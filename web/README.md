# Web Status Server

A live web dashboard for monitoring your CyTube bot's statistics and metrics.

## Features

- **Real-time Statistics**
  - Peak chat users (high water mark)
  - Peak connected viewers (high water mark)
  - Total unique users seen
  - Top 10 most active chatters

- **Interactive Graphs**
  - User activity over time (chat users vs. connected viewers)
  - Time range selection (1 hour, 6 hours, 24 hours, 7 days)
  - Auto-refreshing every 30 seconds

- **Historical Data**
  - User counts logged every 5 minutes
  - Stored in SQLite database
  - Automatic cleanup of data older than 30 days

## Requirements

Install Flask:
```bash
pip install Flask>=3.0.0
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

## Quick Start

1. **Make sure your bot is running** and logging to the database

2. **Start the web server:**
   ```bash
   python web/status_server.py
   ```

3. **Open your browser** to:
   ```
   http://127.0.0.1:5000
   ```

## Command Line Options

```bash
python web/status_server.py [OPTIONS]
```

### Options:

- `--host HOST` - Host to bind to (default: `127.0.0.1`)
  ```bash
  python web/status_server.py --host 0.0.0.0  # Allow external access
  ```

- `--port PORT` - Port to bind to (default: `5000`)
  ```bash
  python web/status_server.py --port 8080
  ```

- `--db PATH` - Path to database file (default: `bot_data.db`)
  ```bash
  python web/status_server.py --db /path/to/custom_db.db
  ```

- `--debug` - Enable debug mode
  ```bash
  python web/status_server.py --debug
  ```

### Example: Public Server

To make the status page accessible from other machines:
```bash
python web/status_server.py --host 0.0.0.0 --port 8080
```

Then access from other devices at: `http://YOUR_IP:8080`

## API Endpoints

The server provides JSON API endpoints for integration:

### Get Current Statistics
```
GET /api/stats
```

Returns:
```json
{
  "high_water_marks": {
    "chat": {
      "count": 35,
      "timestamp": 1731088200
    },
    "connected": {
      "count": 42,
      "timestamp": 1731091800
    }
  },
  "total_users_seen": 156,
  "top_chatters": [
    {"username": "Alice", "messages": 1234},
    {"username": "Bob", "messages": 892}
  ]
}
```

### Get Historical Data
```
GET /api/history/<hours>
```

Parameters:
- `hours` - Number of hours of history (max 168 for 7 days)

Example: `/api/history/24`

Returns:
```json
{
  "hours": 24,
  "data": [
    {
      "timestamp": 1731070800,
      "chat_users": 12,
      "connected_users": 25
    },
    ...
  ]
}
```

### Get User Statistics
```
GET /api/user/<username>
```

Example: `/api/user/Alice`

Returns:
```json
{
  "username": "Alice",
  "first_seen": 1730980800,
  "last_seen": 1731091800,
  "total_chat_lines": 1234,
  "total_time_connected": 86400,
  "current_session_start": null
}
```

## Database Maintenance

The bot automatically logs user counts every 5 minutes. To manage historical data:

### Manual Cleanup

You can manually clean up old history data using Python:

```python
from common.database import BotDatabase

db = BotDatabase('bot_data.db')
deleted = db.cleanup_old_history(days=30)  # Keep last 30 days
print(f'Deleted {deleted} old records')
db.close()
```

### Data Size

User count history is very compact:
- ~288 records per day (every 5 minutes)
- ~8,640 records per month
- Each record is < 100 bytes

30 days of history = ~260KB of storage

## Troubleshooting

### "Database not initialized" error

Make sure the database file exists and contains data:
```bash
# Check if file exists
ls -l bot_data.db

# Verify with correct path
python web/status_server.py --db path/to/bot_data.db
```

### No historical data showing

The bot needs to run for at least 5 minutes to start logging data. If you just started:
1. Wait 5 minutes for the first data point
2. Refresh the web page
3. Historical graph will populate over time

### Port already in use

If port 5000 is already taken:
```bash
python web/status_server.py --port 5001
```

### External access not working

If running with `--host 0.0.0.0` but can't access externally:
1. Check firewall settings
2. Verify the port is open
3. Use your machine's IP address (not 127.0.0.1)

## Security Considerations

⚠️ **Important**: The status page has no authentication!

- By default, it only binds to `127.0.0.1` (localhost only)
- Only use `--host 0.0.0.0` on trusted networks
- Consider using a reverse proxy (nginx, Apache) with authentication for production
- The database is read-only from the web server (no data can be modified)

## Integration Examples

### Embed Graph in Another Page

```html
<iframe 
    src="http://127.0.0.1:5000" 
    width="100%" 
    height="800px"
    frameborder="0">
</iframe>
```

### Fetch Stats with JavaScript

```javascript
fetch('http://127.0.0.1:5000/api/stats')
    .then(response => response.json())
    .then(data => {
        console.log('Peak users:', data.high_water_marks.chat.count);
        console.log('Total seen:', data.total_users_seen);
    });
```

### Monitor with curl

```bash
# Pretty-print JSON stats
curl http://127.0.0.1:5000/api/stats | python -m json.tool
```

## Advanced: Running as a Service

### Using systemd (Linux)

Create `/etc/systemd/system/cytube-status.service`:

```ini
[Unit]
Description=CyTube Bot Status Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/cytube-bot
ExecStart=/usr/bin/python3 web/status_server.py --host 0.0.0.0 --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable cytube-status
sudo systemctl start cytube-status
```

### Using screen (Simple Background)

```bash
screen -S status
python web/status_server.py
# Press Ctrl+A, then D to detach

# Reattach later with:
screen -r status
```

## Tips

1. **Refresh Rate**: The page auto-refreshes every 30 seconds. You can also manually refresh your browser.

2. **Time Zones**: All timestamps are displayed in your local time zone.

3. **Graph Performance**: The 7-day view shows more data points. For best performance, use 1h or 24h views.

4. **Mobile Friendly**: The interface is responsive and works well on mobile devices.

5. **Browser Compatibility**: Works with all modern browsers (Chrome, Firefox, Safari, Edge).

## See Also

- [PM_GUIDE.md](../docs/guides/PM_GUIDE.md) - Using the bot via private messages
- [SHELL_COMMANDS.md](../SHELL_COMMANDS.md) - Command-line interface reference
- [README.md](../README.md) - Main documentation
