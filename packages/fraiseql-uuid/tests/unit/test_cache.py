"""Tests for UUIDCache class."""


from fraiseql_uuid import UUIDCache


class TestUUIDCacheInit:
    """Tests for UUIDCache.__init__()."""

    def test_init_empty_cache(self) -> None:
        """Test initialization creates empty cache."""
        cache = UUIDCache()

        assert cache._cache == {}


class TestUUIDCacheGet:
    """Tests for UUIDCache.get()."""

    def test_get_nonexistent_table(self) -> None:
        """Test getting from nonexistent table returns None."""
        cache = UUIDCache()

        assert cache.get("users", 1) is None

    def test_get_nonexistent_instance(self) -> None:
        """Test getting nonexistent instance returns None."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")

        assert cache.get("users", 2) is None

    def test_get_existing_uuid(self) -> None:
        """Test getting existing UUID."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")

        assert cache.get("users", 1) == "uuid-1"

    def test_get_multiple_tables(self) -> None:
        """Test getting from multiple tables."""
        cache = UUIDCache()
        cache.set("users", 1, "user-uuid-1")
        cache.set("posts", 1, "post-uuid-1")

        assert cache.get("users", 1) == "user-uuid-1"
        assert cache.get("posts", 1) == "post-uuid-1"

    def test_get_multiple_instances(self) -> None:
        """Test getting multiple instances from same table."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        cache.set("users", 2, "uuid-2")
        cache.set("users", 3, "uuid-3")

        assert cache.get("users", 1) == "uuid-1"
        assert cache.get("users", 2) == "uuid-2"
        assert cache.get("users", 3) == "uuid-3"


class TestUUIDCacheSet:
    """Tests for UUIDCache.set()."""

    def test_set_new_table(self) -> None:
        """Test setting UUID in new table."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")

        assert cache.get("users", 1) == "uuid-1"
        assert "users" in cache._cache

    def test_set_new_instance(self) -> None:
        """Test setting new instance in existing table."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        cache.set("users", 2, "uuid-2")

        assert cache.get("users", 1) == "uuid-1"
        assert cache.get("users", 2) == "uuid-2"

    def test_set_overwrite_existing(self) -> None:
        """Test overwriting existing UUID."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        cache.set("users", 1, "uuid-1-updated")

        assert cache.get("users", 1) == "uuid-1-updated"

    def test_set_multiple_tables(self) -> None:
        """Test setting UUIDs in multiple tables."""
        cache = UUIDCache()
        cache.set("users", 1, "user-uuid-1")
        cache.set("posts", 1, "post-uuid-1")
        cache.set("comments", 1, "comment-uuid-1")

        assert cache.get("users", 1) == "user-uuid-1"
        assert cache.get("posts", 1) == "post-uuid-1"
        assert cache.get("comments", 1) == "comment-uuid-1"

    def test_set_returns_none(self) -> None:
        """Test that set() returns None."""
        cache = UUIDCache()
        result = cache.set("users", 1, "uuid-1")

        assert result is None


class TestUUIDCacheClear:
    """Tests for UUIDCache.clear()."""

    def test_clear_empty_cache(self) -> None:
        """Test clearing empty cache."""
        cache = UUIDCache()
        cache.clear()

        assert cache._cache == {}

    def test_clear_populated_cache(self) -> None:
        """Test clearing populated cache."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        cache.set("posts", 1, "uuid-2")

        cache.clear()

        assert cache._cache == {}
        assert cache.get("users", 1) is None
        assert cache.get("posts", 1) is None

    def test_clear_returns_none(self) -> None:
        """Test that clear() returns None."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        result = cache.clear()

        assert result is None

    def test_clear_and_reuse(self) -> None:
        """Test clearing cache and reusing it."""
        cache = UUIDCache()
        cache.set("users", 1, "uuid-1")
        cache.clear()
        cache.set("users", 2, "uuid-2")

        assert cache.get("users", 1) is None
        assert cache.get("users", 2) == "uuid-2"


class TestUUIDCacheEdgeCases:
    """Edge case tests for UUIDCache."""

    def test_cache_with_zero_instance(self) -> None:
        """Test caching with instance 0."""
        cache = UUIDCache()
        cache.set("users", 0, "uuid-0")

        assert cache.get("users", 0) == "uuid-0"

    def test_cache_with_large_instance(self) -> None:
        """Test caching with large instance number."""
        cache = UUIDCache()
        large_instance = 999999999999
        cache.set("users", large_instance, "uuid-large")

        assert cache.get("users", large_instance) == "uuid-large"

    def test_cache_with_empty_table_name(self) -> None:
        """Test caching with empty table name."""
        cache = UUIDCache()
        cache.set("", 1, "uuid-1")

        assert cache.get("", 1) == "uuid-1"

    def test_cache_with_special_chars_in_table_name(self) -> None:
        """Test caching with special characters in table name."""
        cache = UUIDCache()
        cache.set("user_profiles", 1, "uuid-1")
        cache.set("user-sessions", 2, "uuid-2")

        assert cache.get("user_profiles", 1) == "uuid-1"
        assert cache.get("user-sessions", 2) == "uuid-2"

    def test_cache_isolation_between_instances(self) -> None:
        """Test that different cache instances are independent."""
        cache1 = UUIDCache()
        cache2 = UUIDCache()

        cache1.set("users", 1, "uuid-1")
        cache2.set("users", 1, "uuid-2")

        assert cache1.get("users", 1) == "uuid-1"
        assert cache2.get("users", 1) == "uuid-2"

    def test_cache_large_number_of_entries(self) -> None:
        """Test caching large number of entries."""
        cache = UUIDCache()

        # Cache 100 entries across 10 tables
        for table_idx in range(10):
            table_name = f"table_{table_idx}"
            for instance in range(10):
                uuid = f"uuid-{table_idx}-{instance}"
                cache.set(table_name, instance, uuid)

        # Verify all entries
        for table_idx in range(10):
            table_name = f"table_{table_idx}"
            for instance in range(10):
                expected_uuid = f"uuid-{table_idx}-{instance}"
                assert cache.get(table_name, instance) == expected_uuid

    def test_cache_with_real_uuids(self) -> None:
        """Test caching with real UUID values."""
        from fraiseql_uuid import Pattern

        cache = UUIDCache()
        pattern = Pattern()

        uuid1 = pattern.generate(table_code="012345", instance=1)
        uuid2 = pattern.generate(table_code="012345", instance=2)

        cache.set("users", 1, uuid1)
        cache.set("users", 2, uuid2)

        assert cache.get("users", 1) == uuid1
        assert cache.get("users", 2) == uuid2
        assert cache.get("users", 1) == "01234521-0000-4000-8000-000000000001"
        assert cache.get("users", 2) == "01234521-0000-4000-8000-000000000002"
