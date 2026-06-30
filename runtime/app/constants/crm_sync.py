"""Propiedades mínimas para sincronización CRM (deals/contacts)."""

from typing import Final

DEAL_SYNC_PROPERTIES: Final[tuple[str, ...]] = (
    "dealname",
    "amount",
    "pipeline",
    "dealstage",
    "closedate",
    "createdate",
    "hubspot_owner_id",
    "hs_lastmodifieddate",
    "hs_object_id",
    "hs_is_closed_won",
    "hs_is_closed_lost",
    "marca",
    "modelo_solicitado",
    "zona",
    "ciudad",
    "departamento",
)

CONTACT_SYNC_PROPERTIES: Final[tuple[str, ...]] = (
    "firstname",
    "lastname",
    "email",
    "phone",
    "hubspot_owner_id",
    "hs_lastmodifieddate",
    "hs_object_id",
    "city",
    "ciudad",
    "marca",
    "marca_de_interes",
    "modelo_solicitado",
    "hs_analytics_source",
    "origen",
)

CRM_SYNC_PROPERTIES: Final[dict[str, tuple[str, ...]]] = {
    "deals": DEAL_SYNC_PROPERTIES,
    "contacts": CONTACT_SYNC_PROPERTIES,
}

# HubSpot Search API: deals exige hs_lastmodifieddate; contacts acepta lastmodifieddate.
CRM_MODIFIED_DATE_PROPERTY: Final[dict[str, str]] = {
    "deals": "hs_lastmodifieddate",
    "contacts": "lastmodifieddate",
}
