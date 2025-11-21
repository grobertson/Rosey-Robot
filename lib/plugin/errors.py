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
    """Plugin setup() method failed."""
    pass


class PluginTeardownError(PluginError):
    """Plugin teardown() method failed."""
    pass


class PluginDependencyError(PluginError):
    """Plugin dependency not satisfied."""
    pass


class PluginConfigError(PluginError):
    """Plugin configuration invalid or missing."""
    pass


class PluginNotFoundError(PluginError):
    """Plugin not found or not loaded."""
    pass


class PluginAlreadyLoadedError(PluginError):
    """Plugin already loaded."""
    pass
