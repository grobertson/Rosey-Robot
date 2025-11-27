"""
Cytube platform connector for Rosey Bot.

Bridges Cytube WebSocket events to the EventBus, translating between
Cytube's protocol and our internal NATS-based event system.

Key responsibilities:
- Connect to Cytube via existing channel interface
- Translate Cytube events to EventBus messages
- Translate EventBus commands to Cytube actions
- Handle connection lifecycle and errors
- Maintain event correlation
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum

from .event_bus import EventBus, Event, Priority
from .subjects import Subjects, EventTypes, build_platform_subject


logger = logging.getLogger(__name__)


# ============================================================================
# Cytube Event Types
# ============================================================================

class CytubeEventType(Enum):
    """Cytube WebSocket event types"""
    # Chat events
    CHAT_MSG = "chatMsg"
    PM = "pm"
    USER_JOIN = "addUser"
    USER_LEAVE = "userLeave"
    USER_COUNT = "usercount"

    # Media events
    CHANGE_MEDIA = "changeMedia"
    MEDIA_UPDATE = "mediaUpdate"
    PLAYLIST = "playlist"
    QUEUE = "queue"
    DELETE = "delete"
    MOVE_VIDEO = "moveVideo"

    # Channel events
    SET_MOTD = "setMotd"
    ANNOUNCEMENT = "announcement"
    DRAIN_ENABLED = "drinkCount"

    # User events
    SET_LEADER = "setLeader"
    SET_AFK = "setAFK"
    CHAT_FILTERS = "chatFilters"

    # Connection events
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ERROR = "error"


@dataclass
class CytubeEvent:
    """Normalized Cytube event"""
    event_type: CytubeEventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    def to_event_bus_event(self, correlation_id: Optional[str] = None) -> Event:
        """Convert to EventBus event"""
        # Map Cytube event to EventBus subject and type
        subject = build_platform_subject("cytube", self.event_type.value)

        # Determine priority based on event type
        priority = Priority.NORMAL
        if self.event_type in (CytubeEventType.ERROR, CytubeEventType.DISCONNECT):
            priority = Priority.HIGH
        elif self.event_type == CytubeEventType.CHAT_MSG:
            priority = Priority.NORMAL

        return Event(
            subject=subject,
            event_type=EventTypes.MESSAGE,
            source="cytube-connector",
            data=self.data,
            correlation_id=correlation_id,
            priority=priority,
            metadata={
                "cytube_event": self.event_type.value,
                "timestamp": self.timestamp
            }
        )


# ============================================================================
# Cytube Connector
# ============================================================================

class CytubeConnector:
    """
    Connects Cytube WebSocket events to EventBus.

    Acts as a bidirectional translator:
    - Cytube events → EventBus messages
    - EventBus commands → Cytube actions
    """

    def __init__(
        self,
        event_bus: EventBus,
        channel: Any,  # cytube_bot.Channel instance
        platform_name: str = "cytube"
    ):
        """
        Initialize Cytube connector.

        Args:
            event_bus: EventBus for internal communication
            channel: Cytube channel instance (from cytube_bot_async)
            platform_name: Platform identifier (default: cytube)
        """
        self.event_bus = event_bus
        self.channel = channel
        self.platform_name = platform_name

        # Connection state
        self._running = False
        self._subscriptions: List[int] = []
        self._event_handlers: Dict[str, Callable] = {}

        # Statistics
        self._events_received = 0
        self._events_sent = 0
        self._errors = 0

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def start(self) -> bool:
        """
        Start the connector.

        Registers Cytube event handlers and subscribes to EventBus.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Connector already running")
            return False

        try:
            # Register Cytube event handlers
            self._register_cytube_handlers()

            # Subscribe to EventBus commands for this platform
            pattern = f"{Subjects.PLATFORM}.{self.platform_name}.{EventTypes.COMMAND}"
            sub_id = await self.event_bus.subscribe(
                pattern,
                self._handle_eventbus_command
            )
            self._subscriptions.append(sub_id)

            # Subscribe to send requests
            pattern = f"{Subjects.PLATFORM}.{self.platform_name}.{EventTypes.MESSAGE}"
            sub_id = await self.event_bus.subscribe(
                pattern,
                self._handle_eventbus_message
            )
            self._subscriptions.append(sub_id)

            # Subscribe to playlist commands
            pattern = f"{Subjects.PLATFORM}.{self.platform_name}.send.playlist.*"
            sub_id = await self.event_bus.subscribe(
                pattern,
                self._handle_playlist_command
            )
            self._subscriptions.append(sub_id)

            self._running = True
            logger.info(f"Cytube connector started for channel: {self.channel.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start connector: {e}")
            return False

    async def stop(self) -> bool:
        """
        Stop the connector.

        Unregisters handlers and unsubscribes from EventBus.

        Returns:
            True if stopped successfully
        """
        if not self._running:
            return True

        try:
            # Unregister Cytube handlers
            self._unregister_cytube_handlers()

            # Unsubscribe from EventBus
            for sub_id in self._subscriptions:
                await self.event_bus.unsubscribe(sub_id)

            self._subscriptions.clear()
            self._running = False
            logger.info("Cytube connector stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop connector: {e}")
            return False

    # ========================================================================
    # Cytube Event Handling (Incoming)
    # ========================================================================

    def _register_cytube_handlers(self) -> None:
        """Register handlers for Cytube events"""
        # Chat events
        self.channel.on("chatMsg", self._on_chat_message)
        self.channel.on("pm", self._on_pm)
        self.channel.on("addUser", self._on_user_join)
        self.channel.on("userLeave", self._on_user_leave)
        self.channel.on("usercount", self._on_user_count)

        # Media events
        self.channel.on("changeMedia", self._on_change_media)
        self.channel.on("mediaUpdate", self._on_media_update)
        self.channel.on("playlist", self._on_playlist)
        self.channel.on("queue", self._on_queue)
        self.channel.on("delete", self._on_delete)
        self.channel.on("moveVideo", self._on_move_video)

        # Store handlers for cleanup
        self._event_handlers = {
            "chatMsg": self._on_chat_message,
            "pm": self._on_pm,
            "addUser": self._on_user_join,
            "userLeave": self._on_user_leave,
            "usercount": self._on_user_count,
            "changeMedia": self._on_change_media,
            "mediaUpdate": self._on_media_update,
            "playlist": self._on_playlist,
            "queue": self._on_queue,
            "delete": self._on_delete,
            "moveVideo": self._on_move_video,
        }

    def _unregister_cytube_handlers(self) -> None:
        """Unregister handlers for Cytube events"""
        for event_name, handler in self._event_handlers.items():
            self.channel.off(event_name, handler)
        self._event_handlers.clear()

    async def _on_chat_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming chat message"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.CHAT_MSG,
                data={
                    "username": data.get("username", ""),
                    "message": data.get("msg", ""),
                    "time": data.get("time", 0),
                    "meta": data.get("meta", {}),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            self._errors += 1

    async def _on_pm(self, data: Dict[str, Any]) -> None:
        """Handle incoming private message"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.PM,
                data={
                    "username": data.get("username", ""),
                    "message": data.get("msg", ""),
                    "time": data.get("time", 0),
                    "recipient": data.get("to", ""),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling private message: {e}")
            self._errors += 1

    async def _on_user_join(self, data: Dict[str, Any]) -> None:
        """Handle user join event"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.USER_JOIN,
                data={
                    "username": data.get("name", ""),
                    "rank": data.get("rank", 0),
                    "profile": data.get("profile", {}),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling user join: {e}")
            self._errors += 1

    async def _on_user_leave(self, data: Dict[str, Any]) -> None:
        """Handle user leave event"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.USER_LEAVE,
                data={"username": data.get("name", "")}
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling user leave: {e}")
            self._errors += 1

    async def _on_user_count(self, data: Dict[str, Any]) -> None:
        """Handle user count update"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.USER_COUNT,
                data={"count": data}
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling user count: {e}")
            self._errors += 1

    async def _on_change_media(self, data: Dict[str, Any]) -> None:
        """Handle media change event"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.CHANGE_MEDIA,
                data={
                    "title": data.get("title", ""),
                    "type": data.get("type", ""),
                    "id": data.get("id", ""),
                    "duration": data.get("seconds", 0),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling media change: {e}")
            self._errors += 1

    async def _on_media_update(self, data: Dict[str, Any]) -> None:
        """Handle media playback update"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.MEDIA_UPDATE,
                data={
                    "currentTime": data.get("currentTime", 0),
                    "paused": data.get("paused", False),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling media update: {e}")
            self._errors += 1

    async def _on_playlist(self, data: List[Dict[str, Any]]) -> None:
        """Handle full playlist update"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.PLAYLIST,
                data={"playlist": data}
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling playlist: {e}")
            self._errors += 1

    async def _on_queue(self, data: Dict[str, Any]) -> None:
        """Handle video queue event"""
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.QUEUE,
                data={
                    "item": data.get("item", {}),
                    "after": data.get("after", ""),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling queue: {e}")
            self._errors += 1

    async def _on_delete(self, data: Dict[str, Any]) -> None:
        """Handle video delete event
        
        Args:
            data: Delete event data from CyTube containing uid of deleted item
        """
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.DELETE,
                data={
                    "uid": data.get("uid", ""),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling delete: {e}")
            self._errors += 1

    async def _on_move_video(self, data: Dict[str, Any]) -> None:
        """Handle video move event from CyTube.
        
        Called when a video's position changes in the playlist via CyTube UI or API.
        Publishes normalized event to EventBus for subscribers.
        
        Args:
            data: Move event data from CyTube server
                - from (int): Original position in playlist (0-indexed)
                - to (int): New position in playlist (0-indexed)
                - uid (str, optional): Unique identifier of the moved video
        
        Raises:
            Exception: Logged and tracked in error count if event handling fails
        """
        try:
            event = CytubeEvent(
                event_type=CytubeEventType.MOVE_VIDEO,
                data={
                    "from": data.get("from", 0),
                    "to": data.get("to", 0),
                    "uid": data.get("uid", ""),
                }
            )
            await self._publish_to_eventbus(event)
            self._events_received += 1

        except Exception as e:
            logger.error(f"Error handling moveVideo: {e}")
            self._errors += 1

    async def _publish_to_eventbus(self, cytube_event: CytubeEvent) -> None:
        """Publish Cytube event to EventBus"""
        event = cytube_event.to_event_bus_event()
        await self.event_bus.publish(event)
        logger.debug(f"Published Cytube event to EventBus: {cytube_event.event_type.value}")

    # ========================================================================
    # EventBus Command Handling (Outgoing)
    # ========================================================================

    async def _handle_eventbus_command(self, event: Event) -> None:
        """Handle commands from EventBus to send to Cytube"""
        try:
            command = event.data.get("command", "")
            if not command:
                return

            # Route to appropriate Cytube action
            if command.startswith("chat:"):
                await self._send_chat_message(event.data.get("message", ""))
            elif command == "skip":
                await self._skip_video()
            elif command == "leader":
                await self._take_leader()
            else:
                logger.warning(f"Unknown command: {command}")

        except Exception as e:
            logger.error(f"Error handling EventBus command: {e}")
            self._errors += 1

    async def _handle_eventbus_message(self, event: Event) -> None:
        """Handle message send requests from EventBus"""
        try:
            message = event.data.get("message", "")
            if message:
                await self._send_chat_message(message)

        except Exception as e:
            logger.error(f"Error handling EventBus message: {e}")
            self._errors += 1

    async def _send_chat_message(self, message: str) -> None:
        """Send chat message to Cytube"""
        if not message:
            return

        try:
            await self.channel.send_message(message)
            self._events_sent += 1
            logger.debug(f"Sent chat message: {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}")
            self._errors += 1
            raise

    # ========================================================================
    # Playlist Command Handling
    # ========================================================================

    async def _handle_playlist_command(self, event: Event) -> None:
        """Handle playlist commands from EventBus.
        
        Central dispatcher for all playlist manipulation commands. Routes incoming
        commands to specialized handlers based on command type. Commands are
        fire-and-forget; errors are published as separate events.
        
        Supported Commands:
            - playlist.add: Add video to playlist
            - playlist.remove: Remove video by UID
            - playlist.move: Reorder video position
            - playlist.jump: Jump to specific video
            - playlist.clear: Remove all videos
            - playlist.shuffle: Randomize playlist order
        
        Args:
            event: Event from NATS with structure:
                - subject: rosey.platform.cytube.send.playlist.*
                - data.command (str): Command name (e.g., "playlist.add")
                - data.params (dict): Command-specific parameters
                - correlation_id (str): For tracing and error correlation
        
        Raises:
            Exception: Logged and error event published if handling fails
        """
        try:
            # Check if connected
            if not self.channel:
                await self._publish_playlist_error(
                    event,
                    "Not connected to CyTube server"
                )
                return

            # Extract command
            command = event.data.get("command", "")
            if not command:
                logger.warning("Received playlist event with no command")
                return

            # Route to appropriate handler
            if command == "playlist.add":
                await self._playlist_add(event)
            elif command == "playlist.remove":
                await self._playlist_remove(event)
            elif command == "playlist.move":
                await self._playlist_move(event)
            elif command == "playlist.jump":
                await self._playlist_jump(event)
            elif command == "playlist.clear":
                await self._playlist_clear(event)
            elif command == "playlist.shuffle":
                await self._playlist_shuffle(event)
            else:
                await self._publish_playlist_error(
                    event,
                    f"Unknown playlist command: {command}"
                )
                logger.warning(f"Unknown playlist command: {command}")

        except Exception as e:
            logger.error(f"Error handling playlist command: {e}")
            await self._publish_playlist_error(event, str(e))
            self._errors += 1

    async def _publish_playlist_error(self, event: Event, error_message: str) -> None:
        """Publish error event for failed playlist command.
        
        Creates and publishes an error event to the error subject with full context
        from the original command, including correlation ID for tracing.
        
        Args:
            event: Original command event that failed
            error_message: Human-readable error description
        
        Published Event Structure:
            - subject: rosey.platform.cytube.error
            - event_type: "error"
            - data.command: Original command name
            - data.error: Error message
            - data.original_subject: Subject of failed command
            - data.correlation_id: Matches original event
        
        Raises:
            Exception: Logged if error event publication fails (non-fatal)
        """
        try:
            error_event = Event(
                subject=f"{Subjects.PLATFORM}.{self.platform_name}.error",
                event_type="error",
                source="cytube-connector",
                data={
                    "command": event.data.get("command", "unknown"),
                    "error": error_message,
                    "original_subject": event.subject,
                    "correlation_id": event.correlation_id
                },
                correlation_id=event.correlation_id
            )
            await self.event_bus.publish(error_event)
            logger.error(f"Playlist command error: {error_message} (correlation: {event.correlation_id})")
        except Exception as e:
            logger.error(f"Failed to publish error event: {e}")

    async def _playlist_add(self, event: Event) -> None:
        """Add video to playlist via CyTube queue API.
        
        Validates required parameters and calls channel.queue() to add video.
        Video is appended to end of playlist by default.
        
        Args:
            event: Command event with data structure:
                - params.type (str): Media type (yt, dm, vi, etc.)
                - params.id (str): Video ID for the specified type
                - params.position (str, optional): Position hint (default: "end")
                - params.temporary (bool, optional): Temp flag (default: true)
        
        CyTube API: channel.queue(type, id)
        
        Raises:
            Error event published if parameters missing or queue operation fails
        """
        try:
            params = event.data.get("params", {})
            video_type = params.get("type")
            video_id = params.get("id")

            if not video_type or not video_id:
                await self._publish_playlist_error(
                    event,
                    "Missing required parameters: type and id"
                )
                return

            await self.channel.queue(video_type, video_id)
            self._events_sent += 1
            logger.debug(f"Added video to playlist: {video_type}:{video_id}")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to add video: {e}")
            self._errors += 1

    async def _playlist_remove(self, event: Event) -> None:
        """Remove video from playlist via CyTube delete API.
        
        Validates required UID parameter and calls channel.delete() to remove video.
        
        Args:
            event: Command event with data structure:
                - params.uid (str): Unique identifier of video to remove
        
        CyTube API: channel.delete(uid)
        
        Raises:
            Error event published if UID missing or delete operation fails
        """
        try:
            params = event.data.get("params", {})
            uid = params.get("uid")

            if not uid:
                await self._publish_playlist_error(
                    event,
                    "Missing required parameter: uid"
                )
                return

            await self.channel.delete(uid)
            self._events_sent += 1
            logger.debug(f"Removed video from playlist: {uid}")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to remove video: {e}")
            self._errors += 1

    async def _playlist_move(self, event: Event) -> None:
        """Move video to new position in playlist via CyTube moveMedia API.
        
        Validates required parameters and calls channel.moveMedia(). The "after"
        parameter specifies the UID of the video to place this video after.
        Special value "prepend" moves video to the beginning of the playlist.
        
        Args:
            event: Command event with data structure:
                - params.uid (str): UID of video to move
                - params.after (str): UID of video to place after, or "prepend"
        
        CyTube API: channel.moveMedia(uid, after)
        
        Note: CyTube moveMedia uses "after" positioning, not absolute indices.
              To move to position 1: after="prepend"
              To move after position N: after=uid_of_item_at_position_N
        
        Raises:
            Error event published if parameters missing or move operation fails
        """
        try:
            params = event.data.get("params", {})
            uid = params.get("uid")
            after = params.get("after")

            if not uid or not after:
                await self._publish_playlist_error(
                    event,
                    "Missing required parameters: uid and after"
                )
                return

            await self.channel.moveMedia(uid, after)
            self._events_sent += 1
            logger.debug(f"Moved video in playlist: {uid} after {after}")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to move video: {e}")
            self._errors += 1

    async def _playlist_jump(self, event: Event) -> None:
        """Jump to specific video in playlist via CyTube jumpTo API.
        
        Immediately starts playback of the specified video, skipping any currently
        playing content.
        
        Args:
            event: Command event with data structure:
                - params.uid (str): UID of video to jump to
        
        CyTube API: channel.jumpTo(uid)
        
        Raises:
            Error event published if UID missing or jump operation fails
        """
        try:
            params = event.data.get("params", {})
            uid = params.get("uid")

            if not uid:
                await self._publish_playlist_error(
                    event,
                    "Missing required parameter: uid"
                )
                return

            await self.channel.jumpTo(uid)
            self._events_sent += 1
            logger.debug(f"Jumped to video: {uid}")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to jump to video: {e}")
            self._errors += 1

    async def _playlist_clear(self, event: Event) -> None:
        """Clear entire playlist via CyTube clearPlaylist API.
        
        Removes all videos from the playlist. No parameters required.
        This operation cannot be undone.
        
        Args:
            event: Command event (no params required)
        
        CyTube API: channel.clearPlaylist()
        
        Raises:
            Error event published if clear operation fails
        """
        try:
            await self.channel.clearPlaylist()
            self._events_sent += 1
            logger.debug("Cleared playlist")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to clear playlist: {e}")
            self._errors += 1

    async def _playlist_shuffle(self, event: Event) -> None:
        """Shuffle playlist order via CyTube shufflePlaylist API.
        
        Randomly reorders all videos in the playlist. Currently playing video
        position may change. No parameters required.
        
        Args:
            event: Command event (no params required)
        
        CyTube API: channel.shufflePlaylist()
        
        Raises:
            Error event published if shuffle operation fails
        """
        try:
            await self.channel.shufflePlaylist()
            self._events_sent += 1
            logger.debug("Shuffled playlist")

        except Exception as e:
            await self._publish_playlist_error(event, f"Failed to shuffle playlist: {e}")
            self._errors += 1

    async def _skip_video(self) -> None:
        """Skip current video"""
        try:
            # Note: Actual implementation depends on cytube_bot API
            # This is a placeholder showing the pattern
            logger.debug("Skipping video")
            # await self.channel.skip_video()
        except Exception as e:
            logger.error(f"Failed to skip video: {e}")
            raise

    async def _take_leader(self) -> None:
        """Take leader position"""
        try:
            # Note: Actual implementation depends on cytube_bot API
            logger.debug("Taking leader")
            # await self.channel.take_leader()
        except Exception as e:
            logger.error(f"Failed to take leader: {e}")
            raise

    # ========================================================================
    # Queries
    # ========================================================================

    def is_running(self) -> bool:
        """Check if connector is running"""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get connector statistics"""
        return {
            "running": self._running,
            "events_received": self._events_received,
            "events_sent": self._events_sent,
            "errors": self._errors,
            "subscriptions": len(self._subscriptions),
            "handlers": len(self._event_handlers),
        }

    def get_channel_name(self) -> str:
        """Get connected channel name"""
        return self.channel.name if hasattr(self.channel, "name") else "unknown"
