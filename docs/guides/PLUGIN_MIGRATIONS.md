# Plugin Migration Guide

**Sprint**: 15 - Schema Migrations  
**Version**: 1.0  
**Last Updated**: November 24, 2025

---

## Overview

Database schema migrations allow plugins to evolve their database schema over time in a controlled, versioned manner. Each migration consists of SQL statements that modify the schema (UP direction) and statements that reverse those changes (DOWN direction for rollback).

The migration system:
- Tracks which migrations have been applied
- Prevents concurrent migrations per plugin
- Validates migrations for safety
- Detects destructive operations
- Checks for SQLite limitations
- Maintains checksums for tamper detection

---

## Quick Start

### 1. Create Migrations Directory

In your plugin directory, create a `migrations/` subdirectory:

```
plugins/
  your-plugin/
    __init__.py
    plugin.py
    migrations/          # Create this
      001_initial_schema.sql
      002_add_index.sql
```

### 2. Create Your First Migration

Create `001_initial_schema.sql`:

```sql
-- UP
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at);

-- DOWN
DROP INDEX IF EXISTS idx_quotes_added_at;
DROP INDEX IF EXISTS idx_quotes_author;
DROP TABLE IF EXISTS quotes;
```

### 3. Apply the Migration

Using Python with NATS:

```python
import nats
import json

# Connect to NATS
nc = await nats.connect("nats://localhost:4222")

# Apply migration
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({}).encode(),
    timeout=30.0
)

result = json.loads(response.data)
if result['success']:
    print(f"Applied {len(result['applied'])} migrations")
    print(f"Current version: {result['current_version']}")
else:
    print(f"Error: {result['error']}")
```

---

## Migration File Format

### Naming Convention

Migration files must follow this strict naming pattern:

**Format**: `NNN_description.sql`

- **NNN**: Zero-padded 3-digit version number (001, 002, 003, ...)
- **description**: Lowercase words separated by underscores
- **Extension**: Must be `.sql`

**Examples**:
- ✅ `001_create_quotes_table.sql`
- ✅ `002_add_author_index.sql`
- ✅ `015_migrate_legacy_data.sql`
- ❌ `1_create_table.sql` (not zero-padded)
- ❌ `001_CreateTable.sql` (uppercase in description)
- ❌ `001-create-table.sql` (hyphens instead of underscores)

### File Structure

Each migration file has two required sections marked by special comments:

```sql
-- UP
<SQL statements to apply the migration>

-- DOWN
<SQL statements to reverse the migration>
```

**Important Rules**:
1. Both `-- UP` and `-- DOWN` markers are **required**
2. Markers are case-insensitive (`-- up` and `-- down` also work)
3. UP section must come before DOWN section
4. DOWN SQL should completely reverse UP changes
5. Use semicolons to separate statements
6. Comments are preserved and encouraged

**Example with Comments**:

```sql
-- UP
-- Create main quotes table for storing user-submitted quotes
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,           -- Quote content
    author TEXT,                  -- Optional attribution
    added_by TEXT NOT NULL,       -- Username who added it
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for author lookups
CREATE INDEX idx_quotes_author ON quotes(author);

-- DOWN
-- Remove all quote-related structures
DROP INDEX idx_quotes_author;
DROP TABLE quotes;
```

---

## Writing Good Migrations

### Principles

**1. One Logical Change Per Migration**

Keep migrations focused on a single conceptual change:

✅ **Good**: `001_create_quotes_table.sql` creates one table  
✅ **Good**: `002_add_author_index.sql` adds one index  
❌ **Bad**: `001_setup_everything.sql` creates 10 tables and 20 indexes

**2. Write Idempotent UP SQL When Possible**

Use `IF NOT EXISTS` clauses so migrations can be safely re-run:

```sql
-- UP
CREATE TABLE IF NOT EXISTS quotes (...);
CREATE INDEX IF NOT EXISTS idx_quotes_author ON quotes(author);
```

**3. Write Reversible DOWN SQL**

Every UP action should have a matching DOWN action:

```sql
-- UP
CREATE TABLE quotes (...);
CREATE INDEX idx_author ON quotes(author);

-- DOWN
DROP INDEX idx_author;
DROP TABLE quotes;
```

**4. Test on Staging First**

Always test migrations on a staging database before production:

```python
# Dry-run mode - preview without committing
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({"dry_run": True}).encode()
)
```

### Common Patterns

#### Creating a Table

```sql
-- UP
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- DOWN
DROP INDEX IF EXISTS idx_users_username;
DROP TABLE IF EXISTS users;
```

#### Adding a Column

```sql
-- UP
-- Add email column with default value
ALTER TABLE users ADD COLUMN email TEXT DEFAULT '';

-- DOWN
-- SQLite limitation: Cannot DROP COLUMN directly
-- See SQLite Workarounds section below
```

#### Adding an Index

```sql
-- UP
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- DOWN
DROP INDEX IF EXISTS idx_users_email;
```

#### Data Migration

```sql
-- UP
-- Migrate old format to new format
UPDATE quotes 
SET author = 'Unknown' 
WHERE author IS NULL OR author = '';

-- DOWN
-- Cannot reverse data changes - leave as is
-- Alternative: backup data before migration
```

---

## Applying Migrations

### Check Current Status

Before applying migrations, check what's pending:

```python
response = await nc.request(
    "rosey.db.migrate.your-plugin.status",
    json.dumps({}).encode()
)

status = json.loads(response.data)
print(f"Current version: {status['current_version']}")
print(f"Pending migrations: {len(status['pending_migrations'])}")

for pending in status['pending_migrations']:
    print(f"  - v{pending['version']:03d}: {pending['name']}")
```

### Apply All Pending Migrations

```python
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({}).encode(),
    timeout=30.0
)

result = json.loads(response.data)
if result['success']:
    print("Migrations applied successfully!")
    for migration in result['applied']:
        print(f"  ✓ v{migration['version']:03d}: {migration['name']} "
              f"({migration['execution_time_ms']}ms)")
else:
    print(f"Migration failed: {result['error']['message']}")
```

### Apply to Specific Version

```python
# Apply migrations up to version 3
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({"version": 3}).encode()
)
```

### Dry-Run Mode (Preview)

Test migrations without committing changes:

```python
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({"dry_run": True}).encode()
)

result = json.loads(response.data)
if result['success']:
    print("Dry-run successful - would apply:")
    for migration in result['applied']:
        print(f"  - v{migration['version']:03d}: {migration['name']}")
```

### Handling Warnings

The validator may return warnings for destructive operations:

```python
result = json.loads(response.data)
if result['success'] and 'warnings' in result:
    print("⚠️  Warnings:")
    for warning in result['warnings']:
        print(f"  [{warning['level']}] {warning['message']}")
```

---

## Rolling Back Migrations

### Rollback One Version

```python
response = await nc.request(
    "rosey.db.migrate.your-plugin.rollback",
    json.dumps({}).encode()
)
```

### Rollback to Specific Version

```python
# Rollback to version 2 (rolls back all migrations after v2)
response = await nc.request(
    "rosey.db.migrate.your-plugin.rollback",
    json.dumps({"version": 2}).encode()
)
```

### Rollback All Migrations

```python
# Rollback to version 0 (removes all migrations)
response = await nc.request(
    "rosey.db.migrate.your-plugin.rollback",
    json.dumps({"version": 0}).encode()
)
```

### Dry-Run Rollback

```python
response = await nc.request(
    "rosey.db.migrate.your-plugin.rollback",
    json.dumps({"version": 0, "dry_run": True}).encode()
)
```

---

## SQLite Limitations

SQLite does not support several common ALTER TABLE operations:

### ❌ Not Supported

- `DROP COLUMN` - Cannot remove columns
- `ALTER COLUMN` - Cannot modify column type/constraints
- `ADD CONSTRAINT` - Cannot add constraints after table creation

### ✅ Workaround: Table Recreation Pattern

To work around these limitations, recreate the table with the new schema:

#### Example: Dropping a Column

```sql
-- UP
-- Remove 'deprecated_field' column using table recreation
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT
    -- Omit deprecated_field
);

-- Copy data (excluding deprecated_field)
INSERT INTO users_new (id, username, email)
SELECT id, username, email FROM users;

-- Replace old table
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- Recreate indexes
CREATE INDEX idx_users_username ON users(username);

-- DOWN
-- Restore deprecated_field column
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT,
    deprecated_field TEXT  -- Re-add column (data will be NULL)
);

INSERT INTO users_new (id, username, email)
SELECT id, username, email FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE INDEX idx_users_username ON users(username);
```

For more SQLite workaround patterns, see **[examples/migrations/](../../examples/migrations/)** directory.

---

## Validation System

### Automatic Validation

Before applying migrations, the system validates them for:

1. **Destructive Operations** (⚠️ WARNING level - allows execution)
   - DROP COLUMN
   - DROP TABLE
   - TRUNCATE TABLE

2. **SQLite Limitations** (❌ ERROR level - blocks execution)
   - DROP COLUMN (not supported)
   - ALTER COLUMN (not supported)
   - ADD CONSTRAINT (not supported)

3. **Syntax Errors** (❌ ERROR level - blocks execution)
   - Unmatched parentheses
   - Unterminated string literals

4. **Checksum Verification** (❌ ERROR level in status queries)
   - Detects if applied migration files were modified

### Validation Levels

- **INFO**: Informational messages
- **WARNING**: Concerning but not blocking (e.g., data loss warning)
- **ERROR**: Blocks migration execution

### Handling Validation Errors

```python
result = json.loads(response.data)
if not result['success']:
    if result.get('error', {}).get('code') == 'VALIDATION_FAILED':
        print("Migration validation failed:")
        for error in result.get('errors', []):
            print(f"  [{error['level']}] v{error['migration_version']}: "
                  f"{error['message']}")
```

---

## Troubleshooting

### Migration Won't Apply

**Error**: `LOCK_TIMEOUT - Migration already in progress`

**Solution**: Another migration is running for this plugin. Wait for it to complete or check for stuck processes.

---

**Error**: `VALIDATION_FAILED - SQLite does not support DROP COLUMN`

**Solution**: Use the table recreation pattern (see SQLite Limitations section above).

---

**Error**: `MIGRATION_FAILED - SQL execution error`

**Solution**: Check your SQL syntax. Test the SQL statements directly in SQLite to debug.

---

### Checksum Mismatch

**Error**: `Migration file has been modified (checksum mismatch)`

**Solution**: **Never modify applied migrations.** Create a new migration instead:

```bash
# DON'T modify 001_create_table.sql
# DO create 002_fix_schema.sql with corrections
```

### Rollback Fails

**Error**: `Cannot rollback - data would be lost`

**Solution**: Rollbacks can't restore deleted data. Consider:
1. Backup database before rollback
2. Create forward migration instead of rolling back
3. Accept data loss and re-import from backup

---

## Best Practices

1. ✅ **Never modify applied migrations** - Checksums will detect tampering
2. ✅ **Test on staging before production** - Use dry-run mode
3. ✅ **Keep migrations small** - One logical change per file
4. ✅ **Write idempotent SQL** - Use IF NOT EXISTS, IF EXISTS
5. ✅ **Document intent in comments** - Explain why, not just what
6. ✅ **Version control migrations** - Commit to git with code
7. ✅ **Backup before destructive operations** - Especially DROP TABLE
8. ✅ **Handle SQLite limitations** - Use table recreation pattern

---

## Examples

See the **[examples/migrations/](../../examples/migrations/)** directory for complete examples:

- `001_create_table.sql` - Basic table creation with indexes
- `002_add_column.sql` - Adding a column with default value
- `003_drop_column_sqlite.sql` - SQLite table recreation for DROP COLUMN
- `004_create_index.sql` - Adding index to existing table
- `005_alter_column_sqlite.sql` - SQLite table recreation for ALTER COLUMN
- `006_add_foreign_key.sql` - Adding foreign key constraint
- `007_data_migration.sql` - Migrating existing data
- `008_multiple_tables.sql` - Creating multiple related tables
- `009_complex_transformation.sql` - Multi-step schema transformation
- `010_drop_table.sql` - Safely removing a table

---

## Related Documentation

- **[Migration Best Practices](MIGRATION_BEST_PRACTICES.md)** - Detailed best practices guide
- **[Architecture](../ARCHITECTURE.md)** - System architecture overview
- **[NATS Messages](../NATS_MESSAGES.md)** - Message format reference
- **[Examples](../../examples/migrations/)** - Complete migration examples

---

**Version**: 1.0  
**Sprint**: 15 - Schema Migrations  
**Last Updated**: November 24, 2025
