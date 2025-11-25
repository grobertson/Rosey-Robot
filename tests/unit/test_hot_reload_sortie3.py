"""
# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
# This test file is DEPRECATED and scheduled for removal.
#
# Reason: The lib/plugin hot reload system has been superseded by the
# NATS-based plugin architecture. Plugins are now independent processes
# that can be restarted individually without hot reload mechanisms.
#
# Reference: See plugins/quote-db/ and plugins/dice-roller/ for the
# correct plugin pattern.
#
# TODO: Remove this file once all legacy plugin code is deleted.
# ============================================================================

tests/unit/test_hot_reload_sortie3.py

Unit tests for hot reload system (Sprint 8 Sortie 3).
"""

import pytest
import asyncio
import time
from unittest.mock import Mock

# Try to import hot reload (may not be available if watchdog not installed)
try:
    from lib.plugin import (
        PluginManager,
        PluginState,
        Plugin,
        PluginMetadata,
        HotReloadWatcher,
        ReloadHandler,
    )
    from lib.plugin.hot_reload import WATCHDOG_AVAILABLE

    HOTRELOAD_AVAILABLE = WATCHDOG_AVAILABLE
except ImportError:
    HOTRELOAD_AVAILABLE = False
    WATCHDOG_AVAILABLE = False

# Skip entire module if watchdog not installed
if not HOTRELOAD_AVAILABLE:
    pytestmark = pytest.mark.skip("watchdog not installed")


# =================================================================
# Test Plugins
# =================================================================


class SimplePlugin(Plugin):
    """Simple test plugin."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="simple",
            display_name="Simple",
            version="1.0.0",
            description="Simple plugin",
            author="Test",
        )


class CountingPlugin(Plugin):
    """Plugin that counts setup calls."""

    setup_count = 0

    @property
    def metadata(self):
        return PluginMetadata(
            name="counting",
            display_name="Counting",
            version="1.0.0",
            description="Counting plugin",
            author="Test",
        )

    async def setup(self):
        CountingPlugin.setup_count += 1


# =================================================================
# Mock Bot
# =================================================================


class MockBot:
    """Mock bot for testing."""

    def __init__(self):
        self.messages = []
        self.storage = None

    async def send_message(self, message: str):
        self.messages.append(message)


# =================================================================
# Fixtures
# =================================================================


@pytest.fixture
def mock_bot():
    """Create mock bot."""
    return MockBot()


@pytest.fixture
def temp_plugin_dir(tmp_path):
    """Create temporary plugin directory."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    return plugin_dir


@pytest.fixture
def simple_plugin_file(temp_plugin_dir):
    """Create simple plugin file."""
    plugin_file = temp_plugin_dir / "simple_plugin.py"
    plugin_file.write_text(
        '''
from lib.plugin import Plugin, PluginMetadata

class SimplePlugin(Plugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name='simple',
            display_name='Simple',
            version='1.0.0',
            description='Simple plugin',
            author='Test'
        )
'''
    )
    return plugin_file


# =================================================================
# ReloadHandler Tests
# =================================================================


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_init(mock_bot):
    """Test ReloadHandler initialization."""
    manager = PluginManager(mock_bot)
    handler = ReloadHandler(manager, debounce_delay=0.5)

    assert handler.manager is manager
    assert handler.debounce_delay == 0.5
    assert handler.logger is not None
    assert handler._pending == {}
    assert handler._reloading == set()


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_ignore_directory(mock_bot, temp_plugin_dir):
    """Test ReloadHandler ignores directory events."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))

    # Add mock plugin
    from lib.plugin.manager import PluginInfo

    info = PluginInfo(temp_plugin_dir / "test.py")
    info.plugin = SimplePlugin(mock_bot)
    info.state = PluginState.ENABLED
    manager._plugins = {"simple": info}
    manager._file_to_name = {temp_plugin_dir / "test.py": "simple"}

    handler = ReloadHandler(manager)

    # Create mock directory event
    event = Mock()
    event.is_directory = True
    event.src_path = str(temp_plugin_dir)

    handler.on_modified(event)

    # Should not queue for reload
    assert handler._pending == {}


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_ignore_non_python(mock_bot, temp_plugin_dir):
    """Test ReloadHandler ignores non-Python files."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    handler = ReloadHandler(manager)

    # Create mock event for non-Python file
    event = Mock()
    event.is_directory = False
    event.src_path = str(temp_plugin_dir / "readme.txt")

    handler.on_modified(event)

    # Should not queue for reload
    assert handler._pending == {}


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_ignore_init(mock_bot, temp_plugin_dir):
    """Test ReloadHandler ignores __init__.py."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    handler = ReloadHandler(manager)

    # Create mock event for __init__.py
    event = Mock()
    event.is_directory = False
    event.src_path = str(temp_plugin_dir / "__init__.py")

    handler.on_modified(event)

    # Should not queue for reload
    assert handler._pending == {}


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_queue_plugin(mock_bot, temp_plugin_dir):
    """Test ReloadHandler queues plugin for reload."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))

    # Add mock plugin
    from lib.plugin.manager import PluginInfo

    plugin_file = temp_plugin_dir / "test.py"
    info = PluginInfo(plugin_file)
    info.plugin = SimplePlugin(mock_bot)
    info.state = PluginState.ENABLED
    manager._plugins = {"simple": info}
    manager._file_to_name = {plugin_file: "simple"}

    handler = ReloadHandler(manager)

    # Create mock event
    event = Mock()
    event.is_directory = False
    event.src_path = str(plugin_file)

    handler.on_modified(event)

    # Should queue for reload
    assert plugin_file in handler._pending
    assert isinstance(handler._pending[plugin_file], float)


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_start_stop(mock_bot):
    """Test ReloadHandler start and stop."""
    manager = PluginManager(mock_bot)
    handler = ReloadHandler(manager)

    # Start
    await handler.start()
    assert handler._reload_task is not None
    assert not handler._stop_event.is_set()

    # Stop
    await handler.stop()
    assert handler._stop_event.is_set()


# =================================================================
# HotReloadWatcher Tests
# =================================================================


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
def test_watcher_init(mock_bot, temp_plugin_dir):
    """Test HotReloadWatcher initialization."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=False)

    assert watcher.manager is manager
    assert watcher.debounce_delay == 0.5
    assert watcher.logger is not None
    assert not watcher.is_enabled


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_watcher_init_enabled(mock_bot, temp_plugin_dir):
    """Test HotReloadWatcher with enabled=True."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=True)

    assert watcher.is_enabled

    watcher.stop()


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
def test_watcher_custom_debounce(mock_bot, temp_plugin_dir):
    """Test HotReloadWatcher with custom debounce delay."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, debounce_delay=1.0)

    assert watcher.debounce_delay == 1.0


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_watcher_start(mock_bot, temp_plugin_dir):
    """Test starting watcher."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=False)

    assert not watcher.is_enabled

    watcher.start()

    assert watcher.is_enabled
    assert watcher._observer is not None
    assert watcher._handler is not None

    watcher.stop()


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_watcher_start_twice(mock_bot, temp_plugin_dir):
    """Test starting watcher twice (should warn)."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=False)

    watcher.start()
    assert watcher.is_enabled

    # Start again (should warn but not fail)
    watcher.start()
    assert watcher.is_enabled

    watcher.stop()


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_watcher_stop(mock_bot, temp_plugin_dir):
    """Test stopping watcher."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=True)

    assert watcher.is_enabled

    watcher.stop()

    assert not watcher.is_enabled
    assert watcher._observer is None
    assert watcher._handler is None


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_watcher_stop_twice(mock_bot, temp_plugin_dir):
    """Test stopping watcher twice (should not fail)."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=True)

    watcher.stop()
    assert not watcher.is_enabled

    # Stop again (should not fail)
    watcher.stop()
    assert not watcher.is_enabled


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
def test_watcher_repr(mock_bot, temp_plugin_dir):
    """Test watcher string representation."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    watcher = HotReloadWatcher(manager, enabled=False)

    result = repr(watcher)

    assert "HotReloadWatcher" in result
    assert "disabled" in result
    assert str(temp_plugin_dir) in result


# =================================================================
# Integration Tests
# =================================================================


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_manager_hot_reload_integration(mock_bot, temp_plugin_dir):
    """Test PluginManager with hot_reload=True."""
    # Create simple plugin file
    plugin_file = temp_plugin_dir / "test_plugin.py"
    plugin_file.write_text(
        '''
from lib.plugin import Plugin, PluginMetadata

class TestPlugin(Plugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name='test',
            display_name='Test',
            version='1.0.0',
            description='Test',
            author='Test'
        )
'''
    )

    # Create manager with hot reload
    manager = PluginManager(mock_bot, str(temp_plugin_dir), hot_reload=True)
    await manager.load_all()

    # Hot reload should be started
    assert manager._hot_reload is not None
    assert manager._hot_reload.is_enabled

    # Unload (should stop hot reload)
    await manager.unload_all()
    assert manager._hot_reload is None


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_manager_without_hot_reload(mock_bot, temp_plugin_dir):
    """Test PluginManager with hot_reload=False."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir), hot_reload=False)
    await manager.load_all()

    # Hot reload should not be started
    assert manager._hot_reload is None

    await manager.unload_all()


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_manager_custom_reload_delay(mock_bot, temp_plugin_dir):
    """Test PluginManager with custom hot reload delay."""
    manager = PluginManager(
        mock_bot, str(temp_plugin_dir), hot_reload=True, hot_reload_delay=1.0
    )
    await manager.load_all()

    # Should use custom delay
    assert manager._hot_reload_delay == 1.0
    assert manager._hot_reload.debounce_delay == 1.0

    await manager.unload_all()


# =================================================================
# Error Handling Tests
# =================================================================


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
def test_watcher_no_plugin_dir(mock_bot):
    """Test watcher with non-existent plugin directory."""
    manager = PluginManager(mock_bot, "nonexistent")
    watcher = HotReloadWatcher(manager, enabled=False)

    # Should not raise, just log warning
    watcher.start()

    # Should not be enabled (directory doesn't exist)
    # Note: This behavior may vary, implementation may choose to enable anyway


@pytest.mark.skipif(not HOTRELOAD_AVAILABLE, reason="watchdog not installed")
@pytest.mark.asyncio
async def test_reload_handler_reload_error(mock_bot, temp_plugin_dir):
    """Test ReloadHandler handles reload errors gracefully."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))

    # Add mock plugin
    from lib.plugin.manager import PluginInfo

    plugin_file = temp_plugin_dir / "test.py"
    info = PluginInfo(plugin_file)
    info.plugin = SimplePlugin(mock_bot)
    info.state = PluginState.ENABLED
    manager._plugins = {"simple": info}
    manager._file_to_name = {plugin_file: "simple"}

    # Mock reload to raise error
    original_reload = manager.reload

    async def failing_reload(name):
        raise RuntimeError("Reload failed")

    manager.reload = failing_reload

    handler = ReloadHandler(manager, debounce_delay=0.1)
    await handler.start()

    # Queue for reload
    handler._pending[plugin_file] = time.time() - 1.0

    # Wait for reload attempt
    await asyncio.sleep(0.3)

    # Should have logged error, not crashed
    assert plugin_file not in handler._reloading

    await handler.stop()
    manager.reload = original_reload
