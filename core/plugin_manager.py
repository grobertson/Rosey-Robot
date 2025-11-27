"""
Plugin Manager System

This module provides centralized management for all plugins, orchestrating
their lifecycle, permissions, resources, and inter-plugin communication.

Key Components:
- PluginMetadata: Plugin information and configuration
- PluginRegistry: Tracks all registered plugins
- PluginManager: Central orchestrator for plugin system

Architecture:
    PluginManager
        │
        ├── PluginRegistry (plugin tracking)
        │   ├── PluginMetadata (metadata)
        │   ├── PluginProcess (subprocess)
        │   ├── PluginPermissions (security)
        │   └── ResourceMonitor (resources)
        │
        ├── EventBus (communication)
        │
        └── Operations
            ├── load_plugin()
            ├── unload_plugin()
            ├── start_plugin()
            ├── stop_plugin()
            ├── restart_plugin()
            └── list_plugins()

Plugin Lifecycle:
    UNLOADED → load() → LOADED → start() → RUNNING
    RUNNING → stop() → STOPPED → unload() → UNLOADED
    RUNNING → crash → CRASHED → restart() → RUNNING
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set, List, Any, Callable
import time

from .event_bus import EventBus, Event, Priority
from .subjects import build_plugin_subject, EventTypes
from .plugin_isolation import (
    PluginProcess,
    PluginIPC,
    PluginState,
    RestartConfig,
    ResourceLimits
)
from .plugin_permissions import (
    PluginPermissions,
    PermissionProfile,
    Permission
)

logger = logging.getLogger(__name__)


# ============================================================================
# Plugin Metadata
# ============================================================================

@dataclass
class PluginMetadata:
    """
    Metadata describing a plugin.

    Contains all information needed to load, configure, and manage a plugin.
    """

    # Identity
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    # Location
    module_path: str = ""  # Python module path or file path
    config_path: Optional[Path] = None

    # Dependencies
    dependencies: List[str] = field(default_factory=list)  # Other plugins required
    python_requires: str = ">=3.10"

    # Permissions
    permission_profile: PermissionProfile = PermissionProfile.STANDARD
    custom_permissions: Set[Permission] = field(default_factory=set)

    # Resources
    resource_limits: Optional[ResourceLimits] = None
    restart_config: Optional[RestartConfig] = None

    # Behavior
    auto_start: bool = True
    enabled: bool = True
    priority: int = 0  # Higher = starts first

    # Runtime (populated during operation)
    load_time: Optional[float] = field(default=None, init=False)
    start_time: Optional[float] = field(default=None, init=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "module_path": self.module_path,
            "config_path": str(self.config_path) if self.config_path else None,
            "dependencies": self.dependencies,
            "python_requires": self.python_requires,
            "permission_profile": self.permission_profile.value,
            "auto_start": self.auto_start,
            "enabled": self.enabled,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginMetadata":
        """Deserialize from dictionary"""
        config_path = data.get("config_path")
        if config_path:
            config_path = Path(config_path)

        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            module_path=data.get("module_path", ""),
            config_path=config_path,
            dependencies=data.get("dependencies", []),
            python_requires=data.get("python_requires", ">=3.10"),
            permission_profile=PermissionProfile(
                data.get("permission_profile", "standard")
            ),
            auto_start=data.get("auto_start", True),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
        )


# ============================================================================
# Plugin Registry Entry
# ============================================================================

@dataclass
class PluginEntry:
    """
    Registry entry for a loaded plugin.

    Combines metadata with runtime components.
    """

    metadata: PluginMetadata
    process: Optional[PluginProcess] = None
    permissions: Optional[PluginPermissions] = None
    ipc: Optional[PluginIPC] = None

    def get_state(self) -> PluginState:
        """Get current plugin state"""
        if self.process is None:
            return PluginState.STOPPED
        return self.process.state

    def is_running(self) -> bool:
        """Check if plugin is running"""
        return self.process is not None and self.process.is_alive()

    def get_uptime(self) -> Optional[float]:
        """Get plugin uptime"""
        if self.process is None:
            return None
        return self.process.get_uptime()


# ============================================================================
# Plugin Registry
# ============================================================================

class PluginRegistry:
    """
    Registry tracking all plugins in the system.

    Provides fast lookups and state queries.
    """

    def __init__(self):
        """Initialize registry"""
        self._plugins: Dict[str, PluginEntry] = {}
        self._dependency_graph: Dict[str, Set[str]] = {}

    def register(self, entry: PluginEntry) -> None:
        """
        Register a plugin.

        Args:
            entry: PluginEntry to register
        """
        name = entry.metadata.name
        self._plugins[name] = entry
        self._dependency_graph[name] = set(entry.metadata.dependencies)
        logger.info(f"Registered plugin: {name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a plugin.

        Args:
            name: Plugin name

        Returns:
            True if plugin was unregistered
        """
        if name in self._plugins:
            del self._plugins[name]
            if name in self._dependency_graph:
                del self._dependency_graph[name]
            logger.info(f"Unregistered plugin: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[PluginEntry]:
        """Get plugin entry by name"""
        return self._plugins.get(name)

    def has(self, name: str) -> bool:
        """Check if plugin is registered"""
        return name in self._plugins

    def list_all(self) -> List[str]:
        """Get list of all plugin names"""
        return list(self._plugins.keys())

    def list_running(self) -> List[str]:
        """Get list of running plugin names"""
        return [
            name for name, entry in self._plugins.items()
            if entry.is_running()
        ]

    def list_by_state(self, state: PluginState) -> List[str]:
        """Get list of plugins in specific state"""
        return [
            name for name, entry in self._plugins.items()
            if entry.get_state() == state
        ]

    def get_dependencies(self, name: str) -> Set[str]:
        """Get plugin dependencies"""
        return self._dependency_graph.get(name, set())

    def get_dependents(self, name: str) -> Set[str]:
        """Get plugins that depend on this plugin"""
        dependents = set()
        for plugin, deps in self._dependency_graph.items():
            if name in deps:
                dependents.add(plugin)
        return dependents

    def check_dependencies(self, name: str) -> bool:
        """
        Check if all dependencies are running.

        Args:
            name: Plugin name

        Returns:
            True if all dependencies are running
        """
        deps = self.get_dependencies(name)
        for dep in deps:
            entry = self.get(dep)
            if entry is None or not entry.is_running():
                return False
        return True

    def get_load_order(self) -> List[str]:
        """
        Get plugin load order based on dependencies and priority.

        Returns:
            List of plugin names in load order
        """
        # Topological sort with priority
        visited = set()
        result = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)

            # Visit dependencies first
            for dep in self._dependency_graph.get(name, set()):
                if dep in self._plugins:
                    visit(dep)

            result.append(name)

        # Get plugins sorted by priority (highest first)
        plugins_by_priority = sorted(
            self._plugins.items(),
            key=lambda x: x[1].metadata.priority,
            reverse=True
        )

        for name, _ in plugins_by_priority:
            visit(name)

        return result


# ============================================================================
# Plugin Manager
# ============================================================================

class PluginManager:
    """
    Central manager for the plugin system.

    Orchestrates plugin lifecycle, permissions, resources, and communication.
    """

    def __init__(self, event_bus: EventBus):
        """
        Initialize plugin manager.

        Args:
            event_bus: EventBus instance for plugin communication
        """
        self.event_bus = event_bus
        self.registry = PluginRegistry()
        self._callbacks: Dict[str, List[Callable]] = {
            "plugin_loaded": [],
            "plugin_unloaded": [],
            "plugin_started": [],
            "plugin_stopped": [],
            "plugin_crashed": [],
        }

    # ========================================================================
    # Plugin Loading
    # ========================================================================

    async def load_plugin(self, metadata: PluginMetadata) -> bool:
        """
        Load a plugin into the registry.

        Args:
            metadata: Plugin metadata

        Returns:
            True if loaded successfully
        """
        name = metadata.name

        # Check if already loaded
        if self.registry.has(name):
            logger.warning(f"Plugin {name} already loaded")
            return False

        # Validate metadata
        if not metadata.module_path:
            logger.error(f"Plugin {name} has no module_path")
            return False

        try:
            # Create permissions
            permissions = PluginPermissions(
                plugin_name=name,
                profile=metadata.permission_profile
            )

            if metadata.custom_permissions:
                permissions.grant(*metadata.custom_permissions)

            # Create registry entry
            entry = PluginEntry(
                metadata=metadata,
                permissions=permissions
            )

            # Register
            self.registry.register(entry)
            metadata.load_time = time.time()

            logger.info(f"Loaded plugin: {name} v{metadata.version}")
            self._notify_callbacks("plugin_loaded", name)

            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return False

    async def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin from the registry.

        Args:
            name: Plugin name

        Returns:
            True if unloaded successfully
        """
        entry = self.registry.get(name)
        if entry is None:
            logger.warning(f"Plugin {name} not found")
            return False

        # Stop if running
        if entry.is_running():
            await self.stop_plugin(name)

        # Check for dependents
        dependents = self.registry.get_dependents(name)
        if dependents:
            logger.warning(
                f"Plugin {name} has dependents: {dependents}. "
                f"Stop them first."
            )
            return False

        # Unregister
        self.registry.unregister(name)
        logger.info(f"Unloaded plugin: {name}")
        self._notify_callbacks("plugin_unloaded", name)

        return True

    # ========================================================================
    # Plugin Execution
    # ========================================================================

    async def start_plugin(self, name: str) -> bool:
        """
        Start a loaded plugin.

        Args:
            name: Plugin name

        Returns:
            True if started successfully
        """
        entry = self.registry.get(name)
        if entry is None:
            logger.error(f"Plugin {name} not loaded")
            return False

        # Check if already running
        if entry.is_running():
            logger.warning(f"Plugin {name} already running")
            return False

        # Check dependencies
        if not self.registry.check_dependencies(name):
            missing = [
                dep for dep in entry.metadata.dependencies
                if not self.registry.get(dep) or 
                not self.registry.get(dep).is_running()
            ]
            logger.error(
                f"Plugin {name} dependencies not met: {missing}"
            )
            return False

        try:
            # Create process
            process = PluginProcess(
                plugin_name=name,
                module_path=entry.metadata.module_path,
                event_bus=self.event_bus,
                restart_config=entry.metadata.restart_config,
                resource_limits=entry.metadata.resource_limits
            )

            # Create IPC
            ipc = PluginIPC(name, self.event_bus)

            # Update entry
            entry.process = process
            entry.ipc = ipc

            # Start process
            success = await process.start()

            if success:
                entry.metadata.start_time = time.time()
                logger.info(f"Started plugin: {name}")
                self._notify_callbacks("plugin_started", name)

                # Publish event
                await self.event_bus.publish(Event(
                    subject=build_plugin_subject(name, EventTypes.PLUGIN_START),
                    event_type=EventTypes.PLUGIN_START,
                    source="plugin_manager",
                    data={
                        "plugin": name,
                        "version": entry.metadata.version,
                        "timestamp": time.time()
                    },
                    priority=Priority.HIGH
                ))

            return success

        except Exception as e:
            logger.error(f"Failed to start plugin {name}: {e}")
            return False

    async def stop_plugin(self, name: str, timeout: float = 10.0) -> bool:
        """
        Stop a running plugin.

        Args:
            name: Plugin name
            timeout: Shutdown timeout in seconds

        Returns:
            True if stopped successfully
        """
        entry = self.registry.get(name)
        if entry is None or entry.process is None:
            logger.warning(f"Plugin {name} not running")
            return False

        # Check for dependents
        dependents = self.registry.get_dependents(name)
        running_dependents = [
            d for d in dependents
            if self.registry.get(d) and self.registry.get(d).is_running()
        ]

        if running_dependents:
            logger.warning(
                f"Plugin {name} has running dependents: {running_dependents}. "
                f"Stop them first."
            )
            return False

        try:
            # Stop process
            success = await entry.process.stop(timeout=timeout)

            if success:
                logger.info(f"Stopped plugin: {name}")
                self._notify_callbacks("plugin_stopped", name)

                # Publish event
                await self.event_bus.publish(Event(
                    subject=build_plugin_subject(name, EventTypes.PLUGIN_STOP),
                    event_type=EventTypes.PLUGIN_STOP,
                    source="plugin_manager",
                    data={
                        "plugin": name,
                        "timestamp": time.time()
                    },
                    priority=Priority.HIGH
                ))

            return success

        except Exception as e:
            logger.error(f"Failed to stop plugin {name}: {e}")
            return False

    async def restart_plugin(self, name: str) -> bool:
        """
        Restart a plugin.

        Args:
            name: Plugin name

        Returns:
            True if restarted successfully
        """
        entry = self.registry.get(name)
        if entry is None or entry.process is None:
            logger.error(f"Plugin {name} not found or not started")
            return False

        logger.info(f"Restarting plugin: {name}")
        return await entry.process.restart()

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def start_all(self, respect_dependencies: bool = True) -> Dict[str, bool]:
        """
        Start all loaded plugins.

        Args:
            respect_dependencies: Start in dependency order

        Returns:
            Dict mapping plugin names to success status
        """
        results = {}

        if respect_dependencies:
            load_order = self.registry.get_load_order()
        else:
            load_order = self.registry.list_all()

        for name in load_order:
            entry = self.registry.get(name)
            if entry and entry.metadata.enabled and not entry.is_running():
                results[name] = await self.start_plugin(name)

        return results

    async def stop_all(self, timeout: float = 10.0) -> Dict[str, bool]:
        """
        Stop all running plugins.

        Args:
            timeout: Shutdown timeout per plugin

        Returns:
            Dict mapping plugin names to success status
        """
        results = {}

        # Stop in reverse load order
        load_order = self.registry.get_load_order()
        for name in reversed(load_order):
            entry = self.registry.get(name)
            if entry and entry.is_running():
                results[name] = await self.stop_plugin(name, timeout)

        return results

    async def restart_all(self) -> Dict[str, bool]:
        """
        Restart all running plugins.

        Returns:
            Dict mapping plugin names to success status
        """
        results = {}

        for name in self.registry.list_running():
            results[name] = await self.restart_plugin(name)

        return results

    # ========================================================================
    # Query Operations
    # ========================================================================

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed plugin information.

        Args:
            name: Plugin name

        Returns:
            Dict with plugin info, or None if not found
        """
        entry = self.registry.get(name)
        if entry is None:
            return None

        info = entry.metadata.to_dict()
        info.update({
            "state": entry.get_state().value,
            "running": entry.is_running(),
            "uptime": entry.get_uptime(),
        })

        if entry.permissions:
            info["permissions"] = {
                "profile": entry.permissions.profile.value,
                "granted": entry.permissions.get_granted_names(),
                "denied_count": entry.permissions.get_denied_count()
            }

        if entry.process and entry.process.monitor:
            asyncio.create_task(
                entry.process.monitor.get_current_usage()
            )
            # Would need to await this properly in async context

        return info

    def list_plugins(
        self,
        state: Optional[PluginState] = None,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List plugins with optional filtering.

        Args:
            state: Filter by state
            enabled_only: Only include enabled plugins

        Returns:
            List of plugin info dicts
        """
        plugins = []

        for name in self.registry.list_all():
            entry = self.registry.get(name)
            if entry is None:
                continue

            # Apply filters
            if state and entry.get_state() != state:
                continue

            if enabled_only and not entry.metadata.enabled:
                continue

            info = self.get_plugin_info(name)
            if info:
                plugins.append(info)

        return plugins

    def get_statistics(self) -> Dict[str, Any]:
        """Get plugin system statistics"""
        return {
            "total_plugins": len(self.registry.list_all()),
            "running": len(self.registry.list_running()),
            "stopped": len(self.registry.list_by_state(PluginState.STOPPED)),
            "crashed": len(self.registry.list_by_state(PluginState.CRASHED)),
            "failed": len(self.registry.list_by_state(PluginState.FAILED)),
        }

    def get_plugin_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            dict: Status information or None if not running
        """
        entry = self.registry.get(name)
        if entry is None or entry.process is None:
            return None
        
        process = entry.process
        
        status = {
            "name": name,
            "state": process.state.value,
            "pid": process.pid,
            "uptime": time.time() - process.start_time if process.start_time else 0,
            "restart_attempts": len(process.restart_attempts),
        }
        
        # Add resource stats if available
        if process.resource_stats:
            status["resources"] = {
                "cpu_percent": process.resource_stats.current_cpu_percent,
                "memory_mb": process.resource_stats.current_memory_mb,
                "peak_cpu_percent": process.resource_stats.peak_cpu_percent,
                "peak_memory_mb": process.resource_stats.peak_memory_mb,
            }
        
        return status

    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all running plugins.
        
        Returns:
            dict: Plugin name → status dict
        """
        return {
            name: self.get_plugin_status(name)
            for name in self.registry.list_running()
            if self.get_plugin_status(name) is not None
        }

    # ========================================================================
    # Callbacks
    # ========================================================================

    def add_callback(self, event: str, callback: Callable) -> None:
        """
        Add event callback.

        Args:
            event: Event name (plugin_loaded, plugin_started, etc.)
            callback: Callback function
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify_callbacks(self, event: str, plugin_name: str) -> None:
        """Notify callbacks for an event"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(plugin_name)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
