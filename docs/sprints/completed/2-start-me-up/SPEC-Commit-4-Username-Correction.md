# Technical Specification: Commit 4 - Username Correction

**Commit Title:** Username Correction  
**Feature:** Automatic Username Change Detection and Context Migration  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 4), US-011  
**Dependencies:** SPEC-Commit-1-LLM-Foundation.md  
**Target Release:** v2.1.0  

---

## 1. Overview

### 1.1 Purpose

Automatically track username changes in CyTube channels to ensure the bot addresses users correctly in LLM responses and maintains conversation context across username transitions.

### 1.2 Problem Statement

CyTube allows users to change their displayed username without disconnecting. When this happens:
- Bot's conversation context remains associated with old username
- Bot addresses user by old name in responses (confusing/incorrect)
- Rate limiting uses old username (user can bypass cooldown by changing name)

**Example Scenario:**
```
User joins as "Guest_123"
User: "hey rosey!"
Bot: "Hello Guest_123!"
User changes name to "Alice"
User: "what's the weather?"
Bot: "Hello Guest_123, ..."  // WRONG! Should be "Alice"
```

### 1.3 Scope

- Detect `setUserProfile` events from CyTube
- Extract old and new usernames from event data
- Update internal username mapping
- Migrate conversation context from old to new username
- Migrate rate limiting state
- Log username changes

### 1.4 Non-Goals

- Persist username mappings across bot restarts (future enhancement)
- Track username history (future enhancement)
- Handle multiple simultaneous username changes (edge case)
- Validate username changes (trust CyTube server)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: Event Detection**
- Bot shall listen for `setUserProfile` events from CyTube WebSocket
- Bot shall extract `name` (old username) from event data
- Bot shall extract `profile.name` (new username) from event data
- Bot shall ignore events with missing or malformed data

**FR-002: Username Mapping**
- Bot shall maintain mapping: `old_username -> new_username`
- Bot shall update mapping on each `setUserProfile` event
- Mapping shall be in-memory (resets on bot restart)
- Mapping shall support multiple changes: `User1 -> User2 -> User3`

**FR-003: Context Migration**
- Bot shall check if old username has conversation context
- Bot shall copy context from old username to new username
- Bot shall delete old username's context after migration
- Context structure shall remain unchanged (same message format)

**FR-004: Rate Limit Migration**
- Bot shall check if old username has rate limit state (last request timestamp)
- Bot shall copy rate limit state to new username
- Bot shall delete old username's rate limit state after migration
- New username inherits cooldown from old username

**FR-005: Logging**
- Bot shall log all username changes at INFO level
- Log shall include: old name, new name, context migrated (Y/N), rate limit migrated (Y/N)
- Bot shall log errors if migration fails

### 2.2 Non-Functional Requirements

**NFR-001: Performance**
- Username change handling shall complete in <10ms
- Context migration shall not block main event loop
- Memory usage shall remain constant (old context deleted)

**NFR-002: Reliability**
- Failures shall not crash bot
- Partial migration failures shall be logged
- Bot shall continue operating with or without username tracking

---

## 3. Design

### 3.1 CyTube Event Structure

**`setUserProfile` Event:**
```json
{
  "name": "User_123",  // Old username
  "profile": {
    "name": "Alice",   // New username
    "image": "...",
    "text": "..."
  }
}
```

**Note:** CyTube emits this event when:
- User clicks "Change Username"
- User updates profile via UI
- Server assigns username (e.g., "Guest_123" → "User")

### 3.2 Architecture

```
CyTube Server
    ↓ WebSocket
    ├─ Event: setUserProfile
    │  Data: {name: "User_123", profile: {name: "Alice"}}
    ↓
Bot._on_set_user_profile()
    ↓
    ├─ Extract old_name, new_name
    ├─ Check if old_name in llm_user_contexts
    │   ├─ YES: Copy context to new_name
    │   └─ Delete old_name context
    ├─ Check if old_name in llm_last_request
    │   ├─ YES: Copy timestamp to new_name
    │   └─ Delete old_name timestamp
    ├─ Log migration
    └─ Continue
```

### 3.3 Data Structures

**Before Username Change:**
```python
self.llm_user_contexts = {
    "User_123": [
        {"role": "user", "content": "hey rosey!"},
        {"role": "assistant", "content": "Hello!"}
    ]
}

self.llm_last_request = {
    "User_123": 1699632150.5
}
```

**After Username Change (User_123 → Alice):**
```python
self.llm_user_contexts = {
    "Alice": [  # Migrated from User_123
        {"role": "user", "content": "hey rosey!"},
        {"role": "assistant", "content": "Hello!"}
    ]
    # "User_123" deleted
}

self.llm_last_request = {
    "Alice": 1699632150.5  # Migrated from User_123
    # "User_123" deleted
}
```

---

## 4. Implementation

### 4.1 Modified Files

**`lib/bot.py`**

#### 4.1.1 Add Event Handler Registration

```python
class Bot:
    def __init__(self, ...):
        # ... existing code ...
        
        # Register event handlers
        self.on('setUserProfile', self._on_set_user_profile)
```

#### 4.1.2 Implement `_on_set_user_profile()` Handler

```python
async def _on_set_user_profile(self, event, data):
    """Handle username changes and migrate LLM context.
    
    CyTube emits 'setUserProfile' when users change their display name.
    This handler migrates conversation context and rate limit state from
    the old username to the new one.
    
    Args:
        event: Event name ('setUserProfile')
        data: Event data containing:
            - name: Old username
            - profile.name: New username
    """
    try:
        # Extract usernames
        old_name = data.get('name')
        new_name = data.get('profile', {}).get('name')
        
        # Validate data
        if not old_name or not new_name:
            self.logger.warning('setUserProfile missing names: %s', data)
            return
        
        if old_name == new_name:
            # No change (shouldn't happen, but handle gracefully)
            return
        
        # Track what was migrated
        context_migrated = False
        rate_limit_migrated = False
        
        # Migrate conversation context
        if old_name in self.llm_user_contexts:
            self.llm_user_contexts[new_name] = self.llm_user_contexts[old_name]
            del self.llm_user_contexts[old_name]
            context_migrated = True
        
        # Migrate rate limit state
        if old_name in self.llm_last_request:
            self.llm_last_request[new_name] = self.llm_last_request[old_name]
            del self.llm_last_request[old_name]
            rate_limit_migrated = True
        
        # Log migration
        self.logger.info(
            'Username changed: "%s" -> "%s" (context=%s, rate_limit=%s)',
            old_name, new_name, context_migrated, rate_limit_migrated
        )
        
    except Exception as e:
        self.logger.error('Error handling username change: %s', e, exc_info=True)
```

### 4.2 Alternative Implementation (with Mapping)

**If you want to track all username changes:**

```python
class Bot:
    def __init__(self, ...):
        # ... existing code ...
        self.username_mapping = {}  # old_name -> new_name

async def _on_set_user_profile(self, event, data):
    """Handle username changes with full mapping."""
    try:
        old_name = data.get('name')
        new_name = data.get('profile', {}).get('name')
        
        if not old_name or not new_name or old_name == new_name:
            return
        
        # Update mapping
        self.username_mapping[old_name] = new_name
        
        # Migrate data
        # ... same as above ...
        
    except Exception as e:
        self.logger.error('Error handling username change: %s', e, exc_info=True)

def _resolve_username(self, username):
    """Resolve username to current name (follow mapping chain)."""
    while username in self.username_mapping:
        username = self.username_mapping[username]
    return username
```

---

## 5. Testing

### 5.1 Unit Tests

**Test Basic Migration:**
```python
@pytest.mark.asyncio
async def test_username_change_basic():
    bot = Bot()
    
    # Set up initial context
    bot.llm_user_contexts["User_123"] = [
        {"role": "user", "content": "hello"}
    ]
    bot.llm_last_request["User_123"] = 1234567890.0
    
    # Simulate username change
    await bot._on_set_user_profile('setUserProfile', {
        'name': 'User_123',
        'profile': {'name': 'Alice'}
    })
    
    # Verify migration
    assert "Alice" in bot.llm_user_contexts
    assert "User_123" not in bot.llm_user_contexts
    assert bot.llm_user_contexts["Alice"][0]["content"] == "hello"
    
    assert "Alice" in bot.llm_last_request
    assert "User_123" not in bot.llm_last_request
    assert bot.llm_last_request["Alice"] == 1234567890.0
```

**Test No Context to Migrate:**
```python
@pytest.mark.asyncio
async def test_username_change_no_context():
    bot = Bot()
    
    # No existing context for User_123
    await bot._on_set_user_profile('setUserProfile', {
        'name': 'User_123',
        'profile': {'name': 'Alice'}
    })
    
    # Should not crash, just log
    assert "Alice" not in bot.llm_user_contexts
    assert "User_123" not in bot.llm_user_contexts
```

**Test Multiple Changes:**
```python
@pytest.mark.asyncio
async def test_username_change_chain():
    bot = Bot()
    
    # Initial context
    bot.llm_user_contexts["User_123"] = [{"role": "user", "content": "hi"}]
    
    # Change 1: User_123 -> Alice
    await bot._on_set_user_profile('setUserProfile', {
        'name': 'User_123',
        'profile': {'name': 'Alice'}
    })
    
    # Change 2: Alice -> AliceSmith
    await bot._on_set_user_profile('setUserProfile', {
        'name': 'Alice',
        'profile': {'name': 'AliceSmith'}
    })
    
    # Verify final state
    assert "AliceSmith" in bot.llm_user_contexts
    assert "Alice" not in bot.llm_user_contexts
    assert "User_123" not in bot.llm_user_contexts
```

**Test Malformed Event:**
```python
@pytest.mark.asyncio
async def test_username_change_malformed():
    bot = Bot()
    
    # Missing 'name'
    await bot._on_set_user_profile('setUserProfile', {
        'profile': {'name': 'Alice'}
    })
    # Should not crash
    
    # Missing 'profile.name'
    await bot._on_set_user_profile('setUserProfile', {
        'name': 'User_123'
    })
    # Should not crash
```

### 5.2 Integration Tests

**Manual Test Procedure:**

1. **Setup:**
   ```bash
   # Start bot with LLM enabled
   python -m lib bot/rosey/config.json
   
   # Enable DEBUG logging to see events
   # Set "log_level": "DEBUG" in config
   ```

2. **Test Scenario:**
   ```
   Step 1: Join CyTube channel as "Guest_123" (or similar guest name)
   Step 2: Send message: "hey rosey!"
   Step 3: Verify bot responds addressing "Guest_123"
   Step 4: Change username to "Alice" via CyTube UI
   Step 5: Send message: "what time is it?"
   Step 6: Verify bot responds addressing "Alice" (NOT "Guest_123")
   ```

3. **Verify Logs:**
   ```
   [INFO] LLM trigger: user=Guest_123, message="hey rosey!"
   [INFO] LLM response: user=Guest_123, length=50, time=1.2s
   [INFO] Username changed: "Guest_123" -> "Alice" (context=True, rate_limit=True)
   [INFO] LLM trigger: user=Alice, message="what time is it?"
   [INFO] LLM response: user=Alice, length=45, time=1.1s
   ```

4. **Test Rate Limiting:**
   ```
   Step 1: Send message as "Guest_123", bot responds
   Step 2: Wait 5 seconds (less than cooldown)
   Step 3: Change name to "Alice"
   Step 4: Send another message
   Step 5: Verify bot still enforces cooldown (should ignore message)
   Step 6: Wait for cooldown to expire
   Step 7: Send message again
   Step 8: Verify bot responds
   ```

### 5.3 Edge Cases

**Test Same Name:**
```python
await bot._on_set_user_profile('setUserProfile', {
    'name': 'Alice',
    'profile': {'name': 'Alice'}
})
# Should return early, no migration
```

**Test Rapid Changes:**
```python
# User changes name 10 times in 1 second
for i in range(10):
    await bot._on_set_user_profile('setUserProfile', {
        'name': f'User{i}',
        'profile': {'name': f'User{i+1}'}
    })
# Should handle gracefully
```

---

## 6. Acceptance Criteria

- [x] Bot registers `setUserProfile` event handler
- [x] Handler extracts old and new usernames correctly
- [x] Handler migrates conversation context from old to new username
- [x] Handler migrates rate limit state from old to new username
- [x] Handler deletes old username data after migration
- [x] Handler logs username changes at INFO level
- [x] Handler handles missing/malformed data gracefully
- [x] Handler does not crash on errors
- [x] Rate limiting works across username changes (cooldown preserved)
- [x] LLM responses address user by current (new) username

---

## 7. Deployment

### 7.1 Deployment Steps

1. Update `lib/bot.py` with `_on_set_user_profile()` handler
2. Register event handler in `__init__()`
3. Test locally in CyTube channel
4. Verify logs show username changes
5. Deploy to production
6. Monitor for migration issues

### 7.2 Rollback Plan

If username tracking causes issues:
1. Remove event handler registration: `# self.on('setUserProfile', ...)`
2. Restart bot
3. Bot will continue working, just won't track username changes

### 7.3 Monitoring

**Key Metrics:**
- Username changes per day
- Context migration success rate (%)
- Rate limit migration success rate (%)
- Errors in username change handler

**Log Queries:**
```bash
# Count username changes
journalctl -u cytube-bot --since today | grep "Username changed" | wc -l

# Find migration errors
journalctl -u cytube-bot --since today | grep "Error handling username change"

# See recent changes
journalctl -u cytube-bot -f | grep "Username changed"
```

---

## 8. Known Issues and Limitations

### 8.1 Current Limitations

**L-001: No Persistence**
- Username mappings reset on bot restart
- Context associated with old username is lost
- **Future Enhancement:** Store mappings in database

**L-002: No History Tracking**
- Only stores current username, not history
- Cannot query "what were User_123's previous names?"
- **Future Enhancement:** Add `username_history` table

**L-003: Race Conditions**
- If two users change names simultaneously, last one wins
- Unlikely in practice (different usernames)
- **Future Enhancement:** Use locks or queues

**L-004: Memory Leaks**
- If user changes name 1000 times, mapping grows
- Unlikely in practice (users don't change names that often)
- **Mitigation:** Clear mapping periodically (future)

### 8.2 Edge Cases

**Case 1: User A → User B, User C → User A**
```
Initial: User A, User B, User C
Change 1: User A → User B  // Overwrites User B's data!
Change 2: User C → User A
```

**Current Behavior:** User B's original data is lost when User A takes their name.

**Mitigation:** CyTube doesn't allow duplicate names, so this can't happen in practice.

**Case 2: Bot Restart During Conversation**
```
User changes name: Guest_123 → Alice
Bot restarts
User sends message
Bot responds addressing... what?
```

**Current Behavior:** Bot uses current username from CyTube event (Alice), not old name.

**Outcome:** Works correctly! CyTube always sends current username in events.

---

## 9. Documentation Updates

### 9.1 Code Documentation

```python
async def _on_set_user_profile(self, event, data):
    """Handle username changes and migrate LLM context.
    
    CyTube emits 'setUserProfile' when users change their display name.
    This handler migrates conversation context and rate limit state from
    the old username to the new one, ensuring the bot addresses users
    correctly and maintains cooldown periods across name changes.
    
    Args:
        event: Event name ('setUserProfile')
        data: Event data containing:
            - name (str): Old username
            - profile (dict):
                - name (str): New username
                
    Migration Process:
        1. Extract old and new usernames from event data
        2. Check if old username has conversation context
        3. If yes, copy context to new username and delete old
        4. Check if old username has rate limit state
        5. If yes, copy state to new username and delete old
        6. Log migration results
        
    Error Handling:
        - Missing or malformed data: Log warning, return early
        - Same old/new name: Return early (no migration needed)
        - Exception during migration: Log error, continue operation
        
    Examples:
        User joins as "Guest_123", chats with bot, then changes name to "Alice".
        After this handler runs:
        - llm_user_contexts["Alice"] contains previous conversation
        - llm_last_request["Alice"] preserves cooldown state
        - Old "Guest_123" data is deleted
    """
```

### 9.2 Architecture Documentation

Add to `ARCHITECTURE.md`:
```markdown
### Username Change Handling

The bot automatically tracks username changes to maintain conversation context:

**Event Flow:**
1. CyTube emits `setUserProfile` when user changes name
2. Bot extracts old/new usernames
3. Bot migrates conversation context and rate limit state
4. Bot deletes old username data

**Data Structures:**
- `llm_user_contexts`: Stores conversation history per username
- `llm_last_request`: Stores rate limit timestamps per username

**Benefits:**
- Users addressed correctly after name changes
- Conversation history preserved across name changes
- Rate limiting works consistently (can't bypass by changing name)
```

---

## 10. Future Enhancements

**FE-001: Persistent Username Mapping**
```python
# Store in database
CREATE TABLE username_mappings (
    old_name TEXT NOT NULL,
    new_name TEXT NOT NULL,
    changed_at INTEGER NOT NULL
);

# Track full history
def get_username_history(username):
    """Return all previous names for this user."""
    return db.query("SELECT old_name FROM username_mappings WHERE new_name=?", username)
```

**FE-002: Username Aliases**
```python
# Allow users to set aliases
"llm_username_aliases": {
    "Alice": ["alice123", "alice_smith", "Guest_123"]
}

# Recognize user by any alias
if any(alias in message for alias in get_aliases(username)):
    trigger_llm()
```

**FE-003: Username Validation**
```python
# Detect suspicious name changes (impersonation)
if new_name in ADMIN_USERNAMES and old_name not in ADMIN_USERNAMES:
    logger.warning('Suspicious name change: %s -> %s', old_name, new_name)
    # Alert moderators
```

**FE-004: Context Merging**
```python
# If new username already has context, merge instead of overwrite
if new_name in llm_user_contexts and old_name in llm_user_contexts:
    llm_user_contexts[new_name].extend(llm_user_contexts[old_name])
    # Trim to max_history_messages
```

---

## 11. Related Specifications

- **SPEC-Commit-1-LLM-Foundation.md**: Defines context and rate limit structures
- **SPEC-Commit-3-Trigger-System-Refinement.md**: Uses corrected usernames for logging

---

## 12. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Next Commit:** Commit 5 - Deployment Automation
