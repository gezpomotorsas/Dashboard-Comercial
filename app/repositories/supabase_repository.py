"""Repositorio de persistencia en Supabase."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.clients.supabase import SupabaseClientError, get_supabase_client
from app.constants.activities import ACTIVITY_TABLE_MAP
from app.utils.activity_sync import extract_activity_timestamp
from app.utils.dates import to_iso8601, utc_now
from app.utils.serialization import to_json_serializable

logger = logging.getLogger(__name__)

_activity_index_columns_ready: bool | None = None

OBJECT_TABLE_MAP = {
    "contacts": "hubspot_contacts",
    "deals": "hubspot_deals",
    "calls": "hubspot_calls",
    "meetings": "hubspot_meetings",
    "tasks": "hubspot_tasks",
    "emails": "hubspot_emails",
    "communications": "hubspot_communications",
    "notes": "hubspot_notes",
}


class SupabaseRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()

    @staticmethod
    def _activity_index_columns_ready() -> bool:
        global _activity_index_columns_ready
        if _activity_index_columns_ready is True:
            return True
        try:
            get_supabase_client().table("hubspot_calls").select("hubspot_owner_id").limit(0).execute()
            _activity_index_columns_ready = True
        except Exception:
            _activity_index_columns_ready = False
            logger.warning(
                "Columnas hubspot_owner_id/activity_timestamp no disponibles; "
                "ejecute sql/003_activity_sync_columns.sql en Supabase"
            )
        return _activity_index_columns_ready

    def _execute(self, operation: Any) -> Any:
        try:
            response = operation.execute()
            if hasattr(response, "data"):
                return response.data
            return response
        except Exception as exc:
            logger.error("Error de escritura en Supabase")
            raise SupabaseClientError("Error al persistir datos en Supabase") from exc

    def transform_hubspot_object(self, object_type: str, record: dict[str, Any]) -> dict[str, Any]:
        properties = record.get("properties") or {}
        row: dict[str, Any] = {
            "hubspot_id": str(record.get("id")),
            "created_at_hubspot": to_iso8601(record.get("createdAt")),
            "updated_at_hubspot": to_iso8601(record.get("updatedAt")),
            "archived": bool(record.get("archived", False)),
            "properties": to_json_serializable(properties),
            "raw_payload": to_json_serializable(record),
            "synced_at": utc_now().isoformat(),
        }

        if object_type == "deals":
            pipeline_id = properties.get("pipeline")
            row["pipeline_id"] = pipeline_id
            row["dealstage_id"] = properties.get("dealstage")
            from app.services.hubspot_configuration import get_hubspot_config

            brand, _ = get_hubspot_config().resolve_deal_brand(
                {"properties": properties, "pipeline_id": pipeline_id}
            )
            row["brand"] = brand

        if object_type in ACTIVITY_TABLE_MAP and self._activity_index_columns_ready():
            owner = properties.get("hubspot_owner_id")
            row["hubspot_owner_id"] = str(owner) if owner not in (None, "") else None
            activity_ts = extract_activity_timestamp(record)
            row["activity_timestamp"] = to_iso8601(activity_ts)

        return row

    def existing_hubspot_ids(self, object_type: str, hubspot_ids: list[str]) -> set[str]:
        if not hubspot_ids or object_type not in OBJECT_TABLE_MAP:
            return set()
        table = OBJECT_TABLE_MAP[object_type]
        unique_ids = list({str(i) for i in hubspot_ids})
        found: set[str] = set()
        chunk_size = 100
        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i : i + chunk_size]
            rows = (
                self._execute(
                    self._client.table(table)
                    .select("hubspot_id")
                    .in_("hubspot_id", chunk)
                )
                or []
            )
            found.update(str(r["hubspot_id"]) for r in rows if r.get("hubspot_id"))
        return found

    def count_objects(self, object_type: str) -> int:
        if object_type not in OBJECT_TABLE_MAP:
            return 0
        table = OBJECT_TABLE_MAP[object_type]
        result = self._client.table(table).select("id", count="exact").limit(0).execute()
        return result.count or 0

    def upsert_objects(self, object_type: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        table = OBJECT_TABLE_MAP[object_type]
        rows = [self.transform_hubspot_object(object_type, record) for record in records]
        return self._execute(self._client.table(table).upsert(rows, on_conflict="hubspot_id"))

    def upsert_properties(self, object_type: str, properties: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = [
            {
                "object_type": object_type,
                "name": item.get("name"),
                "label": item.get("label"),
                "type": item.get("type"),
                "field_type": item.get("fieldType"),
                "group_name": item.get("groupName"),
                "description": item.get("description"),
                "options": to_json_serializable(item.get("options") or []),
                "calculated": item.get("calculated"),
                "hidden": item.get("hidden"),
                "created_at_hubspot": to_iso8601(item.get("createdAt")),
                "updated_at_hubspot": to_iso8601(item.get("updatedAt")),
                "raw_payload": to_json_serializable(item),
                "synced_at": utc_now().isoformat(),
            }
            for item in properties
        ]
        if not rows:
            return []
        return self._execute(
            self._client.table("hubspot_properties").upsert(rows, on_conflict="object_type,name")
        )

    def upsert_owners(self, owners: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = [
            {
                "hubspot_id": str(item.get("id")),
                "email": item.get("email"),
                "first_name": item.get("firstName"),
                "last_name": item.get("lastName"),
                "user_id": item.get("userId"),
                "teams": to_json_serializable(item.get("teams") or []),
                "archived": bool(item.get("archived", False)),
                "raw_payload": to_json_serializable(item),
                "synced_at": utc_now().isoformat(),
            }
            for item in owners
        ]
        if not rows:
            return []
        return self._execute(self._client.table("hubspot_owners").upsert(rows, on_conflict="hubspot_id"))

    def upsert_pipelines(self, pipelines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pipeline_rows = []
        stage_rows = []
        for pipeline in pipelines:
            pipeline_rows.append(
                {
                    "pipeline_id": str(pipeline.get("id")),
                    "label": pipeline.get("label"),
                    "display_order": pipeline.get("displayOrder"),
                    "archived": bool(pipeline.get("archived", False)),
                    "raw_payload": to_json_serializable(pipeline),
                    "synced_at": utc_now().isoformat(),
                }
            )
            for stage in pipeline.get("stages", []):
                stage_rows.append(
                    {
                        "pipeline_id": str(pipeline.get("id")),
                        "stage_id": str(stage.get("id")),
                        "label": stage.get("label"),
                        "display_order": stage.get("displayOrder"),
                        "metadata": to_json_serializable(stage.get("metadata") or {}),
                        "archived": bool(stage.get("archived", False)),
                        "raw_payload": to_json_serializable(stage),
                        "synced_at": utc_now().isoformat(),
                    }
                )

        results: list[dict[str, Any]] = []
        if pipeline_rows:
            results.extend(
                self._execute(
                    self._client.table("hubspot_pipelines").upsert(pipeline_rows, on_conflict="pipeline_id")
                )
            )
        if stage_rows:
            results.extend(
                self._execute(
                    self._client.table("hubspot_pipeline_stages").upsert(
                        stage_rows, on_conflict="pipeline_id,stage_id"
                    )
                )
            )
        return results

    def create_sync_run(
        self,
        *,
        object_type: str,
        sync_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "source": "hubspot",
            "object_type": object_type,
            "sync_type": sync_type,
            "status": "started",
            "started_at": utc_now().isoformat(),
            "metadata": to_json_serializable(metadata or {}),
        }
        data = self._execute(self._client.table("sync_runs").insert(row))
        return data[0] if isinstance(data, list) else data

    def update_sync_run(self, sync_id: UUID | str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = to_json_serializable(updates)
        if "metadata" in payload and isinstance(payload["metadata"], dict):
            # merge metadata jsonb
            existing = self.get_sync_run(sync_id)
            if existing and isinstance(existing.get("metadata"), dict):
                merged = {**existing["metadata"], **payload["metadata"]}
                payload["metadata"] = merged
        data = self._execute(
            self._client.table("sync_runs").update(payload).eq("id", str(sync_id))
        )
        return data[0] if isinstance(data, list) and data else updates

    def get_sync_run(self, sync_id: UUID | str) -> dict[str, Any] | None:
        data = self._execute(self._client.table("sync_runs").select("*").eq("id", str(sync_id)).limit(1))
        if not data:
            return None
        return data[0]

    def list_sync_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._execute(
            self._client.table("sync_runs").select("*").order("started_at", desc=True).limit(limit)
        )

    def create_sync_error(
        self,
        *,
        sync_run_id: UUID | str,
        object_type: str,
        hubspot_id: str | None,
        error_type: str,
        error_message: str,
        http_status: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "sync_run_id": str(sync_run_id),
            "object_type": object_type,
            "hubspot_id": hubspot_id,
            "error_type": error_type,
            "error_message": error_message,
            "http_status": http_status,
            "payload": to_json_serializable(payload or {}),
        }
        data = self._execute(self._client.table("sync_errors").insert(row))
        return data[0] if isinstance(data, list) else data

    def get_sync_cursor(self, object_type: str) -> dict[str, Any] | None:
        data = self._execute(
            self._client.table("sync_cursors").select("*").eq("object_type", object_type).limit(1)
        )
        if not data:
            return None
        return data[0]

    def upsert_sync_cursor(
        self,
        *,
        object_type: str,
        last_successful_sync_at: datetime,
        last_after: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "object_type": object_type,
            "last_successful_sync_at": last_successful_sync_at.isoformat(),
            "last_after": last_after,
            "updated_at": utc_now().isoformat(),
        }
        return self._execute(
            self._client.table("sync_cursors").upsert(row, on_conflict="object_type")
        )
