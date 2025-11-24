# Product Requirements Document: SQLAlchemy Migration

**Sprint**: Sprint 11 "The Conversation"  
**Status**: Planning  
**Version**: v0.6.0  
**Created**: November 21, 2025  
**Target Completion**: 2-3 days  
**Dependencies**: Sprint 10 (Test Infrastructure Complete)  

---

## Executive Summary

**Mission**: Migrate Rosey's database layer from raw `sqlite3` to **SQLAlchemy ORM** with **Alembic** migrations, enabling database portability (SQLite, PostgreSQL, MySQL) and improved developer experience through type-safe models and schema versioning.

**Why Now**: Sprint 10 completes test infrastructure with full NATS event bus integration. The database layer is stable, well-tested (66%+ coverage), and ready for modernization. SQLAlchemy provides the abstraction needed for production deployments requiring PostgreSQL/MySQL.

**Business Value**:
- **🚀 Production Ready**: PostgreSQL support for multi-bot high-availability deployments
- **🔧 Developer Experience**: Type-safe ORM models, IDE autocomplete, Pythonic queries
- **📊 Schema Versioning**: Alembic migrations for controlled database evolution
- **🧪 Better Testing**: Mock ORM models instead of database connections
- **🔄 Database Portability**: Switch SQLite → PostgreSQL → MySQL with config change

**Success Criteria**: All tests pass with SQLAlchemy, zero functional regressions, schema migrations working, PostgreSQL verified.

---

## 1. Problem Statement

### 1.1 Current State

**Database Implementation**: `common/database.py` (938 lines)
- Direct `sqlite3` library usage
- Raw SQL queries (`CREATE TABLE`, `INSERT`, `SELECT`)
- Parameterized queries (SQL injection safe ✅)
- 8 tables: user_stats, user_actions, channel_stats, user_count_history, recent_chat, current_status, outbound_messages, api_tokens
- Synchronous operations (to be async in Sprint 10 Sortie 1)

**Limitations**:

1. **No Database Portability**: Switching to PostgreSQL/MySQL requires:
   - Rewriting all SQL queries (30+ locations)
   - Handling dialect differences (AUTO_INCREMENT, SERIAL, etc.)
   - Testing against multiple databases
   - Estimated effort: 3-5 days per database

2. **No Schema Versioning**: Database schema changes require:
   - Manual ALTER TABLE statements
   - No rollback capability
   - No migration history
   - Difficult to synchronize dev/staging/production schemas

3. **Limited Type Safety**: SQL queries are strings
   - No compile-time validation
   - Typos discovered at runtime
   - IDE can't autocomplete table/column names
   - Refactoring is error-prone

4. **Testing Complexity**: Tests mock database connections
   - Hard to create test fixtures
   - Brittle tests (sensitive to SQL query changes)
   - No easy way to test schema migrations

5. **Production Concerns**:
   - SQLite file locking issues with multiple processes
   - No built-in replication
   - Limited concurrent write performance
   - Not suitable for high-availability deployments

### 1.2 User Impact

**Development Teams**:
- ❌ Slow onboarding (need to learn raw SQL patterns)
- ❌ Error-prone refactoring (string-based queries)
- ❌ Difficult schema evolution (manual migrations)
- ❌ Complex testing setup

**Operations Teams**:
- ❌ Can't use PostgreSQL for production (high availability)
- ❌ No migration rollback capability
- ❌ Difficult to replicate databases
- ❌ SQLite limitations for scale

**Bot Users**:
- ⚠️ Potential downtime during schema changes (no migrations)
- ⚠️ Limited scalability (SQLite bottlenecks)

### 1.3 Why This Matters

**Strategic Alignment**: Sprint 9 (NATS) + Sprint 10 (Test Infrastructure) positioned Rosey as a production-ready bot platform. SQLAlchemy completes the foundation by enabling **enterprise database backends** (PostgreSQL) while maintaining the **developer-friendly SQLite** experience.

**Technical Debt**: Current raw SQL approach is **maintainable but not scalable**. Adding new tables/columns requires manual SQL in multiple places. Schema evolution is risky without migrations.

**Market Requirements**: Production deployments demand PostgreSQL for:
- High availability (replication, failover)
- Multi-bot architectures (shared database)
- Compliance (audit logs, backups, point-in-time recovery)
- Performance (concurrent writes, indexing, query optimization)

---

## 2. Goals and Non-Goals

### 2.1 Goals

**Primary Goals**:

1. **ORM Migration**: Replace all raw `sqlite3` calls with SQLAlchemy ORM
   - Define 8 ORM models (UserStats, UserActions, ChannelStats, etc.)
   - Replace all `cursor.execute()` with ORM queries
   - Maintain identical functionality (zero regressions)

2. **Schema Migrations**: Implement Alembic for version control
   - Generate initial migration from current schema
   - Add migration commands to setup scripts
   - Document migration workflow

3. **Database Portability**: Support SQLite + PostgreSQL
   - Configuration-based database URL (`sqlite://` or `postgresql://`)
   - Test suite runs against both databases
   - Document deployment options

4. **Type Safety**: Leverage Python type hints + ORM models
   - IDE autocomplete for tables/columns
   - Runtime validation of data types
   - Better refactoring support

5. **Async Support**: Use `sqlalchemy.ext.asyncio` (aligns with Sprint 10 Sortie 1)
   - Async session management
   - Compatible with async NATS handlers
   - Non-blocking database operations

**Secondary Goals**:

6. **Testing Improvements**: Simplify test fixtures
   - Mock ORM models instead of connections
   - Faster test execution (in-memory SQLite)
   - Cleaner test isolation

7. **Developer Experience**: Better code maintainability
   - Pythonic query syntax (no SQL strings)
   - Clear model definitions (self-documenting)
   - Reduced boilerplate

8. **Production Readiness**: PostgreSQL deployment guide
   - Connection pooling configuration
   - Replication setup
   - Backup/restore procedures

### 2.2 Non-Goals

**Explicitly Out of Scope**:

1. **Schema Changes**: No new tables/columns (keep v0.5.0 schema)
2. **Data Migration**: No data transformations (straight migration)
3. **Query Optimization**: No performance tuning (future sprint)
4. **MySQL Support**: Focus SQLite + PostgreSQL (MySQL in v0.7.0+)
5. **Multi-Database**: No sharding/federation (single database only)
6. **ORM Features**: No relationships, lazy loading (keep simple)
7. **API Changes**: No changes to database method signatures
8. **UI/UX**: No user-facing changes

---

## 3. Success Metrics

### 3.1 Functional Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Pass Rate | 100% (1,198 tests) | `pytest -v` |
| Code Coverage | ≥66% (maintain current) | `pytest --cov` |
| Functional Regressions | 0 | Manual testing + CI |
| Migration Success | 100% (dev → prod) | Alembic upgrade/downgrade |

### 3.2 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Database Backends | 2 (SQLite + PostgreSQL) | CI matrix testing |
| ORM Models | 8 (all tables) | Code review |
| Type Hints | 100% (all models/methods) | mypy validation |
| Async Support | 100% (all operations) | Async/await usage |
| Migration History | Complete (v0.5.0 → v0.6.0) | Alembic history |

### 3.3 Developer Experience Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| LOC Reduction | -10% (less boilerplate) | Git diff |
| Type Safety | 100% (mypy clean) | `mypy common/` |
| Setup Time | <5 minutes (Alembic init) | Onboarding test |
| Query Readability | +50% (Pythonic vs SQL) | Code review |

### 3.4 Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Query Performance | ±5% (no regressions) | Performance tests |
| Test Suite Time | ±10% (no slowdown) | CI timing |
| Database Init Time | ±5% (migrations) | Startup benchmark |

---

## 4. User Stories

### 4.1 Developer Stories

**Story 1: Type-Safe Queries**
```
AS A developer
I WANT ORM models with type hints
SO THAT I get IDE autocomplete and catch errors at development time

ACCEPTANCE CRITERIA:
- All database models have type hints
- IDE autocompletes table/column names
- mypy validates types at pre-commit
- Refactoring is safer (renames update all references)
```

**Story 2: Schema Evolution**
```
AS A developer
I WANT Alembic migrations
SO THAT I can version control schema changes and roll back if needed

ACCEPTANCE CRITERIA:
- `alembic upgrade head` applies migrations
- `alembic downgrade -1` rolls back changes
- `alembic history` shows migration timeline
- Migrations documented in version control
```

**Story 3: Pythonic Queries**
```
AS A developer
I WANT to write queries in Python
SO THAT I don't context-switch between Python and SQL

BEFORE (raw SQL):
    cursor.execute('''
        SELECT * FROM user_stats WHERE username = ?
    ''', (username,))

AFTER (SQLAlchemy):
    session.query(UserStats).filter_by(username=username).first()

ACCEPTANCE CRITERIA:
- All queries use ORM syntax
- No raw SQL strings in code
- Queries are composable/reusable
```

### 4.2 Operations Stories

**Story 4: PostgreSQL Deployment**
```
AS AN operations engineer
I WANT to deploy Rosey with PostgreSQL
SO THAT I can run multiple bots with high availability

ACCEPTANCE CRITERIA:
- config.json supports postgres:// URLs
- Bot connects to PostgreSQL successfully
- All tests pass against PostgreSQL
- Deployment guide includes PostgreSQL setup
```

**Story 5: Migration Rollback**
```
AS AN operations engineer
I WANT to roll back failed migrations
SO THAT I can recover from schema errors

ACCEPTANCE CRITERIA:
- `alembic downgrade` reverts schema
- Data integrity maintained during rollback
- Rollback tested in staging environment
- Documented rollback procedures
```

### 4.3 Testing Stories

**Story 6: Fast Test Fixtures**
```
AS A test engineer
I WANT ORM-based test fixtures
SO THAT tests are fast and maintainable

ACCEPTANCE CRITERIA:
- Tests use in-memory SQLite
- Fixtures create ORM models (not SQL)
- Test isolation via rollback/transactions
- Test suite runs <5 minutes
```

---

## 5. Technical Architecture

### 5.1 Technology Stack

**Core Dependencies**:

| Package | Version | Purpose |
|---------|---------|---------|
| **sqlalchemy** | 2.0+ | ORM, query builder, schema management |
| **alembic** | 1.13+ | Database migration tool (by SQLAlchemy team) |
| **asyncpg** | 0.29+ | Async PostgreSQL driver (production) |
| **aiosqlite** | 0.19+ | Async SQLite driver (development) |
| **psycopg2-binary** | 2.9+ | Sync PostgreSQL driver (fallback) |

**Why Alembic?**:
- **Official**: Created/maintained by SQLAlchemy author (Mike Bayer)
- **Most Popular**: Industry standard (Django migrations inspired by Alembic)
- **Powerful**: Auto-generates migrations from model changes
- **Reliable**: Battle-tested in production (Uber, Lyft, Dropbox)
- **Alternatives**: Flask-Migrate (wrapper), Yoyo (simpler but limited), raw SQL scripts (no automation)

### 5.2 System Architecture

**Current (v0.5.0)**:
```
┌─────────────┐
│   Bot       │
│  (lib/bot)  │
└──────┬──────┘
       │
       ├──> DatabaseService (NATS wrapper)
       │    └──> BotDatabase (raw sqlite3)
       │         └──> bot_data.db (SQLite file)
       │
       └──> Shell, Channel, User, etc.
```

**New (v0.6.0 - SQLAlchemy)**:
```
┌─────────────┐
│   Bot       │
│  (lib/bot)  │
└──────┬──────┘
       │
       ├──> DatabaseService (NATS wrapper)
       │    └──> BotDatabase (SQLAlchemy ORM)
       │         ├──> Session (async)
       │         ├──> Engine (database URL)
       │         └──> Models (UserStats, UserActions, etc.)
       │              │
       │              ├──> SQLite (dev/test)
       │              └──> PostgreSQL (prod)
       │
       └──> Shell, Channel, User, etc.

Alembic (migrations):
    alembic/
    ├── versions/
    │   └── 001_initial_schema.py
    └── alembic.ini
```

### 5.3 Database Models (ORM)

**8 Models to Implement**:

```python
# common/models.py (NEW FILE)
from sqlalchemy import Column, Integer, String, Text, Boolean, Index
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from typing import Optional

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models"""
    pass

class UserStats(Base):
    """User statistics tracking"""
    __tablename__ = 'user_stats'
    
    username = Column(String(50), primary_key=True)
    first_seen = Column(Integer, nullable=False)
    last_seen = Column(Integer, nullable=False)
    total_chat_lines = Column(Integer, default=0)
    total_time_connected = Column(Integer, default=0)
    current_session_start = Column(Integer, nullable=True)
    
    __table_args__ = (
        Index('idx_last_seen', 'last_seen'),
    )

class UserAction(Base):
    """Audit log for user actions (PM commands, moderation)"""
    __tablename__ = 'user_actions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)

class ChannelStats(Base):
    """Channel-wide statistics"""
    __tablename__ = 'channel_stats'
    
    id = Column(Integer, primary_key=True, default=1)
    max_users = Column(Integer, default=0)
    last_updated = Column(Integer, nullable=False)

class UserCountHistory(Base):
    """Historical user count tracking"""
    __tablename__ = 'user_count_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    chat_users = Column(Integer, nullable=False)
    connected_users = Column(Integer, nullable=False)

class RecentChat(Base):
    """Recent chat message cache"""
    __tablename__ = 'recent_chat'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    username = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)

class CurrentStatus(Base):
    """Current bot status (singleton)"""
    __tablename__ = 'current_status'
    
    id = Column(Integer, primary_key=True, default=1)
    last_updated = Column(Integer, nullable=False)
    status = Column(String(50), default='offline')
    current_users = Column(Integer, default=0)
    connected_users = Column(Integer, default=0)

class OutboundMessage(Base):
    """Queued outbound messages"""
    __tablename__ = 'outbound_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    message = Column(Text, nullable=False)
    sent = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class ApiToken(Base):
    """API authentication tokens"""
    __tablename__ = 'api_tokens'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    permissions = Column(Text, nullable=False)  # JSON string
    created_at = Column(Integer, nullable=False)
    last_used = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
```

### 5.4 Migration Strategy

**Phase 1: Dual Mode (Compatibility Layer)**
- Keep existing `BotDatabase` API unchanged
- Implement SQLAlchemy backend internally
- Run tests against both implementations
- Verify zero regressions

**Phase 2: Full Migration**
- Remove raw sqlite3 code
- Update all imports
- Clean up compatibility layer
- Deploy with migrations

**Phase 3: PostgreSQL Validation**
- Test against PostgreSQL 16
- CI matrix: SQLite + PostgreSQL
- Performance benchmarking
- Production deployment guide

### 5.5 Alembic Migration Workflow

**Developer Workflow**:
```bash
# 1. Developer changes model (add column)
# common/models.py
class UserStats(Base):
    username = Column(String(50), primary_key=True)
    emoji_count = Column(Integer, default=0)  # NEW

# 2. Generate migration
alembic revision --autogenerate -m "Add emoji_count to user_stats"

# 3. Review generated migration
# alembic/versions/002_add_emoji_count.py
def upgrade():
    op.add_column('user_stats', sa.Column('emoji_count', sa.Integer(), default=0))

def downgrade():
    op.drop_column('user_stats', 'emoji_count')

# 4. Apply migration
alembic upgrade head

# 5. Commit migration + model changes
git add alembic/versions/002_add_emoji_count.py common/models.py
git commit -m "Add emoji tracking to user stats"
```

**Deployment Workflow**:
```bash
# Production deployment
git pull
alembic upgrade head  # Apply pending migrations
python -m lib.bot config-prod.json
```

---

## 6. Implementation Plan

### 6.1 Sprint Breakdown

**Total Effort**: 2-3 days (16-24 hours)

**Sortie 1: Foundation & Models** (6-8 hours)
- Install SQLAlchemy, Alembic, async drivers
- Create `common/models.py` with 8 ORM models
- Setup Alembic (init, alembic.ini, env.py)
- Generate initial migration from v0.5.0 schema
- **Deliverable**: ORM models + initial migration
- **Tests**: Model definitions, migration applies cleanly

**Sortie 2: BotDatabase Migration** (6-8 hours)
- Replace `_connect()` with SQLAlchemy engine/session
- Migrate all query methods to ORM
- Update `log_user_action()`, `get_user_stats()`, etc.
- Async session management
- **Deliverable**: Full SQLAlchemy BotDatabase
- **Tests**: All database tests pass

**Sortie 3: PostgreSQL Support & Testing** (4-6 hours)
- Add database URL configuration
- CI matrix: SQLite + PostgreSQL
- Test fixtures for both databases
- Performance benchmarking
- **Deliverable**: PostgreSQL support verified
- **Tests**: Full suite passes on both databases

**Sortie 4: Documentation & Deployment** (2 hours)
- Update ARCHITECTURE.md
- PostgreSQL deployment guide
- Migration workflow documentation
- Developer onboarding guide
- **Deliverable**: Complete documentation
- **Tests**: Manual deployment verification

### 6.2 Detailed Tasks

**Pre-Sprint Setup**:
- [ ] Review SQLAlchemy 2.0 documentation
- [ ] Review Alembic documentation
- [ ] Backup production database (if applicable)
- [ ] Create Sprint 11 branch: `sprint-11/sqlalchemy-migration`

**Sortie 1 Tasks** (Foundation):
- [ ] Add dependencies to requirements.txt
- [ ] Create `common/models.py`
- [ ] Define 8 ORM models with type hints
- [ ] Initialize Alembic: `alembic init alembic`
- [ ] Configure `alembic.ini` (database URL from config)
- [ ] Configure `alembic/env.py` (async support, model imports)
- [ ] Generate initial migration: `alembic revision --autogenerate -m "Initial schema"`
- [ ] Review migration, fix auto-generation issues
- [ ] Test migration: `alembic upgrade head`
- [ ] Test rollback: `alembic downgrade base`
- [ ] Commit: "Sprint 11 Sortie 1: ORM models and Alembic setup"

**Sortie 2 Tasks** (BotDatabase Migration):
- [ ] Create `BotDatabase.__init__()` with SQLAlchemy
- [ ] Implement async `connect()` / `close()` (from Sprint 10 Sortie 1)
- [ ] Migrate `user_joined()` to ORM
- [ ] Migrate `user_left()` to ORM
- [ ] Migrate `log_chat_message()` to ORM
- [ ] Migrate `log_user_action()` to ORM
- [ ] Migrate `get_user_stats()` to ORM
- [ ] Migrate `get_channel_stats()` to ORM
- [ ] Migrate all remaining methods (20+ methods)
- [ ] Remove raw sqlite3 imports
- [ ] Update tests to use ORM models
- [ ] Run full test suite: `pytest -v`
- [ ] Fix any test failures
- [ ] Commit: "Sprint 11 Sortie 2: SQLAlchemy ORM migration complete"

**Sortie 3 Tasks** (PostgreSQL):
- [ ] Add database URL to `config.json`: `"database_url": "sqlite:///bot_data.db"`
- [ ] Parse database URL in `BotDatabase.__init__()`
- [ ] Install PostgreSQL locally (or Docker)
- [ ] Create test PostgreSQL database
- [ ] Run tests against PostgreSQL: `DATABASE_URL=postgresql://... pytest -v`
- [ ] Fix PostgreSQL-specific issues (if any)
- [ ] Add CI matrix job for PostgreSQL
- [ ] Run performance benchmarks (SQLite vs PostgreSQL)
- [ ] Verify no regressions
- [ ] Commit: "Sprint 11 Sortie 3: PostgreSQL support and testing"

**Sortie 4 Tasks** (Documentation):
- [ ] Update `docs/ARCHITECTURE.md` (SQLAlchemy section)
- [ ] Create `docs/DATABASE_SETUP.md` (PostgreSQL guide)
- [ ] Update `docs/SETUP.md` (Alembic commands)
- [ ] Create `docs/MIGRATIONS.md` (migration workflow)
- [ ] Update `CHANGELOG.md` (v0.6.0 breaking changes)
- [ ] Update `requirements.txt` comments
- [ ] Commit: "Sprint 11 Sortie 4: Documentation complete"
- [ ] Create PR: "Sprint 11: SQLAlchemy Migration (The Conversation) - v0.6.0"

### 6.3 Testing Strategy

**Unit Tests** (new):
- ORM model validation (type hints, constraints)
- Migration up/down tests
- Session lifecycle tests

**Integration Tests** (update):
- All existing database tests (1,198 tests)
- Run against SQLite + PostgreSQL
- Verify identical behavior

**Performance Tests** (new):
- Benchmark query performance (before/after)
- Connection pooling tests
- Concurrent write tests (PostgreSQL)

**Manual Tests**:
- Fresh database initialization
- Migration from v0.5.0 → v0.6.0
- PostgreSQL deployment
- Rollback scenarios

---

## 7. Dependencies and Risks

### 7.1 Dependencies

**Internal Dependencies**:
- **Sprint 10 Complete**: Test infrastructure + async BotDatabase (Sortie 1)
- **Stable Schema**: No schema changes during migration
- **Test Coverage**: 66%+ coverage ensures migration safety

**External Dependencies**:
- **SQLAlchemy 2.0+**: Async support, modern API
- **Alembic 1.13+**: Latest migration features
- **PostgreSQL 14+**: Production database (optional)
- **Python 3.11+**: Type hints, async support

**Blocking Factors**:
- Sprint 10 incomplete (async database prerequisite)
- Breaking changes to database API (avoid!)
- Schema changes mid-migration (freeze schema)

### 7.2 Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data Loss** | Low | Critical | Full backups before migration, test rollback |
| **Performance Regression** | Medium | High | Benchmark before/after, optimize queries |
| **Test Failures** | Medium | Medium | Run tests continuously, fix incrementally |
| **PostgreSQL Issues** | Low | Medium | Test early, use Docker for consistency |
| **Migration Conflicts** | Low | Medium | Freeze schema, coordinate with team |
| **Alembic Learning Curve** | Medium | Low | Documentation, examples, pair programming |

**Risk Management**:

1. **Data Loss Prevention**:
   - Automated backups before migration
   - Test migrations on staging first
   - Verify rollback procedures
   - Document recovery steps

2. **Performance Monitoring**:
   - Benchmark all queries before/after
   - Profile slow queries
   - Add indexes as needed
   - Connection pooling for PostgreSQL

3. **Testing Coverage**:
   - Run full test suite after each method migration
   - CI runs on every commit
   - Manual testing checklist
   - PostgreSQL testing in CI

4. **Rollback Strategy**:
   - Keep sqlite3 code in Git history
   - Alembic downgrade tested
   - Document rollback procedures
   - Staging environment for validation

### 7.3 Rollback Plan

**If Migration Fails**:

1. **Immediate Rollback** (development):
   ```bash
   git checkout main
   alembic downgrade base
   python -m lib.bot config-test.json
   ```

2. **Production Rollback**:
   ```bash
   # Stop bot
   systemctl stop cytube-bot
   
   # Restore database backup
   cp bot_data.db.backup bot_data.db
   
   # Checkout previous version
   git checkout v0.5.0
   
   # Restart bot
   systemctl start cytube-bot
   ```

3. **Post-Rollback**:
   - Document failure reason
   - Fix issues in development
   - Re-test thoroughly
   - Attempt migration again

---

## 8. Breaking Changes

### 8.1 v0.5.0 → v0.6.0 Breaking Changes

**Configuration Changes**:

```json
// v0.5.0 (OLD):
{
  "database": "bot_data.db"
}

// v0.6.0 (NEW):
{
  "database_url": "sqlite:///bot_data.db"
  // OR
  "database_url": "postgresql://user:pass@localhost/rosey"
}
```

**API Changes** (Internal):
- `BotDatabase.__init__(db_path)` → `BotDatabase.__init__(database_url)`
- Synchronous methods → Async methods (from Sprint 10 Sortie 1)
- Raw SQL strings → ORM queries (internal only)

**No User-Facing Changes**:
- Bot behavior identical
- API endpoints unchanged
- PM commands unchanged
- Web dashboard unchanged

### 8.2 Migration Path

**Automatic Migration**:
```bash
# v0.5.0 database detected automatically
# Alembic applies migrations on first run
python -m lib.bot config.json
# Output: Running Alembic migrations...
#         Applied: 001_initial_schema
#         Database ready!
```

**Manual Migration** (advanced):
```bash
# Backup database
cp bot_data.db bot_data.db.backup

# Apply migrations
alembic upgrade head

# Verify
sqlite3 bot_data.db ".schema"
```

---

## 9. Documentation Requirements

### 9.1 User Documentation

**New Guides**:
- [ ] `docs/DATABASE_SETUP.md` - PostgreSQL installation and configuration
- [ ] `docs/MIGRATIONS.md` - Alembic migration workflow
- [ ] `docs/DEPLOYMENT_POSTGRESQL.md` - Production PostgreSQL guide

**Updated Guides**:
- [ ] `docs/SETUP.md` - Add Alembic commands
- [ ] `docs/ARCHITECTURE.md` - SQLAlchemy architecture
- [ ] `docs/TESTING.md` - ORM testing patterns
- [ ] `README.md` - Update dependencies, setup steps

### 9.2 Developer Documentation

**Code Documentation**:
- [ ] `common/models.py` - Docstrings for all models
- [ ] `common/database.py` - SQLAlchemy usage examples
- [ ] `alembic/README` - Migration guide

**API Documentation**:
- [ ] Type hints on all methods
- [ ] Docstrings with SQLAlchemy examples
- [ ] Migration examples in comments

### 9.3 Operations Documentation

**Deployment Guides**:
- [ ] PostgreSQL setup (local, staging, production)
- [ ] Connection pooling configuration
- [ ] Backup and restore procedures
- [ ] Migration rollback procedures
- [ ] Monitoring and performance tuning

---

## 10. Success Validation

### 10.1 Acceptance Criteria

**Must Have** (P0):
- [ ] All 1,198 tests pass with SQLAlchemy
- [ ] Zero functional regressions (manual testing)
- [ ] Initial migration applies cleanly
- [ ] Alembic upgrade/downgrade works
- [ ] PostgreSQL support verified (CI + local)
- [ ] Type hints pass mypy validation
- [ ] Performance within ±10% of v0.5.0
- [ ] Documentation complete

**Should Have** (P1):
- [ ] Code coverage maintained ≥66%
- [ ] CI matrix: SQLite + PostgreSQL
- [ ] Developer onboarding guide
- [ ] PostgreSQL deployment tested

**Nice to Have** (P2):
- [ ] Performance improvements (connection pooling)
- [ ] Query optimization examples
- [ ] Migration examples for common changes

### 10.2 Testing Checklist

**Functional Testing**:
- [ ] Bot starts successfully (SQLite)
- [ ] Bot starts successfully (PostgreSQL)
- [ ] User join/leave tracked
- [ ] Chat messages logged
- [ ] PM commands logged
- [ ] Stats queries work
- [ ] API tokens validated
- [ ] Outbound messages queued

**Migration Testing**:
- [ ] Fresh database initialization
- [ ] v0.5.0 → v0.6.0 upgrade
- [ ] Downgrade to v0.5.0
- [ ] Multiple upgrades (v0.6.0 → v0.6.1 → v0.6.2)

**Performance Testing**:
- [ ] Query performance benchmarks
- [ ] Connection pooling (PostgreSQL)
- [ ] Concurrent writes (PostgreSQL)
- [ ] Test suite execution time

**PostgreSQL Testing**:
- [ ] Local PostgreSQL deployment
- [ ] Docker PostgreSQL deployment
- [ ] Cloud PostgreSQL (RDS, Azure, etc.)
- [ ] Replication setup (optional)

### 10.3 Deployment Checklist

**Pre-Deployment**:
- [ ] Backup production database
- [ ] Test migration on staging
- [ ] Verify rollback procedures
- [ ] Review performance benchmarks
- [ ] Update documentation

**Deployment**:
- [ ] Stop bot service
- [ ] Backup database
- [ ] Pull new code
- [ ] Run migrations: `alembic upgrade head`
- [ ] Start bot service
- [ ] Verify functionality
- [ ] Monitor logs

**Post-Deployment**:
- [ ] Verify all features working
- [ ] Check performance metrics
- [ ] Monitor error rates
- [ ] Update CHANGELOG.md
- [ ] Announce v0.6.0 release

---

## 11. Future Considerations

### 11.1 v0.7.0+ Enhancements

**Database Features**:
- MySQL/MariaDB support (third database backend)
- Multi-tenant support (one database, multiple bots)
- Database sharding (horizontal scaling)
- Read replicas (query performance)

**ORM Features**:
- Relationships between models (foreign keys)
- Lazy loading / eager loading
- Query result caching
- Advanced indexing strategies

**Schema Evolution**:
- Online migrations (zero-downtime)
- Blue-green deployments
- Canary migrations
- Automatic rollback on errors

### 11.2 Monitoring and Observability

**Database Metrics**:
- Query performance tracking
- Connection pool utilization
- Slow query logging
- Database size monitoring

**Migration Metrics**:
- Migration execution time
- Rollback success rate
- Schema version history
- Migration failure alerts

### 11.3 Security Enhancements

**Database Security**:
- Connection encryption (SSL/TLS)
- Role-based access control
- Audit logging (who changed what)
- Secrets management (credentials)

---

## 12. Open Questions

### 12.1 Technical Questions

1. **Connection Pooling**: What pool size for PostgreSQL? (Recommend: 5-10)
2. **Async Driver**: `asyncpg` (fast) vs `psycopg3` (familiar)? (Recommend: asyncpg)
3. **Type Checking**: Enforce mypy in CI? (Recommend: Yes, warnings only)
4. **Migration Strategy**: Auto-generate vs manual migrations? (Recommend: Auto-generate, review manually)

### 12.2 Deployment Questions

5. **PostgreSQL Version**: Minimum version? (Recommend: PostgreSQL 14+)
6. **Cloud Providers**: Support AWS RDS, Azure Database, Google Cloud SQL? (Recommend: Yes, document all)
7. **Backup Strategy**: Automated backups via Alembic? (Recommend: No, use database tools)
8. **High Availability**: PostgreSQL replication? (Recommend: Document, not implement)

### 12.3 Process Questions

9. **Schema Freeze**: Freeze schema during Sprint 11? (Recommend: Yes, critical)
10. **Review Process**: Who reviews migrations? (Recommend: Team lead + peer review)
11. **Staging Environment**: Required for testing? (Recommend: Yes, create if needed)
12. **Rollback Testing**: Test every migration rollback? (Recommend: Yes, automated)

---

## 13. Appendices

### Appendix A: SQLAlchemy vs Raw SQL Comparison

**Query Complexity**:

```python
# Raw SQL (v0.5.0):
cursor.execute('''
    SELECT * FROM user_stats 
    WHERE username = ? AND total_chat_lines > ?
''', (username, 100))
result = cursor.fetchone()

# SQLAlchemy (v0.6.0):
result = await session.execute(
    select(UserStats)
    .where(UserStats.username == username)
    .where(UserStats.total_chat_lines > 100)
)
user = result.scalar_one_or_none()
```

**Insert Complexity**:

```python
# Raw SQL (v0.5.0):
cursor.execute('''
    INSERT INTO user_actions (timestamp, username, action_type, details)
    VALUES (?, ?, ?, ?)
''', (int(time.time()), username, 'pm_command', details))
conn.commit()

# SQLAlchemy (v0.6.0):
action = UserAction(
    timestamp=int(time.time()),
    username=username,
    action_type='pm_command',
    details=details
)
session.add(action)
await session.commit()
```

### Appendix B: Alembic Migration Example

**Adding a Column**:

```python
# alembic/versions/002_add_emoji_count.py
"""Add emoji_count to user_stats

Revision ID: 002
Revises: 001
Create Date: 2025-11-21 14:30:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002'
down_revision = '001'

def upgrade():
    op.add_column('user_stats', 
        sa.Column('emoji_count', sa.Integer(), nullable=False, server_default='0')
    )

def downgrade():
    op.drop_column('user_stats', 'emoji_count')
```

### Appendix C: PostgreSQL Setup Guide (Quick Start)

**Local Development**:

```bash
# Install PostgreSQL
brew install postgresql@16  # macOS
# or
sudo apt install postgresql-16  # Ubuntu

# Start PostgreSQL
brew services start postgresql@16

# Create database
createdb rosey_dev

# Update config.json
{
  "database_url": "postgresql://localhost/rosey_dev"
}

# Run migrations
alembic upgrade head

# Start bot
python -m lib.bot config.json
```

**Docker Development**:

```bash
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: rosey_dev
      POSTGRES_USER: rosey
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"

# Start PostgreSQL
docker-compose up -d postgres

# Update config.json
{
  "database_url": "postgresql://rosey:dev_password@localhost/rosey_dev"
}

# Run migrations
alembic upgrade head
```

---

## 14. Sprint Milestones

### Milestone 1: ORM Foundation (Day 1)
- SQLAlchemy installed
- 8 ORM models defined
- Alembic initialized
- Initial migration created
- **Exit Criteria**: Migration applies cleanly, models pass tests

### Milestone 2: Full Migration (Day 2)
- All database methods migrated
- All tests pass with SQLAlchemy
- Performance validated
- **Exit Criteria**: Zero regressions, 1,198 tests pass

### Milestone 3: PostgreSQL Support (Day 3)
- PostgreSQL tested locally
- CI matrix running
- Documentation complete
- **Exit Criteria**: PostgreSQL verified, deployment guide ready

### Milestone 4: Production Ready (Day 3)
- PR created and reviewed
- Deployment tested on staging
- v0.6.0 release prepared
- **Exit Criteria**: Ready to merge and deploy

---

## 15. Stakeholder Sign-Off

**Product Owner**: _________________ Date: _______  
**Tech Lead**: _________________ Date: _______  
**QA Lead**: _________________ Date: _______  
**DevOps Lead**: _________________ Date: _______  

---

**Document Version**: 1.0  
**Status**: Ready for Review  
**Sprint**: Sprint 11 "The Conversation"  
**Movie Reference**: _The Conversation_ (1974) - Francis Ford Coppola's masterpiece about surveillance and listening. In this sprint, we're "listening" to the database, understanding its structure, and having a "conversation" between the application and data layer through SQLAlchemy's ORM. Just as Harry Caul (Gene Hackman) meticulously records conversations, we're meticulously recording schema changes through Alembic migrations.

**Next Steps**:
1. Review PRD with team
2. Approve dependencies (SQLAlchemy, Alembic)
3. Create Sprint 11 branch
4. Begin Sortie 1: ORM models and Alembic setup

---

**"The conversation is the database. The migration is the recording."**
