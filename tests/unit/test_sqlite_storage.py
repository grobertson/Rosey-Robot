"""
Unit tests for SQLiteStorage implementation.

Tests the concrete SQLite implementation of the StorageAdapter interface.
"""

import pytest
import os
import tempfile
import time
from lib.storage import SQLiteStorage, QueryError


@pytest.fixture
async def sqlite_storage():
    """Create a temporary SQLite storage instance for testing."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    storage = SQLiteStorage(db_path)
    await storage.connect()

    yield storage

    # Cleanup
    await storage.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestSQLiteStorageConnection:
    """Test SQLite connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_creates_database(self):
        """Test that connect creates database file."""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.unlink(db_path)  # Remove file to test creation

        try:
            storage = SQLiteStorage(db_path)
            await storage.connect()

            assert os.path.exists(db_path)
            assert storage.is_connected

            await storage.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, sqlite_storage):
        """Test that connect creates all required tables."""
        cursor = sqlite_storage.conn.cursor()

        # Check that all tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'user_stats', 'user_actions', 'channel_stats',
                'user_count_history', 'recent_chat'
            )
        """)

        tables = [row[0] for row in cursor.fetchall()]
        assert 'user_stats' in tables
        assert 'user_actions' in tables
        assert 'channel_stats' in tables
        assert 'user_count_history' in tables
        assert 'recent_chat' in tables

    @pytest.mark.asyncio
    async def test_close_commits_and_disconnects(self, sqlite_storage):
        """Test that close commits changes and sets connected flag."""
        await sqlite_storage.save_user_stats("test", first_seen=123)
        await sqlite_storage.close()

        assert not sqlite_storage.is_connected


class TestSQLiteUserStats:
    """Test user statistics operations."""

    @pytest.mark.asyncio
    async def test_save_new_user(self, sqlite_storage):
        """Test saving a new user."""
        await sqlite_storage.save_user_stats(
            "alice",
            first_seen=1000,
            last_seen=2000,
            chat_lines=5,
            time_connected=100
        )

        stats = await sqlite_storage.get_user_stats("alice")
        assert stats is not None
        assert stats['username'] == "alice"
        assert stats['first_seen'] == 1000
        assert stats['last_seen'] == 2000
        assert stats['total_chat_lines'] == 5
        assert stats['total_time_connected'] == 100

    @pytest.mark.asyncio
    async def test_update_existing_user(self, sqlite_storage):
        """Test updating existing user stats."""
        await sqlite_storage.save_user_stats("bob", first_seen=1000, chat_lines=5)
        await sqlite_storage.save_user_stats("bob", last_seen=2000, chat_lines=3)

        stats = await sqlite_storage.get_user_stats("bob")
        assert stats['first_seen'] == 1000
        assert stats['last_seen'] == 2000
        assert stats['total_chat_lines'] == 8  # 5 + 3

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, sqlite_storage):
        """Test getting stats for non-existent user returns None."""
        stats = await sqlite_storage.get_user_stats("nobody")
        assert stats is None

    @pytest.mark.asyncio
    async def test_get_all_users_sorted(self, sqlite_storage):
        """Test getting all users returns sorted list."""
        await sqlite_storage.save_user_stats("alice", first_seen=1000, last_seen=3000)
        await sqlite_storage.save_user_stats("bob", first_seen=1000, last_seen=2000)
        await sqlite_storage.save_user_stats("charlie", first_seen=1000, last_seen=1000)

        users = await sqlite_storage.get_all_user_stats()

        assert len(users) == 3
        # Should be sorted by last_seen descending
        assert users[0]['username'] == "alice"
        assert users[1]['username'] == "bob"
        assert users[2]['username'] == "charlie"

    @pytest.mark.asyncio
    async def test_get_all_users_with_pagination(self, sqlite_storage):
        """Test pagination in get_all_user_stats."""
        for i in range(10):
            await sqlite_storage.save_user_stats(f"user{i}", first_seen=i, last_seen=i)

        users = await sqlite_storage.get_all_user_stats(limit=5, offset=2)

        assert len(users) == 5

    @pytest.mark.asyncio
    async def test_session_tracking(self, sqlite_storage):
        """Test session start tracking."""
        now = int(time.time())
        await sqlite_storage.save_user_stats("alice", first_seen=now, session_start=now)

        stats = await sqlite_storage.get_user_stats("alice")
        assert stats['current_session_start'] == now


class TestSQLiteUserActions:
    """Test user action logging."""

    @pytest.mark.asyncio
    async def test_log_action(self, sqlite_storage):
        """Test logging a user action."""
        await sqlite_storage.log_user_action("alice", "join", "from 192.168.1.1", timestamp=1000)

        actions = await sqlite_storage.get_user_actions()
        assert len(actions) == 1
        assert actions[0]['username'] == "alice"
        assert actions[0]['action_type'] == "join"
        assert actions[0]['details'] == "from 192.168.1.1"
        assert actions[0]['timestamp'] == 1000

    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_username(self, sqlite_storage):
        """Test filtering actions by username."""
        await sqlite_storage.log_user_action("alice", "join")
        await sqlite_storage.log_user_action("bob", "join")
        await sqlite_storage.log_user_action("alice", "leave")

        actions = await sqlite_storage.get_user_actions(username="alice")

        assert len(actions) == 2
        assert all(a['username'] == "alice" for a in actions)

    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_type(self, sqlite_storage):
        """Test filtering actions by action type."""
        await sqlite_storage.log_user_action("alice", "join")
        await sqlite_storage.log_user_action("bob", "pm")
        await sqlite_storage.log_user_action("charlie", "join")

        actions = await sqlite_storage.get_user_actions(action_type="join")

        assert len(actions) == 2
        assert all(a['action_type'] == "join" for a in actions)

    @pytest.mark.asyncio
    async def test_get_actions_with_pagination(self, sqlite_storage):
        """Test action retrieval with pagination."""
        for i in range(20):
            await sqlite_storage.log_user_action(f"user{i}", "join", timestamp=i)

        actions = await sqlite_storage.get_user_actions(limit=10, offset=5)

        assert len(actions) == 10


class TestSQLiteChannelStats:
    """Test channel statistics operations."""

    @pytest.mark.asyncio
    async def test_update_channel_stats(self, sqlite_storage):
        """Test updating channel stats."""
        await sqlite_storage.update_channel_stats(max_users=10, max_connected=15, timestamp=1000)

        stats = await sqlite_storage.get_channel_stats()
        assert stats['max_users'] == 10
        assert stats['max_users_timestamp'] == 1000
        assert stats['max_connected'] == 15
        assert stats['max_connected_timestamp'] == 1000

    @pytest.mark.asyncio
    async def test_update_only_increases_max(self, sqlite_storage):
        """Test that updates only increase maximums."""
        await sqlite_storage.update_channel_stats(max_users=20, timestamp=1000)
        await sqlite_storage.update_channel_stats(max_users=10, timestamp=2000)  # Lower value

        stats = await sqlite_storage.get_channel_stats()
        assert stats['max_users'] == 20  # Should remain at higher value
        assert stats['max_users_timestamp'] == 1000  # Original timestamp

    @pytest.mark.asyncio
    async def test_log_user_count(self, sqlite_storage):
        """Test logging user count snapshot."""
        await sqlite_storage.log_user_count(10, 15, timestamp=1000)

        history = await sqlite_storage.get_user_count_history()
        assert len(history) == 1
        assert history[0]['chat_users'] == 10
        assert history[0]['connected_users'] == 15
        assert history[0]['timestamp'] == 1000

    @pytest.mark.asyncio
    async def test_get_user_count_history_filtered(self, sqlite_storage):
        """Test filtering user count history by time range."""
        await sqlite_storage.log_user_count(5, 10, timestamp=1000)
        await sqlite_storage.log_user_count(8, 12, timestamp=2000)
        await sqlite_storage.log_user_count(6, 9, timestamp=3000)

        history = await sqlite_storage.get_user_count_history(start_time=1500, end_time=2500)

        assert len(history) == 1
        assert history[0]['timestamp'] == 2000

    @pytest.mark.asyncio
    async def test_get_user_count_history_with_limit(self, sqlite_storage):
        """Test limiting user count history results."""
        for i in range(10):
            await sqlite_storage.log_user_count(i, i, timestamp=i)

        history = await sqlite_storage.get_user_count_history(limit=5)

        assert len(history) == 5


class TestSQLiteChatMessages:
    """Test chat message storage operations."""

    @pytest.mark.asyncio
    async def test_save_message(self, sqlite_storage):
        """Test saving a chat message."""
        await sqlite_storage.save_message("alice", "Hello world!", timestamp=1000)

        messages = await sqlite_storage.get_recent_messages()
        assert len(messages) == 1
        assert messages[0]['username'] == "alice"
        assert messages[0]['message'] == "Hello world!"
        assert messages[0]['timestamp'] == 1000

    @pytest.mark.asyncio
    async def test_get_recent_messages_sorted(self, sqlite_storage):
        """Test messages are returned most recent first."""
        await sqlite_storage.save_message("alice", "first", timestamp=1000)
        await sqlite_storage.save_message("bob", "second", timestamp=2000)
        await sqlite_storage.save_message("charlie", "third", timestamp=3000)

        messages = await sqlite_storage.get_recent_messages()

        assert messages[0]['message'] == "third"
        assert messages[1]['message'] == "second"
        assert messages[2]['message'] == "first"

    @pytest.mark.asyncio
    async def test_get_recent_messages_with_pagination(self, sqlite_storage):
        """Test pagination in get_recent_messages."""
        for i in range(20):
            await sqlite_storage.save_message(f"user{i}", f"message {i}", timestamp=i)

        messages = await sqlite_storage.get_recent_messages(limit=10, offset=5)

        assert len(messages) == 10

    @pytest.mark.asyncio
    async def test_clear_old_messages(self, sqlite_storage):
        """Test clearing old messages while keeping recent ones."""
        # Add 10 messages
        for i in range(10):
            await sqlite_storage.save_message(f"user{i}", f"message {i}", timestamp=i)

        # Keep only 5 newest
        deleted = await sqlite_storage.clear_old_messages(keep_count=5)

        assert deleted == 5
        messages = await sqlite_storage.get_recent_messages()
        assert len(messages) == 5
        # Should keep newest 5 (timestamps 5-9)
        assert all(m['timestamp'] >= 5 for m in messages)

    @pytest.mark.asyncio
    async def test_clear_old_messages_fewer_than_keep(self, sqlite_storage):
        """Test clearing when there are fewer messages than keep_count."""
        # Add 3 messages
        for i in range(3):
            await sqlite_storage.save_message(f"user{i}", f"message {i}", timestamp=i)

        # Try to keep 10 (more than exist)
        deleted = await sqlite_storage.clear_old_messages(keep_count=10)

        assert deleted == 0
        messages = await sqlite_storage.get_recent_messages()
        assert len(messages) == 3


class TestSQLiteErrorHandling:
    """Test error handling in SQLite storage."""

    @pytest.mark.asyncio
    async def test_operations_require_connection(self):
        """Test that operations fail when not connected."""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            storage = SQLiteStorage(db_path)
            # Don't connect

            with pytest.raises(QueryError, match="Not connected"):
                await storage.save_user_stats("test")

            with pytest.raises(QueryError, match="Not connected"):
                await storage.get_user_stats("test")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSQLiteMigrations:
    """Test database schema migrations."""

    @pytest.mark.asyncio
    async def test_migration_creates_all_tables(self, sqlite_storage):
        """Test that migration creates all required tables."""
        cursor = sqlite_storage.conn.cursor()

        # Check user_stats table structure
        cursor.execute('PRAGMA table_info(user_stats)')
        columns = [col[1] for col in cursor.fetchall()]
        assert 'username' in columns
        assert 'first_seen' in columns
        assert 'last_seen' in columns
        assert 'total_chat_lines' in columns
        assert 'total_time_connected' in columns
        assert 'current_session_start' in columns

    @pytest.mark.asyncio
    async def test_migration_creates_indices(self, sqlite_storage):
        """Test that migration creates indices."""
        cursor = sqlite_storage.conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name IN (
                'idx_user_count_timestamp',
                'idx_recent_chat_timestamp'
            )
        """)

        indices = [row[0] for row in cursor.fetchall()]
        assert 'idx_user_count_timestamp' in indices
        assert 'idx_recent_chat_timestamp' in indices

    @pytest.mark.asyncio
    async def test_migration_initializes_channel_stats(self, sqlite_storage):
        """Test that migration initializes channel_stats table."""
        stats = await sqlite_storage.get_channel_stats()

        # Should have default values
        assert stats['max_users'] == 0
        assert stats['last_updated'] is not None


class TestSQLiteIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_user_session_workflow(self, sqlite_storage):
        """Test complete user session workflow."""
        now = int(time.time())

        # User joins
        await sqlite_storage.save_user_stats(
            "alice",
            first_seen=now,
            last_seen=now,
            session_start=now
        )
        await sqlite_storage.log_user_action("alice", "join", timestamp=now)

        # User sends messages
        await sqlite_storage.save_user_stats("alice", chat_lines=1, last_seen=now + 10)
        await sqlite_storage.save_message("alice", "Hello!", timestamp=now + 10)

        await sqlite_storage.save_user_stats("alice", chat_lines=1, last_seen=now + 20)
        await sqlite_storage.save_message("alice", "How are you?", timestamp=now + 20)

        # User leaves - directly update session
        await sqlite_storage.save_user_stats(
            "alice",
            time_connected=300,
            last_seen=now + 300
        )
        # Clear session start by updating directly
        cursor = sqlite_storage.conn.cursor()
        cursor.execute(
            'UPDATE user_stats SET current_session_start = NULL WHERE username = ?',
            ('alice',)
        )
        sqlite_storage.conn.commit()
        await sqlite_storage.log_user_action("alice", "leave", timestamp=now + 300)

        # Verify final state
        stats = await sqlite_storage.get_user_stats("alice")
        assert stats['total_chat_lines'] == 2
        assert stats['total_time_connected'] == 300
        assert stats['current_session_start'] is None

        actions = await sqlite_storage.get_user_actions(username="alice")
        assert len(actions) == 2
        assert actions[0]['action_type'] == "leave"
        assert actions[1]['action_type'] == "join"

        messages = await sqlite_storage.get_recent_messages()
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_channel_statistics_workflow(self, sqlite_storage):
        """Test channel statistics tracking workflow."""
        # Log user counts over time
        for i in range(1, 6):
            await sqlite_storage.log_user_count(i * 2, i * 3, timestamp=i * 1000)
            await sqlite_storage.update_channel_stats(
                max_users=i * 2,
                max_connected=i * 3,
                timestamp=i * 1000
            )

        # Verify channel stats show maximum
        stats = await sqlite_storage.get_channel_stats()
        assert stats['max_users'] == 10  # 5 * 2
        assert stats['max_connected'] == 15  # 5 * 3

        # Verify history is preserved
        history = await sqlite_storage.get_user_count_history()
        assert len(history) == 5
        assert history[0]['chat_users'] == 2
        assert history[-1]['chat_users'] == 10
