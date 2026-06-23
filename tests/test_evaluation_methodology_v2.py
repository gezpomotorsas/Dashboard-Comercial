"""Pruebas metodología de evaluación v2."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.deal_analytics.activity_attribution import (
    AttributionMethod,
    build_resolved_call_index,
    resolve_activity_to_deal,
)
from app.services.deal_analytics.contact_classification import ContactLevel, classify_call
from app.services.deal_analytics.contact_eligibility import ExclusionReason, resolve_contact_eligibility
from app.services.deal_analytics.evaluation_config import DEFAULT_OPERATIONAL_WEIGHTS, ScoreWeights
from app.services.deal_analytics.first_response import FirstResponseBasis, compute_first_response
from app.services.deal_analytics.operational_scores import (
    RateMetric,
    compute_discipline_operational_score,
    legacy_discipline_contact_score,
)
from app.services.deal_analytics.builder import build_deal_analytics_row
from app.services.deal_analytics.task_semantics import is_closed_deal_row_for_task_metrics
from app.services.hubspot_configuration.store import HubSpotConfigStore


def test_legacy_discipline_duplicates_combined_coverage():
    combined = 40.0
    overdue_rate = 100.0 - combined
    legacy = legacy_discipline_contact_score(40, 40, combined, overdue_rate)
    # Sin duplicación la parte de cobertura combinada sería ~40*0.35; legacy supera por doble conteo
    no_dup_estimate = combined * 0.35 + (100 - overdue_rate) * 0.15
    assert legacy is not None
    assert legacy > no_dup_estimate + 5


def test_operational_score_no_duplicate_components():
    components = {
        "eligible_contact_compliance_rate": RateMetric(8, 10, 80.0, "available"),
        "first_response_sla_rate": RateMetric(5, 10, 50.0, "available"),
        "next_action_compliance_rate": RateMetric(7, 10, 70.0, "available"),
        "effective_contact_rate": RateMetric(6, 10, 60.0, "available"),
        "overdue_task_compliance_rate": RateMetric(9, 10, 90.0, "available"),
    }
    result = compute_discipline_operational_score(components)
    assert result.status == "available"
    assert result.score is not None
    assert len(result.available_components) == 5
    expected = (
        80 * 0.30 + 50 * 0.25 + 70 * 0.20 + 60 * 0.15 + 90 * 0.10
    ) / 1.0
    assert abs(result.score - round(expected, 1)) < 0.2


def test_operational_score_insufficient_components_not_zero():
    components = {
        "eligible_contact_compliance_rate": RateMetric(1, 1, 100.0, "available"),
    }
    result = compute_discipline_operational_score(components, min_components=3)
    assert result.score is None
    assert result.status == "insufficient"


def test_closed_deal_preserves_historical_tasks():
    store = HubSpotConfigStore.from_fixtures(
        pipelines={"default": {"pipeline_id": "default", "label": "Shacman", "archived": False}},
        stages={
            ("default", "won"): {"label": "Cierre ganado", "metadata": {"isClosed": "true", "probability": "1.0"}},
        },
        field_mappings=[
            {
                "object_type": "deals",
                "semantic_key": "deal_stage",
                "hubspot_property_name": "dealstage",
                "is_active": True,
                "priority": 10,
            },
        ],
    )
    now = datetime.now(UTC)
    overdue_due = (now - timedelta(days=2)).isoformat()
    deal = {
        "hubspot_id": "d1",
        "properties": {"dealname": "Ganado", "dealstage": "won", "amount": "100"},
        "pipeline_id": "default",
        "dealstage_id": "won",
    }
    activities = [
        {
            "activity_type": "tasks",
            "properties": {
                "hs_task_subject": "Seguimiento",
                "hs_task_status": "NOT_STARTED",
                "hs_task_due_date": overdue_due,
            },
        },
        {
            "activity_type": "calls",
            "activity_timestamp": now.isoformat(),
            "properties": {"hs_call_outcome": "CONNECTED", "hs_call_status": "COMPLETED"},
        },
    ]
    row = build_deal_analytics_row(
        deal,
        config=store,
        contact_ids={"c1"},
        activities=activities,
        stage_history=[],
        now=now,
    )
    assert row["historical_overdue_task_count"] == 1
    assert row["operational_overdue_task_count"] == 0
    assert row["call_count"] == 1


def test_short_call_without_outcome_not_connected():
    cls = classify_call({"hs_call_direction": "OUTBOUND"}, duration_seconds=1.0)
    assert cls.connection != "connected"
    assert cls.level in (ContactLevel.UNKNOWN, ContactLevel.NOT_CONNECTED)


def test_no_answer_never_connected_by_duration():
    cls = classify_call(
        {"hs_call_outcome": "NO_ANSWER", "hs_call_direction": "OUTBOUND"},
        duration_seconds=120.0,
    )
    assert cls.connection == "unanswered"
    assert not cls.is_effective_for_builder


def test_direct_deal_association_wins():
    attr = resolve_activity_to_deal(
        "call1",
        "calls",
        direct_deal_ids=["d1"],
        contact_deal_ids=["d2"],
        open_deal_context={"d1": {"is_open": True}, "d2": {"is_open": True}},
    )
    assert attr.resolved_deal_id == "d1"
    assert attr.attribution_method == AttributionMethod.DIRECT_DEAL_ASSOCIATION.value


def test_call_not_duplicated_deal_and_contact():
    ctx = {"d1": {"is_open": True, "owner_id": "o1"}}
    deal_to_call = {"d1": ["c1"]}
    call_to_contact = {"c1": ["d1"]}
    rows = {"c1": {"hubspot_id": "c1", "properties": {}, "hubspot_owner_id": "o1"}}
    mapping, quality, _ = build_resolved_call_index(
        deal_ids=["d1"],
        deal_to_call_ids=deal_to_call,
        call_to_contact_deal_ids=call_to_contact,
        open_deal_context=ctx,
        call_rows_by_id=rows,
    )
    assert mapping.get("c1") == "d1"
    assert quality.duplicate_prevented_count >= 0
    assert quality.attributed_activity_count == 1


def test_ambiguous_call_not_attributed_to_all():
    ctx = {
        "d1": {"is_open": True, "owner_id": "o1"},
        "d2": {"is_open": True, "owner_id": "o2"},
    }
    attr = resolve_activity_to_deal(
        "c1",
        "calls",
        direct_deal_ids=[],
        contact_deal_ids=["d1", "d2"],
        open_deal_context=ctx,
        activity_owner_id=None,
    )
    assert attr.is_ambiguous
    assert attr.resolved_deal_id is None


def test_test_record_not_eligible():
    elig = resolve_contact_eligibility(
        {"deal_id": "d1", "is_open": True, "deal_name": "Lead prueba", "has_owner": True, "has_contact": True}
    )
    assert not elig.is_eligible
    assert elig.exclusion_reason == ExclusionReason.TEST_RECORD.value


def test_paused_deal_not_overdue_eligible():
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    elig = resolve_contact_eligibility(
        {"deal_id": "d1", "is_open": True, "has_owner": True, "has_contact": True},
        context={"paused_until": future},
    )
    assert not elig.is_eligible
    assert elig.exclusion_reason == ExclusionReason.PAUSED_UNTIL_FUTURE_DATE.value


def test_first_response_uses_assignment_when_available():
    assigned = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    created = datetime(2025, 12, 1, 10, 0, tzinfo=UTC)
    first = datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    result = compute_first_response(
        {"commercial_group": "prospeccion"},
        first_effective_contact_at=first,
        assignment_at=assigned,
        use_business_minutes=False,
    )
    assert result.first_response_basis == FirstResponseBasis.OWNER_ASSIGNMENT.value
    assert result.first_response_minutes == 15.0


def test_first_response_creation_fallback_documented():
    created = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    first = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    result = compute_first_response(
        {"commercial_group": "prospeccion", "created_at": created.isoformat()},
        first_effective_contact_at=first,
        assignment_at=None,
        use_business_minutes=False,
    )
    assert result.first_response_basis == FirstResponseBasis.DEAL_CREATION_FALLBACK.value
    assert result.data_status == "partial"


def test_commercial_effectiveness_insufficient_sample():
    from app.services.deal_analytics.operational_scores import compute_commercial_effectiveness_score

    result = compute_commercial_effectiveness_score(won_deals=1, lost_deals=0)
    assert result["commercial_effectiveness_status"] == "insufficient"
    assert result["minimum_sample_met"] is False


def test_score_weights_sum_100():
    DEFAULT_OPERATIONAL_WEIGHTS.validate()
    with pytest.raises(ValueError):
        ScoreWeights(
            eligible_contact_compliance=50,
            first_response_sla=50,
            next_action_compliance=50,
            effective_contact=50,
            overdue_task_compliance=50,
        ).validate()


def test_closed_deal_row_task_metrics_flag():
    assert is_closed_deal_row_for_task_metrics({"status": "won", "commercial_group": "cotizacion"})
