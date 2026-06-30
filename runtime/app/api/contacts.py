"""Endpoints de contactos HubSpot."""

from fastapi import APIRouter, Depends, Query

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.common import HubSpotObjectResponse, PaginatedResponse
from app.services import contacts_service

router = APIRouter(prefix="/api/v1/hubspot/contacts", tags=["hubspot-contacts"])


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_contacts(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    properties_with_history: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await contacts_service.list_contacts(
        client,
        limit=limit,
        after=after,
        properties=_split_csv(properties),
        properties_with_history=_split_csv(properties_with_history),
        associations=_split_csv(associations),
        archived=archived,
        all_properties=all_properties,
    )


@router.get("/{contact_id}", response_model=HubSpotObjectResponse)
async def get_contact(
    contact_id: str,
    properties: str | None = None,
    properties_with_history: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    client: HubSpotClient = Depends(get_hubspot_client),
) -> HubSpotObjectResponse:
    return await contacts_service.get_contact(
        client,
        contact_id=contact_id,
        properties=_split_csv(properties),
        properties_with_history=_split_csv(properties_with_history),
        associations=_split_csv(associations),
        archived=archived,
        all_properties=all_properties,
    )
