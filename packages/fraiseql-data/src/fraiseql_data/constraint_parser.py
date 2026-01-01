"""Parser for CHECK constraints to auto-generate valid data."""

import random
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckConstraintRule:
    """Base class for CHECK constraint rules."""

    column: str

    def generate(self) -> Any:
        """Generate value satisfying this constraint."""
        raise NotImplementedError


@dataclass
class EnumConstraintRule(CheckConstraintRule):
    """Rule for IN ('a', 'b', 'c') constraints."""

    values: list[str]

    def generate(self) -> str:
        """Pick random value from enum."""
        return random.choice(self.values)


@dataclass
class RangeConstraintRule(CheckConstraintRule):
    """Rule for range constraints (>, >=, <, <=)."""

    operator: str
    value: float

    def generate(self) -> float:
        """Generate value satisfying range constraint."""
        if self.operator == ">":
            # Generate value greater than threshold
            return self.value + random.uniform(1, 1000)
        elif self.operator == ">=":
            # Generate value greater than or equal to threshold
            return self.value + random.uniform(0, 1000)
        elif self.operator == "<":
            # Generate value less than threshold
            # Ensure positive values for common use cases
            if self.value > 1000:
                return random.uniform(1, self.value - 1)
            else:
                return max(0, self.value - random.uniform(1, 100))
        elif self.operator == "<=":
            # Generate value less than or equal to threshold
            if self.value > 1000:
                return random.uniform(1, self.value)
            else:
                return max(0, self.value - random.uniform(0, 100))
        else:
            raise ValueError(f"Unsupported operator: {self.operator}")


@dataclass
class BetweenConstraintRule(CheckConstraintRule):
    """Rule for BETWEEN min AND max."""

    min_value: float
    max_value: float

    def generate(self) -> float:
        """Generate value in range [min, max]."""
        return random.uniform(self.min_value, self.max_value)


@dataclass
class CombinedRangeRule(CheckConstraintRule):
    """Rule for combined range constraints (e.g., price > 0 AND price < 10000)."""

    min_value: float | None = None
    max_value: float | None = None
    min_inclusive: bool = False
    max_inclusive: bool = False

    def generate(self) -> float:
        """Generate value satisfying both bounds."""
        # Determine effective min/max
        if self.min_value is not None and self.max_value is not None:
            # Both bounds specified
            min_val = self.min_value if self.min_inclusive else self.min_value + 0.01
            max_val = self.max_value if self.max_inclusive else self.max_value - 0.01
            return random.uniform(min_val, max_val)
        elif self.min_value is not None:
            # Only lower bound
            min_val = self.min_value if self.min_inclusive else self.min_value + 1
            return min_val + random.uniform(0, 1000)
        elif self.max_value is not None:
            # Only upper bound
            max_val = self.max_value if self.max_inclusive else self.max_value - 1
            return max(0, max_val - random.uniform(0, 100))
        else:
            # No bounds (shouldn't happen)
            return random.uniform(0, 100)


class CheckConstraintParser:
    """
    Parse simple CHECK constraints to auto-generate valid data.

    Supports:
    - Enum checks: status IN ('a', 'b', 'c')
    - Range checks: price > 0, age >= 18, score < 100
    - BETWEEN: age BETWEEN 18 AND 65
    - Combined: price > 0 AND price < 10000

    Does NOT support:
    - Complex expressions: price * quantity > total
    - Function calls: length(name) > 5
    - Subqueries: customer_id IN (SELECT ...)
    """

    def parse(self, check_clause: str) -> CheckConstraintRule | None:
        """
        Parse CHECK clause into rule, or None if too complex.

        Args:
            check_clause: CHECK constraint condition (e.g., "price > 0")

        Returns:
            CheckConstraintRule if parseable, None otherwise
        """
        # Normalize: remove extra spaces, lowercase operators
        check_clause = " ".join(check_clause.split())

        # Try to parse as enum (IN constraint)
        enum_rule = self._parse_enum(check_clause)
        if enum_rule:
            return enum_rule

        # Try to parse as BETWEEN
        between_rule = self._parse_between(check_clause)
        if between_rule:
            return between_rule

        # Try to parse as combined range (e.g., price > 0 AND price < 10000)
        combined_rule = self._parse_combined_range(check_clause)
        if combined_rule:
            return combined_rule

        # Try to parse as single range constraint
        range_rule = self._parse_range(check_clause)
        if range_rule:
            return range_rule

        # Too complex to parse
        return None

    def _parse_enum(self, check_clause: str) -> EnumConstraintRule | None:
        """Parse IN ('val1', 'val2', ...) constraint or PostgreSQL's ANY(ARRAY[...]) format."""
        # Try PostgreSQL's internal format: column = ANY (ARRAY['val1'::text, ...])
        match = re.search(
            r"\(?(\w+)\s*=\s*ANY\s*\(\s*ARRAY\[(.+?)\]\s*\)",
            check_clause,
            re.IGNORECASE,
        )
        if match:
            column = match.group(1)
            values_str = match.group(2)

            # Extract quoted values (handle ::text casting)
            values = re.findall(r"'([^']+)'", values_str)
            if values:
                return EnumConstraintRule(column=column, values=values)

        # Try standard IN format: column IN ('val1', 'val2', ...)
        match = re.search(
            r"(\w+)\s+IN\s+\((.+?)\)",
            check_clause,
            re.IGNORECASE,
        )
        if not match:
            return None

        column = match.group(1)
        values_str = match.group(2)

        # Extract quoted values
        values = re.findall(r"'([^']+)'", values_str)
        if not values:
            # Try double quotes
            values = re.findall(r'"([^"]+)"', values_str)

        if values:
            return EnumConstraintRule(column=column, values=values)

        return None

    def _parse_between(self, check_clause: str) -> BetweenConstraintRule | None:
        """Parse BETWEEN min AND max constraint."""
        # Pattern: column BETWEEN min AND max
        match = re.search(
            r"(\w+)\s+BETWEEN\s+(\d+\.?\d*)\s+AND\s+(\d+\.?\d*)",
            check_clause,
            re.IGNORECASE,
        )
        if not match:
            return None

        column = match.group(1)
        min_val = float(match.group(2))
        max_val = float(match.group(3))

        return BetweenConstraintRule(column=column, min_value=min_val, max_value=max_val)

    def _parse_range(self, check_clause: str) -> RangeConstraintRule | None:
        """Parse single range constraint (>, >=, <, <=)."""
        # Pattern: column > value or column >= value
        match = re.search(
            r"(\w+)\s*(>|>=|<|<=)\s*(\d+\.?\d*)",
            check_clause,
        )
        if not match:
            return None

        column = match.group(1)
        operator = match.group(2)
        value = float(match.group(3))

        return RangeConstraintRule(column=column, operator=operator, value=value)

    def _parse_combined_range(self, check_clause: str) -> CombinedRangeRule | None:
        """
        Parse combined range constraints (e.g., price > 0 AND price < 10000).

        Supports:
        - column > min AND column < max
        - column >= min AND column <= max
        - (column > min) AND (column < max)
        """
        # Look for AND combining two constraints on same column
        if " AND " not in check_clause.upper():
            return None

        # Split by AND (case-insensitive)
        parts = re.split(r"\s+AND\s+", check_clause, flags=re.IGNORECASE)
        if len(parts) != 2:
            return None

        # Parse each part as a range constraint
        rule1 = self._parse_range(parts[0].strip("()"))
        rule2 = self._parse_range(parts[1].strip("()"))

        if not rule1 or not rule2:
            return None

        # Check if both constraints are on same column
        if rule1.column != rule2.column:
            return None

        # Combine into single rule
        combined = CombinedRangeRule(column=rule1.column)

        for rule in [rule1, rule2]:
            if rule.operator in (">", ">="):
                combined.min_value = rule.value
                combined.min_inclusive = rule.operator == ">="
            elif rule.operator in ("<", "<="):
                combined.max_value = rule.value
                combined.max_inclusive = rule.operator == "<="

        # Verify we got both bounds
        if combined.min_value is not None or combined.max_value is not None:
            return combined

        return None
