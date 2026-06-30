"""Store de configuración HubSpot cargada desde Supabase."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from app.repositories.hubspot_configuration_repository import HubSpotConfigurationRepository
from app.utils.dates import utc_now

logger = logging.getLogger(__name__)

NormalizedStatus = Literal["open", "won", "lost", "unknown"]
ValidationStatus = Literal["pending", "valid", "invalid"]


def _is_truthy(value: Any) -> bool:
    return value in (True, "true", "True", "1", 1)


def _normalize_key(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().lower()


@dataclass
class HubSpotConfigStore:
    properties: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    field_mappings: list[dict[str, Any]] = field(default_factory=list)
    stage_classifications: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    stages: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    pipelines: dict[str, dict[str, Any]] = field(default_factory=dict)
    owners: dict[str, dict[str, Any]] = field(default_factory=dict)
    business_dimensions: list[dict[str, Any]] = field(default_factory=list)
    association_types: list[dict[str, Any]] = field(default_factory=list)
    metadata_snapshot_at: str | None = None
    field_mapping_version: int = 1
    dimension_mapping_version: int = 1
    metadata_version: str | None = None

    @classmethod
    def load(cls, repository: HubSpotConfigurationRepository | None = None) -> HubSpotConfigStore:
        repo = repository or HubSpotConfigurationRepository()
        store = cls()
        try:
            for row in repo.fetch_all("hubspot_properties"):
                key = (str(row["object_type"]), str(row["name"]))
                store.properties[key] = row
            store.field_mappings = repo.fetch_all("hubspot_field_mappings")
            for row in repo.fetch_all("hubspot_stage_classifications"):
                store.stage_classifications[(str(row["pipeline_id"]), str(row["stage_id"]))] = row
            for row in repo.fetch_all("hubspot_pipeline_stages"):
                store.stages[(str(row["pipeline_id"]), str(row["stage_id"]))] = row
            for row in repo.fetch_all("hubspot_pipelines"):
                store.pipelines[str(row["pipeline_id"])] = row
            for row in repo.fetch_all("hubspot_owners"):
                store.owners[str(row["hubspot_id"])] = row
            store.business_dimensions = repo.fetch_all("business_dimension_mappings")
            store.association_types = repo.fetch_all("hubspot_association_types")
            latest = repo.latest_refresh_run()
            if latest and latest.get("status") in ("completed", "completed_with_errors"):
                store.metadata_snapshot_at = latest.get("finished_at") or latest.get("started_at")
                store.field_mapping_version = int(latest.get("field_mapping_version") or 1)
                store.dimension_mapping_version = int(latest.get("dimension_mapping_version") or 1)
                store.metadata_version = str(latest.get("id"))
        except Exception:
            logger.warning("No se pudo cargar configuración HubSpot desde Supabase; usando store vacío")
        return store

    @classmethod
    def from_fixtures(
        cls,
        *,
        pipelines: dict[str, dict[str, Any]] | None = None,
        stages: dict[tuple[str, str], dict[str, Any]] | None = None,
        business_dimensions: list[dict[str, Any]] | None = None,
        field_mappings: list[dict[str, Any]] | None = None,
        properties: dict[tuple[str, str], dict[str, Any]] | None = None,
        stage_classifications: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> HubSpotConfigStore:
        store = cls()
        store.pipelines = pipelines or {}
        store.stages = stages or {}
        store.business_dimensions = business_dimensions or []
        store.field_mappings = field_mappings or []
        store.properties = properties or {}
        store.stage_classifications = stage_classifications or {}
        store.metadata_snapshot_at = utc_now().isoformat()
        return store

    @property
    def known_pipeline_ids(self) -> set[str]:
        return {pid for pid, row in self.pipelines.items() if not row.get("archived")}

    def active_field_mappings(self, object_type: str, semantic_key: str) -> list[dict[str, Any]]:
        rows = [
            m
            for m in self.field_mappings
            if m.get("is_active")
            and m.get("object_type") == object_type
            and m.get("semantic_key") == semantic_key
            and m.get("validation_status") != "invalid"
        ]
        return sorted(rows, key=lambda m: int(m.get("priority") or 100))

    def resolve_property_name(self, object_type: str, semantic_key: str) -> tuple[str | None, ValidationStatus]:
        for mapping in self.active_field_mappings(object_type, semantic_key):
            prop_name = str(mapping["hubspot_property_name"])
            if (object_type, prop_name) in self.properties:
                return prop_name, "valid"
            if mapping.get("validation_status") == "valid":
                return prop_name, "valid"
        for mapping in self.active_field_mappings(object_type, semantic_key):
            return str(mapping["hubspot_property_name"]), "invalid"
        return None, "invalid"

    def get_property_value(self, row: dict[str, Any], object_type: str, semantic_key: str) -> Any:
        prop_name, status = self.resolve_property_name(object_type, semantic_key)
        if not prop_name or status == "invalid":
            return None
        props = row.get("properties") or {}
        return props.get(prop_name)

    def option_label(self, object_type: str, property_name: str, value: Any) -> str | None:
        prop = self.properties.get((object_type, property_name))
        if not prop:
            return None
        options = prop.get("options") or []
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except json.JSONDecodeError:
                options = []
        value_str = str(value)
        for option in options:
            if str(option.get("value")) == value_str:
                return option.get("label") or value_str
        return None

    def _resolve_dimension(
        self,
        dimension_type: str,
        source_type: str,
        source_value: str | None,
    ) -> str | None:
        if source_value in (None, ""):
            return None
        candidates = [
            m
            for m in self.business_dimensions
            if m.get("is_active")
            and m.get("dimension_type") == dimension_type
            and m.get("source_type") == source_type
            and str(m.get("source_value")) == str(source_value)
        ]
        if not candidates:
            return None
        best = sorted(candidates, key=lambda m: int(m.get("priority") or 100))[0]
        return str(best["normalized_value"])

    def _resolve_dimension_from_text(self, dimension_type: str, text: str | None) -> str | None:
        normalized = _normalize_key(text)
        if not normalized:
            return None
        for mapping in sorted(
            [m for m in self.business_dimensions if m.get("is_active") and m.get("dimension_type") == dimension_type],
            key=lambda m: int(m.get("priority") or 100),
        ):
            if mapping.get("source_type") != "property_value":
                continue
            if _normalize_key(str(mapping.get("source_value"))) == normalized:
                return str(mapping["normalized_value"])
            if _normalize_key(str(mapping.get("display_label"))) == normalized:
                return str(mapping["normalized_value"])
        return None

    def _deal_pipeline_id(self, deal: dict[str, Any]) -> str | None:
        pipeline = deal.get("pipeline_id") or self.get_property_value(deal, "deals", "deal_pipeline")
        if pipeline in (None, ""):
            pipeline = (deal.get("properties") or {}).get("pipeline")
        return str(pipeline) if pipeline not in (None, "") else None

    def _resolve_brand_from_semantic(self, row: dict[str, Any], object_type: str, semantic_key: str) -> str | None:
        for mapping in self.active_field_mappings(object_type, semantic_key):
            prop_name = str(mapping["hubspot_property_name"])
            if mapping.get("validation_status") == "invalid":
                continue
            if (object_type, prop_name) not in self.properties and mapping.get("validation_status") != "valid":
                continue
            value = (row.get("properties") or {}).get(prop_name)
            if value in (None, ""):
                continue
            mapped = self._resolve_dimension_from_text("brand", str(value))
            if mapped:
                return mapped
            label = self.option_label(object_type, prop_name, value)
            if label:
                mapped = self._resolve_dimension_from_text("brand", label)
                if mapped:
                    return mapped
        return None

    def resolve_deal_brand(self, deal: dict[str, Any]) -> tuple[str, str]:
        explicit = self._resolve_brand_from_semantic(deal, "deals", "deal_brand")
        if explicit:
            return explicit, "deal_property"
        model_brand = self._resolve_brand_from_semantic(deal, "deals", "deal_model")
        if model_brand:
            return model_brand, "deal_model"
        pipeline_id = self._deal_pipeline_id(deal)
        mapped = self._resolve_dimension("brand", "pipeline_id", pipeline_id)
        if mapped:
            return mapped, "pipeline_mapping"
        stored = deal.get("brand")
        if stored:
            return str(stored), "stored"
        return "unknown", "unavailable"

    def infer_contact_brand(
        self,
        properties: dict[str, Any],
        *,
        deal_pipeline_id: str | None = None,
    ) -> str | None:
        row = {"properties": properties}
        for semantic in ("contact_brand_interest", "contact_model_interest"):
            brand = self._resolve_brand_from_semantic(row, "contacts", semantic)
            if brand:
                return brand
        if deal_pipeline_id:
            mapped = self._resolve_dimension("brand", "pipeline_id", deal_pipeline_id)
            if mapped:
                return mapped
        return None

    def classify_stage(
        self,
        pipeline_id: str | None,
        stage_id: str | None,
    ) -> tuple[NormalizedStatus, str]:
        if not pipeline_id or not stage_id:
            return "unknown", "unavailable"
        stage = self.stages.get((str(pipeline_id), str(stage_id)))
        if stage:
            status = self._status_from_hubspot_metadata(stage.get("metadata"))
            if status != "unknown":
                return status, "hubspot_metadata"
        classification = self.stage_classifications.get((str(pipeline_id), str(stage_id)))
        if classification and classification.get("is_active"):
            return classification["normalized_status"], "database"  # type: ignore[return-value]
        return "unknown", "unavailable"

    def resolve_deal_status(self, deal: dict[str, Any]) -> tuple[NormalizedStatus, str]:
        """Prioridad: metadata etapa → propiedades estándar HubSpot → DB → unknown."""
        pipeline_id = self._deal_pipeline_id(deal)
        stage_id = deal.get("dealstage_id") or self.get_property_value(deal, "deals", "deal_stage")
        stage_status, stage_source = self.classify_stage(
            pipeline_id,
            str(stage_id) if stage_id else None,
        )
        if stage_status in ("open", "won", "lost"):
            return stage_status, stage_source

        if _is_truthy(self.get_property_value(deal, "deals", "deal_closed_won")):
            return "won", "hubspot_property"
        if _is_truthy(self.get_property_value(deal, "deals", "deal_closed_lost")):
            return "lost", "hubspot_property"

        closed_prop = self.get_property_value(deal, "deals", "deal_closed")
        if _is_truthy(closed_prop):
            if _is_truthy(self.get_property_value(deal, "deals", "deal_closed_won")):
                return "won", "hubspot_property"
            if _is_truthy(self.get_property_value(deal, "deals", "deal_closed_lost")):
                return "lost", "hubspot_property"

        if stage_status == "unknown" and stage_source == "database":
            return stage_status, stage_source

        classification = self.stage_classifications.get(
            (str(pipeline_id), str(stage_id)) if pipeline_id and stage_id else ("", "")
        )
        if classification and classification.get("is_active"):
            return classification["normalized_status"], "database"  # type: ignore[return-value]

        return "unknown", "unavailable"

    def resolve_semantic_dimension(
        self,
        deal: dict[str, Any],
        dimension_type: str,
        semantic_keys: tuple[str, ...],
    ) -> tuple[str | None, str | None]:
        """Retorna (normalized_value, display_label)."""
        for semantic in semantic_keys:
            for mapping in self.active_field_mappings("deals", semantic):
                prop_name = str(mapping["hubspot_property_name"])
                if mapping.get("validation_status") == "invalid":
                    continue
                value = (deal.get("properties") or {}).get(prop_name)
                if value in (None, ""):
                    continue
                mapped = self._resolve_dimension_from_text(dimension_type, str(value))
                if mapped:
                    label = self.option_label("deals", prop_name, value) or str(value)
                    for m in self.business_dimensions:
                        if (
                            m.get("dimension_type") == dimension_type
                            and str(m.get("normalized_value")) == mapped
                        ):
                            label = str(m.get("display_label") or label)
                    return mapped, label
                label = self.option_label("deals", prop_name, value) or str(value)
                return str(value).strip().lower(), label
        return None, None

    def dimension_label(self, dimension_type: str, normalized_value: str | None) -> str | None:
        if not normalized_value:
            return None
        for mapping in self.business_dimensions:
            if (
                mapping.get("dimension_type") == dimension_type
                and str(mapping.get("normalized_value")) == normalized_value
            ):
                return str(mapping.get("display_label") or normalized_value)
        if dimension_type == "brand":
            return self.brand_label(normalized_value)
        return normalized_value.replace("_", " ").title()

    @staticmethod
    def _status_from_hubspot_metadata(metadata: Any) -> NormalizedStatus:
        if not metadata:
            return "unknown"
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                return "unknown"
        if not isinstance(metadata, dict):
            return "unknown"
        is_closed = str(metadata.get("isClosed", "")).lower() == "true"
        if not is_closed:
            return "open"
        probability = metadata.get("probability")
        if probability is not None:
            try:
                p = float(probability)
                if p >= 1.0:
                    return "won"
                if p <= 0.0:
                    return "lost"
            except (TypeError, ValueError):
                pass
        return "unknown"

    def is_deal_won(self, deal: dict[str, Any]) -> bool:
        return self.resolve_deal_status(deal)[0] == "won"

    def is_deal_lost(self, deal: dict[str, Any]) -> bool:
        return self.resolve_deal_status(deal)[0] == "lost"

    def list_brand_filters(self) -> list[tuple[str, str]]:
        brands: dict[str, str] = {}
        for mapping in self.business_dimensions:
            if not mapping.get("is_active") or mapping.get("dimension_type") != "brand":
                continue
            normalized = str(mapping["normalized_value"])
            label = str(mapping.get("display_label") or normalized.title())
            brands.setdefault(normalized, label)
        ordered = sorted(brands.items(), key=lambda item: item[1].lower())
        ordered.append(("unknown", "Unknown"))
        return ordered

    def brand_label(self, brand: str) -> str:
        for mapping in self.business_dimensions:
            if mapping.get("dimension_type") == "brand" and str(mapping.get("normalized_value")) == brand:
                return str(mapping.get("display_label") or brand.title())
        if brand == "unknown":
            return "Unknown"
        return brand.title()

    def resolve_deal_zone(
        self,
        deal: dict[str, Any],
        *,
        contacts: list[dict[str, Any]] | None = None,
        owner_id: str | None = None,
    ) -> tuple[str, str, str | None, str | None]:
        """Prioridad: zona explícita → ciudad/depto negocio → contacto → owner → unknown."""
        zone_value, zone_label = self.resolve_semantic_dimension(deal, "zone", ("deal_zone",))
        city_value, city_label = self.resolve_semantic_dimension(deal, "city", ("deal_city",))
        dept_value, dept_label = self.resolve_semantic_dimension(
            deal, "department", ("deal_department",)
        )

        if zone_value:
            label = self.dimension_label("zone", zone_value) or zone_label or zone_value
            return zone_value, label, city_value or city_label, dept_value or dept_label

        for candidate in (city_value, city_label, dept_value, dept_label):
            mapped = self._resolve_dimension_from_text("zone", candidate)
            if mapped:
                return mapped, self.dimension_label("zone", mapped) or mapped, city_value, dept_value

        for contact in contacts or []:
            props = contact.get("properties") or {}
            row = {"properties": props}
            contact_city, contact_city_label = self.resolve_semantic_dimension(
                row, "city", ("contact_city",)
            )
            for candidate in (contact_city, contact_city_label):
                mapped = self._resolve_dimension_from_text("zone", candidate)
                if mapped:
                    return (
                        mapped,
                        self.dimension_label("zone", mapped) or mapped,
                        contact_city or contact_city_label,
                        dept_value,
                    )

        if owner_id:
            owner = self.owners.get(str(owner_id))
            if owner:
                for field in ("team", "teams", "region", "zona"):
                    team_val = owner.get(field)
                    if team_val:
                        mapped = self._resolve_dimension_from_text("zone", str(team_val))
                        if mapped:
                            return (
                                mapped,
                                self.dimension_label("zone", mapped) or mapped,
                                city_value,
                                dept_value,
                            )
                        normalized = str(team_val).strip().lower()
                        return normalized, str(team_val), city_value, dept_value

        return "unknown", "Unknown", city_value or city_label, dept_value or dept_label

    def list_zone_filters(self, rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
        zones: dict[str, str] = {}
        for row in rows:
            value = str(row.get("zone_value") or "unknown")
            label = str(row.get("zone_label") or value)
            zones.setdefault(value, label)
        ordered = sorted(zones.items(), key=lambda item: item[1].lower())
        if ("unknown", "Unknown") not in ordered:
            ordered.append(("unknown", "Unknown"))
        return ordered

    def is_task_completed(self, status: str | None) -> bool:
        if not status:
            return False
        normalized = str(status).strip().upper()
        return normalized in {"COMPLETED", "COMPLETE", "DONE", "FINISHED"}

    def is_call_effective(self, properties: dict[str, Any]) -> bool:
        status = str(properties.get("hs_call_status") or "").upper()
        outcome = str(properties.get("hs_call_outcome") or "").upper()
        if status in {"COMPLETED", "COMPLETE"}:
            return True
        return bool(outcome and outcome not in {"NO_ANSWER", "BUSY", "FAILED", "CANCELED", "CANCELLED"})

    def pipeline_label(self, pipeline_id: str | None) -> str | None:
        if not pipeline_id:
            return None
        row = self.pipelines.get(str(pipeline_id))
        return row.get("label") if row else None

    def stage_label(self, pipeline_id: str | None, stage_id: str | None) -> str | None:
        if not pipeline_id or not stage_id:
            return None
        row = self.stages.get((str(pipeline_id), str(stage_id)))
        return row.get("label") if row else None

    def owner_name(self, owner_id: str | None) -> str | None:
        if not owner_id:
            return None
        owner = self.owners.get(str(owner_id))
        if not owner:
            return None
        name = " ".join(p for p in (owner.get("first_name"), owner.get("last_name")) if p).strip()
        return name or owner.get("email")

    def validate_field_mappings(self) -> tuple[int, int]:
        validated = 0
        invalidated = 0
        for mapping in self.field_mappings:
            if not mapping.get("is_active"):
                continue
            object_type = str(mapping["object_type"])
            prop_name = str(mapping["hubspot_property_name"])
            prop = self.properties.get((object_type, prop_name))
            if prop:
                mapping["validation_status"] = "valid"
                mapping["hubspot_property_label"] = prop.get("label")
                validated += 1
            else:
                mapping["validation_status"] = "invalid"
                invalidated += 1
        return validated, invalidated

    def semantic_mapping_snapshot(self) -> list[dict[str, Any]]:
        keys = sorted({(m["object_type"], m["semantic_key"]) for m in self.field_mappings if m.get("is_active")})
        snapshot: list[dict[str, Any]] = []
        for object_type, semantic_key in keys:
            prop_name, status = self.resolve_property_name(str(object_type), str(semantic_key))
            snapshot.append(
                {
                    "object_type": object_type,
                    "semantic_key": semantic_key,
                    "hubspot_property_name": prop_name,
                    "validation_status": status,
                }
            )
        return snapshot
