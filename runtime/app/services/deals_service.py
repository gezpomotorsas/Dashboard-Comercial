"""Servicio de negocios HubSpot."""

from app.clients.hubspot import HubSpotClient
from app.schemas.common import HubSpotObjectResponse, PaginatedResponse
from app.services.hubspot_base import (
    get_object_by_id,
    list_objects_all_properties_batched,
    list_objects_page,
)


async def list_deals(
    client: HubSpotClient,
    *,
    limit: int,
    after: str | None,
    properties: list[str] | None,
    properties_with_history: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
) -> PaginatedResponse[HubSpotObjectResponse]:
    if all_properties:
        return await list_objects_all_properties_batched(
            client,
            object_type="deals",
            limit=limit,
            after=after,
            associations=associations,
            archived=archived,
            include_brand=True,
        )

    return await list_objects_page(
        client,
        object_type="deals",
        limit=limit,
        after=after,
        properties=properties,
        properties_with_history=properties_with_history,
        associations=associations,
        archived=archived,
        all_properties=False,
        include_brand=True,
    )


async def get_deal(
    client: HubSpotClient,
    *,
    deal_id: str,
    properties: list[str] | None,
    properties_with_history: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
) -> HubSpotObjectResponse:
    return await get_object_by_id(
        client,
        object_type="deals",
        object_id=deal_id,
        properties=properties,
        properties_with_history=properties_with_history,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_brand=True,
    )
