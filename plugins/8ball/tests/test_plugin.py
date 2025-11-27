"""
tests/test_plugin.py

Integration tests for the 8ball plugin.

Tests cover:
- Plugin initialization and shutdown
- NATS subscription management
- Command handling (!8ball ask)
- Cooldown logic
- Event emission
- Error handling
"""

import json
import time
from unittest.mock import MagicMock

import pytest

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugin import EightBallPlugin
from responses import POSITIVE_RESPONSES, NEUTRAL_RESPONSES, NEGATIVE_RESPONSES


# =============================================================================
# Plugin Initialization Tests
# =============================================================================

class TestPluginInit:
    """Tests for plugin initialization."""
    
    def test_init_with_defaults(self, mock_nats):
        """Plugin initializes with default config."""
        plugin = EightBallPlugin(mock_nats)
        
        assert plugin.cooldown_seconds == 3
        assert plugin.emit_events is True
        assert plugin.require_question is True
        assert plugin.max_question_length == 100
    
    def test_init_with_custom_config(self, mock_nats):
        """Plugin respects custom configuration."""
        config = {
            "cooldown_seconds": 10,
            "emit_events": False,
            "require_question": False,
            "max_question_length": 50,
        }
        plugin = EightBallPlugin(mock_nats, config)
        
        assert plugin.cooldown_seconds == 10
        assert plugin.emit_events is False
        assert plugin.require_question is False
        assert plugin.max_question_length == 50
    
    def test_init_has_namespace(self, mock_nats):
        """Plugin has namespace set."""
        plugin = EightBallPlugin(mock_nats)
        assert plugin.NAMESPACE == "8ball"
    
    def test_init_has_version(self, mock_nats):
        """Plugin has version set."""
        plugin = EightBallPlugin(mock_nats)
        assert plugin.VERSION == "1.0.0"


# =============================================================================
# Plugin Lifecycle Tests
# =============================================================================

class TestPluginLifecycle:
    """Tests for plugin lifecycle (initialize/shutdown)."""
    
    @pytest.mark.asyncio
    async def test_initialize_subscribes(self, mock_nats):
        """initialize() subscribes to NATS subjects."""
        plugin = EightBallPlugin(mock_nats)
        await plugin.initialize()
        
        # Should have subscribed to ask subject
        assert len(mock_nats._subscriptions) == 1
        assert mock_nats._subscriptions[0].subject == "rosey.command.8ball.ask"
    
    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes(self, mock_nats):
        """shutdown() unsubscribes from all subjects."""
        plugin = EightBallPlugin(mock_nats)
        await plugin.initialize()
        
        # Store reference before shutdown clears list
        sub = mock_nats._subscriptions[0]
        
        await plugin.shutdown()
        
        # Should have called unsubscribe
        sub.unsubscribe.assert_called_once()
        
        # Internal list should be cleared
        assert len(plugin._subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_shutdown_clears_cooldowns(self, mock_nats):
        """shutdown() clears cooldown tracking."""
        plugin = EightBallPlugin(mock_nats)
        plugin.cooldowns["test_user"] = time.time()
        
        await plugin.shutdown()
        
        assert len(plugin.cooldowns) == 0


# =============================================================================
# Command Handling Tests
# =============================================================================

class TestHandleAsk:
    """Tests for _handle_ask command handler."""
    
    @pytest.mark.asyncio
    async def test_successful_ask(self, mock_nats, mock_message):
        """Successful ask returns a response."""
        plugin = EightBallPlugin(mock_nats)
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Will I win?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Should have published response
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args_list[0]
        subject = call_args[0][0]
        data = json.loads(call_args[0][1].decode())
        
        assert subject == "rosey.reply.123"
        assert data["success"] is True
        assert "result" in data
        assert data["result"]["question"] == "Will I win?"
    
    @pytest.mark.asyncio
    async def test_response_has_all_fields(self, mock_nats, mock_message):
        """Response includes all expected fields."""
        plugin = EightBallPlugin(mock_nats)
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test question?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        result = data["result"]
        
        assert "question" in result
        assert "answer" in result
        assert "category" in result
        assert "flavor" in result
        assert "formatted" in result
    
    @pytest.mark.asyncio
    async def test_response_category_valid(self, mock_nats, mock_message):
        """Response category is one of the valid values."""
        plugin = EightBallPlugin(mock_nats)
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        category = data["result"]["category"]
        
        assert category in ["positive", "neutral", "negative"]
    
    @pytest.mark.asyncio
    async def test_response_answer_is_classic(self, mock_nats, mock_message):
        """Response answer is one of the classic 20."""
        plugin = EightBallPlugin(mock_nats)
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        answer = data["result"]["answer"]
        
        all_responses = POSITIVE_RESPONSES + NEUTRAL_RESPONSES + NEGATIVE_RESPONSES
        assert answer in all_responses
    
    @pytest.mark.asyncio
    async def test_formatted_includes_emoji(self, mock_nats, mock_message):
        """Formatted response includes 8-ball emoji."""
        plugin = EightBallPlugin(mock_nats)
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        formatted = data["result"]["formatted"]
        
        assert "🎱" in formatted


# =============================================================================
# Question Handling Tests
# =============================================================================

class TestQuestionHandling:
    """Tests for question validation and processing."""
    
    @pytest.mark.asyncio
    async def test_no_question_when_required(self, mock_nats, mock_message):
        """Empty question returns error when required=true."""
        plugin = EightBallPlugin(mock_nats, {"require_question": True})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "spirits need a question" in data["error"]
    
    @pytest.mark.asyncio
    async def test_no_question_when_not_required(self, mock_nats, mock_message):
        """Empty question succeeds when required=false."""
        plugin = EightBallPlugin(mock_nats, {"require_question": False})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is True
        assert "what does fate hold?" in data["result"]["question"]
    
    @pytest.mark.asyncio
    async def test_long_question_truncated(self, mock_nats, mock_message):
        """Questions longer than max_question_length are truncated."""
        plugin = EightBallPlugin(mock_nats, {"max_question_length": 20})
        long_question = "Will this very long question be truncated properly?"
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": long_question,
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        question = data["result"]["question"]
        
        assert len(question) <= 23  # 20 + "..."
        assert question.endswith("...")
    
    @pytest.mark.asyncio
    async def test_whitespace_question_stripped(self, mock_nats, mock_message):
        """Questions with only whitespace treated as empty."""
        plugin = EightBallPlugin(mock_nats, {"require_question": True})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "   \t\n   ",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False


# =============================================================================
# Cooldown Tests
# =============================================================================

class TestCooldown:
    """Tests for cooldown functionality."""
    
    def test_check_cooldown_first_use(self, mock_nats):
        """First use is always allowed."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 5})
        assert plugin._check_cooldown("new_user") is True
    
    def test_check_cooldown_immediate_second_use(self, mock_nats):
        """Immediate second use is blocked."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 5})
        plugin._update_cooldown("test_user")
        assert plugin._check_cooldown("test_user") is False
    
    def test_check_cooldown_after_expiry(self, mock_nats):
        """Use after cooldown expires is allowed."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 1})
        plugin.cooldowns["test_user"] = time.time() - 2  # 2 seconds ago
        assert plugin._check_cooldown("test_user") is True
    
    def test_cooldown_independent_per_user(self, mock_nats):
        """Different users have independent cooldowns."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 5})
        plugin._update_cooldown("user1")
        
        # user1 is on cooldown, user2 is not
        assert plugin._check_cooldown("user1") is False
        assert plugin._check_cooldown("user2") is True
    
    def test_get_cooldown_remaining(self, mock_nats):
        """Get remaining cooldown time."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 10})
        plugin.cooldowns["test_user"] = time.time() - 3  # 3 seconds ago
        
        remaining = plugin._get_cooldown_remaining("test_user")
        assert 6 <= remaining <= 8  # ~7 seconds remaining
    
    def test_get_cooldown_remaining_expired(self, mock_nats):
        """Remaining is 0 when cooldown expired."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 5})
        plugin.cooldowns["test_user"] = time.time() - 10  # 10 seconds ago
        
        remaining = plugin._get_cooldown_remaining("test_user")
        assert remaining == 0
    
    def test_cooldown_zero_always_allows(self, mock_nats):
        """Cooldown of 0 always allows."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 0})
        plugin._update_cooldown("test_user")
        assert plugin._check_cooldown("test_user") is True
    
    @pytest.mark.asyncio
    async def test_cooldown_blocks_request(self, mock_nats, mock_message):
        """Request on cooldown returns error."""
        plugin = EightBallPlugin(mock_nats, {"cooldown_seconds": 60})
        plugin._update_cooldown("test_user")
        
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "needs a moment to recover" in data["error"]


# =============================================================================
# Event Emission Tests
# =============================================================================

class TestEventEmission:
    """Tests for analytics event emission."""
    
    @pytest.mark.asyncio
    async def test_emits_event_on_success(self, mock_nats, mock_message):
        """Successful consultation emits event."""
        plugin = EightBallPlugin(mock_nats, {"emit_events": True})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Should have 2 publishes: response + event
        assert mock_nats.publish.call_count == 2
        
        # Second call is the event
        event_call = mock_nats.publish.call_args_list[1]
        subject = event_call[0][0]
        data = json.loads(event_call[0][1].decode())
        
        assert subject == "rosey.event.8ball.consulted"
        assert data["event"] == "8ball.consulted"
        assert data["channel"] == "test_channel"
        assert data["user"] == "test_user"
        assert "category" in data
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_no_event_when_disabled(self, mock_nats, mock_message):
        """No event emitted when emit_events=false."""
        plugin = EightBallPlugin(mock_nats, {"emit_events": False})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Only 1 publish (the response)
        assert mock_nats.publish.call_count == 1
    
    @pytest.mark.asyncio
    async def test_no_event_on_cooldown(self, mock_nats, mock_message):
        """No event emitted when blocked by cooldown."""
        plugin = EightBallPlugin(mock_nats, {"emit_events": True, "cooldown_seconds": 60})
        plugin._update_cooldown("test_user")
        
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Only 1 publish (the error response)
        assert mock_nats.publish.call_count == 1
    
    @pytest.mark.asyncio
    async def test_no_event_on_error(self, mock_nats, mock_message):
        """No event emitted when question required but missing."""
        plugin = EightBallPlugin(mock_nats, {"emit_events": True, "require_question": True})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Only 1 publish (the error response)
        assert mock_nats.publish.call_count == 1


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, mock_nats):
        """Invalid JSON is handled gracefully."""
        plugin = EightBallPlugin(mock_nats)
        
        msg = MagicMock()
        msg.data = b"not valid json"
        msg.reply = "rosey.reply.123"
        
        # Should not raise
        await plugin._handle_ask(msg)
    
    @pytest.mark.asyncio
    async def test_missing_fields(self, mock_nats, mock_message):
        """Missing fields use defaults."""
        plugin = EightBallPlugin(mock_nats, {"require_question": False})
        msg = mock_message({
            "args": "test",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_ask(msg)
        
        # Should succeed with defaults
        call_args = mock_nats.publish.call_args_list[0]
        data = json.loads(call_args[0][1].decode())
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_no_reply_to(self, mock_nats, mock_message):
        """Request without reply_to still processes."""
        plugin = EightBallPlugin(mock_nats, {"emit_events": False})
        msg = mock_message({
            "channel": "test_channel",
            "user": "test_user",
            "args": "Test?"
        })
        
        # Should not raise even without reply_to
        await plugin._handle_ask(msg)


# =============================================================================
# Direct API Tests
# =============================================================================

class TestDirectAPI:
    """Tests for direct (non-NATS) API methods."""
    
    def test_ask_returns_response(self, mock_nats):
        """ask() returns an EightBallResponse."""
        plugin = EightBallPlugin(mock_nats)
        from responses import EightBallResponse
        
        response = plugin.ask()
        assert isinstance(response, EightBallResponse)
    
    def test_ask_with_question(self, mock_nats):
        """ask() accepts optional question (unused in selection)."""
        plugin = EightBallPlugin(mock_nats)
        
        response = plugin.ask("Will I win?")
        assert response is not None
    
    def test_ask_formatted(self, mock_nats):
        """ask_formatted() returns ready-to-display string."""
        plugin = EightBallPlugin(mock_nats)
        
        result = plugin.ask_formatted("Will I win?")
        
        assert isinstance(result, str)
        assert "🎱" in result
        assert "Will I win?" in result
