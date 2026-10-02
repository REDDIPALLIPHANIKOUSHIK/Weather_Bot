import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import httpx
from fastapi import APIRouter, HTTPException
from ..models import VoiceSessionRequest, VoiceSessionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

LANGUAGE_CONFIG: dict[str, str] = {
    "en-IN": "English",
    "te-IN": "Telugu (తెలుగు)",
    "hi-IN": "Hindi (हिन्दी)",
    "ta-IN": "Tamil (தமிழ்)",
    "kn-IN": "Kannada (ಕನ್ನಡ)",
    "ml-IN": "Malayalam (മലയാളം)",
    "mr-IN": "Marathi (मराठी)",
    "bn-IN": "Bengali (বাংলা)",
}

VOICE_TOOL = {
    "functionDeclarations": [
        {
            "name": "get_weather_advisory",
            "description": "Query the authoritative Weatherwise weather and written-SOP safety pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "User outdoor activity and weather query.",
                    },
                    "use_current_location": {
                        "type": "boolean",
                        "description": "True if user mentions 'here', 'where I am', or current GPS location.",
                    },
                },
                "required": ["message", "use_current_location"],
            },
        }
    ]
}


def build_system_instruction(lang_code: str) -> str:
    lang_name = LANGUAGE_CONFIG.get(lang_code, "English")
    return (
        f"You are Weatherwise, an expert real-time voice weather-advisory assistant for outdoor activities.\n"
        f"The user has selected the language: {lang_name}.\n"
        f"You MUST converse and respond clearly, naturally, and unmistakably in {lang_name}.\n"
        "AUTHORITY RULES:\n"
        "1. Open-Meteo is authoritative for live weather facts. Weatherwise written SOPs and its deterministic policy engine are authoritative for all safety guidance.\n"
        "2. For EVERY weather or outdoor activity question (cycling, running, hiking, walking, picnics, commuting, etc.), you MUST call the tool 'get_weather_advisory' before giving advice.\n"
        "3. NEVER invent or fabricate weather metrics, forecasts, or safety conclusions. Speak only the facts returned by 'get_weather_advisory'.\n"
        "4. If the user asks about 'here', 'where I am', or current location, pass use_current_location=true in the tool call.\n"
        f"5. Keep spoken voice responses concise, warm, helpful, and natural in {lang_name}."
    )


@router.post("/session", response_model=VoiceSessionResponse)
async def create_voice_session(req: VoiceSessionRequest | None = None):
    requested_lang = req.language if req and req.language in LANGUAGE_CONFIG else "en-IN"
    gemini_key = os.getenv("GEMINI_API_KEY")

    # If Gemini API key is not configured, signal browser fallback gracefully
    if not gemini_key:
        logger.info("GEMINI_API_KEY not configured. Falling back to browser speech.")
        return VoiceSessionResponse(
            mode="fallback",
            language=requested_lang,
            instructions=build_system_instruction(requested_lang),
        )

    model = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.0-flash-exp")
    now = datetime.now(timezone.utc)
    expire_time = (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    new_session_expire = (now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")

    system_instruction = build_system_instruction(requested_lang)

    payload = {
        "uses": 1,
        "expireTime": expire_time,
        "newSessionExpireTime": new_session_expire,
        "liveConnectConstraints": {
            "model": f"models/{model}",
            "config": {
                "responseModalities": ["AUDIO"],
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "tools": [VOICE_TOOL],
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/auth_tokens",
                headers={
                    "x-goog-api-key": gemini_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            token_name = data.get("name")
            if not token_name:
                raise ValueError("Gemini auth_tokens API did not return token name")

            ws_url = (
                "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained"
                f"?access_token={quote(token_name, safe='/')}"
            )
            return VoiceSessionResponse(
                mode="gemini_live",
                model=model,
                ws_url=ws_url,
                language=requested_lang,
                instructions=system_instruction,
            )
    except Exception as err:
        logger.warning("Gemini token provisioning failed: %s. Enabling fallback.", err)
        return VoiceSessionResponse(
            mode="fallback",
            language=requested_lang,
            instructions=system_instruction,
        )
