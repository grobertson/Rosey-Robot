"""
Plugin Permission System

This module provides fine-grained permission controls for plugins, allowing
administrators to restrict what actions plugins can perform.

Key Components:
- Permission: Enumeration of all available permissions
- PluginPermissions: Manages granted permissions for a plugin
- PermissionValidator: Runtime permission enforcement
- Permission Profiles: Pre-configured permission sets

Architecture:
    Plugin
        ├── PluginPermissions (granted permissions)
        │   ├── Set[Permission]
        │   └── PermissionValidator
        │
        └── Runtime Actions
            ├── File I/O → Check FILE_READ/FILE_WRITE
            ├── Network → Check NETWORK_HTTP/NETWORK_SOCKET
            ├── Database → Check DATABASE_READ/DATABASE_WRITE
            └── Commands → Check COMMAND_EXECUTE

Permission Hierarchy:
    MINIMAL: Basic execution only
    STANDARD: + file read, basic network
    EXTENDED: + file write, database read
    ADMIN: All permissions (use with caution)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from pathlib import Path
from typing import Set, Dict, Optional, List, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


# ============================================================================
# Permission Definitions
# ============================================================================

class Permission(Flag):
    """
    Fine-grained permissions for plugin capabilities.

    Uses Flag enum for easy permission combination with bitwise operators.
    Example: BASIC = Permission.EXECUTE | Permission.CONFIG_READ
    """

    # Core Execution
    EXECUTE = auto()  # Basic execution permission

    # Configuration
    CONFIG_READ = auto()  # Read plugin configuration
    CONFIG_WRITE = auto()  # Modify plugin configuration

    # File System
    FILE_READ = auto()  # Read files from disk
    FILE_WRITE = auto()  # Write files to disk
    FILE_DELETE = auto()  # Delete files
    FILE_EXECUTE = auto()  # Execute files/scripts

    # Network Access
    NETWORK_HTTP = auto()  # Make HTTP/HTTPS requests
    NETWORK_SOCKET = auto()  # Create raw sockets
    NETWORK_WEBHOOK = auto()  # Register webhooks

    # Database Access
    DATABASE_READ = auto()  # Read from database
    DATABASE_WRITE = auto()  # Write to database
    DATABASE_SCHEMA = auto()  # Modify database schema

    # EventBus/Messaging
    EVENT_PUBLISH = auto()  # Publish events to EventBus
    EVENT_SUBSCRIBE = auto()  # Subscribe to events
    EVENT_BROADCAST = auto()  # Send broadcasts to all plugins

    # Platform Integration
    PLATFORM_SEND = auto()  # Send messages to platform (Cytube)
    PLATFORM_MODERATE = auto()  # Moderate platform (kick, ban, etc.)
    PLATFORM_ADMIN = auto()  # Platform admin actions

    # System Access
    SYSTEM_ENV = auto()  # Access environment variables
    SYSTEM_PROCESS = auto()  # Spawn child processes
    SYSTEM_SHELL = auto()  # Execute shell commands

    # Resource Management
    RESOURCE_MEMORY_HIGH = auto()  # Use high memory (>512MB)
    RESOURCE_CPU_HIGH = auto()  # Use high CPU (>50%)
    RESOURCE_DISK_HIGH = auto()  # Use high disk I/O

    # Plugin Management
    PLUGIN_LOAD = auto()  # Load other plugins
    PLUGIN_UNLOAD = auto()  # Unload other plugins
    PLUGIN_CONFIGURE = auto()  # Configure other plugins


# ============================================================================
# Permission Profiles
# ============================================================================

class PermissionProfile(Enum):
    """
    Pre-configured permission sets for common use cases.
    """

    MINIMAL = "minimal"  # Bare minimum permissions
    STANDARD = "standard"  # Typical plugin permissions
    EXTENDED = "extended"  # Extended capabilities
    ADMIN = "admin"  # Full access (use with caution)
    CUSTOM = "custom"  # User-defined permissions


# Pre-defined permission sets for each profile
PROFILE_PERMISSIONS: Dict[PermissionProfile, Set[Permission]] = {
    PermissionProfile.MINIMAL: {
        Permission.EXECUTE,
        Permission.CONFIG_READ,
        Permission.EVENT_SUBSCRIBE,
    },

    PermissionProfile.STANDARD: {
        Permission.EXECUTE,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.FILE_READ,
        Permission.EVENT_PUBLISH,
        Permission.EVENT_SUBSCRIBE,
        Permission.PLATFORM_SEND,
        Permission.DATABASE_READ,
        Permission.NETWORK_HTTP,
    },

    PermissionProfile.EXTENDED: {
        Permission.EXECUTE,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.EVENT_PUBLISH,
        Permission.EVENT_SUBSCRIBE,
        Permission.EVENT_BROADCAST,
        Permission.PLATFORM_SEND,
        Permission.PLATFORM_MODERATE,
        Permission.DATABASE_READ,
        Permission.DATABASE_WRITE,
        Permission.NETWORK_HTTP,
        Permission.NETWORK_WEBHOOK,
        Permission.RESOURCE_MEMORY_HIGH,
        Permission.RESOURCE_CPU_HIGH,
    },

    PermissionProfile.ADMIN: set(Permission),  # All permissions
}


# ============================================================================
# Permission Management
# ============================================================================

@dataclass
class PluginPermissions:
    """
    Manages permissions for a specific plugin.

    Tracks granted permissions, provides permission checking,
    and maintains audit trail of permission requests.
    """

    plugin_name: str
    profile: PermissionProfile = PermissionProfile.STANDARD
    granted: Set[Permission] = field(default_factory=set)
    denied_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Initialize granted permissions from profile"""
        if not self.granted:
            self.granted = PROFILE_PERMISSIONS.get(self.profile, set()).copy()

    def has_permission(self, permission: Permission) -> bool:
        """
        Check if plugin has a specific permission.

        Args:
            permission: Permission to check

        Returns:
            True if permission is granted
        """
        return permission in self.granted

    def has_all(self, *permissions: Permission) -> bool:
        """
        Check if plugin has all specified permissions.

        Args:
            *permissions: Permissions to check

        Returns:
            True if all permissions are granted
        """
        return all(p in self.granted for p in permissions)

    def has_any(self, *permissions: Permission) -> bool:
        """
        Check if plugin has any of the specified permissions.

        Args:
            *permissions: Permissions to check

        Returns:
            True if any permission is granted
        """
        return any(p in self.granted for p in permissions)

    def grant(self, *permissions: Permission) -> None:
        """
        Grant additional permissions to plugin.

        Args:
            *permissions: Permissions to grant
        """
        for p in permissions:
            self.granted.add(p)
            logger.info(f"Granted {p.name} to plugin {self.plugin_name}")

    def revoke(self, *permissions: Permission) -> None:
        """
        Revoke permissions from plugin.

        Args:
            *permissions: Permissions to revoke
        """
        for p in permissions:
            if p in self.granted:
                self.granted.remove(p)
                logger.info(f"Revoked {p.name} from plugin {self.plugin_name}")

    def grant_profile(self, profile: PermissionProfile) -> None:
        """
        Grant all permissions from a profile.

        Args:
            profile: Permission profile to grant
        """
        self.profile = profile
        profile_perms = PROFILE_PERMISSIONS.get(profile, set())
        self.granted.update(profile_perms)
        logger.info(f"Granted {profile.value} profile to plugin {self.plugin_name}")

    def check_and_log(self, permission: Permission, action: str) -> bool:
        """
        Check permission and log if denied.

        Args:
            permission: Permission to check
            action: Description of action being attempted

        Returns:
            True if permission granted, False otherwise
        """
        has_perm = self.has_permission(permission)

        if not has_perm:
            self.denied_log.append({
                "permission": permission.name,
                "action": action,
                "timestamp": __import__("time").time()
            })
            logger.warning(
                f"Permission denied for plugin {self.plugin_name}: "
                f"{permission.name} required for {action}"
            )

        return has_perm

    def get_granted_names(self) -> List[str]:
        """Get list of granted permission names"""
        return sorted([p.name for p in self.granted])

    def get_denied_count(self) -> int:
        """Get count of denied permission attempts"""
        return len(self.denied_log)

    def clear_denied_log(self) -> None:
        """Clear denied permission log"""
        self.denied_log.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize permissions to dictionary"""
        return {
            "plugin_name": self.plugin_name,
            "profile": self.profile.value,
            "granted": [p.name for p in self.granted],
            "denied_count": len(self.denied_log)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginPermissions":
        """Deserialize permissions from dictionary"""
        permissions = cls(
            plugin_name=data["plugin_name"],
            profile=PermissionProfile(data["profile"])
        )

        # Restore granted permissions
        granted_names = data.get("granted", [])
        permissions.granted = {
            getattr(Permission, name)
            for name in granted_names
            if hasattr(Permission, name)
        }

        return permissions


# ============================================================================
# Permission Validation
# ============================================================================

class PermissionError(Exception):
    """Raised when a plugin attempts an action without proper permissions"""

    def __init__(self, plugin_name: str, permission: Permission, action: str):
        self.plugin_name = plugin_name
        self.permission = permission
        self.action = action
        super().__init__(
            f"Plugin '{plugin_name}' lacks {permission.name} "
            f"permission for: {action}"
        )


class PermissionValidator:
    """
    Runtime permission validation and enforcement.

    Provides decorators and context managers for permission checks.
    """

    def __init__(self, permissions: PluginPermissions):
        """
        Initialize validator.

        Args:
            permissions: PluginPermissions instance to validate against
        """
        self.permissions = permissions

    def require(self, permission: Permission, action: str = None):
        """
        Decorator to require permission for a function.

        Args:
            permission: Required permission
            action: Description of action (defaults to function name)

        Example:
            @validator.require(Permission.FILE_READ, "read config file")
            def load_config(self):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                act = action or func.__name__
                if not self.permissions.check_and_log(permission, act):
                    raise PermissionError(
                        self.permissions.plugin_name,
                        permission,
                        act
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def require_any(self, *permissions: Permission, action: str = None):
        """
        Decorator to require any of the specified permissions.

        Args:
            *permissions: Required permissions (any)
            action: Description of action
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                act = action or func.__name__
                if not self.permissions.has_any(*permissions):
                    raise PermissionError(
                        self.permissions.plugin_name,
                        permissions[0],  # Show first permission
                        act
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def require_all(self, *permissions: Permission, action: str = None):
        """
        Decorator to require all specified permissions.

        Args:
            *permissions: Required permissions (all)
            action: Description of action
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                act = action or func.__name__
                if not self.permissions.has_all(*permissions):
                    raise PermissionError(
                        self.permissions.plugin_name,
                        permissions[0],  # Show first permission
                        act
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def check(self, permission: Permission, action: str = None) -> bool:
        """
        Check permission without raising exception.

        Args:
            permission: Permission to check
            action: Description of action

        Returns:
            True if permission granted
        """
        act = action or "unknown action"
        return self.permissions.check_and_log(permission, act)

    def assert_permission(self, permission: Permission, action: str = None) -> None:
        """
        Assert permission, raising exception if denied.

        Args:
            permission: Permission to assert
            action: Description of action

        Raises:
            PermissionError: If permission denied
        """
        act = action or "unknown action"
        if not self.permissions.check_and_log(permission, act):
            raise PermissionError(
                self.permissions.plugin_name,
                permission,
                act
            )


# ============================================================================
# Path-based Permission Helpers
# ============================================================================

@dataclass
class FileAccessPolicy:
    """
    File access policy for path-based restrictions.

    Allows/denies access to specific paths or patterns.
    """

    allowed_paths: Set[Path] = field(default_factory=set)
    denied_paths: Set[Path] = field(default_factory=set)
    allowed_patterns: List[str] = field(default_factory=list)
    denied_patterns: List[str] = field(default_factory=list)

    def is_allowed(self, path: Path) -> bool:
        """
        Check if path is allowed.

        Args:
            path: Path to check

        Returns:
            True if path is allowed
        """
        path = path.resolve()

        # Check explicit denials first
        if path in self.denied_paths:
            return False

        for denied_pattern in self.denied_patterns:
            if path.match(denied_pattern):
                return False

        # Check explicit allows
        if path in self.allowed_paths:
            return True

        for allowed_pattern in self.allowed_patterns:
            if path.match(allowed_pattern):
                return True

        # If no allowed paths specified, default to deny
        if not self.allowed_paths and not self.allowed_patterns:
            return False

        return False

    def add_allowed_path(self, path: Path) -> None:
        """Add allowed path"""
        self.allowed_paths.add(path.resolve())

    def add_denied_path(self, path: Path) -> None:
        """Add denied path"""
        self.denied_paths.add(path.resolve())

    def add_allowed_pattern(self, pattern: str) -> None:
        """Add allowed path pattern (glob)"""
        self.allowed_patterns.append(pattern)

    def add_denied_pattern(self, pattern: str) -> None:
        """Add denied path pattern (glob)"""
        self.denied_patterns.append(pattern)


def create_restricted_permissions(
    plugin_name: str,
    base_profile: PermissionProfile = PermissionProfile.MINIMAL,
    additional_permissions: Optional[Set[Permission]] = None,
    file_policy: Optional[FileAccessPolicy] = None
) -> PluginPermissions:
    """
    Create restricted permissions with custom configuration.

    Args:
        plugin_name: Name of plugin
        base_profile: Base permission profile
        additional_permissions: Additional permissions to grant
        file_policy: File access policy

    Returns:
        Configured PluginPermissions instance
    """
    permissions = PluginPermissions(
        plugin_name=plugin_name,
        profile=base_profile
    )

    if additional_permissions:
        permissions.grant(*additional_permissions)

    # Store file policy as metadata
    if file_policy:
        permissions.__dict__["_file_policy"] = file_policy

    return permissions


def get_file_policy(permissions: PluginPermissions) -> Optional[FileAccessPolicy]:
    """
    Get file access policy from permissions.

    Args:
        permissions: PluginPermissions instance

    Returns:
        FileAccessPolicy if set, None otherwise
    """
    return permissions.__dict__.get("_file_policy")


# ============================================================================
# Permission Helpers
# ============================================================================

def permission_summary(permissions: PluginPermissions) -> str:
    """
    Generate human-readable permission summary.

    Args:
        permissions: PluginPermissions instance

    Returns:
        Formatted permission summary
    """
    lines = [
        f"Plugin: {permissions.plugin_name}",
        f"Profile: {permissions.profile.value}",
        f"Granted Permissions: {len(permissions.granted)}",
    ]

    # Group permissions by category
    categories = {
        "Core": ["EXECUTE"],
        "Config": ["CONFIG_READ", "CONFIG_WRITE"],
        "File": ["FILE_READ", "FILE_WRITE", "FILE_DELETE", "FILE_EXECUTE"],
        "Network": ["NETWORK_HTTP", "NETWORK_SOCKET", "NETWORK_WEBHOOK"],
        "Database": ["DATABASE_READ", "DATABASE_WRITE", "DATABASE_SCHEMA"],
        "Events": ["EVENT_PUBLISH", "EVENT_SUBSCRIBE", "EVENT_BROADCAST"],
        "Platform": ["PLATFORM_SEND", "PLATFORM_MODERATE", "PLATFORM_ADMIN"],
        "System": ["SYSTEM_ENV", "SYSTEM_PROCESS", "SYSTEM_SHELL"],
        "Resources": ["RESOURCE_MEMORY_HIGH", "RESOURCE_CPU_HIGH", "RESOURCE_DISK_HIGH"],
        "Plugins": ["PLUGIN_LOAD", "PLUGIN_UNLOAD", "PLUGIN_CONFIGURE"],
    }

    for category, perm_names in categories.items():
        granted_in_cat = [
            name for name in perm_names
            if hasattr(Permission, name) and 
            getattr(Permission, name) in permissions.granted
        ]
        if granted_in_cat:
            lines.append(f"  {category}: {', '.join(granted_in_cat)}")

    if permissions.denied_log:
        lines.append(f"Denied Attempts: {len(permissions.denied_log)}")

    return "\n".join(lines)
