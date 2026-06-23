"""Verificación rápida post-creación de tablas."""

import json
import sys
import time

import httpx

from app.clients.supabase import get_supabase_client

API = "http://localhost:8000"


def count_table(table: str, col: str = "id") -> int:
    r = get_supabase_client().table(table).select(col, count="exact").limit(0).execute()
    return r.count or 0


def poll_sync(sync_id: str, timeout: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        r = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=30)
        body = r.json()
        if body.get("status") in ("completed", "completed_with_errors", "failed"):
            return body
        time.sleep(3)
    return {"error": "timeout"}


def run_sync(object_type: str, sync_type: str = "full") -> dict:
    r = httpx.post(
        f"{API}/api/v1/sync/{object_type}",
        json={"sync_type": sync_type, "batch_size": 100},
        timeout=30,
    )
    if r.status_code != 200:
        return {"http": r.status_code, "body": r.json()}
    sync_id = r.json()["sync_id"]
    result = poll_sync(sync_id)
    result["sync_id"] = sync_id
    return result


def main() -> None:
    report: dict = {}

    print("=== Tablas ===")
    tables = {
        "hubspot_properties": count_table("hubspot_properties"),
        "hubspot_owners": count_table("hubspot_owners"),
        "hubspot_pipelines": count_table("hubspot_pipelines"),
        "hubspot_pipeline_stages": count_table("hubspot_pipeline_stages"),
        "hubspot_contacts": count_table("hubspot_contacts"),
        "hubspot_deals": count_table("hubspot_deals"),
        "sync_runs": count_table("sync_runs"),
        "sync_errors": count_table("sync_errors"),
        "sync_cursors": count_table("sync_cursors", "object_type"),
    }
    for k, v in tables.items():
        print(f"  {k}: {v}")
    report["counts_before"] = tables

    print("\n=== Sync metadata ===")
    meta = run_sync("metadata")
    report["metadata"] = meta
    print(f"  status={meta.get('status')} processed={meta.get('records_processed')} failed={meta.get('records_failed')}")
    after_meta = {
        "hubspot_properties": count_table("hubspot_properties"),
        "hubspot_owners": count_table("hubspot_owners"),
        "hubspot_pipelines": count_table("hubspot_pipelines"),
        "hubspot_pipeline_stages": count_table("hubspot_pipeline_stages"),
        "sync_runs": count_table("sync_runs"),
        "sync_errors": count_table("sync_errors"),
    }
    report["after_metadata"] = after_meta
    print(f"  guardado: {after_meta}")

    print("\n=== Sync contactos (1ra) ===")
    c1 = run_sync("contacts")
    n1 = count_table("hubspot_contacts")
    report["contacts_1"] = {"sync": c1, "count": n1}
    print(f"  status={c1.get('status')} found={c1.get('records_found')} processed={c1.get('records_processed')} total_db={n1}")

    print("\n=== Sync contactos (2da - idempotencia) ===")
    c2 = run_sync("contacts")
    n2 = count_table("hubspot_contacts")
    report["contacts_2"] = {"sync": c2, "count": n2, "idempotent": n1 == n2}
    print(f"  status={c2.get('status')} total_db={n2} idempotente={n1 == n2}")

    print("\n=== Sync negocios (1ra) ===")
    d1 = run_sync("deals")
    nd1 = count_table("hubspot_deals")
    report["deals_1"] = {"sync": d1, "count": nd1}
    print(f"  status={d1.get('status')} found={d1.get('records_found')} processed={d1.get('records_processed')} total_db={nd1}")

    print("\n=== Sync negocios (2da - idempotencia) ===")
    d2 = run_sync("deals")
    nd2 = count_table("hubspot_deals")
    report["deals_2"] = {"sync": d2, "count": nd2, "idempotent": nd1 == nd2}
    print(f"  status={d2.get('status')} total_db={nd2} idempotente={nd1 == nd2}")

    print("\n=== Sync incremental contactos ===")
    inc_c = run_sync("contacts", "incremental")
    report["inc_contacts"] = inc_c
    print(f"  status={inc_c.get('status')}")

    print("\n=== Sync incremental negocios ===")
    inc_d = run_sync("deals", "incremental")
    report["inc_deals"] = inc_d
    print(f"  status={inc_d.get('status')}")

    cursors = get_supabase_client().table("sync_cursors").select("*").execute().data
    errors = get_supabase_client().table("sync_errors").select("object_type,error_type,error_message").limit(10).execute().data
    report["cursors"] = cursors
    report["errors"] = errors
    print(f"\n=== Cursors: {len(cursors)} | Errores: {len(errors)} ===")

    with open("scripts/verify_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    ok = (
        meta.get("status") == "completed"
        and c1.get("status") in ("completed", "completed_with_errors")
        and n1 == n2
        and nd1 == nd2
        and nd1 > 0
    )
    print("\nRESULTADO:", "EXITO" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
