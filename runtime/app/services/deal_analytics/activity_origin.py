"""Origen de actividad: humano vs automatizado."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ActivityOrigin(StrEnum):
    HUMAN = "human"
    WORKFLOW = "workflow"
    BOT = "bot"
    INTEGRATION = "integration"
    SYSTEM = "system"
    UNKNOWN = "unknown"


WORKFLOW_MARKERS = (
    "workflow",
    "sequence",
    "automation",
    "enrollment",
)


def classify_activity_origin(properties: dict[str, Any], *, activity_type: str) -> str:
    """Inferencia conservadora desde propiedades HubSpot disponibles."""
    for key in ("hs_engagement_source", "hs_object_source", "hs_created_by_user_id"):
        val = str(properties.get(key) or "").lower()
        if "workflow" in val or "automation" in val:
            return ActivityOrigin.WORKFLOW.value
        if "integration" in val:
            return ActivityOrigin.INTEGRATION.value

    body = str(properties.get("hs_communication_body") or properties.get("hs_call_body") or "").lower()
    if any(m in body for m in WORKFLOW_MARKERS):
        return ActivityOrigin.WORKFLOW.value

    if properties.get("hs_created_by_user_id") or properties.get("hubspot_owner_id"):
        return ActivityOrigin.HUMAN.value

    return ActivityOrigin.UNKNOWN.value
