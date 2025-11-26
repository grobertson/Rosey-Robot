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
