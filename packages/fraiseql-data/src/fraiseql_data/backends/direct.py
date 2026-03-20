"""Direct INSERT backend — uses COPY for bulk, INSERT for single rows."""

import json
from typing import Any

from psycopg import Connection, sql
from psycopg.types.json import Json, Jsonb

from fraiseql_data.models import TableInfo

# Threshold: use COPY for batches at or above this size, INSERT below.
# COPY has per-statement overhead (SELECT back) that makes it slower
# than INSERT ... RETURNING for small batches.
COPY_THRESHOLD = 50


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

        first_row = rows[0]
        insert_columns = [
            col.name
            for col in table_info.columns
            if col.name in first_row and first_row[col.name] is not None
        ]

        has_preallocated_pk = any(col.startswith("pk_") for col in insert_columns)
        col_types = {col.name: col.pg_type for col in table_info.columns}

        # Find the PK/identity column for ordering the SELECT back
        identity_col = next(
            (col.name for col in table_info.columns if col.is_identity),
            None,
        )

        qualified_table = f"{self.schema}.{table_info.name}"
        columns_list = ", ".join(insert_columns)
        all_columns = ", ".join(col.name for col in table_info.columns)

        with self.conn.cursor() as cur:
            # For OVERRIDING SYSTEM VALUE we need to use a writable CTE
            # because COPY doesn't support it directly. Use a temp table.
            if has_preallocated_pk:
                # Create temp table matching insert columns
                temp_cols = ", ".join(
                    f"{col} {next(c.pg_type for c in table_info.columns if c.name == col)}"
                    for col in insert_columns
                )
                cur.execute(f"CREATE TEMP TABLE _seed_copy_buf ({temp_cols}) ON COMMIT DROP")

                # COPY into temp table
                copy_sql = f"COPY _seed_copy_buf ({columns_list}) FROM STDIN"
                with cur.copy(copy_sql) as copy:
                    for row in rows:
                        copy.write_row(
                            [
                                self._adapt_value_copy(row.get(col), col_types.get(col, ""))
                                for col in insert_columns
                            ]
                        )

                # INSERT from temp into real table with OVERRIDING SYSTEM VALUE
                cur.execute(f"""
                    INSERT INTO {qualified_table} ({columns_list})
                    OVERRIDING SYSTEM VALUE
                    SELECT {columns_list} FROM _seed_copy_buf
                    RETURNING {all_columns}
                """)
                result_rows = cur.fetchall()
            else:
                # Record the max identity value before insert (for SELECT back)
                pre_max = None
                if identity_col:
                    cur.execute(
                        sql.SQL("SELECT COALESCE(MAX({}), 0) FROM {}").format(
                            sql.Identifier(identity_col),
                            sql.SQL(qualified_table),
                        )
                    )
                    pre_max = cur.fetchone()[0]

                # COPY directly into target table
                copy_sql = f"COPY {qualified_table} ({columns_list}) FROM STDIN"
                with cur.copy(copy_sql) as copy:
                    for row in rows:
                        copy.write_row(
                            [
                                self._adapt_value_copy(row.get(col), col_types.get(col, ""))
                                for col in insert_columns
                            ]
                        )

                # SELECT back inserted rows (using identity column range)
                if identity_col and pre_max is not None:
                    cur.execute(
                        f"SELECT {all_columns} FROM {qualified_table} "
                        f"WHERE {identity_col} > %s ORDER BY {identity_col}",
                        (pre_max,),
                    )
                else:
                    # No identity column — fall back to SELECT all
                    cur.execute(f"SELECT {all_columns} FROM {qualified_table}")
                result_rows = cur.fetchall()

        inserted_rows = [
            {col.name: result[idx] for idx, col in enumerate(table_info.columns)}
            for result in result_rows
        ]

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

        first_row = rows[0]
        insert_columns = [
            col.name
            for col in table_info.columns
            if col.name in first_row and first_row[col.name] is not None
        ]

        has_preallocated_pk = any(col.startswith("pk_") for col in insert_columns)
        col_types = {col.name: col.pg_type for col in table_info.columns}

        columns_list = ", ".join(insert_columns)
        single_placeholder = f"({','.join(['%s'] * len(insert_columns))})"
        placeholders = ", ".join([single_placeholder] * len(rows))
        all_columns = ", ".join(col.name for col in table_info.columns)
        override_clause = " OVERRIDING SYSTEM VALUE" if has_preallocated_pk else ""

        insert_sql = f"""
            INSERT INTO {self.schema}.{table_info.name} ({columns_list}){override_clause}
            VALUES {placeholders}
            RETURNING {all_columns}
        """

        values = []
        for row in rows:
            values.extend(
                self._adapt_value(row.get(col), col_types.get(col, "")) for col in insert_columns
            )

        with self.conn.cursor() as cur:
            cur.execute(insert_sql, values)
            result_rows = cur.fetchall()

        inserted_rows = [
            {col.name: result[idx] for idx, col in enumerate(table_info.columns)}
            for result in result_rows
        ]

        self.conn.commit()
        return inserted_rows

    def _insert_rows_single(
        self, table_info: TableInfo, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Insert rows one-by-one with INSERT ... RETURNING."""
        if not rows:
            return []

        first_row = rows[0]
        insert_columns = [
            col.name
            for col in table_info.columns
            if col.name in first_row and first_row[col.name] is not None
        ]

        has_preallocated_pk = any(col.startswith("pk_") for col in insert_columns)
        col_types = {col.name: col.pg_type for col in table_info.columns}

        columns_list = ", ".join(insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))
        all_columns = ", ".join(col.name for col in table_info.columns)
        override_clause = " OVERRIDING SYSTEM VALUE" if has_preallocated_pk else ""

        insert_sql = f"""
            INSERT INTO {self.schema}.{table_info.name} ({columns_list}){override_clause}
            VALUES ({placeholders})
            RETURNING {all_columns}
        """

        inserted_rows = []
        with self.conn.cursor() as cur:
            for row in rows:
                values = [
                    self._adapt_value(row.get(col), col_types.get(col, ""))
                    for col in insert_columns
                ]
                cur.execute(insert_sql, values)
                result = cur.fetchone()
                complete_row = {col.name: result[i] for i, col in enumerate(table_info.columns)}
                inserted_rows.append(complete_row)

        self.conn.commit()
        return inserted_rows
