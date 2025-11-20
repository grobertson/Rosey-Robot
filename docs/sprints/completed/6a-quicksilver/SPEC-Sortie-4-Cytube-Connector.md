# Sortie 4: Cytube Connector Extraction

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐⭐☆ (Significant Refactor)  
**Estimated Time:** 3-4 hours  
**Priority:** HIGH  
**Dependencies:** Sortie 2 (EventBus Core), Sortie 3 (Subject Design)

---

## Objective

Extract Cytube-specific logic from bot core into standalone `CytubeConnector` service that translates between Cytube WebSocket events and NATS messages, providing platform abstraction.

---

## Deliverables

1. ✅ `CytubeConnector` service class
2. ✅ Event translation layer (Cytube ↔ NATS)
3. ✅ Event normalization (platform-specific → generic)
4. ✅ Configuration for connector
5. ✅ Tests for translation layer
6. ✅ Documentation

---

## Architecture

```
Cytube WebSocket  ←→  CytubeConnector  ←→  NATS Event Bus
(socket.io)           (translator)          (message broker)

Flow:
1. Cytube sends "chatMsg" via WebSocket
2. Connector receives, translates to NATS Event
3. Publishes to:
   - rosey.platform.cytube.chat (raw)
   - rosey.events.message (normalized)
4. Core/plugins subscribe to rosey.events.message
5. Response sent back through connector to Cytube
```

---

## Technical Tasks

### Task 4.1: Review Current Integration

**Analyze existing code:**

Current bot directly uses:
- `lib/socket_io.py` - WebSocket connection
- `lib/channel.py` - Channel state
- `lib/bot.py` - Event handlers (`on_chat_msg`, `on_user_join`, etc.)

**Goal:** Extract into separate service that communicates via NATS only.

---

### Task 4.2: Create CytubeConnector Service

**File:** `bot/rosey/connectors/cytube_connector.py`

```python
"""
Cytube platform connector
Bridges Cytube WebSocket and NATS event bus
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from bot.rosey.core.event_bus import EventBus
from bot.rosey.core.subjects import Subjects, EventTypes
from bot.rosey.core.events import Event, PlatformEvent

# Import existing Cytube client (from lib/)
from lib.socket_io import SocketIOClient
from lib.channel import Channel
from lib.user import User

logger = logging.getLogger(__name__)


class CytubeConnector:
    """
    Cytube platform connector
    
    Responsibilities:
    - Connect to Cytube via WebSocket
    - Translate Cytube events → NATS events (both raw and normalized)
    - Subscribe to NATS commands → send to Cytube
    - Maintain platform-specific state (users, playlist, media)
    
    Example:
        connector = CytubeConnector(
            host="cytu.be",
            channel="MyChannel",
            username="RoseyBot",
            event_bus=bus
        )
        await connector.connect()
        await connector.run()
    """
    
    def __init__(
        self,
        host: str,
        channel: str,
        username: str,
        password: str = None,
        event_bus: EventBus = None,
        use_ssl: bool = True
    ):
        """
        Initialize Cytube connector
        
        Args:
            host: Cytube server host
            channel: Channel name
            username: Bot username
            password: Bot password (if required)
            event_bus: EventBus instance
            use_ssl: Use SSL connection
        """
        self.host = host
        self.channel_name = channel
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.event_bus = event_bus
        
        self.client: Optional[SocketIOClient] = None
        self.channel: Optional[Channel] = None
        self._running = False
        self._tasks = []
    
    async def connect(self):
        """
        Connect to Cytube and NATS
        
        Raises:
            ConnectionError: If connection fails
        """
        logger.info(f"Connecting to Cytube: {self.host}/{self.channel_name}")
        
        # Connect to Cytube
        self.client = SocketIOClient(
            host=self.host,
            use_ssl=self.use_ssl
        )
        
        await self.client.connect()
        
        # Join channel
        self.channel = Channel(self.channel_name, self.client)
        await self.channel.join(self.username, self.password)
        
        # Register Cytube event handlers
        self._register_handlers()
        
        # Subscribe to NATS commands for sending messages to Cytube
        await self._subscribe_nats()
        
        logger.info(f"Connected to Cytube channel: {self.channel_name}")
    
    async def disconnect(self):
        """Disconnect from Cytube and clean up"""
        logger.info("Disconnecting from Cytube...")
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        
        if self.client:
            await self.client.disconnect()
        
        logger.info("Disconnected from Cytube")
    
    async def run(self):
        """
        Run connector (blocking)
        
        Keeps connector alive and processing events
        """
        self._running = True
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Connector run cancelled")
        finally:
            await self.disconnect()
    
    def _register_handlers(self):
        """
        Register Cytube event handlers
        
        Maps Cytube events to translation methods
        """
        if not self.channel:
            return
        
        # Chat events
        self.channel.on("chatMsg", self._on_chat_message)
        
        # User events
        self.channel.on("addUser", self._on_user_join)
        self.channel.on("userLeave", self._on_user_leave)
        
        # Media events
        self.channel.on("changeMedia", self._on_media_change)
        self.channel.on("queue", self._on_media_queue)
        self.channel.on("delete", self._on_media_delete)
        
        # Playlist events
        self.channel.on("playlist", self._on_playlist_update)
        self.channel.on("setPlaylistLocked", self._on_playlist_lock)
        
        logger.info("Registered Cytube event handlers")
    
    # ========== Cytube → NATS Translation ==========
    
    async def _on_chat_message(self, data: Dict[str, Any]):
        """
        Handle Cytube chat message
        
        Translates to:
        - rosey.platform.cytube.chat (raw)
        - rosey.events.message (normalized)
        """
        logger.debug(f"Chat message: {data.get('username')}: {data.get('msg')}")
        
        # Publish raw platform event
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_CHAT,
            data=data,
            source="cytube-connector",
            event_type=EventTypes.MESSAGE
        )
        
        # Publish normalized event
        normalized = self._normalize_chat_message(data)
        await self.event_bus.publish(
            Subjects.EVENTS_MESSAGE,
            data=normalized,
            source="cytube-connector",
            event_type=EventTypes.MESSAGE
        )
    
    async def _on_user_join(self, data: Dict[str, Any]):
        """Handle user join"""
        logger.debug(f"User joined: {data.get('name')}")
        
        # Raw
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_USER_JOIN,
            data=data,
            source="cytube-connector",
            event_type=EventTypes.USER_JOIN
        )
        
        # Normalized
        normalized = self._normalize_user_join(data)
        await self.event_bus.publish(
            Subjects.EVENTS_USER_JOIN,
            data=normalized,
            source="cytube-connector",
            event_type=EventTypes.USER_JOIN
        )
    
    async def _on_user_leave(self, data: Dict[str, Any]):
        """Handle user leave"""
        logger.debug(f"User left: {data.get('name')}")
        
        # Raw
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_USER_LEAVE,
            data=data,
            source="cytube-connector",
            event_type=EventTypes.USER_LEAVE
        )
        
        # Normalized
        normalized = self._normalize_user_leave(data)
        await self.event_bus.publish(
            Subjects.EVENTS_USER_LEAVE,
            data=normalized,
            source="cytube-connector",
            event_type=EventTypes.USER_LEAVE
        )
    
    async def _on_media_change(self, data: Dict[str, Any]):
        """Handle media change (Cytube-specific, no normalization)"""
        logger.debug(f"Media changed: {data.get('title')}")
        
        # Only publish platform-specific (media is Cytube-unique)
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_MEDIA_CHANGE,
            data=data,
            source="cytube-connector",
            event_type=EventTypes.MEDIA_CHANGE
        )
    
    async def _on_media_queue(self, data: Dict[str, Any]):
        """Handle media queue"""
        logger.debug(f"Media queued: {data.get('item', {}).get('media', {}).get('title')}")
        
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_MEDIA_QUEUE,
            data=data,
            source="cytube-connector",
            event_type=EventTypes.MEDIA_QUEUE
        )
    
    async def _on_media_delete(self, data: Dict[str, Any]):
        """Handle media delete"""
        logger.debug(f"Media deleted: UID {data.get('uid')}")
        
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_MEDIA_QUEUE,
            data={"action": "delete", **data},
            source="cytube-connector",
            event_type=EventTypes.MEDIA_DELETE
        )
    
    async def _on_playlist_update(self, data: Dict[str, Any]):
        """Handle playlist update"""
        logger.debug(f"Playlist updated: {len(data)} items")
        
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_PLAYLIST_UPDATE,
            data={"playlist": data},
            source="cytube-connector",
            event_type=EventTypes.PLAYLIST_UPDATE
        )
    
    async def _on_playlist_lock(self, data: Dict[str, Any]):
        """Handle playlist lock"""
        locked = data.get("locked", False)
        logger.debug(f"Playlist {'locked' if locked else 'unlocked'}")
        
        await self.event_bus.publish(
            Subjects.PLATFORM_CYTUBE_PLAYLIST_UPDATE,
            data={"action": "lock", "locked": locked},
            source="cytube-connector",
            event_type=EventTypes.PLAYLIST_LOCK
        )
    
    # ========== Event Normalization ==========
    
    def _normalize_chat_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Cytube chat message to generic format
        
        Cytube format:
        {
            "username": "Alice",
            "msg": "Hello world",
            "time": 1234567890,
            "meta": {...}
        }
        
        Generic format:
        {
            "platform": "cytube",
            "user": {
                "username": "Alice",
                "display_name": "Alice"
            },
            "message": {
                "text": "Hello world",
                "timestamp": 1234567890
            },
            "channel": "MyChannel",
            "raw": {...}  # Original data
        }
        """
        return {
            "platform": "cytube",
            "user": {
                "username": data.get("username"),
                "display_name": data.get("username"),
                "rank": data.get("meta", {}).get("rank", 0)
            },
            "message": {
                "text": data.get("msg"),
                "timestamp": data.get("time")
            },
            "channel": self.channel_name,
            "raw": data
        }
    
    def _normalize_user_join(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize user join event
        
        Generic format:
        {
            "platform": "cytube",
            "user": {
                "username": "Alice",
                "display_name": "Alice"
            },
            "channel": "MyChannel",
            "raw": {...}
        }
        """
        return {
            "platform": "cytube",
            "user": {
                "username": data.get("name"),
                "display_name": data.get("name"),
                "rank": data.get("rank", 0)
            },
            "channel": self.channel_name,
            "raw": data
        }
    
    def _normalize_user_leave(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize user leave event"""
        return {
            "platform": "cytube",
            "user": {
                "username": data.get("name"),
                "display_name": data.get("name")
            },
            "channel": self.channel_name,
            "raw": data
        }
    
    # ========== NATS → Cytube Translation ==========
    
    async def _subscribe_nats(self):
        """
        Subscribe to NATS subjects for sending to Cytube
        
        Listens to:
        - rosey.platform.cytube.send.* (platform-specific commands)
        """
        if not self.event_bus:
            return
        
        # Subscribe to Cytube-specific send commands
        await self.event_bus.subscribe(
            "rosey.platform.cytube.send.>",
            self._handle_send_command
        )
        
        logger.info("Subscribed to NATS command subjects")
    
    async def _handle_send_command(self, event: Event):
        """
        Handle NATS command to send to Cytube
        
        Subject format: rosey.platform.cytube.send.{action}
        Actions: chat, pm, media_queue, media_delete, etc.
        """
        # Extract action from subject
        tokens = event.subject.split('.')
        if len(tokens) < 5:
            logger.error(f"Invalid send command subject: {event.subject}")
            return
        
        action = tokens[4]  # rosey.platform.cytube.send.{action}
        
        logger.debug(f"Handling send command: {action}")
        
        # Dispatch to appropriate handler
        if action == "chat":
            await self._send_chat(event.data)
        elif action == "pm":
            await self._send_pm(event.data)
        elif action == "media_queue":
            await self._send_media_queue(event.data)
        else:
            logger.warning(f"Unknown send command: {action}")
    
    async def _send_chat(self, data: Dict[str, Any]):
        """Send chat message to Cytube"""
        message = data.get("message") or data.get("text")
        if message and self.channel:
            await self.channel.send_chat_message(message)
            logger.debug(f"Sent chat: {message}")
    
    async def _send_pm(self, data: Dict[str, Any]):
        """Send private message to user"""
        username = data.get("username")
        message = data.get("message")
        if username and message and self.channel:
            await self.channel.send_pm(username, message)
            logger.debug(f"Sent PM to {username}: {message}")
    
    async def _send_media_queue(self, data: Dict[str, Any]):
        """Queue media in Cytube"""
        media_data = data.get("media")
        if media_data and self.channel:
            await self.channel.queue_media(media_data)
            logger.debug(f"Queued media: {media_data}")


# ========== Standalone Service Runner ==========

async def run_connector(
    host: str,
    channel: str,
    username: str,
    password: str = None,
    nats_servers: list = None,
    nats_token: str = None
):
    """
    Run Cytube connector as standalone service
    
    Args:
        host: Cytube host
        channel: Channel name
        username: Bot username
        password: Bot password
        nats_servers: NATS server URLs
        nats_token: NATS auth token
    
    Example:
        await run_connector(
            host="cytu.be",
            channel="MyChannel",
            username="RoseyBot",
            nats_servers=["nats://localhost:4222"]
        )
    """
    from bot.rosey.core.event_bus import initialize_event_bus
    
    # Initialize event bus
    event_bus = await initialize_event_bus(
        servers=nats_servers,
        token=nats_token,
        name="cytube-connector"
    )
    
    # Create connector
    connector = CytubeConnector(
        host=host,
        channel=channel,
        username=username,
        password=password,
        event_bus=event_bus
    )
    
    # Connect and run
    await connector.connect()
    await connector.run()


if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    asyncio.run(run_connector(
        host=os.getenv("CYTUBE_HOST", "cytu.be"),
        channel=os.getenv("CYTUBE_CHANNEL"),
        username=os.getenv("CYTUBE_USERNAME"),
        password=os.getenv("CYTUBE_PASSWORD"),
        nats_servers=[os.getenv("NATS_URL", "nats://localhost:4222")],
        nats_token=os.getenv("NATS_TOKEN")
    ))
```

---

### Task 4.3: Configuration

**File:** `.env.example` (update)

```bash
# Cytube Configuration
CYTUBE_HOST=cytu.be
CYTUBE_CHANNEL=MyChannel
CYTUBE_USERNAME=RoseyBot
CYTUBE_PASSWORD=

# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_TOKEN=dev-token-123
```

---

### Task 4.4: Unit Tests

**File:** `tests/connectors/test_cytube_connector.py`

```python
"""
Tests for Cytube connector
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from bot.rosey.connectors.cytube_connector import CytubeConnector
from bot.rosey.core.event_bus import EventBus
from bot.rosey.core.subjects import Subjects


@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing"""
    bus = Mock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def connector(mock_event_bus):
    """Create connector instance for testing"""
    return CytubeConnector(
        host="cytu.be",
        channel="TestChannel",
        username="TestBot",
        event_bus=mock_event_bus
    )


@pytest.mark.asyncio
async def test_normalize_chat_message(connector):
    """Test chat message normalization"""
    cytube_data = {
        "username": "Alice",
        "msg": "Hello world",
        "time": 1234567890,
        "meta": {"rank": 2}
    }
    
    normalized = connector._normalize_chat_message(cytube_data)
    
    assert normalized["platform"] == "cytube"
    assert normalized["user"]["username"] == "Alice"
    assert normalized["message"]["text"] == "Hello world"
    assert normalized["channel"] == "TestChannel"


@pytest.mark.asyncio
async def test_chat_message_publishes_events(connector, mock_event_bus):
    """Test chat message publishes both raw and normalized events"""
    data = {
        "username": "Bob",
        "msg": "Test message",
        "time": 1234567890
    }
    
    await connector._on_chat_message(data)
    
    # Should publish twice: raw + normalized
    assert mock_event_bus.publish.call_count == 2
    
    # Check subjects
    calls = mock_event_bus.publish.call_args_list
    assert calls[0][0][0] == Subjects.PLATFORM_CYTUBE_CHAT  # Raw
    assert calls[1][0][0] == Subjects.EVENTS_MESSAGE        # Normalized


@pytest.mark.asyncio
async def test_user_join_normalization(connector):
    """Test user join normalization"""
    cytube_data = {
        "name": "Charlie",
        "rank": 1
    }
    
    normalized = connector._normalize_user_join(cytube_data)
    
    assert normalized["platform"] == "cytube"
    assert normalized["user"]["username"] == "Charlie"
    assert normalized["user"]["rank"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

### Task 4.5: Service Script

**File:** `infrastructure/services/run-cytube-connector.bat` (Windows)

```batch
@echo off
REM Run Cytube Connector Service

cd %~dp0\..\..
call venv\Scripts\activate

echo Starting Cytube Connector...
python -m bot.rosey.connectors.cytube_connector

pause
```

**File:** `infrastructure/services/run-cytube-connector.sh` (Linux)

```bash
#!/bin/bash

cd "$(dirname "$0")/../.."
source venv/bin/activate

echo "Starting Cytube Connector..."
python -m bot.rosey.connectors.cytube_connector
```

---

## Integration Testing

### Manual Test Flow

1. **Start NATS server:**

```powershell
cd infrastructure\nats
.\start-nats.bat
```

2. **Run EventBus monitor (in separate terminal):**

```python
# test-monitor.py
import asyncio
from bot.rosey.core.event_bus import initialize_event_bus
from bot.rosey.core.subjects import Subjects

async def monitor():
    bus = await initialize_event_bus()
    
    async def handler(event):
        print(f"Event: {event.subject}")
        print(f"  Type: {event.event_type}")
        print(f"  Data: {event.data}")
        print()
    
    await bus.subscribe(Subjects.PLATFORM_CYTUBE_ALL, handler)
    await bus.subscribe(Subjects.EVENTS_ALL, handler)
    
    print("Monitoring events... Press Ctrl+C to stop")
    while True:
        await asyncio.sleep(1)

asyncio.run(monitor())
```

3. **Start Cytube connector:**

```powershell
python infrastructure\services\run-cytube-connector.bat
```

4. **Verify events:**
   - Send chat message in Cytube
   - Monitor should show both platform and normalized events
   - Correlation IDs should match

---

## Documentation

Create `docs/architecture/CONNECTORS.md`:

```markdown
# Platform Connectors

## Overview

Connectors bridge external platforms (Cytube, Discord, Slack) with NATS event bus.

## Responsibilities

1. **Connect** to platform via native protocol (WebSocket, REST API, etc.)
2. **Translate** platform events → NATS events
3. **Normalize** platform events → generic events
4. **Subscribe** to NATS commands → execute on platform
5. **Maintain** platform-specific state

## Event Flow

```
Platform → Connector → NATS (raw + normalized) → Core/Plugins
Core/Plugins → NATS → Connector → Platform
```

## Cytube Connector

### Events Published

**Raw (Platform-Specific):**
- `rosey.platform.cytube.chat`
- `rosey.platform.cytube.user.join`
- `rosey.platform.cytube.media.change`

**Normalized (Generic):**
- `rosey.events.message`
- `rosey.events.user.join`

### Commands Subscribed

- `rosey.platform.cytube.send.chat` - Send chat message
- `rosey.platform.cytube.send.pm` - Send private message
- `rosey.platform.cytube.send.media_queue` - Queue media

### Configuration

```bash
CYTUBE_HOST=cytu.be
CYTUBE_CHANNEL=MyChannel
CYTUBE_USERNAME=RoseyBot
```

### Running Standalone

```bash
python -m bot.rosey.connectors.cytube_connector
```

## Adding New Connectors

To add Discord, Slack, etc.:

1. Create `bot/rosey/connectors/{platform}_connector.py`
2. Implement connection to platform API
3. Map platform events → NATS subjects
4. Normalize events to generic format
5. Subscribe to platform-specific command subjects
6. Test with integration tests
```

---

## Success Criteria

✅ CytubeConnector class implemented  
✅ Event translation working (Cytube → NATS)  
✅ Event normalization implemented  
✅ Command handling (NATS → Cytube)  
✅ Standalone service runnable  
✅ Tests passing (80%+ coverage)  
✅ Documentation complete  

---

## Time Breakdown

- Design & planning: 30 minutes
- CytubeConnector implementation: 2 hours
- Translation & normalization: 45 minutes
- Unit tests: 45 minutes
- Integration testing: 30 minutes
- Documentation: 15 minutes

**Total: 4.75 hours**

---

## Next Steps

- → Sortie 5: Core Router Integration
- → Refactor bot.py to use EventBus
- → Remove direct Cytube dependencies from core
