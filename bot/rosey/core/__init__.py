"""
Rosey Core Module

Contains the foundational components for the Quicksilver architecture:
- Subject hierarchy system for NATS messaging
- EventBus wrapper for NATS pub/sub
- Plugin process isolation and resource monitoring
- Plugin permission system for security
- Plugin manager for orchestration
"""

# Subject System
from .subjects import (
    Subjects,
    EventTypes,
    SubjectBuilder,
    build_platform_subject,
    build_command_subject,
    build_plugin_subject,
    plugin_command,
    plugin_event,
    validate,
    parse,
    matches_pattern
)

# Event Bus
from .event_bus import (
    Priority,
    Event,
    EventBus,
    initialize_event_bus,
    get_event_bus,
    shutdown_event_bus
)

# Plugin Isolation
from .plugin_isolation import (
    RestartPolicy,
    RestartConfig,
    ResourceUsage,
    ResourceLimits,
    ResourceMonitor,
    PluginIPC,
    PluginState,
    PluginProcess
)

# Plugin Permissions
from .plugin_permissions import (
    Permission,
    PermissionProfile,
    PROFILE_PERMISSIONS,
    PluginPermissions,
    PermissionError,
    PermissionValidator,
    FileAccessPolicy,
    create_restricted_permissions,
    get_file_policy,
    permission_summary
)

# Plugin Manager
from .plugin_manager import (
    PluginMetadata,
    PluginEntry,
    PluginRegistry,
    PluginManager
)

from .router import (
    RouteType,
    MatchType,
    RoutePattern,
    RouteRule,
    CommandRouter
)

from .cytube_connector import (
    CytubeEventType,
    CytubeEvent,
    CytubeConnector
)

__all__ = [
    # Subjects
    "Subjects",
    "EventTypes",
    "SubjectBuilder",
    "build_platform_subject",
    "build_command_subject",
    "build_plugin_subject",
    "plugin_command",
    "plugin_event",
    "validate",
    "parse",
    "matches_pattern",
    
    # Event Bus
    "Priority",
    "Event",
    "EventBus",
    "initialize_event_bus",
    "get_event_bus",
    "shutdown_event_bus",
    
    # Plugin Isolation
    "RestartPolicy",
    "RestartConfig",
    "ResourceUsage",
    "ResourceLimits",
    "ResourceMonitor",
    "PluginIPC",
    "PluginState",
    "PluginProcess",
    
    # Plugin Permissions
    "Permission",
    "PermissionProfile",
    "PROFILE_PERMISSIONS",
    "PluginPermissions",
    "PermissionError",
    "PermissionValidator",
    "FileAccessPolicy",
    "create_restricted_permissions",
    "get_file_policy",
    "permission_summary",
    
    # Plugin Manager
    "PluginMetadata",
    "PluginEntry",
    "PluginRegistry",
    "PluginManager",
    
    # Router
    "RouteType",
    "MatchType",
    "RoutePattern",
    "RouteRule",
    "CommandRouter",
    
    # Cytube Connector
    "CytubeEventType",
    "CytubeEvent",
    "CytubeConnector"
]

from bot.rosey.core.subjects import (
    Subjects,
    EventTypes,
    SubjectBuilder,
    build_platform_subject,
    build_command_subject,
    build_plugin_subject,
    plugin_command,
    plugin_event,
    validate,
    parse,
    matches_pattern,
)

from bot.rosey.core.event_bus import (
    Event,
    Priority,
    EventBus,
    initialize_event_bus,
    get_event_bus,
    shutdown_event_bus,
)

__all__ = [
    # Subjects
    "Subjects",
    "EventTypes",
    "SubjectBuilder",
    "build_platform_subject",
    "build_command_subject",
    "build_plugin_subject",
    "plugin_command",
    "plugin_event",
    "validate",
    "parse",
    "matches_pattern",
    # EventBus
    "Event",
    "Priority",
    "EventBus",
    "initialize_event_bus",
    "get_event_bus",
    "shutdown_event_bus",
]
