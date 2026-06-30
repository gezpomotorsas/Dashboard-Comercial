"""Lógica compartida para servicios HubSpot."""

from typing import Any

from app.clients.hubspot import HubSpotClient
from app.config import DEFAULT_PROPERTY_BATCH_SIZE
from app.schemas.common import (
    HubSpotObjectResponse,
    PaginatedResponse,
    PaginationMeta,
    ResponseMeta,
)
from app.services.hubspot_configuration import get_hubspot_config
from app.utils.serialization import chunk_list


def resolve_brand(pipeline_id: str | None) -> str | None:
    if pipeline_id is None:
        return None
    return get_hubspot_config()._resolve_dimension("brand", "pipeline_id", str(pipeline_id))


def build_paginated_response(
    *,
    items: list[Any],
    object_type: str,
    paging: dict[str, Any] | None,
) -> PaginatedResponse[Any]:
    next_after = None
    has_more = False
    if paging:
        next_page = paging.get("next") or {}
        next_after = next_page.get("after")
        has_more = bool(next_after)

    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(next_after=next_after, has_more=has_more),
        meta=ResponseMeta(count=len(items), object_type=object_type),
    )


def map_hubspot_object(
    record: dict[str, Any],
    *,
    include_brand: bool = False,
) -> HubSpotObjectResponse:
    properties = record.get("properties") or {}
    brand = None
    if include_brand:
        brand, _ = get_hubspot_config().resolve_deal_brand({"properties": properties})
        if brand == "unknown":
            brand = None

    return HubSpotObjectResponse(
        id=str(record.get("id")),
        properties=properties,
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
        archived=bool(record.get("archived", False)),
        associations=record.get("associations"),
        brand=brand,
    )


async def fetch_property_names(client: HubSpotClient, object_type: str) -> list[str]:
    payload = await client.get(f"/crm/v3/properties/{object_type}")
    results = payload.get("results", [])
    return [item["name"] for item in results if item.get("name")]


async def list_objects_page(
    client: HubSpotClient,
    *,
    object_type: str,
    limit: int,
    after: str | None,
    properties: list[str] | None,
    properties_with_history: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
    default_properties: list[str] | None = None,
    include_brand: bool = False,
) -> PaginatedResponse[HubSpotObjectResponse]:
    params: dict[str, Any] = {"limit": limit, "archived": str(archived).lower()}

    if after:
        params["after"] = after

    if associations:
        params["associations"] = ",".join(associations)

    property_names = properties
    if all_properties:
        property_names = await fetch_property_names(client, object_type)
    elif not property_names and default_properties:
        property_names = default_properties

    if properties_with_history:
        params["propertiesWithHistory"] = ",".join(properties_with_history)

    if property_names:
        params["properties"] = ",".join(property_names)

    payload = await client.get(f"/crm/v3/objects/{object_type}", params=params)
    items = [map_hubspot_object(item, include_brand=include_brand) for item in payload.get("results", [])]
    return build_paginated_response(
        items=items,
        object_type=object_type,
        paging=payload.get("paging"),
    )


async def list_objects_all_properties_batched(
    client: HubSpotClient,
    *,
    object_type: str,
    limit: int,
    after: str | None,
    associations: list[str] | None,
    archived: bool,
    include_brand: bool = False,
    batch_size: int = DEFAULT_PROPERTY_BATCH_SIZE,
) -> PaginatedResponse[HubSpotObjectResponse]:
    property_names = await fetch_property_names(client, object_type)
    if not property_names:
        return await list_objects_page(
            client,
            object_type=object_type,
            limit=limit,
            after=after,
            properties=None,
            properties_with_history=None,
            associations=associations,
            archived=archived,
            all_properties=False,
            include_brand=include_brand,
        )

    batches = chunk_list(property_names, batch_size)
    merged: dict[str, HubSpotObjectResponse] = {}
    paging: dict[str, Any] | None = None

    for index, batch in enumerate(batches):
        page = await list_objects_page(
            client,
            object_type=object_type,
            limit=limit,
            after=after if index == 0 else None,
            properties=batch,
            properties_with_history=None,
            associations=associations if index == 0 else None,
            archived=archived,
            all_properties=False,
            include_brand=include_brand,
        )
        if index == 0:
            paging = page.pagination.model_dump()
        for item in page.data:
            existing = merged.get(item.id)
            if existing is None:
                merged[item.id] = item
            else:
                existing.properties.update(item.properties)

    items = list(merged.values())
    return build_paginated_response(
        items=items,
        object_type=object_type,
        paging={"next": {"after": paging.get("next_after")}} if paging and paging.get("next_after") else None,
    )


async def get_object_by_id(
    client: HubSpotClient,
    *,
    object_type: str,
    object_id: str,
    properties: list[str] | None,
    properties_with_history: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
    default_properties: list[str] | None = None,
    include_brand: bool = False,
) -> HubSpotObjectResponse:
    params: dict[str, Any] = {"archived": str(archived).lower()}

    if associations:
        params["associations"] = ",".join(associations)

    property_names = properties
    if all_properties:
        property_names = await fetch_property_names(client, object_type)
    elif not property_names and default_properties:
        property_names = default_properties

    if properties_with_history:
        params["propertiesWithHistory"] = ",".join(properties_with_history)

    if property_names and len(property_names) <= DEFAULT_PROPERTY_BATCH_SIZE:
        params["properties"] = ",".join(property_names)
        payload = await client.get(f"/crm/v3/objects/{object_type}/{object_id}", params=params)
        return map_hubspot_object(payload, include_brand=include_brand)

    if property_names and len(property_names) > DEFAULT_PROPERTY_BATCH_SIZE:
        merged_record: dict[str, Any] | None = None
        for batch in chunk_list(property_names, DEFAULT_PROPERTY_BATCH_SIZE):
            params["properties"] = ",".join(batch)
            payload = await client.get(f"/crm/v3/objects/{object_type}/{object_id}", params=params)
            if merged_record is None:
                merged_record = payload
            else:
                merged_record.setdefault("properties", {}).update(payload.get("properties", {}))
        return map_hubspot_object(merged_record or {}, include_brand=include_brand)

    payload = await client.get(f"/crm/v3/objects/{object_type}/{object_id}", params=params)
    return map_hubspot_object(payload, include_brand=include_brand)
