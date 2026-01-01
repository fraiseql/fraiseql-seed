"""Integration tests for full UUID pattern workflow."""

import pytest
from fraiseql_uuid import (
    Pattern,
    UUIDCache,
    UUIDDecoder,
    UUIDGenerator,
    UUIDValidator,
)


class TestFullWorkflow:
    """Tests for complete UUID workflow."""

    def test_generate_validate_decode_workflow(self) -> None:
        """Test full workflow: generate -> validate -> decode."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        # Generate UUID
        uuid = generator.generate(instance=1)

        # Validate UUID
        validation_result = validator.validate(uuid)
        assert validation_result.valid is True

        # Decode UUID
        decoded = decoder.decode(uuid)
        assert decoded["table_code"] == "012345"
        assert decoded["instance"] == 1

    def test_batch_generate_validate_decode_workflow(self) -> None:
        """Test workflow with batch generation."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="123456")
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        # Generate batch
        uuids = generator.generate_batch(count=5)

        # Validate and decode each
        for i, uuid in enumerate(uuids, start=1):
            # Validate
            validation_result = validator.validate(uuid)
            assert validation_result.valid is True

            # Decode
            decoded = decoder.decode(uuid)
            assert decoded["table_code"] == "123456"
            assert decoded["instance"] == i

    def test_workflow_with_all_components(self) -> None:
        """Test workflow with all UUID components set."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="987654",
            seed_dir=22,
            function=42,
            scenario=100,
            test_case=5,
        )
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        # Generate
        uuid = generator.generate(instance=999)

        # Validate
        validation_result = validator.validate(uuid)
        assert validation_result.valid is True

        # Decode and verify all components
        decoded = decoder.decode(uuid)
        assert decoded["table_code"] == "987654"
        assert decoded["seed_dir"] == 22
        assert decoded["function"] == 42
        assert decoded["scenario"] == 100
        assert decoded["test_case"] == 5
        assert decoded["instance"] == 999


class TestWorkflowWithCache:
    """Tests for UUID workflow with caching."""

    def test_generate_and_cache_workflow(self) -> None:
        """Test generating and caching UUIDs."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        cache = UUIDCache()

        # Generate and cache
        uuid1 = generator.generate(instance=1)
        cache.set("users", 1, uuid1)

        # Retrieve from cache
        cached_uuid = cache.get("users", 1)
        assert cached_uuid == uuid1

    def test_cache_batch_workflow(self) -> None:
        """Test caching batch of UUIDs."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        cache = UUIDCache()

        # Generate batch
        uuids = generator.generate_batch(count=10)

        # Cache all
        for i, uuid in enumerate(uuids, start=1):
            cache.set("users", i, uuid)

        # Verify all cached
        for i, expected_uuid in enumerate(uuids, start=1):
            assert cache.get("users", i) == expected_uuid

    def test_validate_cached_uuids(self) -> None:
        """Test validating UUIDs retrieved from cache."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="012345")
        validator = UUIDValidator(pattern)
        cache = UUIDCache()

        # Generate, cache, retrieve, validate
        for instance in range(1, 6):
            uuid = generator.generate(instance=instance)
            cache.set("users", instance, uuid)

            cached_uuid = cache.get("users", instance)
            validation_result = validator.validate(cached_uuid)
            assert validation_result.valid is True


class TestMultiTableWorkflow:
    """Tests for multi-table UUID workflows."""

    def test_multiple_tables_independent(self) -> None:
        """Test that multiple tables have independent UUIDs."""
        pattern = Pattern()
        cache = UUIDCache()

        # Create generators for different tables
        users_gen = UUIDGenerator(pattern, table_code="111111")
        posts_gen = UUIDGenerator(pattern, table_code="222222")
        comments_gen = UUIDGenerator(pattern, table_code="333333")

        # Generate UUIDs
        user_uuid = users_gen.generate(instance=1)
        post_uuid = posts_gen.generate(instance=1)
        comment_uuid = comments_gen.generate(instance=1)

        # Cache them
        cache.set("users", 1, user_uuid)
        cache.set("posts", 1, post_uuid)
        cache.set("comments", 1, comment_uuid)

        # Verify they're different
        assert user_uuid != post_uuid
        assert post_uuid != comment_uuid
        assert user_uuid.startswith("111111")
        assert post_uuid.startswith("222222")
        assert comment_uuid.startswith("333333")

    def test_multiple_tables_with_validation(self) -> None:
        """Test validating UUIDs from multiple tables."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        generators = {
            "users": UUIDGenerator(pattern, table_code="100000"),
            "posts": UUIDGenerator(pattern, table_code="200000"),
            "comments": UUIDGenerator(pattern, table_code="300000"),
        }

        # Generate and validate from each table
        for _table_name, generator in generators.items():
            uuid = generator.generate(instance=1)
            validation_result = validator.validate(uuid)
            assert validation_result.valid is True


class TestRoundTripWorkflow:
    """Tests for complete round-trip workflows."""

    def test_complete_round_trip(self) -> None:
        """Test complete round-trip: params -> generate -> decode -> verify params."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern)

        original_params = {
            "table_code": "456789",
            "seed_dir": 23,
            "function": 1337,
            "scenario": 5678,
            "test_case": 99,
            "instance": 123456,
        }

        # Generate from params
        uuid = generator.generate(**original_params)

        # Decode back
        decoder = UUIDDecoder(pattern)
        decoded = decoder.decode(uuid)

        # Verify all params match
        assert decoded["table_code"] == "456789"
        assert decoded["seed_dir"] == 23
        assert decoded["function"] == 1337
        assert decoded["scenario"] == 5678
        assert decoded["test_case"] == 99
        assert decoded["instance"] == 123456

    def test_round_trip_batch(self) -> None:
        """Test round-trip with batch of UUIDs."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="111222",
            seed_dir=22,
            function=10,
        )
        decoder = UUIDDecoder(pattern)

        # Generate batch
        uuids = generator.generate_batch(count=20, start_instance=100)

        # Decode and verify each
        for i, uuid in enumerate(uuids):
            decoded = decoder.decode(uuid)
            assert decoded["table_code"] == "111222"
            assert decoded["seed_dir"] == 22
            assert decoded["function"] == 10
            assert decoded["instance"] == 100 + i

    def test_round_trip_with_validation_and_cache(self) -> None:
        """Test complete workflow with all components."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="999888")
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)
        cache = UUIDCache()

        # Generate
        uuid = generator.generate(instance=42)

        # Validate
        validation_result = validator.validate(uuid)
        assert validation_result.valid is True

        # Cache
        cache.set("items", 42, uuid)

        # Retrieve from cache
        cached_uuid = cache.get("items", 42)
        assert cached_uuid == uuid

        # Decode cached UUID
        decoded = decoder.decode(cached_uuid)
        assert decoded["table_code"] == "999888"
        assert decoded["instance"] == 42


class TestErrorHandlingWorkflow:
    """Tests for error handling in workflows."""

    def test_validate_before_decode(self) -> None:
        """Test validating invalid UUID before attempting decode."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        invalid_uuid = "not-a-valid-uuid"

        # Validation should catch the error
        validation_result = validator.validate(invalid_uuid)
        assert validation_result.valid is False

        # Decode should raise error
        with pytest.raises(ValueError):
            decoder.decode(invalid_uuid)

    def test_workflow_with_invalid_uuids(self) -> None:
        """Test workflow handling of invalid UUIDs."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        invalid_uuids = [
            "not-a-uuid",
            "",
            "01234521-0000-1000-8000-000000000001",  # wrong version
            "01234521-0000-4000-9000-000000000001",  # wrong variant
        ]

        for invalid_uuid in invalid_uuids:
            validation_result = validator.validate(invalid_uuid)
            assert validation_result.valid is False
            assert validation_result.error is not None


class TestEdgeCaseWorkflows:
    """Tests for edge case workflows."""

    def test_workflow_with_max_values(self) -> None:
        """Test workflow with maximum component values."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="999999",
            seed_dir=99,
            function=9999,
            scenario=9999,
            test_case=99,
        )
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        # Generate with max instance
        uuid = generator.generate(instance=999999999999)

        # Validate
        validation_result = validator.validate(uuid)
        assert validation_result.valid is True

        # Decode
        decoded = decoder.decode(uuid)
        assert decoded["instance"] == 999999999999

    def test_workflow_with_zero_values(self) -> None:
        """Test workflow with zero values."""
        pattern = Pattern()
        generator = UUIDGenerator(
            pattern,
            table_code="000000",
            seed_dir=0,
            function=0,
            scenario=0,
            test_case=0,
        )
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)

        # Generate with zero instance
        uuid = generator.generate(instance=0)

        # Validate
        validation_result = validator.validate(uuid)
        assert validation_result.valid is True

        # Decode
        decoded = decoder.decode(uuid)
        assert decoded["instance"] == 0
        assert decoded["table_code"] == "000000"

    def test_reusable_components_workflow(self) -> None:
        """Test that all components can be reused across workflow."""
        pattern = Pattern()
        generator = UUIDGenerator(pattern, table_code="555555")
        validator = UUIDValidator(pattern)
        decoder = UUIDDecoder(pattern)
        cache = UUIDCache()

        # Use all components multiple times
        for instance in range(1, 11):
            # Generate
            uuid = generator.generate(instance=instance)

            # Validate
            validation_result = validator.validate(uuid)
            assert validation_result.valid is True

            # Cache
            cache.set("items", instance, uuid)

            # Retrieve and decode
            cached_uuid = cache.get("items", instance)
            decoded = decoder.decode(cached_uuid)
            assert decoded["instance"] == instance
