# SPEC-Sortie-4: Documentation & Examples

**Sprint**: 15 - Schema Migrations  
**Sortie**: 4 of 4  
**Estimated Duration**: 0.5 days  
**Status**: Draft  
**Author**: Agent via PRD-Schema-Migrations.md  
**Created**: November 24, 2025  

---

## 1. Overview

This sortie completes Sprint 15 by documenting the schema migration system for plugin developers and updating project architecture documentation. We create comprehensive guides on writing migrations, provide 5-10 example migration patterns, document NATS message formats, and establish best practices for safe schema evolution. This sortie focuses purely on documentation - no code changes.

**What This Sortie Achieves**:
- Plugin developer migration guide
- 5-10 example migration files covering common patterns
- Updated ARCHITECTURE.md with migration system overview
- Migration best practices guide
- NATS message format reference
- SQLite workaround cookbook

**Documentation Deliverables**:
- `docs/guides/PLUGIN_MIGRATIONS.md` - Complete migration guide
- `docs/guides/MIGRATION_BEST_PRACTICES.md` - Best practices and patterns
- `examples/migrations/` - Example migration files
- Updated `docs/ARCHITECTURE.md` - System overview
- Updated `docs/NATS_MESSAGES.md` - Migration message formats

---

## 2. Scope and Non-Goals

### In Scope

- **Plugin Migration Guide**: How to write, apply, and rollback migrations
- **Example Migrations**: 5-10 common patterns (CREATE TABLE, ADD COLUMN, etc.)
- **Best Practices**: Idempotency, rollback safety, testing, SQLite limitations
- **Architecture Documentation**: Migration system overview and data flow
- **NATS Message Format**: Request/response schemas for all handlers
- **SQLite Workarounds**: Table recreation patterns for unsupported operations

### Out of Scope (Future Work)

- **Code changes**: All code complete in Sorties 1-3
- **Additional features**: Auto-migration, schema validation
- **UI/Dashboard**: Web interface for migration management
- **CLI tools**: Command-line migration utilities (use NATS for now)

---

## 3. Requirements

### Functional Requirements

**FR-1: Plugin Migration Guide**
- Explain migration file format (NNN_description.sql)
- Document UP and DOWN sections
- Show how to place files in plugin/migrations/ directory
- Explain version numbering (001, 002, etc.)
- Document NATS commands for apply/rollback/status

**FR-2: Example Migrations**
- CREATE TABLE with indexes
- ADD COLUMN with default value
- DROP COLUMN (SQLite workaround)
- CREATE INDEX on existing table
- ALTER TABLE ADD CONSTRAINT
- Data migration (UPDATE statements in UP)
- Multiple tables in one migration
- Complex table recreation for SQLite
- Rollback examples for each pattern

**FR-3: Best Practices Documentation**
- Write idempotent migrations (IF NOT EXISTS)
- Test migrations on staging before production
- Never modify applied migrations
- Keep migrations small and focused
- Write reversible DOWN SQL
- Document migration intent in comments
- Handle SQLite limitations correctly
- Backup data before destructive operations

**FR-4: Architecture Documentation**
- Add migration system section to ARCHITECTURE.md
- Document data flow: NATS → DatabaseService → MigrationExecutor → Database
- Diagram migration states (pending, applied, rolled_back, failed)
- Explain locking mechanism
- Show integration with plugin system

**FR-5: NATS Message Format Reference**
- Document db.migrate.<plugin>.apply request/response
- Document db.migrate.<plugin>.rollback request/response
- Document db.migrate.<plugin>.status request/response
- Include JSON schemas
- Document error codes

**FR-6: SQLite Workaround Cookbook**
- Table recreation pattern for DROP COLUMN
- Table recreation pattern for ALTER COLUMN
- Constraint addition via CREATE TABLE
- Examples with step-by-step SQL

### Non-Functional Requirements

**NFR-1: Clarity**
- Documentation clear and unambiguous
- Examples executable without modification
- Step-by-step instructions for common tasks

**NFR-2: Completeness**
- Cover all major use cases
- Address common pitfalls and errors
- Link related documentation

**NFR-3: Maintainability**
- Easy to update as system evolves
- Examples reflect actual code patterns
- Version-controlled with code

---

## 4. Technical Design

### 4.1 Plugin Migration Guide Structure

**File**: `docs/guides/PLUGIN_MIGRATIONS.md`

```markdown
# Plugin Migration Guide

## Overview
Database schema migrations allow plugins to evolve their schema over time...

## Migration File Format
Migrations are SQL files in `plugin-name/migrations/` directory.

### Naming Convention
- Format: `NNN_description.sql`
- NNN: Zero-padded version (001, 002, ...)
- description: Lowercase with underscores

### File Structure
```sql
-- UP
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quotes_author ON quotes(author);

-- DOWN
DROP INDEX idx_quotes_author;
DROP TABLE quotes;
```

## Writing Migrations

### Best Practices
- One logical change per migration
- Include both UP and DOWN sections
- Test on staging database first
- Write idempotent migrations when possible

### Creating Your First Migration
1. Create `migrations/` directory in your plugin
2. Create `001_initial_schema.sql`
3. Write UP SQL (schema changes)
4. Write DOWN SQL (rollback)
5. Apply migration via NATS

## Applying Migrations

### Via NATS Message
```python
import nats
import json

nc = await nats.connect("nats://localhost:4222")

# Apply all pending migrations
response = await nc.request(
    "db.migrate.quote-db.apply",
    json.dumps({"target_version": "latest"}).encode()
)

result = json.loads(response.data)
print(result)
```

### Dry Run
```python
# Preview without committing
response = await nc.request(
    "db.migrate.quote-db.apply",
    json.dumps({"target_version": "latest", "dry_run": True}).encode()
)
```

## Rolling Back Migrations

```python
# Rollback to version 2
response = await nc.request(
    "db.migrate.quote-db.rollback",
    json.dumps({"target_version": 2}).encode()
)
```

## Checking Migration Status

```python
response = await nc.request(
    "db.migrate.quote-db.status",
    json.dumps({}).encode()
)

status = json.loads(response.data)
print(f"Current version: {status['current_version']}")
print(f"Pending: {status['pending_count']}")
```

## SQLite Limitations

SQLite does not support:
- DROP COLUMN directly
- ALTER COLUMN directly
- ADD CONSTRAINT directly

See [SQLite Workarounds](#sqlite-workarounds) for solutions.

## Common Patterns

See [examples/migrations/](../../examples/migrations/) for complete examples.
```

### 4.2 Example Migration Files

**Directory**: `examples/migrations/`

Create these example files:

1. **001_create_table.sql** - Basic table creation
2. **002_add_column.sql** - Add column with default
3. **003_drop_column_sqlite.sql** - Table recreation for DROP COLUMN
4. **004_create_index.sql** - Add index to existing table
5. **005_alter_column_sqlite.sql** - Table recreation for ALTER COLUMN
6. **006_add_foreign_key.sql** - Add constraint
7. **007_data_migration.sql** - Update existing data
8. **008_multiple_tables.sql** - Create related tables
9. **009_complex_transformation.sql** - Multi-step schema change
10. **010_drop_table.sql** - Remove deprecated table

### 4.3 Best Practices Guide Structure

**File**: `docs/guides/MIGRATION_BEST_PRACTICES.md`

```markdown
# Migration Best Practices

## Golden Rules

### 1. Never Modify Applied Migrations
Once applied to production, treat migration files as immutable.
Checksum verification will detect changes.

### 2. Write Idempotent Migrations
Use IF NOT EXISTS, IF EXISTS to allow re-running.

### 3. Keep Migrations Small
One logical change per migration.
Easier to rollback, debug, and review.

### 4. Test on Staging First
Always test on staging database before production.

### 5. Write Reversible DOWN SQL
Every UP should have matching DOWN.
If not reversible, document why.

## Idempotency Patterns

### CREATE TABLE
```sql
-- Good
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY);

-- Bad
CREATE TABLE users (id INTEGER PRIMARY KEY);  -- Fails if exists
```

### ADD COLUMN
```sql
-- SQLite doesn't have IF NOT EXISTS for columns
-- Use table recreation or check in application code
```

## Rollback Safety

### Safe Rollbacks
- DROP TABLE (if data acceptable loss)
- DROP INDEX
- Remove column (via recreation)

### Dangerous Rollbacks
- Cannot restore deleted data
- Document data loss in comments
- Consider backup/restore instead

## Testing Migrations

### Unit Test Pattern
```python
async def test_migration_001_creates_table():
    # Apply migration
    await apply_migration("plugin", version=1)
    
    # Verify schema
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    assert 'quotes' in [t['name'] for t in tables]
    
    # Test rollback
    await rollback_migration("plugin", version=0)
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    assert 'quotes' not in [t['name'] for t in tables]
```

## SQLite Limitations

### DROP COLUMN Workaround
```sql
-- UP
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL
    -- Omit author column
);

INSERT INTO quotes_new (id, text)
SELECT id, text FROM quotes;

DROP TABLE quotes;

ALTER TABLE quotes_new RENAME TO quotes;

-- DOWN
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    author TEXT  -- Re-add author column
);

INSERT INTO quotes_new (id, text, author)
SELECT id, text, NULL FROM quotes;

DROP TABLE quotes;

ALTER TABLE quotes_new RENAME TO quotes;
```

## Data Migrations

When migrating data, consider:
- Performance (batch updates for large tables)
- Transactions (all-or-nothing)
- Default values for new columns
- Data validation

## Error Handling

Handle migration failures gracefully:
- Transactions auto-rollback
- Investigate failure before retrying
- Check validation warnings
- Verify checksums

## Deployment Workflow

1. Develop migration on feature branch
2. Test on local SQLite database
3. Create PR with migration file
4. Code review (check UP/DOWN SQL)
5. Merge to main
6. Deploy code to staging
7. Apply migration on staging database
8. Verify schema and functionality
9. Deploy to production
10. Apply migration on production database
11. Monitor for errors
```

### 4.4 Architecture Documentation Update

**File**: `docs/ARCHITECTURE.md` (add new section)

```markdown
## Schema Migrations

### Overview
The migration system allows plugins to evolve their database schema over time through versioned SQL files. Each migration has UP (apply) and DOWN (rollback) sections.

### Components

#### MigrationManager
- Discovers migration files in `plugin/migrations/` directory
- Parses files to extract UP/DOWN SQL
- Computes SHA-256 checksums for tamper detection
- Calculates pending and rollback migrations

#### MigrationExecutor
- Executes migrations within database transactions
- Records results in `plugin_schema_migrations` table
- Supports dry-run mode for safe preview
- Automatic rollback on failure

#### MigrationValidator
- Validates migrations before execution
- Detects destructive operations (DROP TABLE, etc.)
- Checks SQLite limitations
- Verifies checksums on status checks

#### DatabaseService NATS Handlers
- `db.migrate.<plugin>.apply` - Apply pending migrations
- `db.migrate.<plugin>.rollback` - Rollback applied migrations
- `db.migrate.<plugin>.status` - Query migration state
- Per-plugin locking prevents concurrent runs

### Data Flow

```
NATS Client
  |
  | db.migrate.plugin.apply
  v
DatabaseService.handle_migrate_apply()
  |
  +--> MigrationManager.discover_migrations()
  |      |
  |      +--> Scan plugin/migrations/ directory
  |      +--> Parse NNN_description.sql files
  |      +--> Extract UP/DOWN sections
  |      +--> Compute checksums
  |
  +--> MigrationValidator.validate_migration()
  |      |
  |      +--> Check destructive operations
  |      +--> Check SQLite limitations
  |      +--> Check syntax
  |
  +--> MigrationExecutor.apply_migration()
         |
         +--> BEGIN TRANSACTION
         +--> Execute UP SQL
         +--> Record in plugin_schema_migrations
         +--> COMMIT or ROLLBACK
```

### Database Schema

```sql
CREATE TABLE plugin_schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL,
    applied_by TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'applied', 'rolled_back', 'failed'
    error_message TEXT,
    execution_time_ms INTEGER,
    UNIQUE(plugin_name, version)
);
```

### Migration States

- **Pending**: File exists, not applied (version > current)
- **Applied**: Recorded in database with status='applied'
- **Rolled Back**: Previously applied, now reverted (status='rolled_back')
- **Failed**: Execution error (status='failed', error_message populated)
```

### 4.5 NATS Message Format Reference

**File**: `docs/NATS_MESSAGES.md` (add new section)

```markdown
## Migration Messages

### db.migrate.<plugin>.apply

Apply pending migrations to target version.

**Request**:
```json
{
  "target_version": 3,      // or "latest"
  "dry_run": false          // optional, default false
}
```

**Success Response**:
```json
{
  "success": true,
  "dry_run": false,
  "applied_migrations": [
    {
      "success": true,
      "version": 1,
      "name": "create_table",
      "execution_time_ms": 45,
      "applied_at": "2025-11-24T10:30:00Z",
      "applied_by": "system"
    }
  ],
  "warnings": [
    {
      "level": "WARNING",
      "message": "Migration drops table (all data will be deleted)",
      "migration_version": 2,
      "migration_name": "drop_old_table",
      "category": "destructive"
    }
  ]
}
```

**Error Response**:
```json
{
  "success": false,
  "error_code": "VALIDATION_FAILED",
  "message": "Migration validation failed",
  "errors": [
    {
      "level": "ERROR",
      "message": "SQLite does not support DROP COLUMN directly",
      "migration_version": 3,
      "migration_name": "drop_column",
      "category": "sqlite"
    }
  ]
}
```

**Error Codes**:
- `MIGRATION_IN_PROGRESS` - Another migration running for this plugin
- `VALIDATION_FAILED` - Migration has ERROR warnings
- `MIGRATION_FAILED` - SQL execution error
- `INTERNAL_ERROR` - Unexpected error

### db.migrate.<plugin>.rollback

Rollback applied migrations to target version.

**Request**:
```json
{
  "target_version": 0    // 0 = rollback all
}
```

**Success Response**:
```json
{
  "success": true,
  "rolled_back_migrations": [
    {
      "success": true,
      "version": 3,
      "name": "add_index",
      "execution_time_ms": 12,
      "applied_at": "2025-11-24T10:35:00Z",
      "applied_by": "system"
    }
  ]
}
```

### db.migrate.<plugin>.status

Query migration status for plugin.

**Request**:
```json
{}
```

**Success Response**:
```json
{
  "success": true,
  "plugin_name": "quote-db",
  "current_version": 3,
  "pending_count": 2,
  "applied_migrations": [
    {
      "version": 1,
      "name": "create_table",
      "checksum": "abc123...",
      "applied_at": "2025-11-24T10:30:00Z",
      "applied_by": "system",
      "execution_time_ms": 45
    }
  ],
  "pending_migrations": [
    {
      "version": 4,
      "name": "add_column"
    }
  ],
  "available_migrations": [
    {"version": 1, "name": "create_table"},
    {"version": 2, "name": "add_index"},
    {"version": 3, "name": "alter_table"},
    {"version": 4, "name": "add_column"},
    {"version": 5, "name": "data_migration"}
  ],
  "checksum_warnings": [],
  "pending_warnings": [
    {
      "level": "WARNING",
      "message": "Migration drops column (potential data loss)",
      "migration_version": 4,
      "migration_name": "add_column",
      "category": "destructive"
    }
  ]
}
```
```

---

## 5. Implementation Steps

1. **Create Plugin Migration Guide**
   - Create `docs/guides/PLUGIN_MIGRATIONS.md`
   - Write overview and file format section
   - Document naming convention and structure
   - Add applying/rolling back/status examples
   - Document SQLite limitations
   - Link to example files

2. **Create Example Migration Files**
   - Create `examples/migrations/` directory
   - Write 001_create_table.sql (basic CREATE TABLE)
   - Write 002_add_column.sql (ALTER TABLE ADD COLUMN)
   - Write 003_drop_column_sqlite.sql (table recreation)
   - Write 004_create_index.sql (CREATE INDEX)
   - Write 005_alter_column_sqlite.sql (table recreation)
   - Write 006_add_foreign_key.sql (ADD CONSTRAINT)
   - Write 007_data_migration.sql (UPDATE statements)
   - Write 008_multiple_tables.sql (multiple CREATE TABLEs)
   - Write 009_complex_transformation.sql (multi-step)
   - Write 010_drop_table.sql (DROP TABLE)

3. **Create Best Practices Guide**
   - Create `docs/guides/MIGRATION_BEST_PRACTICES.md`
   - Document golden rules (never modify applied, idempotent, etc.)
   - Provide idempotency patterns
   - Document rollback safety considerations
   - Add testing migration examples
   - Document SQLite workarounds with complete SQL
   - Add deployment workflow section

4. **Update Architecture Documentation**
   - Open `docs/ARCHITECTURE.md`
   - Add "Schema Migrations" section
   - Document components (Manager, Executor, Validator, Handlers)
   - Add data flow diagram (ASCII or Mermaid)
   - Document migration states
   - Show plugin_schema_migrations table schema

5. **Update NATS Message Documentation**
   - Open `docs/NATS_MESSAGES.md`
   - Add "Migration Messages" section
   - Document db.migrate.<plugin>.apply format
   - Document db.migrate.<plugin>.rollback format
   - Document db.migrate.<plugin>.status format
   - Include JSON schemas for request/response
   - Document all error codes

6. **Add SQLite Workaround Cookbook** (optional separate file)
   - Create `docs/guides/SQLITE_MIGRATION_WORKAROUNDS.md`
   - Document DROP COLUMN pattern
   - Document ALTER COLUMN pattern
   - Document ADD CONSTRAINT pattern
   - Provide step-by-step SQL examples

7. **Review and Cross-Link**
   - Ensure all docs link to each other
   - Add references from README.md
   - Update ARCHITECTURE.md table of contents
   - Link examples from guides

8. **Create README for Examples**
   - Create `examples/migrations/README.md`
   - Explain purpose of examples
   - List all example files with descriptions
   - Link to full migration guide

---

## 6. Testing Strategy

No automated tests for documentation, but manual review checklist:

### 6.1 Documentation Review Checklist

**Plugin Migration Guide**:
- [ ] File format clearly explained
- [ ] Naming convention documented
- [ ] UP/DOWN structure shown with example
- [ ] NATS commands executable
- [ ] Error handling covered
- [ ] SQLite limitations mentioned

**Example Migrations**:
- [ ] All 10 example files created
- [ ] Each example has UP and DOWN
- [ ] Examples cover common patterns
- [ ] SQLite workarounds demonstrated
- [ ] Comments explain each step

**Best Practices Guide**:
- [ ] Golden rules clearly stated
- [ ] Idempotency patterns demonstrated
- [ ] Rollback safety explained
- [ ] Testing examples provided
- [ ] Deployment workflow documented

**Architecture Documentation**:
- [ ] Migration system overview clear
- [ ] Components documented
- [ ] Data flow diagram included
- [ ] Database schema shown
- [ ] Migration states explained

**NATS Message Documentation**:
- [ ] All three message types documented
- [ ] JSON schemas complete
- [ ] Error codes listed
- [ ] Examples match actual responses

### 6.2 Validation Against Implementation

- [ ] Example migrations match file format in MigrationManager
- [ ] NATS message formats match handler code
- [ ] Error codes match actual handler responses
- [ ] Database schema matches Alembic migration
- [ ] Validation warnings match MigrationValidator output

---

## 7. Acceptance Criteria

- [ ] **AC-1**: Plugin Migration Guide is complete and clear
  - Given a new plugin developer
  - When reading PLUGIN_MIGRATIONS.md
  - Then can create and apply first migration without additional help

- [ ] **AC-2**: 10 example migration files created
  - Given examples/migrations/ directory
  - When listing files
  - Then 10 migration files exist (001-010)

- [ ] **AC-3**: Each example has UP and DOWN sections
  - Given each example migration file
  - When parsing file
  - Then both -- UP and -- DOWN markers present with valid SQL

- [ ] **AC-4**: Best Practices Guide covers key topics
  - Given MIGRATION_BEST_PRACTICES.md
  - When reviewing content
  - Then covers idempotency, rollback safety, testing, SQLite workarounds

- [ ] **AC-5**: Architecture documentation updated
  - Given docs/ARCHITECTURE.md
  - When searching for "Schema Migrations"
  - Then section exists with components, data flow, and schema

- [ ] **AC-6**: NATS message formats documented
  - Given docs/NATS_MESSAGES.md
  - When searching for migration messages
  - Then all three message types documented with schemas

- [ ] **AC-7**: Documentation is cross-linked
  - Given any migration document
  - When reading
  - Then links to related documents work and are relevant

- [ ] **AC-8**: SQLite workarounds clearly explained
  - Given developer needing to DROP COLUMN on SQLite
  - When reading documentation
  - Then finds complete table recreation pattern with example

- [ ] **AC-9**: Examples match implementation
  - Given example migration file format
  - When comparing to MigrationManager code
  - Then format matches expected pattern

- [ ] **AC-10**: Error codes documented
  - Given all error codes in handlers
  - When checking NATS_MESSAGES.md
  - Then all codes listed with descriptions

---

## 8. Rollout Plan

### Pre-deployment

1. Ensure Sorties 1-3 complete and merged
2. Review all documentation drafts
3. Validate examples against actual implementation
4. Test NATS commands from documentation

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-15-sortie-4-documentation`
2. Create `docs/guides/PLUGIN_MIGRATIONS.md` with complete guide
3. Create `docs/guides/MIGRATION_BEST_PRACTICES.md` with best practices
4. Create `examples/migrations/` directory
5. Write all 10 example migration files (001-010)
6. Create `examples/migrations/README.md` explaining examples
7. Update `docs/ARCHITECTURE.md` with Schema Migrations section
8. Update `docs/NATS_MESSAGES.md` with migration message formats
9. (Optional) Create `docs/guides/SQLITE_MIGRATION_WORKAROUNDS.md`
10. Add cross-links between all documents
11. Update main `README.md` to reference migration guides
12. Commit changes with message:
    ```
    Sprint 15 Sortie 4: Documentation & Examples
    
    - Add comprehensive plugin migration guide
    - Create 10 example migration files covering common patterns
    - Document migration best practices (idempotency, rollback, testing)
    - Update architecture docs with migration system overview
    - Document NATS migration message formats
    - Add SQLite workaround patterns
    - Cross-link all migration documentation
    
    Implements: SPEC-Sortie-4-Documentation-Examples.md
    Related: PRD-Schema-Migrations.md
    Completes: Sprint 15 - Schema Migrations
    ```
13. Push branch and create PR
14. Documentation review
15. Merge to main

### Post-deployment

- Share migration guide link with plugin developers
- Announce new migration system in team chat
- Update onboarding docs to reference migration guide

### Rollback Procedure

Documentation-only changes, no rollback needed. If issues:
```bash
# Revert documentation commits
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sorties 1-3**: Code must be complete to validate documentation
- **Actual implementation**: Examples must match real behavior

### External Dependencies

None

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Documentation out of sync with code | Medium | Medium | Review against actual code, include version numbers |
| Examples don't work as written | Low | Medium | Test all example commands before publishing |
| SQLite workarounds incomplete | Low | Medium | Test table recreation pattern on actual SQLite database |
| Users skip reading docs | High | Low | Make docs easy to find, link from error messages |
| Documentation becomes stale | Medium | Medium | Schedule quarterly review, update with code changes |

---

## 10. Documentation

This sortie IS documentation, but we need to maintain:

### Documentation Maintenance

- Review quarterly for accuracy
- Update when code changes
- Add new examples as patterns emerge
- Track user questions to identify gaps

### Future Documentation

- Video tutorial for creating migrations (future)
- Interactive migration playground (future)
- Migration troubleshooting guide (future)

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-Migration-Manager-Foundation.md](SPEC-Sortie-1-Migration-Manager-Foundation.md)
- [SPEC-Sortie-2-NATS-Handlers-Execution.md](SPEC-Sortie-2-NATS-Handlers-Execution.md)
- [SPEC-Sortie-3-Safety-Features-Validation.md](SPEC-Sortie-3-Safety-Features-Validation.md)

**Next**: None - completes Sprint 15

**Parent PRD**: [PRD-Schema-Migrations.md](PRD-Schema-Migrations.md)

**Related Sprints**:
- Sprint 13: Row Operations Foundation
- Sprint 16: Data Migrations (builds on Sprint 15)

**Related Documentation**:
- docs/guides/PLUGIN_MIGRATIONS.md (created by this sortie)
- docs/guides/MIGRATION_BEST_PRACTICES.md (created by this sortie)
- docs/ARCHITECTURE.md (updated by this sortie)
- docs/NATS_MESSAGES.md (updated by this sortie)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation  
**Sprint 15 Completion**: This sortie completes all deliverables for Sprint 15 Schema Migrations
