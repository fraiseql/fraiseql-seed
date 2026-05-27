"""
fraiseql-data - Schema-Aware Seed Data Generation

Provides intelligent seed data generation based on PostgreSQL schema introspection.
"""

from fraiseql_data.builder import SeedBuilder
from fraiseql_data.decorators import seed_data
from fraiseql_data.generators.base import BaseGenerator
from fraiseql_data.generators.groups import ColumnGroup
from fraiseql_data.generators.registry import (
    clear_generators,
    list_generators,
    register_generator,
)
from fraiseql_data.models import SeedRow, Seeds, ValidationResult

__version__ = "0.2.0"

__all__ = [
    "BaseGenerator",
    "ColumnGroup",
    "SeedBuilder",
    "SeedRow",
    "Seeds",
    "ValidationResult",
    "clear_generators",
    "list_generators",
    "register_generator",
    "seed_data",
]
