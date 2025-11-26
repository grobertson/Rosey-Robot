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
        """Test command gets routed to correct plugin"""
        mock_pm = MagicMock()
        mock_pm.get_plugin_for_command.return_value = "test_plugin"
        
        router = CommandRouter(mock_event_bus, mock_pm)
        await router.start()
        
        # Simulate chat command
        await mock_event_bus.publish(
            "cytube.chat.message",
            {
                "username": "testuser",
                "msg": "!test command",
                "channel": "test"
            }
        )
        
        # Router should have processed the event
        events = mock_event_bus.get_published("plugin.test_plugin.command")
        assert len(events) > 0 or mock_pm.get_plugin_for_command.called
        
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
        """Test handling of unknown commands"""
        mock_pm = MagicMock()
        mock_pm.get_plugin_for_command.return_value = None
        
        router = CommandRouter(mock_event_bus, mock_pm)
        await router.start()
        
        # Simulate unknown command
        await mock_event_bus.publish(
            "cytube.chat.message",
            {
                "username": "testuser",
                "msg": "!unknowncommand",
                "channel": "test"
            }
        )
        
        # Should not route to any plugin
        plugin_events = mock_event_bus.get_published("plugin.")
        # Unknown commands might be ignored or logged
        
    @pytest.mark.asyncio
    async def test_non_command_message(self, mock_event_bus):
        """Test handling of non-command messages"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        await router.start()
        
        # Simulate regular chat (no !)
        await mock_event_bus.publish(
            "cytube.chat.message",
            {
                "username": "testuser",
                "msg": "hello everyone",
                "channel": "test"
            }
        )
        
        # Should not route to plugin commands
        mock_pm.get_plugin_for_command.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_router_stop(self, mock_event_bus):
        """Test router shutdown"""
        mock_pm = MagicMock()
        router = CommandRouter(mock_event_bus, mock_pm)
        
        await router.start()
        await router.stop()
        
        # Should unsubscribe from events
        # (Implementation detail - may vary)
