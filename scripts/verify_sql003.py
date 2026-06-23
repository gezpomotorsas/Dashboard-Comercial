"""Verifica migración sql/003_activity_sync_columns.sql."""

from __future__ import annotations

import json
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API = "http://localhost:8000"


def main() -> int:
    import app.repositories.supabase_repository as repo_mod
    from app.clients.supabase import get_supabase_client
    from app.repositories.supabase_repository import SupabaseRepository

    repo_mod._activity_index_columns_ready = None
    client = get_supabase_client()
    tables = {
        "calls": "hubspot_calls",
        "emails": "hubspot_emails",
        "communications": "hubspot_communications",
        "meetings": "hubspot_meetings",
        "tasks": "hubspot_tasks",
        "notes": "hubspot_notes",
    }

    report: dict = {"tables": {}, "index_columns_ready": False, "backfill": {}}

    print("=== Columnas SQL 003 ===")
    for label, table in tables.items():
        try:
            rows = (
                client.table(table)
                .select("hubspot_id,hubspot_owner_id,activity_timestamp")
                .limit(1)
                .execute()
                .data
            )
            sample = rows[0] if rows else {}
            report["tables"][label] = "OK"
            print(
                f"  {label}: OK owner={sample.get('hubspot_owner_id')} "
                f"ts={sample.get('activity_timestamp')}"
            )
        except Exception as exc:
            report["tables"][label] = f"ERROR: {type(exc).__name__}"
            print(f"  {label}: ERROR {type(exc).__name__}")

    repo = SupabaseRepository()
    report["index_columns_ready"] = repo._activity_index_columns_ready()
    print(f"index_columns_ready={report['index_columns_ready']}")

    print("\n=== Conteos actuales ===")
    report["counts"] = {k: repo.count_objects(k) for k in tables}
    for k, n in report["counts"].items():
        print(f"  {k}: {n}")

    print("\n=== Muestra calls (columna vs properties) ===")
    sample_rows = (
        client.table("hubspot_calls")
        .select("hubspot_id,hubspot_owner_id,activity_timestamp,properties")
        .limit(10)
        .execute()
        .data
    )
    col_owner = sum(1 for r in sample_rows if r.get("hubspot_owner_id"))
    col_ts = sum(1 for r in sample_rows if r.get("activity_timestamp"))
    prop_owner = sum(1 for r in sample_rows if (r.get("properties") or {}).get("hubspot_owner_id"))
    report["backfill"] = {
        "sample_size": len(sample_rows),
        "with_owner_column": col_owner,
        "with_timestamp_column": col_ts,
        "with_owner_in_properties": prop_owner,
    }
    print(f"  owner en columna: {col_owner}/{len(sample_rows)}")
    print(f"  timestamp en columna: {col_ts}/{len(sample_rows)}")

    needs_backfill = col_owner < len(sample_rows) and len(sample_rows) > 0
    report["needs_backfill"] = needs_backfill

    if needs_backfill and report["index_columns_ready"]:
        print("\n=== Backfill calls (incremental) para poblar columnas ===")
        try:
            r = httpx.post(
                f"{API}/api/v1/sync/calls",
                json={"sync_type": "incremental", "batch_size": 100},
                timeout=30,
            )
            r.raise_for_status()
            sync_id = r.json()["sync_id"]
            status = "running"
            for _ in range(120):
                run = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=30).json()
                status = run.get("status")
                if status in ("completed", "completed_with_errors", "failed"):
                    report["backfill_sync"] = {
                        "sync_id": sync_id,
                        "status": status,
                        "records_processed": run.get("records_processed"),
                        "records_updated": run.get("records_updated"),
                    }
                    break
                time.sleep(2)
            after = (
                client.table("hubspot_calls")
                .select("hubspot_id,hubspot_owner_id,activity_timestamp")
                .limit(10)
                .execute()
                .data
            )
            report["backfill_after"] = {
                "with_owner_column": sum(1 for r in after if r.get("hubspot_owner_id")),
                "with_timestamp_column": sum(1 for r in after if r.get("activity_timestamp")),
            }
            print(f"  sync status={status}")
            print(f"  tras backfill owner col: {report['backfill_after']['with_owner_column']}/10")
        except Exception as exc:
            report["backfill_sync"] = {"error": type(exc).__name__}
            print(f"  backfill error: {type(exc).__name__}")

    out = __file__.replace("verify_sql003.py", "verify_sql003_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nInforme: {out}")

    ok = report["index_columns_ready"] and all(v == "OK" for v in report["tables"].values())
    print("RESULTADO:", "OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
