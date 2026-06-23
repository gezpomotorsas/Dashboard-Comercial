#!/usr/bin/env python3
"""Backfill hubspot_owner_id en hubspot_deals desde HubSpot batch/read."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.clients.supabase import get_supabase_client
from app.constants.crm_sync import DEAL_SYNC_PROPERTIES
from app.repositories.supabase_repository import SupabaseRepository
from app.utils.serialization import to_json_serializable

BATCH = 100


async def backfill() -> dict[str, int]:
    client = await get_hubspot_client()
    supabase = get_supabase_client()
    base = SupabaseRepository()
    updated = 0
    skipped = 0
    offset = 0

    props_to_fetch = list(DEAL_SYNC_PROPERTIES)

    while True:
        rows = (
            supabase.table("hubspot_deals")
            .select("hubspot_id,properties")
            .order("hubspot_id")
            .range(offset, offset + BATCH - 1)
            .execute()
            .data
            or []
        )
        if not rows:
            break

        ids = [str(r["hubspot_id"]) for r in rows]
        payload = await client.batch_read_objects("deals", object_ids=ids, properties=props_to_fetch)
        by_id = {str(item["id"]): item for item in payload.get("results", []) if item.get("id")}

        upserts: list[dict] = []
        for row in rows:
            deal_id = str(row["hubspot_id"])
            remote = by_id.get(deal_id)
            if not remote:
                skipped += 1
                continue
            merged = dict(row.get("properties") or {})
            merged.update(remote.get("properties") or {})
            upserts.append(
                to_json_serializable(
                    {
                        "hubspot_id": deal_id,
                        "properties": merged,
                        "pipeline_id": merged.get("pipeline"),
                        "dealstage_id": merged.get("dealstage"),
                    }
                )
            )

        if upserts:
            base._execute(supabase.table("hubspot_deals").upsert(upserts, on_conflict="hubspot_id"))
            updated += len(upserts)

        offset += BATCH
        if len(rows) < BATCH:
            break
        print(f"Procesados {offset} deals, actualizados {updated}...")

    await close_hubspot_client()
    return {"updated": updated, "skipped": skipped}


def main() -> int:
    result = asyncio.run(backfill())
    print(f"Backfill owner: actualizados={result['updated']} omitidos={result['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
