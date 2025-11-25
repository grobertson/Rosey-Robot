# Alembic Migration Guide

**Project**: Rosey-Robot  
**Version**: 0.6.0+  
**Last Updated**: November 22, 2025  

---

## Overview

Rosey Bot uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations. Alembic provides version-controlled, incremental schema changes with automatic upgrade and rollback capabilities.

**Why Alembic?**
- ✅ Version-controlled schema changes (like Git for databases)
- ✅ Automatic migration generation from ORM models
- ✅ Rollback support (undo migrations)
- ✅ Works with SQLite and PostgreSQL
- ✅ Production-ready (battle-tested)

---

## Quick Start

### Common Commands

```bash
# Check current migration version
alembic current

# Show migration history
alembic history --verbose

# Upgrade to latest version
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Create new migration (auto-detect changes)
alembic revision --autogenerate -m "Add user email column"

# Create empty migration (for data migrations)
alembic revision -m "Populate default settings"
```

---

## Creating Migrations

### Auto-Generate from Models

**Best For**: Schema changes (add/remove columns, tables, indexes)

**Workflow**:

1. **Modify ORM Models** (`common/models.py`):
   ```python
   class UserStats(Base):
       __tablename__ = 'user_stats'
       
       # Add new column
       email: Mapped[Optional[str]] = mapped_column(String(255))
   ```

2. **Generate Migration**:
   ```bash
   alembic revision --autogenerate -m "Add email to user_stats"
   ```

3. **Review Migration** (`alembic/versions/<hash>_add_email_to_user_stats.py`):
   ```python
   def upgrade() -> None:
       op.add_column('user_stats', sa.Column('email', sa.String(255), nullable=True))

   def downgrade() -> None:
       op.drop_column('user_stats', 'email')
   ```

4. **Test Migration**:
   ```bash
   # Apply migration
   alembic upgrade head
   
   # Verify schema
   sqlite3 bot_data.db ".schema user_stats"
   # or
   psql -d rosey_db -c "\d user_stats"
   ```

5. **Commit to Git**:
   ```bash
   git add alembic/versions/<hash>_add_email_to_user_stats.py
   git commit -m "Add email column to user_stats"
   ```

### Manual Migrations

**Best For**: Data migrations, complex schema changes

**Example: Populate Default Data**:

1. **Create Empty Migration**:
   ```bash
   alembic revision -m "Populate default channel settings"
   ```

2. **Edit Migration File**:
   ```python
   from alembic import op
   import sqlalchemy as sa
   from sqlalchemy import text

   def upgrade() -> None:
       # Insert default settings
       op.execute(
           text("""
           INSERT INTO channel_stats (id, max_users, max_connected)
           VALUES (1, 0, 0)
           """)
       )

   def downgrade() -> None:
       # Remove default settings
       op.execute(
           text("DELETE FROM channel_stats WHERE id = 1")
       )
   ```

3. **Test Migration**:
   ```bash
   alembic upgrade head
   
   # Verify data
   sqlite3 bot_data.db "SELECT * FROM channel_stats;"
   ```

### Migration from Raw SQL

**Converting Existing SQL**:

```python
# Old raw SQL (common/database.py v0.5.0)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_stats (
        username TEXT PRIMARY KEY,
        total_chat_lines INTEGER DEFAULT 0
    )
""")

# New Alembic migration
def upgrade() -> None:
    op.create_table(
        'user_stats',
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('total_chat_lines', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('username')
    )
```

---

## Running Migrations

### Upgrade

**To Latest Version**:
```bash
alembic upgrade head
```

**One Version at a Time**:
```bash
alembic upgrade +1
```

**To Specific Version**:
```bash
alembic upgrade abc123  # Use revision hash
```

**Dry Run** (PostgreSQL only):
```bash
alembic upgrade head --sql > migration.sql
# Review migration.sql before applying
```

### Downgrade

**One Version Back**:
```bash
alembic downgrade -1
```

**To Specific Version**:
```bash
alembic downgrade abc123
```

**To Base** (WARNING: Drops all tables):
```bash
alembic downgrade base
```

### Check Status

**Current Version**:
```bash
alembic current
```

**Migration History**:
```bash
alembic history

# Verbose (shows full details)
alembic history --verbose

# Recent migrations only
alembic history --indicate-current -r-5:
```

**Pending Migrations**:
```bash
alembic show
```

---

## Migration Best Practices

### 1. One Logical Change Per Migration

**Good**:
```bash
alembic revision --autogenerate -m "Add user email column"
alembic revision --autogenerate -m "Add index on email"
```

**Bad**:
```bash
alembic revision --autogenerate -m "Add email, phone, address, and 5 indexes"
```

**Why**: Easier to review, test, and rollback

### 2. Always Review Auto-Generated Migrations

Alembic may miss:
- Renamed columns (appears as drop + add)
- Table renames (appears as drop + create)
- Data transformations

**Review Checklist**:
- [ ] Check upgrade() logic
- [ ] Check downgrade() logic
- [ ] Verify nullable constraints
- [ ] Check default values
- [ ] Test with sample data

### 3. Test Migrations Both Ways

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Test re-upgrade
alembic upgrade head
```

### 4. Add Indexes in Separate Migrations

**Why**: Indexes can be added concurrently in PostgreSQL without locking

```bash
# Schema change
alembic revision --autogenerate -m "Add user_email column"

# Index (separate migration)
alembic revision -m "Add index on user_email"
```

### 5. Handle Data Migrations Carefully

**Pattern**:
```python
def upgrade() -> None:
    # 1. Add new column (nullable)
    op.add_column('user_stats', sa.Column('display_name', sa.String(), nullable=True))
    
    # 2. Populate data
    op.execute(
        text("UPDATE user_stats SET display_name = username WHERE display_name IS NULL")
    )
    
    # 3. Make non-nullable (if needed)
    op.alter_column('user_stats', 'display_name', nullable=False)

def downgrade() -> None:
    op.drop_column('user_stats', 'display_name')
```

### 6. Use Transactions

**Automatic**: Alembic wraps migrations in transactions by default

**Disable** (for operations that can't run in transaction):
```python
# At top of migration file
def upgrade() -> None:
    # Create index concurrently (PostgreSQL only, can't run in transaction)
    op.execute("COMMIT")
    op.execute("CREATE INDEX CONCURRENTLY idx_username ON user_stats(username)")
```

---

## Common Scenarios

### Add Column

```bash
# 1. Update model
# common/models.py
class UserStats(Base):
    email: Mapped[Optional[str]] = mapped_column(String(255))

# 2. Generate migration
alembic revision --autogenerate -m "Add email column"

# 3. Apply
alembic upgrade head
```

### Drop Column

```bash
# 1. Remove from model
# Delete line from common/models.py

# 2. Generate migration
alembic revision --autogenerate -m "Remove deprecated phone column"

# 3. Apply
alembic upgrade head
```

### Rename Column

**Manual Migration** (Alembic sees this as drop + add):

```python
def upgrade() -> None:
    op.alter_column('user_stats', 'old_name', new_column_name='new_name')

def downgrade() -> None:
    op.alter_column('user_stats', 'new_name', new_column_name='old_name')
```

### Add Index

```bash
# 1. Update model
# common/models.py
class UserStats(Base):
    username: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

# 2. Generate migration
alembic revision --autogenerate -m "Add index on username"

# 3. Apply
alembic upgrade head
```

### Create Table

```bash
# 1. Create model
# common/models.py
class NewTable(Base):
    __tablename__ = 'new_table'
    id: Mapped[int] = mapped_column(primary_key=True)

# 2. Generate migration
alembic revision --autogenerate -m "Create new_table"

# 3. Apply
alembic upgrade head
```

### Drop Table

```bash
# 1. Delete model from common/models.py

# 2. Generate migration
alembic revision --autogenerate -m "Drop deprecated_table"

# 3. Apply
alembic upgrade head
```

---

## Troubleshooting

### Merge Conflicts

**Symptom**: Multiple developers create migrations with same parent

**Solution**:
```bash
# Create merge migration
alembic merge -m "Merge feature branches" <rev1> <rev2>

# Apply merge
alembic upgrade head
```

### Out of Sync

**Symptom**: `CommandError: Can't locate revision identified by 'abc123'`

**Solution**:
```bash
# Check current state
alembic current

# Stamp to correct version (skip migrations)
alembic stamp head

# Try upgrade again
alembic upgrade head
```

### Tables Already Exist

**Symptom**: `ProgrammingError: relation "user_stats" already exists`

**Solution**:
```bash
# Stamp to head (tell Alembic tables exist)
alembic stamp head

# Future migrations will work
alembic upgrade head
```

### Downgrade Fails

**Symptom**: `downgrade() removes data that can't be restored`

**Solution**: Migrations with data loss can't be reversed. Options:
1. Restore from backup
2. Skip the problematic downgrade
3. Write manual data restoration script

**Prevention**: Test downgrades in development first

### Migration History Lost

**Symptom**: Alembic can't find migration history

**Solution**:
```bash
# Check alembic_version table
sqlite3 bot_data.db "SELECT * FROM alembic_version;"
# or
psql -d rosey_db -c "SELECT * FROM alembic_version;"

# If empty, stamp to current version
alembic stamp head
```

---

## CI/CD Integration

### GitHub Actions

**Workflow**: `.github/workflows/ci.yml`

```yaml
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run Alembic migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://rosey:test_password@localhost/rosey_test
      
      - name: Run tests
        run: pytest tests/
```

**Matrix Testing** (SQLite + PostgreSQL):
```yaml
strategy:
  matrix:
    db: [sqlite, postgresql]

steps:
  - name: Set DATABASE_URL
    run: |
      if [ "${{ matrix.db }}" = "postgresql" ]; then
        echo "DATABASE_URL=postgresql+asyncpg://rosey:test@localhost/test" >> $GITHUB_ENV
      else
        echo "DATABASE_URL=sqlite+aiosqlite:///:memory:" >> $GITHUB_ENV
      fi
  
  - name: Run migrations
    run: alembic upgrade head
```

### Pre-Deployment Checks

**Script**: `scripts/pre_deploy.sh`

```bash
#!/bin/bash
set -e

echo "Running pre-deployment checks..."

# Check pending migrations
PENDING=$(alembic show 2>&1 || echo "none")
if [ "$PENDING" != "none" ]; then
  echo "⚠️  Pending migrations detected:"
  echo "$PENDING"
  read -p "Apply migrations? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    alembic upgrade head
  else
    echo "❌ Deployment aborted"
    exit 1
  fi
fi

# Verify database connection
python -c "
from common.database import BotDatabase
import asyncio

async def test():
    db = BotDatabase()
    await db.connect()
    count = await db.get_total_users_seen()
    print(f'✅ Database connected ({count} users)')
    await db.close()

asyncio.run(test())
"

echo "✅ Pre-deployment checks passed"
```

**Use in Deployment**:
```bash
# Before deploying
./scripts/pre_deploy.sh

# If checks pass, deploy
./scripts/deploy.sh
```

---

## Advanced Topics

### Branching

**Multiple Feature Branches**:
```bash
# Feature A creates migration
git checkout feature-a
alembic revision --autogenerate -m "Add feature A"
git commit -am "Add feature A migration"

# Feature B creates migration (same parent)
git checkout feature-b
alembic revision --autogenerate -m "Add feature B"
git commit -am "Add feature B migration"

# Merge both branches
git checkout main
git merge feature-a
git merge feature-b

# Create merge migration
alembic merge -m "Merge feature A and B"
alembic upgrade head
```

### Custom Migration Scripts

**Hook into Migration**:

```python
# alembic/env.py
def run_migrations_offline() -> None:
    # Add custom logic
    context.configure(
        # ... existing config ...
        version_table='alembic_version',
        render_as_batch=True,  # SQLite batch mode
    )
```

### Database-Specific Migrations

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    bind = op.get_bind()
    
    if bind.dialect.name == 'postgresql':
        # PostgreSQL-specific
        op.execute("CREATE INDEX CONCURRENTLY idx_username ON user_stats(username)")
    else:
        # SQLite fallback
        op.create_index('idx_username', 'user_stats', ['username'])
```

---

## Resources

### Documentation
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [DATABASE_SETUP.md](DATABASE_SETUP.md) - Database configuration
- [ARCHITECTURE.md](ARCHITECTURE.md) - Database architecture

### Migration Files
- Location: `alembic/versions/`
- Config: `alembic.ini`
- Environment: `alembic/env.py`

### Getting Help
- GitHub Issues: Report migration problems
- Alembic ML: alembic-discuss@googlegroups.com
- Stack Overflow: [alembic] tag

---

**Document Version**: 1.0  
**Last Updated**: November 22, 2025  
**Maintained By**: Rosey-Robot Team
