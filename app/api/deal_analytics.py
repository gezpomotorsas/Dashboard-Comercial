"""Endpoints de analítica centrada en negocios."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.advisor_benchmark import AdvisorBenchmarkResponse
from app.schemas.deal_analytics import (
    DealAnalyticsEnvelope,
    DealAnalyticsRefreshResponse,
    DealAnalyticsRunStatus,
)
from app.services.deal_analytics.advisor_benchmark_query import AdvisorBrandBenchmarkService
from app.services.deal_analytics.filters import DealAnalyticsFilters
from app.services.deal_analytics.query import DealAnalyticsQueryService
from app.services.deal_analytics.refresh import (
    DealAnalyticsRefreshAlreadyRunningError,
    DealAnalyticsRefreshService,
)

router = APIRouter(prefix="/api/v1/deal-analytics", tags=["deal-analytics"])


def _filters_from_query(
  pipeline_id: str | None = None,
  stage_id: str | None = None,
  owner_id: str | None = None,
  status: str | None = None,
  brand_value: str | None = None,
  zone_value: str | None = None,
  model_value: str | None = None,
  source_value: str | None = None,
  age_bucket: str | None = None,
  stage_age_bucket: str | None = None,
  inactivity_bucket: str | None = None,
  activity_count_bucket: str | None = None,
  effective_contact_count_bucket: str | None = None,
  amount_min: float | None = None,
  amount_max: float | None = None,
  has_contact: bool | None = None,
  has_owner: bool | None = None,
  has_amount: bool | None = None,
  has_activity: bool | None = None,
  has_effective_contact: bool | None = None,
  is_stale: bool | None = None,
  is_unattended: bool | None = None,
  has_overdue_tasks: bool | None = None,
  is_unknown_pipeline: bool | None = None,
  limit: int = Query(default=100, ge=1, le=1000),
  offset: int = Query(default=0, ge=0),
  sort_by: str = "deal_id",
  sort_dir: str = "asc",
) -> DealAnalyticsFilters:
    return DealAnalyticsFilters(
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        owner_id=owner_id,
        status=status,
        brand_value=brand_value,
        zone_value=zone_value,
        model_value=model_value,
        source_value=source_value,
        age_bucket=age_bucket,
        stage_age_bucket=stage_age_bucket,
        inactivity_bucket=inactivity_bucket,
        activity_count_bucket=activity_count_bucket,
        effective_contact_count_bucket=effective_contact_count_bucket,
        amount_min=amount_min,
        amount_max=amount_max,
        has_contact=has_contact,
        has_owner=has_owner,
        has_amount=has_amount,
        has_activity=has_activity,
        has_effective_contact=has_effective_contact,
        is_stale=is_stale,
        is_unattended=is_unattended,
        has_overdue_tasks=has_overdue_tasks,
        is_unknown_pipeline=is_unknown_pipeline,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.post("/refresh", response_model=DealAnalyticsRefreshResponse)
async def refresh_deal_analytics() -> DealAnalyticsRefreshResponse:
    service = DealAnalyticsRefreshService()
    try:
        result = await service.start_refresh()
    except DealAnalyticsRefreshAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DealAnalyticsRefreshResponse(**result)


@router.get("/refresh/{run_id}", response_model=DealAnalyticsRunStatus)
async def get_refresh_status(run_id: str) -> DealAnalyticsRunStatus:
    run = DealAnalyticsRefreshService().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return DealAnalyticsRunStatus(
        id=str(run["id"]),
        status=run["status"],
        started_at=run.get("started_at"),
        finished_at=run.get("finished_at"),
        deals_processed=int(run.get("deals_processed") or 0),
        deals_inserted=int(run.get("deals_inserted") or 0),
        deals_updated=int(run.get("deals_updated") or 0),
        deals_failed=int(run.get("deals_failed") or 0),
        metadata_version=run.get("metadata_version"),
        field_mapping_version=run.get("field_mapping_version"),
        dimension_mapping_version=run.get("dimension_mapping_version"),
        duration_seconds=float(run["duration_seconds"]) if run.get("duration_seconds") is not None else None,
        errors=run.get("errors") or [],
    )


@router.get("/filters")
async def deal_analytics_filters() -> dict:
    return DealAnalyticsQueryService().filter_options()


@router.get("/brands/{brand_value}/operating", response_model=DealAnalyticsEnvelope)
async def brand_operating(brand_value: str) -> DealAnalyticsEnvelope:
    allowed = {"voyah", "mhero", "shacman"}
    brand = brand_value.strip().lower()
    if brand not in allowed:
        raise HTTPException(status_code=400, detail=f"Marca no soportada. Use: {', '.join(sorted(allowed))}")
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().brand_operating(brand))


@router.get("/advisors/brand-benchmark", response_model=AdvisorBenchmarkResponse)
async def advisors_brand_benchmark(
    brand_value: str | None = Query(default=None, description="Filtrar por marca: voyah, mhero o shacman"),
    only_registered: bool = Query(
        default=True,
        description="Si true, solo asesores del archivo Propietarios (app/data/advisor_brand_assignments.json)",
    ),
    only_with_email: bool = Query(
        default=False,
        description="Si true, excluye asesores sin correo en HubSpot (útil para flujos n8n de envío)",
    ),
    tolerance_pct: float = Query(default=10.0, ge=0, le=100, description="Tolerancia % para considerar 'similar' al promedio"),
) -> AdvisorBenchmarkResponse:
    if brand_value:
        allowed = {"voyah", "mhero", "shacman"}
        brand = brand_value.strip().lower()
        if brand not in allowed:
            raise HTTPException(status_code=400, detail=f"Marca no soportada. Use: {', '.join(sorted(allowed))}")
    else:
        brand = None

    try:
        payload = AdvisorBrandBenchmarkService().benchmark(
            brand_value=brand,
            only_registered=only_registered,
            tolerance_pct=tolerance_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if only_with_email:
        payload["advisors"] = [
            row for row in payload["advisors"] if row.get("email_status") == "available" and row.get("email")
        ]
        payload["summary"]["total_advisors"] = len(payload["advisors"])

    return AdvisorBenchmarkResponse.model_validate(payload)


@router.get("/brands/{brand_value}/advisors/{owner_id}/portfolio", response_model=DealAnalyticsEnvelope)
async def advisor_portfolio(brand_value: str, owner_id: str) -> DealAnalyticsEnvelope:
    allowed = {"voyah", "mhero", "shacman"}
    brand = brand_value.strip().lower()
    if brand not in allowed:
        raise HTTPException(status_code=400, detail=f"Marca no soportada. Use: {', '.join(sorted(allowed))}")
    return DealAnalyticsEnvelope.model_validate(
        DealAnalyticsQueryService().advisor_portfolio(brand, owner_id)
    )


@router.get("/summary", response_model=DealAnalyticsEnvelope)
async def summary(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().summary(filters))


@router.get("/by-stage", response_model=DealAnalyticsEnvelope)
async def by_stage(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "stage"))


@router.get("/by-pipeline", response_model=DealAnalyticsEnvelope)
async def by_pipeline(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "pipeline"))


@router.get("/by-brand", response_model=DealAnalyticsEnvelope)
async def by_brand(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "brand"))


@router.get("/by-owner", response_model=DealAnalyticsEnvelope)
async def by_owner(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "owner"))


@router.get("/by-zone", response_model=DealAnalyticsEnvelope)
async def by_zone(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "zone"))


@router.get("/brands-zones", response_model=DealAnalyticsEnvelope)
async def brands_zones(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().brands_zones(filters))


@router.get("/by-status", response_model=DealAnalyticsEnvelope)
async def by_status(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().group_by(filters, "status"))


@router.get("/age-distribution", response_model=DealAnalyticsEnvelope)
async def age_distribution(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().age_distribution(filters))


@router.get("/stage-age-distribution", response_model=DealAnalyticsEnvelope)
async def stage_age_distribution(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().stage_age_distribution(filters))


@router.get("/inactivity-distribution", response_model=DealAnalyticsEnvelope)
async def inactivity_distribution(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().inactivity_distribution(filters))


@router.get("/activity-outcomes", response_model=DealAnalyticsEnvelope)
async def activity_outcomes(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().activity_outcomes(filters))


@router.get("/owners", response_model=DealAnalyticsEnvelope)
async def owners(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().owners(filters))


@router.get("/owners/{owner_id}", response_model=DealAnalyticsEnvelope)
async def owner_detail(owner_id: str, filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().owner_detail(owner_id, filters))


@router.get("/deals", response_model=DealAnalyticsEnvelope)
async def deals(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().deals(filters))


@router.get("/deals/{deal_id}")
async def deal_detail(deal_id: str) -> dict:
    row = DealAnalyticsQueryService().deal_detail(deal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Negocio no encontrado en deal_analytics")
    return row


@router.get("/funnel", response_model=DealAnalyticsEnvelope)
async def funnel(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().funnel(filters))


@router.get("/stage-movements", response_model=DealAnalyticsEnvelope)
async def stage_movements(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().stage_movements(filters))


@router.get("/analysis/activity-vs-outcome", response_model=DealAnalyticsEnvelope)
async def analysis_activity_vs_outcome(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(
        DealAnalyticsQueryService().analysis_activity_vs_outcome(filters)
    )


@router.get("/analysis/age-vs-outcome", response_model=DealAnalyticsEnvelope)
async def analysis_age_vs_outcome(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(DealAnalyticsQueryService().analysis_age_vs_outcome(filters))


@router.get("/analysis/meetings-vs-outcome", response_model=DealAnalyticsEnvelope)
async def analysis_meetings_vs_outcome(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(
        DealAnalyticsQueryService().analysis_meetings_vs_outcome(filters)
    )


@router.get("/analysis/response-vs-outcome", response_model=DealAnalyticsEnvelope)
async def analysis_response_vs_outcome(filters: DealAnalyticsFilters = Depends(_filters_from_query)) -> DealAnalyticsEnvelope:
    return DealAnalyticsEnvelope.model_validate(
        DealAnalyticsQueryService().analysis_response_vs_outcome(filters)
    )
