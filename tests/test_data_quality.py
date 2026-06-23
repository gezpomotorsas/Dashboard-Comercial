"""Pruebas de calidad de datos."""

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.services.data_quality.brand_inference import infer_contact_brand, is_valid_email
from app.services.data_quality.rules.activities import (
    evaluate_activities,
    evaluate_broken_associations,
)
from app.services.data_quality.rules.contacts import evaluate_contacts
from app.services.data_quality.rules.deals import evaluate_deals


def test_contact_without_owner():
    rows = [{"hubspot_id": "1", "properties": {"email": "a@b.com"}}]
    findings = list(evaluate_contacts(rows, contact_deal_map={}, deal_pipeline_map={}))
    codes = {f["rule_code"] for f in findings}
    assert "CONTACT_WITHOUT_OWNER" in codes


def test_contact_without_email_and_phone():
    rows = [{"hubspot_id": "1", "properties": {}}]
    findings = list(evaluate_contacts(rows, contact_deal_map={}, deal_pipeline_map={}))
    assert any(f["rule_code"] == "CONTACT_WITHOUT_EMAIL_AND_PHONE" for f in findings)


def test_contact_without_brand():
    rows = [{"hubspot_id": "1", "properties": {"firstname": "Ana"}}]
    findings = list(evaluate_contacts(rows, contact_deal_map={}, deal_pipeline_map={}))
    assert any(f["rule_code"] == "CONTACT_WITHOUT_BRAND" for f in findings)


def test_infer_brand_from_property():
    brand = infer_contact_brand({"marca": "Voyah interés"})
    assert brand == "voyah"


def test_infer_brand_from_deal_pipeline():
    brand = infer_contact_brand({}, deal_pipeline_id="default")
    assert brand == "shacman"


def test_infer_brand_null_when_unknown():
    assert infer_contact_brand({}) is None


def test_invalid_email():
    assert is_valid_email("not-an-email") is False
    assert is_valid_email("ok@example.com") is True


def test_deal_without_contact():
    rows = [{"hubspot_id": "10", "properties": {"pipeline": "default", "dealstage": "s1"}, "pipeline_id": "default", "dealstage_id": "s1"}]
    findings = list(
        evaluate_deals(
            rows,
            deal_contact_map={},
            deal_activity_map={},
            pipeline_stages={"default": {"s1"}},
        )
    )
    assert any(f["rule_code"] == "DEAL_WITHOUT_CONTACT" for f in findings)


def test_deal_unknown_pipeline(hubspot_config_store):
    unknown = "1001269971"
    assert unknown in hubspot_config_store.known_pipeline_ids
    rows = [
        {
            "hubspot_id": "11",
            "properties": {"pipeline": unknown, "dealstage": "x"},
            "pipeline_id": unknown,
            "dealstage_id": "x",
            "updated_at_hubspot": datetime.now(UTC).isoformat(),
        }
    ]
    findings = list(
        evaluate_deals(
            rows,
            deal_contact_map={"11": True},
            deal_activity_map={"11": True},
            pipeline_stages={unknown: {"x"}},
            config=hubspot_config_store,
        )
    )
    assert not any(f["rule_code"] == "DEAL_WITH_UNKNOWN_PIPELINE" for f in findings)


def test_deal_unknown_pipeline_not_in_hubspot_metadata(hubspot_config_store):
    unknown = "pipeline-inexistente"
    rows = [
        {
            "hubspot_id": "12",
            "properties": {"pipeline": unknown, "dealstage": "x"},
            "pipeline_id": unknown,
            "dealstage_id": "x",
            "updated_at_hubspot": datetime.now(UTC).isoformat(),
        }
    ]
    findings = list(
        evaluate_deals(
            rows,
            deal_contact_map={"12": True},
            deal_activity_map={"12": True},
            pipeline_stages={unknown: {"x"}},
            config=hubspot_config_store,
        )
    )
    assert any(f["rule_code"] == "DEAL_WITH_UNKNOWN_PIPELINE" for f in findings)


def test_deal_stale(monkeypatch):
    monkeypatch.setenv("DATA_QUALITY_STALE_DEAL_DAYS", "30")
    from app.config import get_settings

    get_settings.cache_clear()
    old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    rows = [
        {
            "hubspot_id": "12",
            "properties": {"pipeline": "default", "dealstage": "s1", "amount": "100"},
            "pipeline_id": "default",
            "dealstage_id": "s1",
            "updated_at_hubspot": old,
        }
    ]
    findings = list(
        evaluate_deals(
            rows,
            deal_contact_map={"12": True},
            deal_activity_map={"12": True},
            pipeline_stages={"default": {"s1"}},
        )
    )
    assert any(f["rule_code"] == "DEAL_STALE" for f in findings)
    get_settings.cache_clear()


def test_activity_without_association():
    rows = [{"hubspot_id": "50", "properties": {"hs_timestamp": "2024-01-01"}}]
    findings = list(evaluate_activities(rows, activity_type="calls", linked_ids=set()))
    assert any(f["rule_code"] == "ACTIVITY_WITHOUT_CONTACT_OR_DEAL" for f in findings)


def test_broken_association_reference():
    rows = [
        {
            "from_object_type": "contacts",
            "from_hubspot_id": "999",
            "to_object_type": "deals",
            "to_hubspot_id": "888",
            "is_active": True,
        }
    ]
    existing = {"contacts": set(), "deals": set()}
    findings = list(evaluate_broken_associations(rows, existing_ids_by_type=existing))
    assert any(f["rule_code"] == "ASSOCIATION_REFERENCES_MISSING_OBJECT" for f in findings)


def test_finding_fingerprint_unique_keys():
    rows = [{"hubspot_id": "1", "properties": {}}]
    f1 = list(evaluate_contacts(rows, contact_deal_map={}, deal_pipeline_map={}))
    f2 = list(evaluate_contacts(rows, contact_deal_map={}, deal_pipeline_map={}))
    assert f1[0]["issue_key"] == f2[0]["issue_key"]
