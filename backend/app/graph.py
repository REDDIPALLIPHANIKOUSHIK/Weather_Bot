import re
from typing import TypedDict,Any
from langgraph.graph import StateGraph,START,END
from .services import OpenMeteo,UpstreamError,AmbiguousLocation,load_sops,evaluate_policies
from .models import CurrentLocation,Location
from .llm import extract_intent

class AdvisoryState(TypedDict,total=False):
    session_id:str; message:str; activity:str; category:str; location_text:str|None; current_location:dict[str,Any]|None
    location:Location|None; weather:dict[str,Any]|None; policy:dict[str,Any]|None; candidate_sops:list[dict[str,Any]]
    answer:str; status:str; trace:list[str]; time_reference:str

sessions:dict[str,dict[str,Any]]={}
weather_service=OpenMeteo()
ACTIVITIES={"cycling":("cycling",["cycle","cycling","bike","biking"]),"running":("running",["run","running","jog","jogging"]),"hiking":("hiking",["hike","hiking","trek","trekking"]),"picnic":("picnic",["picnic"]),"pet_walking":("pet walking",["walk the dog","walk my dog","dog walk","pet walk"]),"elderly_outdoor":("elderly outdoor activity",["elderly","senior","older parent"]),"walking":("walking",["walk","walking"]),"commuting":("commuting",["commute","commuting","ride to work"]),"park_visit":("park visit",["park","playground"]),"outdoor_leisure":("outdoor leisure",["outdoor","leisure","garden"])}

async def understand(state:AdvisoryState):
    text=state["message"].lower();known=sessions.get(state["session_id"],{});current=state.get("current_location") or known.get("current_location")
    m=re.search(r"\b(?:in|near|around|at)\s+([\w .'-]{2,60}?)(?=\s+(?:today|tomorrow|this|on|during|right|$)|[?.!,]|$)",state["message"],re.I)
    explicit=m.group(1).strip() if m else None
    try: structured=await extract_intent(state["message"],known)
    except RuntimeError:
        return {"status":"intent_unavailable","answer":"I couldn't reliably understand that request, so I didn't check or infer any weather advice. Please try a simpler activity and city question.","trace":state.get("trace",[])+["understand_intent: structured extraction failed validation"]}
    activity=next((k for k,(_,terms) in ACTIVITIES.items() if any(t in text for t in terms)),None) or known.get("activity")
    location=explicit or (None if current else known.get("location_text"))
    t=next((x for x in ["this evening","tonight","tomorrow","this afternoon","today","now"] if x in text),"today")
    if structured:
        activity=known.get("activity") if structured.activity=="unsupported" else structured.activity
        location=structured.location or (None if current and not explicit else location)
        t=structured.time_reference
    return {"activity":activity,"location_text":location,"current_location":current,"time_reference":t,"trace":state.get("trace",[])+["understand_intent: validated structured extraction" if structured else "understand_intent: conservative local extraction (LLM_PROVIDER not configured)"]}

def route_location(state):
    if state.get("status"): return "failure"
    if not state.get("activity"): return "unsupported"
    if not state.get("location_text") and not state.get("current_location"): return "missing"
    return "resolve"

async def resolve(state:AdvisoryState):
    try:
        if not state.get("location_text") and state.get("current_location"):
            c=CurrentLocation.model_validate(state["current_location"])
            return {"location":Location(name="Your current location",country="",latitude=c.latitude,longitude=c.longitude),"trace":state["trace"]+["resolve_location: browser coordinates accepted"]}
        location=await weather_service.geocode(state["location_text"])
        if not location: return {"status":"location_not_found","answer":f"I couldn't resolve ‘{state['location_text']}’ to a location. Please try a nearby city name.","trace":state["trace"]+["resolve_location: no geocoding result"]}
        return {"location":location,"trace":state["trace"]+["resolve_location: Open-Meteo geocoding succeeded"]}
    except AmbiguousLocation as exc: return {"status":"location_ambiguous","answer":f"I found multiple locations named ‘{state['location_text']}’ in {exc}. Which country should I use?","trace":state["trace"]+["resolve_location: ambiguous exact-name results"]}
    except (UpstreamError,ValueError): return {"status":"weather_unavailable","answer":"I couldn't reach the location service. Please try again shortly.","trace":state["trace"]+["geocoding_api_failed"]}

def route_resolved(state): return "failure" if state.get("status") else "fetch"
async def fetch(state:AdvisoryState):
    try:
        w=await weather_service.forecast(state["location"],state.get("time_reference","today"))
        return {"weather":w.model_dump(),"trace":state["trace"]+["fetch_weather: live Open-Meteo forecast retrieved"]}
    except UpstreamError: return {"status":"weather_unavailable","answer":"Live weather data is unavailable right now, so I can't make a weather-based recommendation. Please try again shortly.","trace":state["trace"]+["weather_api_failed"]}
def route_weather(state): return "failure" if state.get("status") else "policies"
def retrieve(state):
    s=[x for x in load_sops() if state["activity"] in x["activities"]]
    return {"candidate_sops":s,"trace":state["trace"]+[f"retrieve_sops: {len(s)} activity policies considered"]}
def evaluate(state):
    r=evaluate_policies(state["candidate_sops"],{**state["weather"],"activity":state["activity"]})
    return {"policy":r.model_dump(),"trace":state["trace"]+["evaluate_sops: deterministic rules evaluated"]}
def route_policy(state): return "answer" if state["policy"]["outcome"]=="matched" else "no_policy"
def answer(state):
    p,w=state["policy"],state["weather"];parts=[]
    for k,l,s in [("temperature_2m","temperature","°C"),("wind_speed_10m","wind"," km/h"),("precipitation_probability","precipitation chance","%"),("uv_index","UV index","")]:
        if w.get(k) is not None: parts.append(f"{l} {w[k]}{s}")
    label="forecast snapshot" if state.get("time_reference") not in {"now","today"} else "current conditions"; facts=", ".join(parts) or "no displayable measurements were returned"
    loc=state["location"];name=loc.name if not loc.country else f"{loc.name}, {loc.country}";source=f"Source: {w['source']} · {w['observed_at']} ({w['timezone']})"
    text=f"{p['severity']} advisory for {state['activity']} in {name}. {' '.join(p['guidance'])} {label.title()}: {facts}. Policy: {p['sop_id']} — {p['title']}. {source}."
    ok=p["sop_id"] in {s["id"] for s in state["candidate_sops"]} and p["sop_id"] in text and (not w.get("observed_at") or w["observed_at"] in text)
    if not ok:return {"status":"validation_failed","answer":"I couldn't validate the recommendation against the available policy and weather data.","trace":state["trace"]+["validate_grounding: failed"]}
    return {"status":"matched","answer":text,"trace":state["trace"]+["compose_answer: rendered from weather, policy and citation","validate_grounding: passed"]}
def ask_location(state): return {"status":"needs_location","answer":"Which city or location should I check? You can also enable current location.","trace":state["trace"]+["ask_for_location: location missing"]}
def unsupported(state): return {"status":"unsupported_activity","answer":"I can check cycling, running, hiking, walking, picnics, commuting, park visits, or outdoor leisure. What activity do you have in mind?","trace":state["trace"]+["intent: unsupported activity"]}
def no_policy(state):
    if state["policy"]["outcome"]=="insufficient_data": return {"status":"insufficient_data","answer":"A weather value required by the applicable policy is missing, so I can't make a recommendation.","trace":state["trace"]+["policy: required weather data unavailable"]}
    return {"status":"no_policy","answer":"I don't have a policy that covers these conditions, so I can't provide a weather-based safety recommendation.","trace":state["trace"]+["policy: no SOP matched"]}

g=StateGraph(AdvisoryState)
for n,fn in [("understand_intent",understand),("resolve_location",resolve),("fetch_weather",fetch),("retrieve_sops",retrieve),("evaluate_sops",evaluate),("compose_and_validate",answer),("ask_for_location",ask_location),("unsupported",unsupported),("no_policy",no_policy)]:g.add_node(n,fn)
g.add_edge(START,"understand_intent")
g.add_conditional_edges("understand_intent",route_location,{"failure":END,"missing":"ask_for_location","resolve":"resolve_location","unsupported":"unsupported"})
g.add_conditional_edges("resolve_location",route_resolved,{"failure":END,"fetch":"fetch_weather"})
g.add_conditional_edges("fetch_weather",route_weather,{"failure":END,"policies":"retrieve_sops"})
g.add_edge("retrieve_sops","evaluate_sops")
g.add_conditional_edges("evaluate_sops",route_policy,{"answer":"compose_and_validate","no_policy":"no_policy"})
for n in ["compose_and_validate","ask_for_location","unsupported","no_policy"]:g.add_edge(n,END)
workflow=g.compile()

async def run_advisory(session_id:str,message:str,current_location:dict[str,Any]|None=None):
    result=await workflow.ainvoke({"session_id":session_id,"message":message,"current_location":current_location,"trace":[]})
    if result.get("activity"):
        mem=sessions.setdefault(session_id,{})
        mem["activity"]=result["activity"]
        if result.get("location_text"):mem["location_text"]=result["location_text"]
        if result.get("current_location"):mem["current_location"]=result["current_location"]
    return result
