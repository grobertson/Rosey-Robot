# Architecture Overview

## Design Philosophy

Rosey uses an **event-driven microservices architecture** built on NATS messaging, enabling:

1. **Plugin Isolation**: Plugins run in separate processes with resource limits
2. **Security**: Sandboxed execution prevents malicious code from affecting core systems
3. **Scalability**: Horizontal scaling across multiple bot instances
4. **Flexibility**: Hot-reload plugins without restarting the bot
5. **Multi-Platform**: Support Discord, Slack, IRC, and other platforms through unified event layer
6. **Development Speed**: All code in single repository, no package installation needed

## Layer Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Platform Connectors                          │
│  • CyTube Connector (WebSocket)                                 │
│  • Discord Connector (future)                                   │
│  • Slack Connector (future)                                     │
│  Translates platform-specific events to/from NATS               │
└─────────────────────────────────────────────────────────────────┘
                              ↕ NATS Subjects
┌─────────────────────────────────────────────────────────────────┐
│                      NATS Event Bus                             │
│  • Subject-based pub/sub routing                                │
│  • Request-reply for synchronous operations                     │
│  • Wildcard subscriptions (* and >)                             │
│  • Message persistence and replay                               │
│  Central nervous system for all communication                   │
└─────────────────────────────────────────────────────────────────┘
                              ↕ NATS Subjects
┌─────────────────────────────────────────────────────────────────┐
│                       Core Services                             │
│  • Router (command routing & dispatch)                          │
│  • Plugin Manager (lifecycle, health, resources)                │
│  • Permission System (capability-based security)                │
│  • Plugin Isolation (sandboxed execution)                       │
│  Orchestrates plugins, enforces security, manages state         │
└─────────────────────────────────────────────────────────────────┘
                              ↕ NATS Subjects
┌─────────────────────────────────────────────────────────────────┐
│                          Plugins                                │
│  • Echo Plugin (isolated process)                               │
│  • Trivia Plugin (isolated process)                             │
│  • Markov Plugin (isolated process)                             │
│  • Custom Plugins (isolated processes)                          │
│  Each runs in separate process with resource limits             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### NATS Event Bus (`bot/rosey/core/event_bus.py`)

**Purpose**: Central message bus for all inter-component communication

**Key Capabilities**:
- **Publish/Subscribe**: Components publish events, subscribers receive them
- **Request/Reply**: Synchronous request-response patterns
- **Wildcards**: Subscribe to multiple subjects with `*` (one token) and `>` (multiple tokens)
- **Subject Hierarchy**: Organized routing with `rosey.category.specifics...`
- **Automatic Reconnection**: Exponential backoff, health monitoring
- **Event Serialization**: JSON-based with correlation IDs and timestamps

**Subject Structure** (`bot/rosey/core/subjects.py`):

```text
rosey.platform.cytube.message       # CyTube chat message
rosey.platform.cytube.user.join     # User joined channel
rosey.events.message                # Normalized message (any platform)
rosey.commands.trivia.execute       # Execute trivia command
rosey.plugins.markov.ready          # Markov plugin ready
rosey.security.violation            # Security violation detected
rosey.monitoring.health             # Health check request
```

**Why NATS?**
1. **Decoupling**: Components don't need to know about each other
2. **Isolation**: Plugins in separate processes can't crash the core
3. **Scalability**: Multiple bot instances can share workload
4. **Security**: Process boundaries prevent code injection
5. **Flexibility**: Hot-reload, dynamic plugin loading
6. **Observability**: All communication is visible and loggable

### Platform Connectors

#### CyTube Connector (`bot/rosey/core/cytube_connector.py`)

**Purpose**: Bridges CyTube WebSocket protocol to NATS event bus

**Responsibilities**:
- Connect to CyTube via WebSocket
- Translate CyTube events → NATS subjects (`rosey.platform.cytube.*`)
- Subscribe to NATS subjects → Send CyTube actions
- Maintain connection state and handle reconnections
- Normalize CyTube-specific data structures

**Event Flow**:

```text
CyTube WebSocket → Connector → NATS → Plugins
                              ↕
Plugins → NATS → Connector → CyTube WebSocket
```

#### Future Connectors

**Discord** (`rosey.platform.discord.*`):
- Discord Gateway events → NATS
- NATS commands → Discord API calls

**Slack** (`rosey.platform.slack.*`):
- Slack RTM events → NATS
- NATS commands → Slack Web API

**IRC** (`rosey.platform.irc.*`):
- IRC protocol → NATS
- NATS commands → IRC commands

All connectors publish to unified `rosey.events.*` subjects for platform-agnostic plugins.

### Core Router (`bot/rosey/core/router.py`)

**Purpose**: Command routing and dispatch system

**Key Features**:
- **Priority Routing**: exact match → prefix match → pattern match → default handler
- **Plugin Discovery**: Automatically discovers plugin capabilities
- **Cooldowns**: Per-command, per-user rate limiting
- **Context Enrichment**: Adds user info, channel state, permissions
- **Command Parsing**: Extracts command, arguments from messages

**Routing Example**:

```text
User: "!trivia start"
  ↓
Router checks:
  1. Exact: "trivia start" → no match
  2. Prefix: "trivia" → matches Trivia Plugin
  3. Dispatch to plugin via NATS: rosey.commands.trivia.execute
  ↓
Trivia Plugin receives command, starts game
```

### Plugin Manager (`bot/rosey/core/plugin_manager.py`)

**Purpose**: Plugin lifecycle management and orchestration

**Responsibilities**:
- **Loading**: Load plugins from YAML specifications
- **Lifecycle**: Start, stop, restart, hot-reload plugins
- **Health Monitoring**: Track plugin health, auto-restart on crash
- **Resource Management**: Enforce CPU/memory limits per plugin
- **Graceful Shutdown**: Coordinate shutdown across all plugins

**Plugin Registry**:

```python
{
  "echo": {
    "metadata": PluginMetadata(...),
    "process": subprocess.Popen(...),
    "health": "running",
    "uptime": 3600,
    "restart_count": 0
  },
  "trivia": {...}
}
```

### Plugin Isolation (`bot/rosey/core/plugin_isolation.py`)

**Purpose**: Sandboxed execution environment for untrusted plugins

**Security Features**:
- **Process Isolation**: Each plugin runs in separate process
- **Resource Limits**: CPU time, memory, file descriptors
- **IPC via NATS**: No direct memory access between plugins
- **Crash Recovery**: Plugin crashes don't affect core or other plugins
- **Permission Enforcement**: Capability-based security model

**Why Process Isolation?**

| Threat | Mitigation |
|--------|-----------|
| Infinite loops | CPU time limits |
| Memory leaks | Memory limits |
| Code injection | Separate process space |
| Filesystem access | Restricted via permissions |
| Network abuse | Rate limiting via permissions |
| Core crashes | Process boundary protection |

### Plugin Permissions (`bot/rosey/core/plugin_permissions.py`)

**Purpose**: Fine-grained capability-based permission system

**Permission Model**:

```python
{
  "chat.send": True,           # Can send chat messages
  "chat.delete": False,        # Cannot delete messages
  "users.list": True,          # Can list users
  "users.kick": False,         # Cannot kick users
  "playlist.queue": True,      # Can queue videos
  "playlist.delete": False,    # Cannot delete videos
  "api.external": False,       # Cannot make external API calls
  "filesystem.read": False     # Cannot read files
}
```

**Default Policy**: Deny all, explicitly grant permissions

**Permission Groups**:
- `basic`: chat.send, users.list (safe for untrusted plugins)
- `moderator`: + chat.delete, users.kick (requires trust)
- `admin`: + playlist.*, config.* (high trust only)

### Legacy Bot Class (`lib/bot.py`)

**Purpose**: Original monolithic bot implementation (being phased out)

**Current Status**: Still used for direct CyTube connection, will be replaced by CyTube Connector

**Key Components**:
- `bot.py` - Main Bot class with CyTube WebSocket connection
- `channel.py` - Channel state (users, playlist, permissions)
- `playlist.py` - Playlist management
- `user.py` - User representation
- `socket_io.py` - WebSocket connection management

**Migration Path**: CyTube Connector wraps lib/bot.py and bridges to NATS

### Common Utilities (`common/`)

**Purpose**: Shared utilities for bot development

**Key Files**:
- `config.py` - JSON/YAML config loading, logging setup, database URL resolution
- `database.py` - Async ORM with dual-database support (SQLite/PostgreSQL)
- `shell.py` - PM command handler (moderator commands via private messages)

**Note**: TCP/telnet REPL server has been removed. Shell.py now only handles PM commands.

### Database Layer (`common/database.py`)

**Purpose**: Unified async database interface with dual-database support

**Supported Databases**:
- **SQLite** (development/testing): Zero-config, file-based, fast for single-user
- **PostgreSQL** (staging/production): ACID guarantees, concurrent writes, replication

**Key Features**:
- **Async ORM**: SQLAlchemy 2.0+ with asyncio support
- **Environment-Aware Pooling**: Auto-scales connections (dev: 2+5, staging: 5+10, production: 10+20)
- **12-Factor Config**: DATABASE_URL environment variable with fallback priority
- **Schema Migrations**: Alembic for version-controlled schema changes
- **Transparent Switching**: Same code works with both databases

**Connection String Priority**:
1. Environment variable: `DATABASE_URL`
2. Config file: `database_url` field
3. Config file (legacy): `database` field (converted to SQLite URL)
4. Default: `sqlite+aiosqlite:///bot_data.db`

**Examples**:
```bash
# SQLite (development)
DATABASE_URL=sqlite+aiosqlite:///bot_data.db

# PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://rosey:password@localhost/rosey_production
```

See [DATABASE_SETUP.md](DATABASE_SETUP.md) for complete PostgreSQL setup guide and [MIGRATIONS.md](MIGRATIONS.md) for Alembic migration workflow.

### Schema Migrations

**Purpose**: Plugin-specific database schema version control and management

**Added**: Sprint 15 - Schema Migrations

#### Overview

Rosey now supports per-plugin schema migrations, enabling plugins to:
- Create and modify their own database tables
- Version-control schema changes with sequential migration files
- Apply migrations via NATS commands (no manual SQL execution)
- Roll back migrations safely if issues occur
- Validate SQL before execution (prevent destructive operations)

**Why Plugin Migrations?**
- **Independence**: Each plugin manages its own schema
- **Safety**: Validation prevents accidental data loss
- **Versioning**: Track schema changes over time
- **Automation**: No manual database access needed
- **Rollback**: Undo schema changes when needed
- **Multi-Database**: Works with SQLite and PostgreSQL

#### Components

**Migration Manager** (`common/migrations/migration_manager.py`):
- Discovers migration files in plugin directories
- Tracks applied migrations in database
- Provides status information (pending, applied, failed)
- Coordinates with executor and validator

**Migration Executor** (`common/migrations/migration_executor.py`):
- Executes UP and DOWN SQL statements
- Runs migrations in transactions (atomic)
- Handles dry-run mode (validation without execution)
- Computes and stores checksums for tamper detection
- Records migration history with timestamps and user

**Migration Validator** (`common/migrations/migration_validator.py`):
- Validates SQL syntax before execution
- Detects SQLite limitations (DROP COLUMN, ALTER COLUMN, ADD CONSTRAINT)
- Checks for destructive operations (DROP TABLE, DELETE)
- Provides validation reports with INFO/WARNING/ERROR levels
- Prevents execution if ERROR-level issues found

**Database Service Handlers** (`common/database_service.py`):
- NATS request handlers for migration operations
- Subjects:
  - `rosey.db.migrate.<plugin>.apply` - Apply migrations (all or to version)
  - `rosey.db.migrate.<plugin>.rollback` - Rollback migrations (single or to version)
  - `rosey.db.migrate.<plugin>.status` - Get migration status
- Integration with Migration Manager, Executor, and Validator

#### Data Flow

```text
Plugin Developer
  ↓ (creates migration file)
plugins/<plugin>/migrations/001_create_table.sql
  ↓
NATS Request: rosey.db.migrate.<plugin>.apply
  ↓
DatabaseService Handler
  ↓
Migration Manager (discover migrations)
  ↓
Migration Validator (validate SQL)
  ↓ (if valid)
Migration Executor (execute in transaction)
  ↓
Database (SQLite or PostgreSQL)
  ↓
NATS Response: {success: true, migrations_applied: 3}
```

#### Migration File Format

**Location**: `plugins/<plugin-name>/migrations/NNN_description.sql`

**Naming Convention**: `{version:03d}_{description}.sql`
- `001_create_quotes_table.sql`
- `002_add_category_column.sql`
- `010_drop_deprecated_table.sql`

**Structure**:

```sql
-- UP
-- SQL statements to apply the migration
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    author TEXT
);

CREATE INDEX IF NOT EXISTS idx_quotes_author ON quotes(author);

-- DOWN
-- SQL statements to reverse the migration
DROP INDEX IF EXISTS idx_quotes_author;
DROP TABLE IF EXISTS quotes;
```

**Rules**:
- File must contain `-- UP` and `-- DOWN` sections
- UP SQL executed when applying migration
- DOWN SQL executed when rolling back
- Each section can contain multiple SQL statements
- Empty lines and comments allowed
- Use `IF NOT EXISTS` / `IF EXISTS` for idempotency

#### Migration States

Migrations tracked in `plugin_schema_migrations` table:

| State | Description |
|-------|-------------|
| `pending` | Migration file exists, not yet applied |
| `applied` | Migration successfully applied to database |
| `rolled_back` | Migration was applied then rolled back |
| `failed` | Migration execution failed (transaction rolled back) |

**Database Schema**:

```sql
CREATE TABLE plugin_schema_migrations (
    id INTEGER PRIMARY KEY,
    plugin_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT NOT NULL,
    checksum TEXT NOT NULL,  -- SHA-256 of file contents
    applied_at TIMESTAMP,
    applied_by TEXT,
    rolled_back_at TIMESTAMP,
    rolled_back_by TEXT,
    status TEXT NOT NULL,  -- 'applied', 'rolled_back', 'failed'
    UNIQUE (plugin_name, version)
);
```

#### Applying Migrations

**Via NATS** (recommended):

```python
import nats
import json

nc = await nats.connect("nats://localhost:4222")

# Apply all pending migrations
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({}).encode(),
    timeout=30.0
)

result = json.loads(response.data)
# {
#   "success": true,
#   "migrations_applied": 3,
#   "final_version": 3,
#   "warnings": ["Migration 002 drops column (data loss)"]
# }
```

**Options**:
- `{"to_version": 2}` - Apply up to version 2 only
- `{"dry_run": true}` - Validate without executing
- `{}` - Apply all pending migrations

#### Rolling Back Migrations

**Via NATS**:

```python
# Rollback single migration (latest)
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"count": 1}).encode(),
    timeout=30.0
)

# Rollback to specific version
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"to_version": 1}).encode(),
    timeout=30.0
)

# Dry-run rollback
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"count": 1, "dry_run": true}).encode(),
    timeout=30.0
)
```

**Rollback Safety**:
- Rollbacks execute in reverse order (newest first)
- Each rollback runs in transaction (atomic)
- Dry-run validates before executing
- Destructive operations warned in validation

#### Checking Migration Status

```python
response = await nc.request(
    "rosey.db.migrate.quote-db.status",
    json.dumps({}).encode(),
    timeout=5.0
)

result = json.loads(response.data)
# {
#   "success": true,
#   "current_version": 3,
#   "available_version": 5,
#   "pending_migrations": [
#     {"version": 4, "description": "add indexes"},
#     {"version": 5, "description": "add foreign keys"}
#   ],
#   "applied_migrations": [
#     {"version": 1, "applied_at": "2025-11-24T10:00:00Z", ...},
#     {"version": 2, "applied_at": "2025-11-24T10:01:00Z", ...},
#     {"version": 3, "applied_at": "2025-11-24T10:02:00Z", ...}
#   ]
# }
```

#### Validation System

**Automatic Validation**:
- All migrations validated before execution
- Validation runs even in non-dry-run mode
- Execution blocked if ERROR-level issues found

**Validation Levels**:
- **INFO**: Informational notes (e.g., "CREATE TABLE uses IF NOT EXISTS")
- **WARNING**: Potential issues (e.g., "DROP TABLE will lose data")
- **ERROR**: Blocking issues (e.g., "SQLite does not support DROP COLUMN")

**Common Validations**:

| Check | Level | Example |
|-------|-------|---------|
| SQLite DROP COLUMN | ERROR | `ALTER TABLE DROP COLUMN` not supported |
| SQLite ALTER COLUMN | ERROR | `ALTER TABLE ALTER COLUMN` not supported |
| SQLite ADD CONSTRAINT | ERROR | `ALTER TABLE ADD CONSTRAINT` not supported |
| DROP TABLE | WARNING | Data will be permanently deleted |
| DELETE without WHERE | WARNING | Deletes all rows |
| Syntax errors | ERROR | Unmatched parentheses, unknown keywords |

**Workaround for SQLite Limitations**:

Use table recreation pattern (see [Migration Best Practices](guides/MIGRATION_BEST_PRACTICES.md)):

```sql
-- UP (drop column workaround)
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    kept_col TEXT
    -- Omit dropped_col
);

INSERT INTO table_new SELECT id, kept_col FROM table;
DROP TABLE table;
ALTER TABLE table_new RENAME TO table;
```

#### Security Features

**Checksum Verification**:
- SHA-256 checksum computed for each migration file
- Stored in database when migration applied
- Verified on every status check
- Detects tampering or accidental modification
- Blocks execution if checksum mismatch

**Transaction Safety**:
- All migrations execute in transactions
- If any statement fails, entire migration rolls back
- Database left in consistent state
- No partial migrations

**User Tracking**:
- Records who applied/rolled back each migration
- `applied_by` and `rolled_back_by` fields
- Audit trail for schema changes

**Dry-Run Mode**:
- Validates SQL without executing
- Tests migrations safely before production
- Returns validation report
- No database changes

#### Error Handling

**Common Errors**:

| Error Code | Cause | Solution |
|------------|-------|----------|
| `LOCK_TIMEOUT` | Another migration in progress | Wait and retry |
| `VALIDATION_FAILED` | SQL validation errors | Fix SQL syntax or workaround |
| `MIGRATION_FAILED` | SQL execution error | Check logs, fix SQL, retry |
| `CHECKSUM_MISMATCH` | File modified after apply | Never modify applied migrations |

**Recovery**:
- Failed migrations automatically roll back transaction
- Database remains in consistent state
- Fix migration file, re-apply
- If data corrupted, restore from backup

#### Integration with Plugins

**Plugin Directory Structure**:

```text
plugins/quote-db/
├── __init__.py
├── plugin.py
└── migrations/
    ├── 001_create_quotes_table.sql
    ├── 002_add_category_column.sql
    └── 003_add_indexes.sql
```

**Plugin Initialization**:

```python
# In plugin startup
async def initialize_schema():
    """Apply any pending migrations."""
    nc = await nats.connect("nats://localhost:4222")
    
    # Check status
    response = await nc.request(
        "rosey.db.migrate.quote-db.status",
        json.dumps({}).encode()
    )
    status = json.loads(response.data)
    
    # Apply if pending
    if status['pending_migrations']:
        response = await nc.request(
            "rosey.db.migrate.quote-db.apply",
            json.dumps({}).encode()
        )
        result = json.loads(response.data)
        if not result['success']:
            raise RuntimeError(f"Migration failed: {result['error']}")
```

#### Best Practices

1. **Never modify applied migrations** - Create new migration instead
2. **Write idempotent SQL** - Use `IF NOT EXISTS`, `IF EXISTS`
3. **Test on staging first** - Always test migrations before production
4. **Backup before destructive operations** - DROP TABLE, DELETE, etc.
5. **Keep migrations small** - One logical change per file
6. **Write reversible DOWN SQL** - Enable safe rollback
7. **Handle SQLite limitations** - Use table recreation pattern
8. **Use dry-run mode** - Validate before executing
9. **Document intent** - Explain why changes are being made
10. **Version incrementally** - Don't skip version numbers

#### Documentation

- **[Plugin Migration Guide](guides/PLUGIN_MIGRATIONS.md)** - Complete guide for plugin developers
- **[Migration Best Practices](guides/MIGRATION_BEST_PRACTICES.md)** - Detailed best practices and patterns
- **[Migration Examples](../examples/migrations/)** - 10 example migration files covering common patterns
- **[NATS Messages](NATS_MESSAGES.md)** - Message format reference for migration handlers

## Event Flow

### Message Flow Example

```text
1. User sends chat message in CyTube
   ↓
2. CyTube WebSocket → CyTube Connector
   Receives: {"msg": "!trivia start", "username": "alice", ...}
   ↓
3. Connector publishes to NATS
   Subject: rosey.platform.cytube.message
   Event: {event_type: "message", data: {...}}
   ↓
4. Router subscribes to rosey.platform.cytube.message
   Detects command: "trivia"
   ↓
5. Router publishes to NATS
   Subject: rosey.commands.trivia.execute
   Event: {command: "start", user: "alice", ...}
   ↓
6. Trivia Plugin (isolated process) subscribes to rosey.commands.trivia.*
   Receives command, processes logic
   ↓
7. Trivia Plugin publishes response to NATS
   Subject: rosey.platform.cytube.send_message
   Event: {text: "Trivia started! Question 1...", ...}
   ↓
8. CyTube Connector subscribes to rosey.platform.cytube.send_message
   Sends message via WebSocket to CyTube
   ↓
9. Message appears in CyTube channel
```

### Subject Patterns

**Wildcards**:
- `*` matches exactly one token: `rosey.commands.*.execute`
- `>` matches zero or more tokens: `rosey.platform.cytube.>`

**Common Patterns**:

```python
# Subscribe to all platform messages
nats.subscribe("rosey.platform.>", handler)

# Subscribe to all trivia commands
nats.subscribe("rosey.commands.trivia.*", handler)

# Subscribe to all security events
nats.subscribe("rosey.security.>", handler)

# Subscribe to specific event
nats.subscribe("rosey.platform.cytube.message", handler)
```

## State Management

### Distributed State

Unlike the monolithic architecture, state is now distributed:

**CyTube Connector State**:
- Channel name, MOTD, CSS, JavaScript
- Current userlist
- Current playlist
- Connection status

**Plugin State**:
- Each plugin maintains its own state
- State persisted via database or files
- No shared memory between plugins

**State Synchronization**:
- NATS subjects used to broadcast state changes
- Plugins subscribe to state they care about
- Event sourcing pattern for state reconstruction

### State Access Example

```python
# Plugin wants to know current users
# Subscribe to user join/leave events
await nats.subscribe("rosey.platform.cytube.user.join", on_user_join)
await nats.subscribe("rosey.platform.cytube.user.leave", on_user_leave)

# Or request current state via request-reply
response = await nats.request(
    "rosey.api.users.list",
    timeout=5.0
)
users = json.loads(response.data)
```

## Async Design

All components use asynchronous I/O with `asyncio`:

- **NATS Communication**: All pub/sub is async
- **Plugin IPC**: Async message passing via NATS
- **CyTube WebSocket**: Async connection management
- **Event Handlers**: Can be sync or async

### Concurrency Model

```python
# Core runs main event loop
loop = asyncio.get_event_loop()

# Each plugin runs in separate process with own event loop
# Plugins communicate via NATS, not shared memory

# Multiple bot instances can run simultaneously
# Load balanced via NATS queue groups
```

## Error Handling

### Plugin Failures

**Crash Isolation**:
- Plugin crash does NOT crash core or other plugins
- Plugin Manager detects crashes via health checks
- Automatic restart with exponential backoff
- Configurable max restart attempts

**Error Propagation**:

```text
Plugin Exception
  ↓
Plugin process exits with error code
  ↓
Plugin Manager detects via process monitoring
  ↓
Log error, update plugin state to "crashed"
  ↓
Attempt restart (with backoff and max attempts)
  ↓
If restart succeeds: Plugin state → "running"
If restart fails: Plugin state → "failed", alert admins
```

### Communication Failures

**NATS Connection Loss**:
- Automatic reconnection with exponential backoff
- Buffered messages replayed on reconnection
- Dead letter queue for failed messages
- Health monitoring detects connectivity issues

**Platform Connection Loss** (e.g., CyTube WebSocket):
- CyTube Connector handles reconnection
- State resynchronization on reconnect
- Queued messages sent after reconnect

## Security Model

### Defense in Depth

1. **Process Isolation**: Plugins can't access core memory
2. **Permission System**: Capability-based, default deny
3. **Resource Limits**: CPU, memory, file descriptors
4. **NATS Security**: Subject-level permissions (future)
5. **Input Validation**: All external input sanitized
6. **Audit Logging**: Security events logged to `rosey.security.*`

### Threat Mitigation

| Threat | Mitigation Strategy |
|--------|---------------------|
| Malicious plugin code | Process isolation + permissions |
| Resource exhaustion | Per-plugin CPU/memory limits |
| Privilege escalation | Capability-based permissions |
| Code injection | No eval(), subprocess restrictions |
| Data exfiltration | Network permission required |
| Core compromise | Process boundaries, no shared memory |

### Permission Enforcement Flow

```text
Plugin wants to delete message
  ↓
Plugin publishes: rosey.platform.cytube.delete_message
  ↓
Router intercepts, checks plugin permissions
  ↓
If "chat.delete" permission granted:
  Forward to CyTube Connector
Else:
  Reject, publish to rosey.security.violation
  ↓
Security violation logged, plugin may be suspended
```

## Future Architecture Plans

### Additional Platform Connectors

**Planned**:
- Discord connector (Discord Gateway API)
- Slack connector (Slack RTM API)
- IRC connector (IRC protocol)
- Twitch connector (Twitch IRC + API)

**Design**:
- Each connector is independent module
- Publishes to unified `rosey.events.*` subjects
- Platform-specific subjects under `rosey.platform.{name}.*`
- Plugins remain platform-agnostic

### Enhanced Plugin System

**Plugin Marketplace**:
- Centralized registry of community plugins
- Version management and dependencies
- Security scanning and code review
- Rating and review system

**Plugin Development Kit**:
- Templates for common plugin types
- Testing framework with MockNATSClient
- Local development environment
- Plugin generator CLI tool

### Horizontal Scaling

**Queue Groups**:

```python
# Multiple bot instances share workload
# NATS queue groups distribute messages

# Bot instance 1
await nats.subscribe("rosey.commands.>", handler, queue="workers")

# Bot instance 2
await nats.subscribe("rosey.commands.>", handler, queue="workers")

# Commands automatically load-balanced across instances
```

**Stateless Design**:
- Shared state via Redis or database
- Session affinity for multi-message interactions
- Leader election for singleton tasks

### Observability

**Metrics** (`rosey.monitoring.*`):
- Message throughput, latency
- Plugin health, restart counts
- Resource usage per plugin
- Error rates by component

**Tracing**:
- Distributed tracing with correlation IDs
- Trace message flow across components
- Performance profiling

**Dashboards**:
- Grafana dashboards for real-time monitoring
- Alert rules for critical events
- Historical analysis and trends

## Making Changes to Rosey

### Core Library Changes (lib/)

- **Location**: `lib/bot.py`, `lib/channel.py`, `lib/user.py`, etc.
- **Purpose**: CyTube protocol implementation (legacy monolithic code)
- **Impact**: Affects all bots using the library
- **Testing**: Run unit tests, test with multiple bots
- **Note**: Being phased out in favor of NATS-based platform connectors

### Bot Core Changes (bot/rosey/core/)

- **Location**: `bot/rosey/core/event_bus.py`, `router.py`, `plugin_manager.py`, etc.
- **Purpose**: NATS-based core services (Sprint 6a architecture)
- **Impact**: Affects all plugins and platform connectors
- **Testing**: Comprehensive unit tests (3,000+ tests), integration tests with NATS
- **Deployment**: Restart bot to apply changes

### Plugin Changes (bot/rosey/plugins/)

- **Location**: `bot/rosey/plugins/*.py`
- **Purpose**: Individual feature implementations (isolated processes)
- **Impact**: Only affects specific plugin
- **Testing**: Unit tests with MockNATSClient, integration tests
- **Deployment**: Hot-reload supported (no bot restart needed)

### Common Utilities (common/)

- **Location**: `common/config.py`, `common/database.py`, `common/shell.py`
- **Purpose**: Shared utilities across components
- **Impact**: Affects all users of the utility
- **Testing**: Unit tests, integration tests
- **Deployment**: Restart affected components

### Testing Strategy

1. **Unit Tests**: Test individual components in isolation
   - Use `pytest` framework
   - Mock external dependencies (NATS, database, etc.)
   - Target 85%+ coverage (66% minimum)

2. **Integration Tests**: Test component interactions
   - Real NATS server (Docker: `docker run -p 4222:4222 nats:latest`)
   - Database fixtures
   - Multi-component workflows

3. **Manual Tests**: Run bot against test channel
   - Verify end-to-end functionality
   - Test edge cases and error handling
   - Performance and load testing

4. **See**: `TESTING.md` for comprehensive testing guide

### Debugging Tips

1. **Enable DEBUG logging**: Set `"log_level": "DEBUG"` in config
2. **Review Logs**: Check bot logs and NATS logs for errors
3. **Use Monitoring**: Grafana dashboards show component health
4. **Add Trace Logging**: Use correlation IDs to trace message flow
5. **Exception Traces**: Full stack traces in logs with context

## Performance Considerations

### Bottlenecks

- **NATS Network I/O**: Message serialization and network latency
- **Plugin Process Spawning**: Initial startup cost for sandboxed plugins
- **CyTube WebSocket**: Network-bound I/O with server
- **Database Queries**: Synchronous database operations (quotes, media CMS)

### Optimizations

- **Async I/O**: Non-blocking operations throughout stack
- **Connection Pooling**: Reuse NATS connections across components
- **Message Batching**: Batch multiple events when possible
- **Lazy Plugin Loading**: Only start plugins when needed
- **Caching**: Cache frequently accessed data (permissions, user ranks)
- **Process Pools**: Reuse plugin processes instead of spawning new ones

### Scaling

- **Horizontal Scaling**: Run multiple bot instances with NATS queue groups
- **Vertical Scaling**: Increase plugin process limits (CPU/memory)
- **Distributed State**: Use Redis or database for shared state across instances
- **Load Balancing**: NATS queue groups automatically distribute messages

### Benchmarks (Typical)

- **Message Latency**: 5-15ms (CyTube → Plugin → Response)
- **Plugin Startup**: 100-300ms (process spawn + NATS connect)
- **Throughput**: 100+ messages/sec per bot instance
- **Memory**: 50-100MB base + 10-20MB per active plugin

## Security Considerations

Security is implemented in layers (defense in depth):

### Credentials

- Store passwords in config files (gitignored)
- Use environment variables for production deployments
- Never commit `config.json` with real credentials
- Rotate API keys and passwords regularly

### Input Validation

- Parse and sanitize all incoming messages
- Validate media URLs before queueing
- Check command syntax before execution
- Escape special characters in user input

### Permission Enforcement

- Default deny policy: plugins have no permissions unless granted
- Capability-based model: permissions are explicit and granular
- Permission groups: basic (read-only), moderator (chat control), admin (config)
- Audit logging: all permission checks and violations logged to `rosey.security.audit`

### Rate Limiting

- Implement cooldowns for commands
- Track message frequency per user
- Respect CyTube flood protection limits
- Plugin-level rate limits enforced by Plugin Manager

### Process Isolation

- Plugins run in separate processes (sandbox)
- Resource limits: CPU (50%), memory (100MB default)
- No direct file system access
- No direct network access without permission
- Plugins communicate only via NATS (mediated by core)

## Migration from Monolithic to Event-Driven

### Old Architecture (Pre-Sprint 6a)

```text
lib/bot.py (monolithic)
├── WebSocket handling
├── Command routing
├── Quote system
├── Media CMS
├── Playlist management
└── All logic in one file
```

**Limitations**:

- Plugin crash = bot crash
- No isolation between features
- Difficult to test components
- Hard to scale horizontally

### New Architecture (Sprint 6a Quicksilver)

```text
NATS Event Bus (rosey.*)
├── Platform Connectors
│   └── CyTube (bot/rosey/core/cytube_connector.py)
├── Core Services
│   ├── Router (bot/rosey/core/router.py)
│   ├── Plugin Manager (bot/rosey/core/plugin_manager.py)
│   ├── Plugin Isolation (bot/rosey/core/plugin_isolation.py)
│   └── Plugin Permissions (bot/rosey/core/plugin_permissions.py)
└── Plugins (separate processes)
    ├── Quote Plugin
    ├── Media CMS Plugin
    ├── Playlist Plugin
    └── Custom Plugins...
```

**Benefits**:

- Plugin isolation: crash recovery without bot restart
- Security: sandboxed plugin execution
- Scalability: horizontal scaling with queue groups
- Testability: mock NATS for unit testing
- Multi-platform: easy to add Discord, Slack, IRC connectors

## Development Workflow

### Plugin Development

1. **Create Plugin File**:

   ```python
   # bot/rosey/plugins/my_plugin.py
   from bot.rosey.core.event_bus import EventBus
   from bot.rosey.core.subjects import Subjects
   
   async def main():
       bus = EventBus()
       await bus.connect("nats://localhost:4222")
       
       async def handle_message(event):
           # Your plugin logic
           await bus.publish(
               Subjects.PLATFORM_CYTUBE_CHAT_SEND,
               {"message": "Hello from plugin!"}
           )
       
       await bus.subscribe(Subjects.EVENTS_CHAT_MESSAGE, handle_message)
   ```

2. **Test Plugin Locally**:

   ```bash
   # Run NATS server
   docker run -p 4222:4222 nats:latest
   
   # Run your plugin
   python -m bot.rosey.plugins.my_plugin
   ```

3. **Register Plugin**:

   ```python
   # bot/rosey/config.json
   {
     "plugins": {
       "my_plugin": {
         "enabled": true,
         "path": "bot.rosey.plugins.my_plugin",
         "permissions": ["chat_read", "chat_send"]
       }
     }
   }
   ```

4. **Deploy**:
   - Plugin Manager automatically loads and starts plugin
   - Monitor health via `rosey.monitoring.plugin_health`

### Testing

- **Unit Tests**: Test components with MockNATSClient
- **Integration Tests**: Test with real NATS server (Docker)
- **Coverage**: Run `pytest --cov=bot/rosey`
- **See**: `TESTING.md` for comprehensive guide

### Debugging Plugins

1. **Enable Debug Logging**: Set `log_level: "DEBUG"` in config
2. **Monitor NATS**: Use `nats sub "rosey.>"` to see all messages
3. **Check Plugin Health**: Monitor `rosey.monitoring.plugin_health`
4. **Review Logs**: Check bot logs for errors and traces
5. **Use Correlation IDs**: Track message flow across components

## Conventions

### Naming

- **Classes**: `PascalCase`
- **Functions/methods**: `snake_case`
- **Private methods**: `_leading_underscore`
- **Constants**: `UPPER_CASE`
- **NATS Subjects**: `rosey.category.specifics` (dot-separated)

### Async

- Prefix async functions with `async def`
- Always `await` coroutines
- Use `asyncio.create_task()` for background tasks
- Plugin event handlers must be async

### Logging

- Use `logger` from event bus or component
- **Log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include context: user, channel, plugin name
- Use correlation IDs for distributed tracing

### Documentation

- **Docstrings**: All public APIs (Google style)
- **Inline comments**: Complex logic and NATS message flows
- **README**: Plugin usage and configuration
- **SPEC docs**: Design decisions and architecture changes
