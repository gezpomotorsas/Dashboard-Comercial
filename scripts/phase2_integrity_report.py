"""Reporte de integridad y cierre parcial sin depender de HTTP bloqueado."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPORT = Path(__file__).resolve().parent / "phase2_closure_report.json"

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

ACTIVITY_TABLES = {
    "calls": "hubspot_calls",
    "meetings": "hubspot_meetings",
    "tasks": "hubspot_tasks",
    "emails": "hubspot_emails",
    "communications": "hubspot_communications",
    "notes": "hubspot_notes",
}


def count_by_pair() -> dict:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    total = client.table("hubspot_associations").select("id", count="exact").eq("is_active", True).limit(0).execute().count or 0
    by_pair = {}
    for from_t, to_t in PAIR_LABELS:
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
        by_pair[f"{from_t}->{to_t}"] = n
    return {"total_active": total, "by_pair": by_pair}


def load_ids(table: str) -> set[str]:
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


def association_integrity() -> dict:
    return integrity()


def missing_targets_by_activity_type() -> dict[str, int]:
    """Asociaciones activas cuyo destino de actividad no existe localmente."""
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    existing = {k: load_ids(t) for k, t in ACTIVITY_TABLES.items()}
    counts: dict[str, int] = {k: 0 for k in ACTIVITY_TABLES}
    offset = 0
    while True:
        rows = (
            client.table("hubspot_associations")
            .select("to_object_type,to_hubspot_id")
            .eq("is_active", True)
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not rows:
            break
        for row in rows:
            t_type = row["to_object_type"]
            if t_type not in ACTIVITY_TABLES:
                continue
            t_id = str(row["to_hubspot_id"])
            if t_id not in existing[t_type]:
                counts[t_type] += 1
        offset += 1000
        if len(rows) < 1000:
            break
    return counts


def activity_table_quality() -> dict:
    from app.clients.supabase import get_supabase_client
    from app.repositories.supabase_repository import SupabaseRepository

    client = get_supabase_client()
    use_index_columns = SupabaseRepository._activity_index_columns_ready()
    without_owner = 0
    without_timestamp = 0
    for table in ACTIVITY_TABLES.values():
        offset = 0
        fields = "hubspot_owner_id,activity_timestamp" if use_index_columns else "properties"
        while True:
            rows = (
                client.table(table)
                .select(fields)
                .range(offset, offset + 999)
                .execute()
                .data
            )
            if not rows:
                break
            for row in rows:
                if use_index_columns:
                    owner = row.get("hubspot_owner_id")
                    ts = row.get("activity_timestamp")
                else:
                    props = row.get("properties") or {}
                    owner = props.get("hubspot_owner_id")
                    ts = props.get("hs_timestamp")
                if not owner:
                    without_owner += 1
                if not ts:
                    without_timestamp += 1
            offset += 1000
            if len(rows) < 1000:
                break
    return {
        "activities_without_owner": without_owner,
        "activities_without_timestamp": without_timestamp,
        "index_columns_ready": use_index_columns,
    }


def integrity() -> dict:
    from app.clients.supabase import get_supabase_client

    client = get_supabase_client()
    existing = {"contacts": load_ids("hubspot_contacts"), "deals": load_ids("hubspot_deals")}
    for k, t in ACTIVITY_TABLES.items():
        existing[k] = load_ids(t)

    missing_from = missing_to = 0
    dup_keys: Counter[tuple] = Counter()
    contacts_with_deal: set[str] = set()
    deals_with_contact: set[str] = set()
    activity_linked: set[str] = set()
    offset = 0

    while True:
        rows = (
            client.table("hubspot_associations")
            .select("from_object_type,from_hubspot_id,to_object_type,to_hubspot_id,association_type_id")
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
            if t_type in ACTIVITY_TABLES:
                activity_linked.add(t_id)
        offset += 1000
        if len(rows) < 1000:
            break

    activities_total = sum(len(existing[k]) for k in ACTIVITY_TABLES)
    base = {
        "missing_source_object": missing_from,
        "missing_target_object": missing_to,
        "logical_duplicates": sum(1 for c in dup_keys.values() if c > 1),
        "contacts_without_deal": len(existing["contacts"]) - len(contacts_with_deal),
        "deals_without_contact": len(existing["deals"]) - len(deals_with_contact),
        "activities_without_contact_or_deal": max(0, activities_total - len(activity_linked)),
        "missing_targets_by_activity_type": missing_targets_by_activity_type(),
    }
    base.update(activity_table_quality())
    return base


async def run_quality() -> dict:
    from app.services.data_quality.engine import DataQualityEngine

    engine = DataQualityEngine()
    run = await engine.start_run(scope="all")
    run_id = run["id"]
    for _ in range(3600):
        row = engine.get_run(run_id)
        if row and row.get("status") in ("completed", "completed_with_errors", "failed"):
            break
        await asyncio.sleep(5)
    summary = engine.get_summary()
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
    row = engine.get_run(run_id) or {}
    return {
        "run_id": str(run_id),
        "status": row.get("status"),
        "records_evaluated": row.get("records_evaluated"),
        "issues_found": row.get("issues_found"),
        "summary": summary,
        "resolved_count": resolved,
    }


def main() -> int:
    report = {
        "counts": count_by_pair(),
        "integrity": integrity(),
    }
    print("=== Conteos ===")
    print(json.dumps(report["counts"], indent=2))
    print("=== Integridad ===")
    print(json.dumps(report["integrity"], indent=2))
    print("=== Calidad (directo) ===")
    report["quality"] = asyncio.run(run_quality())
    print(json.dumps({k: report["quality"][k] for k in ["status", "records_evaluated", "issues_found", "resolved_count"]}, indent=2))
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Guardado: {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
