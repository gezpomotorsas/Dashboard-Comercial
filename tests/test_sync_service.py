"""Pruebas del servicio de sincronización."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.services.sync_service import SyncService, _running_syncs


@pytest.fixture(autouse=True)
def clear_running_syncs():
    _running_syncs.clear()
    yield
    _running_syncs.clear()


@pytest.fixture
def mock_repository():
    repo = MagicMock()
    sync_id = str(uuid4())
    repo.create_sync_run.return_value = {"id": sync_id, "status": "started"}
    repo.get_sync_cursor.return_value = {
        "object_type": "contacts",
        "last_successful_sync_at": datetime(2024, 6, 1, tzinfo=UTC).isoformat(),
    }
    return repo


@pytest.fixture
def mock_hubspot():
    client = MagicMock()
    client.get = AsyncMock(
        return_value={
            "results": [{"id": "1", "properties": {}, "archived": False}],
            "paging": {},
        }
    )
    return client


def test_upsert_called(mock_repository):
    repo = SupabaseRepositoryMock()
    rows = [{"id": "1", "properties": {}, "archived": False}]
    repo.upsert_objects("contacts", rows)
    assert repo.upsert_calls == 1
    assert repo.last_rows[0]["hubspot_id"] == "1"


def test_upsert_idempotent(mock_repository):
    repo = SupabaseRepositoryMock()
    row = {"id": "1", "properties": {"email": "a@b.com"}, "archived": False}
    repo.upsert_objects("contacts", [row])
    repo.upsert_objects("contacts", [row])
    assert repo.upsert_calls == 2
    assert len(repo.stored) == 1


def test_sync_run_created(mock_repository):
    run = mock_repository.create_sync_run(object_type="contacts", sync_type="full", metadata={})
    assert run["status"] == "started"
    mock_repository.create_sync_run.assert_called_once()


def test_sync_error_recorded(mock_repository):
    mock_repository.create_sync_error(
        sync_run_id=str(uuid4()),
        object_type="contacts",
        hubspot_id="99",
        error_type="HubSpotRequestError",
        error_message="fail",
    )
    mock_repository.create_sync_error.assert_called_once()


def test_cursor_incremental_overlap():
    from app.utils.dates import overlap_timestamp

    base = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    overlapped = overlap_timestamp(base, 15)
    assert overlapped < base


@pytest.mark.asyncio
async def test_cursor_not_updated_on_failure(mock_repository):
    mock_repository.upsert_sync_cursor = MagicMock()
    mock_repository.update_sync_run = MagicMock()

    mock_hubspot = MagicMock()
    mock_hubspot.search_objects = AsyncMock(side_effect=RuntimeError("HubSpot down"))

    service = SyncService(hubspot_client=mock_hubspot, repository=mock_repository)

    await service._execute_sync(
        sync_id=str(uuid4()),
        object_type="contacts",
        sync_type="incremental",
        batch_size=10,
        lookback_days=None,
    )

    mock_repository.upsert_sync_cursor.assert_not_called()


@pytest.mark.asyncio
async def test_sync_lock_released_on_create_failure(mock_repository):
    mock_repository.create_sync_run.side_effect = RuntimeError("db down")

    service = SyncService(hubspot_client=MagicMock(), repository=mock_repository)

    with pytest.raises(RuntimeError):
        await service.start_sync(object_type="contacts", sync_type="full", batch_size=10)

    assert "contacts" not in _running_syncs


@pytest.mark.asyncio
async def test_cursor_updated_on_success(mock_repository, mock_hubspot):
    mock_hubspot.search_objects = AsyncMock(return_value={"results": [], "paging": {}})
    mock_repository.upsert_sync_cursor = MagicMock()
    mock_repository.existing_hubspot_ids.return_value = set()

    service = SyncService(hubspot_client=mock_hubspot, repository=mock_repository)

    await service._sync_crm_object_type(
        sync_id=str(uuid4()),
        object_type="contacts",
        sync_type="incremental",
        batch_size=10,
    )

    mock_repository.upsert_sync_cursor.assert_called_once()


class SupabaseRepositoryMock:
    def __init__(self):
        self.upsert_calls = 0
        self.stored: dict[str, dict] = {}
        self.last_rows: list[dict] = []

    def upsert_objects(self, object_type: str, records: list[dict]):
        self.upsert_calls += 1
        from app.repositories.supabase_repository import SupabaseRepository

        repo = SupabaseRepository.__new__(SupabaseRepository)
        rows = [repo.transform_hubspot_object(object_type, r) for r in records]
        self.last_rows = rows
        for row in rows:
            self.stored[row["hubspot_id"]] = row
        return rows
