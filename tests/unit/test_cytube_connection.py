"""
Unit tests for CyTubeConnection implementation.

Tests verify the CyTube-specific connection adapter functionality,
including socket.io integration, event normalization, and authentication.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Optional

from lib.connection import CyTubeConnection
from lib.connection.errors import (
    ConnectionError,
    AuthenticationError,
    NotConnectedError,
    SendError
)
from lib.socket_io import SocketIOResponse, SocketIOError
from lib.error import LoginError, SocketConfigError


@pytest.fixture
def mock_socket():
    """Mock socket.io connection."""
    socket = AsyncMock()
    socket.emit = AsyncMock()
    socket.recv = AsyncMock()
    socket.close = AsyncMock()
    return socket


@pytest.fixture
def mock_http_get():
    """Mock HTTP GET function."""
    async_mock = AsyncMock()
    # Return valid socket config by default
    async_mock.return_value = json.dumps({
        'servers': [
            {'url': 'https://test.server', 'secure': True}
        ]
    })
    return async_mock


@pytest.fixture
def connection(mock_http_get):
    """Create test connection with mocked dependencies."""
    return CyTubeConnection(
        domain='https://cytu.be',
        channel='testchannel',
        channel_password='',
        user='testbot',
        password='',
        get_func=mock_http_get
    )


class TestCyTubeConnectionInit:
    """Test CyTubeConnection initialization."""
    
    def test_basic_initialization(self):
        """Test basic connection initialization."""
        conn = CyTubeConnection(
            domain='https://cytu.be',
            channel='test'
        )
        assert conn.domain == 'https://cytu.be'
        assert conn.channel_name == 'test'
        assert conn.channel_password is None
        assert conn.user_name is None
        assert conn.user_password is None
        assert not conn.is_connected
        
    def test_initialization_with_auth(self):
        """Test initialization with authentication."""
        conn = CyTubeConnection(
            domain='https://cytu.be',
            channel='test',
            channel_password='chanpass',
            user='bot',
            password='botpass'
        )
        assert conn.channel_password == 'chanpass'
        assert conn.user_name == 'bot'
        assert conn.user_password == 'botpass'
        
    def test_custom_timeouts(self):
        """Test custom timeout configuration."""
        conn = CyTubeConnection(
            domain='https://cytu.be',
            channel='test',
            response_timeout=5.0,
            reconnect_delay=10.0
        )
        assert conn.response_timeout == 5.0
        assert conn.reconnect_delay == 10.0


class TestSocketConfigFetching:
    """Test socket configuration fetching."""
    
    @pytest.mark.asyncio
    async def test_get_socket_config_success(self, connection, mock_http_get):
        """Test successful socket config fetch."""
        await connection._get_socket_config()
        
        assert connection.server_url is not None
        assert 'socket.io' in connection.server_url
        mock_http_get.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_socket_config_with_secure_server(self, connection, mock_http_get):
        """Test prefers secure server."""
        mock_http_get.return_value = json.dumps({
            'servers': [
                {'url': 'http://insecure.server', 'secure': False},
                {'url': 'https://secure.server', 'secure': True}
            ]
        })
        
        await connection._get_socket_config()
        assert 'https://secure.server' in connection.server_url
        
    @pytest.mark.asyncio
    async def test_get_socket_config_fallback_to_insecure(self, connection, mock_http_get):
        """Test falls back to insecure server if no secure."""
        mock_http_get.return_value = json.dumps({
            'servers': [
                {'url': 'http://only.server', 'secure': False}
            ]
        })
        
        await connection._get_socket_config()
        assert 'http://only.server' in connection.server_url
        
    @pytest.mark.asyncio
    async def test_get_socket_config_no_servers(self, connection, mock_http_get):
        """Test handles missing servers in config."""
        mock_http_get.return_value = json.dumps({'servers': []})
        
        with pytest.raises(SocketConfigError):
            await connection._get_socket_config()
            
    @pytest.mark.asyncio
    async def test_get_socket_config_error_in_response(self, connection, mock_http_get):
        """Test handles error in config response."""
        mock_http_get.return_value = json.dumps({'error': 'Channel not found'})
        
        with pytest.raises(SocketConfigError):
            await connection._get_socket_config()
            
    @pytest.mark.asyncio
    async def test_get_socket_config_http_failure(self, connection, mock_http_get):
        """Test handles HTTP request failure."""
        mock_http_get.side_effect = Exception("Network error")
        
        with pytest.raises(ConnectionError):
            await connection._get_socket_config()


class TestConnectionLifecycle:
    """Test connection lifecycle (connect/disconnect/reconnect)."""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, connection, mock_socket, mock_http_get):
        """Test successful connection."""
        # Mock socket creation
        socket_io_mock = AsyncMock(return_value=mock_socket)
        connection.socket_io_func = socket_io_mock
        
        # Mock login responses
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel success
            ('login', {'success': True})  # login success
        ]
        
        await connection.connect()
        
        assert connection.is_connected
        assert connection.socket == mock_socket
        socket_io_mock.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, connection, mock_socket):
        """Test connect when already connected."""
        connection._is_connected = True
        connection.socket = mock_socket
        
        await connection.connect()
        
        # Should not attempt reconnection
        assert connection.socket == mock_socket
        
    @pytest.mark.asyncio
    async def test_disconnect(self, connection, mock_socket):
        """Test disconnection."""
        connection._is_connected = True
        connection.socket = mock_socket
        
        await connection.disconnect()
        
        assert not connection.is_connected
        assert connection.socket is None
        mock_socket.close.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, connection):
        """Test disconnect when not connected."""
        await connection.disconnect()
        # Should not raise error
        assert not connection.is_connected
        
    @pytest.mark.asyncio
    async def test_reconnect_with_backoff(self, connection):
        """Test reconnect with exponential backoff."""
        connection.reconnect_delay = 0.1  # Fast for testing
        connection._reconnect_attempts = 0
        
        # Mock connect/disconnect
        connection.connect = AsyncMock()
        connection.disconnect = AsyncMock()
        
        # First reconnect
        await connection.reconnect()
        assert connection._reconnect_attempts == 1
        connection.connect.assert_called_once()
        
        # Second reconnect (should have longer delay)
        await connection.reconnect()
        assert connection._reconnect_attempts == 2
        
    @pytest.mark.asyncio
    async def test_reconnect_max_delay(self, connection):
        """Test reconnect respects max delay."""
        connection.reconnect_delay = 1.0
        connection._max_reconnect_delay = 5.0
        connection._reconnect_attempts = 10  # Would exceed max
        
        connection.connect = AsyncMock()
        connection.disconnect = AsyncMock()
        
        # Should cap at max delay
        await connection.reconnect()


class TestAuthentication:
    """Test channel join and user authentication."""
    
    @pytest.mark.asyncio
    async def test_login_as_guest(self, connection, mock_socket):
        """Test guest login (no user credentials)."""
        connection.user_name = None
        connection.socket = mock_socket
        
        # Mock joinChannel response
        mock_socket.emit.return_value = ('', {})
        
        await connection._login()
        
        # Should only call joinChannel, not login
        assert mock_socket.emit.call_count == 1
        
    @pytest.mark.asyncio
    async def test_login_with_username(self, connection, mock_socket):
        """Test login with username."""
        connection.socket = mock_socket
        
        # Mock responses
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel
            ('login', {'success': True})  # login
        ]
        
        await connection._login()
        
        assert mock_socket.emit.call_count == 2
        
    @pytest.mark.asyncio
    async def test_login_invalid_channel_password(self, connection, mock_socket):
        """Test channel join with invalid password."""
        connection.socket = mock_socket
        mock_socket.emit.return_value = ('needPassword', {})
        
        with pytest.raises(AuthenticationError, match="Invalid channel password"):
            await connection._login()
            
    @pytest.mark.asyncio
    async def test_login_timeout(self, connection, mock_socket):
        """Test login handles timeout."""
        connection.socket = mock_socket
        mock_socket.emit.return_value = None  # Timeout
        
        with pytest.raises(AuthenticationError, match="timeout"):
            await connection._login()
            
    @pytest.mark.asyncio
    async def test_login_guest_rate_limit(self, connection, mock_socket):
        """Test guest login rate limit handling."""
        connection.socket = mock_socket
        
        # Mock responses: rate limit, then success on retry
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel
            ('login', {'error': 'guest logins are restricted to 1 every 5 seconds.'}),
            ('login', {'success': True})  # login retry success
        ]
        
        with patch('asyncio.sleep', new=AsyncMock()):
            await connection._login()
            
        # Should retry after rate limit
        assert mock_socket.emit.call_count == 3
        
    @pytest.mark.asyncio
    async def test_login_auth_error(self, connection, mock_socket):
        """Test login handles authentication error."""
        connection.socket = mock_socket
        
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel
            ('login', {'error': 'Invalid username or password'})
        ]
        
        with pytest.raises(AuthenticationError, match="Invalid username"):
            await connection._login()


class TestMessageSending:
    """Test sending messages and PMs."""
    
    @pytest.mark.asyncio
    async def test_send_message(self, connection, mock_socket):
        """Test sending chat message."""
        connection._is_connected = True
        connection.socket = mock_socket
        
        await connection.send_message("Hello world")
        
        mock_socket.emit.assert_called_once_with(
            'chatMsg',
            {'msg': 'Hello world', 'meta': {}}
        )
        
    @pytest.mark.asyncio
    async def test_send_message_with_metadata(self, connection, mock_socket):
        """Test sending message with formatting metadata."""
        connection._is_connected = True
        connection.socket = mock_socket
        
        await connection.send_message("Styled", meta={'bold': True})
        
        mock_socket.emit.assert_called_once_with(
            'chatMsg',
            {'msg': 'Styled', 'meta': {'bold': True}}
        )
        
    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, connection):
        """Test send_message fails when not connected."""
        with pytest.raises(NotConnectedError):
            await connection.send_message("test")
            
    @pytest.mark.asyncio
    async def test_send_pm(self, connection, mock_socket):
        """Test sending private message."""
        connection._is_connected = True
        connection.socket = mock_socket
        mock_socket.emit.return_value = ('pm', {'success': True})
        
        await connection.send_pm("alice", "Private message")
        
        mock_socket.emit.assert_called_once()
        args = mock_socket.emit.call_args[0]
        assert args[0] == 'pm'
        assert args[1] == {'to': 'alice', 'msg': 'Private message'}
        
    @pytest.mark.asyncio
    async def test_send_pm_not_connected(self, connection):
        """Test send_pm fails when not connected."""
        with pytest.raises(NotConnectedError):
            await connection.send_pm("alice", "test")
            
    @pytest.mark.asyncio
    async def test_send_pm_timeout(self, connection, mock_socket):
        """Test send_pm handles timeout."""
        connection._is_connected = True
        connection.socket = mock_socket
        mock_socket.emit.return_value = None  # Timeout
        
        with pytest.raises(SendError, match="timeout"):
            await connection.send_pm("alice", "test")
            
    @pytest.mark.asyncio
    async def test_send_pm_error(self, connection, mock_socket):
        """Test send_pm handles error response."""
        connection._is_connected = True
        connection.socket = mock_socket
        mock_socket.emit.return_value = ('pm', {'error': 'User not found'})
        
        with pytest.raises(SendError, match="User not found"):
            await connection.send_pm("nonexistent", "test")


class TestEventNormalization:
    """Test CyTube event normalization."""
    
    def test_normalize_chat_message(self, connection):
        """Test chatMsg event normalization."""
        cytube_event = {
            'username': 'alice',
            'msg': 'Hello world',
            'time': 1699123456789
        }
        
        event, data = connection._normalize_event('chatMsg', cytube_event)
        
        assert event == 'message'
        assert data['user'] == 'alice'
        assert data['content'] == 'Hello world'
        assert data['timestamp'] == 1699123456
        assert 'platform_data' in data
        
    def test_normalize_user_join(self, connection):
        """Test addUser event normalization."""
        cytube_event = {'name': 'bob', 'rank': 1}
        
        event, data = connection._normalize_event('addUser', cytube_event)
        
        assert event == 'user_join'
        assert data['user'] == 'bob'
        assert 'platform_data' in data
        
    def test_normalize_user_leave(self, connection):
        """Test userLeave event normalization."""
        cytube_event = {'name': 'charlie'}
        
        event, data = connection._normalize_event('userLeave', cytube_event)
        
        assert event == 'user_leave'
        assert data['user'] == 'charlie'
        
    def test_normalize_user_list(self, connection):
        """Test userlist event normalization.
        
        After Sortie 1: users array contains full normalized user objects,
        not just username strings.
        """
        cytube_event = [
            {'name': 'alice', 'rank': 2, 'afk': False},
            {'name': 'bob', 'rank': 1, 'afk': False}
        ]
        
        event, data = connection._normalize_event('userlist', cytube_event)
        
        assert event == 'user_list'
        assert data['count'] == 2
        
        # ✅ Users array now contains full normalized objects (Sortie 1)
        assert len(data['users']) == 2
        assert data['users'][0]['username'] == 'alice'
        assert data['users'][0]['rank'] == 2
        assert data['users'][0]['is_moderator'] is True
        assert data['users'][1]['username'] == 'bob'
        assert data['users'][1]['rank'] == 1
        assert data['users'][1]['is_moderator'] is False
        
    def test_normalize_pm(self, connection):
        """Test pm event normalization."""
        cytube_event = {
            'username': 'alice',
            'msg': 'Secret message',
            'time': 1699123456789
        }
        
        event, data = connection._normalize_event('pm', cytube_event)
        
        assert event == 'pm'
        assert data['user'] == 'alice'
        assert data['content'] == 'Secret message'
        
    def test_normalize_unknown_event(self, connection):
        """Test unknown events pass through."""
        cytube_event = {'some': 'data'}
        
        event, data = connection._normalize_event('unknownEvent', cytube_event)
        
        assert event == 'unknownEvent'
        assert data == cytube_event


class TestEventHandling:
    """Test event callback registration and triggering."""
    
    def test_register_callback(self, connection):
        """Test event callback registration."""
        callback = Mock()
        connection.on_event('message', callback)
        
        assert callback in connection._event_handlers['message']
        
    def test_unregister_callback(self, connection):
        """Test event callback unregistration."""
        callback = Mock()
        connection.on_event('message', callback)
        connection.off_event('message', callback)
        
        assert callback not in connection._event_handlers.get('message', [])
        
    def test_unregister_nonexistent_callback(self, connection):
        """Test unregistering callback that was never registered."""
        callback = Mock()
        # Should not raise error
        connection.off_event('message', callback)
        
    @pytest.mark.asyncio
    async def test_trigger_sync_callback(self, connection):
        """Test triggering synchronous callback."""
        callback = Mock()
        connection.on_event('test', callback)
        
        await connection._trigger_callbacks('test', {'data': 'value'})
        
        callback.assert_called_once_with('test', {'data': 'value'})
        
    @pytest.mark.asyncio
    async def test_trigger_async_callback(self, connection):
        """Test triggering asynchronous callback."""
        callback = AsyncMock()
        connection.on_event('test', callback)
        
        await connection._trigger_callbacks('test', {'data': 'value'})
        
        callback.assert_called_once_with('test', {'data': 'value'})
        
    @pytest.mark.asyncio
    async def test_callback_error_handling(self, connection):
        """Test error in callback doesn't crash."""
        def bad_callback(event, data):
            raise Exception("Callback error")
        
        connection.on_event('test', bad_callback)
        
        # Should not raise
        await connection._trigger_callbacks('test', {})
        
    @pytest.mark.asyncio
    async def test_recv_events_not_connected(self, connection):
        """Test recv_events fails when not connected."""
        with pytest.raises(NotConnectedError):
            async for _ in connection.recv_events():
                pass
                
    @pytest.mark.asyncio
    async def test_recv_events_yields_normalized(self, connection, mock_socket):
        """Test recv_events yields normalized events."""
        connection._is_connected = True
        connection.socket = mock_socket
        
        # Mock socket to return chat message
        mock_socket.recv.side_effect = [
            ('chatMsg', {'username': 'alice', 'msg': 'hi', 'time': 1699123456789}),
            asyncio.CancelledError()  # Stop iteration
        ]
        
        events = []
        try:
            async for event, data in connection.recv_events():
                events.append((event, data))
        except asyncio.CancelledError:
            pass
        
        assert len(events) == 1
        assert events[0][0] == 'message'
        assert events[0][1]['user'] == 'alice'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
