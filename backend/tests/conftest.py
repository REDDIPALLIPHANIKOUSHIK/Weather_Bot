import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.policy import load_sops
from app.services.weather import WeatherService


@pytest.fixture(scope="session")
def loaded_sops():
    return load_sops()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
