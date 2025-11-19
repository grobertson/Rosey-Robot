# Sortie 7: Plugin Manager

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐⭐☆ (Orchestration & State Management)  
**Estimated Time:** 3-4 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 6a (Process Isolation), Sortie 6b (Permission System)

---

## Objective

Implement the Plugin Manager - the orchestrator that manages multiple plugins, handles lifecycle (start/stop/restart), monitors health, enforces resource limits, coordinates startup order, and provides management API for runtime control.

---

## What Plugin Manager Does

### Core Responsibilities

1. **Discovery** - Find available plugins (from directory, config, registry)
2. **Loading** - Load plugin manifests and validate permissions
3. **Lifecycle** - Start, stop, restart plugins with proper ordering
4. **Monitoring** - Watch plugin health, resource usage, crashes
5. **Enforcement** - Apply resource limits, restart on violations
6. **Recovery** - Auto-restart crashed plugins (with backoff)
7. **Coordination** - Handle dependencies between plugins
8. **Management API** - Enable/disable plugins at runtime

### The Challenge

Multiple plugins with different requirements:
- Some need to start before others (dependencies)
- Some crash and need recovery
- Some exceed limits and need throttling
- Some are optional, some are critical
- Some interact with each other
- All need coordinated shutdown

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Plugin Manager                             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Registry   │  │  Lifecycle   │  │  Monitor     │          │
│  │              │  │              │  │              │          │
│  │ - Discover   │  │ - Start      │  │ - Health     │          │
│  │ - Load       │  │ - Stop       │  │ - Resources  │          │
│  │ - Validate   │  │ - Restart    │  │ - Crashes    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │           Plugin State Tracking                   │           │
│  │                                                   │           │
│  │  plugin_name -> {                                │           │
│  │    process: PluginProcess,                       │           │
│  │    manifest: PluginManifest,                     │           │
│  │    state: running|stopped|crashed|starting,      │           │
│  │    start_time: timestamp,                        │           │
│  │    crash_count: int,                             │           │
│  │    last_health_check: timestamp,                 │           │
│  │  }                                                │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
        ┌───────▼───────┐              ┌───────▼───────┐
        │  Plugin A     │              │  Plugin B     │
        │  (running)    │              │  (crashed)    │
        └───────────────┘              └───────────────┘
```

---

## Design Decisions

### 1. Plugin States

```python
class PluginState(Enum):
    STOPPED = "stopped"       # Not running
    STARTING = "starting"     # In process of starting
    RUNNING = "running"       # Running normally
    UNHEALTHY = "unhealthy"   # Running but failing health checks
    CRASHED = "crashed"       # Process died unexpectedly
    STOPPING = "stopping"     # In process of stopping
    DISABLED = "disabled"     # Intentionally disabled, won't auto-start
```

### 2. Restart Policies

```python
class RestartPolicy(Enum):
    ALWAYS = "always"         # Always restart on crash
    ON_FAILURE = "on-failure" # Restart only on error exit
    NEVER = "never"           # Never auto-restart
```

### 3. Health Checks

**How we determine if plugin is healthy:**
- Process is running (basic)
- Responding to NATS health ping (advanced)
- Within resource limits
- No excessive error rate
- Recent successful command execution

### 4. Startup Dependencies

**Problem:** Plugin B needs Plugin A's events
- Calendar plugin needs Markov plugin for text generation
- Expense plugin needs Calendar plugin for scheduling

**Solution:** Dependency declaration in manifest:
```python
dependencies=["markov", "calendar"]
```

Plugin Manager ensures dependencies start first.

---

## Implementation

### Task 7.1: Plugin State Tracking

**File:** `bot/rosey/plugins/plugin_manager.py`

```python
"""
Plugin Manager - Orchestrates multiple plugins
"""
import asyncio
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from bot.rosey.plugins.plugin_runner import PluginProcess
from bot.rosey.plugins.plugin_manifest import PluginManifest
from bot.rosey.plugins.plugin_registry import PluginRegistry
from bot.rosey.core.event_bus import EventBus, get_event_bus
from bot.rosey.core.subjects import Subjects

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Plugin execution states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    CRASHED = "crashed"
    STOPPING = "stopping"
    DISABLED = "disabled"


class RestartPolicy(Enum):
    """Plugin restart policies"""
    ALWAYS = "always"           # Always restart
    ON_FAILURE = "on-failure"   # Restart on non-zero exit
    NEVER = "never"             # Never auto-restart


@dataclass
class PluginInfo:
    """
    Plugin runtime information
    
    Tracks everything we need to know about a plugin at runtime
    """
    name: str
    manifest: PluginManifest
    plugin_path: Path
    
    # Runtime state
    process: Optional[PluginProcess] = None
    state: PluginState = PluginState.STOPPED
    
    # Lifecycle tracking
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    crash_count: int = 0
    restart_count: int = 0
    last_health_check: Optional[datetime] = None
    
    # Configuration
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE
    enabled: bool = True
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)  # Who depends on this
    
    # Health metrics
    last_command_time: Optional[datetime] = None
    command_success_count: int = 0
    command_error_count: int = 0
    
    def is_running(self) -> bool:
        """Check if plugin is currently running"""
        return self.state in [PluginState.RUNNING, PluginState.UNHEALTHY]
    
    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds"""
        if not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()
    
    def error_rate(self) -> float:
        """Calculate error rate (errors / total commands)"""
        total = self.command_success_count + self.command_error_count
        if total == 0:
            return 0.0
        return self.command_error_count / total


class PluginManager:
    """
    Plugin Manager - Orchestrates plugin lifecycle
    
    Responsibilities:
    - Discover and load plugins
    - Start/stop plugins with dependency ordering
    - Monitor health and resources
    - Auto-restart on crashes
    - Enforce resource limits
    - Provide management API
    
    Example:
        manager = PluginManager(plugins_dir="bot/rosey/plugins")
        await manager.initialize()
        
        # Start all plugins
        await manager.start_all()
        
        # Monitor
        while True:
            await manager.health_check_all()
            await asyncio.sleep(30)
        
        # Shutdown
        await manager.stop_all()
    """
    
    def __init__(
        self,
        plugins_dir: str = None,
        event_bus: EventBus = None,
        health_check_interval: int = 30,
        max_crash_count: int = 3
    ):
        """
        Initialize plugin manager
        
        Args:
            plugins_dir: Directory containing plugins
            event_bus: EventBus instance
            health_check_interval: Seconds between health checks
            max_crash_count: Max crashes before disabling plugin
        """
        self.plugins_dir = Path(plugins_dir or "bot/rosey/plugins")
        self.event_bus = event_bus
        self.health_check_interval = health_check_interval
        self.max_crash_count = max_crash_count
        
        # Plugin tracking
        self.plugins: Dict[str, PluginInfo] = {}
        
        # Registry for discovery
        self.registry = PluginRegistry(str(self.plugins_dir))
        
        # Monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self):
        """
        Initialize plugin manager
        
        - Discovers plugins
        - Loads manifests
        - Validates dependencies
        - Sets up monitoring
        """
        logger.info("Initializing Plugin Manager...")
        
        # Get event bus if not provided
        if not self.event_bus:
            self.event_bus = await get_event_bus()
        
        # Discover plugins
        self.registry.discover()
        
        # Load plugin info
        for plugin_name in self.registry.list_plugins():
            await self._load_plugin(plugin_name)
        
        # Validate dependencies
        self._validate_dependencies()
        
        # Subscribe to plugin events for monitoring
        await self._subscribe_to_plugin_events()
        
        logger.info(f"Plugin Manager initialized with {len(self.plugins)} plugins")
        
        # Start monitoring
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
    
    async def _load_plugin(self, plugin_name: str):
        """
        Load plugin information
        
        Args:
            plugin_name: Plugin identifier
        """
        plugin_data = self.registry.get_plugin(plugin_name)
        if not plugin_data:
            logger.error(f"Plugin '{plugin_name}' not found in registry")
            return
        
        plugin_path = Path(plugin_data["file"])
        
        # Try to load manifest
        # In real implementation, would instantiate plugin temporarily
        # or read from manifest.yaml file
        try:
            # For now, create minimal manifest
            # TODO: Load from plugin or manifest file
            manifest = PluginManifest(
                name=plugin_name,
                version="1.0.0",
                description=f"Plugin: {plugin_name}"
            )
            
            plugin_info = PluginInfo(
                name=plugin_name,
                manifest=manifest,
                plugin_path=plugin_path
            )
            
            self.plugins[plugin_name] = plugin_info
            logger.info(f"Loaded plugin: {plugin_name}")
        
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
    
    def _validate_dependencies(self):
        """
        Validate plugin dependencies exist and build dependency graph
        """
        for plugin_name, plugin_info in self.plugins.items():
            for dep in plugin_info.dependencies:
                if dep not in self.plugins:
                    logger.error(
                        f"Plugin '{plugin_name}' depends on '{dep}' which doesn't exist"
                    )
                    plugin_info.enabled = False
                else:
                    # Track reverse dependency
                    self.plugins[dep].dependents.append(plugin_name)
        
        # Check for circular dependencies
        for plugin_name in self.plugins:
            if self._has_circular_dependency(plugin_name, set()):
                logger.error(f"Circular dependency detected involving '{plugin_name}'")
                self.plugins[plugin_name].enabled = False
    
    def _has_circular_dependency(
        self, 
        plugin_name: str, 
        visited: Set[str]
    ) -> bool:
        """Detect circular dependencies using DFS"""
        if plugin_name in visited:
            return True
        
        visited.add(plugin_name)
        
        plugin_info = self.plugins.get(plugin_name)
        if not plugin_info:
            return False
        
        for dep in plugin_info.dependencies:
            if self._has_circular_dependency(dep, visited.copy()):
                return True
        
        return False
    
    def _get_startup_order(self) -> List[str]:
        """
        Calculate plugin startup order based on dependencies
        
        Uses topological sort to ensure dependencies start first
        
        Returns:
            List of plugin names in startup order
        """
        # Build dependency graph
        graph = {name: set(info.dependencies) for name, info in self.plugins.items()}
        
        # Topological sort (Kahn's algorithm)
        result = []
        in_degree = {name: len(deps) for name, deps in graph.items()}
        
        # Start with plugins that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            # Reduce in-degree for dependents
            for dependent in self.plugins[node].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # If not all plugins processed, there's a cycle (shouldn't happen after validation)
        if len(result) != len(self.plugins):
            logger.error("Dependency cycle detected during startup order calculation")
            # Return all plugins anyway
            return list(self.plugins.keys())
        
        return result
    
    # ========== Lifecycle Management ==========
    
    async def start_plugin(self, plugin_name: str, force: bool = False):
        """
        Start single plugin
        
        Args:
            plugin_name: Plugin to start
            force: Start even if disabled
        
        Raises:
            ValueError: If plugin doesn't exist
            RuntimeError: If dependencies not met
        """
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin '{plugin_name}' not found")
        
        plugin_info = self.plugins[plugin_name]
        
        # Check if already running
        if plugin_info.is_running():
            logger.warning(f"Plugin '{plugin_name}' already running")
            return
        
        # Check if enabled
        if not plugin_info.enabled and not force:
            logger.warning(f"Plugin '{plugin_name}' is disabled")
            return
        
        # Check dependencies
        for dep in plugin_info.dependencies:
            if not self.plugins[dep].is_running():
                raise RuntimeError(
                    f"Cannot start '{plugin_name}': dependency '{dep}' not running"
                )
        
        logger.info(f"Starting plugin: {plugin_name}")
        plugin_info.state = PluginState.STARTING
        
        try:
            # Create process
            plugin_info.process = PluginProcess(
                plugin_name=plugin_name,
                plugin_path=str(plugin_info.plugin_path),
                manifest=plugin_info.manifest,
                nats_url=self.event_bus.servers[0] if self.event_bus else None
            )
            
            # Start
            await plugin_info.process.start()
            
            # Update state
            plugin_info.state = PluginState.RUNNING
            plugin_info.start_time = datetime.now()
            plugin_info.crash_count = 0  # Reset on successful start
            
            logger.info(f"Plugin '{plugin_name}' started successfully")
        
        except Exception as e:
            logger.error(f"Failed to start plugin '{plugin_name}': {e}")
            plugin_info.state = PluginState.CRASHED
            raise
    
    async def stop_plugin(self, plugin_name: str, stop_dependents: bool = True):
        """
        Stop single plugin
        
        Args:
            plugin_name: Plugin to stop
            stop_dependents: Also stop plugins that depend on this one
        """
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin '{plugin_name}' not found")
            return
        
        plugin_info = self.plugins[plugin_name]
        
        if not plugin_info.is_running():
            logger.warning(f"Plugin '{plugin_name}' not running")
            return
        
        # Stop dependents first if requested
        if stop_dependents:
            for dependent in plugin_info.dependents:
                if self.plugins[dependent].is_running():
                    logger.info(f"Stopping dependent plugin: {dependent}")
                    await self.stop_plugin(dependent, stop_dependents=True)
        
        logger.info(f"Stopping plugin: {plugin_name}")
        plugin_info.state = PluginState.STOPPING
        
        try:
            if plugin_info.process:
                await plugin_info.process.stop()
            
            plugin_info.state = PluginState.STOPPED
            plugin_info.stop_time = datetime.now()
            plugin_info.process = None
            
            logger.info(f"Plugin '{plugin_name}' stopped")
        
        except Exception as e:
            logger.error(f"Error stopping plugin '{plugin_name}': {e}")
    
    async def restart_plugin(self, plugin_name: str):
        """
        Restart plugin
        
        Args:
            plugin_name: Plugin to restart
        """
        logger.info(f"Restarting plugin: {plugin_name}")
        
        plugin_info = self.plugins[plugin_name]
        plugin_info.restart_count += 1
        
        await self.stop_plugin(plugin_name, stop_dependents=False)
        await asyncio.sleep(1)  # Brief pause
        await self.start_plugin(plugin_name)
    
    async def start_all(self, enabled_only: bool = True):
        """
        Start all plugins in dependency order
        
        Args:
            enabled_only: Only start enabled plugins
        """
        logger.info("Starting all plugins...")
        
        startup_order = self._get_startup_order()
        
        for plugin_name in startup_order:
            plugin_info = self.plugins[plugin_name]
            
            if enabled_only and not plugin_info.enabled:
                logger.debug(f"Skipping disabled plugin: {plugin_name}")
                continue
            
            try:
                await self.start_plugin(plugin_name)
                # Brief delay between starts
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to start plugin '{plugin_name}': {e}")
        
        logger.info("All plugins started")
    
    async def stop_all(self):
        """Stop all plugins in reverse dependency order"""
        logger.info("Stopping all plugins...")
        
        # Reverse startup order
        shutdown_order = list(reversed(self._get_startup_order()))
        
        for plugin_name in shutdown_order:
            if self.plugins[plugin_name].is_running():
                try:
                    await self.stop_plugin(plugin_name, stop_dependents=False)
                except Exception as e:
                    logger.error(f"Error stopping plugin '{plugin_name}': {e}")
        
        logger.info("All plugins stopped")
    
    # ========== Health Monitoring ==========
    
    async def _subscribe_to_plugin_events(self):
        """Subscribe to plugin events for monitoring"""
        # Subscribe to all plugin events
        await self.event_bus.subscribe(
            f"{Subjects.PLUGINS}.*.>",
            self._handle_plugin_event
        )
        
        # Subscribe to command results/errors for health tracking
        await self.event_bus.subscribe(
            f"{Subjects.COMMANDS}.*.result",
            self._handle_command_result
        )
        
        await self.event_bus.subscribe(
            f"{Subjects.COMMANDS}.*.error",
            self._handle_command_error
        )
    
    async def _handle_plugin_event(self, event):
        """Handle plugin lifecycle events"""
        # Extract plugin name from subject
        # rosey.plugins.{plugin_name}.{event}
        parts = event.subject.split('.')
        if len(parts) >= 3:
            plugin_name = parts[2]
            event_type = parts[3] if len(parts) > 3 else "unknown"
            
            if plugin_name in self.plugins:
                logger.debug(f"Plugin event: {plugin_name} - {event_type}")
                
                if event_type == "error":
                    logger.warning(f"Plugin '{plugin_name}' reported error: {event.data}")
    
    async def _handle_command_result(self, event):
        """Track successful commands"""
        parts = event.subject.split('.')
        if len(parts) >= 3:
            plugin_name = parts[2]
            if plugin_name in self.plugins:
                self.plugins[plugin_name].command_success_count += 1
                self.plugins[plugin_name].last_command_time = datetime.now()
    
    async def _handle_command_error(self, event):
        """Track command errors"""
        parts = event.subject.split('.')
        if len(parts) >= 3:
            plugin_name = parts[2]
            if plugin_name in self.plugins:
                self.plugins[plugin_name].command_error_count += 1
    
    async def health_check_plugin(self, plugin_name: str) -> bool:
        """
        Check if plugin is healthy
        
        Args:
            plugin_name: Plugin to check
        
        Returns:
            True if healthy, False otherwise
        """
        if plugin_name not in self.plugins:
            return False
        
        plugin_info = self.plugins[plugin_name]
        plugin_info.last_health_check = datetime.now()
        
        # Basic: Is process running?
        if not plugin_info.process or not plugin_info.process.is_running():
            if plugin_info.state == PluginState.RUNNING:
                logger.warning(f"Plugin '{plugin_name}' crashed!")
                plugin_info.state = PluginState.CRASHED
                plugin_info.crash_count += 1
                await self._handle_crash(plugin_name)
            return False
        
        # Check resource limits
        if plugin_info.process:
            violations = await plugin_info.process.check_resource_limits()
            if violations:
                logger.warning(
                    f"Plugin '{plugin_name}' resource violations: {violations}"
                )
                plugin_info.state = PluginState.UNHEALTHY
                
                # Restart if repeatedly violating
                if len(violations) >= 2:
                    await self.restart_plugin(plugin_name)
                
                return False
        
        # Check error rate
        if plugin_info.error_rate() > 0.5:  # More than 50% errors
            logger.warning(f"Plugin '{plugin_name}' high error rate: {plugin_info.error_rate():.1%}")
            plugin_info.state = PluginState.UNHEALTHY
            return False
        
        # All checks passed
        if plugin_info.state == PluginState.UNHEALTHY:
            plugin_info.state = PluginState.RUNNING
        
        return True
    
    async def health_check_all(self):
        """Run health checks on all running plugins"""
        for plugin_name, plugin_info in self.plugins.items():
            if plugin_info.is_running():
                await self.health_check_plugin(plugin_name)
    
    async def _handle_crash(self, plugin_name: str):
        """
        Handle plugin crash
        
        Args:
            plugin_name: Plugin that crashed
        """
        plugin_info = self.plugins[plugin_name]
        
        logger.error(
            f"Plugin '{plugin_name}' crashed "
            f"(crash count: {plugin_info.crash_count}/{self.max_crash_count})"
        )
        
        # Check crash count
        if plugin_info.crash_count >= self.max_crash_count:
            logger.error(
                f"Plugin '{plugin_name}' exceeded max crashes, disabling"
            )
            plugin_info.enabled = False
            plugin_info.state = PluginState.DISABLED
            return
        
        # Restart based on policy
        if plugin_info.restart_policy == RestartPolicy.ALWAYS:
            logger.info(f"Auto-restarting plugin '{plugin_name}'")
            # Exponential backoff
            delay = min(2 ** plugin_info.crash_count, 60)
            await asyncio.sleep(delay)
            try:
                await self.start_plugin(plugin_name, force=True)
            except Exception as e:
                logger.error(f"Failed to restart plugin '{plugin_name}': {e}")
        
        elif plugin_info.restart_policy == RestartPolicy.ON_FAILURE:
            # TODO: Check exit code to determine if restart needed
            logger.info(f"Plugin '{plugin_name}' restart policy: on-failure")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        logger.info("Plugin monitoring started")
        
        while self._running:
            try:
                await self.health_check_all()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
        
        logger.info("Plugin monitoring stopped")
    
    # ========== Management API ==========
    
    def enable_plugin(self, plugin_name: str):
        """Enable plugin (allows auto-start)"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].enabled = True
            self.plugins[plugin_name].crash_count = 0
            logger.info(f"Plugin '{plugin_name}' enabled")
    
    def disable_plugin(self, plugin_name: str):
        """Disable plugin (prevents auto-start)"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].enabled = False
            logger.info(f"Plugin '{plugin_name}' disabled")
    
    def get_plugin_status(self, plugin_name: str) -> Optional[Dict]:
        """
        Get plugin status
        
        Returns:
            Status dictionary or None if plugin doesn't exist
        """
        if plugin_name not in self.plugins:
            return None
        
        plugin_info = self.plugins[plugin_name]
        
        stats = {}
        if plugin_info.process:
            stats = plugin_info.process.get_stats()
        
        return {
            "name": plugin_name,
            "state": plugin_info.state.value,
            "enabled": plugin_info.enabled,
            "uptime_seconds": plugin_info.uptime_seconds(),
            "crash_count": plugin_info.crash_count,
            "restart_count": plugin_info.restart_count,
            "error_rate": plugin_info.error_rate(),
            "dependencies": plugin_info.dependencies,
            "dependents": plugin_info.dependents,
            "stats": stats,
        }
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all plugins"""
        return {
            name: self.get_plugin_status(name)
            for name in self.plugins
        }
    
    async def shutdown(self):
        """Shutdown plugin manager"""
        logger.info("Shutting down Plugin Manager...")
        
        # Stop monitoring
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all plugins
        await self.stop_all()
        
        logger.info("Plugin Manager shut down")


# ========== Global Instance ==========

_plugin_manager: Optional[PluginManager] = None


async def initialize_plugin_manager(**kwargs) -> PluginManager:
    """Initialize global plugin manager"""
    global _plugin_manager
    
    if _plugin_manager is not None:
        logger.warning("Plugin Manager already initialized")
        return _plugin_manager
    
    _plugin_manager = PluginManager(**kwargs)
    await _plugin_manager.initialize()
    return _plugin_manager


async def get_plugin_manager() -> PluginManager:
    """Get global plugin manager"""
    if _plugin_manager is None:
        raise RuntimeError("Plugin Manager not initialized")
    return _plugin_manager


async def shutdown_plugin_manager():
    """Shutdown global plugin manager"""
    global _plugin_manager
    
    if _plugin_manager:
        await _plugin_manager.shutdown()
        _plugin_manager = None
```

---

### Task 7.2: Management Commands

**File:** `bot/rosey/plugins/plugin_commands.py`

```python
"""
Plugin management commands
Admin commands to control plugins at runtime
"""
from bot.rosey.core.router import CommandParser, Command
from bot.rosey.plugins.plugin_manager import get_plugin_manager
import logging

logger = logging.getLogger(__name__)


async def handle_plugin_command(command: Command) -> dict:
    """
    Handle !plugin commands
    
    Commands:
        !plugin list - List all plugins and status
        !plugin status <name> - Get detailed status of plugin
        !plugin start <name> - Start plugin
        !plugin stop <name> - Stop plugin
        !plugin restart <name> - Restart plugin
        !plugin enable <name> - Enable plugin
        !plugin disable <name> - Disable plugin
    
    Args:
        command: Parsed command
    
    Returns:
        Response dictionary
    """
    manager = await get_plugin_manager()
    action = command.action
    args = command.args
    
    # Check if user is admin (TODO: implement permissions)
    # For now, allow all
    
    if action == "list":
        return await _handle_list(manager)
    
    elif action == "status":
        if not args:
            return {"message": "Usage: !plugin status <plugin_name>"}
        return await _handle_status(manager, args[0])
    
    elif action == "start":
        if not args:
            return {"message": "Usage: !plugin start <plugin_name>"}
        return await _handle_start(manager, args[0])
    
    elif action == "stop":
        if not args:
            return {"message": "Usage: !plugin stop <plugin_name>"}
        return await _handle_stop(manager, args[0])
    
    elif action == "restart":
        if not args:
            return {"message": "Usage: !plugin restart <plugin_name>"}
        return await _handle_restart(manager, args[0])
    
    elif action == "enable":
        if not args:
            return {"message": "Usage: !plugin enable <plugin_name>"}
        return await _handle_enable(manager, args[0])
    
    elif action == "disable":
        if not args:
            return {"message": "Usage: !plugin disable <plugin_name>"}
        return await _handle_disable(manager, args[0])
    
    else:
        return {
            "message": f"Unknown plugin action: {action}\n"
                      "Available: list, status, start, stop, restart, enable, disable"
        }


async def _handle_list(manager) -> dict:
    """List all plugins"""
    statuses = manager.get_all_status()
    
    lines = ["**Plugins:**\n"]
    
    for name, status in statuses.items():
        state = status["state"]
        enabled = "✅" if status["enabled"] else "❌"
        uptime = status["uptime_seconds"]
        
        state_emoji = {
            "running": "🟢",
            "stopped": "⚫",
            "crashed": "🔴",
            "unhealthy": "🟡",
            "starting": "🔵",
            "stopping": "🔵",
            "disabled": "❌",
        }.get(state, "❓")
        
        uptime_str = f"{uptime/3600:.1f}h" if uptime > 0 else "-"
        
        lines.append(
            f"{enabled} {state_emoji} **{name}** - {state} (uptime: {uptime_str})"
        )
    
    return {"message": "\n".join(lines)}


async def _handle_status(manager, plugin_name: str) -> dict:
    """Get detailed plugin status"""
    status = manager.get_plugin_status(plugin_name)
    
    if not status:
        return {"message": f"❌ Plugin '{plugin_name}' not found"}
    
    lines = [
        f"**Plugin: {plugin_name}**\n",
        f"State: {status['state']}",
        f"Enabled: {'Yes' if status['enabled'] else 'No'}",
        f"Uptime: {status['uptime_seconds']/3600:.1f}h",
        f"Crashes: {status['crash_count']}",
        f"Restarts: {status['restart_count']}",
        f"Error Rate: {status['error_rate']:.1%}",
    ]
    
    if status['dependencies']:
        lines.append(f"Dependencies: {', '.join(status['dependencies'])}")
    
    if status['dependents']:
        lines.append(f"Dependents: {', '.join(status['dependents'])}")
    
    stats = status.get('stats', {})
    if stats.get('running'):
        lines.extend([
            f"\n**Resources:**",
            f"CPU: {stats.get('cpu_percent', 0):.1f}%",
            f"Memory: {stats.get('memory_mb', 0):.1f}MB",
        ])
    
    return {"message": "\n".join(lines)}


async def _handle_start(manager, plugin_name: str) -> dict:
    """Start plugin"""
    try:
        await manager.start_plugin(plugin_name)
        return {"message": f"✅ Started plugin: {plugin_name}"}
    except Exception as e:
        return {"message": f"❌ Failed to start {plugin_name}: {e}"}


async def _handle_stop(manager, plugin_name: str) -> dict:
    """Stop plugin"""
    try:
        await manager.stop_plugin(plugin_name)
        return {"message": f"✅ Stopped plugin: {plugin_name}"}
    except Exception as e:
        return {"message": f"❌ Failed to stop {plugin_name}: {e}"}


async def _handle_restart(manager, plugin_name: str) -> dict:
    """Restart plugin"""
    try:
        await manager.restart_plugin(plugin_name)
        return {"message": f"✅ Restarted plugin: {plugin_name}"}
    except Exception as e:
        return {"message": f"❌ Failed to restart {plugin_name}: {e}"}


async def _handle_enable(manager, plugin_name: str) -> dict:
    """Enable plugin"""
    manager.enable_plugin(plugin_name)
    return {"message": f"✅ Enabled plugin: {plugin_name}"}


async def _handle_disable(manager, plugin_name: str) -> dict:
    """Disable plugin"""
    manager.disable_plugin(plugin_name)
    return {"message": f"✅ Disabled plugin: {plugin_name}"}
```

---

### Task 7.3: Integration with Main Bot

**Update:** `bot/rosey/main.py`

```python
"""
Add PluginManager initialization to main bot
"""

from bot.rosey.plugins.plugin_manager import initialize_plugin_manager, shutdown_plugin_manager
from bot.rosey.plugins.plugin_commands import handle_plugin_command

class RoseyBot:
    async def start(self):
        # ... existing EventBus and Router init ...
        
        # Initialize Plugin Manager
        self.plugin_manager = await initialize_plugin_manager(
            plugins_dir="bot/rosey/plugins",
            event_bus=self.event_bus
        )
        
        logger.info("Plugin Manager initialized")
        
        # Start all plugins
        await self.plugin_manager.start_all()
        
        logger.info("All plugins started")
        
        # Register plugin management commands
        self.router.register_command_handler("plugin", handle_plugin_command)
    
    async def stop(self):
        # ... existing shutdown ...
        
        # Shutdown plugins
        await shutdown_plugin_manager()
```

---

## Configuration

**File:** `config/plugins.yaml`

```yaml
# Plugin configuration

# Directory containing plugins
plugins_dir: bot/rosey/plugins

# Health monitoring
health_check_interval: 30  # seconds
max_crash_count: 3

# Plugin-specific config
plugins:
  trivia:
    enabled: true
    restart_policy: always
    dependencies: []
  
  markov:
    enabled: true
    restart_policy: always
    dependencies: []
  
  calendar:
    enabled: true
    restart_policy: on-failure
    dependencies: []
  
  quote:
    enabled: false  # Disabled by default
    restart_policy: never
    dependencies: []
```

---

## Testing

**File:** `tests/plugins/test_plugin_manager.py`

```python
"""
Tests for Plugin Manager
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from bot.rosey.plugins.plugin_manager import (
    PluginManager,
    PluginInfo,
    PluginState,
    RestartPolicy
)
from bot.rosey.plugins.plugin_manifest import PluginManifest


@pytest.fixture
def mock_event_bus():
    """Mock event bus"""
    bus = Mock()
    bus.subscribe = AsyncMock()
    bus.servers = ["nats://localhost:4222"]
    return bus


@pytest.fixture
async def plugin_manager(mock_event_bus):
    """Create plugin manager for testing"""
    manager = PluginManager(
        plugins_dir="bot/rosey/plugins",
        event_bus=mock_event_bus
    )
    
    # Add some test plugins manually
    manager.plugins["plugin_a"] = PluginInfo(
        name="plugin_a",
        manifest=PluginManifest(name="plugin_a", version="1.0.0", description="Test"),
        plugin_path="plugins/plugin_a.py"
    )
    
    manager.plugins["plugin_b"] = PluginInfo(
        name="plugin_b",
        manifest=PluginManifest(name="plugin_b", version="1.0.0", description="Test"),
        plugin_path="plugins/plugin_b.py",
        dependencies=["plugin_a"]
    )
    
    return manager


def test_dependency_graph_building(plugin_manager):
    """Test dependency graph construction"""
    plugin_manager._validate_dependencies()
    
    # plugin_b depends on plugin_a
    assert "plugin_a" in plugin_manager.plugins["plugin_b"].dependencies
    
    # plugin_a should have plugin_b as dependent
    assert "plugin_b" in plugin_manager.plugins["plugin_a"].dependents


def test_startup_order(plugin_manager):
    """Test startup order respects dependencies"""
    plugin_manager._validate_dependencies()
    order = plugin_manager._get_startup_order()
    
    # plugin_a should start before plugin_b
    assert order.index("plugin_a") < order.index("plugin_b")


def test_circular_dependency_detection(plugin_manager):
    """Test circular dependency detection"""
    # Create circular dependency
    plugin_manager.plugins["plugin_a"].dependencies = ["plugin_b"]
    plugin_manager.plugins["plugin_b"].dependencies = ["plugin_a"]
    
    # Should detect circle
    assert plugin_manager._has_circular_dependency("plugin_a", set())


@pytest.mark.asyncio
async def test_plugin_state_tracking(plugin_manager):
    """Test plugin state changes"""
    plugin_info = plugin_manager.plugins["plugin_a"]
    
    assert plugin_info.state == PluginState.STOPPED
    
    # Simulate state changes
    plugin_info.state = PluginState.STARTING
    assert not plugin_info.is_running()
    
    plugin_info.state = PluginState.RUNNING
    assert plugin_info.is_running()
    
    plugin_info.state = PluginState.CRASHED
    assert not plugin_info.is_running()


@pytest.mark.asyncio
async def test_enable_disable(plugin_manager):
    """Test enabling/disabling plugins"""
    plugin_info = plugin_manager.plugins["plugin_a"]
    
    assert plugin_info.enabled
    
    plugin_manager.disable_plugin("plugin_a")
    assert not plugin_info.enabled
    
    plugin_manager.enable_plugin("plugin_a")
    assert plugin_info.enabled
    assert plugin_info.crash_count == 0  # Should reset crash count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Documentation

**File:** `docs/plugins/PLUGIN-MANAGEMENT.md`

```markdown
# Plugin Management

## Plugin Manager Overview

The Plugin Manager orchestrates all plugins:
- Discovery and loading
- Dependency-ordered startup
- Health monitoring
- Crash recovery
- Resource enforcement
- Runtime control

## Runtime Commands

### List All Plugins

```
!plugin list
```

Shows all plugins with status, uptime, and enabled state.

### Get Plugin Status

```
!plugin status trivia
```

Shows detailed status:
- State (running, stopped, crashed, etc.)
- Uptime
- Resource usage (CPU, memory)
- Error rate
- Dependencies

### Start/Stop Plugins

```
!plugin start trivia
!plugin stop trivia
!plugin restart trivia
```

### Enable/Disable Plugins

```
!plugin enable calendar
!plugin disable quote
```

Disabled plugins won't auto-start on bot restart.

## Plugin States

- **stopped** - Not running
- **starting** - In process of starting
- **running** - Running normally
- **unhealthy** - Running but failing health checks
- **crashed** - Process died unexpectedly
- **stopping** - In process of stopping
- **disabled** - Intentionally disabled

## Restart Policies

Set in plugin manifest:

```python
restart_policy = RestartPolicy.ALWAYS     # Always restart on crash
restart_policy = RestartPolicy.ON_FAILURE # Restart only on error exit
restart_policy = RestartPolicy.NEVER      # Never auto-restart
```

## Dependencies

Plugins can declare dependencies:

```python
dependencies=["markov", "calendar"]
```

Plugin Manager ensures:
- Dependencies start first
- Stopping plugin also stops dependents (optional)
- Circular dependencies detected at startup

## Health Monitoring

Plugin Manager monitors:
- Process alive
- Resource limits (CPU, memory)
- Error rate
- Recent activity

Health checks run every 30 seconds by default.

## Crash Recovery

On crash:
1. Increment crash counter
2. Check restart policy
3. If ALWAYS: restart with exponential backoff
4. If crash count exceeds max (3): disable plugin

## Configuration

**config/plugins.yaml:**

```yaml
plugins_dir: bot/rosey/plugins
health_check_interval: 30
max_crash_count: 3

plugins:
  trivia:
    enabled: true
    restart_policy: always
```

## Programmatic Access

```python
from bot.rosey.plugins.plugin_manager import get_plugin_manager

manager = await get_plugin_manager()

# Start plugin
await manager.start_plugin("trivia")

# Get status
status = manager.get_plugin_status("trivia")

# Enable/disable
manager.enable_plugin("calendar")
manager.disable_plugin("quote")
```
```

---

## Success Criteria

✅ PluginManager class implemented  
✅ Dependency tracking and ordering  
✅ Lifecycle management (start/stop/restart)  
✅ Health monitoring with auto-recovery  
✅ Resource limit enforcement  
✅ Management commands (!plugin)  
✅ Integration with main bot  
✅ Tests covering core functionality  
✅ Documentation complete  

---

## Time Breakdown

- PluginManager core: 2 hours
- Dependency handling: 45 minutes
- Health monitoring: 1 hour
- Management commands: 30 minutes
- Testing: 45 minutes
- Documentation: 30 minutes

**Total: 5.5 hours**

---

## Next: Sortie 8 - Testing & Validation

With the complete system in place (NATS, EventBus, Subjects, Connectors, Router, Plugin Sandbox, Plugin Manager), Sortie 8 will provide comprehensive testing to validate the entire architecture works correctly.

---

## Production Considerations

**Current Implementation: Development-Ready**
- ✅ Basic lifecycle management
- ✅ Crash recovery
- ✅ Resource monitoring
- ✅ Dependency handling

**Future Enhancements:**
- Persistent plugin state across bot restarts
- More sophisticated health checks (NATS ping/pong)
- Plugin versioning and updates
- Hot-reload without restart
- Metrics export (Prometheus)
- Dashboard/UI for monitoring
- Plugin marketplace integration
