"""Tests for UUIDValidator class."""

from fraiseql_uuid import Pattern, UUIDValidator, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_valid(self) -> None:
        """Test creating valid ValidationResult."""
        result = ValidationResult(valid=True)

        assert result.valid is True
        assert result.error is None
        assert result.warnings == []

    def test_validation_result_invalid(self) -> None:
        """Test creating invalid ValidationResult."""
        result = ValidationResult(valid=False, error="Invalid format")

        assert result.valid is False
        assert result.error == "Invalid format"
        assert result.warnings == []

    def test_validation_result_with_warnings(self) -> None:
        """Test creating ValidationResult with warnings."""
        warnings = ["Warning 1", "Warning 2"]
        result = ValidationResult(valid=True, warnings=warnings)

        assert result.valid is True
        assert result.error is None
        assert result.warnings == warnings

    def test_validation_result_warnings_default(self) -> None:
        """Test that warnings defaults to empty list."""
        result = ValidationResult(valid=True)

        assert result.warnings == []
        assert isinstance(result.warnings, list)


class TestUUIDValidatorInit:
    """Tests for UUIDValidator.__init__()."""

    def test_init_with_pattern(self) -> None:
        """Test initialization with pattern."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        assert validator.pattern is pattern


class TestUUIDValidatorValidate:
    """Tests for UUIDValidator.validate()."""

    def test_validate_valid_uuid(self) -> None:
        """Test validating a valid UUID."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("01234521-0000-4000-8000-000000000001")

        assert result.valid is True
        assert result.error is None
        assert result.warnings == []

    def test_validate_valid_uuid_with_all_components(self) -> None:
        """Test validating UUID with all components set."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("12345622-0042-4123-8415-000000000999")

        assert result.valid is True
        assert result.error is None

    def test_validate_invalid_format(self) -> None:
        """Test validating UUID with invalid format."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("not-a-uuid")

        assert result.valid is False
        assert result.error is not None
        assert "Invalid UUID format" in result.error

    def test_validate_empty_string(self) -> None:
        """Test validating empty string."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("")

        assert result.valid is False
        assert result.error is not None
        assert "Invalid UUID format" in result.error

    def test_validate_wrong_version(self) -> None:
        """Test validating UUID with wrong version."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        # Version 1 UUID (has '1' instead of '4')
        result = validator.validate("01234521-0000-1000-8000-000000000001")

        assert result.valid is False
        assert result.error is not None

    def test_validate_wrong_variant(self) -> None:
        """Test validating UUID with wrong variant."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        # Variant should be '8', not '9'
        result = validator.validate("01234521-0000-4000-9000-000000000001")

        assert result.valid is False
        assert result.error is not None

    def test_validate_wrong_segment_count(self) -> None:
        """Test validating UUID with wrong number of segments."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("01234521-0000-4000-000000000001")

        assert result.valid is False
        assert result.error is not None

    def test_validate_wrong_segment_lengths(self) -> None:
        """Test validating UUID with wrong segment lengths."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("0123-0000-4000-8000-000000000001")

        assert result.valid is False
        assert result.error is not None

    def test_validate_non_numeric_characters(self) -> None:
        """Test validating UUID with non-numeric characters."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("0123XX21-0000-4000-8000-000000000001")

        assert result.valid is False
        assert result.error is not None

    def test_validate_strict_mode(self) -> None:
        """Test validation in strict mode."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("01234521-0000-4000-8000-000000000001", strict=True)

        assert result.valid is True

    def test_validate_non_strict_mode(self) -> None:
        """Test validation in non-strict mode."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)
        result = validator.validate("01234521-0000-4000-8000-000000000001", strict=False)

        assert result.valid is True


class TestUUIDValidatorBatch:
    """Tests for validating multiple UUIDs."""

    def test_validate_multiple_valid_uuids(self) -> None:
        """Test validating multiple valid UUIDs."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        uuids = [
            "01234521-0000-4000-8000-000000000001",
            "12345622-0042-4123-8415-000000000999",
            "99999999-9999-4999-8999-999999999999",
        ]

        for uuid in uuids:
            result = validator.validate(uuid)
            assert result.valid is True

    def test_validate_mixed_valid_invalid(self) -> None:
        """Test validating mix of valid and invalid UUIDs."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        test_cases = [
            ("01234521-0000-4000-8000-000000000001", True),
            ("not-a-uuid", False),
            ("12345622-0042-4123-8415-000000000999", True),
            ("", False),
            ("01234521-0000-1000-8000-000000000001", False),  # wrong version
        ]

        for uuid, expected_valid in test_cases:
            result = validator.validate(uuid)
            assert result.valid == expected_valid


class TestUUIDValidatorEdgeCases:
    """Edge case tests for UUIDValidator."""

    def test_validate_max_values(self) -> None:
        """Test validating UUID with maximum values."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        uuid = pattern.generate(
            table_code="999999",
            seed_dir=99,
            function=9999,
            scenario=9999,
            test_case=99,
            instance=999999999999,
        )

        result = validator.validate(uuid)
        assert result.valid is True

    def test_validate_zero_values(self) -> None:
        """Test validating UUID with all zeros."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        uuid = pattern.generate(
            table_code="000000",
            seed_dir=0,
            function=0,
            scenario=0,
            test_case=0,
            instance=0,
        )

        result = validator.validate(uuid)
        assert result.valid is True

    def test_validator_reuse(self) -> None:
        """Test that validator can be reused multiple times."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        result1 = validator.validate("01234521-0000-4000-8000-000000000001")
        result2 = validator.validate("not-a-uuid")
        result3 = validator.validate("12345622-0042-4123-8415-000000000999")

        assert result1.valid is True
        assert result2.valid is False
        assert result3.valid is True

    def test_multiple_validators_independent(self) -> None:
        """Test that multiple validators are independent."""
        pattern = Pattern()
        validator1 = UUIDValidator(pattern)
        validator2 = UUIDValidator(pattern)

        uuid = "01234521-0000-4000-8000-000000000001"

        result1 = validator1.validate(uuid)
        result2 = validator2.validate(uuid)

        assert result1.valid is True
        assert result2.valid is True

    def test_validate_generated_uuid(self) -> None:
        """Test validating a freshly generated UUID."""
        pattern = Pattern()
        validator = UUIDValidator(pattern)

        uuid = pattern.generate(table_code="012345", instance=1)
        result = validator.validate(uuid)

        assert result.valid is True

    def test_validate_batch_generated_uuids(self) -> None:
        """Test validating batch of generated UUIDs."""
        from fraiseql_uuid import UUIDGenerator

        pattern = Pattern()
        validator = UUIDValidator(pattern)
        generator = UUIDGenerator(pattern, table_code="012345")

        uuids = generator.generate_batch(count=10)

        for uuid in uuids:
            result = validator.validate(uuid)
            assert result.valid is True
