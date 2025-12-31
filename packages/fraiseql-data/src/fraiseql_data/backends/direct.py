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
        self, table_info: TableInfo, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Insert rows into table and return inserted data with generated columns.

        Args:
            table_info: Table metadata
            rows: List of row data (without pk_* or auto-generated columns)

        Returns:
            List of complete rows including generated pk_* and defaults
        """
        if not rows:
            return []

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
