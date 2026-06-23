"""Configuración centralizada de la aplicación."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "gezpomotor-hubspot-extractor"

_DEFAULT_HUBSPOT_CONCURRENCY = min(16, max(4, (os.cpu_count() or 4) * 2))

HUBSPOT_OBJECT_TYPES = {
    "contacts": "contacts",
    "deals": "deals",
    "calls": "calls",
    "meetings": "meetings",
    "tasks": "tasks",
    "emails": "emails",
    "communications": "communications",
    "notes": "notes",
}

DEFAULT_PROPERTY_BATCH_SIZE = 80
INCREMENTAL_OVERLAP_MINUTES = 15

CONTACT_SOURCE_PROPERTY_CANDIDATES: tuple[str, ...] = (
    "hs_analytics_source",
    "source",
    "origen",
    "lead_source",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hubspot_access_token: SecretStr = Field(
        validation_alias=AliasChoices(
            "HUBSPOT_ACCESS_TOKEN",
            "hubspot_api_key",
            "hubspot_api_key_service",
        ),
    )
    supabase_url: str = Field(validation_alias=AliasChoices("SUPABASE_URL"))
    supabase_secret_key: SecretStr = Field(
        validation_alias=AliasChoices("SUPABASE_SECRET_KEY"),
    )
    auto_sync_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTO_SYNC_ENABLED"),
    )
    auto_sync_daily_at: str | None = Field(
        default="03:00",
        validation_alias=AliasChoices("AUTO_SYNC_DAILY_AT"),
        description="Hora local (BUSINESS_TIMEZONE) para sync diario HH:MM. Vacío = usar AUTO_SYNC_INTERVAL_MINUTES",
    )
    auto_sync_interval_minutes: int = Field(
        default=1440,
        ge=5,
        le=10080,
        validation_alias=AliasChoices("AUTO_SYNC_INTERVAL_MINUTES"),
        description="Intervalo entre sincronizaciones si AUTO_SYNC_DAILY_AT está vacío (1440 = 24 h)",
    )
    auto_sync_batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
        validation_alias=AliasChoices("AUTO_SYNC_BATCH_SIZE"),
    )
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV"),
    )
    app_version: str = Field(default="0.1.0", validation_alias=AliasChoices("APP_VERSION"))
    hubspot_base_url: str = "https://api.hubapi.com"
    hubspot_timeout_seconds: float = 30.0
    hubspot_max_retries: int = 3
    hubspot_default_limit: int = 100
    association_batch_size: int = Field(default=100, ge=1, le=100)
    data_quality_stale_deal_days: int = Field(
        default=30,
        validation_alias=AliasChoices("DATA_QUALITY_STALE_DEAL_DAYS"),
    )
    allow_full_phase2_validation: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_FULL_PHASE2_VALIDATION"),
    )
    phase2_validation_sample_size: int = Field(default=50, ge=1, le=500)
    association_sync_lookback_days: int = Field(
        default=60,
        ge=0,
        le=3650,
        validation_alias=AliasChoices("ASSOCIATION_SYNC_LOOKBACK_DAYS"),
        description="Solo sincronizar asociaciones de objetos creados/modificados en los últimos N días (0 = sin límite)",
    )
    association_sync_lookback_field: Literal["created_at_hubspot", "updated_at_hubspot"] = Field(
        default="created_at_hubspot",
        validation_alias=AliasChoices("ASSOCIATION_SYNC_LOOKBACK_FIELD"),
    )
    association_sync_hubspot_concurrency: int = Field(
        default=_DEFAULT_HUBSPOT_CONCURRENCY,
        ge=1,
        le=32,
        validation_alias=AliasChoices("ASSOCIATION_SYNC_HUBSPOT_CONCURRENCY"),
        description="Llamadas HubSpot en paralelo durante sync de asociaciones",
    )
    activity_sync_lookback_days: int = Field(
        default=60,
        ge=1,
        le=90,
        validation_alias=AliasChoices("ACTIVITY_SYNC_LOOKBACK_DAYS"),
        description="Ventana móvil (días) para sync de actividades HubSpot",
    )
    task_sync_full_history: bool = Field(
        default=True,
        validation_alias=AliasChoices("TASK_SYNC_FULL_HISTORY"),
        description="Sincronizar historial completo de tareas (list API) en sync full",
    )
    stale_deal_days_without_activity: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias=AliasChoices("STALE_DEAL_DAYS_WITHOUT_ACTIVITY"),
    )
    stale_deal_days_in_stage: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias=AliasChoices("STALE_DEAL_DAYS_IN_STAGE"),
    )
    deal_analytics_batch_size: int = Field(
        default=500,
        ge=50,
        le=2000,
        validation_alias=AliasChoices("DEAL_ANALYTICS_BATCH_SIZE"),
    )
    business_timezone: str = Field(
        default="America/Bogota",
        validation_alias=AliasChoices("BUSINESS_TIMEZONE"),
    )
    contact_coverage_window_days: int = Field(
        default=21,
        ge=7,
        le=60,
        validation_alias=AliasChoices("CONTACT_COVERAGE_WINDOW_DAYS"),
        description="Ventana en días para cobertura de llamadas/WhatsApp (default gerencia: 21)",
    )
    whatsapp_session_gap_hours: int = Field(
        default=24,
        ge=1,
        le=72,
        validation_alias=AliasChoices("WHATSAPP_SESSION_GAP_HOURS"),
    )
    cors_origins: list[str] = Field(
        default=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("auto_sync_daily_at", mode="before")
    @classmethod
    def parse_auto_sync_daily_at(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or stripped.lower() in {"off", "false", "none", "0"}:
            return None
        from app.utils.sync_schedule import parse_daily_at

        hour, minute = parse_daily_at(stripped)
        return f"{hour:02d}:{minute:02d}"

    @field_validator("supabase_url", mode="before")
    @classmethod
    def strip_supabase_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().rstrip("/")

    @field_validator("app_version", mode="before")
    @classmethod
    def strip_version(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
