# Weatherwise — System Architecture

Weatherwise is an outdoor activity weather-advisory platform designed to evaluate safety queries (such as *"Is it safe to cycle in Bhopal today?"* or *"Can I walk here now?"*) deterministically against live Open-Meteo weather observations and written Standard Operating Procedure (SOP) policies.

---

## 1. Core Architectural Principle

> **The language model never decides whether an outdoor activity is safe.**

The AI layer serves strictly for:
1. Understanding natural language intent and extracting activity/time/location context.
2. Low-latency real-time voice streaming with multilingual interaction.

All safety decisions, severity ratings, guidance recommendations, and comfort evaluations are computed **deterministically** by evaluating written SOP rules against live, verified meteorological data from Open-Meteo.

---

## 2. End-to-End Request Pipeline

```
                     ┌───────────────────────────┐
                     │           USER            │
                     │    Text or Live Voice     │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │   Intent Classification   │
                     │  Gemini Structured API /  │
                     │ Resilient Local Extractor │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │    Location Resolution    │
                     │   Precedence Evaluation   │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │    Open-Meteo Weather     │
                     │  Current / Forecast Feed  │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │   SOP Candidate Matcher   │
                     │  Activity Filter (sops)   │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │ Deterministic Policy Eval │
                     │  Conditions, Severities,  │
                     │   and Priority Weights    │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │ Grounded Response Builder │
                     │ Fact & Citation Synthesis │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │ UI Card & Spoken Audio    │
                     │ Metrics, Guidance & Trace │
                     └───────────────────────────┘
```

---

## 3. Location Resolution Precedence

When answering a user request, location resolution strictly follows this hierarchy:

1. **Explicit City or Place in Query** (e.g. *"in Bhopal"*, *"at Pune"*, *"for Jaipur"*):
   - Resolves through Open-Meteo Geocoding API (`https://geocoding-api.open-meteo.com/v1/search`).
   - Normalizes Indic script names (e.g., `"భోపాల్"` -> `"Bhopal"`, `"भोपाल"` -> `"Bhopal"`).
   - Detects ambiguous locations across countries.
2. **Current-Location Intent** (e.g. *"here"*, *"where I am"*, *"ఇక్కడ"*, *"यहाँ"*):
   - Uses real browser GPS coordinates from `navigator.geolocation`.
   - If coordinates are unavailable, prompts user to allow location permission or enter a city.
3. **Session Memory**:
   - If an elliptical follow-up is asked (e.g., *"What about this evening?"*), the active session location is preserved.
4. **Missing Location Fallback**:
   - Responds with `status: "needs_location"` and guides the user cleanly without guessing or hallucinating coordinates.

---

## 4. Deterministic SOP Policy Engine

SOPs are defined in machine-readable YAML (`backend/config/sops.yaml`). Each SOP defines:

- `id`: Unique policy identifier (e.g. `WB-001`)
- `title`: Human-readable policy name
- `category`: Category domain (`outdoor_exercise`, `travel`, `vulnerable_groups`, `leisure`)
- `activities`: Array of targeted activities
- `severity`: Rating tier (`CRITICAL`, `HIGH`, `MODERATE`, `LOW`)
- `priority`: Integer priority weight (1 to 100)
- `conditions`: Condition expression tree supporting `field`, `operator` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`), combined via `all`, `any`, and `not`.
- `guidance`: Prescribed safety guidance strings.

### Conflict Resolution
When multiple candidate policies evaluate to `True`, the engine selects the winner by:
1. **Severity Weight**: `CRITICAL` (4) > `HIGH` (3) > `MODERATE` (2) > `LOW` (1).
2. **Priority Weight**: Highest integer priority breaks ties.

---

## 5. Gemini Live Voice Architecture & Security

### Security Boundary
- The permanent `GEMINI_API_KEY` remains strictly server-side.
- The browser calls `POST /api/voice/session` to obtain a short-lived ephemeral session token from Google's `v1beta/auth_tokens` endpoint.
- The client connects directly to Gemini Live via WebSocket (`wss://generativelanguage.googleapis.com/...`).

### Tool Calling Execution
1. The browser streams raw 16kHz linear PCM microphone audio.
2. Gemini detects outdoor activity questions and invokes the declared tool: `get_weather_advisory(message, use_current_location)`.
3. The browser executes this tool by querying the local `/api/chat` REST endpoint with real coordinates.
4. The structured output is returned to Gemini Live.
5. Gemini generates low-latency audio response in the user's selected language.

### Multilingual Support & Fallback
- 8 supported languages: English, Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali.
- If Gemini Live credentials are not configured or connection drops, the engine automatically switches to the browser Web Speech API (`SpeechRecognition` + `SpeechSynthesis`).
