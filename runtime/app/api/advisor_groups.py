"""API de grupos de asesores."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.advisor_groups import (
    AdvisorGroupCreateRequest,
    AdvisorGroupSchema,
    AdvisorGroupUpdateRequest,
    GroupsCompareRequest,
    HubSpotListOptionSchema,
    HubSpotTeamOptionSchema,
)
from app.schemas.deal_analytics import DealAnalyticsEnvelope
from app.services.advisor_groups_service import AdvisorGroupsService

router = APIRouter(prefix="/api/v1/advisor-groups", tags=["advisor-groups"])

VALID_BRANDS = frozenset({"voyah", "mhero", "shacman"})


def _validate_brand(brand_value: str | None) -> None:
    if brand_value and brand_value.lower() not in VALID_BRANDS:
        raise HTTPException(status_code=400, detail=f"Marca no válida: {brand_value}")


@router.get("", response_model=list[AdvisorGroupSchema])
async def list_groups() -> list[AdvisorGroupSchema]:
    rows = AdvisorGroupsService().list_groups()
    return [AdvisorGroupSchema.model_validate(row) for row in rows]


@router.get("/hubspot/teams", response_model=list[HubSpotTeamOptionSchema])
async def list_hubspot_teams() -> list[HubSpotTeamOptionSchema]:
    rows = await AdvisorGroupsService().list_hubspot_teams()
    return [HubSpotTeamOptionSchema.model_validate(row) for row in rows]


@router.get("/hubspot/lists", response_model=list[HubSpotListOptionSchema])
async def list_hubspot_lists(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> list[HubSpotListOptionSchema]:
    rows = await AdvisorGroupsService().list_hubspot_lists(client)
    return [HubSpotListOptionSchema.model_validate(row) for row in rows]


@router.post("/compare", response_model=DealAnalyticsEnvelope)
async def compare_groups(body: GroupsCompareRequest) -> DealAnalyticsEnvelope:
    _validate_brand(body.brand_value)
    payload = AdvisorGroupsService().compare_groups(body.brand_value.lower(), body.group_ids)
    return DealAnalyticsEnvelope.model_validate(payload)


@router.get("/{group_id}", response_model=AdvisorGroupSchema)
async def get_group(group_id: str) -> AdvisorGroupSchema:
    row = AdvisorGroupsService().get_group(group_id)
    if not row:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return AdvisorGroupSchema.model_validate(row)


@router.post("", response_model=AdvisorGroupSchema)
async def create_group(body: AdvisorGroupCreateRequest) -> AdvisorGroupSchema:
    _validate_brand(body.brand_value)
    row = AdvisorGroupsService().create_group(body.model_dump())
    return AdvisorGroupSchema.model_validate(row)


@router.patch("/{group_id}", response_model=AdvisorGroupSchema)
async def update_group(group_id: str, body: AdvisorGroupUpdateRequest) -> AdvisorGroupSchema:
    _validate_brand(body.brand_value)
    row = AdvisorGroupsService().update_group(group_id, body.model_dump(exclude_unset=True))
    if not row:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return AdvisorGroupSchema.model_validate(row)


@router.delete("/{group_id}")
async def delete_group(group_id: str) -> dict[str, bool]:
    if not AdvisorGroupsService().get_group(group_id):
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    AdvisorGroupsService().delete_group(group_id)
    return {"deleted": True}


@router.post("/import/hubspot-team", response_model=AdvisorGroupSchema)
async def import_hubspot_team(
    team_id: str = Query(...),
    brand_value: str | None = Query(default=None),
) -> AdvisorGroupSchema:
    _validate_brand(brand_value)
    try:
        row = await AdvisorGroupsService().import_hubspot_team(
            team_id,
            brand_value=brand_value.lower() if brand_value else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdvisorGroupSchema.model_validate(row)


@router.post("/import/hubspot-list", response_model=AdvisorGroupSchema)
async def import_hubspot_list(
    list_id: str = Query(...),
    brand_value: str | None = Query(default=None),
    client: HubSpotClient = Depends(get_hubspot_client),
) -> AdvisorGroupSchema:
    _validate_brand(brand_value)
    try:
        row = await AdvisorGroupsService().import_hubspot_list(
            client,
            list_id,
            brand_value=brand_value.lower() if brand_value else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdvisorGroupSchema.model_validate(row)
