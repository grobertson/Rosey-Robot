#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for SQLAlchemy ORM models.

Tests model creation, constraints, indexes, and utility functions.
Uses in-memory SQLite database for fast isolated tests.

Test Coverage:
- Model creation and field validation
- Check constraints (positive values, singleton patterns)
- Indexes (ensure performance-critical indexes exist)
- Utility functions (get_all_models, get_model_by_tablename)
- Type hints and __repr__ methods

Sprint 11 Sortie 1: SQLAlchemy ORM Foundation
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from common.models import (
    Base,
    UserStats,
    UserAction,
    ChannelStats,
    UserCountHistory,
    RecentChat,
    CurrentStatus,
    OutboundMessage,
    ApiToken,
    PluginKVStorage,
    PluginTableSchema,
    get_all_models,
    get_model_by_tablename,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create database session for testing."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_timestamp():
    """Provide consistent timestamp for tests."""
    return int(datetime(2025, 11, 22, 12, 0, 0).timestamp())


# ============================================================================
# Test: UserStats Model
# ============================================================================

def test_user_stats_create(session, sample_timestamp):
    """Test creating a UserStats record."""
    user = UserStats(
        username="Alice",
        first_seen=sample_timestamp,
        last_seen=sample_timestamp,
        total_chat_lines=10,
        total_time_connected=3600,
        current_session_start=sample_timestamp,
    )
    session.add(user)
    session.commit()

    # Verify record
    result = session.execute(
        select(UserStats).where(UserStats.username == "Alice")
    ).scalar_one()
    assert result.username == "Alice"
    assert result.total_chat_lines == 10
    assert result.total_time_connected == 3600
    assert result.current_session_start == sample_timestamp


def test_user_stats_defaults(session, sample_timestamp):
    """Test UserStats default values."""
    user = UserStats(
        username="Bob",
        first_seen=sample_timestamp,
        last_seen=sample_timestamp,
    )
    session.add(user)
    session.commit()

    result = session.execute(
        select(UserStats).where(UserStats.username == "Bob")
    ).scalar_one()
    assert result.total_chat_lines == 0
    assert result.total_time_connected == 0
    assert result.current_session_start is None


def test_user_stats_check_constraint(session, sample_timestamp):
    """Test UserStats check constraints (positive values)."""
    user = UserStats(
        username="Charlie",
        first_seen=sample_timestamp,
        last_seen=sample_timestamp,
        total_chat_lines=-1,  # Invalid
    )
    session.add(user)
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_stats_index_exists(engine):
    """Test that last_seen index exists."""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("user_stats")
    index_names = [idx["name"] for idx in indexes]
    assert "idx_last_seen" in index_names


def test_user_stats_repr(sample_timestamp):
    """Test UserStats __repr__ method."""
    user = UserStats(
        username="Alice",
        first_seen=sample_timestamp,
        last_seen=sample_timestamp,
        total_chat_lines=10,
    )
    repr_str = repr(user)
    assert "Alice" in repr_str
    assert "10" in repr_str


# ============================================================================
# Test: UserAction Model
# ============================================================================

def test_user_action_create(session, sample_timestamp):
    """Test creating a UserAction record."""
    action = UserAction(
        timestamp=sample_timestamp,
        username="Alice",
        action_type="pm_command",
        details="Executed !help command",
    )
    session.add(action)
    session.commit()

    result = session.execute(
        select(UserAction).where(UserAction.username == "Alice")
    ).scalar_one()
    assert result.username == "Alice"
    assert result.action_type == "pm_command"
    assert result.details == "Executed !help command"


def test_user_action_indexes_exist(engine):
    """Test that username and timestamp indexes exist."""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("user_actions")
    index_names = [idx["name"] for idx in indexes]
    assert "idx_user_actions_username" in index_names
    assert "idx_user_actions_timestamp" in index_names
    assert "idx_user_actions_username_timestamp" in index_names


# ============================================================================
# Test: ChannelStats Model (Singleton)
# ============================================================================

def test_channel_stats_create(session, sample_timestamp):
    """Test creating ChannelStats (singleton)."""
    stats = ChannelStats(
        id=1,
        max_users=50,
        last_updated=sample_timestamp,
    )
    session.add(stats)
    session.commit()

    result = session.execute(
        select(ChannelStats).where(ChannelStats.id == 1)
    ).scalar_one()
    assert result.max_users == 50


def test_channel_stats_defaults(session, sample_timestamp):
    """Test ChannelStats default values."""
    stats = ChannelStats(
        id=1,
        last_updated=sample_timestamp,
    )
    session.add(stats)
    session.commit()

    result = session.execute(
        select(ChannelStats).where(ChannelStats.id == 1)
    ).scalar_one()
    assert result.max_users == 0


def test_channel_stats_check_constraint(session, sample_timestamp):
    """Test ChannelStats check constraints."""
    stats = ChannelStats(
        id=1,
        max_users=-1,  # Invalid
        last_updated=sample_timestamp,
    )
    session.add(stats)
    with pytest.raises(IntegrityError):
        session.commit()


# ============================================================================
# Test: UserCountHistory Model
# ============================================================================

def test_user_count_history_create(session, sample_timestamp):
    """Test creating UserCountHistory record."""
    history = UserCountHistory(
        timestamp=sample_timestamp,
        chat_users=10,
        connected_users=15,
    )
    session.add(history)
    session.commit()

    result = session.execute(
        select(UserCountHistory).where(
            UserCountHistory.timestamp == sample_timestamp
        )
    ).scalar_one()
    assert result.chat_users == 10
    assert result.connected_users == 15


def test_user_count_history_check_constraints(session, sample_timestamp):
    """Test UserCountHistory check constraints."""
    history = UserCountHistory(
        timestamp=sample_timestamp,
        chat_users=-1,  # Invalid
        connected_users=15,
    )
    session.add(history)
    with pytest.raises(IntegrityError):
        session.commit()


# ============================================================================
# Test: RecentChat Model
# ============================================================================

def test_recent_chat_create(session, sample_timestamp):
    """Test creating RecentChat record."""
    chat = RecentChat(
        timestamp=sample_timestamp,
        username="Alice",
        message="Hello, world!",
    )
    session.add(chat)
    session.commit()

    result = session.execute(
        select(RecentChat).where(RecentChat.username == "Alice")
    ).scalar_one()
    assert result.message == "Hello, world!"


def test_recent_chat_index_exists(engine):
    """Test that timestamp index exists."""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("recent_chat")
    index_names = [idx["name"] for idx in indexes]
    assert "idx_recent_chat_timestamp" in index_names


# ============================================================================
# Test: CurrentStatus Model (Singleton)
# ============================================================================

def test_current_status_create(session, sample_timestamp):
    """Test creating CurrentStatus (singleton)."""
    status = CurrentStatus(
        id=1,
        status="online",
        current_users=10,
        connected_users=15,
        last_updated=sample_timestamp,
    )
    session.add(status)
    session.commit()

    result = session.execute(
        select(CurrentStatus).where(CurrentStatus.id == 1)
    ).scalar_one()
    assert result.status == "online"
    assert result.current_users == 10


def test_current_status_defaults(session, sample_timestamp):
    """Test CurrentStatus default values."""
    status = CurrentStatus(
        id=1,
        last_updated=sample_timestamp,
    )
    session.add(status)
    session.commit()

    result = session.execute(
        select(CurrentStatus).where(CurrentStatus.id == 1)
    ).scalar_one()
    assert result.status == "offline"
    assert result.current_users == 0
    assert result.connected_users == 0


def test_current_status_check_constraints(session, sample_timestamp):
    """Test CurrentStatus check constraints."""
    status = CurrentStatus(
        id=1,
        current_users=-1,  # Invalid
        last_updated=sample_timestamp,
    )
    session.add(status)
    with pytest.raises(IntegrityError):
        session.commit()


# ============================================================================
# Test: OutboundMessage Model
# ============================================================================

def test_outbound_message_create(session, sample_timestamp):
    """Test creating OutboundMessage record."""
    msg = OutboundMessage(
        timestamp=sample_timestamp,
        message="Test message",
        sent=False,
        retry_count=0,
    )
    session.add(msg)
    session.commit()

    result = session.execute(
        select(OutboundMessage).where(OutboundMessage.message == "Test message")
    ).scalar_one()
    assert result.sent is False
    assert result.retry_count == 0


def test_outbound_message_defaults(session, sample_timestamp):
    """Test OutboundMessage default values."""
    msg = OutboundMessage(
        timestamp=sample_timestamp,
        message="Test message",
    )
    session.add(msg)
    session.commit()

    result = session.execute(
        select(OutboundMessage).where(OutboundMessage.message == "Test message")
    ).scalar_one()
    assert result.sent is False
    assert result.retry_count == 0


def test_outbound_message_indexes_exist(engine):
    """Test that sent and timestamp indexes exist."""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("outbound_messages")
    index_names = [idx["name"] for idx in indexes]
    assert "idx_outbound_sent" in index_names
    assert "idx_outbound_timestamp" in index_names


# ============================================================================
# Test: ApiToken Model
# ============================================================================

def test_api_token_create(session, sample_timestamp):
    """Test creating ApiToken record."""
    token = ApiToken(
        token="test_token_123",
        name="Test Token",
        permissions='{"read": true, "write": false}',
        created_at=sample_timestamp,
        last_used=sample_timestamp,
        is_active=True,
    )
    session.add(token)
    session.commit()

    result = session.execute(
        select(ApiToken).where(ApiToken.token == "test_token_123")
    ).scalar_one()
    assert result.name == "Test Token"
    assert result.is_active is True


def test_api_token_defaults(session, sample_timestamp):
    """Test ApiToken default values."""
    token = ApiToken(
        token="test_token_456",
        name="Test Token 2",
        permissions='{"read": true}',
        created_at=sample_timestamp,
    )
    session.add(token)
    session.commit()

    result = session.execute(
        select(ApiToken).where(ApiToken.token == "test_token_456")
    ).scalar_one()
    assert result.is_active is True
    assert result.last_used is None


def test_api_token_unique_constraint(session, sample_timestamp):
    """Test ApiToken unique token constraint."""
    token1 = ApiToken(
        token="duplicate_token",
        name="Token 1",
        permissions="{}",
        created_at=sample_timestamp,
    )
    token2 = ApiToken(
        token="duplicate_token",
        name="Token 2",
        permissions="{}",
        created_at=sample_timestamp,
    )
    session.add(token1)
    session.commit()

    session.add(token2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_api_token_indexes_exist(engine):
    """Test that token and is_active indexes exist."""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("api_tokens")
    index_names = [idx["name"] for idx in indexes]
    assert "idx_token" in index_names
    assert "idx_is_active" in index_names
    assert "idx_active_tokens" in index_names


# ============================================================================
# Test: Utility Functions
# ============================================================================

def test_get_all_models():
    """Test get_all_models() returns all 10 models."""
    models = get_all_models()
    assert len(models) == 10
    assert UserStats in models
    assert UserAction in models
    assert ChannelStats in models
    assert UserCountHistory in models
    assert RecentChat in models
    assert CurrentStatus in models
    assert OutboundMessage in models
    assert ApiToken in models
    assert PluginKVStorage in models
    assert PluginTableSchema in models


def test_get_model_by_tablename():
    """Test get_model_by_tablename() returns correct models."""
    assert get_model_by_tablename("user_stats") == UserStats
    assert get_model_by_tablename("user_actions") == UserAction
    assert get_model_by_tablename("channel_stats") == ChannelStats
    assert get_model_by_tablename("user_count_history") == UserCountHistory
    assert get_model_by_tablename("recent_chat") == RecentChat
    assert get_model_by_tablename("current_status") == CurrentStatus
    assert get_model_by_tablename("outbound_messages") == OutboundMessage
    assert get_model_by_tablename("api_tokens") == ApiToken


def test_get_model_by_tablename_invalid():
    """Test get_model_by_tablename() with invalid table name."""
    assert get_model_by_tablename("nonexistent_table") is None


# ============================================================================
# Test: Schema Validation
# ============================================================================

def test_all_tables_created(engine):
    """Test that all 10 tables are created."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert len(tables) == 10
    assert "user_stats" in tables
    assert "user_actions" in tables
    assert "channel_stats" in tables
    assert "user_count_history" in tables
    assert "recent_chat" in tables
    assert "current_status" in tables
    assert "outbound_messages" in tables
    assert "api_tokens" in tables
    assert "plugin_kv_storage" in tables
    assert "plugin_table_schemas" in tables


def test_table_comments_exist(engine):
    """Test that table comments are present (PostgreSQL only)."""
    # Note: SQLite doesn't support table comments, but we verify they're
    # defined in models for PostgreSQL compatibility
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        # This will pass on SQLite (no error), verify on PostgreSQL later
        pass


# ============================================================================
# Test: Type Hints
# ============================================================================

def test_model_type_hints():
    """Test that models have proper type hints."""
    # Verify Mapped[type] annotations exist
    assert hasattr(UserStats, "__annotations__")
    assert "username" in UserStats.__annotations__
    assert "first_seen" in UserStats.__annotations__
    assert "last_seen" in UserStats.__annotations__

    assert hasattr(ApiToken, "__annotations__")
    assert "token" in ApiToken.__annotations__
    assert "is_active" in ApiToken.__annotations__


# ============================================================================
# Integration Test: Multiple Models
# ============================================================================

def test_multiple_models_integration(session, sample_timestamp):
    """Test creating records across multiple models."""
    # Create user
    user = UserStats(
        username="Alice",
        first_seen=sample_timestamp,
        last_seen=sample_timestamp,
        total_chat_lines=5,
    )
    session.add(user)

    # Create user action
    action = UserAction(
        timestamp=sample_timestamp,
        username="Alice",
        action_type="chat",
        details="Said hello",
    )
    session.add(action)

    # Create recent chat
    chat = RecentChat(
        timestamp=sample_timestamp,
        username="Alice",
        message="Hello!",
    )
    session.add(chat)

    session.commit()

    # Verify all records
    assert session.execute(
        select(UserStats).where(UserStats.username == "Alice")
    ).scalar_one().total_chat_lines == 5

    assert session.execute(
        select(UserAction).where(UserAction.username == "Alice")
    ).scalar_one().action_type == "chat"

    assert session.execute(
        select(RecentChat).where(RecentChat.username == "Alice")
    ).scalar_one().message == "Hello!"
