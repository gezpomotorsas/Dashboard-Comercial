"""Cálculo de la próxima ejecución del sync automático."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_DAILY_AT_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_daily_at(value: str) -> tuple[int, int]:
    match = _DAILY_AT_RE.match(value.strip())
    if not match:
        raise ValueError("AUTO_SYNC_DAILY_AT debe tener formato HH:MM (ej. 03:00)")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("AUTO_SYNC_DAILY_AT fuera de rango (hora 0-23, minutos 0-59)")
    return hour, minute


def seconds_until_next_daily_run(daily_at: str, timezone_name: str, *, now: datetime | None = None) -> float:
    hour, minute = parse_daily_at(daily_at)
    tz = ZoneInfo(timezone_name)
    current = (now or datetime.now(tz)).astimezone(tz)
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return max(0.0, (target - current).total_seconds())
