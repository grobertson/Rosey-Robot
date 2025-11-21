# Technical Specification: Bot Layer NATS Migration

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 4 of 6  
**Status**: Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Dependencies**: Sortie 3 (Database Service) MUST be complete  
**Blocking**: Sortie 5 (Config v2 & Breaking Changes)  

---

## Overview

**Purpose**: Replace ALL direct `self.db.*` method calls in bot layer with NATS publish/request operations. This establishes proper layer isolation and enables process separation between bot and database.

**Scope**: Update 7 locations in `lib/bot.py` where bot directly calls database methods (NORMALIZATION_TODO.md #11-#17).

**Key Principle**: *"All layers communicate via NATS - no direct calls between bot/database/plugins."*

**Backward Compatibility**: Initially maintain dual-mode operation (try NATS first, fallback to direct calls if no NATS). Breaking changes (removing `db` parameter) deferred to Sortie 5.

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: Bot MUST publish all database operations to NATS subjects  
**FR-002**: Bot MUST use request/reply pattern for synchronous queries  
**FR-003**: Bot MUST maintain backward compatibility during transition (dual-mode)  
**FR-004**: Bot MUST handle NATS timeouts gracefully (log and continue)  
**FR-005**: Bot MUST NOT break if NATS unavailable (fallback to direct calls)  
**FR-006**: All 7 database call sites MUST be migrated  

### 1.2 Non-Functional Requirements

**NFR-001**: Performance parity with direct calls (<5% overhead acceptable)  
**NFR-002**: NATS operations are async (use `await`)  
**NFR-003**: Error handling preserves existing bot behavior  
**NFR-004**: Logging indicates whether NATS or direct path used  

---

## 2. NATS Communication Patterns

### 2.1 Pub/Sub Pattern (Fire-and-Forget)

**Use Case**: Database updates that don't need confirmation

**Pattern**:
```python
# Bot publishes event
if self.nats:
    await self.nats.publish('rosey.db.user.joined', json.dumps({
        'username': username,
        'timestamp': int(time.time())
    }).encode())
else:
    # Fallback to direct call
    if self.db:
        self.db.user_joined(username)
```

**Subjects**:
- `rosey.db.user.joined` - User joined channel
- `rosey.db.user.left` - User left channel
- `rosey.db.message.log` - Log chat message
- `rosey.db.stats.user_count` - Update user count
- `rosey.db.stats.high_water` - Update high water mark
- `rosey.db.status.update` - Bot status update
- `rosey.db.messages.outbound.mark_sent` - Mark message sent

### 2.2 Request/Reply Pattern (Queries)

**Use Case**: Database queries that need results

**Pattern**:
```python
# Bot requests data
if self.nats:
    try:
        response = await self.nats.request(
            'rosey.db.messages.outbound.get',
            json.dumps({'username': username, 'limit': 10}).encode(),
            timeout=2.0  # 2 second timeout
        )
        messages = json.loads(response.data.decode())
    except asyncio.TimeoutError:
        self.logger.warning("NATS request timeout, using empty result")
        messages = []
else:
    # Fallback to direct call
    if self.db:
        messages = self.db.get_unsent_outbound_messages(username, limit=10)
    else:
        messages = []
```

**Subjects**:
- `rosey.db.messages.outbound.get` - Get outbound messages
- `rosey.db.stats.recent_chat.get` - Get recent chat (future)

---

## 3. Migration Changes

### 3.1 Location 1: User Joined (#11)

**File**: `lib/bot.py`  
**Line**: ~395  
**Current Code**:
```python
def _on_user_join(self, _, data):
    """Handle user joining channel."""
    username = data.get('user', '')
    user_data = data.get('user_data', {})
    
    # ... userlist management ...
    
    # Database tracking
    if self.db:
        self.db.user_joined(username)  # ❌ Direct call
```

**Required Change**:
```python
async def _on_user_join(self, _, data):  # NOW ASYNC
    """Handle user joining channel."""
    username = data.get('user', '')
    user_data = data.get('user_data', {})
    
    # ... userlist management ...
    
    # Database tracking via NATS
    if self.nats:
        await self.nats.publish('rosey.db.user.joined', json.dumps({
            'username': username,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug(f"[NATS] Published user_joined: {username}")
    elif self.db:
        # Fallback for backward compatibility
        self.db.user_joined(username)
        self.logger.debug(f"[DB] Direct call user_joined: {username}")
```

---

### 3.2 Location 2: User Left (#12)

**File**: `lib/bot.py`  
**Line**: ~425  
**Current Code**:
```python
def _on_user_leave(self, _, data):
    """Handle user leaving channel."""
    username = data.get('user', '')
    
    # ... userlist management ...
    
    if self.db:
        self.db.user_left(username)  # ❌ Direct call
```

**Required Change**:
```python
async def _on_user_leave(self, _, data):  # NOW ASYNC
    """Handle user leaving channel."""
    username = data.get('user', '')
    
    # ... userlist management ...
    
    if self.nats:
        await self.nats.publish('rosey.db.user.left', json.dumps({
            'username': username,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug(f"[NATS] Published user_left: {username}")
    elif self.db:
        self.db.user_left(username)
        self.logger.debug(f"[DB] Direct call user_left: {username}")
```

---

### 3.3 Location 3: Message Logged (#13)

**File**: `lib/bot.py`  
**Line**: ~540  
**Current Code**:
```python
def _on_chat_message(self, _, data):
    """Handle chat messages."""
    username = data.get('user', '')
    message = data.get('content', '')
    
    # ... message handling ...
    
    if self.db:
        self.db.message_logged(username, message)  # ❌ Direct call
```

**Required Change**:
```python
async def _on_chat_message(self, _, data):  # NOW ASYNC
    """Handle chat messages."""
    username = data.get('user', '')
    message = data.get('content', '')
    
    # ... message handling ...
    
    if self.nats:
        await self.nats.publish('rosey.db.message.log', json.dumps({
            'username': username,
            'message': message,
            'timestamp': data.get('timestamp', int(time.time()))
        }).encode())
        self.logger.debug(f"[NATS] Published message_log: {username}")
    elif self.db:
        self.db.message_logged(username, message)
        self.logger.debug(f"[DB] Direct call message_logged: {username}")
```

---

### 3.4 Location 4: User Count Update (#14)

**File**: `lib/bot.py`  
**Line**: ~375  
**Current Code**:
```python
def _on_user_count(self, _, data):
    """Handle user count updates."""
    chat_count = data.get('usercount', 0)
    connected_count = data.get('connected', 0)
    
    if self.db:
        self.db.update_user_count(chat_count, connected_count)  # ❌ Direct call
```

**Required Change**:
```python
async def _on_user_count(self, _, data):  # NOW ASYNC
    """Handle user count updates."""
    chat_count = data.get('usercount', 0)
    connected_count = data.get('connected', 0)
    
    if self.nats:
        await self.nats.publish('rosey.db.stats.user_count', json.dumps({
            'chat_count': chat_count,
            'connected_count': connected_count,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug(f"[NATS] Published user_count: {chat_count}/{connected_count}")
    elif self.db:
        self.db.update_user_count(chat_count, connected_count)
        self.logger.debug(f"[DB] Direct call update_user_count: {chat_count}/{connected_count}")
```

---

### 3.5 Location 5: High Water Mark (#15)

**File**: `lib/bot.py`  
**Line**: ~385  
**Current Code**:
```python
def _on_user_count(self, _, data):
    """Handle user count updates."""
    chat_count = data.get('usercount', 0)
    connected_count = data.get('connected', 0)
    
    if self.db:
        self.db.update_user_count(chat_count, connected_count)
        self.db.update_high_water_mark(chat_count, connected_count)  # ❌ Direct call
```

**Required Change**:
```python
async def _on_user_count(self, _, data):  # SAME HANDLER AS #14
    """Handle user count updates."""
    chat_count = data.get('usercount', 0)
    connected_count = data.get('connected', 0)
    
    if self.nats:
        # Publish user count
        await self.nats.publish('rosey.db.stats.user_count', json.dumps({
            'chat_count': chat_count,
            'connected_count': connected_count,
            'timestamp': int(time.time())
        }).encode())
        
        # Publish high water mark
        await self.nats.publish('rosey.db.stats.high_water', json.dumps({
            'chat_count': chat_count,
            'connected_count': connected_count,
            'timestamp': int(time.time())
        }).encode())
        
        self.logger.debug(f"[NATS] Published user_count + high_water")
    elif self.db:
        self.db.update_user_count(chat_count, connected_count)
        self.db.update_high_water_mark(chat_count, connected_count)
        self.logger.debug(f"[DB] Direct calls for user_count + high_water")
```

---

### 3.6 Location 6: Bot Status Update (#16)

**File**: `lib/bot.py`  
**Line**: ~210  
**Current Code**:
```python
def _on_connect(self):
    """Handle successful connection."""
    if self.db:
        self.db.log_bot_status('connected', 'Bot connected to channel')  # ❌ Direct call
```

**Required Change**:
```python
async def _on_connect(self):  # NOW ASYNC
    """Handle successful connection."""
    if self.nats:
        await self.nats.publish('rosey.db.status.update', json.dumps({
            'status': 'connected',
            'details': 'Bot connected to channel',
            'timestamp': int(time.time())
        }).encode())
        self.logger.info("[NATS] Published status: connected")
    elif self.db:
        self.db.log_bot_status('connected', 'Bot connected to channel')
        self.logger.info("[DB] Direct call log_bot_status: connected")
```

**Note**: Similar changes needed in `_on_disconnect` and other status update locations.

---

### 3.7 Location 7: Outbound Message Query (#17) - REQUEST/REPLY

**File**: `lib/bot.py`  
**Line**: ~430  
**Current Code**:
```python
def _check_pending_messages(self, username):
    """Check for pending outbound messages."""
    if self.db:
        messages = self.db.get_unsent_outbound_messages(username, limit=10)  # ❌ Direct call
        
        for msg in messages:
            self.send_private_message(username, msg['content'])
            self.db.mark_outbound_message_sent(msg['id'])  # ❌ Direct call
```

**Required Change**:
```python
async def _check_pending_messages(self, username):  # NOW ASYNC
    """Check for pending outbound messages."""
    messages = []
    
    # Query via NATS request/reply
    if self.nats:
        try:
            response = await self.nats.request(
                'rosey.db.messages.outbound.get',
                json.dumps({'username': username, 'limit': 10}).encode(),
                timeout=2.0  # 2 second timeout
            )
            messages = json.loads(response.data.decode())
            self.logger.debug(f"[NATS] Queried outbound messages for {username}: {len(messages)} found")
        except asyncio.TimeoutError:
            self.logger.warning(f"[NATS] Timeout querying outbound messages for {username}")
            messages = []
        except Exception as e:
            self.logger.error(f"[NATS] Error querying outbound messages: {e}")
            messages = []
    elif self.db:
        # Fallback to direct call
        messages = self.db.get_unsent_outbound_messages(username, limit=10)
        self.logger.debug(f"[DB] Direct query outbound messages for {username}: {len(messages)} found")
    
    # Send messages
    for msg in messages:
        self.send_private_message(username, msg['content'])
        
        # Mark as sent via NATS
        if self.nats:
            await self.nats.publish('rosey.db.messages.outbound.mark_sent', json.dumps({
                'message_id': msg['id'],
                'timestamp': int(time.time())
            }).encode())
        elif self.db:
            self.db.mark_outbound_message_sent(msg['id'])
```

---

## 4. Handler Async Migration

### 4.1 Making Handlers Async

**Challenge**: Event handlers are currently synchronous, but NATS operations are async.

**Solution**: Convert handlers to async and ensure they're awaited.

**Pattern**:
```python
# BEFORE (sync)
def _on_user_join(self, _, data):
    if self.db:
        self.db.user_joined(username)

# AFTER (async)
async def _on_user_join(self, _, data):
    if self.nats:
        await self.nats.publish(...)
```

**Invocation Update** (in `lib/bot.py` event dispatcher):
```python
# Check if handler is async
if asyncio.iscoroutinefunction(handler):
    await handler(event_name, normalized_data)
else:
    handler(event_name, normalized_data)
```

### 4.2 Handlers Requiring Async Conversion

All handlers with database calls:
- `_on_user_join` (Location 1)
- `_on_user_leave` (Location 2)
- `_on_chat_message` (Location 3)
- `_on_user_count` (Locations 4-5)
- `_on_connect` (Location 6)
- `_on_disconnect` (Location 6)
- `_check_pending_messages` (Location 7)

---

## 5. Implementation Plan

### Phase 1: Add NATS Client Parameter (1 hour)

1. Update `Bot.__init__()` to accept optional `nats_client` parameter
2. Store as `self.nats`
3. Add logging to indicate NATS availability
4. Update bot initialization in `bot/rosey/rosey.py`

### Phase 2: Convert Pub/Sub Operations (3 hours)

1. **User Joined** (Location 1) - 30 min
   - Convert handler to async
   - Add NATS publish with fallback
   - Test with and without NATS

2. **User Left** (Location 2) - 30 min
   - Convert handler to async
   - Add NATS publish with fallback

3. **Message Logged** (Location 3) - 30 min
   - Convert handler to async
   - Add NATS publish with fallback

4. **User Count + High Water** (Locations 4-5) - 45 min
   - Convert handler to async
   - Add both NATS publishes
   - Test that both events sent

5. **Status Updates** (Location 6) - 45 min
   - Convert connect/disconnect handlers to async
   - Add NATS publish with fallback
   - Update all status update call sites

### Phase 3: Convert Request/Reply Operations (1.5 hours)

1. **Outbound Messages Query** (Location 7) - 1.5 hours
   - Convert handler to async
   - Implement request/reply pattern
   - Add timeout handling
   - Add error handling
   - Test with NATS unavailable

### Phase 4: Event Dispatcher Update (1 hour)

1. Update event emission to handle async handlers
2. Ensure proper await for async handlers
3. Test mixed sync/async handlers

### Phase 5: Testing (2 hours)

1. Unit tests for each migration
2. Integration tests with real NATS
3. Backward compatibility tests (no NATS)
4. Performance benchmarking

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Update Existing Tests**:
```python
# tests/unit/test_bot.py

@pytest.fixture
async def bot_with_nats(nats_client):
    """Bot with NATS client."""
    bot = Bot(connection, channel, nats_client=nats_client)
    return bot

@pytest.mark.asyncio
async def test_user_join_publishes_to_nats(bot_with_nats, nats_client):
    """Verify user join publishes to NATS."""
    await bot_with_nats._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 0}
    })
    
    # Verify NATS publish called
    nats_client.publish.assert_called_once_with(
        'rosey.db.user.joined',
        ANY  # JSON payload
    )

@pytest.mark.asyncio
async def test_user_join_fallback_without_nats(bot):
    """Verify user join falls back to direct DB call without NATS."""
    bot.nats = None  # No NATS client
    bot.db = Mock()
    
    await bot._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 0}
    })
    
    # Verify direct DB call
    bot.db.user_joined.assert_called_once_with('alice')

@pytest.mark.asyncio
async def test_outbound_query_with_nats(bot_with_nats, nats_client):
    """Verify outbound message query uses NATS request/reply."""
    # Mock NATS response
    mock_response = Mock()
    mock_response.data = json.dumps([
        {'id': 1, 'content': 'Hello'}
    ]).encode()
    nats_client.request = AsyncMock(return_value=mock_response)
    
    await bot_with_nats._check_pending_messages('alice')
    
    # Verify NATS request called
    nats_client.request.assert_called_once()

@pytest.mark.asyncio
async def test_outbound_query_timeout_handled(bot_with_nats, nats_client):
    """Verify outbound query handles timeout gracefully."""
    nats_client.request = AsyncMock(side_effect=asyncio.TimeoutError())
    
    # Should not crash
    await bot_with_nats._check_pending_messages('alice')
```

### 6.2 Integration Tests

**Manual Test Checklist**:

1. [ ] Start NATS server
2. [ ] Start DatabaseService
3. [ ] Start bot with NATS client
4. [ ] Verify user join events reach database
5. [ ] Verify messages logged to database
6. [ ] Verify outbound message query works
7. [ ] Stop NATS server, verify bot continues (fallback)

---

## 7. Acceptance Criteria

**Definition of Done**:

- [ ] All 7 database call locations migrated to NATS
- [ ] All relevant handlers converted to async
- [ ] Event dispatcher handles async handlers correctly
- [ ] NATS pub/sub operations working (5 locations)
- [ ] NATS request/reply operations working (1 location)
- [ ] Backward compatibility maintained (fallback to direct calls)
- [ ] Timeout handling for request/reply
- [ ] Error handling for NATS failures
- [ ] Unit tests for all migrations
- [ ] Integration tests with real NATS
- [ ] Performance benchmarking complete (<5% overhead)
- [ ] Logging indicates NATS vs direct path
- [ ] NORMALIZATION_TODO.md items #11-#17 marked complete

---

## 8. Backward Compatibility

### 8.1 Dual-Mode Operation

**Phase 1** (This Sortie):
- Bot accepts both `db` and `nats_client` parameters
- Try NATS first, fallback to `db` if NATS unavailable
- Both paths work simultaneously

**Phase 2** (Sortie 5):
- Remove `db` parameter entirely
- NATS becomes mandatory
- Breaking change - documented and justified

### 8.2 Graceful Degradation

**If NATS Unavailable**:
- Bot logs warning
- Falls back to direct database calls
- All functionality preserved
- No crashes or errors

---

## 9. Dependencies

**Requires**:
- ✅ Sortie 1 (Event Normalization) - event structures defined
- ✅ Sortie 3 (Database Service) - NATS handlers implemented

**Blocks**:
- Sortie 5 (Config v2) - needs NATS migration complete first

**Does NOT Block**:
- Sortie 2 (Bot Handler Migration) - independent

---

## 10. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Async conversion breaks existing code | MEDIUM | HIGH | Comprehensive testing, gradual rollout |
| NATS timeout causes delays | MEDIUM | MEDIUM | 2-second timeout, immediate fallback |
| Performance overhead | LOW | MEDIUM | Benchmark before/after, accept <5% |
| Missing error handling | LOW | HIGH | Test with NATS down, network issues |

---

## 11. Performance Considerations

### 11.1 Expected Overhead

**NATS Pub/Sub**:
- Direct call: ~0.1ms
- NATS publish: ~0.5-1ms
- Overhead: ~0.4-0.9ms (negligible)

**NATS Request/Reply**:
- Direct call: ~0.5ms (SQLite query)
- NATS round-trip: ~2-5ms
- Overhead: ~1.5-4.5ms (acceptable for non-critical path)

### 11.2 Optimization Opportunities

**Batch Operations**: For high-frequency events, consider batching:
```python
# Future optimization: batch messages
self.message_batch.append({'username': username, 'message': message})
if len(self.message_batch) >= 10:
    await self._flush_message_batch()
```

---

## 12. Next Steps

**After Completion**:

1. Mark Sortie 4 complete
2. Performance benchmark (compare NATS vs direct)
3. Begin Sortie 5: Configuration v2 & Breaking Changes (remove `db` parameter)
4. Update deployment docs with NATS requirements

---

**Sortie Status**: Ready for Implementation  
**Priority**: CRITICAL (Core Migration)  
**Estimated Effort**: 6-8 hours  
**Success Metric**: All database operations via NATS, backward compatible, <5% overhead
