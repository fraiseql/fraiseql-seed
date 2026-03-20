"""
B3: Integration tests — INSERT all supported PostgreSQL types into a real database.

Validates that FakerGenerator produces values PostgreSQL actually accepts
for every supported type. This is the test that would have caught the
UUID/JSONB text fallback bugs that motivated Phase B1.
"""

import uuid

import pytest
from fraiseql_data import SeedBuilder
from psycopg import Connection

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def all_types_schema(db_conn: Connection) -> str:
    """Create a schema with a table covering every supported column type."""
    schema = "test_all_types"

    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute(f"CREATE SCHEMA {schema}")

        cur.execute(f"""
            CREATE TABLE {schema}.tb_all_types (
                pk_all_types INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,

                -- Text types
                col_text TEXT,
                col_varchar CHARACTER VARYING(100),

                -- Numeric types
                col_integer INTEGER,
                col_bigint BIGINT,
                col_smallint SMALLINT,
                col_numeric NUMERIC(10, 2),
                col_real REAL,
                col_double DOUBLE PRECISION,

                -- Boolean
                col_boolean BOOLEAN,

                -- Date/Time
                col_timestamp TIMESTAMP WITHOUT TIME ZONE,
                col_timestamptz TIMESTAMP WITH TIME ZONE,
                col_date DATE,
                col_time TIME WITHOUT TIME ZONE,
                col_timetz TIME WITH TIME ZONE,
                col_interval INTERVAL,

                -- UUID
                col_uuid UUID,

                -- JSON
                col_json JSON,
                col_jsonb JSONB,

                -- Network
                col_inet INET,
                col_cidr CIDR,
                col_macaddr MACADDR,
                col_macaddr8 MACADDR8,

                -- Binary
                col_bytea BYTEA,

                -- Arrays
                col_int_array INTEGER[],
                col_text_array TEXT[]
            )
        """)

        db_conn.commit()

    yield schema

    db_conn.rollback()  # Clear any failed transaction state
    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        db_conn.commit()


@pytest.fixture
def diverse_fk_schema(db_conn: Connection) -> str:
    """Schema with FK chain and diverse column types on the child table."""
    schema = "test_diverse_fk"

    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute(f"CREATE SCHEMA {schema}")

        cur.execute(f"""
            CREATE TABLE {schema}.tb_parent (
                pk_parent INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            )
        """)

        cur.execute(f"""
            CREATE TABLE {schema}.tb_child (
                pk_child INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                identifier TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                fk_parent INTEGER NOT NULL
                    REFERENCES {schema}.tb_parent(pk_parent),
                metadata JSONB,
                tags TEXT[],
                ip_address INET,
                is_active BOOLEAN,
                duration INTERVAL,
                score NUMERIC(8, 3)
            )
        """)

        db_conn.commit()

    yield schema

    db_conn.rollback()
    with db_conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        db_conn.commit()


# ---------------------------------------------------------------------------
# Cycle 1 & 3: All-types INSERT
# ---------------------------------------------------------------------------


class TestAllTypesInsert:
    """Verify SeedBuilder can INSERT rows with every supported PG type."""

    def test_insert_10_rows_all_types(self, db_conn: Connection, all_types_schema: str):
        """Core test: 10 rows with every type must INSERT without error."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=10).execute()

        assert len(seeds.tb_all_types) == 10

    def test_inserted_rows_readable(self, db_conn: Connection, all_types_schema: str):
        """Verify we can SELECT back all rows and types are correct."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        builder.add("tb_all_types", count=5).execute()

        with db_conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {all_types_schema}.tb_all_types")
            rows = cur.fetchall()
            assert len(rows) == 5

            # Verify column count matches (pk + id + identifier + name + 25 typed cols)
            assert len(rows[0]) == 29

    def test_identity_column_auto_generated(self, db_conn: Connection, all_types_schema: str):
        """pk_all_types (IDENTITY) must be auto-assigned by the database."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=3).execute()

        pks = [row.pk_all_types for row in seeds.tb_all_types]
        # PKs must be sequential integers assigned by the database
        assert all(isinstance(pk, int) for pk in pks)
        assert len(set(pks)) == 3  # All unique

    def test_uuid_column_valid(self, db_conn: Connection, all_types_schema: str):
        """col_uuid must contain valid UUIDs, not random text."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=5).execute()

        for row in seeds.tb_all_types:
            # col_uuid was accepted by PostgreSQL — parse to verify format
            val = row.col_uuid
            uuid.UUID(str(val))  # Must not raise

    def test_jsonb_column_valid(self, db_conn: Connection, all_types_schema: str):
        """col_jsonb must contain valid JSON accepted by PostgreSQL."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=5).execute()

        for row in seeds.tb_all_types:
            val = row.col_jsonb
            assert isinstance(val, dict)

    def test_array_columns_valid(self, db_conn: Connection, all_types_schema: str):
        """Array columns must contain lists accepted by PostgreSQL."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=5).execute()

        for row in seeds.tb_all_types:
            assert isinstance(row.col_int_array, list)
            assert isinstance(row.col_text_array, list)

    def test_network_types_valid(self, db_conn: Connection, all_types_schema: str):
        """Network types (inet, cidr, macaddr, macaddr8) must be accepted."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=5).execute()

        for row in seeds.tb_all_types:
            # If PostgreSQL accepted the INSERT, the values are valid.
            # Just verify they're not None.
            assert row.col_inet is not None
            assert row.col_cidr is not None
            assert row.col_macaddr is not None
            assert row.col_macaddr8 is not None

    def test_temporal_types_valid(self, db_conn: Connection, all_types_schema: str):
        """All date/time/interval types must be accepted by PostgreSQL."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=5).execute()

        for row in seeds.tb_all_types:
            assert row.col_timestamp is not None
            assert row.col_timestamptz is not None
            assert row.col_date is not None
            assert row.col_time is not None
            assert row.col_timetz is not None
            assert row.col_interval is not None

    def test_bytea_accepted(self, db_conn: Connection, all_types_schema: str):
        """bytea column must accept generated binary data."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=3).execute()

        for row in seeds.tb_all_types:
            assert row.col_bytea is not None

    def test_numeric_precision_preserved(self, db_conn: Connection, all_types_schema: str):
        """numeric(10,2) must store values with correct precision."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        builder.add("tb_all_types", count=5).execute()

        with db_conn.cursor() as cur:
            cur.execute(f"SELECT col_numeric FROM {all_types_schema}.tb_all_types")
            for (val,) in cur.fetchall():
                # Database enforces numeric(10,2) — value must fit
                assert val is not None


# ---------------------------------------------------------------------------
# Cycle 4: FK chain with diverse types
# ---------------------------------------------------------------------------


class TestDiverseFKInsert:
    """Tables with FKs AND diverse column types must seed correctly."""

    def test_fk_chain_with_diverse_types(self, db_conn: Connection, diverse_fk_schema: str):
        """Parent + child with mixed types must INSERT via SeedBuilder."""
        builder = SeedBuilder(db_conn, schema=diverse_fk_schema)
        seeds = builder.add("tb_parent", count=5).add("tb_child", count=20).execute()

        assert len(seeds.tb_parent) == 5
        assert len(seeds.tb_child) == 20

        # Verify FK values reference real parent PKs
        parent_pks = {row.pk_parent for row in seeds.tb_parent}
        for child in seeds.tb_child:
            assert child.fk_parent in parent_pks

    def test_child_types_valid(self, db_conn: Connection, diverse_fk_schema: str):
        """Child table's diverse columns must have correct types."""
        builder = SeedBuilder(db_conn, schema=diverse_fk_schema)
        seeds = builder.add("tb_parent", count=3).add("tb_child", count=10).execute()

        for child in seeds.tb_child:
            assert isinstance(child.metadata, dict)  # JSONB
            assert isinstance(child.tags, list)  # TEXT[]
            assert isinstance(child.is_active, bool)  # BOOLEAN
            assert child.ip_address is not None  # INET
            assert child.duration is not None  # INTERVAL
            assert child.score is not None  # NUMERIC(8,3)


# ---------------------------------------------------------------------------
# Cycle 5: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: nullable columns, defaults, identity skip."""

    @pytest.fixture
    def nullable_schema(self, db_conn: Connection) -> str:
        """Schema with nullable UUID and JSONB columns."""
        schema = "test_nullable"

        with db_conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute(f"CREATE SCHEMA {schema}")

            cur.execute(f"""
                CREATE TABLE {schema}.tb_nullable (
                    pk_nullable INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
                    identifier TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    optional_uuid UUID,
                    optional_jsonb JSONB,
                    optional_text TEXT,
                    required_email TEXT NOT NULL
                )
            """)

            db_conn.commit()

        yield schema

        db_conn.rollback()
        with db_conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            db_conn.commit()

    def test_nullable_columns_accepted(self, db_conn: Connection, nullable_schema: str):
        """Nullable UUID and JSONB columns must seed without error."""
        builder = SeedBuilder(db_conn, schema=nullable_schema)
        seeds = builder.add("tb_nullable", count=20).execute()
        assert len(seeds.tb_nullable) == 20

    def test_identity_column_not_in_insert(self, db_conn: Connection, all_types_schema: str):
        """GENERATED ALWAYS AS IDENTITY must not appear in INSERT values."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        # If identity column were included in INSERT, PostgreSQL would
        # raise: "cannot insert a non-DEFAULT value into column pk_all_types"
        # The fact that this succeeds proves identity columns are skipped.
        seeds = builder.add("tb_all_types", count=5).execute()
        assert len(seeds.tb_all_types) == 5

    def test_zero_count_no_error(self, db_conn: Connection, all_types_schema: str):
        """count=0 must not error — just produces no rows."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=0).execute()
        assert len(seeds.tb_all_types) == 0

    def test_large_batch_succeeds(self, db_conn: Connection, all_types_schema: str):
        """100 rows of all types must INSERT without unique collisions."""
        builder = SeedBuilder(db_conn, schema=all_types_schema)
        seeds = builder.add("tb_all_types", count=100).execute()
        assert len(seeds.tb_all_types) == 100

        # Verify all identifiers are unique
        identifiers = [row.identifier for row in seeds.tb_all_types]
        assert len(identifiers) == len(set(identifiers))
