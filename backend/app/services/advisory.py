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


def format_weather_summary(w: WeatherFacts, time_ref: str) -> str:
    parts = []
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


class AdvisoryCoordinator:
    def __init__(self, weather_service: WeatherService | None = None):
        self.weather_service = weather_service or WeatherService()

    async def run(
        self,
        session_id: str,
        message: str,
        current_location: CurrentLocation | None = None,
    ) -> ChatResponse:
        trace: list[str] = []
        ctx = get_session_context(session_id)

        trace.append(f"Advisory started for session '{session_id}'")

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
            return ChatResponse(
                answer=(
                    "I can evaluate outdoor safety advisories for cycling, running, hiking, "
                    "walking, pet walking, picnics, commuting, park visits, or outdoor leisure. "
                    "Which activity would you like to check?"
                ),
                status="unsupported_activity",
                trace=trace,
            )

        # 3. Location Resolution Precedence
        # Case A: Explicit location in the user's message or extracted intent
        target_location: Location | None = None

        # Guard against any activity name mistakenly leaking into location_text
        if intent.location_text and (
            intent.location_text.lower() in {"park", "the park", "a park", "walk", "a walk", "running", "cycling", "picnic", "hike", "commuting"}
            or intent.location_text.lower() == str(intent.activity).lower()
        ):
            trace.append(f"Ignored false location candidate '{intent.location_text}' because it matches activity")
            intent.location_text = None

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
        elif intent.use_current_location or (not intent.location_text and current_location is not None):
            if current_location is not None:
                target_location = Location(
                    name="Your current location",
                    country="",
                    latitude=current_location.latitude,
                    longitude=current_location.longitude,
                )
                trace.append(f"Accepted live browser coordinates ({current_location.latitude:.4f}, {current_location.longitude:.4f})")
            else:
                trace.append("Current location requested but coordinates not provided by browser")
                return ChatResponse(
                    answer="To check the weather for your current location, please allow browser location access or enter a city name.",
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
            return ChatResponse(
                answer="Which city or location should I check? You can also click 'Use my location' to check your current area.",
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
        is_current_loc = target_location.name.lower() == "your current location"
        loc_display = "your current location" if is_current_loc else (
            target_location.name if not target_location.country else f"{target_location.name}, {target_location.country}"
        )
        activity_label = {
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

        summary_str = format_weather_summary(weather_facts, intent.time_reference)
        source_citation = f"Source: Open-Meteo at {weather_facts.observed_at} ({weather_facts.timezone})"

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

        if policy_result.outcome == "no_match":
            trace.append("No restrictive SOP triggered for current weather")
            answer_text = (
                f"Standard conditions for {activity_label} in {loc_display}. "
                f"Conditions are within normal limits and no adverse safety policies were triggered. "
                f"{summary_str}. {source_citation}."
            )
            status_str = "no_policy"
        else:
            guidance_text = " ".join(policy_result.guidance)
            answer_text = (
                f"[{policy_result.severity} ADVISORY] {activity_label.title()} in {loc_display}. "
                f"{guidance_text} "
                f"{summary_str}. "
                f"Policy: {policy_result.sop_id} - {policy_result.title}. "
                f"{source_citation}."
            )
            status_str = "matched"

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
