"""Ventana temporal para sincronización de asociaciones."""

from datetime import datetime, timedelta

from app.config import INCREMENTAL_OVERLAP_MINUTES
from app.utils.dates import overlap_timestamp, parse_hubspot_datetime, utc_now


def lookback_cutoff(lookback_days: int | None) -> datetime | None:
    if not lookback_days or lookback_days <= 0:
        return None
    return utc_now() - timedelta(days=lookback_days)


def resolve_association_modified_since(
    *,
    sync_type: str,
    lookback_days: int | None,
    cursor_last_sync: str | None = None,
) -> datetime | None:
    """Determina el filtro `updated_at_hubspot >=` para objetos origen."""
    cutoff = lookback_cutoff(lookback_days)

    if sync_type == "incremental" and cursor_last_sync:
        parsed = parse_hubspot_datetime(cursor_last_sync)
        if parsed:
            cursor_start = overlap_timestamp(parsed, INCREMENTAL_OVERLAP_MINUTES)
            if cutoff is None:
                return cursor_start
            return max(cutoff, cursor_start)

    return cutoff


def lookback_modified_since_iso(lookback_days: int | None) -> str | None:
    cutoff = lookback_cutoff(lookback_days)
    return cutoff.isoformat() if cutoff else None
