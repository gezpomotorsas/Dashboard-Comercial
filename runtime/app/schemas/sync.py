"""Esquemas de sincronización."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

SyncType = Literal["full", "incremental", "window"]
SyncStatus = Literal["started", "running", "completed", "completed_with_errors", "failed"]


class SyncRequest(BaseModel):
    sync_type: SyncType = "full"
    batch_size: int = Field(default=100, ge=1, le=500)
    lookback_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def validate_window_lookback(self) -> "SyncRequest":
        if self.sync_type == "window" and self.lookback_days is None:
            self.lookback_days = 60
        return self


class SyncStartResponse(BaseModel):
    sync_id: UUID
    status: SyncStatus = "started"
    message: str = "Sincronización iniciada"


class SyncRunSchema(BaseModel):
    id: UUID
    source: str
    object_type: str
    sync_type: SyncType
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None = None
    records_found: int = 0
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncRunListResponse(BaseModel):
    data: list[SyncRunSchema]
    count: int


class SyncErrorSchema(BaseModel):
    id: UUID
    sync_run_id: UUID
    object_type: str
    hubspot_id: str | None = None
    error_type: str
    error_message: str
    http_status: int | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime
