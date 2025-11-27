"""
tests/test_plugin.py

Integration tests for the CountdownPlugin.

Tests cover:
- Plugin initialization and shutdown
- NATS subscription management
- Command handling (create, check, list, delete)
- Storage operations via NATS
- Event emission
- Error handling
"""

import json
import pytest

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugin import CountdownPlugin


# =============================================================================
# Plugin Initialization Tests
# =============================================================================

class TestPluginInit:
    """Tests for plugin initialization."""
    
    def test_init_with_defaults(self, mock_nats):
        """Plugin initializes with default config."""
        plugin = CountdownPlugin(mock_nats)
        
        assert plugin.check_interval == 30.0
        assert plugin.max_countdowns_per_channel == 20
        assert plugin.max_duration_days == 365
        assert plugin.emit_events is True
    
    def test_init_with_custom_config(self, mock_nats):
        """Plugin respects custom configuration."""
        config = {
            "check_interval": 60.0,
            "max_countdowns_per_channel": 10,
            "max_duration_days": 30,
            "emit_events": False,
        }
        plugin = CountdownPlugin(mock_nats, config)
        
        assert plugin.check_interval == 60.0
        assert plugin.max_countdowns_per_channel == 10
        assert plugin.max_duration_days == 30
        assert plugin.emit_events is False
    
    def test_init_has_namespace(self, mock_nats):
        """Plugin has namespace set."""
        plugin = CountdownPlugin(mock_nats)
        assert plugin.NAMESPACE == "countdown"
    
    def test_init_has_version(self, mock_nats):
        """Plugin has version set."""
        plugin = CountdownPlugin(mock_nats)
        assert plugin.VERSION == "2.0.0"


# =============================================================================
# Plugin Lifecycle Tests
# =============================================================================

class TestPluginLifecycle:
    """Tests for plugin lifecycle (initialize/shutdown)."""
    
    @pytest.mark.asyncio
    async def test_initialize_subscribes(self, mock_nats):
        """initialize() subscribes to NATS subjects."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        # Should have subscribed to 7 command subjects
        assert len(mock_nats._subscriptions) == 7
        
        subjects = [s.subject for s in mock_nats._subscriptions]
        assert "rosey.command.countdown.create" in subjects
        assert "rosey.command.countdown.check" in subjects
        assert "rosey.command.countdown.list" in subjects
        assert "rosey.command.countdown.delete" in subjects
        assert "rosey.command.countdown.alerts" in subjects
        assert "rosey.command.countdown.pause" in subjects
        assert "rosey.command.countdown.resume" in subjects
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_initialize_starts_scheduler(self, mock_nats):
        """initialize() starts the scheduler."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        assert plugin.scheduler is not None
        assert plugin.scheduler.running is True
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_shutdown_stops_scheduler(self, mock_nats):
        """shutdown() stops the scheduler."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        scheduler = plugin.scheduler
        await plugin.shutdown()
        
        assert scheduler.running is False
    
    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes(self, mock_nats):
        """shutdown() unsubscribes from all subjects."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        subs = mock_nats._subscriptions.copy()
        await plugin.shutdown()
        
        # Each subscription should have been unsubscribed
        for sub in subs:
            sub.unsubscribe.assert_called_once()


# =============================================================================
# Create Command Tests
# =============================================================================

class TestHandleCreate:
    """Tests for _handle_create command handler."""
    
    @pytest.mark.asyncio
    async def test_create_success(self, mock_nats, mock_message):
        """Successful create returns response."""
        plugin = CountdownPlugin(mock_nats, {"emit_events": False})
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "test_event 2025-12-25 20:00",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_create(msg)
        
        # Should have published response
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        subject = call_args[0][0]
        data = json.loads(call_args[0][1].decode())
        
        assert subject == "rosey.reply.123"
        assert data["success"] is True
        assert data["result"]["name"] == "test_event"
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_create_missing_args(self, mock_nats, mock_message):
        """Create with missing args returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_create(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "Usage" in data["error"]
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_create_invalid_name(self, mock_nats, mock_message):
        """Create with invalid name returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        # Name with special characters (first word parsed as name)
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "bad! 2025-12-25 20:00",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_create(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "Invalid name" in data["error"]
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_create_invalid_datetime(self, mock_nats, mock_message):
        """Create with invalid datetime returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "test not_a_date",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_create(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "Couldn't parse" in data["error"]
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_create_past_time(self, mock_nats, mock_message):
        """Create with past time returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "test 2020-01-01 12:00",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_create(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "already passed" in data["error"]
        
        await plugin.shutdown()


# =============================================================================
# Check Command Tests
# =============================================================================

class TestHandleCheck:
    """Tests for _handle_check command handler."""
    
    @pytest.mark.asyncio
    async def test_check_not_found(self, mock_nats, mock_message):
        """Check nonexistent countdown returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "nonexistent",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_check(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "No countdown named" in data["error"]
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_check_missing_name(self, mock_nats, mock_message):
        """Check without name returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_check(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "Usage" in data["error"]
        
        await plugin.shutdown()


# =============================================================================
# List Command Tests
# =============================================================================

class TestHandleList:
    """Tests for _handle_list command handler."""
    
    @pytest.mark.asyncio
    async def test_list_empty(self, mock_nats, mock_message):
        """List with no countdowns returns empty."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_list(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is True
        assert data["result"]["countdowns"] == []
        assert "No active countdowns" in data["result"]["message"]
        
        await plugin.shutdown()


# =============================================================================
# Delete Command Tests
# =============================================================================

class TestHandleDelete:
    """Tests for _handle_delete command handler."""
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_nats, mock_message):
        """Delete nonexistent countdown returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "nonexistent",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_delete(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "No countdown named" in data["error"]
        
        await plugin.shutdown()
    
    @pytest.mark.asyncio
    async def test_delete_missing_name(self, mock_nats, mock_message):
        """Delete without name returns error."""
        plugin = CountdownPlugin(mock_nats)
        await plugin.initialize()
        
        msg = mock_message({
            "channel": "lobby",
            "user": "testuser",
            "args": "",
            "reply_to": "rosey.reply.123"
        })
        
        await plugin._handle_delete(msg)
        
        call_args = mock_nats.publish.call_args
        data = json.loads(call_args[0][1].decode())
        
        assert data["success"] is False
        assert "Usage" in data["error"]
        
        await plugin.shutdown()


# =============================================================================
# Name Validation Tests
# =============================================================================

class TestNameValidation:
    """Tests for countdown name validation."""
    
    def test_valid_names(self, mock_nats):
        """Valid names pass validation."""
        plugin = CountdownPlugin(mock_nats)
        
        assert plugin._validate_name("movie_night") is True
        assert plugin._validate_name("test123") is True
        assert plugin._validate_name("a") is True
        assert plugin._validate_name("my_countdown_2025") is True
    
    def test_invalid_names(self, mock_nats):
        """Invalid names fail validation."""
        plugin = CountdownPlugin(mock_nats)
        
        assert plugin._validate_name("") is False
        assert plugin._validate_name("has space") is False
        assert plugin._validate_name("has-dash") is False
        assert plugin._validate_name("UPPERCASE") is False
        assert plugin._validate_name("special!@#") is False
        assert plugin._validate_name("a" * 51) is False  # Too long
