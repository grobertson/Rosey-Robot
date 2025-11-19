"""
Unit tests for EventBus and Event
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from bot.rosey.core.event_bus import (
    Event,
    Priority,
    EventBus,
    initialize_event_bus,
    get_event_bus,
    shutdown_event_bus,
)


class TestEvent:
    """Test Event dataclass"""
    
    def test_event_creation(self):
        """Test creating event with required fields"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"}
        )
        
        assert event.subject == "rosey.test"
        assert event.event_type == "test.event"
        assert event.source == "test"
        assert event.data["key"] == "value"
        assert event.correlation_id is not None
        assert event.timestamp is not None
        assert event.priority == Priority.NORMAL
        assert event.metadata == {}
    
    def test_event_with_all_fields(self):
        """Test creating event with all fields"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"},
            correlation_id="test-123",
            timestamp=1234567890.0,
            priority=Priority.HIGH,
            metadata={"extra": "info"}
        )
        
        assert event.correlation_id == "test-123"
        assert event.timestamp == 1234567890.0
        assert event.priority == Priority.HIGH
        assert event.metadata["extra"] == "info"
    
    def test_event_priority_enum(self):
        """Test priority enum values"""
        assert Priority.LOW.value == 1
        assert Priority.NORMAL.value == 2
        assert Priority.HIGH.value == 3
        assert Priority.CRITICAL.value == 4
    
    def test_event_to_dict(self):
        """Test event serialization to dict"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"}
        )
        
        data = event.to_dict()
        
        assert data["subject"] == "rosey.test"
        assert data["event_type"] == "test.event"
        assert data["source"] == "test"
        assert data["data"]["key"] == "value"
        assert "correlation_id" in data
        assert "timestamp" in data
        assert data["priority"] == Priority.NORMAL.value  # Enum converted to int
        assert "metadata" in data
    
    def test_event_to_json(self):
        """Test event serialization to JSON"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"}
        )
        
        json_str = event.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["subject"] == "rosey.test"
        assert parsed["data"]["key"] == "value"
    
    def test_event_from_dict(self):
        """Test event deserialization from dict"""
        data = {
            "subject": "rosey.test",
            "event_type": "test.event",
            "source": "test",
            "data": {"key": "value"},
            "correlation_id": "test-123",
            "timestamp": 1234567890.0,
            "priority": Priority.HIGH.value,
            "metadata": {}
        }
        
        event = Event.from_dict(data)
        
        assert event.subject == "rosey.test"
        assert event.event_type == "test.event"
        assert event.correlation_id == "test-123"
        assert event.priority == Priority.HIGH
    
    def test_event_from_json(self):
        """Test event deserialization from JSON"""
        json_str = json.dumps({
            "subject": "rosey.test",
            "event_type": "test.event",
            "source": "test",
            "data": {"key": "value"},
            "correlation_id": "test-123",
            "timestamp": 1234567890.0,
            "priority": 2,
            "metadata": {}
        })
        
        event = Event.from_json(json_str)
        
        assert event.subject == "rosey.test"
        assert event.data["key"] == "value"
        assert event.priority == Priority.NORMAL
    
    def test_event_roundtrip(self):
        """Test serialization roundtrip (dict -> Event -> dict)"""
        original = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value", "nested": {"a": 1}}
        )
        
        # Convert to dict and back
        data = original.to_dict()
        restored = Event.from_dict(data)
        
        assert restored.subject == original.subject
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.data == original.data
        assert restored.correlation_id == original.correlation_id
        assert restored.timestamp == original.timestamp


@pytest.mark.asyncio
class TestEventBus:
    """Test EventBus class"""
    
    @pytest.fixture
    async def mock_nats(self):
        """Mock NATS client"""
        nc = AsyncMock()
        nc.is_connected = True
        nc.jetstream = Mock(return_value=AsyncMock())
        nc.drain = AsyncMock()
        nc.close = AsyncMock()
        nc.publish = AsyncMock()
        nc.subscribe = AsyncMock()
        nc.request = AsyncMock()
        return nc
    
    @pytest.fixture
    async def event_bus(self, mock_nats):
        """Create EventBus with mocked NATS"""
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            await bus.connect()
            return bus
    
    async def test_connect(self, mock_nats):
        """Test connecting to NATS"""
        with patch('nats.connect', return_value=mock_nats) as mock_connect:
            bus = EventBus(servers=["nats://localhost:4222"])
            await bus.connect()
            
            assert bus.is_connected()
            mock_connect.assert_called_once()
    
    async def test_connect_already_connected(self, event_bus):
        """Test connecting when already connected"""
        # Should not raise error, just log warning
        await event_bus.connect()
        assert event_bus.is_connected()
    
    async def test_disconnect(self, event_bus, mock_nats):
        """Test disconnecting from NATS"""
        await event_bus.disconnect()
        
        assert not event_bus.is_connected()
        mock_nats.drain.assert_called_once()
        mock_nats.close.assert_called_once()
    
    async def test_publish(self, event_bus, mock_nats):
        """Test publishing event"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"message": "hello"}
        )
        
        await event_bus.publish(event)
        
        # Verify NATS publish was called
        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        
        # Check subject
        assert call_args[0][0] == "rosey.test"
        
        # Check payload is valid JSON with event data
        payload = call_args[0][1]
        parsed = json.loads(payload.decode('utf-8'))
        assert parsed["subject"] == "rosey.test"
        assert parsed["data"]["message"] == "hello"
    
    async def test_publish_not_connected(self, mock_nats):
        """Test publishing when not connected raises error"""
        bus = EventBus(servers=["nats://localhost:4222"])
        
        event = Event(
            subject="rosey.test",
            event_type="test",
            source="test",
            data={}
        )
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await bus.publish(event)
    
    async def test_publish_js(self, event_bus, mock_nats):
        """Test publishing with JetStream"""
        mock_js = mock_nats.jetstream.return_value
        mock_js.publish = AsyncMock(return_value=Mock(seq=1, stream="TEST"))
        
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"message": "hello"}
        )
        
        ack = await event_bus.publish_js(event)
        
        # Verify JetStream publish was called
        mock_js.publish.assert_called_once()
        assert ack is not None
    
    async def test_subscribe(self, event_bus, mock_nats):
        """Test subscribing to subject"""
        callback = AsyncMock()
        
        await event_bus.subscribe("rosey.test.>", callback)
        
        # Verify NATS subscribe was called
        mock_nats.subscribe.assert_called_once()
        call_args = mock_nats.subscribe.call_args
        assert call_args[0][0] == "rosey.test.>"
    
    async def test_subscribe_with_queue(self, event_bus, mock_nats):
        """Test subscribing with queue group"""
        callback = AsyncMock()
        
        await event_bus.subscribe("rosey.test.>", callback, queue="workers")
        
        call_args = mock_nats.subscribe.call_args
        assert call_args[1]["queue"] == "workers"
    
    async def test_subscribe_callback_invoked(self, event_bus, mock_nats):
        """Test subscription callback is invoked with Event"""
        received_events = []
        
        async def callback(event):
            received_events.append(event)
        
        # Setup mock subscription
        mock_sub = Mock()
        mock_sub._id = 1
        mock_nats.subscribe.return_value = mock_sub
        
        await event_bus.subscribe("rosey.test.>", callback)
        
        # Get the wrapper callback that was registered
        wrapper_callback = mock_nats.subscribe.call_args[1]["cb"]
        
        # Simulate NATS message
        mock_msg = Mock()
        event = Event(
            subject="rosey.test.event",
            event_type="test",
            source="test",
            data={"value": 42}
        )
        mock_msg.data = event.to_json().encode('utf-8')
        
        # Call wrapper
        await wrapper_callback(mock_msg)
        
        # Verify callback was invoked with Event object
        assert len(received_events) == 1
        assert received_events[0].data["value"] == 42
    
    async def test_unsubscribe(self, event_bus, mock_nats):
        """Test unsubscribing from subject"""
        callback = AsyncMock()
        
        # Subscribe first
        mock_sub = Mock()
        mock_sub._id = 1
        mock_nats.subscribe.return_value = mock_sub
        
        await event_bus.subscribe("rosey.test.>", callback)
        
        # Unsubscribe
        await event_bus.unsubscribe("rosey.test.>")
        
        # Should be removed from tracking
        assert "rosey.test.>" not in event_bus._subscriptions
    
    async def test_request(self, event_bus, mock_nats):
        """Test request/reply pattern"""
        # Mock NATS request
        mock_response = Mock()
        mock_response.data = json.dumps({"result": "success"}).encode('utf-8')
        mock_nats.request = AsyncMock(return_value=mock_response)
        
        response = await event_bus.request(
            "rosey.test.request",
            {"action": "test"}
        )
        
        assert response["result"] == "success"
        mock_nats.request.assert_called_once()
    
    async def test_request_timeout(self, event_bus, mock_nats):
        """Test request timeout"""
        mock_nats.request = AsyncMock(side_effect=asyncio.TimeoutError())
        
        with pytest.raises(TimeoutError):
            await event_bus.request(
                "rosey.test.request",
                {"action": "test"},
                timeout=1.0
            )
    
    async def test_reply(self, event_bus, mock_nats):
        """Test sending reply"""
        mock_msg = Mock()
        mock_msg.reply = "reply.subject.123"
        
        await event_bus.reply(mock_msg, {"status": "ok"})
        
        # Verify publish to reply subject
        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        assert call_args[0][0] == "reply.subject.123"
    
    async def test_create_stream(self, event_bus, mock_nats):
        """Test creating JetStream stream"""
        mock_js = mock_nats.jetstream.return_value
        mock_js.add_stream = AsyncMock()
        
        await event_bus.create_stream(
            name="TEST_STREAM",
            subjects=["rosey.test.>"],
            max_msgs=1000
        )
        
        mock_js.add_stream.assert_called_once()
        call_args = mock_js.add_stream.call_args[1]
        assert call_args["name"] == "TEST_STREAM"
        assert "rosey.test.>" in call_args["subjects"]
    
    async def test_connection_callbacks(self, mock_nats):
        """Test connection callbacks are registered"""
        on_connect_called = False
        on_disconnect_called = False
        on_error_called = False
        
        def on_connect():
            nonlocal on_connect_called
            on_connect_called = True
        
        def on_disconnect():
            nonlocal on_disconnect_called
            on_disconnect_called = True
        
        def on_error(e):
            nonlocal on_error_called
            on_error_called = True
        
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            bus.on_connect(on_connect)
            bus.on_disconnect(on_disconnect)
            bus.on_error(on_error)
            
            await bus.connect()
            
            # Verify callback registered (called during connect)
            assert on_connect_called
    
    async def test_error_callback_async(self, mock_nats):
        """Test async error callback"""
        error_events = []
        
        async def on_error(e):
            error_events.append(e)
        
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            bus.on_error(on_error)
            await bus.connect()
            
            # Simulate error
            await bus._error_cb(Exception("test error"))
            
            assert len(error_events) == 1


@pytest.mark.asyncio
class TestGlobalEventBus:
    """Test global event bus singleton"""
    
    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up global state after each test"""
        yield
        # Reset global instance
        import bot.rosey.core.event_bus
        bot.rosey.core.event_bus._event_bus = None
    
    @pytest.fixture
    async def mock_nats_global(self):
        """Mock NATS client for global tests"""
        nc = AsyncMock()
        nc.is_connected = True
        nc.jetstream = Mock(return_value=AsyncMock())
        nc.drain = AsyncMock()
        nc.close = AsyncMock()
        return nc
    
    async def test_initialize_event_bus(self, mock_nats_global):
        """Test initializing global event bus"""
        with patch('nats.connect', return_value=mock_nats_global):
            bus1 = await initialize_event_bus()
            
            assert bus1 is not None
            assert bus1.is_connected()
    
    async def test_get_event_bus(self, mock_nats_global):
        """Test getting global event bus"""
        with patch('nats.connect', return_value=mock_nats_global):
            # Initialize first
            bus1 = await initialize_event_bus()
            
            # Get same instance
            bus2 = await get_event_bus()
            
            assert bus1 is bus2
    
    async def test_get_event_bus_not_initialized(self):
        """Test getting event bus before initialization raises error"""
        with pytest.raises(RuntimeError, match="not initialized"):
            await get_event_bus()
    
    async def test_initialize_already_initialized(self, mock_nats_global):
        """Test initializing when already initialized returns same instance"""
        with patch('nats.connect', return_value=mock_nats_global):
            bus1 = await initialize_event_bus()
            bus2 = await initialize_event_bus()
            
            assert bus1 is bus2
    
    async def test_shutdown_event_bus(self, mock_nats_global):
        """Test shutting down global event bus"""
        with patch('nats.connect', return_value=mock_nats_global):
            await initialize_event_bus()
            
            await shutdown_event_bus()
            
            # Should be None now
            with pytest.raises(RuntimeError):
                await get_event_bus()


@pytest.mark.asyncio
async def test_event_bus_integration_mock():
    """
    Integration test with mocked NATS
    Tests full publish/subscribe flow
    """
    mock_nats = AsyncMock()
    mock_nats.is_connected = True
    mock_nats.jetstream = Mock(return_value=AsyncMock())
    
    # Track published messages
    published_messages = []
    
    async def mock_publish(subject, payload, headers=None):
        published_messages.append({
            "subject": subject,
            "payload": json.loads(payload.decode('utf-8'))
        })
    
    mock_nats.publish = mock_publish
    
    # Track subscriptions
    subscriptions = {}
    
    async def mock_subscribe(subject, queue=None, cb=None):
        mock_sub = Mock()
        mock_sub._id = len(subscriptions) + 1
        subscriptions[subject] = {
            "callback": cb,
            "queue": queue
        }
        return mock_sub
    
    mock_nats.subscribe = mock_subscribe
    
    with patch('nats.connect', return_value=mock_nats):
        # Create bus
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        # Subscribe
        received_events = []
        
        async def handler(event):
            received_events.append(event)
        
        await bus.subscribe("rosey.test.>", handler)
        
        # Publish
        event = Event(
            subject="rosey.test.message",
            event_type="message",
            source="test",
            data={"text": "hello"}
        )
        
        await bus.publish(event)
        
        # Verify published
        assert len(published_messages) == 1
        assert published_messages[0]["subject"] == "rosey.test.message"
        assert published_messages[0]["payload"]["data"]["text"] == "hello"
        
        # Simulate message received
        callback = subscriptions["rosey.test.>"]["callback"]
        mock_msg = Mock()
        mock_msg.data = event.to_json().encode('utf-8')
        await callback(mock_msg)
        
        # Verify handler called
        assert len(received_events) == 1
        assert received_events[0].data["text"] == "hello"
        
        await bus.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
