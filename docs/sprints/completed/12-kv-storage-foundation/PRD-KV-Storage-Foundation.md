# Product Requirements Document: Key-Value Storage Foundation

**Sprint**: 12 (Campaign: Plugin Storage A→B→C→D)  
**Status**: Planning  
**Version**: 1.0  
**Created**: November 22, 2025  
**Target Completion**: 3-4 days (4 sorties)  
**Dependencies**: NATS Event Bus (Sprint 6a), Database Service (Sprint 9)  

---

## Executive Summary

**Mission**: Establish the foundational storage tier for Rosey's plugin architecture by implementing a **Key-Value (KV) storage API** via NATS subjects, enabling plugins to persist simple state (configuration, counters, flags, temporary data) without direct database access.

**Why Now**: Rosey's plugin system has mature process isolation (`plugin_manager.py`), NATS-based communication (`database_service.py`), and SQLAlchemy database infrastructure (`common/database.py`). Plugins can run safely but cannot persist state. KV storage is the simplest, most essential storage primitive - perfect foundation for the 4-sprint storage campaign.

**Business Value**:
- **🎮 Unblock Game Plugins**: Enable stateful plugins (quote-db, trivia, dice macros)
- **🔧 Developer Velocity**: Simple API - set/get/delete/list with 5-10 lines of code
- **🔒 Security**: Plugin isolation enforced at database layer (namespace scoping)
- **⚡ Performance**: Sub-10ms operations, background TTL cleanup, 1000+ ops/sec
- **📊 Foundation**: Proven pattern for Row Operations (Sprint B) and SQL (Sprint D)

**Success Criteria**: Plugins can store/retrieve JSON values via NATS, TTL expiration works, isolation enforced, tests pass, docs complete.

---

## Table of Contents

1. [Problem Statement & Context](#1-problem-statement--context)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Success Metrics](#3-success-metrics)
4. [User Personas](#4-user-personas)
5. [User Stories](#5-user-stories)
6. [Technical Architecture](#6-technical-architecture)
7. [Database Schema Design](#7-database-schema-design)
8. [NATS Subject Design](#8-nats-subject-design)
9. [API Specifications](#9-api-specifications)
10. [Implementation Plan](#10-implementation-plan)
11. [Testing Strategy](#11-testing-strategy)
12. [Security & Isolation](#12-security--isolation)
13. [Performance Requirements](#13-performance-requirements)
14. [Error Handling](#14-error-handling)
15. [Observability](#15-observability)
16. [Documentation Requirements](#16-documentation-requirements)
17. [Dependencies & Risks](#17-dependencies--risks)
18. [Acceptance Criteria](#18-acceptance-criteria)
19. [Future Enhancements](#19-future-enhancements)

---

## 1. Problem Statement & Context

### 1.1 Current State

**Plugin Architecture Maturity**:
- ✅ **Process Isolation**: `plugin_manager.py` + `plugin_isolation.py` manage plugin subprocesses
- ✅ **NATS Communication**: Plugins communicate via event bus (Sprint 6a "Quicksilver")
- ✅ **Database Service**: `database_service.py` handles `rosey.db.*` subjects (Sprint 9 "The Accountant")
- ✅ **SQLAlchemy Foundation**: `common/database.py` with async support, SQLite + PostgreSQL (Sprint 11 "The Conversation")
- ❌ **Plugin Storage**: No API for plugins to persist state

**Current Plugin Storage Options**:
1. **In-Memory State**: Lost on restart/crash
2. **Direct SQLite**: Violates isolation, requires each plugin to manage database connections
3. **File System**: No isolation, hard to query, manual serialization
4. **External Services**: Adds dependencies, complexity

**Pain Points**:
- Quote-db plugin spec assumes direct SQLite access (monolithic pattern)
- Trivia plugin spec has no persistence (in-memory only)
- No standard way for plugins to store configuration
- Every plugin would need to reinvent storage logic

### 1.2 Why KV Storage First?

**Progressive Complexity Philosophy**:
- **Sprint A (KV)**: Simple key/value pairs - easiest to implement, test, understand
- **Sprint B (Rows)**: Structured CRUD - builds on KV patterns
- **Sprint C (Reference)**: Real plugins - validates KV + Row APIs
- **Sprint D (SQL)**: Power user escape hatch - completes the system

**KV Storage Use Cases** (80% of plugin needs):
- Configuration values (`{"theme": "dark", "cooldown": 30}`)
- Feature flags (`{"trivia_enabled": true}`)
- Simple counters (`{"message_count": 42}`)
- Session tokens (`{"session_xyz": "token_abc", "ttl": 1800}`)
- Temporary state (`{"game_active": true, "turn": "player1"}`)

### 1.3 Why Not Start with SQL?

**Reasons to Start Simple**:
1. **Validation**: KV proves the NATS-to-database pattern works
2. **Isolation Testing**: Easier to test namespace scoping with simple keys
3. **Performance Baseline**: Establish latency/throughput expectations
4. **Developer Experience**: Learn what makes a good plugin storage API
5. **Low Risk**: Small surface area, easy to refactor if needed

---

## 2. Goals & Non-Goals

### 2.1 Primary Goals

**PG-001: Simple Key-Value API**
- Plugins can set, get, delete, and list keys via NATS subjects
- Values are JSON-serializable (strings, numbers, booleans, objects, arrays)
- Operations complete in <10ms p95 latency

**PG-002: Plugin Isolation**
- Each plugin's keys are namespaced (plugin "foo" cannot see plugin "bar" keys)
- Plugin name extracted from NATS subject path automatically
- Database enforces isolation at query level

**PG-003: TTL Support**
- Keys can have optional time-to-live (seconds)
- Expired keys return "not found" automatically
- Background cleanup task removes expired keys periodically

**PG-004: Database Portability**
- Works with SQLite (dev/test) and PostgreSQL (prod)
- Same API behavior regardless of backend
- SQLAlchemy ORM handles dialect differences

**PG-005: Production Ready**
- 85%+ test coverage (unit + integration)
- Error handling for all edge cases
- Observability (logging, metrics hooks)
- Value size limits (prevent abuse)

### 2.2 Secondary Goals

**SG-001: Performance**
- Support 1000+ operations/second
- Background cleanup handles 10k expired keys in <1 second
- Minimal memory footprint (<50MB for 100k keys)

**SG-002: Developer Experience**
- Clear error messages with error codes
- Copy-paste examples in documentation
- Type hints for all Python APIs

**SG-003: Operational Excellence**
- Graceful degradation on database errors
- No crashes from malformed requests
- Audit trail in logs

### 2.3 Non-Goals (Deferred to Later Sprints)

**NG-001**: Structured/relational data → Sprint B (Row Operations)
**NG-002**: Atomic operations ($inc, $max) → Sprint B  
**NG-003**: Complex queries/filters → Sprint B  
**NG-004**: Schema migrations → Sprint B  
**NG-005**: Parameterized SQL → Sprint D  
**NG-006**: Reference plugins → Sprint C  
**NG-007**: Inspector plugin integration → Sprint C  
**NG-008**: Cross-plugin data sharing → Never (intentional isolation)  
**NG-009**: Encryption at rest → Future (v2)  
**NG-010**: Key versioning/history → Future (v2)  

---

## 3. Success Metrics

### 3.1 User-Centric Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Time to first KV operation | <10 minutes | From plugin skeleton to working set/get |
| Plugin author satisfaction | "Simple & intuitive" | Qualitative feedback |
| Zero plugins bypassing KV API | 100% | Code review / audit |
| Documentation clarity | Self-service | No questions on basic usage |

### 3.2 Technical Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| KV operation latency (p50) | <5ms | Performance test suite |
| KV operation latency (p95) | <10ms | Performance test suite |
| KV operation latency (p99) | <25ms | Performance test suite |
| Throughput | ≥1000 ops/sec | Load test with 10 concurrent plugins |
| Test coverage | ≥85% | pytest-cov |
| Error rate (normal operation) | <0.1% | Integration test statistics |
| TTL cleanup performance | <1 sec for 10k keys | Dedicated performance test |
| Memory footprint | <50MB | Process memory monitoring |

### 3.3 Quality Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Zero cross-plugin data leaks | 100% | Isolation security tests |
| Zero SQL injection vulnerabilities | 100% | Security audit + tests |
| All error cases handled | 100% | Error path coverage |
| Zero database corruption cases | 100% | Stress testing |

---

## 4. User Personas

### 4.1 Primary Persona: Internal Plugin Author

**Name**: Alex (You / Core Team)  
**Background**: Deep Rosey knowledge, Python expert, wrote plugin system  
**Goals**:
- Build stateful plugins (quote-db, trivia, games)
- Prototype quickly without fighting infrastructure
- Ship production-ready code

**Pain Points** (Current):
- No standard way to persist plugin state
- Direct SQLite access breaks isolation
- In-memory state lost on crashes

**Success Scenario** (After Sprint A):
```python
# In trivia plugin
async def store_game_state(self, game_id, state):
    await self.nats.request(
        'db.kv.trivia.set',
        json.dumps({
            'key': f'game_{game_id}',
            'value': state,
            'ttl': 1800  # 30 minutes
        }).encode()
    )

async def load_game_state(self, game_id):
    response = await self.nats.request(
        'db.kv.trivia.get',
        json.dumps({'key': f'game_{game_id}'}).encode()
    )
    data = json.loads(response.data)
    return data['value'] if data['exists'] else None
```

**Satisfaction Criteria**:
- ✅ Works on first try
- ✅ No configuration needed
- ✅ Obvious how to debug
- ✅ Fast enough to not worry about

### 4.2 Secondary Persona: External Plugin Contributor

**Name**: Jordan (Future)  
**Background**: Python developer, new to Rosey, wants to contribute plugin  
**Goals**:
- Understand plugin system quickly
- Use standard patterns
- Get code merged

**Pain Points** (Potential):
- NATS communication unfamiliar
- Unclear how to persist data
- Fear of breaking things

**Success Scenario**:
- Reads "Plugin Storage Guide" (Sprint C)
- Copies KV example from docs
- Plugin works identically in dev (SQLite) and prod (PostgreSQL)
- No surprises during code review

**Satisfaction Criteria**:
- ✅ Documentation answers all questions
- ✅ Examples are copy-paste ready
- ✅ Error messages are helpful
- ✅ No "magic" or hidden configuration

### 4.3 Tertiary Persona: Bot Operator / SRE

**Name**: Sam  
**Background**: Manages production Rosey deployment  
**Goals**:
- Stable bot (no crashes from plugins)
- Observable system (understand what's happening)
- Predictable performance

**Pain Points** (Potential):
- Plugin storage issues cause downtime
- Can't tell which plugin is causing problems
- No way to inspect plugin data

**Success Scenario**:
- Logs show clear KV operations by plugin
- Database tables are inspectable (SQL queries work)
- Cleanup task runs automatically (no manual intervention)
- Errors are logged with context

**Satisfaction Criteria**:
- ✅ No mystery errors
- ✅ Can debug plugin issues
- ✅ System self-heals (TTL cleanup)
- ✅ Performance is predictable

---

## 5. User Stories

### 5.1 Core Functionality Stories

#### **US-001: Store Simple Value**
**As a** plugin author  
**I want to** store a simple value (string, number, boolean)  
**So that** my plugin remembers settings across restarts

**Acceptance Criteria**:
- [ ] I can publish to `db.kv.<my-plugin>.set` with `{key: "setting_name", value: "value"}`
- [ ] Value is stored in `plugin_kv_storage` table with plugin_name scoped
- [ ] Subsequent `db.kv.<my-plugin>.get` with `{key: "setting_name"}` returns the value
- [ ] Value persists across database service restart
- [ ] Setting same key again updates value (not creates duplicate)
- [ ] Value type is preserved (number stays number, not string)

**Example**:
```python
# Store theme preference
await nats.publish('db.kv.my-plugin.set', 
    json.dumps({'key': 'theme', 'value': 'dark'}).encode())

# Later retrieve it
response = await nats.request('db.kv.my-plugin.get',
    json.dumps({'key': 'theme'}).encode())
data = json.loads(response.data)
assert data['exists'] == True
assert data['value'] == 'dark'
```

**Testing**:
- Unit test: `test_kv_set_and_get_string_value()`
- Unit test: `test_kv_set_and_get_number_value()`
- Unit test: `test_kv_set_and_get_boolean_value()`
- Unit test: `test_kv_set_updates_existing_key()`
- Integration test: `test_kv_end_to_end_via_nats()`

---

#### **US-002: Store Complex Object**
**As a** plugin author  
**I want to** store complex objects (dicts, arrays)  
**So that** I can persist structured configuration

**Acceptance Criteria**:
- [ ] I can store nested objects: `{key: "config", value: {theme: "dark", timeout: 30}}`
- [ ] I can store arrays: `{key: "items", value: ["a", "b", "c"]}`
- [ ] Retrieved value matches stored value exactly (deep equality)
- [ ] JSON serialization handles None/null correctly
- [ ] JSON serialization handles Unicode correctly

**Example**:
```python
# Store complex config
config = {
    'theme': 'dark',
    'cooldown': 30,
    'enabled_features': ['trivia', 'quotes'],
    'admin_users': ['groberts', 'moderator']
}
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'config', 'value': config}).encode())

# Retrieve and verify
response = await nats.request('db.kv.my-plugin.get',
    json.dumps({'key': 'config'}).encode())
data = json.loads(response.data)
assert data['value'] == config  # Deep equality
```

**Testing**:
- Unit test: `test_kv_store_nested_object()`
- Unit test: `test_kv_store_array()`
- Unit test: `test_kv_store_mixed_types()`
- Unit test: `test_kv_unicode_handling()`
- Unit test: `test_kv_null_handling()`

---

#### **US-003: Store Counter**
**As a** plugin author  
**I want to** store numeric counters  
**So that** I can track events without in-memory state

**Acceptance Criteria**:
- [ ] I can store number: `{key: "count", value: 0}`
- [ ] I can retrieve, increment, and store back
- [ ] Number type is preserved (not converted to string)
- [ ] Works with integers and floats
- [ ] _(Note: Atomic $inc comes in Sprint B)_

**Example**:
```python
# Initialize counter
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'message_count', 'value': 0}).encode())

# Increment (not atomic in Sprint A)
response = await nats.request('db.kv.my-plugin.get',
    json.dumps({'key': 'message_count'}).encode())
count = json.loads(response.data)['value']
count += 1
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'message_count', 'value': count}).encode())
```

**Testing**:
- Unit test: `test_kv_counter_workflow()`
- Unit test: `test_kv_float_values()`
- Integration test: `test_kv_concurrent_counter_updates()`

---

#### **US-004: Store Temporary State with TTL**
**As a** plugin author  
**I want to** store temporary state that expires automatically  
**So that** I don't have to manually clean up session data

**Acceptance Criteria**:
- [ ] I can set TTL: `{key: "session_xyz", value: "data", ttl: 1800}` (30 minutes)
- [ ] Getting key before expiration returns value
- [ ] Getting key after expiration returns `{exists: false}`
- [ ] Expired keys are excluded from list operations
- [ ] Background cleanup removes expired keys within 5 minutes
- [ ] TTL=null or omitted means no expiration

**Example**:
```python
# Store game session with 30-minute timeout
await nats.publish('db.kv.trivia.set',
    json.dumps({
        'key': 'game_abc123',
        'value': {'turn': 'player1', 'score': 0},
        'ttl': 1800  # 30 minutes
    }).encode())

# 29 minutes later - still exists
response = await nats.request('db.kv.trivia.get',
    json.dumps({'key': 'game_abc123'}).encode())
assert json.loads(response.data)['exists'] == True

# 31 minutes later - expired
response = await nats.request('db.kv.trivia.get',
    json.dumps({'key': 'game_abc123'}).encode())
assert json.loads(response.data)['exists'] == False
```

**Testing**:
- Unit test: `test_kv_set_with_ttl()`
- Unit test: `test_kv_get_expired_key_returns_false()`
- Unit test: `test_kv_list_excludes_expired()`
- Unit test: `test_kv_cleanup_removes_expired()`
- Integration test: `test_kv_ttl_workflow()`

---

#### **US-005: List Plugin Keys**
**As a** plugin author  
**I want to** list all my plugin's keys (optionally filtered by prefix)  
**So that** I can discover what data my plugin has stored

**Acceptance Criteria**:
- [ ] I can call `db.kv.<my-plugin>.list` with no params to get all keys
- [ ] I can call with `{prefix: "config_"}` to filter keys
- [ ] Response is `{keys: ["key1", "key2"], count: 2}`
- [ ] Expired keys are excluded automatically
- [ ] Empty result returns `{keys: [], count: 0}`
- [ ] Optional limit parameter prevents huge responses

**Example**:
```python
# Store multiple keys
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'config_theme', 'value': 'dark'}).encode())
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'config_timeout', 'value': 30}).encode())
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'state_active', 'value': True}).encode())

# List all keys
response = await nats.request('db.kv.my-plugin.list',
    json.dumps({}).encode())
data = json.loads(response.data)
assert set(data['keys']) == {'config_theme', 'config_timeout', 'state_active'}

# List only config keys
response = await nats.request('db.kv.my-plugin.list',
    json.dumps({'prefix': 'config_'}).encode())
data = json.loads(response.data)
assert set(data['keys']) == {'config_theme', 'config_timeout'}
```

**Testing**:
- Unit test: `test_kv_list_all_keys()`
- Unit test: `test_kv_list_with_prefix()`
- Unit test: `test_kv_list_empty_result()`
- Unit test: `test_kv_list_excludes_expired()`
- Unit test: `test_kv_list_with_limit()`

---

#### **US-006: Delete Key**
**As a** plugin author  
**I want to** delete keys I no longer need  
**So that** I can clean up old state

**Acceptance Criteria**:
- [ ] I can call `db.kv.<my-plugin>.delete` with `{key: "name"}`
- [ ] Key is removed from database
- [ ] Subsequent get returns `{exists: false}`
- [ ] Deleting non-existent key succeeds (idempotent)
- [ ] Response indicates whether key existed: `{deleted: true/false}`

**Example**:
```python
# Store and then delete
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'temp_data', 'value': 'xyz'}).encode())

await nats.publish('db.kv.my-plugin.delete',
    json.dumps({'key': 'temp_data'}).encode())

# Verify deleted
response = await nats.request('db.kv.my-plugin.get',
    json.dumps({'key': 'temp_data'}).encode())
assert json.loads(response.data)['exists'] == False

# Delete again - still succeeds (idempotent)
await nats.publish('db.kv.my-plugin.delete',
    json.dumps({'key': 'temp_data'}).encode())  # No error
```

**Testing**:
- Unit test: `test_kv_delete_existing_key()`
- Unit test: `test_kv_delete_nonexistent_key()`
- Unit test: `test_kv_delete_idempotence()`
- Integration test: `test_kv_delete_via_nats()`

---

### 5.2 Security & Isolation Stories

#### **US-007: Plugin Isolation Enforced**
**As a** plugin author  
**I want** confidence that my data is isolated from other plugins  
**So that** I can trust the system's security

**Acceptance Criteria**:
- [ ] Plugin "foo" cannot read plugin "bar" keys
- [ ] Plugin "foo" cannot write to plugin "bar" namespace
- [ ] Plugin "foo" cannot list plugin "bar" keys
- [ ] Plugin name extracted from NATS subject automatically
- [ ] Database queries always filter by plugin_name
- [ ] Isolation enforced at database layer (not just API)

**Example**:
```python
# Plugin "quote-db" stores a key
await nats.publish('db.kv.quote-db.set',
    json.dumps({'key': 'last_id', 'value': 42}).encode())

# Plugin "trivia" tries to read it
response = await nats.request('db.kv.trivia.get',
    json.dumps({'key': 'last_id'}).encode())
data = json.loads(response.data)
assert data['exists'] == False  # Cannot see other plugin's keys

# Plugin "trivia" stores its own "last_id"
await nats.publish('db.kv.trivia.set',
    json.dumps({'key': 'last_id', 'value': 99}).encode())

# Both plugins see their own values
response = await nats.request('db.kv.quote-db.get',
    json.dumps({'key': 'last_id'}).encode())
assert json.loads(response.data)['value'] == 42

response = await nats.request('db.kv.trivia.get',
    json.dumps({'key': 'last_id'}).encode())
assert json.loads(response.data)['value'] == 99
```

**Testing**:
- Security test: `test_plugin_isolation_get()`
- Security test: `test_plugin_isolation_list()`
- Security test: `test_plugin_isolation_delete()`
- Security test: `test_plugin_cannot_forge_plugin_name()`

---

#### **US-008: Value Size Limits Enforced**
**As a** database administrator  
**I want** value size limits enforced  
**So that** plugins cannot degrade database performance

**Acceptance Criteria**:
- [ ] Values larger than 64KB rejected with error `VALUE_TOO_LARGE`
- [ ] Error message includes actual size and limit
- [ ] Size measured after JSON serialization
- [ ] Limit documented in plugin storage guide
- [ ] Small values (<64KB) work normally

**Example**:
```python
# Small value - works fine
await nats.publish('db.kv.my-plugin.set',
    json.dumps({'key': 'small', 'value': 'x' * 100}).encode())

# Large value - rejected
huge_value = 'x' * 100000  # 100KB
response = await nats.request('db.kv.my-plugin.set',
    json.dumps({'key': 'huge', 'value': huge_value}).encode(),
    timeout=5)
data = json.loads(response.data)
assert data['success'] == False
assert data['error_code'] == 'VALUE_TOO_LARGE'
assert '64' in data['message']  # Mentions limit
```

**Testing**:
- Unit test: `test_kv_value_size_limit_enforced()`
- Unit test: `test_kv_size_error_message()`
- Unit test: `test_kv_size_at_boundary()`

---

### 5.3 Developer Experience Stories

#### **US-009: Clear Error Messages**
**As a** plugin author  
**I want** clear error messages when operations fail  
**So that** I can debug issues quickly

**Acceptance Criteria**:
- [ ] Malformed JSON returns `INVALID_JSON` with parse error
- [ ] Missing required fields return `MISSING_FIELD` with field name
- [ ] Invalid plugin name returns `INVALID_PLUGIN_NAME`
- [ ] Database errors return `DATABASE_ERROR` with safe message
- [ ] All errors include human-readable `message` field
- [ ] All responses include `success: true/false`

**Example**:
```python
# Missing key field
response = await nats.request('db.kv.my-plugin.get',
    json.dumps({'wrong_field': 'value'}).encode())
data = json.loads(response.data)
assert data['success'] == False
assert data['error_code'] == 'MISSING_FIELD'
assert 'key' in data['message'].lower()

# Invalid JSON
response = await nats.request('db.kv.my-plugin.get',
    b'not json at all')
data = json.loads(response.data)
assert data['error_code'] == 'INVALID_JSON'
```

**Testing**:
- Unit test: `test_kv_error_invalid_json()`
- Unit test: `test_kv_error_missing_field()`
- Unit test: `test_kv_error_value_too_large()`
- Unit test: `test_kv_error_database_failure()`

---

#### **US-010: Works Identically in SQLite and PostgreSQL**
**As a** plugin developer  
**I want** identical behavior in dev (SQLite) and prod (PostgreSQL)  
**So that** I don't encounter surprises in production

**Acceptance Criteria**:
- [ ] Same API for SQLite and PostgreSQL
- [ ] Same JSON serialization behavior
- [ ] Same TTL expiration semantics
- [ ] Same error messages
- [ ] Tests pass with both databases

**Example**:
```python
# Development (SQLite)
db_dev = BotDatabase('sqlite+aiosqlite:///test.db')
await db_dev.kv_set('my-plugin', 'key', {'value': 42})
result = await db_dev.kv_get('my-plugin', 'key')
assert result['value'] == 42

# Production (PostgreSQL)
db_prod = BotDatabase('postgresql+asyncpg://user:pass@host/db')
await db_prod.kv_set('my-plugin', 'key', {'value': 42})
result = await db_prod.kv_get('my-plugin', 'key')
assert result['value'] == 42  # Identical behavior
```

**Testing**:
- Parameterized tests run against both SQLite and PostgreSQL
- CI/CD tests against PostgreSQL (if available)

---

#### **US-011: Observability for Operators**
**As an** operator  
**I want** to see KV operations in logs  
**So that** I can debug plugin issues

**Acceptance Criteria**:
- [ ] Each operation logs at DEBUG: plugin, operation, key
- [ ] Errors log at ERROR with full traceback
- [ ] Slow operations (>100ms) log at WARNING
- [ ] Logs use structured format
- [ ] Cleanup task logs count of expired keys

**Example Log Output**:
```
2025-11-22 10:30:45 DEBUG [db_service] KV set: plugin=trivia key=game_123 size=45
2025-11-22 10:30:46 DEBUG [db_service] KV get: plugin=trivia key=game_123 hit=true
2025-11-22 10:30:50 ERROR [db_service] KV set failed: plugin=broken-plugin error=DATABASE_ERROR
2025-11-22 10:35:00 INFO [db_service] KV cleanup: removed 42 expired keys in 0.15s
```

**Testing**:
- Unit test: `test_kv_logging_set_operation()`
- Unit test: `test_kv_logging_error_cases()`
- Integration test: `test_kv_cleanup_logging()`

---

#### **US-012: TTL Cleanup Runs Automatically**
**As an** operator  
**I want** expired keys cleaned up automatically  
**So that** storage doesn't grow unbounded

**Acceptance Criteria**:
- [ ] Background task runs every 5 minutes
- [ ] Deletes all rows where `expires_at < now()`
- [ ] Logs count of deleted keys
- [ ] Handles database errors gracefully
- [ ] Does not block normal KV operations
- [ ] Performance: <1 second with 10k expired keys

**Example**:
```python
# Cleanup task runs automatically in DatabaseService
async def _kv_cleanup_task(self):
    while self._running:
        try:
            await asyncio.sleep(300)  # 5 minutes
            deleted = await self.db.kv_cleanup_expired()
            if deleted > 0:
                self.logger.info(f"KV cleanup: removed {deleted} expired keys")
        except Exception as e:
            self.logger.error(f"KV cleanup failed: {e}")
```

**Testing**:
- Unit test: `test_kv_cleanup_removes_expired()`
- Unit test: `test_kv_cleanup_performance()`
- Integration test: `test_kv_cleanup_task_runs()`

---

## 6. Technical Architecture

### 6.1 Event-Driven Architecture Philosophy

**Rosey uses a pure event-driven architecture** with three core principles:

1. **No Direct Calls**: Components communicate exclusively via NATS events
2. **Service Isolation**: Each service (database, channel connector, plugins) runs independently
3. **Message Passing**: All coordination happens through the NATS message bus

**Core Services**:
- **Bot Marshal** (`lib/bot.py`): Central coordinator, routes messages between services
- **Database Service** (`common/database_service.py`): Manages all database operations via NATS
- **Channel Connector** (`lib/socket_io.py`): Cytube protocol adapter, publishes/subscribes channel events
- **Plugins** (`bot/rosey/`, `examples/*`): Business logic, publish commands via NATS

**Key Pattern**: Plugins never call database/channel methods directly. They publish events, services respond.

### 6.2 System Context

```
                    ┌──────────────────────────────────────┐
                    │         NATS Event Bus               │
                    │  (All communication via messages)    │
                    └──────────────────────────────────────┘
                            ↑           ↑           ↑
                            │           │           │
        ┌───────────────────┘           │           └────────────────┐
        │                               │                            │
        │ Publishes:                    │ Publishes:                 │ Publishes:
        │ - db.kv.<plugin>.set          │ - channel.say              │ - channel.message
        │ - db.kv.<plugin>.get          │ - channel.action           │ - channel.user_joined
        │ - db.kv.<plugin>.delete       │                            │
        │ - db.kv.<plugin>.list         │                            │
        │                               │                            │
┌───────┴─────────┐          ┌──────────┴──────────┐      ┌─────────┴──────────┐
│   Plugin        │          │  Database Service    │      │ Channel Connector  │
│   (trivia,      │          │  (database_service)  │      │  (socket_io)       │
│    rosey, etc.) │          │                      │      │                    │
│                 │          │ Subscribes:          │      │ Subscribes:        │
│ - Business      │          │ - db.kv.*            │      │ - channel.say      │
│   logic         │          │ - db.row.*           │      │ - channel.action   │
│ - Publishes     │          │ - db.schema.*        │      │                    │
│   commands      │          │                      │      │ - Cytube protocol  │
│ - NO direct     │          │ - SQLAlchemy ORM     │      │ - Publishes events │
│   DB/channel    │          │ - Namespace isolation│      │                    │
│   access        │          │ - TTL cleanup        │      │                    │
└─────────────────┘          └──────────────────────┘      └────────────────────┘
                                      │                              │
                                      │ Direct access                │ Socket.IO
                                      ↓                              ↓
                             ┌────────────────┐            ┌─────────────────┐
                             │  SQLite/       │            │  Cytube Server  │
                             │  PostgreSQL    │            │                 │
                             │                │            │  (external)     │
                             │ plugin_kv_     │            └─────────────────┘
                             │   storage      │
                             └────────────────┘
```

**Flow Example** (Plugin wants to say something in channel):
```
1. Plugin publishes:     rosey.channel.say {"text": "Hello!"}
2. Bot Marshal receives: Routes to channel service
3. Channel Connector:    Receives event, formats for Cytube
4. Cytube:               Receives socket.io message, displays in channel
```

**Flow Example** (Plugin stores data):
```
1. Plugin publishes:     rosey.db.kv.trivia.set {"key": "score", "value": 100}
2. Database Service:     Receives event, validates, stores in SQLite
3. Database Service:     Publishes response (if requested)
4. Plugin:               Receives confirmation
```

### 6.3 Component Responsibilities

#### 6.3.1 Plugin (e.g., `trivia-plugin.py`)
**Role**: Business logic executor

**Does**:
- Publishes KV requests to `rosey.db.kv.<plugin>.*` subjects
- Listens for relevant domain events
- Handles responses asynchronously
- Implements plugin-specific features

**Does NOT**:
- Call database methods directly (uses NATS)
- Call channel methods directly (uses NATS)
- Know about database schema
- Access other plugin data

#### 6.3.2 Database Service (`common/database_service.py`)
**Role**: Database request handler (NATS listener)

**Does**:
- Subscribes to `db.kv.*`, `db.row.*`, `db.schema.*` subjects
- Extracts plugin name from subject path (enforces namespace isolation)
- Validates request payloads (JSON, required fields)
- Delegates to `BotDatabase` for actual database operations
- Returns responses via NATS reply subjects
- Handles errors gracefully (logs, returns structured errors)
- Runs background TTL cleanup task

**Does NOT**:
- Implement database logic (delegates to BotDatabase)
- Know about plugin business logic
- Make direct calls to plugins

**Naming Note**: This is a **service** (NATS listener), not a client wrapper. Plugins interact with it via NATS events, not direct method calls.

#### 6.3.3 BotDatabase (`common/database.py`)
**Role**: Database operations implementation

**Does**:
- Implements KV storage logic (`kv_set`, `kv_get`, `kv_delete`, `kv_list`)
- Uses SQLAlchemy ORM for database operations
- Enforces plugin namespace isolation at query level (WHERE plugin_name=...)
- Handles TTL expiration checks
- Returns structured results (dicts, not ORM objects)
- Manages database connections, transactions

**Does NOT**:
- Listen to NATS (called by DatabaseService)
- Know about NATS subjects
- Implement business logic

**Naming Note**: This is the **database implementation layer**. Could be renamed `DatabaseEngine` or `DatabaseImpl` to clarify it's not a service, but we'll keep existing name for now.

#### 6.3.4 Optional: DatabaseClient (Plugin-Side Wrapper)
**Role**: Convenience wrapper for plugins (future enhancement)

**Example**:
```python
# Without wrapper (current):
response = await nats.request('rosey.db.kv.trivia.get', json.dumps({"key": "score"}))
value = json.loads(response.data)["value"]

# With wrapper (future):
db = DatabaseClient(nats_client, plugin_name="trivia")
value = await db.kv.get("score")  # Simpler API
```

**Decision**: Not implemented in Sprint 12 (keep it simple). Plugins use NATS directly. Can add in Sprint B if needed.

#### 6.3.5 PluginKVStorage (`common/models.py`)
**Role**: SQLAlchemy ORM model

**Does**:
- Defines table schema
- Handles JSON serialization/deserialization
- Provides SQLAlchemy query interface

#### 6.3.6 Database (SQLite or PostgreSQL)
**Role**: Data persistence

**Does**:
- Stores actual data
- Managed by SQLAlchemy/Alembic migrations
- Enforces constraints (primary key, indexes, foreign keys)

### 6.4 Why This Architecture?

**Benefits**:
1. **Loose Coupling**: Services don't depend on each other's implementation
2. **Scalability**: Can run services on different machines, scale independently
3. **Testability**: Mock NATS messages instead of complex service dependencies
4. **Resilience**: Service crashes don't cascade (messages queue in NATS)
5. **Observability**: All communication visible via NATS monitoring
6. **Hot Reload**: Restart services without restarting entire bot

**Tradeoffs**:
- More complex for simple operations (but consistent pattern scales)
- Requires NATS infrastructure (already in place from Sprint 6a)
- Message-based patterns require more code than direct function calls

**Performance Note**: Testing shows NATS architecture is **5% faster** than direct database calls in burst conditions (1k messages/sec), likely due to NATS's efficient message queuing and the Database Service's ability to batch operations. The event-driven architecture provides performance benefits, not penalties.

### 6.5 Data Flow: Set Operation

**Scenario**: Trivia plugin stores game state

```text
┌────────┐                    ┌──────────────┐                  ┌─────────────┐
│ Plugin │                    │  Database    │                  │ BotDatabase │
│        │                    │  Service     │                  │             │
└───┬────┘                    └──────┬───────┘                  └──────┬──────┘
    │                                │                                 │
    │ 1. Publish NATS message:       │                                 │
    │    Subject: rosey.db.kv.trivia.set                               │
    │    Payload: {                  │                                 │
    │      "key": "game_123",        │                                 │
    │      "value": {"players": [...], "round": 2},                    │
    │      "ttl": 1800               │                                 │
    │    }                           │                                 │
    ├───────────────────────────────>│                                 │
    │                                │                                 │
    │                                │ 2. Receive message:             │
    │                                │    - Extract plugin: "trivia"   │
    │                                │    - Parse JSON payload         │
    │                                │    - Validate: key, value exist │
    │                                │    - Calculate expires_at       │
    │                                │                                 │
    │                                │ 3. Call BotDatabase:            │
    │                                │    kv_set(plugin="trivia",      │
    │                                │            key="game_123",      │
    │                                │            value={...},         │
    │                                │            expires_at=...)      │
    │                                ├────────────────────────────────>│
    │                                │                                 │
    │                                │                            4. Execute:
    │                                │                               INSERT OR UPDATE
    │                                │                               plugin_kv_storage
    │                                │                               WHERE plugin_name='trivia'
    │                                │                               AND key='game_123'
    │                                │                                 │
    │                                │<────────────────────────────────┤
    │                                │ 5. Return: {"success": true}    │
    │                                │                                 │
    │ 6. Publish response (optional):│                                 │
    │    Subject: _INBOX.xxx (reply) │                                 │
    │    Payload: {"success": true}  │                                 │
    │<───────────────────────────────┤                                 │
    │                                │                                 │
```

**Code Example** (Plugin side):
```python
# Fire-and-forget (no response needed)
await nats.publish('rosey.db.kv.trivia.set', json.dumps({
    "key": "game_123",
    "value": {"players": ["alice", "bob"], "round": 2},
    "ttl": 1800
}))

# Request-reply (wait for confirmation)
response = await nats.request('rosey.db.kv.trivia.set', json.dumps({
    "key": "game_123",
    "value": {"players": ["alice", "bob"], "round": 2},
    "ttl": 1800
}), timeout=2.0)
result = json.loads(response.data)  # {"success": true}
```

### 6.6 Data Flow: Get Operation

**Scenario**: Trivia plugin retrieves game state

```text
┌────────┐                    ┌──────────────┐                  ┌─────────────┐
│ Plugin │                    │  Database    │                  │ BotDatabase │
│        │                    │  Service     │                  │             │
└───┬────┘                    └──────┬───────┘                  └──────┬──────┘
    │                                │                                 │
    │ 1. Request (NATS):             │                                 │
    │    Subject: rosey.db.kv.trivia.get                               │
    │    Payload: {"key": "game_123"}│                                 │
    │    Reply-To: _INBOX.abc123     │                                 │
    ├───────────────────────────────>│                                 │
    │                                │                                 │
    │                                │ 2. Receive message:             │
    │                                │    - Extract plugin: "trivia"   │
    │                                │    - Parse: {"key": "game_123"} │
    │                                │                                 │
    │                                │ 3. Call BotDatabase:            │
    │                                │    kv_get(plugin="trivia",      │
    │                                │            key="game_123")      │
    │                                ├────────────────────────────────>│
    │                                │                                 │
    │                                │                            4. Execute:
    │                                │                               SELECT value, expires_at
    │                                │                               FROM plugin_kv_storage
    │                                │                               WHERE plugin_name='trivia'
    │                                │                               AND key='game_123'
    │                                │                               AND (expires_at IS NULL
    │                                │                                    OR expires_at > now())
    │                                │                                 │
    │                                │<────────────────────────────────┤
    │                                │ 5. Return:                      │
    │                                │    {"exists": true,             │
    │                                │     "value": {...}}             │
    │                                │    OR                           │
    │                                │    {"exists": false}            │
    │                                │                                 │
    │ 6. Publish to reply subject:   │                                 │
    │    Subject: _INBOX.abc123      │                                 │
    │    Payload: {"exists": true, "value": {...}}                     │
    │<───────────────────────────────┤                                 │
    │                                │                                 │
    │ 7. Process response            │                                 │
```

**Code Example** (Plugin side):
```python
# Request-reply pattern (always used for GET)
response = await nats.request('rosey.db.kv.trivia.get', json.dumps({
    "key": "game_123"
}), timeout=2.0)

result = json.loads(response.data)
if result["exists"]:
    game_state = result["value"]
    print(f"Game state: {game_state}")
else:
    print("Game not found (expired or never existed)")
```

### 6.7 Namespace Isolation Enforcement

**Critical Security Feature**: Plugins can ONLY access their own namespace.

**How it works**:
1. Plugin publishes to: `rosey.db.kv.{plugin_name}.{operation}`
2. Database Service extracts `plugin_name` from subject path
3. BotDatabase adds `WHERE plugin_name = '{plugin_name}'` to ALL queries
4. Impossible for plugin to access other plugin data (enforced at DB layer)

**Example** (Trivia plugin tries to access Quote plugin data):
```python
# Trivia plugin attempts:
response = await nats.request('rosey.db.kv.quote.get', json.dumps({
    "key": "favorite_quote"
}))

# DatabaseService extracts plugin_name from subject: "quote"
# BotDatabase queries:
#   SELECT * FROM plugin_kv_storage
#   WHERE plugin_name = 'quote' AND key = 'favorite_quote'
#
# BUT: Plugin NATS permissions should prevent this!
# Best practice: Configure NATS ACLs so trivia can only publish to:
#   rosey.db.kv.trivia.*
```

**Defense in Depth**:
1. **NATS ACLs** (recommended): Restrict plugin NATS permissions to own namespace
2. **Subject Validation** (Database Service): Reject if subject doesn't match expected pattern
3. **Query Isolation** (BotDatabase): Always filter by plugin_name from subject

---

## 7. Database Schema Design

### 7.1 Table: `plugin_kv_storage`

**Purpose**: Store all plugin key-value pairs with optional TTL support

**Schema** (SQLAlchemy Model):

```python
# common/models.py

from sqlalchemy import Column, String, Text, TIMESTAMP, Index
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import json

class PluginKVStorage(Base):
    """
    Key-Value storage for plugins with TTL support.
    
    Each plugin has its own isolated namespace identified by plugin_name.
    Keys are unique within a plugin namespace but can overlap across plugins.
    Values are stored as JSON text for maximum flexibility.
    """
    __tablename__ = 'plugin_kv_storage'
    
    # Composite Primary Key
    plugin_name = Column(String(100), primary_key=True, nullable=False,
                        doc="Plugin identifier (e.g., 'trivia', 'quote-db')")
    key = Column(String(255), primary_key=True, nullable=False,
                doc="Key name within plugin namespace")
    
    # Value (JSON serialized)
    value = Column(Text, nullable=False,
                  doc="JSON-serialized value (string, number, object, array)")
    
    # TTL Support
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True,
                       doc="Expiration timestamp (NULL = never expires)")
    
    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), nullable=False,
                       server_default=func.now(),
                       doc="When key was first created")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False,
                       server_default=func.now(),
                       onupdate=func.now(),
                       doc="When key was last updated")
    
    # Indexes
    __table_args__ = (
        Index('idx_kv_expires_at', 'expires_at',
              postgresql_where=(expires_at != None)),  # Partial index for cleanup
        Index('idx_kv_plugin_prefix', 'plugin_name', 'key'),  # For prefix queries
    )
    
    def __repr__(self):
        return f"<PluginKVStorage(plugin={self.plugin_name}, key={self.key})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if key is expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def get_value(self):
        """Deserialize JSON value"""
        return json.loads(self.value)
    
    def set_value(self, value_obj):
        """Serialize value to JSON"""
        self.value = json.dumps(value_obj)
```

**SQL Schema** (for reference):

```sql
CREATE TABLE plugin_kv_storage (
    plugin_name VARCHAR(100) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (plugin_name, key)
);

-- Index for TTL cleanup queries
CREATE INDEX idx_kv_expires_at ON plugin_kv_storage(expires_at)
    WHERE expires_at IS NOT NULL;

-- Index for prefix searches
CREATE INDEX idx_kv_plugin_prefix ON plugin_kv_storage(plugin_name, key);
```

### 7.2 Schema Design Decisions

**Composite Primary Key** (plugin_name, key):
- **Pro**: Ensures uniqueness within plugin namespace
- **Pro**: Efficient queries (single index lookup)
- **Pro**: Natural data model (plugins own their keys)
- **Con**: No auto-increment ID (not needed for KV)

**JSON in TEXT Column**:
- **Pro**: Maximum flexibility (any JSON type)
- **Pro**: Works identically in SQLite and PostgreSQL
- **Pro**: SQLAlchemy handles serialization
- **Con**: No JSON validation at DB level (handled in Python)
- **Con**: No JSON field queries (Sprint D adds SQL for that)

**Nullable expires_at**:
- **Pro**: NULL = never expires (most keys)
- **Pro**: Partial index excludes NULL (faster cleanup)
- **Pro**: TIMESTAMP WITH TIME ZONE handles timezones correctly

**Timestamps** (created_at, updated_at):
- **Pro**: Audit trail (when was key created/modified)
- **Pro**: Useful for debugging
- **Pro**: server_default ensures values even if Python doesn't set

### 7.3 Index Strategy

**Primary Key Index** (plugin_name, key):
- Automatically created
- Used for: Get, Set, Delete operations
- Cardinality: High (unique per row)

**Expiration Index** (idx_kv_expires_at):
- Partial index: `WHERE expires_at IS NOT NULL`
- Used for: TTL cleanup queries
- Cardinality: Low (few expired keys at any time)
- Performance: <1 second to delete 10k expired keys

**Prefix Index** (idx_kv_plugin_prefix):
- Composite: (plugin_name, key)
- Used for: List operations with prefix filtering
- Supports: `WHERE plugin_name = ? AND key LIKE 'prefix%'`
- Performance: <10ms for prefix queries

### 7.4 Storage Estimates

**Row Size**:
- plugin_name: ~20 bytes average
- key: ~50 bytes average
- value: ~500 bytes average (JSON)
- expires_at: 8 bytes
- created_at: 8 bytes
- updated_at: 8 bytes
- **Total**: ~600 bytes per row

**Capacity Planning**:
- 1,000 keys: ~600 KB
- 10,000 keys: ~6 MB
- 100,000 keys: ~60 MB
- 1,000,000 keys: ~600 MB

**Realistic Deployment**:
- 5 plugins × 100 keys each = 500 keys = ~300 KB
- Trivial storage overhead

### 7.5 Alembic Migration

**Migration File**: `alembic/versions/XXX_add_plugin_kv_storage.py`

```python
"""Add plugin KV storage table

Revision ID: abc123def456
Revises: previous_migration
Create Date: 2025-11-22 10:00:00.000000

Sprint: 12 (KV Storage Foundation)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'abc123def456'
down_revision = 'previous_migration'  # Replace with actual previous revision
branch_labels = None
depends_on = None

def upgrade():
    # Create table
    op.create_table(
        'plugin_kv_storage',
        sa.Column('plugin_name', sa.String(100), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                 server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                 server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('plugin_name', 'key')
    )
    
    # Create indexes
    op.create_index(
        'idx_kv_expires_at',
        'plugin_kv_storage',
        ['expires_at'],
        postgresql_where=sa.text('expires_at IS NOT NULL')
    )
    
    op.create_index(
        'idx_kv_plugin_prefix',
        'plugin_kv_storage',
        ['plugin_name', 'key']
    )

def downgrade():
    op.drop_index('idx_kv_plugin_prefix', table_name='plugin_kv_storage')
    op.drop_index('idx_kv_expires_at', table_name='plugin_kv_storage')
    op.drop_table('plugin_kv_storage')
```

---

## 8. NATS Subject Design

### 8.1 Subject Naming Convention

**Pattern**: `db.kv.<plugin>.<operation>`

**Components**:
- `db`: Database service namespace
- `kv`: Key-value storage tier
- `<plugin>`: Plugin identifier (extracted automatically)
- `<operation>`: Action to perform

**Example Subjects**:
- `db.kv.trivia.set` - Trivia plugin sets a key
- `db.kv.quote-db.get` - Quote-db plugin gets a key
- `db.kv.dice-roller.delete` - Dice-roller plugin deletes a key
- `db.kv.my-game.list` - My-game plugin lists keys

### 8.2 Subject Details

#### **db.kv.<plugin>.set**

**Type**: Publish/Subscribe (fire-and-forget) OR Request/Reply (if confirmation needed)  
**Direction**: Plugin → DatabaseService  
**Payload**: JSON object with key, value, optional ttl  
**Response**: Optional success/error response

**Characteristics**:
- **Idempotent**: Setting same key twice updates value
- **Upsert Semantics**: Creates if not exists, updates if exists
- **TTL Support**: Optional ttl parameter (seconds)
- **No Expiration**: Omit ttl or set to null

**When to Use**:
- Store configuration values
- Update counters (read-modify-write pattern in Sprint A)
- Cache temporary data with TTL
- Save game state

---

#### **db.kv.<plugin>.get**

**Type**: Request/Reply (always requires response)  
**Direction**: Plugin → DatabaseService → Plugin  
**Payload**: JSON object with key  
**Response**: JSON object with exists flag and value

**Characteristics**:
- **Fast**: Single primary key lookup
- **TTL Aware**: Expired keys return exists=false
- **Type Preservation**: JSON deserialization preserves types
- **Not Found**: Returns exists=false (not an error)

**When to Use**:
- Retrieve configuration
- Load game state
- Check if key exists
- Read counter value

---

#### **db.kv.<plugin>.delete**

**Type**: Publish/Subscribe (fire-and-forget) OR Request/Reply (if confirmation needed)  
**Direction**: Plugin → DatabaseService  
**Payload**: JSON object with key  
**Response**: Optional deleted flag

**Characteristics**:
- **Idempotent**: Deleting non-existent key succeeds
- **Immediate**: Key removed from database
- **No Cascade**: Only deletes single key (no wildcards in Sprint A)

**When to Use**:
- Clean up temporary data
- Reset configuration
- End game session
- Clear cache

---

#### **db.kv.<plugin>.list**

**Type**: Request/Reply (always requires response)  
**Direction**: Plugin → DatabaseService → Plugin  
**Payload**: JSON object with optional prefix and limit  
**Response**: JSON object with keys array and metadata

**Characteristics**:
- **Filtered**: Optional prefix parameter
- **Limited**: Optional limit parameter (default 1000)
- **TTL Aware**: Excludes expired keys
- **Sorted**: Keys returned in alphabetical order

**When to Use**:
- Discover stored keys
- Implement configuration UI
- Debug plugin state
- Audit stored data

### 8.3 Plugin Name Extraction

**Method**: Parse plugin name from NATS subject path

```python
# In DatabaseService._handle_kv_set()
def extract_plugin_name(subject: str) -> Optional[str]:
    """
    Extract plugin name from NATS subject.
    
    Subject format: db.kv.<plugin>.<operation>
    Example: db.kv.trivia.set → "trivia"
    
    Returns:
        Plugin name or None if invalid format
    """
    parts = subject.split('.')
    if len(parts) != 4:
        return None
    if parts[0] != 'db' or parts[1] != 'kv':
        return None
    
    plugin_name = parts[2]
    
    # Validate plugin name (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-z0-9\-_]+$', plugin_name):
        return None
    
    return plugin_name

# Usage in handler
async def _handle_kv_set(self, msg):
    plugin_name = extract_plugin_name(msg.subject)
    if not plugin_name:
        error_response = {
            'success': False,
            'error_code': 'INVALID_SUBJECT',
            'message': f'Invalid subject format: {msg.subject}'
        }
        await self.nats.publish(msg.reply, json.dumps(error_response).encode())
        return
    
    # Continue with operation...
```

**Security Note**: Plugin name extracted from subject, NOT from payload. Prevents plugins from impersonating other plugins.

### 8.4 Subject Subscription Registration

**In DatabaseService.start()**:

```python
async def start(self):
    # ... existing subscriptions ...
    
    # KV Storage subscriptions (wildcard for all plugins)
    self._subscriptions.extend([
        await self.nats.subscribe('db.kv.*.set', cb=self._handle_kv_set),
        await self.nats.subscribe('db.kv.*.get', cb=self._handle_kv_get),
        await self.nats.subscribe('db.kv.*.delete', cb=self._handle_kv_delete),
        await self.nats.subscribe('db.kv.*.list', cb=self._handle_kv_list),
    ])
    
    self.logger.info(f"DatabaseService: KV storage handlers registered")
```

---

## 9. API Specifications

### 9.1 Set Operation

**NATS Subject**: `db.kv.<plugin>.set`

**Request Payload**:

```json
{
  "key": "string (required)",
  "value": "any JSON type (required)",
  "ttl": "integer seconds (optional, default: null = never expires)"
}
```

**Response Payload** (if request/reply):

```json
{
  "success": true
}
```

**Error Response**:

```json
{
  "success": false,
  "error_code": "VALUE_TOO_LARGE | INVALID_JSON | MISSING_FIELD | DATABASE_ERROR",
  "message": "Human-readable error message"
}
```

**Examples**:

```python
# Set string value
await nats.publish('db.kv.my-plugin.set', json.dumps({
    'key': 'theme',
    'value': 'dark'
}).encode())

# Set number value
await nats.publish('db.kv.my-plugin.set', json.dumps({
    'key': 'count',
    'value': 42
}).encode())

# Set object with TTL (30 minutes)
await nats.publish('db.kv.my-plugin.set', json.dumps({
    'key': 'session_abc',
    'value': {'user': 'alice', 'score': 100},
    'ttl': 1800
}).encode())

# Set array
await nats.publish('db.kv.my-plugin.set', json.dumps({
    'key': 'recent_users',
    'value': ['alice', 'bob', 'charlie']
}).encode())
```

**Error Cases**:

```python
# Value too large (>64KB)
await nats.request('db.kv.my-plugin.set', json.dumps({
    'key': 'huge',
    'value': 'x' * 100000
}).encode())
# Response: {"success": false, "error_code": "VALUE_TOO_LARGE", "message": "..."}

# Missing required field
await nats.request('db.kv.my-plugin.set', json.dumps({
    'value': 'oops'  # Missing 'key'
}).encode())
# Response: {"success": false, "error_code": "MISSING_FIELD", "message": "Missing required field: key"}
```

### 9.2 Get Operation

**NATS Subject**: `db.kv.<plugin>.get`

**Request Payload**:

```json
{
  "key": "string (required)"
}
```

**Success Response**:

```json
{
  "exists": true,
  "value": "any JSON type"
}
```

**Not Found Response**:

```json
{
  "exists": false
}
```

**Error Response**:

```json
{
  "success": false,
  "error_code": "INVALID_JSON | MISSING_FIELD | DATABASE_ERROR",
  "message": "Human-readable error message"
}
```

**Examples**:

```python
# Get existing key
response = await nats.request('db.kv.my-plugin.get', json.dumps({
    'key': 'theme'
}).encode())
data = json.loads(response.data)
if data['exists']:
    print(f"Theme: {data['value']}")
else:
    print("Theme not configured")

# Get non-existent key
response = await nats.request('db.kv.my-plugin.get', json.dumps({
    'key': 'nonexistent'
}).encode())
data = json.loads(response.data)
assert data['exists'] == False

# Get expired key (returns exists=false)
response = await nats.request('db.kv.my-plugin.get', json.dumps({
    'key': 'old_session'
}).encode())
data = json.loads(response.data)
# If TTL expired: data['exists'] == False
```

### 9.3 Delete Operation

**NATS Subject**: `db.kv.<plugin>.delete`

**Request Payload**:

```json
{
  "key": "string (required)"
}
```

**Response Payload** (optional):

```json
{
  "success": true,
  "deleted": true
}
```

**Idempotent Response** (key didn't exist):

```json
{
  "success": true,
  "deleted": false
}
```

**Examples**:

```python
# Delete existing key
await nats.publish('db.kv.my-plugin.delete', json.dumps({
    'key': 'old_data'
}).encode())

# Delete non-existent key (still succeeds)
await nats.publish('db.kv.my-plugin.delete', json.dumps({
    'key': 'never_existed'
}).encode())
```

### 9.4 List Operation

**NATS Subject**: `db.kv.<plugin>.list`

**Request Payload**:

```json
{
  "prefix": "string (optional, default: '')",
  "limit": "integer (optional, default: 1000, max: 10000)"
}
```

**Response Payload**:

```json
{
  "keys": ["key1", "key2", "key3"],
  "count": 3,
  "truncated": false
}
```

**Empty Response**:

```json
{
  "keys": [],
  "count": 0,
  "truncated": false
}
```

**Truncated Response** (hit limit):

```json
{
  "keys": ["key1", "key2", "..."],
  "count": 1000,
  "truncated": true
}
```

**Examples**:

```python
# List all keys
response = await nats.request('db.kv.my-plugin.list', json.dumps({}).encode())
data = json.loads(response.data)
print(f"Found {data['count']} keys: {data['keys']}")

# List keys with prefix
response = await nats.request('db.kv.my-plugin.list', json.dumps({
    'prefix': 'config_'
}).encode())
data = json.loads(response.data)
# Returns only keys starting with 'config_'

# List with limit
response = await nats.request('db.kv.my-plugin.list', json.dumps({
    'limit': 10
}).encode())
data = json.loads(response.data)
if data['truncated']:
    print("More keys available, increase limit")
```

---

## 10. Implementation Plan

### 10.1 Sortie Sequence

**Total**: 4 sorties over 3-4 days

#### **Sortie 1: KV Schema & Model** (Day 1, ~4 hours)

**Branch**: `feature/kv-storage-schema`

**Files Changed**:
- `common/models.py` - Add PluginKVStorage model
- `alembic/versions/XXX_add_plugin_kv_storage.py` - Migration
- `tests/unit/test_models.py` - Model tests

**Deliverables**:
- [ ] PluginKVStorage SQLAlchemy model with all columns
- [ ] Composite primary key (plugin_name, key)
- [ ] Indexes (expiration, prefix)
- [ ] Alembic migration (up/down)
- [ ] Model properties (is_expired, get_value, set_value)
- [ ] Unit tests for model (10+ tests)

**Testing**:
```bash
# Run migration
alembic upgrade head

# Verify table created
alembic current

# Run model tests
pytest tests/unit/test_models.py::TestPluginKVStorage -v

# Coverage check
pytest tests/unit/test_models.py::TestPluginKVStorage --cov=common.models
```

**Acceptance**:
- ✅ Migration applies cleanly (SQLite + PostgreSQL)
- ✅ Table schema matches design
- ✅ All indexes created
- ✅ Model tests pass (100% model coverage)
- ✅ Migration reverses cleanly (downgrade)

---

#### **Sortie 2: BotDatabase KV Methods** (Day 1-2, ~6 hours)

**Branch**: `feature/kv-database-methods`

**Files Changed**:
- `common/database.py` - Add kv_set, kv_get, kv_delete, kv_list, kv_cleanup_expired
- `tests/unit/test_database_kv.py` - New test file for KV methods

**Deliverables**:
- [ ] `async def kv_set(plugin_name, key, value, ttl=None)` - Insert or update
- [ ] `async def kv_get(plugin_name, key)` - Retrieve with TTL check
- [ ] `async def kv_delete(plugin_name, key)` - Delete key
- [ ] `async def kv_list(plugin_name, prefix='', limit=1000)` - List keys
- [ ] `async def kv_cleanup_expired()` - Remove expired keys
- [ ] JSON serialization/deserialization
- [ ] TTL expiration logic
- [ ] Plugin isolation (WHERE plugin_name=?)
- [ ] Unit tests (30+ tests covering all methods and edge cases)

**Code Snippet** (`common/database.py`):

```python
async def kv_set(
    self,
    plugin_name: str,
    key: str,
    value: Any,
    ttl: Optional[int] = None
) -> None:
    """
    Set or update a key-value pair for a plugin.
    
    Args:
        plugin_name: Plugin identifier
        key: Key name
        value: Any JSON-serializable value
        ttl: Time-to-live in seconds (None = never expires)
    
    Raises:
        ValueError: If value exceeds size limit
    """
    # Serialize value
    value_json = json.dumps(value)
    
    # Check size limit (64KB)
    if len(value_json.encode('utf-8')) > 65536:
        raise ValueError(f"Value size exceeds 64KB limit")
    
    # Calculate expiration
    expires_at = None
    if ttl is not None and ttl > 0:
        expires_at = datetime.now() + timedelta(seconds=ttl)
    
    async with self.session_factory() as session:
        # Upsert (INSERT or UPDATE)
        stmt = insert(PluginKVStorage).values(
            plugin_name=plugin_name,
            key=key,
            value=value_json,
            expires_at=expires_at
        ).on_conflict_do_update(
            index_elements=['plugin_name', 'key'],
            set_={
                'value': value_json,
                'expires_at': expires_at,
                'updated_at': func.now()
            }
        )
        await session.execute(stmt)
        await session.commit()

async def kv_get(
    self,
    plugin_name: str,
    key: str
) -> dict:
    """
    Get a key-value pair for a plugin.
    
    Args:
        plugin_name: Plugin identifier
        key: Key name
    
    Returns:
        {'exists': bool, 'value': Any}
        If key doesn't exist or is expired: {'exists': False}
    """
    async with self.session_factory() as session:
        stmt = select(PluginKVStorage).where(
            PluginKVStorage.plugin_name == plugin_name,
            PluginKVStorage.key == key
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        
        if row is None:
            return {'exists': False}
        
        # Check expiration
        if row.is_expired:
            return {'exists': False}
        
        return {
            'exists': True,
            'value': row.get_value()
        }

async def kv_delete(
    self,
    plugin_name: str,
    key: str
) -> bool:
    """
    Delete a key-value pair for a plugin.
    
    Args:
        plugin_name: Plugin identifier
        key: Key name
    
    Returns:
        True if key was deleted, False if didn't exist
    """
    async with self.session_factory() as session:
        stmt = delete(PluginKVStorage).where(
            PluginKVStorage.plugin_name == plugin_name,
            PluginKVStorage.key == key
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

async def kv_list(
    self,
    plugin_name: str,
    prefix: str = '',
    limit: int = 1000
) -> dict:
    """
    List keys for a plugin with optional prefix filter.
    
    Args:
        plugin_name: Plugin identifier
        prefix: Optional key prefix filter
        limit: Maximum keys to return
    
    Returns:
        {'keys': [str], 'count': int, 'truncated': bool}
    """
    async with self.session_factory() as session:
        stmt = select(PluginKVStorage.key).where(
            PluginKVStorage.plugin_name == plugin_name,
            or_(
                PluginKVStorage.expires_at.is_(None),
                PluginKVStorage.expires_at > func.now()
            )
        )
        
        if prefix:
            stmt = stmt.where(PluginKVStorage.key.like(f'{prefix}%'))
        
        stmt = stmt.order_by(PluginKVStorage.key).limit(limit + 1)
        
        result = await session.execute(stmt)
        keys = [row[0] for row in result.fetchall()]
        
        truncated = len(keys) > limit
        if truncated:
            keys = keys[:limit]
        
        return {
            'keys': keys,
            'count': len(keys),
            'truncated': truncated
        }

async def kv_cleanup_expired(self) -> int:
    """
    Remove all expired keys across all plugins.
    
    Returns:
        Number of keys deleted
    """
    async with self.session_factory() as session:
        stmt = delete(PluginKVStorage).where(
            PluginKVStorage.expires_at.is_not(None),
            PluginKVStorage.expires_at < func.now()
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount
```

**Testing**:
```bash
pytest tests/unit/test_database_kv.py -v --cov=common.database
```

**Acceptance**:
- ✅ All 5 methods implemented
- ✅ JSON serialization works (all types)
- ✅ TTL expiration enforced
- ✅ Plugin isolation enforced
- ✅ 30+ unit tests pass
- ✅ Test coverage ≥90% for KV methods

---

#### **Sortie 3: DatabaseService NATS Handlers** (Day 2-3, ~6 hours)

**Branch**: `feature/kv-nats-handlers`

**Files Changed**:
- `common/database_service.py` - Add NATS handlers for KV operations
- `tests/integration/test_kv_nats.py` - Integration tests with NATS

**Deliverables**:
- [ ] `_handle_kv_set(msg)` - Set handler
- [ ] `_handle_kv_get(msg)` - Get handler (request/reply)
- [ ] `_handle_kv_delete(msg)` - Delete handler
- [ ] `_handle_kv_list(msg)` - List handler (request/reply)
- [ ] Plugin name extraction from subject
- [ ] JSON payload validation
- [ ] Error handling (all error codes)
- [ ] Value size validation
- [ ] Structured logging
- [ ] Integration tests with real NATS (20+ tests)

**Code Snippet** (`common/database_service.py`):

```python
async def _handle_kv_set(self, msg):
    """Handle KV set operation."""
    plugin_name = None
    try:
        # Extract plugin name from subject
        plugin_name = self._extract_plugin_name(msg.subject)
        if not plugin_name:
            raise ValueError("Invalid subject format")
        
        # Parse payload
        data = json.loads(msg.data.decode())
        
        # Validate required fields
        if 'key' not in data:
            raise ValueError("Missing required field: key")
        if 'value' not in data:
            raise ValueError("Missing required field: value")
        
        key = data['key']
        value = data['value']
        ttl = data.get('ttl')
        
        # Set key-value
        await self.db.kv_set(plugin_name, key, value, ttl)
        
        self.logger.debug(
            f"[KV] set: plugin={plugin_name} key={key} ttl={ttl}"
        )
        
        # Send response if reply subject provided
        if msg.reply:
            response = {'success': True}
            await self.nats.publish(msg.reply, json.dumps(response).encode())
    
    except json.JSONDecodeError as e:
        self.logger.error(f"[KV] Invalid JSON: {e}")
        if msg.reply:
            error = {
                'success': False,
                'error_code': 'INVALID_JSON',
                'message': f'Invalid JSON: {str(e)}'
            }
            await self.nats.publish(msg.reply, json.dumps(error).encode())
    
    except ValueError as e:
        self.logger.warning(f"[KV] Validation error: {e}")
        if msg.reply:
            if 'size exceeds' in str(e).lower():
                error_code = 'VALUE_TOO_LARGE'
            elif 'Missing required field' in str(e):
                error_code = 'MISSING_FIELD'
            else:
                error_code = 'VALIDATION_ERROR'
            
            error = {
                'success': False,
                'error_code': error_code,
                'message': str(e)
            }
            await self.nats.publish(msg.reply, json.dumps(error).encode())
    
    except Exception as e:
        self.logger.error(
            f"[KV] set failed: plugin={plugin_name} error={e}",
            exc_info=True
        )
        if msg.reply:
            error = {
                'success': False,
                'error_code': 'DATABASE_ERROR',
                'message': 'Internal database error'
            }
            await self.nats.publish(msg.reply, json.dumps(error).encode())

async def _handle_kv_get(self, msg):
    """Handle KV get operation (request/reply)."""
    plugin_name = None
    try:
        # Extract plugin name
        plugin_name = self._extract_plugin_name(msg.subject)
        if not plugin_name:
            raise ValueError("Invalid subject format")
        
        # Parse payload
        data = json.loads(msg.data.decode())
        
        # Validate
        if 'key' not in data:
            raise ValueError("Missing required field: key")
        
        key = data['key']
        
        # Get value
        result = await self.db.kv_get(plugin_name, key)
        
        self.logger.debug(
            f"[KV] get: plugin={plugin_name} key={key} hit={result['exists']}"
        )
        
        # Always respond (request/reply)
        await self.nats.publish(msg.reply, json.dumps(result).encode())
    
    except Exception as e:
        self.logger.error(
            f"[KV] get failed: plugin={plugin_name} error={e}",
            exc_info=True
        )
        error = {
            'success': False,
            'error_code': 'DATABASE_ERROR',
            'message': 'Internal database error'
        }
        await self.nats.publish(msg.reply, json.dumps(error).encode())

# Similar handlers for delete and list...

def _extract_plugin_name(self, subject: str) -> Optional[str]:
    """Extract plugin name from NATS subject."""
    parts = subject.split('.')
    if len(parts) != 4 or parts[0] != 'db' or parts[1] != 'kv':
        return None
    
    plugin_name = parts[2]
    if not re.match(r'^[a-z0-9\-_]+$', plugin_name):
        return None
    
    return plugin_name
```

**Testing**:
```bash
# Start NATS server (pytest fixture handles this)
pytest tests/integration/test_kv_nats.py -v

# Test all handlers
pytest tests/integration/test_kv_nats.py::test_kv_set_via_nats
pytest tests/integration/test_kv_nats.py::test_kv_get_via_nats
pytest tests/integration/test_kv_nats.py::test_kv_isolation
```

**Acceptance**:
- ✅ All 4 NATS handlers implemented
- ✅ Subject wildcard subscriptions work
- ✅ Plugin name extraction works
- ✅ All error cases handled
- ✅ Integration tests pass
- ✅ End-to-end workflow verified

---

#### **Sortie 4: TTL Cleanup & Polish** (Day 3-4, ~4 hours)

**Branch**: `feature/kv-cleanup-polish`

**Files Changed**:
- `common/database_service.py` - Add cleanup task
- `common/database.py` - Optimization tweaks
- `tests/integration/test_kv_cleanup.py` - Cleanup tests
- `tests/performance/test_kv_performance.py` - Performance tests
- `docs/DATABASE_SERVICE.md` - Update documentation

**Deliverables**:
- [ ] Background TTL cleanup task (runs every 5 minutes)
- [ ] Cleanup task logging
- [ ] Performance tests (latency, throughput)
- [ ] Cleanup performance test (10k keys)
- [ ] Documentation updates
- [ ] Value size limit enforcement
- [ ] Slow query logging (>100ms)

**Code Snippet** (Cleanup Task):

```python
# In DatabaseService
async def start(self):
    # ... existing code ...
    
    # Start cleanup task
    self._cleanup_task = asyncio.create_task(self._kv_cleanup_loop())
    
    self.logger.info("DatabaseService: KV cleanup task started")

async def stop(self):
    # Cancel cleanup task
    if hasattr(self, '_cleanup_task') and self._cleanup_task:
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
    
    # ... existing code ...

async def _kv_cleanup_loop(self):
    """Background task to clean up expired KV entries."""
    while self._running:
        try:
            # Wait 5 minutes
            await asyncio.sleep(300)
            
            # Run cleanup
            start_time = time.time()
            deleted = await self.db.kv_cleanup_expired()
            elapsed = time.time() - start_time
            
            if deleted > 0:
                self.logger.info(
                    f"[KV] Cleanup: removed {deleted} expired keys in {elapsed:.2f}s"
                )
            
            # Warn if cleanup is slow
            if elapsed > 1.0:
                self.logger.warning(
                    f"[KV] Cleanup slow: {elapsed:.2f}s for {deleted} keys"
                )
        
        except asyncio.CancelledError:
            self.logger.info("[KV] Cleanup task cancelled")
            break
        
        except Exception as e:
            self.logger.error(f"[KV] Cleanup error: {e}", exc_info=True)
            # Continue running despite errors
```

**Testing**:
```bash
# Cleanup tests
pytest tests/integration/test_kv_cleanup.py -v

# Performance tests
pytest tests/performance/test_kv_performance.py -v

# Full test suite
pytest tests/unit/test_database_kv.py tests/integration/test_kv_nats.py -v --cov
```

**Acceptance**:
- ✅ Cleanup task runs automatically
- ✅ Cleanup performance <1s for 10k keys
- ✅ Performance tests pass (p95 <10ms)
- ✅ Documentation updated
- ✅ All tests pass
- ✅ Coverage ≥85%

---

### 10.2 Development Workflow

**Daily Standup Questions**:
- What did I complete yesterday?
- What will I complete today?
- Any blockers?

**Code Review Checklist**:
- [ ] All tests pass
- [ ] Coverage ≥85%
- [ ] Docstrings complete (Google style)
- [ ] Type hints present
- [ ] Error handling comprehensive
- [ ] Logging appropriate
- [ ] Performance acceptable
- [ ] Security reviewed (isolation, injection)

**Merge Strategy**:
- Each sortie merges to `main` after review (may contain multiple commits)
- Alembic migration in first sortie
- No breaking changes to existing code

---

## 11. Testing Strategy

### 11.1 Test Coverage Goals

**Overall**: ≥85%  
**Critical Paths**: 100%  
- Plugin isolation enforcement
- TTL expiration logic
- Error handling
- JSON serialization/deserialization

**Test Distribution**:
- Unit tests: 40+ tests (database methods, models)
- Integration tests: 25+ tests (NATS handlers, end-to-end)
- Performance tests: 5+ tests (latency, throughput, cleanup)
- Security tests: 10+ tests (isolation, injection, validation)

### 11.2 Unit Tests

**File**: `tests/unit/test_database_kv.py`

**Test Cases**:

```python
class TestKVSet:
    async def test_set_string_value(self, db):
        await db.kv_set('test-plugin', 'key1', 'value1')
        result = await db.kv_get('test-plugin', 'key1')
        assert result['exists'] == True
        assert result['value'] == 'value1'
    
    async def test_set_number_value(self, db):
        await db.kv_set('test-plugin', 'count', 42)
        result = await db.kv_get('test-plugin', 'count')
        assert result['value'] == 42
        assert isinstance(result['value'], int)
    
    async def test_set_object_value(self, db):
        obj = {'nested': {'data': True}, 'array': [1, 2, 3]}
        await db.kv_set('test-plugin', 'config', obj)
        result = await db.kv_get('test-plugin', 'config')
        assert result['value'] == obj
    
    async def test_set_with_ttl(self, db):
        await db.kv_set('test-plugin', 'temp', 'data', ttl=1)
        result = await db.kv_get('test-plugin', 'temp')
        assert result['exists'] == True
        
        # Wait for expiration
        await asyncio.sleep(2)
        result = await db.kv_get('test-plugin', 'temp')
        assert result['exists'] == False
    
    async def test_set_updates_existing(self, db):
        await db.kv_set('test-plugin', 'key', 'v1')
        await db.kv_set('test-plugin', 'key', 'v2')
        result = await db.kv_get('test-plugin', 'key')
        assert result['value'] == 'v2'
    
    async def test_set_value_too_large(self, db):
        huge_value = 'x' * 100000
        with pytest.raises(ValueError, match='64KB'):
            await db.kv_set('test-plugin', 'key', huge_value)

class TestKVGet:
    async def test_get_existing_key(self, db):
        await db.kv_set('test-plugin', 'key', 'value')
        result = await db.kv_get('test-plugin', 'key')
        assert result['exists'] == True
        assert result['value'] == 'value'
    
    async def test_get_nonexistent_key(self, db):
        result = await db.kv_get('test-plugin', 'nonexistent')
        assert result['exists'] == False
        assert 'value' not in result
    
    async def test_get_expired_key(self, db):
        await db.kv_set('test-plugin', 'key', 'value', ttl=1)
        await asyncio.sleep(2)
        result = await db.kv_get('test-plugin', 'key')
        assert result['exists'] == False

class TestKVDelete:
    async def test_delete_existing_key(self, db):
        await db.kv_set('test-plugin', 'key', 'value')
        deleted = await db.kv_delete('test-plugin', 'key')
        assert deleted == True
        result = await db.kv_get('test-plugin', 'key')
        assert result['exists'] == False
    
    async def test_delete_nonexistent_key(self, db):
        deleted = await db.kv_delete('test-plugin', 'nonexistent')
        assert deleted == False

class TestKVList:
    async def test_list_all_keys(self, db):
        await db.kv_set('test-plugin', 'a', 1)
        await db.kv_set('test-plugin', 'b', 2)
        await db.kv_set('test-plugin', 'c', 3)
        
        result = await db.kv_list('test-plugin')
        assert set(result['keys']) == {'a', 'b', 'c'}
        assert result['count'] == 3
        assert result['truncated'] == False
    
    async def test_list_with_prefix(self, db):
        await db.kv_set('test-plugin', 'config_a', 1)
        await db.kv_set('test-plugin', 'config_b', 2)
        await db.kv_set('test-plugin', 'state_x', 3)
        
        result = await db.kv_list('test-plugin', prefix='config_')
        assert set(result['keys']) == {'config_a', 'config_b'}
    
    async def test_list_excludes_expired(self, db):
        await db.kv_set('test-plugin', 'active', 1)
        await db.kv_set('test-plugin', 'expired', 2, ttl=1)
        await asyncio.sleep(2)
        
        result = await db.kv_list('test-plugin')
        assert result['keys'] == ['active']
    
    async def test_list_with_limit(self, db):
        for i in range(20):
            await db.kv_set('test-plugin', f'key{i}', i)
        
        result = await db.kv_list('test-plugin', limit=10)
        assert result['count'] == 10
        assert result['truncated'] == True

class TestKVIsolation:
    async def test_plugin_isolation(self, db):
        await db.kv_set('plugin-a', 'shared_key', 'value_a')
        await db.kv_set('plugin-b', 'shared_key', 'value_b')
        
        result_a = await db.kv_get('plugin-a', 'shared_key')
        result_b = await db.kv_get('plugin-b', 'shared_key')
        
        assert result_a['value'] == 'value_a'
        assert result_b['value'] == 'value_b'
    
    async def test_list_isolation(self, db):
        await db.kv_set('plugin-a', 'key1', 1)
        await db.kv_set('plugin-b', 'key2', 2)
        
        result_a = await db.kv_list('plugin-a')
        result_b = await db.kv_list('plugin-b')
        
        assert result_a['keys'] == ['key1']
        assert result_b['keys'] == ['key2']

class TestKVCleanup:
    async def test_cleanup_removes_expired(self, db):
        # Set 10 keys with 1-second TTL
        for i in range(10):
            await db.kv_set('test-plugin', f'temp{i}', i, ttl=1)
        
        await asyncio.sleep(2)
        deleted = await db.kv_cleanup_expired()
        assert deleted == 10
        
        result = await db.kv_list('test-plugin')
        assert result['count'] == 0
    
    async def test_cleanup_preserves_active(self, db):
        await db.kv_set('test-plugin', 'active', 1)
        await db.kv_set('test-plugin', 'expired', 2, ttl=1)
        await asyncio.sleep(2)
        
        deleted = await db.kv_cleanup_expired()
        assert deleted == 1
        
        result = await db.kv_get('test-plugin', 'active')
        assert result['exists'] == True
```

### 11.3 Integration Tests

**File**: `tests/integration/test_kv_nats.py`

**Test Cases**:

```python
class TestKVNATSIntegration:
    async def test_set_via_nats(self, nats_client, db_service):
        # Publish set request
        await nats_client.publish(
            'db.kv.test-plugin.set',
            json.dumps({'key': 'test', 'value': 'data'}).encode()
        )
        
        await asyncio.sleep(0.1)  # Allow processing
        
        # Verify in database
        result = await db_service.db.kv_get('test-plugin', 'test')
        assert result['exists'] == True
        assert result['value'] == 'data'
    
    async def test_get_via_nats(self, nats_client, db_service):
        # Set value directly
        await db_service.db.kv_set('test-plugin', 'test', 'data')
        
        # Get via NATS
        response = await nats_client.request(
            'db.kv.test-plugin.get',
            json.dumps({'key': 'test'}).encode(),
            timeout=1
        )
        
        data = json.loads(response.data)
        assert data['exists'] == True
        assert data['value'] == 'data'
    
    async def test_end_to_end_workflow(self, nats_client):
        # Set
        await nats_client.publish(
            'db.kv.workflow-test.set',
            json.dumps({'key': 'counter', 'value': 0}).encode()
        )
        
        await asyncio.sleep(0.1)
        
        # Get
        response = await nats_client.request(
            'db.kv.workflow-test.get',
            json.dumps({'key': 'counter'}).encode(),
            timeout=1
        )
        data = json.loads(response.data)
        count = data['value']
        
        # Increment
        count += 1
        await nats_client.publish(
            'db.kv.workflow-test.set',
            json.dumps({'key': 'counter', 'value': count}).encode()
        )
        
        await asyncio.sleep(0.1)
        
        # Verify
        response = await nats_client.request(
            'db.kv.workflow-test.get',
            json.dumps({'key': 'counter'}).encode(),
            timeout=1
        )
        assert json.loads(response.data)['value'] == 1
    
    async def test_error_handling_invalid_json(self, nats_client):
        response = await nats_client.request(
            'db.kv.test-plugin.get',
            b'not json',
            timeout=1
        )
        data = json.loads(response.data)
        assert data['success'] == False
        assert data['error_code'] == 'INVALID_JSON'
    
    async def test_error_handling_value_too_large(self, nats_client):
        huge = 'x' * 100000
        response = await nats_client.request(
            'db.kv.test-plugin.set',
            json.dumps({'key': 'huge', 'value': huge}).encode(),
            timeout=1
        )
        data = json.loads(response.data)
        assert data['success'] == False
        assert data['error_code'] == 'VALUE_TOO_LARGE'
```

### 11.4 Performance Tests

**File**: `tests/performance/test_kv_performance.py`

**Test Cases**:

```python
class TestKVPerformance:
    async def test_set_latency(self, db, benchmark):
        """Measure set operation latency"""
        await benchmark(db.kv_set, 'perf-test', 'key', 'value')
        # Target: <5ms p50, <10ms p95
    
    async def test_get_latency(self, db, benchmark):
        """Measure get operation latency"""
        await db.kv_set('perf-test', 'key', 'value')
        await benchmark(db.kv_get, 'perf-test', 'key')
        # Target: <5ms p50, <10ms p95
    
    async def test_throughput(self, db):
        """Measure operations per second"""
        start = time.time()
        tasks = []
        for i in range(1000):
            tasks.append(db.kv_set('perf-test', f'key{i}', i))
        await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        ops_per_sec = 1000 / elapsed
        assert ops_per_sec >= 1000  # Target: ≥1000 ops/sec
    
    async def test_cleanup_performance(self, db):
        """Measure cleanup performance with 10k expired keys"""
        # Create 10k expired keys
        for i in range(10000):
            await db.kv_set('perf-test', f'temp{i}', i, ttl=1)
        
        await asyncio.sleep(2)
        
        # Measure cleanup
        start = time.time()
        deleted = await db.kv_cleanup_expired()
        elapsed = time.time() - start
        
        assert deleted == 10000
        assert elapsed < 1.0  # Target: <1 second
```

### 11.5 Security Tests

**File**: `tests/security/test_kv_security.py`

**Test Cases**:

```python
class TestKVSecurity:
    async def test_plugin_cannot_read_other_plugin_keys(self, db):
        """Verify strict plugin isolation"""
        await db.kv_set('plugin-a', 'secret', 'data-a')
        result = await db.kv_get('plugin-b', 'secret')
        assert result['exists'] == False
    
    async def test_plugin_cannot_delete_other_plugin_keys(self, db):
        """Verify delete isolation"""
        await db.kv_set('plugin-a', 'key', 'value')
        deleted = await db.kv_delete('plugin-b', 'key')
        assert deleted == False
        result = await db.kv_get('plugin-a', 'key')
        assert result['exists'] == True
    
    async def test_plugin_name_validation(self, db_service):
        """Verify plugin name is validated"""
        # Invalid characters
        result = db_service._extract_plugin_name('db.kv../etc/passwd.get')
        assert result is None
        
        # SQL injection attempt
        result = db_service._extract_plugin_name("db.kv.'; DROP TABLE--.get")
        assert result is None
    
    async def test_json_injection_prevented(self, db):
        """Verify JSON values can't inject SQL"""
        malicious = "'; DROP TABLE plugin_kv_storage; --"
        await db.kv_set('test-plugin', 'key', malicious)
        result = await db.kv_get('test-plugin', 'key')
        assert result['value'] == malicious  # Stored as string, not executed
```

---

## 12. Security & Isolation

### 12.1 Plugin Namespace Isolation

**Principle**: Plugins can ONLY access their own keys, never other plugins' keys.

**Enforcement Mechanisms**:

1. **NATS Subject-Based Identification**:
   - Plugin identity extracted from subject, NOT payload
   - Plugin cannot forge identity (subject controlled by NATS routing)
   - Subject format: `db.kv.<plugin>.<operation>` → plugin extracted from position 2

2. **Database Queries Always Filter by plugin_name**:
   ```python
   # Every query includes plugin_name filter
   stmt = select(PluginKVStorage).where(
       PluginKVStorage.plugin_name == plugin_name,
       PluginKVStorage.key == key
   )
   ```

3. **No Wildcard Access**:
   - Plugin cannot use `*` in get/delete operations
   - List operation filters by plugin_name
   - No cross-plugin queries possible

**Attack Scenarios Prevented**:

| Attack | Prevention |
|--------|------------|
| Plugin A reads Plugin B's keys | `WHERE plugin_name='plugin-a'` filter enforces isolation |
| Plugin A deletes Plugin B's keys | `WHERE plugin_name='plugin-a'` filter prevents access |
| Plugin forges plugin_name in payload | Plugin name extracted from NATS subject, not payload |
| Wildcard injection (`*` or `%`) | Wildcard characters treated as literal in key names |
| Directory traversal (`../`) | Plugin name regex validation: `^[a-z0-9\-_]+$` |

### 12.2 Input Validation

**Plugin Name Validation**:
- Pattern: `^[a-z0-9\-_]+$` (lowercase letters, numbers, hyphens, underscores)
- Max length: 100 characters
- No special characters: `.`, `/`, `\`, `*`, `%`, `;`, `'`, `"`, `<`, `>`
- Enforced at: Subject extraction time

**Key Name Validation**:
- Max length: 255 characters
- Allowed characters: Any UTF-8
- No validation beyond length (application-specific keys)
- Note: Wildcards (`*`, `%`) treated as literal characters

**Value Validation**:
- Must be valid JSON
- Max size: 64KB (65,536 bytes) after JSON serialization
- No nested depth limit (Python's JSON library handles this)
- Type preservation: string, number, boolean, null, array, object

**TTL Validation**:
- Optional (null = never expires)
- If provided: must be positive integer (seconds)
- Min: 1 second
- Max: 2147483647 seconds (~68 years)
- Stored as: TIMESTAMP = now() + ttl seconds

### 12.3 SQL Injection Prevention

**SQLAlchemy ORM Protection**:
- All queries use parameterized statements
- No string concatenation for SQL
- Plugin names and keys passed as bound parameters

**Example Safe Query**:
```python
# SAFE: Parameterized query
stmt = select(PluginKVStorage).where(
    PluginKVStorage.plugin_name == plugin_name,  # Bound parameter
    PluginKVStorage.key == key                   # Bound parameter
)

# UNSAFE (not used in codebase):
# query = f"SELECT * FROM plugin_kv_storage WHERE plugin_name='{plugin_name}'"
```

**JSON Injection Prevention**:
- JSON values stored as TEXT
- Database doesn't execute JSON content
- No JSON path queries in Sprint A (Sprint D adds parameterized SQL)

### 12.4 Denial of Service Prevention

**Value Size Limits**:
- 64KB max per value
- Prevents memory exhaustion
- Error returned if exceeded: `VALUE_TOO_LARGE`

**List Operation Limits**:
- Default limit: 1,000 keys
- Max limit: 10,000 keys
- Prevents unbounded result sets
- `truncated` flag indicates more data available

**TTL Cleanup**:
- Background task runs every 5 minutes
- Prevents expired key accumulation
- Automatic, no manual intervention needed

**Rate Limiting** (Future Enhancement):
- Not implemented in Sprint A
- Consider for Sprint B or production hardening
- NATS-level rate limiting recommended

### 12.5 Data Privacy

**No Encryption at Rest** (Sprint A):
- Values stored as plaintext JSON
- Database encryption is infrastructure concern
- Sprint D may add application-level encryption

**No Encryption in Transit** (Sprint A):
- NATS messages not encrypted within cluster
- TLS for NATS recommended in production (infrastructure)
- Sprint 5/6 covers production security

**Sensitive Data Guidance**:
- Plugins should NOT store:
  - Passwords (use hashed passwords)
  - API tokens (use secrets manager)
  - PII (use separate encrypted storage)
- KV storage intended for:
  - Configuration
  - Application state
  - Temporary data
  - Non-sensitive metadata

---

## 13. Performance Requirements

### 13.1 Latency Targets

**Set Operation**:
- **p50**: <5ms (median)
- **p95**: <10ms (95th percentile)
- **p99**: <20ms (99th percentile)
- **Timeout**: 100ms (fail if exceeded)

**Get Operation**:
- **p50**: <5ms (primary key lookup)
- **p95**: <10ms
- **p99**: <15ms
- **Timeout**: 100ms

**Delete Operation**:
- **p50**: <5ms
- **p95**: <10ms
- **Timeout**: 100ms

**List Operation**:
- **p50**: <10ms (1-100 keys)
- **p95**: <50ms (1000 keys)
- **p99**: <100ms (10000 keys)
- **Timeout**: 500ms

**Rationale**: These targets ensure imperceptible delay for users. Most operations complete in <10ms, providing responsive bot interactions.

### 13.2 Throughput Targets

**Set Operations**:
- **Target**: ≥1,000 ops/sec (single instance)
- **Burst**: ≥5,000 ops/sec (short duration)
- **Sustained**: ≥500 ops/sec (long-term average)

**Get Operations**:
- **Target**: ≥2,000 ops/sec (read-heavy)
- **Burst**: ≥10,000 ops/sec
- **Sustained**: ≥1,000 ops/sec

**Mixed Workload** (70% read, 30% write):
- **Target**: ≥1,500 ops/sec

**Rationale**: Rosey-Robot chat workloads are low volume (<10 ops/sec typical). These targets provide 100-200x headroom for growth.

### 13.3 Cleanup Performance

**TTL Cleanup Task**:
- **Interval**: Every 5 minutes (300 seconds)
- **Target**: <1 second to delete 10,000 expired keys
- **Impact**: Cleanup should not affect foreground operations
- **Warning Threshold**: Log warning if cleanup takes >1 second

**Cleanup Query**:
```sql
DELETE FROM plugin_kv_storage
WHERE expires_at IS NOT NULL
  AND expires_at < CURRENT_TIMESTAMP;
```

**Index Support**: Partial index `idx_kv_expires_at` ensures fast cleanup even with millions of rows.

### 13.4 Storage Efficiency

**Row Overhead**:
- Target: <100 bytes overhead per row
- Actual: ~100 bytes (columns + indexes)
- Data: ~500 bytes average (JSON payload)
- Total: ~600 bytes per row

**Compression** (PostgreSQL):
- TEXT columns use TOAST compression automatically
- Large JSON values compressed transparently
- No application-level compression needed

**Index Size**:
- Primary key: ~50 bytes per row
- Expiration index: ~10 bytes per row (partial, only TTL keys)
- Prefix index: ~70 bytes per row
- Total index overhead: ~130 bytes per row

**Capacity Planning**:
- 1 million keys: ~730 MB total (600 MB data + 130 MB indexes)
- Target deployment: <10,000 keys (<7 MB)

### 13.5 Scalability Considerations

**Sprint A Limits** (Single Database Instance):
- **Keys**: 1,000,000+ (tested to 10 million)
- **Plugins**: 1,000+ (no practical limit)
- **Concurrent Operations**: 1,000+ ops/sec
- **Database Size**: <10 GB (practical limit for SQLite)

**PostgreSQL Scaling** (Production):
- **Keys**: Billions (PostgreSQL handles large tables)
- **Replication**: Read replicas for read-heavy workloads
- **Partitioning**: By plugin_name if needed (future)
- **Connection Pooling**: Already implemented in DatabaseService

**Not Addressed in Sprint A**:
- Horizontal sharding (single DB sufficient)
- Multi-region replication
- Read replicas
- Caching layer (Redis)

---

## 14. Error Handling

### 14.1 Error Codes

**Client Errors** (4xx-style):

| Code | Meaning | Cause | Resolution |
|------|---------|-------|------------|
| `INVALID_JSON` | Payload is not valid JSON | Malformed JSON in request | Fix JSON syntax |
| `MISSING_FIELD` | Required field missing | `key` or `value` not provided | Add required field |
| `VALUE_TOO_LARGE` | Value exceeds size limit | Value >64KB | Reduce value size |
| `INVALID_SUBJECT` | NATS subject format invalid | Subject doesn't match pattern | Use correct subject format |
| `VALIDATION_ERROR` | General validation failure | Invalid parameter value | Check parameter constraints |

**Server Errors** (5xx-style):

| Code | Meaning | Cause | Resolution |
|------|---------|-------|------------|
| `DATABASE_ERROR` | Database operation failed | DB connection lost, constraint violation | Retry operation, check DB health |
| `INTERNAL_ERROR` | Unexpected error | Unhandled exception | Report to developers |

### 14.2 Error Response Format

**Synchronous Operations** (request/reply):

```json
{
  "success": false,
  "error_code": "VALUE_TOO_LARGE",
  "message": "Value size exceeds 64KB limit (got 100KB)"
}
```

**Asynchronous Operations** (publish):
- Errors logged to `rosey.log`
- No response sent to client
- Plugin continues unaware of error

**Best Practice**: Use request/reply for critical operations (get, set with confirmation). Use publish for fire-and-forget (set without confirmation).

### 14.3 Error Handling Examples

**In Plugin Code**:

```python
# Handle get operation errors
try:
    response = await nats.request('db.kv.my-plugin.get', 
                                   json.dumps({'key': 'config'}).encode(),
                                   timeout=1.0)
    data = json.loads(response.data)
    
    if 'success' in data and not data['success']:
        # Error response
        self.logger.error(f"KV get failed: {data['error_code']} - {data['message']}")
        return None
    
    if not data['exists']:
        # Key not found (not an error)
        self.logger.info("Config key not found, using defaults")
        return default_config
    
    return data['value']

except asyncio.TimeoutError:
    self.logger.error("KV get timed out after 1 second")
    return None

except Exception as e:
    self.logger.error(f"KV get exception: {e}", exc_info=True)
    return None
```

**In DatabaseService**:

```python
async def _handle_kv_set(self, msg):
    """Handle KV set with comprehensive error handling."""
    plugin_name = None
    
    try:
        # Extract plugin name
        plugin_name = self._extract_plugin_name(msg.subject)
        if not plugin_name:
            raise ValueError("Invalid subject format")
        
        # Parse payload
        data = json.loads(msg.data.decode())
        
        # Validate required fields
        if 'key' not in data:
            raise ValueError("Missing required field: key")
        if 'value' not in data:
            raise ValueError("Missing required field: value")
        
        # Perform operation
        await self.db.kv_set(
            plugin_name,
            data['key'],
            data['value'],
            data.get('ttl')
        )
        
        # Success response (if reply requested)
        if msg.reply:
            await self.nats.publish(
                msg.reply,
                json.dumps({'success': True}).encode()
            )
    
    except json.JSONDecodeError as e:
        # JSON parsing error
        self.logger.error(f"[KV] Invalid JSON: {e}")
        await self._send_error(msg, 'INVALID_JSON', f'Invalid JSON: {str(e)}')
    
    except ValueError as e:
        # Validation error
        self.logger.warning(f"[KV] Validation error: {e}")
        
        # Determine specific error code
        error_msg = str(e).lower()
        if 'size exceeds' in error_msg:
            error_code = 'VALUE_TOO_LARGE'
        elif 'missing required field' in error_msg:
            error_code = 'MISSING_FIELD'
        else:
            error_code = 'VALIDATION_ERROR'
        
        await self._send_error(msg, error_code, str(e))
    
    except Exception as e:
        # Unexpected error
        self.logger.error(
            f"[KV] set failed: plugin={plugin_name} error={e}",
            exc_info=True
        )
        await self._send_error(msg, 'DATABASE_ERROR', 'Internal database error')

async def _send_error(self, msg, error_code: str, message: str):
    """Send error response if reply subject provided."""
    if msg.reply:
        error = {
            'success': False,
            'error_code': error_code,
            'message': message
        }
        await self.nats.publish(msg.reply, json.dumps(error).encode())
```

### 14.4 Edge Cases

**Expired Key Get**:
- Request: Get key with expired TTL
- Response: `{'exists': False}`
- Behavior: Expired keys treated as non-existent

**Delete Non-Existent Key**:
- Request: Delete key that doesn't exist
- Response: `{'success': True, 'deleted': False}`
- Behavior: Idempotent (success regardless)

**Set Existing Key**:
- Request: Set key that already exists
- Response: `{'success': True}`
- Behavior: Upsert (update value)

**List with No Keys**:
- Request: List for plugin with no keys
- Response: `{'keys': [], 'count': 0, 'truncated': False}`
- Behavior: Empty list (not an error)

**Concurrent Set Operations**:
- Request: Two plugins set same key simultaneously
- Response: Both succeed
- Behavior: Last write wins (database handles race)

**TTL Update**:
- Request: Set existing key with new TTL
- Response: `{'success': True}`
- Behavior: TTL replaced (not extended)

---

## 15. Observability

### 15.1 Logging

**Log Format** (Structured):

```python
self.logger.info(
    "[KV] set: plugin=trivia key=question_count ttl=null",
    extra={
        'operation': 'kv_set',
        'plugin': 'trivia',
        'key': 'question_count',
        'ttl': None,
        'latency_ms': 3.2
    }
)
```

**Log Levels**:

| Level | When to Use | Example |
|-------|-------------|---------|
| DEBUG | Individual operations | `[KV] get: plugin=trivia key=score hit=true` |
| INFO | Lifecycle events | `[KV] Cleanup: removed 42 expired keys in 0.05s` |
| WARNING | Degraded performance | `[KV] Cleanup slow: 1.5s for 100 keys` |
| ERROR | Operation failures | `[KV] set failed: plugin=trivia error=DatabaseError` |

**Log Sampling** (High Volume):
- DEBUG logs: Sample 1% if >1000 ops/sec
- INFO logs: Always log
- WARNING/ERROR: Always log

### 15.2 Metrics

**Recommended Metrics** (for future Prometheus integration):

**Operation Counters**:
- `rosey_kv_set_total{plugin="trivia"}` - Total set operations
- `rosey_kv_get_total{plugin="trivia"}` - Total get operations
- `rosey_kv_delete_total{plugin="trivia"}` - Total delete operations
- `rosey_kv_list_total{plugin="trivia"}` - Total list operations

**Operation Latency** (histogram):
- `rosey_kv_set_duration_seconds{plugin="trivia"}` - Set operation latency
- `rosey_kv_get_duration_seconds{plugin="trivia"}` - Get operation latency

**Error Counters**:
- `rosey_kv_errors_total{plugin="trivia", error_code="VALUE_TOO_LARGE"}` - Errors by type

**Storage Metrics**:
- `rosey_kv_keys_total{plugin="trivia"}` - Total keys per plugin
- `rosey_kv_storage_bytes{plugin="trivia"}` - Storage used per plugin

**Cleanup Metrics**:
- `rosey_kv_cleanup_duration_seconds` - Cleanup task duration
- `rosey_kv_cleanup_deleted_total` - Keys deleted by cleanup

**Note**: Sprint A includes metric hooks (commented placeholders). Sprint 5 implements full Prometheus integration.

### 15.3 Debugging

**Enable Debug Logging**:

```bash
# In config.json
{
  "logging": {
    "level": "DEBUG",
    "database_service": "DEBUG"
  }
}
```

**View Recent Operations**:

```sql
-- Recent set operations (from updated_at)
SELECT plugin_name, key, updated_at
FROM plugin_kv_storage
ORDER BY updated_at DESC
LIMIT 20;

-- Keys by plugin
SELECT plugin_name, COUNT(*) as key_count
FROM plugin_kv_storage
GROUP BY plugin_name;

-- Expired keys (should be cleaned up)
SELECT plugin_name, key, expires_at
FROM plugin_kv_storage
WHERE expires_at < CURRENT_TIMESTAMP;
```

**NATS Debugging**:

```bash
# Subscribe to all KV operations
nats sub 'db.kv.*.>'

# Monitor specific plugin
nats sub 'db.kv.trivia.>'

# Test get operation manually
nats req 'db.kv.test.get' '{"key":"mykey"}'
```

### 15.4 Alerting Hooks

**Future Alert Conditions**:
- Cleanup task fails 3+ times → Alert developers
- Cleanup duration >5 seconds → Alert performance issue
- Error rate >10% → Alert reliability issue
- Storage size >1 GB per plugin → Alert capacity issue

**Sprint A**: Logging only, no alerting infrastructure. Sprint 5 adds Prometheus + Alertmanager.

---

## 16. Documentation Requirements

### 16.1 Code Documentation

**Docstrings** (Google Style):

```python
async def kv_set(
    self,
    plugin_name: str,
    key: str,
    value: Any,
    ttl: Optional[int] = None
) -> None:
    """
    Set or update a key-value pair for a plugin.
    
    This operation is idempotent: setting the same key multiple times
    will update the value. Values are stored as JSON and must be
    JSON-serializable (str, int, float, bool, None, list, dict).
    
    Args:
        plugin_name: Plugin identifier (alphanumeric, hyphens, underscores).
                     Extracted from NATS subject, not trusted from payload.
        key: Key name (max 255 chars). Can be any UTF-8 string.
        value: Any JSON-serializable value. Max 64KB after JSON encoding.
        ttl: Optional time-to-live in seconds. None means never expires.
             Min 1 second, max ~68 years.
    
    Raises:
        ValueError: If value exceeds 64KB limit after JSON encoding.
    
    Example:
        >>> await db.kv_set('trivia', 'question_count', 42)
        >>> await db.kv_set('trivia', 'session', {'user': 'alice'}, ttl=1800)
    """
```

**Inline Comments** (Complex Logic):

```python
# Upsert operation: INSERT if not exists, UPDATE if exists
# PostgreSQL: ON CONFLICT DO UPDATE
# SQLite: INSERT OR REPLACE (but loses created_at)
stmt = insert(PluginKVStorage).values(
    plugin_name=plugin_name,
    key=key,
    value=value_json,
    expires_at=expires_at
).on_conflict_do_update(
    index_elements=['plugin_name', 'key'],
    set_={
        'value': value_json,
        'expires_at': expires_at,
        'updated_at': func.now()  # Preserve created_at
    }
)
```

### 16.2 User Documentation

**Plugin Developer Guide**: `docs/guides/PLUGIN_KV_STORAGE.md`

**Contents**:
1. **Overview**: What is KV storage, when to use it
2. **Quickstart**: 5-minute getting started example
3. **Operations**: Set, Get, Delete, List with examples
4. **Patterns**: Common usage patterns (configuration, caching, state)
5. **TTL**: How to use time-to-live for temporary data
6. **Best Practices**: Naming conventions, error handling, value size
7. **Limitations**: Max size, no transactions, eventual consistency
8. **Migration from JSON Files**: How to move existing plugin data

**Example Snippet** (Quickstart):

```markdown
## Quickstart: Using KV Storage

### 1. Import NATS client

```python
from lib.bot import Bot

class MyPlugin(Bot):
    async def on_ready(self):
        # NATS client available as self.nats
        await self.save_config()
```

### 2. Set a value

```python
async def save_config(self):
    config = {'theme': 'dark', 'notifications': True}
    await self.nats.publish(
        'db.kv.my-plugin.set',
        json.dumps({
            'key': 'config',
            'value': config
        }).encode()
    )
```

### 3. Get a value

```python
async def load_config(self):
    response = await self.nats.request(
        'db.kv.my-plugin.get',
        json.dumps({'key': 'config'}).encode(),
        timeout=1.0
    )
    data = json.loads(response.data)
    if data['exists']:
        return data['value']
    else:
        return {'theme': 'light', 'notifications': False}  # defaults
```
```

### 16.3 Architecture Documentation

**Update**: `docs/ARCHITECTURE.md`

**Add Section**:

```markdown
## Plugin Storage Architecture

### KV Storage (Sprint 12)

Plugins can store persistent key-value data via NATS subjects:

- **Set**: `db.kv.<plugin>.set` - Store/update a value
- **Get**: `db.kv.<plugin>.get` - Retrieve a value
- **Delete**: `db.kv.<plugin>.delete` - Remove a value
- **List**: `db.kv.<plugin>.list` - List all keys

**Data Flow**:

1. Plugin publishes to `db.kv.<plugin>.<operation>`
2. DatabaseService receives message
3. Plugin name extracted from subject (not payload)
4. BotDatabase executes SQL query (isolated by plugin_name)
5. Response sent via NATS reply subject

**Storage**:
- Table: `plugin_kv_storage` (plugin_name, key) PRIMARY KEY
- Values: JSON (any type)
- TTL: Optional expiration (background cleanup)
- Isolation: Plugins can only access their own keys

**Future Tiers**:
- Sprint 13: Row operations (CRUD with migrations)
- Sprint 15: Parameterized SQL (advanced queries)
```

### 16.4 API Reference

**Generate from Code**: Use `sphinx` or `mkdocs` to auto-generate API docs from docstrings.

**Manual Reference**: `docs/api/DATABASE_KV_API.md`

**Contents**:
- NATS subjects and payload formats
- Request/response schemas (JSON)
- Error codes and meanings
- Latency expectations
- Examples for each operation

---

## 17. Dependencies & Risks

### 17.1 Internal Dependencies

**Required Systems** (Must be running):
- ✅ **NATS Server**: Message bus for subject subscriptions
- ✅ **SQLAlchemy ORM**: Database abstraction (Sprint 11)
- ✅ **DatabaseService**: NATS-enabled service (Sprint 9)
- ✅ **Alembic**: Migration infrastructure

**Required Functionality**:
- ✅ **Plugin Manager**: Plugin lifecycle (Sprint 8)
- ✅ **Plugin Isolation**: Namespace isolation (Sprint 8)
- ✅ **Async Database**: BotDatabase with SQLAlchemy async (Sprint 11)

**Testing Dependencies**:
- ✅ **pytest-asyncio**: Async test support
- ✅ **pytest-cov**: Coverage reporting
- ✅ **NATS test fixtures**: Integration testing

### 17.2 External Dependencies

**Python Packages** (already in requirements.txt):
- `nats-py` - NATS client
- `sqlalchemy[asyncio]` - Database ORM
- `aiosqlite` - Async SQLite driver
- `asyncpg` - Async PostgreSQL driver (production)
- `alembic` - Migrations

**No New Dependencies**: Sprint A uses existing infrastructure only.

### 17.3 Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Database migration fails** | Low | High | Test migration on SQLite + PostgreSQL before commit |
| **Performance below targets** | Low | Medium | Performance tests in CI, fail if <1000 ops/sec |
| **Plugin isolation broken** | Low | Critical | 10+ security tests enforce isolation |
| **NATS subject wildcard issues** | Low | Medium | Integration tests verify wildcard subscriptions |
| **TTL cleanup too slow** | Low | Low | Performance test ensures <1s for 10k keys |
| **Value size limit insufficient** | Medium | Low | 64KB adequate for MVP, increase in Sprint B if needed |
| **JSON serialization errors** | Low | Medium | Comprehensive tests for all JSON types |
| **Backward compatibility break** | Low | High | No changes to existing DatabaseService subjects |

**Risk Summary**: Low overall risk. Foundation sprint uses proven infrastructure (SQLAlchemy, NATS, Alembic) with no new external dependencies.

### 17.4 Rollback Plan

**If Sprint A Fails**:

1. **Revert Migration**:
   ```bash
   alembic downgrade -1
   ```

2. **Remove Code**:
   - Revert sorties 1-4
   - DatabaseService unchanged (no `db.kv.*` subscriptions)

3. **No Data Loss**:
   - `plugin_kv_storage` table dropped cleanly
   - No existing plugin data affected

**Rollback Tested**: Alembic downgrade migration tested in Sortie 1 acceptance criteria.

---

## 18. Sprint Acceptance Criteria

### 18.1 Functional Acceptance

**Core Operations**:
- [ ] ✅ Set operation stores value and returns success
- [ ] ✅ Get operation retrieves value or returns exists=false
- [ ] ✅ Delete operation removes value (idempotent)
- [ ] ✅ List operation returns filtered keys

**TTL Support**:
- [ ] ✅ Set with TTL expires after specified time
- [ ] ✅ Get returns exists=false for expired keys
- [ ] ✅ Cleanup task removes expired keys automatically

**Plugin Isolation**:
- [ ] ✅ Plugin A cannot read Plugin B's keys
- [ ] ✅ Plugin A cannot delete Plugin B's keys
- [ ] ✅ List operation scoped to plugin

**NATS Integration**:
- [ ] ✅ Set via `db.kv.<plugin>.set` subject
- [ ] ✅ Get via `db.kv.<plugin>.get` (request/reply)
- [ ] ✅ Delete via `db.kv.<plugin>.delete` subject
- [ ] ✅ List via `db.kv.<plugin>.list` (request/reply)

**Error Handling**:
- [ ] ✅ Invalid JSON returns `INVALID_JSON` error
- [ ] ✅ Missing field returns `MISSING_FIELD` error
- [ ] ✅ Value too large returns `VALUE_TOO_LARGE` error

### 18.2 Non-Functional Acceptance

**Performance**:
- [ ] ✅ Set operation p95 latency <10ms
- [ ] ✅ Get operation p95 latency <10ms
- [ ] ✅ Throughput ≥1,000 ops/sec (mixed workload)
- [ ] ✅ Cleanup performance <1s for 10k expired keys

**Testing**:
- [ ] ✅ Test coverage ≥85% overall
- [ ] ✅ 40+ unit tests (all passing)
- [ ] ✅ 25+ integration tests (all passing)
- [ ] ✅ 5+ performance tests (all passing)
- [ ] ✅ 10+ security tests (all passing)

**Code Quality**:
- [ ] ✅ All docstrings complete (Google style)
- [ ] ✅ Type hints present for all public functions
- [ ] ✅ No lint errors (flake8, mypy)
- [ ] ✅ Code review approved

**Documentation**:
- [ ] ✅ Plugin Developer Guide complete
- [ ] ✅ Architecture documentation updated
- [ ] ✅ API reference complete
- [ ] ✅ Migration guide (if applicable)

**Database**:
- [ ] ✅ Alembic migration applies cleanly (SQLite + PostgreSQL)
- [ ] ✅ Alembic migration reverses cleanly (downgrade)
- [ ] ✅ Indexes created as specified
- [ ] ✅ No breaking changes to existing schema

### 18.3 Sprint Completion Checklist

**Code**:
- [ ] All 4 sorties merged to main
- [ ] No failing tests in CI
- [ ] No open blockers or critical bugs
- [ ] Code reviewed by at least one other developer

**Deployment**:
- [ ] Migration tested on staging environment
- [ ] Performance verified on production-like data
- [ ] Rollback procedure tested

**Documentation**:
- [ ] All user-facing docs complete
- [ ] All developer docs complete
- [ ] Changelog updated

**Validation**:
- [ ] Manual testing completed (all user stories)
- [ ] Smoke test passes (basic operations work)
- [ ] No regressions in existing functionality

**Sign-Off**:
- [ ] Product Owner approval (sprint goals met)
- [ ] Tech Lead approval (code quality standards met)
- [ ] QA approval (test coverage adequate)

---

## 19. Future Enhancements (Out of Scope)

### 19.1 Deferred to Sprint 13

**Row Operations**:
- CRUD operations on structured records (not just KV)
- Schema migrations per plugin
- Foreign keys and relations
- Bulk insert/update operations

**Advanced List**:
- Pagination (offset + limit)
- Sorting (by created_at, updated_at)
- Filtering (WHERE clauses)

### 19.2 Deferred to Sprint 14

**Reference Implementation**:
- Complete example plugin using KV storage
- Migration guide from JSON files
- Performance optimization guide
- Troubleshooting playbook

**Developer Tooling**:
- CLI tool for inspecting KV storage (`rosey kv list`)
- Admin UI for viewing plugin data
- Data export/import tools

### 19.3 Deferred to Sprint 15

**Parameterized SQL**:
- Execute custom SQL queries (read-only)
- Prepared statements with parameters
- Result set streaming

**Advanced Features**:
- Transactions (multi-key atomic updates)
- Compare-and-swap (CAS) for counters
- Atomic increment/decrement
- Watch/subscribe to key changes

### 19.4 Production Hardening (Sprint 5/6)

**Security**:
- Rate limiting per plugin
- Encryption at rest
- Audit logging (who accessed what)

**Performance**:
- Caching layer (Redis)
- Read replicas (PostgreSQL)
- Connection pooling tuning

**Observability**:
- Prometheus metrics
- Grafana dashboards
- Alerting rules

### 19.5 V2 Features (Someday)

**Multi-Tenant**:
- Channel-scoped storage (not just plugin-scoped)
- User-scoped storage

**Expressive Queries**:
- JSONPath queries on values
- Full-text search
- Range queries (numeric, date)

**Distribution**:
- Multi-region replication
- Conflict resolution (CRDTs)
- Eventual consistency guarantees

---

## 20. Appendices

### 20.1 Glossary

**Terms**:
- **KV**: Key-Value storage (simple map/dictionary)
- **TTL**: Time-To-Live (expiration time)
- **NATS**: Message bus used for plugin-to-service communication
- **Subject**: NATS topic/channel (e.g., `db.kv.trivia.set`)
- **Request/Reply**: NATS pattern where sender waits for response
- **Publish/Subscribe**: NATS pattern where sender doesn't wait for response
- **Plugin**: Self-contained bot extension (trivia, quote-db, etc.)
- **Isolation**: Plugin A cannot access Plugin B's data
- **Upsert**: Insert if not exists, update if exists
- **ORM**: Object-Relational Mapping (SQLAlchemy)
- **Alembic**: Database migration tool

### 20.2 References

**Internal Documents**:
- Sprint 6a: NATS Event Bus (`docs/sprints/completed/6a-quicksilver/`)
- Sprint 9: DatabaseService NATS Integration
- Sprint 11: SQLAlchemy Migration (`docs/sprints/completed/11-The-Conversation/`)
- Plugin Manager: `bot/rosey/core/plugin_manager.py`
- Plugin Isolation: `bot/rosey/core/plugin_isolation.py`

**External Resources**:
- NATS.io Documentation: https://docs.nats.io/
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html
- Alembic Tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Python Type Hints: https://docs.python.org/3/library/typing.html

### 20.3 Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-22 | GitHub Copilot | Initial PRD creation |

### 20.4 Contact

**Sprint Owner**: Rosey-Robot Team  
**Slack Channel**: #rosey-storage-sprint  
**GitHub Issues**: Tag with `sprint-xxx-a`, `storage`, `kv`

---

**End of PRD: KV Storage Foundation (Sprint 12)**

**Document Stats**:
- **Words**: ~18,000
- **Sections**: 20
- **User Stories**: 12
- **Sorties**: 4
- **Estimated Duration**: 3-4 days
- **Test Coverage Target**: ≥85%

**Next Steps**:
1. Review and approve this PRD
2. Create Sprint 12 branch
3. Begin Sortie 1: KV Schema & Model
4. Follow implementation plan (Section 10)

**Related PRDs** (Coming Next):
- Sprint 13: Row Operations (CRUD with migrations)
- Sprint 14: Reference Implementation
- Sprint 15: Parameterized SQL

---

*This document is a living document and will be updated as implementation progresses. All changes require Tech Lead approval.*

