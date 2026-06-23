"""Pruebas de semántica de tareas HubSpot."""

from datetime import UTC, datetime, timedelta

from app.services.deal_analytics.builder import _aggregate_tasks, build_deal_analytics_row
from app.services.deal_analytics.contact_metrics import ActivityRecord
from app.services.deal_analytics.query import _build_portfolio_tasks, _weekly_calls_volume
from app.services.deal_analytics.task_semantics import (
    is_closed_deal_for_task_metrics,
    is_reassigned_lead_task,
)
from app.services.hubspot_configuration.store import HubSpotConfigStore


def test_weekly_calls_volume_groups_by_week():
    base = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
    calls = [
        ActivityRecord("1", "calls", "d1", None, base),
        ActivityRecord("2", "calls", "d1", None, base + timedelta(days=1)),
        ActivityRecord("3", "calls", "d2", None, base + timedelta(days=8)),
    ]
    series = _weekly_calls_volume(calls, timezone="UTC")
    assert len(series) >= 2
    assert sum(point["calls"] for point in series) == 3


def test_is_reassigned_lead_task_matches_subject():
    assert is_reassigned_lead_task("Perdiste este Lead")
    assert is_reassigned_lead_task("  PERDISTE ESTE LEAD — contacto X")
    assert not is_reassigned_lead_task("Seguimiento cotización")
    assert not is_reassigned_lead_task(None)


def test_is_closed_deal_for_task_metrics():
    assert is_closed_deal_for_task_metrics({"status": "won"})
    assert is_closed_deal_for_task_metrics({"status": "lost"})
    assert is_closed_deal_for_task_metrics({"commercial_group": "cierre_ganado", "status": "open"})
    assert not is_closed_deal_for_task_metrics({"status": "open", "commercial_group": "cotizacion_financiera"})


def test_aggregate_tasks_excludes_reassigned_lead_from_performance():
    store = HubSpotConfigStore.from_fixtures()
    now = datetime.now(UTC)
    overdue_due = (now - timedelta(days=3)).isoformat()
    activities = [
        {
            "activity_type": "tasks",
            "properties": {
                "hs_task_subject": "Perdiste este Lead",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": overdue_due,
            },
        },
        {
            "activity_type": "tasks",
            "properties": {
                "hs_task_subject": "Llamar al cliente",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": overdue_due,
            },
        },
    ]
    stats = _aggregate_tasks(activities, config=store, now=now)
    assert stats["reassigned_lead_task_count"] == 1
    assert stats["task_count"] == 1
    assert stats["overdue_task_count"] == 1
    assert stats["has_overdue_tasks"] is True


def test_build_portfolio_tasks_excludes_reassigned_lead():
    store = HubSpotConfigStore.from_fixtures()
    now = datetime.now(UTC)
    tasks = [
        {
            "hubspot_id": "t1",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Perdiste este Lead",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now - timedelta(days=1)).isoformat(),
            },
        },
        {
            "hubspot_id": "t2",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Seguimiento",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now + timedelta(days=2)).isoformat(),
            },
        },
    ]
    built, excluded_orphan, excluded_reassigned, excluded_closed = _build_portfolio_tasks(
        tasks,
        task_links={"t1": "d1", "t2": "d2"},
        contact_links={},
        deal_context={
            "d1": {"deal_name": "A", "stage_label": "Etapa", "commercial_group_label": "Grupo", "status": "open"},
            "d2": {"deal_name": "B", "stage_label": "Etapa", "commercial_group_label": "Grupo", "status": "open"},
        },
        contact_names={},
        owner_key="owner1",
        brand_deal_ids={"d1", "d2"},
        config=store,
    )
    assert excluded_orphan == 0
    assert excluded_reassigned == 1
    assert excluded_closed == 0
    assert len(built) == 1
    assert built[0]["task_id"] == "t2"


def test_build_portfolio_tasks_excludes_closed_deal_tasks():
    store = HubSpotConfigStore.from_fixtures()
    now = datetime.now(UTC)
    tasks = [
        {
            "hubspot_id": "t1",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Tarea en ganado",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now - timedelta(days=1)).isoformat(),
            },
        },
        {
            "hubspot_id": "t2",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Tarea activa",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now + timedelta(days=2)).isoformat(),
            },
        },
    ]
    built, excluded_orphan, excluded_reassigned, excluded_closed = _build_portfolio_tasks(
        tasks,
        task_links={"t1": "d1", "t2": "d2"},
        contact_links={},
        deal_context={
            "d1": {
                "deal_name": "Ganado",
                "status": "won",
                "commercial_group": "cierre_ganado",
                "commercial_group_label": "Cierre ganado",
            },
            "d2": {"deal_name": "Abierto", "status": "open", "commercial_group_label": "Cotización"},
        },
        contact_names={},
        owner_key="owner1",
        brand_deal_ids={"d1", "d2"},
        config=store,
    )
    assert excluded_closed == 1
    assert len(built) == 1
    assert built[0]["task_id"] == "t2"


def test_build_portfolio_tasks_splits_overdue_and_completed_late():
    store = HubSpotConfigStore.from_fixtures()
    now = datetime.now(UTC)
    tasks = [
        {
            "hubspot_id": "t1",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Pendiente vencida",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now - timedelta(days=2)).isoformat(),
            },
        },
        {
            "hubspot_id": "t2",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Completada tarde",
                "hs_task_status": "COMPLETED",
                "hs_task_due_date": (now - timedelta(days=5)).isoformat(),
            },
        },
        {
            "hubspot_id": "t3",
            "hubspot_owner_id": "owner1",
            "properties": {
                "hs_task_subject": "Completada a tiempo",
                "hs_task_status": "COMPLETED",
                "hs_task_due_date": (now + timedelta(days=3)).isoformat(),
            },
        },
    ]
    built, *_ = _build_portfolio_tasks(
        tasks,
        task_links={"t1": "d1", "t2": "d1", "t3": "d2"},
        contact_links={},
        deal_context={
            "d1": {"deal_name": "A", "stage_label": "Etapa", "commercial_group_label": "Grupo", "status": "open"},
            "d2": {"deal_name": "B", "stage_label": "Etapa", "commercial_group_label": "Grupo", "status": "open"},
        },
        contact_names={},
        owner_key="owner1",
        brand_deal_ids={"d1", "d2"},
        config=store,
    )
    by_id = {row["task_id"]: row for row in built}
    assert by_id["t1"]["is_overdue"] is True
    assert by_id["t1"]["is_completed_late"] is False
    assert by_id["t2"]["is_overdue"] is False
    assert by_id["t2"]["is_completed_late"] is True
    assert by_id["t3"]["is_completed_late"] is False
    assert sum(1 for row in built if row["is_overdue"]) == 1
    assert sum(1 for row in built if row["is_completed_late"]) == 1


def test_closed_deal_row_still_counts_calls():
    store = HubSpotConfigStore.from_fixtures(
        pipelines={"default": {"pipeline_id": "default", "label": "Shacman", "archived": False}},
        stages={
            ("default", "won"): {"label": "Cierre ganado", "metadata": {"isClosed": "true", "probability": "1.0"}},
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
            ("deals", "dealstage"): {"object_type": "deals", "name": "dealstage"},
            ("deals", "pipeline"): {"object_type": "deals", "name": "pipeline"},
        },
    )
    now = datetime.now(UTC)
    deal = {
        "hubspot_id": "d-won",
        "pipeline_id": "default",
        "dealstage_id": "won",
        "properties": {"pipeline": "default", "dealstage": "won"},
        "created_at_hubspot": (now - timedelta(days=30)).isoformat(),
    }
    activities = [
        {"activity_type": "calls", "activity_timestamp": now.isoformat()},
        {
            "activity_type": "tasks",
            "properties": {
                "hs_task_subject": "Seguimiento",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": (now - timedelta(days=1)).isoformat(),
            },
        },
    ]
    row = build_deal_analytics_row(deal, config=store, contact_ids=set(), activities=activities, stage_history=[])
    assert row["status"] == "won"
    assert row["call_count"] == 1
    assert row["overdue_task_count"] == 0
    assert row["open_task_count"] == 0
