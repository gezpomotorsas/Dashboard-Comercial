"""Capa compatible con supabase-py sobre PostgreSQL directo."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from psycopg import sql
from psycopg.types.json import Jsonb

from app.db.connection import get_pool

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

ALLOWED_TABLES = frozenset(
    {
        "hubspot_properties",
        "hubspot_owners",
        "hubspot_pipelines",
        "hubspot_pipeline_stages",
        "hubspot_association_types",
        "hubspot_contacts",
        "hubspot_deals",
        "hubspot_calls",
        "hubspot_meetings",
        "hubspot_tasks",
        "hubspot_emails",
        "hubspot_communications",
        "hubspot_notes",
        "hubspot_associations",
        "sync_runs",
        "sync_errors",
        "sync_cursors",
        "data_quality_rules",
        "data_quality_runs",
        "data_quality_results",
        "hubspot_field_mappings",
        "hubspot_stage_classifications",
        "business_dimension_mappings",
        "hubspot_metadata_refresh_runs",
        "hubspot_stage_commercial_groups",
        "deal_analytics",
        "deal_analytics_runs",
        "hubspot_deal_stage_history",
        "kpi_definitions",
        "analytics_bucket_config",
        "owner_deal_analytics",
    }
)


class DatabaseClientError(Exception):
    """Error al interactuar con la base de datos."""


@dataclass
class ExecuteResult:
    data: list[dict[str, Any]] | None = None
    count: int | None = None


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise DatabaseClientError(f"Identificador no permitido: {name}")
    return name


def _prepare_value(value: Any) -> Any:
    if isinstance(value, dict | list):
        return Jsonb(value)
    return value


class TableQuery:
    def __init__(self, table: str) -> None:
        if table not in ALLOWED_TABLES:
            raise DatabaseClientError(f"Tabla no permitida: {table}")
        self._table = table
        self._operation: Literal["select", "insert", "update", "upsert"] = "select"
        self._select_columns = "*"
        self._count_exact = False
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._offset: int | None = None
        self._insert_rows: list[dict[str, Any]] | None = None
        self._update_values: dict[str, Any] | None = None
        self._upsert_rows: list[dict[str, Any]] | None = None
        self._on_conflict: str | None = None

    def select(self, columns: str = "*", *, count: str | None = None) -> "TableQuery":
        self._operation = "select"
        self._select_columns = columns
        self._count_exact = count == "exact"
        return self

    def insert(self, rows: dict[str, Any] | list[dict[str, Any]]) -> "TableQuery":
        self._operation = "insert"
        self._insert_rows = rows if isinstance(rows, list) else [rows]
        return self

    def update(self, values: dict[str, Any]) -> "TableQuery":
        self._operation = "update"
        self._update_values = values
        return self

    def upsert(self, rows: dict[str, Any] | list[dict[str, Any]], *, on_conflict: str) -> "TableQuery":
        self._operation = "upsert"
        self._upsert_rows = rows if isinstance(rows, list) else [rows]
        self._on_conflict = on_conflict
        return self

    def eq(self, column: str, value: Any) -> "TableQuery":
        self._filters.append(("eq", _validate_identifier(column), value))
        return self

    def gte(self, column: str, value: Any) -> "TableQuery":
        self._filters.append(("gte", _validate_identifier(column), value))
        return self

    def lte(self, column: str, value: Any) -> "TableQuery":
        self._filters.append(("lte", _validate_identifier(column), value))
        return self

    def lt(self, column: str, value: Any) -> "TableQuery":
        self._filters.append(("lt", _validate_identifier(column), value))
        return self

    def in_(self, column: str, values: list[Any]) -> "TableQuery":
        self._filters.append(("in", _validate_identifier(column), values))
        return self

    def is_(self, column: str, value: str) -> "TableQuery":
        self._filters.append(("is", _validate_identifier(column), value))
        return self

    def order(self, column: str, *, desc: bool = False) -> "TableQuery":
        self._order_by = (_validate_identifier(column), desc)
        return self

    def limit(self, value: int) -> "TableQuery":
        self._limit = value
        return self

    def range(self, start: int, end: int) -> "TableQuery":
        self._offset = start
        self._limit = max(0, end - start + 1)
        return self

    def _build_where(self) -> tuple[sql.SQL, list[Any]]:
        clauses: list[sql.SQL] = []
        params: list[Any] = []
        for op, column, value in self._filters:
            col = sql.Identifier(column)
            if op == "eq":
                params.append(value)
                clauses.append(sql.SQL("{} = {}").format(col, sql.Placeholder()))
            elif op == "gte":
                params.append(value)
                clauses.append(sql.SQL("{} >= {}").format(col, sql.Placeholder()))
            elif op == "lte":
                params.append(value)
                clauses.append(sql.SQL("{} <= {}").format(col, sql.Placeholder()))
            elif op == "lt":
                params.append(value)
                clauses.append(sql.SQL("{} < {}").format(col, sql.Placeholder()))
            elif op == "in":
                if not value:
                    clauses.append(sql.SQL("FALSE"))
                else:
                    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in value)
                    params.extend(value)
                    clauses.append(sql.SQL("{} IN ({})").format(col, placeholders))
            elif op == "is" and value == "null":
                clauses.append(sql.SQL("{} IS NULL").format(col))
        if not clauses:
            return sql.SQL(""), params
        return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses), params

    def _select_columns_sql(self) -> sql.Composable:
        if self._select_columns.strip() == "*":
            return sql.SQL("*")
        parts = [_validate_identifier(c.strip()) for c in self._select_columns.split(",")]
        return sql.SQL(", ").join(sql.Identifier(p) for p in parts)

    def execute(self) -> ExecuteResult:
        try:
            if self._operation == "select":
                return self._execute_select()
            if self._operation == "insert":
                return self._execute_insert()
            if self._operation == "update":
                return self._execute_update()
            if self._operation == "upsert":
                return self._execute_upsert()
            raise DatabaseClientError(f"Operación no soportada: {self._operation}")
        except DatabaseClientError:
            raise
        except Exception as exc:
            logger.exception("Error de base de datos en %s", self._table)
            raise DatabaseClientError("Error al persistir datos en PostgreSQL") from exc

    def _execute_select(self) -> ExecuteResult:
        table = sql.Identifier(self._table)
        where_sql, params = self._build_where()

        if self._count_exact and self._limit == 0:
            query = sql.SQL("SELECT COUNT(*) AS count FROM {}").format(table) + where_sql
            with get_pool().connection() as conn:
                row = conn.execute(query, params).fetchone()
            return ExecuteResult(data=[], count=int(row["count"]) if row else 0)

        query_parts: list[sql.Composable] = [
            sql.SQL("SELECT "),
            self._select_columns_sql(),
            sql.SQL(" FROM "),
            table,
            where_sql,
        ]
        if self._order_by:
            col, desc = self._order_by
            query_parts.append(
                sql.SQL(" ORDER BY {} ").format(sql.Identifier(col))
                + sql.SQL("DESC" if desc else "ASC")
            )
        if self._limit is not None:
            query_parts.append(sql.SQL(" LIMIT {}").format(sql.Literal(self._limit)))
        if self._offset is not None:
            query_parts.append(sql.SQL(" OFFSET {}").format(sql.Literal(self._offset)))

        query = sql.Composed(query_parts)
        with get_pool().connection() as conn:
            rows = conn.execute(query, params).fetchall()
        data = [dict(r) for r in rows]
        count = len(data) if self._count_exact else None
        return ExecuteResult(data=data, count=count)

    def _execute_insert(self) -> ExecuteResult:
        assert self._insert_rows is not None
        if not self._insert_rows:
            return ExecuteResult(data=[])
        return self._execute_write(self._insert_rows, on_conflict=None)

    def _execute_upsert(self) -> ExecuteResult:
        assert self._upsert_rows is not None and self._on_conflict is not None
        if not self._upsert_rows:
            return ExecuteResult(data=[])
        return self._execute_write(self._upsert_rows, on_conflict=self._on_conflict)

    def _execute_write(
        self,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None,
    ) -> ExecuteResult:
        columns = list(rows[0].keys())
        for col in columns:
            _validate_identifier(col)

        table = sql.Identifier(self._table)
        col_idents = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        single_placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
        all_placeholders = sql.SQL(", ").join(
            sql.SQL("({})").format(single_placeholders) for _ in rows
        )
        flat_params: list[Any] = []
        for row in rows:
            flat_params.extend(_prepare_value(row.get(c)) for c in columns)

        query_parts: list[sql.Composable] = [
            sql.SQL("INSERT INTO "),
            table,
            sql.SQL(" ("),
            col_idents,
            sql.SQL(") VALUES "),
            all_placeholders,
        ]

        if on_conflict:
            conflict_cols = [_validate_identifier(c.strip()) for c in on_conflict.split(",")]
            conflict_idents = sql.SQL(", ").join(sql.Identifier(c) for c in conflict_cols)
            update_cols = [c for c in columns if c not in conflict_cols]
            if update_cols:
                update_assignments = sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                    for c in update_cols
                )
                query_parts.extend(
                    [
                        sql.SQL(" ON CONFLICT ("),
                        conflict_idents,
                        sql.SQL(") DO UPDATE SET "),
                        update_assignments,
                    ]
                )
            else:
                query_parts.extend([sql.SQL(" ON CONFLICT ("), conflict_idents, sql.SQL(") DO NOTHING")])

        query_parts.append(sql.SQL(" RETURNING *"))
        query = sql.Composed(query_parts)

        with get_pool().connection() as conn:
            result = conn.execute(query, flat_params).fetchall()
        return ExecuteResult(data=[dict(r) for r in result])

    def _execute_update(self) -> ExecuteResult:
        assert self._update_values is not None
        if not self._update_values:
            return ExecuteResult(data=[])

        assignments = []
        params: list[Any] = []
        for key, value in self._update_values.items():
            _validate_identifier(key)
            assignments.append(
                sql.SQL("{} = {}").format(sql.Identifier(key), sql.Placeholder())
            )
            params.append(_prepare_value(value))

        where_sql, where_params = self._build_where()
        params.extend(where_params)

        query = sql.Composed(
            [
                sql.SQL("UPDATE "),
                sql.Identifier(self._table),
                sql.SQL(" SET "),
                sql.SQL(", ").join(assignments),
                where_sql,
                sql.SQL(" RETURNING *"),
            ]
        )
        with get_pool().connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return ExecuteResult(data=[dict(r) for r in rows])


class DatabaseClient:
    def table(self, name: str) -> TableQuery:
        return TableQuery(name)

    def from_(self, name: str) -> TableQuery:
        return TableQuery(name)
