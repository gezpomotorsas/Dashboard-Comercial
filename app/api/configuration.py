"""Endpoints de configuración HubSpot."""

from fastapi import APIRouter, Depends

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.hubspot_configuration import HubSpotMappingIssue, HubSpotMappingsReport, MetadataRefreshResponse
from app.services.hubspot_configuration.diagnostics import get_configuration_issues, get_configuration_report
from app.services.hubspot_configuration.refresh import HubSpotMetadataRefreshService

router = APIRouter(prefix="/api/v1/configuration", tags=["configuration"])


@router.get("/hubspot-mappings", response_model=HubSpotMappingsReport)
async def hubspot_mappings() -> HubSpotMappingsReport:
    return HubSpotMappingsReport.model_validate(get_configuration_report())


@router.get("/hubspot-mappings/issues", response_model=list[HubSpotMappingIssue])
async def hubspot_mapping_issues() -> list[HubSpotMappingIssue]:
    return [HubSpotMappingIssue.model_validate(item) for item in get_configuration_issues()]
