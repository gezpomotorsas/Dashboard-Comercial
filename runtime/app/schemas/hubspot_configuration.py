"""Esquemas de configuración HubSpot."""

from typing import Any

from pydantic import BaseModel, Field


class HubSpotMappingsReport(BaseModel):
    semantic_fields: list[dict[str, Any]] = Field(default_factory=list)
    properties_found: int = 0
    missing_properties: list[dict[str, Any]] = Field(default_factory=list)
    pipelines: list[dict[str, Any]] = Field(default_factory=list)
    stages: list[dict[str, Any]] = Field(default_factory=list)
    stage_classifications: list[dict[str, Any]] = Field(default_factory=list)
    active_owners: list[dict[str, Any]] = Field(default_factory=list)
    archived_owners: list[dict[str, Any]] = Field(default_factory=list)
    brand_mappings: list[dict[str, Any]] = Field(default_factory=list)
    invalid_mappings: list[dict[str, Any]] = Field(default_factory=list)
    last_refresh_at: str | None = None
    metadata_snapshot_at: str | None = None
    field_mapping_version: int = 1
    dimension_mapping_version: int = 1


class HubSpotMappingIssue(BaseModel):
    issue_type: str
    message: str
    pipeline_id: str | None = None
    stage_id: str | None = None
    object_type: str | None = None
    semantic_key: str | None = None
    hubspot_property_name: str | None = None


class MetadataRefreshResponse(BaseModel):
    id: str
    status: str
    finished_at: str | None = None
    properties_synced: int = 0
    pipelines_synced: int = 0
    stages_synced: int = 0
    owners_synced: int = 0
    association_types_synced: int = 0
    mappings_validated: int = 0
    mappings_invalidated: int = 0
    field_mapping_version: int = 1
    dimension_mapping_version: int = 1
