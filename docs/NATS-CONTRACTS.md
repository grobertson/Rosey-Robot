# NATS Event Contracts

Complete reference for all NATS subjects used in Rosey v1.0. This document defines the event interfaces that all components must follow.

## Table of Contents

- [Subject Namespace Design](#subject-namespace-design)
- [Event Structure](#event-structure)
- [CyTube Events](#cytube-events)
- [Plugin Events](#plugin-events)
- [Platform Events](#platform-events)
- [Database Events](#database-events)
- [Error Handling](#error-handling)
- [Correlation IDs](#correlation-ids)
- [Best Practices](#best-practices)

## Subject Namespace Design

Rosey uses hierarchical NATS subjects for clear separation of concerns:

```
cytube.*         # CyTube platform events (incoming from CyTube server)
  ├── chat       # Chat messages
  ├── user.*     # User events (join, leave, rank change)
  ├── media.*    # Media events (change, queue, delete)
  └── send.*     # Outgoing to CyTube (chat, pm, emote)

plugin.*         # Plugin-specific events
  ├── {name}.*   # Per-plugin namespace
  │   ├── command      # Command routing
  │   ├── event        # Plugin-emitted events
  │   └── request      # Plugin requests (e.g., trivia.request.question)

platform.*       # Platform-wide events
  ├── startup    # Bot startup complete
  ├── shutdown   # Bot shutting down
  └── heartbeat  # Health check

database.*       # Database operations
  ├── get        # Retrieve record
  ├── set        # Create/update record
  ├── query      # Query with filter
  └── delete     # Delete record
```

**Wildcard subscriptions**:

```python
# Subscribe to all CyTube events
await event_bus.subscribe("cytube.*", handler)

# Subscribe to all plugin commands
await event_bus.subscribe("plugin.*.command", handler)

# Subscribe to all database operations
await event_bus.subscribe("database.*", handler)
```

## Event Structure

All NATS events use the `Event` dataclass:

```python
@dataclass
class Event:
    subject: str                    # NATS subject (e.g., "cytube.chat")
    data: Dict[str, Any]            # Event payload
    timestamp: float                # Unix timestamp (seconds since epoch)
    priority: Priority              # LOW, NORMAL, HIGH, CRITICAL
    correlation_id: Optional[str]   # For tracking related events
    metadata: Dict[str, Any]        # Optional metadata

class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
```

**Example**:

```python
event = Event(
    subject="cytube.chat",
    data={
        "user": "alice",
        "message": "!roll 2d6",
        "channel": "main",
        "rank": 2
    },
    timestamp=1732645200.0,
    priority=Priority.NORMAL,
    correlation_id="550e8400-e29b-41d4-a716-446655440000",
    metadata={"source": "cytube_connector"}
)
```

## CyTube Events

### cytube.chat

**Source**: CytubeConnector (incoming chat messages)

**Consumers**: CommandRouter, plugins (if subscribed directly)

**Payload**:

```python
{
    "user": str,        # Username
    "message": str,     # Chat message text
    "channel": str,     # Channel name
    "rank": int,        # User rank (0=guest, 1=user, 2=mod, 3=admin)
    "time": int         # Timestamp (milliseconds)
}
```

**Example**:

```python
await event_bus.publish("cytube.chat", {
    "user": "alice",
    "message": "!roll 2d6",
    "channel": "main",
    "rank": 2,
    "time": 1732645200000
})
```

**Notes**:
- CommandRouter parses messages starting with `!` (configurable prefix)
- Plugins can subscribe directly for chat monitoring

### cytube.user.join

**Source**: CytubeConnector (user joined channel)

**Consumers**: Plugins (for welcome messages, user tracking)

**Payload**:

```python
{
    "user": str,        # Username
    "channel": str,     # Channel name
    "rank": int,        # User rank
    "time": int         # Timestamp (milliseconds)
}
```

**Example**:

```python
await event_bus.publish("cytube.user.join", {
    "user": "bob",
    "channel": "main",
    "rank": 1,
    "time": 1732645200000
})
```

### cytube.user.leave

**Source**: CytubeConnector (user left channel)

**Consumers**: Plugins (for tracking, cleanup)

**Payload**:

```python
{
    "user": str,        # Username
    "channel": str      # Channel name
}
```

### cytube.media.change

**Source**: CytubeConnector (media changed in playlist)

**Consumers**: Plugins (media tracking, announcements)

**Payload**:

```python
{
    "title": str,           # Media title
    "url": str,             # Media URL
    "type": str,            # Media type (yt, vm, dm, etc.)
    "duration": int,        # Duration in seconds
    "channel": str,         # Channel name
    "queued_by": str        # User who queued media
}
```

**Example**:

```python
await event_bus.publish("cytube.media.change", {
    "title": "Cool Video",
    "url": "https://youtube.com/watch?v=...",
    "type": "yt",
    "duration": 240,
    "channel": "main",
    "queued_by": "alice"
})
```

### cytube.send.chat

**Source**: Plugins (send chat message to CyTube)

**Consumer**: CytubeConnector (translates to WebSocket)

**Payload**:

```python
{
    "message": str,     # Message text
    "channel": str      # Channel name (optional, uses current)
}
```

**Example**:

```python
await event_bus.publish("cytube.send.chat", {
    "message": "🎲 Rolled 2d6: [3, 5] = 8",
    "channel": "main"
})
```

**Notes**:
- CytubeConnector translates to `{"name": "chatMsg", "args": [{"msg": "..."}]}`
- Message length limited to CyTube's limit (240 chars default)

### cytube.send.pm

**Source**: Plugins (send private message)

**Consumer**: CytubeConnector

**Payload**:

```python
{
    "to": str,          # Recipient username
    "message": str      # Message text
}
```

**Example**:

```python
await event_bus.publish("cytube.send.pm", {
    "to": "alice",
    "message": "Your trivia score: 42 points"
})
```

### cytube.send.emote

**Source**: Plugins (send emote/action)

**Consumer**: CytubeConnector

**Payload**:

```python
{
    "emote": str,       # Emote text (e.g., "dances")
    "channel": str      # Channel name
}
```

**Example**:

```python
await event_bus.publish("cytube.send.emote", {
    "emote": "rolls the dice",
    "channel": "main"
})
```

**Result**: Bot says "/me rolls the dice" in chat.

## Plugin Events

### plugin.{name}.command

**Source**: CommandRouter (routed command)

**Consumer**: Specific plugin

**Payload**:

```python
{
    "command": str,             # Command name (without prefix)
    "args": List[str],          # Command arguments
    "user": str,                # User who issued command
    "channel": str,             # Channel name
    "rank": int,                # User rank
    "raw_message": str          # Original message
}
```

**Example**:

```python
# User types: !roll 2d6+3
await event_bus.publish("plugin.dice-roller.command", {
    "command": "roll",
    "args": ["2d6+3"],
    "user": "alice",
    "channel": "main",
    "rank": 2,
    "raw_message": "!roll 2d6+3"
})
```

**Notes**:
- Router determines plugin based on command registration
- Plugin subscribes to `plugin.{name}.command` (e.g., `plugin.dice-roller.command`)

### plugin.{name}.event

**Source**: Plugin (emitting custom event)

**Consumer**: Other plugins, core components

**Payload**: Plugin-defined (no fixed structure)

**Example** (trivia plugin emits game start):

```python
await event_bus.publish("plugin.trivia.event", {
    "event_type": "game_start",
    "channel": "main",
    "questions": 10,
    "difficulty": "medium"
})
```

**Use case**: Cross-plugin communication (e.g., countdown plugin listens for trivia game events).

### plugin.{name}.request

**Source**: Another plugin or core component

**Consumer**: Specific plugin (request/reply pattern)

**Payload**: Plugin-defined

**Example** (request random quote):

```python
response = await event_bus.request("plugin.quote-db.request", {
    "action": "random",
    "channel": "main"
}, timeout=5)

# Response
{
    "success": True,
    "quote": {
        "id": 42,
        "text": "Hello, world!",
        "user": "alice",
        "timestamp": 1732645200
    }
}
```

**Notes**:
- Uses NATS request/reply (single responder)
- Timeout default 5 seconds (configurable)

## Platform Events

### platform.startup

**Source**: Rosey orchestrator (startup complete)

**Consumer**: Plugins (initialization hooks)

**Payload**:

```python
{
    "version": str,             # Rosey version (e.g., "1.0.0")
    "plugins": List[str],       # Loaded plugin names
    "timestamp": float          # Startup timestamp
}
```

**Example**:

```python
await event_bus.publish("platform.startup", {
    "version": "1.0.0",
    "plugins": ["dice-roller", "8ball", "trivia"],
    "timestamp": 1732645200.0
})
```

**Use case**: Plugins can perform startup tasks (e.g., restore timers, load cache).

### platform.shutdown

**Source**: Rosey orchestrator (shutdown initiated)

**Consumer**: Plugins (cleanup hooks)

**Payload**:

```python
{
    "reason": str,              # Shutdown reason (e.g., "user_requested")
    "timestamp": float          # Shutdown timestamp
}
```

**Example**:

```python
await event_bus.publish("platform.shutdown", {
    "reason": "user_requested",
    "timestamp": 1732645300.0
})
```

**Use case**: Plugins save state, cancel timers, flush buffers.

### platform.heartbeat

**Source**: Rosey orchestrator (periodic health check)

**Consumer**: Monitoring, plugins

**Payload**:

```python
{
    "timestamp": float,         # Current timestamp
    "uptime": float,            # Uptime in seconds
    "plugins_active": int,      # Number of running plugins
    "nats_connected": bool      # NATS connection status
}
```

**Example**:

```python
await event_bus.publish("platform.heartbeat", {
    "timestamp": 1732645260.0,
    "uptime": 3600.0,
    "plugins_active": 6,
    "nats_connected": True
})
```

**Frequency**: Every 60 seconds (configurable).

## Database Events

### database.get

**Source**: Plugin (request record)

**Consumer**: DatabaseService (request/reply)

**Request Payload**:

```python
{
    "collection": str,          # Collection/table name
    "id": Union[int, str]       # Record ID
}
```

**Response Payload**:

```python
{
    "success": bool,            # True if found
    "data": Dict[str, Any],     # Record data (if found)
    "error": Optional[str]      # Error message (if failed)
}
```

**Example**:

```python
# Request
response = await event_bus.request("database.get", {
    "collection": "quotes",
    "id": 42
})

# Response
{
    "success": True,
    "data": {
        "id": 42,
        "text": "Hello, world!",
        "user": "alice",
        "timestamp": 1732645200
    },
    "error": None
}
```

### database.set

**Source**: Plugin (create/update record)

**Consumer**: DatabaseService

**Request Payload**:

```python
{
    "collection": str,          # Collection/table name
    "id": Optional[Union[int, str]],  # Record ID (None for auto-increment)
    "data": Dict[str, Any]      # Record data
}
```

**Response Payload**:

```python
{
    "success": bool,            # True if saved
    "id": Union[int, str],      # Record ID (new or existing)
    "error": Optional[str]      # Error message (if failed)
}
```

**Example**:

```python
# Create new quote
response = await event_bus.request("database.set", {
    "collection": "quotes",
    "id": None,  # Auto-increment
    "data": {
        "text": "New quote!",
        "user": "bob",
        "timestamp": 1732645300
    }
})

# Response
{
    "success": True,
    "id": 143,
    "error": None
}
```

### database.query

**Source**: Plugin (query with filter)

**Consumer**: DatabaseService

**Request Payload**:

```python
{
    "collection": str,              # Collection/table name
    "filter": Dict[str, Any],       # Filter conditions
    "limit": Optional[int],         # Max results (default 100)
    "offset": Optional[int],        # Pagination offset
    "order_by": Optional[str]       # Sort field
}
```

**Response Payload**:

```python
{
    "success": bool,                # True if query succeeded
    "data": List[Dict[str, Any]],   # Matching records
    "count": int,                   # Total matching count
    "error": Optional[str]          # Error message (if failed)
}
```

**Example**:

```python
# Find quotes by user
response = await event_bus.request("database.query", {
    "collection": "quotes",
    "filter": {"user": "alice"},
    "limit": 10,
    "order_by": "timestamp DESC"
})

# Response
{
    "success": True,
    "data": [
        {"id": 42, "text": "Hello!", "user": "alice", "timestamp": 1732645200},
        {"id": 38, "text": "Goodbye!", "user": "alice", "timestamp": 1732640000}
    ],
    "count": 2,
    "error": None
}
```

### database.delete

**Source**: Plugin (delete record)

**Consumer**: DatabaseService

**Request Payload**:

```python
{
    "collection": str,          # Collection/table name
    "id": Union[int, str]       # Record ID
}
```

**Response Payload**:

```python
{
    "success": bool,            # True if deleted
    "error": Optional[str]      # Error message (if failed)
}
```

**Example**:

```python
response = await event_bus.request("database.delete", {
    "collection": "quotes",
    "id": 42
})

# Response
{
    "success": True,
    "error": None
}
```

## Error Handling

### Error Response Format

All request/reply events should return errors in this format:

```python
{
    "success": False,
    "error": "Human-readable error message",
    "error_code": "SNAKE_CASE_ERROR_CODE",  # Optional
    "details": {...}  # Optional additional context
}
```

**Example** (database.get for missing record):

```python
{
    "success": False,
    "error": "Quote #999 not found",
    "error_code": "RECORD_NOT_FOUND",
    "details": {"collection": "quotes", "id": 999}
}
```

### Standard Error Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| `RECORD_NOT_FOUND` | Database record doesn't exist | database.get, database.delete |
| `INVALID_INPUT` | Invalid parameters | Command parsing, validation |
| `PERMISSION_DENIED` | User lacks permission | Admin commands |
| `TIMEOUT` | Operation timed out | NATS request/reply timeout |
| `NATS_ERROR` | NATS communication failed | EventBus errors |
| `DATABASE_ERROR` | Database operation failed | SQLAlchemy errors |
| `PLUGIN_ERROR` | Plugin-specific error | Plugin business logic errors |

### Handling NATS Timeouts

Request/reply operations have timeouts (default 5s):

```python
try:
    response = await event_bus.request("database.get", {...}, timeout=5)
except asyncio.TimeoutError:
    # Handle timeout
    await event_bus.publish("cytube.send.chat", {
        "message": "❌ Database request timed out"
    })
```

**Best practices**:
- Use longer timeouts for slow operations (e.g., complex queries: 10s)
- Log timeout occurrences for monitoring
- Return user-friendly error messages

### Handling Malformed Events

Validate event data structure:

```python
async def handle_command(event: Event):
    # Validate required fields
    if "command" not in event.data or "user" not in event.data:
        logger.error(f"Malformed command event: {event.data}")
        return
    
    # Proceed with processing
    command = event.data["command"]
    user = event.data["user"]
    # ...
```

## Correlation IDs

Correlation IDs track related events across components.

### Generating Correlation IDs

```python
import uuid

correlation_id = str(uuid.uuid4())
# Example: "550e8400-e29b-41d4-a716-446655440000"
```

### Using Correlation IDs

```python
# Original command
correlation_id = str(uuid.uuid4())
await event_bus.publish("plugin.dice-roller.command", {
    "command": "roll",
    "args": ["2d6"]
}, correlation_id=correlation_id)

# Plugin processes and responds
await event_bus.publish("cytube.send.chat", {
    "message": "🎲 Result: 8"
}, correlation_id=correlation_id)

# Logs show relationship
# [INFO] [550e8400-...] Command: roll 2d6
# [INFO] [550e8400-...] Plugin: dice-roller processing
# [INFO] [550e8400-...] Response: 🎲 Result: 8
```

### Benefits

- **Tracing**: Follow events through entire system
- **Debugging**: Identify which command caused which response
- **Monitoring**: Track command latency (start to finish)

### Automatic Propagation

EventBus automatically propagates correlation IDs:

```python
# Subscriber receives event with correlation_id
async def handle_command(event: Event):
    # event.correlation_id is automatically set
    
    # Publish response (correlation_id auto-included)
    await self.event_bus.publish("cytube.send.chat", {
        "message": "Done!"
    })  # Correlation ID propagated automatically
```

## Best Practices

### 1. Always Validate Event Data

```python
async def handle_event(event: Event):
    # BAD: Assume data structure
    user = event.data["user"]  # KeyError if missing!
    
    # GOOD: Validate and handle missing fields
    if "user" not in event.data:
        logger.error(f"Missing 'user' in event: {event.subject}")
        return
    
    user = event.data["user"]
```

### 2. Use Request/Reply for Synchronous Operations

```python
# BAD: Publish and hope for response
await event_bus.publish("database.get", {...})
# How do we get the response?

# GOOD: Use request/reply
response = await event_bus.request("database.get", {...}, timeout=5)
if response["success"]:
    data = response["data"]
```

### 3. Use Publish for Fire-and-Forget

```python
# GOOD: Send chat message (no response needed)
await event_bus.publish("cytube.send.chat", {
    "message": "Hello!"
})
```

### 4. Set Appropriate Timeouts

```python
# Short timeout for local operations
response = await event_bus.request("plugin.dice-roller.request", {...}, timeout=2)

# Longer timeout for complex queries
response = await event_bus.request("database.query", {...}, timeout=10)
```

### 5. Use Specific Subjects

```python
# BAD: Too generic
await event_bus.publish("plugin.event", {...})

# GOOD: Specific subject
await event_bus.publish("plugin.trivia.event.game_start", {...})
```

**Benefits**: Easier filtering, clearer intent, better debugging.

### 6. Document Custom Events

If your plugin emits custom events, document them:

```python
# plugins/trivia/EVENTS.md

## plugin.trivia.event.game_start

Emitted when trivia game starts.

**Payload**:
- `channel` (str): Channel name
- `questions` (int): Number of questions
- `difficulty` (str): Difficulty level
```

### 7. Handle Partial Failures Gracefully

```python
# Request database, handle failure
response = await event_bus.request("database.get", {...}, timeout=5)

if not response["success"]:
    # Fallback: Use default value
    data = {"text": "Default quote", "user": "system"}
    logger.warning(f"Database failed, using default: {response['error']}")
else:
    data = response["data"]
```

### 8. Use Correlation IDs for Complex Flows

```python
# Multi-step operation
correlation_id = str(uuid.uuid4())

# Step 1: Get user data
user_data = await event_bus.request("database.get", {...}, 
                                    correlation_id=correlation_id)

# Step 2: Process
result = process(user_data)

# Step 3: Send response
await event_bus.publish("cytube.send.chat", {
    "message": result
}, correlation_id=correlation_id)

# All steps traceable via correlation_id
```

## Testing NATS Contracts

### Mock EventBus for Testing

```python
# tests/conftest.py
class MockEventBus:
    def __init__(self):
        self.published_events = []
    
    async def publish(self, subject: str, data: Dict, **kwargs):
        self.published_events.append({"subject": subject, "data": data})
    
    async def request(self, subject: str, data: Dict, **kwargs):
        # Return mock responses based on subject
        if subject == "database.get":
            return {"success": True, "data": {"id": 42, "text": "Mock quote"}}
        return {"success": False, "error": "Not mocked"}
```

### Test Event Publishing

```python
@pytest.mark.asyncio
async def test_plugin_publishes_response(mock_event_bus):
    plugin = DiceRollerPlugin(mock_event_bus)
    
    # Simulate command
    await plugin.handle_command(Event(
        subject="plugin.dice-roller.command",
        data={"command": "roll", "args": ["2d6"], "user": "alice"}
    ))
    
    # Verify response published
    assert len(mock_event_bus.published_events) == 1
    event = mock_event_bus.published_events[0]
    assert event["subject"] == "cytube.send.chat"
    assert "🎲" in event["data"]["message"]
```

### Test Request/Reply

```python
@pytest.mark.asyncio
async def test_plugin_requests_database(mock_event_bus):
    plugin = QuotePlugin(mock_event_bus)
    
    # Simulate command
    await plugin.handle_command(Event(
        subject="plugin.quote-db.command",
        data={"command": "quote", "args": ["42"], "user": "alice"}
    ))
    
    # Verify database.get was called (mocked)
    # Mock should return test data
    # Verify response contains quote
    assert len(mock_event_bus.published_events) == 1
    assert "Mock quote" in mock_event_bus.published_events[0]["data"]["message"]
```

## Summary

**NATS Contract Principles**:

1. **Hierarchical subjects** - Clear namespace separation (cytube.*, plugin.*, platform.*, database.*)
2. **Standard event structure** - All events use `Event` dataclass with consistent fields
3. **Request/reply for sync** - Database queries, plugin requests use request/reply pattern
4. **Publish for async** - Chat messages, notifications use fire-and-forget
5. **Error handling** - Standard error response format with `success`, `error`, `error_code`
6. **Correlation IDs** - Track related events across system
7. **Validation** - Always validate event data structure
8. **Documentation** - Document custom plugin events

**Result**: Clear, testable, loosely-coupled communication between all components.

---

**Next**: [PLUGIN-DEVELOPMENT.md](PLUGIN-DEVELOPMENT.md) - Use these contracts to build plugins.
