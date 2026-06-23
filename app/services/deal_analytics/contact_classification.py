"""Taxonomía canónica de contacto: intento, conexión, significativo, avance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.services.deal_analytics.evaluation_config import (
    CALL_DURATION_CONNECTED_THRESHOLD_SECONDS,
    CALL_DURATION_MEANINGFUL_THRESHOLD_SECONDS,
)
from app.services.hubspot_configuration.store import HubSpotConfigStore

# Re-export for backward compat
UNANSWERED_OUTCOMES = frozenset(
    {
        "NO_ANSWER",
        "BUSY",
        "FAILED",
        "CANCELED",
        "CANCELLED",
        "LEFT_VOICEMAIL",
        "WRONG_NUMBER",
    }
)

CONNECTED_OUTCOMES = frozenset({"CONNECTED", "COMPLETED", "SUCCESSFUL"})


class ContactLevel(StrEnum):
    NONE = "none"
    ATTEMPT = "contact_attempt"
    CONNECTED = "contact_connected"
    CONNECTED_LOW_CONFIDENCE = "connected_with_low_confidence"
    MEANINGFUL = "contact_meaningful"
    NOT_CONNECTED = "not_connected"
    UNKNOWN = "unknown"


class ConnectionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


@dataclass
class CallClassification:
    level: ContactLevel
    connection: str  # connected | unanswered | unknown | not_connected
    confidence: ConnectionConfidence
    is_effective_for_builder: bool
    is_outbound_attempt: bool


def _normalize_upper(value: Any) -> str:
    return str(value or "").strip().upper()


def classify_call(
    properties: dict[str, Any],
    *,
    duration_seconds: float | None = None,
    config: HubSpotConfigStore | None = None,
) -> CallClassification:
    """Clasificación conservadora: outcome > disposition > status > duración."""
    outcome = _normalize_upper(properties.get("hs_call_outcome"))
    disposition = _normalize_upper(properties.get("hs_call_disposition"))
    status = _normalize_upper(properties.get("hs_call_status"))
    direction = _normalize_upper(properties.get("hs_call_direction"))
    is_outbound = direction in ("OUTBOUND", "") or direction not in ("INBOUND",)

    # Outcome / disposition explícitos
    for signal in (outcome, disposition):
        if not signal or signal in ("", "NONE"):
            continue
        if signal in UNANSWERED_OUTCOMES:
            return CallClassification(
                level=ContactLevel.NOT_CONNECTED,
                connection="unanswered",
                confidence=ConnectionConfidence.HIGH,
                is_effective_for_builder=False,
                is_outbound_attempt=is_outbound,
            )
        if signal in CONNECTED_OUTCOMES:
            dur = duration_seconds or 0.0
            level = ContactLevel.MEANINGFUL if dur >= CALL_DURATION_MEANINGFUL_THRESHOLD_SECONDS else ContactLevel.CONNECTED
            return CallClassification(
                level=level,
                connection="connected",
                confidence=ConnectionConfidence.HIGH,
                is_effective_for_builder=True,
                is_outbound_attempt=is_outbound,
            )
        # Outcome presente pero no en listas → conexión con confianza media
        return CallClassification(
            level=ContactLevel.CONNECTED,
            connection="connected",
            confidence=ConnectionConfidence.MEDIUM,
            is_effective_for_builder=True,
            is_outbound_attempt=is_outbound,
        )

    if status in {"COMPLETED", "COMPLETE"}:
        store = config
        effective = store.is_call_effective(properties) if store else True
        return CallClassification(
            level=ContactLevel.CONNECTED if effective else ContactLevel.ATTEMPT,
            connection="connected" if effective else "unknown",
            confidence=ConnectionConfidence.MEDIUM,
            is_effective_for_builder=effective,
            is_outbound_attempt=is_outbound,
        )

    # Duración como respaldo conservador
    dur = duration_seconds
    if dur is not None and dur > 0:
        if dur <= CALL_DURATION_CONNECTED_THRESHOLD_SECONDS:
            return CallClassification(
                level=ContactLevel.UNKNOWN,
                connection="unknown",
                confidence=ConnectionConfidence.LOW,
                is_effective_for_builder=False,
                is_outbound_attempt=is_outbound,
            )
        if dur < CALL_DURATION_MEANINGFUL_THRESHOLD_SECONDS:
            return CallClassification(
                level=ContactLevel.CONNECTED_LOW_CONFIDENCE,
                connection="connected",
                confidence=ConnectionConfidence.LOW,
                is_effective_for_builder=False,
                is_outbound_attempt=is_outbound,
            )
        return CallClassification(
            level=ContactLevel.MEANINGFUL,
            connection="connected",
            confidence=ConnectionConfidence.MEDIUM,
            is_effective_for_builder=True,
            is_outbound_attempt=is_outbound,
        )

    if is_outbound:
        return CallClassification(
            level=ContactLevel.ATTEMPT,
            connection="unknown",
            confidence=ConnectionConfidence.UNAVAILABLE,
            is_effective_for_builder=False,
            is_outbound_attempt=True,
        )

    return CallClassification(
        level=ContactLevel.UNKNOWN,
        connection="unknown",
        confidence=ConnectionConfidence.UNAVAILABLE,
        is_effective_for_builder=False,
        is_outbound_attempt=False,
    )


def classify_call_connection(properties: dict[str, Any], duration_seconds: float | None) -> str:
    """Compatibilidad con API anterior."""
    return classify_call(properties, duration_seconds=duration_seconds).connection


def is_meaningful_contact(level: ContactLevel) -> bool:
    return level in (ContactLevel.MEANINGFUL, ContactLevel.CONNECTED)


def is_connected_level(level: ContactLevel) -> bool:
    return level in (
        ContactLevel.CONNECTED,
        ContactLevel.CONNECTED_LOW_CONFIDENCE,
        ContactLevel.MEANINGFUL,
    )


def classify_whatsapp_message(
    properties: dict[str, Any],
    *,
    activity_origin: str = "unknown",
) -> ContactLevel:
    """WhatsApp: saliente sin respuesta = intento; origen unknown si no hay señal."""
    if activity_origin in ("workflow", "bot", "system", "integration"):
        return ContactLevel.ATTEMPT
    if activity_origin == "human":
        return ContactLevel.ATTEMPT  # requiere hilo para meaningful; elevado en sesiones
    return ContactLevel.UNKNOWN
