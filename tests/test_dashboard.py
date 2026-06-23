"""Pruebas del dashboard semanal."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.dashboard import DashboardWeeklyResponse
from app.services.dashboard_service import DashboardService


def _contact(hid: str, created: str, owner: str | None = "1") -> dict:
    props: dict = {}
    if owner:
        props["hubspot_owner_id"] = owner
    return {
        "hubspot_id": hid,
        "created_at_hubspot": created,
        "properties": props,
    }


def _deal(
    hid: str,
    created: str,
    *,
    pipeline: str = "default",
    brand: str = "shacman",
    amount: str = "1000000",
    won: bool = False,
    lost: bool = False,
    closedate: str | None = None,
    owner: str = "1",
) -> dict:
    props = {
        "pipeline": pipeline,
        "amount": amount,
        "hubspot_owner_id": owner,
        "hs_is_closed_won": "true" if won else "false",
        "hs_is_closed_lost": "true" if lost else "false",
    }
    if closedate:
        props["closedate"] = closedate
    return {
        "hubspot_id": hid,
        "created_at_hubspot": created,
        "updated_at_hubspot": closedate or created,
        "pipeline_id": pipeline,
        "brand": brand,
        "properties": props,
    }


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.fetch_all.side_effect = lambda table, **kwargs: {
        "hubspot_contacts": [
            _contact("c1", "2026-06-16T10:00:00+00:00"),
            _contact("c2", "2026-06-10T10:00:00+00:00", owner="2"),
        ],
        "hubspot_deals": [
            _deal("d1", "2026-06-17T10:00:00+00:00", amount="850000"),
            _deal(
                "d2",
                "2026-06-05T10:00:00+00:00",
                won=True,
                closedate="2026-06-18T12:00:00+00:00",
                amount="5000000",
            ),
            _deal(
                "d3",
                "2026-06-04T10:00:00+00:00",
                pipeline="9999",
                brand="unknown",
                lost=True,
                closedate="2026-06-19T12:00:00+00:00",
            ),
        ],
    }.get(table, [])
    repo.fetch_owners.return_value = [
        {"hubspot_id": "1", "first_name": "Ana", "last_name": "López", "archived": False},
        {"hubspot_id": "2", "first_name": "Luis", "last_name": "Pérez", "archived": False},
    ]
    repo.fetch_pipelines.return_value = [
        {"pipeline_id": "default", "label": "Shacman", "archived": False},
        {"pipeline_id": "1000390393", "label": "Voyah", "archived": False},
    ]
    repo.fetch_contact_deal_brands.return_value = {"c1": "shacman"}
    repo.fetch_contact_activity_times.return_value = {
        "c1": [datetime(2026, 6, 16, 11, 0, tzinfo=UTC)],
    }
    repo.fetch_advisor_activities.return_value = [
        {"owner_id": "1", "calls": 5, "communications": 2, "meetings": 1, "tasks": 3, "notes": 1},
    ]
    repo.quality_summary.return_value = {
        "critical": 2,
        "warning": 5,
        "info": 10,
        "by_rule": [
            {"rule_code": "DEAL_WITHOUT_OWNER", "count": 1},
            {"rule_code": "DEAL_WITHOUT_CONTACT", "count": 1},
        ],
        "last_run_at": "2026-06-18T00:00:00+00:00",
    }
    repo.fetch_owner_commercial_scope.return_value = (set(), set())
    return repo


class TestDashboardService:
    def test_weekly_cards_available(self, mock_repo):
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15")

        assert isinstance(result, DashboardWeeklyResponse)
        codes = {c.code: c for c in result.cards}
        assert codes["leads_created"].value == 1
        assert codes["deals_created"].value == 1
        assert codes["won_deals"].value == 1
        assert codes["close_rate"].value == 50.0
        assert codes["critical_quality_issues"].value == 2

    def test_unknown_brand_in_results(self, mock_repo):
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15")
        brands = {r.brand: r for r in result.charts.brand_results}
        assert "unknown" in brands
        assert brands["unknown"].deals_created >= 0

    def test_first_response_lower_is_better(self, mock_repo):
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15")
        card = next(c for c in result.cards if c.code == "first_response_minutes")
        assert card.direction == "lower_is_better"
        assert card.value == 60.0

    def test_brand_filter(self, mock_repo):
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15", brand="shacman")
        assert result.filters.brand == "shacman"

    def test_activity_window_metadata(self, mock_repo):
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15")
        assert result.metadata.activity_window_days > 60
        assert result.metadata.email_tracking_enabled is False

    def test_owner_scope_uses_attributed_deals(self, mock_repo):
        mock_repo.fetch_owner_commercial_scope.return_value = ({"c9"}, {"d9"})
        mock_repo.fetch_all.side_effect = lambda table, **kwargs: {
            "hubspot_contacts": [
                _contact("c9", "2026-06-16T10:00:00+00:00", owner=None),
            ],
            "hubspot_deals": [
                _deal("d9", "2026-06-17T10:00:00+00:00", owner=None, amount="2000000"),
            ],
        }.get(table, [])
        service = DashboardService(repository=mock_repo)
        result = service.get_weekly_dashboard(week_start="2026-06-15", owner_id="160575836")
        codes = {c.code: c for c in result.cards}
        assert result.metadata.owner_scope_active is True
        assert codes["deals_created"].value == 1
        assert codes["leads_created"].value == 1
        mock_repo.fetch_owner_commercial_scope.assert_called_once()


@pytest.mark.asyncio
async def test_dashboard_weekly_endpoint(mock_repo):
    from app.api.dashboard import get_dashboard_service

    app.dependency_overrides[get_dashboard_service] = lambda: DashboardService(mock_repo)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/dashboard/weekly",
                params={"week_start": "2026-06-15", "brand": "all"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["filters"]["week_start"] == "2026-06-15"
        assert len(payload["cards"]) == 8
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_filters_endpoint(mock_repo):
    from app.api.dashboard import get_dashboard_service

    app.dependency_overrides[get_dashboard_service] = lambda: DashboardService(mock_repo)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/dashboard/filters")
        assert response.status_code == 200
        payload = response.json()
        assert "weeks" in payload
        assert "brands" in payload
        assert any(b["value"] == "unknown" for b in payload["brands"])
    finally:
        app.dependency_overrides.clear()
