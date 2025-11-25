"""
Integration tests for DiceRollerPlugin.

Tests cover:
- Plugin lifecycle (initialize, shutdown)
- NATS command handling
- Event emission
- Error handling
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from plugin import DiceRollerPlugin
from dice import DiceRoller


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_nats():
    """Create mock NATS client for testing."""
    nats = AsyncMock()
    nats.subscribe = AsyncMock(return_value=MagicMock())
    nats.publish = AsyncMock()
    return nats


@pytest.fixture
def plugin(mock_nats):
    """Create plugin instance with mock NATS client."""
    return DiceRollerPlugin(mock_nats)


@pytest.fixture
async def initialized_plugin(plugin):
    """Create and initialize plugin instance."""
    await plugin.initialize()
    return plugin


# =============================================================================
# Plugin Metadata Tests
# =============================================================================


class TestPluginMetadata:
    """Tests for plugin metadata and constants."""

    def test_namespace(self, plugin):
        """Test plugin namespace is correct."""
        assert plugin.NAMESPACE == "dice-roller"

    def test_version(self, plugin):
        """Test plugin version is correct."""
        assert plugin.VERSION == "1.0.0"

    def test_description(self, plugin):
        """Test plugin description is correct."""
        assert plugin.DESCRIPTION == "Roll dice and flip coins"

    def test_nats_subjects(self, plugin):
        """Test NATS subjects are correct."""
        assert plugin.SUBJECT_ROLL == "rosey.command.dice.roll"
        assert plugin.SUBJECT_FLIP == "rosey.command.dice.flip"
        assert plugin.EVENT_ROLLED == "rosey.event.dice.rolled"
        assert plugin.EVENT_FLIPPED == "rosey.event.dice.flipped"


# =============================================================================
# Plugin Instantiation Tests
# =============================================================================


class TestPluginInstantiation:
    """Tests for plugin creation."""

    def test_create_plugin(self, mock_nats):
        """Test plugin instantiates correctly."""
        plugin = DiceRollerPlugin(mock_nats)

        assert plugin.nats == mock_nats
        assert plugin._initialized is False
        assert isinstance(plugin.roller, DiceRoller)

    def test_create_with_config(self, mock_nats):
        """Test plugin applies configuration."""
        config = {
            "max_dice": 10,
            "max_sides": 50,
            "max_modifier": 25,
            "emit_events": False,
        }
        plugin = DiceRollerPlugin(mock_nats, config)

        assert plugin.roller.parser.max_dice == 10
        assert plugin.roller.parser.max_sides == 50
        assert plugin.roller.parser.max_modifier == 25
        assert plugin.emit_events is False

    def test_default_emit_events(self, plugin):
        """Test default emit_events setting."""
        assert plugin.emit_events is True


# =============================================================================
# Plugin Lifecycle Tests
# =============================================================================


class TestPluginLifecycle:
    """Tests for plugin initialize and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_nats(self, plugin, mock_nats):
        """Test initialize subscribes to NATS subjects."""
        await plugin.initialize()

        # Should subscribe to both roll and flip subjects
        assert mock_nats.subscribe.call_count == 2

        # Verify subjects
        subjects = [call[0][0] for call in mock_nats.subscribe.call_args_list]
        assert "rosey.command.dice.roll" in subjects
        assert "rosey.command.dice.flip" in subjects

    @pytest.mark.asyncio
    async def test_initialize_sets_flag(self, plugin):
        """Test initialize sets _initialized flag."""
        assert plugin._initialized is False
        await plugin.initialize()
        assert plugin._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes(self, plugin, mock_nats):
        """Test shutdown unsubscribes from NATS."""
        mock_sub = AsyncMock()
        mock_nats.subscribe.return_value = mock_sub

        await plugin.initialize()
        await plugin.shutdown()

        # Should unsubscribe from both subscriptions
        assert mock_sub.unsubscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_clears_subscriptions(self, initialized_plugin):
        """Test shutdown clears subscription list."""
        await initialized_plugin.shutdown()
        assert len(initialized_plugin._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_shutdown_clears_initialized_flag(self, initialized_plugin):
        """Test shutdown clears _initialized flag."""
        await initialized_plugin.shutdown()
        assert initialized_plugin._initialized is False


# =============================================================================
# NATS Command Handler Tests
# =============================================================================


class TestNATSCommandHandlers:
    """Tests for NATS command handlers."""

    def _make_msg(self, data: dict, reply: str = "test.reply"):
        """Create mock NATS message."""
        msg = MagicMock()
        msg.data = json.dumps(data).encode()
        msg.reply = reply
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_handle_roll_success(self, plugin):
        """Test successful roll via NATS."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "alice",
            "args": "2d6",
        })

        await plugin._handle_roll(msg)

        # Should respond
        msg.respond.assert_called_once()

        # Parse response
        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is True
        assert "result" in response
        assert response["result"]["notation"] == "2d6"
        assert len(response["result"]["rolls"]) == 2
        assert all(1 <= r <= 6 for r in response["result"]["rolls"])

    @pytest.mark.asyncio
    async def test_handle_roll_with_modifier(self, plugin):
        """Test roll with modifier via NATS."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "bob",
            "args": "d20+5",
        })

        await plugin._handle_roll(msg)

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is True
        assert response["result"]["modifier"] == 5
        assert response["result"]["total"] == response["result"]["rolls"][0] + 5

    @pytest.mark.asyncio
    async def test_handle_roll_no_args_shows_usage(self, plugin):
        """Test roll without args returns usage."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "alice",
            "args": "",
        })

        await plugin._handle_roll(msg)

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is False
        assert "Usage" in response["error"]

    @pytest.mark.asyncio
    async def test_handle_roll_invalid_notation(self, plugin):
        """Test roll with invalid notation returns error."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "alice",
            "args": "invalid",
        })

        await plugin._handle_roll(msg)

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is False
        assert "❌" in response["error"]

    @pytest.mark.asyncio
    async def test_handle_roll_exceeds_limits(self, plugin):
        """Test roll exceeding limits returns error."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "alice",
            "args": "100d6",  # Exceeds max_dice
        })

        await plugin._handle_roll(msg)

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is False
        assert "Maximum" in response["error"]

    @pytest.mark.asyncio
    async def test_handle_flip_success(self, plugin):
        """Test successful flip via NATS."""
        msg = self._make_msg({
            "channel": "#test",
            "user": "charlie",
        })

        await plugin._handle_flip(msg)

        msg.respond.assert_called_once()

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is True
        assert response["result"]["outcome"] in ["Heads", "Tails"]
        assert "🪙" in response["result"]["formatted"]

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, plugin):
        """Test handling invalid JSON."""
        msg = MagicMock()
        msg.data = b"not valid json"
        msg.reply = "test.reply"
        msg.respond = AsyncMock()

        await plugin._handle_roll(msg)

        response = json.loads(msg.respond.call_args[0][0])

        assert response["success"] is False
        assert "Invalid" in response["error"]

    @pytest.mark.asyncio
    async def test_no_reply_subject(self, plugin):
        """Test handling message without reply subject."""
        msg = MagicMock()
        msg.data = json.dumps({"channel": "#test", "user": "alice", "args": "2d6"}).encode()
        msg.reply = None  # No reply subject
        msg.respond = AsyncMock()

        # Should not raise, just skip responding
        await plugin._handle_roll(msg)

        msg.respond.assert_not_called()


# =============================================================================
# Event Emission Tests
# =============================================================================


class TestEventEmission:
    """Tests for event emission."""

    @pytest.mark.asyncio
    async def test_roll_emits_event(self, plugin, mock_nats):
        """Test successful roll emits event."""
        await plugin._process_roll("#test", "alice", "2d6")

        # Should publish via NATS
        mock_nats.publish.assert_called()

        # Find the event publish call
        calls = mock_nats.publish.call_args_list
        roll_calls = [c for c in calls if "dice.rolled" in c[0][0]]

        assert len(roll_calls) == 1

        # Parse event data
        event_data = json.loads(roll_calls[0][0][1])

        assert event_data["channel"] == "#test"
        assert event_data["user"] == "alice"
        assert event_data["dice_count"] == 2
        assert event_data["dice_sides"] == 6

    @pytest.mark.asyncio
    async def test_flip_emits_event(self, plugin, mock_nats):
        """Test flip emits event."""
        await plugin._process_flip("#test", "bob")

        calls = mock_nats.publish.call_args_list
        flip_calls = [c for c in calls if "dice.flipped" in c[0][0]]

        assert len(flip_calls) == 1

        event_data = json.loads(flip_calls[0][0][1])

        assert event_data["channel"] == "#test"
        assert event_data["user"] == "bob"
        assert event_data["outcome"] in ["Heads", "Tails"]

    @pytest.mark.asyncio
    async def test_events_disabled_does_not_emit(self, mock_nats):
        """Test events not emitted when disabled."""
        plugin = DiceRollerPlugin(mock_nats, {"emit_events": False})

        await plugin._process_roll("#test", "alice", "2d6")

        # Should not publish events
        calls = mock_nats.publish.call_args_list
        roll_calls = [c for c in calls if "dice.rolled" in c[0][0]]

        assert len(roll_calls) == 0

    @pytest.mark.asyncio
    async def test_failed_roll_does_not_emit(self, plugin, mock_nats):
        """Test failed roll does not emit event."""
        mock_nats.publish.reset_mock()

        await plugin._process_roll("#test", "alice", "invalid")

        # Should not publish events
        mock_nats.publish.assert_not_called()


# =============================================================================
# Direct API Tests
# =============================================================================


class TestDirectAPI:
    """Tests for direct API methods."""

    def test_roll_direct(self, plugin):
        """Test direct roll method."""
        result = plugin.roll("2d6")

        assert result.count == 2
        assert result.sides == 6
        assert len(result.rolls) == 2
        assert all(1 <= r <= 6 for r in result.rolls)

    def test_roll_direct_invalid(self, plugin):
        """Test direct roll with invalid notation."""
        with pytest.raises(ValueError):
            plugin.roll("invalid")

    def test_flip_direct(self, plugin):
        """Test direct flip method."""
        result = plugin.flip()
        assert result in ["Heads", "Tails"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_nats_publish_error_handled(self, plugin, mock_nats):
        """Test NATS publish errors are handled gracefully."""
        mock_nats.publish.side_effect = Exception("NATS error")

        # Should not raise
        result = await plugin._process_roll("#test", "alice", "2d6")

        # Result should still be successful (event failure doesn't affect roll)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_respond_error_handled(self, plugin):
        """Test respond errors are handled gracefully."""
        msg = MagicMock()
        msg.data = json.dumps({"channel": "#test", "user": "alice", "args": "2d6"}).encode()
        msg.reply = "test.reply"
        msg.respond = AsyncMock(side_effect=Exception("Respond error"))

        # Should not raise
        await plugin._handle_roll(msg)

    @pytest.mark.asyncio
    async def test_shutdown_handles_unsubscribe_error(self, plugin, mock_nats):
        """Test shutdown handles unsubscribe errors gracefully."""
        mock_sub = AsyncMock()
        mock_sub.unsubscribe.side_effect = Exception("Unsubscribe error")
        mock_nats.subscribe.return_value = mock_sub

        await plugin.initialize()

        # Should not raise
        await plugin.shutdown()

        # Should still clear subscriptions
        assert len(plugin._subscriptions) == 0
