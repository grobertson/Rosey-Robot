# Plugin Development Guide

Learn to build plugins for Rosey v1.0's plugin-first architecture. This guide covers structure, NATS patterns, database access, command registration, testing, and complete examples.

## Table of Contents

- [Philosophy](#philosophy)
- [Quick Start](#quick-start)
- [Plugin Structure](#plugin-structure)
- [NATS Communication](#nats-communication)
- [Database Access](#database-access)
- [Command Registration](#command-registration)
- [Testing Plugins](#testing-plugins)
- [Example: Building a Plugin](#example-building-a-plugin)
- [Best Practices](#best-practices)
- [Deployment](#deployment)

## Philosophy

**Rosey v1.0 is plugin-first**: The core is infrastructure only (117 lines), **all functionality lives in plugins**.

### Core Principles

1. **NATS Everything** - All communication via event bus, zero direct dependencies
2. **Self-Contained** - Each plugin is independent, can be enabled/disabled without affecting others
3. **Interface-First** - Test NATS contracts, not internal implementation
4. **Graceful Failure** - Plugin crashes don't take down the bot

### What Makes a Good Plugin?

- **Single Responsibility** - One clear purpose (dice rolling, quotes, trivia)
- **NATS-Only Communication** - No direct imports of other plugins or core modules (except `core.event_bus`)
- **Database via NATS** - Use `database.*` subjects, not SQLAlchemy directly
- **Well-Tested** - Unit tests for logic, integration tests for NATS contracts
- **Documented** - Clear README with commands, examples, configuration

## Quick Start

### 1. Create Plugin Directory

```bash
mkdir -p plugins/my-plugin
cd plugins/my-plugin
```

### 2. Create Plugin Structure

```
plugins/my-plugin/
├── __init__.py          # Plugin entry point (required)
├── plugin.py            # Main plugin class (recommended)
├── README.md            # Documentation
├── test_plugin.py       # Tests
└── migrations/          # Database migrations (if needed)
    └── 001_create_tables.sql
```

### 3. Write `__init__.py`

```python
# plugins/my-plugin/__init__.py
"""
My Plugin - Does something cool
"""
from core.event_bus import EventBus
from .plugin import MyPlugin

# Plugin metadata (required)
PLUGIN_INFO = {
    "name": "my-plugin",
    "version": "1.0.0",
    "commands": ["mycommand"],
    "description": "Does something cool"
}

# Plugin lifecycle hooks (required)
async def start(event_bus: EventBus) -> MyPlugin:
    """
    Plugin startup hook.
    
    Args:
        event_bus: Connected EventBus instance
    
    Returns:
        Plugin instance (for stop hook)
    """
    plugin = MyPlugin(event_bus)
    await plugin.register()
    return plugin

async def stop(plugin: MyPlugin):
    """
    Plugin shutdown hook.
    
    Args:
        plugin: Plugin instance from start()
    """
    await plugin.cleanup()
```

### 4. Write Plugin Class

```python
# plugins/my-plugin/plugin.py
import logging
from core.event_bus import EventBus, Event

logger = logging.getLogger(__name__)

class MyPlugin:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def register(self):
        """Register NATS subscriptions."""
        await self.event_bus.subscribe("plugin.my-plugin.command", self.handle_command)
        logger.info("MyPlugin registered")
    
    async def handle_command(self, event: Event):
        """Handle !mycommand."""
        user = event.data.get("user")
        args = event.data.get("args", [])
        
        # Do something cool
        result = f"Hello, {user}!"
        
        # Send response
        await self.event_bus.publish("cytube.send.chat", {
            "message": result
        })
    
    async def cleanup(self):
        """Cleanup on shutdown."""
        logger.info("MyPlugin cleanup")
```

### 5. Enable Plugin

Edit `config.json`:

```json
{
  "plugins": {
    "enabled": ["dice-roller", "my-plugin"]
  }
}
```

### 6. Test

```bash
# Run bot
python rosey.py

# In CyTube chat
!mycommand
# Bot responds: "Hello, alice!"
```

## Plugin Structure

### Minimal Plugin (`__init__.py` only)

```python
# plugins/simple-plugin/__init__.py
from core.event_bus import EventBus, Event

PLUGIN_INFO = {
    "name": "simple-plugin",
    "version": "1.0.0",
    "commands": ["simple"],
    "description": "Minimal plugin example"
}

_event_bus = None

async def start(event_bus: EventBus):
    global _event_bus
    _event_bus = event_bus
    
    async def handle_command(event: Event):
        await event_bus.publish("cytube.send.chat", {
            "message": "Simple response!"
        })
    
    await event_bus.subscribe("plugin.simple-plugin.command", handle_command)

async def stop(_):
    pass
```

**Pros**: Quick prototypes, very simple plugins  
**Cons**: Hard to test, no separation of concerns

### Recommended Structure (Separate `plugin.py`)

```python
# plugins/my-plugin/__init__.py
from core.event_bus import EventBus
from .plugin import MyPlugin

PLUGIN_INFO = {
    "name": "my-plugin",
    "version": "1.0.0",
    "commands": ["mycommand"],
    "description": "Well-structured plugin"
}

async def start(event_bus: EventBus):
    plugin = MyPlugin(event_bus)
    await plugin.register()
    return plugin

async def stop(plugin):
    await plugin.cleanup()
```

```python
# plugins/my-plugin/plugin.py
class MyPlugin:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.data = {}  # Plugin state
    
    async def register(self):
        await self.event_bus.subscribe("plugin.my-plugin.command", self.handle_command)
    
    async def handle_command(self, event: Event):
        # Business logic here
        pass
    
    async def cleanup(self):
        # Cleanup here
        pass
```

**Pros**: Testable, clear separation, scales well  
**Cons**: Slightly more boilerplate

### Complex Plugin (Multiple Files)

```
plugins/my-plugin/
├── __init__.py          # Plugin entry point
├── plugin.py            # Main plugin class
├── handlers.py          # Command handlers
├── utils.py             # Helper functions
├── models.py            # Data models
├── test_plugin.py       # Tests
├── test_handlers.py
├── README.md
└── migrations/
    ├── 001_create_tables.sql
    └── 002_add_columns.sql
```

**Use for**: Large plugins (trivia, playlist management, complex games)

## NATS Communication

### Subscribing to Commands

```python
async def register(self):
    # Subscribe to your plugin's command subject
    await self.event_bus.subscribe("plugin.my-plugin.command", self.handle_command)
    
    # Subscribe to other subjects (e.g., CyTube events)
    await self.event_bus.subscribe("cytube.chat", self.on_chat)
    await self.event_bus.subscribe("cytube.user.join", self.on_user_join)
```

**Command Event Structure** (from CommandRouter):

```python
{
    "command": "mycommand",       # Command name (without prefix)
    "args": ["arg1", "arg2"],     # Arguments
    "user": "alice",              # User who issued command
    "channel": "main",            # Channel name
    "rank": 2,                    # User rank (0=guest, 1=user, 2=mod, 3=admin)
    "raw_message": "!mycommand arg1 arg2"
}
```

### Sending Chat Messages

```python
async def send_message(self, message: str):
    await self.event_bus.publish("cytube.send.chat", {
        "message": message
    })
```

**Example**:

```python
await self.event_bus.publish("cytube.send.chat", {
    "message": "🎲 Rolled 2d6: [3, 5] = 8"
})
```

### Sending Private Messages

```python
async def send_pm(self, user: str, message: str):
    await self.event_bus.publish("cytube.send.pm", {
        "to": user,
        "message": message
    })
```

### Request/Reply Pattern

For synchronous operations (e.g., asking another plugin for data):

```python
# Request
response = await self.event_bus.request("plugin.quote-db.request", {
    "action": "random",
    "channel": "main"
}, timeout=5)

# Check response
if response["success"]:
    quote = response["data"]
    await self.send_message(f"Quote: {quote['text']}")
else:
    await self.send_message(f"Error: {response['error']}")
```

### Emitting Custom Events

```python
# Emit event for other plugins to consume
await self.event_bus.publish("plugin.my-plugin.event.something_happened", {
    "event_type": "milestone_reached",
    "data": {"score": 100}
})

# Other plugins can subscribe
await self.event_bus.subscribe("plugin.my-plugin.event.*", self.on_my_plugin_event)
```

## Database Access

**IMPORTANT**: Plugins access database via NATS, NOT SQLAlchemy directly.

### Get Record by ID

```python
response = await self.event_bus.request("database.get", {
    "collection": "quotes",
    "id": 42
}, timeout=5)

if response["success"]:
    quote = response["data"]
    # quote = {"id": 42, "text": "Hello!", "user": "alice", "timestamp": ...}
else:
    # Handle error
    logger.error(f"Database get failed: {response['error']}")
```

### Create/Update Record

```python
# Create new record (id=None for auto-increment)
response = await self.event_bus.request("database.set", {
    "collection": "quotes",
    "id": None,
    "data": {
        "text": "New quote!",
        "user": "bob",
        "timestamp": time.time()
    }
}, timeout=5)

if response["success"]:
    new_id = response["id"]
    logger.info(f"Created quote #{new_id}")
```

### Query Records

```python
response = await self.event_bus.request("database.query", {
    "collection": "quotes",
    "filter": {"user": "alice"},
    "limit": 10,
    "order_by": "timestamp DESC"
}, timeout=10)

if response["success"]:
    quotes = response["data"]
    count = response["count"]
    # quotes = [{"id": 42, ...}, {"id": 38, ...}]
```

### Delete Record

```python
response = await self.event_bus.request("database.delete", {
    "collection": "quotes",
    "id": 42
}, timeout=5)

if response["success"]:
    logger.info("Quote deleted")
```

### Database Migrations

If your plugin needs custom tables, create migrations:

```sql
-- plugins/my-plugin/migrations/001_create_tables.sql
CREATE TABLE IF NOT EXISTS my_plugin_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    timestamp REAL NOT NULL
);

CREATE INDEX idx_my_plugin_user ON my_plugin_data(user);
```

**Run migrations** (automatically during bot startup):

```bash
python rosey.py
# PluginManager discovers and runs migrations
```

## Command Registration

Commands are registered via `PLUGIN_INFO`:

```python
PLUGIN_INFO = {
    "name": "my-plugin",
    "version": "1.0.0",
    "commands": ["cmd1", "cmd2", "cmd3"],  # Commands this plugin handles
    "description": "Plugin description"
}
```

### Single Command

```python
PLUGIN_INFO = {
    "commands": ["roll"]
}

# Handles: !roll 2d6
```

### Multiple Commands

```python
PLUGIN_INFO = {
    "commands": ["quote", "addquote", "delquote"]
}

# Handles: !quote, !addquote, !delquote
```

### Command Routing

CommandRouter uses `PLUGIN_INFO["commands"]` to route:

```
User types: !roll 2d6
CommandRouter checks: Which plugin has "roll" command?
Finds: dice-roller plugin
Routes to: plugin.dice-roller.command
```

### Handling Commands

```python
async def handle_command(self, event: Event):
    command = event.data["command"]
    args = event.data["args"]
    user = event.data["user"]
    
    if command == "quote":
        await self.show_quote(args, user)
    elif command == "addquote":
        await self.add_quote(args, user)
    elif command == "delquote":
        await self.delete_quote(args, user)
```

### Permission Checks

```python
async def handle_command(self, event: Event):
    rank = event.data.get("rank", 0)
    
    # Admin-only command
    if rank < 3:
        await self.send_message("❌ This command requires admin privileges")
        return
    
    # Proceed with command
    await self.admin_action()
```

**Rank values**:
- 0 = Guest
- 1 = Registered user
- 2 = Moderator
- 3 = Channel admin

## Testing Plugins

### Unit Tests (Business Logic)

```python
# plugins/my-plugin/test_plugin.py
import pytest
from .plugin import MyPlugin
from tests.conftest import mock_event_bus  # Use global mock

@pytest.mark.asyncio
async def test_plugin_initialization(mock_event_bus):
    plugin = MyPlugin(mock_event_bus)
    assert plugin.event_bus == mock_event_bus

@pytest.mark.asyncio
async def test_command_handler(mock_event_bus):
    plugin = MyPlugin(mock_event_bus)
    await plugin.register()
    
    # Simulate command
    from core.event_bus import Event, Priority
    event = Event(
        subject="plugin.my-plugin.command",
        data={"command": "mycommand", "args": ["test"], "user": "alice"},
        timestamp=123456.0,
        priority=Priority.NORMAL
    )
    
    await plugin.handle_command(event)
    
    # Verify response published
    assert len(mock_event_bus.published_events) == 1
    assert mock_event_bus.published_events[0]["subject"] == "cytube.send.chat"
```

### Integration Tests (NATS Contracts)

```python
# plugins/my-plugin/test_integration.py
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_plugin_responds_to_command(mock_event_bus):
    plugin = MyPlugin(mock_event_bus)
    await plugin.register()
    
    # Simulate full command flow
    await mock_event_bus.publish("plugin.my-plugin.command", {
        "command": "mycommand",
        "args": [],
        "user": "alice",
        "channel": "main",
        "rank": 1
    })
    
    # Verify response
    assert len(mock_event_bus.published_events) == 1
    response = mock_event_bus.published_events[0]
    assert response["subject"] == "cytube.send.chat"
    assert "Hello" in response["data"]["message"]
```

### Running Tests

```bash
# Run plugin tests
pytest plugins/my-plugin -v

# Run all plugin tests
pytest plugins -m plugin

# With coverage
pytest plugins/my-plugin --cov=plugins.my-plugin --cov-report=html
```

## Example: Building a Plugin

Let's build a complete plugin: **Fortune Cookie** (random fortunes).

### Step 1: Create Structure

```bash
mkdir -p plugins/fortune
cd plugins/fortune
```

### Step 2: Write `__init__.py`

```python
# plugins/fortune/__init__.py
"""
Fortune Cookie Plugin - Dispense random fortunes
"""
from core.event_bus import EventBus
from .plugin import FortunePlugin

PLUGIN_INFO = {
    "name": "fortune",
    "version": "1.0.0",
    "commands": ["fortune"],
    "description": "Get a random fortune cookie"
}

async def start(event_bus: EventBus):
    plugin = FortunePlugin(event_bus)
    await plugin.register()
    return plugin

async def stop(plugin):
    await plugin.cleanup()
```

### Step 3: Write Plugin Logic

```python
# plugins/fortune/plugin.py
import logging
import random
from typing import List
from core.event_bus import EventBus, Event

logger = logging.getLogger(__name__)

class FortunePlugin:
    """Fortune cookie plugin."""
    
    FORTUNES: List[str] = [
        "You will have a pleasant surprise.",
        "A thrilling time is in your future.",
        "You will make many changes before settling satisfactorily.",
        "Good news will come to you by mail.",
        "Your dearest wish will come true.",
        "You will be successful in your work.",
        "An important person will offer you support."
    ]
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
    
    async def register(self):
        """Register NATS subscriptions."""
        await self.event_bus.subscribe("plugin.fortune.command", self.handle_command)
        self.logger.info("FortunePlugin registered")
    
    async def handle_command(self, event: Event):
        """Handle !fortune command."""
        # Pick random fortune
        fortune = random.choice(self.FORTUNES)
        
        # Send to chat
        await self.event_bus.publish("cytube.send.chat", {
            "message": f"🥠 {fortune}"
        })
        
        self.logger.info(f"Dispensed fortune to {event.data.get('user')}")
    
    async def cleanup(self):
        """Cleanup on shutdown."""
        self.logger.info("FortunePlugin cleanup")
```

### Step 4: Write Tests

```python
# plugins/fortune/test_plugin.py
import pytest
from core.event_bus import Event, Priority
from .plugin import FortunePlugin

@pytest.mark.asyncio
async def test_fortune_plugin_responds(mock_event_bus):
    """Test fortune plugin sends fortune."""
    plugin = FortunePlugin(mock_event_bus)
    await plugin.register()
    
    # Simulate command
    event = Event(
        subject="plugin.fortune.command",
        data={"command": "fortune", "args": [], "user": "alice"},
        timestamp=123456.0,
        priority=Priority.NORMAL
    )
    
    await plugin.handle_command(event)
    
    # Verify response
    assert len(mock_event_bus.published_events) == 1
    response = mock_event_bus.published_events[0]
    assert response["subject"] == "cytube.send.chat"
    assert "🥠" in response["data"]["message"]

@pytest.mark.asyncio
async def test_fortune_plugin_picks_random_fortune(mock_event_bus):
    """Test fortune is random."""
    plugin = FortunePlugin(mock_event_bus)
    await plugin.register()
    
    fortunes = set()
    for _ in range(20):  # Run 20 times
        mock_event_bus.published_events.clear()
        
        event = Event(
            subject="plugin.fortune.command",
            data={"command": "fortune", "args": [], "user": "alice"},
            timestamp=123456.0,
            priority=Priority.NORMAL
        )
        
        await plugin.handle_command(event)
        message = mock_event_bus.published_events[0]["data"]["message"]
        fortunes.add(message)
    
    # Should get at least 3 different fortunes (highly likely)
    assert len(fortunes) >= 3
```

### Step 5: Enable and Test

```json
// config.json
{
  "plugins": {
    "enabled": ["fortune"]
  }
}
```

```bash
# Run bot
python rosey.py

# In CyTube chat
!fortune
# Bot: "🥠 You will have a pleasant surprise."
```

### Step 6: Add Database (Optional)

Store favorite fortunes:

```python
# plugins/fortune/plugin.py (extended)
async def handle_command(self, event: Event):
    args = event.data.get("args", [])
    
    # !fortune favorite - Show user's favorite
    if args and args[0] == "favorite":
        favorite = await self.get_favorite(event.data["user"])
        await self.event_bus.publish("cytube.send.chat", {
            "message": f"🥠 Your favorite: {favorite}"
        })
        return
    
    # Pick random fortune
    fortune = random.choice(self.FORTUNES)
    
    # Save as favorite
    await self.save_favorite(event.data["user"], fortune)
    
    await self.event_bus.publish("cytube.send.chat", {
        "message": f"🥠 {fortune}"
    })

async def get_favorite(self, user: str) -> str:
    response = await self.event_bus.request("database.get", {
        "collection": "fortune_favorites",
        "id": user
    })
    
    if response["success"]:
        return response["data"]["fortune"]
    return "No favorite yet!"

async def save_favorite(self, user: str, fortune: str):
    await self.event_bus.request("database.set", {
        "collection": "fortune_favorites",
        "id": user,
        "data": {"fortune": fortune, "timestamp": time.time()}
    })
```

## Best Practices

### 1. Always Validate Event Data

```python
async def handle_command(self, event: Event):
    # BAD: Assume structure
    user = event.data["user"]  # KeyError if missing!
    
    # GOOD: Validate
    if "user" not in event.data:
        self.logger.error("Missing user in event")
        return
    
    user = event.data["user"]
```

### 2. Use Descriptive Variable Names

```python
# BAD
await self.event_bus.publish("cytube.send.chat", {"message": msg})

# GOOD
response_message = f"🎲 Rolled {notation}: {result}"
await self.event_bus.publish("cytube.send.chat", {"message": response_message})
```

### 3. Log Important Actions

```python
self.logger.info(f"User {user} rolled {notation} = {result}")
self.logger.warning(f"Invalid notation: {notation}")
self.logger.error(f"Database query failed: {error}")
```

### 4. Handle Timeouts

```python
try:
    response = await self.event_bus.request("database.get", {...}, timeout=5)
except asyncio.TimeoutError:
    await self.event_bus.publish("cytube.send.chat", {
        "message": "❌ Database timeout"
    })
```

### 5. Use Type Hints

```python
from typing import List, Dict, Optional

async def handle_command(self, event: Event) -> None:
    args: List[str] = event.data.get("args", [])
    user: str = event.data["user"]
```

### 6. Document Commands

```python
# plugins/my-plugin/__init__.py
PLUGIN_INFO = {
    "name": "my-plugin",
    "version": "1.0.0",
    "commands": ["mycommand"],
    "description": "Does something cool",
    "usage": {
        "mycommand": "!mycommand [args] - Does something cool"
    }
}
```

### 7. Graceful Degradation

```python
# Try database, fall back to default
response = await self.event_bus.request("database.get", {...})

if response["success"]:
    data = response["data"]
else:
    # Use default
    data = {"default": "value"}
    self.logger.warning(f"Database failed, using default: {response['error']}")
```

## Deployment

### Development

```bash
# Enable plugin in config
vim config.json  # Add plugin to "enabled" list

# Run bot
python rosey.py
```

### Production

```bash
# 1. Copy plugin to production server
scp -r plugins/my-plugin user@server:/path/to/rosey/plugins/

# 2. Enable plugin in production config
ssh user@server
vim /path/to/rosey/config.json

# 3. Restart bot
sudo systemctl restart rosey
```

### Standalone Plugin (Advanced)

Run plugin as separate process:

```python
# plugins/my-plugin/standalone.py
import asyncio
import json
from nats.aio.client import Client as NATS
from plugin import MyPlugin

async def main():
    # Connect to NATS
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    
    # Wrap NATS client as EventBus
    from core.event_bus import EventBus
    event_bus = EventBus(nc)
    
    # Start plugin
    plugin = MyPlugin(event_bus)
    await plugin.register()
    
    print("Standalone plugin running...")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

```bash
# Run standalone
python plugins/my-plugin/standalone.py
```

**Benefits**: Process isolation, independent deployment, separate logging.

## Summary

**Plugin Development Checklist**:

- [x] Create plugin directory (`plugins/my-plugin/`)
- [x] Write `__init__.py` with `PLUGIN_INFO`, `start()`, `stop()`
- [x] Write plugin class in `plugin.py`
- [x] Subscribe to `plugin.my-plugin.command`
- [x] Handle commands via NATS
- [x] Use `database.*` subjects for data access
- [x] Write tests (`test_plugin.py`)
- [x] Document commands (README.md)
- [x] Enable in `config.json`
- [x] Test in development (`python rosey.py`)

**Key Takeaways**:

1. **NATS-only communication** - No direct imports of core or other plugins
2. **Database via NATS** - Use `database.*` subjects, not SQLAlchemy
3. **Test NATS contracts** - Mock EventBus, verify published events
4. **Graceful failures** - Validate data, handle timeouts, log errors
5. **Self-contained** - Plugin can be enabled/disabled without affecting others

**Result**: Clean, testable, loosely-coupled plugins that work in v1.0's plugin-first architecture.

---

**Next Steps**:
- Read [NATS-CONTRACTS.md](NATS-CONTRACTS.md) for complete event reference
- Study existing plugins (`plugins/dice-roller/`, `plugins/8ball/`)
- Join CyTube community for support

Happy plugin building! 🎉
