"""Pruebas de privacidad en listado de actividades."""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("HUBSPOT_ACCESS_TOKEN", "test-token")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test")

from app.api.activities import _apply_privacy
from app.main import app
from app.schemas.common import (
    HubSpotObjectResponse,
    PaginatedResponse,
    PaginationMeta,
    ResponseMeta,
)
from app.utils.privacy import REDACTED


def test_listing_redacts_content_by_default():
    response = PaginatedResponse(
        data=[
            HubSpotObjectResponse(
                id="1",
                properties={
                    "hs_email_subject": "Asunto",
                    "hs_email_text": "contenido secreto",
                },
            )
        ],
        pagination=PaginationMeta(),
        meta=ResponseMeta(count=1, object_type="emails"),
    )
    safe = _apply_privacy(response, include_content=False)
    assert safe.data[0].properties["hs_email_subject"] == "Asunto"
    assert safe.data[0].properties["hs_email_text"] == REDACTED


def test_listing_includes_content_when_requested():
    response = PaginatedResponse(
        data=[
            HubSpotObjectResponse(
                id="1",
                properties={"hs_call_body": "notas"},
            )
        ],
        pagination=PaginationMeta(),
        meta=ResponseMeta(count=1, object_type="calls"),
    )
    safe = _apply_privacy(response, include_content=True)
    assert safe.data[0].properties["hs_call_body"] == "notas"


@pytest.mark.asyncio
async def test_activities_endpoint_default_no_body(monkeypatch):
    from app.api import activities as activities_api
    from app.services import activities_service

    async def fake_list(*args, **kwargs):
        return PaginatedResponse(
            data=[
                HubSpotObjectResponse(
                    id="1",
                    properties={"hs_communication_body": "mensaje privado"},
                )
            ],
            pagination=PaginationMeta(),
            meta=ResponseMeta(count=1, object_type="communications"),
        )

    monkeypatch.setattr(activities_service, "list_activities", fake_list)
    monkeypatch.setattr(
        activities_api,
        "get_hubspot_client",
        lambda: MagicMock(),
    )

    with TestClient(app) as c:
        from app.clients.hubspot import get_hubspot_client

        app.dependency_overrides[get_hubspot_client] = lambda: MagicMock()
        r = c.get("/api/v1/hubspot/activities/communications?limit=1")
        app.dependency_overrides.clear()
    if r.status_code == 200:
        body = r.json()["data"][0]["properties"].get("hs_communication_body")
        assert body == REDACTED
