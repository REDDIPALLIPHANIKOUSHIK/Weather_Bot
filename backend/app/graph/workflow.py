import logging
from typing import Any
from langgraph.graph import StateGraph, START, END

from ..models import ChatResponse, CurrentLocation
from .state import AdvisoryGraphState
from .nodes import (
    understand_intent_node,
    validate_activity_node,
    resolve_location_node,
    fetch_weather_node,
    retrieve_sops_node,
    evaluate_policies_node,
    compose_response_node,
    save_context_node,
)

logger = logging.getLogger(__name__)


# Conditional Router 1: Activity Validation
def route_activity_validation(state: AdvisoryGraphState) -> str:
    if state.get("is_activity_valid", False):
        return "valid"
    return "unsupported"


# Conditional Router 2: Location Resolution
def route_location_resolution(state: AdvisoryGraphState) -> str:
    if state.get("location_status") == "resolved" and state.get("location") is not None:
        return "resolved"
    return "missing"


# Conditional Router 3: Weather Fetch
def route_weather_fetch(state: AdvisoryGraphState) -> str:
    if state.get("weather") is not None and not state.get("weather_error"):
        return "success"
    return "failure"


# Conditional Router 4: Policy Evaluation Outcome
def route_policy_evaluation(state: AdvisoryGraphState) -> str:
    outcome = state.get("policy_outcome", "no_match")
    if outcome == "matched":
        return "matched"
    elif outcome == "insufficient_data":
        return "insufficient_data"
    return "no_match"


def build_advisory_graph():
    builder = StateGraph(AdvisoryGraphState)

    # 1. Register Nodes
    builder.add_node("understand_intent", understand_intent_node)
    builder.add_node("validate_activity", validate_activity_node)
    builder.add_node("resolve_location", resolve_location_node)
    builder.add_node("fetch_weather", fetch_weather_node)
    builder.add_node("retrieve_sops", retrieve_sops_node)
    builder.add_node("evaluate_policies", evaluate_policies_node)
    builder.add_node("compose_response", compose_response_node)
    builder.add_node("save_context", save_context_node)

    # 2. Sequential & Conditional Edges
    builder.add_edge(START, "understand_intent")
    builder.add_edge("understand_intent", "validate_activity")

    builder.add_conditional_edges(
        "validate_activity",
        route_activity_validation,
        {
            "valid": "resolve_location",
            "unsupported": "compose_response",
        },
    )

    builder.add_conditional_edges(
        "resolve_location",
        route_location_resolution,
        {
            "resolved": "fetch_weather",
            "missing": "compose_response",
        },
    )

    builder.add_conditional_edges(
        "fetch_weather",
        route_weather_fetch,
        {
            "success": "retrieve_sops",
            "failure": "compose_response",
        },
    )

    builder.add_edge("retrieve_sops", "evaluate_policies")

    builder.add_conditional_edges(
        "evaluate_policies",
        route_policy_evaluation,
        {
            "matched": "compose_response",
            "no_match": "compose_response",
            "insufficient_data": "compose_response",
        },
    )

    builder.add_edge("compose_response", "save_context")
    builder.add_edge("save_context", END)

    return builder.compile()


# Compile the production LangGraph application graph
compiled_advisory_graph = build_advisory_graph()


async def run_advisory_graph(
    session_id: str,
    message: str,
    current_location: CurrentLocation | None = None,
    language: str = "en-IN",
    weather_service: Any | None = None,
) -> ChatResponse:
    """Execute query end-to-end through the compiled LangGraph state graph."""
    initial_state: AdvisoryGraphState = {
        "session_id": session_id,
        "message": message,
        "current_location": current_location,
        "language": language,
        "weather_service": weather_service,
        "trace": [f"[LangGraph] Execution initiated for query: '{message}' (session: {session_id})"],
    }

    final_state = await compiled_advisory_graph.ainvoke(initial_state)
    resp = final_state.get("final_response")
    if resp is not None and isinstance(resp, ChatResponse):
        return resp

    # Fallback safety response if graph execution produced unexpected structure
    return ChatResponse(
        answer="I encountered an unexpected internal state while evaluating the safety policy.",
        status="error",
        trace=final_state.get("trace", []),
    )
