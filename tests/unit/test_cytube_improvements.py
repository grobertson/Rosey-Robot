"""Tests for CyTube connection improvements."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lib.connection.cytube import CyTubeConnection, ConnectionStats
from lib.connection.errors import NotConnectedError


@pytest.fixture
def mock_get():
    """Mock HTTP GET function."""
    return AsyncMock(return_value='{"servers": [{"url": "http://localhost", "secure": true}]}')


@pytest.fixture
def connection(mock_get):
    """Create a CyTubeConnection instance for testing."""
    return CyTubeConnection(
        domain='test.domain',
        channel='testchannel',
        get_func=mock_get
    )


class TestConnectionStats:
    """Test connection statistics tracking."""

    def test_stats_initialization(self, connection):
        """Test that stats are initialized correctly."""
        assert isinstance(connection.stats, ConnectionStats)
        assert connection.stats.messages_sent == 0
        assert connection.stats.messages_received == 0
        assert connection.stats.reconnection_count == 0
        assert connection.stats.events_processed == 0
        assert connection.stats.last_error is None
        assert connection.stats.connected_since is None

    def test_stats_structure(self, connection):
        """Test that stats dataclass has correct fields."""
        stats = connection.stats
        assert hasattr(stats, 'messages_sent')
        assert hasattr(stats, 'messages_received')
        assert hasattr(stats, 'reconnection_count')
        assert hasattr(stats, 'events_processed')
        assert hasattr(stats, 'last_error')
        assert hasattr(stats, 'connected_since')
        assert hasattr(stats, 'last_health_check')


class TestStateValidation:
    """Test _ensure_connected helper."""

    def test_ensure_connected_raises_when_not_connected(self, connection):
        """Test that _ensure_connected raises NotConnectedError."""
        connection._is_connected = False
        
        with pytest.raises(NotConnectedError, match="Not connected to test.domain/testchannel"):
            connection._ensure_connected()

    def test_ensure_connected_passes_when_connected(self, connection):
        """Test that _ensure_connected passes when connected."""
        connection._is_connected = True
        connection.socket = MagicMock()
        
        # Should not raise
        connection._ensure_connected()


class TestContextManager:
    """Test async context manager support."""

    def test_context_manager_methods_exist(self, connection):
        """Test that context manager methods are defined."""
        assert hasattr(connection, '__aenter__')
        assert hasattr(connection, '__aexit__')
        assert callable(connection.__aenter__)
        assert callable(connection.__aexit__)


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_when_not_connected(self, connection):
        """Test health check returns False when not connected."""
        result = await connection.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, connection):
        """Test health check returns True when connection is healthy."""
        connection._is_connected = True
        mock_socket = MagicMock()
        mock_socket.emit = AsyncMock()
        connection.socket = mock_socket
        
        result = await connection.health_check()
        
        assert result is True
        assert connection.stats.last_health_check is not None
        mock_socket.emit.assert_called_once_with('ping', {})

    @pytest.mark.asyncio
    async def test_health_check_failure(self, connection):
        """Test health check returns False on error."""
        connection._is_connected = True
        mock_socket = MagicMock()
        mock_socket.emit = AsyncMock(side_effect=Exception("Connection lost"))
        connection.socket = mock_socket
        
        result = await connection.health_check()
        
        assert result is False
        assert connection.stats.last_error is not None


class TestEventNormalizationMapping:
    """Test event normalization with handler mapping."""

    def test_normalize_message_event(self, connection):
        """Test message normalization through handler mapping."""
        event, data = connection._normalize_event('chatMsg', {
            'username': 'alice',
            'msg': 'Hello',
            'time': 1000000
        })
        
        assert event == 'message'
        assert data['user'] == 'alice'
        assert data['content'] == 'Hello'
        assert data['timestamp'] == 1000

    def test_normalize_user_join_event(self, connection):
        """Test user join normalization through handler mapping."""
        event, data = connection._normalize_event('addUser', {
            'name': 'bob',
            'rank': 2,
            'time': 2000000
        })
        
        assert event == 'user_join'
        assert data['user'] == 'bob'
        assert 'user_data' in data
        assert data['timestamp'] == 2000000

    def test_normalize_unknown_event_passthrough(self, connection):
        """Test that unknown events pass through unchanged."""
        event, data = connection._normalize_event('customEvent', {'foo': 'bar'})
        
        assert event == 'customEvent'
        assert data == {'foo': 'bar'}


class TestImprovedErrorMessages:
    """Test improved error messages with context."""

    @pytest.mark.asyncio
    async def test_pm_timeout_error_includes_context(self, connection):
        """Test PM timeout error includes user and timeout context."""
        connection._is_connected = True
        mock_socket = MagicMock()
        mock_socket.emit = AsyncMock(return_value=None)  # Timeout
        connection.socket = mock_socket
        
        from lib.connection.errors import SendError
        with pytest.raises(SendError, match="PM timeout to 'alice' after"):
            await connection.send_pm('alice', 'test')

    @pytest.mark.asyncio
    async def test_socket_config_error_includes_url(self, connection):
        """Test socket config error includes URL."""
        connection.get_func = AsyncMock(side_effect=Exception("Network error"))
        
        from lib.connection.errors import ConnectionError
        with pytest.raises(ConnectionError, match="Failed to fetch socket config from"):
            await connection._get_socket_config()
