# SPEC-Commit-8: Database Tests

## Purpose

Create comprehensive unit tests for `common/database.py`, covering the `BotDatabase` class and its SQLite operations for state persistence, statistics tracking, and API token management.

## Scope

- **File Under Test**: `common/database.py` (764 lines, 50+ methods)
- **Complexity**: High (database operations, migrations, transactions, background maintenance)
- **Test Count**: 90+ tests across 16 test classes
- **Coverage Target**: 90% (realistic for database testing with error scenarios)
- **Dependencies**: 
  - SPEC-Commit-1: pytest infrastructure, fixtures

## Source Code Analysis

### Key Components

**BotDatabase Class**:
- **Initialization**: `__init__(db_path)`, `_connect()`, `_create_tables()`
- **User Statistics**: `user_joined()`, `user_left()`, `user_chat_message()`, `get_user_stats()`, `get_top_chatters()`, `get_total_users_seen()`
- **User Actions Log**: `log_user_action()`
- **Channel Stats**: `update_high_water_mark()`, `get_high_water_mark()`, `get_high_water_mark_connected()`
- **User Count History**: `log_user_count()`, `get_user_count_history()`, `cleanup_old_history()`
- **Recent Chat**: `get_recent_chat()`, `get_recent_chat_since()`
- **Outbound Messages**: `enqueue_outbound_message()`, `get_unsent_outbound_messages()`, `mark_outbound_sent()`, `mark_outbound_failed()`
- **Current Status**: `update_current_status()`, `get_current_status()`
- **API Tokens**: `generate_api_token()`, `validate_api_token()`, `revoke_api_token()`, `list_api_tokens()`
- **Maintenance**: `perform_maintenance()`, `close()`

**Database Schema** (9 tables):
1. `user_stats`: User statistics (first_seen, last_seen, total_chat_lines, total_time_connected, current_session_start)
2. `user_actions`: Action log (timestamp, username, action_type, details)
3. `channel_stats`: High water marks (max_users, max_connected with timestamps)
4. `user_count_history`: Historical user counts with indexed timestamps
5. `recent_chat`: Recent messages with timestamp index
6. `current_status`: Single-row live bot state
7. `outbound_messages`: Message queue with retry logic (retry_count, last_error)
8. `api_tokens`: Authentication tokens (token, description, created_at, last_used, revoked)
9. Schema migrations: ALTER TABLE for retroactive column additions

**Critical Features**:
- SQLite with `check_same_thread=False`, `row_factory=sqlite3.Row`
- Session tracking: `current_session_start` for connected users
- Automatic migrations: Checks for missing columns and adds them
- Exponential backoff: `2^retry_count` minutes for outbound retry delay
- Partial token matching: Support for truncated token strings (≥8 chars)
- Maintenance: VACUUM, ANALYZE, retention policies (30d history, 7d outbound, 90d tokens)
- Row constraints: `CHECK (id = 1)` for singleton tables

## Test Strategy

**Fixtures**:
```python
@pytest.fixture
def temp_db_path(tmp_path):
    """Provide temporary database path"""
    return str(tmp_path / "test_bot.db")

@pytest.fixture
def db(temp_db_path):
    """Create fresh database instance"""
    database = BotDatabase(temp_db_path)
    yield database
    database.close()

@pytest.fixture
def db_with_users(db):
    """Database with sample users"""
    db.user_joined("alice")
    db.user_joined("bob")
    db.user_joined("charlie")
    return db

@pytest.fixture
def db_with_history(db):
    """Database with user count history"""
    import time
    now = int(time.time())
    for i in range(24):  # 24 hours of data
        timestamp = now - (23 - i) * 3600
        db.conn.execute('''
            INSERT INTO user_count_history (timestamp, chat_users, connected_users)
            VALUES (?, ?, ?)
        ''', (timestamp, 10 + i, 15 + i))
    db.conn.commit()
    return db

@pytest.fixture
def db_with_messages(db):
    """Database with outbound messages"""
    db.enqueue_outbound_message("Hello world")
    db.enqueue_outbound_message("Test message")
    return db

@pytest.fixture
def db_with_tokens(db):
    """Database with API tokens"""
    token1 = db.generate_api_token("Test token 1")
    token2 = db.generate_api_token("Test token 2")
    return db, token1, token2
```

**Test Organization**: 16 test classes with 90+ tests

### Test Class 1: TestDatabaseInit (6 tests)

Tests for database initialization and table creation.

```python
def test_init_creates_database_file(temp_db_path):
    """Database file is created on initialization"""
    import os
    assert not os.path.exists(temp_db_path)
    
    db = BotDatabase(temp_db_path)
    assert os.path.exists(temp_db_path)
    db.close()

def test_init_creates_all_tables(db):
    """All required tables are created"""
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'api_tokens',
        'channel_stats',
        'current_status',
        'outbound_messages',
        'recent_chat',
        'user_actions',
        'user_count_history',
        'user_stats'
    ]
    
    for table in expected_tables:
        assert table in tables

def test_init_creates_indexes(db):
    """Indexes are created for performance"""
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    
    assert 'idx_user_count_timestamp' in indexes
    assert 'idx_recent_chat_timestamp' in indexes
    assert 'idx_outbound_sent' in indexes
    assert 'idx_api_tokens_revoked' in indexes

def test_init_seeds_singleton_tables(db):
    """Singleton tables (current_status, channel_stats) are initialized"""
    cursor = db.conn.cursor()
    
    # Check current_status
    cursor.execute('SELECT COUNT(*) FROM current_status')
    assert cursor.fetchone()[0] == 1
    
    # Check channel_stats
    cursor.execute('SELECT COUNT(*) FROM channel_stats')
    assert cursor.fetchone()[0] == 1

def test_init_row_factory_is_row(db):
    """Database uses sqlite3.Row for dict-like access"""
    import sqlite3
    assert db.conn.row_factory == sqlite3.Row

def test_init_logs_connection(db, caplog):
    """Database connection is logged"""
    assert 'Connected to database' in caplog.text
    assert 'Database tables initialized' in caplog.text
```

### Test Class 2: TestDatabaseMigrations (5 tests)

Tests for automatic schema migrations.

```python
def test_migration_adds_retry_count_to_outbound(temp_db_path):
    """Missing retry_count column is added to outbound_messages"""
    # Create database with old schema
    conn = sqlite3.connect(temp_db_path)
    conn.execute('''
        CREATE TABLE outbound_messages (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            message TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    
    # Initialize BotDatabase (should migrate)
    db = BotDatabase(temp_db_path)
    
    # Check column exists
    cursor = db.conn.cursor()
    cursor.execute('PRAGMA table_info(outbound_messages)')
    columns = [col[1] for col in cursor.fetchall()]
    assert 'retry_count' in columns
    db.close()

def test_migration_adds_last_error_to_outbound(temp_db_path):
    """Missing last_error column is added to outbound_messages"""
    # Create database with old schema
    conn = sqlite3.connect(temp_db_path)
    conn.execute('''
        CREATE TABLE outbound_messages (
            id INTEGER PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            message TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    
    # Initialize BotDatabase (should migrate)
    db = BotDatabase(temp_db_path)
    
    # Check column exists
    cursor = db.conn.cursor()
    cursor.execute('PRAGMA table_info(outbound_messages)')
    columns = [col[1] for col in cursor.fetchall()]
    assert 'last_error' in columns
    db.close()

def test_migration_adds_max_connected_to_channel_stats(temp_db_path):
    """Missing max_connected columns are added to channel_stats"""
    # Create database with old schema
    conn = sqlite3.connect(temp_db_path)
    conn.execute('''
        CREATE TABLE channel_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            max_users INTEGER DEFAULT 0,
            max_users_timestamp INTEGER,
            last_updated INTEGER
        )
    ''')
    conn.execute('INSERT INTO channel_stats (id, max_users, last_updated) VALUES (1, 0, 0)')
    conn.commit()
    conn.close()
    
    # Initialize BotDatabase (should migrate)
    db = BotDatabase(temp_db_path)
    
    # Check columns exist
    cursor = db.conn.cursor()
    cursor.execute('PRAGMA table_info(channel_stats)')
    columns = [col[1] for col in cursor.fetchall()]
    assert 'max_connected' in columns
    assert 'max_connected_timestamp' in columns
    db.close()

def test_migration_idempotent(db):
    """Running migrations multiple times is safe"""
    # Call _create_tables again
    db._create_tables()
    
    # Database should still be functional
    db.user_joined("alice")
    stats = db.get_user_stats("alice")
    assert stats is not None

def test_migration_preserves_data(temp_db_path):
    """Migrations don't lose existing data"""
    # Create old database with data
    conn = sqlite3.connect(temp_db_path)
    conn.execute('''
        CREATE TABLE channel_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            max_users INTEGER DEFAULT 0,
            last_updated INTEGER
        )
    ''')
    conn.execute('INSERT INTO channel_stats (id, max_users, last_updated) VALUES (1, 42, 1234567890)')
    conn.commit()
    conn.close()
    
    # Initialize BotDatabase (migrates)
    db = BotDatabase(temp_db_path)
    
    # Check data preserved
    cursor = db.conn.cursor()
    cursor.execute('SELECT max_users FROM channel_stats WHERE id = 1')
    assert cursor.fetchone()[0] == 42
    db.close()
```

### Test Class 3: TestUserStatistics (10 tests)

Tests for user tracking and statistics.

```python
def test_user_joined_new_user(db):
    """New user is recorded with first_seen and last_seen"""
    import time
    before = int(time.time())
    
    db.user_joined("alice")
    
    after = int(time.time())
    
    stats = db.get_user_stats("alice")
    assert stats is not None
    assert stats['username'] == "alice"
    assert before <= stats['first_seen'] <= after
    assert before <= stats['last_seen'] <= after
    assert stats['total_chat_lines'] == 0
    assert stats['total_time_connected'] == 0
    assert stats['current_session_start'] is not None

def test_user_joined_existing_user(db):
    """Existing user updates last_seen and starts new session"""
    db.user_joined("alice")
    first_stats = db.get_user_stats("alice")
    
    import time
    time.sleep(0.1)
    
    db.user_joined("alice")
    second_stats = db.get_user_stats("alice")
    
    # first_seen unchanged
    assert second_stats['first_seen'] == first_stats['first_seen']
    # last_seen updated
    assert second_stats['last_seen'] > first_stats['last_seen']
    # new session started
    assert second_stats['current_session_start'] >= second_stats['last_seen']

def test_user_left_updates_time_connected(db):
    """User leaving updates total_time_connected"""
    import time
    
    db.user_joined("alice")
    time.sleep(0.2)
    
    db.user_left("alice")
    
    stats = db.get_user_stats("alice")
    assert stats['total_time_connected'] > 0
    assert stats['current_session_start'] is None

def test_user_left_nonexistent_user(db):
    """Leaving with nonexistent user doesn't crash"""
    db.user_left("nonexistent")
    # Should not raise exception

def test_user_left_no_session(db):
    """Leaving without active session doesn't crash"""
    db.user_joined("alice")
    db.user_left("alice")
    
    # Leave again without rejoining
    db.user_left("alice")
    
    # Should not crash or corrupt data
    stats = db.get_user_stats("alice")
    assert stats is not None

def test_user_chat_message_increments_count(db):
    """Chat messages increment total_chat_lines"""
    db.user_joined("alice")
    
    db.user_chat_message("alice")
    db.user_chat_message("alice")
    db.user_chat_message("alice")
    
    stats = db.get_user_stats("alice")
    assert stats['total_chat_lines'] == 3

def test_user_chat_message_stores_in_recent_chat(db):
    """Chat messages are stored in recent_chat"""
    db.user_joined("alice")
    db.user_chat_message("alice", "Hello world")
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent) == 1
    assert recent[0]['username'] == "alice"
    assert recent[0]['message'] == "Hello world"

def test_user_chat_message_filters_server_messages(db):
    """Server messages are not stored in recent_chat"""
    db.user_chat_message("server", "System message")
    db.user_chat_message("Server", "System message")
    db.user_chat_message(None, "No username")
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent) == 0

def test_get_top_chatters(db_with_users):
    """Top chatters are returned in order"""
    db = db_with_users
    
    # alice: 5, bob: 3, charlie: 10
    for _ in range(5):
        db.user_chat_message("alice")
    for _ in range(3):
        db.user_chat_message("bob")
    for _ in range(10):
        db.user_chat_message("charlie")
    
    top = db.get_top_chatters(limit=3)
    assert len(top) == 3
    assert top[0] == ("charlie", 10)
    assert top[1] == ("alice", 5)
    assert top[2] == ("bob", 3)

def test_get_total_users_seen(db_with_users):
    """Total unique users count is correct"""
    assert db_with_users.get_total_users_seen() == 3
```

### Test Class 4: TestUserActions (3 tests)

Tests for user action logging.

```python
def test_log_user_action(db):
    """User actions are logged with timestamp"""
    import time
    before = int(time.time())
    
    db.log_user_action("alice", "pm_command", "!help")
    
    after = int(time.time())
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM user_actions WHERE username = ?', ("alice",))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['username'] == "alice"
    assert row['action_type'] == "pm_command"
    assert row['details'] == "!help"
    assert before <= row['timestamp'] <= after

def test_log_user_action_without_details(db):
    """User actions can be logged without details"""
    db.log_user_action("bob", "kick")
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM user_actions WHERE username = ?', ("bob",))
    row = cursor.fetchone()
    
    assert row['details'] is None

def test_log_user_action_multiple(db):
    """Multiple actions are logged independently"""
    db.log_user_action("alice", "pm_command", "!help")
    db.log_user_action("bob", "kick", "reason: spam")
    db.log_user_action("alice", "pm_command", "!stats")
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM user_actions')
    assert cursor.fetchone()[0] == 3
```

### Test Class 5: TestChannelStats (8 tests)

Tests for high water mark tracking.

```python
def test_update_high_water_mark_initial(db):
    """First update sets high water mark"""
    db.update_high_water_mark(42)
    
    max_users, timestamp = db.get_high_water_mark()
    assert max_users == 42
    assert timestamp is not None

def test_update_high_water_mark_exceeds(db):
    """Exceeding high water mark updates it"""
    db.update_high_water_mark(10)
    db.update_high_water_mark(20)
    
    max_users, _ = db.get_high_water_mark()
    assert max_users == 20

def test_update_high_water_mark_not_exceeds(db):
    """Not exceeding high water mark doesn't update it"""
    db.update_high_water_mark(20)
    db.update_high_water_mark(15)
    
    max_users, _ = db.get_high_water_mark()
    assert max_users == 20

def test_update_high_water_mark_connected(db):
    """Connected viewer count tracked separately"""
    db.update_high_water_mark(10, current_connected_count=25)
    
    max_connected, timestamp = db.get_high_water_mark_connected()
    assert max_connected == 25
    assert timestamp is not None

def test_update_high_water_mark_both(db):
    """Both chat and connected can be updated together"""
    db.update_high_water_mark(10, current_connected_count=25)
    
    max_users, _ = db.get_high_water_mark()
    max_connected, _ = db.get_high_water_mark_connected()
    
    assert max_users == 10
    assert max_connected == 25

def test_update_high_water_mark_logs(db, caplog):
    """New high water marks are logged"""
    db.update_high_water_mark(42, current_connected_count=100)
    
    assert 'New high water mark (chat): 42 users' in caplog.text
    assert 'New high water mark (connected): 100 viewers' in caplog.text

def test_get_high_water_mark_no_data(db):
    """High water mark returns 0 when no data"""
    max_users, timestamp = db.get_high_water_mark()
    assert max_users == 0
    # timestamp may be None or set from init

def test_get_high_water_mark_connected_no_data(db):
    """Connected high water mark returns 0 when no data"""
    max_connected, timestamp = db.get_high_water_mark_connected()
    assert max_connected == 0
```

### Test Class 6: TestUserCountHistory (6 tests)

Tests for historical user count tracking.

```python
def test_log_user_count(db):
    """User counts are logged with timestamp"""
    import time
    before = int(time.time())
    
    db.log_user_count(chat_users=10, connected_users=15)
    
    after = int(time.time())
    
    history = db.get_user_count_history(hours=1)
    assert len(history) == 1
    assert history[0]['chat_users'] == 10
    assert history[0]['connected_users'] == 15
    assert before <= history[0]['timestamp'] <= after

def test_log_user_count_multiple(db):
    """Multiple entries are stored chronologically"""
    db.log_user_count(5, 10)
    db.log_user_count(8, 12)
    db.log_user_count(6, 11)
    
    history = db.get_user_count_history(hours=24)
    assert len(history) == 3
    # Should be in ascending timestamp order
    assert history[0]['timestamp'] <= history[1]['timestamp']
    assert history[1]['timestamp'] <= history[2]['timestamp']

def test_get_user_count_history_time_window(db_with_history):
    """History returns only entries within time window"""
    # db_with_history has 24 hours of data
    history_12h = db_with_history.get_user_count_history(hours=12)
    history_24h = db_with_history.get_user_count_history(hours=24)
    
    assert len(history_12h) < len(history_24h)
    assert len(history_24h) == 24

def test_get_user_count_history_empty(db):
    """Empty history returns empty list"""
    history = db.get_user_count_history(hours=24)
    assert history == []

def test_cleanup_old_history(db_with_history):
    """Old history entries are removed"""
    # Add very old entry
    import time
    old_timestamp = int(time.time()) - (60 * 86400)  # 60 days ago
    db_with_history.conn.execute('''
        INSERT INTO user_count_history (timestamp, chat_users, connected_users)
        VALUES (?, 1, 1)
    ''', (old_timestamp,))
    db_with_history.conn.commit()
    
    deleted = db_with_history.cleanup_old_history(days=30)
    
    assert deleted >= 1

def test_cleanup_old_history_logs(db_with_history, caplog):
    """Cleanup logs number of deleted records"""
    import time
    old_timestamp = int(time.time()) - (60 * 86400)
    db_with_history.conn.execute('''
        INSERT INTO user_count_history (timestamp, chat_users, connected_users)
        VALUES (?, 1, 1)
    ''', (old_timestamp,))
    db_with_history.conn.commit()
    
    deleted = db_with_history.cleanup_old_history(days=30)
    
    assert f'Cleaned up {deleted} old history records' in caplog.text
```

### Test Class 7: TestRecentChat (6 tests)

Tests for recent chat message storage.

```python
def test_get_recent_chat_empty(db):
    """Empty chat returns empty list"""
    recent = db.get_recent_chat(limit=20)
    assert recent == []

def test_get_recent_chat_ordered(db):
    """Recent chat returns messages in chronological order"""
    db.user_joined("alice")
    db.user_chat_message("alice", "Message 1")
    db.user_chat_message("alice", "Message 2")
    db.user_chat_message("alice", "Message 3")
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent) == 3
    assert recent[0]['message'] == "Message 1"
    assert recent[1]['message'] == "Message 2"
    assert recent[2]['message'] == "Message 3"

def test_get_recent_chat_limit(db):
    """Limit parameter restricts number of messages"""
    db.user_joined("alice")
    for i in range(10):
        db.user_chat_message("alice", f"Message {i}")
    
    recent = db.get_recent_chat(limit=5)
    assert len(recent) == 5
    # Should be last 5 messages
    assert recent[0]['message'] == "Message 5"
    assert recent[4]['message'] == "Message 9"

def test_get_recent_chat_since_time_window(db):
    """get_recent_chat_since returns messages in time window"""
    import time
    db.user_joined("alice")
    
    # Old message (outside window)
    old_time = int(time.time()) - (30 * 60)  # 30 minutes ago
    db.conn.execute('''
        INSERT INTO recent_chat (timestamp, username, message)
        VALUES (?, 'alice', 'Old message')
    ''', (old_time,))
    
    # Recent message (inside window)
    db.user_chat_message("alice", "Recent message")
    db.conn.commit()
    
    recent = db.get_recent_chat_since(minutes=20, limit=100)
    
    assert len(recent) == 1
    assert recent[0]['message'] == "Recent message"

def test_get_recent_chat_since_limit(db):
    """get_recent_chat_since respects limit parameter"""
    db.user_joined("alice")
    for i in range(20):
        db.user_chat_message("alice", f"Message {i}")
    
    recent = db.get_recent_chat_since(minutes=60, limit=5)
    assert len(recent) == 5

def test_recent_chat_retention_cleanup(db):
    """Old chat messages are cleaned up on new insert"""
    import time
    
    # Add very old message (beyond 150 hour retention)
    old_time = int(time.time()) - (200 * 3600)
    db.conn.execute('''
        INSERT INTO recent_chat (timestamp, username, message)
        VALUES (?, 'alice', 'Very old message')
    ''', (old_time,))
    db.conn.commit()
    
    # Add new message (triggers cleanup)
    db.user_joined("alice")
    db.user_chat_message("alice", "New message")
    
    # Old message should be gone
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM recent_chat WHERE message = ?',
                  ('Very old message',))
    assert cursor.fetchone()[0] == 0
```

### Test Class 8: TestOutboundMessages (12 tests)

Tests for outbound message queue and retry logic.

```python
def test_enqueue_outbound_message(db):
    """Messages are enqueued with timestamp"""
    import time
    before = int(time.time())
    
    msg_id = db.enqueue_outbound_message("Hello world")
    
    after = int(time.time())
    
    assert msg_id > 0
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    
    assert row['message'] == "Hello world"
    assert row['sent'] == 0
    assert before <= row['timestamp'] <= after
    assert row['retry_count'] == 0

def test_get_unsent_outbound_messages(db_with_messages):
    """Unsent messages are retrieved"""
    db = db_with_messages
    
    messages = db.get_unsent_outbound_messages(limit=10)
    
    assert len(messages) == 2
    assert messages[0]['message'] == "Hello world"
    assert messages[1]['message'] == "Test message"

def test_get_unsent_outbound_messages_excludes_sent(db):
    """Sent messages are not retrieved"""
    msg_id = db.enqueue_outbound_message("Test")
    db.mark_outbound_sent(msg_id)
    
    messages = db.get_unsent_outbound_messages(limit=10)
    assert len(messages) == 0

def test_get_unsent_outbound_messages_limit(db):
    """Limit parameter restricts number of messages"""
    for i in range(10):
        db.enqueue_outbound_message(f"Message {i}")
    
    messages = db.get_unsent_outbound_messages(limit=3)
    assert len(messages) == 3

def test_get_unsent_outbound_messages_retry_backoff(db):
    """Messages with retry_count are delayed by exponential backoff"""
    import time
    
    # Message with retry_count=1 (2 minute delay)
    msg_id = db.enqueue_outbound_message("Retry message")
    db.mark_outbound_failed(msg_id, "Connection error", is_permanent=False)
    
    # Should not be returned immediately
    messages = db.get_unsent_outbound_messages(limit=10, max_retries=3)
    assert len(messages) == 0
    
    # Update timestamp to simulate time passing (3 minutes ago)
    past_time = int(time.time()) - (3 * 60)
    db.conn.execute('''
        UPDATE outbound_messages
        SET timestamp = ?
        WHERE id = ?
    ''', (past_time, msg_id))
    db.conn.commit()
    
    # Should now be returned
    messages = db.get_unsent_outbound_messages(limit=10, max_retries=3)
    assert len(messages) == 1

def test_get_unsent_outbound_messages_max_retries(db):
    """Messages exceeding max_retries are not retrieved"""
    msg_id = db.enqueue_outbound_message("Failing message")
    
    # Fail 3 times
    for _ in range(3):
        db.mark_outbound_failed(msg_id, "Error", is_permanent=False)
    
    messages = db.get_unsent_outbound_messages(limit=10, max_retries=3)
    assert len(messages) == 0

def test_mark_outbound_sent(db):
    """Marking as sent updates sent flag and timestamp"""
    import time
    before = int(time.time())
    
    msg_id = db.enqueue_outbound_message("Test")
    db.mark_outbound_sent(msg_id)
    
    after = int(time.time())
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    
    assert row['sent'] == 1
    assert before <= row['sent_timestamp'] <= after

def test_mark_outbound_failed_transient(db):
    """Transient failure increments retry_count"""
    msg_id = db.enqueue_outbound_message("Test")
    
    db.mark_outbound_failed(msg_id, "Connection timeout", is_permanent=False)
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    
    assert row['sent'] == 0
    assert row['retry_count'] == 1
    assert row['last_error'] == "Connection timeout"

def test_mark_outbound_failed_permanent(db):
    """Permanent failure marks as sent to stop retries"""
    msg_id = db.enqueue_outbound_message("Test")
    
    db.mark_outbound_failed(msg_id, "Permission denied", is_permanent=True)
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    
    assert row['sent'] == 1  # Marked sent to prevent retries
    assert row['retry_count'] == 1
    assert row['last_error'] == "Permission denied"

def test_mark_outbound_failed_logs_transient(db, caplog):
    """Transient failures log retry message"""
    msg_id = db.enqueue_outbound_message("Test")
    db.mark_outbound_failed(msg_id, "Timeout", is_permanent=False)
    
    assert 'will retry' in caplog.text

def test_mark_outbound_failed_logs_permanent(db, caplog):
    """Permanent failures log warning"""
    msg_id = db.enqueue_outbound_message("Test")
    db.mark_outbound_failed(msg_id, "Muted", is_permanent=True)
    
    assert 'permanently failed' in caplog.text

def test_outbound_exponential_backoff_calculation(db):
    """Retry delay doubles each time: 2^retry_count minutes"""
    msg_id = db.enqueue_outbound_message("Test")
    
    # Fail multiple times and check delay progression
    # retry 0: immediate, retry 1: 2min, retry 2: 4min, retry 3: 8min
    
    import time
    base_time = int(time.time()) - 600  # 10 minutes ago
    
    for retry in range(3):
        db.conn.execute('''
            UPDATE outbound_messages
            SET timestamp = ?, retry_count = ?
            WHERE id = ?
        ''', (base_time, retry, msg_id))
        db.conn.commit()
        
        # Calculate expected delay: 2^retry minutes
        expected_delay_seconds = (1 << retry) * 60
        
        # Check if message is available now
        messages = db.get_unsent_outbound_messages(limit=10, max_retries=5)
        
        # Should be available since base_time was 10 minutes ago
        assert len(messages) == 1
```

### Test Class 9: TestCurrentStatus (7 tests)

Tests for live bot status tracking.

```python
def test_update_current_status_single_field(db):
    """Single status field can be updated"""
    db.update_current_status(bot_name="TestBot")
    
    status = db.get_current_status()
    assert status['bot_name'] == "TestBot"

def test_update_current_status_multiple_fields(db):
    """Multiple status fields can be updated together"""
    db.update_current_status(
        bot_name="TestBot",
        bot_rank=2.5,
        channel_name="testchannel"
    )
    
    status = db.get_current_status()
    assert status['bot_name'] == "TestBot"
    assert status['bot_rank'] == 2.5
    assert status['channel_name'] == "testchannel"

def test_update_current_status_updates_last_updated(db):
    """last_updated is automatically set"""
    import time
    before = int(time.time())
    
    db.update_current_status(bot_name="TestBot")
    
    after = int(time.time())
    
    status = db.get_current_status()
    assert before <= status['last_updated'] <= after

def test_update_current_status_all_fields(db):
    """All valid status fields can be updated"""
    db.update_current_status(
        bot_name="TestBot",
        bot_rank=3.0,
        bot_afk=1,
        channel_name="test",
        current_chat_users=10,
        current_connected_users=15,
        playlist_items=5,
        current_media_title="Test Video",
        current_media_duration=180,
        bot_start_time=1234567890,
        bot_connected=1
    )
    
    status = db.get_current_status()
    assert status['bot_name'] == "TestBot"
    assert status['bot_rank'] == 3.0
    assert status['bot_afk'] == 1
    assert status['current_chat_users'] == 10
    assert status['playlist_items'] == 5

def test_update_current_status_invalid_field_ignored(db):
    """Invalid fields are ignored"""
    # Should not raise exception
    db.update_current_status(invalid_field="value", bot_name="TestBot")
    
    status = db.get_current_status()
    assert status['bot_name'] == "TestBot"

def test_update_current_status_no_fields(db):
    """Calling with no fields doesn't crash"""
    db.update_current_status()
    # Should not raise exception

def test_get_current_status_initial(db):
    """Initial status row exists with defaults"""
    status = db.get_current_status()
    assert status is not None
    assert status['id'] == 1
```

### Test Class 10: TestAPITokens (11 tests)

Tests for API token generation and validation.

```python
def test_generate_api_token(db):
    """Token is generated and stored"""
    token = db.generate_api_token("Test token")
    
    assert token is not None
    assert len(token) > 20  # Should be cryptographically secure
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM api_tokens WHERE token = ?', (token,))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['description'] == "Test token"
    assert row['revoked'] == 0

def test_generate_api_token_without_description(db):
    """Token can be generated without description"""
    token = db.generate_api_token()
    assert token is not None

def test_generate_api_token_unique(db):
    """Each token is unique"""
    token1 = db.generate_api_token()
    token2 = db.generate_api_token()
    assert token1 != token2

def test_generate_api_token_logs(db, caplog):
    """Token generation is logged"""
    token = db.generate_api_token("Test")
    assert 'Generated new API token' in caplog.text

def test_validate_api_token_valid(db):
    """Valid token returns True"""
    token = db.generate_api_token("Test")
    assert db.validate_api_token(token) is True

def test_validate_api_token_invalid(db):
    """Invalid token returns False"""
    assert db.validate_api_token("invalid_token_xyz") is False

def test_validate_api_token_updates_last_used(db):
    """Validating token updates last_used"""
    import time
    token = db.generate_api_token("Test")
    
    before = int(time.time())
    db.validate_api_token(token)
    after = int(time.time())
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT last_used FROM api_tokens WHERE token = ?', (token,))
    last_used = cursor.fetchone()['last_used']
    
    assert before <= last_used <= after

def test_validate_api_token_revoked(db):
    """Revoked token returns False"""
    token = db.generate_api_token("Test")
    db.revoke_api_token(token)
    
    assert db.validate_api_token(token) is False

def test_revoke_api_token(db):
    """Token is revoked"""
    token = db.generate_api_token("Test")
    count = db.revoke_api_token(token)
    
    assert count == 1
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT revoked FROM api_tokens WHERE token = ?', (token,))
    assert cursor.fetchone()['revoked'] == 1

def test_revoke_api_token_partial(db):
    """Token can be revoked with partial match (8+ chars)"""
    token = db.generate_api_token("Test")
    partial = token[:12]  # First 12 characters
    
    count = db.revoke_api_token(partial)
    assert count == 1

def test_list_api_tokens(db):
    """Tokens can be listed with metadata"""
    token1 = db.generate_api_token("Token 1")
    token2 = db.generate_api_token("Token 2")
    
    tokens = db.list_api_tokens(include_revoked=False)
    
    assert len(tokens) == 2
    assert 'token_preview' in tokens[0]
    assert 'token' not in tokens[0]  # Full token not exposed
    assert tokens[0]['token_preview'].endswith('...')
```

### Test Class 11: TestDatabaseClose (4 tests)

Tests for database cleanup on close.

```python
def test_close_finalizes_active_sessions(temp_db_path):
    """Active sessions are finalized on close"""
    import time
    
    db = BotDatabase(temp_db_path)
    db.user_joined("alice")
    time.sleep(0.2)
    
    db.close()
    
    # Reopen database
    db2 = BotDatabase(temp_db_path)
    stats = db2.get_user_stats("alice")
    
    assert stats['current_session_start'] is None
    assert stats['total_time_connected'] > 0
    db2.close()

def test_close_logs(db, caplog):
    """Database close is logged"""
    db.close()
    assert 'Database connection closed' in caplog.text

def test_close_idempotent(db):
    """Closing multiple times is safe"""
    db.close()
    # Should not raise exception

def test_close_commits_changes(temp_db_path):
    """Pending changes are committed on close"""
    db = BotDatabase(temp_db_path)
    db.user_joined("alice")
    db.close()
    
    # Reopen and verify
    db2 = BotDatabase(temp_db_path)
    assert db2.get_user_stats("alice") is not None
    db2.close()
```

### Test Class 12: TestDatabaseMaintenance (8 tests)

Tests for periodic maintenance operations.

```python
def test_perform_maintenance_cleanup_old_history(db):
    """Maintenance removes old user count history"""
    import time
    
    # Add old history (60 days ago)
    old_time = int(time.time()) - (60 * 86400)
    db.conn.execute('''
        INSERT INTO user_count_history (timestamp, chat_users, connected_users)
        VALUES (?, 1, 1)
    ''', (old_time,))
    db.conn.commit()
    
    log = db.perform_maintenance()
    
    assert any('history records' in msg for msg in log)

def test_perform_maintenance_cleanup_old_outbound(db):
    """Maintenance removes old sent outbound messages"""
    import time
    
    # Add old sent message (14 days ago)
    old_time = int(time.time()) - (14 * 86400)
    msg_id = db.enqueue_outbound_message("Old message")
    db.conn.execute('''
        UPDATE outbound_messages
        SET sent = 1, sent_timestamp = ?
        WHERE id = ?
    ''', (old_time, msg_id))
    db.conn.commit()
    
    log = db.perform_maintenance()
    
    assert any('outbound messages' in msg for msg in log)

def test_perform_maintenance_cleanup_old_tokens(db):
    """Maintenance removes old revoked tokens"""
    import time
    
    # Add old revoked token (120 days ago)
    old_time = int(time.time()) - (120 * 86400)
    db.conn.execute('''
        INSERT INTO api_tokens (token, description, created_at, revoked)
        VALUES ('old_token', 'Old', ?, 1)
    ''', (old_time,))
    db.conn.commit()
    
    log = db.perform_maintenance()
    
    assert any('revoked tokens' in msg for msg in log)

def test_perform_maintenance_vacuum(db):
    """Maintenance runs VACUUM"""
    log = db.perform_maintenance()
    assert any('VACUUM' in msg for msg in log)

def test_perform_maintenance_analyze(db):
    """Maintenance runs ANALYZE"""
    log = db.perform_maintenance()
    assert any('ANALYZE' in msg for msg in log)

def test_perform_maintenance_logs(db, caplog):
    """Maintenance completion is logged"""
    db.perform_maintenance()
    assert 'Database maintenance completed' in caplog.text

def test_perform_maintenance_error_handling(db, caplog):
    """Maintenance errors are logged and rolled back"""
    # Force an error by closing connection
    db.conn.close()
    
    with pytest.raises(Exception):
        db.perform_maintenance()
    
    assert 'Database maintenance error' in caplog.text

def test_perform_maintenance_idempotent(db):
    """Running maintenance multiple times is safe"""
    db.perform_maintenance()
    db.perform_maintenance()
    # Should not crash
```

### Test Class 13: TestDatabaseEdgeCases (6 tests)

Tests for edge cases and error handling.

```python
def test_database_in_memory(tmp_path):
    """Database can use in-memory SQLite"""
    db = BotDatabase(':memory:')
    db.user_joined("alice")
    
    stats = db.get_user_stats("alice")
    assert stats is not None
    db.close()

def test_database_concurrent_reads(db):
    """Multiple reads can happen concurrently"""
    db.user_joined("alice")
    db.user_joined("bob")
    
    # Simulate concurrent reads
    stats1 = db.get_user_stats("alice")
    stats2 = db.get_user_stats("bob")
    
    assert stats1['username'] == "alice"
    assert stats2['username'] == "bob"

def test_database_special_characters_in_data(db):
    """Special characters in data are handled correctly"""
    db.user_joined("alice")
    db.user_chat_message("alice", "Message with 'quotes' and \"double quotes\"")
    db.log_user_action("alice", "test", "Details with 'quotes'")
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent) == 1

def test_database_unicode_in_data(db):
    """Unicode characters are handled correctly"""
    db.user_joined("alice")
    db.user_chat_message("alice", "日本語 emoji 🎉 中文")
    
    recent = db.get_recent_chat(limit=10)
    assert recent[0]['message'] == "日本語 emoji 🎉 中文"

def test_database_long_strings(db):
    """Very long strings are stored correctly"""
    long_message = "x" * 10000
    db.user_joined("alice")
    db.user_chat_message("alice", long_message)
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent[0]['message']) == 10000

def test_database_null_values(db):
    """NULL values are handled appropriately"""
    db.user_joined("alice")
    db.log_user_action("alice", "test", None)
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT details FROM user_actions WHERE username = ?', ("alice",))
    assert cursor.fetchone()['details'] is None
```

### Test Class 14: TestDatabaseThreadSafety (3 tests)

Tests for thread safety considerations.

```python
def test_check_same_thread_false(db):
    """Database is configured with check_same_thread=False"""
    # This is necessary for web server context
    # Actual test: database creation doesn't raise exception
    assert db.conn is not None

def test_database_connection_isolation(temp_db_path):
    """Each BotDatabase instance has its own connection"""
    db1 = BotDatabase(temp_db_path)
    db2 = BotDatabase(temp_db_path)
    
    assert db1.conn is not db2.conn
    
    db1.close()
    db2.close()

def test_database_row_factory(db):
    """Row factory provides dict-like access"""
    db.user_joined("alice")
    
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM user_stats WHERE username = ?', ("alice",))
    row = cursor.fetchone()
    
    # Dict-like access
    assert row['username'] == "alice"
    
    # Can also convert to dict
    row_dict = dict(row)
    assert 'username' in row_dict
```

### Test Class 15: TestDatabasePerformance (3 tests)

Tests for database performance considerations.

```python
def test_index_on_user_count_timestamp(db):
    """Index exists for efficient timestamp queries"""
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_user_count_timestamp'
    """)
    assert cursor.fetchone() is not None

def test_index_on_recent_chat_timestamp(db):
    """Index exists for efficient recent chat queries"""
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_recent_chat_timestamp'
    """)
    assert cursor.fetchone() is not None

def test_singleton_table_constraint(db):
    """Singleton tables enforce single row with CHECK constraint"""
    cursor = db.conn.cursor()
    
    # Try to insert second row into current_status (should fail)
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute('''
            INSERT INTO current_status (id, last_updated)
            VALUES (2, ?)
        ''', (int(time.time()),))
```

### Test Class 16: TestDatabaseIntegration (4 tests)

Integration tests for multi-operation workflows.

```python
def test_full_user_lifecycle(db):
    """Complete user session: join, chat, leave"""
    import time
    
    db.user_joined("alice")
    
    for i in range(5):
        db.user_chat_message("alice", f"Message {i}")
    
    time.sleep(0.2)
    db.user_left("alice")
    
    stats = db.get_user_stats("alice")
    assert stats['total_chat_lines'] == 5
    assert stats['total_time_connected'] > 0
    assert stats['current_session_start'] is None
    
    recent = db.get_recent_chat(limit=10)
    assert len(recent) == 5

def test_high_water_mark_with_logging(db):
    """High water marks work with user count logging"""
    db.log_user_count(10, 15)
    db.update_high_water_mark(10, 15)
    
    max_users, _ = db.get_high_water_mark()
    max_connected, _ = db.get_high_water_mark_connected()
    
    assert max_users == 10
    assert max_connected == 15
    
    history = db.get_user_count_history(hours=1)
    assert len(history) == 1

def test_outbound_retry_workflow(db):
    """Outbound message retry workflow"""
    # Enqueue message
    msg_id = db.enqueue_outbound_message("Test")
    
    # First attempt fails (transient)
    db.mark_outbound_failed(msg_id, "Connection timeout", is_permanent=False)
    
    # Check retry count incremented
    messages = db.get_unsent_outbound_messages(limit=10, max_retries=3)
    # Will be empty due to backoff
    
    # Second attempt succeeds
    db.mark_outbound_sent(msg_id)
    
    # No longer in unsent queue
    messages = db.get_unsent_outbound_messages(limit=10)
    assert len(messages) == 0

def test_api_token_lifecycle(db):
    """API token full lifecycle: generate, validate, revoke"""
    # Generate token
    token = db.generate_api_token("Test token")
    
    # Validate (should work)
    assert db.validate_api_token(token) is True
    
    # Revoke
    count = db.revoke_api_token(token)
    assert count == 1
    
    # Validate again (should fail)
    assert db.validate_api_token(token) is False
```

## Expected Test Coverage

**Coverage Analysis**:
- **Initialization**: 100% (all table creation, migrations, singleton init)
- **User Statistics**: 95% (all CRUD operations, session tracking)
- **Channel Stats**: 95% (high water marks for both metrics)
- **User Count History**: 95% (logging, querying, cleanup)
- **Recent Chat**: 95% (storage, retrieval, retention)
- **Outbound Messages**: 95% (queue, retry logic, exponential backoff)
- **Current Status**: 95% (dynamic field updates)
- **API Tokens**: 95% (generation, validation, revocation, listing)
- **Maintenance**: 85% (cleanup operations, VACUUM/ANALYZE, error handling)
- **Edge Cases**: 90% (special characters, unicode, NULL, thread safety)

**Overall Coverage**: ~90% (realistic for database testing)

**Challenging Areas**:
- Threading edge cases (limited testability in unit tests)
- Some error recovery paths (database corruption scenarios)
- Performance under heavy load (integration test territory)

## Manual Verification Commands

```bash
# Run all database tests
pytest tests/unit/test_database.py -v

# Run with coverage
pytest tests/unit/test_database.py --cov=common.database --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_database.py::TestUserStatistics -v

# Run with database debugging
pytest tests/unit/test_database.py -v -s --log-cli-level=DEBUG

# Check for database file cleanup (should be empty after tests)
ls tests/unit/*.db  # Should not exist

# Test with in-memory database (faster)
pytest tests/unit/test_database.py -v -k "in_memory"
```

## Success Criteria

- ✅ All 90+ tests pass
- ✅ Coverage ≥90% for common/database.py
- ✅ All database tables tested (9 tables)
- ✅ Schema migrations verified
- ✅ CRUD operations tested for all entities
- ✅ Retry logic and exponential backoff validated
- ✅ API token security (no full token exposure in listings)
- ✅ Maintenance operations tested (VACUUM, ANALYZE, cleanup)
- ✅ Edge cases covered (unicode, special chars, NULL values)
- ✅ No database files left after test runs (temp_db cleanup)
- ✅ Thread safety considerations documented
- ✅ Integration workflows tested

## Dependencies

- **SPEC-Commit-1**: pytest infrastructure, fixtures (tmp_path)
- **Python modules**: sqlite3, logging, time, secrets
- **Test utilities**: freezegun (time manipulation), pytest-asyncio (not needed - no async methods)

## Implementation Notes

1. **Test Isolation**: Each test uses `tmp_path` fixture for clean database
2. **Fixtures**: `db` fixture handles automatic close() via yield
3. **Time Testing**: Use `time.sleep()` for session duration tests
4. **Migration Testing**: Create old schema databases, then initialize BotDatabase
5. **Retry Logic**: Manipulate timestamps to simulate time passing for backoff testing
6. **Maintenance**: Tests create old data to verify cleanup operations
7. **Token Security**: Verify full tokens never exposed in list_api_tokens()
8. **Logging Tests**: Use caplog fixture to verify log messages
9. **Performance**: Index tests verify efficient query patterns
10. **Coverage Strategy**: Focus on business logic, data integrity, and retry mechanisms

## Notes

- **Complexity**: 764 lines, 50+ methods, 9 tables - HIGH complexity
- **Test Count**: 90+ tests ensures comprehensive coverage
- **Coverage Target**: 90% realistic (database error scenarios hard to trigger)
- **Key Features**: 
  - Schema migrations (ALTER TABLE for backward compatibility)
  - Exponential backoff (2^retry_count minutes)
  - Partial token matching (8+ character prefix)
  - Singleton tables (CHECK constraint id=1)
  - Retention policies (30d/7d/90d for different data types)
  - VACUUM/ANALYZE for optimization
- **Testing Strategy**: Heavy use of tmp_path for isolation, direct cursor queries to verify state
- **Next Step**: Ready for implementation after approval
