"""Tests for override priority over FK auto-resolution.

Phase 01: These tests exercise _generate_rows directly to verify that
overrides are applied before FK resolution, independent of the
validate_plan check (relaxed in Phase 02).
"""

from fraiseql_data import SeedBuilder
from fraiseql_data.models import SeedPlan
from psycopg import Connection


def test_override_bypasses_fk_resolution(db_conn: Connection, test_schema: str):
    """Override on FK column should be applied without FK resolution running.

    When fk_manufacturer has an override, _generate_rows should NOT raise
    ForeignKeyResolutionError even if the parent table is absent from
    generated_data.
    """
    builder = SeedBuilder(db_conn, schema=test_schema)
    table_info = builder.introspector.get_table_info("tb_model")
    plan = SeedPlan(table="tb_model", count=3, overrides={"fk_manufacturer": 42})

    # generated_data is empty — no parent table data available.
    # Before fix: ForeignKeyResolutionError is raised.
    rows = builder._generate_rows(table_info, plan, generated_data={})

    assert len(rows) == 3
    for row in rows:
        assert row["fk_manufacturer"] == 42


def test_callable_override_on_fk_column(db_conn: Connection, test_schema: str):
    """Callable override on FK column should receive counter and bypass FK resolution."""
    builder = SeedBuilder(db_conn, schema=test_schema)
    table_info = builder.introspector.get_table_info("tb_model")
    plan = SeedPlan(
        table="tb_model",
        count=3,
        overrides={"fk_manufacturer": lambda counter: counter * 10},
    )

    rows = builder._generate_rows(table_info, plan, generated_data={})

    assert len(rows) == 3
    assert rows[0]["fk_manufacturer"] == 10
    assert rows[1]["fk_manufacturer"] == 20
    assert rows[2]["fk_manufacturer"] == 30
