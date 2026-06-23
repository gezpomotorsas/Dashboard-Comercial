"""Pruebas del endpoint /health."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test_key_value_here")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_VERSION", "0.1.0")

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "gezpomotor-hubspot-extractor"
    assert payload["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_version_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "development"
