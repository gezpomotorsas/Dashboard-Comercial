"""Esquemas de calidad de datos."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

QualityScope = Literal["all", "contacts", "deals", "activities", "associations"]
QualitySeverity = Literal["info", "warning", "critical"]
QualityRunStatus = Literal["started", "running", "completed", "completed_with_errors", "failed"]


class DataQualityRunRequest(BaseModel):
    scope: QualityScope = "all"


class DataQualityRunStartResponse(BaseModel):
    run_id: UUID
    status: QualityRunStatus = "started"


class DataQualityRunSchema(BaseModel):
    id: UUID
    status: QualityRunStatus
    started_at: datetime
    finished_at: datetime | None = None
    rules_executed: int = 0
    records_evaluated: int = 0
    issues_found: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataQualityResultSchema(BaseModel):
    id: UUID
    run_id: UUID
    rule_code: str
    object_type: str
    hubspot_id: str | None = None
    severity: QualitySeverity
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    issue_key: str
    detected_at: datetime
    resolved_at: datetime | None = None
    is_resolved: bool = False


class DataQualityResultListResponse(BaseModel):
    data: list[DataQualityResultSchema]
    count: int
    limit: int
    offset: int


class DataQualitySummary(BaseModel):
    total_issues: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    by_object_type: dict[str, int] = Field(default_factory=dict)
    by_rule: list[dict[str, Any]] = Field(default_factory=list)
    last_run_at: datetime | None = None


class DataQualityRunListResponse(BaseModel):
    data: list[DataQualityRunSchema]
    count: int
