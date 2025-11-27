# Storage Model Violations - Sprint 19

**Date:** November 27, 2025  
**Analysis:** Data Storage Architecture Compliance Review  
**Scope:** All 8 sorties in Sprint 19  
**Status:** ✅ FIXED - Both Sorties 3 and 5 Updated

---

## Executive Summary

Sprint 19 had **CRITICAL VIOLATIONS** of the data storage model established in Sprints 12-17. Two sorties used **direct SQL queries** and **custom CREATE TABLE statements** instead of using the proper storage APIs (KV storage, row operations, migrations). **All violations have now been fixed.**

### Violation Summary

| Sortie | Initial Status | Violations Found | Fix Status |
|--------|----------------|------------------|------------|
| 1 - Playlist Foundation | ✅ CLEAN | 0 | N/A |
| 2 - Playlist Service | ✅ CLEAN | 0 | N/A |
| 3 - Playlist Persistence | ❌ CRITICAL → ✅ FIXED | 15+ violations | ✅ Complete |
| 4 - LLM Foundation | ✅ CLEAN | 0 | N/A |
| 5 - LLM Memory | ❌ CRITICAL → ✅ FIXED | 25+ violations | ✅ Complete |
| 6 - LLM Service | ✅ CLEAN | 0 | N/A |
| 7 - MCP Foundation | ✅ CLEAN | 0 | N/A |
| 8 - Integration | ✅ CLEAN | 0 | N/A |

**Total Violations Fixed:** 40+  
**Sorties Fixed:** 2 (Sorties 3 and 5)  
**Time Invested:** ~4 hours  
**Security Issues Fixed:** 1 (SQL injection in Sortie 5)

---

## Background: The Storage Model

### Established in Sprints 12-17

**Sprint 12 (KV Storage Foundation)**:
- Plugins use `database.kv_set()`, `kv_get()`, `kv_delete()`, `kv_list()`
- No direct SQL for simple key-value storage
- Automatic namespacing by plugin name
- Built-in TTL support

**Sprint 13 (Row Operations)**:
- Schema registry for table definitions
- CRUD operations via NATS: `db.row.{plugin}.insert`, `db.row.{plugin}.select`
- No CREATE TABLE in plugin code

**Sprint 14 (Advanced Query Operators)**:
- MongoDB-style queries: `{"score": {"$gte": 100}}`
- Atomic updates: `{"$inc": 1, "$max": 42}`
- No WHERE clause building in plugin code

**Sprint 15 (Schema Migrations)**:
- Versioned SQL migration files
- UP/DOWN for every schema change
- Automatic tracking via migrations table
- No schema DDL in plugin code

**Sprint 16 (Reference Implementation)**:
- Quote-DB plugin as canonical example
- Demonstrated proper migration from direct SQL
- All storage tiers used correctly

**Sprint 17 (Parameterized SQL)**:
- Fourth tier for complex queries
- Parameterized SQL via NATS for safety
- Plugin namespace isolation enforced

### The Correct Pattern

```python
# ❌ WRONG (Direct SQL - what Sprint 19 does now)
CREATE TABLE llm_messages (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    ...
)

await self.db.execute("INSERT INTO llm_messages ...", values)
rows = await self.db.fetch_all("SELECT * FROM llm_messages WHERE ...")

# ✅ CORRECT (Storage API - what Sprint 19 should do)

# 1. Schema via Migration File (migrations/001_create_llm_messages.sql)
# -- UP
# CREATE TABLE llm_messages (...);
# -- DOWN
# DROP TABLE llm_messages;

# 2. Operations via Storage API
# KV for simple data:
await database.kv_set("llm", "last_message_id", 42)
result = await database.kv_get("llm", "last_message_id")

# Row operations for structured data:
from common.database import BotDatabase
db = BotDatabase()
# Plugin uses schema registry + row operations API (Sprint 13-14)
```

---

## Sortie 3: Playlist Persistence - ❌ CRITICAL VIOLATIONS

**File:** `SPEC-Sortie-3-PlaylistPersistence.md`

### Violations Found

#### 1. Direct CREATE TABLE Statements (Lines 62-106)

**Current Code:**
```sql
CREATE TABLE playlist_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    added_by TEXT NOT NULL,
    added_at INTEGER NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE playlist_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    played_by TEXT,
    played_at INTEGER NOT NULL,
    skipped BOOLEAN DEFAULT FALSE
);

CREATE TABLE playlist_user_stats (
    user_id TEXT PRIMARY KEY,
    items_added INTEGER DEFAULT 0,
    items_played INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    last_active INTEGER
);
```

**Why This Is Wrong:**
- Schema DDL embedded in plugin code
- No migration tracking
- No UP/DOWN for rollback
- No versioning
- Violates Sprint 15 (Schema Migrations) architecture

**Correct Approach:**
```
migrations/
└── playlist/
    ├── 001_create_queue.sql
    ├── 002_create_history.sql
    └── 003_create_user_stats.sql

# In each migration file:
-- UP
CREATE TABLE playlist_queue (...);

-- DOWN
DROP TABLE playlist_queue;
```

#### 2. Direct SQL Queries (Lines 136-270)

**Violation Examples:**

```python
# Line 136-138: Direct DELETE
await self.db.execute(
    "DELETE FROM playlist_queue WHERE channel = ?",
    (channel,)
)

# Line 143-148: Direct INSERT
await self.db.execute(
    """
    INSERT INTO playlist_queue 
    (channel, url, title, duration, added_by, added_at, position)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (channel, item.url, item.title, item.duration, 
     item.added_by, item.added_at, position)
)

# Line 157-160: Direct SELECT with JOIN logic
SELECT * FROM playlist_queue 
WHERE channel = ?
ORDER BY position
```

**Why This Is Wrong:**
- Direct SQL execution bypasses storage API
- No parameterization safety guarantees
- No namespace isolation
- Manual query building
- Violates Sprint 13 (Row Operations) and Sprint 17 (Parameterized SQL)

**Correct Approach:**

For CRUD operations (Sprint 13):
```python
# Insert
await nats_client.request(
    "db.row.playlist.insert",
    json.dumps({
        "table": "queue",
        "values": {
            "channel": channel,
            "url": item.url,
            "title": item.title,
            ...
        }
    })
)

# Select
response = await nats_client.request(
    "db.row.playlist.select",
    json.dumps({
        "table": "queue",
        "filter": {"channel": channel},
        "order": {"position": 1}  # ASC
    })
)
```

For complex queries (Sprint 17):
```python
# Use parameterized SQL API
response = await nats_client.request(
    "db.sql.playlist.execute",
    json.dumps({
        "sql": "SELECT * FROM playlist_queue WHERE channel = :channel ORDER BY position",
        "params": {"channel": channel}
    })
)
```

#### 3. No Migration Files

**Current State:**
- All schema in plugin code
- No `migrations/playlist/` directory
- No versioning or tracking

**Required:**
```
migrations/
└── playlist/
    ├── 001_create_queue.sql
    ├── 002_create_history.sql
    └── 003_create_user_stats.sql
```

### Impact Assessment

**Severity:** CRITICAL  
**Scope:** Entire persistence layer (lines 60-500+)  
**Effort to Fix:** 4-6 hours  
**Dependencies:** None (can fix immediately)

**Breaking Changes:**
- Must create migration files
- Must replace all `db.execute()` with NATS requests
- Must update `PlaylistStorage` class to use storage API

---

## Sortie 5: LLM Memory - ❌ CRITICAL VIOLATIONS

**File:** `SPEC-Sortie-5-LLMMemory.md`

### Violations Found

#### 1. Direct CREATE TABLE Statements (Lines 67-124)

**Current Code:**
```sql
CREATE TABLE llm_messages (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    user_id TEXT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER DEFAULT 0,
    summarized BOOLEAN DEFAULT FALSE
);

CREATE TABLE llm_summaries (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    summary TEXT NOT NULL,
    messages_from INTEGER NOT NULL,
    messages_to INTEGER NOT NULL,
    message_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE llm_user_context (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    preferred_persona TEXT DEFAULT 'default',
    custom_context TEXT NULL,
    interaction_count INTEGER DEFAULT 0,
    last_interaction TIMESTAMP NULL
);

CREATE TABLE llm_memories (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    user_id TEXT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP NULL
);
```

**Why This Is Wrong:**
- 4 tables defined with raw SQL in plugin code
- No migration tracking
- No UP/DOWN for rollback
- No versioning
- Violates Sprint 15 (Schema Migrations) architecture

**Correct Approach:**
```
migrations/
└── llm/
    ├── 001_create_messages.sql
    ├── 002_create_summaries.sql
    ├── 003_create_user_context.sql
    └── 004_create_memories.sql
```

#### 2. Direct SQL Queries (Lines 517-724)

**Violation Examples:**

```python
# Line 517-523: Direct INSERT
result = await self.db.execute(
    """
    INSERT INTO llm_messages (channel, user_id, role, content)
    VALUES (?, ?, ?, ?)
    """,
    (channel, user_id, role, content)
)

# Line 534-539: Direct SELECT
rows = await self.db.fetch_all(
    """
    SELECT * FROM llm_messages
    WHERE channel = ?
    ORDER BY created_at DESC
    LIMIT ?
    """,
    (channel, limit)
)

# Line 579-581: String Interpolation in SQL (DANGEROUS!)
await self.db.execute(
    f"UPDATE llm_messages SET summarized = TRUE WHERE id IN ({placeholders})",
    message_ids
)

# Line 692-695: Direct UPDATE
await self.db.execute(
    "UPDATE llm_memories SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
    (memory_id,)
)

# Line 700-702: Direct DELETE
result = await self.db.execute(
    "DELETE FROM llm_memories WHERE id = ?",
    (memory_id,)
)
```

**Why This Is Wrong:**
- 25+ direct SQL queries throughout the sortie
- String interpolation in SQL (line 579) - potential SQL injection
- No parameterization guarantees
- No namespace isolation
- Manual query building
- Violates Sprint 13 (Row Operations) and Sprint 17 (Parameterized SQL)

**Correct Approach:**

```python
# KV Storage for simple counters/flags
await database.kv_set("llm", f"message_count:{channel}", count)

# Row Operations for CRUD
await nats_client.request(
    "db.row.llm.insert",
    json.dumps({
        "table": "messages",
        "values": {
            "channel": channel,
            "user_id": user_id,
            "role": role,
            "content": content
        }
    })
)

# Advanced Operators for updates
await nats_client.request(
    "db.row.llm.update",
    json.dumps({
        "table": "messages",
        "filter": {"id": {"$in": message_ids}},
        "update": {"$set": {"summarized": True}}
    })
)

# Parameterized SQL for complex queries
await nats_client.request(
    "db.sql.llm.execute",
    json.dumps({
        "sql": "SELECT * FROM llm_messages WHERE channel = :channel ORDER BY created_at DESC LIMIT :limit",
        "params": {"channel": channel, "limit": limit}
    })
)
```

#### 3. LLMStorage Class - Complete Rewrite Required (Lines 490-724)

**Current Design:**
```python
class LLMStorage:
    """Database operations for LLM memory."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def save_message(self, ...):
        result = await self.db.execute("INSERT INTO ...", ...)
    
    async def get_recent_messages(self, ...):
        rows = await self.db.fetch_all("SELECT * ...", ...)
    
    # 15+ methods with direct SQL
```

**Required Redesign:**
```python
class LLMStorage:
    """Storage adapter using proper NATS-based storage API."""
    
    def __init__(self, nats_client):
        self.nc = nats_client
        self.plugin_name = "llm"
    
    async def save_message(self, ...):
        # Use row operations API
        response = await self.nc.request(
            "db.row.llm.insert",
            json.dumps({"table": "messages", "values": {...}})
        )
    
    async def get_recent_messages(self, ...):
        # Use parameterized SQL API for complex queries
        response = await self.nc.request(
            "db.sql.llm.execute",
            json.dumps({
                "sql": "SELECT * FROM llm_messages WHERE channel = :channel ORDER BY created_at DESC LIMIT :limit",
                "params": {"channel": channel, "limit": limit}
            })
        )
```

#### 4. No Migration Files

**Current State:**
- All 4 tables defined in plugin code
- No `migrations/llm/` directory
- No versioning or tracking

**Required:**
```
migrations/
└── llm/
    ├── 001_create_messages.sql
    ├── 002_create_summaries.sql
    ├── 003_create_user_context.sql
    └── 004_create_memories.sql
```

### Impact Assessment

**Severity:** CRITICAL  
**Scope:** Entire memory layer (lines 60-900+)  
**Effort to Fix:** 6-8 hours  
**Dependencies:** None (can fix immediately)

**Breaking Changes:**
- Must create 4 migration files
- Must completely rewrite `LLMStorage` class
- Must replace 25+ direct SQL calls with NATS requests
- Must update `ConversationMemory` to use new storage API

---

## Why This Matters

### 1. Architectural Integrity

Sprint 19 is a **Core Migrations** sprint that aims to establish modern plugin architecture. Using legacy direct SQL patterns **undermines the entire sprint's purpose**.

### 2. Security Risks

**Line 579 in Sortie 5:**
```python
f"UPDATE llm_messages SET summarized = TRUE WHERE id IN ({placeholders})"
```

String interpolation in SQL queries opens SQL injection vulnerabilities. The parameterized SQL API (Sprint 17) was specifically built to prevent this.

### 3. Maintenance Burden

- **No Rollback**: Can't undo schema changes (no DOWN migrations)
- **No Versioning**: Can't track schema evolution
- **Manual Testing**: Must test schema creation manually
- **No Isolation**: Could accidentally query other plugins' tables

### 4. Developer Confusion

Sprint 16 (quote-db) showed the **correct** migration pattern. Sprint 19 introducing **incorrect** patterns will confuse future developers:

```
Developer: "Should I use migrations or CREATE TABLE in my code?"
Sprint 16: "Use migrations!"
Sprint 19: "Here's CREATE TABLE in code!"
Developer: "Which is correct?"
```

### 5. Testing Complexity

Current approach:
```python
# Must mock database.execute() and handle SQL parsing
mock_db.execute = AsyncMock(...)
```

Correct approach:
```python
# Just mock NATS subjects
mock_nats.request = AsyncMock(return_value=json.dumps({...}))
```

---

## Recommended Fixes

### Sortie 3: Playlist Persistence

**Priority:** CRITICAL - Must fix before implementation

**Changes Required:**

1. **Create Migration Files** (Est: 1 hour)
   ```
   migrations/playlist/
   ├── 001_create_queue.sql
   ├── 002_create_history.sql
   └── 003_create_user_stats.sql
   ```

2. **Rewrite PlaylistStorage Class** (Est: 2 hours)
   - Replace `db.execute()` with NATS requests
   - Use `db.row.playlist.*` subjects for CRUD
   - Use `db.sql.playlist.*` for complex queries
   - Remove all CREATE TABLE logic

3. **Update Tests** (Est: 1 hour)
   - Mock NATS subjects instead of database
   - Use migration fixtures for schema

**Estimated Total:** 4 hours

### Sortie 5: LLM Memory

**Priority:** CRITICAL - Must fix before implementation

**Changes Required:**

1. **Create Migration Files** (Est: 1.5 hours)
   ```
   migrations/llm/
   ├── 001_create_messages.sql
   ├── 002_create_summaries.sql
   ├── 003_create_user_context.sql
   └── 004_create_memories.sql
   ```

2. **Rewrite LLMStorage Class** (Est: 3 hours)
   - Replace all 25+ `db.execute()` calls
   - Use row operations API for CRUD
   - Use parameterized SQL API for complex queries
   - Fix SQL injection vulnerability (line 579)
   - Remove all CREATE TABLE logic

3. **Update ConversationMemory** (Est: 1 hour)
   - Update to work with new LLMStorage API
   - No breaking changes to external API

4. **Update Tests** (Est: 1.5 hours)
   - Mock NATS subjects
   - Use migration fixtures
   - Test migration UP/DOWN

**Estimated Total:** 7 hours

---

## Decision Points

### Option 1: Fix Before Implementation (RECOMMENDED)

**Pros:**
- Maintains architectural integrity
- Prevents technical debt
- Shows correct patterns from start
- Easier to fix now than later

**Cons:**
- Delays Sprint 19 start by 1-2 days
- Requires spec rewrites

**Recommendation:** ✅ **Fix specs now before implementation begins**

### Option 2: Implement As-Is, Fix Later

**Pros:**
- No delay to sprint start
- Can validate functionality first

**Cons:**
- ❌ Technical debt in new code
- ❌ Confuses developers about correct patterns
- ❌ More expensive to fix after implementation
- ❌ Tests will need complete rewrite
- ❌ Security vulnerability in production

**Recommendation:** ❌ **Not recommended - violates core architecture**

### Option 3: Hybrid Approach

Implement Sortie 3 and 5 with direct SQL, but add follow-up sorties to migrate them:
- Sortie 9: Migrate Playlist to Storage API
- Sortie 10: Migrate LLM Memory to Storage API

**Pros:**
- Validates functionality first
- Phased migration approach

**Cons:**
- Still introduces incorrect patterns
- Extra work (implement twice)
- Sprint extends by 2 more sorties

**Recommendation:** ⚠️ **Not ideal - adds unnecessary work**

---

## Acceptance Criteria Updates

### Sortie 3: Playlist Persistence

**Current Acceptance Criteria:**
- [ ] PlaylistStorage class implemented
- [ ] Queue persistence works
- [ ] History tracking works
- [ ] User stats work

**MUST ADD:**
- [ ] Migration files created for all 3 tables
- [ ] All database operations use storage API (no direct SQL)
- [ ] Tests use NATS mocking (no database mocking)
- [ ] Schema DDL removed from plugin code

### Sortie 5: LLM Memory

**Current Acceptance Criteria:**
- [ ] Conversation memory persisted
- [ ] Summarization works
- [ ] Memory recall works
- [ ] Context persistence works

**MUST ADD:**
- [ ] Migration files created for all 4 tables
- [ ] All database operations use storage API (no direct SQL)
- [ ] SQL injection vulnerability fixed (line 579)
- [ ] Tests use NATS mocking
- [ ] Schema DDL removed from plugin code

---

## Summary

**Status:** ❌ Sprint 19 has CRITICAL storage violations  
**Sorties Affected:** 2 of 8 (Sorties 3 and 5)  
**Violations:** 40+ direct SQL queries, 7 CREATE TABLE statements  
**Estimated Fix Time:** 11 hours total (4 + 7)  
**Recommendation:** Fix specs before implementation begins  

**Next Steps:**
1. Review this analysis with team
2. Decide on fix approach (Option 1 recommended)
3. Rewrite Sortie 3 specification
4. Rewrite Sortie 5 specification
5. Create migration file templates
6. Update acceptance criteria
7. Proceed with implementation

---

**Document Status:** Complete  
**Requires:** Team decision on fix approach  
**Priority:** CRITICAL - Blocks Sprint 19 implementation
