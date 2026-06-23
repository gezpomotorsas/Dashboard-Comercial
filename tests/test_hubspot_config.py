"""Pruebas de configuración dinámica HubSpot."""

import os

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.services.hubspot_configuration.diagnostics import build_hubspot_mapping_issues, build_hubspot_mappings_report
from app.services.hubspot_configuration.store import HubSpotConfigStore


def _store_with_renamed_stage() -> HubSpotConfigStore:
    return HubSpotConfigStore.from_fixtures(
        pipelines={"p1": {"pipeline_id": "p1", "label": "Pipeline Renombrado", "archived": False}},
        stages={
            ("p1", "s1"): {
                "pipeline_id": "p1",
                "stage_id": "s1",
                "label": "Etapa Renombrada",
                "metadata": {"isClosed": "false"},
            }
        },
        business_dimensions=[
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "p1",
                "normalized_value": "voyah",
                "display_label": "Voyah",
                "is_active": True,
                "priority": 10,
            }
        ],
        field_mappings=[
            {
                "object_type": "deals",
                "semantic_key": "deal_amount",
                "hubspot_property_name": "amount",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            }
        ],
        properties={("deals", "amount"): {"object_type": "deals", "name": "amount"}},
    )


def test_stage_classification_from_hubspot_metadata():
    store = HubSpotConfigStore.from_fixtures(
        stages={
            ("default", "won"): {"metadata": {"isClosed": "true", "probability": "1.0"}},
            ("default", "lost"): {"metadata": {"isClosed": "true", "probability": "0"}},
            ("default", "open"): {"metadata": {"isClosed": "false"}},
        }
    )
    assert store.classify_stage("default", "won") == ("won", "hubspot_metadata")
    assert store.classify_stage("default", "lost") == ("lost", "hubspot_metadata")
    assert store.classify_stage("default", "open") == ("open", "hubspot_metadata")


def test_stage_classification_database_fallback():
    store = HubSpotConfigStore.from_fixtures(
        stages={("p1", "s1"): {"metadata": {}}},
        stage_classifications={
            ("p1", "s1"): {
                "pipeline_id": "p1",
                "stage_id": "s1",
                "normalized_status": "won",
                "is_active": True,
            }
        },
    )
    assert store.classify_stage("p1", "s1") == ("won", "database")


def test_stage_unknown_without_metadata_or_db():
    store = HubSpotConfigStore.from_fixtures(stages={("p1", "s1"): {"metadata": {}}})
    status, source = store.classify_stage("p1", "s1")
    assert status == "unknown"
    assert source == "unavailable"


def test_brand_from_pipeline_mapping():
    store = HubSpotConfigStore.from_fixtures(
        business_dimensions=[
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "1000390393",
                "normalized_value": "voyah",
                "display_label": "Voyah",
                "is_active": True,
                "priority": 10,
            }
        ]
    )
    brand, source = store.resolve_deal_brand({"properties": {"pipeline": "1000390393"}})
    assert brand == "voyah"
    assert source == "pipeline_mapping"


def test_brand_unknown_when_no_mapping():
    store = HubSpotConfigStore.from_fixtures()
    brand, source = store.resolve_deal_brand({"properties": {"pipeline": "999"}})
    assert brand == "unknown"
    assert source == "unavailable"


def test_invalid_field_mapping_marks_semantic_unavailable():
    store = HubSpotConfigStore.from_fixtures(
        field_mappings=[
            {
                "object_type": "deals",
                "semantic_key": "deal_amount",
                "hubspot_property_name": "missing_amount",
                "is_active": True,
                "priority": 10,
                "validation_status": "invalid",
            }
        ]
    )
    _, status = store.resolve_property_name("deals", "deal_amount")
    assert status == "invalid"


def test_renamed_pipeline_label_from_metadata():
    store = _store_with_renamed_stage()
    assert store.pipeline_label("p1") == "Pipeline Renombrado"
    assert store.stage_label("p1", "s1") == "Etapa Renombrada"


def test_new_pipeline_available_after_metadata_change():
    store_v1 = HubSpotConfigStore.from_fixtures(pipelines={"p1": {"pipeline_id": "p1", "label": "A", "archived": False}})
    store_v2 = HubSpotConfigStore.from_fixtures(
        pipelines={
            "p1": {"pipeline_id": "p1", "label": "A", "archived": False},
            "p2": {"pipeline_id": "p2", "label": "Nuevo Pipeline", "archived": False},
        }
    )
    assert "p2" not in store_v1.known_pipeline_ids
    assert "p2" in store_v2.known_pipeline_ids


def test_diagnostics_detects_pipeline_without_brand():
    store = HubSpotConfigStore.from_fixtures(
        pipelines={"p-new": {"pipeline_id": "p-new", "label": "Sin marca", "archived": False}}
    )
    issues = build_hubspot_mapping_issues(store)
    assert any(i["issue_type"] == "pipeline_without_brand" for i in issues)


def test_diagnostics_report_includes_versions():
    store = HubSpotConfigStore.from_fixtures()
    store.field_mapping_version = 3
    store.dimension_mapping_version = 4
    report = build_hubspot_mappings_report(store, latest_refresh={"finished_at": "2026-01-01T00:00:00Z"})
    assert report["field_mapping_version"] == 3
    assert report["dimension_mapping_version"] == 4
