"""Sincronización de asociaciones HubSpot → Supabase."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import HubSpotClientError
from app.config import get_settings
from app.constants.associations import (
    HUBSPOT_BATCH_ASSOCIATION_LIMIT,
    SOURCE_OBJECT_TYPES_BY_GROUP,
    SYNC_GROUP_PAIRS,
)
from app.repositories.associations_repository import AssociationsRepository
from app.services.associations_service import AssociationLabelCache, parse_batch_association_results
from app.utils.association_sync import resolve_association_modified_since
from app.utils.dates import utc_now

logger = logging.getLogger(__name__)

_running_association_syncs: set[str] = set()
_association_lock = asyncio.Lock()


def _is_empty_association_batch_error(message: str) -> bool:
    """HubSpot devuelve este mensaje cuando el objeto no tiene asociaciones."""
    lowered = message.lower()
    return " is associated with " in lowered and lowered.startswith("no ")

OBJECT_TABLE_BY_TYPE = {
    "contacts": "hubspot_contacts",
    "deals": "hubspot_deals",
}


class AssociationSyncAlreadyRunningError(Exception):
    pass


class AssociationsSyncService:
    def __init__(
        self,
        hubspot_client: HubSpotClient | None = None,
        repository: AssociationsRepository | None = None,
    ) -> None:
        self._hubspot = hubspot_client
        self._repository = repository or AssociationsRepository()
        self._settings = get_settings()

    @property
    def hubspot(self) -> HubSpotClient:
        if self._hubspot is None:
            raise RuntimeError("HubSpot client not configured")
        return self._hubspot

    async def start_sync(
        self,
        *,
        sync_group: str,
        sync_type: str,
        batch_size: int,
        object_offset: int = 0,
        object_limit: int | None = None,
    ) -> dict[str, Any]:
        key = f"associations:{sync_group}"
        async with _association_lock:
            if key in _running_association_syncs:
                raise AssociationSyncAlreadyRunningError(
                    f"Sincronización de asociaciones {sync_group} ya está en ejecución"
                )
            _running_association_syncs.add(key)

        object_type = f"associations:{sync_group}"
        lookback_days = self._settings.association_sync_lookback_days
        cursor_key = f"associations:{sync_group}"
        cursor_last: str | None = None
        if sync_type == "incremental":
            cursor = self._repository.get_sync_cursor(cursor_key)
            if cursor:
                cursor_last = cursor.get("last_successful_sync_at")
        modified_since = resolve_association_modified_since(
            sync_type=sync_type,
            lookback_days=lookback_days,
            cursor_last_sync=cursor_last,
        )
        modified_cutoff_iso = modified_since.isoformat() if modified_since else None
        try:
            sync_run = self._repository.create_sync_run(
                object_type=object_type,
                sync_type=sync_type,
                metadata={
                    "batch_size": batch_size,
                    "sync_group": sync_group,
                    "object_offset": object_offset,
                    "object_limit": object_limit,
                    "lookback_days": lookback_days,
                    "lookback_field": self._settings.association_sync_lookback_field,
                    "modified_since_cutoff": modified_cutoff_iso,
                },
            )
        except Exception:
            async with _association_lock:
                _running_association_syncs.discard(key)
            raise

        asyncio.create_task(
            self._run_safe(
                sync_id=sync_run["id"],
                sync_group=sync_group,
                sync_type=sync_type,
                batch_size=batch_size,
                object_offset=object_offset,
                object_limit=object_limit,
                lock_key=key,
            )
        )
        return sync_run

    async def _run_safe(self, **kwargs: Any) -> None:
        lock_key = kwargs.pop("lock_key")
        try:
            await self._execute_sync(**kwargs)
        finally:
            async with _association_lock:
                _running_association_syncs.discard(lock_key)

    async def _process_pair_batch(
        self,
        *,
        sync_id: str,
        sync_group: str,
        sync_type: str,
        pair: dict[str, str],
        object_ids: list[str],
        label_cache: AssociationLabelCache,
    ) -> dict[str, Any]:
        """Una llamada HubSpot + persistencia para un par y lote de IDs."""
        result = {"found": 0, "processed": 0, "failed": 0, "success": True, "object_count": len(object_ids)}
        try:
            payload = await self.hubspot.batch_read_associations(
                pair["from_type"],
                pair["to_type"],
                object_ids,
            )
            parsed = parse_batch_association_results(
                from_object_type=pair["from_type"],
                to_object_type=pair["to_type"],
                payload=payload,
                label_cache=label_cache,
            )
            result["found"] = len(parsed)
            rows = [
                self._repository.transform_association(
                    from_object_type=r.from_object_type,
                    from_hubspot_id=r.from_hubspot_id,
                    to_object_type=r.to_object_type,
                    to_hubspot_id=r.to_hubspot_id,
                    association_type_id=r.association_type_id,
                    association_category=r.association_category,
                    association_label=r.association_label,
                    raw_payload={"source": "batch_read"},
                )
                for r in parsed
            ]
            if rows:
                await asyncio.to_thread(self._repository.upsert_associations, rows)
                result["processed"] = len(rows)

            if sync_type == "incremental" and parsed:
                seen_by_source: dict[str, set[tuple[str, str, str, int | None]]] = {}
                for r in parsed:
                    seen_by_source.setdefault(r.from_hubspot_id, set()).add(
                        (
                            r.from_object_type,
                            r.from_hubspot_id,
                            r.to_object_type,
                            r.association_type_id,
                        )
                    )
                for from_id, keys in seen_by_source.items():
                    await asyncio.to_thread(
                        self._repository.deactivate_associations_for_source,
                        from_object_type=pair["from_type"],
                        from_hubspot_id=from_id,
                        active_keys=keys,
                    )

            for err in payload.get("errors", []):
                message = str(err.get("message", "batch error"))
                if _is_empty_association_batch_error(message):
                    continue
                result["failed"] += 1
                await asyncio.to_thread(
                    self._repository.create_sync_error,
                    sync_run_id=sync_id,
                    object_type=f"associations:{sync_group}",
                    hubspot_id=str(err.get("id")) if err.get("id") else None,
                    error_type="HubSpotBatchError",
                    error_message=message,
                    payload={"from": pair["from_type"], "to": pair["to_type"]},
                )
        except HubSpotClientError as exc:
            result["success"] = False
            result["failed"] += len(object_ids)
            await asyncio.to_thread(
                self._repository.create_sync_error,
                sync_run_id=sync_id,
                object_type=f"associations:{sync_group}",
                hubspot_id=None,
                error_type=type(exc).__name__,
                error_message=str(exc),
                http_status=getattr(exc, "status_code", None),
                payload={"from": pair["from_type"], "to": pair["to_type"]},
            )
        return result

    async def _execute_sync(
        self,
        *,
        sync_id: str,
        sync_group: str,
        sync_type: str,
        batch_size: int,
        object_offset: int = 0,
        object_limit: int | None = None,
    ) -> None:
        started = time.monotonic()
        self._repository.update_sync_run(sync_id, {"status": "running"})
        pairs = SYNC_GROUP_PAIRS.get(sync_group, [])
        label_cache = AssociationLabelCache()
        await asyncio.gather(
            *[
                label_cache.load(self.hubspot, pair["from_type"], pair["to_type"])
                for pair in pairs
            ]
        )

        records_found = 0
        records_processed = 0
        records_failed = 0
        success = True
        cursor_key = f"associations:{sync_group}"
        concurrency = self._settings.association_sync_hubspot_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        modified_since: datetime | None = None
        lookback_days = self._settings.association_sync_lookback_days
        cursor_last: str | None = None
        if sync_type == "incremental":
            cursor = self._repository.get_sync_cursor(cursor_key)
            if cursor:
                cursor_last = cursor.get("last_successful_sync_at")
        modified_since = resolve_association_modified_since(
            sync_type=sync_type,
            lookback_days=lookback_days,
            cursor_last_sync=cursor_last,
        )
        modified_cutoff_iso = modified_since.isoformat() if modified_since else None

        source_types = SOURCE_OBJECT_TYPES_BY_GROUP.get(sync_group, ())
        sample_limit = None
        if not self._settings.allow_full_phase2_validation:
            sample_limit = self._settings.phase2_validation_sample_size

        objects_processed = 0
        hubspot_batches = 0

        async def run_bounded(pair: dict[str, str], object_ids: list[str]) -> dict[str, Any]:
            async with semaphore:
                return await self._process_pair_batch(
                    sync_id=sync_id,
                    sync_group=sync_group,
                    sync_type=sync_type,
                    pair=pair,
                    object_ids=object_ids,
                    label_cache=label_cache,
                )

        try:
            for source_type in source_types:
                table = OBJECT_TABLE_BY_TYPE[source_type]
                modified_iso = modified_since.isoformat() if modified_since else None
                chunk_limit = object_limit
                if sample_limit is not None and chunk_limit is None:
                    chunk_limit = sample_limit
                page_size = min(500, chunk_limit or 500)
                id_batches = self._repository.iter_hubspot_ids(
                    table,
                    limit=sample_limit if object_limit is None else None,
                    start_offset=object_offset,
                    max_objects=chunk_limit,
                    modified_since=modified_iso,
                    lookback_field=self._settings.association_sync_lookback_field,
                    page_size=page_size,
                )
                relevant_pairs = [p for p in pairs if p["from_type"] == source_type]

                work: list[tuple[dict[str, str], list[str]]] = []
                for id_batch in id_batches:
                    chunk_size = min(batch_size, HUBSPOT_BATCH_ASSOCIATION_LIMIT)
                    for i in range(0, len(id_batch), chunk_size):
                        object_ids = id_batch[i : i + chunk_size]
                        for pair in relevant_pairs:
                            work.append((pair, object_ids))

                for wave_start in range(0, len(work), concurrency):
                    wave = work[wave_start : wave_start + concurrency]
                    results = await asyncio.gather(
                        *[run_bounded(pair, object_ids) for pair, object_ids in wave]
                    )
                    for item in results:
                        records_found += item["found"]
                        records_processed += item["processed"]
                        records_failed += item["failed"]
                        objects_processed += item["object_count"]
                        hubspot_batches += 1
                        if not item["success"]:
                            success = False

                    await asyncio.to_thread(
                        self._repository.update_sync_run,
                        sync_id,
                        {
                            "records_found": records_found,
                            "records_processed": records_processed,
                            "records_failed": records_failed,
                            "metadata": {
                                "batch_size": batch_size,
                                "sync_group": sync_group,
                                "object_offset": object_offset,
                                "object_limit": object_limit,
                                "objects_processed": objects_processed,
                                "hubspot_batches": hubspot_batches,
                                "hubspot_concurrency": concurrency,
                                "lookback_days": lookback_days,
                                "modified_since_cutoff": modified_cutoff_iso,
                            },
                        },
                    )

            for perm_err in label_cache.permission_errors:
                await asyncio.to_thread(
                    self._repository.create_sync_error,
                    sync_run_id=sync_id,
                    object_type=f"associations:{sync_group}",
                    hubspot_id=None,
                    error_type="HubSpotPermissionError",
                    error_message=perm_err["error"],
                    payload={"from": perm_err["from"], "to": perm_err["to"]},
                )

            status = "completed" if records_failed == 0 else "completed_with_errors"
            if not success and records_processed == 0:
                status = "failed"

            duration = round(time.monotonic() - started, 2)
            await asyncio.to_thread(
                self._repository.update_sync_run,
                sync_id,
                {
                    "status": status,
                    "finished_at": utc_now().isoformat(),
                    "records_found": records_found,
                    "records_processed": records_processed,
                    "records_inserted": records_processed,
                    "records_failed": records_failed,
                    "metadata": {
                        "batch_size": batch_size,
                        "sync_group": sync_group,
                        "object_offset": object_offset,
                        "object_limit": object_limit,
                        "objects_processed": objects_processed,
                        "hubspot_batches": hubspot_batches,
                        "hubspot_concurrency": concurrency,
                        "lookback_days": lookback_days,
                        "modified_since_cutoff": modified_cutoff_iso,
                        "duration_seconds": duration,
                    },
                },
            )

            partial_chunk = object_limit is not None
            if success and sync_type == "incremental" and status != "failed" and not partial_chunk:
                await asyncio.to_thread(
                    self._repository.upsert_sync_cursor,
                    object_type=cursor_key,
                    last_successful_sync_at=utc_now(),
                )
        except Exception as exc:
            logger.exception("Sync asociaciones fallida: %s", sync_group)
            await asyncio.to_thread(
                self._repository.update_sync_run,
                sync_id,
                {
                    "status": "failed",
                    "finished_at": utc_now().isoformat(),
                    "records_found": records_found,
                    "records_processed": records_processed,
                    "records_failed": records_failed + 1,
                    "error_message": str(exc),
                },
            )
            await asyncio.to_thread(
                self._repository.create_sync_error,
                sync_run_id=sync_id,
                object_type=f"associations:{sync_group}",
                hubspot_id=None,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
