#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite database for bot state persistence and statistics tracking"""
import logging
import sqlite3
import time


class BotDatabase:
    """Database for tracking bot state and user statistics"""

    def __init__(self, db_path='bot_data.db'):
        """Initialize database connection and create tables

        Args:
            db_path: Path to SQLite database file
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish database connection

        Note: check_same_thread=False is safe here because each request
        gets its own connection in the web server context.
        """
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.logger.info('Connected to database: %s', self.db_path)

    def _create_tables(self):
        """Create database tables if they don't exist"""
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

        # Current status table (single row with live bot state)
        cursor.execute('''
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
        cursor.execute('SELECT COUNT(*) FROM current_status')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO current_status (id, last_updated)
                VALUES (1, ?)
            ''', (int(time.time()),))

        # Outbound messages queue (messages to be sent by the bot)
        # Includes retry logic: retry_count tracks attempts, last_error stores
        # failure reason for permanent errors
        cursor.execute('''
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
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_outbound_sent
            ON outbound_messages(sent, timestamp)
        ''')

        # Migrate existing outbound_messages table if needed
        cursor.execute('PRAGMA table_info(outbound_messages)')
        outbound_cols = [col[1] for col in cursor.fetchall()]
        if 'retry_count' not in outbound_cols:
            cursor.execute('''
                ALTER TABLE outbound_messages
                ADD COLUMN retry_count INTEGER DEFAULT 0
            ''')
        if 'last_error' not in outbound_cols:
            cursor.execute('''
                ALTER TABLE outbound_messages
                ADD COLUMN last_error TEXT
            ''')

        # API tokens table for authentication
        # Supports token-based auth for external apps accessing /api/say
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_tokens (
                token TEXT PRIMARY KEY,
                description TEXT,
                created_at INTEGER NOT NULL,
                last_used INTEGER,
                revoked INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_tokens_revoked
            ON api_tokens(revoked, token)
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
        self.logger.info('Database tables initialized')

    def user_joined(self, username):
        """Record a user joining the channel

        Args:
            username: Username that joined
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Check if user exists
        cursor.execute('SELECT username FROM user_stats WHERE username = ?',
                       (username,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing user - start new session
            cursor.execute('''
                UPDATE user_stats
                SET last_seen = ?,
                    current_session_start = ?
                WHERE username = ?
            ''', (now, now, username))
        else:
            # New user - create entry
            cursor.execute('''
                INSERT INTO user_stats
                (username, first_seen, last_seen, current_session_start)
                VALUES (?, ?, ?, ?)
            ''', (username, now, now, now))

        self.conn.commit()

    def user_left(self, username):
        """Record a user leaving the channel

        Args:
            username: Username that left
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Get session start time
        cursor.execute('''
            SELECT current_session_start, total_time_connected
            FROM user_stats WHERE username = ?
        ''', (username,))

        row = cursor.fetchone()
        if row and row['current_session_start']:
            session_duration = now - row['current_session_start']
            new_total = row['total_time_connected'] + session_duration

            # Update user stats
            cursor.execute('''
                UPDATE user_stats
                SET last_seen = ?,
                    total_time_connected = ?,
                    current_session_start = NULL
                WHERE username = ?
            ''', (now, new_total, username))

            self.conn.commit()

    def user_chat_message(self, username, message=None):
        """Increment chat message count for user and optionally log message

        Args:
            username: Username that sent a message
            message: Optional message text to store in recent_chat
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Update user stats
        cursor.execute('''
            UPDATE user_stats
            SET total_chat_lines = total_chat_lines + 1,
                last_seen = ?
            WHERE username = ?
        ''', (now, username))

        # Store in recent chat if message provided
        # Filter out server messages (username may be None or indicate server)
        if message and username and username.lower() != 'server':
            cursor.execute('''
                INSERT INTO recent_chat (timestamp, username, message)
                VALUES (?, ?, ?)
            ''', (now, username, message))

            # Cleanup messages older than retention window (default 150 hours)
            retention_hours = 150
            cutoff = int(time.time()) - (retention_hours * 3600)
            cursor.execute('''
                DELETE FROM recent_chat
                WHERE timestamp < ?
            ''', (cutoff,))

        self.conn.commit()

    def log_user_action(self, username, action_type, details=None):
        """Log a user action (PM command, etc.)

        Args:
            username: Username performing the action
            action_type: Type of action (e.g., 'pm_command', 'kick', 'ban')
            details: Optional details about the action
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO user_actions
            (timestamp, username, action_type, details)
            VALUES (?, ?, ?, ?)
        ''', (int(time.time()), username, action_type, details))
        self.conn.commit()

    def update_high_water_mark(self, current_user_count,
                               current_connected_count=None):
        """Update high water mark if current count exceeds it

        Args:
            current_user_count: Current number of users in chat
            current_connected_count: Current number of connected viewers
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Get current max
        cursor.execute('''
            SELECT max_users, max_connected
            FROM channel_stats WHERE id = 1
        ''')
        row = cursor.fetchone()
        current_max_users = row['max_users'] if row else 0
        current_max_connected = row['max_connected'] if row else 0

        updated = False

        # Update max users (chat) if exceeded
        if current_user_count > current_max_users:
            cursor.execute('''
                UPDATE channel_stats
                SET max_users = ?,
                    max_users_timestamp = ?,
                    last_updated = ?
                WHERE id = 1
            ''', (current_user_count, now, now))
            updated = True
            self.logger.info('New high water mark (chat): %d users',
                           current_user_count)

        # Update max connected if exceeded
        if current_connected_count and current_connected_count > current_max_connected:
            cursor.execute('''
                UPDATE channel_stats
                SET max_connected = ?,
                    max_connected_timestamp = ?,
                    last_updated = ?
                WHERE id = 1
            ''', (current_connected_count, now, now))
            updated = True
            self.logger.info('New high water mark (connected): %d viewers',
                           current_connected_count)

        if updated:
            self.conn.commit()

    def get_user_stats(self, username):
        """Get statistics for a specific user

        Args:
            username: Username to look up

        Returns:
            dict with user stats or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM user_stats WHERE username = ?
        ''', (username,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_high_water_mark(self):
        """Get the high water mark (max users ever in chat)

        Returns:
            tuple: (max_users, timestamp) or (0, None)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT max_users, max_users_timestamp
            FROM channel_stats WHERE id = 1
        ''')
        row = cursor.fetchone()

        if row:
            return (row['max_users'], row['max_users_timestamp'])
        return (0, None)

    def get_high_water_mark_connected(self):
        """Get the high water mark for connected viewers

        Returns:
            tuple: (max_connected, timestamp) or (0, None)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT max_connected, max_connected_timestamp
            FROM channel_stats WHERE id = 1
        ''')
        row = cursor.fetchone()

        if row:
            return (row['max_connected'], row['max_connected_timestamp'])
        return (0, None)

    def get_top_chatters(self, limit=10):
        """Get top chatters by message count

        Args:
            limit: Number of results to return

        Returns:
            list of tuples: (username, chat_lines)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT username, total_chat_lines
            FROM user_stats
            WHERE total_chat_lines > 0
            ORDER BY total_chat_lines DESC
            LIMIT ?
        ''', (limit,))

        return [(row['username'], row['total_chat_lines'])
                for row in cursor.fetchall()]

    def get_total_users_seen(self):
        """Get total number of unique users ever seen

        Returns:
            int: Total unique users
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM user_stats')
        return cursor.fetchone()['count']

    def log_user_count(self, chat_users, connected_users):
        """Log current user counts for historical tracking

        Args:
            chat_users: Number of users in chat (with usernames)
            connected_users: Total connected viewers (including anonymous)
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        cursor.execute('''
            INSERT INTO user_count_history (timestamp, chat_users, connected_users)
            VALUES (?, ?, ?)
        ''', (now, chat_users, connected_users))

        self.conn.commit()

    def get_user_count_history(self, hours=24):
        """Get user count history for the specified time period

        Args:
            hours: Number of hours of history to retrieve (default 24)

        Returns:
            list: List of dicts with timestamp, chat_users, connected_users
        """
        cursor = self.conn.cursor()
        since = int(time.time()) - (hours * 3600)

        cursor.execute('''
            SELECT timestamp, chat_users, connected_users
            FROM user_count_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        ''', (since,))

        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_history(self, days=30):
        """Remove user count history older than specified days

        Args:
            days: Keep history for this many days (default 30)
        """
        cursor = self.conn.cursor()
        cutoff = int(time.time()) - (days * 86400)

        cursor.execute('''
            DELETE FROM user_count_history
            WHERE timestamp < ?
        ''', (cutoff,))

        deleted = cursor.rowcount
        self.conn.commit()

        if deleted > 0:
            self.logger.info('Cleaned up %d old history records', deleted)

        return deleted

    def get_recent_chat(self, limit=20):
        """Get recent chat messages

        Args:
            limit: Maximum number of messages to retrieve (default 20)

        Returns:
            list: List of dicts with timestamp, username, message in reverse
                chronological order (newest first). Note: Messages with identical
                timestamps may appear in reverse insertion order due to SQLite's
                tie-breaking behavior.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT timestamp, username, message
            FROM recent_chat
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        # Query returns DESC (newest first), reverse() flips to newest first
        # when considering the LIMIT. Messages with same timestamp maintain
        # reverse insertion order due to SQLite rowid ordering.
        messages = [dict(row) for row in cursor.fetchall()]
        messages.reverse()
        return messages

    def get_recent_chat_since(self, minutes=20, limit=1000):
        """Get recent chat messages within the last `minutes` minutes.

        Args:
            minutes: Time window in minutes to retrieve messages for.
            limit: Maximum number of messages to return (safety cap).

        Returns:
            list of dicts with timestamp, username, message in chronological
                order (oldest first, ascending by timestamp).
        """
        cursor = self.conn.cursor()
        since = int(time.time()) - (minutes * 60)
        cursor.execute('''
            SELECT timestamp, username, message
            FROM recent_chat
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (since, limit))

        return [dict(row) for row in cursor.fetchall()]

    def enqueue_outbound_message(self, message):
        """Add a message to the outbound queue for the bot to send.

        Args:
            message: Text message to send

        Returns:
            id of inserted outbound message
        """
        cursor = self.conn.cursor()
        now = int(time.time())
        cursor.execute('''
            INSERT INTO outbound_messages (timestamp, message, sent)
            VALUES (?, ?, 0)
        ''', (now, message))
        self.conn.commit()
        return cursor.lastrowid

    def get_unsent_outbound_messages(self, limit=50, max_retries=3):
        """Fetch unsent outbound messages ready for sending.

        Only returns messages that haven't exceeded retry limit.
        Uses exponential backoff: messages with higher retry counts
        will be delayed longer before being returned.

        Args:
            limit: Max number of messages to fetch
            max_retries: Maximum retry attempts before giving up

        Returns:
            list of rows as dicts (includes retry_count and last_error)
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Calculate retry delay: 2^retry_count minutes
        # retry 0: immediate, retry 1: 2min, retry 2: 4min, retry 3: 8min
        cursor.execute('''
            SELECT id, timestamp, message, retry_count, last_error
            FROM outbound_messages
            WHERE sent = 0
              AND retry_count < ?
              AND (retry_count = 0 OR timestamp + (1 << retry_count) * 60 <= ?)
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (max_retries, now, limit))
        return [dict(row) for row in cursor.fetchall()]

    def mark_outbound_sent(self, outbound_id):
        """Mark outbound message as successfully sent.

        Records sent timestamp and marks as sent.
        """
        cursor = self.conn.cursor()
        now = int(time.time())
        cursor.execute('''
            UPDATE outbound_messages
            SET sent = 1, sent_timestamp = ?
            WHERE id = ?
        ''', (now, outbound_id))
        self.conn.commit()

    def mark_outbound_failed(self, outbound_id, error_msg, is_permanent=False):
        """Mark outbound message send attempt as failed.

        Increments retry count for transient errors, or marks as permanently
        failed for errors like permission denied or muted.

        Args:
            outbound_id: Message ID that failed
            error_msg: Error message description
            is_permanent: If True, mark as sent to prevent further retries
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        if is_permanent:
            # Permanent failure - mark as "sent" to stop retries
            cursor.execute('''
                UPDATE outbound_messages
                SET sent = 1,
                    sent_timestamp = ?,
                    retry_count = retry_count + 1,
                    last_error = ?
                WHERE id = ?
            ''', (now, error_msg, outbound_id))
            self.logger.warning('Outbound message %d permanently failed: %s',
                              outbound_id, error_msg)
        else:
            # Transient failure - increment retry count for backoff
            cursor.execute('''
                UPDATE outbound_messages
                SET retry_count = retry_count + 1,
                    last_error = ?
                WHERE id = ?
            ''', (error_msg, outbound_id))
            self.logger.info('Outbound message %d failed (will retry): %s',
                           outbound_id, error_msg)

        self.conn.commit()

    def update_current_status(self, **kwargs):
        """Update current bot status

        Args:
            **kwargs: Status fields to update (bot_name, bot_rank, bot_afk,
                     channel_name, current_chat_users, current_connected_users,
                     playlist_items, current_media_title, current_media_duration,
                     bot_start_time, bot_connected)
        """
        cursor = self.conn.cursor()

        # Build update query dynamically
        fields = []
        values = []

        for key, value in kwargs.items():
            if key in ['bot_name', 'bot_rank', 'bot_afk', 'channel_name',
                      'current_chat_users', 'current_connected_users',
                      'playlist_items', 'current_media_title',
                      'current_media_duration', 'bot_start_time',
                      'bot_connected']:
                fields.append(f'{key} = ?')
                values.append(value)

        if not fields:
            return

        # Always update last_updated
        fields.append('last_updated = ?')
        values.append(int(time.time()))

        query = f'UPDATE current_status SET {", ".join(fields)} WHERE id = 1'
        cursor.execute(query, values)
        self.conn.commit()

    def get_current_status(self):
        """Get current bot status

        Returns:
            dict: Current status or None if not available
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM current_status WHERE id = 1')
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def generate_api_token(self, description=''):
        """Generate a new API token for external app authentication.

        Tokens are used to authenticate requests to protected endpoints
        like /api/say. Each token can have a description for tracking.

        Args:
            description: Optional description of what this token is for

        Returns:
            str: The generated token (store this securely - it won't be
                 retrievable later)
        """
        import secrets
        # Generate a cryptographically secure random token
        token = secrets.token_urlsafe(32)  # 256 bits of entropy

        cursor = self.conn.cursor()
        now = int(time.time())

        cursor.execute('''
            INSERT INTO api_tokens (token, description, created_at)
            VALUES (?, ?, ?)
        ''', (token, description, now))

        self.conn.commit()
        self.logger.info('Generated new API token: %s...', token[:8])
        return token

    def validate_api_token(self, token):
        """Check if an API token is valid (exists and not revoked).

        Also updates the last_used timestamp for valid tokens.

        Args:
            token: The token string to validate

        Returns:
            bool: True if token is valid, False otherwise
        """
        if not token:
            return False

        cursor = self.conn.cursor()

        # Check if token exists and is not revoked
        cursor.execute('''
            SELECT token FROM api_tokens
            WHERE token = ? AND revoked = 0
        ''', (token,))

        row = cursor.fetchone()

        if row:
            # Update last_used timestamp
            now = int(time.time())
            cursor.execute('''
                UPDATE api_tokens
                SET last_used = ?
                WHERE token = ?
            ''', (now, token))
            self.conn.commit()
            return True

        return False

    def revoke_api_token(self, token):
        """Revoke an API token, preventing its further use.

        Args:
            token: The token to revoke (can be partial - first 8+ chars)

        Returns:
            int: Number of tokens revoked
        """
        cursor = self.conn.cursor()

        # Support partial token matching for convenience (min 8 chars)
        if len(token) >= 8:
            cursor.execute('''
                UPDATE api_tokens
                SET revoked = 1
                WHERE token LIKE ? AND revoked = 0
            ''', (token + '%',))
        else:
            # Exact match only for short strings
            cursor.execute('''
                UPDATE api_tokens
                SET revoked = 1
                WHERE token = ? AND revoked = 0
            ''', (token,))

        count = cursor.rowcount
        self.conn.commit()

        if count > 0:
            self.logger.info('Revoked %d API token(s)', count)

        return count

    def list_api_tokens(self, include_revoked=False):
        """List all API tokens with their metadata.

        Args:
            include_revoked: If True, include revoked tokens

        Returns:
            list: List of dicts with token metadata (token is truncated
                  for security)
        """
        cursor = self.conn.cursor()

        if include_revoked:
            cursor.execute('''
                SELECT token, description, created_at, last_used, revoked
                FROM api_tokens
                ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT token, description, created_at, last_used, revoked
                FROM api_tokens
                WHERE revoked = 0
                ORDER BY created_at DESC
            ''')

        tokens = []
        for row in cursor.fetchall():
            token_data = dict(row)
            # Truncate token for security (show first 8 chars only)
            token_data['token_preview'] = token_data['token'][:8] + '...'
            del token_data['token']  # Don't expose full token
            tokens.append(token_data)

        return tokens

    def perform_maintenance(self):
        """Perform periodic database maintenance tasks.

        This is designed to be called by a background task and includes:
        - Cleanup of old user count history (keep last 30 days)
        - Cleanup of old outbound messages (keep last 7 days)
        - VACUUM to reclaim space and optimize database
        - Analyze to update query planner statistics

        Safe to call multiple times; operations are idempotent.
        """
        cursor = self.conn.cursor()
        maintenance_log = []

        try:
            # Cleanup old user count history (30 days retention)
            deleted_history = self.cleanup_old_history(days=30)
            if deleted_history > 0:
                maintenance_log.append(
                    f'Cleaned {deleted_history} old history records'
                )

            # Cleanup old outbound messages that were sent >7 days ago
            cutoff_sent = int(time.time()) - (7 * 86400)
            cursor.execute('''
                DELETE FROM outbound_messages
                WHERE sent = 1 AND sent_timestamp < ?
            ''', (cutoff_sent,))
            deleted_outbound = cursor.rowcount
            if deleted_outbound > 0:
                maintenance_log.append(
                    f'Cleaned {deleted_outbound} old outbound messages'
                )

            # Cleanup old revoked tokens (>90 days)
            cutoff_tokens = int(time.time()) - (90 * 86400)
            cursor.execute('''
                DELETE FROM api_tokens
                WHERE revoked = 1 AND created_at < ?
            ''', (cutoff_tokens,))
            deleted_tokens = cursor.rowcount
            if deleted_tokens > 0:
                maintenance_log.append(
                    f'Cleaned {deleted_tokens} old revoked tokens'
                )

            self.conn.commit()

            # VACUUM to reclaim space (must be outside transaction)
            self.logger.info('Running VACUUM to optimize database...')
            self.conn.execute('VACUUM')
            maintenance_log.append('VACUUM completed')

            # ANALYZE to update statistics
            self.conn.execute('ANALYZE')
            maintenance_log.append('ANALYZE completed')

            self.logger.info(
                'Database maintenance completed: %s',
                ', '.join(maintenance_log)
            )

            return maintenance_log

        except Exception as e:
            self.logger.error('Database maintenance error: %s', e)
            self.conn.rollback()
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            # Update any active sessions before closing
            cursor = self.conn.cursor()
            now = int(time.time())
            cursor.execute('''
                UPDATE user_stats
                SET total_time_connected = total_time_connected + (? - current_session_start),
                    current_session_start = NULL,
                    last_seen = ?
                WHERE current_session_start IS NOT NULL
            ''', (now, now))
            self.conn.commit()

            self.conn.close()
            self.logger.info('Database connection closed')
