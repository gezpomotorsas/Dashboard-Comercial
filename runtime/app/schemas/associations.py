"""Esquemas de asociaciones."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse, PaginationMeta, ResponseMeta
from app.schemas.sync import SyncType


class AssociationRecord(BaseModel):
    from_object_type: str
    from_hubspot_id: str
    to_object_type: str
    to_hubspot_id: str
    association_type_id: int | None = None
    association_category: str | None = None
    association_label: str | None = None
    is_active: bool = True


class AssociationLabelSchema(BaseModel):
    from_object_type: str
    to_object_type: str
    category: str | None = None
    type_id: int | None = Field(default=None, alias="typeId")
    label: str | None = None


class AssociationTypeListResponse(BaseModel):
    data: list[AssociationLabelSchema]
    count: int


class AssociationSyncRequest(BaseModel):
    sync_type: SyncType = "full"
    batch_size: int = Field(default=100, ge=1, le=100)
    object_offset: int = Field(
        default=0,
        ge=0,
        description="Índice del primer objeto origen a procesar en esta ejecución",
    )
    object_limit: int | None = Field(
        default=None,
        ge=1,
        le=2000,
        description="Máximo de objetos origen a procesar en esta ejecución",
    )


class AssociationSyncStartResponse(BaseModel):
    sync_id: str
    status: str = "started"
    message: str = "Sincronización de asociaciones iniciada"


def build_association_paginated(
    items: list[Any],
    *,
    next_after: str | None,
    object_type: str = "associations",
) -> PaginatedResponse[Any]:
    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(next_after=next_after, has_more=bool(next_after)),
        meta=ResponseMeta(count=len(items), object_type=object_type),
    )
