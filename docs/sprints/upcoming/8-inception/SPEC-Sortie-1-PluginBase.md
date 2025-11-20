# Sprint 8, Sortie 1: Plugin Base Class

**Status:** Planning  
**Estimated Effort:** 4 hours  
**Sprint:** Inception (Sprint 8)  
**Phase:** 1 - Core Plugin Infrastructure  
**Dependencies:** Sprint 7 complete (adapter-based architecture)

## Objective

Design and implement the abstract `Plugin` base class that all plugins inherit from. Define lifecycle hooks, event registration, configuration management, and service access patterns.

## Background

Sprint 7 gave us clean separation: bot logic, connection, and storage. Sprint 8 adds the plugin layer - a way to extend bot functionality without modifying core code.

Plugins need:
- **Lifecycle management:** Setup, teardown, enable/disable
- **Event handlers:** Register for bot events (message, join, leave, etc.)
- **Configuration:** Plugin-specific settings
- **Service access:** Storage, connection, event bus
- **Metadata:** Name, version, description, dependencies

## Success Criteria

- ✅ Abstract `Plugin` base class defined
- ✅ Lifecycle hooks (setup, teardown, on_enable, on_disable)
- ✅ Event registration API
- ✅ Configuration management
- ✅ Service access methods
- ✅ Plugin metadata structure
- ✅ Type hints throughout

## Technical Design

### Module Structure

```
lib/
├── bot.py
├── connection/
├── storage/
└── plugin/
    ├── __init__.py          # Exports Plugin, PluginMetadata
    ├── base.py              # Plugin base class
    ├── metadata.py          # Plugin metadata structure
    └── errors.py            # Plugin-specific exceptions
```

### Plugin Metadata

```python
"""
lib/plugin/metadata.py

Plugin metadata structure.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PluginMetadata:
    """
    Plugin metadata and requirements.
    
    Attributes:
        name: Plugin identifier (lowercase, no spaces)
        display_name: Human-readable name
        version: Semantic version string
        description: Short description
        author: Plugin author
        dependencies: List of required plugin names
        min_bot_version: Minimum bot version required
        config_schema: Optional config validation schema
    """
    name: str
    display_name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = None
    min_bot_version: Optional[str] = None
    config_schema: Optional[dict] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
    
    def __str__(self) -> str:
        return f"{self.display_name} v{self.version}"
```

### Plugin Base Class

```python
"""
lib/plugin/base.py

Abstract plugin base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
import logging
from .metadata import PluginMetadata
from .errors import PluginError


class Plugin(ABC):
    """
    Abstract base class for bot plugins.
    
    Plugins extend bot functionality with modular, reloadable code.
    All plugins must inherit from this class and implement required methods.
    
    Lifecycle:
        1. __init__() - Construct plugin (fast, no I/O)
        2. setup() - Initialize plugin (async, can do I/O)
        3. on_enable() - Called when plugin enabled
        4. [plugin runs, handles events]
        5. on_disable() - Called when plugin disabled
        6. teardown() - Cleanup plugin (async)
    
    Attributes:
        bot: Bot instance (access to send_message, etc.)
        storage: Storage adapter (optional)
        config: Plugin configuration dict
        logger: Logger instance for this plugin
        is_enabled: Whether plugin is currently enabled
    """
    
    def __init__(self, bot, config: Optional[Dict[str, Any]] = None):
        """
        Initialize plugin.
        
        IMPORTANT: This should be fast (no I/O, no blocking).
        Do heavy initialization in setup().
        
        Args:
            bot: Bot instance
            config: Plugin configuration (from config file)
        """
        self.bot = bot
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.metadata.name}")
        self._is_enabled = False
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """
        Plugin metadata (name, version, description, etc.).
        
        This should be a class-level constant, not computed.
        
        Example:
            @property
            def metadata(self):
                return PluginMetadata(
                    name='dice_roller',
                    display_name='Dice Roller',
                    version='1.0.0',
                    description='Roll dice with !roll command',
                    author='YourName'
                )
        """
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Check if plugin is currently enabled."""
        return self._is_enabled
    
    @property
    def storage(self):
        """Access bot's storage adapter (may be None)."""
        return self.bot.storage
    
    # Lifecycle Hooks
    
    async def setup(self) -> None:
        """
        Initialize plugin (called once on load).
        
        Use this for:
        - Database table creation
        - Loading persistent state
        - Validating configuration
        - Registering event handlers
        - Starting background tasks
        
        Raise PluginError if setup fails.
        """
        pass
    
    async def teardown(self) -> None:
        """
        Cleanup plugin (called once on unload).
        
        Use this for:
        - Saving persistent state
        - Closing connections
        - Canceling background tasks
        - Releasing resources
        
        Should not raise exceptions (best effort cleanup).
        """
        pass
    
    async def on_enable(self) -> None:
        """
        Called when plugin is enabled.
        
        Use this for:
        - Re-registering event handlers
        - Resuming background tasks
        - Logging enable event
        
        Called after setup() on initial load.
        Called when user runs !plugin enable <name>.
        """
        self._is_enabled = True
        self.logger.info(f"{self.metadata.display_name} enabled")
    
    async def on_disable(self) -> None:
        """
        Called when plugin is disabled.
        
        Use this for:
        - Unregistering event handlers
        - Pausing background tasks
        - Logging disable event
        
        Called when user runs !plugin disable <name>.
        Plugin remains loaded but inactive.
        """
        self._is_enabled = False
        self.logger.info(f"{self.metadata.display_name} disabled")
    
    # Event Registration
    
    def on(self, event_name: str, handler: Callable) -> None:
        """
        Register event handler.
        
        Args:
            event_name: Event name ('message', 'user_join', etc.)
            handler: Async function to call on event
        
        Example:
            self.on('message', self.handle_message)
        """
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
    
    def on_message(self, handler: Callable) -> Callable:
        """
        Decorator to register message handler.
        
        Example:
            @plugin.on_message
            async def handle_message(self, username, message):
                if message.startswith('!hello'):
                    await self.send_message('Hello!')
        """
        self.on('message', handler)
        return handler
    
    def on_user_join(self, handler: Callable) -> Callable:
        """Decorator to register user join handler."""
        self.on('user_join', handler)
        return handler
    
    def on_user_leave(self, handler: Callable) -> Callable:
        """Decorator to register user leave handler."""
        self.on('user_leave', handler)
        return handler
    
    def on_command(self, command: str, handler: Callable) -> Callable:
        """
        Decorator to register command handler.
        
        Args:
            command: Command name (without !)
            handler: Async function(username, args) to call
        
        Example:
            @plugin.on_command('roll')
            async def handle_roll(self, username, args):
                # Handle !roll command
                pass
        """
        async def wrapper(username: str, message: str):
            if message.startswith(f'!{command}'):
                args = message.split()[1:]
                await handler(username, args)
        
        self.on('message', wrapper)
        return handler
    
    # Bot Interaction
    
    async def send_message(self, message: str) -> None:
        """
        Send message to channel.
        
        Convenience wrapper around bot.send_message().
        
        Args:
            message: Message text to send
        """
        await self.bot.send_message(message)
    
    # Configuration
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        
        Example:
            max_dice = self.get_config('max_dice', 10)
            api_key = self.get_config('api.key')
        """
        # Support dot notation for nested config
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    # Utility
    
    def __str__(self) -> str:
        return str(self.metadata)
    
    def __repr__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"<{self.metadata.name} v{self.metadata.version} ({status})>"
```

### Plugin Errors

```python
"""
lib/plugin/errors.py

Plugin-specific exceptions.
"""


class PluginError(Exception):
    """Base exception for plugin errors."""
    pass


class PluginLoadError(PluginError):
    """Plugin failed to load."""
    pass


class PluginSetupError(PluginError):
    """Plugin setup failed."""
    pass


class PluginDependencyError(PluginError):
    """Plugin dependency not satisfied."""
    pass


class PluginConfigError(PluginError):
    """Plugin configuration invalid."""
    pass
```

### Example Plugin

```python
"""
plugins/example_plugin.py

Example plugin demonstrating base class usage.
"""

from lib.plugin import Plugin, PluginMetadata


class ExamplePlugin(Plugin):
    """Simple example plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name='example',
            display_name='Example Plugin',
            version='1.0.0',
            description='Demonstrates plugin features',
            author='Copilot'
        )
    
    async def setup(self) -> None:
        """Initialize plugin."""
        self.logger.info("Setting up example plugin")
        
        # Register message handler
        self.on('message', self.handle_message)
        
        # Or use decorator
        @self.on_command('example')
        async def handle_example(username, args):
            await self.send_message(f"Example command from {username}")
    
    async def handle_message(self, username: str, message: str) -> None:
        """Handle chat messages."""
        if not self.is_enabled:
            return
        
        if message == '!ping':
            await self.send_message('pong!')
    
    async def teardown(self) -> None:
        """Cleanup plugin."""
        self.logger.info("Tearing down example plugin")
```

## Implementation Steps

1. **Create plugin module structure** (15 min)
   ```bash
   mkdir lib/plugin
   touch lib/plugin/__init__.py
   touch lib/plugin/base.py
   touch lib/plugin/metadata.py
   touch lib/plugin/errors.py
   ```

2. **Implement PluginMetadata** (30 min)
   - Create dataclass with all metadata fields
   - Add validation in __post_init__
   - Add __str__ method

3. **Implement Plugin base class** (2 hours)
   - Define abstract methods
   - Implement lifecycle hooks
   - Implement event registration
   - Add configuration helpers
   - Add bot interaction methods
   - Comprehensive docstrings

4. **Implement plugin errors** (15 min)
   - Create error hierarchy
   - Add docstrings

5. **Update lib/plugin/__init__.py** (10 min)
   ```python
   from .base import Plugin
   from .metadata import PluginMetadata
   from .errors import (
       PluginError,
       PluginLoadError,
       PluginSetupError,
       PluginDependencyError,
       PluginConfigError
   )
   
   __all__ = [
       'Plugin',
       'PluginMetadata',
       'PluginError',
       'PluginLoadError',
       'PluginSetupError',
       'PluginDependencyError',
       'PluginConfigError'
   ]
   ```

6. **Write unit tests** (1 hour)
   ```python
   # test/test_plugin_base.py
   
   import pytest
   from lib.plugin import Plugin, PluginMetadata, PluginError
   
   
   class MockPlugin(Plugin):
       """Mock plugin for testing."""
       
       @property
       def metadata(self):
           return PluginMetadata(
               name='mock',
               display_name='Mock Plugin',
               version='1.0.0',
               description='Test plugin',
               author='Test'
           )
   
   
   @pytest.mark.asyncio
   async def test_plugin_lifecycle(mock_bot):
       """Test plugin lifecycle."""
       plugin = MockPlugin(mock_bot)
       
       assert not plugin.is_enabled
       
       await plugin.setup()
       await plugin.on_enable()
       assert plugin.is_enabled
       
       await plugin.on_disable()
       assert not plugin.is_enabled
       
       await plugin.teardown()
   
   
   @pytest.mark.asyncio
   async def test_event_registration(mock_bot):
       """Test event handler registration."""
       plugin = MockPlugin(mock_bot)
       
       called = []
       
       @plugin.on_message
       async def handler(username, message):
           called.append((username, message))
       
       # Handler registered
       assert 'message' in plugin._event_handlers
       assert len(plugin._event_handlers['message']) == 1
   
   
   def test_config_access(mock_bot):
       """Test configuration access."""
       config = {
           'setting1': 'value1',
           'nested': {
               'setting2': 'value2'
           }
       }
       plugin = MockPlugin(mock_bot, config)
       
       assert plugin.get_config('setting1') == 'value1'
       assert plugin.get_config('nested.setting2') == 'value2'
       assert plugin.get_config('missing', 'default') == 'default'
   ```

7. **Create example plugin** (30 min)
   - Create plugins/ directory
   - Write example_plugin.py
   - Demonstrate all features

8. **Validation** (15 min)
   ```bash
   mypy lib/plugin/
   pylint lib/plugin/
   black lib/plugin/
   pytest test/test_plugin_base.py -v
   ```

## Testing Strategy

### Unit Tests

- ✅ Plugin metadata creation
- ✅ Lifecycle hooks (setup, teardown, enable, disable)
- ✅ Event registration
- ✅ Configuration access (flat and nested)
- ✅ Bot interaction methods

### Integration Tests

- ✅ Plugin with mock bot
- ✅ Multiple event handlers
- ✅ Command decorator

## Dependencies

**Python Packages:**
- None (pure Python)

**Internal Modules:**
- `lib/bot.py` (for Bot type hints)

## Validation

Before moving to Sortie 2:

1. ✅ Plugin base class defined
2. ✅ PluginMetadata structure complete
3. ✅ All lifecycle hooks present
4. ✅ Event registration works
5. ✅ Configuration access works
6. ✅ Type checking passes
7. ✅ Unit tests pass
8. ✅ Example plugin written

## Risks & Mitigations

**Risk:** Plugin API too complex  
**Mitigation:** Start minimal, extend based on real plugin needs in Sprint 9

**Risk:** Event handler conflicts  
**Mitigation:** Plugins isolated, handlers called in sequence (not parallel)

**Risk:** Configuration complexity  
**Mitigation:** Simple dict-based config, optional schema validation later

## Design Decisions

### Why Abstract Base Class?

Forces plugins to implement required methods (metadata). Type checkers can validate.

### Why Lifecycle Hooks?

Separate concerns: setup (once) vs enable (repeatable). Enables hot reload.

### Why Event Registration?

Decoupled: plugins don't need to know about bot internals. Bot dispatches to handlers.

### Why Decorator API?

More readable than manual registration:

```python
# Decorator (better)
@plugin.on_command('roll')
async def handle_roll(username, args):
    pass

# Manual (worse)
plugin.on('message', lambda u, m: handle_roll(u, m.split()[1:]) if m.startswith('!roll') else None)
```

## Next Steps

After completion, proceed to:

- **Sortie 2:** Implement PluginManager (discovery, loading, lifecycle)
- **Sortie 3:** Implement hot reload (file watching, reload logic)

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 8 - Inception
