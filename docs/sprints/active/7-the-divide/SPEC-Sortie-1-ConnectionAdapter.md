# Sprint 7, Sortie 1: Connection Adapter Interface

**Status:** Planning  
**Estimated Effort:** 4 hours  
**Sprint:** The Divide (Sprint 7)  
**Phase:** 1 - Extract Connection Layer  
**Dependencies:** None (first sortie)

## Objective

Design and implement the abstract `ConnectionAdapter` interface that defines the contract for all platform connection implementations. This interface must be platform-agnostic, enabling future support for Discord, Twitch, Matrix, or other chat platforms.

## Background

Currently, `lib/bot.py` has direct dependencies on `socket_io.py` and CyTube-specific protocol details. This tight coupling prevents:
- Platform portability (can't target other chat systems)
- Testing isolation (can't test bot logic without network)
- Clear separation of concerns (transport mixed with business logic)

## Success Criteria

- ✅ Abstract `ConnectionAdapter` class defined with all required methods
- ✅ Type hints throughout (Python 3.10+)
- ✅ Comprehensive docstrings (Google or NumPy style)
- ✅ Protocol-agnostic method signatures
- ✅ Event normalization schema documented
- ✅ Unit tests for adapter interface validation
- ✅ No CyTube-specific terminology in interface

## Technical Design

### Module Location

```
lib/
└── connection/
    ├── __init__.py          # Exports ConnectionAdapter
    ├── adapter.py           # Abstract base class
    └── errors.py            # Connection-specific exceptions
```

### Abstract Interface

```python
"""
lib/connection/adapter.py

Abstract connection adapter for chat platforms.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Optional, Tuple, Dict, Any
import logging


class ConnectionAdapter(ABC):
    """
    Abstract interface for platform connections.
    
    This interface defines the contract that all connection implementations
    must follow. It abstracts platform-specific details to enable the bot
    to work with multiple chat platforms.
    
    Attributes:
        logger: Logger instance for connection events
        is_connected: Connection status flag
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize connection adapter.
        
        Args:
            logger: Optional logger instance. If None, creates default logger.
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
        4. Set is_connected = True
        
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
        1. Leave channel/room/server
        2. Close network connection
        3. Clean up resources
        4. Set is_connected = False
        
        Should not raise exceptions (best effort cleanup).
        """
        pass
    
    @abstractmethod
    async def send_message(self, content: str, **metadata) -> None:
        """
        Send message to channel/room.
        
        Args:
            content: Message text to send
            **metadata: Platform-specific metadata (formatting, mentions, etc.)
        
        Raises:
            NotConnectedError: If not connected
            SendError: If message fails to send
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
        """
        pass
    
    @abstractmethod
    def on_event(self, event: str, callback: Callable) -> None:
        """
        Register callback for normalized event.
        
        Args:
            event: Normalized event name (e.g., 'message', 'user_join')
            callback: Async or sync callback function(event, data)
        """
        pass
    
    @abstractmethod
    def off_event(self, event: str, callback: Callable) -> None:
        """
        Unregister callback for event.
        
        Args:
            event: Normalized event name
            callback: Previously registered callback
        """
        pass
    
    @abstractmethod
    async def recv_events(self) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """
        Async iterator yielding normalized events.
        
        Yields:
            Tuple of (event_name, event_data)
            
        Example:
            async for event, data in connection.recv_events():
                if event == 'message':
                    print(f"{data['user']}: {data['content']}")
        
        Raises:
            NotConnectedError: If not connected
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._is_connected
    
    @abstractmethod
    async def reconnect(self) -> None:
        """
        Reconnect after disconnection.
        
        Default implementation:
        1. Disconnect if connected
        2. Wait brief period
        3. Connect
        
        Override for platform-specific reconnection logic.
        
        Raises:
            ConnectionError: If reconnection fails
        """
        pass
```

### Connection Errors

```python
"""
lib/connection/errors.py

Connection-specific exceptions.
"""


class ConnectionError(Exception):
    """Base exception for connection errors."""
    pass


class AuthenticationError(ConnectionError):
    """Authentication or login failed."""
    pass


class NotConnectedError(ConnectionError):
    """Operation requires active connection."""
    pass


class SendError(ConnectionError):
    """Failed to send message or data."""
    pass


class UserNotFoundError(ConnectionError):
    """Target user does not exist."""
    pass


class ProtocolError(ConnectionError):
    """Platform protocol violation."""
    pass
```

### Normalized Event Schema

The connection adapter translates platform-specific events into normalized events:

```python
# Platform Event: CyTube "chatMsg"
{
    "username": "alice",
    "msg": "Hello world",
    "time": 1699123456789,
    "meta": {}
}

# Normalized Event: "message"
{
    "event": "message",
    "user": "alice",
    "content": "Hello world",
    "timestamp": 1699123456,
    "platform_data": {  # Original platform-specific data
        "time": 1699123456789,
        "meta": {}
    }
}
```

**Normalized Event Types:**
- `message` - Chat message received
- `user_join` - User joined channel
- `user_leave` - User left channel
- `user_list` - User list updated
- `channel_state` - Channel state changed (topic, settings, etc.)
- `pm` - Private message received
- `connected` - Connection established
- `disconnected` - Connection lost
- `error` - Connection error occurred

## Implementation Steps

1. **Create module structure** (15 min)
   ```bash
   mkdir -p lib/connection
   touch lib/connection/__init__.py
   touch lib/connection/adapter.py
   touch lib/connection/errors.py
   ```

2. **Implement abstract base class** (1 hour)
   - Copy interface code above to `adapter.py`
   - Add comprehensive docstrings
   - Add type hints for all methods
   - Validate with mypy

3. **Implement error classes** (15 min)
   - Copy error code to `errors.py`
   - Add docstrings

4. **Write unit tests** (1.5 hours)
   ```python
   # test/test_connection_adapter.py
   
   import pytest
   from lib.connection import ConnectionAdapter
   from lib.connection.errors import NotConnectedError
   
   
   class MockConnection(ConnectionAdapter):
       """Mock connection for testing."""
       
       async def connect(self):
           self._is_connected = True
       
       async def disconnect(self):
           self._is_connected = False
       
       async def send_message(self, content, **metadata):
           if not self.is_connected:
               raise NotConnectedError("Not connected")
           self.sent_messages.append(content)
       
       # ... implement remaining methods
   
   
   def test_connection_interface():
       """Test connection adapter interface."""
       conn = MockConnection()
       assert not conn.is_connected
   
   
   @pytest.mark.asyncio
   async def test_connect_disconnect():
       """Test connect/disconnect lifecycle."""
       conn = MockConnection()
       await conn.connect()
       assert conn.is_connected
       await conn.disconnect()
       assert not conn.is_connected
   
   
   @pytest.mark.asyncio
   async def test_send_requires_connection():
       """Test send fails when not connected."""
       conn = MockConnection()
       with pytest.raises(NotConnectedError):
           await conn.send_message("test")
   ```

5. **Update lib/__init__.py** (5 min)
   ```python
   from .connection import ConnectionAdapter
   ```

6. **Validate with linters** (15 min)
   ```bash
   mypy lib/connection/
   pylint lib/connection/
   black lib/connection/
   ```

7. **Documentation** (45 min)
   - Add module docstring
   - Add usage examples
   - Document normalized event schema

## Testing Strategy

### Unit Tests

- ✅ Abstract interface can't be instantiated
- ✅ Mock implementation satisfies interface
- ✅ Type hints validate correctly
- ✅ Error classes inherit properly

### Interface Validation Tests

- ✅ All abstract methods present
- ✅ Method signatures correct
- ✅ Return types correct
- ✅ Raises NotImplementedError when not overridden

## Dependencies

**Python Packages:**
- None (pure Python ABC)

**Internal Modules:**
- None (this is the foundation)

## Validation

Before moving to Sortie 2:

1. ✅ `ConnectionAdapter` class defined and importable
2. ✅ All error classes defined
3. ✅ Type checking passes (mypy)
4. ✅ Unit tests pass
5. ✅ Documentation complete
6. ✅ Code review approved

## Risks & Mitigations

**Risk:** Interface too complex  
**Mitigation:** Keep minimal - only essential methods. Extend in future if needed.

**Risk:** Interface too CyTube-specific  
**Mitigation:** Review with Discord/Matrix APIs in mind. Ensure terminology is generic.

**Risk:** Type hints too restrictive  
**Mitigation:** Use `Any` and `Optional` where flexibility needed. Protocol typing if appropriate.

## Open Questions

1. Should `recv_events()` be required, or can `on_event()` suffice?
   - **Decision:** Keep both. `recv_events()` for event loop pattern, `on_event()` for callback pattern.

2. Should reconnection logic be in adapter or external?
   - **Decision:** In adapter. Platform-specific backoff strategies belong with connection logic.

3. How to handle platform-specific features (e.g., CyTube playlist control)?
   - **Decision:** Expose via `metadata` parameter. Document platform-specific extensions.

## Next Steps

After completion, proceed to:
- **Sortie 2:** Implement `CyTubeConnection` concrete adapter
- **Sortie 3:** Integrate connection adapter into `Bot` class

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 7 - The Divide
