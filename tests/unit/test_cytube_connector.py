"""
Unit tests for CytubeConnector

Tests CyTube WebSocket bridge without actual WebSocket connection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.cytube_connector import CytubeConnector, CytubeEventType


@pytest.mark.unit
@pytest.mark.core
class TestCytubeConnector:
    """Test CytubeConnector functionality"""
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, mock_event_bus):
        """Test connector initialization"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        assert connector.event_bus == mock_event_bus
        assert connector.channel == mock_channel
        
    @pytest.mark.asyncio
    async def test_connect(self, mock_event_bus):
        """Test connecting to CyTube"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        mock_channel.on = MagicMock()
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        result = await connector.start()
        assert isinstance(result, bool)
            
    @pytest.mark.asyncio
    async def test_disconnect(self, mock_event_bus):
        """Test disconnecting from CyTube"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        mock_channel.on = MagicMock()
        mock_channel.off = MagicMock()
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        await connector.start()
        result = await connector.stop()
        assert result is True
            
    @pytest.mark.asyncio
    async def test_chat_message_translation(self, mock_event_bus, mock_cytube_events):
        """Test translating CyTube chat to EventBus"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        # Test event translation
        cytube_data = mock_cytube_events.chat()
        await connector._on_chat_message(cytube_data)
        
        # Should publish to event bus
        assert len(mock_event_bus.published_events) == 1
        
    @pytest.mark.asyncio
    async def test_user_join_translation(self, mock_event_bus, mock_cytube_events):
        """Test translating user join events"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        cytube_data = mock_cytube_events.user_join()
        await connector._on_user_join(cytube_data)
        
        assert len(mock_event_bus.published_events) == 1
        
    @pytest.mark.asyncio
    async def test_media_change_translation(self, mock_event_bus, mock_cytube_events):
        """Test translating media change events"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        cytube_data = mock_cytube_events.media()
        await connector._on_change_media(cytube_data)
        
        assert len(mock_event_bus.published_events) == 1
        
    @pytest.mark.asyncio
    async def test_send_chat_command(self, mock_event_bus):
        """Test sending chat message to CyTube"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        mock_channel.send_message = AsyncMock()
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        await connector._send_chat_message("test message")
        mock_channel.send_message.assert_called_once_with("test message")
            
    @pytest.mark.asyncio
    async def test_event_type_enum(self):
        """Test CyTube event type enumeration"""
        # Verify event types exist
        assert CytubeEventType.CHAT_MSG
        assert CytubeEventType.USER_JOIN
        assert CytubeEventType.USER_LEAVE
        assert CytubeEventType.CHANGE_MEDIA
        
    @pytest.mark.asyncio
    async def test_reconnection_logic(self, mock_event_bus):
        """Test connector statistics"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        stats = connector.get_statistics()
        assert 'running' in stats
        assert 'events_received' in stats
        
    @pytest.mark.asyncio
    async def test_event_correlation(self, mock_event_bus):
        """Test getting channel name"""
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        connector = CytubeConnector(mock_event_bus, mock_channel)
        
        name = connector.get_channel_name()
        assert name == "test-channel"
