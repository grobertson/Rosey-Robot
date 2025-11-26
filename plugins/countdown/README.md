# ⏰ Countdown Plugin

The Countdown plugin provides event countdown timers for chat channels, with automatic T-0 announcements, recurring patterns, customizable alerts, and persistent storage.

## Features

- **One-Time Countdowns**: Create countdowns to specific dates/times
- **Recurring Countdowns**: Weekly, daily, or monthly repeating events
- **T-Minus Alerts**: Customizable warnings before countdown completion
- **Pause/Resume**: Pause and resume recurring countdowns
- **Multiple Formats**: Supports various datetime input formats
- **Channel-Scoped**: Each channel has its own countdowns
- **Automatic Announcements**: T-0 announcements when countdowns complete
- **Persistent Storage**: Countdowns survive restarts via NATS storage API
- **Event Emission**: Analytics events for tracking

## Commands

### `!countdown <name> <datetime>`

Create a new one-time countdown.

```
User: !countdown movie_night 2025-12-01 20:00
Rosey: ⏰ Countdown 'movie_night' created! Time remaining: 6 days, 4 hours, 30 minutes

User: !countdown birthday tomorrow 14:00
Rosey: ⏰ Countdown 'birthday' created! Time remaining: 18 hours, 15 minutes

User: !countdown meeting in 2 hours
Rosey: ⏰ Countdown 'meeting' created! Time remaining: 2 hours
```

### `!countdown <name> every <pattern>`

Create a recurring countdown.

```
User: !countdown friday_movie every friday 19:00
Rosey: ⏰🔄 Recurring countdown 'friday_movie' created!
       Pattern: Every Friday at 19:00
       Next occurrence: 2 days, 10 hours

User: !countdown standup every day 09:30
Rosey: ⏰🔄 Recurring countdown 'standup' created!
       Pattern: Every day at 09:30
       Next occurrence: 14 hours, 15 minutes

User: !countdown paycheck every 15th 12:00
Rosey: ⏰🔄 Recurring countdown 'paycheck' created!
       Pattern: Every 15th at 12:00
       Next occurrence: 8 days, 2 hours
```

### `!countdown <name>`

Check remaining time for a countdown.

```
User: !countdown movie_night
Rosey: ⏰ 'movie_night' — 6 days, 4 hours, 28 minutes remaining

User: !countdown friday_movie
Rosey: ⏰🔄 'friday_movie' (recurring, active)
       Pattern: Every Friday at 19:00
       Next: 2 days, 10 hours
```

### `!countdown list`

List all active countdowns in the channel.

```
User: !countdown list
Rosey: ⏰ Active countdowns:
  • movie_night — 6d 4h 28m
  • friday_movie — 2d 10h (🔄 recurring)
  • standup — 14h 15m (🔄 recurring)
```

### `!countdown alerts <name> <minutes>`

Set custom T-minus alerts (default: 5 and 1 minute).

```
User: !countdown alerts movie_night 15,5,1
Rosey: ⏰ Alerts set for 'movie_night': 15, 5, 1 minutes before

User: !countdown alerts standup 10,5
Rosey: ⏰ Alerts set for 'standup': 10, 5 minutes before
```

### `!countdown pause <name>`

Pause a recurring countdown.

```
User: !countdown pause friday_movie
Rosey: ⏰⏸️ 'friday_movie' paused. Use !countdown resume to continue.
```

### `!countdown resume <name>`

Resume a paused recurring countdown.

```
User: !countdown resume friday_movie
Rosey: ⏰▶️ 'friday_movie' resumed! Next: 5 days, 8 hours
```

### `!countdown delete <name>`

Delete a countdown.

```
User: !countdown delete meeting
Rosey: ⏰ Countdown 'meeting' deleted.
```

## Supported Datetime Formats

### One-Time Countdowns

| Format | Example |
|--------|---------|
| Standard | `2025-12-01 20:00` |
| With seconds | `2025-12-01 20:00:30` |
| ISO format | `2025-12-01T20:00:00` |
| US format | `12/01/2025 20:00` |
| Tomorrow | `tomorrow` or `tomorrow 14:00` |
| Relative (hours) | `in 2 hours` or `2 hours` |
| Relative (minutes) | `in 30 minutes` or `30 minutes` |
| Relative (days) | `in 3 days` or `3 days` |
| Relative (weeks) | `in 1 week` |

### Recurring Patterns

| Pattern | Example |
|---------|---------|
| Daily | `every day 09:00` |
| Weekly (full) | `every friday 19:00` |
| Weekly (abbrev) | `every fri 19:00` |
| Monthly | `every 1st 12:00`, `every 15th 14:00` |

All times are interpreted as **UTC**.

## T-Minus Alerts

Alerts notify the channel when a countdown is approaching completion:

```
Rosey: ⏰ 5 minutes until 'movie_night'!
...
Rosey: ⏰ 1 minute until 'movie_night'!
...
Rosey: 🎉 TIME'S UP! 'movie_night' has arrived!
```

Default alerts are at 5 and 1 minute. Customize per-countdown with `!countdown alerts`.

## Recurring Behavior

When a recurring countdown completes:

1. 🎉 Announces completion to the channel
2. 🔄 Automatically calculates next occurrence
3. 📢 Announces next scheduled time
4. ⏰ Resumes countdown to next occurrence

Pausing a recurring countdown prevents it from auto-repeating.

## Configuration

Edit `config.json` to customize behavior:

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

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `check_interval` | float | 30.0 | Seconds between scheduler checks |
| `max_countdowns_per_channel` | int | 20 | Max active countdowns per channel |
| `max_duration_days` | int | 365 | Max days in future for countdown |
| `emit_events` | bool | true | Emit analytics events |
| `announce_completion` | bool | true | Announce T-0 to channel |
| `default_alerts` | list | [5, 1] | Default T-minus alerts (minutes) |
| `allow_custom_alerts` | bool | true | Allow per-countdown alert config |
| `max_alert_minutes` | int | 60 | Max minutes for alert setting |

## NATS Integration

### Command Subjects

| Subject | Purpose |
|---------|---------|
| `rosey.command.countdown.create` | Create countdown |
| `rosey.command.countdown.check` | Check remaining time |
| `rosey.command.countdown.list` | List countdowns |
| `rosey.command.countdown.delete` | Delete countdown |
| `rosey.command.countdown.alerts` | Configure alerts |
| `rosey.command.countdown.pause` | Pause recurring |
| `rosey.command.countdown.resume` | Resume recurring |

### Event Subjects

| Subject | Purpose |
|---------|---------|
| `rosey.event.countdown.created` | Countdown created |
| `rosey.event.countdown.completed` | Countdown reached T-0 |
| `rosey.event.countdown.deleted` | Countdown deleted |
| `rosey.event.countdown.alert` | T-minus alert fired |
| `rosey.event.countdown.recurring_reset` | Recurring countdown reset |
| `rosey.event.countdown.paused` | Recurring countdown paused |
| `rosey.event.countdown.resumed` | Recurring countdown resumed |

### Storage Subjects (via NATS Storage API)

| Subject | Purpose |
|---------|---------|
| `rosey.db.row.countdown.insert` | Create record |
| `rosey.db.row.countdown.select` | Query records |
| `rosey.db.row.countdown.update` | Update record |
| `rosey.db.row.countdown.delete` | Delete record |
| `rosey.db.migrate.countdown.status` | Migration status |

### Request Format

```json
{
  "channel": "lobby",
  "user": "username",
  "args": "friday_movie every friday 19:00",
  "reply_to": "rosey.reply.abc123"
}
```

### Response Format

```json
{
  "success": true,
  "result": {
    "name": "friday_movie",
    "target_time": "2025-11-28T19:00:00+00:00",
    "created_by": "username",
    "channel": "lobby",
    "remaining": "2 days, 10 hours",
    "is_recurring": true,
    "recurrence": "Every Friday at 19:00",
    "message": "⏰🔄 Recurring countdown 'friday_movie' created!"
  }
}
```

## Database Schema

The plugin uses the NATS storage API with a `countdowns` table:

```sql
CREATE TABLE countdowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    target_time TIMESTAMP NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
    recurrence_rule TEXT NULL,
    is_paused BOOLEAN DEFAULT FALSE NOT NULL,
    alert_minutes TEXT NULL,
    last_alert_sent INTEGER NULL,
    completed BOOLEAN DEFAULT FALSE NOT NULL,
    
    UNIQUE(channel, name)
);
```

## Migrations

Run migrations before first use:

```bash
# Check status
nats req rosey.db.migrate.countdown.status '{}'

# Apply migrations
nats req rosey.db.migrate.countdown.apply '{}'
```

## Testing

Run tests from the plugin directory:

```bash
cd plugins/countdown
pytest
```

Or with coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

Current test count: **151 tests**

## Architecture

The plugin follows the NATS-based architecture:

1. **Plugin Process**: Standalone process communicating via NATS
2. **Scheduler**: Asyncio-based timer checking pending countdowns
3. **Alert Manager**: Tracks and fires T-minus alerts
4. **Recurrence Engine**: Calculates next occurrence for recurring events
5. **Storage**: All persistence via NATS storage API (no direct DB access)
6. **Events**: Event emission for analytics and other plugins

```
┌─────────────────┐     NATS     ┌─────────────────┐
│  Bot / Router   │ ←──────────→ │ CountdownPlugin │
└─────────────────┘              └────────┬────────┘
                                          │
                           ┌──────────────┼──────────────┐
                           │              │              │
                           ▼              ▼              ▼
                    ┌──────────┐   ┌──────────┐   ┌──────────┐
                    │Scheduler │   │ Alert    │   │Recurrence│
                    │  (async) │   │ Manager  │   │ Engine   │
                    └──────────┘   └──────────┘   └──────────┘
                           │
                           ▼
┌─────────────────┐     NATS     ┌─────────────────┐
│ Storage Service │ ←──────────→ │  Storage API    │
└─────────────────┘              │ (NATS subjects) │
                                 └─────────────────┘
```

## Version History

- **2.0.0** - Added recurring countdowns, T-minus alerts, pause/resume
- **1.0.0** - Initial release with one-time countdowns

## License

Part of the Rosey-Robot project.
