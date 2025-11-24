"""
Unit tests for PluginKVStorage model.

Sprint: 12 (KV Storage Foundation)
Sortie: 1 (Schema & Model)
"""

import pytest
import json
import time

from common.models import PluginKVStorage


class TestPluginKVStorageModel:
    """Test PluginKVStorage ORM model."""

    def test_create_basic_entry(self):
        """Test creating a basic KV entry."""
        entry = PluginKVStorage(
            plugin_name="test-plugin",
            key="config",
            value_json='{"theme": "dark"}',
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert entry.plugin_name == "test-plugin"
        assert entry.key == "config"
        assert entry.value_json == '{"theme": "dark"}'
        assert entry.expires_at is None

    def test_set_value_dict(self):
        """Test set_value() with dict."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="data",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value({"count": 42, "active": True})
        assert entry.value_json == '{"count": 42, "active": true}'

    def test_set_value_list(self):
        """Test set_value() with list."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="items",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value([1, 2, 3])
        assert entry.value_json == '[1, 2, 3]'

    def test_set_value_string(self):
        """Test set_value() with string."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="name",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value("hello")
        assert entry.value_json == '"hello"'

    def test_set_value_number(self):
        """Test set_value() with number."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="count",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value(123)
        assert entry.value_json == '123'

    def test_set_value_boolean(self):
        """Test set_value() with boolean."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="enabled",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value(True)
        assert entry.value_json == 'true'

        entry.set_value(False)
        assert entry.value_json == 'false'

    def test_set_value_null(self):
        """Test set_value() with None/null."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="nullable",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        entry.set_value(None)
        assert entry.value_json == 'null'

    def test_get_value_dict(self):
        """Test get_value() deserializes dict correctly."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="data",
            value_json='{"name": "Alice", "scores": [95, 87, 92]}',
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        value = entry.get_value()
        assert value == {"name": "Alice", "scores": [95, 87, 92]}
        assert isinstance(value, dict)
        assert isinstance(value["scores"], list)

    def test_get_value_preserves_types(self):
        """Test get_value() preserves Python types."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="mixed",
            value_json='{"str": "hello", "int": 42, "float": 3.14, "bool": true, "null": null}',
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        value = entry.get_value()
        assert value["str"] == "hello"
        assert value["int"] == 42
        assert value["float"] == 3.14
        assert value["bool"] is True
        assert value["null"] is None

    def test_value_size_limit_just_under(self):
        """Test value just under 64KB limit succeeds."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="large",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        # Just under limit - should work (accounting for JSON quotes)
        small_value = "x" * 65000
        entry.set_value(small_value)  # Should succeed
        assert len(entry.value_json.encode('utf-8')) <= 65536

    def test_value_size_limit_exceeded(self):
        """Test value over 64KB limit raises ValueError."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="huge",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        # Over limit - should fail
        large_value = "x" * 70000
        with pytest.raises(ValueError, match="exceeds 64KB limit"):
            entry.set_value(large_value)

    def test_value_size_error_message(self):
        """Test size limit error message includes actual size."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="large",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        large_value = "x" * 70000
        with pytest.raises(ValueError) as exc_info:
            entry.set_value(large_value)

        assert "bytes" in str(exc_info.value)
        assert "65536" in str(exc_info.value)

    def test_is_expired_no_expiration(self):
        """Test is_expired returns False when expires_at is None."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="forever",
            value_json='"data"',
            expires_at=None,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert entry.is_expired is False

    def test_is_expired_future(self):
        """Test is_expired returns False for future expiration."""
        future_time = int(time.time()) + 3600  # 1 hour from now
        entry = PluginKVStorage(
            plugin_name="test",
            key="future",
            value_json='"data"',
            expires_at=future_time,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert entry.is_expired is False

    def test_is_expired_past(self):
        """Test is_expired returns True for past expiration."""
        past_time = int(time.time()) - 3600  # 1 hour ago
        entry = PluginKVStorage(
            plugin_name="test",
            key="past",
            value_json='"data"',
            expires_at=past_time,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert entry.is_expired is True

    def test_is_expired_exactly_now(self):
        """Test is_expired at exact expiration time."""
        now = int(time.time())
        entry = PluginKVStorage(
            plugin_name="test",
            key="now",
            value_json='"data"',
            expires_at=now,
            created_at=now,
            updated_at=now
        )
        # Should be expired (>= comparison)
        assert entry.is_expired is True

    def test_repr_basic(self):
        """Test string representation."""
        entry = PluginKVStorage(
            plugin_name="test-plugin",
            key="config",
            value_json='"data"',
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        repr_str = repr(entry)
        assert "test-plugin" in repr_str
        assert "config" in repr_str
        assert "PluginKVStorage" in repr_str

    def test_repr_expired(self):
        """Test repr includes EXPIRED marker for expired entries."""
        past_time = int(time.time()) - 3600
        entry = PluginKVStorage(
            plugin_name="test",
            key="old",
            value_json='"data"',
            expires_at=past_time,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert "[EXPIRED]" in repr(entry)

    def test_repr_not_expired(self):
        """Test repr does not include EXPIRED for active entries."""
        future_time = int(time.time()) + 3600
        entry = PluginKVStorage(
            plugin_name="test",
            key="active",
            value_json='"data"',
            expires_at=future_time,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        assert "[EXPIRED]" not in repr(entry)

    def test_invalid_json_get_value(self):
        """Test get_value() raises JSONDecodeError for invalid JSON."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="bad",
            value_json="not valid json",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        with pytest.raises(json.JSONDecodeError):
            entry.get_value()

    def test_unicode_handling(self):
        """Test Unicode characters are handled correctly."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="unicode",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        unicode_data = {"message": "Hello 世界 🌍", "emoji": "🎉"}
        entry.set_value(unicode_data)

        retrieved = entry.get_value()
        assert retrieved["message"] == "Hello 世界 🌍"
        assert retrieved["emoji"] == "🎉"

    def test_nested_structures(self):
        """Test deeply nested structures."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="nested",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep",
                        "array": [1, 2, [3, 4]]
                    }
                }
            }
        }

        entry.set_value(nested_data)
        retrieved = entry.get_value()
        assert retrieved["level1"]["level2"]["level3"]["value"] == "deep"
        assert retrieved["level1"]["level2"]["level3"]["array"][2][1] == 4

    def test_empty_collections(self):
        """Test empty dict and list."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="empty",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        # Empty dict
        entry.set_value({})
        assert entry.get_value() == {}

        # Empty list
        entry.set_value([])
        assert entry.get_value() == []

    def test_special_float_values(self):
        """Test special float values."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="float",
            created_at=int(time.time()),
            updated_at=int(time.time())
        )

        # Regular floats work
        entry.set_value(3.14159)
        assert entry.get_value() == 3.14159

        # Negative floats work
        entry.set_value(-42.5)
        assert entry.get_value() == -42.5

        # Very large floats work
        entry.set_value(1.7976931348623157e+308)
        assert isinstance(entry.get_value(), float)

    def test_plugin_name_variations(self):
        """Test various valid plugin name formats."""
        valid_names = [
            "test",
            "my-plugin",
            "plugin_123",
            "a",
            "test-plugin-name",
            "quote-db",
            "trivia_game"
        ]

        now = int(time.time())
        for name in valid_names:
            entry = PluginKVStorage(
                plugin_name=name,
                key="test",
                value_json='"data"',
                created_at=now,
                updated_at=now
            )
            assert entry.plugin_name == name

    def test_key_variations(self):
        """Test various valid key formats."""
        valid_keys = [
            "simple",
            "config_theme",
            "user-score",
            "session:abc123",
            "data.nested.key",
            "a",
            "x" * 255  # Max length
        ]

        now = int(time.time())
        for key in valid_keys:
            entry = PluginKVStorage(
                plugin_name="test",
                key=key,
                value_json='"data"',
                created_at=now,
                updated_at=now
            )
            assert entry.key == key

    def test_tablename(self):
        """Test table name is correct."""
        assert PluginKVStorage.__tablename__ == 'plugin_kv_storage'

    def test_timestamps_type(self):
        """Test timestamp fields accept integers."""
        now = int(time.time())
        entry = PluginKVStorage(
            plugin_name="test",
            key="time",
            value_json='"data"',
            created_at=now,
            updated_at=now
        )

        assert isinstance(entry.created_at, int)
        assert isinstance(entry.updated_at, int)
        assert entry.created_at == now
        assert entry.updated_at == now
