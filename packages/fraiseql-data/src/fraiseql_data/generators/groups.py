"""Column groups for correlated multi-column generation."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnGroup:
    """A group of semantically related columns generated atomically."""

    name: str
    fields: frozenset[str]
    generator: Callable[[dict[str, Any]], dict[str, Any]]
    min_match: int = 2


def _generate_address_stub(_context: dict[str, Any]) -> dict[str, Any]:
    """Stub address generator (replaced in Cycle 2)."""
    return {}


def _generate_person_stub(_context: dict[str, Any]) -> dict[str, Any]:
    """Stub person generator (replaced in Cycle 3)."""
    return {}


def _generate_geo_stub(_context: dict[str, Any]) -> dict[str, Any]:
    """Stub geo generator (replaced in Cycle 6)."""
    return {}


BUILTIN_GROUPS: list[ColumnGroup] = [
    ColumnGroup(
        name="address",
        fields=frozenset(
            {
                "country",
                "state",
                "city",
                "postal_code",
                "street",
                "address",
                "zip",
                "zipcode",
                "zip_code",
            }
        ),
        generator=_generate_address_stub,
    ),
    ColumnGroup(
        name="person",
        fields=frozenset({"first_name", "last_name", "name", "email"}),
        generator=_generate_person_stub,
    ),
    ColumnGroup(
        name="geo",
        fields=frozenset({"latitude", "longitude", "lat", "lng", "lon"}),
        generator=_generate_geo_stub,
    ),
]


class GroupRegistry:
    """Registry for detecting and managing column groups."""

    def __init__(self, groups: list[ColumnGroup] | None = None):
        self._groups = groups if groups is not None else BUILTIN_GROUPS

    def detect_groups(self, column_names: set[str]) -> list[ColumnGroup]:
        """Return active groups where >= min_match columns are present."""
        return [
            group for group in self._groups if len(column_names & group.fields) >= group.min_match
        ]

    def col_to_group(
        self,
        active_groups: list[ColumnGroup],
        column_names: set[str],
    ) -> dict[str, ColumnGroup]:
        """Build reverse lookup: column name -> owning group (only for existing columns)."""
        result: dict[str, ColumnGroup] = {}
        for group in active_groups:
            for col in group.fields & column_names:
                result[col] = group
        return result
