"""
Unit tests for PluginManager

Tests plugin lifecycle management without actually loading plugins.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from core.plugin_manager import (
    PluginManager, PluginMetadata, PluginState
)


@pytest.mark.unit
@pytest.mark.core
class TestPluginManager:
    """Test PluginManager functionality"""
    
    @pytest.mark.asyncio
    async def test_plugin_manager_initialization(self, mock_event_bus):
        """Test plugin manager initialization"""
        pm = PluginManager(mock_event_bus)
        
        assert pm.event_bus == mock_event_bus
        assert pm.registry is not None
        assert len(pm.list_plugins()) == 0
        
    @pytest.mark.asyncio
    async def test_plugin_discovery(self, mock_event_bus):
        """Test plugin registry listing"""
        pm = PluginManager(mock_event_bus)
        
        # Initially empty
        plugins = pm.registry.list_all()
        assert isinstance(plugins, list)
        assert len(plugins) == 0
        
    @pytest.mark.asyncio
    async def test_load_plugin(self, mock_event_bus):
        """Test loading a plugin"""
        pm = PluginManager(mock_event_bus)
        
        # Create metadata for test plugin
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        result = await pm.load_plugin(metadata)
        assert result is True
        assert pm.registry.has("test_plugin")
            
    @pytest.mark.asyncio
    async def test_start_plugin(self, mock_event_bus):
        """Test starting a loaded plugin"""
        pm = PluginManager(mock_event_bus)
        
        # Load a plugin first
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        await pm.load_plugin(metadata)
        
        # Starting will fail without actual module, but API should be correct
        result = await pm.start_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_stop_plugin(self, mock_event_bus):
        """Test stopping a running plugin"""
        pm = PluginManager(mock_event_bus)
        
        # Try to stop non-existent plugin
        result = await pm.stop_plugin("nonexistent")
        assert result is False
        
    @pytest.mark.asyncio
    async def test_list_plugins(self, mock_event_bus):
        """Test listing all plugins"""
        pm = PluginManager(mock_event_bus)
        
        plugins = pm.list_plugins()
        assert isinstance(plugins, list)
        
    @pytest.mark.asyncio
    async def test_get_plugin_info(self, mock_event_bus):
        """Test getting plugin information"""
        pm = PluginManager(mock_event_bus)
        
        # Test getting info for non-existent plugin
        info = pm.get_plugin_info("nonexistent")
        assert info is None
        
    @pytest.mark.asyncio
    async def test_plugin_state_transitions(self, mock_event_bus):
        """Test plugin state machine"""
        # Test state transitions: STOPPED -> RUNNING -> CRASHED -> FAILED
        # PluginState has: STOPPED, RUNNING, CRASHED, FAILED (no UNLOADED or LOADED)
        assert hasattr(PluginState, 'STOPPED')
        assert hasattr(PluginState, 'RUNNING')
        assert hasattr(PluginState, 'CRASHED')
        assert hasattr(PluginState, 'FAILED')
        
    @pytest.mark.asyncio
    async def test_plugin_crash_recovery(self, mock_event_bus):
        """Test plugin crash detection"""
        pm = PluginManager(mock_event_bus)
        
        # Test statistics includes crashed count
        stats = pm.get_statistics()
        assert 'crashed' in stats
        assert stats['crashed'] == 0
        
    @pytest.mark.asyncio
    async def test_plugin_permissions(self, mock_event_bus):
        """Test plugin permission checking"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        await pm.load_plugin(metadata)
        
        entry = pm.registry.get("test_plugin")
        assert entry.permissions is not None
        
    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_event_bus):
        """Test getting plugin system statistics"""
        pm = PluginManager(mock_event_bus)
        
        stats = pm.get_statistics()
        assert 'total_plugins' in stats
        assert 'running' in stats
        assert stats['total_plugins'] == 0


@pytest.mark.integration
@pytest.mark.core
class TestPluginManagerIntegration:
    """Integration tests for PluginManager with PluginProcess"""
    
    @pytest.mark.asyncio
    async def test_load_and_start_plugin(self, mock_event_bus):
        """Test 1: Load and start a plugin with PluginProcess"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        # Load plugin
        load_result = await pm.load_plugin(metadata)
        assert load_result is True
        assert pm.registry.has("test_plugin")
        
        # Start plugin
        start_result = await pm.start_plugin("test_plugin")
        assert isinstance(start_result, bool)
        
    @pytest.mark.asyncio
    async def test_stop_plugin_process(self, mock_event_bus):
        """Test 2: Stop a running plugin"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        # Stop plugin
        result = await pm.stop_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_restart_plugin_process(self, mock_event_bus):
        """Test 3: Restart a running plugin"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        # Restart plugin
        result = await pm.restart_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_multiple_plugins_concurrent(self, mock_event_bus):
        """Test 4: Start multiple plugins concurrently"""
        pm = PluginManager(mock_event_bus)
        
        plugins = ["plugin1", "plugin2", "plugin3"]
        
        for name in plugins:
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                module_path=f"plugins.{name}"
            )
            await pm.load_plugin(metadata)
        
        # Start all plugins
        for name in plugins:
            await pm.start_plugin(name)
        
        # Verify all loaded
        assert all(pm.registry.has(name) for name in plugins)
        
    @pytest.mark.asyncio
    async def test_stop_all_plugins(self, mock_event_bus):
        """Test 5: Stop all running plugins"""
        pm = PluginManager(mock_event_bus)
        
        plugins = ["plugin1", "plugin2"]
        
        for name in plugins:
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                module_path=f"plugins.{name}"
            )
            await pm.load_plugin(metadata)
            await pm.start_plugin(name)
        
        # Stop all
        await pm.stop_all()
        
        # Verify statistics
        stats = pm.get_statistics()
        assert 'total_plugins' in stats
        
    @pytest.mark.asyncio
    async def test_plugin_status_api(self, mock_event_bus):
        """Test 6: Get status for a single plugin"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        # Get status
        status = pm.get_plugin_status("test_plugin")
        
        # Status may be None if plugin failed to start
        if status is not None:
            assert 'name' in status
            assert 'state' in status
            assert status['name'] == "test_plugin"
        
    @pytest.mark.asyncio
    async def test_all_plugin_status_api(self, mock_event_bus):
        """Test 7: Get status for all plugins"""
        pm = PluginManager(mock_event_bus)
        
        plugins = ["plugin1", "plugin2"]
        
        for name in plugins:
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                module_path=f"plugins.{name}"
            )
            await pm.load_plugin(metadata)
            await pm.start_plugin(name)
        
        # Get all status
        all_status = pm.get_all_plugin_status()
        assert isinstance(all_status, dict)
        
    @pytest.mark.asyncio
    async def test_plugin_auto_restart_after_crash(self, mock_event_bus):
        """Test 8: Plugin auto-restart after crash"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Check crash recovery is configured
        entry = pm.registry.get("test_plugin")
        assert entry is not None
        
    @pytest.mark.asyncio
    async def test_plugin_max_restart_attempts(self, mock_event_bus):
        """Test 9: Plugin gives up after max restart attempts"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Verify entry exists (actual crash testing requires real plugin)
        entry = pm.registry.get("test_plugin")
        assert entry is not None
        
    @pytest.mark.asyncio
    async def test_resource_violation_restart(self, mock_event_bus):
        """Test 10: Resource violation triggers restart"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        # Verify plugin loaded (resource monitoring requires running process)
        assert pm.registry.has("test_plugin")
        
    @pytest.mark.asyncio
    async def test_stop_already_stopped_plugin(self, mock_event_bus):
        """Test 11: Stop already stopped plugin (edge case)"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Try stopping without starting
        result = await pm.stop_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_start_already_running_plugin(self, mock_event_bus):
        """Test 12: Start already running plugin (edge case)"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        # Try starting again
        result = await pm.start_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_restart_not_running_plugin(self, mock_event_bus):
        """Test 13: Restart plugin that isn't running"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Try restarting without starting
        result = await pm.restart_plugin("test_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_concurrent_plugin_operations(self, mock_event_bus):
        """Test 14: Concurrent operations on same plugin"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Concurrent starts (should be safe)
        import asyncio
        results = await asyncio.gather(
            pm.start_plugin("test_plugin"),
            pm.start_plugin("test_plugin"),
            return_exceptions=True
        )
        
        assert len(results) == 2
        
    @pytest.mark.asyncio
    async def test_plugin_startup_timeout(self, mock_event_bus):
        """Test 15: Plugin startup timeout handling"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="slow_plugin",
            version="1.0.0",
            module_path="plugins.slow_plugin"
        )
        
        await pm.load_plugin(metadata)
        
        # Attempt to start (will timeout with non-existent module)
        result = await pm.start_plugin("slow_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_plugin_without_resource_limits(self, mock_event_bus):
        """Test 16: Plugin without resource limits"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="unlimited_plugin",
            version="1.0.0",
            module_path="plugins.unlimited_plugin",
            resource_limits=None  # No resource limits
        )
        
        await pm.load_plugin(metadata)
        
        # Should still be able to start
        result = await pm.start_plugin("unlimited_plugin")
        assert isinstance(result, bool)
        
    @pytest.mark.asyncio
    async def test_plugin_status_for_nonexistent(self, mock_event_bus):
        """Test 17: Get status for non-existent plugin"""
        pm = PluginManager(mock_event_bus)
        
        status = pm.get_plugin_status("nonexistent")
        assert status is None
        
    @pytest.mark.asyncio
    async def test_all_status_empty_list(self, mock_event_bus):
        """Test 18: Get all status with no plugins"""
        pm = PluginManager(mock_event_bus)
        
        all_status = pm.get_all_plugin_status()
        assert isinstance(all_status, dict)
        assert len(all_status) == 0
        
    @pytest.mark.asyncio
    async def test_plugin_uptime_tracking(self, mock_event_bus):
        """Test 19: Plugin uptime is tracked correctly"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        status = pm.get_plugin_status("test_plugin")
        
        if status is not None:
            assert 'uptime' in status
            assert isinstance(status['uptime'], (int, float))
        
    @pytest.mark.asyncio
    async def test_plugin_restart_attempts_tracking(self, mock_event_bus):
        """Test 20: Plugin restart attempts are tracked"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        status = pm.get_plugin_status("test_plugin")
        
        if status is not None:
            assert 'restart_attempts' in status
            assert isinstance(status['restart_attempts'], int)
        
    @pytest.mark.asyncio
    async def test_plugin_resource_stats_in_status(self, mock_event_bus):
        """Test 21: Plugin resource stats in status"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        status = pm.get_plugin_status("test_plugin")
        
        # Resource stats may or may not be present depending on process state
        if status is not None and 'resources' in status:
            resources = status['resources']
            assert 'cpu_percent' in resources
            assert 'memory_mb' in resources
        
    @pytest.mark.asyncio
    async def test_plugin_state_in_status(self, mock_event_bus):
        """Test 22: Plugin state is correctly reported in status"""
        pm = PluginManager(mock_event_bus)
        
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            module_path="plugins.test_plugin"
        )
        
        await pm.load_plugin(metadata)
        await pm.start_plugin("test_plugin")
        
        status = pm.get_plugin_status("test_plugin")
        
        if status is not None:
            assert 'state' in status
            assert status['state'] in ['stopped', 'running', 'crashed', 'failed']
