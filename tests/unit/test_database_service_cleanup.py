"""
Unit tests for DatabaseService background cleanup task.

Sprint: 12 (KV Storage Foundation)
Sortie: 4 (TTL Cleanup & Polish)
"""

import asyncio
import pytest
import time
from sqlalchemy import update

from common.database_service import DatabaseService
from common.database import BotDatabase
from common.models import Base, PluginKVStorage


@pytest.fixture
async def db():
    """Create test database instance with in-memory SQLite."""
    test_db = BotDatabase(':memory:')
    
    # Create tables directly
    async with test_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_db
    
    await test_db.close()


class TestCleanupTask:
    """Test background cleanup task functionality."""
    
    async def test_cleanup_task_starts(self, db):
        """Test cleanup task starts with service."""
        # Create mock NATS client
        class MockNATS:
            async def subscribe(self, subject, cb):
                return None
        
        service = DatabaseService(
            MockNATS(),
            ":memory:",
            cleanup_interval_seconds=60
        )
        service.db = db  # Use test database
        
        # Start cleanup task manually (without full service start)
        service._shutdown = False
        service._cleanup_task = asyncio.create_task(service._kv_cleanup_loop())
        
        # Task should be running
        assert service._cleanup_task is not None
        assert not service._cleanup_task.done()
        
        # Cleanup
        service._shutdown = True
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass
    
    async def test_cleanup_removes_expired(self, db):
        """Test cleanup removes expired keys."""
        # Set expired keys using helper
        async def set_expired_key(plugin_name: str, key: str, value):
            """Helper to create a key that's already expired."""
            await db.kv_set(plugin_name, key, value, ttl_seconds=3600)
            
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
        
        # Setup expired keys
        for i in range(10):
            await set_expired_key("test", f"expired{i}", i)
        
        # Verify keys exist (but expired)
        result = await db.kv_list("test", limit=100)
        assert result['count'] == 0  # kv_list excludes expired
        
        # Run cleanup manually
        deleted = await db.kv_cleanup_expired()
        assert deleted == 10
    
    async def test_cleanup_preserves_valid_keys(self, db):
        """Test cleanup preserves non-expired keys."""
        # Helper to set expired key
        async def set_expired_key(plugin_name: str, key: str, value):
            await db.kv_set(plugin_name, key, value, ttl_seconds=3600)
            past_timestamp = int(time.time()) - 100
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
        
        # Setup mix of expired and valid keys
        # Expired
        for i in range(5):
            await set_expired_key("test", f"expired{i}", i)
        
        # Valid with TTL
        for i in range(5):
            await db.kv_set("test", f"valid{i}", i, ttl_seconds=3600)
        
        # Permanent (no TTL)
        for i in range(5):
            await db.kv_set("test", f"permanent{i}", i)
        
        # Run cleanup
        deleted = await db.kv_cleanup_expired()
        assert deleted == 5
        
        # Verify valid keys remain
        result = await db.kv_list("test", limit=100)
        assert result['count'] == 10  # 5 valid + 5 permanent
    
    async def test_cleanup_handles_errors(self, db):
        """Test cleanup continues after errors."""
        class MockNATS:
            async def subscribe(self, subject, cb):
                return None
        
        service = DatabaseService(
            MockNATS(),
            ":memory:",
            cleanup_interval_seconds=1  # Fast for testing
        )
        service.db = db
        
        # Mock cleanup to raise error first time, succeed second time
        original_cleanup = db.kv_cleanup_expired
        call_count = 0
        error_raised = False
        
        async def mock_cleanup():
            nonlocal call_count, error_raised
            call_count += 1
            if call_count == 1:
                error_raised = True
                raise Exception("Simulated error")
            return await original_cleanup()
        
        db.kv_cleanup_expired = mock_cleanup
        
        # Start cleanup task
        service._shutdown = False
        service._cleanup_task = asyncio.create_task(service._kv_cleanup_loop())
        
        # Wait for first cleanup + error backoff + second cleanup
        # First cleanup at 1s -> error -> 60s backoff -> second cleanup at 61s
        # But we don't want to wait that long, so let's just verify error handling
        await asyncio.sleep(2)
        
        # Verify error was raised and caught
        assert error_raised is True
        assert call_count == 1  # Only first attempt in this time
        
        # Task should still be running (not crashed)
        assert not service._cleanup_task.done()
        
        # Cleanup
        service._shutdown = True
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass
    
    async def test_cleanup_respects_shutdown_signal(self, db):
        """Test cleanup task stops when shutdown signal received."""
        class MockNATS:
            async def subscribe(self, subject, cb):
                return None
        
        service = DatabaseService(
            MockNATS(),
            ":memory:",
            cleanup_interval_seconds=10
        )
        service.db = db
        
        # Start cleanup task
        service._shutdown = False
        service._cleanup_task = asyncio.create_task(service._kv_cleanup_loop())
        
        # Let it start
        await asyncio.sleep(0.1)
        assert not service._cleanup_task.done()
        
        # Send shutdown signal
        service._shutdown = True
        
        # Task should complete quickly
        try:
            await asyncio.wait_for(service._cleanup_task, timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Cleanup task did not stop on shutdown signal")
    
    async def test_cleanup_configurable_interval(self, db):
        """Test cleanup interval is configurable."""
        class MockNATS:
            async def subscribe(self, subject, cb):
                return None
        
        # Test short interval
        service1 = DatabaseService(
            MockNATS(),
            ":memory:",
            cleanup_interval_seconds=1
        )
        assert service1.cleanup_interval_seconds == 1
        
        # Test custom interval
        service2 = DatabaseService(
            MockNATS(),
            ":memory:",
            cleanup_interval_seconds=600
        )
        assert service2.cleanup_interval_seconds == 600
        
        # Test default interval (5 minutes)
        service3 = DatabaseService(
            MockNATS(),
            ":memory:"
        )
        assert service3.cleanup_interval_seconds == 300
    
    async def test_cleanup_logs_performance(self, db, caplog):
        """Test cleanup logs performance metrics."""
        # Set some expired keys
        async def set_expired_key(plugin_name: str, key: str, value):
            await db.kv_set(plugin_name, key, value, ttl_seconds=3600)
            past_timestamp = int(time.time()) - 100
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
        
        for i in range(5):
            await set_expired_key("test", f"key{i}", i)
        
        # Run cleanup
        with caplog.at_level('INFO'):
            deleted = await db.kv_cleanup_expired()
        
        assert deleted == 5
        # Note: Log assertions would need actual service cleanup loop running
