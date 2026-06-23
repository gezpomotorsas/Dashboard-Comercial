"""Filtros compartidos para deal analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DealAnalyticsFilters(BaseModel):
    pipeline_id: str | None = None
    stage_id: str | None = None
    owner_id: str | None = None
    status: str | None = None
    brand_value: str | None = None
    zone_value: str | None = None
    model_value: str | None = None
    source_value: str | None = None
    age_bucket: str | None = None
    stage_age_bucket: str | None = None
    inactivity_bucket: str | None = None
    activity_count_bucket: str | None = None
    effective_contact_count_bucket: str | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    closed_from: datetime | None = None
    closed_to: datetime | None = None
    has_contact: bool | None = None
    has_owner: bool | None = None
    has_amount: bool | None = None
    has_activity: bool | None = None
    has_effective_contact: bool | None = None
    is_stale: bool | None = None
    is_unattended: bool | None = None
    has_overdue_tasks: bool | None = None
    has_future_task: bool | None = None
    is_unknown_pipeline: bool | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = "deal_id"
    sort_dir: str = "asc"


def apply_deal_filters(rows: list[dict[str, Any]], filters: DealAnalyticsFilters) -> list[dict[str, Any]]:
    result = rows
    if filters.pipeline_id:
        result = [r for r in result if r.get("pipeline_id") == filters.pipeline_id]
    if filters.stage_id:
        result = [r for r in result if r.get("stage_id") == filters.stage_id]
    if filters.owner_id:
        result = [r for r in result if r.get("owner_id") == filters.owner_id]
    if filters.status:
        result = [r for r in result if r.get("status") == filters.status]
    if filters.brand_value:
        result = [r for r in result if r.get("brand_value") == filters.brand_value]
    if filters.zone_value:
        result = [r for r in result if r.get("zone_value") == filters.zone_value]
    if filters.model_value:
        result = [r for r in result if r.get("model_value") == filters.model_value]
    if filters.source_value:
        result = [r for r in result if r.get("source_value") == filters.source_value]
    if filters.has_contact is not None:
        result = [r for r in result if bool(r.get("has_contact")) == filters.has_contact]
    if filters.has_owner is not None:
        result = [r for r in result if bool(r.get("has_owner")) == filters.has_owner]
    if filters.has_amount is not None:
        result = [r for r in result if bool(r.get("has_amount")) == filters.has_amount]
    if filters.has_activity is not None:
        result = [r for r in result if bool(r.get("has_activity")) == filters.has_activity]
    if filters.has_effective_contact is not None:
        result = [r for r in result if bool(r.get("has_effective_contact")) == filters.has_effective_contact]
    if filters.is_stale is not None:
        result = [r for r in result if bool(r.get("is_stale")) == filters.is_stale]
    if filters.is_unattended is not None:
        result = [r for r in result if bool(r.get("is_unattended")) == filters.is_unattended]
    if filters.has_overdue_tasks is not None:
        result = [r for r in result if bool(r.get("has_overdue_tasks")) == filters.has_overdue_tasks]
    if filters.has_future_task is not None:
        result = [r for r in result if bool(r.get("has_future_task")) == filters.has_future_task]
    if filters.is_unknown_pipeline is not None:
        result = [r for r in result if bool(r.get("is_unknown_pipeline")) == filters.is_unknown_pipeline]
    if filters.amount_min is not None:
        result = [r for r in result if (r.get("amount") or 0) >= filters.amount_min]
    if filters.amount_max is not None:
        result = [r for r in result if (r.get("amount") or 0) <= filters.amount_max]
    if filters.created_from:
        result = [
            r for r in result
            if r.get("created_at") and _parse_dt(r["created_at"]) >= filters.created_from
        ]
    if filters.created_to:
        result = [
            r for r in result
            if r.get("created_at") and _parse_dt(r["created_at"]) <= filters.created_to
        ]
    if filters.closed_from:
        result = [
            r for r in result
            if r.get("closed_at") and _parse_dt(r["closed_at"]) >= filters.closed_from
        ]
    if filters.closed_to:
        result = [
            r for r in result
            if r.get("closed_at") and _parse_dt(r["closed_at"]) <= filters.closed_to
        ]
    if filters.age_bucket:
        result = [r for r in result if _bucket_match(r.get("age_days"), filters.age_bucket, "deal_age")]
    if filters.stage_age_bucket:
        result = [
            r for r in result if _bucket_match(r.get("days_in_current_stage"), filters.stage_age_bucket, "stage_age")
        ]
    if filters.inactivity_bucket:
        if filters.inactivity_bucket == "sin_actividad":
            result = [r for r in result if not r.get("has_activity")]
        else:
            result = [
                r for r in result
                if _bucket_match(r.get("days_since_last_activity"), filters.inactivity_bucket, "inactivity")
            ]
    if filters.activity_count_bucket:
        result = [
            r for r in result
            if _bucket_match(r.get("activity_count", 0), filters.activity_count_bucket, "activity_count")
        ]
    if filters.effective_contact_count_bucket:
        result = [
            r for r in result
            if _bucket_match(
                r.get("effective_contact_count", 0),
                filters.effective_contact_count_bucket,
                "effective_contact_count",
            )
        ]
    return result


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


_DEFAULT_BUCKETS: dict[str, list[dict[str, Any]]] = {
    "deal_age": [
        {"key": "0-30", "min": 0, "max": 30},
        {"key": "31-60", "min": 31, "max": 60},
        {"key": "61-90", "min": 61, "max": 90},
        {"key": "91-180", "min": 91, "max": 180},
        {"key": "181-365", "min": 181, "max": 365},
        {"key": "366+", "min": 366, "max": None},
    ],
    "stage_age": [
        {"key": "0-7", "min": 0, "max": 7},
        {"key": "8-15", "min": 8, "max": 15},
        {"key": "16-30", "min": 16, "max": 30},
        {"key": "31-60", "min": 31, "max": 60},
        {"key": "61-90", "min": 61, "max": 90},
        {"key": "91+", "min": 91, "max": None},
    ],
    "inactivity": [
        {"key": "0-7", "min": 0, "max": 7},
        {"key": "8-15", "min": 8, "max": 15},
        {"key": "16-30", "min": 16, "max": 30},
        {"key": "31-60", "min": 31, "max": 60},
        {"key": "61-90", "min": 61, "max": 90},
        {"key": "91+", "min": 91, "max": None},
    ],
    "activity_count": [
        {"key": "0", "min": 0, "max": 0},
        {"key": "1-2", "min": 1, "max": 2},
        {"key": "3-5", "min": 3, "max": 5},
        {"key": "6-10", "min": 6, "max": 10},
        {"key": "11-20", "min": 11, "max": 20},
        {"key": "21+", "min": 21, "max": None},
    ],
    "effective_contact_count": [
        {"key": "0", "min": 0, "max": 0},
        {"key": "1", "min": 1, "max": 1},
        {"key": "2-3", "min": 2, "max": 3},
        {"key": "4-5", "min": 4, "max": 5},
        {"key": "6+", "min": 6, "max": None},
    ],
}


def get_buckets(bucket_type: str, configured: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    if configured and bucket_type in configured:
        return configured[bucket_type]
    return _DEFAULT_BUCKETS.get(bucket_type, [])


def value_to_bucket(value: int | float | None, bucket_type: str, configured: dict | None = None) -> str | None:
    if value is None:
        return None
    for bucket in get_buckets(bucket_type, configured):
        min_v = bucket.get("min")
        max_v = bucket.get("max")
        if min_v is not None and value < min_v:
            continue
        if max_v is not None and value > max_v:
            continue
        return str(bucket["key"])
    return None


def _bucket_match(value: int | float | None, bucket_key: str, bucket_type: str) -> bool:
    return value_to_bucket(value, bucket_type) == bucket_key
