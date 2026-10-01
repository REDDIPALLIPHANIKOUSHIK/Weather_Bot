from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
import pytest
from app.models import Location
from app.services import OpenMeteo

@pytest.mark.asyncio
async def test_forecast_uses_requested_forecast_hour_and_real_response_fields():
    zone = ZoneInfo("UTC")
    noon = (datetime.now(zone) + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    times = [(noon + timedelta(hours=i-1)).strftime("%Y-%m-%dT%H:00") for i in range(3)]
    payload = {"timezone":"UTC", "hourly":{"time":times, "temperature_2m":[10,20,30], "wind_speed_10m":[1,2,3], "precipitation":[0,0.2,0], "precipitation_probability":[5,15,25], "uv_index":[1,4,3], "weather_code":[0,2,3]}}
    async def handler(request):
        assert request.url.params["forecast_days"] == "2"
        return httpx.Response(200, json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = await OpenMeteo(client).forecast(Location(name="Test", country="", latitude=1, longitude=2), "tomorrow")
    assert weather.temperature_2m == 20
    assert weather.precipitation_probability == 15
    assert weather.weather_code == 2
    assert weather.observed_at == times[1]
