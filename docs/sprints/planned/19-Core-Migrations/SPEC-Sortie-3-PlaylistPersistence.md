# SPEC: Sortie 3 - Playlist Persistence & Polish

**Sprint:** 19 - Core Migrations  
**Sortie:** 3 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 1-2 days  
**Priority:** MEDIUM - Completes playlist migration  
**Prerequisites:** Sortie 2 (Playlist Service & Events)

---

## 1. Overview

### 1.1 Purpose

Complete the playlist migration with:

- Database persistence for queue state
- Play history tracking
- User quotas and rate limiting
- Cleanup of old lib/playlist.py

### 1.2 Scope

**In Scope:**
- Database schema for playlist persistence
- Queue recovery on restart
- Play history with duration tracking
- User quotas (max items in queue)
- Rate limiting
- Final cleanup and deprecation of lib/playlist.py

**Out of Scope:**
- Complex analytics
- Playlist templates/presets
- Cross-channel features

### 1.3 Dependencies

- Sorties 1-2 complete
- Database service (Sprint 17)

---

## 2. Technical Design

### 2.1 Extended File Structure

```
plugins/playlist/
├── ...existing files...
├── storage.py            # Database operations
└── tests/
    ├── ...existing tests...
    └── test_storage.py      # Storage tests
```

### 2.2 Database Schema

```sql
-- Queue items (for persistence across restarts)
CREATE TABLE playlist_queue (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    position INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    media_id TEXT NOT NULL,
    title TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(channel, position)
);

CREATE INDEX idx_playlist_queue_channel ON playlist_queue(channel, position);

-- Play history
CREATE TABLE playlist_history (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    media_type TEXT NOT NULL,
    media_id TEXT NOT NULL,
    title TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    added_by TEXT NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    play_duration INTEGER DEFAULT 0,  -- How long it actually played
    skipped BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_playlist_history_channel ON playlist_history(channel);
CREATE INDEX idx_playlist_history_user ON playlist_history(added_by);

-- User statistics
CREATE TABLE playlist_user_stats (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    items_added INTEGER DEFAULT 0,
    items_played INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    total_duration_added INTEGER DEFAULT 0,
    total_duration_played INTEGER DEFAULT 0,
    last_add TIMESTAMP NULL
);

CREATE INDEX idx_playlist_user_stats_user ON playlist_user_stats(user_id);
```

### 2.3 Storage Class

```python
# plugins/playlist/storage.py

from typing import List, Optional
from datetime import datetime
from common.database_service import DatabaseService
from .models import PlaylistItem, MediaType


class PlaylistStorage:
    """Database operations for playlist persistence."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def create_tables(self) -> None:
        """Create playlist tables if not exists."""
        ...
    
    # === Queue Persistence ===
    
    async def save_queue(self, channel: str, items: List[PlaylistItem]) -> None:
        """Save entire queue to database."""
        # Clear existing
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
    
    async def load_queue(self, channel: str) -> List[PlaylistItem]:
        """Load queue from database."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM playlist_queue 
            WHERE channel = ? 
            ORDER BY position
            """,
            (channel,)
        )
        
        return [self._row_to_item(row) for row in rows]
    
    async def clear_queue(self, channel: str) -> None:
        """Clear persisted queue."""
        await self.db.execute(
            "DELETE FROM playlist_queue WHERE channel = ?",
            (channel,)
        )
    
    # === History ===
    
    async def record_play(
        self, 
        channel: str, 
        item: PlaylistItem,
        play_duration: int,
        skipped: bool,
    ) -> None:
        """Record item play in history."""
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
    
    async def get_history(
        self, 
        channel: str, 
        limit: int = 20
    ) -> List[dict]:
        """Get recent play history."""
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
    ) -> List[dict]:
        """Get user's play history."""
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
    
    # === User Stats ===
    
    async def get_user_stats(self, user: str) -> Optional[dict]:
        """Get user playlist statistics."""
        row = await self.db.fetch_one(
            "SELECT * FROM playlist_user_stats WHERE user_id = ?",
            (user,)
        )
        return dict(row) if row else None
    
    async def _update_user_stats(
        self, 
        user: str, 
        duration: int, 
        skipped: bool
    ) -> None:
        """Update user stats after play."""
        await self.db.execute(
            """
            INSERT INTO playlist_user_stats (user_id, items_played, items_skipped,
                                            total_duration_played)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                items_played = items_played + 1,
                items_skipped = items_skipped + ?,
                total_duration_played = total_duration_played + ?
            """,
            (user, 1 if skipped else 0, duration,
             1 if skipped else 0, duration)
        )
    
    async def record_add(self, user: str, duration: int) -> None:
        """Record item add for user stats."""
        await self.db.execute(
            """
            INSERT INTO playlist_user_stats (user_id, items_added, 
                                            total_duration_added, last_add)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                items_added = items_added + 1,
                total_duration_added = total_duration_added + ?,
                last_add = CURRENT_TIMESTAMP
            """,
            (user, duration, duration)
        )
    
    def _row_to_item(self, row) -> PlaylistItem:
        """Convert database row to PlaylistItem."""
        return PlaylistItem(
            id=str(row["id"]),
            media_type=MediaType(row["media_type"]),
            media_id=row["media_id"],
            title=row["title"],
            duration=row["duration"],
            added_by=row["added_by"],
            added_at=row["added_at"],
        )
```

### 2.4 User Quotas & Rate Limiting

```python
# plugins/playlist/quotas.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict


@dataclass
class QuotaConfig:
    """Quota configuration."""
    max_items_per_user: int = 5
    max_duration_per_user: int = 1800  # 30 minutes
    rate_limit_seconds: int = 10
    rate_limit_count: int = 3


class QuotaManager:
    """
    Manage user quotas for playlist additions.
    """
    
    def __init__(self, config: QuotaConfig):
        self.config = config
        self._last_adds: Dict[str, list[datetime]] = {}
    
    def check_quota(
        self, 
        user: str, 
        current_items: int,
        current_duration: int,
        new_duration: int,
    ) -> tuple[bool, str]:
        """
        Check if user can add another item.
        
        Returns:
            (allowed, reason)
        """
        # Check item count
        if current_items >= self.config.max_items_per_user:
            return False, f"You can only have {self.config.max_items_per_user} items in queue"
        
        # Check total duration
        if current_duration + new_duration > self.config.max_duration_per_user:
            max_mins = self.config.max_duration_per_user // 60
            return False, f"You can only have {max_mins} minutes of content queued"
        
        # Check rate limit
        if not self._check_rate_limit(user):
            return False, "Slow down! You're adding too fast."
        
        return True, ""
    
    def record_add(self, user: str) -> None:
        """Record an addition for rate limiting."""
        now = datetime.utcnow()
        if user not in self._last_adds:
            self._last_adds[user] = []
        
        self._last_adds[user].append(now)
        
        # Cleanup old entries
        cutoff = now - timedelta(seconds=self.config.rate_limit_seconds)
        self._last_adds[user] = [
            t for t in self._last_adds[user] if t > cutoff
        ]
    
    def _check_rate_limit(self, user: str) -> bool:
        """Check if user is within rate limit."""
        if user not in self._last_adds:
            return True
        
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.config.rate_limit_seconds)
        recent = [t for t in self._last_adds[user] if t > cutoff]
        
        return len(recent) < self.config.rate_limit_count
```

### 2.5 Extended Plugin

```python
# plugins/playlist/plugin.py (final extensions)

class PlaylistPlugin(PluginBase):
    """Complete playlist plugin with persistence."""
    
    async def setup(self) -> None:
        """Setup with persistence."""
        # Initialize storage
        db_service = await get_database_service()
        self.storage = PlaylistStorage(db_service)
        await self.storage.create_tables()
        
        # Initialize quotas
        self.quota_manager = QuotaManager(QuotaConfig(
            max_items_per_user=self.config.get("max_items_per_user", 5),
            max_duration_per_user=self.config.get("max_duration_per_user", 1800),
        ))
        
        # ... existing setup ...
        
        # Recovery: load persisted queues
        await self._recover_queues()
        
        # Add history commands
        await self.subscribe("rosey.command.playlist.history", self._handle_history)
        await self.subscribe("rosey.command.playlist.mystats", self._handle_mystats)
    
    async def _recover_queues(self) -> None:
        """Recover queues from database on startup."""
        # Get all channels with persisted queues
        channels = await self.storage.get_persisted_channels()
        
        for channel in channels:
            items = await self.storage.load_queue(channel)
            if items:
                self.queues[channel] = PlaylistQueue()
                for item in items:
                    self.queues[channel].add(item)
                
                self.logger.info(f"Recovered {len(items)} items for {channel}")
    
    async def _handle_add(self, msg) -> None:
        """Extended with quotas and persistence."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        url = data.get("args", "").strip()
        
        if not url:
            return await self._reply_usage(msg, "add <url>")
        
        # Check quotas
        queue = self._get_queue(channel)
        user_items = len(queue.find_by_user(user))
        user_duration = sum(i.duration for i in queue.find_by_user(user))
        
        allowed, reason = self.quota_manager.check_quota(
            user, user_items, user_duration, 0  # Duration unknown yet
        )
        
        if not allowed:
            return await self._reply_error(msg, reason)
        
        # Add item
        result = await self.service.add_item(channel, url, user)
        
        if not result.success:
            return await self._reply_error(msg, result.error)
        
        # Record for quotas and stats
        self.quota_manager.record_add(user)
        await self.storage.record_add(user, result.item.duration)
        
        # Persist queue
        await self.storage.save_queue(channel, queue.items)
        
        await self._reply(
            msg,
            f"📺 Added to queue (#{result.position}): {result.item.title}"
        )
    
    async def _on_item_finished(self, channel: str, item: PlaylistItem, skipped: bool) -> None:
        """Called when an item finishes playing."""
        # Record in history
        play_duration = item.duration if not skipped else 0
        await self.storage.record_play(channel, item, play_duration, skipped)
    
    async def _handle_history(self, msg) -> None:
        """Handle !history command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        
        history = await self.storage.get_history(channel, limit=10)
        
        if not history:
            return await self._reply(msg, "📜 No play history yet")
        
        lines = ["📜 **Recent Plays**\n"]
        for item in history:
            status = "⏭️" if item["skipped"] else "✅"
            lines.append(f"{status} {item['title']} - {item['added_by']}")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_mystats(self, msg) -> None:
        """Handle !mystats command."""
        data = json.loads(msg.data.decode())
        user = data["user"]
        
        stats = await self.storage.get_user_stats(user)
        
        if not stats:
            return await self._reply(msg, "📊 No playlist stats yet")
        
        hours = stats["total_duration_played"] // 3600
        minutes = (stats["total_duration_played"] % 3600) // 60
        
        lines = [
            f"📊 **Playlist Stats for {user}**\n",
            f"• Items Added: {stats['items_added']}",
            f"• Items Played: {stats['items_played']}",
            f"• Skip Rate: {stats['items_skipped'] / max(1, stats['items_played']) * 100:.0f}%",
            f"• Total Time: {hours}h {minutes}m",
        ]
        
        await self._reply(msg, "\n".join(lines))
    
    async def teardown(self) -> None:
        """Persist state on shutdown."""
        # Save all queues
        for channel, queue in self.queues.items():
            await self.storage.save_queue(channel, queue.items)
        
        await super().teardown()
```

### 2.6 Migration & Cleanup

```python
# migration/migrate_playlist.py

"""
Migration script to transition from lib/playlist.py to plugins/playlist.

Steps:
1. Load existing queue state from lib/playlist.py
2. Import into plugins/playlist storage
3. Verify data integrity
4. Mark lib/playlist.py as deprecated
"""

async def migrate_playlist_to_plugin():
    """One-time migration script."""
    from lib.playlist import PlaylistManager as OldManager
    from plugins.playlist.storage import PlaylistStorage
    from plugins.playlist.models import PlaylistItem, MediaType
    
    # Load old state
    old_manager = OldManager()
    
    # Get new storage
    storage = PlaylistStorage(db_service)
    
    # Migrate each channel's queue
    for channel, queue in old_manager.queues.items():
        items = []
        for old_item in queue.items:
            item = PlaylistItem(
                id=str(old_item.id),
                media_type=MediaType(old_item.type),
                media_id=old_item.media_id,
                title=old_item.title,
                duration=old_item.duration,
                added_by=old_item.added_by,
                added_at=old_item.added_at,
            )
            items.append(item)
        
        await storage.save_queue(channel, items)
        print(f"Migrated {len(items)} items for {channel}")
```

---

## 3. Implementation Steps

### Step 1: Database Schema (30 minutes)

1. Create Alembic migration
2. Run migration
3. Verify tables

### Step 2: Implement Storage (1.5 hours)

1. Implement PlaylistStorage class
2. Implement queue persistence
3. Implement history tracking
4. Implement user stats
5. Write tests

### Step 3: Implement Quotas (1 hour)

1. Implement QuotaManager
2. Implement rate limiting
3. Write tests

### Step 4: Extend Plugin (1.5 hours)

1. Add storage initialization
2. Add queue recovery on startup
3. Add history commands
4. Add quota checking to add
5. Add persistence on changes

### Step 5: Migration Script (1 hour)

1. Write migration script
2. Test migration
3. Document migration process

### Step 6: Deprecate lib/playlist.py (30 minutes)

1. Add deprecation warnings
2. Update imports
3. Document removal timeline

---

## 4. Acceptance Criteria

### 4.1 Functional

- [ ] Queue persists across bot restarts
- [ ] Play history tracked
- [ ] User stats available via `!mystats`
- [ ] User quotas enforced
- [ ] Rate limiting prevents spam

### 4.2 Technical

- [ ] Database migration runs cleanly
- [ ] Queue recovery on startup
- [ ] Clean shutdown with persistence
- [ ] Test coverage > 85%

### 4.3 Migration

- [ ] Migration script works
- [ ] lib/playlist.py deprecated
- [ ] No data loss during migration

---

## 5. Sample Interactions

```
User: !add https://youtube.com/watch?v=...
Rosey: 📺 Added to queue (#1): Never Gonna Give You Up

[5 more adds...]

User: !add https://youtube.com/watch?v=...
Rosey: ❌ You can only have 5 items in queue

User: !history
Rosey: 📜 **Recent Plays**

       ✅ Never Gonna Give You Up - User
       ⏭️ Some Other Song - User2
       ✅ Cool Track - User

User: !mystats
Rosey: 📊 **Playlist Stats for User**

       • Items Added: 42
       • Items Played: 38
       • Skip Rate: 15%
       • Total Time: 2h 45m

[After restart]
Rosey: [Recovered 3 items for #lobby]
```

---

**Commit Message Template:**
```
feat(plugins): Complete playlist migration

- Add database persistence for queues
- Add play history tracking
- Add user statistics
- Add quota and rate limiting
- Add migration from lib/playlist.py
- Deprecate lib/playlist.py

Implements: SPEC-Sortie-3-PlaylistPersistence.md
Completes: Playlist Plugin Migration
Related: PRD-Core-Migrations.md
Part: 3 of 3 (Playlist Migration)
```
