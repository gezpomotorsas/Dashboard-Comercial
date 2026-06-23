"""Endpoints de sincronización."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.clients.hubspot import HubSpotClient, get_hubspot_client
from app.schemas.sync import SyncRequest, SyncRunListResponse, SyncRunSchema, SyncStartResponse
from app.services.sync_service import SyncAlreadyRunningError, SyncService

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


def get_sync_service(
    client: HubSpotClient = Depends(get_hubspot_client),
) -> SyncService:
    return SyncService(hubspot_client=client)


async def _start_sync(
    object_type: str,
    body: SyncRequest,
    service: SyncService,
) -> SyncStartResponse:
    try:
        sync_run = await service.start_sync(
            object_type=object_type,
            sync_type=body.sync_type,
            batch_size=body.batch_size,
            lookback_days=body.lookback_days,
        )
    except SyncAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return SyncStartResponse(
        sync_id=sync_run["id"],
        status="started",
        message="Sincronización iniciada",
    )


@router.post("/metadata", response_model=SyncStartResponse)
async def sync_metadata(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("metadata", body, service)


@router.post("/contacts", response_model=SyncStartResponse)
async def sync_contacts(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("contacts", body, service)


@router.post("/deals", response_model=SyncStartResponse)
async def sync_deals(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("deals", body, service)


@router.post("/calls", response_model=SyncStartResponse)
async def sync_calls(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("calls", body, service)


@router.post("/meetings", response_model=SyncStartResponse)
async def sync_meetings(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("meetings", body, service)


@router.post("/tasks", response_model=SyncStartResponse)
async def sync_tasks(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("tasks", body, service)


@router.post("/emails", response_model=SyncStartResponse)
async def sync_emails(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("emails", body, service)


@router.post("/communications", response_model=SyncStartResponse)
async def sync_communications(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("communications", body, service)


@router.post("/notes", response_model=SyncStartResponse)
async def sync_notes(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("notes", body, service)


@router.post("/all", response_model=SyncStartResponse)
async def sync_all(
    body: SyncRequest,
    service: SyncService = Depends(get_sync_service),
) -> SyncStartResponse:
    return await _start_sync("all", body, service)


@router.get("/runs", response_model=SyncRunListResponse)
async def list_sync_runs(
    service: SyncService = Depends(get_sync_service),
) -> SyncRunListResponse:
    runs = service.list_sync_runs()
    return SyncRunListResponse(
        data=[SyncRunSchema.model_validate(run) for run in runs],
        count=len(runs),
    )


@router.get("/runs/{sync_id}", response_model=SyncRunSchema)
async def get_sync_run(
    sync_id: UUID,
    service: SyncService = Depends(get_sync_service),
) -> SyncRunSchema:
    run = service.get_sync_run(sync_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run no encontrado")
    return SyncRunSchema.model_validate(run)
