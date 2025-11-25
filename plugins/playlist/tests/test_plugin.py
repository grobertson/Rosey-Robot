"""
Tests for playlist plugin NATS integration.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY

from models import MediaType
from plugin import PlaylistPlugin


@pytest.fixture
def mock_msg():
    """Create a mock NATS message."""
    msg = MagicMock()
    msg.reply = "reply.subject"
    msg.data = b'{"channel": "test-channel", "user": "testuser", "args": ""}'
    return msg


@pytest.mark.asyncio
class TestPlaylistPlugin:
    """Test PlaylistPlugin NATS integration."""
    
    async def test_plugin_initialization(self, mock_nats, playlist_config):
        """Test plugin initializes correctly."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        assert plugin.NAMESPACE == "playlist"
        assert plugin.max_queue_size == 100
        assert plugin.max_items_per_user == 5
        assert "admin1" in plugin.admins
    
    async def test_plugin_setup(self, mock_nats, playlist_config):
        """Test plugin setup subscribes to subjects."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Should subscribe to 7 subjects
        assert mock_nats.subscribe.call_count == 7
        
        # Check subject names
        subjects = [call[0][0] for call in mock_nats.subscribe.call_args_list]
        assert "rosey.command.playlist.add" in subjects
        assert "rosey.command.playlist.queue" in subjects
        assert "rosey.command.playlist.skip" in subjects
        assert "rosey.command.playlist.remove" in subjects
        assert "rosey.command.playlist.clear" in subjects
        assert "rosey.command.playlist.shuffle" in subjects
        assert "rosey.command.playlist.move" in subjects
    
    async def test_plugin_teardown(self, mock_nats, playlist_config):
        """Test plugin teardown unsubscribes."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Mock subscriptions
        for _ in range(7):
            sub = MagicMock()
            sub.unsubscribe = AsyncMock()
            plugin._subscriptions.append(sub)
        
        await plugin.teardown()
        
        # All subscriptions should be unsubscribed
        for sub in plugin._subscriptions[:7]:
            sub.unsubscribe.assert_called_once()
    
    async def test_handle_add_success(self, mock_nats, playlist_config, mock_msg):
        """Test adding item successfully."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Update message with valid YouTube URL
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": "https://youtube.com/watch?v=dQw4w9WgXcQ"
        }).encode()
        
        await plugin._handle_add(mock_msg)
        
        # Should have called publish at least once (for reply)
        assert mock_nats.publish.called
        
        # Find the reply message (sent to mock_msg.reply)
        reply_calls = [c for c in mock_nats.publish.call_args_list 
                       if c[0][0] == mock_msg.reply]
        assert len(reply_calls) > 0
        
        response = json.loads(reply_calls[0][0][1].decode())
        assert response["success"] is True
        assert "Added to queue" in response["message"]
        assert "item" in response["data"]
    
    async def test_handle_add_no_url(self, mock_nats, playlist_config, mock_msg):
        """Test adding without URL gives error."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        await plugin._handle_add(mock_msg)
        
        # Should send error response
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is False
        assert "Usage" in response["error"]
    
    async def test_handle_add_invalid_url(self, mock_nats, playlist_config, mock_msg):
        """Test adding invalid URL gives error."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": "https://example.com/not-a-video"
        }).encode()
        
        await plugin._handle_add(mock_msg)
        
        # Should send error response
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is False
        assert "Unrecognized" in response["error"]
    
    async def test_handle_add_user_limit(self, mock_nats, playlist_config, mock_msg):
        """Test adding beyond user limit gives error."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add 5 items (max per user)
        for i in range(5):
            mock_msg.data = json.dumps({
                "channel": "test-channel",
                "user": "testuser",
                "args": f"https://youtube.com/watch?v=test{i}"
            }).encode()
            await plugin._handle_add(mock_msg)
        
        # Try to add 6th item
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": "https://youtube.com/watch?v=test6"
        }).encode()
        await plugin._handle_add(mock_msg)
        
        # Last call should be error
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is False
        assert "already have" in response["error"]
    
    async def test_handle_queue_empty(self, mock_nats, playlist_config, mock_msg):
        """Test queue command on empty queue."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        await plugin._handle_queue(mock_msg)
        
        # Should send success with empty message
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is True
        assert "empty" in response["message"].lower()
    
    async def test_handle_queue_with_items(self, mock_nats, playlist_config, mock_msg):
        """Test queue command with items."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add items
        for i in range(3):
            add_msg = MagicMock()
            add_msg.reply = "reply"
            add_msg.data = json.dumps({
                "channel": "test-channel",
                "user": f"user{i}",
                "args": f"https://youtube.com/watch?v=test{i}"
            }).encode()
            await plugin._handle_add(add_msg)
        
        # Get queue
        await plugin._handle_queue(mock_msg)
        
        # Should include queue display
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is True
        assert "Playlist" in response["message"]
        assert "upcoming" in response["data"]
    
    async def test_handle_skip_no_current(self, mock_nats, playlist_config, mock_msg):
        """Test skip with nothing playing."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        await plugin._handle_skip(mock_msg)
        
        # Should send error
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is False
        assert "Nothing is playing" in response["error"]
    
    async def test_handle_remove(self, mock_nats, playlist_config, mock_msg):
        """Test removing item."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add item
        add_msg = MagicMock()
        add_msg.reply = "add.reply"
        add_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": "https://youtube.com/watch?v=test1"
        }).encode()
        await plugin._handle_add(add_msg)
        
        # Remove user's last item
        mock_msg.reply = "remove.reply"
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": ""
        }).encode()
        await plugin._handle_remove(mock_msg)
        
        # Find remove reply
        reply_calls = [c for c in mock_nats.publish.call_args_list 
                       if c[0][0] == "remove.reply"]
        assert len(reply_calls) > 0
        
        response = json.loads(reply_calls[0][0][1].decode())
        assert response["success"] is True
        assert "Removed" in response["message"]
    
    async def test_handle_clear_not_admin(self, mock_nats, playlist_config, mock_msg):
        """Test clear command by non-admin."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        await plugin._handle_clear(mock_msg)
        
        # Should send error
        mock_nats.publish.assert_called()
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is False
        assert "Admin only" in response["error"]
    
    async def test_handle_clear_admin(self, mock_nats, playlist_config, mock_msg):
        """Test clear command by admin."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add items
        for i in range(3):
            add_msg = MagicMock()
            add_msg.reply = f"add{i}.reply"
            add_msg.data = json.dumps({
                "channel": "test-channel",
                "user": f"user{i}",
                "args": f"https://youtube.com/watch?v=test{i}"
            }).encode()
            await plugin._handle_add(add_msg)
        
        # Clear as admin
        mock_msg.reply = "clear.reply"
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "admin1",
            "args": ""
        }).encode()
        await plugin._handle_clear(mock_msg)
        
        # Find clear reply
        reply_calls = [c for c in mock_nats.publish.call_args_list 
                       if c[0][0] == "clear.reply"]
        assert len(reply_calls) > 0
        
        response = json.loads(reply_calls[0][0][1].decode())
        assert response["success"] is True
        assert "Cleared" in response["message"]
        assert response["data"]["count"] == 3
    
    async def test_handle_shuffle(self, mock_nats, playlist_config, mock_msg):
        """Test shuffle command."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add multiple items
        for i in range(5):
            add_msg = MagicMock()
            add_msg.reply = "reply"
            add_msg.data = json.dumps({
                "channel": "test-channel",
                "user": f"user{i}",
                "args": f"https://youtube.com/watch?v=test{i}"
            }).encode()
            await plugin._handle_add(add_msg)
        
        # Shuffle
        await plugin._handle_shuffle(mock_msg)
        
        # Should send success
        call_args = mock_nats.publish.call_args
        response = json.loads(call_args[0][1].decode())
        
        assert response["success"] is True
        assert "Shuffled" in response["message"]
    
    async def test_channel_isolation(self, mock_nats, playlist_config):
        """Test that channels have isolated queues."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add item to channel 1
        msg1 = MagicMock()
        msg1.reply = "reply"
        msg1.data = json.dumps({
            "channel": "channel1",
            "user": "user1",
            "args": "https://youtube.com/watch?v=test1"
        }).encode()
        await plugin._handle_add(msg1)
        
        # Add item to channel 2
        msg2 = MagicMock()
        msg2.reply = "reply"
        msg2.data = json.dumps({
            "channel": "channel2",
            "user": "user2",
            "args": "https://youtube.com/watch?v=test2"
        }).encode()
        await plugin._handle_add(msg2)
        
        # Each channel should have its own queue
        assert "channel1" in plugin.queues
        assert "channel2" in plugin.queues
        assert plugin.queues["channel1"].length == 1
        assert plugin.queues["channel2"].length == 1
    
    async def test_event_emission(self, mock_nats, playlist_config, mock_msg):
        """Test that events are emitted."""
        plugin = PlaylistPlugin(mock_nats, playlist_config)
        await plugin.setup()
        
        # Add item (should emit event)
        mock_msg.data = json.dumps({
            "channel": "test-channel",
            "user": "testuser",
            "args": "https://youtube.com/watch?v=test1"
        }).encode()
        await plugin._handle_add(mock_msg)
        
        # Should publish to both reply and event subjects
        assert mock_nats.publish.call_count >= 2
        
        # Check for event publication
        event_calls = [call for call in mock_nats.publish.call_args_list 
                       if "playlist.item.added" in str(call)]
        assert len(event_calls) > 0
