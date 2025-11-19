# Sortie 2: Event Bus Core Library

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐☆☆ (Core Architecture)  
**Estimated Time:** 3-4 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 1 (NATS Infrastructure)

---

## Objective

Implement the core EventBus library that wraps NATS client, providing pub/sub, request/reply, and JetStream functionality with automatic reconnection and error handling.

---

## Deliverables

1. ✅ EventBus class with full API
2. ✅ JetStream stream creation and management
3. ✅ Automatic reconnection logic
4. ✅ Error handling and logging
5. ✅ Unit tests (80%+ coverage)
6. ✅ API documentation

---

## Technical Tasks

### Task 2.1: Install Dependencies

**Update:** `requirements.txt` or `pyproject.toml`

```toml
# Add to pyproject.toml
[tool.poetry.dependencies]
nats-py = "^2.7.0"
```

```bash
# Or requirements.txt
nats-py>=2.7.0
```

**Install:**

```powershell
pip install nats-py
# or
poetry add nats-py
```

---

### Task 2.2: Create Event Model

**File:** `bot/rosey/core/events.py`

```python
"""
Event data models for NATS message bus
"""
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json
import uuid


class EventPriority(Enum):
    """Event priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Event:
    """
    Generic event structure for NATS messages
    
    All events flowing through the system use this structure
    for consistency and easy serialization.
    """
    subject: str                           # NATS subject
    event_type: str                        # Event type identifier
    source: str                            # Source service/component
    data: Dict[str, Any]                   # Event payload
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> bytes:
        """
        Serialize event to JSON bytes for NATS
        
        Returns:
            JSON-encoded bytes ready for NATS publish
        """
        d = asdict(self)
        d['priority'] = self.priority.value
        return json.dumps(d, default=str).encode('utf-8')
    
    @classmethod
    def from_json(cls, data: bytes) -> 'Event':
        """
        Deserialize event from JSON bytes
        
        Args:
            data: JSON-encoded bytes from NATS message
            
        Returns:
            Event instance
        """
        d = json.loads(data.decode('utf-8'))
        d['priority'] = EventPriority(d['priority'])
        return cls(**d)
    
    def __repr__(self) -> str:
        return (f"Event(subject={self.subject}, type={self.event_type}, "
                f"source={self.source}, id={self.correlation_id[:8]}...)")


@dataclass
class PlatformEvent(Event):
    """
    Platform-specific event (Cytube, Discord, etc.)
    Includes platform identifier
    """
    platform: str = "unknown"
    
    def __post_init__(self):
        if 'platform' not in self.metadata:
            self.metadata['platform'] = self.platform


@dataclass
class CommandEvent(Event):
    """
    Command execution event
    Includes command details
    """
    command: str = ""
    args: list = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if 'command' not in self.metadata:
            self.metadata['command'] = self.command
```

---

### Task 2.3: Implement EventBus Class

**File:** `bot/rosey/core/event_bus.py`

```python
"""
NATS-based event bus for Rosey
Core message broker abstraction
"""
import asyncio
import logging
from typing import Callable, Optional, Any, Dict
from contextlib import asynccontextmanager

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, RetentionPolicy
from nats.errors import TimeoutError, ConnectionClosedError

from .events import Event

logger = logging.getLogger(__name__)


class EventBusError(Exception):
    """Base exception for event bus errors"""
    pass


class NotConnectedError(EventBusError):
    """Raised when operation requires connection but not connected"""
    pass


class PublishError(EventBusError):
    """Raised when publish fails"""
    pass


class SubscriptionError(EventBusError):
    """Raised when subscription fails"""
    pass


class EventBus:
    """
    NATS-based event bus
    
    Provides:
    - Pub/sub messaging
    - Request/reply pattern
    - JetStream persistence
    - Automatic reconnection
    - Error handling
    
    Example:
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        await bus.subscribe("rosey.events.>", handler)
        await bus.publish("rosey.events.test", {"msg": "hello"})
        
        await bus.disconnect()
    """
    
    def __init__(
        self,
        servers: list[str] = None,
        token: str = None,
        name: str = "rosey-core",
        max_reconnect_attempts: int = -1
    ):
        """
        Initialize event bus
        
        Args:
            servers: List of NATS server URLs
            token: Authentication token
            name: Client name for identification
            max_reconnect_attempts: Max reconnection attempts (-1 = infinite)
        """
        self.servers = servers or ["nats://localhost:4222"]
        self.token = token
        self.name = name
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self.nc: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self._subscriptions: Dict[str, Any] = {}
        self._connected = False
        self._reconnecting = False
        
    @property
    def connected(self) -> bool:
        """Check if connected to NATS"""
        return self._connected and self.nc is not None
    
    async def connect(self):
        """
        Connect to NATS server
        
        Raises:
            EventBusError: If connection fails
        """
        if self.connected:
            logger.warning("Already connected to NATS")
            return
        
        logger.info(f"Connecting to NATS: {self.servers}")
        
        try:
            self.nc = await nats.connect(
                servers=self.servers,
                token=self.token,
                name=self.name,
                # Reconnection settings
                max_reconnect_attempts=self.max_reconnect_attempts,
                reconnect_time_wait=2,
                # Callbacks
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
                closed_cb=self._on_closed,
            )
            
            # Enable JetStream
            self.js = self.nc.jetstream()
            
            # Create streams
            await self._create_streams()
            
            self._connected = True
            logger.info(f"Connected to NATS server (ID: {self.nc._client_id})")
            
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise EventBusError(f"Connection failed: {e}") from e
    
    async def disconnect(self):
        """
        Gracefully disconnect from NATS
        """
        if not self.connected:
            return
        
        logger.info("Disconnecting from NATS...")
        
        try:
            # Drain subscriptions first
            if self.nc:
                await self.nc.drain()
                await self.nc.close()
            
            self._connected = False
            self.nc = None
            self.js = None
            self._subscriptions.clear()
            
            logger.info("Disconnected from NATS")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def _create_streams(self):
        """Create JetStream streams for event persistence"""
        
        streams = [
            {
                "name": "PLATFORM_EVENTS",
                "subjects": ["rosey.platform.>"],
                "retention": RetentionPolicy.LIMITS,
                "max_age": 7 * 24 * 60 * 60,  # 7 days
                "max_bytes": 1024 * 1024 * 1024,  # 1GB
            },
            {
                "name": "COMMANDS",
                "subjects": ["rosey.commands.>"],
                "retention": RetentionPolicy.LIMITS,
                "max_age": 24 * 60 * 60,  # 24 hours
                "max_bytes": 100 * 1024 * 1024,  # 100MB
            },
            {
                "name": "PLUGINS",
                "subjects": ["rosey.plugins.>"],
                "retention": RetentionPolicy.LIMITS,
                "max_age": 24 * 60 * 60,  # 24 hours
                "max_bytes": 100 * 1024 * 1024,  # 100MB
            },
        ]
        
        for stream_config in streams:
            try:
                await self.js.add_stream(
                    name=stream_config["name"],
                    subjects=stream_config["subjects"],
                    retention=stream_config["retention"],
                    max_age=stream_config["max_age"],
                    max_bytes=stream_config["max_bytes"],
                )
                logger.info(f"Created stream: {stream_config['name']}")
            except Exception as e:
                # Stream might already exist
                logger.debug(f"Stream {stream_config['name']} exists or error: {e}")
    
    async def publish(
        self,
        subject: str,
        data: Dict[str, Any],
        source: str = "core",
        event_type: str = None,
        **kwargs
    ):
        """
        Publish event to subject (core pub/sub, no persistence)
        
        Args:
            subject: NATS subject to publish to
            data: Event data payload
            source: Source component identifier
            event_type: Event type (defaults to last part of subject)
            **kwargs: Additional Event fields
            
        Raises:
            NotConnectedError: If not connected to NATS
            PublishError: If publish fails
        """
        if not self.connected:
            raise NotConnectedError("Not connected to NATS")
        
        event = Event(
            subject=subject,
            event_type=event_type or subject.split('.')[-1],
            source=source,
            data=data,
            **kwargs
        )
        
        try:
            await self.nc.publish(subject, event.to_json())
            logger.debug(f"Published to {subject}: {event.event_type}")
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            raise PublishError(f"Publish failed: {e}") from e
    
    async def publish_js(
        self,
        subject: str,
        data: Dict[str, Any],
        source: str = "core",
        event_type: str = None,
        **kwargs
    ):
        """
        Publish to JetStream (guaranteed delivery with persistence)
        
        Args:
            subject: NATS subject
            data: Event data
            source: Source identifier
            event_type: Event type
            **kwargs: Additional Event fields
            
        Returns:
            JetStream ack with sequence number
            
        Raises:
            NotConnectedError: If not connected
            PublishError: If publish fails
        """
        if not self.connected:
            raise NotConnectedError("Not connected to NATS")
        
        event = Event(
            subject=subject,
            event_type=event_type or subject.split('.')[-1],
            source=source,
            data=data,
            **kwargs
        )
        
        try:
            ack = await self.js.publish(subject, event.to_json())
            logger.debug(f"Published to JetStream {subject}: seq={ack.seq}")
            return ack
        except Exception as e:
            logger.error(f"Failed to publish to JetStream {subject}: {e}")
            raise PublishError(f"JetStream publish failed: {e}") from e
    
    async def subscribe(
        self,
        subject: str,
        handler: Callable[[Event], Any],
        queue: str = None
    ):
        """
        Subscribe to subject (core pub/sub)
        
        Args:
            subject: Subject to subscribe (supports wildcards: *, >)
            handler: Async function to handle events
            queue: Queue group name (for load balancing)
            
        Returns:
            Subscription object
            
        Raises:
            NotConnectedError: If not connected
            SubscriptionError: If subscription fails
        """
        if not self.connected:
            raise NotConnectedError("Not connected to NATS")
        
        async def wrapper(msg):
            try:
                event = Event.from_json(msg.data)
                await handler(event)
            except Exception as e:
                logger.error(f"Error handling event on {subject}: {e}", exc_info=True)
        
        try:
            sub = await self.nc.subscribe(subject, queue=queue, cb=wrapper)
            self._subscriptions[subject] = sub
            logger.info(f"Subscribed to {subject}" +
                       (f" (queue: {queue})" if queue else ""))
            return sub
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise SubscriptionError(f"Subscription failed: {e}") from e
    
    async def request(
        self,
        subject: str,
        data: Dict[str, Any],
        timeout: float = 5.0
    ) -> Event:
        """
        Request/reply pattern
        
        Publishes request and waits for response.
        
        Args:
            subject: Request subject
            data: Request data
            timeout: Response timeout in seconds
            
        Returns:
            Response event
            
        Raises:
            NotConnectedError: If not connected
            TimeoutError: If no response within timeout
        """
        if not self.connected:
            raise NotConnectedError("Not connected to NATS")
        
        event = Event(
            subject=subject,
            event_type="request",
            source="core",
            data=data
        )
        
        try:
            response = await self.nc.request(
                subject,
                event.to_json(),
                timeout=timeout
            )
            return Event.from_json(response.data)
        except TimeoutError:
            logger.error(f"Request timeout on {subject}")
            raise
        except Exception as e:
            logger.error(f"Request failed on {subject}: {e}")
            raise
    
    async def reply(self, msg, data: Dict[str, Any]):
        """
        Reply to request message
        
        Args:
            msg: Original NATS message to reply to
            data: Response data
        """
        event = Event(
            subject=msg.subject,
            event_type="response",
            source="core",
            data=data
        )
        await self.nc.publish(msg.reply, event.to_json())
    
    # Callback handlers
    
    async def _on_error(self, e):
        """Handle NATS errors"""
        logger.error(f"NATS error: {e}")
    
    async def _on_disconnected(self):
        """Handle disconnection"""
        logger.warning("Disconnected from NATS")
        self._connected = False
        self._reconnecting = True
    
    async def _on_reconnected(self):
        """Handle reconnection"""
        logger.info("Reconnected to NATS")
        self._connected = True
        self._reconnecting = False
    
    async def _on_closed(self):
        """Handle connection closed"""
        logger.info("NATS connection closed")
        self._connected = False


# Global instance management

_event_bus: Optional[EventBus] = None


async def initialize_event_bus(
    servers: list[str] = None,
    token: str = None,
    **kwargs
) -> EventBus:
    """
    Initialize and connect global event bus
    
    Args:
        servers: NATS server URLs
        token: Auth token
        **kwargs: Additional EventBus args
        
    Returns:
        Connected EventBus instance
    """
    global _event_bus
    
    if _event_bus is not None:
        logger.warning("Event bus already initialized")
        return _event_bus
    
    _event_bus = EventBus(servers=servers, token=token, **kwargs)
    await _event_bus.connect()
    return _event_bus


async def get_event_bus() -> EventBus:
    """
    Get global event bus instance
    
    Returns:
        EventBus instance
        
    Raises:
        RuntimeError: If event bus not initialized
    """
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized. Call initialize_event_bus() first.")
    return _event_bus


async def shutdown_event_bus():
    """Shutdown global event bus"""
    global _event_bus
    
    if _event_bus:
        await _event_bus.disconnect()
        _event_bus = None


@asynccontextmanager
async def event_bus_context(servers: list[str] = None, token: str = None):
    """
    Context manager for event bus lifecycle
    
    Example:
        async with event_bus_context() as bus:
            await bus.publish("test", {"msg": "hello"})
    """
    bus = await initialize_event_bus(servers, token)
    try:
        yield bus
    finally:
        await shutdown_event_bus()
```

---

### Task 2.4: Unit Tests

**File:** `tests/core/test_event_bus.py`

```python
"""
Unit tests for EventBus
"""
import pytest
import asyncio
from bot.rosey.core.event_bus import (
    EventBus,
    initialize_event_bus,
    get_event_bus,
    shutdown_event_bus,
    NotConnectedError,
    event_bus_context
)
from bot.rosey.core.events import Event


@pytest.fixture
async def event_bus():
    """Create and connect event bus for testing"""
    bus = await initialize_event_bus()
    yield bus
    await shutdown_event_bus()


@pytest.mark.asyncio
async def test_connect_disconnect():
    """Test basic connection lifecycle"""
    bus = EventBus()
    assert not bus.connected
    
    await bus.connect()
    assert bus.connected
    
    await bus.disconnect()
    assert not bus.connected


@pytest.mark.asyncio
async def test_publish_subscribe(event_bus):
    """Test pub/sub messaging"""
    received = []
    
    async def handler(event):
        received.append(event)
    
    await event_bus.subscribe("test.hello", handler)
    await event_bus.publish("test.hello", {"msg": "world"})
    
    await asyncio.sleep(0.1)  # Allow message delivery
    
    assert len(received) == 1
    assert received[0].data["msg"] == "world"
    assert received[0].event_type == "hello"


@pytest.mark.asyncio
async def test_wildcard_subscription(event_bus):
    """Test wildcard subscriptions"""
    received = []
    
    async def handler(event):
        received.append(event)
    
    await event_bus.subscribe("test.>", handler)
    
    await event_bus.publish("test.one", {"id": 1})
    await event_bus.publish("test.two", {"id": 2})
    await event_bus.publish("other.three", {"id": 3})
    
    await asyncio.sleep(0.1)
    
    assert len(received) == 2
    assert received[0].data["id"] == 1
    assert received[1].data["id"] == 2


@pytest.mark.asyncio
async def test_request_reply(event_bus):
    """Test request/reply pattern"""
    
    async def handler(event):
        # Simulate processing
        await asyncio.sleep(0.1)
        return {"result": event.data["input"] * 2}
    
    # In real implementation, handler would use msg.reply
    # For testing, we use request which handles both sides
    
    # This test requires a running NATS server
    # Simplified for demonstration
    pass  # TODO: Implement with mock


@pytest.mark.asyncio
async def test_publish_not_connected():
    """Test publishing when not connected raises error"""
    bus = EventBus()
    
    with pytest.raises(NotConnectedError):
        await bus.publish("test", {})


@pytest.mark.asyncio
async def test_context_manager():
    """Test context manager"""
    async with event_bus_context() as bus:
        assert bus.connected
        await bus.publish("test", {"msg": "hello"})
    
    # Should be disconnected after context
    bus = await get_event_bus()
    # Event bus is shut down, should raise
    with pytest.raises(RuntimeError):
        await get_event_bus()


@pytest.mark.asyncio
async def test_event_serialization():
    """Test Event to/from JSON"""
    event = Event(
        subject="test.event",
        event_type="test",
        source="unit-test",
        data={"key": "value", "number": 42}
    )
    
    # Serialize
    json_bytes = event.to_json()
    assert isinstance(json_bytes, bytes)
    
    # Deserialize
    restored = Event.from_json(json_bytes)
    assert restored.subject == event.subject
    assert restored.event_type == event.event_type
    assert restored.source == event.source
    assert restored.data == event.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Run tests:**

```powershell
# Ensure NATS server is running
cd infrastructure\nats
.\start-nats.bat

# In another terminal, run tests
pytest tests/core/test_event_bus.py -v
```

---

## Documentation

Create `docs/architecture/EVENT-BUS-API.md`:

```markdown
# Event Bus API Reference

## Overview

The EventBus class provides a high-level interface to NATS messaging.

## Quick Start

```python
from bot.rosey.core.event_bus import initialize_event_bus, get_event_bus

# Initialize
bus = await initialize_event_bus(servers=["nats://localhost:4222"])

# Publish
await bus.publish("rosey.events.message", {"text": "Hello"})

# Subscribe
async def handler(event):
    print(f"Got: {event.data}")

await bus.subscribe("rosey.events.>", handler)
```

## API Methods

### Connection

- `await bus.connect()` - Connect to NATS
- `await bus.disconnect()` - Graceful disconnect
- `bus.connected` - Check connection status

### Publishing

- `await bus.publish(subject, data, ...)` - Pub/sub (no persistence)
- `await bus.publish_js(subject, data, ...)` - JetStream (guaranteed)

### Subscribing

- `await bus.subscribe(subject, handler, queue=None)` - Subscribe to subject
- Supports wildcards: `*` (one token), `>` (one or more tokens)

### Request/Reply

- `response = await bus.request(subject, data, timeout=5.0)` - Send request
- `await bus.reply(msg, data)` - Reply to request

## Event Structure

```python
@dataclass
class Event:
    subject: str
    event_type: str
    source: str
    data: Dict[str, Any]
    timestamp: str
    correlation_id: str
    priority: EventPriority
    metadata: Dict[str, Any]
```

## Error Handling

- `NotConnectedError` - Not connected when operation requires connection
- `PublishError` - Publish operation failed
- `SubscriptionError` - Subscribe operation failed
- `TimeoutError` - Request timeout (from nats-py)

## Best Practices

1. Use context manager for automatic cleanup
2. Always await publish operations
3. Use JetStream for critical events
4. Handle reconnection in subscribers
5. Use correlation_id for request tracking
```

---

## Success Criteria

✅ EventBus class fully implemented  
✅ Pub/sub working  
✅ Request/reply working  
✅ JetStream streams created  
✅ Automatic reconnection functional  
✅ Unit tests passing (80%+ coverage)  
✅ API documentation complete  

---

## Time Breakdown

- Event model: 30 minutes
- EventBus class: 2 hours
- Unit tests: 45 minutes
- Documentation: 30 minutes

**Total: 3.75 hours**

---

## Next Steps

- → Sortie 3: Subject Design & Event Model
- → Define complete subject hierarchy
- → Create subject constants
