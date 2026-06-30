"""Consultas y agregaciones sobre deal_analytics."""

from __future__ import annotations

import statistics
import threading
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from app.config import get_settings
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.services.deal_analytics.contact_metrics import (
    ActivityRecord,
    activity_attributed_to_owner,
    build_activity_record,
    compute_contact_metrics,
    load_attributed_contact_activity_bundle,
    load_contact_activity_bundle,
    merge_contact_metrics_into_advisor_row,
    normalize_owner_id,
    rollup_group_contact_metrics,
    serialize_metrics_for_json,
)
from app.services.deal_analytics.evaluation_metadata import build_evaluation_metadata
from app.services.deal_analytics.operational_scores import (
    legacy_pipeline_effectiveness_component,
    management_discipline_score,
)
from app.services.deal_analytics.filters import (
    DealAnalyticsFilters,
    get_buckets,
    value_to_bucket,
)
from app.services.deal_analytics.task_semantics import (
    is_closed_deal_for_task_metrics,
    is_closed_deal_row_for_task_metrics,
    is_reassigned_lead_task,
    task_subject_from_record,
)
from app.services.hubspot_configuration import get_hubspot_config
from app.utils.dates import parse_hubspot_datetime, utc_now
from app.utils.week_bounds import monday_of, week_starts_between

_RESPONSE_CACHE_TTL_SECONDS = 300
_response_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_filtered_rows_cache: dict[str, tuple[float, tuple[list[dict[str, Any]], int]]] = {}
_contact_bundle_cache: dict[frozenset[str], tuple[float, Any]] = {}
_filtered_rows_locks_guard = threading.Lock()
_filtered_rows_locks: dict[str, threading.Lock] = {}


def _filter_rows_cache_key(filters: DealAnalyticsFilters) -> str:
    payload = filters.model_dump(
        exclude={"limit", "offset", "sort_by", "sort_dir"},
        exclude_none=True,
    )
    return str(sorted(payload.items()))


def _filtered_rows_cache_get(key: str) -> tuple[list[dict[str, Any]], int] | None:
    entry = _filtered_rows_cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _RESPONSE_CACHE_TTL_SECONDS:
        _filtered_rows_cache.pop(key, None)
        return None
    return value


def _filtered_rows_cache_set(key: str, value: tuple[list[dict[str, Any]], int]) -> None:
    _filtered_rows_cache[key] = (time.time(), value)


def _contact_bundle_cache_get(key: frozenset[str]) -> Any | None:
    entry = _contact_bundle_cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _RESPONSE_CACHE_TTL_SECONDS:
        _contact_bundle_cache.pop(key, None)
        return None
    return value


def _contact_bundle_cache_set(key: frozenset[str], value: Any) -> None:
    _contact_bundle_cache[key] = (time.time(), value)


def _filtered_rows_lock(key: str) -> threading.Lock:
    with _filtered_rows_locks_guard:
        lock = _filtered_rows_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _filtered_rows_locks[key] = lock
        return lock


def invalidate_deal_analytics_cache() -> None:
    _response_cache.clear()
    _filtered_rows_cache.clear()
    _contact_bundle_cache.clear()
    _filtered_rows_locks.clear()


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _response_cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _RESPONSE_CACHE_TTL_SECONDS:
        _response_cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict[str, Any]) -> None:
    _response_cache[key] = (time.time(), value)


def _open_deal_ids(rows: list[dict[str, Any]]) -> list[str]:
    """IDs de negocios abiertos — suficientes para métricas de cobertura de contacto."""
    return [str(r["deal_id"]) for r in rows if r.get("deal_id") and r.get("is_open")]


def _brand_deal_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(r["deal_id"]) for r in rows if r.get("deal_id")]

SUMMARY_COLUMNS = (
    "deal_id,deal_name,status,amount,is_open,is_won,is_lost,is_stale,is_unattended,"
    "has_overdue_tasks,has_owner,has_future_task,has_recent_activity_7d,"
    "has_recent_activity_30d,has_recent_activity_60d,has_recent_effective_contact_30d,"
    "age_days,days_in_current_stage,days_since_last_activity,days_since_effective_contact,"
    "pipeline_id,pipeline_label,stage_id,stage_label,stage_display_order,"
    "owner_id,owner_name,brand_value,brand_label,zone_value,zone_label,"
    "activity_count,effective_contact_count,stage_change_count,completed_meeting_count,"
    "overdue_task_count,open_task_count,alert_reason,unattended_reason,stale_reason,"
    "has_activity,has_effective_contact,stage_history_status,data_completeness_score,"
    "first_response_minutes,call_count,completed_call_count,task_count,note_count,"
    "meeting_count,communication_count,contact_count,created_at,closed_at,"
    "commercial_group,commercial_group_label,commercial_group_order,is_stale_45d,"
    "completed_task_count"
)


class DealAnalyticsQueryService:
    def __init__(self, repository: DealAnalyticsRepository | None = None) -> None:
        self._repo = repository or DealAnalyticsRepository()
        self._settings = get_settings()
        self._contact_bundle_cache: dict[frozenset[str], Any] = {}

    def _contact_bundle(
        self,
        deal_ids: list[str],
        rows: list[dict[str, Any]] | None = None,
        *,
        preloaded_contact_ids: set[str] | None = None,
        preloaded_deal_contact_links: dict[str, list[str]] | None = None,
    ) -> Any:
        key = frozenset(str(d) for d in deal_ids)
        cached = _contact_bundle_cache_get(key)
        if cached is not None:
            return cached
        if key in self._contact_bundle_cache:
            return self._contact_bundle_cache[key]

        ctx = {}
        if rows:
            for r in rows:
                did = str(r.get("deal_id") or "")
                if did:
                    ctx[did] = r
        bundle = load_attributed_contact_activity_bundle(
            self._repo,
            list(key),
            open_deal_context=ctx or None,
            preloaded_contact_ids=preloaded_contact_ids,
            preloaded_deal_contact_links=preloaded_deal_contact_links,
        )
        self._contact_bundle_cache[key] = bundle
        _contact_bundle_cache_set(key, bundle)
        return bundle

    def _contact_metric_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "deal_id": r.get("deal_id"),
                "owner_id": r.get("owner_id"),
                "is_open": bool(r.get("is_open")),
                "is_won": bool(r.get("is_won")),
                "is_lost": bool(r.get("is_lost")),
                "amount": r.get("amount"),
            }
            for r in rows
            if r.get("deal_id")
        ]

    def _compute_owner_contact_metrics(
        self,
        rows: list[dict[str, Any]],
        owner_id: str | None,
        bundle: Any,
    ) -> dict[str, Any]:
        metrics = compute_contact_metrics(
            self._contact_metric_rows(rows),
            bundle,
            owner_id=owner_id,
            contact_window_days=self._settings.contact_coverage_window_days,
            session_gap_hours=float(self._settings.whatsapp_session_gap_hours),
            timezone=self._settings.business_timezone,
        )
        return serialize_metrics_for_json(metrics)

    def _envelope(
        self,
        *,
        filters: DealAnalyticsFilters,
        rows: list[dict[str, Any]],
        data: Any,
        total_deals: int,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        config = get_hubspot_config()
        included = len(rows)
        return {
            "filters": filters.model_dump(exclude_none=True),
            "population": {
                "total_deals": total_deals,
                "included_deals": included,
                "excluded_deals": max(0, total_deals - included),
            },
            "data": data,
            "data_quality": {
                "status": "available" if rows else "unavailable",
                "notes": notes or [],
                "activity_coverage": "synced",
                "task_coverage": "open_tasks_all_completed",
                "stage_history_coverage": _stage_history_coverage(rows),
            },
            "configuration": {
                "metadata_snapshot_at": config.metadata_snapshot_at,
                "field_mapping_version": config.field_mapping_version,
                "dimension_mapping_version": config.dimension_mapping_version,
            },
            "generated_at": utc_now().isoformat(),
            "timezone": self._settings.business_timezone,
            "evaluation_metadata": build_evaluation_metadata(),
        }

    def _filtered_rows(self, filters: DealAnalyticsFilters) -> tuple[list[dict[str, Any]], int]:
        cache_key = _filter_rows_cache_key(filters)
        cached = _filtered_rows_cache_get(cache_key)
        if cached is not None:
            return cached

        lock = _filtered_rows_lock(cache_key)
        with lock:
            cached = _filtered_rows_cache_get(cache_key)
            if cached is not None:
                return cached

            total = self._repo.count_deals()
            if self._repo.count_analytics() == 0:
                result: tuple[list[dict[str, Any]], int] = ([], total)
            else:
                rows = self._repo.fetch_all_filtered(filters, columns=SUMMARY_COLUMNS)
                result = (rows, total)
            _filtered_rows_cache_set(cache_key, result)
            return result

    def summary(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        open_rows = [r for r in rows if r.get("is_open")]
        won_rows = [r for r in rows if r.get("is_won")]
        lost_rows = [r for r in rows if r.get("is_lost")]
        unknown_rows = [r for r in rows if r.get("status") == "unknown"]
        stale_rows = [r for r in rows if r.get("is_stale")]
        unattended_open = [r for r in open_rows if r.get("is_unattended")]
        amounts = [float(r["amount"]) for r in rows if r.get("amount") is not None]
        managed_30d = sum(1 for r in open_rows if r.get("has_recent_activity_30d"))
        effective_30d = sum(1 for r in open_rows if r.get("has_recent_effective_contact_30d"))
        open_count = len(open_rows)

        data = {
            "total_deals": len(rows),
            "open_deals": open_count,
            "won_deals": len(won_rows),
            "lost_deals": len(lost_rows),
            "unknown_status_deals": len(unknown_rows),
            "open_pipeline_amount": sum(float(r.get("amount") or 0) for r in open_rows),
            "won_amount": sum(float(r.get("amount") or 0) for r in won_rows),
            "lost_amount": sum(float(r.get("amount") or 0) for r in lost_rows),
            "stale_deals": len(stale_rows),
            "stale_pipeline_amount": sum(float(r.get("amount") or 0) for r in stale_rows),
            "unattended_open_deals": len(unattended_open),
            "deals_without_owner": sum(1 for r in rows if not r.get("has_owner")),
            "deals_with_overdue_tasks": sum(
                1 for r in open_rows if r.get("has_overdue_tasks")
            ),
            "open_managed_30d": managed_30d,
            "open_managed_30d_rate": round(managed_30d / open_count * 100, 1) if open_count else None,
            "open_effective_contact_30d": effective_30d,
            "open_effective_contact_30d_rate": round(effective_30d / open_count * 100, 1) if open_count else None,
            "status_distribution": _status_distribution(rows),
            "average_deal_amount": round(statistics.mean(amounts), 2) if amounts else None,
            "median_deal_amount": round(statistics.median(amounts), 2) if amounts else None,
            "activity_coverage_note": (
                "Gestión reciente basada en actividades sincronizadas en Supabase."
            ),
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def brands_zones(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            brand = str(row.get("brand_value") or "unknown")
            zone = str(row.get("zone_value") or "unknown")
            key = (brand, zone)
            item = groups.setdefault(
                key,
                {
                    "brand_value": brand,
                    "brand_label": row.get("brand_label") or brand,
                    "zone_value": zone,
                    "zone_label": row.get("zone_label") or zone,
                    "total_deals": 0,
                    "open_deals": 0,
                    "won_deals": 0,
                    "lost_deals": 0,
                    "open_pipeline_amount": 0.0,
                    "won_amount": 0.0,
                    "managed_30d": 0,
                    "effective_contact_30d": 0,
                    "stale_deals": 0,
                    "unattended_open_deals": 0,
                    "deals_with_overdue_tasks": 0,
                },
            )
            item["total_deals"] += 1
            if row.get("is_open"):
                item["open_deals"] += 1
                item["open_pipeline_amount"] += float(row.get("amount") or 0)
                if row.get("has_recent_activity_30d"):
                    item["managed_30d"] += 1
                if row.get("has_recent_effective_contact_30d"):
                    item["effective_contact_30d"] += 1
                if row.get("is_unattended"):
                    item["unattended_open_deals"] += 1
            if row.get("is_won"):
                item["won_deals"] += 1
                item["won_amount"] += float(row.get("amount") or 0)
            if row.get("is_lost"):
                item["lost_deals"] += 1
            if row.get("is_stale"):
                item["stale_deals"] += 1
            if row.get("is_open") and row.get("has_overdue_tasks"):
                item["deals_with_overdue_tasks"] += 1

        data = []
        for item in groups.values():
            open_count = item["open_deals"]
            closed = item["won_deals"] + item["lost_deals"]
            item["managed_30d_rate"] = round(item["managed_30d"] / open_count * 100, 1) if open_count else None
            item["effective_contact_30d_rate"] = (
                round(item["effective_contact_30d"] / open_count * 100, 1) if open_count else None
            )
            item["close_rate"] = round(item["won_deals"] / closed * 100, 1) if closed else None
            data.append(item)
        data.sort(key=lambda x: (-x["open_pipeline_amount"], x["brand_label"], x["zone_label"]))
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def brand_operating(self, brand_value: str) -> dict[str, Any]:
        """Dashboard operativo por marca: etapas semánticas, asesores, semanal."""
        brand = brand_value.strip().lower()
        cache_key = f"brand_operating:{brand}:v6"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        filters = DealAnalyticsFilters(brand_value=brand)
        rows, total = self._filtered_rows(filters)
        open_rows = [r for r in rows if r.get("is_open")]

        stage_groups: dict[str, dict[str, Any]] = {}
        for row in open_rows:
            key = str(row.get("commercial_group") or "unknown")
            item = stage_groups.setdefault(
                key,
                {
                    "commercial_group": key,
                    "commercial_group_label": row.get("commercial_group_label") or key,
                    "display_order": row.get("commercial_group_order") or 999,
                    "open_deals": 0,
                    "stale_45d": 0,
                    "with_overdue_tasks": 0,
                    "stages_detail": defaultdict(int),
                },
            )
            item["open_deals"] += 1
            if row.get("is_stale_45d"):
                item["stale_45d"] += 1
            if row.get("has_overdue_tasks"):
                item["with_overdue_tasks"] += 1
            stage_label = str(row.get("stage_label") or "—")
            item["stages_detail"][stage_label] += 1

        stage_groups_list = []
        for item in stage_groups.values():
            detail = [
                {"stage_label": label, "count": count}
                for label, count in sorted(item["stages_detail"].items(), key=lambda x: -x[1])
            ]
            stage_groups_list.append({**item, "stages_detail": detail})
        stage_groups_list.sort(key=lambda x: x["display_order"])

        advisors: dict[str, dict[str, Any]] = {}
        for row in rows:
            owner_id = str(row.get("owner_id") or "unassigned")
            owner_name = row.get("owner_name") or ("Sin asignar" if owner_id == "unassigned" else owner_id)
            item = advisors.setdefault(
                owner_id,
                {
                    "owner_id": None if owner_id == "unassigned" else owner_id,
                    "owner_name": owner_name,
                    "brand_value": brand_value,
                    "assigned_deals": 0,
                    "open_deals": 0,
                    "new_deals_7d": 0,
                    "new_deals_30d": 0,
                    "stale_45d_open": 0,
                    "tasks_completed": 0,
                    "tasks_open": 0,
                    "tasks_overdue": 0,
                    "deals_with_overdue_tasks": 0,
                    "managed_30d": 0,
                },
            )
            item["assigned_deals"] += 1
            if not is_closed_deal_row_for_task_metrics(row):
                item["tasks_completed"] += int(row.get("completed_task_count") or 0)
                item["tasks_open"] += int(row.get("open_task_count") or 0)
                item["tasks_overdue"] += int(row.get("overdue_task_count") or 0)
                if row.get("has_overdue_tasks"):
                    item["deals_with_overdue_tasks"] += 1
            if row.get("is_open"):
                item["open_deals"] += 1
                if row.get("is_stale_45d"):
                    item["stale_45d_open"] += 1
                if row.get("has_recent_activity_30d"):
                    item["managed_30d"] += 1
            created = _parse_created_at(row.get("created_at"))
            if created:
                age_days = (utc_now() - created).days
                if age_days <= 7:
                    item["new_deals_7d"] += 1
                if age_days <= 30:
                    item["new_deals_30d"] += 1

        advisor_list = []
        brand_deal_ids = _brand_deal_ids(rows)
        open_deal_ids = _open_deal_ids(rows)
        bundle = None
        if brand_deal_ids:
            brand_contact_ids = self._repo.fetch_contact_ids_for_deals(brand_deal_ids)
            brand_deal_contact_links = self._repo.fetch_deal_contact_links(brand_deal_ids)
            bundle = self._contact_bundle(
                brand_deal_ids,
                rows,
                preloaded_contact_ids=brand_contact_ids,
                preloaded_deal_contact_links=brand_deal_contact_links,
            )
        tz = self._settings.business_timezone
        config = get_hubspot_config()
        deal_context = {
            str(r["deal_id"]): {
                "is_won": bool(r.get("is_won")),
                "is_lost": bool(r.get("is_lost")),
            }
            for r in rows
            if r.get("deal_id")
        }
        task_links = self._repo.fetch_task_links_for_deals(brand_deal_ids) if brand_deal_ids else {}
        tasks_raw = (
            self._repo.fetch_tasks_by_ids(sorted(task_links.keys())) if task_links else []
        )
        tasks_raw = _filter_tasks_for_management_metrics(
            tasks_raw,
            task_links=task_links,
            deal_context=deal_context,
        )
        for item in advisors.values():
            open_count = item["open_deals"]
            item["managed_30d_rate"] = round(item["managed_30d"] / open_count * 100, 1) if open_count else None
            item["tasks_overdue_rate"] = (
                round(item["tasks_overdue"] / max(item["tasks_open"] + item["tasks_completed"], 1) * 100, 1)
            )
            owner_key = str(item.get("owner_id") or "unassigned")
            owner_rows = [r for r in rows if str(r.get("owner_id") or "unassigned") == owner_key]
            if bundle and item.get("owner_id"):
                metrics = self._compute_owner_contact_metrics(owner_rows, item["owner_id"], bundle)
                item = merge_contact_metrics_into_advisor_row(item, metrics)
            item["won_sales"] = _won_sales_units_summary(
                [r for r in owner_rows if r.get("is_won")],
                timezone=tz,
            )
            item["leads_created"] = _monthly_period_summary(
                owner_rows,
                date_field="created_at",
                timezone=tz,
            )
            item["performance"] = _build_performance_metrics(
                owner_rows,
                item,
                bundle=bundle,
                owner_id=item.get("owner_id"),
                tasks_raw=tasks_raw,
                task_links=task_links,
                timezone=tz,
                is_task_completed=config.is_task_completed,
            )
            advisor_list.append(item)
        advisor_list.sort(key=lambda x: (-x["open_deals"], x["owner_name"] or ""))

        brand_contact = None
        if bundle and open_deal_ids:
            brand_contact = serialize_metrics_for_json(
                compute_contact_metrics(
                    self._contact_metric_rows(rows),
                    bundle,
                    owner_id=None,
                    contact_window_days=self._settings.contact_coverage_window_days,
                    session_gap_hours=float(self._settings.whatsapp_session_gap_hours),
                    timezone=self._settings.business_timezone,
                )
            )

        weekly = _weekly_deals_created(rows, timezone=self._settings.business_timezone)
        weekly_won = _weekly_deals_closed(
            rows, timezone=self._settings.business_timezone, outcome="won"
        )
        weekly_lost = _weekly_deals_closed(
            rows, timezone=self._settings.business_timezone, outcome="lost"
        )
        won_sales_summary = _won_sales_units_summary(
            rows, timezone=self._settings.business_timezone
        )
        weekly_calls = (
            _weekly_calls_volume(bundle.calls, timezone=self._settings.business_timezone)
            if bundle and bundle.calls
            else (
                _weekly_calls_for_deals(
                    self._repo,
                    brand_deal_ids,
                    timezone=self._settings.business_timezone,
                    lookback_days=self._settings.activity_sync_lookback_days,
                )
                if brand_deal_ids
                else []
            )
        )

        from app.services.deal_analytics.brand_stale import stale_threshold_days_for_brand

        stale_threshold_days = stale_threshold_days_for_brand(brand_value)

        data = {
            "brand_value": brand_value,
            "brand_label": rows[0].get("brand_label") if rows else brand_value.title(),
            "stale_threshold_days": stale_threshold_days,
            "totals": {
                "all_deals": len(rows),
                "open_deals": len(open_rows),
                "won_deals": sum(1 for r in rows if r.get("is_won")),
                "lost_deals": sum(1 for r in rows if r.get("is_lost")),
                "stale_45d_open": sum(1 for r in open_rows if r.get("is_stale_45d")),
                "new_deals_7d": sum(1 for r in rows if _is_new_within_days(r, 7)),
                "new_deals_30d": sum(1 for r in rows if _is_new_within_days(r, 30)),
            },
            "stage_groups": stage_groups_list,
            "advisors": advisor_list,
            "weekly_created": weekly,
            "weekly_won": weekly_won,
            "weekly_lost": weekly_lost,
            "won_sales_summary": won_sales_summary,
            "weekly_calls": weekly_calls,
            "contact_methodology": {
                "version": "2.0",
                "contact_window_days": self._settings.contact_coverage_window_days,
                "brand_summary": brand_contact,
                "focus": "calls_whatsapp_coverage",
            },
            "activity_coverage_note": (
                "Metodología centrada en llamadas y WhatsApp. Cobertura = negocios únicos contactados / activos. "
                f"Ventana de contacto: {self._settings.contact_coverage_window_days} días. "
                f"Actividades sincronizadas: ventana {self._settings.activity_sync_lookback_days} días "
                "(tareas con historial completo). Sesiones WhatsApp = estimación."
            ),
        }
        result = self._envelope(filters=filters, rows=rows, data=data, total_deals=total)
        _cache_set(cache_key, result)
        return result

    def groups_compare(self, brand_value: str, groups: list[dict[str, Any]]) -> dict[str, Any]:
        """Compara KPIs agregados entre grupos de asesores en una marca."""
        brand = brand_value.strip().lower()
        filters = DealAnalyticsFilters(brand_value=brand)
        rows, total = self._filtered_rows(filters)

        compared: list[dict[str, Any]] = []
        brand_deal_ids = _brand_deal_ids(rows)
        open_deal_ids = _open_deal_ids(rows)
        bundle = self._contact_bundle(brand_deal_ids, rows) if brand_deal_ids else None
        tz = self._settings.business_timezone
        config = get_hubspot_config()
        deal_context = {
            str(r["deal_id"]): {
                "is_won": bool(r.get("is_won")),
                "is_lost": bool(r.get("is_lost")),
            }
            for r in rows
            if r.get("deal_id")
        }
        task_links = self._repo.fetch_task_links_for_deals(brand_deal_ids) if brand_deal_ids else {}
        tasks_raw = (
            self._repo.fetch_tasks_by_ids(sorted(task_links.keys())) if task_links else []
        )
        tasks_raw = _filter_tasks_for_management_metrics(
            tasks_raw,
            task_links=task_links,
            deal_context=deal_context,
        )
        for group in groups:
            member_ids = {str(m.get("owner_id")) for m in group.get("members") or [] if m.get("owner_id")}
            group_rows = [r for r in rows if str(r.get("owner_id") or "") in member_ids]
            advisors = _aggregate_advisors_from_rows(group_rows, brand)
            if bundle:
                enriched: list[dict[str, Any]] = []
                for adv in advisors:
                    if adv.get("owner_id"):
                        owner_rows = [
                            r for r in group_rows if normalize_owner_id(r.get("owner_id")) == adv["owner_id"]
                        ]
                        metrics = self._compute_owner_contact_metrics(owner_rows, adv["owner_id"], bundle)
                        enriched.append(merge_contact_metrics_into_advisor_row(adv, metrics))
                    else:
                        enriched.append(adv)
                advisors = enriched
            rollup = _rollup_advisor_metrics(advisors)
            group_contact = None
            if bundle and group_rows:
                group_contact = serialize_metrics_for_json(
                    rollup_group_contact_metrics(
                        advisors,
                        group_deals=self._contact_metric_rows(group_rows),
                        bundle=bundle,
                        contact_window_days=self._settings.contact_coverage_window_days,
                        timezone=self._settings.business_timezone,
                    )
                )
            compared.append(
                {
                    "group_id": str(group.get("id")),
                    "group_name": group.get("name") or "Grupo",
                    "source": group.get("source"),
                    "hubspot_source_label": group.get("hubspot_source_label"),
                    "member_count": len(member_ids),
                    **rollup,
                    "contact_methodology": group_contact,
                    "performance": _build_performance_metrics(
                        group_rows,
                        rollup,
                        bundle=bundle,
                        owner_id=None,
                        tasks_raw=tasks_raw,
                        task_links=task_links,
                        timezone=tz,
                        is_task_completed=config.is_task_completed,
                    ),
                    "advisors": advisors,
                }
            )

        data = {
            "brand_value": brand,
            "brand_label": rows[0].get("brand_label") if rows else brand.title(),
            "groups": compared,
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def advisor_portfolio(self, brand_value: str, owner_id: str) -> dict[str, Any]:
        """Cartera detallada de un asesor dentro de una marca: resumen, gráficas y negocios."""
        brand = brand_value.strip().lower()
        owner_key = owner_id.strip()
        cache_key = f"advisor_portfolio:{brand}:{owner_key}:v2"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        if owner_key == "unassigned":
            filters = DealAnalyticsFilters(brand_value=brand, has_owner=False)
        else:
            filters = DealAnalyticsFilters(brand_value=brand, owner_id=owner_key)
        rows, total = self._filtered_rows(filters)
        open_rows = [r for r in rows if r.get("is_open")]

        owner_name = "Sin asignar"
        if owner_key != "unassigned" and rows:
            owner_name = str(rows[0].get("owner_name") or owner_key)
        elif owner_key != "unassigned":
            owner_name = owner_key

        managed_30d = sum(1 for r in open_rows if r.get("has_recent_activity_30d"))
        open_count = len(open_rows)

        stage_groups: dict[str, dict[str, Any]] = {}
        for row in open_rows:
            key = str(row.get("commercial_group") or "unknown")
            item = stage_groups.setdefault(
                key,
                {
                    "commercial_group": key,
                    "commercial_group_label": row.get("commercial_group_label") or key,
                    "display_order": row.get("commercial_group_order") or 999,
                    "open_deals": 0,
                    "stale_45d": 0,
                },
            )
            item["open_deals"] += 1
            if row.get("is_stale_45d"):
                item["stale_45d"] += 1
        by_commercial_group = sorted(stage_groups.values(), key=lambda x: x["display_order"])

        inactivity_buckets = [
            {"bucket": "Sin actividad", "count": sum(1 for r in open_rows if not r.get("has_activity"))},
        ]
        for bucket in get_buckets("inactivity"):
            label = str(bucket["key"])
            count = sum(
                1
                for r in open_rows
                if r.get("has_activity")
                and value_to_bucket(r.get("days_since_last_activity"), "inactivity") == label
            )
            inactivity_buckets.append({"bucket": label, "count": count})

        by_stage: dict[str, dict[str, Any]] = {}
        for row in open_rows:
            label = str(row.get("stage_label") or "—")
            item = by_stage.setdefault(label, {"stage_label": label, "count": 0, "stale_45d": 0})
            item["count"] += 1
            if row.get("is_stale_45d"):
                item["stale_45d"] += 1
        by_stage_list = sorted(by_stage.values(), key=lambda x: -x["count"])

        deals = [_slim_deal_row(row) for row in rows]
        deals.sort(key=_deal_risk_sort_key)

        deal_ids = [str(r["deal_id"]) for r in rows if r.get("deal_id")]
        deal_context: dict[str, dict[str, Any]] = {
            str(r["deal_id"]): {
                "deal_name": r.get("deal_name"),
                "stage_label": r.get("stage_label"),
                "commercial_group_label": r.get("commercial_group_label"),
                "commercial_group": r.get("commercial_group"),
                "status": r.get("status"),
                "is_won": bool(r.get("is_won")),
                "is_lost": bool(r.get("is_lost")),
            }
            for r in rows
            if r.get("deal_id")
        }
        brand_deal_ids = set(deal_ids)
        deal_task_links = self._repo.fetch_task_links_for_deals(deal_ids)
        contact_links: dict[str, str] = {}
        contact_names: dict[str, str] = {}

        if owner_key == "unassigned":
            task_ids = set(deal_task_links.keys())
            tasks_raw = self._repo.fetch_tasks_by_ids(sorted(task_ids))
            task_links = deal_task_links
        else:
            tasks_raw = self._repo.fetch_tasks_for_owner(owner_key)
            task_ids = [str(t["hubspot_id"]) for t in tasks_raw if t.get("hubspot_id")]
            task_links = self._repo.fetch_deal_links_for_tasks(task_ids)
            contact_links = self._repo.fetch_contact_links_for_tasks(task_ids)
            extra_deal_ids = set(task_links.values()) - brand_deal_ids
            if extra_deal_ids:
                deal_context.update(self._repo.fetch_deal_context_by_ids(sorted(extra_deal_ids)))
            contact_ids = sorted(set(contact_links.values()))
            contact_names = self._repo.fetch_contact_names_by_ids(contact_ids) if contact_ids else {}

        config = get_hubspot_config()
        portfolio_tasks, excluded_orphan_tasks, excluded_reassigned_lead_tasks, excluded_closed_deal_tasks = (
            _build_portfolio_tasks(
                tasks_raw,
                task_links=task_links,
                contact_links=contact_links if owner_key != "unassigned" else {},
                deal_context=deal_context,
                contact_names=contact_names if owner_key != "unassigned" else {},
                owner_key=owner_key,
                brand_deal_ids=brand_deal_ids,
                config=config,
            )
        )

        linked_tasks_raw = _filter_tasks_with_record_link(
            tasks_raw,
            task_links,
            contact_links if owner_key != "unassigned" else task_links,
        )
        linked_tasks_raw = _filter_tasks_for_management_metrics(
            linked_tasks_raw,
            task_links=task_links,
            deal_context=deal_context,
        )

        weekly_created = _weekly_deals_created(rows, timezone=self._settings.business_timezone)
        weekly_won = _weekly_deals_closed(
            rows, timezone=self._settings.business_timezone, outcome="won"
        )
        weekly_lost = _weekly_deals_closed(
            rows, timezone=self._settings.business_timezone, outcome="lost"
        )
        weekly_overdue_tasks = _weekly_overdue_tasks(
            linked_tasks_raw,
            timezone=self._settings.business_timezone,
            is_task_completed=config.is_task_completed,
        )

        contact_methodology = None
        contact_deal_ids = _open_deal_ids(rows)
        if owner_key != "unassigned" and contact_deal_ids:
            bundle = self._contact_bundle(contact_deal_ids, rows)
            contact_methodology = self._compute_owner_contact_metrics(rows, owner_key, bundle)

        data = {
            "advisor": {
                "owner_id": None if owner_key == "unassigned" else owner_key,
                "owner_name": owner_name,
                "brand_value": brand,
                "brand_label": rows[0].get("brand_label") if rows else brand.title(),
            },
            "summary": {
                "assigned_deals": len(rows),
                "open_deals": open_count,
                "won_deals": sum(1 for r in rows if r.get("is_won")),
                "lost_deals": sum(1 for r in rows if r.get("is_lost")),
                "stale_45d_open": sum(1 for r in open_rows if r.get("is_stale_45d")),
                "unattended_open": sum(1 for r in open_rows if r.get("is_unattended")),
                "deals_with_overdue_tasks": sum(1 for r in open_rows if r.get("has_overdue_tasks")),
                "open_pipeline_amount": sum(float(r.get("amount") or 0) for r in open_rows),
                "managed_30d_rate": round(managed_30d / open_count * 100, 1) if open_count else None,
                **(
                    {
                        "call_coverage_rate": contact_methodology.get("calls", {}).get("call_coverage_rate"),
                        "whatsapp_coverage_rate": contact_methodology.get("whatsapp", {}).get(
                            "whatsapp_coverage_rate"
                        ),
                        "combined_coverage_rate": contact_methodology.get("coverage", {}).get(
                            "combined_contact_coverage_rate"
                        ),
                        "overdue_contact_21d": contact_methodology.get("coverage", {}).get("overdue_contact_21d"),
                        "channel_overdue_21d": contact_methodology.get("coverage", {}).get("channel_overdue_21d"),
                        "channel_overdue_21d_label": contact_methodology.get("coverage", {}).get(
                            "channel_overdue_21d_label"
                        ),
                        "discipline_operational_score": contact_methodology.get("evaluation", {}).get(
                            "discipline_operational_score"
                        ),
                        "discipline_operational_status": contact_methodology.get("evaluation", {}).get(
                            "discipline_operational_status"
                        ),
                        "legacy_discipline_contact_score": contact_methodology.get("evaluation", {}).get(
                            "legacy_discipline_contact_score"
                        ),
                        "discipline_contact_score": contact_methodology.get("evaluation", {}).get(
                            "discipline_contact_score"
                        ),
                        "commercial_effectiveness_score": contact_methodology.get("evaluation", {}).get(
                            "commercial_effectiveness_score"
                        ),
                        "effectiveness_commercial_score": contact_methodology.get("evaluation", {}).get(
                            "effectiveness_commercial_score"
                        ),
                    }
                    if contact_methodology
                    else {}
                ),
            },
            "won_sales": _won_sales_units_summary(
                [r for r in rows if r.get("is_won")],
                timezone=self._settings.business_timezone,
            ),
            "charts": {
                "by_commercial_group": by_commercial_group,
                "open_health": [
                    {
                        "label": "Cobertura llamadas",
                        "count": contact_methodology.get("calls", {}).get("call_coverage_numerator", 0)
                        if contact_methodology
                        else 0,
                    },
                    {
                        "label": "Cobertura WhatsApp",
                        "count": contact_methodology.get("whatsapp", {}).get("whatsapp_coverage_numerator", 0)
                        if contact_methodology
                        else 0,
                    },
                    {
                        "label": "Sin gestión 21d",
                        "count": contact_methodology.get("coverage", {}).get("deals_no_recent_contact", 0)
                        if contact_methodology
                        else 0,
                    },
                    {
                        "label": "Multicanal",
                        "count": contact_methodology.get("coverage", {}).get("deals_multichannel", 0)
                        if contact_methodology
                        else 0,
                    },
                ],
                "inactivity_distribution": inactivity_buckets,
                "by_stage": by_stage_list[:15],
                "weekly_created": weekly_created,
                "weekly_won": weekly_won,
                "weekly_lost": weekly_lost,
                "weekly_overdue_tasks": weekly_overdue_tasks,
                "weekly_calls": contact_methodology.get("calls", {}).get("weekly_trend", [])
                if contact_methodology
                else [],
                "weekly_whatsapp": contact_methodology.get("whatsapp", {}).get("weekly_trend", [])
                if contact_methodology
                else [],
                "duration_ranges": contact_methodology.get("calls", {}).get("duration_ranges", [])
                if contact_methodology
                else [],
                "channel_mix": contact_methodology.get("coverage", {}).get("channel_mix", {})
                if contact_methodology
                else {},
                "calls_by_weekday": contact_methodology.get("calls", {}).get("by_weekday", [])
                if contact_methodology
                else [],
                "whatsapp_by_weekday": contact_methodology.get("whatsapp", {}).get("by_weekday", [])
                if contact_methodology
                else [],
                "calls_by_time_band": contact_methodology.get("calls", {}).get("by_time_band", [])
                if contact_methodology
                else [],
                "whatsapp_by_time_band": contact_methodology.get("whatsapp", {}).get("by_time_band", [])
                if contact_methodology
                else [],
            },
            "contact_methodology": contact_methodology,
            "deals": deals,
            "tasks": portfolio_tasks,
            "task_counts": {
                "total": len(portfolio_tasks),
                "pending": sum(1 for t in portfolio_tasks if not t["is_completed"]),
                "overdue": sum(1 for t in portfolio_tasks if t["is_overdue"]),
                "completed_late": sum(1 for t in portfolio_tasks if t["is_completed_late"]),
                "completed": sum(1 for t in portfolio_tasks if t["is_completed"]),
                "excluded_orphan": excluded_orphan_tasks,
                "excluded_reassigned_lead": excluded_reassigned_lead_tasks,
                "excluded_closed_deal": excluded_closed_deal_tasks,
            },
            "activity_coverage_note": (
                "Análisis centrado en llamadas y WhatsApp. Cobertura = negocios únicos contactados / activos. "
                f"Ventana: {self._settings.contact_coverage_window_days} días. "
                f"Sesiones WhatsApp = estimación ({self._settings.whatsapp_session_gap_hours}h). "
                "Tareas: solo vinculadas a contacto o negocio (huérfanas excluidas). "
                "«Perdiste este Lead» = reasignación; no cuenta en rendimiento. "
                "Tareas de negocios en cierre ganado/perdido excluidas de gestión; las llamadas sí cuentan."
            ),
        }
        result = self._envelope(filters=filters, rows=rows, data=data, total_deals=total)
        _cache_set(cache_key, result)
        return result

    def group_by(self, filters: DealAnalyticsFilters, dimension: str) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        key_field, label_field = _dimension_fields(dimension)
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "open_count": 0,
                "won_count": 0,
                "lost_count": 0,
                "open_pipeline_amount": 0.0,
                "won_amount": 0.0,
            }
        )
        for row in rows:
            key = str(row.get(key_field) or "unknown")
            label = str(row.get(label_field) or key)
            groups[key]["key"] = key
            groups[key]["label"] = label
            groups[key]["count"] += 1
            if row.get("is_open"):
                groups[key]["open_count"] += 1
                groups[key]["open_pipeline_amount"] += float(row.get("amount") or 0)
            if row.get("is_won"):
                groups[key]["won_count"] += 1
                groups[key]["won_amount"] += float(row.get("amount") or 0)
            if row.get("is_lost"):
                groups[key]["lost_count"] += 1
        data = sorted(groups.values(), key=lambda item: item["count"], reverse=True)
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def age_distribution(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets_cfg = self._repo.fetch_bucket_config()
        open_rows = [r for r in rows if r.get("is_open")]
        dist = _bucket_distribution(open_rows, "age_days", "deal_age", buckets_cfg)
        ages = [int(r["age_days"]) for r in open_rows if r.get("age_days") is not None]
        data = {
            "distribution": dist,
            "average_open_deal_age_days": round(statistics.mean(ages), 1) if ages else None,
            "median_open_deal_age_days": round(statistics.median(ages), 1) if ages else None,
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def stage_age_distribution(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets_cfg = self._repo.fetch_bucket_config()
        eligible = [r for r in rows if r.get("days_in_current_stage") is not None]
        dist = _bucket_distribution(eligible, "days_in_current_stage", "stage_age", buckets_cfg)
        vals = [int(r["days_in_current_stage"]) for r in eligible]
        data = {
            "distribution": dist,
            "average_days_in_current_stage": round(statistics.mean(vals), 1) if vals else None,
            "median_days_in_current_stage": round(statistics.median(vals), 1) if vals else None,
            "data_status": "available" if eligible else "partial",
        }
        notes = [] if eligible else ["Sin historial confiable de entrada en etapa"]
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total, notes=notes)

    def inactivity_distribution(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets_cfg = self._repo.fetch_bucket_config()
        dist = _bucket_distribution(rows, "days_since_last_activity", "inactivity", buckets_cfg)
        no_activity = sum(1 for r in rows if not r.get("has_activity"))
        dist.append({"bucket": "sin_actividad", "count": no_activity})
        data = {
            "distribution": dist,
            "deals_without_activity_7d": sum(1 for r in rows if not r.get("has_recent_activity_7d")),
            "deals_without_activity_15d": sum(
                1 for r in rows if (r.get("days_since_last_activity") or 999) >= 15
            ),
            "deals_without_activity_30d": sum(1 for r in rows if not r.get("has_recent_activity_30d")),
            "deals_without_activity_60d": sum(1 for r in rows if not r.get("has_recent_activity_60d")),
            "deals_without_any_activity": no_activity,
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def activity_outcomes(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets_cfg = self._repo.fetch_bucket_config()
        activity_buckets = _outcome_by_bucket(rows, "activity_count", "activity_count", buckets_cfg)
        effective_buckets = _outcome_by_bucket(
            rows, "effective_contact_count", "effective_contact_count", buckets_cfg
        )
        data = {
            "activity_count_buckets": activity_buckets,
            "effective_contact_buckets": effective_buckets,
            "deals_with_activity": sum(1 for r in rows if r.get("has_activity")),
            "deals_without_activity": sum(1 for r in rows if not r.get("has_activity")),
            "deals_with_effective_contact": sum(1 for r in rows if r.get("has_effective_contact")),
            "deals_without_effective_contact": sum(1 for r in rows if not r.get("has_effective_contact")),
            "deals_managed_last_7d": sum(1 for r in rows if r.get("has_recent_activity_7d")),
            "deals_managed_last_30d": sum(1 for r in rows if r.get("has_recent_activity_30d")),
            "deals_managed_last_60d": sum(1 for r in rows if r.get("has_recent_activity_60d")),
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def owners(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        data = _aggregate_owners(rows)
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def owner_detail(self, owner_id: str, filters: DealAnalyticsFilters) -> dict[str, Any]:
        filters.owner_id = owner_id
        rows, total = self._filtered_rows(filters)
        owners = _aggregate_owners(rows)
        data = next((o for o in owners if str(o.get("owner_id")) == owner_id), None)
        data = {**(data or {}), "deals_sample_size": len(rows)}
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def deals(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        total_filtered = self._repo.count_filtered(filters)
        page = self._repo.fetch_filtered_page(
            filters,
            columns="*",
            offset=filters.offset,
            limit=filters.limit,
            order_by=filters.sort_by if filters.sort_by in _SORTABLE_FIELDS else "deal_id",
            ascending=filters.sort_dir != "desc",
        )
        data = {"items": page, "total": total_filtered, "limit": filters.limit, "offset": filters.offset}
        rows = page
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=self._repo.count_deals())

    def deal_detail(self, deal_id: str) -> dict[str, Any] | None:
        return self._repo.get_analytics_by_id(deal_id)

    def funnel(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        by_stage: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("stage_id") or "unknown")
            item = by_stage.setdefault(
                key,
                {
                    "stage_id": key,
                    "stage_label": row.get("stage_label") or key,
                    "display_order": row.get("stage_display_order") or 9999,
                    "count": 0,
                    "open_count": 0,
                    "won_count": 0,
                    "lost_count": 0,
                    "stale_count": 0,
                },
            )
            item["count"] += 1
            if row.get("is_open"):
                item["open_count"] += 1
            if row.get("is_won"):
                item["won_count"] += 1
            if row.get("is_lost"):
                item["lost_count"] += 1
            if row.get("is_stale"):
                item["stale_count"] += 1
        data = sorted(by_stage.values(), key=lambda x: (x["display_order"], x["stage_label"]))
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def stage_movements(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        data = {
            "deals_with_stage_changes": sum(1 for r in rows if (r.get("stage_change_count") or 0) > 0),
            "average_stage_changes_per_deal": round(
                statistics.mean([r.get("stage_change_count", 0) for r in rows]), 2
            )
            if rows
            else None,
            "median_stage_changes_per_deal": round(
                statistics.median([r.get("stage_change_count", 0) for r in rows]), 2
            )
            if rows
            else None,
            "data_status": _stage_history_coverage(rows),
        }
        notes = []
        if data["data_status"] == "partial":
            notes.append("Historial de etapas parcial; métricas de movimiento limitadas")
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total, notes=notes)

    def analysis_activity_vs_outcome(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        return self._descriptive_analysis(filters, "activity_count", "activity_count")

    def analysis_age_vs_outcome(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        return self._descriptive_analysis(filters, "age_days", "deal_age")

    def analysis_meetings_vs_outcome(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets = [
            {"label": "0 reuniones", "min": 0, "max": 0},
            {"label": "1-2 reuniones", "min": 1, "max": 2},
            {"label": "3+ reuniones", "min": 3, "max": None},
        ]
        data = _custom_outcome_buckets(rows, "completed_meeting_count", buckets)
        return self._envelope(
            filters=filters,
            rows=rows,
            data={"association_observed": data, "interpretation": "asociación observada, no causal"},
            total_deals=total,
        )

    def analysis_response_vs_outcome(self, filters: DealAnalyticsFilters) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        with_response = [r for r in rows if r.get("first_response_minutes") is not None]
        without_response = [r for r in rows if r.get("first_response_minutes") is None]
        data = {
            "with_first_response": _outcome_snapshot(with_response),
            "without_first_response": _outcome_snapshot(without_response),
            "interpretation": "diferencia descriptiva; no implica causalidad",
            "data_status": "partial" if not with_response else "available",
        }
        return self._envelope(filters=filters, rows=rows, data=data, total_deals=total)

    def filter_options(self) -> dict[str, Any]:
        config = get_hubspot_config()
        rows = self._repo.fetch_all_filtered(
            DealAnalyticsFilters(),
            columns="pipeline_id,pipeline_label,stage_id,stage_label,owner_id,owner_name,"
            "brand_value,brand_label,zone_value,zone_label,model_value,model_label,source_value,source_label",
        )
        return {
            "pipelines": _unique_options(rows, "pipeline_id", "pipeline_label"),
            "stages": _unique_options(rows, "stage_id", "stage_label"),
            "owners": _unique_options(rows, "owner_id", "owner_name"),
            "brands": _unique_options(rows, "brand_value", "brand_label"),
            "zones": _unique_options(rows, "zone_value", "zone_label"),
            "models": _unique_options(rows, "model_value", "model_label"),
            "sources": _unique_options(rows, "source_value", "source_label"),
            "statuses": [
                {"value": "open", "label": "Abierto"},
                {"value": "won", "label": "Ganado"},
                {"value": "lost", "label": "Perdido"},
                {"value": "unknown", "label": "Desconocido"},
            ],
            "age_buckets": [{"value": b["key"], "label": b["key"]} for b in get_buckets("deal_age")],
            "stage_age_buckets": [{"value": b["key"], "label": b["key"]} for b in get_buckets("stage_age")],
            "inactivity_buckets": [
                *[{"value": b["key"], "label": b["key"]} for b in get_buckets("inactivity")],
                {"value": "sin_actividad", "label": "Sin actividad registrada"},
            ],
            "metadata_snapshot_at": config.metadata_snapshot_at,
        }

    def _descriptive_analysis(
        self,
        filters: DealAnalyticsFilters,
        field: str,
        bucket_type: str,
    ) -> dict[str, Any]:
        rows, total = self._filtered_rows(filters)
        buckets_cfg = self._repo.fetch_bucket_config()
        data = _outcome_by_bucket(rows, field, bucket_type, buckets_cfg)
        return self._envelope(
            filters=filters,
            rows=rows,
            data={"buckets": data, "interpretation": "asociación observada, no causal"},
            total_deals=total,
        )


def _task_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    overdue_rank = 0 if row.get("is_overdue") else 1
    days = row.get("days_unresolved")
    days_rank = -(days if isinstance(days, int) else 0)
    return (overdue_rank, days_rank, str(row.get("subject") or row.get("task_id") or ""))


def _filter_tasks_for_management_metrics(
    tasks: list[dict[str, Any]],
    *,
    task_links: dict[str, str],
    deal_context: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Excluye tareas ligadas a negocios en cierre ganado/perdido."""
    result: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("hubspot_id") or "")
        deal_id = task_links.get(task_id)
        if deal_id and is_closed_deal_for_task_metrics(deal_context.get(deal_id)):
            continue
        result.append(task)
    return result


def _filter_tasks_with_record_link(
    tasks: list[dict[str, Any]],
    deal_links: dict[str, str],
    contact_links: dict[str, str],
) -> list[dict[str, Any]]:
    """Excluye tareas huérfanas (sin negocio ni contacto asociado)."""
    linked_ids = set(deal_links.keys()) | set(contact_links.keys())
    return [t for t in tasks if str(t.get("hubspot_id") or "") in linked_ids]


def _build_portfolio_tasks(
    tasks: list[dict[str, Any]],
    *,
    task_links: dict[str, str],
    contact_links: dict[str, str],
    deal_context: dict[str, dict[str, Any]],
    contact_names: dict[str, str],
    owner_key: str,
    brand_deal_ids: set[str],
    config: Any,
) -> tuple[list[dict[str, Any]], int, int, int]:
    now = utc_now()
    result: list[dict[str, Any]] = []
    excluded_orphan = 0
    excluded_reassigned_lead = 0
    excluded_closed_deal = 0
    seen: set[str] = set()
    for task in tasks:
        task_id = str(task.get("hubspot_id") or "")
        if not task_id or task_id in seen:
            continue
        seen.add(task_id)
        props = task.get("properties") or {}
        if is_reassigned_lead_task(task_subject_from_record(task)):
            excluded_reassigned_lead += 1
            continue
        task_owner = task.get("hubspot_owner_id") or props.get("hubspot_owner_id")
        deal_id = task_links.get(task_id)
        contact_id = contact_links.get(task_id)
        owns_task = owner_key != "unassigned" and task_owner and str(task_owner) == owner_key
        linked_to_brand_deal = bool(deal_id and deal_id in brand_deal_ids)

        if owner_key == "unassigned":
            if task_owner:
                continue
            if not linked_to_brand_deal:
                continue
        elif not owns_task:
            continue

        if not deal_id and not contact_id:
            excluded_orphan += 1
            continue

        if deal_id and is_closed_deal_for_task_metrics(deal_context.get(deal_id)):
            excluded_closed_deal += 1
            continue

        status = props.get("hs_task_status")
        is_completed = config.is_task_completed(status)
        due_raw = props.get("hs_task_due_date") or task.get("activity_timestamp")
        due_at = parse_hubspot_datetime(due_raw)
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)

        is_overdue = bool(due_at and not is_completed and due_at < now)
        is_past_due = bool(due_at and due_at < now)
        is_completed_late = bool(is_completed and is_past_due)
        days_unresolved: int | None = None
        if is_overdue and due_at:
            days_unresolved = max(0, (now - due_at).days)
        elif is_completed_late and due_at:
            days_unresolved = max(0, (now - due_at).days)
        elif not is_completed and due_at:
            days_unresolved = 0

        deal_info = deal_context.get(deal_id or "") or {}
        created_raw = task.get("created_at_hubspot") or props.get("hs_createdate")
        created_at = parse_hubspot_datetime(created_raw)
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        result.append(
            {
                "task_id": task_id,
                "subject": props.get("hs_task_subject") or f"Tarea {task_id}",
                "status": status,
                "status_label": "Completada" if is_completed else "Pendiente",
                "priority": props.get("hs_task_priority"),
                "due_at": due_at.isoformat() if due_at else None,
                "created_at": created_at.isoformat() if created_at else None,
                "is_completed": is_completed,
                "is_overdue": is_overdue,
                "is_past_due": is_past_due,
                "is_completed_late": is_completed_late,
                "days_unresolved": days_unresolved,
                "deal_id": deal_id,
                "deal_name": deal_info.get("deal_name") if deal_id else None,
                "deal_stage_label": deal_info.get("stage_label") if deal_id else None,
                "deal_commercial_group_label": deal_info.get("commercial_group_label") if deal_id else None,
                "deal_status": deal_info.get("status") if deal_id else None,
                "contact_id": contact_id,
                "contact_name": contact_names.get(contact_id or "") if contact_id else None,
            }
        )
    result.sort(key=_task_sort_key)
    return result, excluded_orphan, excluded_reassigned_lead, excluded_closed_deal


def _slim_deal_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "deal_id": row.get("deal_id"),
        "deal_name": row.get("deal_name"),
        "status": row.get("status"),
        "stage_label": row.get("stage_label"),
        "commercial_group_label": row.get("commercial_group_label"),
        "amount": row.get("amount"),
        "age_days": row.get("age_days"),
        "days_in_current_stage": row.get("days_in_current_stage"),
        "days_since_last_activity": row.get("days_since_last_activity"),
        "days_since_effective_contact": row.get("days_since_effective_contact"),
        "is_open": bool(row.get("is_open")),
        "is_stale_45d": bool(row.get("is_stale_45d")),
        "is_stale": bool(row.get("is_stale")),
        "is_unattended": bool(row.get("is_unattended")),
        "has_overdue_tasks": bool(row.get("has_overdue_tasks")),
        "has_recent_activity_30d": bool(row.get("has_recent_activity_30d")),
        "overdue_task_count": row.get("overdue_task_count") or 0,
        "open_task_count": row.get("open_task_count") or 0,
        "alert_reason": row.get("alert_reason"),
        "unattended_reason": row.get("unattended_reason"),
        "created_at": row.get("created_at"),
    }


def _deal_risk_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    open_rank = 0 if row.get("is_open") else 1
    stale_rank = 0 if row.get("is_stale_45d") else 1
    inactivity = row.get("days_since_last_activity")
    inactivity_rank = -(inactivity if isinstance(inactivity, int) else -1)
    return (open_rank, stale_rank, inactivity_rank, str(row.get("deal_name") or row.get("deal_id") or ""))


def _aggregate_advisors_from_rows(rows: list[dict[str, Any]], brand_value: str) -> list[dict[str, Any]]:
    advisors: dict[str, dict[str, Any]] = {}
    for row in rows:
        owner_id = str(row.get("owner_id") or "unassigned")
        owner_name = row.get("owner_name") or ("Sin asignar" if owner_id == "unassigned" else owner_id)
        item = advisors.setdefault(
            owner_id,
            {
                "owner_id": None if owner_id == "unassigned" else owner_id,
                "owner_name": owner_name,
                "brand_value": brand_value,
                "assigned_deals": 0,
                "open_deals": 0,
                "new_deals_7d": 0,
                "new_deals_30d": 0,
                "stale_45d_open": 0,
                "tasks_completed": 0,
                "tasks_open": 0,
                "tasks_overdue": 0,
                "deals_with_overdue_tasks": 0,
                "managed_30d": 0,
            },
        )
        item["assigned_deals"] += 1
        if not is_closed_deal_row_for_task_metrics(row):
            item["tasks_completed"] += int(row.get("completed_task_count") or 0)
            item["tasks_open"] += int(row.get("open_task_count") or 0)
            item["tasks_overdue"] += int(row.get("overdue_task_count") or 0)
            if row.get("is_open") and row.get("has_overdue_tasks"):
                item["deals_with_overdue_tasks"] += 1
        if row.get("is_open"):
            item["open_deals"] += 1
            if row.get("is_stale_45d"):
                item["stale_45d_open"] += 1
            if row.get("has_recent_activity_30d"):
                item["managed_30d"] += 1
        created = _parse_created_at(row.get("created_at"))
        if created:
            age_days = (utc_now() - created).days
            if age_days <= 7:
                item["new_deals_7d"] += 1
            if age_days <= 30:
                item["new_deals_30d"] += 1

    advisor_list = []
    for item in advisors.values():
        open_count = item["open_deals"]
        item["managed_30d_rate"] = round(item["managed_30d"] / open_count * 100, 1) if open_count else None
        item["tasks_overdue_rate"] = round(
            item["tasks_overdue"] / max(item["tasks_open"] + item["tasks_completed"], 1) * 100,
            1,
        )
        advisor_list.append(item)
    advisor_list.sort(key=lambda x: (-x["open_deals"], x["owner_name"] or ""))
    return advisor_list


def _rollup_advisor_metrics(advisors: list[dict[str, Any]]) -> dict[str, Any]:
    open_deals = sum(a["open_deals"] for a in advisors)
    managed_30d = sum(a.get("managed_30d") or 0 for a in advisors)
    return {
        "assigned_deals": sum(a["assigned_deals"] for a in advisors),
        "open_deals": open_deals,
        "new_deals_7d": sum(a["new_deals_7d"] for a in advisors),
        "new_deals_30d": sum(a["new_deals_30d"] for a in advisors),
        "stale_45d_open": sum(a["stale_45d_open"] for a in advisors),
        "tasks_completed": sum(a["tasks_completed"] for a in advisors),
        "tasks_open": sum(a["tasks_open"] for a in advisors),
        "tasks_overdue": sum(a["tasks_overdue"] for a in advisors),
        "deals_with_overdue_tasks": sum(a["deals_with_overdue_tasks"] for a in advisors),
        "managed_30d_rate": round(managed_30d / open_deals * 100, 1) if open_deals else None,
    }


def _parse_created_at(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _is_new_within_days(row: dict[str, Any], days: int) -> bool:
    created = _parse_created_at(row.get("created_at"))
    if not created:
        return False
    return (utc_now() - created).days <= days


def _weekly_deals_created(
    rows: list[dict[str, Any]],
    *,
    timezone: str,
) -> list[dict[str, Any]]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)

    def row_date(row: dict[str, Any]) -> datetime | None:
        return _parse_created_at(row.get("created_at"))

    week_keys = _week_keys_from_rows(rows, row_date=row_date, timezone=timezone)
    counts = {k: 0 for k in week_keys}
    for row in rows:
        created = row_date(row)
        if not created:
            continue
        local = created.astimezone(tz)
        key = monday_of(local.date()).isoformat()
        if key in counts:
            counts[key] += 1

    return [{"week_start": k, "deals_created": counts[k]} for k in week_keys]


def _weekly_calls_volume(
    calls: list[Any],
    *,
    timezone: str,
) -> list[dict[str, Any]]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)

    def row_date(call: Any) -> datetime | None:
        ts = getattr(call, "timestamp", None)
        if ts is None:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts

    dated_calls = [c for c in calls if row_date(c)]
    week_keys = _week_keys_from_rows(dated_calls, row_date=row_date, timezone=timezone)
    counts = {k: 0 for k in week_keys}
    for call in dated_calls:
        dt = row_date(call)
        if not dt:
            continue
        key = monday_of(dt.astimezone(tz).date()).isoformat()
        if key in counts:
            counts[key] += 1
    return [{"week_start": k, "calls": counts[k]} for k in week_keys]


def _weekly_calls_for_deals(
    repo: DealAnalyticsRepository,
    deal_ids: list[str],
    *,
    timezone: str,
    lookback_days: int = 60,
    contact_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Volumen semanal de llamadas vinculadas a negocios (ventana de sync, no todo el histórico)."""
    from datetime import timedelta

    if not deal_ids:
        return []

    deal_id_set = set(deal_ids)
    since_iso = (utc_now() - timedelta(days=lookback_days)).isoformat()
    raw_calls = repo.fetch_calls_since(since_iso)
    if not raw_calls:
        return []

    call_ids = [str(row["hubspot_id"]) for row in raw_calls if row.get("hubspot_id")]
    call_to_deals = repo.fetch_deal_links_for_calls(call_ids)
    brand_contacts = contact_ids if contact_ids is not None else repo.fetch_contact_ids_for_deals(deal_ids)
    call_to_contacts = repo.fetch_contact_links_for_calls(call_ids)

    matched_rows: list[dict[str, Any]] = []
    for row in raw_calls:
        call_id = str(row.get("hubspot_id") or "")
        if not call_id:
            continue
        if call_to_deals.get(call_id, set()) & deal_id_set:
            matched_rows.append(row)
            continue
        if brand_contacts and call_to_contacts.get(call_id, set()) & brand_contacts:
            matched_rows.append(row)

    if not matched_rows:
        return []

    duration_samples: list[float] = []
    for row in matched_rows:
        raw_dur = (row.get("properties") or {}).get("hs_call_duration")
        if raw_dur not in (None, ""):
            try:
                duration_samples.append(float(raw_dur))
            except (TypeError, ValueError):
                pass

    records = []
    for row in matched_rows:
        rec = build_activity_record(
            activity_id=str(row["hubspot_id"]),
            activity_type="calls",
            deal_id=None,
            row=row,
            duration_samples=duration_samples,
        )
        if rec:
            records.append(rec)

    return _weekly_calls_volume(records, timezone=timezone)


def _won_sales_units_summary(rows: list[dict[str, Any]], *, timezone: str) -> dict[str, Any]:
    """Unidades ganadas: total histórico, mes calendario actual y mes anterior."""
    return _monthly_period_summary(
        rows,
        date_field="closed_at",
        timezone=timezone,
        include=lambda row: bool(row.get("is_won")),
    )


def _scope_owner_activities(
    bundle: Any | None,
    owner_rows: list[dict[str, Any]],
    owner_id: str | None,
) -> tuple[list[ActivityRecord], list[ActivityRecord]]:
    if not bundle:
        return [], []
    deal_owner_map = {
        str(row["deal_id"]): normalize_owner_id(row.get("owner_id"))
        for row in owner_rows
        if row.get("deal_id")
    }
    deal_ids = set(deal_owner_map.keys())
    norm_owner = normalize_owner_id(owner_id) if owner_id else None
    scoped_calls: list[ActivityRecord] = []
    scoped_wa: list[ActivityRecord] = []

    for call in bundle.calls:
        if not call.deal_id or call.deal_id not in deal_ids:
            continue
        deal_owner = deal_owner_map.get(call.deal_id)
        if norm_owner and not activity_attributed_to_owner(call, norm_owner):
            if call.owner_id != norm_owner and deal_owner != norm_owner:
                continue
        scoped_calls.append(call)

    for msg in bundle.whatsapp:
        if not msg.deal_id or msg.deal_id not in deal_ids:
            continue
        deal_owner = deal_owner_map.get(msg.deal_id)
        if norm_owner and not activity_attributed_to_owner(msg, norm_owner):
            if msg.owner_id != norm_owner and deal_owner != norm_owner:
                continue
        scoped_wa.append(msg)

    return scoped_calls, scoped_wa


def _tasks_for_scope_rows(
    scope_rows: list[dict[str, Any]],
    *,
    tasks_raw: list[dict[str, Any]],
    task_links: dict[str, str],
) -> list[dict[str, Any]]:
    scope_deal_ids = {str(row["deal_id"]) for row in scope_rows if row.get("deal_id")}
    if not scope_deal_ids:
        return []
    return [
        task
        for task in tasks_raw
        if task_links.get(str(task.get("hubspot_id") or "")) in scope_deal_ids
    ]


def _build_performance_metrics(
    scope_rows: list[dict[str, Any]],
    rollup: dict[str, Any],
    *,
    bundle: Any | None,
    owner_id: str | None,
    tasks_raw: list[dict[str, Any]],
    task_links: dict[str, str],
    timezone: str,
    is_task_completed: Any,
) -> dict[str, Any]:
    scoped_calls, scoped_wa = _scope_owner_activities(bundle, scope_rows, owner_id)
    scope_tasks = _tasks_for_scope_rows(
        scope_rows,
        tasks_raw=tasks_raw,
        task_links=task_links,
    )
    return {
        "won_sales": _won_sales_units_summary(
            [row for row in scope_rows if row.get("is_won")],
            timezone=timezone,
        ),
        "leads_created": _monthly_period_summary(
            scope_rows,
            date_field="created_at",
            timezone=timezone,
        ),
        "tasks_overdue": int(rollup.get("tasks_overdue") or 0),
        "tasks_overdue_monthly": _monthly_overdue_tasks_summary(
            scope_tasks,
            timezone=timezone,
            is_task_completed=is_task_completed,
        ),
        "tasks_completed_monthly": _monthly_tasks_summary(
            scope_tasks,
            timezone=timezone,
            is_task_completed=is_task_completed,
            mode="completed",
        ),
        "tasks_managed_monthly": _monthly_tasks_summary(
            scope_tasks,
            timezone=timezone,
            is_task_completed=is_task_completed,
            mode="managed",
        ),
        "calls_monthly": _monthly_activity_summary(scoped_calls, timezone=timezone),
        "whatsapp_monthly": _monthly_activity_summary(scoped_wa, timezone=timezone),
    }


def _monthly_activity_summary(
    activities: list[ActivityRecord],
    *,
    timezone: str,
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    this_month_start = date(now.year, now.month, 1)
    if now.month == 1:
        prev_month_start = date(now.year - 1, 12, 1)
    else:
        prev_month_start = date(now.year, now.month - 1, 1)

    units_this_month = 0
    units_previous_month = 0

    for activity in activities:
        event_date = activity.timestamp.astimezone(tz).date()
        if event_date >= this_month_start:
            units_this_month += 1
        elif event_date >= prev_month_start:
            units_previous_month += 1

    if units_previous_month == 0:
        month_over_month_change_pct = 0.0 if units_this_month == 0 else None
    else:
        month_over_month_change_pct = round(
            (units_this_month - units_previous_month) / units_previous_month * 1000
        ) / 10

    return {
        "total_units": units_this_month + units_previous_month,
        "units_this_month": units_this_month,
        "units_previous_month": units_previous_month,
        "month_over_month_change_pct": month_over_month_change_pct,
        "this_month_key": this_month_start.isoformat()[:7],
        "previous_month_key": prev_month_start.isoformat()[:7],
    }


def _monthly_period_summary(
    rows: list[dict[str, Any]],
    *,
    date_field: str,
    timezone: str,
    include: Any = None,
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    this_month_start = date(now.year, now.month, 1)
    if now.month == 1:
        prev_month_start = date(now.year - 1, 12, 1)
    else:
        prev_month_start = date(now.year, now.month - 1, 1)

    total_units = 0
    units_this_month = 0
    units_previous_month = 0

    for row in rows:
        if include and not include(row):
            continue
        total_units += 1
        event_dt = _parse_created_at(row.get(date_field))
        if not event_dt:
            continue
        event_date = event_dt.astimezone(tz).date()
        if event_date >= this_month_start:
            units_this_month += 1
        elif event_date >= prev_month_start:
            units_previous_month += 1

    if units_previous_month == 0:
        if units_this_month == 0:
            month_over_month_change_pct = 0.0
        else:
            month_over_month_change_pct = None
    else:
        month_over_month_change_pct = round(
            (units_this_month - units_previous_month) / units_previous_month * 1000
        ) / 10

    return {
        "total_units": total_units,
        "units_this_month": units_this_month,
        "units_previous_month": units_previous_month,
        "month_over_month_change_pct": month_over_month_change_pct,
        "this_month_key": this_month_start.isoformat()[:7],
        "previous_month_key": prev_month_start.isoformat()[:7],
    }


def _monthly_overdue_tasks_summary(
    tasks: list[dict[str, Any]],
    *,
    timezone: str,
    is_task_completed: Any,
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    from app.utils.dates import parse_hubspot_datetime

    tz = ZoneInfo(timezone)
    now = utc_now()
    this_month_start = datetime.now(tz).date().replace(day=1)
    if this_month_start.month == 1:
        prev_month_start = date(this_month_start.year - 1, 12, 1)
    else:
        prev_month_start = date(this_month_start.year, this_month_start.month - 1, 1)

    units_this_month = 0
    units_previous_month = 0

    for task in tasks:
        props = task.get("properties") or {}
        if is_task_completed(props.get("hs_task_status")):
            continue
        due_raw = props.get("hs_task_due_date") or task.get("activity_timestamp")
        due_at = parse_hubspot_datetime(due_raw)
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if not due_at or due_at >= now:
            continue
        due_date = due_at.astimezone(tz).date()
        if due_date >= this_month_start:
            units_this_month += 1
        elif due_date >= prev_month_start:
            units_previous_month += 1

    if units_previous_month == 0:
        month_over_month_change_pct = 0.0 if units_this_month == 0 else None
    else:
        month_over_month_change_pct = round(
            (units_this_month - units_previous_month) / units_previous_month * 1000
        ) / 10

    return {
        "total_units": units_this_month + units_previous_month,
        "units_this_month": units_this_month,
        "units_previous_month": units_previous_month,
        "month_over_month_change_pct": month_over_month_change_pct,
        "this_month_key": this_month_start.isoformat()[:7],
        "previous_month_key": prev_month_start.isoformat()[:7],
    }


def _task_record_datetime(task: dict[str, Any], *candidates: str) -> datetime | None:
    props = task.get("properties") or {}
    for key in candidates:
        raw = task.get(key) if key in task else props.get(key)
        dt = parse_hubspot_datetime(raw)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
    return None


def _monthly_tasks_summary(
    tasks: list[dict[str, Any]],
    *,
    timezone: str,
    is_task_completed: Any,
    mode: str,
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    this_month_start = date(now.year, now.month, 1)
    if now.month == 1:
        prev_month_start = date(now.year - 1, 12, 1)
    else:
        prev_month_start = date(now.year, now.month - 1, 1)

    units_this_month = 0
    units_previous_month = 0

    for task in tasks:
        if is_reassigned_lead_task(task_subject_from_record(task)):
            continue
        props = task.get("properties") or {}
        if mode == "completed":
            if not is_task_completed(props.get("hs_task_status")):
                continue
            event_dt = _task_record_datetime(
                task,
                "activity_timestamp",
                "hs_lastmodifieddate",
                "hs_timestamp",
                "created_at_hubspot",
                "hs_createdate",
            )
        else:
            event_dt = _task_record_datetime(
                task,
                "created_at_hubspot",
                "hs_createdate",
                "activity_timestamp",
            )
        if not event_dt:
            continue
        event_date = event_dt.astimezone(tz).date()
        if event_date >= this_month_start:
            units_this_month += 1
        elif event_date >= prev_month_start:
            units_previous_month += 1

    if units_previous_month == 0:
        month_over_month_change_pct = 0.0 if units_this_month == 0 else None
    else:
        month_over_month_change_pct = round(
            (units_this_month - units_previous_month) / units_previous_month * 1000
        ) / 10

    return {
        "total_units": units_this_month + units_previous_month,
        "units_this_month": units_this_month,
        "units_previous_month": units_previous_month,
        "month_over_month_change_pct": month_over_month_change_pct,
        "this_month_key": this_month_start.isoformat()[:7],
        "previous_month_key": prev_month_start.isoformat()[:7],
    }


def _weekly_deals_closed(
    rows: list[dict[str, Any]],
    *,
    timezone: str,
    outcome: str,
) -> list[dict[str, Any]]:
    if outcome == "won":
        def include(row: dict[str, Any]) -> bool:
            return bool(row.get("is_won"))
    else:

        def include(row: dict[str, Any]) -> bool:
            return bool(row.get("is_lost"))

    return _weekly_date_series(
        rows,
        date_field="closed_at",
        timezone=timezone,
        include=include,
        count_key="deals_closed",
        amount_key="total_amount",
    )


def _week_keys_from_rows(
    rows: list[dict[str, Any]],
    *,
    row_date: Any,
    timezone: str,
) -> list[str]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    today = now.date()
    dates: list[date] = []
    for row in rows:
        dt = row_date(row)
        if dt:
            dates.append(dt.astimezone(tz).date())
    if not dates:
        return [monday_of(today).isoformat()]
    earliest = min(dates)
    latest = max(max(dates), today)
    return [d.isoformat() for d in week_starts_between(earliest, latest)]


def _weekly_date_series(
    rows: list[dict[str, Any]],
    *,
    date_field: str,
    timezone: str,
    include: Any,
    count_key: str,
    amount_key: str | None = None,
) -> list[dict[str, Any]]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)

    def row_date(row: dict[str, Any]) -> datetime | None:
        return _parse_created_at(row.get(date_field))

    filtered = [row for row in rows if not include or include(row)]
    week_keys = _week_keys_from_rows(filtered, row_date=row_date, timezone=timezone)
    counts = {k: 0 for k in week_keys}
    amounts = {k: 0.0 for k in week_keys} if amount_key else {}

    for row in filtered:
        dt = row_date(row)
        if not dt:
            continue
        local = dt.astimezone(tz)
        week_monday = monday_of(local.date()).isoformat()
        if week_monday not in counts:
            continue
        counts[week_monday] += 1
        if amount_key is not None:
            amounts[week_monday] += float(row.get("amount") or 0)

    return [
        {
            "week_start": k,
            count_key: counts[k],
            **({amount_key: round(amounts[k], 2)} if amount_key else {}),
        }
        for k in week_keys
    ]


def _weekly_overdue_tasks(
    tasks: list[dict[str, Any]],
    *,
    timezone: str,
    is_task_completed: Any,
) -> list[dict[str, Any]]:
    from zoneinfo import ZoneInfo

    from app.utils.dates import parse_hubspot_datetime

    tz = ZoneInfo(timezone)
    now = utc_now()

    def row_date(task: dict[str, Any]) -> datetime | None:
        props = task.get("properties") or {}
        due_raw = props.get("hs_task_due_date") or task.get("activity_timestamp")
        due_at = parse_hubspot_datetime(due_raw)
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        return due_at

    overdue_tasks = []
    for task in tasks:
        props = task.get("properties") or {}
        if is_reassigned_lead_task(task_subject_from_record(task)):
            continue
        if is_task_completed(props.get("hs_task_status")):
            continue
        due_at = row_date(task)
        if not due_at or due_at >= now:
            continue
        overdue_tasks.append(task)
    week_keys = _week_keys_from_rows(overdue_tasks, row_date=row_date, timezone=timezone)
    counts = {k: 0 for k in week_keys}
    for task in overdue_tasks:
        due = row_date(task)
        if not due:
            continue
        local = due.astimezone(tz)
        week_monday = monday_of(local.date()).isoformat()
        if week_monday in counts:
            counts[week_monday] += 1

    return [{"week_start": k, "tasks_overdue": counts[k]} for k in week_keys]


def _dimension_fields(dimension: str) -> tuple[str, str]:
    mapping = {
        "pipeline": ("pipeline_id", "pipeline_label"),
        "stage": ("stage_id", "stage_label"),
        "brand": ("brand_value", "brand_label"),
        "zone": ("zone_value", "zone_label"),
        "owner": ("owner_id", "owner_name"),
        "status": ("status", "status"),
        "model": ("model_value", "model_label"),
        "source": ("source_value", "source_label"),
    }
    return mapping.get(dimension, (dimension, dimension))


_SORTABLE_FIELDS = frozenset(
    {
        "deal_id",
        "deal_name",
        "amount",
        "age_days",
        "days_in_current_stage",
        "days_since_last_activity",
        "days_since_effective_contact",
        "last_activity_at",
        "created_at",
    }
)


def _status_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("status") or "unknown")] += 1
    labels = {"open": "Abierto", "won": "Ganado", "lost": "Perdido", "unknown": "Desconocido"}
    return [{"status": k, "label": labels.get(k, k), "count": v} for k, v in sorted(counts.items())]


def _aggregate_owners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        owner_id = str(row.get("owner_id") or "unassigned")
        owner_name = row.get("owner_name") or ("Sin asignar" if owner_id == "unassigned" else owner_id)
        item = groups.setdefault(
            owner_id,
            {
                "owner_id": None if owner_id == "unassigned" else owner_id,
                "owner_name": owner_name,
                "assigned_deals": 0,
                "open_deals": 0,
                "won_deals": 0,
                "lost_deals": 0,
                "open_pipeline_amount": 0.0,
                "won_amount": 0.0,
                "managed_7d": 0,
                "managed_30d": 0,
                "managed_60d": 0,
                "effective_contact_30d": 0,
                "overdue_tasks_deals": 0,
                "unattended_open_deals": 0,
                "stale_open_deals": 0,
                "no_activity_30d_open": 0,
                "no_future_task_open": 0,
                "stage_changes": 0,
            },
        )
        item["assigned_deals"] += 1
        if row.get("is_open"):
            item["open_deals"] += 1
            item["open_pipeline_amount"] += float(row.get("amount") or 0)
            if row.get("has_recent_activity_7d"):
                item["managed_7d"] += 1
            if row.get("has_recent_activity_30d"):
                item["managed_30d"] += 1
            if row.get("has_recent_activity_60d"):
                item["managed_60d"] += 1
            if row.get("has_recent_effective_contact_30d"):
                item["effective_contact_30d"] += 1
            if not row.get("has_recent_activity_30d"):
                item["no_activity_30d_open"] += 1
            if not row.get("has_future_task"):
                item["no_future_task_open"] += 1
            if row.get("is_unattended"):
                item["unattended_open_deals"] += 1
            if row.get("is_stale"):
                item["stale_open_deals"] += 1
        if row.get("is_won"):
            item["won_deals"] += 1
            item["won_amount"] += float(row.get("amount") or 0)
        if row.get("is_lost"):
            item["lost_deals"] += 1
        if row.get("is_open") and row.get("has_overdue_tasks"):
            item["overdue_tasks_deals"] += 1
        item["stage_changes"] += int(row.get("stage_change_count") or 0)

    result = []
    for item in groups.values():
        open_count = item["open_deals"]
        closed = item["won_deals"] + item["lost_deals"]
        item["managed_7d_rate"] = round(item["managed_7d"] / open_count * 100, 1) if open_count else None
        item["managed_30d_rate"] = round(item["managed_30d"] / open_count * 100, 1) if open_count else None
        item["managed_60d_rate"] = round(item["managed_60d"] / open_count * 100, 1) if open_count else None
        item["effective_contact_30d_rate"] = (
            round(item["effective_contact_30d"] / open_count * 100, 1) if open_count else None
        )
        item["close_rate"] = round(item["won_deals"] / closed * 100, 1) if closed else None
        item["discipline_score"] = _discipline_score(item)
        item["management_discipline_score"] = item["discipline_score"]
        item["effectiveness_score"] = _effectiveness_score(item)
        item["legacy_effectiveness_score"] = item["effectiveness_score"]
        item["management_status"] = _management_status(item["discipline_score"], item["effectiveness_score"])
        item["sample_size"] = item["assigned_deals"]
        item["minimum_population_met"] = item["assigned_deals"] >= 5
        result.append(item)
    return sorted(result, key=lambda x: (-(x["open_deals"] or 0), x["owner_name"] or ""))


def _discipline_score(item: dict[str, Any]) -> float | None:
    return management_discipline_score(item)


def _effectiveness_score(item: dict[str, Any]) -> float | None:
    from app.services.deal_analytics.operational_scores import compute_commercial_effectiveness_score

    closed = (item.get("won_deals") or 0) + (item.get("lost_deals") or 0)
    if closed == 0:
        return None
    commercial = compute_commercial_effectiveness_score(
        won_deals=item.get("won_deals") or 0,
        lost_deals=item.get("lost_deals") or 0,
    )
    if commercial.get("commercial_effectiveness_status") == "available":
        return commercial.get("commercial_effectiveness_score")
    close_rate = item.get("close_rate") or 0
    won_amount_norm = legacy_pipeline_effectiveness_component(
        float(item.get("won_amount") or 0),
        float(item.get("open_pipeline_amount") or 0),
    )
    return round(close_rate * 0.7 + won_amount_norm * 0.3, 1)


def _management_status(discipline: float | None, effectiveness: float | None) -> str:
    if discipline is None and effectiveness is None:
        return "Información insuficiente"
    d = discipline or 0
    e = effectiveness or 0
    if d >= 70 and e >= 50:
        return "Gestión saludable"
    if d < 50 or e < 30:
        return "Cartera en riesgo"
    return "Requiere seguimiento"


def _bucket_distribution(
    rows: list[dict[str, Any]],
    field: str,
    bucket_type: str,
    buckets_cfg: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        bucket = value_to_bucket(row.get(field), bucket_type, buckets_cfg) or "unknown"
        counts[bucket] += 1
    return [{"bucket": k, "count": v} for k, v in sorted(counts.items())]


def _outcome_by_bucket(
    rows: list[dict[str, Any]],
    field: str,
    bucket_type: str,
    buckets_cfg: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = value_to_bucket(row.get(field), bucket_type, buckets_cfg) or "unknown"
        grouped[bucket].append(row)
    result = []
    for bucket, items in sorted(grouped.items()):
        closed = [r for r in items if r.get("is_won") or r.get("is_lost")]
        won = sum(1 for r in items if r.get("is_won"))
        lost = sum(1 for r in items if r.get("is_lost"))
        result.append(
            {
                "bucket": bucket,
                "total_deals": len(items),
                "open_deals": sum(1 for r in items if r.get("is_open")),
                "won_deals": won,
                "lost_deals": lost,
                "close_rate": round(won / len(closed) * 100, 1) if closed else None,
                "won_amount": sum(float(r.get("amount") or 0) for r in items if r.get("is_won")),
            }
        )
    return result


def _custom_outcome_buckets(
    rows: list[dict[str, Any]],
    field: str,
    buckets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field) or 0
        label = "unknown"
        for bucket in buckets:
            min_v = bucket.get("min")
            max_v = bucket.get("max")
            if min_v is not None and value < min_v:
                continue
            if max_v is not None and value > max_v:
                continue
            label = str(bucket["label"])
            break
        grouped[label].append(row)
    return [
        {"bucket": bucket, **_outcome_snapshot(items)}
        for bucket, items in grouped.items()
    ]


def _outcome_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [r for r in rows if r.get("is_won") or r.get("is_lost")]
    won = sum(1 for r in rows if r.get("is_won"))
    return {
        "total_deals": len(rows),
        "open_deals": sum(1 for r in rows if r.get("is_open")),
        "won_deals": won,
        "lost_deals": sum(1 for r in rows if r.get("is_lost")),
        "close_rate": round(won / len(closed) * 100, 1) if closed else None,
        "won_amount": sum(float(r.get("amount") or 0) for r in rows if r.get("is_won")),
    }


def _unique_options(rows: list[dict[str, Any]], value_field: str, label_field: str) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for row in rows:
        value = row.get(value_field)
        if value in (None, ""):
            continue
        seen[str(value)] = str(row.get(label_field) or value)
    return [{"value": k, "label": v} for k, v in sorted(seen.items(), key=lambda item: item[1].lower())]


def _stage_history_coverage(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "unavailable"
    partial = sum(1 for r in rows if r.get("stage_history_status") == "partial")
    if partial == len(rows):
        return "partial"
    if partial > 0:
        return "mixed"
    return "available"
