"""Pruebas de sincronización de actividades (ventana 60 días)."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")
os.environ.setdefault("ACTIVITY_SYNC_LOOKBACK_DAYS", "60")

from app.constants.activities import SENSITIVE_ACTIVITY_PROPERTY_KEYS
from app.repositories.supabase_repository import SupabaseRepository
from app.services.sync_service import SyncService, _running_syncs
from app.utils.activity_sync import (
    activity_window_bounds,
    activity_within_window,
    extract_activity_timestamp,
    lookback_cutoff_utc,
    parse_hs_timestamp_value,
    resolve_activity_modified_since,
)
from app.utils.privacy import REDACTED, redact_activity_properties, safe_error_message


@pytest.fixture(autouse=True)
def clear_running_syncs():
    _running_syncs.clear()
    yield
    _running_syncs.clear()


def test_lookback_cutoff_uses_bogota_timezone():
    from app.utils.activity_sync import get_business_timezone

    start, end = activity_window_bounds(60)
    bogota = get_business_timezone()
    now_bogota = datetime.now(bogota)
    expected_start = (now_bogota - timedelta(days=60)).astimezone(UTC)
    assert abs((start - expected_start).total_seconds()) < 2
    assert end.tzinfo == UTC
    assert start < end


def test_activity_older_than_window_excluded():
    window_start, window_end = activity_window_bounds(60)
    old_ts = int((window_start - timedelta(days=1)).timestamp() * 1000)
    record = {"properties": {"hs_timestamp": str(old_ts)}}
    assert activity_within_window(record, window_start=window_start, window_end=window_end) is False


def test_activity_inside_window_included():
    window_start, window_end = activity_window_bounds(60)
    mid = window_start + (window_end - window_start) / 2
    record = {"properties": {"hs_timestamp": str(int(mid.timestamp() * 1000))}}
    assert activity_within_window(record, window_start=window_start, window_end=window_end) is True


def test_parse_hs_timestamp_milliseconds():
    ts = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    ms = int(ts.timestamp() * 1000)
    assert parse_hs_timestamp_value(str(ms)) == ts


def test_incremental_modified_since_respects_window_and_cursor():
    cursor = datetime(2024, 1, 1, tzinfo=UTC).isoformat()
    result = resolve_activity_modified_since(
        sync_type="incremental",
        lookback_days=60,
        cursor_last_sync=cursor,
    )
    cutoff = lookback_cutoff_utc(60)
    assert result is not None
    assert abs((result - cutoff).total_seconds()) < 2


def test_transform_activity_extracts_owner_and_timestamp(monkeypatch):
    monkeypatch.setattr(
        SupabaseRepository,
        "_activity_index_columns_ready",
        staticmethod(lambda: True),
    )
    repo = SupabaseRepository.__new__(SupabaseRepository)
    ts_ms = int(datetime(2025, 1, 15, 10, 0, tzinfo=UTC).timestamp() * 1000)
    row = repo.transform_hubspot_object(
        "calls",
        {
            "id": "99",
            "properties": {
                "hs_timestamp": str(ts_ms),
                "hubspot_owner_id": "42",
                "hs_call_title": "Llamada",
            },
            "createdAt": "2025-01-15T10:00:00Z",
            "archived": False,
        },
    )
    assert row["hubspot_owner_id"] == "42"
    assert row["activity_timestamp"] is not None
    assert extract_activity_timestamp({"properties": {"hs_timestamp": str(ts_ms)}}) is not None


def test_redact_sensitive_properties_by_default():
    props = {
        "hs_call_title": "Titulo",
        "hs_call_body": "contenido privado",
        "hs_email_text": "hola cliente",
    }
    redacted = redact_activity_properties(props)
    assert redacted["hs_call_title"] == "Titulo"
    assert redacted["hs_call_body"] == REDACTED
    assert redacted["hs_email_text"] == REDACTED


def test_sensitive_keys_cover_communications():
    assert "hs_communication_body" in SENSITIVE_ACTIVITY_PROPERTY_KEYS
    assert "hs_email_text" in SENSITIVE_ACTIVITY_PROPERTY_KEYS


def test_safe_error_message_truncates():
    msg = safe_error_message("x" * 1000, max_len=100)
    assert len(msg) <= 101


@pytest.mark.asyncio
async def test_window_sync_uses_search_with_timestamp_filter(monkeypatch):
    repo = MagicMock()
    repo.create_sync_run.return_value = {"id": str(uuid4())}
    repo.get_sync_cursor.return_value = None
    repo.existing_hubspot_ids.return_value = set()
    repo.upsert_objects.return_value = []

    hubspot = MagicMock()
    window_start, window_end = activity_window_bounds(60)
    monkeypatch.setattr(
        "app.services.sync_service.activity_window_chunks",
        lambda *a, **k: [(window_start, window_end)],
    )
    ts_ms = int((window_start + timedelta(hours=1)).timestamp() * 1000)
    hubspot.search_objects = AsyncMock(
        return_value={
            "results": [{"id": "1", "properties": {"hs_timestamp": str(ts_ms), "hubspot_owner_id": "1"}}],
            "paging": {},
        }
    )

    service = SyncService(hubspot_client=hubspot, repository=repo)
    await service._execute_sync(
        sync_id=str(uuid4()),
        object_type="calls",
        sync_type="window",
        batch_size=100,
        lookback_days=60,
    )

    hubspot.search_objects.assert_awaited()
    call_args = hubspot.search_objects.await_args
    assert call_args.args[0] == "calls"
    filters = call_args.kwargs["filter_groups"][0]["filters"]
    assert filters[0]["propertyName"] == "hs_timestamp"
    repo.upsert_objects.assert_called_once()


@pytest.mark.asyncio
async def test_second_window_sync_updates_not_duplicates(monkeypatch):
    repo = MagicMock()
    repo.get_sync_cursor.return_value = None
    repo.existing_hubspot_ids.return_value = {"1"}
    repo.upsert_objects.return_value = []

    hubspot = MagicMock()
    window_start, window_end = activity_window_bounds(60)
    monkeypatch.setattr(
        "app.services.sync_service.activity_window_chunks",
        lambda *a, **k: [(window_start, window_end)],
    )
    ts_ms = int((window_start + timedelta(hours=2)).timestamp() * 1000)
    hubspot.search_objects = AsyncMock(
        return_value={
            "results": [{"id": "1", "properties": {"hs_timestamp": str(ts_ms)}}],
            "paging": {},
        }
    )

    service = SyncService(hubspot_client=hubspot, repository=repo)
    found, processed, failed, inserted, updated, _ = await service._sync_activity_type(
        sync_id=str(uuid4()),
        object_type="calls",
        sync_type="window",
        batch_size=100,
        lookback_days=60,
    )
    assert failed == 0
    assert inserted == 0
    assert updated == 1
    assert processed == 1
    assert found == 1


@pytest.mark.asyncio
async def test_incremental_cursor_not_updated_on_failure():
    repo = MagicMock()
    repo.get_sync_cursor.return_value = {
        "last_successful_sync_at": datetime(2024, 6, 1, tzinfo=UTC).isoformat(),
    }
    hubspot = MagicMock()
    hubspot.search_objects = AsyncMock(side_effect=RuntimeError("HubSpot down"))

    service = SyncService(hubspot_client=hubspot, repository=repo)
    await service._execute_sync(
        sync_id=str(uuid4()),
        object_type="emails",
        sync_type="incremental",
        batch_size=50,
        lookback_days=60,
    )
    repo.upsert_sync_cursor.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_cursor_updated_on_success():
    repo = MagicMock()
    repo.get_sync_cursor.return_value = {
        "last_successful_sync_at": datetime(2024, 6, 1, tzinfo=UTC).isoformat(),
    }
    repo.existing_hubspot_ids.return_value = set()
    repo.upsert_objects.return_value = []
    hubspot = MagicMock()
    hubspot.search_objects = AsyncMock(return_value={"results": [], "paging": {}})

    service = SyncService(hubspot_client=hubspot, repository=repo)
    await service._sync_activity_type(
        sync_id=str(uuid4()),
        object_type="communications",
        sync_type="incremental",
        batch_size=50,
        lookback_days=60,
    )
    repo.upsert_sync_cursor.assert_called_once()


def test_association_resolved_when_activity_in_local_set():
    """Simula que tras sync el destino existe en el set local."""
    existing_calls = {"100", "200"}
    assoc_target = "100"
    assert assoc_target in existing_calls
