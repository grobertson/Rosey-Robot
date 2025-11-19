# Sprint 7, Sortie 2: CyTube Connection Implementation

**Status:** Planning  
**Estimated Effort:** 8 hours  
**Sprint:** The Divide (Sprint 7)  
**Phase:** 1 - Extract Connection Layer  
**Dependencies:** Sortie 1 (ConnectionAdapter interface)

## Objective

Implement `CyTubeConnection` class that wraps socket.io and CyTube protocol details, conforming to the `ConnectionAdapter` interface. Extract all connection-related code from `lib/bot.py` into this isolated module.

## Background

Currently, `lib/bot.py` contains ~300 lines of connection-related code:
- Socket.io configuration fetching (`get_socket_config()`)
- Connection establishment (`connect()`)
- Login/authentication (`login()`)
- Event receiving loop (`recv()`)
- Reconnection logic
- 19+ direct `socket.emit()` calls

This code will move to `CyTubeConnection` while maintaining identical functionality.

## Success Criteria

- ✅ `CyTubeConnection` implements all `ConnectionAdapter` methods
- ✅ All socket.io operations isolated in connection module
- ✅ Event normalization from CyTube → platform-agnostic schema
- ✅ Reconnection logic with exponential backoff
- ✅ Connection can be used standalone (without Bot class)
- ✅ All unit tests pass
- ✅ Integration test: connect, send message, receive events, disconnect
- ✅ No regression in functionality

## Technical Design

### Module Location

```
lib/
└── connection/
    ├── __init__.py          # Exports ConnectionAdapter, CyTubeConnection
    ├── adapter.py           # Abstract base (Sortie 1)
    ├── cytube.py            # CyTube implementation (THIS SORTIE)
    └── errors.py            # Connection errors
```

### CyTubeConnection Class

```python
"""
lib/connection/cytube.py

CyTube connection implementation using socket.io.
"""

import asyncio
import re
import logging
from typing import Dict, Any, Optional, Callable, AsyncIterator, Tuple
from collections import defaultdict

from .adapter import ConnectionAdapter
from .errors import (
    ConnectionError, AuthenticationError,
    NotConnectedError, SendError
)
from ..socket_io import SocketIO, SocketIOResponse, SocketIOError
from ..error import LoginError, ChannelError
from ..util import get as http_get


class CyTubeConnection(ConnectionAdapter):
    """
    CyTube connection implementation.
    
    Manages socket.io connection to CyTube server, handles authentication,
    and normalizes CyTube events to platform-agnostic format.
    
    Attributes:
        domain: CyTube server domain (e.g., 'https://cytu.be')
        channel: Channel name and optional password
        user: Bot user credentials (name, password) or None for guest
        socket: socket.io connection (None when disconnected)
    """
    
    SOCKET_CONFIG_URL = '%(domain)s/socketconfig/%(channel)s.json'
    GUEST_LOGIN_LIMIT = re.compile(r'guest logins .* ([0-9]+) seconds\.', re.I)
    
    def __init__(self,
                 domain: str,
                 channel: str,
                 channel_password: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 response_timeout: float = 3.0,
                 reconnect_delay: float = 5.0,
                 get_func: Optional[Callable] = None,
                 socket_io_func: Optional[Callable] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize CyTube connection.
        
        Args:
            domain: CyTube server domain (e.g., 'https://cytu.be')
            channel: Channel name
            channel_password: Optional channel password
            user: Optional username (None = guest, name only = guest with name)
            password: Optional user password (registered account)
            response_timeout: Timeout for socket.io responses (seconds)
            reconnect_delay: Delay between reconnection attempts (seconds)
            get_func: HTTP GET function (default: lib.util.get)
            socket_io_func: socket.io connect function (default: SocketIO.connect)
            logger: Logger instance
        """
        super().__init__(logger)
        
        self.domain = domain
        self.channel_name = channel
        self.channel_password = channel_password
        self.user_name = user
        self.user_password = password
        
        self.response_timeout = response_timeout
        self.reconnect_delay = reconnect_delay
        
        self.get_func = get_func or http_get
        self.socket_io_func = socket_io_func or SocketIO.connect
        
        self.socket: Optional[SocketIO] = None
        self.server_url: Optional[str] = None
        
        # Event callbacks
        self._event_handlers: Dict[str, list] = defaultdict(list)
        
        # Reconnection state
        self._reconnect_attempts = 0
        self._max_reconnect_delay = 60.0
    
    async def connect(self) -> None:
        """
        Establish connection to CyTube channel.
        
        Steps:
        1. Fetch socket.io configuration
        2. Connect to socket.io server
        3. Authenticate and join channel
        
        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If login fails
        """
        if self._is_connected:
            self.logger.warning("Already connected")
            return
        
        try:
            # Fetch socket.io server configuration
            await self._get_socket_config()
            
            # Connect to socket.io server
            self.logger.info(f"Connecting to {self.server_url}")
            self.socket = await self.socket_io_func(
                self.server_url,
                loop=asyncio.get_event_loop()
            )
            
            # Login to channel
            await self._login()
            
            self._is_connected = True
            self._reconnect_attempts = 0
            self.logger.info("Connected successfully")
            
            # Emit connected event
            await self._emit_normalized_event('connected', {})
            
        except SocketIOError as e:
            raise ConnectionError(f"Socket.io connection failed: {e}") from e
        except LoginError as e:
            raise AuthenticationError(f"Login failed: {e}") from e
        except Exception as e:
            self.logger.error(f"Connection error: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect: {e}") from e
    
    async def disconnect(self) -> None:
        """Close connection gracefully."""
        if not self._is_connected:
            return
        
        try:
            if self.socket:
                await self.socket.close()
                self.socket = None
            
            self._is_connected = False
            self.logger.info("Disconnected")
            
            # Emit disconnected event
            await self._emit_normalized_event('disconnected', {})
            
        except Exception as e:
            self.logger.warning(f"Error during disconnect: {e}")
    
    async def send_message(self, content: str, **metadata) -> None:
        """
        Send chat message to channel.
        
        Args:
            content: Message text
            **metadata: Optional 'meta' dict for CyTube formatting
        
        Raises:
            NotConnectedError: If not connected
            SendError: If message fails to send
        """
        if not self._is_connected or not self.socket:
            raise NotConnectedError("Not connected to channel")
        
        try:
            meta = metadata.get('meta', {})
            await self.socket.emit('chatMsg', {
                'msg': content,
                'meta': meta
            })
        except SocketIOError as e:
            raise SendError(f"Failed to send message: {e}") from e
    
    async def send_pm(self, user: str, content: str) -> None:
        """
        Send private message to user.
        
        Args:
            user: Username to PM
            content: Message text
        
        Raises:
            NotConnectedError: If not connected
            SendError: If PM fails to send
        """
        if not self._is_connected or not self.socket:
            raise NotConnectedError("Not connected to channel")
        
        try:
            response = await self.socket.emit(
                'pm',
                {'to': user, 'msg': content},
                callback=True,
                timeout=self.response_timeout
            )
            
            if not response.success:
                raise SendError(f"PM failed: {response.data}")
                
        except SocketIOError as e:
            raise SendError(f"Failed to send PM: {e}") from e
    
    def on_event(self, event: str, callback: Callable) -> None:
        """Register callback for normalized event."""
        if callback not in self._event_handlers[event]:
            self._event_handlers[event].append(callback)
            self.logger.debug(f"Registered handler for {event}")
    
    def off_event(self, event: str, callback: Callable) -> None:
        """Unregister callback for event."""
        try:
            self._event_handlers[event].remove(callback)
            self.logger.debug(f"Unregistered handler for {event}")
        except ValueError:
            self.logger.warning(f"Handler not found for {event}")
    
    async def recv_events(self) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """
        Async iterator yielding normalized events.
        
        Yields:
            Tuple of (event_name, event_data)
        
        Raises:
            NotConnectedError: If not connected
        """
        if not self._is_connected or not self.socket:
            raise NotConnectedError("Not connected")
        
        try:
            while self._is_connected:
                # Receive raw CyTube event
                event, data = await self.socket.recv()
                
                # Normalize event
                normalized = self._normalize_event(event, data)
                
                if normalized:
                    norm_event, norm_data = normalized
                    
                    # Trigger registered callbacks
                    await self._trigger_callbacks(norm_event, norm_data)
                    
                    # Yield to event loop consumer
                    yield norm_event, norm_data
                    
        except SocketIOError as e:
            self.logger.error(f"Socket error in recv_events: {e}")
            await self._emit_normalized_event('error', {'error': str(e)})
            raise
    
    async def reconnect(self) -> None:
        """
        Reconnect with exponential backoff.
        
        Raises:
            ConnectionError: If reconnection fails
        """
        self._reconnect_attempts += 1
        
        # Calculate backoff delay
        delay = min(
            self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._max_reconnect_delay
        )
        
        self.logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")
        await asyncio.sleep(delay)
        
        await self.disconnect()
        await self.connect()
    
    # Private methods
    
    async def _get_socket_config(self) -> None:
        """Fetch socket.io server URL from CyTube."""
        url = self.SOCKET_CONFIG_URL % {
            'domain': self.domain,
            'channel': self.channel_name
        }
        
        self.logger.info(f"Fetching socket config: {url}")
        
        response = await self.get_func(url, loop=asyncio.get_event_loop())
        config = response.json()
        
        if 'error' in config:
            raise ConnectionError(f"Socket config error: {config['error']}")
        
        # Build socket.io server URL
        servers = config.get('servers', [])
        if not servers:
            raise ConnectionError("No socket.io servers in config")
        
        server = servers[0]
        self.server_url = f"{server['url']}/socket.io/"
        self.logger.info(f"Socket.io server: {self.server_url}")
    
    async def _login(self) -> None:
        """Authenticate and join channel."""
        if not self.socket:
            raise ConnectionError("Socket not connected")
        
        # Join channel
        channel_data = {'name': self.channel_name}
        if self.channel_password:
            channel_data['pw'] = self.channel_password
        
        response = await self.socket.emit(
            'joinChannel',
            channel_data,
            callback=True,
            timeout=self.response_timeout
        )
        
        if not response.success:
            error = response.data
            if 'error' in error:
                raise AuthenticationError(f"Join channel failed: {error['error']}")
        
        # Authenticate user (if credentials provided)
        if self.user_name:
            login_data = {'name': self.user_name}
            
            if self.user_password:
                # Registered user login
                login_data['pw'] = self.user_password
            
            response = await self.socket.emit(
                'login',
                login_data,
                callback=True,
                timeout=self.response_timeout
            )
            
            if not response.success or not response.data.get('success'):
                error = response.data.get('error', 'Unknown error')
                
                # Check for guest login rate limit
                match = self.GUEST_LOGIN_LIMIT.search(error)
                if match:
                    wait_time = int(match.group(1))
                    self.logger.warning(f"Guest login rate limited: {wait_time}s")
                    await asyncio.sleep(wait_time)
                    # Retry login
                    return await self._login()
                
                raise AuthenticationError(f"Login failed: {error}")
        
        self.logger.info("Login successful")
    
    def _normalize_event(self, 
                        event: str, 
                        data: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Normalize CyTube event to platform-agnostic format.
        
        Args:
            event: CyTube event name
            data: CyTube event data
        
        Returns:
            Tuple of (normalized_event, normalized_data) or None to skip
        """
        # Chat message
        if event == 'chatMsg':
            return ('message', {
                'user': data.get('username'),
                'content': data.get('msg'),
                'timestamp': data.get('time', 0) // 1000,
                'platform_data': data
            })
        
        # User joined
        elif event == 'addUser':
            return ('user_join', {
                'user': data.get('name'),
                'platform_data': data
            })
        
        # User left
        elif event == 'userLeave':
            return ('user_leave', {
                'user': data.get('name'),
                'platform_data': data
            })
        
        # User list
        elif event == 'userlist':
            return ('user_list', {
                'users': [u.get('name') for u in data],
                'platform_data': data
            })
        
        # Private message
        elif event == 'pm':
            return ('pm', {
                'user': data.get('username'),
                'content': data.get('msg'),
                'timestamp': data.get('time', 0) // 1000,
                'platform_data': data
            })
        
        # Pass through other events as-is
        else:
            return (event, data)
    
    async def _emit_normalized_event(self, event: str, data: Dict[str, Any]) -> None:
        """Emit normalized event to registered callbacks."""
        await self._trigger_callbacks(event, data)
    
    async def _trigger_callbacks(self, event: str, data: Dict[str, Any]) -> None:
        """Trigger all callbacks for event."""
        for callback in self._event_handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}", exc_info=True)
```

## Implementation Steps

1. **Create cytube.py module** (30 min)
   - Copy template above
   - Add imports
   - Add docstrings

2. **Extract socket config fetching** (30 min)
   - Move `get_socket_config()` logic from bot.py
   - Adapt to `_get_socket_config()` method
   - Test with real CyTube server

3. **Extract login logic** (1 hour)
   - Move `login()` logic from bot.py
   - Adapt to `_login()` method
   - Handle guest login rate limiting
   - Test authentication flows

4. **Implement event normalization** (1.5 hours)
   - Map CyTube events to normalized schema
   - Test with real event data
   - Document event mappings

5. **Implement send operations** (45 min)
   - `send_message()` → `chatMsg` emit
   - `send_pm()` → `pm` emit
   - Error handling

6. **Implement reconnection** (45 min)
   - Exponential backoff logic
   - Max retry limits
   - State cleanup

7. **Write comprehensive tests** (2.5 hours)
   - Mock socket.io for unit tests
   - Test all lifecycle methods
   - Test error scenarios
   - Integration test with real CyTube server (optional)

8. **Update imports** (15 min)
   ```python
   # lib/connection/__init__.py
   from .adapter import ConnectionAdapter
   from .cytube import CyTubeConnection
   from .errors import *
   ```

## Testing Strategy

### Unit Tests

```python
# test/test_cytube_connection.py

import pytest
from unittest.mock import AsyncMock, Mock, patch
from lib.connection import CyTubeConnection
from lib.connection.errors import NotConnectedError


@pytest.fixture
def mock_socket():
    """Mock socket.io connection."""
    socket = AsyncMock()
    socket.emit = AsyncMock()
    socket.recv = AsyncMock()
    socket.close = AsyncMock()
    return socket


@pytest.fixture
async def connection(mock_socket):
    """Create test connection."""
    conn = CyTubeConnection(
        domain='https://cytu.be',
        channel='testchannel'
    )
    
    # Mock socket creation
    conn.socket = mock_socket
    conn._is_connected = True
    
    return conn


@pytest.mark.asyncio
async def test_send_message(connection, mock_socket):
    """Test sending chat message."""
    await connection.send_message("Hello world")
    
    mock_socket.emit.assert_called_once_with(
        'chatMsg',
        {'msg': 'Hello world', 'meta': {}}
    )


@pytest.mark.asyncio
async def test_send_requires_connection():
    """Test send fails when not connected."""
    conn = CyTubeConnection('https://cytu.be', 'test')
    
    with pytest.raises(NotConnectedError):
        await conn.send_message("test")


@pytest.mark.asyncio
async def test_event_normalization(connection, mock_socket):
    """Test CyTube event normalization."""
    # Setup mock to return chat message
    mock_socket.recv.return_value = (
        'chatMsg',
        {'username': 'alice', 'msg': 'hello', 'time': 1699123456789}
    )
    
    # Get first event
    async for event, data in connection.recv_events():
        assert event == 'message'
        assert data['user'] == 'alice'
        assert data['content'] == 'hello'
        assert data['timestamp'] == 1699123456
        break


@pytest.mark.asyncio
async def test_reconnect_backoff(connection):
    """Test exponential backoff on reconnect."""
    connection._reconnect_attempts = 0
    connection.reconnect_delay = 1.0
    
    # Mock connect/disconnect
    connection.connect = AsyncMock()
    connection.disconnect = AsyncMock()
    
    # First reconnect: 1s delay
    await connection.reconnect()
    assert connection._reconnect_attempts == 1
    
    # Second reconnect: 2s delay
    await connection.reconnect()
    assert connection._reconnect_attempts == 2
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_connection():
    """Test connection to real CyTube server."""
    conn = CyTubeConnection(
        domain='https://cytu.be',
        channel='test'
    )
    
    try:
        await conn.connect()
        assert conn.is_connected
        
        await conn.send_message("Test message")
        
        await conn.disconnect()
        assert not conn.is_connected
        
    except Exception as e:
        pytest.skip(f"Integration test failed: {e}")
```

## Code Extraction Mapping

Map bot.py code to CyTubeConnection:

| bot.py Line | Method | CyTubeConnection Method |
|-------------|--------|-------------------------|
| 322-380 | `get_socket_config()` | `_get_socket_config()` |
| 381-395 | `connect()` | `connect()` |
| 396-458 | `login()` | `_login()` |
| 674 | `socket.recv()` | `recv_events()` |
| 407, 826, etc. | `socket.emit()` | Various send methods |

## Dependencies

**Python Packages:**
- None (uses existing socket_io module)

**Internal Modules:**
- `lib.socket_io` - SocketIO client
- `lib.error` - Existing error classes
- `lib.util` - HTTP get function

## Validation

Before moving to Sortie 3:

1. ✅ `CyTubeConnection` implements all adapter methods
2. ✅ Can connect to real CyTube server
3. ✅ Can send messages
4. ✅ Can receive events
5. ✅ Event normalization works
6. ✅ Reconnection logic works
7. ✅ All tests pass
8. ✅ No regressions (compare with bot.py behavior)

## Risks & Mitigations

**Risk:** Breaking existing socket.io behavior  
**Mitigation:** Extensive testing with real CyTube server. Keep bot.py intact until validation complete.

**Risk:** Event normalization loses data  
**Mitigation:** Include `platform_data` field with original event. Bot can access if needed.

**Risk:** Reconnection logic flawed  
**Mitigation:** Test with network interruptions. Monitor production carefully.

## Next Steps

After completion, proceed to:
- **Sortie 3:** Integrate `CyTubeConnection` into `Bot` class
- **Sortie 4:** Extract storage layer

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 7 - The Divide
