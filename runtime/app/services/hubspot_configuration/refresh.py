"""Refresco de metadata HubSpot y validación de mapeos."""

from __future__ import annotations

import logging
from typing import Any

from app.clients.hubspot import HubSpotClient
from app.repositories.hubspot_configuration_repository import HubSpotConfigurationRepository
from app.repositories.supabase_repository import SupabaseRepository
from app.services import metadata_service
from app.services.hubspot_configuration import get_hubspot_config, invalidate_hubspot_config
from app.utils.dates import utc_now

logger = logging.getLogger(__name__)


class HubSpotMetadataRefreshService:
    def __init__(
        self,
        *,
        hubspot_client: HubSpotClient,
        supabase_repository: SupabaseRepository | None = None,
        config_repository: HubSpotConfigurationRepository | None = None,
    ) -> None:
        self._hubspot = hubspot_client
        self._supabase = supabase_repository or SupabaseRepository()
        self._config_repo = config_repository or HubSpotConfigurationRepository()

    async def refresh_hubspot_metadata(self) -> dict[str, Any]:
        run = self._config_repo.create_refresh_run()
        run_id = str(run["id"])
        field_version, dimension_version = self._config_repo.next_mapping_versions()
        try:
            contact_props = await metadata_service.get_contact_properties(self._hubspot)
            deal_props = await metadata_service.get_deal_properties(self._hubspot)
            owners = await metadata_service.get_owners(self._hubspot)
            pipelines = await metadata_service.get_deal_pipelines(self._hubspot)
            association_labels = await metadata_service.get_association_labels(self._hubspot)

            self._supabase.upsert_properties("contacts", [p.model_dump(by_alias=True) for p in contact_props])
            self._supabase.upsert_properties("deals", [p.model_dump(by_alias=True) for p in deal_props])
            self._supabase.upsert_owners([o.model_dump(by_alias=True) for o in owners])
            self._supabase.upsert_pipelines([p.model_dump(by_alias=True) for p in pipelines])

            association_rows: list[dict[str, Any]] = []
            for label in association_labels:
                association_rows.append(
                    {
                        "from_object_type": label.from_object_type or "unknown",
                        "to_object_type": label.to_object_type or "unknown",
                        "association_type_id": str(label.type_id) if label.type_id is not None else None,
                        "association_category": label.category,
                        "association_label": label.label,
                        "raw_payload": label.model_dump(by_alias=True),
                    }
                )
            self._config_repo.upsert_association_types(association_rows)

            invalidate_hubspot_config()
            store = get_hubspot_config(refresh=True)
            validated, invalidated = store.validate_field_mappings()
            for mapping in store.field_mappings:
                if not mapping.get("id"):
                    continue
                self._config_repo.update_field_mapping_validation(
                    str(mapping["id"]),
                    validation_status=str(mapping.get("validation_status") or "pending"),
                    hubspot_property_label=mapping.get("hubspot_property_label"),
                )

            finished = utc_now().isoformat()
            status = "completed_with_errors" if invalidated else "completed"
            result = self._config_repo.update_refresh_run(
                run_id,
                {
                    "status": status,
                    "finished_at": finished,
                    "properties_synced": len(contact_props) + len(deal_props),
                    "pipelines_synced": len(pipelines),
                    "stages_synced": sum(len(p.stages or []) for p in pipelines),
                    "owners_synced": len(owners),
                    "association_types_synced": len(association_rows),
                    "mappings_validated": validated,
                    "mappings_invalidated": invalidated,
                    "field_mapping_version": field_version,
                    "dimension_mapping_version": dimension_version,
                    "metadata": {
                        "metadata_snapshot_at": finished,
                    },
                },
            )
            invalidate_hubspot_config()
            return result
        except Exception as exc:
            logger.exception("Refresh de metadata HubSpot fallido")
            self._config_repo.update_refresh_run(
                run_id,
                {
                    "status": "failed",
                    "finished_at": utc_now().isoformat(),
                    "error_message": str(exc),
                },
            )
            raise
