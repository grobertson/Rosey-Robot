# SPEC: Sortie 1 - Playlist Plugin Foundation

**Sprint:** 19 - Core Migrations  
**Sortie:** 1 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2-3 days  
**Priority:** HIGH - Core migration, other plugins depend on this

---

## 1. Overview

### 1.1 Purpose

Migrate the existing `lib/playlist.py` functionality into a proper NATS-based plugin, demonstrating:

- Migration pattern from monolith to plugin
- Service exposure (PlaylistService)
- Backward compatibility during migration
- Clean separation of concerns

### 1.2 Current State Analysis

The existing `lib/playlist.py` contains:
- Playlist item models
- Playlist state management  
- Media type detection
- Queue operations

This needs to be:
1. Wrapped in a plugin structure
2. Exposed as a service for other plugins
3. Event-driven via NATS
4. Backward compatible during transition

### 1.3 Scope

**In Scope (Sortie 1):**
- Plugin structure and configuration
- Migrate core playlist models
- Basic NATS command handlers
- PlaylistService interface definition
- Unit tests for migrated code

**Out of Scope (Sortie 2):**
- Full service implementation
- CyTube connector integration
- Event emission

**Out of Scope (Sortie 3):**
- Persistence layer
- History tracking
- Advanced features

### 1.4 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Existing `lib/playlist.py` (reference)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/playlist/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── models.py             # Playlist item models (migrated)
├── queue.py              # Queue management (migrated)
├── service.py            # PlaylistService (new)
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_models.py       # Model tests
    ├── test_queue.py        # Queue tests
    ├── test_service.py      # Service tests
    └── test_plugin.py       # Integration tests
```

### 2.1 NATS Subjects

**Command Subjects (for user commands):**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.playlist.add` | Subscribe | Handle `!add` command |
| `rosey.command.playlist.queue` | Subscribe | Handle `!queue` command |
| `rosey.command.playlist.skip` | Subscribe | Handle `!skip` command |
| `rosey.command.playlist.remove` | Subscribe | Handle `!remove` command |
| `rosey.command.playlist.clear` | Subscribe | Handle `!clear` command |
| `rosey.command.playlist.shuffle` | Subscribe | Handle `!shuffle` command |

**Event Subjects (notifications to other plugins):**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `playlist.item.added` | Publish | Event when item added |
| `playlist.item.playing` | Publish | Event when item starts |
| `playlist.item.removed` | Publish | Event when item removed |
| `playlist.cleared` | Publish | Event when queue cleared |

**Service Subjects (for other plugins to call):**

Service subjects will be added in Sortie 2. These use NATS request/reply pattern for inter-plugin communication. See SPEC-Sortie-2 for complete service API via NATS.

### 2.3 Models (Migrated)

```python
# plugins/playlist/models.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import re


class MediaType(Enum):
    """Supported media types."""
    YOUTUBE = "yt"
    VIMEO = "vi"
    DAILYMOTION = "dm"
    SOUNDCLOUD = "sc"
    TWITCH_CLIP = "tc"
    CUSTOM = "cu"
    UNKNOWN = "unknown"


@dataclass
class PlaylistItem:
    """
    Represents an item in the playlist.
    
    Migrated from lib/playlist.py with enhancements.
    """
    id: str  # Unique ID within playlist
    media_type: MediaType
    media_id: str  # Platform-specific ID
    title: str
    duration: int  # Seconds, 0 if unknown
    added_by: str
    added_at: datetime = field(default_factory=datetime.utcnow)
    
    # Optional metadata
    thumbnail_url: Optional[str] = None
    channel_name: Optional[str] = None
    
    @property
    def url(self) -> str:
        """Reconstruct URL from media type and ID."""
        urls = {
            MediaType.YOUTUBE: f"https://youtube.com/watch?v={self.media_id}",
            MediaType.VIMEO: f"https://vimeo.com/{self.media_id}",
            MediaType.DAILYMOTION: f"https://dailymotion.com/video/{self.media_id}",
            MediaType.SOUNDCLOUD: f"https://soundcloud.com/{self.media_id}",
        }
        return urls.get(self.media_type, self.media_id)
    
    @property
    def formatted_duration(self) -> str:
        """Format duration as HH:MM:SS or MM:SS."""
        if self.duration == 0:
            return "??:??"
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    def to_dict(self) -> dict:
        """Serialize for NATS/JSON."""
        return {
            "id": self.id,
            "media_type": self.media_type.value,
            "media_id": self.media_id,
            "title": self.title,
            "duration": self.duration,
            "added_by": self.added_by,
            "added_at": self.added_at.isoformat(),
            "url": self.url,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PlaylistItem':
        """Deserialize from NATS/JSON."""
        return cls(
            id=data["id"],
            media_type=MediaType(data["media_type"]),
            media_id=data["media_id"],
            title=data["title"],
            duration=data["duration"],
            added_by=data["added_by"],
            added_at=datetime.fromisoformat(data["added_at"]),
        )


class MediaParser:
    """Parse URLs to extract media type and ID."""
    
    PATTERNS = {
        MediaType.YOUTUBE: [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ],
        MediaType.VIMEO: [
            r'vimeo\.com/(\d+)',
        ],
        MediaType.DAILYMOTION: [
            r'dailymotion\.com/video/([a-zA-Z0-9]+)',
        ],
        MediaType.SOUNDCLOUD: [
            r'soundcloud\.com/([a-zA-Z0-9-]+/[a-zA-Z0-9-]+)',
        ],
    }
    
    @classmethod
    def parse(cls, url: str) -> tuple[MediaType, str]:
        """
        Parse a URL to extract media type and ID.
        
        Returns:
            Tuple of (MediaType, media_id)
            
        Raises:
            ValueError: If URL format not recognized
        """
        for media_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return media_type, match.group(1)
        
        raise ValueError(f"Unrecognized media URL: {url}")
    
    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Check if URL is a supported media URL."""
        try:
            cls.parse(url)
            return True
        except ValueError:
            return False
```

### 2.4 Queue Management (Migrated)

```python
# plugins/playlist/queue.py

from dataclasses import dataclass, field
from typing import List, Optional, Iterator
from collections import deque
import uuid
import random

from .models import PlaylistItem


@dataclass
class QueueStats:
    """Statistics about the queue."""
    total_items: int
    total_duration: int  # Seconds
    unique_users: int


class PlaylistQueue:
    """
    Manages the playlist queue.
    
    Thread-safe for concurrent access.
    """
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._items: deque[PlaylistItem] = deque()
        self._current: Optional[PlaylistItem] = None
        self._history: deque[PlaylistItem] = deque(maxlen=50)
    
    @property
    def current(self) -> Optional[PlaylistItem]:
        """Currently playing item."""
        return self._current
    
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
    
    def add(self, item: PlaylistItem) -> bool:
        """
        Add an item to the queue.
        
        Returns:
            True if added, False if queue full
        """
        if len(self._items) >= self.max_size:
            return False
        
        # Generate unique ID if not set
        if not item.id:
            item.id = str(uuid.uuid4())[:8]
        
        self._items.append(item)
        return True
    
    def remove(self, item_id: str) -> Optional[PlaylistItem]:
        """
        Remove an item by ID.
        
        Returns:
            Removed item, or None if not found
        """
        for i, item in enumerate(self._items):
            if item.id == item_id:
                del self._items[i]
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
            return self._current
        
        self._current = None
        return None
    
    def peek(self, count: int = 5) -> List[PlaylistItem]:
        """Preview upcoming items without removing."""
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
        """Get position of item in queue (1-indexed)."""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                return i + 1
        return None
```

### 2.5 Plugin Foundation

```python
# plugins/playlist/plugin.py

import json
from typing import Optional
from lib.plugin.base import PluginBase
from .models import PlaylistItem, MediaParser, MediaType
from .queue import PlaylistQueue


class PlaylistPlugin(PluginBase):
    """
    Playlist management plugin.
    
    Commands:
        !add <url> - Add media to queue
        !queue - Show current queue
        !skip - Vote to skip current
        !remove [id] - Remove from queue
        !clear - Clear queue (admin)
        !shuffle - Shuffle queue
    
    Note: This plugin does NOT expose services via get_service().
    All inter-plugin communication happens via NATS request/reply.
    See Sortie 2 for NATS service subject definitions.
    """
    
    NAME = "playlist"
    VERSION = "1.0.0"
    DESCRIPTION = "Media playlist management"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        
        max_queue = self.config.get("max_queue_size", 100)
        self.queues: dict[str, PlaylistQueue] = {}  # channel -> queue
        self.default_max_queue = max_queue
    
    def _get_queue(self, channel: str) -> PlaylistQueue:
        """Get or create queue for a channel."""
        if channel not in self.queues:
            self.queues[channel] = PlaylistQueue(
                max_size=self.default_max_queue
            )
        return self.queues[channel]
    
    async def setup(self) -> None:
        """Register command handlers."""
        await self.subscribe("rosey.command.playlist.add", self._handle_add)
        await self.subscribe("rosey.command.playlist.queue", self._handle_queue)
        await self.subscribe("rosey.command.playlist.skip", self._handle_skip)
        await self.subscribe("rosey.command.playlist.remove", self._handle_remove)
        await self.subscribe("rosey.command.playlist.clear", self._handle_clear)
        await self.subscribe("rosey.command.playlist.shuffle", self._handle_shuffle)
        
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup."""
        self.queues.clear()
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_add(self, msg) -> None:
        """Handle !add <url> command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        url = data.get("args", "").strip()
        
        if not url:
            return await self._reply_usage(msg, "add <url>")
        
        # Parse URL
        try:
            media_type, media_id = MediaParser.parse(url)
        except ValueError:
            return await self._reply_error(msg, "Unrecognized media URL")
        
        # Create item (title will be fetched in Sortie 2)
        item = PlaylistItem(
            id="",  # Will be assigned by queue
            media_type=media_type,
            media_id=media_id,
            title=f"[{media_type.value}] {media_id}",  # Placeholder
            duration=0,  # Will be fetched
            added_by=user,
        )
        
        # Add to queue
        queue = self._get_queue(channel)
        if not queue.add(item):
            return await self._reply_error(msg, "Queue is full!")
        
        position = queue.length
        await self._reply(msg, f"📺 Added to queue (#{position}): {item.title}")
        
        # Emit event
        await self.publish("playlist.item.added", {
            "event": "playlist.item.added",
            "channel": channel,
            "item": item.to_dict(),
            "position": position,
        })
    
    async def _handle_queue(self, msg) -> None:
        """Handle !queue command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        
        queue = self._get_queue(channel)
        
        if queue.is_empty and not queue.current:
            return await self._reply(msg, "📺 Queue is empty")
        
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
        total_time = stats.total_duration
        if total_time > 0:
            hours, remainder = divmod(total_time, 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            lines.append(f"\n📊 {stats.total_items} items | {time_str} | {stats.unique_users} users")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_skip(self, msg) -> None:
        """Handle !skip command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        
        queue = self._get_queue(channel)
        
        if not queue.current:
            return await self._reply_error(msg, "Nothing is playing!")
        
        # For now, direct skip. Voting system in Sortie 2.
        skipped = queue.current
        next_item = queue.advance()
        
        if next_item:
            await self._reply(msg, f"⏭️ Skipped. Now playing: {next_item.title}")
        else:
            await self._reply(msg, "⏭️ Skipped. Queue is now empty.")
        
        await self.publish("playlist.item.removed", {
            "event": "playlist.item.removed",
            "channel": channel,
            "item": skipped.to_dict(),
            "reason": "skipped",
            "by": user,
        })
    
    async def _handle_remove(self, msg) -> None:
        """Handle !remove [id] command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
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
            item = queue.remove(item_id)
            if not item:
                return await self._reply_error(msg, f"Item '{item_id}' not found")
            
            # Check permission
            is_admin = await self._check_admin(user)
            if item.added_by != user and not is_admin:
                # Put it back
                queue.add(item)
                return await self._reply_error(msg, "You can only remove your own items")
        
        await self._reply(msg, f"🗑️ Removed: {item.title}")
        
        await self.publish("playlist.item.removed", {
            "event": "playlist.item.removed",
            "channel": channel,
            "item": item.to_dict(),
            "reason": "removed",
            "by": user,
        })
    
    async def _handle_clear(self, msg) -> None:
        """Handle !clear command (admin only)."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        
        if not await self._check_admin(user):
            return await self._reply_error(msg, "Admin only command")
        
        queue = self._get_queue(channel)
        count = queue.clear()
        
        await self._reply(msg, f"🗑️ Cleared {count} items from queue")
        
        await self.publish("playlist.cleared", {
            "event": "playlist.cleared",
            "channel": channel,
            "count": count,
            "by": user,
        })
    
    async def _handle_shuffle(self, msg) -> None:
        """Handle !shuffle command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        
        queue = self._get_queue(channel)
        
        if queue.length < 2:
            return await self._reply_error(msg, "Need at least 2 items to shuffle")
        
        queue.shuffle()
        await self._reply(msg, f"🔀 Shuffled {queue.length} items")
```

### 2.6 Configuration

```json
{
  "max_queue_size": 100,
  "max_items_per_user": 5,
  "allowed_media_types": ["yt", "vi", "sc"],
  "require_duration_check": false,
  "admins": []
}
```

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/playlist/` directory
2. Create all files with docstrings
3. Create `config.json` with defaults

### Step 2: Migrate Models (1.5 hours)

1. Analyze existing `lib/playlist.py`
2. Implement `PlaylistItem` dataclass
3. Implement `MediaType` enum
4. Implement `MediaParser` class
5. Write comprehensive tests

### Step 3: Migrate Queue (1.5 hours)

1. Implement `PlaylistQueue` class
2. Implement all queue operations
3. Implement channel isolation
4. Write tests for queue operations

### Step 4: Implement Plugin (2 hours)

1. Implement `PlaylistPlugin.__init__()`
2. Implement `setup()` with subscriptions
3. Implement all command handlers
4. Basic event emission
5. Channel queue management

### Step 5: Testing (1.5 hours)

1. Unit tests for models
2. Unit tests for queue
3. Integration tests for plugin
4. Test channel isolation

### Step 6: Documentation (30 minutes)

1. Write README.md
2. Document commands
3. Document migration plan

---

## 4. Test Cases

### 4.1 Model Tests

| Test | Validation |
|------|------------|
| Parse YouTube URL | Correct type and ID |
| Parse Vimeo URL | Correct type and ID |
| Parse invalid URL | ValueError raised |
| Duration formatting | HH:MM:SS format |
| Serialization roundtrip | Identical after to_dict/from_dict |

### 4.2 Queue Tests

| Test | Validation |
|------|------------|
| Add item | Item in queue |
| Add to full queue | Returns False |
| Remove by ID | Item removed |
| Remove by user | Only user's items |
| Advance | Current updated, history tracked |
| Shuffle | Order changed |
| Clear | All items removed |
| Stats | Correct counts |

### 4.3 Plugin Tests

| Command | Expected |
|---------|----------|
| `!add <youtube-url>` | Added to queue |
| `!add invalid` | Error message |
| `!queue` | Shows queue |
| `!skip` | Advances queue |
| `!remove` | Removes user's item |
| `!clear` (admin) | Clears queue |
| `!shuffle` | Shuffles queue |

---

## 5. Acceptance Criteria

### 5.1 Functional

- [ ] `!add <url>` adds YouTube/Vimeo/SoundCloud
- [ ] `!queue` shows current and upcoming
- [ ] `!skip` advances to next item
- [ ] `!remove` removes items (own or admin)
- [ ] `!clear` clears queue (admin only)
- [ ] `!shuffle` randomizes queue
- [ ] Queues isolated per channel

### 5.2 Technical

- [ ] Models fully migrated from lib/playlist.py
- [ ] Queue operations thread-safe
- [ ] Events emitted on state changes
- [ ] Test coverage > 85%

### 5.3 Migration

- [ ] Existing lib/playlist.py still works
- [ ] No breaking changes to consumers
- [ ] Migration path documented

---

## 6. Sample Interactions

```
User: !add https://youtube.com/watch?v=dQw4w9WgXcQ
Rosey: 📺 Added to queue (#1): [yt] dQw4w9WgXcQ

User: !queue
Rosey: 📺 **Playlist**

       **Up Next:**
       1. [yt] dQw4w9WgXcQ [??:??] - User

       📊 1 item | 0m | 1 user

User: !shuffle
Rosey: ❌ Need at least 2 items to shuffle

User: !add https://vimeo.com/123456
Rosey: 📺 Added to queue (#2): [vi] 123456

User: !shuffle
Rosey: 🔀 Shuffled 2 items

Admin: !clear
Rosey: 🗑️ Cleared 2 items from queue
```

---

## 7. Checklist

### Pre-Implementation
- [ ] Review existing lib/playlist.py
- [ ] Identify all consumers
- [ ] Plan migration path

### Implementation
- [ ] Create plugin directory structure
- [ ] Migrate PlaylistItem model
- [ ] Migrate MediaParser
- [ ] Implement PlaylistQueue
- [ ] Implement PlaylistPlugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing
- [ ] Compare behavior to original
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add playlist plugin foundation

- Migrate PlaylistItem model from lib/playlist.py
- Migrate MediaParser with URL patterns
- Implement PlaylistQueue with channel isolation
- Add basic command handlers
- Emit playlist events

Implements: SPEC-Sortie-1-PlaylistFoundation.md
Related: PRD-Core-Migrations.md
Part: 1 of 3 (Playlist Migration)
```
