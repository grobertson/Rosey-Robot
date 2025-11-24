"""
Unit tests for BotDatabase KV methods.

Sprint: 12 (KV Storage Foundation)
Sortie: 2 (BotDatabase KV Methods)
"""

import asyncio
import pytest
import time
from sqlalchemy import update
from common.database import BotDatabase
from common.models import Base, PluginKVStorage


@pytest.fixture
async def db():
    """Create test database instance with in-memory SQLite."""
    test_db = BotDatabase(':memory:')
    
    # Create tables directly without calling connect() which expects all tables
    async with test_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_db
    
    await test_db.close()


class TestKVSet:
    """Test kv_set method."""
    
    async def test_set_basic_dict(self, db):
        """Test setting a basic dictionary value."""
        await db.kv_set("test-plugin", "config", {"theme": "dark"})
        
        result = await db.kv_get("test-plugin", "config")
        assert result['exists'] is True
        assert result['value'] == {"theme": "dark"}
    
    async def test_set_all_json_types(self, db):
        """Test serialization of all JSON types."""
        test_cases = [
            ("dict", {"key": "value"}),
            ("list", [1, 2, 3]),
            ("string", "hello world"),
            ("int", 42),
            ("float", 3.14),
            ("bool_true", True),
            ("bool_false", False),
            ("null", None),
            ("nested", {"users": [{"name": "Alice", "score": 95}]}),
        ]
        
        for key, value in test_cases:
            await db.kv_set("test", key, value)
            result = await db.kv_get("test", key)
            assert result['exists'] is True
            assert result['value'] == value, f"Failed for {key}"
    
    async def test_set_with_ttl(self, db):
        """Test TTL expiration."""
        # Set with 1 second TTL
        await db.kv_set("test", "expires", "data", ttl_seconds=1)
        
        # Should exist immediately
        result = await db.kv_get("test", "expires")
        assert result['exists'] is True
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Should not exist after TTL
        result = await db.kv_get("test", "expires")
        assert result['exists'] is False
    
    async def test_set_upsert_behavior(self, db):
        """Test that set updates existing keys."""
        # Initial set
        await db.kv_set("test", "counter", 1)
        result = await db.kv_get("test", "counter")
        assert result['value'] == 1
        
        # Update
        await db.kv_set("test", "counter", 2)
        result = await db.kv_get("test", "counter")
        assert result['value'] == 2
        
        # Verify only one row exists
        list_result = await db.kv_list("test")
        assert list_result['count'] == 1
    
    async def test_set_value_size_limit(self, db):
        """Test value size limit enforcement."""
        # Just under limit - should work
        small_value = "x" * 65000
        await db.kv_set("test", "small", small_value)  # Should succeed
        
        # Over limit - should fail
        large_value = "x" * 70000
        with pytest.raises(ValueError, match="exceeds 64KB limit"):
            await db.kv_set("test", "large", large_value)
    
    async def test_set_non_serializable(self, db):
        """Test handling of non-JSON-serializable values."""
        class NotSerializable:
            pass
        
        with pytest.raises(TypeError, match="not JSON-serializable"):
            await db.kv_set("test", "bad", NotSerializable())
    
    async def test_set_zero_ttl(self, db):
        """Test that TTL=0 means no expiration."""
        await db.kv_set("test", "permanent", "data", ttl_seconds=0)
        
        result = await db.kv_get("test", "permanent")
        assert result['exists'] is True
    
    async def test_set_negative_ttl_ignored(self, db):
        """Test that negative TTL is treated as no expiration."""
        await db.kv_set("test", "negative", "data", ttl_seconds=-100)
        
        result = await db.kv_get("test", "negative")
        assert result['exists'] is True
    
    async def test_set_updates_ttl(self, db):
        """Test that updating a key updates its TTL."""
        # Set with long TTL
        await db.kv_set("test", "key", "value1", ttl_seconds=3600)
        
        # Update with short TTL
        await db.kv_set("test", "key", "value2", ttl_seconds=1)
        
        # Value should be updated
        result = await db.kv_get("test", "key")
        assert result['value'] == "value2"
        
        # Should expire after short TTL
        await asyncio.sleep(1.5)
        result = await db.kv_get("test", "key")
        assert result['exists'] is False


class TestKVGet:
    """Test kv_get method."""
    
    async def test_get_existing_key(self, db):
        """Test getting an existing key."""
        await db.kv_set("test", "existing", {"data": "value"})
        
        result = await db.kv_get("test", "existing")
        assert result['exists'] is True
        assert result['value'] == {"data": "value"}
    
    async def test_get_nonexistent_key(self, db):
        """Test getting a key that doesn't exist."""
        result = await db.kv_get("test", "nonexistent")
        assert result['exists'] is False
        assert 'value' not in result
    
    async def test_get_expired_key(self, db):
        """Test that expired keys return exists=False."""
        await db.kv_set("test", "expired", "data", ttl_seconds=1)
        
        await asyncio.sleep(1.5)
        
        result = await db.kv_get("test", "expired")
        assert result['exists'] is False
    
    async def test_get_type_preservation(self, db):
        """Test that types are preserved through serialization."""
        # Integer should stay integer
        await db.kv_set("test", "int", 42)
        result = await db.kv_get("test", "int")
        assert result['value'] == 42
        assert isinstance(result['value'], int)
        
        # Float should stay float
        await db.kv_set("test", "float", 3.14)
        result = await db.kv_get("test", "float")
        assert result['value'] == 3.14
        assert isinstance(result['value'], float)
        
        # Boolean should stay boolean
        await db.kv_set("test", "bool", True)
        result = await db.kv_get("test", "bool")
        assert result['value'] is True
        assert isinstance(result['value'], bool)


class TestKVDelete:
    """Test kv_delete method."""
    
    async def test_delete_existing_key(self, db):
        """Test deleting an existing key."""
        await db.kv_set("test", "temp", "data")
        
        deleted = await db.kv_delete("test", "temp")
        assert deleted is True
        
        # Verify it's gone
        result = await db.kv_get("test", "temp")
        assert result['exists'] is False
    
    async def test_delete_nonexistent_key(self, db):
        """Test deleting a key that doesn't exist (idempotent)."""
        deleted = await db.kv_delete("test", "nonexistent")
        assert deleted is False
    
    async def test_delete_idempotence(self, db):
        """Test that delete is idempotent."""
        await db.kv_set("test", "temp", "data")
        
        # First delete
        deleted1 = await db.kv_delete("test", "temp")
        assert deleted1 is True
        
        # Second delete
        deleted2 = await db.kv_delete("test", "temp")
        assert deleted2 is False


class TestKVList:
    """Test kv_list method."""
    
    async def test_list_empty(self, db):
        """Test listing when no keys exist."""
        result = await db.kv_list("test")
        assert result['keys'] == []
        assert result['count'] == 0
        assert result['truncated'] is False
    
    async def test_list_basic(self, db):
        """Test listing keys."""
        await db.kv_set("test", "key1", 1)
        await db.kv_set("test", "key2", 2)
        await db.kv_set("test", "key3", 3)
        
        result = await db.kv_list("test")
        assert result['count'] == 3
        assert result['keys'] == ["key1", "key2", "key3"]
        assert result['truncated'] is False
    
    async def test_list_with_prefix(self, db):
        """Test prefix filtering."""
        await db.kv_set("test", "user:alice", {"name": "Alice"})
        await db.kv_set("test", "user:bob", {"name": "Bob"})
        await db.kv_set("test", "config:theme", "dark")
        await db.kv_set("test", "config:lang", "en")
        
        # List with "user:" prefix
        result = await db.kv_list("test", prefix="user:")
        assert result['count'] == 2
        assert "user:alice" in result['keys']
        assert "user:bob" in result['keys']
        assert "config:theme" not in result['keys']
        
        # List with "config:" prefix
        result = await db.kv_list("test", prefix="config:")
        assert result['count'] == 2
        assert "config:theme" in result['keys']
        assert "config:lang" in result['keys']
    
    async def test_list_excludes_expired(self, db):
        """Test that list excludes expired keys."""
        await db.kv_set("test", "expires1", 1, ttl_seconds=1)
        await db.kv_set("test", "expires2", 2, ttl_seconds=1)
        await db.kv_set("test", "permanent", 3)
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # List should only show permanent key
        result = await db.kv_list("test")
        assert result['count'] == 1
        assert result['keys'] == ["permanent"]
    
    async def test_list_sorted(self, db):
        """Test that keys are sorted alphabetically."""
        keys = ["zebra", "apple", "mango", "banana"]
        for key in keys:
            await db.kv_set("test", key, 1)
        
        result = await db.kv_list("test")
        assert result['keys'] == ["apple", "banana", "mango", "zebra"]
    
    async def test_list_truncation(self, db):
        """Test limit and truncation detection."""
        # Set 15 keys
        for i in range(15):
            await db.kv_set("test", f"key{i:02d}", i)
        
        # List with limit=10
        result = await db.kv_list("test", limit=10)
        assert result['count'] == 10
        assert result['truncated'] is True
        assert len(result['keys']) == 10
        
        # List with limit=20
        result = await db.kv_list("test", limit=20)
        assert result['count'] == 15
        assert result['truncated'] is False
    
    async def test_list_custom_limit(self, db):
        """Test custom limit parameter."""
        for i in range(100):
            await db.kv_set("test", f"key{i:03d}", i)
        
        # List with small limit
        result = await db.kv_list("test", limit=5)
        assert result['count'] == 5
        assert result['truncated'] is True
        
        # List with medium limit
        result = await db.kv_list("test", limit=50)
        assert result['count'] == 50
        assert result['truncated'] is True


class TestKVCleanup:
    """Test kv_cleanup_expired method."""
    
    async def _set_expired_key(self, db, plugin_name: str, key: str, value):
        """Helper to create a key that's already expired."""
        # Set key with normal TTL first
        await db.kv_set(plugin_name, key, value, ttl_seconds=3600)
        
        # Update expires_at to be in the past
        past_timestamp = int(time.time()) - 100  # 100 seconds ago
        async with db._get_session() as session:
            stmt = (
                update(PluginKVStorage)
                .where(
                    PluginKVStorage.plugin_name == plugin_name,
                    PluginKVStorage.key == key
                )
                .values(expires_at=past_timestamp)
            )
            await session.execute(stmt)
    
    async def test_cleanup_no_expired(self, db):
        """Test cleanup when no expired keys exist."""
        await db.kv_set("test", "permanent", "data")
        
        deleted = await db.kv_cleanup_expired()
        assert deleted == 0
        
        # Verify key still exists
        result = await db.kv_get("test", "permanent")
        assert result['exists'] is True
    
    async def test_cleanup_some_expired(self, db):
        """Test cleanup removes only expired keys."""
        # Set expired keys using helper
        for i in range(5):
            await self._set_expired_key(db, "test", f"expires{i}", i)
        
        # Set permanent keys
        for i in range(3):
            await db.kv_set("test", f"keep{i}", i)
        
        # Cleanup
        deleted = await db.kv_cleanup_expired()
        assert deleted == 5
        
        # Verify only permanent keys remain
        result = await db.kv_list("test")
        assert result['count'] == 3
        assert all("keep" in key for key in result['keys'])
    
    async def test_cleanup_all_expired(self, db):
        """Test cleanup when all keys are expired."""
        # Set all keys as expired using helper
        for i in range(10):
            await self._set_expired_key(db, "test", f"key{i}", i)
        
        deleted = await db.kv_cleanup_expired()
        assert deleted == 10
        
        # Verify nothing remains
        result = await db.kv_list("test")
        assert result['count'] == 0
    
    async def test_cleanup_across_plugins(self, db):
        """Test cleanup works across all plugins."""
        # Set expired keys for multiple plugins
        for plugin in ["plugin-a", "plugin-b", "plugin-c"]:
            for i in range(3):
                await self._set_expired_key(db, plugin, f"key{i}", i)
        
        # Cleanup should remove all expired keys
        deleted = await db.kv_cleanup_expired()
        assert deleted == 9


class TestPluginIsolation:
    """Test that plugins can't access each other's data."""
    
    async def test_get_isolation(self, db):
        """Test that get is isolated by plugin."""
        await db.kv_set("plugin-a", "secret", "data-a")
        await db.kv_set("plugin-b", "secret", "data-b")
        
        # Each plugin should only see their own data
        result_a = await db.kv_get("plugin-a", "secret")
        assert result_a['value'] == "data-a"
        
        result_b = await db.kv_get("plugin-b", "secret")
        assert result_b['value'] == "data-b"
    
    async def test_list_isolation(self, db):
        """Test that list is isolated by plugin."""
        await db.kv_set("plugin-a", "key1", 1)
        await db.kv_set("plugin-a", "key2", 2)
        await db.kv_set("plugin-b", "key3", 3)
        await db.kv_set("plugin-b", "key4", 4)
        
        # Each plugin should only see their own keys
        list_a = await db.kv_list("plugin-a")
        assert set(list_a['keys']) == {"key1", "key2"}
        
        list_b = await db.kv_list("plugin-b")
        assert set(list_b['keys']) == {"key3", "key4"}
    
    async def test_delete_isolation(self, db):
        """Test that delete is isolated by plugin."""
        await db.kv_set("plugin-a", "shared-name", "data-a")
        await db.kv_set("plugin-b", "shared-name", "data-b")
        
        # Delete from plugin-a
        deleted = await db.kv_delete("plugin-a", "shared-name")
        assert deleted is True
        
        # plugin-a key should be gone
        result_a = await db.kv_get("plugin-a", "shared-name")
        assert result_a['exists'] is False
        
        # plugin-b key should still exist
        result_b = await db.kv_get("plugin-b", "shared-name")
        assert result_b['exists'] is True
        assert result_b['value'] == "data-b"


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    async def test_empty_string_key(self, db):
        """Test handling of empty string as key (should work)."""
        await db.kv_set("test", "", "empty key")
        
        result = await db.kv_get("test", "")
        assert result['exists'] is True
        assert result['value'] == "empty key"
    
    async def test_special_characters_in_key(self, db):
        """Test keys with special characters."""
        special_keys = [
            "key:with:colons",
            "key/with/slashes",
            "key.with.dots",
            "key-with-dashes",
            "key_with_underscores",
            "key with spaces",
            "key@with#symbols$",
        ]
        
        for key in special_keys:
            await db.kv_set("test", key, "value")
            result = await db.kv_get("test", key)
            assert result['exists'] is True, f"Failed for key: {key}"
    
    async def test_unicode_in_values(self, db):
        """Test Unicode characters in values."""
        unicode_data = {
            "message": "Hello 世界 🌍",
            "emoji": "🎉🎊🎈",
            "symbols": "±§∞≈"
        }
        
        await db.kv_set("test", "unicode", unicode_data)
        result = await db.kv_get("test", "unicode")
        assert result['value'] == unicode_data
    
    async def test_very_large_dict(self, db):
        """Test handling of large but valid dicts."""
        # Create dict with 1000 keys
        large_dict = {f"key{i}": f"value{i}" for i in range(1000)}
        
        await db.kv_set("test", "large", large_dict)
        result = await db.kv_get("test", "large")
        assert result['value'] == large_dict
    
    async def test_deeply_nested_structure(self, db):
        """Test deeply nested data structures."""
        nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "data": "deep"
                            }
                        }
                    }
                }
            }
        }
        
        await db.kv_set("test", "nested", nested)
        result = await db.kv_get("test", "nested")
        assert result['value'] == nested


class TestPerformance:
    """Test performance characteristics."""
    
    async def test_bulk_set_performance(self, db):
        """Test performance of bulk set operations."""
        start = time.time()
        for i in range(100):
            await db.kv_set("test", f"key{i}", {"index": i})
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<2s for 100 keys)
        assert elapsed < 2.0
        
        # Verify all were set
        result = await db.kv_list("test", limit=200)
        assert result['count'] == 100
    
    async def test_bulk_get_performance(self, db):
        """Test performance of bulk get operations."""
        # Set up data
        for i in range(100):
            await db.kv_set("test", f"key{i}", {"index": i})
        
        # Measure get performance
        start = time.time()
        for i in range(100):
            await db.kv_get("test", f"key{i}")
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<2s for 100 keys)
        assert elapsed < 2.0
    
    async def test_list_performance_1000(self, db):
        """Test performance of listing many keys."""
        # Set up 1000 keys
        for i in range(1000):
            await db.kv_set("test", f"key{i:04d}", i)
        
        # Measure list performance
        start = time.time()
        result = await db.kv_list("test", limit=1000)
        elapsed = time.time() - start
        
        assert result['count'] == 1000
        # Should be very fast (<0.1s)
        assert elapsed < 0.1
