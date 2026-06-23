"""Persistencia de grupos de asesores en Supabase."""

from __future__ import annotations

from typing import Any

from app.clients.supabase import get_supabase_client
from app.utils.dates import utc_now
from app.utils.serialization import to_json_serializable


class AdvisorGroupsRepository:
    def __init__(self) -> None:
        self._client = get_supabase_client()

    def _execute(self, operation: Any) -> Any:
        response = operation.execute()
        return response.data if hasattr(response, "data") else response

    def list_groups(self) -> list[dict[str, Any]]:
        rows = (
            self._execute(
                self._client.table("advisor_groups")
                .select("*")
                .order("name")
            )
            or []
        )
        return [self._attach_members(row) for row in rows]

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        rows = (
            self._execute(
                self._client.table("advisor_groups").select("*").eq("id", group_id).limit(1)
            )
            or []
        )
        if not rows:
            return None
        return self._attach_members(rows[0])

    def create_group(self, payload: dict[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
        now = utc_now().isoformat()
        row = {
            "name": payload["name"],
            "description": payload.get("description"),
            "brand_value": payload.get("brand_value"),
            "source": payload.get("source") or "manual",
            "hubspot_source_id": payload.get("hubspot_source_id"),
            "hubspot_source_label": payload.get("hubspot_source_label"),
            "created_at": now,
            "updated_at": now,
        }
        inserted = self._execute(self._client.table("advisor_groups").insert(row))
        group = inserted[0] if isinstance(inserted, list) else inserted
        group_id = str(group["id"])
        self._replace_members(group_id, members)
        return self.get_group(group_id) or group

    def update_group(
        self,
        group_id: str,
        payload: dict[str, Any],
        members: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        updates = {k: v for k, v in payload.items() if v is not None}
        if updates:
            updates["updated_at"] = utc_now().isoformat()
            self._execute(self._client.table("advisor_groups").update(updates).eq("id", group_id))
        if members is not None:
            self._replace_members(group_id, members)
        return self.get_group(group_id)

    def delete_group(self, group_id: str) -> bool:
        self._execute(self._client.table("advisor_groups").delete().eq("id", group_id))
        return True

    def get_groups_by_ids(self, group_ids: list[str]) -> list[dict[str, Any]]:
        if not group_ids:
            return []
        rows = (
            self._execute(
                self._client.table("advisor_groups").select("*").in_("id", group_ids)
            )
            or []
        )
        return [self._attach_members(row) for row in rows]

    def list_owners_from_db(self) -> list[dict[str, Any]]:
        return (
            self._execute(
                self._client.table("hubspot_owners")
                .select("hubspot_id,email,first_name,last_name,teams,archived")
                .eq("archived", False)
                .order("first_name")
            )
            or []
        )

    def _replace_members(self, group_id: str, members: list[dict[str, Any]]) -> None:
        self._execute(self._client.table("advisor_group_members").delete().eq("group_id", group_id))
        if not members:
            return
        rows = [
            to_json_serializable(
                {
                    "group_id": group_id,
                    "owner_id": str(m["owner_id"]),
                    "owner_name": m.get("owner_name"),
                }
            )
            for m in members
            if m.get("owner_id")
        ]
        if rows:
            self._execute(self._client.table("advisor_group_members").insert(rows))

    def _attach_members(self, group: dict[str, Any]) -> dict[str, Any]:
        group_id = str(group["id"])
        members = (
            self._execute(
                self._client.table("advisor_group_members")
                .select("owner_id,owner_name")
                .eq("group_id", group_id)
                .order("owner_name")
            )
            or []
        )
        group = dict(group)
        group["members"] = members
        group["member_count"] = len(members)
        return group
