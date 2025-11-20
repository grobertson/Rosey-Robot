# Sprint 8: Inception - Product Requirements Document

## Overview

**Sprint Name:** Inception (2010)  
**Sprint Goal:** Build a robust, production-ready plugin architecture with hot reload capability  
**Status:** Planning  
**Dependencies:** Sprint 7 (The Divide) complete

## Executive Summary

Sprint 8 delivers a comprehensive plugin system that transforms the bot from a monolithic application into an extensible platform. Plugins will be self-contained modules with clear lifecycle management, configuration, event handling, and crucially - **hot reload** capability for development and production updates without bot restart.

This architecture enables:
- **Rapid feature development** - New features as plugins without touching core
- **Community contributions** - Third-party plugin ecosystem
- **A/B testing** - Load/unload plugins dynamically
- **Resource isolation** - Plugin failures don't crash the bot
- **Development velocity** - Hot reload during development

## Context & Motivation

### Current State

After Sprint 7, we have:
- Clean separation: `bot.py`, `connection.py`, `storage.py`
- Event system: `bot.on('event', handler)`
- Abstract interfaces for extensibility

**However:**
- Features are still hardcoded in `bot.py`
- Adding features requires modifying core code
- No hot reload - restart required for updates
- No plugin isolation or sandboxing
- No structured way to share/distribute features

### Strategic Vision

**Plugin-First Architecture:** Future features should default to plugins unless they belong in core. This enables:

1. **Modular Development** - Teams work on isolated plugins
2. **Safe Experimentation** - Load experimental plugins without risk
3. **Community Ecosystem** - Share plugins like npm packages
4. **Zero-Downtime Updates** - Hot reload production plugins
5. **Resource Management** - Limit plugin resources, unload unused plugins

### Inspiration

Drawing from successful plugin ecosystems:
- **WordPress** - Massive plugin ecosystem, hooks/filters pattern
- **VS Code Extensions** - TypeScript activation events, contribution points
- **Django Apps** - Reusable apps with settings, migrations, templates
- **Pytest Plugins** - Entry points discovery, hook system

## Plugin Architecture

### High-Level Design

```
┌─────────────────────────────────────────────┐
│              Bot Core                       │
│  - Plugin Manager                           │
│  - Event Bus                                │
│  - Service Registry                         │
└──────────────┬──────────────────────────────┘
               │
               ├──── Plugin Lifecycle ────┐
               │                           │
               ▼                           ▼
      ┌────────────────┐         ┌────────────────┐
      │   Plugin A     │         │   Plugin B     │
      │                │         │                │
      │ - Config       │         │ - Config       │
      │ - State        │         │ - State        │
      │ - Event Hooks  │         │ - Event Hooks  │
      └────────────────┘         └────────────────┘
```

### Core Components

#### 1. Plugin Manager (`lib/plugins/manager.py`)

**Responsibilities:**
- Plugin discovery (scan directories, entry points)
- Plugin loading and initialization
- Plugin lifecycle management (start, stop, reload)
- Dependency resolution between plugins
- Error isolation and recovery
- Hot reload coordination

#### 2. Plugin Base Class (`lib/plugins/base.py`)

**Responsibilities:**
- Abstract interface all plugins implement
- Lifecycle hooks (setup, teardown, on_enable, on_disable)
- Access to bot services (connection, storage, logger)
- Configuration management
- Metadata declaration

#### 3. Event Bus (`lib/plugins/events.py`)

**Responsibilities:**
- Pub/sub event system for plugin communication
- Event priority and ordering
- Async event dispatch
- Event filtering and routing

#### 4. Service Registry (`lib/plugins/services.py`)

**Responsibilities:**
- Dependency injection for plugins
- Service discovery (find other plugins)
- API exposure (plugins can provide APIs to other plugins)
- Resource tracking

## Plugin Interface Design

### Base Plugin Class

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

class Plugin(ABC):
    """Base class for all bot plugins."""
    
    # Plugin metadata (class attributes)
    name: str = None              # Required: Plugin identifier
    version: str = "0.1.0"        # Semantic version
    description: str = ""         # Human-readable description
    author: str = ""              # Plugin author
    dependencies: list = []       # List of required plugin names
    
    def __init__(self, bot, config: Optional[Dict[str, Any]] = None):
        """
        Initialize plugin.
        
        Args:
            bot: Bot instance providing services
            config: Plugin-specific configuration dict
        """
        self.bot = bot
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.name}")
        self.enabled = False
        
    @abstractmethod
    async def setup(self):
        """
        Setup plugin resources (called once on load).
        
        Use for:
        - Database schema initialization
        - Loading configuration
        - Registering commands
        - Creating resources
        """
        pass
    
    @abstractmethod
    async def teardown(self):
        """
        Cleanup plugin resources (called on unload/reload).
        
        Use for:
        - Closing connections
        - Saving state
        - Unregistering handlers
        - Releasing resources
        """
        pass
    
    async def on_enable(self):
        """Called when plugin is enabled (after setup)."""
        self.enabled = True
        self.logger.info(f"Plugin {self.name} enabled")
    
    async def on_disable(self):
        """Called when plugin is disabled (before teardown)."""
        self.enabled = False
        self.logger.info(f"Plugin {self.name} disabled")
    
    # Convenience methods for common operations
    
    def register_command(self, name: str, handler, **options):
        """Register bot command handled by this plugin."""
        self.bot.register_command(name, handler, plugin=self, **options)
    
    def on_event(self, event: str, handler):
        """Register event handler for this plugin."""
        self.bot.on(event, handler)
    
    def emit_event(self, event: str, data: Any):
        """Emit event to plugin event bus."""
        self.bot.plugin_manager.emit(event, data, source=self)
    
    def get_service(self, service_name: str) -> Any:
        """Get service from service registry."""
        return self.bot.services.get(service_name)
    
    def provide_service(self, service_name: str, service: Any):
        """Provide service to other plugins."""
        self.bot.services.register(service_name, service, provider=self)
```

### Example Plugin Implementation

```python
from lib.plugins import Plugin

class DiceRollerPlugin(Plugin):
    """Simple dice rolling plugin."""
    
    name = "dice_roller"
    version = "1.0.0"
    description = "Roll dice with !roll command"
    author = "YourName"
    dependencies = []
    
    async def setup(self):
        """Setup dice roller."""
        self.register_command("roll", self.handle_roll, 
                             help="!roll [NdM] - Roll N dice with M sides")
        self.logger.info("Dice roller plugin loaded")
    
    async def teardown(self):
        """Cleanup dice roller."""
        # Commands auto-unregistered by plugin manager
        self.logger.info("Dice roller plugin unloaded")
    
    async def handle_roll(self, event, data):
        """Handle !roll command."""
        import random
        
        message = data.get('msg', '')
        args = message.split()[1:]  # Skip command name
        
        if not args:
            # Default: 1d6
            result = random.randint(1, 6)
            await self.bot.connection.send_message(f"🎲 Rolled: {result}")
            return
        
        # Parse NdM format
        try:
            dice_spec = args[0]
            if 'd' not in dice_spec.lower():
                await self.bot.connection.send_message("Usage: !roll NdM (e.g., !roll 2d6)")
                return
            
            num_dice, num_sides = dice_spec.lower().split('d')
            num_dice = int(num_dice) if num_dice else 1
            num_sides = int(num_sides)
            
            if num_dice > 100 or num_sides > 1000:
                await self.bot.connection.send_message("Too many dice or sides!")
                return
            
            rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
            total = sum(rolls)
            
            await self.bot.connection.send_message(
                f"🎲 Rolled {num_dice}d{num_sides}: {rolls} = {total}"
            )
        except ValueError:
            await self.bot.connection.send_message("Invalid format. Use: !roll 2d6")
```

## Plugin Manager Implementation

### Plugin Lifecycle

```
┌──────────┐
│ Discover │  Scan plugin directories, find Plugin classes
└────┬─────┘
     │
     ▼
┌──────────┐
│   Load   │  Import module, instantiate Plugin class
└────┬─────┘
     │
     ▼
┌──────────┐
│  Setup   │  Call plugin.setup() - allocate resources
└────┬─────┘
     │
     ▼
┌──────────┐
│  Enable  │  Call plugin.on_enable() - start operation
└────┬─────┘
     │
     │  ┌─────────────┐
     ├─→│   Running   │ ←──┐
     │  └─────────────┘    │
     │         │            │
     │         ▼            │
     │  ┌─────────────┐    │
     │  │ Hot Reload  │────┘
     │  └─────────────┘
     │
     ▼
┌──────────┐
│ Disable  │  Call plugin.on_disable() - pause operation
└────┬─────┘
     │
     ▼
┌──────────┐
│ Teardown │  Call plugin.teardown() - release resources
└────┬─────┘
     │
     ▼
┌──────────┐
│  Unload  │  Remove from registry
└──────────┘
```

### Plugin Manager Interface

```python
class PluginManager:
    """Manages plugin lifecycle and coordination."""
    
    def __init__(self, bot, plugin_dirs: list[str]):
        """
        Initialize plugin manager.
        
        Args:
            bot: Bot instance
            plugin_dirs: Directories to scan for plugins
        """
        self.bot = bot
        self.plugin_dirs = plugin_dirs
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_modules = {}
        self.logger = logging.getLogger("plugin_manager")
    
    async def discover_plugins(self) -> list[str]:
        """
        Discover available plugins.
        
        Returns:
            List of discovered plugin names
        """
        discovered = []
        for plugin_dir in self.plugin_dirs:
            # Scan for Python files or packages
            for entry in Path(plugin_dir).iterdir():
                if entry.is_file() and entry.suffix == '.py':
                    plugin_name = entry.stem
                    discovered.append(plugin_name)
                elif entry.is_dir() and (entry / '__init__.py').exists():
                    plugin_name = entry.name
                    discovered.append(plugin_name)
        return discovered
    
    async def load_plugin(self, plugin_name: str, config: dict = None) -> Plugin:
        """
        Load and setup plugin.
        
        Args:
            plugin_name: Name of plugin to load
            config: Plugin configuration
            
        Returns:
            Loaded plugin instance
            
        Raises:
            PluginLoadError: If plugin fails to load
        """
        try:
            # Import plugin module
            module = self._import_plugin(plugin_name)
            
            # Find Plugin subclass
            plugin_class = self._find_plugin_class(module)
            
            # Instantiate plugin
            plugin = plugin_class(self.bot, config)
            
            # Check dependencies
            await self._check_dependencies(plugin)
            
            # Setup plugin
            await plugin.setup()
            
            # Enable plugin
            await plugin.on_enable()
            
            # Register plugin
            self.plugins[plugin_name] = plugin
            self.plugin_modules[plugin_name] = module
            
            self.logger.info(f"Loaded plugin: {plugin_name} v{plugin.version}")
            return plugin
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            raise PluginLoadError(f"Failed to load {plugin_name}") from e
    
    async def unload_plugin(self, plugin_name: str):
        """
        Unload plugin gracefully.
        
        Args:
            plugin_name: Name of plugin to unload
        """
        if plugin_name not in self.plugins:
            raise PluginNotFoundError(f"Plugin {plugin_name} not loaded")
        
        plugin = self.plugins[plugin_name]
        
        try:
            # Disable plugin
            await plugin.on_disable()
            
            # Teardown plugin
            await plugin.teardown()
            
            # Unregister plugin
            del self.plugins[plugin_name]
            
            # Remove module from sys.modules for clean reload
            module_name = self.plugin_modules[plugin_name].__name__
            if module_name in sys.modules:
                del sys.modules[module_name]
            del self.plugin_modules[plugin_name]
            
            self.logger.info(f"Unloaded plugin: {plugin_name}")
            
        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_name}: {e}")
            raise
    
    async def reload_plugin(self, plugin_name: str):
        """
        Hot reload plugin (unload + load).
        
        Args:
            plugin_name: Name of plugin to reload
        """
        if plugin_name not in self.plugins:
            raise PluginNotFoundError(f"Plugin {plugin_name} not loaded")
        
        # Preserve config
        old_plugin = self.plugins[plugin_name]
        config = old_plugin.config
        
        # Unload
        await self.unload_plugin(plugin_name)
        
        # Brief pause to ensure cleanup
        await asyncio.sleep(0.1)
        
        # Reload
        await self.load_plugin(plugin_name, config)
        
        self.logger.info(f"Hot reloaded plugin: {plugin_name}")
    
    async def load_all(self, config: dict = None):
        """Load all discovered plugins."""
        plugins = await self.discover_plugins()
        for plugin_name in plugins:
            plugin_config = config.get(plugin_name, {}) if config else {}
            try:
                await self.load_plugin(plugin_name, plugin_config)
            except PluginLoadError as e:
                self.logger.warning(f"Skipping plugin {plugin_name}: {e}")
    
    def get_plugin(self, plugin_name: str) -> Plugin:
        """Get loaded plugin by name."""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> list[str]:
        """List loaded plugin names."""
        return list(self.plugins.keys())
```

## Hot Reload Implementation

### File System Watcher

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PluginFileHandler(FileSystemEventHandler):
    """Watch plugin files for changes."""
    
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self.reload_queue = asyncio.Queue()
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        
        if event.src_path.endswith('.py'):
            # Determine which plugin was modified
            plugin_name = self._extract_plugin_name(event.src_path)
            if plugin_name:
                self.reload_queue.put_nowait(plugin_name)
    
    async def process_reloads(self):
        """Process reload queue."""
        pending = set()
        
        while True:
            try:
                # Wait for reload event
                plugin_name = await asyncio.wait_for(
                    self.reload_queue.get(), 
                    timeout=1.0
                )
                
                # Debounce: collect changes for 0.5s
                pending.add(plugin_name)
                
                # Wait for more changes
                await asyncio.sleep(0.5)
                
                # Reload all pending plugins
                for name in pending:
                    try:
                        await self.plugin_manager.reload_plugin(name)
                    except Exception as e:
                        print(f"Hot reload failed for {name}: {e}")
                
                pending.clear()
                
            except asyncio.TimeoutError:
                # No changes, continue
                continue
```

### Configuration

```json
{
  "plugins": {
    "enabled": ["dice_roller", "quote_db", "trivia"],
    "disabled": [],
    "hot_reload": true,
    "plugin_dirs": [
      "plugins/",
      "plugins/community/"
    ],
    "plugin_config": {
      "dice_roller": {
        "max_dice": 100
      },
      "quote_db": {
        "database": "quotes.db",
        "max_quotes": 1000
      }
    }
  }
}
```

## Plugin Discovery Strategies

### 1. Directory Scanning (Primary)

```
plugins/
├── dice_roller/
│   ├── __init__.py       # Contains Plugin subclass
│   └── config.json       # Optional plugin config
├── quote_db/
│   ├── __init__.py
│   ├── database.py
│   └── config.json
└── trivia.py             # Single-file plugin
```

### 2. Entry Points (Advanced)

```python
# setup.py
setup(
    name="my-bot-plugin",
    entry_points={
        'rosey.plugins': [
            'my_plugin = my_plugin:MyPlugin',
        ]
    }
)
```

### 3. Package Discovery

Use `importlib.metadata` to find installed packages with plugins:

```python
from importlib.metadata import entry_points

def discover_entry_point_plugins():
    """Discover plugins via entry points."""
    eps = entry_points()
    if hasattr(eps, 'select'):  # Python 3.10+
        plugins = eps.select(group='rosey.plugins')
    else:
        plugins = eps.get('rosey.plugins', [])
    
    return [(ep.name, ep.load()) for ep in plugins]
```

## Plugin Configuration

### Per-Plugin Configuration

Each plugin gets its own config section:

```yaml
plugins:
  dice_roller:
    enabled: true
    max_dice: 100
    max_sides: 1000
    cooldown: 2  # seconds
  
  quote_db:
    enabled: true
    database: "data/quotes.db"
    max_quotes: 1000
    require_approval: false
  
  trivia:
    enabled: false  # Disabled
    database: "data/trivia.db"
    points_per_win: 10
```

### Configuration Schema Validation

```python
from marshmallow import Schema, fields, validate

class DiceRollerConfigSchema(Schema):
    """Configuration schema for dice roller plugin."""
    enabled = fields.Bool(default=True)
    max_dice = fields.Int(validate=validate.Range(min=1, max=1000), default=100)
    max_sides = fields.Int(validate=validate.Range(min=1, max=10000), default=1000)
    cooldown = fields.Float(validate=validate.Range(min=0, max=60), default=2.0)

class DiceRollerPlugin(Plugin):
    name = "dice_roller"
    config_schema = DiceRollerConfigSchema
    
    async def setup(self):
        # Config automatically validated against schema
        self.max_dice = self.config.get('max_dice', 100)
        self.max_sides = self.config.get('max_sides', 1000)
```

## Error Isolation & Recovery

### Plugin Sandboxing

```python
class PluginManager:
    async def _safe_call(self, plugin: Plugin, method: str, *args, **kwargs):
        """Call plugin method with error isolation."""
        try:
            method_fn = getattr(plugin, method)
            return await method_fn(*args, **kwargs)
        except Exception as e:
            self.logger.error(
                f"Plugin {plugin.name} error in {method}: {e}",
                exc_info=True
            )
            
            # Track errors
            self._record_error(plugin, method, e)
            
            # Disable plugin if too many errors
            if self._should_disable(plugin):
                self.logger.warning(f"Disabling plugin {plugin.name} due to errors")
                await self.unload_plugin(plugin.name)
            
            return None
```

### Error Recovery

```python
class PluginManager:
    async def handle_plugin_crash(self, plugin_name: str, error: Exception):
        """Handle plugin crash."""
        plugin = self.plugins.get(plugin_name)
        
        if not plugin:
            return
        
        # Log crash
        self.logger.error(f"Plugin {plugin_name} crashed: {error}")
        
        # Attempt recovery based on plugin settings
        if plugin.config.get('auto_reload_on_crash', False):
            self.logger.info(f"Attempting to reload {plugin_name}")
            try:
                await self.reload_plugin(plugin_name)
                self.logger.info(f"Successfully reloaded {plugin_name}")
            except Exception as e:
                self.logger.error(f"Failed to reload {plugin_name}: {e}")
                await self.unload_plugin(plugin_name)
        else:
            # Unload crashed plugin
            await self.unload_plugin(plugin_name)
```

## Plugin Communication

### Event Bus

```python
class PluginEventBus:
    """Event bus for inter-plugin communication."""
    
    def __init__(self):
        self.handlers: Dict[str, list] = defaultdict(list)
    
    def subscribe(self, event: str, handler, priority: int = 0):
        """Subscribe to plugin event."""
        self.handlers[event].append((priority, handler))
        self.handlers[event].sort(key=lambda x: x[0], reverse=True)
    
    def unsubscribe(self, event: str, handler):
        """Unsubscribe from plugin event."""
        self.handlers[event] = [
            (p, h) for p, h in self.handlers[event] if h != handler
        ]
    
    async def emit(self, event: str, data: Any, source: Plugin = None):
        """Emit event to subscribers."""
        for priority, handler in self.handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, data, source=source)
                else:
                    handler(event, data, source=source)
            except Exception as e:
                logging.error(f"Event handler error: {e}")
```

### Service Registry

```python
class ServiceRegistry:
    """Registry for plugin-provided services."""
    
    def __init__(self):
        self.services: Dict[str, Any] = {}
        self.providers: Dict[str, Plugin] = {}
    
    def register(self, name: str, service: Any, provider: Plugin):
        """Register service."""
        if name in self.services:
            raise ServiceAlreadyRegistered(f"Service {name} already registered")
        
        self.services[name] = service
        self.providers[name] = provider
    
    def unregister(self, name: str):
        """Unregister service."""
        if name in self.services:
            del self.services[name]
            del self.providers[name]
    
    def get(self, name: str) -> Any:
        """Get service."""
        return self.services.get(name)
    
    def list_services(self) -> list[str]:
        """List available services."""
        return list(self.services.keys())
```

## Plugin Testing

### Plugin Test Harness

```python
import pytest
from lib.plugins import Plugin
from lib.plugins.manager import PluginManager

class MockBot:
    """Mock bot for testing plugins."""
    
    def __init__(self):
        self.commands = {}
        self.handlers = defaultdict(list)
        self.messages_sent = []
    
    def register_command(self, name, handler, **options):
        self.commands[name] = (handler, options)
    
    def on(self, event, handler):
        self.handlers[event].append(handler)
    
    async def send_message(self, msg):
        self.messages_sent.append(msg)

@pytest.fixture
def mock_bot():
    return MockBot()

@pytest.fixture
async def dice_plugin(mock_bot):
    plugin = DiceRollerPlugin(mock_bot, {})
    await plugin.setup()
    return plugin

async def test_dice_roller_basic(dice_plugin, mock_bot):
    """Test basic dice roll."""
    handler = mock_bot.commands['roll'][0]
    
    await handler(None, {'msg': '!roll'})
    
    assert len(mock_bot.messages_sent) == 1
    assert '🎲' in mock_bot.messages_sent[0]
```

## Refactoring Strategy

### Phase 1: Plugin Infrastructure (Days 1-3)

**Goal:** Build core plugin system

**Steps:**
1. Create `lib/plugins/` directory structure
2. Implement `Plugin` base class
3. Implement `PluginManager` with lifecycle management
4. Implement plugin discovery (directory scanning)
5. Add plugin loading/unloading
6. Integrate with `Bot` class
7. Unit tests for plugin system

**Validation:**
- Can load/unload simple plugin
- Plugin lifecycle hooks work
- Error isolation works

### Phase 2: Hot Reload (Days 4-5)

**Goal:** Implement hot reload capability

**Steps:**
1. Add file system watcher (watchdog)
2. Implement reload queue and debouncing
3. Add reload command (`!plugin reload <name>`)
4. Test reload with state preservation
5. Add configuration for hot reload enable/disable
6. Integration tests

**Validation:**
- File changes trigger reload
- Plugin state handles reload gracefully
- No memory leaks on repeated reloads

### Phase 3: Plugin Communication (Days 6-7)

**Goal:** Enable inter-plugin communication

**Steps:**
1. Implement `PluginEventBus`
2. Implement `ServiceRegistry`
3. Add plugin-to-plugin examples
4. Document event patterns
5. Add service discovery commands

**Validation:**
- Plugins can emit/receive events
- Plugins can provide/consume services
- Event priorities work

### Phase 4: Configuration & Management (Days 8-9)

**Goal:** Production-ready configuration

**Steps:**
1. Implement per-plugin configuration
2. Add config schema validation
3. Add plugin management commands:
   - `!plugin list` - List loaded plugins
   - `!plugin enable <name>` - Enable plugin
   - `!plugin disable <name>` - Disable plugin
   - `!plugin reload <name>` - Hot reload plugin
   - `!plugin info <name>` - Plugin information
4. Add configuration file support (YAML/JSON)
5. Documentation

**Validation:**
- Config validation works
- Management commands work
- Config hot reload works

### Phase 5: Documentation & Examples (Days 10)

**Goal:** Developer experience

**Steps:**
1. Write plugin developer guide
2. Create plugin template/cookiecutter
3. Create 2-3 example plugins
4. API documentation
5. Migration guide (features → plugins)

**Validation:**
- Documentation is clear
- Examples work
- Template generates valid plugin

## Plugin Management Commands

### Command Interface

```python
# !plugin list
"""
Loaded Plugins:
  ✓ dice_roller (v1.0.0) - Roll dice
  ✓ quote_db (v0.5.0) - Quote database
  ✗ trivia (v1.2.0) - Trivia game [DISABLED]
"""

# !plugin info dice_roller
"""
Plugin: dice_roller
Version: 1.0.0
Author: YourName
Status: Enabled
Description: Roll dice with !roll command
Commands: !roll
Dependencies: None
Config:
  max_dice: 100
  max_sides: 1000
"""

# !plugin reload dice_roller
"""
♻️ Reloading dice_roller...
✓ Successfully reloaded dice_roller v1.0.0
"""

# !plugin disable trivia
"""
⏸️ Disabling trivia...
✓ Plugin trivia disabled
"""
```

## Directory Structure

```
lib/
├── plugins/
│   ├── __init__.py
│   ├── base.py              # Plugin base class
│   ├── manager.py           # PluginManager
│   ├── events.py            # PluginEventBus
│   ├── services.py          # ServiceRegistry
│   ├── loader.py            # Plugin loading utilities
│   ├── watcher.py           # Hot reload file watcher
│   └── errors.py            # Plugin-specific exceptions
│
plugins/                     # User plugins directory
├── dice_roller/
│   ├── __init__.py
│   └── config.json
├── quote_db/
│   ├── __init__.py
│   ├── database.py
│   └── config.json
└── trivia.py
│
docs/
└── 8-inception/
    ├── PRD-Inception.md
    ├── plugin-developer-guide.md
    ├── plugin-api-reference.md
    └── examples/
        ├── minimal-plugin.py
        ├── stateful-plugin.py
        └── service-provider-plugin.py
```

## Testing Strategy

### Unit Tests

**Plugin Base:**
- Test lifecycle hooks execution order
- Test error handling in hooks
- Test configuration loading

**Plugin Manager:**
- Test plugin discovery
- Test load/unload
- Test dependency resolution
- Test error isolation
- Test hot reload

**Event Bus:**
- Test event dispatch
- Test priority ordering
- Test error handling

**Service Registry:**
- Test service registration/lookup
- Test unregistration on plugin unload

### Integration Tests

**Full Stack:**
- Load multiple plugins
- Test inter-plugin communication
- Test hot reload with active plugins
- Test plugin crash recovery
- Test resource cleanup on unload

### Performance Tests

- Plugin load time (target: < 100ms per plugin)
- Hot reload time (target: < 500ms)
- Event dispatch overhead (target: < 1ms)
- Memory usage with 10+ plugins

## Success Criteria

### Functional Requirements

- ✅ Plugin base class and manager implemented
- ✅ Plugin discovery works (directory scanning)
- ✅ Plugin lifecycle works (setup, teardown, enable, disable)
- ✅ Hot reload works without bot restart
- ✅ Error isolation prevents plugin crashes affecting bot
- ✅ Plugin configuration system works
- ✅ Plugin management commands work
- ✅ Event bus enables inter-plugin communication
- ✅ Service registry enables plugin services

### Code Quality Requirements

- ✅ 100% test coverage for plugin system
- ✅ Type hints throughout
- ✅ Clear error messages for plugin failures
- ✅ No memory leaks on hot reload

### Documentation Requirements

- ✅ Plugin developer guide (comprehensive)
- ✅ Plugin API reference (all classes/methods)
- ✅ 3+ example plugins with comments
- ✅ Plugin template/starter
- ✅ Hot reload best practices guide

### Performance Requirements

- ✅ Plugin load time < 100ms
- ✅ Hot reload time < 500ms
- ✅ Event dispatch overhead < 1ms
- ✅ Memory stable across 100 reloads

## Risks & Mitigation

### Risk: Hot Reload Complexity

**Probability:** High  
**Impact:** Medium  
**Mitigation:**
- Start with simple reload (unload + load)
- Defer stateful reload to Sprint 9
- Document hot reload limitations
- Provide plugin state preservation guidelines

### Risk: Plugin Security

**Probability:** Medium  
**Impact:** High  
**Mitigation:**
- Phase 1: Trust model (all plugins trusted)
- Document security considerations
- Plan sandboxing for future sprint
- Review code before loading plugins

### Risk: Circular Dependencies

**Probability:** Low  
**Impact:** Medium  
**Mitigation:**
- Implement dependency resolution algorithm
- Detect circular deps at load time
- Clear error messages
- Document best practices (minimize deps)

### Risk: Memory Leaks on Reload

**Probability:** Medium  
**Impact:** High  
**Mitigation:**
- Careful module cleanup on unload
- Clear references in plugin manager
- Memory profiling tests
- Document resource cleanup requirements

## Timeline Estimate

**Optimistic:** 7 days (1.5 weeks)
- Assumes smooth implementation

**Realistic:** 10 days (2 weeks)
- Accounts for hot reload complexity
- Testing and edge cases

**Pessimistic:** 14 days (3 weeks)
- Major issues with hot reload
- Complex dependency resolution

## Dependencies & Blockers

### Dependencies

- **Sprint 7 Complete:** Clean module structure required
- **Python 3.10+:** For modern type hints and match statements

### New Dependencies

- `watchdog` - File system monitoring for hot reload
- `marshmallow` - Configuration schema validation (optional)
- `importlib-metadata` - Entry point discovery (stdlib in 3.10+)

## Acceptance Criteria Summary

**Sprint 8 is COMPLETE when:**

1. ✅ Plugin system implemented (`Plugin`, `PluginManager`, `EventBus`, `ServiceRegistry`)
2. ✅ Plugin discovery works (directory scanning)
3. ✅ Plugin lifecycle fully functional (setup, teardown, enable, disable)
4. ✅ Hot reload works reliably without bot restart
5. ✅ Error isolation prevents cascading failures
6. ✅ Plugin configuration system with validation
7. ✅ Plugin management commands implemented
8. ✅ 3+ example plugins created and tested
9. ✅ Plugin developer guide written
10. ✅ All tests passing (unit + integration)
11. ✅ No memory leaks across 100 hot reloads
12. ✅ Code review approved
13. ✅ Ready for Sprint 9 (battle testing with real plugins)

---

**Document Status:** Complete  
**Last Updated:** November 12, 2025  
**Next Steps:** Review PRD, create sortie specifications, prepare for Sprint 9 validation
