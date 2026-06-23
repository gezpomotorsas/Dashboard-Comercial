"""Pruebas de paginación y transformaciones."""

import os

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.repositories.supabase_repository import SupabaseRepository
from app.services.hubspot_base import build_paginated_response, map_hubspot_object, resolve_brand
from app.utils.serialization import chunk_list


def test_resolve_brand_shacman():
    assert resolve_brand("default") == "shacman"


def test_resolve_brand_voyah():
    assert resolve_brand("1000390393") == "voyah"


def test_resolve_brand_mhero():
    assert resolve_brand("1963395799") == "mhero"


def test_resolve_brand_unknown():
    assert resolve_brand("999") is None


def test_build_paginated_response():
    response = build_paginated_response(
        items=[{"id": "1"}],
        object_type="contacts",
        paging={"next": {"after": "abc123"}},
    )
    assert response.pagination.has_more is True
    assert response.pagination.next_after == "abc123"
    assert response.meta.count == 1


def test_map_contact():
    record = {
        "id": "101",
        "properties": {"email": "test@example.com", "firstname": "Juan"},
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-02T00:00:00Z",
        "archived": False,
    }
    mapped = map_hubspot_object(record)
    assert mapped.id == "101"
    assert mapped.properties["email"] == "test@example.com"
    assert mapped.brand is None


def test_map_deal_with_brand():
    record = {
        "id": "201",
        "properties": {"dealname": "Negocio Voyah", "pipeline": "1000390393"},
        "archived": False,
    }
    mapped = map_hubspot_object(record, include_brand=True)
    assert mapped.brand == "voyah"


def test_chunk_list():
    chunks = chunk_list(["a", "b", "c", "d", "e"], 2)
    assert chunks == [["a", "b"], ["c", "d"], ["e"]]


def test_transform_contact_row():
    repo = SupabaseRepository.__new__(SupabaseRepository)
    row = repo.transform_hubspot_object(
        "contacts",
        {
            "id": "101",
            "properties": {"email": "a@b.com"},
            "createdAt": "2024-01-01T00:00:00.000Z",
            "archived": False,
        },
    )
    assert row["hubspot_id"] == "101"
    assert row["properties"]["email"] == "a@b.com"


def test_transform_deal_row_brand():
    repo = SupabaseRepository.__new__(SupabaseRepository)
    row = repo.transform_hubspot_object(
        "deals",
        {
            "id": "301",
            "properties": {"pipeline": "1963395799", "dealstage": "stage1"},
            "archived": False,
        },
    )
    assert row["brand"] == "mhero"
    assert row["pipeline_id"] == "1963395799"
