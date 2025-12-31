"""Base generator interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseGenerator(ABC):
    """
    Base class for custom generators.

    Subclass this to create custom data generators that can be registered
    and used in seed plans.

    Example:
        >>> class SKUGenerator(BaseGenerator):
        ...     def generate(self, column_name, pg_type, **context):
        ...         instance = context.get('instance', 1)
        ...         return f"SKU-{instance:06d}"
        >>>
        >>> register_generator('sku', SKUGenerator)
        >>> builder.add("tb_product", count=100, strategy="sku")
    """

    @abstractmethod
    def generate(self, column_name: str, pg_type: str, **context: Any) -> Any:
        """
        Generate a value for a column.

        Args:
            column_name: Column name being generated
            pg_type: PostgreSQL type of the column
            **context: Additional context:
                - instance: Row instance number (1-based)
                - row_data: Other column data in current row (dict)
                - table_info: TableInfo for current table

        Returns:
            Generated value appropriate for the column

        Example:
            >>> def generate(self, column_name, pg_type, **context):
            ...     instance = context.get('instance', 1)
            ...     row_data = context.get('row_data', {})
            ...     category = row_data.get('category', 'GEN')
            ...     return f"PROD-{category}-{instance:05d}"
        """
        pass
