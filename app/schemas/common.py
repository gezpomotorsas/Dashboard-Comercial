"""Esquemas Pydantic compartidos."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    next_after: str | None = None
    has_more: bool = False


class ResponseMeta(BaseModel):
    count: int
    object_type: str


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta
    meta: ResponseMeta


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str


class VersionResponse(BaseModel):
    service: str
    version: str
    environment: str


class ErrorResponse(BaseModel):
    detail: str
    error_type: str | None = None


class HubSpotPropertyOption(BaseModel):
    label: str | None = None
    value: str | None = None
    description: str | None = None
    display_order: int | None = Field(default=None, alias="displayOrder")
    hidden: bool | None = None

    model_config = {"populate_by_name": True}


class HubSpotPropertySchema(BaseModel):
    name: str
    label: str | None = None
    type: str | None = None
    field_type: str | None = Field(default=None, alias="fieldType")
    group_name: str | None = Field(default=None, alias="groupName")
    description: str | None = None
    options: list[HubSpotPropertyOption] | list[dict[str, Any]] = Field(default_factory=list)
    calculated: bool | None = None
    hidden: bool | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class HubSpotOwnerSchema(BaseModel):
    id: str
    email: str | None = None
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    user_id: int | None = Field(default=None, alias="userId")
    teams: list[dict[str, Any]] | None = None
    archived: bool = False

    model_config = {"populate_by_name": True}


class HubSpotPipelineStageSchema(BaseModel):
    id: str
    label: str | None = None
    display_order: int | None = Field(default=None, alias="displayOrder")
    metadata: dict[str, Any] | None = None
    archived: bool = False

    model_config = {"populate_by_name": True}


class HubSpotPipelineSchema(BaseModel):
    id: str
    label: str | None = None
    display_order: int | None = Field(default=None, alias="displayOrder")
    stages: list[HubSpotPipelineStageSchema] = Field(default_factory=list)
    archived: bool = False

    model_config = {"populate_by_name": True}


class HubSpotAssociationLabelSchema(BaseModel):
    category: str | None = None
    type_id: int | None = Field(default=None, alias="typeId")
    label: str | None = None
    from_object_type: str | None = None
    to_object_type: str | None = None

    model_config = {"populate_by_name": True}


class HubSpotObjectResponse(BaseModel):
    id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    archived: bool = False
    associations: dict[str, Any] | None = None
    brand: str | None = None

    model_config = {"populate_by_name": True}
