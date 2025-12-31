"""Custom exceptions with helpful error messages."""


class FraiseQLDataError(Exception):
    """Base exception for fraiseql-data errors."""

    pass


class SchemaNotFoundError(FraiseQLDataError):
    """Schema does not exist in database."""

    def __init__(self, schema: str):
        super().__init__(
            f"Schema '{schema}' not found in database.\n\n"
            f"Suggestions:\n"
            f"1. Check schema name spelling\n"
            f"2. Ensure schema exists: CREATE SCHEMA {schema};\n"
            f"3. Check database connection settings"
        )


class TableNotFoundError(FraiseQLDataError):
    """Table does not exist in schema."""

    def __init__(self, table: str, schema: str):
        super().__init__(
            f"Table '{table}' not found in schema '{schema}'.\n\n"
            f"Suggestions:\n"
            f"1. Check table name spelling\n"
            f"2. Use SchemaIntrospector.get_tables() to see available tables\n"
            f"3. Ensure table exists: CREATE TABLE {schema}.{table} (...);"
        )


class ColumnGenerationError(FraiseQLDataError):
    """Could not auto-generate data for column."""

    def __init__(self, column: str, pg_type: str, table: str):
        super().__init__(
            f"Could not auto-generate data for column '{column}' "
            f"(type: {pg_type}) in table '{table}'.\n\n"
            f"Suggestions:\n"
            f"1. Provide override:\n"
            f"   builder.add('{table}', count=5, overrides={{\n"
            f"       '{column}': lambda: your_custom_value()\n"
            f"   }})\n\n"
            f"2. Use custom generator:\n"
            f"   from faker import Faker\n"
            f"   fake = Faker()\n"
            f"   builder.add('{table}', overrides={{\n"
            f"       '{column}': lambda: fake.your_method()\n"
            f"   }})"
        )


class CircularDependencyError(FraiseQLDataError):
    """Circular dependency detected in table relationships."""

    def __init__(self, tables: set[str]):
        tables_str = ", ".join(sorted(tables))
        super().__init__(
            f"Circular dependency detected involving tables: {tables_str}\n\n"
            f"Suggestions:\n"
            f"1. Check foreign key relationships for cycles\n"
            f"2. If self-referencing table, this will be supported in Phase 2\n"
            f"3. Temporarily remove FK constraint, seed data, then re-add constraint"
        )


class MissingDependencyError(FraiseQLDataError):
    """Table depends on another table that is not in seed plan."""

    def __init__(self, table: str, dependency: str):
        super().__init__(
            f"Table '{table}' depends on '{dependency}', "
            f"but '{dependency}' is not in seed plan.\n\n"
            f"Suggestions:\n"
            f"1. Add dependency to seed plan:\n"
            f"   builder.add('{dependency}', count=N)\n"
            f"   builder.add('{table}', count=M)\n\n"
            f"2. Or use decorator:\n"
            f"   @seed_data('{dependency}', count=N)\n"
            f"   @seed_data('{table}', count=M)\n"
            f"   def test_fn(seeds): ..."
        )


class ForeignKeyResolutionError(FraiseQLDataError):
    """Could not resolve foreign key reference."""

    def __init__(self, fk_column: str, referenced_table: str):
        super().__init__(
            f"Could not resolve foreign key '{fk_column}' referencing '{referenced_table}'.\n\n"
            f"Suggestions:\n"
            f"1. Ensure '{referenced_table}' is seeded before this table\n"
            f"2. Check that '{referenced_table}' has generated data\n"
            f"3. Verify foreign key constraint is correct"
        )
