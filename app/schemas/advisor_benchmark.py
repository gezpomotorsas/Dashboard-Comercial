"""Esquemas para benchmark asesor vs marca."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AdvisorBenchmarkMetric(BaseModel):
    key: str
    label: str
    higher_is_better: bool
    advisor_value: float
    brand_avg_value: float | None = None
    delta_pct: float | None = None
    verdict: Literal["above", "below", "similar"] | None = None
    status: Literal["good", "needs_improvement", "unknown"]


class AdvisorBenchmarkRow(BaseModel):
    owner_id: str
    owner_name: str | None = None
    registered_name: str | None = None
    email: str | None = None
    email_status: Literal["available", "missing"] = "missing"
    first_name: str | None = None
    last_name: str | None = None
    brand_value: str
    brand_label: str
    location: str = ""
    match_status: Literal["matched", "not_found_in_hubspot"] = "matched"
    peer_count: int = 0
    open_deals: int | None = None
    overall_status: Literal["good", "needs_improvement", "insufficient_data"]
    overall_verdict: Literal["above", "below", "similar"] | None = None
    action: Literal["felicitar", "compromiso_mejora", "sin_datos"]
    metrics_above_count: int = 0
    metrics_below_count: int = 0
    metrics_similar_count: int = 0
    strengths: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)
    metrics: list[AdvisorBenchmarkMetric] = Field(default_factory=list)


class AdvisorBenchmarkSummary(BaseModel):
    total_advisors: int = 0
    good_count: int = 0
    needs_improvement_count: int = 0
    insufficient_data_count: int = 0
    unmatched_count: int = 0
    missing_email_count: int = 0


class AdvisorBenchmarkResponse(BaseModel):
    generated_at: str
    timezone: str
    tolerance_pct: float
    only_registered: bool
    brands: list[str]
    advisors: list[AdvisorBenchmarkRow]
    unmatched_registrations: list[dict[str, Any]] = Field(default_factory=list)
    advisors_missing_email: list[dict[str, Any]] = Field(default_factory=list)
    summary: AdvisorBenchmarkSummary
