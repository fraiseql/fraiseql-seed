"""Seed generation orchestrator."""

from typing import Any


class SeedOrchestrator:
    """Orchestrate seed data generation across multiple tables."""

    def __init__(self, config: dict[str, Any]):
        """Initialize orchestrator.

        Args:
            config: Orchestration configuration
        """
        self.config = config

    def generate_seeds(self, table: str, rows: int) -> None:
        """Generate seed data for a table (stub).

        Args:
            table: Table name
            rows: Number of rows to generate
        """
        # TODO: Implement seed orchestration
        raise NotImplementedError("Seed orchestration not yet implemented")
