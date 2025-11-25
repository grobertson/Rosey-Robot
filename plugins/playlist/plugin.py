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
    !voteskip - Vote to skip current item
    !history [n] - Show recent plays (default 10)
    !mystats - Show your playlist statistics

NATS Subjects:
    Subscribe:
        rosey.command.playlist.add
        rosey.command.playlist.queue
        rosey.command.playlist.skip
        rosey.command.playlist.remove
        rosey.command.playlist.clear
        rosey.command.playlist.shuffle
        rosey.command.playlist.move
        rosey.command.playlist.voteskip
        rosey.command.playlist.history
        rosey.command.playlist.mystats
    
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
    from .service import PlaylistService
    from .metadata import MetadataFetcher
    from .voting import SkipVoteManager
    from .storage import PlaylistStorage
    from .quotas import QuotaManager, QuotaConfig
except ImportError:
    from models import MediaParser, MediaType, PlaylistItem
    from queue import PlaylistQueue
    from service import PlaylistService
    from metadata import MetadataFetcher
    from voting import SkipVoteManager
    from storage import PlaylistStorage
    from quotas import QuotaManager, QuotaConfig

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
    SUBJECT_VOTESKIP = "rosey.command.playlist.voteskip"
    SUBJECT_HISTORY = "rosey.command.playlist.history"
    SUBJECT_MYSTATS = "rosey.command.playlist.mystats"
    
    # Events
    EVENT_ITEM_ADDED = "playlist.item.added"
    EVENT_ITEM_REMOVED = "playlist.item.removed"
    EVENT_ITEM_PLAYING = "playlist.item.playing"
    EVENT_CLEARED = "playlist.cleared"
    EVENT_METADATA_FETCHED = "playlist.metadata.fetched"
    EVENT_SKIP_VOTE = "playlist.skip.vote"
    EVENT_SKIP_PASSED = "playlist.skip.passed"
    EVENT_SHUFFLED = "playlist.shuffled"
    
    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None, db_service = None):
        """
        Initialize playlist plugin.
        
        Args:
            nats_client: Connected NATS client for messaging
            config: Plugin configuration dict
            db_service: DatabaseService instance for persistence (optional)
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
        self.persist_queue = self.config.get("persist_queue", True)
        
        # Channel-specific queues
        self.queues: Dict[str, PlaylistQueue] = {}
        
        # Initialize metadata fetcher
        self.metadata_fetcher = MetadataFetcher(
            youtube_api_key=self.config.get("youtube_api_key"),
            timeout=self.config.get("metadata_timeout", 10.0)
        )
        
        # Initialize vote manager
        self.vote_manager = SkipVoteManager(
            threshold=self.config.get("skip_threshold", 0.5),
            min_votes=self.config.get("min_skip_votes", 2),
            timeout_minutes=self.config.get("skip_vote_timeout", 5)
        )
        
        # Initialize storage (optional)
        self.storage: Optional[PlaylistStorage] = None
        if db_service:
            self.storage = PlaylistStorage(db_service)
        
        # Initialize quota manager
        quota_config = QuotaConfig(
            max_items_per_user=self.config.get("max_items_per_user", 5),
            max_duration_per_user=self.config.get("max_duration_per_user", 1800),
            rate_limit_count=self.config.get("rate_limit_count", 3),
            rate_limit_window=self.config.get("rate_limit_window", 10)
        )
        self.quota_manager = QuotaManager(quota_config)
        
        # Service will be initialized in setup()
        self.service: Optional[PlaylistService] = None
        
        self.logger.info(f"{self.NAMESPACE} v{self.VERSION} initialized")
    
    async def setup(self) -> None:
        """Initialize plugin and register command handlers."""
        if self._initialized:
            return
        
        # Initialize database tables if storage enabled
        if self.storage:
            await self.storage.create_tables()
            
            # Recover queues from database
            channels = await self.storage.get_persisted_channels()
            for channel in channels:
                items = await self.storage.load_queue(channel)
                if items:
                    queue = self._get_queue(channel)
                    queue.items = items
                    self.logger.info(f"Recovered {len(items)} items for {channel}")
        
        # Initialize PlaylistService
        self.service = PlaylistService(
            queues=self.queues,
            metadata_fetcher=self.metadata_fetcher,
            vote_manager=self.vote_manager,
            event_callback=self._emit_event,
            config=self.config
        )
        
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
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_VOTESKIP, cb=self._handle_voteskip)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_HISTORY, cb=self._handle_history)
        )
        self._subscriptions.append(
            await self.nats.subscribe(self.SUBJECT_MYSTATS, cb=self._handle_mystats)
        )
        
        self._initialized = True
        self.logger.info(f"{self.NAMESPACE} plugin ready")
    
    async def teardown(self) -> None:
        """Cleanup plugin resources."""
        # Persist queues if storage enabled
        if self.storage and self.persist_queue:
            for channel, queue in self.queues.items():
                await self.storage.save_queue(channel, queue.items)
            self.logger.info("Persisted all queues to database")
        
        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.error(f"Error unsubscribing: {e}")
        
        # Close metadata fetcher
        await self.metadata_fetcher.close()
        
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
    
    async def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit event via service (adds timestamp and event type)."""
        from datetime import datetime
        data["event"] = event_type
        data["timestamp"] = datetime.utcnow().isoformat()
        await self._publish_event(event_type, data)
    
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
            
            # Check quota before adding
            queue = self._get_queue(channel)
            quota_check = self.quota_manager.check_quota(channel, user, queue.items)
            if not quota_check["allowed"]:
                return await self._reply_error(msg, quota_check["reason"])
            
            # Use service to add item (handles metadata fetching)
            result = await self.service.add_item(channel, url, user, fetch_metadata=True)
            
            if not result.success:
                return await self._reply_error(msg, result.error)
            
            # Record add for quota tracking
            self.quota_manager.record_add(channel, user)
            
            # Record add in storage
            if self.storage:
                await self.storage.record_add(user, result.item.duration)
            
            # Persist queue if enabled
            if self.storage and self.persist_queue:
                await self.storage.save_queue(channel, queue.items)
            
            message = f"📺 Added to queue (#{result.position}): {result.item.title}"
            await self._reply_success(msg, message, {
                "item": result.item.to_dict(),
                "position": result.position
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
            
            # Record play in history (skipped)
            if self.storage and queue.current:
                await self.storage.record_play(channel, queue.current, play_duration=0, skipped=True)
            
            # Use service to skip (emits events)
            next_item = await self.service.skip(channel, user)
            
            # Persist queue if enabled
            if self.storage and self.persist_queue:
                await self.storage.save_queue(channel, queue.items)
            
            if next_item:
                message = f"⏭️ Skipped. Now playing: {next_item.title}"
                await self._reply_success(msg, message, {"next": next_item.to_dict()})
            else:
                message = "⏭️ Skipped. Queue is now empty."
                await self._reply_success(msg, message)
            
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
            
            # Use service to clear (emits event and resets votes)
            count = await self.service.clear(channel, user)
            
            message = f"🗑️ Cleared {count} items from queue"
            await self._reply_success(msg, message, {"count": count})
            
        except Exception as e:
            self.logger.error(f"Error in _handle_clear: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error clearing queue")
    
    async def _handle_shuffle(self, msg) -> None:
        """Handle !shuffle command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            
            queue = self._get_queue(channel)
            
            if queue.length < 2:
                return await self._reply_error(msg, "Need at least 2 items to shuffle")
            
            # Use service to shuffle (emits event)
            count = await self.service.shuffle(channel, user)
            
            message = f"🔀 Shuffled {count} items"
            await self._reply_success(msg, message, {"count": count})
            
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
    
    async def _handle_voteskip(self, msg) -> None:
        """Handle !voteskip command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            user = data.get("user", "")
            
            # Use service for vote skip
            result = await self.service.vote_skip(channel, user)
            
            if not result["success"]:
                return await self._reply_error(msg, result.get("error", "Vote failed"))
            
            if result.get("already_voted"):
                return await self._reply(msg, {
                    "success": True,
                    "message": "You already voted to skip!",
                    "votes": result["votes"],
                    "needed": result["needed"]
                })
            
            if result.get("passed"):
                message = f"⏭️ Skip vote passed! ({result['votes']} votes)"
            else:
                message = f"⏭️ Vote recorded ({result['votes']}/{result['needed']} needed)"
            
            await self._reply_success(msg, message, result)
            
        except Exception as e:
            self.logger.error(f"Error in _handle_voteskip: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error voting to skip")
    
    async def _handle_history(self, msg) -> None:
        """Handle !history command."""
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "")
            args = data.get("args", "").strip().split()
            
            if not self.storage:
                return await self._reply_error(msg, "History tracking not enabled")
            
            limit = 10
            if args and args[0].isdigit():
                limit = min(int(args[0]), 50)
            
            history = await self.storage.get_history(channel, limit=limit)
            
            if not history:
                return await self._reply_success(msg, "📜 No play history")
            
            lines = [f"📜 **Recent Plays** (last {len(history)}):\n"]
            
            for i, entry in enumerate(history, 1):
                title = entry["title"]
                added_by = entry["added_by"]
                skipped = "⏭️" if entry.get("skipped") else "✅"
                
                # Format timestamp
                from datetime import datetime
                played_at = entry.get("played_at")
                if isinstance(played_at, str):
                    played_at = datetime.fromisoformat(played_at)
                time_str = played_at.strftime("%H:%M") if played_at else "unknown"
                
                lines.append(f"{i}. {skipped} {title} - {added_by} ({time_str})")
            
            message = "\n".join(lines)
            await self._reply_success(msg, message, {"history": history})
            
        except Exception as e:
            self.logger.error(f"Error in _handle_history: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error fetching history")
    
    async def _handle_mystats(self, msg) -> None:
        """Handle !mystats command."""
        try:
            data = json.loads(msg.data.decode())
            user = data.get("user", "")
            
            if not self.storage:
                return await self._reply_error(msg, "Stats tracking not enabled")
            
            stats = await self.storage.get_user_stats(user)
            
            if not stats:
                return await self._reply_success(msg, "📊 No stats yet! Add some items to get started.")
            
            lines = [f"📊 **Stats for {user}**\n"]
            lines.append(f"Items Added: {stats['items_added']}")
            lines.append(f"Items Played: {stats['items_played']}")
            lines.append(f"Items Skipped: {stats['items_skipped']}")
            
            # Format durations
            added_mins = stats["total_duration_added"] // 60
            played_mins = stats["total_duration_played"] // 60
            lines.append(f"Time Added: {added_mins}m")
            lines.append(f"Time Played: {played_mins}m")
            
            # Last add
            last_add = stats.get("last_add")
            if last_add:
                from datetime import datetime
                if isinstance(last_add, str):
                    last_add = datetime.fromisoformat(last_add)
                lines.append(f"Last Add: {last_add.strftime('%Y-%m-%d %H:%M')}")
            
            message = "\n".join(lines)
            await self._reply_success(msg, message, {"stats": stats})
            
        except Exception as e:
            self.logger.error(f"Error in _handle_mystats: {e}", exc_info=True)
            await self._reply_error(msg, "Internal error fetching stats")

