"""Esquemas deal analytics."""

from typing import Any

from pydantic import BaseModel, Field

from app.services.deal_analytics.filters import DealAnalyticsFilters


class DealAnalyticsRefreshResponse(BaseModel):
    run_id: str
    status: str


class DealAnalyticsRunStatus(BaseModel):
    id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    deals_processed: int = 0
    deals_inserted: int = 0
    deals_updated: int = 0
    deals_failed: int = 0
    metadata_version: str | None = None
    field_mapping_version: int | None = None
    dimension_mapping_version: int | None = None
    duration_seconds: float | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class DealAnalyticsEnvelope(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    population: dict[str, int] = Field(default_factory=dict)
    data: Any = None
    data_quality: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    generated_at: str
    timezone: str = "America/Bogota"


DealAnalyticsFilterParams = DealAnalyticsFilters
