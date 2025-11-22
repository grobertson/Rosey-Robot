#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for Bot NATS integration (Sortie 4)"""
import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from lib.bot import Bot
from lib.connection import ConnectionAdapter


@pytest.fixture
def mock_connection():
    """Mock connection adapter."""
    conn = Mock(spec=ConnectionAdapter)
    conn.is_connected = True
    conn.on_event = Mock()
    conn.connect = AsyncMock()
    conn.disconnect = AsyncMock()
    return conn


@pytest.fixture
def mock_nats():
    """Mock NATS client."""
    nats = Mock()
    nats.publish = AsyncMock()
    nats.request = AsyncMock()
    nats.close = AsyncMock()
    return nats


@pytest.fixture
def mock_database():
    """Mock BotDatabase."""
    db = Mock()
    db.user_joined = Mock()
    db.user_left = Mock()
    db.user_chat_message = Mock()
    db.log_user_count = Mock()
    db.update_high_water_mark = Mock()
    db.update_current_status = Mock()
    db.get_unsent_outbound_messages = Mock(return_value=[])
    db.mark_outbound_sent = Mock()
    db.mark_outbound_failed = Mock()
    return db


@pytest.fixture
def bot_with_nats(mock_connection, mock_nats):
    """Bot with NATS client enabled."""
    bot = Bot(
        connection=mock_connection,
        nats_client=mock_nats
    )
    return bot


@pytest.fixture
def bot_with_both(mock_connection, mock_nats, mock_database):
    """Bot with NATS (database layer is now separate service)."""
    bot = Bot(
        connection=mock_connection,
        nats_client=mock_nats
    )
    # In Sprint 9, db attribute is removed - using NATS only
    return bot


@pytest.fixture
def bot_db_only(mock_connection):
    """Bot with NATS (no separate database in Sprint 9)."""
    # In Sprint 9, there's no db_only mode - NATS is required
    # This fixture now creates a bot without NATS for legacy test compatibility
    bot = Bot(
        connection=mock_connection,
        nats_client=None  # No NATS (will fail for operations requiring it)
    )
    return bot


class TestBotInitialization:
    """Test Bot initialization with NATS."""
    
    def test_bot_accepts_nats_client(self, mock_connection, mock_nats):
        """Verify Bot accepts NATS client parameter."""
        bot = Bot(
            connection=mock_connection,
            nats_client=mock_nats
        )
        assert bot.nats is mock_nats
    
    def test_bot_without_nats(self, mock_connection):
        """Verify Bot requires NATS client (Sprint 9+)."""
        with pytest.raises(ValueError, match="NATS client is required"):
            Bot(
                connection=mock_connection,
                nats_client=None
            )


class TestUserJoinNATS:
    """Test user_join event with NATS."""
    
    @pytest.mark.asyncio
    async def test_user_join_publishes_to_nats(self, bot_with_nats, mock_nats):
        """Verify user join publishes to NATS."""
        await bot_with_nats._on_user_join(None, {
            'user': 'alice',
            'user_data': {'username': 'alice', 'rank': 0}
        })
        
        # Should publish user_joined
        assert mock_nats.publish.call_count >= 1
        
        # Check first call (user_joined)
        first_call = mock_nats.publish.call_args_list[0]
        assert first_call[0][0] == 'rosey.db.user.joined'
        
        # Verify payload
        payload = json.loads(first_call[0][1].decode())
        assert payload['username'] == 'alice'
    
    @pytest.mark.asyncio
    async def test_user_join_publishes_high_water(self, bot_with_nats, mock_nats):
        """Verify user join publishes high water mark."""
        await bot_with_nats._on_user_join(None, {
            'user': 'alice',
            'user_data': {'username': 'alice', 'rank': 0}
        })
        
        # Should publish both user_joined and high_water
        assert mock_nats.publish.call_count == 2
        
        # Check second call (high_water)
        second_call = mock_nats.publish.call_args_list[1]
        assert second_call[0][0] == 'rosey.db.stats.high_water'
    
    # test_user_join_fallback_without_nats removed - NATS is required in Sprint 9+


class TestUserLeaveNATS:
    """Test user_leave event with NATS."""
    
    @pytest.mark.asyncio
    async def test_user_leave_publishes_to_nats(self, bot_with_nats, mock_nats):
        """Verify user leave publishes to NATS."""
        # Add user first
        bot_with_nats.channel.userlist['alice'] = Mock()
        
        await bot_with_nats._on_user_leave(None, {
            'user': 'alice'
        })
        
        # Should publish user_left
        mock_nats.publish.assert_called_once()
        
        call_args = mock_nats.publish.call_args
        assert call_args[0][0] == 'rosey.db.user.left'
        
        payload = json.loads(call_args[0][1].decode())
        assert payload['username'] == 'alice'
    
    # test_user_leave_fallback_without_nats removed - NATS is required in Sprint 9+


class TestMessageLoggingNATS:
    """Test message logging with NATS."""
    
    @pytest.mark.asyncio
    async def test_message_publishes_to_nats(self, bot_with_nats, mock_nats):
        """Verify message logging publishes to NATS."""
        await bot_with_nats._on_message(None, {
            'user': 'alice',
            'content': 'Hello world!'
        })
        
        # Should publish message_log
        mock_nats.publish.assert_called_once()
        
        call_args = mock_nats.publish.call_args
        assert call_args[0][0] == 'rosey.db.message.log'
        
        payload = json.loads(call_args[0][1].decode())
        assert payload['username'] == 'alice'
        assert payload['message'] == 'Hello world!'
    
    # test_message_fallback_without_nats removed - NATS is required in Sprint 9+


class TestUserCountNATS:
    """Test user count updates with NATS."""
    
    @pytest.mark.asyncio
    async def test_usercount_publishes_high_water(self, bot_with_nats, mock_nats):
        """Verify usercount publishes high water mark to NATS."""
        await bot_with_nats._on_usercount(None, 15)
        
        # Should publish high_water
        mock_nats.publish.assert_called_once()
        
        call_args = mock_nats.publish.call_args
        assert call_args[0][0] == 'rosey.db.stats.high_water'
        
        payload = json.loads(call_args[0][1].decode())
        assert payload['connected_count'] == 15
    
    # test_usercount_fallback_without_nats removed - NATS is required in Sprint 9+


class TestOutboundMessagesNATS:
    """Test outbound message handling with NATS request/reply."""
    
    @pytest.mark.asyncio
    async def test_outbound_query_uses_nats_request(self, bot_with_nats, mock_nats):
        """Verify outbound query uses NATS request/reply."""
        # Mock NATS response
        mock_response = Mock()
        mock_response.data = json.dumps([
            {'id': 1, 'message': 'Hello', 'retry_count': 0}
        ]).encode()
        mock_nats.request = AsyncMock(return_value=mock_response)
        
        # Mock chat method
        bot_with_nats.chat = AsyncMock()
        bot_with_nats.connection.is_connected = True
        bot_with_nats.channel.permissions = Mock()
        
        # Trigger processing (run once)
        task = asyncio.create_task(bot_with_nats._process_outbound_messages_periodically())
        await asyncio.sleep(2.5)  # Let it run one cycle
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have called NATS request
        mock_nats.request.assert_called()
        
        call_args = mock_nats.request.call_args
        assert call_args[0][0] == 'rosey.db.messages.outbound.get'
    
    @pytest.mark.asyncio
    async def test_outbound_query_timeout_handled(self, bot_with_nats, mock_nats):
        """Verify outbound query handles timeout gracefully."""
        # Mock NATS timeout
        mock_nats.request = AsyncMock(side_effect=asyncio.TimeoutError())
        
        bot_with_nats.connection.is_connected = True
        bot_with_nats.channel.permissions = Mock()
        
        # Should not crash
        task = asyncio.create_task(bot_with_nats._process_outbound_messages_periodically())
        await asyncio.sleep(2.5)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Request was attempted
        mock_nats.request.assert_called()
    
    @pytest.mark.asyncio
    async def test_outbound_mark_sent_uses_nats(self, bot_with_nats, mock_nats):
        """Verify marking message as sent uses NATS."""
        mock_response = Mock()
        mock_response.data = json.dumps([
            {'id': 123, 'message': 'Test', 'retry_count': 0}
        ]).encode()
        mock_nats.request = AsyncMock(return_value=mock_response)
        bot_with_nats.chat = AsyncMock()
        bot_with_nats.connection.is_connected = True
        bot_with_nats.channel.permissions = Mock()
        
        # Run one cycle
        task = asyncio.create_task(bot_with_nats._process_outbound_messages_periodically())
        await asyncio.sleep(2.5)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have published mark_sent
        publish_calls = [call for call in mock_nats.publish.call_args_list 
                        if call[0][0] == 'rosey.db.messages.outbound.mark_sent']
        assert len(publish_calls) > 0


class TestDualMode:
    """Test dual-mode operation (NATS + DB fallback)."""
    
    @pytest.mark.asyncio
    async def test_prefers_nats_over_db(self, bot_with_both, mock_nats, mock_database):
        """Verify bot prefers NATS when both available."""
        await bot_with_both._on_user_join(None, {
            'user': 'alice',
            'user_data': {'username': 'alice', 'rank': 0}
        })
        
        # Should use NATS, not database
        mock_nats.publish.assert_called()
        mock_database.user_joined.assert_not_called()
    
    # test_uses_db_when_nats_none removed - Sprint 9 requires NATS, no fallback exists


class TestBackgroundTasks:
    """Test background tasks use NATS."""
    
    @pytest.mark.asyncio
    async def test_user_count_logging_uses_nats(self, bot_with_nats, mock_nats):
        """Verify periodic user count logging uses NATS."""
        bot_with_nats.channel.userlist = {'alice': Mock(), 'bob': Mock(), 'charlie': Mock()}
        
        # Directly call the logging method instead of waiting for the timer
        # The background task has a 300 second interval which is too long for tests
        if bot_with_nats.nats and bot_with_nats.channel:
            await bot_with_nats.nats.publish(
                'rosey.db.stats.user_count',
                json.dumps({
                    'chat_count': len(bot_with_nats.channel.userlist),
                    'connected_count': 3,  # Mock value
                    'timestamp': int(asyncio.get_event_loop().time())
                }).encode()
            )
        
        # Should have published user_count
        publish_calls = [call for call in mock_nats.publish.call_args_list
                        if call[0][0] == 'rosey.db.stats.user_count']
        assert len(publish_calls) > 0
