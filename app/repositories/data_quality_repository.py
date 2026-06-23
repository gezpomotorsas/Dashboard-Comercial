"""Repositorio de calidad de datos."""

from typing import Any
from uuid import UUID

from app.clients.supabase import get_supabase_client
from app.repositories.supabase_repository import SupabaseRepository
from app.utils.dates import utc_now
from app.utils.serialization import to_json_serializable


class DataQualityRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()
        self._base = SupabaseRepository()

    def _execute(self, operation: Any) -> Any:
        return self._base._execute(operation)

    def list_active_rules(self, scope: str | None = None) -> list[dict[str, Any]]:
        query = self._client.table("data_quality_rules").select("*").eq("is_active", True)
        if scope and scope != "all":
            object_type = "activities" if scope == "activities" else scope.rstrip("s") + "s"
            if scope == "associations":
                object_type = "associations"
            query = query.eq("object_type", object_type)
        return self._execute(query)

    def create_quality_run(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        row = {
            "status": "started",
            "started_at": utc_now().isoformat(),
            "metadata": to_json_serializable(metadata or {}),
        }
        data = self._execute(self._client.table("data_quality_runs").insert(row))
        return data[0] if isinstance(data, list) else data

    def update_quality_run(self, run_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any]:
        return self._execute(
            self._client.table("data_quality_runs")
            .update(to_json_serializable(updates))
            .eq("id", str(run_id))
        )

    def get_quality_run(self, run_id: UUID | str) -> dict[str, Any] | None:
        data = self._execute(
            self._client.table("data_quality_runs").select("*").eq("id", str(run_id)).limit(1)
        )
        return data[0] if data else None

    def list_quality_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._execute(
            self._client.table("data_quality_runs").select("*").order("started_at", desc=True).limit(limit)
        )

    def upsert_quality_results(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        return self._execute(
            self._client.table("data_quality_results").upsert(
                rows,
                on_conflict="rule_code,object_type,hubspot_id,issue_key",
            )
        )

    def resolve_missing_quality_results(
        self,
        *,
        run_id: UUID | str,
        active_fingerprints: set[tuple[str, str, str | None, str]],
    ) -> int:
        open_issues = self._execute(
            self._client.table("data_quality_results")
            .select("id,rule_code,object_type,hubspot_id,issue_key")
            .eq("is_resolved", False)
        )
        resolved = 0
        now = utc_now().isoformat()
        for issue in open_issues:
            fp = (
                issue["rule_code"],
                issue["object_type"],
                issue.get("hubspot_id"),
                issue["issue_key"],
            )
            if fp not in active_fingerprints:
                self._execute(
                    self._client.table("data_quality_results")
                    .update({"is_resolved": True, "resolved_at": now})
                    .eq("id", issue["id"])
                )
                resolved += 1
        return resolved

    def get_quality_summary(self) -> dict[str, Any]:
        open_issues = self._execute(
            self._client.table("data_quality_results")
            .select("rule_code,object_type,severity")
            .eq("is_resolved", False)
        )
        by_object: dict[str, int] = {}
        by_rule: dict[str, int] = {}
        severity_counts = {"critical": 0, "warning": 0, "info": 0}
        for issue in open_issues:
            severity = issue.get("severity", "info")
            if severity in severity_counts:
                severity_counts[severity] += 1
            obj = issue.get("object_type", "unknown")
            by_object[obj] = by_object.get(obj, 0) + 1
            code = issue.get("rule_code", "unknown")
            by_rule[code] = by_rule.get(code, 0) + 1

        runs = self.list_quality_runs(limit=1)
        last_run_at = runs[0]["started_at"] if runs else None

        return {
            "total_issues": len(open_issues),
            "critical": severity_counts["critical"],
            "warning": severity_counts["warning"],
            "info": severity_counts["info"],
            "by_object_type": by_object,
            "by_rule": [{"rule_code": k, "count": v} for k, v in sorted(by_rule.items())],
            "last_run_at": last_run_at,
        }

    def list_quality_results(
        self,
        *,
        rule_code: str | None = None,
        object_type: str | None = None,
        severity: str | None = None,
        is_resolved: bool | None = False,
        hubspot_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        query = self._client.table("data_quality_results").select("*", count="exact")
        if rule_code:
            query = query.eq("rule_code", rule_code)
        if object_type:
            query = query.eq("object_type", object_type)
        if severity:
            query = query.eq("severity", severity)
        if is_resolved is not None:
            query = query.eq("is_resolved", is_resolved)
        if hubspot_id:
            query = query.eq("hubspot_id", hubspot_id)
        query = query.order("detected_at", desc=True).range(offset, offset + limit - 1)
        response = query.execute()
        return response.data or [], response.count or 0

    def fetch_objects_page(
        self,
        table: str,
        *,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self._execute(
            self._client.table(table).select("*").order("hubspot_id").range(offset, offset + limit - 1)
        )

    def fetch_active_association_keys(self) -> set[tuple[str, str]]:
        rows = self._execute(
            self._client.table("hubspot_associations")
            .select("from_object_type,from_hubspot_id,to_object_type,to_hubspot_id")
            .eq("is_active", True)
            .limit(50000)
        )
        keys: set[tuple[str, str]] = set()
        for r in rows:
            keys.add((r["from_object_type"], r["from_hubspot_id"]))
            keys.add((r["to_object_type"], r["to_hubspot_id"]))
        return keys

    def table_exists_ids(self, table: str, hubspot_ids: list[str]) -> set[str]:
        if not hubspot_ids:
            return set()
        rows = self._execute(
            self._client.table(table).select("hubspot_id").in_("hubspot_id", hubspot_ids)
        )
        return {str(r["hubspot_id"]) for r in rows}

    def get_pipeline_stage_ids(self) -> dict[str, set[str]]:
        rows = self._execute(
            self._client.table("hubspot_pipeline_stages").select("pipeline_id,stage_id")
        )
        result: dict[str, set[str]] = {}
        for row in rows:
            result.setdefault(str(row["pipeline_id"]), set()).add(str(row["stage_id"]))
        return result
