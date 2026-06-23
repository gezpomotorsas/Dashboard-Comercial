"""Backfill columnas indexadas tras sql/003."""

from __future__ import annotations

import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API = "http://localhost:8000"
TYPES = ("calls", "communications", "meetings", "tasks", "notes")
BODY = {"sync_type": "window", "lookback_days": 60, "batch_size": 100}


def main() -> int:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    print("=== Backfill columnas indexadas ===")

    for activity_type in TYPES:
        r = httpx.post(f"{API}/api/v1/sync/{activity_type}", json=BODY, timeout=60)
        r.raise_for_status()
        sync_id = r.json()["sync_id"]
        deadline = time.time() + 600
        run: dict = {}
        while time.time() < deadline:
            run = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=30).json()
            if run.get("status") in ("completed", "completed_with_errors", "failed"):
                break
            time.sleep(2)

        table = f"hubspot_{activity_type}"
        total = client.table(table).select("hubspot_id", count="exact").limit(0).execute().count or 0
        with_owner = (
            client.table(table)
            .select("hubspot_id", count="exact")
            .not_.is_("hubspot_owner_id", "null")
            .limit(0)
            .execute()
            .count
            or 0
        )
        with_ts = (
            client.table(table)
            .select("hubspot_id", count="exact")
            .not_.is_("activity_timestamp", "null")
            .limit(0)
            .execute()
            .count
            or 0
        )
        print(
            f"  {activity_type}: {run.get('status')} "
            f"proc={run.get('records_processed')} "
            f"owner={with_owner}/{total} ts={with_ts}/{total}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
