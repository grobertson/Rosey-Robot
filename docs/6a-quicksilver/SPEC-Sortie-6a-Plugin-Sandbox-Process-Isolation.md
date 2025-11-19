# Sortie 6a: Plugin Sandbox - Process Isolation

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐⭐☆ (Security & Process Management)  
**Estimated Time:** 4-5 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 2 (EventBus), Sortie 3 (Subjects)

---

## Objective

Implement basic plugin process isolation using Python subprocesses, enabling plugins to run in separate processes with NATS-only communication, crash isolation, and resource monitoring.

This is the **foundation layer** for plugin security. Subsequent sorties will add:
- 6b: Permission system and capability grants
- 6c: State management and thread context
- 6d: File generation and attachment handling
- 6e: External API gateway

---

## Core Requirements

1. **Process Isolation**: Each plugin runs in separate subprocess
2. **NATS-Only Communication**: Plugin communicates exclusively via NATS (no direct bot access)
3. **Crash Isolation**: Plugin crash doesn't affect bot or other plugins
4. **Resource Monitoring**: Track CPU, memory per plugin
5. **Clean Lifecycle**: Start, stop, restart plugins cleanly
6. **Developer Experience**: Simple interface for plugin authors

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Bot Core Process                     │
│  ┌────────────────┐         ┌──────────────┐               │
│  │  Core Router   │◄────────┤  EventBus    │               │
│  └────────────────┘         └──────▲───────┘               │
└─────────────────────────────────────┼───────────────────────┘
                                      │
                        ┌─────────────┴──────────────┐
                        │      NATS Message Broker    │
                        └─────────────┬──────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────┐
        │                             │                          │
┌───────▼─────────┐          ┌────────▼────────┐      ┌────────▼────────┐
│ Plugin Process  │          │ Plugin Process  │      │ Plugin Process  │
│  (Trivia)       │          │  (Markov)       │      │  (Calendar)     │
│                 │          │                 │      │                 │
│ PluginInterface │          │ PluginInterface │      │ PluginInterface │
│      │          │          │      │          │      │      │          │
│      └──────────┤          │      └──────────┤      │      └──────────┤
│   EventBus Conn │          │   EventBus Conn │      │   EventBus Conn │
└─────────────────┘          └─────────────────┘      └─────────────────┘

Each plugin:
- Separate Python process (subprocess.Popen)
- Own NATS connection
- Isolated memory space
- Can crash without affecting others
```

---

## Design Decisions

### Why Subprocesses? (Not Threads or Containers)

**Considered Approaches:**

1. **Threads** ❌
   - Share memory space (not isolated)
   - Python GIL limits parallelism
   - One plugin crash can corrupt shared state

2. **Multiprocessing** ✅ (CHOSEN)
   - True isolation (separate memory)
   - Cross-platform (Windows, Linux, Mac)
   - Standard library (no dependencies)
   - Easy resource monitoring
   - Plugin crashes contained

3. **Docker Containers** 🤔 (Future consideration)
   - Strongest isolation
   - More complex deployment
   - Requires Docker runtime
   - Good for production, overkill for development
   - Consider for Sortie 6f (production hardening)

**Decision:** Start with subprocesses, design API to allow container backend later.

### Communication Model

**Plugin ↔ Bot communication happens ONLY via NATS:**

```python
# Plugin CANNOT do this:
from bot.rosey.core import some_module  # ❌ No direct imports

# Plugin CAN do this:
await self.nats.publish("rosey.plugins.myplugin.result", data)  # ✅
```

This enforces:
- Clear API boundaries
- Easy to audit communication
- Simple to add network isolation later
- Plugins are naturally distributed-systems-ready

---

## Technical Tasks

### Task 6a.1: Plugin Interface Base Class

**File:** `bot/rosey/plugins/plugin_interface.py`

```python
"""
Plugin interface base class
All plugins inherit from PluginInterface
"""
import asyncio
import logging
import sys
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from bot.rosey.core.event_bus import EventBus
from bot.rosey.core.subjects import Subjects
from bot.rosey.core.events import Event

logger = logging.getLogger(__name__)


class PluginInterface(ABC):
    """
    Base class for all Rosey plugins
    
    Plugins run in separate processes and communicate via NATS.
    
    Minimal example:
    
        class MyPlugin(PluginInterface):
            @property
            def plugin_name(self) -> str:
                return "myplugin"
            
            async def handle_command(self, event: Event):
                command_data = event.data
                result = {"message": "Command executed!"}
                await self.publish_result(result, event.correlation_id)
    
    Full lifecycle:
        1. Plugin process starts
        2. __init__ called (setup state)
        3. connect() called (connect to NATS)
        4. on_start() called (plugin initialization)
        5. run() called (event loop, blocking)
        6. on_stop() called on shutdown
        7. disconnect() called
    """
    
    def __init__(self, nats_url: str = None, nats_token: str = None):
        """
        Initialize plugin
        
        Args:
            nats_url: NATS server URL
            nats_token: NATS auth token
        """
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.nats_token = nats_token or os.getenv("NATS_TOKEN")
        
        self.event_bus: Optional[EventBus] = None
        self._running = False
        self._command_queue = asyncio.Queue()
    
    # ========== Abstract Methods (Plugin Author Implements) ==========
    
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """
        Plugin identifier (used in NATS subjects)
        
        Must be lowercase, alphanumeric + underscores only.
        Examples: 'trivia', 'markov', 'calendar_manager'
        """
        pass
    
    @abstractmethod
    async def handle_command(self, event: Event):
        """
        Handle command execution
        
        Called when command arrives on: rosey.commands.{plugin_name}.execute
        
        Args:
            event: Command event with data, user context, etc.
        
        Plugin should:
        1. Process command
        2. Call self.publish_result() with response
        3. Or call self.publish_error() if error
        
        Example:
            async def handle_command(self, event: Event):
                data = event.data
                action = data.get("action")
                
                if action == "start":
                    result = await self.start_game()
                    await self.publish_result(result, event.correlation_id)
                else:
                    await self.publish_error(
                        "Unknown action", 
                        event.correlation_id
                    )
        """
        pass
    
    # ========== Optional Lifecycle Hooks ==========
    
    async def on_start(self):
        """
        Called after NATS connection established, before run()
        
        Override to initialize plugin state, load data, etc.
        
        Example:
            async def on_start(self):
                self.game_state = {}
                await self.load_questions_from_db()
        """
        pass
    
    async def on_stop(self):
        """
        Called before shutdown
        
        Override to cleanup resources, save state, etc.
        
        Example:
            async def on_stop(self):
                await self.save_state_to_db()
                await self.cleanup_temp_files()
        """
        pass
    
    async def on_event(self, event: Event):
        """
        Called for any non-command event plugin subscribes to
        
        Override to handle generic events (user join, messages, etc.)
        
        Example:
            async def on_event(self, event: Event):
                if event.event_type == "user_join":
                    username = event.data.get("user", {}).get("username")
                    await self.welcome_user(username)
        """
        pass
    
    # ========== NATS Connection Management ==========
    
    async def connect(self):
        """
        Connect to NATS event bus
        
        Called automatically by run(). Plugin authors don't need to call this.
        """
        logger.info(f"Plugin '{self.plugin_name}' connecting to NATS: {self.nats_url}")
        
        self.event_bus = EventBus(
            servers=[self.nats_url],
            token=self.nats_token,
            name=f"plugin-{self.plugin_name}"
        )
        
        await self.event_bus.connect()
        
        # Subscribe to plugin's command subject
        command_subject = Subjects.plugin_command(self.plugin_name, "execute")
        await self.event_bus.subscribe(command_subject, self._handle_command_wrapper)
        
        logger.info(f"Plugin '{self.plugin_name}' connected and subscribed to {command_subject}")
    
    async def disconnect(self):
        """Disconnect from NATS"""
        if self.event_bus:
            await self.event_bus.disconnect()
            logger.info(f"Plugin '{self.plugin_name}' disconnected")
    
    # ========== Command Handling (Internal) ==========
    
    async def _handle_command_wrapper(self, event: Event):
        """
        Internal wrapper for command handling
        
        Adds error handling and logging around plugin's handle_command()
        """
        try:
            logger.info(f"Plugin '{self.plugin_name}' received command: {event.correlation_id}")
            await self.handle_command(event)
        except Exception as e:
            logger.error(f"Plugin '{self.plugin_name}' command error: {e}", exc_info=True)
            await self.publish_error(str(e), event.correlation_id)
    
    # ========== Publishing Methods (For Plugin Authors) ==========
    
    async def publish_result(
        self, 
        data: Dict[str, Any], 
        correlation_id: str = None,
        response_channel: Dict[str, Any] = None
    ):
        """
        Publish command result
        
        Publishes to: rosey.commands.{plugin_name}.result
        
        Args:
            data: Result data (must contain 'message' or 'text' for chat response)
            correlation_id: Links response to request
            response_channel: Override response destination
        
        Example:
            await self.publish_result({
                "message": "Game started! First question: What is 2+2?",
                "game_id": 123
            }, event.correlation_id)
        """
        subject = Subjects.plugin_command(self.plugin_name, "result")
        
        payload = {
            **data,
            "correlation_id": correlation_id
        }
        
        if response_channel:
            payload["response_channel"] = response_channel
        
        await self.event_bus.publish(
            subject,
            data=payload,
            source=f"plugin-{self.plugin_name}",
            correlation_id=correlation_id
        )
        
        logger.debug(f"Plugin '{self.plugin_name}' published result")
    
    async def publish_error(
        self, 
        error_message: str, 
        correlation_id: str = None
    ):
        """
        Publish error
        
        Publishes to: rosey.commands.{plugin_name}.error
        
        Args:
            error_message: Error description
            correlation_id: Links to original request
        """
        subject = Subjects.plugin_command(self.plugin_name, "error")
        
        await self.event_bus.publish(
            subject,
            data={"error": error_message},
            source=f"plugin-{self.plugin_name}",
            correlation_id=correlation_id
        )
        
        logger.error(f"Plugin '{self.plugin_name}' published error: {error_message}")
    
    async def publish_event(self, event_name: str, data: Dict[str, Any]):
        """
        Publish plugin-specific event
        
        Publishes to: rosey.plugins.{plugin_name}.{event_name}
        
        Args:
            event_name: Event identifier (e.g., 'game_started', 'user_scored')
            data: Event data
        
        Example:
            await self.publish_event("game_started", {
                "game_id": 123,
                "players": ["Alice", "Bob"]
            })
        """
        subject = Subjects.plugin_event(self.plugin_name, event_name)
        
        await self.event_bus.publish(
            subject,
            data=data,
            source=f"plugin-{self.plugin_name}"
        )
    
    # ========== Subscription Helpers ==========
    
    async def subscribe_to_events(self, event_types: List[str] = None):
        """
        Subscribe to normalized events
        
        Args:
            event_types: Specific event types (e.g., ['message', 'user_join'])
                        If None, subscribes to all events
        
        Events will be delivered to self.on_event()
        
        Example:
            await self.subscribe_to_events(['user_join', 'user_leave'])
        """
        if event_types:
            for event_type in event_types:
                subject = f"{Subjects.EVENTS}.{event_type}"
                await self.event_bus.subscribe(subject, self.on_event)
                logger.info(f"Plugin '{self.plugin_name}' subscribed to {subject}")
        else:
            subject = Subjects.EVENTS_ALL
            await self.event_bus.subscribe(subject, self.on_event)
            logger.info(f"Plugin '{self.plugin_name}' subscribed to all events")
    
    # ========== Main Run Loop ==========
    
    async def run(self):
        """
        Main plugin loop (blocking)
        
        Called by plugin runner. Handles full lifecycle:
        1. Connect to NATS
        2. Call on_start()
        3. Keep alive until stopped
        4. Call on_stop()
        5. Disconnect
        """
        try:
            # Connect
            await self.connect()
            
            # Initialize
            await self.on_start()
            
            # Publish started event
            await self.publish_event("started", {
                "plugin_name": self.plugin_name,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            logger.info(f"Plugin '{self.plugin_name}' running")
            self._running = True
            
            # Keep alive
            while self._running:
                await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            logger.info(f"Plugin '{self.plugin_name}' received interrupt")
        
        except Exception as e:
            logger.error(f"Plugin '{self.plugin_name}' fatal error: {e}", exc_info=True)
            await self.publish_event("error", {"error": str(e)})
        
        finally:
            # Cleanup
            logger.info(f"Plugin '{self.plugin_name}' stopping")
            
            await self.on_stop()
            await self.publish_event("stopped", {
                "plugin_name": self.plugin_name
            })
            await self.disconnect()
    
    def stop(self):
        """
        Stop plugin
        
        Called externally (e.g., by plugin manager) to trigger shutdown
        """
        logger.info(f"Plugin '{self.plugin_name}' stop requested")
        self._running = False


# ========== Plugin Entry Point Helper ==========

def run_plugin(plugin_class, **kwargs):
    """
    Entry point helper for plugin scripts
    
    Usage in plugin file:
        if __name__ == "__main__":
            run_plugin(MyPlugin)
    """
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s - {plugin_class.__name__} - %(levelname)s - %(message)s'
    )
    
    # Create and run plugin
    plugin = plugin_class(**kwargs)
    
    try:
        asyncio.run(plugin.run())
    except KeyboardInterrupt:
        logger.info(f"Plugin {plugin.plugin_name} interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Plugin {plugin.plugin_name} failed: {e}", exc_info=True)
        sys.exit(1)
```

---

### Task 6a.2: Simple Example Plugin

**File:** `bot/rosey/plugins/examples/echo_plugin.py`

```python
"""
Echo plugin - Simple example demonstrating PluginInterface

Responds to any command by echoing it back
"""
from bot.rosey.plugins.plugin_interface import PluginInterface, run_plugin
from bot.rosey.core.events import Event


class EchoPlugin(PluginInterface):
    """
    Echo plugin - Repeats commands back to user
    
    Usage:
        !echo hello world
        -> Bot: "Echo: hello world"
    """
    
    @property
    def plugin_name(self) -> str:
        return "echo"
    
    async def on_start(self):
        """Initialize plugin"""
        print(f"🔊 Echo plugin starting...")
        self.echo_count = 0
    
    async def handle_command(self, event: Event):
        """
        Handle echo command
        
        Takes any input and echoes it back
        """
        data = event.data
        args = data.get("args", [])
        
        # Increment counter
        self.echo_count += 1
        
        # Build echo message
        if args:
            echo_text = " ".join(args)
            message = f"🔊 Echo #{self.echo_count}: {echo_text}"
        else:
            message = "🔊 Echo: (nothing to echo)"
        
        # Send response
        await self.publish_result({
            "message": message,
            "count": self.echo_count
        }, event.correlation_id)
    
    async def on_stop(self):
        """Cleanup on shutdown"""
        print(f"🔊 Echo plugin stopping... (echoed {self.echo_count} messages)")


if __name__ == "__main__":
    run_plugin(EchoPlugin)
```

---

### Task 6a.3: Plugin Process Runner

**File:** `bot/rosey/plugins/plugin_runner.py`

```python
"""
Plugin process runner
Manages plugin as subprocess with monitoring
"""
import asyncio
import logging
import subprocess
import sys
import os
import signal
import psutil
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginProcess:
    """
    Manages a single plugin as subprocess
    
    Responsibilities:
    - Start plugin in separate process
    - Monitor resource usage (CPU, memory)
    - Detect crashes and report
    - Clean shutdown
    
    Example:
        runner = PluginProcess("trivia", "plugins/trivia/trivia_plugin.py")
        await runner.start()
        
        # Monitor
        stats = runner.get_stats()
        print(f"CPU: {stats['cpu_percent']}%")
        
        await runner.stop()
    """
    
    def __init__(
        self,
        plugin_name: str,
        plugin_path: str,
        nats_url: str = None,
        nats_token: str = None,
        python_executable: str = None
    ):
        """
        Initialize plugin runner
        
        Args:
            plugin_name: Plugin identifier
            plugin_path: Path to plugin .py file
            nats_url: NATS server URL
            nats_token: NATS token
            python_executable: Python interpreter (default: sys.executable)
        """
        self.plugin_name = plugin_name
        self.plugin_path = Path(plugin_path)
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.nats_token = nats_token or os.getenv("NATS_TOKEN")
        self.python_executable = python_executable or sys.executable
        
        self.process: Optional[subprocess.Popen] = None
        self.psutil_process: Optional[psutil.Process] = None
        self._start_time = None
    
    async def start(self):
        """
        Start plugin subprocess
        
        Raises:
            FileNotFoundError: If plugin file doesn't exist
            RuntimeError: If plugin already running
        """
        if self.is_running():
            raise RuntimeError(f"Plugin '{self.plugin_name}' already running")
        
        if not self.plugin_path.exists():
            raise FileNotFoundError(f"Plugin file not found: {self.plugin_path}")
        
        logger.info(f"Starting plugin '{self.plugin_name}' from {self.plugin_path}")
        
        # Build environment
        env = os.environ.copy()
        env["NATS_URL"] = self.nats_url
        if self.nats_token:
            env["NATS_TOKEN"] = self.nats_token
        
        # Start subprocess
        self.process = subprocess.Popen(
            [self.python_executable, str(self.plugin_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Wrap with psutil for monitoring
        self.psutil_process = psutil.Process(self.process.pid)
        self._start_time = asyncio.get_event_loop().time()
        
        logger.info(f"Plugin '{self.plugin_name}' started (PID: {self.process.pid})")
        
        # Give it a moment to crash if there's an immediate error
        await asyncio.sleep(0.5)
        
        if not self.is_running():
            # Grab any error output
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"Plugin '{self.plugin_name}' failed to start: {stderr}")
    
    async def stop(self, timeout: float = 5.0):
        """
        Stop plugin gracefully
        
        Args:
            timeout: Seconds to wait before force kill
        """
        if not self.is_running():
            logger.warning(f"Plugin '{self.plugin_name}' not running")
            return
        
        logger.info(f"Stopping plugin '{self.plugin_name}' (PID: {self.process.pid})")
        
        try:
            # Send SIGTERM (or CTRL_BREAK_EVENT on Windows)
            if sys.platform == "win32":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=timeout)
                logger.info(f"Plugin '{self.plugin_name}' stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill
                logger.warning(f"Plugin '{self.plugin_name}' didn't stop, killing")
                self.process.kill()
                self.process.wait()
        
        except Exception as e:
            logger.error(f"Error stopping plugin '{self.plugin_name}': {e}")
        
        finally:
            self.process = None
            self.psutil_process = None
    
    def is_running(self) -> bool:
        """Check if plugin process is running"""
        if self.process is None:
            return False
        
        return self.process.poll() is None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get plugin resource usage statistics
        
        Returns:
            Dict with CPU%, memory, uptime, etc.
        """
        if not self.is_running() or not self.psutil_process:
            return {
                "running": False,
                "pid": None
            }
        
        try:
            # Get CPU and memory
            cpu_percent = self.psutil_process.cpu_percent(interval=0.1)
            memory_info = self.psutil_process.memory_info()
            
            # Calculate uptime
            uptime = asyncio.get_event_loop().time() - self._start_time if self._start_time else 0
            
            return {
                "running": True,
                "pid": self.process.pid,
                "cpu_percent": cpu_percent,
                "memory_mb": memory_info.rss / (1024 * 1024),  # Convert to MB
                "memory_percent": self.psutil_process.memory_percent(),
                "uptime_seconds": uptime,
                "num_threads": self.psutil_process.num_threads()
            }
        
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error getting stats for '{self.plugin_name}': {e}")
            return {"running": False, "error": str(e)}
    
    async def get_output(self, lines: int = 10) -> Dict[str, str]:
        """
        Get recent stdout/stderr from plugin
        
        Args:
            lines: Number of lines to retrieve
        
        Returns:
            Dict with 'stdout' and 'stderr' keys
        """
        if not self.process:
            return {"stdout": "", "stderr": ""}
        
        # This is basic - for production, consider using asyncio subprocess
        # or a logging aggregator
        
        return {
            "stdout": "(output capture not implemented in basic version)",
            "stderr": "(error capture not implemented in basic version)"
        }
```

---

### Task 6a.4: Basic Plugin Registry

**File:** `bot/rosey/plugins/plugin_registry.py`

```python
"""
Plugin registry - Tracks available plugins
"""
from typing import Dict, List
from pathlib import Path
import importlib.util
import logging

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Registry of available plugins
    
    Discovers plugins from plugins directory
    """
    
    def __init__(self, plugins_dir: str = None):
        """
        Initialize registry
        
        Args:
            plugins_dir: Directory containing plugins
        """
        self.plugins_dir = Path(plugins_dir or "bot/rosey/plugins")
        self.plugins: Dict[str, Dict] = {}
    
    def discover(self):
        """
        Discover plugins in plugins directory
        
        Looks for Python files with PluginInterface subclass
        """
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return
        
        logger.info(f"Discovering plugins in {self.plugins_dir}")
        
        # Find all .py files (excluding __init__ and examples)
        for py_file in self.plugins_dir.rglob("*.py"):
            if py_file.name.startswith("_") or "examples" in py_file.parts:
                continue
            
            try:
                # Load module
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find PluginInterface subclasses
                    from bot.rosey.plugins.plugin_interface import PluginInterface
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, PluginInterface) and 
                            attr is not PluginInterface):
                            
                            # Found a plugin!
                            plugin_class = attr
                            
                            # Get plugin name (instantiate temporarily)
                            try:
                                instance = plugin_class()
                                plugin_name = instance.plugin_name
                                
                                self.plugins[plugin_name] = {
                                    "name": plugin_name,
                                    "class": plugin_class,
                                    "file": str(py_file),
                                    "module": module.__name__
                                }
                                
                                logger.info(f"Discovered plugin: {plugin_name} ({py_file.name})")
                            except Exception as e:
                                logger.error(f"Error instantiating {attr_name}: {e}")
            
            except Exception as e:
                logger.error(f"Error loading {py_file}: {e}")
        
        logger.info(f"Discovered {len(self.plugins)} plugins")
    
    def get_plugin(self, name: str) -> Dict:
        """Get plugin info by name"""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all plugin names"""
        return list(self.plugins.keys())
```

---

## Testing

### Task 6a.5: Integration Test

**File:** `tests/plugins/test_plugin_runner.py`

```python
"""
Integration tests for plugin process runner
"""
import pytest
import asyncio
from pathlib import Path

from bot.rosey.plugins.plugin_runner import PluginProcess
from bot.rosey.core.event_bus import initialize_event_bus, shutdown_event_bus
from bot.rosey.core.subjects import Subjects


@pytest.fixture
async def event_bus():
    """Setup event bus for testing"""
    bus = await initialize_event_bus()
    yield bus
    await shutdown_event_bus()


@pytest.mark.asyncio
async def test_plugin_start_stop(event_bus):
    """Test starting and stopping plugin process"""
    
    # Path to echo plugin
    plugin_path = Path("bot/rosey/plugins/examples/echo_plugin.py")
    
    if not plugin_path.exists():
        pytest.skip(f"Plugin not found: {plugin_path}")
    
    # Create runner
    runner = PluginProcess("echo", str(plugin_path))
    
    # Start
    await runner.start()
    assert runner.is_running()
    
    # Check stats
    stats = runner.get_stats()
    assert stats["running"] is True
    assert stats["pid"] is not None
    assert stats["memory_mb"] > 0
    
    # Wait a moment
    await asyncio.sleep(1)
    
    # Stop
    await runner.stop()
    assert not runner.is_running()


@pytest.mark.asyncio
async def test_plugin_receives_command(event_bus):
    """Test plugin receives and responds to command"""
    
    plugin_path = Path("bot/rosey/plugins/examples/echo_plugin.py")
    if not plugin_path.exists():
        pytest.skip(f"Plugin not found: {plugin_path}")
    
    # Start plugin
    runner = PluginProcess("echo", str(plugin_path))
    await runner.start()
    
    try:
        # Give plugin time to connect
        await asyncio.sleep(2)
        
        # Setup result listener
        results = []
        
        async def result_handler(event):
            results.append(event)
        
        await event_bus.subscribe(
            Subjects.plugin_command("echo", "result"),
            result_handler
        )
        
        # Send command
        await event_bus.publish(
            Subjects.plugin_command("echo", "execute"),
            data={"args": ["hello", "world"]},
            source="test"
        )
        
        # Wait for response
        await asyncio.sleep(1)
        
        # Check result
        assert len(results) > 0
        result = results[0]
        assert "hello world" in result.data.get("message", "").lower()
    
    finally:
        await runner.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Documentation

**File:** `docs/plugins/PLUGIN-DEVELOPMENT.md`

```markdown
# Plugin Development Guide

## Quick Start

### 1. Create Plugin File

```python
# bot/rosey/plugins/my_plugin.py

from bot.rosey.plugins.plugin_interface import PluginInterface, run_plugin
from bot.rosey.core.events import Event


class MyPlugin(PluginInterface):
    @property
    def plugin_name(self) -> str:
        return "myplugin"
    
    async def handle_command(self, event: Event):
        # Command logic here
        data = event.data
        args = data.get("args", [])
        
        result = {"message": f"Received: {args}"}
        await self.publish_result(result, event.correlation_id)


if __name__ == "__main__":
    run_plugin(MyPlugin)
```

### 2. Test Locally

```bash
# Terminal 1: Start NATS
cd infrastructure/nats
./start-nats.bat

# Terminal 2: Start bot core
python -m bot.rosey.main

# Terminal 3: Start your plugin
python bot/rosey/plugins/my_plugin.py

# Terminal 4: Test via chat
# In Cytube: !myplugin test args
```

## Plugin Interface

### Lifecycle

```python
__init__()              # Setup
connect()               # Connect to NATS (automatic)
on_start()              # Initialize (override)
run()                   # Main loop (automatic)
  └─ handle_command()   # Your logic (override)
on_stop()               # Cleanup (override)
disconnect()            # Disconnect (automatic)
```

### Publishing Responses

```python
# Command result (goes back to user)
await self.publish_result({
    "message": "Hello!"
}, event.correlation_id)

# Plugin event (for monitoring/other plugins)
await self.publish_event("custom_event", {
    "data": "value"
})

# Error
await self.publish_error("Something went wrong", event.correlation_id)
```

### Subscribing to Events

```python
async def on_start(self):
    # Subscribe to user joins
    await self.subscribe_to_events(['user_join'])

async def on_event(self, event: Event):
    if event.event_type == "user_join":
        username = event.data.get("user", {}).get("username")
        # Do something with user join
```

## Best Practices

1. **Keep plugins focused** - One responsibility per plugin
2. **Handle errors** - Use try/except in handle_command()
3. **Log appropriately** - Use logger for debugging
4. **Test independently** - Plugin should work standalone
5. **Document commands** - Clear help text for users

## Security Notes

- Plugins run in separate processes (isolated)
- Can ONLY communicate via NATS
- Cannot import bot core modules
- Cannot access filesystem (future: restricted)
- Cannot make network calls (future: gateway only)
```

---

## Success Criteria

✅ PluginInterface base class implemented  
✅ Example plugin (echo) working  
✅ PluginProcess runner managing subprocess  
✅ Resource monitoring functional (CPU, memory)  
✅ Crash isolation verified  
✅ Plugin registry discovering plugins  
✅ Integration tests passing  
✅ Documentation complete  

---

## Time Breakdown

- PluginInterface design & implementation: 2 hours
- PluginProcess runner: 1.5 hours
- Example plugin & testing: 1 hour
- Documentation: 30 minutes

**Total: 5 hours**

---

## Next Steps

### Sortie 6b: Permission System (Next)
- Subject-based allowlists (what plugins can subscribe/publish to)
- Resource limits enforcement (max CPU, memory)
- Capability grants (filesystem, network, external APIs)

### Sortie 6c: State & Context Management
- Persistent storage for plugins (key-value store)
- Thread context handling (Slack threads, Discord replies)
- Multi-message workflows

### Sortie 6d: File & Attachment Handling
- File generation (ICS, PDF, CSV)
- Upload to platforms
- Temporary storage cleanup

### Sortie 6e: External API Gateway
- Controlled external API access
- OAuth token management
- Rate limiting per plugin

---

## Notes for Implementation

**Key Design Principles:**

1. **Fail-Safe**: Plugin crash doesn't affect bot
2. **Observable**: Easy to monitor plugin health
3. **Simple API**: Plugin authors need minimal boilerplate
4. **Platform-Agnostic**: Same plugin works on Cytube, Slack, Discord

**Known Limitations (to address in future sorties):**

- No permission enforcement yet (all plugins can subscribe to anything)
- No resource limits (plugin can consume unlimited CPU/memory)
- No filesystem isolation (plugin has full filesystem access)
- No state persistence (plugin loses state on restart)
- Stdout/stderr capture is basic (need better logging)

**Production Considerations (Sortie 6f+):**

- Consider Docker containers for stronger isolation
- Implement proper log aggregation
- Add health check endpoints
- Implement automatic restart on crash
- Add metrics collection (Prometheus?)
