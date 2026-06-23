"""Utilidades de fechas."""

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_hubspot_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def to_iso8601(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_hubspot_datetime(value)
        if parsed is None:
            return value
        value = parsed
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def overlap_timestamp(base: datetime, minutes: int = 15) -> datetime:
    return base - timedelta(minutes=minutes)


def hubspot_ms_timestamp(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)
