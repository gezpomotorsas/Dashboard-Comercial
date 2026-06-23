"""Sincronización operativa de actividades recientes (ventana móvil)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _integrity_module():
    path = Path(__file__).resolve().parent / "phase2_integrity_report.py"
    spec = importlib.util.spec_from_file_location("phase2_integrity_report", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

API = os.getenv("PHASE2_API_URL", "http://localhost:8000")
POLL_SEC = int(os.getenv("ACTIVITY_SYNC_POLL_SEC", "2"))
POLL_TIMEOUT = int(os.getenv("ACTIVITY_SYNC_POLL_TIMEOUT_SEC", "1800"))
BATCH_SIZE = int(os.getenv("ACTIVITY_SYNC_BATCH_SIZE", "100"))

REPORT_PATH = Path(__file__).resolve().parent / "recent_activities_report.json"
INTEGRITY_BEFORE = 121320

ACTIVITY_TYPES = (
    "calls",
    "emails",
    "communications",
    "meetings",
    "tasks",
    "notes",
)

TABLES = {
    "calls": "hubspot_calls",
    "emails": "hubspot_emails",
    "communications": "hubspot_communications",
    "meetings": "hubspot_meetings",
    "tasks": "hubspot_tasks",
    "notes": "hubspot_notes",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def verify_tables() -> dict[str, str]:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    status: dict[str, str] = {}
    for activity_type, table in TABLES.items():
        try:
            client.table(table).select("id", count="exact").limit(0).execute()
            status[activity_type] = "OK"
        except Exception as exc:
            status[activity_type] = f"ERROR: {type(exc).__name__}"
    return status


def count_rows(activity_type: str) -> int:
    from app.repositories.supabase_repository import SupabaseRepository

    return SupabaseRepository().count_objects(activity_type)


def start_sync(activity_type: str, sync_type: str, lookback_days: int) -> dict:
    body: dict = {"sync_type": sync_type, "batch_size": BATCH_SIZE}
    if sync_type == "window":
        body["lookback_days"] = lookback_days
    r = httpx.post(
        f"{API}/api/v1/sync/{activity_type}",
        json=body,
        timeout=60,
    )
    if r.status_code != 200:
        return {"activity_type": activity_type, "http_status": r.status_code, "error": r.text[:200]}
    data = r.json()
    return {"activity_type": activity_type, "sync_id": data["sync_id"], "sync_type": sync_type}


def wait_sync(sync_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        r = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=30)
        if r.status_code != 200:
            time.sleep(POLL_SEC)
            continue
        run = r.json()
        status = run.get("status")
        if status in ("completed", "completed_with_errors", "failed"):
            return {
                "sync_id": sync_id,
                "status": status,
                "records_found": run.get("records_found", 0),
                "records_processed": run.get("records_processed", 0),
                "records_inserted": run.get("records_inserted", 0),
                "records_updated": run.get("records_updated", 0),
                "records_failed": run.get("records_failed", 0),
                "duration_seconds": (run.get("metadata") or {}).get("duration_seconds"),
                "records_excluded": (run.get("metadata") or {}).get("records_excluded", 0),
            }
        time.sleep(POLL_SEC)
    return {"sync_id": sync_id, "status": "timeout"}


def run_activity_sequence(
    *,
    sync_type: str,
    lookback_days: int,
    label: str,
) -> list[dict]:
    results: list[dict] = []
    for activity_type in ACTIVITY_TYPES:
        started = time.perf_counter()
        count_before = count_rows(activity_type)
        kick = start_sync(activity_type, sync_type, lookback_days)
        if "error" in kick:
            results.append({**kick, "phase": label, "duration_seconds": round(time.perf_counter() - started, 2)})
            print(f"  {activity_type}: ERROR http={kick.get('http_status')}")
            continue
        outcome = wait_sync(kick["sync_id"])
        count_after = count_rows(activity_type)
        duration = round(time.perf_counter() - started, 2)
        entry = {
            "phase": label,
            "activity_type": activity_type,
            "sync_type": sync_type,
            "count_before": count_before,
            "count_after": count_after,
            "duration_seconds": duration,
            **outcome,
        }
        results.append(entry)
        print(
            f"  {activity_type}: status={outcome.get('status')} "
            f"found={outcome.get('records_found', 0)} "
            f"proc={outcome.get('records_processed', 0)} "
            f"ins={outcome.get('records_inserted', 0)} "
            f"upd={outcome.get('records_updated', 0)} "
            f"fail={outcome.get('records_failed', 0)} "
            f"rows={count_before}->{count_after} "
            f"dur={duration}s"
        )
    return results


def integrity_snapshot() -> dict:
    mod = _integrity_module()
    counts = mod.count_by_pair()
    integrity = mod.association_integrity()
    activity_counts = {t: count_rows(t) for t in ACTIVITY_TYPES}
    missing_by_type: dict[str, int] = {}
    for activity_type in ACTIVITY_TYPES:
        pair_c = counts["by_pair"].get(f"contacts->{activity_type}", 0)
        pair_d = counts["by_pair"].get(f"deals->{activity_type}", 0)
        local = activity_counts.get(activity_type, 0)
        missing_by_type[activity_type] = max(0, pair_c + pair_d - local)

    return {
        "total_active_associations": counts["total_active"],
        "missing_target_object": integrity["missing_target_object"],
        "missing_source_object": integrity["missing_source_object"],
        "activities_without_owner": integrity.get("activities_without_owner", 0),
        "activities_without_timestamp": integrity.get("activities_without_timestamp", 0),
        "activities_without_contact_or_deal": integrity["activities_without_contact_or_deal"],
        "activity_row_counts": activity_counts,
        "missing_targets_by_activity_type_estimate": missing_by_type,
    }


def kpi_readiness(activity_counts: dict[str, int], integrity: dict) -> dict:
    total_assoc = integrity.get("total_active_associations", 0)
    missing = integrity.get("missing_target_object", 0)
    resolved = max(0, total_assoc - missing)
    coverage = round((resolved / total_assoc) * 100, 2) if total_assoc else 0.0
    has_core = all(activity_counts.get(t, 0) > 0 for t in ("calls", "emails", "communications"))

    def status_for(metric: str) -> str:
        if not has_core:
            return "unavailable"
        if coverage >= 40:
            return "available" if metric in ("activities_by_owner", "calls_completed") else "partial"
        return "partial" if activity_counts.get("calls", 0) > 0 else "unavailable"

    metrics = [
        "activities_completed",
        "calls_completed",
        "emails_sent",
        "communications_sent",
        "meetings_completed",
        "activities_by_owner",
        "leads_without_activity",
        "first_response_minutes",
        "contacted_within_24h_rate",
    ]
    return {
        "analysis_window": "últimos 60 días",
        "association_coverage_pct": coverage,
        "kpis": {m: status_for(m) for m in metrics},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync actividades HubSpot ventana móvil")
    parser.add_argument("--days", type=int, default=int(os.getenv("ACTIVITY_SYNC_LOOKBACK_DAYS", "60")))
    parser.add_argument("--skip-idempotency", action="store_true")
    parser.add_argument("--skip-incremental", action="store_true")
    args = parser.parse_args()

    if not (1 <= args.days <= 90):
        print("lookback_days debe estar entre 1 y 90")
        return 1

    print("=== Verificación tablas ===")
    tables = verify_tables()
    for t, s in tables.items():
        print(f"  {t}: {s}")
    if any(v != "OK" for v in tables.values()):
        print("ADVERTENCIA: ejecuta sql/003_activity_sync_columns.sql en Supabase si faltan columnas")

    try:
        health = httpx.get(f"{API}/health", timeout=15).status_code
        print(f"health={health} ventana={args.days}d batch={BATCH_SIZE}")
    except Exception as exc:
        print(f"API no disponible: {type(exc).__name__}")
        return 1

    report: dict = {
        "started_at": _now(),
        "lookback_days": args.days,
        "tables": tables,
        "runs": [],
    }

    print("\n=== Integridad (antes) ===")
    report["integrity_before"] = integrity_snapshot()
    report["integrity_before"]["reference_missing_targets"] = INTEGRITY_BEFORE

    print(f"\n=== Window sync ({args.days} días) ===")
    window_runs = run_activity_sequence(sync_type="window", lookback_days=args.days, label="window")
    report["runs"].extend(window_runs)

    if not args.skip_idempotency:
        print("\n=== Idempotencia (segunda ventana) ===")
        idem_runs = run_activity_sequence(sync_type="window", lookback_days=args.days, label="idempotency")
        report["runs"].extend(idem_runs)

    if not args.skip_incremental:
        print("\n=== Incremental ===")
        inc_runs = run_activity_sequence(sync_type="incremental", lookback_days=args.days, label="incremental")
        report["runs"].extend(inc_runs)

    after = integrity_snapshot()
    report["integrity_after"] = after
    report["integrity_delta"] = {
        "missing_target_object": after["missing_target_object"] - report["integrity_before"]["missing_target_object"],
        "reference_missing_targets": INTEGRITY_BEFORE,
        "reduction_vs_reference": INTEGRITY_BEFORE - after["missing_target_object"],
    }
    report["kpi_readiness"] = kpi_readiness(after["activity_row_counts"], after)
    report["finished_at"] = _now()

    failed = [r for r in report["runs"] if r.get("status") == "failed"]
    email_scope_missing = any(
        r.get("activity_type") == "emails" and r.get("records_failed", 0) == 0
        for r in report["runs"]
    )
    report["email_scope_missing"] = email_scope_missing
    report["success"] = len(failed) == 0 and all(
        r.get("status") in ("completed", "completed_with_errors") for r in report["runs"] if "status" in r
    )

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nInforme: {REPORT_PATH}")
    print(
        f"Asociaciones destino inexistente: {report['integrity_before']['missing_target_object']} -> "
        f"{after['missing_target_object']} (ref {INTEGRITY_BEFORE})"
    )
    print(f"RESULTADO: {'EXITO' if report['success'] else 'CON ERRORES'}")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
