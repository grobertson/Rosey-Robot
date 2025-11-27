"""
Plugin Process Isolation System

This module provides process isolation for plugins, ensuring they run in separate
processes with resource monitoring, crash recovery, and controlled IPC through
the EventBus.

Key Components:
- PluginProcess: Manages individual plugin subprocesses
- ResourceMonitor: Tracks resource usage (CPU, memory, etc.)
- PluginIPC: EventBus wrapper for plugin communication
- RestartPolicy: Configurable restart behavior

Architecture:
    Main Process
        │
        ├── EventBus (NATS)
        │
        ├── PluginProcess(echo)
        │   ├── subprocess
        │   ├── ResourceMonitor
        │   └── PluginIPC → EventBus
        │
        ├── PluginProcess(trivia)
        │   ├── subprocess
        │   ├── ResourceMonitor
        │   └── PluginIPC → EventBus
        │
        └── PluginProcess(markov)
            ├── subprocess
            ├── ResourceMonitor
            └── PluginIPC → EventBus
"""

import asyncio
import importlib
import inspect
import json
import logging
import multiprocessing
import os
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, List

try:
    import psutil
except ImportError:
    psutil = None

try:
    import nats
except ImportError:
    nats = None

from .event_bus import EventBus, Event, Priority
from .subjects import build_plugin_subject, EventTypes

logger = logging.getLogger(__name__)


# ============================================================================
# Restart Policies
# ============================================================================

class RestartPolicy(Enum):
    """Plugin restart policies"""
    NEVER = "never"  # Don't restart on failure
    ON_FAILURE = "on-failure"  # Restart only on non-zero exit
    ALWAYS = "always"  # Always restart regardless of exit code
    UNLESS_STOPPED = "unless-stopped"  # Restart unless explicitly stopped


@dataclass
class RestartConfig:
    """Configuration for plugin restart behavior"""
    enabled: bool = True  # Auto-restart enabled
    max_attempts: int = 5  # Max consecutive failures
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    initial_delay: float = 1.0  # Initial backoff delay (seconds)
    max_delay: float = 30.0  # Max backoff delay (seconds)
    reset_window: float = 60.0  # Reset attempt count after success for this long


@dataclass
class RestartAttempt:
    """Single restart attempt record"""
    timestamp: float  # When restart was attempted
    success: bool  # Whether restart succeeded
    exit_code: Optional[int]  # Exit code of crashed process
    signal: Optional[int]  # Signal that killed process


# ============================================================================
# Resource Monitoring
# ============================================================================

@dataclass
class ResourceUsage:
    """Snapshot of plugin resource usage"""
    timestamp: float
    cpu_percent: float  # CPU usage percentage
    memory_mb: float  # Memory usage in MB
    memory_percent: float  # Memory usage percentage
    num_threads: int  # Number of threads
    num_fds: int  # Number of file descriptors (Unix only)
    io_read_mb: float  # IO read in MB
    io_write_mb: float  # IO write in MB


@dataclass
class ResourceLimits:
    """Resource limits for plugin processes"""
    max_cpu_percent: Optional[float] = None  # Max CPU % (per core)
    max_memory_mb: Optional[float] = None  # Max memory in MB
    max_threads: Optional[int] = None  # Max thread count
    max_fds: Optional[int] = None  # Max file descriptors
    check_interval: float = 5.0  # How often to check (seconds)
    violation_threshold: int = 2  # Consecutive violations before kill


@dataclass
class ResourceStats:
    """Resource usage statistics"""
    current_cpu_percent: float
    current_memory_mb: float
    peak_cpu_percent: float
    peak_memory_mb: float
    total_checks: int
    violations: int
    last_check: float  # timestamp


class ResourceMonitor:
    """
    Monitors resource usage of a plugin process.

    Tracks CPU, memory, threads, file descriptors, and I/O stats.
    Can enforce limits and trigger callbacks when exceeded.
    """

    def __init__(
        self,
        pid: int,
        limits: Optional[ResourceLimits] = None,
        sample_interval: float = 1.0
    ):
        """
        Initialize resource monitor.

        Args:
            pid: Process ID to monitor
            limits: Optional resource limits
            sample_interval: Sampling interval in seconds
        """
        self.pid = pid
        self.limits = limits or ResourceLimits()
        self.sample_interval = sample_interval

        if psutil is None:
            logger.warning("psutil not installed, resource monitoring disabled")
            self._process = None
        else:
            try:
                self._process = psutil.Process(pid)
            except psutil.NoSuchProcess:
                logger.error(f"Process {pid} not found")
                self._process = None

        self._history: List[ResourceUsage] = []
        self._max_history = 3600  # Keep 1 hour at 1s intervals
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[ResourceUsage], None]] = []

    def add_callback(self, callback: Callable[[ResourceUsage], None]) -> None:
        """Add callback for resource updates"""
        self._callbacks.append(callback)

    async def start_monitoring(self) -> None:
        """Start background monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.debug(f"Started monitoring process {self.pid}")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring"""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.debug(f"Stopped monitoring process {self.pid}")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                usage = await self.get_current_usage()
                if usage:
                    self._history.append(usage)

                    # Trim history
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]

                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback(usage)
                        except Exception as e:
                            logger.error(f"Resource callback error: {e}")

                    # Check limits
                    violations = self.check_limits(usage)
                    if violations:
                        logger.warning(f"Resource limit violations for PID {self.pid}: {violations}")

                await asyncio.sleep(self.sample_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error for PID {self.pid}: {e}")
                await asyncio.sleep(self.sample_interval)

    async def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get current resource usage snapshot"""
        if self._process is None:
            return None

        try:
            # Run psutil calls in thread pool (they can block)
            loop = asyncio.get_event_loop()

            cpu_percent = await loop.run_in_executor(None, self._process.cpu_percent, 0.1)
            mem_info = await loop.run_in_executor(None, self._process.memory_info)
            mem_percent = await loop.run_in_executor(None, self._process.memory_percent)
            num_threads = await loop.run_in_executor(None, self._process.num_threads)

            # IO counters (may not be available on all platforms)
            try:
                io_counters = await loop.run_in_executor(None, self._process.io_counters)
                io_read_mb = io_counters.read_bytes / (1024 * 1024)
                io_write_mb = io_counters.write_bytes / (1024 * 1024)
            except (AttributeError, psutil.AccessDenied):
                io_read_mb = 0.0
                io_write_mb = 0.0

            # File descriptors (Unix only)
            try:
                num_fds = await loop.run_in_executor(None, self._process.num_fds)
            except (AttributeError, psutil.AccessDenied):
                num_fds = 0

            return ResourceUsage(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_mb=mem_info.rss / (1024 * 1024),
                memory_percent=mem_percent,
                num_threads=num_threads,
                num_fds=num_fds,
                io_read_mb=io_read_mb,
                io_write_mb=io_write_mb
            )

        except psutil.NoSuchProcess:
            logger.debug(f"Process {self.pid} no longer exists")
            return None
        except Exception as e:
            logger.error(f"Error getting resource usage for PID {self.pid}: {e}")
            return None

    def check_limits(self, usage: ResourceUsage) -> List[str]:
        """
        Check if usage exceeds limits.

        Returns:
            List of violation descriptions
        """
        violations = []

        if self.limits.max_cpu_percent and usage.cpu_percent > self.limits.max_cpu_percent:
            violations.append(f"CPU {usage.cpu_percent:.1f}% > {self.limits.max_cpu_percent}%")

        if self.limits.max_memory_mb and usage.memory_mb > self.limits.max_memory_mb:
            violations.append(f"Memory {usage.memory_mb:.1f}MB > {self.limits.max_memory_mb}MB")

        if self.limits.max_threads and usage.num_threads > self.limits.max_threads:
            violations.append(f"Threads {usage.num_threads} > {self.limits.max_threads}")

        if self.limits.max_fds and usage.num_fds > self.limits.max_fds:
            violations.append(f"FDs {usage.num_fds} > {self.limits.max_fds}")

        return violations

    def get_history(self, duration_seconds: Optional[float] = None) -> List[ResourceUsage]:
        """Get resource usage history"""
        if duration_seconds is None:
            return self._history.copy()

        cutoff = time.time() - duration_seconds
        return [u for u in self._history if u.timestamp >= cutoff]

    def get_average_usage(self, duration_seconds: Optional[float] = None) -> Optional[ResourceUsage]:
        """Get average resource usage over time period"""
        history = self.get_history(duration_seconds)
        if not history:
            return None

        return ResourceUsage(
            timestamp=time.time(),
            cpu_percent=sum(u.cpu_percent for u in history) / len(history),
            memory_mb=sum(u.memory_mb for u in history) / len(history),
            memory_percent=sum(u.memory_percent for u in history) / len(history),
            num_threads=sum(u.num_threads for u in history) // len(history),
            num_fds=sum(u.num_fds for u in history) // len(history),
            io_read_mb=sum(u.io_read_mb for u in history) / len(history),
            io_write_mb=sum(u.io_write_mb for u in history) / len(history)
        )


# ============================================================================
# Plugin IPC
# ============================================================================

class PluginIPC:
    """
    EventBus wrapper for plugin-specific communication.

    Provides high-level interface for plugin IPC patterns:
    - Command handling (subscribe to plugin commands)
    - Event publishing (publish plugin events)
    - Health checks (respond to health probes)
    - Shutdown signals (receive shutdown notifications)
    """

    def __init__(self, plugin_name: str, event_bus: EventBus):
        """
        Initialize plugin IPC.

        Args:
            plugin_name: Name of the plugin
            event_bus: EventBus instance for communication
        """
        self.plugin_name = plugin_name
        self.event_bus = event_bus
        self._command_subscriptions: Dict[str, int] = {}

    async def subscribe_commands(
        self,
        callback: Callable[[Event], Any]
    ) -> None:
        """
        Subscribe to all commands for this plugin.

        Args:
            callback: Async callback function to handle commands
        """
        subject = f"rosey.commands.{self.plugin_name}.>"
        sid = await self.event_bus.subscribe(subject, callback)
        self._command_subscriptions[subject] = sid
        logger.info(f"Plugin {self.plugin_name} subscribed to commands")

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: Priority = Priority.NORMAL
    ) -> None:
        """
        Publish an event from this plugin.

        Args:
            event_type: Type of event
            data: Event data
            priority: Event priority
        """
        subject = build_plugin_subject(self.plugin_name, event_type)
        event = Event(
            subject=subject,
            event_type=event_type,
            source=f"plugin.{self.plugin_name}",
            data=data,
            priority=priority
        )
        await self.event_bus.publish(event)

    async def send_health_ok(self, details: Optional[Dict[str, Any]] = None) -> None:
        """Send health check OK response"""
        await self.publish_event(
            EventTypes.HEALTH_CHECK,
            {
                "status": "ok",
                "plugin": self.plugin_name,
                "timestamp": time.time(),
                **(details or {})
            }
        )

    async def send_startup(self, details: Optional[Dict[str, Any]] = None) -> None:
        """Send plugin startup notification"""
        await self.publish_event(
            EventTypes.PLUGIN_START,
            {
                "plugin": self.plugin_name,
                "pid": os.getpid(),
                "timestamp": time.time(),
                **(details or {})
            },
            priority=Priority.HIGH
        )

    async def send_shutdown(self, details: Optional[Dict[str, Any]] = None) -> None:
        """Send plugin shutdown notification"""
        await self.publish_event(
            EventTypes.PLUGIN_STOP,
            {
                "plugin": self.plugin_name,
                "pid": os.getpid(),
                "timestamp": time.time(),
                **(details or {})
            },
            priority=Priority.HIGH
        )

    async def cleanup(self) -> None:
        """Cleanup IPC resources"""
        for subject, sid in self._command_subscriptions.items():
            try:
                await self.event_bus.unsubscribe(sid)
            except Exception as e:
                logger.error(f"Error unsubscribing from {subject}: {e}")
        self._command_subscriptions.clear()


# ============================================================================
# Plugin Process
# ============================================================================

class PluginState(Enum):
    """Plugin process states"""
    STOPPED = "stopped"  # Not running
    STARTING = "starting"  # Starting up
    RUNNING = "running"  # Running normally
    UNHEALTHY = "unhealthy"  # Running but health check failing
    STOPPING = "stopping"  # Shutting down
    CRASHED = "crashed"  # Exited unexpectedly
    FAILED = "failed"  # Failed to start


@dataclass
class PluginProcess:
    """
    Manages a plugin subprocess with monitoring and IPC.

    Handles:
    - Process lifecycle (start, stop, restart)
    - Resource monitoring
    - Health checks
    - Crash recovery
    - IPC through EventBus
    """

    # Configuration
    plugin_name: str
    module_path: str  # Python module path or script path
    event_bus: EventBus
    restart_config: RestartConfig = field(default_factory=RestartConfig)
    resource_limits: Optional[ResourceLimits] = None

    # State (don't pass to __init__)
    state: PluginState = field(default=PluginState.STOPPED, init=False)
    process: Optional[multiprocessing.Process] = field(default=None, init=False)
    pid: Optional[int] = field(default=None, init=False)
    monitor: Optional[ResourceMonitor] = field(default=None, init=False)

    # Runtime tracking
    _start_time: Optional[float] = field(default=None, init=False)
    _restart_count: int = field(default=0, init=False)
    _last_restart: Optional[float] = field(default=None, init=False)
    _health_check_task: Optional[asyncio.Task] = field(default=None, init=False)
    _monitor_task: Optional[asyncio.Task] = field(default=None, init=False)
    restart_attempts: List[RestartAttempt] = field(default_factory=list, init=False)
    
    # Resource monitoring
    resource_monitor: Optional[ResourceMonitor] = field(default=None, init=False)
    resource_stats: Optional[ResourceStats] = field(default=None, init=False)
    _resource_task: Optional[asyncio.Task] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize after dataclass creation"""
        self._callbacks: Dict[str, List[Callable]] = {
            "state_change": [],
            "resource_violation": [],
            "health_check_failed": []
        }

    async def start(self) -> bool:
        """
        Start the plugin process.

        Returns:
            True if started successfully
        """
        if self.state not in (PluginState.STOPPED, PluginState.CRASHED, PluginState.FAILED):
            logger.warning(f"Cannot start plugin {self.plugin_name} in state {self.state}")
            return False

        self._set_state(PluginState.STARTING)
        logger.info(f"Starting plugin {self.plugin_name}")

        try:
            # Create subprocess
            self.process = multiprocessing.Process(
                target=self._run_plugin,
                name=f"plugin-{self.plugin_name}",
                daemon=False
            )
            self.process.start()
            self.pid = self.process.pid
            self._start_time = time.time()

            logger.info(f"Plugin {self.plugin_name} spawned with PID {self.pid}")

            # Wait for plugin to be ready (up to 2 seconds)
            ready = await self._wait_for_ready(timeout=2.0)
            
            if not ready:
                # Plugin didn't start properly
                logger.error(f"Plugin {self.plugin_name} failed to become ready")
                self._set_state(PluginState.FAILED)
                await self.stop()  # Clean up
                return False
            
            # Start resource monitoring
            if psutil:
                self.monitor = ResourceMonitor(
                    self.pid,
                    limits=self.resource_limits,
                    sample_interval=1.0
                )
                self.monitor.add_callback(self._on_resource_update)
                await self.monitor.start_monitoring()

            # Start health checking (legacy)
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # Start crash monitoring
            self._monitor_task = asyncio.create_task(self._monitor_subprocess())
            
            # Start resource limit enforcement (Sortie 4)
            if self.resource_limits:
                await self._start_resource_monitoring()

            self._set_state(PluginState.RUNNING)
            logger.info(f"Plugin {self.plugin_name} is running")
            return True

        except Exception as e:
            logger.error(f"Failed to start plugin {self.plugin_name}: {e}")
            self._set_state(PluginState.FAILED)
            return False

    async def stop(self, timeout: float = 10.0) -> bool:
        """
        Stop the plugin process gracefully.

        Args:
            timeout: Seconds to wait before force killing

        Returns:
            True if stopped gracefully, False if force killed
        """
        if self.state == PluginState.STOPPED:
            return True
        
        if not self.process or not self.process.is_alive():
            self._set_state(PluginState.STOPPED)
            self.pid = None
            return True

        self._set_state(PluginState.STOPPING)
        logger.info(f"Stopping plugin {self.plugin_name} (PID {self.pid})")

        try:
            # Stop health checks
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Stop crash monitoring
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Stop resource monitoring task
            if self._resource_task:
                self._resource_task.cancel()
                try:
                    await self._resource_task
                except asyncio.CancelledError:
                    pass
                self._resource_task = None

            # Stop monitoring
            if self.monitor:
                await self.monitor.stop_monitoring()

            # Send SIGTERM for graceful shutdown
            self.process.terminate()
            logger.debug(f"Sent SIGTERM to plugin {self.plugin_name}")

            # Wait for graceful exit with timeout
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self.process.join),
                    timeout=timeout
                )
                logger.info(f"Plugin {self.plugin_name} stopped gracefully")
                self._set_state(PluginState.STOPPED)
                self.pid = None
                return True
                
            except asyncio.TimeoutError:
                # Force kill after timeout
                logger.warning(f"Plugin {self.plugin_name} did not stop within {timeout}s, force killing")
                self.process.kill()
                await asyncio.to_thread(self.process.join, 2.0)
                logger.info(f"Plugin {self.plugin_name} force killed")
                self._set_state(PluginState.STOPPED)
                self.pid = None
                return False

        except Exception as e:
            logger.error(f"Error stopping plugin {self.plugin_name}: {e}")
            self._set_state(PluginState.STOPPED)
            self.pid = None
            return False

    async def restart(self) -> bool:
        """
        Restart the plugin process.

        Returns:
            True if restarted successfully
        """
        logger.info(f"Restarting plugin {self.plugin_name}")
        await self.stop()
        await asyncio.sleep(0.5)  # Brief pause
        return await self.start()

    def is_alive(self) -> bool:
        """Check if process is alive"""
        return self.process is not None and self.process.is_alive()

    @property
    def start_time(self) -> Optional[float]:
        """Get process start time"""
        return self._start_time

    def get_uptime(self) -> Optional[float]:
        """Get plugin uptime in seconds"""
        if self._start_time is None:
            return None
        return time.time() - self._start_time

    async def _wait_for_ready(self, timeout: float) -> bool:
        """
        Wait for plugin to publish ready event.
        
        Args:
            timeout: Max seconds to wait
            
        Returns:
            bool: True if ready event received, False if timeout
        """
        ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
        ready_event = asyncio.Event()
        
        async def ready_handler(msg):
            """Handle ready event"""
            logger.debug(f"Plugin {self.plugin_name} ready event received")
            ready_event.set()
        
        # Subscribe to ready subject
        sub = await self.event_bus.subscribe(ready_subject, callback=ready_handler)
        
        try:
            # Wait for ready event with timeout
            await asyncio.wait_for(ready_event.wait(), timeout=timeout)
            logger.info(f"Plugin {self.plugin_name} is ready")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Plugin {self.plugin_name} ready timeout after {timeout}s")
            return False
        finally:
            # Always unsubscribe
            await sub.unsubscribe()

    def _run_plugin(self) -> None:
        """
        Plugin subprocess entry point.

        This runs IN THE SUBPROCESS. It:
        1. Sets up signal handlers for graceful shutdown
        2. Connects to NATS
        3. Dynamically imports the plugin module
        4. Finds and instantiates the plugin class
        5. Calls plugin.initialize()
        6. Runs the asyncio event loop
        7. Cleans up on shutdown
        """
        import signal
        import importlib
        import inspect
        import sys
        from pathlib import Path
        
        # Setup logging for subprocess
        logging.basicConfig(
            level=logging.INFO,
            format=f'[%(asctime)s] [%(levelname)s] [plugin:{self.plugin_name}] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        subprocess_logger = logging.getLogger(__name__)
        
        subprocess_logger.info(f"Plugin {self.plugin_name} subprocess started (PID: {os.getpid()})")
        
        # Shutdown event for signal handling
        shutdown_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            """Handle shutdown signals gracefully"""
            subprocess_logger.info(f"Plugin {self.plugin_name} received signal {signum}")
            shutdown_event.set()
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Run the async main function
        try:
            asyncio.run(self._run_plugin_async(subprocess_logger, shutdown_event))
        except Exception as e:
            subprocess_logger.error(f"Plugin {self.plugin_name} fatal error: {e}", exc_info=True)
            sys.exit(1)
        
        subprocess_logger.info(f"Plugin {self.plugin_name} subprocess exiting")
    
    async def _run_plugin_async(self, subprocess_logger: logging.Logger, shutdown_event: asyncio.Event) -> None:
        """
        Async plugin subprocess main function.
        
        Args:
            subprocess_logger: Logger for subprocess
            shutdown_event: Event that gets set on shutdown signal
        """
        import importlib
        import inspect
        import sys
        from pathlib import Path
        
        plugin_instance = None
        nc = None
        
        try:
            # 1. Connect to NATS
            nats_servers = self.event_bus.servers if hasattr(self.event_bus, 'servers') else ["nats://localhost:4222"]
            subprocess_logger.info(f"Connecting to NATS: {nats_servers}")
            nc = await nats.connect(servers=nats_servers)
            subprocess_logger.info(f"Plugin {self.plugin_name} connected to NATS")
            
            # 2. Dynamically import the plugin module
            subprocess_logger.info(f"Loading plugin module: {self.module_path}")
            
            # Add plugin directory to Python path if needed
            plugin_dir = Path(self.module_path).parent
            if str(plugin_dir) not in sys.path:
                sys.path.insert(0, str(plugin_dir))
            
            # Import the module
            try:
                # Try importing as package (plugins.dice-roller.plugin)
                module_name = self.module_path.replace('/', '.').replace('\\', '.')
                if module_name.endswith('.py'):
                    module_name = module_name[:-3]
                plugin_module = importlib.import_module(module_name)
            except ImportError:
                # Try importing from file path
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"plugin_{self.plugin_name}",
                    self.module_path
                )
                if spec and spec.loader:
                    plugin_module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = plugin_module
                    spec.loader.exec_module(plugin_module)
                else:
                    raise ImportError(f"Could not load plugin from {self.module_path}")
            
            subprocess_logger.info(f"Plugin module loaded: {plugin_module.__name__}")
            
            # 3. Find the plugin class (class ending with "Plugin")
            plugin_class = None
            
            # First try inspect.getmembers (works for real modules)
            for name, obj in inspect.getmembers(plugin_module, inspect.isclass):
                if name.endswith('Plugin') and hasattr(obj, '__module__') and obj.__module__ == plugin_module.__name__:
                    plugin_class = obj
                    subprocess_logger.info(f"Found plugin class via inspect: {name}")
                    break
            
            # Fallback: search module __dict__ for classes ending with "Plugin" (works for mocks and dynamic modules)
            if plugin_class is None:
                for name in dir(plugin_module):
                    if name.endswith('Plugin'):
                        obj = getattr(plugin_module, name)
                        if inspect.isclass(obj) or (hasattr(obj, '__call__') and hasattr(obj, '__name__')):
                            plugin_class = obj
                            subprocess_logger.info(f"Found plugin class via getattr: {name}")
                            break
            
            if plugin_class is None:
                raise RuntimeError(
                    f"No plugin class found in {self.module_path}. "
                    "Plugin class name must end with 'Plugin'."
                )
            
            # 4. Instantiate the plugin class with NATS client
            subprocess_logger.info(f"Instantiating plugin class: {plugin_class.__name__}")
            
            # Get plugin config (if any)
            plugin_config = {}  # TODO: Load from config file in future
            
            # Instantiate plugin
            plugin_instance = plugin_class(nats_client=nc, config=plugin_config)
            subprocess_logger.info(f"Plugin instance created: {plugin_instance}")
            
            # 5. Initialize the plugin (subscribe to subjects)
            subprocess_logger.info(f"Initializing plugin {self.plugin_name}")
            await plugin_instance.initialize()
            subprocess_logger.info(f"Plugin {self.plugin_name} initialized successfully")
            
            # 5a. Publish ready event
            ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
            await nc.publish(ready_subject, b"ready")
            subprocess_logger.info(f"Plugin {self.plugin_name} published ready event")
            
            # 6. Run event loop until shutdown signal
            subprocess_logger.info(f"Plugin {self.plugin_name} running, waiting for shutdown signal")
            await shutdown_event.wait()
            
        except Exception as e:
            subprocess_logger.error(
                f"Error in plugin {self.plugin_name}: {e}",
                exc_info=True
            )
            raise
        
        finally:
            # 7. Cleanup
            subprocess_logger.info(f"Plugin {self.plugin_name} shutting down")
            
            if plugin_instance and hasattr(plugin_instance, 'shutdown'):
                try:
                    subprocess_logger.info("Calling plugin.shutdown()")
                    await plugin_instance.shutdown()
                except Exception as e:
                    subprocess_logger.error(f"Error during plugin shutdown: {e}")
            
            if nc:
                try:
                    subprocess_logger.info("Closing NATS connection")
                    await nc.close()
                except Exception as e:
                    subprocess_logger.error(f"Error closing NATS: {e}")
            
            subprocess_logger.info(f"Plugin {self.plugin_name} cleanup complete")

    async def _monitor_subprocess(self) -> None:
        """
        Monitor subprocess and handle crashes.
        Runs continuously while plugin should be running (0.5s polling).
        """
        while self.state == PluginState.RUNNING:
            await asyncio.sleep(0.5)
            
            if not self.is_alive():
                # Crash detected
                exit_code = self.process.exitcode if self.process else -1
                logger.error(f"Plugin {self.plugin_name} crashed (exit code {exit_code})")
                
                # Update state
                self._set_state(PluginState.FAILED)
                
                # Log crash event
                await self._handle_crash(exit_code)
                
                # Auto-restart if enabled
                if self.restart_config.enabled:
                    await self._attempt_restart()
                
                break

    async def _health_check_loop(self) -> None:
        """Background health check loop (legacy - kept for compatibility)"""
        interval = 30.0  # Health check every 30 seconds

        while self.state in (PluginState.STARTING, PluginState.RUNNING, PluginState.UNHEALTHY):
            try:
                await asyncio.sleep(interval)

                # Check if process is alive
                if not self.is_alive():
                    logger.error(f"Plugin {self.plugin_name} process died")
                    self._set_state(PluginState.CRASHED)
                    # Note: _monitor_subprocess() will handle the crash
                    break

                # TODO: Actual health check via EventBus request/reply
                # For now, just check process alive status

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for {self.plugin_name}: {e}")

    async def _handle_crash(self, exit_code: int) -> None:
        """
        Handle plugin crash and publish crash event.
        
        Args:
            exit_code: Exit code of crashed process
        """
        crash_event = {
            "plugin": self.plugin_name,
            "pid": self.pid,
            "exit_code": exit_code,
            "timestamp": time.time(),
            "restart_attempts": len(self.restart_attempts)
        }
        
        # Publish crash event
        subject = f"rosey.plugin.{self.plugin_name}.crashed"
        try:
            await self.event_bus.publish(subject, json.dumps(crash_event).encode())
        except Exception as e:
            logger.error(f"Failed to publish crash event: {e}")
        
        logger.error(f"Plugin {self.plugin_name} crash: {crash_event}")

    async def _attempt_restart(self) -> bool:
        """
        Attempt to restart plugin with exponential backoff.
        
        Returns:
            bool: True if restarted, False if gave up
        """
        attempt_count = len(self.restart_attempts)
        
        # Check if exceeded max attempts
        if attempt_count >= self.restart_config.max_attempts:
            logger.error(
                f"Plugin {self.plugin_name} exceeded max restart attempts "
                f"({self.restart_config.max_attempts}), giving up"
            )
            self._set_state(PluginState.FAILED)
            return False
        
        # Calculate backoff
        delay = self._calculate_backoff(attempt_count)
        
        if delay > 0:
            logger.info(
                f"Restarting plugin {self.plugin_name} in {delay}s "
                f"(attempt {attempt_count + 1}/{self.restart_config.max_attempts})"
            )
            await asyncio.sleep(delay)
        else:
            logger.info(
                f"Restarting plugin {self.plugin_name} immediately "
                f"(attempt {attempt_count + 1}/{self.restart_config.max_attempts})"
            )
        
        # Record attempt
        attempt = RestartAttempt(
            timestamp=time.time(),
            success=False,
            exit_code=self.process.exitcode if self.process else None,
            signal=None
        )
        self.restart_attempts.append(attempt)
        
        # Attempt restart
        success = await self.restart()
        attempt.success = success
        
        if success:
            logger.info(f"Plugin {self.plugin_name} restart successful")
            # Reset attempts after successful restart
            asyncio.create_task(self._reset_attempts_after_success())
        else:
            logger.error(f"Plugin {self.plugin_name} restart failed")
        
        return success

    async def _reset_attempts_after_success(self) -> None:
        """
        Reset restart attempt counter after sustained success.
        Waits for reset_window before clearing attempts.
        """
        await asyncio.sleep(self.restart_config.reset_window)
        
        # If still running, clear attempts
        if self.state == PluginState.RUNNING:
            logger.info(f"Plugin {self.plugin_name} stable, resetting restart attempts")
            self.restart_attempts.clear()

    # ========================================================================
    # Resource Monitoring (Sortie 4)
    # ========================================================================

    async def _start_resource_monitoring(self) -> None:
        """Start monitoring plugin resource usage"""
        if not self.resource_limits:
            logger.debug(f"No resource limits for plugin {self.plugin_name}")
            return
        
        if not psutil:
            logger.warning(f"psutil not available, resource monitoring disabled for {self.plugin_name}")
            return
        
        # Create resource monitor
        self.resource_monitor = ResourceMonitor(
            self.pid,
            limits=self.resource_limits,
            sample_interval=self.resource_limits.check_interval
        )
        
        # Initialize stats
        self.resource_stats = ResourceStats(
            current_cpu_percent=0.0,
            current_memory_mb=0.0,
            peak_cpu_percent=0.0,
            peak_memory_mb=0.0,
            total_checks=0,
            violations=0,
            last_check=time.time()
        )
        
        # Start monitoring task
        self._resource_task = asyncio.create_task(self._monitor_resources())
        
        logger.info(
            f"Started resource monitoring for {self.plugin_name} "
            f"(CPU: {self.resource_limits.max_cpu_percent}%, "
            f"Memory: {self.resource_limits.max_memory_mb}MB)"
        )

    async def _monitor_resources(self) -> None:
        """Monitor plugin resource usage periodically"""
        consecutive_violations = 0
        
        while self.state == PluginState.RUNNING:
            try:
                await asyncio.sleep(self.resource_limits.check_interval)
                
                # Get current usage
                usage = await self.resource_monitor.get_current_usage()
                if not usage:
                    # Process died
                    break
                
                # Update stats
                self.resource_stats.current_cpu_percent = usage.cpu_percent
                self.resource_stats.current_memory_mb = usage.memory_mb
                self.resource_stats.peak_cpu_percent = max(
                    self.resource_stats.peak_cpu_percent,
                    usage.cpu_percent
                )
                self.resource_stats.peak_memory_mb = max(
                    self.resource_stats.peak_memory_mb,
                    usage.memory_mb
                )
                self.resource_stats.total_checks += 1
                self.resource_stats.last_check = time.time()
                
                # Publish resource event
                await self._publish_resource_event()
                
                # Check limits
                violations = self.resource_monitor.check_limits(usage)
                
                if violations:
                    consecutive_violations += 1
                    self.resource_stats.violations += 1
                    
                    violation_str = ", ".join(violations)
                    logger.warning(
                        f"Plugin {self.plugin_name} resource violation "
                        f"({consecutive_violations}/{self.resource_limits.violation_threshold}): "
                        f"{violation_str}"
                    )
                    
                    # Kill if threshold exceeded
                    if consecutive_violations >= self.resource_limits.violation_threshold:
                        logger.error(
                            f"Plugin {self.plugin_name} exceeded resource limits, killing"
                        )
                        await self._kill_for_resource_violation(violation_str)
                        break
                else:
                    consecutive_violations = 0  # Reset on success
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitoring error for {self.plugin_name}: {e}")

    async def _publish_resource_event(self) -> None:
        """Publish current resource usage to NATS"""
        event = {
            "plugin": self.plugin_name,
            "pid": self.pid,
            "cpu_percent": self.resource_stats.current_cpu_percent,
            "memory_mb": self.resource_stats.current_memory_mb,
            "peak_cpu_percent": self.resource_stats.peak_cpu_percent,
            "peak_memory_mb": self.resource_stats.peak_memory_mb,
            "timestamp": time.time()
        }
        
        subject = f"rosey.plugin.{self.plugin_name}.resources"
        try:
            await self.event_bus.publish(subject, json.dumps(event).encode())
        except Exception as e:
            logger.error(f"Failed to publish resource event: {e}")

    async def _kill_for_resource_violation(self, reason: str) -> None:
        """
        Kill plugin for exceeding resource limits.
        
        Args:
            reason: Description of violation
        """
        violation_event = {
            "plugin": self.plugin_name,
            "pid": self.pid,
            "reason": reason,
            "cpu_percent": self.resource_stats.current_cpu_percent,
            "memory_mb": self.resource_stats.current_memory_mb,
            "timestamp": time.time()
        }
        
        # Publish violation event
        subject = f"rosey.plugin.{self.plugin_name}.resource_violation"
        try:
            await self.event_bus.publish(subject, json.dumps(violation_event).encode())
        except Exception as e:
            logger.error(f"Failed to publish violation event: {e}")
        
        logger.error(
            f"Killing plugin {self.plugin_name} for resource violation: {reason}"
        )
        
        # Force kill (don't wait for graceful shutdown)
        if self.process and self.process.is_alive():
            self.process.kill()
            await asyncio.to_thread(self.process.join, 2.0)
        
        self._set_state(PluginState.FAILED)
        
        # Crash recovery will restart plugin if enabled

    # ========================================================================
    # State Management
    # ========================================================================

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            float: Delay in seconds (0 for first attempt)
        """
        if attempt == 0:
            return 0.0  # First restart immediate
        
        # Exponential: initial_delay * multiplier^(attempt-1)
        delay = self.restart_config.initial_delay * (
            self.restart_config.backoff_multiplier ** (attempt - 1)
        )
        
        # Cap at max_delay
        return min(delay, self.restart_config.max_delay)

    def _set_state(self, new_state: PluginState) -> None:
        """Update plugin state and notify callbacks"""
        old_state = self.state
        self.state = new_state

        logger.debug(f"Plugin {self.plugin_name} state: {old_state} -> {new_state}")

        for callback in self._callbacks["state_change"]:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

    def _on_resource_update(self, usage: ResourceUsage) -> None:
        """Handle resource usage update"""
        if self.monitor:
            violations = self.monitor.check_limits(usage)
            if violations:
                for callback in self._callbacks["resource_violation"]:
                    try:
                        callback(usage, violations)
                    except Exception as e:
                        logger.error(f"Resource violation callback error: {e}")

    def add_callback(self, event: str, callback: Callable) -> None:
        """Add event callback"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
