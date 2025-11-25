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

- **Sortie 1** ✅: Foundation - basic commands and queue management
- **Sortie 2** ✅: Service interface, metadata fetching, skip voting
- **Sortie 3** ✅: Persistence, history tracking, user quotas

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

#### `!voteskip`
Vote to skip the current item. When enough votes are collected (configurable threshold), the item is automatically skipped.

**Example:**
```
!voteskip
⏭️ Vote recorded (2/3 needed)

!voteskip  # Another user votes
⏭️ Skip vote passed! (3 votes)
```

#### `!history [n]`
Show recent plays for this channel (default 10, max 50).

**Example:**
```
!history 5
📜 **Recent Plays** (last 5):

1. ✅ Cool Video - Alice (14:30)
2. ⏭️ Another Video - Bob (14:25)
3. ✅ Third Video - Alice (14:20)
4. ✅ Fourth Video - Charlie (14:15)
5. ⏭️ Fifth Video - Bob (14:10)
```

#### `!mystats`
Show your personal playlist statistics.

**Example:**
```
!mystats
📊 **Stats for Alice**

Items Added: 42
Items Played: 38
Items Skipped: 4
Time Added: 180m
Time Played: 165m
Last Add: 2025-11-24 14:30
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

## Service API (Sortie 2)

The Playlist Plugin exposes a `PlaylistService` interface for programmatic access by other plugins.

### Getting the Service

```python
# From another plugin
playlist_service = await bot.get_service("playlist")
```

### Service Methods

#### `add_item(channel, url, user, fetch_metadata=True)` → `AddResult`

Add an item to the playlist programmatically.

```python
result = await playlist_service.add_item(
    channel="lobby",
    url="https://youtube.com/watch?v=dQw4w9WgXcQ",
    user="bot_user",
    fetch_metadata=True
)

if result.success:
    print(f"Added: {result.item.title} at position {result.position}")
else:
    print(f"Error: {result.error}")
```

#### `remove_item(channel, item_id, user, is_admin=False)` → `Optional[PlaylistItem]`

Remove an item from the playlist.

#### `get_queue(channel)` → `List[PlaylistItem]`

Get all items in the queue.

```python
items = playlist_service.get_queue("lobby")
for item in items:
    print(f"{item.title} - {item.formatted_duration}")
```

#### `get_current(channel)` → `Optional[PlaylistItem]`

Get the currently playing item.

#### `get_stats(channel)` → `QueueStats`

Get queue statistics (total items, duration, unique users).

#### `skip(channel, user)` → `Optional[PlaylistItem]`

Skip to the next item (direct skip).

#### `vote_skip(channel, user)` → `Dict`

Cast a skip vote. Returns vote status with `votes`, `needed`, and `passed` fields.

```python
result = await playlist_service.vote_skip("lobby", "user1")
print(f"Votes: {result['votes']}/{result['needed']}")
if result['passed']:
    print("Item skipped!")
```

#### `shuffle(channel, user)` → `int`

Shuffle the queue. Returns number of items shuffled.

#### `clear(channel, user)` → `int`

Clear the queue. Returns number of items removed.

#### `subscribe(channel, callback)`

Subscribe to playlist events for a channel.

```python
def on_playlist_event(event_type, data):
    print(f"Event: {event_type}, Data: {data}")

playlist_service.subscribe("lobby", on_playlist_event)
```

### Metadata Fetching

The service automatically fetches metadata (title, duration, thumbnail) for supported platforms using oEmbed APIs:
- **YouTube**: Title, author, thumbnail
- **Vimeo**: Title, author, duration, thumbnail  
- **SoundCloud**: Title, author, thumbnail

Metadata fetching is asynchronous and non-blocking. Items are added immediately with placeholder titles, then updated when metadata arrives.

### Skip Voting

The skip vote system allows democratic playlist control:

- **Configurable threshold**: Default 50% of active users
- **Minimum votes**: Ensures at least N votes needed (default 2)
- **Auto-reset**: Votes reset when item changes
- **Timeout**: Vote sessions expire after 5 minutes (configurable)

**Configuration:**
```json
{
  "skip_threshold": 0.5,
  "min_skip_votes": 2,
  "skip_vote_timeout": 5
}
```

---

## Persistence & History (Sortie 3)

The playlist plugin now includes full database persistence for queue state and play history.

### Queue Persistence

Queues are automatically saved to the database and recovered on bot restart:

- **Auto-save**: Queue state persisted after adds/removes/skips
- **Auto-recovery**: Queues restored on startup
- **Per-channel**: Each channel's queue is independently persisted

**Configuration:**
```json
{
  "persist_queue": true
}
```

### Play History

Every item that plays is recorded in the database:

- **Track plays**: Records title, user, duration, timestamp
- **Track skips**: Marks items that were skipped vs completed
- **Per-channel**: History isolated by channel
- **Query via `!history`**: Users can view recent plays

**History Fields:**
- `title`: Item title
- `added_by`: User who added it
- `played_at`: Timestamp of play
- `play_duration`: Actual seconds played
- `skipped`: Whether item was skipped

### User Statistics

The plugin tracks per-user statistics across all channels:

- **Items added**: Total items user has added
- **Items played**: How many of their items played
- **Items skipped**: How many were skipped
- **Total duration added**: Total seconds of content added
- **Total duration played**: Actual playtime of their content
- **Last add**: Timestamp of most recent add

**Query via `!mystats`**: Users can view their own stats

### User Quotas

To prevent abuse, quotas limit how much a single user can add:

**Item Count Quota:**
- Default: 5 items max per user in queue
- Configurable via `max_items_per_user`

**Duration Quota:**
- Default: 1800 seconds (30 minutes) max per user
- Configurable via `max_duration_per_user`
- Prevents one user from dominating queue time

**Rate Limiting:**
- Default: 3 adds per 10 seconds
- Prevents spam/flooding
- Configurable via `rate_limit_count` and `rate_limit_window`

**Example Error Messages:**
```
You have 5 items in queue (max 5)
Adding would exceed 30 minute limit (1900s total)
Rate limit: max 3 adds per 10 seconds
```

---

## Configuration

Configuration file: `plugins/playlist/config.json`

```json
{
  "max_queue_size": 100,
  "max_items_per_user": 5,
  "max_duration_per_user": 1800,
  "rate_limit_count": 3,
  "rate_limit_window": 10,
  "allowed_media_types": [],
  "require_duration_check": false,
  "emit_events": true,
  "admins": ["admin1", "admin2"],
  "persist_queue": true,
  "skip_threshold": 0.5,
  "min_skip_votes": 2,
  "skip_vote_timeout": 5
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_queue_size` | int | 100 | Maximum items in queue |
| `max_items_per_user` | int | 5 | Max items per user |
| `max_duration_per_user` | int | 1800 | Max total duration (seconds) |
| `rate_limit_count` | int | 3 | Max adds per time window |
| `rate_limit_window` | int | 10 | Rate limit window (seconds) |
| `allowed_media_types` | array | `[]` | Whitelist of media types (empty = all allowed) |
| `require_duration_check` | bool | false | Reject items without duration info |
| `emit_events` | bool | true | Publish events to NATS |
| `admins` | array | `[]` | List of admin usernames |
| `persist_queue` | bool | true | Persist queue to database |
| `skip_threshold` | float | 0.5 | Vote threshold (50%) |
| `min_skip_votes` | int | 2 | Minimum votes to skip |
| `skip_vote_timeout` | int | 5 | Vote timeout (minutes) |

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
