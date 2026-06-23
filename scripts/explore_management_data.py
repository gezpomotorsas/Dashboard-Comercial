#!/usr/bin/env python3
"""Exploración de solo lectura: datos gerenciales HubSpot vs Supabase.

No inicia sincronizaciones ni modifica registros remotos.
Genera informes JSON y Markdown sin datos personales ni secretos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.clients.hubspot_exceptions import HubSpotClientError
from app.clients.supabase import get_supabase_client
from app.config import get_settings
from app.constants.activities import ACTIVITY_SYNC_PROPERTIES, ACTIVITY_TABLE_MAP, SENSITIVE_ACTIVITY_PROPERTY_KEYS
from app.constants.crm_sync import DEAL_SYNC_PROPERTIES
from app.repositories.supabase_repository import SupabaseRepository

BOGOTA = ZoneInfo("America/Bogota")
DEFAULT_JSON = ROOT / "scripts" / "management_data_exploration_report.json"
DEFAULT_MD = ROOT / "scripts" / "management_data_exploration_summary.md"

CRM_OBJECTS = ("deals", "calls", "communications", "meetings", "tasks", "notes", "emails", "contacts")
ACTIVITY_TYPES = ("calls", "communications", "meetings", "tasks", "notes", "emails")

ASSOCIATION_PAIRS = [
    ("deal", "call"),
    ("deal", "communication"),
    ("deal", "meeting"),
    ("deal", "task"),
    ("deal", "note"),
    ("deal", "email"),
]

SCOPE_PROBE_PATHS: dict[str, tuple[str, str]] = {
    "crm.objects.deals.read": ("GET", "/crm/v3/objects/deals?limit=1"),
    "crm.objects.contacts.read": ("GET", "/crm/v3/objects/contacts?limit=1"),
    "crm.objects.calls.read": ("GET", "/crm/v3/objects/calls?limit=1"),
    "crm.objects.communications.read": ("GET", "/crm/v3/objects/communications?limit=1"),
    "crm.objects.meetings.read": ("GET", "/crm/v3/objects/meetings?limit=1"),
    "crm.objects.tasks.read": ("GET", "/crm/v3/objects/tasks?limit=1"),
    "crm.objects.notes.read": ("GET", "/crm/v3/objects/notes?limit=1"),
    "crm.schemas.deals.read": ("GET", "/crm/v3/properties/deals?limit=1"),
    "crm.schemas.contacts.read": ("GET", "/crm/v3/properties/contacts?limit=1"),
    "owners": ("GET", "/crm/v3/owners?limit=1"),
}

DEAL_FIELDS_SPEC: list[tuple[str, str, str]] = [
    ("deal_id", "hs_object_id", "standard"),
    ("deal_name", "dealname", "standard"),
    ("pipeline", "pipeline", "standard"),
    ("stage", "dealstage", "standard"),
    ("owner", "hubspot_owner_id", "standard"),
    ("brand_custom", "marca", "custom"),
    ("zone", "zona", "custom"),
    ("city", "ciudad", "custom"),
    ("department", "departamento", "custom"),
    ("model", "modelo_solicitado", "custom"),
    ("source", "hs_analytics_source", "standard"),
    ("amount", "amount", "standard"),
    ("created_at", "createdate", "standard"),
    ("close_date", "closedate", "standard"),
    ("last_modified", "hs_lastmodifieddate", "standard"),
    ("closed_won", "hs_is_closed_won", "standard"),
    ("closed_lost", "hs_is_closed_lost", "standard"),
    ("owner_assigned_date", "hubspot_owner_assigneddate", "standard"),
    ("last_activity", "notes_last_updated", "standard"),
    ("num_activities", "num_notes", "standard"),
]

SENSITIVE_KEYS = SENSITIVE_ACTIVITY_PROPERTY_KEYS | frozenset(
    {"email", "firstname", "lastname", "phone", "dealname", "hs_call_body", "hs_note_body"}
)

ZONE_CANDIDATE_PATTERNS = re.compile(
    r"zona|regional|ciudad|departamento|sede|concesionario|ubicaci|location|city|team",
    re.I,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _redact_properties(props: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in props.items():
        if key in SENSITIVE_KEYS:
            redacted[key] = "<redacted>"
        elif isinstance(value, str) and len(value) > 80:
            redacted[key] = f"<string len={len(value)}>"
        else:
            redacted[key] = value
    return redacted


def _count_key_column(table: str) -> str:
  if table == "sync_cursors":
    return "object_type"
  return "id"


def count_table(table: str, *, filters: list[tuple[str, str, Any]] | None = None) -> int:
    client = get_supabase_client()
    query = client.table(table).select(_count_key_column(table), count="exact").limit(0)
    for col, op, val in filters or []:
        if op == "eq":
            query = query.eq(col, val)
        elif op == "is":
            query = query.is_(col, val)
        elif op == "not.is":
            query = query.not_.is_(col, val)
        elif op == "gt":
            query = query.gt(col, val)
    return query.execute().count or 0


def fetch_page(table: str, columns: str, offset: int, page_size: int = 1000) -> list[dict]:
    return (
        get_supabase_client()
        .table(table)
        .select(columns)
        .range(offset, offset + page_size - 1)
        .execute()
        .data
        or []
    )


def load_all_rows(table: str, columns: str, *, max_rows: int | None = None) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        chunk = fetch_page(table, columns, offset)
        if not chunk:
            break
        rows.extend(chunk)
        if max_rows and len(rows) >= max_rows:
            return rows[:max_rows]
        if len(chunk) < 1000:
            break
        offset += 1000
    return rows


def table_date_bounds(table: str, ts_col: str) -> dict[str, str | None]:
    rows = load_all_rows(table, ts_col, max_rows=5000)
    values = [r.get(ts_col) for r in rows if r.get(ts_col)]
    if not values:
        return {"min": None, "max": None, "sampled_rows": len(rows)}
    return {"min": min(values), "max": max(values), "sampled_rows": len(rows)}


def duplicate_hubspot_ids(table: str) -> int:
    rows = load_all_rows(table, "hubspot_id")
    ids = [str(r["hubspot_id"]) for r in rows if r.get("hubspot_id")]
    return len(ids) - len(set(ids))


def property_metadata(object_type: str, name: str) -> dict[str, Any] | None:
    rows = (
        get_supabase_client()
        .table("hubspot_properties")
        .select("name,label,type,field_type,options,description")
        .eq("object_type", object_type)
        .eq("name", name)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def coverage_in_properties(
    table: str,
    property_name: str,
    *,
    sample_limit: int = 5000,
) -> dict[str, Any]:
    rows = load_all_rows(table, "properties", max_rows=sample_limit)
    total = len(rows)
    populated = 0
    for row in rows:
        val = (row.get("properties") or {}).get(property_name)
        if val not in (None, "", "0", "false"):
            populated += 1
    return {
        "sample_size": total,
        "populated": populated,
        "coverage_pct": _pct(populated, total),
    }


def owner_coverage_deals() -> dict[str, Any]:
    rows = load_all_rows("hubspot_deals", "properties,hubspot_id")
    owner_ids = set(
        str(r["hubspot_id"])
        for r in (
            get_supabase_client()
            .table("hubspot_owners")
            .select("hubspot_id")
            .limit(5000)
            .execute()
            .data
            or []
        )
    )
    with_owner = without_owner = orphan_owner = 0
    for row in rows:
        owner = (row.get("properties") or {}).get("hubspot_owner_id")
        if owner in (None, ""):
            without_owner += 1
        else:
            with_owner += 1
            if str(owner) not in owner_ids:
                orphan_owner += 1
    return {
        "total": len(rows),
        "with_owner": with_owner,
        "without_owner": without_owner,
        "orphan_owner_not_in_metadata": orphan_owner,
        "with_owner_pct": _pct(with_owner, len(rows)),
    }


def activity_owner_stats(activity_type: str) -> dict[str, Any]:
    table = ACTIVITY_TABLE_MAP[activity_type]
    use_cols = SupabaseRepository._activity_index_columns_ready()
    cols = "hubspot_owner_id,activity_timestamp,properties" if use_cols else "properties"
    rows = load_all_rows(table, cols)
    with_owner = without_owner = with_ts = 0
    for row in rows:
        if use_cols:
            owner = row.get("hubspot_owner_id")
            ts = row.get("activity_timestamp")
        else:
            props = row.get("properties") or {}
            owner = props.get("hubspot_owner_id")
            ts = props.get("hs_timestamp")
        if owner not in (None, ""):
            with_owner += 1
        else:
            without_owner += 1
        if ts:
            with_ts += 1
    return {
        "total": len(rows),
        "with_owner": with_owner,
        "without_owner": without_owner,
        "with_timestamp": with_ts,
        "index_columns_ready": use_cols,
    }


def association_stats() -> dict[str, Any]:
    client = get_supabase_client()
    existing: dict[str, set[str]] = {
        "deals": {str(r["hubspot_id"]) for r in load_all_rows("hubspot_deals", "hubspot_id")},
        "contacts": {str(r["hubspot_id"]) for r in load_all_rows("hubspot_contacts", "hubspot_id")},
    }
    for act, table in ACTIVITY_TABLE_MAP.items():
        existing[act] = {str(r["hubspot_id"]) for r in load_all_rows(table, "hubspot_id")}

    result: dict[str, Any] = {"by_activity_type": {}, "pairs": {}}
    for act in ACTIVITY_TYPES:
        total_acts = len(existing.get(act, set()))
        deal_assoc = contact_assoc = no_assoc = missing_deal = missing_contact = 0
        linked_acts: set[str] = set()
        offset = 0
        while True:
            rows = (
                client.table("hubspot_associations")
                .select("from_object_type,from_hubspot_id,to_object_type,to_hubspot_id")
                .eq("is_active", True)
                .or_(f"to_object_type.eq.{act},from_object_type.eq.{act}")
                .range(offset, offset + 999)
                .execute()
                .data
                or []
            )
            if not rows:
                break
            for row in rows:
                f_type, f_id = row["from_object_type"], str(row["from_hubspot_id"])
                t_type, t_id = row["to_object_type"], str(row["to_hubspot_id"])
                act_id: str | None = None
                deal_id: str | None = None
                contact_id: str | None = None
                if t_type == act:
                    act_id = t_id
                    if f_type == "deals":
                        deal_id = f_id
                    elif f_type == "contacts":
                        contact_id = f_id
                elif f_type == act:
                    act_id = f_id
                    if t_type == "deals":
                        deal_id = t_id
                    elif t_type == "contacts":
                        contact_id = t_id
                if not act_id:
                    continue
                linked_acts.add(act_id)
                if deal_id:
                    deal_assoc += 1
                    if deal_id not in existing["deals"]:
                        missing_deal += 1
                if contact_id:
                    contact_assoc += 1
                    if contact_id not in existing["contacts"]:
                        missing_contact += 1
            offset += 1000
            if len(rows) < 1000:
                break
        no_assoc = max(0, total_acts - len(linked_acts))
        result["by_activity_type"][act] = {
            "total_activities": total_acts,
            "with_deal_association_rows": deal_assoc,
            "with_contact_association_rows": contact_assoc,
            "activities_without_any_association": no_assoc,
            "associations_to_missing_deal": missing_deal,
            "associations_to_missing_contact": missing_contact,
        }

    from_map = {"deal": "deals", "contact": "contacts"}
    to_map = {
        "call": "calls",
        "communication": "communications",
        "meeting": "meetings",
        "task": "tasks",
        "note": "notes",
        "email": "emails",
    }
    for from_t, to_t in ASSOCIATION_PAIRS:
        n = (
            client.table("hubspot_associations")
            .select("id", count="exact")
            .eq("is_active", True)
            .eq("from_object_type", from_map.get(from_t, from_t))
            .eq("to_object_type", to_map.get(to_t, to_t))
            .limit(0)
            .execute()
            .count
            or 0
        )
        result["pairs"][f"{from_t}->{to_t}"] = n
    return result


def call_duration_stats() -> dict[str, Any]:
    rows = load_all_rows("hubspot_calls", "properties,activity_timestamp")
    durations: list[float] = []
    null_count = zero_count = negative = 0
    for row in rows:
        raw = (row.get("properties") or {}).get("hs_call_duration")
        val = _safe_float(raw)
        if val is None:
            null_count += 1
            continue
        if val == 0:
            zero_count += 1
        if val < 0:
            negative += 1
        durations.append(val)
    stats: dict[str, Any] = {
        "count": len(rows),
        "null_count": null_count,
        "zero_count": zero_count,
        "negative_count": negative,
        "parsed_count": len(durations),
    }
    if durations:
        sorted_d = sorted(durations)
        stats.update(
            {
                "minimum": sorted_d[0],
                "maximum": sorted_d[-1],
                "median": statistics.median(sorted_d),
                "percentile_95": sorted_d[min(len(sorted_d) - 1, math.ceil(0.95 * len(sorted_d)) - 1)],
                "mean": round(statistics.mean(sorted_d), 2),
            }
        )
        # Heuristic: if median < 1000 and max < 7200, likely seconds; if median > 10000, likely ms
        med = stats["median"]
        if med > 10000:
            stats["inferred_unit"] = "milliseconds_likely"
        elif med < 7200:
            stats["inferred_unit"] = "seconds_likely"
        else:
            stats["inferred_unit"] = "ambiguous"
    meta = property_metadata("calls", "hs_call_duration")
    if meta:
        stats["metadata_type"] = meta.get("type")
        stats["metadata_label"] = meta.get("label")
    return stats


def communication_channel_breakdown() -> dict[str, Any]:
    rows = load_all_rows("hubspot_communications", "properties")
    channels: Counter[str] = Counter()
    with_body = without_body = 0
    for row in rows:
        props = row.get("properties") or {}
        ch = str(props.get("hs_communication_channel_type") or "<empty>")
        channels[ch] += 1
        body = props.get("hs_communication_body")
        if body not in (None, ""):
            with_body += 1
        else:
            without_body += 1
    return {
        "total": len(rows),
        "channel_counts": dict(channels.most_common(20)),
        "with_body": with_body,
        "without_body": without_body,
        "body_coverage_pct": _pct(with_body, len(rows)),
    }


def task_status_breakdown() -> dict[str, Any]:
    rows = load_all_rows("hubspot_tasks", "properties,activity_timestamp")
    statuses: Counter[str] = Counter()
    with_due = without_due = 0
    now = datetime.now(UTC)
    overdue = open_tasks = completed = 0
    for row in rows:
        props = row.get("properties") or {}
        status = str(props.get("hs_task_status") or "<empty>")
        statuses[status] += 1
        due_raw = props.get("hs_task_due_date")
        if due_raw not in (None, ""):
            with_due += 1
            try:
                due_dt = datetime.fromisoformat(str(due_raw).replace("Z", "+00:00"))
                if status.upper() not in ("COMPLETED",) and due_dt < now:
                    overdue += 1
                if status.upper() not in ("COMPLETED",):
                    open_tasks += 1
                else:
                    completed += 1
            except ValueError:
                pass
        else:
            without_due += 1
    meta = property_metadata("tasks", "hs_task_status")
    options = []
    if meta and meta.get("options"):
        options = [
            {"value": o.get("value"), "label": o.get("label")}
            for o in meta["options"]
            if isinstance(o, dict)
        ]
    return {
        "total": len(rows),
        "status_counts": dict(statuses.most_common()),
        "with_due_date": with_due,
        "without_due_date": without_due,
        "overdue_open_estimate": overdue,
        "open_estimate": open_tasks,
        "completed_estimate": completed,
        "status_options_from_metadata": options,
        "due_date_property": "hs_task_due_date",
    }


def _table_for_object_type(object_type: str) -> str | None:
    mapping = {
        "deals": "hubspot_deals",
        "contacts": "hubspot_contacts",
        "owners": "hubspot_owners",
    }
    return mapping.get(object_type)


def zone_candidates() -> list[dict[str, Any]]:
    props = (
        get_supabase_client()
        .table("hubspot_properties")
        .select("object_type,name,label,type,field_type,options")
        .in_("object_type", ["deals", "contacts", "owners"])
        .limit(5000)
        .execute()
        .data
        or []
    )
    candidates: list[dict[str, Any]] = []
    for prop in props:
        text = f"{prop.get('name','')} {prop.get('label','')}"
        if not ZONE_CANDIDATE_PATTERNS.search(text):
            continue
        table = _table_for_object_type(prop["object_type"])
        if not table:
            continue
        cov = coverage_in_properties(table, prop["name"], sample_limit=3000)
        candidates.append(
            {
                "object_type": prop["object_type"],
                "name": prop["name"],
                "label": prop.get("label"),
                "type": prop.get("type"),
                "field_type": prop.get("field_type"),
                "options_count": len(prop.get("options") or []),
                "coverage_in_sample": cov,
            }
        )
    return sorted(candidates, key=lambda x: (-(x["coverage_in_sample"].get("coverage_pct") or 0), x["name"]))


def weekly_series(table: str, ts_col: str) -> dict[str, Any]:
    rows = load_all_rows(table, ts_col)
    weeks: Counter[str] = Counter()
    for row in rows:
        raw = row.get(ts_col)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            week_start = (dt.astimezone(BOGOTA).date() - timedelta(days=dt.weekday())).isoformat()
            weeks[week_start] += 1
        except ValueError:
            continue
    if not weeks:
        return {"min_week": None, "max_week": None, "weeks_with_data": 0, "weeks_empty": None, "coverage_pct": None}
    min_w = min(weeks)
    max_w = max(weeks)
    start = datetime.fromisoformat(min_w).date()
    end = datetime.fromisoformat(max_w).date()
    total_weeks = ((end - start).days // 7) + 1
    with_data = len(weeks)
    empty = max(0, total_weeks - with_data)
    return {
        "min_week": min_w,
        "max_week": max_w,
        "total_weeks_span": total_weeks,
        "weeks_with_data": with_data,
        "weeks_empty": empty,
        "coverage_pct": _pct(with_data, total_weeks),
        "total_records": sum(weeks.values()),
    }


def deal_field_coverage() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label, prop_name, source in DEAL_FIELDS_SPEC:
        meta = property_metadata("deals", prop_name)
        cov = coverage_in_properties("hubspot_deals", prop_name)
        in_sync = prop_name in DEAL_SYNC_PROPERTIES
        results.append(
            {
                "analytical_label": label,
                "hubspot_property": prop_name,
                "source": source,
                "type": (meta or {}).get("type"),
                "label": (meta or {}).get("label"),
                "in_supabase_properties_json": True,
                "in_deal_sync_properties": in_sync,
                "coverage_pct": cov.get("coverage_pct"),
                "sample_size": cov.get("sample_size"),
            }
        )
    return results


def explore_database(sample_size: int) -> dict[str, Any]:
    tables = {
        "hubspot_deals": "created_at_hubspot",
        "hubspot_contacts": "created_at_hubspot",
        "hubspot_calls": "activity_timestamp",
        "hubspot_communications": "activity_timestamp",
        "hubspot_meetings": "activity_timestamp",
        "hubspot_tasks": "activity_timestamp",
        "hubspot_notes": "activity_timestamp",
        "hubspot_emails": "activity_timestamp",
        "hubspot_owners": "synced_at",
        "hubspot_associations": "synced_at",
        "hubspot_properties": "synced_at",
        "sync_runs": "started_at",
        "sync_errors": "created_at",
        "sync_cursors": "updated_at",
    }
    counts = {t: count_table(t) for t in tables}
    date_bounds = {}
    for t, col in tables.items():
        if t in ACTIVITY_TABLE_MAP.values() or t.startswith("hubspot_"):
            try:
                date_bounds[t] = table_date_bounds(t, col)
            except Exception as exc:
                date_bounds[t] = {"error": type(exc).__name__}

    owners = load_all_rows("hubspot_owners", "hubspot_id,archived", max_rows=5000)
    active_owners = sum(1 for o in owners if not o.get("archived"))
    archived_owners = sum(1 for o in owners if o.get("archived"))

    return {
        "table_counts": counts,
        "date_bounds": date_bounds,
        "duplicate_hubspot_ids": {t: duplicate_hubspot_ids(t) for t in ACTIVITY_TABLE_MAP.values()},
        "deal_field_coverage": deal_field_coverage(),
        "deal_owners": owner_coverage_deals(),
        "activity_owners": {a: activity_owner_stats(a) for a in ACTIVITY_TYPES},
        "call_duration": call_duration_stats(),
        "communications": communication_channel_breakdown(),
        "tasks": task_status_breakdown(),
        "zone_candidates": zone_candidates()[:25],
        "owners_summary": {
            "total": len(owners),
            "active": active_owners,
            "archived": archived_owners,
        },
        "settings": {
            "activity_sync_lookback_days": get_settings().activity_sync_lookback_days,
            "association_sync_lookback_days": get_settings().association_sync_lookback_days,
            "task_sync_full_history": get_settings().task_sync_full_history,
            "business_timezone": get_settings().business_timezone,
        },
    }


async def fetch_token_scopes(client) -> list[str]:
    token = get_settings().hubspot_access_token.get_secret_value()
    try:
        payload = await client.get(f"/oauth/v1/access-tokens/{token}")
        return list(payload.get("scopes") or [])
    except HubSpotClientError:
        return []


async def probe_scope(client, scope: str, method: str, path: str) -> dict[str, Any]:
    try:
        if method == "GET":
            await client.get(path)
        else:
            await client.post(path, json_body={})
        return {"scope": scope, "http_status": 200, "accessible": True, "error_summary": None}
    except HubSpotClientError as exc:
        status = getattr(exc, "status_code", None) or 0
        msg = str(exc)[:120]
        return {
            "scope": scope,
            "http_status": status,
            "accessible": False,
            "error_summary": msg,
        }


async def api_object_total(client, object_type: str) -> int | None:
    try:
        body = {
            "filterGroups": [],
            "limit": 1,
        }
        payload = await client.post(f"/crm/v3/objects/{object_type}/search", json_body=body)
        total = payload.get("total")
        return int(total) if total is not None else None
    except HubSpotClientError:
        return None


async def sample_objects(
    client,
    object_type: str,
    properties: list[str],
    *,
    limit: int,
    properties_with_history: list[str] | None = None,
    associations: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "limit": min(limit, 10),
        "properties": ",".join(properties),
    }
    if properties_with_history:
        params["propertiesWithHistory"] = ",".join(properties_with_history)
    if associations:
        params["associations"] = ",".join(associations)
    payload = await client.get(f"/crm/v3/objects/{object_type}", params=params)
    results = payload.get("results") or []
    sanitized = []
    for item in results[:limit]:
        props = _redact_properties(item.get("properties") or {})
        entry: dict[str, Any] = {
            "id": str(item.get("id")),
            "properties": props,
            "has_associations": bool(item.get("associations")),
        }
        if properties_with_history and "propertiesWithHistory" in item:
            hist = item["propertiesWithHistory"]
            entry["history_keys"] = list(hist.keys()) if isinstance(hist, dict) else []
            if isinstance(hist, dict) and "dealstage" in hist:
                stages = hist["dealstage"]
                entry["dealstage_history_entries"] = len(stages) if isinstance(stages, list) else 0
        sanitized.append(entry)
    return {
        "sample_count": len(sanitized),
        "samples": sanitized,
        "paging_has_more": bool((payload.get("paging") or {}).get("next")),
    }


async def test_stage_history(client, sample_size: int) -> dict[str, Any]:
    result = await sample_objects(
        client,
        "deals",
        list(DEAL_SYNC_PROPERTIES),
        limit=sample_size,
        properties_with_history=["dealstage"],
    )
    with_history = sum(1 for s in result["samples"] if s.get("dealstage_history_entries", 0) > 0)
    return {
        "endpoint": "GET /crm/v3/objects/deals?propertiesWithHistory=dealstage",
        "project_sync_requests_history": False,
        "sample_size": len(result["samples"]),
        "deals_with_stage_history": with_history,
        "coverage_in_sample_pct": _pct(with_history, len(result["samples"])),
        "samples_meta": [
            {
                "id": s["id"],
                "history_entries": s.get("dealstage_history_entries", 0),
            }
            for s in result["samples"]
        ],
    }


async def explore_api(sample_size: int, object_filter: str | None) -> dict[str, Any]:
    client = await get_hubspot_client()
    api_reachable = False
    token_scopes: list[str] = []
    try:
        token_scopes = await fetch_token_scopes(client)
    except HubSpotClientError:
        token_scopes = []

    scope_tests = []
    for scope, (method, path) in SCOPE_PROBE_PATHS.items():
        result = await probe_scope(client, scope, method, path)
        scope_tests.append(result)
        if result.get("accessible"):
            api_reachable = True

    missing_scopes = [
        t["scope"]
        for t in scope_tests
        if not t["accessible"] and t.get("http_status") in (401, 403)
    ]

    api_totals: dict[str, Any] = {}
    for obj in CRM_OBJECTS:
        if object_filter and obj != object_filter:
            continue
        try:
            estimated = await api_object_total(client, obj)
        except HubSpotClientError as exc:
            estimated = None
            api_totals[obj] = {
                "estimated_total": None,
                "error": str(exc)[:120],
            }
            continue
        api_totals[obj] = {
            "estimated_total": estimated,
            "note": "estimated via CRM search API total field",
        }

    objects_detail: dict[str, Any] = {}
    activity_props = ACTIVITY_SYNC_PROPERTIES

    if not object_filter or object_filter == "deals":
        try:
            objects_detail["deals"] = await sample_objects(
                client, "deals", list(DEAL_SYNC_PROPERTIES), limit=sample_size
            )
            api_reachable = True
        except HubSpotClientError as exc:
            objects_detail["deals"] = {"error": str(exc)[:120]}
    for act in ACTIVITY_TYPES:
        if object_filter and act != object_filter:
            continue
        props = list(activity_props.get(act, ()))
        try:
            objects_detail[act] = await sample_objects(
                client, act, props, limit=sample_size, associations=["deals", "contacts"]
            )
            api_reachable = True
        except HubSpotClientError as exc:
            objects_detail[act] = {"error": str(exc)[:120]}

    stage_history: dict[str, Any] = {"error": "not_run"}
    try:
        stage_history = await test_stage_history(client, min(sample_size, 10))
        api_reachable = True
    except HubSpotClientError as exc:
        stage_history = {"error": str(exc)[:120]}

    comm_body_test: dict[str, Any] = {"accessible": False}
    try:
        comm_sample = await sample_objects(
            client,
            "communications",
            ["hs_communication_body", "hs_communication_channel_type"],
            limit=3,
        )
        has_body_key = any(
            "hs_communication_body" in (s.get("properties") or {})
            for s in comm_sample.get("samples", [])
        )
        comm_body_test = {
            "accessible": has_body_key,
            "http_status": 200,
            "note": "property key present in response; values redacted",
        }
        api_reachable = True
    except HubSpotClientError as exc:
        comm_body_test = {
            "accessible": False,
            "http_status": getattr(exc, "status_code", None),
            "error_summary": str(exc)[:120],
        }

    await close_hubspot_client()

    return {
        "api_reachable": api_reachable,
        "token_scopes_detected": token_scopes,
        "scope_probes": scope_tests,
        "missing_scopes": missing_scopes,
        "api_estimated_totals": api_totals,
        "object_samples": objects_detail,
        "stage_history_test": stage_history,
        "communication_body_test": comm_body_test,
    }


def build_metrics_availability(db: dict, api: dict | None) -> list[dict[str, Any]]:
    """Clasificación heurística de métricas gerenciales."""
    deals_count = db["table_counts"].get("hubspot_deals", 0)
    calls_count = db["table_counts"].get("hubspot_calls", 0)
    comm_count = db["table_counts"].get("hubspot_communications", 0)
    tasks = db.get("tasks", {})
    call_dur = db.get("call_duration", {})
    lookback = db["settings"]["activity_sync_lookback_days"]
    task_full = db["settings"]["task_sync_full_history"]

    def entry(name: str, status: str, source: str, coverage: str, blocker: str, action: str) -> dict:
        return {
            "metric": name,
            "status": status,
            "source": source,
            "coverage": coverage,
            "blocker": blocker,
            "next_action": action,
        }

    metrics = [
        entry("Negocios totales", "DISPONIBLE", "hubspot_deals", f"{deals_count} registros", "Ninguno", "Usar directamente"),
        entry(
            "Cantidad de llamadas",
            "DISPONIBLE" if calls_count else "DISPONIBLE CON NUEVA SINCRONIZACIÓN",
            "hubspot_calls",
            f"{calls_count} local ({lookback}d ventana)",
            "Ventana 60d" if lookback < 365 else "Ninguno",
            "Ampliar ventana si se requiere historia",
        ),
        entry(
            "Duración de llamadas",
            "DISPONIBLE PARCIALMENTE",
            "hs_call_duration",
            f"parsed={call_dur.get('parsed_count', 0)}",
            f"Unidad: {call_dur.get('inferred_unit', 'por confirmar')}",
            "Validar unidad y normalizar a segundos",
        ),
        entry(
            "WhatsApp por asesor",
            "DISPONIBLE PARCIALMENTE",
            "hubspot_communications",
            f"{comm_count} mensajes",
            "Sin ID de conversación; ventana 60d",
            "Agrupar por canal y ventana temporal",
        ),
        entry(
            "Tareas vencidas",
            "DISPONIBLE" if task_full else "DISPONIBLE PARCIALMENTE",
            "hubspot_tasks",
            f"overdue_est={tasks.get('overdue_open_estimate', 0)}",
            "Validar hs_task_status contra metadata",
            "Confirmar opciones de estado",
        ),
        entry(
            "Historial de etapas",
            "DISPONIBLE PARCIALMENTE" if api else "POR VALIDAR",
            "Deals propertiesWithHistory",
            str((api or {}).get("stage_history_test", {}).get("coverage_in_sample_pct", "—")) + "% muestra",
            "No sincronizado localmente",
            "Prueba puntual y diseño de extracción",
        ),
        entry(
            "Zona por negocio",
            "DISPONIBLE PARCIALMENTE",
            "Propiedades deals",
            "Cobertura variable",
            "Mapping e inferencia",
            "Priorizar campo zona/ciudad",
        ),
        entry(
            "Negocios sin propietario (dashboard)",
            "DISPONIBLE PARCIALMENTE",
            "hubspot_deals.properties",
            f"{db['deal_owners'].get('with_owner_pct', 0)}% con owner",
            "Owner en JSON no columna indexada",
            "Verificar backfill owner",
        ),
        entry(
            "Predicción semanal",
            "POR VALIDAR",
            "Varias tablas",
            "Ver time_series_readiness",
            "Historia limitada en actividades",
            "Medir semanas y huecos",
        ),
    ]
    return metrics


def build_time_series_readiness(db: dict) -> dict[str, Any]:
    series = {
        "deals_created": weekly_series("hubspot_deals", "created_at_hubspot"),
        "calls": weekly_series("hubspot_calls", "activity_timestamp"),
        "communications": weekly_series("hubspot_communications", "activity_timestamp"),
        "tasks": weekly_series("hubspot_tasks", "activity_timestamp"),
        "meetings": weekly_series("hubspot_meetings", "activity_timestamp"),
    }
    # Won deals approximation from properties would need full scan; use created as proxy
    return series


def api_vs_local_comparison(db: dict, api: dict | None) -> list[dict[str, Any]]:
    rows = []
    mapping = {
        "deals": "hubspot_deals",
        "calls": "hubspot_calls",
        "communications": "hubspot_communications",
        "meetings": "hubspot_meetings",
        "tasks": "hubspot_tasks",
        "notes": "hubspot_notes",
    }
    totals = (api or {}).get("api_estimated_totals", {})
    for obj, table in mapping.items():
        local = db["table_counts"].get(table, 0)
        estimated = (totals.get(obj) or {}).get("estimated_total")
        coverage = _pct(local, estimated) if estimated else None
        if estimated is None:
            action = "Estimar total API o revisar scope"
        elif local >= estimated * 0.9:
            action = "Mantener sync incremental"
        elif local < estimated * 0.5:
            action = "Sincronización adicional (fuera de este script)"
        else:
            action = "Revisar ventana lookback / histórico parcial"
        rows.append(
            {
                "object": obj.capitalize(),
                "api_accessible": bool((api or {}).get("scope_probes")),
                "api_estimated_total": estimated,
                "local_count": local,
                "local_coverage_pct": coverage,
                "action": action,
            }
        )
    return rows


def build_data_quality_issues(db: dict, api: dict | None) -> list[str]:
    issues: list[str] = []
    if db["deal_owners"]["without_owner"] > db["deal_owners"]["with_owner"]:
        issues.append(
            "Más del 50% de negocios locales sin hubspot_owner_id en properties — "
            "puede explicar dashboard sin asesor"
        )
    if db["deal_owners"]["orphan_owner_not_in_metadata"] > 0:
        issues.append(
            f"{db['deal_owners']['orphan_owner_not_in_metadata']} negocios con owner "
            "no presente en hubspot_owners"
        )
    call_dur = db.get("call_duration", {})
    if call_dur.get("null_count", 0) > call_dur.get("parsed_count", 0):
        issues.append("Mayoría de llamadas sin hs_call_duration poblado")
    if db["settings"]["activity_sync_lookback_days"] <= 60:
        issues.append("Actividades limitadas a ventana móvil de 60 días (config ACTIVITY_SYNC_LOOKBACK_DAYS)")
    if api and api.get("stage_history_test", {}).get("project_sync_requests_history") is False:
        issues.append("El sync actual no solicita propertiesWithHistory para dealstage")
    comm = db.get("communications", {})
    if comm.get("total", 0) > 0 and not comm.get("channel_counts"):
        issues.append("Comunicaciones sin hs_communication_channel_type poblado")
    return issues


def build_recommendations(db: dict, api: dict | None, issues: list[str]) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []
    if db["deal_owners"]["with_owner_pct"] and (db["deal_owners"]["with_owner_pct"] or 0) < 80:
        recs.append(
            {
                "priority": "Alta",
                "action": "Validar cobertura de hubspot_owner_id en negocios (backfill si aplica)",
                "reason": "Bloquea métricas por asesor y cartera",
            }
        )
    recs.append(
        {
            "priority": "Alta",
            "action": "Confirmar unidad de hs_call_duration y normalizar en capa analítica",
            "reason": "KPIs de minutos de llamada dependen de esto",
        }
    )
    if api and (api.get("stage_history_test", {}).get("deals_with_stage_history", 0) or 0) > 0:
        recs.append(
            {
                "priority": "Alta",
                "action": "Diseñar extracción puntual de historial dealstage vía propertiesWithHistory",
                "reason": "Métricas de estancamiento por etapa requieren historial",
            }
        )
    recs.append(
        {
            "priority": "Media",
            "action": "Mapear zona desde propiedades candidatas (zona, ciudad, regional)",
            "reason": "Gerencia requiere desglose geográfico",
        }
    )
    recs.append(
        {
            "priority": "Media",
            "action": "Definir reglas de llamada conectada usando hs_call_status + hs_call_outcome + duración",
            "reason": "No basta con existencia de actividad tipo call",
        }
    )
    recs.append(
        {
            "priority": "Media",
            "action": "Documentar aproximación de conversaciones WhatsApp (agrupación temporal)",
            "reason": "API no expone hilo de conversación unificado",
        }
    )
    if db["settings"]["activity_sync_lookback_days"] < 180:
        recs.append(
            {
                "priority": "Media",
                "action": "Evaluar ampliación de ventana histórica para actividades (fuera de sync masivo automático)",
                "reason": "Predicción semanal necesita más semanas",
            }
        )
    recs.append(
        {
            "priority": "Opcional",
            "action": "Refrescar deal_analytics tras validar owners y zona",
            "reason": "Capa analítica ya existe en sql/005-006",
        }
    )
    return recs


def render_markdown(report: dict[str, Any]) -> str:
    db = report.get("database", {})
    api = report.get("api", {})
    metrics = report.get("metrics_availability", [])
    comparison = report.get("api_vs_local", [])
    issues = report.get("data_quality_issues", [])
    recs = report.get("recommended_next_steps", [])
    ts = report.get("time_series_readiness", {})

    lines = [
        "# Informe ejecutivo — Exploración de datos gerenciales",
        "",
        f"Generado: {report.get('generated_at', '')}",
        "",
        "## Qué tenemos",
        "",
    ]
    counts = db.get("table_counts", {})
    if counts.get("hubspot_deals"):
        lines.append(
            f"- **Negocios**: {counts['hubspot_deals']} registros sincronizados con pipeline, etapa, "
            "monto y marca (vía pipeline o propiedad custom)."
        )
    if counts.get("hubspot_calls"):
        lines.append(
            f"- **Llamadas**: {counts['hubspot_calls']} en ventana local; propiedades de dirección, "
            "estado, resultado, duración y propietario disponibles en metadata."
        )
    if counts.get("hubspot_tasks"):
        lines.append(
            f"- **Tareas**: {counts['hubspot_tasks']} registros"
            + (" con historial completo habilitado." if db.get("settings", {}).get("task_sync_full_history") else ".")
        )
    if counts.get("hubspot_associations"):
        lines.append(
            f"- **Asociaciones**: {counts['hubspot_associations']} filas para vincular actividades con negocios y contactos."
        )

    lines.extend(["", "## Qué tenemos parcialmente", ""])
    lines.append(
        "- **Comunicaciones / WhatsApp**: mensajes individuales con canal; no hay ID de conversación confiable en la API."
    )
    lines.append(
        "- **Duración de llamadas**: campo presente pero la unidad debe confirmarse antes de KPIs de minutos."
    )
    lines.append(
        "- **Zona geográfica**: candidatos en propiedades custom; cobertura desigual."
    )
    if api.get("stage_history_test"):
        sh = api["stage_history_test"]
        lines.append(
            f"- **Historial de etapas**: accesible vía API en muestra ({sh.get('coverage_in_sample_pct', 0)}%), "
            "pero no está sincronizado localmente."
        )

    lines.extend(["", "## Qué falta", ""])
    for issue in issues[:6]:
        lines.append(f"- {issue}")
    if not issues:
        lines.append("- No se detectaron bloqueos críticos en esta exploración.")

    lines.extend(["", "## Qué se puede analizar ahora", ""])
    for m in metrics:
        if m["status"] == "DISPONIBLE":
            lines.append(f"- {m['metric']}")

    lines.extend(["", "## Qué requiere ajustes", ""])
    for m in metrics:
        if m["status"] not in ("DISPONIBLE",):
            lines.append(f"- **{m['metric']}**: {m['blocker']} → {m['next_action']}")

    lines.extend(["", "## Qué no se puede analizar todavía", ""])
    lines.append("- Conversaciones WhatsApp como hilos cerrados con conteo de respuestas fiable.")
    lines.append("- Movimientos de etapa históricos completos sin nueva extracción.")
    lines.append("- Predicción semanal robusta si la historia de actividades es < 90 días.")

    lines.extend(["", "## Riesgos", ""])
    for issue in issues:
        lines.append(f"- {issue}")

    lines.extend(["", "## Recomendación del siguiente paso", ""])
    for priority in ("Alta", "Media", "Opcional"):
        bucket = [r for r in recs if r["priority"] == priority]
        if bucket:
            lines.append(f"### {priority} prioridad")
            for r in bucket:
                lines.append(f"- {r['action']}: {r['reason']}")
            lines.append("")

    lines.extend(["", "## Matriz de disponibilidad", "", "| Necesidad | Estado | Fuente | Cobertura | Bloqueo | Siguiente acción |", "| --- | --- | --- | ---: | --- | --- |"])
    for m in metrics:
        lines.append(
            f"| {m['metric']} | {m['status']} | {m['source']} | {m['coverage']} | {m['blocker']} | {m['next_action']} |"
        )

    lines.extend(["", "## Comparación API vs Supabase", "", "| Objeto | API estimado | Local | Cobertura local | Acción |", "| --- | ---: | ---: | ---: | --- |"])
    for row in comparison:
        cov = row.get("local_coverage_pct")
        cov_s = f"{cov}%" if cov is not None else "—"
        lines.append(
            f"| {row['object']} | {row.get('api_estimated_total', '—')} | {row.get('local_count', 0)} | {cov_s} | {row.get('action', '')} |"
        )

    lines.extend(["", "## Series temporales (semanal, America/Bogota)", ""])
    for name, data in ts.items():
        lines.append(
            f"- **{name}**: {data.get('weeks_with_data', 0)} semanas con datos "
            f"({data.get('min_week', '—')} → {data.get('max_week', '—')})"
        )

    return "\n".join(lines) + "\n"


async def run_exploration(
    *,
    sample_size: int,
    object_filter: str | None,
    skip_api: bool,
    skip_database: bool,
    output_json: Path,
    output_md: Path,
) -> dict[str, Any]:
    settings = get_settings()
    report: dict[str, Any] = {
        "generated_at": _now_iso(),
        "environment": {
            "api_reachable": False,
            "database_reachable": False,
            "health_ok": False,
            "app_env": settings.app_env,
            "hubspot_token_configured": bool(settings.hubspot_access_token.get_secret_value()),
            "supabase_configured": bool(settings.supabase_url and settings.supabase_secret_key.get_secret_value()),
        },
        "objects": {},
        "associations": {},
        "owners": {},
        "dimensions": {"brand": {}, "zone": {}},
        "metrics_availability": [],
        "time_series_readiness": {},
        "missing_scopes": [],
        "data_quality_issues": [],
        "recommended_next_steps": [],
    }

    db_section: dict[str, Any] = {}
    api_section: dict[str, Any] | None = None

    if not skip_database:
        try:
            get_supabase_client().table("sync_runs").select("id").limit(1).execute()
            report["environment"]["database_reachable"] = True
            db_section = explore_database(sample_size)
            report["environment"]["health_ok"] = True
            report["associations"] = association_stats()
            report["owners"] = {
                "deals": db_section.get("deal_owners"),
                "activities": db_section.get("activity_owners"),
                "summary": db_section.get("owners_summary"),
            }
            report["dimensions"]["brand"] = {
                "source": "pipeline_id mapping + deals.marca custom",
                "pipeline_mappings": ["default→shacman", "1000390393→voyah", "1963395799→mhero"],
            }
            report["dimensions"]["zone"] = {
                "candidates": db_section.get("zone_candidates", []),
                "resolution_priority": "zona → ciudad/depto → contacto → owner team",
            }
            for obj in ("deals", "calls", "communications", "meetings", "tasks", "notes"):
                key = f"hubspot_{obj}" if obj != "deals" else "hubspot_deals"
                report["objects"][obj] = {
                    "local_count": db_section["table_counts"].get(key, 0),
                    "date_bounds": db_section["date_bounds"].get(key),
                }
            if "calls" in db_section:
                report["objects"]["calls"]["duration_stats"] = db_section["call_duration"]
            if "communications" in db_section:
                report["objects"]["communications"]["channels"] = db_section["communications"]
            if "tasks" in db_section:
                report["objects"]["tasks"]["status_breakdown"] = db_section["tasks"]
            report["objects"]["deals"]["field_coverage"] = db_section.get("deal_field_coverage")
        except Exception as exc:
            db_section = {"error": type(exc).__name__, "message": str(exc)[:200]}
            report["database"] = db_section
    else:
        report["database"] = {"skipped": True}

    if not skip_api:
        try:
            api_section = await explore_api(sample_size, object_filter)
            report["environment"]["api_reachable"] = bool(api_section.get("api_reachable"))
            report["environment"]["health_ok"] = (
                report["environment"]["database_reachable"] and report["environment"]["api_reachable"]
            )
            report["missing_scopes"] = api_section.get("missing_scopes", [])
            for obj, detail in api_section.get("object_samples", {}).items():
                if obj in report["objects"]:
                    report["objects"][obj]["api_sample"] = {
                        "sample_count": detail.get("sample_count"),
                        "paging_has_more": detail.get("paging_has_more"),
                    }
                else:
                    report["objects"][obj] = {"api_sample": detail}
            report["objects"]["deals"]["stage_history_test"] = api_section.get("stage_history_test")
            report["api"] = api_section
        except Exception as exc:
            report["api"] = {"error": type(exc).__name__, "message": str(exc)[:200]}
            api_section = None
    else:
        report["api"] = {"skipped": True}

    if db_section and "error" not in db_section:
        report["database"] = db_section
        report["time_series_readiness"] = build_time_series_readiness(db_section)
        report["metrics_availability"] = build_metrics_availability(db_section, api_section)
        report["api_vs_local"] = api_vs_local_comparison(db_section, api_section)
        report["data_quality_issues"] = build_data_quality_issues(db_section, api_section)
        report["recommended_next_steps"] = build_recommendations(
            db_section, api_section, report["data_quality_issues"]
        )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exploración de datos gerenciales (solo lectura)")
    parser.add_argument("--sample-size", type=int, default=20, help="Tamaño de muestra API (máx 10 por request)")
    parser.add_argument("--object", type=str, default=None, help="Limitar a un objeto HubSpot")
    parser.add_argument("--skip-api", action="store_true", help="Omitir exploración HubSpot API")
    parser.add_argument("--skip-database", action="store_true", help="Omitir exploración Supabase")
    parser.add_argument("--output", type=str, default=None, help="Ruta base de salida (sin extensión)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = Path(args.output) if args.output else DEFAULT_JSON.with_suffix("")
    json_path = base.with_suffix(".json") if args.output else DEFAULT_JSON
    md_path = base.with_suffix(".md") if args.output else DEFAULT_MD

    print("Exploración de datos gerenciales (solo lectura)")
    print(f"  sample_size={args.sample_size}")
    print(f"  skip_api={args.skip_api} skip_database={args.skip_database}")

    report = asyncio.run(
        run_exploration(
            sample_size=args.sample_size,
            object_filter=args.object,
            skip_api=args.skip_api,
            skip_database=args.skip_database,
            output_json=json_path,
            output_md=md_path,
        )
    )

    env = report.get("environment", {})
    print(f"\nAPI alcanzable: {env.get('api_reachable')}")
    print(f"Base de datos alcanzable: {env.get('database_reachable')}")
    counts = (report.get("database") or {}).get("table_counts", {})
    if counts:
        print("Conteos locales:", {k: counts[k] for k in sorted(counts) if k.startswith("hubspot_")})
    print(f"\nInforme JSON: {json_path}")
    print(f"Resumen MD:   {md_path}")
    return 0 if env.get("health_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
