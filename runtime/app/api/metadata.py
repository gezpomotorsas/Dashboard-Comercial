"""Endpoints de metadatos HubSpot."""

from fastapi import APIRouter, Depends

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.common import (
    HubSpotAssociationLabelSchema,
    HubSpotOwnerSchema,
    HubSpotPipelineSchema,
    HubSpotPropertySchema,
)
from app.schemas.hubspot_configuration import MetadataRefreshResponse
from app.services import metadata_service
from app.services.hubspot_configuration.refresh import HubSpotMetadataRefreshService

router = APIRouter(prefix="/api/v1/hubspot/metadata", tags=["hubspot-metadata"])


@router.get("/contact-properties", response_model=list[HubSpotPropertySchema])
async def contact_properties(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotPropertySchema]:
    return await metadata_service.get_contact_properties(client)


@router.get("/deal-properties", response_model=list[HubSpotPropertySchema])
async def deal_properties(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotPropertySchema]:
    return await metadata_service.get_deal_properties(client)


@router.get("/owners", response_model=list[HubSpotOwnerSchema])
async def owners(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotOwnerSchema]:
    return await metadata_service.get_owners(client)


@router.get("/deal-pipelines", response_model=list[HubSpotPipelineSchema])
async def deal_pipelines(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotPipelineSchema]:
    return await metadata_service.get_deal_pipelines(client)


@router.get("/association-labels", response_model=list[HubSpotAssociationLabelSchema])
async def association_labels(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotAssociationLabelSchema]:
    return await metadata_service.get_association_labels(client)


@router.post("/refresh", response_model=MetadataRefreshResponse)
async def refresh_hubspot_metadata(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> MetadataRefreshResponse:
    result = await HubSpotMetadataRefreshService(hubspot_client=client).refresh_hubspot_metadata()
    return MetadataRefreshResponse(
        id=str(result["id"]),
        status=result["status"],
        finished_at=result.get("finished_at"),
        properties_synced=int(result.get("properties_synced") or 0),
        pipelines_synced=int(result.get("pipelines_synced") or 0),
        stages_synced=int(result.get("stages_synced") or 0),
        owners_synced=int(result.get("owners_synced") or 0),
        association_types_synced=int(result.get("association_types_synced") or 0),
        mappings_validated=int(result.get("mappings_validated") or 0),
        mappings_invalidated=int(result.get("mappings_invalidated") or 0),
        field_mapping_version=int(result.get("field_mapping_version") or 1),
        dimension_mapping_version=int(result.get("dimension_mapping_version") or 1),
    )
