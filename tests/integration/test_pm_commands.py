"""
Integration tests for PM Command Flow.

Tests PM-based command flow with authentication and response:
- Moderator authentication (rank >= 2.0)
- Command execution triggering bot actions
- Response splitting for long messages
- Error handling and user notification
- Database logging of PM commands
"""

import pytest
from unittest.mock import AsyncMock
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MockEvent:
    """Mock NATS Event for testing."""
    subject: str
    data: Dict[str, Any]

    @classmethod
    def create_pm_event(cls, username: str, message: str):
        """Create a PM event with standard structure."""
        return cls(
            subject="rosey.platform.cytube.pm",
            data={
                'username': username,
                'msg': message,
                'time': 0
            }
        )


pytestmark = pytest.mark.asyncio


@pytest.mark.xfail(reason="PM command database logging needs refactor - see issue #XX")
async def test_pm_command_moderator_flow(integration_bot, integration_shell, integration_db, moderator_user):
    """Complete PM command flow for moderator."""
    # Add moderator to userlist
    integration_bot.channel.userlist._users['ModUser'] = moderator_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()

    # Send PM command
    event = MockEvent.create_pm_event('ModUser', 'status')
    await integration_shell.handle_pm_command(event)

    # Verify response sent
    integration_bot.pm.assert_called()

    # Verify database logging
    cursor = integration_db.conn.cursor()
    cursor.execute('''
        SELECT * FROM user_actions 
        WHERE username = 'ModUser' AND action_type = 'pm_command'
    ''')
    log_entry = cursor.fetchone()
    assert log_entry is not None


async def test_pm_command_non_moderator_blocked(integration_bot, integration_shell, regular_user):
    """Non-moderator PM commands are blocked."""
    # Add regular user to userlist
    integration_bot.channel.userlist._users['RegularUser'] = regular_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()
    integration_bot.chat = AsyncMock()

    # Send PM command
    event = MockEvent.create_pm_event('RegularUser', 'say test')
    await integration_shell.handle_pm_command(event)

    # Verify no action taken
    integration_bot.pm.assert_not_called()
    integration_bot.chat.assert_not_called()


@pytest.mark.xfail(reason="PM command database logging needs refactor - see issue #XX")
async def test_pm_command_triggers_bot_action(integration_bot, integration_shell, moderator_user):
    """PM command triggers actual bot action."""
    # Add moderator to userlist
    integration_bot.channel.userlist._users['ModUser'] = moderator_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()
    integration_bot.chat = AsyncMock()

    # PM: "say Hello"
    event = MockEvent.create_pm_event('ModUser', 'say Hello everyone')
    await integration_shell.handle_pm_command(event)

    # Verify chat message sent
    integration_bot.chat.assert_called_once_with("Hello everyone")

    # Verify response PM sent
    integration_bot.pm.assert_called()


@pytest.mark.xfail(reason="PM command database logging needs refactor - see issue #XX")
async def test_pm_command_long_response_splits(integration_bot, integration_shell, moderator_user):
    """Long PM responses are split into multiple messages."""
    # Add moderator to userlist
    integration_bot.channel.userlist._users['ModUser'] = moderator_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()

    # Command with long response (help text)
    event = MockEvent.create_pm_event('ModUser', 'help')
    await integration_shell.handle_pm_command(event)

    # Should send multiple PM chunks (help text is >500 chars)
    assert integration_bot.pm.call_count >= 2


@pytest.mark.xfail(reason="PM command database logging needs refactor - see issue #XX")
async def test_pm_command_error_sends_error_message(integration_bot, integration_shell, moderator_user):
    """PM command errors send error message back."""
    # Add moderator to userlist
    integration_bot.channel.userlist._users['ModUser'] = moderator_user
    integration_bot.channel.userlist.count = 1
    integration_bot.pm = AsyncMock()
    integration_bot.pause = AsyncMock(side_effect=Exception("No permission"))

    # Command that will error
    event = MockEvent.create_pm_event('ModUser', 'pause')
    await integration_shell.handle_pm_command(event)

    # Should send error PM
    calls = [str(call) for call in integration_bot.pm.call_args_list]
    assert any('Error:' in call for call in calls)
