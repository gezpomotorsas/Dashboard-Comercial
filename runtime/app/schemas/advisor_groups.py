"""Esquemas para grupos de asesores."""

from typing import Any, Literal

from pydantic import BaseModel, Field

GroupSource = Literal["manual", "hubspot_team", "hubspot_list"]


class AdvisorGroupMemberSchema(BaseModel):
    owner_id: str
    owner_name: str | None = None


class AdvisorGroupSchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    brand_value: str | None = None
    source: GroupSource = "manual"
    hubspot_source_id: str | None = None
    hubspot_source_label: str | None = None
    members: list[AdvisorGroupMemberSchema] = Field(default_factory=list)
    member_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AdvisorGroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    brand_value: str | None = None
    source: GroupSource = "manual"
    hubspot_source_id: str | None = None
    hubspot_source_label: str | None = None
    members: list[AdvisorGroupMemberSchema] = Field(default_factory=list)


class AdvisorGroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    brand_value: str | None = None
    members: list[AdvisorGroupMemberSchema] | None = None


class HubSpotTeamOptionSchema(BaseModel):
    team_id: str
    team_name: str
    member_count: int
    owner_ids: list[str]


class HubSpotListOptionSchema(BaseModel):
    list_id: str
    name: str
    object_type_id: str | None = None
    processing_type: str | None = None
    size: int | None = None


class GroupsCompareRequest(BaseModel):
    brand_value: str
    group_ids: list[str] = Field(min_length=1, max_length=8)


class GroupCompareRowSchema(BaseModel):
    group_id: str
    group_name: str
    member_count: int
    assigned_deals: int
    open_deals: int
    new_deals_7d: int
    new_deals_30d: int
    stale_45d_open: int
    tasks_completed: int
    tasks_open: int
    tasks_overdue: int
    deals_with_overdue_tasks: int
    managed_30d_rate: float | None = None
    advisors: list[dict[str, Any]] = Field(default_factory=list)
