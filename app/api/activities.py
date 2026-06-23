"""Endpoints de actividades HubSpot."""

from fastapi import APIRouter, Depends, Query

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.common import HubSpotObjectResponse, PaginatedResponse
from app.services import activities_service
from app.utils.privacy import redact_hubspot_object

router = APIRouter(prefix="/api/v1/hubspot/activities", tags=["hubspot-activities"])


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_privacy(
    response: PaginatedResponse[HubSpotObjectResponse],
    *,
    include_content: bool,
) -> PaginatedResponse[HubSpotObjectResponse]:
    if include_content:
        return response
    redacted = []
    for item in response.data:
        raw = item.model_dump(by_alias=True)
        safe = redact_hubspot_object(raw)
        redacted.append(HubSpotObjectResponse.model_validate(safe))
    return PaginatedResponse(
        data=redacted,
        pagination=response.pagination,
        meta=response.meta,
    )


async def _list_activity(
    activity_type: str,
    *,
    limit: int,
    after: str | None,
    properties: str | None,
    associations: str | None,
    archived: bool,
    all_properties: bool,
    include_content: bool,
    client: HubSpotClient,
) -> PaginatedResponse[HubSpotObjectResponse]:
    result = await activities_service.list_activities(
        client,
        activity_type=activity_type,
        limit=limit,
        after=after,
        properties=_split_csv(properties),
        associations=_split_csv(associations),
        archived=archived,
        all_properties=all_properties,
    )
    return _apply_privacy(result, include_content=include_content)


@router.get("/calls", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_calls(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(
        default=False,
        description="Si es true, incluye cuerpos de llamadas/notas (datos sensibles)",
    ),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "calls",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )


@router.get("/meetings", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_meetings(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(default=False),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "meetings",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )


@router.get("/tasks", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_tasks(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(default=False),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "tasks",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )


@router.get("/emails", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_emails(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(default=False),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "emails",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )


@router.get("/communications", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_communications(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(default=False),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "communications",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )


@router.get("/notes", response_model=PaginatedResponse[HubSpotObjectResponse])
async def list_notes(
    limit: int = Query(default=10, ge=1, le=100),
    after: str | None = None,
    properties: str | None = None,
    associations: str | None = None,
    archived: bool = False,
    all_properties: bool = False,
    include_content: bool = Query(default=False),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> PaginatedResponse[HubSpotObjectResponse]:
    return await _list_activity(
        "notes",
        limit=limit,
        after=after,
        properties=properties,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        include_content=include_content,
        client=client,
    )
