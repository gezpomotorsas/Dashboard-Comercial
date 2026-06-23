"""Pruebas de ventana temporal en sync de asociaciones."""

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.utils.association_sync import (
    lookback_cutoff,
    resolve_association_modified_since,
)


def test_full_sync_uses_lookback_only():
    cutoff = resolve_association_modified_since(sync_type="full", lookback_days=60)
    assert cutoff is not None
    assert cutoff > datetime.now(UTC) - timedelta(days=61)


def test_full_sync_no_lookback_when_zero():
    assert resolve_association_modified_since(sync_type="full", lookback_days=0) is None


def test_incremental_uses_later_of_cursor_and_lookback():
    old_cursor = "2020-01-01T00:00:00+00:00"
    result = resolve_association_modified_since(
        sync_type="incremental",
        lookback_days=60,
        cursor_last_sync=old_cursor,
    )
    lookback = lookback_cutoff(60)
    assert result is not None
    assert abs((result - lookback).total_seconds()) < 1


def test_incremental_cursor_newer_than_lookback():
    recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    result = resolve_association_modified_since(
        sync_type="incremental",
        lookback_days=60,
        cursor_last_sync=recent,
    )
    assert result is not None
    assert result > lookback_cutoff(60)  # type: ignore[operator]
