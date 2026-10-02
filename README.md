# Weatherwise — Outdoor Activity Weather Advisory Bot

**Weatherwise** is a production-grade weather-advisory platform designed to answer safety questions for outdoor activities—such as *"Is it safe to cycle in Bhopal today?"*, *"Should I take my child to the park in Pune this afternoon?"*, or *"Can I go for a walk here now?"*.

Rather than allowing a language model to hallucinate or guess safety conclusions, Weatherwise pairs live meteorological data from **Open-Meteo** with a **deterministic Standard Operating Procedure (SOP) policy engine**. The application extracts user intent, resolves location precedence, validates live conditions, evaluates written safety rules, and generates grounded recommendations accompanied by a complete engineering trace and real-time voice synthesis.

---

## Key Features

- **Grounded Outdoor Safety Advisories**: Covers 10 distinct activities across exercise, vulnerable populations, travel, and leisure:
  - *Cycling*, *Running*, *Hiking*, *Walking*, *Pet Walking*, *Elderly Outdoor*, *Commuting*, *Park Visits (Children)*, *Picnics*, and *Outdoor Leisure*.
- **Zero Hallucinated Safety Decisions**: Language models never decide safety. All thresholds, severity tags (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`), and recommendations originate deterministically from verified SOP rules evaluated against live weather metrics.
- **Live Open-Meteo Integration**: Real-time current conditions and hourly forecasts: temperature, wind speed, precipitation, rain probability, UV index, and weather codes.
- **Real Browser Geolocation**: High-accuracy `navigator.geolocation` integration with permission handling, status indicators, and retry support for questions about "here" or "current location".
- **Strict Location Precedence**:
  1. Explicit city in user prompt (e.g., *"in Bhopal"*)
  2. Live GPS coordinates when the user asks about *"here"* or *"where I am"*
  3. Session memory for elliptical follow-ups (e.g., *"What about this evening?"*)
  4. Honest clarification prompt if no location is available
- **Real-Time Gemini Live Voice**: Bidirectional voice interaction using Google's low-latency Gemini Live API over WebSocket with client-side audio streaming (16kHz PCM capture and 24kHz PCM playback).
- **Server-Side Security Boundary**: The permanent Gemini API key never touches the browser. Ephemeral credentials with strict tool calling constraints are generated via `POST /api/voice/session`.
- **8-Language Multilingual Support**: English, Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, and Bengali for both text queries, voice recognition, and spoken replies.
- **Resilient Fallback Mode**: If Gemini Live is unconfigured or unavailable, the system automatically falls back to browser Web Speech API (`SpeechRecognition` + `SpeechSynthesis`) without breaking user workflows.
- **Explainable Engineering Trace**: Collapsible trace detailing intent classification, coordinate resolution, weather metrics, candidate SOP evaluations, and grounding validation.
- **Monorepo Vercel Deployment**: Configured for Vercel Services uniting a Next.js frontend with a FastAPI backend.

---

## Technology Stack

### Frontend
- **Framework**: Next.js 15+ (App Router)
- **Library**: React 19, TypeScript
- **Styling**: Tailwind CSS v4 (Glassmorphism, dark palette, responsive design)
- **Icons**: Lucide React
- **Audio Processing**: Web Audio API (`AudioContext`, `ScriptProcessorNode`, PCM ArrayBuffer streaming)
- **Geolocation**: Browser `navigator.geolocation` API

### Backend
- **Framework**: Python 3.12+, FastAPI
- **Data Validation & Schemas**: Pydantic v2
- **HTTP Client**: `httpx` (asynchronous networking with retries and timeout controls)
- **Policy Definition**: PyYAML (machine-readable rule definitions in `config/sops.yaml`)
- **Testing**: `pytest`, `pytest-asyncio`

### Meteorological & AI Services
- **Weather Provider**: Open-Meteo Forecast API & Open-Meteo Geocoding API
- **Voice Engine**: Gemini Live WebSocket API (`BidiGenerateContentConstrained`) with tool calling (`get_weather_advisory`)
- **Intent Extraction**: Gemini structured JSON schema extraction with local multilingual regex fallback

---

## Architecture & Request Flow

```
┌────────────────────────────────────────────────────────┐
│                   User (Text / Voice)                  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Intent Understanding Layer               │
│  - Activity (cycling, walking, picnic, etc.)           │
│  - Location (explicit city, Indic script, or 'here')   │
│  - Time Reference (now, today, evening, tomorrow)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Location Precedence Resolution             │
│  Explicit City  ──►  Open-Meteo Geocoding              │
│  'Here' Intent  ──►  Live Browser Coordinates (GPS)    │
│  Follow-Up      ──►  Ephemeral Session Memory          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                Live Weather Retrieval                  │
│  Open-Meteo Forecast API (Current + Hourly Snapshot)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           Deterministic SOP Policy Engine              │
│  1. Retrieve applicable SOPs for activity              │
│  2. Validate required weather fields                   │
│  3. Evaluate conditions (eq, gt, gte, lt, lte, in)     │
│  4. Resolve conflicts by severity and priority weights │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              Grounded Response Synthesis               │
│  Facts + Severity Badge + Guidance + Trace + Citation  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Frontend Display & Audio Playback        │
└────────────────────────────────────────────────────────┘
```

---

## Deterministic SOP Policy Engine

Safety rules reside in `config/sops.yaml`. Each policy is validated on startup into typed Pydantic models:

```yaml
- id: WB-001
  title: Crosswinds During Cycling
  category: outdoor_exercise
  activities: [cycling]
  severity: HIGH
  priority: 90
  conditions:
    field: wind_speed_10m
    operator: gte
    value: 40
  guidance:
    - "Strong winds can make a bicycle difficult to control; postpone the ride until conditions ease."
```

### Supported Condition Operators
- **Scalar**: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`
- **Composite**: `all`, `any`, `not`

### Priority Resolution
If multiple conditions match (e.g. Extreme Heat `WB-005` [CRITICAL] and Wet Conditions `WB-002` [MODERATE] for running), the engine deterministically selects the highest severity tier (`CRITICAL` > `HIGH` > `MODERATE` > `LOW`), using priority integer weights (1–100) to break ties.

---

## Gemini Live Voice & Security

1. **Client-Server Boundary**: The browser never receives permanent API keys.
2. **Ephemeral Session Tokens**: The backend communicates with `https://generativelanguage.googleapis.com/v1beta/auth_tokens` to create a 30-minute scoped token locked to the `models/gemini-2.0-flash-exp` model and the `get_weather_advisory` tool schema.
3. **Direct WebSocket**: The browser connects to `wss://generativelanguage.googleapis.com/ws/...` using the ephemeral token.
4. **Tool Execution**: When the user speaks an outdoor question, Gemini invokes `get_weather_advisory`. The client queries `/api/chat` with current GPS coordinates and feeds the grounded result back into the WebSocket.
5. **Instant Interruption**: Speaking while the assistant is talking automatically cancels queued audio buffers and returns the UI to a listening state.

---

## Multilingual Support

Weatherwise provides full end-to-end support for 8 languages:

| Language | Code | Native Name | Script Support |
| :--- | :--- | :--- | :--- |
| **English** | `en-IN` | English | Latin |
| **Telugu** | `te-IN` | తెలుగు | Telugu script & transliteration |
| **Hindi** | `hi-IN` | हिन्दी | Devanagari |
| **Tamil** | `ta-IN` | தமிழ் | Tamil script |
| **Kannada** | `kn-IN` | ಕನ್ನಡ | Kannada script |
| **Malayalam** | `ml-IN` | മലയാളം | Malayalam script |
| **Marathi** | `mr-IN` | मराठी | Devanagari |
| **Bengali** | `bn-IN` | বাংলা | Bengali script |

The core policy engine remains language-independent; localization occurs seamlessly at the interaction and speech layer.

---

## REST API Specification

### `GET /health`
Returns system health and service status.

**Response**:
```json
{
  "status": "ok",
  "service": "Weatherwise",
  "version": "1.0.0"
}
```

---

### `POST /api/chat`
Processes an outdoor activity query.

**Request**:
```json
{
  "session_id": "session_abc123",
  "message": "Is it safe to cycle in Bhopal today?",
  "current_location": {
    "latitude": 23.2599,
    "longitude": 77.4126,
    "accuracy": 15.0
  }
}
```

**Response**:
```json
{
  "answer": "[HIGH ADVISORY] Cycling in Bhopal, India. Strong winds can make a bicycle difficult to control; postpone the ride until conditions ease. Current conditions: 28.5°C, winds 42.0 km/h, 10% rain probability. Policy: WB-001 - Crosswinds During Cycling. Source: Open-Meteo at 2026-10-02T14:00 (Asia/Kolkata).",
  "status": "matched",
  "location": {
    "name": "Bhopal",
    "country": "India",
    "latitude": 23.2599,
    "longitude": 77.4126
  },
  "weather": {
    "temperature_2m": 28.5,
    "wind_speed_10m": 42.0,
    "precipitation": 0.0,
    "precipitation_probability": 10,
    "uv_index": 5.4,
    "weather_code": 1,
    "observed_at": "2026-10-02T14:00",
    "timezone": "Asia/Kolkata",
    "source": "Open-Meteo"
  },
  "policy": {
    "outcome": "matched",
    "sop_id": "WB-001",
    "title": "Crosswinds During Cycling",
    "severity": "HIGH",
    "priority": 90,
    "guidance": ["Strong winds can make a bicycle difficult to control; postpone the ride until conditions ease."],
    "trace": [...]
  },
  "trace": [
    "Advisory started for session 'session_abc123'",
    "Intent extracted via rule_based: activity='cycling', location='Bhopal', use_curr=False, time='today'",
    "Geocoded 'Bhopal' -> Bhopal, India",
    "Retrieved live Open-Meteo weather for Bhopal",
    "Found 3 applicable SOP definitions for 'cycling'",
    "Policy evaluation outcome: matched (matched: WB-001)",
    "Grounded answer generated successfully"
  ]
}
```

---

### `POST /api/voice/session`
Mints short-lived ephemeral session credentials for Gemini Live WebSocket connections.

**Request**:
```json
{
  "language": "te-IN"
}
```

**Response (when configured)**:
```json
{
  "mode": "gemini_live",
  "model": "gemini-2.0-flash-exp",
  "ws_url": "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token=...",
  "language": "te-IN",
  "instructions": "..."
}
```

*(When `GEMINI_API_KEY` is omitted, the API responds with `mode: "fallback"` to activate browser Web Speech safely).*

---

## Local Development Setup

### 1. Prerequisites
- **Node.js**: v18+ (tested on v24)
- **Python**: 3.11+ (tested on 3.12)

### 2. Backend Setup
```bash
# Navigate to repository root
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend service
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# In a separate terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Automated Test Suite

Run the complete backend test suite:

```bash
# From repository root
pytest -v
```

The automated tests validate:
- Health check endpoints (`/health`)
- End-to-end explicit city queries
- Live GPS coordinate handling
- Missing/denied location fallbacks
- Unsupported activity detection
- Deterministic condition trees & operator logic
- Conflict resolution (highest severity & priority selection)
- Missing weather field detection (`insufficient_data`)
- Prompt injection resistance
- Upstream Open-Meteo failure handling
- Multi-turn session context preservation
- Voice session token provisioning and fallback
- Multilingual voice configurations for all 8 supported languages

To run frontend checks:
```bash
cd frontend
npm run build
```

---

## Vercel Deployment

The repository is configured for monorepo deployment using Vercel Services via `vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "frontend": {
      "root": "frontend/",
      "framework": "nextjs"
    },
    "backend": {
      "root": "backend/",
      "framework": "fastapi",
      "entrypoint": "main:app"
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/health", "destination": { "service": "backend" } },
    { "source": "/(.*)", "destination": { "service": "frontend" } }
  ]
}
```

Environment variables to configure on Vercel:
- `GEMINI_API_KEY`: Google Gemini API key (server-side only)
- `GEMINI_LIVE_MODEL`: Optional override for live voice model (defaults to `gemini-2.0-flash-exp`)
- `CORS_ORIGINS`: Allowed origins (e.g., `*` or your production domain)

---

## License

MIT License. Designed and engineered for production reliability.
