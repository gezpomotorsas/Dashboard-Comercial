"""Endpoints de lectura de asociaciones."""

from fastapi import APIRouter, Depends, Query

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.repositories.associations_repository import AssociationsRepository
from app.schemas.associations import (
    AssociationTypeListResponse,
    build_association_paginated,
)
from app.services.associations_service import get_all_association_labels, list_associations_from_db

router = APIRouter(prefix="/api/v1/hubspot/associations", tags=["hubspot-associations"])


def get_associations_repository() -> AssociationsRepository:
    return AssociationsRepository()


@router.get("/types", response_model=AssociationTypeListResponse)
async def association_types(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> AssociationTypeListResponse:
    labels = await get_all_association_labels(client)
    return AssociationTypeListResponse(data=labels, count=len(labels))


@router.get("/contact-deal")
async def contact_deal_associations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: AssociationsRepository = Depends(get_associations_repository),
):
    rows, total = await list_associations_from_db(repo, sync_group="contact-deal", limit=limit, offset=offset)
    next_after = str(offset + limit) if offset + limit < total else None
    return build_association_paginated(rows, next_after=next_after)


@router.get("/contact-activities")
async def contact_activity_associations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: AssociationsRepository = Depends(get_associations_repository),
):
    rows, _ = await list_associations_from_db(
        repo, sync_group="contact-activities", limit=limit, offset=offset
    )
    return build_association_paginated(rows, next_after=str(offset + limit) if len(rows) == limit else None)


@router.get("/deal-activities")
async def deal_activity_associations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: AssociationsRepository = Depends(get_associations_repository),
):
    rows, _ = await list_associations_from_db(
        repo, sync_group="deal-activities", limit=limit, offset=offset
    )
    return build_association_paginated(rows, next_after=str(offset + limit) if len(rows) == limit else None)
