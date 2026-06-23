"""Esquemas del dashboard semanal."""

from typing import Any, Literal

from pydantic import BaseModel, Field

DataStatus = Literal["available", "partial", "unavailable"]
Direction = Literal["higher_is_better", "lower_is_better", "informational"]


class DashboardFiltersApplied(BaseModel):
    week_start: str
    week_end: str
    brand: str
    owner_id: str | None = None
    pipeline_id: str | None = None


class DashboardKpiCard(BaseModel):
    code: str
    label: str
    value: float | int | None = None
    unit: str
    previous_value: float | int | None = None
    change_value: float | int | None = None
    change_percentage: float | None = None
    direction: Direction
    data_status: DataStatus
    status_reason: str | None = None
    display_value: str | None = None


class TrendPoint(BaseModel):
    week_start: str
    week_label: str
    leads_created: int = 0
    deals_created: int = 0
    pipeline_created_amount: float = 0
    won_amount: float = 0


class BrandResultRow(BaseModel):
    brand: str
    brand_label: str
    leads_created: int | None = None
    leads_data_status: DataStatus = "unavailable"
    deals_created: int = 0
    won_deals: int = 0


class CloseRateChart(BaseModel):
    won_deals: int = 0
    lost_deals: int = 0
    close_rate: float | None = None
    data_status: DataStatus = "unavailable"


class AdvisorActivityRow(BaseModel):
    owner_id: str
    owner_name: str
    calls: int = 0
    communications: int = 0
    completed_meetings: int = 0
    tasks: int = 0
    notes: int = 0
    total_effective: int = 0


class FirstResponseBrandRow(BaseModel):
    brand: str
    brand_label: str
    average_first_response_minutes: float | None = None
    median_first_response_minutes: float | None = None
    sample_size: int = 0
    data_status: DataStatus = "unavailable"


class Contacted24hBrandRow(BaseModel):
    brand: str
    brand_label: str
    contacted_within_24h_rate: float | None = None
    eligible_contacts: int = 0
    contacted_count: int = 0
    data_status: DataStatus = "unavailable"


class DataQualityRuleRow(BaseModel):
    rule_code: str
    label: str
    severity: str
    count: int


class DashboardCharts(BaseModel):
    leads_and_deals_trend: list[TrendPoint] = Field(default_factory=list)
    brand_results: list[BrandResultRow] = Field(default_factory=list)
    pipeline_vs_won: list[TrendPoint] = Field(default_factory=list)
    close_rate: CloseRateChart = Field(default_factory=CloseRateChart)
    advisor_activities: list[AdvisorActivityRow] = Field(default_factory=list)
    first_response_by_brand: list[FirstResponseBrandRow] = Field(default_factory=list)
    contacted_within_24h_by_brand: list[Contacted24hBrandRow] = Field(default_factory=list)
    data_quality: list[DataQualityRuleRow] = Field(default_factory=list)


class DashboardMetadata(BaseModel):
    generated_at: str
    timezone: str = "America/Bogota"
    activity_window_days: int = 60
    email_tracking_enabled: bool = False
    email_data_required: bool = False
    owner_scope_active: bool = False
    owner_scope_note: str | None = None
    metadata_snapshot_at: str | None = None
    metadata_version: str | None = None
    field_mapping_version: int = 1
    dimension_mapping_version: int = 1


class DashboardWeeklyResponse(BaseModel):
    filters: DashboardFiltersApplied
    cards: list[DashboardKpiCard]
    charts: DashboardCharts
    metadata: DashboardMetadata


class FilterOption(BaseModel):
    value: str
    label: str


class DashboardFiltersResponse(BaseModel):
    weeks: list[FilterOption]
    brands: list[FilterOption]
    owners: list[FilterOption]
    pipelines: list[FilterOption]
    metadata: dict[str, Any] = Field(default_factory=dict)
