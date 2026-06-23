"""Validación operativa fase 2."""

from __future__ import annotations

import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API = "http://localhost:8000"
ALLOW_FULL = os.getenv("ALLOW_FULL_PHASE2_VALIDATION", "false").lower() == "true"
SAMPLE = int(os.getenv("PHASE2_VALIDATION_SAMPLE_SIZE", "50"))


def check_tables() -> dict[str, str]:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    tables = [
        "hubspot_associations",
        "data_quality_rules",
        "data_quality_runs",
        "data_quality_results",
    ]
    result = {}
    for table in tables:
        try:
            if table == "sync_cursors":
                client.table(table).select("object_type", count="exact").limit(0).execute()
            else:
                client.table(table).select("id", count="exact").limit(0).execute()
            result[table] = "OK"
        except Exception as exc:
            result[table] = type(exc).__name__
    return result


def poll_sync(path: str, sync_id: str, timeout: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        r = httpx.get(f"{API}{path}/{sync_id}", timeout=30)
        body = r.json()
        if body.get("status") in ("completed", "completed_with_errors", "failed"):
            return body
        time.sleep(3)
    return {"error": "timeout"}


def count_assoc(**filters) -> int:
    from app.repositories.associations_repository import AssociationsRepository

    return AssociationsRepository().count_associations(**filters)


def main() -> int:
    print("=== Fase 2: verificación ===")
    print(f"ALLOW_FULL_PHASE2_VALIDATION={ALLOW_FULL}")

    tables = check_tables()
    print("Tablas:", tables)
    if any(v != "OK" for v in tables.values()):
        print("ERROR: Ejecuta sql/002_phase2_associations_quality.sql en Supabase")
        return 1

    print("\n=== Endpoints asociaciones ===")
    for path in [
        "/api/v1/hubspot/associations/types",
        "/api/v1/hubspot/associations/contact-deal?limit=2",
    ]:
        r = httpx.get(f"{API}{path}", timeout=120)
        print(f"  {path}: HTTP {r.status_code}")

    print("\n=== Sync contact-deal ===")
    before = count_assoc(is_active=True)
    r = httpx.post(
        f"{API}/api/v1/sync/associations/contact-deal",
        json={"sync_type": "full", "batch_size": min(SAMPLE, 100)},
        timeout=30,
    )
    print(f"  POST: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:300])
        return 1
    sync_id = r.json()["sync_id"]
    result = poll_sync("/api/v1/sync/runs", sync_id)
    after = count_assoc(is_active=True)
    print(f"  status={result.get('status')} before={before} after={after} processed={result.get('records_processed')}")

    print("\n=== Segunda sync (idempotencia) ===")
    r2 = httpx.post(
        f"{API}/api/v1/sync/associations/contact-deal",
        json={"sync_type": "full", "batch_size": min(SAMPLE, 100)},
        timeout=30,
    )
    sync_id2 = r2.json().get("sync_id")
    if sync_id2:
        poll_sync("/api/v1/sync/runs", sync_id2)
    after2 = count_assoc(is_active=True)
    print(f"  after2={after2} idempotente={after2 == after}")

    print("\n=== Incremental contact-deal ===")
    r3 = httpx.post(
        f"{API}/api/v1/sync/associations/contact-deal",
        json={"sync_type": "incremental", "batch_size": min(SAMPLE, 100)},
        timeout=30,
    )
    if r3.status_code == 200:
        inc = poll_sync("/api/v1/sync/runs", r3.json()["sync_id"])
        print(f"  incremental status={inc.get('status')}")

    print("\n=== Calidad de datos ===")
    qr = httpx.post(f"{API}/api/v1/data-quality/run", json={"scope": "all"}, timeout=60)
    print(f"  POST run: {qr.status_code}")
    if qr.status_code == 200:
        run_id = qr.json()["run_id"]
        for _ in range(120):
            run = httpx.get(f"{API}/api/v1/data-quality/runs/{run_id}", timeout=30).json()
            if run.get("status") in ("completed", "failed", "completed_with_errors"):
                break
            time.sleep(2)
        summary = httpx.get(f"{API}/api/v1/data-quality/summary", timeout=30).json()
        print(f"  issues={summary.get('total_issues')} critical={summary.get('critical')}")

    report = {
        "tables": tables,
        "associations_before": before,
        "associations_after": after,
        "associations_after_second": after2,
        "sync_result": {k: result.get(k) for k in ["status", "records_processed", "records_failed"]},
    }
    with open("scripts/phase2_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    ok = result.get("status") in ("completed", "completed_with_errors") and after2 == after
    print("\nRESULTADO:", "EXITO" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
