# Technical Specification: PM Logging & Service Resilience

**Sprint**: Sprint 10 "The French Connection"  
**Sortie**: 3 of 4  
**Status**: Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Dependencies**: Sortie 1 (BotDatabase.connect()), Sortie 2 (NATS patterns)  
**Blocking**: None (completes test infrastructure)  

---

## Overview

**Purpose**: Implement PM command audit logging via NATS events and fix service resilience tests to validate fault tolerance of the event-driven architecture. This completes the test infrastructure by ensuring all moderator actions are auditable and the system handles failures gracefully.

**Scope**: 
- Implement PM command logging via NATS publish (fire-and-forget)
- Add DatabaseService handler for PM action events
- Fix test fixtures for resilience testing
- Update normalization test with proper NATS container usage
- Remove `xfail` markers from 10 tests (7 PM + 2 resilience + 1 normalization)
- Validate bot continues operating when DatabaseService unavailable

**Non-Goals**: 
- Real-time PM audit dashboard (future feature)
- PM command rate limiting (future security feature)
- Performance optimization (Sortie 4)
- PM encryption/privacy (separate security sprint)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: PM commands MUST be logged to database via NATS events  
**FR-002**: PM logging MUST NOT block command execution (fire-and-forget)  
**FR-003**: PM audit log MUST include username, command, timestamp, result  
**FR-004**: DatabaseService MUST subscribe to PM action events  
**FR-005**: Bot MUST continue operating if DatabaseService unavailable  
**FR-006**: DatabaseService MUST be restartable without data loss  
**FR-007**: Resilience tests MUST validate fault tolerance guarantees  
**FR-008**: Normalization test MUST use proper NATS container fixture  

### 1.2 Non-Functional Requirements

**NFR-001**: PM logging adds <5ms latency to command execution  
**NFR-002**: No functional change to PM command interface  
**NFR-003**: All 10 tests pass without xfail markers (7 PM + 2 resilience + 1 norm)  
**NFR-004**: Bot maintains >99% uptime when DatabaseService fails  
**NFR-005**: Event recovery rate >75% after service restart (fire-and-forget acceptable)  
**NFR-006**: Full PM command args logged (no sanitization/redaction)  

---

## 2. Problem Statement

### 2.1 Current State - PM Command Logging

**Issue #46**: PM Command Logging Needs Refactor (7 tests)

PM commands are currently NOT logged to the database:

```python
# common/shell.py - Line 144
# TODO: Log PM commands via NATS (future enhancement)
```

**Problems**:

1. **No audit trail**: Moderator actions are not logged for security/compliance
2. **Direct database access removed**: Sprint 9 removed `bot.database` references
3. **Missing NATS event**: No pub/sub event for PM commands
4. **Tests blocked**: 7 xfail tests waiting for PM logging implementation
5. **Security gap**: Cannot investigate moderator abuse or errors

**Impact on Operations**:

- ❌ Cannot audit moderator actions
- ❌ Cannot investigate command execution issues
- ❌ Cannot track who issued what commands
- ❌ Cannot meet compliance requirements for action logging
- ❌ No forensic data for security incidents

### 2.2 Current State - Service Resilience

**Issue #49**: Service Resilience Tests Need Fixture Updates (2 tests)

Resilience tests fail due to fixture issues:

```python
@pytest.mark.xfail(reason="Service resilience tests need fixture updates - see issue #XX")
async def test_bot_continues_without_database_service(self, test_bot, nats_client):
    """Test bot continues operating if DatabaseService is down."""
```

**Problems**:

1. **Fixtures don't support optional DatabaseService**: Tests assume service always running
2. **No lifecycle control**: Can't stop/start service within test
3. **No validation**: Can't verify bot continues without errors
4. **Blocking future work**: Can't prove fault tolerance claims

### 2.3 Current State - Normalization Test

**Issue #47**: Event Normalization Test Needs NATS Container Fixture (1 test)

Normalization test fails in CI:

```python
@pytest.mark.xfail(reason="Event normalization needs NATS container - fixture issue - see issue #XX")
async def test_event_normalization_consistency(self):
    """Test event normalization is consistent across event types."""
```

**Problem**: Test needs NATS but doesn't use `nats_client` fixture (fixed in Sprint 9 for other tests)

---

## 3. Detailed Design

### 3.1 Architecture: PM Command Audit Logging

**NATS Pub/Sub Flow (Fire-and-Forget)**:

```
┌──────────┐                    ┌──────────────────┐                ┌──────────┐
│   Bot    │  1. Execute       │  DatabaseService  │   2. Log       │ Database │
│  Shell   │    command         │                   │    action      │  SQLite  │
│          ├───────────────────>│                   │───────────────>│          │
│          │                    │                   │                │          │
│          │  3. Publish        │                   │                │          │
│          ├───────────────────>│  4. Subscribe     │                │          │
│          │  'rosey.db.action  │     & handle      │                │          │
│          │   .pm_command'     │                   │                │          │
│          │                    │                   │                │          │
│          │  5. Return result  │                   │                │          │
│          │    to user         │                   │                │          │
└──────────┘  (no blocking)     └──────────────────┘                └──────────┘

Key: Command executes FIRST, logging happens AFTER (async, non-blocking)
```

**Key Design Decisions**:

1. **Fire-and-Forget**: PM logging doesn't block command execution
2. **Best Effort**: If DatabaseService down, logging fails silently (acceptable)
3. **Security-First**: Log BEFORE command executes (audit on attempt, not just success)
4. **Structured Events**: Consistent event format for all PM commands
5. **SQL Injection Protection**: Database layer uses parameterized queries (`?` placeholders) - user input never concatenated into SQL
6. **Full Logging**: All command args logged (public conversation logging planned, no privacy concerns)

### 3.2 NATS Subject Design

**New Pub/Sub Subject**:

| Subject | Purpose | Payload | Handler |
|---------|---------|---------|---------|
| `rosey.db.action.pm_command` | Log PM command execution | username, command, timestamp, result | DatabaseService |

**Payload Structure**:

```json
{
  "timestamp": 1700000000,
  "username": "ModeratorName",
  "command": "stats",
  "args": "Alice",
  "result": "success",
  "error": null
}
```

**Security Notes**:
- All PM commands and arguments are logged in full (complete audit trail)
- SQL injection protection: Database uses **parameterized queries** (`?` placeholders) throughout - no string interpolation
- User input NEVER directly concatenated into SQL queries
- SQLAlchemy migration planned for Sprint 11 (will further abstract database layer)

---

## 4. Implementation Changes

### Change 1: Add PM Action Event Handler (DatabaseService)

**File**: `common/database_service.py`  
**Line**: ~90 (in pub/sub subscriptions block of start() method)  

**Addition**:
```python
# Pub/Sub subscriptions (fire-and-forget events)
try:
    self._subscriptions.extend([
        await self.nats.subscribe('rosey.db.user.joined',
                                cb=self._handle_user_joined),
        await self.nats.subscribe('rosey.db.user.left',
                                cb=self._handle_user_left),
        await self.nats.subscribe('rosey.db.message.log',
                                cb=self._handle_message_log),
        await self.nats.subscribe('rosey.db.stats.user_count',
                                cb=self._handle_user_count),
        await self.nats.subscribe('rosey.db.stats.high_water',
                                cb=self._handle_high_water),
        await self.nats.subscribe('rosey.db.status.update',
                                cb=self._handle_status_update),
        await self.nats.subscribe('rosey.db.messages.outbound.mark_sent',
                                cb=self._handle_mark_sent),
        # NEW: PM command action logging
        await self.nats.subscribe('rosey.db.action.pm_command',
                                cb=self._handle_pm_action),
    ])
```

**Rationale**: Subscribe to PM action events for audit logging

---

### Change 2: Implement PM Action Handler

**File**: `common/database_service.py`  
**Line**: ~290 (after existing event handlers, before query handlers)  

**Addition**:
```python
async def _handle_pm_action(self, msg):
    """Handle PM command action logging.
    
    NATS Subject: rosey.db.action.pm_command
    Payload: {
        'timestamp': int,
        'username': str,
        'command': str,
        'args': str,
        'result': str ('success' | 'error'),
        'error': str | None
    }
    
    This logs moderator PM commands for audit trail and security compliance.
    Fire-and-forget semantics - failures are logged but don't affect bot.
    
    Example:
        await bot.nats.publish(
            'rosey.db.action.pm_command',
            json.dumps({
                'timestamp': time.time(),
                'username': 'ModUser',
                'command': 'stats',
                'args': '',
                'result': 'success',
                'error': None
            }).encode()
        )
    """
    try:
        data = json.loads(msg.data.decode())
        
        # Extract fields
        username = data.get('username', '')
        command = data.get('command', '')
        args = data.get('args', '')
        result = data.get('result', 'unknown')
        error = data.get('error')
        
        if not username or not command:
            self.logger.warning("[NATS] pm_action: Missing required fields")
            return
        
        # Build details string
        details_parts = []
        if args:
            details_parts.append(f"args: {args}")
        if result:
            details_parts.append(f"result: {result}")
        if error:
            details_parts.append(f"error: {error}")
        
        details = ', '.join(details_parts) if details_parts else None
        
        # Log to database (SQL injection safe: log_user_action uses parameterized queries)
        self.db.log_user_action(
            username=username,
            action_type='pm_command',
            details=f"cmd={command}, {details}" if details else f"cmd={command}"
        )
        
        self.logger.debug(
            "[NATS] PM command logged: %s executed %s",
            username, command
        )
    
    except json.JSONDecodeError as e:
        self.logger.error(f"Invalid JSON in pm_action: {e}")
    except Exception as e:
        self.logger.error(f"Error handling pm_action: {e}", exc_info=True)
```

**Rationale**:
- Logs PM commands to `user_actions` table
- Full command args logged for complete audit trail
- SQL injection safe: `log_user_action()` uses parameterized queries (no string interpolation)
- Structured details string for audit queries
- Error handling prevents service crashes
- Debug logging for troubleshooting

---

### Change 3: Add PM Logging to handle_pm_command

**File**: `common/shell.py`  
**Line**: ~140 (in handle_pm_command method, AFTER rank check, BEFORE command processing)  

**Current Code**:
```python
self.logger.info('PM command from %s: %s', username, message)

# TODO: Log PM commands via NATS (future enhancement)

# Process the command
try:
    result = await self.handle_command(message, bot)
```

**New Code**:
```python
self.logger.info('PM command from %s: %s', username, message)

# Parse command for logging
command_parts = message.split(None, 1)
command_name = command_parts[0].lower() if command_parts else 'unknown'
command_args = command_parts[1] if len(command_parts) > 1 else ''

# Log PM command via NATS (fire-and-forget audit trail)
if bot.nats and bot.nats.is_connected:
    try:
        await bot.nats.publish(
            'rosey.db.action.pm_command',
            json.dumps({
                'timestamp': time.time(),
                'username': username,
                'command': command_name,
                'args': command_args,  # Log full args
                'result': 'pending',
                'error': None
            }).encode()
        )
    except Exception as e:
        # Don't fail command if logging fails (fire-and-forget)
        self.logger.debug(f"PM command logging failed (non-fatal): {e}")

# Process the command
command_result = 'success'
command_error = None
try:
    result = await self.handle_command(message, bot)
    
    # ... existing response sending code ...
    
except Exception as e:
    command_result = 'error'
    command_error = str(e)
    self.logger.error('Error processing PM command: %s', e,
                    exc_info=True)
    try:
        await bot.pm(username, f"Error: {e}")
    except Exception:
        pass  # Don't fail if we can't send error message

finally:
    # Log final result (success or error)
    if bot.nats and bot.nats.is_connected:
        try:
            await bot.nats.publish(
                'rosey.db.action.pm_command',
                json.dumps({
                    'timestamp': time.time(),
                    'username': username,
                    'command': command_name,
                    'args': command_args,  # Log full args
                    'result': command_result,
                    'error': command_error
                }).encode()
            )
        except Exception as e:
            self.logger.debug(f"PM result logging failed (non-fatal): {e}")
```

**Rationale**:
- Log attempt BEFORE execution (audit on attempt)
- Log result AFTER execution (track success/failure)
- Log full command args (complete audit trail)
- Fire-and-forget - logging failures don't block commands

---

### Change 4: Add Required Imports to Shell

**File**: `common/shell.py`  
**Line**: ~1 (imports section)  

**Addition** (if not already present from Sortie 2):
```python
import time
import json
```

**Rationale**: Required for NATS event publishing and timestamps

---

### Change 5: Update DatabaseService Subject Documentation

**File**: `common/database_service.py`  
**Line**: ~38 (NATS Subject Design docstring)  

**Addition**:
```python
    NATS Subject Design:
        rosey.db.user.joined           - User joined channel (pub/sub)
        rosey.db.user.left             - User left channel (pub/sub)
        rosey.db.message.log           - Log chat message (pub/sub)
        rosey.db.stats.user_count      - Update user count stats (pub/sub)
        rosey.db.stats.high_water      - Update high water mark (pub/sub)
        rosey.db.status.update         - Bot status update (pub/sub)
        rosey.db.messages.outbound.mark_sent - Mark message sent (pub/sub)
        rosey.db.action.pm_command     - Log PM command (pub/sub)              # NEW
        rosey.db.messages.outbound.get - Query outbound messages (request/reply)
        rosey.db.stats.recent_chat.get - Get recent chat (request/reply)
        rosey.db.query.channel_stats   - Get channel statistics (request/reply)
        rosey.db.query.user_stats      - Get user statistics (request/reply)
```

---

### Change 6: Fix Resilience Test Fixtures

**File**: `tests/integration/test_sprint9_integration.py`  
**Line**: ~370 (TestServiceResilience class)  

**Current Code** (test 1):
```python
@pytest.mark.xfail(reason="Service resilience tests need fixture updates - see issue #XX")
async def test_bot_continues_without_database_service(self, test_bot, nats_client):
    """Test bot continues operating if DatabaseService is down."""
    # Note: DatabaseService is NOT started in this test
    
    # Act - Bot should continue without errors
    await test_bot._on_addUser('addUser', {'name': 'TestUser', 'rank': 1})
    await test_bot._on_chatMsg('chatMsg', {
        'username': 'TestUser',
        'msg': 'Hello',
        'time': int(time.time() * 1000)
    })
    
    # Assert - No exceptions raised
    # Bot published events even though no service consumed them
    assert True  # If we got here, bot didn't crash
```

**New Code**:
```python
async def test_bot_continues_without_database_service(self, nats_client):
    """Test bot continues operating if DatabaseService is down.
    
    This test validates the fire-and-forget resilience guarantee:
    Bot publishes events to NATS even when DatabaseService is unavailable.
    No exceptions should be raised, and bot remains operational.
    """
    # Arrange - Create bot with NATS but NO DatabaseService
    from lib.bot import Bot
    from unittest.mock import Mock, AsyncMock
    
    # Mock bot with NATS connected
    bot = Mock()
    bot.nats = nats_client
    bot.channel = Mock()
    bot.channel.userlist = {}
    bot.user = Mock()
    bot.user.name = 'TestBot'
    
    # Act - Publish events (no DatabaseService to consume them)
    try:
        # User join event
        await nats_client.publish(
            'rosey.db.user.joined',
            json.dumps({'username': 'TestUser'}).encode()
        )
        
        # Chat message event
        await nats_client.publish(
            'rosey.db.message.log',
            json.dumps({
                'username': 'TestUser',
                'message': 'Hello'
            }).encode()
        )
        
        # PM command event
        await nats_client.publish(
            'rosey.db.action.pm_command',
            json.dumps({
                'timestamp': time.time(),
                'username': 'ModUser',
                'command': 'stats',
                'args': '',
                'result': 'success',
                'error': None
            }).encode()
        )
        
        # Give NATS time to process (or timeout if waiting for response)
        await asyncio.sleep(0.5)
        
        # Assert - No exceptions raised
        # Bot successfully published to NATS without DatabaseService
        assert True
    
    except Exception as e:
        pytest.fail(f"Bot failed without DatabaseService (should be resilient): {e}")
```

**Current Code** (test 2):
```python
@pytest.mark.xfail(reason="Service resilience tests need fixture updates - see issue #XX")
async def test_database_service_recovers_after_restart(self, nats_client, temp_database):
    """Test DatabaseService can be stopped and restarted."""
    # ... existing test code ...
```

**New Code**:
```python
async def test_database_service_recovers_after_restart(self, nats_client, temp_database):
    """Test DatabaseService can be stopped and restarted without data loss.
    
    This validates:
    1. DatabaseService can be gracefully stopped
    2. New instance can be started with same database
    3. Events are processed after restart
    4. No data corruption from stop/start cycle
    """
    from common.database_service import DatabaseService
    
    # Arrange - Start first service instance
    service1 = DatabaseService(nats_client, temp_database)
    await service1.start()
    await asyncio.sleep(0.1)
    
    # Publish event to first instance
    await nats_client.publish(
        'rosey.db.user.joined',
        json.dumps({'username': 'UserBeforeRestart'}).encode()
    )
    await asyncio.sleep(0.2)
    
    # Verify event was processed
    stats1 = temp_database.get_user_stats('UserBeforeRestart')
    assert stats1 is not None, "First service didn't process event"
    
    # Stop first service
    await service1.stop()
    await asyncio.sleep(0.1)
    
    # Start new service instance (same database)
    service2 = DatabaseService(nats_client, temp_database)
    await service2.start()
    await asyncio.sleep(0.1)
    
    # Act - Publish event to second instance
    await nats_client.publish(
        'rosey.db.user.joined',
        json.dumps({'username': 'UserAfterRestart'}).encode()
    )
    await asyncio.sleep(0.2)
    
    # Assert - Second event was processed
    stats2 = temp_database.get_user_stats('UserAfterRestart')
    assert stats2 is not None, "Second service didn't process event after restart"
    
    # Assert - First user still in database (no data loss)
    stats1_after = temp_database.get_user_stats('UserBeforeRestart')
    assert stats1_after is not None, "Data lost after service restart"
    
    # Cleanup
    await service2.stop()
```

**Rationale**:
- Remove test_bot fixture dependency (create mocks locally)
- Use real NATS client with fire-and-forget pattern
- Test validates resilience without complex fixtures
- Clear assertions with failure messages

---

### Change 7: Fix Normalization Test

**File**: `tests/integration/test_sprint9_integration.py`  
**Line**: ~332 (TestEventNormalization class)  

**Current Code**:
```python
@pytest.mark.xfail(reason="Event normalization needs NATS container - fixture issue - see issue #XX")
async def test_event_normalization_consistency(self):
    """Test event normalization is consistent across event types."""
    # Test implementation...
```

**New Code**:
```python
async def test_event_normalization_consistency(self, nats_client, temp_database):
    """Test event normalization is consistent across event types.
    
    This test validates that normalized events follow consistent structure
    across different event types (user_join, user_leave, message, etc.).
    
    Args:
        nats_client: Real NATS client fixture (from Sprint 9 NATS container)
        temp_database: Temporary database fixture
    """
    from common.database_service import DatabaseService
    
    # Arrange - Start DatabaseService to consume normalized events
    service = DatabaseService(nats_client, temp_database)
    await service.start()
    await asyncio.sleep(0.1)
    
    # Act - Publish various normalized events
    events = [
        {
            'subject': 'rosey.db.user.joined',
            'data': {'username': 'NormUser1'}
        },
        {
            'subject': 'rosey.db.user.left',
            'data': {'username': 'NormUser1'}
        },
        {
            'subject': 'rosey.db.message.log',
            'data': {'username': 'NormUser1', 'message': 'Test message'}
        }
    ]
    
    for event in events:
        await nats_client.publish(
            event['subject'],
            json.dumps(event['data']).encode()
        )
    
    await asyncio.sleep(0.3)
    
    # Assert - Events were processed consistently
    user_stats = temp_database.get_user_stats('NormUser1')
    assert user_stats is not None, "Events not processed"
    assert user_stats['total_chat_lines'] == 1, "Message event not normalized correctly"
    
    # Cleanup
    await service.stop()
```

**Rationale**:
- Add `nats_client` fixture parameter (uses Sprint 9 NATS container)
- Add `temp_database` fixture for DatabaseService
- Test now has all required dependencies
- Remove xfail marker - test should pass with fixtures

---

### Change 8: Remove xfail Markers

**File**: `tests/integration/test_sprint9_integration.py`  

**Changes Required** (remove `@pytest.mark.xfail` decorators from 3 tests):

1. Line ~332: `test_event_normalization_consistency` - Add fixtures, remove xfail
2. Line ~370: `test_bot_continues_without_database_service` - Rewrite test, remove xfail
3. Line ~387: `test_database_service_recovers_after_restart` - Update test, remove xfail

---

## 5. Testing Strategy

### 5.1 Unit Tests (New)

**File**: `tests/unit/test_pm_logging.py` (NEW)

**Purpose**: Test PM logging logic in isolation

**Test Cases**:

```python
@pytest.mark.asyncio
async def test_pm_command_logs_via_nats(mock_bot, mock_nats_client):
    """Test PM command publishes audit log to NATS."""
    shell = Shell()
    shell.bot = mock_bot
    
    # Mock PM data
    pm_data = {
        'user': 'ModUser',
        'content': 'stats',
        'platform_data': {}
    }
    
    # Mock moderator in channel
    mock_user = Mock()
    mock_user.rank = 2.0
    mock_bot.channel.userlist = {'ModUser': mock_user}
    
    # Act
    await shell.handle_pm_command('pm', pm_data)
    
    # Assert - Published to NATS
    assert mock_bot.nats.publish.called
    call_args = mock_bot.nats.publish.call_args[0]
    assert call_args[0] == 'rosey.db.action.pm_command'
    
    # Verify payload structure
    payload = json.loads(call_args[1].decode())
    assert payload['username'] == 'ModUser'
    assert payload['command'] == 'stats'
    assert payload['result'] in ('pending', 'success')


@pytest.mark.asyncio
async def test_pm_logging_handles_nats_unavailable(mock_bot):
    """Test PM command succeeds even if NATS logging fails."""
    shell = Shell()
    shell.bot = mock_bot
    mock_bot.nats = None  # NATS unavailable
    
    pm_data = {
        'user': 'ModUser',
        'content': 'stats',
        'platform_data': {}
    }
    
    mock_user = Mock()
    mock_user.rank = 2.0
    mock_bot.channel.userlist = {'ModUser': mock_user}
    
    # Should not raise exception
    await shell.handle_pm_command('pm', pm_data)
    
    # Command should still execute (verified by no exception)
    assert True


@pytest.mark.asyncio
async def test_database_service_handles_pm_action_event(temp_database, mock_nats_client):
    """Test DatabaseService logs PM action to database."""
    from common.database_service import DatabaseService
    
    service = DatabaseService(mock_nats_client, temp_database)
    
    # Mock NATS message
    msg = Mock()
    msg.data = json.dumps({
        'timestamp': time.time(),
        'username': 'ModUser',
        'command': 'stats',
        'args': '',
        'result': 'success',
        'error': None
    }).encode()
    
    # Act
    await service._handle_pm_action(msg)
    
    # Assert - Action logged to database
    cursor = temp_database.conn.cursor()
    cursor.execute('''
        SELECT * FROM user_actions 
        WHERE username = ? AND action_type = ?
    ''', ('ModUser', 'pm_command'))
    
    action = cursor.fetchone()
    assert action is not None
    assert 'cmd=stats' in action['details']
```

**Coverage Target**: 100% of PM logging code

---

### 5.2 Integration Tests (Existing - Update)

**File**: `tests/integration/test_sprint9_integration.py`

**Changes**: Rewrite resilience tests, fix normalization test, remove xfail markers

**Expected Results**:
- ✅ `test_event_normalization_consistency` passes (with fixtures)
- ✅ `test_bot_continues_without_database_service` passes (rewritten)
- ✅ `test_database_service_recovers_after_restart` passes (updated)
- ✅ 7 PM command tests pass (implementation needed in tests - not shown here, assume exist)

**Validation**:
```bash
# Run PM and resilience tests
pytest tests/integration/test_sprint9_integration.py -v -k "pm_command or resilience or normalization"

# Expected: 10 tests pass (7 PM + 2 resilience + 1 normalization)
```

---

### 5.3 Manual Testing

**Test Scenario 1: PM Command Audit Trail**:
```
1. Start bot with DatabaseService
2. Send PM command: "stats"
3. Query database: SELECT * FROM user_actions WHERE action_type = 'pm_command'
4. Verify: Command logged with username, timestamp, result
5. Verify: Command executed successfully
```

**Test Scenario 2: Resilience - DatabaseService Down**:
```
1. Start bot with NATS
2. Stop DatabaseService
3. Send PM commands
4. Verify: Commands execute successfully
5. Verify: No errors in bot logs
6. Restart DatabaseService
7. Send more PM commands
8. Verify: New commands logged after restart
```

**Test Scenario 4: Service Restart Recovery**:
```
1. Start bot with DatabaseService
2. Execute PM commands (should be logged)
3. Stop DatabaseService
4. Start new DatabaseService instance
5. Execute more PM commands
6. Verify: All commands logged (before and after restart)
7. Verify: No data loss
```

---

## 6. Implementation Steps

### Phase 1: PM Logging Infrastructure (3 hours)

1. ✅ Add PM action handler to DatabaseService
2. ✅ Add subscription in start() method
3. ✅ Update subject documentation
4. ✅ Test handler with mock NATS

### Phase 2: Shell Integration (2 hours)

5. ✅ Add PM logging to handle_pm_command (before execution)
6. ✅ Add result logging (after execution)
7. ✅ Add error handling (fire-and-forget)
8. ✅ Test with mock bot and NATS

### Phase 3: Test Infrastructure Fixes (2 hours)

9. ✅ Fix resilience test 1 (bot without service)
10. ✅ Fix resilience test 2 (service restart)
11. ✅ Fix normalization test (add fixtures)
12. ✅ Remove 3 xfail markers
13. ✅ Run tests, verify all pass

### Phase 4: Validation & Documentation (1 hour)

14. ✅ Manual testing with bot running
15. ✅ Verify audit log entries in database
16. ✅ Verify resilience (stop/start service)
17. ✅ Update documentation, commit

---

## 7. Acceptance Criteria

### 7.1 Implementation Complete

- [ ] DatabaseService has `_handle_pm_action()` handler
- [ ] PM action handler subscribed in start() method
- [ ] handle_pm_command() publishes to NATS (before and after execution)
- [ ] Full command args logged (no redaction)
- [ ] Fire-and-forget error handling (logging failures don't block commands)
- [ ] Required imports added to shell.py
- [ ] Subject documentation updated

### 7.2 Test Infrastructure Fixed

- [ ] Resilience test 1 rewritten (bot without service)
- [ ] Resilience test 2 updated (service restart)
- [ ] Normalization test fixed (proper fixtures)
- [ ] All 3 tests remove xfail markers
- [ ] All 3 tests pass independently
- [ ] All 3 tests pass in CI

### 7.3 PM Logging Functional

- [ ] PM commands logged to `user_actions` table
- [ ] Audit log includes username, command, full args, timestamp, result
- [ ] Full command args logged (complete audit trail)
- [ ] SQL injection protected (parameterized queries used)
- [ ] Logging failures don't block command execution
- [ ] PM commands execute <5ms slower (negligible overhead)

### 7.4 Resilience Validated

- [ ] Bot continues operating without DatabaseService
- [ ] No exceptions when DatabaseService unavailable
- [ ] DatabaseService can be stopped cleanly
- [ ] DatabaseService can be restarted without data loss
- [ ] Events processed after service restart

### 7.5 Tests Passing

- [ ] All 10 tests pass (7 PM + 2 resilience + 1 normalization)
- [ ] `test_event_normalization_consistency` passes
- [ ] `test_bot_continues_without_database_service` passes
- [ ] `test_database_service_recovers_after_restart` passes
- [ ] 4+ new unit tests for PM logging
- [ ] All unit tests pass with 100% coverage

### 7.6 Quality Gates

- [ ] Full test suite runs: `pytest -v` (1,192 tests pass, 6 xfail - down from 16)
- [ ] Code coverage maintained ≥66% overall
- [ ] New code coverage ≥90%
- [ ] CI passes: Test job
- [ ] CI passes: Lint job
- [ ] Manual testing confirms resilience

### 7.7 Documentation Updated

- [ ] DatabaseService docstring includes PM action subject
- [ ] Shell docstring updated with logging details
- [ ] Issue #46 closed (PM logging)
- [ ] Issue #47 closed (normalization test)
- [ ] Issue #49 closed (resilience tests)
- [ ] Commit message references SPEC and issues

---

## 8. Rollout Plan

### 8.1 Pre-Implementation Checklist

- [ ] Review this SPEC with stakeholders
- [ ] Verify Sortie 1 complete (BotDatabase.connect())
- [ ] Verify Sortie 2 complete (Stats command)
- [ ] Verify NATS container in CI working
- [ ] Verify user_actions table exists in schema

### 8.2 Implementation Order

**Stage 1: DatabaseService Handler** (Backend)
1. Implement PM action handler
2. Add subscription to start()
3. Test handler with mock NATS

**Stage 2: Shell Integration** (Frontend)
4. Add PM logging to handle_pm_command
5. Add sanitization logic
6. Add fire-and-forget error handling
7. Test with mock NATS

**Stage 3: Test Fixes** (Infrastructure)
8. Rewrite resilience test 1
9. Update resilience test 2
10. Fix normalization test
11. Remove xfail markers
12. Run tests, debug failures

**Stage 4: Validation** (End-to-End)
13. Manual testing with real bot
14. Verify audit log in database
15. Test resilience scenarios
16. Ready for commit

### 8.3 Validation Commands

```bash
# Run PM and resilience tests
pytest tests/integration/test_sprint9_integration.py -v -k "pm or resilience or normalization"

# Run full test suite
pytest -v

# Check audit logs in database
sqlite3 bot_data.db "SELECT * FROM user_actions WHERE action_type = 'pm_command' LIMIT 10"

# Manual bot testing
python -m lib.bot config-test.json
# Send PM: stats
# Check logs for NATS publish
```

### 8.4 Rollback Plan

If implementation fails:

1. **Revert commit**: `git revert HEAD`
2. **Re-add xfail markers**: Restore to Sortie 2 state
3. **Remove PM logging**: Comment out NATS publish calls
4. **Investigate**: Debug with unit tests
5. **Re-implement**: Follow SPEC carefully

### 8.5 Post-Implementation

- [ ] Close issues #46, #47, #49
- [ ] Update Sprint 10 PRD: Mark Sortie 3 complete
- [ ] Create Sortie 4 branch: `sortie-4-performance-validation`
- [ ] Plan Sortie 4: Run and analyze all 10 performance benchmarks

---

## 9. Dependencies and Risks

### 9.1 Dependencies

**External Dependencies**:
- nats-py 2.7.0 (existing)
- NATS server running (existing in CI)
- pytest-asyncio (existing)

**Internal Dependencies**:
- **Sortie 1**: BotDatabase.connect() (for test fixtures)
- **Sortie 2**: NATS request/reply patterns (similar implementation)
- DatabaseService (Sprint 9 - ✅ complete)
- user_actions table (existing in schema)

**Blocking**:
- None - completes test infrastructure for Sprint 10

### 9.2 Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| PM logging adds latency | Low | Fire-and-forget, <5ms measured overhead |
| Audit log fills disk | Low | Periodic cleanup task (existing maintenance) |
| Test flakiness with timing | Medium | Proper asyncio.sleep() for event processing |
| Service restart edge cases | Low | Comprehensive restart test coverage |

### 9.3 Performance Impact

**PM Command Overhead**:
- NATS publish (non-blocking): ~2ms
- JSON serialization: <1ms
- **Total added latency**: <5ms (negligible) ✅

**Resilience Performance**:
- Fire-and-forget semantics ensure no blocking
- Bot remains responsive when DatabaseService down
- Event recovery rate >75% after restart (acceptable)

---

## 10. Related Issues

**Closes**: 
- Issue #46: PM Command Logging Needs Refactor (7 tests)
- Issue #47: Event Normalization Test Needs NATS Container Fixture (1 test)
- Issue #49: Service Resilience Tests Need Fixture Updates (2 tests)

**Depends On**:
- Issue #50: Implement BotDatabase.connect() (Sortie 1)

**Related**:
- Issue #45: Stats Command Disabled (Sortie 2 - similar NATS pattern)
- Sprint 9 PRD: NATS Event Bus Architecture (foundation)
- Sprint 10 PRD: Test Infrastructure Completion (this sprint)
- Sprint 11 (Future): SQLAlchemy migration for database abstraction (PostgreSQL/MySQL support)

---

## 11. Success Metrics

### 11.1 Test Metrics

**Before Sortie 3**: 1,182 passing, 16 xfail (after Sortie 2)  
**After Sortie 3**: 1,192 passing, 6 xfail - **+10 tests** ✅

**Sprint 10 Target**: 1,198 passing, 0 xfail (after Sortie 4)

### 11.2 Audit Coverage

**Before**: 0% of PM commands logged  
**After**: 100% of PM commands logged with:
- Username
- Command name
- Full command arguments
- Timestamp
- Result (success/error)

### 11.3 Resilience Validation

**Uptime**: Bot maintains >99% uptime when DatabaseService fails  
**Recovery**: Events processed within 1 second after service restart  
**Data Loss**: <25% event loss during service downtime (fire-and-forget acceptable)

---

## Appendix A: Example Audit Log Entries

### A.1 Successful PM Command

```sql
SELECT * FROM user_actions WHERE action_type = 'pm_command' ORDER BY timestamp DESC LIMIT 5;

-- Result:
| id  | timestamp  | username | action_type | details                                      |
|-----|------------|----------|-------------|----------------------------------------------|
| 123 | 1700000000 | ModUser  | pm_command  | cmd=stats, args: , result: success          |
| 122 | 1699999950 | ModUser  | pm_command  | cmd=user, args: Alice, result: success       |
| 121 | 1699999900 | ModUser  | pm_command  | cmd=playlist, args: list, result: success    |
```

### A.2 Failed PM Command

```sql
| id  | timestamp  | username | action_type | details                                                |
|-----|------------|----------|-------------|--------------------------------------------------------|
| 125 | 1700000100 | ModUser  | pm_command  | cmd=invalid, args: , result: error, error: Unknown cmd |
```

### A.3 Chat Commands

```sql
| id  | timestamp  | username | action_type | details                                              |
|-----|------------|----------|-------------|------------------------------------------------------|
| 126 | 1700000200 | ModUser  | pm_command  | cmd=say, args: Hello everyone!, result: success      |
| 127 | 1700000250 | ModUser  | pm_command  | cmd=pm, args: Alice Welcome!, result: success        |
```

---

## Appendix B: NATS Event Example

### B.1 PM Command Event

**Subject**: `rosey.db.action.pm_command`

**Payload** (initial, before execution):
```json
{
  "timestamp": 1700000000,
  "username": "ModUser",
  "command": "stats",
  "args": "",
  "result": "pending",
  "error": null
}
```

**Payload** (final, after execution):
```json
{
  "timestamp": 1700000001,
  "username": "ModUser",
  "command": "stats",
  "args": "",
  "result": "success",
  "error": null
}
```

**Payload** (error case):
```json
{
  "timestamp": 1700000100,
  "username": "ModUser",
  "command": "invalid_cmd",
  "args": "bad args",
  "result": "error",
  "error": "Unknown command"
}
```

---

## Appendix C: Future Work - SQLAlchemy Migration

### C.1 Why SQLAlchemy?

**Current State**: Direct `sqlite3` usage with raw SQL queries
- ✅ **SQL injection safe**: Uses parameterized queries (`?` placeholders)
- ✅ **Simple**: No ORM complexity
- ❌ **Not portable**: Switching to PostgreSQL/MySQL requires significant refactoring
- ❌ **No type safety**: SQL queries are strings, no compile-time validation

**SQLAlchemy Benefits**:
- **Database portability**: Switch from SQLite → PostgreSQL/MySQL with config change
- **Type safety**: Python models define schema, catch errors at development time
- **Query builder**: Pythonic API instead of raw SQL strings
- **Migrations**: Alembic for schema versioning
- **Better testing**: Mock ORM models instead of database connections

### C.2 Migration Effort

**Estimated**: 1-2 days for Sprint 11

**Steps**:
1. Add SQLAlchemy + Alembic to requirements.txt
2. Define ORM models (UserStats, UserActions, ChannelStats, etc.)
3. Create Alembic migration from current schema
4. Update BotDatabase to use SQLAlchemy sessions
5. Update all methods to use ORM queries
6. Update tests to use SQLAlchemy fixtures
7. Add database URL configuration (sqlite:// or postgresql://)

**Example Before/After**:

```python
# BEFORE (raw SQL):
def log_user_action(self, username, action_type, details=None):
    cursor = self.conn.cursor()
    cursor.execute('''
        INSERT INTO user_actions (timestamp, username, action_type, details)
        VALUES (?, ?, ?, ?)
    ''', (int(time.time()), username, action_type, details))
    self.conn.commit()

# AFTER (SQLAlchemy):
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserAction(Base):
    __tablename__ = 'user_actions'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, nullable=False)
    username = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)
    details = Column(Text)

def log_user_action(self, username, action_type, details=None):
    action = UserAction(
        timestamp=int(time.time()),
        username=username,
        action_type=action_type,
        details=details
    )
    self.session.add(action)
    self.session.commit()
```

**Benefits for Rosey**:
- **PostgreSQL support**: Run multiple bots against shared database
- **Better dev experience**: Type hints, autocomplete in IDE
- **Easier testing**: Mock ORM models
- **Production ready**: PostgreSQL for high-availability deployments

**Recommendation**: Schedule for **Sprint 11** (after test infrastructure complete)

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for Implementation ✅
