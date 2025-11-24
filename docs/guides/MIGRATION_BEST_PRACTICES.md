# Migration Best Practices

**Sprint**: 15 - Schema Migrations  
**Version**: 1.0  
**Last Updated**: November 24, 2025

---

## Golden Rules

### 1. Never Modify Applied Migrations

Once a migration has been applied to any environment (especially production), treat the file as **immutable**.

**Why**: The system computes SHA-256 checksums of migration files. If you modify an applied migration, the checksum will mismatch and the system will detect tampering.

❌ **Bad**:
```bash
# Migration already applied to production
$ vim plugins/quote-db/migrations/001_create_table.sql
# Edit to fix typo...
```

✅ **Good**:
```bash
# Create new migration to fix the issue
$ cat > plugins/quote-db/migrations/004_fix_schema.sql
-- UP
ALTER TABLE quotes ADD COLUMN fixed_field TEXT;
-- DOWN
-- Use table recreation to remove column
```

### 2. Write Idempotent Migrations

Migrations should be safe to re-run without errors.

❌ **Bad**:
```sql
-- UP
CREATE TABLE quotes (...);  -- Fails if table exists
```

✅ **Good**:
```sql
-- UP
CREATE TABLE IF NOT EXISTS quotes (...);  -- Safe to re-run
```

### 3. Keep Migrations Small

One logical change per migration file makes them:
- Easier to review
- Easier to rollback
- Easier to debug
- Faster to execute

❌ **Bad**: `001_setup_everything.sql` with 500 lines creating 10 tables

✅ **Good**:
- `001_create_quotes_table.sql`
- `002_create_users_table.sql`
- `003_add_quote_indexes.sql`

### 4. Test on Staging First

Always test migrations on a staging database before production.

```python
# 1. Test with dry-run
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({"dry_run": True}).encode()
)

# 2. Apply to staging database
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({}).encode()
)

# 3. Verify application functionality
# 4. Only then apply to production
```

### 5. Write Reversible DOWN SQL

Every UP should have a matching DOWN that reverses the changes.

✅ **Good**:
```sql
-- UP
CREATE TABLE quotes (...);
CREATE INDEX idx_author ON quotes(author);

-- DOWN
DROP INDEX idx_author;
DROP TABLE quotes;
```

⚠️ **Acceptable** (with documentation):
```sql
-- UP
DROP TABLE deprecated_table;  -- Data will be lost

-- DOWN
-- Cannot restore deleted data
-- Restore from backup if rollback needed
CREATE TABLE deprecated_table (...);
```

### 6. Document Intent in Comments

Explain **why** changes are being made, not just **what**.

❌ **Bad**:
```sql
-- UP
CREATE TABLE users (id INTEGER PRIMARY KEY);
```

✅ **Good**:
```sql
-- UP
-- Create users table to track quote authors
-- Enables future features: user profiles, author attribution
CREATE TABLE users (id INTEGER PRIMARY KEY);
```

### 7. Handle SQLite Limitations

SQLite does not support DROP COLUMN, ALTER COLUMN, or ADD CONSTRAINT directly. Use table recreation pattern.

See [SQLite Workarounds](#sqlite-workarounds) section below.

### 8. Backup Before Destructive Operations

Before migrations that drop tables or modify data:

```bash
# Backup database
$ cp bot_data.db bot_data.backup.$(date +%Y%m%d).db

# Then apply migration
```

---

## Idempotency Patterns

### CREATE TABLE

✅ **Idempotent**:
```sql
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL
);
```

### CREATE INDEX

✅ **Idempotent**:
```sql
CREATE INDEX IF NOT EXISTS idx_quotes_author ON quotes(author);
```

### DROP TABLE

✅ **Idempotent**:
```sql
DROP TABLE IF EXISTS old_table;
```

### DROP INDEX

✅ **Idempotent**:
```sql
DROP INDEX IF EXISTS idx_old;
```

### ALTER TABLE ADD COLUMN

⚠️ **Not fully idempotent in SQLite** (no IF NOT EXISTS for columns):

```sql
-- SQLite will error if column exists
ALTER TABLE quotes ADD COLUMN category TEXT DEFAULT '';

-- Workaround: Check in application code before applying
-- Or use table recreation to make idempotent
```

### INSERT Data

⚠️ **Not idempotent** without checks:

```sql
-- Will insert duplicates on re-run
INSERT INTO config (key, value) VALUES ('version', '1.0');

-- Better: Use INSERT OR IGNORE with UNIQUE constraint
INSERT OR IGNORE INTO config (key, value) VALUES ('version', '1.0');

-- Or: Use REPLACE
REPLACE INTO config (key, value) VALUES ('version', '1.0');
```

---

## Rollback Safety

### Safe Rollbacks

Operations that can be safely reversed:

✅ **CREATE TABLE** → DROP TABLE
```sql
-- UP
CREATE TABLE temp_data (...);
-- DOWN
DROP TABLE temp_data;  -- Safe if data is temporary
```

✅ **CREATE INDEX** → DROP INDEX
```sql
-- UP
CREATE INDEX idx_fast_lookup ON table(column);
-- DOWN
DROP INDEX idx_fast_lookup;  -- Completely reversible
```

✅ **ALTER TABLE ADD COLUMN** → Table recreation without column
```sql
-- UP
ALTER TABLE users ADD COLUMN phone TEXT;
-- DOWN
-- Recreate table without phone column (data in phone column lost)
```

### Dangerous Rollbacks

Operations where rollback causes data loss:

⚠️ **DROP TABLE** - Cannot restore deleted data
```sql
-- UP
DROP TABLE deprecated_table;
-- DOWN
CREATE TABLE deprecated_table (...);
-- WARNING: Original data cannot be restored
```

⚠️ **Data modifications** - Original values lost
```sql
-- UP
UPDATE quotes SET author = 'Unknown' WHERE author IS NULL;
-- DOWN
-- Cannot determine which authors were originally NULL
```

### Handling Non-Reversible Changes

**Document the limitation**:
```sql
-- UP
DROP TABLE legacy_users;

-- DOWN
-- WARNING: Data cannot be restored by this rollback
-- Restore from backup if rollback is required
CREATE TABLE legacy_users (...);
```

**Recommend backup strategy**:
```sql
-- UP
-- BACKUP DATABASE BEFORE APPLYING THIS MIGRATION
-- This migration deletes all data in old_table
DROP TABLE old_table;

-- DOWN
-- Restore from backup taken before migration
```

---

## Testing Migrations

### Unit Test Pattern

```python
import pytest
from common.database import BotDatabase
from common.migrations import MigrationManager, MigrationExecutor

@pytest.fixture
async def test_db():
    """Fresh database for each test."""
    db = BotDatabase(':memory:')
    await db.connect()
    yield db
    await db.close()

@pytest.mark.asyncio
async def test_migration_001_creates_quotes_table(test_db):
    """Test that migration 001 creates quotes table correctly."""
    manager = MigrationManager(test_db)
    executor = MigrationExecutor(test_db)
    
    # Discover migrations
    migrations = manager.discover_migrations('quote-db')
    migration_001 = [m for m in migrations if m.version == 1][0]
    
    # Apply migration
    async with test_db._get_session() as session:
        result = await executor.apply_migration(
            session, 'quote-db', migration_001, 'test'
        )
    
    assert result.success
    
    # Verify table exists
    async with test_db._get_session() as session:
        tables = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        table_names = [row[0] for row in tables]
        assert 'quotes' in table_names
    
    # Verify indexes exist
    async with test_db._get_session() as session:
        indexes = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='quotes'")
        )
        index_names = [row[0] for row in indexes]
        assert 'idx_quotes_author' in index_names

@pytest.mark.asyncio
async def test_migration_001_rollback(test_db):
    """Test that migration 001 can be rolled back."""
    manager = MigrationManager(test_db)
    executor = MigrationExecutor(test_db)
    
    migrations = manager.discover_migrations('quote-db')
    migration_001 = [m for m in migrations if m.version == 1][0]
    
    # Apply then rollback
    async with test_db._get_session() as session:
        await executor.apply_migration(session, 'quote-db', migration_001, 'test')
        await executor.rollback_migration(session, 'quote-db', migration_001, 'test')
    
    # Verify table removed
    async with test_db._get_session() as session:
        tables = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        table_names = [row[0] for row in tables]
        assert 'quotes' not in table_names
```

### Integration Test Pattern

```python
@pytest.mark.asyncio
async def test_full_migration_cycle():
    """Test applying all migrations then rolling back all."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    try:
        manager = MigrationManager(db)
        executor = MigrationExecutor(db)
        
        # Apply all migrations
        migrations = manager.discover_migrations('quote-db')
        for migration in migrations:
            async with db._get_session() as session:
                result = await executor.apply_migration(
                    session, 'quote-db', migration, 'test'
                )
                assert result.success
        
        # Verify final state
        async with db._get_session() as session:
            # Check expected tables exist
            # Check expected indexes exist
            # Insert test data
            # Query test data
            pass
        
        # Rollback all
        for migration in reversed(migrations):
            async with db._get_session() as session:
                result = await executor.rollback_migration(
                    session, 'quote-db', migration, 'test'
                )
                assert result.success
        
        # Verify clean state
        async with db._get_session() as session:
            tables = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            table_names = [row[0] for row in tables]
            # Only system tables should remain
            assert 'quotes' not in table_names
    
    finally:
        await db.close()
```

---

## SQLite Workarounds

### DROP COLUMN Pattern

**Problem**: SQLite doesn't support `ALTER TABLE DROP COLUMN`

**Solution**: Recreate table without the column

```sql
-- UP
-- Remove 'deprecated_col' using table recreation
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    kept_col TEXT
    -- Omit deprecated_col
);

INSERT INTO table_new (id, kept_col)
SELECT id, kept_col FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- Recreate indexes
CREATE INDEX idx_kept ON table(kept_col);

-- DOWN
-- Restore deprecated_col (data will be NULL)
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    kept_col TEXT,
    deprecated_col TEXT
);

INSERT INTO table_new (id, kept_col)
SELECT id, kept_col FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

CREATE INDEX idx_kept ON table(kept_col);
```

### ALTER COLUMN Pattern

**Problem**: SQLite doesn't support `ALTER TABLE ALTER COLUMN`

**Solution**: Recreate table with modified column

```sql
-- UP
-- Change column type from TEXT to INTEGER
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    changed_col INTEGER  -- Changed from TEXT
);

-- Copy with type conversion
INSERT INTO table_new (id, changed_col)
SELECT id, CAST(changed_col AS INTEGER) FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- DOWN
-- Revert to TEXT
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    changed_col TEXT  -- Back to TEXT
);

INSERT INTO table_new (id, changed_col)
SELECT id, CAST(changed_col AS TEXT) FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;
```

### ADD CONSTRAINT Pattern

**Problem**: SQLite doesn't support `ALTER TABLE ADD CONSTRAINT`

**Solution**: Recreate table with constraint in definition

```sql
-- UP
-- Add foreign key constraint
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    other_id INTEGER,
    FOREIGN KEY (other_id) REFERENCES other_table(id)
);

INSERT INTO table_new SELECT * FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;

-- DOWN
-- Remove constraint
CREATE TABLE table_new (
    id INTEGER PRIMARY KEY,
    other_id INTEGER
    -- No constraint
);

INSERT INTO table_new SELECT * FROM table;

DROP TABLE table;
ALTER TABLE table_new RENAME TO table;
```

### Tips for Table Recreation

1. **Always rename to table_new** - clear naming convention
2. **Copy data carefully** - match column order and types
3. **Recreate all indexes** - they're dropped with original table
4. **Test thoroughly** - data transformation can have edge cases
5. **Consider data volume** - large tables take time to copy

---

## Data Migrations

### When to Migrate Data

Migrate data in migrations when:
- Normalizing existing data
- Fixing data quality issues
- Populating new columns with defaults
- Transforming data format

### Performance Considerations

For large tables, batch updates:

```sql
-- UP
-- Bad: Single UPDATE on million-row table
UPDATE large_table SET new_col = COMPUTE_VALUE(old_col);

-- Better: Batch with LIMIT (run multiple times)
UPDATE large_table 
SET new_col = COMPUTE_VALUE(old_col)
WHERE id IN (
    SELECT id FROM large_table 
    WHERE new_col IS NULL 
    LIMIT 1000
);
```

### Transaction Safety

All migrations run in transactions automatically:
- If UP fails, entire migration rolls back
- If DOWN fails, entire rollback aborts
- Database left in consistent state

```sql
-- UP
-- All these statements execute atomically
UPDATE table1 SET col = 'value';
UPDATE table2 SET col = 'value';
-- If either fails, both roll back
```

### Default Values

When adding columns, consider:

```sql
-- UP
-- Option 1: Default at column definition
ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active';

-- Option 2: Update after adding
ALTER TABLE users ADD COLUMN status TEXT;
UPDATE users SET status = 'active' WHERE status IS NULL;

-- Option 3: Computed default
ALTER TABLE users ADD COLUMN full_name TEXT;
UPDATE users SET full_name = first_name || ' ' || last_name;
```

### Data Validation

Validate data after migration:

```sql
-- UP
UPDATE quotes SET author = 'Unknown' WHERE author IS NULL;

-- Verify all authors are set
-- SELECT COUNT(*) FROM quotes WHERE author IS NULL; -- Should be 0

-- Add NOT NULL constraint after data fixed
-- (Requires table recreation in SQLite)
```

---

## Error Handling

### Validation Errors

**ERROR: `VALIDATION_FAILED - SQLite does not support DROP COLUMN`**

Fix: Use table recreation pattern

**ERROR: `Unmatched parentheses`**

Fix: Check SQL syntax, count opening/closing parens

**ERROR: `Unterminated string`**

Fix: Check quotes, use proper escaping

### Execution Errors

**ERROR: `MIGRATION_FAILED - no such table: xyz`**

Fix: Ensure migrations run in order, previous migrations applied

**ERROR: `MIGRATION_FAILED - UNIQUE constraint failed`**

Fix: Check for duplicate data, add UNIQUE constraint handling

**ERROR: `LOCK_TIMEOUT`**

Fix: Wait for other migration to complete, check for stuck processes

### Checksum Errors

**ERROR: `Migration file has been modified (checksum mismatch)`**

Fix: Do not modify applied migrations. Create new migration instead.

### Recovery Strategies

**If migration fails mid-execution:**
1. Transaction automatically rolls back
2. Check error message
3. Fix migration SQL
4. Re-apply migration

**If data is corrupted:**
1. Restore from backup
2. Fix migration
3. Re-apply

**If production migration fails:**
1. DO NOT PANIC
2. Transaction rolled back - database still consistent
3. Fix migration on dev/staging
4. Test thoroughly
5. Re-deploy and re-apply

---

## Deployment Workflow

### Development Phase

```bash
# 1. Create feature branch
git checkout -b feature/add-tags-table

# 2. Create migration file
cat > plugins/quote-db/migrations/004_create_tags.sql
# Write UP and DOWN SQL

# 3. Test locally
python
>>> # Connect to NATS, apply migration with dry_run=True
>>> # Apply migration for real to local database
>>> # Test application functionality

# 4. Run unit tests
pytest tests/unit/migrations/test_004_create_tags.py

# 5. Commit
git add plugins/quote-db/migrations/004_create_tags.sql
git commit -m "Add tags table migration"
```

### Code Review

```markdown
**Migration Checklist**:
- [ ] UP and DOWN sections both present
- [ ] SQL syntax correct
- [ ] Idempotent where possible
- [ ] Handles SQLite limitations if needed
- [ ] Comments explain intent
- [ ] Tests pass
- [ ] Rollback tested on staging
```

### Staging Deployment

```bash
# 1. Merge to main
git checkout main
git merge feature/add-tags-table

# 2. Deploy code to staging
./deploy_staging.sh

# 3. Backup staging database
cp /data/staging/bot_data.db /backups/bot_data.staging.$(date +%Y%m%d).db

# 4. Apply migration
python
>>> # Connect to staging NATS
>>> # Apply migration
>>> # Verify application works

# 5. Test rollback
>>> # Rollback migration
>>> # Verify application still works

# 6. Re-apply migration
>>> # Apply again for final state
```

### Production Deployment

```bash
# 1. Schedule maintenance window (if needed)
# 2. Announce to users

# 3. Deploy code to production
./deploy_production.sh

# 4. Backup production database
cp /data/prod/bot_data.db /backups/bot_data.prod.$(date +%Y%m%d).db

# 5. Apply migration (during low-traffic period)
python
>>> # Connect to production NATS
>>> # Apply migration
>>> # Monitor for errors

# 6. Verify application health
# - Check error logs
# - Test key features
# - Monitor performance metrics

# 7. Monitor for issues (24-48 hours)
```

### Rollback Procedure

```bash
# If issues discovered after deployment:

# 1. Assess severity
# - Data corruption? Rollback immediately
# - Performance issue? May be fixed forward
# - Minor bug? Create fix migration

# 2. Backup current state
cp /data/prod/bot_data.db /backups/bot_data.prod.before_rollback.$(date +%Y%m%d).db

# 3. Rollback migration
python
>>> # Connect to NATS
>>> # Rollback to previous version

# 4. Verify application works

# 5. Rollback code deployment
git revert <commit>
./deploy_production.sh

# 6. Investigate and fix issue on dev/staging
# 7. Re-deploy when fixed
```

---

## Anti-Patterns to Avoid

### ❌ Modifying Applied Migrations

```bash
# NEVER DO THIS
vim plugins/quote-db/migrations/001_create_table.sql
# Edit already-applied migration
```

Checksums will detect this and block further migrations.

### ❌ Skipping Rollback Testing

```python
# Testing only the UP direction
await apply_migration()
# Assuming DOWN works...
```

Always test rollback on staging before production.

### ❌ Making Migrations Dependent on Application Code

```sql
-- UP
-- WRONG: Calling application function
UPDATE users SET status = CALL_PYTHON_FUNCTION(username);

-- RIGHT: Pure SQL only
UPDATE users SET status = 'active';
```

### ❌ Ignoring Validation Warnings

```python
result = json.loads(response.data)
# Ignoring warnings...
if result['success']:
    # Continue without reading warnings
```

Read and understand all warnings, especially for destructive operations.

### ❌ Running Migrations Manually in Production

```bash
# WRONG: Manually editing production database
sqlite3 /data/prod/bot_data.db
sqlite> ALTER TABLE...
```

Always use the migration system to track changes.

### ❌ Combining Schema and Data Changes Poorly

```sql
-- UP
CREATE TABLE new_table (...);
-- Migrating millions of rows...
UPDATE massive_table SET ...;
```

Split into separate migrations for better rollback granularity.

---

## Checklist: Before Merging Migration PR

- [ ] UP and DOWN sections present and correct
- [ ] SQL syntax validated (no syntax errors)
- [ ] Idempotent where possible (IF NOT EXISTS, etc.)
- [ ] SQLite limitations handled (table recreation if needed)
- [ ] Comments explain intent and any gotchas
- [ ] Unit tests written and passing
- [ ] Dry-run tested locally
- [ ] Applied and rolled back on local database
- [ ] Applied to staging database
- [ ] Application tested on staging
- [ ] Rollback tested on staging
- [ ] Re-applied to staging for final state
- [ ] Performance impact assessed
- [ ] Backup strategy documented if destructive
- [ ] Code review approved

---

## Related Documentation

- **[Plugin Migration Guide](PLUGIN_MIGRATIONS.md)** - How to write and apply migrations
- **[Migration Examples](../../examples/migrations/)** - Complete example files
- **[Architecture](../ARCHITECTURE.md)** - System architecture overview
- **[NATS Messages](../NATS_MESSAGES.md)** - Message format reference

---

**Version**: 1.0  
**Sprint**: 15 - Schema Migrations  
**Last Updated**: November 24, 2025
