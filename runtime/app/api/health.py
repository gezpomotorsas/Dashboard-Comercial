"""Endpoints de salud y versión."""

from fastapi import APIRouter

from app.config import SERVICE_NAME, get_settings
from app.schemas.common import HealthResponse, VersionResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=settings.app_version,
    )


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        service=SERVICE_NAME,
        version=settings.app_version,
        environment=settings.app_env,
    )
