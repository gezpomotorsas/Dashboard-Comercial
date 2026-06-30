"""Resolución canónica actividad → negocio con deduplicación."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.services.deal_analytics.contact_eligibility import resolve_contact_eligibility


class AttributionMethod(StrEnum):
    DIRECT_DEAL_ASSOCIATION = "direct_deal_association"
    UNIQUE_CONTACT_OPEN_DEAL = "unique_contact_open_deal"
    TEMPORAL_OWNER_MATCH = "temporal_owner_match"
    AMBIGUOUS = "ambiguous"
    UNATTRIBUTED = "unattributed"


class AttributionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


@dataclass
class ActivityAttribution:
    activity_id: str
    activity_type: str
    resolved_deal_id: str | None
    attribution_method: str
    attribution_confidence: str
    candidate_deal_count: int
    is_ambiguous: bool


@dataclass
class AttributionQuality:
    attributed_activity_count: int = 0
    ambiguous_activity_count: int = 0
    unattributed_activity_count: int = 0
    duplicate_prevented_count: int = 0


@dataclass
class ResolvedActivityBundle:
    """Actividades atribuidas sin duplicar por activity_id."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    communications: list[dict[str, Any]] = field(default_factory=list)
    quality: AttributionQuality = field(default_factory=AttributionQuality)
    attributions: dict[str, ActivityAttribution] = field(default_factory=dict)


def resolve_activity_to_deal(
    activity_id: str,
    activity_type: str,
    *,
    direct_deal_ids: list[str],
    contact_deal_ids: list[str],
    open_deal_context: dict[str, dict[str, Any]],
    activity_owner_id: str | None = None,
) -> ActivityAttribution:
    """Prioridad: asociación directa → único negocio abierto del contacto."""
    direct = [d for d in direct_deal_ids if d in open_deal_context]
    if len(direct) == 1:
        return ActivityAttribution(
            activity_id=activity_id,
            activity_type=activity_type,
            resolved_deal_id=direct[0],
            attribution_method=AttributionMethod.DIRECT_DEAL_ASSOCIATION.value,
            attribution_confidence=AttributionConfidence.HIGH.value,
            candidate_deal_count=1,
            is_ambiguous=False,
        )
    if len(direct) > 1:
        return ActivityAttribution(
            activity_id=activity_id,
            activity_type=activity_type,
            resolved_deal_id=None,
            attribution_method=AttributionMethod.AMBIGUOUS.value,
            attribution_confidence=AttributionConfidence.LOW.value,
            candidate_deal_count=len(direct),
            is_ambiguous=True,
        )

    eligible_contact_deals = []
    for deal_id in contact_deal_ids:
        ctx = open_deal_context.get(deal_id)
        if not ctx:
            continue
        elig = resolve_contact_eligibility(ctx)
        if elig.is_eligible:
            eligible_contact_deals.append(deal_id)

    if len(eligible_contact_deals) == 1:
        return ActivityAttribution(
            activity_id=activity_id,
            activity_type=activity_type,
            resolved_deal_id=eligible_contact_deals[0],
            attribution_method=AttributionMethod.UNIQUE_CONTACT_OPEN_DEAL.value,
            attribution_confidence=AttributionConfidence.MEDIUM.value,
            candidate_deal_count=1,
            is_ambiguous=False,
        )

    if len(eligible_contact_deals) > 1 and activity_owner_id:
        owner_matches = [
            d
            for d in eligible_contact_deals
            if str(open_deal_context.get(d, {}).get("owner_id") or "") == str(activity_owner_id)
        ]
        if len(owner_matches) == 1:
            return ActivityAttribution(
                activity_id=activity_id,
                activity_type=activity_type,
                resolved_deal_id=owner_matches[0],
                attribution_method=AttributionMethod.TEMPORAL_OWNER_MATCH.value,
                attribution_confidence=AttributionConfidence.MEDIUM.value,
                candidate_deal_count=len(eligible_contact_deals),
                is_ambiguous=False,
            )

    if len(eligible_contact_deals) > 1:
        return ActivityAttribution(
            activity_id=activity_id,
            activity_type=activity_type,
            resolved_deal_id=None,
            attribution_method=AttributionMethod.AMBIGUOUS.value,
            attribution_confidence=AttributionConfidence.LOW.value,
            candidate_deal_count=len(eligible_contact_deals),
            is_ambiguous=True,
        )

    return ActivityAttribution(
        activity_id=activity_id,
        activity_type=activity_type,
        resolved_deal_id=None,
        attribution_method=AttributionMethod.UNATTRIBUTED.value,
        attribution_confidence=AttributionConfidence.UNAVAILABLE.value,
        candidate_deal_count=0,
        is_ambiguous=False,
    )


def build_resolved_call_index(
    *,
    deal_ids: list[str],
    deal_to_call_ids: dict[str, list[str]],
    call_to_contact_deal_ids: dict[str, list[str]],
    open_deal_context: dict[str, dict[str, Any]],
    call_rows_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], AttributionQuality, dict[str, ActivityAttribution]]:
    """Mapa call_id → deal_id único; deduplica cuando misma llamada aparece por deal y contacto."""
    quality = AttributionQuality()
    call_to_deal: dict[str, str] = {}
    attributions: dict[str, ActivityAttribution] = {}
    seen: set[str] = set()

    all_call_ids: set[str] = set()
    for ids in deal_to_call_ids.values():
        all_call_ids.update(ids)
    for ids in call_to_contact_deal_ids.values():
        all_call_ids.update(ids)

    for call_id in sorted(all_call_ids):
        if call_id in seen:
            quality.duplicate_prevented_count += 1
            continue
        seen.add(call_id)

        direct_deals = [d for d, ids in deal_to_call_ids.items() if call_id in ids]
        contact_deals: list[str] = []
        for d, ids in call_to_contact_deal_ids.items():
            if call_id in ids:
                contact_deals.append(d)

        row = call_rows_by_id.get(call_id) or {}
        props = row.get("properties") or {}
        owner = row.get("hubspot_owner_id") or props.get("hubspot_owner_id")

        attr = resolve_activity_to_deal(
            call_id,
            "calls",
            direct_deal_ids=direct_deals,
            contact_deal_ids=contact_deals,
            open_deal_context=open_deal_context,
            activity_owner_id=str(owner) if owner else None,
        )
        attributions[call_id] = attr

        if attr.is_ambiguous:
            quality.ambiguous_activity_count += 1
        elif attr.resolved_deal_id:
            call_to_deal[call_id] = attr.resolved_deal_id
            quality.attributed_activity_count += 1
        else:
            quality.unattributed_activity_count += 1

    return call_to_deal, quality, attributions
