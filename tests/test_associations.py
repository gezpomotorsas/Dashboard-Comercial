"""Pruebas de asociaciones."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.repositories.associations_repository import (
    AssociationsRepository,
    _dedupe_association_rows,
)
from app.services.associations_service import (
    AssociationLabelCache,
    parse_batch_association_results,
)
from app.services.associations_sync_service import (
    AssociationsSyncService,
    AssociationSyncAlreadyRunningError,
    _is_empty_association_batch_error,
    _running_association_syncs,
)


@pytest.fixture(autouse=True)
def clear_association_locks():
    _running_association_syncs.clear()
    yield
    _running_association_syncs.clear()


def test_parse_batch_contact_deal():
    cache = AssociationLabelCache()
    cache._cache[("contacts", "deals")] = {3: {"label": "Primary"}}
    payload = {
        "results": [
            {
                "from": {"id": "1"},
                "to": [
                    {
                        "toObjectId": "99",
                        "associationTypes": [{"category": "HUBSPOT_DEFINED", "typeId": 3}],
                    }
                ],
            }
        ]
    }
    records = parse_batch_association_results(
        from_object_type="contacts",
        to_object_type="deals",
        payload=payload,
        label_cache=cache,
    )
    assert len(records) == 1
    assert records[0].from_hubspot_id == "1"
    assert records[0].to_hubspot_id == "99"
    assert records[0].association_label == "Primary"


def test_parse_batch_null_label():
    cache = AssociationLabelCache()
    payload = {
        "results": [
            {
                "from": {"id": "1"},
                "to": [
                    {
                        "toObjectId": "2",
                        "associationTypes": [{"category": "USER_DEFINED", "typeId": 99, "label": None}],
                    }
                ],
            }
        ]
    }
    records = parse_batch_association_results(
        from_object_type="contacts",
        to_object_type="calls",
        payload=payload,
        label_cache=cache,
    )
    assert records[0].association_label is None


def test_transform_association():
    repo = AssociationsRepository.__new__(AssociationsRepository)
    row = repo.transform_association(
        from_object_type="contacts",
        from_hubspot_id="1",
        to_object_type="deals",
        to_hubspot_id="2",
        association_type_id=3,
        association_category="HUBSPOT_DEFINED",
        association_label=None,
    )
    assert row["from_object_type"] == "contacts"
    assert row["is_active"] is True
    assert row["last_seen_at"] is not None


def test_empty_association_batch_error_is_ignored():
    assert _is_empty_association_batch_error(
        "No deal is associated with contact 133451885275."
    )
    assert not _is_empty_association_batch_error("Rate limit exceeded")


def test_dedupe_association_rows_same_batch():
    rows = [
        {
            "from_object_type": "contacts",
            "from_hubspot_id": "1",
            "to_object_type": "deals",
            "to_hubspot_id": "9",
            "association_type_id": 3,
            "association_label": None,
        },
        {
            "from_object_type": "contacts",
            "from_hubspot_id": "1",
            "to_object_type": "deals",
            "to_hubspot_id": "9",
            "association_type_id": 3,
            "association_label": "Primary",
        },
    ]
    deduped = _dedupe_association_rows(rows)
    assert len(deduped) == 1
    assert deduped[0]["association_label"] == "Primary"


@pytest.mark.asyncio
async def test_association_sync_lock_on_running():
    _running_association_syncs.add("associations:contact-deal")
    service = AssociationsSyncService(hubspot_client=MagicMock(), repository=MagicMock())
    with pytest.raises(AssociationSyncAlreadyRunningError):
        await service.start_sync(sync_group="contact-deal", sync_type="full", batch_size=10)


@pytest.mark.asyncio
async def test_association_sync_releases_lock_on_create_failure():
    repo = MagicMock()
    repo.create_sync_run.side_effect = RuntimeError("db")
    service = AssociationsSyncService(hubspot_client=MagicMock(), repository=repo)
    with pytest.raises(RuntimeError):
        await service.start_sync(sync_group="contact-deal", sync_type="full", batch_size=10)
    assert "associations:contact-deal" not in _running_association_syncs


@pytest.mark.asyncio
async def test_hubspot_batch_read_called(monkeypatch):
    repo = MagicMock()
    repo.create_sync_run.return_value = {"id": "sync-1"}
    repo.iter_hubspot_ids.return_value = iter([["101", "102"]])
    repo.transform_association.side_effect = lambda **kw: kw

    client = MagicMock()
    client.batch_read_associations = AsyncMock(
        return_value={"results": [], "errors": []}
    )

    service = AssociationsSyncService(hubspot_client=client, repository=repo)
    monkeypatch.setattr(
        "app.services.associations_sync_service.AssociationLabelCache.load",
        AsyncMock(),
    )

    await service._execute_sync(
        sync_id="sync-1",
        sync_group="contact-deal",
        sync_type="full",
        batch_size=100,
    )

    assert client.batch_read_associations.await_count >= 1
    repo.upsert_associations.assert_not_called()
    repo.deactivate_associations_for_source.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_calls_deactivate(monkeypatch):
    repo = MagicMock()
    repo.create_sync_run.return_value = {"id": "sync-1"}
    repo.get_sync_cursor.return_value = None
    repo.iter_hubspot_ids.return_value = iter([["101"]])
    repo.transform_association.side_effect = lambda **kw: {
        "from_object_type": kw["from_object_type"],
        "from_hubspot_id": kw["from_hubspot_id"],
        "to_object_type": kw["to_object_type"],
        "to_hubspot_id": kw["to_hubspot_id"],
        "association_type_id": kw["association_type_id"],
    }

    client = MagicMock()
    client.batch_read_associations = AsyncMock(
        return_value={
            "results": [
                {
                    "from": {"id": "101"},
                    "to": [
                        {
                            "toObjectId": "201",
                            "associationTypes": [{"category": "HUBSPOT_DEFINED", "typeId": 3}],
                        }
                    ],
                }
            ],
            "errors": [],
        }
    )

    service = AssociationsSyncService(hubspot_client=client, repository=repo)
    monkeypatch.setattr(
        "app.services.associations_sync_service.AssociationLabelCache.load",
        AsyncMock(),
    )

    await service._execute_sync(
        sync_id="sync-1",
        sync_group="contact-deal",
        sync_type="incremental",
        batch_size=100,
    )

    repo.deactivate_associations_for_source.assert_called()


@pytest.mark.asyncio
async def test_parallel_hubspot_calls_for_activity_group(monkeypatch):
    repo = MagicMock()
    repo.create_sync_run.return_value = {"id": "sync-1"}
    repo.iter_hubspot_ids.return_value = iter([["101"]])
    repo.transform_association.side_effect = lambda **kw: kw

    client = MagicMock()
    client.batch_read_associations = AsyncMock(return_value={"results": [], "errors": []})

    service = AssociationsSyncService(hubspot_client=client, repository=repo)
    monkeypatch.setattr(
        "app.services.associations_sync_service.AssociationLabelCache.load",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.associations_sync_service.get_settings",
        lambda: type(
            "S",
            (),
            {
                "allow_full_phase2_validation": True,
                "phase2_validation_sample_size": 50,
                "association_sync_lookback_days": 0,
                "association_sync_lookback_field": "created_at_hubspot",
                "association_sync_hubspot_concurrency": 6,
            },
        )(),
    )

    await service._execute_sync(
        sync_id="sync-1",
        sync_group="contact-activities",
        sync_type="full",
        batch_size=100,
    )

    assert client.batch_read_associations.await_count == 6
