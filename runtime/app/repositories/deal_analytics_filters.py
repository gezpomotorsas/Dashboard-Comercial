"""Aplicación de filtros deal_analytics a consultas Supabase."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.deal_analytics.filters import DealAnalyticsFilters, get_buckets, value_to_bucket


def apply_db_filters(query: Any, filters: DealAnalyticsFilters) -> Any:
    if filters.pipeline_id:
        query = query.eq("pipeline_id", filters.pipeline_id)
    if filters.stage_id:
        query = query.eq("stage_id", filters.stage_id)
    if filters.owner_id:
        query = query.eq("owner_id", filters.owner_id)
    if filters.status:
        query = query.eq("status", filters.status)
    if filters.brand_value:
        query = query.eq("brand_value", filters.brand_value)
    if filters.zone_value:
        query = query.eq("zone_value", filters.zone_value)
    if filters.model_value:
        query = query.eq("model_value", filters.model_value)
    if filters.source_value:
        query = query.eq("source_value", filters.source_value)
    if filters.has_contact is not None:
        query = query.eq("has_contact", filters.has_contact)
    if filters.has_owner is not None:
        query = query.eq("has_owner", filters.has_owner)
    if filters.has_amount is not None:
        query = query.eq("has_amount", filters.has_amount)
    if filters.has_activity is not None:
        query = query.eq("has_activity", filters.has_activity)
    if filters.has_effective_contact is not None:
        query = query.eq("has_effective_contact", filters.has_effective_contact)
    if filters.is_stale is not None:
        query = query.eq("is_stale", filters.is_stale)
    if filters.is_unattended is not None:
        query = query.eq("is_unattended", filters.is_unattended)
    if filters.has_overdue_tasks is not None:
        query = query.eq("has_overdue_tasks", filters.has_overdue_tasks)
    if filters.is_unknown_pipeline is not None:
        query = query.eq("is_unknown_pipeline", filters.is_unknown_pipeline)
    if filters.amount_min is not None:
        query = query.gte("amount", filters.amount_min)
    if filters.amount_max is not None:
        query = query.lte("amount", filters.amount_max)
    if filters.created_from:
        query = query.gte("created_at", _iso(filters.created_from))
    if filters.created_to:
        query = query.lte("created_at", _iso(filters.created_to))
    if filters.closed_from:
        query = query.gte("closed_at", _iso(filters.closed_from))
    if filters.closed_to:
        query = query.lte("closed_at", _iso(filters.closed_to))

    query = _apply_bucket_filter(query, filters.age_bucket, "age_days", "deal_age")
    query = _apply_bucket_filter(query, filters.stage_age_bucket, "days_in_current_stage", "stage_age")
    if filters.inactivity_bucket == "sin_actividad":
        query = query.eq("has_activity", False)
    else:
        query = _apply_bucket_filter(
            query, filters.inactivity_bucket, "days_since_last_activity", "inactivity"
        )
    query = _apply_bucket_filter(query, filters.activity_count_bucket, "activity_count", "activity_count")
    query = _apply_bucket_filter(
        query,
        filters.effective_contact_count_bucket,
        "effective_contact_count",
        "effective_contact_count",
    )
    return query


def _iso(value: datetime) -> str:
    return value.isoformat()


def _apply_bucket_filter(
    query: Any,
    bucket_key: str | None,
    field: str,
    bucket_type: str,
) -> Any:
    if not bucket_key:
        return query
    for bucket in get_buckets(bucket_type):
        if str(bucket["key"]) != bucket_key:
            continue
        min_v = bucket.get("min")
        max_v = bucket.get("max")
        if min_v is not None:
            query = query.gte(field, min_v)
        if max_v is not None:
            query = query.lte(field, max_v)
        break
    return query


def row_matches_bucket_filters(row: dict[str, Any], filters: DealAnalyticsFilters) -> bool:
    if filters.age_bucket and value_to_bucket(row.get("age_days"), "deal_age") != filters.age_bucket:
        return False
    if (
        filters.stage_age_bucket
        and value_to_bucket(row.get("days_in_current_stage"), "stage_age") != filters.stage_age_bucket
    ):
        return False
    if filters.inactivity_bucket:
        if filters.inactivity_bucket == "sin_actividad":
            if row.get("has_activity"):
                return False
        elif value_to_bucket(row.get("days_since_last_activity"), "inactivity") != filters.inactivity_bucket:
            return False
    if (
        filters.activity_count_bucket
        and value_to_bucket(row.get("activity_count", 0), "activity_count") != filters.activity_count_bucket
    ):
        return False
    if (
        filters.effective_contact_count_bucket
        and value_to_bucket(
            row.get("effective_contact_count", 0),
            "effective_contact_count",
        )
        != filters.effective_contact_count_bucket
    ):
        return False
    return True
