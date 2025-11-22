# SPEC: Sortie 3 - Service Management & Hot Reload

**Sprint:** Sprint 12 "Assault on Precinct 13" - Defending the boundaries  
**Sortie:** 3 of 4  
**Version:** 1.0  
**Status:** Planning  
**Estimated Duration:** 8-10 hours  
**Dependencies:** Sortie 1 & 2 MUST be complete (plugin archives + storage isolation)  

---

## Executive Summary

Sortie 3 implements the **unified service management system** with the `rosey` CLI for starting, stopping, and monitoring all bot services (bot core, NATS, database, plugins). Most critically, it enables **hot reload** - installing, updating, and removing plugins without restarting the bot process.

**Core Deliverables**:

1. Service manager (`rosey start/stop/restart/status`)
2. Log aggregation and tailing (`rosey logs [service] -f`)
3. Development mode (`rosey dev` with auto-reload)
4. Plugin hot reload (install/update/remove without bot restart)
5. Process isolation (plugin crashes don't affect bot)
6. Health monitoring and auto-restart

**Success Metric**: Install a plugin while bot is running, see it start immediately. Remove plugin, see graceful shutdown. Bot never restarts.

---

## 1. Problem Statement

### 1.1 Current State (Post-Sortie 2)

**What We Have**:

- ✅ `.roseyplug` archive format
- ✅ Plugin installation (`rosey plugin install`)
- ✅ Isolated storage (per-plugin databases + files)
- ✅ Plugin registry

**What's Missing**:

- ❌ No unified service management
- ❌ Start/stop bot requires manual `python -m lib.bot`
- ❌ NATS server managed separately
- ❌ No log aggregation across services
- ❌ Plugin changes require full bot restart
- ❌ Plugin crashes can crash entire bot
- ❌ No health monitoring or auto-restart

### 1.2 Goals

**Service Management Goals**:

- [x] Unified CLI for all services (bot, NATS, plugins)
- [x] Start/stop individual services or all together
- [x] Service health monitoring (running/stopped/crashed)
- [x] Log aggregation with service filtering
- [x] Development mode with auto-reload

**Hot Reload Goals**:

- [x] Install plugin without bot restart
- [x] Update plugin without bot restart
- [x] Remove plugin without bot restart
- [x] Plugin state preserved during reload
- [x] Zero downtime for bot core

**Process Isolation Goals**:

- [x] Plugin crashes don't affect bot
- [x] Plugin restarts don't affect other plugins
- [x] Graceful shutdown on plugin removal
- [x] Resource cleanup on plugin crash

---

## 2. Technical Design

### 2.1 Architecture Overview

**Service Hierarchy**:

```text
rosey (CLI)
├── ServiceManager
│   ├── BotService (bot core)
│   │   ├── PluginLoader
│   │   │   ├── Plugin: markov-chat (process)
│   │   │   ├── Plugin: quote-bot (process)
│   │   │   └── Plugin: weather-alerts (process)
│   │   └── NATS client (shared)
│   ├── NATSService (NATS server)
│   └── WebService (status dashboard)
└── LogAggregator (collects all logs)
```

**Plugin Hot Reload Architecture**:

```text
┌─────────────────────────────────────────────────────┐
│                   Bot Process                       │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │           PluginLoader                      │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │  Plugin Registry                     │  │  │
│  │  │  {                                   │  │  │
│  │  │    "markov-chat": <Plugin Instance>, │  │  │
│  │  │    "quote-bot": <Plugin Instance>    │  │  │
│  │  │  }                                   │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  │                                             │  │
│  │  Hot Reload Operations:                    │  │
│  │  • load_plugin(name) → start process       │  │
│  │  • unload_plugin(name) → stop gracefully   │  │
│  │  • reload_plugin(name) → unload + load     │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  NATS Client (shared across plugins)               │
└─────────────────────────────────────────────────────┘

Plugin Install → PluginLoader.load_plugin() → Plugin starts
Plugin Remove → PluginLoader.unload_plugin() → Plugin stops
Bot keeps running throughout
```

### 2.2 Directory Structure

**Service Management Files**:

```text
rosey/
├── services/
│   ├── __init__.py
│   ├── manager.py              # NEW - ServiceManager class
│   ├── bot_service.py          # NEW - BotService wrapper
│   ├── nats_service.py         # NEW - NATSService wrapper
│   ├── web_service.py          # NEW - WebService wrapper
│   └── health.py               # NEW - Health monitoring
├── plugin/
│   ├── loader.py               # NEW - PluginLoader (hot reload)
│   ├── process.py              # NEW - Plugin process management
│   └── watcher.py              # NEW - File watcher (dev mode)
└── cli/
    ├── service.py              # NEW - Service commands
    ├── dev.py                  # NEW - Development mode
    └── logs.py                 # NEW - Log aggregation
```

**Log Files**:

```text
logs/
├── rosey.log                   # Combined logs (all services)
├── bot.log                     # Bot core logs
├── nats.log                    # NATS server logs
├── web.log                     # Web dashboard logs
└── plugins/
    ├── markov-chat.log         # Per-plugin logs
    ├── quote-bot.log
    └── weather-alerts.log
```

### 2.3 Component Details

#### Component 1: Service Manager (`rosey/services/manager.py`)

**Responsibilities**:

- Start/stop/restart services
- Track service status (running/stopped/crashed)
- Health monitoring
- Graceful shutdown

**Class Definition**:

```python
"""Unified service management"""
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"
    UNKNOWN = "unknown"


class Service:
    """Base service interface"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = ServiceStatus.STOPPED
        self.process: Optional[asyncio.subprocess.Process] = None
        self.start_time: Optional[float] = None
        self.crash_count = 0
    
    async def start(self) -> bool:
        """Start service"""
        raise NotImplementedError
    
    async def stop(self) -> bool:
        """Stop service gracefully"""
        raise NotImplementedError
    
    async def restart(self) -> bool:
        """Restart service"""
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()
    
    async def health_check(self) -> bool:
        """Check if service is healthy"""
        raise NotImplementedError
    
    def get_status(self) -> Dict[str, any]:
        """Get service status info"""
        return {
            'name': self.name,
            'status': self.status.value,
            'pid': self.process.pid if self.process else None,
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'crash_count': self.crash_count
        }


class ServiceManager:
    """
    Manages all Rosey services.
    
    Services:
    - bot: Bot core with plugin loader
    - nats: NATS server
    - web: Status dashboard (optional)
    """
    
    def __init__(self, data_dir: Path, config: Dict):
        """
        Initialize service manager.
        
        Args:
            data_dir: Base data directory
            config: Bot configuration
        """
        self.data_dir = data_dir
        self.config = config
        self.services: Dict[str, Service] = {}
        
        # Initialize services
        from rosey.services.bot_service import BotService
        from rosey.services.nats_service import NATSService
        from rosey.services.web_service import WebService
        
        self.services['bot'] = BotService(data_dir, config)
        self.services['nats'] = NATSService(data_dir, config)
        self.services['web'] = WebService(data_dir, config)
        
        # Health monitoring
        self._health_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self, services: Optional[List[str]] = None) -> None:
        """
        Start services.
        
        Args:
            services: List of service names (default: all)
        """
        if services is None:
            services = ['nats', 'bot']  # Default: NATS first, then bot
        
        logger.info(f"Starting services: {', '.join(services)}")
        
        for service_name in services:
            if service_name not in self.services:
                logger.error(f"Unknown service: {service_name}")
                continue
            
            service = self.services[service_name]
            
            try:
                logger.info(f"Starting {service_name}...")
                success = await service.start()
                
                if success:
                    logger.info(f"Started {service_name}")
                else:
                    logger.error(f"Failed to start {service_name}")
                    
            except Exception as e:
                logger.error(f"Error starting {service_name}: {e}")
        
        # Start health monitoring
        self._running = True
        self._health_task = asyncio.create_task(self._health_monitor())
    
    async def stop(self, services: Optional[List[str]] = None) -> None:
        """
        Stop services.
        
        Args:
            services: List of service names (default: all)
        """
        if services is None:
            services = ['bot', 'web', 'nats']  # Reverse order
        
        logger.info(f"Stopping services: {', '.join(services)}")
        
        # Stop health monitoring
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        for service_name in services:
            if service_name not in self.services:
                continue
            
            service = self.services[service_name]
            
            try:
                logger.info(f"Stopping {service_name}...")
                await service.stop()
                logger.info(f"Stopped {service_name}")
            except Exception as e:
                logger.error(f"Error stopping {service_name}: {e}")
    
    async def restart(self, service_name: str) -> None:
        """Restart specific service"""
        if service_name not in self.services:
            raise ValueError(f"Unknown service: {service_name}")
        
        logger.info(f"Restarting {service_name}...")
        service = self.services[service_name]
        await service.restart()
        logger.info(f"Restarted {service_name}")
    
    def status(self) -> Dict[str, Dict[str, any]]:
        """Get status of all services"""
        return {
            name: service.get_status()
            for name, service in self.services.items()
        }
    
    async def _health_monitor(self) -> None:
        """Monitor service health and restart if needed"""
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                for name, service in self.services.items():
                    if service.status == ServiceStatus.RUNNING:
                        healthy = await service.health_check()
                        
                        if not healthy:
                            logger.warning(f"Service {name} failed health check")
                            service.status = ServiceStatus.CRASHED
                            service.crash_count += 1
                            
                            # Auto-restart if crash count < 3
                            if service.crash_count < 3:
                                logger.info(f"Auto-restarting {name}...")
                                await service.restart()
                            else:
                                logger.error(f"Service {name} crashed too many times")
                                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
```

#### Component 2: Bot Service (`rosey/services/bot_service.py`)

**Responsibilities**:

- Start bot core process
- Integrate PluginLoader for hot reload
- Forward commands to PluginLoader

**Class Definition**:

```python
"""Bot core service wrapper"""
from pathlib import Path
from typing import Dict, Optional
import asyncio
import signal
import time
from rosey.services.manager import Service, ServiceStatus
from rosey.plugin.loader import PluginLoader
import logging

logger = logging.getLogger(__name__)


class BotService(Service):
    """
    Bot core service with plugin loader.
    """
    
    def __init__(self, data_dir: Path, config: Dict):
        super().__init__("bot")
        self.data_dir = data_dir
        self.config = config
        self.plugin_loader: Optional[PluginLoader] = None
    
    async def start(self) -> bool:
        """Start bot core"""
        try:
            self.status = ServiceStatus.STARTING
            
            # Import bot module
            from lib.bot import CytubeBot
            
            # Create bot instance
            logger.info("Creating bot instance...")
            self.bot = CytubeBot(self.config)
            
            # Initialize plugin loader
            logger.info("Initializing plugin loader...")
            self.plugin_loader = PluginLoader(
                data_dir=self.data_dir,
                nats_client=self.bot.nats,
                config=self.config
            )
            await self.plugin_loader.initialize()
            
            # Load enabled plugins
            logger.info("Loading plugins...")
            await self.plugin_loader.load_all()
            
            # Start bot in background task
            logger.info("Starting bot...")
            self._bot_task = asyncio.create_task(self.bot.start())
            
            self.status = ServiceStatus.RUNNING
            self.start_time = time.time()
            
            logger.info("Bot service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            self.status = ServiceStatus.CRASHED
            return False
    
    async def stop(self) -> bool:
        """Stop bot gracefully"""
        try:
            self.status = ServiceStatus.STOPPING
            
            # Unload all plugins
            if self.plugin_loader:
                logger.info("Unloading plugins...")
                await self.plugin_loader.unload_all()
            
            # Stop bot
            if hasattr(self, 'bot'):
                logger.info("Stopping bot...")
                await self.bot.stop()
            
            # Cancel bot task
            if hasattr(self, '_bot_task'):
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    pass
            
            self.status = ServiceStatus.STOPPED
            logger.info("Bot service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop bot: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check bot health"""
        if not hasattr(self, 'bot'):
            return False
        
        # Check if bot task is running
        if hasattr(self, '_bot_task') and self._bot_task.done():
            return False
        
        # Check NATS connection
        if not self.bot.nats.is_connected:
            return False
        
        return True
    
    # Plugin hot reload methods
    
    async def load_plugin(self, plugin_name: str) -> bool:
        """Load plugin dynamically (hot reload)"""
        if not self.plugin_loader:
            raise RuntimeError("Plugin loader not initialized")
        
        return await self.plugin_loader.load_plugin(plugin_name)
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload plugin dynamically (hot reload)"""
        if not self.plugin_loader:
            raise RuntimeError("Plugin loader not initialized")
        
        return await self.plugin_loader.unload_plugin(plugin_name)
    
    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload plugin (hot reload)"""
        if not self.plugin_loader:
            raise RuntimeError("Plugin loader not initialized")
        
        return await self.plugin_loader.reload_plugin(plugin_name)
    
    def list_plugins(self) -> Dict[str, Dict]:
        """List loaded plugins"""
        if not self.plugin_loader:
            return {}
        
        return self.plugin_loader.list_plugins()
```

#### Component 3: Plugin Loader (`rosey/plugin/loader.py`)

**Responsibilities**:

- Load/unload plugins dynamically
- Manage plugin lifecycle (start/stop)
- Isolate plugin processes
- Handle plugin crashes

**Class Definition**:

```python
"""Dynamic plugin loader with hot reload"""
from pathlib import Path
from typing import Dict, Optional, Any
import asyncio
import importlib.util
import sys
import logging

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Dynamically loads and manages plugins.
    
    Supports hot reload - plugins can be loaded/unloaded
    without restarting the bot.
    """
    
    def __init__(self, data_dir: Path, nats_client, config: Dict):
        """
        Initialize plugin loader.
        
        Args:
            data_dir: Base data directory
            nats_client: Shared NATS client
            config: Bot configuration
        """
        self.data_dir = data_dir
        self.plugins_dir = data_dir / "plugins"
        self.nats = nats_client
        self.config = config
        
        # Loaded plugin instances
        self._plugins: Dict[str, Any] = {}
        
        # Plugin metadata
        from rosey.plugin.registry import PluginRegistry
        self.registry = PluginRegistry(self.plugins_dir)
    
    async def initialize(self) -> None:
        """Initialize plugin loader"""
        logger.info("Plugin loader initialized")
    
    async def load_all(self) -> None:
        """Load all enabled plugins"""
        enabled = self.registry.list_enabled()
        
        logger.info(f"Loading {len(enabled)} enabled plugins...")
        
        for plugin_meta in enabled:
            plugin_name = plugin_meta['name']
            
            try:
                await self.load_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
    
    async def load_plugin(self, plugin_name: str) -> bool:
        """
        Load plugin dynamically.
        
        Args:
            plugin_name: Name of plugin to load
            
        Returns:
            True if loaded successfully
        """
        if plugin_name in self._plugins:
            logger.warning(f"Plugin {plugin_name} already loaded")
            return True
        
        try:
            logger.info(f"Loading plugin: {plugin_name}")
            
            # Get plugin metadata
            plugin_meta = self.registry.get(plugin_name)
            if not plugin_meta:
                raise ValueError(f"Plugin {plugin_name} not installed")
            
            # Load manifest
            plugin_dir = self.plugins_dir / plugin_name
            manifest_path = plugin_dir / "manifest.yaml"
            
            from rosey.plugin.manifest import ManifestValidator
            validator = ManifestValidator()
            manifest = validator.validate(manifest_path)
            
            # Initialize plugin storage
            from rosey.plugin.storage import PluginStorage
            storage = PluginStorage(plugin_name, self.plugins_dir)
            await storage.initialize()
            
            # Load plugin module
            plugin_file = plugin_dir / (manifest.get('entry_point', 'plugin.py'))
            spec = importlib.util.spec_from_file_location(
                f"rosey_plugin_{plugin_name}",
                plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Get plugin class
            main_class = manifest.get('main_class', 'Plugin')
            plugin_class = getattr(module, main_class)
            
            # Get plugin config
            config_path = plugin_dir / "config.yaml"
            plugin_config = {}
            if config_path.exists():
                import yaml
                with open(config_path) as f:
                    plugin_config = yaml.safe_load(f) or {}
            
            # Create logger for plugin
            plugin_logger = logging.getLogger(f"plugin.{plugin_name}")
            
            # Instantiate plugin
            plugin_instance = plugin_class(
                storage=storage,
                config=plugin_config,
                nats=self.nats,
                logger=plugin_logger
            )
            
            # Call on_load lifecycle hook
            if hasattr(plugin_instance, 'on_load'):
                await plugin_instance.on_load()
            
            # Store plugin instance
            self._plugins[plugin_name] = {
                'instance': plugin_instance,
                'module': module,
                'storage': storage,
                'manifest': manifest
            }
            
            # Update registry status
            self.registry.update(plugin_name, {'status': 'running'})
            
            logger.info(f"Loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            self.registry.update(plugin_name, {'status': 'crashed'})
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload plugin dynamically.
        
        Args:
            plugin_name: Name of plugin to unload
            
        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return True
        
        try:
            logger.info(f"Unloading plugin: {plugin_name}")
            
            plugin_data = self._plugins[plugin_name]
            plugin_instance = plugin_data['instance']
            
            # Call on_unload lifecycle hook
            if hasattr(plugin_instance, 'on_unload'):
                await plugin_instance.on_unload()
            
            # Remove from loaded plugins
            del self._plugins[plugin_name]
            
            # Remove module from sys.modules
            module_name = f"rosey_plugin_{plugin_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Update registry status
            self.registry.update(plugin_name, {'status': 'stopped'})
            
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload plugin (unload + load).
        
        Args:
            plugin_name: Name of plugin to reload
            
        Returns:
            True if reloaded successfully
        """
        logger.info(f"Reloading plugin: {plugin_name}")
        
        # Unload
        await self.unload_plugin(plugin_name)
        
        # Small delay
        await asyncio.sleep(0.5)
        
        # Load
        return await self.load_plugin(plugin_name)
    
    async def unload_all(self) -> None:
        """Unload all plugins"""
        plugin_names = list(self._plugins.keys())
        
        logger.info(f"Unloading {len(plugin_names)} plugins...")
        
        for plugin_name in plugin_names:
            try:
                await self.unload_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to unload plugin {plugin_name}: {e}")
    
    def list_plugins(self) -> Dict[str, Dict]:
        """List loaded plugins with status"""
        result = {}
        
        for plugin_name, plugin_data in self._plugins.items():
            manifest = plugin_data['manifest']
            result[plugin_name] = {
                'name': plugin_name,
                'version': manifest['version'],
                'display_name': manifest.get('display_name', plugin_name),
                'status': 'running',
                'permissions': manifest.get('permissions', [])
            }
        
        return result
```

#### Component 4: NATS Service (`rosey/services/nats_service.py`)

**Responsibilities**:

- Start/stop NATS server
- Health checks
- Log forwarding

**Class Definition**:

```python
"""NATS server service wrapper"""
from pathlib import Path
from typing import Dict
import asyncio
import signal
import time
from rosey.services.manager import Service, ServiceStatus
import logging

logger = logging.getLogger(__name__)


class NATSService(Service):
    """
    NATS server service.
    
    Manages NATS server as subprocess.
    """
    
    def __init__(self, data_dir: Path, config: Dict):
        super().__init__("nats")
        self.data_dir = data_dir
        self.config = config
        self.nats_config = config.get('nats', {})
    
    async def start(self) -> bool:
        """Start NATS server"""
        try:
            self.status = ServiceStatus.STARTING
            
            # Get NATS server command
            nats_cmd = self.nats_config.get('server_cmd', 'nats-server')
            host = self.nats_config.get('host', 'localhost')
            port = self.nats_config.get('port', 4222)
            
            # Create log file
            log_file = self.data_dir.parent / "logs" / "nats.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Start NATS server
            logger.info(f"Starting NATS server on {host}:{port}...")
            
            self.process = await asyncio.create_subprocess_exec(
                nats_cmd,
                "-a", host,
                "-p", str(port),
                "-l", str(log_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for startup
            await asyncio.sleep(2)
            
            # Check if still running
            if self.process.returncode is not None:
                raise RuntimeError("NATS server exited immediately")
            
            self.status = ServiceStatus.RUNNING
            self.start_time = time.time()
            
            logger.info("NATS server started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start NATS: {e}")
            self.status = ServiceStatus.CRASHED
            return False
    
    async def stop(self) -> bool:
        """Stop NATS server"""
        try:
            self.status = ServiceStatus.STOPPING
            
            if self.process:
                logger.info("Stopping NATS server...")
                
                # Send SIGTERM
                self.process.send_signal(signal.SIGTERM)
                
                # Wait for shutdown (timeout 10s)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("NATS server did not stop, killing...")
                    self.process.kill()
                    await self.process.wait()
            
            self.process = None
            self.status = ServiceStatus.STOPPED
            
            logger.info("NATS server stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop NATS: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check NATS health"""
        if not self.process:
            return False
        
        # Check if process is alive
        if self.process.returncode is not None:
            return False
        
        # Try to connect
        try:
            import nats
            nc = await nats.connect(
                servers=[f"nats://{self.nats_config.get('host', 'localhost')}:{self.nats_config.get('port', 4222)}"]
            )
            await nc.close()
            return True
        except:
            return False
```

### 2.4 CLI Commands (Update `rosey/cli/`)

**Service Management Commands** (`rosey/cli/service.py`):

```python
"""Service management CLI commands"""
import click
from pathlib import Path
import asyncio
from rosey.cli.utils import success, error, info


@click.group(name='service')
def service_cli():
    """Manage Rosey services (bot, NATS, web)"""
    pass


@click.command()
@click.argument('service', required=False, default='all')
def start(service: str):
    """
    Start services.
    
    Args:
        service: Service name (bot/nats/web/all, default: all)
    """
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    
    try:
        config = get_config()
        manager = ServiceManager(Path("data"), config)
        
        services = None if service == 'all' else [service]
        
        info(f"Starting {service}...")
        asyncio.run(manager.start(services))
        
        success(f"Started {service}")
        info("\nNext steps:")
        info("  rosey status           # Check service status")
        info("  rosey logs -f          # Tail logs")
        
    except KeyboardInterrupt:
        info("\nShutting down...")
        asyncio.run(manager.stop())
    except Exception as e:
        error(f"Failed to start: {e}")
        raise click.Abort()


@click.command()
@click.argument('service', required=False, default='all')
def stop(service: str):
    """
    Stop services.
    
    Args:
        service: Service name (bot/nats/web/all, default: all)
    """
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    
    try:
        config = get_config()
        manager = ServiceManager(Path("data"), config)
        
        services = None if service == 'all' else [service]
        
        info(f"Stopping {service}...")
        asyncio.run(manager.stop(services))
        
        success(f"Stopped {service}")
        
    except Exception as e:
        error(f"Failed to stop: {e}")
        raise click.Abort()


@click.command()
@click.argument('service')
def restart(service: str):
    """
    Restart service.
    
    Args:
        service: Service name (bot/nats/web)
    """
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    
    try:
        config = get_config()
        manager = ServiceManager(Path("data"), config)
        
        info(f"Restarting {service}...")
        asyncio.run(manager.restart(service))
        
        success(f"Restarted {service}")
        
    except Exception as e:
        error(f"Failed to restart: {e}")
        raise click.Abort()


@click.command()
def status():
    """Show status of all services"""
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    
    try:
        config = get_config()
        manager = ServiceManager(Path("data"), config)
        
        # Get status
        statuses = manager.status()
        
        # Display table
        click.echo("\nService Status:\n")
        
        for name, status_info in statuses.items():
            status = status_info['status']
            pid = status_info['pid']
            uptime = status_info.get('uptime', 0)
            
            # Status icon
            if status == 'running':
                icon = click.style("●", fg='green')
            elif status == 'stopped':
                icon = click.style("○", fg='white')
            elif status == 'crashed':
                icon = click.style("✕", fg='red')
            else:
                icon = click.style("?", fg='yellow')
            
            # Format uptime
            if uptime > 0:
                uptime_str = f"{int(uptime)}s"
            else:
                uptime_str = "-"
            
            click.echo(f"{icon} {name:<10} {status:<10} PID: {pid or '-':<8} Uptime: {uptime_str}")
        
        click.echo()
        
    except Exception as e:
        error(f"Failed to get status: {e}")
        raise click.Abort()


# Register commands
service_cli.add_command(start)
service_cli.add_command(stop)
service_cli.add_command(restart)
service_cli.add_command(status)
```

**Log Tailing Command** (`rosey/cli/logs.py`):

```python
"""Log aggregation and tailing"""
import click
from pathlib import Path
import asyncio


@click.command()
@click.argument('service', required=False, default='all')
@click.option('-f', '--follow', is_flag=True, help='Follow log output')
@click.option('-n', '--lines', type=int, default=50, help='Number of lines to show')
def logs(service: str, follow: bool, lines: int):
    """
    View service logs.
    
    Args:
        service: Service name (bot/nats/plugin-name/all, default: all)
    """
    from rosey.cli.utils import info, error
    
    try:
        logs_dir = Path("logs")
        
        # Determine log files
        if service == 'all':
            log_files = [logs_dir / "rosey.log"]
        elif service == 'bot':
            log_files = [logs_dir / "bot.log"]
        elif service == 'nats':
            log_files = [logs_dir / "nats.log"]
        elif service == 'web':
            log_files = [logs_dir / "web.log"]
        else:
            # Assume plugin name
            log_files = [logs_dir / "plugins" / f"{service}.log"]
        
        # Check if files exist
        for log_file in log_files:
            if not log_file.exists():
                error(f"Log file not found: {log_file}")
                return
        
        # Tail logs
        if follow:
            info(f"Tailing logs for {service} (Ctrl+C to stop)...")
            
            import subprocess
            for log_file in log_files:
                subprocess.run(["tail", "-f", str(log_file)])
        else:
            info(f"Last {lines} lines for {service}:")
            
            for log_file in log_files:
                with open(log_file) as f:
                    all_lines = f.readlines()
                    for line in all_lines[-lines:]:
                        click.echo(line.rstrip())
        
    except KeyboardInterrupt:
        info("\nStopped tailing logs")
    except Exception as e:
        error(f"Failed to view logs: {e}")
        raise click.Abort()
```

**Development Mode** (`rosey/cli/dev.py`):

```python
"""Development mode with auto-reload"""
import click
from pathlib import Path
import asyncio


@click.command()
def dev():
    """
    Start Rosey in development mode.
    
    Features:
    - Starts all services (NATS, bot, web)
    - Auto-reloads on code changes
    - Verbose logging
    """
    from rosey.cli.utils import info, error
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    
    try:
        info("Starting Rosey in development mode...")
        info("Features:")
        info("  - All services started (NATS, bot, web)")
        info("  - Auto-reload on code changes")
        info("  - Verbose logging\n")
        
        # Load config
        config = get_config()
        
        # Enable verbose logging
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        # Create service manager
        manager = ServiceManager(Path("data"), config)
        
        # Start all services
        info("Starting services...")
        asyncio.run(manager.start(['nats', 'bot', 'web']))
        
        info("\n✓ Development mode active")
        info("\nCommands:")
        info("  Ctrl+C              - Stop all services")
        info("  rosey status        - Check service status")
        info("  rosey logs -f bot   - Tail bot logs\n")
        
        # Keep running until interrupted
        try:
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            pass
        
        # Stop services
        info("\nStopping services...")
        asyncio.run(manager.stop())
        
        info("✓ Stopped")
        
    except Exception as e:
        error(f"Development mode failed: {e}")
        raise click.Abort()
```

### 2.5 Hot Reload Integration

**Plugin Installation with Hot Reload** (Update `rosey/cli/plugin.py`):

```python
@plugin_cli.command('install')
@click.argument('source')
@click.option('--no-reload', is_flag=True, help='Skip hot reload (requires bot restart)')
def install_plugin(source: str, no_reload: bool):
    """Install plugin from file or Git repository"""
    import asyncio
    from rosey.plugin.manager import PluginManager
    from rosey.services.manager import ServiceManager
    from common.config import get_config
    from pathlib import Path
    
    try:
        # Initialize manager
        manager = PluginManager(Path("data"))
        
        # Install plugin
        info("Installing plugin...")
        result = asyncio.run(manager.install(source))
        
        success(f"Installed {result['name']} v{result['version']}")
        
        # Hot reload (if bot is running)
        if not no_reload:
            try:
                config = get_config()
                service_manager = ServiceManager(Path("data"), config)
                
                # Check if bot is running
                bot_status = service_manager.services['bot'].get_status()
                
                if bot_status['status'] == 'running':
                    info("\nBot is running - loading plugin dynamically...")
                    
                    bot_service = service_manager.services['bot']
                    success_load = asyncio.run(bot_service.load_plugin(result['name']))
                    
                    if success_load:
                        success(f"Plugin {result['name']} loaded successfully (hot reload)")
                    else:
                        error("Hot reload failed - restart bot manually")
                else:
                    info("\nBot is not running - plugin will load on next start")
            except Exception as e:
                error(f"Hot reload failed: {e}")
                info("Restart bot manually to load plugin")
        
        info("\nNext steps:")
        info(f"  rosey plugin list              # Verify installation")
        info(f"  rosey logs -f {result['name']} # View plugin logs")
        
    except Exception as e:
        error(f"Installation failed: {e}")
        raise click.Abort()
```

---

## 3. Implementation Plan

### 3.1 Phase 1: Service Management Foundation (3-4 hours)

**Tasks**:

1. **Implement ServiceManager**:
   - Service base class
   - Service lifecycle (start/stop/restart)
   - Status tracking
   - Health monitoring

2. **Implement BotService**:
   - Integrate with existing bot
   - Start/stop bot process
   - Health checks

3. **Implement NATSService**:
   - Start/stop NATS server subprocess
   - Health checks
   - Log forwarding

4. **Basic CLI commands**:
   - `rosey start/stop/restart`
   - `rosey status`

**Acceptance Criteria**:

- ✅ `rosey start` starts bot and NATS
- ✅ `rosey status` shows service health
- ✅ `rosey stop` gracefully stops all services
- ✅ Services restart on crash (<3 crashes)

### 3.2 Phase 2: Plugin Hot Reload (3-4 hours)

**Tasks**:

1. **Implement PluginLoader**:
   - Dynamic module loading
   - Plugin lifecycle hooks (on_load/on_unload)
   - Plugin registry integration
   - Crash handling

2. **Integrate with BotService**:
   - Load plugins during bot startup
   - Hot reload methods (load/unload/reload)

3. **Update plugin install CLI**:
   - Detect running bot
   - Trigger hot reload after install
   - Show success/failure

**Acceptance Criteria**:

- ✅ Install plugin while bot running → plugin starts immediately
- ✅ Remove plugin while bot running → plugin stops gracefully
- ✅ Bot never restarts
- ✅ Plugin crashes don't affect bot

### 3.3 Phase 3: Logging & Development Mode (2 hours)

**Tasks**:

1. **Implement log aggregation**:
   - Collect logs from all services
   - Per-plugin log files
   - `rosey logs` command

2. **Implement development mode**:
   - Start all services
   - Verbose logging
   - Auto-reload on code changes (optional)
   - `rosey dev` command

**Acceptance Criteria**:

- ✅ `rosey logs -f bot` tails bot logs
- ✅ `rosey logs -f markov-chat` tails plugin logs
- ✅ `rosey dev` starts all services with verbose logs
- ✅ Ctrl+C gracefully stops all services

---

## 4. Testing Strategy

### 4.1 Unit Tests

**`tests/unit/services/test_service_manager.py`**:

```python
"""Tests for service manager"""
import pytest
from rosey.services.manager import ServiceManager


@pytest.mark.asyncio
async def test_start_all_services(tmp_path, test_config):
    """Test starting all services"""
    manager = ServiceManager(tmp_path, test_config)
    
    await manager.start(['nats', 'bot'])
    
    # Verify services started
    status = manager.status()
    assert status['nats']['status'] == 'running'
    assert status['bot']['status'] == 'running'
    
    # Cleanup
    await manager.stop()


@pytest.mark.asyncio
async def test_service_restart(tmp_path, test_config):
    """Test restarting individual service"""
    manager = ServiceManager(tmp_path, test_config)
    
    await manager.start(['bot'])
    
    # Get initial PID
    initial_pid = manager.services['bot'].process.pid
    
    # Restart
    await manager.restart('bot')
    
    # Verify new PID
    new_pid = manager.services['bot'].process.pid
    assert new_pid != initial_pid
    
    # Cleanup
    await manager.stop()
```

**`tests/unit/plugin/test_plugin_loader.py`**:

```python
"""Tests for plugin loader"""
import pytest
from rosey.plugin.loader import PluginLoader


@pytest.mark.asyncio
async def test_load_plugin(tmp_path, test_nats, test_plugin_archive):
    """Test loading plugin dynamically"""
    # Install plugin first
    from rosey.plugin.manager import PluginManager
    manager = PluginManager(tmp_path)
    await manager.install(str(test_plugin_archive))
    
    # Load plugin
    loader = PluginLoader(tmp_path, test_nats, {})
    await loader.initialize()
    
    success = await loader.load_plugin('test-plugin')
    assert success
    
    # Verify loaded
    plugins = loader.list_plugins()
    assert 'test-plugin' in plugins
    
    # Cleanup
    await loader.unload_plugin('test-plugin')


@pytest.mark.asyncio
async def test_hot_reload(tmp_path, test_nats, test_plugin_archive):
    """Test hot reload (unload + load)"""
    # Install and load plugin
    from rosey.plugin.manager import PluginManager
    manager = PluginManager(tmp_path)
    await manager.install(str(test_plugin_archive))
    
    loader = PluginLoader(tmp_path, test_nats, {})
    await loader.initialize()
    await loader.load_plugin('test-plugin')
    
    # Get initial instance ID
    initial_id = id(loader._plugins['test-plugin']['instance'])
    
    # Reload
    success = await loader.reload_plugin('test-plugin')
    assert success
    
    # Verify new instance
    new_id = id(loader._plugins['test-plugin']['instance'])
    assert new_id != initial_id
    
    # Cleanup
    await loader.unload_plugin('test-plugin')


@pytest.mark.asyncio
async def test_plugin_crash_isolation(tmp_path, test_nats, crashing_plugin):
    """Test that plugin crashes don't affect bot"""
    # Install crashing plugin
    from rosey.plugin.manager import PluginManager
    manager = PluginManager(tmp_path)
    await manager.install(str(crashing_plugin))
    
    # Load plugin
    loader = PluginLoader(tmp_path, test_nats, {})
    await loader.initialize()
    
    # This should fail but not crash the loader
    success = await loader.load_plugin('crashing-plugin')
    assert not success
    
    # Verify loader still functional
    plugins = loader.list_plugins()
    assert 'crashing-plugin' not in plugins
```

### 4.2 Integration Tests

**`tests/integration/test_hot_reload_workflow.py`**:

```python
"""Integration tests for hot reload"""
import pytest
from click.testing import CliRunner
from rosey.cli.main import main


@pytest.mark.asyncio
async def test_install_with_hot_reload(tmp_path, running_bot, test_plugin_archive):
    """Test installing plugin while bot is running"""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        # Start bot
        # (running_bot fixture handles this)
        
        # Install plugin
        result = runner.invoke(main, [
            'plugin', 'install', str(test_plugin_archive)
        ])
        
        assert result.exit_code == 0
        assert 'Installed' in result.output
        assert 'loaded successfully (hot reload)' in result.output
        
        # Verify plugin is running
        result = runner.invoke(main, ['plugin', 'list'])
        assert 'test-plugin' in result.output


@pytest.mark.asyncio
async def test_remove_with_hot_reload(tmp_path, running_bot_with_plugin):
    """Test removing plugin while bot is running"""
    runner = CliRunner()
    
    # Remove plugin
    result = runner.invoke(main, [
        'plugin', 'remove', 'test-plugin', '--yes'
    ])
    
    assert result.exit_code == 0
    assert 'Removed' in result.output
    
    # Verify plugin stopped
    result = runner.invoke(main, ['plugin', 'list'])
    assert 'No plugins installed' in result.output
```

---

## 5. Dependencies

### 5.1 Python Packages

**No new dependencies** - all functionality uses existing packages:

- `asyncio` - async/await support
- `subprocess` - process management
- `importlib` - dynamic module loading
- `signal` - graceful shutdown

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

- [x] `rosey start` starts all services (NATS, bot, web)
- [x] `rosey stop` gracefully stops all services
- [x] `rosey restart <service>` restarts individual service
- [x] `rosey status` shows service health (running/stopped/crashed)
- [x] `rosey logs [service] -f` tails logs for specific service
- [x] `rosey dev` starts all services in development mode
- [x] Plugin hot reload: install while bot running → plugin starts
- [x] Plugin hot reload: remove while bot running → plugin stops
- [x] Plugin hot reload: update while bot running → plugin reloads
- [x] Plugin crashes don't affect bot core
- [x] Service crashes auto-restart (<3 times)
- [x] Graceful shutdown on Ctrl+C

### 6.2 Non-Functional Requirements

- [x] Service start time <10 seconds
- [x] Plugin hot reload <5 seconds
- [x] Zero downtime for bot core during plugin operations
- [x] Process isolation (plugin in separate process)
- [x] Clean shutdown (all resources released)

### 6.3 Test Coverage

- [x] Unit tests: 90%+ coverage
- [x] Integration tests: Full lifecycle (start → hot reload → stop)
- [x] Crash tests: Plugin crashes, service crashes
- [x] Concurrency tests: Multiple plugins, concurrent operations

---

## 7. Documentation Requirements

### 7.1 Operator Guide

**Update `docs/OPERATORS.md`**:

```markdown
## Service Management

### Starting Services

```bash
# Start all services
rosey start

# Start specific service
rosey start bot
rosey start nats
```

### Stopping Services

```bash
# Stop all services
rosey stop

# Stop specific service
rosey stop bot
```

### Checking Status

```bash
rosey status
```

Output:
```text
Service Status:

● bot        running    PID: 12345    Uptime: 3600s
● nats       running    PID: 12346    Uptime: 3600s
○ web        stopped    PID: -        Uptime: -
```

### Viewing Logs

```bash
# Tail all logs
rosey logs -f

# Tail bot logs
rosey logs -f bot

# Tail plugin logs
rosey logs -f markov-chat

# View last 100 lines
rosey logs bot -n 100
```

## Hot Reload

### Installing Plugins

When you install a plugin while the bot is running, it will start automatically:

```bash
rosey plugin install ./markov-chat-1.2.0.roseyplug
# Output: Plugin markov-chat loaded successfully (hot reload)
```

No bot restart needed!

### Removing Plugins

When you remove a plugin while the bot is running, it will stop gracefully:

```bash
rosey plugin remove markov-chat --yes
# Output: Plugin markov-chat unloaded successfully
```

### Updating Plugins

To update a plugin, remove and reinstall:

```bash
rosey plugin remove markov-chat --yes
rosey plugin install ./markov-chat-1.3.0.roseyplug
```

Hot reload handles both operations without bot restart.

## Development Mode

For development, use `rosey dev`:

```bash
rosey dev
```

Features:
- Starts all services (NATS, bot, web)
- Verbose logging (DEBUG level)
- Auto-reload on code changes (coming soon)
- Ctrl+C gracefully stops all services
```

---

## 8. Rollback Plan

### 8.1 Rollback Triggers

- Service management failures (can't start/stop bot)
- Plugin hot reload crashes bot
- Process isolation broken (plugin crashes bot)
- Critical performance regression (>50% slower startup)

### 8.2 Rollback Procedure

1. **Disable hot reload**: Set `hot_reload_enabled: false` in config
2. **Fallback to manual start**: Use `python -m lib.bot` directly
3. **Remove ServiceManager**: Revert to previous bot startup
4. **Document issues**: Log failures for analysis

**Recovery Time**: <1 hour (manual bot startup works immediately)

---

## 9. Deployment Checklist

### 9.1 Pre-Deployment

- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Hot reload tested (install/remove/update)
- [ ] Process isolation verified
- [ ] Performance benchmarks acceptable
- [ ] Documentation updated

### 9.2 Deployment Steps

```bash
# 1. Stop bot
rosey stop  # (or Ctrl+C)

# 2. Update code
git pull origin main
pip install -e .

# 3. Test service management
rosey status
rosey start bot

# 4. Test hot reload
rosey plugin install ./test-plugin.roseyplug
rosey plugin list
rosey plugin remove test-plugin --yes

# 5. Start all services
rosey start
```

### 9.3 Post-Deployment Validation

- [ ] `rosey status` shows all services running
- [ ] Install plugin without bot restart works
- [ ] Remove plugin without bot restart works
- [ ] Plugin logs visible (`rosey logs -f <plugin>`)
- [ ] No regression in bot functionality
- [ ] Performance acceptable (startup <10s)

---

## 10. Performance Considerations

### 10.1 Startup Time

**Targets**:

- NATS server: <2 seconds
- Bot core: <5 seconds
- Plugin loading: <3 seconds per plugin
- Total: <10 seconds for full stack

**Optimizations**:

- Parallel plugin loading
- Lazy NATS subscriptions
- Deferred database connections

### 10.2 Hot Reload Performance

**Targets**:

- Install plugin: <5 seconds
- Remove plugin: <2 seconds
- Reload plugin: <6 seconds

**Optimizations**:

- Keep module in memory cache
- Reuse database connections
- Parallel unload/load

### 10.3 Memory Overhead

**Targets**:

- ServiceManager: <5MB
- PluginLoader: <10MB
- Per-plugin overhead: <50MB

**Monitoring**:

- Track process memory usage
- Alert on memory leaks
- Auto-restart on high memory

---

## Appendices

### A. Service Status States

```python
class ServiceStatus(Enum):
    STOPPED = "stopped"      # Service not running
    STARTING = "starting"    # Service is starting up
    RUNNING = "running"      # Service healthy
    STOPPING = "stopping"    # Service is shutting down
    CRASHED = "crashed"      # Service exited unexpectedly
    UNKNOWN = "unknown"      # Status cannot be determined
```

### B. Plugin Lifecycle Hooks

**Required Methods** (base class):

```python
class Plugin:
    async def on_load(self):
        """Called when plugin loads (setup)"""
        pass
    
    async def on_unload(self):
        """Called when plugin unloads (cleanup)"""
        pass
```

**Optional Methods**:

```python
    async def on_reload(self):
        """Called during hot reload (save state)"""
        pass
    
    async def on_crash(self, error: Exception):
        """Called when plugin crashes (error handling)"""
        pass
```

### C. CLI Output Examples

**`rosey start`**:

```text
Starting services...
Starting NATS server on localhost:4222...
✓ NATS server started
Starting bot...
Creating bot instance...
Initializing plugin loader...
Loading plugins...
  Loading plugin: markov-chat
  ✓ Loaded plugin: markov-chat
  Loading plugin: quote-bot
  ✓ Loaded plugin: quote-bot
Starting bot...
✓ Bot service started
✓ Started all

Next steps:
  rosey status           # Check service status
  rosey logs -f          # Tail logs
```

**`rosey status`**:

```text
Service Status:

● bot        running    PID: 12345    Uptime: 3600s
● nats       running    PID: 12346    Uptime: 3602s
○ web        stopped    PID: -        Uptime: -
```

**`rosey logs -f bot`** (tail output):

```text
Tailing logs for bot (Ctrl+C to stop)...
2025-11-21 10:30:00 [INFO] Bot starting...
2025-11-21 10:30:01 [INFO] Connected to NATS
2025-11-21 10:30:02 [INFO] Loaded plugin: markov-chat
2025-11-21 10:30:03 [INFO] Loaded plugin: quote-bot
2025-11-21 10:30:04 [INFO] Bot started successfully
```

**`rosey plugin install ./markov-chat.roseyplug`** (with hot reload):

```text
Installing plugin...
✓ Installed markov-chat v1.2.0

Permissions:
  - read_messages
  - send_messages
  - database_access

Note: Permissions are informational (trust-based)

Bot is running - loading plugin dynamically...
✓ Plugin markov-chat loaded successfully (hot reload)

Next steps:
  rosey plugin list              # Verify installation
  rosey logs -f markov-chat      # View plugin logs
```

**`rosey dev`**:

```text
Starting Rosey in development mode...
Features:
  - All services started (NATS, bot, web)
  - Auto-reload on code changes
  - Verbose logging

Starting services...
Starting NATS server on localhost:4222...
✓ NATS server started
Starting bot...
✓ Bot service started
Starting web dashboard on http://localhost:8080...
✓ Web service started

✓ Development mode active

Commands:
  Ctrl+C              - Stop all services
  rosey status        - Check service status
  rosey logs -f bot   - Tail bot logs
```

---

**Document Status**: ✅ Ready for Implementation  
**Estimated Effort**: 8-10 hours  
**Risk Level**: HIGH (process management, hot reload complexity)  
**Next Sortie**: Sortie 4 - Database CLI & Documentation  

**Key Success Factors**:

1. ✅ Hot reload works reliably (>99% success rate)
2. ✅ Plugin crashes isolated (don't affect bot)
3. ✅ Graceful shutdown always works
4. ✅ Service health monitoring accurate
5. ✅ Log aggregation complete (all services)

**Movie Quote**: *"The siege begins, but the defenders hold strong. No one gets through, no one gets out, until the job is done."* 🎬
