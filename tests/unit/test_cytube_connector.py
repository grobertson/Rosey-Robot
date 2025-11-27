"""
Unit tests for Cytube connector.

Tests cover:
- CytubeEvent: Event normalization and conversion
- CytubeConnector: Bidirectional event translation
- Connection lifecycle and error handling
"""

import pytest
from unittest.mock import AsyncMock, Mock

from bot.rosey.core.cytube_connector import (
    CytubeEventType,
    CytubeEvent,
    CytubeConnector
)
from bot.rosey.core.event_bus import Event, EventBus, Priority
from bot.rosey.core.subjects import Subjects, EventTypes


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = AsyncMock(spec=EventBus)
    bus.subscribe = AsyncMock(return_value=1)
    bus.unsubscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_channel():
    """Mock Cytube channel"""
    channel = Mock()
    channel.name = "test-channel"
    channel.send_message = AsyncMock()
    channel.on = Mock()
    channel.off = Mock()
    return channel


# ============================================================================
# CytubeEvent Tests
# ============================================================================

class TestCytubeEvent:
    """Test Cytube event normalization"""

    def test_event_creation(self):
        """Test creating Cytube event"""
        event = CytubeEvent(
            event_type=CytubeEventType.CHAT_MSG,
            data={"username": "test", "message": "hello"}
        )

        assert event.event_type == CytubeEventType.CHAT_MSG
        assert event.data["username"] == "test"
        assert event.timestamp > 0

    def test_to_eventbus_event_chat(self):
        """Test converting chat message to EventBus event"""
        cytube_event = CytubeEvent(
            event_type=CytubeEventType.CHAT_MSG,
            data={"username": "user1", "message": "test"}
        )

        eb_event = cytube_event.to_event_bus_event()

        assert eb_event.event_type == EventTypes.MESSAGE
        assert eb_event.source == "cytube-connector"
        assert "cytube" in eb_event.subject
        assert eb_event.data["username"] == "user1"
        assert eb_event.priority == Priority.NORMAL

    def test_to_eventbus_event_error_priority(self):
        """Test error events get high priority"""
        cytube_event = CytubeEvent(
            event_type=CytubeEventType.ERROR,
            data={"error": "connection failed"}
        )

        eb_event = cytube_event.to_event_bus_event()

        assert eb_event.priority == Priority.HIGH

    def test_to_eventbus_event_with_correlation(self):
        """Test event with correlation ID"""
        cytube_event = CytubeEvent(
            event_type=CytubeEventType.USER_JOIN,
            data={"username": "newuser"}
        )

        eb_event = cytube_event.to_event_bus_event(correlation_id="test-123")

        assert eb_event.correlation_id == "test-123"

    def test_event_metadata(self):
        """Test event includes metadata"""
        cytube_event = CytubeEvent(
            event_type=CytubeEventType.CHANGE_MEDIA,
            data={"title": "test video"}
        )

        eb_event = cytube_event.to_event_bus_event()

        assert "cytube_event" in eb_event.metadata
        assert eb_event.metadata["cytube_event"] == "changeMedia"
        assert "timestamp" in eb_event.metadata


# ============================================================================
# CytubeConnector Tests
# ============================================================================

@pytest.mark.asyncio
class TestCytubeConnector:
    """Test Cytube connector"""

    async def test_connector_creation(self, mock_event_bus, mock_channel):
        """Test creating connector"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        assert connector.event_bus is mock_event_bus
        assert connector.channel is mock_channel
        assert connector.platform_name == "cytube"
        assert connector.is_running() is False

    async def test_custom_platform_name(self, mock_event_bus, mock_channel):
        """Test connector with custom platform name"""
        connector = CytubeConnector(
            mock_event_bus,
            mock_channel,
            platform_name="custom"
        )

        assert connector.platform_name == "custom"

    async def test_start_connector(self, mock_event_bus, mock_channel):
        """Test starting connector"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        success = await connector.start()

        assert success is True
        assert connector.is_running() is True
        # Should register handlers and subscribe to EventBus
        assert mock_channel.on.call_count >= 8  # Multiple event types
        assert mock_event_bus.subscribe.call_count == 3  # MESSAGE, PM, playlist commands

    async def test_start_already_running(self, mock_event_bus, mock_channel):
        """Test starting already running connector"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        await connector.start()
        success = await connector.start()

        assert success is False

    async def test_stop_connector(self, mock_event_bus, mock_channel):
        """Test stopping connector"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        await connector.start()
        success = await connector.stop()

        assert success is True
        assert connector.is_running() is False
        # Should unregister handlers and unsubscribe
        assert mock_channel.off.call_count >= 8
        assert mock_event_bus.unsubscribe.call_count == 3  # MESSAGE, PM, playlist commands

    async def test_handle_chat_message(self, mock_event_bus, mock_channel):
        """Test handling incoming chat message"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        chat_data = {
            "username": "testuser",
            "msg": "Hello world!",
            "time": 123456789,
            "meta": {}
        }

        await connector._on_chat_message(chat_data)

        # Should publish to EventBus
        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["username"] == "testuser"
        assert event.data["message"] == "Hello world!"

    async def test_handle_pm(self, mock_event_bus, mock_channel):
        """Test handling incoming private message"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        pm_data = {
            "username": "moduser",
            "msg": "status",
            "time": 123456789,
            "to": "botname"
        }

        await connector._on_pm(pm_data)

        # Should publish to EventBus with PM subject
        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.subject == "rosey.platform.cytube.pm"
        assert event.event_type == "message"
        assert event.metadata["cytube_event"] == "pm"
        assert event.data["username"] == "moduser"
        assert event.data["message"] == "status"
        assert event.data["recipient"] == "botname"

    async def test_handle_user_join(self, mock_event_bus, mock_channel):
        """Test handling user join event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        join_data = {
            "name": "newuser",
            "rank": 1,
            "profile": {"image": "avatar.png"}
        }

        await connector._on_user_join(join_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["username"] == "newuser"
        assert event.data["rank"] == 1

    async def test_handle_user_leave(self, mock_event_bus, mock_channel):
        """Test handling user leave event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        leave_data = {"name": "goneuser"}

        await connector._on_user_leave(leave_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["username"] == "goneuser"

    async def test_handle_user_count(self, mock_event_bus, mock_channel):
        """Test handling user count update"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        await connector._on_user_count(42)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["count"] == 42

    async def test_handle_change_media(self, mock_event_bus, mock_channel):
        """Test handling media change event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        media_data = {
            "title": "Test Video",
            "type": "yt",
            "id": "abc123",
            "seconds": 180
        }

        await connector._on_change_media(media_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["title"] == "Test Video"
        assert event.data["duration"] == 180

    async def test_handle_media_update(self, mock_event_bus, mock_channel):
        """Test handling media playback update"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        update_data = {
            "currentTime": 45.5,
            "paused": False
        }

        await connector._on_media_update(update_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["currentTime"] == 45.5
        assert event.data["paused"] is False

    async def test_handle_playlist(self, mock_event_bus, mock_channel):
        """Test handling playlist update"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        playlist_data = [
            {"title": "Video 1", "id": "1"},
            {"title": "Video 2", "id": "2"}
        ]

        await connector._on_playlist(playlist_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert len(event.data["playlist"]) == 2

    async def test_handle_queue(self, mock_event_bus, mock_channel):
        """Test handling video queue event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        queue_data = {
            "item": {"title": "Queued Video"},
            "after": "video-123"
        }

        await connector._on_queue(queue_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["item"]["title"] == "Queued Video"

    async def test_handle_delete(self, mock_event_bus, mock_channel):
        """Test handling video delete event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        delete_data = {"uid": "video-abc123"}

        await connector._on_delete(delete_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.subject == "rosey.platform.cytube.delete"
        assert event.data["uid"] == "video-abc123"
        assert connector._events_received == 1

    async def test_handle_delete_missing_uid(self, mock_event_bus, mock_channel):
        """Test handling delete event with missing uid"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        delete_data = {}

        await connector._on_delete(delete_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["uid"] == ""

    async def test_handle_move_video(self, mock_event_bus, mock_channel):
        """Test handling video move event"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        move_data = {
            "from": 3,
            "to": 1,
            "uid": "video-xyz789"
        }

        await connector._on_move_video(move_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.subject == "rosey.platform.cytube.moveVideo"
        assert event.data["from"] == 3
        assert event.data["to"] == 1
        assert event.data["uid"] == "video-xyz789"
        assert connector._events_received == 1

    async def test_handle_move_video_without_uid(self, mock_event_bus, mock_channel):
        """Test handling move event without uid (older CyTube versions)"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        move_data = {"from": 5, "to": 2}

        await connector._on_move_video(move_data)

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]
        assert event.data["from"] == 5
        assert event.data["to"] == 2
        assert event.data["uid"] == ""

    async def test_handle_delete_error(self, mock_event_bus, mock_channel):
        """Test error handling in delete handler"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Make publish raise an exception
        mock_event_bus.publish.side_effect = Exception("Publish failed")

        delete_data = {"uid": "test-uid"}

        await connector._on_delete(delete_data)

        assert connector._errors == 1

    async def test_handle_move_video_error(self, mock_event_bus, mock_channel):
        """Test error handling in moveVideo handler"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Make publish raise an exception
        mock_event_bus.publish.side_effect = Exception("Publish failed")

        move_data = {"from": 1, "to": 3, "uid": "test-uid"}

        await connector._on_move_video(move_data)

        assert connector._errors == 1

    async def test_send_chat_message(self, mock_event_bus, mock_channel):
        """Test sending chat message to Cytube"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        await connector._send_chat_message("Hello from bot!")

        mock_channel.send_message.assert_called_once_with("Hello from bot!")

    async def test_handle_eventbus_message(self, mock_event_bus, mock_channel):
        """Test handling message from EventBus"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="router",
            data={"message": "Test message"}
        )

        await connector._handle_eventbus_message(event)

        mock_channel.send_message.assert_called_once_with("Test message")

    async def test_handle_eventbus_command_chat(self, mock_event_bus, mock_channel):
        """Test handling chat command from EventBus"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.COMMAND}",
            event_type=EventTypes.COMMAND,
            source="plugin",
            data={"command": "chat:send", "message": "Command message"}
        )

        await connector._handle_eventbus_command(event)

        mock_channel.send_message.assert_called_once()

    async def test_get_statistics(self, mock_event_bus, mock_channel):
        """Test getting connector statistics"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        stats = connector.get_statistics()

        assert stats["running"] is False
        assert stats["events_received"] == 0
        assert stats["events_sent"] == 0
        assert stats["errors"] == 0

    async def test_statistics_tracking(self, mock_event_bus, mock_channel):
        """Test that statistics are tracked correctly"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Simulate events
        await connector._on_chat_message({
            "username": "user",
            "msg": "test",
            "time": 123,
            "meta": {}
        })

        await connector._send_chat_message("response")

        stats = connector.get_statistics()
        assert stats["events_received"] == 1
        assert stats["events_sent"] == 1

    async def test_get_channel_name(self, mock_event_bus, mock_channel):
        """Test getting channel name"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        assert connector.get_channel_name() == "test-channel"

    async def test_error_handling_chat(self, mock_event_bus, mock_channel):
        """Test error handling in chat message processing"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Simulate error in publish
        mock_event_bus.publish.side_effect = Exception("Publish failed")

        # Should not raise, but log error
        await connector._on_chat_message({
            "username": "user",
            "msg": "test",
            "time": 123,
            "meta": {}
        })

        stats = connector.get_statistics()
        assert stats["errors"] == 1

    async def test_empty_message_handling(self, mock_event_bus, mock_channel):
        """Test handling empty messages"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        await connector._send_chat_message("")

        # Should not send empty message
        mock_channel.send_message.assert_not_called()

    # Playlist Command Tests

    async def test_playlist_add_success(self, mock_event_bus, mock_channel):
        """Test adding video to playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.queue = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.add",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.add",
                "params": {
                    "type": "yt",
                    "id": "dQw4w9WgXcQ"
                }
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.queue.assert_called_once_with("yt", "dQw4w9WgXcQ")
        assert connector._events_sent == 1

    async def test_playlist_add_missing_params(self, mock_event_bus, mock_channel):
        """Test add command with missing parameters"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.add",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.add",
                "params": {
                    "type": "yt"
                    # Missing "id"
                }
            }
        )

        await connector._handle_playlist_command(event)

        # Should publish error
        assert mock_event_bus.publish.call_count >= 1
        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "type and id" in error_event.data["error"]

    async def test_playlist_remove_success(self, mock_event_bus, mock_channel):
        """Test removing video from playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.delete = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.remove",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.remove",
                "params": {"uid": "abc123"}
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.delete.assert_called_once_with("abc123")
        assert connector._events_sent == 1

    async def test_playlist_remove_missing_uid(self, mock_event_bus, mock_channel):
        """Test remove command with missing uid"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.remove",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.remove",
                "params": {}
            }
        )

        await connector._handle_playlist_command(event)

        # Should publish error
        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "uid" in error_event.data["error"]

    async def test_playlist_move_success(self, mock_event_bus, mock_channel):
        """Test moving video in playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.moveMedia = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.move",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.move",
                "params": {
                    "uid": "video1",
                    "after": "video2"
                }
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.moveMedia.assert_called_once_with("video1", "video2")
        assert connector._events_sent == 1

    async def test_playlist_move_missing_params(self, mock_event_bus, mock_channel):
        """Test move command with missing parameters"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.move",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.move",
                "params": {"uid": "video1"}
            }
        )

        await connector._handle_playlist_command(event)

        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "uid and after" in error_event.data["error"]

    async def test_playlist_jump_success(self, mock_event_bus, mock_channel):
        """Test jumping to video in playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.jumpTo = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.jump",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.jump",
                "params": {"uid": "abc123"}
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.jumpTo.assert_called_once_with("abc123")
        assert connector._events_sent == 1

    async def test_playlist_clear_success(self, mock_event_bus, mock_channel):
        """Test clearing playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.clearPlaylist = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.clear",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.clear",
                "params": {}
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.clearPlaylist.assert_called_once()
        assert connector._events_sent == 1

    async def test_playlist_shuffle_success(self, mock_event_bus, mock_channel):
        """Test shuffling playlist"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.shufflePlaylist = AsyncMock()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.shuffle",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.shuffle",
                "params": {}
            }
        )

        await connector._handle_playlist_command(event)

        mock_channel.shufflePlaylist.assert_called_once()
        assert connector._events_sent == 1

    async def test_playlist_command_not_connected(self, mock_event_bus, mock_channel):
        """Test playlist command when not connected"""
        connector = CytubeConnector(mock_event_bus, None)  # No channel
        await connector.start()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.add",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.add",
                "params": {"type": "yt", "id": "test"}
            }
        )

        await connector._handle_playlist_command(event)

        # Should publish error
        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "Not connected" in error_event.data["error"]

    async def test_playlist_command_unknown(self, mock_event_bus, mock_channel):
        """Test unknown playlist command"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        event = Event(
            subject="rosey.platform.cytube.send.playlist.invalid",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.invalid",
                "params": {}
            }
        )

        await connector._handle_playlist_command(event)

        # Should publish error
        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "Unknown" in error_event.data["error"]

    async def test_playlist_command_channel_error(self, mock_event_bus, mock_channel):
        """Test playlist command when channel method raises error"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        mock_channel.queue = AsyncMock(side_effect=Exception("Channel error"))

        event = Event(
            subject="rosey.platform.cytube.send.playlist.add",
            event_type="command",
            source="shell",
            data={
                "command": "playlist.add",
                "params": {"type": "yt", "id": "test"}
            }
        )

        await connector._handle_playlist_command(event)

        # Should publish error
        error_event = None
        for call in mock_event_bus.publish.call_args_list:
            evt = call[0][0]
            if evt.event_type == "error":
                error_event = evt
                break

        assert error_event is not None
        assert "Channel error" in error_event.data["error"]
        assert connector._errors == 1


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestCytubeConnectorIntegration:
    """Test connector integration scenarios"""

    async def test_full_message_flow(self, mock_event_bus, mock_channel):
        """Test complete message flow from Cytube to EventBus"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Simulate Cytube chat message
        await connector._on_chat_message({
            "username": "alice",
            "msg": "!help",
            "time": 123456,
            "meta": {}
        })

        # Should publish to EventBus
        assert mock_event_bus.publish.call_count == 1
        event = mock_event_bus.publish.call_args[0][0]

        # Verify event structure
        assert event.event_type == EventTypes.MESSAGE
        assert event.data["username"] == "alice"
        assert event.data["message"] == "!help"
        assert "cytube" in event.subject

    async def test_bidirectional_flow(self, mock_event_bus, mock_channel):
        """Test bidirectional message flow"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Incoming: Cytube -> EventBus
        await connector._on_chat_message({
            "username": "user",
            "msg": "hello",
            "time": 123,
            "meta": {}
        })

        # Outgoing: EventBus -> Cytube
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="bot",
            data={"message": "Hello back!"}
        )
        await connector._handle_eventbus_message(event)

        # Verify both directions
        assert mock_event_bus.publish.call_count == 1
        assert mock_channel.send_message.call_count == 1

        stats = connector.get_statistics()
        assert stats["events_received"] == 1
        assert stats["events_sent"] == 1

    async def test_multiple_event_types(self, mock_event_bus, mock_channel):
        """Test handling multiple event types"""
        connector = CytubeConnector(mock_event_bus, mock_channel)
        await connector.start()

        # Chat message
        await connector._on_chat_message({
            "username": "user1",
            "msg": "hi",
            "time": 1,
            "meta": {}
        })

        # User join
        await connector._on_user_join({
            "name": "user2",
            "rank": 1,
            "profile": {}
        })

        # Media change
        await connector._on_change_media({
            "title": "Video",
            "type": "yt",
            "id": "123",
            "seconds": 100
        })

        # Should publish all events
        assert mock_event_bus.publish.call_count == 3

        stats = connector.get_statistics()
        assert stats["events_received"] == 3

    async def test_lifecycle_management(self, mock_event_bus, mock_channel):
        """Test connector lifecycle management"""
        connector = CytubeConnector(mock_event_bus, mock_channel)

        # Start
        assert await connector.start() is True
        assert connector.is_running() is True

        # Process events
        await connector._on_chat_message({
            "username": "user",
            "msg": "test",
            "time": 123,
            "meta": {}
        })

        # Stop
        assert await connector.stop() is True
        assert connector.is_running() is False

        # Verify cleanup
        assert len(connector._subscriptions) == 0
        assert len(connector._event_handlers) == 0
