import pytest
import httpx
from app.models import Location
from app.services.weather import WeatherService, UpstreamWeatherError, AmbiguousLocationError


@pytest.mark.asyncio
async def test_weather_service_geocode_and_forecast_mock():
    # Test with custom transport to test API mapping accurately
    def mock_handler(request: httpx.Request):
        url = str(request.url)
        if "geocoding-api.open-meteo.com" in url:
            if "Bhopal" in url:
                return httpx.Response(200, json={
                    "results": [
                        {"name": "Bhopal", "country": "India", "latitude": 23.2599, "longitude": 77.4126}
                    ]
                })
            elif "AmbiguousTown" in url:
                return httpx.Response(200, json={
                    "results": [
                        {"name": "AmbiguousTown", "country": "USA", "latitude": 40.0, "longitude": -80.0},
                        {"name": "AmbiguousTown", "country": "Canada", "latitude": 45.0, "longitude": -75.0},
                    ]
                })
            else:
                return httpx.Response(200, json={"results": []})

        if "api.open-meteo.com/v1/forecast" in url:
            return httpx.Response(200, json={
                "timezone": "Asia/Kolkata",
                "current": {
                    "time": "2026-10-02T14:00",
                    "temperature_2m": 31.4,
                    "wind_speed_10m": 12.0,
                    "precipitation": 0.0,
                    "weather_code": 1,
                },
                "hourly": {
                    "time": ["2026-10-02T14:00", "2026-10-02T18:00"],
                    "temperature_2m": [31.4, 27.5],
                    "wind_speed_10m": [12.0, 15.0],
                    "precipitation": [0.0, 0.0],
                    "precipitation_probability": [5, 10],
                    "uv_index": [6.5, 1.2],
                    "weather_code": [1, 2],
                }
            })

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = WeatherService(client=client)

    # 1. Geocode known city
    loc = await service.geocode("Bhopal")
    assert loc is not None
    assert loc.name == "Bhopal"
    assert loc.country == "India"
    assert loc.latitude == 23.2599

    # 2. Indic script mapping
    loc_indic = await service.geocode("భోపాల్")
    assert loc_indic is not None
    assert loc_indic.name == "Bhopal"

    # 3. Ambiguous location
    with pytest.raises(AmbiguousLocationError):
        await service.geocode("AmbiguousTown")

    # 4. Unknown location
    unknown_loc = await service.geocode("NonExistentPlaceXYZ999")
    assert unknown_loc is None

    # 5. Fetch forecast
    facts = await service.forecast(loc, "today")
    assert facts.temperature_2m == 31.4
    assert facts.wind_speed_10m == 12.0
    assert facts.precipitation_probability == 5
    assert facts.timezone == "Asia/Kolkata"
    assert facts.source == "Open-Meteo"


@pytest.mark.asyncio
async def test_weather_upstream_failure():
    def failure_handler(request: httpx.Request):
        return httpx.Response(500, json={"error": "Internal Error"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(failure_handler))
    service = WeatherService(client=client)

    with pytest.raises(UpstreamWeatherError):
        await service.geocode("Bhopal")
