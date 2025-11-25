# Rosey Plugins

Complete guide to all available Rosey plugins, commands, and configuration.

---

## Table of Contents

1. [Games & Entertainment](#games--entertainment)
2. [AI & Automation](#ai--automation)
3. [Admin & Observability](#admin--observability)
4. [Plugin Configuration](#plugin-configuration)
5. [Developing Your Own Plugin](#developing-your-own-plugin)

---

## Games & Entertainment

### 🎲 Dice Roller (`dice-roller`)

Roll dice using standard tabletop RPG notation.

**Commands:**

| Command | Description | Example |
|---------|-------------|---------|
| `!roll <notation>` | Roll dice | `!roll 2d6+3` |
| `!flip` | Flip a coin | `!flip` |

**Dice Notation:**

- Basic rolls: `d20`, `3d6`, `10d10`
- Modifiers: `2d6+3`, `1d20-1`
- Keep highest: `4d6kh3` (roll 4d6, keep highest 3)
- Keep lowest: `4d6kl3` (roll 4d6, keep lowest 3)
- Drop highest: `4d6dh1` (roll 4d6, drop highest 1)
- Drop lowest: `4d6dl1` (roll 4d6, drop lowest 1)
- Advantage: `2d20kh1` or `!roll adv`
- Disadvantage: `2d20kl1` or `!roll dis`

**Examples:**

```
!roll d20              → Roll a d20
!roll 2d6+3            → Roll 2d6 and add 3
!roll 4d6kh3           → Roll 4d6, keep highest 3 (stat rolling)
!roll d20 adv          → Roll with advantage (2d20, keep highest)
!flip                  → Flip a coin
```

**Configuration:** `plugins/dice-roller/config.json`

```json
{
  "max_dice": 100,
  "max_sides": 1000,
  "max_modifier": 1000,
  "emit_events": true
}
```

**Links:**
- [Dice Roller README](../plugins/dice-roller/README.md)
- [Dice Notation Guide](../plugins/dice-roller/README.md#dice-notation)

---

### 🔮 Magic 8-Ball (`8ball`)

Consult the mystical Magic 8-Ball for yes/no questions.

**Commands:**

| Command | Description | Example |
|---------|-------------|---------|
| `!8ball <question>` | Ask a question | `!8ball Will I win?` |

**Response Types:**

- **Positive** (10): Yes, definitely; Without a doubt; You may rely on it; etc.
- **Negative** (5): Don't count on it; My reply is no; Outlook not so good; etc.
- **Non-committal** (5): Reply hazy; Ask again later; Cannot predict now; etc.

**Examples:**

```
!8ball Will we watch a good movie tonight?
!8ball Should I add another movie to the queue?
!8ball Is the grindhouse in session?
```

**Configuration:** `plugins/8ball/config.json`

```json
{
  "cooldown_seconds": 3,
  "require_question": true,
  "emit_events": true
}
```

**Links:**
- [8-Ball README](../plugins/8ball/README.md)

---

### ⏰ Countdown Timer (`countdown`)

Track time until events with one-time or recurring countdowns.

**Commands:**

| Command | Description | Example |
|---------|-------------|---------|
| `!countdown <name> <datetime>` | Create countdown | `!countdown movie 2025-12-31 23:59` |
| `!countdown <name>` | Check time remaining | `!countdown movie` |
| `!countdown list` | List all countdowns | `!countdown list` |
| `!countdown delete <name>` | Delete countdown | `!countdown delete movie` |
| `!countdown <name> every <pattern>` | Recurring countdown | `!countdown movie every friday 19:00` |
| `!countdown alerts <name> <minutes>` | Set T-minus alerts | `!countdown alerts movie 5,1` |
| `!countdown pause <name>` | Pause recurring | `!countdown pause movie` |
| `!countdown resume <name>` | Resume recurring | `!countdown resume movie` |

**Datetime Formats:**

- **Absolute:** `2025-12-31 23:59`, `2025-12-31T23:59:00`
- **Relative:** `in 2 hours`, `in 30 minutes`, `tomorrow 19:00`
- **Recurring:** `every friday 19:00`, `every day 12:00`, `every 2 weeks`

**Examples:**

```
!countdown movie 2025-12-31 23:59        # New Year's movie
!countdown movie tomorrow 19:00           # Tomorrow at 7pm
!countdown stream in 2 hours              # 2 hours from now
!countdown movienight every friday 19:00  # Weekly recurring
!countdown alerts movienight 10,5,1       # Alerts at T-10, T-5, T-1 minutes
!countdown                                # Check current countdown
!countdown list                           # List all countdowns
```

**Configuration:** `plugins/countdown/config.json`

```json
{
  "check_interval": 30.0,
  "max_countdowns_per_channel": 20,
  "max_duration_days": 365,
  "announce_completion": true,
  "default_alerts": [5, 1],
  "allow_custom_alerts": true,
  "max_alert_minutes": 60
}
```

**Links:**
- [Countdown README](../plugins/countdown/README.md)
- [Recurring Patterns Guide](../plugins/countdown/README.md#recurring-countdowns)

---

### 🧠 Trivia Game (`trivia`)

Interactive quiz game with scoring and leaderboards.

**Commands:**

| Command | Description | Example |
|---------|-------------|---------|
| `!trivia start [N]` | Start game (N questions) | `!trivia start 10` |
| `!trivia stop` | End current game | `!trivia stop` |
| `!a <answer>` | Submit answer | `!a Paris` or `!a 2` |
| `!trivia stats` | View your stats | `!trivia stats` |
| `!trivia stats @user` | View user stats | `!trivia stats @PlayerName` |
| `!trivia lb` | Channel leaderboard | `!trivia lb` |
| `!trivia lb global` | Global leaderboard | `!trivia lb global` |
| `!trivia ach` | View achievements | `!trivia ach` |
| `!trivia cat` | Category stats | `!trivia cat` |

**Game Features:**

- **Multiple Choice:** 4 answer options per question
- **Time Limit:** 30 seconds per question (configurable)
- **Points Decay:** First answer gets full points, decreases over time
- **Scoring:**
  - Correct answer: 100-1000 points (decay over time)
  - Streaks: Bonus points for consecutive correct answers
  - Difficulty: Higher difficulty = more points
- **Categories:** General, History, Science, Entertainment, Sports, Geography, and more
- **Difficulty Levels:** Easy, Medium, Hard
- **Achievements:** Win streaks, categories mastered, participation milestones

**Examples:**

```
!trivia start              # Start 10-question game (default)
!trivia start 20           # Start 20-question game
!a 1                       # Submit answer A
!a Paris                   # Submit answer by text
!trivia stop               # End game early
!trivia stats              # Your stats
!trivia lb                 # Channel leaderboard
!trivia ach                # Your achievements
```

**Configuration:** `plugins/trivia/config.json`

```json
{
  "time_per_question": 30,
  "start_delay": 5,
  "between_question_delay": 3,
  "default_questions": 10,
  "max_questions": 50,
  "min_questions": 1,
  "points_decay": true,
  "base_points": 1000,
  "min_points": 100,
  "streak_bonus": 50,
  "emit_events": true
}
```

**Links:**
- [Trivia README](../plugins/trivia/README.md)
- [Scoring System](../plugins/trivia/README.md#scoring)
- [Achievements Guide](../plugins/trivia/README.md#achievements)

---

## AI & Automation

### 💬 LLM Chat (`llm`)

AI-powered chat with multiple model providers.

**Supported Providers:**
- OpenAI (GPT-4, GPT-3.5)
- Ollama (Local models)
- Azure OpenAI
- OpenRouter

**Configuration:** See [LLM_CONFIGURATION.md](guides/LLM_CONFIGURATION.md)

**Commands:** Bot responds to mentions or configured triggers

---

### 📝 Quote Database (`quote-db`)

Save and recall memorable channel quotes.

**Commands:**

| Command | Description |
|---------|-------------|
| `!quote` | Random quote |
| `!quote add <text>` | Save a quote |
| `!quote search <term>` | Search quotes |

**Links:**
- [Quote DB Plugin](../plugins/quote-db/)

---

## Admin & Observability

### 🔍 Inspector (`inspector`)

Real-time NATS event monitoring for administrators.

**Commands (Admin Only):**

| Command | Description | Example |
|---------|-------------|---------|
| `!inspect events [pattern]` | View recent events | `!inspect events trivia.*` |
| `!inspect plugins` | List loaded plugins | `!inspect plugins` |
| `!inspect stats` | View statistics | `!inspect stats` |
| `!inspect pause` | Pause capture | `!inspect pause` |
| `!inspect resume` | Resume capture | `!inspect resume` |
| `!inspect clear` | Clear buffer | `!inspect clear` |

**Event Patterns:**

- `*` - Single segment wildcard (e.g., `trivia.*` matches `trivia.start`)
- `**` - Multiple segment wildcard (e.g., `trivia.**` matches `trivia.game.started`)
- `>` - All remaining segments (e.g., `rosey.>` matches everything under rosey)
- `?` - Single character wildcard

**Examples:**

```
!inspect events                    # Show all recent events
!inspect events trivia.*           # Show only trivia events
!inspect events rosey.command.**   # Show all commands
!inspect plugins                   # List active plugins
!inspect stats                     # Buffer statistics
!inspect pause                     # Stop capturing
!inspect resume                    # Resume capturing
```

**Configuration:** `plugins/inspector/config.json`

```json
{
  "buffer_size": 1000,
  "admins": ["admin1", "admin2"],
  "exclude_patterns": [
    "_INBOX.*",
    "inspector.*"
  ],
  "emit_events": false
}
```

**Links:**
- [Inspector README](../plugins/inspector/README.md)
- [Event Pattern Guide](../plugins/inspector/README.md#event-patterns)

---

## Plugin Configuration

### Configuration Files

Each plugin has a `config.json` file in its directory:

```
plugins/
├── dice-roller/config.json
├── 8ball/config.json
├── countdown/config.json
├── trivia/config.json
└── inspector/config.json
```

### Common Configuration Options

Most plugins support these common options:

```json
{
  "emit_events": true,      // Publish analytics events
  "log_level": "INFO",      // Logging verbosity
  "enabled": true           // Enable/disable plugin
}
```

### Environment-Specific Configs

Use different configs per environment:

```bash
# Development
python -m lib.bot config-dev.json

# Production
python -m lib.bot config-prod.json
```

---

## Developing Your Own Plugin

Want to create a custom plugin? Here's a minimal example:

```python
# plugins/my_plugin/plugin.py

import json
import logging
from typing import Any, Dict, Optional
from nats.aio.client import Client as NATS


class MyPlugin:
    """My custom plugin."""
    
    NAMESPACE = "myplugin"
    VERSION = "1.0.0"
    DESCRIPTION = "My awesome plugin"
    
    # NATS subjects
    SUBJECT_COMMAND = "rosey.command.myplugin.do_something"
    EVENT_SOMETHING_HAPPENED = "rosey.event.myplugin.something_happened"
    
    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.NAMESPACE}")
        self._subscriptions = []
    
    async def initialize(self) -> None:
        """Initialize plugin and subscribe to NATS subjects."""
        self.logger.info(f"Initializing {self.NAMESPACE} v{self.VERSION}")
        
        # Subscribe to command
        sub = await self.nats.subscribe(
            self.SUBJECT_COMMAND,
            cb=self._handle_command
        )
        self._subscriptions.append(sub)
    
    async def shutdown(self) -> None:
        """Clean up subscriptions."""
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
    
    async def _handle_command(self, msg) -> None:
        """Handle incoming command."""
        try:
            data = json.loads(msg.data.decode())
            # Do something cool
            result = {"status": "success", "message": "Did something!"}
            await self.nats.publish(
                msg.reply,
                json.dumps(result).encode()
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
```

### Plugin Structure

```
plugins/my_plugin/
├── __init__.py
├── plugin.py           # Main plugin class
├── config.json         # Default configuration
├── README.md          # Documentation
└── tests/
    ├── __init__.py
    └── test_plugin.py  # Unit tests
```

### Best Practices

1. **Use NATS for everything** - No direct database access
2. **Handle errors gracefully** - Log and respond with error messages
3. **Write tests** - Aim for 85%+ coverage
4. **Document commands** - Clear README with examples
5. **Version your plugin** - Use semantic versioning
6. **Subscribe on init** - Set up subscriptions in `initialize()`
7. **Clean up** - Unsubscribe in `shutdown()`

### NATS Subject Conventions

- **Commands**: `rosey.command.<plugin>.<action>`
- **Events**: `rosey.event.<plugin>.<event_type>`
- **Database**: `rosey.db.row.<plugin>.<operation>`
- **Internal**: `<plugin>.internal.<message_type>`

### Plugin Loading

Plugins are loaded automatically from the `plugins/` directory. Create a `plugin.py` file with a class that follows the pattern above.

---

## Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [Database Setup](DATABASE_SETUP.md)
- [LLM Configuration](guides/LLM_CONFIGURATION.md)
- [Testing Guide](TESTING.md)
- [Agent Development Workflow](guides/AGENT_WORKFLOW_DETAILED.md)

---

**Version:** 0.7.0  
**Last Updated:** November 24, 2025  
**Maintained By:** Rosey-Robot Team
