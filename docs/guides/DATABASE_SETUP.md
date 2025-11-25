# PostgreSQL Setup Guide

**Project**: Rosey-Robot  
**Version**: 0.6.1  
**Last Updated**: November 22, 2025  

---

## Overview

Rosey Bot supports both SQLite and PostgreSQL databases through SQLAlchemy's async ORM. This guide covers PostgreSQL setup for local development, staging, and production environments.

**Use Cases**:
- **Development/Testing**: SQLite (zero-config, fast)
- **Staging**: PostgreSQL (production-like environment)
- **Production**: PostgreSQL (ACID, concurrent writes, replication)

---

## Quick Start (Docker Compose)

### 1. Start Services

```bash
# Start PostgreSQL, NATS, and pgAdmin
docker-compose up -d

# View logs
docker-compose logs -f postgres

# Wait for "database system is ready to accept connections"
```

### 2. Configure Database URL

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"

# Linux/macOS
export DATABASE_URL="postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"
```

### 3. Run Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify tables created
docker-compose exec postgres psql -U rosey -d rosey_dev -c "\dt"
```

### 4. Run Tests

```bash
# All tests with PostgreSQL
pytest tests/ -v

# Just functional tests
pytest tests/unit/test_database_functional.py -v
```

### 5. Access pgAdmin (Optional)

```
URL: http://localhost:5050
Email: admin@rosey.local
Password: admin
```

**Add Server in pgAdmin**:
- Name: Rosey Dev
- Host: postgres (container name)
- Port: 5432
- Database: rosey_dev
- Username: rosey
- Password: rosey_dev_password

---

## Installation Methods

### Method 1: Docker Compose (Recommended)

**Advantages**:
- ✅ Zero PostgreSQL installation required
- ✅ Consistent across all platforms
- ✅ Includes NATS and pgAdmin
- ✅ Data persists in Docker volumes
- ✅ Easy cleanup and reset

**Setup**:
```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View PostgreSQL logs
docker-compose logs -f postgres

# Connect to PostgreSQL
docker-compose exec postgres psql -U rosey -d rosey_dev
```

**Docker Compose Services**:
- **postgres**: PostgreSQL 16-alpine on port 5432
- **nats**: NATS 2.10-alpine on ports 4222/8222
- **pgadmin**: pgAdmin 4 on port 5050

**Cleanup**:
```bash
# Stop services (data preserved)
docker-compose down

# Stop and delete data
docker-compose down -v
```

---

### Method 2: Manual PostgreSQL Installation

**Windows**:
```powershell
# Download PostgreSQL 16 from https://www.postgresql.org/download/windows/
# Run installer, note password

# Create database
psql -U postgres
CREATE DATABASE rosey_dev;
CREATE USER rosey WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE rosey_dev TO rosey;
\q

# Set environment variable
$env:DATABASE_URL = "postgresql+asyncpg://rosey:your_password@localhost/rosey_dev"
```

**Linux (Ubuntu/Debian)**:
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE rosey_dev;
CREATE USER rosey WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE rosey_dev TO rosey;
\q

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://rosey:your_password@localhost/rosey_dev"
```

**macOS (Homebrew)**:
```bash
# Install PostgreSQL
brew install postgresql@16
brew services start postgresql@16

# Create database
psql postgres
CREATE DATABASE rosey_dev;
CREATE USER rosey WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE rosey_dev TO rosey;
\q

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://rosey:your_password@localhost/rosey_dev"
```

---

### Method 3: Cloud PostgreSQL

**Providers**:
- AWS RDS for PostgreSQL
- Google Cloud SQL for PostgreSQL
- Azure Database for PostgreSQL
- DigitalOcean Managed PostgreSQL
- Heroku Postgres
- Supabase

**Example (AWS RDS)**:
```bash
# Connection string format
DATABASE_URL="postgresql+asyncpg://rosey:password@instance.region.rds.amazonaws.com:5432/rosey_production"

# With SSL (recommended)
DATABASE_URL="postgresql+asyncpg://rosey:password@instance.region.rds.amazonaws.com:5432/rosey_production?ssl=require"
```

**Security Considerations**:
- ✅ Use SSL/TLS for connections
- ✅ Restrict IP access (security groups)
- ✅ Use strong passwords (32+ characters)
- ✅ Store credentials in secrets manager
- ✅ Enable connection logging
- ✅ Regular automated backups

---

## Database URL Configuration

### Priority Order

Rosey Bot uses **12-factor app** configuration with this priority:

1. **Environment Variable**: `DATABASE_URL` (highest priority)
2. **Config File**: `config.json` → `database_url` field
3. **Config File (Legacy)**: `config.json` → `database` field (converted to SQLite URL)
4. **Default**: `sqlite+aiosqlite:///bot_data.db`

### Connection String Format

**PostgreSQL**:
```
postgresql+asyncpg://username:password@host:port/database

# Examples:
postgresql+asyncpg://rosey:password@localhost/rosey_dev
postgresql+asyncpg://rosey:password@localhost:5432/rosey_production
postgresql+asyncpg://rosey:password@postgres.example.com/rosey_db
```

**SQLite** (development/testing):
```
sqlite+aiosqlite:///relative/path/database.db
sqlite+aiosqlite:////absolute/path/database.db
sqlite+aiosqlite:///:memory:
```

### Setting Environment Variable

**Windows PowerShell** (current session):
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://rosey:password@localhost/rosey_dev"
```

**Windows PowerShell** (permanent):
```powershell
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql+asyncpg://rosey:password@localhost/rosey_dev', 'User')
```

**Linux/macOS** (current session):
```bash
export DATABASE_URL="postgresql+asyncpg://rosey:password@localhost/rosey_dev"
```

**Linux/macOS** (permanent):
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export DATABASE_URL="postgresql+asyncpg://rosey:password@localhost/rosey_dev"' >> ~/.bashrc
source ~/.bashrc
```

**systemd Service** (production):
```ini
[Service]
Environment="DATABASE_URL=postgresql+asyncpg://rosey:password@localhost/rosey_production"
```

---

## Connection Pooling

### Pool Configuration

Rosey Bot uses environment-aware connection pooling:

**Development** (`ROSEY_ENV=development` or not set):
- pool_size: 2
- max_overflow: 5
- Total: 2-7 connections

**Staging** (`ROSEY_ENV=staging`):
- pool_size: 5
- max_overflow: 10
- Total: 5-15 connections

**Production** (`ROSEY_ENV=production`):
- pool_size: 10
- max_overflow: 20
- Total: 10-30 connections

### Pool Settings

```python
# Automatic configuration in common/database.py
pool_timeout = 30        # Wait 30s for connection
pool_recycle = 3600      # Recycle connections every hour
pool_pre_ping = True     # Test connections before use
command_timeout = 60     # 60s statement timeout
```

### Setting Environment

```bash
# Development (default)
# No ROSEY_ENV needed

# Staging
export ROSEY_ENV=staging

# Production
export ROSEY_ENV=production
```

---

## Database Migrations

### Using Alembic

**Apply Migrations**:
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1
```

**Check Status**:
```bash
# Show current version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic show
```

**Create Migration**:
```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "Add new table"

# Manual migration
alembic revision -m "Add index on username"
```

### Migration Testing

**Test on SQLite First**:
```bash
# Use in-memory SQLite
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
alembic upgrade head
pytest tests/
```

**Test on PostgreSQL**:
```bash
# Use test database
export DATABASE_URL="postgresql+asyncpg://rosey:test_password@localhost/rosey_test"
alembic upgrade head
pytest tests/
```

---

## Backup and Restore

### PostgreSQL Backup

**Full Database Backup** (Docker):
```bash
# Backup to SQL file
docker-compose exec postgres pg_dump -U rosey rosey_dev > backup_$(date +%Y%m%d).sql

# Compressed backup
docker-compose exec postgres pg_dump -U rosey rosey_dev | gzip > backup_$(date +%Y%m%d).sql.gz
```

**Full Database Backup** (Manual):
```bash
# SQL format
pg_dump -U rosey -h localhost rosey_dev > backup.sql

# Custom format (compressed)
pg_dump -U rosey -h localhost -Fc rosey_dev > backup.dump
```

**Automated Backups**:
```bash
# Add to crontab (daily at 2am)
0 2 * * * pg_dump -U rosey rosey_production | gzip > /backups/rosey_$(date +\%Y\%m\%d).sql.gz
```

### PostgreSQL Restore

**From SQL Backup** (Docker):
```bash
# Restore to empty database
docker-compose exec -T postgres psql -U rosey rosey_dev < backup.sql

# Drop and recreate first
docker-compose exec postgres psql -U rosey -d postgres -c "DROP DATABASE rosey_dev;"
docker-compose exec postgres psql -U rosey -d postgres -c "CREATE DATABASE rosey_dev;"
docker-compose exec -T postgres psql -U rosey rosey_dev < backup.sql
```

**From SQL Backup** (Manual):
```bash
# Restore
psql -U rosey rosey_dev < backup.sql

# From compressed
gunzip -c backup.sql.gz | psql -U rosey rosey_dev
```

**From Custom Format**:
```bash
pg_restore -U rosey -d rosey_dev backup.dump
```

### SQLite to PostgreSQL Migration

**Export SQLite Data**:
```python
# Export script (export_sqlite.py)
import asyncio
from common.database import BotDatabase

async def export():
    db = BotDatabase('sqlite+aiosqlite:///bot_data.db')
    await db.connect()
    
    # Get all data
    users = await db.get_all_users()
    quotes = await db.get_all_quotes()
    # ... export other tables
    
    await db.close()
    
    # Save to JSON
    import json
    with open('export.json', 'w') as f:
        json.dump({
            'users': [u.dict() for u in users],
            'quotes': [q.dict() for q in quotes],
        }, f, indent=2)

asyncio.run(export())
```

**Import to PostgreSQL**:
```python
# Import script (import_postgres.py)
import asyncio
import json
from common.database import BotDatabase

async def import_data():
    db = BotDatabase('postgresql+asyncpg://rosey:password@localhost/rosey_dev')
    await db.connect()
    
    with open('export.json') as f:
        data = json.load(f)
    
    for user in data['users']:
        await db.user_joined(user['username'])
    
    for quote in data['quotes']:
        await db.add_quote(quote['username'], quote['quote'])
    
    await db.close()

asyncio.run(import_data())
```

---

## Troubleshooting

### Connection Refused

**Symptoms**:
```
psycopg.OperationalError: connection refused
```

**Solutions**:
```bash
# Check PostgreSQL running
docker-compose ps
# or
sudo systemctl status postgresql

# Check port 5432
netstat -an | grep 5432
# or
ss -tlnp | grep 5432

# Test connection
psql -U rosey -h localhost -d rosey_dev
```

### Authentication Failed

**Symptoms**:
```
psycopg.OperationalError: password authentication failed
```

**Solutions**:
```bash
# Verify credentials in docker-compose.yml
cat docker-compose.yml | grep POSTGRES_

# Reset password (Docker)
docker-compose exec postgres psql -U postgres
ALTER USER rosey WITH PASSWORD 'new_password';

# Update DATABASE_URL with correct password
```

### Pool Exhausted

**Symptoms**:
```
sqlalchemy.exc.TimeoutError: QueuePool limit reached
```

**Solutions**:
```bash
# Increase pool size
export ROSEY_ENV=production  # Uses 10+20 pool

# Or check for connection leaks in code
# Ensure all sessions use async context manager:
async with self._get_session() as session:
    # ... operations ...
    # Session automatically closed
```

### Migration Failed

**Symptoms**:
```
alembic.util.exc.CommandError: Can't locate revision
```

**Solutions**:
```bash
# Check current state
alembic current

# Stamp to specific revision
alembic stamp head

# Try upgrade again
alembic upgrade head

# If corrupted, reset (WARNING: deletes data)
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

### Slow Queries

**Symptoms**:
- Queries take >1 second
- High CPU usage on database

**Solutions**:
```sql
-- Enable query logging
ALTER DATABASE rosey_dev SET log_statement = 'all';
ALTER DATABASE rosey_dev SET log_min_duration_statement = 1000;

-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Add indexes (example)
CREATE INDEX idx_user_stats_username ON user_stats(username);
CREATE INDEX idx_chat_log_timestamp ON chat_log(timestamp);
```

---

## Performance Tuning

### PostgreSQL Configuration

**For Development** (docker-compose.yml):
```yaml
command:
  - "postgres"
  - "-c"
  - "shared_buffers=256MB"
  - "-c"
  - "work_mem=16MB"
  - "-c"
  - "maintenance_work_mem=128MB"
```

**For Production** (postgresql.conf):
```ini
# Memory
shared_buffers = 4GB              # 25% of RAM
effective_cache_size = 12GB       # 75% of RAM
work_mem = 64MB                   # Per query
maintenance_work_mem = 512MB      # For VACUUM, CREATE INDEX

# Connections
max_connections = 100             # Adjust based on pool size

# Checkpoints
checkpoint_timeout = 10min
checkpoint_completion_target = 0.9

# WAL
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB

# Logging
log_min_duration_statement = 1000  # Log slow queries >1s
```

### Connection Pooling Best Practices

**PgBouncer** (production recommendation):
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
rosey_production = host=localhost port=5432 dbname=rosey_production

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
```

**Update DATABASE_URL**:
```bash
# Connect through PgBouncer
DATABASE_URL="postgresql+asyncpg://rosey:password@localhost:6432/rosey_production"
```

---

## Monitoring

### Query Performance

**Enable pg_stat_statements**:
```sql
-- Add to postgresql.conf
shared_preload_libraries = 'pg_stat_statements'

-- Create extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View top queries
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### Connection Monitoring

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Connections by state
SELECT state, count(*) 
FROM pg_stat_activity 
GROUP BY state;

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '1 minute'
ORDER BY duration DESC;
```

### Database Size

```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('rosey_dev'));

-- Table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## CI/CD Integration

### GitHub Actions Matrix

```yaml
# .github/workflows/ci.yml (excerpt)
strategy:
  matrix:
    db: [sqlite, postgresql]

services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: rosey
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: rosey_test
    options: >-
      --health-cmd "pg_isready -U rosey"
      --health-interval 10s

steps:
  - name: Set DATABASE_URL
    run: |
      if [ "${{ matrix.db }}" = "postgresql" ]; then
        echo "DATABASE_URL=postgresql+asyncpg://rosey:test_password@localhost/rosey_test" >> $GITHUB_ENV
      fi
```

### Heroku Deployment

```bash
# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# Database URL automatically set
heroku config:get DATABASE_URL

# Run migrations
heroku run alembic upgrade head

# Check logs
heroku logs --tail
```

---

## Security Checklist

### Development
- [ ] Use strong passwords (not default)
- [ ] Don't commit credentials to git
- [ ] Use environment variables
- [ ] Restrict PostgreSQL to localhost

### Production
- [ ] Use SSL/TLS connections
- [ ] Rotate passwords regularly
- [ ] Use secrets manager (AWS Secrets Manager, etc.)
- [ ] Enable connection logging
- [ ] Restrict IP access (firewall/security groups)
- [ ] Regular automated backups
- [ ] Test backup restoration
- [ ] Monitor query performance
- [ ] Set up alerting (disk space, connections)
- [ ] Keep PostgreSQL updated

---

## Resources

### Documentation
- [PostgreSQL Official Docs](https://www.postgresql.org/docs/)
- [SQLAlchemy Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [asyncpg Driver](https://magicstack.github.io/asyncpg/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)

### Tools
- [pgAdmin](https://www.pgadmin.org/) - GUI management
- [psql](https://www.postgresql.org/docs/current/app-psql.html) - CLI client
- [PgBouncer](https://www.pgbouncer.org/) - Connection pooler
- [pg_stat_statements](https://www.postgresql.org/docs/current/pgstatstatements.html) - Query stats

### Related Guides
- [MIGRATIONS.md](MIGRATIONS.md) - Alembic migration workflow
- [SETUP.md](SETUP.md) - Local development setup
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TESTING.md](TESTING.md) - Testing guide
- [README.md](../README.md) - Main project documentation

---

**Document Version**: 1.0  
**Last Updated**: November 22, 2025  
**Maintained By**: Rosey-Robot Team
