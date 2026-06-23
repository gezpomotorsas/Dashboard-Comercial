"""Cliente Supabase (PostgREST)."""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


class SupabaseClientError(Exception):
    """Error al interactuar con Supabase."""


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    try:
        return create_client(
            settings.supabase_url,
            settings.supabase_secret_key.get_secret_value(),
        )
    except Exception as exc:
        raise SupabaseClientError(f"No se pudo conectar a Supabase: {exc}") from exc


def close_supabase_client() -> None:
    get_supabase_client.cache_clear()
