"""Pruebas del horario de sync automático."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.utils.sync_schedule import parse_daily_at, seconds_until_next_daily_run


def test_parse_daily_at_normalizes() -> None:
    assert parse_daily_at("3:00") == (3, 0)
    assert parse_daily_at("03:00") == (3, 0)


def test_parse_daily_at_invalid() -> None:
    with pytest.raises(ValueError):
        parse_daily_at("25:00")
    with pytest.raises(ValueError):
        parse_daily_at("bad")


def test_seconds_until_next_daily_run_same_day() -> None:
    tz = ZoneInfo("America/Bogota")
    now = datetime(2026, 6, 20, 1, 0, tzinfo=tz)
    delay = seconds_until_next_daily_run("03:00", "America/Bogota", now=now)
    assert delay == 2 * 3600


def test_seconds_until_next_daily_run_next_day() -> None:
    tz = ZoneInfo("America/Bogota")
    now = datetime(2026, 6, 20, 10, 0, tzinfo=tz)
    delay = seconds_until_next_daily_run("03:00", "America/Bogota", now=now)
    assert delay == 17 * 3600
