# Architecture Overview

## Design Philosophy

This project follows a **monolithic architecture** where all components live together in a single repository. This design choice prioritizes:

1. **Development Speed**: No package installation between changes
2. **Transparency**: All code is visible and editable
3. **Simplicity**: Straightforward file organization
4. **Flexibility**: Easy to customize any layer

## Layer Architecture

### Classic Monolithic (v1.x)

```
┌─────────────────────────────────────────────────────┐
│              Bot Applications & Examples             │
│  • bot/rosey/ - Full-featured main bot              │
│  • examples/ - Reference implementations            │
│    - tui/ (terminal UI), log/, echo/, markov/       │
│  • Business logic                                    │
│  • Event handlers                                    │
│  • Bot-specific features                            │
└─────────────────────────────────────────────────────┘
                        ↓ uses
┌─────────────────────────────────────────────────────┐
│               Common Utilities (common/)             │
│  • Configuration loading (get_config)                │
│  • REPL shell interface                             │
│  • Logging setup                                     │
│  • Shared helper functions                          │
└─────────────────────────────────────────────────────┘
                        ↓ uses
┌─────────────────────────────────────────────────────┐
│              Core Library (lib/)                     │
│  • Bot base class                                    │
│  • Channel/Playlist/User models                     │
│  • Socket.IO communication                           │
│  • Event system                                      │
│  • CyTube protocol implementation                   │
└─────────────────────────────────────────────────────┘
                        ↓ uses
┌─────────────────────────────────────────────────────┐
│           External Dependencies                      │
│  • websockets (WebSocket client)                     │
│  • requests (HTTP client)                            │
│  • asyncio (Python standard library)                │
└─────────────────────────────────────────────────────┘
```

### Event-Driven with NATS (v2.x - Sprint 9)

**⚠️ Breaking Change:** As of Sprint 9 (The Accountant), Rosey has transitioned to an event-driven architecture using NATS as the central event bus. This enables service isolation, independent scaling, and proper separation of concerns.

```
┌──────────────────────────────────────────────────────────────┐
│                    Bot Applications                           │
│  • bot/rosey/ - Main bot (publishes events)                  │
│  • Multiple bot instances supported                          │
│  • Publishes: user events, chat, media, status               │
│  • Subscribes: None (stateless)                              │
└──────────────────────────────────────────────────────────────┘
                        ↓ publishes events
┌──────────────────────────────────────────────────────────────┐
│                   NATS Event Bus                              │
│  • Subject Hierarchy: rosey.platform.*, rosey.events.*       │
│  • Pub/Sub: Broadcast events to all subscribers              │
│  • Request/Reply: Query services synchronously                │
│  • Guaranteed delivery (when configured)                     │
│  • Message persistence (JetStream optional)                  │
└──────────────────────────────────────────────────────────────┘
       ↓ subscribes              ↓ subscribes         ↓ subscribes
┌───────────────────┐  ┌────────────────────┐  ┌───────────────┐
│ Database Service  │  │  Future Services   │  │  Monitoring   │
│ (lib/database_    │  │  • Analytics       │  │  • Prometheus │
│  service.py)      │  │  • Moderation      │  │  • Grafana    │
│                   │  │  • Notifications   │  │  • Alerting   │
│ Subscribes to:    │  │  • Integrations    │  │               │
│ • user.joined     │  └────────────────────┘  └───────────────┘
│ • user.left       │
│ • chat.message    │
│ • media.played    │
│ • stats.usercount │
│                   │
│ Provides:         │
│ • Query endpoints │
│ • Data storage    │
│ • SQLite backend  │
└───────────────────┘
```

### Event Flow (Sprint 9)

```
1. CyTube Server
   ↓ WebSocket
2. Bot (lib/bot.py)
   • Normalizes CyTube events → NormalizedEvent
   • Publishes to NATS: rosey.platform.cytube.{event_type}
   ↓ NATS Publish
3. NATS Event Bus
   • Routes to all interested subscribers
   • Guaranteed delivery (at-least-once)
   ↓ NATS Subscribe
4. Services (e.g., DatabaseService)
   • Receive events asynchronously
   • Process independently
   • Store/analyze/react
   ↓ Optional Reply
5. Bot (Request/Reply pattern)
   • Query services for data
   • Timeout-based fallback
```

### Service Isolation Benefits

**Before Sprint 9 (Monolithic):**
- Bot tightly coupled to database
- Single process failure = total failure
- Hard to scale horizontally
- Testing requires full stack
- Changes require bot restart

**After Sprint 9 (Event-Driven):**
- ✅ **Independent Processes:** Bot and database run separately
- ✅ **Fault Tolerance:** Database crash doesn't kill bot
- ✅ **Horizontal Scaling:** Multiple bots → one database
- ✅ **Easy Testing:** Mock NATS for unit tests
- ✅ **Hot Updates:** Restart database without bot downtime
- ✅ **Extensibility:** Add new services by subscribing

## Core Components

### Sprint 9: Event-Driven Components

#### Event Normalization (lib/event_normalization.py)

**Purpose**: Convert platform-specific events into a standardized format for NATS

**Key Classes**:
- `NormalizedEvent` - Standard event container with validation
- Event type constants (`USER_JOINED`, `CHAT_MESSAGE`, etc.)
- Conversion utilities (`cytube_to_normalized()`)

**Event Structure**:
```python
@dataclass
class NormalizedEvent:
    event_type: str          # e.g., 'user.joined', 'chat.message'
    platform: str            # e.g., 'cytube'
    data: Dict[str, Any]     # Platform-specific data
    timestamp: float         # UTC timestamp
    metadata: Dict[str, Any] # Optional tracking info
```

**Example**:
```python
# CyTube event
cytube_event = {
    'name': 'addUser',
    'data': {'name': 'Alice', 'rank': 2}
}

# Normalized
normalized = cytube_to_normalized(cytube_event)
# NormalizedEvent(
#     event_type='user.joined',
#     platform='cytube',
#     data={'name': 'Alice', 'rank': 2, ...},
#     timestamp=1700000000.0,
#     metadata={}
# )
```

#### Subject Hierarchy (lib/subjects.py)

**Purpose**: Define consistent NATS subject naming for routing

**Subject Pattern**: `rosey.{category}.{source}.{event_type}`

**Categories**:
- `platform` - Events from external platforms (CyTube, Discord, etc.)
- `events` - Internal application events
- `commands` - Command execution requests
- `plugins` - Plugin lifecycle and communication

**Examples**:
```text
rosey.platform.cytube.user.joined
rosey.platform.cytube.chat.message
rosey.events.database.user_stats_updated
rosey.commands.chat.send_message
rosey.plugins.markov.generate_text
```

**Wildcards**:
- `*` matches single token: `rosey.platform.*.user.joined` (all platforms)
- `>` matches rest: `rosey.platform.cytube.>` (all CyTube events)

#### Database Service (lib/database_service.py)

**Purpose**: Isolated service for data storage via NATS

**Subscription Patterns**:
```python
# Pub/Sub (fire-and-forget)
'rosey.platform.cytube.user.joined'      → user_joined_handler()
'rosey.platform.cytube.chat.message'     → chat_message_handler()
'rosey.platform.cytube.stats.usercount'  → usercount_handler()

# Request/Reply (query)
'rosey.events.database.query.user_stats' → get_user_stats()
'rosey.events.database.query.recent_chat'→ get_recent_messages()
```

**Handler Types**:
1. **Event Handlers**: Process incoming events, update storage
2. **Query Handlers**: Return data synchronously via NATS request/reply
3. **Lifecycle**: Start/stop, health checks, graceful shutdown

**Running**:
```bash
# As module
python -m lib.database_service config.json

# As script
python lib/database_service.py config.json
```

**Test Coverage**: 26/26 tests passing
- Lifecycle: start, stop, idempotent operations
- Pub/Sub: all event handlers
- Request/Reply: query patterns
- Error handling: invalid data, missing fields
- Integration: end-to-end flows

#### Bot NATS Integration (lib/bot.py)

**Purpose**: Publish bot events to NATS instead of direct database calls

**Key Changes (Sprint 9)**:
- ⚠️ **BREAKING**: Removed `db`, `db_path`, `enable_db` parameters
- ⚠️ **BREAKING**: `nats_client` is now **required** (not optional)
- All `self.db.*` calls replaced with `self.nats.publish()`
- Graceful degradation: continues if NATS unavailable

**Publishing Pattern**:
```python
# Old (v1.x - tight coupling)
if self.db:
    self.db.user_joined(username, ...)

# New (v2.x - event-driven)
if self.nats:
    await self.nats.publish(
        subject='rosey.platform.cytube.user.joined',
        payload=json.dumps(event_data).encode()
    )
```

**Event Types Published**:
- User events: joined, left, rank changed, profile updated
- Chat events: messages, PMs, emotes
- Media events: queue, delete, play, pause
- Stats events: user count, high water marks

**Configuration (v2)**:
```json
{
  "version": 2,
  "platforms": [{
    "name": "cytube",
    "server": "https://cytu.be",
    "channel": "your_channel"
  }],
  "nats": {
    "url": "nats://localhost:4222"
  }
}
```

### lib/ - Core Library

**Purpose**: Handles all CyTube protocol interaction

**Key Files**:
- `bot.py` - Main Bot class with event system and CyTube API
- `socket_io.py` - WebSocket connection management
- `channel.py` - Channel state tracking
- `playlist.py` - Playlist state and operations
- `user.py` - User representation and permissions
- `media_link.py` - Media URL parsing (YouTube, Vimeo, etc.)

**Responsibilities**:
- WebSocket connection lifecycle
- CyTube protocol messages (emit/receive)
- State synchronization (users, playlist, channel settings)
- Permission checking
- Event emission

**Extension Points**:
- Subclass `Bot` for custom behavior
- Override event handlers (`_on_*` methods)
- Add new CyTube API methods

### common/ - Shared Utilities

**Purpose**: Reusable components for bot development

**Key Files**:
- `config.py` - JSON config loading, logging setup, proxy configuration
- `shell.py` - Interactive REPL server for runtime bot control

**Responsibilities**:
- Configuration management
- Logger configuration
- REPL server for debugging
- Shared utility functions

**Extension Points**:
- Add new configuration options
- Extend shell commands
- Add shared helper functions

### bot/ - Main Application & examples/ - Reference Implementations

**Purpose**: 
- `bot/rosey/` - Full-featured production bot with logging, shell, database
- `examples/` - Simplified reference implementations for learning

**Structure**:

```text
bot/
└── rosey/          # Main Rosey bot
    ├── rosey.py    # Full-featured implementation
    ├── prompt.md   # AI personality (for future LLM)
    └── config.json.dist

examples/
├── tui/            # ⭐ Terminal UI chat client
├── log/            # Simple chat/media logging
├── echo/           # Basic message echo
└── markov/         # Markov chain text generation
```

**Responsibilities**:
- Business logic
- Event handling
- Bot-specific features
- Configuration

**Extension Points**:
- Customize Rosey in `bot/rosey/`
- Create new examples in `examples/`
- Combine features from multiple examples
- Add custom commands and behaviors

## Event Flow

```
1. WebSocket Message Received
   ↓
2. socket_io.py: Parse message
   ↓
3. bot.py: Trigger event
   ↓
4. Internal handlers (_on_*): Update state
   ↓
5. User handlers: Custom bot logic
   ↓
6. [Optional] Send response back through socket
```

## State Management

The Bot maintains synchronized state:

```python
bot.user                    # Bot's user info
bot.channel                 # Channel state
  .name, .motd, .css, .js
  .userlist                 # All users
  .playlist                 # Playlist state
    .current               # Current media
    .queue                 # Queued items
  .permissions             # Channel permissions
```

State is updated automatically via internal event handlers (`_on_*` methods).

## Event System

### Registration
```python
bot.on('eventName', handler1, handler2, ...)
bot.off('eventName', handler1)
```

### Handler Signature
```python
async def handler(event: str, data: dict) -> bool:
    # Return True to stop propagation
    return False
```

### Event Priority
Handlers execute in registration order. Return `True` to stop propagation.

### Built-in Events
- Protocol events: `chatMsg`, `pm`, `setCurrent`, `queue`, `delete`, etc.
- Custom events: `login`, `error`

## Communication Patterns

### Request-Response
Some operations wait for confirmation:
```python
response = await bot.socket.emit(
    'eventName',
    payload,
    response_matcher,
    timeout
)
```

### Fire-and-Forget
Most state updates are broadcast:
```python
await bot.socket.emit('eventName', payload)
```

### State Sync
Channel state synced on connection:
1. Join channel
2. Receive initial state (userlist, playlist, settings)
3. Subscribe to updates

## Async Design

All I/O operations are asynchronous using `asyncio`:

- **Bot.run()**: Main event loop
- **Event handlers**: Can be sync or async
- **API methods**: All async (`await bot.chat(...)`)

### Event Loop Management
```python
loop = asyncio.get_event_loop()
bot = MyBot(loop=loop, ...)
loop.run_until_complete(bot.run())
```

## Error Handling

### Exception Hierarchy
```
CytubeError (base)
├── SocketIOError (connection issues)
├── LoginError (authentication)
├── ChannelError (general channel errors)
├── ChannelPermissionError (insufficient permissions)
└── Kicked (bot was kicked)
```

### Error Propagation
- Network errors: Caught, logged, trigger reconnect
- Permission errors: Raised to caller
- Unexpected errors in handlers: Logged, trigger 'error' event

## Future Architecture Plans

### LLM Integration Layer

```text
bot/rosey/
├── rosey.py            # Main bot
├── llm/
│   ├── client.py       # LLM API client
│   ├── context.py      # Context management
│   ├── prompts.py      # Prompt templates
│   └── filters.py      # Response filtering
└── config.json
```

### Plugin System

```text
bot/rosey/
├── rosey.py
└── plugins/
    ├── commands.py     # Command handler plugin
    ├── moderation.py   # Auto-moderation plugin
    └── playlist.py     # Playlist management plugin
```

### Multi-Channel Support
```python
class MultiBot:
    def __init__(self):
        self.bots = {}  # channel -> Bot instance
    
    async def connect(self, channel):
        bot = Bot(channel=channel, ...)
        self.bots[channel] = bot
        await bot.run()
```

## Development Workflow

### Making Changes

1. **Library Changes** (lib/)
   - Modify source
   - Test immediately (no reinstall needed)
   - Changes affect all bots

2. **Bot Changes** (bot/rosey/)
   - Modify rosey.py
   - Restart bot
   - Independent of examples

3. **Common Changes** (common/)
   - Modify utilities
   - Restart affected bots
   - Changes affect all users

4. **Example Changes** (examples/)
   - Modify for learning/testing
   - Won't affect main Rosey bot

### Testing Strategy

1. **Unit tests**: Test individual components
2. **Integration tests**: Test bot + library interaction
3. **Manual tests**: Run bots against test channels

### Debugging

1. **Enable DEBUG logging**: Set `"log_level": "DEBUG"` in config
2. **Use REPL shell**: Connect via telnet for runtime inspection
3. **Add print statements**: Direct console output
4. **Exception traces**: Full stack traces in logs

## Performance Considerations

### Bottlenecks
- WebSocket I/O (network bound)
- Message parsing (JSON deserialization)
- Event handler execution

### Optimizations
- Async I/O prevents blocking
- State caching reduces lookups
- Lazy loading for large data

### Scaling
- One bot = one connection
- Multiple bots = multiple processes
- Connection pooling not applicable

## Security Considerations

### Credentials
- Store passwords in config files (gitignored)
- Consider environment variables for production
- Never commit config.json with real credentials

### Input Validation
- Parse and sanitize all incoming messages
- Validate media URLs before queueing
- Check permissions before operations

### Rate Limiting
- Implement cooldowns for commands
- Track message frequency
- Respect channel flood protection

## Migration from Package Structure

### Package Structure (Original)

Old structure:

```text
site-packages/cytube_bot_async/  # Installed package
your-project/
└── bot.py                        # Your code
```

New structure:

```text
rosey-robot/
├── lib/           # Library code (local)
├── common/        # Shared utilities
├── bot/rosey/     # Main application
└── examples/      # Reference implementations
```

Benefits:

- No installation step
- Edit library directly
- Single source tree
- Easier debugging

### Sprint 9 Migration (v1.x → v2.x)

**Major Architecture Change**: Monolithic → Event-Driven with NATS

#### Breaking Changes

1. **Bot Constructor**:
```python
# Old (v1.x)
bot = Bot(
    url='https://cytu.be',
    channel='mychannel',
    enable_db=True,        # ❌ REMOVED
    db_path='bot.db'       # ❌ REMOVED
)

# New (v2.x)
import nats
nats_client = await nats.connect('nats://localhost:4222')
bot = Bot(
    connection=connection_adapter,
    nats_client=nats_client  # ✅ REQUIRED
)
```

2. **Configuration Format**:
```json
// Old (v1.x)
{
  "url": "https://cytu.be",
  "channel": "mychannel",
  "database": {
    "path": "bot.db",
    "enabled": true
  }
}

// New (v2.x)
{
  "version": 2,
  "platforms": [{
    "name": "cytube",
    "server": "https://cytu.be",
    "channel": "mychannel"
  }],
  "nats": {
    "url": "nats://localhost:4222"
  }
}
```

3. **Database Service**:
```bash
# Old (v1.x) - Database embedded in bot process
python bot/rosey/rosey.py config.json

# New (v2.x) - Database runs as separate service
# Terminal 1: Start NATS
nats-server

# Terminal 2: Start Database Service
python -m lib.database_service config.json

# Terminal 3: Start Bot
python bot/rosey/rosey.py config.json
```

#### Migration Steps

See [`docs/sprints/active/9-The-Accountant/MIGRATION.md`](docs/sprints/active/9-The-Accountant/MIGRATION.md) for complete guide.

**Quick Start**:
1. Install NATS: `brew install nats-server` (macOS) or download from https://nats.io
2. Migrate config: `python -m common.config bot/rosey/config.json`
3. Start NATS: `nats-server` (in background: `nats-server &`)
4. Start DatabaseService: `python -m lib.database_service config.json`
5. Start Bot: `python bot/rosey/rosey.py config.json`

#### Rollback

If you need to revert to v1.x:
```bash
# 1. Stop all services
# 2. Restore config backup
cp config.json.backup config.json

# 3. Checkout v1.x tag
git checkout v1.x  # or specific commit before Sprint 9

# 4. Start bot (old way)
python bot/rosey/rosey.py config.json
```

#### Compatibility

- ✅ **CyTube Protocol**: Unchanged, fully compatible
- ✅ **User Code**: Event handlers still work (if not using `bot.db` directly)
- ⚠️ **Database Access**: Must go through NATS, not `bot.db`
- ⚠️ **Configuration**: Auto-migration available, but format changed
- ❌ **Direct DB**: Removed `bot.db` attribute entirely

## Conventions

### Naming
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Private methods: `_leading_underscore`
- Constants: `UPPER_CASE`

### Async
- Prefix async functions with `async def`
- Always `await` coroutines
- Use `asyncio.create_task()` for background tasks

### Logging
- Use `self.logger` in Bot subclasses
- Log levels: DEBUG, INFO, WARNING, ERROR
- Include context in log messages

### Documentation
- Docstrings for public APIs
- Comments for complex logic
- README for usage instructions
