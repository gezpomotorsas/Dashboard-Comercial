"""Servicio de sincronización HubSpot -> PostgreSQL."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import HubSpotClientError, HubSpotPermissionError, HubSpotRateLimitError
from app.config import INCREMENTAL_OVERLAP_MINUTES, get_settings
from app.constants.activities import ACTIVITY_SYNC_ORDER, ACTIVITY_SYNC_PROPERTIES
from app.constants.crm_sync import CRM_MODIFIED_DATE_PROPERTY, CRM_SYNC_PROPERTIES
from app.repositories.supabase_repository import SupabaseRepository
from app.services import metadata_service
from app.services.hubspot_configuration import get_hubspot_config, invalidate_hubspot_config
from app.utils.activity_sync import (
    activity_window_bounds,
    activity_window_chunks,
    activity_within_window,
    build_timestamp_filter_groups,
    chunk_days_for_activity,
    is_activity_object_type,
    resolve_activity_modified_since,
)
from app.utils.dates import hubspot_ms_timestamp, overlap_timestamp, parse_hubspot_datetime, utc_now
from app.utils.privacy import safe_error_message

logger = logging.getLogger(__name__)

TASK_UPSERT_CHUNK_SIZE = 25
HUBSPOT_PAGE_RETRIES = 4

SYNC_OBJECT_TYPES = [
    "metadata",
    "contacts",
    "deals",
    *ACTIVITY_SYNC_ORDER,
]

_running_syncs: set[str] = set()
_sync_lock = asyncio.Lock()


class SyncAlreadyRunningError(Exception):
    """Ya existe una sincronización activa para este tipo de objeto."""


class SyncService:
    def __init__(
        self,
        hubspot_client: HubSpotClient | None = None,
        repository: SupabaseRepository | None = None,
    ) -> None:
        self._hubspot = hubspot_client
        self._repository = repository or SupabaseRepository()
        self._settings = get_settings()

    @property
    def hubspot(self) -> HubSpotClient:
        if self._hubspot is None:
            raise RuntimeError("HubSpot client not configured")
        return self._hubspot

    def _report_progress(
        self,
        sync_id: str,
        *,
        current_phase: str,
        records_found: int | None = None,
        records_processed: int | None = None,
        records_inserted: int | None = None,
        records_updated: int | None = None,
        records_failed: int | None = None,
    ) -> None:
        metadata: dict[str, Any] = {
            "current_phase": current_phase,
            "last_heartbeat": utc_now().isoformat(),
        }
        updates: dict[str, Any] = {"metadata": metadata}
        if records_found is not None:
            updates["records_found"] = records_found
        if records_processed is not None:
            updates["records_processed"] = records_processed
        if records_inserted is not None:
            updates["records_inserted"] = records_inserted
        if records_updated is not None:
            updates["records_updated"] = records_updated
        if records_failed is not None:
            updates["records_failed"] = records_failed
        try:
            self._repository.update_sync_run(sync_id, updates)
        except Exception:
            logger.debug("No se pudo reportar progreso de sync %s", sync_id, exc_info=True)

    async def start_sync(
        self,
        *,
        object_type: str,
        sync_type: str,
        batch_size: int,
        lookback_days: int | None = None,
    ) -> dict[str, Any]:
        key = object_type
        async with _sync_lock:
            if key in _running_syncs:
                raise SyncAlreadyRunningError(f"Sincronización de {object_type} ya está en ejecución")
            _running_syncs.add(key)

        effective_lookback = self._resolve_lookback_days(object_type, sync_type, lookback_days)
        metadata: dict[str, Any] = {
            "batch_size": batch_size,
            "lookback_days": effective_lookback if is_activity_object_type(object_type) else None,
        }

        try:
            sync_run = self._repository.create_sync_run(
                object_type=object_type,
                sync_type=sync_type,
                metadata=metadata,
            )
        except Exception:
            async with _sync_lock:
                _running_syncs.discard(key)
            raise

        asyncio.create_task(
            self._run_sync_safe(
                sync_id=sync_run["id"],
                object_type=object_type,
                sync_type=sync_type,
                batch_size=batch_size,
                lookback_days=effective_lookback,
            )
        )
        return sync_run

    @staticmethod
    def _resolve_lookback_days(
        object_type: str,
        sync_type: str,
        lookback_days: int | None,
    ) -> int | None:
        settings = get_settings()
        if not is_activity_object_type(object_type):
            return None
        if lookback_days is not None:
            return lookback_days
        if sync_type in ("window", "full", "incremental"):
            return settings.activity_sync_lookback_days
        return settings.activity_sync_lookback_days

    async def _run_sync_safe(
        self,
        *,
        sync_id: str,
        object_type: str,
        sync_type: str,
        batch_size: int,
        lookback_days: int | None,
    ) -> None:
        try:
            await self._execute_sync(
                sync_id=sync_id,
                object_type=object_type,
                sync_type=sync_type,
                batch_size=batch_size,
                lookback_days=lookback_days,
            )
        finally:
            async with _sync_lock:
                _running_syncs.discard(object_type)

    async def _execute_sync(
        self,
        *,
        sync_id: str,
        object_type: str,
        sync_type: str,
        batch_size: int,
        lookback_days: int | None,
    ) -> None:
        started = time.perf_counter()
        self._repository.update_sync_run(
            sync_id,
            {
                "status": "running",
                "metadata": {
                    "current_phase": f"starting:{object_type}",
                    "last_heartbeat": utc_now().isoformat(),
                },
            },
        )
        records_found = 0
        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_failed = 0
        records_excluded = 0

        try:
            if object_type == "metadata":
                records_found, records_processed, records_failed = await self._sync_metadata(
                    sync_id=sync_id,
                )
                records_inserted = records_processed
            elif object_type == "all":
                total_found = 0
                total_processed = 0
                total_failed = 0
                total_inserted = 0
                total_updated = 0
                sequence = [
                    "metadata",
                    "deals",
                    *ACTIVITY_SYNC_ORDER,
                    "contacts",
                ]
                for item_type in sequence:
                    self._report_progress(
                        sync_id,
                        current_phase=f"sync:{item_type}",
                        records_found=total_found,
                        records_processed=total_processed,
                        records_inserted=total_inserted,
                        records_updated=total_updated,
                        records_failed=total_failed,
                    )
                    try:
                        if item_type == "metadata":
                            found, processed, failed = await self._sync_metadata(sync_id=sync_id)
                            ins, upd = processed, 0
                        else:
                            if item_type == "tasks" and self._settings.task_sync_full_history:
                                item_sync_type = "full"
                            elif is_activity_object_type(item_type):
                                item_sync_type = "window"
                            else:
                                item_sync_type = sync_type
                            found, processed, failed, ins, upd, _ = await self._sync_object_type(
                                sync_id=sync_id,
                                object_type=item_type,
                                sync_type=item_sync_type,
                                batch_size=batch_size,
                                lookback_days=lookback_days,
                            )
                        total_found += found
                        total_processed += processed
                        total_failed += failed
                        total_inserted += ins
                        total_updated += upd
                    except Exception as exc:
                        total_failed += 1
                        logger.exception(
                            "Sync parcial fallido (%s) en run %s; continúa siguiente tipo",
                            item_type,
                            sync_id,
                        )
                        self._repository.create_sync_error(
                            sync_run_id=sync_id,
                            object_type=item_type,
                            hubspot_id=None,
                            error_type=type(exc).__name__,
                            error_message=safe_error_message(str(exc)),
                        )
                records_found = total_found
                records_processed = total_processed
                records_failed = total_failed
                records_inserted = total_inserted
                records_updated = total_updated
            else:
                result = await self._sync_object_type(
                    sync_id=sync_id,
                    object_type=object_type,
                    sync_type=sync_type,
                    batch_size=batch_size,
                    lookback_days=lookback_days,
                )
                (
                    records_found,
                    records_processed,
                    records_failed,
                    records_inserted,
                    records_updated,
                    records_excluded,
                ) = result

            duration = round(time.perf_counter() - started, 2)
            status = "completed" if records_failed == 0 else "completed_with_errors"
            self._repository.update_sync_run(
                sync_id,
                {
                    "status": status,
                    "finished_at": utc_now().isoformat(),
                    "records_found": records_found,
                    "records_processed": records_processed,
                    "records_inserted": records_inserted,
                    "records_updated": records_updated,
                    "records_failed": records_failed,
                    "metadata": {
                        "batch_size": batch_size,
                        "lookback_days": lookback_days,
                        "duration_seconds": duration,
                        "records_excluded": records_excluded,
                    },
                },
            )
            logger.info(
                "Sync %s %s: found=%s processed=%s inserted=%s updated=%s failed=%s duration=%ss",
                object_type,
                sync_type,
                records_found,
                records_processed,
                records_inserted,
                records_updated,
                records_failed,
                duration,
            )
        except Exception as exc:
            logger.exception("Sincronización fallida para %s", object_type)
            self._repository.update_sync_run(
                sync_id,
                {
                    "status": "failed",
                    "finished_at": utc_now().isoformat(),
                    "records_found": records_found,
                    "records_processed": records_processed,
                    "records_failed": records_failed + 1,
                    "error_message": safe_error_message(str(exc)),
                },
            )
            self._repository.create_sync_error(
                sync_run_id=sync_id,
                object_type=object_type,
                hubspot_id=None,
                error_type=type(exc).__name__,
                error_message=safe_error_message(str(exc)),
            )

    async def _sync_metadata(self, *, sync_id: str) -> tuple[int, int, int]:
        contact_props = await metadata_service.get_contact_properties(self.hubspot)
        deal_props = await metadata_service.get_deal_properties(self.hubspot)
        owners = await metadata_service.get_owners(self.hubspot)
        pipelines = await metadata_service.get_deal_pipelines(self.hubspot)

        self._repository.upsert_properties("contacts", [p.model_dump(by_alias=True) for p in contact_props])
        self._repository.upsert_properties("deals", [p.model_dump(by_alias=True) for p in deal_props])
        self._repository.upsert_owners([o.model_dump(by_alias=True) for o in owners])
        self._repository.upsert_pipelines([p.model_dump(by_alias=True) for p in pipelines])

        invalidate_hubspot_config()
        store = get_hubspot_config(refresh=True)
        store.validate_field_mappings()

        total = len(contact_props) + len(deal_props) + len(owners) + len(pipelines)
        return total, total, 0

    async def _sync_object_type(
        self,
        *,
        sync_id: str,
        object_type: str,
        sync_type: str,
        batch_size: int,
        lookback_days: int | None,
    ) -> tuple[int, int, int, int, int, int]:
        if object_type == "metadata":
            found, processed, failed = await self._sync_metadata(sync_id=sync_id)
            return found, processed, failed, processed, 0, 0

        if object_type == "tasks" and self._settings.task_sync_full_history and sync_type == "full":
            return await self._sync_tasks_full_list(
                sync_id=sync_id,
                batch_size=batch_size,
            )

        if is_activity_object_type(object_type):
            return await self._sync_activity_type(
                sync_id=sync_id,
                object_type=object_type,
                sync_type=sync_type,
                batch_size=batch_size,
                lookback_days=lookback_days or self._settings.activity_sync_lookback_days,
            )

        return await self._sync_crm_object_type(
            sync_id=sync_id,
            object_type=object_type,
            sync_type=sync_type,
            batch_size=batch_size,
        )

    async def _sync_crm_object_type(
        self,
        *,
        sync_id: str,
        object_type: str,
        sync_type: str,
        batch_size: int,
    ) -> tuple[int, int, int, int, int, int]:
        cursor = self._repository.get_sync_cursor(object_type)
        modified_since: datetime | None = None
        if sync_type == "incremental" and cursor:
            last_sync = cursor.get("last_successful_sync_at")
            if isinstance(last_sync, str):
                parsed = parse_hubspot_datetime(last_sync)
                if parsed:
                    modified_since = overlap_timestamp(parsed, INCREMENTAL_OVERLAP_MINUTES)

        records_found = 0
        records_processed = 0
        records_failed = 0
        records_inserted = 0
        records_updated = 0
        after: str | None = None
        success = True

        while True:
            try:
                if sync_type == "incremental" and modified_since:
                    payload = await self._search_modified(
                        object_type=object_type,
                        modified_since=modified_since,
                        limit=batch_size,
                        after=after,
                    )
                else:
                    params: dict[str, Any] = {"limit": batch_size}
                    if after:
                        params["after"] = after
                    sync_props = CRM_SYNC_PROPERTIES.get(object_type)
                    if sync_props:
                        params["properties"] = ",".join(sync_props)
                    payload = await self.hubspot.get(f"/crm/v3/objects/{object_type}", params=params)

                results = payload.get("results", [])
                records_found += len(results)

                if results:
                    ins, upd, failed = self._upsert_batch(
                        sync_id=sync_id,
                        object_type=object_type,
                        results=results,
                    )
                    records_processed += ins + upd
                    records_inserted += ins
                    records_updated += upd
                    records_failed += failed
                    if failed:
                        success = False

                self._report_progress(
                    sync_id,
                    current_phase=f"sync:{object_type}",
                    records_found=records_found,
                    records_processed=records_processed,
                    records_inserted=records_inserted,
                    records_updated=records_updated,
                    records_failed=records_failed,
                )

                paging = payload.get("paging") or {}
                next_after = (paging.get("next") or {}).get("after")
                if not next_after:
                    break
                after = next_after
            except HubSpotClientError as exc:
                success = False
                records_failed += 1
                self._repository.create_sync_error(
                    sync_run_id=sync_id,
                    object_type=object_type,
                    hubspot_id=None,
                    error_type=type(exc).__name__,
                    error_message=safe_error_message(str(exc)),
                    http_status=getattr(exc, "status_code", None),
                )
                break

        if success and sync_type == "incremental":
            self._repository.upsert_sync_cursor(
                object_type=object_type,
                last_successful_sync_at=utc_now(),
                last_after=after,
            )

        return records_found, records_processed, records_failed, records_inserted, records_updated, 0

    async def _sync_tasks_full_list(
        self,
        *,
        sync_id: str,
        batch_size: int,
    ) -> tuple[int, int, int, int, int, int]:
        """Lista paginada de todas las tareas HubSpot (activas y archivadas)."""
        properties = list(ACTIVITY_SYNC_PROPERTIES["tasks"])
        totals = [0, 0, 0, 0, 0, 0]

        for archived in (False, True):
            phase = "sync:tasks:archived" if archived else "sync:tasks"
            found, processed, failed, inserted, updated, _ = await self._sync_tasks_full_list_pass(
                sync_id=sync_id,
                batch_size=batch_size,
                properties=properties,
                archived=archived,
                progress_phase=phase,
            )
            totals[0] += found
            totals[1] += processed
            totals[2] += failed
            totals[3] += inserted
            totals[4] += updated

        records_found, records_processed, records_failed, records_inserted, records_updated = totals[:5]
        success = records_failed == 0

        if success:
            self._repository.upsert_sync_cursor(
                object_type="tasks",
                last_successful_sync_at=utc_now(),
                last_after=None,
            )

        logger.info(
            "Task full-list sync: found=%s processed=%s inserted=%s updated=%s failed=%s",
            records_found,
            records_processed,
            records_inserted,
            records_updated,
            records_failed,
        )
        return records_found, records_processed, records_failed, records_inserted, records_updated, 0

    async def _sync_tasks_full_list_pass(
        self,
        *,
        sync_id: str,
        batch_size: int,
        properties: list[str],
        archived: bool,
        progress_phase: str,
    ) -> tuple[int, int, int, int, int, int]:
        records_found = 0
        records_processed = 0
        records_failed = 0
        records_inserted = 0
        records_updated = 0
        after: str | None = None

        while True:
            try:
                payload = await self._hubspot_list_tasks_page(
                    batch_size=batch_size,
                    properties=properties,
                    archived=archived,
                    after=after,
                )
            except HubSpotClientError as exc:
                records_failed += 1
                self._repository.create_sync_error(
                    sync_run_id=sync_id,
                    object_type="tasks",
                    hubspot_id=None,
                    error_type=type(exc).__name__,
                    error_message=safe_error_message(str(exc)),
                    http_status=getattr(exc, "status_code", None),
                )
                break

            results = payload.get("results", [])
            records_found += len(results)

            if results:
                ins, upd, failed = self._upsert_batch(
                    sync_id=sync_id,
                    object_type="tasks",
                    results=results,
                )
                records_processed += ins + upd
                records_inserted += ins
                records_updated += upd
                records_failed += failed
                self._report_progress(
                    sync_id,
                    current_phase=progress_phase,
                    records_found=records_found,
                    records_processed=records_processed,
                    records_inserted=records_inserted,
                    records_updated=records_updated,
                    records_failed=records_failed,
                )

            paging = payload.get("paging") or {}
            next_after = (paging.get("next") or {}).get("after")
            if not next_after:
                break
            after = next_after

        return records_found, records_processed, records_failed, records_inserted, records_updated, 0

    async def _hubspot_list_tasks_page(
        self,
        *,
        batch_size: int,
        properties: list[str],
        archived: bool,
        after: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": batch_size,
            "properties": ",".join(properties),
            "archived": str(archived).lower(),
        }
        if after:
            params["after"] = after

        last_exc: HubSpotClientError | None = None
        for attempt in range(HUBSPOT_PAGE_RETRIES):
            try:
                return await self.hubspot.get("/crm/v3/objects/tasks", params=params)
            except HubSpotRateLimitError as exc:
                last_exc = exc
                await asyncio.sleep(exc.retry_after or min(2**attempt, 30))
            except HubSpotClientError as exc:
                last_exc = exc
                if attempt + 1 >= HUBSPOT_PAGE_RETRIES:
                    raise
                await asyncio.sleep(min(2**attempt, 15))
        if last_exc:
            raise last_exc
        raise HubSpotClientError("No se pudo leer página de tareas")

    async def _sync_activity_type(
        self,
        *,
        sync_id: str,
        object_type: str,
        sync_type: str,
        batch_size: int,
        lookback_days: int,
    ) -> tuple[int, int, int, int, int, int]:
        effective_sync = sync_type
        if sync_type == "full":
            effective_sync = "window"

        cursor = self._repository.get_sync_cursor(object_type)
        cursor_last = cursor.get("last_successful_sync_at") if cursor else None

        window_start, window_end = activity_window_bounds(lookback_days)
        properties = list(ACTIVITY_SYNC_PROPERTIES[object_type])

        records_found = 0
        records_processed = 0
        records_failed = 0
        records_inserted = 0
        records_updated = 0
        records_excluded = 0
        success = True

        if effective_sync == "window":
            time_chunks = activity_window_chunks(
                lookback_days,
                chunk_days=chunk_days_for_activity(object_type),
            )
            search_mode = "timestamp"
        else:
            modified_since = resolve_activity_modified_since(
                sync_type="incremental",
                lookback_days=lookback_days,
                cursor_last_sync=cursor_last if isinstance(cursor_last, str) else None,
            )
            time_chunks = [(modified_since or window_start, window_end)]
            search_mode = "incremental"

        for chunk_start, chunk_end in time_chunks:
            after: str | None = None
            chunk_pages = 0
            while True:
                try:
                    use_upper = effective_sync == "window"
                    filter_groups = build_timestamp_filter_groups(
                        gte=chunk_start,
                        lte=chunk_end if use_upper else None,
                    )
                    payload = await self.hubspot.search_objects(
                        object_type,
                        filter_groups=filter_groups,
                        properties=properties,
                        limit=min(batch_size, 100),
                        after=after,
                    )
                    results = payload.get("results", [])
                    records_found += len(results)
                    chunk_pages += 1

                    if effective_sync == "window":
                        in_window = [
                            r
                            for r in results
                            if activity_within_window(
                                r,
                                window_start=window_start,
                                window_end=window_end,
                            )
                        ]
                        records_excluded += len(results) - len(in_window)
                        batch = in_window
                    else:
                        batch = results

                    if batch:
                        ins, upd, failed = self._upsert_batch(
                            sync_id=sync_id,
                            object_type=object_type,
                            results=batch,
                        )
                        records_processed += ins + upd
                        records_inserted += ins
                        records_updated += upd
                        records_failed += failed
                        if failed:
                            success = False
                        self._report_progress(
                            sync_id,
                            current_phase=f"sync:{object_type}",
                            records_found=records_found,
                            records_processed=records_processed,
                            records_inserted=records_inserted,
                            records_updated=records_updated,
                            records_failed=records_failed,
                        )

                    paging = payload.get("paging") or {}
                    next_after = (paging.get("next") or {}).get("after")
                    if not next_after:
                        break
                    if chunk_pages >= 100:
                        logger.warning(
                            "Activity sync %s: límite de páginas por chunk alcanzado",
                            object_type,
                        )
                        break
                    after = next_after
                except HubSpotPermissionError as exc:
                    if object_type == "emails":
                        logger.warning(
                            "Emails no sincronizados: falta scope HubSpot (crm.objects.emails.read)"
                        )
                        self._repository.update_sync_run(
                            sync_id,
                            {
                                "metadata": {
                                    "email_scope_missing": True,
                                    "scope_error": safe_error_message(str(exc)),
                                }
                            },
                        )
                        return 0, 0, 0, 0, 0, 0
                    success = False
                    records_failed += 1
                    self._repository.create_sync_error(
                        sync_run_id=sync_id,
                        object_type=object_type,
                        hubspot_id=None,
                        error_type=type(exc).__name__,
                        error_message=safe_error_message(str(exc)),
                    )
                    break
                except HubSpotClientError as exc:
                    success = False
                    records_failed += 1
                    self._repository.create_sync_error(
                        sync_run_id=sync_id,
                        object_type=object_type,
                        hubspot_id=None,
                        error_type=type(exc).__name__,
                        error_message=safe_error_message(str(exc)),
                        http_status=getattr(exc, "status_code", None),
                    )
                    break

        if success and effective_sync == "incremental":
            self._repository.upsert_sync_cursor(
                object_type=object_type,
                last_successful_sync_at=utc_now(),
                last_after=None,
            )

        logger.info(
            "Activity sync %s mode=%s found=%s excluded=%s",
            object_type,
            search_mode,
            records_found,
            records_excluded,
        )
        return (
            records_found,
            records_processed,
            records_failed,
            records_inserted,
            records_updated,
            records_excluded,
        )

    def _upsert_batch(
        self,
        *,
        sync_id: str,
        object_type: str,
        results: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        if not results:
            return 0, 0, 0

        chunk_size = TASK_UPSERT_CHUNK_SIZE if object_type == "tasks" else len(results)
        inserted = updated = failed = 0

        for start in range(0, len(results), chunk_size):
            chunk = results[start : start + chunk_size]
            chunk_ids = [str(r.get("id")) for r in chunk if r.get("id")]
            existing = self._repository.existing_hubspot_ids(object_type, chunk_ids)
            try:
                self._repository.upsert_objects(object_type, chunk)
                inserted += sum(1 for i in chunk_ids if i not in existing)
                updated += len(chunk_ids) - sum(1 for i in chunk_ids if i not in existing)
            except Exception as exc:
                for record in chunk:
                    record_id = str(record.get("id") or "")
                    was_existing = record_id in existing
                    try:
                        self._repository.upsert_objects(object_type, [record])
                        if was_existing:
                            updated += 1
                        else:
                            inserted += 1
                    except Exception as single_exc:
                        failed += 1
                        self._repository.create_sync_error(
                            sync_run_id=sync_id,
                            object_type=object_type,
                            hubspot_id=record_id or None,
                            error_type=type(single_exc).__name__,
                            error_message=safe_error_message(str(single_exc)),
                            payload={"batch_fallback": True, "batch_error": safe_error_message(str(exc))},
                        )
        return inserted, updated, failed

    async def _search_modified(
        self,
        *,
        object_type: str,
        modified_since: datetime,
        limit: int,
        after: str | None,
    ) -> dict[str, Any]:
        filter_groups = [
            {
                "filters": [
                    {
                        "propertyName": CRM_MODIFIED_DATE_PROPERTY.get(
                            object_type, "hs_lastmodifieddate"
                        ),
                        "operator": "GTE",
                        "value": str(hubspot_ms_timestamp(modified_since)),
                    }
                ]
            }
        ]
        return await self.hubspot.search_objects(
            object_type,
            filter_groups=filter_groups,
            limit=limit,
            after=after,
            properties=list(CRM_SYNC_PROPERTIES.get(object_type, ())),
        )

    def get_sync_run(self, sync_id: UUID) -> dict[str, Any] | None:
        return self._repository.get_sync_run(sync_id)

    def list_sync_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._repository.list_sync_runs(limit=limit)
