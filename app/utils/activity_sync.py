"""Ventana temporal de actividades (zona America/Bogota → UTC)."""

from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import INCREMENTAL_OVERLAP_MINUTES, get_settings
from app.utils.dates import hubspot_ms_timestamp, overlap_timestamp, parse_hubspot_datetime

# Fallback fijo UTC-5 si tzdata no está instalado (p. ej. Windows sin paquete)
_BOGOTA_FALLBACK = timezone(timedelta(hours=-5))


@lru_cache
def get_business_timezone() -> ZoneInfo | timezone:
    settings = get_settings()
    try:
        return ZoneInfo(settings.business_timezone)
    except ZoneInfoNotFoundError:
        return _BOGOTA_FALLBACK


def business_now() -> datetime:
    return datetime.now(get_business_timezone())


def activity_window_bounds(lookback_days: int) -> tuple[datetime, datetime]:
    """Retorna (desde, hasta) en UTC para la ventana móvil de N días en Bogotá."""
    end_bogota = business_now()
    start_bogota = end_bogota - timedelta(days=lookback_days)
    return start_bogota.astimezone(UTC), end_bogota.astimezone(UTC)


def lookback_cutoff_utc(lookback_days: int) -> datetime:
    start, _ = activity_window_bounds(lookback_days)
    return start


def resolve_activity_modified_since(
    *,
    sync_type: str,
    lookback_days: int,
    cursor_last_sync: str | None = None,
) -> datetime | None:
    """Filtro para búsqueda incremental: max(ventana, cursor - overlap)."""
    cutoff = lookback_cutoff_utc(lookback_days)

    if sync_type == "incremental" and cursor_last_sync:
        parsed = parse_hubspot_datetime(cursor_last_sync)
        if parsed:
            cursor_start = overlap_timestamp(parsed, INCREMENTAL_OVERLAP_MINUTES)
            return max(cutoff, cursor_start)

    if sync_type in ("window", "full"):
        return cutoff

    return None


def parse_hs_timestamp_value(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)
    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000.0, tz=UTC)
    return parse_hubspot_datetime(text)


def extract_activity_timestamp(record: dict[str, Any]) -> datetime | None:
    props = record.get("properties") or {}
    ts = parse_hs_timestamp_value(props.get("hs_timestamp"))
    if ts is not None:
        return ts
    return parse_hubspot_datetime(record.get("createdAt"))


def activity_within_window(
    record: dict[str, Any],
    *,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    ts = extract_activity_timestamp(record)
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return window_start <= ts <= window_end


def activity_window_chunks(lookback_days: int, *, chunk_days: int = 10) -> list[tuple[datetime, datetime]]:
    """Divide la ventana en sub-rangos para evitar el límite de 10k de búsqueda HubSpot."""
    start, end = activity_window_bounds(lookback_days)
    chunks: list[tuple[datetime, datetime]] = []
    cursor = start
    step = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + step, end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


def chunk_days_for_activity(object_type: str) -> int:
    if object_type in ("tasks", "notes"):
        return 7
    return 10


def build_timestamp_filter_groups(
    *,
    gte: datetime,
    lte: datetime | None = None,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {
            "propertyName": "hs_timestamp",
            "operator": "GTE",
            "value": str(hubspot_ms_timestamp(gte)),
        }
    ]
    if lte is not None:
        filters.append(
            {
                "propertyName": "hs_timestamp",
                "operator": "LTE",
                "value": str(hubspot_ms_timestamp(lte)),
            }
        )
    return [{"filters": filters}]


def is_activity_object_type(object_type: str) -> bool:
    from app.constants.activities import ACTIVITY_SYNC_ORDER

    return object_type in ACTIVITY_SYNC_ORDER
