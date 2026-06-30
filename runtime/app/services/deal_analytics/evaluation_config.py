"""Configuración de metodología de evaluación v2 (pesos, SLA, umbrales)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings


@dataclass(frozen=True)
class ScoreWeights:
    eligible_contact_compliance: float = 30.0
    first_response_sla: float = 25.0
    next_action_compliance: float = 20.0
    effective_contact: float = 15.0
    overdue_task_compliance: float = 10.0

    def as_dict(self) -> dict[str, float]:
        return {
            "eligible_contact_compliance": self.eligible_contact_compliance,
            "first_response_sla": self.first_response_sla,
            "next_action_compliance": self.next_action_compliance,
            "effective_contact": self.effective_contact,
            "overdue_task_compliance": self.overdue_task_compliance,
        }

    def validate(self) -> None:
        total = sum(self.as_dict().values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Score weights must sum to 100, got {total}")


DEFAULT_OPERATIONAL_WEIGHTS = ScoreWeights()

# SLA por grupo comercial (mapeado desde stage_semantics commercial_group)
CONTACT_SLA_BY_COMMERCIAL_GROUP: dict[str, dict[str, int | float]] = {
    "prospeccion": {"first_response_minutes": 30, "followup_days": 1},
    "contacto_inicial": {"first_response_minutes": 30, "followup_days": 1},
    "cotizacion": {"followup_days": 3},
    "cotizacion_financiera": {"followup_days": 3},
    "prueba_manejo": {"followup_days": 2},
    "test_drive": {"followup_days": 2},
    "negociacion": {"followup_days": 3},
    "cierre": {"followup_days": 2},
}

DEFAULT_SLA: dict[str, int | float] = {
    "first_response_minutes": 60,
    "followup_days": 3,
}

# Grupos que no requieren gestión activa de contacto
NON_ACTIONABLE_COMMERCIAL_GROUPS = frozenset(
    {
        "cierre_ganado",
        "cierre_perdido",
        "unknown",
    }
)

# Umbrales clasificación llamadas (segundos)
CALL_DURATION_CONNECTED_THRESHOLD_SECONDS = 5.0
CALL_DURATION_MEANINGFUL_THRESHOLD_SECONDS = 30.0

# Mínimos para scores y rankings
MIN_COMPONENTS_FOR_OPERATIONAL_SCORE = 3
MIN_SAMPLE_SIZE_FOR_RANKING = 5
MIN_CLOSED_DEALS_FOR_EFFECTIVENESS = 3

# Horario comercial (minutos desde medianoche, zona BUSINESS_TIMEZONE)
BUSINESS_HOURS_START = 8 * 60  # 08:00
BUSINESS_HOURS_END = 18 * 60  # 18:00
BUSINESS_DAYS = frozenset({0, 1, 2, 3, 4})  # Lun–Vie


def get_sla_for_deal(deal: dict[str, Any]) -> dict[str, int | float]:
    group = str(deal.get("commercial_group") or "unknown").lower()
    return dict(CONTACT_SLA_BY_COMMERCIAL_GROUP.get(group, DEFAULT_SLA))


def get_evaluation_settings() -> dict[str, Any]:
    settings = get_settings()
    DEFAULT_OPERATIONAL_WEIGHTS.validate()
    return {
        "operational_score_weights": DEFAULT_OPERATIONAL_WEIGHTS.as_dict(),
        "contact_sla_by_commercial_group": CONTACT_SLA_BY_COMMERCIAL_GROUP,
        "default_sla": DEFAULT_SLA,
        "call_duration_connected_threshold_seconds": CALL_DURATION_CONNECTED_THRESHOLD_SECONDS,
        "call_duration_meaningful_threshold_seconds": CALL_DURATION_MEANINGFUL_THRESHOLD_SECONDS,
        "min_components_for_operational_score": MIN_COMPONENTS_FOR_OPERATIONAL_SCORE,
        "min_sample_size_for_ranking": MIN_SAMPLE_SIZE_FOR_RANKING,
        "min_closed_deals_for_effectiveness": MIN_CLOSED_DEALS_FOR_EFFECTIVENESS,
        "business_timezone": settings.business_timezone,
        "contact_coverage_window_days": settings.contact_coverage_window_days,
        "activity_lookback_days": settings.activity_sync_lookback_days,
        "business_hours": {"start_minute": BUSINESS_HOURS_START, "end_minute": BUSINESS_HOURS_END},
    }
