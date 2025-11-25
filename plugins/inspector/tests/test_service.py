import pytest
from unittest.mock import Mock
from datetime import datetime
from plugins.inspector.service import InspectorService
from plugins.inspector.buffer import EventBuffer, CapturedEvent
from plugins.inspector.filters import FilterChain


class TestInspectorService:
    """Test InspectorService functionality."""

    @pytest.fixture
    def service(self):
        buffer = EventBuffer()
        filters = FilterChain()
        return InspectorService(buffer, filters)

    def test_pause_resume(self, service):
        assert service.is_paused is False
        service.pause()
        assert service.is_paused is True
        service.resume()
        assert service.is_paused is False

    def test_subscription(self, service):
        mock_callback = Mock()
        service.subscribe(mock_callback)
        
        event = CapturedEvent(datetime.now(), "test", b"{}", 2)
        service._notify_subscribers(event)
        
        mock_callback.assert_called_once_with(event)
        
        service.unsubscribe(mock_callback)
        service._notify_subscribers(event)
        
        assert mock_callback.call_count == 1
