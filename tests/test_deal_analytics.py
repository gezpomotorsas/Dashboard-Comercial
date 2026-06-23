"""Pruebas de analítica centrada en negocios."""

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.services.deal_analytics.builder import build_deal_analytics_row
from app.services.deal_analytics.filters import apply_deal_filters, value_to_bucket
from app.services.deal_analytics.query import _outcome_snapshot, _weekly_deals_created
from app.services.hubspot_configuration.store import HubSpotConfigStore


def _store() -> HubSpotConfigStore:
    return HubSpotConfigStore.from_fixtures(
        pipelines={"default": {"pipeline_id": "default", "label": "Shacman", "archived": False}},
        stages={
            ("default", "open"): {"metadata": {"isClosed": "false"}},
            ("default", "won"): {"metadata": {"isClosed": "true", "probability": "1.0"}},
        },
        business_dimensions=[
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "default",
                "normalized_value": "shacman",
                "display_label": "Shacman",
                "is_active": True,
                "priority": 10,
            }
        ],
        field_mappings=[
            {
                "object_type": "deals",
                "semantic_key": "deal_amount",
                "hubspot_property_name": "amount",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_name",
                "hubspot_property_name": "dealname",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_stage",
                "hubspot_property_name": "dealstage",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_pipeline",
                "hubspot_property_name": "pipeline",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
        ],
        properties={
            ("deals", "amount"): {"object_type": "deals", "name": "amount"},
            ("deals", "dealname"): {"object_type": "deals", "name": "dealname"},
            ("deals", "dealstage"): {"object_type": "deals", "name": "dealstage"},
            ("deals", "pipeline"): {"object_type": "deals", "name": "pipeline"},
        },
    )


def test_one_row_per_deal_id():
    store = _store()
    deal = {
        "hubspot_id": "d1",
        "pipeline_id": "default",
        "dealstage_id": "open",
        "properties": {"dealname": "Negocio A", "amount": "1000000", "pipeline": "default", "dealstage": "open"},
        "created_at_hubspot": datetime.now(UTC).isoformat(),
    }
    row = build_deal_analytics_row(
        deal,
        config=store,
        contact_ids={"c1", "c2"},
        activities=[
            {"activity_type": "calls", "activity_timestamp": datetime.now(UTC).isoformat()},
            {"activity_type": "tasks", "activity_timestamp": datetime.now(UTC).isoformat()},
        ],
        stage_history=[],
    )
    assert row["deal_id"] == "d1"
    assert row["contact_count"] == 2
    assert row["call_count"] == 1
    assert row["task_count"] == 1
    assert row["activity_count"] == 1
    assert row["amount"] == 1_000_000.0


def test_amount_not_multiplied_by_contacts_or_activities():
    store = _store()
    deal = {
        "hubspot_id": "d2",
        "pipeline_id": "default",
        "dealstage_id": "open",
        "properties": {"amount": "5000000", "pipeline": "default", "dealstage": "open"},
        "created_at_hubspot": datetime.now(UTC).isoformat(),
    }
    row = build_deal_analytics_row(
        deal,
        config=store,
        contact_ids={"c1", "c2", "c3"},
        activities=[{"activity_type": "calls", "activity_timestamp": datetime.now(UTC).isoformat()}] * 5,
        stage_history=[],
    )
    assert row["amount"] == 5_000_000.0
    assert row["contact_count"] == 3
    assert row["activity_count"] == 5


def test_future_closedate_with_open_stage_stays_open():
    store = _store()
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    deal = {
        "hubspot_id": "d3",
        "pipeline_id": "default",
        "dealstage_id": "open",
        "properties": {
            "pipeline": "default",
            "dealstage": "open",
            "closedate": future,
        },
        "created_at_hubspot": datetime.now(UTC).isoformat(),
    }
    row = build_deal_analytics_row(
        deal,
        config=store,
        contact_ids=set(),
        activities=[],
        stage_history=[],
    )
    assert row["status"] == "open"
    assert row["closed_at"] is None


def test_status_partition_counts():
    rows = [
        {"deal_id": "1", "status": "open", "is_open": True, "is_won": False, "is_lost": False},
        {"deal_id": "2", "status": "won", "is_open": False, "is_won": True, "is_lost": False},
        {"deal_id": "3", "status": "lost", "is_open": False, "is_won": False, "is_lost": True},
        {"deal_id": "4", "status": "unknown", "is_open": False, "is_won": False, "is_lost": False},
    ]
    assert len(rows) == 4
    assert sum(1 for r in rows if r["status"] == "open") == 1
    assert sum(1 for r in rows if r["status"] == "won") == 1
    assert sum(1 for r in rows if r["status"] == "lost") == 1
    assert sum(1 for r in rows if r["status"] == "unknown") == 1


def test_brand_unknown_remains_visible():
    store = HubSpotConfigStore.from_fixtures()
    deal = {
        "hubspot_id": "d4",
        "properties": {"pipeline": "unknown-pipe"},
        "created_at_hubspot": datetime.now(UTC).isoformat(),
    }
    row = build_deal_analytics_row(deal, config=store, contact_ids=set(), activities=[], stage_history=[])
    assert row["brand_value"] == "unknown"


def test_activity_data_status_synced():
    store = _store()
    deal = {
        "hubspot_id": "d5",
        "pipeline_id": "default",
        "dealstage_id": "open",
        "properties": {"pipeline": "default", "dealstage": "open"},
        "created_at_hubspot": datetime.now(UTC).isoformat(),
    }
    row = build_deal_analytics_row(deal, config=store, contact_ids=set(), activities=[], stage_history=[])
    assert row["activity_data_status"] == "synced"


def test_weekly_deals_created_full_history():
    old = datetime(2024, 1, 10, 12, 0, tzinfo=UTC)
    recent = datetime.now(UTC) - timedelta(days=3)
    rows = [
        {"created_at": old.isoformat()},
        {"created_at": recent.isoformat()},
    ]
    series = _weekly_deals_created(rows, timezone="America/Bogota")
    assert len(series) > 12
    assert sum(p["deals_created"] for p in series) == 2


def test_bucket_configuration():
    assert value_to_bucket(5, "stage_age") == "0-7"
    assert value_to_bucket(45, "deal_age") == "31-60"


def test_close_rate_excludes_open_deals():
    snapshot = _outcome_snapshot(
        [
            {"is_open": True, "is_won": False, "is_lost": False, "amount": 100},
            {"is_open": False, "is_won": True, "is_lost": False, "amount": 200},
            {"is_open": False, "is_won": False, "is_lost": True, "amount": 0},
        ]
    )
    assert snapshot["close_rate"] == 50.0


def test_filters_keep_one_row_per_deal():
    from app.services.deal_analytics.filters import DealAnalyticsFilters

    rows = [{"deal_id": "1", "pipeline_id": "p1"}, {"deal_id": "2", "pipeline_id": "p2"}]
    filtered = apply_deal_filters(rows, DealAnalyticsFilters(pipeline_id="p1"))
    assert len(filtered) == 1
    assert filtered[0]["deal_id"] == "1"
