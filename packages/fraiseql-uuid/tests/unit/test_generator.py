"""Tests for UUIDGenerator class."""

import pytest
from fraiseql_uuid import Pattern, UUIDGenerator


class TestUUIDGeneratorInit:
    """Tests for UUIDGenerator.__init__()."""

    def test_init_with_pattern(self) -> None:
        """Test initialization with pattern."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern)

        assert generator.pattern is pattern
        assert generator.defaults == {}

    def test_init_with_defaults(self) -> None:
        """Test initialization with default parameters."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345", seed_dir=22)

        assert generator.pattern is pattern
        assert generator.defaults == {"table_code": "012345", "seed_dir": 22}

    def test_init_with_all_defaults(self) -> None:
        """Test initialization with all default parameters."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="012345",
            seed_dir=22,
            function=42,
            scenario=100,
            test_case=5,
        )

        assert generator.defaults["table_code"] == "012345"
        assert generator.defaults["seed_dir"] == 22
        assert generator.defaults["function"] == 42
        assert generator.defaults["scenario"] == 100
        assert generator.defaults["test_case"] == 5


class TestUUIDGeneratorGenerate:
    """Tests for UUIDGenerator.generate()."""

    def test_generate_minimal(self) -> None:
        """Test generating UUID with minimal parameters."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuid = generator.generate(instance=1)

        assert uuid == "01234521-0000-4000-8000-000000000001"
        assert len(uuid) == 36

    def test_generate_with_defaults(self) -> None:
        """Test that generator uses defaults."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="012345",
            seed_dir=22,
            function=42,
        )
        uuid = generator.generate(instance=1)

        assert uuid == "01234522-0042-4000-8000-000000000001"

    def test_generate_with_override(self) -> None:
        """Test that generate parameters override defaults."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345", seed_dir=22)
        uuid = generator.generate(instance=1, seed_dir=23)

        # seed_dir should be overridden to 23
        assert uuid == "01234523-0000-4000-8000-000000000001"

    def test_generate_multiple_overrides(self) -> None:
        """Test overriding multiple defaults."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="012345",
            seed_dir=22,
            function=10,
            scenario=100,
        )
        uuid = generator.generate(
            instance=1,
            function=99,
            test_case=5,
        )

        # function and test_case overridden, scenario=100 (0100 split as 010/0)
        assert uuid == "01234522-0099-4010-8005-000000000001"

    def test_generate_requires_instance(self) -> None:
        """Test that instance is always required."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")

        with pytest.raises(TypeError):
            generator.generate()

    def test_generate_sequential_instances(self) -> None:
        """Test generating UUIDs with sequential instances."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")

        uuid1 = generator.generate(instance=1)
        uuid2 = generator.generate(instance=2)
        uuid3 = generator.generate(instance=3)

        assert uuid1 == "01234521-0000-4000-8000-000000000001"
        assert uuid2 == "01234521-0000-4000-8000-000000000002"
        assert uuid3 == "01234521-0000-4000-8000-000000000003"

    def test_generate_without_table_code_default(self) -> None:
        """Test that generate fails if table_code not in defaults or params."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern)

        with pytest.raises(KeyError):
            generator.generate(instance=1)


class TestUUIDGeneratorGenerateBatch:
    """Tests for UUIDGenerator.generate_batch()."""

    def test_generate_batch_basic(self) -> None:
        """Test generating batch of UUIDs."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuids = generator.generate_batch(count=3)

        assert len(uuids) == 3
        assert uuids[0] == "01234521-0000-4000-8000-000000000001"
        assert uuids[1] == "01234521-0000-4000-8000-000000000002"
        assert uuids[2] == "01234521-0000-4000-8000-000000000003"

    def test_generate_batch_with_start_instance(self) -> None:
        """Test generating batch with custom start instance."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuids = generator.generate_batch(count=3, start_instance=10)

        assert len(uuids) == 3
        assert uuids[0] == "01234521-0000-4000-8000-000000000010"
        assert uuids[1] == "01234521-0000-4000-8000-000000000011"
        assert uuids[2] == "01234521-0000-4000-8000-000000000012"

    def test_generate_batch_zero_count(self) -> None:
        """Test generating batch with zero count."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuids = generator.generate_batch(count=0)

        assert len(uuids) == 0
        assert uuids == []

    def test_generate_batch_single(self) -> None:
        """Test generating batch with single UUID."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuids = generator.generate_batch(count=1)

        assert len(uuids) == 1
        assert uuids[0] == "01234521-0000-4000-8000-000000000001"

    def test_generate_batch_with_defaults(self) -> None:
        """Test that batch generation uses defaults."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="012345",
            seed_dir=22,
            function=42,
        )
        uuids = generator.generate_batch(count=2)

        assert uuids[0] == "01234522-0042-4000-8000-000000000001"
        assert uuids[1] == "01234522-0042-4000-8000-000000000002"

    def test_generate_batch_with_overrides(self) -> None:
        """Test that batch generation accepts overrides."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345", seed_dir=22)
        uuids = generator.generate_batch(count=2, seed_dir=23, scenario=100)

        # All should have seed_dir=23 and scenario=100
        assert uuids[0] == "01234523-0000-4010-8000-000000000001"
        assert uuids[1] == "01234523-0000-4010-8000-000000000002"

    def test_generate_batch_large_count(self) -> None:
        """Test generating large batch of UUIDs."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        uuids = generator.generate_batch(count=100)

        assert len(uuids) == 100
        assert uuids[0] == "01234521-0000-4000-8000-000000000001"
        assert uuids[99] == "01234521-0000-4000-8000-000000000100"

        # Verify uniqueness
        assert len(set(uuids)) == 100

    def test_generate_batch_with_scenario_override(self) -> None:
        """Test that batch generation works with scenario override."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        # Pass scenario as override (not instance, which would conflict)
        uuids = generator.generate_batch(count=3, scenario=100)

        # Should have scenario=100 (0100 split as 010/0) in all UUIDs
        assert uuids[0] == "01234521-0000-4010-8000-000000000001"
        assert uuids[1] == "01234521-0000-4010-8000-000000000002"
        assert uuids[2] == "01234521-0000-4010-8000-000000000003"


class TestUUIDGeneratorEdgeCases:
    """Edge case tests for UUIDGenerator."""

    def test_generator_reuse(self) -> None:
        """Test that generator can be reused multiple times."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")

        uuid1 = generator.generate(instance=1)
        uuid2 = generator.generate(instance=2)
        batch = generator.generate_batch(count=2, start_instance=10)

        assert uuid1 == "01234521-0000-4000-8000-000000000001"
        assert uuid2 == "01234521-0000-4000-8000-000000000002"
        assert len(batch) == 2

    def test_multiple_generators_independent(self) -> None:
        """Test that multiple generators are independent."""
        pattern = Pattern()
        gen1 = UUIDGenerator(pattern, table_code="111111")
        gen2 = UUIDGenerator(pattern, table_code="222222")

        uuid1 = gen1.generate(instance=1)
        uuid2 = gen2.generate(instance=1)

        assert uuid1.startswith("111111")
        assert uuid2.startswith("222222")

    def test_generator_with_max_values(self) -> None:
        """Test generator with maximum values."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="999999",
            seed_dir=99,
            function=9999,
            scenario=9999,
            test_case=99,
        )
        uuid = generator.generate(instance=999999999999)

        decoded = pattern.decode(uuid)
        assert decoded["table_code"] == "999999"
        assert decoded["instance"] == 999999999999

    def test_generator_with_zero_values(self) -> None:
        """Test generator with zero values."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="000000",
            seed_dir=0,
            function=0,
            scenario=0,
            test_case=0,
        )
        uuid = generator.generate(instance=0)

        assert uuid == "00000000-0000-4000-8000-000000000000"
