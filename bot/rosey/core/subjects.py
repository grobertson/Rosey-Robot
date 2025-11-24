"""
NATS Subject Hierarchy for Rosey Bot

This module defines the complete subject hierarchy used for all NATS communication.
Subjects follow a hierarchical pattern for organized routing and filtering.

Subject Structure:
    rosey.{category}.{specifics}...

Categories:
    - platform: Platform-specific events (cytube, discord, slack, etc.)
    - events: Normalized cross-platform events
    - commands: Command execution requests
    - plugins: Plugin-specific events
    - mediacms: MediaCMS integration
    - api: API layer communication
    - security: Security violations and alerts
    - monitoring: Health checks and metrics

Examples:
    rosey.platform.cytube.message
    rosey.events.message
    rosey.commands.trivia.execute
    rosey.plugins.markov.ready
"""

from typing import Dict, List


class Subjects:
    """
    NATS subject hierarchy constants

    Provides constants for all subject patterns used in Rosey.
    Use these constants to ensure consistency across the codebase.
    """

    # Base subject
    BASE = "rosey"

    # Top-level categories
    PLATFORM = f"{BASE}.platform"      # Platform-specific events
    EVENTS = f"{BASE}.events"          # Normalized events
    COMMANDS = f"{BASE}.commands"      # Command execution
    PLUGINS = f"{BASE}.plugins"        # Plugin events
    MEDIACMS = f"{BASE}.mediacms"      # MediaCMS integration
    API = f"{BASE}.api"                # API layer
    SECURITY = f"{BASE}.security"      # Security events
    MONITORING = f"{BASE}.monitoring"  # Health/metrics

    # Helper methods for building subjects
    @staticmethod
    def platform_subject(platform: str, event: str) -> str:
        """Build platform-specific subject"""
        return f"{Subjects.PLATFORM}.{platform}.{event}"

    @staticmethod
    def event_subject(event: str) -> str:
        """Build normalized event subject"""
        return f"{Subjects.EVENTS}.{event}"

    @staticmethod
    def command_subject(plugin: str, action: str) -> str:
        """Build command subject"""
        return f"{Subjects.COMMANDS}.{plugin}.{action}"

    @staticmethod
    def plugin_subject(plugin: str, event: str) -> str:
        """Build plugin event subject"""
        return f"{Subjects.PLUGINS}.{plugin}.{event}"

    @staticmethod
    def monitoring_subject(metric: str) -> str:
        """Build monitoring subject"""
        return f"{Subjects.MONITORING}.{metric}"


class EventTypes:
    """
    Common event type constants

    Standard event type strings used across the system.
    """

    # User events
    USER_JOIN = "user.join"
    USER_LEAVE = "user.leave"
    USER_UPDATE = "user.update"

    # Message events
    MESSAGE = "message"
    MESSAGE_DELETE = "message.delete"
    MESSAGE_EDIT = "message.edit"

    # Media events
    MEDIA_CHANGE = "media.change"
    MEDIA_QUEUE = "media.queue"
    MEDIA_DELETE = "media.delete"

    # Playlist events
    PLAYLIST_ADD = "playlist.add"
    PLAYLIST_REMOVE = "playlist.remove"
    PLAYLIST_MOVE = "playlist.move"

    # Command events
    COMMAND = "command"
    COMMAND_RESULT = "command.result"
    COMMAND_ERROR = "command.error"

    # Plugin lifecycle
    PLUGIN_START = "plugin.start"
    PLUGIN_STOP = "plugin.stop"
    PLUGIN_ERROR = "plugin.error"
    PLUGIN_READY = "plugin.ready"

    # Health events
    HEALTH_CHECK = "health.check"
    HEALTH_STATUS = "health.status"


class SubjectBuilder:
    """
    Fluent interface for building NATS subjects

    Provides a chainable API for constructing subjects with validation.

    Example:
        subject = (SubjectBuilder()
                   .platform("cytube")
                   .event("message")
                   .build())
        # Result: "rosey.platform.cytube.message"

        subject = (SubjectBuilder()
                   .command("trivia", "answer")
                   .build())
        # Result: "rosey.commands.trivia.answer"
    """

    def __init__(self):
        self._parts: List[str] = [Subjects.BASE]

    def platform(self, platform: str) -> 'SubjectBuilder':
        """Add platform category and platform name"""
        self._parts.extend(["platform", platform])
        return self

    def events(self) -> 'SubjectBuilder':
        """Add events category"""
        self._parts.append("events")
        return self

    def event(self, event: str) -> 'SubjectBuilder':
        """Add event name"""
        self._parts.append(event)
        return self

    def commands(self) -> 'SubjectBuilder':
        """Add commands category"""
        self._parts.append("commands")
        return self

    def command(self, plugin: str, action: str) -> 'SubjectBuilder':
        """Add command category, plugin, and action"""
        self._parts.extend(["commands", plugin, action])
        return self

    def plugins(self) -> 'SubjectBuilder':
        """Add plugins category"""
        self._parts.append("plugins")
        return self

    def plugin(self, plugin_name: str) -> 'SubjectBuilder':
        """Add plugin name"""
        self._parts.extend(["plugins", plugin_name])
        return self

    def monitoring(self) -> 'SubjectBuilder':
        """Add monitoring category"""
        self._parts.append("monitoring")
        return self

    def security(self) -> 'SubjectBuilder':
        """Add security category"""
        self._parts.append("security")
        return self

    def part(self, part: str) -> 'SubjectBuilder':
        """Add arbitrary part"""
        self._parts.append(part)
        return self

    def build(self) -> str:
        """Build the final subject string"""
        return ".".join(self._parts)

    def reset(self) -> 'SubjectBuilder':
        """Reset builder to start fresh"""
        self._parts = [Subjects.BASE]
        return self


# ========== Helper Functions ==========

def build_platform_subject(platform: str, event: str) -> str:
    """
    Build platform-specific subject

    Args:
        platform: Platform name (cytube, discord, slack, etc.)
        event: Event name (message, user.join, etc.)

    Returns:
        Subject string: rosey.platform.{platform}.{event}

    Example:
        >>> build_platform_subject("cytube", "message")
        'rosey.platform.cytube.message'
    """
    return f"{Subjects.PLATFORM}.{platform}.{event}"


def build_command_subject(plugin: str, action: str) -> str:
    """
    Build command subject

    Args:
        plugin: Plugin name
        action: Command action (execute, result, error)

    Returns:
        Subject string: rosey.commands.{plugin}.{action}

    Example:
        >>> build_command_subject("trivia", "execute")
        'rosey.commands.trivia.execute'
    """
    return f"{Subjects.COMMANDS}.{plugin}.{action}"


def build_plugin_subject(plugin: str, event: str) -> str:
    """
    Build plugin event subject

    Args:
        plugin: Plugin name
        event: Event name (ready, error, etc.)

    Returns:
        Subject string: rosey.plugins.{plugin}.{event}

    Example:
        >>> build_plugin_subject("markov", "ready")
        'rosey.plugins.markov.ready'
    """
    return f"{Subjects.PLUGINS}.{plugin}.{event}"


def plugin_command(plugin: str) -> str:
    """
    Get plugin's command subject pattern (for subscribing)

    Args:
        plugin: Plugin name

    Returns:
        Subject pattern: rosey.commands.{plugin}.>

    Example:
        >>> plugin_command("trivia")
        'rosey.commands.trivia.>'
    """
    return f"{Subjects.COMMANDS}.{plugin}.>"


def plugin_event(plugin: str) -> str:
    """
    Get plugin's event subject pattern (for subscribing)

    Args:
        plugin: Plugin name

    Returns:
        Subject pattern: rosey.plugins.{plugin}.>

    Example:
        >>> plugin_event("markov")
        'rosey.plugins.markov.>'
    """
    return f"{Subjects.PLUGINS}.{plugin}.>"


def validate(subject: str) -> bool:
    """
    Validate subject format

    Args:
        subject: Subject string to validate

    Returns:
        True if valid, False otherwise

    Valid subjects:
        - Must start with "rosey."
        - Parts separated by "."
        - No empty parts (no "..")
        - No leading/trailing dots
        - Can contain wildcards (* or >)

    Examples:
        >>> validate("rosey.platform.cytube.message")
        True
        >>> validate("rosey.events.*")
        True
        >>> validate("rosey.commands.trivia.>")
        True
        >>> validate("invalid")
        False
        >>> validate("rosey..invalid")
        False
    """
    if not subject:
        return False

    # Must start with base subject
    if not subject.startswith(f"{Subjects.BASE}."):
        return False

    # Split into parts
    parts = subject.split(".")

    # Check for empty parts
    if any(part == "" for part in parts):
        return False

    # At least 2 parts (rosey.something)
    if len(parts) < 2:
        return False

    # Wildcard validation
    for i, part in enumerate(parts):
        if part == ">":
            # ">" can only be at the end
            if i != len(parts) - 1:
                return False

    return True


def parse(subject: str) -> Dict[str, str]:
    """
    Parse subject into components

    Args:
        subject: Subject string to parse

    Returns:
        Dictionary with parsed components

    Examples:
        >>> parse("rosey.platform.cytube.message")
        {'base': 'rosey', 'category': 'platform', 'platform': 'cytube', 'event': 'message'}

        >>> parse("rosey.commands.trivia.answer")
        {'base': 'rosey', 'category': 'commands', 'plugin': 'trivia', 'action': 'answer'}

        >>> parse("rosey.plugins.markov.ready")
        {'base': 'rosey', 'category': 'plugins', 'plugin': 'markov', 'event': 'ready'}
    """
    if not validate(subject):
        return {}

    parts = subject.split(".")
    result = {"base": parts[0]}

    if len(parts) < 2:
        return result

    category = parts[1]
    result["category"] = category

    # Parse based on category
    if category == "platform" and len(parts) >= 4:
        result["platform"] = parts[2]
        result["event"] = ".".join(parts[3:])  # Rest is event (may have dots)

    elif category == "events" and len(parts) >= 3:
        result["event"] = ".".join(parts[2:])

    elif category == "commands" and len(parts) >= 4:
        result["plugin"] = parts[2]
        result["action"] = parts[3]

    elif category == "plugins" and len(parts) >= 4:
        result["plugin"] = parts[2]
        result["event"] = parts[3]

    elif category == "monitoring" and len(parts) >= 3:
        result["metric"] = ".".join(parts[2:])

    elif category == "security" and len(parts) >= 3:
        result["event"] = ".".join(parts[2:])

    return result


# ========== Wildcard Matching ==========

def matches_pattern(subject: str, pattern: str) -> bool:
    """
    Check if subject matches a wildcard pattern

    NATS wildcards:
        * - Matches exactly one token
        > - Matches one or more tokens (only at end)

    Args:
        subject: Subject to test
        pattern: Pattern with optional wildcards

    Returns:
        True if subject matches pattern

    Examples:
        >>> matches_pattern("rosey.platform.cytube.message", "rosey.platform.*.*")
        True
        >>> matches_pattern("rosey.platform.cytube.message", "rosey.platform.>")
        True
        >>> matches_pattern("rosey.events.message", "rosey.commands.>")
        False
    """
    subject_parts = subject.split(".")
    pattern_parts = pattern.split(".")

    # Handle ">" wildcard (matches rest)
    if pattern_parts and pattern_parts[-1] == ">":
        # Check prefix matches
        prefix_len = len(pattern_parts) - 1
        if len(subject_parts) < prefix_len:
            return False

        for i in range(prefix_len):
            if pattern_parts[i] != "*" and pattern_parts[i] != subject_parts[i]:
                return False

        return True

    # No ">" wildcard - must match exactly
    if len(subject_parts) != len(pattern_parts):
        return False

    for s, p in zip(subject_parts, pattern_parts):
        if p != "*" and p != s:
            return False

    return True
