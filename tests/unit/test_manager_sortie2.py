"""
# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
# This test file is DEPRECATED and scheduled for removal.
#
# Reason: The lib/plugin PluginManager has been superseded by the
# NATS-based plugin architecture. Plugins now run as independent processes
# and there is no central manager.
#
# Reference: See plugins/quote-db/ and plugins/dice-roller/ for the
# correct plugin pattern.
#
# TODO: Remove this file once all legacy plugin code is deleted.
# ============================================================================

tests/unit/test_plugin_manager_sortie2.py

Unit tests for plugin manager (Sprint 8 Sortie 2).
"""

import pytest
from pathlib import Path
from lib.plugin import (
    PluginManager,
    PluginState,
    PluginInfo,
    Plugin,
    PluginMetadata,
    PluginError,
    PluginDependencyError,
)


# =================================================================
# Test Plugins
# =================================================================


class TestPluginA(Plugin):
    """Test plugin A (no dependencies)."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="plugin_a",
            display_name="Plugin A",
            version="1.0.0",
            description="Test plugin A",
            author="Test",
            dependencies=[],
        )


class TestPluginB(Plugin):
    """Test plugin B (depends on A)."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="plugin_b",
            display_name="Plugin B",
            version="1.0.0",
            description="Test plugin B",
            author="Test",
            dependencies=["plugin_a"],
        )


class TestPluginC(Plugin):
    """Test plugin C (depends on B)."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="plugin_c",
            display_name="Plugin C",
            version="1.0.0",
            description="Test plugin C",
            author="Test",
            dependencies=["plugin_b"],
        )


class CircularPluginA(Plugin):
    """Plugin with circular dependency (A -> B)."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="circular_a",
            display_name="Circular A",
            version="1.0.0",
            description="Circular dependency A",
            author="Test",
            dependencies=["circular_b"],
        )


class CircularPluginB(Plugin):
    """Plugin with circular dependency (B -> A)."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="circular_b",
            display_name="Circular B",
            version="1.0.0",
            description="Circular dependency B",
            author="Test",
            dependencies=["circular_a"],
        )


class FailingSetupPlugin(Plugin):
    """Plugin that fails during setup."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="failing_setup",
            display_name="Failing Setup",
            version="1.0.0",
            description="Fails during setup",
            author="Test",
        )

    async def setup(self):
        raise RuntimeError("Setup intentionally failed")


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


# =================================================================
# PluginState Tests
# =================================================================


def test_plugin_state_enum():
    """Test PluginState enum values."""
    assert PluginState.UNLOADED.value == "unloaded"
    assert PluginState.LOADED.value == "loaded"
    assert PluginState.SETUP.value == "setup"
    assert PluginState.ENABLED.value == "enabled"
    assert PluginState.DISABLED.value == "disabled"
    assert PluginState.TORN_DOWN.value == "torn_down"
    assert PluginState.FAILED.value == "failed"


# =================================================================
# PluginInfo Tests
# =================================================================


def test_plugin_info_init():
    """Test PluginInfo initialization."""
    file_path = Path("plugins/test.py")
    info = PluginInfo(file_path)

    assert info.plugin is None
    assert info.state == PluginState.UNLOADED
    assert info.error is None
    assert info.file_path == file_path


def test_plugin_info_properties(mock_bot):
    """Test PluginInfo properties."""
    file_path = Path("plugins/test.py")
    info = PluginInfo(file_path)

    # Before plugin loaded
    assert info.name is None
    assert info.metadata is None

    # After plugin loaded
    plugin = TestPluginA(mock_bot)
    info.plugin = plugin
    info.state = PluginState.LOADED

    assert info.name == "plugin_a"
    assert info.metadata.display_name == "Plugin A"


def test_plugin_info_str(mock_bot):
    """Test PluginInfo string representation."""
    file_path = Path("plugins/test.py")
    info = PluginInfo(file_path)

    # Before plugin loaded
    result = str(info)
    assert "test" in result
    assert "unloaded" in result

    # After plugin loaded
    plugin = TestPluginA(mock_bot)
    info.plugin = plugin
    info.state = PluginState.LOADED

    result = str(info)
    assert "Plugin A" in result
    assert "loaded" in result


def test_plugin_info_repr(mock_bot):
    """Test PluginInfo repr."""
    file_path = Path("plugins/test.py")
    info = PluginInfo(file_path)

    # Before plugin loaded
    result = repr(info)
    assert "PluginInfo" in result
    assert "test.py" in result

    # After plugin loaded
    plugin = TestPluginA(mock_bot)
    info.plugin = plugin
    info.state = PluginState.LOADED

    result = repr(info)
    assert "plugin_a" in result
    assert "1.0.0" in result


# =================================================================
# PluginManager Initialization Tests
# =================================================================


def test_manager_init(mock_bot):
    """Test PluginManager initialization."""
    manager = PluginManager(mock_bot, "plugins")

    assert manager.bot is mock_bot
    assert manager.plugin_dir == Path("plugins")
    assert manager.logger is not None
    assert manager._plugins == {}
    assert manager._file_to_name == {}


def test_manager_custom_logger(mock_bot):
    """Test PluginManager with custom logger."""
    import logging

    logger = logging.getLogger("test")
    manager = PluginManager(mock_bot, "plugins", logger=logger)

    assert manager.logger is logger


# =================================================================
# Discovery Tests
# =================================================================


@pytest.mark.asyncio
async def test_discover_no_directory(mock_bot):
    """Test discover with non-existent directory."""
    manager = PluginManager(mock_bot, "nonexistent")

    with pytest.raises(PluginError) as exc_info:
        manager.discover()

    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_discover_empty_directory(mock_bot, temp_plugin_dir):
    """Test discover with empty directory."""
    manager = PluginManager(mock_bot, str(temp_plugin_dir))

    files = manager.discover()

    assert files == []


@pytest.mark.asyncio
async def test_discover_plugin_files(mock_bot, temp_plugin_dir):
    """Test discovering plugin files."""
    # Create plugin files
    (temp_plugin_dir / "plugin1.py").write_text("# Plugin 1")
    (temp_plugin_dir / "plugin2.py").write_text("# Plugin 2")
    (temp_plugin_dir / "__init__.py").write_text("# Init")
    (temp_plugin_dir / "not_python.txt").write_text("Text file")

    manager = PluginManager(mock_bot, str(temp_plugin_dir))
    files = manager.discover()

    # Should find 2 .py files (excluding __init__.py)
    assert len(files) == 2
    assert all(f.suffix == ".py" for f in files)
    assert all(f.name != "__init__.py" for f in files)


# =================================================================
# Dependency Resolution Tests
# =================================================================


@pytest.mark.asyncio
async def test_resolve_no_dependencies(mock_bot):
    """Test dependency resolution with no dependencies."""
    manager = PluginManager(mock_bot)

    # Add plugin with no dependencies
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.LOADED
    manager._plugins = {"plugin_a": info}

    order = manager._resolve_dependencies()

    assert order == ["plugin_a"]


@pytest.mark.asyncio
async def test_resolve_simple_dependency(mock_bot):
    """Test dependency resolution with simple dependency chain."""
    manager = PluginManager(mock_bot)

    # Add plugins: B depends on A
    info_a = PluginInfo(Path("a.py"))
    info_a.plugin = TestPluginA(mock_bot)
    info_a.state = PluginState.LOADED

    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = TestPluginB(mock_bot)
    info_b.state = PluginState.LOADED

    manager._plugins = {"plugin_a": info_a, "plugin_b": info_b}

    order = manager._resolve_dependencies()

    # A should come before B
    assert order.index("plugin_a") < order.index("plugin_b")


@pytest.mark.asyncio
async def test_resolve_complex_dependency(mock_bot):
    """Test dependency resolution with complex chain."""
    manager = PluginManager(mock_bot)

    # Add plugins: C depends on B, B depends on A
    info_a = PluginInfo(Path("a.py"))
    info_a.plugin = TestPluginA(mock_bot)
    info_a.state = PluginState.LOADED

    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = TestPluginB(mock_bot)
    info_b.state = PluginState.LOADED

    info_c = PluginInfo(Path("c.py"))
    info_c.plugin = TestPluginC(mock_bot)
    info_c.state = PluginState.LOADED

    manager._plugins = {"plugin_a": info_a, "plugin_b": info_b, "plugin_c": info_c}

    order = manager._resolve_dependencies()

    # A before B, B before C
    assert order.index("plugin_a") < order.index("plugin_b")
    assert order.index("plugin_b") < order.index("plugin_c")


@pytest.mark.asyncio
async def test_resolve_missing_dependency(mock_bot):
    """Test dependency resolution with missing dependency."""
    manager = PluginManager(mock_bot)

    # Add plugin B which depends on A, but A is missing
    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = TestPluginB(mock_bot)
    info_b.state = PluginState.LOADED

    manager._plugins = {"plugin_b": info_b}

    with pytest.raises(PluginDependencyError) as exc_info:
        manager._resolve_dependencies()

    assert "missing plugin" in str(exc_info.value)
    assert "plugin_a" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_circular_dependency(mock_bot):
    """Test dependency resolution with circular dependency."""
    manager = PluginManager(mock_bot)

    # Add plugins with circular dependency
    info_a = PluginInfo(Path("a.py"))
    info_a.plugin = CircularPluginA(mock_bot)
    info_a.state = PluginState.LOADED

    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = CircularPluginB(mock_bot)
    info_b.state = PluginState.LOADED

    manager._plugins = {"circular_a": info_a, "circular_b": info_b}

    with pytest.raises(PluginDependencyError) as exc_info:
        manager._resolve_dependencies()

    assert "circular" in str(exc_info.value).lower()


# =================================================================
# Lifecycle Management Tests
# =================================================================


@pytest.mark.asyncio
async def test_setup_plugin(mock_bot):
    """Test plugin setup."""
    manager = PluginManager(mock_bot)

    # Add plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.LOADED
    manager._plugins = {"plugin_a": info}

    await manager._setup_plugin("plugin_a")

    assert info.state == PluginState.SETUP


@pytest.mark.asyncio
async def test_setup_plugin_failure(mock_bot):
    """Test plugin setup failure."""
    manager = PluginManager(mock_bot)

    # Add failing plugin
    info = PluginInfo(Path("failing.py"))
    info.plugin = FailingSetupPlugin(mock_bot)
    info.state = PluginState.LOADED
    manager._plugins = {"failing_setup": info}

    with pytest.raises(Exception):
        await manager._setup_plugin("failing_setup")

    assert info.state == PluginState.FAILED
    assert info.error is not None


@pytest.mark.asyncio
async def test_enable_plugin(mock_bot):
    """Test plugin enable."""
    manager = PluginManager(mock_bot)

    # Add plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.SETUP
    manager._plugins = {"plugin_a": info}

    await manager._enable_plugin("plugin_a")

    assert info.state == PluginState.ENABLED
    assert info.plugin.is_enabled is True


@pytest.mark.asyncio
async def test_disable_plugin(mock_bot):
    """Test plugin disable."""
    manager = PluginManager(mock_bot)

    # Add enabled plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.ENABLED
    info.plugin._is_enabled = True
    manager._plugins = {"plugin_a": info}

    await manager._disable_plugin("plugin_a")

    assert info.state == PluginState.DISABLED
    assert info.plugin.is_enabled is False


@pytest.mark.asyncio
async def test_teardown_plugin(mock_bot):
    """Test plugin teardown."""
    manager = PluginManager(mock_bot)

    # Add disabled plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.DISABLED
    manager._plugins = {"plugin_a": info}

    await manager._teardown_plugin("plugin_a")

    assert info.state == PluginState.TORN_DOWN


# =================================================================
# Public API Tests
# =================================================================


@pytest.mark.asyncio
async def test_enable_not_found(mock_bot):
    """Test enable with plugin not found."""
    manager = PluginManager(mock_bot)

    with pytest.raises(PluginError) as exc_info:
        await manager.enable("nonexistent")

    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_enable_already_enabled(mock_bot):
    """Test enable already enabled plugin."""
    manager = PluginManager(mock_bot)

    # Add enabled plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.ENABLED
    manager._plugins = {"plugin_a": info}

    # Should not raise, just log warning
    await manager.enable("plugin_a")

    assert info.state == PluginState.ENABLED


@pytest.mark.asyncio
async def test_enable_wrong_state(mock_bot):
    """Test enable from wrong state."""
    manager = PluginManager(mock_bot)

    # Add unloaded plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.UNLOADED
    manager._plugins = {"plugin_a": info}

    with pytest.raises(PluginError) as exc_info:
        await manager.enable("plugin_a")

    assert "state" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_disable_not_found(mock_bot):
    """Test disable with plugin not found."""
    manager = PluginManager(mock_bot)

    with pytest.raises(PluginError):
        await manager.disable("nonexistent")


@pytest.mark.asyncio
async def test_disable_not_enabled(mock_bot):
    """Test disable not enabled plugin."""
    manager = PluginManager(mock_bot)

    # Add disabled plugin
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.DISABLED
    manager._plugins = {"plugin_a": info}

    # Should not raise, just log warning
    await manager.disable("plugin_a")

    assert info.state == PluginState.DISABLED


@pytest.mark.asyncio
async def test_get_plugin(mock_bot):
    """Test get plugin by name."""
    manager = PluginManager(mock_bot)

    # Add plugin
    info = PluginInfo(Path("a.py"))
    plugin = TestPluginA(mock_bot)
    info.plugin = plugin
    info.state = PluginState.LOADED
    manager._plugins = {"plugin_a": info}

    result = manager.get("plugin_a")

    assert result is plugin


@pytest.mark.asyncio
async def test_get_plugin_not_found(mock_bot):
    """Test get with plugin not found."""
    manager = PluginManager(mock_bot)

    result = manager.get("nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_list_plugins(mock_bot):
    """Test list all plugins."""
    manager = PluginManager(mock_bot)

    # Add plugins
    info_a = PluginInfo(Path("a.py"))
    info_a.plugin = TestPluginA(mock_bot)
    info_a.state = PluginState.LOADED

    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = TestPluginB(mock_bot)
    info_b.state = PluginState.ENABLED

    manager._plugins = {"plugin_a": info_a, "plugin_b": info_b}

    plugins = manager.list_plugins()

    assert len(plugins) == 2
    assert info_a in plugins
    assert info_b in plugins


@pytest.mark.asyncio
async def test_get_enabled(mock_bot):
    """Test get enabled plugins."""
    manager = PluginManager(mock_bot)

    # Add plugins (one enabled, one disabled)
    info_a = PluginInfo(Path("a.py"))
    plugin_a = TestPluginA(mock_bot)
    info_a.plugin = plugin_a
    info_a.state = PluginState.ENABLED

    info_b = PluginInfo(Path("b.py"))
    plugin_b = TestPluginB(mock_bot)
    info_b.plugin = plugin_b
    info_b.state = PluginState.DISABLED

    manager._plugins = {"plugin_a": info_a, "plugin_b": info_b}

    enabled = manager.get_enabled()

    assert len(enabled) == 1
    assert plugin_a in enabled
    assert plugin_b not in enabled


@pytest.mark.asyncio
async def test_unload_all(mock_bot):
    """Test unload all plugins."""
    manager = PluginManager(mock_bot)

    # Add plugins
    info_a = PluginInfo(Path("a.py"))
    info_a.plugin = TestPluginA(mock_bot)
    info_a.state = PluginState.ENABLED
    info_a.plugin._is_enabled = True

    info_b = PluginInfo(Path("b.py"))
    info_b.plugin = TestPluginB(mock_bot)
    info_b.state = PluginState.SETUP

    manager._plugins = {"plugin_a": info_a, "plugin_b": info_b}
    manager._file_to_name = {Path("a.py"): "plugin_a", Path("b.py"): "plugin_b"}

    await manager.unload_all()

    assert manager._plugins == {}
    assert manager._file_to_name == {}


# =================================================================
# Integration Tests
# =================================================================


@pytest.mark.asyncio
async def test_full_lifecycle(mock_bot):
    """Test complete plugin lifecycle."""
    manager = PluginManager(mock_bot)

    # Manually add plugin (simulating load)
    info = PluginInfo(Path("a.py"))
    info.plugin = TestPluginA(mock_bot)
    info.state = PluginState.LOADED
    manager._plugins = {"plugin_a": info}

    # Setup
    await manager._setup_plugin("plugin_a")
    assert info.state == PluginState.SETUP

    # Enable
    await manager.enable("plugin_a")
    assert info.state == PluginState.ENABLED
    assert info.plugin.is_enabled is True

    # Disable
    await manager.disable("plugin_a")
    assert info.state == PluginState.DISABLED
    assert info.plugin.is_enabled is False

    # Enable again
    await manager.enable("plugin_a")
    assert info.state == PluginState.ENABLED

    # Teardown
    await manager._disable_plugin("plugin_a")
    await manager._teardown_plugin("plugin_a")
    assert info.state == PluginState.TORN_DOWN
