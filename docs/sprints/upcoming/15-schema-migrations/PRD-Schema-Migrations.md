# PRD: Schema Migrations (Sprint 15)

**Version**: 1.0  
**Status**: Draft  
**Sprint**: 15 (Schema Migrations)  
**Estimated Duration**: 4-5 days  
**Estimated Sorties**: 4 sorties  
**Prerequisites**: Sprint 13 (Row Operations Foundation)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Context](#2-problem-statement--context)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Success Metrics](#4-success-metrics)
5. [User Personas](#5-user-personas)
6. [User Stories](#6-user-stories)
7. [Technical Architecture](#7-technical-architecture)
8. [Migration File Format](#8-migration-file-format)
9. [NATS API Specifications](#9-nats-api-specifications)
10. [Migration Execution Engine](#10-migration-execution-engine)
11. [Implementation Plan](#11-implementation-plan)
12. [Testing Strategy](#12-testing-strategy)
13. [Performance Requirements](#13-performance-requirements)
14. [Security & Safety](#14-security--safety)
15. [Error Handling](#15-error-handling)
16. [Observability](#16-observability)
17. [Documentation Requirements](#17-documentation-requirements)
18. [Dependencies & Risks](#18-dependencies--risks)
19. [Sprint Acceptance Criteria](#19-sprint-acceptance-criteria)
20. [Future Enhancements](#20-future-enhancements)
21. [Appendices](#21-appendices)

---

## 1. Executive Summary

### 1.1 Overview

Sprint 15 introduces **database schema migrations** for plugins, enabling safe schema evolution without data loss. Plugins can add columns, create indexes, modify constraints, and rollback changes through versioned migration files managed by the database service.

### 1.2 Key Features

**Migration Management**:
- Versioned migration files (001_create_table.sql, 002_add_column.sql, etc.)
- Up/down migrations for rollback support
- Automatic migration tracking per plugin
- Dependency resolution (migration ordering)

**Supported Operations**:
- ADD COLUMN (with defaults, constraints)
- DROP COLUMN (with safety checks)
- CREATE INDEX / DROP INDEX
- ALTER COLUMN (type changes, nullability)
- ADD CONSTRAINT / DROP CONSTRAINT
- RENAME TABLE / RENAME COLUMN

**Safety Features**:
- Dry-run mode (preview changes without executing)
- Rollback to previous version
- Automatic backups before destructive operations
- Migration locking (prevent concurrent migrations)

### 1.3 Sprint Scope

**In Scope**:
- Migration file format (SQL-based, up/down)
- NATS API for migration operations (apply, rollback, status)
- Migration execution engine with transaction support
- Version tracking table (`plugin_schema_migrations`)
- Safety checks (column exists, data loss warnings)
- Rollback support (down migrations)

**Out of Scope** (Deferred):
- Data migrations (INSERT/UPDATE in migrations) - Sprint 16
- Complex transformations (CASE statements, data cleanup) - Sprint 16
- Zero-downtime migrations (online schema changes) - V2
- Migration templates/generators - V2
- Cross-plugin migrations (foreign keys across plugins) - Never (violates isolation)

### 1.4 Why This Matters

**Current Pain** (Sprint 13):
```python
# Plugin registers schema - but what if schema needs to change later?
schema = {
    'table': 'quotes',
    'fields': [
        {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
        {'name': 'text', 'type': 'TEXT', 'nullable': False}
    ]
}

# If we want to add 'rating' field later - CANNOT DO THIS!
# Calling register_schema again with different schema → SCHEMA_CONFLICT error
```

**After Sprint 15**:
```python
# Migration 001: Create initial table
# File: migrations/001_create_quotes.sql
"""
-- UP
CREATE TABLE quote_db_quotes (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    author VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- DOWN
DROP TABLE quote_db_quotes;
"""

# Migration 002: Add rating column
# File: migrations/002_add_rating.sql
"""
-- UP
ALTER TABLE quote_db_quotes ADD COLUMN rating INTEGER DEFAULT 0;
CREATE INDEX idx_quotes_rating ON quote_db_quotes(rating);

-- DOWN
DROP INDEX idx_quotes_rating;
ALTER TABLE quote_db_quotes DROP COLUMN rating;
"""

# Apply migrations via NATS
response = await nats.request('db.migrate.quote-db.apply', json.dumps({
    'target_version': 2  # Apply up to migration 002
}).encode())
```

### 1.5 Migration Lifecycle

```
Initial State: No tables
    ↓
[001_create_quotes] → quote_db_quotes table created
    ↓
[002_add_rating] → rating column added, index created
    ↓
[003_add_user_fk] → user_id column added, constraint created
    ↓
Rollback to version 2 ← [003 DOWN] → constraint dropped, column removed
    ↓
Current State: quote_db_quotes with id, text, author, timestamp, rating
```

---

## 2. Problem Statement & Context

### 2.1 Current Limitations

**Sprint 13 Schema Registration**:
- One-time schema definition (no evolution)
- Schema conflicts rejected (cannot modify existing tables)
- Manual database alterations required (breaks automation)
- No rollback mechanism (destructive changes permanent)

### 2.2 Real-World Scenarios

**Scenario 1: Adding Features**
- Quote-db plugin adds "favorites" feature
- Needs `favorite_count INTEGER` column
- Currently: Manual ALTER TABLE or recreate database
- With migrations: Apply `003_add_favorite_count.sql`

**Scenario 2: Performance Optimization**
- Trivia plugin searches by `difficulty` field frequently
- Needs index on `difficulty` column
- Currently: Manual CREATE INDEX
- With migrations: Apply `004_index_difficulty.sql`

**Scenario 3: Bug Fix Rollback**
- Migration 005 adds column with wrong type
- Data import fails, need to revert
- Currently: Manual DROP COLUMN, hope for no data loss
- With migrations: Run `db.migrate.rollback` to version 004

### 2.3 Database Support

**PostgreSQL** (Production):
- Full DDL support (ALTER TABLE, CREATE INDEX, etc.)
- Transaction-safe DDL (can rollback schema changes)
- Advisory locks (prevent concurrent migrations)

**SQLite** (Development):
- Limited ALTER TABLE support (can add columns, cannot drop easily)
- No transactional DDL (schema changes commit immediately)
- Workaround: Table recreation for complex changes

---

## 3. Goals & Non-Goals

### 3.1 Goals

**Primary Goals**:
1. **Safe Schema Evolution**: Plugins evolve schemas without data loss
2. **Version Control**: Migration history tracked, auditable
3. **Rollback Support**: Undo recent migrations cleanly
4. **Developer Experience**: Simple SQL-based migration files
5. **Automation**: Migrations applied automatically on plugin startup

**Secondary Goals**:
6. **Safety Checks**: Detect destructive operations, warn before execution
7. **Dry Run**: Preview migration effects without applying
8. **Plugin Isolation**: Plugin A migrations don't affect Plugin B

### 3.2 Non-Goals

**Explicitly Out of Scope**:
- ❌ Data migrations (INSERT/UPDATE/DELETE in migrations) - Use Sprint 16 reference implementation
- ❌ Complex data transformations (Python scripts in migrations)
- ❌ Zero-downtime migrations (online schema changes)
- ❌ Migration generators (auto-generate from schema diffs)
- ❌ Cross-database migrations (PostgreSQL → SQLite)
- ❌ Cross-plugin foreign keys (violates isolation principle)

**Why These Limitations**:
- Data migrations need careful testing (reference implementation in Sprint 16)
- Zero-downtime requires connection pooling + read replicas (V2)
- Migration generators complex, error-prone (manual SQL safer)

---

## 4. Success Metrics

### 4.1 Functional Metrics

**Before Sprint 15**:
- Schema changes: Manual SQL scripts
- Rollback capability: None (hope for backups)
- Migration tracking: None
- Plugin startup time: <500ms

**After Sprint 15**:
- Schema changes: Automated via migrations
- Rollback capability: One command (`db.migrate.rollback`)
- Migration tracking: Version table per plugin
- Plugin startup time: <1000ms (includes migration check)

### 4.2 Developer Experience Metrics

**Success Indicators**:
- Migration application: <5 seconds for typical migration
- Migration authoring: <5 minutes to write simple migration
- Rollback time: <3 seconds
- Zero data loss during migrations (with proper down migrations)

### 4.3 Reliability Metrics

**Targets**:
- Migration success rate: >99%
- Failed migration recovery: 100% (automatic rollback)
- Concurrent migration conflicts: 0 (locking prevents)

---

## 5. User Personas

### 5.1 Alex - Plugin Developer

**Profile**: Builds and maintains plugins, adds features over time

**Needs**:
- Add columns to existing tables
- Create indexes for performance
- Rename columns for clarity
- Rollback bad migrations quickly

**Pain Points**:
- Manual ALTER TABLE commands error-prone
- No version history of schema changes
- Fear of breaking production database

**Success Scenario**:
```python
# Alex adds new feature to quote-db
# 1. Write migration file: 003_add_tags.sql
# 2. Test locally with dry-run
# 3. Apply migration: db.migrate.apply
# 4. If issues, rollback: db.migrate.rollback
# 5. Migration tracked in version table
```

### 5.2 Jordan - System Administrator

**Profile**: Manages Rosey deployments, troubleshoots production issues

**Needs**:
- View migration history per plugin
- Rollback failed migrations
- Apply pending migrations after updates
- Audit schema changes

**Pain Points**:
- Manual schema tracking (spreadsheets)
- No automated rollback mechanism
- Uncertainty about schema state

**Success Scenario**:
```bash
# Jordan deploys new plugin version
# 1. Check migration status: db.migrate.status
# 2. See pending migrations: [004_add_stats, 005_index_user]
# 3. Apply automatically on startup
# 4. Log shows: "Applied migrations 004, 005 successfully"
```

### 5.3 Sam - Power User / Contributor

**Profile**: Contributes to plugins, reviews PRs, tests features

**Needs**:
- Understand schema changes in PRs
- Test migrations locally before merge
- Ensure migrations are reversible

**Pain Points**:
- Schema changes buried in code
- No way to test rollback scenarios
- Production surprises from schema changes

**Success Scenario**:
```
# Sam reviews PR with new migration
# 1. Sees: migrations/006_add_premium.sql in PR
# 2. Reads UP/DOWN migrations clearly
# 3. Tests locally: apply → test → rollback → test
# 4. Approves PR with confidence
```

---

## 6. User Stories

### 6.1 GH-MIG-001: Add Column to Existing Table

**As a** plugin developer  
**I want to** add a new column to an existing table  
**So that** I can store additional data without recreating the table

**Acceptance Criteria**:
- [ ] Write migration file with ADD COLUMN statement
- [ ] Apply migration via NATS (`db.migrate.quote-db.apply`)
- [ ] Column appears in table schema
- [ ] Existing data preserved
- [ ] Down migration removes column cleanly
- [ ] Default value applied to existing rows

**Example**:
```sql
-- UP
ALTER TABLE quote_db_quotes ADD COLUMN rating INTEGER DEFAULT 0;

-- DOWN
ALTER TABLE quote_db_quotes DROP COLUMN rating;
```

---

### 6.2 GH-MIG-002: Create Index for Performance

**As a** plugin developer  
**I want to** create an index on a frequently-queried column  
**So that** search operations are faster

**Acceptance Criteria**:
- [ ] Write migration file with CREATE INDEX statement
- [ ] Apply migration via NATS
- [ ] Index created in database
- [ ] Query performance improves
- [ ] Down migration drops index

**Example**:
```sql
-- UP
CREATE INDEX idx_quotes_author ON quote_db_quotes(author);
CREATE INDEX idx_quotes_rating ON quote_db_quotes(rating);

-- DOWN
DROP INDEX idx_quotes_rating;
DROP INDEX idx_quotes_author;
```

---

### 6.3 GH-MIG-003: Rollback Failed Migration

**As a** plugin developer  
**I want to** rollback a migration that caused issues  
**So that** I can restore the previous working state

**Acceptance Criteria**:
- [ ] Apply migration that introduces bug
- [ ] Call `db.migrate.quote-db.rollback`
- [ ] Down migration executes
- [ ] Schema returns to previous version
- [ ] Version table updated
- [ ] No data loss (if down migration written correctly)

**Example**:
```python
# Migration 005 failed, rollback to 004
response = await nats.request('db.migrate.quote-db.rollback', json.dumps({
    'target_version': 4
}).encode())
```

---

### 6.4 GH-MIG-004: View Migration History

**As a** system administrator  
**I want to** view all applied migrations for a plugin  
**So that** I can audit schema changes and troubleshoot issues

**Acceptance Criteria**:
- [ ] Call `db.migrate.quote-db.status`
- [ ] Response shows applied migrations with timestamps
- [ ] Response shows pending migrations (not yet applied)
- [ ] Response shows current version
- [ ] Clear indication of migration state

**Example Response**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "current_version": 3,
  "applied_migrations": [
    {
      "version": 1,
      "name": "create_quotes",
      "applied_at": "2025-11-20T10:00:00Z",
      "applied_by": "system"
    },
    {
      "version": 2,
      "name": "add_rating",
      "applied_at": "2025-11-21T14:30:00Z",
      "applied_by": "alex"
    },
    {
      "version": 3,
      "name": "index_author",
      "applied_at": "2025-11-22T09:15:00Z",
      "applied_by": "system"
    }
  ],
  "pending_migrations": [
    {
      "version": 4,
      "name": "add_tags"
    }
  ]
}
```

---

### 6.5 GH-MIG-005: Dry-Run Migration Preview

**As a** plugin developer  
**I want to** preview migration effects without applying  
**So that** I can verify SQL syntax and see changes before committing

**Acceptance Criteria**:
- [ ] Call `db.migrate.quote-db.apply` with `dry_run: true`
- [ ] Response shows SQL statements that would execute
- [ ] No actual schema changes made
- [ ] Version table not updated
- [ ] Can test multiple times safely

**Example**:
```python
response = await nats.request('db.migrate.quote-db.apply', json.dumps({
    'target_version': 4,
    'dry_run': true
}).encode())

# Response shows:
# "Would execute: ALTER TABLE quote_db_quotes ADD COLUMN tags TEXT[]"
# "Would execute: CREATE INDEX idx_quotes_tags ON quote_db_quotes USING GIN(tags)"
```

---

### 6.6 GH-MIG-006: Automatic Migration on Startup

**As a** plugin developer  
**I want** migrations to apply automatically when plugin starts  
**So that** schema stays in sync with code version

**Acceptance Criteria**:
- [ ] Plugin startup checks migration status
- [ ] Pending migrations auto-applied (if enabled)
- [ ] Plugin initialization waits for migrations
- [ ] Startup logs show migration activity
- [ ] Failed migrations prevent plugin start

**Example**:
```python
# In plugin on_ready()
async def on_ready(self):
    # Auto-migrate to latest version
    response = await self.nats.request('db.migrate.my-plugin.apply', json.dumps({
        'target_version': 'latest',
        'auto': True
    }).encode())
    
    if not json.loads(response.data)['success']:
        raise RuntimeError("Migration failed, cannot start plugin")
    
    # Continue plugin initialization...
```

---

### 6.7 GH-MIG-007: Rename Column Safely

**As a** plugin developer  
**I want to** rename a column for clarity  
**So that** code is more maintainable

**Acceptance Criteria**:
- [ ] Write migration with RENAME COLUMN statement
- [ ] Apply migration via NATS
- [ ] Column renamed in database
- [ ] Existing data preserved
- [ ] Down migration restores original name
- [ ] Queries using new name work

**Example**:
```sql
-- UP
ALTER TABLE quote_db_quotes RENAME COLUMN author TO author_name;

-- DOWN
ALTER TABLE quote_db_quotes RENAME COLUMN author_name TO author;
```

---

### 6.8 GH-MIG-008: Add NOT NULL Constraint

**As a** plugin developer  
**I want to** add a NOT NULL constraint to an existing column  
**So that** data quality is enforced

**Acceptance Criteria**:
- [ ] Write migration with ALTER COLUMN SET NOT NULL
- [ ] Apply migration (fails if NULLs exist)
- [ ] Constraint enforced on new inserts
- [ ] Down migration removes constraint

**Example**:
```sql
-- UP
-- First, update NULLs to default value
UPDATE quote_db_quotes SET author = 'Unknown' WHERE author IS NULL;
-- Then add constraint
ALTER TABLE quote_db_quotes ALTER COLUMN author SET NOT NULL;

-- DOWN
ALTER TABLE quote_db_quotes ALTER COLUMN author DROP NOT NULL;
```

---

### 6.9 GH-MIG-009: Drop Column with Safety Check

**As a** plugin developer  
**I want to** drop an unused column  
**So that** table structure stays clean

**Acceptance Criteria**:
- [ ] Write migration with DROP COLUMN statement
- [ ] System warns if column contains non-NULL data
- [ ] Apply migration drops column
- [ ] Data loss warning logged
- [ ] Down migration cannot restore data (lossy operation)

**Example**:
```sql
-- UP
ALTER TABLE quote_db_quotes DROP COLUMN deprecated_field;

-- DOWN
-- WARNING: Data loss! Column cannot be restored with original data
ALTER TABLE quote_db_quotes ADD COLUMN deprecated_field TEXT;
```

---

### 6.10 GH-MIG-010: Migration Locking (Prevent Concurrent Runs)

**As a** system administrator  
**I want** only one migration to run at a time  
**So that** concurrent migrations don't corrupt schema

**Acceptance Criteria**:
- [ ] First migration acquires lock
- [ ] Second concurrent migration waits or fails
- [ ] Lock released after migration completes
- [ ] Lock auto-released after timeout (5 minutes)
- [ ] Lock status visible in migration table

**Example**:
```
Time  | Process A              | Process B
------|------------------------|------------------------
10:00 | Acquire lock           | -
10:01 | Apply migration 004    | Attempt apply 005 → LOCKED
10:02 | Complete, release lock | -
10:03 | -                      | Retry, acquire lock
10:04 | -                      | Apply migration 005
10:05 | -                      | Complete, release lock
```

---

## 7. Technical Architecture

### 7.1 System Components

```
┌─────────────────┐
│  Plugin Code    │
│  (quote-db)     │
└────────┬────────┘
         │ NATS: db.migrate.quote-db.*
         ↓
┌─────────────────────────────────────────┐
│     DatabaseService                     │
│  ┌───────────────────────────────────┐  │
│  │  MigrationManager                 │  │
│  │  - Load migration files           │  │
│  │  - Parse UP/DOWN sections         │  │
│  │  - Validate SQL syntax            │  │
│  │  - Execute with transactions      │  │
│  │  - Track versions                 │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  MigrationExecutor                │  │
│  │  - Acquire migration lock         │  │
│  │  - Begin transaction              │  │
│  │  - Execute UP/DOWN SQL            │  │
│  │  - Update version table           │  │
│  │  - Commit or rollback             │  │
│  │  - Release lock                   │  │
│  └───────────────────────────────────┘  │
└─────────────────┬───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│         PostgreSQL / SQLite             │
│  ┌───────────────────────────────────┐  │
│  │  plugin_schema_migrations         │  │
│  │  - plugin_name                    │  │
│  │  - version                        │  │
│  │  - name                           │  │
│  │  - applied_at                     │  │
│  │  - applied_by                     │  │
│  │  - execution_time_ms              │  │
│  │  - checksum                       │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  quote_db_quotes (example)        │  │
│  │  - id, text, author, rating...    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 7.2 Component Responsibilities

**MigrationManager**:
- Discover migration files in plugin directories
- Parse migration files (extract UP/DOWN sections)
- Validate SQL syntax (basic checks)
- Determine pending migrations (current version → target version)
- Generate migration plan (ordered list of migrations to apply)

**MigrationExecutor**:
- Acquire advisory lock (PostgreSQL) or file lock (SQLite)
- Begin database transaction
- Execute UP or DOWN SQL statements
- Update `plugin_schema_migrations` table
- Commit transaction (success) or rollback (failure)
- Release lock

**Migration Version Table** (`plugin_schema_migrations`):
- Track which migrations applied per plugin
- Store checksum to detect file modifications
- Record execution time for performance monitoring
- Support multiple plugins (isolated via plugin_name column)

### 7.3 Migration Discovery

**File Locations**:
```
plugins/
├── quote-db/
│   ├── migrations/
│   │   ├── 001_create_quotes.sql
│   │   ├── 002_add_rating.sql
│   │   ├── 003_index_author.sql
│   │   └── 004_add_tags.sql
│   └── plugin.py
├── trivia/
│   ├── migrations/
│   │   ├── 001_create_stats.sql
│   │   ├── 002_add_difficulty.sql
│   │   └── 003_leaderboard_view.sql
│   └── plugin.py
```

**Naming Convention**:
- Format: `{version}_{description}.sql`
- Version: Zero-padded integer (001, 002, ...)
- Description: Snake_case, descriptive
- Examples: `001_create_table.sql`, `015_add_user_preferences.sql`

### 7.4 Data Flow: Apply Migration

```
1. Plugin → NATS: db.migrate.quote-db.apply {"target_version": 3}
2. DatabaseService receives request
3. MigrationManager.get_pending_migrations('quote-db', current=1, target=3)
   → Returns: [migration_002, migration_003]
4. MigrationExecutor.acquire_lock('quote-db')
5. For each migration (002, 003):
   a. Begin transaction
   b. Execute UP SQL
   c. Insert into plugin_schema_migrations (version=002, checksum=...)
   d. Commit transaction
6. MigrationExecutor.release_lock('quote-db')
7. DatabaseService → NATS Reply: {"success": true, "applied": [2, 3]}
```

### 7.5 Data Flow: Rollback Migration

```
1. Plugin → NATS: db.migrate.quote-db.rollback {"target_version": 1}
2. DatabaseService receives request
3. MigrationManager.get_rollback_migrations('quote-db', current=3, target=1)
   → Returns: [migration_003, migration_002] (reverse order)
4. MigrationExecutor.acquire_lock('quote-db')
5. For each migration (003, 002):
   a. Begin transaction
   b. Execute DOWN SQL
   c. Delete from plugin_schema_migrations (version=003)
   d. Commit transaction
6. MigrationExecutor.release_lock('quote-db')
7. DatabaseService → NATS Reply: {"success": true, "rolled_back": [3, 2]}
```

---

## 8. Migration File Format

### 8.1 File Structure

**SQL-Based Migrations**:
```sql
-- Migration: 002_add_rating
-- Description: Add rating column to quotes table
-- Author: alex
-- Date: 2025-11-22

-- UP
ALTER TABLE quote_db_quotes ADD COLUMN rating INTEGER DEFAULT 0;
CREATE INDEX idx_quotes_rating ON quote_db_quotes(rating);

-- DOWN
DROP INDEX idx_quotes_rating;
ALTER TABLE quote_db_quotes DROP COLUMN rating;
```

**Required Sections**:
- `-- UP`: SQL statements to apply migration
- `-- DOWN`: SQL statements to rollback migration

**Optional Metadata** (comments at top):
- Migration name
- Description
- Author
- Date

### 8.2 UP Section

**Purpose**: Apply schema changes (forward migration)

**Rules**:
- Must be valid SQL for target database (PostgreSQL/SQLite)
- Can contain multiple statements (separated by `;`)
- Should be idempotent where possible (IF NOT EXISTS)
- Must succeed completely or fail completely (transactional)

**Examples**:
```sql
-- UP: Add column with default
ALTER TABLE quote_db_quotes ADD COLUMN favorite_count INTEGER DEFAULT 0;

-- UP: Create index
CREATE INDEX IF NOT EXISTS idx_quotes_author ON quote_db_quotes(author);

-- UP: Add constraint
ALTER TABLE quote_db_quotes ADD CONSTRAINT check_rating CHECK (rating >= 0 AND rating <= 5);

-- UP: Multiple operations
ALTER TABLE quote_db_quotes ADD COLUMN tags TEXT[];
CREATE INDEX idx_quotes_tags ON quote_db_quotes USING GIN(tags);
UPDATE quote_db_quotes SET tags = '{}' WHERE tags IS NULL;
ALTER TABLE quote_db_quotes ALTER COLUMN tags SET NOT NULL;
```

### 8.3 DOWN Section

**Purpose**: Reverse schema changes (rollback migration)

**Rules**:
- Must undo all changes from UP section (in reverse order)
- Should restore schema to previous state
- May lose data for destructive operations (DROP COLUMN)
- Optional warnings for irreversible operations

**Examples**:
```sql
-- DOWN: Remove column (data loss!)
ALTER TABLE quote_db_quotes DROP COLUMN favorite_count;

-- DOWN: Drop index
DROP INDEX IF EXISTS idx_quotes_author;

-- DOWN: Remove constraint
ALTER TABLE quote_db_quotes DROP CONSTRAINT check_rating;

-- DOWN: Reverse multiple operations
ALTER TABLE quote_db_quotes ALTER COLUMN tags DROP NOT NULL;
DROP INDEX idx_quotes_tags;
ALTER TABLE quote_db_quotes DROP COLUMN tags;
```

### 8.4 Checksum Verification

**Purpose**: Detect modified migration files after application

**Implementation**:
```python
import hashlib

def compute_checksum(migration_file: str) -> str:
    """Compute SHA256 checksum of migration UP section."""
    with open(migration_file, 'r') as f:
        content = f.read()
    
    # Extract UP section only
    up_section = extract_up_section(content)
    
    # Compute checksum
    return hashlib.sha256(up_section.encode('utf-8')).hexdigest()[:16]
```

**On Apply**:
- Compute checksum of UP section
- Store in `plugin_schema_migrations` table

**On Subsequent Runs**:
- Recompute checksum of applied migrations
- Compare with stored checksum
- Warn if mismatch (file was modified)

### 8.5 SQLite Limitations

**SQLite Cannot**:
- DROP COLUMN (easily - requires table recreation)
- ALTER COLUMN type (requires table recreation)
- ADD CONSTRAINT (certain types)

**Workaround for DROP COLUMN**:
```sql
-- UP: Drop column via table recreation (SQLite)
CREATE TABLE quote_db_quotes_new (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    author TEXT
    -- Removed: deprecated_field
);

INSERT INTO quote_db_quotes_new SELECT id, text, author FROM quote_db_quotes;
DROP TABLE quote_db_quotes;
ALTER TABLE quote_db_quotes_new RENAME TO quote_db_quotes;
```

**Migration Manager Handles**:
- Detect database type (PostgreSQL vs SQLite)
- Provide helpers for common SQLite workarounds
- Warn if migration uses unsupported SQLite features

---

## 9. NATS API Specifications

### 9.1 Apply Migration

**Subject**: `db.migrate.<plugin>.apply`

**Request**:
```json
{
  "target_version": 3,
  "dry_run": false,
  "auto": false
}
```

**Fields**:
- `target_version` (int|"latest"): Version to migrate to
- `dry_run` (bool, default=false): Preview without executing
- `auto` (bool, default=false): Auto-apply on startup

**Response (Success)**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "previous_version": 1,
  "current_version": 3,
  "applied_migrations": [
    {
      "version": 2,
      "name": "add_rating",
      "execution_time_ms": 45,
      "statements": 2
    },
    {
      "version": 3,
      "name": "index_author",
      "execution_time_ms": 120,
      "statements": 1
    }
  ],
  "total_time_ms": 165
}
```

**Response (Dry Run)**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "dry_run": true,
  "would_apply": [
    {
      "version": 2,
      "name": "add_rating",
      "up_sql": "ALTER TABLE quote_db_quotes ADD COLUMN rating INTEGER DEFAULT 0;\nCREATE INDEX idx_quotes_rating ON quote_db_quotes(rating);"
    }
  ]
}
```

**Response (Failure)**:
```json
{
  "success": false,
  "error_code": "MIGRATION_FAILED",
  "message": "Migration 002_add_rating failed: column 'rating' already exists",
  "plugin": "quote-db",
  "failed_version": 2,
  "rolled_back": true
}
```

---

### 9.2 Rollback Migration

**Subject**: `db.migrate.<plugin>.rollback`

**Request**:
```json
{
  "target_version": 1,
  "dry_run": false
}
```

**Fields**:
- `target_version` (int): Version to rollback to
- `dry_run` (bool, default=false): Preview without executing

**Response (Success)**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "previous_version": 3,
  "current_version": 1,
  "rolled_back_migrations": [
    {
      "version": 3,
      "name": "index_author",
      "execution_time_ms": 30
    },
    {
      "version": 2,
      "name": "add_rating",
      "execution_time_ms": 60
    }
  ],
  "total_time_ms": 90
}
```

**Response (Failure)**:
```json
{
  "success": false,
  "error_code": "ROLLBACK_FAILED",
  "message": "Rollback of migration 003 failed: index 'idx_quotes_author' does not exist",
  "plugin": "quote-db",
  "failed_version": 3,
  "partial_rollback": true,
  "current_version": 2
}
```

---

### 9.3 Migration Status

**Subject**: `db.migrate.<plugin>.status`

**Request**:
```json
{}
```

**Response**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "current_version": 3,
  "applied_migrations": [
    {
      "version": 1,
      "name": "create_quotes",
      "applied_at": "2025-11-20T10:00:00Z",
      "applied_by": "system",
      "execution_time_ms": 150,
      "checksum": "a1b2c3d4e5f67890"
    },
    {
      "version": 2,
      "name": "add_rating",
      "applied_at": "2025-11-21T14:30:00Z",
      "applied_by": "alex",
      "execution_time_ms": 45,
      "checksum": "f0e1d2c3b4a59876"
    },
    {
      "version": 3,
      "name": "index_author",
      "applied_at": "2025-11-22T09:15:00Z",
      "applied_by": "system",
      "execution_time_ms": 120,
      "checksum": "9876543210abcdef"
    }
  ],
  "pending_migrations": [
    {
      "version": 4,
      "name": "add_tags",
      "file": "migrations/004_add_tags.sql"
    }
  ],
  "locked": false,
  "checksum_warnings": []
}
```

**With Checksum Warning**:
```json
{
  ...
  "checksum_warnings": [
    {
      "version": 2,
      "name": "add_rating",
      "stored_checksum": "f0e1d2c3b4a59876",
      "current_checksum": "deadbeef12345678",
      "message": "Migration file was modified after application!"
    }
  ]
}
```

---

### 9.4 Reset Migrations (Dangerous!)

**Subject**: `db.migrate.<plugin>.reset`

**Request**:
```json
{
  "confirm": "RESET_ALL_MIGRATIONS",
  "drop_tables": false
}
```

**Purpose**: Clear migration history (development/testing only)

**Response**:
```json
{
  "success": true,
  "plugin": "quote-db",
  "deleted_migrations": 3,
  "tables_dropped": 0,
  "message": "Migration history reset. Run apply to re-apply migrations."
}
```

**Safety**:
- Requires confirmation string (prevents accidental reset)
- Does NOT drop tables by default (only clears version table)
- Logs warning in production mode
- Only available if `ENABLE_MIGRATION_RESET=true` env var set

---

## 10. Migration Execution Engine

### 10.1 MigrationManager Class

**File**: `common/database/migration_manager.py`

```python
from pathlib import Path
import re
from typing import List, Dict, Optional

class MigrationManager:
    """Manages migration discovery, parsing, and validation."""
    
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.migrations_cache: Dict[str, List[Migration]] = {}
    
    def discover_migrations(self, plugin_name: str) -> List[Migration]:
        """
        Discover migration files for a plugin.
        
        Returns migrations sorted by version number.
        """
        plugin_dir = self.plugins_dir / plugin_name / 'migrations'
        if not plugin_dir.exists():
            return []
        
        migrations = []
        for file in plugin_dir.glob('*.sql'):
            migration = self.parse_migration_file(file)
            migrations.append(migration)
        
        return sorted(migrations, key=lambda m: m.version)
    
    def parse_migration_file(self, file_path: Path) -> Migration:
        """Parse migration file, extract UP/DOWN sections."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract version from filename
        match = re.match(r'(\d+)_(.+)\.sql', file_path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {file_path.name}")
        
        version = int(match.group(1))
        name = match.group(2)
        
        # Extract UP section
        up_match = re.search(r'--\s*UP\s*\n(.*?)(?=--\s*DOWN|\Z)', content, re.DOTALL | re.IGNORECASE)
        if not up_match:
            raise ValueError(f"Migration {file_path.name} missing UP section")
        up_sql = up_match.group(1).strip()
        
        # Extract DOWN section
        down_match = re.search(r'--\s*DOWN\s*\n(.*)', content, re.DOTALL | re.IGNORECASE)
        down_sql = down_match.group(1).strip() if down_match else ''
        
        return Migration(
            version=version,
            name=name,
            file_path=file_path,
            up_sql=up_sql,
            down_sql=down_sql,
            checksum=self.compute_checksum(up_sql)
        )
    
    def get_pending_migrations(
        self,
        plugin_name: str,
        current_version: int,
        target_version: int
    ) -> List[Migration]:
        """Get migrations to apply (current → target)."""
        all_migrations = self.discover_migrations(plugin_name)
        
        return [
            m for m in all_migrations
            if current_version < m.version <= target_version
        ]
    
    def get_rollback_migrations(
        self,
        plugin_name: str,
        current_version: int,
        target_version: int
    ) -> List[Migration]:
        """Get migrations to rollback (current → target, reverse order)."""
        all_migrations = self.discover_migrations(plugin_name)
        
        migrations = [
            m for m in all_migrations
            if target_version < m.version <= current_version
        ]
        
        return sorted(migrations, key=lambda m: m.version, reverse=True)
    
    @staticmethod
    def compute_checksum(sql: str) -> str:
        """Compute SHA256 checksum of SQL content."""
        import hashlib
        return hashlib.sha256(sql.encode('utf-8')).hexdigest()[:16]
```

---

### 10.2 MigrationExecutor Class

**File**: `common/database/migration_executor.py`

```python
import asyncio
from sqlalchemy import text
from typing import Dict, List

class MigrationExecutor:
    """Executes migrations with transaction support and locking."""
    
    def __init__(self, db: BotDatabase):
        self.db = db
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def apply_migration(
        self,
        plugin_name: str,
        migration: Migration,
        dry_run: bool = False
    ) -> MigrationResult:
        """
        Apply a single migration.
        
        - Acquires lock
        - Begins transaction
        - Executes UP SQL
        - Updates version table
        - Commits or rolls back
        """
        lock = self._get_lock(plugin_name)
        
        async with lock:
            if dry_run:
                return MigrationResult(
                    success=True,
                    version=migration.version,
                    dry_run=True,
                    sql_preview=migration.up_sql
                )
            
            # Begin transaction
            async with self.db.session.begin():
                try:
                    # Execute UP SQL
                    start_time = time.time()
                    await self._execute_sql(migration.up_sql)
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    # Update version table
                    await self._record_migration(
                        plugin_name=plugin_name,
                        version=migration.version,
                        name=migration.name,
                        checksum=migration.checksum,
                        execution_time_ms=execution_time_ms
                    )
                    
                    return MigrationResult(
                        success=True,
                        version=migration.version,
                        execution_time_ms=execution_time_ms
                    )
                
                except Exception as e:
                    # Transaction auto-rolls back
                    return MigrationResult(
                        success=False,
                        version=migration.version,
                        error=str(e)
                    )
    
    async def rollback_migration(
        self,
        plugin_name: str,
        migration: Migration,
        dry_run: bool = False
    ) -> MigrationResult:
        """Rollback a single migration (execute DOWN SQL)."""
        lock = self._get_lock(plugin_name)
        
        async with lock:
            if dry_run:
                return MigrationResult(
                    success=True,
                    version=migration.version,
                    dry_run=True,
                    sql_preview=migration.down_sql
                )
            
            async with self.db.session.begin():
                try:
                    # Execute DOWN SQL
                    start_time = time.time()
                    await self._execute_sql(migration.down_sql)
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    # Remove from version table
                    await self._delete_migration_record(
                        plugin_name=plugin_name,
                        version=migration.version
                    )
                    
                    return MigrationResult(
                        success=True,
                        version=migration.version,
                        execution_time_ms=execution_time_ms
                    )
                
                except Exception as e:
                    return MigrationResult(
                        success=False,
                        version=migration.version,
                        error=str(e)
                    )
    
    async def _execute_sql(self, sql: str) -> None:
        """Execute SQL statements (may be multiple, separated by ;)."""
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        
        for stmt in statements:
            await self.db.session.execute(text(stmt))
    
    async def _record_migration(
        self,
        plugin_name: str,
        version: int,
        name: str,
        checksum: str,
        execution_time_ms: float
    ) -> None:
        """Insert migration record into version table."""
        await self.db.session.execute(
            text("""
                INSERT INTO plugin_schema_migrations
                (plugin_name, version, name, applied_at, applied_by, execution_time_ms, checksum)
                VALUES (:plugin, :version, :name, NOW(), :user, :time, :checksum)
            """),
            {
                'plugin': plugin_name,
                'version': version,
                'name': name,
                'user': 'system',  # TODO: Get from context
                'time': execution_time_ms,
                'checksum': checksum
            }
        )
    
    def _get_lock(self, plugin_name: str) -> asyncio.Lock:
        """Get or create asyncio lock for plugin."""
        if plugin_name not in self.locks:
            self.locks[plugin_name] = asyncio.Lock()
        return self.locks[plugin_name]
```

---

### 10.3 Database Schema

**Migration Version Table**:

```sql
CREATE TABLE plugin_schema_migrations (
    id SERIAL PRIMARY KEY,
    plugin_name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by VARCHAR(255) NOT NULL,
    execution_time_ms FLOAT NOT NULL,
    checksum VARCHAR(32) NOT NULL,
    
    UNIQUE(plugin_name, version)
);

CREATE INDEX idx_migrations_plugin ON plugin_schema_migrations(plugin_name);
CREATE INDEX idx_migrations_version ON plugin_schema_migrations(plugin_name, version);
```

---

## 11. Implementation Plan

### 11.1 Sortie 1: Migration Manager Foundation

**Estimated Time**: 1.5 days

**Scope**:
- Create `common/database/migration_manager.py`
- Create `common/database/migration_executor.py`
- Create `plugin_schema_migrations` table (Alembic migration)
- Implement migration file discovery
- Implement UP/DOWN section parsing
- Implement checksum computation

**Key Code**:
```python
# common/database/migration_manager.py
class MigrationManager:
    def discover_migrations(self, plugin_name: str) -> List[Migration]
    def parse_migration_file(self, file_path: Path) -> Migration
    def get_pending_migrations(...) -> List[Migration]
    def get_rollback_migrations(...) -> List[Migration]
    def compute_checksum(sql: str) -> str

# common/database/migration_executor.py
class MigrationExecutor:
    async def apply_migration(...)
    async def rollback_migration(...)
    async def _execute_sql(...)
    async def _record_migration(...)
```

**Tests**:
- Parse valid migration files
- Parse invalid migration files (missing sections)
- Discover migrations in plugin directory
- Compute checksums consistently
- Pending migrations calculation
- Rollback migrations calculation (reverse order)

**Acceptance**:
- [ ] MigrationManager discovers migration files
- [ ] Migration files parsed correctly (UP/DOWN extracted)
- [ ] Checksums computed and verified
- [ ] 30+ unit tests passing

---

### 11.2 Sortie 2: NATS Handlers & Execution

**Estimated Time**: 1.5 days

**Scope**:
- Add NATS handlers in `DatabaseService`
- Implement `db.migrate.<plugin>.apply` handler
- Implement `db.migrate.<plugin>.rollback` handler
- Implement `db.migrate.<plugin>.status` handler
- Implement migration locking (asyncio.Lock)
- Implement transaction support (begin/commit/rollback)

**Key Code**:
```python
# common/database/database_service.py
class DatabaseService:
    async def handle_migrate_apply(self, msg):
        plugin_name = msg.subject.split('.')[2]
        data = json.loads(msg.data)
        
        manager = MigrationManager(self.plugins_dir)
        executor = MigrationExecutor(self.db)
        
        current_version = await self._get_current_version(plugin_name)
        target_version = data.get('target_version', 'latest')
        
        if target_version == 'latest':
            all_migrations = manager.discover_migrations(plugin_name)
            target_version = max(m.version for m in all_migrations) if all_migrations else 0
        
        pending = manager.get_pending_migrations(plugin_name, current_version, target_version)
        
        results = []
        for migration in pending:
            result = await executor.apply_migration(plugin_name, migration, dry_run=data.get('dry_run', False))
            if not result.success:
                await msg.respond(json.dumps({
                    'success': False,
                    'error_code': 'MIGRATION_FAILED',
                    'message': result.error,
                    'failed_version': migration.version
                }).encode())
                return
            results.append(result)
        
        await msg.respond(json.dumps({
            'success': True,
            'applied_migrations': [r.to_dict() for r in results]
        }).encode())
```

**Tests**:
- Apply single migration
- Apply multiple migrations
- Rollback single migration
- Rollback multiple migrations
- Dry-run mode (no changes)
- Failed migration rolls back transaction
- Concurrent migration attempts (locking)
- Status shows applied/pending migrations

**Acceptance**:
- [ ] NATS handlers registered
- [ ] Apply migration works end-to-end
- [ ] Rollback migration works end-to-end
- [ ] Status returns correct information
- [ ] Migration locking prevents concurrent runs
- [ ] 40+ integration tests passing

---

### 11.3 Sortie 3: Safety Features & Validation

**Estimated Time**: 1 day

**Scope**:
- Implement checksum verification on status
- Implement destructive operation warnings (DROP COLUMN)
- Implement SQLite limitation detection
- Implement migration validation (basic SQL syntax check)
- Add safety prompts for dangerous operations

**Key Code**:
```python
class MigrationValidator:
    def validate_migration(self, migration: Migration, db_type: str) -> List[Warning]:
        warnings = []
        
        # Check for destructive operations
        if 'DROP COLUMN' in migration.up_sql.upper():
            warnings.append(Warning(
                level='WARNING',
                message=f"Migration {migration.version} drops column (potential data loss)"
            ))
        
        # Check SQLite limitations
        if db_type == 'sqlite':
            if 'DROP COLUMN' in migration.up_sql.upper():
                warnings.append(Warning(
                    level='ERROR',
                    message=f"SQLite does not support DROP COLUMN directly. Use table recreation workaround."
                ))
        
        return warnings
```

**Tests**:
- Checksum mismatch detected
- DROP COLUMN warning shown
- SQLite limitation error raised
- Invalid SQL syntax detected

**Acceptance**:
- [ ] Checksum verification works
- [ ] Destructive operations warned
- [ ] SQLite limitations detected
- [ ] 20+ validation tests passing

---

### 11.4 Sortie 4: Documentation & Examples

**Estimated Time**: 0.5 days

**Scope**:
- Update `docs/guides/PLUGIN_ROW_STORAGE.md` with migration section
- Create example migrations for quote-db plugin
- Update `ARCHITECTURE.md` with migration system
- Add migration best practices guide

**Deliverables**:
- Plugin migration guide (how to write migrations)
- Example migration files (5-10 common patterns)
- Architecture documentation update
- Best practices (idempotency, rollback safety, etc.)

**Acceptance**:
- [ ] Plugin developer guide complete
- [ ] 5+ example migrations created
- [ ] Architecture docs updated
- [ ] Best practices documented

---

## 12. Testing Strategy

### 12.1 Unit Tests

**MigrationManager Tests** (`tests/unit/test_migration_manager.py`):

```python
import pytest
from pathlib import Path
from common.database.migration_manager import MigrationManager, Migration

class TestMigrationDiscovery:
    def test_discover_migrations(self, tmp_path):
        # Setup: Create fake plugin with migrations
        plugin_dir = tmp_path / 'test-plugin' / 'migrations'
        plugin_dir.mkdir(parents=True)
        
        (plugin_dir / '001_create_table.sql').write_text("""
        -- UP
        CREATE TABLE test_table (id INTEGER PRIMARY KEY);
        -- DOWN
        DROP TABLE test_table;
        """)
        
        (plugin_dir / '002_add_column.sql').write_text("""
        -- UP
        ALTER TABLE test_table ADD COLUMN name TEXT;
        -- DOWN
        ALTER TABLE test_table DROP COLUMN name;
        """)
        
        # Test
        manager = MigrationManager(tmp_path)
        migrations = manager.discover_migrations('test-plugin')
        
        assert len(migrations) == 2
        assert migrations[0].version == 1
        assert migrations[1].version == 2
    
    def test_parse_migration_file(self):
        content = """
        -- UP
        CREATE TABLE test (id INT);
        -- DOWN
        DROP TABLE test;
        """
        
        migration = manager.parse_migration_content(content, version=1, name='test')
        assert 'CREATE TABLE' in migration.up_sql
        assert 'DROP TABLE' in migration.down_sql
    
    def test_checksum_computation(self):
        sql1 = "CREATE TABLE test (id INT);"
        sql2 = "CREATE TABLE test (id INT);"
        sql3 = "CREATE TABLE test (id INTEGER);"
        
        assert manager.compute_checksum(sql1) == manager.compute_checksum(sql2)
        assert manager.compute_checksum(sql1) != manager.compute_checksum(sql3)

class TestMigrationSelection:
    def test_pending_migrations(self):
        # Current version: 2, Target version: 4
        # Should return: [migration_3, migration_4]
        pending = manager.get_pending_migrations('test-plugin', current_version=2, target_version=4)
        assert len(pending) == 2
        assert pending[0].version == 3
        assert pending[1].version == 4
    
    def test_rollback_migrations(self):
        # Current version: 4, Target version: 2
        # Should return: [migration_4, migration_3] (reverse order)
        rollback = manager.get_rollback_migrations('test-plugin', current_version=4, target_version=2)
        assert len(rollback) == 2
        assert rollback[0].version == 4
        assert rollback[1].version == 3
```

**Target**: 50+ unit tests

### 12.2 Integration Tests

**End-to-End Migration Tests** (`tests/integration/test_migrations.py`):

```python
import pytest
import json
import asyncio

@pytest.mark.asyncio
class TestMigrationIntegration:
    async def test_apply_single_migration(self, nats_client, db):
        # Setup: Create migration file
        migration_dir = Path('plugins/test-plugin/migrations')
        migration_dir.mkdir(parents=True, exist_ok=True)
        
        (migration_dir / '001_create_table.sql').write_text("""
        -- UP
        CREATE TABLE test_plugin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL
        );
        -- DOWN
        DROP TABLE test_plugin_users;
        """)
        
        # Apply migration
        response = await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 1
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert data['current_version'] == 1
        
        # Verify table exists
        result = await db.session.execute(text("SELECT 1 FROM test_plugin_users LIMIT 1"))
        # Should not raise error (table exists)
    
    async def test_apply_multiple_migrations(self, nats_client, db):
        # Create migrations 001, 002, 003
        # ...
        
        # Apply all at once
        response = await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 3
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert len(data['applied_migrations']) == 3
        assert data['current_version'] == 3
    
    async def test_rollback_migration(self, nats_client, db):
        # Apply migrations 1, 2, 3
        await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 3
        }).encode())
        
        # Rollback to version 1
        response = await nats_client.request('db.migrate.test-plugin.rollback', json.dumps({
            'target_version': 1
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert len(data['rolled_back_migrations']) == 2
        assert data['current_version'] == 1
    
    async def test_failed_migration_rolls_back(self, nats_client, db):
        # Migration with invalid SQL
        (migration_dir / '001_bad.sql').write_text("""
        -- UP
        CREATE TABLE test_bad (id INVALID_TYPE);
        -- DOWN
        DROP TABLE test_bad;
        """)
        
        response = await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 1
        }).encode())
        
        data = json.loads(response.data)
        assert not data['success']
        assert data['error_code'] == 'MIGRATION_FAILED'
        
        # Verify no table created (transaction rolled back)
        with pytest.raises(Exception):
            await db.session.execute(text("SELECT 1 FROM test_bad LIMIT 1"))
    
    async def test_concurrent_migrations_locked(self, nats_client, db):
        # Start migration 1 (slow)
        task1 = asyncio.create_task(nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 1
        }).encode()))
        
        # Wait a bit, then try migration 2 (should be blocked)
        await asyncio.sleep(0.1)
        task2 = asyncio.create_task(nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 2
        }).encode()))
        
        # Task 1 completes first
        result1 = await task1
        data1 = json.loads(result1.data)
        assert data1['success']
        
        # Task 2 completes after (was locked)
        result2 = await task2
        data2 = json.loads(result2.data)
        # Either succeeds (applied migration 2) or reports already at version
    
    async def test_migration_status(self, nats_client, db):
        # Apply migrations 1, 2
        await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 2
        }).encode())
        
        # Check status
        response = await nats_client.request('db.migrate.test-plugin.status', json.dumps({}).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert data['current_version'] == 2
        assert len(data['applied_migrations']) == 2
        assert data['applied_migrations'][0]['version'] == 1
        assert data['applied_migrations'][1]['version'] == 2
    
    async def test_dry_run_mode(self, nats_client, db):
        response = await nats_client.request('db.migrate.test-plugin.apply', json.dumps({
            'target_version': 1,
            'dry_run': true
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert data['dry_run']
        assert len(data['would_apply']) == 1
        
        # Verify no actual changes
        status_response = await nats_client.request('db.migrate.test-plugin.status', json.dumps({}).encode())
        status_data = json.loads(status_response.data)
        assert status_data['current_version'] == 0  # No migrations applied
```

**Target**: 30+ integration tests

### 12.3 Safety Tests

**Validation Tests** (`tests/unit/test_migration_validator.py`):

```python
class TestMigrationValidator:
    def test_detect_drop_column(self):
        migration = Migration(
            version=1,
            name='drop_col',
            up_sql='ALTER TABLE test DROP COLUMN old_field;',
            down_sql='ALTER TABLE test ADD COLUMN old_field TEXT;'
        )
        
        warnings = validator.validate_migration(migration, db_type='postgresql')
        assert any(w.level == 'WARNING' and 'DROP COLUMN' in w.message for w in warnings)
    
    def test_sqlite_drop_column_error(self):
        migration = Migration(
            version=1,
            name='drop_col',
            up_sql='ALTER TABLE test DROP COLUMN old_field;',
            down_sql=''
        )
        
        warnings = validator.validate_migration(migration, db_type='sqlite')
        assert any(w.level == 'ERROR' and 'SQLite' in w.message for w in warnings)
    
    def test_checksum_mismatch_warning(self):
        # Apply migration with checksum A
        # Modify file to have checksum B
        # Check status → should warn about mismatch
        pass
```

**Target**: 20+ validation tests

---

## 13. Performance Requirements

### 13.1 Latency Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Discover migrations | <100ms | Read filesystem, parse files |
| Apply single migration | <5s | Depends on SQL complexity |
| Rollback single migration | <3s | Usually faster than apply |
| Migration status check | <500ms | Query version table |
| Lock acquisition | <100ms | In-memory lock |

### 13.2 Scalability

**Migration Files**:
- Support 100+ migrations per plugin
- No performance degradation with large migration count

**Concurrent Plugins**:
- 10+ plugins can check/apply migrations simultaneously
- Per-plugin locking (no global bottleneck)

### 13.3 Startup Impact

**Plugin Startup Time**:
- Without migrations: 300ms baseline
- With migration check: +200ms (status check)
- With pending migrations: +5s per migration
- Target: Plugin startup <10s even with 5 pending migrations

---

## 14. Security & Safety

### 14.1 SQL Injection Prevention

**Migration Files**:
- Migration SQL written by plugin developers (trusted)
- No user input in migration SQL
- File-based (not NATS payload-based)

**Risk**: Low (migrations are code, not user input)

### 14.2 Destructive Operation Warnings

**Detected Operations**:
- DROP COLUMN → Data loss warning
- DROP TABLE → Data loss warning
- TRUNCATE → Data loss warning
- ALTER COLUMN TYPE → Potential data loss

**Handling**:
- Log warning before execution
- Require confirmation flag for production
- Dry-run mode shows warnings without executing

### 14.3 Backup Recommendations

**Best Practices** (documented):
- Backup database before applying migrations (manual or automated)
- Test migrations on staging environment first
- Always write DOWN migrations for rollback

**Future** (V2):
- Automatic backups before destructive migrations
- Point-in-time recovery integration

---

## 15. Error Handling

### 15.1 Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| MIGRATION_FAILED | SQL execution failed | Syntax error, constraint violation |
| MIGRATION_NOT_FOUND | Migration file missing | Trying to apply version 5 but file doesn't exist |
| INVALID_VERSION | Version number invalid | target_version='abc' |
| LOCKED | Migration in progress | Another process applying migrations |
| CHECKSUM_MISMATCH | File modified after apply | Migration file edited post-application |
| ROLLBACK_FAILED | DOWN migration failed | Cannot undo changes |

### 15.2 Error Response Format

```json
{
  "success": false,
  "error_code": "MIGRATION_FAILED",
  "message": "Migration 003_add_tags failed: column 'tags' already exists",
  "plugin": "quote-db",
  "failed_version": 3,
  "sql_error": "ERROR: column 'tags' of relation 'quote_db_quotes' already exists",
  "rolled_back": true,
  "current_version": 2
}
```

### 15.3 Recovery Strategies

**Failed Apply**:
1. Transaction auto-rolls back
2. Version table not updated
3. Plugin remains at previous version
4. Retry after fixing migration file

**Failed Rollback**:
1. Transaction auto-rolls back
2. Version table may be inconsistent
3. Manual intervention required
4. Check database state, fix manually, update version table

---

## 16. Observability

### 16.1 Logging

**Migration Events**:

```python
self.logger.info(
    "[MIGRATE] apply: plugin=quote-db version=2→3 migrations=[2,3] time=1250ms",
    extra={
        'operation': 'migrate_apply',
        'plugin': 'quote-db',
        'previous_version': 2,
        'current_version': 3,
        'migrations': [2, 3],
        'total_time_ms': 1250
    }
)

self.logger.warning(
    "[MIGRATE] rollback: plugin=quote-db version=3→2 reason=failed_deploy time=900ms",
    extra={
        'operation': 'migrate_rollback',
        'plugin': 'quote-db',
        'previous_version': 3,
        'current_version': 2,
        'total_time_ms': 900
    }
)

self.logger.error(
    "[MIGRATE] FAILED: plugin=quote-db version=3 error='column already exists' rolled_back=true",
    extra={
        'operation': 'migrate_failed',
        'plugin': 'quote-db',
        'failed_version': 3,
        'error': 'column already exists',
        'rolled_back': True
    }
)
```

### 16.2 Metrics (Future)

```
# Migration counters
rosey_migrations_applied_total{plugin="quote-db"}
rosey_migrations_failed_total{plugin="quote-db"}
rosey_migrations_rolled_back_total{plugin="quote-db"}

# Migration latency
rosey_migration_duration_seconds{plugin="quote-db", version="3"}

# Current versions
rosey_migration_current_version{plugin="quote-db"} 3
```

---

## 17. Documentation Requirements

### 17.1 Plugin Developer Guide

**Update `docs/guides/PLUGIN_ROW_STORAGE.md`**:

````markdown
## Schema Migrations

### Creating Your First Migration

Migrations live in `plugins/<your-plugin>/migrations/` directory.

**File naming**: `{version}_{description}.sql`
- Version: 3-digit zero-padded integer (001, 002, ...)
- Description: Snake_case description

**Example**: `001_create_quotes.sql`

```sql
-- UP
CREATE TABLE quote_db_quotes (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    author VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quotes_author ON quote_db_quotes(author);

-- DOWN
DROP TABLE quote_db_quotes;
```

### Applying Migrations

**On Plugin Startup** (automatic):

```python
async def on_ready(self):
    # Auto-apply pending migrations
    response = await self.nats.request('db.migrate.my-plugin.apply', json.dumps({
        'target_version': 'latest',
        'auto': True
    }).encode())
    
    data = json.loads(response.data)
    if not data['success']:
        raise RuntimeError(f"Migration failed: {data['message']}")
```

**Manual Application**:

```python
# Apply specific version
await self.nats.request('db.migrate.my-plugin.apply', json.dumps({
    'target_version': 3
}).encode())

# Apply all pending
await self.nats.request('db.migrate.my-plugin.apply', json.dumps({
    'target_version': 'latest'
}).encode())
```

### Rollback

```python
# Rollback to version 2
await self.nats.request('db.migrate.my-plugin.rollback', json.dumps({
    'target_version': 2
}).encode())
```

### Best Practices

1. **Test locally first**: Always test migrations in development before production
2. **Write DOWN migrations**: Always provide rollback SQL
3. **Small migrations**: One logical change per migration
4. **Idempotent when possible**: Use `IF NOT EXISTS`, `IF EXISTS`
5. **Backup data**: Backup before destructive changes (DROP COLUMN)
6. **Dry-run**: Preview changes with `dry_run: true`

### Common Patterns

**Add Column**:
```sql
-- UP
ALTER TABLE my_plugin_table ADD COLUMN new_field INTEGER DEFAULT 0;

-- DOWN
ALTER TABLE my_plugin_table DROP COLUMN new_field;
```

**Create Index**:
```sql
-- UP
CREATE INDEX idx_table_field ON my_plugin_table(field);

-- DOWN
DROP INDEX idx_table_field;
```

**Rename Column**:
```sql
-- UP
ALTER TABLE my_plugin_table RENAME COLUMN old_name TO new_name;

-- DOWN
ALTER TABLE my_plugin_table RENAME COLUMN new_name TO old_name;
```

**Add NOT NULL Constraint**:
```sql
-- UP
-- First, set default for existing NULLs
UPDATE my_plugin_table SET field = 'default' WHERE field IS NULL;
-- Then add constraint
ALTER TABLE my_plugin_table ALTER COLUMN field SET NOT NULL;

-- DOWN
ALTER TABLE my_plugin_table ALTER COLUMN field DROP NOT NULL;
```
````

### 17.2 Architecture Documentation

**Update `docs/ARCHITECTURE.md`**:

```markdown
## Schema Migrations (Sprint 15)

Plugins manage database schema evolution via versioned SQL migration files.

**Components**:
- **MigrationManager**: Discovers, parses, validates migration files
- **MigrationExecutor**: Executes UP/DOWN SQL with transaction support
- **Version Table**: `plugin_schema_migrations` tracks applied migrations

**NATS API**:
- `db.migrate.<plugin>.apply` - Apply migrations to target version
- `db.migrate.<plugin>.rollback` - Rollback to previous version
- `db.migrate.<plugin>.status` - View migration history

**Safety Features**:
- Per-plugin locking (prevent concurrent migrations)
- Transaction support (auto-rollback on failure)
- Checksum verification (detect file modifications)
- Dry-run mode (preview changes)

**Migration Files**: `plugins/<plugin>/migrations/001_create_table.sql`

**Example Workflow**:
1. Developer writes migration file (UP/DOWN SQL)
2. Plugin startup calls `db.migrate.apply` with `auto: true`
3. MigrationManager discovers pending migrations
4. MigrationExecutor applies each migration in transaction
5. Version table updated with applied migrations
```

---

## 18. Dependencies & Risks

### 18.1 Dependencies

**Required**:
- ✅ Sprint 13 (Row Operations Foundation)
- ✅ SQLAlchemy with DDL support
- ✅ PostgreSQL 12+ or SQLite 3.35+
- ✅ Alembic (for version table migration)

**No New Dependencies**: Uses existing infrastructure

### 18.2 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Failed migrations corrupt database | Low | High | Transaction rollback, thorough testing |
| SQLite limitations block adoption | Medium | Medium | Document workarounds, provide examples |
| Migration conflicts in team | Medium | Low | Clear naming convention, version control |
| Rollback loses data | Low | High | Warn about destructive operations, document |
| Concurrent migration race | Low | Medium | Migration locking prevents |

### 18.3 Rollback Plan

**If Sprint 15 Fails**:

1. **Revert Alembic Migration**:
   ```bash
   alembic downgrade -1  # Drop plugin_schema_migrations table
   ```

2. **Remove Code**:
   - Revert commits 1-4
   - DatabaseService unchanged (no NATS subscriptions)

3. **No Data Loss**:
   - `plugin_schema_migrations` table dropped
   - Plugin tables unaffected (migrations never ran)
   - Sprints XXX-A, XXX-B, XXX-C unaffected

---

## 19. Sprint Acceptance Criteria

### 19.1 Functional Acceptance

- [ ] ✅ MigrationManager discovers migration files
- [ ] ✅ Migration files parsed (UP/DOWN extracted)
- [ ] ✅ Checksums computed and verified
- [ ] ✅ Apply single migration works
- [ ] ✅ Apply multiple migrations works
- [ ] ✅ Rollback single migration works
- [ ] ✅ Rollback multiple migrations works
- [ ] ✅ Migration status shows applied/pending
- [ ] ✅ Dry-run mode previews without applying
- [ ] ✅ Failed migrations roll back automatically
- [ ] ✅ Concurrent migrations locked (no race conditions)

### 19.2 Safety Acceptance

- [ ] ✅ Checksum mismatch detected and warned
- [ ] ✅ Destructive operations (DROP COLUMN) warned
- [ ] ✅ SQLite limitations detected and warned
- [ ] ✅ Migration lock prevents concurrent runs
- [ ] ✅ Transaction rollback works on SQL error

### 19.3 Performance Acceptance

- [ ] ✅ Migration discovery <100ms
- [ ] ✅ Single migration application <5s
- [ ] ✅ Status check <500ms
- [ ] ✅ Plugin startup with migrations <10s

### 19.4 Quality Acceptance

- [ ] ✅ Test coverage ≥85%
- [ ] ✅ 50+ unit tests passing
- [ ] ✅ 30+ integration tests passing
- [ ] ✅ 20+ validation tests passing
- [ ] ✅ Documentation complete
- [ ] ✅ Example migrations created (5+)
- [ ] ✅ No breaking changes to Sprints XXX-A/B/C

---

## 20. Future Enhancements

### 20.1 Deferred to Sprint 16 (Reference Implementation)

**Data Migrations**:
- INSERT/UPDATE/DELETE in migration files
- Data transformations during schema changes
- Backfill operations for new columns

**Example** (Sprint 16):
```sql
-- UP
ALTER TABLE quote_db_quotes ADD COLUMN popularity INTEGER DEFAULT 0;

-- Backfill popularity from view count
UPDATE quote_db_quotes 
SET popularity = (SELECT COUNT(*) FROM quote_views WHERE quote_id = quote_db_quotes.id);
```

### 20.2 V2 Features

**Zero-Downtime Migrations**:
- Online schema changes (pt-online-schema-change style)
- Blue-green deployment support
- Read replicas during migration

**Migration Generators**:
- Detect schema changes automatically
- Generate migration files from model changes
- Django-style makemigrations command

**Advanced Rollback**:
- Automatic backups before destructive operations
- Point-in-time recovery integration
- Snapshot-based rollback

**Migration Templates**:
- Common patterns (add_column, create_index, etc.)
- Code generation helpers
- IDE integration

### 20.3 Out of Scope (Forever)

- ❌ Cross-plugin foreign keys (violates isolation)
- ❌ Cross-database migrations (PostgreSQL → SQLite)
- ❌ Python code in migrations (SQL-only keeps it simple)

---

## 21. Appendices

### 21.1 Migration File Examples

**Example 1: Create Table**:
```sql
-- UP
CREATE TABLE quote_db_quotes (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    author VARCHAR(255),
    added_by VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- DOWN
DROP TABLE quote_db_quotes;
```

**Example 2: Add Column**:
```sql
-- UP
ALTER TABLE quote_db_quotes ADD COLUMN rating INTEGER DEFAULT 0;
ALTER TABLE quote_db_quotes ADD CONSTRAINT check_rating CHECK (rating BETWEEN 0 AND 5);

-- DOWN
ALTER TABLE quote_db_quotes DROP CONSTRAINT check_rating;
ALTER TABLE quote_db_quotes DROP COLUMN rating;
```

**Example 3: Create Index**:
```sql
-- UP
CREATE INDEX idx_quotes_author ON quote_db_quotes(author);
CREATE INDEX idx_quotes_rating ON quote_db_quotes(rating);

-- DOWN
DROP INDEX idx_quotes_rating;
DROP INDEX idx_quotes_author;
```

**Example 4: Rename Column**:
```sql
-- UP
ALTER TABLE quote_db_quotes RENAME COLUMN author TO author_name;

-- DOWN
ALTER TABLE quote_db_quotes RENAME COLUMN author_name TO author;
```

**Example 5: Add NOT NULL**:
```sql
-- UP
UPDATE quote_db_quotes SET author = 'Unknown' WHERE author IS NULL;
ALTER TABLE quote_db_quotes ALTER COLUMN author SET NOT NULL;

-- DOWN
ALTER TABLE quote_db_quotes ALTER COLUMN author DROP NOT NULL;
```

### 21.2 Glossary

**Terms**:
- **Migration**: Versioned SQL file with UP/DOWN sections
- **UP**: SQL to apply schema change (forward)
- **DOWN**: SQL to rollback schema change (backward)
- **Version**: Sequential integer identifying migration (001, 002, ...)
- **Pending**: Migrations not yet applied
- **Applied**: Migrations already executed
- **Rollback**: Execute DOWN SQL to undo migrations
- **Checksum**: SHA256 hash of migration UP section
- **Dry-run**: Preview mode (no actual execution)

### 21.3 References

**Internal Documents**:
- Sprint 12: KV Storage Foundation
- Sprint 13: Row Operations Foundation
- Sprint 14: Advanced Query Operators

**External Resources**:
- Alembic Documentation: https://alembic.sqlalchemy.org/
- PostgreSQL DDL: https://www.postgresql.org/docs/current/ddl.html
- SQLite ALTER TABLE: https://www.sqlite.org/lang_altertable.html
- Django Migrations: https://docs.djangoproject.com/en/stable/topics/migrations/

### 21.4 Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-22 | GitHub Copilot | Initial PRD creation |

---

**End of PRD: Schema Migrations (Sprint 15)**

**Document Stats**:
- **Words**: ~13,000
- **Sections**: 21
- **User Stories**: 10
- **Commits**: 4
- **Estimated Duration**: 4-5 days
- **Test Coverage Target**: ≥85%

**Next Steps**:
1. Review and approve this PRD
2. Create Sprint 15 branch
3. Begin Sortie 1: Migration Manager Foundation
4. Follow implementation plan (Section 11)

**Related PRDs**:
- ✅ Sprint 12: KV Storage Foundation (completed)
- ✅ Sprint 13: Row Operations Foundation (completed)
- ✅ Sprint 14: Advanced Query Operators (completed)
- ⏳ Sprint 16: Reference Implementation (next)
- ⏳ Sprint 17: Parameterized SQL

---

*This document is a living document and will be updated as implementation progresses. All changes require Tech Lead approval.*
