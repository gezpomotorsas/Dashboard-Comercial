"""Cliente de base de datos PostgreSQL local."""

from functools import lru_cache

from app.db.connection import get_pool
from app.db.postgrest_compat import DatabaseClient, DatabaseClientError

# Alias histórico usado en el proyecto
SupabaseClientError = DatabaseClientError


@lru_cache
def get_database_client() -> DatabaseClient:
    return DatabaseClient()


def get_supabase_client() -> DatabaseClient:
    """Compatibilidad: antes apuntaba a Supabase, ahora PostgreSQL local."""
    return get_database_client()


def close_pool() -> None:
    from app.db.connection import close_pool as _close

    _close()
    get_database_client.cache_clear()
