# Sortie 3: Subject Design & Event Model

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐☆☆☆ (Design & Standards)  
**Estimated Time:** 2 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 2 (EventBus Core)

---

## Objective

Define complete NATS subject hierarchy, create constants module, implement validation, and document event patterns for all services.

---

## Deliverables

1. ✅ Complete subject hierarchy design
2. ✅ `Subjects` constants module
3. ✅ Subject validation utilities
4. ✅ Event type registry
5. ✅ Documentation with examples
6. ✅ Subject naming standards

---

## Technical Tasks

### Task 3.1: Design Subject Hierarchy

**Principles:**

1. **Hierarchical Organization**: Use dot-separated tokens (e.g., `rosey.platform.cytube.chat`)
2. **Wildcard Support**: Design for `*` (single token) and `>` (one or more tokens)
3. **Scoped Permissions**: Enable permission control by subject prefix
4. **Versioning**: Include version for future compatibility (`v1`, `v2`)
5. **Clear Semantics**: Subject should clearly indicate purpose

**Hierarchy Design:**

```
rosey.                                   # Root namespace

  platform.                              # Platform-specific events (raw)
    cytube.                              # Cytube platform
      chat                               # Chat message
      user.join                          # User joined
      user.leave                         # User left
      media.change                       # Media changed
      media.queue                        # Media queued
      playlist.update                    # Playlist updated
    
    discord.                             # Discord (future)
      message
      member.join
      voice.join
    
    slack.                               # Slack (future)
      message
      channel.join

  events.                                # Normalized events (generic)
    message                              # Generic message
    user.join                            # Generic user join
    user.leave                           # Generic user leave
    media.change                         # Generic media change
    command.received                     # Command received
    error                                # Error event

  commands.                              # Command execution
    {plugin}.                            # Plugin-specific commands
      execute                            # Execute command
      result                             # Command result
      error                              # Command error

  plugins.                               # Plugin events
    {plugin}.                            # Plugin-specific events
      started                            # Plugin started
      stopped                            # Plugin stopped
      error                              # Plugin error
      health                             # Health check
      {custom}                           # Plugin-defined events

  mediacms.                              # MediaCMS integration
    playlist.request                     # Request playlist generation
    playlist.ready                       # Playlist generated
    playlist.error                       # Generation error
    media.metadata                       # Media metadata

  api.                                   # API layer
    request                              # API request
    response                             # API response
    error                                # API error

  security.                              # Security events
    violation                            # Permission violation
    rate_limit                           # Rate limit exceeded
    auth.failed                          # Authentication failed

  monitoring.                            # System monitoring
    health                               # Health check
    metrics                              # Metrics report
    alert                                # Alert/warning
```

---

### Task 3.2: Create Subjects Constants Module

**File:** `bot/rosey/core/subjects.py`

```python
"""
NATS subject definitions for Rosey
Centralized subject constants to prevent typos and enable IDE autocomplete
"""


class Subjects:
    """
    NATS subject hierarchy constants
    
    Usage:
        await bus.publish(Subjects.EVENTS_MESSAGE, data)
        await bus.subscribe(Subjects.PLATFORM_CYTUBE_ALL, handler)
    """
    
    # Root namespace
    ROOT = "rosey"
    
    # ========== PLATFORM EVENTS (Raw platform-specific) ==========
    
    # Cytube platform
    PLATFORM_CYTUBE = f"{ROOT}.platform.cytube"
    PLATFORM_CYTUBE_CHAT = f"{PLATFORM_CYTUBE}.chat"
    PLATFORM_CYTUBE_USER_JOIN = f"{PLATFORM_CYTUBE}.user.join"
    PLATFORM_CYTUBE_USER_LEAVE = f"{PLATFORM_CYTUBE}.user.leave"
    PLATFORM_CYTUBE_MEDIA_CHANGE = f"{PLATFORM_CYTUBE}.media.change"
    PLATFORM_CYTUBE_MEDIA_QUEUE = f"{PLATFORM_CYTUBE}.media.queue"
    PLATFORM_CYTUBE_PLAYLIST_UPDATE = f"{PLATFORM_CYTUBE}.playlist.update"
    PLATFORM_CYTUBE_ALL = f"{PLATFORM_CYTUBE}.>"  # All Cytube events
    
    # Discord platform (future)
    PLATFORM_DISCORD = f"{ROOT}.platform.discord"
    PLATFORM_DISCORD_MESSAGE = f"{PLATFORM_DISCORD}.message"
    PLATFORM_DISCORD_MEMBER_JOIN = f"{PLATFORM_DISCORD}.member.join"
    PLATFORM_DISCORD_VOICE_JOIN = f"{PLATFORM_DISCORD}.voice.join"
    PLATFORM_DISCORD_ALL = f"{PLATFORM_DISCORD}.>"
    
    # Slack platform (future)
    PLATFORM_SLACK = f"{ROOT}.platform.slack"
    PLATFORM_SLACK_MESSAGE = f"{PLATFORM_SLACK}.message"
    PLATFORM_SLACK_CHANNEL_JOIN = f"{PLATFORM_SLACK}.channel.join"
    PLATFORM_SLACK_ALL = f"{PLATFORM_SLACK}.>"
    
    # All platform events
    PLATFORM_ALL = f"{ROOT}.platform.>"
    
    # ========== NORMALIZED EVENTS (Generic, platform-agnostic) ==========
    
    EVENTS = f"{ROOT}.events"
    EVENTS_MESSAGE = f"{EVENTS}.message"
    EVENTS_USER_JOIN = f"{EVENTS}.user.join"
    EVENTS_USER_LEAVE = f"{EVENTS}.user.leave"
    EVENTS_MEDIA_CHANGE = f"{EVENTS}.media.change"
    EVENTS_COMMAND_RECEIVED = f"{EVENTS}.command.received"
    EVENTS_ERROR = f"{EVENTS}.error"
    EVENTS_ALL = f"{EVENTS}.>"
    
    # ========== COMMANDS ==========
    
    COMMANDS = f"{ROOT}.commands"
    
    @staticmethod
    def plugin_command(plugin_name: str, command: str = None) -> str:
        """
        Generate plugin command subject
        
        Args:
            plugin_name: Plugin identifier (e.g., 'trivia', 'markov')
            command: Specific command (e.g., 'execute', 'result')
                     If None, returns wildcard for all commands
        
        Returns:
            Subject string
        
        Example:
            Subjects.plugin_command('trivia', 'execute')
            # Returns: 'rosey.commands.trivia.execute'
            
            Subjects.plugin_command('trivia')
            # Returns: 'rosey.commands.trivia.>'
        """
        base = f"{Subjects.COMMANDS}.{plugin_name}"
        if command:
            return f"{base}.{command}"
        return f"{base}.>"
    
    # Common command types
    COMMAND_EXECUTE = "execute"
    COMMAND_RESULT = "result"
    COMMAND_ERROR = "error"
    
    # ========== PLUGINS ==========
    
    PLUGINS = f"{ROOT}.plugins"
    
    @staticmethod
    def plugin_event(plugin_name: str, event: str = None) -> str:
        """
        Generate plugin event subject
        
        Args:
            plugin_name: Plugin identifier
            event: Specific event type (e.g., 'started', 'error')
                   If None, returns wildcard for all events
        
        Returns:
            Subject string
        
        Example:
            Subjects.plugin_event('trivia', 'game_started')
            # Returns: 'rosey.plugins.trivia.game_started'
        """
        base = f"{Subjects.PLUGINS}.{plugin_name}"
        if event:
            return f"{base}.{event}"
        return f"{base}.>"
    
    # Common plugin events
    PLUGIN_STARTED = "started"
    PLUGIN_STOPPED = "stopped"
    PLUGIN_ERROR = "error"
    PLUGIN_HEALTH = "health"
    
    # ========== MEDIACMS ==========
    
    MEDIACMS = f"{ROOT}.mediacms"
    MEDIACMS_PLAYLIST_REQUEST = f"{MEDIACMS}.playlist.request"
    MEDIACMS_PLAYLIST_READY = f"{MEDIACMS}.playlist.ready"
    MEDIACMS_PLAYLIST_ERROR = f"{MEDIACMS}.playlist.error"
    MEDIACMS_MEDIA_METADATA = f"{MEDIACMS}.media.metadata"
    MEDIACMS_ALL = f"{MEDIACMS}.>"
    
    # ========== API ==========
    
    API = f"{ROOT}.api"
    API_REQUEST = f"{API}.request"
    API_RESPONSE = f"{API}.response"
    API_ERROR = f"{API}.error"
    API_ALL = f"{API}.>"
    
    # ========== SECURITY ==========
    
    SECURITY = f"{ROOT}.security"
    SECURITY_VIOLATION = f"{SECURITY}.violation"
    SECURITY_RATE_LIMIT = f"{SECURITY}.rate_limit"
    SECURITY_AUTH_FAILED = f"{SECURITY}.auth.failed"
    SECURITY_ALL = f"{SECURITY}.>"
    
    # ========== MONITORING ==========
    
    MONITORING = f"{ROOT}.monitoring"
    MONITORING_HEALTH = f"{MONITORING}.health"
    MONITORING_METRICS = f"{MONITORING}.metrics"
    MONITORING_ALERT = f"{MONITORING}.alert"
    MONITORING_ALL = f"{MONITORING}.>"
    
    # ========== VALIDATION ==========
    
    @staticmethod
    def validate(subject: str) -> bool:
        """
        Validate subject format
        
        Rules:
        - Must start with 'rosey.'
        - Tokens separated by '.'
        - Only alphanumeric, '.', '_', '-', '*', '>'
        - '*' and '>' only at end
        
        Args:
            subject: Subject to validate
        
        Returns:
            True if valid
        
        Example:
            Subjects.validate("rosey.events.message")  # True
            Subjects.validate("rosey.events.>")        # True
            Subjects.validate("invalid.subject")       # False
        """
        if not subject.startswith(f"{Subjects.ROOT}."):
            return False
        
        # Check characters
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789._->")
        if not all(c in allowed_chars for c in subject.lower()):
            return False
        
        # Check wildcard positions
        if '*' in subject or '>' in subject:
            # Wildcards only at end
            if not (subject.endswith('.*') or subject.endswith('.>')):
                return False
        
        return True
    
    @staticmethod
    def parse(subject: str) -> dict:
        """
        Parse subject into components
        
        Args:
            subject: Subject string
        
        Returns:
            Dictionary with components
        
        Example:
            Subjects.parse("rosey.platform.cytube.chat")
            # Returns: {
            #   'root': 'rosey',
            #   'category': 'platform',
            #   'subcategory': 'cytube',
            #   'event': 'chat',
            #   'tokens': ['rosey', 'platform', 'cytube', 'chat']
            # }
        """
        tokens = subject.split('.')
        
        result = {
            'tokens': tokens,
            'root': tokens[0] if len(tokens) > 0 else None,
            'category': tokens[1] if len(tokens) > 1 else None,
            'subcategory': tokens[2] if len(tokens) > 2 else None,
            'event': tokens[3] if len(tokens) > 3 else None,
        }
        
        return result


# Event type constants
class EventTypes:
    """
    Standard event type identifiers
    """
    
    # Messages
    MESSAGE = "message"
    COMMAND = "command"
    
    # User events
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    USER_UPDATE = "user_update"
    
    # Media events
    MEDIA_CHANGE = "media_change"
    MEDIA_QUEUE = "media_queue"
    MEDIA_DELETE = "media_delete"
    
    # Playlist events
    PLAYLIST_UPDATE = "playlist_update"
    PLAYLIST_LOCK = "playlist_lock"
    PLAYLIST_CLEAR = "playlist_clear"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    SYSTEM_HEALTH = "system_health"
    
    # Plugin events
    PLUGIN_START = "plugin_start"
    PLUGIN_STOP = "plugin_stop"
    PLUGIN_ERROR = "plugin_error"
    PLUGIN_RESULT = "plugin_result"
```

---

### Task 3.3: Subject Builder Utility

**File:** `bot/rosey/core/subject_builder.py`

```python
"""
Subject builder utilities
Helper functions for constructing NATS subjects
"""
from typing import List


class SubjectBuilder:
    """
    Fluent interface for building NATS subjects
    
    Example:
        subject = (SubjectBuilder()
            .root("rosey")
            .category("commands")
            .plugin("trivia")
            .action("execute")
            .build())
        # Returns: "rosey.commands.trivia.execute"
    """
    
    def __init__(self):
        self._tokens: List[str] = []
    
    def root(self, root: str) -> 'SubjectBuilder':
        """Set root namespace"""
        self._tokens.append(root)
        return self
    
    def category(self, category: str) -> 'SubjectBuilder':
        """Set category (platform, events, commands, etc.)"""
        self._tokens.append(category)
        return self
    
    def subcategory(self, subcategory: str) -> 'SubjectBuilder':
        """Set subcategory (cytube, discord, etc.)"""
        self._tokens.append(subcategory)
        return self
    
    def plugin(self, plugin_name: str) -> 'SubjectBuilder':
        """Set plugin name"""
        self._tokens.append(plugin_name)
        return self
    
    def action(self, action: str) -> 'SubjectBuilder':
        """Set action/event"""
        self._tokens.append(action)
        return self
    
    def token(self, token: str) -> 'SubjectBuilder':
        """Add arbitrary token"""
        self._tokens.append(token)
        return self
    
    def wildcard_one(self) -> 'SubjectBuilder':
        """Add single-token wildcard (*)"""
        self._tokens.append('*')
        return self
    
    def wildcard_many(self) -> 'SubjectBuilder':
        """Add multi-token wildcard (>)"""
        self._tokens.append('>')
        return self
    
    def build(self) -> str:
        """Build subject string"""
        return '.'.join(self._tokens)
    
    def __str__(self) -> str:
        return self.build()


# Convenience functions

def build_platform_subject(platform: str, event: str) -> str:
    """
    Build platform-specific subject
    
    Args:
        platform: Platform name (cytube, discord, slack)
        event: Event name
    
    Returns:
        Subject string
    
    Example:
        build_platform_subject("cytube", "chat")
        # Returns: "rosey.platform.cytube.chat"
    """
    return f"rosey.platform.{platform}.{event}"


def build_command_subject(plugin: str, action: str = "execute") -> str:
    """
    Build command subject
    
    Args:
        plugin: Plugin name
        action: Action (execute, result, error)
    
    Returns:
        Subject string
    
    Example:
        build_command_subject("trivia", "execute")
        # Returns: "rosey.commands.trivia.execute"
    """
    return f"rosey.commands.{plugin}.{action}"


def build_plugin_subject(plugin: str, event: str) -> str:
    """
    Build plugin event subject
    
    Args:
        plugin: Plugin name
        event: Event type
    
    Returns:
        Subject string
    
    Example:
        build_plugin_subject("trivia", "game_started")
        # Returns: "rosey.plugins.trivia.game_started"
    """
    return f"rosey.plugins.{plugin}.{event}"
```

---

### Task 3.4: Unit Tests

**File:** `tests/core/test_subjects.py`

```python
"""
Tests for subject constants and validation
"""
import pytest
from bot.rosey.core.subjects import Subjects, EventTypes
from bot.rosey.core.subject_builder import (
    SubjectBuilder,
    build_platform_subject,
    build_command_subject,
    build_plugin_subject
)


def test_subject_constants():
    """Test subject constant values"""
    assert Subjects.ROOT == "rosey"
    assert Subjects.EVENTS_MESSAGE == "rosey.events.message"
    assert Subjects.PLATFORM_CYTUBE_CHAT == "rosey.platform.cytube.chat"


def test_plugin_command_subject():
    """Test plugin command subject generation"""
    assert Subjects.plugin_command("trivia", "execute") == "rosey.commands.trivia.execute"
    assert Subjects.plugin_command("trivia") == "rosey.commands.trivia.>"


def test_plugin_event_subject():
    """Test plugin event subject generation"""
    assert Subjects.plugin_event("markov", "response") == "rosey.plugins.markov.response"
    assert Subjects.plugin_event("markov") == "rosey.plugins.markov.>"


def test_subject_validation():
    """Test subject validation"""
    # Valid subjects
    assert Subjects.validate("rosey.events.message")
    assert Subjects.validate("rosey.platform.cytube.chat")
    assert Subjects.validate("rosey.events.>")
    assert Subjects.validate("rosey.commands.*")
    
    # Invalid subjects
    assert not Subjects.validate("invalid.subject")
    assert not Subjects.validate("rosey")
    assert not Subjects.validate("rosey.*.events")  # Wildcard not at end
    assert not Subjects.validate("rosey.events.@invalid")  # Invalid char


def test_subject_parsing():
    """Test subject parsing"""
    parsed = Subjects.parse("rosey.platform.cytube.chat")
    
    assert parsed['root'] == 'rosey'
    assert parsed['category'] == 'platform'
    assert parsed['subcategory'] == 'cytube'
    assert parsed['event'] == 'chat'
    assert len(parsed['tokens']) == 4


def test_subject_builder():
    """Test fluent subject builder"""
    subject = (SubjectBuilder()
        .root("rosey")
        .category("commands")
        .plugin("trivia")
        .action("execute")
        .build())
    
    assert subject == "rosey.commands.trivia.execute"


def test_subject_builder_wildcards():
    """Test wildcard building"""
    subject = (SubjectBuilder()
        .root("rosey")
        .category("events")
        .wildcard_many()
        .build())
    
    assert subject == "rosey.events.>"


def test_convenience_functions():
    """Test convenience builder functions"""
    assert build_platform_subject("cytube", "chat") == "rosey.platform.cytube.chat"
    assert build_command_subject("trivia") == "rosey.commands.trivia.execute"
    assert build_plugin_subject("markov", "response") == "rosey.plugins.markov.response"


def test_event_types():
    """Test event type constants"""
    assert EventTypes.MESSAGE == "message"
    assert EventTypes.USER_JOIN == "user_join"
    assert EventTypes.MEDIA_CHANGE == "media_change"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Documentation

Create `docs/architecture/SUBJECT-DESIGN.md`:

```markdown
# NATS Subject Design

## Subject Hierarchy

```
rosey.
  platform.{platform}.{event}    # Platform-specific (raw)
  events.{event}                 # Normalized (generic)
  commands.{plugin}.{action}     # Command execution
  plugins.{plugin}.{event}       # Plugin events
  mediacms.*                     # MediaCMS integration
  api.*                          # API layer
  security.*                     # Security events
  monitoring.*                   # Monitoring/health
```

## Usage Examples

### Subscribe to all messages

```python
from bot.rosey.core.subjects import Subjects

await bus.subscribe(Subjects.EVENTS_MESSAGE, handle_message)
```

### Subscribe to all Cytube events

```python
await bus.subscribe(Subjects.PLATFORM_CYTUBE_ALL, handle_cytube_event)
```

### Publish command

```python
subject = Subjects.plugin_command("trivia", "execute")
await bus.publish(subject, {"action": "start"})
```

### Plugin publishes event

```python
subject = Subjects.plugin_event("trivia", "game_started")
await bus.publish(subject, {"game_id": 123})
```

## Wildcards

- `*` matches exactly one token: `rosey.platform.*` matches `rosey.platform.cytube`
- `>` matches one or more tokens: `rosey.platform.>` matches `rosey.platform.cytube.chat`

## Naming Conventions

1. **Lowercase**: All subjects lowercase
2. **Dots**: Use dots for hierarchy (not slashes or colons)
3. **Underscores**: Use underscores within tokens (`user_join` not `user-join`)
4. **Descriptive**: Clear semantic meaning
5. **Hierarchical**: Most general → most specific

## Permission Design

Subjects enable fine-grained permissions:

```python
# Plugin sandbox permissions
ALLOWED_SUBSCRIPTIONS = [
    "rosey.events.>",                      # All normalized events
    f"rosey.commands.{plugin_name}.>",     # Own commands only
]

ALLOWED_PUBLICATIONS = [
    f"rosey.plugins.{plugin_name}.>",      # Own events only
]
```

## JetStream Streams

Subjects are organized into JetStream streams:

- `PLATFORM_EVENTS`: `rosey.platform.>`
- `COMMANDS`: `rosey.commands.>`
- `PLUGINS`: `rosey.plugins.>`
- `MONITORING`: `rosey.monitoring.>`
```

---

## Success Criteria

✅ Complete subject hierarchy defined  
✅ `Subjects` constants module created  
✅ Subject validation working  
✅ Builder utilities implemented  
✅ Unit tests passing (100% coverage)  
✅ Documentation complete with examples  

---

## Time Breakdown

- Subject hierarchy design: 30 minutes
- Constants module: 45 minutes
- Builder utilities: 30 minutes
- Unit tests: 30 minutes
- Documentation: 15 minutes

**Total: 2.5 hours**

---

## Next Steps

- → Sortie 4: Cytube Connector Extraction
- → Extract Cytube logic from bot core
- → Implement event translation layer
