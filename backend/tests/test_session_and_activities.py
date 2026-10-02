import pytest
from app.models import CurrentLocation, Location, WeatherFacts
from app.services.advisory import AdvisoryCoordinator
from app.services.weather import WeatherService


class ComprehensiveMockWeather(WeatherService):
    async def geocode(self, query: str):
        q = query.lower()
        if "delhi" in q:
            return Location(name="Delhi", country="India", latitude=28.61, longitude=77.20)
        if "jaipur" in q:
            return Location(name="Jaipur", country="India", latitude=26.91, longitude=75.78)
        if "pune" in q:
            return Location(name="Pune", country="India", latitude=18.52, longitude=73.85)
        return Location(name="DefaultCity", country="India", latitude=20.0, longitude=78.0)

    async def forecast(self, location: Location, time_reference: str = "today"):
        return WeatherFacts(
            temperature_2m=36.0,  # Warm weather
            wind_speed_10m=20.0,
            precipitation=0.0,
            precipitation_probability=20.0,
            uv_index=7.0,
            weather_code=1,
            observed_at="2026-10-02T15:00",
            timezone="Asia/Kolkata",
            source="Open-Meteo",
        )


@pytest.mark.asyncio
async def test_session_continuity_multiple_turns():
    coordinator = AdvisoryCoordinator(weather_service=ComprehensiveMockWeather())
    sid = "session-multiturn-123"

    # Turn 1: User asks about cycling in Jaipur
    r1 = await coordinator.run(sid, "Is it safe to cycle in Jaipur today?")
    assert r1.status == "matched" or r1.status == "no_policy"
    assert r1.location.name == "Jaipur"

    # Turn 2: User asks follow-up about this evening without naming activity or city
    r2 = await coordinator.run(sid, "What about this evening?")
    assert r2.status != "unsupported_activity"
    assert r2.status != "needs_location"
    assert r2.location.name == "Jaipur"

    # Turn 3: User switches city explicitly to Pune
    r3 = await coordinator.run(sid, "Can I cycle in Pune tomorrow?")
    assert r3.location.name == "Pune"


@pytest.mark.asyncio
async def test_all_supported_activities():
    coordinator = AdvisoryCoordinator(weather_service=ComprehensiveMockWeather())
    activities_queries = [
        ("cycling", "Is cycling safe in Delhi today?"),
        ("running", "Can I go running in Delhi today?"),
        ("hiking", "Should I go hiking in Delhi today?"),
        ("walking", "Is it safe to walk in Delhi today?"),
        ("pet_walking", "Can I take my dog for a pet walk in Delhi today?"),
        ("elderly_outdoor", "Is it safe for an elderly person to go outside in Delhi today?"),
        ("picnic", "Is today a good day for a picnic in Delhi?"),
        ("commuting", "Is it safe to cycle commute to work in Delhi today?"),
        ("park_visit", "Should I take my child to the park in Delhi this afternoon?"),
        ("outdoor_leisure", "Is it a good time for outdoor leisure in Delhi today?"),
    ]

    for expected_act, query in activities_queries:
        resp = await coordinator.run(f"session-{expected_act}", query)
        assert resp.status in {"matched", "no_policy"}, f"Failed for {expected_act}: {resp.status}, {resp.answer}"
        assert resp.location is not None
        assert resp.weather is not None
