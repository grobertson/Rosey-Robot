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
import logging
import multiprocessing
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timedelta

try:
    import psutil
except ImportError:
    psutil = None

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
    policy: RestartPolicy = RestartPolicy.ON_FAILURE
    max_retries: int = 3  # Maximum restart attempts (-1 for unlimited)
    backoff_seconds: float = 1.0  # Initial backoff delay
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    max_backoff_seconds: float = 60.0  # Maximum backoff delay
    reset_after_seconds: float = 300.0  # Reset retry count after stable run


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
            
            logger.info(f"Plugin {self.plugin_name} started with PID {self.pid}")
            
            # Start resource monitoring
            if psutil:
                self.monitor = ResourceMonitor(
                    self.pid,
                    limits=self.resource_limits,
                    sample_interval=1.0
                )
                self.monitor.add_callback(self._on_resource_update)
                await self.monitor.start_monitoring()
            
            # Start health checking
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            self._set_state(PluginState.RUNNING)
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
            True if stopped successfully
        """
        if self.state == PluginState.STOPPED:
            return True
        
        self._set_state(PluginState.STOPPING)
        logger.info(f"Stopping plugin {self.plugin_name}")
        
        try:
            # Stop health checks
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Stop monitoring
            if self.monitor:
                await self.monitor.stop_monitoring()
            
            # Send shutdown signal
            if self.process and self.process.is_alive():
                # Try graceful shutdown first
                self.process.terminate()
                
                # Wait for graceful shutdown
                start = time.time()
                while self.process.is_alive() and (time.time() - start) < timeout:
                    await asyncio.sleep(0.1)
                
                # Force kill if still alive
                if self.process.is_alive():
                    logger.warning(f"Force killing plugin {self.plugin_name}")
                    self.process.kill()
                    self.process.join(timeout=1.0)
            
            self._set_state(PluginState.STOPPED)
            self.pid = None
            return True
        
        except Exception as e:
            logger.error(f"Error stopping plugin {self.plugin_name}: {e}")
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
    
    def get_uptime(self) -> Optional[float]:
        """Get plugin uptime in seconds"""
        if self._start_time is None:
            return None
        return time.time() - self._start_time
    
    def _run_plugin(self) -> None:
        """
        Plugin subprocess entry point.
        
        This runs in the subprocess. It loads and executes the plugin module.
        """
        # TODO: This is a placeholder. In practice, plugins would:
        # 1. Import their module
        # 2. Connect to EventBus
        # 3. Register command handlers
        # 4. Run event loop
        
        logger.info(f"Plugin {self.plugin_name} subprocess started (PID: {os.getpid()})")
        
        # For now, just sleep to simulate a running plugin
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info(f"Plugin {self.plugin_name} received interrupt")
    
    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        interval = 30.0  # Health check every 30 seconds
        
        while self.state in (PluginState.STARTING, PluginState.RUNNING, PluginState.UNHEALTHY):
            try:
                await asyncio.sleep(interval)
                
                # Check if process is alive
                if not self.is_alive():
                    logger.error(f"Plugin {self.plugin_name} process died")
                    self._set_state(PluginState.CRASHED)
                    await self._handle_crash()
                    break
                
                # TODO: Actual health check via EventBus request/reply
                # For now, just check process alive status
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for {self.plugin_name}: {e}")
    
    async def _handle_crash(self) -> None:
        """Handle plugin crash"""
        logger.error(f"Plugin {self.plugin_name} crashed")
        
        # Check restart policy
        if self._should_restart():
            # Calculate backoff
            backoff = self._calculate_backoff()
            logger.info(f"Restarting {self.plugin_name} in {backoff:.1f}s (attempt {self._restart_count + 1})")
            
            await asyncio.sleep(backoff)
            
            self._restart_count += 1
            self._last_restart = time.time()
            
            await self.restart()
        else:
            logger.warning(f"Not restarting {self.plugin_name} (policy: {self.restart_config.policy})")
    
    def _should_restart(self) -> bool:
        """Check if plugin should restart based on policy"""
        policy = self.restart_config.policy
        
        if policy == RestartPolicy.NEVER:
            return False
        
        if policy == RestartPolicy.ALWAYS:
            return True
        
        if policy in (RestartPolicy.ON_FAILURE, RestartPolicy.UNLESS_STOPPED):
            # Check max retries
            if self.restart_config.max_retries >= 0:
                if self._restart_count >= self.restart_config.max_retries:
                    return False
            
            # Reset count if stable for long enough
            if self._last_restart and self._start_time:
                stable_time = time.time() - self._start_time
                if stable_time >= self.restart_config.reset_after_seconds:
                    self._restart_count = 0
            
            return True
        
        return False
    
    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay"""
        backoff = self.restart_config.backoff_seconds * (
            self.restart_config.backoff_multiplier ** self._restart_count
        )
        return min(backoff, self.restart_config.max_backoff_seconds)
    
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
