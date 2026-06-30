"""Servicio de contactos HubSpot."""

from app.clients.hubspot import HubSpotClient
from app.schemas.common import HubSpotObjectResponse, PaginatedResponse
from app.services.hubspot_base import (
    get_object_by_id,
    list_objects_all_properties_batched,
    list_objects_page,
)

DEFAULT_ASSOCIATIONS = ["deals", "calls", "meetings", "tasks", "emails", "communications", "notes"]


async def list_contacts(
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
            object_type="contacts",
            limit=limit,
            after=after,
            associations=associations,
            archived=archived,
        )

    return await list_objects_page(
        client,
        object_type="contacts",
        limit=limit,
        after=after,
        properties=properties,
        properties_with_history=properties_with_history,
        associations=associations,
        archived=archived,
        all_properties=False,
    )


async def get_contact(
    client: HubSpotClient,
    *,
    contact_id: str,
    properties: list[str] | None,
    properties_with_history: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
) -> HubSpotObjectResponse:
    return await get_object_by_id(
        client,
        object_type="contacts",
        object_id=contact_id,
        properties=properties,
        properties_with_history=properties_with_history,
        associations=associations or DEFAULT_ASSOCIATIONS,
        archived=archived,
        all_properties=all_properties,
    )
