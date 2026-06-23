"""Pruebas de endpoints deal analytics."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.main import app


@pytest.mark.asyncio
async def test_deal_analytics_filters_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.deal_analytics.DealAnalyticsQueryService.filter_options",
        lambda self: {"pipelines": [], "stages": [], "owners": [], "brands": [], "statuses": []},
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/deal-analytics/filters")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_advisor_portfolio_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.deal_analytics.DealAnalyticsQueryService.advisor_portfolio",
        lambda self, brand, owner_id: {
            "filters": {"brand_value": brand, "owner_id": owner_id},
            "population": {"total_deals": 100, "included_deals": 5, "excluded_deals": 95},
            "data": {
                "advisor": {"owner_id": owner_id, "owner_name": "Test", "brand_value": brand, "brand_label": "Voyah"},
                "summary": {"assigned_deals": 5, "open_deals": 3, "won_deals": 1, "lost_deals": 1,
                            "stale_45d_open": 1, "unattended_open": 0, "deals_with_overdue_tasks": 0,
                            "open_pipeline_amount": 0, "managed_30d_rate": 66.7},
                "charts": {"by_commercial_group": [], "open_health": [], "inactivity_distribution": [], "by_stage": [], "weekly_created": [], "weekly_won": [], "weekly_lost": [], "weekly_overdue_tasks": []},
                "deals": [],
                "tasks": [],
                "task_counts": {
                    "total": 0,
                    "pending": 0,
                    "overdue": 0,
                    "completed_late": 0,
                    "completed": 0,
                },
            },
            "data_quality": {"status": "available", "notes": [], "activity_coverage": "synced"},
            "configuration": {},
            "generated_at": "2026-01-01T00:00:00Z",
            "timezone": "America/Bogota",
        },
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/deal-analytics/brands/voyah/advisors/123/portfolio")
    assert response.status_code == 200
    assert response.json()["data"]["advisor"]["owner_id"] == "123"


@pytest.mark.asyncio
async def test_advisor_portfolio_invalid_brand():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/deal-analytics/brands/invalid/advisors/123/portfolio")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_deal_analytics_summary_endpoint(monkeypatch):
    monkeypatch.setattr(
        "app.api.deal_analytics.DealAnalyticsQueryService.summary",
        lambda self, filters: {
            "filters": {},
            "population": {"total_deals": 10, "included_deals": 10, "excluded_deals": 0},
            "data": {"total_deals": 10, "open_deals": 5, "won_deals": 2, "lost_deals": 1},
            "data_quality": {"status": "available", "notes": [], "activity_coverage": "synced"},
            "configuration": {},
            "generated_at": "2026-01-01T00:00:00Z",
            "timezone": "America/Bogota",
        },
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/deal-analytics/summary")
    assert response.status_code == 200
    assert response.json()["population"]["total_deals"] == 10
