import pytest
from app import graph
from app.models import Location, WeatherFacts
from app.services import UpstreamError

@pytest.mark.asyncio
async def test_follow_up_reuses_activity_and_place(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = []
    async def geocode(place):
        calls.append(("geocode", place))
        return Location(name="Bhopal", country="India", latitude=23.26, longitude=77.41)
    async def forecast(location, time_reference):
        calls.append(("forecast", time_reference))
        return WeatherFacts(temperature_2m=20, wind_speed_10m=45, precipitation=0, precipitation_probability=10, uv_index=2, weather_code=1, observed_at="2030-01-01T10:00", timezone="Asia/Kolkata")
    monkeypatch.setattr(graph.weather_service, "geocode", geocode)
    monkeypatch.setattr(graph.weather_service, "forecast", forecast)
    session = "memory-test-session"
    first = await graph.run_advisory(session, "Is it safe to cycle in Bhopal today?")
    second = await graph.run_advisory(session, "What about this evening?")
    assert first["status"] == "matched"
    assert "WB-001" in first["answer"] and "2030-01-01T10:00" in first["answer"]
    assert calls[-2:] == [("geocode", "Bhopal"), ("forecast", "this evening")]
    assert second["activity"] == "cycling"

@pytest.mark.asyncio
async def test_session_context_does_not_cross_session_boundaries(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async def geocode(_place):
        raise AssertionError("A separate session without a place must ask instead of reusing one")
    monkeypatch.setattr(graph.weather_service, "geocode", geocode)
    result = await graph.run_advisory("isolated-session", "What about this evening?")
    assert result["status"] == "unsupported_activity"

@pytest.mark.asyncio
async def test_live_weather_failure_stops_before_policy(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async def geocode(place):
        return Location(name=place, country="India", latitude=1, longitude=2)
    async def forecast(_location, _time):
        raise UpstreamError("unavailable")
    monkeypatch.setattr(graph.weather_service, "geocode", geocode)
    monkeypatch.setattr(graph.weather_service, "forecast", forecast)
    result = await graph.run_advisory("weather-failure-session", "Is it safe to cycle in Pune?")
    assert result["status"] == "weather_unavailable"
    assert result.get("policy") is None
    assert "weather_api_failed" in " ".join(result["trace"])

@pytest.mark.asyncio
async def test_unknown_location_stops_before_weather(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async def geocode(_place): return None
    async def forecast(*_args): raise AssertionError("Weather must not run for unresolved places")
    monkeypatch.setattr(graph.weather_service, "geocode", geocode)
    monkeypatch.setattr(graph.weather_service, "forecast", forecast)
    result = await graph.run_advisory("unknown-location-session", "Can I hike in Nowhereville today?")
    assert result["status"] == "location_not_found"
    assert result.get("weather") is None
