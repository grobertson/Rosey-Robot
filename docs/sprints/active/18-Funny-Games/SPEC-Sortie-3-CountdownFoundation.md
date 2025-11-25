# SPEC: Sortie 3 - Countdown Plugin Foundation

**Sprint:** 18 - Funny Games  
**Sortie:** 3 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** HIGH - Foundation for advanced countdown

---

## 1. Overview

### 1.1 Purpose

The Countdown plugin provides time tracking for events, demonstrating:

- Stateful plugin with persistence
- Timer management (asyncio-based)
- Channel-scoped data
- Event-driven updates

This sortie establishes the **foundation** with one-time countdowns. Sortie 4 adds recurring and advanced features.

### 1.2 Scope

**In Scope (Sortie 3):**
- `!countdown <name> <datetime>` - Create countdown
- `!countdown <name>` - Check remaining time
- `!countdown list` - List active countdowns
- `!countdown delete <name>` - Remove countdown
- One-time countdowns
- Automatic announcement at T-0
- Database persistence
- Channel-scoped countdowns

**Out of Scope (Sortie 4):**
- Recurring countdowns
- Channel-specific recurring events
- T-minus alerts (5 min, 1 min warnings)
- Timezone handling (UTC only in Sortie 3)

### 1.3 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Database service (Sprint 17)
- Event bus (existing)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/countdown/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── countdown.py          # Countdown model and logic
├── scheduler.py          # Timer/scheduling logic
├── storage.py            # Database operations
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_countdown.py    # Unit tests for model
    ├── test_scheduler.py    # Unit tests for scheduler
    ├── test_storage.py      # Storage tests
    └── test_plugin.py       # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.countdown.create` | Subscribe | Handle `!countdown <name> <datetime>` |
| `rosey.command.countdown.check` | Subscribe | Handle `!countdown <name>` |
| `rosey.command.countdown.list` | Subscribe | Handle `!countdown list` |
| `rosey.command.countdown.delete` | Subscribe | Handle `!countdown delete <name>` |
| `countdown.created` | Publish | Event when countdown created |
| `countdown.completed` | Publish | Event when countdown reaches T-0 |
| `countdown.deleted` | Publish | Event when countdown removed |

### 2.3 Message Schemas

#### Create Request (incoming)
```json
{
  "channel": "string",
  "user": "string",
  "args": "movie_night 2025-12-01 20:00",
  "reply_to": "rosey.reply.abc123"
}
```

#### Create Response (outgoing)
```json
{
  "success": true,
  "result": {
    "name": "movie_night",
    "target_time": "2025-12-01T20:00:00Z",
    "created_by": "user123",
    "channel": "lobby",
    "remaining": "6 days, 4 hours, 30 minutes",
    "message": "⏰ Countdown 'movie_night' created! Time remaining: 6 days, 4 hours, 30 minutes"
  }
}
```

#### Check Response (outgoing)
```json
{
  "success": true,
  "result": {
    "name": "movie_night",
    "target_time": "2025-12-01T20:00:00Z",
    "remaining": "6 days, 4 hours, 30 minutes",
    "message": "⏰ 'movie_night' — 6 days, 4 hours, 30 minutes remaining"
  }
}
```

#### List Response (outgoing)
```json
{
  "success": true,
  "result": {
    "countdowns": [
      {"name": "movie_night", "remaining": "6d 4h 30m"},
      {"name": "birthday", "remaining": "14d 2h 15m"}
    ],
    "message": "⏰ Active countdowns:\n• movie_night — 6d 4h 30m\n• birthday — 14d 2h 15m"
  }
}
```

#### Completed Event (published to channel)
```json
{
  "event": "countdown.completed",
  "timestamp": "2025-12-01T20:00:00Z",
  "channel": "lobby",
  "countdown": {
    "name": "movie_night",
    "created_by": "user123"
  },
  "message": "🎉 TIME'S UP! 'movie_night' has arrived!"
}
```

### 2.4 Database Schema

```sql
CREATE TABLE countdown (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    target_time TIMESTAMP NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_rule TEXT NULL,  -- For Sortie 4
    completed BOOLEAN DEFAULT FALSE,
    
    UNIQUE(channel, name)  -- Names unique per channel
);

CREATE INDEX idx_countdown_channel ON countdown(channel);
CREATE INDEX idx_countdown_target ON countdown(target_time) WHERE completed = FALSE;
```

### 2.5 Class Design

```python
# plugins/countdown/countdown.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class Countdown:
    """Represents a countdown timer."""
    id: Optional[int]
    name: str
    channel: str
    target_time: datetime
    created_by: str
    created_at: datetime
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    completed: bool = False
    
    @property
    def remaining(self) -> timedelta:
        """Time remaining until target."""
        now = datetime.utcnow()
        if now >= self.target_time:
            return timedelta(0)
        return self.target_time - now
    
    @property
    def is_expired(self) -> bool:
        """Check if countdown has passed."""
        return datetime.utcnow() >= self.target_time
    
    def format_remaining(self, short: bool = False) -> str:
        """
        Format remaining time as human-readable string.
        
        Args:
            short: If True, use abbreviated format (e.g., "6d 4h 30m")
        
        Returns:
            Formatted time string
        """
        ...
    
    @classmethod
    def parse_datetime(cls, time_str: str) -> datetime:
        """
        Parse user input into datetime.
        
        Supported formats:
        - "2025-12-01 20:00"
        - "2025-12-01T20:00:00"
        - "tomorrow 20:00"
        - "in 2 hours"
        - "next friday 19:00"
        
        Raises:
            ValueError: If format not recognized
        """
        ...
```

```python
# plugins/countdown/scheduler.py

import asyncio
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional
import logging


class CountdownScheduler:
    """
    Manages countdown timers using asyncio.
    
    Uses a single task that checks countdowns at regular intervals
    rather than creating one task per countdown.
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,  # Check every 30 seconds
        on_complete: Optional[Callable] = None
    ):
        self.check_interval = check_interval
        self.on_complete = on_complete
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._pending: Dict[str, datetime] = {}  # countdown_id -> target_time
        self.logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the scheduler loop."""
        ...
    
    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        ...
    
    def schedule(self, countdown_id: str, target_time: datetime) -> None:
        """Add a countdown to track."""
        ...
    
    def cancel(self, countdown_id: str) -> bool:
        """Remove a countdown from tracking. Returns True if found."""
        ...
    
    async def _check_loop(self) -> None:
        """Main loop that checks for completed countdowns."""
        ...
    
    def _get_completed(self) -> list[str]:
        """Get list of countdown IDs that have completed."""
        ...
```

```python
# plugins/countdown/storage.py

from typing import List, Optional
from common.database_service import DatabaseService
from .countdown import Countdown


class CountdownStorage:
    """Database operations for countdowns using DatabaseService."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def create_table(self) -> None:
        """Create countdown table if not exists."""
        ...
    
    async def create(self, countdown: Countdown) -> Countdown:
        """Insert new countdown, return with ID."""
        ...
    
    async def get_by_name(self, channel: str, name: str) -> Optional[Countdown]:
        """Get countdown by channel and name."""
        ...
    
    async def get_all_for_channel(self, channel: str) -> List[Countdown]:
        """Get all active countdowns for a channel."""
        ...
    
    async def get_all_pending(self) -> List[Countdown]:
        """Get all non-completed countdowns across all channels."""
        ...
    
    async def mark_completed(self, countdown_id: int) -> None:
        """Mark a countdown as completed."""
        ...
    
    async def delete(self, channel: str, name: str) -> bool:
        """Delete a countdown. Returns True if found and deleted."""
        ...
```

```python
# plugins/countdown/plugin.py

from lib.plugin.base import PluginBase
from common.database_service import get_database_service
from .countdown import Countdown
from .scheduler import CountdownScheduler
from .storage import CountdownStorage


class CountdownPlugin(PluginBase):
    """
    Countdown timer plugin.
    
    Commands:
        !countdown <name> <datetime> - Create a countdown
        !countdown <name> - Check remaining time
        !countdown list - List all countdowns
        !countdown delete <name> - Delete a countdown
    """
    
    NAME = "countdown"
    VERSION = "1.0.0"
    DESCRIPTION = "Track countdowns to events"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        self.storage: Optional[CountdownStorage] = None
        self.scheduler: Optional[CountdownScheduler] = None
    
    async def setup(self) -> None:
        """Initialize storage, scheduler, and subscriptions."""
        # Initialize storage
        db_service = await get_database_service()
        self.storage = CountdownStorage(db_service)
        await self.storage.create_table()
        
        # Initialize scheduler with completion callback
        self.scheduler = CountdownScheduler(
            check_interval=self.config.get("check_interval", 30.0),
            on_complete=self._on_countdown_complete
        )
        
        # Load existing countdowns into scheduler
        pending = await self.storage.get_all_pending()
        for countdown in pending:
            self.scheduler.schedule(
                f"{countdown.channel}:{countdown.name}",
                countdown.target_time
            )
        
        # Start scheduler
        await self.scheduler.start()
        
        # Subscribe to commands
        await self.subscribe("rosey.command.countdown.create", self._handle_create)
        await self.subscribe("rosey.command.countdown.check", self._handle_check)
        await self.subscribe("rosey.command.countdown.list", self._handle_list)
        await self.subscribe("rosey.command.countdown.delete", self._handle_delete)
        
        self.logger.info(f"{self.NAME} plugin loaded with {len(pending)} pending countdowns")
    
    async def teardown(self) -> None:
        """Stop scheduler and cleanup."""
        if self.scheduler:
            await self.scheduler.stop()
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_create(self, msg) -> None:
        """Handle !countdown <name> <datetime>."""
        ...
    
    async def _handle_check(self, msg) -> None:
        """Handle !countdown <name>."""
        ...
    
    async def _handle_list(self, msg) -> None:
        """Handle !countdown list."""
        ...
    
    async def _handle_delete(self, msg) -> None:
        """Handle !countdown delete <name>."""
        ...
    
    async def _on_countdown_complete(self, countdown_id: str) -> None:
        """Called when a countdown reaches T-0."""
        channel, name = countdown_id.split(":", 1)
        countdown = await self.storage.get_by_name(channel, name)
        
        if countdown and not countdown.completed:
            # Mark as completed
            await self.storage.mark_completed(countdown.id)
            
            # Announce to channel
            await self._announce_completion(countdown)
            
            # Emit event
            await self._emit_completed_event(countdown)
    
    async def _announce_completion(self, countdown: Countdown) -> None:
        """Send completion message to channel."""
        ...
    
    async def _emit_completed_event(self, countdown: Countdown) -> None:
        """Emit countdown.completed event."""
        ...
```

### 2.6 Configuration

```json
{
  "check_interval": 30.0,
  "max_countdowns_per_channel": 20,
  "max_duration_days": 365,
  "emit_events": true,
  "announce_completion": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `check_interval` | float | 30.0 | Seconds between scheduler checks |
| `max_countdowns_per_channel` | int | 20 | Max active countdowns per channel |
| `max_duration_days` | int | 365 | Max days in future for countdown |
| `emit_events` | bool | true | Emit NATS events |
| `announce_completion` | bool | true | Announce T-0 to channel |

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/countdown/` directory
2. Create all files with docstrings
3. Create `config.json` with defaults
4. Create test file structure

### Step 2: Implement Countdown Model (1.5 hours)

1. Implement `Countdown` dataclass
2. Implement `remaining` property
3. Implement `format_remaining()` with short format
4. Implement `parse_datetime()` with multiple formats
5. Write unit tests for parsing and formatting

### Step 3: Implement Scheduler (2 hours)

1. Implement `CountdownScheduler.__init__()`
2. Implement `start()` and `stop()` lifecycle
3. Implement `schedule()` and `cancel()`
4. Implement `_check_loop()` with proper asyncio handling
5. Write unit tests for scheduler behavior

### Step 4: Implement Storage (1.5 hours)

1. Implement table creation
2. Implement CRUD operations
3. Implement `get_all_pending()` for restart recovery
4. Write tests with test database

### Step 5: Implement Plugin (2 hours)

1. Implement `setup()` with storage, scheduler init
2. Implement countdown recovery on startup
3. Implement all command handlers
4. Implement completion callback and announcement
5. Implement event emission

### Step 6: Integration Testing (1 hour)

1. Test full flow: create → check → complete
2. Test persistence across restarts
3. Test channel isolation
4. Test concurrent countdowns

### Step 7: Documentation (30 minutes)

1. Write README.md with examples
2. Document datetime formats
3. Document configuration

---

## 4. Test Cases

### 4.1 Countdown Model Tests

| Test | Validation |
|------|------------|
| Parse "2025-12-01 20:00" | Returns correct datetime |
| Parse "tomorrow 14:00" | Returns next day at 14:00 |
| Parse "in 2 hours" | Returns now + 2 hours |
| Parse invalid string | Raises ValueError |
| Format 6d 4h 30m (long) | "6 days, 4 hours, 30 minutes" |
| Format 6d 4h 30m (short) | "6d 4h 30m" |
| Format < 1 minute | "less than a minute" |
| is_expired for past time | Returns True |
| is_expired for future time | Returns False |

### 4.2 Scheduler Tests

| Scenario | Expected |
|----------|----------|
| Schedule countdown | Added to pending |
| Cancel countdown | Removed from pending |
| Countdown expires | on_complete called |
| Multiple countdowns | All tracked independently |
| Stop scheduler | Loop terminates cleanly |
| Restart scheduler | Resumes checking |

### 4.3 Storage Tests

| Operation | Validation |
|-----------|------------|
| Create countdown | Returns with ID |
| Create duplicate | Raises/returns error |
| Get by name | Returns correct countdown |
| Get all for channel | Returns only that channel |
| Get all pending | Excludes completed |
| Mark completed | Updates completed flag |
| Delete countdown | Returns True, count decreases |

### 4.4 Plugin Integration Tests

| Scenario | Expected |
|----------|----------|
| `!countdown test 2025-12-01 20:00` | Creates countdown, responds |
| `!countdown test` | Shows remaining time |
| `!countdown list` | Lists all channel countdowns |
| `!countdown delete test` | Removes countdown |
| Countdown reaches T-0 | Announces, marks complete |
| Plugin restart | Recovers pending countdowns |
| Max countdowns exceeded | Returns error |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Invalid datetime format | "❌ Couldn't parse that time. Try: '2025-12-01 20:00' or 'tomorrow 19:00'" |
| Countdown not found | "❌ No countdown named 'xyz' found in this channel" |
| Name already exists | "❌ A countdown named 'xyz' already exists. Delete it first or use a different name." |
| Date in past | "❌ That time has already passed! Pick a future time." |
| Max countdowns reached | "❌ This channel has reached the limit of {N} countdowns. Delete some first." |
| Duration too long | "❌ That's too far in the future. Max is {N} days." |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| Database unavailable | Log error, respond with "temporary issue" message |
| Scheduler task failure | Log, attempt restart |
| NATS timeout | Log, use fallback response |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!countdown <name> <datetime>` creates countdown
- [ ] `!countdown <name>` shows remaining time
- [ ] `!countdown list` shows all channel countdowns
- [ ] `!countdown delete <name>` removes countdown
- [ ] Countdown announced at T-0
- [ ] Channel isolation (can't see other channels' countdowns)
- [ ] Persistence across restarts

### 6.2 Technical

- [ ] Plugin loads without errors
- [ ] Scheduler runs efficiently (single loop, not per-countdown)
- [ ] Database operations use parameterized queries
- [ ] Events emitted correctly
- [ ] Test coverage > 85%

### 6.3 Documentation

- [ ] README.md with examples
- [ ] Supported datetime formats documented
- [ ] Configuration documented

---

## 7. Sample Interactions

```
User: !countdown movie_night 2025-12-01 20:00
Rosey: ⏰ Countdown 'movie_night' created! Time remaining: 6 days, 4 hours, 30 minutes

User: !countdown movie_night
Rosey: ⏰ 'movie_night' — 6 days, 4 hours, 28 minutes remaining

User: !countdown birthday tomorrow 14:00
Rosey: ⏰ Countdown 'birthday' created! Time remaining: 18 hours, 15 minutes

User: !countdown list
Rosey: ⏰ Active countdowns:
  • movie_night — 6d 4h 28m
  • birthday — 18h 15m

[At T-0]
Rosey: 🎉 TIME'S UP! 'movie_night' has arrived!

User: !countdown delete birthday
Rosey: ⏰ Countdown 'birthday' deleted.

User: !countdown nonexistent
Rosey: ❌ No countdown named 'nonexistent' found in this channel
```

---

## 8. Future Enhancements (Sortie 4)

These are **NOT** in scope for Sortie 3:

- Recurring countdowns (`!countdown friday_movie every friday 19:00`)
- Channel-specific recurring events
- T-minus alerts (5 min, 1 min warnings)
- Timezone support (`!countdown ... EST`)
- User-specific countdowns (DM reminders)

---

## 9. Checklist

### Pre-Implementation
- [ ] Review quote-db plugin for storage patterns
- [ ] Review database_service API
- [ ] Test datetime parsing library options

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement Countdown model
- [ ] Implement CountdownScheduler
- [ ] Implement CountdownStorage
- [ ] Implement CountdownPlugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real times
- [ ] Verify persistence after restart
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add countdown plugin foundation

- Implement one-time countdown timers
- Add datetime parsing (multiple formats)
- Add persistent storage
- Add asyncio-based scheduler
- Announce completion at T-0

Implements: SPEC-Sortie-3-CountdownFoundation.md
Related: PRD-Funny-Games.md
```
