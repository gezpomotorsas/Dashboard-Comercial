"""Punto de entrada FastAPI."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    activities,
    advisor_groups,
    associations,
    configuration,
    contacts,
    dashboard,
    data_quality,
    deal_analytics,
    deals,
    health,
    metadata,
    sync,
    sync_associations,
)
from app.clients.hubspot import close_hubspot_client, get_hubspot_client
from app.clients.hubspot_exceptions import (
    HubSpotAuthenticationError,
    HubSpotClientError,
    HubSpotNotFoundError,
    HubSpotPermissionError,
    HubSpotRateLimitError,
    HubSpotRequestError,
)
from app.clients.supabase import SupabaseClientError, close_supabase_client
from app.config import SERVICE_NAME, get_settings
from app.logging_config import setup_logging
from app.services.sync_scheduler import start_sync_scheduler, stop_sync_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("Iniciando %s v%s (%s)", SERVICE_NAME, settings.app_version, settings.app_env)
    await get_hubspot_client()
    scheduler = start_sync_scheduler()
    if scheduler:
        logger.info("Sync automático habilitado")
    yield
    await stop_sync_scheduler()
    close_supabase_client()
    await close_hubspot_client()
    logger.info("Aplicación detenida")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Gezpomotor HubSpot Extractor",
        description="API de extracción de datos HubSpot hacia Supabase (solo lectura).",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(configuration.router)
    app.include_router(metadata.router)
    app.include_router(contacts.router)
    app.include_router(deals.router)
    app.include_router(activities.router)
    app.include_router(sync.router)
    app.include_router(associations.router)
    app.include_router(sync_associations.router)
    app.include_router(data_quality.router)
    app.include_router(dashboard.router)
    app.include_router(deal_analytics.router)
    app.include_router(advisor_groups.router)

    @app.exception_handler(HubSpotAuthenticationError)
    async def hubspot_auth_handler(_: Request, exc: HubSpotAuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc), "error_type": "authentication"})

    @app.exception_handler(HubSpotPermissionError)
    async def hubspot_permission_handler(_: Request, exc: HubSpotPermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc), "error_type": "permission"})

    @app.exception_handler(HubSpotNotFoundError)
    async def hubspot_not_found_handler(_: Request, exc: HubSpotNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "error_type": "not_found"})

    @app.exception_handler(HubSpotRateLimitError)
    async def hubspot_rate_limit_handler(_: Request, exc: HubSpotRateLimitError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc), "error_type": "rate_limit"})

    @app.exception_handler(HubSpotRequestError)
    async def hubspot_request_handler(_: Request, exc: HubSpotRequestError) -> JSONResponse:
        status_code = exc.status_code or 502
        return JSONResponse(status_code=status_code, content={"detail": str(exc), "error_type": "request"})

    @app.exception_handler(HubSpotClientError)
    async def hubspot_client_handler(_: Request, exc: HubSpotClientError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc), "error_type": "hubspot_client"})

    @app.exception_handler(SupabaseClientError)
    async def database_client_handler(_: Request, exc: SupabaseClientError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "error_type": "supabase_unavailable"},
        )

    return app


app = create_app()
