"""Sync HubSpot + refresh deal_analytics para el dashboard."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.clients.hubspot import get_hubspot_client
from app.config import get_settings
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.repositories.supabase_repository import SupabaseRepository
from app.services.associations_sync_service import (
    AssociationSyncAlreadyRunningError,
    AssociationsSyncService,
)
from app.services.deal_analytics.query import invalidate_deal_analytics_cache
from app.services.deal_analytics.refresh import (
    DealAnalyticsRefreshAlreadyRunningError,
    DealAnalyticsRefreshService,
)
from app.services.sync_service import SyncAlreadyRunningError, SyncService

logger = logging.getLogger(__name__)

TERMINAL = frozenset({"completed", "completed_with_errors", "failed"})
POLL_RETRIES = 5

_sync_lock = asyncio.Lock()
_current_sync_task: asyncio.Task[dict[str, str]] | None = None
_sync_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "result": None,
}


def get_dashboard_sync_state() -> dict[str, Any]:
    return {
        "running": bool(_sync_state["running"]),
        "started_at": _sync_state["started_at"],
        "result": _sync_state["result"],
    }


async def _poll_sync_run(repo: SupabaseRepository, sync_id: str, *, poll_sec: float = 3.0) -> dict[str, Any]:
    while True:
        run = repo.get_sync_run(sync_id)
        if not run:
            raise RuntimeError(f"sync_run {sync_id} no encontrado")
        if run.get("status") in TERMINAL:
            return run
        await asyncio.sleep(poll_sec)


async def _poll_analytics_run(
    repo: DealAnalyticsRepository, run_id: str, *, poll_sec: float = 3.0
) -> dict[str, Any]:
    while True:
        last_exc: Exception | None = None
        for attempt in range(POLL_RETRIES):
            try:
                run = repo.get_run(run_id)
                if not run:
                    raise RuntimeError(f"deal_analytics run {run_id} no encontrado")
                if run.get("status") in TERMINAL:
                    return run
                break
            except Exception as exc:
                last_exc = exc
                if attempt + 1 >= POLL_RETRIES:
                    raise
                await asyncio.sleep(poll_sec * (attempt + 1))
        else:
            if last_exc:
                raise last_exc
        await asyncio.sleep(poll_sec)


async def _start_analytics_refresh(result: dict[str, str]) -> None:
    try:
        refresh_svc = DealAnalyticsRefreshService()
        refresh_run = await refresh_svc.start_refresh()
        run_id = str(refresh_run["run_id"])
        result["analytics"] = f"iniciado ({run_id})"
        final = await _poll_analytics_run(DealAnalyticsRepository(), run_id)
        processed = final.get("deals_processed") or 0
        result["analytics"] = f"{final.get('status')} ({run_id}, {processed} negocios)"
        if final.get("status") in {"completed", "completed_with_errors"}:
            invalidate_deal_analytics_cache()
    except DealAnalyticsRefreshAlreadyRunningError:
        result["analytics"] = "ya en curso"
    except Exception as exc:
        logger.exception("Refresh deal_analytics fallido")
        result["analytics"] = f"error: {exc}"


async def _run_dashboard_sync_impl(*, refresh_analytics: bool = True) -> dict[str, str]:
    """Sync incremental completo, espera fin y recalcula deal_analytics."""
    from app.utils.dates import utc_now

    _sync_state["running"] = True
    _sync_state["started_at"] = utc_now().isoformat()
    _sync_state["result"] = None
    result: dict[str, str] = {}
    try:
        settings = get_settings()
        repo = SupabaseRepository()
        hubspot = await get_hubspot_client()
        sync = SyncService(hubspot_client=hubspot, repository=repo)
        assoc = AssociationsSyncService(hubspot_client=hubspot)

        sync_id: str | None = None
        try:
            sync_run = await sync.start_sync(
                object_type="all",
                sync_type="incremental",
                batch_size=settings.auto_sync_batch_size,
            )
            sync_id = str(sync_run["id"])
            result["objects"] = f"iniciado ({sync_id})"
        except SyncAlreadyRunningError:
            result["objects"] = "ya en curso"
        except Exception as exc:
            result["objects"] = f"error: {exc}"

        if sync_id:
            try:
                final = await _poll_sync_run(repo, sync_id)
                proc = final.get("records_processed") or 0
                status = final.get("status") or "?"
                err = final.get("error_message") or ""
                result["objects"] = f"{status} ({sync_id}, {proc} registros)"
                if err:
                    result["objects"] += f" — {err[:120]}"
            except Exception as exc:
                result["objects"] = f"error esperando sync: {exc}"

        assoc_id: str | None = None
        try:
            assoc_run = await assoc.start_sync(
                sync_group="all",
                sync_type="incremental",
                batch_size=settings.auto_sync_batch_size,
            )
            assoc_id = str(assoc_run["id"])
            result["associations"] = f"iniciado ({assoc_id})"
        except AssociationSyncAlreadyRunningError:
            result["associations"] = "ya en curso"
        except Exception as exc:
            result["associations"] = f"error: {exc}"

        if assoc_id:
            try:
                final = await _poll_sync_run(repo, assoc_id)
                proc = final.get("records_processed") or 0
                result["associations"] = f"{final.get('status')} ({assoc_id}, {proc} registros)"
            except Exception as exc:
                result["associations"] = f"error esperando asoc: {exc}"

        if refresh_analytics:
            await _start_analytics_refresh(result)

        return result
    finally:
        _sync_state["result"] = result
        _sync_state["running"] = False


async def run_dashboard_sync(*, refresh_analytics: bool = True) -> dict[str, str]:
    """Ejecuta sync Supabase; si ya hay uno en curso, espera a que termine."""
    global _current_sync_task

    async with _sync_lock:
        if _current_sync_task is not None and not _current_sync_task.done():
            task = _current_sync_task
        else:
            _current_sync_task = asyncio.create_task(
                _run_dashboard_sync_impl(refresh_analytics=refresh_analytics)
            )
            task = _current_sync_task

    try:
        return await task
    finally:
        async with _sync_lock:
            if _current_sync_task is task and task.done():
                _current_sync_task = None
                if _sync_state["running"]:
                    _sync_state["running"] = False


def schedule_dashboard_sync(*, refresh_analytics: bool = True) -> None:
    """Ejecuta run_dashboard_sync en segundo plano."""

    async def _worker() -> None:
        try:
            result = await run_dashboard_sync(refresh_analytics=refresh_analytics)
            logger.info("Dashboard sync pipeline: %s", result)
        except Exception:
            logger.exception("Dashboard sync pipeline falló")

    asyncio.create_task(_worker())
