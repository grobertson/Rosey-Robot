"""
Unit tests for StorageAdapter abstract interface.

Tests the abstract base class, error hierarchy, and mock implementation.
"""

import pytest
import time
from unittest.mock import AsyncMock
from lib.storage import (
    StorageAdapter,
    StorageError,
    StorageConnectionError,
    QueryError,
    MigrationError,
    IntegrityError
)


class MockStorage(StorageAdapter):
    """Mock storage implementation for testing."""
    
    def __init__(self):
        super().__init__()
        self.users = {}
        self.actions = []
        self.messages = []
        self.channel_stats = {
            'max_users': 0,
            'max_users_timestamp': 0,
            'max_connected': 0,
            'max_connected_timestamp': 0,
            'last_updated': 0
        }
        self.user_count_history = []
        self.next_id = 1
    
    async def connect(self):
        """Connect to mock storage."""
        self._is_connected = True
    
    async def close(self):
        """Close mock storage."""
        self._is_connected = False
    
    async def save_user_stats(self, username, first_seen=None, last_seen=None,
                             chat_lines=None, time_connected=None, session_start=None):
        """Save user stats to mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        if username not in self.users:
            self.users[username] = {
                'username': username,
                'first_seen': first_seen or 0,
                'last_seen': last_seen or 0,
                'total_chat_lines': 0,
                'total_time_connected': 0,
                'current_session_start': None
            }
        
        user = self.users[username]
        if first_seen is not None:
            user['first_seen'] = first_seen
        if last_seen is not None:
            user['last_seen'] = last_seen
        if chat_lines is not None:
            user['total_chat_lines'] += chat_lines
        if time_connected is not None:
            user['total_time_connected'] += time_connected
        if session_start is not None:
            user['current_session_start'] = session_start
    
    async def get_user_stats(self, username):
        """Get user stats from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        return self.users.get(username)
    
    async def get_all_user_stats(self, limit=None, offset=0):
        """Get all user stats from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        users_list = list(self.users.values())
        users_list.sort(key=lambda u: u['last_seen'], reverse=True)
        
        if offset:
            users_list = users_list[offset:]
        if limit:
            users_list = users_list[:limit]
        
        return users_list
    
    async def log_user_action(self, username, action_type, details=None, timestamp=None):
        """Log user action to mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        action = {
            'id': self.next_id,
            'timestamp': timestamp or int(time.time()),
            'username': username,
            'action_type': action_type,
            'details': details
        }
        self.actions.append(action)
        self.next_id += 1
    
    async def get_user_actions(self, username=None, action_type=None, limit=100, offset=0):
        """Get user actions from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        filtered = self.actions
        if username:
            filtered = [a for a in filtered if a['username'] == username]
        if action_type:
            filtered = [a for a in filtered if a['action_type'] == action_type]
        
        filtered.sort(key=lambda a: a['timestamp'], reverse=True)
        
        if offset:
            filtered = filtered[offset:]
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    async def update_channel_stats(self, max_users=None, max_connected=None, timestamp=None):
        """Update channel stats in mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        ts = timestamp or int(time.time())
        
        if max_users is not None and max_users > self.channel_stats['max_users']:
            self.channel_stats['max_users'] = max_users
            self.channel_stats['max_users_timestamp'] = ts
        
        if max_connected is not None and max_connected > self.channel_stats['max_connected']:
            self.channel_stats['max_connected'] = max_connected
            self.channel_stats['max_connected_timestamp'] = ts
        
        self.channel_stats['last_updated'] = ts
    
    async def get_channel_stats(self):
        """Get channel stats from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        return self.channel_stats.copy()
    
    async def log_user_count(self, chat_users, connected_users, timestamp=None):
        """Log user count to mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        record = {
            'id': self.next_id,
            'timestamp': timestamp or int(time.time()),
            'chat_users': chat_users,
            'connected_users': connected_users
        }
        self.user_count_history.append(record)
        self.next_id += 1
    
    async def get_user_count_history(self, start_time=None, end_time=None, limit=None):
        """Get user count history from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        filtered = self.user_count_history
        if start_time:
            filtered = [r for r in filtered if r['timestamp'] >= start_time]
        if end_time:
            filtered = [r for r in filtered if r['timestamp'] <= end_time]
        
        filtered.sort(key=lambda r: r['timestamp'])
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    async def save_message(self, username, message, timestamp=None):
        """Save message to mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        msg = {
            'id': self.next_id,
            'timestamp': timestamp or int(time.time()),
            'username': username,
            'message': message
        }
        self.messages.append(msg)
        self.next_id += 1
    
    async def get_recent_messages(self, limit=100, offset=0):
        """Get recent messages from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        messages = sorted(self.messages, key=lambda m: m['timestamp'], reverse=True)
        
        if offset:
            messages = messages[offset:]
        if limit:
            messages = messages[:limit]
        
        return messages
    
    async def clear_old_messages(self, keep_count=1000):
        """Clear old messages from mock storage."""
        if not self.is_connected:
            raise StorageError("Not connected")
        
        if len(self.messages) <= keep_count:
            return 0
        
        # Sort by timestamp descending and keep newest
        self.messages.sort(key=lambda m: m['timestamp'], reverse=True)
        deleted_count = len(self.messages) - keep_count
        self.messages = self.messages[:keep_count]
        
        return deleted_count


# ==================== Test Classes ====================


class TestStorageAdapter:
    """Test StorageAdapter abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that StorageAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageAdapter()
    
    def test_mock_storage_instantiation(self):
        """Test that mock implementation can be instantiated."""
        storage = MockStorage()
        assert storage is not None
        assert not storage.is_connected
    
    def test_logger_default(self):
        """Test default logger is created."""
        storage = MockStorage()
        assert storage.logger is not None
        assert storage.logger.name == 'MockStorage'


class TestConnectionLifecycle:
    """Test connection lifecycle operations."""
    
    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(self):
        """Test connect() sets is_connected flag."""
        storage = MockStorage()
        assert not storage.is_connected
        
        await storage.connect()
        
        assert storage.is_connected
    
    @pytest.mark.asyncio
    async def test_close_clears_connected_flag(self):
        """Test close() clears is_connected flag."""
        storage = MockStorage()
        await storage.connect()
        assert storage.is_connected
        
        await storage.close()
        
        assert not storage.is_connected
    
    @pytest.mark.asyncio
    async def test_operations_require_connection(self):
        """Test operations fail when not connected."""
        storage = MockStorage()
        
        with pytest.raises(StorageError, match="Not connected"):
            await storage.save_user_stats("test")
        
        with pytest.raises(StorageError, match="Not connected"):
            await storage.get_user_stats("test")


class TestUserStats:
    """Test user statistics operations."""
    
    @pytest.mark.asyncio
    async def test_save_new_user(self):
        """Test saving new user stats."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.save_user_stats(
            "alice",
            first_seen=1000,
            last_seen=2000,
            chat_lines=5,
            time_connected=100
        )
        
        user = await storage.get_user_stats("alice")
        assert user is not None
        assert user['username'] == "alice"
        assert user['first_seen'] == 1000
        assert user['last_seen'] == 2000
        assert user['total_chat_lines'] == 5
        assert user['total_time_connected'] == 100
    
    @pytest.mark.asyncio
    async def test_update_existing_user(self):
        """Test updating existing user stats."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.save_user_stats("bob", first_seen=1000, chat_lines=5)
        await storage.save_user_stats("bob", last_seen=2000, chat_lines=3)
        
        user = await storage.get_user_stats("bob")
        assert user['first_seen'] == 1000
        assert user['last_seen'] == 2000
        assert user['total_chat_lines'] == 8  # 5 + 3
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self):
        """Test getting stats for non-existent user."""
        storage = MockStorage()
        await storage.connect()
        
        user = await storage.get_user_stats("nobody")
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_get_all_users(self):
        """Test getting all user stats."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.save_user_stats("alice", last_seen=3000)
        await storage.save_user_stats("bob", last_seen=2000)
        await storage.save_user_stats("charlie", last_seen=1000)
        
        users = await storage.get_all_user_stats()
        
        assert len(users) == 3
        # Should be sorted by last_seen descending
        assert users[0]['username'] == "alice"
        assert users[1]['username'] == "bob"
        assert users[2]['username'] == "charlie"
    
    @pytest.mark.asyncio
    async def test_get_all_users_with_pagination(self):
        """Test pagination in get_all_user_stats."""
        storage = MockStorage()
        await storage.connect()
        
        for i in range(10):
            await storage.save_user_stats(f"user{i}", last_seen=i)
        
        users = await storage.get_all_user_stats(limit=5, offset=2)
        
        assert len(users) == 5


class TestUserActions:
    """Test user action logging."""
    
    @pytest.mark.asyncio
    async def test_log_action(self):
        """Test logging user action."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.log_user_action("alice", "join", "from 192.168.1.1", timestamp=1000)
        
        actions = await storage.get_user_actions()
        assert len(actions) == 1
        assert actions[0]['username'] == "alice"
        assert actions[0]['action_type'] == "join"
        assert actions[0]['details'] == "from 192.168.1.1"
        assert actions[0]['timestamp'] == 1000
    
    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_username(self):
        """Test filtering actions by username."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.log_user_action("alice", "join")
        await storage.log_user_action("bob", "join")
        await storage.log_user_action("alice", "leave")
        
        actions = await storage.get_user_actions(username="alice")
        
        assert len(actions) == 2
        assert all(a['username'] == "alice" for a in actions)
    
    @pytest.mark.asyncio
    async def test_get_actions_filtered_by_type(self):
        """Test filtering actions by type."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.log_user_action("alice", "join")
        await storage.log_user_action("bob", "pm")
        await storage.log_user_action("charlie", "join")
        
        actions = await storage.get_user_actions(action_type="join")
        
        assert len(actions) == 2
        assert all(a['action_type'] == "join" for a in actions)


class TestChannelStats:
    """Test channel statistics."""
    
    @pytest.mark.asyncio
    async def test_update_channel_stats(self):
        """Test updating channel stats."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.update_channel_stats(max_users=10, max_connected=15, timestamp=1000)
        
        stats = await storage.get_channel_stats()
        assert stats['max_users'] == 10
        assert stats['max_users_timestamp'] == 1000
        assert stats['max_connected'] == 15
        assert stats['max_connected_timestamp'] == 1000
    
    @pytest.mark.asyncio
    async def test_update_only_increases_max(self):
        """Test that updates only increase maximums."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.update_channel_stats(max_users=20, timestamp=1000)
        await storage.update_channel_stats(max_users=10, timestamp=2000)  # Lower value
        
        stats = await storage.get_channel_stats()
        assert stats['max_users'] == 20  # Should remain at higher value
        assert stats['max_users_timestamp'] == 1000  # Original timestamp
    
    @pytest.mark.asyncio
    async def test_log_user_count(self):
        """Test logging user count."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.log_user_count(10, 15, timestamp=1000)
        
        history = await storage.get_user_count_history()
        assert len(history) == 1
        assert history[0]['chat_users'] == 10
        assert history[0]['connected_users'] == 15
    
    @pytest.mark.asyncio
    async def test_get_user_count_history_filtered(self):
        """Test filtering user count history."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.log_user_count(5, 10, timestamp=1000)
        await storage.log_user_count(8, 12, timestamp=2000)
        await storage.log_user_count(6, 9, timestamp=3000)
        
        history = await storage.get_user_count_history(start_time=1500, end_time=2500)
        
        assert len(history) == 1
        assert history[0]['timestamp'] == 2000


class TestChatMessages:
    """Test chat message operations."""
    
    @pytest.mark.asyncio
    async def test_save_message(self):
        """Test saving chat message."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.save_message("alice", "Hello world!", timestamp=1000)
        
        messages = await storage.get_recent_messages()
        assert len(messages) == 1
        assert messages[0]['username'] == "alice"
        assert messages[0]['message'] == "Hello world!"
        assert messages[0]['timestamp'] == 1000
    
    @pytest.mark.asyncio
    async def test_get_recent_messages_sorted(self):
        """Test messages are returned most recent first."""
        storage = MockStorage()
        await storage.connect()
        
        await storage.save_message("alice", "first", timestamp=1000)
        await storage.save_message("bob", "second", timestamp=2000)
        await storage.save_message("charlie", "third", timestamp=3000)
        
        messages = await storage.get_recent_messages()
        
        assert messages[0]['message'] == "third"
        assert messages[1]['message'] == "second"
        assert messages[2]['message'] == "first"
    
    @pytest.mark.asyncio
    async def test_clear_old_messages(self):
        """Test clearing old messages."""
        storage = MockStorage()
        await storage.connect()
        
        # Add 10 messages
        for i in range(10):
            await storage.save_message(f"user{i}", f"message {i}", timestamp=i)
        
        # Keep only 5 newest
        deleted = await storage.clear_old_messages(keep_count=5)
        
        assert deleted == 5
        messages = await storage.get_recent_messages()
        assert len(messages) == 5
        # Should keep newest 5 (timestamps 5-9)
        assert all(m['timestamp'] >= 5 for m in messages)


class TestErrorHierarchy:
    """Test storage error classes."""
    
    def test_storage_error_base(self):
        """Test StorageError is base exception."""
        err = StorageError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"
    
    def test_connection_error_inheritance(self):
        """Test StorageConnectionError inherits from StorageError."""
        err = StorageConnectionError("connection failed")
        assert isinstance(err, StorageError)
        assert isinstance(err, Exception)
    
    def test_query_error_inheritance(self):
        """Test QueryError inherits from StorageError."""
        err = QueryError("query failed")
        assert isinstance(err, StorageError)
    
    def test_migration_error_inheritance(self):
        """Test MigrationError inherits from StorageError."""
        err = MigrationError("migration failed")
        assert isinstance(err, StorageError)
    
    def test_integrity_error_inheritance(self):
        """Test IntegrityError inherits from StorageError."""
        err = IntegrityError("constraint violated")
        assert isinstance(err, StorageError)
    
    def test_error_can_be_caught_as_storage_error(self):
        """Test specific errors can be caught as StorageError."""
        try:
            raise QueryError("test")
        except StorageError as e:
            assert str(e) == "test"
