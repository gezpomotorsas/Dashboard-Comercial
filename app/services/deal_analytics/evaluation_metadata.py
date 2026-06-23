"""Metadata de frescura y trazabilidad para respuestas de evaluación."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.services.deal_analytics.evaluation_config import get_evaluation_settings


def build_evaluation_metadata(
    *,
    cache_generated_at: datetime | None = None,
    cache_expires_at: datetime | None = None,
    deal_analytics_last_refresh_at: datetime | None = None,
    hubspot_last_sync_at: datetime | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    eval_cfg = get_evaluation_settings()
    return {
        "calculation_at": now.isoformat(),
        "cache_generated_at": cache_generated_at.isoformat() if cache_generated_at else None,
        "cache_expires_at": cache_expires_at.isoformat() if cache_expires_at else None,
        "deal_analytics_last_refresh_at": (
            deal_analytics_last_refresh_at.isoformat() if deal_analytics_last_refresh_at else None
        ),
        "hubspot_last_sync_at": hubspot_last_sync_at.isoformat() if hubspot_last_sync_at else None,
        "available_activity_history_start": (
            now.replace(hour=0, minute=0, second=0, microsecond=0)
            - __import__("datetime").timedelta(days=settings.activity_sync_lookback_days)
        ).isoformat(),
        "activity_lookback_days": settings.activity_sync_lookback_days,
        "contact_window_days": settings.contact_coverage_window_days,
        "business_timezone": settings.business_timezone,
        "methodology_version": "2.0",
        "evaluation_config": eval_cfg,
    }
