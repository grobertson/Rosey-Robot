# Technical Specification: Database Methods Completion

**Sprint**: Sprint 10.5 "The French Connection II"  
**Sortie**: 1 of 4  
**Estimated Effort**: 1 hour  
**Dependencies**: Sprint 10 Sortie 1 (async database foundation)  

---

## Overview

Add two missing BotDatabase methods (`get_recent_messages()` and `log_chat()`) to unblock 3 performance benchmarks. Methods follow existing async patterns and integrate with current database schema.

---

## Implementation

### 1. Add get_recent_messages()

**File**: `common/database.py`  
**Location**: After `save_message()` method (~line 250)  

```python
async def get_recent_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent chat messages from database.
    
    Returns messages sorted by timestamp descending (most recent first).
    Used for chat history display and throughput benchmarks.
    
    Args:
        limit: Maximum messages to return (default 100)
        offset: Number of messages to skip for pagination (default 0)
    
    Returns:
        List of message dicts with keys:
        - id: Message ID (int)
        - timestamp: Unix timestamp (int)
        - username: Username who sent message (str)
        - message: Message text (str)
    
    Example:
        messages = await db.get_recent_messages(limit=10)
        for msg in messages:
            print(f"{msg['username']}: {msg['message']}")
    """
    cursor = await self.conn.cursor()
    await cursor.execute('''
        SELECT id, timestamp, username, message
        FROM recent_chat
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    rows = await cursor.fetchall()
    return [
        {
            'id': row[0],
            'timestamp': row[1],
            'username': row[2],
            'message': row[3]
        }
        for row in rows
    ]
```

---

### 2. Add log_chat()

**File**: `common/database.py`  
**Location**: After `get_recent_messages()` method  

```python
async def log_chat(self, username: str, message: str, timestamp: int = None) -> None:
    """Log chat message to database.
    
    Convenience method for performance benchmarks. Production code
    should use save_message() which includes additional tracking.
    
    Args:
        username: Username who sent message
        message: Message text
        timestamp: Unix timestamp (default: current time)
    
    Example:
        await db.log_chat('Alice', 'Hello world!')
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    cursor = await self.conn.cursor()
    await cursor.execute('''
        INSERT INTO recent_chat (timestamp, username, message)
        VALUES (?, ?, ?)
    ''', (timestamp, username, message))
    
    await self.conn.commit()
```

---

### 3. Add Unit Tests

**File**: `tests/unit/test_database.py`  
**Location**: End of file (new test class)  

```python
class TestChatMethods:
    """Test chat message methods."""
    
    @pytest.mark.asyncio
    async def test_log_chat(self, temp_database):
        """Test logging chat message."""
        await temp_database.log_chat('Alice', 'Hello!')
        
        messages = await temp_database.get_recent_messages()
        assert len(messages) == 1
        assert messages[0]['username'] == 'Alice'
        assert messages[0]['message'] == 'Hello!'
    
    @pytest.mark.asyncio
    async def test_get_recent_messages_limit(self, temp_database):
        """Test message retrieval with limit."""
        # Add 10 messages
        for i in range(10):
            await temp_database.log_chat(f'User{i}', f'Message {i}', timestamp=i)
        
        # Get last 5
        messages = await temp_database.get_recent_messages(limit=5)
        assert len(messages) == 5
        assert messages[0]['message'] == 'Message 9'  # Most recent first
    
    @pytest.mark.asyncio
    async def test_get_recent_messages_offset(self, temp_database):
        """Test message pagination."""
        # Add 10 messages
        for i in range(10):
            await temp_database.log_chat(f'User{i}', f'Message {i}', timestamp=i)
        
        # Get middle 5 (skip first 3)
        messages = await temp_database.get_recent_messages(limit=5, offset=3)
        assert len(messages) == 5
        assert messages[0]['message'] == 'Message 6'
    
    @pytest.mark.asyncio
    async def test_log_chat_custom_timestamp(self, temp_database):
        """Test logging with custom timestamp."""
        custom_time = 1234567890
        await temp_database.log_chat('Alice', 'Test', timestamp=custom_time)
        
        messages = await temp_database.get_recent_messages()
        assert messages[0]['timestamp'] == custom_time
```

---

## Testing

### Run Unit Tests
```bash
pytest tests/unit/test_database.py::TestChatMethods -v
```

### Run Unblocked Benchmarks
```bash
pytest tests/performance/test_nats_overhead.py::TestThroughputBenchmarks -v
pytest tests/performance/test_nats_overhead.py::TestCPUOverhead::test_direct_database_cpu -v
```

**Expected**: 3 benchmarks now pass (sustained throughput, burst throughput, direct database CPU)

---

## Acceptance Criteria

- [ ] `get_recent_messages()` implemented with async/await
- [ ] `log_chat()` implemented with async/await
- [ ] 4 unit tests pass (100% coverage of new methods)
- [ ] `test_sustained_throughput` passes
- [ ] `test_burst_throughput` passes
- [ ] `test_direct_database_cpu` passes
- [ ] Benchmarks passing: 7/10 (up from 4/10)

---

**Estimated Time**: 1 hour  
**Files Changed**: 2 (database.py, test_database.py)  
**Lines Added**: ~80
