import pytest
from app.routes.voice import LANGUAGE_CONFIG, build_system_instruction


@pytest.mark.asyncio
async def test_voice_session_fallback_when_no_key(async_client):
    response = await async_client.post("/api/voice/session", json={"language": "en-IN"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "fallback"
    assert data["language"] == "en-IN"
    assert "Weatherwise" in data["instructions"]


@pytest.mark.asyncio
async def test_multilingual_voice_session_configurations(async_client):
    languages = ["en-IN", "te-IN", "hi-IN", "ta-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN"]
    for lang in languages:
        response = await async_client.post("/api/voice/session", json={"language": lang})
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == lang
        # Verify the language instruction contains the target language name
        expected_name = LANGUAGE_CONFIG[lang]
        assert expected_name in data["instructions"]
        assert "get_weather_advisory" in data["instructions"]


def test_build_system_instruction():
    instruction = build_system_instruction("te-IN")
    assert "Telugu" in instruction
    assert "Open-Meteo" in instruction
    assert "get_weather_advisory" in instruction
