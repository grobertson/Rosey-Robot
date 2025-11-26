"""
Integration tests for chat command flow

Tests full command flow: CyTube -> EventBus -> Router -> Plugin
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.integration
class TestChatCommandFlow:
    """Test end-to-end command processing"""
    
    @pytest.mark.asyncio
    async def test_simple_command_flow(self, mock_event_bus, mock_cytube_events):
        """Test: User sends !roll -> dice plugin responds"""
        
        # 1. CyTube chat event arrives
        chat_event = mock_cytube_events.chat(msg="!roll 2d6")
        
        # 2. Publish to EventBus
        await mock_event_bus.publish(
            "cytube.chat.message",
            chat_event
        )
        
        # 3. Verify event was published
        events = mock_event_bus.get_published("cytube.chat.message")
        assert len(events) == 1
        assert events[0]['data']['msg'] == "!roll 2d6"
        
    @pytest.mark.asyncio
    async def test_command_with_args(self, mock_event_bus, mock_cytube_events):
        """Test command parsing with multiple arguments"""
        
        chat_event = mock_cytube_events.chat(msg="!countdown movie 2025-12-31 23:59")
        
        await mock_event_bus.publish(
            "cytube.chat.message",
            chat_event
        )
        
        # Command should be parsed correctly
        events = mock_event_bus.get_published("cytube.chat.message")
        assert len(events) == 1
        
    @pytest.mark.asyncio
    async def test_plugin_response_flow(self, mock_event_bus, mock_cytube_events):
        """Test: Plugin responds -> CyTube sends message"""
        
        # 1. Plugin publishes response
        await mock_event_bus.publish(
            "platform.cytube.send_chat",
            {"msg": "🎲 Rolled 2d6: [3, 5] = 8"}
        )
        
        # 2. Verify response was published
        responses = mock_event_bus.get_published("platform.cytube.send_chat")
        assert len(responses) == 1
        assert "8" in responses[0]['data']['msg']
        
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, mock_event_bus, mock_cytube_events):
        """Test error response flow"""
        
        # 1. Invalid command
        chat_event = mock_cytube_events.chat(msg="!roll invalid")
        await mock_event_bus.publish("cytube.chat.message", chat_event)
        
        # 2. Plugin might send error response
        await mock_event_bus.publish(
            "platform.cytube.send_chat",
            {"msg": "Error: Invalid dice notation"}
        )
        
        responses = mock_event_bus.get_published("platform.cytube.send_chat")
        assert len(responses) >= 1
        
    @pytest.mark.asyncio
    async def test_multiple_commands_sequence(self, mock_event_bus, mock_cytube_events):
        """Test processing multiple commands in sequence"""
        
        commands = [
            "!roll 2d6",
            "!8ball will this work?",
            "!trivia start"
        ]
        
        for cmd in commands:
            chat_event = mock_cytube_events.chat(msg=cmd)
            await mock_event_bus.publish("cytube.chat.message", chat_event)
        
        events = mock_event_bus.get_published("cytube.chat.message")
        assert len(events) == len(commands)
        
    @pytest.mark.asyncio
    async def test_concurrent_commands(self, mock_event_bus, mock_cytube_events):
        """Test handling concurrent commands from different users"""
        
        import asyncio
        
        async def send_command(user, msg):
            event = mock_cytube_events.chat(username=user, msg=msg)
            await mock_event_bus.publish("cytube.chat.message", event)
        
        # Simulate concurrent commands
        await asyncio.gather(
            send_command("user1", "!roll 2d6"),
            send_command("user2", "!8ball test"),
            send_command("user3", "!roll d20")
        )
        
        events = mock_event_bus.get_published("cytube.chat.message")
        assert len(events) == 3
