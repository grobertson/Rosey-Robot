#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for BotDatabase connection lifecycle (Sprint 10 Sortie 1)

Tests the async connect/close/migrations functionality added in Sprint 10.
Validates that the database can be properly initialized and torn down in tests.
"""
import pytest
import asyncio
import time
from pathlib import Path
import tempfile

from common.database import BotDatabase


@pytest.mark.asyncio
async def test_connect_creates_connection():
    """Test connect() establishes connection and sets state."""
    db = BotDatabase(':memory:')
    assert not db.is_connected
    assert db.conn is None
    
    await db.connect()
    
    assert db.is_connected
    assert db.conn is not None
    
    await db.close()


@pytest.mark.asyncio
async def test_connect_twice_raises_error():
    """Test connecting twice raises RuntimeError."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    with pytest.raises(RuntimeError, match="already connected"):
        await db.connect()
    
    await db.close()


@pytest.mark.asyncio
async def test_close_gracefully_handles_no_connection():
    """Test close() is safe when not connected."""
    db = BotDatabase(':memory:')
    
    # Should not raise - safe to call multiple times
    await db.close()
    await db.close()
    
    assert not db.is_connected


@pytest.mark.asyncio
async def test_migrations_create_all_tables():
    """Test _run_migrations() creates all required tables."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    # Check tables exist
    cursor = await db.conn.cursor()
    await cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = [row[0] for row in await cursor.fetchall()]
    
    # Expected tables from Sprint 9 schema
    expected = [
        'api_tokens',
        'channel_stats',
        'current_status',
        'outbound_messages',
        'recent_chat',
        'user_actions',
        'user_count_history',
        'user_stats'
    ]
    
    for table in expected:
        assert table in tables, f"Missing table: {table}"
    
    await db.close()


@pytest.mark.asyncio
async def test_close_commits_active_sessions():
    """Test close() updates active user sessions before closing."""
    # Use temp file instead of :memory: so we can reopen
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db2 = None
    try:
        db = BotDatabase(db_path)
        await db.connect()
        
        # Create user with active session (set time 1 second ago)
        cursor = await db.conn.cursor()
        now = int(time.time())
        await cursor.execute('''
            INSERT INTO user_stats 
            (username, first_seen, last_seen, current_session_start)
            VALUES ('Alice', ?, ?, ?)
        ''', (now - 1, now - 1, now - 1))
        await db.conn.commit()
        
        # Wait a moment to ensure time passes
        await asyncio.sleep(0.1)
        
        # Close database (should update session)
        await db.close()
        
        # Reopen and verify session was closed
        db2 = BotDatabase(db_path)
        await db2.connect()
        cursor2 = await db2.conn.cursor()
        await cursor2.execute('''
            SELECT current_session_start, total_time_connected
            FROM user_stats WHERE username = 'Alice'
        ''')
        row = await cursor2.fetchone()
        
        assert row[0] is None, "Session should be ended (current_session_start = NULL)"
        assert row[1] >= 1, "Time should be tracked (total_time_connected >= 1)"
        
    finally:
        # Ensure db2 is closed before cleanup
        if db2 and db2.is_connected:
            await db2.close()
        
        # Give Windows time to release file lock
        await asyncio.sleep(0.1)
        
        # Cleanup temp file
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # File still locked on Windows - ignore


@pytest.mark.asyncio
async def test_is_connected_property():
    """Test is_connected property reflects connection state."""
    db = BotDatabase(':memory:')
    
    # Initially not connected
    assert not db.is_connected
    
    # Connected after connect()
    await db.connect()
    assert db.is_connected
    
    # Not connected after close()
    await db.close()
    assert not db.is_connected


@pytest.mark.asyncio
async def test_connect_creates_indexes():
    """Test that connect() creates all required indexes."""
    db = BotDatabase(':memory:')
    await db.connect()
    
    cursor = await db.conn.cursor()
    await cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' 
        ORDER BY name
    """)
    indexes = [row[0] for row in await cursor.fetchall()]
    
    # Expected indexes from Sprint 9 schema
    expected_indexes = [
        'idx_api_tokens_revoked',
        'idx_outbound_sent',
        'idx_recent_chat_timestamp',
        'idx_user_count_timestamp'
    ]
    
    for index in expected_indexes:
        assert index in indexes, f"Missing index: {index}"
    
    await db.close()
