# Event Normalization Audit - TODO Summary

**Date**: January 2025  
**Status**: Sprint 9 Sortie 1 Complete ✅  
**Priority**: HIGH (Technical Debt - Blocks Multi-Platform Support)

**Last Updated**: January 2025 - Sortie 1 Implementation Complete

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

**Remaining** (12 items):
- ⏳ Bot layer event handlers (6 items) - Sortie 2
- ⏳ Database service layer (5 items) - Sortie 3
- ⏳ NATS integration (1 item) - Sortie 4

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

#### 6. Bot User List Handler
**File**: `lib/bot.py`  
**Line**: 266  
**Severity**: HIGH (depends on #4)  
**Status**: ⚠️ Workaround in place - uses `platform_data`

```python
# TODO: NORMALIZATION - Should use normalized 'users' array with full user objects
# Currently accessing platform_data because connection layer puts objects there
# Once connection layer fixed, use: users_data = data.get('users', [])
```

**Current Code** (Workaround):
```python
users_data = data.get('platform_data', [])  # Using platform_data
for user in users_data:
    self._add_user(user)
```

**After #4 Fixed** (Correct):
```python
users_data = data.get('users', [])  # Use normalized field
for user in users_data:
    self._add_user(user)
```

**Dependencies**: Blocked by #4 (User List Event Normalization)

---

#### 7. Bot User Join Handler
**File**: `lib/bot.py`  
**Line**: 278  
**Severity**: HIGH (depends on #2)  
**Status**: ⚠️ Workaround in place - uses `platform_data`

```python
# TODO: NORMALIZATION - Should have 'user_data' at top level with full user object
# Currently must access platform_data due to incomplete normalization
# Target: user_data = data.get('user_data', {})
```

**Current Code** (Workaround):
```python
user_data = data.get('platform_data', data)  # Fallback to platform_data
self._add_user(user_data)
```

**After #2 Fixed** (Correct):
```python
user_data = data.get('user_data', {})  # Use normalized field
self._add_user(user_data)
```

**Dependencies**: Blocked by #2 (User Join Event Normalization)

---

#### 8. Bot User Leave Handler
**File**: `lib/bot.py`  
**Line**: 298  
**Severity**: MEDIUM (depends on #3)  
**Status**: ⚠️ Has fallback to 'name' field

```python
# TODO: NORMALIZATION - Should only use 'user' field once connection layer fixed
# Remove fallback to 'name' after normalization complete
```

**Current Code** (Workaround):
```python
user = data.get('user', data.get('name', ''))  # Fallback to 'name'
```

**After #3 Fixed** (Correct):
```python
user = data.get('user', '')  # Only normalized field
```

**Dependencies**: Blocked by #3 (User Leave Event Normalization)

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

#### 11. Bot User Join Database Call
**File**: `lib/bot.py`  
**Line**: 287-290  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    username = data.get('user', user_data.get('name'))
    if username:
        self.db.user_joined(username)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS - database layer subscribes
if self.nats:
    await self.nats.publish('rosey.db.user.joined', {
        'username': data.get('user', ''),
        'user_data': data.get('user_data', {}),
        'timestamp': data.get('timestamp', int(time.time()))
    })
```

**Impact**: 
- Bot and database are tightly coupled
- Cannot run in separate processes
- Cannot horizontally scale
- Plugins cannot observe user join events

---

#### 12. Bot User Leave Database Call
**File**: `lib/bot.py`  
**Line**: 303-305  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    self.db.user_left(user)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS
if self.nats:
    await self.nats.publish('rosey.db.user.left', {
        'username': user,
        'timestamp': int(time.time())
    })
```

---

#### 13. Bot Message Logging Database Call
**File**: `lib/bot.py`  
**Line**: 407-408  
**Severity**: **CRITICAL** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    self.db.user_chat_message(username, msg)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS
if self.nats:
    await self.nats.publish('rosey.db.message.log', {
        'username': username,
        'content': msg,
        'timestamp': data.get('timestamp', int(time.time()))
    })
```

---

#### 14. Bot User Count Logging Database Call
**File**: `lib/bot.py`  
**Line**: 423-424  
**Severity**: **HIGH** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    self.db.log_user_count(chat_users, connected_users)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS
if self.nats:
    await self.nats.publish('rosey.db.stats.user_count', {
        'chat_users': chat_users,
        'connected_users': connected_users,
        'timestamp': int(time.time())
    })
```

---

#### 15. Bot Status Update Database Call
**File**: `lib/bot.py`  
**Line**: 468-469  
**Severity**: **HIGH** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    self.db.update_current_status(**status)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS
if self.nats:
    await self.nats.publish('rosey.db.status.update', status)
```

---

#### 16. Bot High Water Mark Update Database Call
**File**: `lib/bot.py`  
**Line**: 237, 294  
**Severity**: **MEDIUM** (violates layer isolation)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    self.db.update_high_water_mark(user_count, connected_count)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT):
```python
# Publish to NATS
if self.nats:
    await self.nats.publish('rosey.db.stats.high_water', {
        'user_count': user_count,
        'connected_count': connected_count,
        'timestamp': int(time.time())
    })
```

**Note**: This call appears in multiple locations - all must be updated.

---

#### 17. Bot Outbound Message Query Database Call
**File**: `lib/bot.py`  
**Line**: 505  
**Severity**: **CRITICAL** (synchronous query - needs request/reply)  
**Status**: ❌ ANTI-PATTERN - Direct database call

```python
# CURRENT (WRONG):
if self.db:
    messages = self.db.get_unsent_outbound_messages(...)  # ❌ DIRECT DATABASE CALL
```

**Required Changes** (CORRECT - Request/Reply Pattern):
```python
# Request from NATS with reply
if self.nats:
    response = await self.nats.request('rosey.db.messages.outbound.get', {
        'username': username,
        'limit': 10
    }, timeout=2.0)
    
    if response:
        messages = json.loads(response.data)
```

**Note**: This is a **query** operation requiring response - use NATS request/reply pattern, not pub/sub.

---

## Implementation Roadmap

### Phase 0: NATS Infrastructure (NEW - Foundation for EVERYTHING)
**Priority**: **BLOCKING** - Must be done first  
**Estimated Effort**: 6-8 hours  
**Blockers**: None

1. ⏳ **Setup NATS Server** - Install and configure NATS server (local or containerized)
2. ⏳ **Bot NATS Client** - Add NATS client to bot layer (`lib/bot.py`)
3. ⏳ **Database NATS Service** - Convert database to NATS-subscribing service (`common/database.py`)
4. ⏳ **Subject Registry** - Define all NATS subjects (`lib/nats/subjects.py`)
5. ⏳ **Connection Management** - Implement reconnection, health checks
6. ⏳ **Message Serialization** - JSON encoding/decoding with correlation IDs

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

