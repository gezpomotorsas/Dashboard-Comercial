"""Configuración centralizada de relaciones de asociación HubSpot."""

from typing import TypedDict

ACTIVITY_OBJECT_TYPES: tuple[str, ...] = (
    "calls",
    "meetings",
    "tasks",
    "emails",
    "communications",
    "notes",
)

SYNC_GROUPS = ("contact-deal", "contact-activities", "deal-activities", "all")


class AssociationPair(TypedDict):
    from_type: str
    to_type: str
    sync_group: str


# Dirección normalizada: from → to (no invertir arbitrariamente)
ASSOCIATION_PAIRS: list[AssociationPair] = [
    {"from_type": "contacts", "to_type": "deals", "sync_group": "contact-deal"},
    *[
        {"from_type": "contacts", "to_type": activity, "sync_group": "contact-activities"}
        for activity in ACTIVITY_OBJECT_TYPES
    ],
    *[
        {"from_type": "deals", "to_type": activity, "sync_group": "deal-activities"}
        for activity in ACTIVITY_OBJECT_TYPES
    ],
]

SYNC_GROUP_PAIRS: dict[str, list[AssociationPair]] = {
    "contact-deal": [p for p in ASSOCIATION_PAIRS if p["sync_group"] == "contact-deal"],
    "contact-activities": [p for p in ASSOCIATION_PAIRS if p["sync_group"] == "contact-activities"],
    "deal-activities": [p for p in ASSOCIATION_PAIRS if p["sync_group"] == "deal-activities"],
    "all": list(ASSOCIATION_PAIRS),
}

SOURCE_OBJECT_TYPES_BY_GROUP: dict[str, tuple[str, ...]] = {
    "contact-deal": ("contacts",),
    "contact-activities": ("contacts",),
    "deal-activities": ("deals",),
    "all": ("contacts", "deals"),
}

HUBSPOT_BATCH_ASSOCIATION_LIMIT = 100
