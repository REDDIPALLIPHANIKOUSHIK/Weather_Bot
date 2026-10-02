import logging
from typing import Any
from ..models import ChatResponse, CurrentLocation, Location, PolicyResult, WeatherFacts
from ..policy import evaluate_policies, load_sops
from .intent import SUPPORTED_ACTIVITIES, extract_intent
from .weather import AmbiguousLocationError, UpstreamWeatherError, WeatherService

logger = logging.getLogger(__name__)

# Ephemeral in-process session memory: session_id -> dict
_SESSION_STORE: dict[str, dict[str, Any]] = {}


def get_session_context(session_id: str) -> dict[str, Any]:
    return _SESSION_STORE.setdefault(session_id, {})


def update_session_context(session_id: str, updates: dict[str, Any]):
    ctx = _SESSION_STORE.setdefault(session_id, {})
    ctx.update(updates)


import os
import httpx

LOCALIZED_ACTIVITIES = {
    "te-IN": {
        "cycling": "సైక్లింగ్",
        "running": "పరుగు (రన్నింగ్)",
        "hiking": "హైకింగ్",
        "walking": "నడక (వాకింగ్)",
        "pet_walking": "కుక్కను వాకింగ్‌కి తీసుకెళ్లడం",
        "elderly_outdoor": "పెద్దల బహిరంగ నడక",
        "picnic": "పిక్నిక్",
        "commuting": "ప్రయాణం",
        "park_visit": "పిల్లల పార్క్ సందర్శన",
        "outdoor_leisure": "బహిరంగ విశ్రాంతి",
    },
    "hi-IN": {
        "cycling": "साइकिल चलाना",
        "running": "दौड़ना",
        "hiking": "हाइकिंग",
        "walking": "टहलना",
        "pet_walking": "कुत्ते को टहलाना",
        "elderly_outdoor": "बुजुर्गों का टहलना",
        "picnic": "पिकनिक",
        "commuting": "यात्रा/कम्यूट",
        "park_visit": "बच्चों का पार्क",
        "outdoor_leisure": "बाहर विश्राम",
    },
    "ta-IN": {
        "cycling": "சைக்கிள் ஓட்டுதல்",
        "running": "ஓட்டம்",
        "hiking": "ஹைக்கிங்",
        "walking": "நடைபயிற்சி",
        "pet_walking": "செல்லப்பிராணி நடைபயிற்சி",
        "elderly_outdoor": "முதியவர்கள் நடைபயிற்சி",
        "picnic": "பிக்னிக்",
        "commuting": "பயணம்",
        "park_visit": "பூங்கா வருகை",
        "outdoor_leisure": "வெளிப்புற ஓய்வு",
    },
    "kn-IN": {
        "cycling": "ಸೈಕ್ಲಿಂಗ್",
        "running": "ಓಟ",
        "hiking": "ಹೈಕಿಂಗ್",
        "walking": "ವಾಕಿಂಗ್",
        "pet_walking": "ಸಾಕುಪ್ರಾಣಿ ವಾಕಿಂಗ್",
        "elderly_outdoor": "ಹಿರಿಯರ ನಡಿಗೆ",
        "picnic": "ಪಿಕ್ನಿಕ್",
        "commuting": "ಪ್ರಯಾಣ",
        "park_visit": "ಪಾರ್ಕ್ ಭೇಟಿ",
        "outdoor_leisure": "ಹೊರಾಂಗಣ ವಿಶ್ರಾಂತಿ",
    },
}


def format_weather_summary(w: WeatherFacts, time_ref: str, lang: str = "en-IN") -> str:
    parts = []
    if lang == "te-IN":
        if w.temperature_2m is not None:
            parts.append(f"{w.temperature_2m}°C ఉష్ణోగ్రత")
        if w.wind_speed_10m is not None:
            parts.append(f"గాలి వేగం {w.wind_speed_10m} km/h")
        if w.precipitation_probability is not None:
            parts.append(f"వర్షం సంభావ్యత {w.precipitation_probability}%")
        elif w.precipitation is not None and w.precipitation > 0:
            parts.append(f"{w.precipitation} mm వర్షపాతం")
        if w.uv_index is not None and w.uv_index > 0:
            parts.append(f"UV సూచిక {w.uv_index}")
        label = "ముందస్తు అంచనా" if time_ref not in {"now", "today"} else "ప్రస్తుత పరిస్థితులు"
        metrics_str = ", ".join(parts) if parts else "వివరాలు అందుబాటులో ఉన్నాయి"
        return f"{label}: {metrics_str}"
    elif lang == "hi-IN":
        if w.temperature_2m is not None:
            parts.append(f"तापमान {w.temperature_2m}°C")
        if w.wind_speed_10m is not None:
            parts.append(f"हवा की गति {w.wind_speed_10m} km/h")
        if w.precipitation_probability is not None:
            parts.append(f"बारिश की संभावना {w.precipitation_probability}%")
        elif w.precipitation is not None and w.precipitation > 0:
            parts.append(f"{w.precipitation} मिमी वर्षा")
        if w.uv_index is not None and w.uv_index > 0:
            parts.append(f"यूवी {w.uv_index}")
        label = "पूर्वानुमान" if time_ref not in {"now", "today"} else "वर्तमान स्थिति"
        metrics_str = ", ".join(parts) if parts else "विवरण उपलब्ध हैं"
        return f"{label}: {metrics_str}"
    elif lang == "ta-IN":
        if w.temperature_2m is not None:
            parts.append(f"வெப்பநிலை {w.temperature_2m}°C")
        if w.wind_speed_10m is not None:
            parts.append(f"காற்றின் வேகம் {w.wind_speed_10m} km/h")
        if w.precipitation_probability is not None:
            parts.append(f"மழை வாய்ப்பு {w.precipitation_probability}%")
        if w.uv_index is not None and w.uv_index > 0:
            parts.append(f"UV {w.uv_index}")
        label = "முன்னறிவிப்பு" if time_ref not in {"now", "today"} else "தற்போதைய வானிலை"
        metrics_str = ", ".join(parts) if parts else "விவரங்கள் உள்ளன"
        return f"{label}: {metrics_str}"
    elif lang == "kn-IN":
        if w.temperature_2m is not None:
            parts.append(f"ತಾಪಮಾನ {w.temperature_2m}°C")
        if w.wind_speed_10m is not None:
            parts.append(f"ಗಾಳಿಯ ವೇಗ {w.wind_speed_10m} km/h")
        if w.precipitation_probability is not None:
            parts.append(f"ಮಳೆಯ ಸಂಭವನೀಯತೆ {w.precipitation_probability}%")
        if w.uv_index is not None and w.uv_index > 0:
            parts.append(f"UV {w.uv_index}")
        label = "ಮುನ್ಸೂಚನೆ" if time_ref not in {"now", "today"} else "ಪ್ರಸ್ತುತ ಹವಾಮಾನ"
        metrics_str = ", ".join(parts) if parts else "ವಿವರ ಲಭ್ಯವಿದೆ"
        return f"{label}: {metrics_str}"
    else:
        if w.temperature_2m is not None:
            parts.append(f"{w.temperature_2m}°C")
        if w.wind_speed_10m is not None:
            parts.append(f"winds {w.wind_speed_10m} km/h")
        if w.precipitation_probability is not None:
            parts.append(f"{w.precipitation_probability}% rain probability")
        elif w.precipitation is not None and w.precipitation > 0:
            parts.append(f"{w.precipitation} mm precipitation")
        if w.uv_index is not None and w.uv_index > 0:
            parts.append(f"UV index {w.uv_index}")

        label = "Forecast" if time_ref not in {"now", "today"} else "Current conditions"
        metrics_str = ", ".join(parts) if parts else "metrics unavailable"
        return f"{label}: {metrics_str}"


def format_source_citation(w: WeatherFacts, lang: str = "en-IN") -> str:
    if lang == "te-IN":
        return f"మూలం: Open-Meteo ({w.observed_at})"
    elif lang == "hi-IN":
        return f"स्रोत: Open-Meteo ({w.observed_at})"
    elif lang == "ta-IN":
        return f"மூலம்: Open-Meteo ({w.observed_at})"
    elif lang == "kn-IN":
        return f"ಮೂಲ: Open-Meteo ({w.observed_at})"
    return f"Source: Open-Meteo at {w.observed_at} ({w.timezone})"


def detect_target_language(message: str, requested_lang: str) -> str:
    # Auto-detect Indic script from message if typed in that language
    if any("\u0c00" <= ch <= "\u0c7f" for ch in message):
        return "te-IN"
    if any("\u0900" <= ch <= "\u097f" for ch in message):
        return "hi-IN"
    if any("\u0b80" <= ch <= "\u0bff" for ch in message):
        return "ta-IN"
    if any("\u0c80" <= ch <= "\u0cff" for ch in message):
        return "kn-IN"
    if any("\u0d00" <= ch <= "\u0d7f" for ch in message):
        return "ml-IN"
    if any("\u0980" <= ch <= "\u09ff" for ch in message):
        return "bn-IN"
    return requested_lang or "en-IN"


LOCALIZED_MESSAGES = {
    "te-IN": {
        "unsupported": (
            "నేను సైక్లింగ్, రన్నింగ్, హైకింగ్, వాకింగ్, పెట్ వాకింగ్, పిక్నిక్, "
            "కమ్యూటింగ్, లేదా పార్క్ సందర్శనల కోసం బహిరంగ భద్రతా సూచనలను అంచనా వేయగలను. "
            "మీరు ఏ కార్యాచరణను తనిఖీ చేయాలనుకుంటున్నారు?"
        ),
        "needs_location": (
            "మీ ప్రస్తుత ప్రదేశం కోసం వాతావరణాన్ని తనిఖీ చేయడానికి, దయచేసి స్థాన అనుమతిని "
            "అనుమతించండి లేదా ఒక నగరం పేరును నమోదు చేయండి."
        ),
        "standard_prefix": "{loc}లో {act} కోసం పరిస్థితులు అనుకూలంగా ఉన్నాయి. ఎటువంటి ప్రతికూల భద్రతా హెచ్చరికలు లేవు.",
        "advisory_prefix": "[{sev} హెచ్చరిక] {loc}లో {act}.",
        "policy_label": "భద్రతా విధానం",
    },
    "hi-IN": {
        "unsupported": (
            "मैं साइकिल चलाने, दौड़ने, लंबी पैदल यात्रा, टहलने, पालतू जानवरों को टहलाने, पिकनिक "
            "या पार्क जाने के लिए मौसम सुरक्षा सलाह दे सकता हूँ। आप किस गतिविधि की जांच करना चाहते हैं?"
        ),
        "needs_location": (
            "मौसम की जांच करने के लिए, कृपया स्थान की अनुमति दें या किसी शहर का नाम दर्ज करें।"
        ),
        "standard_prefix": "{loc} में {act} के लिए सामान्य मौसम की स्थिति है। कोई प्रतिकूल सुरक्षा चेतावनी नहीं है।",
        "advisory_prefix": "[{sev} चेतावनी] {loc} में {act}।",
        "policy_label": "सुरक्षा नीति",
    },
    "ta-IN": {
        "unsupported": (
            "சைக்கிள் ஓட்டுதல், ஓடுதல், நடைபயிற்சி, பிக்னிக், அல்லது பூங்கா வருகைகளுக்கான வானிலை "
            "பாதுகாப்பு ஆலோசனைகளை என்னால் மதிப்பீடு செய்ய முடியும். எந்தச் செயல்பாட்டைச் சரிபார்க்க விரும்புகிறீர்கள்?"
        ),
        "needs_location": "வானிலையைச் சரிபார்க்க, தயவுசெய்து இருப்பிட அனுமதியை வழங்கவும் அல்லது நகரத்தின் பெயரை உள்ளிடவும்.",
        "standard_prefix": "{loc} இல் {act} செய்வதற்கு சாதகமான வானிலை நிலவுகிறது. பாதகமான எச்சரிக்கைகள் எதுவும் இல்லை.",
        "advisory_prefix": "[{sev} எச்சரிக்கை] {loc} இல் {act}.",
        "policy_label": "பாதுகாப்புக் கொள்கை",
    },
    "kn-IN": {
        "unsupported": "ಸೈಕ್ಲಿಂಗ್, ಓಟ, ವಾಕಿಂಗ್, ಪಿಕ್ನಿಕ್, ಅಥವಾ ಪಾರ್ಕ್ ಭೇಟಿಗಳ ಸುರಕ್ಷತಾ ಸಲಹೆಗಳನ್ನು ನಾನು ನೀಡಬಲ್ಲೆ. ನೀವು ಯಾವ ಚಟುವಟಿಕೆಯನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?",
        "needs_location": "ಹವಾಮಾನವನ್ನು ಪರೀಕ್ಷಿಸಲು, ದಯವಿಟ್ಟು ಸ್ಥಳ ಪ್ರವೇಶವನ್ನು ಅನುಮತಿಸಿ ಅಥವಾ ನಗರದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ.",
        "standard_prefix": "{loc} ನಲ್ಲಿ {act} ಗೆ ಸಾಮಾನ್ಯ ಹವಾಮಾನ ಪರಿಸ್ಥಿತಿಗಳಿವೆ. ಯಾವುದೇ ಪ್ರತಿಕೂಲ ಎಚ್ಚರಿಕೆಗಳಿಲ್ಲ.",
        "advisory_prefix": "[{sev} ಎಚ್ಚರಿಕೆ] {loc} ನಲ್ಲಿ {act}.",
        "policy_label": "ಸುರಕ್ಷತಾ ನೀತಿ",
    },
}


async def polish_or_translate_advisory(raw_answer: str, target_lang: str) -> str:
    if target_lang == "en-IN":
        return raw_answer

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return raw_answer

    lang_map = {
        "te-IN": "Telugu",
        "hi-IN": "Hindi",
        "ta-IN": "Tamil",
        "kn-IN": "Kannada",
        "ml-IN": "Malayalam",
        "mr-IN": "Marathi",
        "bn-IN": "Bengali",
    }
    lang_name = lang_map.get(target_lang)
    if not lang_name:
        return raw_answer

    try:
        model = os.getenv("GEMINI_INTENT_MODEL", "gemini-2.0-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        prompt = (
            f"You are Weatherwise. Translate and present this strictly grounded outdoor weather advisory into fluent, respectful, natural {lang_name}.\n"
            "STRICT CONSTRAINTS:\n"
            "1. Keep all numbers, metrics (°C, km/h, %), times, location names, and safety guidance 100% faithful to the source.\n"
            "2. Do NOT add any ungrounded weather claims or alter safety decisions.\n"
            "3. Output ONLY the translated advisory text, no quotes or preamble.\n\n"
            f"Source advisory:\n{raw_answer}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 350,
            },
        }
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(url, json=body)
            if resp.status_code == 200:
                data = resp.json()
                translated = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if translated:
                    return translated
    except Exception as err:
        logger.debug("Advisory translation with Gemini failed: %s", err)

    return raw_answer


class AdvisoryCoordinator:
    def __init__(self, weather_service: WeatherService | None = None):
        self.weather_service = weather_service or WeatherService()

    async def run(
        self,
        session_id: str,
        message: str,
        current_location: CurrentLocation | None = None,
        language: str = "en-IN",
    ) -> ChatResponse:
        trace: list[str] = []
        ctx = get_session_context(session_id)
        target_lang = detect_target_language(message, language)

        trace.append(f"Advisory started for session '{session_id}' (lang: {target_lang})")

        # Persist and reuse current location in session memory
        if current_location is not None:
            update_session_context(session_id, {"current_location": current_location.model_dump()})
            effective_current_loc = current_location
        elif ctx.get("current_location"):
            try:
                effective_current_loc = CurrentLocation.model_validate(ctx["current_location"])
                trace.append("Reused current_location from session context")
            except Exception:
                effective_current_loc = None
        else:
            effective_current_loc = None

        # 1. Intent Extraction
        intent = await extract_intent(message, ctx)
        trace.append(
            f"Intent extracted via {intent.extraction_source}: "
            f"activity='{intent.activity}', location='{intent.location_text}', "
            f"use_curr={intent.use_current_location}, time='{intent.time_reference}'"
        )

        # 2. Activity Validation
        if not intent.activity or intent.activity not in SUPPORTED_ACTIVITIES:
            trace.append("Activity unsupported or unrecognized")
            unsupported_text = (
                LOCALIZED_MESSAGES.get(target_lang, {}).get("unsupported")
                or (
                    "I can evaluate outdoor safety advisories for cycling, running, hiking, "
                    "walking, pet walking, picnics, commuting, park visits, or outdoor leisure. "
                    "Which activity would you like to check?"
                )
            )
            return ChatResponse(
                answer=unsupported_text,
                status="unsupported_activity",
                trace=trace,
            )

        # 3. Location Resolution Precedence
        target_location: Location | None = None

        # Guard against any activity name mistakenly leaking into location_text
        if intent.location_text and (
            intent.location_text.lower() in {"park", "the park", "a park", "walk", "a walk", "running", "cycling", "picnic", "hike", "commuting"}
            or intent.location_text.lower() == str(intent.activity).lower()
        ):
            trace.append(f"Ignored false location candidate '{intent.location_text}' because it matches activity")
            intent.location_text = None

        # Case A: Explicit location in the user's message or extracted intent
        if intent.location_text and not intent.use_current_location:
            try:
                resolved_loc = await self.weather_service.geocode(intent.location_text)
                if not resolved_loc:
                    trace.append(f"Geocoding returned no results for '{intent.location_text}'")
                    return ChatResponse(
                        answer=f"I couldn't find a location named '{intent.location_text}'. Please check the spelling or try a nearby city.",
                        status="location_not_found",
                        trace=trace,
                    )
                target_location = resolved_loc
                trace.append(f"Geocoded '{intent.location_text}' -> {resolved_loc.name}, {resolved_loc.country}")
            except AmbiguousLocationError as amb_err:
                trace.append(f"Ambiguous location '{intent.location_text}': {amb_err}")
                return ChatResponse(
                    answer=f"Multiple locations match '{intent.location_text}' ({amb_err}). Please specify which country or state you mean.",
                    status="location_ambiguous",
                    trace=trace,
                )
            except UpstreamWeatherError as up_err:
                trace.append(f"Geocoding service upstream failure: {up_err}")
                return ChatResponse(
                    answer="I couldn't reach the location service right now. Please try again in a moment.",
                    status="weather_unavailable",
                    trace=trace,
                )

        # Case B: "here" / "current location" or no explicit city with live coordinates
        elif intent.use_current_location or (not intent.location_text and effective_current_loc is not None):
            if effective_current_loc is not None:
                loc_name = effective_current_loc.city_name.strip() if effective_current_loc.city_name else "Your current location"
                target_location = Location(
                    name=loc_name,
                    country="",
                    latitude=effective_current_loc.latitude,
                    longitude=effective_current_loc.longitude,
                )
                trace.append(f"Accepted live browser coordinates ({effective_current_loc.latitude:.4f}, {effective_current_loc.longitude:.4f}) for '{loc_name}'")
            else:
                trace.append("Current location requested but coordinates not provided by browser")
                needs_loc_msg = (
                    LOCALIZED_MESSAGES.get(target_lang, {}).get("needs_location")
                    or "To check the weather for your current location, please allow browser location access or enter a city name."
                )
                return ChatResponse(
                    answer=needs_loc_msg,
                    status="needs_location",
                    trace=trace,
                )

        # Case C: Reusing previous location from session context if available
        elif ctx.get("location_text"):
            prev_loc_name = ctx["location_text"]
            try:
                resolved_loc = await self.weather_service.geocode(prev_loc_name)
                if resolved_loc:
                    target_location = resolved_loc
                    trace.append(f"Reused session location: {resolved_loc.name}, {resolved_loc.country}")
            except Exception as err:
                trace.append(f"Session location re-geocode failed: {err}")

        # Case D: Location missing entirely
        if not target_location:
            trace.append("No explicit, live, or session location available")
            needs_loc_msg = (
                LOCALIZED_MESSAGES.get(target_lang, {}).get("needs_location")
                or "Which city or location should I check? You can also click 'Use my location' to check your current area."
            )
            return ChatResponse(
                answer=needs_loc_msg,
                status="needs_location",
                trace=trace,
            )

        # 4. Fetch Live Weather Data from Open-Meteo
        try:
            weather_facts = await self.weather_service.forecast(target_location, intent.time_reference)
            trace.append(
                f"Retrieved live Open-Meteo weather for {target_location.name}: "
                f"temp={weather_facts.temperature_2m}°C, wind={weather_facts.wind_speed_10m} km/h, "
                f"precip_prob={weather_facts.precipitation_probability}%, uv={weather_facts.uv_index}"
            )
        except UpstreamWeatherError as err:
            trace.append(f"Weather API failed: {err}")
            return ChatResponse(
                answer="Live weather data is temporarily unavailable from Open-Meteo. Please try again in a few moments.",
                status="weather_unavailable",
                location=target_location,
                trace=trace,
            )

        # 5. Retrieve Candidate SOPs
        all_sops = load_sops()
        candidate_sops = [s for s in all_sops if intent.activity in s.activities]
        trace.append(f"Found {len(candidate_sops)} applicable SOP definitions for '{intent.activity}'")

        # 6. Deterministic Policy Evaluation
        facts_dict = weather_facts.model_dump()
        facts_dict["activity"] = intent.activity

        policy_result = evaluate_policies(all_sops, intent.activity, facts_dict)
        trace.append(f"Policy evaluation outcome: {policy_result.outcome} (matched: {policy_result.sop_id or 'none'})")

        # 7. Compose Grounded Response
        is_current_loc = (
            not target_location.name
            or target_location.name.lower() in {"your current location", "current location"}
        )
        if is_current_loc:
            loc_display = {
                "te-IN": "మీ ప్రస్తుత ప్రదేశం",
                "hi-IN": "आपके वर्तमान स्थान",
                "ta-IN": "உங்கள் தற்போதைய இருப்பிடம்",
                "kn-IN": "ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಸ್ಥಳ",
            }.get(target_lang, "your current location")
        else:
            loc_display = target_location.name if not target_location.country else f"{target_location.name}, {target_location.country}"

        # Localized or friendly activity label
        activity_label = (
            LOCALIZED_ACTIVITIES.get(target_lang, {}).get(intent.activity)
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
            }.get(intent.activity, intent.activity.replace("_", " "))
        )

        summary_str = format_weather_summary(weather_facts, intent.time_reference, target_lang)
        source_citation = format_source_citation(weather_facts, target_lang)

        if policy_result.outcome == "insufficient_data":
            trace.append("Required weather fields for policy evaluation were missing")
            return ChatResponse(
                answer=(
                    f"A weather metric required to evaluate safety for {activity_label} in {loc_display} "
                    f"was not provided by the weather feed. To ensure your safety, no ungrounded recommendation can be made."
                ),
                status="insufficient_data",
                location=target_location,
                weather=weather_facts,
                policy=policy_result,
                trace=trace,
            )

        loc_msgs = LOCALIZED_MESSAGES.get(target_lang)

        if policy_result.outcome == "no_match":
            trace.append("No restrictive SOP triggered for current weather")
            if loc_msgs:
                prefix = loc_msgs["standard_prefix"].format(loc=loc_display, act=activity_label)
                answer_text = f"{prefix} {summary_str} {source_citation}."
            else:
                answer_text = (
                    f"Standard conditions for {activity_label} in {loc_display}. "
                    f"Conditions are within normal limits and no adverse safety policies were triggered. "
                    f"{summary_str}. {source_citation}."
                )
            status_str = "no_policy"
        else:
            guidance_text = " ".join(policy_result.guidance)
            if loc_msgs:
                prefix = loc_msgs["advisory_prefix"].format(sev=policy_result.severity, loc=loc_display, act=activity_label)
                pol_lbl = loc_msgs["policy_label"]
                answer_text = (
                    f"{prefix} {guidance_text} {summary_str} "
                    f"{pol_lbl}: {policy_result.sop_id} - {policy_result.title}. "
                    f"{source_citation}."
                )
            else:
                answer_text = (
                    f"[{policy_result.severity} ADVISORY] {activity_label.title()} in {loc_display}. "
                    f"{guidance_text} "
                    f"{summary_str}. "
                    f"Policy: {policy_result.sop_id} - {policy_result.title}. "
                    f"{source_citation}."
                )
            status_str = "matched"

        # Apply polish/natural translation for non-English responses if Gemini is available
        if target_lang != "en-IN":
            answer_text = await polish_or_translate_advisory(answer_text, target_lang)

        # Update Session Memory
        update_session_context(session_id, {
            "activity": intent.activity,
            "location_text": intent.location_text or target_location.name,
            "time_reference": intent.time_reference,
        })

        trace.append("Grounded answer generated successfully")

        return ChatResponse(
            answer=answer_text,
            status=status_str,
            location=target_location,
            weather=weather_facts,
            policy=policy_result,
            trace=trace,
        )
