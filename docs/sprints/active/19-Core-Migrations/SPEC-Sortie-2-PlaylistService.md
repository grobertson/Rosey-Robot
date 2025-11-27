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

Implement the playlist service that other plugins can consume via NATS:

- NATS request/reply subjects for programmatic access
- CyTube connector integration
- Metadata fetching (titles, durations)
- Skip voting system
- Comprehensive event emission

**Architecture Note**: This sortie implements the NATS-based service pattern. Other plugins interact with playlist functionality by sending NATS requests to `service.playlist.*` subjects and receiving responses. NO Python object sharing or `get_service()` calls.

### 1.2 Scope

**In Scope:**
- NATS service request/reply subjects for playlist operations
- Service request handlers in playlist plugin
- Metadata fetching via YouTube/Vimeo APIs
- Skip voting system
- CyTube state synchronization
- Real-time event streaming
- Complete request/response schemas

**Out of Scope (Sortie 3):**
- Database persistence
- Play history
- User quotas

**Architecture Pattern:**
Other plugins communicate with playlist via NATS request/reply:
```python
# Consumer sends request
response = await nats_client.request(
    "service.playlist.add_item",
    json.dumps({"channel": "lobby", "url": "...", "user": "Alice"})
)
result = json.loads(response.data)
```

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

**Service Request/Reply Subjects (for other plugins):**

| Subject | Type | Purpose | Request Schema | Response Schema |
|---------|------|---------|----------------|-----------------|
| `service.playlist.add_item` | Request/Reply | Add item to queue | `{channel, url, user}` | `{success, item?, position?, error?}` |
| `service.playlist.remove_item` | Request/Reply | Remove item from queue | `{channel, item_id, user, is_admin}` | `{success, item?, error?}` |
| `service.playlist.get_queue` | Request/Reply | Get all queue items | `{channel}` | `{success, items[], error?}` |
| `service.playlist.get_current` | Request/Reply | Get current playing item | `{channel}` | `{success, item?, error?}` |
| `service.playlist.get_stats` | Request/Reply | Get queue statistics | `{channel}` | `{success, stats{}, error?}` |
| `service.playlist.vote_skip` | Request/Reply | Vote to skip current | `{channel, user}` | `{success, votes, needed, passed, error?}` |
| `service.playlist.skip` | Request/Reply | Direct skip (admin) | `{channel, user}` | `{success, next_item?, error?}` |
| `service.playlist.shuffle` | Request/Reply | Shuffle queue | `{channel}` | `{success, count, error?}` |
| `service.playlist.clear` | Request/Reply | Clear queue | `{channel, user}` | `{success, count, error?}` |

**Event Subjects (notifications):**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `playlist.metadata.fetched` | Publish | Event when metadata retrieved |
| `playlist.skip.vote` | Publish | Event when skip vote cast |
| `playlist.skip.passed` | Publish | Event when skip vote passes |
| `playlist.shuffled` | Publish | Event when queue shuffled |

**CyTube Sync Subjects:**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `playlist.sync.cytube` | Subscribe | Sync request from CyTube |
| `cytube.playlist.update` | Publish | Push update to CyTube |

### 2.3 Service Request Handlers

Instead of a Python `PlaylistService` class, the plugin implements NATS request/reply handlers for each service operation.

```python
# plugins/playlist/plugin.py (extensions for Sortie 2)

class PlaylistPlugin(PluginBase):
    """
    Playlist plugin with NATS service request handlers.
    
    Other plugins interact via NATS request/reply, not Python imports.
    """
    
    async def setup(self) -> None:
        """Extended setup with service request handlers."""
        # Initialize metadata fetcher
        self.metadata_fetcher = MetadataFetcher(
            youtube_api_key=self.config.get("youtube_api_key")
        )
        
        # Initialize vote manager
        self.vote_manager = SkipVoteManager(
            threshold=self.config.get("skip_threshold", 0.5),
            min_votes=self.config.get("min_skip_votes", 2),
        )
        
        # Register service request/reply handlers
        await self.subscribe("service.playlist.add_item", self._service_add_item)
        await self.subscribe("service.playlist.remove_item", self._service_remove_item)
        await self.subscribe("service.playlist.get_queue", self._service_get_queue)
        await self.subscribe("service.playlist.get_current", self._service_get_current)
        await self.subscribe("service.playlist.get_stats", self._service_get_stats)
        await self.subscribe("service.playlist.vote_skip", self._service_vote_skip)
        await self.subscribe("service.playlist.skip", self._service_skip)
        await self.subscribe("service.playlist.shuffle", self._service_shuffle)
        await self.subscribe("service.playlist.clear", self._service_clear)
        
        # ... existing command subscriptions from Sortie 1 ...
        
        self.logger.info(f"{self.NAME} plugin loaded with service handlers")
    
    # === Service Request Handlers (NATS request/reply) ===
    
    async def _service_add_item(self, msg) -> None:
        """
        Service handler: Add item to playlist.
        
        Request: {channel, url, user}
        Response: {success, item?, position?, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            url = data["url"]
            user = data["user"]
            
            # Parse URL
            try:
                media_type, media_id = MediaParser.parse(url)
            except ValueError as e:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": f"Invalid URL: {str(e)}"
                }).encode())
                return
            
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
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Queue is full"
                }).encode())
                return
            
            position = queue.length
            
            # Start metadata fetch (async, non-blocking)
            asyncio.create_task(
                self._fetch_and_update_metadata(channel, item)
            )
            
            # Emit event
            await self.publish("playlist.item.added", {
                "event": "playlist.item.added",
                "channel": channel,
                "item": item.to_dict(),
                "position": position,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Reply with success
            await msg.respond(json.dumps({
                "success": True,
                "item": item.to_dict(),
                "position": position,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service add_item error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": f"Internal error: {str(e)}"
            }).encode())
    
    async def _service_remove_item(self, msg) -> None:
        """
        Service handler: Remove item from playlist.
        
        Request: {channel, item_id, user, is_admin}
        Response: {success, item?, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            item_id = data["item_id"]
            user = data["user"]
            is_admin = data.get("is_admin", False)
            
            queue = self._get_queue(channel)
            
            # Find item first
            item = None
            for i in queue.items:
                if i.id == item_id:
                    item = i
                    break
            
            if not item:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Item not found"
                }).encode())
                return
            
            # Check permission
            if item.added_by != user and not is_admin:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Permission denied"
                }).encode())
                return
            
            removed = queue.remove(item_id)
            
            if removed:
                await self.publish("playlist.item.removed", {
                    "event": "playlist.item.removed",
                    "channel": channel,
                    "item": removed.to_dict(),
                    "reason": "removed",
                    "by": user,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            await msg.respond(json.dumps({
                "success": True,
                "item": removed.to_dict() if removed else None,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service remove_item error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_get_queue(self, msg) -> None:
        """
        Service handler: Get queue items.
        
        Request: {channel}
        Response: {success, items[], error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            
            queue = self._get_queue(channel)
            items = [item.to_dict() for item in queue.items]
            
            await msg.respond(json.dumps({
                "success": True,
                "items": items,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service get_queue error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_get_current(self, msg) -> None:
        """
        Service handler: Get current playing item.
        
        Request: {channel}
        Response: {success, item?, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            
            queue = self._get_queue(channel)
            current = queue.current
            
            await msg.respond(json.dumps({
                "success": True,
                "item": current.to_dict() if current else None,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service get_current error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_get_stats(self, msg) -> None:
        """
        Service handler: Get queue statistics.
        
        Request: {channel}
        Response: {success, stats{}, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            
            queue = self._get_queue(channel)
            stats = queue.get_stats()
            
            await msg.respond(json.dumps({
                "success": True,
                "stats": {
                    "total_items": stats.total_items,
                    "total_duration": stats.total_duration,
                    "unique_users": stats.unique_users,
                }
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service get_stats error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_vote_skip(self, msg) -> None:
        """
        Service handler: Vote to skip current item.
        
        Request: {channel, user}
        Response: {success, votes, needed, passed, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            user = data["user"]
            
            queue = self._get_queue(channel)
            
            if not queue.current:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Nothing playing"
                }).encode())
                return
            
            result = self.vote_manager.vote(channel, user)
            
            await self.publish("playlist.skip.vote", {
                "event": "playlist.skip.vote",
                "channel": channel,
                "user": user,
                "votes": result["votes"],
                "needed": result["needed"],
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            if result["passed"]:
                # Skip to next
                skipped = queue.current
                next_item = queue.advance()
                
                await self.publish("playlist.skip.passed", {
                    "event": "playlist.skip.passed",
                    "channel": channel,
                    "votes": result["votes"],
                    "skipped_item": skipped.to_dict(),
                    "next_item": next_item.to_dict() if next_item else None,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            await msg.respond(json.dumps({
                "success": True,
                "votes": result["votes"],
                "needed": result["needed"],
                "passed": result["passed"],
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service vote_skip error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_skip(self, msg) -> None:
        """
        Service handler: Direct skip (admin action).
        
        Request: {channel, user}
        Response: {success, next_item?, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            user = data["user"]
            
            queue = self._get_queue(channel)
            skipped = queue.current
            
            if not skipped:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Nothing playing"
                }).encode())
                return
            
            next_item = queue.advance()
            
            await self.publish("playlist.item.removed", {
                "event": "playlist.item.removed",
                "channel": channel,
                "item": skipped.to_dict(),
                "reason": "skipped",
                "by": user,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            if next_item:
                await self.publish("playlist.item.playing", {
                    "event": "playlist.item.playing",
                    "channel": channel,
                    "item": next_item.to_dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            await msg.respond(json.dumps({
                "success": True,
                "next_item": next_item.to_dict() if next_item else None,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service skip error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_shuffle(self, msg) -> None:
        """
        Service handler: Shuffle queue.
        
        Request: {channel}
        Response: {success, count, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            
            queue = self._get_queue(channel)
            count = queue.length
            queue.shuffle()
            
            await self.publish("playlist.shuffled", {
                "event": "playlist.shuffled",
                "channel": channel,
                "count": count,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            await msg.respond(json.dumps({
                "success": True,
                "count": count,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service shuffle error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_clear(self, msg) -> None:
        """
        Service handler: Clear queue.
        
        Request: {channel, user}
        Response: {success, count, error?}
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            user = data["user"]
            
            queue = self._get_queue(channel)
            count = queue.clear()
            
            await self.publish("playlist.cleared", {
                "event": "playlist.cleared",
                "channel": channel,
                "count": count,
                "by": user,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            await msg.respond(json.dumps({
                "success": True,
                "count": count,
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Service clear error: {e}")
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    # === Helper Methods ===
    
    async def _fetch_and_update_metadata(
        self, 
        channel: str, 
        item: PlaylistItem
    ) -> None:
        """Fetch metadata and update item."""
        try:
            metadata = await self.metadata_fetcher.fetch(
                item.media_type, 
                item.media_id
            )
            
            item.title = metadata.get("title", item.title)
            item.duration = metadata.get("duration", 0)
            item.thumbnail_url = metadata.get("thumbnail")
            item.channel_name = metadata.get("channel")
            
            await self.publish("playlist.metadata.fetched", {
                "event": "playlist.metadata.fetched",
                "channel": channel,
                "item": item.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            })
            
        except Exception as e:
            self.logger.warning(f"Metadata fetch failed for {item.media_id}: {e}")
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

### 2.7 Command Handler Updates

Update command handlers to use internal queue methods (same as Sortie 1 but with metadata fetching):

```python
# plugins/playlist/plugin.py (command handler updates)

class PlaylistPlugin(PluginBase):
    """Command handlers use internal methods, not service."""
    
    async def _handle_add(self, msg) -> None:
        """Handle !add command with metadata fetching."""
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
            return await self._reply_error(msg, "Queue is full!")
        
        position = queue.length
        
        # Fetch metadata asynchronously
        asyncio.create_task(
            self._fetch_and_update_metadata(channel, item)
        )
        
        await self._reply(msg, f"📺 Added to queue (#{position}): {item.title}")
        
        # Emit event
        await self.publish("playlist.item.added", {
            "event": "playlist.item.added",
            "channel": channel,
            "item": item.to_dict(),
            "position": position,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    async def _handle_voteskip(self, msg) -> None:
        """Handle !voteskip command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        
        queue = self._get_queue(channel)
        if not queue.current:
            return await self._reply_error(msg, "Nothing is playing!")
        
        result = self.vote_manager.vote(channel, user)
        
        if not result["success"]:
            return await self._reply_error(msg, result.get("error", "Vote failed"))
        
        if result["already_voted"]:
            return await self._reply(msg, "You already voted to skip!")
        
        await self.publish("playlist.skip.vote", {
            "event": "playlist.skip.vote",
            "channel": channel,
            "user": user,
            "votes": result["votes"],
            "needed": result["needed"],
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        if result["passed"]:
            # Skip to next
            skipped = queue.current
            next_item = queue.advance()
            
            await self.publish("playlist.skip.passed", {
                "event": "playlist.skip.passed",
                "channel": channel,
                "votes": result["votes"],
                "skipped_item": skipped.to_dict(),
                "next_item": next_item.to_dict() if next_item else None,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
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

### Step 3: Implement Service Request Handlers (2.5 hours)

1. Add all service request/reply subscriptions in setup()
2. Implement each handler method (_service_add_item, etc.)
3. Ensure proper request/response JSON format
4. Add comprehensive error handling
5. Write tests for each handler

### Step 4: Update Command Handlers (1.5 hours)

1. Update plugin setup to initialize metadata and voting
2. Update _handle_add to include metadata fetching
3. Add _handle_voteskip command
4. Wire up vote manager

### Step 5: Add CyTube Sync (1 hour)

1. Implement CyTubeSynchronizer
2. Wire up with existing CyTube connector
3. Test bidirectional sync

### Step 6: Integration Testing (1 hour)

1. Test service request/reply from mock plugin
2. Test metadata fetching
3. Test vote system
4. Test event emission
5. Test timeout scenarios

---

## 4. Acceptance Criteria

### 4.1 Functional

- [ ] Service request/reply handlers implemented for all operations
- [ ] Metadata fetched automatically on add
- [ ] Skip voting works with configurable threshold
- [ ] Events emitted for all state changes
- [ ] CyTube sync bidirectional
- [ ] Other plugins can call playlist via NATS subjects

### 4.2 Technical

- [ ] All service operations via NATS request/reply
- [ ] Async metadata fetching (non-blocking)
- [ ] Proper error handling in all handlers
- [ ] Request/response schemas documented
- [ ] Test coverage > 85%
- [ ] No get_service() or Python object sharing

---

## 5. Sample Service Usage via NATS

```python
# From another plugin - using NATS request/reply

import json
import asyncio


class SomeOtherPlugin(PluginBase):
    """Example plugin using playlist service via NATS."""
    
    async def example_add_item(self):
        """Add item to playlist via NATS request."""
        try:
            # Prepare request
            request = {
                "channel": "lobby",
                "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
                "user": "Alice",
            }
            
            # Send request via NATS (with timeout)
            response = await self.nats_client.request(
                "service.playlist.add_item",
                json.dumps(request).encode(),
                timeout=5.0,  # 5 second timeout
            )
            
            # Parse response
            result = json.loads(response.data.decode())
            
            if result["success"]:
                item = result["item"]
                position = result["position"]
                self.logger.info(f"Added to playlist at #{position}: {item['title']}")
                return True
            else:
                self.logger.error(f"Failed to add: {result['error']}")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error("Playlist service timeout")
            return False
        except Exception as e:
            self.logger.error(f"Playlist service error: {e}")
            return False
    
    async def example_get_queue(self):
        """Get queue items via NATS request."""
        try:
            request = {"channel": "lobby"}
            
            response = await self.nats_client.request(
                "service.playlist.get_queue",
                json.dumps(request).encode(),
                timeout=5.0,
            )
            
            result = json.loads(response.data.decode())
            
            if result["success"]:
                items = result["items"]
                self.logger.info(f"Queue has {len(items)} items")
                return items
            else:
                self.logger.error(f"Failed to get queue: {result.get('error')}")
                return []
                
        except Exception as e:
            self.logger.error(f"Get queue error: {e}")
            return []
    
    async def example_vote_skip(self, user: str):
        """Vote to skip via NATS request."""
        try:
            request = {"channel": "lobby", "user": user}
            
            response = await self.nats_client.request(
                "service.playlist.vote_skip",
                json.dumps(request).encode(),
                timeout=5.0,
            )
            
            result = json.loads(response.data.decode())
            
            if result["success"]:
                votes = result["votes"]
                needed = result["needed"]
                passed = result["passed"]
                
                if passed:
                    self.logger.info(f"Skip vote passed! ({votes} votes)")
                else:
                    self.logger.info(f"Vote recorded: {votes}/{needed}")
                
                return passed
            else:
                self.logger.error(f"Vote failed: {result.get('error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"Vote skip error: {e}")
            return False
    
    async def example_listen_to_events(self):
        """Subscribe to playlist events."""
        async def handle_item_added(msg):
            data = json.loads(msg.data.decode())
            item = data["item"]
            position = data["position"]
            self.logger.info(f"New item added: {item['title']} at #{position}")
        
        async def handle_skip_passed(msg):
            data = json.loads(msg.data.decode())
            votes = data["votes"]
            self.logger.info(f"Skip vote passed with {votes} votes")
        
        # Subscribe to events
        await self.subscribe("playlist.item.added", handle_item_added)
        await self.subscribe("playlist.skip.passed", handle_skip_passed)
```

### Benefits of NATS Request/Reply Pattern

✅ **Process Isolation**: Plugins can run as separate processes  
✅ **No Shared Memory**: No direct Python object references  
✅ **Independent Deployment**: Restart one plugin without affecting others  
✅ **Timeout Control**: Each request has configurable timeout  
✅ **Error Handling**: Clear success/error responses  
✅ **Observable**: All service calls visible in NATS monitoring  
✅ **Testable**: Easy to mock service responses in tests  
✅ **Language Agnostic**: Could rewrite plugin in different language

---

**Commit Message Template:**
```
feat(plugins): Add playlist service via NATS request/reply

- Implement service request/reply handlers for playlist operations
- Add metadata fetching (YouTube, Vimeo, SoundCloud)
- Add skip voting system
- Add CyTube synchronization
- Emit comprehensive events via NATS

Architecture: Uses NATS request/reply pattern for inter-plugin communication.
Other plugins call playlist via service.playlist.* subjects, not Python imports.

Implements: SPEC-Sortie-2-PlaylistService.md
Related: PRD-Core-Migrations.md
Part: 2 of 3 (Playlist Migration)
```
