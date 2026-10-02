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
        "standard_prefix": "{loc}లో {act} కోసం ప్రస్తుత పరిస్థితుల్లో వర్తించే Weatherwise SOP నిబంధనలు ఏవీ లేవు, కాబట్టి విధాన-ఆధారిత భద్రతా సిఫార్సు అందించబడదు.",
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
        "standard_prefix": "वर्तमान परिस्थितियों में {loc} में {act} के लिए कोई लागू Weatherwise SOP नियम नहीं है, इसलिए कोई नीति-आधारित सुरक्षा अनुशंसा प्रदान नहीं की जा सकती।",
        "advisory_prefix": "[{sev} चेतावनी] {loc} में {act}।",
        "policy_label": "सुरक्षा नीति",
    },
    "ta-IN": {
        "unsupported": (
            "சைக்கிள் ஓட்டுதல், ஓடுதல், நடைபயிற்சி, பிக்னிக், அல்லது பூங்கா வருகைகளுக்கான வானிலை "
            "பாதுகாப்பு ஆலோசனைகளை என்னால் மதிப்பீடு செய்ய முடியும். எந்தச் செயல்பாட்டைச் சரிபார்க்க விரும்புகிறீர்கள்?"
        ),
        "needs_location": "வானிலையைச் சரிபார்க்க, தயவுசெய்து இருப்பிட அனுமதியை வழங்கவும் அல்லது நகரத்தின் பெயரை உள்ளிடவும்.",
        "standard_prefix": "தற்போதைய வானிலை நிலைமைகளில் {loc} இல் {act} க்குப் பொருந்தக்கூடிய Weatherwise SOP விதிகள் எதுவும் இல்லை, எனவே கொள்கை அடிப்படையிலான பாதுகாப்பு பரிந்துரையை வழங்க முடியாது.",
        "advisory_prefix": "[{sev} எச்சரிக்கை] {loc} இல் {act}.",
        "policy_label": "பாதுகாப்புக் கொள்கை",
    },
    "kn-IN": {
        "unsupported": "ಸೈಕ್ಲಿಂಗ್, ಓಟ, ವಾಕಿಂಗ್, ಪಿಕ್ನಿಕ್, ಅಥವಾ ಪಾರ್ಕ್ ಭೇಟಿಗಳ ಸುರಕ್ಷತಾ ಸಲಹೆಗಳನ್ನು ನಾನು ನೀಡಬಲ್ಲೆ. ನೀವು ಯಾವ ಚಟುವಟಿಕೆಯನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?",
        "needs_location": "ಹವಾಮಾನವನ್ನು ಪರೀಕ್ಷಿಸಲು, ದಯವಿಟ್ಟು ಸ್ಥಳ ಪ್ರವೇಶವನ್ನು ಅನುಮತಿಸಿ ಅಥವಾ ನಗರದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ.",
        "standard_prefix": "ಪ್ರಸ್ತುತ ಹವಾಮಾನ ಪರಿಸ್ಥಿತಿಗಳಲ್ಲಿ {loc} ನಲ್ಲಿ {act} ಗೆ ಅನ್ವಯವಾಗುವ ಯಾವುದೇ Weatherwise SOP ನಿಯಮಗಳಿಲ್ಲ, ಆದ್ದರಿಂದ ನೀತಿ-ಆಧಾರಿತ ಸುರಕ್ಷತಾ ಶಿಫಾರಸನ್ನು ನೀಡಲಾಗುವುದಿಲ್ಲ.",
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
        """Execute through production compiled LangGraph workflow."""
        from ..graph import run_advisory_graph
        return await run_advisory_graph(
            session_id=session_id,
            message=message,
            current_location=current_location,
            language=language,
            weather_service=self.weather_service,
        )
