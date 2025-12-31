"""
FraiseQL Seed - Seed data management for FraiseQL projects with Trinity pattern.

This package provides tools for:
- Auto-generating staging schemas from production schemas
- Converting UUID-based seed data to INTEGER-based production data
- Validating schema compatibility and data integrity
- Managing seed data loading and database resets
"""

__version__ = "0.1.0"

from fraiseql_seed.core.models import Column, ForeignKey, TableInfo, TrinityPattern

__all__ = ["Column", "ForeignKey", "TableInfo", "TrinityPattern", "__version__"]
