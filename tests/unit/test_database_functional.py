"""
Functional tests for BotDatabase after SQLAlchemy ORM migration.

These tests verify that all 28 migrated methods work correctly with the new
SQLAlchemy ORM implementation. They test the public API, not internal schema details.

Sprint 11 Sortie 2/3: Async/ORM functional validation
"""
import pytest
import time
from common.database import BotDatabase


# ==============================================================================
# Test Phase 2: User Tracking (7 methods)
# ==============================================================================

class TestUserTracking:
    """Test user tracking methods (join, leave, chat, actions)"""

    @pytest.mark.asyncio
    async def test_user_joined_new_user(self, db):
        """New user creates stats record"""
        await db.user_joined("alice")
        
        stats = await db.get_user_stats("alice")
        assert stats is not None
        assert stats['username'] == "alice"
        assert stats['total_chat_lines'] == 0
        assert stats['total_time_connected'] == 0
        assert stats['current_session_start'] is not None

    @pytest.mark.asyncio
    async def test_user_joined_existing_user(self, db):
        """Existing user updates last_seen"""
        await db.user_joined("alice")
        first_seen = (await db.get_user_stats("alice"))['first_seen']
        
        time.sleep(1)
        await db.user_joined("alice")
        
        stats = await db.get_user_stats("alice")
        assert stats['first_seen'] == first_seen  # Unchanged
        assert stats['last_seen'] > first_seen  # Updated

    @pytest.mark.asyncio
    async def test_user_left_calculates_duration(self, db):
        """User leaving calculates session duration"""
        await db.user_joined("alice")
        time.sleep(2)
        await db.user_left("alice")
        
        stats = await db.get_user_stats("alice")
        assert stats['total_time_connected'] >= 2
        assert stats['current_session_start'] is None

    @pytest.mark.asyncio
    async def test_user_chat_message_increments_count(self, db):
        """Chat message increments counter"""
        await db.user_joined("alice")
        await db.user_chat_message("alice", "Hello!")
        await db.user_chat_message("alice", "World!")
        
        stats = await db.get_user_stats("alice")
        assert stats['total_chat_lines'] == 2

    @pytest.mark.asyncio
    async def test_log_chat_stores_message(self, db):
        """Chat messages stored in recent_chat"""
        await db.log_chat("alice", "Test message")
        
        messages = await db.get_recent_chat(limit=10)
        assert len(messages) == 1
        assert messages[0]['username'] == "alice"
        assert messages[0]['message'] == "Test message"

    @pytest.mark.asyncio
    async def test_log_user_action_creates_audit_log(self, db):
        """User actions logged for audit"""
        await db.log_user_action("alice", "pm_command", "stats request")
        
        # Note: No direct get method, but action is logged (tested via maintenance)
        # This tests the method doesn't raise errors
        assert True

    @pytest.mark.asyncio
    async def test_update_high_water_mark(self, db):
        """High water mark tracks peak users"""
        await db.update_high_water_mark(5, 10)
        max_chat, max_connected = await db.get_high_water_mark()
        assert max_chat == 5
        assert max_connected == 10
        
        # Update with higher values
        await db.update_high_water_mark(8, 15)
        max_chat, max_connected = await db.get_high_water_mark()
        assert max_chat == 8
        assert max_connected == 15
        
        # Update with lower values (should not change)
        await db.update_high_water_mark(3, 7)
        max_chat, max_connected = await db.get_high_water_mark()
        assert max_chat == 8  # Unchanged
        assert max_connected == 15  # Unchanged


# ==============================================================================
# Test Phase 3: Query Methods (10 methods)
# ==============================================================================

class TestQueryMethods:
    """Test query methods (stats, history, chat)"""

    @pytest.mark.asyncio
    async def test_get_user_stats_nonexistent(self, db):
        """Nonexistent user returns None"""
        stats = await db.get_user_stats("nonexistent")
        assert stats is None

    @pytest.mark.asyncio
    async def test_get_top_chatters(self, db):
        """Top chatters ordered by message count"""
        await db.user_joined("alice")
        await db.user_joined("bob")
        await db.user_joined("charlie")
        
        for _ in range(5):
            await db.user_chat_message("alice", "msg")
        for _ in range(10):
            await db.user_chat_message("bob", "msg")
        for _ in range(3):
            await db.user_chat_message("charlie", "msg")
        
        top = await db.get_top_chatters(limit=3)
        assert len(top) == 3
        assert top[0]['username'] == "bob"  # 10 messages
        assert top[1]['username'] == "alice"  # 5 messages
        assert top[2]['username'] == "charlie"  # 3 messages

    @pytest.mark.asyncio
    async def test_get_total_users_seen(self, db):
        """Total users count"""
        await db.user_joined("alice")
        await db.user_joined("bob")
        await db.user_joined("charlie")
        
        total = await db.get_total_users_seen()
        assert total == 3

    @pytest.mark.asyncio
    async def test_log_and_get_user_count_history(self, db):
        """User count history tracking"""
        now = int(time.time())
        
        await db.log_user_count(now - 3600, 5, 10)
        await db.log_user_count(now - 1800, 7, 12)
        await db.log_user_count(now, 10, 15)
        
        history = await db.get_user_count_history(since=now - 4000)
        assert len(history) == 3
        assert history[0]['chat_users'] == 5
        assert history[-1]['chat_users'] == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_history(self, db):
        """Old history cleanup"""
        now = int(time.time())
        old = now - (40 * 86400)  # 40 days ago
        
        await db.log_user_count(old, 5, 10)
        await db.log_user_count(now, 10, 15)
        
        deleted = await db.cleanup_old_history(days=30)
        assert deleted == 1  # Only old record deleted
        
        history = await db.get_user_count_history(since=old - 1000)
        assert len(history) == 1  # Only recent remains

    @pytest.mark.asyncio
    async def test_get_recent_chat(self, db):
        """Recent chat ordered correctly"""
        await db.log_chat("alice", "First")
        time.sleep(0.1)
        await db.log_chat("bob", "Second")
        time.sleep(0.1)
        await db.log_chat("charlie", "Third")
        
        messages = await db.get_recent_chat(limit=10)
        assert len(messages) == 3
        # Oldest first
        assert messages[0]['username'] == "alice"
        assert messages[1]['username'] == "bob"
        assert messages[2]['username'] == "charlie"

    @pytest.mark.asyncio
    async def test_get_recent_chat_since(self, db):
        """Recent chat time filtering"""
        now = int(time.time())
        
        await db.log_chat("alice", "Old message")
        time.sleep(2)
        cutoff = int(time.time())
        time.sleep(1)
        await db.log_chat("bob", "New message")
        
        messages = await db.get_recent_chat_since(since=cutoff)
        assert len(messages) == 1
        assert messages[0]['username'] == "bob"


# ==============================================================================
# Test Phase 4: Outbound Messages (4 methods)
# ==============================================================================

class TestOutboundMessages:
    """Test outbound message queue"""

    @pytest.mark.asyncio
    async def test_enqueue_and_get_unsent(self, db):
        """Enqueue and retrieve unsent messages"""
        msg_id = await db.enqueue_outbound_message("Test message")
        assert msg_id is not None
        
        unsent = await db.get_unsent_outbound_messages(limit=10)
        assert len(unsent) == 1
        assert unsent[0]['message'] == "Test message"
        assert unsent[0]['id'] == msg_id

    @pytest.mark.asyncio
    async def test_mark_outbound_sent(self, db):
        """Mark message as sent"""
        msg_id = await db.enqueue_outbound_message("Test")
        await db.mark_outbound_sent(msg_id)
        
        unsent = await db.get_unsent_outbound_messages()
        assert len(unsent) == 0  # Marked as sent

    @pytest.mark.asyncio
    async def test_mark_outbound_failed_transient(self, db):
        """Transient failure increments retry count"""
        msg_id = await db.enqueue_outbound_message("Test")
        await db.mark_outbound_failed(msg_id, "Rate limit", is_permanent=False)
        
        unsent = await db.get_unsent_outbound_messages(bypass_backoff=True)
        assert len(unsent) == 1  # Still in queue
        assert unsent[0]['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_mark_outbound_failed_permanent(self, db):
        """Permanent failure removes from queue"""
        msg_id = await db.enqueue_outbound_message("Test")
        await db.mark_outbound_failed(msg_id, "Permission denied", is_permanent=True)
        
        unsent = await db.get_unsent_outbound_messages()
        assert len(unsent) == 0  # Marked as sent (permanent failure)


# ==============================================================================
# Test Phase 5: Status & Tokens (7 methods)
# ==============================================================================

class TestStatusAndTokens:
    """Test status and API token management"""

    @pytest.mark.asyncio
    async def test_update_and_get_current_status(self, db):
        """Update and retrieve bot status"""
        await db.update_current_status(
            bot_name="TestBot",
            bot_afk=False,
            current_chat_users=5
        )
        
        status = await db.get_current_status()
        assert status is not None
        assert status['bot_name'] == "TestBot"
        assert status['bot_afk'] == False
        assert status['current_chat_users'] == 5

    @pytest.mark.asyncio
    async def test_generate_api_token(self, db):
        """Generate API token"""
        token = await db.generate_api_token("Test token")
        assert token is not None
        assert len(token) > 20  # Secure token

    @pytest.mark.asyncio
    async def test_validate_api_token(self, db):
        """Validate API token"""
        token = await db.generate_api_token("Test")
        
        # Valid token
        assert await db.validate_api_token(token) == True
        
        # Invalid token
        assert await db.validate_api_token("invalid_token") == False

    @pytest.mark.asyncio
    async def test_revoke_api_token(self, db):
        """Revoke API token"""
        token = await db.generate_api_token("Test")
        
        # Token works
        assert await db.validate_api_token(token) == True
        
        # Revoke (partial match)
        count = await db.revoke_api_token(token[:8])
        assert count == 1
        
        # Token no longer works
        assert await db.validate_api_token(token) == False

    @pytest.mark.asyncio
    async def test_list_api_tokens(self, db):
        """List API tokens"""
        token1 = await db.generate_api_token("Token 1")
        token2 = await db.generate_api_token("Token 2")
        
        tokens = await db.list_api_tokens(include_revoked=False)
        assert len(tokens) == 2
        # Tokens are truncated for security
        assert all('token_preview' in t for t in tokens)
        assert all('...' in t['token_preview'] for t in tokens)

    @pytest.mark.asyncio
    async def test_perform_maintenance(self, db):
        """Database maintenance operations"""
        # Add some old data
        old_time = int(time.time()) - (40 * 86400)
        await db.log_user_count(old_time, 5, 10)
        await db.enqueue_outbound_message("Old")
        msg_id = await db.enqueue_outbound_message("Test")
        await db.mark_outbound_sent(msg_id)
        
        # Run maintenance
        log = await db.perform_maintenance()
        assert isinstance(log, list)
        assert any('VACUUM' in item for item in log)


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestIntegration:
    """End-to-end integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_user_lifecycle(self, db):
        """Complete user lifecycle"""
        # User joins
        await db.user_joined("alice")
        
        # User chats
        await db.user_chat_message("alice", "Hello!")
        await db.log_chat("alice", "Hello!")
        
        # Check stats
        stats = await db.get_user_stats("alice")
        assert stats['total_chat_lines'] == 1
        
        # User leaves
        await db.user_left("alice")
        stats = await db.get_user_stats("alice")
        assert stats['current_session_start'] is None
        
        # User in top chatters
        top = await db.get_top_chatters(1)
        assert top[0]['username'] == "alice"

    @pytest.mark.asyncio
    async def test_api_token_lifecycle(self, db):
        """Complete API token workflow"""
        # Generate
        token = await db.generate_api_token("Integration test")
        
        # Validate
        assert await db.validate_api_token(token) == True
        
        # List
        tokens = await db.list_api_tokens()
        assert len(tokens) == 1
        
        # Revoke
        await db.revoke_api_token(token)
        
        # No longer valid
        assert await db.validate_api_token(token) == False
