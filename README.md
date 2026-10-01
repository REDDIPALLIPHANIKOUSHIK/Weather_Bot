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

## Vercel deployment

This repository uses Vercel Services to build `frontend/` (Next.js) and `backend/` (FastAPI) as one project and serve them from one domain. The root `vercel.json` sends `/api/*` and `/health` to FastAPI and all other paths to Next.js. The backend entrypoint is `app.main:app`; its dependencies are detected from `backend/requirements.txt` and its Python version from `backend/.python-version`.

Before deploying, connect the Git repository or run `vercel link` from the repository root. In Vercel Project Settings, set the framework preset to **Services** (Vercel Services is currently Beta). Then deploy from this repository root with `vercel deploy --prod`. Do not set a service-specific root directory in project settings; the root `vercel.json` defines both service roots.

Set `OPENAI_API_KEY` in the Vercel project environment variables if you want structured intent extraction. For an OpenAI-compatible provider, also set `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, and optionally `LLM_MODEL`. These are backend runtime variables; do not use `NEXT_PUBLIC_` names. Open-Meteo needs no key. `CORS_ORIGINS` is only needed for separate browser origins; calls from the bundled frontend use the same domain and do not need CORS.

Locally, copy `.env.example` to `frontend/.env.local` for `NEXT_PUBLIC_API_URL=http://localhost:8000`, and to `backend/.env` for `CORS_ORIGINS=http://localhost:3000` plus optional LLM settings. In production, leave `NEXT_PUBLIC_API_URL` unset so the frontend calls `/api/chat` on its own origin and Vercel routes it to FastAPI. If deploying the frontend separately, set `NEXT_PUBLIC_API_URL` to the backend's public base URL and allow that frontend origin with `CORS_ORIGINS`.

The canonical SOP file remains `config/sops.yaml`; `backend/config/sops.yaml` is its service-root deployment copy because Vercel builds each service independently. Keep the two copies in sync when editing policies. The loader resolves paths relative to its Python module and does not depend on the process working directory.

Session context is stored in process memory and the browser session ID is held in `sessionStorage`. On Vercel, serverless instances can be recycled or scaled independently, so follow-up context may not survive across requests. Durable cross-instance sessions require an external store, which this project does not currently configure.

See [architecture](docs/architecture.md), [engineering decisions](docs/decisions.md), and [evaluation notes](docs/evaluation.md).

## Scope and limitations

This is an interview take-home prototype, not a certified safety service. Policy thresholds are illustrative and need domain-owner review. It supports a small English activity vocabulary. Session context is lost on restart and is not shared across backend workers. Forecast hour selection is a snapshot, and live weather varies.
