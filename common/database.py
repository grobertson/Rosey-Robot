#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database for bot state persistence and statistics tracking.

Uses SQLAlchemy ORM with async support.
Supports SQLite (dev/test) and PostgreSQL (production).

Migration History:
    v0.5.0: aiosqlite (direct SQL queries)
    v0.6.0: SQLAlchemy ORM (Sprint 11 Sortie 2)
"""
import logging
import sqlite3
import time
from contextlib import asynccontextmanager

from sqlalchemy import select, update, delete, func, literal_column, or_, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)

from common.models import (
    UserStats,
    UserAction,
    ChannelStats,
    UserCountHistory,
    RecentChat,
    CurrentStatus,
    OutboundMessage,
    ApiToken
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
        
        # Create async engine with connection pooling
        # Note: SQLite uses NullPool by default (no pooling args)
        engine_kwargs = {
            'echo': False,  # Set True to log all SQL queries
            'pool_pre_ping': True,  # Verify connections before use
        }
        
        # Only add pooling args for non-SQLite databases
        if not database_url.startswith('sqlite'):
            engine_kwargs['pool_size'] = 5  # Connection pool size
            engine_kwargs['max_overflow'] = 10  # Max overflow connections
        
        self.engine = create_async_engine(database_url, **engine_kwargs)
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )
        
        self._is_connected = False
        self.logger.info('Initialized database: %s', database_url)

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
        Get the high water mark (max users ever in chat).

        Returns:
            tuple: (max_users, timestamp) or (0, None)
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(ChannelStats).where(ChannelStats.id == 1)
            )
            stats = result.scalar_one_or_none()

            if stats:
                return (stats.max_users, stats.max_users_timestamp)
            return (0, None)

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
            list of tuples: (username, chat_lines)
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(UserStats)
                .where(UserStats.total_chat_lines > 0)
                .order_by(UserStats.total_chat_lines.desc())
                .limit(limit)
            )
            users = result.scalars().all()

            return [(user.username, user.total_chat_lines) for user in users]

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

    async def log_user_count(self, chat_users, connected_users):
        """
        Log current user counts for historical tracking.

        Args:
            chat_users: Number of users in chat (with usernames)
            connected_users: Total connected viewers (including anonymous)
        """
        now = int(time.time())

        async with self._get_session() as session:
            history = UserCountHistory(
                timestamp=now,
                chat_users=chat_users,
                connected_users=connected_users
            )
            session.add(history)
            # Commit handled by context manager

    async def get_user_count_history(self, hours=24):
        """
        Get user count history for the specified time period.

        Args:
            hours: Number of hours of history to retrieve (default 24)

        Returns:
            list: List of dicts with timestamp, chat_users, connected_users
        """
        since = int(time.time()) - (hours * 3600)

        async with self._get_session() as session:
            result = await session.execute(
                select(UserCountHistory)
                .where(UserCountHistory.timestamp >= since)
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

    async def get_recent_chat_since(self, minutes=20, limit=1000):
        """
        Get recent chat messages within the last `minutes` minutes.

        Args:
            minutes: Time window in minutes to retrieve messages for.
            limit: Maximum number of messages to return (safety cap).

        Returns:
            list of dicts with timestamp, username, message in chronological
                order (oldest first, ascending by timestamp).
        """
        since = int(time.time()) - (minutes * 60)

        async with self._get_session() as session:
            result = await session.execute(
                select(RecentChat)
                .where(RecentChat.timestamp >= since)
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

    async def get_unsent_outbound_messages(self, limit=50, max_retries=3):
        """
        Fetch unsent outbound messages ready for sending.

        Only returns messages that haven't exceeded retry limit.
        Uses exponential backoff: messages with higher retry counts
        will be delayed longer before being returned.

        Args:
            limit: Max number of messages to fetch
            max_retries: Maximum retry attempts before giving up

        Returns:
            list of rows as dicts (includes retry_count and last_error)
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Complex query with exponential backoff: 2^retry_count minutes
            # Use literal_column for bitshift since SQLAlchemy doesn't support <<
            result = await session.execute(
                select(OutboundMessage)
                .where(
                    OutboundMessage.sent == False,
                    OutboundMessage.retry_count < max_retries,
                    or_(
                        OutboundMessage.retry_count == 0,
                        OutboundMessage.timestamp + 
                            literal_column('(1 << retry_count) * 60') <= now
                    )
                )
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
        Update current bot status.

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
                    ApiToken.is_active == True
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
                        ApiToken.is_active == True
                    )
                    .values(is_active=False)
                )
            else:
                # Exact match only for short strings
                result = await session.execute(
                    update(ApiToken)
                    .where(
                        ApiToken.token == token,
                        ApiToken.is_active == True
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
                    .where(ApiToken.is_active == True)
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
                        OutboundMessage.sent == True,
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
                        ApiToken.is_active == False,
                        ApiToken.created_at < cutoff_tokens
                    )
                )
                deleted_tokens = result.rowcount
                if deleted_tokens > 0:
                    maintenance_log.append(
                        f'Cleaned {deleted_tokens} old revoked tokens'
                    )

            # VACUUM and ANALYZE must be done outside transaction
            # Use raw connection from engine
            async with self.engine.begin() as conn:
                # SQLite VACUUM and ANALYZE
                self.logger.info('Running VACUUM to optimize database...')
                await conn.execute(text('VACUUM'))
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
