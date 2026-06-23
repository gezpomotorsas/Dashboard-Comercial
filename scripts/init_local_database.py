#!/usr/bin/env python3
"""Aplica migraciones SQL en PostgreSQL local."""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"


def get_database_url() -> str:
    from app.config import get_settings

    return get_settings().database_url


def apply_migrations(dsn: str) -> None:
    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No hay archivos SQL en {SQL_DIR}")

    with psycopg.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

            for path in files:
                name = path.name
                if name in applied:
                    print(f"  omitido  {name}")
                    continue
                print(f"  aplicando {name}...")
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (name,),
                )
                print(f"  listo    {name}")


def main() -> None:
    dsn = get_database_url()
    print(f"Inicializando base de datos: {dsn.split('@')[-1]}")
    try:
        apply_migrations(dsn)
    except psycopg.OperationalError as exc:
        print(
            "No se pudo conectar a PostgreSQL. "
            "Levante el contenedor con: docker compose up -d",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    print("Esquema listo.")


if __name__ == "__main__":
    main()
