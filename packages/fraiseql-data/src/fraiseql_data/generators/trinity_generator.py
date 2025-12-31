"""Trinity pattern column generator."""

from typing import Any

from fraiseql_uuid import Pattern


class TrinityGenerator:
    """
    Generate Trinity pattern columns (id, identifier).

    Trinity pattern columns:
        - id: UUID v4 with encoded metadata (using fraiseql-uuid Pattern)
        - identifier: Human-readable slug derived from 'name' column or generated

    The generator creates debuggable UUIDs with table context and auto-generates
    identifiers from the row's 'name' field when available.
    """

    def __init__(self, pattern: Pattern, table_name: str, seed_dir: int = 21):
        """
        Initialize Trinity generator.

        Args:
            pattern: fraiseql-uuid Pattern for generating UUIDs
            table_name: Table name for identifier generation
            seed_dir: Seed directory code for UUID generation (default: 21 for test data)
        """
        self.pattern = pattern
        self.table_name = table_name
        self.seed_dir = seed_dir

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
            Dict with 'id' (UUID) and 'identifier' (slug) keys

        Examples:
            >>> gen = TrinityGenerator(pattern, 'tb_manufacturer')
            >>> gen.generate(1, name='Acme Corp')
            {'id': UUID('...'), 'identifier': 'acme-corp-1'}
            >>> gen.generate(2, name='Beta Inc')
            {'id': UUID('...'), 'identifier': 'beta-inc-2'}
            >>> gen.generate(3)  # No name provided
            {'id': UUID('...'), 'identifier': 'tb_manufacturer_0003'}
        """
        trinity_data = {}

        # Generate UUID id
        trinity_data["id"] = self.pattern.generate(
            table_code=self.table_code,
            seed_dir=self.seed_dir,
            function=0,
            scenario=0,
            test_case=0,
            instance=instance,
        )

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

        return trinity_data
