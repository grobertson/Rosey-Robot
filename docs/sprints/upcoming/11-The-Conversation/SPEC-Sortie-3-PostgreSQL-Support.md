# Technical Specification: PostgreSQL Support & Testing

**Sprint**: Sprint 11 "The Conversation"  
**Sortie**: 3 of 4  
**Status**: Ready for Implementation  
**Estimated Effort**: 4-6 hours  
**Dependencies**: Sortie 1 (ORM models), Sortie 2 (BotDatabase migration)  
**Blocking**: Sortie 4 (documentation)  

---

## Overview

**Purpose**: Enable PostgreSQL production deployment by validating SQLAlchemy ORM works identically with both SQLite and PostgreSQL, adding CI matrix testing, implementing connection pooling, and documenting PostgreSQL setup.

**Scope**: 
- Set up local PostgreSQL testing environment (Docker)
- Validate all 1,198 tests pass with PostgreSQL
- Add GitHub Actions CI matrix (SQLite + PostgreSQL)
- Implement PostgreSQL connection pooling
- Document PostgreSQL deployment workflow
- Performance benchmarking (SQLite vs PostgreSQL)

**Non-Goals**: 
- PostgreSQL-specific features (FTS, JSON queries, etc.)
- MySQL/MariaDB support (Sprint 12+)
- Production PostgreSQL deployment (ops team)
- Schema optimization for PostgreSQL
- Multi-database write coordination

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: All 1,198 tests MUST pass with PostgreSQL  
**FR-002**: Test suite MUST run in CI for both SQLite and PostgreSQL  
**FR-003**: Connection pooling MUST be configured for PostgreSQL  
**FR-004**: Database URL MUST support PostgreSQL connection strings  
**FR-005**: Migration MUST work with PostgreSQL (Alembic upgrade)  
**FR-006**: Performance MUST be acceptable (within 2x of SQLite)  
**FR-007**: Documentation MUST cover PostgreSQL setup  

### 1.2 Non-Functional Requirements

**NFR-001**: CI matrix job completion <10 minutes per database  
**NFR-002**: PostgreSQL connection pool: 5-20 connections  
**NFR-003**: Connection retry logic for transient failures  
**NFR-004**: Graceful degradation if PostgreSQL unavailable  
**NFR-005**: Zero code changes between SQLite/PostgreSQL (config only)  

---

## 2. Problem Statement

### 2.1 Current Situation

**Database Support**: SQLite only (v0.5.0)  
**Testing**: Single database type in CI  
**Production Limitations**:
- Single-file database (no horizontal scaling)
- Limited concurrent writes (write serialization)
- No replication or high availability
- Backup requires file copy (downtime)

**SQLite Strengths** (keep for dev/test):
- Zero configuration
- File-based (portable)
- Fast for single-user scenarios
- Perfect for development/testing

**SQLite Weaknesses** (need PostgreSQL for production):
- Write lock contention under load
- No network access (single machine)
- Limited backup strategies
- No read replicas

### 2.2 PostgreSQL Benefits

**Production-Ready Features**:
- ✅ Concurrent writes (MVCC)
- ✅ Network access (multi-machine)
- ✅ Replication (streaming, logical)
- ✅ Hot backups (pg_dump, WAL archiving)
- ✅ Connection pooling (PgBouncer)
- ✅ Advanced indexing (GiST, GIN, BRIN)
- ✅ Full-text search (built-in)
- ✅ JSON/JSONB support
- ✅ Proven at scale (TB+ databases)

**Use Cases**:
- **Development/Test**: SQLite (fast, zero-config)
- **Staging**: PostgreSQL (prod-like)
- **Production**: PostgreSQL (HA, replication)
- **CI**: Both (matrix testing)

---

## 3. Detailed Design

### 3.1 Database URL Format

**SQLite** (development, testing):
```
sqlite+aiosqlite:///bot_data.db           # Relative path
sqlite+aiosqlite:////absolute/path/db.db  # Absolute path
sqlite+aiosqlite:///:memory:              # In-memory (tests)
```

**PostgreSQL** (staging, production):
```
postgresql+asyncpg://user:password@localhost/dbname
postgresql+asyncpg://user:password@localhost:5432/dbname
postgresql+asyncpg://user:password@postgres.example.com/rosey_db
```

**Environment Variable** (12-factor app):
```bash
export DATABASE_URL="postgresql+asyncpg://rosey:secret@localhost/rosey_db"
```

**Config Priority** (BotDatabase):
1. Environment variable: `DATABASE_URL`
2. Config file: `config.json` → `database_url`
3. Config file (legacy): `config.json` → `database` (converted to SQLite URL)
4. Default: `sqlite+aiosqlite:///bot_data.db`

### 3.2 PostgreSQL Connection Pooling

**SQLAlchemy Pool Settings** (production-optimized):

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    database_url,
    
    # Connection pool settings
    pool_size=10,              # Min persistent connections
    max_overflow=20,           # Max additional connections
    pool_timeout=30,           # Wait 30s for connection
    pool_recycle=3600,         # Recycle connections every hour
    pool_pre_ping=True,        # Test connections before use
    
    # PostgreSQL-specific settings
    connect_args={
        'server_settings': {
            'application_name': 'rosey-bot',
            'jit': 'off',      # Disable JIT for short queries
        },
        'command_timeout': 60,  # 60s statement timeout
    } if database_url.startswith('postgresql') else {},
    
    # Logging
    echo=False,                # Set True to log all queries
    echo_pool=False,           # Set True to log pool operations
)
```

**Pool Sizing Guidelines**:
- **Development**: pool_size=2, max_overflow=5
- **Staging**: pool_size=5, max_overflow=10
- **Production**: pool_size=10, max_overflow=20
- **Formula**: pool_size = (concurrent_requests * 2) + overflow

**Connection Lifecycle**:
1. Request arrives
2. Acquire connection from pool
3. Execute query
4. Return connection to pool
5. Pool pre-pings before reuse

### 3.3 CI Matrix Strategy

**GitHub Actions Matrix**:

```yaml
jobs:
  test:
    name: Test (${{ matrix.db }})
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        db: [sqlite, postgresql]
      fail-fast: false  # Continue other DBs if one fails
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
      
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: rosey
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: rosey_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U rosey"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Set DATABASE_URL
        run: |
          if [ "${{ matrix.db }}" = "postgresql" ]; then
            echo "DATABASE_URL=postgresql+asyncpg://rosey:test_password@localhost/rosey_test" >> $GITHUB_ENV
          else
            echo "DATABASE_URL=sqlite+aiosqlite:///:memory:" >> $GITHUB_ENV
          fi
      
      - name: Run Alembic migrations
        run: |
          alembic upgrade head
      
      - name: Run tests
        run: |
          pytest tests/ -v --cov=common --cov=lib
        env:
          NATS_URL: nats://localhost:4222
      
      - name: Check coverage
        run: |
          coverage report --fail-under=66
```

**Matrix Benefits**:
- Tests both databases on every PR
- Catches database-specific bugs early
- Validates Alembic migrations work on both
- Ensures performance acceptable on both

---

## 4. Implementation Changes

### Change 1: Update BotDatabase Connection Pooling

**File**: `common/database.py`  
**Location**: `__init__` method (pool configuration)  

**Current Code** (Sortie 2):
```python
self.engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
```

**New Code** (Sortie 3 - environment-aware):
```python
# Determine if PostgreSQL
is_postgresql = database_url.startswith('postgresql')

# Pool settings based on environment
if 'ROSEY_ENV' in os.environ:
    env = os.environ['ROSEY_ENV'].lower()
    if env == 'production':
        pool_size, max_overflow = 10, 20
    elif env == 'staging':
        pool_size, max_overflow = 5, 10
    else:  # development
        pool_size, max_overflow = 2, 5
else:
    # Default: moderate pool
    pool_size, max_overflow = 5, 10

# PostgreSQL-specific connection args
connect_args = {}
if is_postgresql:
    connect_args = {
        'server_settings': {
            'application_name': 'rosey-bot',
            'jit': 'off',  # Disable JIT for short queries
        },
        'command_timeout': 60,  # Statement timeout
    }

self.engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=pool_size,
    max_overflow=max_overflow,
    pool_timeout=30,
    pool_recycle=3600,  # Recycle connections every hour
    connect_args=connect_args,
)

self.logger.info(
    'Database engine initialized: %s (pool: %d+%d)',
    'PostgreSQL' if is_postgresql else 'SQLite',
    pool_size,
    max_overflow
)
```

**Rationale**: Environment-aware pooling, PostgreSQL optimizations

---

### Change 2: Add Database URL Environment Variable Support

**File**: `common/config.py` (or wherever config loading happens)  
**New Function**: `get_database_url()`  

**Implementation**:
```python
import os
from pathlib import Path

def get_database_url(config: dict) -> str:
    """
    Get database URL with priority:
    1. Environment variable DATABASE_URL
    2. Config file database_url field
    3. Config file database field (legacy, converted)
    4. Default SQLite
    
    Args:
        config: Loaded configuration dict
    
    Returns:
        SQLAlchemy database URL
    
    Examples:
        >>> os.environ['DATABASE_URL'] = 'postgresql://...'
        >>> get_database_url({})
        'postgresql://...'
        
        >>> get_database_url({'database_url': 'sqlite+aiosqlite:///db.db'})
        'sqlite+aiosqlite:///db.db'
        
        >>> get_database_url({'database': 'bot_data.db'})
        'sqlite+aiosqlite:///bot_data.db'
    """
    # 1. Environment variable (highest priority)
    if 'DATABASE_URL' in os.environ:
        url = os.environ['DATABASE_URL']
        
        # Ensure async drivers
        if url.startswith('sqlite:///'):
            url = url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        elif url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+asyncpg://')
        
        return url
    
    # 2. Config file database_url field
    if 'database_url' in config:
        return config['database_url']
    
    # 3. Legacy database field (v0.5.0 compatibility)
    if 'database' in config:
        db_path = config['database']
        # Convert path to URL
        if db_path == ':memory:':
            return 'sqlite+aiosqlite:///:memory:'
        else:
            return f'sqlite+aiosqlite:///{db_path}'
    
    # 4. Default
    return 'sqlite+aiosqlite:///bot_data.db'
```

**Usage in BotDatabase**:
```python
from common.config import get_database_url

# In __init__
config = load_config()  # Your config loading
database_url = get_database_url(config)
self.engine = create_async_engine(database_url, ...)
```

**Rationale**: 12-factor app pattern, environment variable priority

---

### Change 3: Update CI Workflow (Matrix Testing)

**File**: `.github/workflows/ci.yml`  
**Section**: `test` job  

**Current Code** (single database):
```yaml
  test:
    name: Test
    runs-on: ubuntu-latest
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
```

**New Code** (matrix with both databases):
```yaml
  test:
    name: Test (${{ matrix.db }})
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        db: [sqlite, postgresql]
      fail-fast: false  # Continue testing other DBs if one fails
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
        options: >-
          --health-cmd "wget --no-verbose --tries=1 --spider http://localhost:8222/healthz || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: rosey
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: rosey_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U rosey"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov pytest-asyncio
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      
      - name: Set DATABASE_URL for matrix
        run: |
          if [ "${{ matrix.db }}" = "postgresql" ]; then
            echo "DATABASE_URL=postgresql+asyncpg://rosey:test_password@localhost/rosey_test" >> $GITHUB_ENV
          else
            echo "DATABASE_URL=sqlite+aiosqlite:///:memory:" >> $GITHUB_ENV
          fi
      
      - name: Run Alembic migrations
        run: |
          alembic upgrade head
        env:
          DATABASE_URL: ${{ env.DATABASE_URL }}
      
      - name: Run tests
        run: |
          pytest tests/ --cov=lib --cov=common --cov-report=term-missing --cov-report=xml
        env:
          NATS_URL: nats://localhost:4222
          DATABASE_URL: ${{ env.DATABASE_URL }}
      
      - name: Check coverage
        run: |
          coverage report --fail-under=66
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: ${{ matrix.db }}
          name: codecov-${{ matrix.db }}
        continue-on-error: true
```

**Rationale**: Matrix testing catches database-specific issues early

---

### Change 4: Add PostgreSQL Docker Compose (Local Development)

**File**: `docker-compose.yml` (NEW)  
**Location**: Project root  

**Complete File**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: rosey-postgres
    environment:
      POSTGRES_USER: rosey
      POSTGRES_PASSWORD: rosey_dev_password
      POSTGRES_DB: rosey_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rosey"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
  
  nats:
    image: nats:2.10-alpine
    container_name: rosey-nats
    ports:
      - "4222:4222"
      - "8222:8222"
    command: ["-js", "-m", "8222"]
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8222/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
  
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: rosey-pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@rosey.local
      PGADMIN_DEFAULT_PASSWORD: admin
      PGADMIN_CONFIG_SERVER_MODE: 'False'
    ports:
      - "5050:80"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
  pgadmin_data:
```

**Usage**:
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f postgres

# Stop services
docker-compose down

# Reset database (WARNING: deletes data)
docker-compose down -v
docker-compose up -d
```

**Rationale**: Easy local PostgreSQL setup for development/testing

---

### Change 5: Create PostgreSQL Initialization Script

**File**: `scripts/init_postgres.sql` (NEW)  
**Location**: `scripts/`  

**Complete Script**:
```sql
-- PostgreSQL initialization script for Rosey Bot
-- Runs automatically via docker-compose on first startup

-- Create extensions (if needed in future)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Trigram similarity for FTS
-- CREATE EXTENSION IF NOT EXISTS btree_gin;  -- GIN indexes on scalar types

-- Set timezone (optional)
SET timezone = 'UTC';

-- Grant privileges (already done by POSTGRES_USER, but explicit)
GRANT ALL PRIVILEGES ON DATABASE rosey_dev TO rosey;

-- Performance tuning for development (optional)
ALTER DATABASE rosey_dev SET log_statement = 'all';  -- Log all statements
ALTER DATABASE rosey_dev SET log_duration = on;      -- Log query duration

-- Tables are created by Alembic migrations (not here)
-- Run: alembic upgrade head

-- Print confirmation
SELECT 'PostgreSQL initialized for Rosey Bot' AS status;
```

**Rationale**: Consistent PostgreSQL setup across environments

---

### Change 6: Add PostgreSQL Test Fixtures

**File**: `tests/conftest.py`  
**New Fixtures**: `postgres_database`, `database_url`  

**Additions**:
```python
import os
import pytest
from common.database import BotDatabase

@pytest.fixture(scope='session')
def database_url():
    """
    Get database URL from environment or use in-memory SQLite.
    
    Usage in CI:
        DATABASE_URL=postgresql://... pytest tests/
    
    Usage locally:
        pytest tests/  # Uses SQLite in-memory
    """
    return os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


@pytest.fixture
async def postgres_database(database_url):
    """
    Create temporary PostgreSQL database for testing.
    
    Only used when DATABASE_URL points to PostgreSQL.
    Creates tables via Alembic, cleans up after test.
    """
    if not database_url.startswith('postgresql'):
        pytest.skip('PostgreSQL tests require DATABASE_URL=postgresql://...')
    
    db = BotDatabase(database_url)
    await db.connect()
    
    # Run migrations
    import subprocess
    result = subprocess.run(
        ['alembic', 'upgrade', 'head'],
        capture_output=True,
        env={**os.environ, 'DATABASE_URL': database_url}
    )
    if result.returncode != 0:
        raise RuntimeError(f'Alembic migration failed: {result.stderr}')
    
    yield db
    
    # Cleanup
    await db.close()
    
    # Drop all tables (reset for next test)
    from sqlalchemy import text
    async with db.engine.begin() as conn:
        await conn.execute(text('DROP SCHEMA public CASCADE'))
        await conn.execute(text('CREATE SCHEMA public'))


@pytest.fixture
async def database(database_url):
    """
    Generic database fixture (works with SQLite or PostgreSQL).
    
    Automatically detects database type from DATABASE_URL.
    """
    db = BotDatabase(database_url)
    await db.connect()
    
    # Run migrations if PostgreSQL
    if database_url.startswith('postgresql'):
        import subprocess
        subprocess.run(['alembic', 'upgrade', 'head'], check=True)
    
    yield db
    
    await db.close()
```

**Rationale**: Test fixtures work with both databases transparently

---

## 5. Testing Strategy

### 5.1 Local PostgreSQL Testing

**Setup** (one-time):
```bash
# Start PostgreSQL via Docker
docker-compose up -d postgres

# Wait for ready
docker-compose logs -f postgres | grep "ready"

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"

# Run migrations
alembic upgrade head
```

**Run Tests**:
```bash
# All tests with PostgreSQL
pytest tests/ -v

# Specific test suite
pytest tests/unit/test_database.py -v

# With coverage
pytest tests/ --cov=common --cov-report=html

# Performance benchmarks
pytest tests/performance/ -v --benchmark-only
```

**Verify Results**:
```bash
# All 1,198 tests should pass
# Coverage should be ≥66%
# No PostgreSQL-specific errors
```

### 5.2 CI Matrix Testing

**Trigger**:
- Every push to main or nano-sprint branches
- Every pull request
- Manual workflow dispatch

**Matrix Jobs**:
1. **test (sqlite)**: Tests with SQLite in-memory
2. **test (postgresql)**: Tests with PostgreSQL 16

**Expected Results**:
- Both jobs pass (green checkmarks)
- Coverage ≥66% on both
- Total time <10 minutes per job

**Debugging Failures**:
```bash
# Check CI logs for specific database
gh run view --log | grep -A 20 "matrix.db: postgresql"

# Reproduce locally
export DATABASE_URL="postgresql+asyncpg://rosey:test_password@localhost/rosey_test"
pytest tests/ -v
```

### 5.3 Performance Benchmarking

**File**: `tests/performance/test_database_comparison.py` (NEW)

**Benchmark Tests**:
```python
import pytest
import time
from common.database import BotDatabase

@pytest.mark.benchmark
@pytest.mark.parametrize('database_url', [
    'sqlite+aiosqlite:///:memory:',
    'postgresql+asyncpg://rosey:password@localhost/rosey_bench',
])
@pytest.mark.asyncio
async def test_insert_performance(database_url, benchmark):
    """Compare insert performance (SQLite vs PostgreSQL)"""
    db = BotDatabase(database_url)
    await db.connect()
    
    async def operation():
        await db.user_joined(f'User{time.time()}')
    
    result = await benchmark.pedantic(operation, iterations=100, rounds=10)
    
    # Log results
    print(f'{database_url}: {result.stats.mean:.4f}s mean')
    
    await db.close()


@pytest.mark.benchmark
@pytest.mark.parametrize('database_url', [
    'sqlite+aiosqlite:///:memory:',
    'postgresql+asyncpg://rosey:password@localhost/rosey_bench',
])
@pytest.mark.asyncio
async def test_query_performance(database_url, benchmark):
    """Compare query performance (SQLite vs PostgreSQL)"""
    db = BotDatabase(database_url)
    await db.connect()
    
    # Setup: 1000 users
    for i in range(1000):
        await db.user_joined(f'User{i}')
    
    async def operation():
        await db.get_top_chatters(10)
    
    result = await benchmark.pedantic(operation, iterations=100, rounds=10)
    
    print(f'{database_url}: {result.stats.mean:.4f}s mean')
    
    await db.close()
```

**Run Benchmarks**:
```bash
# Compare both databases
pytest tests/performance/test_database_comparison.py --benchmark-only

# Expected results:
# SQLite insert: ~2-5ms
# PostgreSQL insert: ~5-10ms
# SQLite query: ~5-10ms
# PostgreSQL query: ~10-20ms
# Ratio: PostgreSQL ~2x slower (acceptable for ACID guarantees)
```

### 5.4 Migration Testing

**Test Scenarios**:

**Scenario 1: Fresh PostgreSQL Database**
```bash
# Start fresh PostgreSQL
docker-compose down -v
docker-compose up -d postgres

# Run migrations
export DATABASE_URL="postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"
alembic upgrade head

# Verify tables created
psql postgresql://rosey:rosey_dev_password@localhost/rosey_dev -c "\dt"

# Should show all 8 tables
```

**Scenario 2: Migration Rollback**
```bash
# Downgrade
alembic downgrade -1

# Check state
alembic current

# Re-upgrade
alembic upgrade head

# Verify idempotent
```

**Scenario 3: Data Preservation**
```bash
# Insert test data
python -c "
from common.database import BotDatabase
import asyncio

async def test():
    db = BotDatabase('postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev')
    await db.connect()
    await db.user_joined('TestUser')
    print('User created')
    await db.close()

asyncio.run(test())
"

# Run migration (no-op if up-to-date)
alembic upgrade head

# Verify data intact
psql postgresql://rosey:rosey_dev_password@localhost/rosey_dev \
  -c "SELECT username FROM user_stats WHERE username = 'TestUser';"

# Should return: TestUser
```

---

## 6. Implementation Steps

### Phase 1: Local Setup (1 hour)

1. ✅ Create `docker-compose.yml` (PostgreSQL + NATS + pgAdmin)
2. ✅ Create `scripts/init_postgres.sql` (initialization)
3. ✅ Start services: `docker-compose up -d`
4. ✅ Verify PostgreSQL: `docker-compose ps`
5. ✅ Test connection: `psql postgresql://rosey:rosey_dev_password@localhost/rosey_dev`

### Phase 2: Code Changes (1-2 hours)

6. ✅ Update `common/config.py` (add `get_database_url()`)
7. ✅ Update `common/database.py` (environment-aware pooling)
8. ✅ Update `tests/conftest.py` (PostgreSQL fixtures)
9. ✅ Test locally: `export DATABASE_URL=postgresql://...` then `pytest tests/ -v`

### Phase 3: CI Integration (1 hour)

10. ✅ Update `.github/workflows/ci.yml` (add matrix)
11. ✅ Add PostgreSQL service to CI
12. ✅ Set DATABASE_URL per matrix job
13. ✅ Test CI: Push branch, check Actions
14. ✅ Verify both matrix jobs pass

### Phase 4: Performance Validation (1-2 hours)

15. ✅ Create `tests/performance/test_database_comparison.py`
16. ✅ Run benchmarks locally (SQLite vs PostgreSQL)
17. ✅ Document results (acceptable performance)
18. ✅ Add performance tests to CI (optional, can be slow)

### Phase 5: Documentation (30 minutes)

19. ✅ Create `docs/DATABASE_SETUP.md` (PostgreSQL guide)
20. ✅ Update `docs/SETUP.md` (local development with PostgreSQL)
21. ✅ Update `docs/ARCHITECTURE.md` (database section)
22. ✅ Update `README.md` (PostgreSQL support note)

### Phase 6: Final Validation (30 minutes)

23. ✅ Clean environment: `docker-compose down -v`
24. ✅ Fresh start: `docker-compose up -d`
25. ✅ Migrations: `alembic upgrade head`
26. ✅ All tests: `pytest tests/ -v`
27. ✅ Coverage: `pytest tests/ --cov=common --cov-report=html`
28. ✅ Commit: "Sprint 11 Sortie 3: PostgreSQL support and CI matrix"

---

## 7. Acceptance Criteria

### 7.1 Local PostgreSQL Working

- [ ] Docker Compose starts PostgreSQL successfully
- [ ] Can connect: `psql postgresql://rosey:rosey_dev_password@localhost/rosey_dev`
- [ ] Alembic migrations apply: `alembic upgrade head`
- [ ] All 1,198 tests pass with PostgreSQL
- [ ] pgAdmin accessible at http://localhost:5050

### 7.2 CI Matrix Passing

- [ ] CI has matrix with sqlite + postgresql
- [ ] Both matrix jobs pass (green)
- [ ] PostgreSQL service healthy in CI
- [ ] Migrations run successfully in CI
- [ ] Coverage ≥66% on both databases
- [ ] Total CI time <20 minutes (both jobs)

### 7.3 Performance Acceptable

- [ ] Benchmark tests created
- [ ] SQLite insert: <5ms average
- [ ] PostgreSQL insert: <10ms average
- [ ] SQLite query: <10ms average
- [ ] PostgreSQL query: <20ms average
- [ ] PostgreSQL within 2x of SQLite (acceptable)

### 7.4 Documentation Complete

- [ ] `docs/DATABASE_SETUP.md` created (PostgreSQL setup)
- [ ] `docs/SETUP.md` updated (local development)
- [ ] `docs/ARCHITECTURE.md` updated (database options)
- [ ] `README.md` mentions PostgreSQL support
- [ ] Docker Compose documented

### 7.5 Code Quality

- [ ] No hardcoded credentials
- [ ] Environment variables used correctly
- [ ] Connection pooling configured
- [ ] Error handling for connection failures
- [ ] Logging includes database type

---

## 8. Deliverables

### 8.1 Code Changes

**Modified Files**:
- `common/database.py` - Environment-aware pooling
- `common/config.py` - `get_database_url()` function
- `tests/conftest.py` - PostgreSQL fixtures
- `.github/workflows/ci.yml` - Matrix testing

**New Files**:
- `docker-compose.yml` - Local services (PostgreSQL, NATS, pgAdmin)
- `scripts/init_postgres.sql` - PostgreSQL initialization
- `tests/performance/test_database_comparison.py` - Benchmarks (~150 lines)

### 8.2 Documentation

**New**:
- `docs/DATABASE_SETUP.md` - PostgreSQL setup guide (~200 lines)

**Updated**:
- `docs/SETUP.md` - Local development section
- `docs/ARCHITECTURE.md` - Database options
- `README.md` - PostgreSQL support note

### 8.3 CI Configuration

- GitHub Actions matrix (SQLite + PostgreSQL)
- PostgreSQL service container
- Alembic migrations in CI
- Database-specific environment variables

---

## 9. Related Issues

**Depends On**:
- Sprint 11 Sortie 1 (ORM models)
- Sprint 11 Sortie 2 (BotDatabase migration)

**Blocks**:
- Sortie 4: Documentation and deployment

**Related**:
- Sprint 10 complete (async database)
- Sprint 11 PRD: PostgreSQL support goal

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tests Passing (SQLite) | 1,198/1,198 | CI logs |
| Tests Passing (PostgreSQL) | 1,198/1,198 | CI logs |
| CI Matrix Jobs | 2/2 passing | GitHub Actions |
| Performance Ratio | PostgreSQL ≤2x SQLite | Benchmarks |
| Coverage (both DBs) | ≥66% | pytest-cov |

---

## Appendix A: PostgreSQL Connection Strings

### Local Development
```bash
# Docker Compose
DATABASE_URL="postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"

# Manual install
DATABASE_URL="postgresql+asyncpg://rosey:mypassword@localhost/rosey_db"

# Custom port
DATABASE_URL="postgresql+asyncpg://rosey:password@localhost:5433/rosey_db"
```

### CI/Testing
```bash
# GitHub Actions
DATABASE_URL="postgresql+asyncpg://rosey:test_password@localhost/rosey_test"

# In-memory SQLite (tests)
DATABASE_URL="sqlite+aiosqlite:///:memory:"
```

### Production
```bash
# Cloud provider (example)
DATABASE_URL="postgresql+asyncpg://rosey:$POSTGRES_PASSWORD@postgres.example.com/rosey_production"

# Connection pooling via PgBouncer
DATABASE_URL="postgresql+asyncpg://rosey:password@pgbouncer.example.com:6432/rosey_db"

# SSL enabled
DATABASE_URL="postgresql+asyncpg://rosey:password@postgres.example.com/rosey_db?ssl=require"
```

---

## Appendix B: PostgreSQL Quick Reference

### Docker Commands
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f postgres

# Connect to PostgreSQL
docker-compose exec postgres psql -U rosey -d rosey_dev

# Stop services
docker-compose down

# Reset database (delete data)
docker-compose down -v
```

### psql Commands
```sql
-- List databases
\l

-- Connect to database
\c rosey_dev

-- List tables
\dt

-- Describe table
\d user_stats

-- Show table size
SELECT pg_size_pretty(pg_total_relation_size('user_stats'));

-- Show active connections
SELECT * FROM pg_stat_activity WHERE datname = 'rosey_dev';

-- Kill connection
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = 12345;
```

### Backup/Restore
```bash
# Backup database
docker-compose exec postgres pg_dump -U rosey rosey_dev > backup.sql

# Restore database
docker-compose exec -T postgres psql -U rosey rosey_dev < backup.sql

# Backup with Docker volume
docker run --rm -v rosey-robot_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data
```

---

## Appendix C: Troubleshooting

### Issue: Tests fail with PostgreSQL but pass with SQLite

**Symptoms**:
```
AssertionError: Expected 10, got 0
```

**Cause**: Data not committed or transaction isolation

**Fix**: Ensure session commits in `_get_session()`:
```python
async with self._get_session() as session:
    # ... operations ...
    # Commit happens automatically on context exit
```

### Issue: Connection pool exhausted

**Symptoms**:
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached
```

**Cause**: Too many concurrent connections

**Fix**: Increase pool size or fix connection leaks:
```python
# Increase pool
pool_size=20, max_overflow=40

# Find leaks (ensure all sessions closed)
async with self._get_session() as session:
    # Session automatically closed here
```

### Issue: Alembic migration fails on PostgreSQL

**Symptoms**:
```
alembic.util.exc.CommandError: Can't locate revision identified by '<hash>'
```

**Cause**: Migration history out of sync

**Fix**: Reset migration state:
```bash
# Check current state
alembic current

# Stamp to specific revision
alembic stamp head

# Try upgrade again
alembic upgrade head
```

### Issue: CI PostgreSQL service not ready

**Symptoms**:
```
psycopg2.OperationalError: could not connect to server
```

**Cause**: Tests run before PostgreSQL fully ready

**Fix**: Add health check to CI (already in SPEC):
```yaml
options: >-
  --health-cmd "pg_isready -U rosey"
  --health-interval 10s
  --health-timeout 5s
  --health-retries 5
```

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for Implementation ✅

**Next Steps**:
1. Create `docker-compose.yml` (PostgreSQL + NATS + pgAdmin)
2. Start services: `docker-compose up -d`
3. Update `common/database.py` (environment-aware pooling)
4. Update `common/config.py` (DATABASE_URL environment variable)
5. Update `.github/workflows/ci.yml` (add matrix)
6. Test locally with PostgreSQL: `pytest tests/ -v`
7. Push to trigger CI matrix
8. Verify both SQLite and PostgreSQL jobs pass
9. Create performance benchmarks
10. Commit: "Sprint 11 Sortie 3: PostgreSQL support + CI matrix"

---

**"In the matrix, you test both realities. One is comfortable (SQLite). The other reveals the truth (PostgreSQL). Take both pills."** 🎬
