"""
Database storage for playlist persistence.

Handles:
- Queue persistence across restarts
- Play history tracking
- User statistics
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

try:
    from .models import PlaylistItem, MediaType
except ImportError:
    from models import PlaylistItem, MediaType

logger = logging.getLogger(__name__)


class PlaylistStorage:
    """
    Database operations for playlist persistence.
    
    Manages:
    - Queue state (persist across restarts)
    - Play history (track what's been played)
    - User statistics (adds, plays, skips)
    
    Example:
        storage = PlaylistStorage(db_service)
        await storage.create_tables()
        
        # Save queue
        await storage.save_queue("lobby", queue.items)
        
        # Load on restart
        items = await storage.load_queue("lobby")
        
        # Record play
        await storage.record_play("lobby", item, play_duration=180, skipped=False)
    """
    
    def __init__(self, db_service):
        """
        Initialize storage.
        
        Args:
            db_service: DatabaseService instance from common.database_service
        """
        self.db = db_service
    
    async def create_tables(self) -> None:
        """Create playlist tables if they don't exist."""
        # Queue persistence table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                position INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration INTEGER DEFAULT 0,
                added_by TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel, position)
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_queue_channel 
            ON playlist_queue(channel, position)
        """)
        
        # Play history table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                media_type TEXT NOT NULL,
                media_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration INTEGER DEFAULT 0,
                added_by TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                play_duration INTEGER DEFAULT 0,
                skipped BOOLEAN DEFAULT FALSE
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_history_channel 
            ON playlist_history(channel)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_history_user 
            ON playlist_history(added_by)
        """)
        
        # User statistics table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                items_added INTEGER DEFAULT 0,
                items_played INTEGER DEFAULT 0,
                items_skipped INTEGER DEFAULT 0,
                total_duration_added INTEGER DEFAULT 0,
                total_duration_played INTEGER DEFAULT 0,
                last_add TIMESTAMP NULL
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_user_stats_user 
            ON playlist_user_stats(user_id)
        """)
        
        logger.info("Playlist tables initialized")
    
    # ===================================================================
    # Queue Persistence
    # ===================================================================
    
    async def save_queue(self, channel: str, items: List[PlaylistItem]) -> None:
        """
        Save entire queue to database.
        
        Replaces existing queue for channel.
        
        Args:
            channel: Channel name
            items: List of PlaylistItem objects
        """
        # Clear existing queue
        await self.db.execute(
            "DELETE FROM playlist_queue WHERE channel = ?",
            (channel,)
        )
        
        # Insert all items
        for i, item in enumerate(items):
            await self.db.execute(
                """
                INSERT INTO playlist_queue 
                (channel, position, media_type, media_id, title, duration, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (channel, i, item.media_type.value, item.media_id,
                 item.title, item.duration, item.added_by, item.added_at)
            )
        
        logger.debug(f"Saved {len(items)} items for {channel}")
    
    async def load_queue(self, channel: str) -> List[PlaylistItem]:
        """
        Load queue from database.
        
        Args:
            channel: Channel name
        
        Returns:
            List of PlaylistItem objects in position order
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM playlist_queue 
            WHERE channel = ? 
            ORDER BY position
            """,
            (channel,)
        )
        
        items = [self._row_to_item(row) for row in rows]
        logger.debug(f"Loaded {len(items)} items for {channel}")
        return items
    
    async def clear_queue(self, channel: str) -> None:
        """
        Clear persisted queue for channel.
        
        Args:
            channel: Channel name
        """
        await self.db.execute(
            "DELETE FROM playlist_queue WHERE channel = ?",
            (channel,)
        )
        logger.debug(f"Cleared queue for {channel}")
    
    async def get_persisted_channels(self) -> List[str]:
        """
        Get list of channels with persisted queues.
        
        Returns:
            List of channel names
        """
        rows = await self.db.fetch_all(
            "SELECT DISTINCT channel FROM playlist_queue"
        )
        return [row["channel"] for row in rows]
    
    # ===================================================================
    # Play History
    # ===================================================================
    
    async def record_play(
        self,
        channel: str,
        item: PlaylistItem,
        play_duration: int,
        skipped: bool = False,
    ) -> None:
        """
        Record item play in history.
        
        Args:
            channel: Channel name
            item: PlaylistItem that was played
            play_duration: Actual seconds played
            skipped: Whether item was skipped
        """
        await self.db.execute(
            """
            INSERT INTO playlist_history
            (channel, media_type, media_id, title, duration,
             added_by, play_duration, skipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (channel, item.media_type.value, item.media_id, item.title,
             item.duration, item.added_by, play_duration, skipped)
        )
        
        # Update user stats
        await self._update_user_stats(item.added_by, item.duration, skipped)
        
        logger.debug(f"Recorded play: {item.title} by {item.added_by} in {channel}")
    
    async def get_history(
        self,
        channel: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent play history for channel.
        
        Args:
            channel: Channel name
            limit: Maximum results
        
        Returns:
            List of history dicts with keys: id, title, added_by, played_at, skipped, etc.
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM playlist_history 
            WHERE channel = ?
            ORDER BY played_at DESC
            LIMIT ?
            """,
            (channel, limit)
        )
        return [dict(row) for row in rows]
    
    async def get_user_history(
        self,
        user: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get user's play history across all channels.
        
        Args:
            user: Username
            limit: Maximum results
        
        Returns:
            List of history dicts
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM playlist_history
            WHERE added_by = ?
            ORDER BY played_at DESC
            LIMIT ?
            """,
            (user, limit)
        )
        return [dict(row) for row in rows]
    
    # ===================================================================
    # User Statistics
    # ===================================================================
    
    async def get_user_stats(self, user: str) -> Optional[Dict[str, Any]]:
        """
        Get user playlist statistics.
        
        Args:
            user: Username
        
        Returns:
            Dict with keys: items_added, items_played, items_skipped,
            total_duration_added, total_duration_played, last_add
            None if user has no stats
        """
        row = await self.db.fetch_one(
            "SELECT * FROM playlist_user_stats WHERE user_id = ?",
            (user,)
        )
        return dict(row) if row else None
    
    async def record_add(self, user: str, duration: int) -> None:
        """
        Record item addition for user stats.
        
        Args:
            user: Username
            duration: Item duration in seconds
        """
        await self.db.execute(
            """
            INSERT INTO playlist_user_stats 
            (user_id, items_added, total_duration_added, last_add)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                items_added = items_added + 1,
                total_duration_added = total_duration_added + ?,
                last_add = ?
            """,
            (user, duration, datetime.utcnow(), duration, datetime.utcnow())
        )
    
    async def _update_user_stats(
        self,
        user: str,
        duration: int,
        skipped: bool
    ) -> None:
        """
        Update user stats after play.
        
        Args:
            user: Username
            duration: Item duration
            skipped: Whether item was skipped
        """
        skip_increment = 1 if skipped else 0
        
        await self.db.execute(
            """
            INSERT INTO playlist_user_stats 
            (user_id, items_played, items_skipped, total_duration_played)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                items_played = items_played + 1,
                items_skipped = items_skipped + ?,
                total_duration_played = total_duration_played + ?
            """,
            (user, skip_increment, duration, skip_increment, duration)
        )
    
    # ===================================================================
    # Internal Helpers
    # ===================================================================
    
    def _row_to_item(self, row: Dict[str, Any]) -> PlaylistItem:
        """
        Convert database row to PlaylistItem.
        
        Args:
            row: Database row dict
        
        Returns:
            PlaylistItem instance
        """
        return PlaylistItem(
            id=str(row["id"]),
            media_type=MediaType(row["media_type"]),
            media_id=row["media_id"],
            title=row["title"],
            duration=row["duration"],
            added_by=row["added_by"],
            added_at=row["added_at"] if isinstance(row["added_at"], datetime) 
                    else datetime.fromisoformat(row["added_at"]),
        )
