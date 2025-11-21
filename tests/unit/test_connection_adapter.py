"""
Unit tests for ConnectionAdapter abstract interface.

Tests verify the abstract base class contract and demonstrate
usage with a mock implementation.
"""

import pytest
import asyncio
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock

from lib.connection import (
    ConnectionAdapter,
    ConnectionError,
    AuthenticationError,
    NotConnectedError,
    SendError,
    UserNotFoundError,
    ProtocolError,
)


class MockConnection(ConnectionAdapter):
    """
    Mock connection implementation for testing.
    
    Provides a concrete implementation of ConnectionAdapter that
    tracks all method calls and allows simulating various scenarios.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_messages: List[Tuple[str, Dict[str, Any]]] = []
        self.sent_pms: List[Tuple[str, str]] = []
        self.event_callbacks: Dict[str, List] = {}
        self.connect_count = 0
        self.disconnect_count = 0
        self.reconnect_count = 0
        self._should_fail_connect = False
        self._should_fail_auth = False
        self._event_queue: List[Tuple[str, Dict[str, Any]]] = []
        
    async def connect(self) -> None:
        """Connect to mock platform."""
        self.connect_count += 1
        if self._should_fail_connect:
            raise ConnectionError("Connection failed")
        if self._should_fail_auth:
            raise AuthenticationError("Invalid credentials")
        await asyncio.sleep(0.01)  # Simulate network delay
        self._is_connected = True
        self.logger.info("Connected to mock platform")
        
    async def disconnect(self) -> None:
        """Disconnect from mock platform."""
        self.disconnect_count += 1
        self._is_connected = False
        self.logger.info("Disconnected from mock platform")
        
    async def send_message(self, content: str, **metadata) -> None:
        """Send message to mock channel."""
        if not self.is_connected:
            raise NotConnectedError("Not connected")
        self.sent_messages.append((content, metadata))
        self.logger.debug(f"Sent message: {content}")
        
    async def send_pm(self, user: str, content: str) -> None:
        """Send private message to mock user."""
        if not self.is_connected:
            raise NotConnectedError("Not connected")
        if user == "nonexistent":
            raise UserNotFoundError(f"User {user} not found")
        self.sent_pms.append((user, content))
        self.logger.debug(f"Sent PM to {user}: {content}")
        
    def on_event(self, event: str, callback) -> None:
        """Register event callback."""
        if event not in self.event_callbacks:
            self.event_callbacks[event] = []
        self.event_callbacks[event].append(callback)
        
    def off_event(self, event: str, callback) -> None:
        """Unregister event callback."""
        if event in self.event_callbacks and callback in self.event_callbacks[event]:
            self.event_callbacks[event].remove(callback)
            
    async def recv_events(self):
        """Yield events from queue."""
        if not self.is_connected:
            raise NotConnectedError("Not connected")
        while self._event_queue:
            yield self._event_queue.pop(0)
            await asyncio.sleep(0.001)  # Yield control
            
    async def reconnect(self) -> None:
        """Reconnect to mock platform."""
        self.reconnect_count += 1
        if self.is_connected:
            await self.disconnect()
        await asyncio.sleep(0.1)  # Simulate backoff
        await self.connect()
        
    def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Helper to emit event to registered callbacks."""
        self._event_queue.append((event, data))
        if event in self.event_callbacks:
            for callback in self.event_callbacks[event]:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event, data))
                else:
                    callback(event, data)


class TestConnectionAdapter:
    """Test suite for ConnectionAdapter abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that ConnectionAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ConnectionAdapter()
    
    def test_mock_implementation_instantiates(self):
        """Test that concrete implementation can be instantiated."""
        conn = MockConnection()
        assert isinstance(conn, ConnectionAdapter)
        assert not conn.is_connected
        
    def test_logger_initialization(self):
        """Test logger is initialized correctly."""
        conn = MockConnection()
        assert conn.logger is not None
        assert conn.logger.name == "MockConnection"
        
    def test_custom_logger(self):
        """Test custom logger can be provided."""
        import logging
        custom_logger = logging.getLogger("test")
        conn = MockConnection(logger=custom_logger)
        assert conn.logger is custom_logger


class TestConnectionLifecycle:
    """Test connection lifecycle methods."""
    
    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connect establishes connection."""
        conn = MockConnection()
        assert not conn.is_connected
        await conn.connect()
        assert conn.is_connected
        assert conn.connect_count == 1
        
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect closes connection."""
        conn = MockConnection()
        await conn.connect()
        assert conn.is_connected
        await conn.disconnect()
        assert not conn.is_connected
        assert conn.disconnect_count == 1
        
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connect handles failures."""
        conn = MockConnection()
        conn._should_fail_connect = True
        with pytest.raises(ConnectionError):
            await conn.connect()
        assert not conn.is_connected
        
    @pytest.mark.asyncio
    async def test_authentication_failure(self):
        """Test connect handles authentication failures."""
        conn = MockConnection()
        conn._should_fail_auth = True
        with pytest.raises(AuthenticationError):
            await conn.connect()
        assert not conn.is_connected
        
    @pytest.mark.asyncio
    async def test_reconnect(self):
        """Test reconnect restores connection."""
        conn = MockConnection()
        await conn.connect()
        await conn.disconnect()
        assert not conn.is_connected
        await conn.reconnect()
        assert conn.is_connected
        assert conn.reconnect_count == 1


class TestMessageSending:
    """Test message sending functionality."""
    
    @pytest.mark.asyncio
    async def test_send_message_requires_connection(self):
        """Test send_message fails when not connected."""
        conn = MockConnection()
        with pytest.raises(NotConnectedError):
            await conn.send_message("test")
            
    @pytest.mark.asyncio
    async def test_send_message_when_connected(self):
        """Test send_message works when connected."""
        conn = MockConnection()
        await conn.connect()
        await conn.send_message("Hello world")
        assert len(conn.sent_messages) == 1
        assert conn.sent_messages[0][0] == "Hello world"
        
    @pytest.mark.asyncio
    async def test_send_message_with_metadata(self):
        """Test send_message includes metadata."""
        conn = MockConnection()
        await conn.connect()
        await conn.send_message("Test", meta={"key": "value"}, flag=True)
        assert len(conn.sent_messages) == 1
        content, metadata = conn.sent_messages[0]
        assert content == "Test"
        assert metadata["meta"] == {"key": "value"}
        assert metadata["flag"] is True
        
    @pytest.mark.asyncio
    async def test_send_pm_requires_connection(self):
        """Test send_pm fails when not connected."""
        conn = MockConnection()
        with pytest.raises(NotConnectedError):
            await conn.send_pm("alice", "test")
            
    @pytest.mark.asyncio
    async def test_send_pm_when_connected(self):
        """Test send_pm works when connected."""
        conn = MockConnection()
        await conn.connect()
        await conn.send_pm("alice", "Private message")
        assert len(conn.sent_pms) == 1
        assert conn.sent_pms[0] == ("alice", "Private message")
        
    @pytest.mark.asyncio
    async def test_send_pm_to_nonexistent_user(self):
        """Test send_pm handles nonexistent user."""
        conn = MockConnection()
        await conn.connect()
        with pytest.raises(UserNotFoundError):
            await conn.send_pm("nonexistent", "test")


class TestEventHandling:
    """Test event handling functionality."""
    
    def test_register_event_callback(self):
        """Test on_event registers callback."""
        conn = MockConnection()
        callback = Mock()
        conn.on_event("message", callback)
        assert "message" in conn.event_callbacks
        assert callback in conn.event_callbacks["message"]
        
    def test_unregister_event_callback(self):
        """Test off_event unregisters callback."""
        conn = MockConnection()
        callback = Mock()
        conn.on_event("message", callback)
        conn.off_event("message", callback)
        assert callback not in conn.event_callbacks.get("message", [])
        
    def test_multiple_callbacks_per_event(self):
        """Test multiple callbacks can be registered for same event."""
        conn = MockConnection()
        callback1 = Mock()
        callback2 = Mock()
        conn.on_event("message", callback1)
        conn.on_event("message", callback2)
        assert len(conn.event_callbacks["message"]) == 2
        
    @pytest.mark.asyncio
    async def test_recv_events_requires_connection(self):
        """Test recv_events fails when not connected."""
        conn = MockConnection()
        with pytest.raises(NotConnectedError):
            async for _ in conn.recv_events():
                pass
                
    @pytest.mark.asyncio
    async def test_recv_events_yields_events(self):
        """Test recv_events yields queued events."""
        conn = MockConnection()
        await conn.connect()
        
        # Queue some events
        conn._event_queue.append(("message", {"user": "alice", "content": "hi"}))
        conn._event_queue.append(("user_join", {"user": "bob"}))
        
        # Consume events
        events = []
        async for event, data in conn.recv_events():
            events.append((event, data))
            if len(events) >= 2:
                break
                
        assert len(events) == 2
        assert events[0][0] == "message"
        assert events[0][1]["user"] == "alice"
        assert events[1][0] == "user_join"
        assert events[1][1]["user"] == "bob"


class TestErrorHierarchy:
    """Test connection error class hierarchy."""
    
    def test_connection_error_inheritance(self):
        """Test all errors inherit from ConnectionError."""
        assert issubclass(AuthenticationError, ConnectionError)
        assert issubclass(NotConnectedError, ConnectionError)
        assert issubclass(SendError, ConnectionError)
        assert issubclass(UserNotFoundError, ConnectionError)
        assert issubclass(ProtocolError, ConnectionError)
        
    def test_errors_can_be_raised(self):
        """Test errors can be raised and caught."""
        with pytest.raises(ConnectionError):
            raise AuthenticationError("test")
            
        with pytest.raises(ConnectionError):
            raise NotConnectedError("test")
            
    def test_specific_error_handling(self):
        """Test specific errors can be caught individually."""
        try:
            raise AuthenticationError("Invalid credentials")
        except AuthenticationError as e:
            assert str(e) == "Invalid credentials"
        except ConnectionError:
            pytest.fail("Should catch AuthenticationError specifically")


class TestNormalizedEvents:
    """Test normalized event schema."""
    
    @pytest.mark.asyncio
    async def test_message_event_schema(self):
        """Test normalized message event has correct schema."""
        conn = MockConnection()
        await conn.connect()
        
        message_event = {
            "user": "alice",
            "content": "Hello world",
            "timestamp": 1699123456,
            "platform_data": {}
        }
        conn._event_queue.append(("message", message_event))
        
        async for event, data in conn.recv_events():
            assert event == "message"
            assert "user" in data
            assert "content" in data
            assert "timestamp" in data
            break
            
    @pytest.mark.asyncio
    async def test_user_join_event_schema(self):
        """Test normalized user_join event has correct schema."""
        conn = MockConnection()
        await conn.connect()
        
        join_event = {
            "user": "bob",
            "timestamp": 1699123456,
            "platform_data": {}
        }
        conn._event_queue.append(("user_join", join_event))
        
        async for event, data in conn.recv_events():
            assert event == "user_join"
            assert "user" in data
            break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
