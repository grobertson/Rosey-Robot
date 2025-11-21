"""
Shared pytest fixtures for Rosey test suite.

This file contains fixtures that are available to all test files.
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from lib.connection import ConnectionAdapter


@pytest.fixture
def event_loop():
    """
    Create event loop for async tests.
    
    This fixture ensures each test gets a fresh event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
    Mock Bot instance with common attributes.
    
    Returns:
        Mock: Bot with mocked channel, database, and methods
    """
    bot = Mock()
    bot.connected = True
    bot.channel = Mock()
    bot.channel.name = 'test_channel'
    bot.channel.users = []
    bot.channel.playlist = []
    bot.channel.send_chat = AsyncMock()
    bot.channel.send_pm = AsyncMock()
    bot.db = None  # Tests can set this if needed
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
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "asyncio: Async tests")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")
