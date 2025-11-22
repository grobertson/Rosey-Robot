# Product Requirements Document: Event Normalization & NATS-First Architecture

**Version:** 2.0 - BREAKING CHANGES  
**Status:** Planning (Nano-Sprint)  
**Sprint Name:** Sprint 9 "The Accountant" - *Thorough and kicks ass*  
**Target Release:** 0.9.0  
**Author:** GitHub Copilot (Claude Sonnet 4.5)  
**Date:** November 21, 2025  
**Priority:** CRITICAL - Blocks Multi-Platform Support  

---

## ⚠️ BREAKING CHANGES NOTICE

**This sprint introduces intentional breaking changes to establish the correct architectural foundation.**

- Configuration format will change (NATS required, new structure)
- Database initialization moves to separate service
- Bot no longer accepts `db` parameter
- Plugin API changes to NATS-only access
- Event structure changes require plugin updates

**Rationale**: Technical debt has accumulated to the point where maintaining backward compatibility would perpetuate architectural flaws. This is a one-time breaking change to establish the foundation for all future development.

---

## Executive Summary

Sprint 9 "The Accountant" is a **comprehensive architectural rework** that transforms Rosey from a tightly-coupled monolith into a properly-distributed, event-driven system. This is not a refactoring - it's a **redesign with breaking changes** to establish the correct foundation.

**The Problem**: Rosey has fundamental architectural flaws that prevent it from achieving its vision:
1. **Tight Coupling**: Bot directly calls database methods, preventing process isolation
2. **Incomplete Normalization**: Events have inconsistent structures, preventing platform-agnostic code
3. **Violated Boundaries**: Plugins can access bot/database internals, preventing security/sandboxing
4. **No Distribution**: Cannot run bot, database, and plugins in separate processes
5. **No Scaling**: Cannot horizontally scale across multiple bot instances

**The Solution**: Burn it down and rebuild it right:
1. **NATS-Only Communication**: Remove ALL direct method calls between layers - NATS is the ONLY way layers communicate
2. **Complete Normalization**: Fix ALL event structures to be platform-agnostic and consistent
3. **Hard Boundaries**: Enforce strict layer isolation - bot cannot access database, plugins cannot access bot
4. **Distributed-First**: Design for separate processes from day one
5. **Configuration v2**: New config format that reflects distributed architecture

**Key Achievement Goal**: Transform Rosey into a **distributed-first, event-driven, platform-agnostic** system where NATS is the foundation, not an afterthought.

---

## 1. Product Overview

### 1.1 Background

**Current State of Rosey-Robot:**

Rosey-Robot has grown through 8 sprints from a simple CyTube bot to an ambitious multi-platform framework. Each sprint added capabilities:

- **Sprint 2 (Start Me Up)**: LLM integration, initial event normalization attempt
- **Sprint 6a (Quicksilver)**: NATS event bus infrastructure
- **Sprint 8 (Inception)**: Plugin system with 146 tests (A+ grade)

However, the architecture evolved **organically rather than by design**. Technical debt accumulated:

**Fundamental Architectural Flaws:**

1. **No True Layer Isolation**: Bot class accepts `db` parameter and calls methods directly
   ```python
   # CURRENT (WRONG)
   def __init__(self, connection, channel_name, db=None):  # db injected
       self.db = db
       self.db.user_joined(username)  # direct call
   ```

2. **Inconsistent Event Structure**: Normalization was attempted but incomplete
   - `user_list` has array of strings instead of objects (backwards!)
   - `user_join` missing `user_data`, forcing handlers to access `platform_data`
   - `pm` missing `recipient` field for bi-directional support
   - Event structure varies by event type (no consistency)

3. **Plugin Security Hole**: Plugins can access bot internals
   ```python
   # CURRENT (DANGEROUS)
   self.bot.db.user_joined(...)  # plugin directly manipulates database!
   self.bot.channel.userlist     # plugin accesses bot state directly!
   ```

4. **NATS is Optional**: NATS exists but is treated as optional, not foundational
   - Bot works without NATS (defeating the purpose)
   - Database doesn't subscribe to NATS
   - Plugins don't use NATS for data access

**Why This Matters:**

These aren't bugs - they're **architectural anti-patterns** that prevent Rosey from achieving its vision:

- ❌ Multi-platform support impossible (platform-specific code scattered)
- ❌ Process isolation impossible (tight coupling)
- ❌ Horizontal scaling impossible (shared state)
- ❌ Plugin sandboxing impossible (direct access to internals)
- ❌ Hot-reload impossible (no clear boundaries)

**The Verdict**: The current architecture is **fundamentally unsound** for a distributed system. We need to break things to fix them.

### 1.2 Problem Statement

**Developer Pain**: Current architecture makes future development painful:

- Adding new platform requires touching bot/database/plugin code (scattered concerns)
- Writing plugins requires understanding bot internals (no clear API)
- Testing requires mocking database (tight coupling)
- Running in production requires everything in one process (no isolation)
- Debugging requires instrumenting multiple layers (no observability)

**Operator Pain**: Current architecture makes operations risky:

- Cannot scale bot without scaling database (coupled deployment)
- Cannot restart bot without disrupting database (no independence)
- Cannot update plugins without restarting bot (no hot-reload)
- Cannot monitor event flow (direct calls are invisible)
- Cannot sandbox untrusted plugins (direct access to everything)

**Technical Constraints - REMOVED:**

**❌ ~~Must maintain backward compatibility~~** → **NO.** Breaking compatibility is acceptable to fix architecture.

**❌ ~~Cannot break the 146 passing tests~~** → **WRONG.** Tests should reflect correct architecture, not perpetuate bad design.

**❌ ~~Must preserve all current functionality while fixing architecture~~** → **MISLEADING.** Functionality is preserved, but interfaces change.

**❌ ~~Database migration must be transparent to users~~** → **UNREALISTIC.** Users need new configuration format.

**New Constraints - What We Actually Care About:**

**✅ Zero Data Loss**: Existing database data must be preserved (schema unchanged).

**✅ Zero Feature Loss**: All current features must work after migration (different architecture, same capabilities).

**✅ Clear Migration Path**: Document exactly what users need to change (configuration, plugin updates).

**✅ Better Developer Experience**: New architecture must be simpler to work with than current mess.

**✅ Foundation for Future**: Architecture must support multi-platform, scaling, sandboxing without another rewrite.

**Impact of Not Fixing:**

Every future feature will be:

- Harder to implement (working around architecture flaws)
- Harder to test (coupled components)
- Harder to deploy (monolithic structure)
- Harder to scale (tight coupling)
- Harder to secure (no boundaries)

**Verdict**: Fix the architecture now, accept breaking changes, or pay compounding interest forever.

### 1.3 Solution - Architectural Redesign

**Not a Refactoring - A Redesign:**

This sprint is NOT incremental improvement. It's a **hard reset** on architecture to establish the correct foundation.

**Core Principle: NATS is Not Optional**

```python
# BEFORE (Optional NATS)
def __init__(self, connection, channel_name, db=None, nats_client=None):
    self.db = db  # Direct injection
    self.nats = nats_client  # Optional

# AFTER (NATS Required)
def __init__(self, connection, channel_name, nats_client):
    # No db parameter - NATS is the ONLY way to communicate
    self.nats = nats_client  # REQUIRED
```

**The New Architecture:**

```text
┌─────────────────────────────────────────────────────────────┐
│                         NATS Event Bus                      │
│                    (Foundation Layer)                       │
│                                                             │
│  Subjects:                                                  │
│  • rosey.events.message     • rosey.db.user.joined         │
│  • rosey.events.user.join   • rosey.db.message.log         │
│  • rosey.events.user.leave  • rosey.db.query.*             │
│  • rosey.events.pm          • rosey.plugin.*               │
└─────────────────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
         │                    │                    │
    Publishes          Subscribes &           Subscribes
    normalized            Publishes          to everything
      events               to DB
         │                    │                    │
┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐
│  Bot Process    │  │ Database Process│  │  Plugin Process │
│  ├─Connection   │  │  ├─SQLite       │  │  ├─PluginA      │
│  ├─Handlers     │  │  ├─Stats        │  │  ├─PluginB      │
│  ├─LLM          │  │  └─Queries      │  │  └─PluginC      │
│  └─Commands     │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
   (No DB access)     (No Bot access)     (No Bot/DB access)
```

**What Changes:**

1. **Bot Layer**: Remove `db` parameter, remove ALL `self.db.*` calls
   - Bot publishes normalized events to NATS
   - Bot uses request/reply for synchronous queries
   - Bot has NO direct database access

2. **Database Layer**: Becomes standalone service
   - Subscribes to NATS subjects (`rosey.db.*`)
   - Responds to request/reply queries
   - Publishes database events for plugins
   - Has NO reference to bot

3. **Connection Layer**: Fix ALL event normalization
   - `user_list`: Full objects in `users` array (not strings!)
   - `user_join`/`user_leave`: Add `user_data` field
   - `pm`: Add `recipient` field
   - All events follow consistent structure

4. **Plugin Layer**: NATS-only access
   - Plugins get NATS client, nothing else
   - Subscribe to subjects for data
   - Publish to subjects for actions
   - CANNOT access bot/database internals

5. **Configuration**: New format
   ```json
   {
     "platform": {
       "type": "cytube",
       "domain": "https://cytu.be",
       "channel": "AKWHR89327M",
       "credentials": {...}
     },
     "nats": {
       "server": "nats://localhost:4222",
       "cluster_id": "rosey",
       "client_id": "rosey-bot-1"
     },
     "database": {
       "path": "bot_data.db",
       "service_enabled": true
     },
     "plugins": {
       "directory": "./plugins",
       "enabled": ["markov", "quotes"]
     }
   }
   ```

**Migration Path:**

1. **Users must**: Update configuration to new format
2. **Users must**: Start NATS server (required dependency)
3. **Users must**: Update plugin code to use NATS (if custom plugins)
4. **Users get**: Same features, better architecture
5. **Users get**: Path to multi-platform, scaling, sandboxing

**What Doesn't Change:**

- ✅ Database schema (same tables, same data)
- ✅ Features (same bot capabilities)
- ✅ CyTube connection (same websocket protocol)
- ✅ Commands (same PM commands, same chat commands)

**What Does Change:**

- ❌ Configuration format (new structure)
- ❌ Bot constructor signature (no db parameter)
- ❌ Plugin API (NATS-only access)
- ❌ Event structures (fixed normalization)
- ❌ Deployment (NATS server required)

**Breaking Changes are Worth It:**

This is a one-time breaking change that establishes the foundation for:

- Sprint 10: Multi-platform (Discord, Slack)
- Sprint 11: Plugin sandboxing
- Sprint 12: Horizontal scaling
- Future: Everything else we want to build

**Without this fix**, every future feature fights the architecture. **With this fix**, every future feature builds on a solid foundation.

---

## 1.4 Breaking Changes Detail

**This section documents ALL breaking changes for user awareness.**

### Configuration Format (BREAKING)

**Old Format** (`bot/rosey/config.json`):
```json
{
  "domain": "https://cytu.be",
  "channel": "AKWHR89327M",
  "user": ["SaveTheRobots", "password"],
  "shell": "localhost:5555",
  "db": "bot_data.db",
  "llm": {...},
  "plugins": {...}
}
```

**New Format** (Configuration v2):
```json
{
  "platform": {
    "type": "cytube",
    "domain": "https://cytu.be",
    "channel": "AKWHR89327M",
    "credentials": {
      "username": "SaveTheRobots",
      "password": "password"
    }
  },
  "nats": {
    "server": "nats://localhost:4222",
    "cluster_id": "rosey",
    "client_id": "rosey-bot-1",
    "reconnect_delay": 2.0,
    "max_reconnects": -1
  },
  "database": {
    "path": "bot_data.db",
    "service_enabled": true,
    "nats_subjects": {
      "user_joined": "rosey.db.user.joined",
      "user_left": "rosey.db.user.left",
      "message_log": "rosey.db.message.log"
    }
  },
  "plugins": {
    "directory": "./plugins",
    "enabled": ["markov", "quotes"],
    "hot_reload": true
  },
  "llm": {...},
  "shell": {
    "enabled": true,
    "host": "localhost",
    "port": 5555
  }
}
```

**Migration**: Auto-migration script provided (`scripts/migrate_config_v2.py`)

### Bot Constructor Signature (BREAKING)

**Old Signature**:
```python
bot = Bot(
    connection=connection,
    channel_name="AKWHR89327M",
    logger=logger,
    db=database,           # ❌ REMOVED
    nats_client=nats       # Was optional
)
```

**New Signature**:
```python
bot = Bot(
    connection=connection,
    channel_name="AKWHR89327M",
    nats_client=nats,      # ✅ REQUIRED
    logger=logger
)
# No db parameter - enforces architectural boundary
```

**Migration**: Update all bot instantiation code, remove `db` parameter

### Plugin API (BREAKING)

**Old Plugin API**:
```python
class MyPlugin(PluginBase):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        
    async def handle_message(self, event, data):
        # ❌ DANGEROUS: Direct access to bot internals
        self.bot.db.user_joined(username)
        userlist = self.bot.channel.userlist
```

**New Plugin API**:
```python
class MyPlugin(PluginBase):
    def __init__(self, nats_client, config):
        self.nats = nats_client  # ✅ ONLY NATS
        self.config = config
        # No bot reference - enforced boundary
        
    async def handle_message(self, event, data):
        # ✅ CORRECT: Use NATS for everything
        await self.nats.publish('rosey.db.user.joined', {
            'username': username,
            'timestamp': int(time.time())
        })
        
        # Query via request/reply
        response = await self.nats.request(
            'rosey.db.userlist.get',
            {},
            timeout=2.0
        )
        userlist = json.loads(response.data)
```

**Migration**: Update ALL custom plugins to use NATS-only API

### Event Structure (BREAKING)

**Old Structure** (user_list - BACKWARDS!):
```python
{
    "users": ["alice", "bob", "charlie"],  # ❌ Just strings
    "platform_data": [...]                 # Full objects buried here
}
```

**New Structure** (user_list - CORRECT):
```python
{
    "users": [                             # ✅ Full normalized objects
        {
            "username": "alice",
            "rank": 2,
            "is_afk": False,
            "is_moderator": True
        },
        {
            "username": "bob",
            "rank": 0,
            "is_afk": False,
            "is_moderator": False
        }
    ],
    "platform_data": [...]                 # Original platform data
}
```

**Impact**: Plugins that iterate `data['users']` will get objects instead of strings

**Migration**: Update plugins to handle user objects: `user['username']` not `user`

### Database Initialization (BREAKING)

**Old Pattern**:
```python
# Bot owns database
db = BotDatabase('bot_data.db')
bot = Bot(connection, channel, db=db)
```

**New Pattern**:
```python
# Database is separate service
nats = await connect_nats('nats://localhost:4222')
db_service = DatabaseService(nats, 'bot_data.db')
await db_service.start()  # Subscribes to NATS

bot = Bot(connection, channel, nats_client=nats)
```

**Migration**: Update deployment scripts to start database service separately

### Deployment Requirements (BREAKING)

**Old Deployment**:
- Python 3.8+
- SQLite
- CyTube connection

**New Deployment** (Additional Requirements):
- ✅ **NATS Server** (required): `nats-server` must be running
- ✅ **Separate Processes** (recommended): Bot, database, plugins should run separately
- ✅ **Process Supervisor** (recommended): systemd, supervisor, or docker-compose

**Migration**: Install NATS server, update deployment scripts

### Test Suite (BREAKING)

**Old Tests**:
```python
# Tests mock database directly
db_mock = Mock(spec=BotDatabase)
bot = Bot(connection, channel, db=db_mock)
```

**New Tests**:
```python
# Tests mock NATS client
nats_mock = Mock(spec=NATSClient)
bot = Bot(connection, channel, nats_client=nats_mock)

# Verify NATS publish called
nats_mock.publish.assert_called_with('rosey.db.user.joined', {...})
```

**Migration**: Update all test fixtures and mocks to use NATS

### What DOESN'T Break

**✅ Data**: Database schema unchanged, all data preserved

**✅ Features**: All bot commands, LLM integration, PM commands work

**✅ CyTube Protocol**: Websocket connection logic unchanged

**✅ Core Logic**: Bot behavior, command handling, user tracking same

---

## 2. Goals and Success Metrics

### 2.1 Primary Goals

- **PG-001**: **Complete Event Normalization** - All events have consistent, platform-agnostic structure
- **PG-002**: **Eliminate ALL Direct Calls** - Zero `self.db.*` calls, NATS is the ONLY communication path
- **PG-003**: **Enforce Process Isolation** - Bot, database, plugins run in separate processes by default
- **PG-004**: **Remove `db` Parameter** - Bot constructor takes ONLY NATS client (hard boundary)
- **PG-005**: **Plugin NATS-Only API** - Plugins get NATS client, NOTHING else (no bot/db access)
- **PG-006**: **New Configuration Format** - Configuration v2 reflects distributed architecture
- **PG-007**: **Maintain Test Coverage** - All tests pass with new architecture (after updates)

### 2.2 Success Metrics

| Metric | Target | Measurement | Verification |
|--------|--------|-------------|--------------|
| Event Structure Compliance | 100% | All events follow normalization spec | Unit tests for each event type |
| Direct Database Calls | 0 | No `self.db.method()` in bot layer | Grep search returns no matches + lint rule |
| Bot Layer Isolation | ✅ Enforced | Bot has NO `db` parameter | Constructor signature enforcement |
| NATS Message Throughput | >1000 msg/sec | Event bus performance | Load testing |
| Process Isolation | ✅ Mandatory | Bot/DB/Plugins in separate processes | Integration test + deployment docs |
| Test Coverage | ≥85% | Maintain Sprint 8 level | Pytest coverage report |
| Configuration Migration | 100% | All old configs converted | Migration script validates |
| Plugin API Compliance | 100% | Plugins use ONLY NATS | Lint rules + architectural tests |
| Performance Overhead | <5% | NATS vs direct call latency | Benchmark tests |

### 2.3 Non-Goals (Still)

**Out of Scope for Sprint 9:**

- ✗ Multi-platform support (Discord, Slack) - **enabled** by this sprint, **implemented** in Sprint 10
- ✗ Plugin sandboxing (resource limits) - **enabled** by this sprint, **implemented** in Sprint 11
- ✗ Horizontal scaling (multiple bots) - **enabled** by this sprint, **tested** in Sprint 12
- ✗ Database schema changes - schema unchanged, only communication patterns change
- ✗ New features - this is pure architecture work
- ✗ Performance optimization - maintain existing performance (no degradation, no improvement)
- ✗ UI/UX changes - no user-facing feature changes
- ✗ UI/UX changes - no user-facing changes

**Future Sprints Will Deliver:**
- Sprint 10: Multi-platform connectors (Discord, Slack)
- Sprint 11: Plugin process isolation and sandboxing
- Sprint 12: Horizontal scaling and high availability

---

## 3. User Stories and Acceptance Criteria

### 3.1 Epic: Event Normalization

**User Story 3.1.1: Platform-Agnostic Event Structure**
```
As a platform connector developer
I want all events to have consistent normalized fields
So that I can write platform-agnostic code that works with any chat platform
```

**Acceptance Criteria:**
- [ ] All message events have `user`, `content`, `timestamp` fields
- [ ] All user_join events have `user`, `user_data`, `timestamp` fields
- [ ] All user_leave events have `user`, `timestamp` fields (optional `user_data`)
- [ ] All user_list events have `users` array with full normalized user objects
- [ ] All PM events have `user`, `recipient`, `content`, `timestamp` fields
- [ ] Platform-specific data is in `platform_data` wrapper
- [ ] Unit tests verify structure for each event type
- [ ] NORMALIZATION_SPEC.md is implementation authority

**User Story 3.1.2: Bot Handler Normalization**
```
As a bot core developer
I want event handlers to use only normalized fields
So that handlers work with any platform without changes
```

**Acceptance Criteria:**
- [ ] `_on_user_list` uses `data.get('users', [])` with full objects
- [ ] `_on_user_join` uses `data.get('user_data', {})` not `platform_data`
- [ ] `_on_user_leave` uses `data.get('user')` with no fallbacks
- [ ] `_on_message` already correct - verify no regressions
- [ ] Shell PM handler uses `data.get('user')` and `data.get('content')`
- [ ] No `platform_data` access in core bot handlers
- [ ] Integration tests verify handlers work with normalized events

**User Story 3.1.3: Connection Layer Normalization**
```
As a connection adapter implementer
I want the CyTube connection to properly normalize all events
So that downstream handlers receive consistent structure
```

**Acceptance Criteria:**
- [ ] User list normalization creates full user objects in `users` array
- [ ] User join normalization includes `user_data` with rank, afk, moderator fields
- [ ] User leave normalization matches user_join structure
- [ ] PM normalization includes `recipient` field
- [ ] Message normalization documented and verified
- [ ] All normalization has unit tests
- [ ] Platform_data wrapper preserves original for plugins

### 3.2 Epic: NATS-First Communication

**User Story 3.2.1: Pub/Sub Event Publishing**
```
As a bot core developer
I want to publish all database events to NATS
So that database layer and plugins can observe events
```

**Acceptance Criteria:**
- [ ] User join publishes to `rosey.db.user.joined` with username, user_data, timestamp
- [ ] User leave publishes to `rosey.db.user.left` with username, timestamp
- [ ] Message log publishes to `rosey.db.message.log` with username, content, timestamp
- [ ] User count publishes to `rosey.db.stats.user_count` with counts, timestamp
- [ ] Status update publishes to `rosey.db.status.update` with status dict
- [ ] High water mark publishes to `rosey.db.stats.high_water` with counts, timestamp
- [ ] All publishes are async, non-blocking
- [ ] Failed publishes log errors but don't crash bot

**User Story 3.2.2: Database Layer Subscription**
```
As a database service developer
I want database to subscribe to NATS events
So that it updates based on published events from bot
```

**Acceptance Criteria:**
- [ ] Database subscribes to `rosey.db.user.joined` → calls `user_joined()`
- [ ] Database subscribes to `rosey.db.user.left` → calls `user_left()`
- [ ] Database subscribes to `rosey.db.message.log` → calls `user_chat_message()`
- [ ] Database subscribes to `rosey.db.stats.*` → updates statistics
- [ ] Database subscribes to `rosey.db.status.update` → updates status
- [ ] Subscriptions are async, non-blocking
- [ ] Failed handlers log errors but continue processing

**User Story 3.2.3: Request/Reply Pattern**
```
As a bot core developer
I want to query database via NATS request/reply
So that synchronous operations work without direct calls
```

**Acceptance Criteria:**
- [ ] `get_unsent_outbound_messages()` uses `rosey.db.messages.outbound.get` subject
- [ ] Request includes username, limit parameters
- [ ] Reply contains JSON-encoded message list
- [ ] Timeout after 2 seconds with graceful fallback
- [ ] Request/reply measured <50ms p95 latency
- [ ] Error handling for no response, malformed response

**User Story 3.2.4: Process Isolation**
```
As a system operator
I want to run bot and database in separate processes
So that I have true isolation and can scale independently
```

**Acceptance Criteria:**
- [ ] Bot process can start without database process
- [ ] Database process subscribes to NATS and handles events
- [ ] Bot publishes events that database receives
- [ ] Request/reply works across process boundary
- [ ] Processes can restart independently without data loss
- [ ] Integration test verifies cross-process communication
- [ ] Documentation explains multi-process deployment

### 3.3 Epic: Testing and Validation

**User Story 3.3.1: Normalization Test Coverage**
```
As a quality engineer
I want comprehensive tests for event normalization
So that we catch regressions and verify correctness
```

**Acceptance Criteria:**
- [ ] Unit tests for each event type normalization (message, user_join, user_leave, user_list, pm)
- [ ] Tests verify all required normalized fields present
- [ ] Tests verify platform_data wrapper exists
- [ ] Tests verify handler access to normalized fields
- [ ] Tests verify no platform_data access in handlers
- [ ] Coverage ≥85% for normalization code

**User Story 3.3.2: NATS Communication Testing**
```
As a quality engineer
I want tests for NATS pub/sub and request/reply patterns
So that we verify layer communication works correctly
```

**Acceptance Criteria:**
- [ ] Unit tests for bot layer NATS publishes
- [ ] Unit tests for database layer NATS subscriptions
- [ ] Integration tests for end-to-end event flow (bot → NATS → database)
- [ ] Tests for request/reply timeout handling
- [ ] Tests for malformed message handling
- [ ] Tests for NATS connection failures
- [ ] Load tests verify >1000 msg/sec throughput

**User Story 3.3.3: Regression Testing**
```
As a quality engineer
I want all existing tests to still pass
So that we verify backward compatibility
```

**Acceptance Criteria:**
- [ ] All 146 Sprint 8 tests pass unchanged
- [ ] Bot still connects to live CyTube channel
- [ ] PM commands still work (help, info, status)
- [ ] Database tracking still functions
- [ ] User list updates correctly
- [ ] No performance regressions (within 5%)

---

## 4. Technical Architecture

### 4.1 Event Normalization Layer

**Component**: Connection Adapters (e.g., `lib/connection/cytube.py`)

**Responsibility**: Transform platform-specific events to normalized structure

**Normalized Event Structure:**

```python
{
    # PLATFORM-AGNOSTIC (required)
    "user": str,              # Username
    "content": str,           # Message text (if applicable)
    "timestamp": int,         # Unix timestamp (seconds)
    
    # Event-specific normalized fields
    "user_data": {...},       # Full user object (user_join, user_leave)
    "recipient": str,         # PM recipient (pm events)
    "users": [{...}, ...],    # User objects array (user_list)
    "is_read": bool,          # Read status (pm events, optional)
    
    # PLATFORM-SPECIFIC (optional, for plugins)
    "platform_data": {
        # Original platform event structure
        # Varies by platform (CyTube, Discord, etc.)
    }
}
```

**User Object Normalization:**

```python
{
    "username": str,          # Username
    "rank": int,              # Permission level (0=guest, 1=user, 2=mod, 3=admin)
    "is_afk": bool,           # AFK status
    "is_moderator": bool,     # True if rank >= 2
    # Future: avatar_url, user_id, account_age, etc.
}
```

**Normalization Functions:**

```python
# lib/connection/cytube.py

def _normalize_user_join(self, data: Dict) -> Dict:
    """Normalize CyTube addUser to user_join event."""
    return {
        'user': data.get('name', ''),
        'user_data': {
            'username': data.get('name', ''),
            'rank': data.get('rank', 0),
            'is_afk': data.get('afk', False),
            'is_moderator': data.get('rank', 0) >= 2,
        },
        'timestamp': int(time.time()),
        'platform_data': data
    }

def _normalize_user_list(self, data: List[Dict]) -> Dict:
    """Normalize CyTube userlist to user_list event."""
    return {
        'users': [
            {
                'username': user.get('name', ''),
                'rank': user.get('rank', 0),
                'is_afk': user.get('afk', False),
                'is_moderator': user.get('rank', 0) >= 2,
            }
            for user in data
        ],
        'timestamp': int(time.time()),
        'platform_data': data
    }
```

### 4.2 NATS Communication Patterns

**Component**: NATS Event Bus (from Sprint 6a)

**Subject Hierarchy:**

```text
rosey.db.user.joined              # User joined channel (pub/sub)
rosey.db.user.left                # User left channel (pub/sub)
rosey.db.message.log              # Chat message logged (pub/sub)
rosey.db.stats.user_count         # User count update (pub/sub)
rosey.db.stats.high_water         # High water mark update (pub/sub)
rosey.db.status.update            # Bot status update (pub/sub)
rosey.db.messages.outbound.get    # Query outbound messages (request/reply)
rosey.db.stats.user.query         # Query user stats (request/reply - future)
rosey.db.config.get               # Get config value (request/reply - future)
```

**Pattern 1: Pub/Sub (Async Events)**

```python
# Bot Layer (lib/bot.py)
async def _on_user_join(self, _, data):
    """Handle user join - publish to NATS."""
    if self.nats:
        await self.nats.publish('rosey.db.user.joined', {
            'username': data.get('user', ''),
            'user_data': data.get('user_data', {}),
            'timestamp': data.get('timestamp', int(time.time()))
        })

# Database Layer (common/database.py)
async def _handle_user_joined(self, msg):
    """Subscribe to user join events."""
    data = json.loads(msg.data)
    self.user_joined(data['username'])  # Internal DB method
    self.logger.info(f"User joined: {data['username']}")
```

**Pattern 2: Request/Reply (Sync Queries)**

```python
# Bot Layer (lib/bot.py)
async def _fetch_outbound_messages(self, username: str):
    """Query database via NATS request/reply."""
    if not self.nats:
        return []
    
    try:
        response = await self.nats.request(
            'rosey.db.messages.outbound.get',
            {'username': username, 'limit': 10},
            timeout=2.0
        )
        return json.loads(response.data)
    except asyncio.TimeoutError:
        self.logger.warning("Database query timeout")
        return []

# Database Layer (common/database.py)
async def _handle_outbound_query(self, msg):
    """Respond to outbound message queries."""
    data = json.loads(msg.data)
    messages = self.get_unsent_outbound_messages(
        data['username'],
        limit=data.get('limit', 10)
    )
    await self.nats.publish(msg.reply, messages)
```

### 4.3 Database Layer Service

**New Component**: `common/database_service.py`

**Purpose**: Wraps `BotDatabase` with NATS subscription handlers

**Architecture:**

```python
class DatabaseService:
    """NATS-enabled database service."""
    
    def __init__(self, nats_client, db_path):
        self.nats = nats_client
        self.db = BotDatabase(db_path)
        self._subscriptions = []
    
    async def start(self):
        """Subscribe to all database subjects."""
        self._subscriptions = [
            await self.nats.subscribe('rosey.db.user.joined', self._handle_user_joined),
            await self.nats.subscribe('rosey.db.user.left', self._handle_user_left),
            await self.nats.subscribe('rosey.db.message.log', self._handle_message_log),
            await self.nats.subscribe('rosey.db.stats.user_count', self._handle_user_count),
            await self.nats.subscribe('rosey.db.stats.high_water', self._handle_high_water),
            await self.nats.subscribe('rosey.db.status.update', self._handle_status_update),
            await self.nats.subscribe('rosey.db.messages.outbound.get', self._handle_outbound_query),
        ]
        self.logger.info(f"Database service started with {len(self._subscriptions)} subscriptions")
    
    async def stop(self):
        """Unsubscribe from all subjects."""
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions = []
```

### 4.4 Bot Layer Changes

**Modified Component**: `lib/bot.py`

**Changes Required:**

1. **Add NATS Client Reference**
```python
def __init__(self, connection, channel_name, logger=None, nats_client=None):
    # ... existing code ...
    self.nats = nats_client  # NEW: NATS client for event publishing
```

2. **Replace Direct Database Calls with NATS Publishes**
```python
# BEFORE (items #11-#16):
if self.db:
    self.db.user_joined(username)

# AFTER:
if self.nats:
    await self.nats.publish('rosey.db.user.joined', {
        'username': username,
        'user_data': user_data,
        'timestamp': int(time.time())
    })

# Maintain backward compatibility
if self.db and not self.nats:
    # Direct call if no NATS (transition period)
    self.db.user_joined(username)
```

3. **Replace Direct Query with Request/Reply (item #17)**
```python
# BEFORE:
if self.db:
    messages = self.db.get_unsent_outbound_messages(username)

# AFTER:
if self.nats:
    response = await self.nats.request(
        'rosey.db.messages.outbound.get',
        {'username': username, 'limit': 10},
        timeout=2.0
    )
    messages = json.loads(response.data) if response else []
elif self.db:
    # Backward compatibility
    messages = self.db.get_unsent_outbound_messages(username)
```

### 4.5 Migration Strategy

**Phase 0: NATS Infrastructure**
- Verify NATS server running (from Sprint 6a)
- Implement subject registry: `lib/nats/subjects.py`
- Add connection management utilities

**Phase 1: Event Normalization**
- Fix connection layer normalization (items #1-#5)
- Update bot handlers (items #6-#10)
- Add normalization unit tests

**Phase 2: NATS Migration**
- Implement database service (new component)
- Add NATS publishes to bot layer (items #11-#17)
- Maintain backward compatibility (dual-mode)
- Add NATS communication tests

**Phase 3: Integration & Testing**
- End-to-end testing with NATS
- Performance benchmarking
- Process isolation testing
- Regression testing (146 existing tests)

**Phase 4: Transition**
- Document NATS-first patterns
- Update deployment guides
- Deprecate direct database calls (warnings)
- Plan removal of backward compatibility (future sprint)

---

## 5. Data Flow and Interactions

### 5.1 Message Event Flow (Current)

```text
CyTube Server
     │
     │ WebSocket: chatMsg event
     ↓
CyTubeConnection
     │
     │ _emit_normalized_event('message', normalized_data)
     ↓
Bot._on_message()
     │
     │ ❌ DIRECT CALL: self.db.user_chat_message(username, msg)
     ↓
BotDatabase.user_chat_message()
     │
     │ SQL INSERT
     ↓
SQLite Database

❌ Problem: Plugins cannot observe message logging
❌ Problem: Database and bot must be in same process
```

### 5.2 Message Event Flow (Target)

```text
CyTube Server
     │
     │ WebSocket: chatMsg event
     ↓
CyTubeConnection
     │
     │ _emit_normalized_event('message', normalized_data)
     ↓
Bot._on_message()
     │
     │ ✅ NATS PUBLISH: rosey.db.message.log
     ├─────────────────┐
     │                 │
     ↓                 ↓
DatabaseService    Plugins (observers)
     │                 │
     │                 ├─> Analytics Plugin (tracks trends)
     │                 ├─> Moderation Plugin (filters spam)
     │                 └─> Logging Plugin (archives chat)
     │
     │ user_chat_message()
     ↓
SQLite Database

✅ Solution: Plugins can observe all events
✅ Solution: Database can run in separate process
✅ Solution: Horizontal scaling possible
```

### 5.3 User Join Flow (Current)

```text
CyTube Server
     │
     │ WebSocket: addUser event
     ↓
CyTubeConnection
     │
     │ ⚠️ INCOMPLETE: normalized_data missing 'user_data' field
     ↓
Bot._on_user_join()
     │
     │ ⚠️ WORKAROUND: user_data = data.get('platform_data', data)
     │ ❌ DIRECT CALL: self.db.user_joined(username)
     ↓
BotDatabase.user_joined()

❌ Problem: Handler accesses platform_data (not platform-agnostic)
❌ Problem: Direct database call (tight coupling)
```

### 5.4 User Join Flow (Target)

```text
CyTube Server
     │
     │ WebSocket: addUser event
     ↓
CyTubeConnection
     │
     │ ✅ COMPLETE: normalized_data includes 'user_data' field
     ↓
Bot._on_user_join()
     │
     │ ✅ NORMALIZED: user_data = data.get('user_data', {})
     │ ✅ NATS PUBLISH: rosey.db.user.joined
     ├─────────────────┐
     │                 │
     ↓                 ↓
DatabaseService    Plugins
     │                 │
     │                 └─> Welcome Plugin (sends greeting)
     │
     │ user_joined()
     ↓
SQLite Database

✅ Solution: Platform-agnostic handler code
✅ Solution: Plugins can react to user joins
```

### 5.5 Database Query Flow (Target)

```text
Bot needs outbound messages
     │
     │ ✅ NATS REQUEST: rosey.db.messages.outbound.get
     ↓
NATS Server
     │
     │ Routes to subscriber
     ↓
DatabaseService._handle_outbound_query()
     │
     │ Query internal database
     ↓
BotDatabase.get_unsent_outbound_messages()
     │
     │ SQL SELECT
     ↓
SQLite Database
     ↓
     │ Results
     ↓
DatabaseService
     │
     │ ✅ NATS REPLY: JSON-encoded messages
     ↓
NATS Server
     │
     │ Delivers response
     ↓
Bot receives messages

✅ Solution: Synchronous query via request/reply
✅ Solution: Timeout handling (2 sec)
✅ Solution: Process-isolated communication
```

---

## 6. Security and Privacy Considerations

### 6.1 Process Isolation Security

**Benefit**: Running bot and database in separate processes provides security boundaries

**Risk Mitigation**:
- Process crashes isolated - database crash doesn't bring down bot
- Memory isolation - bot cannot directly access database memory
- Syscall isolation - database cannot execute bot code
- Resource limits - can apply CPU/memory limits per process

**Implementation**:
- Database service runs as separate Python process
- Communication only via NATS (no shared memory)
- Process supervisor (systemd) monitors both processes
- Independent restart capability

### 6.2 Plugin Security Enhancement

**Current Risk**: Plugins can access bot internals directly
- `self.bot.db.user_joined()` - plugin directly manipulates database
- `self.bot.channel.userlist` - plugin directly accesses state
- No isolation between plugins

**Future Benefit** (enabled by this sprint):
- Plugins only access NATS event bus
- Cannot directly call bot methods
- Cannot access other plugin state
- Process sandboxing possible (future sprint)

**Sprint 9 Preparation**:
- All database operations via NATS (this sprint)
- Plugin API only exposes NATS client (future sprint)
- Documentation discourages direct access (this sprint)

### 6.3 Data Privacy

**NATS Message Content**:
- Contains usernames, message text, user data
- Transmitted over NATS (local or network)

**Mitigation**:
- NATS TLS support for network deployment (document, not implement)
- NATS authentication (document, not implement)
- Message payload encryption (future consideration)
- Local deployment default (NATS on localhost)

**Compliance**:
- No PII stored beyond what database already stores
- NATS messages ephemeral (not persisted)
- Audit logging capability via NATS monitoring (future)

---

## 7. Dependencies and Integrations

### 7.1 Internal Dependencies

**Sprint 6a (Quicksilver)**: NATS Event Bus Infrastructure
- ✅ NATS server operational
- ✅ NATS client library integrated
- ✅ Basic pub/sub working
- ⚠️ Need: Subject hierarchy definition (new file)
- ⚠️ Need: Request/reply pattern implementation (extend existing)

**Sprint 8 (Inception)**: Plugin System
- ✅ 146 tests passing - MUST NOT BREAK
- ✅ Plugin base class established
- ✅ Event handler registration working
- ⚠️ Need: Update plugin docs with NATS patterns

**Existing Components**:
- `lib/bot.py` - Core bot (MODIFY: add NATS publishes)
- `lib/connection/cytube.py` - Connection adapter (MODIFY: fix normalization)
- `common/database.py` - Database (WRAP: create service layer)
- `common/shell.py` - PM commands (MODIFY: use normalized fields)

### 7.2 External Dependencies

**NATS Server**:
- Already installed (Sprint 6a)
- Version: Latest stable (2.x)
- Configuration: Local development (localhost:4222)
- Production: Document external NATS deployment

**Python Libraries**:
- `nats-py` - Already in requirements.txt (Sprint 6a)
- No new dependencies required

### 7.3 Breaking Changes

**None Expected** - Backward Compatibility Maintained:
- Direct database calls remain functional during transition
- NATS optional (backward compatibility fallback)
- Configuration changes optional
- Existing bots work unchanged

**Future Breaking Change** (Sprint 11+):
- Remove direct database access from Bot class
- Require NATS for database operations
- Deprecation warnings in Sprint 9, removal in Sprint 11

---

## 8. Testing Strategy

### 8.1 Unit Testing

**Event Normalization Tests** (items #1-#5):
```python
# tests/unit/test_normalization_cytube.py

def test_normalize_user_join():
    """Verify user_join normalization includes user_data."""
    cytube_data = {'name': 'alice', 'rank': 2, 'afk': False}
    result = connection._normalize_user_join(cytube_data)
    
    assert result['user'] == 'alice'
    assert result['user_data']['username'] == 'alice'
    assert result['user_data']['rank'] == 2
    assert result['user_data']['is_afk'] is False
    assert result['user_data']['is_moderator'] is True  # rank >= 2
    assert 'timestamp' in result
    assert result['platform_data'] == cytube_data

def test_normalize_user_list():
    """Verify user_list has full objects in users array."""
    cytube_data = [
        {'name': 'alice', 'rank': 2, 'afk': False},
        {'name': 'bob', 'rank': 0, 'afk': True}
    ]
    result = connection._normalize_user_list(cytube_data)
    
    assert len(result['users']) == 2
    assert result['users'][0]['username'] == 'alice'
    assert result['users'][0]['is_moderator'] is True
    assert result['users'][1]['username'] == 'bob'
    assert result['users'][1]['is_afk'] is True
    assert result['platform_data'] == cytube_data
```

**NATS Communication Tests** (items #11-#17):
```python
# tests/unit/test_nats_bot_layer.py

async def test_user_join_publishes_nats(mock_nats):
    """Verify bot publishes user_join to NATS."""
    bot = Bot(connection, channel, nats_client=mock_nats)
    
    await bot._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 2},
        'timestamp': 1234567890
    })
    
    mock_nats.publish.assert_called_once()
    subject, payload = mock_nats.publish.call_args[0]
    assert subject == 'rosey.db.user.joined'
    assert payload['username'] == 'alice'

# tests/unit/test_nats_database_service.py

async def test_database_handles_user_joined(mock_db):
    """Verify database service handles user_joined events."""
    service = DatabaseService(nats_client, mock_db)
    
    msg = MockMsg(data=json.dumps({
        'username': 'alice',
        'user_data': {...},
        'timestamp': 1234567890
    }))
    
    await service._handle_user_joined(msg)
    
    mock_db.user_joined.assert_called_once_with('alice')
```

### 8.2 Integration Testing

**End-to-End Event Flow**:
```python
# tests/integration/test_nats_event_flow.py

async def test_user_join_end_to_end():
    """Verify user join flows through entire system."""
    # Setup
    nats_server = await start_test_nats_server()
    bot = create_test_bot(nats_client=nats_client)
    db_service = DatabaseService(nats_client, test_db)
    await db_service.start()
    
    # Simulate CyTube user join
    await bot._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 2},
        'timestamp': 1234567890
    })
    
    # Wait for async processing
    await asyncio.sleep(0.1)
    
    # Verify database was updated
    assert test_db.get_user('alice') is not None
    
    # Cleanup
    await db_service.stop()
    await nats_server.stop()
```

**Process Isolation Test**:
```python
# tests/integration/test_process_isolation.py

def test_bot_and_database_separate_processes():
    """Verify bot and database can run in separate processes."""
    # Start NATS server
    nats_proc = subprocess.Popen(['nats-server'])
    time.sleep(1)
    
    # Start database service in separate process
    db_proc = subprocess.Popen([
        'python', '-m', 'common.database_service',
        '--nats', 'localhost:4222',
        '--db', 'test.db'
    ])
    time.sleep(1)
    
    # Start bot in separate process
    bot_proc = subprocess.Popen([
        'python', '-m', 'bot.rosey.rosey',
        'test_config.json'
    ])
    time.sleep(5)
    
    # Verify both processes running
    assert db_proc.poll() is None
    assert bot_proc.poll() is None
    
    # Verify communication working (check database for events)
    db = BotDatabase('test.db')
    assert len(db.get_recent_events()) > 0
    
    # Cleanup
    bot_proc.terminate()
    db_proc.terminate()
    nats_proc.terminate()
```

### 8.3 Regression Testing

**Sprint 8 Test Suite**:
- All 146 tests MUST pass unchanged
- Run full pytest suite after each phase
- No modifications to existing test code
- New tests added in separate files

**Live Connection Test**:
```python
# tests/integration/test_live_cytube.py (enhanced)

async def test_live_connection_with_normalization():
    """Verify bot still works with live CyTube channel."""
    bot = await create_live_bot(
        channel='AKWHR89327M',
        username='SaveTheRobots',
        nats_enabled=True
    )
    
    # Connect and wait for userlist
    await bot.connect()
    await asyncio.sleep(5)
    
    # Verify normalized events received
    assert len(bot.channel.userlist) > 0
    
    # Verify NATS messages published
    assert bot.nats.message_count > 0
    
    # Test PM commands
    response = await bot.send_pm('help')
    assert 'Available commands' in response
```

### 8.4 Performance Testing

**NATS Throughput Benchmark**:
```python
# tests/performance/test_nats_throughput.py

async def test_event_publishing_throughput():
    """Verify NATS can handle expected event load."""
    nats_client = await connect_nats()
    
    start = time.time()
    count = 10000
    
    # Publish 10k events
    for i in range(count):
        await nats_client.publish('rosey.db.test', {
            'event_id': i,
            'timestamp': time.time()
        })
    
    elapsed = time.time() - start
    throughput = count / elapsed
    
    # Target: >1000 msg/sec
    assert throughput > 1000, f"Throughput {throughput:.0f} msg/sec < 1000"
```

**Latency Comparison**:
```python
# tests/performance/test_latency.py

async def test_nats_vs_direct_call_latency():
    """Compare NATS request/reply vs direct database call."""
    # Direct call baseline
    direct_times = []
    for _ in range(100):
        start = time.perf_counter()
        result = db.get_unsent_outbound_messages('testuser')
        direct_times.append(time.perf_counter() - start)
    
    # NATS request/reply
    nats_times = []
    for _ in range(100):
        start = time.perf_counter()
        result = await nats_client.request('rosey.db.messages.outbound.get', {...})
        nats_times.append(time.perf_counter() - start)
    
    direct_p95 = np.percentile(direct_times, 95)
    nats_p95 = np.percentile(nats_times, 95)
    overhead = (nats_p95 - direct_p95) / direct_p95
    
    # Target: <5% overhead at p95
    assert overhead < 0.05, f"NATS overhead {overhead*100:.1f}% > 5%"
```

---

## 9. Rollout and Deployment

### 9.1 Development Environment Setup

**NATS Server Installation**:
```bash
# Already installed in Sprint 6a, verify:
nats-server --version

# Start NATS server for development
nats-server -p 4222 -m 8222
```

**Configuration Changes**:
```json
{
  "domain": "https://cytu.be",
  "channel": "AKWHR89327M",
  "user": ["SaveTheRobots", "password"],
  "shell": "localhost:5555",
  "db": "bot_data.db",
  "nats": {
    "enabled": true,
    "server": "localhost:4222",
    "subjects": {
      "database": "rosey.db.*",
      "events": "rosey.events.*"
    }
  }
}
```

### 9.2 Phased Rollout

**Phase 1: Development Testing** (Days 1-2)
- All developers run with NATS enabled
- Dual-mode operation (NATS + direct calls)
- Extensive logging to verify NATS communication
- Unit and integration tests passing

**Phase 2: Staging Deployment** (Day 3)
- Deploy to test CyTube channel
- Run for 24 hours with monitoring
- Verify all events flowing through NATS
- Performance metrics collected

**Phase 3: Production Deployment** (Day 4)
- Deploy to production CyTube channel
- Monitor for 48 hours
- Gradual cutover from direct calls to NATS
- Rollback plan available

**Rollback Plan**:
- Set `nats.enabled: false` in config
- Restart bot (reverts to direct database calls)
- No data loss (database unchanged)
- Backward compatible design ensures safety

### 9.3 Documentation Updates

**New Documentation**:
- `docs/NORMALIZATION_SPEC.md` - Already created ✅
- `docs/NORMALIZATION_TODO.md` - Already created ✅
- `docs/NATS_SETUP.md` - NATS installation and configuration
- `docs/NATS_TROUBLESHOOTING.md` - Common issues and solutions
- `docs/PROCESS_ISOLATION.md` - Multi-process deployment guide

**Updated Documentation**:
- `docs/ARCHITECTURE.md` - Add NATS communication flows
- `docs/QUICKSTART.md` - Include NATS setup steps
- `docs/TESTING.md` - Add NATS testing patterns
- `lib/plugin/base.py` - Document NATS access for plugins
- `README.md` - Update architecture diagram

### 9.4 Monitoring and Observability

**NATS Metrics** (via NATS monitoring port 8222):
- Message throughput (msg/sec)
- Subject subscription counts
- Queue depth
- Connection status
- Error rates

**Application Metrics**:
- Event normalization success rate
- NATS publish success rate
- Request/reply timeout rate
- Database update latency
- Process health (bot, database, NATS)

**Logging Enhancements**:
```python
# Structured logging for NATS events
logger.info("NATS publish", extra={
    'subject': 'rosey.db.user.joined',
    'username': username,
    'latency_ms': latency
})

logger.info("NATS subscribe", extra={
    'subject': 'rosey.db.message.log',
    'message_count': count,
    'handler': '_handle_message_log'
})
```

---

## 10. Success Criteria and Validation

### 10.1 Definition of Done

**Event Normalization Complete**:
- [ ] All 5 connection layer normalization items (#1-#5) implemented
- [ ] All 4 bot handler items (#6-#9) implemented  
- [ ] Shell PM handler item (#10) implemented
- [ ] Unit tests for each event type passing
- [ ] Integration tests verify normalized events work end-to-end

**NATS Migration Complete**:
- [ ] All 7 direct database call items (#11-#17) replaced with NATS
- [ ] Database service implemented and tested
- [ ] Request/reply pattern working for queries
- [ ] Pub/sub pattern working for events
- [ ] Process isolation verified in integration test

**Testing Complete**:
- [ ] All 146 Sprint 8 tests still passing
- [ ] New normalization unit tests passing (≥20 tests)
- [ ] New NATS communication tests passing (≥15 tests)
- [ ] Integration tests passing (≥5 end-to-end scenarios)
- [ ] Performance tests passing (<5% overhead, >1000 msg/sec)
- [ ] Live CyTube connection test passing

**Documentation Complete**:
- [ ] NORMALIZATION_SPEC.md finalized
- [ ] NORMALIZATION_TODO.md updated to "implemented" status
- [ ] NATS_SETUP.md created
- [ ] ARCHITECTURE.md updated with NATS flows
- [ ] Plugin documentation updated with NATS patterns
- [ ] All sortie specs completed

**Deployment Ready**:
- [ ] NATS server operational
- [ ] Bot works with NATS enabled
- [ ] Database service works standalone
- [ ] Process isolation tested
- [ ] Backward compatibility verified
- [ ] Rollback procedure documented

### 10.2 Acceptance Testing

**Test Scenario 1: Platform-Agnostic Handler**
```gherkin
Given a CyTube connection adapter
When a user joins the channel
Then the normalized event has 'user' and 'user_data' fields
And the bot handler accesses only normalized fields
And the handler does NOT access 'platform_data'
```

**Test Scenario 2: NATS Event Flow**
```gherkin
Given bot and database running in separate processes
When a user sends a chat message
Then bot publishes 'rosey.db.message.log' to NATS
And database service receives the event
And database updates the message log table
And the process boundary is maintained
```

**Test Scenario 3: Request/Reply Query**
```gherkin
Given bot needs outbound messages for a user
When bot sends NATS request 'rosey.db.messages.outbound.get'
Then database service responds within 2 seconds
And response contains JSON-encoded message list
And bot receives the messages successfully
```

**Test Scenario 4: Backward Compatibility**
```gherkin
Given a legacy configuration without NATS settings
When bot starts with NATS disabled
Then bot falls back to direct database calls
And all functionality works as before
And no errors are logged
```

### 10.3 Performance Validation

**Baseline Metrics** (pre-Sprint 9):
- Direct database call latency: ~0.5ms p95
- User join processing: ~2ms p95
- Message logging: ~1ms p95
- Memory usage: ~80MB steady state

**Target Metrics** (post-Sprint 9):
- NATS event publish latency: <1ms p95 (≤2x baseline)
- NATS request/reply latency: <5ms p95 (<10x baseline)
- User join processing: <3ms p95 (<50% overhead)
- Message logging: <2ms p95 (<100% overhead)
- Memory usage: <100MB steady state (<25% increase)
- NATS throughput: >1000 msg/sec sustained

**Validation Method**:
- Run performance test suite before and after migration
- Compare p95 latencies for all operations
- Verify overhead within acceptable bounds (<5% for most operations)
- Load test with 10k events to verify throughput
- Monitor production for 48 hours post-deployment

---

## 11. Risks and Mitigation Strategies

### 11.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking Sprint 8 tests | Medium | High | Run tests after each change, fix immediately |
| NATS performance overhead | Low | Medium | Performance testing early, optimize if needed |
| Normalization bugs | Medium | High | Comprehensive unit tests, incremental changes |
| Process communication failure | Low | High | Timeout handling, graceful degradation |
| Database service crashes | Low | Medium | Supervisor restart, NATS reconnection logic |
| Race conditions in async code | Medium | Medium | Careful async/await usage, integration tests |

### 11.2 Risk Mitigation Details

**Risk: Breaking Existing Tests**

*Mitigation Strategy*:
- Run full test suite after every commit
- Use feature flags for new behavior (dual-mode)
- Incremental changes with frequent validation
- Automated CI runs all tests on every PR
- Rollback capability if tests fail

**Risk: NATS Performance Overhead**

*Mitigation Strategy*:
- Early performance testing in Phase 1
- Benchmark NATS vs direct calls
- Optimize serialization (use msgpack if needed)
- Connection pooling and batching (if needed)
- Monitor production metrics closely

**Risk: Event Normalization Bugs**

*Mitigation Strategy*:
- Unit test each event type thoroughly
- Integration tests verify end-to-end flow
- Live testing with real CyTube channel
- Incremental rollout (dev → staging → prod)
- Detailed logging to diagnose issues

**Risk: Process Communication Failure**

*Mitigation Strategy*:
- Timeout handling (2 sec for request/reply)
- Graceful degradation (log warning, continue)
- NATS reconnection logic (exponential backoff)
- Health checks for bot and database processes
- Monitoring alerts for communication failures

### 11.3 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Incomplete documentation | Medium | Medium | Documentation checkpoint in each phase |
| Complex rollback procedure | Low | Medium | Simple flag-based rollback, test procedure |
| Learning curve for NATS | Medium | Low | Example code, troubleshooting guide |
| Deployment complexity | Low | Medium | Automated deployment scripts |

---

## 12. Future Enhancements (Post-Sprint 9)

### 12.1 Sprint 10: Multi-Platform Support

**Enabled by Sprint 9**:
- Event normalization complete ✅
- Platform-agnostic handlers ✅
- NATS event bus ready ✅

**Sprint 10 Will Add**:
- Discord connection adapter
- Slack connection adapter
- IRC connection adapter
- Platform detection in events (`platform` field)
- Platform-specific plugin capabilities

### 12.2 Sprint 11: Plugin Process Isolation

**Enabled by Sprint 9**:
- NATS-first communication ✅
- Process isolation patterns established ✅
- Plugin event access via NATS ✅

**Sprint 11 Will Add**:
- Plugin launcher service
- Process sandboxing (resource limits)
- Plugin crash recovery
- Plugin health monitoring
- Plugin API restrictions (no direct bot access)

### 12.3 Sprint 12: Horizontal Scaling

**Enabled by Sprint 9**:
- Database service independent ✅
- Bot publishes to shared NATS ✅
- No direct coupling between instances ✅

**Sprint 12 Will Add**:
- Multiple bot instances sharing database
- Load balancing across bot instances
- Distributed state management
- Leader election (if needed)
- Multi-instance monitoring dashboard

### 12.4 Long-Term Vision

**Year 1**:
- Multi-platform production deployment
- 100+ community plugins
- Horizontal scaling to 1000+ channels
- Plugin marketplace

**Year 2**:
- Platform bridge (forward events between platforms)
- Unified user identity across platforms
- Advanced analytics and ML capabilities
- Cloud-native deployment (Kubernetes)

---

## 13. Appendices

### Appendix A: NATS Subject Hierarchy (Complete)

```text
rosey.
├── db.                           # Database operations
│   ├── user.
│   │   ├── joined               # User joined event (pub/sub)
│   │   ├── left                 # User left event (pub/sub)
│   │   └── query                # Query user info (request/reply)
│   ├── message.
│   │   ├── log                  # Log chat message (pub/sub)
│   │   └── query                # Query message history (request/reply)
│   ├── stats.
│   │   ├── user_count           # User count update (pub/sub)
│   │   ├── high_water           # High water mark (pub/sub)
│   │   └── query                # Query statistics (request/reply)
│   ├── status.
│   │   ├── update               # Status update (pub/sub)
│   │   └── query                # Query status (request/reply)
│   ├── config.
│   │   ├── get                  # Get config value (request/reply)
│   │   └── set                  # Set config value (request/reply)
│   └── messages.
│       └── outbound.
│           └── get              # Get outbound messages (request/reply)
├── events.                       # Normalized platform events
│   ├── message                  # Chat message (any platform)
│   ├── user.
│   │   ├── join                 # User joined
│   │   ├── leave                # User left
│   │   └── list                 # User list update
│   └── pm                       # Private message
└── platform.                     # Platform-specific events
    ├── cytube.
    │   ├── message              # CyTube-specific message
    │   ├── user.join            # CyTube-specific user join
    │   └── ...
    ├── discord.
    │   └── ...
    └── slack.
        └── ...
```

### Appendix B: Normalization Audit Summary

**Total Issues Identified**: 17

**Category Breakdown**:
- Event Normalization: 10 items (#1-#10)
- Direct Database Calls: 7 items (#11-#17)

**Severity Distribution**:
- CRITICAL: 3 items (#4, #11, #12, #13, #17)
- HIGH: 4 items (#2, #6, #7, #14, #15)
- MEDIUM: 5 items (#3, #5, #8, #10, #16)
- LOW: 1 item (#1)
- NONE: 1 item (#9 - already correct)

**Effort Estimate**:
- Phase 0 (NATS Infrastructure): 6-8 hours
- Phase 1 (Event Normalization): 4-6 hours
- Phase 2 (NATS Migration): 6-8 hours
- Phase 3 (Bot Handlers): 2-3 hours
- Phase 4 (Components): 1-2 hours
- Phase 5 (Documentation): 3-4 hours
- **Total**: 22-31 hours (3-4 days)

### Appendix C: File Change Summary

**Files Modified**:
1. `lib/connection/cytube.py` - Fix normalization (5 changes)
2. `lib/bot.py` - NATS migration (11 changes)
3. `common/shell.py` - Use normalized fields (1 change)

**Files Created**:
1. `common/database_service.py` - Database NATS service
2. `lib/nats/subjects.py` - Subject hierarchy registry
3. `docs/NATS_SETUP.md` - Setup guide
4. `docs/NATS_TROUBLESHOOTING.md` - Troubleshooting guide
5. `docs/PROCESS_ISOLATION.md` - Multi-process deployment

**Test Files Created**:
1. `tests/unit/test_normalization_cytube.py`
2. `tests/unit/test_nats_bot_layer.py`
3. `tests/unit/test_nats_database_service.py`
4. `tests/integration/test_nats_event_flow.py`
5. `tests/integration/test_process_isolation.py`
6. `tests/performance/test_nats_throughput.py`
7. `tests/performance/test_latency.py`

### Appendix D: Reference Documentation

**Internal**:
- [NORMALIZATION_SPEC.md](../../../docs/NORMALIZATION_SPEC.md) - Event normalization specification
- [NORMALIZATION_TODO.md](../../../docs/NORMALIZATION_TODO.md) - Audit findings and TODO list
- [ARCHITECTURE.md](../../../docs/ARCHITECTURE.md) - System architecture overview
- [AGENTS.md](../../../AGENTS.md) - Agent-assisted development workflow

**External**:
- [NATS Documentation](https://docs.nats.io/) - NATS server and client docs
- [NATS Python Client](https://github.com/nats-io/nats.py) - Python NATS library
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html) - Martin Fowler's guide

---

## 14. Glossary

**Event Normalization**: Process of transforming platform-specific event structures into standardized format

**NATS**: Message bus technology for event-driven communication (from "Neural Autonomic Transport System")

**Pub/Sub**: Publish/Subscribe pattern - fire-and-forget message delivery to multiple subscribers

**Request/Reply**: Synchronous query pattern - send request, wait for response

**Platform-Agnostic**: Code that works with any chat platform without modification

**Process Isolation**: Running components in separate OS processes for security and fault tolerance

**Direct Database Call**: Anti-pattern where bot directly invokes database methods (tight coupling)

**Normalized Fields**: Standard event fields consistent across all platforms (user, content, timestamp)

**Platform Data**: Original platform-specific event structure wrapped in normalized event

**Subject**: NATS topic/channel for publishing and subscribing to messages

**Layer Isolation**: Architectural principle that layers communicate only via defined interfaces (NATS)

---

**PRD Status**: ✅ Complete  
**Next Action**: Create Sortie Specifications  
**Document Owner**: Rosey-Robot Team  
**Sprint Start Date**: TBD  
**Estimated Sprint Duration**: 3-4 days  
**Sprint Goal**: Transform Rosey into properly-isolated, NATS-driven, platform-agnostic system
