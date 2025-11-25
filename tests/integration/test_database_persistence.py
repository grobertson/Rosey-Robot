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
from common.models import Base


pytestmark = pytest.mark.asyncio


async def _init_db(db_path: str) -> BotDatabase:
    """Create and initialize a BotDatabase with schema."""
    db = BotDatabase(db_path)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await db.connect()
    return db


async def test_user_stats_persist_across_restart(tmp_path):
    """User statistics persist across database reopens."""
    db_path = str(tmp_path / "persist_test.db")

    # First session
    db1 = await _init_db(db_path)
    await db1.user_joined('alice')
    for _ in range(10):
        await db1.user_chat_message('alice', 'test message')
    await db1.close()

    # Second session (reopen)
    db2 = BotDatabase(db_path)
    await db2.connect()
    stats = await db2.get_user_stats('alice')
    assert stats['total_chat_lines'] == 10
    await db2.close()


async def test_high_water_marks_persist(tmp_path):
    """High water marks persist across reopens."""
    db_path = str(tmp_path / "persist_test.db")

    # Set high water marks
    db1 = await _init_db(db_path)
    await db1.update_high_water_mark(42, 100)
    await db1.close()

    # Reopen and verify
    db2 = BotDatabase(db_path)
    await db2.connect()
    max_chat, _ = await db2.get_high_water_mark()
    max_connected, _ = await db2.get_high_water_mark_connected()
    assert max_chat == 42
    assert max_connected == 100
    await db2.close()


async def test_outbound_messages_persist(tmp_path):
    """Outbound message queue persists."""
    db_path = str(tmp_path / "persist_test.db")

    # Enqueue messages
    db1 = await _init_db(db_path)
    await db1.enqueue_outbound_message("Message 1")
    await db1.enqueue_outbound_message("Message 2")
    await db1.close()

    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    await db2.connect()
    messages = await db2.get_unsent_outbound_messages()
    assert len(messages) == 2
    assert messages[0]['message'] == "Message 1"
    assert messages[1]['message'] == "Message 2"
    await db2.close()


async def test_api_tokens_persist(tmp_path):
    """API tokens persist across sessions."""
    db_path = str(tmp_path / "persist_test.db")

    # Generate token
    db1 = await _init_db(db_path)
    token = await db1.generate_api_token("Test token")
    await db1.close()

    # Reopen and validate
    db2 = BotDatabase(db_path)
    await db2.connect()
    assert await db2.validate_api_token(token) is True
    await db2.close()


async def test_recent_chat_persists(tmp_path):
    """Recent chat messages persist."""
    db_path = str(tmp_path / "persist_test.db")

    # Store messages
    db1 = await _init_db(db_path)
    await db1.user_joined('alice')
    await db1.user_chat_message('alice', 'Message 1')
    await db1.user_chat_message('alice', 'Message 2')
    await db1.close()

    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    await db2.connect()
    recent = await db2.get_recent_chat(limit=10)
    assert len(recent) >= 2
    # Messages should be in the recent list
    messages = [msg['message'] for msg in recent if isinstance(msg, dict) and msg.get('message')]
    assert 'Message 1' in messages or 'Message 2' in messages
    await db2.close()
