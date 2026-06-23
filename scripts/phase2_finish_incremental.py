"""Completa incrementales pendientes y calidad tras sync full."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API = "http://localhost:8000"
GROUPS = ("contact-activities", "deal-activities")
REPORT = Path(__file__).resolve().parent / "phase2_finish_report.json"


def poll(sync_id: str, timeout: int = 7200) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            body = httpx.get(f"{API}/api/v1/sync/runs/{sync_id}", timeout=180).json()
        except httpx.HTTPError:
            time.sleep(10)
            continue
        if body.get("status") in ("completed", "completed_with_errors", "failed"):
            return body
        time.sleep(10)
    return {"status": "timeout", "sync_id": sync_id}


def post_sync(group: str) -> dict:
    r = httpx.post(
        f"{API}/api/v1/sync/associations/{group}",
        json={"sync_type": "incremental", "batch_size": 100},
        timeout=120,
    )
    r.raise_for_status()
    sync_id = r.json()["sync_id"]
    result = poll(sync_id)
    result["group"] = group
    return result


async def quality() -> dict:
    from app.services.data_quality.engine import DataQualityEngine

    engine = DataQualityEngine()
    run = await engine.start_run(scope="all")
    run_id = run["id"]
    for _ in range(720):
        row = engine.get_run(run_id)
        if row and row.get("status") in ("completed", "failed", "completed_with_errors"):
            return {
                "run_id": str(run_id),
                "status": row.get("status"),
                "records_evaluated": row.get("records_evaluated"),
                "issues_found": row.get("issues_found"),
                "summary": engine.get_summary(),
            }
        await asyncio.sleep(5)
    return {"run_id": str(run_id), "status": "timeout"}


def main() -> int:
    if os.getenv("ALLOW_FULL_PHASE2_VALIDATION", "false").lower() != "true":
        print("Requiere ALLOW_FULL_PHASE2_VALIDATION=true en el entorno del servidor")
    report: dict = {"incremental": [], "quality": {}}
    for group in GROUPS:
        print(f"incremental {group}...")
        report["incremental"].append(post_sync(group))
        print(f"  {report['incremental'][-1].get('status')}")
    print("calidad...")
    report["quality"] = asyncio.run(quality())
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Guardado {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
