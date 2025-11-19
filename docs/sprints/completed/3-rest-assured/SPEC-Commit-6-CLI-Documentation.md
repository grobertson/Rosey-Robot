# SPEC: Command-Line Tool and Documentation

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 6 - CLI Tool & Docs  
**Dependencies:** All previous commits  
**Estimated Effort:** Medium

---

## Objective

Create a command-line utility for easy API access, generate comprehensive documentation (Postman collection, cURL examples, markdown reference), and update project documentation.

---

## Changes Required

### 1. Command-Line Tool

**File:** `tools/rosey_cli.py` (new)

```python
#!/usr/bin/env python3
"""
Rosey CLI - Command-line tool for Rosey Bot API.

Usage:
    rosey-cli send "Hello everyone!"
    rosey-cli announce "Server reboot scheduled"
    rosey-cli status
    rosey-cli playlist list
    rosey-cli playlist add "https://youtube.com/watch?v=..."
    rosey-cli playlist bulk playlist.txt
    rosey-cli playlist clear --confirm
"""
import os
import sys
import argparse
import json
from typing import Optional
import httpx


DEFAULT_API_URL = "http://localhost:8080/api/v1"
API_KEY_ENV = "ROSEY_API_KEY"
API_KEY_FILE = os.path.expanduser("~/.rosey-api-key")


def get_api_key() -> Optional[str]:
    """Get API key from environment or file."""
    # Try environment variable first
    key = os.environ.get(API_KEY_ENV)
    if key:
        return key.strip()
    
    # Try key file
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    
    return None


def get_api_url() -> str:
    """Get API base URL from environment or use default."""
    return os.environ.get("ROSEY_API_URL", DEFAULT_API_URL)


def make_request(method: str, path: str, data: dict = None) -> dict:
    """Make API request."""
    api_key = get_api_key()
    if not api_key:
        print("Error: API key not found.", file=sys.stderr)
        print(f"Set {API_KEY_ENV} environment variable or create {API_KEY_FILE}", file=sys.stderr)
        print("Get your API key via PM: !apikey", file=sys.stderr)
        sys.exit(1)
    
    api_url = get_api_url()
    url = f"{api_url}{path}"
    headers = {"X-API-Key": api_key}
    
    try:
        if method == "GET":
            response = httpx.get(url, headers=headers, timeout=30.0)
        elif method == "POST":
            response = httpx.post(url, headers=headers, json=data, timeout=30.0)
        elif method == "DELETE":
            response = httpx.delete(url, headers=headers, timeout=30.0)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code}", file=sys.stderr)
        try:
            error_data = e.response.json()
            print(f"  {error_data.get('error', 'Unknown error')}", file=sys.stderr)
        except:
            print(f"  {e.response.text}", file=sys.stderr)
        sys.exit(1)
    
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to API server", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print(f"  URL: {api_url}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Command Handlers
# ============================================================================

def cmd_send(args):
    """Send chat message."""
    result = make_request("POST", "/chat/send", {"message": args.message})
    print(f"✓ Message sent at {result['timestamp']}")


def cmd_announce(args):
    """Send system announcement."""
    result = make_request("POST", "/system/announce", {
        "message": args.message
    })
    print(f"✓ Announcement sent at {result['timestamp']}")


def cmd_status(args):
    """Get bot status."""
    result = make_request("GET", "/status")
    print(f"Status: {'Connected' if result['connected'] else 'Disconnected'}")
    print(f"Uptime: {result['uptime_seconds']} seconds")
    print(f"API Version: {result['api_version']}")


def cmd_playlist_list(args):
    """List playlist items."""
    result = make_request("GET", "/playlist")
    
    if result['total'] == 0:
        print("Playlist is empty")
        return
    
    print(f"Playlist ({result['total']} items):")
    for item in result['items']:
        duration_min = item['duration'] // 60
        duration_sec = item['duration'] % 60
        print(f"  [{item['position']}] {item['title']}")
        print(f"      {duration_min}:{duration_sec:02d} | by {item['user']} | ID: {item['id']}")


def cmd_playlist_add(args):
    """Add single media to playlist."""
    result = make_request("POST", "/playlist/add", {
        "url": args.url,
        "position": args.position
    })
    
    media = result['media']
    print(f"✓ Added: {media['title']}")
    print(f"  Duration: {media['duration']}s")


def cmd_playlist_bulk(args):
    """Bulk add media from file."""
    # Read URLs from file
    try:
        with open(args.file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    if not urls:
        print("Error: No URLs found in file", file=sys.stderr)
        sys.exit(1)
    
    print(f"Adding {len(urls)} items to playlist...")
    print("This may take several minutes. Progress will be shown below.\n")
    
    # Note: For real-time progress, the CLI could add items one-by-one
    # instead of using bulk endpoint. Trade-off: simplicity vs granular feedback
    # For now, using bulk endpoint with summary at end.
    
    # Prepare request
    items = [{"url": url, "position": "end"} for url in urls]
    result = make_request("POST", "/playlist/bulk-add", {"items": items})
    
    print(f"\n✓ Successfully added: {result['added']}")
    if result['failed'] > 0:
        print(f"✗ Failed: {result['failed']}")
        if args.verbose:
            print("\nFailed items:")
            for error in result['errors']:
                print(f"  - {error['url']}: {error['reason']}")


def cmd_playlist_remove(args):
    """Remove media from playlist."""
    result = make_request("DELETE", f"/playlist/{args.media_id}")
    print(f"✓ Removed media ID: {args.media_id}")


def cmd_playlist_clear(args):
    """Clear entire playlist."""
    if not args.confirm:
        print("Error: This will remove ALL items from the playlist!", file=sys.stderr)
        print("Add --confirm to proceed", file=sys.stderr)
        sys.exit(1)
    
    result = make_request("DELETE", "/playlist?confirm=true")
    print(f"✓ Cleared playlist ({result['removed']} items removed)")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Rosey Bot CLI - Control your CyTube bot from the command line",
        epilog="Get your API key via PM: !apikey"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # send command
    send_parser = subparsers.add_parser('send', help='Send chat message')
    send_parser.add_argument('message', help='Message text')
    send_parser.set_defaults(func=cmd_send)
    
    # announce command
    announce_parser = subparsers.add_parser('announce', help='Send system announcement')
    announce_parser.add_argument('message', help='Announcement text')
    announce_parser.set_defaults(func=cmd_announce)
    
    # status command
    status_parser = subparsers.add_parser('status', help='Get bot status')
    status_parser.set_defaults(func=cmd_status)
    
    # playlist commands
    playlist_parser = subparsers.add_parser('playlist', help='Playlist management')
    playlist_sub = playlist_parser.add_subparsers(dest='playlist_cmd', help='Playlist command')
    
    # playlist list
    playlist_list = playlist_sub.add_parser('list', help='List playlist items')
    playlist_list.set_defaults(func=cmd_playlist_list)
    
    # playlist add
    playlist_add = playlist_sub.add_parser('add', help='Add single media')
    playlist_add.add_argument('url', help='Media URL')
    playlist_add.add_argument('--position', default='end', help='Position (end, next, or index)')
    playlist_add.set_defaults(func=cmd_playlist_add)
    
    # playlist bulk
    playlist_bulk = playlist_sub.add_parser('bulk', help='Bulk add from file')
    playlist_bulk.add_argument('file', help='File with URLs (one per line)')
    playlist_bulk.add_argument('--verbose', '-v', action='store_true',
                               help='Show detailed error information')
    playlist_bulk.set_defaults(func=cmd_playlist_bulk)
    
    # playlist remove
    playlist_remove = playlist_sub.add_parser('remove', help='Remove media by ID')
    playlist_remove.add_argument('media_id', help='Media ID to remove')
    playlist_remove.set_defaults(func=cmd_playlist_remove)
    
    # playlist clear
    playlist_clear = playlist_sub.add_parser('clear', help='Clear entire playlist')
    playlist_clear.add_argument('--confirm', action='store_true',
                                help='Confirm playlist clear')
    playlist_clear.set_defaults(func=cmd_playlist_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'playlist' and not args.playlist_cmd:
        playlist_parser.print_help()
        sys.exit(1)
    
    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()
```

Make it executable:

```bash
chmod +x tools/rosey_cli.py
```

Create symlink for easy access (optional):

```bash
ln -s tools/rosey_cli.py /usr/local/bin/rosey-cli
```

### 2. Postman Collection

**File:** `docs/3-rest-assured/Rosey-API.postman_collection.json` (new)

```json
{
  "info": {
    "name": "Rosey Bot API",
    "description": "Complete API collection for Rosey CyTube bot",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "auth": {
    "type": "apikey",
    "apikey": [
      {
        "key": "value",
        "value": "{{api_key}}",
        "type": "string"
      },
      {
        "key": "key",
        "value": "X-API-Key",
        "type": "string"
      }
    ]
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8080/api/v1",
      "type": "string"
    },
    {
      "key": "api_key",
      "value": "your-api-key-here",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "Status",
      "item": [
        {
          "name": "Get Bot Status",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/status",
              "host": ["{{base_url}}"],
              "path": ["status"]
            }
          }
        },
        {
          "name": "Health Check",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "http://localhost:8080/health",
              "protocol": "http",
              "host": ["localhost"],
              "port": "8080",
              "path": ["health"]
            }
          }
        }
      ]
    },
    {
      "name": "Chat",
      "item": [
        {
          "name": "Send Message",
          "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"message\": \"Hello from Postman!\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/chat/send",
              "host": ["{{base_url}}"],
              "path": ["chat", "send"]
            }
          }
        }
      ]
    },
    {
      "name": "System",
      "item": [
        {
          "name": "Send Announcement",
          "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"message\": \"Bot updated successfully\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/system/announce",
              "host": ["{{base_url}}"],
              "path": ["system", "announce"]
            }
          }
        }
      ]
    },
    {
      "name": "Playlist",
      "item": [
        {
          "name": "Get Playlist",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/playlist",
              "host": ["{{base_url}}"],
              "path": ["playlist"]
            }
          }
        },
        {
          "name": "Add Media",
          "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"url\": \"https://youtube.com/watch?v=dQw4w9WgXcQ\",\n  \"position\": \"end\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/playlist/add",
              "host": ["{{base_url}}"],
              "path": ["playlist", "add"]
            }
          }
        },
        {
          "name": "Bulk Add Media",
          "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"items\": [\n    {\"url\": \"https://youtube.com/watch?v=dQw4w9WgXcQ\"},\n    {\"url\": \"https://youtube.com/watch?v=9bZkp7q19f0\"},\n    {\"url\": \"https://youtube.com/watch?v=kJQP7kiw5Fk\"}\n  ]\n}"
            },
            "url": {
              "raw": "{{base_url}}/playlist/bulk-add",
              "host": ["{{base_url}}"],
              "path": ["playlist", "bulk-add"]
            }
          }
        },
        {
          "name": "Remove Media",
          "request": {
            "method": "DELETE",
            "header": [],
            "url": {
              "raw": "{{base_url}}/playlist/:media_id",
              "host": ["{{base_url}}"],
              "path": ["playlist", ":media_id"],
              "variable": [{"key": "media_id", "value": "abc123"}]
            }
          }
        },
        {
          "name": "Clear Playlist",
          "request": {
            "method": "DELETE",
            "header": [],
            "url": {
              "raw": "{{base_url}}/playlist?confirm=true",
              "host": ["{{base_url}}"],
              "path": ["playlist"],
              "query": [{"key": "confirm", "value": "true"}]
            }
          }
        }
      ]
    }
  ]
}
```

### 3. cURL Examples Document

**File:** `docs/API_EXAMPLES.md` (new)

```markdown
# Rosey Bot API - cURL Examples

Quick reference for using the Rosey Bot API with cURL.

## Setup

Export your API key once:

```bash
export API_KEY="your-api-key-here"
```

Or set it permanently in your shell config (~/.bashrc, ~/.zshrc):

```bash
echo 'export ROSEY_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

## Status

### Get Bot Status

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/status
```

### Health Check (No Auth)

```bash
curl http://localhost:8080/health
```

## Chat

### Send Message

```bash
curl -X POST http://localhost:8080/api/v1/chat/send \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello everyone!"}'
```

## System Announcements

### Send Announcement

```bash
curl -X POST http://localhost:8080/api/v1/system/announce \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Bot updated successfully"}'
```

## Playlist Management

### Get Playlist

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/playlist
```

Pretty print with jq:

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/playlist | jq
```

### Add Single Video

```bash
curl -X POST http://localhost:8080/api/v1/playlist/add \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "position": "end"}'
```

### Bulk Add Videos

```bash
curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
      {"url": "https://youtube.com/watch?v=9bZkp7q19f0"},
      {"url": "https://youtube.com/watch?v=kJQP7kiw5Fk"}
    ]
  }'
```

### Bulk Add from File

Create `playlist.txt` with one URL per line, then:

```bash
jq -R -s 'split("\n") | map(select(length > 0)) | map({url: ., position: "end"}) | {items: .}' \
  playlist.txt | \
curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @-
```

### Remove Media

```bash
# Get media ID from playlist first
MEDIA_ID="abc123"

curl -X DELETE \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8080/api/v1/playlist/$MEDIA_ID"
```

### Clear Playlist

```bash
curl -X DELETE \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8080/api/v1/playlist?confirm=true"
```

## Error Handling

Check HTTP status code:

```bash
curl -w "\nHTTP Status: %{http_code}\n" \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/status
```

Full response with headers:

```bash
curl -i \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/status
```

## Advanced Usage

### Save Response to File

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/playlist \
  -o playlist_backup.json
```

### Timing

```bash
curl -w "\nTime: %{time_total}s\n" \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/status
```

### Follow Redirects

```bash
curl -L \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8080/api/v1/status
```

## Troubleshooting

### 401 Unauthorized

- Check API key is correct
- Verify key hasn't been revoked
- Ensure X-API-Key header is set

### 503 Service Unavailable

- Bot is not connected to CyTube
- Check bot status
- Restart bot if needed

### Connection Refused

- API server not running
- Wrong host/port
- Firewall blocking connection
```

### 4. README Updates

**File:** `README.md` (update)

Add new section after LLM Integration:

```markdown
## 🌐 REST API

Rosey provides a comprehensive REST API for programmatic bot control.

### Quick Start

1. **Get API Key via PM:**
   ```
   You: !apikey
   Bot: Your API key: abc123def456...
   ```

2. **Use the API:**
   ```bash
   curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/status
   ```

3. **Or use the CLI tool:**
   ```bash
   rosey-cli send "Hello everyone!"
   rosey-cli playlist bulk playlist.txt
   ```

### Features

- **Chat & Announcements:** Send messages and system notifications
- **Playlist Management:** Add, remove, bulk load media
- **Status Monitoring:** Check bot connection and uptime
- **API Key Management:** Self-service via PM commands
- **Auto-Documentation:** Swagger UI at `/docs`

### Documentation

- **Interactive Docs:** http://localhost:8080/docs
- **API Examples:** [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md)
- **Postman Collection:** [docs/3-rest-assured/Rosey-API.postman_collection.json](docs/3-rest-assured/Rosey-API.postman_collection.json)
- **CLI Tool:** `tools/rosey_cli.py`

### CLI Tool

```bash
# Install httpx dependency
pip install httpx

# Set up API key
export ROSEY_API_KEY="your-key"
# or
echo "your-key" > ~/.rosey-api-key

# Use the CLI
rosey-cli status
rosey-cli send "Hello!"
rosey-cli playlist add "https://youtube.com/watch?v=..."
rosey-cli playlist bulk playlist.txt
```

See [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md) for more examples.
```

Update "Future Development" to remove "REST API" if listed as planned.

### 5. Update Dependencies

**File:** `requirements.txt` (update)

Ensure httpx is listed for CLI tool:

```
httpx>=0.25.0  # For CLI tool
```

---

## Success Criteria

- ✅ CLI tool works for all commands
- ✅ API key loaded from environment or file
- ✅ Postman collection can be imported and used
- ✅ cURL examples document is complete and accurate
- ✅ README updated with REST API section
- ✅ All documentation references correct URLs
- ✅ CLI tool provides helpful error messages
- ✅ CLI tool returns appropriate exit codes

---

## Testing Checklist

### CLI Tool Tests

```bash
# Set up
export ROSEY_API_KEY="your-key"

# Test all commands
python tools/rosey_cli.py status
python tools/rosey_cli.py send "Test message"
python tools/rosey_cli.py announce "Test announcement" --priority high
python tools/rosey_cli.py playlist list
python tools/rosey_cli.py playlist add "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Create test file
echo "https://youtube.com/watch?v=dQw4w9WgXcQ" > test_playlist.txt
echo "https://youtube.com/watch?v=9bZkp7q19f0" >> test_playlist.txt

python tools/rosey_cli.py playlist bulk test_playlist.txt --verbose

# Test error handling
unset ROSEY_API_KEY
python tools/rosey_cli.py status  # Should show error about missing key
```

### Postman Collection Test

1. Import `Rosey-API.postman_collection.json` into Postman
2. Set `api_key` variable to your actual key
3. Test each request in collection
4. Verify all requests work

### Documentation Review

1. Open http://localhost:8080/docs in browser
2. Verify all endpoints documented
3. Test example requests from Swagger UI
4. Review API_EXAMPLES.md and test each curl command
5. Verify README links work

---

## Rollback Plan

- CLI tool is optional, can be removed without affecting API
- Documentation updates can be reverted
- API server continues to function without CLI
- Postman collection is for convenience only
