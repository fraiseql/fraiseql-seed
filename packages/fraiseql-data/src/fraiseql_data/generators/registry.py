"""Generator registry for custom generator plugins."""


class GeneratorRegistry:
    """Registry for custom generator plugins."""

    def __init__(self):
        self._generators: dict[str, type] = {}

    def register(self, name: str, generator_class: type) -> None:
        """
        Register a custom generator.

        Args:
            name: Generator name (used in strategy parameter)
            generator_class: Generator class (must have generate method)

        Raises:
            ValueError: If generator class doesn't have generate method
        """
        if not hasattr(generator_class, "generate"):
            raise ValueError(
                f"Generator class must have 'generate' method. "
                f"Class {generator_class.__name__} is missing it."
            )
        self._generators[name] = generator_class

    def get(self, name: str) -> type | None:
        """
        Get generator by name.

        Args:
            name: Generator name

        Returns:
            Generator class or None if not found
        """
        return self._generators.get(name)

    def list_generators(self) -> list[str]:
        """
        List all registered generators.

        Returns:
            List of generator names
        """
        return list(self._generators.keys())

    def clear(self) -> None:
        """Clear all registered generators (for testing)."""
        self._generators.clear()


# Global registry instance
_registry = GeneratorRegistry()


def register_generator(name: str, generator_class: type) -> None:
    """
    Register a custom generator (user-facing API).

    Args:
        name: Generator name
        generator_class: Generator class with generate() method

    Example:
        >>> from fraiseql_data import BaseGenerator, register_generator
        >>>
        >>> class SKUGenerator(BaseGenerator):
        ...     def generate(self, column_name, pg_type, **context):
        ...         instance = context.get('instance', 1)
        ...         return f"SKU-{instance:06d}"
        >>>
        >>> register_generator('sku', SKUGenerator)
    """
    _registry.register(name, generator_class)


def get_generator(name: str) -> type | None:
    """
    Get a registered generator.

    Args:
        name: Generator name

    Returns:
        Generator class or None if not found
    """
    return _registry.get(name)


def list_generators() -> list[str]:
    """
    List all registered generators.

    Returns:
        List of generator names
    """
    return _registry.list_generators()


def clear_generators() -> None:
    """Clear all registered generators (for testing)."""
    _registry.clear()
