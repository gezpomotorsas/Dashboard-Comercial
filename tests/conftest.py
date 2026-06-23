"""Fixtures compartidas de pruebas."""

import os

import pytest

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test_key_value_here")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_VERSION", "0.1.0")


def _default_hubspot_config_store():
    from app.services.hubspot_configuration.store import HubSpotConfigStore

    return HubSpotConfigStore.from_fixtures(
        pipelines={
            "default": {"pipeline_id": "default", "label": "Shacman", "archived": False},
            "1000390393": {"pipeline_id": "1000390393", "label": "Voyah", "archived": False},
            "1963395799": {"pipeline_id": "1963395799", "label": "MHero", "archived": False},
            "1001269971": {"pipeline_id": "1001269971", "label": "Otro", "archived": False},
        },
        business_dimensions=[
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "default",
                "normalized_value": "shacman",
                "display_label": "Shacman",
                "is_active": True,
                "priority": 10,
            },
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "1000390393",
                "normalized_value": "voyah",
                "display_label": "Voyah",
                "is_active": True,
                "priority": 10,
            },
            {
                "dimension_type": "brand",
                "source_type": "pipeline_id",
                "source_value": "1963395799",
                "normalized_value": "mhero",
                "display_label": "MHero",
                "is_active": True,
                "priority": 10,
            },
            {
                "dimension_type": "brand",
                "source_type": "property_value",
                "source_value": "voyah interés",
                "normalized_value": "voyah",
                "display_label": "Voyah",
                "is_active": True,
                "priority": 10,
            },
        ],
        field_mappings=[
            {
                "object_type": "deals",
                "semantic_key": "deal_amount",
                "hubspot_property_name": "amount",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_stage",
                "hubspot_property_name": "dealstage",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_pipeline",
                "hubspot_property_name": "pipeline",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_close_date",
                "hubspot_property_name": "closedate",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_closed_won",
                "hubspot_property_name": "hs_is_closed_won",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "deals",
                "semantic_key": "deal_closed_lost",
                "hubspot_property_name": "hs_is_closed_lost",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
            {
                "object_type": "contacts",
                "semantic_key": "contact_brand_interest",
                "hubspot_property_name": "marca",
                "is_active": True,
                "priority": 10,
                "validation_status": "valid",
            },
        ],
        properties={
            ("deals", "amount"): {"object_type": "deals", "name": "amount", "options": []},
            ("deals", "dealstage"): {"object_type": "deals", "name": "dealstage", "options": []},
            ("deals", "pipeline"): {"object_type": "deals", "name": "pipeline", "options": []},
            ("deals", "closedate"): {"object_type": "deals", "name": "closedate", "options": []},
            ("deals", "hs_is_closed_won"): {"object_type": "deals", "name": "hs_is_closed_won", "options": []},
            ("deals", "hs_is_closed_lost"): {"object_type": "deals", "name": "hs_is_closed_lost", "options": []},
            ("contacts", "marca"): {"object_type": "contacts", "name": "marca", "options": []},
        },
        stages={
            ("default", "closedwon"): {
                "pipeline_id": "default",
                "stage_id": "closedwon",
                "metadata": {"isClosed": "true", "probability": "1.0"},
            },
            ("default", "closedlost"): {
                "pipeline_id": "default",
                "stage_id": "closedlost",
                "metadata": {"isClosed": "true", "probability": "0.0"},
            },
        },
    )


@pytest.fixture(autouse=True)
def hubspot_config_store(monkeypatch):
    from app.services.hubspot_configuration import set_hubspot_config

    store = _default_hubspot_config_store()
    set_hubspot_config(store)
    return store
