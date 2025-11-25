"""
Tests for NATS KV-based conversation memory.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.llm.memory import (
    ConversationMemory,
    MemoryConfig,
    StoredMessage,
    StoredMemory
)
from plugins.llm.providers.base import Message


@pytest.fixture
def memory_config():
    """Memory configuration for tests."""
    return MemoryConfig(
        max_messages_in_context=10
    )


@pytest.fixture
def mock_kv_entry():
    """Mock KV entry."""
    entry = MagicMock()
    entry.value = b'[]'
    return entry


@pytest.fixture
async def mock_nats_client(mock_kv_entry):
    """Mock NATS client with JetStream KV."""
    mock_nc = AsyncMock()
    mock_js = AsyncMock()
    mock_kv = AsyncMock()
    
    # Setup JetStream - jetstream() is NOT async, it returns the JS context
    mock_nc.jetstream = MagicMock(return_value=mock_js)
    
    # Setup JS methods - these ARE async
    mock_js.key_value = AsyncMock(return_value=mock_kv)
    mock_js.create_key_value = AsyncMock(return_value=mock_kv)
    
    # Setup KV operations
    mock_kv.get = AsyncMock(return_value=mock_kv_entry)
    mock_kv.put = AsyncMock()
    mock_kv.delete = AsyncMock()
    mock_kv.keys = AsyncMock(return_value=[])
    
    return mock_nc, mock_kv


@pytest.fixture
async def memory(mock_nats_client, memory_config):
    """Initialized memory instance."""
    mock_nc, _ = mock_nats_client
    mem = ConversationMemory(mock_nc, memory_config)
    await mem.initialize()
    return mem


# ============================================================================
# Initialization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_initialization(mock_nats_client, memory_config):
    """Test memory system initialization."""
    mock_nc, mock_kv = mock_nats_client
    
    memory = ConversationMemory(mock_nc, memory_config)
    await memory.initialize()
    
    # Should get JetStream context
    mock_nc.jetstream.assert_called_once()
    
    # Should have KV bucket
    assert memory.kv is not None


@pytest.mark.asyncio
async def test_memory_initialization_creates_bucket(mock_nats_client, memory_config):
    """Test bucket creation when it doesn't exist."""
    mock_nc, mock_kv = mock_nats_client
    mock_js = mock_nc.jetstream()
    
    # First call raises exception (bucket doesn't exist)
    mock_js.key_value.side_effect = Exception("Not found")
    
    memory = ConversationMemory(mock_nc, memory_config)
    
    with patch('nats.js.api.KeyValueConfig'):
        await memory.initialize()
    
    # Should try to create bucket
    mock_js.create_key_value.assert_called_once()


# ============================================================================
# Message Storage Tests
# ============================================================================


@pytest.mark.asyncio
async def test_add_message(memory, mock_nats_client):
    """Test adding message to conversation."""
    _, mock_kv = mock_nats_client
    
    await memory.add_message(
        channel="test-channel",
        role="user",
        content="Hello, world!",
        user_id="alice"
    )
    
    # Should store to KV
    mock_kv.put.assert_called_once()
    call_args = mock_kv.put.call_args
    
    # Check key
    assert call_args[0][0] == "messages:test-channel:recent"
    
    # Check value contains message
    stored_data = json.loads(call_args[0][1].decode())
    assert len(stored_data) == 1
    assert stored_data[0]["role"] == "user"
    assert stored_data[0]["content"] == "Hello, world!"
    assert stored_data[0]["user_id"] == "alice"


@pytest.mark.asyncio
async def test_add_multiple_messages(memory, mock_nats_client):
    """Test adding multiple messages."""
    _, mock_kv = mock_nats_client
    
    # Add first message
    await memory.add_message(
        channel="test-channel",
        role="user",
        content="First message",
        user_id="alice"
    )
    
    # Mock get to return first message
    first_msg = StoredMessage(
        role="user",
        content="First message",
        user_id="alice",
        timestamp="2025-01-01T00:00:00"
    )
    mock_kv.get.return_value.value = json.dumps([
        {
            "role": first_msg.role,
            "content": first_msg.content,
            "user_id": first_msg.user_id,
            "timestamp": first_msg.timestamp
        }
    ]).encode()
    
    # Add second message
    await memory.add_message(
        channel="test-channel",
        role="assistant",
        content="Second message"
    )
    
    # Should have both messages
    last_call = mock_kv.put.call_args
    stored_data = json.loads(last_call[0][1].decode())
    assert len(stored_data) == 2


@pytest.mark.asyncio
async def test_message_rotation(memory, mock_nats_client):
    """Test that messages are rotated when exceeding limit."""
    _, mock_kv = mock_nats_client
    
    # Create 25 messages (more than 2x max_context of 10)
    existing_messages = [
        {
            "role": "user",
            "content": f"Message {i}",
            "user_id": "alice",
            "timestamp": f"2025-01-01T00:00:{i:02d}"
        }
        for i in range(25)
    ]
    
    mock_kv.get.return_value.value = json.dumps(existing_messages).encode()
    
    await memory.add_message(
        channel="test-channel",
        role="user",
        content="New message"
    )
    
    # Should keep only last 20 messages (2x max_context)
    last_call = mock_kv.put.call_args
    stored_data = json.loads(last_call[0][1].decode())
    assert len(stored_data) == 20


@pytest.mark.asyncio
async def test_get_recent_messages(memory, mock_nats_client):
    """Test retrieving recent messages."""
    _, mock_kv = mock_nats_client
    
    # Mock stored messages
    messages = [
        {
            "role": "user",
            "content": "Hello",
            "user_id": "alice",
            "timestamp": "2025-01-01T00:00:01"
        },
        {
            "role": "assistant",
            "content": "Hi there!",
            "user_id": None,
            "timestamp": "2025-01-01T00:00:02"
        }
    ]
    mock_kv.get.return_value.value = json.dumps(messages).encode()
    
    # Get messages
    result = await memory.get_recent_messages("test-channel")
    
    # Should return Message objects
    assert len(result) == 2
    assert isinstance(result[0], Message)
    assert result[0].role == "user"
    assert result[0].content == "Hello"
    assert result[1].role == "assistant"
    assert result[1].content == "Hi there!"


@pytest.mark.asyncio
async def test_get_recent_messages_with_limit(memory, mock_nats_client):
    """Test retrieving messages with custom limit."""
    _, mock_kv = mock_nats_client
    
    # Mock 10 stored messages
    messages = [
        {
            "role": "user",
            "content": f"Message {i}",
            "user_id": "alice",
            "timestamp": f"2025-01-01T00:00:{i:02d}"
        }
        for i in range(10)
    ]
    mock_kv.get.return_value.value = json.dumps(messages).encode()
    
    # Get last 5 messages
    result = await memory.get_recent_messages("test-channel", limit=5)
    
    assert len(result) == 5
    # Should be last 5 messages
    assert result[0].content == "Message 5"
    assert result[-1].content == "Message 9"


@pytest.mark.asyncio
async def test_reset_context(memory, mock_nats_client):
    """Test clearing conversation history."""
    _, mock_kv = mock_nats_client
    
    # Mock existing messages
    messages = [
        {
            "role": "user",
            "content": "Message 1",
            "user_id": "alice",
            "timestamp": "2025-01-01T00:00:01"
        },
        {
            "role": "assistant",
            "content": "Message 2",
            "user_id": None,
            "timestamp": "2025-01-01T00:00:02"
        }
    ]
    mock_kv.get.return_value.value = json.dumps(messages).encode()
    
    # Reset context
    count = await memory.reset_context("test-channel")
    
    # Should return count
    assert count == 2
    
    # Should delete the key
    mock_kv.delete.assert_called_once_with("messages:test-channel:recent")


# ============================================================================
# Memory Storage Tests
# ============================================================================


@pytest.mark.asyncio
async def test_remember(memory, mock_nats_client):
    """Test storing a memory."""
    _, mock_kv = mock_nats_client
    
    memory_id = await memory.remember(
        channel="test-channel",
        content="Alice likes Python",
        category="preference",
        user_id="alice",
        importance=3
    )
    
    # Should return memory ID
    assert memory_id
    assert len(memory_id) == 8  # UUID first 8 chars
    
    # Should store to KV
    mock_kv.put.assert_called_once()
    call_args = mock_kv.put.call_args
    
    # Check key pattern
    assert call_args[0][0].startswith("memories:test-channel:")
    
    # Check stored data
    stored_data = json.loads(call_args[0][1].decode())
    assert stored_data["content"] == "Alice likes Python"
    assert stored_data["category"] == "preference"
    assert stored_data["user_id"] == "alice"
    assert stored_data["importance"] == 3


@pytest.mark.asyncio
async def test_recall(memory, mock_nats_client):
    """Test recalling memories."""
    _, mock_kv = mock_nats_client
    
    # Mock stored memories
    memory_keys = [
        "memories:test-channel:abc123",
        "memories:test-channel:def456"
    ]
    mock_kv.keys.return_value = memory_keys
    
    # Setup get to return different memories
    memories_data = {
        "memories:test-channel:abc123": {
            "id": "abc123",
            "content": "Alice likes Python programming",
            "category": "preference",
            "importance": 3,
            "user_id": "alice",
            "created_at": "2025-01-01T00:00:00"
        },
        "memories:test-channel:def456": {
            "id": "def456",
            "content": "Bob prefers JavaScript",
            "category": "preference",
            "importance": 2,
            "user_id": "bob",
            "created_at": "2025-01-01T00:01:00"
        }
    }
    
    async def mock_get(key):
        entry = MagicMock()
        entry.value = json.dumps(memories_data[key]).encode()
        return entry
    
    mock_kv.get.side_effect = mock_get
    
    # Recall memories about Python
    results = await memory.recall(
        channel="test-channel",
        query="Python",
        limit=5
    )
    
    # Should find matching memory
    assert len(results) == 1
    assert "Python" in results[0]


@pytest.mark.asyncio
async def test_recall_sorts_by_importance(memory, mock_nats_client):
    """Test that recall sorts by importance."""
    _, mock_kv = mock_nats_client
    
    # Mock stored memories
    memory_keys = [
        "memories:test-channel:abc123",
        "memories:test-channel:def456",
        "memories:test-channel:ghi789"
    ]
    mock_kv.keys.return_value = memory_keys
    
    # Setup memories with different importance
    memories_data = {
        "memories:test-channel:abc123": {
            "id": "abc123",
            "content": "Low importance fact",
            "category": "fact",
            "importance": 1,
            "user_id": None,
            "created_at": "2025-01-01T00:00:00"
        },
        "memories:test-channel:def456": {
            "id": "def456",
            "content": "High importance fact",
            "category": "fact",
            "importance": 5,
            "user_id": None,
            "created_at": "2025-01-01T00:01:00"
        },
        "memories:test-channel:ghi789": {
            "id": "ghi789",
            "content": "Medium importance fact",
            "category": "fact",
            "importance": 3,
            "user_id": None,
            "created_at": "2025-01-01T00:02:00"
        }
    }
    
    async def mock_get(key):
        entry = MagicMock()
        entry.value = json.dumps(memories_data[key]).encode()
        return entry
    
    mock_kv.get.side_effect = mock_get
    
    # Recall memories about "fact"
    results = await memory.recall(
        channel="test-channel",
        query="fact",
        limit=2
    )
    
    # Should return top 2 by importance
    assert len(results) == 2
    assert "High importance" in results[0]
    assert "Medium importance" in results[1]


@pytest.mark.asyncio
async def test_forget(memory, mock_nats_client):
    """Test forgetting a memory."""
    _, mock_kv = mock_nats_client
    
    success = await memory.forget(
        channel="test-channel",
        memory_id="abc123"
    )
    
    # Should return success
    assert success
    
    # Should delete from KV
    mock_kv.delete.assert_called_once_with("memories:test-channel:abc123")


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_add_message_without_initialization():
    """Test that operations fail gracefully without initialization."""
    mock_nc = AsyncMock()
    memory = ConversationMemory(mock_nc)
    
    # Should not raise, just log warning
    await memory.add_message(
        channel="test-channel",
        role="user",
        content="Test"
    )
    
    # Memory should not be stored
    assert memory.kv is None


@pytest.mark.asyncio
async def test_get_messages_returns_empty_on_error(memory, mock_nats_client):
    """Test that get_messages returns empty list on error."""
    _, mock_kv = mock_nats_client
    
    # Mock KV to raise exception
    mock_kv.get.side_effect = Exception("Network error")
    
    # Should return empty list, not raise
    result = await memory.get_recent_messages("test-channel")
    assert result == []


@pytest.mark.asyncio
async def test_recall_returns_empty_on_error(memory, mock_nats_client):
    """Test that recall returns empty list on error."""
    _, mock_kv = mock_nats_client
    
    # Mock keys to raise exception
    mock_kv.keys.side_effect = Exception("Network error")
    
    # Should return empty list, not raise
    result = await memory.recall("test-channel", "query")
    assert result == []


# ============================================================================
# Channel Isolation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_channel_isolation(memory, mock_nats_client):
    """Test that channels are isolated."""
    _, mock_kv = mock_nats_client
    
    # Add messages to different channels
    await memory.add_message(
        channel="channel-1",
        role="user",
        content="Channel 1 message"
    )
    
    await memory.add_message(
        channel="channel-2",
        role="user",
        content="Channel 2 message"
    )
    
    # Should use different keys
    calls = mock_kv.put.call_args_list
    assert calls[0][0][0] == "messages:channel-1:recent"
    assert calls[1][0][0] == "messages:channel-2:recent"


@pytest.mark.asyncio
async def test_memory_channel_isolation(memory, mock_nats_client):
    """Test that memory storage is per-channel."""
    _, mock_kv = mock_nats_client
    
    # Remember in different channels
    await memory.remember(
        channel="channel-1",
        content="Fact about channel 1"
    )
    
    await memory.remember(
        channel="channel-2",
        content="Fact about channel 2"
    )
    
    # Should use different key patterns
    calls = mock_kv.put.call_args_list
    assert "channel-1" in calls[0][0][0]
    assert "channel-2" in calls[1][0][0]
