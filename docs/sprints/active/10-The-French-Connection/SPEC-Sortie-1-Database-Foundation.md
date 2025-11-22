# Technical Specification: Database Foundation

**Sprint**: Sprint 10 "The French Connection"  
**Sortie**: 1 of 4  
**Status**: Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Dependencies**: None (Foundation)  
**Blocking**: Sortie 2 (Stats Command), Sortie 4 (Performance Benchmarks)  

---

## Overview

**Purpose**: Implement async `BotDatabase` connection lifecycle to unblock 22 xfail tests (12 Sprint 9 integration tests + 10 performance benchmarks). This is the **foundation sortie** - all database-dependent tests require this implementation.

**Scope**: 
- Add `async def connect()` and `async def close()` to `BotDatabase` class
- Migrate from synchronous `sqlite3` to async `aiosqlite`
- Update test fixtures to use async connection patterns
- Remove `xfail` markers from 12 Sprint 9 integration tests
- Validate all database tests pass without pollution

**Non-Goals**: 
- Stats command implementation (Sortie 2)
- PM logging refactor (Sortie 3)
- Performance optimization (Sortie 4 validates first)
- Production deployment (Sprint 11)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: `BotDatabase` MUST have async `connect()` method for initialization  
**FR-002**: `BotDatabase` MUST have async `close()` method for graceful shutdown  
**FR-003**: `connect()` MUST initialize database connection with `aiosqlite`  
**FR-004**: `connect()` MUST run migrations to create all required tables  
**FR-005**: `close()` MUST commit pending transactions before closing connection  
**FR-006**: Tests MUST be able to create/destroy temporary databases independently  
**FR-007**: Test fixtures MUST use async patterns (`await db.connect()`)  
**FR-008**: All existing database methods MUST be converted to async (`async def`)  

### 1.2 Non-Functional Requirements

**NFR-001**: No behavior changes - API remains identical except async/await  
**NFR-002**: All 12 Sprint 9 integration tests pass without xfail markers  
**NFR-003**: Test coverage maintained at 66%+ (no regressions)  
**NFR-004**: No test pollution - each test gets clean database state  
**NFR-005**: Clean async-only implementation (no backward compatibility needed)  

---

## 2. Problem Statement

### 2.1 Current State

**Issue #50**: BotDatabase.connect() not implemented - blocking 12 integration tests

The current `BotDatabase` class uses synchronous `sqlite3` and auto-connects in `__init__`:

```python
class BotDatabase:
    def __init__(self, db_path='bot_data.db'):
        self.db_path = db_path
        self.conn = None
        self._connect()         # ❌ Synchronous auto-connect
        self._create_tables()   # ❌ Synchronous table creation
```

**Problems**:

1. **No async support**: Test fixtures can't use `await db.connect()`
2. **Auto-connection**: No control over connection lifecycle
3. **SQLite3 only**: Blocks async I/O patterns required by NATS architecture
4. **Test pollution**: Shared connection state between tests
5. **Blocking initialization**: Can't await in `__init__`

**Impact on Tests**:

```python
# tests/conftest.py - temp_database fixture
@pytest.fixture
async def temp_database():
    db = BotDatabase(db_path)
    await db.connect()  # ❌ AttributeError: 'BotDatabase' object has no attribute 'connect'
    yield db
    await db.close()    # ❌ AttributeError: 'BotDatabase' object has no attribute 'close'
```

**Blocked Tests** (12 total):
- `test_database_initialization_and_schema` - Can't create test database
- `test_user_join_event_processing` - Needs temp_database fixture
- `test_user_leave_event_processing` - Needs temp_database fixture
- `test_chat_event_publishing` - Needs temp_database fixture
- `test_media_change_event` - Needs temp_database fixture
- `test_playlist_event_flow` - Needs temp_database fixture
- `test_service_statistics_query` - Needs temp_database fixture
- `test_concurrent_event_processing` - Needs temp_database fixture
- `test_database_stats_integration` - Needs temp_database fixture
- Plus 3 more database integration tests
- Plus 10 performance benchmarks (all blocked by database init)

---

## 3. Detailed Design

### 3.1 BotDatabase Class Architecture

**Async-Only Lifecycle Pattern**:

```python
# Sprint 10 - Clean async implementation:
db = BotDatabase('test.db')  # No connection yet
await db.connect()           # Explicit async connection
await db.user_joined('Alice') # Async operations
await db.close()             # Async cleanup
```

**Key Design Decisions**:

1. **Async-Only Implementation**:
   - Remove `_connect()` and `_create_tables()` sync methods entirely
   - `__init__` only stores path - no connection
   - All database operations require `await db.connect()` first
   - Clean break from Sprint 9 - v0.5.0 alpha allows breaking changes

2. **Connection State Tracking**:
   - Add `_is_connected` boolean property
   - Add `is_connected` read-only property for checking status
   - Prevents double-connection bugs

3. **Migration Runner**:
   - Extract `_create_tables()` logic into separate `_run_migrations()` method
   - Call from `connect()` to ensure schema exists
   - Idempotent - safe to call multiple times

4. **Graceful Shutdown**:
   - `close()` commits any pending transactions
   - Sets `_is_connected = False` to prevent further operations
   - Closes connection cleanly

---

### 3.2 Implementation Changes

#### Change 1: Add aiosqlite Dependency

**File**: `requirements.txt`  

**Addition**:
```text
aiosqlite>=0.19.0  # Async SQLite wrapper for BotDatabase
```

**Rationale**: `aiosqlite` provides async interface to SQLite3, compatible with existing schema and queries.

---

#### Change 2: Import aiosqlite in BotDatabase

**File**: `common/database.py`  
**Line**: 4 (after existing imports)  

**Addition**:
```python
import aiosqlite
from typing import Optional
```

**Rationale**: Support both sync (sqlite3) and async (aiosqlite) for migration period.

---

#### Change 3: Add Connection Lifecycle Methods

**File**: `common/database.py`  
**Line**: After `__init__` method (~25)  

**Addition**:
```python
    async def connect(self) -> None:
        """Initialize async database connection and run migrations.
        
        This method must be called before using the database in async contexts.
        Creates the SQLite connection using aiosqlite and initializes all tables.
        
        Example:
            db = BotDatabase('test.db')
            await db.connect()
            await db.user_joined('Alice')
            await db.close()
        
        Raises:
            RuntimeError: If already connected
            aiosqlite.Error: If database connection fails
        """
        if self._is_connected:
            raise RuntimeError(f"Database already connected: {self.db_path}")
        
        self.logger.info('Connecting to database (async): %s', self.db_path)
        
        # Create async connection
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        
        # Run migrations to create tables
        await self._run_migrations()
        
        self._is_connected = True
        self.logger.info('Database connected successfully: %s', self.db_path)
    
    async def close(self) -> None:
        """Close database connection gracefully.
        
        Commits any pending transactions and closes the connection.
        Safe to call multiple times - subsequent calls are no-ops.
        
        Example:
            await db.close()
        """
        if not self._is_connected:
            self.logger.debug('Database already closed or never connected')
            return
        
        if self.conn:
            try:
                # Commit any pending transactions
                await self.conn.commit()
                
                # Close active sessions (update user stats)
                now = int(time.time())
                cursor = await self.conn.cursor()
                await cursor.execute('''
                    UPDATE user_stats
                    SET total_time_connected = total_time_connected + (? - current_session_start),
                        current_session_start = NULL,
                        last_seen = ?
                    WHERE current_session_start IS NOT NULL
                ''', (now, now))
                await self.conn.commit()
                
                # Close connection
                await self.conn.close()
                self.logger.info('Database connection closed: %s', self.db_path)
            
            except Exception as e:
                self.logger.error('Error closing database: %s', e)
                raise
            
            finally:
                self._is_connected = False
                self.conn = None
    
    @property
    def is_connected(self) -> bool:
        """Check if database is currently connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._is_connected
```

**Rationale**:
- `connect()` establishes async connection and runs migrations
- `close()` ensures clean shutdown with transaction commit
- `is_connected` property allows external code to check connection state
- Error handling prevents resource leaks
- Logging provides visibility into connection lifecycle

---

#### Change 4: Add Connection State Tracking

**File**: `common/database.py`  
**Line**: In `__init__` method (~15)  

**Current Code**:
```python
def __init__(self, db_path='bot_data.db'):
    """Initialize database connection and create tables"""
    self.logger = logging.getLogger(__name__)
    self.db_path = db_path
    self.conn = None
    self._connect()
    self._create_tables()
```

**New Code**:
```python
def __init__(self, db_path='bot_data.db'):
    """Initialize database instance (connection created via connect()).
    
    Args:
        db_path: Path to SQLite database file (default: 'bot_data.db')
    
    Note:
        Call `await db.connect()` after initialization to establish connection.
        This is v0.5.0 alpha - breaking change from Sprint 9.
    """
    self.logger = logging.getLogger(__name__)
    self.db_path = db_path
    self.conn: Optional[aiosqlite.Connection] = None
    self._is_connected = False
```

**Rationale**:
- **Clean break**: No backward compatibility - v0.5.0 alpha allows breaking changes
- **Type hints**: `Optional[aiosqlite.Connection]` clarifies connection type
- **State tracking**: `_is_connected` prevents connection bugs
- **Simple**: No try/except fallback logic needed

---

#### Change 5: Extract Migration Runner

**File**: `common/database.py`  
**Line**: After `_create_tables()` method (~100)  

**Addition**:
```python
    async def _run_migrations(self) -> None:
        """Run database migrations to create tables.
        
        This is the async version of _create_tables(). Creates all required
        tables if they don't exist. Idempotent - safe to call multiple times.
        
        Tables created:
        - user_stats: User statistics (chat lines, time connected)
        - user_actions: Audit log for PM commands
        - channel_stats: High water marks for users
        - user_count_history: Historical user count data
        - recent_chat: Last N chat messages
        - current_status: Live bot state
        - outbound_messages: Message queue for bot
        - api_tokens: Authentication tokens
        """
        cursor = await self.conn.cursor()
        
        # User statistics table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                username TEXT PRIMARY KEY,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                total_chat_lines INTEGER DEFAULT 0,
                total_time_connected INTEGER DEFAULT 0,
                current_session_start INTEGER
            )
        ''')
        
        # User actions/PM log table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        # High water mark table (single row with channel stats)
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                max_users INTEGER DEFAULT 0,
                max_users_timestamp INTEGER,
                max_connected INTEGER DEFAULT 0,
                max_connected_timestamp INTEGER,
                last_updated INTEGER
            )
        ''')
        
        # User count history table for graphing over time
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_count_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                chat_users INTEGER NOT NULL,
                connected_users INTEGER NOT NULL
            )
        ''')
        
        # Create index for efficient time-range queries
        await cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_count_timestamp
            ON user_count_history(timestamp)
        ''')
        
        # Recent chat messages table (keep last N messages)
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS recent_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                username TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        
        # Create index for efficient timestamp queries
        await cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_recent_chat_timestamp
            ON recent_chat(timestamp DESC)
        ''')
        
        # Current status table (single row with live bot state)
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bot_name TEXT,
                bot_rank REAL,
                bot_afk INTEGER DEFAULT 0,
                channel_name TEXT,
                current_chat_users INTEGER DEFAULT 0,
                current_connected_users INTEGER DEFAULT 0,
                playlist_items INTEGER DEFAULT 0,
                current_media_title TEXT,
                current_media_duration INTEGER,
                bot_start_time INTEGER,
                bot_connected INTEGER DEFAULT 0,
                last_updated INTEGER
            )
        ''')
        
        # Initialize current_status if empty
        await cursor.execute('SELECT COUNT(*) FROM current_status')
        row = await cursor.fetchone()
        if row[0] == 0:
            await cursor.execute('''
                INSERT INTO current_status (id, last_updated)
                VALUES (1, ?)
            ''', (int(time.time()),))
        
        # Outbound messages queue
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS outbound_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                sent_timestamp INTEGER,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        ''')
        await cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_outbound_sent
            ON outbound_messages(sent, timestamp)
        ''')
        
        # Migrate existing outbound_messages table if needed
        await cursor.execute('PRAGMA table_info(outbound_messages)')
        outbound_cols = [col[1] for col in await cursor.fetchall()]
        if 'retry_count' not in outbound_cols:
            await cursor.execute('''
                ALTER TABLE outbound_messages
                ADD COLUMN retry_count INTEGER DEFAULT 0
            ''')
        if 'last_error' not in outbound_cols:
            await cursor.execute('''
                ALTER TABLE outbound_messages
                ADD COLUMN last_error TEXT
            ''')
        
        # API tokens table
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_tokens (
                token TEXT PRIMARY KEY,
                description TEXT,
                created_at INTEGER NOT NULL,
                last_used INTEGER,
                revoked INTEGER DEFAULT 0
            )
        ''')
        await cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_tokens_revoked
            ON api_tokens(revoked, token)
        ''')
        
        # Initialize channel_stats if empty
        await cursor.execute('SELECT COUNT(*) FROM channel_stats')
        row = await cursor.fetchone()
        if row[0] == 0:
            await cursor.execute('''
                INSERT INTO channel_stats (id, max_users, last_updated)
                VALUES (1, 0, ?)
            ''', (int(time.time()),))
        else:
            # Migrate existing database - add new columns if they don't exist
            await cursor.execute('PRAGMA table_info(channel_stats)')
            columns = [col[1] for col in await cursor.fetchall()]
            if 'max_connected' not in columns:
                await cursor.execute('''
                    ALTER TABLE channel_stats
                    ADD COLUMN max_connected INTEGER DEFAULT 0
                ''')
            if 'max_connected_timestamp' not in columns:
                await cursor.execute('''
                    ALTER TABLE channel_stats
                    ADD COLUMN max_connected_timestamp INTEGER
                ''')
        
        await self.conn.commit()
        self.logger.info('Database migrations completed')
```

**Rationale**:
- Async version of existing `_create_tables()` method
- Identical schema - no breaking changes
- Idempotent - safe to call multiple times
- Includes all table definitions and indexes
- Handles database migrations for new columns

---

#### Change 6: Update Test Fixture (temp_database)

**File**: `tests/conftest.py`  
**Line**: ~95 (temp_database fixture)  

**Current Code**:
```python
@pytest.fixture
async def temp_database():
    """Create temporary database for testing."""
    # NOTE: BotDatabase.connect() not implemented - needs DatabaseService refactor
    # Tests using this fixture should be marked with @pytest.mark.xfail
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = BotDatabase(db_path)
    await db.connect()  # ❌ Not implemented yet
    
    yield db
    
    await db.close()
    Path(db_path).unlink(missing_ok=True)
```

**New Code**:
```python
@pytest.fixture
async def temp_database():
    """Create temporary database for testing.
    
    Provides a fully-initialized async BotDatabase instance with:
    - Temporary file path (auto-cleaned up)
    - All tables created via migrations
    - Clean state for each test
    - Automatic connection lifecycle management
    
    Example:
        async def test_database_operations(temp_database):
            await temp_database.user_joined('Alice')
            stats = await temp_database.get_user_stats('Alice')
            assert stats is not None
    
    Yields:
        BotDatabase: Connected async database instance
    """
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Initialize and connect database
    db = BotDatabase(db_path)
    await db.connect()
    
    # Provide to test
    yield db
    
    # Cleanup
    try:
        await db.close()
    except Exception as e:
        logging.warning('Error closing test database: %s', e)
    
    finally:
        # Remove temp file
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception as e:
            logging.warning('Error removing test database file: %s', e)
```

**Rationale**:
- **Works now**: `await db.connect()` is implemented
- **Clean lifecycle**: Connect → test → close → cleanup
- **Error handling**: Prevents resource leaks if test crashes
- **Documentation**: Clear docstring with example usage
- **Safety**: Always removes temp file even if close() fails

---

#### Change 7: Remove xfail Markers from Sprint 9 Tests

**File**: `tests/integration/test_sprint9_integration.py`  
**Lines**: Multiple (all tests marked with xfail for BotDatabase.connect())  

**Changes Required** (12 tests):

```python
# BEFORE:
@pytest.mark.xfail(reason="BotDatabase.connect() not implemented - temp_database fixture fails")
@pytest.mark.asyncio
async def test_database_initialization_and_schema(temp_database):
    """Test database connection and schema creation via connect()."""
    # Test implementation...

# AFTER:
@pytest.mark.asyncio
async def test_database_initialization_and_schema(temp_database):
    """Test database connection and schema creation via connect()."""
    # Test implementation...
```

**Tests to Update** (remove `@pytest.mark.xfail` decorator):

1. `test_database_initialization_and_schema` (line ~135)
2. `test_user_join_event_processing` (line ~156)
3. `test_user_leave_event_processing` (line ~186)
4. `test_chat_event_publishing` (line ~214)
5. `test_media_change_event` (line ~247)
6. `test_playlist_event_flow` (line ~269)
7. `test_service_statistics_query` (line ~300)
8. `test_concurrent_event_processing` (line ~429)
9. `test_database_stats_integration` (line ~464)
10-12. Three additional database integration tests (search file for xfail + BotDatabase.connect)

**Rationale**:
- Tests now have working `temp_database` fixture
- No test implementation changes needed - just remove markers
- Tests should pass immediately after database changes
- Validates that async database implementation works correctly

---

## 4. Testing Strategy

### 4.1 Unit Tests (New)

**File**: `tests/unit/test_database_lifecycle.py` (NEW)

**Purpose**: Test database connection lifecycle in isolation

**Test Cases**:

```python
@pytest.mark.asyncio
async def test_connect_creates_connection():
    """Test connect() establishes connection."""
    db = BotDatabase(':memory:')
    assert not db.is_connected
    
    await db.connect()
    assert db.is_connected
    assert db.conn is not None
    
    await db.close()

@pytest.mark.asyncio
async def test_connect_twice_raises_error():
    """Test connecting twice raises RuntimeError."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    with pytest.raises(RuntimeError, match="already connected"):
        await db.connect()
    
    await db.close()

@pytest.mark.asyncio
async def test_close_gracefully_handles_no_connection():
    """Test close() is safe when not connected."""
    db = BotDatabase(':memory:')
    # Should not raise
    await db.close()
    await db.close()  # Multiple closes OK

@pytest.mark.asyncio
async def test_migrations_create_all_tables():
    """Test _run_migrations() creates all required tables."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    # Check tables exist
    cursor = await db.conn.cursor()
    await cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = [row[0] for row in await cursor.fetchall()]
    
    expected = [
        'api_tokens',
        'channel_stats',
        'current_status',
        'outbound_messages',
        'recent_chat',
        'user_actions',
        'user_count_history',
        'user_stats'
    ]
    
    for table in expected:
        assert table in tables, f"Missing table: {table}"
    
    await db.close()

@pytest.mark.asyncio
async def test_close_commits_active_sessions():
    """Test close() updates active user sessions."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    # Create user with active session
    cursor = await db.conn.cursor()
    now = int(time.time())
    await cursor.execute('''
        INSERT INTO user_stats 
        (username, first_seen, last_seen, current_session_start)
        VALUES ('Alice', ?, ?, ?)
    ''', (now, now, now))
    await db.conn.commit()
    
    # Close database
    await db.close()
    
    # Reopen and verify session was closed
    db2 = BotDatabase(db.db_path)
    await db2.connect()
    cursor2 = await db2.conn.cursor()
    await cursor2.execute('''
        SELECT current_session_start, total_time_connected
        FROM user_stats WHERE username = 'Alice'
    ''')
    row = await cursor2.fetchone()
    
    assert row[0] is None  # Session ended
    assert row[1] > 0      # Time tracked
    
    await db2.close()
```

**Coverage Target**: 100% of new connection methods

---

### 4.2 Integration Tests (Existing)

**File**: `tests/integration/test_sprint9_integration.py`

**Changes**: Remove xfail markers (no implementation changes)

**Expected Results**:
- ✅ All 12 database tests pass
- ✅ temp_database fixture works correctly
- ✅ No test pollution between tests
- ✅ Clean database state for each test

**Validation**:
```bash
# Run Sprint 9 integration tests
pytest tests/integration/test_sprint9_integration.py -v -k "database"

# Expected output:
# test_database_initialization_and_schema PASSED
# test_user_join_event_processing PASSED
# test_user_leave_event_processing PASSED
# test_chat_event_publishing PASSED
# test_media_change_event PASSED
# test_playlist_event_flow PASSED
# test_service_statistics_query PASSED
# test_concurrent_event_processing PASSED
# test_database_stats_integration PASSED
# ... (12 total)
```

---

### 4.3 Performance Benchmarks (Existing - Will Unblock)

**File**: `tests/benchmarks/test_performance.py`

**Changes**: Remove xfail markers from 10 benchmarks

**Expected Results**:
- ✅ All 10 benchmarks run (may fail performance thresholds - that's OK for Sortie 1)
- ✅ Baseline performance metrics collected
- ✅ NATS latency measured
- ✅ Database overhead quantified

**Validation** (Sortie 4):
```bash
# Run performance benchmarks (Sortie 1 - just validate they run)
pytest tests/benchmarks/test_performance.py -v

# Expected: All run, some may fail thresholds (to be fixed in Sortie 4)
```

---

### 4.4 Test Coverage

**Target**: Maintain 66%+ overall coverage (no regressions)

**New Coverage**:
- `common/database.py`: +120 lines (connect, close, _run_migrations)
- `tests/unit/test_database_lifecycle.py`: +150 lines (new tests)

**Run Coverage**:
```bash
pytest --cov=common --cov=lib --cov-report=html --cov-report=term
```

**Success Criteria**:
- Overall coverage ≥66%
- `common/database.py` coverage ≥80% (new code fully tested)
- No coverage regressions in existing modules

---

## 5. Implementation Steps

### Phase 1: Core Implementation (4 hours)

1. ✅ Add `aiosqlite` to `requirements.txt`
2. ✅ Update imports in `common/database.py`
3. ✅ Simplify `__init__` - remove `_connect()` and `_create_tables()` calls
4. ✅ Add `_is_connected` field to `__init__`
5. ✅ Implement `connect()` method
6. ✅ Implement `close()` method
7. ✅ Add `is_connected` property
8. ✅ Implement `_run_migrations()` method (replaces `_create_tables()`)
9. ✅ Delete `_connect()` sync method entirely
10. ✅ Delete `_create_tables()` sync method entirely

### Phase 2: Test Infrastructure (2 hours)

9. ✅ Update `temp_database` fixture in `tests/conftest.py`
10. ✅ Create `tests/unit/test_database_lifecycle.py`
11. ✅ Write 5 unit tests for connection lifecycle
12. ✅ Run unit tests, verify 100% coverage of new code

### Phase 3: Integration Test Migration (2 hours)

13. ✅ Remove xfail markers from 12 Sprint 9 tests
14. ✅ Run integration tests, verify all pass
15. ✅ Remove xfail markers from 10 performance benchmarks
16. ✅ Run benchmarks, verify they execute (may fail thresholds)

### Phase 4: Validation and Documentation (1 hour)

17. ✅ Run full test suite: `pytest -v`
18. ✅ Run coverage report: `pytest --cov`
19. ✅ Update issue #50 with implementation details
20. ✅ Commit with detailed message

---

## 6. Acceptance Criteria

### 6.1 Implementation Complete

- [ ] `aiosqlite>=0.19.0` added to requirements.txt
- [ ] `BotDatabase.connect()` method implemented with async/await
- [ ] `BotDatabase.close()` method implemented with async/await
- [ ] `BotDatabase.is_connected` property added
- [ ] `_run_migrations()` async method replaces `_create_tables()`
- [ ] Connection state tracking with `_is_connected` boolean
- [ ] `_connect()` and `_create_tables()` sync methods removed (breaking change)

### 6.2 Test Infrastructure Updated

- [ ] `temp_database` fixture works with async database
- [ ] Fixture creates clean database state for each test
- [ ] Fixture cleans up temporary files after tests
- [ ] 5+ unit tests for connection lifecycle in `test_database_lifecycle.py`
- [ ] All unit tests pass with 100% coverage of new code

### 6.3 Integration Tests Passing

- [ ] All 12 Sprint 9 integration tests pass (xfail removed)
- [ ] `test_database_initialization_and_schema` passes
- [ ] `test_user_join_event_processing` passes
- [ ] `test_user_leave_event_processing` passes
- [ ] `test_chat_event_publishing` passes
- [ ] `test_media_change_event` passes
- [ ] `test_playlist_event_flow` passes
- [ ] `test_service_statistics_query` passes
- [ ] `test_concurrent_event_processing` passes
- [ ] `test_database_stats_integration` passes
- [ ] Plus 3 additional database integration tests pass

### 6.4 Performance Benchmarks Unblocked

- [ ] All 10 performance benchmarks execute (don't crash)
- [ ] xfail markers removed from benchmark tests
- [ ] Baseline performance data collected (may fail thresholds - OK)
- [ ] NATS latency measured (for Sortie 4 optimization)

### 6.5 Quality Gates

- [ ] Full test suite runs: `pytest -v` (all non-xfail tests pass)
- [ ] Code coverage ≥66% overall (no regressions)
- [ ] `common/database.py` coverage ≥80%
- [ ] CI passes: Test job (1,179 tests pass, 19 xfail)
- [ ] CI passes: Lint job (no new errors)
- [ ] CI passes: Build job (requirements.txt valid)

### 6.6 Documentation Updated

- [ ] Docstrings added to `connect()` method with usage examples
- [ ] Docstrings added to `close()` method
- [ ] Docstring added to `is_connected` property
- [ ] `__init__` docstring updated with async usage instructions
- [ ] Issue #50 updated with implementation summary
- [ ] Commit message references SPEC and issue number

---

## 7. Rollout Plan

### 7.1 Pre-Implementation Checklist

- [ ] Review this SPEC with stakeholders
- [ ] Verify NATS container available in CI (from Sprint 9)
- [ ] Confirm test coverage threshold (66%) in pytest.ini
- [ ] Back up current database implementation (git commit)

### 7.2 Implementation Order

**Stage 1: Core Database** (No Tests Yet)
1. Add aiosqlite to requirements
2. Implement connect/close/migrations
3. Update __init__ with backward compatibility

**Stage 2: Test Infrastructure** (Isolated Testing)
4. Update temp_database fixture
5. Create unit tests for lifecycle
6. Verify unit tests pass in isolation

**Stage 3: Integration** (Full Validation)
7. Remove xfail from Sprint 9 tests
8. Run integration tests
9. Debug any failures
10. Remove xfail from benchmarks

**Stage 4: Validation** (CI Ready)
11. Run full test suite locally
12. Run coverage report
13. Fix any regressions
14. Ready for commit

### 7.3 Validation Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests only
pytest tests/unit/test_database_lifecycle.py -v

# Run Sprint 9 integration tests
pytest tests/integration/test_sprint9_integration.py -v -k database

# Run full test suite
pytest -v

# Run coverage report
pytest --cov=common --cov=lib --cov-report=html --cov-report=term

# Run benchmarks (validate they execute)
pytest tests/benchmarks/test_performance.py -v
```

### 7.4 Rollback Plan

If implementation fails or causes regressions:

1. **Revert commit**: `git revert HEAD`
2. **Re-add xfail markers**: Restore to Sprint 9 state
3. **Investigate issue**: Debug with isolated test case
4. **Re-implement**: Follow SPEC more carefully
5. **Validate in stages**: Don't skip validation steps

### 7.5 Post-Implementation

- [ ] Update issue #50: Close with implementation summary
- [ ] Update Sprint 10 PRD: Mark Sortie 1 complete
- [ ] Create Sortie 2 branch: `sortie-2-stats-command`
- [ ] Plan Sortie 2 implementation: Stats command via NATS request/reply

---

## 8. Dependencies and Risks

### 8.1 Dependencies

**External Dependencies**:
- `aiosqlite>=0.19.0` (new dependency - stable package)
- NATS container in CI (from Sprint 9 - ✅ working)
- pytest-asyncio (existing dependency)

**Internal Dependencies**:
- None - this is the foundation sortie

**Blocking**:
- Sortie 2 (Stats Command) - needs async database
- Sortie 4 (Performance Benchmarks) - needs async database
- Sprint 11+ features - require stable test infrastructure

### 8.2 Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| aiosqlite compatibility issues | Low | API is compatible with sqlite3, well-tested |
| Breaking sync database usage | Medium | Backward compatibility via try/except in __init__ |
| Test pollution between tests | Medium | temp_database fixture creates isolated databases |
| Performance regression | Low | aiosqlite is optimized, no expected slowdown |
| CI timeout with 22 more tests | Low | Tests run in <2 minutes currently, plenty of margin |

### 8.3 Breaking Changes (v0.5.0 Alpha)

**Sprint 10**: Clean async-only implementation
- Remove: `_connect()` and `_create_tables()` sync methods
- Change: Database no longer auto-connects in `__init__`
- Require: All code must call `await db.connect()` after instantiation

**Impact**: Any code using BotDatabase must be updated:
```python
# OLD (Sprint 9):
db = BotDatabase('bot.db')  # Auto-connected

# NEW (Sprint 10):
db = BotDatabase('bot.db')
await db.connect()          # Required
```

**Justification**: v0.5.0 is alpha - breaking changes expected for better architecture

---

## 9. Related Issues

**Closes**: 
- Issue #50: Implement BotDatabase.connect() for Sprint 9 Tests

**Unblocks**:
- Issue #45: Stats Command Disabled (Sortie 2)
- Issue #51: Performance Tests Fail at Module Level (Sortie 4)
- Issue #48: Database Stats Integration Needs Update (Sortie 2)

**Related**:
- Sprint 9 PRD: NATS Event Bus Architecture (completed)
- Sprint 10 PRD: Test Infrastructure Completion (this sprint)

---

## 10. Success Metrics

### 10.1 Test Metrics

**Before Sortie 1**:
- Tests passing: 1,167 (94.9%)
- Tests xfailed: 31 (2.5%)
- Tests skipped: 16 (1.3%)
- Coverage: 66.41%

**After Sortie 1** (Target):
- Tests passing: 1,179 (96.1%) - **+12 tests** ✅
- Tests xfailed: 19 (1.5%) - **-12 xfails** ✅
- Tests skipped: 16 (1.3%)
- Coverage: ≥66% (maintained)

**Sprint 10 Complete** (After all 4 sorties):
- Tests passing: 1,198 (97.6%) - **+31 tests** 🎯
- Tests xfailed: 0 (0%) - **-31 xfails** 🎯
- Tests skipped: 16 (1.3%)
- Coverage: ≥75% (target)

### 10.2 Development Velocity

**Sprint 9**: 6 days to implement NATS architecture
**Sprint 10 Goal**: 4 days to complete test infrastructure

**Sortie 1 Velocity**:
- Estimated: 6-8 hours (1 day)
- Implementation: 4 hours
- Testing: 2 hours
- Validation: 1 hour
- Documentation: 1 hour

### 10.3 Quality Metrics

- ✅ All database tests pass without xfail
- ✅ No test pollution detected
- ✅ CI passes in <2 minutes (no timeout)
- ✅ Zero regressions in existing tests
- ✅ 100% coverage of new connection methods

---

## Appendix A: Example Usage

### A.1 Test Usage (After Sortie 1)

```python
# tests/integration/test_my_feature.py

@pytest.mark.asyncio
async def test_user_statistics(temp_database):
    """Test user statistics tracking."""
    # Database already connected by fixture
    
    # Track user join
    await temp_database.user_joined('Alice')
    
    # Track chat message
    await temp_database.user_chat_message('Alice', 'Hello!')
    
    # Get stats
    stats = await temp_database.get_user_stats('Alice')
    
    # Assertions
    assert stats is not None
    assert stats['username'] == 'Alice'
    assert stats['total_chat_lines'] == 1
    
    # Database auto-closed by fixture
```

### A.2 Production Usage (Sprint 10+)

```python
# Production code (async-only)

async def main():
    """Bot main loop with async database."""
    # Initialize database
    db = BotDatabase('bot_data.db')
    await db.connect()
    
    try:
        # Use database
        await db.user_joined('Alice')
        stats = await db.get_user_stats('Alice')
        
    finally:
        # Always close
        await db.close()
```

---

## Appendix B: Database Schema

**Tables Created by _run_migrations()**:

1. **user_stats**: User statistics (chat lines, time connected)
2. **user_actions**: Audit log for PM commands
3. **channel_stats**: High water marks for user counts
4. **user_count_history**: Historical user count data for graphs
5. **recent_chat**: Last N chat messages (150 hour retention)
6. **current_status**: Live bot state (single row)
7. **outbound_messages**: Message queue with retry logic
8. **api_tokens**: Authentication tokens for external apps

**No Schema Changes**: Sortie 1 uses existing Sprint 9 schema.

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for Implementation ✅
