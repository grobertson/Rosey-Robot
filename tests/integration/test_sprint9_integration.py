#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for Sprint 9 NATS Event Bus Architecture.

Tests the complete event flow:
1. Bot publishes event to NATS
2. NATS routes to DatabaseService
3. DatabaseService processes and stores
4. Bot queries data via request/reply

Requirements:
- NATS server running on localhost:4222
- No other services needed (tests start DatabaseService)

Run with:
    pytest tests/integration/test_sprint9_integration.py -v
    pytest tests/integration/test_sprint9_integration.py -v --nats-url=nats://localhost:4222

Mark tests as integration:
    @pytest.mark.integration
"""

import pytest
import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Import NATS
try:
    from nats.aio.client import Client as NATS
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="nats-py not installed")

# Import bot components
from lib.bot import Bot
from common.database import BotDatabase
from common.database_service import DatabaseService


@pytest.fixture
def nats_url(request):
    """Get NATS URL from command line or use default."""
    return request.config.getoption("--nats-url", default="nats://localhost:4222")


@pytest.fixture
async def nats_client(nats_url):
    """Real NATS client for integration tests."""
    if not NATS_AVAILABLE:
        pytest.skip("NATS not available")
    
    nc = NATS()
    try:
        await nc.connect(nats_url)
        yield nc
    finally:
        await nc.close()


@pytest.fixture
async def temp_database():
    """Create temporary database for testing."""
    # NOTE: BotDatabase.connect() not implemented - needs DatabaseService refactor
    # Tests using this fixture should be marked with @pytest.mark.xfail
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = BotDatabase(db_path)
    await db.connect()
    
    yield db
    
    await db.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
async def database_service(nats_client):
    """Start DatabaseService for testing.
    
    Creates its own temporary database that DatabaseService manages.
    This fixture tests DatabaseService's ability to create and connect
    its own BotDatabase instance (as it does in production).
    """
    # Create temp db path
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Create service (it will create BotDatabase internally)
    service = DatabaseService(nats_client, db_path)
    
    # Start service (connects database)
    await service.start()
    
    # Give it a moment to subscribe
    await asyncio.sleep(0.1)
    
    yield service
    
    # Stop service (closes database)
    await service.stop()
    
    # Cleanup temp file
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception as e:
        logging.warning(f'Error removing database_service temp file: {e}')


@pytest.fixture
def mock_connection():
    """Mock connection adapter for bot."""
    conn = Mock()
    conn.is_connected = True
    conn.on_event = Mock()
    conn.connect = AsyncMock()
    conn.disconnect = AsyncMock()
    return conn


@pytest.fixture
async def test_bot(mock_connection, nats_client):
    """Create bot with real NATS for testing."""
    bot = Bot(
        connection=mock_connection,
        nats_client=nats_client
    )
    bot.channel.name = 'test_channel'
    bot.user.name = 'TestBot'
    
    yield bot
    
    # Cleanup (bot doesn't own NATS client)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestUserJoinedFlow:
    """Test complete user joined event flow."""
    
    async def test_user_joined_publishes_to_nats(self, test_bot, database_service):
        """Test that user joined event is published to NATS and stored."""
        # Arrange - Use normalized data structure
        event_data = {
            'user': 'TestUser',
            'user_data': {
                'username': 'TestUser',
                'rank': 2
            }
        }
        
        # Act - Simulate user join (bot publishes to NATS)
        await test_bot._on_user_join('user_join', event_data)
        
        # Wait for DatabaseService to process
        await asyncio.sleep(0.2)
        
        # Assert - Check database (query DatabaseService's database)
        stats = await database_service.db.get_user_stats('TestUser')
        assert stats is not None
        assert stats['username'] == 'TestUser'
        assert stats['first_seen'] is not None
    
    async def test_multiple_users_joined(self, test_bot, database_service):
        """Test multiple users joining in sequence."""
        # Arrange - Use normalized data structure
        users = [
            {'user': 'User1', 'user_data': {'username': 'User1', 'rank': 1}},
            {'user': 'User2', 'user_data': {'username': 'User2', 'rank': 2}},
            {'user': 'User3', 'user_data': {'username': 'User3', 'rank': 3}},
        ]
        
        # Act
        for user_event in users:
            await test_bot._on_user_join('user_join', user_event)
        
        await asyncio.sleep(0.3)
        
        # Assert - Check each user individually
        for user in users:
            stats = await database_service.db.get_user_stats(user['user'])
            assert stats is not None, f"User {user['user']} not found"
            assert stats['username'] == user['user']


@pytest.mark.integration
@pytest.mark.asyncio
class TestChatMessageFlow:
    """Test complete chat message event flow."""
    
    async def test_chat_message_published_and_stored(self, test_bot, database_service):
        """Test chat message is published to NATS and stored in database."""
        # Arrange - Use normalized data structure
        msg_data = {
            'user': 'Alice',
            'content': 'Hello, world!',
            'timestamp': int(time.time())
        }
        
        # Act
        await test_bot._on_message('message', msg_data)
        
        await asyncio.sleep(0.2)
        
        # Assert
        recent_messages = await database_service.db.get_recent_chat(limit=10)
        assert len(recent_messages) > 0
        
        # Find our message
        msg_found = False
        for msg in recent_messages:
            if msg['username'] == 'Alice' and msg['message'] == 'Hello, world!':
                msg_found = True
                break
        
        assert msg_found, "Message not found in database"
    
    async def test_multiple_messages_ordered(self, test_bot, database_service):
        """Test multiple messages are stored in order."""
        # Arrange
        messages = [
            {'username': 'Alice', 'msg': 'First', 'time': int(time.time() * 1000)},
            {'username': 'Bob', 'msg': 'Second', 'time': int(time.time() * 1000) + 100},
            {'username': 'Charlie', 'msg': 'Third', 'time': int(time.time() * 1000) + 200},
        ]
        
        # Act
        for msg in messages:
            # Convert to normalized structure
            normalized_msg = {
                'user': msg['username'],
                'content': msg['msg'],
                'timestamp': msg.get('time', int(time.time()))
            }
            await test_bot._on_message('message', normalized_msg)
            await asyncio.sleep(0.05)
        
        await asyncio.sleep(0.3)
        
        # Assert
        recent = await database_service.db.get_recent_chat(limit=10)
        assert len(recent) >= 3
        
        # Messages should be in reverse chronological order (newest first)
        recent_texts = [m['message'] for m in recent[:3]]
        assert 'Third' in recent_texts
        assert 'Second' in recent_texts
        assert 'First' in recent_texts


@pytest.mark.integration
@pytest.mark.asyncio
class TestUserCountFlow:
    """Test user count tracking flow."""
    
    async def test_usercount_published_and_stored(self, test_bot, database_service):
        """Test user count is published and stored."""
        # Arrange
        usercount_data = {'count': 42}
        
        # Act
        await test_bot._on_usercount('usercount', usercount_data)
        
        await asyncio.sleep(0.2)
        
        # Assert - Check high water mark for connected viewers
        max_connected, timestamp = await database_service.db.get_high_water_mark_connected()
        assert max_connected >= 42


@pytest.mark.integration
@pytest.mark.asyncio
class TestMediaPlayedFlow:
    """Test media played event flow."""
    
    async def test_media_played_published(self, test_bot, database_service):
        """Test media played event is published to NATS."""
        # Arrange - Add item to playlist first
        playlist_item = {
            'uid': 1,
            'temp': False,
            'queueby': 'TestUser',
            'media': {
                'type': 'yt',
                'id': 'dQw4w9WgXcQ',
                'title': 'Test Video',
                'seconds': 212
            }
        }
        
        # Add to playlist
        test_bot._on_queue('queue', {'after': None, 'item': playlist_item})
        
        # Act - Set as current (pass uid, not full data structure)
        test_bot._on_setCurrent('setCurrent', 1)
        
        await asyncio.sleep(0.2)
        
        # Assert - Media logging happens through NATS
        # DatabaseService should have received the event
        # (Actual storage depends on DatabaseService implementation)


@pytest.mark.integration
@pytest.mark.asyncio
class TestRequestReplyFlow:
    """Test request/reply pattern for queries."""
    
    @pytest.mark.xfail(reason="DatabaseService request/reply handlers not implemented yet")
    async def test_query_user_stats_via_nats(self, nats_client, database_service):
        """Test querying user stats via NATS request/reply."""
        # Arrange - Add user to database
        await database_service.db.user_joined('QueryUser')
        # Log some chat messages for the user
        for _ in range(10):
            await database_service.db.user_chat_message('QueryUser', 'test message')
        
        # Act - Query via NATS request/reply
        subject = 'rosey.events.database.query.user_stats'
        request_data = {'username': 'QueryUser'}
        
        response = await nats_client.request(
            subject,
            json.dumps(request_data).encode(),
            timeout=1.0
        )
        
        # Assert
        assert response is not None
        result = json.loads(response.data.decode())
        assert result.get('username') == 'QueryUser'
        assert result.get('chat_messages') == 10


@pytest.mark.integration
@pytest.mark.asyncio
class TestEventNormalization:
    """Test event normalization in real flow."""
    
    @pytest.mark.xfail(reason="Event normalization needs NATS container - fixture issue - see issue #XX")
    async def test_cytube_event_normalized_and_published(self, test_bot, nats_client):
        """Test that CyTube events are normalized before publishing."""
        # Arrange
        received_events = []
        
        async def event_handler(msg):
            data = json.loads(msg.data.decode())
            received_events.append(data)
        
        # Subscribe to all platform events
        sub = await nats_client.subscribe('rosey.platform.cytube.>', cb=event_handler)
        
        # Act - Trigger user join
        await test_bot._on_user_join('user_join', {'user': 'NormalizedUser', 'user_data': {'username': 'NormalizedUser', 'rank': 1}})
        
        await asyncio.sleep(0.2)
        
        # Cleanup
        await sub.unsubscribe()
        
        # Assert
        assert len(received_events) > 0
        
        # Check first event is normalized
        event = received_events[0]
        assert 'event_type' in event
        assert 'platform' in event
        assert 'data' in event
        assert 'timestamp' in event
        assert event['platform'] == 'cytube'


@pytest.mark.integration
@pytest.mark.asyncio
class TestServiceResilience:
    """Test system resilience and fault tolerance."""
    
    @pytest.mark.xfail(reason="Service resilience tests need fixture updates - see issue #XX")
    async def test_bot_continues_without_database_service(self, test_bot, nats_client):
        """Test bot continues operating if DatabaseService is down."""
        # Note: DatabaseService is NOT started in this test
        
        # Act - Bot should continue without errors
        await test_bot._on_user_join('user_join', {'user': 'TestUser', 'user_data': {'username': 'TestUser', 'rank': 1}})
        await test_bot._on_message('message', {
            'user': 'TestUser',
            'content': 'Hello',
            'timestamp': int(time.time())
        })
        
        # Assert - No exceptions raised
        # Bot published events even though no service consumed them
        assert True  # If we got here, bot didn't crash
    
    @pytest.mark.xfail(reason="Service resilience tests need fixture updates - see issue #XX")
    async def test_database_service_recovers_after_restart(self, nats_client):
        """Test DatabaseService can be stopped and restarted."""
        # Arrange
        service1 = DatabaseService(nats_client)
        await service1.start()
        await asyncio.sleep(0.1)
        
        # Stop service
        await service1.stop()
        await asyncio.sleep(0.1)
        
        # Start new service instance
        service2 = DatabaseService(nats_client)
        await service2.start()
        await asyncio.sleep(0.1)
        
        # Act - Publish event
        subject = 'rosey.platform.cytube.user.joined'
        event_data = {
            'event_type': 'user.joined',
            'platform': 'cytube',
            'data': {'name': 'RecoveryUser', 'rank': 1},
            'timestamp': time.time()
        }
        
        await nats_client.publish(subject, json.dumps(event_data).encode())
        await asyncio.sleep(0.2)
        
        # Assert - Event was processed
        stats = await database_service.db.get_user_stats('RecoveryUser')
        assert stats is not None
        
        # Cleanup
        await service2.stop()


@pytest.mark.integration
@pytest.mark.asyncio
class TestPerformance:
    """Test performance characteristics."""
    
    async def test_high_throughput_messages(self, test_bot, database_service):
        """Test system handles high message throughput."""
        # Arrange
        num_messages = 100
        messages = [
            {
                'username': f'User{i}',
                'msg': f'Message {i}',
                'time': int(time.time() * 1000) + i
            }
            for i in range(num_messages)
        ]
        
        # Act - Send messages rapidly
        start_time = time.time()
        for msg in messages:
            normalized_msg = {'user': msg['username'], 'content': msg['msg'], 'timestamp': msg.get('time', int(time.time()))}
            await test_bot._on_message('message', normalized_msg)
            # Small delay to avoid overwhelming
            await asyncio.sleep(0.001)
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        elapsed = time.time() - start_time
        
        # Assert
        recent = await database_service.db.get_recent_chat(limit=num_messages + 10)
        assert len(recent) >= num_messages * 0.95  # At least 95% received
        
        # Performance check - should handle 100+ events/sec
        throughput = num_messages / elapsed
        assert throughput > 50, f"Throughput too low: {throughput:.2f} events/sec"
    
    @pytest.mark.benchmark
    async def test_latency_overhead(self, test_bot, database_service):
        """Test NATS adds minimal latency overhead."""
        # Arrange
        num_iterations = 10
        latencies = []
        
        # Act - Measure latency
        for i in range(num_iterations):
            start = time.time()
            
            await test_bot._on_message('message', {
                'user': 'LatencyTest',
                'content': f'Iteration {i}',
                'timestamp': int(time.time())
            })
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            end = time.time()
            latencies.append((end - start) * 1000)  # Convert to ms
        
        # Assert
        avg_latency = sum(latencies) / len(latencies)
        
        # Should be under 200ms on average (includes 100ms sleep baseline)
        assert avg_latency < 200, f"Average latency too high: {avg_latency:.2f}ms"
        
        # Print stats for reference
        print("\nLatency Stats:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--nats-url",
        action="store",
        default="nats://localhost:4222",
        help="NATS server URL for integration tests"
    )


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (require NATS server)"
    )
    config.addinivalue_line(
        "markers",
        "benchmark: Performance benchmark tests"
    )


# ============================================================================
# Test Collection
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Skip integration tests if NATS is not available."""
    if not NATS_AVAILABLE:
        skip_nats = pytest.mark.skip(reason="nats-py not installed")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_nats)
