"""
CyTube connection implementation using socket.io.

This module provides a concrete implementation of ConnectionAdapter
for the CyTube chat platform.
"""

import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, Optional, Tuple

from ..error import LoginError, SocketConfigError
from ..socket_io import SocketIO, SocketIOError, SocketIOResponse
from ..util import get as http_get
from .adapter import ConnectionAdapter
from .errors import AuthenticationError, ConnectionError, NotConnectedError, SendError


@dataclass
class ConnectionStats:
    """Statistics for monitoring connection health."""
    messages_sent: int = 0
    messages_received: int = 0
    reconnection_count: int = 0
    events_processed: int = 0
    last_error: Optional[str] = None
    connected_since: Optional[float] = None
    last_health_check: Optional[float] = None


class CyTubeConnection(ConnectionAdapter):
    """
    CyTube connection implementation.

    Manages socket.io connection to CyTube server, handles authentication,
    and normalizes CyTube events to platform-agnostic format.

    Attributes:
        domain: CyTube server domain (e.g., 'https://cytu.be')
        channel_name: Channel name
        channel_password: Optional channel password
        user_name: Bot username (None for guest)
        user_password: Bot password (None for guest)
        socket: socket.io connection (None when disconnected)
        server_url: socket.io server URL

    Example:
        >>> conn = CyTubeConnection('https://cytu.be', 'mychannel')
        >>> await conn.connect()
        >>> await conn.send_message("Hello!")
        >>> await conn.disconnect()
    """

    SOCKET_CONFIG_URL = '%(domain)s/socketconfig/%(channel)s.json'
    SOCKET_IO_URL = '%(domain)s/socket.io/'
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
            reconnect_delay: Initial delay between reconnection attempts (seconds)
            get_func: HTTP GET function (default: lib.util.get)
            socket_io_func: socket.io connect function (default: SocketIO.connect)
            logger: Logger instance
        """
        super().__init__(logger)

        # Connection parameters
        self.domain = domain
        self.channel_name = channel
        self.channel_password = channel_password
        self.user_name = user
        self.user_password = password

        # Timing configuration
        self.response_timeout = response_timeout
        self.reconnect_delay = reconnect_delay
        self._max_reconnect_delay = 60.0

        # Dependency injection
        self.get_func = get_func or http_get
        self.socket_io_func = socket_io_func or SocketIO.connect

        # Connection state
        self.socket: Optional[SocketIO] = None
        self.server_url: Optional[str] = None
        self._reconnect_attempts = 0

        # Event handling
        self._event_handlers: Dict[str, list] = defaultdict(list)

        # Statistics and monitoring
        self.stats = ConnectionStats()

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
            self.stats.connected_since = time.time()
            self.stats.reconnection_count = 0
            self.logger.info("Connected successfully")

            # Emit connected event
            await self._emit_normalized_event('connected', {})

        except SocketIOError as e:
            raise ConnectionError(f"Socket.io connection failed: {e}") from e
        except LoginError as e:
            raise AuthenticationError(f"Login failed: {e}") from e
        except SocketConfigError as e:
            raise ConnectionError(f"Socket config error: {e}") from e
        except Exception as e:
            self.logger.error(f"Connection error: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """
        Close connection gracefully.

        Closes socket.io connection and cleans up resources.
        Does not raise exceptions - makes best effort to clean up.
        """
        if not self._is_connected:
            return

        try:
            if self.socket:
                await self.socket.close()
                self.socket = None

            self._is_connected = False
            self.stats.connected_since = None
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
                       (e.g., meta={'italic': True, 'color': '#FF0000'})

        Raises:
            NotConnectedError: If not connected
            SendError: If message fails to send

        Example:
            >>> await conn.send_message("Hello world")
            >>> await conn.send_message("Styled", meta={'bold': True})
        """
        self._ensure_connected()

        try:
            meta = metadata.get('meta', {})
            await self.socket.emit('chatMsg', {
                'msg': content,
                'meta': meta
            })
            self.stats.messages_sent += 1
        except SocketIOError as e:
            self.stats.last_error = str(e)
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

        Example:
            >>> await conn.send_pm("alice", "Private message")
        """
        self._ensure_connected()

        try:
            response = await self.socket.emit(
                'pm',
                {'to': user, 'msg': content},
                SocketIOResponse.match_event(r'^pm$'),
                self.response_timeout
            )

            if response is None:
                raise SendError(
                    f"PM timeout to '{user}' after {self.response_timeout}s"
                )

            # Check if PM was successful
            if len(response) > 1 and isinstance(response[1], dict):
                error = response[1].get('error')
                if error:
                    raise SendError(f"PM to '{user}' failed: {error}")

            self.stats.messages_sent += 1

        except SocketIOError as e:
            self.stats.last_error = str(e)
            raise SendError(f"Failed to send PM to '{user}': {e}") from e

    def on_event(self, event: str, callback: Callable) -> None:
        """
        Register callback for normalized event.

        Args:
            event: Normalized event name (e.g., 'message', 'user_join')
            callback: Callback function(event: str, data: dict)
                     Can be async or sync
        """
        if callback not in self._event_handlers[event]:
            self._event_handlers[event].append(callback)
            self.logger.debug(f"Registered handler for {event}")

    def off_event(self, event: str, callback: Callable) -> None:
        """
        Unregister callback for event.

        Args:
            event: Normalized event name
            callback: Previously registered callback
        """
        try:
            self._event_handlers[event].remove(callback)
            self.logger.debug(f"Unregistered handler for {event}")
        except (KeyError, ValueError):
            self.logger.warning(f"Handler not found for {event}")

    async def recv_events(self) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:  # type: ignore[override,misc]
        """
        Async iterator yielding normalized events.

        Yields:
            Tuple of (event_name, event_data)

        Raises:
            NotConnectedError: If not connected

        Example:
            >>> async for event, data in conn.recv_events():
            ...     if event == 'message':
            ...         print(f"{data['user']}: {data['content']}")
        """
        self._ensure_connected()

        try:
            while self._is_connected:
                # Receive raw CyTube event
                event, data = await self.socket.recv()

                # Normalize event
                normalized = self._normalize_event(event, data)

                if normalized:
                    norm_event, norm_data = normalized

                    # Update statistics
                    self.stats.messages_received += 1
                    self.stats.events_processed += 1

                    # Trigger registered callbacks
                    await self._trigger_callbacks(norm_event, norm_data)

                    # Yield to event loop consumer
                    yield norm_event, norm_data

        except SocketIOError as e:
            self.stats.last_error = str(e)
            self.logger.error(f"Socket error in recv_events: {e}")
            await self._emit_normalized_event('error', {'error': str(e)})
            raise

    async def reconnect(self) -> None:
        """
        Reconnect with exponential backoff.

        Calculates backoff delay using formula:
        delay = min(initial_delay * 2^(attempts-1), max_delay)

        Raises:
            ConnectionError: If reconnection fails
        """
        self._reconnect_attempts += 1
        self.stats.reconnection_count += 1

        # Calculate backoff delay
        delay = min(
            self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._max_reconnect_delay
        )

        self.logger.info(
            f"Reconnecting to {self.domain}/{self.channel_name} in {delay}s "
            f"(attempt {self._reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        await self.disconnect()
        await self.connect()

    async def health_check(self) -> bool:
        """
        Perform health check on connection.

        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._is_connected or not self.socket:
            return False

        try:
            # Simple ping to verify connection is alive
            await asyncio.wait_for(
                self.socket.emit('ping', {}),
                timeout=2.0
            )
            self.stats.last_health_check = time.time()
            return True
        except (SocketIOError, asyncio.TimeoutError, Exception) as e:
            self.logger.warning(f"Health check failed: {e}")
            self.stats.last_error = str(e)
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        return False

    # Private methods

    def _ensure_connected(self) -> None:
        """Validate connection state, raise if not connected."""
        if not self._is_connected or not self.socket:
            raise NotConnectedError(
                f"Not connected to {self.domain}/{self.channel_name}. "
                f"Call connect() first."
            )

    async def _get_socket_config(self) -> None:
        """
        Fetch socket.io server URL from CyTube.

        Raises:
            ConnectionError: If config fetch fails
            SocketConfigError: If config is invalid
        """
        data = {
            'domain': self.domain,
            'channel': self.channel_name
        }
        url = self.SOCKET_CONFIG_URL % data

        # Ensure URL has protocol
        if not url.startswith('http'):
            url = 'https://' + url

        self.logger.info(f"Fetching socket config: {url}")

        try:
            response = await self.get_func(url)
            config = json.loads(response)
        except Exception as e:
            error_msg = f"Failed to fetch socket config from {url}: {e}"
            self.stats.last_error = error_msg
            raise ConnectionError(error_msg) from e

        self.logger.info(f"Socket config: {config}")

        if 'error' in config:
            raise SocketConfigError(f"Socket config error: {config['error']}")

        # Find best server (prefer secure)
        servers = config.get('servers', [])
        if not servers:
            raise SocketConfigError('No socket.io servers in config')

        # Try to find secure server first
        server_url = None
        for srv in servers:
            if srv.get('secure'):
                server_url = srv['url']
                self.logger.info(f"Using secure server: {server_url}")
                break

        # Fall back to any server
        if not server_url:
            server_url = servers[0]['url']
            self.logger.info(f"Using non-secure server: {server_url}")

        # Build socket.io URL
        data['domain'] = server_url
        self.server_url = self.SOCKET_IO_URL % data
        self.logger.info(f"Socket.io server: {self.server_url}")

    async def _login(self) -> None:
        """
        Authenticate and join channel.

        Raises:
            AuthenticationError: If login fails
            SocketIOError: If socket communication fails
        """
        if not self.socket:
            raise ConnectionError("Socket not connected during login")

        # Step 1: Join channel
        await self._join_channel()

        # Step 2: Authenticate user (if credentials provided)
        if self.user_name:
            await self._authenticate_user()
        else:
            self.logger.info("Connected as guest")

    async def _join_channel(self) -> None:
        """Join the CyTube channel (with optional password).

        Raises:
            AuthenticationError: If channel join fails or password invalid
        """
        if not self.socket:
            raise ConnectionError("Socket not connected during channel join")

        self.logger.info(f"Joining channel '{self.channel_name}'")
        channel_data = {'name': self.channel_name}
        if self.channel_password:
            channel_data['pw'] = self.channel_password

        response = await self.socket.emit(
            'joinChannel',
            channel_data,
            SocketIOResponse.match_event(r'^(needPassword|)$'),
            self.response_timeout
        )

        if response is None:
            error_msg = (
                f"Channel join timeout for '{self.channel_name}' "
                f"after {self.response_timeout}s"
            )
            self.stats.last_error = error_msg
            raise AuthenticationError(error_msg)

        if response[0] == 'needPassword':
            error_msg = f"Invalid password for channel '{self.channel_name}'"
            self.stats.last_error = error_msg
            raise AuthenticationError(error_msg)

        self.logger.info(f"Successfully joined channel '{self.channel_name}'")

    async def _authenticate_user(self) -> None:
        """Authenticate user with CyTube (handles rate limiting).

        Raises:
            AuthenticationError: If authentication fails
        """
        if not self.socket:
            raise ConnectionError("Socket not connected during authentication")

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            self.logger.info(f"Authenticating as '{self.user_name}'")
            login_data = {'name': self.user_name}

            if self.user_password:
                login_data['pw'] = self.user_password

            response = await self.socket.emit(
                'login',
                login_data,
                SocketIOResponse.match_event(r'^login$'),
                self.response_timeout
            )

            if response is None:
                error_msg = (
                    f"Authentication timeout for user '{self.user_name}' "
                    f"after {self.response_timeout}s"
                )
                self.stats.last_error = error_msg
                raise AuthenticationError(error_msg)

            result = response[1] if len(response) > 1 else {}
            self.logger.debug(f"Login response: {result}")

            # Success case
            if result.get('success', False):
                self.logger.info(f"Successfully authenticated as '{self.user_name}'")
                return

            # Error handling
            error = result.get('error', 'Unknown authentication error')
            self.logger.error(f"Authentication failed: {error}")

            # Check for rate limiting
            if await self._handle_rate_limit(error):
                retry_count += 1
                continue

            # Non-retriable error
            error_msg = f"Failed to authenticate user '{self.user_name}': {error}"
            self.stats.last_error = error_msg
            raise AuthenticationError(error_msg)

        # Max retries exceeded
        error_msg = (
            f"Authentication failed after {max_retries} retries "
            f"for user '{self.user_name}'"
        )
        self.stats.last_error = error_msg
        raise AuthenticationError(error_msg)

    async def _handle_rate_limit(self, error: str) -> bool:
        """Handle guest login rate limiting.

        Args:
            error: Error message from login response

        Returns:
            True if rate limit detected and handled, False otherwise
        """
        match = self.GUEST_LOGIN_LIMIT.match(error)
        if not match:
            return False

        try:
            wait_time = max(int(match.group(1)), 1)
            self.logger.warning(
                f"Guest login rate limited. Waiting {wait_time}s before retry..."
            )
            await asyncio.sleep(wait_time)
            return True
        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse rate limit duration: {e}")
            return False

    def _normalize_cytube_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CyTube user object to platform-agnostic structure.

        Converts CyTube-specific user fields to normalized format that works
        across platforms. This enables platform-agnostic user handling.

        Args:
            user_data: Raw CyTube user object

        Returns:
            Normalized user dictionary with standard fields:
            - username: User's name
            - rank: Privilege level (0=guest, 2+=moderator)
            - is_afk: Away from keyboard status
            - is_moderator: True if rank >= 2
            - meta: User profile metadata
        """
        return {
            'username': user_data.get('name', ''),
            'rank': user_data.get('rank', 0),
            'is_afk': user_data.get('afk', False),
            'is_moderator': user_data.get('rank', 0) >= 2,
            'meta': user_data.get('meta', {})
        }

    def _normalize_event(self,
                        event: str,
                        data: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Normalize CyTube event to platform-agnostic format.

        Uses a cleaner mapping approach for better maintainability.
        Unknown events pass through as-is for backward compatibility.

        Args:
            event: CyTube event name
            data: CyTube event data

        Returns:
            Tuple of (normalized_event, normalized_data) or None to skip
        """
        # Map CyTube events to normalization handlers
        normalizers = {
            'chatMsg': self._normalize_message,
            'addUser': self._normalize_user_join,
            'userLeave': self._normalize_user_leave,
            'userlist': self._normalize_user_list,
            'pm': self._normalize_pm,
        }

        normalizer = normalizers.get(event)
        if normalizer:
            return normalizer(data)

        # Pass through unknown events as-is (backward compatibility)
        return (event, data)

    def _normalize_message(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Normalize chat message event."""
        return ('message', {
            'user': data.get('username', ''),
            'content': data.get('msg', ''),
            'timestamp': data.get('time', 0) // 1000,
            'platform_data': data
        })

    def _normalize_user_join(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Normalize user join event."""
        return ('user_join', {
            'user': data.get('name', ''),
            'user_data': self._normalize_cytube_user(data),
            'timestamp': data.get('time', 0),
            'platform_data': data
        })

    def _normalize_user_leave(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Normalize user leave event."""
        normalized = {
            'user': data.get('name', ''),
            'timestamp': data.get('time', 0),
            'platform_data': data
        }

        # Add user_data if available (CyTube may include rank/afk)
        if 'rank' in data or 'afk' in data:
            normalized['user_data'] = self._normalize_cytube_user(data)

        return ('user_leave', normalized)

    def _normalize_user_list(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Normalize user list event."""
        return ('user_list', {
            'users': [self._normalize_cytube_user(u) for u in data],  # type: ignore[arg-type]
            'count': len(data),
            'platform_data': data
        })

    def _normalize_pm(self, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Normalize private message event."""
        return ('pm', {
            'user': data.get('username', ''),
            'recipient': self.user_name or 'bot',
            'content': data.get('msg', ''),
            'timestamp': data.get('time', 0) // 1000,
            'platform_data': data
        })

    async def _emit_normalized_event(self, event: str, data: Dict[str, Any]) -> None:
        """
        Emit normalized event to registered callbacks.

        Args:
            event: Normalized event name
            data: Event data
        """
        await self._trigger_callbacks(event, data)

    async def _trigger_callbacks(self, event: str, data: Dict[str, Any]) -> None:
        """
        Trigger all callbacks for event.

        Args:
            event: Event name
            data: Event data
        """
        for callback in self._event_handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}", exc_info=True)
