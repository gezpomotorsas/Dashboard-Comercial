"""Reglas de calidad para contactos."""

from collections.abc import Iterator
from typing import Any

from app.config import CONTACT_SOURCE_PROPERTY_CANDIDATES
from app.services.data_quality.brand_inference import infer_contact_brand, is_valid_email


def evaluate_contacts(
    rows: list[dict[str, Any]],
    *,
    contact_deal_map: dict[str, set[str]],
    deal_pipeline_map: dict[str, str | None],
) -> Iterator[dict[str, Any]]:
    for row in rows:
        hid = row.get("hubspot_id")
        props = row.get("properties") or {}
        if not props.get("hubspot_owner_id"):
            yield _finding("CONTACT_WITHOUT_OWNER", hid, "warning", "missing_owner", "Sin propietario")
        email = props.get("email")
        phone = props.get("phone") or props.get("mobilephone")
        if not email and not phone:
            yield _finding(
                "CONTACT_WITHOUT_EMAIL_AND_PHONE",
                hid,
                "critical",
                "no_contact_channel",
                "Sin email ni teléfono",
            )
        if not props.get("lifecyclestage"):
            yield _finding(
                "CONTACT_WITHOUT_LIFECYCLE_STAGE",
                hid,
                "info",
                "missing_lifecycle",
                "Sin lifecyclestage",
            )
        if not any(props.get(p) for p in CONTACT_SOURCE_PROPERTY_CANDIDATES):
            yield _finding("CONTACT_WITHOUT_SOURCE", hid, "info", "missing_source", "Sin fuente")
        deal_ids = contact_deal_map.get(str(hid), set())
        deal_pipeline = None
        if deal_ids:
            deal_pipeline = deal_pipeline_map.get(next(iter(deal_ids)))
        brand = infer_contact_brand(props, deal_pipeline_id=deal_pipeline)
        if brand is None:
            yield _finding("CONTACT_WITHOUT_BRAND", hid, "warning", "missing_brand", "Marca no inferible")
        if email and not is_valid_email(str(email)):
            yield _finding(
                "CONTACT_WITH_INVALID_EMAIL",
                hid,
                "warning",
                "invalid_email",
                "Email con formato inválido",
            )
        if not props.get("firstname") and not props.get("lastname"):
            yield _finding("CONTACT_WITHOUT_NAME", hid, "info", "missing_name", "Sin nombre")
        if not deal_ids:
            yield _finding("CONTACT_WITHOUT_DEAL", hid, "info", "no_deal", "Sin negocio asociado")


def _finding(code: str, hubspot_id: Any, severity: str, issue_key: str, message: str) -> dict[str, Any]:
    return {
        "rule_code": code,
        "object_type": "contacts",
        "hubspot_id": str(hubspot_id) if hubspot_id else None,
        "severity": severity,
        "issue_key": issue_key,
        "message": message,
        "details": {},
    }
