"""Esquemas relacionados con HubSpot."""

from typing import Any

from pydantic import BaseModel, Field


class HubSpotPagingNext(BaseModel):
    after: str


class HubSpotPaging(BaseModel):
    next: HubSpotPagingNext | None = None


class HubSpotListResult(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    paging: HubSpotPaging | None = None
    total: int | None = None


class HubSpotSearchResult(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    paging: HubSpotPaging | None = None
    total: int | None = None
