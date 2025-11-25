"""
Playlist service interface for programmatic access.

Exposed to other plugins via service registration.
"""

from typing import List, Optional, Callable, Any, Dict
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

try:
    from .models import PlaylistItem, MediaType, MediaParser
    from .queue import PlaylistQueue, QueueStats
    from .metadata import MetadataFetcher
    from .voting import SkipVoteManager
except ImportError:
    from models import PlaylistItem, MediaType, MediaParser
    from queue import PlaylistQueue, QueueStats
    from metadata import MetadataFetcher
    from voting import SkipVoteManager

logger = logging.getLogger(__name__)


@dataclass
class AddResult:
    """
    Result of adding an item to the playlist.
    """
    success: bool
    item: Optional[PlaylistItem] = None
    position: Optional[int] = None
    error: Optional[str] = None


@dataclass
class PlaybackState:
    """
    Current playback state for a channel.
    """
    current: Optional[PlaylistItem]
    position_seconds: int  # Position in current item
    is_playing: bool
    queue_length: int


class PlaylistService:
    """
    Service interface for playlist management.
    
    Exposed to other plugins for programmatic access to playlist operations.
    
    Example usage from another plugin:
        ```python
        # Get service
        playlist = await bot.get_service("playlist")
        
        # Add an item
        result = await playlist.add_item("lobby", "https://youtube.com/...", "user1")
        if result.success:
            print(f"Added at position {result.position}")
        
        # Get queue
        items = playlist.get_queue("lobby")
        
        # Vote to skip
        vote = await playlist.vote_skip("lobby", "user2")
        print(f"Votes: {vote['votes']}/{vote['needed']}")
        
        # Subscribe to events
        def on_playlist_event(event_type, data):
            print(f"Playlist event: {event_type}")
        
        playlist.subscribe("lobby", on_playlist_event)
        ```
    """
    
    def __init__(
        self,
        queues: Dict[str, PlaylistQueue],
        metadata_fetcher: MetadataFetcher,
        vote_manager: SkipVoteManager,
        event_callback: Callable[[str, dict], Any],
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize playlist service.
        
        Args:
            queues: Dict mapping channel names to PlaylistQueue instances
            metadata_fetcher: MetadataFetcher for titles/durations
            vote_manager: SkipVoteManager for voting
            event_callback: Async callback for emitting events
            config: Optional configuration dict
        """
        self._queues = queues
        self._metadata = metadata_fetcher
        self._votes = vote_manager
        self._emit_event = event_callback
        self._config = config or {}
        
        # Subscribers for real-time updates
        self._subscribers: Dict[str, List[Callable]] = {}
    
    # === Queue Operations ===
    
    async def add_item(
        self,
        channel: str,
        url: str,
        user: str,
        fetch_metadata: bool = True,
    ) -> AddResult:
        """
        Add an item to the playlist.
        
        Args:
            channel: Channel to add to
            url: Media URL
            user: User adding the item
            fetch_metadata: Whether to fetch title/duration (default True)
        
        Returns:
            AddResult with success status and item details
        """
        # Parse URL
        try:
            media_type, media_id = MediaParser.parse(url)
        except ValueError as e:
            logger.warning(f"Invalid URL from {user}: {url}")
            return AddResult(success=False, error=str(e))
        
        # Create item with placeholder title
        item = PlaylistItem(
            id="",  # Will be assigned by queue
            media_type=media_type,
            media_id=media_id,
            title="Loading...",
            duration=0,
            added_by=user,
        )
        
        # Add to queue
        queue = self._get_queue(channel)
        
        # Check max queue size
        max_size = self._config.get("max_queue_size", 100)
        if queue.length >= max_size:
            return AddResult(success=False, error=f"Queue is full (max {max_size})")
        
        # Check per-user limit
        max_per_user = self._config.get("max_items_per_user", 5)
        user_items = queue.find_by_user(user)
        if len(user_items) >= max_per_user:
            return AddResult(success=False, error=f"You have {max_per_user} items queued already")
        
        success = queue.add(item)
        if not success:
            return AddResult(success=False, error="Failed to add item to queue")
        
        position = queue.length
        
        # Fetch metadata asynchronously (non-blocking)
        if fetch_metadata:
            asyncio.create_task(
                self._fetch_and_update_metadata(channel, item)
            )
        
        # Emit event
        await self._emit_event("playlist.item.added", {
            "channel": channel,
            "item": item.to_dict(),
            "position": position,
            "user": user,
        })
        
        logger.info(f"Added {media_type.value}:{media_id} to {channel} queue (#{position}) by {user}")
        
        return AddResult(success=True, item=item, position=position)
    
    async def remove_item(
        self,
        channel: str,
        item_id: str,
        user: str,
        is_admin: bool = False,
    ) -> Optional[PlaylistItem]:
        """
        Remove an item from the playlist.
        
        Args:
            channel: Channel name
            item_id: Item ID to remove
            user: User requesting removal
            is_admin: Whether user has admin privileges
        
        Returns:
            Removed item, or None if not found/not allowed
        """
        queue = self._get_queue(channel)
        
        # Find item
        item = queue.get_by_id(item_id)
        if not item:
            logger.warning(f"Item {item_id} not found in {channel} queue")
            return None
        
        # Check permission (owner or admin can remove)
        if item.added_by != user and not is_admin:
            logger.warning(f"{user} attempted to remove {item_id} added by {item.added_by}")
            return None
        
        # Remove from queue
        removed = queue.remove(item_id)
        
        if removed:
            await self._emit_event("playlist.item.removed", {
                "channel": channel,
                "item": removed.to_dict(),
                "reason": "removed",
                "by": user,
            })
            logger.info(f"Removed {item_id} from {channel} by {user}")
        
        return removed
    
    def get_queue(self, channel: str) -> List[PlaylistItem]:
        """
        Get all items in a channel's queue.
        
        Args:
            channel: Channel name
        
        Returns:
            List of PlaylistItem objects
        """
        return list(self._get_queue(channel).items)
    
    def get_current(self, channel: str) -> Optional[PlaylistItem]:
        """
        Get currently playing item.
        
        Args:
            channel: Channel name
        
        Returns:
            Current PlaylistItem, or None if nothing playing
        """
        return self._get_queue(channel).current
    
    def get_stats(self, channel: str) -> QueueStats:
        """
        Get queue statistics.
        
        Args:
            channel: Channel name
        
        Returns:
            QueueStats with total_items, total_duration, unique_users
        """
        return self._get_queue(channel).get_stats()
    
    def get_playback_state(self, channel: str) -> PlaybackState:
        """
        Get current playback state.
        
        Args:
            channel: Channel name
        
        Returns:
            PlaybackState with current item, position, playing status
        """
        queue = self._get_queue(channel)
        return PlaybackState(
            current=queue.current,
            position_seconds=0,  # Would need CyTube integration for actual position
            is_playing=queue.current is not None,
            queue_length=queue.length,
        )
    
    # === Playback Control ===
    
    async def skip(self, channel: str, user: str) -> Optional[PlaylistItem]:
        """
        Skip current item (direct skip, no voting).
        
        Args:
            channel: Channel name
            user: User requesting skip
        
        Returns:
            Next item that's now playing, or None if queue empty
        """
        queue = self._get_queue(channel)
        skipped = queue.current
        
        if not skipped:
            logger.debug(f"Skip requested in {channel} but nothing playing")
            return None
        
        # Advance to next
        next_item = queue.advance()
        
        # Reset votes (new item)
        self._votes.reset(channel)
        
        # Emit events
        await self._emit_event("playlist.item.removed", {
            "channel": channel,
            "item": skipped.to_dict(),
            "reason": "skipped",
            "by": user,
        })
        
        if next_item:
            await self._emit_event("playlist.item.playing", {
                "channel": channel,
                "item": next_item.to_dict(),
            })
            logger.info(f"Skipped to {next_item.id} in {channel}")
        
        return next_item
    
    async def vote_skip(self, channel: str, user: str) -> Dict[str, Any]:
        """
        Cast a skip vote.
        
        If enough votes collected, automatically skips.
        
        Args:
            channel: Channel name
            user: User voting
        
        Returns:
            Dict with vote status:
            - success (bool)
            - votes (int)
            - needed (int)
            - passed (bool)
            - already_voted (bool)
            - error (str, if failed)
        """
        queue = self._get_queue(channel)
        
        if not queue.current:
            return {"success": False, "error": "Nothing playing"}
        
        # Cast vote
        result = self._votes.vote(channel, user, queue.current.id)
        
        # Emit vote event
        await self._emit_event("playlist.skip.vote", {
            "channel": channel,
            "user": user,
            "votes": result["votes"],
            "needed": result["needed"],
        })
        
        # If passed, skip immediately
        if result.get("passed"):
            logger.info(f"Skip vote passed in {channel} with {result['votes']} votes")
            await self.skip(channel, "vote")
            await self._emit_event("playlist.skip.passed", {
                "channel": channel,
                "votes": result["votes"],
            })
        
        return result
    
    async def shuffle(self, channel: str, user: str) -> int:
        """
        Shuffle the queue.
        
        Args:
            channel: Channel name
            user: User requesting shuffle
        
        Returns:
            Number of items shuffled
        """
        queue = self._get_queue(channel)
        count = queue.length
        queue.shuffle()
        
        await self._emit_event("playlist.shuffled", {
            "channel": channel,
            "count": count,
            "by": user,
        })
        
        logger.info(f"Shuffled {count} items in {channel} by {user}")
        
        return count
    
    async def clear(self, channel: str, user: str) -> int:
        """
        Clear the queue.
        
        Args:
            channel: Channel name
            user: User requesting clear
        
        Returns:
            Number of items cleared
        """
        queue = self._get_queue(channel)
        count = queue.clear()
        
        # Reset votes
        self._votes.reset(channel)
        
        await self._emit_event("playlist.cleared", {
            "channel": channel,
            "count": count,
            "by": user,
        })
        
        logger.info(f"Cleared {count} items from {channel} by {user}")
        
        return count
    
    # === Subscriptions ===
    
    def subscribe(
        self,
        channel: str,
        callback: Callable[[str, dict], None],
    ) -> None:
        """
        Subscribe to playlist events for a channel.
        
        Args:
            channel: Channel to subscribe to
            callback: Function to call with (event_type, data)
        """
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)
        logger.debug(f"Added subscriber for {channel}")
    
    def unsubscribe(self, channel: str, callback: Callable) -> None:
        """
        Unsubscribe from playlist events.
        
        Args:
            channel: Channel to unsubscribe from
            callback: Callback function to remove
        """
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(callback)
                logger.debug(f"Removed subscriber from {channel}")
            except ValueError:
                pass
    
    async def notify_subscribers(self, channel: str, event_type: str, data: dict) -> None:
        """
        Notify all subscribers of an event.
        
        Args:
            channel: Channel event occurred in
            event_type: Type of event
            data: Event data
        """
        if channel in self._subscribers:
            for callback in self._subscribers[channel]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_type, data)
                    else:
                        callback(event_type, data)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}")
    
    # === Configuration ===
    
    def update_config(self, channel: str, **kwargs) -> None:
        """
        Update per-channel configuration.
        
        Args:
            channel: Channel name
            **kwargs: Configuration options to update
        """
        # Channel-specific config not yet implemented
        # For now, updates are global
        self._config.update(kwargs)
        logger.info(f"Updated config for {channel}: {kwargs}")
    
    # === Private Methods ===
    
    def _get_queue(self, channel: str) -> PlaylistQueue:
        """
        Get or create queue for channel.
        
        Args:
            channel: Channel name
        
        Returns:
            PlaylistQueue instance
        """
        if channel not in self._queues:
            self._queues[channel] = PlaylistQueue()
        return self._queues[channel]
    
    async def _fetch_and_update_metadata(
        self,
        channel: str,
        item: PlaylistItem,
    ) -> None:
        """
        Fetch metadata and update item.
        
        Runs asynchronously without blocking add operation.
        
        Args:
            channel: Channel name
            item: PlaylistItem to update
        """
        try:
            metadata = await self._metadata.fetch(item.media_type, item.media_id)
            
            # Update item fields
            item.title = metadata.get("title", item.title)
            item.duration = metadata.get("duration", 0)
            item.thumbnail_url = metadata.get("thumbnail")
            item.channel_name = metadata.get("channel")
            
            # Emit metadata fetched event
            await self._emit_event("playlist.metadata.fetched", {
                "channel": channel,
                "item": item.to_dict(),
            })
            
            logger.debug(f"Fetched metadata for {item.id}: {item.title}")
            
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {item.id}: {e}")
            # Keep placeholder title on error
