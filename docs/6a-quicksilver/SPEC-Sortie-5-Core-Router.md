# Sortie 5: Core Router Integration

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐☆☆ (Integration & Refactor)  
**Estimated Time:** 2-3 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 2 (EventBus), Sortie 3 (Subjects), Sortie 4 (Cytube Connector)

---

## Objective

Refactor bot core to use NATS EventBus for all communication, replacing direct event handlers with NATS subscriptions, implementing command routing and response handling.

---

## Deliverables

1. ✅ Refactored `Bot` class using EventBus
2. ✅ Command parser and router
3. ✅ Response handler for sending to platforms
4. ✅ Configuration updates
5. ✅ Migration guide
6. ✅ Tests

---

## Architecture Change

### Before (Current)

```
Bot.py ──────> Cytube WebSocket
  │              (direct connection)
  └──> Plugins (in-process)
```

### After (NATS-based)

```
Bot Core (Router)
  │
  └──> EventBus (NATS)
         │
         ├──> Cytube Connector (separate process)
         └──> Plugins (separate processes)
```

---

## Technical Tasks

### Task 5.1: Refactor Bot Class

**File:** `bot/rosey/core/router.py` (NEW - replaces parts of bot.py)

```python
"""
Core event router
Handles event routing, command parsing, and response coordination
"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

from bot.rosey.core.event_bus import EventBus, get_event_bus
from bot.rosey.core.subjects import Subjects, EventTypes
from bot.rosey.core.events import Event

logger = logging.getLogger(__name__)


@dataclass
class Command:
    """Parsed command structure"""
    name: str                      # Command name (e.g., 'trivia')
    action: str                    # Action (e.g., 'start', 'stop')
    args: list                     # Positional arguments
    kwargs: Dict[str, Any]         # Keyword arguments
    user: Dict[str, Any]           # User who issued command
    channel: str                   # Channel/platform context
    platform: str                  # Platform (cytube, discord, etc.)
    raw_message: str               # Original message text


class CommandParser:
    """
    Parse chat messages into commands
    
    Supports formats:
    - !trivia start
    - !trivia start easy
    - !markov generate --count 5
    """
    
    def __init__(self, prefix: str = "!"):
        self.prefix = prefix
    
    def is_command(self, text: str) -> bool:
        """Check if message is a command"""
        return text.strip().startswith(self.prefix)
    
    def parse(self, text: str, context: Dict[str, Any]) -> Optional[Command]:
        """
        Parse command from text
        
        Args:
            text: Message text
            context: Message context (user, channel, platform)
        
        Returns:
            Command object or None if not a valid command
        """
        if not self.is_command(text):
            return None
        
        # Remove prefix
        text = text.strip()[len(self.prefix):]
        
        # Split into tokens
        tokens = text.split()
        if not tokens:
            return None
        
        # First token is command name
        command_name = tokens[0].lower()
        
        # Second token (if exists) is action, else default to 'execute'
        action = tokens[1].lower() if len(tokens) > 1 else "execute"
        
        # Remaining tokens are arguments
        args = []
        kwargs = {}
        
        i = 2
        while i < len(tokens):
            token = tokens[i]
            
            # Check for --key value or --key=value
            if token.startswith('--'):
                if '=' in token:
                    key, value = token[2:].split('=', 1)
                    kwargs[key] = value
                elif i + 1 < len(tokens):
                    key = token[2:]
                    value = tokens[i + 1]
                    kwargs[key] = value
                    i += 1
            else:
                args.append(token)
            
            i += 1
        
        return Command(
            name=command_name,
            action=action,
            args=args,
            kwargs=kwargs,
            user=context.get("user", {}),
            channel=context.get("channel", ""),
            platform=context.get("platform", ""),
            raw_message=text
        )


class CoreRouter:
    """
    Core event router
    
    Responsibilities:
    - Subscribe to normalized events
    - Parse commands from messages
    - Route commands to plugins
    - Handle responses and send back to platforms
    
    Example:
        router = CoreRouter(event_bus)
        await router.start()
    """
    
    def __init__(self, event_bus: EventBus, command_prefix: str = "!"):
        self.event_bus = event_bus
        self.command_parser = CommandParser(prefix=command_prefix)
        self._running = False
        
        # Command handlers registry
        self._command_handlers: Dict[str, Callable] = {}
        
        # Response handlers by correlation_id
        self._response_handlers: Dict[str, asyncio.Queue] = {}
    
    async def start(self):
        """
        Start router
        
        Subscribes to events and begins processing
        """
        logger.info("Starting Core Router...")
        
        # Subscribe to normalized events
        await self.event_bus.subscribe(
            Subjects.EVENTS_MESSAGE,
            self._handle_message
        )
        
        await self.event_bus.subscribe(
            Subjects.EVENTS_USER_JOIN,
            self._handle_user_join
        )
        
        # Subscribe to command results from plugins
        await self.event_bus.subscribe(
            f"{Subjects.COMMANDS}.*.result",
            self._handle_command_result
        )
        
        # Subscribe to plugin errors
        await self.event_bus.subscribe(
            f"{Subjects.PLUGINS}.*.error",
            self._handle_plugin_error
        )
        
        self._running = True
        logger.info("Core Router started")
    
    async def stop(self):
        """Stop router"""
        logger.info("Stopping Core Router...")
        self._running = False
    
    def register_command_handler(self, command: str, handler: Callable):
        """
        Register direct command handler (for core commands)
        
        Args:
            command: Command name
            handler: Async function(command: Command) -> Dict
        """
        self._command_handlers[command] = handler
        logger.info(f"Registered command handler: {command}")
    
    # ========== Event Handlers ==========
    
    async def _handle_message(self, event: Event):
        """
        Handle incoming message event
        
        Checks if message is command, parses, and routes
        """
        data = event.data
        message_text = data.get("message", {}).get("text", "")
        
        logger.debug(f"Message from {data.get('user', {}).get('username')}: {message_text}")
        
        # Check if command
        if not self.command_parser.is_command(message_text):
            return
        
        # Parse command
        command = self.command_parser.parse(message_text, data)
        if not command:
            logger.warning(f"Failed to parse command: {message_text}")
            return
        
        logger.info(f"Command: {command.name} {command.action} from {command.user.get('username')}")
        
        # Check for direct handler (core commands)
        if command.name in self._command_handlers:
            try:
                result = await self._command_handlers[command.name](command)
                await self._send_response(command, result)
            except Exception as e:
                logger.error(f"Command handler error: {e}", exc_info=True)
                await self._send_error(command, str(e))
            return
        
        # Route to plugin via NATS
        await self._route_command(command, event.correlation_id)
    
    async def _handle_user_join(self, event: Event):
        """Handle user join event"""
        data = event.data
        username = data.get("user", {}).get("username")
        platform = data.get("platform")
        
        logger.info(f"User joined ({platform}): {username}")
        
        # Could implement welcome messages here
        # Or publish to plugins that care about user joins
    
    async def _handle_command_result(self, event: Event):
        """
        Handle command result from plugin
        
        Plugin publishes to: rosey.commands.{plugin}.result
        """
        logger.debug(f"Command result: {event.subject}")
        
        # Extract plugin name from subject
        plugin_name = event.subject.split('.')[2]  # rosey.commands.{plugin}.result
        
        # Get result data
        result_data = event.data
        
        # Determine response channel (from correlation_id or metadata)
        correlation_id = event.correlation_id
        response_channel = result_data.get("response_channel")
        
        # Send response back to platform
        if response_channel:
            await self._send_to_platform(response_channel, result_data)
    
    async def _handle_plugin_error(self, event: Event):
        """Handle plugin error event"""
        logger.error(f"Plugin error: {event.subject} - {event.data}")
        
        # Could notify admins, log to monitoring, etc.
    
    # ========== Command Routing ==========
    
    async def _route_command(self, command: Command, correlation_id: str):
        """
        Route command to plugin via NATS
        
        Publishes to: rosey.commands.{plugin}.execute
        """
        subject = Subjects.plugin_command(command.name, "execute")
        
        # Build command data
        command_data = {
            "action": command.action,
            "args": command.args,
            "kwargs": command.kwargs,
            "user": command.user,
            "channel": command.channel,
            "platform": command.platform,
            "response_channel": {
                "platform": command.platform,
                "channel": command.channel
            }
        }
        
        try:
            # Publish command (JetStream for guaranteed delivery)
            await self.event_bus.publish_js(
                subject,
                data=command_data,
                source="core-router",
                event_type=EventTypes.COMMAND,
                correlation_id=correlation_id
            )
            logger.debug(f"Routed command to {subject}")
        except Exception as e:
            logger.error(f"Failed to route command: {e}")
            await self._send_error(command, "Command routing failed")
    
    # ========== Response Handling ==========
    
    async def _send_response(self, command: Command, result: Dict[str, Any]):
        """
        Send command result back to platform
        
        Args:
            command: Original command
            result: Result data from handler/plugin
        """
        response_text = result.get("message") or result.get("text", "")
        
        if not response_text:
            logger.warning(f"No response text for command: {command.name}")
            return
        
        # Determine platform-specific send subject
        platform = command.platform
        channel = command.channel
        
        # Build send subject (e.g., rosey.platform.cytube.send.chat)
        send_subject = f"rosey.platform.{platform}.send.chat"
        
        # Build send data
        send_data = {
            "channel": channel,
            "message": response_text
        }
        
        # Add metadata if present
        if "metadata" in result:
            send_data["metadata"] = result["metadata"]
        
        # Publish to platform connector
        await self.event_bus.publish(
            send_subject,
            data=send_data,
            source="core-router"
        )
        
        logger.debug(f"Sent response to {platform}/{channel}")
    
    async def _send_error(self, command: Command, error_message: str):
        """Send error message back to user"""
        await self._send_response(command, {
            "message": f"❌ Error: {error_message}"
        })
    
    async def _send_to_platform(self, response_channel: Dict[str, Any], data: Dict[str, Any]):
        """
        Send data to platform
        
        Args:
            response_channel: {platform, channel}
            data: Data to send (must contain 'message' or 'text')
        """
        platform = response_channel.get("platform")
        channel = response_channel.get("channel")
        
        if not platform or not channel:
            logger.error("Invalid response channel")
            return
        
        send_subject = f"rosey.platform.{platform}.send.chat"
        
        await self.event_bus.publish(
            send_subject,
            data={
                "channel": channel,
                "message": data.get("message") or data.get("text", "")
            },
            source="core-router"
        )


# ========== Global Router Instance ==========

_router: Optional[CoreRouter] = None


async def initialize_router(event_bus: EventBus = None, **kwargs) -> CoreRouter:
    """
    Initialize and start global router
    
    Args:
        event_bus: EventBus instance (or uses global)
        **kwargs: Additional CoreRouter args
    
    Returns:
        CoreRouter instance
    """
    global _router
    
    if _router is not None:
        logger.warning("Router already initialized")
        return _router
    
    if event_bus is None:
        event_bus = await get_event_bus()
    
    _router = CoreRouter(event_bus, **kwargs)
    await _router.start()
    return _router


async def get_router() -> CoreRouter:
    """Get global router instance"""
    if _router is None:
        raise RuntimeError("Router not initialized. Call initialize_router() first.")
    return _router


async def shutdown_router():
    """Shutdown global router"""
    global _router
    
    if _router:
        await _router.stop()
        _router = None
```

---

### Task 5.2: Main Entry Point

**File:** `bot/rosey/main.py` (NEW)

```python
"""
Main entry point for Rosey bot
Initializes EventBus, starts router, manages lifecycle
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

from bot.rosey.core.event_bus import initialize_event_bus, shutdown_event_bus
from bot.rosey.core.router import initialize_router, shutdown_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class RoseyBot:
    """
    Main bot application
    Manages lifecycle of all components
    """
    
    def __init__(self):
        self.running = False
        self.event_bus = None
        self.router = None
    
    async def start(self):
        """Start bot"""
        logger.info("Starting Rosey Bot...")
        
        # Load configuration
        load_dotenv()
        
        # Initialize EventBus
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        nats_token = os.getenv("NATS_TOKEN")
        
        self.event_bus = await initialize_event_bus(
            servers=[nats_url],
            token=nats_token,
            name="rosey-core"
        )
        
        logger.info("EventBus initialized")
        
        # Initialize Router
        command_prefix = os.getenv("COMMAND_PREFIX", "!")
        self.router = await initialize_router(
            event_bus=self.event_bus,
            command_prefix=command_prefix
        )
        
        logger.info("Core Router initialized")
        
        # Register core commands
        self._register_core_commands()
        
        self.running = True
        logger.info("Rosey Bot started successfully")
    
    async def stop(self):
        """Stop bot"""
        logger.info("Stopping Rosey Bot...")
        self.running = False
        
        # Shutdown components
        await shutdown_router()
        await shutdown_event_bus()
        
        logger.info("Rosey Bot stopped")
    
    async def run(self):
        """
        Run bot (blocking)
        
        Keeps bot alive until stopped
        """
        await self.start()
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()
    
    def _register_core_commands(self):
        """Register core commands (non-plugin commands)"""
        
        # Example: !ping command
        async def handle_ping(command):
            return {"message": "🏓 Pong!"}
        
        # Example: !help command
        async def handle_help(command):
            return {
                "message": "Available commands: !ping, !help, !trivia, !markov, !quote, !poll, !media"
            }
        
        self.router.register_command_handler("ping", handle_ping)
        self.router.register_command_handler("help", handle_help)
        
        logger.info("Core commands registered")


async def main():
    """Main entry point"""
    bot = RoseyBot()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run bot
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### Task 5.3: Configuration Updates

**File:** `.env.example` (update)

```bash
# Bot Configuration
COMMAND_PREFIX=!

# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_TOKEN=dev-token-123

# Cytube Configuration (for connector)
CYTUBE_HOST=cytu.be
CYTUBE_CHANNEL=MyChannel
CYTUBE_USERNAME=RoseyBot
CYTUBE_PASSWORD=

# Logging
LOG_LEVEL=INFO
```

---

### Task 5.4: Unit Tests

**File:** `tests/core/test_router.py`

```python
"""
Tests for Core Router
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from bot.rosey.core.router import CoreRouter, CommandParser, Command
from bot.rosey.core.event_bus import EventBus
from bot.rosey.core.events import Event


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = Mock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.publish_js = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def router(mock_event_bus):
    """Create router instance"""
    return CoreRouter(mock_event_bus, command_prefix="!")


def test_command_parser_is_command():
    """Test command detection"""
    parser = CommandParser(prefix="!")
    
    assert parser.is_command("!trivia start")
    assert parser.is_command("!help")
    assert not parser.is_command("hello world")
    assert not parser.is_command("trivia start")


def test_command_parser_parse():
    """Test command parsing"""
    parser = CommandParser(prefix="!")
    
    context = {
        "user": {"username": "Alice"},
        "channel": "TestChannel",
        "platform": "cytube"
    }
    
    command = parser.parse("!trivia start easy", context)
    
    assert command.name == "trivia"
    assert command.action == "start"
    assert command.args == ["easy"]
    assert command.user["username"] == "Alice"


def test_command_parser_kwargs():
    """Test parsing keyword arguments"""
    parser = CommandParser(prefix="!")
    
    command = parser.parse("!markov generate --count 5 --user Alice", {})
    
    assert command.name == "markov"
    assert command.action == "generate"
    assert command.kwargs["count"] == "5"
    assert command.kwargs["user"] == "Alice"


@pytest.mark.asyncio
async def test_router_register_command():
    """Test command handler registration"""
    bus = Mock(spec=EventBus)
    router = CoreRouter(bus)
    
    async def handler(cmd):
        return {"message": "test"}
    
    router.register_command_handler("test", handler)
    
    assert "test" in router._command_handlers


@pytest.mark.asyncio
async def test_router_route_command(router, mock_event_bus):
    """Test command routing to plugin"""
    command = Command(
        name="trivia",
        action="start",
        args=[],
        kwargs={},
        user={"username": "Alice"},
        channel="TestChannel",
        platform="cytube",
        raw_message="trivia start"
    )
    
    await router._route_command(command, "correlation-123")
    
    # Should publish to rosey.commands.trivia.execute
    mock_event_bus.publish_js.assert_called_once()
    call_args = mock_event_bus.publish_js.call_args
    assert call_args[0][0] == "rosey.commands.trivia.execute"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Success Criteria

✅ CoreRouter class implemented  
✅ Command parsing working  
✅ Command routing to plugins via NATS  
✅ Response handling functional  
✅ Main entry point created  
✅ Tests passing (80%+ coverage)  
✅ Documentation complete  

---

## Time Breakdown

- Design & planning: 20 minutes
- CoreRouter implementation: 1.5 hours
- CommandParser: 30 minutes
- Main entry point: 30 minutes
- Unit tests: 30 minutes
- Documentation: 15 minutes

**Total: 3.25 hours**

---

## Next Steps

- → Sortie 6: Plugin Sandbox Foundation
- → Implement process isolation for plugins
- → Create plugin interface with permissions
