"""Inferencia de marca para contactos vía configuración dinámica."""

import re
from typing import Any

from app.services.hubspot_configuration import get_hubspot_config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(EMAIL_RE.match(value.strip()))


def infer_contact_brand(
    properties: dict[str, Any],
    *,
    deal_pipeline_id: str | None = None,
) -> str | None:
    return get_hubspot_config().infer_contact_brand(properties, deal_pipeline_id=deal_pipeline_id)
