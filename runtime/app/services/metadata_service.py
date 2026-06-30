"""Servicio de metadatos HubSpot."""

from typing import Any

from app.clients.hubspot import HubSpotClient
from app.clients.hubspot_exceptions import HubSpotNotFoundError, HubSpotRequestError
from app.schemas.common import (
    HubSpotAssociationLabelSchema,
    HubSpotOwnerSchema,
    HubSpotPipelineSchema,
    HubSpotPropertySchema,
)


def _map_property(item: dict[str, Any]) -> HubSpotPropertySchema:
    return HubSpotPropertySchema.model_validate(item)


async def get_contact_properties(client: HubSpotClient) -> list[HubSpotPropertySchema]:
    payload = await client.get("/crm/v3/properties/contacts")
    return [_map_property(item) for item in payload.get("results", [])]


async def get_deal_properties(client: HubSpotClient) -> list[HubSpotPropertySchema]:
    payload = await client.get("/crm/v3/properties/deals")
    return [_map_property(item) for item in payload.get("results", [])]


async def get_owners(client: HubSpotClient) -> list[HubSpotOwnerSchema]:
    payload = await client.get("/crm/v3/owners", params={"limit": 500})
    return [HubSpotOwnerSchema.model_validate(item) for item in payload.get("results", [])]


async def get_deal_pipelines(client: HubSpotClient) -> list[HubSpotPipelineSchema]:
    payload = await client.get("/crm/v3/pipelines/deals")
    return [HubSpotPipelineSchema.model_validate(item) for item in payload.get("results", [])]


async def get_association_labels(client: HubSpotClient) -> list[HubSpotAssociationLabelSchema]:
    labels: list[HubSpotAssociationLabelSchema] = []
    object_types = ["contacts", "deals", "calls", "meetings", "tasks", "emails", "notes", "communications"]
    for from_type in object_types:
        for to_type in object_types:
            if from_type == to_type:
                continue
            try:
                payload = await client.get(f"/crm/v4/associations/{from_type}/{to_type}/labels")
                for item in payload.get("results", []):
                    labels.append(
                        HubSpotAssociationLabelSchema(
                            category=item.get("category"),
                            typeId=item.get("typeId"),
                            label=item.get("label"),
                            from_object_type=from_type,
                            to_object_type=to_type,
                        )
                    )
            except (HubSpotNotFoundError, HubSpotRequestError):
                continue
    return labels
