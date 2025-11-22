# Alembic Database Migrations

**Sprint 11 Sortie 1** - SQLAlchemy ORM Foundation

## Overview

This directory contains Alembic migrations for managing database schema changes.

### Migration History

- **45490ea63a06** - Initial schema v0.5.0 to v0.6.0 (Sprint 11 Sortie 1)
  - Migrates raw SQL schema to SQLAlchemy ORM models
  - Adds type safety with `Mapped[type]` annotations
  - Normalizes column types (TEXT → String with lengths)
  - Adds comprehensive indexes for performance
  - Status: Pre-stamped (v0.5.0 schema already compatible)

## Usage

### Check Current Version

```bash
alembic current
```

### View Migration History

```bash
alembic history --verbose
```

### Generate New Migration

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Downgrade to base (WARNING: destroys all data)
alembic downgrade base
```

### Stamp Existing Database

If you have an existing database that matches the schema:

```bash
alembic stamp head
```

## Configuration

### Database URL

Alembic loads database URL from (in priority order):

1. **Environment Variable**: `ROSEY_DATABASE_URL`
   ```bash
   $env:ROSEY_DATABASE_URL = 'sqlite+aiosqlite:///bot_data.db'
   alembic upgrade head
   ```

2. **config.json**: `database_url` field (v0.6.0+)
   ```json
   {
     "database_url": "sqlite+aiosqlite:///bot_data.db"
   }
   ```

3. **config.json**: `database` field (v0.5.0 fallback)
   ```json
   {
     "database": "bot_data.db"
   }
   ```

4. **Default**: `sqlite+aiosqlite:///bot_data.db`

### Async Support

Alembic is configured for async SQLAlchemy operations:

- **SQLite**: `sqlite+aiosqlite:///`
- **PostgreSQL**: `postgresql+asyncpg://`

### SQLite Batch Mode

Enabled for ALTER TABLE support on SQLite (required for schema changes).

## Models

All ORM models are defined in `common/models.py`:

- **UserStats** - User activity tracking
- **UserAction** - Audit log (PM commands, moderation)
- **ChannelStats** - Channel-wide statistics
- **UserCountHistory** - Historical user count tracking
- **RecentChat** - Recent chat message cache
- **CurrentStatus** - Current bot status (singleton)
- **OutboundMessage** - Queued outbound messages
- **ApiToken** - API authentication tokens

## Migration Workflow

### 1. Update Models

Edit `common/models.py` to add/modify ORM models.

### 2. Generate Migration

```bash
alembic revision --autogenerate -m "Add new_table"
```

### 3. Review Generated Migration

Check `alembic/versions/<hash>_<description>.py`:

- Verify table/column changes are correct
- Check indexes and constraints
- Test upgrade/downgrade logic

### 4. Test Migration

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Test re-upgrade
alembic upgrade head
```

### 5. Commit Migration

```bash
git add alembic/versions/<hash>_<description>.py
git commit -m "Add migration: <description>"
```

## Production Deployment

### Pre-Deployment

1. **Backup Database**:
   ```bash
   # SQLite
   cp bot_data.db bot_data.db.backup

   # PostgreSQL
   pg_dump -h localhost -U postgres rosey_bot > backup.sql
   ```

2. **Test Migration** (on staging):
   ```bash
   alembic upgrade head
   ```

3. **Verify Application** (on staging):
   ```bash
   python -m pytest tests/integration/test_database.py -v
   ```

### Deployment

1. **Stop Bot**:
   ```bash
   systemctl stop cytube-bot
   ```

2. **Apply Migration**:
   ```bash
   cd /opt/rosey-bot
   source venv/bin/activate
   alembic upgrade head
   ```

3. **Verify Migration**:
   ```bash
   alembic current
   # Should show: <hash> (head)
   ```

4. **Start Bot**:
   ```bash
   systemctl start cytube-bot
   ```

### Rollback

If migration fails:

```bash
# Stop bot
systemctl stop cytube-bot

# Rollback migration
alembic downgrade -1

# Restore backup (if needed)
cp bot_data.db.backup bot_data.db

# Start bot
systemctl start cytube-bot
```

## Troubleshooting

### "No such table" Error

If you see `NoSuchTableError: <table>` during migration:

1. **Fresh Database**: Use `Base.metadata.create_all()` instead
2. **Existing Database**: Verify schema with `alembic current`

### "Table already exists" Error

Database schema already matches migration:

```bash
alembic stamp head
```

### Migration Out of Sync

Reset Alembic version:

```bash
# Check current version
alembic current

# Stamp correct version
alembic stamp <revision_hash>
```

### Offline Migrations

Generate SQL without applying:

```bash
alembic upgrade head --sql > migration.sql
```

Review `migration.sql` and apply manually.

## Architecture

### Async Engine

Migrations use async SQLAlchemy engine:

```python
from sqlalchemy.ext.asyncio import async_engine_from_config

connectable = async_engine_from_config(
    configuration,
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)

async with connectable.connect() as connection:
    await connection.run_sync(do_run_migrations)
```

### Batch Mode

SQLite requires batch mode for ALTER TABLE:

```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,  # Required for SQLite
)
```

### Autogeneration

Alembic detects schema changes automatically:

- Added/dropped tables
- Added/dropped columns
- Type changes (with `compare_type=True`)
- Index changes
- Constraint changes (with `compare_server_default=True`)

## References

- **Alembic Documentation**: https://alembic.sqlalchemy.org/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/
- **Sprint 11 PRD**: `docs/sprints/active/11-The-Conversation/PRD-ORM-Migration.md`
- **Sortie 1 SPEC**: `docs/sprints/active/11-The-Conversation/SPEC-Sortie-1-ORM-Foundation.md`

---

**Version**: v0.6.0  
**Created**: Sprint 11 Sortie 1 (Nov 2025)  
**Author**: Rosey-Robot Team
