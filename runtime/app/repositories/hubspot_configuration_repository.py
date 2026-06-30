"""Repositorio de configuración dinámica HubSpot en Supabase."""

from __future__ import annotations

import logging
from typing import Any

from app.clients.supabase import get_supabase_client
from app.repositories.supabase_repository import SupabaseRepository
from app.utils.dates import utc_now
from app.utils.serialization import to_json_serializable

logger = logging.getLogger(__name__)


class HubSpotConfigurationRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()
        self._base = SupabaseRepository()

    def _execute(self, operation: Any) -> Any:
        return self._base._execute(operation)

    def fetch_all(self, table: str, *, columns: str = "*") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        while True:
            batch = self._execute(
                self._client.table(table).select(columns).range(offset, offset + page - 1)
            ) or []
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def upsert_association_types(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        payload = [
            {
                "from_object_type": item["from_object_type"],
                "to_object_type": item["to_object_type"],
                "association_type_id": item.get("association_type_id"),
                "association_category": item.get("association_category"),
                "association_label": item.get("association_label"),
                "is_active": item.get("is_active", True),
                "raw_payload": to_json_serializable(item.get("raw_payload") or {}),
                "synced_at": utc_now().isoformat(),
            }
            for item in rows
        ]
        return self._execute(
            self._client.table("hubspot_association_types").upsert(
                payload,
                on_conflict="from_object_type,to_object_type,association_type_id,association_category",
            )
        )

    def create_refresh_run(self) -> dict[str, Any]:
        row = {
            "status": "started",
            "started_at": utc_now().isoformat(),
        }
        data = self._execute(self._client.table("hubspot_metadata_refresh_runs").insert(row))
        return data[0] if isinstance(data, list) else data

    def update_refresh_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        data = self._execute(
            self._client.table("hubspot_metadata_refresh_runs")
            .update(to_json_serializable(updates))
            .eq("id", str(run_id))
        )
        return data[0] if isinstance(data, list) and data else updates

    def latest_refresh_run(self) -> dict[str, Any] | None:
        data = self._execute(
            self._client.table("hubspot_metadata_refresh_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(1)
        )
        return data[0] if data else None

    def update_field_mapping_validation(
        self,
        mapping_id: str,
        *,
        validation_status: str,
        validated_at: str | None = None,
        hubspot_property_label: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {
            "validation_status": validation_status,
            "validated_at": validated_at or utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        if hubspot_property_label is not None:
            updates["hubspot_property_label"] = hubspot_property_label
        self._execute(
            self._client.table("hubspot_field_mappings").update(updates).eq("id", mapping_id)
        )

    def next_mapping_versions(self) -> tuple[int, int]:
        latest = self.latest_refresh_run()
        if not latest:
            return 1, 1
        return (
            int(latest.get("field_mapping_version") or 1),
            int(latest.get("dimension_mapping_version") or 1),
        )
