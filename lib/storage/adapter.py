"""
Abstract storage adapter for data persistence.

This module defines the StorageAdapter abstract base class that all
storage implementations must inherit from. It provides a database-agnostic
interface for bot data persistence.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageAdapter(ABC):
    """
    Abstract interface for data storage.

    This interface defines the contract that all storage implementations
    must follow. It abstracts database-specific details to enable the bot
    to work with multiple storage backends (SQLite, PostgreSQL, Redis, etc.).

    All methods are async to support asynchronous database drivers and
    improve bot responsiveness.

    Attributes:
        logger: Logger instance for storage events
        is_connected: Storage connection status

    Example:
        >>> class MyStorage(StorageAdapter):
        ...     async def connect(self):
        ...         self._is_connected = True
        ...     # ... implement other methods
        >>> storage = MyStorage()
        >>> await storage.connect()
        >>> await storage.save_user_stats("alice", first_seen=123456)
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize storage adapter.

        Args:
            logger: Optional logger instance. If None, creates default logger.
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._is_connected = False

    @abstractmethod
    async def connect(self) -> None:
        """
        Initialize storage connection.

        This method should:
        1. Establish database connection
        2. Run any necessary migrations
        3. Create required tables/indices
        4. Set is_connected = True

        Raises:
            StorageConnectionError: If connection fails
            MigrationError: If schema migration fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close storage connection.

        This method should:
        1. Commit any pending transactions
        2. Close database connection
        3. Clean up resources (connection pools, etc.)
        4. Set is_connected = False

        Should not raise exceptions (best effort cleanup).
        Implementers should catch and log any errors.
        """
        pass

    @property
    def is_connected(self) -> bool:
        """
        Check if storage is connected.

        Returns:
            True if connected and ready for operations, False otherwise
        """
        return self._is_connected

    # ==================== User Statistics ====================

    @abstractmethod
    async def save_user_stats(self,
                             username: str,
                             first_seen: Optional[int] = None,
                             last_seen: Optional[int] = None,
                             chat_lines: Optional[int] = None,
                             time_connected: Optional[int] = None,
                             session_start: Optional[int] = None) -> None:
        """
        Save or update user statistics.

        If user doesn't exist, creates new record. If user exists, updates
        only the provided fields (None values are ignored).

        Args:
            username: Username (case-sensitive)
            first_seen: Unix timestamp (seconds) of first appearance
            last_seen: Unix timestamp of last activity
            chat_lines: Total chat messages sent (increment if provided)
            time_connected: Total seconds connected (increment if provided)
            session_start: Unix timestamp of current session start

        Raises:
            StorageError: If save fails
            IntegrityError: If data violates constraints
        """
        pass

    @abstractmethod
    async def get_user_stats(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve statistics for a user.

        Args:
            username: Username to lookup (case-sensitive)

        Returns:
            Dict with keys:
                - username: str
                - first_seen: int (Unix timestamp)
                - last_seen: int (Unix timestamp)
                - total_chat_lines: int
                - total_time_connected: int (seconds)
                - current_session_start: Optional[int] (Unix timestamp)
            Returns None if user not found

        Raises:
            StorageError: If query fails
        """
        pass

    @abstractmethod
    async def get_all_user_stats(self,
                                 limit: Optional[int] = None,
                                 offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve statistics for all users.

        Args:
            limit: Maximum number of users to return (None = all users)
            offset: Number of users to skip (for pagination)

        Returns:
            List of user stat dicts (same format as get_user_stats)
            Sorted by last_seen descending (most recent first)

        Raises:
            StorageError: If query fails
        """
        pass

    # ==================== User Actions / Logs ====================

    @abstractmethod
    async def log_user_action(self,
                             username: str,
                             action_type: str,
                             details: Optional[str] = None,
                             timestamp: Optional[int] = None) -> None:
        """
        Log user action (join, leave, PM, etc.).

        Args:
            username: Username performing action
            action_type: Type of action (e.g., 'join', 'leave', 'pm', 'kick')
            details: Optional action details (JSON string or plain text)
            timestamp: Optional Unix timestamp (defaults to current time)

        Raises:
            StorageError: If log fails
        """
        pass

    @abstractmethod
    async def get_user_actions(self,
                              username: Optional[str] = None,
                              action_type: Optional[str] = None,
                              limit: int = 100,
                              offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve user action logs.

        Args:
            username: Filter by username (None = all users)
            action_type: Filter by action type (None = all types)
            limit: Maximum actions to return
            offset: Number of actions to skip

        Returns:
            List of action dicts with keys:
                - id: int (unique action ID)
                - timestamp: int (Unix timestamp)
                - username: str
                - action_type: str
                - details: Optional[str]
            Sorted by timestamp descending (most recent first)

        Raises:
            StorageError: If query fails
        """
        pass

    # ==================== Channel Statistics ====================

    @abstractmethod
    async def update_channel_stats(self,
                                   max_users: Optional[int] = None,
                                   max_connected: Optional[int] = None,
                                   timestamp: Optional[int] = None) -> None:
        """
        Update channel-level statistics.

        Updates the channel's high water marks if provided values exceed
        current maximums.

        Args:
            max_users: New maximum chat user count
            max_connected: New maximum connected user count
            timestamp: Unix timestamp of new maximum (defaults to current time)

        Raises:
            StorageError: If update fails
        """
        pass

    @abstractmethod
    async def get_channel_stats(self) -> Dict[str, Any]:
        """
        Retrieve channel statistics.

        Returns:
            Dict with keys:
                - max_users: int (highest chat user count)
                - max_users_timestamp: int (when max_users was reached)
                - max_connected: int (highest connected count)
                - max_connected_timestamp: int (when max_connected was reached)
                - last_updated: int (last modification time)

        Raises:
            StorageError: If query fails
        """
        pass

    @abstractmethod
    async def log_user_count(self,
                            chat_users: int,
                            connected_users: int,
                            timestamp: Optional[int] = None) -> None:
        """
        Log user count snapshot for historical tracking.

        Used to build graphs of user activity over time.

        Args:
            chat_users: Number of users in chat (visible users)
            connected_users: Number of connected users (includes hidden)
            timestamp: Optional Unix timestamp (defaults to current time)

        Raises:
            StorageError: If log fails
        """
        pass

    @abstractmethod
    async def get_user_count_history(self,
                                     start_time: Optional[int] = None,
                                     end_time: Optional[int] = None,
                                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve user count history.

        Args:
            start_time: Filter >= this Unix timestamp (None = no lower bound)
            end_time: Filter <= this Unix timestamp (None = no upper bound)
            limit: Maximum records to return (None = all records)

        Returns:
            List of dicts with keys:
                - id: int
                - timestamp: int (Unix timestamp)
                - chat_users: int
                - connected_users: int
            Sorted by timestamp ascending (oldest first)

        Raises:
            StorageError: If query fails
        """
        pass

    # ==================== Chat Messages ====================

    @abstractmethod
    async def save_message(self,
                          username: str,
                          message: str,
                          timestamp: Optional[int] = None) -> None:
        """
        Store chat message (for recent chat cache).

        Messages are typically kept for a short time (e.g., last 1000 messages)
        for display in web interfaces or debugging.

        Args:
            username: Username who sent message
            message: Message text (plain text, not HTML)
            timestamp: Optional Unix timestamp (defaults to current time)

        Raises:
            StorageError: If save fails
        """
        pass

    @abstractmethod
    async def get_recent_messages(self,
                                  limit: int = 100,
                                  offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve recent chat messages.

        Args:
            limit: Maximum messages to return
            offset: Number of messages to skip

        Returns:
            List of dicts with keys:
                - id: int
                - timestamp: int (Unix timestamp)
                - username: str
                - message: str
            Sorted by timestamp descending (most recent first)

        Raises:
            StorageError: If query fails
        """
        pass

    @abstractmethod
    async def clear_old_messages(self, keep_count: int = 1000) -> int:
        """
        Delete old messages, keeping only most recent N.

        Useful for preventing unbounded growth of message logs.

        Args:
            keep_count: Number of recent messages to keep

        Returns:
            Number of messages deleted

        Raises:
            StorageError: If deletion fails
        """
        pass
