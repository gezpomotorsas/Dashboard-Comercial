"""Semántica de tareas HubSpot para analítica de asesores."""

from __future__ import annotations

from typing import Any

from app.services.deal_analytics.stage_semantics import normalize_stage_text

# Tarea de workflow: el lead fue reasignado a otro asesor; no penaliza rendimiento.
REASSIGNED_LEAD_SUBJECT_PATTERN = "perdiste este lead"

CLOSED_DEAL_COMMERCIAL_GROUPS = frozenset({"cierre_ganado", "cierre_perdido"})


def task_subject_from_record(task: dict[str, Any]) -> str:
    props = task.get("properties") or {}
    return str(props.get("hs_task_subject") or task.get("hs_task_subject") or "")


def is_reassigned_lead_task(subject: str | None) -> bool:
    normalized = normalize_stage_text(subject)
    if not normalized:
        return False
    return REASSIGNED_LEAD_SUBJECT_PATTERN in normalized


def is_reassigned_lead_activity(item: dict[str, Any]) -> bool:
    if item.get("activity_type") != "tasks":
        return False
    return is_reassigned_lead_task(task_subject_from_record(item))


def is_closed_deal_for_task_metrics(deal_info: dict[str, Any] | None) -> bool:
    """Negocios en cierre ganado/perdido no deben afectar estadísticas de tareas."""
    if not deal_info:
        return False
    status = str(deal_info.get("status") or "").lower()
    if status in ("won", "lost"):
        return True
    if deal_info.get("is_won") or deal_info.get("is_lost"):
        return True
    group = str(deal_info.get("commercial_group") or "").lower()
    if group in CLOSED_DEAL_COMMERCIAL_GROUPS:
        return True
    label = normalize_stage_text(str(deal_info.get("commercial_group_label") or ""))
    return "cierre ganado" in label or "cierre perdido" in label


def is_closed_deal_row_for_task_metrics(row: dict[str, Any]) -> bool:
    return is_closed_deal_for_task_metrics(
        {
            "status": row.get("status"),
            "is_won": row.get("is_won"),
            "is_lost": row.get("is_lost"),
            "commercial_group": row.get("commercial_group"),
            "commercial_group_label": row.get("commercial_group_label"),
        }
    )
