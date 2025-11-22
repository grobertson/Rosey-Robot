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
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Index,
    CheckConstraint
)
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
        comment="High water mark - maximum concurrent users"
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
        return f"<ChannelStats(max_users={self.max_users})>"


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
    Schema matches v0.5.0 current_status table exactly.
    """
    __tablename__ = 'current_status'
    
    # Primary key (singleton)
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
        comment="Always 1 (singleton table)"
    )
    
    # Status fields
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
    
    current_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Current chat-enabled users"
    )
    
    connected_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default='0',
        comment="Current total connected users"
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
            f"current_users={self.current_users})>"
        )


# ============================================================================
# Outbound Messages Queue
# ============================================================================

class OutboundMessage(Base):
    """
    Queued outbound messages (for send rate limiting).
    
    Primary use: Message queue, rate limiting, retry logic
    
    Schema matches v0.5.0 outbound_messages table exactly.
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
    
    Schema matches v0.5.0 api_tokens table exactly.
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
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable token name"
    )
    
    permissions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON string of permissions"
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
        return (
            f"<ApiToken(name='{self.name}', "
            f"token='{token_preview}', active={self.is_active})>"
        )


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
    'get_model_by_tablename',
    'get_all_models',
]
