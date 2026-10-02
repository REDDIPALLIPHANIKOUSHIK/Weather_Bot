import logging
import os
from typing import Any
import httpx

from ..models import ChatResponse, CurrentLocation, Location, PolicyResult, WeatherFacts
from ..policy import evaluate_policies, load_sops
from ..services.advisory import (
    LOCALIZED_ACTIVITIES,
    LOCALIZED_MESSAGES,
    detect_target_language,
    format_source_citation,
    format_weather_summary,
    get_session_context,
    polish_or_translate_advisory,
    update_session_context,
)
from ..services.intent import (
    ACTIVITY_BY_KEYWORD,
    ACTIVITY_WORDS,
    SUPPORTED_ACTIVITIES,
    extract_intent,
)
from ..services.weather import (
    AmbiguousLocationError,
    UpstreamWeatherError,
    WeatherService,
)
from .state import AdvisoryGraphState

logger = logging.getLogger(__name__)
_weather_service = WeatherService()


async def understand_intent_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    session_id = state.get("session_id", "default_session")
    message = state.get("message", "")
    language = state.get("language", "en-IN")
    target_lang = detect_target_language(message, language)

    trace.append(f"[LangGraph:understand_intent] Started for session '{session_id}' (lang: {target_lang})")

    ctx = state.get("session_context") or get_session_context(session_id)
    intent = await extract_intent(message, ctx)

    trace.append(
        f"[LangGraph:understand_intent] Extracted intent via {intent.extraction_source}: "
        f"activity='{intent.activity}', location='{intent.location_text}', "
        f"use_curr={intent.use_current_location}, time='{intent.time_reference}'"
    )

    return {
        "target_lang": target_lang,
        "session_context": ctx,
        "intent": intent,
        "activity": intent.activity,
        "trace": trace,
    }


def validate_activity_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    activity = state.get("activity")

    is_valid = bool(activity and activity in SUPPORTED_ACTIVITIES)
    if is_valid:
        trace.append(f"[LangGraph:validate_activity] Activity '{activity}' is valid and supported")
    else:
        trace.append(f"[LangGraph:validate_activity] Activity '{activity}' is unsupported or unrecognized")

    return {
        "is_activity_valid": is_valid,
        "trace": trace,
    }


async def resolve_location_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    intent = state.get("intent")
    session_id = state.get("session_id", "default_session")
    current_location = state.get("current_location")
    ctx = state.get("session_context") or get_session_context(session_id)

    # Persist and reuse current location in session memory
    if current_location is not None:
        update_session_context(session_id, {"current_location": current_location.model_dump()})
        effective_current_loc = current_location
    elif ctx.get("current_location"):
        try:
            effective_current_loc = CurrentLocation.model_validate(ctx["current_location"])
            trace.append("[LangGraph:resolve_location] Reused current_location from session context")
        except Exception:
            effective_current_loc = None
    else:
        effective_current_loc = None

    target_location: Location | None = None
    loc_status = "resolved"
    loc_error: str | None = None

    ws = state.get("weather_service") or _weather_service

    if intent:
        # Guard against any activity name mistakenly leaking into location_text
        if intent.location_text and (
            intent.location_text.lower() in ACTIVITY_WORDS
            or intent.location_text.lower() in ACTIVITY_BY_KEYWORD
            or intent.location_text.lower() == str(intent.activity).lower()
        ):
            trace.append(f"[LangGraph:resolve_location] Ignored false location candidate '{intent.location_text}' matching activity")
            intent.location_text = None

        # Case A: Explicit location in the user's query
        if intent.location_text and not intent.use_current_location:
            try:
                resolved_loc = await ws.geocode(intent.location_text)
                if not resolved_loc:
                    trace.append(f"[LangGraph:resolve_location] Geocoding returned no results for '{intent.location_text}'")
                    loc_status = "not_found"
                    loc_error = f"I couldn't find a location named '{intent.location_text}'. Please check spelling or try a nearby city."
                else:
                    target_location = resolved_loc
                    trace.append(f"[LangGraph:resolve_location] Geocoded '{intent.location_text}' -> {resolved_loc.name}, {resolved_loc.country}")
            except AmbiguousLocationError as amb_err:
                trace.append(f"[LangGraph:resolve_location] Ambiguous location '{intent.location_text}': {amb_err}")
                loc_status = "ambiguous"
                loc_error = str(amb_err)
            except UpstreamWeatherError as up_err:
                trace.append(f"[LangGraph:resolve_location] Geocoding upstream failure: {up_err}")
                loc_status = "error"
                loc_error = str(up_err)

        # Case B: "here" / "current location" or coordinates available
        elif intent.use_current_location or (not intent.location_text and effective_current_loc is not None):
            if effective_current_loc is not None:
                loc_name = effective_current_loc.city_name.strip() if effective_current_loc.city_name else "Your current location"
                target_location = Location(
                    name=loc_name,
                    country="",
                    latitude=effective_current_loc.latitude,
                    longitude=effective_current_loc.longitude,
                )
                trace.append(f"[LangGraph:resolve_location] Accepted live coordinates ({effective_current_loc.latitude:.4f}, {effective_current_loc.longitude:.4f}) for '{loc_name}'")
            else:
                trace.append("[LangGraph:resolve_location] Current location requested but coordinates not provided by browser")
                loc_status = "needs_location"

        # Case C: Previous session location
        elif ctx.get("location_text"):
            prev_loc_name = ctx["location_text"]
            try:
                resolved_loc = await ws.geocode(prev_loc_name)
                if resolved_loc:
                    target_location = resolved_loc
                    trace.append(f"[LangGraph:resolve_location] Reused session location: {resolved_loc.name}, {resolved_loc.country}")
            except Exception as err:
                trace.append(f"[LangGraph:resolve_location] Session location re-geocode failed: {err}")

    if not target_location and loc_status == "resolved":
        trace.append("[LangGraph:resolve_location] No explicit, live, or session location available")
        loc_status = "needs_location"

    return {
        "location": target_location,
        "location_status": loc_status,
        "location_error": loc_error,
        "trace": trace,
    }


async def fetch_weather_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    loc = state.get("location")
    intent = state.get("intent")
    time_ref = intent.time_reference if intent else "today"
    ws = state.get("weather_service") or _weather_service

    weather_facts: WeatherFacts | None = None
    weather_err: str | None = None

    if loc:
        try:
            weather_facts = await ws.forecast(loc, time_ref)
            trace.append(
                f"[LangGraph:fetch_weather] Retrieved Open-Meteo weather for {loc.name}: "
                f"temp={weather_facts.temperature_2m}°C, wind={weather_facts.wind_speed_10m} km/h, "
                f"precip_prob={weather_facts.precipitation_probability}%, uv={weather_facts.uv_index}"
            )
        except UpstreamWeatherError as err:
            trace.append(f"[LangGraph:fetch_weather] Weather API failure: {err}")
            weather_err = str(err)

    return {
        "weather": weather_facts,
        "weather_error": weather_err,
        "trace": trace,
    }


def retrieve_sops_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    activity = state.get("activity") or ""

    all_sops = load_sops()
    candidates = [s for s in all_sops if activity in s.activities]
    trace.append(f"[LangGraph:retrieve_sops] Retrieved {len(candidates)} candidate SOPs for activity '{activity}'")

    return {
        "candidate_sops": candidates,
        "trace": trace,
    }


def evaluate_policies_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    candidates = state.get("candidate_sops", [])
    activity = state.get("activity") or ""
    weather = state.get("weather")

    if not weather:
        policy_result = PolicyResult(
            outcome="insufficient_data",
            trace=[{"error": "Weather facts unavailable for policy evaluation"}],
        )
    else:
        facts_dict = weather.model_dump()
        facts_dict["activity"] = activity
        policy_result = evaluate_policies(candidates, activity, facts_dict)

    trace.append(f"[LangGraph:evaluate_policies] Outcome: {policy_result.outcome} (matched: {policy_result.sop_id or 'none'})")

    return {
        "policy_result": policy_result,
        "policy_outcome": policy_result.outcome,
        "trace": trace,
    }


async def compose_response_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    target_lang = state.get("target_lang", "en-IN")
    is_activity_valid = state.get("is_activity_valid", False)
    activity = state.get("activity")
    loc_status = state.get("location_status", "resolved")
    loc_error = state.get("location_error")
    target_loc = state.get("location")
    weather_err = state.get("weather_error")
    weather = state.get("weather")
    policy_res = state.get("policy_result")
    intent = state.get("intent")
    time_ref = intent.time_reference if intent else "today"

    trace.append(f"[LangGraph:compose_response] Composing grounded response (lang: {target_lang})")

    # Branch 1: Unsupported / Unrecognized Activity
    if not is_activity_valid:
        msg = (
            LOCALIZED_MESSAGES.get(target_lang, {}).get("unsupported")
            or "I can evaluate outdoor safety advisories for cycling, running, hiking, walking, pet walking, picnics, commuting, park visits, or outdoor leisure. Which activity would you like to check?"
        )
        resp = ChatResponse(answer=msg, status="unsupported_activity", trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "unsupported_activity", "trace": trace}

    # Branch 2: Location Missing / Ambiguous / Not Found
    if loc_status == "needs_location":
        msg = (
            LOCALIZED_MESSAGES.get(target_lang, {}).get("needs_location")
            or "To check the weather for your current location, please allow browser location access or enter a city name."
        )
        resp = ChatResponse(answer=msg, status="needs_location", trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "needs_location", "trace": trace}

    if loc_status == "ambiguous":
        msg = f"Multiple locations match '{intent.location_text if intent else ''}' ({loc_error}). Please specify which country or state you mean."
        resp = ChatResponse(answer=msg, status="location_ambiguous", trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "location_ambiguous", "trace": trace}

    if loc_status == "not_found":
        msg = loc_error or f"I couldn't find a location named '{intent.location_text if intent else ''}'. Please check the spelling or try a nearby city."
        resp = ChatResponse(answer=msg, status="location_not_found", trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "location_not_found", "trace": trace}

    if loc_status == "error":
        msg = "I couldn't reach the location service right now. Please try again in a moment."
        resp = ChatResponse(answer=msg, status="weather_unavailable", trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "weather_unavailable", "trace": trace}

    # Branch 3: Weather API Failure
    if weather_err or not weather:
        msg = "Live weather data is temporarily unavailable from Open-Meteo. Please try again in a few moments."
        resp = ChatResponse(answer=msg, status="weather_unavailable", location=target_loc, trace=trace)
        return {"final_response": resp, "answer": msg, "response_status": "weather_unavailable", "trace": trace}

    # Branch 4: Grounded Safety Decision Composition
    is_current_loc = (
        not target_loc
        or not target_loc.name
        or target_loc.name.lower() in {"your current location", "current location"}
    )
    if is_current_loc:
        loc_display = {
            "te-IN": "మీ ప్రస్తుత ప్రదేశం",
            "hi-IN": "आपके वर्तमान स्थान",
            "ta-IN": "உங்கள் தற்போதைய இருப்பிடம்",
            "kn-IN": "ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಸ್ಥಳ",
        }.get(target_lang, "your current location")
    else:
        loc_display = target_loc.name if not target_loc.country else f"{target_loc.name}, {target_loc.country}"

    activity_label = (
        LOCALIZED_ACTIVITIES.get(target_lang, {}).get(activity or "")
        or {
            "park_visit": "a children's park visit",
            "pet_walking": "walking a pet",
            "elderly_outdoor": "an elderly outdoor visit",
            "picnic": "a picnic",
            "commuting": "commuting",
            "outdoor_leisure": "outdoor leisure",
            "cycling": "cycling",
            "running": "running",
            "hiking": "hiking",
            "walking": "walking",
        }.get(activity or "", str(activity).replace("_", " "))
    )

    summary_str = format_weather_summary(weather, time_ref, target_lang)
    source_citation = format_source_citation(weather, target_lang)

    # Outcome A: Insufficient Weather Data
    if not policy_res or policy_res.outcome == "insufficient_data":
        trace.append("[LangGraph:compose_response] Required weather fields missing for safe policy evaluation")
        answer_text = (
            f"A weather metric required to evaluate safety for {activity_label} in {loc_display} "
            f"was not provided by the weather feed. To ensure your safety, no ungrounded recommendation can be made."
        )
        status_str = "insufficient_data"

    # Outcome B: No SOP matched (CRITICAL REQUIREMENT: Honest statement, never say 'conditions are normal' or 'everything is safe')
    elif policy_res.outcome == "no_match":
        trace.append("[LangGraph:compose_response] Honest no-SOP match branch: No applicable SOP rule exists for conditions")
        if target_lang == "te-IN":
            answer_text = (
                f"{loc_display}లో {activity_label} కోసం ప్రస్తుత పరిస్థితుల్లో వర్తించే Weatherwise SOP నిబంధనలు ఏవీ లేవు, "
                f"కాబట్టి విధాన-ఆధారిత భద్రతా సిఫార్సు అందించబడదు. {summary_str} {source_citation}."
            )
        elif target_lang == "hi-IN":
            answer_text = (
                f"वर्तमान परिस्थितियों में {loc_display} में {activity_label} के लिए कोई लागू Weatherwise SOP नियम नहीं है, "
                f"इसलिए कोई नीति-आधारित सुरक्षा अनुशंसा प्रदान नहीं की जा सकती। {summary_str} {source_citation}."
            )
        elif target_lang == "ta-IN":
            answer_text = (
                f"தற்போதைய வானிலை நிலைமைகளில் {loc_display} இல் {activity_label} க்குப் பொருந்தக்கூடிய Weatherwise SOP விதிகள் எதுவும் இல்லை, "
                f"எனவே கொள்கை அடிப்படையிலான பாதுகாப்பு பரிந்துரையை வழங்க முடியாது. {summary_str} {source_citation}."
            )
        elif target_lang == "kn-IN":
            answer_text = (
                f"ಪ್ರಸ್ತುತ ಹವಾಮಾನ ಪರಿಸ್ಥಿತಿಗಳಲ್ಲಿ {loc_display} ನಲ್ಲಿ {activity_label} ಗೆ ಅನ್ವಯವಾಗುವ ಯಾವುದೇ Weatherwise SOP ನಿಯಮಗಳಿಲ್ಲ, "
                f"ಆದ್ದರಿಂದ ನೀತಿ-ಆಧಾರಿತ ಸುರಕ್ಷತಾ ಶಿಫಾರಸನ್ನು ನೀಡಲಾಗುವುದಿಲ್ಲ. {summary_str} {source_citation}."
            )
        else:
            answer_text = (
                f"No applicable Weatherwise SOP exists for {activity_label} in {loc_display} under current conditions, "
                f"so no policy-backed safety recommendation can be provided. {summary_str}. {source_citation}."
            )
        status_str = "no_policy"

    # Outcome C: SOP Matched
    else:
        trace.append(f"[LangGraph:compose_response] Matched SOP {policy_res.sop_id} with severity {policy_res.severity}")
        guidance_text = " ".join(policy_res.guidance)
        loc_msgs = LOCALIZED_MESSAGES.get(target_lang)

        if loc_msgs:
            prefix = loc_msgs["advisory_prefix"].format(sev=policy_res.severity, loc=loc_display, act=activity_label)
            pol_lbl = loc_msgs.get("policy_label", "విధానం")
            answer_text = (
                f"{prefix} {guidance_text} {summary_str} "
                f"{pol_lbl}: {policy_res.sop_id} - {policy_res.title}. "
                f"{source_citation}."
            )
        else:
            answer_text = (
                f"[{policy_res.severity} ADVISORY] {activity_label.title()} in {loc_display}. "
                f"{guidance_text} "
                f"{summary_str}. "
                f"Policy: {policy_res.sop_id} - {policy_res.title}. "
                f"{source_citation}."
            )
        status_str = "matched"

    # Natural Indic translation polish if Gemini is available
    if target_lang != "en-IN":
        answer_text = await polish_or_translate_advisory(answer_text, target_lang)

    resp = ChatResponse(
        answer=answer_text,
        status=status_str,
        location=target_loc,
        weather=weather,
        policy=policy_res,
        trace=trace,
    )

    return {
        "final_response": resp,
        "answer": answer_text,
        "response_status": status_str,
        "trace": trace,
    }


def save_context_node(state: AdvisoryGraphState) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    session_id = state.get("session_id", "default_session")
    activity = state.get("activity")
    intent = state.get("intent")
    target_loc = state.get("location")

    if activity or (intent and intent.location_text) or target_loc:
        update_session_context(session_id, {
            "activity": activity,
            "location_text": (intent.location_text if intent else None) or (target_loc.name if target_loc else None),
            "time_reference": intent.time_reference if intent else "today",
        })
        trace.append(f"[LangGraph:save_context] Updated session memory for '{session_id}'")

    return {"trace": trace}
