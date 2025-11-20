# SPEC: Chat and System Announcement Endpoints

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 4 - Chat Endpoints  
**Dependencies:** Commit 3 (FastAPI Foundation)  
**Estimated Effort:** Small

---

## Objective

Implement API endpoints for sending chat messages and system announcements. This enables programmatic communication with the CyTube channel.

---

## Changes Required

### 1. Bot Integration Module

**File:** `web/bot_interface.py` (new)

```python
"""
Interface between API server and bot.
Provides methods for API to interact with bot functionality.
"""
import asyncio
from typing import Optional
from datetime import datetime


class BotInterface:
    """
    Interface for API to communicate with bot.
    Uses shared state or message queue to send commands to bot.
    """
    
    def __init__(self):
        self.bot = None  # Will be set by bot when it starts
        self._message_queue = asyncio.Queue()
    
    def set_bot(self, bot):
        """Set reference to bot instance."""
        self.bot = bot
    
    async def send_message(self, message: str) -> bool:
        """
        Send chat message to channel.
        
        Args:
            message: Message text to send
            
        Returns:
            True if message queued successfully
        """
        if not self.bot or not self.bot.connected:
            return False
        
        try:
            await self.bot.send_chat_message(message)
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    async def send_announcement(self, message: str) -> bool:
        """
        Send system announcement to channel.
        
        Args:
            message: Announcement text
            
        Returns:
            True if announcement sent successfully
        """
        if not self.bot or not self.bot.connected:
            return False
        
        try:
            # Format announcement with info icon
            formatted = f"ℹ️ {message}"
            
            await self.bot.send_chat_message(formatted)
            return True
        except Exception as e:
            print(f"Error sending announcement: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if bot is connected to CyTube."""
        return self.bot is not None and self.bot.connected
    
    def get_uptime(self) -> Optional[int]:
        """Get bot uptime in seconds."""
        if not self.bot or not hasattr(self.bot, 'start_time'):
            return None
        
        if not self.bot.start_time:
            return 0
        
        uptime = datetime.utcnow() - self.bot.start_time
        return int(uptime.total_seconds())


# Global bot interface instance
bot_interface = BotInterface()
```

### 2. API Endpoints for Chat

**File:** `web/api_server.py` (update)

Add these models and endpoints:

```python
# Add to Pydantic models section

class SendMessageRequest(BaseModel):
    """Request to send chat message."""
    message: str = Field(
        ...,
        description="Message text to send to channel",
        min_length=1,
        max_length=500,
        example="Hello from the API!"
    )


class SendMessageResponse(BaseModel):
    """Response from send message endpoint."""
    success: bool = Field(..., description="Whether message was sent")
    timestamp: str = Field(..., description="Message timestamp (ISO 8601)")


class SystemAnnouncementRequest(BaseModel):
    """Request to send system announcement."""
    message: str = Field(
        ...,
        description="Announcement text",
        min_length=1,
        max_length=500,
        example="Server reboot in 5 minutes"
    )


class SystemAnnouncementResponse(BaseModel):
    """Response from system announcement endpoint."""
    success: bool = Field(..., description="Whether announcement was sent")
    timestamp: str = Field(..., description="Announcement timestamp (ISO 8601)")


# Add to imports at top
from web.bot_interface import bot_interface

# Add endpoints after status endpoint

@app.post(
    "/api/v1/chat/send",
    response_model=SendMessageResponse,
    summary="Send chat message",
    description="Send a message to the CyTube channel as the bot.",
    responses={
        200: {"description": "Message sent successfully"},
        401: {"description": "Invalid or missing API key"},
        503: {"description": "Bot is not connected to channel"}
    },
    tags=["Chat"]
)
async def send_chat_message(
    request: SendMessageRequest,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Send chat message to channel."""
    username = await verify_auth(x_api_key)
    
    # Check if bot is connected
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel. Please try again later."
        )
    
    # Send message
    success = await bot_interface.send_message(request.message)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Check bot logs for details."
        )
    
    return SendMessageResponse(
        success=True,
        timestamp=datetime.utcnow().isoformat()
    )


@app.post(
    "/api/v1/system/announce",
    response_model=SystemAnnouncementResponse,
    summary="Send system announcement",
    description="Send a formatted system announcement to the channel.",
    responses={
        200: {"description": "Announcement sent successfully"},
        401: {"description": "Invalid or missing API key"},
        503: {"description": "Bot is not connected to channel"}
    },
    tags=["System"]
)
async def send_system_announcement(
    request: SystemAnnouncementRequest,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Send system announcement to channel."""
    username = await verify_auth(x_api_key)
    
    # Check if bot is connected
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel. Please try again later."
        )
    
    # Send announcement
    success = await bot_interface.send_announcement(request.message)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send announcement. Check bot logs for details."
        )
    
    return SystemAnnouncementResponse(
        success=True,
        timestamp=datetime.utcnow().isoformat()
    )


# Update status endpoint to use bot_interface

@app.get(
    "/api/v1/status",
    response_model=StatusResponse,
    summary="Get bot status",
    description="Returns current bot status including connection state and uptime.",
    tags=["Status"]
)
async def get_status(
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Get current bot status."""
    username = await verify_auth(x_api_key)
    
    return StatusResponse(
        connected=bot_interface.is_connected(),
        uptime_seconds=bot_interface.get_uptime() or 0,
        api_version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )
```

### 3. Bot Integration

**File:** `bot/rosey/rosey.py` (update)

Connect bot to API interface:

```python
# Add to imports
from web.bot_interface import bot_interface

# In bot initialization (e.g., in main() or Bot.__init__)
def main():
    """Run the bot."""
    bot = RoseyBot()
    
    # Register bot with API interface
    bot_interface.set_bot(bot)
    
    # Run bot
    bot.run()
```

Also add these methods to the bot class if they don't exist:

```python
async def send_chat_message(self, message: str):
    """
    Send chat message to channel.
    
    Args:
        message: Message text to send
    """
    if self.connected:
        await self.channel.send_chat(message)


@property
def connected(self) -> bool:
    """Check if bot is connected to channel."""
    return self.channel and self.channel.connected
```

---

## Testing Checklist

### Manual Tests

1. **Send Simple Message**
   ```bash
   curl -X POST http://localhost:8080/api/v1/chat/send \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello from the API!"}'
   
   # Expected: 200 OK
   # {"success": true, "timestamp": "2025-11-10T..."}
   # Message should appear in channel
   ```

2. **Send System Announcement**

   ```bash
   curl -X POST http://localhost:8080/api/v1/system/announce \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"message": "Bot update complete"}'
   
   # Expected: 200 OK
   # Message in channel: "ℹ️ Bot update complete"
   ```

3. **Bot Disconnected**
3. **Bot Disconnected**
   ```bash
   # Stop bot, keep API running
   curl -X POST http://localhost:8080/api/v1/chat/send \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"message": "This will fail"}'
   
   # Expected: 503 Service Unavailable
   # {"error": "Bot is not connected to channel..."}
   ```

4. **Message Too Long**
   ```bash
   curl -X POST http://localhost:8080/api/v1/chat/send \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"message": "'"$(python -c 'print("x" * 501)')"'"}'
   
   # Expected: 422 Unprocessable Entity
   # Pydantic validation error for max_length
   ```

5. **Status Check**
   ```bash
   curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/status
   
   # Expected: 200 OK
   # {"connected": true, "uptime_seconds": 1234, ...}
   ```

### Swagger UI Testing

1. Open http://localhost:8080/docs
2. Authorize with API key
3. Test `/api/v1/chat/send`:
   - Try it out with simple message
   - Verify message appears in channel
4. Test `/api/v1/system/announce`:
   - Try sending announcement
   - Verify formatting in channel (ℹ️ prefix)
   - Verify formatting in channel
5. Test `/api/v1/status`:
   - Verify connected=true when bot running
   - Verify uptime increases over time

---

## Success Criteria

- ✅ `/api/v1/chat/send` endpoint sends messages to channel
- ✅ `/api/v1/system/announce` endpoint sends formatted announcements
- ✅ Announcements prefixed with "ℹ️"
- ✅ Returns 503 when bot is disconnected
- ✅ Message length validation (1-500 characters)
- ✅ Status endpoint shows actual bot connection state
- ✅ Status endpoint shows actual bot uptime
- ✅ All endpoints require authentication
- ✅ All requests logged to audit trail
- ✅ OpenAPI documentation generated automatically

---

## Usage Examples

### Python Example

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "http://localhost:8080/api/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Send message
response = requests.post(
    f"{BASE_URL}/chat/send",
    headers=headers,
    json={"message": "Hello from Python!"}
)
print(response.json())

# Send high priority announcement
response = requests.post(
    f"{BASE_URL}/system/announce",
    headers=headers,
    json={"message": "Maintenance starting soon"}
)
print(response.json())
```

### PowerShell Example

```powershell
$apiKey = "your-api-key-here"
$baseUrl = "http://localhost:8080/api/v1"

$headers = @{
    "X-API-Key" = $apiKey
    "Content-Type" = "application/json"
}

# Send message
$body = @{
    message = "Hello from PowerShell!"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "$baseUrl/chat/send" `
    -Method Post `
    -Headers $headers `
    -Body $body
```

---

## Future Enhancements

- Rate limiting per endpoint (prevent spam)
- Message queueing with retry logic
- Support for formatted messages (bold, italic, colors)
- Message history/recall
- Scheduled announcements
- Announcement templates
- Multi-line message support
- Mention/tag specific users in messages

---

## Rollback Plan

If issues arise:
1. Comment out new endpoints in `api_server.py`
2. Bot continues to function normally
3. Can still use PM commands for bot control
4. No database changes, so no data loss
5. Re-enable endpoints once issues resolved
