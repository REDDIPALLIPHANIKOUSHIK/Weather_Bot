import re
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from .services import OpenMeteo, UpstreamError, AmbiguousLocation, load_sops, evaluate_policies
from .models import Location
from .llm import extract_intent

class AdvisoryState(TypedDict, total=False):
    session_id: str; message: str; activity: str; category: str; location_text: str | None
    location: Location | None; weather: dict[str, Any] | None; policy: dict[str, Any] | None
    candidate_sops: list[dict[str, Any]]; answer: str; status: str; trace: list[str]; time_reference: str

sessions: dict[str, dict[str, Any]] = {}
weather_service = OpenMeteo()
ACTIVITIES = {"cycling": ("cycling", ["cycle", "cycling", "bike", "biking"]), "running": ("running", ["run", "running", "jog", "jogging"]),
 "hiking": ("hiking", ["hike", "hiking", "trek", "trekking"]), "picnic": ("picnic", ["picnic"]), "pet_walking": ("pet walking", ["walk the dog", "walk my dog", "dog walk", "pet walk"]), "elderly_outdoor": ("elderly outdoor activity", ["elderly", "senior", "older parent"]), "walking": ("walking", ["walk", "walking"]),
 "commuting": ("commuting", ["commute", "commuting", "ride to work"]), "park_visit": ("park visit", ["park", "playground"]), "outdoor_leisure": ("outdoor leisure", ["outdoor", "leisure", "garden"])}

async def understand(state: AdvisoryState):
    text = state["message"].lower()
    try:
        known = sessions.get(state["session_id"], {})
        structured = await extract_intent(state["message"], known)
    except RuntimeError:
        return {"status":"intent_unavailable", "answer":"I couldn't reliably understand that request, so I didn't check or infer any weather advice. Please try a simpler activity and city question.", "trace":state.get("trace", [])+["understand_intent: structured extraction failed validation"]}
    activity = next((key for key, (_, terms) in ACTIVITIES.items() if any(t in text for t in terms)), None)
    known = sessions.get(state["session_id"], {})
    activity = activity or known.get("activity")
    match = re.search(r"\b(?:in|near|around|at)\s+([\w .'-]{2,60}?)(?=\s+(?:today|tomorrow|this|on|during|right|$)|[?.!,]|$)", state["message"], re.I)
    location = match.group(1).strip() if match else known.get("location_text")
    t = next((x for x in ["this evening", "tonight", "tomorrow", "this afternoon", "today", "now"] if x in text), "today")
    if structured:
        activity = known.get("activity") if structured.activity == "unsupported" else structured.activity
        location = structured.location or known.get("location_text")
        t = structured.time_reference
    trace = state.get("trace", []) + ["understand_intent: validated structured extraction" if structured else "understand_intent: conservative local extraction (LLM_PROVIDER not configured)"]
    return {"activity": activity, "location_text": location, "time_reference": t, "trace": trace}

def route_location(state):
    if state.get("status"):
        return "failure"
    if not state.get("activity"):
        return "unsupported"
    if not state.get("location_text"):
        return "missing"
    return "resolve"

async def resolve(state):
    try:
        location = await weather_service.geocode(state["location_text"])
        if not location:
            return {"status": "location_not_found", "answer": f"I couldn't resolve ‘{state['location_text']}’ to a location. Please try a nearby city name.", "trace": state["trace"] + ["resolve_location: no geocoding result"]}
        return {"location": location, "trace": state["trace"] + ["resolve_location: Open-Meteo geocoding succeeded"]}
    except AmbiguousLocation as exc:
        return {"status":"location_ambiguous", "answer":f"I found multiple locations named ‘{state['location_text']}’ in {exc}. Which country should I use?", "trace":state["trace"]+["resolve_location: ambiguous exact-name results"]}
    except UpstreamError:
        return {"status": "weather_unavailable", "answer": "I couldn't reach the location service. Please try again shortly.", "trace": state["trace"] + ["geocoding_api_failed"]}

def route_resolved(state):
    return "failure" if state.get("status") else "fetch"

async def fetch(state):
    try:
        w = await weather_service.forecast(state["location"], state.get("time_reference", "today"))
        return {"weather": w.model_dump(), "trace": state["trace"] + ["fetch_weather: live Open-Meteo forecast retrieved"]}
    except UpstreamError:
        return {"status": "weather_unavailable", "answer": "Live weather data is unavailable right now, so I can't make a weather-based recommendation. Please try again shortly.", "trace": state["trace"] + ["weather_api_failed"]}

def route_weather(state):
    return "failure" if state.get("status") else "policies"

def retrieve(state):
    sops = load_sops()
    subset = [s for s in sops if state["activity"] in s["activities"]]
    return {"candidate_sops": subset, "trace": state["trace"] + [f"retrieve_sops: {len(subset)} activity policies considered"]}

def evaluate(state):
    facts = {**state["weather"], "activity": state["activity"]}
    result = evaluate_policies(state["candidate_sops"], facts)
    return {"policy": result.model_dump(), "trace": state["trace"] + ["evaluate_sops: deterministic rules evaluated"]}

def route_policy(state):
    return "answer" if state["policy"]["outcome"] == "matched" else "no_policy"

def answer(state):
    p, w = state["policy"], state["weather"]
    metrics = []
    if w.get("temperature_2m") is not None: metrics.append(f"temperature {w['temperature_2m']}°C")
    if w.get("wind_speed_10m") is not None: metrics.append(f"wind {w['wind_speed_10m']} km/h")
    if w.get("precipitation_probability") is not None: metrics.append(f"precipitation chance {w['precipitation_probability']}%")
    if w.get("uv_index") is not None: metrics.append(f"UV index {w['uv_index']}")
    guidance = " ".join(p["guidance"])
    forecast_label = "forecast snapshot" if state.get("time_reference") not in {"now", "today"} else "current conditions"
    facts_text = ", ".join(metrics) if metrics else "no displayable measurements were returned"
    source_time = f"Source: {w['source']} · {w['observed_at']} ({w['timezone']})" if w.get("observed_at") else f"Source: {w['source']}"
    text = f"{p['severity']} advisory for {state['activity']} in {state['location'].name}, {state['location'].country}. {guidance} {forecast_label.title()}: {facts_text}. Policy: {p['sop_id']} — {p['title']}. {source_time}."
    # Grounding validation: every claimed weather value and policy citation must originate in state.
    if p["sop_id"] not in {s["id"] for s in state["candidate_sops"]} or not all(str(w[k]) in text for k in ["temperature_2m", "wind_speed_10m"] if w.get(k) is not None) or p["sop_id"] not in text or (w.get("observed_at") and w["observed_at"] not in text):
        return {"status": "validation_failed", "answer": "I couldn't validate the recommendation against the available policy and weather data.", "trace": state["trace"] + ["validate_grounding: failed"]}
    return {"status": "matched", "answer": text, "trace": state["trace"] + ["compose_answer: rendered from weather, policy and citation", "validate_grounding: passed"]}

def ask_location(state):
    return {"status": "needs_location", "answer": "Which city should I check?", "trace": state["trace"] + ["ask_for_location: location missing"]}

def unsupported(state):
    return {"status": "unsupported_activity", "answer": "I can check cycling, running, hiking, walking, picnics, commuting, park visits, or outdoor leisure. What activity do you have in mind?", "trace": state["trace"] + ["intent: unsupported activity"]}

def no_policy(state):
    outcome = state["policy"]["outcome"]
    if outcome == "insufficient_data":
        return {"status": "insufficient_data", "answer": "A weather value required by the applicable policy is missing, so I can't make a recommendation.", "trace": state["trace"] + ["policy: required weather data unavailable"]}
    return {"status": "no_policy", "answer": "I don't have a policy that covers these conditions, so I can't provide a weather-based safety recommendation.", "trace": state["trace"] + ["policy: no SOP matched"]}

g = StateGraph(AdvisoryState)
for name, fn in [("understand_intent", understand), ("resolve_location", resolve), ("fetch_weather", fetch), ("retrieve_sops", retrieve), ("evaluate_sops", evaluate), ("compose_and_validate", answer), ("ask_for_location", ask_location), ("unsupported", unsupported), ("no_policy", no_policy)]: g.add_node(name, fn)
g.add_edge(START, "understand_intent")
g.add_conditional_edges("understand_intent", route_location, {"failure": END, "missing": "ask_for_location", "resolve": "resolve_location", "unsupported": "unsupported"})
g.add_conditional_edges("resolve_location", route_resolved, {"failure": END, "fetch": "fetch_weather"})
g.add_conditional_edges("fetch_weather", route_weather, {"failure": END, "policies": "retrieve_sops"})
g.add_edge("retrieve_sops", "evaluate_sops")
g.add_conditional_edges("evaluate_sops", route_policy, {"answer": "compose_and_validate", "no_policy": "no_policy"})
for n in ["compose_and_validate", "ask_for_location", "unsupported", "no_policy"]: g.add_edge(n, END)
workflow = g.compile()

async def run_advisory(session_id: str, message: str):
    result = await workflow.ainvoke({"session_id": session_id, "message": message, "trace": []})
    if result.get("activity"):
        memory = sessions.setdefault(session_id, {})
        memory["activity"] = result["activity"]
        if result.get("location_text"): memory["location_text"] = result["location_text"]
    return result
