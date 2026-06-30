"""Servicio de grupos de asesores e importación HubSpot."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import HubSpotClientError
from app.repositories.advisor_groups_repository import AdvisorGroupsRepository
from app.services.deal_analytics.query import DealAnalyticsQueryService

logger = logging.getLogger(__name__)


class AdvisorGroupsService:
    def __init__(
        self,
        repository: AdvisorGroupsRepository | None = None,
        query_service: DealAnalyticsQueryService | None = None,
    ) -> None:
        self._repo = repository or AdvisorGroupsRepository()
        self._query = query_service or DealAnalyticsQueryService()

    def list_groups(self) -> list[dict[str, Any]]:
        return self._repo.list_groups()

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        return self._repo.get_group(group_id)

    def create_group(self, payload: dict[str, Any]) -> dict[str, Any]:
        members = payload.pop("members", [])
        return self._repo.create_group(payload, members)

    def update_group(self, group_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        members = payload.pop("members", None)
        return self._repo.update_group(group_id, payload, members)

    def delete_group(self, group_id: str) -> bool:
        return self._repo.delete_group(group_id)

    def compare_groups(self, brand_value: str, group_ids: list[str]) -> dict[str, Any]:
        groups = self._repo.get_groups_by_ids(group_ids)
        if not groups:
            return {"brand_value": brand_value, "groups": []}
        return self._query.groups_compare(brand_value, groups)

    async def list_hubspot_teams(self) -> list[dict[str, Any]]:
        owners = self._repo.list_owners_from_db()
        teams: dict[str, dict[str, Any]] = {}
        for owner in owners:
            owner_id = str(owner.get("hubspot_id") or "")
            if not owner_id:
                continue
            owner_name = _owner_display_name(owner)
            for team in owner.get("teams") or []:
                if not isinstance(team, dict):
                    continue
                team_id = str(team.get("id") or team.get("name") or "")
                team_name = str(team.get("name") or team_id)
                if not team_id:
                    continue
                item = teams.setdefault(
                    team_id,
                    {
                        "team_id": team_id,
                        "team_name": team_name,
                        "owner_ids": [],
                        "owner_names": {},
                    },
                )
                if owner_id not in item["owner_ids"]:
                    item["owner_ids"].append(owner_id)
                    item["owner_names"][owner_id] = owner_name
        result = []
        for item in teams.values():
            result.append(
                {
                    "team_id": item["team_id"],
                    "team_name": item["team_name"],
                    "member_count": len(item["owner_ids"]),
                    "owner_ids": item["owner_ids"],
                }
            )
        result.sort(key=lambda x: (-x["member_count"], x["team_name"].lower()))
        return result

    async def import_hubspot_team(self, team_id: str, *, brand_value: str | None = None) -> dict[str, Any]:
        teams = await self.list_hubspot_teams()
        match = next((t for t in teams if t["team_id"] == team_id), None)
        if not match:
            raise ValueError(f"Team HubSpot {team_id} no encontrado")
        members = [
            {"owner_id": oid, "owner_name": None}
            for oid in match["owner_ids"]
        ]
        existing = self._find_by_hubspot_source("hubspot_team", team_id)
        payload = {
            "name": match["team_name"],
            "description": "Importado desde team HubSpot",
            "brand_value": brand_value,
            "source": "hubspot_team",
            "hubspot_source_id": team_id,
            "hubspot_source_label": match["team_name"],
            "members": members,
        }
        if existing:
            return self._repo.update_group(
                str(existing["id"]),
                {k: payload[k] for k in ("name", "description", "brand_value", "hubspot_source_label")},
                members,
            ) or existing
        return self._repo.create_group(payload, members)

    async def list_hubspot_lists(self, client: HubSpotClient) -> list[dict[str, Any]]:
        try:
            payload = await client.paginate("/crm/v3/lists", params={"limit": 100})
        except HubSpotClientError as exc:
            logger.warning("No se pudieron listar segmentos HubSpot: %s", exc)
            return []
        rows = []
        for item in payload:
            list_id = str(item.get("listId") or item.get("id") or "")
            if not list_id:
                continue
            rows.append(
                {
                    "list_id": list_id,
                    "name": item.get("name") or list_id,
                    "object_type_id": item.get("objectTypeId"),
                    "processing_type": item.get("processingType"),
                    "size": item.get("additionalProperties", {}).get("hs_list_size")
                    if isinstance(item.get("additionalProperties"), dict)
                    else item.get("listSize"),
                }
            )
        rows.sort(key=lambda x: x["name"].lower())
        return rows

    async def import_hubspot_list(
        self,
        client: HubSpotClient,
        list_id: str,
        *,
        brand_value: str | None = None,
    ) -> dict[str, Any]:
        lists = await self.list_hubspot_lists(client)
        match = next((row for row in lists if row["list_id"] == list_id), None)
        if not match:
            raise ValueError(f"Lista HubSpot {list_id} no encontrada")

        owner_ids = await self._resolve_list_owner_ids(client, list_id)
        if not owner_ids:
            raise ValueError(
                "La lista no tiene miembros mapeables a asesores HubSpot. "
                "Use un team HubSpot o cree el grupo manualmente."
            )
        members = [{"owner_id": oid, "owner_name": None} for oid in sorted(owner_ids)]
        existing = self._find_by_hubspot_source("hubspot_list", list_id)
        payload = {
            "name": match["name"],
            "description": "Importado desde lista/segmento HubSpot",
            "brand_value": brand_value,
            "source": "hubspot_list",
            "hubspot_source_id": list_id,
            "hubspot_source_label": match["name"],
            "members": members,
        }
        if existing:
            return self._repo.update_group(
                str(existing["id"]),
                {k: payload[k] for k in ("name", "description", "brand_value", "hubspot_source_label")},
                members,
            ) or existing
        return self._repo.create_group(payload, members)

    async def _resolve_list_owner_ids(self, client: HubSpotClient, list_id: str) -> set[str]:
        owner_ids: set[str] = set()
        after: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 100}
            if after:
                params["after"] = after
            try:
                payload = await client.get(f"/crm/v3/lists/{list_id}/memberships", params=params)
            except HubSpotClientError:
                break
            for item in payload.get("results", []):
                record_id = str(item.get("recordId") or item.get("id") or "")
                if not record_id:
                    continue
                owner_ids.add(record_id)
            paging = payload.get("paging") or {}
            after = (paging.get("next") or {}).get("after")
            if not after:
                break

        owners_in_db = {str(o["hubspot_id"]) for o in self._repo.list_owners_from_db()}
        return owner_ids & owners_in_db

    def _find_by_hubspot_source(self, source: str, source_id: str) -> dict[str, Any] | None:
        rows = self._repo.list_groups()
        for row in rows:
            if row.get("source") == source and str(row.get("hubspot_source_id") or "") == source_id:
                return row
        return None


def _owner_display_name(owner: dict[str, Any]) -> str:
    first = (owner.get("first_name") or "").strip()
    last = (owner.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    return name or owner.get("email") or str(owner.get("hubspot_id") or "")
