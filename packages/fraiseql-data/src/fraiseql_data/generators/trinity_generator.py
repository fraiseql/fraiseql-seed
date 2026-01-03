"""Trinity pattern column generator."""

from typing import Any

from fraiseql_uuid import Pattern


class TrinityGenerator:
    """
    Generate Trinity pattern columns (id, identifier, and optionally pk_*).

    Trinity pattern columns:
        - id: UUID v4 with encoded metadata (using fraiseql-uuid Pattern)
        - identifier: Human-readable slug derived from 'name' column or generated
        - pk_*: Deterministically allocated INTEGER primary key (if Trinity extension enabled)

    The generator creates debuggable UUIDs with table context, auto-generates
    identifiers from the row's 'name' field when available, and optionally
    allocates deterministic primary keys via the Trinity PostgreSQL extension.
    """

    def __init__(
        self,
        pattern: Pattern,
        table_name: str,
        seed_dir: int = 21,
        trinity_context: dict[str, Any] | None = None,
    ):
        """
        Initialize Trinity generator.

        Args:
            pattern: fraiseql-uuid Pattern for generating UUIDs
            table_name: Table name for identifier generation
            seed_dir: Seed directory code for UUID generation (default: 21 for test data)
            trinity_context: Optional context for Trinity extension allocation with keys:
                - conn: Database connection for calling trinity.allocate_uuid_pk()
                - tenant_id: Tenant ID for multi-tenant isolation
        """
        self.pattern = pattern
        self.table_name = table_name
        self.seed_dir = seed_dir
        self.trinity_context = trinity_context

        # Auto-generate table code from table name
        import hashlib

        self.table_code = hashlib.md5(table_name.encode()).hexdigest()[:6]

    def generate(self, instance: int, **row_data: Any) -> dict[str, Any]:
        """
        Generate Trinity columns for a row.

        Args:
            instance: Row instance number (1-based)
            **row_data: Other column data (used to derive identifier from 'name')

        Returns:
            Dict with 'id' (UUID), 'identifier' (slug), and optionally 'pk_{table_name}'
            keys when Trinity context is provided.

        Examples:
            >>> gen = TrinityGenerator(pattern, 'tb_manufacturer')
            >>> gen.generate(1, name='Acme Corp')
            {'id': UUID('...'), 'identifier': 'acme-corp-1'}

            >>> # With Trinity context
            >>> gen = TrinityGenerator(pattern, 'tb_manufacturer', trinity_context={...})
            >>> gen.generate(1, name='Acme Corp')
            {'id': UUID('...'), 'identifier': 'acme-corp-1', 'pk_tb_manufacturer': 42}
        """
        trinity_data = {}

        # Generate UUID id
        generated_id = self.pattern.generate(
            table_code=self.table_code,
            seed_dir=self.seed_dir,
            function=0,
            scenario=0,
            test_case=0,
            instance=instance,
        )
        trinity_data["id"] = generated_id

        # Generate identifier
        # Try to derive from 'name' column if it exists
        if "name" in row_data and row_data["name"]:
            base = row_data["name"]
            # Simple slugify
            identifier = base.lower().replace(" ", "-").replace("_", "-")
            # Make unique by appending instance
            trinity_data["identifier"] = f"{identifier}-{instance}"
        else:
            # Fallback: table name + instance
            trinity_data["identifier"] = f"{self.table_name}_{instance:04d}"

        # Allocate deterministic pk_* via Trinity extension if context provided
        if self.trinity_context:
            pk_column = f"pk_{self.table_name}"
            try:
                conn = self.trinity_context["conn"]
                tenant_id = self.trinity_context.get("tenant_id")

                # Call Trinity extension to allocate deterministic PK
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT trinity.allocate_uuid_pk(%s, %s, %s)",
                        (self.table_name, str(generated_id), tenant_id),
                    )
                    allocated_pk = cur.fetchone()[0]
                    trinity_data[pk_column] = allocated_pk
                    conn.commit()
            except Exception as e:
                raise RuntimeError(
                    f"Trinity extension allocation failed for {self.table_name}: {e}"
                ) from e

        return trinity_data
