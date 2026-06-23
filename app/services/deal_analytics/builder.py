"""Construcción de fila deal_analytics desde datos sincronizados."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.services.deal_analytics.brand_stale import stale_threshold_days_for_brand
from app.services.deal_analytics.stage_semantics import resolve_commercial_stage_group
from app.services.deal_analytics.task_semantics import is_closed_deal_row_for_task_metrics, is_reassigned_lead_activity
from app.services.hubspot_configuration.store import HubSpotConfigStore
from app.utils.dates import parse_hubspot_datetime, utc_now


MEETING_COMPLETED = frozenset({"COMPLETED", "COMPLETE"})
EFFECTIVE_TYPES = frozenset({"calls", "communications", "meetings"})
INTERNAL_TYPES = frozenset({"tasks", "notes"})


def _parse_amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_owner_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized or None


def _days_between(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return max(0, (end - start).days)


def _minutes_between(start: datetime, end: datetime) -> float | None:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end < start:
        return None
    return (end - start).total_seconds() / 60.0


def build_deal_analytics_row(
    deal: dict[str, Any],
    *,
    config: HubSpotConfigStore,
    contact_ids: set[str],
    contacts: list[dict[str, Any]] | None = None,
    activities: list[dict[str, Any]],
    stage_history: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    now = now or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    deal_id = str(deal["hubspot_id"])
    props = deal.get("properties") or {}
    pipeline_id = deal.get("pipeline_id") or config.get_property_value(deal, "deals", "deal_pipeline")
    if pipeline_id in (None, ""):
        pipeline_id = props.get("pipeline")
    pipeline_id = str(pipeline_id) if pipeline_id not in (None, "") else None

    stage_id = deal.get("dealstage_id") or config.get_property_value(deal, "deals", "deal_stage")
    stage_id = str(stage_id) if stage_id not in (None, "") else None

    status, status_source = config.resolve_deal_status(deal)

    close_raw = config.get_property_value(deal, "deals", "deal_close_date") or props.get("closedate")
    closed_at = parse_hubspot_datetime(close_raw)
    if closed_at and closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=UTC)

    if status == "open" and closed_at and closed_at > now:
        closed_at = None

    created_raw = (
        config.get_property_value(deal, "deals", "deal_created_at")
        or deal.get("created_at_hubspot")
        or props.get("createdate")
    )
    created_at = parse_hubspot_datetime(created_raw)
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    last_modified_at = parse_hubspot_datetime(deal.get("updated_at_hubspot"))
    if last_modified_at and last_modified_at.tzinfo is None:
        last_modified_at = last_modified_at.replace(tzinfo=UTC)

    if status in ("won", "lost") and closed_at and created_at and closed_at < created_at:
        closed_at = None

    owner_raw = (
        config.get_property_value(deal, "deals", "deal_owner")
        or config.get_property_value(deal, "deals", "owner")
        or props.get("hubspot_owner_id")
    )
    owner_id = _normalize_owner_id(owner_raw)
    if not owner_id:
        owner_id = _resolve_owner_from_activities(activities)
    owner = config.owners.get(str(owner_id)) if owner_id else None
    owner_active = not bool(owner.get("archived")) if owner else None

    amount = _parse_amount(config.get_property_value(deal, "deals", "deal_amount") or props.get("amount"))

    stage_row = config.stages.get((str(pipeline_id), str(stage_id))) if pipeline_id and stage_id else None
    stage_display_order = stage_row.get("display_order") if stage_row else None
    stage_label_resolved = config.stage_label(pipeline_id, stage_id) or (stage_row.get("label") if stage_row else None)
    commercial_group, commercial_group_label, commercial_group_order = resolve_commercial_stage_group(
        stage_label_resolved
    )
    is_unknown_stage = not stage_id or not stage_row

    brand_value, brand_label = _resolve_brand(deal, config, pipeline_id)
    is_unknown_brand = brand_value == "unknown"
    zone_value, zone_label, city_value, department_value = config.resolve_deal_zone(
        deal,
        contacts=contacts,
        owner_id=owner_id,
    )
    is_unknown_zone = zone_value == "unknown"
    model_value, model_label = config.resolve_semantic_dimension(deal, "model", ("deal_model",))
    source_value, source_label = config.resolve_semantic_dimension(deal, "source", ("deal_source",))

    activity_stats = _aggregate_activities(
        activities,
        config=config,
        now=now,
        lookback_days=0,
        created_at=created_at,
    )
    closed_for_tasks = status in ("won", "lost") or commercial_group in (
        "cierre_ganado",
        "cierre_perdido",
    )
    task_stats_historical = _aggregate_tasks(activities, config=config, now=now)
    task_stats_operational = (
        _empty_task_stats()
        if closed_for_tasks
        else task_stats_historical
    )
    history_stats = _aggregate_stage_history(stage_history, pipeline_id, stage_id)

    age_days = _days_between(created_at, now) if created_at else None
    days_in_stage = history_stats.get("days_in_current_stage")
    days_since_last = activity_stats.get("days_since_last_activity")

    is_open = status == "open"
    is_won = status == "won"
    is_lost = status == "lost"
    is_unknown_pipeline = bool(pipeline_id and pipeline_id not in config.known_pipeline_ids)

    stale_threshold_days = stale_threshold_days_for_brand(brand_value)

    stale_reason = _stale_reason(
        is_open=is_open,
        days_since_last=days_since_last,
        days_in_stage=days_in_stage,
        stale_activity_days=stale_threshold_days,
        stale_stage_days=stale_threshold_days,
        has_activity=activity_stats["has_activity"],
    )
    is_stale = stale_reason is not None
    stale_45d = is_open and (
        days_since_last is not None and days_since_last >= stale_threshold_days
        or (not activity_stats["has_activity"])
    )

    is_unattended, unattended_reason = _unattended_status(
        is_open=is_open,
        has_recent_activity_30d=activity_stats["has_recent_activity_30d"],
        has_recent_effective_contact_30d=activity_stats["has_recent_effective_contact_30d"],
        has_overdue_tasks=task_stats_operational["has_overdue_tasks"],
        has_future_task=task_stats_operational["has_future_task"],
    )
    alert_reason = _alert_reason(is_stale, stale_reason, is_unattended, unattended_reason)

    deal_name = config.get_property_value(deal, "deals", "deal_name") or props.get("dealname")

    completeness = _completeness_score(
        has_owner=bool(owner_id),
        has_contact=bool(contact_ids),
        has_amount=amount is not None,
        has_activity=activity_stats["has_activity"],
        has_effective=activity_stats["has_effective_contact"],
        status_known=status != "unknown",
        pipeline_known=not is_unknown_pipeline,
    )

    return {
        "deal_id": deal_id,
        "deal_name": deal_name,
        "pipeline_id": pipeline_id,
        "pipeline_label": config.pipeline_label(pipeline_id),
        "stage_id": stage_id,
        "stage_label": stage_label_resolved or config.stage_label(pipeline_id, stage_id),
        "stage_display_order": stage_display_order,
        "commercial_group": commercial_group,
        "commercial_group_label": commercial_group_label,
        "commercial_group_order": commercial_group_order,
        "owner_id": owner_id,
        "owner_name": config.owner_name(owner_id),
        "owner_active": owner_active,
        "brand_value": brand_value,
        "brand_label": brand_label,
        "zone_value": zone_value,
        "zone_label": zone_label,
        "city_value": city_value,
        "department_value": department_value,
        "model_value": model_value,
        "model_label": model_label,
        "source_value": source_value,
        "source_label": source_label,
        "status": status,
        "status_source": status_source,
        "amount": amount,
        "currency": "COP",
        "created_at": created_at.isoformat() if created_at else None,
        "closed_at": closed_at.isoformat() if closed_at and status in ("won", "lost") else None,
        "last_modified_at": last_modified_at.isoformat() if last_modified_at else None,
        "age_days": age_days,
        "days_in_current_stage": days_in_stage,
        "first_activity_at": activity_stats["first_activity_at"],
        "last_activity_at": activity_stats["last_activity_at"],
        "days_since_last_activity": days_since_last,
        "first_effective_contact_at": activity_stats["first_effective_contact_at"],
        "last_effective_contact_at": activity_stats["last_effective_contact_at"],
        "days_since_effective_contact": activity_stats["days_since_effective_contact"],
        "first_response_minutes": activity_stats["first_response_minutes"],
        "contact_count": len(contact_ids),
        "activity_count": activity_stats["activity_count"],
        "effective_contact_count": activity_stats["effective_contact_count"],
        "call_count": activity_stats["call_count"],
        "completed_call_count": activity_stats["completed_call_count"],
        "last_call_at": activity_stats["last_call_at"],
        "communication_count": activity_stats["communication_count"],
        "last_communication_at": activity_stats["last_communication_at"],
        "meeting_count": activity_stats["meeting_count"],
        "completed_meeting_count": activity_stats["completed_meeting_count"],
        "task_count": task_stats_operational["task_count"],
        "open_task_count": task_stats_operational["open_task_count"],
        "completed_task_count": task_stats_operational["completed_task_count"],
        "overdue_task_count": task_stats_operational["overdue_task_count"],
        "tasks_due_next_7d": task_stats_operational["tasks_due_next_7d"],
        "oldest_overdue_task_days": task_stats_operational["oldest_overdue_task_days"],
        "has_overdue_tasks": task_stats_operational["has_overdue_tasks"],
        "has_future_task": task_stats_operational["has_future_task"],
        "task_data_status": task_stats_operational["task_data_status"],
        "historical_task_count": task_stats_historical["task_count"],
        "historical_open_task_count": task_stats_historical["open_task_count"],
        "historical_completed_task_count": task_stats_historical["completed_task_count"],
        "historical_overdue_task_count": task_stats_historical["overdue_task_count"],
        "operational_open_task_count": task_stats_operational["open_task_count"],
        "operational_overdue_task_count": task_stats_operational["overdue_task_count"],
        "operational_has_overdue_tasks": task_stats_operational["has_overdue_tasks"],
        "operational_has_future_task": task_stats_operational["has_future_task"],
        "note_count": activity_stats["note_count"],
        "stage_change_count": history_stats["stage_change_count"],
        "stages_visited_count": history_stats["stages_visited_count"],
        "has_contact": len(contact_ids) > 0,
        "has_owner": bool(owner_id),
        "has_amount": amount is not None,
        "has_activity": activity_stats["has_activity"],
        "has_effective_contact": activity_stats["has_effective_contact"],
        "has_recent_activity_7d": activity_stats["has_recent_activity_7d"],
        "has_recent_activity_30d": activity_stats["has_recent_activity_30d"],
        "has_recent_activity_60d": activity_stats["has_recent_activity_60d"],
        "has_recent_effective_contact_7d": activity_stats["has_recent_effective_contact_7d"],
        "has_recent_effective_contact_30d": activity_stats["has_recent_effective_contact_30d"],
        "has_recent_effective_contact_60d": activity_stats["has_recent_effective_contact_60d"],
        "is_open": is_open,
        "is_won": is_won,
        "is_lost": is_lost,
        "is_stale": is_stale,
        "is_stale_45d": stale_45d,
        "is_unattended": is_unattended,
        "unattended_reason": unattended_reason,
        "alert_reason": alert_reason,
        "is_unknown_pipeline": is_unknown_pipeline,
        "is_unknown_brand": is_unknown_brand,
        "is_unknown_zone": is_unknown_zone,
        "is_unknown_stage": is_unknown_stage,
        "stale_reason": stale_reason,
        "data_completeness_score": completeness,
        "activity_data_status": "synced",
        "stage_history_status": history_stats["stage_history_status"],
        "metadata_snapshot_at": config.metadata_snapshot_at,
        "field_mapping_version": config.field_mapping_version,
        "dimension_mapping_version": config.dimension_mapping_version,
        "calculated_at": now.isoformat(),
    }


def _resolve_owner_from_activities(activities: list[dict[str, Any]]) -> str | None:
    counts: Counter[str] = Counter()
    for item in activities:
        oid = item.get("hubspot_owner_id")
        if not oid:
            oid = (item.get("properties") or {}).get("hubspot_owner_id")
        normalized = _normalize_owner_id(oid)
        if normalized:
            counts[normalized] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _resolve_brand(deal: dict[str, Any], config: HubSpotConfigStore, pipeline_id: str | None) -> tuple[str, str]:
    brand, source = config.resolve_deal_brand(deal)
    label = config.brand_label(brand)
    if source in ("deal_property", "deal_model", "pipeline_mapping", "stored"):
        return brand, label
    if pipeline_id:
        mapped = config._resolve_dimension("brand", "pipeline_id", pipeline_id)
        if mapped:
            return mapped, config.brand_label(mapped)
    return brand, label


def _aggregate_activities(
    activities: list[dict[str, Any]],
    *,
    config: HubSpotConfigStore,
    now: datetime,
    lookback_days: int,
    created_at: datetime | None,
) -> dict[str, Any]:
    window_start = now - timedelta(days=lookback_days) if lookback_days > 0 else None
    timestamps: list[datetime] = []
    effective_ts: list[datetime] = []
    call_ts: list[datetime] = []
    comm_ts: list[datetime] = []
    counts = {
        "call_count": 0,
        "completed_call_count": 0,
        "communication_count": 0,
        "meeting_count": 0,
        "completed_meeting_count": 0,
        "note_count": 0,
    }

    for item in activities:
        activity_type = item.get("activity_type")
        if activity_type in INTERNAL_TYPES:
            continue
        ts = parse_hubspot_datetime(item.get("activity_timestamp"))
        if not ts:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if window_start and ts < window_start:
            continue
        timestamps.append(ts)
        props = item.get("properties") or {}

        if activity_type == "calls":
            counts["call_count"] += 1
            call_ts.append(ts)
            from app.services.deal_analytics.contact_classification import classify_call

            call_cls = classify_call(props, config=config)
            if call_cls.is_effective_for_builder:
                counts["completed_call_count"] += 1
                effective_ts.append(ts)
        elif activity_type == "communications":
            counts["communication_count"] += 1
            comm_ts.append(ts)
            effective_ts.append(ts)
        elif activity_type == "meetings":
            counts["meeting_count"] += 1
            if item.get("meeting_completed"):
                counts["completed_meeting_count"] += 1
                effective_ts.append(ts)

    for item in activities:
        if item.get("activity_type") != "notes":
            continue
        ts = parse_hubspot_datetime(item.get("activity_timestamp"))
        if not ts:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if window_start and ts < window_start:
            continue
        counts["note_count"] += 1
        timestamps.append(ts)

    timestamps.sort()
    effective_ts.sort()
    last_activity = timestamps[-1] if timestamps else None
    last_effective = effective_ts[-1] if effective_ts else None
    days_since = _days_between(last_activity, now) if last_activity else None
    days_since_effective = _days_between(last_effective, now) if last_effective else None

    first_response_minutes = None
    if created_at and effective_ts:
        first_response_minutes = _minutes_between(created_at, effective_ts[0])

    return {
        "activity_count": len(timestamps),
        "effective_contact_count": len(effective_ts),
        "has_activity": len(timestamps) > 0,
        "has_effective_contact": len(effective_ts) > 0,
        "first_activity_at": timestamps[0].isoformat() if timestamps else None,
        "last_activity_at": last_activity.isoformat() if last_activity else None,
        "first_effective_contact_at": effective_ts[0].isoformat() if effective_ts else None,
        "last_effective_contact_at": last_effective.isoformat() if last_effective else None,
        "first_response_minutes": first_response_minutes,
        "days_since_last_activity": days_since,
        "days_since_effective_contact": days_since_effective,
        "has_recent_activity_7d": any(ts >= now - timedelta(days=7) for ts in timestamps),
        "has_recent_activity_30d": any(ts >= now - timedelta(days=30) for ts in timestamps),
        "has_recent_activity_60d": any(ts >= now - timedelta(days=60) for ts in timestamps),
        "has_recent_effective_contact_7d": any(ts >= now - timedelta(days=7) for ts in effective_ts),
        "has_recent_effective_contact_30d": any(ts >= now - timedelta(days=30) for ts in effective_ts),
        "has_recent_effective_contact_60d": any(ts >= now - timedelta(days=60) for ts in effective_ts),
        "last_call_at": call_ts[-1].isoformat() if call_ts else None,
        "last_communication_at": comm_ts[-1].isoformat() if comm_ts else None,
        **counts,
    }


def _empty_task_stats() -> dict[str, Any]:
    return {
        "task_count": 0,
        "open_task_count": 0,
        "completed_task_count": 0,
        "overdue_task_count": 0,
        "tasks_due_next_7d": 0,
        "oldest_overdue_task_days": None,
        "has_overdue_tasks": False,
        "has_future_task": False,
        "task_data_status": "partial",
        "reassigned_lead_task_count": 0,
    }


def _aggregate_tasks(
    activities: list[dict[str, Any]],
    *,
    config: HubSpotConfigStore,
    now: datetime,
) -> dict[str, Any]:
    open_count = completed_count = overdue_count = due_next_7d = 0
    oldest_overdue_days: int | None = None
    has_future = False
    total = 0
    reassigned_lead_count = 0

    for item in activities:
        if item.get("activity_type") != "tasks":
            continue
        if is_reassigned_lead_activity(item):
            reassigned_lead_count += 1
            continue
        total += 1
        props = item.get("properties") or {}
        status = props.get("hs_task_status")
        if config.is_task_completed(status):
            completed_count += 1
            continue
        open_count += 1
        due_raw = props.get("hs_task_due_date") or item.get("activity_timestamp")
        due_at = parse_hubspot_datetime(due_raw)
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if due_at:
            if due_at < now:
                overdue_count += 1
                days_overdue = _days_between(due_at, now)
                if days_overdue is not None:
                    oldest_overdue_days = max(oldest_overdue_days or 0, days_overdue)
            elif due_at <= now + timedelta(days=7):
                due_next_7d += 1
                has_future = True
        else:
            has_future = has_future or False

    for item in activities:
        if item.get("activity_type") != "tasks":
            continue
        if is_reassigned_lead_activity(item):
            continue
        props = item.get("properties") or {}
        if config.is_task_completed(props.get("hs_task_status")):
            continue
        due_raw = props.get("hs_task_due_date")
        due_at = parse_hubspot_datetime(due_raw)
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if due_at and due_at > now + timedelta(days=7):
            has_future = True

    return {
        "task_count": total,
        "open_task_count": open_count,
        "completed_task_count": completed_count,
        "overdue_task_count": overdue_count,
        "tasks_due_next_7d": due_next_7d,
        "oldest_overdue_task_days": oldest_overdue_days,
        "has_overdue_tasks": overdue_count > 0,
        "has_future_task": has_future,
        "task_data_status": "partial" if total == 0 else "available",
        "reassigned_lead_task_count": reassigned_lead_count,
    }


def _unattended_status(
    *,
    is_open: bool,
    has_recent_activity_30d: bool,
    has_recent_effective_contact_30d: bool,
    has_overdue_tasks: bool,
    has_future_task: bool,
) -> tuple[bool, str | None]:
    if not is_open:
        return False, None
    reasons: list[str] = []
    if not has_recent_activity_30d:
        reasons.append("no_recent_activity")
    if not has_recent_effective_contact_30d:
        reasons.append("no_recent_effective_contact")
    if has_overdue_tasks:
        reasons.append("overdue_tasks")
    if not has_future_task:
        reasons.append("no_future_task")
    if not reasons:
        return False, None
    if len(reasons) > 1:
        return True, "multiple_reasons"
    return True, reasons[0]


def _alert_reason(
    is_stale: bool,
    stale_reason: str | None,
    is_unattended: bool,
    unattended_reason: str | None,
) -> str | None:
    if is_stale and is_unattended:
        return f"stale:{stale_reason};unattended:{unattended_reason}"
    if is_stale:
        return stale_reason
    if is_unattended:
        return unattended_reason
    return None


def _aggregate_stage_history(
    history: list[dict[str, Any]],
    pipeline_id: str | None,
    stage_id: str | None,
) -> dict[str, Any]:
    if not history:
        return {
            "stage_change_count": 0,
            "stages_visited_count": 0,
            "days_in_current_stage": None,
            "stage_history_status": "partial",
        }

    stages_visited = {str(h.get("stage_id")) for h in history if h.get("stage_id")}
    current = next((h for h in history if h.get("is_current")), None)
    days_in_stage = None
    if current and current.get("entered_at"):
        entered = parse_hubspot_datetime(current["entered_at"])
        if entered:
            days_in_stage = _days_between(entered, utc_now())

    return {
        "stage_change_count": max(0, len(history) - 1),
        "stages_visited_count": len(stages_visited),
        "days_in_current_stage": days_in_stage,
        "stage_history_status": "available",
    }


def _stale_reason(
    *,
    is_open: bool,
    days_since_last: int | None,
    days_in_stage: int | None,
    stale_activity_days: int,
    stale_stage_days: int,
    has_activity: bool,
) -> str | None:
    if not is_open:
        return None
    no_activity = not has_activity or (
        days_since_last is not None and days_since_last >= stale_activity_days
    )
    long_stage = days_in_stage is not None and days_in_stage >= stale_stage_days
    if no_activity and long_stage:
        return "both"
    if no_activity:
        return "no_recent_activity"
    if long_stage:
        return "too_long_in_stage"
    return None


def _completeness_score(**flags: bool) -> float:
    total = len(flags)
    if total == 0:
        return 0.0
    return round(sum(1 for v in flags.values() if v) / total * 100, 1)
