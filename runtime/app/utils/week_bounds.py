"""Semanas comerciales en America/Bogota (lunes 00:00, exclusivo al lunes siguiente)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")


def bogota_now() -> datetime:
    return datetime.now(BOGOTA)


def monday_of(date_value: date) -> date:
    return date_value - timedelta(days=date_value.weekday())


def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    """Retorna (inicio, fin) en UTC. Fin exclusivo."""
    start_local = datetime.combine(week_start, time.min, tzinfo=BOGOTA)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def parse_week_start(value: str) -> date:
    parsed = date.fromisoformat(value)
    return monday_of(parsed)


def recent_week_starts(count: int = 8, *, anchor: date | None = None) -> list[date]:
    anchor = anchor or bogota_now().date()
    current = monday_of(anchor)
    return [current - timedelta(weeks=i) for i in range(count - 1, -1, -1)]


def week_starts_between(earliest: date, latest: date) -> list[date]:
    """Semanas (lunes) desde earliest hasta latest, inclusive."""
    start = monday_of(earliest)
    end = monday_of(latest)
    if start > end:
        start, end = end, start
    weeks: list[date] = []
    current = start
    while current <= end:
        weeks.append(current)
        current += timedelta(weeks=1)
    return weeks


def in_range(ts: datetime | None, start: datetime, end: datetime) -> bool:
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return start <= ts < end
