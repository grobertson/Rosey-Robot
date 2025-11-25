# Playlist Plugin

**Version:** 1.0.0  
**Status:** Foundation (Sortie 1)  
**Architecture:** NATS-based, event-driven

---

## Overview

The Playlist Plugin manages media queues for channels, providing commands for adding, removing, and organizing playlist items. This is a migration of the core `lib/playlist.py` functionality to the modern plugin architecture.

### Features

- ✅ Add media from multiple platforms (YouTube, Vimeo, Twitch, etc.)
- ✅ Queue display with current and upcoming items
- ✅ Skip/shuffle operations
- ✅ Per-channel queue isolation
- ✅ User limits and permissions
- ✅ Event emission for analytics/integration

### Roadmap

- **Sortie 1** (Current): Foundation - basic commands and queue management
- **Sortie 2** (Next): Service interface for other plugins, event integration
- **Sortie 3** (Future): Persistence, history, external catalog integration

---

## Commands

### User Commands

#### `!add <url>`
Add media to the queue.

**Supported URLs:**
- YouTube: `https://youtube.com/watch?v=...` or `https://youtu.be/...`
- YouTube Playlist: `https://youtube.com/playlist?list=...`
- Vimeo: `https://vimeo.com/...`
- Twitch: `https://twitch.tv/videos/...` or `https://clips.twitch.tv/...`
- SoundCloud: `https://soundcloud.com/...`
- Dailymotion: `https://dailymotion.com/video/...`
- Streamable: `https://streamable.com/...`
- Google Drive: `https://drive.google.com/file/d/...`
- Raw files: `.mp4`, `.webm`, `.mp3`, etc. (HTTPS only)

**Examples:**
```
!add https://youtube.com/watch?v=dQw4w9WgXcQ
!add https://vimeo.com/123456
```

**Limits:**
- Default max 5 items per user
- Default max 100 items per queue

#### `!queue`
Display current queue with upcoming items.

**Example output:**
```
📺 **Playlist**

▶️ Now: Cool Video [3:45]
   Added by: Alice

**Up Next:**
1. Another Video [2:30] - Bob
2. Third Video [4:15] - Alice
... and 5 more

📊 7 items | 25m | 3 users
```

#### `!skip`
Skip the currently playing item.

**Example:**
```
!skip
⏭️ Skipped. Now playing: Another Video
```

#### `!remove [id]`
Remove an item from the queue.

- Without ID: Removes your last added item
- With ID: Removes specific item (must be yours or you must be admin)

**Examples:**
```
!remove         # Remove your last item
!remove abc123  # Remove specific item by ID
```

#### `!shuffle`
Randomize the queue order.

**Example:**
```
!shuffle
🔀 Shuffled 7 items
```

### Admin Commands

#### `!clear`
Clear all items from the queue (admin only).

**Example:**
```
!clear
🗑️ Cleared 7 items from queue
```

#### `!move <item_id> <after_id>`
Move an item to a different position.

**Examples:**
```
!move abc123 xyz789  # Move abc123 after xyz789
!move abc123 start   # Move abc123 to start of queue
```

---

## Configuration

Configuration file: `plugins/playlist/config.json`

```json
{
  "max_queue_size": 100,
  "max_items_per_user": 5,
  "allowed_media_types": [],
  "require_duration_check": false,
  "emit_events": true,
  "admins": ["admin1", "admin2"]
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_queue_size` | int | 100 | Maximum items in queue |
| `max_items_per_user` | int | 5 | Max items per user |
| `allowed_media_types` | array | `[]` | Whitelist of media types (empty = all allowed) |
| `require_duration_check` | bool | false | Reject items without duration info |
| `emit_events` | bool | true | Publish events to NATS |
| `admins` | array | `[]` | List of admin usernames |

### Media Type Codes

Use these codes in `allowed_media_types`:
- `yt` - YouTube
- `yp` - YouTube Playlist
- `vi` - Vimeo
- `dm` - Dailymotion
- `sc` - SoundCloud
- `tc` - Twitch Clip
- `tv` - Twitch VOD
- `tw` - Twitch Stream
- `sb` - Streamable
- `gd` - Google Drive
- `fi` - Raw file
- `hl` - HLS stream
- `rt` - RTMP stream

---

## NATS Integration

### Command Subjects (Subscribe)

| Subject | Purpose |
|---------|---------|
| `rosey.command.playlist.add` | Add item to queue |
| `rosey.command.playlist.queue` | Get queue status |
| `rosey.command.playlist.skip` | Skip current item |
| `rosey.command.playlist.remove` | Remove item from queue |
| `rosey.command.playlist.clear` | Clear queue (admin) |
| `rosey.command.playlist.shuffle` | Shuffle queue |
| `rosey.command.playlist.move` | Move item position |

### Event Subjects (Publish)

| Subject | When | Data |
|---------|------|------|
| `playlist.item.added` | Item added to queue | `{item, position, channel}` |
| `playlist.item.removed` | Item removed | `{item, reason, by, channel}` |
| `playlist.item.playing` | Item starts playing | `{item, channel}` |
| `playlist.cleared` | Queue cleared | `{count, by, channel}` |

### Message Format

**Command Request:**
```json
{
  "channel": "channel-name",
  "user": "username",
  "args": "command arguments"
}
```

**Command Response:**
```json
{
  "success": true,
  "message": "Human-readable message",
  "data": {
    "item": {...},
    "position": 3
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error message"
}
```

---

## Architecture

### Channel Isolation

Each channel gets its own `PlaylistQueue` instance. Queues are created on-demand and stored in the plugin's `queues` dictionary.

### Queue Operations

The `PlaylistQueue` class provides thread-safe operations:
- `add(item, after)` - Add item to queue
- `remove(item_id)` - Remove by ID
- `remove_by_user(user, count)` - Remove user's items
- `advance()` - Skip to next item
- `shuffle()` - Randomize order
- `clear()` - Remove all items
- `get_stats()` - Get queue statistics

### Media Parsing

The `MediaParser` class extracts media type and ID from URLs using regex patterns. Supports 15+ platforms out of the box.

### Event Flow

```
User: !add <url>
  ↓
Bot → rosey.command.playlist.add
  ↓
Plugin: Parse URL → Create item → Add to queue
  ↓
Plugin → playlist.item.added event
  ↓
Plugin → Response with position
```

---

## Development

### Running Tests

```bash
pytest plugins/playlist/tests/ -v
pytest plugins/playlist/tests/ --cov=plugins/playlist --cov-report=html
```

### Testing with NATS

```bash
# Start NATS server
nats-server

# Run plugin
python -m plugins.playlist.plugin
```

### Integration

Other plugins can subscribe to playlist events:

```python
# Subscribe to item added events
await nats.subscribe("playlist.item.added", callback=on_item_added)

async def on_item_added(msg):
    data = json.loads(msg.data.decode())
    item = data["item"]
    print(f"New item: {item['title']}")
```

---

## Troubleshooting

### "Queue is full" error
- Check `max_queue_size` in config
- Clear old items with `!clear` (admin)

### "You already have X items in queue" error
- Check `max_items_per_user` in config
- Remove your items with `!remove`

### "Unrecognized media URL" error
- Verify URL is from a supported platform
- Check `allowed_media_types` whitelist
- Ensure HTTPS for raw files

### Items not being removed
- Check if user is admin (for admin commands)
- Verify item ID is correct
- Check item ownership for non-admin removal

---

## Migration Notes

### From lib/playlist.py

This plugin replaces the monolithic `lib/playlist.py` with:
- Modern NATS-based messaging
- Channel-specific queue isolation
- Event-driven architecture
- Better error handling
- Comprehensive testing

### Backward Compatibility

The plugin maintains feature parity with the original implementation:
- All original commands work the same
- Same media type support
- Same queue semantics (FIFO, skip, shuffle)

### Future Enhancements (Sortie 2+)

- **Service interface**: Other plugins can query/modify playlist
- **Persistence**: Queue survives bot restarts
- **History**: Track previously played items
- **Voting**: Community skip voting
- **External catalogs**: TMDb, Plex, Jellyfin integration

---

## License

MIT License - See main project LICENSE file

---

**Maintained by:** Rosey-Robot Team  
**Sprint:** 19 - Core Migrations  
**Last Updated:** November 24, 2025
