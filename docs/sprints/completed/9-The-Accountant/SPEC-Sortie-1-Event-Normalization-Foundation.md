# Technical Specification: Event Normalization Foundation

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 1 of 6  
**Status**: Ready for Implementation  
**Estimated Effort**: 4-6 hours  
**Dependencies**: None (Foundation)  
**Blocking**: All other sorties in Sprint 9  

---

## Overview

**Purpose**: Fix the connection layer event normalization to establish correct, platform-agnostic event structures for all event types. This is the **foundation sortie** - all other Sprint 9 work depends on these structures being correct.

**Scope**: Fix 5 critical normalization issues in `lib/connection/cytube.py` identified in NORMALIZATION_TODO.md (#1-#5).

**Non-Goals**: 
- Bot handler changes (Sortie 2)
- NATS migration (Sortie 3-4)
- Configuration changes (Sortie 5)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: All events MUST have platform-agnostic top-level fields  
**FR-002**: All events MUST include original platform data in `platform_data` wrapper  
**FR-003**: `user_list` events MUST have `users` array with full normalized user objects  
**FR-004**: `user_join` events MUST have both `user` (string) and `user_data` (object) fields  
**FR-005**: `pm` events MUST have `recipient` field for bi-directional messaging  
**FR-006**: All events MUST have `timestamp` field (Unix timestamp, seconds)  

### 1.2 Non-Functional Requirements

**NFR-001**: Zero performance degradation (normalization is additive, not transformative)  
**NFR-002**: Backward compatibility maintained (existing handlers continue working)  
**NFR-003**: All changes covered by unit tests  

---

## 2. Detailed Design

### 2.1 Event Structure Standards

**Canonical Normalized Event Structure**:

```python
{
    # Platform-Agnostic Fields (REQUIRED - handlers use these)
    'user': str,              # Username (sender for messages, subject for user events)
    'content': str,           # Message content (for message events)
    'timestamp': int,         # Unix timestamp in seconds
    
    # Event-Specific Normalized Fields
    'user_data': Dict,        # Full user object (for user_join, user_list)
    'users': List[Dict],      # User list (for user_list events)
    'recipient': str,         # Recipient username (for PM events)
    
    # Platform-Specific Data (ALWAYS present)
    'platform_data': Dict,    # Original platform event data
}
```

**Field Requirements by Event Type**:

| Event Type | Required Fields | Optional Fields |
|------------|----------------|-----------------|
| `message` | user, content, timestamp, platform_data | user_data |
| `user_join` | user, user_data, timestamp, platform_data | - |
| `user_leave` | user, timestamp, platform_data | user_data (if available) |
| `user_list` | users (array of objects), timestamp, platform_data | - |
| `pm` | user, recipient, content, timestamp, platform_data | - |

### 2.2 Implementation Changes

#### Change 1: User Join Event (`user_join`)

**File**: `lib/connection/cytube.py`  
**Line**: ~491  
**Issue**: Missing `user_data` field (NORMALIZATION_TODO.md #2)  

**Current Code**:
```python
normalized = {
    'user': data.get('name', ''),
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Required Change**:
```python
normalized = {
    'user': data.get('name', ''),
    'user_data': {
        'username': data.get('name', ''),
        'rank': data.get('rank', 0),
        'is_afk': data.get('afk', False),
        'is_moderator': data.get('rank', 0) >= 2,
        'meta': data.get('meta', {})
    },
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Rationale**: Handlers need full user data without accessing `platform_data`. This enables platform-agnostic user handling.

---

#### Change 2: User Leave Event (`user_leave`)

**File**: `lib/connection/cytube.py`  
**Line**: ~505  
**Issue**: Missing `user_data` field when available (NORMALIZATION_TODO.md #3)  

**Current Code**:
```python
normalized = {
    'user': data.get('name', ''),
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Required Change**:
```python
# For user_leave, we may have full user data or just username
user_data = None
if 'rank' in data or 'afk' in data:
    # Full user data available
    user_data = {
        'username': data.get('name', ''),
        'rank': data.get('rank', 0),
        'is_afk': data.get('afk', False),
        'is_moderator': data.get('rank', 0) >= 2,
        'meta': data.get('meta', {})
    }

normalized = {
    'user': data.get('name', ''),
    'timestamp': int(time.time()),
    'platform_data': data
}

# Only add user_data if available
if user_data:
    normalized['user_data'] = user_data
```

**Rationale**: User leave events may or may not have full user data depending on platform. Include it when available.

---

#### Change 3: User List Event (`user_list`) - BACKWARDS!

**File**: `lib/connection/cytube.py`  
**Line**: ~517  
**Issue**: `users` field contains strings instead of normalized user objects (NORMALIZATION_TODO.md #4)  
**Severity**: HIGH - This breaks platform-agnostic user list handling  

**Current Code** (WRONG):
```python
normalized = {
    'users': [user.get('name', '') for user in data],  # ❌ Just usernames!
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Required Change** (CORRECT):
```python
normalized = {
    'users': [
        {
            'username': user.get('name', ''),
            'rank': user.get('rank', 0),
            'is_afk': user.get('afk', False),
            'is_moderator': user.get('rank', 0) >= 2,
            'meta': user.get('meta', {})
        }
        for user in data
    ],
    'timestamp': int(time.time()),
    'platform_data': data
}
```

**Rationale**: This is the MOST CRITICAL fix. Current implementation is backwards - handlers that iterate `data['users']` expect objects but get strings. This breaks platform-agnostic user tracking.

**Breaking Change Impact**: 
- Handlers currently doing `for username in data['users']` will break
- Must update to `for user in data['users']: username = user['username']`
- This is intentional - the current structure is wrong

---

#### Change 4: Private Message Event (`pm`)

**File**: `lib/connection/cytube.py`  
**Line**: ~533  
**Issue**: Missing `recipient` field for bi-directional PM support (NORMALIZATION_TODO.md #5)  

**Current Code**:
```python
normalized = {
    'user': data.get('username', ''),
    'content': data.get('msg', ''),
    'timestamp': int(data.get('time', 0) / 1000),
    'platform_data': data
}
```

**Required Change**:
```python
normalized = {
    'user': data.get('username', ''),
    'recipient': self.channel.username,  # Bot is the recipient
    'content': data.get('msg', ''),
    'timestamp': int(data.get('time', 0) / 1000),
    'platform_data': data
}
```

**Rationale**: For multi-platform support, we need to know both sender AND recipient. CyTube only sends PMs TO the bot, so recipient is always the bot's username.

---

#### Change 5: Message Event (Documentation Only)

**File**: `lib/connection/cytube.py`  
**Line**: ~479  
**Issue**: Needs documentation and validation (NORMALIZATION_TODO.md #1)  
**Status**: ✅ Already correct, needs tests  

**Current Code** (CORRECT):
```python
normalized = {
    'user': data.get('username', ''),
    'content': data.get('msg', ''),
    'timestamp': int(data.get('time', 0) / 1000),
    'platform_data': data
}
```

**Required Changes**:
- Add docstring explaining normalization structure
- Add unit test verifying all required fields present

---

### 2.3 Normalization Helper Functions

**Create Reusable Helpers** (avoid duplication):

**File**: `lib/connection/cytube.py` (add at class level)

```python
def _normalize_cytube_user(self, user_data: Dict) -> Dict:
    """Normalize CyTube user object to platform-agnostic structure.
    
    Args:
        user_data: Raw CyTube user object
        
    Returns:
        Normalized user dictionary with standard fields
    """
    return {
        'username': user_data.get('name', ''),
        'rank': user_data.get('rank', 0),
        'is_afk': user_data.get('afk', False),
        'is_moderator': user_data.get('rank', 0) >= 2,
        'meta': user_data.get('meta', {})
    }
```

**Usage in Changes**:
```python
# Change 1 (user_join)
normalized = {
    'user': data.get('name', ''),
    'user_data': self._normalize_cytube_user(data),
    'timestamp': int(time.time()),
    'platform_data': data
}

# Change 3 (user_list)
normalized = {
    'users': [self._normalize_cytube_user(user) for user in data],
    'timestamp': int(time.time()),
    'platform_data': data
}
```

---

## 3. Implementation Plan

### Phase 1: Add Helper Function (30 minutes)

1. Add `_normalize_cytube_user()` helper method
2. Add docstring with field documentation
3. Add inline comments explaining each field

### Phase 2: Fix User Join Event (30 minutes)

1. Update `user_join` normalization to use helper
2. Verify `user_data` field structure
3. Add inline TODO comments for bot handler updates (Sortie 2)

### Phase 3: Fix User Leave Event (30 minutes)

1. Add conditional `user_data` inclusion
2. Handle case where only username available
3. Document conditional behavior

### Phase 4: Fix User List Event (1 hour) - CRITICAL

1. Update `users` array to use helper for each user
2. **Add migration notes** - this BREAKS existing handlers
3. Add comment marking as BREAKING CHANGE
4. Verify structure matches specification

### Phase 5: Fix PM Event (30 minutes)

1. Add `recipient` field (bot's username)
2. Document recipient determination logic
3. Add note about multi-platform recipient handling

### Phase 6: Testing (1.5 hours)

1. Create `tests/unit/test_event_normalization.py`
2. Test each event type's structure
3. Verify all required fields present
4. Verify helper function correctness
5. Add test for backward compatibility (existing handlers still work for now)

### Phase 7: Documentation (30 minutes)

1. Update NORMALIZATION_SPEC.md with final structures
2. Add examples for each event type
3. Document breaking change in CHANGELOG.md (draft)
4. Update NORMALIZATION_TODO.md status (#1-#5 marked complete)

---

## 4. Testing Strategy

### 4.1 Unit Tests

**New Test File**: `tests/unit/test_event_normalization.py`

```python
import pytest
from lib.connection.cytube import CyTubeConnection

class TestEventNormalization:
    """Test suite for event normalization layer."""
    
    def test_message_event_structure(self):
        """Verify message events have required fields."""
        # Mock connection and emit
        conn = CyTubeConnection(...)
        
        # Simulate CyTube message event
        raw_data = {
            'username': 'alice',
            'msg': 'Hello world',
            'time': 1700000000000
        }
        
        # Trigger normalization
        conn._on_chat_message('chatMsg', raw_data)
        
        # Verify normalized structure
        normalized = conn.last_normalized_event  # Need to capture this
        assert 'user' in normalized
        assert 'content' in normalized
        assert 'timestamp' in normalized
        assert 'platform_data' in normalized
        assert normalized['user'] == 'alice'
        assert normalized['content'] == 'Hello world'
        assert isinstance(normalized['timestamp'], int)
    
    def test_user_join_has_user_data(self):
        """Verify user_join events include user_data field."""
        # ... similar structure
        assert 'user_data' in normalized
        assert normalized['user_data']['username'] == 'alice'
        assert 'rank' in normalized['user_data']
        assert 'is_moderator' in normalized['user_data']
    
    def test_user_list_has_user_objects(self):
        """Verify user_list events contain array of user objects."""
        raw_data = [
            {'name': 'alice', 'rank': 2, 'afk': False},
            {'name': 'bob', 'rank': 0, 'afk': True}
        ]
        
        # Normalize
        normalized = conn._normalize_user_list(raw_data)
        
        # Verify structure
        assert 'users' in normalized
        assert len(normalized['users']) == 2
        
        # Verify each user is an object, not a string
        for user in normalized['users']:
            assert isinstance(user, dict)
            assert 'username' in user
            assert 'rank' in user
            assert 'is_moderator' in user
    
    def test_pm_has_recipient(self):
        """Verify PM events include recipient field."""
        # ... verify 'recipient' field present
```

### 4.2 Integration Tests

**Existing Tests**: Verify no regressions

```bash
# Run existing test suite - should still pass
pytest tests/ -v

# Expected: 146 tests pass (Sprint 8 baseline)
# Acceptable: Minor failures in tests that directly check event structure
```

### 4.3 Manual Testing

**Test Procedure**:

1. Start bot in test environment
2. Join channel, verify user_join event structure
3. Leave channel, verify user_leave event structure
4. Send message, verify message event structure
5. Check userlist, verify user_list structure
6. Send PM to bot, verify pm event structure

**Verification**: Check logs for normalized event structures

---

## 5. Acceptance Criteria

**Definition of Done**:

- [ ] Helper function `_normalize_cytube_user()` implemented
- [ ] User join events include `user_data` field with full normalized user object
- [ ] User leave events include `user_data` when available
- [ ] User list events have `users` array with full user objects (not strings) ⚠️ BREAKING
- [ ] PM events include `recipient` field
- [ ] Message events documented and verified (no changes needed)
- [ ] Unit tests created for all event types
- [ ] Unit tests verify all required fields present
- [ ] All existing tests still pass (or failures documented as expected)
- [ ] NORMALIZATION_SPEC.md updated with final event structures
- [ ] NORMALIZATION_TODO.md items #1-#5 marked complete
- [ ] CHANGELOG.md updated with breaking change notice (draft)
- [ ] Code comments mark breaking changes clearly

---

## 6. Migration Notes

### 6.1 Breaking Changes

**User List Structure Change**:

**Before** (Current - WRONG):
```python
data['users']  # => ['alice', 'bob', 'charlie']  # Strings!
```

**After** (New - CORRECT):
```python
data['users']  # => [
                #      {'username': 'alice', 'rank': 2, ...},
                #      {'username': 'bob', 'rank': 0, ...}
                #    ]  # Full objects!
```

**Impact**: Any code iterating `data['users']` expecting strings will break

**Fix Required in Sortie 2**: Update bot handlers to handle user objects

### 6.2 Backward Compatibility

**Maintained**:
- Event names unchanged
- `platform_data` still present (existing handlers can still access)
- Event order unchanged
- Timing unchanged

**Not Maintained**:
- `user_list` structure intentionally broken (was backwards)
- Handlers must update to use new structure (Sortie 2)

---

## 7. Risks and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing handlers | HIGH | HIGH | Sortie 2 immediately follows to fix handlers |
| Performance degradation | LOW | MEDIUM | Benchmark before/after, accept <5% overhead |
| Missing edge cases | MEDIUM | LOW | Comprehensive unit tests, manual testing |
| Documentation drift | MEDIUM | MEDIUM | Update NORMALIZATION_SPEC.md as part of DoD |

---

## 8. Dependencies and Blockers

**Dependencies**: None (this is the foundation)

**Blocks**: 
- Sortie 2 (Bot Handler Migration) - depends on these structures
- Sortie 3 (Database Service) - depends on event structures
- Sortie 4 (Bot NATS Migration) - depends on event structures

**Critical Path**: This sortie MUST complete before any other Sprint 9 work

---

## 9. Rollback Plan

**If Sortie 1 Fails**:

1. Revert changes to `lib/connection/cytube.py`
2. Defer Sprint 9 until issues resolved
3. Document failure reasons
4. Reassess scope and approach

**Rollback Trigger**: 
- Unit tests fail
- Performance degradation >5%
- Existing tests regress unexpectedly

---

## 10. Next Steps

**After Completion**:

1. Mark Sortie 1 complete in Sprint 9 tracking
2. Begin Sortie 2: Bot Handler Migration (fix handlers to use new structures)
3. Update NORMALIZATION_TODO.md with Sortie 1 completion status
4. Create PR for review (or continue with Sortie 2 immediately)

---

**Sortie Status**: Ready for Implementation  
**Priority**: CRITICAL (Foundation)  
**Estimated Effort**: 4-6 hours  
**Success Metric**: All events have correct platform-agnostic structure with full test coverage
