"""Pruebas de endpoints de grupos de asesores."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.main import app

SAMPLE_GROUP = {
    "id": "grp-1",
    "name": "Equipo Norte",
    "description": None,
    "brand_value": "shacman",
    "source": "manual",
    "hubspot_source_id": None,
    "hubspot_source_label": None,
    "members": [{"owner_id": "101", "owner_name": "Ana"}],
    "member_count": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


@pytest.mark.asyncio
async def test_list_advisor_groups(monkeypatch):
    monkeypatch.setattr(
        "app.api.advisor_groups.AdvisorGroupsService.list_groups",
        lambda self: [SAMPLE_GROUP],
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/advisor-groups")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Equipo Norte"


@pytest.mark.asyncio
async def test_compare_advisor_groups(monkeypatch):
    monkeypatch.setattr(
        "app.api.advisor_groups.AdvisorGroupsService.compare_groups",
        lambda self, brand, group_ids: {
            "filters": {"brand_value": brand, "group_ids": group_ids},
            "population": {"total_deals": 10, "included_deals": 5, "excluded_deals": 5},
            "data": {
                "brand_value": brand,
                "brand_label": "Shacman",
                "groups": [
                    {
                        "group_id": "grp-1",
                        "group_name": "Equipo Norte",
                        "member_count": 1,
                        "assigned_deals": 5,
                        "open_deals": 3,
                        "new_deals_7d": 0,
                        "new_deals_30d": 1,
                        "stale_45d_open": 1,
                        "tasks_completed": 0,
                        "tasks_open": 2,
                        "tasks_overdue": 1,
                        "deals_with_overdue_tasks": 0,
                        "managed_30d_rate": 50.0,
                        "advisors": [],
                    }
                ],
            },
            "data_quality": {"status": "available", "notes": [], "activity_coverage": "synced"},
            "configuration": {},
            "generated_at": "2026-01-01T00:00:00Z",
            "timezone": "America/Bogota",
        },
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/advisor-groups/compare",
            json={"brand_value": "shacman", "group_ids": ["grp-1"]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["brand_value"] == "shacman"
    assert body["data"]["groups"][0]["open_deals"] == 3


@pytest.mark.asyncio
async def test_compare_advisor_groups_invalid_brand():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/advisor-groups/compare",
            json={"brand_value": "invalid", "group_ids": ["grp-1"]},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_advisor_group(monkeypatch):
    monkeypatch.setattr(
        "app.api.advisor_groups.AdvisorGroupsService.create_group",
        lambda self, payload: {**SAMPLE_GROUP, **payload, "id": "grp-new"},
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/advisor-groups",
            json={
                "name": "Nuevo",
                "brand_value": "voyah",
                "members": [{"owner_id": "202", "owner_name": "Luis"}],
            },
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Nuevo"


@pytest.mark.asyncio
async def test_delete_advisor_group(monkeypatch):
    monkeypatch.setattr(
        "app.api.advisor_groups.AdvisorGroupsService.get_group",
        lambda self, group_id: SAMPLE_GROUP if group_id == "grp-1" else None,
    )
    monkeypatch.setattr(
        "app.api.advisor_groups.AdvisorGroupsService.delete_group",
        lambda self, group_id: True,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/advisor-groups/grp-1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
