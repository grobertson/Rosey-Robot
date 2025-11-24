# Plugin Storage Architecture Plan

## Overview

Design and implement a comprehensive database-service API for plugins to store and retrieve data. The system provides multiple storage tiers to balance simplicity and power, with strong isolation guarantees between plugins.

## Architecture Principles

1. **Plugin Isolation**: Each plugin operates in its own namespace/schema, enforced by database-service
2. **NATS-First**: All storage operations flow through NATS subjects, no direct database access
3. **Progressive Complexity**: Start with simple KV, graduate to structured rows, escape hatch to SQL
4. **Migration Management**: Plugin-owned Alembic migrations executed by database-service
5. **Dev vs Prod**: SQLite allowed for local development, database-service required for production

## Storage Tiers

### Tier 1: Key-Value Store (KV)
**Purpose**: Simple persistence for configuration, flags, counters, small data blobs

**NATS Subjects**:
- `db.kv.<plugin>.set` - Store key/value with optional TTL
- `db.kv.<plugin>.get` - Retrieve value by key
- `db.kv.<plugin>.delete` - Remove key
- `db.kv.<plugin>.list` - List all keys with optional prefix filter

**Example Payloads**:
```json
// Set
{
  "key": "last_quote_id",
  "value": "42",
  "ttl": 3600
}

// Get
{
  "key": "last_quote_id"
}
// Response: {"value": "42", "exists": true}

// List
{
  "prefix": "config_"
}
// Response: {"keys": ["config_trigger", "config_cooldown"]}
```

**Use Cases**:
- Configuration values
- Feature flags
- Simple counters
- Session tokens
- Cache data

### Tier 2: Named Row Operations
**Purpose**: Structured CRUD for entities with typed fields, indexes, relationships

**NATS Subjects**:
- `db.row.<plugin>.insert` - Create new row
- `db.row.<plugin>.select` - Fetch rows by ID or criteria
- `db.row.<plugin>.search` - Query with filters and pagination
- `db.row.<plugin>.update` - Modify existing rows
- `db.row.<plugin>.delete` - Remove rows

**Example Payloads**:
```json
// Insert
{
  "table": "quotes",
  "data": {
    "text": "Keep circulating the tapes",
    "author": "MST3K",
    "added_by": "groberts",
    "timestamp": "2025-11-22T10:30:00Z"
  }
}
// Response: {"id": 42, "created": true}

// Search with operators
{
  "table": "trivia_stats",
  "filters": {
    "user_id": {"$eq": "groberts"},
    "score": {"$gte": 100}
  },
  "sort": {"field": "score", "order": "desc"},
  "limit": 10
}

// Update with atomic operators
{
  "table": "trivia_stats",
  "filters": {"user_id": "groberts"},
  "operations": {
    "score": {"$inc": 10},
    "last_answer": {"$set": "correct"},
    "best_streak": {"$max": 5}
  }
}
```

**Supported Operators**:
- Filters: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$like`
- Updates: `$set`, `$inc`, `$dec`, `$max`, `$min`, `$push` (arrays)

**Use Cases**:
- Quote database
- Trivia statistics
- User preferences
- Leaderboards
- Activity logs

### Tier 3: Parameterized SQL (Advanced)
**Purpose**: Complex queries, joins, aggregations, custom schemas for power users

**NATS Subjects**:
- `db.sql.<plugin>.query` - Execute parameterized SQL with safety checks

**Example Payload**:
```json
{
  "query": "SELECT user_id, COUNT(*) as wins FROM trivia_rounds WHERE result = :result AND timestamp > :since GROUP BY user_id ORDER BY wins DESC LIMIT :limit",
  "params": {
    "result": "win",
    "since": "2025-11-01",
    "limit": 10
  }
}
```

**Safety Guardrails**:
- Parameterized queries only (no string interpolation)
- Schema-scoped (plugin can only access its own tables)
- Query timeout limits
- Result size limits
- Rate limiting per plugin

**Use Cases**:
- Complex analytics
- Multi-table joins
- Aggregations and reporting
- Performance-critical queries
- Migration from legacy systems

## Migration System

**NATS Subject**: `db.migrate.<plugin>`

**Payload**:
```json
{
  "action": "apply",
  "migrations": [
    {
      "version": "001_create_quotes",
      "up": "CREATE TABLE quotes (id SERIAL PRIMARY KEY, text TEXT NOT NULL, author VARCHAR(255), added_by VARCHAR(255), timestamp TIMESTAMPTZ DEFAULT NOW());",
      "down": "DROP TABLE quotes;"
    }
  ]
}
```

**Features**:
- Alembic-style versioning
- Up/down migrations
- Atomic application
- Rollback support
- Version tracking per plugin

## Two-PRD Approach

### PRD A: Plugin Storage Foundation
**Scope**: KV tier + Named Operations tier + Migration hooks

**User Stories**:
- GH-PSF-001: Plugin stores key/value config data
- GH-PSF-002: Plugin performs CRUD on structured entities
- GH-PSF-003: Plugin runs schema migrations
- GH-PSF-004: Database service enforces plugin isolation
- GH-PSF-005: Developer tests storage locally with SQLite

**Deliverables**:
- Database service KV API implementation
- Database service named row API implementation
- Migration runner for plugin schemas
- SQLite dev mode support
- Unit tests (85%+ coverage)
- Integration tests with sample plugins
- API documentation

**Estimated Complexity**: 3-4 commits (Foundation, CRUD, Migrations, Testing)

### PRD B: Advanced Plugin Storage (Parameterized SQL)
**Scope**: SQL tier with safety guardrails

**User Stories**:
- GH-APS-001: Power user executes complex queries
- GH-APS-002: System prevents SQL injection
- GH-APS-003: System enforces resource limits
- GH-APS-004: Developer profiles query performance

**Deliverables**:
- Parameterized SQL API implementation
- Query parser and validator
- Schema isolation enforcement
- Timeout and rate limiting
- Query profiling tools
- Security audit documentation

**Estimated Complexity**: 2-3 commits (SQL API, Safety, Performance)

## Sprint Folder Organization

### Current State
- `docs/sprints/active/12-Funny-Games/` - Needs to move to upcoming with XXX- prefix
- `docs/sprints/upcoming/12-Assault-on-Precinct-13/` - Plugin system foundation
- `docs/sprints/upcoming/13-Across-110th-Street/` - Multi-platform support (duplicate)
- `docs/sprints/upcoming/14-Funny-Games/` - Old game specs (merge/archive)
- `docs/sprints/upcoming/15-Across-110th-Street/` - Multi-platform support (duplicate)
- `docs/sprints/upcoming/99-The-Expandables/` - Future expansion

### Target State
All planning sprints get `XXX-` prefix to prevent renumbering churn:

- `docs/sprints/upcoming/XXX-Plugin-Storage-Foundation/` ✅ Created
- `docs/sprints/upcoming/XXX-Plugin-Storage-Advanced/` - To be created (PRD B)
- `docs/sprints/upcoming/XXX-Funny-Games/` - Move from active + merge with 14
- `docs/sprints/upcoming/XXX-Assault-on-Precinct-13/` - Rename from 12
- `docs/sprints/upcoming/XXX-Multi-Platform-Support/` - Merge 13 + 15
- `docs/sprints/upcoming/XXX-The-Expandables/` - Rename from 99

### Movie Name Suggestions for Storage Sprints

**Foundation PRD Options**:
- `XXX-Deep-Storage` (Deep Star Six reference)
- `XXX-Storage-24` (Storage 24 - 2012 creature feature)
- `XXX-The-Vault` (Various heist films)
- `XXX-The-Keep` (1983 horror film)
- `XXX-Cube` (1997 sci-fi - isolated rooms/data cells)

**Advanced SQL PRD Options**:
- `XXX-Raw-Deal` (Raw SQL, get it?)
- `XXX-Maximum-Overdrive` (Power features)
- `XXX-Escape-from-New-York` (SQL escape hatch)
- `XXX-The-Running-Man` (Query runner)
- `XXX-Death-Race-2000` (Performance racing)

## Plugin Updates Required

After storage foundation is complete, update these plugin specs:

### Quote Database Plugin
**Current**: Direct SQLite access (monolithic assumption)
**Update To**: 
```
- Use db.kv.quote-db.set/get for last_id counter
- Use db.row.quote-db.insert for new quotes
- Use db.row.quote-db.search for quote lookups
- Use db.row.quote-db.select for random quote
- Use db.migrate.quote-db for schema setup
```

### Trivia Plugin
**Current**: In-memory state (no persistence)
**Update To**:
```
- Use db.kv.trivia.* for active game state
- Use db.row.trivia.insert for game history
- Use db.row.trivia.update for user stats (atomic $inc)
- Use db.row.trivia.search for leaderboards
- Use db.migrate.trivia for schema setup
```

### Dice Roller Plugin
**Current**: Stateless (no changes needed)
**Update**: Maybe add `db.kv.dice.set` for user-defined macros (optional)

### Inspector Plugin
**Current**: Not yet specced
**Update**: Add storage inspection commands:
```
- !inspect storage quote-db - Show tables and row counts
- !inspect kv llm - List KV keys for plugin
- !inspect migrations playlist - Show migration history
```

## Dependencies and Sequencing

**Prerequisite**: None (storage is foundational)

**Blocks**:
- XXX-Funny-Games sprint (needs storage for quote-db, trivia)
- XXX-Assault-on-Precinct-13 sprint (plugin system needs storage)
- Any stateful plugin development

**Recommended Order**:
1. Foundation PRD → Implement KV + named operations + migrations
2. Test with quote-db plugin as reference implementation
3. Advanced PRD → Implement SQL tier
4. Test with trivia plugin for complex queries
5. Update all plugin specs to use new storage APIs
6. Proceed with Funny Games sprint

## Open Questions

1. **Naming**: Which movie names do you prefer for the two storage sprints?
2. **Folder Consolidation**: 
   - Merge 13-Across-110th-Street + 15-Across-110th-Street into one XXX-Multi-Platform-Support?
   - Merge 14-Funny-Games into XXX-Funny-Games (from active)?
   - Archive or delete old game specs that assume monolithic architecture?
3. **Weather Plugin**: Remove from Funny Games lineup? Feels thematically weak.
4. **Priority**: Should storage Foundation go active immediately, or do you want to review both PRDs first?

## Success Metrics

**Foundation Sprint**:
- KV API handles 1000+ ops/sec
- Named operations support all listed operators
- Migration system applies 10+ migrations cleanly
- SQLite dev mode has feature parity with Postgres
- 85%+ test coverage
- Zero cross-plugin data leaks in isolation tests

**Advanced Sprint**:
- SQL queries execute with <100ms p95 latency
- Parameterization prevents all injection attempts
- Resource limits prevent runaway queries
- Query profiling identifies bottlenecks
- Security audit finds zero vulnerabilities

## Timeline Estimate

**Foundation**: 4-6 days (3-4 commits)
**Advanced**: 3-4 days (2-3 commits)
**Total**: ~1.5-2 weeks for complete storage system

---

## Next Actions

1. Get user input on movie-themed naming preferences
2. Finalize folder reorganization (move active/12-Funny-Games, rename all numbered sprints)
3. Create PRD B for Advanced SQL layer
4. Decide which storage sprint goes active first
5. Begin implementation with nano-sprint workflow (PRD → SPECs → Commits)
