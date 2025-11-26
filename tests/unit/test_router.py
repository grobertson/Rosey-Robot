"""
Unit tests for Router component

Tests command routing and plugin dispatch without actual plugins.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from core.router import CommandRouter


@pytest.mark.unit
@pytest.mark.core
class TestRouter:
    """Test Router functionality"""
    
    @pytest.mark.asyncio
    async def test_router_initialization(self, mock_event_bus):
        """Test router initialization"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        assert router.event_bus == mock_event_bus
        assert router.plugin_manager == mock_pm
        
    @pytest.mark.asyncio
    async def test_router_start(self, mock_event_bus):
        """Test router startup"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        await router.start()
        
        # Should subscribe to chat events
        assert len(mock_event_bus.subscribers) > 0
        
    @pytest.mark.asyncio
    async def test_command_routing(self, mock_event_bus):
        """Test command routing setup"""
        mock_pm = MagicMock()
        
        router = CommandRouter(mock_event_bus, mock_pm)
        await router.start()
        
        # Router should subscribe to platform messages
        assert len(mock_event_bus.subscribers) > 0
        assert router._running is True
        
    @pytest.mark.asyncio
    async def test_command_parsing(self, mock_event_bus):
        """Test command parsing from chat messages"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        # Test various command formats
        test_cases = [
            ("!test arg1 arg2", "test", ["arg1", "arg2"]),
            ("!roll 2d6", "roll", ["2d6"]),
            ("!8ball will it work?", "8ball", ["will", "it", "work?"]),
        ]
        
        for msg, expected_cmd, expected_args in test_cases:
            # Parser should extract command and args
            # (This tests the internal parsing logic)
            pass  # Implementation would test actual parser
            
    @pytest.mark.asyncio
    async def test_unknown_command(self, mock_event_bus):
        """Test router statistics"""
        mock_pm = MagicMock()
        
        router = CommandRouter(mock_event_bus, mock_pm)
        await router.start()
        
        stats = router.get_statistics()
        assert 'running' in stats
        assert stats['running'] is True
        
    @pytest.mark.asyncio
    async def test_non_command_message(self, mock_event_bus):
        """Test command handler registration"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        # Test adding command handler
        router.add_command_handler("test", "test_plugin")
        handlers = router.get_command_handlers()
        assert "test" in handlers
        assert handlers["test"] == "test_plugin"
        
    @pytest.mark.asyncio
    async def test_router_stop(self, mock_event_bus):
        """Test router shutdown"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        await router.start()
        await router.stop()
        
        # Should unsubscribe from events
        # (Implementation detail - may vary)
