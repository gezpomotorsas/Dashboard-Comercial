#!/usr/bin/env python3
"""Ejecuta metadata refresh + deal_analytics refresh de forma síncrona."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.repositories.deal_analytics_repository import DealAnalyticsRepository
from app.services.deal_analytics.refresh import DealAnalyticsRefreshService
from app.services.hubspot_configuration.refresh import HubSpotMetadataRefreshService


async def refresh_metadata() -> dict:
    client = await get_hubspot_client()
    try:
        return await HubSpotMetadataRefreshService(hubspot_client=client).refresh_hubspot_metadata()
    finally:
        await close_hubspot_client()


def refresh_deal_analytics() -> dict:
    repo = DealAnalyticsRepository()
    service = DealAnalyticsRefreshService(repository=repo)
    run = repo.create_run()
    run_id = str(run["id"])
    print(f"deal_analytics refresh iniciado: {run_id}")
    service._execute_refresh(run_id)
    result = repo.get_run(run_id) or {}
    return result


def main() -> int:
    repo = DealAnalyticsRepository()
    before = repo.count_analytics()
    deals = repo.count_deals()
    print(f"hubspot_deals: {deals}")
    print(f"deal_analytics antes: {before}")

    print("Refrescando metadata HubSpot...")
    t0 = time.perf_counter()
    meta = asyncio.run(refresh_metadata())
    print(
        f"Metadata OK en {time.perf_counter() - t0:.1f}s "
        f"(properties={meta.get('properties_synced')}, pipelines={meta.get('pipelines_synced')})"
    )

    print("Refrescando deal_analytics (puede tardar varios minutos)...")
    t1 = time.perf_counter()
    result = refresh_deal_analytics()
    elapsed = time.perf_counter() - t1

    after = repo.count_analytics()
    print(f"deal_analytics después: {after}")
    print(
        f"Refresh: status={result.get('status')} "
        f"processed={result.get('deals_processed')} "
        f"failed={result.get('deals_failed')} "
        f"duration={result.get('duration_seconds')}s "
        f"(elapsed={elapsed:.1f}s)"
    )
    if result.get("errors"):
        print(f"Errores (muestra): {result['errors'][:3]}")

    if after > 0 and result.get("status") in ("completed", "completed_with_errors"):
        print("RESULTADO: EXITO")
        return 0
    print("RESULTADO: FALLO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
