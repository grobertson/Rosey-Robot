# Sprint 7, Sortie 3: Bot Connection Integration

**Status:** Planning  
**Estimated Effort:** 6 hours  
**Sprint:** The Divide (Sprint 7)  
**Phase:** 1 - Extract Connection Layer  
**Dependencies:** Sortie 1 (ConnectionAdapter), Sortie 2 (CyTubeConnection)

## Objective

Refactor `Bot` class to use `ConnectionAdapter` interface via dependency injection, removing all direct socket.io dependencies from bot.py. The bot should work with any connection implementation, not just CyTube.

## Background

Currently, `Bot.__init__()` accepts socket.io connection parameters and creates socket connection internally. After this sortie:
- Bot accepts `ConnectionAdapter` instance via dependency injection
- All `socket.emit()` calls replaced with `connection.send_*()` methods
- All CyTube event handling uses normalized events
- Bot is platform-agnostic

## Success Criteria

- ✅ Bot constructor accepts `ConnectionAdapter` instance
- ✅ No direct socket.io imports in bot.py
- ✅ All socket operations go through connection adapter
- ✅ All CyTube event handlers use normalized events
- ✅ Existing bot implementations (rosey.py) work with minimal changes
- ✅ All existing tests updated and passing
- ✅ No functionality regressions

## Technical Design

### Bot Constructor Changes

**Before:**
```python
class Bot:
    def __init__(self, domain, channel, user=None, 
                 restart_delay=5, response_timeout=0.1,
                 get=default_get, socket_io=SocketIO.connect,
                 db_path='bot_data.db', enable_db=True):
        self.domain = domain
        self.channel_name, self.channel_password = to_sequence(channel, 2)
        # ... socket.io setup
```

**After:**
```python
class Bot:
    def __init__(self, connection: ConnectionAdapter,
                 storage: Optional[StorageAdapter] = None,
                 restart_delay: float = 5.0):
        """
        Initialize bot with dependency injection.
        
        Args:
            connection: Connection adapter for chat platform
            storage: Optional storage adapter for persistence
            restart_delay: Delay before reconnection attempts
        """
        self.connection = connection
        self.storage = storage
        self.restart_delay = restart_delay
        
        self.channel = Channel()
        self.user = User()
        self.handlers = collections.defaultdict(list)
        
        self.logger = logging.getLogger(__name__)
```

### Method Refactoring

**1. Remove Connection Management**

Methods to **DELETE** from Bot:
- `get_socket_config()` - Now in CyTubeConnection
- `connect()` - Now in ConnectionAdapter
- `login()` - Now in CyTubeConnection

**2. Update Run Loop**

**Before:**
```python
async def run(self):
    """Main event loop."""
    while True:
        try:
            await self.get_socket_config()
            self.socket = await self.socket_io(self.server, loop=self.loop)
            await self.login()
            
            while True:
                ev, data = await self.socket.recv()
                await self.trigger(ev, data)
                
        except Exception as e:
            self.logger.error(f"Error: {e}")
            if self.restart_delay:
                await asyncio.sleep(self.restart_delay)
            else:
                break
```

**After:**
```python
async def run(self):
    """Main event loop."""
    while True:
        try:
            await self.connection.connect()
            
            async for event, data in self.connection.recv_events():
                await self.trigger(event, data)
                
        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            
            if self.restart_delay and self.restart_delay > 0:
                await asyncio.sleep(self.restart_delay)
                await self.connection.reconnect()
            else:
                break
        finally:
            await self.connection.disconnect()
```

**3. Update Message Sending**

**Before:**
```python
async def chat(self, msg, **kwargs):
    """Send chat message."""
    await self.socket.emit('chatMsg', {
        'msg': msg,
        'meta': kwargs.get('meta', {})
    })
```

**After:**
```python
async def chat(self, msg: str, **kwargs):
    """Send chat message."""
    await self.connection.send_message(msg, **kwargs)
```

**4. Update PM Sending**

**Before:**
```python
async def pm(self, username, msg):
    """Send private message."""
    res = await self.socket.emit(
        'pm',
        {'to': username, 'msg': msg},
        callback=True,
        timeout=self.response_timeout
    )
    # ...
```

**After:**
```python
async def pm(self, username: str, msg: str):
    """Send private message."""
    await self.connection.send_pm(username, msg)
```

**5. Update Event Handlers**

**Before (CyTube events):**
```python
def _on_chatMsg(self, event, data):
    """Handle chatMsg event."""
    username = data.get('username')
    msg = data.get('msg')
    # ...
```

**After (Normalized events):**
```python
def _on_message(self, event, data):
    """Handle normalized message event."""
    username = data.get('user')
    msg = data.get('content')
    # Original CyTube data available in data['platform_data'] if needed
    # ...
```

### Event Handler Mapping

Update event registrations:

| Old CyTube Event | New Normalized Event | Handler Update |
|------------------|---------------------|----------------|
| `chatMsg` | `message` | Rename handler, update data access |
| `addUser` | `user_join` | Rename handler, update data access |
| `userLeave` | `user_leave` | Rename handler, update data access |
| `userlist` | `user_list` | Rename handler, update data access |
| `pm` | `pm` | Update data access only |

### Backward Compatibility Layer (Optional)

For gradual migration, add helper constructor:

```python
@classmethod
def from_cytube(cls, domain: str, channel: str, 
                channel_password: Optional[str] = None,
                user: Optional[str] = None,
                password: Optional[str] = None,
                **kwargs):
    """
    Create Bot with CyTube connection (backward compatibility).
    
    Args:
        domain: CyTube server domain
        channel: Channel name
        channel_password: Optional channel password
        user: Optional username
        password: Optional user password
        **kwargs: Additional Bot options
    
    Returns:
        Bot instance configured for CyTube
    
    Example:
        bot = Bot.from_cytube('https://cytu.be', 'mychannel', 
                              user='botname', password='secret')
    """
    from lib.connection import CyTubeConnection
    
    connection = CyTubeConnection(
        domain=domain,
        channel=channel,
        channel_password=channel_password,
        user=user,
        password=password
    )
    
    return cls(connection=connection, **kwargs)
```

## Implementation Steps

1. **Update Bot constructor** (30 min)
   - Change signature to accept ConnectionAdapter
   - Remove socket.io related initialization
   - Update docstrings

2. **Refactor run() method** (45 min)
   - Use `connection.connect()`
   - Use `connection.recv_events()` iterator
   - Update error handling and reconnection

3. **Update message methods** (1 hour)
   - `chat()` → `connection.send_message()`
   - `pm()` → `connection.send_pm()`
   - Remove all other `socket.emit()` calls
   - Update CyTube-specific methods (mark as deprecated or adapt)

4. **Update event handlers** (2 hours)
   - Rename `_on_chatMsg` → `_on_message`
   - Rename `_on_addUser` → `_on_user_join`
   - Update data access (use normalized field names)
   - Keep platform_data access where needed

5. **Remove connection code** (30 min)
   - Delete `get_socket_config()`
   - Delete `connect()`
   - Delete `login()`
   - Remove socket.io imports

6. **Update bot implementations** (1 hour)
   - Update `bot/rosey/rosey.py` to new constructor
   - Update any other bot files
   - Test that bots still work

7. **Update tests** (1.5 hours)
   - Create mock ConnectionAdapter for tests
   - Update all bot tests to use mock
   - Update integration tests
   - Ensure 100% test coverage maintained

8. **Add backward compatibility** (30 min)
   - Add `Bot.from_cytube()` class method
   - Document migration path
   - Add deprecation warnings if desired

## Code Changes

### Key Files to Modify

```
lib/
├── bot.py                   # Main refactoring
├── __init__.py             # Update exports
└── connection/             # Already done in Sorties 1-2

bot/rosey/
└── rosey.py                # Update bot usage

test/
├── test_bot.py             # Update with mock connection
├── test_bot_lifecycle.py   # Update integration tests
└── conftest.py             # Add connection fixtures
```

### Test Fixtures

```python
# test/conftest.py

import pytest
from unittest.mock import AsyncMock
from lib.connection import ConnectionAdapter

@pytest.fixture
def mock_connection():
    """Mock connection adapter for testing."""
    conn = AsyncMock(spec=ConnectionAdapter)
    conn.is_connected = True
    conn.connect = AsyncMock()
    conn.disconnect = AsyncMock()
    conn.send_message = AsyncMock()
    conn.send_pm = AsyncMock()
    conn.on_event = Mock()
    
    # Mock event iterator
    async def mock_recv_events():
        # Return test events
        yield 'message', {'user': 'alice', 'content': 'test'}
    
    conn.recv_events = mock_recv_events
    
    return conn

@pytest.fixture
def bot(mock_connection):
    """Bot instance with mock connection."""
    from lib import Bot
    return Bot(connection=mock_connection)
```

## Migration Guide

### For Bot Developers

**Old Usage:**
```python
from lib import Bot

bot = Bot('https://cytu.be', 'mychannel', 
          user=('botname', 'password'))

await bot.run()
```

**New Usage (Direct):**
```python
from lib import Bot
from lib.connection import CyTubeConnection

connection = CyTubeConnection(
    domain='https://cytu.be',
    channel='mychannel',
    user='botname',
    password='password'
)

bot = Bot(connection=connection)

await bot.run()
```

**New Usage (Helper):**
```python
from lib import Bot

bot = Bot.from_cytube('https://cytu.be', 'mychannel',
                      user='botname', password='password')

await bot.run()
```

### Event Handler Updates

**Old:**
```python
@bot.on('chatMsg')
def handle_chat(event, data):
    user = data['username']
    msg = data['msg']
    print(f"{user}: {msg}")
```

**New:**
```python
@bot.on('message')
def handle_chat(event, data):
    user = data['user']
    msg = data['content']
    print(f"{user}: {msg}")
    
    # Access CyTube-specific data if needed:
    cytube_data = data.get('platform_data', {})
```

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_bot_uses_connection_adapter(mock_connection):
    """Test bot delegates to connection adapter."""
    bot = Bot(connection=mock_connection)
    
    await bot.chat("Hello")
    
    mock_connection.send_message.assert_called_once_with("Hello")


@pytest.mark.asyncio
async def test_bot_run_loop(mock_connection):
    """Test bot event loop."""
    bot = Bot(connection=mock_connection)
    
    # Mock single event then stop
    async def mock_events():
        yield 'message', {'user': 'test', 'content': 'hi'}
        raise KeyboardInterrupt()
    
    mock_connection.recv_events = mock_events
    
    handler_called = False
    
    def handler(event, data):
        nonlocal handler_called
        handler_called = True
        assert data['user'] == 'test'
    
    bot.on('message', handler)
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    
    assert handler_called
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_bot_with_real_cytube():
    """Test bot with real CyTube connection."""
    from lib.connection import CyTubeConnection
    
    connection = CyTubeConnection(
        domain='https://cytu.be',
        channel='test'
    )
    
    bot = Bot(connection=connection)
    
    message_received = False
    
    def on_message(event, data):
        nonlocal message_received
        message_received = True
    
    bot.on('message', on_message)
    
    # Run for 5 seconds
    try:
        await asyncio.wait_for(bot.run(), timeout=5.0)
    except asyncio.TimeoutError:
        pass
    
    assert message_received
```

## Dependencies

**Python Packages:**
- None (uses existing modules)

**Internal Modules:**
- `lib.connection.ConnectionAdapter` (Sortie 1)
- `lib.connection.CyTubeConnection` (Sortie 2)

## Validation

Before moving to Sortie 4:

1. ✅ Bot constructor accepts ConnectionAdapter
2. ✅ No socket.io imports in bot.py
3. ✅ All message methods use connection adapter
4. ✅ Event handlers use normalized events
5. ✅ rosey.py and other bots updated and working
6. ✅ All tests passing
7. ✅ No functionality regressions
8. ✅ Code coverage maintained at current levels

## Risks & Mitigations

**Risk:** Breaking all existing bots  
**Mitigation:** Provide `Bot.from_cytube()` helper for easy migration. Update all bots in same PR.

**Risk:** Normalized events lose platform-specific data  
**Mitigation:** Include `platform_data` field with original event data. Document access patterns.

**Risk:** Performance regression  
**Mitigation:** Benchmark before/after. Connection adapter adds minimal overhead (< 1ms per message).

## Open Questions

1. Should we deprecate direct Bot construction with domain/channel?
   - **Decision:** Yes, but keep `from_cytube()` helper indefinitely for convenience.

2. How to handle CyTube-specific bot methods (playlist control, etc.)?
   - **Decision:** Keep methods, add type check for CyTubeConnection, raise NotImplementedError for other platforms.

3. Should event handler registration change?
   - **Decision:** No, keep `bot.on('event', handler)` pattern. Just update event names.

## Next Steps

After completion, proceed to:
- **Sortie 4:** Create StorageAdapter interface
- **Sortie 5:** Implement SQLiteStorage with Alembic

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 7 - The Divide
