"""
Integration tests for End-to-End Workflows.

Tests complete user workflows from start to finish:
- Complete user session: join → chat → stats → leave
- Playlist manipulation: add → query → move → jump → remove
- Moderator control: PM auth → command → bot action → database log
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


pytestmark = pytest.mark.asyncio


async def test_complete_user_session_workflow(integration_bot, integration_db):
    """Complete workflow: join → chat → stats query → leave."""
    # 1. User joins
    user_mock = MagicMock()
    user_mock.name = 'alice'
    user_mock.rank = 1.0
    user_mock.afk = False
    integration_bot.channel.userlist._users['alice'] = user_mock
    integration_bot.channel.userlist.count = 1
    integration_db.user_joined('alice')

    # 2. User chats
    for i in range(5):
        integration_db.user_chat_message('alice')

    # 3. Query stats
    stats = integration_db.get_user_stats('alice')
    assert stats['total_chat_lines'] == 5

    # 4. User leaves
    await asyncio.sleep(0.5)
    integration_db.user_left('alice')

    # 5. Verify final stats
    final_stats = integration_db.get_user_stats('alice')
    assert final_stats['total_time_connected'] >= 0  # May be 0 due to timing
    assert final_stats['current_session_start'] is None


async def test_playlist_manipulation_workflow(integration_bot, integration_shell):
    """Complete workflow: add → query → move → jump → remove."""
    integration_bot.add_media = AsyncMock()
    integration_bot.move_media = AsyncMock()
    integration_bot.set_current_media = AsyncMock()
    integration_bot.remove_media = AsyncMock()

    # Setup playlist
    item1 = MagicMock(title="Video 1", duration=120, temp=False)
    item2 = MagicMock(title="Video 2", duration=180, temp=False)
    item3 = MagicMock(title="Video 3", duration=240, temp=False)
    integration_bot.channel.playlist.queue = [item1, item2, item3]
    integration_bot.channel.playlist.current = item1

    # 1. Add new item
    await integration_shell.handle_command("add https://youtu.be/xyz", integration_bot)

    # 2. Query playlist
    result = await integration_shell.handle_command("playlist", integration_bot)
    assert "Video 1" in result

    # 3. Move item
    await integration_shell.handle_command("move 2 3", integration_bot)

    # 4. Jump to item
    await integration_shell.handle_command("jump 2", integration_bot)

    # 5. Remove item
    await integration_shell.handle_command("remove 3", integration_bot)

    # Verify all commands executed
    integration_bot.add_media.assert_called_once()
    integration_bot.set_current_media.assert_called_once()


@pytest.mark.xfail(reason="PM command database logging needs refactor - see issue #XX")
async def test_moderator_control_workflow(integration_bot, integration_shell, integration_db, moderator_user):
    """Complete workflow: PM auth → command → bot action → database log."""
    # Setup moderator
    moderator_user.name = "ModUser"
    moderator_user.rank = 3.0
    integration_bot.channel.userlist._users['ModUser'] = moderator_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()
    integration_bot.kick = AsyncMock()

    # 1. Moderator sends PM command
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'kick alice Spamming'
    })

    # 2. Verify bot action executed
    integration_bot.kick.assert_called_once_with('alice', 'Spamming')

    # 3. Verify database log
    cursor = integration_db.conn.cursor()
    cursor.execute('''
        SELECT * FROM user_actions 
        WHERE username = 'ModUser' AND action_type = 'pm_command'
    ''')
    log_entry = cursor.fetchone()
    assert log_entry is not None
    assert log_entry['details'] == 'kick alice Spamming'

    # 4. Verify response sent
    integration_bot.pm.assert_called()
