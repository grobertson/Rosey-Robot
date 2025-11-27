"""Integration tests for Sprint 18 - Funny Games.

Tests cross-plugin interactions, help system integration, and performance.
"""

import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def mock_message(content: str, user: str = "testuser", channel: str = "lobby"):
    """Create a mock NATS message."""
    data = {
        "content": content,
        "user": user,
        "channel": channel,
    }
    msg = MagicMock()
    msg.data = json.dumps(data).encode()
    msg.subject = "test.subject"
    msg.reply = "test.reply"
    return msg


class TestPluginLoading:
    """Test that all Sprint 18 plugins load correctly."""
    
    async def test_dice_roller_plugin_exists(self):
        """Verify dice-roller plugin can be imported."""
        import sys
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        assert DiceRollerPlugin is not None
    
    @pytest.mark.skip(reason="8ball requires special import handling - covered by unit tests")
    async def test_8ball_plugin_exists(self):
        """Verify 8ball plugin can be imported."""
        pass
    
    async def test_countdown_plugin_exists(self):
        """Verify countdown plugin can be imported."""
        from plugins.countdown.plugin import CountdownPlugin
        assert CountdownPlugin is not None
    
    async def test_trivia_plugin_exists(self):
        """Verify trivia plugin can be imported."""
        from plugins.trivia.plugin import TriviaPlugin
        assert TriviaPlugin is not None
    
    async def test_inspector_plugin_exists(self):
        """Verify inspector plugin can be imported."""
        from plugins.inspector.plugin import InspectorPlugin
        assert InspectorPlugin is not None


class TestPluginSubscriptions:
    """Test that plugins register expected NATS subscriptions."""
    
    async def test_dice_roller_subscriptions(self):
        """Verify dice-roller registers correct subscriptions."""
        import sys
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        
        nc = AsyncMock()
        plugin = DiceRollerPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should have 2 subscriptions: roll and flip
        assert len(plugin._subscriptions) == 2
        
        await plugin.shutdown()
    
    @pytest.mark.skip(reason="8ball requires special import handling - covered by unit tests")
    async def test_8ball_subscriptions(self):
        """Verify 8ball registers correct subscriptions."""
        pass
    
    async def test_countdown_subscriptions(self):
        """Verify countdown registers correct subscriptions."""
        from plugins.countdown.plugin import CountdownPlugin
        
        # Mock NATS request with proper response structure
        nc = AsyncMock()
        mock_response = MagicMock()
        # Return the migration status that countdown expects
        mock_response.data = json.dumps({
            "success": True,
            "current_version": 2,
            "migrations_applied": [1, 2]
        }).encode()
        nc.request = AsyncMock(return_value=mock_response)
        
        plugin = CountdownPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should have 7 subscriptions: create, check, list, delete, alerts, pause, resume
        assert len(plugin._subscriptions) == 7
        
        await plugin.shutdown()
    
    async def test_trivia_subscriptions(self):
        """Verify trivia registers correct subscriptions."""
        from plugins.trivia.plugin import TriviaPlugin
        
        nc = AsyncMock()
        nc.request = AsyncMock()
        plugin = TriviaPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should have 7 subscriptions
        assert len(plugin._subscriptions) == 7
        
        await plugin.shutdown()
    
    async def test_inspector_subscriptions(self):
        """Verify inspector registers correct subscriptions."""
        from plugins.inspector.plugin import InspectorPlugin
        
        nc = AsyncMock()
        plugin = InspectorPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should have 7 subscriptions: wildcard + 6 commands
        assert len(plugin._subscriptions) == 7
        
        await plugin.shutdown()


class TestCrossPluginInteraction:
    """Test interactions between different plugins."""
    
    async def test_inspector_captures_dice_events(self):
        """Verify inspector captures dice roll events."""
        from plugins.inspector.plugin import InspectorPlugin
        
        nc = AsyncMock()
        inspector = InspectorPlugin(nc, {})
        
        await inspector.initialize()
        
        # Simulate a dice roll event
        test_msg = mock_message("!roll d20")
        test_msg.subject = "rosey.command.dice.roll"
        
        # Manually capture event (inspector subscribes to > wildcard)
        from plugins.inspector.buffer import CapturedEvent
        from datetime import datetime
        event = CapturedEvent(
            timestamp=datetime.utcnow(),
            subject=test_msg.subject,
            data=test_msg.data.encode() if isinstance(test_msg.data, str) else test_msg.data,
            size_bytes=len(test_msg.data) if isinstance(test_msg.data, (str, bytes)) else 0,
        )
        inspector.buffer.append(event)
        
        # Check that event was captured
        events = inspector.buffer.get_recent(pattern="rosey.command.dice.*")
        assert len(events) == 1
        assert events[0].subject == "rosey.command.dice.roll"
        
        await inspector.shutdown()
    
    async def test_inspector_excludes_inbox_messages(self):
        """Verify inspector excludes _INBOX messages by default."""
        from plugins.inspector.plugin import InspectorPlugin
        
        nc = AsyncMock()
        inspector = InspectorPlugin(nc, {})
        
        await inspector.initialize()
        
        # Simulate an _INBOX message
        test_msg = mock_message("internal")
        test_msg.subject = "_INBOX.abc123"
        
        # Check if filter would exclude it
        should_capture = inspector.filter_chain.should_capture(test_msg.subject)
        assert not should_capture, "_INBOX messages should be filtered out"
        
        await inspector.shutdown()
    
    async def test_multiple_plugins_coexist(self):
        """Verify multiple plugins can operate simultaneously."""
        import sys
        
        # Import dice-roller
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        
        # Import countdown and trivia (skip 8ball due to import complexity)
        from plugins.countdown.plugin import CountdownPlugin
        from plugins.trivia.plugin import TriviaPlugin
        
        nc = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "success": True,
            "current_version": 2,
            "migrations_applied": [1, 2]
        }).encode()
        nc.request = AsyncMock(return_value=mock_response)
        
        # Initialize all plugins
        dice = DiceRollerPlugin(nc, {})
        countdown = CountdownPlugin(nc, {})
        trivia = TriviaPlugin(nc, {})
        
        await dice.initialize()
        await countdown.initialize()
        await trivia.initialize()
        
        # All should be active
        assert len(dice._subscriptions) > 0
        assert len(countdown._subscriptions) > 0
        assert len(trivia._subscriptions) > 0
        
        # Cleanup
        await dice.shutdown()
        await countdown.shutdown()
        await trivia.shutdown()


class TestPerformance:
    """Performance tests for Sprint 18 plugins."""
    
    async def test_inspector_buffer_performance(self):
        """Verify inspector buffer handles high event volume."""
        from plugins.inspector.buffer import EventBuffer, CapturedEvent
        
        buffer = EventBuffer(max_size=1000)
        
        # Add 2000 events (should keep only last 1000)
        for i in range(2000):
            event = CapturedEvent(
                timestamp=datetime.utcnow(),
                subject=f"test.event.{i}",
                data=b'{"test": true}',
                size_bytes=16,
            )
            buffer.append(event)
        
        # Buffer should maintain size limit
        assert len(buffer._buffer) == 1000
        
        # Query should be fast
        start = time.perf_counter()
        events = buffer.get_recent(10)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 0.01  # Should be < 10ms
        assert len(events) == 10
    
    async def test_inspector_filter_performance(self):
        """Verify event filtering is performant."""
        from plugins.inspector.filters import FilterChain
        
        filter = FilterChain(
            include=["test.*"],
            exclude=["test.excluded.*"],
        )
        
        # Test 1000 events
        start = time.perf_counter()
        for i in range(1000):
            subject = f"test.event.{i}" if i % 2 == 0 else f"test.excluded.{i}"
            filter.should_capture(subject)
        elapsed = time.perf_counter() - start
        
        # Should be < 100ms for 1000 events
        assert elapsed < 0.1
    
    async def test_dice_roller_performance(self):
        """Verify dice rolling is performant."""
        import sys
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        
        nc = AsyncMock()
        nc.publish = AsyncMock()
        plugin = DiceRollerPlugin(nc, {})
        
        await plugin.initialize()
        
        # Roll 100 times
        start = time.perf_counter()
        for _ in range(100):
            await plugin._handle_roll(mock_message("!roll 2d6+3"))
        elapsed = time.perf_counter() - start
        
        # Should be < 1 second
        assert elapsed < 1.0
        
        await plugin.shutdown()


class TestErrorHandling:
    """Test error handling across plugins."""
    
    async def test_dice_roller_invalid_input(self):
        """Verify dice roller handles invalid input gracefully."""
        import sys
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        
        nc = AsyncMock()
        plugin = DiceRollerPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should not crash on invalid input
        try:
            await plugin._handle_roll(mock_message("!roll invalid"))
            await plugin._handle_roll(mock_message("!roll 999d999"))
            await plugin._handle_roll(mock_message("!roll"))
            # If we get here, test passes (no exceptions)
            assert True
        except Exception as e:
            pytest.fail(f"Plugin crashed on invalid input: {e}")
        
        await plugin.shutdown()
    
    async def test_countdown_invalid_time(self):
        """Verify countdown handles invalid time gracefully."""
        from plugins.countdown.plugin import CountdownPlugin
        
        nc = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "success": True,
            "current_version": 2,
            "migrations_applied": [1, 2]
        }).encode()
        nc.request = AsyncMock(return_value=mock_response)
        plugin = CountdownPlugin(nc, {})
        
        await plugin.initialize()
        
        # Should not crash on invalid time
        await plugin._handle_create(mock_message("!countdown test invalid_time"))
        
        await plugin.shutdown()
    
    async def test_trivia_concurrent_starts(self):
        """Verify trivia handles concurrent start requests."""
        from plugins.trivia.plugin import TriviaPlugin
        
        nc = AsyncMock()
        nc.request = AsyncMock()
        nc.publish = AsyncMock()
        plugin = TriviaPlugin(nc, {})
        
        await plugin.initialize()
        
        # Try to start multiple games in same channel
        await plugin._handle_start(mock_message("!trivia start"))
        await plugin._handle_start(mock_message("!trivia start"))
        
        # Should only have one active game
        assert len(plugin.active_games) <= 1
        
        await plugin.shutdown()


class TestConfiguration:
    """Test plugin configuration handling."""
    
    async def test_dice_roller_custom_config(self):
        """Verify dice roller respects custom configuration."""
        import sys
        sys.path.insert(0, "plugins/dice-roller")
        from plugin import DiceRollerPlugin
        sys.path.pop(0)
        
        nc = AsyncMock()
        config = {
            "max_dice": 50,
            "max_sides": 500,
        }
        plugin = DiceRollerPlugin(nc, config)
        
        await plugin.initialize()
        
        # Check parser limits (not direct attributes)
        assert plugin.roller.parser.max_dice == 50
        assert plugin.roller.parser.max_sides == 500
        
        await plugin.shutdown()
    
    async def test_inspector_custom_buffer_size(self):
        """Verify inspector respects custom buffer size."""
        from plugins.inspector.plugin import InspectorPlugin
        
        nc = AsyncMock()
        config = {"buffer_size": 500}
        plugin = InspectorPlugin(nc, config)
        
        await plugin.initialize()
        
        assert plugin.buffer.max_size == 500
        
        await plugin.shutdown()
    
    async def test_trivia_custom_timing(self):
        """Verify trivia respects custom timing configuration."""
        from plugins.trivia.plugin import TriviaPlugin
        
        nc = AsyncMock()
        nc.request = AsyncMock()
        config = {
            "time_per_question": 60,
            "default_questions": 5,
        }
        plugin = TriviaPlugin(nc, config)
        
        await plugin.initialize()
        
        assert plugin.time_per_question == 60
        assert plugin.default_questions == 5
        
        await plugin.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
