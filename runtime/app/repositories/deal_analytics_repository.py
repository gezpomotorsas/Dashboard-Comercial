"""Repositorio deal_analytics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.clients.supabase import get_supabase_client
from app.repositories.deal_analytics_filters import apply_db_filters
from app.repositories.supabase_repository import SupabaseRepository
from app.services.deal_analytics.filters import DealAnalyticsFilters
from app.utils.dates import utc_now
from app.utils.serialization import to_json_serializable


class DealAnalyticsRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()
        self._base = SupabaseRepository()

    def _execute(self, operation: Any) -> Any:
        return self._base._execute(operation)

    def fetch_contacts_by_ids(self, contact_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not contact_ids:
            return {}
        result: dict[str, dict[str, Any]] = {}
        chunk_size = 100
        for i in range(0, len(contact_ids), chunk_size):
            chunk = contact_ids[i : i + chunk_size]
            rows = self._execute(
                self._client.table("hubspot_contacts")
                .select("hubspot_id,properties")
                .in_("hubspot_id", chunk)
            ) or []
            for row in rows:
                result[str(row["hubspot_id"])] = row
        return result

    def count_filtered(self, filters: DealAnalyticsFilters) -> int:
        query = apply_db_filters(
            self._client.table("deal_analytics").select("deal_id", count="exact").limit(0),
            filters,
        )
        result = query.execute()
        return result.count or 0

    def fetch_filtered_page(
        self,
        filters: DealAnalyticsFilters,
        *,
        columns: str = "*",
        offset: int = 0,
        limit: int = 1000,
        order_by: str = "deal_id",
        ascending: bool = True,
    ) -> list[dict[str, Any]]:
        query = apply_db_filters(
            self._client.table("deal_analytics").select(columns).order(order_by, desc=not ascending),
            filters,
        )
        return self._execute(query.range(offset, offset + limit - 1)) or []

    def fetch_all_filtered(
        self,
        filters: DealAnalyticsFilters,
        *,
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        while True:
            batch = self.fetch_filtered_page(filters, columns=columns, offset=offset, limit=page)
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def fetch_deals_page(self, *, offset: int, limit: int) -> list[dict[str, Any]]:
        return self._execute(
            self._client.table("hubspot_deals")
            .select("hubspot_id,created_at_hubspot,updated_at_hubspot,pipeline_id,dealstage_id,brand,properties")
            .order("hubspot_id")
            .range(offset, offset + limit - 1)
        ) or []

    def count_deals(self) -> int:
        result = self._client.table("hubspot_deals").select("hubspot_id", count="exact").limit(0).execute()
        return result.count or 0

    def fetch_all_associations(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        while True:
            batch = self._execute(
                self._client.table("hubspot_associations")
                .select("from_object_type,from_hubspot_id,to_object_type,to_hubspot_id,is_active")
                .eq("is_active", True)
                .range(offset, offset + page - 1)
            ) or []
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def fetch_activities_index(self) -> dict[str, dict[str, Any]]:
        specs = [
            ("calls", "hubspot_calls"),
            ("communications", "hubspot_communications"),
            ("meetings", "hubspot_meetings"),
            ("tasks", "hubspot_tasks"),
            ("notes", "hubspot_notes"),
        ]
        index: dict[str, dict[str, Any]] = {}
        for activity_type, table in specs:
            offset = 0
            while True:
                batch = self._execute(
                    self._client.table(table)
                    .select("hubspot_id,activity_timestamp,properties,hubspot_owner_id")
                    .order("hubspot_id")
                    .range(offset, offset + 999)
                ) or []
                if not batch:
                    break
                for row in batch:
                    meeting_completed = True
                    if activity_type == "meetings":
                        props = row.get("properties") or {}
                        outcome = str(props.get("hs_meeting_outcome") or "").upper()
                        meeting_completed = not outcome or outcome in {"COMPLETED", "COMPLETE"}
                    index[str(row["hubspot_id"])] = {
                        "activity_type": activity_type,
                        "activity_timestamp": row.get("activity_timestamp"),
                        "meeting_completed": meeting_completed,
                        "properties": row.get("properties") or {},
                        "hubspot_owner_id": row.get("hubspot_owner_id"),
                    }
                offset += 1000
                if len(batch) < 1000:
                    break
        return index

    def fetch_stage_history_by_deals(self, deal_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not deal_ids:
            return {}
        result: dict[str, list[dict[str, Any]]] = {deal_id: [] for deal_id in deal_ids}
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            rows = self._execute(
                self._client.table("hubspot_deal_stage_history")
                .select("*")
                .in_("deal_hubspot_id", chunk)
            ) or []
            for row in rows:
                result.setdefault(str(row["deal_hubspot_id"]), []).append(row)
        return result

    def fetch_task_ids_for_deals(self, deal_ids: list[str]) -> list[str]:
        return sorted(self.fetch_task_links_for_deals(deal_ids).keys())

    def fetch_task_links_for_deals(self, deal_ids: list[str]) -> dict[str, str]:
        """Mapa task_id -> deal_id (primera asociación activa)."""
        if not deal_ids:
            return {}
        links: dict[str, str] = {}
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "deals")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "tasks")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "deals")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "tasks")
                .eq("is_active", True)
            ) or []
            for row in forward:
                tid = str(row["to_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["from_hubspot_id"])
            for row in backward:
                tid = str(row["from_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["to_hubspot_id"])
        return links

    def fetch_deal_links_for_tasks(self, task_ids: list[str]) -> dict[str, str]:
        """Mapa task_id -> deal_id (primera asociación activa)."""
        if not task_ids:
            return {}
        links: dict[str, str] = {}
        chunk_size = 100
        for i in range(0, len(task_ids), chunk_size):
            chunk = task_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "tasks")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "deals")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "tasks")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "deals")
                .eq("is_active", True)
            ) or []
            for row in forward:
                tid = str(row["from_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["to_hubspot_id"])
            for row in backward:
                tid = str(row["to_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["from_hubspot_id"])
        return links

    def fetch_contact_links_for_tasks(self, task_ids: list[str]) -> dict[str, str]:
        """Mapa task_id -> contact_id (primera asociación activa)."""
        if not task_ids:
            return {}
        links: dict[str, str] = {}
        chunk_size = 100
        for i in range(0, len(task_ids), chunk_size):
            chunk = task_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "tasks")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "tasks")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            for row in forward:
                tid = str(row["from_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["to_hubspot_id"])
            for row in backward:
                tid = str(row["to_hubspot_id"])
                if tid not in links:
                    links[tid] = str(row["from_hubspot_id"])
        return links

    def fetch_contact_names_by_ids(self, contact_ids: list[str]) -> dict[str, str]:
        names: dict[str, str] = {}
        for contact_id, row in self.fetch_contacts_by_ids(contact_ids).items():
            props = row.get("properties") or {}
            first = str(props.get("firstname") or "").strip()
            last = str(props.get("lastname") or "").strip()
            full = f"{first} {last}".strip()
            names[contact_id] = full or str(props.get("email") or contact_id)
        return names

    def fetch_tasks_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            batch = self._execute(
                self._client.table("hubspot_tasks")
                .select("hubspot_id,properties,activity_timestamp,hubspot_owner_id,created_at_hubspot")
                .eq("hubspot_owner_id", owner_id)
                .order("hubspot_id")
                .range(offset, offset + 999)
            ) or []
            if not batch:
                break
            rows.extend(batch)
            offset += 1000
            if len(batch) < 1000:
                break
        return rows

    def fetch_deal_names_by_ids(self, deal_ids: list[str]) -> dict[str, str]:
        return {
            deal_id: ctx.get("deal_name") or deal_id
            for deal_id, ctx in self.fetch_deal_context_by_ids(deal_ids).items()
        }

    def fetch_deal_context_by_ids(self, deal_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Contexto de negocio para tareas: nombre, etapa y grupo comercial."""
        if not deal_ids:
            return {}
        context: dict[str, dict[str, Any]] = {}
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            analytics_rows = self._execute(
                self._client.table("deal_analytics")
                .select(
                    "deal_id,deal_name,stage_label,commercial_group_label,commercial_group,status,is_won,is_lost"
                )
                .in_("deal_id", chunk)
            ) or []
            for row in analytics_rows:
                deal_id = str(row["deal_id"])
                context[deal_id] = {
                    "deal_name": row.get("deal_name") or deal_id,
                    "stage_label": row.get("stage_label"),
                    "commercial_group_label": row.get("commercial_group_label"),
                    "commercial_group": row.get("commercial_group"),
                    "status": row.get("status"),
                    "is_won": bool(row.get("is_won")),
                    "is_lost": bool(row.get("is_lost")),
                }
            missing = [d for d in chunk if d not in context]
            if not missing:
                continue
            batch = self._execute(
                self._client.table("hubspot_deals")
                .select("hubspot_id,properties")
                .in_("hubspot_id", missing)
            ) or []
            for row in batch:
                deal_id = str(row["hubspot_id"])
                props = row.get("properties") or {}
                context.setdefault(
                    deal_id,
                    {
                        "deal_name": props.get("dealname") or deal_id,
                        "stage_label": None,
                        "commercial_group_label": None,
                        "status": None,
                    },
                )
        return context

    def fetch_tasks_by_ids(self, task_ids: list[str]) -> list[dict[str, Any]]:
        if not task_ids:
            return []
        rows: list[dict[str, Any]] = []
        chunk_size = 100
        for i in range(0, len(task_ids), chunk_size):
            chunk = task_ids[i : i + chunk_size]
            batch = self._execute(
                self._client.table("hubspot_tasks")
                .select("hubspot_id,properties,activity_timestamp,hubspot_owner_id,created_at_hubspot")
                .in_("hubspot_id", chunk)
            ) or []
            rows.extend(batch)
        return rows

    def fetch_activity_links_for_deals(
        self,
        deal_ids: list[str],
        activity_types: tuple[str, ...] = ("calls", "communications"),
    ) -> list[dict[str, Any]]:
        """Enlaces deal ↔ actividad (ambas direcciones)."""
        if not deal_ids:
            return []
        links: list[dict[str, Any]] = []
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id,to_object_type")
                .eq("from_object_type", "deals")
                .in_("from_hubspot_id", chunk)
                .in_("to_object_type", list(activity_types))
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id,from_object_type")
                .eq("to_object_type", "deals")
                .in_("to_hubspot_id", chunk)
                .in_("from_object_type", list(activity_types))
                .eq("is_active", True)
            ) or []
            for row in forward:
                links.append(
                    {
                        "deal_id": str(row["from_hubspot_id"]),
                        "activity_id": str(row["to_hubspot_id"]),
                        "activity_type": str(row["to_object_type"]),
                    }
                )
            for row in backward:
                links.append(
                    {
                        "deal_id": str(row["to_hubspot_id"]),
                        "activity_id": str(row["from_hubspot_id"]),
                        "activity_type": str(row["from_object_type"]),
                    }
                )
        return links

    def fetch_contact_ids_for_deals(self, deal_ids: list[str]) -> set[str]:
        """Contactos vinculados a negocios (asociaciones activas en ambas direcciones)."""
        if not deal_ids:
            return set()
        contacts: set[str] = set()
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("to_hubspot_id")
                .eq("from_object_type", "deals")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id")
                .eq("to_object_type", "deals")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            contacts.update(str(row["to_hubspot_id"]) for row in forward)
            contacts.update(str(row["from_hubspot_id"]) for row in backward)
        return contacts

    def fetch_deal_contact_links(self, deal_ids: list[str]) -> dict[str, list[str]]:
        """Mapa deal_id -> lista de contact_id asociados."""
        if not deal_ids:
            return {}
        links: dict[str, list[str]] = defaultdict(list)
        chunk_size = 100
        for i in range(0, len(deal_ids), chunk_size):
            chunk = deal_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "deals")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "deals")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            for row in forward:
                links[str(row["from_hubspot_id"])].append(str(row["to_hubspot_id"]))
            for row in backward:
                links[str(row["to_hubspot_id"])].append(str(row["from_hubspot_id"]))
        return {k: sorted(set(v)) for k, v in links.items()}

    def fetch_calls_since(self, since_iso: str) -> list[dict[str, Any]]:
        """Llamadas con timestamp >= since_iso (ISO), paginado."""
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        columns = "hubspot_id,properties,activity_timestamp,hubspot_owner_id,created_at_hubspot"
        while True:
            batch = self._execute(
                self._client.table("hubspot_calls")
                .select(columns)
                .gte("activity_timestamp", since_iso)
                .order("hubspot_id")
                .range(offset, offset + page - 1)
            ) or []
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def fetch_deal_links_for_calls(self, call_ids: list[str]) -> dict[str, set[str]]:
        """Mapa call_id -> deal_ids asociados directamente."""
        if not call_ids:
            return {}
        links: dict[str, set[str]] = defaultdict(set)
        chunk_size = 100
        for i in range(0, len(call_ids), chunk_size):
            chunk = call_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "calls")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "deals")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "calls")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "deals")
                .eq("is_active", True)
            ) or []
            for row in forward:
                links[str(row["from_hubspot_id"])].add(str(row["to_hubspot_id"]))
            for row in backward:
                links[str(row["to_hubspot_id"])].add(str(row["from_hubspot_id"]))
        return dict(links)

    def fetch_contact_links_for_calls(self, call_ids: list[str]) -> dict[str, set[str]]:
        """Mapa call_id -> contact_ids asociados."""
        if not call_ids:
            return {}
        links: dict[str, set[str]] = defaultdict(set)
        chunk_size = 100
        for i in range(0, len(call_ids), chunk_size):
            chunk = call_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "calls")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "calls")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "contacts")
                .eq("is_active", True)
            ) or []
            for row in forward:
                links[str(row["from_hubspot_id"])].add(str(row["to_hubspot_id"]))
            for row in backward:
                links[str(row["to_hubspot_id"])].add(str(row["from_hubspot_id"]))
        return dict(links)

    def fetch_call_contact_links(self, contact_ids: list[str]) -> list[dict[str, str]]:
        """Pares contacto↔llamada en lotes (evita N+1 por contacto)."""
        if not contact_ids:
            return []
        links: list[dict[str, str]] = []
        chunk_size = 100
        for i in range(0, len(contact_ids), chunk_size):
            chunk = contact_ids[i : i + chunk_size]
            forward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("from_object_type", "contacts")
                .in_("from_hubspot_id", chunk)
                .eq("to_object_type", "calls")
                .eq("is_active", True)
            ) or []
            backward = self._execute(
                self._client.table("hubspot_associations")
                .select("from_hubspot_id,to_hubspot_id")
                .eq("to_object_type", "contacts")
                .in_("to_hubspot_id", chunk)
                .eq("from_object_type", "calls")
                .eq("is_active", True)
            ) or []
            for row in forward:
                links.append(
                    {"contact_id": str(row["from_hubspot_id"]), "call_id": str(row["to_hubspot_id"])}
                )
            for row in backward:
                links.append(
                    {"contact_id": str(row["to_hubspot_id"]), "call_id": str(row["from_hubspot_id"])}
                )
        return links

    def fetch_call_ids_for_contacts(self, contact_ids: list[str]) -> set[str]:
        """Llamadas vinculadas a contactos (HubSpot suele asociar calls → contacts, no deals)."""
        return {link["call_id"] for link in self.fetch_call_contact_links(contact_ids)}

    def fetch_calls_by_ids(self, call_ids: list[str]) -> list[dict[str, Any]]:
        if not call_ids:
            return []
        rows: list[dict[str, Any]] = []
        chunk_size = 100
        for i in range(0, len(call_ids), chunk_size):
            chunk = call_ids[i : i + chunk_size]
            batch = self._execute(
                self._client.table("hubspot_calls")
                .select("hubspot_id,properties,activity_timestamp,hubspot_owner_id,created_at_hubspot")
                .in_("hubspot_id", chunk)
            ) or []
            rows.extend(batch)
        return rows

    def fetch_communications_by_ids(self, comm_ids: list[str]) -> list[dict[str, Any]]:
        if not comm_ids:
            return []
        rows: list[dict[str, Any]] = []
        chunk_size = 100
        for i in range(0, len(comm_ids), chunk_size):
            chunk = comm_ids[i : i + chunk_size]
            batch = self._execute(
                self._client.table("hubspot_communications")
                .select("hubspot_id,properties,activity_timestamp,hubspot_owner_id,created_at_hubspot")
                .in_("hubspot_id", chunk)
            ) or []
            rows.extend(batch)
        return rows

    def upsert_deal_analytics(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        payload = [to_json_serializable(row) for row in rows]
        self._execute(self._client.table("deal_analytics").upsert(payload, on_conflict="deal_id"))

    def create_run(self) -> dict[str, Any]:
        row = {"status": "started", "started_at": utc_now().isoformat()}
        data = self._execute(self._client.table("deal_analytics_runs").insert(row))
        return data[0] if isinstance(data, list) else data

    def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        self._execute(
            self._client.table("deal_analytics_runs")
            .update(to_json_serializable(updates))
            .eq("id", str(run_id))
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        data = self._execute(
            self._client.table("deal_analytics_runs").select("*").eq("id", str(run_id)).limit(1)
        )
        return data[0] if data else None

    def fetch_analytics_page(self, *, offset: int, limit: int) -> list[dict[str, Any]]:
        return self._execute(
            self._client.table("deal_analytics").select("*").order("deal_id").range(offset, offset + limit - 1)
        ) or []

    def fetch_all_analytics(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        page = 1000
        while True:
            batch = self.fetch_analytics_page(offset=offset, limit=page)
            if not batch:
                break
            rows.extend(batch)
            offset += page
            if len(batch) < page:
                break
        return rows

    def count_analytics(self) -> int:
        result = self._client.table("deal_analytics").select("deal_id", count="exact").limit(0).execute()
        return result.count or 0

    def fetch_owner_analytics(self) -> list[dict[str, Any]]:
        return self._execute(self._client.from_("owner_deal_analytics").select("*")) or []

    def fetch_bucket_config(self) -> dict[str, list[dict[str, Any]]]:
        try:
            rows = self._execute(self._client.table("analytics_bucket_config").select("bucket_type,buckets")) or []
            return {str(r["bucket_type"]): r.get("buckets") or [] for r in rows}
        except Exception:
            return {}

    def get_analytics_by_id(self, deal_id: str) -> dict[str, Any] | None:
        data = self._execute(self._client.table("deal_analytics").select("*").eq("deal_id", deal_id).limit(1))
        return data[0] if data else None
