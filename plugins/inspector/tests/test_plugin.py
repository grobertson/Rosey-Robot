import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from plugins.inspector.plugin import InspectorPlugin


class TestInspectorPlugin:
    """Test InspectorPlugin integration."""

    @pytest.fixture
    def mock_nats(self):
        nats = AsyncMock()
        nats.subscribe = AsyncMock(return_value=MagicMock())
        nats.publish = AsyncMock()
        return nats

    @pytest.fixture
    def plugin(self, mock_nats):
        return InspectorPlugin(mock_nats)

    @pytest.mark.asyncio
    async def test_setup(self, plugin, mock_nats):
        """Test plugin initialization."""
        await plugin.initialize()
        
        # Should subscribe to wildcard >
        assert mock_nats.subscribe.called
        
        # Should register commands
        assert mock_nats.subscribe.call_count == 7

    @pytest.mark.asyncio
    async def test_capture_event(self, plugin):
        """Test event capturing."""
        msg = MagicMock()
        msg.subject = "test.event"
        msg.data = b'{"foo": "bar"}'
        
        await plugin._capture_event(msg)
        
        recent = plugin.buffer.get_recent()
        assert len(recent) == 1
        assert recent[0].subject == "test.event"
        assert recent[0].data_decoded == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_admin_check(self, plugin):
        """Test admin restriction."""
        # Configure admin
        plugin.config["admins"] = ["admin"]
        
        msg = MagicMock()
        msg.data = json.dumps({"user": "user"}).encode()
        msg.respond = AsyncMock()
        msg.reply = "test.reply"
        
        await plugin._handle_events(msg)
        
        # Should fail
        response = json.loads(plugin.nc.publish.call_args[0][1])
        assert response["success"] is False
        assert "Admin only" in response["error"]
        
        # Should succeed for admin
        msg.data = json.dumps({"user": "admin"}).encode()
        plugin.nc.publish.reset_mock()
        await plugin._handle_events(msg)
        
        response = json.loads(plugin.nc.publish.call_args[0][1])
        # Might be success or "No recent events", but not "Admin only"
        if not response["success"]:
            assert "Admin only" not in response.get("error", "")

    @pytest.mark.asyncio
    async def test_handle_stats(self, plugin):
        """Test stats command."""
        msg = MagicMock()
        msg.data = json.dumps({"user": "admin"}).encode()
        msg.reply = "test.reply"
        
        # Add some events
        event = MagicMock()
        event.subject = "test.a"
        plugin.buffer.append(event)
        
        await plugin._handle_stats(msg)
        
        # Decode bytes to string then parse JSON
        response_data = plugin.nc.publish.call_args[0][1].decode()
        response = json.loads(response_data)
        assert response["success"] is True
        assert "Total Events: 1" in response["result"]["message"]
