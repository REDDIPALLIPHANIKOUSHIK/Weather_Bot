from fastapi.testclient import TestClient
from app.main import app

def test_voice_requires_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    assert TestClient(app).post("/api/voice/session").status_code==503
