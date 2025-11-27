# Migration Examples

This directory contains example migration files demonstrating common patterns for the Rosey-Robot schema migration system.

## Overview

These examples show how to:
- Create tables with indexes
- Add and modify columns
- Work around SQLite limitations
- Manage relationships with foreign keys
- Migrate existing data
- Handle complex multi-step transformations
- Safely drop tables

## Example Files

### 001_create_table.sql
**Pattern**: Basic table creation with indexes

Creates a quotes table with primary key and three indexes for common query patterns. Demonstrates:
- IF NOT EXISTS for idempotency
- Multiple CREATE INDEX statements
- Proper UP/DOWN symmetry

### 002_add_column.sql
**Pattern**: Adding a column with default value

Adds a category column to the quotes table. Demonstrates:
- ALTER TABLE ADD COLUMN syntax
- Default values for new columns
- SQLite table recreation for rollback

### 003_drop_column_sqlite.sql
**Pattern**: SQLite workaround for DROP COLUMN

Removes a column using table recreation pattern. Demonstrates:
- Complete table recreation workflow
- Data preservation during transformation
- Index recreation after table replacement

**SQLite Limitation**: DROP COLUMN not supported - must recreate table

### 004_create_index.sql
**Pattern**: Adding index to existing table

Creates a composite index for efficient multi-column filtering. Demonstrates:
- Composite index syntax
- Simple add/remove pattern
- When to use multi-column indexes

### 005_alter_column_sqlite.sql
**Pattern**: SQLite workaround for ALTER COLUMN

Changes column type and constraints using table recreation. Demonstrates:
- Type conversion during migration
- COALESCE for data transformation
- Complete index recreation

**SQLite Limitation**: ALTER COLUMN not supported - must recreate table

### 006_add_foreign_key.sql
**Pattern**: Adding foreign key constraint

Creates users table and adds foreign key to quotes. Demonstrates:
- Foreign keys must be defined at CREATE TABLE time in SQLite
- Table recreation to add constraint
- Multi-table migrations
- ON DELETE behaviors

**SQLite Limitation**: ADD CONSTRAINT not supported - must recreate table

### 007_data_migration.sql
**Pattern**: Migrating existing data

Updates existing data without changing schema. Demonstrates:
- Bulk UPDATE statements
- Data normalization
- Limited rollback capabilities for data changes
- Why data migrations need backups

### 008_multiple_tables.sql
**Pattern**: Creating multiple related tables

Creates collections and tags feature with multiple tables. Demonstrates:
- Multiple CREATE TABLE in one migration
- Many-to-many relationships
- Proper foreign key setup
- Comprehensive index strategy

### 009_complex_transformation.sql
**Pattern**: Multi-step schema evolution

Adds full-text search and audit logging. Demonstrates:
- FTS5 virtual tables
- Trigger creation for data sync
- Audit trail implementation
- Complex rollback procedures

### 010_drop_table.sql
**Pattern**: Safely removing tables

Drops deprecated tables with warnings. Demonstrates:
- Cascade considerations
- Data loss warnings in comments
- Dependency cleanup
- Non-reversible operations

## Using These Examples

### 1. Study the Pattern

Read the migration file to understand:
- What SQL operations are used
- How UP and DOWN sections mirror each other
- Any SQLite-specific workarounds
- Comments explaining the "why"

### 2. Adapt to Your Needs

Copy the relevant example and modify:
- Table names
- Column names and types
- Index names
- Constraints

### 3. Test Thoroughly

Before applying to production:
```python
# Dry-run to preview changes
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({"dry_run": True}).encode()
)
```

### 4. Apply Migration

```python
# Apply for real
response = await nc.request(
    "rosey.db.migrate.your-plugin.apply",
    json.dumps({}).encode()
)
```

## SQLite Limitation Patterns

### Pattern: DROP COLUMN

```sql
-- Create new table without the column
CREATE TABLE table_new (...columns without dropped column...);

-- Copy data
INSERT INTO table_new SELECT ...columns... FROM table;

-- Replace table
DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- Recreate indexes
CREATE INDEX ...;
```

### Pattern: ALTER COLUMN

```sql
-- Create new table with modified column
CREATE TABLE table_new (...modified column definition...);

-- Copy data with transformation
INSERT INTO table_new SELECT ...transform columns... FROM table;

-- Replace table
DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- Recreate indexes
CREATE INDEX ...;
```

### Pattern: ADD CONSTRAINT

```sql
-- Create new table with constraint
CREATE TABLE table_new (
    ...columns...,
    CONSTRAINT_NAME ...constraint definition...
);

-- Copy data
INSERT INTO table_new SELECT * FROM table;

-- Replace table
DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- Recreate indexes
CREATE INDEX ...;
```

## Best Practices from Examples

1. **Always use IF NOT EXISTS / IF EXISTS** for idempotent operations
2. **Comment your migrations** explaining why, not just what
3. **Keep migrations focused** - one logical change per file
4. **Test rollback on staging** before production deployment
5. **Backup before destructive operations** (DROP TABLE, data migrations)
6. **Recreate all indexes** after table recreation
7. **Use transactions** (automatic in migration system)
8. **Document non-reversible changes** in comments

## Related Documentation

- **[Plugin Migration Guide](../../docs/guides/PLUGIN_MIGRATIONS.md)** - Complete migration guide
- **[Migration Best Practices](../../docs/guides/MIGRATION_BEST_PRACTICES.md)** - Detailed best practices
- **[Architecture](../../docs/ARCHITECTURE.md)** - System architecture overview

## Need Help?

If these examples don't cover your use case:
1. Check the [Plugin Migration Guide](../../docs/guides/PLUGIN_MIGRATIONS.md)
2. Review [Migration Best Practices](../../docs/guides/MIGRATION_BEST_PRACTICES.md)
3. Search for similar patterns in the examples
4. Test your migration thoroughly with dry-run mode

---

**Version**: 1.0  
**Sprint**: 15 - Schema Migrations  
**Last Updated**: November 24, 2025
