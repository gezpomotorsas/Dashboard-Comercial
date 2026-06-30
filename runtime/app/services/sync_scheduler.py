"""Sincronización automática periódica HubSpot -> Supabase."""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.services.dashboard_sync_pipeline import run_dashboard_sync
from app.utils.sync_schedule import seconds_until_next_daily_run

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def trigger_incremental_sync() -> dict[str, str]:
    """Sync incremental + refresh deal_analytics (scheduler y compat)."""
    return await run_dashboard_sync(refresh_analytics=True)


async def _run_scheduled_sync() -> None:
    await run_dashboard_sync(refresh_analytics=True)


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
            logger.info("Sync incremental programado completado (solicitud enviada)")
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
