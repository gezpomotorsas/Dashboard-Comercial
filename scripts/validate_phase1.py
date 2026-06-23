"""Validación operativa fase 1 - sin exponer secretos."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from typing import Any

import httpx

from app.clients.supabase import get_supabase_client

# Evitar imprimir secretos al cargar settings
from app.config import get_settings
from app.services.hubspot_configuration import get_hubspot_config

API_BASE = "http://localhost:8000"
TABLES = [
    "sync_runs",
    "sync_errors",
    "sync_cursors",
    "hubspot_properties",
    "hubspot_owners",
    "hubspot_pipelines",
    "hubspot_pipeline_stages",
    "hubspot_contacts",
    "hubspot_deals",
]
REQUIRED_OBJECT_COLUMNS = {
    "hubspot_contacts": {"hubspot_id", "properties", "raw_payload", "synced_at"},
    "hubspot_deals": {
        "hubspot_id",
        "pipeline_id",
        "dealstage_id",
        "brand",
        "properties",
        "raw_payload",
        "synced_at",
    },
}
REPORT: dict[str, Any] = {}


def mask_config() -> None:
    settings = get_settings()
    token = settings.hubspot_access_token.get_secret_value()
    url = settings.supabase_url
    secret = settings.supabase_secret_key.get_secret_value()
    REPORT["config"] = {
        "HUBSPOT_ACCESS_TOKEN": "configurado" if token else "NO configurado",
        "SUPABASE_URL": "configurado" if url else "NO configurado",
        "SUPABASE_SECRET_KEY": "configurado" if secret else "NO configurado",
        "hubspot_alias": "hubspot_api_key_service" if token else None,
    }
    print("=== PASO 1: Configuración ===")
    for k, v in REPORT["config"].items():
        if k != "hubspot_alias":
            print(f"{k}: {v}")


def verify_tables() -> None:
    print("\n=== PASO 2: Tablas Supabase ===")
    client = get_supabase_client()
    results: dict[str, Any] = {}
    for table in TABLES:
        try:
            data = client.table(table).select("*").limit(1).execute()
            row = data.data[0] if data.data else {}
            columns = set(row.keys()) if row else set()
            required = REQUIRED_OBJECT_COLUMNS.get(table)
            missing_cols = required - columns if required and row else set()
            results[table] = {
                "exists": True,
                "sample_columns": sorted(columns) if columns else "vacía (sin filas)",
                "missing_required_columns": sorted(missing_cols) if missing_cols else [],
                "row_count_sample": len(data.data),
            }
            status = "OK"
            if missing_cols:
                status = "ESTRUCTURA INCOMPLETA"
            print(f"  {table}: {status}")
        except Exception as exc:
            results[table] = {"exists": False, "error": type(exc).__name__}
            print(f"  {table}: ERROR - {type(exc).__name__}")
    REPORT["tables"] = results


def api_get(path: str) -> tuple[int, Any]:
    with httpx.Client(base_url=API_BASE, timeout=120.0) as client:
        r = client.get(path)
        try:
            body = r.json()
        except Exception:
            body = r.text[:200]
        return r.status_code, body


def api_post(path: str, body: dict) -> tuple[int, Any]:
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        r = client.post(path, json=body)
        return r.status_code, r.json()


def verify_read_endpoints() -> None:
    print("\n=== PASO 3: Endpoints de lectura ===")
    endpoints = [
        "/health",
        "/version",
        "/api/v1/hubspot/metadata/contact-properties",
        "/api/v1/hubspot/metadata/deal-properties",
        "/api/v1/hubspot/metadata/owners",
        "/api/v1/hubspot/metadata/deal-pipelines",
        "/api/v1/hubspot/contacts?limit=2",
        "/api/v1/hubspot/deals?limit=2",
    ]
    results = []
    for path in endpoints:
        status, body = api_get(path)
        summary: dict[str, Any] = {"path": path, "status": status}
        text = json.dumps(body) if not isinstance(body, str) else body
        if "pat-" in text or "sb_secret" in text:
            summary["secrets_exposed"] = True
        else:
            summary["secrets_exposed"] = False

        if path == "/health" or path == "/version":
            summary["payload"] = body
        elif "metadata" in path:
            items = body if isinstance(body, list) else []
            summary["count"] = len(items)
            summary["sample_property_names"] = [
                i.get("name") for i in items[:5] if isinstance(i, dict)
            ]
        elif "contacts" in path:
            summary["count"] = body.get("meta", {}).get("count") if isinstance(body, dict) else 0
            summary["pagination"] = body.get("pagination") if isinstance(body, dict) else None
            summary["contact_ids"] = [
                i.get("id") for i in body.get("data", []) if isinstance(body, dict)
            ]
            props = body.get("data", [{}])[0].get("properties", {}) if isinstance(body, dict) and body.get("data") else {}
            summary["sample_property_keys"] = list(props.keys())[:8]
        elif "deals" in path:
            summary["count"] = body.get("meta", {}).get("count") if isinstance(body, dict) else 0
            summary["pagination"] = body.get("pagination") if isinstance(body, dict) else None
            deals = body.get("data", []) if isinstance(body, dict) else []
            summary["deal_ids"] = [d.get("id") for d in deals]
            summary["brands"] = [d.get("brand") for d in deals]
            summary["pipeline_ids"] = [
                d.get("properties", {}).get("pipeline") for d in deals
            ]
        results.append(summary)
        print(f"  {path}: HTTP {status}")
    REPORT["read_endpoints"] = results


def validate_brand_mapping() -> None:
    print("\n=== PASO 4: Mapeo de marcas ===")
    status, body = api_get("/api/v1/hubspot/deals?limit=100")
    deals = body.get("data", []) if isinstance(body, dict) else []
    pipeline_counter: Counter[str] = Counter()
    brand_counter: Counter[str | None] = Counter()
    mismatches = []
    for deal in deals:
        pipeline = deal.get("properties", {}).get("pipeline")
        brand = deal.get("brand")
        pipeline_counter[str(pipeline)] += 1
        brand_counter[brand] += 1
        config = get_hubspot_config()
        expected, _ = config.resolve_deal_brand({"properties": {"pipeline": pipeline}})
        if expected == "unknown":
            expected = None
        if expected != brand:
            mismatches.append({"id": deal.get("id"), "pipeline": pipeline, "brand": brand, "expected": expected})

    # Paginar más deals si hay más
    after = body.get("pagination", {}).get("next_after") if isinstance(body, dict) else None
    pages = 1
    while after and pages < 20:
        status, page = api_get(f"/api/v1/hubspot/deals?limit=100&after={after}")
        for deal in page.get("data", []):
            pipeline = deal.get("properties", {}).get("pipeline")
            brand = deal.get("brand")
            pipeline_counter[str(pipeline)] += 1
            brand_counter[brand] += 1
            config = get_hubspot_config()
            expected, _ = config.resolve_deal_brand({"properties": {"pipeline": pipeline}})
            if expected == "unknown":
                expected = None
            if expected != brand:
                mismatches.append({"id": deal.get("id"), "pipeline": pipeline, "brand": brand, "expected": expected})
        after = page.get("pagination", {}).get("next_after")
        pages += 1

    unknown_pipelines = [
        p for p in pipeline_counter if p not in get_hubspot_config().known_pipeline_ids and p != "None"
    ]
    REPORT["brand_mapping"] = {
        "deals_sampled": sum(pipeline_counter.values()),
        "by_pipeline": dict(pipeline_counter),
        "by_brand": dict(brand_counter),
        "unknown_pipelines": unknown_pipelines,
        "null_brand_count": brand_counter[None],
        "mismatches_count": len(mismatches),
        "mismatch_sample_ids": [m["id"] for m in mismatches[:5]],
    }
    print(f"  Negocios analizados: {sum(pipeline_counter.values())}")
    print(f"  Por pipeline: {dict(pipeline_counter)}")
    print(f"  Por marca: {dict(brand_counter)}")
    print(f"  Pipelines desconocidos: {unknown_pipelines}")
    print(f"  brand=null: {brand_counter[None]}")


def table_count(table: str) -> int:
    client = get_supabase_client()
    data = client.table(table).select("id", count="exact").limit(0).execute()
    return data.count or 0


def poll_sync(sync_id: str, timeout: int = 300) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        status, body = api_get(f"/api/v1/sync/runs/{sync_id}")
        if status != 200:
            return {"error": f"HTTP {status}", "body": body}
        st = body.get("status")
        if st in ("completed", "completed_with_errors", "failed"):
            return body
        time.sleep(2)
    return {"error": "timeout", "last_status": body.get("status")}


def run_sync(object_type: str, sync_type: str = "full") -> dict[str, Any]:
    status, body = api_post(
        f"/api/v1/sync/{object_type}",
        {"sync_type": sync_type, "batch_size": 100},
    )
    if status == 409:
        time.sleep(5)
        status, body = api_post(
            f"/api/v1/sync/{object_type}",
            {"sync_type": sync_type, "batch_size": 100},
        )
    if status != 200:
        return {"http_status": status, "error": body}
    sync_id = body.get("sync_id")
    result = poll_sync(sync_id)
    result["sync_id"] = sync_id
    result["counts_after"] = {
        "sync_runs": table_count("sync_runs"),
        "sync_errors": table_count("sync_errors"),
    }
    if object_type == "metadata":
        result["table_counts"] = {
            "hubspot_properties": table_count("hubspot_properties"),
            "hubspot_owners": table_count("hubspot_owners"),
            "hubspot_pipelines": table_count("hubspot_pipelines"),
            "hubspot_pipeline_stages": table_count("hubspot_pipeline_stages"),
        }
    elif object_type == "contacts":
        result["table_counts"] = {"hubspot_contacts": table_count("hubspot_contacts")}
    elif object_type == "deals":
        result["table_counts"] = {"hubspot_deals": table_count("hubspot_deals")}
    return result


def data_quality_checks(table: str) -> dict[str, Any]:
    client = get_supabase_client()
    if table == "hubspot_deals":
        select_cols = "hubspot_id,pipeline_id,dealstage_id,brand,properties,raw_payload"
    else:
        select_cols = "hubspot_id,properties,raw_payload"
    data = client.table(table).select(select_cols).execute()
    rows = data.data or []
    hubspot_ids = [r.get("hubspot_id") for r in rows]
    null_ids = sum(1 for i in hubspot_ids if not i)
    dup_ids = len(hubspot_ids) - len(set(hubspot_ids))
    empty_payload = sum(1 for r in rows if not r.get("raw_payload"))
    empty_props = sum(1 for r in rows if not r.get("properties"))
    result: dict[str, Any] = {
        "total_rows": len(rows),
        "null_hubspot_ids": null_ids,
        "duplicate_hubspot_ids": dup_ids,
        "empty_raw_payload": empty_payload,
        "empty_properties": empty_props,
    }
    if table == "hubspot_deals":
        result["by_brand"] = dict(Counter(r.get("brand") for r in rows))
        result["by_pipeline_id"] = dict(Counter(r.get("pipeline_id") for r in rows))
    return result


def main() -> int:
    mask_config()
    verify_tables()
    verify_read_endpoints()
    validate_brand_mapping()

    print("\n=== PASO 5: Sync metadata ===")
    meta_before = {
        "hubspot_properties": table_count("hubspot_properties"),
        "hubspot_owners": table_count("hubspot_owners"),
        "hubspot_pipelines": table_count("hubspot_pipelines"),
        "hubspot_pipeline_stages": table_count("hubspot_pipeline_stages"),
        "sync_runs": table_count("sync_runs"),
        "sync_errors": table_count("sync_errors"),
    }
    meta_sync = run_sync("metadata")
    meta_after = {
        "hubspot_properties": table_count("hubspot_properties"),
        "hubspot_owners": table_count("hubspot_owners"),
        "hubspot_pipelines": table_count("hubspot_pipelines"),
        "hubspot_pipeline_stages": table_count("hubspot_pipeline_stages"),
        "sync_runs": table_count("sync_runs"),
        "sync_errors": table_count("sync_errors"),
    }
    REPORT["metadata_sync"] = {"before": meta_before, "result": meta_sync, "after": meta_after}
    print(f"  Status: {meta_sync.get('status', meta_sync.get('error'))}")
    print(f"  Tablas después: {meta_after}")

    print("\n=== PASO 6: Sync contactos (1ra vez) ===")
    contacts_before = table_count("hubspot_contacts")
    contacts_sync_1 = run_sync("contacts")
    contacts_after_1 = table_count("hubspot_contacts")
    contacts_quality_1 = data_quality_checks("hubspot_contacts")
    REPORT["contacts_sync_1"] = {
        "before": contacts_before,
        "result": contacts_sync_1,
        "after": contacts_after_1,
        "quality": contacts_quality_1,
    }
    print(f"  Status: {contacts_sync_1.get('status')}")
    print(f"  Antes: {contacts_before} | Después: {contacts_after_1}")
    print(f"  Calidad: {contacts_quality_1}")

    print("\n=== PASO 6b: Sync contactos (2da vez - idempotencia) ===")
    contacts_sync_2 = run_sync("contacts")
    contacts_after_2 = table_count("hubspot_contacts")
    REPORT["contacts_sync_2"] = {
        "result": contacts_sync_2,
        "after": contacts_after_2,
        "idempotent": contacts_after_2 == contacts_after_1,
    }
    print(f"  Status: {contacts_sync_2.get('status')}")
    print(f"  Conteo 1ra: {contacts_after_1} | Conteo 2da: {contacts_after_2} | Idempotente: {contacts_after_2 == contacts_after_1}")

    print("\n=== PASO 7: Sync negocios (1ra vez) ===")
    deals_before = table_count("hubspot_deals")
    deals_sync_1 = run_sync("deals")
    deals_after_1 = table_count("hubspot_deals")
    deals_quality_1 = data_quality_checks("hubspot_deals")
    REPORT["deals_sync_1"] = {
        "before": deals_before,
        "result": deals_sync_1,
        "after": deals_after_1,
        "quality": deals_quality_1,
    }
    print(f"  Status: {deals_sync_1.get('status')}")
    print(f"  Antes: {deals_before} | Después: {deals_after_1}")
    print(f"  Calidad: {deals_quality_1}")

    print("\n=== PASO 7b: Sync negocios (2da vez - idempotencia) ===")
    deals_sync_2 = run_sync("deals")
    deals_after_2 = table_count("hubspot_deals")
    REPORT["deals_sync_2"] = {
        "result": deals_sync_2,
        "after": deals_after_2,
        "idempotent": deals_after_2 == deals_after_1,
    }
    print(f"  Status: {deals_sync_2.get('status')}")
    print(f"  Conteo 1ra: {deals_after_1} | Conteo 2da: {deals_after_2} | Idempotente: {deals_after_2 == deals_after_1}")

    print("\n=== PASO 8: Sync incremental contactos ===")
    inc_contacts = run_sync("contacts", sync_type="incremental")
    client = get_supabase_client()
    cursor_contacts = client.table("sync_cursors").select("*").eq("object_type", "contacts").limit(1).execute()
    REPORT["incremental_contacts"] = {
        "result": inc_contacts,
        "cursor": cursor_contacts.data[0] if cursor_contacts.data else None,
        "count_after": table_count("hubspot_contacts"),
    }
    print(f"  Status: {inc_contacts.get('status')}")
    print(f"  Cursor: {'presente' if cursor_contacts.data else 'ausente'}")

    print("\n=== PASO 8b: Sync incremental negocios ===")
    inc_deals = run_sync("deals", sync_type="incremental")
    cursor_deals = client.table("sync_cursors").select("*").eq("object_type", "deals").limit(1).execute()
    REPORT["incremental_deals"] = {
        "result": inc_deals,
        "cursor": cursor_deals.data[0] if cursor_deals.data else None,
        "count_after": table_count("hubspot_deals"),
    }
    print(f"  Status: {inc_deals.get('status')}")
    print(f"  Cursor: {'presente' if cursor_deals.data else 'ausente'}")

    # Errores finales
    errors = client.table("sync_errors").select("object_type,error_type,error_message,http_status").limit(20).execute()
    runs = client.table("sync_runs").select("object_type,sync_type,status,records_found,records_processed,records_failed").order("started_at", desc=True).limit(10).execute()
    REPORT["sync_errors_sample"] = errors.data
    REPORT["sync_runs_recent"] = runs.data

    report_path = "scripts/phase1_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2, default=str)
    print(f"\nReporte guardado en {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
