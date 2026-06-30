"""Diagnóstico de configuración HubSpot."""

from __future__ import annotations

from typing import Any

from app.repositories.hubspot_configuration_repository import HubSpotConfigurationRepository
from app.services.hubspot_configuration.store import HubSpotConfigStore


def build_hubspot_mappings_report(store: HubSpotConfigStore, *, latest_refresh: dict[str, Any] | None) -> dict[str, Any]:
    pipelines = [
        {
            "pipeline_id": pid,
            "label": row.get("label"),
            "archived": row.get("archived", False),
        }
        for pid, row in sorted(store.pipelines.items(), key=lambda item: item[1].get("label") or "")
    ]
    stages = [
        {
            "pipeline_id": key[0],
            "stage_id": key[1],
            "label": row.get("label"),
            "archived": row.get("archived", False),
            "normalized_status": store.classify_stage(key[0], key[1])[0],
            "stage_status_source": store.classify_stage(key[0], key[1])[1],
        }
        for key, row in sorted(store.stages.items(), key=lambda item: (item[0][0], item[1].get("display_order") or 0))
    ]
    owners = [
        {
            "hubspot_id": oid,
            "name": store.owner_name(oid),
            "email": row.get("email"),
            "archived": row.get("archived", False),
        }
        for oid, row in sorted(store.owners.items(), key=lambda item: store.owner_name(item[0]) or "")
    ]
    brand_mappings = [
        {
            "source_type": m.get("source_type"),
            "source_value": m.get("source_value"),
            "normalized_value": m.get("normalized_value"),
            "display_label": m.get("display_label"),
            "is_active": m.get("is_active", True),
        }
        for m in store.business_dimensions
        if m.get("dimension_type") == "brand"
    ]
    invalid_mappings = [
        m for m in store.semantic_mapping_snapshot() if m.get("validation_status") == "invalid"
    ]
    return {
        "semantic_fields": store.semantic_mapping_snapshot(),
        "properties_found": len(store.properties),
        "missing_properties": invalid_mappings,
        "pipelines": pipelines,
        "stages": stages,
        "stage_classifications": [
            {
                "pipeline_id": key[0],
                "stage_id": key[1],
                "normalized_status": row.get("normalized_status"),
                "source": row.get("source"),
            }
            for key, row in store.stage_classifications.items()
        ],
        "active_owners": [o for o in owners if not o.get("archived")],
        "archived_owners": [o for o in owners if o.get("archived")],
        "brand_mappings": brand_mappings,
        "invalid_mappings": invalid_mappings,
        "last_refresh_at": (latest_refresh or {}).get("finished_at") or (latest_refresh or {}).get("started_at"),
        "metadata_snapshot_at": store.metadata_snapshot_at,
        "field_mapping_version": store.field_mapping_version,
        "dimension_mapping_version": store.dimension_mapping_version,
    }


def build_hubspot_mapping_issues(store: HubSpotConfigStore) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for mapping in store.semantic_mapping_snapshot():
        if mapping.get("validation_status") == "invalid":
            issues.append(
                {
                    "issue_type": "missing_property",
                    "object_type": mapping["object_type"],
                    "semantic_key": mapping["semantic_key"],
                    "hubspot_property_name": mapping.get("hubspot_property_name"),
                    "message": "Propiedad inexistente en el esquema actual",
                }
            )

    for pipeline_id, row in store.pipelines.items():
        if row.get("archived"):
            continue
        if not store._resolve_dimension("brand", "pipeline_id", pipeline_id):
            issues.append(
                {
                    "issue_type": "pipeline_without_brand",
                    "pipeline_id": pipeline_id,
                    "pipeline_label": row.get("label"),
                    "message": "Pipeline sin mapeo de marca",
                }
            )

    for key, row in store.stages.items():
        if row.get("archived"):
            continue
        status, source = store.classify_stage(key[0], key[1])
        if status == "unknown":
            issues.append(
                {
                    "issue_type": "stage_without_classification",
                    "pipeline_id": key[0],
                    "stage_id": key[1],
                    "stage_label": row.get("label"),
                    "stage_status_source": source,
                    "message": "Etapa sin clasificación open/won/lost",
                }
            )

    for mapping in store.field_mappings:
        if not mapping.get("is_active"):
            continue
        object_type = str(mapping["object_type"])
        prop_name = str(mapping["hubspot_property_name"])
        prop = store.properties.get((object_type, prop_name))
        if not prop:
            continue
        options = prop.get("options") or []
        if isinstance(options, str):
            continue
        for option in options:
            if option.get("hidden"):
                issues.append(
                    {
                        "issue_type": "obsolete_enum_option",
                        "object_type": object_type,
                        "property_name": prop_name,
                        "option_value": option.get("value"),
                        "option_label": option.get("label"),
                        "message": "Opción de enumeración archivada/oculta",
                    }
                )

    return issues


def get_configuration_report() -> dict[str, Any]:
    repo = HubSpotConfigurationRepository()
    store = HubSpotConfigStore.load(repo)
    latest = repo.latest_refresh_run()
    return build_hubspot_mappings_report(store, latest_refresh=latest)


def get_configuration_issues() -> list[dict[str, Any]]:
    store = HubSpotConfigStore.load()
    return build_hubspot_mapping_issues(store)
