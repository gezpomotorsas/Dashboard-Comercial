"""Motor de ejecución de calidad de datos."""

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.repositories.data_quality_repository import DataQualityRepository
from app.services.data_quality.rules.activities import (
    ACTIVITY_TABLES,
    evaluate_activities,
    evaluate_broken_associations,
)
from app.services.data_quality.rules.contacts import evaluate_contacts
from app.services.data_quality.rules.deals import evaluate_deals
from app.utils.dates import utc_now

logger = logging.getLogger(__name__)

_running_quality: set[str] = set()
_quality_lock = asyncio.Lock()

PAGE_SIZE = 500


class DataQualityAlreadyRunningError(Exception):
    pass


class DataQualityEngine:
    def __init__(self, repository: DataQualityRepository | None = None) -> None:
        self._repository = repository or DataQualityRepository()

    async def start_run(self, scope: str = "all") -> dict[str, Any]:
        async with _quality_lock:
            if scope in _running_quality:
                raise DataQualityAlreadyRunningError(f"Análisis {scope} ya en ejecución")
            _running_quality.add(scope)

        run = self._repository.create_quality_run(metadata={"scope": scope})
        asyncio.create_task(self._run_safe(run_id=run["id"], scope=scope))
        return run

    async def _run_safe(self, *, run_id: str, scope: str) -> None:
        try:
            await asyncio.to_thread(self._execute_sync, run_id, scope)
        finally:
            async with _quality_lock:
                _running_quality.discard(scope)

    def _execute_sync(self, run_id: str, scope: str) -> None:
        self._repository.update_quality_run(run_id, {"status": "running"})
        rules_executed = 0
        records_evaluated = 0
        issues_found = 0
        active_fingerprints: set[tuple[str, str, str | None, str]] = set()

        try:
            assoc_rows = self._repository._execute(
                self._repository._client.table("hubspot_associations")
                .select("*")
                .eq("is_active", True)
                .limit(50000)
            )
            contact_deal_map, deal_contact_map, deal_activity_map, activity_linked = (
                self._build_association_maps(assoc_rows)
            )
            deal_pipeline_map = self._build_deal_pipeline_map()
            pipeline_stages = self._repository.get_pipeline_stage_ids()

            findings: list[dict[str, Any]] = []

            if scope in ("all", "contacts"):
                offset = 0
                while True:
                    rows = self._repository.fetch_objects_page("hubspot_contacts", offset=offset, limit=PAGE_SIZE)
                    if not rows:
                        break
                    records_evaluated += len(rows)
                    findings.extend(
                        evaluate_contacts(
                            rows,
                            contact_deal_map=contact_deal_map,
                            deal_pipeline_map=deal_pipeline_map,
                        )
                    )
                    offset += PAGE_SIZE

            if scope in ("all", "deals"):
                offset = 0
                while True:
                    rows = self._repository.fetch_objects_page("hubspot_deals", offset=offset, limit=PAGE_SIZE)
                    if not rows:
                        break
                    records_evaluated += len(rows)
                    findings.extend(
                        evaluate_deals(
                            rows,
                            deal_contact_map=deal_contact_map,
                            deal_activity_map=deal_activity_map,
                            pipeline_stages=pipeline_stages,
                        )
                    )
                    offset += PAGE_SIZE

            if scope in ("all", "activities"):
                for activity_type, table in ACTIVITY_TABLES.items():
                    offset = 0
                    while True:
                        rows = self._repository.fetch_objects_page(table, offset=offset, limit=PAGE_SIZE)
                        if not rows:
                            break
                        records_evaluated += len(rows)
                        findings.extend(
                            evaluate_activities(
                                rows,
                                activity_type=activity_type,
                                linked_ids=activity_linked,
                            )
                        )
                        offset += PAGE_SIZE

            if scope in ("all", "associations"):
                existing_ids = self._load_existing_ids()
                findings.extend(
                    evaluate_broken_associations(assoc_rows, existing_ids_by_type=existing_ids)
                )

            rules_executed = len({f["rule_code"] for f in findings})
            issues_found = len(findings)

            result_rows = []
            for f in findings:
                fp = (f["rule_code"], f["object_type"], f.get("hubspot_id"), f["issue_key"])
                active_fingerprints.add(fp)
                result_rows.append(
                    {
                        "run_id": str(run_id),
                        "rule_code": f["rule_code"],
                        "object_type": f["object_type"],
                        "hubspot_id": f.get("hubspot_id"),
                        "severity": f["severity"],
                        "message": f["message"],
                        "details": f.get("details", {}),
                        "issue_key": f["issue_key"],
                        "detected_at": utc_now().isoformat(),
                        "is_resolved": False,
                    }
                )

            for i in range(0, len(result_rows), 200):
                self._repository.upsert_quality_results(result_rows[i : i + 200])

            self._repository.resolve_missing_quality_results(
                run_id=UUID(run_id),
                active_fingerprints=active_fingerprints,
            )

            status = "completed"
            self._repository.update_quality_run(
                run_id,
                {
                    "status": status,
                    "finished_at": utc_now().isoformat(),
                    "rules_executed": rules_executed,
                    "records_evaluated": records_evaluated,
                    "issues_found": issues_found,
                },
            )
        except Exception as exc:
            logger.exception("Calidad de datos fallida")
            self._repository.update_quality_run(
                run_id,
                {
                    "status": "failed",
                    "finished_at": utc_now().isoformat(),
                    "error_message": str(exc),
                },
            )

    def _build_association_maps(
        self, rows: list[dict[str, Any]]
    ) -> tuple[dict[str, set[str]], dict[str, bool], dict[str, bool], set[str]]:
        contact_deal: dict[str, set[str]] = {}
        deal_contact: dict[str, bool] = {}
        deal_activity: dict[str, bool] = {}
        activity_linked: set[str] = set()
        activity_types = set(ACTIVITY_TABLES.keys())

        for row in rows:
            if not row.get("is_active", True):
                continue
            f_type, f_id = row["from_object_type"], str(row["from_hubspot_id"])
            t_type, t_id = row["to_object_type"], str(row["to_hubspot_id"])
            if f_type == "contacts" and t_type == "deals":
                contact_deal.setdefault(f_id, set()).add(t_id)
                deal_contact[t_id] = True
            if f_type == "deals" and t_type in activity_types:
                deal_activity[f_id] = True
                activity_linked.add(t_id)
            if f_type == "contacts" and t_type in activity_types:
                activity_linked.add(t_id)

        return contact_deal, deal_contact, deal_activity, activity_linked

    def _build_deal_pipeline_map(self) -> dict[str, str | None]:
        rows = self._repository.fetch_objects_page("hubspot_deals", offset=0, limit=50000)
        return {str(r["hubspot_id"]): r.get("pipeline_id") for r in rows}

    def _load_existing_ids(self) -> dict[str, set[str]]:
        tables = {
            "contacts": "hubspot_contacts",
            "deals": "hubspot_deals",
            **{k: v for k, v in ACTIVITY_TABLES.items()},
        }
        result: dict[str, set[str]] = {}
        for obj_type, table in tables.items():
            ids: set[str] = set()
            offset = 0
            while True:
                rows = self._repository.fetch_objects_page(table, offset=offset, limit=PAGE_SIZE)
                if not rows:
                    break
                ids.update(str(r["hubspot_id"]) for r in rows)
                offset += PAGE_SIZE
            result[obj_type] = ids
        return result

    def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        return self._repository.get_quality_run(run_id)

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._repository.list_quality_runs(limit)

    def get_summary(self) -> dict[str, Any]:
        return self._repository.get_quality_summary()

    def list_results(self, **filters: Any) -> tuple[list[dict[str, Any]], int]:
        return self._repository.list_quality_results(**filters)
