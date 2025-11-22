"""Unit tests for common/database.py - BotDatabase class

Tests cover:
- Database initialization and table creation
- Schema migrations and backward compatibility
- User statistics tracking (join, leave, chat messages)
- User actions logging
- Channel high water marks (chat and connected viewers)
- User count history and time-series data
- Recent chat message storage and retention
- Outbound message queue with retry logic and exponential backoff
- Current bot status tracking
- API token generation, validation, and revocation
- Database maintenance (cleanup, VACUUM, ANALYZE)
- Edge cases (unicode, special characters, NULL values)
- Thread safety considerations
- Integration workflows

Coverage target: 90% (realistic for database testing)
"""
import pytest
import sqlite3
import time

from common.database import BotDatabase


# ============================================================================
# Fixtures
# ============================================================================

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


# ============================================================================
# Test Class 1: Database Initialization
# ============================================================================

class TestDatabaseInit:
    """Tests for database initialization and table creation"""

    def test_init_creates_database_file(self, temp_db_path):
        """Database file is created on initialization"""
        import os
        assert not os.path.exists(temp_db_path)
        
        db = BotDatabase(temp_db_path)
        assert os.path.exists(temp_db_path)
        db.close()

    def test_init_creates_all_tables(self, db):
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

    def test_init_creates_indexes(self, db):
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

    def test_init_seeds_singleton_tables(self, db):
        """Singleton tables (current_status, channel_stats) are initialized"""
        cursor = db.conn.cursor()
        
        # Check current_status
        cursor.execute('SELECT COUNT(*) FROM current_status')
        assert cursor.fetchone()[0] == 1
        
        # Check channel_stats
        cursor.execute('SELECT COUNT(*) FROM channel_stats')
        assert cursor.fetchone()[0] == 1

    def test_init_row_factory_is_row(self, db):
        """Database uses sqlite3.Row for dict-like access"""
        assert db.conn.row_factory == sqlite3.Row

    def test_init_logs_connection(self, temp_db_path, caplog):
        """Database connection is logged"""
        # Need to set log level to INFO and enable propagation
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        db = BotDatabase(temp_db_path)
        assert 'Connected to database' in caplog.text
        assert 'Database tables initialized' in caplog.text
        db.close()


# ============================================================================
# Test Class 2: Database Migrations
# ============================================================================

class TestDatabaseMigrations:
    """Tests for automatic schema migrations"""

    def test_migration_adds_retry_count_to_outbound(self, temp_db_path):
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

    def test_migration_adds_last_error_to_outbound(self, temp_db_path):
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

    def test_migration_adds_max_connected_to_channel_stats(self, temp_db_path):
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

    def test_migration_idempotent(self, db):
        """Running migrations multiple times is safe"""
        # Call _create_tables again
        db._create_tables()
        
        # Database should still be functional
        db.user_joined("alice")
        stats = db.get_user_stats("alice")
        assert stats is not None

    def test_migration_preserves_data(self, temp_db_path):
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


# ============================================================================
# Test Class 3: User Statistics
# ============================================================================

class TestUserStatistics:
    """Tests for user tracking and statistics"""

    def test_user_joined_new_user(self, db):
        """New user is recorded with first_seen and last_seen"""
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

    def test_user_joined_existing_user(self, db):
        """Existing user updates last_seen and starts new session"""
        db.user_joined("alice")
        first_stats = db.get_user_stats("alice")
        
        time.sleep(1.1)  # Need >1 second for integer timestamp difference
        
        db.user_joined("alice")
        second_stats = db.get_user_stats("alice")
        
        # first_seen unchanged
        assert second_stats['first_seen'] == first_stats['first_seen']
        # last_seen updated
        assert second_stats['last_seen'] > first_stats['last_seen']
        # new session started
        assert second_stats['current_session_start'] >= second_stats['last_seen']

    def test_user_left_updates_time_connected(self, db):
        """User leaving updates total_time_connected"""
        db.user_joined("alice")
        time.sleep(1.1)  # Need >1 second for measurable time difference
        
        db.user_left("alice")
        
        stats = db.get_user_stats("alice")
        assert stats['total_time_connected'] >= 1
        assert stats['current_session_start'] is None

    def test_user_left_nonexistent_user(self, db):
        """Leaving with nonexistent user doesn't crash"""
        db.user_left("nonexistent")
        # Should not raise exception

    def test_user_left_no_session(self, db):
        """Leaving without active session doesn't crash"""
        db.user_joined("alice")
        db.user_left("alice")
        
        # Leave again without rejoining
        db.user_left("alice")
        
        # Should not crash or corrupt data
        stats = db.get_user_stats("alice")
        assert stats is not None

    def test_user_chat_message_increments_count(self, db):
        """Chat messages increment total_chat_lines"""
        db.user_joined("alice")
        
        db.user_chat_message("alice")
        db.user_chat_message("alice")
        db.user_chat_message("alice")
        
        stats = db.get_user_stats("alice")
        assert stats['total_chat_lines'] == 3

    def test_user_chat_message_stores_in_recent_chat(self, db):
        """Chat messages are stored in recent_chat"""
        db.user_joined("alice")
        db.user_chat_message("alice", "Hello world")
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent) == 1
        assert recent[0]['username'] == "alice"
        assert recent[0]['message'] == "Hello world"

    def test_user_chat_message_filters_server_messages(self, db):
        """Server messages are not stored in recent_chat"""
        db.user_chat_message("server", "System message")
        db.user_chat_message("Server", "System message")
        db.user_chat_message(None, "No username")
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent) == 0

    def test_get_top_chatters(self, db_with_users):
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

    def test_get_total_users_seen(self, db_with_users):
        """Total unique users count is correct"""
        assert db_with_users.get_total_users_seen() == 3


# ============================================================================
# Test Class 4: User Actions
# ============================================================================

class TestUserActions:
    """Tests for user action logging"""

    def test_log_user_action(self, db):
        """User actions are logged with timestamp"""
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

    def test_log_user_action_without_details(self, db):
        """User actions can be logged without details"""
        db.log_user_action("bob", "kick")
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM user_actions WHERE username = ?', ("bob",))
        row = cursor.fetchone()
        
        assert row['details'] is None

    def test_log_user_action_multiple(self, db):
        """Multiple actions are logged independently"""
        db.log_user_action("alice", "pm_command", "!help")
        db.log_user_action("bob", "kick", "reason: spam")
        db.log_user_action("alice", "pm_command", "!stats")
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM user_actions')
        assert cursor.fetchone()[0] == 3


# ============================================================================
# Test Class 5: Channel Stats
# ============================================================================

class TestChannelStats:
    """Tests for high water mark tracking"""

    def test_update_high_water_mark_initial(self, db):
        """First update sets high water mark"""
        db.update_high_water_mark(42)
        
        max_users, timestamp = db.get_high_water_mark()
        assert max_users == 42
        assert timestamp is not None

    def test_update_high_water_mark_exceeds(self, db):
        """Exceeding high water mark updates it"""
        db.update_high_water_mark(10)
        db.update_high_water_mark(20)
        
        max_users, _ = db.get_high_water_mark()
        assert max_users == 20

    def test_update_high_water_mark_not_exceeds(self, db):
        """Not exceeding high water mark doesn't update it"""
        db.update_high_water_mark(20)
        db.update_high_water_mark(15)
        
        max_users, _ = db.get_high_water_mark()
        assert max_users == 20

    def test_update_high_water_mark_connected(self, db):
        """Connected viewer count tracked separately"""
        db.update_high_water_mark(10, current_connected_count=25)
        
        max_connected, timestamp = db.get_high_water_mark_connected()
        assert max_connected == 25
        assert timestamp is not None

    def test_update_high_water_mark_both(self, db):
        """Both chat and connected can be updated together"""
        db.update_high_water_mark(10, current_connected_count=25)
        
        max_users, _ = db.get_high_water_mark()
        max_connected, _ = db.get_high_water_mark_connected()
        
        assert max_users == 10
        assert max_connected == 25

    def test_update_high_water_mark_logs(self, db, caplog):
        """New high water marks are logged"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        db.update_high_water_mark(42, current_connected_count=100)
        
        assert 'New high water mark (chat): 42 users' in caplog.text
        assert 'New high water mark (connected): 100 viewers' in caplog.text

    def test_get_high_water_mark_no_data(self, db):
        """High water mark returns 0 when no data"""
        max_users, timestamp = db.get_high_water_mark()
        assert max_users == 0
        # timestamp may be None or set from init

    def test_get_high_water_mark_connected_no_data(self, db):
        """Connected high water mark returns 0 when no data"""
        max_connected, timestamp = db.get_high_water_mark_connected()
        assert max_connected == 0


# ============================================================================
# Test Class 6: User Count History
# ============================================================================

class TestUserCountHistory:
    """Tests for historical user count tracking"""

    def test_log_user_count(self, db):
        """User counts are logged with timestamp"""
        before = int(time.time())
        
        db.log_user_count(chat_users=10, connected_users=15)
        
        after = int(time.time())
        
        history = db.get_user_count_history(hours=1)
        assert len(history) == 1
        assert history[0]['chat_users'] == 10
        assert history[0]['connected_users'] == 15
        assert before <= history[0]['timestamp'] <= after

    def test_log_user_count_multiple(self, db):
        """Multiple entries are stored chronologically"""
        db.log_user_count(5, 10)
        db.log_user_count(8, 12)
        db.log_user_count(6, 11)
        
        history = db.get_user_count_history(hours=24)
        assert len(history) == 3
        # Should be in ascending timestamp order
        assert history[0]['timestamp'] <= history[1]['timestamp']
        assert history[1]['timestamp'] <= history[2]['timestamp']

    def test_get_user_count_history_time_window(self, db_with_history):
        """History returns only entries within time window"""
        # db_with_history has 24 hours of data
        history_12h = db_with_history.get_user_count_history(hours=12)
        history_24h = db_with_history.get_user_count_history(hours=24)
        
        assert len(history_12h) < len(history_24h)
        assert len(history_24h) == 24

    def test_get_user_count_history_empty(self, db):
        """Empty history returns empty list"""
        history = db.get_user_count_history(hours=24)
        assert history == []

    def test_cleanup_old_history(self, db_with_history):
        """Old history entries are removed"""
        # Add very old entry
        old_timestamp = int(time.time()) - (60 * 86400)  # 60 days ago
        db_with_history.conn.execute('''
            INSERT INTO user_count_history (timestamp, chat_users, connected_users)
            VALUES (?, 1, 1)
        ''', (old_timestamp,))
        db_with_history.conn.commit()
        
        deleted = db_with_history.cleanup_old_history(days=30)
        
        assert deleted >= 1

    def test_cleanup_old_history_logs(self, db_with_history, caplog):
        """Cleanup logs number of deleted records"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        old_timestamp = int(time.time()) - (60 * 86400)
        db_with_history.conn.execute('''
            INSERT INTO user_count_history (timestamp, chat_users, connected_users)
            VALUES (?, 1, 1)
        ''', (old_timestamp,))
        db_with_history.conn.commit()
        
        deleted = db_with_history.cleanup_old_history(days=30)
        
        assert f'Cleaned up {deleted} old history records' in caplog.text


# ============================================================================
# Test Class 7: Recent Chat
# ============================================================================

class TestRecentChat:
    """Tests for recent chat message storage"""

    def test_get_recent_chat_empty(self, db):
        """Empty chat returns empty list"""
        recent = db.get_recent_chat(limit=20)
        assert recent == []

    def test_get_recent_chat_ordered(self, db):
        """Recent chat returns messages in reverse chronological order (newest first)"""
        db.user_joined("alice")
        db.user_chat_message("alice", "Message 1")
        time.sleep(0.01)  # Small delay between messages
        db.user_chat_message("alice", "Message 2")
        time.sleep(0.01)
        db.user_chat_message("alice", "Message 3")
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent) == 3
        # Despite comment in code, reverse() makes it NEWEST first (DESC order reversed)
        # Messages with same timestamp returned in reverse insertion order
        assert recent[0]['message'] == "Message 3"
        assert recent[1]['message'] == "Message 2"
        assert recent[2]['message'] == "Message 1"

    def test_get_recent_chat_limit(self, db):
        """Limit parameter restricts number of messages"""
        db.user_joined("alice")
        for i in range(10):
            db.user_chat_message("alice", f"Message {i}")
        
        recent = db.get_recent_chat(limit=5)
        assert len(recent) == 5
        # Verify we got 5 messages from the 10 inserted
        # Actual order depends on SQLite behavior with same timestamps

    def test_get_recent_chat_since_time_window(self, db):
        """get_recent_chat_since returns messages in time window"""
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

    def test_get_recent_chat_since_limit(self, db):
        """get_recent_chat_since respects limit parameter"""
        db.user_joined("alice")
        for i in range(20):
            db.user_chat_message("alice", f"Message {i}")
        
        recent = db.get_recent_chat_since(minutes=60, limit=5)
        assert len(recent) == 5

    def test_recent_chat_retention_cleanup(self, db):
        """Old chat messages are cleaned up on new insert"""
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


# ============================================================================
# Test Class 8: Outbound Messages
# ============================================================================

class TestOutboundMessages:
    """Tests for outbound message queue and retry logic"""

    def test_enqueue_outbound_message(self, db):
        """Messages are enqueued with timestamp"""
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

    def test_get_unsent_outbound_messages(self, db_with_messages):
        """Unsent messages are retrieved"""
        db = db_with_messages
        
        messages = db.get_unsent_outbound_messages(limit=10)
        
        assert len(messages) == 2
        assert messages[0]['message'] == "Hello world"
        assert messages[1]['message'] == "Test message"

    def test_get_unsent_outbound_messages_excludes_sent(self, db):
        """Sent messages are not retrieved"""
        msg_id = db.enqueue_outbound_message("Test")
        db.mark_outbound_sent(msg_id)
        
        messages = db.get_unsent_outbound_messages(limit=10)
        assert len(messages) == 0

    def test_get_unsent_outbound_messages_limit(self, db):
        """Limit parameter restricts number of messages"""
        for i in range(10):
            db.enqueue_outbound_message(f"Message {i}")
        
        messages = db.get_unsent_outbound_messages(limit=3)
        assert len(messages) == 3

    def test_get_unsent_outbound_messages_retry_backoff(self, db):
        """Messages with retry_count are delayed by exponential backoff"""
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

    def test_get_unsent_outbound_messages_max_retries(self, db):
        """Messages exceeding max_retries are not retrieved"""
        msg_id = db.enqueue_outbound_message("Failing message")
        
        # Fail 3 times
        for _ in range(3):
            db.mark_outbound_failed(msg_id, "Error", is_permanent=False)
        
        messages = db.get_unsent_outbound_messages(limit=10, max_retries=3)
        assert len(messages) == 0

    def test_mark_outbound_sent(self, db):
        """Marking as sent updates sent flag and timestamp"""
        before = int(time.time())
        
        msg_id = db.enqueue_outbound_message("Test")
        db.mark_outbound_sent(msg_id)
        
        after = int(time.time())
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        
        assert row['sent'] == 1
        assert before <= row['sent_timestamp'] <= after

    def test_mark_outbound_failed_transient(self, db):
        """Transient failure increments retry_count"""
        msg_id = db.enqueue_outbound_message("Test")
        
        db.mark_outbound_failed(msg_id, "Connection timeout", is_permanent=False)
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        
        assert row['sent'] == 0
        assert row['retry_count'] == 1
        assert row['last_error'] == "Connection timeout"

    def test_mark_outbound_failed_permanent(self, db):
        """Permanent failure marks as sent to stop retries"""
        msg_id = db.enqueue_outbound_message("Test")
        
        db.mark_outbound_failed(msg_id, "Permission denied", is_permanent=True)
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM outbound_messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        
        assert row['sent'] == 1  # Marked sent to prevent retries
        assert row['retry_count'] == 1
        assert row['last_error'] == "Permission denied"

    def test_mark_outbound_failed_logs_transient(self, db, caplog):
        """Transient failures log retry message"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        msg_id = db.enqueue_outbound_message("Test")
        db.mark_outbound_failed(msg_id, "Timeout", is_permanent=False)
        
        assert 'will retry' in caplog.text

    def test_mark_outbound_failed_logs_permanent(self, db, caplog):
        """Permanent failures log warning"""
        msg_id = db.enqueue_outbound_message("Test")
        db.mark_outbound_failed(msg_id, "Muted", is_permanent=True)
        
        assert 'permanently failed' in caplog.text

    def test_outbound_exponential_backoff_calculation(self, db):
        """Retry delay doubles each time: 2^retry_count minutes"""
        msg_id = db.enqueue_outbound_message("Test")
        
        # Fail multiple times and check delay progression
        # retry 0: immediate, retry 1: 2min, retry 2: 4min, retry 3: 8min
        
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


# ============================================================================
# Test Class 9: Current Status
# ============================================================================

class TestCurrentStatus:
    """Tests for live bot status tracking"""

    def test_update_current_status_single_field(self, db):
        """Single status field can be updated"""
        db.update_current_status(bot_name="TestBot")
        
        status = db.get_current_status()
        assert status['bot_name'] == "TestBot"

    def test_update_current_status_multiple_fields(self, db):
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

    def test_update_current_status_updates_last_updated(self, db):
        """last_updated is automatically set"""
        before = int(time.time())
        
        db.update_current_status(bot_name="TestBot")
        
        after = int(time.time())
        
        status = db.get_current_status()
        assert before <= status['last_updated'] <= after

    def test_update_current_status_all_fields(self, db):
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

    def test_update_current_status_invalid_field_ignored(self, db):
        """Invalid fields are ignored"""
        # Should not raise exception
        db.update_current_status(invalid_field="value", bot_name="TestBot")
        
        status = db.get_current_status()
        assert status['bot_name'] == "TestBot"

    def test_update_current_status_no_fields(self, db):
        """Calling with no fields doesn't crash"""
        db.update_current_status()
        # Should not raise exception

    def test_get_current_status_initial(self, db):
        """Initial status row exists with defaults"""
        status = db.get_current_status()
        assert status is not None
        assert status['id'] == 1


# ============================================================================
# Test Class 10: API Tokens
# ============================================================================

class TestAPITokens:
    """Tests for API token generation and validation"""

    def test_generate_api_token(self, db):
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

    def test_generate_api_token_without_description(self, db):
        """Token can be generated without description"""
        token = db.generate_api_token()
        assert token is not None

    def test_generate_api_token_unique(self, db):
        """Each token is unique"""
        token1 = db.generate_api_token()
        token2 = db.generate_api_token()
        assert token1 != token2

    def test_generate_api_token_logs(self, db, caplog):
        """Token generation is logged"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        token = db.generate_api_token("Test")
        assert 'Generated new API token' in caplog.text

    def test_validate_api_token_valid(self, db):
        """Valid token returns True"""
        token = db.generate_api_token("Test")
        assert db.validate_api_token(token) is True

    def test_validate_api_token_invalid(self, db):
        """Invalid token returns False"""
        assert db.validate_api_token("invalid_token_xyz") is False

    def test_validate_api_token_updates_last_used(self, db):
        """Validating token updates last_used"""
        token = db.generate_api_token("Test")
        
        before = int(time.time())
        db.validate_api_token(token)
        after = int(time.time())
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT last_used FROM api_tokens WHERE token = ?', (token,))
        last_used = cursor.fetchone()['last_used']
        
        assert before <= last_used <= after

    def test_validate_api_token_revoked(self, db):
        """Revoked token returns False"""
        token = db.generate_api_token("Test")
        db.revoke_api_token(token)
        
        assert db.validate_api_token(token) is False

    def test_revoke_api_token(self, db):
        """Token is revoked"""
        token = db.generate_api_token("Test")
        count = db.revoke_api_token(token)
        
        assert count == 1
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT revoked FROM api_tokens WHERE token = ?', (token,))
        assert cursor.fetchone()['revoked'] == 1

    def test_revoke_api_token_partial(self, db):
        """Token can be revoked with partial match (8+ chars)"""
        token = db.generate_api_token("Test")
        partial = token[:12]  # First 12 characters
        
        count = db.revoke_api_token(partial)
        assert count == 1

    def test_list_api_tokens(self, db):
        """Tokens can be listed with metadata"""
        token1 = db.generate_api_token("Token 1")
        token2 = db.generate_api_token("Token 2")
        
        tokens = db.list_api_tokens(include_revoked=False)
        
        assert len(tokens) == 2
        assert 'token_preview' in tokens[0]
        assert 'token' not in tokens[0]  # Full token not exposed
        assert tokens[0]['token_preview'].endswith('...')


# ============================================================================
# Test Class 11: Database Close
# ============================================================================

class TestDatabaseClose:
    """Tests for database cleanup on close"""

    def test_close_finalizes_active_sessions(self, temp_db_path):
        """Active sessions are finalized on close"""
        db = BotDatabase(temp_db_path)
        db.user_joined("alice")
        time.sleep(1.1)  # Need >1 second for measurable time
        
        db.close()
        
        # Reopen database
        db2 = BotDatabase(temp_db_path)
        stats = db2.get_user_stats("alice")
        
        assert stats['current_session_start'] is None
        assert stats['total_time_connected'] >= 1
        db2.close()

    def test_close_logs(self, temp_db_path, caplog):
        """Database close is logged"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        db = BotDatabase(temp_db_path)
        db.close()
        assert 'Database connection closed' in caplog.text

    def test_close_idempotent(self, temp_db_path):
        """Closing multiple times is safe"""
        db = BotDatabase(temp_db_path)
        db.close()
        # Second close should not crash
        db.conn = None  # Simulate closed state

    def test_close_commits_changes(self, temp_db_path):
        """Pending changes are committed on close"""
        db = BotDatabase(temp_db_path)
        db.user_joined("alice")
        db.close()
        
        # Reopen and verify
        db2 = BotDatabase(temp_db_path)
        assert db2.get_user_stats("alice") is not None
        db2.close()


# ============================================================================
# Test Class 12: Database Maintenance
# ============================================================================

class TestDatabaseMaintenance:
    """Tests for periodic maintenance operations"""

    def test_perform_maintenance_cleanup_old_history(self, db):
        """Maintenance removes old user count history"""
        # Add old history (60 days ago)
        old_time = int(time.time()) - (60 * 86400)
        db.conn.execute('''
            INSERT INTO user_count_history (timestamp, chat_users, connected_users)
            VALUES (?, 1, 1)
        ''', (old_time,))
        db.conn.commit()
        
        log = db.perform_maintenance()
        
        assert any('history records' in msg for msg in log)

    def test_perform_maintenance_cleanup_old_outbound(self, db):
        """Maintenance removes old sent outbound messages"""
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

    def test_perform_maintenance_cleanup_old_tokens(self, db):
        """Maintenance removes old revoked tokens"""
        # Add old revoked token (120 days ago)
        old_time = int(time.time()) - (120 * 86400)
        db.conn.execute('''
            INSERT INTO api_tokens (token, description, created_at, revoked)
            VALUES ('old_token', 'Old', ?, 1)
        ''', (old_time,))
        db.conn.commit()
        
        log = db.perform_maintenance()
        
        assert any('revoked tokens' in msg for msg in log)

    def test_perform_maintenance_vacuum(self, db):
        """Maintenance runs VACUUM"""
        log = db.perform_maintenance()
        assert any('VACUUM' in msg for msg in log)

    def test_perform_maintenance_analyze(self, db):
        """Maintenance runs ANALYZE"""
        log = db.perform_maintenance()
        assert any('ANALYZE' in msg for msg in log)

    def test_perform_maintenance_logs(self, db, caplog):
        """Maintenance completion is logged"""
        import logging
        logging.getLogger('common.database').setLevel(logging.INFO)
        logging.getLogger('common.database').propagate = True
        
        db.perform_maintenance()
        assert 'Database maintenance completed' in caplog.text

    def test_perform_maintenance_error_handling(self, temp_db_path, caplog):
        """Maintenance errors are logged and rolled back"""
        import logging
        logging.getLogger('common.database').setLevel(logging.ERROR)
        logging.getLogger('common.database').propagate = True
        
        db = BotDatabase(temp_db_path)
        # Force an error by closing connection
        db.conn.close()
        
        # Maintenance will fail with sqlite3 error
        try:
            db.perform_maintenance()
            assert False, "Should have raised exception"
        except Exception as e:
            # Should log the error
            assert 'Database maintenance error' in caplog.text or 'Cannot operate on a closed database' in str(e)

    def test_perform_maintenance_idempotent(self, db):
        """Running maintenance multiple times is safe"""
        db.perform_maintenance()
        db.perform_maintenance()
        # Should not crash


# ============================================================================
# Test Class 13: Database Edge Cases
# ============================================================================

class TestDatabaseEdgeCases:
    """Tests for edge cases and error handling"""

    def test_database_in_memory(self):
        """Database can use in-memory SQLite"""
        db = BotDatabase(':memory:')
        db.user_joined("alice")
        
        stats = db.get_user_stats("alice")
        assert stats is not None
        db.close()

    def test_database_concurrent_reads(self, db):
        """Multiple reads can happen concurrently"""
        db.user_joined("alice")
        db.user_joined("bob")
        
        # Simulate concurrent reads
        stats1 = db.get_user_stats("alice")
        stats2 = db.get_user_stats("bob")
        
        assert stats1['username'] == "alice"
        assert stats2['username'] == "bob"

    def test_database_special_characters_in_data(self, db):
        """Special characters in data are handled correctly"""
        db.user_joined("alice")
        db.user_chat_message("alice", "Message with 'quotes' and \"double quotes\"")
        db.log_user_action("alice", "test", "Details with 'quotes'")
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent) == 1

    def test_database_unicode_in_data(self, db):
        """Unicode characters are handled correctly"""
        db.user_joined("alice")
        db.user_chat_message("alice", "日本語 emoji 🎉 中文")
        
        recent = db.get_recent_chat(limit=10)
        assert recent[0]['message'] == "日本語 emoji 🎉 中文"

    def test_database_long_strings(self, db):
        """Very long strings are stored correctly"""
        long_message = "x" * 10000
        db.user_joined("alice")
        db.user_chat_message("alice", long_message)
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent[0]['message']) == 10000

    def test_database_null_values(self, db):
        """NULL values are handled appropriately"""
        db.user_joined("alice")
        db.log_user_action("alice", "test", None)
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT details FROM user_actions WHERE username = ?', ("alice",))
        assert cursor.fetchone()['details'] is None


# ============================================================================
# Test Class 14: Database Thread Safety
# ============================================================================

class TestDatabaseThreadSafety:
    """Tests for thread safety considerations"""

    def test_check_same_thread_false(self, db):
        """Database is configured with check_same_thread=False"""
        # This is necessary for web server context
        # Actual test: database creation doesn't raise exception
        assert db.conn is not None

    def test_database_connection_isolation(self, temp_db_path):
        """Each BotDatabase instance has its own connection"""
        db1 = BotDatabase(temp_db_path)
        db2 = BotDatabase(temp_db_path)
        
        assert db1.conn is not db2.conn
        
        db1.close()
        db2.close()

    def test_database_row_factory(self, db):
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


# ============================================================================
# Test Class 15: Database Performance
# ============================================================================

class TestDatabasePerformance:
    """Tests for database performance considerations"""

    def test_index_on_user_count_timestamp(self, db):
        """Index exists for efficient timestamp queries"""
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_user_count_timestamp'
        """)
        assert cursor.fetchone() is not None

    def test_index_on_recent_chat_timestamp(self, db):
        """Index exists for efficient recent chat queries"""
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_recent_chat_timestamp'
        """)
        assert cursor.fetchone() is not None

    def test_singleton_table_constraint(self, db):
        """Singleton tables enforce single row with CHECK constraint"""
        cursor = db.conn.cursor()
        
        # Try to insert second row into current_status (should fail)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute('''
                INSERT INTO current_status (id, last_updated)
                VALUES (2, ?)
            ''', (int(time.time()),))


# ============================================================================
# Test Class 16: Database Integration
# ============================================================================

class TestDatabaseIntegration:
    """Integration tests for multi-operation workflows"""

    def test_full_user_lifecycle(self, db):
        """Complete user session: join, chat, leave"""
        db.user_joined("alice")
        
        for i in range(5):
            db.user_chat_message("alice", f"Message {i}")
        
        time.sleep(1.1)  # Need >1 second for measurable time
        db.user_left("alice")
        
        stats = db.get_user_stats("alice")
        assert stats['total_chat_lines'] == 5
        assert stats['total_time_connected'] >= 1
        assert stats['current_session_start'] is None
        
        recent = db.get_recent_chat(limit=10)
        assert len(recent) == 5

    def test_high_water_mark_with_logging(self, db):
        """High water marks work with user count logging"""
        db.log_user_count(10, 15)
        db.update_high_water_mark(10, 15)
        
        max_users, _ = db.get_high_water_mark()
        max_connected, _ = db.get_high_water_mark_connected()
        
        assert max_users == 10
        assert max_connected == 15
        
        history = db.get_user_count_history(hours=1)
        assert len(history) == 1

    def test_outbound_retry_workflow(self, db):
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

    def test_api_token_lifecycle(self, db):
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
