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
├── storage.py            # Storage adapter using NATS storage API
└── tests/
    ├── ...existing tests...
    └── test_storage.py      # Storage tests

migrations/
└── playlist/
    ├── 001_create_queue.sql
    ├── 002_create_history.sql
    └── 003_create_user_stats.sql
```

### 2.2 Database Schema (via Migrations)

**Migration Files** (Sprint 15 pattern):

**`migrations/playlist/001_create_queue.sql`:**
```sql
-- UP
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

-- DOWN
DROP INDEX IF EXISTS idx_playlist_queue_channel;
DROP TABLE IF EXISTS playlist_queue;
```

**`migrations/playlist/002_create_history.sql`:**
```sql
-- UP
CREATE TABLE playlist_history (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    media_type TEXT NOT NULL,
    media_id TEXT NOT NULL,
    title TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    added_by TEXT NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    play_duration INTEGER DEFAULT 0,
    skipped BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_playlist_history_channel ON playlist_history(channel);
CREATE INDEX idx_playlist_history_user ON playlist_history(added_by);

-- DOWN
DROP INDEX IF EXISTS idx_playlist_history_user;
DROP INDEX IF EXISTS idx_playlist_history_channel;
DROP TABLE IF EXISTS playlist_history;
```

**`migrations/playlist/003_create_user_stats.sql`:**
```sql
-- UP
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

-- DOWN
DROP INDEX IF EXISTS idx_playlist_user_stats_user;
DROP TABLE IF EXISTS playlist_user_stats;
```

**Note:** Schema is managed via migrations (Sprint 15 pattern). Plugin code does NOT contain CREATE TABLE statements.

### 2.3 Storage Adapter

```python
# plugins/playlist/storage.py

"""
Storage adapter for playlist plugin using NATS-based storage API.

Uses:
- KV Storage (Sprint 12): Counters, feature flags
- Row Operations (Sprint 13): CRUD operations
- Advanced Operators (Sprint 14): Atomic updates, complex queries
- Parameterized SQL (Sprint 17): Complex multi-table queries

Note: Database access is infrastructure (like NATS), not plugin-to-plugin
communication. Uses BotDatabase methods which are acceptable as established
in Sprint 17.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime


class PlaylistStorage:
    """
    Storage adapter for playlist persistence using proper storage APIs.
    
    This class demonstrates the correct storage pattern for plugins:
    - Schema via migrations (not CREATE TABLE in code)
    - KV storage for simple counters
    - Row operations for CRUD
    - Parameterized SQL for complex queries
    """
    
    def __init__(self, nats_client, plugin_name: str = "playlist"):
        """
        Initialize storage adapter.
        
        Args:
            nats_client: NATS client for storage API requests
            plugin_name: Plugin namespace for storage isolation
        """
        self.nc = nats_client
        self.plugin_name = plugin_name
    
    # === Queue Persistence (Using Row Operations API) ===
    
    async def save_queue(self, channel: str, items: List[dict]) -> None:
        """
        Save entire queue to database using row operations API.
        
        Uses Sprint 13 (Row Operations) pattern with atomic batch insert.
        """
        # Clear existing queue for channel
        await self.nc.request(
            f"db.row.{self.plugin_name}.delete",
            json.dumps({
                "table": "queue",
                "filter": {"channel": channel}
            }).encode()
        )
        
        # Batch insert new queue items
        for i, item in enumerate(items):
            await self.nc.request(
                f"db.row.{self.plugin_name}.insert",
                json.dumps({
                    "table": "queue",
                    "values": {
                        "channel": channel,
                        "position": i,
                        "media_type": item.get("media_type"),
                        "media_id": item.get("media_id"),
                        "title": item.get("title"),
                        "duration": item.get("duration", 0),
                        "added_by": item.get("added_by"),
                        "added_at": item.get("added_at")
                    }
                }).encode()
            )
    
    async def load_queue(self, channel: str) -> List[dict]:
        """
        Load queue from database using row operations API.
        
        Uses Sprint 13 (Row Operations) with ordered query.
        """
        response = await self.nc.request(
            f"db.row.{self.plugin_name}.select",
            json.dumps({
                "table": "queue",
                "filter": {"channel": channel},
                "order": {"position": 1}  # ASC order
            }).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        return data.get("rows", [])
    
    async def clear_queue(self, channel: str) -> None:
        """Clear persisted queue using row operations API."""
        await self.nc.request(
            f"db.row.{self.plugin_name}.delete",
            json.dumps({
                "table": "queue",
                "filter": {"channel": channel}
            }).encode()
        )
    
    # === History (Using Row Operations API) ===
    
    async def record_play(
        self, 
        channel: str, 
        item: dict,
        play_duration: int,
        skipped: bool,
    ) -> None:
        """
        Record item play in history using row operations API.
        
        Uses Sprint 13 (Row Operations) insert.
        """
        await self.nc.request(
            f"db.row.{self.plugin_name}.insert",
            json.dumps({
                "table": "history",
                "values": {
                    "channel": channel,
                    "media_type": item.get("media_type"),
                    "media_id": item.get("media_id"),
                    "title": item.get("title"),
                    "duration": item.get("duration", 0),
                    "added_by": item.get("added_by"),
                    "play_duration": play_duration,
                    "skipped": skipped
                }
            }).encode()
        )
        
        # Update user stats atomically
        await self._update_user_stats(item.get("added_by"), item.get("duration", 0), skipped)
    
    async def get_history(
        self, 
        channel: str, 
        limit: int = 20
    ) -> List[dict]:
        """
        Get recent play history using row operations API.
        
        Uses Sprint 13 (Row Operations) with ordering and limit.
        """
        response = await self.nc.request(
            f"db.row.{self.plugin_name}.select",
            json.dumps({
                "table": "history",
                "filter": {"channel": channel},
                "order": {"played_at": -1},  # DESC order
                "limit": limit
            }).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        return data.get("rows", [])
    
    async def get_user_history(
        self, 
        user: str, 
        limit: int = 20
    ) -> List[dict]:
        """
        Get user's play history using row operations API.
        
        Uses Sprint 13 (Row Operations) with filtering.
        """
        response = await self.nc.request(
            f"db.row.{self.plugin_name}.select",
            json.dumps({
                "table": "history",
                "filter": {"added_by": user},
                "order": {"played_at": -1},  # DESC order
                "limit": limit
            }).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        return data.get("rows", [])
    
    # === User Stats (Using KV Storage + Atomic Updates) ===
    
    async def get_user_stats(self, user: str) -> Optional[dict]:
        """
        Get user playlist statistics using row operations API.
        
        Uses Sprint 13 (Row Operations) select.
        """
        response = await self.nc.request(
            f"db.row.{self.plugin_name}.select",
            json.dumps({
                "table": "user_stats",
                "filter": {"user_id": user},
                "limit": 1
            }).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        rows = data.get("rows", [])
        return rows[0] if rows else None
    
    async def _update_user_stats(
        self, 
        user: str, 
        duration: int, 
        skipped: bool
    ) -> None:
        """
        Update user stats after play using atomic operators.
        
        Uses Sprint 14 (Advanced Operators) with $inc for atomic updates.
        This avoids race conditions in concurrent plays.
        """
        await self.nc.request(
            f"db.row.{self.plugin_name}.update",
            json.dumps({
                "table": "user_stats",
                "filter": {"user_id": user},
                "update": {
                    "$inc": {
                        "items_played": 1,
                        "items_skipped": 1 if skipped else 0,
                        "total_duration_played": duration
                    }
                },
                "upsert": True  # Create if doesn't exist
            }).encode()
        )
    
    async def record_add(self, user: str, duration: int) -> None:
        """
        Record item add for user stats using atomic operators.
        
        Uses Sprint 14 (Advanced Operators) with $inc and $set for atomic updates.
        """
        await self.nc.request(
            f"db.row.{self.plugin_name}.update",
            json.dumps({
                "table": "user_stats",
                "filter": {"user_id": user},
                "update": {
                    "$inc": {
                        "items_added": 1,
                        "total_duration_added": duration
                    },
                    "$set": {
                        "last_add": int(datetime.now().timestamp())
                    }
                },
                "upsert": True
            }).encode()
        )

### 2.4 QuotaManager (Using KV Storage)

```python
# plugins/playlist/quotas.py

"""
Quota management using KV Storage (Sprint 12) for rate limiting.

Demonstrates Sprint 12 (KV Storage) pattern for temporary data with TTL.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict
import json


@dataclass
class QuotaConfig:
    """Quota configuration."""
    max_items_per_user: int = 5
    max_duration_per_user: int = 1800  # 30 minutes
    rate_limit_seconds: int = 10
    rate_limit_count: int = 3


class QuotaManager:
    """
    Manage user quotas using KV storage for rate limiting.
    
    Uses Sprint 12 (KV Storage) with TTL for temporary rate limit data.
    """
    
    def __init__(self, nats_client, config: QuotaConfig, plugin_name: str = "playlist"):
        self.nc = nats_client
        self.plugin_name = plugin_name
        self.config = config
    
    async def check_quota(
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
        
        # Check rate limit using KV storage
        if not await self._check_rate_limit(user):
            return False, "Slow down! You're adding too fast."
        
        return True, ""
    
    async def record_add(self, user: str) -> None:
        """
        Record an addition for rate limiting using KV storage.
        
        Uses Sprint 12 (KV Storage) with TTL to auto-expire old entries.
        """
        key = f"ratelimit:{user}"
        
        # Get current rate limit data
        response = await self.nc.request(
            f"db.kv.{self.plugin_name}.get",
            json.dumps({"key": key}).encode(),
            timeout=2.0
        )
        
        data = json.loads(response.data.decode())
        timestamps = data.get("value", []) if data.get("exists") else []
        
        # Add current timestamp
        now = int(datetime.now().timestamp())
        timestamps.append(now)
        
        # Store with TTL matching rate limit window
        await self.nc.request(
            f"db.kv.{self.plugin_name}.set",
            json.dumps({
                "key": key,
                "value": timestamps,
                "ttl_seconds": self.config.rate_limit_seconds
            }).encode()
        )
    
    async def _check_rate_limit(self, user: str) -> bool:
        """
        Check if user is within rate limit using KV storage.
        
        Uses Sprint 12 (KV Storage) to retrieve recent additions.
        """
        key = f"ratelimit:{user}"
        
        response = await self.nc.request(
            f"db.kv.{self.plugin_name}.get",
            json.dumps({"key": key}).encode(),
            timeout=2.0
        )
        
        data = json.loads(response.data.decode())
        if not data.get("exists"):
            return True
        
        timestamps = data.get("value", [])
        now = int(datetime.now().timestamp())
        cutoff = now - self.config.rate_limit_seconds
        
        # Count recent additions (KV TTL handles cleanup)
        recent = [t for t in timestamps if t > cutoff]
        return len(recent) < self.config.rate_limit_count
```

### 2.5 Extended Plugin

```python
# plugins/playlist/plugin.py (final extensions)

class PlaylistPlugin(PluginBase):
    """Complete playlist plugin with persistence."""
    
    async def setup(self) -> None:
        """Setup with persistence using storage API."""
        # Initialize storage adapter (NATS-based, no DB service needed)
        self.storage = PlaylistStorage(
            nats_client=self._nc,
            plugin_name="playlist"
        )
        
        # Initialize quotas (uses KV storage internally)
        self.quota_manager = QuotaManager(
            nats_client=self._nc,
            config=QuotaConfig(
                max_items_per_user=self.config.get("max_items_per_user", 5),
                max_duration_per_user=self.config.get("max_duration_per_user", 1800),
            ),
            plugin_name="playlist"
        )
        
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

### Step 1: Create Migration Files (30 minutes)

1. Create `migrations/playlist/` directory
2. Write 001_create_queue.sql (with UP/DOWN)
3. Write 002_create_history.sql (with UP/DOWN)
4. Write 003_create_user_stats.sql (with UP/DOWN)
5. Test migrations (UP then DOWN then UP)

**Verification:**
```bash
# Apply migrations
python -m common.database migrate --plugin playlist --action up

# Verify tables created
sqlite3 bot_data.db ".schema playlist_queue"

# Test rollback
python -m common.database migrate --plugin playlist --action down
```

### Step 2: Implement Storage Adapter (2 hours)

1. Create `plugins/playlist/storage.py`
2. Implement `PlaylistStorage` class using NATS storage API
3. Implement queue operations (save/load/clear) with row operations API
4. Implement history operations with row operations API  
5. Implement user stats with atomic operators
6. Write comprehensive tests (mock NATS, not database)

**Key Pattern:**
```python
# Use NATS requests, not direct SQL
await self.nc.request("db.row.playlist.insert", ...)
await self.nc.request("db.row.playlist.select", ...)
```

### Step 3: Implement QuotaManager with KV Storage (1 hour)

1. Create `plugins/playlist/quotas.py`
2. Implement `QuotaManager` using KV storage for rate limiting
3. Use KV storage with TTL for auto-expiring rate limit data
4. Write tests (mock NATS KV subjects)

**Key Pattern:**
```python
# Use KV storage for temporary data
await self.nc.request("db.kv.playlist.set", 
    json.dumps({"key": f"ratelimit:{user}", "value": [...], "ttl_seconds": 10}))
```

### Step 4: Extend Plugin (1.5 hours)

1. Update plugin setup to use storage adapter
2. Add queue recovery on startup
3. Add history commands (!history, !mystats)
4. Add quota checking to add handler
5. Add persistence after queue changes
6. Write integration tests

### Step 5: Migration Script (Optional, 1 hour)

1. Write script to migrate from lib/playlist.py if exists
2. Test migration with sample data
3. Document migration process

**Note:** Only needed if lib/playlist.py has existing data to migrate.

### Step 6: Documentation (30 minutes)

1. Update plugin README with new commands
2. Document quota configuration
3. Document migration files
4. Update acceptance criteria

---

## 4. Acceptance Criteria

### 4.1 Functional

- [ ] Queue persists across bot restarts
- [ ] Play history tracked
- [ ] User stats available via `!mystats`
- [ ] User quotas enforced
- [ ] Rate limiting prevents spam

### 4.2 Technical

- [ ] Migration files created for all 3 tables (with UP/DOWN)
- [ ] All database operations use storage API (no direct SQL in plugin code)
- [ ] Tests use NATS mocking (no database mocking)
- [ ] Schema DDL removed from plugin code
- [ ] Queue recovery on startup works
- [ ] Clean shutdown with persistence
- [ ] Test coverage > 85%

### 4.3 Storage Architecture Compliance

- [ ] ✅ Uses migrations for schema (Sprint 15 pattern)
- [ ] ✅ Uses row operations for CRUD (Sprint 13 pattern)
- [ ] ✅ Uses advanced operators for atomic updates (Sprint 14 pattern)
- [ ] ✅ Uses KV storage for rate limiting (Sprint 12 pattern)
- [ ] ✅ No direct SQL queries in plugin code
- [ ] ✅ No CREATE TABLE statements in plugin code
- [ ] ✅ Storage adapter uses NATS requests only

### 4.4 Migration (if applicable)

- [ ] Migration script works if lib/playlist.py exists
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
