"""Trinity pattern column generator."""

from typing import Any
from fraiseql_uuid import Pattern


class TrinityGenerator:
    """Generate Trinity pattern columns (id, identifier)."""

    def __init__(self, pattern: Pattern, table_name: str, seed_dir: int = 21):
        self.pattern = pattern
        self.table_name = table_name
        self.seed_dir = seed_dir

        # Auto-generate table code from table name
        import hashlib
        self.table_code = hashlib.md5(table_name.encode()).hexdigest()[:6]

    def generate(self, instance: int, **row_data: Any) -> dict[str, Any]:
        """Generate Trinity columns for a row."""
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
