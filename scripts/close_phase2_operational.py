"""Cierre operativo fase 2: sync completa, idempotencia, incremental, integridad y calidad."""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("PHASE2_API_URL", "http://localhost:8000")
BATCH_SIZE = int(os.getenv("PHASE2_SYNC_BATCH_SIZE", "100"))
SYNC_TIMEOUT = int(os.getenv("PHASE2_SYNC_TIMEOUT_SEC", "7200"))
REPORT_PATH = Path(__file__).resolve().parent / "phase2_closure_report.json"

SYNC_GROUPS = ("contact-deal", "contact-activities", "deal-activities")
PAIR_LABELS = [
    ("contacts", "deals"),
    ("contacts", "calls"),
    ("contacts", "meetings"),
    ("contacts", "tasks"),
    ("contacts", "emails"),
    ("contacts", "communications"),
    ("contacts", "notes"),
    ("deals", "calls"),
    ("deals", "meetings"),
    ("deals", "tasks"),
    ("deals", "emails"),
    ("deals", "communications"),
    ("deals", "notes"),
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def poll_sync(sync_id: str) -> dict:
    start = time.time()
    while time.time() - start < SYNC_TIMEOUT:
        r = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=180)
        body = r.json()
        status = body.get("status")
        if status in ("completed", "completed_with_errors", "failed"):
            md = body.get("metadata") or {}
            return {
                "sync_id": sync_id,
                "status": status,
                "records_found": body.get("records_found"),
                "records_processed": body.get("records_processed"),
                "records_failed": body.get("records_failed"),
                "duration_seconds": md.get("duration_seconds"),
                "error_message": body.get("error_message"),
            }
        time.sleep(5)
    return {"sync_id": sync_id, "status": "timeout"}


def run_sync(group: str, sync_type: str) -> dict:
    started = time.time()
    r = httpx.post(
        f"{API}/api/v1/sync/associations/{group}",
        json={"sync_type": sync_type, "batch_size": BATCH_SIZE},
        timeout=60,
    )
    if r.status_code != 200:
        return {"group": group, "sync_type": sync_type, "http_status": r.status_code, "error": r.text[:200]}
    sync_id = r.json()["sync_id"]
    result = poll_sync(sync_id)
    result["group"] = group
    result["sync_type"] = sync_type
    result["wall_seconds"] = round(time.time() - started, 2)
    return result


def count_associations() -> dict[str, int]:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    total = client.table("hubspot_associations").select("id", count="exact").eq("is_active", True).limit(0).execute().count or 0
    by_pair: dict[str, int] = {}
    for from_t, to_t in PAIR_LABELS:
        key = f"{from_t}->{to_t}"
        n = (
            client.table("hubspot_associations")
            .select("id", count="exact")
            .eq("is_active", True)
            .eq("from_object_type", from_t)
            .eq("to_object_type", to_t)
            .limit(0)
            .execute()
            .count
            or 0
        )
        by_pair[key] = n
    return {"total_active": total, "by_pair": by_pair}


def load_id_set(table: str) -> set[str]:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    ids: set[str] = set()
    offset = 0
    while True:
        rows = client.table(table).select("hubspot_id").range(offset, offset + 999).execute().data
        if not rows:
            break
        ids.update(str(r["hubspot_id"]) for r in rows if r.get("hubspot_id"))
        offset += 1000
        if len(rows) < 1000:
            break
    return ids


def integrity_checks() -> dict:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    table_map = {
        "contacts": "hubspot_contacts",
        "deals": "hubspot_deals",
        "calls": "hubspot_calls",
        "meetings": "hubspot_meetings",
        "tasks": "hubspot_tasks",
        "emails": "hubspot_emails",
        "communications": "hubspot_communications",
        "notes": "hubspot_notes",
    }
    existing = {k: load_id_set(v) for k, v in table_map.items()}

    missing_from = 0
    missing_to = 0
    dup_keys: Counter[tuple] = Counter()
    contacts_with_deal: set[str] = set()
    deals_with_contact: set[str] = set()
    activity_linked: set[str] = set()
    offset = 0

    while True:
        rows = (
            client.table("hubspot_associations")
            .select(
                "from_object_type,from_hubspot_id,to_object_type,to_hubspot_id,association_type_id"
            )
            .eq("is_active", True)
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not rows:
            break
        for row in rows:
            f_type, f_id = row["from_object_type"], str(row["from_hubspot_id"])
            t_type, t_id = row["to_object_type"], str(row["to_hubspot_id"])
            type_id = row.get("association_type_id")
            dup_keys[(f_type, f_id, t_type, t_id, type_id)] += 1
            if f_type in existing and f_id not in existing[f_type]:
                missing_from += 1
            if t_type in existing and t_id not in existing[t_type]:
                missing_to += 1
            if f_type == "contacts" and t_type == "deals":
                contacts_with_deal.add(f_id)
                deals_with_contact.add(t_id)
            if t_type in {"calls", "meetings", "tasks", "emails", "communications", "notes"}:
                activity_linked.add(t_id)
        offset += 1000
        if len(rows) < 1000:
            break

    duplicates = sum(1 for c in dup_keys.values() if c > 1)
    contacts_total = len(existing["contacts"])
    deals_total = len(existing["deals"])
    activities_total = sum(len(existing[k]) for k in table_map if k not in ("contacts", "deals"))

    return {
        "missing_source_object": missing_from,
        "missing_target_object": missing_to,
        "logical_duplicates": duplicates,
        "contacts_without_deal": contacts_total - len(contacts_with_deal),
        "deals_without_contact": deals_total - len(deals_with_contact),
        "activities_without_contact_or_deal": activities_total - len(activity_linked),
    }


def cursor_state() -> list[dict]:
    from app.clients.supabase import get_supabase_client

    return (
        get_supabase_client()
        .table("sync_cursors")
        .select("object_type,last_successful_sync_at,updated_at")
        .ilike("object_type", "associations%")
        .execute()
        .data
    )


def run_quality() -> dict:
    r = httpx.post(f"{API}/api/v1/data-quality/run", json={"scope": "all"}, timeout=120)
    if r.status_code != 200:
        return {"http_status": r.status_code, "error": r.text[:200]}
    run_id = r.json()["run_id"]
    start = time.time()
    while time.time() - start < SYNC_TIMEOUT:
        run = httpx.get(f"{API}/api/v1/data-quality/runs/{run_id}", timeout=60).json()
        if run.get("status") in ("completed", "completed_with_errors", "failed"):
            summary = httpx.get(f"{API}/api/v1/data-quality/summary", timeout=120).json()
            from app.clients.supabase import get_supabase_client

            resolved = (
                get_supabase_client()
                .table("data_quality_results")
                .select("id", count="exact")
                .eq("is_resolved", True)
                .limit(0)
                .execute()
                .count
                or 0
            )
            return {
                "run_id": run_id,
                "status": run.get("status"),
                "records_evaluated": run.get("records_evaluated"),
                "issues_found": run.get("issues_found"),
                "rules_executed": run.get("rules_executed"),
                "summary": summary,
                "resolved_count": resolved,
            }
        time.sleep(5)
    return {"run_id": run_id, "status": "timeout"}


def main() -> int:
    allow_full = os.getenv("ALLOW_FULL_PHASE2_VALIDATION", "false").lower() == "true"
    sample_size = os.getenv("PHASE2_VALIDATION_SAMPLE_SIZE", "50")

    report: dict = {
        "started_at": _now(),
        "allow_full_phase2_validation": allow_full,
        "phase2_validation_sample_size": sample_size,
        "prior_sample_evidence": {
            "conclusion": "muestra limitada",
            "basis": [
                "validate_phase2.py usa batch_size=min(PHASE2_VALIDATION_SAMPLE_SIZE,100) con default 50",
                "associations_sync_service aplica sample_limit=phase2_validation_sample_size si ALLOW_FULL=false",
                "sync_runs previos muestran batch_size=50 y records_processed=125",
            ],
        },
        "counts_before": count_associations(),
        "full_syncs": [],
        "idempotency": [],
        "incremental": [],
        "cursors_after": [],
        "counts_after": {},
        "integrity": {},
        "quality": {},
    }

    if not allow_full:
        print("ERROR: ALLOW_FULL_PHASE2_VALIDATION debe ser true para cierre operativo completo")
        print(f"Config actual: ALLOW_FULL_PHASE2_VALIDATION={allow_full}")
        return 1

    print("=== Sync completa (secuencial) ===")
    for group in SYNC_GROUPS:
        print(f"  full {group}...")
        before = count_associations()["total_active"]
        result = run_sync(group, "full")
        after = count_associations()["total_active"]
        result["associations_before"] = before
        result["associations_after"] = after
        report["full_syncs"].append(result)
        print(f"    {result.get('status')} proc={result.get('records_processed')} saved_delta={after - before}")

        print(f"  idempotencia {group}...")
        count_before = count_associations()["total_active"]
        idem = run_sync(group, "full")
        count_after = count_associations()["total_active"]
        idem["associations_before"] = count_before
        idem["associations_after"] = count_after
        idem["idempotent"] = count_after == count_before
        report["idempotency"].append(idem)
        print(f"    idempotent={idem['idempotent']} {count_before}->{count_after}")

    print("=== Incremental ===")
    for group in SYNC_GROUPS:
        print(f"  incremental {group}...")
        cursors_before = cursor_state()
        inc = run_sync(group, "incremental")
        cursors_after = cursor_state()
        inc["cursors_before"] = cursors_before
        inc["cursors_after"] = cursors_after
        report["incremental"].append(inc)
        report["cursors_after"] = cursors_after
        print(f"    {inc.get('status')}")

    report["counts_after"] = count_associations()
    print("=== Integridad ===")
    report["integrity"] = integrity_checks()
    print("  ", report["integrity"])

    print("=== Calidad completa ===")
    report["quality"] = run_quality()
    print(f"  status={report['quality'].get('status')} issues={report['quality'].get('issues_found')}")

    report["finished_at"] = _now()
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Reporte: {REPORT_PATH}")

    ok = all(
        s.get("status") in ("completed", "completed_with_errors")
        for s in report["full_syncs"]
    ) and all(i.get("idempotent") for i in report["idempotency"])
    print("CIERRE:", "EXITO" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
