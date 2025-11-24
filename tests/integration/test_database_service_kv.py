"""
Integration tests for DatabaseService KV handlers via NATS.

Sprint: 12 (KV Storage Foundation)
Sortie: 3 (DatabaseService NATS Handlers)

These tests verify the full request/response cycle through NATS for KV operations.
Requires NATS server running at localhost:4222.
"""

import asyncio
import json
import pytest
from nats.aio.client import Client as NATS

from common.database_service import DatabaseService
from common.database import BotDatabase
from common.models import Base


@pytest.fixture
async def nats_client():
    """Create NATS client for tests."""
    nc = NATS()
    try:
        await nc.connect("nats://localhost:4222")
        yield nc
    finally:
        await nc.close()


@pytest.fixture
async def db_service(nats_client):
    """Create DatabaseService instance with in-memory database."""
    # Create in-memory database
    db = BotDatabase(":memory:")
    
    # Create tables directly without calling connect()
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create and start service
    service = DatabaseService(nats_client, ":memory:")
    service.db = db  # Use our pre-configured DB
    
    # Start service (registers NATS subscriptions)
    await service.start()
    
    # Give handlers time to register
    await asyncio.sleep(0.1)
    
    yield service
    
    # Cleanup
    await service.stop()


class TestKVSetGet:
    """Test kv.set and kv.get handlers."""
    
    async def test_set_and_get_basic(self, nats_client, db_service):
        """Test basic set and get operations."""
        # Set a value
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "config",
                "value": {"theme": "dark"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"] == {}
        
        # Get it back
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({
                "plugin_name": "test",
                "key": "config"
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["exists"] is True
        assert result["data"]["value"] == {"theme": "dark"}
    
    async def test_set_with_ttl(self, nats_client, db_service):
        """Test TTL support."""
        # Set with 2 second TTL
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "temp",
                "value": "data",
                "ttl_seconds": 2
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        
        # Should exist immediately
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result["data"]["exists"] is True
        
        # Wait for expiration
        await asyncio.sleep(3)
        
        # Should not exist after TTL
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result["data"]["exists"] is False
    
    async def test_set_all_json_types(self, nats_client, db_service):
        """Test that all JSON types are preserved."""
        test_values = [
            ("string", "hello"),
            ("int", 42),
            ("float", 3.14),
            ("bool_true", True),
            ("bool_false", False),
            ("null", None),
            ("list", [1, 2, 3]),
            ("dict", {"nested": {"key": "value"}}),
        ]
        
        for key, value in test_values:
            # Set
            response = await nats_client.request(
                "rosey.db.kv.set",
                json.dumps({
                    "plugin_name": "test",
                    "key": key,
                    "value": value
                }).encode(),
                timeout=1.0
            )
            assert json.loads(response.data.decode())["success"] is True
            
            # Get and verify
            response = await nats_client.request(
                "rosey.db.kv.get",
                json.dumps({"plugin_name": "test", "key": key}).encode(),
                timeout=1.0
            )
            result = json.loads(response.data.decode())
            assert result["data"]["value"] == value
    
    async def test_get_nonexistent_key(self, nats_client, db_service):
        """Test getting a key that doesn't exist."""
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({
                "plugin_name": "test",
                "key": "nonexistent"
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["exists"] is False
        # Note: 'value' key not present when exists=False


class TestKVDelete:
    """Test kv.delete handler."""
    
    async def test_delete_existing_key(self, nats_client, db_service):
        """Test deleting an existing key."""
        # Set a value first
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "temp",
                "value": "data"
            }).encode(),
            timeout=1.0
        )
        
        # Delete it
        response = await nats_client.request(
            "rosey.db.kv.delete",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["deleted"] is True
        
        # Verify it's gone
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result["data"]["exists"] is False
    
    async def test_delete_nonexistent_key(self, nats_client, db_service):
        """Test deleting a key that doesn't exist."""
        response = await nats_client.request(
            "rosey.db.kv.delete",
            json.dumps({"plugin_name": "test", "key": "nonexistent"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["deleted"] is False


class TestKVList:
    """Test kv.list handler."""
    
    async def test_list_empty(self, nats_client, db_service):
        """Test listing when no keys exist."""
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "empty"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["count"] == 0
        assert result["data"]["keys"] == []
        assert result["data"]["truncated"] is False
    
    async def test_list_all_keys(self, nats_client, db_service):
        """Test listing all keys for a plugin."""
        # Set multiple keys
        for i in range(3):
            await nats_client.request(
                "rosey.db.kv.set",
                json.dumps({
                    "plugin_name": "test",
                    "key": f"key{i}",
                    "value": i
                }).encode(),
                timeout=1.0
            )
        
        # List all
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "test"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["count"] == 3
        assert "key0" in result["data"]["keys"]
        assert "key1" in result["data"]["keys"]
        assert "key2" in result["data"]["keys"]
    
    async def test_list_with_prefix(self, nats_client, db_service):
        """Test prefix filtering."""
        # Set keys with different prefixes
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "user:alice", "value": 1}).encode(),
            timeout=1.0
        )
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "user:bob", "value": 2}).encode(),
            timeout=1.0
        )
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "config:theme", "value": 3}).encode(),
            timeout=1.0
        )
        
        # List with prefix
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "test", "prefix": "user:"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["count"] == 2
        assert "user:alice" in result["data"]["keys"]
        assert "user:bob" in result["data"]["keys"]
        assert "config:theme" not in result["data"]["keys"]
    
    async def test_list_with_limit(self, nats_client, db_service):
        """Test limit parameter."""
        # Set 10 keys
        for i in range(10):
            await nats_client.request(
                "rosey.db.kv.set",
                json.dumps({"plugin_name": "test", "key": f"key{i}", "value": i}).encode(),
                timeout=1.0
            )
        
        # List with limit=5
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "test", "limit": 5}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is True
        assert result["data"]["count"] == 5
        assert result["data"]["truncated"] is True


class TestValidation:
    """Test request validation and error handling."""
    
    async def test_invalid_json(self, nats_client, db_service):
        """Test handling of invalid JSON."""
        response = await nats_client.request(
            "rosey.db.kv.set",
            b"not valid json",
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_JSON"
    
    async def test_missing_plugin_name_set(self, nats_client, db_service):
        """Test missing plugin_name in set request."""
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"key": "config", "value": "data"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is False
        assert result["error"]["code"] == "MISSING_FIELD"
        assert "plugin_name" in result["error"]["message"]
    
    async def test_missing_key_get(self, nats_client, db_service):
        """Test missing key in get request."""
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is False
        assert result["error"]["code"] == "MISSING_FIELD"
        assert "key" in result["error"]["message"]
    
    async def test_missing_value_set(self, nats_client, db_service):
        """Test missing value in set request."""
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "config"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is False
        assert result["error"]["code"] == "MISSING_FIELD"
        assert "value" in result["error"]["message"]
    
    async def test_value_too_large(self, nats_client, db_service):
        """Test value size limit."""
        large_value = "x" * 70000
        
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "large",
                "value": large_value
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["success"] is False
        assert result["error"]["code"] == "VALUE_TOO_LARGE"


class TestPluginIsolation:
    """Test that plugins can't access each other's data."""
    
    async def test_get_isolation(self, nats_client, db_service):
        """Test that plugins can't get each other's keys."""
        # Plugin A sets a key
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "plugin-a", "key": "secret", "value": "data"}).encode(),
            timeout=1.0
        )
        
        # Plugin B tries to get it
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "plugin-b", "key": "secret"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["data"]["exists"] is False
    
    async def test_list_isolation(self, nats_client, db_service):
        """Test that list only returns plugin's own keys."""
        # Set keys for different plugins
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "plugin-a", "key": "key1", "value": 1}).encode(),
            timeout=1.0
        )
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "plugin-b", "key": "key2", "value": 2}).encode(),
            timeout=1.0
        )
        
        # List for plugin-a
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "plugin-a"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["data"]["count"] == 1
        assert "key1" in result["data"]["keys"]
        assert "key2" not in result["data"]["keys"]
    
    async def test_delete_isolation(self, nats_client, db_service):
        """Test that delete only affects plugin's own keys."""
        # Plugin A sets a key
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "plugin-a", "key": "key", "value": "data"}).encode(),
            timeout=1.0
        )
        
        # Plugin B tries to delete it
        response = await nats_client.request(
            "rosey.db.kv.delete",
            json.dumps({"plugin_name": "plugin-b", "key": "key"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result["data"]["deleted"] is False
        
        # Verify plugin A's key still exists
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "plugin-a", "key": "key"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result["data"]["exists"] is True
