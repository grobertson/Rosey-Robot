"""
Abstract connection adapter for chat platforms.

This module defines the ConnectionAdapter abstract base class that all
platform connection implementations must inherit from. It provides a
platform-agnostic interface for connecting to chat platforms.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, Optional, Tuple


class ConnectionAdapter(ABC):
    """
    Abstract interface for platform connections.

    This interface defines the contract that all connection implementations
    must follow. It abstracts platform-specific details to enable the bot
    to work with multiple chat platforms (CyTube, Discord, Twitch, etc.).

    The adapter pattern allows swapping connection implementations without
    changing bot business logic, enabling platform portability and easier
    testing with mock connections.

    Attributes:
        logger: Logger instance for connection events
        is_connected: Connection status flag

    Example:
        >>> class MyConnection(ConnectionAdapter):
        ...     async def connect(self):
        ...         # Platform-specific connection logic
        ...         self._is_connected = True
        ...     # ... implement other methods
        >>> conn = MyConnection()
        >>> await conn.connect()
        >>> await conn.send_message("Hello world")
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize connection adapter.

        Args:
            logger: Optional logger instance. If None, creates default logger
                    named after the class.
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._is_connected = False

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to platform.

        This method should:
        1. Establish network connection
        2. Perform authentication/login
        3. Join channel/room/server
        4. Set _is_connected = True

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If login fails
            TimeoutError: If connection times out
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection gracefully.

        This method should:
        1. Leave channel/room/server (if applicable)
        2. Close network connection
        3. Clean up resources
        4. Set _is_connected = False

        This method should not raise exceptions - it should make best
        effort to clean up even if errors occur.
        """
        pass

    @abstractmethod
    async def send_message(self, content: str, **metadata) -> None:
        """
        Send message to channel/room.

        Args:
            content: Message text to send
            **metadata: Platform-specific metadata (formatting, mentions, etc.)
                       Examples: meta={}, spoiler=True, reply_to=message_id

        Raises:
            NotConnectedError: If not connected
            SendError: If message fails to send

        Example:
            >>> await conn.send_message("Hello!", meta={"color": "blue"})
        """
        pass

    @abstractmethod
    async def send_pm(self, user: str, content: str) -> None:
        """
        Send private message to user.

        Args:
            user: Username to send message to
            content: Message text

        Raises:
            NotConnectedError: If not connected
            SendError: If PM fails to send
            UserNotFoundError: If user doesn't exist

        Example:
            >>> await conn.send_pm("alice", "Hello privately!")
        """
        pass

    @abstractmethod
    def on_event(self, event: str, callback: Callable) -> None:
        """
        Register callback for normalized event.

        Callbacks can be async or sync functions. They receive two arguments:
        - event: The normalized event name (string)
        - data: Event data dictionary

        Args:
            event: Normalized event name (e.g., 'message', 'user_join')
            callback: Callback function(event: str, data: dict)

        Example:
            >>> def on_message(event, data):
            ...     print(f"{data['user']}: {data['content']}")
            >>> conn.on_event('message', on_message)
        """
        pass

    @abstractmethod
    def off_event(self, event: str, callback: Callable) -> None:
        """
        Unregister callback for event.

        Args:
            event: Normalized event name
            callback: Previously registered callback function

        Example:
            >>> conn.off_event('message', on_message)
        """
        pass

    @abstractmethod
    async def recv_events(self) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """
        Async iterator yielding normalized events.

        This method provides an event loop pattern for consuming events.
        It yields (event_name, event_data) tuples as they arrive.

        Yields:
            Tuple of (event_name, event_data) where:
            - event_name: Normalized event name (string)
            - event_data: Event data dictionary

        Raises:
            NotConnectedError: If not connected

        Example:
            >>> async for event, data in conn.recv_events():
            ...     if event == 'message':
            ...         print(f"{data['user']}: {data['content']}")
            ...     elif event == 'user_join':
            ...         print(f"{data['user']} joined")
        """
        pass

    @property
    def is_connected(self) -> bool:
        """
        Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        return self._is_connected

    @abstractmethod
    async def reconnect(self) -> None:
        """
        Reconnect after disconnection.

        Default implementation should:
        1. Disconnect if currently connected
        2. Wait a brief period (avoid rapid reconnection)
        3. Connect

        Implementations should override with platform-specific reconnection
        logic, including exponential backoff and retry limits.

        Raises:
            ConnectionError: If reconnection fails

        Example:
            >>> try:
            ...     await conn.reconnect()
            ... except ConnectionError:
            ...     print("Reconnection failed")
        """
        pass
