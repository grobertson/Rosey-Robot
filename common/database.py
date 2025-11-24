#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database for bot state persistence and statistics tracking.

Uses SQLAlchemy ORM with async support.
Supports SQLite (dev/test) and PostgreSQL (production).

Migration History:
    v0.5.0: aiosqlite (direct SQL queries)
    v0.6.0: SQLAlchemy ORM (Sprint 11 Sortie 2)
    v0.6.1: PostgreSQL support (Sprint 11 Sortie 3)
"""
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import delete, func, insert, literal_column, or_, select, text, update, MetaData, Table
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models import (
    ApiToken,
    ChannelStats,
    CurrentStatus,
    OutboundMessage,
    PluginKVStorage,
    PluginTableSchema,
    RecentChat,
    UserAction,
    UserCountHistory,
    UserStats,
)


class BotDatabase:
    """
    Database for tracking bot state and user statistics.

    Uses SQLAlchemy ORM with async support for database operations.
    Supports SQLite (dev/test) and PostgreSQL (production).

    Attributes:
        engine: SQLAlchemy async engine
        session_factory: Factory for creating async sessions
        database_url: Database connection URL
        is_postgresql: Whether using PostgreSQL (vs SQLite)

    Example:
        # SQLite (development)
        db = BotDatabase('sqlite+aiosqlite:///bot_data.db')
        await db.connect()
        await db.user_joined('Alice')
        await db.close()

        # PostgreSQL (production)
        db = BotDatabase('postgresql+asyncpg://user:pass@host/db')
        await db.connect()
    """

    def __init__(self, database_url='sqlite+aiosqlite:///bot_data.db'):
        """
        Initialize database engine and session factory.

        Args:
            database_url: SQLAlchemy database URL or file path
                SQLite URL: 'sqlite+aiosqlite:///path/to/db.db'
                SQLite path: '/path/to/db.db' or 'C:\\path\\to\\db.db'
                In-memory: ':memory:'
                PostgreSQL: 'postgresql+asyncpg://user:pass@host/db'

        Note:
            Tables are created via Alembic migrations, not here.
            Call connect() after initialization to ensure tables exist.
        """
        self.logger = logging.getLogger(__name__)

        # Convert file paths to SQLAlchemy URLs
        if not database_url.startswith(('sqlite+', 'postgresql+', 'mysql+')):
            if database_url == ':memory:':
                database_url = 'sqlite+aiosqlite:///:memory:'
            else:
                # Convert file path to URL (works for relative and absolute paths)
                import pathlib
                import urllib.parse
                path_obj = pathlib.Path(database_url)
                # Ensure absolute path for consistency
                if not path_obj.is_absolute():
                    path_obj = path_obj.resolve()
                # Convert to URI format (forward slashes, URL-encoded)
                path_str = path_obj.as_posix()  # Convert \\ to /
                encoded_path = urllib.parse.quote(path_str, safe='/:')
                database_url = f'sqlite+aiosqlite:///{encoded_path}'

        self.database_url = database_url
        self.is_postgresql = database_url.startswith('postgresql')

        # Determine connection pool settings based on environment
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
        if self.is_postgresql:
            connect_args = {
                'server_settings': {
                    'application_name': 'rosey-bot',
                    'jit': 'off',  # Disable JIT for short queries
                },
                'command_timeout': 60,  # Statement timeout
            }

        # Create async engine with connection pooling
        # Note: SQLite uses NullPool (no pooling), so pool args only for PostgreSQL
        engine_kwargs = {
            'echo': False,  # Set True to log all SQL queries
            'pool_pre_ping': True,  # Verify connections before use
        }

        # Add pooling args only for PostgreSQL (SQLite uses NullPool)
        if self.is_postgresql:
            engine_kwargs.update({
                'pool_size': pool_size,
                'max_overflow': max_overflow,
                'pool_timeout': 30,  # Wait 30s for connection
                'pool_recycle': 3600,  # Recycle connections every hour
            })

        # Add PostgreSQL-specific args
        if connect_args:
            engine_kwargs['connect_args'] = connect_args

        self.engine = create_async_engine(database_url, **engine_kwargs)

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )

        self._is_connected = False
        
        # Initialize schema registry (Sprint 13)
        from common.schema_registry import SchemaRegistry
        self.schema_registry = SchemaRegistry(self)
        
        # Table cache for row operations (Sprint 13 Sortie 2)
        self._table_cache = {}
        
        self.logger.info(
            'Database engine initialized: %s (pool: %d+%d)',
            'PostgreSQL' if self.is_postgresql else 'SQLite',
            pool_size,
            max_overflow
        )

    async def connect(self) -> None:
        """
        Connect to database and verify connection.

        This method verifies the database connection is working.
        Tables are created via Alembic migrations, not here.

        Maintained for compatibility with Sprint 10 tests.

        Example:
            db = BotDatabase('sqlite+aiosqlite:///test.db')
            await db.connect()
            await db.user_joined('Alice')
            await db.close()

        Raises:
            RuntimeError: If already connected
        """
        if self._is_connected:
            raise RuntimeError(f"Database already connected: {self.database_url}")

        self.logger.info('Verifying database connection...')

        # Verify connection by executing simple query
        async with self._get_session() as session:
            result = await session.execute(select(func.count()).select_from(UserStats))
            count = result.scalar()
            self._is_connected = True
            self.logger.info('Database connected (%d users)', count)
        
        # Load schema registry cache (Sprint 13)
        await self.schema_registry.load_cache()

    async def close(self) -> None:
        """
        Close database engine and all pooled connections.

        Disposes of the engine and closes all connections in the pool.
        Safe to call multiple times - subsequent calls are no-ops.

        Should be called during application shutdown.

        Example:
            await db.close()
        """
        if not self._is_connected:
            self.logger.debug('Database already closed or never connected')
            return

        try:
            # Update active sessions (close any open user sessions)
            now = int(time.time())
            async with self._get_session() as session:
                await session.execute(
                    update(UserStats)
                    .where(UserStats.current_session_start.is_not(None))
                    .values(
                        total_time_connected=UserStats.total_time_connected +
                            (now - UserStats.current_session_start),
                        current_session_start=None,
                        last_seen=now
                    )
                )

            # Dispose engine (closes all pooled connections)
            await self.engine.dispose()
            self.logger.info('Database connection closed')

        except Exception as e:
            self.logger.error('Error closing database: %s', e)
            raise

        finally:
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if database is currently connected.

        Returns:
            bool: True if connected, False otherwise
        """
        return self._is_connected

    @asynccontextmanager
    async def _get_session(self):
        """
        Get async session from pool (context manager).

        Automatically handles commit/rollback/cleanup.
        Sessions are acquired from the connection pool.

        Usage:
            async with self._get_session() as session:
                result = await session.execute(select(UserStats))
                # Commit happens automatically on success
                # Rollback happens automatically on exception

        Yields:
            AsyncSession: Database session
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # ========================================================================
    # User Tracking Methods
    # ========================================================================

    async def user_joined(self, username):
        """
        Record a user joining the channel.

        Args:
            username: Username that joined
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Check if user exists
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                # Update existing user - start new session
                user.last_seen = now
                user.current_session_start = now
            else:
                # New user - create entry
                user = UserStats(
                    username=username,
                    first_seen=now,
                    last_seen=now,
                    current_session_start=now,
                    total_chat_lines=0,
                    total_time_connected=0
                )
                session.add(user)

            # Commit handled by context manager

    async def user_left(self, username):
        """
        Record a user leaving the channel.

        Args:
            username: Username that left
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Get user
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user and user.current_session_start:
                # Calculate session duration
                session_duration = now - user.current_session_start

                # Update stats
                user.last_seen = now
                user.total_time_connected += session_duration
                user.current_session_start = None

                # Commit handled by context manager

    async def user_chat_message(self, username, message=None):
        """
        Increment chat message count for user and optionally log message.

        Args:
            username: Username that sent a message
            message: Optional message text to store in recent_chat
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Update user stats (increment counter)
            await session.execute(
                update(UserStats)
                .where(UserStats.username == username)
                .values(
                    total_chat_lines=UserStats.total_chat_lines + 1,
                    last_seen=now
                )
            )

            # Store in recent chat if message provided
            if message and username and username.lower() != 'server':
                # Add message
                chat = RecentChat(
                    timestamp=now,
                    username=username,
                    message=message
                )
                session.add(chat)

                # Cleanup old messages (retention: 150 hours)
                retention_hours = 150
                cutoff = now - (retention_hours * 3600)
                await session.execute(
                    delete(RecentChat).where(RecentChat.timestamp < cutoff)
                )

            # Commit handled by context manager

    async def get_recent_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """
        Get recent chat messages from database.

        Returns messages sorted by timestamp descending (most recent first).
        Used for chat history display and throughput benchmarks.

        Args:
            limit: Maximum messages to return (default 100)
            offset: Number of messages to skip for pagination (default 0)

        Returns:
            List of message dicts with keys:
            - id: Message ID (int)
            - timestamp: Unix timestamp (int)
            - username: Username who sent message (str)
            - message: Message text (str)

        Example:
            messages = await db.get_recent_messages(limit=10)
            for msg in messages:
                print(f\"{msg['username']}: {msg['message']}\")
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(RecentChat)
                .order_by(RecentChat.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            messages = result.scalars().all()

            return [
                {
                    'id': msg.id,
                    'timestamp': msg.timestamp,
                    'username': msg.username,
                    'message': msg.message
                }
                for msg in messages
            ]

    async def log_chat(self, username: str, message: str, timestamp: int = None) -> None:
        """
        Log chat message to database.

        Convenience method for performance benchmarks. Production code
        should use user_chat_message() which includes additional tracking.

        Args:
            username: Username who sent message
            message: Message text
            timestamp: Unix timestamp (default: current time)

        Example:
            await db.log_chat('Alice', 'Hello world!')
        """
        if timestamp is None:
            timestamp = int(time.time())

        async with self._get_session() as session:
            chat = RecentChat(
                timestamp=timestamp,
                username=username,
                message=message
            )
            session.add(chat)

            # Commit handled by context manager

    # ========================================================================
    # Audit Logging
    # ========================================================================

    async def log_user_action(self, username, action_type, details=None):
        """
        Log a user action (PM command, moderation, etc.).

        Args:
            username: Username performing the action
            action_type: Type of action (e.g., 'pm_command', 'kick')
            details: Optional details about the action
        """
        now = int(time.time())

        async with self._get_session() as session:
            action = UserAction(
                timestamp=now,
                username=username,
                action_type=action_type,
                details=details
            )
            session.add(action)
            # Commit handled by context manager

    # ========================================================================
    # Channel Statistics
    # ========================================================================

    async def update_high_water_mark(self, current_user_count,
                                    current_connected_count=None):
        """
        Update high water mark if current count exceeds it.

        Args:
            current_user_count: Current number of users in chat
            current_connected_count: Current number of connected viewers
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Get or create channel stats (singleton)
            result = await session.execute(
                select(ChannelStats).where(ChannelStats.id == 1)
            )
            stats = result.scalar_one_or_none()

            if not stats:
                # Initialize
                stats = ChannelStats(
                    id=1,
                    max_users=0,
                    last_updated=now
                )
                session.add(stats)

            # Update high water marks
            if current_user_count > stats.max_users:
                stats.max_users = current_user_count
                stats.max_users_timestamp = now
                self.logger.info('New high water mark (chat): %d users',
                               current_user_count)

            if current_connected_count and current_connected_count > (stats.max_connected or 0):
                stats.max_connected = current_connected_count
                stats.max_connected_timestamp = now
                self.logger.info('New high water mark (connected): %d viewers',
                               current_connected_count)

            stats.last_updated = now
            # Commit handled by context manager

    async def get_user_stats(self, username):
        """
        Get statistics for a specific user.

        Args:
            username: Username to look up

        Returns:
            dict: User stats or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                return {
                    'username': user.username,
                    'first_seen': user.first_seen,
                    'last_seen': user.last_seen,
                    'total_chat_lines': user.total_chat_lines,
                    'total_time_connected': user.total_time_connected,
                    'current_session_start': user.current_session_start
                }
            return None

    async def get_high_water_mark(self):
        """
        Get the high water marks for both chat and connected users.

        Returns:
            tuple: (max_chat_users, max_connected_users) or (0, 0)
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(ChannelStats).where(ChannelStats.id == 1)
            )
            stats = result.scalar_one_or_none()

            if stats:
                return (stats.max_users, stats.max_connected or 0)
            return (0, 0)

    async def get_high_water_mark_connected(self):
        """
        Get the high water mark for connected viewers.

        Returns:
            tuple: (max_connected, timestamp) or (0, None)
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(ChannelStats).where(ChannelStats.id == 1)
            )
            stats = result.scalar_one_or_none()

            if stats:
                return (stats.max_connected, stats.max_connected_timestamp)
            return (0, None)

    async def get_top_chatters(self, limit=10):
        """
        Get top chatters by message count.

        Args:
            limit: Number of results to return

        Returns:
            list of dicts: Each dict has 'username' and 'total_chat_lines'
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(UserStats)
                .where(UserStats.total_chat_lines > 0)
                .order_by(UserStats.total_chat_lines.desc())
                .limit(limit)
            )
            users = result.scalars().all()

            return [
                {
                    'username': user.username,
                    'total_chat_lines': user.total_chat_lines
                }
                for user in users
            ]

    async def get_total_users_seen(self):
        """
        Get total number of unique users ever seen.

        Returns:
            int: Total unique users
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(UserStats)
            )
            count = result.scalar()
            return count

    # ========================================================================
    # Historical Tracking
    # ========================================================================

    async def log_user_count(self, *args):
        """
        Log current user counts for historical tracking.

        Args:
            Two calling conventions supported:
            - log_user_count(chat_users, connected_users)  # Production (uses current time)
            - log_user_count(timestamp, chat_users, connected_users)  # Tests (uses provided timestamp)
        """
        if len(args) == 2:
            chat_users, connected_users = args
            timestamp = int(time.time())
        elif len(args) == 3:
            # Old format: (timestamp, chat, conn) - use provided timestamp for tests
            timestamp, chat_users, connected_users = args
        else:
            raise TypeError(
                f"log_user_count() takes 2 or 3 positional arguments but {len(args)} were given"
            )

        async with self._get_session() as session:
            history = UserCountHistory(
                timestamp=timestamp,
                chat_users=chat_users,
                connected_users=connected_users
            )
            session.add(history)
            # Commit handled by context manager

    async def get_user_count_history(self, hours=None, since=None):
        """
        Get user count history for the specified time period.

        Args:
            hours: Number of hours of history to retrieve (default 24)
            since: Alternative to hours - absolute timestamp cutoff

        Returns:
            list: List of dicts with timestamp, chat_users, connected_users
        """
        if since is not None:
            cutoff = since
        elif hours is not None:
            cutoff = int(time.time()) - (hours * 3600)
        else:
            cutoff = int(time.time()) - (24 * 3600)  # Default 24 hours

        async with self._get_session() as session:
            result = await session.execute(
                select(UserCountHistory)
                .where(UserCountHistory.timestamp >= cutoff)
                .order_by(UserCountHistory.timestamp.asc())
            )
            history = result.scalars().all()

            return [
                {
                    'timestamp': h.timestamp,
                    'chat_users': h.chat_users,
                    'connected_users': h.connected_users
                }
                for h in history
            ]

    async def cleanup_old_history(self, days=30):
        """
        Remove user count history older than specified days.

        Args:
            days: Keep history for this many days (default 30)

        Returns:
            int: Number of records deleted
        """
        cutoff = int(time.time()) - (days * 86400)

        async with self._get_session() as session:
            result = await session.execute(
                delete(UserCountHistory).where(UserCountHistory.timestamp < cutoff)
            )
            deleted = result.rowcount

            if deleted > 0:
                self.logger.info('Cleaned up %d old history records', deleted)

            return deleted

    # ========================================================================
    # Recent Chat
    # ========================================================================

    async def get_recent_chat(self, limit=20):
        """
        Get recent chat messages.

        Args:
            limit: Maximum number of messages to retrieve (default 20)

        Returns:
            list: List of dicts with timestamp, username, message in reverse
                chronological order (newest first). Note: Messages with identical
                timestamps may appear in reverse insertion order due to SQLite's
                tie-breaking behavior.
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(RecentChat)
                .order_by(RecentChat.timestamp.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            # Convert to dicts and reverse (to get oldest-to-newest for limit)
            chat_list = [
                {
                    'timestamp': msg.timestamp,
                    'username': msg.username,
                    'message': msg.message
                }
                for msg in messages
            ]
            chat_list.reverse()
            return chat_list

    async def get_recent_chat_since(self, minutes=None, since=None, limit=1000):
        """
        Get recent chat messages since a specific time.

        Args:
            minutes: Time window in minutes to retrieve messages for (default 20).
            since: Alternative to minutes - absolute timestamp cutoff (exclusive).
            limit: Maximum number of messages to return (safety cap).

        Returns:
            list of dicts with timestamp, username, message in chronological
                order (oldest first, ascending by timestamp).

        Note: When using 'since', returns messages with timestamp > since (not >=).
        """
        # Support both 'minutes' and 'since' parameter names
        if since is not None:
            since_timestamp = since
            # Use > not >= when since is explicit timestamp
            use_gt = True
        elif minutes is not None:
            since_timestamp = int(time.time()) - (minutes * 60)
            use_gt = False
        else:
            since_timestamp = int(time.time()) - (20 * 60)  # Default 20 minutes
            use_gt = False

        async with self._get_session() as session:
            if use_gt:
                where_clause = RecentChat.timestamp > since_timestamp
            else:
                where_clause = RecentChat.timestamp >= since_timestamp

            result = await session.execute(
                select(RecentChat)
                .where(where_clause)
                .order_by(RecentChat.timestamp.asc())
                .limit(limit)
            )
            messages = result.scalars().all()

            return [
                {
                    'timestamp': msg.timestamp,
                    'username': msg.username,
                    'message': msg.message
                }
                for msg in messages
            ]

    # ========================================================================
    # Outbound Messages Queue
    # ========================================================================

    async def enqueue_outbound_message(self, message):
        """
        Add a message to the outbound queue for the bot to send.

        Args:
            message: Text message to send

        Returns:
            id of inserted outbound message
        """
        now = int(time.time())

        async with self._get_session() as session:
            outbound = OutboundMessage(
                timestamp=now,
                message=message,
                sent=False,
                retry_count=0
            )
            session.add(outbound)
            await session.flush()  # Flush to get the ID
            return outbound.id

    async def get_unsent_outbound_messages(self, limit=50, max_retries=3, bypass_backoff=False):
        """
        Fetch unsent outbound messages ready for sending.

        Only returns messages that haven't exceeded retry limit.
        Uses exponential backoff: messages with higher retry counts
        will be delayed longer before being returned.

        Args:
            limit: Max number of messages to fetch
            max_retries: Maximum retry attempts before giving up
            bypass_backoff: If True, skip backoff delay (for testing)

        Returns:
            list of rows as dicts (includes retry_count and last_error)
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Build WHERE clause
            where_clauses = [
                OutboundMessage.sent.is_(False),
                OutboundMessage.retry_count < max_retries
            ]

            # Add backoff check unless bypassed (for tests)
            if not bypass_backoff:
                where_clauses.append(
                    or_(
                        OutboundMessage.retry_count == 0,
                        OutboundMessage.timestamp +
                            literal_column('(1 << retry_count) * 60') <= now
                    )
                )

            result = await session.execute(
                select(OutboundMessage)
                .where(*where_clauses)
                .order_by(OutboundMessage.timestamp.asc())
                .limit(limit)
            )
            messages = result.scalars().all()

            return [
                {
                    'id': msg.id,
                    'timestamp': msg.timestamp,
                    'message': msg.message,
                    'retry_count': msg.retry_count,
                    'last_error': msg.error_message
                }
                for msg in messages
            ]

    async def mark_outbound_sent(self, outbound_id):
        """
        Mark outbound message as successfully sent.

        Records sent timestamp and marks as sent.

        Args:
            outbound_id: Message ID to mark as sent
        """
        now = int(time.time())

        async with self._get_session() as session:
            await session.execute(
                update(OutboundMessage)
                .where(OutboundMessage.id == outbound_id)
                .values(sent=True, sent_timestamp=now)
            )
            # Commit handled by context manager

    async def mark_outbound_failed(self, outbound_id, error_msg, is_permanent=False):
        """
        Mark outbound message send attempt as failed.

        Increments retry count for transient errors, or marks as permanently
        failed for errors like permission denied or muted.

        Args:
            outbound_id: Message ID that failed
            error_msg: Error message description
            is_permanent: If True, mark as sent to prevent further retries
        """
        now = int(time.time())

        async with self._get_session() as session:
            if is_permanent:
                # Permanent failure - mark as "sent" to stop retries
                await session.execute(
                    update(OutboundMessage)
                    .where(OutboundMessage.id == outbound_id)
                    .values(
                        sent=True,
                        sent_timestamp=now,
                        retry_count=OutboundMessage.retry_count + 1,
                        error_message=error_msg
                    )
                )
                self.logger.warning('Outbound message %d permanently failed: %s',
                                  outbound_id, error_msg)
            else:
                # Transient failure - increment retry count for backoff
                await session.execute(
                    update(OutboundMessage)
                    .where(OutboundMessage.id == outbound_id)
                    .values(
                        retry_count=OutboundMessage.retry_count + 1,
                        error_message=error_msg
                    )
                )
                self.logger.info('Outbound message %d failed (will retry): %s',
                               outbound_id, error_msg)

            # Commit handled by context manager

    # ========================================================================
    # Current Status
    # ========================================================================

    async def update_current_status(self, **kwargs):
        """
        Update current bot status (creates row if doesn't exist).

        Args:
            **kwargs: Status fields to update (bot_name, bot_rank, bot_afk,
                     channel_name, current_chat_users, current_connected_users,
                     playlist_items, current_media_title, current_media_duration,
                     bot_start_time, bot_connected)
        """
        allowed_fields = [
            'bot_name', 'bot_rank', 'bot_afk', 'channel_name',
            'current_chat_users', 'current_connected_users',
            'playlist_items', 'current_media_title',
            'current_media_duration', 'bot_start_time', 'bot_connected'
        ]

        # Filter to allowed fields
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return

        # Add last_updated timestamp
        updates['last_updated'] = int(time.time())

        async with self._get_session() as session:
            # Check if row exists, create if not (singleton pattern)
            result = await session.execute(
                select(CurrentStatus).where(CurrentStatus.id == 1)
            )
            status = result.scalar_one_or_none()

            if not status:
                # Create initial row
                status = CurrentStatus(
                    id=1,
                    last_updated=updates['last_updated'],
                    status='offline'
                )
                session.add(status)
                await session.flush()  # Ensure row exists before update

            # Now update
            await session.execute(
                update(CurrentStatus)
                .where(CurrentStatus.id == 1)
                .values(**updates)
            )

    async def get_current_status(self):
        """
        Get current bot status.

        Returns:
            dict: Current status or None if not available
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(CurrentStatus).where(CurrentStatus.id == 1)
            )
            status = result.scalar_one_or_none()

            if status:
                return {
                    'id': status.id,
                    'bot_name': status.bot_name,
                    'bot_rank': status.bot_rank,
                    'bot_afk': status.bot_afk,
                    'channel_name': status.channel_name,
                    'current_chat_users': status.current_chat_users,
                    'current_connected_users': status.current_connected_users,
                    'playlist_items': status.playlist_items,
                    'current_media_title': status.current_media_title,
                    'current_media_duration': status.current_media_duration,
                    'bot_start_time': status.bot_start_time,
                    'bot_connected': status.bot_connected,
                    'last_updated': status.last_updated
                }
            return None

    async def generate_api_token(self, description=''):
        """
        Generate a new API token for external app authentication.

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
        now = int(time.time())

        async with self._get_session() as session:
            api_token = ApiToken(
                token=token,
                description=description,
                created_at=now,
                is_active=True
            )
            session.add(api_token)

        self.logger.info('Generated new API token: %s...', token[:8])
        return token

    async def validate_api_token(self, token):
        """
        Check if an API token is valid (exists and not revoked).

        Also updates the last_used timestamp for valid tokens.

        Args:
            token: The token string to validate

        Returns:
            bool: True if token is valid, False otherwise
        """
        if not token:
            return False

        async with self._get_session() as session:
            result = await session.execute(
                select(ApiToken).where(
                    ApiToken.token == token,
                    ApiToken.is_active
                )
            )
            api_token = result.scalar_one_or_none()

            if api_token:
                # Update last_used timestamp
                api_token.last_used = int(time.time())
                return True

            return False

    async def revoke_api_token(self, token):
        """
        Revoke an API token, preventing its further use.

        Args:
            token: The token to revoke (can be partial - first 8+ chars)

        Returns:
            int: Number of tokens revoked
        """
        async with self._get_session() as session:
            # Support partial token matching for convenience (min 8 chars)
            if len(token) >= 8:
                result = await session.execute(
                    update(ApiToken)
                    .where(
                        ApiToken.token.startswith(token),
                        ApiToken.is_active
                    )
                    .values(is_active=False)
                )
            else:
                # Exact match only for short strings
                result = await session.execute(
                    update(ApiToken)
                    .where(
                        ApiToken.token == token,
                        ApiToken.is_active
                    )
                    .values(is_active=False)
                )

            count = result.rowcount

            if count > 0:
                self.logger.info('Revoked %d API token(s)', count)

            return count

    async def list_api_tokens(self, include_revoked=False):
        """
        List all API tokens with their metadata.

        Args:
            include_revoked: If True, include revoked tokens

        Returns:
            list: List of dicts with token metadata (token is truncated
                  for security)
        """
        async with self._get_session() as session:
            if include_revoked:
                result = await session.execute(
                    select(ApiToken).order_by(ApiToken.created_at.desc())
                )
            else:
                result = await session.execute(
                    select(ApiToken)
                    .where(ApiToken.is_active)
                    .order_by(ApiToken.created_at.desc())
                )

            tokens = result.scalars().all()

            # Convert to dicts and truncate tokens for security
            return [
                {
                    'token_preview': token.token[:8] + '...',
                    'description': token.description,
                    'created_at': token.created_at,
                    'last_used': token.last_used,
                    'revoked': not token.is_active
                }
                for token in tokens
            ]

    # ========================================================================
    # Plugin KV Storage Methods (Sprint 12)
    # ========================================================================

    async def kv_set(
        self,
        plugin_name: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Set a key-value pair for a plugin with optional TTL.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
            value: Any JSON-serializable value
            ttl_seconds: Optional TTL in seconds (None = no expiration)
            
        Raises:
            ValueError: If value exceeds 64KB when serialized
            TypeError: If value is not JSON-serializable
            
        Example:
            await db.kv_set('trivia', 'config', {'theme': 'dark'})
            await db.kv_set('trivia', 'session', data, ttl_seconds=1800)
        """
        # Serialize value to JSON
        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Value is not JSON-serializable: {e}")
        
        # Check size limit (64KB)
        size_bytes = len(value_json.encode('utf-8'))
        if size_bytes > 65536:
            raise ValueError(
                f"Value size ({size_bytes} bytes) exceeds 64KB limit (65536 bytes)"
            )
        
        # Calculate expiration timestamp
        expires_at = None
        if ttl_seconds is not None and ttl_seconds > 0:
            expires_at = int(time.time()) + ttl_seconds
        
        # Get current timestamp
        now = int(time.time())
        
        async with self._get_session() as session:
            # Use dialect-specific insert for upsert
            if self.is_postgresql:
                # PostgreSQL: INSERT ... ON CONFLICT DO UPDATE
                stmt = pg_insert(PluginKVStorage).values(
                    plugin_name=plugin_name,
                    key=key,
                    value_json=value_json,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['plugin_name', 'key'],
                    set_={
                        'value_json': value_json,
                        'expires_at': expires_at,
                        'updated_at': now
                    }
                )
            else:
                # SQLite: INSERT ... ON CONFLICT DO UPDATE
                stmt = sqlite_insert(PluginKVStorage).values(
                    plugin_name=plugin_name,
                    key=key,
                    value_json=value_json,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['plugin_name', 'key'],
                    set_={
                        'value_json': value_json,
                        'expires_at': expires_at,
                        'updated_at': now
                    }
                )
            
            await session.execute(stmt)

    async def kv_get(
        self,
        plugin_name: str,
        key: str
    ) -> dict:
        """
        Get a key-value pair for a plugin.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
        
        Returns:
            {'exists': bool, 'value': Any}
            If key doesn't exist or is expired: {'exists': False}
            
        Example:
            result = await db.kv_get('trivia', 'config')
            if result['exists']:
                config = result['value']
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(PluginKVStorage).where(
                    PluginKVStorage.plugin_name == plugin_name,
                    PluginKVStorage.key == key
                )
            )
            row = result.scalar_one_or_none()
            
            if row is None:
                return {'exists': False}
            
            # Check expiration
            if row.is_expired:
                return {'exists': False}
            
            # Deserialize value
            try:
                value = json.loads(row.value_json)
            except json.JSONDecodeError as e:
                # Log error but don't crash
                self.logger.error(
                    f"Failed to deserialize KV value for {plugin_name}/{key}: {e}"
                )
                return {'exists': False}
            
            return {
                'exists': True,
                'value': value
            }

    async def kv_delete(
        self,
        plugin_name: str,
        key: str
    ) -> bool:
        """
        Delete a key-value pair for a plugin.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
        
        Returns:
            True if key was deleted, False if didn't exist
            
        Example:
            deleted = await db.kv_delete('trivia', 'old_session')
            if deleted:
                print('Session deleted')
        """
        async with self._get_session() as session:
            result = await session.execute(
                delete(PluginKVStorage).where(
                    PluginKVStorage.plugin_name == plugin_name,
                    PluginKVStorage.key == key
                )
            )
            return result.rowcount > 0

    async def kv_list(
        self,
        plugin_name: str,
        prefix: str = '',
        limit: int = 1000
    ) -> dict:
        """
        List keys for a plugin with optional prefix filter.
        
        Args:
            plugin_name: Plugin identifier
            prefix: Optional key prefix filter
            limit: Maximum keys to return (default 1000)
        
        Returns:
            {
                'keys': [str],           # List of key names
                'count': int,            # Number of keys returned
                'truncated': bool        # True if more results available
            }
            
        Example:
            # List all keys
            result = await db.kv_list('trivia')
            
            # List keys with prefix
            result = await db.kv_list('trivia', prefix='user:')
        """
        now = int(time.time())
        
        async with self._get_session() as session:
            # Build query
            stmt = select(PluginKVStorage.key).where(
                PluginKVStorage.plugin_name == plugin_name,
                # Only non-expired entries
                or_(
                    PluginKVStorage.expires_at.is_(None),
                    PluginKVStorage.expires_at > now
                )
            )
            
            # Apply prefix filter if provided
            if prefix:
                stmt = stmt.where(PluginKVStorage.key.like(f'{prefix}%'))
            
            # Order by key and fetch limit+1 to detect truncation
            stmt = stmt.order_by(PluginKVStorage.key).limit(limit + 1)
            
            result = await session.execute(stmt)
            keys = [row[0] for row in result.fetchall()]
            
            # Check if results were truncated
            truncated = len(keys) > limit
            if truncated:
                keys = keys[:limit]
            
            return {
                'keys': keys,
                'count': len(keys),
                'truncated': truncated
            }

    async def kv_cleanup_expired(self) -> int:
        """
        Remove all expired keys across all plugins.
        
        Returns:
            Number of keys deleted
            
        Example:
            deleted = await db.kv_cleanup_expired()
            print(f'Cleaned up {deleted} expired keys')
        """
        now = int(time.time())
        
        async with self._get_session() as session:
            result = await session.execute(
                delete(PluginKVStorage).where(
                    PluginKVStorage.expires_at.is_not(None),
                    PluginKVStorage.expires_at < now
                )
            )
            return result.rowcount

    async def perform_maintenance(self):
        """
        Perform periodic database maintenance tasks.

        This is designed to be called by a background task and includes:
        - Cleanup of old user count history (keep last 30 days)
        - Cleanup of old outbound messages (keep last 7 days)
        - Cleanup of old revoked tokens (keep last 90 days)
        - VACUUM to reclaim space and optimize database
        - ANALYZE to update query planner statistics

        Safe to call multiple times; operations are idempotent.
        """
        maintenance_log = []

        try:
            # Cleanup old user count history (30 days retention)
            deleted_history = await self.cleanup_old_history(days=30)
            if deleted_history > 0:
                maintenance_log.append(
                    f'Cleaned {deleted_history} old history records'
                )

            # Cleanup old outbound messages that were sent >7 days ago
            cutoff_sent = int(time.time()) - (7 * 86400)
            async with self._get_session() as session:
                result = await session.execute(
                    delete(OutboundMessage).where(
                        OutboundMessage.sent.is_(True),
                        OutboundMessage.sent_timestamp < cutoff_sent
                    )
                )
                deleted_outbound = result.rowcount
                if deleted_outbound > 0:
                    maintenance_log.append(
                        f'Cleaned {deleted_outbound} old outbound messages'
                    )

            # Cleanup old revoked tokens (>90 days)
            cutoff_tokens = int(time.time()) - (90 * 86400)
            async with self._get_session() as session:
                result = await session.execute(
                    delete(ApiToken).where(
                        ApiToken.is_active.is_(False),
                        ApiToken.created_at < cutoff_tokens
                    )
                )
                deleted_tokens = result.rowcount
                if deleted_tokens > 0:
                    maintenance_log.append(
                        f'Cleaned {deleted_tokens} old revoked tokens'
                    )

            # VACUUM and ANALYZE must be done outside transaction
            # PostgreSQL requires autocommit mode, SQLite is fine either way
            self.logger.info('Running VACUUM to optimize database...')
            async with self.engine.connect() as conn:
                # Set autocommit for PostgreSQL (no-op for SQLite)
                conn_autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn_autocommit.execute(text('VACUUM'))
                maintenance_log.append('VACUUM completed')

                await conn.execute(text('ANALYZE'))
                maintenance_log.append('ANALYZE completed')

            self.logger.info(
                'Database maintenance completed: %s',
                ', '.join(maintenance_log)
            )

            return maintenance_log

        except Exception as e:
            self.logger.error('Database maintenance error: %s', e)
            raise

    # ==================== Row Storage Operations (Sprint 13) ====================

    async def get_table(self, full_table_name: str) -> Table:
        """
        Get SQLAlchemy Table object for plugin table (with caching).
        
        Args:
            full_table_name: Full table name (e.g., "quote_db_quotes")
        
        Returns:
            SQLAlchemy Table object
        
        Example:
            table = await db.get_table("myplugin_data")
            # Use table for queries
        """
        if full_table_name not in self._table_cache:
            # Reflect table from database using async connection
            metadata = MetaData()
            async with self.engine.connect() as conn:
                await conn.run_sync(
                    lambda sync_conn: metadata.reflect(
                        bind=sync_conn,
                        only=[full_table_name]
                    )
                )
            
            table = metadata.tables[full_table_name]
            self._table_cache[full_table_name] = table
        
        return self._table_cache[full_table_name]

    def _validate_and_coerce_row(self, data: dict, schema: dict) -> dict:
        """
        Validate row data against schema and coerce types.
        
        Args:
            data: Row data to validate
            schema: Schema definition from SchemaRegistry
        
        Returns:
            Validated and coerced data dict
        
        Raises:
            ValueError: If validation fails or type coercion impossible
        
        Example:
            schema = {'fields': [
                {'name': 'count', 'type': 'integer', 'required': True}
            ]}
            result = db._validate_and_coerce_row({'count': '42'}, schema)
            # result = {'count': 42}
        """
        result = {}
        schema_fields = {f['name']: f for f in schema['fields']}
        
        # Check required fields
        for field in schema['fields']:
            if field.get('required', False) and field['name'] not in data:
                raise ValueError(f"Missing required field: {field['name']}")
        
        # Validate and coerce each field in data
        for key, value in data.items():
            if key not in schema_fields:
                raise ValueError(f"Unknown field: {key}")
            
            field_def = schema_fields[key]
            field_type = field_def['type']
            
            # Handle None values
            if value is None:
                if field_def.get('required', False):
                    raise ValueError(f"Field '{key}' cannot be null")
                result[key] = None
                continue
            
            # Type coercion
            try:
                if field_type == 'string':
                    result[key] = str(value)
                
                elif field_type == 'text':
                    result[key] = str(value)
                
                elif field_type == 'integer':
                    if isinstance(value, str):
                        result[key] = int(value)
                    elif isinstance(value, (int, float)):
                        result[key] = int(value)
                    else:
                        raise ValueError(f"Cannot convert {type(value).__name__} to integer")
                
                elif field_type == 'float':
                    result[key] = float(value)
                
                elif field_type == 'boolean':
                    if isinstance(value, bool):
                        result[key] = value
                    elif isinstance(value, str):
                        result[key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        result[key] = bool(value)
                
                elif field_type == 'datetime':
                    if isinstance(value, datetime):
                        result[key] = value
                    elif isinstance(value, str):
                        # Try ISO 8601 format
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        raise ValueError(f"Cannot convert {type(value).__name__} to datetime")
            
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Field '{key}': Cannot convert value to {field_type}: {e}"
                )
        
        return result

    async def row_insert(
        self,
        plugin_name: str,
        table_name: str,
        data: dict | list[dict]
    ) -> dict:
        """
        Insert row(s) into plugin table.
        
        Args:
            plugin_name: Plugin identifier (e.g., "quote_db")
            table_name: Table name without plugin prefix (e.g., "quotes")
            data: Single dict or list of dicts to insert
        
        Returns:
            Single insert: {"id": 42, "created": True}
            Bulk insert: {"ids": [42, 43, 44], "created": 3}
        
        Raises:
            ValueError: If table not registered or data invalid
        
        Example:
            # Single insert
            result = await db.row_insert(
                "quote_db", "quotes",
                {"text": "Hello world", "author": "Alice"}
            )
            # result = {"id": 1, "created": True}
            
            # Bulk insert
            result = await db.row_insert(
                "quote_db", "quotes",
                [
                    {"text": "Quote 1", "author": "Bob"},
                    {"text": "Quote 2", "author": "Charlie"}
                ]
            )
            # result = {"ids": [2, 3], "created": 2}
        """
        # Get schema
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'. "
                f"Register schema first using schema_register."
            )
        
        # Handle bulk vs single
        is_bulk = isinstance(data, list)
        rows = data if is_bulk else [data]
        
        if len(rows) == 0:
            raise ValueError("No data provided for insert")
        
        # Validate and coerce all rows
        validated_rows = []
        for i, row in enumerate(rows):
            try:
                validated = self._validate_and_coerce_row(row, schema)
                # Add timestamps if not present
                now = datetime.now()
                if 'created_at' not in validated:
                    validated['created_at'] = now
                if 'updated_at' not in validated:
                    validated['updated_at'] = now
                validated_rows.append(validated)
            except ValueError as e:
                raise ValueError(f"Row {i}: {e}")
        
        # Get table
        full_table_name = f"{plugin_name}_{table_name}"
        table = await self.get_table(full_table_name)
        
        # Insert with transaction
        async with self._get_session() as session:
            if is_bulk:
                # Bulk insert with RETURNING
                stmt = insert(table).returning(table.c.id)
                result = await session.execute(stmt, validated_rows)
                ids = [row[0] for row in result.fetchall()]
                
                return {
                    "ids": ids,
                    "created": len(ids)
                }
            else:
                # Single insert
                stmt = insert(table).values(**validated_rows[0]).returning(table.c.id)
                result = await session.execute(stmt)
                row_id = result.scalar()
                
                return {
                    "id": row_id,
                    "created": True
                }

    async def row_select(
        self,
        plugin_name: str,
        table_name: str,
        row_id: int
    ) -> dict:
        """
        Select row by primary key ID.
        
        Args:
            plugin_name: Plugin identifier (e.g., "quote_db")
            table_name: Table name without plugin prefix (e.g., "quotes")
            row_id: Primary key ID
        
        Returns:
            {"exists": True, "data": {...}} if found
            {"exists": False} if not found
        
        Example:
            result = await db.row_select("quote_db", "quotes", 1)
            if result['exists']:
                print(result['data'])  # {'id': 1, 'text': '...', ...}
        """
        # Verify table exists
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        # Get table and select
        full_table_name = f"{plugin_name}_{table_name}"
        table = await self.get_table(full_table_name)
        
        async with self._get_session() as session:
            stmt = select(table).where(table.c.id == row_id)
            result = await session.execute(stmt)
            row = result.fetchone()
            
            if row:
                # Convert to dict and serialize datetimes
                data = dict(row._mapping)
                
                # Convert datetime objects to ISO strings
                for key, value in data.items():
                    if isinstance(value, datetime):
                        data[key] = value.isoformat()
                
                return {
                    "exists": True,
                    "data": data
                }
            else:
                return {
                    "exists": False
                }
