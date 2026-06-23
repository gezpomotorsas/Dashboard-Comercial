#!/usr/bin/env python3
"""Sincronización completa HubSpot -> PostgreSQL local con progreso en consola."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
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


def _render_progress(run: dict) -> str:
    status = run.get("status", "?")
    phase = run.get("current_phase") or "-"
    found = run.get("records_found") or 0
    processed = run.get("records_processed") or 0
    inserted = run.get("records_inserted") or 0
    updated = run.get("records_updated") or 0
    failed = run.get("records_failed") or 0
    heartbeat = _format_ts(run.get("last_heartbeat"))
    return (
        f"[{status}] fase={phase} | encontrados={found} procesados={processed} "
        f"ins={inserted} upd={updated} err={failed} | latido={heartbeat}"
    )


async def poll_until_done(service: SyncService, sync_id: str, poll_sec: float) -> dict:
    last_line = ""
    while True:
        run = service.get_sync_run(sync_id)
        if not run:
            raise RuntimeError(f"sync_run {sync_id} no encontrado")
        line = _render_progress(run)
        if line != last_line:
            print(line, flush=True)
            last_line = line
        if run.get("status") in TERMINAL_STATUSES:
            return run
        await asyncio.sleep(poll_sec)


async def run_sync(
    *,
    object_type: str,
    sync_type: str,
    batch_size: int,
    lookback_days: int | None,
    poll_sec: float,
) -> int:
    hubspot = await get_hubspot_client()
    service = SyncService(hubspot_client=hubspot)
    started = time.perf_counter()

    print(
        f"Iniciando sync object_type={object_type} sync_type={sync_type} "
        f"batch_size={batch_size}"
    )
    sync_run = await service.start_sync(
        object_type=object_type,
        sync_type=sync_type,
        batch_size=batch_size,
        lookback_days=lookback_days,
    )
    sync_id = str(sync_run["id"])
    print(f"sync_run_id={sync_id}")

    final = await poll_until_done(service, sync_id, poll_sec)
    duration = round(time.perf_counter() - started, 1)
    print(f"\nFinalizado en {duration}s — status={final.get('status')}")
    if final.get("error_message"):
        print(f"Error: {final['error_message']}", file=sys.stderr)

    await close_hubspot_client()
    return 0 if final.get("status") == "completed" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync HubSpot completo contra PostgreSQL local")
    parser.add_argument("--object-type", default="all", help="metadata|contacts|deals|all|...")
    parser.add_argument("--sync-type", default="full", choices=["full", "incremental", "window"])
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--poll-sec", type=float, default=2.0)
    args = parser.parse_args()

    code = asyncio.run(
        run_sync(
            object_type=args.object_type,
            sync_type=args.sync_type,
            batch_size=args.batch_size,
            lookback_days=args.lookback_days,
            poll_sec=args.poll_sec,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
