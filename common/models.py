#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLAlchemy ORM Models for Rosey Bot
====================================

Defines database schema using SQLAlchemy 2.0 ORM with type hints.

Models correspond to v0.5.0 schema:
- UserStats: User activity tracking
- UserAction: Audit log for PM commands, moderation
- ChannelStats: Channel-wide statistics
- UserCountHistory: Historical user count tracking
- RecentChat: Recent chat message cache (rolling window)
- CurrentStatus: Current bot status (singleton pattern)
- OutboundMessage: Queued outbound messages
- ApiToken: API authentication tokens

Usage:
    from common.models import Base, UserStats, UserAction

    # Create engine
    engine = create_async_engine('sqlite+aiosqlite:///bot_data.db')

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Query
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(UserStats).where(UserStats.username == 'Alice')
        )
        user = result.scalar_one_or_none()

Migration History:
    v0.5.0: Raw SQL schema (sqlite3)
    v0.6.0: SQLAlchemy ORM (Sprint 11 Sortie 1)
"""

from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ============================================================================
# Base Class
# ============================================================================

class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all ORM models.

    Attributes:
        AsyncAttrs: Enables async attribute loading (SQLAlchemy 2.0)
        DeclarativeBase: Base for declarative model definitions

    Usage:
        class MyModel(Base):
            __tablename__ = 'my_table'
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """
    pass


# ============================================================================
# User Statistics
# ============================================================================

class UserStats(Base):
    """
    Tracks user activity and connection time.

    Primary use: Bot statistics, user profiles, activity tracking

    Schema matches v0.5.0 user_stats table exactly.
    """
    __tablename__ = 'user_stats'

    # Primary key
    username: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="CyTube username (case-sensitive)"
    )

    # Timestamps (Unix epoch seconds)
    first_seen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="First time user joined channel (Unix timestamp)"
    )

    last_seen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # Frequently queried for "recent users"
        comment="Last time user was seen (Unix timestamp)"
    )

    # Activity counters
    total_chat_lines: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Total chat messages sent"
    )

    total_time_connected: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Total seconds connected to channel"
    )

    # Session tracking
    current_session_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current session start time (None if offline)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_last_seen', 'last_seen'),
        CheckConstraint('total_chat_lines >= 0', name='check_positive_lines'),
        CheckConstraint('total_time_connected >= 0', name='check_positive_time'),
        {'comment': 'User activity tracking and statistics'}
    )

    def __repr__(self) -> str:
        return (
            f"<UserStats(username='{self.username}', "
            f"last_seen={self.last_seen}, "
            f"total_chat_lines={self.total_chat_lines})>"
        )


# ============================================================================
# User Actions (Audit Log)
# ============================================================================

class UserAction(Base):
    """
    Audit log for user actions (PM commands, moderation, etc.).

    Primary use: Security auditing, PM command logging, compliance

    Schema matches v0.5.0 user_actions table exactly.
    """
    __tablename__ = 'user_actions'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique action ID"
    )

    # Action metadata
    timestamp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # Frequently queried for recent actions
        comment="Action timestamp (Unix epoch)"
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # Frequently queried for user audit
        comment="Username performing action"
    )

    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action type (e.g., 'pm_command', 'kick', 'ban')"
    )

    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Action details (JSON or plain text)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_user_actions_timestamp', 'timestamp'),
        Index('idx_user_actions_username', 'username'),
        Index('idx_user_actions_username_timestamp', 'username', 'timestamp'),  # Compound index
        {'comment': 'Audit log for user actions and PM commands'}
    )

    def __repr__(self) -> str:
        return (
            f"<UserAction(id={self.id}, "
            f"username='{self.username}', "
            f"action_type='{self.action_type}')>"
        )


# ============================================================================
# Channel Statistics
# ============================================================================

class ChannelStats(Base):
    """
    Channel-wide statistics (high water mark, etc.).

    Primary use: Channel metrics, bot dashboard

    Note: Singleton table (id always = 1)
    Schema matches v0.5.0 channel_stats table exactly.
    """
    __tablename__ = 'channel_stats'

    # Primary key (singleton)
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
        comment="Always 1 (singleton table)"
    )

    # Statistics
    max_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="High water mark - maximum concurrent chat users"
    )

    max_users_timestamp: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Timestamp when max_users was reached"
    )

    max_connected: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="High water mark - maximum concurrent connected users (including guests)"
    )

    max_connected_timestamp: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Timestamp when max_connected was reached"
    )

    last_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last update timestamp (Unix epoch)"
    )

    # Table-level constraints
    __table_args__ = (
        CheckConstraint('id = 1', name='check_singleton'),
        CheckConstraint('max_users >= 0', name='check_positive_users'),
        {'comment': 'Channel-wide statistics (singleton table)'}
    )

    def __repr__(self) -> str:
        return f"<ChannelStats(max_users={self.max_users}, max_connected={self.max_connected})>"


# ============================================================================
# User Count History
# ============================================================================

class UserCountHistory(Base):
    """
    Historical user count tracking for graphing and analysis.

    Primary use: Charts, analytics, trend analysis

    Schema matches v0.5.0 user_count_history table exactly.
    """
    __tablename__ = 'user_count_history'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique history entry ID"
    )

    # Timestamp
    timestamp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # Frequently queried for time ranges
        comment="Sample timestamp (Unix epoch)"
    )

    # User counts
    chat_users: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of chat-enabled users"
    )

    connected_users: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total connected users (including guests)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_user_count_timestamp', 'timestamp'),
        CheckConstraint('chat_users >= 0', name='check_positive_chat_users'),
        CheckConstraint('connected_users >= 0', name='check_positive_connected'),
        CheckConstraint('connected_users >= chat_users', name='check_connected_ge_chat'),
        {'comment': 'Historical user count tracking for analytics'}
    )

    def __repr__(self) -> str:
        return (
            f"<UserCountHistory(timestamp={self.timestamp}, "
            f"chat={self.chat_users}, connected={self.connected_users})>"
        )


# ============================================================================
# Recent Chat Cache
# ============================================================================

class RecentChat(Base):
    """
    Recent chat message cache (rolling window).

    Primary use: Recent chat history API, message replay

    Schema matches v0.5.0 recent_chat table exactly.
    """
    __tablename__ = 'recent_chat'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique message ID"
    )

    # Message metadata
    timestamp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # Frequently queried for recent messages
        comment="Message timestamp (Unix epoch)"
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Username who sent message"
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Chat message content"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_recent_chat_timestamp', 'timestamp'),
        {'comment': 'Recent chat message cache (rolling window)'}
    )

    def __repr__(self) -> str:
        msg_preview = self.message[:30] + '...' if len(self.message) > 30 else self.message
        return (
            f"<RecentChat(username='{self.username}', "
            f"message='{msg_preview}')>"
        )


# ============================================================================
# Current Status (Bot Status)
# ============================================================================

class CurrentStatus(Base):
    """
    Current bot status (online/offline, current users, etc.).

    Primary use: Bot dashboard, status API, health checks

    Note: Singleton table (id always = 1)
    Schema supports full bot status tracking including media and playlist info.
    """
    __tablename__ = 'current_status'

    # Primary key (singleton)
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
        comment="Always 1 (singleton table)"
    )

    # Core status
    last_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last status update timestamp (Unix epoch)"
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default='offline',
        server_default='offline',
        comment="Bot status (online/offline/connecting)"
    )

    # Bot identity
    bot_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Bot username in channel"
    )

    bot_rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Bot rank level in channel"
    )

    bot_afk: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether bot is marked AFK"
    )

    # Channel info
    channel_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Channel name/room"
    )

    # User counts
    current_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Current chat-enabled users (deprecated, use current_chat_users)"
    )

    connected_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Current total connected users (deprecated, use current_connected_users)"
    )

    current_chat_users: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current chat-enabled users"
    )

    current_connected_users: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current total connected users (including guests)"
    )

    # Playlist/Media info
    playlist_items: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of items in playlist"
    )

    current_media_title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Currently playing media title"
    )

    current_media_duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current media duration in seconds"
    )

    # Uptime tracking
    bot_start_time: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Bot start timestamp (for uptime calculation)"
    )

    bot_connected: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether bot is connected to channel"
    )

    # Table-level constraints
    __table_args__ = (
        CheckConstraint('id = 1', name='check_singleton'),
        CheckConstraint('current_users >= 0', name='check_positive_current'),
        CheckConstraint('connected_users >= 0', name='check_positive_connected'),
        {'comment': 'Current bot status (singleton table)'}
    )

    def __repr__(self) -> str:
        return (
            f"<CurrentStatus(status='{self.status}', "
            f"bot_name='{self.bot_name}', "
            f"current_chat_users={self.current_chat_users})>"
        )


# ============================================================================
# Outbound Messages Queue
# ============================================================================

class OutboundMessage(Base):
    """
    Queued outbound messages (for send rate limiting).

    Primary use: Message queue, rate limiting, retry logic

    Schema matches v0.5.0 outbound_messages table with sent_timestamp tracking.
    """
    __tablename__ = 'outbound_messages'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique message queue ID"
    )

    # Message metadata
    timestamp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # Frequently queried for queue processing
        comment="Message queued timestamp (Unix epoch)"
    )

    sent_timestamp: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Timestamp when message was sent (None if not sent yet)"
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message content to send"
    )

    # Queue state
    sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default='0',
        index=True,  # Frequently queried for unsent messages
        comment="Whether message has been sent"
    )

    # Retry tracking (added in v0.5.0)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Number of send attempts"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if send failed"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_outbound_timestamp', 'timestamp'),
        Index('idx_outbound_sent', 'sent'),
        Index('idx_outbound_sent_timestamp', 'sent', 'timestamp'),  # Compound index
        CheckConstraint('retry_count >= 0', name='check_positive_retries'),
        {'comment': 'Outbound message queue for rate limiting'}
    )

    def __repr__(self) -> str:
        msg_preview = self.message[:30] + '...' if len(self.message) > 30 else self.message
        return (
            f"<OutboundMessage(id={self.id}, sent={self.sent}, "
            f"message='{msg_preview}')>"
        )


# ============================================================================
# API Tokens
# ============================================================================

class ApiToken(Base):
    """
    API authentication tokens for web API access.

    Primary use: API authentication, permission management

    Schema supports token description/name and permissions tracking.
    """
    __tablename__ = 'api_tokens'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique token ID"
    )

    # Token
    token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # Frequently queried for auth
        comment="API authentication token (UUID or similar)"
    )

    # Token metadata
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Human-readable token name (deprecated, use description)"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of what this token is for"
    )

    permissions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string of permissions (optional)"
    )

    # Timestamps
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Token creation timestamp (Unix epoch)"
    )

    last_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Last usage timestamp (None if never used)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default='1',
        index=True,  # Frequently queried for active tokens
        comment="Whether token is active (can be disabled)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        Index('idx_token', 'token'),
        Index('idx_is_active', 'is_active'),
        Index('idx_active_tokens', 'is_active', 'token'),  # Compound index
        {'comment': 'API authentication tokens'}
    )

    def __repr__(self) -> str:
        token_preview = self.token[:8] + '...' if len(self.token) > 8 else self.token
        desc = self.description or self.name or 'no description'
        return (
            f"<ApiToken(description='{desc}', "
            f"token='{token_preview}', active={self.is_active})>"
        )


# ============================================================================
# Plugin KV Storage (Sprint 12)
# ============================================================================

class PluginKVStorage(Base):
    """
    Key-value storage for plugins with TTL support.

    Each plugin gets an isolated namespace identified by plugin_name.
    Values are stored as JSON and can optionally expire after a TTL.

    Sprint: 12 (KV Storage Foundation)
    Sortie: 1 (Schema & Model)
    """
    __tablename__ = 'plugin_kv_storage'

    # Composite primary key
    plugin_name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        nullable=False,
        comment="Plugin identifier (e.g., 'trivia', 'quote-db')"
    )

    key: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
        comment="Key name within plugin namespace"
    )

    # Value storage (JSON serialized)
    value_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-serialized value (string, number, object, array)"
    )

    # TTL support
    expires_at: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Expiration timestamp (Unix epoch, NULL = never expires)"
    )

    # Timestamps
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="When key was first created (Unix epoch)"
    )

    updated_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="When key was last updated (Unix epoch)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        # Index for TTL cleanup queries
        Index('idx_plugin_kv_expires', 'expires_at'),
        # Index for prefix queries
        Index('idx_plugin_kv_prefix', 'plugin_name', 'key'),
        {'comment': 'Plugin key-value storage with TTL support'}
    )

    def __repr__(self) -> str:
        expired = " [EXPIRED]" if self.is_expired else ""
        return f"<PluginKVStorage(plugin={self.plugin_name}, key={self.key}{expired})>"

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        import time
        return time.time() >= self.expires_at

    def get_value(self):
        """
        Deserialize and return the stored value.

        Returns:
            Deserialized Python object (dict, list, str, int, etc.)

        Raises:
            json.JSONDecodeError: If value_json is invalid JSON
        """
        import json
        return json.loads(self.value_json)

    def set_value(self, value) -> None:
        """
        Serialize and store a Python value as JSON.

        Args:
            value: Any JSON-serializable Python object

        Raises:
            TypeError: If value is not JSON-serializable
            ValueError: If serialized value exceeds 64KB
        """
        import json
        serialized = json.dumps(value)

        # Check size limit (64KB)
        size_bytes = len(serialized.encode('utf-8'))
        if size_bytes > 65536:
            raise ValueError(
                f"Value size ({size_bytes} bytes) exceeds 64KB limit (65536 bytes)"
            )

        self.value_json = serialized


# ============================================================================
# Plugin Table Schemas (Sprint 13)
# ============================================================================

class PluginTableSchema(Base):
    """
    Stores table schemas for plugin row-based storage.

    Each plugin can register multiple tables. The schema_json field
    defines the columns (name, type, required) for each table.

    Sprint: 13 (Row Operations Foundation)
    Sortie: 1 (Schema Registry & Table Creation)
    """
    __tablename__ = 'plugin_table_schemas'

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique schema ID"
    )

    # Plugin and table identification
    plugin_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Plugin identifier (e.g., 'quote-db', 'trivia')"
    )

    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Table name within plugin namespace"
    )

    # Schema definition (JSON)
    schema_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON schema: {'fields': [{'name': 'text', 'type': 'text', 'required': true}]}"
    )

    # Version tracking
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default='1',
        comment="Schema version (for migrations)"
    )

    # Timestamps
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Schema creation timestamp (Unix epoch)"
    )

    updated_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Schema last updated timestamp (Unix epoch)"
    )

    # Table-level constraints and indexes
    __table_args__ = (
        # Unique constraint on (plugin_name, table_name)
        Index('idx_plugin_table_unique', 'plugin_name', 'table_name', unique=True),
        # Index for plugin schema lookups
        Index('idx_plugin_name', 'plugin_name'),
        {'comment': 'Plugin table schemas for row-based storage'}
    )

    def __repr__(self) -> str:
        return f"<PluginTableSchema(plugin={self.plugin_name}, table={self.table_name}, v{self.version})>"

    def get_schema(self) -> dict:
        """
        Deserialize schema_json to dict.

        Returns:
            Schema dict with 'fields' key

        Raises:
            json.JSONDecodeError: If schema_json is invalid JSON
        """
        import json
        return json.loads(self.schema_json)

    def set_schema(self, schema: dict) -> None:
        """
        Serialize and store schema as JSON.

        Args:
            schema: Schema dict with 'fields' key

        Raises:
            TypeError: If schema is not JSON-serializable
        """
        import json
        self.schema_json = json.dumps(schema)


# ============================================================================
# Utility Functions
# ============================================================================

def get_model_by_tablename(tablename: str) -> Optional[type[Base]]:
    """
    Get ORM model class by table name.

    Args:
        tablename: Database table name (e.g., 'user_stats')

    Returns:
        Model class (e.g., UserStats) or None if not found

    Example:
        >>> model_class = get_model_by_tablename('user_stats')
        >>> print(model_class.__name__)
        UserStats
    """
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, '__tablename__') and cls.__tablename__ == tablename:
            return cls
    return None


def get_all_models() -> list[type[Base]]:
    """
    Get all ORM model classes.

    Returns:
        List of model classes

    Example:
        >>> models = get_all_models()
        >>> for model in models:
        ...     print(model.__tablename__)
        user_stats
        user_actions
        ...
    """
    return [mapper.class_ for mapper in Base.registry.mappers]


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    'Base',
    'UserStats',
    'UserAction',
    'ChannelStats',
    'UserCountHistory',
    'RecentChat',
    'CurrentStatus',
    'OutboundMessage',
    'ApiToken',
    'PluginKVStorage',
    'PluginTableSchema',
    'get_model_by_tablename',
    'get_all_models',
]
