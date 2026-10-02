import pytest
from app import graph
from app.models import WeatherFacts

@pytest.mark.asyncio
async def test_current_location_path(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    async def geocode(_): raise AssertionError("Current location should not geocode")
    async def forecast(location,_):
        assert location.latitude==pytest.approx(13.0827); assert location.longitude==pytest.approx(80.2707)
        return WeatherFacts(temperature_2m=29,wind_speed_10m=42,precipitation=0,precipitation_probability=10,uv_index=5,weather_code=1,observed_at="2030-01-01T10:00",timezone="Asia/Kolkata")
    monkeypatch.setattr(graph.weather_service,"geocode",geocode);monkeypatch.setattr(graph.weather_service,"forecast",forecast)
    result=await graph.run_advisory("loc-test","Is it safe to cycle here today?",{"latitude":13.0827,"longitude":80.2707})
    assert result["location"].name=="Your current location"
