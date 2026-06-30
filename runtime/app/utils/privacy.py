"""Redacción de contenido sensible en respuestas y mensajes."""

from typing import Any

from app.constants.activities import SENSITIVE_ACTIVITY_PROPERTY_KEYS

REDACTED = "[REDACTED]"


def redact_activity_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    if not properties:
        return {}
    return {
        key: (REDACTED if key in SENSITIVE_ACTIVITY_PROPERTY_KEYS else value)
        for key, value in properties.items()
    }


def redact_hubspot_object(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    props = out.get("properties")
    if isinstance(props, dict):
        out["properties"] = redact_activity_properties(props)
    return out


def safe_error_message(message: str, *, max_len: int = 500) -> str:
    """Recorta mensajes de error; no intenta parsear PII embebida."""
    text = message.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text
