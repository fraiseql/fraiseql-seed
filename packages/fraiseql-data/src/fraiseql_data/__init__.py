"""
fraiseql-data - Schema-Aware Seed Data Generation

Provides intelligent seed data generation based on PostgreSQL schema introspection.
"""

from fraiseql_data.orchestrator import SeedOrchestrator

__version__ = "0.1.0"

__all__ = [
    "SeedOrchestrator",
]
