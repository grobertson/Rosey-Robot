# SPEC: Sortie 2 - Playlist Service & Events

**Sprint:** 19 - Core Migrations  
**Sortie:** 2 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** HIGH - Enables other plugins to use playlist  
**Prerequisites:** Sortie 1 (Playlist Foundation)

---

## 1. Overview

### 1.1 Purpose

Implement the PlaylistService that other plugins can consume:

- Service interface for programmatic access
- CyTube connector integration
- Metadata fetching (titles, durations)
- Skip voting system
- Comprehensive event emission

### 1.2 Scope

**In Scope:**
- `PlaylistService` class with full API
- Service registration for other plugins
- Metadata fetching via YouTube/Vimeo APIs
- Skip voting system
- CyTube state synchronization
- Real-time event streaming

**Out of Scope (Sortie 3):**
- Database persistence
- Play history
- User quotas

### 1.3 Dependencies

- Sortie 1 (Playlist Foundation) - MUST be complete
- CyTube connector (existing)
- httpx for API requests
- Event bus (existing)

---

## 2. Technical Design

### 2.1 Extended File Structure

Additions to playlist plugin:

```
plugins/playlist/
├── ...existing files...
├── service.py            # PlaylistService implementation
├── metadata.py           # Metadata fetching
├── voting.py             # Skip voting system
├── cytube_sync.py        # CyTube integration
└── tests/
    ├── ...existing tests...
    ├── test_metadata.py     # Metadata tests
    ├── test_voting.py       # Voting tests
    └── test_cytube_sync.py  # Sync tests
```

### 2.2 New NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `playlist.metadata.fetched` | Publish | Event when metadata retrieved |
| `playlist.skip.vote` | Publish | Event when skip vote cast |
| `playlist.skip.passed` | Publish | Event when skip vote passes |
| `playlist.sync.cytube` | Subscribe | Sync request from CyTube |
| `cytube.playlist.update` | Publish | Push update to CyTube |

### 2.3 PlaylistService Design

```python
# plugins/playlist/service.py

from typing import List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

from .models import PlaylistItem, MediaType
from .queue import PlaylistQueue, QueueStats
from .metadata import MetadataFetcher
from .voting import SkipVoteManager


@dataclass
class AddResult:
    """Result of adding an item."""
    success: bool
    item: Optional[PlaylistItem] = None
    position: Optional[int] = None
    error: Optional[str] = None


@dataclass
class PlaybackState:
    """Current playback state."""
    current: Optional[PlaylistItem]
    position_seconds: int  # Position in current item
    is_playing: bool
    queue_length: int


class PlaylistService:
    """
    Service interface for playlist management.
    
    Exposed to other plugins for programmatic access.
    
    Example usage from another plugin:
        playlist = await get_service("playlist")
        result = await playlist.add_item(channel, url, user)
        if result.success:
            print(f"Added at position {result.position}")
    """
    
    def __init__(
        self,
        queues: dict[str, PlaylistQueue],
        metadata_fetcher: 'MetadataFetcher',
        vote_manager: 'SkipVoteManager',
        event_callback: Callable[[str, dict], Any],
    ):
        self._queues = queues
        self._metadata = metadata_fetcher
        self._votes = vote_manager
        self._emit_event = event_callback
        
        # Subscribers for real-time updates
        self._subscribers: dict[str, List[Callable]] = {}
    
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
            fetch_metadata: Whether to fetch title/duration
            
        Returns:
            AddResult with success status and item details
        """
        from .models import MediaParser
        
        # Parse URL
        try:
            media_type, media_id = MediaParser.parse(url)
        except ValueError as e:
            return AddResult(success=False, error=str(e))
        
        # Create item
        item = PlaylistItem(
            id="",
            media_type=media_type,
            media_id=media_id,
            title=f"Loading...",
            duration=0,
            added_by=user,
        )
        
        # Add to queue
        queue = self._get_queue(channel)
        if not queue.add(item):
            return AddResult(success=False, error="Queue is full")
        
        position = queue.length
        
        # Fetch metadata asynchronously
        if fetch_metadata:
            asyncio.create_task(
                self._fetch_and_update_metadata(channel, item)
            )
        
        # Emit event
        await self._emit_event("playlist.item.added", {
            "channel": channel,
            "item": item.to_dict(),
            "position": position,
        })
        
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
            channel: Channel
            item_id: Item ID to remove
            user: User requesting removal
            is_admin: Whether user is admin
            
        Returns:
            Removed item, or None if not found/not allowed
        """
        queue = self._get_queue(channel)
        
        # Find item first
        item = None
        for i in queue.items:
            if i.id == item_id:
                item = i
                break
        
        if not item:
            return None
        
        # Check permission
        if item.added_by != user and not is_admin:
            return None
        
        removed = queue.remove(item_id)
        
        if removed:
            await self._emit_event("playlist.item.removed", {
                "channel": channel,
                "item": removed.to_dict(),
                "reason": "removed",
                "by": user,
            })
        
        return removed
    
    def get_queue(self, channel: str) -> List[PlaylistItem]:
        """Get all items in a channel's queue."""
        return self._get_queue(channel).items
    
    def get_current(self, channel: str) -> Optional[PlaylistItem]:
        """Get currently playing item."""
        return self._get_queue(channel).current
    
    def get_stats(self, channel: str) -> QueueStats:
        """Get queue statistics."""
        return self._get_queue(channel).get_stats()
    
    def get_playback_state(self, channel: str) -> PlaybackState:
        """Get current playback state."""
        queue = self._get_queue(channel)
        return PlaybackState(
            current=queue.current,
            position_seconds=0,  # Would need CyTube integration
            is_playing=queue.current is not None,
            queue_length=queue.length,
        )
    
    # === Playback Control ===
    
    async def skip(self, channel: str, user: str) -> Optional[PlaylistItem]:
        """
        Skip current item (direct skip, no voting).
        
        Returns:
            Next item, or None if queue empty
        """
        queue = self._get_queue(channel)
        skipped = queue.current
        
        if not skipped:
            return None
        
        next_item = queue.advance()
        
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
        
        return next_item
    
    async def vote_skip(self, channel: str, user: str) -> dict:
        """
        Cast a skip vote.
        
        Returns:
            Vote status with current/needed counts
        """
        queue = self._get_queue(channel)
        
        if not queue.current:
            return {"success": False, "error": "Nothing playing"}
        
        result = self._votes.vote(channel, user)
        
        await self._emit_event("playlist.skip.vote", {
            "channel": channel,
            "user": user,
            "votes": result["votes"],
            "needed": result["needed"],
        })
        
        if result["passed"]:
            await self.skip(channel, "vote")
            await self._emit_event("playlist.skip.passed", {
                "channel": channel,
                "votes": result["votes"],
            })
        
        return result
    
    async def shuffle(self, channel: str) -> int:
        """
        Shuffle the queue.
        
        Returns:
            Number of items shuffled
        """
        queue = self._get_queue(channel)
        count = queue.length
        queue.shuffle()
        
        await self._emit_event("playlist.shuffled", {
            "channel": channel,
            "count": count,
        })
        
        return count
    
    async def clear(self, channel: str, user: str) -> int:
        """
        Clear the queue.
        
        Returns:
            Number of items cleared
        """
        queue = self._get_queue(channel)
        count = queue.clear()
        
        await self._emit_event("playlist.cleared", {
            "channel": channel,
            "count": count,
            "by": user,
        })
        
        return count
    
    # === Subscriptions ===
    
    def subscribe(
        self, 
        channel: str, 
        callback: Callable[[str, dict], None]
    ) -> None:
        """Subscribe to playlist events for a channel."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)
    
    def unsubscribe(self, channel: str, callback: Callable) -> None:
        """Unsubscribe from playlist events."""
        if channel in self._subscribers:
            self._subscribers[channel].remove(callback)
    
    # === Private Methods ===
    
    def _get_queue(self, channel: str) -> PlaylistQueue:
        """Get or create queue for channel."""
        if channel not in self._queues:
            self._queues[channel] = PlaylistQueue()
        return self._queues[channel]
    
    async def _fetch_and_update_metadata(
        self, 
        channel: str, 
        item: PlaylistItem
    ) -> None:
        """Fetch metadata and update item."""
        try:
            metadata = await self._metadata.fetch(item.media_type, item.media_id)
            
            item.title = metadata.get("title", item.title)
            item.duration = metadata.get("duration", 0)
            item.thumbnail_url = metadata.get("thumbnail")
            item.channel_name = metadata.get("channel")
            
            await self._emit_event("playlist.metadata.fetched", {
                "channel": channel,
                "item": item.to_dict(),
            })
            
        except Exception as e:
            # Keep placeholder title on error
            pass
```

### 2.4 Metadata Fetching

```python
# plugins/playlist/metadata.py

import httpx
from typing import Optional
import os
from .models import MediaType


class MetadataFetcher:
    """
    Fetch metadata for media items.
    
    Supports:
    - YouTube (via oEmbed or Data API)
    - Vimeo (via oEmbed)
    - SoundCloud (via oEmbed)
    """
    
    OEMBED_URLS = {
        MediaType.YOUTUBE: "https://www.youtube.com/oembed",
        MediaType.VIMEO: "https://vimeo.com/api/oembed.json",
        MediaType.SOUNDCLOUD: "https://soundcloud.com/oembed",
    }
    
    def __init__(self, youtube_api_key: Optional[str] = None):
        self._youtube_api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def fetch(self, media_type: MediaType, media_id: str) -> dict:
        """
        Fetch metadata for a media item.
        
        Returns:
            Dict with keys: title, duration, thumbnail, channel
        """
        if media_type == MediaType.YOUTUBE:
            return await self._fetch_youtube(media_id)
        elif media_type == MediaType.VIMEO:
            return await self._fetch_vimeo(media_id)
        elif media_type == MediaType.SOUNDCLOUD:
            return await self._fetch_soundcloud(media_id)
        else:
            return {"title": media_id, "duration": 0}
    
    async def _fetch_youtube(self, video_id: str) -> dict:
        """Fetch YouTube metadata."""
        client = await self._get_client()
        
        # Try oEmbed first (no API key needed)
        url = f"https://www.youtube.com/watch?v={video_id}"
        oembed_url = f"{self.OEMBED_URLS[MediaType.YOUTUBE]}?url={url}&format=json"
        
        response = await client.get(oembed_url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", video_id),
                "duration": 0,  # oEmbed doesn't include duration
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "channel": data.get("author_name"),
            }
        
        # Fallback
        return {"title": f"YouTube: {video_id}", "duration": 0}
    
    async def _fetch_vimeo(self, video_id: str) -> dict:
        """Fetch Vimeo metadata."""
        client = await self._get_client()
        
        url = f"https://vimeo.com/{video_id}"
        oembed_url = f"{self.OEMBED_URLS[MediaType.VIMEO]}?url={url}"
        
        response = await client.get(oembed_url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", video_id),
                "duration": data.get("duration", 0),
                "thumbnail": data.get("thumbnail_url"),
                "channel": data.get("author_name"),
            }
        
        return {"title": f"Vimeo: {video_id}", "duration": 0}
    
    async def _fetch_soundcloud(self, track_path: str) -> dict:
        """Fetch SoundCloud metadata."""
        client = await self._get_client()
        
        url = f"https://soundcloud.com/{track_path}"
        oembed_url = f"{self.OEMBED_URLS[MediaType.SOUNDCLOUD]}?url={url}&format=json"
        
        response = await client.get(oembed_url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", track_path),
                "duration": 0,  # Would need API for duration
                "thumbnail": data.get("thumbnail_url"),
                "channel": data.get("author_name"),
            }
        
        return {"title": f"SoundCloud: {track_path}", "duration": 0}
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

### 2.5 Skip Voting System

```python
# plugins/playlist/voting.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set


@dataclass
class VoteSession:
    """Active vote session for a channel."""
    channel: str
    item_id: str  # Item being voted on
    voters: Set[str] = field(default_factory=set)
    started_at: datetime = field(default_factory=datetime.utcnow)
    threshold: float = 0.5  # Percentage needed


class SkipVoteManager:
    """
    Manage skip voting for channels.
    
    Votes reset when:
    - Item changes
    - Vote passes
    - Timeout (configurable)
    """
    
    def __init__(
        self,
        threshold: float = 0.5,  # 50% of active users
        timeout_minutes: int = 5,
        min_votes: int = 2,
    ):
        self.threshold = threshold
        self.timeout = timedelta(minutes=timeout_minutes)
        self.min_votes = min_votes
        self._sessions: Dict[str, VoteSession] = {}
        
        # Track active users per channel (for threshold calculation)
        self._active_users: Dict[str, Set[str]] = {}
    
    def vote(self, channel: str, user: str) -> dict:
        """
        Cast a skip vote.
        
        Returns:
            {
                "success": bool,
                "votes": int,
                "needed": int,
                "passed": bool,
                "already_voted": bool,
            }
        """
        session = self._get_or_create_session(channel)
        
        # Check if already voted
        if user in session.voters:
            return {
                "success": False,
                "votes": len(session.voters),
                "needed": self._calculate_needed(channel),
                "passed": False,
                "already_voted": True,
            }
        
        # Add vote
        session.voters.add(user)
        
        votes = len(session.voters)
        needed = self._calculate_needed(channel)
        passed = votes >= needed
        
        if passed:
            self._clear_session(channel)
        
        return {
            "success": True,
            "votes": votes,
            "needed": needed,
            "passed": passed,
            "already_voted": False,
        }
    
    def reset(self, channel: str) -> None:
        """Reset votes for a channel (e.g., when item changes)."""
        self._clear_session(channel)
    
    def set_active_users(self, channel: str, users: Set[str]) -> None:
        """Update active user count for threshold calculation."""
        self._active_users[channel] = users
    
    def get_status(self, channel: str) -> dict:
        """Get current vote status."""
        session = self._sessions.get(channel)
        
        if not session:
            return {"active": False, "votes": 0, "needed": self._calculate_needed(channel)}
        
        return {
            "active": True,
            "votes": len(session.voters),
            "needed": self._calculate_needed(channel),
            "voters": list(session.voters),
        }
    
    def _get_or_create_session(self, channel: str) -> VoteSession:
        """Get existing session or create new one."""
        if channel not in self._sessions:
            self._sessions[channel] = VoteSession(
                channel=channel,
                item_id="",  # Will be set by plugin
                threshold=self.threshold,
            )
        return self._sessions[channel]
    
    def _clear_session(self, channel: str) -> None:
        """Clear session for channel."""
        self._sessions.pop(channel, None)
    
    def _calculate_needed(self, channel: str) -> int:
        """Calculate votes needed to pass."""
        active = len(self._active_users.get(channel, set()))
        
        if active < self.min_votes:
            return self.min_votes
        
        return max(self.min_votes, int(active * self.threshold) + 1)
```

### 2.6 CyTube Synchronization

```python
# plugins/playlist/cytube_sync.py

from typing import Optional, Callable
import asyncio


class CyTubeSynchronizer:
    """
    Synchronize playlist state with CyTube.
    
    Handles:
    - Push playlist updates to CyTube
    - Receive CyTube state changes
    - Handle playback position
    """
    
    def __init__(
        self,
        cytube_client,
        on_cytube_update: Callable,
    ):
        self._cytube = cytube_client
        self._on_update = on_cytube_update
        self._syncing = False
    
    async def push_queue_update(self, channel: str, items: list) -> None:
        """Push queue update to CyTube."""
        if self._syncing:
            return  # Avoid feedback loop
        
        await self._cytube.send_queue_update(channel, items)
    
    async def push_now_playing(self, channel: str, item: dict) -> None:
        """Update CyTube now playing."""
        if self._syncing:
            return
        
        await self._cytube.send_media_update(channel, item)
    
    async def handle_cytube_change(self, event: dict) -> None:
        """Handle incoming CyTube state change."""
        self._syncing = True
        try:
            event_type = event.get("type")
            
            if event_type == "queue":
                await self._on_update("queue_changed", event)
            elif event_type == "mediaUpdate":
                await self._on_update("media_changed", event)
            elif event_type == "delete":
                await self._on_update("item_deleted", event)
        finally:
            self._syncing = False
    
    def get_playback_position(self, channel: str) -> int:
        """Get current playback position in seconds."""
        return self._cytube.get_position(channel)
```

### 2.7 Extended Plugin

```python
# plugins/playlist/plugin.py (extensions)

class PlaylistPlugin(PluginBase):
    """Extended with service and metadata."""
    
    async def setup(self) -> None:
        """Extended setup with service."""
        # Initialize metadata fetcher
        self.metadata_fetcher = MetadataFetcher(
            youtube_api_key=self.config.get("youtube_api_key")
        )
        
        # Initialize vote manager
        self.vote_manager = SkipVoteManager(
            threshold=self.config.get("skip_threshold", 0.5),
            min_votes=self.config.get("min_skip_votes", 2),
        )
        
        # Initialize service
        self.service = PlaylistService(
            queues=self.queues,
            metadata_fetcher=self.metadata_fetcher,
            vote_manager=self.vote_manager,
            event_callback=self._emit_event,
        )
        
        # Register service
        await self.register_service("playlist", self.service)
        
        # ... existing subscriptions ...
        
        # Subscribe to vote skip
        await self.subscribe("rosey.command.playlist.voteskip", self._handle_voteskip)
    
    async def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit event via NATS."""
        data["event"] = event_type
        data["timestamp"] = datetime.utcnow().isoformat()
        await self.publish(event_type, data)
    
    async def _handle_add(self, msg) -> None:
        """Handle !add with metadata fetching."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        url = data.get("args", "").strip()
        
        if not url:
            return await self._reply_usage(msg, "add <url>")
        
        # Use service for add
        result = await self.service.add_item(channel, url, user)
        
        if not result.success:
            return await self._reply_error(msg, result.error)
        
        await self._reply(
            msg, 
            f"📺 Added to queue (#{result.position}): {result.item.title}"
        )
    
    async def _handle_voteskip(self, msg) -> None:
        """Handle !voteskip command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        
        result = await self.service.vote_skip(channel, user)
        
        if not result["success"]:
            return await self._reply_error(msg, result.get("error", "Vote failed"))
        
        if result["already_voted"]:
            return await self._reply(msg, "You already voted to skip!")
        
        if result["passed"]:
            await self._reply(msg, f"⏭️ Skip vote passed! ({result['votes']} votes)")
        else:
            await self._reply(
                msg, 
                f"⏭️ Vote recorded ({result['votes']}/{result['needed']} needed)"
            )
```

---

## 3. Implementation Steps

### Step 1: Implement MetadataFetcher (1.5 hours)

1. Implement oEmbed fetching
2. Handle YouTube, Vimeo, SoundCloud
3. Add error handling and fallbacks
4. Write tests with mocked HTTP

### Step 2: Implement SkipVoteManager (1 hour)

1. Implement vote tracking
2. Implement threshold calculation
3. Implement session management
4. Write tests

### Step 3: Implement PlaylistService (2.5 hours)

1. Implement all service methods
2. Implement event emission
3. Implement subscription system
4. Write comprehensive tests

### Step 4: Integrate with Plugin (1.5 hours)

1. Update plugin setup
2. Register service
3. Update command handlers to use service
4. Wire up metadata fetching

### Step 5: Add CyTube Sync (1 hour)

1. Implement CyTubeSynchronizer
2. Wire up with existing CyTube connector
3. Test bidirectional sync

### Step 6: Integration Testing (1 hour)

1. Test service API
2. Test metadata fetching
3. Test vote system
4. Test event emission

---

## 4. Acceptance Criteria

### 4.1 Functional

- [ ] PlaylistService exposed to other plugins
- [ ] Metadata fetched automatically on add
- [ ] Skip voting works with configurable threshold
- [ ] Events emitted for all state changes
- [ ] CyTube sync bidirectional

### 4.2 Technical

- [ ] Service API matches design
- [ ] Async metadata fetching (non-blocking)
- [ ] Proper error handling
- [ ] Test coverage > 85%

---

## 5. Sample Service Usage

```python
# From another plugin
playlist = await get_service("playlist")

# Add an item
result = await playlist.add_item("lobby", "https://youtube.com/...", "user1")
if result.success:
    print(f"Added at #{result.position}")

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

---

**Commit Message Template:**
```
feat(plugins): Add playlist service and events

- Implement PlaylistService for other plugins
- Add metadata fetching (YouTube, Vimeo, SoundCloud)
- Add skip voting system
- Add CyTube synchronization
- Emit comprehensive events

Implements: SPEC-Sortie-2-PlaylistService.md
Related: PRD-Core-Migrations.md
Part: 2 of 3 (Playlist Migration)
```
