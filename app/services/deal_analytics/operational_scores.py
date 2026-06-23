"""Scores operativos v2: disciplina operativa y efectividad comercial."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.deal_analytics.contact_classification import ContactLevel, is_connected_level, is_meaningful_contact
from app.services.deal_analytics.contact_eligibility import resolve_contact_eligibility, summarize_eligibility
from app.services.deal_analytics.evaluation_config import (
    DEFAULT_OPERATIONAL_WEIGHTS,
    MIN_CLOSED_DEALS_FOR_EFFECTIVENESS,
    MIN_COMPONENTS_FOR_OPERATIONAL_SCORE,
    MIN_SAMPLE_SIZE_FOR_RANKING,
    ScoreWeights,
    get_sla_for_deal,
)
from app.services.deal_analytics.first_response import compute_first_response
from app.utils.dates import parse_hubspot_datetime


@dataclass
class RateMetric:
    numerator: int
    denominator: int
    rate: float | None
    data_status: str  # available | insufficient | unavailable | partial

    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate": self.rate,
            "data_status": self.data_status,
        }


@dataclass
class OperationalScoreResult:
    score: float | None
    status: str  # available | insufficient | unavailable | partial
    available_components: list[str] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "status": self.status,
            "available_components": self.available_components,
            "missing_components": self.missing_components,
            "components": self.components,
            "weights": self.weights,
        }


def _rate(numerator: int, denominator: int, *, min_denom: int = 1) -> RateMetric:
    if denominator < min_denom:
        return RateMetric(numerator, denominator, None, "insufficient")
    return RateMetric(
        numerator,
        denominator,
        round(numerator / denominator * 100, 1),
        "available",
    )


def legacy_discipline_contact_score(
    call_cov: float | None,
    wa_cov: float | None,
    combined_cov: float | None,
    overdue_rate: float | None,
) -> float | None:
    """Fórmula original (deprecated): duplica cobertura combinada."""
    if combined_cov is None and call_cov is None and wa_cov is None:
        return None
    return round(
        (call_cov or 0) * 0.25
        + (wa_cov or 0) * 0.25
        + (combined_cov or 0) * 0.25
        + max(0, 100 - (overdue_rate or 0)) * 0.15
        + (combined_cov or 0) * 0.10,
        1,
    )


def compute_eligible_contact_compliance(
    deals: list[dict[str, Any]],
    *,
    last_contact_by_deal: dict[str, datetime],
    now: datetime,
) -> RateMetric:
    eligible_ids: list[str] = []
    compliant = 0
    for deal in deals:
        if not deal.get("is_open"):
            continue
        deal_id = str(deal.get("deal_id") or "")
        elig = resolve_contact_eligibility(deal)
        if not elig.is_eligible:
            continue
        eligible_ids.append(deal_id)
        sla = elig.applicable_sla
        followup_days = int(sla.get("followup_days", 3))
        last = last_contact_by_deal.get(deal_id)
        if last and (now - last).days <= followup_days:
            compliant += 1
        elif not last:
            created = parse_hubspot_datetime(deal.get("created_at"))
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if (now - created).days <= followup_days:
                    compliant += 1
    return _rate(compliant, len(eligible_ids), min_denom=1)


def compute_first_response_sla_rate(
    deals: list[dict[str, Any]],
    *,
    assignment_at_by_deal: dict[str, datetime | None] | None = None,
) -> RateMetric:
    assignment_at_by_deal = assignment_at_by_deal or {}
    evaluated = 0
    within = 0
    for deal in deals:
        if not deal.get("is_open"):
            continue
        elig = resolve_contact_eligibility(deal)
        if not elig.is_eligible:
            continue
        first_raw = deal.get("first_effective_contact_at")
        first_dt = parse_hubspot_datetime(first_raw) if first_raw else None
        deal_id = str(deal.get("deal_id") or "")
        result = compute_first_response(
            deal,
            first_effective_contact_at=first_dt,
            assignment_at=assignment_at_by_deal.get(deal_id),
        )
        if result.first_response_minutes is None:
            continue
        evaluated += 1
        if result.within_sla:
            within += 1
    return _rate(within, evaluated, min_denom=1)


def compute_next_action_compliance(
    deals: list[dict[str, Any]],
    next_action_by_deal: dict[str, Any],
) -> RateMetric:
    eligible = 0
    ok = 0
    for deal in deals:
        if not deal.get("is_open"):
            continue
        elig = resolve_contact_eligibility(deal)
        if not elig.is_eligible:
            continue
        deal_id = str(deal.get("deal_id") or "")
        eligible += 1
        na = next_action_by_deal.get(deal_id)
        if not na:
            continue
        status = getattr(na, "next_action_status", None) or (na.get("next_action_status") if isinstance(na, dict) else None)
        if status in ("scheduled_on_time", "due_soon", "not_required"):
            ok += 1
    return _rate(ok, eligible, min_denom=1)


def compute_effective_contact_rate(
    deals: list[dict[str, Any]],
    *,
    meaningful_contact_deal_ids: set[str],
) -> RateMetric:
    eligible = 0
    hit = 0
    for deal in deals:
        if not deal.get("is_open"):
            continue
        elig = resolve_contact_eligibility(deal)
        if not elig.is_eligible:
            continue
        eligible += 1
        deal_id = str(deal.get("deal_id") or "")
        if deal_id in meaningful_contact_deal_ids:
            hit += 1
    return _rate(hit, eligible, min_denom=1)


def compute_overdue_task_compliance(deals: list[dict[str, Any]]) -> RateMetric:
    eligible = 0
    clean = 0
    for deal in deals:
        if not deal.get("is_open"):
            continue
        elig = resolve_contact_eligibility(deal)
        if not elig.is_eligible:
            continue
        eligible += 1
        has_overdue = deal.get("operational_has_overdue_tasks")
        if has_overdue is None:
            has_overdue = deal.get("has_overdue_tasks", False)
        overdue = int(deal.get("operational_overdue_task_count") or deal.get("overdue_task_count") or 0)
        if not has_overdue and overdue == 0:
            clean += 1
    return _rate(clean, eligible, min_denom=1)


def compute_discipline_operational_score(
    components: dict[str, RateMetric],
    *,
    weights: ScoreWeights | None = None,
    min_components: int = MIN_COMPONENTS_FOR_OPERATIONAL_SCORE,
) -> OperationalScoreResult:
    w = weights or DEFAULT_OPERATIONAL_WEIGHTS
    w.validate()
    weight_map = w.as_dict()
    key_map = {
        "eligible_contact_compliance": "eligible_contact_compliance_rate",
        "first_response_sla": "first_response_sla_rate",
        "next_action_compliance": "next_action_compliance_rate",
        "effective_contact": "effective_contact_rate",
        "overdue_task_compliance": "overdue_task_compliance_rate",
    }
    available: list[str] = []
    missing: list[str] = []
    comp_out: dict[str, dict[str, Any]] = {}
    weighted_sum = 0.0
    weight_used = 0.0

    for weight_key, comp_key in key_map.items():
        metric = components.get(comp_key)
        if metric and metric.rate is not None and metric.data_status == "available":
            available.append(comp_key)
            comp_out[comp_key] = metric.to_dict()
            wt = weight_map[weight_key]
            weighted_sum += metric.rate * wt
            weight_used += wt
        else:
            missing.append(comp_key)
            if metric:
                comp_out[comp_key] = metric.to_dict()

    if len(available) < min_components or weight_used <= 0:
        return OperationalScoreResult(
            score=None,
            status="insufficient" if available else "unavailable",
            available_components=available,
            missing_components=missing,
            components=comp_out,
            weights=weight_map,
        )

    score = round(weighted_sum / weight_used, 1)
    status = "partial" if missing else "available"
    return OperationalScoreResult(
        score=score,
        status=status,
        available_components=available,
        missing_components=missing,
        components=comp_out,
        weights=weight_map,
    )


def legacy_pipeline_effectiveness_component(
    won_amount: float,
    open_pipeline_amount: float,
) -> float:
    return min(100.0, won_amount / max(open_pipeline_amount, 1) * 10)


def compute_commercial_effectiveness_score(
    *,
    won_deals: int,
    lost_deals: int,
    cohort_mature_won: int | None = None,
    cohort_mature_closed: int | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> dict[str, Any]:
    closed = won_deals + lost_deals
    mature_closed = cohort_mature_closed if cohort_mature_closed is not None else closed
    mature_won = cohort_mature_won if cohort_mature_won is not None else won_deals

    conversion = _rate(mature_won, mature_closed, min_denom=MIN_CLOSED_DEALS_FOR_EFFECTIVENESS)
    components = {"mature_cohort_conversion": conversion.to_dict()}
    missing = []
    if conversion.data_status != "available":
        missing.append("mature_cohort_conversion")

    score = conversion.rate
    status = conversion.data_status
    if closed < MIN_CLOSED_DEALS_FOR_EFFECTIVENESS:
        status = "insufficient"

    return {
        "commercial_effectiveness_score": score,
        "commercial_effectiveness_status": status,
        "legacy_effectiveness_commercial_score": round(won_deals / closed * 100, 1) if closed else None,
        "components": components,
        "missing_components": missing,
        "sample_size": closed,
        "minimum_sample_met": closed >= MIN_SAMPLE_SIZE_FOR_RANKING,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "cohort_definition": "won_lost_in_scope",
    }


def management_discipline_score(item: dict[str, Any]) -> float | None:
    """Antes discipline_score — disciplina integral de gestión."""
    open_count = item.get("open_deals") or 0
    if open_count == 0:
        return None
    managed = item.get("managed_30d_rate") or 0
    effective = item.get("effective_contact_30d_rate") or 0
    overdue_penalty = min(100, (item.get("overdue_tasks_deals") or 0) / open_count * 100)
    unattended_penalty = min(100, (item.get("unattended_open_deals") or 0) / open_count * 100)
    return round(
        (managed * 0.35)
        + (effective * 0.35)
        + max(0, 100 - overdue_penalty) * 0.15
        + max(0, 100 - unattended_penalty) * 0.15,
        1,
    )

def build_operational_evaluation_payload(
    deals: list[dict[str, Any]],
    *,
    last_contact_by_deal: dict[str, datetime],
    meaningful_contact_deal_ids: set[str],
    next_action_by_deal: dict[str, Any],
    assignment_at_by_deal: dict[str, datetime | None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    components = {
        "eligible_contact_compliance_rate": compute_eligible_contact_compliance(
            deals, last_contact_by_deal=last_contact_by_deal, now=now
        ),
        "first_response_sla_rate": compute_first_response_sla_rate(
            deals, assignment_at_by_deal=assignment_at_by_deal
        ),
        "next_action_compliance_rate": compute_next_action_compliance(deals, next_action_by_deal),
        "effective_contact_rate": compute_effective_contact_rate(
            deals, meaningful_contact_deal_ids=meaningful_contact_deal_ids
        ),
        "overdue_task_compliance_rate": compute_overdue_task_compliance(deals),
    }
    operational = compute_discipline_operational_score(components)
    eligibility_summary = summarize_eligibility(deals, now=now)

    won = sum(1 for d in deals if d.get("is_won"))
    lost = sum(1 for d in deals if d.get("is_lost"))
    commercial = compute_commercial_effectiveness_score(won_deals=won, lost_deals=lost, period_end=now)

    return {
        "eligibility": eligibility_summary,
        "discipline_operational_score": operational.to_dict(),
        "legacy_discipline_contact_score": None,  # filled by caller if legacy cov known
        "commercial_effectiveness": commercial,
        "discipline_contact_score": operational.score,  # deprecated alias → operational when available
    }
