"""
Integration tests for Database Persistence.

Tests data persistence across bot restarts:
- User statistics
- High water marks
- Outbound message queue
- API tokens
- Recent chat history
"""

import pytest
from common.database import BotDatabase


pytestmark = pytest.mark.asyncio


async def test_user_stats_persist_across_restart(tmp_path):
    """User statistics persist across database reopens."""
    db_path = str(tmp_path / "persist_test.db")

    # First session
    db1 = BotDatabase(db_path)
    db1.user_joined('alice')
    for _ in range(10):
        db1.user_chat_message('alice')
    db1.close()

    # Second session (reopen)
    db2 = BotDatabase(db_path)
    stats = db2.get_user_stats('alice')
    assert stats['total_chat_lines'] == 10
    db2.close()


async def test_high_water_marks_persist(tmp_path):
    """High water marks persist across reopens."""
    db_path = str(tmp_path / "persist_test.db")

    # Set high water marks
    db1 = BotDatabase(db_path)
    db1.update_high_water_mark(42, 100)
    db1.close()

    # Reopen and verify
    db2 = BotDatabase(db_path)
    max_chat, _ = db2.get_high_water_mark()
    max_connected, _ = db2.get_high_water_mark_connected()
    assert max_chat == 42
    assert max_connected == 100
    db2.close()


async def test_outbound_messages_persist(tmp_path):
    """Outbound message queue persists."""
    db_path = str(tmp_path / "persist_test.db")

    # Enqueue messages
    db1 = BotDatabase(db_path)
    db1.enqueue_outbound_message("Message 1")
    db1.enqueue_outbound_message("Message 2")
    db1.close()

    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    messages = db2.get_unsent_outbound_messages()
    assert len(messages) == 2
    assert messages[0]['message'] == "Message 1"
    assert messages[1]['message'] == "Message 2"
    db2.close()


async def test_api_tokens_persist(tmp_path):
    """API tokens persist across sessions."""
    db_path = str(tmp_path / "persist_test.db")

    # Generate token
    db1 = BotDatabase(db_path)
    token = db1.generate_api_token("Test token")
    db1.close()

    # Reopen and validate
    db2 = BotDatabase(db_path)
    assert db2.validate_api_token(token) is True
    db2.close()


async def test_recent_chat_persists(tmp_path):
    """Recent chat messages persist."""
    db_path = str(tmp_path / "persist_test.db")

    # Store messages
    db1 = BotDatabase(db_path)
    db1.user_joined('alice')
    db1.user_chat_message('alice', 'Message 1')
    db1.user_chat_message('alice', 'Message 2')
    db1.close()

    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    recent = db2.get_recent_chat(limit=10)
    assert len(recent) >= 2
    # Messages should be in the recent list
    messages = [msg['message'] for msg in recent if msg.get('message')]
    assert 'Message 1' in messages or 'Message 2' in messages
    db2.close()
