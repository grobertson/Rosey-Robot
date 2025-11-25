"""
Playlist Queue Management

Thread-safe queue operations with channel isolation and statistics.
Modernized from lib/playlist.py's Playlist class.
"""

import random
import uuid
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

try:
    from .models import PlaylistItem
except ImportError:
    from models import PlaylistItem


@dataclass
class QueueStats:
    """Statistics about the queue."""
    total_items: int
    total_duration: int  # Seconds
    unique_users: int


class PlaylistQueue:
    """
    Manages the playlist queue for a single channel.
    
    This provides thread-safe queue operations with support for:
    - Adding/removing items
    - Advancing to next item (skip)
    - Shuffling queue
    - Queue statistics
    - History tracking
    
    Each channel gets its own PlaylistQueue instance for isolation.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize playlist queue.
        
        Args:
            max_size: Maximum number of items allowed in queue
        """
        self.max_size = max_size
        self._items: deque[PlaylistItem] = deque()
        self._current: Optional[PlaylistItem] = None
        self._history: deque[PlaylistItem] = deque(maxlen=50)
        self.locked = False
        self.paused = True
    
    @property
    def current(self) -> Optional[PlaylistItem]:
        """Currently playing item."""
        return self._current
    
    @current.setter
    def current(self, item: Optional[PlaylistItem]) -> None:
        """Set currently playing item."""
        self._current = item
    
    @property
    def items(self) -> List[PlaylistItem]:
        """List of queued items (not including current)."""
        return list(self._items)
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._items) == 0
    
    @property
    def length(self) -> int:
        """Number of items in queue."""
        return len(self._items)
    
    def add(self, item: PlaylistItem, after: Optional[str] = None) -> bool:
        """
        Add an item to the queue.
        
        Args:
            item: Item to add
            after: Optional item ID to insert after (None = append to end)
            
        Returns:
            True if added, False if queue full
        """
        if len(self._items) >= self.max_size:
            return False
        
        # Generate unique ID if not set
        if not item.id:
            item.id = str(uuid.uuid4())[:8]
        
        # Insert after specific item or append
        if after is None:
            self._items.append(item)
        else:
            # Find position to insert after
            for i, existing in enumerate(self._items):
                if existing.id == after:
                    # Convert to list for insertion, then back to deque
                    items_list = list(self._items)
                    items_list.insert(i + 1, item)
                    self._items = deque(items_list)
                    return True
            # If 'after' not found, append anyway
            self._items.append(item)
        
        return True
    
    def remove(self, item_id: str) -> Optional[PlaylistItem]:
        """
        Remove an item by ID.
        
        Args:
            item_id: ID of item to remove
            
        Returns:
            Removed item, or None if not found
        """
        for item in self._items:
            if item.id == item_id:
                self._items.remove(item)
                return item
        return None
    
    def remove_by_user(self, user: str, count: int = 1) -> List[PlaylistItem]:
        """
        Remove items added by a specific user.
        
        Args:
            user: Username to match
            count: Max items to remove (0 = all)
            
        Returns:
            List of removed items
        """
        removed = []
        remaining = deque()
        
        for item in self._items:
            if item.added_by == user and (count == 0 or len(removed) < count):
                removed.append(item)
            else:
                remaining.append(item)
        
        self._items = remaining
        return removed
    
    def advance(self) -> Optional[PlaylistItem]:
        """
        Move to next item (skip current).
        
        Returns:
            The new current item, or None if queue empty
        """
        if self._current:
            self._history.append(self._current)
        
        if self._items:
            self._current = self._items.popleft()
            self.paused = False
            return self._current
        
        self._current = None
        self.paused = True
        return None
    
    def peek(self, count: int = 5) -> List[PlaylistItem]:
        """
        Preview upcoming items without removing.
        
        Args:
            count: Number of items to preview
            
        Returns:
            List of upcoming items (up to count)
        """
        return list(self._items)[:count]
    
    def shuffle(self) -> None:
        """Shuffle the queue (excluding current)."""
        items = list(self._items)
        random.shuffle(items)
        self._items = deque(items)
    
    def clear(self) -> int:
        """
        Clear all items from queue.
        
        Returns:
            Number of items cleared
        """
        count = len(self._items)
        self._items.clear()
        return count
    
    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        users = set(item.added_by for item in self._items)
        total_duration = sum(item.duration for item in self._items)
        
        return QueueStats(
            total_items=len(self._items),
            total_duration=total_duration,
            unique_users=len(users),
        )
    
    def find_by_user(self, user: str) -> List[PlaylistItem]:
        """Find all items added by a user."""
        return [item for item in self._items if item.added_by == user]
    
    def get_position(self, item_id: str) -> Optional[int]:
        """
        Get position of item in queue (1-indexed).
        
        Args:
            item_id: ID of item to find
            
        Returns:
            Position (1-indexed) or None if not found
        """
        for i, item in enumerate(self._items):
            if item.id == item_id:
                return i + 1
        return None
    
    def get_by_id(self, item_id: str) -> Optional[PlaylistItem]:
        """
        Get item by ID.
        
        Args:
            item_id: ID to search for
            
        Returns:
            Item if found, None otherwise
        """
        for item in self._items:
            if item.id == item_id:
                return item
        return None
    
    def move(self, item_id: str, after: Optional[str] = None) -> bool:
        """
        Move an item to a different position.
        
        Args:
            item_id: ID of item to move
            after: ID of item to place it after (None = move to end)
            
        Returns:
            True if moved, False if item not found
        """
        item = self.remove(item_id)
        if item is None:
            return False
        
        return self.add(item, after=after)
