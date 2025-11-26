# Inspector Plugin

The Inspector plugin provides runtime observability into the NATS event bus. It allows admins to monitor events, inspect loaded plugins, and view system statistics.

## Commands

All commands are admin-only.

- `!inspect events [pattern]` - Show recent events (optionally filtered by pattern)
- `!inspect plugins` - List all loaded plugins and their status
- `!inspect plugin <name>` - Show detailed information about a specific plugin
- `!inspect stats` - Show event statistics (total events, buffer usage, top subjects)
- `!inspect pause` - Pause event capturing
- `!inspect resume` - Resume event capturing

## Configuration

```json
{
  "buffer_size": 1000,
  "default_event_count": 10,
  "include_patterns": null,
  "exclude_patterns": [
    "_INBOX.*",
    "inspector.*"
  ],
  "admins": ["admin_user"],
  "log_to_file": false,
  "log_file_path": "inspector.log"
}
```

## Service

The inspector exposes a service that other plugins can use to access captured events programmatically.

```python
inspector = await get_service("inspector")
events = inspector.get_recent_events(pattern="trivia.*")
```
