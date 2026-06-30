"""Servicio de actividades HubSpot."""

from app.clients.hubspot import HubSpotClient
from app.schemas.common import HubSpotObjectResponse, PaginatedResponse
from app.services.hubspot_base import (
    get_object_by_id,
    list_objects_all_properties_batched,
    list_objects_page,
)

ACTIVITY_DEFAULT_PROPERTIES: dict[str, list[str]] = {
    "calls": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_call_title",
        "hs_call_status",
        "hs_call_outcome",
        "hs_call_direction",
        "hs_call_duration",
        "hs_call_body",
    ],
    "meetings": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_meeting_title",
        "hs_meeting_start_time",
        "hs_meeting_end_time",
        "hs_meeting_outcome",
        "hs_meeting_body",
    ],
    "tasks": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_task_subject",
        "hs_task_status",
        "hs_task_type",
        "hs_task_priority",
    ],
    "emails": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_email_subject",
        "hs_email_direction",
        "hs_email_status",
        "hs_email_text",
    ],
    "communications": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_communication_channel_type",
        "hs_communication_body",
    ],
    "notes": [
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_note_body",
    ],
}


async def list_activities(
    client: HubSpotClient,
    *,
    activity_type: str,
    limit: int,
    after: str | None,
    properties: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
) -> PaginatedResponse[HubSpotObjectResponse]:
    default_props = ACTIVITY_DEFAULT_PROPERTIES.get(activity_type, [])

    if all_properties:
        return await list_objects_all_properties_batched(
            client,
            object_type=activity_type,
            limit=limit,
            after=after,
            associations=associations,
            archived=archived,
        )

    return await list_objects_page(
        client,
        object_type=activity_type,
        limit=limit,
        after=after,
        properties=properties,
        properties_with_history=None,
        associations=associations,
        archived=archived,
        all_properties=False,
        default_properties=default_props,
    )


async def get_activity(
    client: HubSpotClient,
    *,
    activity_type: str,
    activity_id: str,
    properties: list[str] | None,
    associations: list[str] | None,
    archived: bool,
    all_properties: bool,
) -> HubSpotObjectResponse:
    return await get_object_by_id(
        client,
        object_type=activity_type,
        object_id=activity_id,
        properties=properties,
        properties_with_history=None,
        associations=associations,
        archived=archived,
        all_properties=all_properties,
        default_properties=ACTIVITY_DEFAULT_PROPERTIES.get(activity_type),
    )
