"""Lectura de datos para dashboard (solo Supabase)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.clients.supabase import get_supabase_client
from app.repositories.supabase_repository import SupabaseRepository
from app.utils.dates import parse_hubspot_datetime


def _normalize_owner_id(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized or None


def _row_owner_id(row: dict) -> str | None:
    owner = row.get("hubspot_owner_id")
    if owner in (None, ""):
        owner = (row.get("properties") or {}).get("hubspot_owner_id")
    return _normalize_owner_id(owner)


class DashboardRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()
        self._base = SupabaseRepository()

    def _execute(self, operation: Any) -> Any:
        return self._base._execute(operation)

    def fetch_all(
        self,
        table: str,
        *,
        columns: str = "*",
        date_column: str | None = None,
        gte: datetime | None = None,
        lt: datetime | None = None,
        order_column: str = "hubspot_id",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        while True:
            query = self._client.table(table).select(columns)
            if date_column and gte is not None:
                query = query.gte(date_column, gte.isoformat())
            if date_column and lt is not None:
                query = query.lt(date_column, lt.isoformat())
            batch = self._execute(query.order(order_column).range(offset, offset + page - 1)) or []
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def fetch_owners(self) -> list[dict[str, Any]]:
        return self.fetch_all("hubspot_owners", columns="hubspot_id,first_name,last_name,email,archived")

    def fetch_pipelines(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            "hubspot_pipelines",
            columns="pipeline_id,label,archived",
            order_column="pipeline_id",
        )

    def fetch_contact_deal_brands(self) -> dict[str, str]:
        """contact_hubspot_id -> brand desde primer deal asociado."""
        mapping: dict[str, str] = {}
        offset = 0
        while True:
            batch = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("is_active", True)
                .eq("from_object_type", "contacts")
                .eq("to_object_type", "deals")
                .range(offset, offset + 999)
            ) or []
            if not batch:
                break
            deal_ids = list({str(r["to_hubspot_id"]) for r in batch})
            deals = self._execute(
                self._client.table("hubspot_deals")
                .select("hubspot_id,brand,pipeline_id")
                .in_("hubspot_id", deal_ids)
            ) or []
            deal_brand = {
                str(d["hubspot_id"]): (d.get("brand") or "unknown")
                for d in deals
            }
            for row in batch:
                cid = str(row["from_hubspot_id"])
                if cid in mapping:
                    continue
                bid = deal_brand.get(str(row["to_hubspot_id"]))
                if bid:
                    mapping[cid] = bid
            offset += 1000
            if len(batch) < 1000:
                break
        return mapping

    def fetch_contact_activity_times(
        self,
        *,
        activity_types: tuple[str, ...] = ("calls", "communications", "meetings"),
    ) -> dict[str, list[datetime]]:
        """contact_id -> timestamps de actividades efectivas."""
        type_tables = {
            "calls": "hubspot_calls",
            "communications": "hubspot_communications",
            "meetings": "hubspot_meetings",
        }
        activity_ts: dict[str, datetime] = {}
        for activity_type in activity_types:
            table = type_tables[activity_type]
            for row in self.fetch_all(
                table,
                columns="hubspot_id,activity_timestamp,properties,hubspot_owner_id",
            ):
                ts = parse_hubspot_datetime(row.get("activity_timestamp"))
                if ts is None:
                    props = row.get("properties") or {}
                    raw = props.get("hs_timestamp")
                    if raw:
                        ts = parse_hubspot_datetime(str(raw))
                if activity_type == "meetings":
                    props = row.get("properties") or {}
                    outcome = str(props.get("hs_meeting_outcome") or "").upper()
                    if outcome and outcome not in ("COMPLETED", "COMPLETE"):
                        continue
                if ts:
                    activity_ts[str(row["hubspot_id"])] = ts

        contact_map: dict[str, list[datetime]] = {}
        offset = 0
        while True:
            batch = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id,to_object_type")
                .eq("is_active", True)
                .eq("from_object_type", "contacts")
                .in_("to_object_type", list(activity_types))
                .range(offset, offset + 999)
            ) or []
            if not batch:
                break
            for row in batch:
                aid = str(row["to_hubspot_id"])
                ts = activity_ts.get(aid)
                if not ts:
                    continue
                cid = str(row["from_hubspot_id"])
                contact_map.setdefault(cid, []).append(ts)
            offset += 1000
            if len(batch) < 1000:
                break
        return contact_map

    def fetch_advisor_activities(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        specs = [
            ("calls", "hubspot_calls", "effective"),
            ("communications", "hubspot_communications", "effective"),
            ("meetings", "hubspot_meetings", "effective"),
            ("tasks", "hubspot_tasks", "internal"),
            ("notes", "hubspot_notes", "internal"),
        ]
        counts: dict[str, dict[str, int]] = {}
        for key, table, _kind in specs:
            rows = self.fetch_all(
                table,
                columns="hubspot_owner_id,activity_timestamp,properties",
                date_column="activity_timestamp",
                gte=start,
                lt=end,
            )
            for row in rows:
                if key == "meetings":
                    props = row.get("properties") or {}
                    outcome = str(props.get("hs_meeting_outcome") or "").upper()
                    if outcome and outcome not in ("COMPLETED", "COMPLETE"):
                        continue
                owner = row.get("hubspot_owner_id")
                if not owner:
                    props = row.get("properties") or {}
                    owner = props.get("hubspot_owner_id")
                if not owner:
                    continue
                oid = str(owner)
                counts.setdefault(oid, {})
                counts[oid][key] = counts[oid].get(key, 0) + 1
        return [{"owner_id": k, **v} for k, v in counts.items()]

    def quality_summary(self) -> dict[str, Any]:
        from app.repositories.data_quality_repository import DataQualityRepository

        return DataQualityRepository().get_quality_summary()

    def fetch_owner_commercial_scope(
        self,
        owner_id: str,
        *,
        activity_gte: datetime,
        activity_lt: datetime,
    ) -> tuple[set[str], set[str]]:
        """Contactos y negocios atribuidos a un asesor (propietario directo + actividades)."""
        owner_id = _normalize_owner_id(owner_id) or owner_id
        contact_ids: set[str] = set()
        deal_ids: set[str] = set()

        for row in self.fetch_all("hubspot_contacts", columns="hubspot_id,properties"):
            if _normalize_owner_id((row.get("properties") or {}).get("hubspot_owner_id")) == owner_id:
                contact_ids.add(str(row["hubspot_id"]))

        for row in self.fetch_all("hubspot_deals", columns="hubspot_id,properties"):
            if _normalize_owner_id((row.get("properties") or {}).get("hubspot_owner_id")) == owner_id:
                deal_ids.add(str(row["hubspot_id"]))

        activity_specs = [
            ("calls", "hubspot_calls"),
            ("communications", "hubspot_communications"),
            ("meetings", "hubspot_meetings"),
            ("tasks", "hubspot_tasks"),
            ("notes", "hubspot_notes"),
        ]
        activity_ids: set[str] = set()
        activity_types: set[str] = set()
        for activity_type, table in activity_specs:
            rows = self.fetch_all(
                table,
                columns="hubspot_id,hubspot_owner_id,activity_timestamp,properties",
                date_column="activity_timestamp",
                gte=activity_gte,
                lt=activity_lt,
            )
            for row in rows:
                if activity_type == "meetings":
                    props = row.get("properties") or {}
                    outcome = str(props.get("hs_meeting_outcome") or "").upper()
                    if outcome and outcome not in ("COMPLETED", "COMPLETE"):
                        continue
                if _row_owner_id(row) != owner_id:
                    continue
                activity_ids.add(str(row["hubspot_id"]))
                activity_types.add(activity_type)

        if activity_ids:
            linked_contacts, linked_deals = self._objects_linked_to_activities(
                activity_ids,
                activity_types=tuple(activity_types),
            )
            contact_ids |= linked_contacts
            deal_ids |= linked_deals

        return contact_ids, deal_ids

    def _objects_linked_to_activities(
        self,
        activity_ids: set[str],
        *,
        activity_types: tuple[str, ...],
    ) -> tuple[set[str], set[str]]:
        contact_ids: set[str] = set()
        deal_ids: set[str] = set()
        if not activity_ids or not activity_types:
            return contact_ids, deal_ids

        ids_list = list(activity_ids)
        chunk_size = 100
        for chunk_start in range(0, len(ids_list), chunk_size):
            chunk = ids_list[chunk_start : chunk_start + chunk_size]
            for activity_type in activity_types:
                rows = self._execute(
                    self._client.table("hubspot_associations")
                    .select("from_object_type,from_hubspot_id,to_hubspot_id")
                    .eq("is_active", True)
                    .eq("to_object_type", activity_type)
                    .in_("to_hubspot_id", chunk)
                ) or []
                for row in rows:
                    from_type = row.get("from_object_type")
                    from_id = str(row["from_hubspot_id"])
                    if from_type == "contacts":
                        contact_ids.add(from_id)
                    elif from_type == "deals":
                        deal_ids.add(from_id)
        return contact_ids, deal_ids
