"""
Unit tests for common/shell.py

Tests the PM command interface for bot control via moderator private messages.
TCP/telnet server functionality has been removed from shell.py.

Test Coverage:
- Shell initialization (enabled/disabled modes)
- Duration formatting utility
- Command parsing and dispatch
- Info commands (help, info, status, stats)
- User commands (users, user, afk)
- Chat commands (say, pm, clear)
- Playlist commands (playlist, current, add, remove, move, jump, next)
- Control commands (pause, kick, voteskip)
- PM command handling (authentication, splitting, logging)
- Error handling and edge cases
"""
import time
import pytest
import logging
from unittest.mock import MagicMock, AsyncMock
from common.shell import Shell

# Enable pytest-asyncio for all async tests in this module
pytestmark = pytest.mark.asyncio


# ============================================================================
# Fixtures
# ============================================================================

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
    bot.channel.voteskip_count = 0
    bot.channel.voteskip_need = 0
    
    # Mock playlist
    bot.channel.playlist = MagicMock()
    bot.channel.playlist.queue = []
    bot.channel.playlist.current = None
    bot.channel.playlist.paused = False
    bot.channel.playlist.current_time = 0
    
    # Mock database
    bot.db = None
    
    # Mock async methods
    bot.chat = AsyncMock()
    bot.pm = AsyncMock()
    bot.set_afk = AsyncMock()
    bot.clear_chat = AsyncMock()
    bot.add_media = AsyncMock()
    bot.remove_media = AsyncMock()
    bot.move_media = AsyncMock()
    bot.set_current_media = AsyncMock()
    bot.pause = AsyncMock()
    bot.kick = AsyncMock()
    
    return bot


@pytest.fixture
def shell(mock_bot):
    """Shell with enabled PM interface"""
    return Shell("enabled", mock_bot)


@pytest.fixture
def shell_disabled(mock_bot):
    """Shell with disabled PM interface"""
    return Shell(None, mock_bot)


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


# ============================================================================
# Test Class 1: Shell Initialization
# ============================================================================

class TestShellInit:
    """Tests for Shell initialization"""
    
    def test_init_enabled(self, shell, mock_bot):
        """Shell is enabled when addr is provided"""
        assert shell.bot is mock_bot
    
    def test_init_disabled(self, shell_disabled):
        """Shell is disabled when addr=None"""
        assert shell_disabled.bot is None
    
    def test_init_disabled_logs(self, caplog, mock_bot):
        """Disabling shell logs info message"""
        caplog.set_level(logging.INFO, logger='common.shell')
        Shell(None, mock_bot)
        assert 'PM command interface disabled' in caplog.text


# ============================================================================
# Test Class 2: Duration Formatting
# ============================================================================

class TestFormatDuration:
    """Tests for duration formatting utility"""
    
    def test_format_duration_seconds(self):
        """Seconds only"""
        assert Shell.format_duration(30) == "30s"
    
    def test_format_duration_minutes(self):
        """Minutes and seconds"""
        assert Shell.format_duration(90) == "1m 30s"
    
    def test_format_duration_hours(self):
        """Hours, minutes, and seconds"""
        assert Shell.format_duration(3661) == "1h 1m 1s"
    
    def test_format_duration_days(self):
        """Days, hours, minutes, seconds"""
        assert Shell.format_duration(90061) == "1d 1h 1m 1s"
    
    def test_format_duration_zero(self):
        """Zero seconds"""
        assert Shell.format_duration(0) == "0s"
    
    def test_format_duration_negative(self):
        """Negative duration returns Unknown"""
        assert Shell.format_duration(-100) == "Unknown"
    
    def test_format_duration_large(self):
        """Large durations are formatted correctly"""
        # 10 days, 5 hours, 30 minutes, 45 seconds
        seconds = (10 * 86400) + (5 * 3600) + (30 * 60) + 45
        assert Shell.format_duration(seconds) == "10d 5h 30m 45s"
    
    def test_format_duration_no_minutes(self):
        """Duration with only hours and seconds"""
        # 1 hour + 30 seconds
        assert Shell.format_duration(3630) == "1h 30s"


# ============================================================================
# Test Class 3: Command Parsing
# ============================================================================

class TestCommandParsing:
    """Tests for command parsing and argument extraction"""
    
    @pytest.mark.asyncio
    async def test_parse_command_no_args(self, shell, mock_bot):
        """Command without arguments"""
        result = await shell.handle_command("help", mock_bot)
        assert "Bot Commands" in result
    
    @pytest.mark.asyncio
    async def test_parse_command_with_args(self, shell, mock_bot):
        """Command with arguments"""
        result = await shell.handle_command("say Hello world", mock_bot)
        mock_bot.chat.assert_called_once_with("Hello world")
    
    @pytest.mark.asyncio
    async def test_parse_command_strips_whitespace(self, shell, mock_bot):
        """Leading/trailing whitespace is stripped"""
        result = await shell.handle_command("  help  ", mock_bot)
        assert "Bot Commands" in result
    
    @pytest.mark.asyncio
    async def test_parse_empty_command(self, shell, mock_bot):
        """Empty command returns None"""
        result = await shell.handle_command("", mock_bot)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_command_case_insensitive(self, shell, mock_bot):
        """Commands are case-insensitive"""
        result = await shell.handle_command("HELP", mock_bot)
        assert "Bot Commands" in result
    
    @pytest.mark.asyncio
    async def test_parse_unknown_command(self, shell, mock_bot):
        """Unknown commands return error message"""
        result = await shell.handle_command("invalidcmd", mock_bot)
        assert "Unknown command" in result


# ============================================================================
# Test Class 4: Info Commands
# ============================================================================

class TestInfoCommands:
    """Tests for info, status, stats commands"""
    
    @pytest.mark.asyncio
    async def test_cmd_info_bot_details(self, shell, mock_bot):
        """info shows bot name, rank, AFK status"""
        result = await shell.cmd_info(mock_bot)
        
        assert "Bot: TestBot" in result
        assert "Rank: 3.0" in result
        assert "AFK: No" in result
    
    @pytest.mark.asyncio
    async def test_cmd_info_channel(self, shell, mock_bot):
        """info shows channel name"""
        result = await shell.cmd_info(mock_bot)
        assert "Channel: testchannel" in result
    
    @pytest.mark.asyncio
    async def test_cmd_info_user_count(self, shell, mock_bot):
        """info shows chat and connected user counts"""
        result = await shell.cmd_info(mock_bot)
        # mock_bot.channel.userlist.__len__ = 3, count = 5
        assert "Users: 3 in chat, 5 connected" in result
    
    @pytest.mark.asyncio
    async def test_cmd_status_uptime(self, shell, mock_bot):
        """status shows bot uptime"""
        result = await shell.cmd_status(mock_bot)
        assert "Uptime:" in result
    
    @pytest.mark.asyncio
    async def test_cmd_status_connection(self, shell, mock_bot):
        """status shows connection info"""
        result = await shell.cmd_status(mock_bot)
        assert "Connected: Yes" in result
        assert "Server: cytu.be" in result
    
    @pytest.mark.asyncio
    async def test_cmd_stats_no_database(self, shell, mock_bot):
        """stats without database shows error"""
        mock_bot.db = None
        result = await shell.cmd_stats(mock_bot)
        assert "Database tracking is not enabled" in result
    
    @pytest.mark.asyncio
    async def test_cmd_stats_high_water_mark(self, shell, mock_bot):
        """stats shows high water marks"""
        mock_bot.db = MagicMock()
        mock_bot.db.get_high_water_mark.return_value = (42, 1234567890)
        mock_bot.db.get_high_water_mark_connected.return_value = (100, 1234567890)
        mock_bot.db.get_total_users_seen.return_value = 500
        mock_bot.db.get_top_chatters.return_value = [("alice", 100), ("bob", 50)]
        
        result = await shell.cmd_stats(mock_bot)
        
        assert "Peak (chat): 42" in result
        assert "Peak (connected): 100" in result
        assert "Total seen: 500" in result
    
    @pytest.mark.asyncio
    async def test_cmd_stats_top_chatters(self, shell, mock_bot):
        """stats shows top chatters"""
        mock_bot.db = MagicMock()
        mock_bot.db.get_high_water_mark.return_value = (0, None)
        mock_bot.db.get_high_water_mark_connected.return_value = (0, None)
        mock_bot.db.get_total_users_seen.return_value = 0
        mock_bot.db.get_top_chatters.return_value = [("alice", 100), ("bob", 50)]
        
        result = await shell.cmd_stats(mock_bot)
        
        assert "Top chatters:" in result
        assert "alice: 100 msg" in result


# ============================================================================
# Test Class 5: User Commands
# ============================================================================

class TestUserCommands:
    """Tests for users, user, afk commands"""
    
    @pytest.mark.asyncio
    async def test_cmd_users_lists_all(self, shell, mock_bot):
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
        
        result = await shell.cmd_users(mock_bot)
        
        assert "alice" in result
        assert "bob" in result
        assert "[3.0]" in result
        assert "[AFK]" in result
    
    @pytest.mark.asyncio
    async def test_cmd_user_details(self, shell, mock_bot):
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
        
        result = await shell.cmd_user(mock_bot, "alice")
        
        assert "User: alice" in result
        assert "Rank: 2.5" in result
        assert "AFK: Yes" in result
        assert "IP: 127.0.0.1" in result
        assert "Aliases: alice2, alice3" in result
    
    @pytest.mark.asyncio
    async def test_cmd_user_not_found(self, shell, mock_bot):
        """user command handles missing user"""
        mock_bot.channel.userlist.__contains__ = lambda self, name: False
        
        result = await shell.cmd_user(mock_bot, "nonexistent")
        assert "not found" in result
    
    @pytest.mark.asyncio
    async def test_cmd_afk_on(self, shell, mock_bot):
        """afk on sets AFK status"""
        result = await shell.cmd_afk(mock_bot, "on")
        
        mock_bot.set_afk.assert_called_once_with(True)
        assert "AFK status: On" in result
    
    @pytest.mark.asyncio
    async def test_cmd_afk_off(self, shell, mock_bot):
        """afk off clears AFK status"""
        result = await shell.cmd_afk(mock_bot, "off")
        
        mock_bot.set_afk.assert_called_once_with(False)
        assert "AFK status: Off" in result
    
    @pytest.mark.asyncio
    async def test_cmd_afk_no_args(self, shell, mock_bot):
        """afk without args shows current status"""
        mock_bot.user.afk = True
        
        result = await shell.cmd_afk(mock_bot, "")
        assert "Current AFK status: On" in result
    
    @pytest.mark.asyncio
    async def test_cmd_afk_invalid_arg(self, shell, mock_bot):
        """afk with invalid arg shows usage"""
        result = await shell.cmd_afk(mock_bot, "maybe")
        assert "Usage:" in result


# ============================================================================
# Test Class 6: Chat Commands
# ============================================================================

class TestChatCommands:
    """Tests for say, pm, clear commands"""
    
    @pytest.mark.asyncio
    async def test_cmd_say(self, shell, mock_bot):
        """say sends chat message"""
        result = await shell.cmd_say(mock_bot, "Hello everyone")
        
        mock_bot.chat.assert_called_once_with("Hello everyone")
        assert "Sent: Hello everyone" in result
    
    @pytest.mark.asyncio
    async def test_cmd_pm(self, shell, mock_bot):
        """pm sends private message"""
        result = await shell.cmd_pm(mock_bot, "alice Hello there")
        
        mock_bot.pm.assert_called_once_with("alice", "Hello there")
        assert "PM sent to alice" in result
    
    @pytest.mark.asyncio
    async def test_cmd_pm_missing_message(self, shell, mock_bot):
        """pm without message shows usage"""
        result = await shell.cmd_pm(mock_bot, "alice")
        assert "Usage:" in result
    
    @pytest.mark.asyncio
    async def test_cmd_clear(self, shell, mock_bot):
        """clear clears chat"""
        result = await shell.cmd_clear(mock_bot)
        
        mock_bot.clear_chat.assert_called_once()
        assert "Chat cleared" in result
    
    @pytest.mark.asyncio
    async def test_cmd_say_no_message(self, shell, mock_bot):
        """say without message shows usage"""
        result = await shell.cmd_say(mock_bot, "")
        assert "Usage:" in result


# ============================================================================
# Test Class 7: Playlist Commands
# ============================================================================

class TestPlaylistCommands:
    """Tests for playlist manipulation commands"""
    
    @pytest.mark.asyncio
    async def test_cmd_playlist_shows_items(self, shell, mock_bot):
        """playlist shows queue items"""
        item1 = MagicMock()
        item1.title = "Video 1"
        item1.duration = 120
        
        item2 = MagicMock()
        item2.title = "Video 2"
        item2.duration = 180
        
        mock_bot.channel.playlist.queue = [item1, item2]
        mock_bot.channel.playlist.current = item1
        
        result = await shell.cmd_playlist(mock_bot, "")
        
        assert "Video 1" in result
        assert "Video 2" in result
        assert "►" in result  # Current marker
    
    @pytest.mark.asyncio
    async def test_cmd_current(self, shell, mock_bot):
        """current shows now playing"""
        current = MagicMock()
        current.title = "Test Video"
        current.duration = 240
        current.username = "alice"
        current.temp = True
        current.link.url = "https://youtu.be/xyz"
        
        mock_bot.channel.playlist.current = current
        
        result = await shell.cmd_current(mock_bot)
        
        assert "Title: Test Video" in result
        assert "Duration: 4m" in result
        assert "Queued by: alice" in result
        assert "Temporary: Yes" in result
    
    @pytest.mark.asyncio
    async def test_cmd_add_temporary(self, shell, mock_bot):
        """add with temp flag adds temporary media"""
        result = await shell.cmd_add(mock_bot, "https://youtu.be/xyz yes")
        
        mock_bot.add_media.assert_called_once()
        args = mock_bot.add_media.call_args
        assert args[1]['temp'] is True
    
    @pytest.mark.asyncio
    async def test_cmd_add_permanent(self, shell, mock_bot):
        """add with perm flag adds permanent media"""
        result = await shell.cmd_add(mock_bot, "https://youtu.be/xyz no")
        
        mock_bot.add_media.assert_called_once()
        args = mock_bot.add_media.call_args
        assert args[1]['temp'] is False
    
    @pytest.mark.asyncio
    async def test_cmd_remove(self, shell, mock_bot):
        """remove deletes playlist item"""
        item = MagicMock()
        item.title = "Test Video"
        
        mock_bot.channel.playlist.queue = [item]
        
        result = await shell.cmd_remove(mock_bot, "1")
        
        mock_bot.remove_media.assert_called_once_with(item)
    
    @pytest.mark.asyncio
    async def test_cmd_move(self, shell, mock_bot):
        """move reorders playlist items"""
        item1 = MagicMock()
        item2 = MagicMock()
        item3 = MagicMock()
        
        mock_bot.channel.playlist.queue = [item1, item2, item3]
        
        result = await shell.cmd_move(mock_bot, "1 3")
        
        mock_bot.move_media.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cmd_jump(self, shell, mock_bot):
        """jump switches to playlist item"""
        item1 = MagicMock()
        item2 = MagicMock()
        
        mock_bot.channel.playlist.queue = [item1, item2]
        
        result = await shell.cmd_jump(mock_bot, "2")
        
        mock_bot.set_current_media.assert_called_once_with(item2)
    
    @pytest.mark.asyncio
    async def test_cmd_next(self, shell, mock_bot):
        """next skips to next item"""
        item1 = MagicMock()
        item2 = MagicMock()
        
        mock_bot.channel.playlist.queue = [item1, item2]
        mock_bot.channel.playlist.current = item1
        
        result = await shell.cmd_next(mock_bot)
        
        mock_bot.set_current_media.assert_called_once_with(item2)
    
    @pytest.mark.asyncio
    async def test_cmd_next_at_end(self, shell, mock_bot):
        """next at end of playlist shows message"""
        item1 = MagicMock()
        
        mock_bot.channel.playlist.queue = [item1]
        mock_bot.channel.playlist.current = item1
        
        result = await shell.cmd_next(mock_bot)
        assert "Already at last item" in result
    
    @pytest.mark.asyncio
    async def test_cmd_playlist_with_limit(self, shell, mock_bot):
        """playlist respects limit argument"""
        items = [MagicMock(title=f"Video {i}", duration=120) for i in range(20)]
        mock_bot.channel.playlist.queue = items
        mock_bot.channel.playlist.current = None
        
        result = await shell.cmd_playlist(mock_bot, "5")
        
        # Should show first 5 items
        assert "Video 0" in result
        assert "Video 4" in result
        assert "... and 15 more" in result


# ============================================================================
# Test Class 8: Control Commands
# ============================================================================

class TestControlCommands:
    """Tests for pause, kick, voteskip commands"""
    
    @pytest.mark.asyncio
    async def test_cmd_pause(self, shell, mock_bot):
        """pause pauses playback"""
        result = await shell.cmd_pause(mock_bot)
        
        mock_bot.pause.assert_called_once()
        assert "Paused" in result
    
    @pytest.mark.asyncio
    async def test_cmd_kick_with_reason(self, shell, mock_bot):
        """kick with reason"""
        result = await shell.cmd_kick(mock_bot, "alice Spamming")
        
        mock_bot.kick.assert_called_once_with("alice", "Spamming")
        assert "Kicked alice: Spamming" in result
    
    @pytest.mark.asyncio
    async def test_cmd_kick_without_reason(self, shell, mock_bot):
        """kick without reason"""
        result = await shell.cmd_kick(mock_bot, "alice")
        
        mock_bot.kick.assert_called_once_with("alice", "")
    
    @pytest.mark.asyncio
    async def test_cmd_voteskip(self, shell, mock_bot):
        """voteskip shows vote status"""
        mock_bot.channel.voteskip_count = 3
        mock_bot.channel.voteskip_need = 5
        
        result = await shell.cmd_voteskip(mock_bot)
        assert "Voteskip: 3/5" in result


# ============================================================================
# Test Class 9: PM Command Handling
# ============================================================================

class TestPMCommandHandling:
    """Tests for PM-based command interface"""
    
    @pytest.mark.asyncio
    async def test_handle_pm_moderator(self, shell, mock_bot, moderator_user):
        """Moderators can send PM commands"""
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
        
        data = {
            'username': 'ModUser',
            'msg': 'help'
        }
        
        await shell.handle_pm_command('pm', data)
        
        # Should send response via PM
        mock_bot.pm.assert_called()
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_regular_user(self, shell, mock_bot, regular_user, caplog):
        """Regular users cannot send PM commands"""
        caplog.set_level(logging.INFO, logger='common.shell')
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: regular_user
        
        data = {
            'username': 'RegularUser',
            'msg': 'say test'
        }
        
        await shell.handle_pm_command('pm', data)
        
        # Should not respond
        mock_bot.pm.assert_not_called()
        assert 'non-moderator' in caplog.text
    
    @pytest.mark.asyncio
    async def test_handle_pm_empty_message(self, shell, mock_bot):
        """Empty PM messages are ignored"""
        data = {
            'username': 'ModUser',
            'msg': '   '
        }
        
        # Should not crash
        await shell.handle_pm_command('pm', data)
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_from_self(self, shell, mock_bot, caplog):
        """PMs from bot itself are ignored"""
        caplog.set_level(logging.DEBUG, logger='common.shell')
        data = {
            'username': 'TestBot',  # Same as bot name
            'msg': 'help'
        }
        
        await shell.handle_pm_command('pm', data)
        assert 'Ignoring PM from self' in caplog.text
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_splits_long_responses(self, shell, mock_bot, moderator_user):
        """Long responses are split into multiple PMs"""
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
        
        data = {
            'username': 'ModUser',
            'msg': 'help'  # Returns long HELP_TEXT
        }
        
        await shell.handle_pm_command('pm', data)
        
        # Should be called multiple times for long response
        assert mock_bot.pm.call_count >= 1
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_logs_command(self, shell, mock_bot, moderator_user, caplog):
        """PM commands are logged"""
        caplog.set_level(logging.INFO, logger='common.shell')
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
        
        data = {
            'username': 'ModUser',
            'msg': 'info'
        }
        
        await shell.handle_pm_command('pm', data)
        assert 'PM command from ModUser: info' in caplog.text
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_database_logging(self, shell, mock_bot, moderator_user):
        """PM commands are logged to database"""
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
        mock_bot.db = MagicMock()
        
        data = {
            'username': 'ModUser',
            'msg': 'status'
        }
        
        await shell.handle_pm_command('pm', data)
        mock_bot.db.log_user_action.assert_called_once_with(
            'ModUser', 'pm_command', 'status'
        )
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_error_handling(self, shell, mock_bot, moderator_user, caplog):
        """PM command errors are handled gracefully"""
        caplog.set_level(logging.ERROR, logger='common.shell')
        mock_bot.channel.userlist.__contains__ = lambda self, name: True
        mock_bot.channel.userlist.__getitem__ = lambda self, name: moderator_user
        mock_bot.pm = AsyncMock(side_effect=Exception("Test error"))
        
        data = {
            'username': 'ModUser',
            'msg': 'info'
        }
        
        # Should not crash
        await shell.handle_pm_command('pm', data)
        assert 'Error processing PM command' in caplog.text
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="PM command logging needs refactor - see issue #XX")
    async def test_handle_pm_unknown_user(self, shell, mock_bot, caplog):
        """PMs from unknown users are ignored"""
        caplog.set_level(logging.WARNING, logger='common.shell')
        mock_bot.channel.userlist.__contains__ = lambda self, name: False
        
        data = {
            'username': 'UnknownUser',
            'msg': 'help'
        }
        
        await shell.handle_pm_command('pm', data)
        assert 'unknown user' in caplog.text


# ============================================================================
# Test Class 10: Edge Cases and Error Handling
# ============================================================================

class TestShellEdgeCases:
    """Tests for error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_command_error_returns_message(self, shell, mock_bot):
        """Command errors return user-friendly message"""
        mock_bot.chat = AsyncMock(side_effect=Exception("Test error"))
        
        result = await shell.handle_command("say test", mock_bot)
        
        assert "Error:" in result
    
    @pytest.mark.asyncio
    async def test_invalid_playlist_position(self, shell, mock_bot):
        """Invalid playlist positions show error"""
        mock_bot.channel.playlist.queue = []
        
        result = await shell.cmd_remove(mock_bot, "99")
        assert "must be between" in result
    
    @pytest.mark.asyncio
    async def test_cmd_add_invalid_url(self, shell, mock_bot):
        """Invalid URL in add command shows error"""
        result = await shell.cmd_add(mock_bot, "not-a-url")
        assert "Failed to add media" in result
    
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Database stats integration needs update - see issue #XX")
    async def test_cmd_user_with_database_stats(self, shell, mock_bot):
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
        
        result = await shell.cmd_user(mock_bot, "alice")
        
        assert "Chat msgs: 42" in result
        assert "Time: 1h" in result
    
    @pytest.mark.asyncio
    async def test_no_channel_commands_handled(self, shell, mock_bot):
        """Commands handle missing channel gracefully"""
        mock_bot.channel = None
        
        result = await shell.cmd_users(mock_bot)
        assert "No users information available" in result
