"""Direct INSERT backend - generates and executes SQL directly."""

from typing import Any

from psycopg import Connection

from fraiseql_data.models import TableInfo


class DirectBackend:
    """
    Execute seed generation using direct INSERT statements.

    Uses PostgreSQL's RETURNING clause to capture auto-generated values
    (pk_* IDENTITY columns, defaults) after insertion.
    """

    def __init__(self, conn: Connection, schema: str):
        """
        Initialize backend.

        Args:
            conn: PostgreSQL connection
            schema: Schema name for qualified table names
        """
        self.conn = conn
        self.schema = schema

    def insert_rows(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
        bulk: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Insert rows into table and return inserted data with generated columns.

        Args:
            table_info: Table metadata
            rows: List of row data (without pk_* or auto-generated columns)
            bulk: Use bulk insert (default True)

        Returns:
            List of complete rows including generated pk_* and defaults
        """
        if not rows:
            return []

        # Use bulk insert for multiple rows, single for one row or if bulk=False
        if bulk and len(rows) > 1:
            return self.insert_rows_bulk(table_info, rows)
        else:
            return self._insert_rows_single(table_info, rows)

    def insert_rows_bulk(
        self,
        table_info: TableInfo,
        rows: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Insert rows using multi-row INSERT for better performance.

        Args:
            table_info: Table metadata
            rows: List of row data
            batch_size: Number of rows per INSERT statement

        Returns:
            List of complete rows including generated columns
        """
        if not rows:
            return []

        # Get columns to insert
        insert_columns = [
            col.name
            for col in table_info.columns
            if not (col.is_primary_key and col.name.startswith("pk_"))
        ]

        inserted_rows = []

        # Process in batches
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]

            # Build multi-row INSERT
            columns_list = ", ".join(insert_columns)
            single_placeholder = f"({','.join(['%s'] * len(insert_columns))})"
            placeholders = ", ".join([single_placeholder] * len(batch))
            all_columns = ", ".join([col.name for col in table_info.columns])

            sql = f"""
                INSERT INTO {self.schema}.{table_info.name} ({columns_list})
                VALUES {placeholders}
                RETURNING {all_columns}
            """

            # Flatten values: [row1_col1, row1_col2, row2_col1, row2_col2, ...]
            values = []
            for row in batch:
                for col in insert_columns:
                    values.append(row.get(col))

            # Execute bulk insert
            with self.conn.cursor() as cur:
                cur.execute(sql, values)
                result_rows = cur.fetchall()

                # Convert to dicts
                for result in result_rows:
                    complete_row = {
                        col.name: result[idx]
                        for idx, col in enumerate(table_info.columns)
                    }
                    inserted_rows.append(complete_row)

        self.conn.commit()
        return inserted_rows

    def _insert_rows_single(
        self, table_info: TableInfo, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Insert rows one-by-one (original implementation).

        Args:
            table_info: Table metadata
            rows: List of row data

        Returns:
            List of complete rows including generated columns
        """
        # Get columns to insert (exclude pk_* IDENTITY columns)
        insert_columns = [
            col.name
            for col in table_info.columns
            if not (col.is_primary_key and col.name.startswith("pk_"))
        ]

        # Build INSERT ... RETURNING statement
        columns_list = ", ".join(insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))

        # Return all columns including generated ones
        all_columns = ", ".join([col.name for col in table_info.columns])

        sql = f"""
            INSERT INTO {self.schema}.{table_info.name} ({columns_list})
            VALUES ({placeholders})
            RETURNING {all_columns}
        """

        inserted_rows = []
        with self.conn.cursor() as cur:
            for row in rows:
                # Extract values in correct order
                values = [row.get(col) for col in insert_columns]

                # Execute and get returned row
                cur.execute(sql, values)
                result = cur.fetchone()

                # Build complete row dict
                complete_row = {
                    col.name: result[i] for i, col in enumerate(table_info.columns)
                }
                inserted_rows.append(complete_row)

        self.conn.commit()
        return inserted_rows
