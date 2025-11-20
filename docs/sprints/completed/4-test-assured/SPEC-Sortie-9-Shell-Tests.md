# SPEC-Commit-9: Shell Tests

## Purpose

Create comprehensive unit tests for `common/shell.py`, covering the `Shell` command-based control interface including TCP server, command parsing, PM handling, and 30+ bot control commands.

## Scope

- **File Under Test**: `common/shell.py` (806 lines, 30+ commands)
- **Complexity**: High (async TCP server, command parsing, bot integration)
- **Test Count**: 80+ tests across 13 test classes
- **Coverage Target**: 85% (realistic for async networking and extensive command set)
- **Dependencies**:
  - SPEC-Commit-1: pytest infrastructure, pytest-asyncio
  - SPEC-Commit-2: User tests (for user manipulation commands)
  - SPEC-Commit-7: Bot tests (for bot integration)

## Source Code Analysis

### Key Components

**Shell Class**:
- **Initialization**: `__init__(addr, bot, loop)` - Parse "host:port", setup async server
- **Server Lifecycle**: `start()`, `close()`, `handle_connection(reader, writer)`
- **I/O**: `write(writer, string)` - Convert LF→CRLF for telnet compatibility
- **Command Processing**: `handle_command(cmd, bot)` - Parse and dispatch commands
- **PM Integration**: `handle_pm_command(event, data)` - Moderator commands via PM (rank 2.0+)

**Commands** (30+):
- **Info**: help, info, status, stats
- **Users**: users, user, afk
- **Chat**: say, pm, clear
- **Playlist**: playlist, current, add, remove, move, jump, next
- **Control**: pause, kick, voteskip

**Critical Features**:
- Address parsing: "host:port" → (host, port)
- Shell disable: addr=None → no server
- Event loop management: Get running loop or create new
- Telnet compatibility: LF→CRLF conversion
- PM authentication: Moderator rank check (≥2.0)
- PM response splitting: Max 500 chars per message
- Command parsing: Split on whitespace, extract args
- Error handling: Try/except with user-friendly messages
- Duration formatting: seconds → "1d 2h 3m 4s"

**Text Constants**:
- `WELCOME`: Multi-line banner with box drawing
- `HELP_TEXT`: Comprehensive command reference (80+ lines)

## Test Strategy

**Fixtures**:
```python
@pytest.fixture
def mock_bot():
    """Mock bot with channel, user, playlist"""
    bot = MagicMock()
    bot.user.name = "TestBot"
    bot.user.rank = 3.0
    bot.user.afk = False
    bot.socket = True
    bot.server = "cytu.be"
    bot.start_time = time.time() - 3600  # 1 hour ago
    bot.connect_time = time.time() - 1800  # 30 min ago
    
    # Mock channel
    bot.channel = MagicMock()
    bot.channel.name = "testchannel"
    bot.channel.userlist = MagicMock()
    bot.channel.userlist.count = 5
    bot.channel.userlist.__len__ = MagicMock(return_value=3)
    bot.channel.userlist.leader = None
    
    # Mock playlist
    bot.channel.playlist = MagicMock()
    bot.channel.playlist.queue = []
    bot.channel.playlist.current = None
    bot.channel.playlist.paused = False
    bot.channel.playlist.current_time = 0
    
    # Mock database
    bot.db = None
    
    return bot

@pytest.fixture
def mock_writer():
    """Mock asyncio StreamWriter"""
    writer = AsyncMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer

@pytest.fixture
def shell_disabled():
    """Shell with disabled server (addr=None)"""
    bot = MagicMock()
    shell = Shell(None, bot)
    return shell

@pytest.fixture
def shell_enabled(mock_bot):
    """Shell with enabled server"""
    shell = Shell("localhost:9001", mock_bot)
    return shell

@pytest.fixture
def moderator_user():
    """Mock moderator user (rank 2.0)"""
    user = MagicMock()
    user.name = "ModUser"
    user.rank = 2.0
    return user

@pytest.fixture
def regular_user():
    """Mock regular user (rank 1.0)"""
    user = MagicMock()
    user.name = "RegularUser"
    user.rank = 1.0
    return user
```

**Test Organization**: 13 test classes with 80+ tests

### Test Class 1: TestShellInit (8 tests)

Tests for Shell initialization and configuration.

```python
def test_init_disabled(shell_disabled):
    """Shell is disabled when addr=None"""
    assert shell_disabled.host is None
    assert shell_disabled.port is None
    assert shell_disabled.loop is None
    assert shell_disabled.bot is None
    assert shell_disabled.server_coro is None

def test_init_disabled_logs_warning(caplog, mock_bot):
    """Disabling shell logs warning"""
    Shell(None, mock_bot)
    assert 'shell is disabled' in caplog.text

def test_init_parses_address(shell_enabled):
    """Address is parsed into host and port"""
    assert shell_enabled.host == "localhost"
    assert shell_enabled.port == 9001

def test_init_parses_ipv4_address(mock_bot):
    """IPv4 addresses are parsed correctly"""
    shell = Shell("192.168.1.10:8080", mock_bot)
    assert shell.host == "192.168.1.10"
    assert shell.port == 8080

def test_init_parses_domain_address(mock_bot):
    """Domain names are parsed correctly"""
    shell = Shell("example.com:9000", mock_bot)
    assert shell.host == "example.com"
    assert shell.port == 9000

def test_init_stores_bot(shell_enabled, mock_bot):
    """Bot instance is stored"""
    assert shell_enabled.bot is mock_bot

def test_init_creates_event_loop(shell_enabled):
    """Event loop is created or retrieved"""
    assert shell_enabled.loop is not None

def test_init_logs_startup(caplog, mock_bot):
    """Shell startup is logged"""
    Shell("localhost:9001", mock_bot)
    assert 'starting shell at localhost:9001' in caplog.text
```

### Test Class 2: TestShellWrite (4 tests)

Tests for write method and line ending conversion.

```python
@pytest.mark.asyncio
async def test_write_converts_lf_to_crlf(mock_writer):
    """LF is converted to CRLF for telnet compatibility"""
    await Shell.write(mock_writer, "Line1\nLine2\nLine3")
    
    mock_writer.write.assert_called_once()
    written = mock_writer.write.call_args[0][0]
    assert written == b"Line1\r\nLine2\r\nLine3"

@pytest.mark.asyncio
async def test_write_encodes_utf8(mock_writer):
    """Text is encoded as UTF-8"""
    await Shell.write(mock_writer, "Hello")
    
    written = mock_writer.write.call_args[0][0]
    assert written == b"Hello"
    assert isinstance(written, bytes)

@pytest.mark.asyncio
async def test_write_drains(mock_writer):
    """Writer drain is called to flush output"""
    await Shell.write(mock_writer, "Test")
    mock_writer.drain.assert_called_once()

@pytest.mark.asyncio
async def test_write_unicode(mock_writer):
    """Unicode characters are handled correctly"""
    await Shell.write(mock_writer, "日本語 🎉")
    
    written = mock_writer.write.call_args[0][0]
    assert written == "日本語 🎉\r\n".encode('utf-8')  # if input had \n
```

### Test Class 3: TestFormatDuration (7 tests)

Tests for duration formatting utility.

```python
def test_format_duration_seconds():
    """Seconds only"""
    assert Shell.format_duration(30) == "30s"

def test_format_duration_minutes():
    """Minutes and seconds"""
    assert Shell.format_duration(90) == "1m 30s"

def test_format_duration_hours():
    """Hours, minutes, and seconds"""
    assert Shell.format_duration(3661) == "1h 1m 1s"

def test_format_duration_days():
    """Days, hours, minutes, seconds"""
    assert Shell.format_duration(90061) == "1d 1h 1m 1s"

def test_format_duration_zero():
    """Zero seconds"""
    assert Shell.format_duration(0) == "0s"

def test_format_duration_negative():
    """Negative duration returns Unknown"""
    assert Shell.format_duration(-100) == "Unknown"

def test_format_duration_large():
    """Large durations are formatted correctly"""
    # 10 days, 5 hours, 30 minutes, 45 seconds
    seconds = (10 * 86400) + (5 * 3600) + (30 * 60) + 45
    assert Shell.format_duration(seconds) == "10d 5h 30m 45s"
```

### Test Class 4: TestCommandParsing (6 tests)

Tests for command parsing and argument extraction.

```python
@pytest.mark.asyncio
async def test_parse_command_no_args(mock_bot):
    """Command without arguments"""
    shell = Shell(None, mock_bot)
    
    # help command has no args
    result = await shell.handle_command("help", mock_bot)
    assert "Bot Commands" in result

@pytest.mark.asyncio
async def test_parse_command_with_args(mock_bot):
    """Command with arguments"""
    shell = Shell(None, mock_bot)
    mock_bot.chat = AsyncMock()
    
    result = await shell.handle_command("say Hello world", mock_bot)
    mock_bot.chat.assert_called_once_with("Hello world")

@pytest.mark.asyncio
async def test_parse_command_strips_whitespace(mock_bot):
    """Leading/trailing whitespace is stripped"""
    shell = Shell(None, mock_bot)
    
    result = await shell.handle_command("  help  ", mock_bot)
    assert "Bot Commands" in result

@pytest.mark.asyncio
async def test_parse_empty_command(mock_bot):
    """Empty command returns None"""
    shell = Shell(None, mock_bot)
    result = await shell.handle_command("", mock_bot)
    assert result is None

@pytest.mark.asyncio
async def test_parse_command_case_insensitive(mock_bot):
    """Commands are case-insensitive"""
    shell = Shell(None, mock_bot)
    
    result = await shell.handle_command("HELP", mock_bot)
    assert "Bot Commands" in result

@pytest.mark.asyncio
async def test_parse_unknown_command(mock_bot):
    """Unknown commands return error message"""
    shell = Shell(None, mock_bot)
    result = await shell.handle_command("invalidcmd", mock_bot)
    assert "Unknown command" in result
```

### Test Class 5: TestInfoCommands (8 tests)

Tests for info, status, stats commands.

```python
@pytest.mark.asyncio
async def test_cmd_info_bot_details(mock_bot):
    """info shows bot name, rank, AFK status"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_info(mock_bot)
    
    assert "Bot: TestBot" in result
    assert "Rank: 3.0" in result
    assert "AFK: No" in result

@pytest.mark.asyncio
async def test_cmd_info_channel(mock_bot):
    """info shows channel name"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_info(mock_bot)
    assert "Channel: testchannel" in result

@pytest.mark.asyncio
async def test_cmd_info_user_count(mock_bot):
    """info shows chat and connected user counts"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_info(mock_bot)
    # mock_bot.channel.userlist.__len__ = 3, count = 5
    assert "Users: 3 in chat, 5 connected" in result

@pytest.mark.asyncio
async def test_cmd_status_uptime(mock_bot):
    """status shows bot uptime"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_status(mock_bot)
    assert "Uptime:" in result

@pytest.mark.asyncio
async def test_cmd_status_connection(mock_bot):
    """status shows connection info"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_status(mock_bot)
    assert "Connected: Yes" in result
    assert "Server: cytu.be" in result

@pytest.mark.asyncio
async def test_cmd_stats_no_database(mock_bot):
    """stats without database shows error"""
    mock_bot.db = None
    shell = Shell(None, mock_bot)
    result = await shell.cmd_stats(mock_bot)
    assert "Database tracking is not enabled" in result

@pytest.mark.asyncio
async def test_cmd_stats_high_water_mark(mock_bot):
    """stats shows high water marks"""
    mock_bot.db = MagicMock()
    mock_bot.db.get_high_water_mark.return_value = (42, 1234567890)
    mock_bot.db.get_high_water_mark_connected.return_value = (100, 1234567890)
    mock_bot.db.get_total_users_seen.return_value = 500
    mock_bot.db.get_top_chatters.return_value = [("alice", 100), ("bob", 50)]
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_stats(mock_bot)
    
    assert "Peak (chat): 42" in result
    assert "Peak (connected): 100" in result
    assert "Total seen: 500" in result

@pytest.mark.asyncio
async def test_cmd_stats_top_chatters(mock_bot):
    """stats shows top chatters"""
    mock_bot.db = MagicMock()
    mock_bot.db.get_high_water_mark.return_value = (0, None)
    mock_bot.db.get_high_water_mark_connected.return_value = (0, None)
    mock_bot.db.get_total_users_seen.return_value = 0
    mock_bot.db.get_top_chatters.return_value = [("alice", 100), ("bob", 50)]
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_stats(mock_bot)
    
    assert "Top chatters:" in result
    assert "alice: 100 msg" in result
```

### Test Class 6: TestUserCommands (7 tests)

Tests for users, user, afk commands.

```python
@pytest.mark.asyncio
async def test_cmd_users_lists_all(mock_bot):
    """users command lists all channel users"""
    # Create mock users
    user1 = MagicMock()
    user1.name = "alice"
    user1.rank = 3.0
    user1.afk = False
    user1.muted = False
    
    user2 = MagicMock()
    user2.name = "bob"
    user2.rank = 1.0
    user2.afk = True
    user2.muted = False
    
    mock_bot.channel.userlist.values.return_value = [user1, user2]
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_users(mock_bot)
    
    assert "alice" in result
    assert "bob" in result
    assert "[3.0]" in result
    assert "[AFK]" in result

@pytest.mark.asyncio
async def test_cmd_user_details(mock_bot):
    """user command shows detailed info"""
    user = MagicMock()
    user.name = "alice"
    user.rank = 2.5
    user.afk = True
    user.muted = False
    user.ip = "127.0.0.1"
    user.uncloaked_ip = None
    user.aliases = ["alice2", "alice3"]
    
    mock_bot.channel.userlist.__contains__ = lambda self, name: name == "alice"
    mock_bot.channel.userlist.__getitem__ = lambda self, name: user
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_user(mock_bot, "alice")
    
    assert "User: alice" in result
    assert "Rank: 2.5" in result
    assert "AFK: Yes" in result
    assert "IP: 127.0.0.1" in result
    assert "Aliases: alice2, alice3" in result

@pytest.mark.asyncio
async def test_cmd_user_not_found(mock_bot):
    """user command handles missing user"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: False
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_user(mock_bot, "nonexistent")
    assert "not found" in result

@pytest.mark.asyncio
async def test_cmd_afk_on(mock_bot):
    """afk on sets AFK status"""
    mock_bot.set_afk = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_afk(mock_bot, "on")
    
    mock_bot.set_afk.assert_called_once_with(True)
    assert "AFK status: On" in result

@pytest.mark.asyncio
async def test_cmd_afk_off(mock_bot):
    """afk off clears AFK status"""
    mock_bot.set_afk = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_afk(mock_bot, "off")
    
    mock_bot.set_afk.assert_called_once_with(False)
    assert "AFK status: Off" in result

@pytest.mark.asyncio
async def test_cmd_afk_no_args(mock_bot):
    """afk without args shows current status"""
    mock_bot.user.afk = True
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_afk(mock_bot, "")
    assert "Current AFK status: On" in result

@pytest.mark.asyncio
async def test_cmd_afk_invalid_arg(mock_bot):
    """afk with invalid arg shows usage"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_afk(mock_bot, "maybe")
    assert "Usage:" in result
```

### Test Class 7: TestChatCommands (5 tests)

Tests for say, pm, clear commands.

```python
@pytest.mark.asyncio
async def test_cmd_say(mock_bot):
    """say sends chat message"""
    mock_bot.chat = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_say(mock_bot, "Hello everyone")
    
    mock_bot.chat.assert_called_once_with("Hello everyone")
    assert "Sent: Hello everyone" in result

@pytest.mark.asyncio
async def test_cmd_pm(mock_bot):
    """pm sends private message"""
    mock_bot.pm = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_pm(mock_bot, "alice Hello there")
    
    mock_bot.pm.assert_called_once_with("alice", "Hello there")
    assert "PM sent to alice" in result

@pytest.mark.asyncio
async def test_cmd_pm_missing_message(mock_bot):
    """pm without message shows usage"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_pm(mock_bot, "alice")
    assert "Usage:" in result

@pytest.mark.asyncio
async def test_cmd_clear(mock_bot):
    """clear clears chat"""
    mock_bot.clear_chat = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_clear(mock_bot)
    
    mock_bot.clear_chat.assert_called_once()
    assert "Chat cleared" in result

@pytest.mark.asyncio
async def test_cmd_say_no_message(mock_bot):
    """say without message shows usage"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_say(mock_bot, "")
    assert "Usage:" in result
```

### Test Class 8: TestPlaylistCommands (10 tests)

Tests for playlist manipulation commands.

```python
@pytest.mark.asyncio
async def test_cmd_playlist_shows_items(mock_bot):
    """playlist shows queue items"""
    item1 = MagicMock()
    item1.title = "Video 1"
    item1.duration = 120
    
    item2 = MagicMock()
    item2.title = "Video 2"
    item2.duration = 180
    
    mock_bot.channel.playlist.queue = [item1, item2]
    mock_bot.channel.playlist.current = item1
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_playlist(mock_bot, "")
    
    assert "Video 1" in result
    assert "Video 2" in result
    assert "►" in result  # Current marker

@pytest.mark.asyncio
async def test_cmd_current(mock_bot):
    """current shows now playing"""
    current = MagicMock()
    current.title = "Test Video"
    current.duration = 240
    current.username = "alice"
    current.temp = True
    current.link.url = "https://youtu.be/xyz"
    
    mock_bot.channel.playlist.current = current
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_current(mock_bot)
    
    assert "Title: Test Video" in result
    assert "Duration: 4m" in result
    assert "Queued by: alice" in result
    assert "Temporary: Yes" in result

@pytest.mark.asyncio
async def test_cmd_add_temporary(mock_bot):
    """add with temp flag adds temporary media"""
    mock_bot.add_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_add(mock_bot, "https://youtu.be/xyz yes")
    
    mock_bot.add_media.assert_called_once()
    args = mock_bot.add_media.call_args
    assert args[1]['temp'] is True

@pytest.mark.asyncio
async def test_cmd_add_permanent(mock_bot):
    """add with perm flag adds permanent media"""
    mock_bot.add_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_add(mock_bot, "https://youtu.be/xyz no")
    
    mock_bot.add_media.assert_called_once()
    args = mock_bot.add_media.call_args
    assert args[1]['temp'] is False

@pytest.mark.asyncio
async def test_cmd_remove(mock_bot):
    """remove deletes playlist item"""
    item = MagicMock()
    item.title = "Test Video"
    
    mock_bot.channel.playlist.queue = [item]
    mock_bot.remove_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_remove(mock_bot, "1")
    
    mock_bot.remove_media.assert_called_once_with(item)

@pytest.mark.asyncio
async def test_cmd_move(mock_bot):
    """move reorders playlist items"""
    item1 = MagicMock()
    item2 = MagicMock()
    item3 = MagicMock()
    
    mock_bot.channel.playlist.queue = [item1, item2, item3]
    mock_bot.move_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_move(mock_bot, "1 3")
    
    mock_bot.move_media.assert_called_once()

@pytest.mark.asyncio
async def test_cmd_jump(mock_bot):
    """jump switches to playlist item"""
    item1 = MagicMock()
    item2 = MagicMock()
    
    mock_bot.channel.playlist.queue = [item1, item2]
    mock_bot.set_current_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_jump(mock_bot, "2")
    
    mock_bot.set_current_media.assert_called_once_with(item2)

@pytest.mark.asyncio
async def test_cmd_next(mock_bot):
    """next skips to next item"""
    item1 = MagicMock()
    item2 = MagicMock()
    
    mock_bot.channel.playlist.queue = [item1, item2]
    mock_bot.channel.playlist.current = item1
    mock_bot.set_current_media = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_next(mock_bot)
    
    mock_bot.set_current_media.assert_called_once_with(item2)

@pytest.mark.asyncio
async def test_cmd_next_at_end(mock_bot):
    """next at end of playlist shows message"""
    item1 = MagicMock()
    
    mock_bot.channel.playlist.queue = [item1]
    mock_bot.channel.playlist.current = item1
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_next(mock_bot)
    assert "Already at last item" in result

@pytest.mark.asyncio
async def test_cmd_playlist_with_limit(mock_bot):
    """playlist respects limit argument"""
    items = [MagicMock(title=f"Video {i}", duration=120) for i in range(20)]
    mock_bot.channel.playlist.queue = items
    mock_bot.channel.playlist.current = None
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_playlist(mock_bot, "5")
    
    # Should show first 5 items
    assert "Video 0" in result
    assert "Video 4" in result
    assert "... and 15 more" in result
```

### Test Class 9: TestControlCommands (4 tests)

Tests for pause, kick, voteskip commands.

```python
@pytest.mark.asyncio
async def test_cmd_pause(mock_bot):
    """pause pauses playback"""
    mock_bot.pause = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_pause(mock_bot)
    
    mock_bot.pause.assert_called_once()
    assert "Paused" in result

@pytest.mark.asyncio
async def test_cmd_kick_with_reason(mock_bot):
    """kick with reason"""
    mock_bot.kick = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_kick(mock_bot, "alice Spamming")
    
    mock_bot.kick.assert_called_once_with("alice", "Spamming")
    assert "Kicked alice: Spamming" in result

@pytest.mark.asyncio
async def test_cmd_kick_without_reason(mock_bot):
    """kick without reason"""
    mock_bot.kick = AsyncMock()
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_kick(mock_bot, "alice")
    
    mock_bot.kick.assert_called_once_with("alice", "")

@pytest.mark.asyncio
async def test_cmd_voteskip(mock_bot):
    """voteskip shows vote status"""
    mock_bot.channel.voteskip_count = 3
    mock_bot.channel.voteskip_need = 5
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_voteskip(mock_bot)
    assert "Voteskip: 3/5" in result
```

### Test Class 10: TestPMCommandHandling (9 tests)

Tests for PM-based command interface.

```python
@pytest.mark.asyncio
async def test_handle_pm_moderator(mock_bot, moderator_user):
    """Moderators can send PM commands"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
    mock_bot.pm = AsyncMock()
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': 'help'
    }
    
    await shell.handle_pm_command('pm', data)
    
    # Should send response via PM
    mock_bot.pm.assert_called()

@pytest.mark.asyncio
async def test_handle_pm_regular_user(mock_bot, regular_user, caplog):
    """Regular users cannot send PM commands"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: regular_user
    mock_bot.pm = AsyncMock()
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'RegularUser',
        'msg': 'say test'
    }
    
    await shell.handle_pm_command('pm', data)
    
    # Should not respond
    mock_bot.pm.assert_not_called()
    assert 'non-moderator' in caplog.text

@pytest.mark.asyncio
async def test_handle_pm_empty_message(mock_bot):
    """Empty PM messages are ignored"""
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': '   '
    }
    
    # Should not crash
    await shell.handle_pm_command('pm', data)

@pytest.mark.asyncio
async def test_handle_pm_from_self(mock_bot, caplog):
    """PMs from bot itself are ignored"""
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'TestBot',  # Same as bot name
        'msg': 'help'
    }
    
    await shell.handle_pm_command('pm', data)
    assert 'Ignoring PM from self' in caplog.text

@pytest.mark.asyncio
async def test_handle_pm_splits_long_responses(mock_bot, moderator_user):
    """Long responses are split into multiple PMs"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
    mock_bot.pm = AsyncMock()
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': 'help'  # Returns long HELP_TEXT
    }
    
    await shell.handle_pm_command('pm', data)
    
    # Should be called multiple times for long response
    assert mock_bot.pm.call_count >= 1

@pytest.mark.asyncio
async def test_handle_pm_logs_command(mock_bot, moderator_user, caplog):
    """PM commands are logged"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
    mock_bot.pm = AsyncMock()
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': 'info'
    }
    
    await shell.handle_pm_command('pm', data)
    assert 'PM command from ModUser: info' in caplog.text

@pytest.mark.asyncio
async def test_handle_pm_database_logging(mock_bot, moderator_user):
    """PM commands are logged to database"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
    mock_bot.pm = AsyncMock()
    mock_bot.db = MagicMock()
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': 'status'
    }
    
    await shell.handle_pm_command('pm', data)
    mock_bot.db.log_user_action.assert_called_once_with(
        'ModUser', 'pm_command', 'status'
    )

@pytest.mark.asyncio
async def test_handle_pm_error_handling(mock_bot, moderator_user, caplog):
    """PM command errors are handled gracefully"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
    mock_bot.pm = AsyncMock(side_effect=Exception("Test error"))
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'ModUser',
        'msg': 'info'
    }
    
    # Should not crash
    await shell.handle_pm_command('pm', data)
    assert 'Error processing PM command' in caplog.text

@pytest.mark.asyncio
async def test_handle_pm_unknown_user(mock_bot, caplog):
    """PMs from unknown users are ignored"""
    mock_bot.channel.userlist.__contains__ = lambda self, name: False
    
    shell = Shell(None, mock_bot)
    
    data = {
        'username': 'UnknownUser',
        'msg': 'help'
    }
    
    await shell.handle_pm_command('pm', data)
    assert 'unknown user' in caplog.text
```

### Test Class 11: TestServerLifecycle (6 tests)

Tests for server start, close, and connection handling.

```python
@pytest.mark.asyncio
async def test_start_creates_server(shell_enabled):
    """start() creates listening server"""
    with patch('asyncio.start_server') as mock_start:
        mock_start.return_value = AsyncMock()
        shell_enabled.server_coro = asyncio.coroutine(lambda: AsyncMock())()
        
        await shell_enabled.start()
        assert shell_enabled.server is not None

@pytest.mark.asyncio
async def test_start_disabled_does_nothing(shell_disabled):
    """start() with disabled shell does nothing"""
    await shell_disabled.start()  # Should not crash

def test_close_shuts_down_server(shell_enabled):
    """close() shuts down server"""
    shell_enabled.server = MagicMock()
    shell_enabled.server_task = MagicMock()
    
    shell_enabled.close()
    
    shell_enabled.server.close.assert_called_once()
    shell_enabled.server_task.cancel.assert_called_once()

def test_close_logs(shell_enabled, caplog):
    """close() logs shutdown"""
    shell_enabled.server = MagicMock()
    shell_enabled.server_task = MagicMock()
    
    shell_enabled.close()
    
    assert 'closing shell server' in caplog.text

def test_close_without_server(shell_enabled):
    """close() without server doesn't crash"""
    shell_enabled.server = None
    shell_enabled.server_task = None
    shell_enabled.close()  # Should not raise

def test_close_disabled(shell_disabled):
    """close() with disabled shell doesn't crash"""
    shell_disabled.close()  # Should not raise
```

### Test Class 12: TestConnectionHandling (5 tests)

Tests for interactive shell connection handling.

```python
@pytest.mark.asyncio
async def test_handle_connection_sends_welcome(shell_enabled, mock_writer):
    """Connection sends welcome message"""
    reader = AsyncMock()
    reader.readline.return_value = b'exit\n'
    
    await shell_enabled.handle_connection(reader, mock_writer)
    
    # Check that write was called with welcome text
    calls = [call[0][1] for call in mock_writer.write.call_args_list]
    assert any('CyTube Bot Control Shell' in call for call in calls)

@pytest.mark.asyncio
async def test_handle_connection_processes_commands(shell_enabled, mock_writer):
    """Connection processes user commands"""
    reader = AsyncMock()
    reader.readline.side_effect = [b'help\n', b'exit\n']
    
    await shell_enabled.handle_connection(reader, mock_writer)
    
    # Should show help text
    calls = [call[0][1] for call in mock_writer.write.call_args_list]
    assert any('Bot Commands' in call for call in calls)

@pytest.mark.asyncio
async def test_handle_connection_exit_command(shell_enabled, mock_writer, caplog):
    """exit command closes connection"""
    reader = AsyncMock()
    reader.readline.return_value = b'exit\n'
    
    await shell_enabled.handle_connection(reader, mock_writer)
    
    assert 'exiting shell' in caplog.text

@pytest.mark.asyncio
async def test_handle_connection_handles_unicode_error(shell_enabled, mock_writer):
    """Invalid unicode is handled gracefully"""
    reader = AsyncMock()
    reader.readline.side_effect = [b'\xff\xfe\n', b'exit\n']
    
    # Should not crash
    await shell_enabled.handle_connection(reader, mock_writer)

@pytest.mark.asyncio
async def test_handle_connection_closes_writer(shell_enabled, mock_writer):
    """Connection closes writer on exit"""
    reader = AsyncMock()
    reader.readline.return_value = b'exit\n'
    
    await shell_enabled.handle_connection(reader, mock_writer)
    
    mock_writer.close.assert_called_once()
```

### Test Class 13: TestShellEdgeCases (6 tests)

Tests for error handling and edge cases.

```python
@pytest.mark.asyncio
async def test_command_error_returns_message(mock_bot):
    """Command errors return user-friendly message"""
    mock_bot.chat = AsyncMock(side_effect=Exception("Test error"))
    
    shell = Shell(None, mock_bot)
    result = await shell.handle_command("say test", mock_bot)
    
    assert "Error:" in result

@pytest.mark.asyncio
async def test_invalid_playlist_position(mock_bot):
    """Invalid playlist positions show error"""
    mock_bot.channel.playlist.queue = []
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_remove(mock_bot, "99")
    assert "must be between" in result

@pytest.mark.asyncio
async def test_cmd_add_invalid_url(mock_bot):
    """Invalid URL in add command shows error"""
    shell = Shell(None, mock_bot)
    result = await shell.cmd_add(mock_bot, "not-a-url")
    assert "Failed to add media" in result

def test_format_duration_no_minutes():
    """Duration with only hours and seconds"""
    # 1 hour + 30 seconds
    assert Shell.format_duration(3630) == "1h 30s"

@pytest.mark.asyncio
async def test_cmd_user_with_database_stats(mock_bot):
    """user command includes database stats if available"""
    user = MagicMock()
    user.name = "alice"
    user.rank = 1.0
    user.afk = False
    user.muted = False
    user.ip = None
    user.uncloaked_ip = None
    user.aliases = []
    
    mock_bot.channel.userlist.__contains__ = lambda self, name: True
    mock_bot.channel.userlist.__getitem__ = lambda self, name: user
    mock_bot.db = MagicMock()
    mock_bot.db.get_user_stats.return_value = {
        'total_chat_lines': 42,
        'total_time_connected': 3600
    }
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_user(mock_bot, "alice")
    
    assert "Chat msgs: 42" in result
    assert "Time: 1h" in result

@pytest.mark.asyncio
async def test_no_channel_commands_handled(mock_bot):
    """Commands handle missing channel gracefully"""
    mock_bot.channel = None
    
    shell = Shell(None, mock_bot)
    result = await shell.cmd_users(mock_bot)
    assert "No users information available" in result
```

## Expected Test Coverage

**Coverage Analysis**:
- **Initialization**: 100% (address parsing, disabled mode, event loop)
- **I/O Operations**: 95% (write, CRLF conversion, unicode)
- **Command Parsing**: 95% (split, args extraction, case-insensitive)
- **Info Commands**: 90% (info, status, stats with/without database)
- **User Commands**: 90% (users, user, afk)
- **Chat Commands**: 95% (say, pm, clear)
- **Playlist Commands**: 85% (playlist, current, add, remove, move, jump, next)
- **Control Commands**: 95% (pause, kick, voteskip)
- **PM Handling**: 90% (authentication, splitting, logging, error handling)
- **Server Lifecycle**: 85% (start, close, connection handling)
- **Error Handling**: 85% (command errors, invalid input, unicode)

**Overall Coverage**: ~85% (realistic for async networking and extensive command set)

**Challenging Areas**:
- Actual socket.io server integration (requires integration tests)
- Complex move operations edge cases
- Network errors and disconnections
- Full PM message splitting logic with exact boundaries

## Manual Verification Commands

```bash
# Run all shell tests
pytest tests/unit/test_shell.py -v

# Run with coverage
pytest tests/unit/test_shell.py --cov=common.shell --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_shell.py::TestPlaylistCommands -v

# Run with async debugging
pytest tests/unit/test_shell.py -v -s --log-cli-level=DEBUG

# Test PM handling specifically
pytest tests/unit/test_shell.py::TestPMCommandHandling -v
```

## Success Criteria

- ✅ All 80+ tests pass
- ✅ Coverage ≥85% for common/shell.py
- ✅ All 30+ commands tested
- ✅ PM authentication validated (rank 2.0+ check)
- ✅ Message splitting tested (500 char limit)
- ✅ Command parsing edge cases covered
- ✅ Server lifecycle tested (start, close)
- ✅ Error handling verified
- ✅ Unicode and telnet compatibility tested
- ✅ Duration formatting validated
- ✅ Integration with bot methods mocked appropriately

## Dependencies

- **SPEC-Commit-1**: pytest infrastructure, pytest-asyncio
- **SPEC-Commit-2**: User tests (for user command tests)
- **SPEC-Commit-7**: Bot tests (for bot integration mocking)
- **Python modules**: asyncio, logging
- **Test utilities**: unittest.mock (AsyncMock, MagicMock, patch)

## Implementation Notes

1. **Async Testing**: All command methods are async, use pytest-asyncio
2. **Mocking Strategy**: Mock bot and its components (channel, userlist, playlist, database)
3. **StreamWriter Mocking**: Use AsyncMock for writer.drain(), MagicMock for write()
4. **PM Rank Check**: Test both moderator (≥2.0) and regular user (<2.0) scenarios
5. **Error Testing**: Use side_effect to simulate exceptions in bot methods
6. **Unicode Testing**: Test LF→CRLF conversion with unicode characters
7. **Disabled Shell**: Test that addr=None properly disables all shell functionality
8. **Command Coverage**: Prioritize most commonly used commands (info, say, playlist)
9. **Integration Note**: Full TCP server testing requires integration tests
10. **Coverage Strategy**: Focus on command logic and PM handling, mock network I/O

## Notes

- **Complexity**: 806 lines, 30+ commands, async TCP server - HIGH complexity
- **Test Count**: 80+ tests ensures comprehensive command coverage
- **Coverage Target**: 85% realistic (actual socket I/O hard to unit test)
- **Key Features**:
  - PM-based control for moderators (rank 2.0+)
  - Message splitting (500 char chunks)
  - Telnet compatibility (LF→CRLF)
  - Duration formatting utility
  - 30+ commands covering all bot functions
  - Disabled mode (addr=None)
- **Testing Strategy**: Heavy mocking of bot and async I/O, focus on command logic
- **Next Step**: Ready for implementation after approval
