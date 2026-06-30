"""Elegibilidad de negocios para métricas de contacto y cobertura."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.services.deal_analytics.evaluation_config import NON_ACTIONABLE_COMMERCIAL_GROUPS, get_sla_for_deal
from app.utils.dates import parse_hubspot_datetime


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class ExclusionReason(StrEnum):
    CLOSED_DEAL = "closed_deal"
    MISSING_OWNER = "missing_owner"
    NON_ACTIONABLE_STAGE = "non_actionable_stage"
    NO_CONTACT_INFORMATION = "no_contact_information"
    PAUSED_UNTIL_FUTURE_DATE = "paused_until_future_date"
    DO_NOT_CONTACT = "do_not_contact"
    DUPLICATE = "duplicate"
    TEST_RECORD = "test_record"
    INVALID_DATA = "invalid_data"
    UNKNOWN = "unknown"


@dataclass
class ContactEligibility:
    is_eligible: bool
    eligibility_status: EligibilityStatus
    exclusion_reason: str | None
    contact_due_at: datetime | None
    applicable_sla: dict[str, int | float]
    data_status: str  # available | partial | unknown


def _is_test_or_duplicate(deal: dict[str, Any]) -> ExclusionReason | None:
    name = str(deal.get("deal_name") or "").lower()
    if any(token in name for token in ("test", "prueba", "duplicate", "duplicado")):
        if "test" in name or "prueba" in name:
            return ExclusionReason.TEST_RECORD
        return ExclusionReason.DUPLICATE
    return None


def resolve_contact_eligibility(
    deal: dict[str, Any],
    *,
    now: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> ContactEligibility:
    """Determina si un negocio entra al denominador de cobertura/contacto."""
    ctx = context or {}
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    sla = get_sla_for_deal(deal)
    data_status = "available"

    if not deal.get("is_open", True) and deal.get("status") not in (None, "open"):
        if deal.get("is_won") or deal.get("is_lost") or str(deal.get("status")) in ("won", "lost"):
            return ContactEligibility(
                is_eligible=False,
                eligibility_status=EligibilityStatus.EXCLUDED,
                exclusion_reason=ExclusionReason.CLOSED_DEAL.value,
                contact_due_at=None,
                applicable_sla=sla,
                data_status=data_status,
            )

    group = str(deal.get("commercial_group") or "").lower()
    if group in NON_ACTIONABLE_COMMERCIAL_GROUPS:
        return ContactEligibility(
            is_eligible=False,
            eligibility_status=EligibilityStatus.EXCLUDED,
            exclusion_reason=ExclusionReason.NON_ACTIONABLE_STAGE.value,
            contact_due_at=None,
            applicable_sla=sla,
            data_status=data_status,
        )

    owner_id = deal.get("owner_id")
    if not owner_id and not deal.get("has_owner", False):
        return ContactEligibility(
            is_eligible=False,
            eligibility_status=EligibilityStatus.EXCLUDED,
            exclusion_reason=ExclusionReason.MISSING_OWNER.value,
            contact_due_at=None,
            applicable_sla=sla,
            data_status="partial",
        )

    if deal.get("has_contact") is False and not ctx.get("has_contact_channel"):
        return ContactEligibility(
            is_eligible=False,
            eligibility_status=EligibilityStatus.EXCLUDED,
            exclusion_reason=ExclusionReason.NO_CONTACT_INFORMATION.value,
            contact_due_at=None,
            applicable_sla=sla,
            data_status="partial",
        )

    test_dup = _is_test_or_duplicate(deal)
    if test_dup:
        return ContactEligibility(
            is_eligible=False,
            eligibility_status=EligibilityStatus.EXCLUDED,
            exclusion_reason=test_dup.value,
            contact_due_at=None,
            applicable_sla=sla,
            data_status=data_status,
        )

    # Pausa futura / do-not-contact — configurable vía props cuando existan
    pause_until = ctx.get("paused_until") or deal.get("paused_until")
    if pause_until:
        pause_dt = parse_hubspot_datetime(pause_until)
        if pause_dt and pause_dt.tzinfo is None:
            pause_dt = pause_dt.replace(tzinfo=UTC)
        if pause_dt and pause_dt > now:
            return ContactEligibility(
                is_eligible=False,
                eligibility_status=EligibilityStatus.EXCLUDED,
                exclusion_reason=ExclusionReason.PAUSED_UNTIL_FUTURE_DATE.value,
                contact_due_at=pause_dt,
                applicable_sla=sla,
                data_status="partial",
            )

    dnc = ctx.get("do_not_contact") or deal.get("do_not_contact")
    if dnc in (True, "true", "1", 1):
        return ContactEligibility(
            is_eligible=False,
            eligibility_status=EligibilityStatus.EXCLUDED,
            exclusion_reason=ExclusionReason.DO_NOT_CONTACT.value,
            contact_due_at=None,
            applicable_sla=sla,
            data_status="partial",
        )

    followup_days = int(sla.get("followup_days", 3))
    last_contact = deal.get("last_effective_contact_at") or deal.get("last_activity_at")
    contact_due_at = None
    if last_contact:
        last_dt = parse_hubspot_datetime(last_contact)
        if last_dt:
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            from datetime import timedelta

            contact_due_at = last_dt + timedelta(days=followup_days)

    return ContactEligibility(
        is_eligible=True,
        eligibility_status=EligibilityStatus.ELIGIBLE,
        exclusion_reason=None,
        contact_due_at=contact_due_at,
        applicable_sla=sla,
        data_status=data_status,
    )


def summarize_eligibility(
    deals: list[dict[str, Any]],
    *,
    context_by_deal: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ctx_map = context_by_deal or {}
    total_open = sum(1 for d in deals if d.get("is_open"))
    eligible = 0
    excluded_by_reason: dict[str, int] = {}
    for deal in deals:
        if not deal.get("is_open"):
            continue
        deal_id = str(deal.get("deal_id") or "")
        result = resolve_contact_eligibility(deal, now=now, context=ctx_map.get(deal_id))
        if result.is_eligible:
            eligible += 1
        elif result.exclusion_reason:
            excluded_by_reason[result.exclusion_reason] = excluded_by_reason.get(result.exclusion_reason, 0) + 1
    return {
        "total_open_deals": total_open,
        "eligible_deals": eligible,
        "excluded_deals": total_open - eligible,
        "excluded_by_reason": excluded_by_reason,
    }
