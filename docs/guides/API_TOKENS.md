# API Token Authentication

## Overview

The bot's web interface now uses token-based authentication to secure the `/api/say` endpoint, which allows external applications to send messages through the bot. This ensures that only authorized users and applications can post messages.

## Quick Start

### For Web UI Users

1. Open the bot's web status page (default: http://127.0.0.1:5000/)
2. Click the **🔑 Token** button in the Recent Chat section
3. Click **Generate Token** and give it a description (e.g., "My Laptop")
4. Click **Copy to Clipboard** or manually save the token somewhere secure
5. Click **Save this token as your current token?** → Yes
6. You can now use the send box to send messages as the bot!

### For External Applications

If you're building an app that integrates with the bot:

```python
import requests

# Your API token (get this from the web UI)
API_TOKEN = "your-token-here"

# Send a message
response = requests.post(
    'http://127.0.0.1:5000/api/say',
    headers={'X-API-Token': API_TOKEN},
    json={'message': 'Hello from my app!'}
)

if response.json().get('queued'):
    print(f"Message queued! ID: {response.json()['id']}")
else:
    print(f"Error: {response.json().get('error')}")
```

## Token Management

### Generating Tokens

**Via Web UI:**
1. Click **🔑 Token** button
2. Enter a description (helps you remember what it's for)
3. Click **Generate Token**
4. **Save the token immediately** - it's only shown once!

**Via API:**
```bash
curl -X POST http://127.0.0.1:5000/api/tokens \
  -H "Content-Type: application/json" \
  -d '{"description": "My Python script"}'
```

### Listing Active Tokens

```bash
curl http://127.0.0.1:5000/api/tokens
```

Returns:
```json
{
  "tokens": [
    {
      "token_preview": "AbC12345...",
      "description": "My laptop",
      "created_at": 1699564800,
      "last_used": 1699651200,
      "revoked": 0
    }
  ]
}
```

### Revoking Tokens

If a token is compromised or no longer needed:

**Via API:**
```bash
# Use first 8+ characters of the token
curl -X DELETE http://127.0.0.1:5000/api/tokens/AbC12345
```

**Note:** Revoked tokens are kept in the database for 90 days for audit purposes, then automatically cleaned up.

## Security Best Practices

### Do's ✅
- **Generate separate tokens** for each application/device
- **Use descriptive names** so you know what each token is for
- **Revoke tokens immediately** if you suspect they're compromised
- **Keep tokens secure** - treat them like passwords
- **Use HTTPS** if the web server is exposed to the internet

### Don'ts ❌
- **Never share tokens** publicly (GitHub, Discord, etc.)
- **Don't reuse tokens** across multiple apps
- **Don't embed tokens** in client-side JavaScript
- **Don't commit tokens** to version control

## Message Queue & Retry Logic

When you send a message via `/api/say`:

1. **Queued**: Message is stored in the database
2. **Processing**: Bot attempts to send (every ~2 seconds)
3. **Sent**: Message successfully delivered to chat
4. **Retrying**: Transient error occurred (network issue, etc.)
5. **Failed**: Permanent error (permissions, muted, etc.)
6. **Abandoned**: Exceeded max retries (3 attempts)

### Retry Behavior

- **Permanent errors** (permissions, muted, flood control):
  - Message marked as failed immediately
  - No retries attempted
  
- **Transient errors** (network timeouts, temporary issues):
  - Exponential backoff: 2min, 4min, 8min
  - Max 3 retry attempts
  - After 3 failures, message is abandoned

### Checking Message Status

The web UI shows recent outbound messages in the "Outbound Message Status" section (click to expand). Each message displays:
- ✓ Sent - Successfully delivered
- ⏱ Queued - Waiting to be sent
- 🔄 Retry N - Failed, will retry
- ✗ Failed - Permanent error
- ⚠ Abandoned - Exceeded max retries

## API Reference

### POST /api/say

Queue a message to be sent by the bot.

**Headers:**
- `X-API-Token`: Your API token (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "message": "Text to send"
}
```

**Response (Success):**
```json
{
  "queued": true,
  "id": 123
}
```

**Response (Error):**
```json
{
  "error": "Unauthorized - invalid or missing API token"
}
```

**HTTP Status Codes:**
- `200` - Message queued successfully
- `400` - Missing or empty message
- `401` - Invalid or missing token
- `500` - Server error

### GET /api/outbound/recent

Get recent outbound message status.

**Query Parameters:**
- `limit` (optional): Number of messages to return (default 20, max 100)

**Response:**
```json
{
  "messages": [
    {
      "id": 123,
      "timestamp": 1699564800,
      "message": "Hello!",
      "message_preview": "Hello!",
      "sent": 1,
      "sent_timestamp": 1699564802,
      "retry_count": 0,
      "last_error": null,
      "status": "sent"
    }
  ]
}
```

### POST /api/tokens

Generate a new API token.

**Request Body:**
```json
{
  "description": "Optional description"
}
```

**Response:**
```json
{
  "token": "full-token-string-here",
  "description": "Optional description",
  "created_at": 1699564800
}
```

**Warning:** The full token is only returned once. Store it securely!

### GET /api/tokens

List all active (non-revoked) tokens.

**Response:**
```json
{
  "tokens": [
    {
      "token_preview": "AbC12345...",
      "description": "My app",
      "created_at": 1699564800,
      "last_used": 1699651200,
      "revoked": 0
    }
  ]
}
```

### DELETE /api/tokens/{token_prefix}

Revoke a token by its prefix (first 8+ characters).

**Response (Success):**
```json
{
  "revoked": 1
}
```

**Response (Not Found):**
```json
{
  "error": "Token not found"
}
```

## Database Maintenance

The bot automatically performs maintenance daily:
- Cleans up old user count history (>30 days)
- Removes old outbound messages (>7 days after sending)
- Deletes old revoked tokens (>90 days)
- Runs VACUUM to reclaim disk space
- Updates query planner statistics

First maintenance runs at bot startup, then every 24 hours.

## Troubleshooting

### "Unauthorized" Error

**Cause:** Invalid or missing token

**Solutions:**
1. Make sure you saved the token correctly
2. Generate a new token if you lost the original
3. Check that you're using `X-API-Token` header (not `Authorization`)

### Messages Stuck in "Queued"

**Cause:** Bot is not connected or database issue

**Solutions:**
1. Check bot is running and connected to the channel
2. Check bot logs for errors
3. Verify database file permissions

### "Failed" or "Abandoned" Messages

**Cause:** Bot lacks permissions or is muted

**Solutions:**
1. Check bot has chat permissions in the channel
2. Verify bot is not muted or shadowmuted
3. Check message doesn't violate chat rules (spam filter, etc.)

### Token Not Working After Creation

**Cause:** Browser hasn't saved the token

**Solutions:**
1. Click "Set Token" and paste it manually
2. Check browser's localStorage isn't disabled
3. Try a different browser

## Examples

### Python Script

```python
#!/usr/bin/env python3
import requests
import time

API_TOKEN = "your-token-here"
API_URL = "http://127.0.0.1:5000/api/say"

def send_message(text):
    """Send a message via the bot"""
    response = requests.post(
        API_URL,
        headers={'X-API-Token': API_TOKEN},
        json={'message': text}
    )
    return response.json()

# Send a message
result = send_message("Hello from Python!")
if result.get('queued'):
    print(f"✓ Message queued (ID: {result['id']})")
else:
    print(f"✗ Error: {result.get('error')}")
```

### JavaScript (Node.js)

```javascript
const fetch = require('node-fetch');

const API_TOKEN = 'your-token-here';
const API_URL = 'http://127.0.0.1:5000/api/say';

async function sendMessage(text) {
    const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Token': API_TOKEN
        },
        body: JSON.stringify({ message: text })
    });
    return await response.json();
}

// Send a message
sendMessage('Hello from Node.js!')
    .then(result => {
        if (result.queued) {
            console.log(`✓ Message queued (ID: ${result.id})`);
        } else {
            console.log(`✗ Error: ${result.error}`);
        }
    });
```

### Bash Script

```bash
#!/bin/bash

API_TOKEN="your-token-here"
API_URL="http://127.0.0.1:5000/api/say"

send_message() {
    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -H "X-API-Token: $API_TOKEN" \
        -d "{\"message\": \"$1\"}"
}

# Send a message
send_message "Hello from Bash!"
```

## Support

For issues or questions:
1. Check bot logs for error messages
2. Verify token is valid and not revoked
3. Test with the web UI first before troubleshooting external apps
4. Check this documentation for common issues

Happy botting! 🤖
