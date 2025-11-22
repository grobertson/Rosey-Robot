# Product Requirements Document: Multi-Platform Support

**Version:** 1.0  
**Status:** Planning (Nano-Sprint)  
**Sprint Name:** Sprint 10 "Across 110th Street" - *Crossing platform boundaries*  
**Target Release:** 0.10.0  
**Author:** GitHub Copilot (Claude Sonnet 4.5)  
**Date:** November 21, 2025  
**Priority:** HIGH - Enabled by Sprint 9 Architecture  
**Dependencies:** Sprint 9 (The Accountant) MUST be complete  

---

## Executive Summary

Sprint 10 "Across 110th Street" delivers on the promise of Sprint 9's architectural rework: **true multi-platform support**. With NATS-first architecture and event normalization complete, Rosey can now connect to Discord, Slack, and other chat platforms using platform-agnostic connection adapters.

**The Opportunity**: Sprint 9 established the foundation - normalized events, NATS-only communication, and layer isolation. Now we leverage that investment to add new platforms **without touching bot/database/plugin code**.

**The Solution**: Implement platform connection adapters that:
1. Connect to platform-specific APIs (Discord Gateway, Slack RTM/Events API)
2. Transform platform events to Rosey's normalized structure
3. Publish to NATS for bot/database/plugin consumption
4. Subscribe to NATS for outbound messages to platform

**Key Achievement Goal**: Rosey runs simultaneously on CyTube, Discord, and Slack with **zero code changes** to bot core, database, or plugins.

**Movie Connection**: *Across 110th Street* - crossing the boundary between different territories. Sprint 10 crosses platform boundaries while maintaining a unified system.

---

## 1. Product Overview

### 1.1 Background

**Sprint 9 Foundation:**

Sprint 9 "The Accountant" completed the architectural transformation:
- ✅ Event normalization complete - all events have consistent structure
- ✅ NATS-first communication - bot/database/plugins communicate only via NATS
- ✅ Process isolation - bot, database, plugins run in separate processes
- ✅ Hard boundaries - no direct access between layers
- ✅ Configuration v2 - platform-agnostic configuration format

**What Sprint 9 Enabled:**

```text
Platform-Agnostic Bot Core
         ↑
         │ Normalized events via NATS
         │
    ┌────┴────┬─────────┬─────────┐
    │         │         │         │
  CyTube   Discord   Slack     IRC
 Adapter   Adapter  Adapter  Adapter
    │         │         │         │
    ↓         ↓         ↓         ↓
  CyTube   Discord   Slack     IRC
  Server   Gateway     API    Server
```

**The Challenge:**

Each platform has different:
- Connection protocols (WebSocket, REST, Gateway)
- Event structures (different field names, types, formats)
- Authentication mechanisms (tokens, OAuth, passwords)
- Rate limits and constraints
- Feature capabilities (threads, reactions, embeds)

**The Solution:**

Platform adapters handle platform-specific details, bot core remains platform-agnostic.

### 1.2 Problem Statement

**User Need**: Bot operators want to:
- Run Rosey on Discord servers for gaming communities
- Run Rosey on Slack workspaces for team chat
- Run Rosey across multiple platforms simultaneously
- Use same plugins/commands regardless of platform
- Manage multiple bot instances from single configuration

**Developer Need**: Plugin developers want to:
- Write plugins once, work on all platforms
- Access normalized events regardless of platform
- Use platform-specific features when needed (via `platform_data`)
- Test plugins without multiple platform accounts

**Architectural Requirements:**

✅ **Zero Core Changes**: Bot/database/plugin code unchanged from Sprint 9

✅ **Adapter Pattern**: Each platform has dedicated connection adapter

✅ **Normalized Events**: All adapters emit same event structure

✅ **Platform Isolation**: Adapters handle platform quirks, not bot core

✅ **Configuration-Driven**: Enable/disable platforms via config

✅ **Independent Scaling**: Each platform adapter runs in separate process

**Impact of Success:**

- ✅ Rosey becomes truly multi-platform bot framework
- ✅ User base expands to Discord/Slack communities
- ✅ Plugins work everywhere (platform-agnostic)
- ✅ Development velocity increases (write once, run everywhere)
- ✅ Foundation for future platforms (IRC, Matrix, Telegram)

### 1.3 Solution

**Three Platform Adapters:**

1. **CyTube Adapter** (existing - needs refactoring)
   - Already implemented in `lib/connection/cytube.py`
   - Needs: Event normalization fixes from Sprint 9
   - Needs: Extract to adapter pattern

2. **Discord Adapter** (NEW)
   - Uses discord.py library (Gateway WebSocket)
   - Implements: Message, user join/leave, DMs, reactions
   - Target: Discord servers (multiple guilds/channels)

3. **Slack Adapter** (NEW)
   - Uses slack-sdk library (Events API + WebSocket)
   - Implements: Message, user join/leave, DMs, threads
   - Target: Slack workspaces (multiple channels)

**Architecture:**

```text
┌──────────────────────────────────────────────────────────┐
│                     NATS Event Bus                       │
│  Subjects:                                               │
│  • rosey.events.{platform}.message                       │
│  • rosey.events.{platform}.user.join                     │
│  • rosey.events.{platform}.user.leave                    │
│  • rosey.platform.{platform}.send_message                │
└──────────────────────────────────────────────────────────┘
    ↑ Publish      ↑ Publish      ↑ Publish      ↑ Subscribe
    │ normalized   │ normalized   │ normalized   │ to send
    │ events       │ events       │ events       │ commands
    │              │              │              │
┌───┴────┐    ┌───┴────┐    ┌───┴────┐    ┌───┴────┐
│ CyTube │    │Discord │    │ Slack  │    │  Bot   │
│Adapter │    │Adapter │    │Adapter │    │  Core  │
│Process │    │Process │    │Process │    │Process │
└───┬────┘    └───┬────┘    └───┬────┘    └────────┘
    │             │             │
    ↓             ↓             ↓
  CyTube       Discord        Slack
  WebSocket    Gateway     Events API
```

**Connection Adapter Interface:**

```python
class PlatformAdapter(ABC):
    """Base class for platform connection adapters."""
    
    @abstractmethod
    async def connect(self):
        """Connect to platform."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from platform."""
        pass
    
    @abstractmethod
    async def send_message(self, channel_id: str, content: str):
        """Send message to platform channel."""
        pass
    
    @abstractmethod
    def normalize_message(self, platform_event: dict) -> dict:
        """Transform platform message to normalized event."""
        pass
    
    @abstractmethod
    def normalize_user_join(self, platform_event: dict) -> dict:
        """Transform platform user join to normalized event."""
        pass
```

**Configuration v2 (Multi-Platform):**

```json
{
  "platforms": [
    {
      "type": "cytube",
      "enabled": true,
      "domain": "https://cytu.be",
      "channel": "AKWHR89327M",
      "credentials": {
        "username": "SaveTheRobots",
        "password": "password"
      }
    },
    {
      "type": "discord",
      "enabled": true,
      "credentials": {
        "bot_token": "YOUR_DISCORD_BOT_TOKEN"
      },
      "guilds": [
        {
          "guild_id": "123456789",
          "channels": ["general", "bot-commands"]
        }
      ]
    },
    {
      "type": "slack",
      "enabled": true,
      "credentials": {
        "bot_token": "xoxb-YOUR-SLACK-BOT-TOKEN",
        "app_token": "xapp-YOUR-SLACK-APP-TOKEN"
      },
      "workspace": "my-workspace",
      "channels": ["general", "random"]
    }
  ],
  "nats": {
    "server": "nats://localhost:4222",
    "cluster_id": "rosey",
    "client_id": "rosey-bot-1"
  },
  "database": {
    "path": "bot_data.db",
    "service_enabled": true
  },
  "plugins": {
    "directory": "./plugins",
    "enabled": ["markov", "quotes", "llm"]
  }
}
```

---

## 2. Goals and Success Metrics

### 2.1 Primary Goals

- **PG-001**: **Discord Support** - Full connection adapter for Discord (messages, users, DMs)
- **PG-002**: **Slack Support** - Full connection adapter for Slack (messages, users, DMs)
- **PG-003**: **CyTube Refactoring** - Extract CyTube to adapter pattern matching Discord/Slack
- **PG-004**: **Multi-Platform Bot** - Single bot instance connects to all platforms simultaneously
- **PG-005**: **Zero Core Changes** - Bot/database/plugin code unchanged (validates Sprint 9 architecture)
- **PG-006**: **Platform-Agnostic Plugins** - Existing plugins work on Discord/Slack without modification
- **PG-007**: **Configuration-Driven** - Enable/disable platforms via config, no code changes

### 2.2 Success Metrics

| Metric | Target | Measurement | Verification |
|--------|--------|-------------|--------------|
| Platform Adapters | 3 | CyTube, Discord, Slack | Implementation complete |
| Normalized Event Compliance | 100% | All adapters emit consistent structure | Validation tests |
| Zero Core Modifications | ✅ | No changes to bot/database/plugin code | Git diff analysis |
| Plugin Compatibility | 100% | All plugins work on all platforms | Integration tests |
| Multi-Platform Operation | ✅ | Bot runs on all 3 platforms simultaneously | Live deployment test |
| Event Throughput | >500 msg/sec per platform | Measured under load | Performance tests |
| Connection Reliability | >99.9% uptime per platform | Connection monitoring | 24-hour stability test |
| Configuration Simplicity | <5 min setup per platform | Time to add new platform | User testing |

### 2.3 Non-Goals

**Out of Scope for Sprint 10:**

- ✗ IRC, Matrix, Telegram adapters - future platforms after proving pattern
- ✗ Platform-specific features (Discord threads, Slack workflows) - phase 2
- ✗ Cross-platform message forwarding - Sprint 11+ feature
- ✗ Platform-specific UI (embeds, rich formatting) - basic text first
- ✗ Voice/video support - text chat only
- ✗ Platform moderation APIs - focus on messaging
- ✗ OAuth flows - bot tokens only (users provide pre-configured tokens)

**Future Sprints Will Deliver:**

- Sprint 11 (Assault on Precinct 13): Plugin process isolation and sandboxing
- Sprint 12 (The Expandables): Horizontal scaling across multiple bot instances
- Sprint 13+: Advanced platform features (threads, reactions, embeds)
- Sprint 13+: Cross-platform bridging and message forwarding

---

## 3. Platform Specifications

### 3.1 Discord Adapter

**Library**: `discord.py` (v2.x)

**Connection Method**: Discord Gateway (WebSocket)

**Authentication**: Bot token (`credentials.bot_token`)

**Normalized Events Supported:**

1. **Message Event**
   ```python
   {
       "user": message.author.name,
       "content": message.content,
       "timestamp": int(message.created_at.timestamp()),
       "channel_id": str(message.channel.id),
       "platform": "discord",
       "platform_data": {
           "message_id": str(message.id),
           "guild_id": str(message.guild.id) if message.guild else None,
           "channel_id": str(message.channel.id),
           "author": {
               "id": str(message.author.id),
               "name": message.author.name,
               "discriminator": message.author.discriminator,
               "bot": message.author.bot
           },
           "embeds": message.embeds,
           "attachments": message.attachments
       }
   }
   ```

2. **User Join Event**
   ```python
   {
       "user": member.name,
       "user_data": {
           "username": member.name,
           "rank": 1,  # Map Discord roles to rank
           "is_afk": False,
           "is_moderator": member.guild_permissions.manage_messages,
           "display_name": member.display_name
       },
       "timestamp": int(member.joined_at.timestamp()),
       "channel_id": None,  # Guild-level event
       "platform": "discord",
       "platform_data": {
           "member_id": str(member.id),
           "guild_id": str(member.guild.id),
           "roles": [str(role.id) for role in member.roles],
           "permissions": member.guild_permissions.value
       }
   }
   ```

3. **User Leave Event**
   ```python
   {
       "user": member.name,
       "timestamp": int(time.time()),
       "channel_id": None,
       "platform": "discord",
       "platform_data": {
           "member_id": str(member.id),
           "guild_id": str(member.guild.id)
       }
   }
   ```

4. **PM (Direct Message) Event**
   ```python
   {
       "user": message.author.name,
       "recipient": client.user.name,  # Bot's username
       "content": message.content,
       "timestamp": int(message.created_at.timestamp()),
       "platform": "discord",
       "platform_data": {
           "message_id": str(message.id),
           "channel_id": str(message.channel.id),
           "author_id": str(message.author.id)
       }
   }
   ```

**Configuration:**
```json
{
  "type": "discord",
  "enabled": true,
  "credentials": {
    "bot_token": "YOUR_DISCORD_BOT_TOKEN"
  },
  "guilds": [
    {
      "guild_id": "123456789",
      "channels": ["general", "bot-commands"],
      "excluded_channels": ["admin-only"]
    }
  ],
  "intents": {
    "guilds": true,
    "members": true,
    "messages": true,
    "message_content": true
  },
  "rate_limits": {
    "messages_per_second": 5,
    "burst": 10
  }
}
```

**Rate Limits**: Discord allows 5 messages/sec per channel, adapter must queue and throttle

**Bot Setup Requirements**:
- Create Discord Application at https://discord.com/developers/applications
- Enable "Message Content Intent" in Bot settings
- Generate bot token
- Invite bot to server with appropriate permissions (Send Messages, Read Message History)

### 3.2 Slack Adapter

**Library**: `slack-sdk` (v3.x)

**Connection Method**: Slack Events API + Socket Mode (WebSocket)

**Authentication**: Bot token (`xoxb-*`) + App token (`xapp-*`)

**Normalized Events Supported:**

1. **Message Event**
   ```python
   {
       "user": event["user_profile"]["display_name"] or event["user_profile"]["real_name"],
       "content": event["text"],
       "timestamp": int(float(event["ts"])),
       "channel_id": event["channel"],
       "platform": "slack",
       "platform_data": {
           "user_id": event["user"],
           "channel_id": event["channel"],
           "thread_ts": event.get("thread_ts"),
           "blocks": event.get("blocks"),
           "attachments": event.get("attachments")
       }
   }
   ```

2. **User Join Event** (member_joined_channel)
   ```python
   {
       "user": user_info["profile"]["display_name"] or user_info["real_name"],
       "user_data": {
           "username": user_info["name"],
           "rank": 1,  # Map based on is_admin, is_owner
           "is_afk": False,
           "is_moderator": user_info.get("is_admin", False),
           "display_name": user_info["profile"]["display_name"]
       },
       "timestamp": int(time.time()),
       "channel_id": event["channel"],
       "platform": "slack",
       "platform_data": {
           "user_id": event["user"],
           "channel_id": event["channel"],
           "team_id": event.get("team")
       }
   }
   ```

3. **User Leave Event** (member_left_channel)
   ```python
   {
       "user": user_name,  # Lookup required
       "timestamp": int(time.time()),
       "channel_id": event["channel"],
       "platform": "slack",
       "platform_data": {
           "user_id": event["user"],
           "channel_id": event["channel"]
       }
   }
   ```

4. **PM Event** (im message)
   ```python
   {
       "user": event["user_profile"]["display_name"],
       "recipient": bot_user_name,
       "content": event["text"],
       "timestamp": int(float(event["ts"])),
       "platform": "slack",
       "platform_data": {
           "user_id": event["user"],
           "channel_id": event["channel"]
       }
   }
   ```

**Configuration:**
```json
{
  "type": "slack",
  "enabled": true,
  "credentials": {
    "bot_token": "xoxb-YOUR-SLACK-BOT-TOKEN",
    "app_token": "xapp-YOUR-SLACK-APP-TOKEN"
  },
  "workspace": "my-workspace",
  "channels": [
    "general",
    "random",
    "bot-testing"
  ],
  "socket_mode": true,
  "rate_limits": {
    "messages_per_second": 1,
    "tier": "standard"
  }
}
```

**Rate Limits**: Slack Tier 1 (standard) allows 1 message/sec, adapter must respect limits

**Bot Setup Requirements**:
- Create Slack App at https://api.slack.com/apps
- Enable Socket Mode
- Subscribe to bot events: `message.channels`, `member_joined_channel`, `member_left_channel`
- Add OAuth scopes: `chat:write`, `channels:read`, `channels:history`, `users:read`
- Install app to workspace
- Copy Bot User OAuth Token (`xoxb-*`)
- Copy App-Level Token (`xapp-*`)

### 3.3 CyTube Adapter Refactoring

**Current State**: `lib/connection/cytube.py` is tightly coupled to bot

**Target State**: Extract to adapter pattern matching Discord/Slack

**Refactoring Steps**:

1. Create `lib/adapters/cytube_adapter.py`
2. Move connection logic from `lib/connection/cytube.py`
3. Implement `PlatformAdapter` interface
4. Update event normalization (fixes from Sprint 9)
5. Remove direct bot references
6. Publish to NATS instead of callback pattern

**Normalized Events** (already defined in Sprint 9):
- Message, user_join, user_leave, user_list, pm

**Configuration** (already exists):
```json
{
  "type": "cytube",
  "enabled": true,
  "domain": "https://cytu.be",
  "channel": "AKWHR89327M",
  "credentials": {
    "username": "SaveTheRobots",
    "password": "password"
  }
}
```

---

## 4. Implementation Plan

### Phase 1: Adapter Framework (2-3 hours)

**Goal**: Establish common adapter interface and infrastructure

**Deliverables**:
1. `lib/adapters/base.py` - `PlatformAdapter` abstract base class
2. `lib/adapters/__init__.py` - Adapter registry
3. `lib/adapters/manager.py` - Multi-adapter manager
4. Configuration schema for multi-platform setup
5. NATS subject hierarchy for platform-specific events

**NATS Subjects**:
```text
rosey.platform.{platform_name}.events.message
rosey.platform.{platform_name}.events.user.join
rosey.platform.{platform_name}.events.user.leave
rosey.platform.{platform_name}.events.pm
rosey.platform.{platform_name}.commands.send_message
rosey.platform.{platform_name}.commands.send_pm
```

**Example**:
```python
# lib/adapters/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class PlatformAdapter(ABC):
    """Base class for all platform connection adapters."""
    
    def __init__(self, nats_client, config: Dict[str, Any]):
        self.nats = nats_client
        self.config = config
        self.platform_name = config.get('type', 'unknown')
        
    @abstractmethod
    async def connect(self):
        """Connect to platform and start listening for events."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from platform."""
        pass
    
    @abstractmethod
    async def send_message(self, channel_id: str, content: str):
        """Send message to platform channel."""
        pass
    
    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish normalized event to NATS."""
        subject = f"rosey.platform.{self.platform_name}.events.{event_type}"
        await self.nats.publish(subject, data)
```

### Phase 2: Discord Adapter (4-6 hours)

**Goal**: Full Discord support with all normalized events

**Dependencies**:
- Install: `pip install discord.py`
- Discord bot token configured

**Deliverables**:
1. `lib/adapters/discord_adapter.py` - Full Discord implementation
2. Unit tests for Discord event normalization
3. Integration tests for Discord connection
4. Documentation: `docs/platforms/DISCORD_SETUP.md`

**Implementation**:
```python
# lib/adapters/discord_adapter.py
import discord
from discord.ext import commands
from .base import PlatformAdapter

class DiscordAdapter(PlatformAdapter):
    def __init__(self, nats_client, config):
        super().__init__(nats_client, config)
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.client = discord.Client(intents=intents)
        self._setup_handlers()
    
    async def connect(self):
        """Connect to Discord Gateway."""
        token = self.config['credentials']['bot_token']
        await self.client.start(token)
    
    async def disconnect(self):
        """Disconnect from Discord."""
        await self.client.close()
    
    async def send_message(self, channel_id: str, content: str):
        """Send message to Discord channel."""
        channel = self.client.get_channel(int(channel_id))
        if channel:
            await channel.send(content)
    
    def _setup_handlers(self):
        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return  # Ignore own messages
            
            normalized = self.normalize_message(message)
            await self._publish_event('message', normalized)
        
        @self.client.event
        async def on_member_join(member):
            normalized = self.normalize_user_join(member)
            await self._publish_event('user.join', normalized)
    
    def normalize_message(self, message: discord.Message) -> dict:
        """Transform Discord message to normalized event."""
        return {
            'user': message.author.name,
            'content': message.content,
            'timestamp': int(message.created_at.timestamp()),
            'channel_id': str(message.channel.id),
            'platform': 'discord',
            'platform_data': {
                'message_id': str(message.id),
                'guild_id': str(message.guild.id) if message.guild else None,
                'author': {
                    'id': str(message.author.id),
                    'name': message.author.name,
                    'bot': message.author.bot
                }
            }
        }
```

### Phase 3: Slack Adapter (4-6 hours)

**Goal**: Full Slack support with all normalized events

**Dependencies**:
- Install: `pip install slack-sdk`
- Slack bot token + app token configured

**Deliverables**:
1. `lib/adapters/slack_adapter.py` - Full Slack implementation
2. Unit tests for Slack event normalization
3. Integration tests for Slack connection
4. Documentation: `docs/platforms/SLACK_SETUP.md`

**Implementation**:
```python
# lib/adapters/slack_adapter.py
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from .base import PlatformAdapter

class SlackAdapter(PlatformAdapter):
    def __init__(self, nats_client, config):
        super().__init__(nats_client, config)
        self.app_token = config['credentials']['app_token']
        self.bot_token = config['credentials']['bot_token']
        self.web_client = WebClient(token=self.bot_token)
        self.socket_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self.web_client
        )
        self._setup_handlers()
    
    async def connect(self):
        """Connect to Slack via Socket Mode."""
        self.socket_client.connect()
    
    async def disconnect(self):
        """Disconnect from Slack."""
        self.socket_client.close()
    
    async def send_message(self, channel_id: str, content: str):
        """Send message to Slack channel."""
        self.web_client.chat_postMessage(
            channel=channel_id,
            text=content
        )
    
    def _setup_handlers(self):
        @self.socket_client.on("message")
        async def handle_message(client, event):
            if event.get("subtype") == "bot_message":
                return  # Ignore bot messages
            
            normalized = self.normalize_message(event)
            await self._publish_event('message', normalized)
        
        @self.socket_client.on("member_joined_channel")
        async def handle_join(client, event):
            normalized = self.normalize_user_join(event)
            await self._publish_event('user.join', normalized)
    
    def normalize_message(self, event: dict) -> dict:
        """Transform Slack message to normalized event."""
        # Lookup user info
        user_info = self.web_client.users_info(user=event["user"])
        user_profile = user_info["user"]["profile"]
        
        return {
            'user': user_profile.get("display_name") or user_profile.get("real_name"),
            'content': event["text"],
            'timestamp': int(float(event["ts"])),
            'channel_id': event["channel"],
            'platform': 'slack',
            'platform_data': {
                'user_id': event["user"],
                'channel_id': event["channel"],
                'thread_ts': event.get("thread_ts")
            }
        }
```

### Phase 4: CyTube Refactoring (2-3 hours)

**Goal**: Extract CyTube to adapter pattern

**Deliverables**:
1. `lib/adapters/cytube_adapter.py` - Refactored CyTube adapter
2. Update `lib/connection/cytube.py` to use adapter
3. Tests updated to use adapter pattern
4. Documentation updated

**Implementation**: Move existing CyTube logic to adapter, implement `PlatformAdapter` interface

### Phase 5: Multi-Platform Manager (2-3 hours)

**Goal**: Orchestrate multiple platform adapters simultaneously

**Deliverables**:
1. `lib/adapters/manager.py` - Adapter lifecycle management
2. Configuration loading and validation
3. Graceful startup/shutdown for all platforms
4. Health checks and monitoring

**Implementation**:
```python
# lib/adapters/manager.py
class AdapterManager:
    """Manages multiple platform adapters."""
    
    def __init__(self, nats_client, config):
        self.nats = nats_client
        self.config = config
        self.adapters = []
    
    async def start_all(self):
        """Start all enabled platform adapters."""
        for platform_config in self.config.get('platforms', []):
            if not platform_config.get('enabled', False):
                continue
            
            adapter = self._create_adapter(platform_config)
            await adapter.connect()
            self.adapters.append(adapter)
    
    async def stop_all(self):
        """Stop all platform adapters."""
        for adapter in self.adapters:
            await adapter.disconnect()
    
    def _create_adapter(self, config):
        """Factory method to create adapter based on type."""
        adapter_type = config['type']
        if adapter_type == 'discord':
            return DiscordAdapter(self.nats, config)
        elif adapter_type == 'slack':
            return SlackAdapter(self.nats, config)
        elif adapter_type == 'cytube':
            return CyTubeAdapter(self.nats, config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
```

### Phase 6: Testing & Documentation (3-4 hours)

**Goal**: Comprehensive testing and user documentation

**Deliverables**:
1. Unit tests for each adapter (normalization logic)
2. Integration tests (live connections - optional)
3. Multi-platform deployment guide
4. Platform setup tutorials (Discord, Slack, CyTube)
5. Troubleshooting documentation
6. Example configurations

**Testing Strategy**:
- Mock platform APIs for unit tests
- Use test bot accounts for integration tests (optional)
- Validate normalized event structure for all platforms
- Test multi-platform operation (all 3 simultaneously)
- Performance testing (throughput, latency)

---

## 5. User Stories and Acceptance Criteria

### 5.1 Epic: Discord Integration

**User Story 5.1.1: Discord Bot Connection**
```
As a bot operator
I want to connect Rosey to my Discord server
So that I can use Rosey's features in Discord
```

**Acceptance Criteria:**
- [ ] Discord adapter connects to Discord Gateway via bot token
- [ ] Bot appears online in Discord server
- [ ] Bot can send and receive messages in configured channels
- [ ] Bot gracefully handles connection failures and reconnects
- [ ] Configuration includes Discord bot token and guild/channel settings

**User Story 5.1.2: Discord Event Normalization**
```
As a plugin developer
I want Discord events to have the same structure as CyTube events
So that my plugins work on Discord without code changes
```

**Acceptance Criteria:**
- [ ] Discord messages normalized to `{user, content, timestamp, platform_data}`
- [ ] Discord member joins normalized to `{user, user_data, timestamp, platform_data}`
- [ ] Discord member leaves normalized to `{user, timestamp, platform_data}`
- [ ] Discord DMs normalized to `{user, recipient, content, timestamp, platform_data}`
- [ ] All normalized events include `platform: "discord"` field
- [ ] Unit tests verify event structure for all event types

### 5.2 Epic: Slack Integration

**User Story 5.2.1: Slack Bot Connection**
```
As a bot operator
I want to connect Rosey to my Slack workspace
So that I can use Rosey's features in Slack
```

**Acceptance Criteria:**
- [ ] Slack adapter connects to Slack Events API via Socket Mode
- [ ] Bot appears online in Slack workspace
- [ ] Bot can send and receive messages in configured channels
- [ ] Bot gracefully handles connection failures and reconnects
- [ ] Configuration includes Slack bot token, app token, and channel settings

**User Story 5.2.2: Slack Event Normalization**
```
As a plugin developer
I want Slack events to have the same structure as CyTube events
So that my plugins work on Slack without code changes
```

**Acceptance Criteria:**
- [ ] Slack messages normalized to `{user, content, timestamp, platform_data}`
- [ ] Slack member joins normalized to `{user, user_data, timestamp, platform_data}`
- [ ] Slack member leaves normalized to `{user, timestamp, platform_data}`
- [ ] Slack DMs normalized to `{user, recipient, content, timestamp, platform_data}`
- [ ] All normalized events include `platform: "slack"` field
- [ ] Unit tests verify event structure for all event types

### 5.3 Epic: Multi-Platform Operation

**User Story 5.3.1: Simultaneous Platform Connections**
```
As a bot operator
I want to run Rosey on CyTube, Discord, and Slack simultaneously
So that I can manage communities across multiple platforms
```

**Acceptance Criteria:**
- [ ] Configuration supports multiple platform entries
- [ ] Adapter manager starts all enabled platforms
- [ ] Bot responds to messages on all platforms independently
- [ ] Plugins receive events from all platforms
- [ ] Each platform adapter runs in isolated process/thread
- [ ] Failure on one platform doesn't affect others

**User Story 5.3.2: Platform-Agnostic Plugins**
```
As a plugin developer
I want my plugins to work on all platforms without modification
So that I don't have to write platform-specific code
```

**Acceptance Criteria:**
- [ ] Markov plugin works on Discord without changes
- [ ] Quotes plugin works on Slack without changes
- [ ] LLM plugin works on all platforms without changes
- [ ] Plugins use NATS to access platform events
- [ ] Plugins don't need to know which platform events came from
- [ ] Integration tests verify plugins on each platform

---

## 6. Success Criteria

### Definition of Done

**Platform Adapters Complete:**
- [ ] Discord adapter implemented with all normalized events
- [ ] Slack adapter implemented with all normalized events
- [ ] CyTube adapter refactored to match adapter pattern
- [ ] All adapters implement `PlatformAdapter` interface
- [ ] All adapters publish to NATS (no direct bot references)

**Testing Complete:**
- [ ] Unit tests for each adapter (event normalization)
- [ ] Integration tests for each platform (connection, send/receive)
- [ ] Multi-platform test (all 3 platforms simultaneously)
- [ ] Plugin compatibility tests (existing plugins on new platforms)
- [ ] Performance tests (throughput, latency per platform)

**Documentation Complete:**
- [ ] Platform setup guides (Discord, Slack, CyTube)
- [ ] Multi-platform deployment guide
- [ ] Configuration reference with examples
- [ ] Troubleshooting documentation
- [ ] Architecture updates (ARCHITECTURE.md)

**Deployment Ready:**
- [ ] Bot connects to all configured platforms
- [ ] Plugins work on all platforms
- [ ] Zero modifications to bot core (validates Sprint 9 architecture)
- [ ] Configuration examples provided
- [ ] Migration guide from single-platform to multi-platform

---

## 7. Risks and Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Platform API changes | Medium | High | Pin library versions, monitor changelogs |
| Rate limiting issues | High | Medium | Implement throttling, queue management |
| Event structure inconsistencies | Medium | High | Comprehensive validation tests |
| NATS throughput bottleneck | Low | Medium | Performance testing early, optimize if needed |
| Platform-specific auth complexity | Medium | Medium | Clear setup documentation, validation |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Multiple bot token management | High | Low | Secure configuration storage, documentation |
| Platform downtime | Medium | Medium | Graceful degradation, automatic reconnection |
| Plugin incompatibility | Low | Medium | Comprehensive compatibility testing |
| Configuration complexity | Medium | Low | Configuration validation, examples |

---

## 8. Future Enhancements

### Sprint 11 (Assault on Precinct 13)

**Plugin Sandboxing** - Enabled by Sprint 10's multi-platform validation:
- Process isolation for plugins (separate processes)
- Resource limits (CPU, memory, rate limits)
- Permission system (plugins declare required capabilities)
- Secure plugin marketplace

### Sprint 12 (The Expandables)

**Horizontal Scaling** - Enabled by Sprint 10's adapter pattern:
- Multiple bot instances per platform
- Load balancing across instances
- Distributed state management
- High availability deployment

### Sprint 13+ (Future)

**Advanced Platform Features:**
- Discord: Threads, reactions, embeds, slash commands
- Slack: Workflows, blocks, interactive components
- Platform-specific UI components
- Cross-platform message bridging
- Additional platforms: IRC, Matrix, Telegram, WhatsApp

---

## Appendix: Platform Comparison

| Feature | CyTube | Discord | Slack |
|---------|--------|---------|-------|
| Connection | WebSocket | Gateway (WebSocket) | Socket Mode (WebSocket) |
| Auth | Username/Password | Bot Token | Bot Token + App Token |
| Rate Limit | ~10 msg/sec | 5 msg/sec per channel | 1 msg/sec (Tier 1) |
| User List | Yes | Guild members | Channel members |
| DMs | Yes | Yes | Yes |
| Threads | No | Yes | Yes |
| Reactions | No | Yes | Yes |
| Embeds | Limited | Rich embeds | Blocks/Attachments |
| Setup Complexity | Low | Medium | High |

---

**Sprint Status**: Ready to Begin (Blocked by Sprint 9)  
**Estimated Effort**: 17-25 hours (3-4 days)  
**Sprint Goal**: Cross platform boundaries - Rosey works on CyTube, Discord, and Slack  
**Movie Tagline**: "They're across 110th Street... going from one platform to another!"
