"""Primera respuesta desde asignación o creación (fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.services.deal_analytics.evaluation_config import (
    BUSINESS_DAYS,
    BUSINESS_HOURS_END,
    BUSINESS_HOURS_START,
    get_sla_for_deal,
)
from app.utils.dates import parse_hubspot_datetime


class FirstResponseBasis(StrEnum):
    OWNER_ASSIGNMENT = "owner_assignment"
    DEAL_CREATION_FALLBACK = "deal_creation_fallback"
    UNAVAILABLE = "unavailable"


@dataclass
class FirstResponseResult:
    first_response_minutes: float | None
    first_response_basis: str
    assignment_at: datetime | None
    first_contact_at: datetime | None
    data_status: str
    sla_minutes: int | None
    within_sla: bool | None


def _business_minutes_between(start: datetime, end: datetime) -> float:
    """Minutos hábiles aproximados (sin festivos)."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end <= start:
        return 0.0
    total = 0.0
    cursor = start
    while cursor < end:
        if cursor.weekday() in BUSINESS_DAYS:
            day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
            work_start = day_start.replace(hour=BUSINESS_HOURS_START // 60, minute=BUSINESS_HOURS_START % 60)
            work_end = day_start.replace(hour=BUSINESS_HOURS_END // 60, minute=BUSINESS_HOURS_END % 60)
            seg_start = max(cursor, work_start)
            seg_end = min(end, work_end)
            if seg_end > seg_start:
                total += (seg_end - seg_start).total_seconds() / 60.0
        cursor = (cursor.replace(hour=0, minute=0, second=0, microsecond=0) + __import__("datetime").timedelta(days=1))
    return total


def compute_first_response(
    deal: dict[str, Any],
    *,
    first_effective_contact_at: datetime | None,
    assignment_at: datetime | None = None,
    use_business_minutes: bool = True,
) -> FirstResponseResult:
    sla = get_sla_for_deal(deal)
    sla_minutes = int(sla.get("first_response_minutes", 60))

    created_raw = deal.get("created_at")
    created_at = parse_hubspot_datetime(created_raw) if created_raw else None
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    basis = FirstResponseBasis.UNAVAILABLE
    anchor: datetime | None = None

    if assignment_at:
        if assignment_at.tzinfo is None:
            assignment_at = assignment_at.replace(tzinfo=UTC)
        anchor = assignment_at
        basis = FirstResponseBasis.OWNER_ASSIGNMENT
    elif created_at:
        anchor = created_at
        basis = FirstResponseBasis.DEAL_CREATION_FALLBACK

    if not anchor or not first_effective_contact_at:
        return FirstResponseResult(
            first_response_minutes=None,
            first_response_basis=basis.value,
            assignment_at=assignment_at,
            first_contact_at=first_effective_contact_at,
            data_status="partial" if anchor or first_effective_contact_at else "unavailable",
            sla_minutes=sla_minutes,
            within_sla=None,
        )

    if first_effective_contact_at.tzinfo is None:
        first_effective_contact_at = first_effective_contact_at.replace(tzinfo=UTC)

    if use_business_minutes:
        minutes = _business_minutes_between(anchor, first_effective_contact_at)
    else:
        minutes = (first_effective_contact_at - anchor).total_seconds() / 60.0

    within = minutes <= sla_minutes if minutes is not None else None
    data_status = "available" if basis == FirstResponseBasis.OWNER_ASSIGNMENT else "partial"

    return FirstResponseResult(
        first_response_minutes=round(minutes, 1),
        first_response_basis=basis.value,
        assignment_at=assignment_at,
        first_contact_at=first_effective_contact_at,
        data_status=data_status,
        sla_minutes=sla_minutes,
        within_sla=within,
    )
