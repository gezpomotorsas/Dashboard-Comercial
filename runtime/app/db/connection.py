"""Pool de conexiones PostgreSQL."""

from __future__ import annotations

import logging
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


@lru_cache
def get_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=True,
    )


def close_pool() -> None:
    global _pool
    pool = get_pool()
    pool.close()
    get_pool.cache_clear()
