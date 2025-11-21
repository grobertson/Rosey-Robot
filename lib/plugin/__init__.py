"""
lib/plugin

Plugin system for extensible bot functionality.

This module provides:
- Plugin: Abstract base class for all plugins
- PluginMetadata: Plugin information and requirements
- PluginManager: Plugin discovery, loading, and lifecycle management
- HotReloadWatcher: Automatic plugin reload on file changes
- Exception hierarchy for plugin errors

Example:
    from lib.plugin import Plugin, PluginMetadata, PluginManager
    
    class MyPlugin(Plugin):
        @property
        def metadata(self):
            return PluginMetadata(
                name='my_plugin',
                display_name='My Plugin',
                version='1.0.0',
                description='Does cool stuff',
                author='Me'
            )
        
        async def setup(self):
            self.on_command('hello', self.say_hello)
        
        async def say_hello(self, username, args):
            await self.send_message(f'Hello {username}!')
    
    # Use PluginManager with hot reload
    manager = PluginManager(bot, 'plugins', hot_reload=True)
    await manager.load_all()
"""

from .base import Plugin
from .metadata import PluginMetadata
from .manager import PluginManager, PluginState, PluginInfo
from .event import Event, EventPriority
from .event_bus import EventBus
from .errors import (
    PluginError,
    PluginLoadError,
    PluginSetupError,
    PluginTeardownError,
    PluginDependencyError,
    PluginConfigError,
    PluginNotFoundError,
    PluginAlreadyLoadedError,
)

# Hot reload (optional - requires watchdog)
try:
    from .hot_reload import HotReloadWatcher, ReloadHandler

    __all__ = [
        "Plugin",
        "PluginMetadata",
        "PluginManager",
        "PluginState",
        "PluginInfo",
        "Event",
        "EventPriority",
        "EventBus",
        "HotReloadWatcher",
        "ReloadHandler",
        "PluginError",
        "PluginLoadError",
        "PluginSetupError",
        "PluginTeardownError",
        "PluginDependencyError",
        "PluginConfigError",
        "PluginNotFoundError",
        "PluginAlreadyLoadedError",
    ]
except ImportError:
    # Watchdog not installed
    __all__ = [
        "Plugin",
        "PluginMetadata",
        "PluginManager",
        "PluginState",
        "PluginInfo",
        "Event",
        "EventPriority",
        "EventBus",
        "PluginError",
        "PluginLoadError",
        "PluginSetupError",
        "PluginTeardownError",
        "PluginDependencyError",
        "PluginConfigError",
        "PluginNotFoundError",
        "PluginAlreadyLoadedError",
    ]
