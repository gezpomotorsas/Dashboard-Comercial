"""Endpoints de calidad de datos."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.data_quality import (
    DataQualityResultListResponse,
    DataQualityResultSchema,
    DataQualityRunListResponse,
    DataQualityRunRequest,
    DataQualityRunSchema,
    DataQualityRunStartResponse,
    DataQualitySummary,
)
from app.services.data_quality.engine import DataQualityAlreadyRunningError, DataQualityEngine

router = APIRouter(prefix="/api/v1/data-quality", tags=["data-quality"])


def get_quality_engine() -> DataQualityEngine:
    return DataQualityEngine()


@router.post("/run", response_model=DataQualityRunStartResponse)
async def run_quality_analysis(
    body: DataQualityRunRequest,
    engine: DataQualityEngine = Depends(get_quality_engine),
) -> DataQualityRunStartResponse:
    try:
        run = await engine.start_run(scope=body.scope)
    except DataQualityAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return DataQualityRunStartResponse(run_id=run["id"], status="started")


@router.get("/runs", response_model=DataQualityRunListResponse)
async def list_runs(
    engine: DataQualityEngine = Depends(get_quality_engine),
) -> DataQualityRunListResponse:
    runs = engine.list_runs()
    return DataQualityRunListResponse(
        data=[DataQualityRunSchema.model_validate(r) for r in runs],
        count=len(runs),
    )


@router.get("/runs/{run_id}", response_model=DataQualityRunSchema)
async def get_run(
    run_id: UUID,
    engine: DataQualityEngine = Depends(get_quality_engine),
) -> DataQualityRunSchema:
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run no encontrado")
    return DataQualityRunSchema.model_validate(run)


@router.get("/results", response_model=DataQualityResultListResponse)
async def list_results(
    rule_code: str | None = None,
    object_type: str | None = None,
    severity: str | None = None,
    is_resolved: bool | None = False,
    hubspot_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    engine: DataQualityEngine = Depends(get_quality_engine),
) -> DataQualityResultListResponse:
    rows, count = engine.list_results(
        rule_code=rule_code,
        object_type=object_type,
        severity=severity,
        is_resolved=is_resolved,
        hubspot_id=hubspot_id,
        limit=limit,
        offset=offset,
    )
    return DataQualityResultListResponse(
        data=[DataQualityResultSchema.model_validate(r) for r in rows],
        count=count,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=DataQualitySummary)
async def quality_summary(
    engine: DataQualityEngine = Depends(get_quality_engine),
) -> DataQualitySummary:
    return DataQualitySummary.model_validate(engine.get_summary())
