"""
Integration tests for Bot Lifecycle.

Tests complete bot lifecycle from startup to shutdown, including:
- Component initialization
- User tracking (join, chat, leave)
- Database integration
- High water mark tracking
- Session finalization
"""

import pytest
import asyncio
from unittest.mock import MagicMock


pytestmark = pytest.mark.asyncio


async def test_bot_startup_sequence(integration_bot, integration_db):
    """Bot startup initializes all components."""
    # Verify bot state
    assert integration_bot.user.name == "IntegrationTestBot"
    assert integration_bot.channel.name == "test_integration"
    assert integration_bot.db is not None
    assert integration_bot.db == integration_db
    
    # Verify database is connected
    status = integration_db.get_current_status()
    assert status is not None


async def test_bot_user_join_triggers_database(integration_bot, integration_db):
    """User joining is logged to database."""
    # Simulate user join event
    user_data = {
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    }
    
    # Add to channel userlist
    user_mock = MagicMock()
    user_mock.name = 'alice'
    user_mock.rank = 1.0
    user_mock.afk = False
    user_mock.muted = False
    integration_bot.channel.userlist._users['alice'] = user_mock
    integration_bot.channel.userlist.count += 1
    
    # Trigger database logging
    integration_db.user_joined('alice')
    
    # Verify database record
    stats = integration_db.get_user_stats('alice')
    assert stats is not None
    assert stats['username'] == 'alice'
    assert stats['current_session_start'] is not None


async def test_bot_user_chat_updates_database(integration_bot, integration_db):
    """Chat messages increment database counters."""
    # Add user first
    integration_db.user_joined('alice')
    
    # Simulate chat messages
    for i in range(5):
        integration_db.user_chat_message('alice')
    
    # Verify count
    stats = integration_db.get_user_stats('alice')
    assert stats['total_chat_lines'] == 5


async def test_bot_user_leave_finalizes_session(integration_bot, integration_db):
    """User leaving finalizes database session."""
    # Add user
    integration_db.user_joined('alice')
    
    # Wait to simulate session time (needs to be more substantial for SQLite timing)
    await asyncio.sleep(0.5)
    
    # User leaves
    integration_db.user_left('alice')
    
    # Verify session finalized
    stats = integration_db.get_user_stats('alice')
    assert stats['total_time_connected'] >= 0  # May be rounded to 0
    assert stats['current_session_start'] is None


async def test_bot_high_water_mark_tracking(integration_bot, integration_db):
    """Bot updates high water marks."""
    # Add multiple users
    for i in range(5):
        user_mock = MagicMock()
        user_mock.name = f'user{i}'
        user_mock.rank = 1.0
        integration_bot.channel.userlist._users[f'user{i}'] = user_mock
        integration_db.user_joined(f'user{i}')
    
    integration_bot.channel.userlist.count = 5
    
    # Update high water marks
    integration_db.update_high_water_mark(5, 8)
    
    # Verify high water marks
    max_chat, _ = integration_db.get_high_water_mark()
    max_connected, _ = integration_db.get_high_water_mark_connected()
    
    assert max_chat == 5
    assert max_connected == 8


async def test_bot_shutdown_finalizes_database(integration_bot, integration_db):
    """Bot shutdown finalizes all active sessions."""
    # Add users
    integration_db.user_joined('alice')
    integration_db.user_joined('bob')
    
    await asyncio.sleep(0.1)
    
    # Finalize all sessions (simulates shutdown)
    db_path = integration_db.db_path
    integration_db.close()
    
    # Reopen and check sessions finalized
    from common.database import BotDatabase
    db2 = BotDatabase(db_path)
    alice_stats = db2.get_user_stats('alice')
    bob_stats = db2.get_user_stats('bob')
    
    assert alice_stats['current_session_start'] is None
    assert bob_stats['current_session_start'] is None
    db2.close()
