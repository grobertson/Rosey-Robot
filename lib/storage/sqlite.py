"""
SQLite storage adapter implementation.

This module provides a concrete implementation of the StorageAdapter
interface using SQLite as the backend database.
"""

import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .adapter import StorageAdapter
from .errors import IntegrityError as StorageIntegrityError
from .errors import MigrationError, QueryError, StorageConnectionError


class SQLiteStorage(StorageAdapter):
    """
    SQLite implementation of the StorageAdapter interface.

    This adapter provides persistent storage using SQLite, suitable for
    single-instance bot deployments. It maintains compatibility with the
    existing database schema from common/database.py.

    Attributes:
        db_path: Path to the SQLite database file
        conn: SQLite connection object

    Example:
        >>> storage = SQLiteStorage('bot_data.db')
        >>> await storage.connect()
        >>> await storage.save_user_stats("alice", first_seen=123456)
        >>> stats = await storage.get_user_stats("alice")
        >>> await storage.close()
    """

    def __init__(self, db_path: str = 'bot_data.db',
                 logger: Optional[logging.Logger] = None):
        """
        Initialize SQLite storage adapter.

        Args:
            db_path: Path to SQLite database file
            logger: Optional logger instance
        """
        super().__init__(logger)
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    async def connect(self) -> None:
        """
        Connect to SQLite database and run migrations.

        Creates database file if it doesn't exist and initializes
        all required tables and indices.

        Raises:
            StorageConnectionError: If connection fails
            MigrationError: If schema creation/migration fails
        """
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.logger.info('Connected to SQLite database: %s', self.db_path)

            await self._run_migrations()
            self._is_connected = True

        except sqlite3.Error as e:
            self.logger.error('Failed to connect to database: %s', e)
            raise StorageConnectionError(f"Failed to connect to {self.db_path}: {e}")

    async def close(self) -> None:
        """
        Close database connection gracefully.

        Commits any pending transactions before closing.

        Raises:
            StorageConnectionError: If close operation fails
        """
        if self.conn and self._is_connected:
            try:
                self.conn.commit()
                self.conn.close()
                self.logger.info('Closed database connection')
                self._is_connected = False
            except sqlite3.Error as e:
                self.logger.error('Error closing database: %s', e)
                raise StorageConnectionError(f"Failed to close database: {e}")

    async def _run_migrations(self) -> None:
        """
        Run database schema migrations.

        Creates all necessary tables and indices if they don't exist.
        Performs schema migrations for existing databases.

        Raises:
            MigrationError: If migration fails
        """
        assert self.conn is not None, "Database not connected"
        try:
            cursor = self.conn.cursor()

            # User statistics table
            cursor.execute('''
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    details TEXT
                )
            ''')

            # High water mark table (single row with channel stats)
            cursor.execute('''
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_count_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    chat_users INTEGER NOT NULL,
                    connected_users INTEGER NOT NULL
                )
            ''')

            # Create index for efficient time-range queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_count_timestamp
                ON user_count_history(timestamp)
            ''')

            # Recent chat messages table (keep last N messages)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recent_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            ''')

            # Create index for efficient timestamp queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_recent_chat_timestamp
                ON recent_chat(timestamp DESC)
            ''')

            # Initialize channel_stats if empty
            cursor.execute('SELECT COUNT(*) FROM channel_stats')
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO channel_stats (id, max_users, last_updated)
                    VALUES (1, 0, ?)
                ''', (int(time.time()),))
            else:
                # Migrate existing database - add new columns if they don't exist
                cursor.execute('PRAGMA table_info(channel_stats)')
                columns = [col[1] for col in cursor.fetchall()]
                if 'max_connected' not in columns:
                    cursor.execute('''
                        ALTER TABLE channel_stats
                        ADD COLUMN max_connected INTEGER DEFAULT 0
                    ''')
                if 'max_connected_timestamp' not in columns:
                    cursor.execute('''
                        ALTER TABLE channel_stats
                        ADD COLUMN max_connected_timestamp INTEGER
                    ''')

            self.conn.commit()
            self.logger.info('Database schema initialized')

        except sqlite3.Error as e:
            self.logger.error('Migration failed: %s', e)
            raise MigrationError(f"Failed to run migrations: {e}")

    async def save_user_stats(self, username: str, first_seen: Optional[int] = None,
                             last_seen: Optional[int] = None, chat_lines: Optional[int] = None,
                             time_connected: Optional[int] = None,
                             session_start: Optional[int] = None) -> None:
        """
        Save or update user statistics.

        Args:
            username: Username to update
            first_seen: Unix timestamp of first appearance (for new users)
            last_seen: Unix timestamp of last activity
            chat_lines: Number of chat lines to add to total
            time_connected: Seconds connected to add to total
            session_start: Unix timestamp when current session started

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None

        try:
            cursor = self.conn.cursor()
            now = int(time.time())

            # Check if user exists
            cursor.execute('SELECT username FROM user_stats WHERE username = ?',
                          (username,))
            exists = cursor.fetchone() is not None

            if exists:
                # Build dynamic UPDATE query based on provided parameters
                updates = []
                params: List[Any] = []

                if last_seen is not None:
                    updates.append('last_seen = ?')
                    params.append(last_seen)

                if chat_lines is not None:
                    updates.append('total_chat_lines = total_chat_lines + ?')
                    params.append(chat_lines)

                if time_connected is not None:
                    updates.append('total_time_connected = total_time_connected + ?')
                    params.append(time_connected)

                if session_start is not None:
                    updates.append('current_session_start = ?')
                    params.append(session_start)

                if updates:
                    params.append(username)
                    query = f"UPDATE user_stats SET {', '.join(updates)} WHERE username = ?"
                    cursor.execute(query, params)
            else:
                # Insert new user
                cursor.execute('''
                    INSERT INTO user_stats
                    (username, first_seen, last_seen, total_chat_lines,
                     total_time_connected, current_session_start)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, first_seen or now, last_seen or now,
                      chat_lines or 0, time_connected or 0, session_start))

            self.conn.commit()

        except sqlite3.IntegrityError as e:
            self.logger.error('Integrity error saving user stats: %s', e)
            raise StorageIntegrityError(f"Failed to save user stats: {e}")
        except sqlite3.Error as e:
            self.logger.error('Error saving user stats: %s', e)
            raise QueryError(f"Failed to save user stats: {e}")

    async def get_user_stats(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve statistics for a single user.

        Args:
            username: Username to look up

        Returns:
            Dictionary with user stats, or None if user not found.
            Keys: username, first_seen, last_seen, total_chat_lines,
                  total_time_connected, current_session_start

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT username, first_seen, last_seen, total_chat_lines,
                       total_time_connected, current_session_start
                FROM user_stats WHERE username = ?
            ''', (username,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

        except sqlite3.Error as e:
            self.logger.error('Error getting user stats: %s', e)
            raise QueryError(f"Failed to get user stats: {e}")

    async def get_all_user_stats(self, limit: Optional[int] = None,
                                 offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve statistics for all users.

        Args:
            limit: Maximum number of records to return (None for all)
            offset: Number of records to skip

        Returns:
            List of user stat dictionaries, sorted by last_seen descending

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            query = '''
                SELECT username, first_seen, last_seen, total_chat_lines,
                       total_time_connected, current_session_start
                FROM user_stats
                ORDER BY last_seen DESC
            '''

            if limit is not None:
                query += f' LIMIT {limit} OFFSET {offset}'
            elif offset > 0:
                query += f' OFFSET {offset}'

            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error('Error getting all user stats: %s', e)
            raise QueryError(f"Failed to get all user stats: {e}")

    async def log_user_action(self, username: str, action_type: str,
                             details: Optional[str] = None,
                             timestamp: Optional[int] = None) -> None:
        """
        Log a user action (join, leave, PM, kick, etc.).

        Args:
            username: User who performed the action
            action_type: Type of action (join, leave, pm, kick, etc.)
            details: Optional additional details about the action
            timestamp: Unix timestamp (defaults to current time)

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO user_actions (timestamp, username, action_type, details)
                VALUES (?, ?, ?, ?)
            ''', (timestamp or int(time.time()), username, action_type, details))

            self.conn.commit()

        except sqlite3.Error as e:
            self.logger.error('Error logging user action: %s', e)
            raise QueryError(f"Failed to log user action: {e}")

    async def get_user_actions(self, username: Optional[str] = None,
                              action_type: Optional[str] = None,
                              limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve user action logs with optional filtering.

        Args:
            username: Filter by username (None for all users)
            action_type: Filter by action type (None for all types)
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of action log dictionaries, sorted by timestamp descending.
            Keys: id, timestamp, username, action_type, details

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()

            query = '''
                SELECT id, timestamp, username, action_type, details
                FROM user_actions
                WHERE 1=1
            '''
            params = []

            if username:
                query += ' AND username = ?'
                params.append(username)

            if action_type:
                query += ' AND action_type = ?'
                params.append(action_type)

            query += f' ORDER BY timestamp DESC LIMIT {limit} OFFSET {offset}'

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error('Error getting user actions: %s', e)
            raise QueryError(f"Failed to get user actions: {e}")

    async def update_channel_stats(self, max_users: Optional[int] = None,
                                   max_connected: Optional[int] = None,
                                   timestamp: Optional[int] = None) -> None:
        """
        Update channel-level statistics (high water marks).

        Only updates maximums if new values exceed current values.

        Args:
            max_users: New maximum user count (updates if greater than current)
            max_connected: New maximum connected count (updates if greater)
            timestamp: Unix timestamp for the maximum (defaults to current time)

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            now = timestamp or int(time.time())

            # Get current maximums
            cursor.execute('''
                SELECT max_users, max_connected FROM channel_stats WHERE id = 1
            ''')
            row = cursor.fetchone()
            current_max_users = row['max_users'] if row else 0
            current_max_connected = row['max_connected'] if row else 0

            updates = []
            params = []

            if max_users is not None and max_users > current_max_users:
                updates.extend(['max_users = ?', 'max_users_timestamp = ?'])
                params.extend([max_users, now])

            if max_connected is not None and max_connected > current_max_connected:
                updates.extend(['max_connected = ?', 'max_connected_timestamp = ?'])
                params.extend([max_connected, now])

            if updates:
                updates.append('last_updated = ?')
                params.append(now)
                query = f"UPDATE channel_stats SET {', '.join(updates)} WHERE id = 1"
                cursor.execute(query, params)
                self.conn.commit()

        except sqlite3.Error as e:
            self.logger.error('Error updating channel stats: %s', e)
            raise QueryError(f"Failed to update channel stats: {e}")

    async def get_channel_stats(self) -> Dict[str, Any]:
        """
        Retrieve channel-level statistics.

        Returns:
            Dictionary with keys: max_users, max_users_timestamp,
            max_connected, max_connected_timestamp, last_updated

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT max_users, max_users_timestamp, max_connected,
                       max_connected_timestamp, last_updated
                FROM channel_stats WHERE id = 1
            ''')

            row = cursor.fetchone()
            if row:
                return dict(row)

            # Return default values if no stats exist
            return {
                'max_users': 0,
                'max_users_timestamp': None,
                'max_connected': 0,
                'max_connected_timestamp': None,
                'last_updated': None
            }

        except sqlite3.Error as e:
            self.logger.error('Error getting channel stats: %s', e)
            raise QueryError(f"Failed to get channel stats: {e}")

    async def log_user_count(self, chat_users: int, connected_users: int,
                            timestamp: Optional[int] = None) -> None:
        """
        Log a snapshot of user counts for historical tracking.

        Args:
            chat_users: Number of users in chat
            connected_users: Number of connected users
            timestamp: Unix timestamp (defaults to current time)

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO user_count_history (timestamp, chat_users, connected_users)
                VALUES (?, ?, ?)
            ''', (timestamp or int(time.time()), chat_users, connected_users))

            self.conn.commit()

        except sqlite3.Error as e:
            self.logger.error('Error logging user count: %s', e)
            raise QueryError(f"Failed to log user count: {e}")

    async def get_user_count_history(self, start_time: Optional[int] = None,
                                     end_time: Optional[int] = None,
                                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve historical user count data.

        Args:
            start_time: Unix timestamp for range start (None for all)
            end_time: Unix timestamp for range end (None for all)
            limit: Maximum number of records to return

        Returns:
            List of user count records, sorted by timestamp ascending.
            Keys: id, timestamp, chat_users, connected_users

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()

            query = '''
                SELECT id, timestamp, chat_users, connected_users
                FROM user_count_history
                WHERE 1=1
            '''
            params = []

            if start_time is not None:
                query += ' AND timestamp >= ?'
                params.append(start_time)

            if end_time is not None:
                query += ' AND timestamp <= ?'
                params.append(end_time)

            query += ' ORDER BY timestamp ASC'

            if limit is not None:
                query += f' LIMIT {limit}'

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error('Error getting user count history: %s', e)
            raise QueryError(f"Failed to get user count history: {e}")

    async def save_message(self, username: str, message: str,
                          timestamp: Optional[int] = None) -> None:
        """
        Save a chat message to the recent messages cache.

        Args:
            username: User who sent the message
            message: Message content
            timestamp: Unix timestamp (defaults to current time)

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO recent_chat (timestamp, username, message)
                VALUES (?, ?, ?)
            ''', (timestamp or int(time.time()), username, message))

            self.conn.commit()

        except sqlite3.Error as e:
            self.logger.error('Error saving message: %s', e)
            raise QueryError(f"Failed to save message: {e}")

    async def get_recent_messages(self, limit: int = 100,
                                  offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve recent chat messages.

        Args:
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of message dictionaries, sorted by timestamp descending.
            Keys: id, timestamp, username, message

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, username, message
                FROM recent_chat
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error('Error getting recent messages: %s', e)
            raise QueryError(f"Failed to get recent messages: {e}")

    async def clear_old_messages(self, keep_count: int = 1000) -> int:
        """
        Delete old messages, keeping only the most recent N.

        Args:
            keep_count: Number of most recent messages to keep

        Returns:
            Number of messages deleted

        Raises:
            QueryError: If database operation fails
        """
        if not self.is_connected:
            raise QueryError("Not connected to database")
        assert self.conn is not None  # Type narrowing for mypy

        try:
            cursor = self.conn.cursor()

            # Get the timestamp of the Nth newest message
            cursor.execute('''
                SELECT timestamp FROM recent_chat
                ORDER BY timestamp DESC
                LIMIT 1 OFFSET ?
            ''', (keep_count - 1,))

            row = cursor.fetchone()
            if not row:
                # Fewer messages than keep_count, nothing to delete
                return 0

            cutoff_timestamp = row['timestamp']

            # Delete messages older than cutoff
            cursor.execute('''
                DELETE FROM recent_chat
                WHERE timestamp < ?
            ''', (cutoff_timestamp,))

            deleted = cursor.rowcount
            self.conn.commit()

            return deleted

        except sqlite3.Error as e:
            self.logger.error('Error clearing old messages: %s', e)
            raise QueryError(f"Failed to clear old messages: {e}")




