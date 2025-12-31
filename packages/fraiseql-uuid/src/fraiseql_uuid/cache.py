"""UUID generation cache for performance."""



class UUIDCache:
    """Cache for generated UUIDs."""

    def __init__(self) -> None:
        """Initialize cache."""
        self._cache: dict[str, dict[int, str]] = {}

    def get(self, table: str, instance: int) -> str | None:
        """Get cached UUID.

        Args:
            table: Table name
            instance: Instance number

        Returns:
            Cached UUID or None
        """
        return self._cache.get(table, {}).get(instance)

    def set(self, table: str, instance: int, uuid: str) -> None:
        """Set cached UUID.

        Args:
            table: Table name
            instance: Instance number
            uuid: UUID to cache
        """
        if table not in self._cache:
            self._cache[table] = {}
        self._cache[table][instance] = uuid

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
