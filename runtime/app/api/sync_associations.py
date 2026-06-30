"""Endpoints de sincronización de asociaciones."""


from fastapi import APIRouter, Depends, HTTPException, status

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.clients.supabase import SupabaseClientError
from app.schemas.associations import AssociationSyncRequest, AssociationSyncStartResponse
from app.services.associations_sync_service import (
    AssociationsSyncService,
    AssociationSyncAlreadyRunningError,
)

router = APIRouter(prefix="/api/v1/sync/associations", tags=["sync-associations"])


def get_associations_sync_service(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> AssociationsSyncService:
    return AssociationsSyncService(hubspot_client=client)


async def _start(
    sync_group: str,
    body: AssociationSyncRequest,
    service: AssociationsSyncService,
) -> AssociationSyncStartResponse:
    try:
        sync_run = await service.start_sync(
            sync_group=sync_group,
            sync_type=body.sync_type,
            batch_size=body.batch_size,
            object_offset=body.object_offset,
            object_limit=body.object_limit,
        )
    except AssociationSyncAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SupabaseClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return AssociationSyncStartResponse(
        sync_id=str(sync_run["id"]),
        status="started",
        message="Sincronización de asociaciones iniciada",
    )


@router.post("/contact-deal", response_model=AssociationSyncStartResponse)
async def sync_contact_deal(
    body: AssociationSyncRequest,
    service: AssociationsSyncService = Depends(get_associations_sync_service),
) -> AssociationSyncStartResponse:
    return await _start("contact-deal", body, service)


@router.post("/contact-activities", response_model=AssociationSyncStartResponse)
async def sync_contact_activities(
    body: AssociationSyncRequest,
    service: AssociationsSyncService = Depends(get_associations_sync_service),
) -> AssociationSyncStartResponse:
    return await _start("contact-activities", body, service)


@router.post("/deal-activities", response_model=AssociationSyncStartResponse)
async def sync_deal_activities(
    body: AssociationSyncRequest,
    service: AssociationsSyncService = Depends(get_associations_sync_service),
) -> AssociationSyncStartResponse:
    return await _start("deal-activities", body, service)


@router.post("/all", response_model=AssociationSyncStartResponse)
async def sync_all_associations(
    body: AssociationSyncRequest,
    service: AssociationsSyncService = Depends(get_associations_sync_service),
) -> AssociationSyncStartResponse:
    return await _start("all", body, service)
