"""Pruebas del cliente HubSpot."""

import os

import pytest
from pydantic import SecretStr

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import (
    HubSpotAuthenticationError,
    HubSpotPermissionError,
    HubSpotRateLimitError,
    HubSpotRequestError,
)
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        hubspot_access_token=SecretStr("test-token"),
        supabase_url="https://example.supabase.co",
        supabase_secret_key=SecretStr("sb_secret_test"),
        hubspot_max_retries=2,
    )


@pytest.mark.asyncio
async def test_hubspot_401(settings, httpx_mock):
    httpx_mock.add_response(status_code=401, json={"message": "Invalid token"})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        with pytest.raises(HubSpotAuthenticationError):
            await client.get("/crm/v3/owners")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hubspot_403(settings, httpx_mock):
    httpx_mock.add_response(status_code=403, json={"message": "Forbidden"})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        with pytest.raises(HubSpotPermissionError):
            await client.get("/crm/v3/objects/contacts")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hubspot_429_retry_then_success(settings, httpx_mock):
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"}, json={"message": "Rate limit"})
    httpx_mock.add_response(status_code=200, json={"results": []})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        payload = await client.get("/crm/v3/owners")
        assert payload == {"results": []}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hubspot_500_retry_exhausted(settings, httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(status_code=500, json={"message": "Server error"})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        with pytest.raises(HubSpotRequestError):
            await client.get("/crm/v3/owners")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_hubspot_400_no_retry(settings, httpx_mock):
    httpx_mock.add_response(status_code=400, json={"message": "Bad request"})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        with pytest.raises(HubSpotRequestError) as exc:
            await client.get("/crm/v3/owners")
        assert exc.value.status_code == 400
    finally:
        await client.close()


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
@pytest.mark.asyncio
async def test_hubspot_rate_limit_exhausted(settings, httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"}, json={"message": "Rate limit"})

    client = HubSpotClient(settings=settings)
    await client.open()
    try:
        with pytest.raises(HubSpotRateLimitError):
            await client.get("/crm/v3/owners")
    finally:
        await client.close()
