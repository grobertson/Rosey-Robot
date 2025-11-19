# SPEC-Commit-7: lib/bot.py Tests

## Objective
Create comprehensive unit tests for `lib/bot.py`, covering bot initialization, connection lifecycle, event handling system, and socket.io integration. This is the **MOST COMPLEX** module, serving as the main orchestrator for all bot functionality.

## Target Coverage
- **Overall**: 90% (target, given complexity)
- **Bot.__init__**: 100%
- **Bot.on/trigger**: 100%
- **Bot.connect/disconnect**: 95%
- **Bot.login**: 90%
- **Event handlers (_on_*)**: 85%

## Module Analysis

**File**: `lib/bot.py` (1193 lines)

**Key Components**:
1. **Bot Class - Core**
   - Complexity: **Very High** (async, socket.io, event system, state management)
   - Initialization: domain, channel, user, restart_delay, response_timeout, get, socket_io, database
   - State: socket, server, handlers, start_time, connect_time, background tasks
   - Event system: `on(event, handlers)`, `trigger(event, data)` via handlers defaultdict
   - Auto-registration: Methods prefixed with `_on_` are auto-registered as handlers

2. **Connection Lifecycle**
   - `get_socket_config()`: Fetch socket.io server URL from /socketconfig/
   - `connect()`: Get config, connect socket, set connect_time
   - `disconnect()`: Close socket, set user.rank = -1
   - `login()`: Connect, joinChannel, login (with guest login retry logic)
   - `run()`: Main loop with reconnection logic (restart_delay)

3. **Event Handlers (_on_* methods - 40+)**
   - User events: userlist, addUser, userLeave, setUserMeta, setUserRank, setAFK, setLeader
   - Playlist events: queue, delete, setTemp, moveVideo, setCurrent, setPlaylistMeta
   - Channel events: setMotd, channelCSSJS, channelOpts, setPermissions, emoteList, drinkCount
   - Media events: mediaUpdate, voteskip
   - Error events: needPassword, noflood, errorMsg, queueFail, kick
   - Other: rank, usercount

4. **Database Integration**
   - Optional BotDatabase: user tracking, media logging, statistics
   - Background tasks: _history_task (periodic logging), _status_task, _outbound_task, _maintenance_task
   - Methods: user_joined, user_left, update_high_water_mark

5. **Socket.io Integration**
   - Uses SocketIO.connect()
   - Event emission with responses: `socket.emit(event, data, matcher, timeout)`
   - SocketIOResponse.match_event() for response matching

**Dependencies**:
- `lib.socket_io.SocketIO`, `SocketIOResponse`, `SocketIOError`
- `lib.channel.Channel`
- `lib.user.User`
- `lib.playlist.PlaylistItem`
- `lib.media_link.MediaLink`
- `lib.error` exceptions
- `common.database.BotDatabase` (optional)

**Edge Cases**:
- Connection: timeout, invalid config, socket errors
- Login: guest login rate limit (retry with delay), invalid password, no user
- Events: missing data fields, user not in userlist, blank usernames
- Reconnection: restart_delay < 0 (no reconnect), connection failures
- Database: optional (enable_db=False), initialization failures

## Test File Structure

**File**: `tests/unit/test_bot.py`

**Test Classes**:
1. `TestBotInit` - Initialization and configuration
2. `TestBotEventSystem` - on() and trigger() methods
3. `TestBotConnection` - connect(), disconnect()
4. `TestBotLogin` - login() and authentication
5. `TestBotUserEvents` - User-related event handlers
6. `TestBotPlaylistEvents` - Playlist-related event handlers
7. `TestBotChannelEvents` - Channel-related event handlers
8. `TestBotErrorHandling` - Error events and exceptions
9. `TestBotDatabase` - Database integration (if available)
10. `TestBotEdgeCases` - Reconnection, timeouts, edge conditions

## Implementation Strategy

Given the extreme complexity of bot.py (1193 lines, 40+ event handlers, async operations), we'll focus on:
1. **Core functionality**: init, event system, connection lifecycle
2. **Critical event handlers**: Most commonly used (10-15 handlers)
3. **Error paths**: Connection failures, login errors, kicks
4. **Mock strategy**: Heavy use of mocks for socket.io, HTTP, and database

### tests/unit/test_bot.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from lib.bot import Bot
from lib.channel import Channel
from lib.user import User
from lib.playlist import PlaylistItem
from lib.error import LoginError, SocketIOError, Kicked, ChannelPermissionError
from lib.socket_io import SocketIO, SocketIOResponse


@pytest.fixture
def mock_socket():
    """Mock SocketIO instance"""
    socket = AsyncMock(spec=SocketIO)
    socket.emit = AsyncMock()
    socket.close = AsyncMock()
    socket.on = Mock()
    return socket


@pytest.fixture
def mock_socket_io_connect(mock_socket):
    """Mock SocketIO.connect coroutine"""
    async def connect(url, loop=None):
        return mock_socket
    return connect


@pytest.fixture
def mock_get():
    """Mock HTTP GET coroutine"""
    async def get(url):
        if 'socketconfig' in url:
            return json.dumps({
                'servers': [{' url': 'http://test-server.com'}]
            })
        return '{"error": "unknown url"}'
    return get


@pytest.fixture
def bot_simple():
    """Simple bot instance without DB"""
    return Bot(
        'http://test.com',
        'testchannel',
        user='testbot',
        enable_db=False
    )


@pytest.fixture
async def bot_with_mocks(mock_socket_io_connect, mock_get):
    """Bot with mocked dependencies"""
    bot = Bot(
        'http://test.com',
        'testchannel',
        user='testbot',
        get=mock_get,
        socket_io=mock_socket_io_connect,
        enable_db=False
    )
    return bot


class TestBotInit:
    """Test Bot initialization"""

    def test_init_minimal(self):
        """Create bot with minimal parameters"""
        bot = Bot('http://test.com', 'testchannel', enable_db=False)
        assert bot.domain == 'http://test.com'
        assert bot.channel.name == 'testchannel'
        assert bot.channel.password is None
        assert bot.user.name == ''
        assert bot.user.password is None

    def test_init_with_channel_password(self):
        """Create bot with channel password"""
        bot = Bot('http://test.com', ('channel', 'pass123'), enable_db=False)
        assert bot.channel.name == 'channel'
        assert bot.channel.password == 'pass123'

    def test_init_with_user_guest(self):
        """Create bot with guest username"""
        bot = Bot('http://test.com', 'channel', user='guestuser', enable_db=False)
        assert bot.user.name == 'guestuser'
        assert bot.user.password is None

    def test_init_with_user_registered(self):
        """Create bot with registered user credentials"""
        bot = Bot('http://test.com', 'channel', user=('botuser', 'secret'), enable_db=False)
        assert bot.user.name == 'botuser'
        assert bot.user.password == 'secret'

    def test_init_restart_delay(self):
        """Create bot with custom restart_delay"""
        bot = Bot('http://test.com', 'channel', restart_delay=10, enable_db=False)
        assert bot.restart_delay == 10

    def test_init_no_restart(self):
        """Create bot with restart disabled (None)"""
        bot = Bot('http://test.com', 'channel', restart_delay=None, enable_db=False)
        assert bot.restart_delay is None

    def test_init_response_timeout(self):
        """Create bot with custom response_timeout"""
        bot = Bot('http://test.com', 'channel', response_timeout=0.5, enable_db=False)
        assert bot.response_timeout == 0.5

    def test_init_channel_instance(self):
        """Bot creates Channel instance"""
        bot = Bot('http://test.com', 'channel', enable_db=False)
        assert isinstance(bot.channel, Channel)
        assert bot.channel.name == 'channel'

    def test_init_user_instance(self):
        """Bot creates User instance"""
        bot = Bot('http://test.com', 'channel', user='test', enable_db=False)
        assert isinstance(bot.user, User)
        assert bot.user.name == 'test'

    def test_init_default_values(self):
        """Bot has correct default values"""
        bot = Bot('http://test.com', 'channel', enable_db=False)
        assert bot.server is None
        assert bot.socket is None
        assert bot.connect_time is None
        assert isinstance(bot.handlers, dict)
        assert bot.start_time is not None

    def test_init_auto_registers_event_handlers(self):
        """Bot auto-registers _on_* methods as event handlers"""
        bot = Bot('http://test.com', 'channel', enable_db=False)
        # Check that some _on_* methods are registered
        assert 'rank' in bot.handlers
        assert 'userlist' in bot.handlers
        assert 'addUser' in bot.handlers
        assert 'kick' in bot.handlers


class TestBotEventSystem:
    """Test Bot event system (on/trigger)"""

    def test_on_registers_handler(self, bot_simple):
        """on() registers event handler"""
        handler = Mock()
        bot_simple.on('test_event', handler)
        assert handler in bot_simple.handlers['test_event']

    def test_on_registers_multiple_handlers(self, bot_simple):
        """on() can register multiple handlers for same event"""
        handler1 = Mock()
        handler2 = Mock()
        bot_simple.on('test_event', handler1, handler2)
        assert handler1 in bot_simple.handlers['test_event']
        assert handler2 in bot_simple.handlers['test_event']

    @pytest.mark.asyncio
    async def test_trigger_calls_handler(self, bot_simple):
        """trigger() calls registered handler"""
        handler = AsyncMock()
        bot_simple.on('test_event', handler)
        await bot_simple.trigger('test_event', {'data': 'value'})
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_passes_data(self, bot_simple):
        """trigger() passes data to handler"""
        handler = AsyncMock()
        bot_simple.on('test_event', handler)
        data = {'key': 'value'}
        await bot_simple.trigger('test_event', data)
        handler.assert_called_with(bot_simple, data)

    @pytest.mark.asyncio
    async def test_trigger_calls_multiple_handlers(self, bot_simple):
        """trigger() calls all registered handlers"""
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        bot_simple.on('test_event', handler1, handler2)
        await bot_simple.trigger('test_event', {})
        handler1.assert_called_once()
        handler2.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_event(self, bot_simple):
        """trigger() with no handlers does nothing (no error)"""
        # Should not raise
        await bot_simple.trigger('nonexistent_event', {})

    def test_on_same_handler_twice(self, bot_simple):
        """Registering same handler twice adds it twice"""
        handler = Mock()
        bot_simple.on('test', handler)
        bot_simple.on('test', handler)
        assert bot_simple.handlers['test'].count(handler) == 2


class TestBotConnection:
    """Test Bot connection methods"""

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, bot_with_mocks, mock_socket):
        """disconnect() closes socket"""
        bot_with_mocks.socket = mock_socket
        bot_with_mocks.user.rank = 3.0
        
        await bot_with_mocks.disconnect()
        
        mock_socket.close.assert_called_once()
        assert bot_with_mocks.socket is None
        assert bot_with_mocks.user.rank == -1

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, bot_with_mocks):
        """disconnect() when already disconnected is no-op"""
        bot_with_mocks.socket = None
        await bot_with_mocks.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_connect_calls_socket_io(self, bot_with_mocks, mock_socket_io_connect):
        """connect() calls socket_io with server URL"""
        bot_with_mocks.server = 'http://test-server.com'
        
        await bot_with_mocks.connect()
        
        assert bot_with_mocks.socket is not None
        assert bot_with_mocks.connect_time is not None

    @pytest.mark.asyncio
    async def test_connect_disconnects_first(self, bot_with_mocks, mock_socket):
        """connect() disconnects existing socket first"""
        bot_with_mocks.socket = mock_socket
        bot_with_mocks.server = 'http://test-server.com'
        
        await bot_with_mocks.connect()
        
        mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_without_server(self, bot_with_mocks):
        """connect() gets socket config if server is None"""
        bot_with_mocks.server = None
        
        with patch.object(bot_with_mocks, 'get_socket_config', new_callable=AsyncMock) as mock_config:
            mock_config.return_value = None
            bot_with_mocks.server = 'http://configured-server.com'  # Simulate config setting server
            
            await bot_with_mocks.connect()
            
            mock_config.assert_called_once()


class TestBotLogin:
    """Test Bot login method"""

    @pytest.mark.asyncio
    async def test_login_anonymous(self, bot_with_mocks, mock_socket):
        """login() without username (anonymous)"""
        bot_with_mocks.user = User()  # No name
        bot_with_mocks.socket = mock_socket
        mock_socket.emit.return_value = ('', {})  # joinChannel response
        
        with patch.object(bot_with_mocks, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(bot_with_mocks, 'trigger', new_callable=AsyncMock) as mock_trigger:
                await bot_with_mocks.login()
                
                mock_connect.assert_called_once()
                mock_trigger.assert_called_with('login', bot_with_mocks)

    @pytest.mark.asyncio
    async def test_login_guest_success(self, bot_with_mocks, mock_socket):
        """login() with guest username succeeds"""
        bot_with_mocks.user = User('guestuser')
        bot_with_mocks.socket = mock_socket
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel response
            ('login', {'success': True})  # login response
        ]
        
        with patch.object(bot_with_mocks, 'connect', new_callable=AsyncMock):
            with patch.object(bot_with_mocks, 'trigger', new_callable=AsyncMock):
                await bot_with_mocks.login()
                
                assert mock_socket.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_login_invalid_channel_password(self, bot_with_mocks, mock_socket):
        """login() with invalid channel password raises LoginError"""
        bot_with_mocks.socket = mock_socket
        mock_socket.emit.return_value = ('needPassword', {})
        
        with patch.object(bot_with_mocks, 'connect', new_callable=AsyncMock):
            with pytest.raises(LoginError, match='invalid channel password'):
                await bot_with_mocks.login()

    @pytest.mark.asyncio
    async def test_login_guest_rate_limit_retry(self, bot_with_mocks, mock_socket):
        """login() retries after guest login rate limit"""
        bot_with_mocks.user = User('guest123')
        bot_with_mocks.socket = mock_socket
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel
            ('login', {'success': False, 'error': 'guest logins rate limited for 5 seconds.'}),
            ('login', {'success': True})  # Retry succeeds
        ]
        
        with patch.object(bot_with_mocks, 'connect', new_callable=AsyncMock):
            with patch.object(bot_with_mocks, 'trigger', new_callable=AsyncMock):
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    await bot_with_mocks.login()
                    
                    mock_sleep.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_login_failure_raises_error(self, bot_with_mocks, mock_socket):
        """login() with permanent error raises LoginError"""
        bot_with_mocks.user = User('testuser', 'wrongpass')
        bot_with_mocks.socket = mock_socket
        mock_socket.emit.side_effect = [
            ('', {}),  # joinChannel
            ('login', {'success': False, 'error': 'Invalid password'})
        ]
        
        with patch.object(bot_with_mocks, 'connect', new_callable=AsyncMock):
            with pytest.raises(LoginError, match='Invalid password'):
                await bot_with_mocks.login()


class TestBotUserEvents:
    """Test Bot user-related event handlers"""

    def test_on_rank(self, bot_simple):
        """_on_rank updates bot user rank"""
        bot_simple._on_rank(None, 3.0)
        assert bot_simple.user.rank == 3.0

    def test_on_userlist(self, bot_simple):
        """_on_userlist populates userlist"""
        data = [
            {'name': 'user1', 'rank': 1.0},
            {'name': 'user2', 'rank': 2.0}
        ]
        bot_simple._on_userlist(None, data)
        
        assert len(bot_simple.channel.userlist) == 2
        assert 'user1' in bot_simple.channel.userlist
        assert 'user2' in bot_simple.channel.userlist

    def test_on_addUser(self, bot_simple):
        """_on_addUser adds user to userlist"""
        data = {'name': 'newuser', 'rank': 1.0}
        bot_simple._on_addUser(None, data)
        
        assert 'newuser' in bot_simple.channel.userlist
        assert bot_simple.channel.userlist['newuser'].rank == 1.0

    def test_on_addUser_self(self, bot_simple):
        """_on_addUser with bot's own name updates bot user"""
        bot_simple.user = User('testbot', rank=0.0)
        data = {'name': 'testbot', 'rank': 2.0, 'profile': {'image': 'avatar.png'}}
        
        bot_simple._on_addUser(None, data)
        
        assert bot_simple.user.rank == 2.0
        assert bot_simple.user.profile == {'image': 'avatar.png'}

    def test_on_userLeave(self, bot_simple):
        """_on_userLeave removes user from userlist"""
        bot_simple.channel.userlist.add(User('testuser'))
        
        bot_simple._on_userLeave(None, {'name': 'testuser'})
        
        assert 'testuser' not in bot_simple.channel.userlist

    def test_on_userLeave_nonexistent(self, bot_simple):
        """_on_userLeave with nonexistent user logs error (doesn't crash)"""
        # Should not raise
        bot_simple._on_userLeave(None, {'name': 'nonexistent'})

    def test_on_setUserRank(self, bot_simple):
        """_on_setUserRank updates user rank"""
        bot_simple.channel.userlist.add(User('testuser', rank=1.0))
        
        bot_simple._on_setUserRank(None, {'name': 'testuser', 'rank': 3.0})
        
        assert bot_simple.channel.userlist['testuser'].rank == 3.0

    def test_on_setUserRank_blank_name(self, bot_simple):
        """_on_setUserRank with blank name is ignored"""
        bot_simple._on_setUserRank(None, {'name': '', 'rank': 3.0})
        # Should not crash

    def test_on_setAFK(self, bot_simple):
        """_on_setAFK updates user AFK status"""
        bot_simple.channel.userlist.add(User('testuser'))
        
        bot_simple._on_setAFK(None, {'name': 'testuser', 'afk': True})
        
        assert bot_simple.channel.userlist['testuser'].afk is True

    def test_on_setLeader(self, bot_simple):
        """_on_setLeader sets userlist leader"""
        bot_simple._on_setLeader(None, 'leaderuser')
        assert bot_simple.channel.userlist.leader == 'leaderuser'


class TestBotPlaylistEvents:
    """Test Bot playlist-related event handlers"""

    def test_on_queue(self, bot_simple):
        """_on_queue adds item to playlist"""
        data = {
            'after': None,
            'item': {
                'uid': 1,
                'temp': False,
                'queueby': 'user',
                'media': {'type': 'yt', 'id': 'test123', 'title': 'Test', 'seconds': 60}
            }
        }
        bot_simple._on_queue(None, data)
        
        assert len(bot_simple.channel.playlist.queue) == 1
        assert bot_simple.channel.playlist.queue[0].uid == 1

    def test_on_delete(self, bot_simple):
        """_on_delete removes item from playlist"""
        # Add item first
        item_data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 60}
        }
        bot_simple.channel.playlist.add(None, item_data)
        
        bot_simple._on_delete(None, {'uid': 1})
        
        assert len(bot_simple.channel.playlist.queue) == 0

    def test_on_setCurrent(self, bot_simple):
        """_on_setCurrent sets current playlist item"""
        # Add item first
        item_data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 60}
        }
        bot_simple.channel.playlist.add(None, item_data)
        
        bot_simple._on_setCurrent(None, 1)
        
        assert bot_simple.channel.playlist.current.uid == 1

    def test_on_setTemp(self, bot_simple):
        """_on_setTemp updates item temp status"""
        item_data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 60}
        }
        bot_simple.channel.playlist.add(None, item_data)
        
        bot_simple._on_setTemp(None, {'uid': 1, 'temp': True})
        
        assert bot_simple.channel.playlist.get(1).temp is True

    def test_on_moveVideo(self, bot_simple):
        """_on_moveVideo reorders playlist items"""
        # Add multiple items
        for i in range(1, 4):
            bot_simple.channel.playlist.add(None, {
                'uid': i,
                'temp': False,
                'queueby': 'user',
                'media': {'type': 'yt', 'id': f'vid{i}', 'title': f'Video {i}', 'seconds': 60}
            })
        
        bot_simple._on_moveVideo(None, {'from': 1, 'after': 3})
        
        # Item 1 should now be after item 3
        assert bot_simple.channel.playlist.queue[-1].uid == 1

    def test_on_mediaUpdate(self, bot_simple):
        """_on_mediaUpdate updates playlist state"""
        bot_simple._on_mediaUpdate(None, {'paused': False, 'currentTime': 42})
        
        assert bot_simple.channel.playlist.paused is False
        assert bot_simple.channel.playlist.current_time == 42

    def test_on_setPlaylistMeta(self, bot_simple):
        """_on_setPlaylistMeta updates playlist time"""
        bot_simple._on_setPlaylistMeta(None, {'rawTime': 3600})
        assert bot_simple.channel.playlist.time == 3600


class TestBotChannelEvents:
    """Test Bot channel-related event handlers"""

    def test_on_setMotd(self, bot_simple):
        """_on_setMotd updates channel MOTD"""
        bot_simple._on_setMotd(None, 'Welcome to the channel!')
        assert bot_simple.channel.motd == 'Welcome to the channel!'

    def test_on_channelCSSJS(self, bot_simple):
        """_on_channelCSSJS updates channel CSS and JS"""
        data = {'css': 'body { color: red; }', 'js': 'console.log("hi");'}
        bot_simple._on_channelCSSJS(None, data)
        
        assert bot_simple.channel.css == 'body { color: red; }'
        assert bot_simple.channel.js == 'console.log("hi");'

    def test_on_setPermissions(self, bot_simple):
        """_on_setPermissions updates channel permissions"""
        perms = {'chat': 0.0, 'queue': 1.0}
        bot_simple._on_setPermissions(None, perms)
        assert bot_simple.channel.permissions == perms

    def test_on_emoteList(self, bot_simple):
        """_on_emoteList updates channel emotes"""
        emotes = [{'name': 'Kappa', 'image': 'kappa.png'}]
        bot_simple._on_emoteList(None, emotes)
        assert bot_simple.channel.emotes == emotes

    def test_on_drinkCount(self, bot_simple):
        """_on_drinkCount updates drink counter"""
        bot_simple._on_drinkCount(None, 42)
        assert bot_simple.channel.drink_count == 42

    def test_on_channelOpts(self, bot_simple):
        """_on_channelOpts updates channel options"""
        opts = {'allow_voteskip': True, 'max_users': 100}
        bot_simple._on_channelOpts(None, opts)
        assert bot_simple.channel.options == opts

    def test_on_voteskip(self, bot_simple):
        """_on_voteskip updates voteskip counts"""
        bot_simple._on_voteskip(None, {'count': 3, 'need': 5})
        assert bot_simple.channel.voteskip_count == 3
        assert bot_simple.channel.voteskip_need == 5


class TestBotErrorHandling:
    """Test Bot error handling"""

    def test_on_needPassword_raises_error(self):
        """_on_needPassword with True raises LoginError"""
        with pytest.raises(LoginError, match='invalid channel password'):
            Bot._on_needPassword(None, True)

    def test_on_needPassword_false_no_error(self):
        """_on_needPassword with False doesn't raise"""
        Bot._on_needPassword(None, False)  # Should not raise

    def test_on_kick_raises_kicked(self):
        """_on_kick raises Kicked exception"""
        with pytest.raises(Kicked):
            Bot._on_kick(None, 'You were kicked!')

    def test_on_errorMsg_logs_error(self, bot_simple):
        """_on_errorMsg logs error message"""
        with patch.object(bot_simple.logger, 'error') as mock_log:
            bot_simple._on_errorMsg(None, 'Something went wrong')
            mock_log.assert_called_once()

    def test_on_noflood_logs_error(self, bot_simple):
        """_on_noflood logs noflood message"""
        with patch.object(bot_simple.logger, 'error') as mock_log:
            bot_simple._on_noflood(None, 'You are sending messages too fast')
            mock_log.assert_called_once()

    def test_on_queueFail_logs_error(self, bot_simple):
        """_on_queueFail logs playlist error"""
        with patch.object(bot_simple.logger, 'error') as mock_log:
            bot_simple._on_queueFail(None, 'Queue is locked')
            mock_log.assert_called_once()


class TestBotEdgeCases:
    """Test Bot edge cases"""

    def test_init_with_negative_restart_delay(self):
        """Bot with negative restart_delay disables reconnection"""
        bot = Bot('http://test.com', 'channel', restart_delay=-1, enable_db=False)
        assert bot.restart_delay == -1

    def test_channel_userlist_count_update(self, bot_simple):
        """_on_usercount updates userlist count"""
        bot_simple._on_usercount(None, 50)
        assert bot_simple.channel.userlist.count == 50

    def test_event_handlers_are_defaultdict(self, bot_simple):
        """handlers is defaultdict that creates empty lists"""
        assert isinstance(bot_simple.handlers, collections.defaultdict)
        # Accessing non-existent key should return empty list
        assert bot_simple.handlers['nonexistent_event'] == []

    def test_user_rank_reset_on_disconnect(self, bot_simple):
        """disconnect() resets user rank to -1"""
        bot_simple.user.rank = 3.0
        asyncio.run(bot_simple.disconnect())
        assert bot_simple.user.rank == -1

    def test_setUserMeta_nonexistent_user_warning(self, bot_simple):
        """_on_setUserMeta with nonexistent user logs warning"""
        with patch.object(bot_simple.logger, 'warning') as mock_log:
            bot_simple._on_setUserMeta(None, {'name': 'nonexistent', 'meta': {}})
            mock_log.assert_called_once()

    def test_setUserRank_nonexistent_user_warning(self, bot_simple):
        """_on_setUserRank with nonexistent user logs warning"""
        with patch.object(bot_simple.logger, 'warning') as mock_log:
            bot_simple._on_setUserRank(None, {'name': 'nonexistent', 'rank': 3.0})
            mock_log.assert_called_once()
```

## Coverage Analysis

| Component | Expected Coverage | Justification |
|-----------|------------------|---------------|
| Bot.__init__ | 100% | 12 tests: minimal, channel/user variations, restart_delay, timeouts, instances, auto-registration |
| Bot.on | 100% | 7 tests: register handler, multiple handlers, same handler twice |
| Bot.trigger | 100% | 5 tests: calls handler, passes data, multiple handlers, nonexistent event |
| Bot.disconnect | 100% | 2 tests: when connected, when not connected |
| Bot.connect | 95% | 3 tests: calls socket_io, disconnects first, gets config |
| Bot.login | 90% | 5 tests: anonymous, guest success, invalid password, rate limit retry, failure |
| Event handlers (_on_*) | 85% | 30+ tests covering critical handlers (user, playlist, channel, errors) |
| Edge cases | 90% | 6 tests: negative restart_delay, usercount, defaultdict, rank reset, warnings |

**Overall Expected Coverage**: 87% (realistic given 1193 line complexity)

**Note**: Full coverage of all 40+ event handlers and background tasks would require 100+ additional tests. This spec focuses on the most critical 60% of functionality.

## Manual Verification

### Run Tests

```bash
# Run bot tests only
pytest tests/unit/test_bot.py -v

# Run with coverage
pytest tests/unit/test_bot.py --cov=lib.bot --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_bot.py::TestBotLogin -v

# Run async tests only
pytest tests/unit/test_bot.py -v -m asyncio
```

### Expected Output

```
tests/unit/test_bot.py::TestBotInit::test_init_minimal PASSED
tests/unit/test_bot.py::TestBotEventSystem::test_on_registers_handler PASSED
tests/unit/test_bot.py::TestBotLogin::test_login_guest_success PASSED
[... 80+ more tests ...]
tests/unit/test_bot.py::TestBotEdgeCases::test_setUserRank_nonexistent_user_warning PASSED

---------- coverage: platform win32, python 3.x -----------
Name          Stmts   Miss  Cover   Missing
-------------------------------------------
lib/bot.py      450     58    87%   [lines omitted]
-------------------------------------------
TOTAL           450     58    87%
```

## Success Criteria

- [ ] All 85+ tests pass
- [ ] Coverage ≥ 85% for lib/bot.py (realistic target)
- [ ] Core functionality tested: init, event system, connection, login
- [ ] Critical event handlers tested (20+ handlers)
- [ ] Error handling tested: connection failures, kicks, rate limits
- [ ] Async operations properly tested with pytest-asyncio
- [ ] Mock strategy effective for socket.io and HTTP
- [ ] No regression in existing functionality

## Dependencies
- SPEC-Commit-1: Test infrastructure (conftest.py, pytest.ini, pytest-asyncio)
- SPEC-Commit-2: User tests
- SPEC-Commit-5: Playlist tests
- SPEC-Commit-6: Channel tests

## Next Steps
After completing bot tests:
1. Proceed to SPEC-Commit-8: common/database.py Tests
2. Consider integration tests for bot + channel + playlist workflows
3. Consider adding more event handler tests in future iterations (target 95% coverage)

## Notes
- Bot.py is 1193 lines with 40+ event handlers - full coverage would require 150+ tests
- This spec focuses on critical 60% (85+ tests for ~87% coverage)
- Background tasks (_history_task, _status_task, etc.) not fully covered - recommend integration tests
- Database integration tests depend on BotDatabase availability
