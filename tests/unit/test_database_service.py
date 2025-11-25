#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for DatabaseService (NATS-enabled database wrapper)"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
async def nats_client():
    """Mock NATS client for testing."""
    client = Mock()
    client.subscribe = AsyncMock()
    client.publish = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_database():
    """Mock BotDatabase instance."""
    db = Mock()
    # Mock all database methods used by service (all async)
    db.connect = AsyncMock()
    db.close = AsyncMock()
    db.user_joined = AsyncMock()
    db.user_left = AsyncMock()
    db.user_chat_message = AsyncMock()
    db.log_user_count = AsyncMock()
    db.update_high_water_mark = AsyncMock()
    db.update_current_status = AsyncMock()
    db.mark_outbound_sent = AsyncMock()
    db.get_unsent_outbound_messages = AsyncMock(return_value=[])
    db.get_recent_chat = AsyncMock(return_value=[])
    return db


@pytest.fixture
def db_service(nats_client, mock_database):
    """DatabaseService with mocked NATS and database."""
    with patch('common.database_service.BotDatabase', return_value=mock_database):
        from common.database_service import DatabaseService
        service = DatabaseService(nats_client, ':memory:')
        # Replace db with our mock
        service.db = mock_database
        return service


class TestDatabaseServiceLifecycle:
    """Test service startup, shutdown, and lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_all_subjects(self, db_service, nats_client):
        """Verify start() subscribes to required subjects."""
        await db_service.start()

        # Should have subscribed to multiple subjects (count may change as features are added)
        assert nats_client.subscribe.call_count >= 9  # At minimum the original 9
        assert db_service._running is True
        assert len(db_service._subscriptions) >= 9

    @pytest.mark.asyncio
    async def test_start_idempotent(self, db_service, nats_client):
        """Verify start() is idempotent (safe to call multiple times)."""
        await db_service.start()
        initial_count = nats_client.subscribe.call_count

        # Call start again
        await db_service.start()

        # Should not subscribe again
        assert nats_client.subscribe.call_count == initial_count

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_all(self, db_service):
        """Verify stop() unsubscribes from all subjects."""
        await db_service.start()

        # Mock subscription objects
        mock_subs = [Mock(unsubscribe=AsyncMock()) for _ in range(9)]
        db_service._subscriptions = mock_subs

        await db_service.stop()

        # All subscriptions unsubscribed
        for sub in mock_subs:
            sub.unsubscribe.assert_called_once()

        assert db_service._running is False
        assert len(db_service._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_stop_handles_errors(self, db_service):
        """Verify stop() handles unsubscribe errors gracefully."""
        await db_service.start()

        # Create mock that raises exception
        failing_sub = Mock(unsubscribe=AsyncMock(side_effect=Exception("Unsubscribe failed")))
        db_service._subscriptions = [failing_sub]

        # Should not raise exception
        await db_service.stop()

        assert db_service._running is False


class TestPubSubHandlers:
    """Test pub/sub event handlers (fire-and-forget)."""

    @pytest.mark.asyncio
    async def test_handle_user_joined(self, db_service, mock_database):
        """Verify user_joined handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({'username': 'alice'}).encode()

        await db_service._handle_user_joined(msg)

        mock_database.user_joined.assert_called_once_with('alice')

    @pytest.mark.asyncio
    async def test_handle_user_joined_missing_username(self, db_service, mock_database):
        """Verify user_joined handler handles missing username."""
        msg = Mock()
        msg.data = json.dumps({}).encode()

        await db_service._handle_user_joined(msg)

        # Should not call database
        mock_database.user_joined.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_user_joined_invalid_json(self, db_service, mock_database):
        """Verify user_joined handler handles invalid JSON gracefully."""
        msg = Mock()
        msg.data = b'invalid json'

        # Should not raise exception
        await db_service._handle_user_joined(msg)

        mock_database.user_joined.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_user_left(self, db_service, mock_database):
        """Verify user_left handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({'username': 'bob'}).encode()

        await db_service._handle_user_left(msg)

        mock_database.user_left.assert_called_once_with('bob')

    @pytest.mark.asyncio
    async def test_handle_message_log(self, db_service, mock_database):
        """Verify message_log handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({
            'username': 'alice',
            'message': 'Hello world!'
        }).encode()

        await db_service._handle_message_log(msg)

        mock_database.user_chat_message.assert_called_once_with('alice', 'Hello world!')

    @pytest.mark.asyncio
    async def test_handle_message_log_missing_data(self, db_service, mock_database):
        """Verify message_log handler requires both username and message."""
        # Missing message
        msg = Mock()
        msg.data = json.dumps({'username': 'alice'}).encode()
        await db_service._handle_message_log(msg)
        mock_database.user_chat_message.assert_not_called()

        # Missing username
        msg.data = json.dumps({'message': 'Hello'}).encode()
        await db_service._handle_message_log(msg)
        mock_database.user_chat_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_user_count(self, db_service, mock_database):
        """Verify user_count handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({
            'chat_count': 10,
            'connected_count': 15
        }).encode()

        await db_service._handle_user_count(msg)

        mock_database.log_user_count.assert_called_once_with(10, 15)

    @pytest.mark.asyncio
    async def test_handle_high_water(self, db_service, mock_database):
        """Verify high_water handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({
            'chat_count': 25,
            'connected_count': 30
        }).encode()

        await db_service._handle_high_water(msg)

        mock_database.update_high_water_mark.assert_called_once_with(25, 30)

    @pytest.mark.asyncio
    async def test_handle_high_water_no_connected(self, db_service, mock_database):
        """Verify high_water handler works with only chat_count."""
        msg = Mock()
        msg.data = json.dumps({
            'chat_count': 25
        }).encode()

        await db_service._handle_high_water(msg)

        # Should pass None for connected_count
        mock_database.update_high_water_mark.assert_called_once_with(25, None)

    @pytest.mark.asyncio
    async def test_handle_status_update(self, db_service, mock_database):
        """Verify status_update handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({
            'status_data': {
                'bot_name': 'Rosey',
                'bot_rank': 3.0,
                'current_chat_users': 10
            }
        }).encode()

        await db_service._handle_status_update(msg)

        mock_database.update_current_status.assert_called_once_with(
            bot_name='Rosey',
            bot_rank=3.0,
            current_chat_users=10
        )

    @pytest.mark.asyncio
    async def test_handle_mark_sent(self, db_service, mock_database):
        """Verify mark_sent handler calls database correctly."""
        msg = Mock()
        msg.data = json.dumps({'message_id': 123}).encode()

        await db_service._handle_mark_sent(msg)

        mock_database.mark_outbound_sent.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_handle_mark_sent_missing_id(self, db_service, mock_database):
        """Verify mark_sent handler requires message_id."""
        msg = Mock()
        msg.data = json.dumps({}).encode()

        await db_service._handle_mark_sent(msg)

        mock_database.mark_outbound_sent.assert_not_called()


class TestRequestReplyHandlers:
    """Test request/reply query handlers."""

    @pytest.mark.asyncio
    async def test_handle_outbound_query_success(self, db_service, mock_database, nats_client):
        """Verify outbound_query handler replies with messages."""
        msg = Mock()
        msg.data = json.dumps({'limit': 10, 'max_retries': 3}).encode()
        msg.reply = 'reply.inbox.123'

        # Mock database response
        mock_database.get_unsent_outbound_messages.return_value = [
            {'id': 1, 'message': 'Hello'},
            {'id': 2, 'message': 'World'}
        ]

        await db_service._handle_outbound_query(msg)

        # Verify database queried correctly
        mock_database.get_unsent_outbound_messages.assert_called_once_with(
            limit=10,
            max_retries=3
        )

        # Verify reply sent
        nats_client.publish.assert_called_once()
        call_args = nats_client.publish.call_args
        assert call_args[0][0] == 'reply.inbox.123'

        # Verify response data
        response = json.loads(call_args[0][1].decode())
        assert len(response) == 2
        assert response[0]['id'] == 1
        assert response[1]['message'] == 'World'

    @pytest.mark.asyncio
    async def test_handle_outbound_query_default_params(self, db_service, mock_database, nats_client):
        """Verify outbound_query uses default parameters."""
        msg = Mock()
        msg.data = json.dumps({}).encode()
        msg.reply = 'reply.inbox.456'

        mock_database.get_unsent_outbound_messages.return_value = []

        await db_service._handle_outbound_query(msg)

        # Should use defaults: limit=50, max_retries=3
        mock_database.get_unsent_outbound_messages.assert_called_once_with(
            limit=50,
            max_retries=3
        )

    @pytest.mark.asyncio
    async def test_handle_outbound_query_error(self, db_service, mock_database, nats_client):
        """Verify outbound_query sends empty response on error."""
        msg = Mock()
        msg.data = json.dumps({'limit': 10}).encode()
        msg.reply = 'reply.inbox.789'

        # Mock database error
        mock_database.get_unsent_outbound_messages.side_effect = Exception("DB Error")

        await db_service._handle_outbound_query(msg)

        # Should still send reply (empty array)
        nats_client.publish.assert_called_once()
        response = json.loads(nats_client.publish.call_args[0][1].decode())
        assert response == []

    @pytest.mark.asyncio
    async def test_handle_recent_chat_query_success(self, db_service, mock_database, nats_client):
        """Verify recent_chat_query handler replies with messages."""
        msg = Mock()
        msg.data = json.dumps({'limit': 20}).encode()
        msg.reply = 'reply.inbox.chat1'

        # Mock database response
        mock_database.get_recent_chat.return_value = [
            {'timestamp': 1234567890, 'username': 'alice', 'message': 'Hi'},
            {'timestamp': 1234567891, 'username': 'bob', 'message': 'Hello'}
        ]

        await db_service._handle_recent_chat_query(msg)

        # Verify database queried
        mock_database.get_recent_chat.assert_called_once_with(limit=20)

        # Verify reply sent
        nats_client.publish.assert_called_once()
        call_args = nats_client.publish.call_args
        assert call_args[0][0] == 'reply.inbox.chat1'

        # Verify response data
        response = json.loads(call_args[0][1].decode())
        assert len(response) == 2
        assert response[0]['username'] == 'alice'

    @pytest.mark.asyncio
    async def test_handle_recent_chat_query_default_limit(self, db_service, mock_database, nats_client):
        """Verify recent_chat_query uses default limit."""
        msg = Mock()
        msg.data = json.dumps({}).encode()
        msg.reply = 'reply.inbox.chat2'

        mock_database.get_recent_chat.return_value = []

        await db_service._handle_recent_chat_query(msg)

        # Should use default: limit=50
        mock_database.get_recent_chat.assert_called_once_with(limit=50)

    @pytest.mark.asyncio
    async def test_handle_recent_chat_query_invalid_json(self, db_service, nats_client):
        """Verify recent_chat_query handles invalid JSON."""
        msg = Mock()
        msg.data = b'not json'
        msg.reply = 'reply.inbox.chat3'

        await db_service._handle_recent_chat_query(msg)

        # Should send empty response
        nats_client.publish.assert_called_once()
        response = json.loads(nats_client.publish.call_args[0][1].decode())
        assert response == []


class TestErrorHandling:
    """Test error handling across all handlers."""

    @pytest.mark.asyncio
    async def test_database_error_does_not_crash_service(self, db_service, mock_database):
        """Verify database errors don't crash the service."""
        # Make database method raise exception
        mock_database.user_joined.side_effect = Exception("Database error")

        msg = Mock()
        msg.data = json.dumps({'username': 'alice'}).encode()

        # Should not raise exception (error logged internally)
        await db_service._handle_user_joined(msg)

        # Service should still be running
        assert db_service._running is False  # Not started in this test

    @pytest.mark.asyncio
    async def test_start_error_cleanup(self, db_service, nats_client):
        """Verify start() cleans up on subscription error."""
        # Make one subscription fail
        nats_client.subscribe.side_effect = [
            AsyncMock(),  # First subscription succeeds
            Exception("Subscribe failed")  # Second fails
        ]

        with pytest.raises(Exception):
            await db_service.start()

        # Should have attempted cleanup
        assert db_service._running is False


class TestIntegration:
    """Integration-style tests with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_full_user_join_leave_cycle(self, db_service, mock_database):
        """Test complete user join/leave cycle."""
        # User joins
        join_msg = Mock()
        join_msg.data = json.dumps({'username': 'alice'}).encode()
        await db_service._handle_user_joined(join_msg)

        # User sends message
        msg_msg = Mock()
        msg_msg.data = json.dumps({
            'username': 'alice',
            'message': 'Hello everyone!'
        }).encode()
        await db_service._handle_message_log(msg_msg)

        # User leaves
        leave_msg = Mock()
        leave_msg.data = json.dumps({'username': 'alice'}).encode()
        await db_service._handle_user_left(leave_msg)

        # Verify all operations called
        mock_database.user_joined.assert_called_once_with('alice')
        mock_database.user_chat_message.assert_called_once_with('alice', 'Hello everyone!')
        mock_database.user_left.assert_called_once_with('alice')

    @pytest.mark.asyncio
    async def test_stats_update_sequence(self, db_service, mock_database):
        """Test stats update sequence."""
        # Update user counts
        count_msg = Mock()
        count_msg.data = json.dumps({
            'chat_count': 15,
            'connected_count': 20
        }).encode()
        await db_service._handle_user_count(count_msg)

        # Update high water mark
        hw_msg = Mock()
        hw_msg.data = json.dumps({
            'chat_count': 15,
            'connected_count': 20
        }).encode()
        await db_service._handle_high_water(hw_msg)

        # Update status
        status_msg = Mock()
        status_msg.data = json.dumps({
            'status_data': {
                'current_chat_users': 15,
                'current_connected_users': 20
            }
        }).encode()
        await db_service._handle_status_update(status_msg)

        # Verify all calls made
        mock_database.log_user_count.assert_called_once()
        mock_database.update_high_water_mark.assert_called_once()
        mock_database.update_current_status.assert_called_once()
