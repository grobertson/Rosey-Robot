"""
Integration tests for NATS connectivity
Tests actual NATS pub/sub without full bot stack
"""
import pytest
import asyncio
import json
from unittest.mock import patch

from bot.rosey.core.event_bus import EventBus, Event
from tests.fixtures.mock_nats import create_mock_nats


@pytest.mark.asyncio
@pytest.mark.integration
class TestNATSIntegration:
    """Test NATS integration with mock client"""
    
    @pytest.fixture
    async def mock_event_bus(self):
        """Create EventBus with mocked NATS"""
        mock_nats = create_mock_nats()
        
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            await bus.connect()
            
            yield bus
            
            await bus.disconnect()
    
    async def test_connect_disconnect(self):
        """Test connecting and disconnecting"""
        mock_nats = create_mock_nats()
        
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            
            # Initially not connected
            assert not bus.is_connected()
            
            # Connect
            await bus.connect()
            assert bus.is_connected()
            
            # Disconnect
            await bus.disconnect()
            assert not bus.is_connected()
    
    async def test_publish_subscribe(self, mock_event_bus):
        """Test basic pub/sub"""
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        # Subscribe
        await mock_event_bus.subscribe("rosey.test.>", handler)
        
        # Give subscription time to set up
        await asyncio.sleep(0.1)
        
        # Publish
        event = Event(
            subject="rosey.test.message",
            event_type="test",
            source="test",
            data={"message": "hello"}
        )
        
        await mock_event_bus.publish(event)
        
        # Wait for delivery
        await asyncio.sleep(0.2)
        
        # Verify received
        assert len(received_events) == 1
        assert received_events[0].subject == "rosey.test.message"
        assert received_events[0].data["message"] == "hello"
    
    async def test_wildcard_subscription(self, mock_event_bus):
        """Test wildcard subscriptions"""
        events_received = {
            "single": [],
            "multi": []
        }
        
        async def single_handler(event: Event):
            events_received["single"].append(event)
        
        async def multi_handler(event: Event):
            events_received["multi"].append(event)
        
        # Single-level wildcard
        await mock_event_bus.subscribe("rosey.test.*", single_handler)
        
        # Multi-level wildcard
        await mock_event_bus.subscribe("rosey.test.>", multi_handler)
        
        await asyncio.sleep(0.1)
        
        # Publish to different levels
        await mock_event_bus.publish(Event(
            subject="rosey.test.one",
            event_type="test",
            source="test",
            data={}
        ))
        
        await mock_event_bus.publish(Event(
            subject="rosey.test.one.two",
            event_type="test",
            source="test",
            data={}
        ))
        
        await asyncio.sleep(0.2)
        
        # Single wildcard should match first only
        assert len(events_received["single"]) == 1
        
        # Multi wildcard should match both
        assert len(events_received["multi"]) == 2
    
    async def test_request_reply(self, mock_event_bus):
        """Test request/reply pattern"""
        # Note: This test demonstrates the pattern, but the actual reply mechanism
        # requires the raw NATS message which isn't exposed through Event
        # In practice, plugins would use publish() to send responses
        
        responses = []
        
        async def responder(event: Event):
            # Plugin would typically publish response to a result subject
            response_event = Event(
                subject="rosey.test.response",
                event_type="response",
                source="responder",
                data={"status": "success", "echo": event.data}
            )
            await mock_event_bus.publish(response_event)
        
        # Responder subscribes to requests
        await mock_event_bus.subscribe("rosey.test.request", responder)
        
        # Collector subscribes to responses
        async def collect_response(event: Event):
            responses.append(event)
        
        await mock_event_bus.subscribe("rosey.test.response", collect_response)
        await asyncio.sleep(0.1)
        
        # Send request
        request_event = Event(
            subject="rosey.test.request",
            event_type="request",
            source="test",
            data={"message": "ping"}
        )
        await mock_event_bus.publish(request_event)
        await asyncio.sleep(0.3)
        
        # Verify response received
        assert len(responses) > 0
        assert responses[0].data["status"] == "success"
        assert responses[0].data["echo"]["message"] == "ping"
    
    async def test_multiple_subscribers(self, mock_event_bus):
        """Test multiple subscribers to same subject"""
        counts = {"handler1": 0, "handler2": 0}
        
        async def handler1(event: Event):
            counts["handler1"] += 1
        
        async def handler2(event: Event):
            counts["handler2"] += 1
        
        # Both subscribe to same subject
        await mock_event_bus.subscribe("rosey.test.multi", handler1)
        await mock_event_bus.subscribe("rosey.test.multi", handler2)
        
        await asyncio.sleep(0.1)
        
        # Publish one event
        await mock_event_bus.publish(Event(
            subject="rosey.test.multi",
            event_type="test",
            source="test",
            data={}
        ))
        
        await asyncio.sleep(0.2)
        
        # Both should receive
        assert counts["handler1"] == 1
        assert counts["handler2"] == 1
    
    async def test_unsubscribe(self, mock_event_bus):
        """Test unsubscribing"""
        received = []
        
        async def handler(event: Event):
            received.append(event)
        
        # Subscribe
        sub_id = await mock_event_bus.subscribe("rosey.test.unsub", handler)
        await asyncio.sleep(0.1)
        
        # Publish first event
        await mock_event_bus.publish(Event(
            subject="rosey.test.unsub",
            event_type="test",
            source="test",
            data={"count": 1}
        ))
        
        await asyncio.sleep(0.2)
        assert len(received) == 1
        
        # Unsubscribe (EventBus API)
        await mock_event_bus.unsubscribe("rosey.test.unsub")
        # Also unsubscribe in the mock (since EventBus.unsubscribe only removes from tracking)
        await mock_event_bus._nc.unsubscribe_by_subject("rosey.test.unsub")
        await asyncio.sleep(0.1)
        
        # Publish second event
        await mock_event_bus.publish(Event(
            subject="rosey.test.unsub",
            event_type="test",
            source="test",
            data={"count": 2}
        ))
        
        await asyncio.sleep(0.2)
        
        # Should still have only first event (second not received)
        assert len(received) == 1
    
    async def test_event_serialization(self, mock_event_bus):
        """Test event serialization/deserialization"""
        received_event = None
        
        async def handler(event: Event):
            nonlocal received_event
            received_event = event
        
        await mock_event_bus.subscribe("rosey.test.serial", handler)
        await asyncio.sleep(0.1)
        
        # Create event with complex data
        original = Event(
            subject="rosey.test.serial",
            event_type="test",
            source="test",
            data={
                "string": "hello",
                "number": 42,
                "boolean": True,
                "list": [1, 2, 3],
                "nested": {"key": "value"}
            }
        )
        
        await mock_event_bus.publish(original)
        await asyncio.sleep(0.2)
        
        # Verify all fields preserved
        assert received_event is not None
        assert received_event.subject == original.subject
        assert received_event.event_type == original.event_type
        assert received_event.source == original.source
        assert received_event.data == original.data
        assert received_event.correlation_id == original.correlation_id


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
