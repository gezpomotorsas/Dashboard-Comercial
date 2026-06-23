"""Comparación asesor vs promedio de su marca (para automatización n8n)."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Verdict = Literal["above", "below", "similar"] | None
OverallStatus = Literal["good", "needs_improvement", "insufficient_data"]
Action = Literal["felicitar", "compromiso_mejora", "sin_datos"]

ASSIGNMENTS_PATH = Path(__file__).resolve().parents[2] / "data" / "advisor_brand_assignments.json"

BRAND_LABELS = {
    "voyah": "Voyah",
    "mhero": "MHero",
    "shacman": "Shacman",
}


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    higher_is_better: bool
    pick: str  # performance key path


PERFORMANCE_METRIC_DEFS: tuple[MetricDef, ...] = (
    MetricDef("won_sales_month", "Ventas este mes", True, "won_sales.units_this_month"),
    MetricDef("leads_created", "Leads creados (mes)", True, "leads_created.units_this_month"),
    MetricDef("tasks_completed_monthly", "Tareas completadas (mes)", True, "tasks_completed_monthly.units_this_month"),
    MetricDef("tasks_managed_monthly", "Tareas gestionadas (mes)", True, "tasks_managed_monthly.units_this_month"),
    MetricDef("tasks_overdue", "Tareas atrasadas", False, "tasks_overdue"),
    MetricDef("calls_monthly", "Llamadas (mes)", True, "calls_monthly.units_this_month"),
    MetricDef("whatsapp_monthly", "WhatsApp (mes)", True, "whatsapp_monthly.units_this_month"),
)

COVERAGE_METRIC_DEFS: tuple[MetricDef, ...] = (
    MetricDef("call_coverage_rate", "Cobertura llamadas (%)", True, "call_coverage_rate"),
    MetricDef("whatsapp_coverage_rate", "Cobertura WhatsApp (%)", True, "whatsapp_coverage_rate"),
    MetricDef("combined_coverage_rate", "Cobertura combinada (%)", True, "combined_coverage_rate"),
    MetricDef("managed_30d_rate", "Gestión 30d (%)", True, "managed_30d_rate"),
    MetricDef("discipline_operational_score", "Disciplina operativa", True, "discipline_operational_score"),
)


def load_advisor_assignments() -> list[dict[str, str]]:
    if not ASSIGNMENTS_PATH.exists():
        return []
    with ASSIGNMENTS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return " ".join(normalized.lower().split())


def find_advisor_by_name(advisors: list[dict[str, Any]], assignment_name: str) -> dict[str, Any] | None:
    target = normalize_name(assignment_name)
    if not target:
        return None

    for advisor in advisors:
        if normalize_name(str(advisor.get("owner_name") or "")) == target:
            return advisor

    target_tokens = set(target.split())
    best: dict[str, Any] | None = None
    best_score = 0
    for advisor in advisors:
        name_tokens = set(normalize_name(str(advisor.get("owner_name") or "")).split())
        if not name_tokens:
            continue
        overlap = len(target_tokens & name_tokens)
        if overlap > best_score and overlap >= max(1, min(len(target_tokens), len(name_tokens)) - 1):
            best = advisor
            best_score = overlap
    return best


def _get_nested(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def advisor_performance(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("performance"):
        return row["performance"]
    return {
        "won_sales": row.get("won_sales") or _empty_summary(),
        "leads_created": row.get("leads_created") or _empty_summary(),
        "tasks_overdue": int(row.get("tasks_overdue") or 0),
        "tasks_overdue_monthly": _empty_summary(),
        "tasks_completed_monthly": _empty_summary(),
        "tasks_managed_monthly": _empty_summary(),
        "calls_monthly": {
            **_empty_summary(),
            "units_this_month": int(row.get("total_calls") or 0),
        },
        "whatsapp_monthly": {
            **_empty_summary(),
            "units_this_month": int(row.get("whatsapp_messages") or 0),
        },
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "total_units": 0,
        "units_this_month": 0,
        "units_previous_month": 0,
        "month_over_month_change_pct": None,
        "this_month_key": "",
        "previous_month_key": "",
    }


def _metric_value(row: dict[str, Any], definition: MetricDef) -> float | None:
    if definition.pick in {
        "call_coverage_rate",
        "whatsapp_coverage_rate",
        "combined_coverage_rate",
        "managed_30d_rate",
        "discipline_operational_score",
    }:
        raw = row.get(definition.pick)
        if raw is None:
            raw = row.get("discipline_contact_score") if definition.pick == "discipline_operational_score" else None
    elif definition.pick == "tasks_overdue":
        raw = advisor_performance(row).get("tasks_overdue")
    else:
        raw = _get_nested(advisor_performance(row), definition.pick)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def classify_vs_brand(
    advisor_value: float,
    brand_avg: float | None,
    *,
    higher_is_better: bool,
    tolerance_pct: float = 10.0,
) -> Verdict:
    if brand_avg is None:
        return None
    if brand_avg == 0:
        if advisor_value == 0:
            return "similar"
        above = advisor_value > 0
        return "above" if (above and higher_is_better) or (not above and not higher_is_better) else "below"
    delta_pct = ((advisor_value - brand_avg) / abs(brand_avg)) * 100
    if abs(delta_pct) <= tolerance_pct:
        return "similar"
    above = advisor_value > brand_avg
    if higher_is_better:
        return "above" if above else "below"
    return "below" if above else "above"


def _brand_average(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


def _metric_status(verdict: Verdict) -> Literal["good", "needs_improvement", "unknown"]:
    if verdict in ("above", "similar"):
        return "good"
    if verdict == "below":
        return "needs_improvement"
    return "unknown"


def build_advisor_brand_comparison(
    advisor: dict[str, Any],
    peers: list[dict[str, Any]],
    *,
    tolerance_pct: float = 10.0,
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    definitions = (*PERFORMANCE_METRIC_DEFS, *COVERAGE_METRIC_DEFS)

    for definition in definitions:
        advisor_value = _metric_value(advisor, definition)
        if advisor_value is None:
            continue
        peer_values = [_metric_value(peer, definition) for peer in peers]
        brand_avg = _brand_average(peer_values)
        verdict = classify_vs_brand(
            advisor_value,
            brand_avg,
            higher_is_better=definition.higher_is_better,
            tolerance_pct=tolerance_pct,
        )
        delta_pct = None
        if brand_avg not in (None, 0):
            delta_pct = round(((advisor_value - brand_avg) / abs(brand_avg)) * 100, 1)

        metrics.append(
            {
                "key": definition.key,
                "label": definition.label,
                "higher_is_better": definition.higher_is_better,
                "advisor_value": round(advisor_value, 1),
                "brand_avg_value": brand_avg,
                "delta_pct": delta_pct,
                "verdict": verdict,
                "status": _metric_status(verdict),
            }
        )
    return metrics


def summarize_comparison(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [metric for metric in metrics if metric.get("verdict") is not None]
    if not comparable:
        return {
            "overall_status": "insufficient_data",
            "overall_verdict": None,
            "action": "sin_datos",
            "metrics_above_count": 0,
            "metrics_below_count": 0,
            "metrics_similar_count": 0,
            "strengths": [],
            "improvement_areas": [],
        }

    above = sum(1 for metric in comparable if metric["verdict"] == "above")
    below = sum(1 for metric in comparable if metric["verdict"] == "below")
    similar = sum(1 for metric in comparable if metric["verdict"] == "similar")
    strengths = [metric["label"] for metric in comparable if metric["verdict"] == "above"]
    improvement_areas = [metric["label"] for metric in comparable if metric["verdict"] == "below"]

    if below == 0:
        overall_status: OverallStatus = "good"
        action: Action = "felicitar"
        overall_verdict: Verdict = "above" if above > 0 else "similar"
    else:
        overall_status = "needs_improvement"
        action = "compromiso_mejora"
        overall_verdict = "below" if below >= above else "similar"

    return {
        "overall_status": overall_status,
        "overall_verdict": overall_verdict,
        "action": action,
        "metrics_above_count": above,
        "metrics_below_count": below,
        "metrics_similar_count": similar,
        "strengths": strengths,
        "improvement_areas": improvement_areas,
    }
