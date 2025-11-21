"""
lib/plugin

Plugin system for extensible bot functionality.

This module provides:
- Plugin: Abstract base class for all plugins
- PluginMetadata: Plugin information and requirements
- PluginManager: Plugin discovery, loading, and lifecycle management
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
    
    # Use PluginManager to load plugins
    manager = PluginManager(bot, 'plugins')
    await manager.load_all()
"""

from .base import Plugin
from .metadata import PluginMetadata
from .manager import PluginManager, PluginState, PluginInfo
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

__all__ = [
    "Plugin",
    "PluginMetadata",
    "PluginManager",
    "PluginState",
    "PluginInfo",
    "PluginError",
    "PluginLoadError",
    "PluginSetupError",
    "PluginTeardownError",
    "PluginDependencyError",
    "PluginConfigError",
    "PluginNotFoundError",
    "PluginAlreadyLoadedError",
]
