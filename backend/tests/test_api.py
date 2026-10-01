from fastapi.testclient import TestClient
from app.main import app

def test_health():
    assert TestClient(app).get("/health").json() == {"status":"ok"}

def test_chat_rejects_oversized_input():
    response = TestClient(app).post("/api/chat", json={"session_id":"s1", "message":"x"*1001})
    assert response.status_code == 422

def test_chat_rejects_blank_input():
    response = TestClient(app).post("/api/chat", json={"session_id":"s1", "message":"   "})
    assert response.status_code == 422
