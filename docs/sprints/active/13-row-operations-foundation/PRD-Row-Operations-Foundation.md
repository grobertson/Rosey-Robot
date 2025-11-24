# PRD: Row Operations Foundation (Sprint 13)

## Executive Summary

Sprint 13 delivers **Tier 2 storage**: structured row-based CRUD operations for plugins. Building on Sprint 12's key-value foundation, this sprint enables plugins to store and query typed entities (quotes, trivia stats, user preferences) through a simple CRUD API.

**What This Sprint Delivers**:
- Insert rows into plugin-owned tables
- Select rows by ID or simple equality filters
- Update rows by ID
- Delete rows by ID  
- Search rows with basic filtering and pagination
- Table schema registration and validation
- Plugin isolation at the table level

**What This Sprint Does NOT Deliver**:
- MongoDB-style operators ($inc, $gte, etc.) - **Sprint 14**
- Schema migrations - **Sprint 15**
- Complex joins or aggregations - **Sprint 17**

**Business Value**: Plugins can graduate from simple key-value storage to structured relational data without learning SQL. The quote-db plugin can store quotes with proper fields (text, author, timestamp), and the trivia plugin can track game history and user statistics.

**Success Metrics**:
- Insert operation <10ms p95 latency
- Select by ID <5ms p95 latency
- Search with filters <20ms p95 latency
- 85%+ test coverage
- Zero cross-plugin data access in security tests

**Duration**: 4-5 days, 5 sorties

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Table of Contents](#table-of-contents)
3. [Problem Statement & Context](#3-problem-statement--context)
4. [Goals & Non-Goals](#4-goals--non-goals)
5. [Success Metrics](#5-success-metrics)
6. [User Personas](#6-user-personas)
7. [User Stories](#7-user-stories)
8. [Technical Architecture](#8-technical-architecture)
9. [Table Schema Registry](#9-table-schema-registry)
10. [NATS Subject Design](#10-nats-subject-design)
11. [API Specifications](#11-api-specifications)
12. [Implementation Plan](#12-implementation-plan)
13. [Testing Strategy](#13-testing-strategy)
14. [Security & Isolation](#14-security--isolation)
15. [Performance Requirements](#15-performance-requirements)
16. [Error Handling](#16-error-handling)
17. [Observability](#17-observability)
18. [Documentation Requirements](#18-documentation-requirements)
19. [Dependencies & Risks](#19-dependencies--risks)
20. [Sprint Acceptance Criteria](#20-sprint-acceptance-criteria)
21. [Future Enhancements](#21-future-enhancements)
22. [Appendices](#22-appendices)

---

## 3. Problem Statement & Context

### 3.1 The Problem

Sprint 12 delivered key-value storage, which works well for simple use cases (configuration, flags, counters). However, plugins often need to store **structured entities with multiple fields**:

- **Quote Database**: Needs to store quotes with `text`, `author`, `added_by`, `timestamp`
- **Trivia Plugin**: Needs to track game rounds with `user_id`, `question`, `answer`, `score`, `timestamp`
- **User Preferences**: Needs to store per-user settings with `user_id`, `theme`, `notifications`, `timezone`

**Current Workaround** (using KV):
```python
# Store quote as JSON blob in single KV entry
await nats.publish('db.kv.quote-db.set', json.dumps({
    'key': f'quote_{id}',
    'value': {
        'text': 'Keep circulating the tapes',
        'author': 'MST3K',
        'added_by': 'groberts',
        'timestamp': '2025-11-22T10:30:00Z'
    }
}).encode())

# Problem: How do I search for all quotes by "MST3K"?
# Problem: How do I get the 10 most recent quotes?
# Problem: How do I update just the author field?
```

**Limitations of KV for Structured Data**:
- ❌ No field-level queries (can't search by author)
- ❌ No sorting (can't get "most recent")
- ❌ No pagination (must fetch all keys)
- ❌ No atomic field updates (must read-modify-write entire value)
- ❌ No schema validation (typos in field names go undetected)

### 3.2 Why Now?

**Dependencies Ready**:
- ✅ Sprint 12: KV storage proves NATS-to-database pattern works
- ✅ Sprint 11: SQLAlchemy ORM provides relational database abstraction
- ✅ Sprint 9: DatabaseService has NATS handler infrastructure

**Blocked Work**:
- Quote-db plugin spec requires structured storage
- Trivia plugin spec requires queryable game history
- XXX-Funny-Games sprint depends on both plugins

### 3.3 Comparison to Alternatives

**Option A: Keep Using KV + Client-Side Filtering** ❌
- Plugins fetch all keys and filter in memory
- Doesn't scale (100+ quotes = slow)
- No indexes (every query is O(n))

**Option B: Give Plugins Direct SQL Access** ❌  
- Security risk (SQL injection, cross-plugin access)
- No isolation enforcement
- Breaks abstraction (plugins tied to PostgreSQL/SQLite)

**Option C: This Sprint - Row Operations API** ✅
- Type-safe CRUD operations
- Server-side filtering and indexing
- Plugin isolation enforced by DatabaseService
- Database-agnostic (works on SQLite + PostgreSQL)

---

## 4. Goals & Non-Goals

### 4.1 Goals

**Primary Goals**:
1. **Enable CRUD on Structured Data**: Plugins can insert, select, update, delete rows
2. **Basic Query Support**: Filter by field equality, sort by single field, paginate results
3. **Schema Validation**: Table schemas registered and validated before use
4. **Plugin Isolation**: Plugin A cannot access Plugin B's tables
5. **Performance**: Single-row operations <10ms, searches <20ms

**Secondary Goals**:
6. **Developer Experience**: Simple JSON API, clear error messages
7. **Database Agnostic**: Works identically on SQLite (dev) and PostgreSQL (prod)
8. **Extensibility**: API design allows future operators (Sprint 14)

### 4.2 Non-Goals (Out of Scope)

**Deferred to Sprint 14 (Advanced Queries)**:
- ❌ MongoDB-style operators ($inc, $gte, $in, $like)
- ❌ Multi-field sorting
- ❌ Compound filters (AND/OR logic)
- ❌ Atomic increment/decrement

**Deferred to Sprint 15 (Migrations)**:
- ❌ Schema evolution (ALTER TABLE)
- ❌ Migration versioning
- ❌ Schema rollback

**Deferred to Sprint 17 (Advanced SQL)**:
- ❌ Joins across tables
- ❌ Aggregations (COUNT, SUM, AVG)
- ❌ Raw SQL queries

**Never in Scope**:
- ❌ ORM code generation for plugins
- ❌ Automatic schema inference
- ❌ NoSQL document storage (use KV for that)

### 4.3 Success Criteria

**Must Have**:
- [ ] Insert row returns ID
- [ ] Select by ID returns row
- [ ] Update by ID modifies row
- [ ] Delete by ID removes row
- [ ] Search with equality filter returns matching rows
- [ ] Pagination works (limit + offset)
- [ ] Schema validation rejects invalid tables
- [ ] Plugin isolation prevents cross-plugin access

**Should Have**:
- [ ] Single-field sorting (ASC/DESC)
- [ ] Bulk insert (multiple rows)
- [ ] Result count metadata

**Nice to Have**:
- [ ] Upsert operation (insert or update)
- [ ] Soft delete (mark deleted instead of removing)

---

## 5. Success Metrics

### 5.1 User-Centric Metrics

**Plugin Developer Productivity**:
- Time to add structured storage: <30 minutes (register schema + use API)
- Lines of code required: <50 (vs 200+ for direct SQL)
- Bugs related to storage: <2 per plugin (schema validation catches errors)

**Query Success Rate**:
- 99%+ of queries return correct results
- <1% error rate due to validation failures

### 5.2 Technical Metrics

**Performance** (single database instance):
- Insert: <10ms p95 latency
- Select by ID: <5ms p95 latency (primary key lookup)
- Search: <20ms p95 latency (with indexes)
- Throughput: ≥500 ops/sec (mixed workload)

**Scalability**:
- Support 10+ plugins with 10+ tables each
- Handle 100,000+ rows per table
- Efficient pagination (no full table scans)

**Reliability**:
- 99.9%+ uptime (DatabaseService availability)
- Zero data corruption incidents
- <1% failed operations (excluding validation errors)

### 5.3 Quality Metrics

**Test Coverage**:
- Overall: ≥85%
- Critical paths: 100% (CRUD operations, plugin isolation)
- Unit tests: 50+ tests
- Integration tests: 30+ tests

**Code Quality**:
- Zero linting errors (flake8, mypy)
- All public APIs have docstrings
- Type hints on all functions

---

## 6. User Personas

### 6.1 Persona: Plugin Developer Alex

**Background**:
- Experience: Intermediate Python developer
- Goal: Build quote-db plugin with searchable quotes
- Current blocker: KV storage can't query by author

**Pain Points**:
- Doesn't want to learn SQL or database schema design
- Needs simple API for insert/search operations
- Worried about plugin isolation (doesn't want to break other plugins)

**How Row Operations Help**:
- Register `quotes` table schema once
- Use simple JSON API: `db.row.quote-db.insert`
- Search by author: `filters: {"author": {"$eq": "MST3K"}}`
- No SQL knowledge required

**Success Scenario**:
```python
# Register schema (once at startup)
await register_table_schema('quotes', {
    'text': 'TEXT',
    'author': 'VARCHAR(255)',
    'added_by': 'VARCHAR(255)',
    'timestamp': 'TIMESTAMP'
})

# Insert quote
await nats.request('db.row.quote-db.insert', json.dumps({
    'table': 'quotes',
    'data': {
        'text': 'Keep circulating the tapes',
        'author': 'MST3K',
        'added_by': 'groberts',
        'timestamp': datetime.now().isoformat()
    }
}).encode())

# Search by author
response = await nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {'author': 'MST3K'},
    'limit': 10
}).encode())
```

### 6.2 Persona: Bot Administrator Jordan

**Background**:
- Experience: Linux sysadmin, basic Python
- Goal: Deploy Rosey with multiple plugins reliably
- Current concern: Plugin data isolation and performance

**Pain Points**:
- Needs confidence that plugins can't access each other's data
- Wants to monitor storage performance
- Concerned about database growth

**How Row Operations Help**:
- Plugin isolation enforced at subject level (`db.row.<plugin>.*`)
- Logging shows per-plugin operation counts
- Table schema registration prevents runaway storage

**Success Scenario**:
- Deploy 5 plugins with row storage
- Monitor logs: `[ROW] insert: plugin=quote-db table=quotes rows=1 latency=3ms`
- Inspect database: Each plugin has its own table namespace
- Performance stays consistent as data grows

### 6.3 Persona: Power User Sam

**Background**:
- Experience: Senior developer, database expert
- Goal: Build trivia plugin with leaderboards
- Current frustration: Row operations too simple for complex queries

**Pain Points**:
- Needs atomic counters (score += 10)
- Wants compound filters (score > 100 AND active = true)
- Wants aggregations (COUNT, MAX)

**How Row Operations Help** (Sprint 13 scope):
- Basic CRUD works for simple queries
- Pagination for leaderboards (top 10 scores)
- Foundation for Sprint 14 operators

**What's Coming Next** (Sprint 14):
- Atomic operators: `{"score": {"$inc": 10}}`
- Compound filters: `{"score": {"$gte": 100}, "active": true}`
- Sam can graduate to these features when ready

---

## 7. User Stories

### 7.1 User Story: Register Table Schema

**ID**: GH-ROW-001  
**Title**: As a plugin developer, I want to register my table schema so that my data structure is validated

**Description**:
Plugin developers need to define their table schemas before performing CRUD operations. Schema registration happens at plugin initialization and validates field types, primary keys, and indexes.

**Acceptance Criteria**:
- [ ] Plugin can register table schema via NATS subject `db.schema.<plugin>.register`
- [ ] Schema includes table name, fields (name + type), primary key
- [ ] Supported types: TEXT, VARCHAR(n), INTEGER, FLOAT, BOOLEAN, TIMESTAMP, JSON
- [ ] Schema validation rejects invalid types
- [ ] Schema validation rejects duplicate field names
- [ ] Registration is idempotent (same schema twice = success)
- [ ] Schema mismatch returns error (can't change schema without migration)

**Example**:
```python
await nats.request('db.schema.quote-db.register', json.dumps({
    'table': 'quotes',
    'fields': [
        {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
        {'name': 'text', 'type': 'TEXT', 'nullable': False},
        {'name': 'author', 'type': 'VARCHAR(255)'},
        {'name': 'added_by', 'type': 'VARCHAR(255)'},
        {'name': 'timestamp', 'type': 'TIMESTAMP', 'default': 'CURRENT_TIMESTAMP'}
    ],
    'indexes': [
        {'fields': ['author']},
        {'fields': ['timestamp']}
    ]
}).encode())
```

**Test Cases**:
1. Valid schema registration succeeds
2. Duplicate registration (same schema) succeeds
3. Schema mismatch (different types) returns error
4. Invalid type (e.g., "IMAGINARY") returns error
5. Missing primary key returns error

---

### 7.2 User Story: Insert Row

**ID**: GH-ROW-002  
**Title**: As a plugin developer, I want to insert a row so that I can store new entities

**Description**:
Plugins insert rows into their tables with typed data. The database assigns an auto-increment ID and returns it to the caller.

**Acceptance Criteria**:
- [ ] Insert via NATS subject `db.row.<plugin>.insert`
- [ ] Payload includes table name and data fields
- [ ] Auto-increment ID assigned and returned
- [ ] Type validation enforced (string goes in TEXT, number in INTEGER)
- [ ] NULL constraint enforced (nullable=False fields required)
- [ ] Default values applied (timestamp defaults to NOW)
- [ ] Response includes `id` and `created: true`

**Example**:
```python
response = await nats.request('db.row.quote-db.insert', json.dumps({
    'table': 'quotes',
    'data': {
        'text': 'Keep circulating the tapes',
        'author': 'MST3K',
        'added_by': 'groberts'
        # timestamp auto-filled with CURRENT_TIMESTAMP
    }
}).encode())
# Response: {"id": 42, "created": true}
```

**Test Cases**:
1. Valid insert returns ID
2. Missing required field returns error
3. Invalid type (string in INTEGER field) returns error
4. Default timestamp applied correctly
5. Auto-increment ID increments

---

### 7.3 User Story: Select Row by ID

**ID**: GH-ROW-003  
**Title**: As a plugin developer, I want to select a row by ID so that I can retrieve a specific entity

**Description**:
Plugins retrieve rows by primary key ID. This is the fastest query type (single index lookup).

**Acceptance Criteria**:
- [ ] Select via NATS subject `db.row.<plugin>.select`
- [ ] Payload includes table name and ID
- [ ] Returns row data if exists
- [ ] Returns `exists: false` if not found
- [ ] Response time <5ms p95 (primary key lookup)

**Example**:
```python
response = await nats.request('db.row.quote-db.select', json.dumps({
    'table': 'quotes',
    'id': 42
}).encode())
# Response: {
#   "exists": true,
#   "data": {
#     "id": 42,
#     "text": "Keep circulating the tapes",
#     "author": "MST3K",
#     "added_by": "groberts",
#     "timestamp": "2025-11-22T10:30:00Z"
#   }
# }
```

**Test Cases**:
1. Select existing row returns data
2. Select non-existent row returns exists=false
3. Select with invalid ID type returns error
4. Select from unregistered table returns error

---

### 7.4 User Story: Update Row by ID

**ID**: GH-ROW-004  
**Title**: As a plugin developer, I want to update a row by ID so that I can modify entity data

**Description**:
Plugins update specific fields of a row identified by ID. Only provided fields are updated (partial update).

**Acceptance Criteria**:
- [ ] Update via NATS subject `db.row.<plugin>.update`
- [ ] Payload includes table name, ID, and fields to update
- [ ] Partial updates supported (only specified fields changed)
- [ ] Type validation enforced
- [ ] Returns `updated: true` if row existed
- [ ] Returns `updated: false` if row not found (idempotent)

**Example**:
```python
response = await nats.request('db.row.quote-db.update', json.dumps({
    'table': 'quotes',
    'id': 42,
    'data': {
        'author': 'Mystery Science Theater 3000'  # Only update author
    }
}).encode())
# Response: {"updated": true}
```

**Test Cases**:
1. Update existing row succeeds
2. Partial update only changes specified fields
3. Update non-existent row returns updated=false
4. Update with invalid type returns error
5. Update primary key returns error (immutable)

---

### 7.5 User Story: Delete Row by ID

**ID**: GH-ROW-005  
**Title**: As a plugin developer, I want to delete a row by ID so that I can remove unwanted entities

**Description**:
Plugins delete rows by ID. Operation is idempotent (deleting non-existent row succeeds).

**Acceptance Criteria**:
- [ ] Delete via NATS subject `db.row.<plugin>.delete`
- [ ] Payload includes table name and ID
- [ ] Returns `deleted: true` if row existed
- [ ] Returns `deleted: false` if row not found (idempotent)
- [ ] Row permanently removed from database

**Example**:
```python
response = await nats.request('db.row.quote-db.delete', json.dumps({
    'table': 'quotes',
    'id': 42
}).encode())
# Response: {"deleted": true}
```

**Test Cases**:
1. Delete existing row succeeds
2. Delete non-existent row returns deleted=false
3. Select after delete returns exists=false
4. Delete with invalid ID type returns error

---

### 7.6 User Story: Search Rows with Filters

**ID**: GH-ROW-006  
**Title**: As a plugin developer, I want to search rows by field values so that I can query my data

**Description**:
Plugins search rows using equality filters on any field. Results can be limited and paginated.

**Acceptance Criteria**:
- [ ] Search via NATS subject `db.row.<plugin>.search`
- [ ] Payload includes table name and filters (field: value)
- [ ] Equality matching only in Sprint 13
- [ ] Returns array of matching rows
- [ ] Supports limit parameter (default 100, max 1000)
- [ ] Supports offset parameter for pagination
- [ ] Returns metadata (count, truncated flag)

**Example**:
```python
response = await nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {
        'author': 'MST3K'  # Equality filter
    },
    'limit': 10,
    'offset': 0
}).encode())
# Response: {
#   "rows": [
#     {"id": 42, "text": "...", "author": "MST3K", ...},
#     {"id": 43, "text": "...", "author": "MST3K", ...}
#   ],
#   "count": 2,
#   "truncated": false
# }
```

**Test Cases**:
1. Search with single filter returns matching rows
2. Search with multiple filters (AND logic)
3. Search with no matches returns empty array
4. Search with limit returns correct number of rows
5. Pagination (offset + limit) works correctly
6. Search on indexed field is fast (<20ms)

---

### 7.7 User Story: Sort Search Results

**ID**: GH-ROW-007  
**Title**: As a plugin developer, I want to sort search results so that I can get ordered data

**Description**:
Plugins can sort search results by a single field in ascending or descending order.

**Acceptance Criteria**:
- [ ] Search payload includes optional `sort` parameter
- [ ] Sort format: `{"field": "timestamp", "order": "desc"}`
- [ ] Supported orders: "asc", "desc"
- [ ] Default: no sorting (database order)
- [ ] Sort works with pagination

**Example**:
```python
response = await nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {},
    'sort': {'field': 'timestamp', 'order': 'desc'},
    'limit': 10
}).encode())
# Returns 10 most recent quotes
```

**Test Cases**:
1. Sort ascending works
2. Sort descending works
3. Sort on indexed field is fast
4. Sort with pagination returns correct page
5. Invalid sort field returns error

---

### 7.8 User Story: Bulk Insert

**ID**: GH-ROW-008  
**Title**: As a plugin developer, I want to insert multiple rows in one operation so that I can improve performance

**Description**:
Plugins can insert multiple rows in a single NATS request for better efficiency.

**Acceptance Criteria**:
- [ ] Insert payload accepts `data` as array
- [ ] All rows inserted in single transaction
- [ ] Returns array of IDs (same order as input)
- [ ] If any row fails validation, entire operation fails (atomic)
- [ ] Performance: bulk insert 100 rows <100ms

**Example**:
```python
response = await nats.request('db.row.quote-db.insert', json.dumps({
    'table': 'quotes',
    'data': [
        {'text': 'Quote 1', 'author': 'Author 1'},
        {'text': 'Quote 2', 'author': 'Author 2'},
        {'text': 'Quote 3', 'author': 'Author 3'}
    ]
}).encode())
# Response: {"ids": [42, 43, 44], "created": 3}
```

**Test Cases**:
1. Bulk insert 10 rows succeeds
2. Bulk insert 100 rows completes in <100ms
3. Invalid row in batch fails entire operation
4. IDs returned in correct order

---

### 7.9 User Story: Plugin Isolation

**ID**: GH-ROW-009  
**Title**: As a bot administrator, I want plugin table isolation so that plugins cannot access each other's data

**Description**:
DatabaseService enforces plugin isolation by extracting plugin name from NATS subject and scoping all queries to that plugin's tables.

**Acceptance Criteria**:
- [ ] Plugin name extracted from subject: `db.row.<plugin>.insert`
- [ ] Table name scoped: `<plugin>_<table>` in database
- [ ] Plugin A cannot query `<plugin_b>_<table>`
- [ ] Security tests verify isolation with 10+ attack scenarios
- [ ] No SQL injection possible via table names

**Example**:
```python
# quote-db plugin inserts
await nats.request('db.row.quote-db.insert', {...})
# Creates row in table: quote_db_quotes

# trivia plugin inserts
await nats.request('db.row.trivia.insert', {...})
# Creates row in table: trivia_stats

# quote-db CANNOT access trivia table (enforced by subject)
```

**Test Cases**:
1. Plugin A can access own tables
2. Plugin A cannot access Plugin B's tables
3. Table name injection attempt blocked
4. Plugin name validation prevents path traversal
5. Search across plugins returns no results

---

### 7.10 User Story: Schema Validation Errors

**ID**: GH-ROW-010  
**Title**: As a plugin developer, I want clear error messages when my data is invalid so that I can fix bugs quickly

**Description**:
When CRUD operations fail due to schema violations, developers receive detailed error messages explaining the problem.

**Acceptance Criteria**:
- [ ] Missing required field: "Missing required field: text"
- [ ] Type mismatch: "Field 'score' expects INTEGER, got STRING"
- [ ] Table not registered: "Table 'quotes' not found. Register schema first."
- [ ] Invalid field name: "Field 'invalid_field' not in schema"
- [ ] Primary key violation: "Cannot update primary key field 'id'"

**Example**:
```python
# Insert without required field
response = await nats.request('db.row.quote-db.insert', json.dumps({
    'table': 'quotes',
    'data': {
        'author': 'MST3K'
        # Missing required 'text' field
    }
}).encode())
# Response: {
#   "success": false,
#   "error_code": "VALIDATION_ERROR",
#   "message": "Missing required field: text",
#   "field": "text"
# }
```

**Test Cases**:
1. Each error code has specific test
2. Error messages include field names
3. Multiple validation errors reported
4. Stack traces excluded from error responses

---

## 8. Technical Architecture

### 8.1 System Context

```
┌─────────────────┐
│  Plugin Code    │
│  (quote-db,     │
│   trivia, etc)  │
└────────┬────────┘
         │ NATS: db.row.<plugin>.*
         ▼
┌─────────────────────────────────┐
│   DatabaseService               │
│   ┌───────────────────────────┐ │
│   │  Subject Handlers         │ │
│   │  - _handle_row_insert()   │ │
│   │  - _handle_row_select()   │ │
│   │  - _handle_row_update()   │ │
│   │  - _handle_row_delete()   │ │
│   │  - _handle_row_search()   │ │
│   │  - _handle_schema_register│ │
│   └──────────┬────────────────┘ │
│              │                   │
│   ┌──────────▼────────────────┐ │
│   │  SchemaRegistry           │ │
│   │  - validate_schema()      │ │
│   │  - get_table_schema()     │ │
│   │  - register_table()       │ │
│   └──────────┬────────────────┘ │
│              │                   │
│   ┌──────────▼────────────────┐ │
│   │  BotDatabase (ORM)        │ │
│   │  - row_insert()           │ │
│   │  - row_select()           │ │
│   │  - row_update()           │ │
│   │  - row_delete()           │ │
│   │  - row_search()           │ │
│   └──────────┬────────────────┘ │
└──────────────┼──────────────────┘
               │
               ▼
      ┌────────────────┐
      │  PostgreSQL /  │
      │  SQLite        │
      │                │
      │  Tables:       │
      │  - quote_db_   │
      │    quotes      │
      │  - trivia_     │
      │    stats       │
      │  - <plugin>_   │
      │    <table>     │
      └────────────────┘
```

### 8.2 Component Responsibilities

**Plugin Code**:
- Publishes NATS messages to `db.row.<plugin>.*` subjects
- Registers table schema at initialization
- Handles responses (success/error)

**DatabaseService** (new code):
- Subscribes to `db.row.*.*` wildcard
- Extracts plugin name from subject
- Validates requests against registered schemas
- Delegates to BotDatabase ORM methods
- Returns responses via NATS reply subjects

**SchemaRegistry** (new component):
- In-memory cache of registered table schemas
- Validates schema definitions
- Provides schema lookup by `(plugin, table)` key
- Persists schemas to database (for restart recovery)

**BotDatabase** (new methods):
- `row_insert()` - Execute INSERT with type coercion
- `row_select()` - Execute SELECT by primary key
- `row_update()` - Execute UPDATE by primary key
- `row_delete()` - Execute DELETE by primary key
- `row_search()` - Execute SELECT with WHERE, ORDER BY, LIMIT, OFFSET

**Database Tables**:
- Plugin tables prefixed: `<plugin>_<table>`
- Schema metadata table: `plugin_table_schemas`
- Standard columns: `id` (primary key), user-defined fields

### 8.3 Data Flow: Insert Operation

```
1. Plugin publishes:
   Subject: db.row.quote-db.insert
   Payload: {"table": "quotes", "data": {"text": "...", "author": "MST3K"}}

2. DatabaseService._handle_row_insert():
   - Extract plugin_name = "quote-db" from subject
   - Validate table_name = "quotes"
   - Lookup schema: SchemaRegistry.get_table_schema("quote-db", "quotes")
   - Validate data against schema (types, required fields)

3. BotDatabase.row_insert():
   - Build SQLAlchemy INSERT statement
   - Target table: "quote_db_quotes"
   - Execute with async session
   - Get auto-increment ID

4. Response:
   Subject: msg.reply
   Payload: {"id": 42, "created": true}

5. Plugin receives response
```

### 8.4 Data Flow: Search Operation

```
1. Plugin publishes:
   Subject: db.row.quote-db.search
   Payload: {"table": "quotes", "filters": {"author": "MST3K"}, "limit": 10}

2. DatabaseService._handle_row_search():
   - Extract plugin_name = "quote-db"
   - Lookup schema
   - Validate filters (field names exist, types match)

3. BotDatabase.row_search():
   - Build SELECT statement with WHERE clause
   - Add ORDER BY if sort specified
   - Add LIMIT + OFFSET for pagination
   - Execute query with async session
   - Fetch rows

4. Response:
   Payload: {"rows": [...], "count": 2, "truncated": false}

5. Plugin processes results
```

### 8.5 DatabaseClient Abstraction (Optional)

**Role**: Plugin-side convenience wrapper around NATS message formatting (future enhancement)

While plugins can interact with the Database Service directly via NATS messages, the raw API requires significant boilerplate:

**Without DatabaseClient (current approach)**:
```python
# Insert operation
response = await nats.request('rosey.db.row.trivia.insert', json.dumps({
    "table": "game_stats",
    "data": {
        "user_id": "alice",
        "score": 100,
        "timestamp": datetime.now().isoformat()
    }
}), timeout=2.0)
result = json.loads(response.data)
if result.get("success"):
    game_id = result["id"]

# Select operation
response = await nats.request('rosey.db.row.trivia.select', json.dumps({
    "table": "game_stats",
    "id": 42
}), timeout=2.0)
result = json.loads(response.data)
if result.get("exists"):
    record = result["record"]

# Update operation
response = await nats.request('rosey.db.row.trivia.update', json.dumps({
    "table": "game_stats",
    "id": 42,
    "data": {"score": 150}
}), timeout=2.0)
result = json.loads(response.data)

# Search operation
response = await nats.request('rosey.db.row.trivia.search', json.dumps({
    "table": "game_stats",
    "filters": {"user_id": "alice"},
    "sort": {"field": "timestamp", "order": "desc"},
    "limit": 10
}), timeout=2.0)
result = json.loads(response.data)
rows = result["rows"]
```

**With DatabaseClient (future enhancement)**:
```python
# Initialize once per plugin
db = DatabaseClient(nats_client, plugin_name="trivia")

# Insert operation - cleaner API
game_id = await db.row.insert("game_stats", {
    "user_id": "alice",
    "score": 100,
    "timestamp": datetime.now()
})

# Select operation - returns None if not found
record = await db.row.select("game_stats", id=42)
if record:
    print(f"Score: {record['score']}")

# Update operation - returns True if successful
success = await db.row.update("game_stats", 42, {"score": 150})

# Delete operation
deleted = await db.row.delete("game_stats", 42)

# Search operation - type-safe result
results = await db.row.search(
    "game_stats",
    filters={"user_id": "alice"},
    sort=("timestamp", "desc"),
    limit=10
)
for row in results:
    print(f"{row['user_id']}: {row['score']}")
```

**Benefits of DatabaseClient**:
1. **Less Boilerplate**: No manual JSON serialization, NATS subject construction, or response parsing
2. **Type Safety**: IDE autocomplete and type hints for all operations
3. **Error Handling**: Converts NATS errors to Python exceptions with clear messages
4. **Consistent API**: Same patterns across KV, row, and future operations
5. **Testing**: Mock DatabaseClient instead of NATS connection
6. **Developer Experience**: Focus on business logic, not message plumbing

**Example DatabaseClient Implementation** (future):
```python
# common/database_client.py

from typing import Optional, Any, Dict, List
from datetime import datetime
import json
from nats.aio.client import Client as NATS

class DatabaseClient:
    """
    Convenience wrapper for plugin-side database operations.
    
    Abstracts NATS message formatting and response parsing.
    """
    
    def __init__(self, nats_client: NATS, plugin_name: str):
        self.nats = nats_client
        self.plugin = plugin_name
        self.row = RowOperations(self)
        self.kv = KVOperations(self)  # From Sprint 12
    
class RowOperations:
    """Row CRUD operations."""
    
    def __init__(self, client: DatabaseClient):
        self._client = client
    
    async def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert a row and return its ID.
        
        Args:
            table: Table name (without plugin prefix)
            data: Field values
            
        Returns:
            Auto-generated ID
            
        Raises:
            DatabaseError: If insertion fails
        """
        subject = f"rosey.db.row.{self._client.plugin}.insert"
        payload = json.dumps({"table": table, "data": data})
        
        response = await self._client.nats.request(subject, payload.encode(), timeout=2.0)
        result = json.loads(response.data)
        
        if not result.get("success"):
            raise DatabaseError(result.get("message", "Insert failed"))
        
        return result["id"]
    
    async def select(self, table: str, id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a row by primary key.
        
        Returns:
            Record dict, or None if not found
        """
        subject = f"rosey.db.row.{self._client.plugin}.select"
        payload = json.dumps({"table": table, "id": id})
        
        response = await self._client.nats.request(subject, payload.encode(), timeout=2.0)
        result = json.loads(response.data)
        
        if result.get("exists"):
            return result["record"]
        return None
    
    async def update(self, table: str, id: int, data: Dict[str, Any]) -> bool:
        """
        Update a row by primary key.
        
        Returns:
            True if row was updated, False if not found
        """
        subject = f"rosey.db.row.{self._client.plugin}.update"
        payload = json.dumps({"table": table, "id": id, "data": data})
        
        response = await self._client.nats.request(subject, payload.encode(), timeout=2.0)
        result = json.loads(response.data)
        
        return result.get("updated", False)
    
    async def delete(self, table: str, id: int) -> bool:
        """
        Delete a row by primary key.
        
        Returns:
            True if row was deleted, False if not found
        """
        subject = f"rosey.db.row.{self._client.plugin}.delete"
        payload = json.dumps({"table": table, "id": id})
        
        response = await self._client.nats.request(subject, payload.encode(), timeout=2.0)
        result = json.loads(response.data)
        
        return result.get("deleted", False)
    
    async def search(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[tuple[str, str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search rows with filters, sorting, and pagination.
        
        Args:
            table: Table name
            filters: WHERE conditions (field: value)
            sort: Tuple of (field, order) where order is 'asc' or 'desc'
            limit: Max rows to return
            offset: Skip N rows
            
        Returns:
            List of matching rows
        """
        subject = f"rosey.db.row.{self._client.plugin}.search"
        payload = {
            "table": table,
            "limit": limit,
            "offset": offset
        }
        
        if filters:
            payload["filters"] = filters
        if sort:
            payload["sort"] = {"field": sort[0], "order": sort[1]}
        
        response = await self._client.nats.request(
            subject,
            json.dumps(payload).encode(),
            timeout=2.0
        )
        result = json.loads(response.data)
        
        return result.get("rows", [])

class DatabaseError(Exception):
    """Database operation failed."""
    pass
```

**Usage in Plugins** (future):
```python
# plugin/trivia.py

from common.database_client import DatabaseClient

class TriviaPlugin:
    def __init__(self, nats_client):
        self.db = DatabaseClient(nats_client, plugin_name="trivia")
    
    async def record_game(self, user_id: str, score: int):
        """Record a completed trivia game."""
        game_id = await self.db.row.insert("game_stats", {
            "user_id": user_id,
            "score": score,
            "timestamp": datetime.now()
        })
        print(f"Recorded game {game_id}")
    
    async def get_user_stats(self, user_id: str):
        """Get all games for a user."""
        games = await self.db.row.search(
            "game_stats",
            filters={"user_id": user_id},
            sort=("timestamp", "desc")
        )
        
        total_score = sum(g["score"] for g in games)
        return {
            "games_played": len(games),
            "total_score": total_score,
            "avg_score": total_score / len(games) if games else 0
        }
```

**Decision**: 
- **Not implemented in Sprint 13** (focus on core Database Service functionality)
- Plugins use NATS directly (establishes API contract)
- **Recommended for Sprint 14 or later** after row operations are proven stable
- DatabaseClient can be added without breaking existing plugins (backward compatible)

**Rationale**:
- Sprint B establishes the NATS API contract that must remain stable
- Adding wrapper later is non-breaking (just convenience layer)
- Keeps Sprint B focused on robust Database Service implementation
- Allows validation of API design with real plugin usage before adding abstraction

**Performance Note**: The NATS architecture provides **5% better throughput** than direct database calls in burst conditions (1k messages/sec), so the DatabaseClient wrapper adds developer convenience without performance penalty.

---

## 9. Table Schema Registry

### 9.1 Schema Storage Table

**Table**: `plugin_table_schemas`

```sql
CREATE TABLE plugin_table_schemas (
    plugin_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    schema_json TEXT NOT NULL,  -- JSON schema definition
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (plugin_name, table_name)
);
```

**Purpose**: Persist schemas across DatabaseService restarts

### 9.2 Schema Definition Format

```json
{
    "table": "quotes",
    "fields": [
        {
            "name": "id",
            "type": "INTEGER",
            "primary_key": true,
            "auto_increment": true
        },
        {
            "name": "text",
            "type": "TEXT",
            "nullable": false
        },
        {
            "name": "author",
            "type": "VARCHAR(255)",
            "nullable": true
        },
        {
            "name": "timestamp",
            "type": "TIMESTAMP",
            "default": "CURRENT_TIMESTAMP"
        }
    ],
    "indexes": [
        {"fields": ["author"]},
        {"fields": ["timestamp"]}
    ]
}
```

### 9.3 Supported Field Types

| Type | SQLite | PostgreSQL | Python Type | Notes |
|------|--------|------------|-------------|-------|
| INTEGER | INTEGER | INTEGER | int | 32-bit signed |
| BIGINT | INTEGER | BIGINT | int | 64-bit signed |
| FLOAT | REAL | DOUBLE PRECISION | float | 64-bit floating point |
| TEXT | TEXT | TEXT | str | Unlimited length |
| VARCHAR(n) | TEXT | VARCHAR(n) | str | Max n characters |
| BOOLEAN | INTEGER | BOOLEAN | bool | SQLite: 0/1 |
| TIMESTAMP | TEXT | TIMESTAMP WITH TIME ZONE | datetime | ISO 8601 format |
| JSON | TEXT | JSONB | dict/list | Stored as JSON string |

### 9.4 SchemaRegistry Class

```python
# common/schema_registry.py

from typing import Dict, Optional, Any
import json

class SchemaRegistry:
    """
    In-memory cache of plugin table schemas with persistence.
    
    Schemas are loaded from plugin_table_schemas table at startup
    and cached for fast validation during CRUD operations.
    """
    
    def __init__(self, db: BotDatabase):
        self.db = db
        self._schemas: Dict[tuple[str, str], dict] = {}  # (plugin, table) -> schema
        
    async def load_schemas(self):
        """Load all schemas from database into memory cache."""
        schemas = await self.db.fetch_all(
            "SELECT plugin_name, table_name, schema_json FROM plugin_table_schemas"
        )
        for row in schemas:
            key = (row['plugin_name'], row['table_name'])
            self._schemas[key] = json.loads(row['schema_json'])
        
        self.logger.info(f"Loaded {len(self._schemas)} table schemas")
    
    async def register_schema(
        self,
        plugin_name: str,
        table_name: str,
        schema: dict
    ) -> None:
        """
        Register or validate a table schema.
        
        If schema already exists and matches, returns success.
        If schema exists and differs, raises SchemaConflictError.
        If schema is new, creates table and stores schema.
        """
        # Validate schema structure
        self._validate_schema_structure(schema)
        
        # Check existing schema
        key = (plugin_name, table_name)
        existing = self._schemas.get(key)
        
        if existing:
            if existing == schema:
                return  # Idempotent: same schema OK
            else:
                raise SchemaConflictError(
                    f"Table {plugin_name}.{table_name} schema mismatch. "
                    f"Use migrations to alter schema."
                )
        
        # Create table in database
        full_table_name = f"{plugin_name}_{table_name}"
        await self.db.create_table_from_schema(full_table_name, schema)
        
        # Store schema in database
        await self.db.execute(
            """
            INSERT INTO plugin_table_schemas (plugin_name, table_name, schema_json)
            VALUES (:plugin, :table, :schema)
            """,
            {
                'plugin': plugin_name,
                'table': table_name,
                'schema': json.dumps(schema)
            }
        )
        
        # Cache in memory
        self._schemas[key] = schema
        
        self.logger.info(f"Registered schema: {plugin_name}.{table_name}")
    
    def get_schema(self, plugin_name: str, table_name: str) -> Optional[dict]:
        """Get schema for table, or None if not registered."""
        return self._schemas.get((plugin_name, table_name))
    
    def _validate_schema_structure(self, schema: dict) -> None:
        """Validate schema definition format."""
        # Check required keys
        if 'table' not in schema:
            raise ValidationError("Schema missing 'table' field")
        if 'fields' not in schema or not isinstance(schema['fields'], list):
            raise ValidationError("Schema missing 'fields' array")
        
        # Check for primary key
        has_pk = any(f.get('primary_key') for f in schema['fields'])
        if not has_pk:
            raise ValidationError("Schema must define a primary_key field")
        
        # Validate field types
        valid_types = {
            'INTEGER', 'BIGINT', 'FLOAT', 'TEXT', 
            'BOOLEAN', 'TIMESTAMP', 'JSON'
        }
        for field in schema['fields']:
            field_type = field.get('type', '').split('(')[0]  # VARCHAR(255) -> VARCHAR
            if field_type not in valid_types and not field_type.startswith('VARCHAR'):
                raise ValidationError(f"Invalid field type: {field_type}")
```

---

## 10. NATS Subject Design

### 10.1 Subject Patterns

**Schema Registration**:
- `db.schema.<plugin>.register` - Register table schema

**CRUD Operations**:
- `db.row.<plugin>.insert` - Insert row(s)
- `db.row.<plugin>.select` - Select row by ID
- `db.row.<plugin>.update` - Update row by ID
- `db.row.<plugin>.delete` - Delete row by ID
- `db.row.<plugin>.search` - Search rows with filters

### 10.2 Subject Subscription Registration

```python
# In DatabaseService.start()
async def start(self):
    # ... existing KV subscriptions ...
    
    # Schema registration
    self._subscriptions.append(
        await self.nats.subscribe('db.schema.*.register', 
                                 cb=self._handle_schema_register)
    )
    
    # Row operations (wildcard for all plugins)
    self._subscriptions.extend([
        await self.nats.subscribe('db.row.*.insert', cb=self._handle_row_insert),
        await self.nats.subscribe('db.row.*.select', cb=self._handle_row_select),
        await self.nats.subscribe('db.row.*.update', cb=self._handle_row_update),
        await self.nats.subscribe('db.row.*.delete', cb=self._handle_row_delete),
        await self.nats.subscribe('db.row.*.search', cb=self._handle_row_search),
    ])
    
    self.logger.info("DatabaseService: Row operation handlers registered")
```

### 10.3 Plugin Name Extraction

```python
def _extract_plugin_and_operation(self, subject: str) -> tuple[str, str]:
    """
    Extract plugin name and operation from NATS subject.
    
    Subject: db.row.<plugin>.<operation>
    Example: db.row.quote-db.insert -> ("quote-db", "insert")
    """
    parts = subject.split('.')
    if len(parts) != 4 or parts[0] != 'db' or parts[1] != 'row':
        raise ValueError(f"Invalid subject format: {subject}")
    
    plugin_name = parts[2]
    operation = parts[3]
    
    # Validate plugin name (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-z0-9\-_]+$', plugin_name):
        raise ValueError(f"Invalid plugin name: {plugin_name}")
    
    return plugin_name, operation
```

---

## 11. API Specifications

### 11.1 Schema Registration

**NATS Subject**: `db.schema.<plugin>.register`

**Request Payload**:
```json
{
  "table": "quotes",
  "fields": [
    {"name": "id", "type": "INTEGER", "primary_key": true, "auto_increment": true},
    {"name": "text", "type": "TEXT", "nullable": false},
    {"name": "author", "type": "VARCHAR(255)"},
    {"name": "timestamp", "type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
  ],
  "indexes": [
    {"fields": ["author"]},
    {"fields": ["timestamp"]}
  ]
}
```

**Success Response**:
```json
{
  "success": true,
  "table": "quotes",
  "full_table_name": "quote_db_quotes"
}
```

**Error Response** (schema conflict):
```json
{
  "success": false,
  "error_code": "SCHEMA_CONFLICT",
  "message": "Table quote-db.quotes schema mismatch. Use migrations to alter schema."
}
```

---

### 11.2 Insert Operation

**NATS Subject**: `db.row.<plugin>.insert`

**Single Row Request**:
```json
{
  "table": "quotes",
  "data": {
    "text": "Keep circulating the tapes",
    "author": "MST3K",
    "added_by": "groberts"
  }
}
```

**Bulk Insert Request**:
```json
{
  "table": "quotes",
  "data": [
    {"text": "Quote 1", "author": "Author 1"},
    {"text": "Quote 2", "author": "Author 2"},
    {"text": "Quote 3", "author": "Author 3"}
  ]
}
```

**Single Row Response**:
```json
{
  "id": 42,
  "created": true
}
```

**Bulk Insert Response**:
```json
{
  "ids": [42, 43, 44],
  "created": 3
}
```

**Error Response** (validation):
```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Missing required field: text",
  "field": "text"
}
```

**Error Response** (type mismatch):
```json
{
  "success": false,
  "error_code": "TYPE_MISMATCH",
  "message": "Field 'timestamp' expects TIMESTAMP, got STRING",
  "field": "timestamp",
  "expected": "TIMESTAMP",
  "got": "STRING"
}
```

---

### 11.3 Select Operation

**NATS Subject**: `db.row.<plugin>.select`

**Request Payload**:
```json
{
  "table": "quotes",
  "id": 42
}
```

**Success Response** (found):
```json
{
  "exists": true,
  "data": {
    "id": 42,
    "text": "Keep circulating the tapes",
    "author": "MST3K",
    "added_by": "groberts",
    "timestamp": "2025-11-22T10:30:00Z"
  }
}
```

**Success Response** (not found):
```json
{
  "exists": false
}
```

**Error Response** (table not registered):
```json
{
  "success": false,
  "error_code": "TABLE_NOT_FOUND",
  "message": "Table 'quotes' not found. Register schema first.",
  "table": "quotes"
}
```

---

### 11.4 Update Operation

**NATS Subject**: `db.row.<plugin>.update`

**Request Payload** (partial update):
```json
{
  "table": "quotes",
  "id": 42,
  "data": {
    "author": "Mystery Science Theater 3000"
  }
}
```

**Success Response**:
```json
{
  "updated": true
}
```

**Response** (row not found):
```json
{
  "updated": false
}
```

**Error Response** (attempting to update primary key):
```json
{
  "success": false,
  "error_code": "IMMUTABLE_FIELD",
  "message": "Cannot update primary key field 'id'",
  "field": "id"
}
```

---

### 11.5 Delete Operation

**NATS Subject**: `db.row.<plugin>.delete`

**Request Payload**:
```json
{
  "table": "quotes",
  "id": 42
}
```

**Success Response** (deleted):
```json
{
  "deleted": true
}
```

**Response** (row not found):
```json
{
  "deleted": false
}
```

---

### 11.6 Search Operation

**NATS Subject**: `db.row.<plugin>.search`

**Basic Search Request**:
```json
{
  "table": "quotes",
  "filters": {
    "author": "MST3K"
  },
  "limit": 10,
  "offset": 0
}
```

**Search with Sort**:
```json
{
  "table": "quotes",
  "filters": {},
  "sort": {"field": "timestamp", "order": "desc"},
  "limit": 10
}
```

**Search with Multiple Filters** (AND logic):
```json
{
  "table": "trivia_stats",
  "filters": {
    "user_id": "groberts",
    "active": true
  },
  "limit": 100
}
```

**Success Response**:
```json
{
  "rows": [
    {
      "id": 42,
      "text": "Keep circulating the tapes",
      "author": "MST3K",
      "added_by": "groberts",
      "timestamp": "2025-11-22T10:30:00Z"
    },
    {
      "id": 43,
      "text": "Watch out for snakes!",
      "author": "MST3K",
      "added_by": "groberts",
      "timestamp": "2025-11-22T10:35:00Z"
    }
  ],
  "count": 2,
  "truncated": false
}
```

**Empty Response**:
```json
{
  "rows": [],
  "count": 0,
  "truncated": false
}
```

**Truncated Response** (more rows available):
```json
{
  "rows": [...],
  "count": 100,
  "truncated": true
}
```

---

## 12. Implementation Plan

### 12.1 Sortie Sequence

**Total**: 5 sorties over 4-5 days

#### **Sortie 1: Schema Registry & Table Creation** (Day 1, ~4 hours)

**Branch**: `feature/row-schema-registry`

**Files Changed**:
- `common/schema_registry.py` - New file for SchemaRegistry class
- `common/models.py` - Add PluginTableSchemas model
- `alembic/versions/XXX_add_plugin_table_schemas.py` - Migration
- `tests/unit/test_schema_registry.py` - Schema registry tests

**Deliverables**:
- [ ] PluginTableSchemas SQLAlchemy model
- [ ] SchemaRegistry class with in-memory cache
- [ ] Schema validation logic
- [ ] Dynamic table creation from schema
- [ ] Alembic migration
- [ ] Unit tests (20+ tests)

**Testing**:
```bash
alembic upgrade head
pytest tests/unit/test_schema_registry.py -v --cov=common.schema_registry
```

**Acceptance**:
- ✅ Migration applies cleanly
- ✅ Schema validation rejects invalid schemas
- ✅ Table creation works (SQLite + PostgreSQL)
- ✅ Schema cache loaded from database
- ✅ Unit tests pass

---

#### **Sortie 2: Insert & Select Operations** (Day 1-2, ~5 hours)

**Branch**: `feature/row-insert-select`

**Files Changed**:
- `common/database.py` - Add row_insert(), row_select()
- `common/database_service.py` - Add _handle_row_insert(), _handle_row_select(), _handle_schema_register()
- `tests/unit/test_database_row.py` - Row operation tests
- `tests/integration/test_row_nats.py` - NATS integration tests

**Deliverables**:
- [ ] BotDatabase.row_insert() method
- [ ] BotDatabase.row_select() method
- [ ] DatabaseService NATS handlers for insert/select/schema
- [ ] Type coercion (string -> datetime, etc.)
- [ ] Auto-increment ID handling
- [ ] Plugin isolation enforcement
- [ ] Unit tests (20+ tests)
- [ ] Integration tests (10+ tests)

**Code Snippet**:
```python
# common/database.py

async def row_insert(
    self,
    plugin_name: str,
    table_name: str,
    data: dict | list[dict]
) -> dict:
    """
    Insert row(s) into plugin table.
    
    Args:
        plugin_name: Plugin identifier
        table_name: Table name (without plugin prefix)
        data: Single dict or list of dicts to insert
    
    Returns:
        Single: {"id": 42, "created": True}
        Bulk: {"ids": [42, 43, 44], "created": 3}
    """
    full_table_name = f"{plugin_name}_{table_name}"
    
    # Get schema from registry
    schema = self.schema_registry.get_schema(plugin_name, table_name)
    if not schema:
        raise ValueError(f"Table {table_name} not registered")
    
    # Handle bulk vs single
    is_bulk = isinstance(data, list)
    rows = data if is_bulk else [data]
    
    # Validate and coerce types
    for row in rows:
        self._validate_row_data(row, schema)
    
    # Build INSERT statement
    table = self.get_table(full_table_name)
    
    async with self.session_factory() as session:
        if is_bulk:
            # Bulk insert
            result = await session.execute(
                insert(table).returning(table.c.id),
                rows
            )
            ids = [row[0] for row in result.fetchall()]
            await session.commit()
            return {"ids": ids, "created": len(ids)}
        else:
            # Single insert
            result = await session.execute(
                insert(table).values(**rows[0]).returning(table.c.id)
            )
            row_id = result.scalar()
            await session.commit()
            return {"id": row_id, "created": True}

async def row_select(
    self,
    plugin_name: str,
    table_name: str,
    row_id: int
) -> dict:
    """
    Select row by primary key ID.
    
    Returns:
        {"exists": True, "data": {...}} or {"exists": False}
    """
    full_table_name = f"{plugin_name}_{table_name}"
    table = self.get_table(full_table_name)
    
    async with self.session_factory() as session:
        stmt = select(table).where(table.c.id == row_id)
        result = await session.execute(stmt)
        row = result.fetchone()
        
        if row:
            return {"exists": True, "data": dict(row._mapping)}
        else:
            return {"exists": False}
```

**Testing**:
```bash
pytest tests/unit/test_database_row.py::TestInsert -v
pytest tests/unit/test_database_row.py::TestSelect -v
pytest tests/integration/test_row_nats.py::test_insert_via_nats -v
```

**Acceptance**:
- ✅ Single insert works
- ✅ Bulk insert works
- ✅ Select by ID works
- ✅ Type validation enforced
- ✅ Plugin isolation enforced
- ✅ All tests pass

---

#### **Sortie 3: Update & Delete Operations** (Day 2-3, ~4 hours)

**Branch**: `feature/row-update-delete`

**Files Changed**:
- `common/database.py` - Add row_update(), row_delete()
- `common/database_service.py` - Add _handle_row_update(), _handle_row_delete()
- `tests/unit/test_database_row.py` - Update/delete tests
- `tests/integration/test_row_nats.py` - Update/delete integration tests

**Deliverables**:
- [ ] BotDatabase.row_update() method (partial updates)
- [ ] BotDatabase.row_delete() method (idempotent)
- [ ] DatabaseService NATS handlers
- [ ] Primary key immutability enforcement
- [ ] Unit tests (15+ tests)
- [ ] Integration tests (8+ tests)

**Testing**:
```bash
pytest tests/unit/test_database_row.py::TestUpdate -v
pytest tests/unit/test_database_row.py::TestDelete -v
```

**Acceptance**:
- ✅ Update modifies only specified fields
- ✅ Delete removes row
- ✅ Delete non-existent row is idempotent
- ✅ Cannot update primary key
- ✅ All tests pass

---

#### **Sortie 4: Search with Filters & Pagination** (Day 3-4, ~5 hours)

**Branch**: `feature/row-search`

**Files Changed**:
- `common/database.py` - Add row_search()
- `common/database_service.py` - Add _handle_row_search()
- `tests/unit/test_database_row.py` - Search tests
- `tests/integration/test_row_nats.py` - Search integration tests

**Deliverables**:
- [ ] BotDatabase.row_search() with filters
- [ ] Equality filters (AND logic)
- [ ] Sorting (single field, ASC/DESC)
- [ ] Pagination (limit + offset)
- [ ] Result metadata (count, truncated)
- [ ] Index usage for performance
- [ ] Unit tests (20+ tests)
- [ ] Integration tests (12+ tests)

**Code Snippet**:
```python
# common/database.py

async def row_search(
    self,
    plugin_name: str,
    table_name: str,
    filters: dict = None,
    sort: dict = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """
    Search rows with filters, sorting, and pagination.
    
    Args:
        plugin_name: Plugin identifier
        table_name: Table name
        filters: Field equality filters (AND logic)
        sort: {"field": "timestamp", "order": "desc"}
        limit: Max rows to return (default 100, max 1000)
        offset: Pagination offset
    
    Returns:
        {"rows": [...], "count": int, "truncated": bool}
    """
    full_table_name = f"{plugin_name}_{table_name}"
    table = self.get_table(full_table_name)
    
    # Build WHERE clause
    stmt = select(table)
    if filters:
        for field, value in filters.items():
            stmt = stmt.where(table.c[field] == value)
    
    # Add ORDER BY
    if sort:
        field = sort['field']
        order = sort.get('order', 'asc')
        if order == 'desc':
            stmt = stmt.order_by(table.c[field].desc())
        else:
            stmt = stmt.order_by(table.c[field])
    
    # Pagination with truncation detection
    stmt = stmt.limit(limit + 1).offset(offset)
    
    async with self.session_factory() as session:
        result = await session.execute(stmt)
        rows = [dict(row._mapping) for row in result.fetchall()]
        
        truncated = len(rows) > limit
        if truncated:
            rows = rows[:limit]
        
        return {
            "rows": rows,
            "count": len(rows),
            "truncated": truncated
        }
```

**Testing**:
```bash
pytest tests/unit/test_database_row.py::TestSearch -v
pytest tests/integration/test_row_nats.py::test_search_filters -v
pytest tests/integration/test_row_nats.py::test_search_pagination -v
```

**Acceptance**:
- ✅ Search with single filter works
- ✅ Search with multiple filters (AND) works
- ✅ Sorting works (ASC/DESC)
- ✅ Pagination works (limit + offset)
- ✅ Truncation detection works
- ✅ Empty search returns empty array
- ✅ All tests pass

---

#### **Sortie 5: Testing, Polish & Documentation** (Day 4-5, ~4 hours)

**Branch**: `feature/row-operations-polish`

**Files Changed**:
- `tests/unit/test_database_row.py` - Additional edge case tests
- `tests/integration/test_row_nats.py` - End-to-end workflow tests
- `tests/security/test_row_isolation.py` - Security/isolation tests
- `tests/performance/test_row_performance.py` - Performance benchmarks
- `docs/guides/PLUGIN_ROW_STORAGE.md` - User guide
- `docs/ARCHITECTURE.md` - Update with row operations

**Deliverables**:
- [ ] Edge case tests (20+ tests)
- [ ] Security tests (15+ tests for isolation)
- [ ] Performance tests (5+ benchmarks)
- [ ] User guide with examples
- [ ] Architecture documentation updated
- [ ] Coverage ≥85%

**Testing**:
```bash
pytest tests/unit/test_database_row.py -v --cov=common.database
pytest tests/integration/test_row_nats.py -v
pytest tests/security/test_row_isolation.py -v
pytest tests/performance/test_row_performance.py -v
```

**Acceptance**:
- ✅ All tests pass
- ✅ Coverage ≥85%
- ✅ No cross-plugin data access
- ✅ Performance targets met
- ✅ Documentation complete

---

## 13. Testing Strategy

### 13.1 Test Coverage Goals

**Overall**: ≥85%  
**Critical Paths**: 100%
- Schema validation
- CRUD operations
- Plugin isolation
- Type coercion

**Test Distribution**:
- Unit tests: 95+ tests
- Integration tests: 40+ tests
- Performance tests: 5+ tests
- Security tests: 15+ tests

### 13.2 Unit Tests

**File**: `tests/unit/test_schema_registry.py`

```python
class TestSchemaRegistry:
    async def test_register_valid_schema(self, db):
        schema = {
            'table': 'quotes',
            'fields': [
                {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
                {'name': 'text', 'type': 'TEXT'}
            ]
        }
        await db.schema_registry.register_schema('test-plugin', 'quotes', schema)
        
        # Verify in cache
        cached = db.schema_registry.get_schema('test-plugin', 'quotes')
        assert cached == schema
    
    async def test_schema_conflict(self, db):
        schema1 = {...}
        schema2 = {...}  # Different
        
        await db.schema_registry.register_schema('test-plugin', 'quotes', schema1)
        
        with pytest.raises(SchemaConflictError):
            await db.schema_registry.register_schema('test-plugin', 'quotes', schema2)
    
    async def test_invalid_type(self, db):
        schema = {
            'table': 'bad',
            'fields': [
                {'name': 'field1', 'type': 'IMAGINARY'}
            ]
        }
        
        with pytest.raises(ValidationError, match='Invalid field type'):
            await db.schema_registry.register_schema('test-plugin', 'bad', schema)
```

**File**: `tests/unit/test_database_row.py`

```python
class TestRowInsert:
    async def test_insert_single_row(self, db):
        data = {'text': 'Test quote', 'author': 'Test'}
        result = await db.row_insert('test-plugin', 'quotes', data)
        
        assert 'id' in result
        assert result['created'] == True
        
        # Verify in database
        row = await db.row_select('test-plugin', 'quotes', result['id'])
        assert row['exists'] == True
        assert row['data']['text'] == 'Test quote'
    
    async def test_insert_bulk_rows(self, db):
        data = [
            {'text': 'Quote 1', 'author': 'Author 1'},
            {'text': 'Quote 2', 'author': 'Author 2'},
            {'text': 'Quote 3', 'author': 'Author 3'}
        ]
        result = await db.row_insert('test-plugin', 'quotes', data)
        
        assert len(result['ids']) == 3
        assert result['created'] == 3
    
    async def test_insert_missing_required_field(self, db):
        data = {'author': 'Test'}  # Missing 'text'
        
        with pytest.raises(ValidationError, match='Missing required field: text'):
            await db.row_insert('test-plugin', 'quotes', data)
    
    async def test_insert_type_mismatch(self, db):
        data = {'text': 'Test', 'timestamp': 'not a timestamp'}
        
        with pytest.raises(ValidationError, match='expects TIMESTAMP'):
            await db.row_insert('test-plugin', 'quotes', data)

class TestRowSearch:
    async def test_search_by_single_filter(self, db):
        # Insert test data
        await db.row_insert('test-plugin', 'quotes', [
            {'text': 'Q1', 'author': 'MST3K'},
            {'text': 'Q2', 'author': 'MST3K'},
            {'text': 'Q3', 'author': 'Other'}
        ])
        
        # Search
        result = await db.row_search('test-plugin', 'quotes', filters={'author': 'MST3K'})
        
        assert result['count'] == 2
        assert all(row['author'] == 'MST3K' for row in result['rows'])
    
    async def test_search_with_pagination(self, db):
        # Insert 25 quotes
        data = [{'text': f'Quote {i}', 'author': 'Test'} for i in range(25)]
        await db.row_insert('test-plugin', 'quotes', data)
        
        # First page
        page1 = await db.row_search('test-plugin', 'quotes', limit=10, offset=0)
        assert page1['count'] == 10
        assert page1['truncated'] == True
        
        # Second page
        page2 = await db.row_search('test-plugin', 'quotes', limit=10, offset=10)
        assert page2['count'] == 10
        
        # Third page
        page3 = await db.row_search('test-plugin', 'quotes', limit=10, offset=20)
        assert page3['count'] == 5
        assert page3['truncated'] == False
```

### 13.3 Integration Tests

**File**: `tests/integration/test_row_nats.py`

```python
class TestRowNATSIntegration:
    async def test_end_to_end_workflow(self, nats_client, db_service):
        # 1. Register schema
        await nats_client.request(
            'db.schema.test-plugin.register',
            json.dumps({
                'table': 'quotes',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
                    {'name': 'text', 'type': 'TEXT', 'nullable': False}
                ]
            }).encode()
        )
        
        # 2. Insert row
        insert_resp = await nats_client.request(
            'db.row.test-plugin.insert',
            json.dumps({
                'table': 'quotes',
                'data': {'text': 'Test quote'}
            }).encode()
        )
        insert_data = json.loads(insert_resp.data)
        quote_id = insert_data['id']
        
        # 3. Select by ID
        select_resp = await nats_client.request(
            'db.row.test-plugin.select',
            json.dumps({
                'table': 'quotes',
                'id': quote_id
            }).encode()
        )
        select_data = json.loads(select_resp.data)
        assert select_data['exists'] == True
        assert select_data['data']['text'] == 'Test quote'
        
        # 4. Update
        await nats_client.request(
            'db.row.test-plugin.update',
            json.dumps({
                'table': 'quotes',
                'id': quote_id,
                'data': {'text': 'Updated quote'}
            }).encode()
        )
        
        # 5. Verify update
        select_resp2 = await nats_client.request(
            'db.row.test-plugin.select',
            json.dumps({'table': 'quotes', 'id': quote_id}).encode()
        )
        select_data2 = json.loads(select_resp2.data)
        assert select_data2['data']['text'] == 'Updated quote'
        
        # 6. Delete
        delete_resp = await nats_client.request(
            'db.row.test-plugin.delete',
            json.dumps({'table': 'quotes', 'id': quote_id}).encode()
        )
        delete_data = json.loads(delete_resp.data)
        assert delete_data['deleted'] == True
        
        # 7. Verify deleted
        select_resp3 = await nats_client.request(
            'db.row.test-plugin.select',
            json.dumps({'table': 'quotes', 'id': quote_id}).encode()
        )
        select_data3 = json.loads(select_resp3.data)
        assert select_data3['exists'] == False
```

### 13.4 Security Tests

**File**: `tests/security/test_row_isolation.py`

```python
class TestRowIsolation:
    async def test_plugin_cannot_read_other_plugin_table(self, db):
        # plugin-a inserts
        await db.row_insert('plugin-a', 'data', {'field': 'secret-a'})
        
        # plugin-b cannot read plugin-a's table
        with pytest.raises(ValueError, match='not registered'):
            await db.row_search('plugin-b', 'data', {})
    
    async def test_table_name_injection_blocked(self, db):
        # Attempt SQL injection via table name
        malicious_table = "quotes; DROP TABLE users; --"
        
        with pytest.raises(ValueError):
            await db.row_insert('test-plugin', malicious_table, {})
```

---

## 14. Security & Isolation

### 14.1 Plugin Isolation Enforcement

**Table Namespace**:
- Plugin tables automatically prefixed: `<plugin>_<table>`
- Example: quote-db plugin's "quotes" table → `quote_db_quotes`
- Plugin cannot specify full table name (prevents cross-plugin access)

**NATS Subject Extraction**:
```python
# Plugin identity from subject, NOT payload
subject = 'db.row.quote-db.insert'
plugin_name = subject.split('.')[2]  # "quote-db"

# Query always scoped to plugin's tables
full_table_name = f"{plugin_name}_{table_name}"
```

**SQL Injection Prevention**:
- All queries use SQLAlchemy ORM (parameterized queries)
- Table names validated (alphanumeric + underscores only)
- Field names validated against registered schema
- No string interpolation in SQL

### 14.2 Schema Validation

**Type Safety**:
- Field types validated at registration time
- Data types validated at insert/update time
- Type coercion attempted (string → datetime)
- Mismatches rejected with clear errors

**Required Fields**:
- Fields with `nullable: false` enforced
- Insert without required field → ValidationError
- NULL values rejected for non-nullable fields

**Primary Key Immutability**:
- Primary key fields cannot be updated
- Attempt to update PK → IMMUTABLE_FIELD error
- Prevents ID collision and data corruption

### 14.3 Attack Scenarios Prevented

| Attack | Prevention |
|--------|------------|
| Cross-plugin read | Plugin name from subject, scoped queries |
| Cross-plugin write | Plugin name from subject, table prefixing |
| SQL injection | SQLAlchemy ORM, parameterized queries |
| Table name injection | Regex validation, alphanumeric only |
| Field name injection | Schema validation, field existence check |
| Type confusion | Runtime type validation and coercion |
| Schema manipulation | Schema changes require migrations (Sprint 15) |

---

## 15. Performance Requirements

### 15.1 Latency Targets

**Insert Operations**:
- Single insert: <10ms p95 latency
- Bulk insert (100 rows): <100ms p95 latency
- Auto-increment ID assignment: <1ms

**Select by ID**:
- <5ms p95 latency (primary key lookup)
- <2ms p50 latency

**Update by ID**:
- <10ms p95 latency
- Partial update (few fields): <8ms p95

**Delete by ID**:
- <8ms p95 latency
- Idempotent (same latency if not found)

**Search Operations**:
- Single equality filter: <20ms p95
- Multiple filters (indexed): <30ms p95
- Sort + pagination (indexed): <25ms p95
- No filters (full table scan): <50ms p95 for 1000 rows

### 15.2 Throughput Targets

**Mixed Workload** (40% insert, 40% select, 10% update, 10% delete):
- ≥500 ops/sec sustained
- ≥1000 ops/sec burst (30 seconds)

**Read-Heavy Workload** (80% select, 20% write):
- ≥1000 ops/sec sustained

**Write-Heavy Workload** (80% insert, 20% read):
- ≥300 ops/sec sustained
- Bulk inserts improve throughput

### 15.3 Scalability

**Tables per Plugin**:
- Support 20+ tables per plugin
- No performance degradation with multiple tables

**Rows per Table**:
- 100,000+ rows with consistent performance
- Indexes required for large tables (auto-created from schema)

**Concurrent Operations**:
- 100+ concurrent requests
- Connection pooling handles load

---

## 16. Error Handling

### 16.1 Error Codes

**Client Errors (4xx-style)**:

| Code | Meaning | Example |
|------|---------|---------|
| `TABLE_NOT_FOUND` | Table not registered | "Table 'quotes' not found. Register schema first." |
| `VALIDATION_ERROR` | Data validation failed | "Missing required field: text" |
| `TYPE_MISMATCH` | Field type incorrect | "Field 'score' expects INTEGER, got STRING" |
| `IMMUTABLE_FIELD` | Attempting to update PK | "Cannot update primary key field 'id'" |
| `INVALID_FIELD` | Field not in schema | "Field 'invalid_field' not in schema" |
| `SCHEMA_CONFLICT` | Schema mismatch | "Table schema mismatch. Use migrations to alter." |
| `INVALID_FILTER` | Filter validation failed | "Filter field 'unknown' not in schema" |

**Server Errors (5xx-style)**:

| Code | Meaning | Example |
|------|---------|---------|
| `DATABASE_ERROR` | DB operation failed | "Internal database error" |
| `INTERNAL_ERROR` | Unexpected error | "Unexpected error occurred" |

### 16.2 Error Response Format

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Missing required field: text",
  "field": "text",
  "details": {}
}
```

### 16.3 Error Handling in Plugin Code

```python
try:
    response = await nats.request('db.row.my-plugin.insert', 
                                   json.dumps({...}).encode(),
                                   timeout=1.0)
    data = json.loads(response.data)
    
    if 'success' in data and not data['success']:
        # Handle error
        self.logger.error(f"Insert failed: {data['error_code']} - {data['message']}")
        if data['error_code'] == 'TABLE_NOT_FOUND':
            # Register schema first
            await self.register_schema()
        return None
    
    return data['id']

except asyncio.TimeoutError:
    self.logger.error("Insert timed out")
    return None
```

---

## 17. Observability

### 17.1 Logging

**Log Format** (Structured):

```python
self.logger.info(
    "[ROW] insert: plugin=quote-db table=quotes rows=1 latency=3ms",
    extra={
        'operation': 'row_insert',
        'plugin': 'quote-db',
        'table': 'quotes',
        'rows': 1,
        'latency_ms': 3.2
    }
)
```

**Log Levels**:

| Level | When | Example |
|-------|------|---------|
| DEBUG | Individual operations | `[ROW] insert: plugin=quote-db table=quotes rows=1` |
| INFO | Schema registration | `[ROW] schema registered: quote-db.quotes` |
| WARNING | Slow operations | `[ROW] search slow: 150ms plugin=trivia table=stats` |
| ERROR | Operation failures | `[ROW] insert failed: plugin=quote-db error=ValidationError` |

### 17.2 Metrics (Future)

**Recommended Metrics** (for Prometheus):

```
# Operation counters
rosey_row_insert_total{plugin="quote-db", table="quotes"}
rosey_row_select_total{plugin="quote-db", table="quotes"}
rosey_row_update_total{plugin="quote-db", table="quotes"}
rosey_row_delete_total{plugin="quote-db", table="quotes"}
rosey_row_search_total{plugin="quote-db", table="quotes"}

# Latency histograms
rosey_row_insert_duration_seconds{plugin="quote-db", table="quotes"}
rosey_row_search_duration_seconds{plugin="quote-db", table="quotes"}

# Error counters
rosey_row_errors_total{plugin="quote-db", error_code="VALIDATION_ERROR"}

# Storage metrics
rosey_row_table_rows_total{plugin="quote-db", table="quotes"}
rosey_row_table_size_bytes{plugin="quote-db", table="quotes"}
```

### 17.3 Debugging

**Inspect Database Tables**:

```sql
-- List all plugin tables
SELECT tablename FROM pg_tables WHERE tablename LIKE '%\_%';

-- Count rows per table
SELECT 'quote_db_quotes' as table, COUNT(*) FROM quote_db_quotes
UNION ALL
SELECT 'trivia_stats' as table, COUNT(*) FROM trivia_stats;

-- Show recent inserts
SELECT * FROM quote_db_quotes ORDER BY id DESC LIMIT 10;
```

**NATS Debugging**:

```bash
# Subscribe to all row operations
nats sub 'db.row.*.>'

# Monitor specific plugin
nats sub 'db.row.quote-db.>'

# Test insert manually
nats req 'db.row.test.insert' '{"table":"quotes","data":{"text":"test"}}'
```

---

## 18. Documentation Requirements

### 18.1 Code Documentation

**Docstrings** (Google Style):

```python
async def row_insert(
    self,
    plugin_name: str,
    table_name: str,
    data: dict | list[dict]
) -> dict:
    """
    Insert row(s) into a plugin table.
    
    This operation validates data against the registered table schema,
    performs type coercion where possible, and returns auto-generated IDs.
    
    Args:
        plugin_name: Plugin identifier (extracted from NATS subject).
        table_name: Table name without plugin prefix.
        data: Single dict or list of dicts to insert. Each dict must
             contain all required fields defined in the schema.
    
    Returns:
        Single row: {"id": 42, "created": True}
        Bulk insert: {"ids": [42, 43, 44], "created": 3}
    
    Raises:
        ValueError: If table not registered.
        ValidationError: If data doesn't match schema.
        TypeError: If data types cannot be coerced.
    
    Example:
        >>> await db.row_insert('quote-db', 'quotes', {
        ...     'text': 'Keep circulating the tapes',
        ...     'author': 'MST3K'
        ... })
        {'id': 42, 'created': True}
    """
```

### 18.2 User Documentation

**Plugin Developer Guide**: `docs/guides/PLUGIN_ROW_STORAGE.md`

**Contents**:
1. Overview - When to use row storage vs KV storage
2. Schema Registration - How to define table schemas
3. CRUD Operations - Insert, select, update, delete examples
4. Search & Filters - Querying data with filters and pagination
5. Best Practices - Schema design, indexing, error handling
6. Performance Tips - Bulk inserts, indexed searches
7. Migration Path - From KV to Row storage

**Example Snippet**:

```markdown
## Quick Start: Row Storage

### 1. Define Your Schema

```python
# In your plugin's on_ready() method
schema = {
    'table': 'quotes',
    'fields': [
        {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
        {'name': 'text', 'type': 'TEXT', 'nullable': False},
        {'name': 'author', 'type': 'VARCHAR(255)'},
        {'name': 'timestamp', 'type': 'TIMESTAMP', 'default': 'CURRENT_TIMESTAMP'}
    ],
    'indexes': [
        {'fields': ['author']},
        {'fields': ['timestamp']}
    ]
}

await self.nats.request(
    'db.schema.quote-db.register',
    json.dumps(schema).encode()
)
```

### 2. Insert Data

```python
response = await self.nats.request(
    'db.row.quote-db.insert',
    json.dumps({
        'table': 'quotes',
        'data': {
            'text': 'Keep circulating the tapes',
            'author': 'MST3K'
        }
    }).encode()
)

data = json.loads(response.data)
quote_id = data['id']  # Auto-generated ID
```

### 3. Search Data

```python
response = await self.nats.request(
    'db.row.quote-db.search',
    json.dumps({
        'table': 'quotes',
        'filters': {'author': 'MST3K'},
        'sort': {'field': 'timestamp', 'order': 'desc'},
        'limit': 10
    }).encode()
)

data = json.loads(response.data)
for quote in data['rows']:
    print(f"{quote['text']} - {quote['author']}")
```
```

### 18.3 Architecture Documentation

**Update**: `docs/ARCHITECTURE.md`

**Add Section**:

```markdown
## Plugin Storage - Row Operations (Sprint 13)

Plugins can store structured entities with typed fields via row operations:

- **Register Schema**: `db.schema.<plugin>.register` - Define table structure
- **Insert**: `db.row.<plugin>.insert` - Create rows
- **Select**: `db.row.<plugin>.select` - Retrieve by ID
- **Update**: `db.row.<plugin>.update` - Modify rows
- **Delete**: `db.row.<plugin>.delete` - Remove rows
- **Search**: `db.row.<plugin>.search` - Query with filters

**Data Flow**:

1. Plugin registers table schema (once at startup)
2. DatabaseService validates schema and creates table
3. Plugin performs CRUD operations via NATS
4. DatabaseService validates data against schema
5. BotDatabase executes SQL with plugin isolation
6. Response sent via NATS reply subject

**Storage**:
- Plugin tables: `<plugin>_<table>` (e.g., `quote_db_quotes`)
- Schema metadata: `plugin_table_schemas` table
- Auto-increment primary keys
- Indexes defined in schema

**Isolation**:
- Plugin name extracted from NATS subject
- Queries scoped to plugin's table namespace
- No cross-plugin access possible

**Future Enhancements**:
- Sprint 14: MongoDB-style operators ($inc, $gte, etc.)
- Sprint 15: Schema migrations (ALTER TABLE)
- Sprint 17: Parameterized SQL (complex queries)
```

---

## 19. Dependencies & Risks

### 19.1 Internal Dependencies

**Required** (Must be completed):
- ✅ Sprint 12: KV Storage Foundation (completed)
- ✅ Sprint 11: SQLAlchemy ORM (completed)
- ✅ Sprint 9: DatabaseService NATS handlers (completed)

**Testing Dependencies**:
- ✅ pytest-asyncio
- ✅ NATS test fixtures
- ✅ SQLite test database

### 19.2 External Dependencies

**No New Dependencies**: Sprint 13 uses existing infrastructure only.

**Python Packages** (already in requirements.txt):
- `nats-py` - NATS client
- `sqlalchemy[asyncio]` - ORM
- `aiosqlite` - Async SQLite
- `asyncpg` - Async PostgreSQL
- `alembic` - Migrations

### 19.3 Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Dynamic table creation fails** | Low | High | Test on SQLite + PostgreSQL before merge |
| **Schema validation too strict** | Medium | Medium | Allow type coercion, clear error messages |
| **Performance below targets** | Low | Medium | Performance tests in CI, indexes on common fields |
| **Plugin isolation broken** | Low | Critical | 15+ security tests verify isolation |
| **Schema conflicts on update** | Medium | Low | Clear error, migration path in Sprint 15 |
| **Type coercion edge cases** | Medium | Medium | Comprehensive type coercion tests |
| **Pagination bugs** | Low | Low | Edge case tests (empty results, single page, etc.) |

### 19.4 Rollback Plan

**If Sprint 13 Fails**:

1. **Revert Migration**:
   ```bash
   alembic downgrade -1
   ```

2. **Remove Code**:
   - Revert commits 1-5
   - DatabaseService unchanged (no new subscriptions active)

3. **No Data Loss**:
   - `plugin_table_schemas` table dropped cleanly
   - Plugin tables dropped (no production data yet)
   - KV storage (Sprint 12) unaffected

**Rollback Tested**: Alembic downgrade tested in Sortie 1 acceptance criteria.

---

## 20. Sprint Acceptance Criteria

### 20.1 Functional Acceptance

**Schema Registration**:
- [ ] ✅ Register valid schema succeeds
- [ ] ✅ Duplicate registration (same schema) succeeds
- [ ] ✅ Schema conflict (different schema) returns error
- [ ] ✅ Invalid type rejected
- [ ] ✅ Table created in database

**Insert Operation**:
- [ ] ✅ Single insert returns ID
- [ ] ✅ Bulk insert returns array of IDs
- [ ] ✅ Missing required field returns error
- [ ] ✅ Type validation enforced
- [ ] ✅ Default values applied

**Select Operation**:
- [ ] ✅ Select existing row returns data
- [ ] ✅ Select non-existent row returns exists=false
- [ ] ✅ Select by ID <5ms p95

**Update Operation**:
- [ ] ✅ Partial update modifies only specified fields
- [ ] ✅ Update non-existent row returns updated=false
- [ ] ✅ Cannot update primary key

**Delete Operation**:
- [ ] ✅ Delete existing row succeeds
- [ ] ✅ Delete non-existent row is idempotent

**Search Operation**:
- [ ] ✅ Search with single filter works
- [ ] ✅ Search with multiple filters (AND) works
- [ ] ✅ Sorting works (ASC/DESC)
- [ ] ✅ Pagination works (limit + offset)
- [ ] ✅ Empty search returns empty array

**Plugin Isolation**:
- [ ] ✅ Plugin A cannot access Plugin B's tables
- [ ] ✅ Plugin name extracted from subject
- [ ] ✅ Table name injection blocked

### 20.2 Non-Functional Acceptance

**Performance**:
- [ ] ✅ Insert <10ms p95
- [ ] ✅ Select by ID <5ms p95
- [ ] ✅ Search <20ms p95
- [ ] ✅ Throughput ≥500 ops/sec (mixed workload)
- [ ] ✅ Bulk insert 100 rows <100ms

**Testing**:
- [ ] ✅ Test coverage ≥85%
- [ ] ✅ 95+ unit tests (all passing)
- [ ] ✅ 40+ integration tests (all passing)
- [ ] ✅ 5+ performance tests (all passing)
- [ ] ✅ 15+ security tests (all passing)

**Code Quality**:
- [ ] ✅ All docstrings complete
- [ ] ✅ Type hints present
- [ ] ✅ No lint errors
- [ ] ✅ Code review approved

**Documentation**:
- [ ] ✅ Plugin Developer Guide complete
- [ ] ✅ Architecture docs updated
- [ ] ✅ API reference complete
- [ ] ✅ Migration guide (KV → Row)

**Database**:
- [ ] ✅ Alembic migration applies cleanly
- [ ] ✅ Alembic migration reverses cleanly
- [ ] ✅ Works on SQLite and PostgreSQL
- [ ] ✅ No breaking changes to Sprint 12 (KV)

### 20.3 Sprint Completion Checklist

**Code**:
- [ ] All 5 sorties merged to main
- [ ] No failing tests in CI
- [ ] No open blockers
- [ ] Code reviewed

**Deployment**:
- [ ] Migration tested on staging
- [ ] Performance verified
- [ ] Rollback tested

**Documentation**:
- [ ] User docs complete
- [ ] Developer docs complete
- [ ] Changelog updated

**Validation**:
- [ ] Manual testing (all user stories)
- [ ] Smoke test passes
- [ ] No regressions

**Sign-Off**:
- [ ] Product Owner approval
- [ ] Tech Lead approval
- [ ] QA approval

---

## 21. Future Enhancements (Out of Scope)

### 21.1 Deferred to Sprint 14 (Advanced Queries)

**MongoDB-Style Operators**:
- Filter operators: `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$like`
- Update operators: `$inc`, `$dec`, `$max`, `$min`, `$push` (arrays)
- Compound filters with AND/OR logic
- Multi-field sorting

### 21.2 Deferred to Sprint 15 (Migrations)

**Schema Evolution**:
- ALTER TABLE support (add/drop/modify columns)
- Migration versioning (001_create_table, 002_add_column)
- Rollback support (up/down migrations)
- Migration dependency tracking

### 21.3 Deferred to Sprint 17 (Advanced SQL)

**Complex Queries**:
- Joins across tables
- Aggregations (COUNT, SUM, AVG, GROUP BY)
- Subqueries
- Raw SQL with parameterization

### 21.4 V2 Features (Someday)

**Advanced Features**:
- Transactions (multi-row atomic updates)
- Foreign keys and relations
- Full-text search
- Geospatial queries
- Time-series optimizations
- Materialized views

---

## 22. Appendices

### 22.1 Glossary

**Terms**:
- **Row**: A single record/entity in a table (e.g., one quote)
- **Schema**: Table structure definition (fields, types, indexes)
- **CRUD**: Create, Read, Update, Delete operations
- **Primary Key**: Unique identifier for row (usually auto-increment ID)
- **Filter**: Equality condition for search queries
- **Pagination**: Splitting results into pages (limit + offset)
- **Isolation**: Plugin A cannot access Plugin B's data
- **Type Coercion**: Converting value to expected type (string → datetime)
- **Idempotent**: Operation can be repeated without changing result

### 22.2 References

**Internal Documents**:
- Sprint 12: KV Storage Foundation
- Sprint 11: SQLAlchemy Migration
- Sprint 9: DatabaseService NATS Integration
- Plugin Manager: `bot/rosey/core/plugin_manager.py`

**External Resources**:
- SQLAlchemy Core: https://docs.sqlalchemy.org/en/14/core/
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html
- Alembic Migrations: https://alembic.sqlalchemy.org/
- MongoDB Query Operators: https://docs.mongodb.com/manual/reference/operator/query/

### 22.3 Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-22 | GitHub Copilot | Initial PRD creation |

### 22.4 Contact

**Sprint Owner**: Rosey-Robot Team  
**Slack Channel**: #rosey-storage-sprint  
**GitHub Issues**: Tag with `sprint-xxx-b`, `storage`, `row-operations`

---

**End of PRD: Row Operations Foundation (Sprint 13)**

**Document Stats**:
- **Words**: ~12,000
- **Sections**: 22
- **User Stories**: 10
- **Commits**: 5
- **Estimated Duration**: 4-5 days
- **Test Coverage Target**: ≥85%

**Next Steps**:
1. Review and approve this PRD
2. Create Sprint 13 branch
3. Begin Sortie 1: Schema Registry & Table Creation
4. Follow implementation plan (Section 12)

**Related PRDs**:
- ✅ Sprint 12: KV Storage Foundation (completed)
- ⏳ Sprint 14: Advanced Query Operators (next)
- ⏳ Sprint 15: Schema Migrations
- ⏳ Sprint 16: Reference Implementation
- ⏳ Sprint 17: Parameterized SQL

---

*This document is a living document and will be updated as implementation progresses. All changes require Tech Lead approval.*

