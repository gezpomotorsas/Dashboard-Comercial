"""Reglas de calidad para actividades y asociaciones."""

from collections.abc import Iterator
from typing import Any

ACTIVITY_TABLES = {
    "calls": "hubspot_calls",
    "meetings": "hubspot_meetings",
    "tasks": "hubspot_tasks",
    "emails": "hubspot_emails",
    "communications": "hubspot_communications",
    "notes": "hubspot_notes",
}


def evaluate_activities(
    rows: list[dict[str, Any]],
    *,
    activity_type: str,
    linked_ids: set[str],
) -> Iterator[dict[str, Any]]:
    for row in rows:
        hid = str(row.get("hubspot_id"))
        props = row.get("properties") or {}
        if hid not in linked_ids:
            yield {
                "rule_code": "ACTIVITY_WITHOUT_CONTACT_OR_DEAL",
                "object_type": "activities",
                "hubspot_id": hid,
                "severity": "warning",
                "issue_key": f"orphan:{activity_type}",
                "message": "Actividad sin contacto ni negocio",
                "details": {"activity_type": activity_type},
            }
        if not props.get("hubspot_owner_id"):
            yield {
                "rule_code": "ACTIVITY_WITHOUT_OWNER",
                "object_type": "activities",
                "hubspot_id": hid,
                "severity": "info",
                "issue_key": "missing_owner",
                "message": "Sin propietario",
                "details": {"activity_type": activity_type},
            }
        if not props.get("hs_timestamp"):
            yield {
                "rule_code": "ACTIVITY_WITHOUT_TIMESTAMP",
                "object_type": "activities",
                "hubspot_id": hid,
                "severity": "warning",
                "issue_key": "missing_timestamp",
                "message": "Sin hs_timestamp",
                "details": {"activity_type": activity_type},
            }


def evaluate_broken_associations(
    rows: list[dict[str, Any]],
    *,
    existing_ids_by_type: dict[str, set[str]],
) -> Iterator[dict[str, Any]]:
    for row in rows:
        if not row.get("is_active", True):
            continue
        from_type = row["from_object_type"]
        from_id = row["from_hubspot_id"]
        to_type = row["to_object_type"]
        to_id = row["to_hubspot_id"]
        missing = []
        if from_id not in existing_ids_by_type.get(from_type, set()):
            missing.append(f"from:{from_type}:{from_id}")
        if to_id not in existing_ids_by_type.get(to_type, set()):
            missing.append(f"to:{to_type}:{to_id}")
        if missing:
            yield {
                "rule_code": "ASSOCIATION_REFERENCES_MISSING_OBJECT",
                "object_type": "associations",
                "hubspot_id": from_id,
                "severity": "critical",
                "issue_key": f"missing:{'|'.join(missing)}",
                "message": "Asociación referencia objeto inexistente localmente",
                "details": {"missing": missing},
            }
