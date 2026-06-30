"""Repositorio de asociaciones HubSpot en Supabase."""

import logging
import time
from collections.abc import Iterator
from typing import Any

from app.clients.supabase import SupabaseClientError, get_supabase_client
from app.repositories.supabase_repository import SupabaseRepository
from app.utils.dates import utc_now
from app.utils.serialization import to_json_serializable

logger = logging.getLogger(__name__)

_UNIQUE_KEY_FIELDS = (
    "from_object_type",
    "from_hubspot_id",
    "to_object_type",
    "to_hubspot_id",
    "association_type_id",
)


def _association_upsert_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in _UNIQUE_KEY_FIELDS)


def _dedupe_association_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Elimina duplicados dentro del mismo lote antes del upsert."""
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = _association_upsert_key(row)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = row
            continue
        if not existing.get("association_label") and row.get("association_label"):
            deduped[key] = row
    return list(deduped.values())


class AssociationsRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()
        self._base = SupabaseRepository()

    def _execute(self, operation: Any, *, retries: int = 3) -> Any:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return self._base._execute(operation)
            except SupabaseClientError as exc:
                last_exc = exc
                if attempt + 1 >= retries:
                    raise
                time.sleep(1.5 * (attempt + 1))
        if last_exc:
            raise last_exc
        raise SupabaseClientError("Error al persistir datos en Supabase")

    def transform_association(
        self,
        *,
        from_object_type: str,
        from_hubspot_id: str,
        to_object_type: str,
        to_hubspot_id: str,
        association_type_id: int | None,
        association_category: str | None,
        association_label: str | None,
        raw_payload: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        now = utc_now().isoformat()
        return {
            "from_object_type": from_object_type,
            "from_hubspot_id": str(from_hubspot_id),
            "to_object_type": to_object_type,
            "to_hubspot_id": str(to_hubspot_id),
            "association_type_id": association_type_id,
            "association_category": association_category,
            "association_label": association_label,
            "raw_payload": to_json_serializable(raw_payload or {}),
            "is_active": is_active,
            "last_seen_at": now,
            "synced_at": now,
        }

    def upsert_associations(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        unique_rows = _dedupe_association_rows(rows)
        saved: list[dict[str, Any]] = []
        chunk_size = 200
        for i in range(0, len(unique_rows), chunk_size):
            chunk = unique_rows[i : i + chunk_size]
            saved.extend(
                self._execute(
                    self._client.table("hubspot_associations").upsert(
                        chunk,
                        on_conflict="from_object_type,from_hubspot_id,to_object_type,to_hubspot_id,association_type_id",
                    )
                )
                or []
            )
        return saved

    def count_hubspot_objects(
        self,
        table: str,
        *,
        modified_since: str | None = None,
        lookback_field: str = "created_at_hubspot",
    ) -> int:
        query = self._client.table(table).select("hubspot_id", count="exact").limit(0)
        if modified_since:
            query = query.gte(lookback_field, modified_since)
        return query.execute().count or 0

    def iter_hubspot_ids(
        self,
        table: str,
        *,
        limit: int | None = None,
        start_offset: int = 0,
        max_objects: int | None = None,
        modified_since: str | None = None,
        lookback_field: str = "created_at_hubspot",
        page_size: int = 250,
    ) -> Iterator[list[str]]:
        offset = start_offset
        collected = 0
        cap = max_objects if max_objects is not None else limit
        while True:
            if cap is not None and collected >= cap:
                return
            fetch_size = page_size
            if cap is not None:
                fetch_size = min(page_size, cap - collected)
            if fetch_size <= 0:
                return
            query = self._client.table(table).select("hubspot_id,updated_at_hubspot,created_at_hubspot")
            if modified_since:
                query = query.gte(lookback_field, modified_since)
            query = query.order("hubspot_id").range(offset, offset + fetch_size - 1)
            rows = self._execute(query)
            if not rows:
                break
            ids = [str(r["hubspot_id"]) for r in rows if r.get("hubspot_id")]
            if not ids:
                break
            yield ids
            collected += len(ids)
            offset += len(ids)
            if len(rows) < fetch_size:
                break

    def deactivate_associations_for_source(
        self,
        *,
        from_object_type: str,
        from_hubspot_id: str,
        active_keys: set[tuple[str, str, str, int | None]],
    ) -> None:
        existing = self._execute(
            self._client.table("hubspot_associations")
            .select("to_object_type,to_hubspot_id,association_type_id")
            .eq("from_object_type", from_object_type)
            .eq("from_hubspot_id", str(from_hubspot_id))
            .eq("is_active", True)
        )
        now = utc_now().isoformat()
        for row in existing:
            key = (
                from_object_type,
                str(from_hubspot_id),
                row["to_object_type"],
                row.get("association_type_id"),
            )
            full_key = (key[0], key[1], key[2], key[3])
            if full_key not in active_keys:
                query = (
                    self._client.table("hubspot_associations")
                    .update({"is_active": False, "synced_at": now})
                    .eq("from_object_type", from_object_type)
                    .eq("from_hubspot_id", str(from_hubspot_id))
                    .eq("to_object_type", row["to_object_type"])
                    .eq("to_hubspot_id", row.get("to_hubspot_id"))
                )
                type_id = row.get("association_type_id")
                if type_id is None:
                    query = query.is_("association_type_id", "null")
                else:
                    query = query.eq("association_type_id", type_id)
                self._execute(query)

    def list_associations(
        self,
        *,
        from_object_type: str | None = None,
        to_object_type: str | None = None,
        from_hubspot_id: str | None = None,
        is_active: bool | None = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        query = self._client.table("hubspot_associations").select("*", count="exact")
        if from_object_type:
            query = query.eq("from_object_type", from_object_type)
        if to_object_type:
            query = query.eq("to_object_type", to_object_type)
        if from_hubspot_id:
            query = query.eq("from_hubspot_id", from_hubspot_id)
        if is_active is not None:
            query = query.eq("is_active", is_active)
        query = query.order("synced_at", desc=True).range(offset, offset + limit - 1)
        response = query.execute()
        return response.data or [], response.count or 0

    def count_associations(self, **filters: Any) -> int:
        query = self._client.table("hubspot_associations").select("id", count="exact").limit(0)
        for key, value in filters.items():
            if value is not None:
                query = query.eq(key, value)
        response = query.execute()
        return response.count or 0

    def get_existing_association_keys(self, limit: int = 10000) -> set[tuple[str, str, str, str, int | None]]:
        rows = self._execute(
            self._client.table("hubspot_associations")
            .select("from_object_type,from_hubspot_id,to_object_type,to_hubspot_id,association_type_id")
            .eq("is_active", True)
            .limit(limit)
        )
        return {
            (
                r["from_object_type"],
                r["from_hubspot_id"],
                r["to_object_type"],
                r["to_hubspot_id"],
                r.get("association_type_id"),
            )
            for r in rows
        }

    def create_sync_run(self, **kwargs: Any) -> dict[str, Any]:
        return self._base.create_sync_run(**kwargs)

    def update_sync_run(self, sync_id: Any, updates: dict[str, Any]) -> dict[str, Any]:
        return self._base.update_sync_run(sync_id, updates)

    def create_sync_error(self, **kwargs: Any) -> dict[str, Any]:
        return self._base.create_sync_error(**kwargs)

    def get_sync_cursor(self, object_type: str) -> dict[str, Any] | None:
        return self._base.get_sync_cursor(object_type)

    def upsert_sync_cursor(self, **kwargs: Any) -> dict[str, Any]:
        return self._base.upsert_sync_cursor(**kwargs)
