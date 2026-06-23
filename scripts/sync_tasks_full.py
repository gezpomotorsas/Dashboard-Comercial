#!/usr/bin/env python3
"""Sincroniza el historial completo de tareas HubSpot -> Supabase y refresca analítica."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.repositories.supabase_repository import SupabaseRepository
from app.services.deal_analytics.refresh import DealAnalyticsRefreshService
from app.services.sync_service import SyncService

TERMINAL_STATUSES = frozenset({"completed", "completed_with_errors", "failed"})


async def poll_sync_run(repo: SupabaseRepository, sync_id: str, poll_sec: float) -> dict:
    last_line = ""
    while True:
        run = repo.get_sync_run(sync_id)
        if not run:
            raise RuntimeError(f"sync_run {sync_id} no encontrado")
        line = (
            f"[tasks] status={run.get('status')} found={run.get('records_found', 0)} "
            f"processed={run.get('records_processed', 0)} ins={run.get('records_inserted', 0)} "
            f"upd={run.get('records_updated', 0)} err={run.get('records_failed', 0)}"
        )
        if line != last_line:
            print(line, flush=True)
            last_line = line
        if run.get("status") in TERMINAL_STATUSES:
            return run
        await asyncio.sleep(poll_sec)


async def main_async(batch_size: int, poll_sec: float, skip_analytics: bool) -> int:
    hubspot = await get_hubspot_client()
    sync = SyncService(hubspot_client=hubspot)
    repo = SupabaseRepository()
    started = time.perf_counter()
    before = repo.count_objects("tasks")

    print(f"Tareas en Supabase antes del sync: {before:,}")
    print("=== Sync historial completo de tareas (activas + archivadas) ===")
    run = await sync.start_sync(object_type="tasks", sync_type="full", batch_size=batch_size)
    sync_id = str(run["id"])
    print(f"sync_run_id={sync_id}")
    final = await poll_sync_run(repo, sync_id, poll_sec)
    after = repo.count_objects("tasks")
    print(f"Tareas en Supabase después del sync: {after:,} (delta {after - before:+,})")

    exit_code = 0 if final.get("status") == "completed" else 1

    if not skip_analytics and exit_code == 0:
        print("\n=== Refresh deal_analytics (tareas en KPIs de negocios) ===")
        da_repo = DealAnalyticsRepository()
        refresh = DealAnalyticsRefreshService(repository=da_repo)
        run_row = da_repo.create_run()
        run_id = str(run_row["id"])
        await asyncio.to_thread(refresh._execute_refresh, run_id)
        result = da_repo.get_run(run_id) or {}
        print(f"Analítica status={result.get('status')} processed={result.get('deals_processed', 0)}")
        if result.get("status") not in ("completed", "completed_with_errors"):
            exit_code = 1

    duration = round(time.perf_counter() - started, 1)
    print(f"Finalizado en {duration}s status={final.get('status')}")
    await close_hubspot_client()
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync completo de tareas HubSpot")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--poll-sec", type=float, default=3.0)
    parser.add_argument("--skip-analytics", action="store_true")
    args = parser.parse_args()
    code = asyncio.run(
        main_async(
            batch_size=args.batch_size,
            poll_sec=args.poll_sec,
            skip_analytics=args.skip_analytics,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
