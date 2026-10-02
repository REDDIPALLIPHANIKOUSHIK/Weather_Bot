from typing import Any, TypedDict
from ..models import ChatResponse, CurrentLocation, Location, PolicyResult, SOPDefinition, WeatherFacts
from ..services.intent import ExtractedIntent


class AdvisoryGraphState(TypedDict, total=False):
    # Inputs
    session_id: str
    message: str
    current_location: CurrentLocation | None
    language: str
    target_lang: str
    weather_service: Any | None

    # Context & Intent
    session_context: dict[str, Any]
    intent: ExtractedIntent | None
    activity: str | None
    is_activity_valid: bool

    # Location Resolution
    location: Location | None
    location_status: str  # "resolved", "needs_location", "ambiguous", "not_found", "error"
    location_error: str | None

    # Weather Facts
    weather: WeatherFacts | None
    weather_error: str | None

    # Policy Evaluation
    candidate_sops: list[SOPDefinition]
    policy_result: PolicyResult | None
    policy_outcome: str  # "matched", "no_match", "insufficient_data"

    # Response & Execution Trace
    response_status: str
    answer: str | None
    trace: list[str]
    final_response: ChatResponse | None
