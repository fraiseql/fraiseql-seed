"""Pytest decorators for seed data generation."""

from collections.abc import Callable
from typing import Any


def seed_data(
    table: str,
    count: int,
    strategy: str = "faker",
    overrides: dict[str, Any] | None = None,
):
    """
    Decorator to inject seed data into pytest test functions.

    Usage:
        @seed_data("tb_manufacturer", count=5)
        def test_api(seeds, db_conn, test_schema):
            assert len(seeds.tb_manufacturer) == 5

    The decorator works with the `seeds` pytest fixture defined in conftest.py.
    """

    def decorator(func: Callable) -> Callable:
        # Get existing seed plans or create new list
        if not hasattr(func, "_seed_plans"):
            func._seed_plans = []

        # Add this seed plan to function metadata
        func._seed_plans.append(
            {
                "table": table,
                "count": count,
                "strategy": strategy,
                "overrides": overrides or {},
            }
        )

        # Return original function (fixture will handle execution)
        return func

    return decorator
