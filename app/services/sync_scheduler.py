"""Sincronización automática periódica HubSpot -> Supabase."""

from __future__ import annotations

import asyncio
import logging

from app.clients.hubspot import get_hubspot_client
from app.config import get_settings
from app.services.associations_sync_service import (
    AssociationSyncAlreadyRunningError,
    AssociationsSyncService,
)
from app.services.sync_service import SyncAlreadyRunningError, SyncService
from app.utils.sync_schedule import seconds_until_next_daily_run

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _run_scheduled_sync() -> None:
    settings = get_settings()
    hubspot = await get_hubspot_client()
    sync = SyncService(hubspot_client=hubspot)
    assoc = AssociationsSyncService(hubspot_client=hubspot)

    try:
        await sync.start_sync(
            object_type="all",
            sync_type="incremental",
            batch_size=settings.auto_sync_batch_size,
        )
        logger.info("Sync incremental programado iniciado (objetos CRM + actividades)")
    except SyncAlreadyRunningError:
        logger.info("Sync incremental omitido: ya hay una sincronización en curso")

    try:
        await assoc.start_sync(
            sync_group="all",
            sync_type="incremental",
            batch_size=settings.auto_sync_batch_size,
        )
        logger.info("Sync incremental de asociaciones iniciado")
    except AssociationSyncAlreadyRunningError:
        logger.info("Sync de asociaciones omitido: ya en curso")
    except Exception as exc:
        logger.warning("No se pudo iniciar sync de asociaciones: %s", exc)


async def _wait_until_next_run() -> bool:
    """Espera al próximo ciclo. Devuelve False si se solicitó detener el scheduler."""
    settings = get_settings()
    assert _stop_event is not None

    if settings.auto_sync_daily_at:
        delay_sec = seconds_until_next_daily_run(
            settings.auto_sync_daily_at,
            settings.business_timezone,
        )
        logger.info(
            "Scheduler de sync diario activo: %s (%s), próxima ejecución en %.0f min",
            settings.auto_sync_daily_at,
            settings.business_timezone,
            delay_sec / 60,
        )
    else:
        delay_sec = settings.auto_sync_interval_minutes * 60
        logger.info(
            "Scheduler de sync activo: cada %s min (incremental), próxima ejecución en %.0f min",
            settings.auto_sync_interval_minutes,
            delay_sec / 60,
        )

    try:
        await asyncio.wait_for(_stop_event.wait(), timeout=delay_sec)
        return False
    except TimeoutError:
        return True


async def _scheduler_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        if not await _wait_until_next_run():
            break
        if _stop_event.is_set():
            break
        try:
            await _run_scheduled_sync()
        except Exception:
            logger.exception("Error en sync programado")


def start_sync_scheduler() -> asyncio.Task | None:
    global _scheduler_task, _stop_event
    settings = get_settings()
    if not settings.auto_sync_enabled:
        return None
    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return _scheduler_task


async def stop_sync_scheduler() -> None:
    global _scheduler_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _scheduler_task is not None:
        try:
            await asyncio.wait_for(_scheduler_task, timeout=5.0)
        except TimeoutError:
            _scheduler_task.cancel()
        _scheduler_task = None
    _stop_event = None
