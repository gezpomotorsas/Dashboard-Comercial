"""Pruebas de endpoints de configuración HubSpot."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.main import app


@pytest.mark.asyncio
async def test_hubspot_mappings_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.configuration.get_configuration_report",
        lambda: {
            "semantic_fields": [],
            "properties_found": 0,
            "missing_properties": [],
            "pipelines": [],
            "stages": [],
            "stage_classifications": [],
            "active_owners": [],
            "archived_owners": [],
            "brand_mappings": [],
            "invalid_mappings": [],
            "last_refresh_at": None,
            "metadata_snapshot_at": None,
            "field_mapping_version": 1,
            "dimension_mapping_version": 1,
        },
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/configuration/hubspot-mappings")
    assert response.status_code == 200
    assert "semantic_fields" in response.json()


@pytest.mark.asyncio
async def test_hubspot_mapping_issues_endpoint(monkeypatch):
    monkeypatch.setattr("app.api.configuration.get_configuration_issues", lambda: [])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/configuration/hubspot-mappings/issues")
    assert response.status_code == 200
    assert response.json() == []
