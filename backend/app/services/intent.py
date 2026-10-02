import json
import logging
import os
import re
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SUPPORTED_ACTIVITIES = {
    "cycling": (
        "outdoor_exercise",
        [
            "cycling", "cycle", "bicycle", "bike", "biking", "riding a bike",
            # Indic
            "సైకిల్", "సైక్లింగ్", "సైకిలింగ్",
            "साइकिल", "साइकिलिंग", "सायकल",
            "சைக்கிள்", "சைக்கிளிங்",
            "ಸೈಕ್ಲಿಂಗ್", "ಸೈಕಲ್",
            "സൈക്ലിംഗ്", "സൈക്കിൾ",
            "সাইকেল", "সাইক্লিং",
        ],
    ),
    "running": (
        "outdoor_exercise",
        [
            "running", "run", "jogging", "jog", "sprint",
            # Indic
            "పరుగు", "రన్నింగ్", "జాగింగ్",
            "दौड़", "दौड़ना", "रनिंग", "जॉगिंग",
            "ஓட்டம்", "ரன்னிங்",
            "ಓಟ", "ರನ್ನಿಂಗ್",
            "ഓട്ടം", "റണ്ണിംഗ്",
            "দৌড়", "রানিং",
        ],
    ),
    "hiking": (
        "outdoor_exercise",
        [
            "hiking", "hike", "trekking", "trek", "trail",
            # Indic
            "హైకింగ్", "ట్రెక్కింగ్",
            "हाइकिंग", "ट्रेकिंग",
            "ஹைக்கிங்", "ட்ரெக்கிங்",
            "ಹೈಕಿಂಗ್", "ಟ್ರೆಕ್ಕಿಂಗ್",
            "ഹൈക്കിംഗ്", "ട്രെക്കിംഗ്",
            "হাইকিং", "ট্রেকিং",
        ],
    ),
    "walking": (
        "vulnerable_groups",
        [
            "walking", "walk", "stroll", "going for a walk",
            # Indic
            "నడవడం", "నడక", "వాకింగ్",
            "टहलना", "घूमना", "वॉकिंग", "सैर",
            "நடப்பது", "நடைபயிற்சி", "வாக்கிங்",
            "ನಡೆಯುವುದು", "ವಾಕಿಂಗ್",
            "നടത്തം", "വാക്കിംഗ്",
            "হাঁটা", "ওয়াকিং",
        ],
    ),
    "pet_walking": (
        "leisure",
        [
            "pet walking", "dog walking", "walk my dog", "walk the dog", "pet walk", "dog walk", "walking the dog",
            # Indic
            "కుక్కను నడపడం", "పెట్ వాకింగ్",
            "कुत्ते को टहलाना", "पेट वॉकिंग",
        ],
    ),
    "elderly_outdoor": (
        "vulnerable_groups",
        [
            "elderly", "senior", "older adult", "grandparents", "aged person",
            # Indic
            "వృద్ధులు", "పెద్దవారు",
            "बुजुर्ग", "वरिष्ठ नागरिक",
            "முதியவர்கள்",
            "ಹಿರಿಯರು",
            "മുതിർന്നവർ",
            "বয়স্ক",
        ],
    ),
    "picnic": (
        "leisure",
        [
            "picnic", "picnicking", "outdoor meal",
            # Indic
            "పిక్నిక్",
            "पिकनिक",
            "பிக்னிக்",
            "ಪಿಕ್ನಿಕ್",
            "പിക്നിക്",
            "পিকনিক",
        ],
    ),
    "commuting": (
        "travel",
        [
            "commuting", "commute", "travel to work", "office commute", "ride to work",
            # Indic
            "ప్రయాణం", "ఆఫీస్ ప్రయాణం",
            "आवागमन", "यात्रा", "कम्यूट",
        ],
    ),
    "park_visit": (
        "vulnerable_groups",
        [
            "park visit", "children's park", "kids park", "playground", "taking child to park", "take child to the park", "park",
            # Indic
            "పార్కు", "పార్క్", "పిల్లల పార్క్",
            "पार्क", "उद्यान", "बच्चों का पार्क",
            "பூங்கா", "பார்க்",
            "ಪಾರ್ಕ್", "ಉದ್ಯಾನ",
            "പാർക്ക്",
            "পার্ক",
        ],
    ),
    "outdoor_leisure": (
        "leisure",
        [
            "outdoor leisure", "relaxing outside", "sit outside", "leisure", "outdoor relaxation",
            # Indic
            "విశ్రాంతి", "బయట కూర్చోవడం",
            "विश्राम", "बाहर बैठना",
        ],
    ),
}

ACTIVITY_BY_KEYWORD: dict[str, str] = {}
for act, (_, terms) in SUPPORTED_ACTIVITIES.items():
    for term in terms:
        ACTIVITY_BY_KEYWORD[term] = act

# Multilingual current location triggers
CURRENT_LOCATION_PATTERNS = [
    r"\bhere\b",
    r"\bwhere i am\b",
    r"\bcurrent location\b",
    r"\bmy location\b",
    r"\baround here\b",
    r"\bnearby\b",
    # Indic words for 'here'
    "ఇక్కడ",  # Telugu
    "यहाँ", "यहाँ पे", "इधर",  # Hindi
    "இங்கு", "இங்கே",  # Tamil
    "ಇಲ್ಲಿ",  # Kannada
    "ഇവിടെ",  # Malayalam
    "येथे", "इथे",  # Marathi
    "এখানে",  # Bengali
]

TIME_PATTERNS = [
    ("this afternoon", ["this afternoon", "afternoon", "ఈ మధ్యాహ్నం", "दोपहर"]),
    ("this evening", ["this evening", "evening", "ఈ సాయంత్రం", "शाम"]),
    ("tonight", ["tonight", "night", "ఈ రాత్రి", "रात"]),
    ("tomorrow", ["tomorrow", "రేపు", "कल"]),
    ("now", ["right now", "now", "currently", "ఇప్పుడు", "अभी"]),
    ("today", ["today", "this morning", "morning", "ఈరోజు", "आज"]),
]


class ExtractedIntent(BaseModel):
    activity: str | None = None
    category: str | None = None
    location_text: str | None = None
    use_current_location: bool = False
    time_reference: str = "today"
    confidence: float = 1.0
    extraction_source: str = "rule_based"


def parse_intent_locally(message: str, session_context: dict[str, Any] | None = None) -> ExtractedIntent:
    lowered = message.lower()
    session_ctx = session_context or {}

    # 1. Detect current location intent
    use_curr = False
    for pat in CURRENT_LOCATION_PATTERNS:
        if pat.startswith(r"\b"):
            if re.search(pat, lowered, re.IGNORECASE):
                use_curr = True
                break
        else:
            if pat in message:
                use_curr = True
                break

    # 2. Extract explicit city/location
    explicit_location: str | None = None
    loc_match = re.search(
        r"\b(?:in|at|near|around|for)\s+([A-Za-z\s.'-]{2,40}?)(?=\s+(?:today|tomorrow|this|now|tonight|right|morning|afternoon|evening|$)|[?.!,]|$)",
        message,
        re.IGNORECASE,
    )
    if loc_match:
        cand = loc_match.group(1).strip()
        if cand.lower() not in {"today", "tomorrow", "cycling", "running", "hiking", "picnic", "a walk", "the park"}:
            explicit_location = cand

    # Check for direct Indic city mention in text if no explicit english match
    if not explicit_location:
        from .weather import INDIC_CITY_MAP
        for indic_name in INDIC_CITY_MAP:
            if indic_name in message:
                explicit_location = indic_name
                break

    # 3. Extract Activity
    detected_act: str | None = None
    sorted_keywords = sorted(ACTIVITY_BY_KEYWORD.keys(), key=lambda k: len(k), reverse=True)
    for kw in sorted_keywords:
        if kw.isascii() and re.match(r"^\w", kw):
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lowered):
                detected_act = ACTIVITY_BY_KEYWORD[kw]
                break
        else:
            # Indic or non-word script
            if kw in message:
                detected_act = ACTIVITY_BY_KEYWORD[kw]
                break

    # 4. Extract Time reference
    detected_time = "today"
    for standard_time, triggers in TIME_PATTERNS:
        matched = False
        for trig in triggers:
            if trig.isascii():
                if re.search(r"\b" + re.escape(trig) + r"\b", lowered):
                    detected_time = standard_time
                    matched = True
                    break
            else:
                if trig in message:
                    detected_time = standard_time
                    matched = True
                    break
        if matched:
            break

    # 5. Integrate session context for follow-ups
    final_act = detected_act or session_ctx.get("activity")
    final_loc = explicit_location
    if not final_loc and not use_curr:
        final_loc = session_ctx.get("location_text")

    category = None
    if final_act and final_act in SUPPORTED_ACTIVITIES:
        category = SUPPORTED_ACTIVITIES[final_act][0]

    return ExtractedIntent(
        activity=final_act,
        category=category,
        location_text=final_loc,
        use_current_location=use_curr,
        time_reference=detected_time,
        confidence=0.9,
        extraction_source="rule_based",
    )


async def extract_intent(
    message: str,
    session_context: dict[str, Any] | None = None,
) -> ExtractedIntent:
    """Extract intent with LLM when available; fallback immediately to local parsing on failure/absence."""
    local_result = parse_intent_locally(message, session_context)

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return local_result

    try:
        model_name = os.getenv("GEMINI_INTENT_MODEL", "gemini-2.0-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        
        prompt = (
            f"Analyze this outdoor weather advisory query: '{message}'\n"
            f"Prior context: {json.dumps(session_context or {})}\n\n"
            "Return JSON matching this schema:\n"
            "{\n"
            '  "activity": "cycling"|"running"|"hiking"|"walking"|"pet_walking"|"elderly_outdoor"|"picnic"|"commuting"|"park_visit"|"outdoor_leisure"|"unsupported",\n'
            '  "location": string or null,\n'
            '  "use_current_location": boolean (true if user asked about here/current location/GPS),\n'
            '  "time_reference": "now"|"today"|"this afternoon"|"this evening"|"tonight"|"tomorrow"\n'
            "}\n"
            "Do NOT evaluate safety or make weather claims. Return strictly JSON."
        )

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            }
        }

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(url, json=body)
            if resp.status_code == 200:
                data = resp.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)

                act = parsed.get("activity")
                if act == "unsupported":
                    act = None
                elif act not in SUPPORTED_ACTIVITIES:
                    act = local_result.activity

                loc = parsed.get("location") or local_result.location_text
                use_curr = parsed.get("use_current_location", local_result.use_current_location)
                time_ref = parsed.get("time_reference", local_result.time_reference)

                cat = SUPPORTED_ACTIVITIES[act][0] if act in SUPPORTED_ACTIVITIES else None

                return ExtractedIntent(
                    activity=act,
                    category=cat,
                    location_text=loc,
                    use_current_location=use_curr,
                    time_reference=time_ref,
                    confidence=0.98,
                    extraction_source="gemini_structured",
                )
    except Exception as err:
        logger.debug("Gemini intent extraction failed, relying on local parser: %s", err)

    return local_result
