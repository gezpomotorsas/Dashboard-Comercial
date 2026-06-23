"""Pruebas de métricas de contacto (Etapa 2)."""

from datetime import UTC, datetime, timedelta

from app.services.deal_analytics.contact_metrics import (
    ActivityRecord,
    ContactActivityBundle,
    classify_call_connection,
    compute_contact_metrics,
    estimate_whatsapp_sessions,
    parse_duration_seconds,
)


def _call(deal_id: str, owner: str, days_ago: int, duration: float | None = None, outcome: str | None = None):
    now = datetime.now(UTC)
    return ActivityRecord(
        activity_id=f"call-{deal_id}-{days_ago}",
        activity_type="calls",
        deal_id=deal_id,
        owner_id=owner,
        timestamp=now - timedelta(days=days_ago),
        properties={
            "hs_call_direction": "OUTBOUND",
            "hs_call_outcome": outcome or "",
            "hs_call_duration": str(int(duration * 1000)) if duration and duration > 100 else duration,
        },
        duration_seconds=duration,
        call_connection=classify_call_connection(
            {"hs_call_outcome": outcome or "", "hs_call_duration": duration},
            duration,
        ),
    )


def _wa(deal_id: str, owner: str, days_ago: int, hours: int = 0):
    now = datetime.now(UTC)
    return ActivityRecord(
        activity_id=f"wa-{deal_id}-{days_ago}-{hours}",
        activity_type="communications",
        deal_id=deal_id,
        owner_id=owner,
        timestamp=now - timedelta(days=days_ago, hours=hours),
        properties={"hs_communication_channel_type": "WHATS_APP"},
    )


def test_unique_deals_not_inflated_by_multiple_calls():
    deals = [
        {"deal_id": "1", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 100},
        {"deal_id": "2", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 200},
    ]
    calls = [_call("1", "A", 1) for _ in range(15)]
    bundle = ContactActivityBundle(calls=calls, whatsapp=[], deal_to_call_ids={}, deal_to_whatsapp_ids={})
    metrics = compute_contact_metrics(deals, bundle, owner_id="A", contact_window_days=21)
    assert metrics["calls"]["total_calls"] == 15
    assert metrics["calls"]["unique_deals_called"] == 1


def test_call_coverage_rate():
    deals = [
        {"deal_id": "1", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "2", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "3", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "4", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
    ]
    calls = [_call("1", "A", 2), _call("2", "A", 3)]
    bundle = ContactActivityBundle(calls=calls, whatsapp=[], deal_to_call_ids={}, deal_to_whatsapp_ids={})
    metrics = compute_contact_metrics(deals, bundle, owner_id="A", contact_window_days=21)
    assert metrics["calls"]["call_coverage_rate"] == 50.0
    assert metrics["calls"]["call_coverage_numerator"] == 2
    assert metrics["calls"]["call_coverage_denominator"] == 4


def test_combined_channel_mix():
    deals = [
        {"deal_id": "1", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "2", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "3", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
    ]
    calls = [_call("1", "A", 1)]
    wa = [_wa("2", "A", 1)]
    both = [_call("3", "A", 1), _wa("3", "A", 1)]
    bundle = ContactActivityBundle(
        calls=calls + [_call("3", "A", 1)],
        whatsapp=wa + [_wa("3", "A", 1)],
        deal_to_call_ids={},
        deal_to_whatsapp_ids={},
    )
    metrics = compute_contact_metrics(deals, bundle, owner_id="A", contact_window_days=21)
    mix = metrics["coverage"]["channel_mix"]
    assert mix["call_only"] == 1
    assert mix["whatsapp_only"] == 1
    assert mix["multichannel"] == 1


def test_whatsapp_session_estimation():
    messages = [
        _wa("1", "A", 1, hours=0),
        _wa("1", "A", 1, hours=1),
        _wa("1", "A", 3),
    ]
    sessions = estimate_whatsapp_sessions(messages, gap_hours=24)
    assert len(sessions) == 2


def test_completed_status_maps_via_hubspot_status():
    props = {"hs_call_status": "COMPLETED", "hs_call_outcome": ""}
    assert classify_call_connection(props, None) == "connected"


def test_duration_ms_normalization():
    assert parse_duration_seconds(120000, sample_values=[90000, 180000]) == 120.0
    assert parse_duration_seconds(45) == 45.0


def test_group_rollup_uses_base_records():
    from app.services.deal_analytics.contact_metrics import rollup_group_contact_metrics

    deals = [
        {"deal_id": "1", "owner_id": "A", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
        {"deal_id": "2", "owner_id": "B", "is_open": True, "is_won": False, "is_lost": False, "amount": 0},
    ]
    calls = [_call("1", "A", 1), _call("2", "B", 1)]
    bundle = ContactActivityBundle(calls=calls, whatsapp=[], deal_to_call_ids={}, deal_to_whatsapp_ids={})
    m_a = compute_contact_metrics(deals, bundle, owner_id="A", contact_window_days=21)
    m_b = compute_contact_metrics(deals, bundle, owner_id="B", contact_window_days=21)
    advisors = [
        {"owner_id": "A", "contact_metrics": m_a, "call_coverage_rate": m_a["calls"]["call_coverage_rate"]},
        {"owner_id": "B", "contact_metrics": m_b, "call_coverage_rate": m_b["calls"]["call_coverage_rate"]},
    ]
    group = rollup_group_contact_metrics(advisors, group_deals=deals, bundle=bundle, contact_window_days=21)
    assert group["calls"]["unique_deals_called"] == 2
    assert group["group_aggregation"]["aggregation_method"] == "from_base_records"
