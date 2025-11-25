# SPEC: Sortie 4 - Countdown Plugin Advanced Features

**Sprint:** 18 - Funny Games  
**Sortie:** 4 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** MEDIUM - Depends on Sortie 3  
**Prerequisites:** Sortie 3 (Countdown Foundation)

---

## 1. Overview

### 1.1 Purpose

Extend the Countdown plugin with advanced features:

- **Recurring countdowns** (weekly movie nights, daily standups)
- **T-minus alerts** (5 min, 1 min warnings)
- **Channel-specific presets** (Friday 19:00 for lobby)
- **Timezone support** (optional, UTC default)

### 1.2 Scope

**In Scope:**
- `!countdown <name> every <pattern>` - Recurring countdown
- `!countdown alerts <name> <minutes>` - Set T-minus alerts
- `!countdown pause <name>` / `!countdown resume <name>` - Control recurring
- Recurring patterns: daily, weekly (day + time), monthly
- Alert system (5 min, 1 min before)
- Recurrence auto-reset after completion

**Out of Scope:**
- Complex cron expressions
- Multi-channel linked countdowns
- User-specific timezone preferences

### 1.3 Dependencies

- Sortie 3 (Countdown Foundation) - MUST be complete
- Existing Countdown model, storage, scheduler
- Event bus for alerts

---

## 2. Technical Design

### 2.1 Extended File Structure

Additions to existing plugin:

```
plugins/countdown/
├── ...existing files...
├── recurrence.py         # Recurrence pattern parsing & calculation
├── alerts.py             # T-minus alert logic
└── tests/
    ├── ...existing tests...
    ├── test_recurrence.py   # Recurrence pattern tests
    └── test_alerts.py       # Alert timing tests
```

### 2.2 New NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.countdown.alerts` | Subscribe | Handle `!countdown alerts` |
| `rosey.command.countdown.pause` | Subscribe | Handle `!countdown pause` |
| `rosey.command.countdown.resume` | Subscribe | Handle `!countdown resume` |
| `countdown.alert` | Publish | T-minus alert event |
| `countdown.recurring.reset` | Publish | Event when recurring resets |

### 2.3 Message Schemas

#### Create Recurring Request
```json
{
  "channel": "lobby",
  "user": "admin",
  "args": "friday_movie every friday 19:00",
  "reply_to": "rosey.reply.abc123"
}
```

#### Create Recurring Response
```json
{
  "success": true,
  "result": {
    "name": "friday_movie",
    "pattern": "every friday 19:00",
    "next_occurrence": "2025-12-06T19:00:00Z",
    "remaining": "4 days, 5 hours, 30 minutes",
    "is_recurring": true,
    "message": "⏰🔄 Recurring countdown 'friday_movie' created! Next: Friday at 7:00 PM (4 days, 5 hours)"
  }
}
```

#### Alert Event (published)
```json
{
  "event": "countdown.alert",
  "timestamp": "2025-12-06T18:55:00Z",
  "channel": "lobby",
  "countdown": {
    "name": "friday_movie",
    "target_time": "2025-12-06T19:00:00Z"
  },
  "minutes_remaining": 5,
  "message": "⏰ 5 minutes until 'friday_movie'!"
}
```

#### Recurring Reset Event
```json
{
  "event": "countdown.recurring.reset",
  "timestamp": "2025-12-06T19:00:00Z",
  "channel": "lobby",
  "countdown": {
    "name": "friday_movie",
    "previous_target": "2025-12-06T19:00:00Z",
    "next_target": "2025-12-13T19:00:00Z"
  }
}
```

### 2.4 Extended Database Schema

Add columns to existing table (via migration):

```sql
-- Migration: Add recurrence and alert columns
ALTER TABLE countdown ADD COLUMN recurrence_rule TEXT NULL;
ALTER TABLE countdown ADD COLUMN is_paused BOOLEAN DEFAULT FALSE;
ALTER TABLE countdown ADD COLUMN alert_minutes TEXT NULL;  -- JSON array: [5, 1]
ALTER TABLE countdown ADD COLUMN last_alert_sent INTEGER NULL;  -- Minutes value of last alert
```

### 2.5 Recurrence Pattern Design

```python
# plugins/countdown/recurrence.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import re


class RecurrenceType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class RecurrenceRule:
    """
    Represents a recurrence pattern.
    
    Examples:
        "every day 09:00" -> RecurrenceRule(DAILY, time=09:00)
        "every friday 19:00" -> RecurrenceRule(WEEKLY, day=4, time=19:00)
        "every 1st 12:00" -> RecurrenceRule(MONTHLY, day_of_month=1, time=12:00)
    """
    type: RecurrenceType
    time: datetime.time
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    day_of_month: Optional[int] = None  # 1-31
    
    def next_occurrence(self, after: datetime = None) -> datetime:
        """
        Calculate the next occurrence after a given time.
        
        Args:
            after: Reference time (default: now)
            
        Returns:
            Next datetime when this recurrence occurs
        """
        ...
    
    def to_string(self) -> str:
        """Serialize to string for storage."""
        ...
    
    @classmethod
    def from_string(cls, rule_str: str) -> 'RecurrenceRule':
        """Parse from storage string."""
        ...
    
    @classmethod
    def parse(cls, pattern: str) -> 'RecurrenceRule':
        """
        Parse user input into RecurrenceRule.
        
        Supported patterns:
            "every day 09:00"
            "every monday 10:00"
            "every friday 19:00"
            "every 1st 12:00"
            "every 15th 14:00"
        
        Raises:
            ValueError: If pattern not recognized
        """
        ...


# Day name mapping
DAYS = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6,
}
```

### 2.6 Alert System Design

```python
# plugins/countdown/alerts.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Callable
import asyncio


@dataclass
class AlertConfig:
    """Configuration for countdown alerts."""
    minutes: List[int]  # e.g., [5, 1] for 5-min and 1-min warnings
    
    @classmethod
    def default(cls) -> 'AlertConfig':
        return cls(minutes=[5, 1])
    
    @classmethod
    def parse(cls, config_str: str) -> 'AlertConfig':
        """Parse from '5,1' or '10,5,1' format."""
        ...
    
    def to_string(self) -> str:
        """Serialize for storage."""
        return ','.join(str(m) for m in self.minutes)


class AlertManager:
    """
    Manages T-minus alerts for countdowns.
    
    Integrates with CountdownScheduler to send warnings
    at configured intervals before T-0.
    """
    
    def __init__(self, on_alert: Callable = None):
        self.on_alert = on_alert
        self._pending_alerts: dict[str, AlertConfig] = {}
        self._sent_alerts: dict[str, set[int]] = {}  # countdown_id -> sent minutes
    
    def configure(self, countdown_id: str, config: AlertConfig) -> None:
        """Set alert configuration for a countdown."""
        self._pending_alerts[countdown_id] = config
        self._sent_alerts[countdown_id] = set()
    
    def remove(self, countdown_id: str) -> None:
        """Remove alert tracking for a countdown."""
        self._pending_alerts.pop(countdown_id, None)
        self._sent_alerts.pop(countdown_id, None)
    
    def check_alerts(
        self, 
        countdown_id: str, 
        remaining: timedelta
    ) -> List[int]:
        """
        Check if any alerts should fire.
        
        Args:
            countdown_id: ID of the countdown
            remaining: Time remaining
            
        Returns:
            List of minute values that should trigger alerts now
        """
        ...
    
    def reset(self, countdown_id: str) -> None:
        """Reset sent alerts (for recurring countdowns)."""
        self._sent_alerts[countdown_id] = set()
```

### 2.7 Extended Plugin Class

```python
# plugins/countdown/plugin.py (additions)

class CountdownPlugin(PluginBase):
    """Extended with recurring and alert support."""
    
    async def setup(self) -> None:
        """Extended setup."""
        # ... existing setup ...
        
        # Initialize alert manager
        self.alert_manager = AlertManager(on_alert=self._on_alert)
        
        # Subscribe to new commands
        await self.subscribe("rosey.command.countdown.alerts", self._handle_alerts)
        await self.subscribe("rosey.command.countdown.pause", self._handle_pause)
        await self.subscribe("rosey.command.countdown.resume", self._handle_resume)
        
        # Load alert configs for existing countdowns
        pending = await self.storage.get_all_pending()
        for countdown in pending:
            if countdown.alert_minutes:
                config = AlertConfig.parse(countdown.alert_minutes)
                self.alert_manager.configure(
                    f"{countdown.channel}:{countdown.name}",
                    config
                )
    
    async def _handle_create(self, msg) -> None:
        """Extended to handle recurring patterns."""
        data = json.loads(msg.data.decode())
        args = data.get("args", "")
        
        # Check for recurring pattern
        if " every " in args.lower():
            await self._create_recurring(msg, data)
        else:
            await self._create_oneshot(msg, data)  # Existing logic
    
    async def _create_recurring(self, msg, data: dict) -> None:
        """Create a recurring countdown."""
        args = data["args"]
        channel = data["channel"]
        user = data["user"]
        
        # Parse "name every pattern"
        match = re.match(r'^(\S+)\s+every\s+(.+)$', args, re.IGNORECASE)
        if not match:
            return await self._reply_error(msg, "Invalid recurring format")
        
        name = match.group(1)
        pattern = match.group(2)
        
        try:
            rule = RecurrenceRule.parse(pattern)
        except ValueError as e:
            return await self._reply_error(msg, str(e))
        
        # Create countdown with recurrence
        next_time = rule.next_occurrence()
        countdown = Countdown(
            id=None,
            name=name,
            channel=channel,
            target_time=next_time,
            created_by=user,
            created_at=datetime.utcnow(),
            is_recurring=True,
            recurrence_rule=rule.to_string(),
        )
        
        countdown = await self.storage.create(countdown)
        self.scheduler.schedule(f"{channel}:{name}", next_time)
        
        # ... respond ...
    
    async def _on_countdown_complete(self, countdown_id: str) -> None:
        """Extended for recurring reset."""
        channel, name = countdown_id.split(":", 1)
        countdown = await self.storage.get_by_name(channel, name)
        
        if not countdown:
            return
        
        # Announce completion
        await self._announce_completion(countdown)
        
        if countdown.is_recurring and not countdown.is_paused:
            # Reset for next occurrence
            rule = RecurrenceRule.from_string(countdown.recurrence_rule)
            next_time = rule.next_occurrence()
            
            await self.storage.update_target_time(countdown.id, next_time)
            self.scheduler.schedule(countdown_id, next_time)
            self.alert_manager.reset(countdown_id)
            
            await self._emit_recurring_reset(countdown, next_time)
        else:
            # One-shot: mark completed
            await self.storage.mark_completed(countdown.id)
    
    async def _handle_alerts(self, msg) -> None:
        """Handle !countdown alerts <name> <minutes>."""
        data = json.loads(msg.data.decode())
        args = data.get("args", "").split()
        
        if len(args) < 2:
            return await self._reply_usage(msg, "alerts <name> <minutes>")
        
        name = args[0]
        minutes_str = args[1]  # e.g., "5,1" or "10,5,1"
        
        countdown = await self.storage.get_by_name(data["channel"], name)
        if not countdown:
            return await self._reply_error(msg, f"Countdown '{name}' not found")
        
        try:
            config = AlertConfig.parse(minutes_str)
        except ValueError:
            return await self._reply_error(msg, "Invalid format. Use: 5,1 or 10,5,1")
        
        await self.storage.update_alerts(countdown.id, config.to_string())
        self.alert_manager.configure(
            f"{countdown.channel}:{countdown.name}",
            config
        )
        
        await self._reply(msg, f"⏰ Alerts set for '{name}': {config.minutes} minutes before")
    
    async def _handle_pause(self, msg) -> None:
        """Handle !countdown pause <name>."""
        ...
    
    async def _handle_resume(self, msg) -> None:
        """Handle !countdown resume <name>."""
        ...
    
    async def _on_alert(
        self, 
        countdown_id: str, 
        minutes: int, 
        countdown: Countdown
    ) -> None:
        """Called when a T-minus alert should fire."""
        await self.publish(
            "countdown.alert",
            {
                "event": "countdown.alert",
                "channel": countdown.channel,
                "countdown": {"name": countdown.name},
                "minutes_remaining": minutes,
            }
        )
        
        # Send to channel
        await self._send_to_channel(
            countdown.channel,
            f"⏰ {minutes} minute{'s' if minutes != 1 else ''} until '{countdown.name}'!"
        )
```

### 2.8 Extended Configuration

```json
{
  "check_interval": 30.0,
  "max_countdowns_per_channel": 20,
  "max_duration_days": 365,
  "emit_events": true,
  "announce_completion": true,
  "default_alerts": [5, 1],
  "allow_custom_alerts": true,
  "max_alert_minutes": 60
}
```

---

## 3. Implementation Steps

### Step 1: Database Migration (30 minutes)

1. Create Alembic migration for new columns
2. Add `recurrence_rule`, `is_paused`, `alert_minutes`, `last_alert_sent`
3. Run migration
4. Update storage class with new methods

### Step 2: Implement Recurrence Module (2 hours)

1. Implement `RecurrenceType` enum
2. Implement `RecurrenceRule` dataclass
3. Implement pattern parsing (daily, weekly, monthly)
4. Implement `next_occurrence()` calculation
5. Implement serialization/deserialization
6. Write comprehensive tests for all patterns

### Step 3: Implement Alert Module (1.5 hours)

1. Implement `AlertConfig` dataclass
2. Implement `AlertManager` class
3. Implement alert checking logic
4. Implement sent-alert tracking
5. Write tests for alert timing

### Step 4: Extend Scheduler (1 hour)

1. Integrate AlertManager with scheduler loop
2. Check alerts during each loop iteration
3. Fire alerts at correct times
4. Handle edge cases (missed alerts, etc.)

### Step 5: Extend Plugin (2 hours)

1. Update `_handle_create()` for recurring patterns
2. Implement `_create_recurring()` method
3. Extend `_on_countdown_complete()` for auto-reset
4. Implement `_handle_alerts()` command
5. Implement `_handle_pause()` and `_handle_resume()`
6. Wire up alert callbacks

### Step 6: Integration Testing (1.5 hours)

1. Test full recurring flow: create → complete → auto-reset
2. Test alert timing accuracy
3. Test pause/resume
4. Test persistence of recurring state
5. Test edge cases (pause at T-0, etc.)

### Step 7: Documentation (30 minutes)

1. Update README.md with recurring examples
2. Document recurrence patterns
3. Document alert configuration

---

## 4. Test Cases

### 4.1 Recurrence Pattern Tests

| Pattern | Expected |
|---------|----------|
| `every day 09:00` | Daily at 09:00 UTC |
| `every monday 10:00` | Weekly on Monday |
| `every friday 19:00` | Weekly on Friday |
| `every fri 19:00` | Weekly on Friday (abbreviated) |
| `every 1st 12:00` | Monthly on 1st |
| `every 15th 14:00` | Monthly on 15th |
| `every invalid` | ValueError |

### 4.2 Next Occurrence Tests

| Pattern | Current Time | Expected Next |
|---------|--------------|---------------|
| `every friday 19:00` | Wed 10:00 | Fri 19:00 (same week) |
| `every friday 19:00` | Fri 20:00 | Fri 19:00 (next week) |
| `every day 09:00` | Mon 10:00 | Tue 09:00 |
| `every 1st 12:00` | Jan 15 | Feb 1 |
| `every 31st 12:00` | Feb 1 | Mar 31 |

### 4.3 Alert Tests

| Config | Time Until T-0 | Alert Fires? |
|--------|----------------|--------------|
| `[5, 1]` | 5 min 30 sec | Yes (5 min) |
| `[5, 1]` | 5 min 30 sec (again) | No (already sent) |
| `[5, 1]` | 1 min 30 sec | Yes (1 min) |
| `[5, 1]` | 0 min 30 sec | No |
| `[10, 5, 1]` | 10 min | Yes (10 min) |

### 4.4 Recurring Lifecycle Tests

| Scenario | Expected |
|----------|----------|
| Create recurring | Scheduled for next occurrence |
| Recurring completes | Announces, resets to next occurrence |
| Pause recurring | No more completions/resets |
| Resume recurring | Resumes with next occurrence |
| Delete recurring | Fully removed |

### 4.5 Integration Tests

| Scenario | Expected |
|----------|----------|
| `!countdown movie every friday 19:00` | Creates recurring, shows next Friday |
| `!countdown alerts movie 10,5,1` | Configures alerts |
| Recurring reaches T-0 | Announces, resets, sends event |
| `!countdown pause movie` | Pauses, no more resets |
| `!countdown resume movie` | Resumes from next occurrence |
| Restart with recurring | Recovers state, continues |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Invalid recurrence pattern | "❌ Couldn't parse that pattern. Try: 'every friday 19:00' or 'every day 09:00'" |
| Invalid day name | "❌ Unknown day. Use: monday, tuesday, wednesday, thursday, friday, saturday, sunday" |
| Invalid alert format | "❌ Invalid alert format. Use comma-separated minutes: 5,1 or 10,5,1" |
| Alert too far in advance | "❌ Alerts can't be more than {N} minutes before" |
| Pause non-recurring | "❌ 'xyz' is not a recurring countdown" |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| Migration fails | Roll back, alert admin |
| Alert timing drift | Use absolute times, not relative |
| Missed alert window | Skip that alert, continue |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!countdown <name> every friday 19:00` creates weekly recurring
- [ ] `!countdown <name> every day 09:00` creates daily recurring
- [ ] Recurring countdowns auto-reset after T-0
- [ ] `!countdown alerts <name> 5,1` configures T-minus alerts
- [ ] Alerts fire at correct times (5 min, 1 min before)
- [ ] `!countdown pause/resume` controls recurring
- [ ] Paused countdowns don't reset or alert

### 6.2 Technical

- [ ] Database migration runs cleanly
- [ ] Recurrence calculations handle edge cases
- [ ] Alert timing is accurate (±30 seconds)
- [ ] Events emitted for alerts and resets
- [ ] Test coverage > 85%

### 6.3 Documentation

- [ ] README.md updated with recurring examples
- [ ] All recurrence patterns documented
- [ ] Alert configuration documented

---

## 7. Sample Interactions

```
User: !countdown friday_movie every friday 19:00
Rosey: ⏰🔄 Recurring countdown 'friday_movie' created! 
       Next: Friday at 7:00 PM (4 days, 5 hours)

User: !countdown alerts friday_movie 10,5,1
Rosey: ⏰ Alerts set for 'friday_movie': [10, 5, 1] minutes before

User: !countdown friday_movie
Rosey: ⏰🔄 'friday_movie' (recurring) — 4 days, 5 hours until next occurrence

[At T-10 minutes]
Rosey: ⏰ 10 minutes until 'friday_movie'!

[At T-5 minutes]
Rosey: ⏰ 5 minutes until 'friday_movie'!

[At T-1 minute]
Rosey: ⏰ 1 minute until 'friday_movie'!

[At T-0]
Rosey: 🎉 TIME'S UP! 'friday_movie' has arrived!
       (Next occurrence: Friday, Dec 13 at 7:00 PM)

User: !countdown pause friday_movie
Rosey: ⏰⏸️ 'friday_movie' paused. Use !countdown resume to continue.

User: !countdown resume friday_movie
Rosey: ⏰▶️ 'friday_movie' resumed! Next: Friday, Dec 13 at 7:00 PM (6 days)

User: !countdown standup every day 09:00
Rosey: ⏰🔄 Recurring countdown 'standup' created!
       Next: Tomorrow at 9:00 AM (14 hours)
```

---

## 8. Checklist

### Pre-Implementation
- [ ] Sortie 3 complete and tested
- [ ] Alembic migration plan reviewed
- [ ] Edge cases for recurrence identified

### Implementation
- [ ] Create database migration
- [ ] Implement recurrence module
- [ ] Implement alert module
- [ ] Extend scheduler
- [ ] Extend plugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real recurring
- [ ] Verify alerts fire correctly
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add advanced countdown features

- Add recurring countdowns (daily, weekly, monthly)
- Add T-minus alerts (configurable)
- Add pause/resume for recurring
- Auto-reset recurring after T-0

Implements: SPEC-Sortie-4-CountdownAdvanced.md
Related: PRD-Funny-Games.md
```
