"""Endpoints agregados del dashboard gerencial."""

from fastapi import APIRouter, Depends, Query

from app.schemas.dashboard import DashboardFiltersResponse, DashboardWeeklyResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def get_dashboard_service() -> DashboardService:
    return DashboardService()


@router.get("/weekly", response_model=DashboardWeeklyResponse)
async def weekly_dashboard(
    week_start: str | None = Query(default=None, description="Lunes de la semana (YYYY-MM-DD)"),
    brand: str = Query(default="all"),
    owner_id: str | None = Query(default=None),
    pipeline_id: str | None = Query(default=None),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardWeeklyResponse:
    return service.get_weekly_dashboard(
        week_start=week_start,
        brand=brand,
        owner_id=owner_id,
        pipeline_id=pipeline_id,
    )


@router.get("/filters", response_model=DashboardFiltersResponse)
async def dashboard_filters(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardFiltersResponse:
    return service.get_filters()
