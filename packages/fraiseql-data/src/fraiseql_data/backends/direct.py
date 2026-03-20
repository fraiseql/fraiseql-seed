"""Direct INSERT backend — uses COPY for bulk, INSERT for single rows."""

import json
from dataclasses import dataclass
from typing import Any

from psycopg import Connection, sql
from psycopg.types.json import Json, Jsonb

from fraiseql_data.models import TableInfo

# Threshold: use COPY for batches at or above this size, INSERT below.
# COPY has per-statement overhead (SELECT back) that makes it slower
# than INSERT ... RETURNING for small batches.
COPY_THRESHOLD = 50


@dataclass(frozen=True, slots=True)
class _InsertContext:
    """Shared state for INSERT operations."""

    insert_columns: list[str]
    col_types: dict[str, str]
    columns_sql: sql.Composable
    all_columns_sql: sql.Composable
    override_clause: sql.Composable
    qualified_table: sql.Composable


class DirectBackend:
    """
    Execute seed generation using PostgreSQL's COPY protocol (bulk)
    or INSERT ... RETURNING (single-row / small batches).

    COPY is ~2x faster than multi-row INSERT for bulk loads.
    INSERT ... RETURNING is used when we need per-row feedback
    (self-referencing tables, small batches).
    """

    def __init__(self, conn: Connection, schema: str):
        self.conn = conn
        self.schema = schema

    # ------------------------------------------------------------------
    # Value adaptation for psycopg3
    # ------------------------------------------------------------------

    @staticmethod
    def _adapt_value(value: Any, pg_type: str) -> Any:
        """Wrap Python values for psycopg3 parameter binding (INSERT path)."""
        if value is None:
            return None
        if pg_type == "jsonb" and isinstance(value, (dict, list)):
            return Jsonb(value)
        if pg_type == "json" and isinstance(value, (dict, list)):
            return Json(value)
        return value

    @staticmethod
    def _adapt_value_copy(value: Any, pg_type: str) -> Any:
        """Adapt Python values for COPY protocol (text format).

        COPY is stricter than INSERT: no implicit float→int cast,
        JSON must be a string, etc.
        """
        if value is None:
            return None
        if pg_type in ("jsonb", "json") and isinstance(value, (dict, list)):
            return json.dumps(value)
        # COPY won't cast float to int — coerce explicitly
        if pg_type in ("integer", "bigint", "smallint") and isinstance(value, float):
            return int(value)
        return value

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _prepare_insert(self, table_info: TableInfo, rows: list[dict[str, Any]]) -> _InsertContext:
        """Build shared SQL fragments for INSERT operations."""
        first_row = rows[0]
        insert_columns = [
            col.name
            for col in table_info.columns
            if col.name in first_row and first_row[col.name] is not None
        ]

        # pk_ columns in data means pre-allocated PKs (convention, not SQL)
        has_preallocated_pk = any(col.startswith("pk_") for col in insert_columns)
        col_types = {col.name: col.pg_type for col in table_info.columns}

        columns_sql = sql.SQL(", ").join(sql.Identifier(c) for c in insert_columns)
        all_columns_sql = sql.SQL(", ").join(sql.Identifier(col.name) for col in table_info.columns)
        override_clause = (
            sql.SQL(" OVERRIDING SYSTEM VALUE") if has_preallocated_pk else sql.SQL("")
        )
        qualified_table = sql.Identifier(self.schema, table_info.name)

        return _InsertContext(
            insert_columns=insert_columns,
            col_types=col_types,
            columns_sql=columns_sql,
            all_columns_sql=all_columns_sql,
            override_clause=override_clause,
            qualified_table=qualified_table,
        )

    @staticmethod
    def _rows_to_dicts(
        result_rows: list[tuple[Any, ...]], table_info: TableInfo
    ) -> list[dict[str, Any]]:
        """Convert raw cursor tuples to column-keyed dicts."""
        return [
            {col.name: result[idx] for idx, col in enumerate(table_info.columns)}
            for result in result_rows
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert_rows(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
        bulk: bool = True,
    ) -> list[dict[str, Any]]:
        """Insert rows and return complete data with generated columns."""
        if not rows:
            return []

        if bulk and len(rows) >= COPY_THRESHOLD:
            return self._copy_rows(table_info, rows)
        if bulk and len(rows) > 1:
            return self._insert_rows_bulk(table_info, rows)
        return self._insert_rows_single(table_info, rows)

    # ------------------------------------------------------------------
    # COPY path (fast bulk)
    # ------------------------------------------------------------------

    def _copy_rows(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Insert rows via COPY FROM STDIN, then SELECT back with generated cols."""
        if not rows:
            return []

        ctx = self._prepare_insert(table_info, rows)

        # Find the PK/identity column for ordering the SELECT back
        identity_col = next(
            (col.name for col in table_info.columns if col.is_identity),
            None,
        )

        with self.conn.cursor() as cur:
            # For OVERRIDING SYSTEM VALUE we need to use a writable CTE
            # because COPY doesn't support it directly. Use a temp table.
            has_preallocated_pk = any(col.startswith("pk_") for col in ctx.insert_columns)
            if has_preallocated_pk:
                # Create temp table matching insert columns.
                # Column types come from introspection — use sql.SQL() for type
                # names (they are keywords/type names, not identifiers).
                temp_col_defs = sql.SQL(", ").join(
                    sql.SQL("{} {}").format(
                        sql.Identifier(col),
                        sql.SQL(next(c.pg_type for c in table_info.columns if c.name == col)),
                    )
                    for col in ctx.insert_columns
                )
                cur.execute(
                    sql.SQL("CREATE TEMP TABLE _seed_copy_buf ({}) ON COMMIT DROP").format(
                        temp_col_defs
                    )
                )

                # COPY into temp table
                copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier("_seed_copy_buf"), ctx.columns_sql
                )
                with cur.copy(copy_stmt) as copy:
                    for row in rows:
                        copy.write_row(
                            [
                                self._adapt_value_copy(row.get(col), ctx.col_types.get(col, ""))
                                for col in ctx.insert_columns
                            ]
                        )

                # INSERT from temp into real table with OVERRIDING SYSTEM VALUE
                cur.execute(
                    sql.SQL(
                        "INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE SELECT {} FROM {} RETURNING {}"
                    ).format(
                        ctx.qualified_table,
                        ctx.columns_sql,
                        ctx.columns_sql,
                        sql.Identifier("_seed_copy_buf"),
                        ctx.all_columns_sql,
                    )
                )
                result_rows = cur.fetchall()
            else:
                # Record the max identity value before insert (for SELECT back)
                pre_max = None
                if identity_col:
                    cur.execute(
                        sql.SQL("SELECT COALESCE(MAX({}), 0) FROM {}").format(
                            sql.Identifier(identity_col),
                            ctx.qualified_table,
                        )
                    )
                    row = cur.fetchone()
                    assert row is not None
                    pre_max = row[0]

                # COPY directly into target table
                copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    ctx.qualified_table, ctx.columns_sql
                )
                with cur.copy(copy_stmt) as copy:
                    for row in rows:
                        copy.write_row(
                            [
                                self._adapt_value_copy(row.get(col), ctx.col_types.get(col, ""))
                                for col in ctx.insert_columns
                            ]
                        )

                # SELECT back inserted rows (using identity column range)
                if identity_col and pre_max is not None:
                    cur.execute(
                        sql.SQL("SELECT {} FROM {} WHERE {} > %s ORDER BY {}").format(
                            ctx.all_columns_sql,
                            ctx.qualified_table,
                            sql.Identifier(identity_col),
                            sql.Identifier(identity_col),
                        ),
                        (pre_max,),
                    )
                else:
                    # No identity column — fall back to SELECT all
                    cur.execute(
                        sql.SQL("SELECT {} FROM {}").format(
                            ctx.all_columns_sql, ctx.qualified_table
                        )
                    )
                result_rows = cur.fetchall()

        inserted_rows = self._rows_to_dicts(result_rows, table_info)
        self.conn.commit()
        return inserted_rows

    # ------------------------------------------------------------------
    # INSERT path (small batches, single rows)
    # ------------------------------------------------------------------

    def _insert_rows_bulk(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Insert rows using multi-row INSERT ... RETURNING."""
        if not rows:
            return []

        ctx = self._prepare_insert(table_info, rows)

        single_placeholder = sql.SQL("({})").format(
            sql.SQL(", ").join(sql.Placeholder() for _ in ctx.insert_columns)
        )
        placeholders = sql.SQL(", ").join(single_placeholder for _ in rows)

        insert_stmt = sql.SQL("INSERT INTO {} ({}){} VALUES {} RETURNING {}").format(
            ctx.qualified_table,
            ctx.columns_sql,
            ctx.override_clause,
            placeholders,
            ctx.all_columns_sql,
        )

        values: list[Any] = []
        for row in rows:
            values.extend(
                self._adapt_value(row.get(col), ctx.col_types.get(col, ""))
                for col in ctx.insert_columns
            )

        with self.conn.cursor() as cur:
            cur.execute(insert_stmt, values)
            result_rows = cur.fetchall()

        inserted_rows = self._rows_to_dicts(result_rows, table_info)
        self.conn.commit()
        return inserted_rows

    def _insert_rows_single(
        self, table_info: TableInfo, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Insert rows one-by-one with INSERT ... RETURNING."""
        if not rows:
            return []

        ctx = self._prepare_insert(table_info, rows)

        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in ctx.insert_columns)
        insert_stmt = sql.SQL("INSERT INTO {} ({}){} VALUES ({}) RETURNING {}").format(
            ctx.qualified_table,
            ctx.columns_sql,
            ctx.override_clause,
            placeholders,
            ctx.all_columns_sql,
        )

        inserted_rows = []
        with self.conn.cursor() as cur:
            for row in rows:
                values = [
                    self._adapt_value(row.get(col), ctx.col_types.get(col, ""))
                    for col in ctx.insert_columns
                ]
                cur.execute(insert_stmt, values)
                result = cur.fetchone()
                assert result is not None
                complete_row = {col.name: result[i] for i, col in enumerate(table_info.columns)}
                inserted_rows.append(complete_row)

        self.conn.commit()
        return inserted_rows
