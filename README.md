# Weatherwise — Weather-Advisory Support Bot

A small FastAPI + LangGraph + Next.js application that pairs live Open-Meteo forecasts with editable written SOPs. The deterministic SOP evaluator makes the recommendation; natural-language parsing does not decide whether an activity is safe.

## Local setup

Requirements: Python 3.11+, Node.js 20.9+, and internet access for live geocoding and forecasts. No weather API key is needed. Optional `OPENAI_API_KEY` enables provider-based structured intent extraction; without it, bounded local extraction is used.

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Backend health: http://localhost:8000/health. Copy `.env.example` to the backend `.env` to configure `CORS_ORIGINS` and optional LLM settings, and to `frontend/.env.local` for `NEXT_PUBLIC_API_URL`. Set backend CORS to the deployed frontend origins.

## Checks

```powershell
python -m pytest -q
python evals/run.py
cd frontend
npm run build
```

## Adding a policy

Append a uniquely identified entry to `config/sops.yaml`, including category, supported activities, severity, priority, a boolean condition, and guidance. The graph and engine do not need edits. Restart the API to reload configuration. Supported operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, and `contains`; conditions support nested `all`, `any`, and `not`.

## API

`POST /api/chat` accepts `{ "session_id": "…", "message": "…" }`. Responses include `status`, `answer`, location, selected weather facts, policy/citation where applicable, and graph trace. Use the same session ID for follow-up questions. Memory is in-process and ephemeral.

## Deployment

Deploy the `backend` directory as a Python 3.11 web service with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; set `PYTHONPATH` to the backend working directory. Deploy `frontend` to a Next.js host and configure `NEXT_PUBLIC_API_URL` as a build-time environment variable. Configure backend CORS for that frontend origin. No credentials are required for Open-Meteo.

See [architecture](docs/architecture.md), [engineering decisions](docs/decisions.md), and [evaluation notes](docs/evaluation.md).

## Scope and limitations

This is an interview take-home prototype, not a certified safety service. Policy thresholds are illustrative and need domain-owner review. It supports a small English activity vocabulary. Session context is lost on restart and is not shared across backend workers. Forecast hour selection is a snapshot, and live weather varies.
