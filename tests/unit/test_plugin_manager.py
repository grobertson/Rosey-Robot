"""
# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
# This test file is DEPRECATED and scheduled for removal.
#
# Reason: The centralized PluginManager has been superseded by the NATS-based
# plugin architecture. Plugins now run as independent processes and communicate
# via NATS messaging. There is no central manager.
#
# Reference: See plugins/quote-db/ and plugins/dice-roller/ for the
# correct plugin pattern.
#
# TODO: Remove this file once all legacy plugin code is deleted.
# ============================================================================

Unit tests for plugin manager system.

Tests cover:
- PluginMetadata: Plugin information and configuration
- PluginEntry: Registry entry combining metadata and runtime
- PluginRegistry: Plugin tracking and dependency management
- PluginManager: Central orchestration and lifecycle management
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from bot.rosey.core.plugin_manager import (
    PluginMetadata,
    PluginEntry,
    PluginRegistry,
    PluginManager
)
from bot.rosey.core.plugin_isolation import PluginState, PluginProcess
from bot.rosey.core.plugin_permissions import (
    PermissionProfile,
    PluginPermissions
)
from bot.rosey.core.event_bus import EventBus


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = AsyncMock(spec=EventBus)
    bus.is_connected.return_value = True
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def sample_metadata():
    """Sample plugin metadata"""
    return PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        description="Test plugin",
        author="Test Author",
        module_path="test.plugin",
        permission_profile=PermissionProfile.STANDARD
    )


# ============================================================================
# PluginMetadata Tests
# ============================================================================

class TestPluginMetadata:
    """Test plugin metadata"""

    def test_metadata_creation(self):
        """Test creating plugin metadata"""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author"
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test plugin"
        assert metadata.author == "Test Author"
        assert metadata.permission_profile == PermissionProfile.STANDARD
        assert metadata.auto_start is True
        assert metadata.enabled is True

    def test_metadata_defaults(self):
        """Test metadata default values"""
        metadata = PluginMetadata(name="test")

        assert metadata.version == "1.0.0"
        assert metadata.description == ""
        assert metadata.dependencies == []
        assert metadata.permission_profile == PermissionProfile.STANDARD
        assert metadata.auto_start is True

    def test_metadata_with_dependencies(self):
        """Test metadata with dependencies"""
        metadata = PluginMetadata(
            name="advanced-plugin",
            dependencies=["base-plugin", "utils-plugin"]
        )

        assert "base-plugin" in metadata.dependencies
        assert "utils-plugin" in metadata.dependencies

    def test_metadata_to_dict(self):
        """Test serializing metadata"""
        metadata = PluginMetadata(
            name="test-plugin",
            version="0.2.0",
            description="Test",
            author="Author",
            module_path="test.module",
            dependencies=["dep1"]
        )

        data = metadata.to_dict()

        assert data["name"] == "test-plugin"
        assert data["version"] == "0.2.0"
        assert data["description"] == "Test"
        assert data["author"] == "Author"
        assert data["module_path"] == "test.module"
        assert data["dependencies"] == ["dep1"]
        assert data["permission_profile"] == "standard"

    def test_metadata_from_dict(self):
        """Test deserializing metadata"""
        data = {
            "name": "test-plugin",
            "version": "0.2.0",
            "description": "Test plugin",
            "author": "Author",
            "module_path": "test.module",
            "dependencies": ["dep1", "dep2"],
            "permission_profile": "extended",
            "auto_start": False,
            "enabled": True,
            "priority": 5
        }

        metadata = PluginMetadata.from_dict(data)

        assert metadata.name == "test-plugin"
        assert metadata.version == "0.2.0"
        assert metadata.description == "Test plugin"
        assert metadata.dependencies == ["dep1", "dep2"]
        assert metadata.permission_profile == PermissionProfile.EXTENDED
        assert metadata.auto_start is False
        assert metadata.priority == 5

    def test_metadata_roundtrip(self):
        """Test serialization roundtrip"""
        original = PluginMetadata(
            name="roundtrip-test",
            version="1.2.3",
            description="Test roundtrip",
            dependencies=["dep1"],
            permission_profile=PermissionProfile.MINIMAL,
            auto_start=False,
            priority=10
        )

        data = original.to_dict()
        restored = PluginMetadata.from_dict(data)

        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.description == original.description
        assert restored.dependencies == original.dependencies
        assert restored.permission_profile == original.permission_profile
        assert restored.auto_start == original.auto_start
        assert restored.priority == original.priority


# ============================================================================
# PluginEntry Tests
# ============================================================================

class TestPluginEntry:
    """Test plugin registry entry"""

    def test_entry_creation(self, sample_metadata):
        """Test creating plugin entry"""
        entry = PluginEntry(metadata=sample_metadata)

        assert entry.metadata is sample_metadata
        assert entry.process is None
        assert entry.permissions is None
        assert entry.ipc is None

    def test_entry_with_permissions(self, sample_metadata):
        """Test entry with permissions"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )

        entry = PluginEntry(
            metadata=sample_metadata,
            permissions=perms
        )

        assert entry.permissions is perms

    def test_get_state_no_process(self, sample_metadata):
        """Test getting state when no process"""
        entry = PluginEntry(metadata=sample_metadata)

        assert entry.get_state() == PluginState.STOPPED

    def test_get_state_with_process(self, sample_metadata, mock_event_bus):
        """Test getting state with process"""
        process = Mock(spec=PluginProcess)
        process.state = PluginState.RUNNING

        entry = PluginEntry(
            metadata=sample_metadata,
            process=process
        )

        assert entry.get_state() == PluginState.RUNNING

    def test_is_running_no_process(self, sample_metadata):
        """Test is_running with no process"""
        entry = PluginEntry(metadata=sample_metadata)

        assert entry.is_running() is False

    def test_is_running_with_process(self, sample_metadata):
        """Test is_running with process"""
        process = Mock(spec=PluginProcess)
        process.is_alive.return_value = True

        entry = PluginEntry(
            metadata=sample_metadata,
            process=process
        )

        assert entry.is_running() is True

    def test_get_uptime(self, sample_metadata):
        """Test getting uptime"""
        process = Mock(spec=PluginProcess)
        process.get_uptime.return_value = 123.45

        entry = PluginEntry(
            metadata=sample_metadata,
            process=process
        )

        assert entry.get_uptime() == 123.45


# ============================================================================
# PluginRegistry Tests
# ============================================================================

class TestPluginRegistry:
    """Test plugin registry"""

    def test_registry_creation(self):
        """Test creating registry"""
        registry = PluginRegistry()

        assert len(registry._plugins) == 0
        assert len(registry._dependency_graph) == 0

    def test_register_plugin(self, sample_metadata):
        """Test registering plugin"""
        registry = PluginRegistry()
        entry = PluginEntry(metadata=sample_metadata)

        registry.register(entry)

        assert registry.has("test-plugin")
        assert len(registry.list_all()) == 1

    def test_unregister_plugin(self, sample_metadata):
        """Test unregistering plugin"""
        registry = PluginRegistry()
        entry = PluginEntry(metadata=sample_metadata)

        registry.register(entry)
        assert registry.has("test-plugin")

        success = registry.unregister("test-plugin")

        assert success is True
        assert not registry.has("test-plugin")

    def test_unregister_nonexistent(self):
        """Test unregistering non-existent plugin"""
        registry = PluginRegistry()

        success = registry.unregister("nonexistent")

        assert success is False

    def test_get_plugin(self, sample_metadata):
        """Test getting plugin entry"""
        registry = PluginRegistry()
        entry = PluginEntry(metadata=sample_metadata)
        registry.register(entry)

        retrieved = registry.get("test-plugin")

        assert retrieved is entry

    def test_get_nonexistent(self):
        """Test getting non-existent plugin"""
        registry = PluginRegistry()

        entry = registry.get("nonexistent")

        assert entry is None

    def test_list_all(self, sample_metadata):
        """Test listing all plugins"""
        registry = PluginRegistry()

        metadata1 = sample_metadata
        metadata2 = PluginMetadata(name="plugin2")
        metadata3 = PluginMetadata(name="plugin3")

        registry.register(PluginEntry(metadata=metadata1))
        registry.register(PluginEntry(metadata=metadata2))
        registry.register(PluginEntry(metadata=metadata3))

        all_plugins = registry.list_all()

        assert len(all_plugins) == 3
        assert "test-plugin" in all_plugins
        assert "plugin2" in all_plugins
        assert "plugin3" in all_plugins

    def test_list_running(self, sample_metadata):
        """Test listing running plugins"""
        registry = PluginRegistry()

        # Create entries with different states
        running_process = Mock(spec=PluginProcess)
        running_process.is_alive.return_value = True

        stopped_process = Mock(spec=PluginProcess)
        stopped_process.is_alive.return_value = False

        metadata1 = PluginMetadata(name="running-plugin")
        metadata2 = PluginMetadata(name="stopped-plugin")
        metadata3 = PluginMetadata(name="no-process-plugin")

        registry.register(PluginEntry(
            metadata=metadata1,
            process=running_process
        ))
        registry.register(PluginEntry(
            metadata=metadata2,
            process=stopped_process
        ))
        registry.register(PluginEntry(metadata=metadata3))

        running = registry.list_running()

        assert len(running) == 1
        assert "running-plugin" in running

    def test_list_by_state(self):
        """Test listing plugins by state"""
        registry = PluginRegistry()

        process1 = Mock(spec=PluginProcess)
        process1.state = PluginState.RUNNING
        process1.is_alive.return_value = True

        process2 = Mock(spec=PluginProcess)
        process2.state = PluginState.CRASHED
        process2.is_alive.return_value = False

        registry.register(PluginEntry(
            metadata=PluginMetadata(name="running"),
            process=process1
        ))
        registry.register(PluginEntry(
            metadata=PluginMetadata(name="crashed"),
            process=process2
        ))

        running = registry.list_by_state(PluginState.RUNNING)
        crashed = registry.list_by_state(PluginState.CRASHED)

        assert "running" in running
        assert "crashed" in crashed

    def test_get_dependencies(self):
        """Test getting plugin dependencies"""
        registry = PluginRegistry()

        metadata = PluginMetadata(
            name="dependent",
            dependencies=["dep1", "dep2"]
        )
        registry.register(PluginEntry(metadata=metadata))

        deps = registry.get_dependencies("dependent")

        assert deps == {"dep1", "dep2"}

    def test_get_dependents(self):
        """Test getting plugins that depend on a plugin"""
        registry = PluginRegistry()

        base = PluginMetadata(name="base")
        dependent1 = PluginMetadata(name="dep1", dependencies=["base"])
        dependent2 = PluginMetadata(name="dep2", dependencies=["base", "other"])
        independent = PluginMetadata(name="indep")

        registry.register(PluginEntry(metadata=base))
        registry.register(PluginEntry(metadata=dependent1))
        registry.register(PluginEntry(metadata=dependent2))
        registry.register(PluginEntry(metadata=independent))

        dependents = registry.get_dependents("base")

        assert "dep1" in dependents
        assert "dep2" in dependents
        assert "indep" not in dependents

    def test_check_dependencies_all_met(self):
        """Test checking dependencies when all are met"""
        registry = PluginRegistry()

        # Create dependencies as running
        dep_process = Mock(spec=PluginProcess)
        dep_process.is_alive.return_value = True

        registry.register(PluginEntry(
            metadata=PluginMetadata(name="dep1"),
            process=dep_process
        ))
        registry.register(PluginEntry(
            metadata=PluginMetadata(name="dep2"),
            process=dep_process
        ))

        # Create dependent
        registry.register(PluginEntry(
            metadata=PluginMetadata(
                name="dependent",
                dependencies=["dep1", "dep2"]
            )
        ))

        result = registry.check_dependencies("dependent")

        assert result is True

    def test_check_dependencies_missing(self):
        """Test checking dependencies when some are missing"""
        registry = PluginRegistry()

        registry.register(PluginEntry(
            metadata=PluginMetadata(name="dep1")
        ))
        # dep2 not registered

        registry.register(PluginEntry(
            metadata=PluginMetadata(
                name="dependent",
                dependencies=["dep1", "dep2"]
            )
        ))

        result = registry.check_dependencies("dependent")

        assert result is False

    def test_get_load_order_simple(self):
        """Test getting load order with simple dependencies"""
        registry = PluginRegistry()

        base = PluginMetadata(name="base")
        middle = PluginMetadata(name="middle", dependencies=["base"])
        top = PluginMetadata(name="top", dependencies=["middle"])

        registry.register(PluginEntry(metadata=top))  # Register out of order
        registry.register(PluginEntry(metadata=base))
        registry.register(PluginEntry(metadata=middle))

        order = registry.get_load_order()

        # base should come before middle, middle before top
        assert order.index("base") < order.index("middle")
        assert order.index("middle") < order.index("top")

    def test_get_load_order_with_priority(self):
        """Test load order respects priority"""
        registry = PluginRegistry()

        low = PluginMetadata(name="low", priority=1)
        high = PluginMetadata(name="high", priority=10)
        medium = PluginMetadata(name="medium", priority=5)

        registry.register(PluginEntry(metadata=low))
        registry.register(PluginEntry(metadata=medium))
        registry.register(PluginEntry(metadata=high))

        order = registry.get_load_order()

        # Higher priority loads first
        assert order.index("high") < order.index("medium")
        assert order.index("medium") < order.index("low")


# ============================================================================
# PluginManager Tests
# ============================================================================

@pytest.mark.asyncio
class TestPluginManager:
    """Test plugin manager"""

    async def test_manager_creation(self, mock_event_bus):
        """Test creating plugin manager"""
        manager = PluginManager(mock_event_bus)

        assert manager.event_bus is mock_event_bus
        assert isinstance(manager.registry, PluginRegistry)

    async def test_load_plugin(self, mock_event_bus, sample_metadata):
        """Test loading a plugin"""
        manager = PluginManager(mock_event_bus)

        success = await manager.load_plugin(sample_metadata)

        assert success is True
        assert manager.registry.has("test-plugin")

        entry = manager.registry.get("test-plugin")
        assert entry.metadata is sample_metadata
        assert entry.permissions is not None

    async def test_load_plugin_already_loaded(self, mock_event_bus, sample_metadata):
        """Test loading already loaded plugin"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)
        success = await manager.load_plugin(sample_metadata)

        assert success is False

    async def test_load_plugin_no_module_path(self, mock_event_bus):
        """Test loading plugin without module path"""
        manager = PluginManager(mock_event_bus)
        metadata = PluginMetadata(name="test", module_path="")

        success = await manager.load_plugin(metadata)

        assert success is False

    async def test_unload_plugin(self, mock_event_bus, sample_metadata):
        """Test unloading a plugin"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)
        success = await manager.unload_plugin("test-plugin")

        assert success is True
        assert not manager.registry.has("test-plugin")

    async def test_unload_nonexistent(self, mock_event_bus):
        """Test unloading non-existent plugin"""
        manager = PluginManager(mock_event_bus)

        success = await manager.unload_plugin("nonexistent")

        assert success is False

    async def test_start_plugin(self, mock_event_bus, sample_metadata):
        """Test starting a plugin"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)

        with patch('bot.rosey.core.plugin_manager.PluginProcess') as MockProcess:
            mock_process = Mock()
            mock_process.start = AsyncMock(return_value=True)
            MockProcess.return_value = mock_process

            success = await manager.start_plugin("test-plugin")

            assert success is True
            MockProcess.assert_called_once()

    async def test_start_plugin_not_loaded(self, mock_event_bus):
        """Test starting plugin that's not loaded"""
        manager = PluginManager(mock_event_bus)

        success = await manager.start_plugin("nonexistent")

        assert success is False

    async def test_stop_plugin(self, mock_event_bus, sample_metadata):
        """Test stopping a plugin"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)

        # Start plugin first
        mock_process = Mock()
        mock_process.start = AsyncMock(return_value=True)
        mock_process.stop = AsyncMock(return_value=True)
        mock_process.is_alive.return_value = True

        entry = manager.registry.get("test-plugin")
        entry.process = mock_process

        success = await manager.stop_plugin("test-plugin")

        assert success is True
        mock_process.stop.assert_called_once()

    async def test_restart_plugin(self, mock_event_bus, sample_metadata):
        """Test restarting a plugin"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)

        mock_process = Mock()
        mock_process.restart = AsyncMock(return_value=True)

        entry = manager.registry.get("test-plugin")
        entry.process = mock_process

        success = await manager.restart_plugin("test-plugin")

        assert success is True
        mock_process.restart.assert_called_once()

    async def test_get_plugin_info(self, mock_event_bus, sample_metadata):
        """Test getting plugin info"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)

        info = manager.get_plugin_info("test-plugin")

        assert info is not None
        assert info["name"] == "test-plugin"
        assert info["version"] == "1.0.0"
        assert "state" in info
        assert "permissions" in info

    async def test_get_plugin_info_nonexistent(self, mock_event_bus):
        """Test getting info for non-existent plugin"""
        manager = PluginManager(mock_event_bus)

        info = manager.get_plugin_info("nonexistent")

        assert info is None

    async def test_list_plugins(self, mock_event_bus):
        """Test listing all plugins"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(PluginMetadata(name="plugin1", module_path="p1"))
        await manager.load_plugin(PluginMetadata(name="plugin2", module_path="p2"))

        plugins = manager.list_plugins()

        assert len(plugins) == 2
        assert any(p["name"] == "plugin1" for p in plugins)
        assert any(p["name"] == "plugin2" for p in plugins)

    async def test_get_statistics(self, mock_event_bus, sample_metadata):
        """Test getting statistics"""
        manager = PluginManager(mock_event_bus)

        await manager.load_plugin(sample_metadata)

        stats = manager.get_statistics()

        assert stats["total_plugins"] == 1
        assert "running" in stats
        assert "stopped" in stats

    async def test_add_callback(self, mock_event_bus):
        """Test adding event callback"""
        manager = PluginManager(mock_event_bus)
        callback = Mock()

        manager.add_callback("plugin_loaded", callback)

        metadata = PluginMetadata(name="test", module_path="test.module")
        await manager.load_plugin(metadata)

        callback.assert_called_once_with("test")


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestPluginManagerIntegration:
    """Test plugin manager integration scenarios"""

    async def test_full_lifecycle(self, mock_event_bus):
        """Test complete plugin lifecycle"""
        manager = PluginManager(mock_event_bus)

        metadata = PluginMetadata(
            name="lifecycle-test",
            version="1.0.0",
            module_path="test.module"
        )

        # Load
        assert await manager.load_plugin(metadata) is True
        assert manager.registry.has("lifecycle-test")

        # Start (with mocked process)
        with patch('bot.rosey.core.plugin_manager.PluginProcess') as MockProcess:
            mock_process = Mock()
            mock_process.start = AsyncMock(return_value=True)
            mock_process.stop = AsyncMock(return_value=True)
            mock_process.is_alive.return_value = True
            MockProcess.return_value = mock_process

            assert await manager.start_plugin("lifecycle-test") is True

            # Stop
            entry = manager.registry.get("lifecycle-test")
            entry.process = mock_process
            assert await manager.stop_plugin("lifecycle-test") is True

        # Unload
        assert await manager.unload_plugin("lifecycle-test") is True
        assert not manager.registry.has("lifecycle-test")

    async def test_dependency_chain(self, mock_event_bus):
        """Test loading plugins with dependencies"""
        manager = PluginManager(mock_event_bus)

        base = PluginMetadata(name="base", module_path="base")
        dependent = PluginMetadata(
            name="dependent",
            module_path="dependent",
            dependencies=["base"]
        )

        # Load both
        await manager.load_plugin(base)
        await manager.load_plugin(dependent)

        # Check load order
        order = manager.registry.get_load_order()
        assert order.index("base") < order.index("dependent")

        # Check dependencies
        assert manager.registry.check_dependencies("dependent") is False  # base not running

    async def test_callbacks_triggered(self, mock_event_bus):
        """Test that callbacks are triggered"""
        manager = PluginManager(mock_event_bus)

        loaded_plugins = []
        unloaded_plugins = []

        manager.add_callback("plugin_loaded", lambda name: loaded_plugins.append(name))
        manager.add_callback("plugin_unloaded", lambda name: unloaded_plugins.append(name))

        metadata = PluginMetadata(name="callback-test", module_path="test")

        await manager.load_plugin(metadata)
        assert "callback-test" in loaded_plugins

        await manager.unload_plugin("callback-test")
        assert "callback-test" in unloaded_plugins
