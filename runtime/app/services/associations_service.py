"""Servicio de lectura y transformación de asociaciones HubSpot."""

import logging
from typing import Any

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import HubSpotClientError, HubSpotPermissionError
from app.constants.associations import (
    ACTIVITY_OBJECT_TYPES,
    ASSOCIATION_PAIRS,
    SYNC_GROUP_PAIRS,
)
from app.repositories.associations_repository import AssociationsRepository
from app.schemas.associations import AssociationLabelSchema, AssociationRecord

logger = logging.getLogger(__name__)


class AssociationLabelCache:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], dict[int, dict[str, Any]]] = {}
        self._permission_errors: list[dict[str, str]] = []

    @property
    def permission_errors(self) -> list[dict[str, str]]:
        return list(self._permission_errors)

    async def load(self, client: HubSpotClient, from_type: str, to_type: str) -> None:
        key = (from_type, to_type)
        if key in self._cache:
            return
        try:
            labels = await client.get_association_labels(from_type, to_type)
            self._cache[key] = {
                int(item["typeId"]): item for item in labels if item.get("typeId") is not None
            }
        except HubSpotPermissionError as exc:
            self._permission_errors.append(
                {"from": from_type, "to": to_type, "error": str(exc)}
            )
            self._cache[key] = {}
        except HubSpotClientError as exc:
            logger.warning("No se pudieron cargar labels %s->%s: %s", from_type, to_type, exc)
            self._cache[key] = {}

    def resolve_label(self, from_type: str, to_type: str, type_id: int | None) -> str | None:
        if type_id is None:
            return None
        item = self._cache.get((from_type, to_type), {}).get(type_id)
        if not item:
            return None
        return item.get("label")


def parse_batch_association_results(
    *,
    from_object_type: str,
    to_object_type: str,
    payload: dict[str, Any],
    label_cache: AssociationLabelCache,
) -> list[AssociationRecord]:
    records: list[AssociationRecord] = []
    for result in payload.get("results", []):
        from_id = str(result.get("from", {}).get("id", ""))
        if not from_id:
            continue
        for to_item in result.get("to", []):
            to_id = str(to_item.get("toObjectId", ""))
            if not to_id:
                continue
            for assoc_type in to_item.get("associationTypes", []):
                type_id = assoc_type.get("typeId")
                category = assoc_type.get("category")
                label = assoc_type.get("label") or label_cache.resolve_label(
                    from_object_type, to_object_type, type_id
                )
                records.append(
                    AssociationRecord(
                        from_object_type=from_object_type,
                        from_hubspot_id=from_id,
                        to_object_type=to_object_type,
                        to_hubspot_id=to_id,
                        association_type_id=type_id,
                        association_category=category,
                        association_label=label,
                    )
                )
    return records


async def get_all_association_labels(client: HubSpotClient) -> list[AssociationLabelSchema]:
    labels: list[AssociationLabelSchema] = []
    seen: set[tuple[str, str]] = set()
    for pair in ASSOCIATION_PAIRS:
        key = (pair["from_type"], pair["to_type"])
        if key in seen:
            continue
        seen.add(key)
        try:
            results = await client.get_association_labels(pair["from_type"], pair["to_type"])
            for item in results:
                labels.append(
                    AssociationLabelSchema(
                        from_object_type=pair["from_type"],
                        to_object_type=pair["to_type"],
                        category=item.get("category"),
                        typeId=item.get("typeId"),
                        label=item.get("label"),
                    )
                )
        except HubSpotPermissionError as exc:
            logger.warning("Sin permiso labels %s->%s: %s", pair["from_type"], pair["to_type"], exc)
        except HubSpotClientError as exc:
            logger.warning("Error labels %s->%s: %s", pair["from_type"], pair["to_type"], exc)
    return labels


async def list_associations_from_db(
    repository: AssociationsRepository,
    *,
    sync_group: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    pairs = SYNC_GROUP_PAIRS.get(sync_group, [])
    if not pairs:
        return [], 0
    from_types = {p["from_type"] for p in pairs}
    to_types = {p["to_type"] for p in pairs}
    all_rows: list[dict[str, Any]] = []
    total = 0
    for from_type in from_types:
        for to_type in to_types:
            if not any(p["from_type"] == from_type and p["to_type"] == to_type for p in pairs):
                continue
            rows, count = repository.list_associations(
                from_object_type=from_type,
                to_object_type=to_type,
                limit=limit,
                offset=offset,
            )
            all_rows.extend(rows)
            total += count
    return all_rows[:limit], total


def activity_types_for_group(sync_group: str) -> tuple[str, ...]:
    if sync_group == "contact-activities":
        return ACTIVITY_OBJECT_TYPES
    if sync_group == "deal-activities":
        return ACTIVITY_OBJECT_TYPES
    return ()
