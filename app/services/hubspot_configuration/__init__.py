"""Configuración dinámica HubSpot."""

from app.services.hubspot_configuration.store import HubSpotConfigStore

_store: HubSpotConfigStore | None = None


def get_hubspot_config(*, refresh: bool = False) -> HubSpotConfigStore:
    global _store
    if _store is None or refresh:
        _store = HubSpotConfigStore.load()
    return _store


def invalidate_hubspot_config() -> None:
    global _store
    _store = None


def set_hubspot_config(store: HubSpotConfigStore) -> None:
    global _store
    _store = store
