# Sprint 7: The Divide - Product Requirements Document

## Overview

**Sprint Name:** The Divide (2011)  
**Sprint Goal:** Refactor monolithic `lib/bot.py` into three focused, loosely-coupled modules with clear abstraction layers  
**Status:** Planning  
**Dependencies:** Sprint 6 (Make It Real) complete

## Executive Summary

The current `lib/bot.py` has grown to over 1,000 lines and handles three distinct responsibilities: core bot logic, database operations, and connection management. This violates the Single Responsibility Principle and creates tight coupling that makes the codebase difficult to maintain, test, and evolve.

Sprint 7 addresses this by surgically dividing `bot.py` into three specialized modules, each with well-defined interfaces and minimal coupling. Critically, these modules are designed with **platform independence** in mind - the bot should be able to swap CyTube for another platform, or SQLite for PostgreSQL, without rewriting core business logic.

## Context & Motivation

### Current Pain Points

1. **Tight Coupling:** Bot logic is intertwined with CyTube-specific socket.io code and SQLite operations
2. **Testing Difficulty:** Cannot test bot logic without mocking both database and network layers
3. **Single File Complexity:** 1,000+ lines make navigation, understanding, and modification challenging
4. **Platform Lock-in:** CyTube-specific code embedded throughout makes platform migration impossible
5. **Database Lock-in:** Direct SQLite calls prevent easy migration to PostgreSQL or other databases
6. **Maintenance Burden:** Changes to one concern (e.g., reconnection logic) risk breaking others (e.g., command handling)

### Strategic Vision

**Future-Proof Architecture:** The refactoring must anticipate:
- **Platform Portability:** Bot could target Discord, Twitch, Matrix, or other platforms
- **Database Scalability:** SQLite → PostgreSQL/MySQL migration path when scaling
- **Testing Isolation:** Each layer independently testable without network or database
- **Plugin Foundation:** Clean interfaces enable Sprint 8's plugin architecture

## Proposed Architecture

### Module Structure

```
lib/
├── bot.py              # Core bot logic (business logic layer)
├── connection.py       # Connection abstraction (transport layer)
└── storage.py          # Data storage abstraction (storage layer)
```

### Abstraction Layers

```
┌─────────────────────────────────────────┐
│         Bot (Business Logic)            │
│  - Command routing & execution          │
│  - Event orchestration                  │
│  - Feature coordination                 │
└────────────┬────────────────────────────┘
             │
             ├──────────────┬──────────────┐
             │              │              │
             ▼              ▼              ▼
    ┌────────────┐  ┌──────────────┐  ┌──────────┐
    │Connection  │  │   Storage    │  │ Channel  │
    │(Transport) │  │   (Data)     │  │  (State) │
    └────────────┘  └──────────────┘  └──────────┘
         │                │
         ▼                ▼
    ┌────────────┐  ┌──────────────┐
    │CyTubeConn  │  │SQLiteStorage │
    │(Concrete)  │  │  (Concrete)  │
    └────────────┘  └──────────────┘
```

## Module 1: `lib/bot.py` - Core Bot Logic

### Responsibilities

**What it DOES:**
- Command registration and routing
- Event handler registration and orchestration
- Message processing and response logic
- User permission checking
- Feature coordination (chat logging, command execution, etc.)
- High-level bot lifecycle (start, stop, restart logic)

**What it DOES NOT do:**
- Make direct socket.io calls
- Execute SQL queries
- Manage WebSocket connections
- Handle reconnection logic
- Serialize/deserialize protocol messages

### Interface Design

```python
class Bot:
    """Platform-agnostic bot orchestrator."""
    
    def __init__(self, 
                 connection: ConnectionAdapter,
                 storage: StorageAdapter = None,
                 config: BotConfig = None):
        """
        Initialize bot with dependency-injected adapters.
        
        Args:
            connection: Transport layer adapter (CyTube, Discord, etc.)
            storage: Storage layer adapter (SQLite, Postgres, etc.)
            config: Bot configuration (commands, behaviors, etc.)
        """
        self.connection = connection
        self.storage = storage
        self.config = config or BotConfig()
        self.handlers = {}
        self.commands = {}
        
    async def start(self):
        """Start bot and connect to platform."""
        await self.connection.connect()
        self._register_default_handlers()
        
    async def stop(self):
        """Gracefully shut down bot."""
        await self.connection.disconnect()
        if self.storage:
            await self.storage.close()
    
    def on(self, event: str, handler: Callable):
        """Register event handler (platform-agnostic)."""
        
    def command(self, name: str, **options):
        """Decorator for registering bot commands."""
        
    async def send_message(self, message: str, **metadata):
        """Send message to channel (platform-agnostic)."""
        await self.connection.send_message(message, **metadata)
```

### Key Design Principles

1. **No Direct I/O:** Bot never touches sockets or database connections directly
2. **Dependency Injection:** All external dependencies injected via constructor
3. **Interface-Oriented:** Code against `ConnectionAdapter` and `StorageAdapter` interfaces
4. **Pure Business Logic:** Focus on "what" not "how" (leave "how" to adapters)

## Module 2: `lib/connection.py` - Connection Abstraction

### Responsibilities

**What it DOES:**
- Define abstract `ConnectionAdapter` interface
- Provide `CyTubeConnection` implementation
- Handle platform-specific protocol details (socket.io, CyTube events)
- Manage WebSocket lifecycle (connect, disconnect, reconnect)
- Serialize/deserialize platform messages
- Emit normalized events to bot layer

**What it DOES NOT do:**
- Make business logic decisions
- Access database directly
- Process commands (that's bot.py's job)

### Interface Design

```python
class ConnectionAdapter(ABC):
    """Abstract interface for platform connections."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to platform."""
        
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection gracefully."""
        
    @abstractmethod
    async def send_message(self, message: str, **metadata) -> None:
        """Send message to channel/room/server."""
        
    @abstractmethod
    async def send_pm(self, user: str, message: str) -> None:
        """Send private message to user."""
        
    @abstractmethod
    def on_event(self, event: str, callback: Callable) -> None:
        """Register callback for platform event."""
        
    @abstractmethod
    async def recv_events(self) -> AsyncIterator[Tuple[str, dict]]:
        """Async iterator yielding (event_name, event_data) tuples."""
        
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""


class CyTubeConnection(ConnectionAdapter):
    """CyTube-specific connection implementation."""
    
    def __init__(self, 
                 domain: str,
                 channel: str,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 **socket_options):
        """Initialize CyTube connection with credentials."""
        self.domain = domain
        self.channel = channel
        self.user = user
        self.password = password
        self.socket = None
        self._reconnect_delay = 5
        self._response_timeout = 3
        
    async def connect(self) -> None:
        """Connect to CyTube channel via socket.io."""
        config = await self._fetch_socket_config()
        self.socket = await SocketIO.connect(config['server'])
        await self._login_to_channel()
        
    async def send_message(self, message: str, **metadata) -> None:
        """Send chat message to CyTube channel."""
        meta_obj = metadata.get('meta', {})
        await self.socket.emit('chatMsg', {
            'msg': message,
            'meta': meta_obj
        })
```

### Normalized Event Schema

The connection layer translates platform-specific events into normalized events:

```python
# CyTube "chatMsg" → Normalized "message"
{
    "event": "message",
    "user": "alice",
    "content": "Hello world",
    "timestamp": 1234567890,
    "metadata": {"rank": 2}  # Platform-specific extras
}

# CyTube "addUser" → Normalized "user_join"
{
    "event": "user_join",
    "user": "bob",
    "metadata": {"rank": 1, "afk": false}
}
```

### Reconnection Strategy

Connection layer owns all reconnection logic:
- Exponential backoff (5s, 10s, 20s, 40s, max 60s)
- Automatic reconnection on disconnect
- Connection health monitoring
- Timeout handling

## Module 3: `lib/storage.py` - Data Storage Abstraction

### Responsibilities

**What it DOES:**
- Define abstract `StorageAdapter` interface
- Provide `SQLiteStorage` implementation
- Abstract CRUD operations
- Handle schema migrations (via Alembic)
- Manage connection lifecycle
- Query result normalization

**What it DOES NOT do:**
- Make business logic decisions
- Communicate with external platforms
- Process events or commands

### Interface Design

```python
class StorageAdapter(ABC):
    """Abstract interface for data storage."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize database connection."""
        
    @abstractmethod
    async def close(self) -> None:
        """Close database connection."""
        
    @abstractmethod
    async def save_message(self, 
                          username: str,
                          message: str,
                          timestamp: int,
                          **metadata) -> None:
        """Store chat message."""
        
    @abstractmethod
    async def save_user_action(self,
                               username: str,
                               action_type: str,
                               details: dict = None) -> None:
        """Store user action (join, leave, etc.)."""
        
    @abstractmethod
    async def get_user_stats(self, username: str) -> dict:
        """Retrieve statistics for user."""
        
    @abstractmethod
    async def update_channel_stats(self, **stats) -> None:
        """Update channel-level statistics."""
        
    @abstractmethod
    async def get_recent_messages(self, limit: int = 100) -> List[dict]:
        """Retrieve recent chat messages."""


class SQLiteStorage(StorageAdapter):
    """SQLite implementation of storage layer."""
    
    def __init__(self, db_path: str = 'bot_data.db'):
        """Initialize SQLite storage."""
        self.db_path = db_path
        self.conn = None
        
    async def connect(self) -> None:
        """Connect to SQLite database."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self._run_migrations()
        
    async def save_message(self, 
                          username: str,
                          message: str,
                          timestamp: int,
                          **metadata) -> None:
        """Save chat message to recent_chat table."""
        await self.conn.execute(
            "INSERT INTO recent_chat (username, message, timestamp) VALUES (?, ?, ?)",
            (username, message, timestamp)
        )
        await self.conn.commit()
```

### Schema Migration Strategy

**Tool Selection: Alembic**

After evaluating options (South is deprecated, yoyo-migrations, custom solutions), **Alembic** is recommended:

**Why Alembic:**
- Industry standard for Python database migrations
- Developed by SQLAlchemy team (deep integration)
- Supports auto-generation from SQLAlchemy models
- Handles both upgrade and downgrade paths
- Works with SQLite, PostgreSQL, MySQL, and more
- Transactional DDL support
- Mature, well-documented, actively maintained

**Migration Structure:**
```
lib/
└── storage/
    ├── __init__.py
    ├── base.py           # StorageAdapter interface
    ├── sqlite.py         # SQLiteStorage implementation
    └── migrations/       # Alembic migrations directory
        ├── alembic.ini
        ├── env.py
        ├── script.py.mako
        └── versions/
            ├── 001_initial_schema.py
            ├── 002_add_user_stats.py
            └── ...
```

**Migration Workflow:**
```python
class SQLiteStorage(StorageAdapter):
    async def _run_migrations(self):
        """Run Alembic migrations on connect."""
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config("lib/storage/migrations/alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        
        # Upgrade to latest version
        command.upgrade(alembic_cfg, "head")
```

**Benefits:**
- Version-controlled schema changes
- Reversible migrations (upgrade/downgrade)
- Auto-generate migrations from model changes
- Team collaboration (merge migration branches)
- Production deployment safety (test migrations before applying)

### Future Database Support

The abstract interface enables future implementations:
- `PostgreSQLStorage` - Production-scale deployment
- `RedisStorage` - High-performance caching layer
- `NoOpStorage` - Testing without database

## Refactoring Strategy

### Phase 1: Extract Connection Layer (Week 1, Days 1-3)

**Goal:** Move all socket.io/CyTube protocol code to `lib/connection.py`

**Steps:**
1. Create `ConnectionAdapter` abstract base class
2. Create `CyTubeConnection` implementation
3. Move socket.io imports and dependencies
4. Move `get_socket_config()`, `connect()`, `login()` methods
5. Move WebSocket event loop and reconnection logic
6. Extract CyTube-specific event handlers (`_on_rank`, `_on_setMotd`, etc.)
7. Update tests to use `CyTubeConnection` directly

**Validation:**
- `CyTubeConnection` can connect/disconnect independently
- All CyTube events properly normalized
- Tests pass for connection layer

### Phase 2: Extract Storage Layer (Week 1, Days 4-5)

**Goal:** Move all database code to `lib/storage.py`

**Steps:**
1. Create `StorageAdapter` abstract base class
2. Create `SQLiteStorage` implementation
3. Move `common/database.py` code to new storage module
4. Integrate Alembic for schema migrations
5. Migrate all database operations from bot.py
6. Add async wrapper for SQLite (use `aiosqlite`)
7. Update tests to use storage adapter

**Validation:**
- Database operations work through adapter
- Alembic migrations execute on startup
- Bot can run with `NoOpStorage` for testing
- Migration path documented

### Phase 3: Refactor Bot Core (Week 2, Days 1-3)

**Goal:** Reduce `bot.py` to pure business logic

**Steps:**
1. Inject connection and storage as dependencies
2. Remove all direct socket.io calls → use `self.connection.send_message()`
3. Remove all direct database calls → use `self.storage.save_message()`
4. Simplify event handlers to pure logic
5. Extract command routing to separate module (if needed)
6. Update `rosey.py` and other bots to use new architecture

**Validation:**
- Bot logic testable without network/database
- Existing bots work with new architecture
- All 600+ tests pass

### Phase 4: Documentation & Testing (Week 2, Days 4-5)

**Goal:** Comprehensive documentation and test coverage

**Steps:**
1. Write architecture documentation
2. Create adapter implementation guide
3. Update existing tests for new structure
4. Add integration tests for full stack
5. Performance testing (ensure no regression)
6. Update deployment documentation

## Migration Guide for Existing Bots

### Before (Current):

```python
from lib import Bot

bot = Bot('cytube.example.com', 
          channel='mychannel',
          user=('botname', 'password'))

@bot.on('chatMsg')
def handle_chat(event, data):
    # Process chat
    pass

bot.run()
```

### After (Sprint 7):

```python
from lib import Bot
from lib.connection import CyTubeConnection
from lib.storage import SQLiteStorage

connection = CyTubeConnection('cytube.example.com',
                               channel='mychannel',
                               user='botname',
                               password='password')

storage = SQLiteStorage('bot_data.db')

bot = Bot(connection=connection,
          storage=storage)

@bot.on('message')  # Normalized event name
def handle_chat(event, data):
    # Process chat (same logic)
    pass

await bot.start()
```

**Migration Complexity:** LOW
- Constructor signature changes
- Event names normalized (documented mapping)
- Core logic unchanged

## Testing Strategy

### Unit Tests

**Connection Layer:**
- Test `CyTubeConnection` with mocked socket.io
- Test reconnection logic
- Test event normalization
- Test error handling

**Storage Layer:**
- Test CRUD operations with in-memory SQLite
- Test Alembic migrations (upgrade/downgrade)
- Test concurrent access
- Test error handling

**Bot Layer:**
- Test with mock connection and storage
- Test command routing
- Test event handler registration
- Test permission checks

### Integration Tests

**Full Stack:**
- Test bot + CyTube connection + SQLite storage
- Test reconnection scenarios
- Test database persistence across restarts
- Test Alembic migration application
- Test multi-bot scenarios

### Performance Tests

- **Baseline:** Measure current bot.py performance
- **Target:** No regression > 5% in message throughput
- **Metrics:** Messages/second, memory usage, reconnect time

## Success Criteria

### Functional Requirements

- ✅ All existing bot functionality preserved
- ✅ All 600+ tests pass
- ✅ No breaking changes to bot implementations
- ✅ Rosey bot works with new architecture
- ✅ Connection can be swapped (demonstrate with mock)
- ✅ Storage can be swapped (demonstrate with NoOp)
- ✅ Alembic migrations work (create, apply, rollback)

### Code Quality Requirements

- ✅ `bot.py` < 400 lines (from 1,000+)
- ✅ No direct socket.io imports in `bot.py`
- ✅ No direct database imports in `bot.py`
- ✅ 100% of tests updated for new architecture
- ✅ Code coverage ≥ current levels (no regression)

### Documentation Requirements

- ✅ Architecture decision record (ADR) for refactoring
- ✅ Connection adapter implementation guide
- ✅ Storage adapter implementation guide
- ✅ Alembic migration guide
- ✅ Migration guide for bot developers
- ✅ API documentation for all three modules

## Risks & Mitigation

### Risk: Breaking Changes

**Probability:** Medium  
**Impact:** High  
**Mitigation:**
- Maintain backward compatibility layer (deprecate old API)
- Comprehensive testing before merging
- Staged rollout (feature branch → test → prod)
- Detailed migration guide

### Risk: Performance Regression

**Probability:** Low  
**Impact:** Medium  
**Mitigation:**
- Benchmark current performance
- Profile new architecture
- Optimize hot paths (message sending, event handling)
- Accept 5% degradation, reject >10%

### Risk: Over-Abstraction

**Probability:** Medium  
**Impact:** Low  
**Mitigation:**
- YAGNI principle: Abstract only what's needed for CyTube + one alternative
- Validate abstractions with prototype Discord/Matrix adapter
- Prefer concrete implementations over premature generalization

## Timeline Estimate

**Optimistic:** 5 days (1 week)
- Assumes clean separation, no surprises

**Realistic:** 7-10 days (1.5-2 weeks)
- Assumes some refactoring challenges
- Accounts for test updates

**Pessimistic:** 12-14 days (2.5-3 weeks)
- Accounts for major restructuring
- Includes extensive testing and debugging

## Dependencies & Blockers

### Dependencies

- **Sprint 6 Complete:** Production deployment stable
- **Test Suite:** 600+ tests provide safety net
- **No Active Development:** Refactoring best done when feature work paused

### Blockers

- **None identified:** All prerequisites met

## Acceptance Criteria Summary

**Sprint 7 is COMPLETE when:**

1. ✅ Three modules exist: `bot.py` (< 400 lines), `connection.py`, `storage.py`
2. ✅ Abstract interfaces defined: `ConnectionAdapter`, `StorageAdapter`
3. ✅ Concrete implementations work: `CyTubeConnection`, `SQLiteStorage`
4. ✅ Alembic integration complete (migrations directory, initial schema)
5. ✅ All existing functionality preserved (feature parity)
6. ✅ All 600+ tests pass with updated architecture
7. ✅ Rosey bot migrated and working
8. ✅ Connection swap demonstrated (mock or alternative platform)
9. ✅ Storage swap demonstrated (`NoOpStorage`)
10. ✅ Documentation complete (architecture, migration, Alembic, API)
11. ✅ Code review approved by maintainers
12. ✅ Performance within 5% of baseline
13. ✅ Branch merged to main

---

**Document Status:** Complete  
**Last Updated:** November 12, 2025  
**Next Steps:** Review PRD, create sortie specifications, begin Phase 1
