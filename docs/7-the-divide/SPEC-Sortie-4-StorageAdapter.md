# Sprint 7, Sortie 4: Storage Adapter Interface

**Status:** Planning  
**Estimated Effort:** 4 hours  
**Sprint:** The Divide (Sprint 7)  
**Phase:** 2 - Extract Storage Layer  
**Dependencies:** Sortie 3 (Bot Integration complete)

## Objective

Design and implement the abstract `StorageAdapter` interface that defines the contract for all storage implementations. This interface must be database-agnostic, enabling future support for PostgreSQL, Redis, or other storage backends.

## Background

Currently, `common/database.py` contains `BotDatabase` class with direct SQLite dependencies. This tight coupling prevents:
- Database portability (can't swap SQLite for PostgreSQL)
- Testing isolation (can't test bot logic without database)
- Horizontal scaling (SQLite doesn't support concurrent writes well)
- Clear separation of concerns (SQL details mixed with business logic)

## Success Criteria

- ✅ Abstract `StorageAdapter` class defined with all required methods
- ✅ Type hints throughout (Python 3.10+)
- ✅ Comprehensive docstrings
- ✅ Database-agnostic method signatures
- ✅ Async-first API (ready for async database drivers)
- ✅ Unit tests for adapter interface validation
- ✅ No SQLite-specific terminology in interface

## Technical Design

### Module Location

```
lib/
└── storage/
    ├── __init__.py          # Exports StorageAdapter
    ├── adapter.py           # Abstract base class
    └── errors.py            # Storage-specific exceptions
```

### Abstract Interface

```python
"""
lib/storage/adapter.py

Abstract storage adapter for data persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging


class StorageAdapter(ABC):
    """
    Abstract interface for data storage.
    
    This interface defines the contract that all storage implementations
    must follow. It abstracts database-specific details to enable the bot
    to work with multiple storage backends.
    
    Attributes:
        logger: Logger instance for storage events
        is_connected: Storage connection status
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
        3. Set is_connected = True
        
        Raises:
            StorageError: If connection fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close storage connection.
        
        This method should:
        1. Commit any pending transactions
        2. Close database connection
        3. Clean up resources
        4. Set is_connected = False
        
        Should not raise exceptions (best effort cleanup).
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if storage is connected."""
        return self._is_connected
    
    # User Statistics
    
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
        
        Args:
            username: Username
            first_seen: Unix timestamp of first appearance
            last_seen: Unix timestamp of last activity
            chat_lines: Total chat messages sent
            time_connected: Total seconds connected
            session_start: Unix timestamp of current session start
        
        Raises:
            StorageError: If save fails
        """
        pass
    
    @abstractmethod
    async def get_user_stats(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve statistics for user.
        
        Args:
            username: Username to lookup
        
        Returns:
            Dict with keys: username, first_seen, last_seen, total_chat_lines,
            total_time_connected, current_session_start
            None if user not found
        
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
            limit: Maximum number of users to return
            offset: Number of users to skip (for pagination)
        
        Returns:
            List of user stat dicts
        
        Raises:
            StorageError: If query fails
        """
        pass
    
    # User Actions / Logs
    
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
            action_type: Type of action (e.g., 'join', 'leave', 'pm')
            details: Optional action details (JSON string)
            timestamp: Optional timestamp (defaults to now)
        
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
            List of action dicts with keys: id, timestamp, username,
            action_type, details
        
        Raises:
            StorageError: If query fails
        """
        pass
    
    # Channel Statistics
    
    @abstractmethod
    async def update_channel_stats(self,
                                   max_users: Optional[int] = None,
                                   max_connected: Optional[int] = None,
                                   timestamp: Optional[int] = None) -> None:
        """
        Update channel-level statistics.
        
        Args:
            max_users: New maximum chat user count
            max_connected: New maximum connected user count
            timestamp: Timestamp of new maximum
        
        Raises:
            StorageError: If update fails
        """
        pass
    
    @abstractmethod
    async def get_channel_stats(self) -> Dict[str, Any]:
        """
        Retrieve channel statistics.
        
        Returns:
            Dict with keys: max_users, max_users_timestamp, max_connected,
            max_connected_timestamp, last_updated
        
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
        
        Args:
            chat_users: Number of users in chat
            connected_users: Number of connected users
            timestamp: Optional timestamp (defaults to now)
        
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
            start_time: Filter >= this timestamp
            end_time: Filter <= this timestamp
            limit: Maximum records to return
        
        Returns:
            List of dicts with keys: id, timestamp, chat_users, connected_users
        
        Raises:
            StorageError: If query fails
        """
        pass
    
    # Chat Messages
    
    @abstractmethod
    async def save_message(self,
                          username: str,
                          message: str,
                          timestamp: Optional[int] = None) -> None:
        """
        Store chat message (for recent chat cache).
        
        Args:
            username: Username who sent message
            message: Message text
            timestamp: Optional timestamp (defaults to now)
        
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
            List of dicts with keys: id, timestamp, username, message
        
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def clear_old_messages(self, keep_count: int = 1000) -> int:
        """
        Delete old messages, keeping only most recent N.
        
        Args:
            keep_count: Number of recent messages to keep
        
        Returns:
            Number of messages deleted
        
        Raises:
            StorageError: If deletion fails
        """
        pass
```

### Storage Errors

```python
"""
lib/storage/errors.py

Storage-specific exceptions.
"""


class StorageError(Exception):
    """Base exception for storage errors."""
    pass


class ConnectionError(StorageError):
    """Storage connection failed."""
    pass


class QueryError(StorageError):
    """Query execution failed."""
    pass


class MigrationError(StorageError):
    """Schema migration failed."""
    pass


class IntegrityError(StorageError):
    """Data integrity violation."""
    pass
```

## Implementation Steps

1. **Create module structure** (15 min)
   ```bash
   mkdir -p lib/storage
   touch lib/storage/__init__.py
   touch lib/storage/adapter.py
   touch lib/storage/errors.py
   ```

2. **Implement abstract base class** (1.5 hours)
   - Copy interface code to `adapter.py`
   - Add comprehensive docstrings
   - Add type hints for all methods
   - Validate with mypy

3. **Implement error classes** (15 min)
   - Copy error code to `errors.py`
   - Add docstrings

4. **Write unit tests** (1.5 hours)
   ```python
   # test/test_storage_adapter.py
   
   import pytest
   from lib.storage import StorageAdapter
   from lib.storage.errors import StorageError
   
   
   class MockStorage(StorageAdapter):
       """Mock storage for testing."""
       
       def __init__(self):
           super().__init__()
           self.data = {}
       
       async def connect(self):
           self._is_connected = True
       
       async def close(self):
           self._is_connected = False
       
       async def save_user_stats(self, username, **kwargs):
           if not self.is_connected:
               raise StorageError("Not connected")
           self.data[username] = kwargs
       
       async def get_user_stats(self, username):
           return self.data.get(username)
       
       # ... implement remaining methods
   
   
   def test_storage_interface():
       """Test storage adapter interface."""
       storage = MockStorage()
       assert not storage.is_connected
   
   
   @pytest.mark.asyncio
   async def test_connect_disconnect():
       """Test connect/disconnect lifecycle."""
       storage = MockStorage()
       await storage.connect()
       assert storage.is_connected
       await storage.close()
       assert not storage.is_connected
   
   
   @pytest.mark.asyncio
   async def test_save_requires_connection():
       """Test operations require connection."""
       storage = MockStorage()
       with pytest.raises(StorageError):
           await storage.save_user_stats("test", first_seen=123)
   ```

5. **Update lib/__init__.py** (5 min)
   ```python
   from .storage import StorageAdapter
   ```

6. **Validate with linters** (15 min)
   ```bash
   mypy lib/storage/
   pylint lib/storage/
   black lib/storage/
   ```

7. **Documentation** (30 min)
   - Add module docstring
   - Add usage examples
   - Document async patterns

## Testing Strategy

### Unit Tests

- ✅ Abstract interface can't be instantiated
- ✅ Mock implementation satisfies interface
- ✅ Type hints validate correctly
- ✅ Error classes inherit properly
- ✅ All abstract methods present

### Interface Validation Tests

- ✅ All abstract methods must be implemented
- ✅ Method signatures correct
- ✅ Return types correct
- ✅ Async methods properly defined

## Dependencies

**Python Packages:**
- None (pure Python ABC)

**Internal Modules:**
- None (this is foundation for storage layer)

## Validation

Before moving to Sortie 5:

1. ✅ `StorageAdapter` class defined and importable
2. ✅ All error classes defined
3. ✅ Type checking passes (mypy)
4. ✅ Unit tests pass
5. ✅ Documentation complete
6. ✅ Code review approved

## Risks & Mitigations

**Risk:** Interface too complex  
**Mitigation:** Only include methods used by current BotDatabase. Can extend later.

**Risk:** Interface too SQLite-specific  
**Mitigation:** Review with PostgreSQL/Redis APIs in mind. Use generic terminology.

**Risk:** Async overhead  
**Mitigation:** Async is necessary for future scalability. Minimal overhead with aiosqlite.

## Open Questions

1. Should we support transactions explicitly?
   - **Decision:** Not in v1. Can add `begin_transaction()`, `commit()`, `rollback()` later if needed.

2. Should we support bulk operations?
   - **Decision:** Not initially. Single operations sufficient for current use case.

3. How to handle schema migrations?
   - **Decision:** Each implementation handles its own migrations (Alembic for SQLite, etc.)

## Next Steps

After completion, proceed to:
- **Sortie 5:** Implement SQLiteStorage with Alembic migrations
- **Sortie 6:** Integrate storage adapter into Bot class

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 7 - The Divide
