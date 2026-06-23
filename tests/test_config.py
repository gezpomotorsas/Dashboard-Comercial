"""Pruebas de configuración."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_valid(monkeypatch):
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "pat-test-token")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_VERSION", "0.1.0")

    settings = Settings(_env_file=None)
    assert settings.hubspot_access_token.get_secret_value() == "pat-test-token"
    assert settings.supabase_url == "https://example.supabase.co"


def test_settings_missing_required(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("hubspot_api_key", raising=False)
    monkeypatch.delenv("hubspot_api_key_service", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_token_hidden_in_repr(monkeypatch):
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "super-secret")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret")

    settings = Settings(_env_file=None)
    assert "super-secret" not in repr(settings.hubspot_access_token)
    assert settings.hubspot_access_token.get_secret_value() == "super-secret"


def test_hubspot_alias(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("hubspot_api_key_service", "pat-alias-token")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")

    settings = Settings(_env_file=None)
    assert settings.hubspot_access_token.get_secret_value() == "pat-alias-token"


def test_supabase_url_stripped(monkeypatch):
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "pat-test")
    monkeypatch.setenv("SUPABASE_URL", "  https://example.supabase.co/rest/v1/  ")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")

    settings = Settings(_env_file=None)
    assert settings.supabase_url == "https://example.supabase.co/rest/v1"
