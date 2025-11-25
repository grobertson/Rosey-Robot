"""
Playlist Plugin

Media playlist management plugin with NATS-based communication.
Migrated from lib/playlist.py to plugin architecture.

Commands:
    !add <url> - Add media to queue
    !queue - Show current queue
    !skip - Skip current item
    !remove [id] - Remove from queue
    !clear - Clear queue (admin)
    !shuffle - Shuffle queue

NATS Subjects:
    Subscribe:
        rosey.command.playlist.add
        rosey.command.playlist.queue
        rosey.command.playlist.skip
        rosey.command.playlist.remove
        rosey.command.playlist.clear
        rosey.command.playlist.shuffle
        rosey.command.playlist.move
    
    Publish:
        playlist.item.added - When item added to queue
        playlist.item.removed - When item removed
        playlist.item.playing - When item starts playing
        playlist.cleared - When queue cleared
"""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = Any

try:
    from .models import MediaParser, MediaType, PlaylistItem
    from .queue import PlaylistQueue
except ImportError:
    from models import MediaParser, MediaType, PlaylistItem
    from queue import PlaylistQueue

logger = logging.getLogger(__name__)


class PlaylistPlugin:
    """
    Playlist management plugin.
    
    Manages media queues for channels with support for:
    - Adding/removing items
    - Queue display
    - Skip/shuffle operations
    - Channel isolation
    - Event emission
    
    This plugin communicates entirely via NATS messaging.
    """
    
    # Plugin metadata
    NAMESPACE = "playlist"
    VERSION = "1.0.0"
    DESCRIPTION = "Media playlist management"
    
    # NATS subjects
    SUBJECT_ADD = "rosey.command.playlist.add"
    SUBJECT_QUEUE = "rosey.command.playlist.queue"
    SUBJECT_SKIP = "rosey.command.playlist.skip"
    SUBJECT_REMOVE = "rosey.command.playlist.remove"
    SUBJECT_CLEAR = "rosey.command.playlist.clear"
    SUBJECT_SHUFFLE = "rosey.command.playlist.shuffle"
    SUBJECT_MOVE = "rosey.command.playlist.move"
    
    # Events
    EVENT_ITEM_ADDED = "playlist.item.added"
    EVENT_ITEM_REMOVED = "playlist.item.removed"
    EVENT_ITEM_PLAYING = "playlist.item.playing"
    EVENT_CLEARED = "playlist.cleared"
    
    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        """
        Initialize playlist plugin.
        
        Args:
            nats_client: Connected NATS client for messaging
            config: Plugin configuration dict
        """
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.NAMESPACE}")
        self._initialized = False
        self._subscriptions: List[Any] = []
        
        # Load configuration
        self.max_queue_size = self.config.get("max_queue_size", 100)
        self.max_items_per_user = self.config.get("max_items_per_user", 5)
        self.allowed_media_types = self.config.get("allowed_media_types", [])
        self.emit_events = self.config.get("emit_events", True)
        self.admins = self.config.get("admins", [])
        
        # Channel-specific queues
        self.queues: Dict[str, PlaylistQueue] = {}
        
        self.logger.info(f"{self.NAMESPACE} v{self.VERSION} initialized")
    
    async def setup(self) -> None:
        """Initialize plugin and register command handlers."""
        if self._initialized:
            return
        
        # Subscribe to command subjects
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_ADD, cb=self._handle_add)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_QUEUE, cb=self._handle_queue)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_SKIP, cb=self._handle_skip)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_REMOVE, cb=self._handle_remove)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_CLEAR, cb=self._handle_clear)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_SHUFFLE, cb=self._handle_shuffle)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_MOVE, cb=self._handle_move)
        )
        
        self._initialized = True
        self.logger.info(f"{self.NAMESPACE} plugin ready")
    
    async def teardown(self) -> None:
        """Cleanup plugin resources."""
        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.error(f"Error unsubscribing: {e}")
        
        self._subscriptions.clear()
        self.queues.clear()
        self._initialized = False
        
        self.logger.info(f"{self.NAMESPACE} plugin shutdown")
    
    def _get_queue(self, channel: str) -> PlaylistQueue:
        """Get or create queue for a channel."""
        if channel not in self.queues:
            self.queues[channel] = PlaylistQueue(max_size=self.max_queue_size)
        return self.queues[channel]
    
    def _is_admin(self, user: str) -> bool:
        """Check if user is an admin."""
        return user in self.admins
    
    async def _publish_event(self, event_name: str, data: dict) -> None:
        """Publish event to NATS if events enabled."""
        if not self.emit_events:
            return
        
        try:
            await self.nats.publish(event_name, json.dumps(data).encode())
        except Exception as e:
            self.logger.error(f"Error publishing event {event_name}: {e}")
    
    async def _reply(self, msg, response: dict) -> None:
        """Send reply to NATS request."""
        try:
            await self.nats.publish(msg.reply, json.dumps(response).encode())
        except Exception as e:
            self.logger.error(f"Error sending reply: {e}")
    
    async def _reply_error(self, msg, error: str) -> None:
        """Send error response."""
        await self._reply(msg, {"success": False, "error": error})
    
    async def _reply_success(self, msg, message: str, data: Optional[dict] = None) -> None:
        """Send success response."""
        response = {"success": True, "message": message}
        if data:
            response["data"] = data
        await self._reply(msg, response)
    
    # =================================================================
    # Command Handlers
    # =================================================================
    
    async def _handle_add(self, msg) -> None:
        """Handle !add <url> command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            url = data.get("args", "").strip()
            
            if not url:
                return await self._reply_error(msg, "Usage: !add <url>")
            
            # Parse URL
            try:
                media_type, media_id = MediaParser.parse(url)
            except ValueError as e:
                return await self._reply_error(msg, str(e))
            
            # Check if media type is allowed
            if self.allowed_media_types and media_type.value not in self.allowed_media_types:
                return await self._reply_error(msg, f"Media type {media_type.value} not allowed")
            
            # Check per-user limit
            queue = self._get_queue(channel)
            user_items = queue.find_by_user(user)
            if len(user_items) >= self.max_items_per_user:
                return await self._reply_error(
                    msg,
                    f"You already have {len(user_items)} items in queue (max: {self.max_items_per_user})"
                )
            
            # Create item (title will be placeholder for now, can be enriched in Sortie 2)
            item = PlaylistItem(
                id="",  # Will be assigned by queue
                media_type=media_type,
                media_id=media_id,
                title=f"[{media_type.value}] {media_id[:20]}",  # Placeholder
                duration=0,  # Will be fetched in Sortie 2
                added_by=user,
            )
            
            # Add to queue
            if not queue.add(item):
                return await self._reply_error(msg, "Queue is full!")
            
            position = queue.length
            message = f"📺 Added to queue (#{position}): {item.title}"
            
            await self._reply_success(msg, message, {"item": item.to_dict(), "position": position})
            
            # Emit event
            await self._publish_event(self.EVENT_ITEM_ADDED, {
                "event": self.EVENT_ITEM_ADDED,
                "channel": channel,
                "item": item.to_dict(),
                "position": position,
            })
            
        except Exception as e:
            self.logger.error(f"Error in _handle_add: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error adding item")
    
    async def _handle_queue(self, msg) -> None:
        """Handle !queue command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            
            queue = self._get_queue(channel)
            
            if queue.is_empty and not queue.current:
                return await self._reply_success(msg, "📺 Queue is empty")
            
            lines = ["📺 **Playlist**\n"]
            
            # Current item
            if queue.current:
                lines.append(f"▶️ Now: {queue.current.title} [{queue.current.formatted_duration}]")
                lines.append(f"   Added by: {queue.current.added_by}\n")
            
            # Upcoming items
            upcoming = queue.peek(5)
            if upcoming:
                lines.append("**Up Next:**")
                for i, item in enumerate(upcoming, 1):
                    lines.append(f"{i}. {item.title} [{item.formatted_duration}] - {item.added_by}")
                
                if queue.length > 5:
                    lines.append(f"... and {queue.length - 5} more")
            
            # Stats
            stats = queue.get_stats()
            if stats.total_duration > 0:
                hours, remainder = divmod(stats.total_duration, 3600)
                minutes, _ = divmod(remainder, 60)
                time_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
                lines.append(f"\n📊 {stats.total_items} items | {time_str} | {stats.unique_users} users")
            
            message = "\n".join(lines)
            await self._reply_success(msg, message, {
                "current": queue.current.to_dict() if queue.current else None,
                "upcoming": [item.to_dict() for item in upcoming],
                "stats": stats.__dict__,
            })
            
        except Exception as e:
            self.logger.error(f"Error in _handle_queue: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error fetching queue")
    
    async def _handle_skip(self, msg) -> None:
        """Handle !skip command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            
            queue = self._get_queue(channel)
            
            if not queue.current:
                return await self._reply_error(msg, "Nothing is playing!")
            
            skipped = queue.current
            next_item = queue.advance()
            
            if next_item:
                message = f"⏭️ Skipped. Now playing: {next_item.title}"
                await self._reply_success(msg, message, {"next": next_item.to_dict()})
                
                # Emit playing event
                await self._publish_event(self.EVENT_ITEM_PLAYING, {
                    "event": self.EVENT_ITEM_PLAYING,
                    "channel": channel,
                    "item": next_item.to_dict(),
                })
            else:
                message = "⏭️ Skipped. Queue is now empty."
                await self._reply_success(msg, message)
            
            # Emit removed event
            await self._publish_event(self.EVENT_ITEM_REMOVED, {
                "event": self.EVENT_ITEM_REMOVED,
                "channel": channel,
                "item": skipped.to_dict(),
                "reason": "skipped",
                "by": user,
            })
            
        except Exception as e:
            self.logger.error(f"Error in _handle_skip: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error skipping")
    
    async def _handle_remove(self, msg) -> None:
        """Handle !remove [id] command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            item_id = data.get("args", "").strip()
            
            queue = self._get_queue(channel)
            
            if not item_id:
                # Remove user's last item
                removed = queue.remove_by_user(user, count=1)
                if not removed:
                    return await self._reply_error(msg, "You have nothing in the queue")
                item = removed[0]
            else:
                # Remove by ID (admin or own item)
                item = queue.get_by_id(item_id)
                if not item:
                    return await self._reply_error(msg, f"Item '{item_id}' not found")
                
                # Check permission
                if item.added_by != user and not self._is_admin(user):
                    return await self._reply_error(msg, "You can only remove your own items")
                
                queue.remove(item_id)
            
            message = f"🗑️ Removed: {item.title}"
            await self._reply_success(msg, message, {"item": item.to_dict()})
            
            # Emit event
            await self._publish_event(self.EVENT_ITEM_REMOVED, {
                "event": self.EVENT_ITEM_REMOVED,
                "channel": channel,
                "item": item.to_dict(),
                "reason": "removed",
                "by": user,
            })
            
        except Exception as e:
            self.logger.error(f"Error in _handle_remove: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error removing item")
    
    async def _handle_clear(self, msg) -> None:
        """Handle !clear command (admin only)."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            
            if not self._is_admin(user):
                return await self._reply_error(msg, "Admin only command")
            
            queue = self._get_queue(channel)
            count = queue.clear()
            
            message = f"🗑️ Cleared {count} items from queue"
            await self._reply_success(msg, message, {"count": count})
            
            # Emit event
            await self._publish_event(self.EVENT_CLEARED, {
                "event": self.EVENT_CLEARED,
                "channel": channel,
                "count": count,
                "by": user,
            })
            
        except Exception as e:
            self.logger.error(f"Error in _handle_clear: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error clearing queue")
    
    async def _handle_shuffle(self, msg) -> None:
        """Handle !shuffle command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            
            queue = self._get_queue(channel)
            
            if queue.length < 2:
                return await self._reply_error(msg, "Need at least 2 items to shuffle")
            
            queue.shuffle()
            
            message = f"🔀 Shuffled {queue.length} items"
            await self._reply_success(msg, message, {"count": queue.length})
            
        except Exception as e:
            self.logger.error(f"Error in _handle_shuffle: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error shuffling queue")
    
    async def _handle_move(self, msg) -> None:
        """Handle !move <item_id> <after_id> command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            args = data.get("args", "").strip().split()
            
            if len(args) < 2:
                return await self._reply_error(msg, "Usage: !move <item_id> <after_id>")
            
            item_id = args[0]
            after_id = args[1] if args[1] != "start" else None
            
            queue = self._get_queue(channel)
            item = queue.get_by_id(item_id)
            
            if not item:
                return await self._reply_error(msg, f"Item '{item_id}' not found")
            
            # Check permission
            if item.added_by != user and not self._is_admin(user):
                return await self._reply_error(msg, "You can only move your own items")
            
            if queue.move(item_id, after=after_id):
                message = f"↕️ Moved: {item.title}"
                await self._reply_success(msg, message)
            else:
                await self._reply_error(msg, "Failed to move item")
            
        except Exception as e:
            self.logger.error(f"Error in _handle_move: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error moving item")
