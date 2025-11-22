"""
Shared pytest fixtures for Rosey test suite.

This file contains fixtures that are available to all test files.
"""
import os
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock
from lib.connection import ConnectionAdapter
from nats.aio.client import Client as NATS
from common.database import BotDatabase


@pytest.fixture
def event_loop():
    """
    Create event loop for async tests.
    
    This fixture ensures each test gets a fresh event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures (Sprint 11 - SQLAlchemy ORM + PostgreSQL)
# ============================================================================

@pytest.fixture(scope='session')
def database_url():
    """
    Get database URL from environment or use in-memory SQLite.
    
    Usage in CI:
        DATABASE_URL=postgresql+asyncpg://... pytest tests/
    
    Usage locally:
        pytest tests/  # Uses SQLite in-memory
    
    Returns:
        str: Database URL (SQLite in-memory or PostgreSQL from env)
    """
    return os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')


@pytest.fixture
def temp_db_path(tmp_path):
    """
    Provide temporary database path for testing.
    
    Returns:
        str: Path to temporary test database file
    """
    return str(tmp_path / "test_bot.db")


@pytest.fixture
async def db(temp_db_path, database_url):
    """
    Create fresh async database instance for testing.
    
    Automatically uses DATABASE_URL from environment if set (for PostgreSQL CI testing),
    otherwise uses temp_db_path (for local SQLite testing).
    
    Creates tables via SQLAlchemy ORM (not Alembic, for test speed).
    Tables must be created BEFORE connect() since connect() queries the database.
    
    Args:
        temp_db_path: Temporary database path from fixture
        database_url: Database URL from environment or in-memory
    
    Yields:
        BotDatabase: Connected database instance with tables created
    
    Cleanup:
        Closes database connection after test
    """
    from common.models import Base
    
    # Use environment DATABASE_URL if PostgreSQL, else temp file
    if database_url.startswith('postgresql'):
        db_url = database_url
    else:
        db_url = temp_db_path
    
    database = BotDatabase(db_url)
    
    # Create all tables from ORM models (fast for tests)
    # MUST be done before connect() since connect() queries the DB
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Now connect (verifies connection by querying user count)
    await database.connect()
    
    yield database
    await database.close()
    
    # Cleanup PostgreSQL tables after test (reset for next test)
    if database_url.startswith('postgresql'):
        try:
            from sqlalchemy import text
            async with database.engine.begin() as conn:
                # Drop all tables in public schema
                await conn.execute(text('DROP SCHEMA public CASCADE'))
                await conn.execute(text('CREATE SCHEMA public'))
                await conn.execute(text('GRANT ALL ON SCHEMA public TO rosey'))
                await conn.execute(text('GRANT ALL ON SCHEMA public TO public'))
        except Exception:
            # Cleanup errors are non-fatal (e.g., schema already dropped)
            pass


@pytest.fixture
async def db_with_users(db):
    """
    Database with sample users pre-populated.
    
    Creates three test users: alice, bob, charlie
    
    Args:
        db: Database fixture
    
    Returns:
        BotDatabase: Database with users
    """
    await db.user_joined("alice")
    await db.user_joined("bob")
    await db.user_joined("charlie")
    return db


@pytest.fixture
async def db_with_history(db):
    """
    Database with user count history (24 hours of data).
    
    Args:
        db: Database fixture
    
    Returns:
        BotDatabase: Database with historical data
    """
    import time
    now = int(time.time())
    for i in range(24):  # 24 hours of data
        timestamp = now - (23 - i) * 3600
        await db.log_user_count(timestamp, 10 + i, 15 + i)
    return db


@pytest.fixture
async def db_with_messages(db):
    """
    Database with outbound messages in queue.
    
    Args:
        db: Database fixture
    
    Returns:
        BotDatabase: Database with queued messages
    """
    await db.enqueue_outbound_message("Hello world")
    await db.enqueue_outbound_message("Test message")
    return db


@pytest.fixture
async def db_with_tokens(db):
    """
    Database with API tokens.
    
    Args:
        db: Database fixture
    
    Returns:
        tuple: (database, token1, token2)
    """
    token1 = await db.generate_api_token("Test token 1")
    token2 = await db.generate_api_token("Test token 2")
    return db, token1, token2


@pytest.fixture
def sample_config():
    """
    Sample bot configuration for testing.
    
    Returns:
        dict: Basic bot configuration with required fields
    """
    return {
        'channel': 'test_channel',
        'username': 'TestBot',
        'password': 'test_password',
        'server': 'wss://cytu.be:9443/socket.io/',
        'database': {
            'enabled': False  # Default to disabled for unit tests
        },
        'logging': {
            'level': 'WARNING'  # Reduce noise in tests
        }
    }


@pytest.fixture
def mock_websocket():
    """
    Mock websocket connection.
    
    Returns:
        AsyncMock: Mocked websocket with common methods
    """
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws


@pytest.fixture
def mock_channel():
    """
    Mock Channel instance.
    
    Returns:
        Mock: Channel with common attributes and methods
    """
    channel = Mock()
    channel.name = 'test_channel'
    channel.users = []
    channel.playlist = []
    channel.connected = True
    channel.send_chat = AsyncMock()
    channel.send_pm = AsyncMock()
    return channel


@pytest.fixture
def mock_user():
    """
    Mock User instance.
    
    Args:
        Can be parametrized with rank, username, etc.
    
    Returns:
        Mock: User with basic attributes
    """
    user = Mock()
    user.name = 'TestUser'
    user.rank = 1.0
    user.afk = False
    user.profile = {}
    return user


@pytest.fixture
def mock_database():
    """
    Mock Database instance.
    
    Returns:
        Mock: Database with common methods mocked
    """
    db = Mock()
    db.log_user_action = AsyncMock()
    db.log_media = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value={'id': 1, 'username': 'TestUser'})
    db.update_user_rank = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_nats_client():
    """
    Mock NATS client for Sprint 9 testing.
    
    Returns:
        Mock: NATS client with publish, request, subscribe methods mocked
    """
    nats = Mock(spec=NATS)
    nats.publish = AsyncMock()
    nats.request = AsyncMock()
    nats.subscribe = AsyncMock()
    nats.is_connected = True
    nats.connected_url = Mock(return_value='nats://localhost:4222')
    
    # Mock response for request/reply pattern
    mock_response = Mock()
    mock_response.data = json.dumps({'success': True}).encode()
    nats.request.return_value = mock_response
    
    return nats


@pytest.fixture
async def nats_client():
    """
    Real NATS client for integration testing.
    
    NOTE: Requires NATS server running on localhost:4222
    Use mock_nats_client for unit tests instead.
    
    Returns:
        NATS: Connected NATS client
    """
    nats = NATS()
    try:
        await nats.connect("nats://localhost:4222", connect_timeout=2)
        yield nats
    finally:
        if nats.is_connected:
            await nats.close()


@pytest.fixture
def sample_chat_event():
    """
    Sample chat event data.
    
    Returns:
        dict: Chat event in CyTube format
    """
    return {
        'username': 'TestUser',
        'msg': 'Hello, world!',
        'time': 1699747200000,  # Nov 11, 2024 (fixed timestamp for consistency)
        'meta': {}
    }


@pytest.fixture
def sample_pm_event():
    """
    Sample PM event data.
    
    Returns:
        dict: PM event in CyTube format
    """
    return {
        'username': 'ModUser',
        'to': 'TestBot',
        'msg': 'help',
        'time': 1699747200000
    }


@pytest.fixture
def sample_media():
    """
    Sample media item.
    
    Returns:
        dict: Media item in CyTube format
    """
    return {
        'id': 'yt_dQw4w9WgXcQ',
        'title': 'Test Video',
        'duration': 212,
        'type': 'yt',
        'uid': 'test_uid_123'
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """
    Create temporary config file for testing.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        sample_config: Sample configuration fixture
    
    Returns:
        Path: Path to temporary config.json file
    """
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(sample_config, indent=2))
    return config_file


@pytest.fixture
def mock_bot():
    """
    Mock Bot instance with common attributes (Sprint 9 - NATS-first).
    
    Returns:
        Mock: Bot with mocked channel, NATS client, and methods
    """
    bot = Mock()
    bot.connected = True
    bot.channel = Mock()
    bot.channel.name = 'test_channel'
    bot.channel.users = []
    bot.channel.playlist = []
    bot.channel.send_chat = AsyncMock()
    bot.channel.send_pm = AsyncMock()
    bot.nats = Mock(spec=NATS)
    bot.nats.publish = AsyncMock()
    bot.nats.request = AsyncMock()
    bot.send_chat_message = AsyncMock()
    bot.pm = AsyncMock()
    return bot


@pytest.fixture
def mock_connection():
    """
    Mock ConnectionAdapter for testing Bot integration.
    
    Returns:
        AsyncMock: Connection adapter with all required methods mocked
    """
    conn = AsyncMock(spec=ConnectionAdapter)
    conn.is_connected = True
    conn.connect = AsyncMock()
    conn.disconnect = AsyncMock()
    conn.send_message = AsyncMock()
    conn.send_pm = AsyncMock()
    conn.on_event = Mock()
    conn.off_event = Mock()
    conn.reconnect = AsyncMock()
    
    # Mock event iterator that returns no events by default
    # Tests can override this
    async def mock_recv_events():
        if False:  # Never yield, just return empty iterator
            yield
    
    conn.recv_events = mock_recv_events
    
    return conn


# Test data files


@pytest.fixture
def sample_playlist_file(tmp_path):
    """
    Create sample playlist text file.
    
    Args:
        tmp_path: pytest's temporary directory fixture
    
    Returns:
        Path: Path to temporary playlist file
    """
    playlist_file = tmp_path / "test_playlist.txt"
    playlist_file.write_text(
        "https://youtube.com/watch?v=dQw4w9WgXcQ\n"
        "https://youtube.com/watch?v=9bZkp7q19f0\n"
        "# Comment line\n"
        "https://vimeo.com/123456789\n"
    )
    return playlist_file


# Pytest configuration helpers


def pytest_configure(config):
    """
    Pytest configuration hook.
    
    Registers custom markers.
    """
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests (requires NATS)")
    config.addinivalue_line("markers", "asyncio: Async tests")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
