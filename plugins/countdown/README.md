# ⏰ Countdown Plugin

The Countdown plugin provides event countdown timers for chat channels, with automatic T-0 announcements and persistent storage.

## Features

- **One-Time Countdowns**: Create countdowns to specific dates/times
- **Multiple Formats**: Supports various datetime input formats
- **Channel-Scoped**: Each channel has its own countdowns
- **Automatic Announcements**: T-0 announcements when countdowns complete
- **Persistent Storage**: Countdowns survive restarts via NATS storage API
- **Event Emission**: Analytics events for tracking

## Commands

### `!countdown <name> <datetime>`

Create a new countdown.

```
User: !countdown movie_night 2025-12-01 20:00
Rosey: ⏰ Countdown 'movie_night' created! Time remaining: 6 days, 4 hours, 30 minutes

User: !countdown birthday tomorrow 14:00
Rosey: ⏰ Countdown 'birthday' created! Time remaining: 18 hours, 15 minutes

User: !countdown meeting in 2 hours
Rosey: ⏰ Countdown 'meeting' created! Time remaining: 2 hours
```

### `!countdown <name>`

Check remaining time for a countdown.

```
User: !countdown movie_night
Rosey: ⏰ 'movie_night' — 6 days, 4 hours, 28 minutes remaining
```

### `!countdown list`

List all active countdowns in the channel.

```
User: !countdown list
Rosey: ⏰ Active countdowns:
  • movie_night — 6d 4h 28m
  • birthday — 18h 15m
  • meeting — 1h 45m
```

### `!countdown delete <name>`

Delete a countdown.

```
User: !countdown delete meeting
Rosey: ⏰ Countdown 'meeting' deleted.
```

## Supported Datetime Formats

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

All times are interpreted as **UTC**.

## Configuration

Edit `config.json` to customize behavior:

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
| `emit_events` | bool | true | Emit analytics events |
| `announce_completion` | bool | true | Announce T-0 to channel |

## NATS Integration

### Command Subjects

| Subject | Purpose |
|---------|---------|
| `rosey.command.countdown.create` | Create countdown |
| `rosey.command.countdown.check` | Check remaining time |
| `rosey.command.countdown.list` | List countdowns |
| `rosey.command.countdown.delete` | Delete countdown |

### Event Subjects

| Subject | Purpose |
|---------|---------|
| `rosey.event.countdown.created` | Countdown created |
| `rosey.event.countdown.completed` | Countdown reached T-0 |
| `rosey.event.countdown.deleted` | Countdown deleted |

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
  "args": "movie_night 2025-12-01 20:00",
  "reply_to": "rosey.reply.abc123"
}
```

### Response Format

```json
{
  "success": true,
  "result": {
    "name": "movie_night",
    "target_time": "2025-12-01T20:00:00+00:00",
    "created_by": "username",
    "channel": "lobby",
    "remaining": "6 days, 4 hours, 30 minutes",
    "message": "⏰ Countdown 'movie_night' created! Time remaining: 6 days, 4 hours, 30 minutes"
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

## Architecture

The plugin follows the NATS-based architecture:

1. **Plugin Process**: Standalone process communicating via NATS
2. **Scheduler**: Asyncio-based timer checking pending countdowns
3. **Storage**: All persistence via NATS storage API (no direct DB access)
4. **Events**: Event emission for analytics and other plugins

```
┌─────────────────┐     NATS     ┌─────────────────┐
│  Bot / Router   │ ←──────────→ │ CountdownPlugin │
└─────────────────┘              └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │    Scheduler    │
                                 │  (asyncio loop) │
                                 └─────────────────┘
                                          │
                                          ▼
┌─────────────────┐     NATS     ┌─────────────────┐
│ Storage Service │ ←──────────→ │  Storage API    │
└─────────────────┘              │ (NATS subjects) │
                                 └─────────────────┘
```

## Version History

- **1.0.0** - Initial release with one-time countdowns

## Future Enhancements (Sortie 4)

- Recurring countdowns (`!countdown friday_movie every friday 19:00`)
- T-minus alerts (5 min, 1 min warnings)
- Timezone support (`!countdown ... EST`)
- User-specific countdowns (DM reminders)

## License

Part of the Rosey-Robot project.
