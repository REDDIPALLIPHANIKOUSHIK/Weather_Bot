import logging
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models import ChatRequest, ChatResponse
from .graph import run_advisory

load_dotenv()
class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "message": record.getMessage()})

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
for handler in logging.getLogger().handlers:
    handler.setFormatter(JsonLogFormatter())
app = FastAPI(title="Weather Advisory Support Bot", version="1.0.0")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

@app.get("/health")
async def health(): return {"status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    state = await run_advisory(request.session_id, request.message.strip())
    return ChatResponse(answer=state["answer"], status=state["status"], location=state.get("location"), weather=state.get("weather"), policy=state.get("policy"), trace=state.get("trace", []))
