"""Estado de próxima acción por negocio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.services.deal_analytics.evaluation_config import get_sla_for_deal
from app.services.deal_analytics.task_semantics import is_closed_deal_for_task_metrics, is_reassigned_lead_task
from app.utils.dates import parse_hubspot_datetime


class NextActionStatus(StrEnum):
    SCHEDULED_ON_TIME = "scheduled_on_time"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


@dataclass
class NextActionResult:
    has_next_action: bool
    next_action_due_at: datetime | None
    next_action_status: str
    next_action_owner: str | None
    next_action_overdue_days: int | None
    next_action_data_status: str
    next_action_task_id: str | None = None


def _is_task_completed(status: Any, config: Any) -> bool:
    if config and hasattr(config, "is_task_completed"):
        return config.is_task_completed(status)
    normalized = str(status or "").strip().upper()
    return normalized in {"COMPLETED", "COMPLETE", "DONE", "FINISHED"}


def resolve_next_action_status(
    deal: dict[str, Any],
    tasks: list[dict[str, Any]],
    *,
    config: Any,
    now: datetime | None = None,
) -> NextActionResult:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    if is_closed_deal_for_task_metrics(deal) or not deal.get("is_open", True):
        return NextActionResult(
            has_next_action=False,
            next_action_due_at=None,
            next_action_status=NextActionStatus.NOT_REQUIRED.value,
            next_action_owner=None,
            next_action_overdue_days=None,
            next_action_data_status="available",
        )

    sla = get_sla_for_deal(deal)
    due_soon_days = min(2, int(sla.get("followup_days", 3)))

    open_tasks: list[tuple[datetime, dict[str, Any]]] = []
    for task in tasks:
        props = task.get("properties") or {}
        subject = str(props.get("hs_task_subject") or "")
        if is_reassigned_lead_task(subject):
            continue
        if _is_task_completed(props.get("hs_task_status"), config):
            continue
        due_raw = props.get("hs_task_due_date") or task.get("activity_timestamp")
        due_at = parse_hubspot_datetime(due_raw)
        if not due_at:
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if due_at >= now:
            open_tasks.append((due_at, task))

    if not open_tasks:
        return NextActionResult(
            has_next_action=False,
            next_action_due_at=None,
            next_action_status=NextActionStatus.MISSING.value,
            next_action_owner=deal.get("owner_id"),
            next_action_overdue_days=None,
            next_action_data_status="available",
        )

    open_tasks.sort(key=lambda x: x[0])
    due_at, task = open_tasks[0]
    props = task.get("properties") or {}
    owner = task.get("hubspot_owner_id") or props.get("hubspot_owner_id") or deal.get("owner_id")
    days_until = (due_at.date() - now.date()).days

    if days_until < 0:
        status = NextActionStatus.OVERDUE
        overdue_days = abs(days_until)
    elif days_until <= due_soon_days:
        status = NextActionStatus.DUE_SOON
        overdue_days = None
    else:
        status = NextActionStatus.SCHEDULED_ON_TIME
        overdue_days = None

    if not owner:
        return NextActionResult(
            has_next_action=True,
            next_action_due_at=due_at,
            next_action_status=NextActionStatus.INVALID.value,
            next_action_owner=None,
            next_action_overdue_days=overdue_days,
            next_action_data_status="partial",
            next_action_task_id=str(task.get("hubspot_id") or ""),
        )

    return NextActionResult(
        has_next_action=True,
        next_action_due_at=due_at,
        next_action_status=status.value,
        next_action_owner=str(owner),
        next_action_overdue_days=overdue_days,
        next_action_data_status="available",
        next_action_task_id=str(task.get("hubspot_id") or ""),
    )
