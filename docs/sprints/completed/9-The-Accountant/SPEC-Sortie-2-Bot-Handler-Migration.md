# Technical Specification: Bot Handler Migration to Normalized Events

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 2 of 6  
**Status**: Ready for Implementation  
**Estimated Effort**: 3-4 hours  
**Dependencies**: Sortie 1 (Event Normalization Foundation) MUST be complete  
**Blocking**: Sortie 3-6  

---

## Overview

**Purpose**: Update bot layer event handlers to use ONLY normalized fields, removing all dependencies on `platform_data`. This makes handlers truly platform-agnostic and prepares for multi-platform support.

**Scope**: Fix 5 bot handlers in `lib/bot.py` identified in NORMALIZATION_TODO.md (#6-#10).

**Key Principle**: *"The normalization layer should always win where possible."* — Sprint 8 Retrospective

**Non-Goals**:
- NATS migration (Sortie 4)
- Database service changes (Sortie 3)
- Configuration changes (Sortie 5)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: All bot handlers MUST use normalized fields (`user`, `content`, `user_data`, `users`) instead of `platform_data`  
**FR-002**: Handlers MUST NOT access `platform_data` directly (unless absolutely necessary for CyTube-specific features)  
**FR-003**: `_on_user_list` MUST handle `users` array of objects (not strings)  
**FR-004**: `_on_user_join` MUST use `user_data` field (not `platform_data`)  
**FR-005**: All changes MUST maintain existing functionality (no behavior changes)  

### 1.2 Non-Functional Requirements

**NFR-001**: Zero functional changes (only data source changes)  
**NFR-002**: All existing tests continue to pass  
**NFR-003**: Code is more readable and platform-agnostic  

---

## 2. Handler Changes

### 2.1 Handler: `_on_user_list` (Priority: HIGH)

**File**: `lib/bot.py`  
**Line**: ~347  
**Issue**: Accesses `platform_data` instead of normalized `users` array (NORMALIZATION_TODO.md #6)  
**Severity**: HIGH - Breaks after Sortie 1 changes  

**Current Code** (BREAKS with Sortie 1):
```python
def _on_user_list(self, _, data):
    """Handle initial user list."""
    # Get platform-specific user data
    users = data.get('platform_data', [])  # ❌ WRONG - should use 'users'
    
    # Update channel userlist
    self.channel.userlist.clear()
    for user in users:
        if isinstance(user, dict):
            username = user.get('name', '')
            # ... more processing
```

**Required Change**:
```python
def _on_user_list(self, _, data):
    """Handle initial user list.
    
    Uses normalized 'users' field which contains array of user objects
    with platform-agnostic structure (username, rank, is_moderator, etc).
    """
    # ✅ CORRECT - Use normalized 'users' array
    users = data.get('users', [])
    
    # Update channel userlist
    self.channel.userlist.clear()
    for user in users:
        # user is now guaranteed to be a dict with normalized fields
        username = user.get('username', '')  # Changed from 'name'
        rank = user.get('rank', 0)
        is_afk = user.get('is_afk', False)
        is_moderator = user.get('is_moderator', False)
        
        if username:
            self.channel.userlist.add(username)
            
            # Update username corrections if user is moderator
            if is_moderator:
                # Check for display name vs actual username
                self._check_username_correction(username, user)
            
            # Log AFK status if changed
            if is_afk and username not in self.afk_users:
                self.logger.debug(f"User {username} is AFK")
                self.afk_users.add(username)
    
    self.logger.info(f"User list updated: {len(self.channel.userlist)} users")
```

**Key Changes**:
- `data.get('platform_data', [])` → `data.get('users', [])`
- `user.get('name', '')` → `user.get('username', '')`
- Use normalized fields directly: `rank`, `is_afk`, `is_moderator`

**Rationale**: After Sortie 1, `users` contains full normalized objects. Using these makes handler platform-agnostic.

---

### 2.2 Handler: `_on_user_join` (Priority: HIGH)

**File**: `lib/bot.py`  
**Line**: ~385  
**Issue**: Accesses `platform_data` instead of normalized `user_data` (NORMALIZATION_TODO.md #7)  

**Current Code**:
```python
def _on_user_join(self, _, data):
    """Handle user joining channel."""
    username = data.get('user', '')
    
    # ❌ WRONG - Digs into platform_data
    user_data = data.get('platform_data', {})
    rank = user_data.get('rank', 0)
    is_afk = user_data.get('afk', False)
```

**Required Change**:
```python
def _on_user_join(self, _, data):
    """Handle user joining channel.
    
    Uses normalized 'user_data' field which contains full user object
    with platform-agnostic structure.
    """
    username = data.get('user', '')
    
    # ✅ CORRECT - Use normalized 'user_data' field
    user_data = data.get('user_data', {})
    rank = user_data.get('rank', 0)
    is_afk = user_data.get('is_afk', False)  # Changed from 'afk'
    is_moderator = user_data.get('is_moderator', False)
    
    # Add to userlist
    if username:
        self.channel.userlist.add(username)
        
        # Check for username corrections (moderators only)
        if is_moderator:
            self._check_username_correction(username, user_data)
        
        # Track AFK status
        if is_afk:
            self.afk_users.add(username)
        
        self.logger.info(f"User joined: {username} (rank={rank}, mod={is_moderator})")
```

**Key Changes**:
- `data.get('platform_data', {})` → `data.get('user_data', {})`
- `user_data.get('afk', False)` → `user_data.get('is_afk', False)`
- Added explicit `is_moderator` handling

**Rationale**: Sortie 1 adds `user_data` field with normalized user object. This makes join handling platform-agnostic.

---

### 2.3 Handler: `_on_user_leave` (Priority: MEDIUM)

**File**: `lib/bot.py`  
**Line**: ~415  
**Issue**: Could use `user_data` when available (NORMALIZATION_TODO.md #8)  

**Current Code**:
```python
def _on_user_leave(self, _, data):
    """Handle user leaving channel."""
    username = data.get('user', '')
    
    # Currently only uses username
    if username and username in self.channel.userlist:
        self.channel.userlist.remove(username)
        self.afk_users.discard(username)
        self.logger.info(f"User left: {username}")
```

**Required Change**:
```python
def _on_user_leave(self, _, data):
    """Handle user leaving channel.
    
    Optionally uses 'user_data' field if available for enhanced logging.
    """
    username = data.get('user', '')
    user_data = data.get('user_data', None)  # May be None
    
    if username and username in self.channel.userlist:
        self.channel.userlist.remove(username)
        self.afk_users.discard(username)
        
        # Enhanced logging if user_data available
        if user_data:
            rank = user_data.get('rank', 0)
            was_mod = user_data.get('is_moderator', False)
            log_msg = f"User left: {username} (rank={rank}, mod={was_mod})"
        else:
            log_msg = f"User left: {username}"
        
        self.logger.info(log_msg)
```

**Key Changes**:
- Check for optional `user_data` field
- Enhanced logging when available
- Graceful degradation if not present

**Rationale**: User leave events may not always have full user data. Use it when available for better logging.

---

### 2.4 Handler: `_check_llm_trigger` (Priority: LOW)

**File**: `lib/bot.py`  
**Line**: ~780  
**Issue**: Uses `platform_data` to check meta.afk (NORMALIZATION_TODO.md #9)  

**Current Code**:
```python
def _check_llm_trigger(self, username: str, message: str, data: Dict) -> bool:
    """Check if message triggers LLM response."""
    # ... trigger checks ...
    
    # Check if user is AFK - ❌ WRONG uses platform_data
    user_data = data.get('platform_data', {})
    is_afk = user_data.get('meta', {}).get('afk', False)
    
    if is_afk:
        return False
```

**Required Change**:
```python
def _check_llm_trigger(self, username: str, message: str, data: Dict) -> bool:
    """Check if message triggers LLM response.
    
    Uses normalized event structure to determine user AFK status.
    """
    # ... trigger checks ...
    
    # ✅ CORRECT - Check AFK via multiple sources
    # First check: normalized user_data (if present)
    user_data = data.get('user_data', {})
    is_afk = user_data.get('is_afk', False)
    
    # Second check: our tracked AFK users
    if not is_afk and username in self.afk_users:
        is_afk = True
    
    if is_afk:
        self.logger.debug(f"Skipping LLM trigger for AFK user: {username}")
        return False
```

**Key Changes**:
- `data.get('platform_data', {})` → `data.get('user_data', {})`
- `user_data.get('meta', {}).get('afk', False)` → `user_data.get('is_afk', False)`
- Added fallback check against `self.afk_users` set
- Added debug logging

**Rationale**: Message events may include `user_data` if available. Use normalized `is_afk` field.

---

### 2.5 Handler: `_on_set_user_profile` (Priority: LOW)

**File**: `lib/bot.py`  
**Line**: ~865  
**Issue**: Uses `platform_data.meta` for profile parsing (NORMALIZATION_TODO.md #10)  

**Current Code**:
```python
def _on_set_user_profile(self, _, data):
    """Handle user profile updates for username corrections."""
    # ❌ WRONG - Accesses platform_data.meta
    meta = data.get('platform_data', {}).get('meta', {})
    profile_text = meta.get('text', '')
    profile_image = meta.get('image', '')
```

**Required Change**:
```python
def _on_set_user_profile(self, _, data):
    """Handle user profile updates for username corrections.
    
    Profile updates are CyTube-specific and require platform_data access.
    This is acceptable as long as it's clearly marked.
    """
    # ⚠️ EXCEPTION - Profile meta is CyTube-specific feature
    # Accessing platform_data is acceptable here with clear comment
    user_data = data.get('user_data', {})
    meta = user_data.get('meta', {})
    
    # Fallback to platform_data if not in user_data
    if not meta:
        meta = data.get('platform_data', {}).get('meta', {})
    
    profile_text = meta.get('text', '')
    profile_image = meta.get('image', '')
    
    # ... rest of username correction logic ...
```

**Key Changes**:
- Try normalized `user_data.meta` first
- Fallback to `platform_data.meta` if needed
- Document this as CyTube-specific feature exception
- Mark with ⚠️ EXCEPTION comment

**Rationale**: Profile meta is CyTube-specific. We'll add it to normalized `user_data.meta`, but fallback to `platform_data` is acceptable for platform-specific features.

---

## 3. Additional Improvements

### 3.1 Username Correction Helper

**Current**: `_check_username_correction` may access `platform_data`

**Improvement**: Update to use normalized `user_data.meta`

```python
def _check_username_correction(self, username: str, user_data: Dict):
    """Check and store username corrections from user profile.
    
    Args:
        username: Current username
        user_data: Normalized user data dict (should include 'meta')
    """
    # Get profile meta from normalized user_data
    meta = user_data.get('meta', {})
    profile_text = meta.get('text', '')
    
    # ... rest of correction logic unchanged ...
```

### 3.2 AFK Tracking Consistency

**Issue**: AFK status tracked in multiple places inconsistently

**Improvement**: Centralize AFK status determination

```python
def _get_user_afk_status(self, username: str, user_data: Dict = None) -> bool:
    """Determine if user is AFK from multiple sources.
    
    Args:
        username: Username to check
        user_data: Optional normalized user data
        
    Returns:
        True if user is AFK
    """
    # Check normalized user_data first
    if user_data and user_data.get('is_afk', False):
        return True
    
    # Check our tracked AFK users
    if username in self.afk_users:
        return True
    
    return False
```

**Usage**:
```python
# In _check_llm_trigger
is_afk = self._get_user_afk_status(username, data.get('user_data'))
```

---

## 4. Implementation Plan

### Phase 1: Helper Functions (30 minutes)

1. Add `_get_user_afk_status()` helper
2. Update `_check_username_correction()` to use normalized fields
3. Add docstrings explaining normalized field usage

### Phase 2: Critical Handlers (1.5 hours)

1. **Update `_on_user_list`** (30 minutes)
   - Change to use `data['users']` array
   - Update field names (`name` → `username`, `afk` → `is_afk`)
   - Test thoroughly (most critical change)

2. **Update `_on_user_join`** (30 minutes)
   - Change to use `data['user_data']`
   - Update field names
   - Test username corrections still work

3. **Update `_on_user_leave`** (30 minutes)
   - Add optional `user_data` handling
   - Enhanced logging
   - Test leave tracking works

### Phase 3: Minor Handlers (1 hour)

1. **Update `_check_llm_trigger`** (30 minutes)
   - Use new AFK status helper
   - Test LLM triggering still works correctly

2. **Update `_on_set_user_profile`** (30 minutes)
   - Try normalized meta first, fallback to platform_data
   - Document exception clearly
   - Test username corrections from profiles

### Phase 4: Testing (1 hour)

1. Run full test suite
2. Manual testing for each handler
3. Verify no regressions
4. Test edge cases (missing fields, empty data)

---

## 5. Testing Strategy

### 5.1 Unit Tests

**Update Existing Tests**: Modify test fixtures to use new event structures

```python
# tests/unit/test_bot.py (update fixtures)

@pytest.fixture
def user_list_event():
    """User list event with normalized structure."""
    return {
        'users': [
            {
                'username': 'alice',
                'rank': 2,
                'is_afk': False,
                'is_moderator': True,
                'meta': {}
            },
            {
                'username': 'bob',
                'rank': 0,
                'is_afk': False,
                'is_moderator': False,
                'meta': {}
            }
        ],
        'timestamp': 1700000000,
        'platform_data': [...]  # Original data
    }

@pytest.fixture
def user_join_event():
    """User join event with normalized structure."""
    return {
        'user': 'alice',
        'user_data': {
            'username': 'alice',
            'rank': 2,
            'is_afk': False,
            'is_moderator': True,
            'meta': {'text': 'Alice (she/her)'}
        },
        'timestamp': 1700000000,
        'platform_data': {...}
    }
```

**New Tests**:

```python
def test_user_list_uses_normalized_users(bot, user_list_event):
    """Verify _on_user_list uses normalized 'users' array."""
    bot._on_user_list(None, user_list_event)
    
    # Verify userlist updated
    assert 'alice' in bot.channel.userlist
    assert 'bob' in bot.channel.userlist
    assert len(bot.channel.userlist) == 2

def test_user_join_uses_user_data(bot, user_join_event):
    """Verify _on_user_join uses normalized 'user_data'."""
    bot._on_user_join(None, user_join_event)
    
    assert 'alice' in bot.channel.userlist

def test_user_leave_handles_optional_user_data(bot):
    """Verify _on_user_leave works with or without user_data."""
    # Add user first
    bot.channel.userlist.add('alice')
    
    # Leave without user_data
    bot._on_user_leave(None, {'user': 'alice', 'timestamp': 1700000000})
    assert 'alice' not in bot.channel.userlist
    
    # Leave with user_data
    bot.channel.userlist.add('bob')
    bot._on_user_leave(None, {
        'user': 'bob',
        'user_data': {'username': 'bob', 'rank': 0},
        'timestamp': 1700000000
    })
    assert 'bob' not in bot.channel.userlist
```

### 5.2 Integration Tests

**Manual Test Checklist**:

1. [ ] Bot receives user list and updates correctly
2. [ ] User joins and is added to userlist
3. [ ] User leaves and is removed from userlist
4. [ ] LLM triggers work (not blocked by AFK check)
5. [ ] Username corrections work (profile parsing)
6. [ ] No crashes or errors in logs

---

## 6. Acceptance Criteria

**Definition of Done**:

- [ ] All 5 handlers updated to use normalized fields
- [ ] `_on_user_list` uses `data['users']` array of objects
- [ ] `_on_user_join` uses `data['user_data']` object
- [ ] `_on_user_leave` handles optional `user_data`
- [ ] `_check_llm_trigger` uses normalized AFK status
- [ ] `_on_set_user_profile` tries normalized meta first
- [ ] Helper functions added for code reuse
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual testing completed successfully
- [ ] Code comments explain normalized field usage
- [ ] NORMALIZATION_TODO.md items #6-#10 marked complete

---

## 7. Migration Notes

### 7.1 Breaking Changes

**None** - This sortie maintains backward compatibility because:
- Normalized fields are ADDED in Sortie 1
- `platform_data` still present (not removed)
- If normalized field missing, fallback works

### 7.2 Code Quality

**Improvements**:
- More readable (no nested `platform_data` access)
- More maintainable (consistent field names)
- More platform-agnostic (ready for Discord/Slack)

---

## 8. Dependencies

**Requires**:
- ✅ Sortie 1 (Event Normalization Foundation) - MUST be complete

**Blocks**:
- Sortie 3 (Database Service Layer)
- Sortie 4 (Bot NATS Migration)
- All subsequent sorties

**No Blockers** - Can proceed after Sortie 1

---

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Field name typos | LOW | HIGH | Comprehensive unit tests |
| Missing fallbacks | LOW | MEDIUM | Test with missing fields |
| AFK tracking breaks | LOW | MEDIUM | Dedicated AFK helper function |
| Username corrections break | LOW | HIGH | Test profile parsing explicitly |

---

## 10. Next Steps

**After Completion**:

1. Mark Sortie 2 complete
2. Begin Sortie 3: Database Service Layer
3. Update NORMALIZATION_TODO.md (#6-#10 complete)
4. Continue with NATS migration work

---

**Sortie Status**: Ready for Implementation  
**Priority**: HIGH (Critical Path)  
**Estimated Effort**: 3-4 hours  
**Success Metric**: All handlers use only normalized fields, zero regressions
