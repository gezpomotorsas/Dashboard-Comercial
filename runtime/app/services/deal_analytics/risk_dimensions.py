"""Dimensiones de riesgo independientes y prioridad derivada."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class RiskDimensions:
    contact_status: str
    next_action_status: str
    progression_status: str
    task_status: str
    risk_priority: str
    risk_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_status": self.contact_status,
            "next_action_status": self.next_action_status,
            "progression_status": self.progression_status,
            "task_status": self.task_status,
            "risk_priority": self.risk_priority,
            "risk_reasons": self.risk_reasons,
        }


def compute_risk_dimensions(
    deal: dict[str, Any],
    *,
    next_action: Any | None = None,
    contact_overdue: bool = False,
) -> RiskDimensions:
    reasons: list[str] = []

    # Contact
    if contact_overdue:
        contact_status = "overdue"
        reasons.append("contact_overdue")
    elif deal.get("has_effective_contact") or deal.get("has_recent_effective_contact_30d"):
        contact_status = "on_time"
    elif not deal.get("has_activity"):
        contact_status = "no_contact"
        reasons.append("no_contact")
    else:
        contact_status = "unknown"

    # Next action
    na_status = "unknown"
    if next_action is not None:
        na_status = getattr(next_action, "next_action_status", None) or (
            next_action.get("next_action_status") if isinstance(next_action, dict) else "unknown"
        )
        if na_status == "missing":
            reasons.append("next_action_missing")
        elif na_status == "overdue":
            reasons.append("next_action_overdue")

    # Progression
    if deal.get("is_stale") or deal.get("is_stale_45d"):
        progression_status = "stalled_in_stage"
        reasons.append("stalled_in_stage")
    elif deal.get("days_in_current_stage") is not None and deal.get("days_in_current_stage", 0) < 7:
        progression_status = "recently_changed"
    elif deal.get("has_recent_activity_30d"):
        progression_status = "progressing"
    else:
        progression_status = "unknown"

    # Tasks
    if deal.get("operational_has_overdue_tasks") or deal.get("has_overdue_tasks"):
        task_status = "overdue"
        if "tasks_overdue" not in reasons:
            reasons.append("tasks_overdue")
    elif int(deal.get("operational_open_task_count") or deal.get("open_task_count") or 0) == 0:
        task_status = "no_tasks"
    elif deal.get("has_future_task") or deal.get("operational_has_future_task"):
        task_status = "healthy"
    else:
        task_status = "unknown"

    # Priority (dedupe reasons)
    unique_reasons = list(dict.fromkeys(reasons))
    priority = RiskPriority.NONE
    if not deal.get("is_open"):
        priority = RiskPriority.NONE
    elif len(unique_reasons) >= 3:
        priority = RiskPriority.CRITICAL
    elif "contact_overdue" in unique_reasons and "tasks_overdue" in unique_reasons:
        priority = RiskPriority.CRITICAL
    elif unique_reasons:
        priority = RiskPriority.HIGH if len(unique_reasons) >= 2 else RiskPriority.MEDIUM
    elif contact_status == "unknown" and task_status == "unknown":
        priority = RiskPriority.INSUFFICIENT_DATA

    return RiskDimensions(
        contact_status=contact_status,
        next_action_status=na_status,
        progression_status=progression_status,
        task_status=task_status,
        risk_priority=priority.value,
        risk_reasons=unique_reasons,
    )
