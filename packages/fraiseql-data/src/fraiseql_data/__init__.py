"""
fraiseql-data - Schema-Aware Seed Data Generation

Provides intelligent seed data generation based on PostgreSQL schema introspection.
"""

from fraiseql_data.builder import SeedBuilder
from fraiseql_data.decorators import seed_data
from fraiseql_data.generators.base import BaseGenerator
from fraiseql_data.generators.registry import (
    clear_generators,
    list_generators,
    register_generator,
)
from fraiseql_data.models import SeedRow, Seeds

__version__ = "0.1.0"

__all__ = [
    "SeedBuilder",
    "seed_data",
    "Seeds",
    "SeedRow",
    "BaseGenerator",
    "register_generator",
    "list_generators",
    "clear_generators",
]
