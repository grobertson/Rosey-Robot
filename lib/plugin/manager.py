"""
lib/plugin/manager.py

Plugin discovery, loading, and lifecycle management.
"""

import importlib.util
import logging
import sys
import traceback
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

from .base import Plugin
from .errors import (
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginSetupError,
)
from .event_bus import EventBus
from .metadata import PluginMetadata
from .service_registry import ServiceRegistry


class PluginState(Enum):
    """
    Plugin lifecycle states.

    States:
        UNLOADED: Initial state, plugin not loaded
        LOADED: Module imported, Plugin() instantiated
        SETUP: setup() complete, ready to enable
        ENABLED: Active, handling events
        DISABLED: Inactive, not handling events
        TORN_DOWN: Cleanup complete
        FAILED: Error occurred (from any state)
    """

    UNLOADED = "unloaded"
    LOADED = "loaded"
    SETUP = "setup"
    ENABLED = "enabled"
    DISABLED = "disabled"
    TORN_DOWN = "torn_down"
    FAILED = "failed"


class PluginInfo:
    """
    Plugin information and state tracking.

    Tracks plugin instance, current state, errors, and file path.

    Attributes:
        plugin: Plugin instance (None if not loaded)
        state: Current plugin state
        error: Error message if state == FAILED
        file_path: Path to plugin file

    Example:
        info = PluginInfo(Path('plugins/example.py'))
        info.plugin = ExamplePlugin(bot)
        info.state = PluginState.LOADED
    """

    def __init__(self, file_path: Path):
        """
        Initialize plugin info.

        Args:
            file_path: Path to plugin file
        """
        self.plugin: Optional[Plugin] = None
        self.state: PluginState = PluginState.UNLOADED
        self.error: Optional[str] = None
        self.file_path: Path = file_path

    @property
    def name(self) -> Optional[str]:
        """Plugin name (None if not loaded)."""
        return self.plugin.metadata.name if self.plugin else None

    @property
    def metadata(self) -> Optional[PluginMetadata]:
        """Plugin metadata (None if not loaded)."""
        return self.plugin.metadata if self.plugin else None

    def __str__(self) -> str:
        """String representation for logs."""
        if self.plugin:
            return f"{self.plugin.metadata.display_name} ({self.state.value})"
        return f"{self.file_path.stem} ({self.state.value})"

    def __repr__(self) -> str:
        """Developer representation."""
        if self.plugin and self.metadata:
            return f"<PluginInfo: {self.name} v{self.metadata.version} ({self.state.value})>"
        return f"<PluginInfo: {self.file_path.name} ({self.state.value})>"


class PluginManager:
    """
    Manage plugin discovery, loading, and lifecycle.

    Features:
        - Discover plugins from directory
        - Load plugins dynamically
        - Resolve dependencies (topological sort)
        - Manage lifecycle (setup, enable, disable, teardown)
        - Isolate errors (one plugin failure doesn't crash others)
        - Track plugin state

    Args:
        bot: Bot instance
        plugin_dir: Directory containing plugin files (default: plugins/)
        logger: Optional logger instance

    Example:
        manager = PluginManager(bot, 'plugins')
        await manager.load_all()

        # Get plugin
        my_plugin = manager.get('my_plugin')

        # Disable plugin
        await manager.disable('my_plugin')

        # Reload plugin
        await manager.reload('my_plugin')
    """

    def __init__(
        self,
        bot,
        plugin_dir: str = "plugins",
        hot_reload: bool = False,
        hot_reload_delay: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize plugin manager.

        Args:
            bot: Bot instance
            plugin_dir: Directory containing plugin files
            hot_reload: Enable automatic reload on file changes (default: False)
            hot_reload_delay: Debounce delay for hot reload in seconds (default: 0.5)
            logger: Optional logger instance
        """
        self.bot = bot
        self.plugin_dir = Path(plugin_dir)
        self.logger = logger or logging.getLogger("plugin.manager")

        # Event bus for inter-plugin communication
        self.event_bus = EventBus(logger=self.logger)

        # Service registry for dependency injection
        self.service_registry = ServiceRegistry(logger=self.logger)

        # Plugin registry: name -> PluginInfo
        self._plugins: Dict[str, PluginInfo] = {}

        # File tracking: path -> name (for hot reload)
        self._file_to_name: Dict[Path, str] = {}

        # Hot reload watcher (lazy initialization)
        self._hot_reload_enabled = hot_reload
        self._hot_reload_delay = hot_reload_delay
        self._hot_reload: Optional[object] = None  # HotReloadWatcher

    # =================================================================
    # Discovery
    # =================================================================

    def discover(self) -> List[Path]:
        """
        Discover plugin files in plugin directory.

        Scans plugin directory for .py files (excluding __init__.py).

        Returns:
            List of plugin file paths

        Raises:
            PluginError: If plugin directory doesn't exist

        Example:
            files = manager.discover()
            print(f"Found {len(files)} plugin files")
        """
        if not self.plugin_dir.exists():
            raise PluginError(f"Plugin directory not found: {self.plugin_dir}")

        # Find all .py files except __init__.py
        plugin_files = [
            f for f in self.plugin_dir.glob("*.py") if f.name != "__init__.py"
        ]

        self.logger.info(f"Discovered {len(plugin_files)} plugin files")
        return plugin_files

    # =================================================================
    # Loading
    # =================================================================

    async def load_all(self) -> None:  # noqa: C901 (plugin loading complexity)
        """
        Discover and load all plugins.

        This performs a complete plugin initialization:
            1. Discovers plugin files
            2. Loads each plugin module
            3. Resolves dependencies
            4. Sets up plugins in dependency order
            5. Enables all plugins

        Continues on errors - one plugin failure doesn't prevent
        loading others.

        Example:
            await manager.load_all()
            enabled = manager.get_enabled()
            print(f"Loaded {len(enabled)} plugins")
        """
        # Discover
        plugin_files = self.discover()

        # Load all modules first
        for file_path in plugin_files:
            try:
                await self._load_plugin_file(file_path)
            except Exception as e:
                self.logger.error(f"Failed to load {file_path}: {e}")
                # Continue loading other plugins

        # Resolve dependencies and get load order
        try:
            load_order = self._resolve_dependencies()
        except PluginDependencyError as e:
            self.logger.error(f"Dependency resolution failed: {e}")
            return

        # Setup plugins in dependency order
        for name in load_order:
            info = self._plugins[name]
            if info.state == PluginState.LOADED:
                try:
                    await self._setup_plugin(name)
                except Exception as e:
                    self.logger.error(f"Setup failed for {name}: {e}")

        # Enable all successfully setup plugins
        for name in load_order:
            info = self._plugins[name]
            if info.state == PluginState.SETUP:
                try:
                    await self._enable_plugin(name)
                except Exception as e:
                    self.logger.error(f"Enable failed for {name}: {e}")

        enabled_count = sum(
            1 for p in self._plugins.values() if p.state == PluginState.ENABLED
        )
        self.logger.info(f"Loaded {enabled_count}/{len(self._plugins)} plugins")

        # Start hot reload if enabled
        if self._hot_reload_enabled and not self._hot_reload:
            try:
                from .hot_reload import HotReloadWatcher

                self._hot_reload = HotReloadWatcher(
                    self,
                    enabled=True,
                    debounce_delay=self._hot_reload_delay,
                    logger=self.logger,
                )
            except ImportError:
                self.logger.warning(
                    "Hot reload requested but watchdog not installed. "
                    "Install with: pip install watchdog"
                )

    async def _load_plugin_file(self, file_path: Path) -> None:
        """
        Load plugin from file.

        Dynamically imports module, finds Plugin subclass,
        instantiates plugin, and registers it.

        Args:
            file_path: Path to plugin .py file

        Raises:
            PluginLoadError: If load fails
        """
        try:
            # Import module dynamically
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Failed to load spec for {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Find Plugin subclass in module
            plugin_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, Plugin)
                    and obj is not Plugin
                ):
                    plugin_class = obj
                    break

            if plugin_class is None:
                raise PluginLoadError(f"No Plugin subclass found in {file_path}")

            # Instantiate plugin
            plugin = plugin_class(self.bot)

            # Create plugin info
            info = PluginInfo(file_path)
            info.plugin = plugin
            info.state = PluginState.LOADED

            # Register
            self._plugins[plugin.metadata.name] = info
            self._file_to_name[file_path] = plugin.metadata.name

            self.logger.info(f"Loaded plugin: {plugin.metadata.display_name}")

        except Exception as e:
            # Create failed plugin info
            info = PluginInfo(file_path)
            info.state = PluginState.FAILED
            info.error = str(e)
            self._plugins[file_path.stem] = info

            self.logger.error(f"Failed to load {file_path}: {e}")
            self.logger.debug(traceback.format_exc())
            raise PluginLoadError(f"Failed to load {file_path}") from e

    # =================================================================
    # Dependency Resolution
    # =================================================================

    def _resolve_dependencies(self) -> List[str]:  # noqa: C901 (dependency resolution)
        """
        Resolve plugin dependencies using topological sort.

        Uses Kahn's algorithm to determine load order that
        respects dependencies (dependencies loaded first).

        Returns:
            List of plugin names in load order (dependencies first)

        Raises:
            PluginDependencyError: If circular dependency or missing dependency

        Example:
            # Plugin A depends on B, B depends on C
            order = manager._resolve_dependencies()
            # Returns: ['C', 'B', 'A']
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}

        for name, info in self._plugins.items():
            if info.state != PluginState.LOADED:
                continue

            assert info.metadata is not None  # guaranteed when LOADED
            graph[name] = set(info.metadata.dependencies)
            in_degree[name] = 0

        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    raise PluginDependencyError(
                        f"Plugin {name} depends on missing plugin: {dep}"
                    )
                in_degree[name] += 1

        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            name = queue.pop(0)
            result.append(name)

            # Reduce in-degree for dependents
            for other_name, deps in graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        if len(result) != len(graph):
            raise PluginDependencyError("Circular dependency detected")

        return result

    # =================================================================
    # Lifecycle Management
    # =================================================================

    async def _setup_plugin(self, name: str) -> None:
        """
        Run plugin setup.

        Calls plugin.setup() and transitions to SETUP state.

        Args:
            name: Plugin name

        Raises:
            PluginSetupError: If setup fails
        """
        info = self._plugins[name]
        assert info.plugin is not None  # guaranteed when in registry

        try:
            await info.plugin.setup()
            info.state = PluginState.SETUP
            self.logger.info(f"Setup complete: {name}")

        except Exception as e:
            info.state = PluginState.FAILED
            info.error = str(e)
            self.logger.error(f"Setup failed for {name}: {e}")
            self.logger.debug(traceback.format_exc())
            raise PluginSetupError(f"Setup failed for {name}") from e

    async def _enable_plugin(self, name: str) -> None:
        """
        Enable plugin.

        Calls plugin.on_enable() and transitions to ENABLED state.

        Args:
            name: Plugin name

        Raises:
            Exception: If enable fails
        """
        info = self._plugins[name]
        assert info.plugin is not None  # guaranteed when in registry

        try:
            await info.plugin.on_enable()
            info.state = PluginState.ENABLED
            self.logger.info(f"Enabled: {name}")

        except Exception as e:
            info.state = PluginState.FAILED
            info.error = str(e)
            self.logger.error(f"Enable failed for {name}: {e}")
            raise

    async def _disable_plugin(self, name: str) -> None:
        """
        Disable plugin.

        Calls plugin.on_disable() and transitions to DISABLED state.

        Args:
            name: Plugin name
        """
        info = self._plugins[name]
        assert info.plugin is not None  # guaranteed when in registry

        try:
            await info.plugin.on_disable()
            info.state = PluginState.DISABLED
            self.logger.info(f"Disabled: {name}")

        except Exception as e:
            self.logger.error(f"Disable failed for {name}: {e}")
            # Don't fail on disable errors

    async def _teardown_plugin(self, name: str) -> None:
        """
        Run plugin teardown.

        Calls plugin.teardown() and transitions to TORN_DOWN state.

        Args:
            name: Plugin name
        """
        info = self._plugins[name]
        assert info.plugin is not None  # guaranteed when in registry

        try:
            await info.plugin.teardown()
            info.state = PluginState.TORN_DOWN
            self.logger.info(f"Teardown complete: {name}")

        except Exception as e:
            self.logger.error(f"Teardown failed for {name}: {e}")
            # Don't fail on teardown errors (best effort)

    # =================================================================
    # Public API
    # =================================================================

    async def enable(self, name: str) -> None:
        """
        Enable plugin by name.

        Transitions plugin from DISABLED or SETUP to ENABLED.

        Args:
            name: Plugin name

        Raises:
            PluginError: If plugin not found or not in correct state

        Example:
            await manager.enable('my_plugin')
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")

        info = self._plugins[name]

        if info.state == PluginState.ENABLED:
            self.logger.warning(f"Plugin already enabled: {name}")
            return

        if info.state not in (PluginState.DISABLED, PluginState.SETUP):
            raise PluginError(f"Cannot enable plugin in state: {info.state.value}")

        await self._enable_plugin(name)

    async def disable(self, name: str) -> None:
        """
        Disable plugin by name.

        Transitions plugin from ENABLED to DISABLED.
        Plugin remains loaded but inactive.

        Args:
            name: Plugin name

        Raises:
            PluginError: If plugin not found

        Example:
            await manager.disable('my_plugin')
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")

        info = self._plugins[name]

        if info.state != PluginState.ENABLED:
            self.logger.warning(f"Plugin not enabled: {name}")
            return

        await self._disable_plugin(name)

    async def reload(self, name: str) -> None:
        """
        Reload plugin (disable, teardown, reload module, setup, enable).

        Complete plugin reload cycle:
            1. Disable if enabled
            2. Teardown if setup
            3. Remove from registry
            4. Reload module from file
            5. Setup
            6. Enable

        Args:
            name: Plugin name

        Raises:
            PluginError: If reload fails

        Example:
            await manager.reload('my_plugin')
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")

        info = self._plugins[name]
        file_path = info.file_path

        # Disable if enabled
        if info.state == PluginState.ENABLED:
            await self._disable_plugin(name)

        # Teardown if setup
        if info.state in (PluginState.DISABLED, PluginState.SETUP):
            await self._teardown_plugin(name)

        # Remove from registry
        del self._plugins[name]
        if file_path in self._file_to_name:
            del self._file_to_name[file_path]

        # Reload module
        await self._load_plugin_file(file_path)

        # Setup and enable
        await self._setup_plugin(name)
        await self._enable_plugin(name)

        self.logger.info(f"Reloaded plugin: {name}")

    def get(self, name: str) -> Optional[Plugin]:
        """
        Get plugin instance by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found

        Example:
            plugin = manager.get('my_plugin')
            if plugin:
                print(f"Found: {plugin.metadata.display_name}")
        """
        info = self._plugins.get(name)
        return info.plugin if info else None

    def list_plugins(self) -> List[PluginInfo]:
        """
        Get list of all plugins.

        Returns:
            List of PluginInfo objects

        Example:
            for info in manager.list_plugins():
                print(f"{info.name}: {info.state.value}")
        """
        return list(self._plugins.values())

    def get_enabled(self) -> List[Plugin]:
        """
        Get list of enabled plugins.

        Returns:
            List of enabled Plugin instances

        Example:
            enabled = manager.get_enabled()
            print(f"{len(enabled)} plugins active")
        """
        return [
            info.plugin
            for info in self._plugins.values()
            if info.state == PluginState.ENABLED and info.plugin is not None
        ]

    async def unload_all(self) -> None:
        """
        Unload all plugins (disable, teardown, remove from registry).

        Performs graceful shutdown of all plugins:
            1. Stop hot reload watcher
            2. Disable all enabled plugins
            3. Teardown all setup plugins
            4. Clear registry

        Example:
            await manager.unload_all()
        """
        # Stop hot reload first
        if self._hot_reload:
            self._hot_reload.stop()  # type: ignore[attr-defined]
            self._hot_reload = None

        for name in list(self._plugins.keys()):
            info = self._plugins[name]

            if info.state == PluginState.ENABLED:
                await self._disable_plugin(name)

            if info.state in (PluginState.DISABLED, PluginState.SETUP):
                await self._teardown_plugin(name)

        self._plugins.clear()
        self._file_to_name.clear()

        self.logger.info("All plugins unloaded")
