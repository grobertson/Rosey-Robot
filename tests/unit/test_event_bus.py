"""
Unit tests for EventBus (NATS wrapper)

Tests the core NATS messaging functionality without requiring
an actual NATS server (uses mocking).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.event_bus import EventBus, Event, Priority


@pytest.mark.unit
@pytest.mark.core
class TestEventBus:
    """Test EventBus core functionality"""
    
    @pytest.mark.asyncio
    async def test_event_creation(self):
        """Test Event dataclass creation"""
        event = Event(
            subject="test.subject",
            event_type="test",
            source="test_component",
            data={"key": "value"}
        )
        
        assert event.subject == "test.subject"
        assert event.event_type == "test"
        assert event.source == "test_component"
        assert event.data == {"key": "value"}
        assert event.priority == Priority.NORMAL
        assert event.correlation_id is not None
        
    @pytest.mark.asyncio
    async def test_event_priority(self):
        """Test event priority levels"""
        low = Event(subject="test", event_type="test", source="test", data={}, priority=Priority.LOW)
        normal = Event(subject="test", event_type="test", source="test", data={}, priority=Priority.NORMAL)
        high = Event(subject="test", event_type="test", source="test", data={}, priority=Priority.HIGH)
        critical = Event(subject="test", event_type="test", source="test", data={}, priority=Priority.CRITICAL)
        
        assert low.priority.value < normal.priority.value
        assert normal.priority.value < high.priority.value
        assert high.priority.value < critical.priority.value
        
    @pytest.mark.asyncio
    @patch('core.event_bus.nats.connect')
    async def test_connect(self, mock_connect):
        """Test EventBus connection"""
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.jetstream = MagicMock()
        mock_connect.return_value = mock_nc
        
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        assert bus.is_connected()
        mock_connect.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('core.event_bus.nats.connect')
    async def test_disconnect(self, mock_connect):
        """Test EventBus disconnection"""
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.jetstream = MagicMock()
        mock_connect.return_value = mock_nc
        
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        await bus.disconnect()
        
        assert not bus.is_connected()
        mock_nc.drain.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('core.event_bus.nats.connect')
    async def test_publish(self, mock_connect):
        """Test event publishing"""
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.jetstream = MagicMock()
        mock_connect.return_value = mock_nc
        
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        event = Event(
            subject="test.subject",
            data={"key": "value"},
            event_type="test",
            source="test_component"
        )
        
        await bus.publish(event)
        
        assert event.subject == "test.subject"
        assert event.data == {"key": "value"}
        mock_nc.publish.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('core.event_bus.nats.connect')
    async def test_subscribe(self, mock_connect):
        """Test event subscription"""
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.jetstream = MagicMock()
        mock_sub = MagicMock()
        mock_sub._id = 1
        mock_nc.subscribe.return_value = mock_sub
        mock_connect.return_value = mock_nc
        
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        callback = AsyncMock()
        sub_id = await bus.subscribe("test.>", callback)
        
        assert sub_id == 1
        mock_nc.subscribe.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('core.event_bus.nats.connect')
    async def test_request_reply(self, mock_connect):
        """Test request/reply pattern"""
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.jetstream = MagicMock()
        mock_response = MagicMock()
        mock_response.data = b'{"success": true, "data": "test"}'
        mock_nc.request.return_value = mock_response
        mock_connect.return_value = mock_nc
        
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        response = await bus.request(
            subject="test.request",
            data={"query": "test"},
            timeout=1.0
        )
        
        assert response is not None
        assert "success" in response
        mock_nc.request.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_event_correlation_id(self):
        """Test correlation ID generation and propagation"""
        event1 = Event(subject="test", event_type="test", source="test", data={})
        event2 = Event(subject="test", event_type="test", source="test", data={}, 
                      correlation_id=event1.correlation_id)
        
        assert event1.correlation_id == event2.correlation_id
        
    @pytest.mark.asyncio
    async def test_event_metadata(self):
        """Test event metadata handling"""
        metadata = {"trace_id": "12345", "user": "testuser"}
        event = Event(
            subject="test",
            event_type="test",
            source="test",
            data={},
            metadata=metadata
        )
        
        assert event.metadata == metadata
        assert event.metadata["trace_id"] == "12345"
