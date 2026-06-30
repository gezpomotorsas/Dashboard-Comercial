"""Constantes para sincronización y exposición de actividades HubSpot."""

from typing import Final

# Orden de sincronización (prioridad comercial)
ACTIVITY_SYNC_ORDER: Final[tuple[str, ...]] = (
    "calls",
    "emails",
    "communications",
    "meetings",
    "tasks",
    "notes",
)

ACTIVITY_TABLE_MAP: Final[dict[str, str]] = {
    "calls": "hubspot_calls",
    "meetings": "hubspot_meetings",
    "tasks": "hubspot_tasks",
    "emails": "hubspot_emails",
    "communications": "hubspot_communications",
    "notes": "hubspot_notes",
}

# Propiedades mínimas por tipo (sync ventana / incremental)
ACTIVITY_SYNC_PROPERTIES: Final[dict[str, tuple[str, ...]]] = {
    "calls": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_call_title",
        "hs_call_status",
        "hs_call_outcome",
        "hs_call_direction",
        "hs_call_duration",
        "hs_call_body",
    ),
    "emails": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_email_subject",
        "hs_email_direction",
        "hs_email_status",
        "hs_email_text",
    ),
    "communications": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_communication_channel_type",
        "hs_communication_body",
    ),
    "meetings": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_meeting_title",
        "hs_meeting_start_time",
        "hs_meeting_end_time",
        "hs_meeting_outcome",
        "hs_meeting_body",
    ),
    "tasks": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_task_subject",
        "hs_task_status",
        "hs_task_type",
        "hs_task_priority",
        "hs_task_due_date",
    ),
    "notes": (
        "hs_timestamp",
        "hubspot_owner_id",
        "hs_note_body",
    ),
}

# Contenido sensible: no exponer en listados por defecto ni en logs
SENSITIVE_ACTIVITY_PROPERTY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "hs_call_body",
        "hs_email_text",
        "hs_email_html",
        "hs_communication_body",
        "hs_note_body",
        "hs_meeting_body",
        "hs_task_body",
    }
)

ASSOCIATION_ACTIVITY_TYPES: Final[tuple[str, ...]] = (
    "calls",
    "meetings",
    "tasks",
    "emails",
    "communications",
    "notes",
)
