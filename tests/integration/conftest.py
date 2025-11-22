"""
Shared fixtures for integration tests.

Integration tests validate multi-component workflows with minimal mocking.
Uses real Bot, Database, and Shell instances to test realistic interactions.
"""

import pytest
import time
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from common.database import BotDatabase
from common.shell import Shell
from lib.bot import Bot


@pytest.fixture
async def temp_database():
    """Create temporary database for testing.
    
    Provides a fully-initialized async BotDatabase instance with:
    - Temporary file path (auto-cleaned up)
    - All tables created via migrations
    - Clean state for each test
    - Automatic connection lifecycle management
    
    Example:
        async def test_database_operations(temp_database):
            await temp_database.user_joined('Alice')
            stats = await temp_database.get_user_stats('Alice')
            assert stats is not None
    
    Yields:
        BotDatabase: Connected async database instance
    """
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Initialize and connect database
    db = BotDatabase(db_path)
    await db.connect()
    
    # Provide to test
    yield db
    
    # Cleanup
    try:
        await db.close()
    except Exception as e:
        logging.warning('Error closing test database: %s', e)
    
    finally:
        # Remove temp file
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception as e:
            logging.warning('Error removing test database file: %s', e)


@pytest.fixture
async def integration_db(tmp_path):
    """Real database for integration testing."""
    db_path = str(tmp_path / "integration_test.db")
    db = BotDatabase(db_path)
    await db.connect()
    yield db
    # Close async connection
    try:
        if db.is_connected:
            await db.close()
    except Exception as e:
        logging.warning('Error closing integration_db: %s', e)


@pytest.fixture
async def integration_bot(integration_db):
    """Bot instance with real database but mocked connection."""
    from lib.connection import ConnectionAdapter
    
    # Create mock connection adapter
    mock_conn = AsyncMock(spec=ConnectionAdapter)
    mock_conn.is_connected = True
    mock_conn.connect = AsyncMock()
    mock_conn.disconnect = AsyncMock()
    mock_conn.send_message = AsyncMock()
    mock_conn.send_pm = AsyncMock()
    mock_conn.on_event = MagicMock()
    
    # Mock event iterator
    async def mock_recv_events():
        if False:
            yield
    mock_conn.recv_events = mock_recv_events
    
    # Create mock NATS client (required in Sprint 9+)
    mock_nats = AsyncMock()
    mock_nats.publish = AsyncMock()
    mock_nats.request = AsyncMock()
    mock_nats.subscribe = AsyncMock()
    mock_nats.is_connected = True
    
    bot = Bot(
        connection=mock_conn,
        nats_client=mock_nats,
        restart_delay=5
    )
    
    # Connect bot to integration database for backward compatibility
    # (Bot will use NATS for new operations, but old tests may check db)
    bot.db = integration_db
    
    # Set up channel and user info for backward compatibility
    bot.channel.name = "test_integration"
    bot.user.name = "IntegrationTestBot"
    bot.user.rank = 3.0
    bot.user.afk = False
    
    # Set up start time for uptime calculations
    bot.start_time = time.time()
    bot.connect_time = time.time()
    
    # Create userlist mock with proper attributes
    bot.channel.userlist = MagicMock()
    bot.channel.userlist._users = {}
    bot.channel.userlist.count = 0
    bot.channel.userlist.leader = None
    bot.channel.userlist.__contains__ = lambda self, name: name in self._users
    bot.channel.userlist.__getitem__ = lambda self, name: self._users[name]
    bot.channel.userlist.__setitem__ = lambda self, name, user: self._users.__setitem__(name, user)
    bot.channel.userlist.__len__ = lambda self: len(self._users)
    
    bot.channel.playlist = MagicMock()
    bot.channel.playlist.queue = []
    bot.channel.playlist.current = None
    bot.channel.playlist.__len__ = lambda self: len(self.queue)
    
    # Mock usercount tracking
    bot.channel.usercount = MagicMock()
    bot.channel.usercount.chatcount = 0
    bot.channel.usercount.usercount = 0
    
    yield bot
    
    # Cleanup
    if bot.db:
        bot.db = None


@pytest.fixture
def integration_shell(integration_bot):
    """Shell instance connected to integration bot."""
    # Enable PM command interface
    shell = Shell("enabled", integration_bot)
    yield shell
    # No explicit close needed for PM-only shell


@pytest.fixture
def moderator_user():
    """Mock moderator user (rank >= 2.0)."""
    user = MagicMock()
    user.name = "ModUser"
    user.rank = 2.5
    user.afk = False
    user.muted = False
    return user


@pytest.fixture
def regular_user():
    """Mock regular user (rank < 2.0)."""
    user = MagicMock()
    user.name = "RegularUser"
    user.rank = 1.0
    user.afk = False
    user.muted = False
    return user


@pytest.fixture
def admin_user():
    """Mock admin user (rank = 5.0)."""
    user = MagicMock()
    user.name = "AdminUser"
    user.rank = 5.0
    user.afk = False
    user.muted = False
    return user
