"""Métricas de contacto: llamadas, WhatsApp y cobertura de cartera (Etapa 2)."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.utils.dates import parse_hubspot_datetime, utc_now

WHATSAPP_CHANNEL = "WHATS_APP"
DEFAULT_CONTACT_WINDOW_DAYS = 21
DEFAULT_SESSION_GAP_HOURS = 24
DURATION_INSUFFICIENT_PCT = 5.0
DURATION_PARTIAL_PCT = 30.0

TIME_BANDS: tuple[tuple[str, int, int], ...] = (
    ("06:00-08:59", 6, 8),
    ("09:00-11:59", 9, 11),
    ("12:00-13:59", 12, 13),
    ("14:00-16:59", 14, 16),
    ("17:00-19:59", 17, 19),
    ("20:00+", 20, 23),
)

DURATION_RANGE_LABELS: tuple[tuple[str, float | None, float | None], ...] = (
    ("0 segundos", 0, 0),
    ("1-30 segundos", 1, 30),
    ("31-60 segundos", 31, 60),
    ("1-3 minutos", 61, 180),
    ("3-5 minutos", 181, 300),
    ("5-10 minutos", 301, 600),
    ("10-20 minutos", 601, 1200),
    ("Más de 20 minutos", 1201, None),
    ("Sin duración", None, None),
)

from app.services.deal_analytics.contact_classification import (
    UNANSWERED_OUTCOMES,
    classify_call,
    classify_call_connection,
)


@dataclass
class ActivityRecord:
    activity_id: str
    activity_type: str
    deal_id: str | None
    owner_id: str | None
    timestamp: datetime
    properties: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None
    call_connection: str | None = None


@dataclass
class ContactActivityBundle:
    calls: list[ActivityRecord]
    whatsapp: list[ActivityRecord]
    deal_to_call_ids: dict[str, list[str]]
    deal_to_whatsapp_ids: dict[str, list[str]]
    attribution_quality: dict[str, Any] | None = None


def normalize_owner_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized or None


def parse_duration_seconds(raw: Any, *, sample_values: list[float] | None = None) -> float | None:
    val = _safe_float(raw)
    if val is None:
        return None
    if val < 0:
        return None
    if val == 0:
        return 0.0
    samples = sample_values or []
    if samples:
        med = statistics.median(samples + [val])
        if med > 10_000 or val > 10_000:
            return val / 1000.0
    if val > 10_000:
        return val / 1000.0
    return val


# UNANSWERED_OUTCOMES imported from contact_classification


def duration_data_status(coverage_pct: float | None) -> str:
    if coverage_pct is None or coverage_pct <= 0:
        return "unavailable"
    if coverage_pct < DURATION_INSUFFICIENT_PCT:
        return "insufficient"
    if coverage_pct < DURATION_PARTIAL_PCT:
        return "partial"
    return "available"


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _trimmed_mean(values: list[float], trim_pct: float = 5.0) -> float | None:
    if not values:
        return None
    if len(values) < 4:
        return round(statistics.mean(values), 2)
    sorted_v = sorted(values)
    trim = max(1, int(len(sorted_v) * trim_pct / 100.0))
    trimmed = sorted_v[trim : len(sorted_v) - trim] if len(sorted_v) > 2 * trim else sorted_v
    return round(statistics.mean(trimmed), 2) if trimmed else None


def _skewness(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return 0.0
    n = len(values)
    return round(sum(((x - mean) / std) ** 3 for x in values) / n, 4)


def _kurtosis_excess(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return 0.0
    n = len(values)
    return round(sum(((x - mean) / std) ** 4 for x in values) / n - 3.0, 4)


def _time_band(hour: int) -> str:
    for label, start, end in TIME_BANDS:
        if start <= hour <= end:
            return label
    return "20:00+"


def _local_dt(ts: datetime, tz: ZoneInfo) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(tz)


def estimate_whatsapp_sessions(
    messages: list[ActivityRecord],
    *,
    gap_hours: float = DEFAULT_SESSION_GAP_HOURS,
) -> list[list[ActivityRecord]]:
    by_deal: dict[str, list[ActivityRecord]] = defaultdict(list)
    for msg in messages:
        key = msg.deal_id or f"orphan:{msg.activity_id}"
        by_deal[key].append(msg)
    sessions: list[list[ActivityRecord]] = []
    gap = timedelta(hours=gap_hours)
    for deal_msgs in by_deal.values():
        ordered = sorted(deal_msgs, key=lambda m: m.timestamp)
        current: list[ActivityRecord] = []
        last_ts: datetime | None = None
        for msg in ordered:
            if last_ts is None or (msg.timestamp - last_ts) <= gap:
                current.append(msg)
            else:
                if current:
                    sessions.append(current)
                current = [msg]
            last_ts = msg.timestamp
        if current:
            sessions.append(current)
    return sessions


def activity_attributed_to_owner(activity: ActivityRecord, deal_owner_id: str | None) -> bool:
    act_owner = activity.owner_id
    if act_owner and deal_owner_id:
        return act_owner == deal_owner_id
    if act_owner:
        return True
    return deal_owner_id is not None


def build_activity_record(
    *,
    activity_id: str,
    activity_type: str,
    deal_id: str | None,
    row: dict[str, Any],
    duration_samples: list[float] | None = None,
) -> ActivityRecord | None:
    props = row.get("properties") or {}
    ts = parse_hubspot_datetime(row.get("activity_timestamp") or props.get("hs_timestamp"))
    if not ts:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    owner = normalize_owner_id(row.get("hubspot_owner_id") or props.get("hubspot_owner_id"))
    duration = None
    connection = None
    if activity_type == "calls":
        raw_dur = props.get("hs_call_duration")
        if raw_dur not in (None, ""):
            duration_samples_list = duration_samples or []
            if raw_dur not in (None, ""):
                try:
                    duration_samples_list.append(float(raw_dur))
                except (TypeError, ValueError):
                    pass
        duration = parse_duration_seconds(props.get("hs_call_duration"), sample_values=duration_samples)
        call_cls = classify_call(props, duration_seconds=duration)
        connection = call_cls.connection
    channel = str(props.get("hs_communication_channel_type") or "").upper()
    if activity_type == "communications" and channel and channel != WHATSAPP_CHANNEL:
        return None
    return ActivityRecord(
        activity_id=activity_id,
        activity_type=activity_type,
        deal_id=deal_id,
        owner_id=owner,
        timestamp=ts,
        properties=props,
        duration_seconds=duration,
        call_connection=connection,
    )


def compute_contact_metrics(
    deals: list[dict[str, Any]],
    bundle: ContactActivityBundle,
    *,
    owner_id: str | None = None,
    contact_window_days: int = DEFAULT_CONTACT_WINDOW_DAYS,
    session_gap_hours: float = DEFAULT_SESSION_GAP_HOURS,
    timezone: str = "America/Bogota",
    now: datetime | None = None,
    trim_pct: float = 5.0,
) -> dict[str, Any]:
    """Calcula métricas de contacto para un conjunto de negocios (asesor o grupo)."""
    now = now or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    tz = ZoneInfo(timezone)
    window_start = now - timedelta(days=contact_window_days)

    open_deals = [d for d in deals if d.get("is_open")]
    if owner_id:
        open_deals = [d for d in open_deals if normalize_owner_id(d.get("owner_id")) == owner_id]
        all_deals = [d for d in deals if normalize_owner_id(d.get("owner_id")) == owner_id]
    else:
        all_deals = list(deals)

    open_deal_ids = {str(d["deal_id"]) for d in open_deals if d.get("deal_id")}
    deal_owner_map = {
        str(d["deal_id"]): normalize_owner_id(d.get("owner_id"))
        for d in all_deals
        if d.get("deal_id")
    }

    scoped_calls: list[ActivityRecord] = []
    scoped_wa: list[ActivityRecord] = []

    for call in bundle.calls:
        if not call.deal_id or call.deal_id not in open_deal_ids and call.deal_id not in deal_owner_map:
            continue
        deal_owner = deal_owner_map.get(call.deal_id or "")
        if owner_id and not activity_attributed_to_owner(call, owner_id):
            if call.owner_id != owner_id and deal_owner != owner_id:
                continue
        scoped_calls.append(call)

    for msg in bundle.whatsapp:
        if not msg.deal_id or msg.deal_id not in deal_owner_map:
            continue
        deal_owner = deal_owner_map.get(msg.deal_id or "")
        if owner_id and not activity_attributed_to_owner(msg, owner_id):
            if msg.owner_id != owner_id and deal_owner != owner_id:
                continue
        scoped_wa.append(msg)

    calls_in_window = [c for c in scoped_calls if c.timestamp >= window_start]
    wa_in_window = [m for m in scoped_wa if m.timestamp >= window_start]

    deal_last_call: dict[str, datetime] = {}
    deal_last_wa: dict[str, datetime] = {}
    deal_calls_window: dict[str, int] = defaultdict(int)
    deal_wa_window: dict[str, int] = defaultdict(int)

    for call in scoped_calls:
        if call.deal_id:
            deal_last_call[call.deal_id] = max(deal_last_call.get(call.deal_id, call.timestamp), call.timestamp)
    for call in calls_in_window:
        if call.deal_id:
            deal_calls_window[call.deal_id] += 1

    for msg in scoped_wa:
        if msg.deal_id:
            deal_last_wa[msg.deal_id] = max(deal_last_wa.get(msg.deal_id, msg.timestamp), msg.timestamp)
    for msg in wa_in_window:
        if msg.deal_id:
            deal_wa_window[msg.deal_id] += 1

    unique_deals_called = len({c.deal_id for c in calls_in_window if c.deal_id})
    unique_deals_wa = len({m.deal_id for m in wa_in_window if m.deal_id})
    active_open = len(open_deals)

    outbound = sum(1 for c in scoped_calls if str(c.properties.get("hs_call_direction") or "").upper() == "OUTBOUND")
    inbound = sum(1 for c in scoped_calls if str(c.properties.get("hs_call_direction") or "").upper() == "INBOUND")
    connected = sum(1 for c in scoped_calls if c.call_connection == "connected")
    unanswered = sum(1 for c in scoped_calls if c.call_connection == "unanswered")

    durations_valid = [c.duration_seconds for c in scoped_calls if c.duration_seconds is not None]
    durations_positive = [d for d in durations_valid if d > 0]
    duration_missing = len(scoped_calls) - len(durations_valid)
    duration_coverage = round(len(durations_valid) / len(scoped_calls) * 100, 2) if scoped_calls else None
    dur_status = duration_data_status(duration_coverage)

    sorted_dur = sorted(durations_positive)
    total_minutes = round(sum(durations_positive) / 60.0, 2) if durations_positive else 0.0

    duration_stats = {
        "duration_valid_count": len(durations_valid),
        "duration_missing_count": duration_missing,
        "duration_coverage_percentage": duration_coverage,
        "duration_data_status": dur_status,
        "total_call_minutes": total_minutes if dur_status in ("available", "partial") else None,
        "average_call_duration_seconds": round(statistics.mean(durations_positive), 2) if durations_positive and dur_status != "unavailable" else None,
        "median_call_duration_seconds": round(statistics.median(durations_positive), 2) if durations_positive and dur_status != "unavailable" else None,
        "trimmed_mean_call_duration_seconds": _trimmed_mean(durations_positive, trim_pct) if durations_positive and dur_status not in ("unavailable", "insufficient") else None,
        "minimum_call_duration_seconds": sorted_dur[0] if sorted_dur else None,
        "maximum_call_duration_seconds": sorted_dur[-1] if sorted_dur else None,
        "percentile_25": _percentile(sorted_dur, 25),
        "percentile_50": _percentile(sorted_dur, 50),
        "percentile_75": _percentile(sorted_dur, 75),
        "percentile_90": _percentile(sorted_dur, 90),
        "percentile_95": _percentile(sorted_dur, 95),
        "standard_deviation": round(statistics.stdev(durations_positive), 2) if len(durations_positive) > 1 else None,
        "interquartile_range": (
            round(_percentile(sorted_dur, 75) - _percentile(sorted_dur, 25), 2)
            if sorted_dur and _percentile(sorted_dur, 75) is not None and _percentile(sorted_dur, 25) is not None
            else None
        ),
        "skewness": _skewness(durations_positive),
        "kurtosis": _kurtosis_excess(durations_positive),
        "duration_ranges": _duration_ranges(scoped_calls),
        "duration_note": (
            f"Duración disponible en {duration_coverage}% de las llamadas."
            if dur_status in ("insufficient", "unavailable")
            else None
        ),
    }

    call_days = {c.timestamp.astimezone(tz).date() for c in scoped_calls}
    wa_days = {m.timestamp.astimezone(tz).date() for m in scoped_wa}

    sessions = estimate_whatsapp_sessions(wa_in_window, gap_hours=session_gap_hours)
    session_sizes = [len(s) for s in sessions]

    deals_called_7 = _deals_with_activity_in_days(open_deal_ids, deal_last_call, now, 7)
    deals_called_21 = _deals_with_activity_in_days(open_deal_ids, deal_last_call, now, 21)
    deals_called_30 = _deals_with_activity_in_days(open_deal_ids, deal_last_call, now, 30)

    deals_wa_7 = _deals_with_activity_in_days(open_deal_ids, deal_last_wa, now, 7)
    deals_wa_21 = _deals_with_activity_in_days(open_deal_ids, deal_last_wa, now, 21)
    deals_wa_30 = _deals_with_activity_in_days(open_deal_ids, deal_last_wa, now, 30)

    channel_mix = _combined_channel_mix(open_deal_ids, deal_last_call, deal_last_wa, now, contact_window_days)

    overdue_21 = 0
    for deal_id in open_deal_ids:
        days_call = _days_since(deal_last_call.get(deal_id), now)
        days_wa = _days_since(deal_last_wa.get(deal_id), now)
        if (days_call is None or days_call > 21) and (days_wa is None or days_wa > 21):
            overdue_21 += 1

    call_coverage_rate = round(unique_deals_called / active_open * 100, 1) if active_open else None
    wa_coverage_rate = round(unique_deals_wa / active_open * 100, 1) if active_open else None
    combined_unique = len(
        {d for d in open_deal_ids if deal_calls_window.get(d, 0) > 0 or deal_wa_window.get(d, 0) > 0}
    )
    combined_coverage_rate = round(combined_unique / active_open * 100, 1) if active_open else None
    overdue_rate = round(overdue_21 / active_open * 100, 1) if active_open else None

    discipline_score = _discipline_contact_score(
        call_coverage_rate, wa_coverage_rate, combined_coverage_rate, overdue_rate
    )
    legacy_discipline = discipline_score

    from app.services.deal_analytics.contact_classification import ContactLevel, is_meaningful_contact
    from app.services.deal_analytics.operational_scores import (
        build_operational_evaluation_payload,
        legacy_discipline_contact_score,
    )

    meaningful_deals = {
        c.deal_id
        for c in scoped_calls
        if c.deal_id
        and is_meaningful_contact(
            classify_call(c.properties, duration_seconds=c.duration_seconds).level
        )
    }
    last_contact: dict[str, datetime] = {}
    for c in scoped_calls:
        if c.deal_id:
            last_contact[c.deal_id] = max(last_contact.get(c.deal_id, c.timestamp), c.timestamp)
    for m in scoped_wa:
        if m.deal_id:
            last_contact[m.deal_id] = max(last_contact.get(m.deal_id, m.timestamp), m.timestamp)

    operational_eval = build_operational_evaluation_payload(
        all_deals,
        last_contact_by_deal=last_contact,
        meaningful_contact_deal_ids=meaningful_deals,
        next_action_by_deal={},
        now=now,
    )
    operational_eval["legacy_discipline_contact_score"] = legacy_discipline_contact_score(
        call_coverage_rate, wa_coverage_rate, combined_coverage_rate, overdue_rate
    )
    discipline_operational = operational_eval.get("discipline_operational_score") or {}

    won = sum(1 for d in all_deals if d.get("is_won"))
    lost = sum(1 for d in all_deals if d.get("is_lost"))
    closed = won + lost
    close_rate = round(won / closed * 100, 1) if closed else None
    won_amount = sum(float(d.get("amount") or 0) for d in all_deals if d.get("is_won"))
    effectiveness_score = round(close_rate, 1) if close_rate is not None else None
    from app.services.deal_analytics.operational_scores import compute_commercial_effectiveness_score

    commercial_effectiveness = compute_commercial_effectiveness_score(
        won_deals=won, lost_deals=lost, period_end=now
    )

    load_class = _load_classification(
        active_open, combined_coverage_rate, overdue_rate
    )

    return {
        "contact_window_days": contact_window_days,
        "session_gap_hours": session_gap_hours,
        "active_deals": active_open,
        "assigned_deals": len(all_deals),
        "open_pipeline_amount": sum(float(d.get("amount") or 0) for d in open_deals),
        "won_deals": won,
        "lost_deals": lost,
        "close_rate": close_rate,
        "won_amount": won_amount,
        "calls": {
            "total_calls": len(scoped_calls),
            "outbound_calls": outbound,
            "inbound_calls": inbound,
            "completed_calls": sum(
                1 for c in scoped_calls if str(c.properties.get("hs_call_status") or "").upper() in {"COMPLETED", "COMPLETE"}
            ),
            "connected_calls": connected,
            "unanswered_calls": unanswered,
            "unknown_connection_calls": len(scoped_calls) - connected - unanswered,
            "unique_deals_called": unique_deals_called,
            "active_calling_days": len(call_days),
            "calls_per_active_day": round(len(scoped_calls) / len(call_days), 2) if call_days else None,
            "calls_per_deal": round(len(scoped_calls) / unique_deals_called, 2) if unique_deals_called else None,
            "deals_without_calls": sum(1 for d in open_deal_ids if d not in deal_last_call),
            "deals_with_one_call": sum(1 for d, n in deal_calls_window.items() if n == 1),
            "deals_with_multiple_calls": sum(1 for d, n in deal_calls_window.items() if n > 1),
            "deals_called_last_7d": deals_called_7,
            "deals_called_last_21d": deals_called_21,
            "deals_called_last_30d": deals_called_30,
            "call_coverage_rate": call_coverage_rate,
            "call_coverage_numerator": unique_deals_called,
            "call_coverage_denominator": active_open,
            **duration_stats,
            "by_weekday": _activity_by_weekday(scoped_calls, tz),
            "by_time_band": _calls_by_time_band(scoped_calls, tz),
            "weekly_trend": _weekly_activity_trend(scoped_calls, tz, now),
        },
        "whatsapp": {
            "whatsapp_messages": len(scoped_wa),
            "unique_deals_with_whatsapp": unique_deals_wa,
            "active_whatsapp_days": len(wa_days),
            "messages_per_deal_average": round(len(wa_in_window) / unique_deals_wa, 2) if unique_deals_wa else None,
            "messages_per_deal_median": (
                round(statistics.median(list(deal_wa_window.values())), 2) if deal_wa_window else None
            ),
            "first_whatsapp_at": min((m.timestamp for m in scoped_wa), default=None),
            "last_whatsapp_at": max((m.timestamp for m in scoped_wa), default=None),
            "days_since_last_whatsapp": _days_since(max((m.timestamp for m in scoped_wa), default=None), now),
            "deals_with_whatsapp_7d": deals_wa_7,
            "deals_with_whatsapp_21d": deals_wa_21,
            "deals_with_whatsapp_30d": deals_wa_30,
            "whatsapp_coverage_rate": wa_coverage_rate,
            "whatsapp_coverage_numerator": unique_deals_wa,
            "whatsapp_coverage_denominator": active_open,
            "estimated_whatsapp_sessions": len(sessions),
            "average_messages_per_session": round(len(wa_in_window) / len(sessions), 2) if sessions else None,
            "median_messages_per_session": round(statistics.median(session_sizes), 2) if session_sizes else None,
            "session_estimation_warning": (
                "HubSpot no proporciona un ID de conversación ni dirección en los datos disponibles. "
                "Las sesiones son una aproximación."
            ),
            "by_weekday": _activity_by_weekday(scoped_wa, tz),
            "by_time_band": _whatsapp_by_time_band(wa_in_window, tz),
            "weekly_trend": _weekly_activity_trend(scoped_wa, tz, now),
        },
        "coverage": {
            "combined_contact_coverage_rate": combined_coverage_rate,
            "combined_contact_coverage_numerator": combined_unique,
            "combined_contact_coverage_denominator": active_open,
            "deals_no_recent_contact": channel_mix["no_recent_contact"],
            "deals_call_only": channel_mix["call_only"],
            "deals_whatsapp_only": channel_mix["whatsapp_only"],
            "deals_multichannel": channel_mix["multichannel"],
            "channel_mix": channel_mix,
            "overdue_contact_21d": overdue_21,
            "overdue_contact_21d_rate": overdue_rate,
            "channel_overdue_21d": overdue_21,
            "channel_overdue_21d_rate": overdue_rate,
            "channel_overdue_21d_label": "Sin llamada ni WhatsApp en 21 días",
        },
        "evaluation": {
            "discipline_operational_score": discipline_operational.get("score"),
            "discipline_operational_status": discipline_operational.get("status"),
            "discipline_operational_detail": discipline_operational,
            "legacy_discipline_contact_score": legacy_discipline,
            "discipline_contact_score": discipline_operational.get("score") or legacy_discipline,
            "effectiveness_commercial_score": commercial_effectiveness.get("commercial_effectiveness_score")
            or effectiveness_score,
            "commercial_effectiveness_score": commercial_effectiveness.get("commercial_effectiveness_score"),
            "commercial_effectiveness_status": commercial_effectiveness.get("commercial_effectiveness_status"),
            "commercial_effectiveness_detail": commercial_effectiveness,
            "legacy_effectiveness_commercial_score": effectiveness_score,
            "operational_evaluation": operational_eval,
            "load_alert_40_plus": active_open >= 40,
            "load_classification": load_class,
        },
        "data_quality": {
            "calls_status": "available" if scoped_calls else "partial",
            "whatsapp_status": "available" if scoped_wa else "partial",
            "duration_status": dur_status,
            "whatsapp_sessions_status": "estimated",
            "whatsapp_direction_status": "unavailable",
        },
    }


def merge_contact_metrics_into_advisor_row(
    base: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Enriquece fila de asesor con KPIs de contacto."""
    calls = metrics.get("calls") or {}
    wa = metrics.get("whatsapp") or {}
    cov = metrics.get("coverage") or {}
    ev = metrics.get("evaluation") or {}
    return {
        **base,
        "call_coverage_rate": calls.get("call_coverage_rate"),
        "whatsapp_coverage_rate": wa.get("whatsapp_coverage_rate"),
        "combined_coverage_rate": cov.get("combined_contact_coverage_rate"),
        "overdue_contact_21d": cov.get("overdue_contact_21d"),
        "overdue_contact_21d_rate": cov.get("overdue_contact_21d_rate"),
        "total_calls": calls.get("total_calls"),
        "unique_deals_called": calls.get("unique_deals_called"),
        "total_call_minutes": calls.get("total_call_minutes"),
        "median_call_duration_seconds": calls.get("median_call_duration_seconds"),
        "duration_data_status": calls.get("duration_data_status"),
        "whatsapp_messages": wa.get("whatsapp_messages"),
        "unique_deals_with_whatsapp": wa.get("unique_deals_with_whatsapp"),
        "estimated_whatsapp_sessions": wa.get("estimated_whatsapp_sessions"),
        "discipline_operational_score": ev.get("discipline_operational_score"),
        "discipline_operational_status": ev.get("discipline_operational_status"),
        "legacy_discipline_contact_score": ev.get("legacy_discipline_contact_score"),
        "discipline_contact_score": ev.get("discipline_contact_score"),
        "commercial_effectiveness_score": ev.get("commercial_effectiveness_score"),
        "effectiveness_commercial_score": ev.get("effectiveness_commercial_score"),
        "channel_overdue_21d": cov.get("channel_overdue_21d"),
        "load_classification": ev.get("load_classification"),
        "won_deals": metrics.get("won_deals"),
        "close_rate": metrics.get("close_rate"),
        "contact_metrics": metrics,
    }


def rollup_group_contact_metrics(
    advisor_metrics: list[dict[str, Any]],
    *,
    group_deals: list[dict[str, Any]],
    bundle: ContactActivityBundle,
    contact_window_days: int = DEFAULT_CONTACT_WINDOW_DAYS,
    timezone: str = "America/Bogota",
) -> dict[str, Any]:
    """Agregación grupal desde registros base (no promedio de promedios)."""
    group_metrics = compute_contact_metrics(
        group_deals,
        bundle,
        owner_id=None,
        contact_window_days=contact_window_days,
        timezone=timezone,
    )
    advisor_medians = [
        (a.get("contact_metrics") or {}).get("calls", {}).get("median_call_duration_seconds")
        for a in advisor_metrics
        if (a.get("contact_metrics") or {}).get("calls", {}).get("median_call_duration_seconds") is not None
    ]
    group_metrics["group_aggregation"] = {
        "aggregation_method": "from_base_records",
        "advisor_count": len(advisor_metrics),
        "simple_avg_call_coverage_among_advisors": _safe_avg(
            [a.get("call_coverage_rate") for a in advisor_metrics if a.get("call_coverage_rate") is not None]
        ),
        "simple_avg_combined_coverage_among_advisors": _safe_avg(
            [a.get("combined_coverage_rate") for a in advisor_metrics if a.get("combined_coverage_rate") is not None]
        ),
        "median_of_advisor_medians_duration_seconds": (
            round(statistics.median(advisor_medians), 2) if advisor_medians else None
        ),
    }
    return group_metrics


def _safe_avg(values: list[float]) -> float | None:
    return round(statistics.mean(values), 2) if values else None


def _days_since(ts: datetime | None, now: datetime) -> int | None:
    if not ts:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return max(0, (now - ts).days)


def _deals_with_activity_in_days(
    deal_ids: set[str],
    last_activity: dict[str, datetime],
    now: datetime,
    days: int,
) -> int:
    cutoff = now - timedelta(days=days)
    return sum(1 for d in deal_ids if d in last_activity and last_activity[d] >= cutoff)


def _combined_channel_mix(
    open_deal_ids: set[str],
    deal_last_call: dict[str, datetime],
    deal_last_wa: dict[str, datetime],
    now: datetime,
    window_days: int,
) -> dict[str, int]:
    cutoff = now - timedelta(days=window_days)
    counts = {
        "no_recent_contact": 0,
        "call_only": 0,
        "whatsapp_only": 0,
        "multichannel": 0,
    }
    for deal_id in open_deal_ids:
        has_call = deal_id in deal_last_call and deal_last_call[deal_id] >= cutoff
        has_wa = deal_id in deal_last_wa and deal_last_wa[deal_id] >= cutoff
        if not has_call and not has_wa:
            counts["no_recent_contact"] += 1
        elif has_call and has_wa:
            counts["multichannel"] += 1
        elif has_call:
            counts["call_only"] += 1
        else:
            counts["whatsapp_only"] += 1
    return counts


def _duration_ranges(calls: list[ActivityRecord]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for call in calls:
        label = _duration_range_label(call.duration_seconds)
        counter[label] += 1
    return [{"range": label, "count": counter.get(label, 0)} for label, _, _ in DURATION_RANGE_LABELS]


def _duration_range_label(seconds: float | None) -> str:
    if seconds is None:
        return "Sin duración"
    for label, low, high in DURATION_RANGE_LABELS:
        if label == "Sin duración":
            continue
        if low is not None and high is not None and low <= seconds <= high:
            return label
        if high is None and low is not None and seconds >= low:
            return label
    return "Sin duración"


def _activity_by_weekday(activities: list[ActivityRecord], tz: ZoneInfo) -> list[dict[str, Any]]:
    weekdays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    counts = Counter(_local_dt(a.timestamp, tz).weekday() for a in activities)
    return [{"weekday": weekdays[i], "count": counts.get(i, 0)} for i in range(7)]


def _calls_by_time_band(calls: list[ActivityRecord], tz: ZoneInfo) -> list[dict[str, Any]]:
    bands: dict[str, dict[str, Any]] = {
        label: {"time_band": label, "calls": 0, "unique_deals": set(), "total_minutes": 0.0, "connected": 0}
        for label, _, _ in TIME_BANDS
    }
    for call in calls:
        band = _time_band(_local_dt(call.timestamp, tz).hour)
        if band not in bands:
            bands[band] = {"time_band": band, "calls": 0, "unique_deals": set(), "total_minutes": 0.0, "connected": 0}
        entry = bands[band]
        entry["calls"] += 1
        if call.deal_id:
            entry["unique_deals"].add(call.deal_id)
        if call.duration_seconds and call.duration_seconds > 0:
            entry["total_minutes"] += call.duration_seconds / 60.0
        if call.call_connection == "connected":
            entry["connected"] += 1
    result = []
    for label, _, _ in TIME_BANDS:
        entry = bands[label]
        calls_n = entry["calls"]
        result.append(
            {
                "time_band": label,
                "calls": calls_n,
                "unique_deals": len(entry["unique_deals"]),
                "total_minutes": round(entry["total_minutes"], 2),
                "connected_rate": round(entry["connected"] / calls_n * 100, 1) if calls_n else None,
            }
        )
    return result


def _whatsapp_by_time_band(messages: list[ActivityRecord], tz: ZoneInfo) -> list[dict[str, Any]]:
    bands: dict[str, dict[str, Any]] = defaultdict(lambda: {"messages": 0, "unique_deals": set()})
    for msg in messages:
        band = _time_band(_local_dt(msg.timestamp, tz).hour)
        bands[band]["time_band"] = band
        bands[band]["messages"] += 1
        if msg.deal_id:
            bands[band]["unique_deals"].add(msg.deal_id)
    result = []
    for label, _, _ in TIME_BANDS:
        entry = bands.get(label, {"messages": 0, "unique_deals": set()})
        result.append(
            {
                "time_band": label,
                "messages": entry.get("messages", 0),
                "unique_deals": len(entry.get("unique_deals", set())),
            }
        )
    return result


def _weekly_activity_trend(
    activities: list[ActivityRecord],
    tz: ZoneInfo,
    now: datetime,
) -> list[dict[str, Any]]:
    from app.utils.week_bounds import monday_of

    counts: Counter[str] = Counter()
    for act in activities:
        local = _local_dt(act.timestamp, tz)
        key = monday_of(local.date()).isoformat()
        counts[key] += 1
    if not counts:
        return []
    keys = sorted(counts.keys())
    return [{"week_start": k, "count": counts[k]} for k in keys[-12:]]


def _discipline_contact_score(
    call_cov: float | None,
    wa_cov: float | None,
    combined_cov: float | None,
    overdue_rate: float | None,
) -> float | None:
    if combined_cov is None and call_cov is None and wa_cov is None:
        return None
    score = (
        (call_cov or 0) * 0.25
        + (wa_cov or 0) * 0.25
        + (combined_cov or 0) * 0.25
        + max(0, 100 - (overdue_rate or 0)) * 0.15
        + (combined_cov or 0) * 0.10
    )
    return round(score, 1)


def _load_classification(
    active_deals: int,
    combined_coverage: float | None,
    overdue_rate: float | None,
) -> str:
    high_load = active_deals >= 40
    cov = combined_coverage or 0
    overdue = overdue_rate or 0
    healthy = cov >= 50 and overdue < 30
    if high_load and healthy:
        return "Carga alta, gestión saludable"
    if high_load and not healthy:
        return "Carga alta, cobertura baja"
    if not high_load and not healthy:
        return "Carga normal, cobertura baja"
    return "Carga normal, gestión saludable"


def load_contact_activity_bundle(
    repo: Any,
    deal_ids: list[str],
) -> ContactActivityBundle:
    """Carga llamadas y WhatsApp asociados a los negocios indicados."""
    deal_set = {str(d) for d in deal_ids}
    links = repo.fetch_activity_links_for_deals(deal_ids, ("calls", "communications"))
    call_ids: set[str] = set()
    comm_ids: set[str] = set()
    deal_to_call_ids: dict[str, list[str]] = defaultdict(list)
    deal_to_wa_ids: dict[str, list[str]] = defaultdict(list)

    for link in links:
        deal_id = str(link["deal_id"])
        act_id = str(link["activity_id"])
        act_type = link["activity_type"]
        if act_type == "calls":
            call_ids.add(act_id)
            deal_to_call_ids[deal_id].append(act_id)
        elif act_type == "communications":
            comm_ids.add(act_id)
            deal_to_wa_ids[deal_id].append(act_id)

    raw_calls = repo.fetch_calls_by_ids(sorted(call_ids))
    raw_comms = repo.fetch_communications_by_ids(sorted(comm_ids))

    duration_raw_samples = [
        float((r.get("properties") or {}).get("hs_call_duration"))
        for r in raw_calls
        if (r.get("properties") or {}).get("hs_call_duration") not in (None, "")
    ]

    calls: list[ActivityRecord] = []
    for row in raw_calls:
        act_id = str(row["hubspot_id"])
        deal_id = _first_deal_for_activity(act_id, deal_to_call_ids, deal_set)
        rec = build_activity_record(
            activity_id=act_id,
            activity_type="calls",
            deal_id=deal_id,
            row=row,
            duration_samples=duration_raw_samples,
        )
        if rec:
            calls.append(rec)

    whatsapp: list[ActivityRecord] = []
    for row in raw_comms:
        act_id = str(row["hubspot_id"])
        props = row.get("properties") or {}
        channel = str(props.get("hs_communication_channel_type") or "").upper()
        if channel != WHATSAPP_CHANNEL:
            continue
        deal_id = _first_deal_for_activity(act_id, deal_to_wa_ids, deal_set)
        rec = build_activity_record(
            activity_id=act_id,
            activity_type="communications",
            deal_id=deal_id,
            row=row,
        )
        if rec:
            whatsapp.append(rec)

    return ContactActivityBundle(
        calls=calls,
        whatsapp=whatsapp,
        deal_to_call_ids=dict(deal_to_call_ids),
        deal_to_whatsapp_ids=dict(deal_to_wa_ids),
    )


def load_attributed_contact_activity_bundle(
    repo: Any,
    deal_ids: list[str],
    *,
    open_deal_context: dict[str, dict[str, Any]] | None = None,
    preloaded_contact_ids: set[str] | None = None,
    preloaded_deal_contact_links: dict[str, list[str]] | None = None,
) -> ContactActivityBundle:
    """Carga llamadas con resolución canónica deal↔contacto y deduplicación."""
    from app.services.deal_analytics.activity_attribution import build_resolved_call_index

    deal_set = {str(d) for d in deal_ids}
    ctx = open_deal_context or {did: {"deal_id": did, "is_open": True} for did in deal_set}

    links = repo.fetch_activity_links_for_deals(deal_ids, ("calls", "communications"))
    deal_to_call_ids: dict[str, list[str]] = defaultdict(list)
    deal_to_wa_ids: dict[str, list[str]] = defaultdict(list)
    comm_ids: set[str] = set()

    for link in links:
        deal_id = str(link["deal_id"])
        act_id = str(link["activity_id"])
        act_type = link["activity_type"]
        if act_type == "calls":
            deal_to_call_ids[deal_id].append(act_id)
        elif act_type == "communications":
            comm_ids.add(act_id)
            deal_to_wa_ids[deal_id].append(act_id)

    if preloaded_contact_ids is not None:
        contact_ids = preloaded_contact_ids
    elif hasattr(repo, "fetch_contact_ids_for_deals"):
        contact_ids = repo.fetch_contact_ids_for_deals(deal_ids)
    else:
        contact_ids = set()
    call_to_contact_deals: dict[str, list[str]] = defaultdict(list)
    extra_call_ids: set[str] = set()
    if contact_ids and (
        hasattr(repo, "fetch_call_contact_links") or hasattr(repo, "fetch_call_ids_for_contacts")
    ):
        sorted_contacts = sorted(contact_ids)
        if preloaded_deal_contact_links is not None:
            deal_contact_links = preloaded_deal_contact_links
        elif hasattr(repo, "fetch_deal_contact_links"):
            deal_contact_links = repo.fetch_deal_contact_links(deal_ids)
        else:
            deal_contact_links = {}
        contact_to_deals: dict[str, list[str]] = defaultdict(list)
        for deal_id, cids in deal_contact_links.items():
            for cid in cids:
                contact_to_deals[cid].append(deal_id)
        if hasattr(repo, "fetch_call_contact_links"):
            call_contact_links = repo.fetch_call_contact_links(sorted_contacts)
            for link in call_contact_links:
                cid = link["contact_id"]
                call_id = link["call_id"]
                extra_call_ids.add(call_id)
                for deal_id in contact_to_deals.get(cid, []):
                    call_to_contact_deals[str(call_id)].append(str(deal_id))
        else:
            extra_call_ids = repo.fetch_call_ids_for_contacts(sorted_contacts)

    all_call_ids = set()
    for ids in deal_to_call_ids.values():
        all_call_ids.update(ids)
    all_call_ids |= extra_call_ids

    raw_calls = repo.fetch_calls_by_ids(sorted(all_call_ids))
    call_rows_by_id = {str(r["hubspot_id"]): r for r in raw_calls}

    call_to_deal, quality, _attrs = build_resolved_call_index(
        deal_ids=deal_ids,
        deal_to_call_ids=dict(deal_to_call_ids),
        call_to_contact_deal_ids=dict(call_to_contact_deals),
        open_deal_context=ctx,
        call_rows_by_id=call_rows_by_id,
    )

    duration_raw_samples = [
        float((r.get("properties") or {}).get("hs_call_duration"))
        for r in raw_calls
        if (r.get("properties") or {}).get("hs_call_duration") not in (None, "")
    ]

    calls: list[ActivityRecord] = []
    for call_id, deal_id in call_to_deal.items():
        row = call_rows_by_id.get(call_id)
        if not row:
            continue
        rec = build_activity_record(
            activity_id=call_id,
            activity_type="calls",
            deal_id=deal_id,
            row=row,
            duration_samples=duration_raw_samples,
        )
        if rec:
            calls.append(rec)

    raw_comms = repo.fetch_communications_by_ids(sorted(comm_ids))
    whatsapp: list[ActivityRecord] = []
    for row in raw_comms:
        act_id = str(row["hubspot_id"])
        props = row.get("properties") or {}
        channel = str(props.get("hs_communication_channel_type") or "").upper()
        if channel != WHATSAPP_CHANNEL:
            continue
        deal_id = _first_deal_for_activity(act_id, deal_to_wa_ids, deal_set)
        rec = build_activity_record(
            activity_id=act_id,
            activity_type="communications",
            deal_id=deal_id,
            row=row,
        )
        if rec:
            whatsapp.append(rec)

    return ContactActivityBundle(
        calls=calls,
        whatsapp=whatsapp,
        deal_to_call_ids=dict(deal_to_call_ids),
        deal_to_whatsapp_ids=dict(deal_to_wa_ids),
        attribution_quality={
            "attributed_activity_count": quality.attributed_activity_count,
            "ambiguous_activity_count": quality.ambiguous_activity_count,
            "unattributed_activity_count": quality.unattributed_activity_count,
            "duplicate_prevented_count": quality.duplicate_prevented_count,
        },
    )


def _first_deal_for_activity(
    activity_id: str,
    deal_map: dict[str, list[str]],
    deal_set: set[str],
) -> str | None:
    for deal_id, ids in deal_map.items():
        if activity_id in ids and deal_id in deal_set:
            return deal_id
    return None


def serialize_metrics_for_json(metrics: dict[str, Any]) -> dict[str, Any]:
    """Convierte datetimes a ISO para respuesta API."""

    def convert(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        if isinstance(obj, set):
            return list(obj)
        return obj

    return convert(metrics)
