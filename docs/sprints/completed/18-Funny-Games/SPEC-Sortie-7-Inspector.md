# SPEC: Sortie 7 - Plugin Inspector

**Sprint:** 18 - Funny Games  
**Sortie:** 7 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** MEDIUM - Important for observability and debugging

---

## 1. Overview

### 1.1 Purpose

The Plugin Inspector provides runtime observability into the NATS event bus, demonstrating:

- Wildcard event subscription
- Event logging and filtering
- Runtime plugin introspection
- Admin-focused tooling
- Service exposure pattern (InspectorService)

### 1.2 Scope

**In Scope:**
- `!inspect events [pattern]` - Show recent events matching pattern
- `!inspect plugins` - List loaded plugins
- `!inspect plugin <name>` - Show plugin details
- `!inspect stats` - Show event statistics
- `!inspect pause` / `!inspect resume` - Control logging
- Event stream logging (configurable)
- Event filtering by subject pattern
- InspectorService for programmatic access
- Rate-limited to admins

**Out of Scope:**
- Full event replay/history (beyond buffer)
- Event modification/injection
- Performance profiling
- Memory profiling

### 1.3 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Plugin manager (existing)
- Event bus (existing)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/inspector/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── service.py            # InspectorService (exposed to other plugins)
├── buffer.py             # Circular event buffer
├── filters.py            # Event filtering logic
├── formatters.py         # Event display formatting
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_buffer.py       # Buffer tests
    ├── test_filters.py      # Filter tests
    ├── test_service.py      # Service tests
    └── test_plugin.py       # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `>` | Subscribe | Wildcard subscription to ALL events |
| `rosey.command.inspect.events` | Subscribe | Handle `!inspect events` |
| `rosey.command.inspect.plugins` | Subscribe | Handle `!inspect plugins` |
| `rosey.command.inspect.plugin` | Subscribe | Handle `!inspect plugin` |
| `rosey.command.inspect.stats` | Subscribe | Handle `!inspect stats` |
| `rosey.command.inspect.pause` | Subscribe | Handle `!inspect pause` |
| `rosey.command.inspect.resume` | Subscribe | Handle `!inspect resume` |
| `inspector.event.captured` | Publish | (Optional) Event when notable event captured |

### 2.3 Message Schemas

#### Events Request
```json
{
  "channel": "lobby",
  "user": "admin",
  "args": "trivia.*",
  "reply_to": "rosey.reply.abc123"
}
```

#### Events Response
```json
{
  "success": true,
  "result": {
    "pattern": "trivia.*",
    "count": 5,
    "events": [
      {
        "timestamp": "2025-12-01T20:00:00.123Z",
        "subject": "trivia.game.started",
        "size_bytes": 256,
        "preview": "{\"game_id\": \"abc123\", \"channel\": ...}"
      }
    ],
    "message": "📡 Last 5 events matching 'trivia.*':\n\n[20:00:00] trivia.game.started (256B)\n..."
  }
}
```

#### Plugins Response
```json
{
  "success": true,
  "result": {
    "plugins": [
      {
        "name": "trivia",
        "version": "1.0.0",
        "status": "active",
        "subscriptions": 4
      }
    ],
    "message": "🔌 Loaded Plugins:\n\n• trivia v1.0.0 (active) - 4 subs\n• countdown v1.0.0 (active) - 4 subs"
  }
}
```

#### Stats Response
```json
{
  "success": true,
  "result": {
    "total_events": 1542,
    "events_per_second": 2.3,
    "buffer_size": 1000,
    "buffer_used": 856,
    "top_subjects": [
      {"subject": "rosey.chat.message", "count": 523},
      {"subject": "trivia.answer.*", "count": 234}
    ],
    "message": "📊 Inspector Stats:\n\n• Total: 1,542 events\n• Rate: 2.3/sec\n• Buffer: 856/1000"
  }
}
```

### 2.4 Class Design

```python
# plugins/inspector/buffer.py

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Iterator
from collections import deque
import json


@dataclass
class CapturedEvent:
    """A captured NATS event."""
    timestamp: datetime
    subject: str
    data: bytes
    size_bytes: int
    
    @property
    def data_decoded(self) -> Optional[dict]:
        """Attempt to decode data as JSON."""
        try:
            return json.loads(self.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    
    @property
    def preview(self) -> str:
        """Get a preview of the data (truncated)."""
        try:
            text = self.data.decode()
            if len(text) > 100:
                return text[:100] + "..."
            return text
        except UnicodeDecodeError:
            return f"<binary {self.size_bytes} bytes>"
    
    def matches_pattern(self, pattern: str) -> bool:
        """Check if subject matches a glob-like pattern."""
        ...


class EventBuffer:
    """
    Circular buffer for storing recent events.
    
    Thread-safe for append and iteration.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._buffer: deque[CapturedEvent] = deque(maxlen=max_size)
        self._total_count = 0
        self._subject_counts: dict[str, int] = {}
    
    def append(self, event: CapturedEvent) -> None:
        """Add an event to the buffer."""
        self._buffer.append(event)
        self._total_count += 1
        
        # Track subject counts
        # Normalize to base subject (remove trailing segments for wildcards)
        base_subject = self._normalize_subject(event.subject)
        self._subject_counts[base_subject] = self._subject_counts.get(base_subject, 0) + 1
    
    def get_recent(
        self, 
        count: int = 10, 
        pattern: Optional[str] = None
    ) -> List[CapturedEvent]:
        """
        Get recent events, optionally filtered by pattern.
        
        Args:
            count: Max number of events to return
            pattern: Glob-like pattern to filter (e.g., "trivia.*")
        
        Returns:
            List of matching events, most recent first
        """
        ...
    
    def get_stats(self) -> dict:
        """Get buffer statistics."""
        return {
            "total_events": self._total_count,
            "buffer_size": self.max_size,
            "buffer_used": len(self._buffer),
            "top_subjects": self._get_top_subjects(10),
        }
    
    def _get_top_subjects(self, limit: int) -> List[dict]:
        """Get most common subjects."""
        sorted_subjects = sorted(
            self._subject_counts.items(),
            key=lambda x: -x[1]
        )[:limit]
        return [{"subject": s, "count": c} for s, c in sorted_subjects]
    
    def _normalize_subject(self, subject: str) -> str:
        """Normalize subject for counting (collapse numbered segments)."""
        ...
    
    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        self._subject_counts.clear()
        # Keep total count for lifetime stats
```

```python
# plugins/inspector/filters.py

import re
from fnmatch import fnmatch
from typing import List, Optional


class EventFilter:
    """
    Filter events by subject pattern.
    
    Supports glob-like patterns:
    - * matches single segment (e.g., trivia.* matches trivia.start)
    - ** matches multiple segments (e.g., trivia.** matches trivia.game.started)
    - ? matches single character
    """
    
    def __init__(self, pattern: str):
        self.pattern = pattern
        self._regex = self._compile_pattern(pattern)
    
    def matches(self, subject: str) -> bool:
        """Check if subject matches the pattern."""
        return bool(self._regex.match(subject))
    
    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Convert glob pattern to regex."""
        # Handle NATS-style wildcards
        # * = single token
        # > = all remaining tokens
        regex = pattern
        regex = regex.replace(".", r"\.")
        regex = regex.replace("**", r".*")
        regex = regex.replace("*", r"[^.]*")
        regex = regex.replace(">", r".*")
        return re.compile(f"^{regex}$")


class FilterChain:
    """Chain of filters (include/exclude)."""
    
    def __init__(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        self.include_filters = [EventFilter(p) for p in (include or [])]
        self.exclude_filters = [EventFilter(p) for p in (exclude or [])]
    
    def should_capture(self, subject: str) -> bool:
        """Determine if an event should be captured."""
        # If exclude matches, reject
        for f in self.exclude_filters:
            if f.matches(subject):
                return False
        
        # If no include filters, accept all
        if not self.include_filters:
            return True
        
        # If include filters exist, must match one
        for f in self.include_filters:
            if f.matches(subject):
                return True
        
        return False
```

```python
# plugins/inspector/service.py

from typing import List, Optional, Callable
from .buffer import EventBuffer, CapturedEvent
from .filters import FilterChain


class InspectorService:
    """
    Service exposed to other plugins for inspection.
    
    Example usage from another plugin:
        inspector = await get_service("inspector")
        events = inspector.get_recent_events(pattern="trivia.*")
    """
    
    def __init__(self, buffer: EventBuffer, filter_chain: FilterChain):
        self._buffer = buffer
        self._filter_chain = filter_chain
        self._paused = False
        self._subscribers: List[Callable] = []
    
    @property
    def is_paused(self) -> bool:
        """Check if capturing is paused."""
        return self._paused
    
    def pause(self) -> None:
        """Pause event capturing."""
        self._paused = True
    
    def resume(self) -> None:
        """Resume event capturing."""
        self._paused = False
    
    def get_recent_events(
        self, 
        count: int = 10, 
        pattern: Optional[str] = None
    ) -> List[CapturedEvent]:
        """Get recent events, optionally filtered."""
        return self._buffer.get_recent(count, pattern)
    
    def get_stats(self) -> dict:
        """Get capture statistics."""
        return self._buffer.get_stats()
    
    def subscribe(self, callback: Callable[[CapturedEvent], None]) -> None:
        """Subscribe to captured events (for real-time streaming)."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable) -> None:
        """Unsubscribe from captured events."""
        self._subscribers.remove(callback)
    
    def _notify_subscribers(self, event: CapturedEvent) -> None:
        """Notify all subscribers of a new event."""
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                pass  # Don't let subscriber errors break capture
```

```python
# plugins/inspector/plugin.py

from datetime import datetime
from lib.plugin.base import PluginBase
from .buffer import EventBuffer, CapturedEvent
from .filters import FilterChain
from .service import InspectorService


class InspectorPlugin(PluginBase):
    """
    Plugin inspector for runtime observability.
    
    Commands (admin only):
        !inspect events [pattern] - Show recent events
        !inspect plugins - List loaded plugins
        !inspect plugin <name> - Show plugin details
        !inspect stats - Show event statistics
        !inspect pause - Pause event capturing
        !inspect resume - Resume event capturing
    """
    
    NAME = "inspector"
    VERSION = "1.0.0"
    DESCRIPTION = "Runtime inspection and debugging"
    ADMIN_ONLY = True
    
    def __init__(self, nats_client, config: dict = None, plugin_manager=None):
        super().__init__(nats_client, config)
        self.plugin_manager = plugin_manager
        
        # Initialize buffer and filter
        buffer_size = self.config.get("buffer_size", 1000)
        self.buffer = EventBuffer(max_size=buffer_size)
        
        self.filter_chain = FilterChain(
            include=self.config.get("include_patterns"),
            exclude=self.config.get("exclude_patterns", [
                "_INBOX.*",  # NATS internal
                "inspector.*",  # Avoid self-reference
            ]),
        )
        
        # Initialize service
        self.service = InspectorService(self.buffer, self.filter_chain)
    
    async def setup(self) -> None:
        """Register handlers and start wildcard subscription."""
        # Subscribe to ALL events with wildcard
        await self.subscribe(">", self._capture_event)
        
        # Register command handlers
        await self.subscribe("rosey.command.inspect.events", self._handle_events)
        await self.subscribe("rosey.command.inspect.plugins", self._handle_plugins)
        await self.subscribe("rosey.command.inspect.plugin", self._handle_plugin)
        await self.subscribe("rosey.command.inspect.stats", self._handle_stats)
        await self.subscribe("rosey.command.inspect.pause", self._handle_pause)
        await self.subscribe("rosey.command.inspect.resume", self._handle_resume)
        
        # Register service for other plugins
        await self.register_service("inspector", self.service)
        
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup."""
        await self.unregister_service("inspector")
        self.buffer.clear()
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _capture_event(self, msg) -> None:
        """Capture incoming event (wildcard handler)."""
        if self.service.is_paused:
            return
        
        if not self.filter_chain.should_capture(msg.subject):
            return
        
        event = CapturedEvent(
            timestamp=datetime.utcnow(),
            subject=msg.subject,
            data=msg.data,
            size_bytes=len(msg.data),
        )
        
        self.buffer.append(event)
        self.service._notify_subscribers(event)
    
    async def _handle_events(self, msg) -> None:
        """Handle !inspect events [pattern]."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        pattern = data.get("args", "").strip() or None
        count = self.config.get("default_event_count", 10)
        
        events = self.buffer.get_recent(count, pattern)
        
        if not events:
            pattern_msg = f" matching '{pattern}'" if pattern else ""
            return await self._reply(msg, f"📡 No recent events{pattern_msg}")
        
        lines = [f"📡 Last {len(events)} events" + (f" matching '{pattern}':" if pattern else ":")]
        
        for event in events:
            time_str = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            lines.append(f"\n[{time_str}] {event.subject} ({event.size_bytes}B)")
            lines.append(f"  {event.preview}")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_plugins(self, msg) -> None:
        """Handle !inspect plugins."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        if not self.plugin_manager:
            return await self._reply_error(msg, "Plugin manager not available")
        
        plugins = self.plugin_manager.get_loaded_plugins()
        
        if not plugins:
            return await self._reply(msg, "🔌 No plugins loaded")
        
        lines = ["🔌 Loaded Plugins:\n"]
        
        for plugin in plugins:
            status = "active" if plugin.is_active else "inactive"
            subs = len(plugin.subscriptions) if hasattr(plugin, "subscriptions") else "?"
            lines.append(f"• {plugin.NAME} v{plugin.VERSION} ({status}) - {subs} subs")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_plugin(self, msg) -> None:
        """Handle !inspect plugin <name>."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        name = data.get("args", "").strip()
        if not name:
            return await self._reply_usage(msg, "plugin <name>")
        
        if not self.plugin_manager:
            return await self._reply_error(msg, "Plugin manager not available")
        
        plugin = self.plugin_manager.get_plugin(name)
        if not plugin:
            return await self._reply_error(msg, f"Plugin '{name}' not found")
        
        lines = [f"🔌 Plugin: {plugin.NAME}\n"]
        lines.append(f"• Version: {plugin.VERSION}")
        lines.append(f"• Description: {plugin.DESCRIPTION}")
        lines.append(f"• Status: {'active' if plugin.is_active else 'inactive'}")
        
        if hasattr(plugin, "subscriptions"):
            lines.append(f"\n📡 Subscriptions:")
            for sub in plugin.subscriptions[:10]:  # Limit to 10
                lines.append(f"  • {sub}")
            if len(plugin.subscriptions) > 10:
                lines.append(f"  ... and {len(plugin.subscriptions) - 10} more")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_stats(self, msg) -> None:
        """Handle !inspect stats."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        stats = self.buffer.get_stats()
        
        lines = ["📊 Inspector Stats:\n"]
        lines.append(f"• Total Events: {stats['total_events']:,}")
        lines.append(f"• Buffer: {stats['buffer_used']}/{stats['buffer_size']}")
        lines.append(f"• Status: {'PAUSED' if self.service.is_paused else 'Active'}")
        
        if stats["top_subjects"]:
            lines.append("\n📈 Top Subjects:")
            for item in stats["top_subjects"][:5]:
                lines.append(f"  • {item['subject']}: {item['count']:,}")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_pause(self, msg) -> None:
        """Handle !inspect pause."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        self.service.pause()
        await self._reply(msg, "📡 Event capturing paused")
    
    async def _handle_resume(self, msg) -> None:
        """Handle !inspect resume."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        self.service.resume()
        await self._reply(msg, "📡 Event capturing resumed")
    
    async def _check_admin(self, user: str) -> bool:
        """Check if user is an admin."""
        admins = self.config.get("admins", [])
        return user in admins or not admins  # If no admins configured, allow all
```

### 2.5 Configuration

```json
{
  "buffer_size": 1000,
  "default_event_count": 10,
  "include_patterns": null,
  "exclude_patterns": [
    "_INBOX.*",
    "inspector.*"
  ],
  "admins": [],
  "log_to_file": false,
  "log_file_path": "inspector.log"
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `buffer_size` | int | 1000 | Max events to store |
| `default_event_count` | int | 10 | Default events to show |
| `include_patterns` | list | null | Patterns to include (null = all) |
| `exclude_patterns` | list | [...] | Patterns to exclude |
| `admins` | list | [] | Users allowed to use inspect commands |
| `log_to_file` | bool | false | Also log events to file |
| `log_file_path` | str | "inspector.log" | Path to log file |

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/inspector/` directory
2. Create all files with docstrings
3. Create `config.json` with defaults

### Step 2: Implement Event Buffer (1.5 hours)

1. Implement `CapturedEvent` dataclass
2. Implement `EventBuffer` class
3. Implement circular buffer with deque
4. Implement pattern matching
5. Implement statistics tracking
6. Write comprehensive tests

### Step 3: Implement Filter System (1 hour)

1. Implement `EventFilter` class
2. Implement glob-to-regex conversion
3. Implement `FilterChain` class
4. Test various patterns

### Step 4: Implement InspectorService (1 hour)

1. Implement service class
2. Implement pause/resume
3. Implement subscriber pattern
4. Write tests

### Step 5: Implement Plugin (2 hours)

1. Implement wildcard subscription
2. Implement `_capture_event()`
3. Implement all command handlers
4. Implement admin check
5. Implement service registration

### Step 6: Plugin Manager Integration (1 hour)

1. Update plugin to receive plugin_manager
2. Implement plugin listing
3. Implement plugin detail view
4. Test with real plugins

### Step 7: Testing (1 hour)

1. Test event capture
2. Test pattern filtering
3. Test admin restriction
4. Test buffer overflow

### Step 8: Documentation (30 minutes)

1. Write README.md with examples
2. Document all commands
3. Document configuration

---

## 4. Test Cases

### 4.1 Event Buffer Tests

| Test | Validation |
|------|------------|
| Append event | Event in buffer |
| Buffer overflow | Oldest events removed |
| Get recent | Returns correct count |
| Pattern filter | Only matching events |
| Statistics | Correct counts |

### 4.2 Filter Tests

| Pattern | Subject | Matches? |
|---------|---------|----------|
| `trivia.*` | `trivia.start` | Yes |
| `trivia.*` | `trivia.game.start` | No |
| `trivia.**` | `trivia.game.start` | Yes |
| `trivia.>` | `trivia.game.start` | Yes |
| `*.start` | `trivia.start` | Yes |
| `_INBOX.*` | `_INBOX.123` | Yes |

### 4.3 Service Tests

| Scenario | Expected |
|----------|----------|
| Pause then capture | No events captured |
| Resume then capture | Events captured |
| Subscribe callback | Callback called |
| Unsubscribe | Callback not called |

### 4.4 Plugin Tests

| Command | Expected |
|---------|----------|
| `!inspect events` | Shows last 10 |
| `!inspect events trivia.*` | Shows filtered |
| `!inspect plugins` | Lists plugins |
| `!inspect plugin trivia` | Shows details |
| `!inspect stats` | Shows statistics |
| Non-admin user | "Admin only" error |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Non-admin | "Admin only command" |
| Unknown plugin | "Plugin 'xyz' not found" |
| Empty pattern result | "No recent events matching..." |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| JSON decode error | Skip event, log warning |
| Subscriber exception | Catch, continue |
| Plugin manager unavailable | Return error message |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!inspect events` shows recent events
- [ ] `!inspect events <pattern>` filters correctly
- [ ] `!inspect plugins` lists all plugins
- [ ] `!inspect plugin <name>` shows details
- [ ] `!inspect stats` shows statistics
- [ ] `!inspect pause/resume` controls capture
- [ ] Admin restriction enforced
- [ ] Events captured in real-time
- [ ] Buffer handles overflow gracefully

### 6.2 Technical

- [ ] Wildcard subscription works
- [ ] Pattern matching correct
- [ ] Service exposed to other plugins
- [ ] Test coverage > 85%

### 6.3 Documentation

- [ ] README.md with examples
- [ ] All patterns documented
- [ ] Configuration documented

---

## 7. Sample Interactions

```
Admin: !inspect events
Rosey: 📡 Last 10 events:

       [20:00:00.123] trivia.game.started (256B)
         {"game_id": "abc123", "channel": "lobby", ...}
       
       [20:00:01.456] trivia.question.asked (512B)
         {"question_number": 1, "difficulty": "easy", ...}
       
       [20:00:05.789] trivia.answer.correct (128B)
         {"user": "player1", "points": 12, ...}

Admin: !inspect events countdown.*
Rosey: 📡 Last 3 events matching 'countdown.*':

       [19:55:00.000] countdown.completed (64B)
         {"name": "movie_night", "channel": "lobby"}
       
       [19:50:00.000] countdown.alert (48B)
         {"minutes_remaining": 5, "name": "movie_night"}

Admin: !inspect plugins
Rosey: 🔌 Loaded Plugins:

       • trivia v1.0.0 (active) - 4 subs
       • countdown v1.0.0 (active) - 4 subs
       • quote-db v1.0.0 (active) - 5 subs
       • inspector v1.0.0 (active) - 7 subs

Admin: !inspect plugin trivia
Rosey: 🔌 Plugin: trivia

       • Version: 1.0.0
       • Description: Interactive trivia game
       • Status: active

       📡 Subscriptions:
         • rosey.command.trivia.start
         • rosey.command.trivia.stop
         • rosey.command.trivia.answer
         • rosey.command.trivia.skip

Admin: !inspect stats
Rosey: 📊 Inspector Stats:

       • Total Events: 1,542
       • Buffer: 856/1000
       • Status: Active

       📈 Top Subjects:
         • rosey.chat.message: 523
         • trivia.answer.*: 234
         • countdown.*: 45

Admin: !inspect pause
Rosey: 📡 Event capturing paused

Admin: !inspect resume
Rosey: 📡 Event capturing resumed

User: !inspect events
Rosey: ❌ Admin only command
```

---

## 8. Checklist

### Pre-Implementation
- [ ] Review NATS wildcard subscription docs
- [ ] Understand plugin manager API
- [ ] Design pattern matching

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement EventBuffer
- [ ] Implement EventFilter and FilterChain
- [ ] Implement InspectorService
- [ ] Implement InspectorPlugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real events
- [ ] Verify admin restriction
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add inspector plugin

- Implement wildcard event capture
- Add circular event buffer
- Add pattern-based filtering
- Add plugin introspection
- Expose InspectorService for other plugins
- Admin-only access control

Implements: SPEC-Sortie-7-Inspector.md
Related: PRD-Funny-Games.md
```
