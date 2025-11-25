# Event Normalization Audit - TODO Summary

**Date**: January 2025  
**Status**: Sprint 9 Sortie 2 Complete ✅  
**Priority**: HIGH (Technical Debt - Blocks Multi-Platform Support)

**Last Updated**: January 2025 - Sortie 2 Implementation Complete

---

## Overview

This document summarizes the comprehensive audit of Rosey-Robot's event normalization layer and NATS-first architecture migration. The audit identified **17 locations** requiring changes to achieve platform-agnostic, properly-isolated architecture.

### Sprint 9 Progress

**Sortie 1 Complete** ✅ (5 items):
- ✅ Message event normalization (documentation)
- ✅ User join event with user_data field
- ✅ User leave event with optional user_data
- ✅ User list event with object array (BREAKING CHANGE)
- ✅ PM event with recipient field

**Sortie 2 Complete** ✅ (3 items):
- ✅ Bot user list handler (uses normalized 'users' array)
- ✅ Bot user join handler (uses normalized 'user_data')
- ✅ Bot user leave handler (uses normalized 'user' field)

**Sortie 3 Complete** ✅ (3 items):
- ✅ Database NATS service (`common/database_service.py` created)
- ✅ NATS subject hierarchy defined (9 subjects)
- ✅ Standalone service support with CLI

**Remaining** (6 items):
- ⏳ Bot NATS migration (replace direct db calls) - Sortie 4
- ⏳ Shell PM handler (1 item) - After Sortie 3
- ⏳ Bot message handler documentation (1 item) - Documentation only
- ⏳ NATS connection management (2 items) - Sortie 4-6

### Architectural Goals

**Current State**: 
1. ~~Event handlers inconsistently access normalized fields vs `platform_data`~~ ✅ Connection layer complete
2. Bot layer directly calls database methods (`self.db.user_joined()`) violating layer isolation
3. Components are tightly coupled - cannot run in separate processes

**Target State**: 
1. ✅ Connection layer uses normalized fields for platform-agnostic operation (COMPLETE)
2. ALL inter-layer communication flows through NATS event bus - no direct method calls
3. Bot publishes events to NATS → Database subscribes to NATS and updates → Plugins subscribe to NATS for data
4. Request/reply pattern via NATS for synchronous operations (queries, confirmations)
5. True process isolation - bot, database, plugins can run in separate processes/containers

### Key Principles

> **"The normalization layer should always win where possible."**
> — Architecture Decision, Sprint 8 Retrospective

> **"All layers communicate via NATS - no direct calls between bot/database/plugins."**
> — NATS-First Architecture Principle

---

## TODO Locations

### Critical Path: Connection Layer (5 items) ✅ COMPLETE

These foundation issues have been fixed in Sprint 9 Sortie 1. All other TODOs depend on these being resolved.

#### 1. Message Event Normalization ✅ COMPLETE
**File**: `lib/connection/cytube.py`  
**Line**: 479  
**Severity**: LOW (already mostly complete)  
**Status**: ✅ Complete - Documentation added

**Implementation**:
```python
# ✅ NORMALIZATION COMPLETE: Platform-agnostic message structure
# All top-level fields are normalized, platform-specific data in platform_data
if event == 'chatMsg':
    return ('message', {
        'user': data.get('username', ''),
        'content': data.get('msg', ''),
        'timestamp': data.get('time', 0) // 1000,
        'platform_data': data
    })
```

**Completed**:
- ✅ Structure verified correct
- ✅ Documentation added
- ✅ Unit tests created (test_message_structure)

---

#### 2. User Join Event Normalization ✅ COMPLETE
**File**: `lib/connection/cytube.py`  
**Line**: 491  
**Severity**: HIGH (breaks platform-agnostic user handling)  
**Status**: ✅ Complete - user_data field added

**Implementation**:
```python
# ✅ NORMALIZATION COMPLETE: Adds user_data for platform-agnostic user handling
# Includes both 'user' (string) and 'user_data' (full normalized object)
elif event == 'addUser':
    return ('user_join', {
        'user': data.get('name', ''),
        'user_data': self._normalize_cytube_user(data),
        'timestamp': data.get('time', 0),
        'platform_data': data
    })
```

**Helper Method Added**:
```python
def _normalize_cytube_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize CyTube user object to platform-agnostic structure."""
    return {
        'username': user_data.get('name', ''),
        'rank': user_data.get('rank', 0),
        'is_afk': user_data.get('afk', False),
        'is_moderator': user_data.get('rank', 0) >= 2,
        'meta': user_data.get('meta', {})
    }
```

**Completed**:
- ✅ Helper function created for reusable normalization
- ✅ user_data field added with full normalized user object
- ✅ Unit tests created (test_user_join_includes_user_data, test_user_join_guest),
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Impact**: Bot handler `_on_user_join` currently accesses `platform_data` due to this missing field.

---

#### 3. User Leave Event Normalization  COMPLETE
**File**: `lib/connection/cytube.py`
**Line**: 501
**Status**:  Complete - optional user_data added

**Completed**: Optional user_data field added when CyTube provides rank/afk fields. Unit tests created.

---

#### 4. User List Event Normalization  COMPLETE (BREAKING CHANGE)
**File**: `lib/connection/cytube.py`
**Line**: 510
**Status**:  Complete - BACKWARDS structure fixed

**Completed**: Fixed critical bug where users array contained strings instead of objects. Unit tests created.  BREAKING CHANGE requires Sortie 2 handler updates.

---

#### 5. PM Event Normalization  COMPLETE
**File**: `lib/connection/cytube.py`
**Line**: 520
**Status**:  Complete - recipient field added

**Completed**: Recipient field added (bot's username). Unit tests created.

---

### Dependent: Bot Event Handlers (4 items)

These handlers currently work around incomplete normalization by accessing `platform_data`. They must be updated **after** connection layer is fixed.

#### 6. Bot User List Handler ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 266  
**Severity**: HIGH (depends on #4 ✅)  
**Status**: ✅ Complete - uses normalized 'users' array

**Implementation** (Sortie 2):
```python
# ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'users' array
users_data = data.get('users', [])
for user in users_data:
    self._add_user(user)  # Updated to handle both normalized and CyTube format
```

**Completed**:
- ✅ Uses normalized 'users' field
- ✅ _add_user() updated to accept both 'username' and 'name'
- ✅ All tests updated and passing
- ✅ Enhanced logging added

**Dependencies**: Blocked by #4 (User List Event Normalization) ✅ COMPLETE

---

#### 7. Bot User Join Handler ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 278  
**Severity**: HIGH (depends on #2 ✅)  
**Status**: ✅ Complete - uses normalized 'user_data' field

**Implementation** (Sortie 2):
```python
# ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'user_data' field
user_data = data.get('user_data', {})
username = data.get('user', user_data.get('username', ''))

if user_data:
    self._add_user(user_data)
    self.logger.info('User joined: %s (rank=%s)', username, user_data.get('rank', 0))
else:
    self.logger.warning('User join without user_data: %s', username)
```

**Completed**:
- ✅ Uses normalized 'user_data' field
- ✅ Enhanced logging with rank information
- ✅ Graceful handling when user_data missing
- ✅ All tests updated and passing

**Dependencies**: Blocked by #2 (User Join Event Normalization) ✅ COMPLETE

---

#### 8. Bot User Leave Handler ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 298  
**Severity**: MEDIUM (depends on #3 ✅)  
**Status**: ✅ Complete - uses normalized 'user' field, optionally 'user_data'

**Implementation** (Sortie 2):
```python
# ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'user' field
username = data.get('user', '')
user_data = data.get('user_data', None)  # May be None

if username:
    # Enhanced logging if user_data available
    if user_data:
        rank = user_data.get('rank', 0)
        was_mod = user_data.get('is_moderator', False)
        self.logger.info('User left: %s (rank=%s, mod=%s)', username, rank, was_mod)
    else:
        self.logger.info('User left: %s', username)
```

**Completed**:
- ✅ Uses normalized 'user' field
- ✅ Optional enhanced logging with user_data
- ✅ Graceful handling when user_data not present
- ✅ All tests updated and passing

**Dependencies**: Blocked by #3 (User Leave Event Normalization) ✅ COMPLETE

---

#### 9. Bot Message Handler
**File**: `lib/bot.py`  
**Line**: 400  
**Severity**: NONE (already correct!)  
**Status**: ✅ **This is the correct pattern** - example for others

```python
# TODO: NORMALIZATION - This is correct pattern, all handlers should follow this
# Use normalized fields (user, content) - no platform_data access needed
```

**Current Code** (CORRECT):
```python
username = data.get('user')
msg = data.get('content', '')
if username:
    self.db.user_chat_message(username, msg)
```

**Action Required**:
- ✅ Code is already correct
- ⏳ Use as reference example in documentation
- ⏳ Add to NORMALIZATION_SPEC.md as best practice

---

### Component: Shell (1 item)

#### 10. Shell PM Handler
**File**: `common/shell.py`  
**Line**: 103  
**Severity**: MEDIUM (depends on #5)  
**Status**: ⚠️ Has fallback to `platform_data`

```python
# TODO: NORMALIZATION - Shell should only use normalized fields (user, content)
# Platform-specific access to platform_data should be removed once normalization is complete
```

**Current Code** (Workaround):
```python
platform_data = data.get('platform_data', {})
username = data.get('user', platform_data.get('username', ''))
message = data.get('content', platform_data.get('msg', '')).strip()
```

**After #5 Fixed** (Correct):
```python
username = data.get('user', '')
message = data.get('content', '').strip()
# No platform_data access needed
```

**Dependencies**: Blocked by #5 (PM Event Normalization)

---

### CRITICAL: Direct Database Calls - ANTI-PATTERN (6+ items)

These are **violations of the NATS-First Architecture**. The bot layer directly calls database methods instead of publishing to NATS. This creates tight coupling and prevents process isolation.

#### 11. Bot User Join Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 329-370 (Sortie 4)  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
async def _on_user_join(self, _, data):
    # ... normalization handling ...
    
    if self.nats:
        # Publish to NATS
        await self.nats.publish('rosey.db.user.joined', json.dumps({
            'username': username,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug('[NATS] Published user_joined event: username=%s', username)
    elif self.db:
        # Fallback to direct database call
        self.db.user_joined(username)
        self.logger.debug('[DB] Direct call to user_joined(): username=%s', username)
```

**Completed**:
- ✅ Publishes to 'rosey.db.user.joined' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Handler converted to async
- ✅ Also publishes high water mark update
- ✅ All tests passing (1131 total)
- ✅ NATS integration tests added (test_bot_nats_integration.py)

**Impact**: 
- ✅ Bot and database can now run in separate processes
- ✅ Horizontally scalable via NATS
- ✅ Plugins can observe user join events on NATS bus

---

#### 12. Bot User Leave Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 372-407 (Sortie 4)  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
async def _on_user_leave(self, _, data):
    # ... normalization handling ...
    
    if self.nats:
        await self.nats.publish('rosey.db.user.left', json.dumps({
            'username': username,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug('[NATS] Published user_left event: username=%s', username)
    elif self.db:
        self.db.user_left(username)
        self.logger.debug('[DB] Direct call to user_left(): username=%s', username)
```

**Completed**:
- ✅ Publishes to 'rosey.db.user.left' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Handler already async (from Sortie 2)
- ✅ All tests passing

---

#### 13. Bot Message Logging Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 495-515 (Sortie 4)  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
async def _on_message(self, _, data):
    # ... message handling ...
    
    if self.nats:
        await self.nats.publish('rosey.db.message.log', json.dumps({
            'username': username,
            'message': msg,
            'timestamp': int(time.time())
        }).encode())
        self.logger.debug('[NATS] Published message_log event: user=%s, msg=%s...', username, msg[:50])
    elif self.db:
        self.db.user_chat_message(username, msg)
        self.logger.debug('[DB] Direct call to user_chat_message(): user=%s', username)
```

**Completed**:
- ✅ Publishes to 'rosey.db.message.log' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Handler converted to async
- ✅ All tests passing

---

#### 14. Bot User Count Logging Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 515-549 (Sortie 4)  
**Severity**: **HIGH** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
async def _log_user_counts_periodically(self):
    while True:
        await asyncio.sleep(300)  # 5 minutes
        
        if self.channel and self.channel.userlist:
            chat_users = len(self.channel.userlist)
            connected_users = len(self.channel.userlist)
            
            try:
                if self.nats:
                    await self.nats.publish('rosey.db.stats.user_count', json.dumps({
                        'chat_count': chat_users,
                        'connected_count': connected_users,
                        'timestamp': int(time.time())
                    }).encode())
                    self.logger.debug('[NATS] Published user_count: chat=%d, conn=%d', 
                                    chat_users, connected_users)
                elif self.db:
                    self.db.log_user_count(chat_users, connected_users)
                    self.logger.debug('[DB] Logged user count: chat=%d, conn=%d', 
                                    chat_users, connected_users)
```

**Completed**:
- ✅ Publishes to 'rosey.db.stats.user_count' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Fixed bug: changed `.count` to `len()` for dict-based userlist
- ✅ Now works in NATS-only mode (no DB requirement)
- ✅ All tests passing

---

#### 15. Bot Status Update Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 551-601 (Sortie 4)  
**Severity**: **HIGH** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
async def _update_current_status_periodically(self):
    while True:
        await asyncio.sleep(10)
        
        if self.channel:
            status_data = {
                'bot_name': self.channel.username,
                # ... other status fields ...
            }
            
            try:
                if self.nats:
                    await self.nats.publish('rosey.db.status.update', 
                                          json.dumps(status_data).encode())
                    self.logger.debug('[NATS] Published status_update')
                elif self.db:
                    self.db.update_current_status(**status_data)
                    self.logger.debug('[DB] Updated current status directly')
```

**Completed**:
- ✅ Publishes to 'rosey.db.status.update' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Status updates now visible on event bus
- ✅ All tests passing

---

#### 16. Bot High Water Mark Update Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Lines**: 230-247 (usercount), 329-370 (user_join) (Sortie 4)  
**Severity**: **MEDIUM** (violates layer isolation)  
**Status**: ✅ **COMPLETE** - Now uses NATS with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4):
# Location 1: _on_usercount handler (now async)
async def _on_usercount(self, _, data):
    usercount = data if isinstance(data, int) else data.get('count', 0)
    self.channel.userlist.connected = usercount
    
    if self.nats:
        await self.nats.publish('rosey.db.stats.high_water', json.dumps({
            'user_count': len(self.channel.userlist),
            'connected_count': usercount,
            'timestamp': int(time.time())
        }).encode())
    elif self.db:
        self.db.update_high_water_mark(len(self.channel.userlist), usercount)

# Location 2: _on_user_join handler (now async)
# Also publishes high_water after user_joined event
```

**Completed**:
- ✅ Publishes to 'rosey.db.stats.high_water' via NATS
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Updated in multiple locations (usercount + user_join)
- ✅ Handler converted to async
- ✅ All tests passing

**Note**: Multiple locations all now use NATS - consistent pattern throughout.

---

#### 17. Bot Outbound Message Query Database Call ✅ COMPLETE
**File**: `lib/bot.py`  
**Line**: 602-745 (Sortie 4)  
**Severity**: **CRITICAL** (synchronous query - needs request/reply)  
**Status**: ✅ **COMPLETE** - Now uses NATS request/reply with dual-mode fallback (Sortie 4)

```python
# ✅ NORMALIZATION COMPLETE (Sortie 4): Request/Reply Pattern
async def _process_outbound_messages_periodically(self):
    while True:
        await asyncio.sleep(2)
        
        if self.connection.is_connected and self.channel.permissions:
            try:
                # Query via NATS request/reply
                if self.nats:
                    try:
                        response = await self.nats.request(
                            'rosey.db.messages.outbound.get',
                            json.dumps({
                                'username': self.channel.username,
                                'limit': 10
                            }).encode(),
                            timeout=2.0
                        )
                        messages = json.loads(response.data.decode())
                        self.logger.debug('[NATS] Got %d outbound messages', len(messages))
                    except asyncio.TimeoutError:
                        self.logger.warning('[NATS] Request timeout for outbound messages')
                        messages = []
                elif self.db:
                    messages = self.db.get_unsent_outbound_messages(
                        username=self.channel.username, limit=10
                    )
                    self.logger.debug('[DB] Got %d outbound messages', len(messages))
                
                # Process and mark as sent via NATS
                for msg in messages:
                    await self.chat(msg['message'])
                    
                    if self.nats:
                        await self.nats.publish('rosey.db.messages.outbound.mark_sent',
                                              json.dumps({'id': msg['id']}).encode())
                    elif self.db:
                        self.db.mark_outbound_sent(msg['id'])
```

**Completed**:
- ✅ Uses NATS request/reply pattern for queries
- ✅ Publishes 'rosey.db.messages.outbound.mark_sent' after sending
- ✅ Dual-mode operation (NATS primary, DB fallback)
- ✅ Timeout handling (2s with graceful degradation)
- ✅ Error handling for NATS failures
- ✅ All tests passing
- ✅ Request/reply integration tests added

**Note**: This was a **query** operation requiring response - correctly uses NATS request/reply pattern (not pub/sub).

---

## Implementation Roadmap

### Phase 0: NATS Infrastructure (NEW - Foundation for EVERYTHING)
**Priority**: **BLOCKING** - Must be done first  
**Estimated Effort**: 6-8 hours  
**Blockers**: None

1. ✅ **Setup NATS Server** - Install and configure NATS server (Sprint 6a complete)
2. ⏳ **Bot NATS Client** - Add NATS client to bot layer (`lib/bot.py`) (Sortie 4)
3. ✅ **Database NATS Service** - Convert database to NATS-subscribing service (`common/database_service.py`) (Sortie 3 COMPLETE)
4. ✅ **Subject Registry** - Subjects defined in DatabaseService docstrings (Sortie 3)
5. ⏳ **Connection Management** - Implement reconnection, health checks (Sortie 4-6)
6. ⏳ **Message Serialization** - JSON encoding/decoding with correlation IDs (Sortie 4-6)

**Testing**: NATS connectivity, pub/sub, request/reply patterns

**Deliverables**:
- NATS server running (local development)
- Bot can publish to NATS
- Database subscribes to NATS subjects
- Subject hierarchy documented

### Phase 1: Connection Layer Normalization
**Priority**: CRITICAL  
**Estimated Effort**: 4-6 hours  
**Blockers**: Phase 0 must be complete

1. ✅ **Audit Complete** - All locations identified and marked
2. ⏳ **Fix #4** - User List structure (CRITICAL - backwards structure)
3. ⏳ **Fix #2** - User Join user_data field (HIGH)
4. ⏳ **Fix #3** - User Leave consistency (MEDIUM)
5. ⏳ **Fix #5** - PM recipient field (MEDIUM)
6. ⏳ **Document #1** - Message event (LOW)

**Testing**: Write unit tests for each normalized event type

### Phase 2: Remove Direct Database Calls (NATS Migration)
**Priority**: **CRITICAL** - Core architecture fix  
**Estimated Effort**: 6-8 hours  
**Blockers**: Phase 0 must be complete

1. ⏳ **Fix #11** - User join database call → NATS publish
2. ⏳ **Fix #12** - User leave database call → NATS publish
3. ⏳ **Fix #13** - Message logging database call → NATS publish
4. ⏳ **Fix #14** - User count logging database call → NATS publish
5. ⏳ **Fix #15** - Status update database call → NATS publish
6. ⏳ **Fix #16** - High water mark database call → NATS publish
7. ⏳ **Fix #17** - Outbound message query → NATS request/reply

**Testing**: 
- Verify all events flow through NATS
- Test request/reply pattern (#17)
- Confirm database updates via NATS subscription

**Critical Success Criteria**:
- ✅ Bot has NO direct `self.db.method()` calls
- ✅ All database updates flow through NATS
- ✅ Can run bot and database in separate processes

### Phase 3: Bot Handler Normalization
**Priority**: HIGH  
**Estimated Effort**: 2-3 hours  
**Blockers**: Phase 1 must be complete

1. ⏳ **Fix #6** - User List handler (depends on #4)
2. ⏳ **Fix #7** - User Join handler (depends on #2)
3. ⏳ **Fix #8** - User Leave handler (depends on #3)
4. ✅ **Document #9** - Message handler (already correct)

**Testing**: Integration tests for bot event handling

### Phase 4: Component Cleanup
**Priority**: MEDIUM  
**Estimated Effort**: 1-2 hours  
**Blockers**: Phase 1 must be complete

1. ⏳ **Fix #10** - Shell PM handler (depends on #5)
2. ⏳ **Audit** - Check other components for platform_data access
3. ⏳ **Audit** - Check for any remaining direct method calls between layers
4. ⏳ **Update** - Plugin documentation with NATS-first patterns

**Testing**: End-to-end tests with live connection

### Phase 5: Documentation & Architecture Validation
**Priority**: MEDIUM  
**Estimated Effort**: 3-4 hours  
**Blockers**: Phases 1-4 complete

1. ⏳ Update ARCHITECTURE.md with NATS communication flows
2. ⏳ Update plugin documentation (lib/plugin/base.py) with NATS examples
3. ⏳ Create migration examples for plugin developers
4. ⏳ Add NATS section to TESTING.md
5. ⏳ Update quickstart guides with NATS setup
6. ⏳ Document NATS subject hierarchy completely
7. ⏳ Create NATS troubleshooting guide

**Testing**: Documentation review, architecture validation

**Total Estimated Effort**: 22-31 hours (3-4 days)**

**CRITICAL NOTE**: This is now a **much larger effort** due to NATS infrastructure requirements. The original estimate of 10-14 hours was based on normalization only. Adding NATS-first architecture doubles the scope but is ESSENTIAL for proper layer isolation.

---

## Risk Assessment

### High Risk Items

1. **User List Structure (#4)** - Backwards structure could break existing plugins
   - **Mitigation**: Comprehensive tests, gradual rollout
   - **Impact**: High - affects all user list operations

2. **Breaking Changes** - Handlers expect different structure
   - **Mitigation**: Update all handlers atomically, thorough testing
   - **Impact**: Medium - contained to bot codebase

### Medium Risk Items

3. **Missing Fields** - Components may rely on fields we remove
   - **Mitigation**: Audit all data.get() calls, add fallbacks
   - **Impact**: Low-Medium - most access is in known handlers

4. **Plugin Compatibility** - Plugins accessing platform_data
   - **Mitigation**: Plugin system is new (Sprint 8), no existing plugins yet
   - **Impact**: Low - no plugins in production

### Low Risk Items

5. **Documentation Drift** - Docs may contradict implementation
   - **Mitigation**: Update docs as part of implementation
   - **Impact**: Low - affects developer experience only

---

## Success Criteria

### Definition of Done

- [ ] All 10 TODO items addressed (fixed or documented)
- [ ] Connection layer passes unit tests for all event types
- [ ] Bot handlers use only normalized fields (no platform_data access)
- [ ] Shell component uses only normalized fields
- [ ] Bot connects and operates correctly on live CyTube channel
- [ ] PM commands work without platform_data access
- [ ] User list updates work correctly
- [ ] All tests pass (unit + integration)
- [ ] NORMALIZATION_SPEC.md updated to "implemented" status
- [ ] Architecture documentation updated

### Verification Steps

1. **Unit Test**: Each event type normalization
2. **Integration Test**: Event handlers with normalized events
3. **Live Test**: Connect to CyTube channel AKWHR89327M
4. **Command Test**: Send PM commands, verify responses
5. **User Test**: Users join/leave, verify userlist updates
6. **Grep Test**: No platform_data access in core components

```powershell
# Verify no platform_data in core (except connection layer)
grep -r "platform_data" lib/bot.py common/shell.py
# Should return: no matches (or only comments)
```

---

## Related Sprint Planning

### Recommended Sprint Structure

This work fits naturally into a dedicated nano-sprint:

**Sprint Name**: "9-normalize" or "9-platform-agnostic"  
**Duration**: 1-2 days  
**Sorties**: 3-4 (Foundation, Handlers, Components, Documentation)

### Sortie Breakdown

1. **Sortie 1: Connection Layer Foundation**
   - Fix user_list, user_join, user_leave, pm normalizations
   - Unit tests for each event type
   - ~4-6 hours

2. **Sortie 2: Bot Handler Updates**
   - Update all bot event handlers
   - Remove platform_data access
   - Integration tests
   - ~2-3 hours

3. **Sortie 3: Component Cleanup**
   - Fix Shell PM handler
   - Audit other components
   - End-to-end tests
   - ~1-2 hours

4. **Sortie 4: Documentation & Polish**
   - Update ARCHITECTURE.md
   - Update plugin documentation
   - Update NORMALIZATION_SPEC.md
   - Migration examples
   - ~2-3 hours

---

## Historical Context

### How We Got Here

1. **Sprint 2 (LLM Integration)**: Initial event normalization added
2. **Sprint 6a (NATS Event Bus)**: Normalization layer expanded for pub/sub
3. **Sprint 8 (Plugin System)**: Multi-platform architecture planned
4. **Sprint 8 Retrospective**: Identified normalization as technical debt
5. **Production Deployment**: Discovered event structure bugs during live testing
6. **This Audit**: Comprehensive review revealed 10 improvement points

### Key Learning

**"We started normalization early but didn't complete it consistently."**

The message event normalization was done well (#9 - bot message handler is correct). However, user events (join, leave, list) were only partially normalized, leaving handlers dependent on platform_data. This technical debt accumulated until discovered during production deployment.

### Lessons for Future

1. **Complete the Layer**: Don't half-implement architectural patterns
2. **Test Live Early**: Bugs appeared only during real-world connection
3. **Document the Pattern**: Having NORMALIZATION_SPEC.md from the start would have prevented inconsistency
4. **Audit Regularly**: Regular audits catch drift before it becomes debt

---

## Appendix: Quick Reference

### File Locations

| File | TODO Count | Priority | Status |
|------|-----------|----------|---------|
| `lib/bot.py` | 11 (4 normalization + 7 NATS) | **CRITICAL** | NATS migration needed |
| `lib/connection/cytube.py` | 5 | CRITICAL | Foundation |
| `common/shell.py` | 1 | MEDIUM | Depends on above |
| **TOTAL** | **17** | **CRITICAL** | **Audit Complete** |

### Issue Categories

| Category | Count | Examples |
|----------|-------|----------|
| Event Normalization | 10 | user_list structure, user_data fields, recipient field |
| Direct Database Calls | 7 | user_joined(), user_left(), log_user_count() |
| **Total Issues** | **17** | All must be fixed for proper architecture |

### Dependency Graph

```
[Connection Layer]
    ├─ #4 user_list (CRITICAL) ──┬─> #6 bot user_list handler
    ├─ #2 user_join (HIGH) ──────┴─> #7 bot user_join handler
    ├─ #3 user_leave (MEDIUM) ──────> #8 bot user_leave handler
    ├─ #5 pm (MEDIUM) ───────────────> #10 shell PM handler
    └─ #1 message (LOW) ─────────────> #9 bot message handler (✅ done)

[Documentation]
    └─ NORMALIZATION_SPEC.md
```

### Command Shortcuts

```powershell
# Find all TODO markers
grep -r "TODO: NORMALIZATION" --include="*.py"

# Check for platform_data access (audit)
grep -r "platform_data" lib/bot.py common/shell.py

# Run normalization tests
pytest tests/unit/test_connection_adapter.py -v
pytest tests/integration/test_bot.py -v -k "user_list or user_join or user_leave"

# Connect to live channel (test)
.\.venv\Scripts\python.exe -m bot.rosey.rosey
```

---

## Next Steps

1. **Review This Audit** - Team reviews findings and priorities
2. **Create Sprint 9** - Set up nano-sprint in `docs/sprints/active/9-normalize/`
3. **Write PRD** - Product requirements for normalization completion
4. **Write Specs** - Technical specs for each sortie
5. **Implement** - Execute with agent assistance following AGENTS.md workflow
6. **Test** - Comprehensive testing at each phase
7. **Document** - Update all related documentation
8. **Deploy** - Test in production environment
9. **Close** - Mark all TODOs resolved, update this document

---

**Audit Status**: ✅ Complete  
**Implementation Status**: ⏳ Pending  
**Next Action**: Create Sprint 9 PRD and specs  
**Document Owner**: Rosey-Robot Team  
**Last Updated**: January 2025

