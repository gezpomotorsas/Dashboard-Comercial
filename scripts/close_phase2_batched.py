"""Cierre fase 2 en lotes pequeños con checkpoint y progreso visible.

Uso:
  ALLOW_FULL_PHASE2_VALIDATION=true
  .venv\\Scripts\\python scripts\\close_phase2_batched.py
  .venv\\Scripts\\python scripts\\close_phase2_batched.py --group contact-deal --phase incremental
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("PHASE2_API_URL", "http://localhost:8000")
OBJECT_CHUNK = int(os.getenv("PHASE2_OBJECT_CHUNK", "500"))
BATCH_SIZE = int(os.getenv("PHASE2_SYNC_BATCH_SIZE", "100"))
POLL_SEC = int(os.getenv("PHASE2_POLL_SEC", "3"))
CHUNK_TIMEOUT = int(os.getenv("PHASE2_CHUNK_TIMEOUT_SEC", "900"))

STATE_PATH = Path(__file__).resolve().parent / "phase2_batch_state.json"
REPORT_PATH = Path(__file__).resolve().parent / "phase2_batch_report.json"

GROUPS = ("contact-deal", "contact-activities", "deal-activities")
SOURCE_TABLE = {
    "contact-deal": "hubspot_contacts",
    "contact-activities": "hubspot_contacts",
    "deal-activities": "hubspot_deals",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"offsets": {}, "history": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def count_source(table: str) -> int:
    from app.config import get_settings
    from app.repositories.associations_repository import AssociationsRepository
    from app.utils.association_sync import lookback_modified_since_iso

    lookback = get_settings().association_sync_lookback_days
    field = get_settings().association_sync_lookback_field
    modified_since = lookback_modified_since_iso(lookback)
    return AssociationsRepository().count_hubspot_objects(
        table,
        modified_since=modified_since,
        lookback_field=field,
    )


def lookback_label() -> str:
    from app.config import get_settings

    days = get_settings().association_sync_lookback_days
    field = get_settings().association_sync_lookback_field
    if not days:
        return "sin_limite"
    return f"ultimos_{days}d_por_{field}"


def count_assoc_total() -> int:
    from app.repositories.associations_repository import AssociationsRepository

    return AssociationsRepository().count_associations(is_active=True)


def poll_sync(sync_id: str) -> dict:
    start = time.time()
    last_proc = -1
    while time.time() - start < CHUNK_TIMEOUT:
        try:
            body = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=60).json()
        except httpx.HTTPError:
            time.sleep(POLL_SEC)
            continue
        status = body.get("status")
        proc = body.get("records_processed") or 0
        md = body.get("metadata") or {}
        if proc != last_proc or status != "running":
            print(
                f"      poll status={status} proc={proc} fail={body.get('records_failed')} "
                f"objects={md.get('objects_processed')} batches={md.get('hubspot_batches')}"
            )
            last_proc = proc
        if status in ("completed", "completed_with_errors", "failed"):
            return {
                "sync_id": sync_id,
                "status": status,
                "records_processed": proc,
                "records_failed": body.get("records_failed"),
                "error_message": body.get("error_message"),
                "metadata": md,
            }
        time.sleep(POLL_SEC)
    return {"sync_id": sync_id, "status": "timeout"}


def run_chunk(
    group: str,
    *,
    sync_type: str,
    object_offset: int,
    object_limit: int,
) -> dict:
    payload = {
        "sync_type": sync_type,
        "batch_size": BATCH_SIZE,
        "object_offset": object_offset,
        "object_limit": object_limit,
    }
    r = httpx.post(f"{API}/api/v1/sync/associations/{group}", json=payload, timeout=120)
    if r.status_code == 409:
        print("      esperando lock...")
        time.sleep(10)
        r = httpx.post(f"{API}/api/v1/sync/associations/{group}", json=payload, timeout=120)
    if r.status_code != 200:
        return {"status": "http_error", "http_status": r.status_code, "error": r.text[:200]}
    sync_id = r.json()["sync_id"]
    return poll_sync(sync_id)


def run_group_batched(
    group: str,
    sync_type: str,
    state: dict,
    *,
    from_offset: int | None = None,
) -> list[dict]:
    table = SOURCE_TABLE[group]
    total = count_source(table)
    key = f"{sync_type}:{group}"
    offset = from_offset if from_offset is not None else state["offsets"].get(key, 0)
    results: list[dict] = []

    print(f"\n=== {sync_type} {group} | ventana={lookback_label()} total_objetos={total} offset_inicial={offset} chunk={OBJECT_CHUNK} batch={BATCH_SIZE} ===")

    while offset < total:
        assoc_before = count_assoc_total()
        print(f"  lote offset={offset} limit={OBJECT_CHUNK} assoc_activas={assoc_before}")
        chunk = run_chunk(
            group,
            sync_type=sync_type,
            object_offset=offset,
            object_limit=OBJECT_CHUNK,
        )
        assoc_after = count_assoc_total()
        chunk["object_offset"] = offset
        chunk["object_limit"] = OBJECT_CHUNK
        chunk["associations_before"] = assoc_before
        chunk["associations_after"] = assoc_after
        chunk["associations_delta"] = assoc_after - assoc_before
        results.append(chunk)
        state["history"].append({"at": _now(), "group": group, "sync_type": sync_type, **chunk})
        save_state(state)

        if chunk.get("status") not in ("completed", "completed_with_errors"):
            print(f"  ERROR en lote offset={offset}: {chunk.get('status')} {chunk.get('error_message', '')[:120]}")
            break

        offset += OBJECT_CHUNK
        state["offsets"][key] = offset
        save_state(state)
        pct = min(100, round(offset / total * 100, 1)) if total else 100
        print(f"  OK lote -> offset_siguiente={offset} ({pct}%) assoc_delta={chunk['associations_delta']}")

    if offset >= total:
        print(f"  {group} {sync_type} COMPLETO ({total} objetos)")
        state["offsets"][key] = total

    save_state(state)
    return results


def finalize_incremental_cursor(group: str) -> None:
    from app.repositories.associations_repository import AssociationsRepository
    from app.utils.dates import utc_now

    AssociationsRepository().upsert_sync_cursor(
        object_type=f"associations:{group}",
        last_successful_sync_at=utc_now(),
    )
    print(f"  cursor actualizado: associations:{group}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync asociaciones en lotes pequeños")
    parser.add_argument("--group", choices=GROUPS, help="Solo un grupo")
    parser.add_argument("--phase", choices=("full", "incremental", "both"), default="both")
    parser.add_argument("--reset-offset", action="store_true", help="Reinicia offsets guardados")
    parser.add_argument("--from-offset", type=int, default=None)
    args = parser.parse_args()

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    if os.getenv("ALLOW_FULL_PHASE2_VALIDATION", "false").lower() != "true":
        print("ADVERTENCIA: el servidor debe iniciarse con ALLOW_FULL_PHASE2_VALIDATION=true")

    try:
        health = httpx.get(f"{API}/health", timeout=15).status_code
        print(
            f"health={health} concurrencia_hubspot={settings.association_sync_hubspot_concurrency} "
            f"chunk={OBJECT_CHUNK} batch={BATCH_SIZE}"
        )
    except httpx.HTTPError as exc:
        print(f"API no disponible: {exc}")
        return 1

    state = load_state()
    if args.reset_offset:
        state["offsets"] = {}
        save_state(state)

    groups = (args.group,) if args.group else GROUPS
    report: dict = {"started_at": _now(), "chunks": [], "assoc_start": count_assoc_total()}

    phases = ("full", "incremental") if args.phase == "both" else (args.phase,)
    for sync_type in phases:
        for group in groups:
            chunks = run_group_batched(
                group,
                sync_type,
                state,
                from_offset=args.from_offset if args.from_offset is not None else None,
            )
            report["chunks"].extend(chunks)
            if sync_type == "incremental" and all(
                c.get("status") in ("completed", "completed_with_errors") for c in chunks
            ):
                key = f"{sync_type}:{group}"
                if state["offsets"].get(key, 0) >= count_source(SOURCE_TABLE[group]):
                    finalize_incremental_cursor(group)

    report["assoc_end"] = count_assoc_total()
    report["finished_at"] = _now()
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReporte: {REPORT_PATH}")
    print(f"Asociaciones: {report['assoc_start']} -> {report['assoc_end']}")
    failed = [c for c in report["chunks"] if c.get("status") not in ("completed", "completed_with_errors")]
    print("RESULTADO:", "EXITO" if not failed else f"REVISAR ({len(failed)} lotes fallidos)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
