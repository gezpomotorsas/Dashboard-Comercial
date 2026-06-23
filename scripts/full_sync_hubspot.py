#!/usr/bin/env python3
"""Carga completa HubSpot -> Supabase con progreso en consola."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.repositories.supabase_repository import SupabaseRepository
from app.services.associations_sync_service import AssociationsSyncService
from app.services.deal_analytics.refresh import DealAnalyticsRefreshService
from app.services.sync_service import SyncService

TERMINAL_STATUSES = frozenset({"completed", "completed_with_errors", "failed"})


def _format_ts(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return value


def _render_progress(label: str, run: dict) -> str:
    status = run.get("status", "?")
    meta = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    phase = run.get("current_phase") or meta.get("current_phase") or run.get("object_type") or "-"
    found = run.get("records_found") or 0
    processed = run.get("records_processed") or 0
    inserted = run.get("records_inserted") or 0
    updated = run.get("records_updated") or 0
    failed = run.get("records_failed") or 0
    heartbeat = _format_ts(run.get("last_heartbeat") or meta.get("last_heartbeat"))
    return (
        f"[{label}] [{status}] fase={phase} | encontrados={found} procesados={processed} "
        f"ins={inserted} upd={updated} err={failed} | latido={heartbeat}"
    )


async def poll_sync_run(
    repo: SupabaseRepository,
    sync_id: str,
    label: str,
    poll_sec: float,
) -> dict:
    last_line = ""
    while True:
        run = repo.get_sync_run(sync_id)
        if not run:
            raise RuntimeError(f"sync_run {sync_id} no encontrado")
        line = _render_progress(label, run)
        if line != last_line:
            print(line, flush=True)
            last_line = line
        if run.get("status") in TERMINAL_STATUSES:
            return run
        await asyncio.sleep(poll_sec)


async def run_full_load(
    *,
    batch_size: int,
    lookback_days: int | None,
    poll_sec: float,
    skip_associations: bool,
    skip_analytics: bool,
) -> int:
    hubspot = await get_hubspot_client()
    sync = SyncService(hubspot_client=hubspot)
    assoc = AssociationsSyncService(hubspot_client=hubspot)
    repo = SupabaseRepository()
    started = time.perf_counter()
    exit_code = 0

    print("=== Fase 1/3: objetos CRM + actividades (full) ===")
    crm_run = await sync.start_sync(
        object_type="all",
        sync_type="full",
        batch_size=batch_size,
        lookback_days=lookback_days,
    )
    crm_id = str(crm_run["id"])
    print(f"sync_run_id={crm_id}")
    crm_final = await poll_sync_run(repo, crm_id, "CRM", poll_sec)
    if crm_final.get("status") != "completed":
        exit_code = 1

    if not skip_associations:
        print("\n=== Fase 2/3: asociaciones (full) ===")
        assoc_run = await assoc.start_sync(
            sync_group="all",
            sync_type="full",
            batch_size=batch_size,
        )
        assoc_id = str(assoc_run["id"])
        assoc_final = await poll_sync_run(repo, assoc_id, "ASOC", poll_sec)
        if assoc_final.get("status") != "completed":
            exit_code = 1

    if not skip_analytics:
        print("\n=== Fase 3/3: refresh analítica de negocios ===")
        da_repo = DealAnalyticsRepository()
        refresh = DealAnalyticsRefreshService(repository=da_repo)
        run_row = da_repo.create_run()
        run_id = str(run_row.get("id") or "")
        if not run_id:
            raise RuntimeError(f"No se obtuvo id del run de analítica: {run_row!r}")
        print(f"deal_analytics run_id={run_id}")

        async def _refresh_worker() -> None:
            await asyncio.to_thread(refresh._execute_refresh, run_id)

        worker = asyncio.create_task(_refresh_worker())
        result: dict = {}
        while not worker.done():
            current = da_repo.get_run(run_id) or {}
            st = current.get("status")
            print(
                f"[ANALYTICA] status={st} processed={current.get('deals_processed', 0)}",
                flush=True,
            )
            if st in TERMINAL_STATUSES:
                result = current
                break
            await asyncio.sleep(poll_sec)
        await worker
        if not result:
            result = da_repo.get_run(run_id) or {}
        print(
            f"[ANALITICA] final status={result.get('status')} "
            f"processed={result.get('deals_processed', 0)} failed={result.get('deals_failed', 0)}"
        )
        if result.get("status") not in ("completed", "completed_with_errors"):
            exit_code = 1

    duration = round(time.perf_counter() - started, 1)
    print(f"\nCarga completa finalizada en {duration}s (exit={exit_code})")
    await close_hubspot_client()
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga completa HubSpot en Supabase")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--lookback-days", type=int, default=60, help="Ventana actividades")
    parser.add_argument("--poll-sec", type=float, default=3.0)
    parser.add_argument("--skip-associations", action="store_true")
    parser.add_argument("--skip-analytics", action="store_true")
    args = parser.parse_args()

    code = asyncio.run(
        run_full_load(
            batch_size=args.batch_size,
            lookback_days=args.lookback_days,
            poll_sec=args.poll_sec,
            skip_associations=args.skip_associations,
            skip_analytics=args.skip_analytics,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
