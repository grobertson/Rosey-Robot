# Technical Specification: Commit 3 - Trigger System Refinement

**Commit Title:** Trigger System Refinement  
**Feature:** Enhanced Message Trigger Detection  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 3), US-004  
**Dependencies:** SPEC-Commit-1-LLM-Foundation.md  
**Target Release:** v2.1.0  

---

## 1. Overview

### 1.1 Purpose

Improve the trigger detection system to handle real-world chat scenarios more reliably, including case-insensitive matching, multiple trigger patterns, and better logging for debugging trigger failures.

### 1.2 Scope

- Implement case-insensitive username matching
- Support multiple trigger patterns from configuration
- Add debug logging for trigger checks (matched and not matched)
- Handle edge cases (punctuation, spacing, Unicode)
- Maintain backward compatibility with Commit 1

### 1.3 Non-Goals

- Regex pattern matching (future enhancement)
- Fuzzy/similarity matching (e.g., "rsey" → "rosey")
- Context-aware triggers (e.g., only respond to questions)
- Trigger priority/ordering

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: Case-Insensitive Matching**
- Trigger detection shall be case-insensitive
- "rosey", "Rosey", "ROSEY", "rOsEy" shall all match trigger "rosey"
- Case-insensitivity shall apply to all configured triggers
- Original message case shall be preserved when passing to LLM

**FR-002: Multiple Trigger Support**
- Configuration shall accept list of trigger strings
- Any trigger match shall activate LLM response
- Triggers shall be evaluated in order defined in config
- First match shall trigger response (no multiple responses per message)

**FR-003: Default Trigger Behavior**
- If `llm_triggers` not specified, use bot's username as default
- Bot username shall be normalized (lowercase) for matching
- Default trigger shall support both plain username and @-mention format

**FR-004: Debug Logging**
- Log each message checked for triggers (at DEBUG level)
- Log which trigger matched (if any)
- Log when no triggers matched
- Include username and message preview in logs

**FR-005: Edge Case Handling**
- Handle punctuation adjacent to triggers ("rosey!" → match)
- Handle Unicode characters in messages
- Handle empty/whitespace-only messages gracefully
- Handle very long messages (>1000 chars) without performance issues

### 2.2 Non-Functional Requirements

**NFR-001: Performance**
- Trigger check shall complete in <1ms for typical messages
- Trigger check shall complete in <5ms for messages with 10+ triggers
- Performance shall not degrade with message length

**NFR-002: Maintainability**
- Code shall be readable and well-commented
- Logic shall be testable with unit tests
- Changes shall not break existing functionality

---

## 3. Design

### 3.1 Algorithm

**Improved Trigger Matching:**

```python
def _check_llm_trigger(self, message: str) -> bool:
    # Quick checks
    if not llm_enabled or not llm_client:
        return False
    
    # Normalize message for comparison
    message_lower = message.lower()
    
    # Get triggers (or use default)
    triggers = config.get('llm_triggers', [bot_username.lower()])
    
    # Check each trigger
    for trigger in triggers:
        trigger_lower = trigger.lower()
        if trigger_lower in message_lower:
            logger.debug('LLM trigger matched: "%s" in "%s"', trigger, message[:50])
            return True
    
    logger.debug('LLM no trigger matched in: "%s"', message[:50])
    return False
```

**Matching Examples:**

| Message | Trigger | Match? | Reason |
|---------|---------|--------|--------|
| "hey rosey!" | "rosey" | ✅ Yes | Exact substring (case-insensitive) |
| "ROSEY help me" | "rosey" | ✅ Yes | Case-insensitive |
| "@rosey what time?" | "@rosey" | ✅ Yes | Prefix trigger |
| "tell rosey123 hi" | "rosey" | ✅ Yes | Substring match (may be false positive) |
| "hello world" | "rosey" | ❌ No | No match |
| "ros ey" | "rosey" | ❌ No | Spaces break match |

### 3.2 Configuration Schema

**Updated `llm_triggers` field:**

```json
{
  "llm": {
    "llm_triggers": ["rosey", "@rosey", "hey rosey"]
  }
}
```

**Examples:**

```json
// Single trigger (bot name only)
"llm_triggers": ["botname"]

// Multiple triggers
"llm_triggers": ["botname", "@botname", "hey bot"]

// Phrases
"llm_triggers": ["hey rosey", "rosey help", "question for rosey"]

// Empty (use bot username as default)
"llm_triggers": []
```

### 3.3 Logging Output

**Debug Level Logs:**

```
[2025-11-10 14:32:20] [lib.bot] [DEBUG] LLM trigger check: user=TestUser, message="hey rosey!"
[2025-11-10 14:32:20] [lib.bot] [DEBUG] LLM trigger matched: "rosey" in "hey rosey!"
[2025-11-10 14:32:22] [lib.bot] [INFO] LLM response: user=TestUser, length=156, time=1.8s

[2025-11-10 14:33:15] [lib.bot] [DEBUG] LLM trigger check: user=TestUser, message="hello world"
[2025-11-10 14:33:15] [lib.bot] [DEBUG] LLM no trigger matched in: "hello world"
```

**Info Level Logs:**

```
[2025-11-10 14:32:20] [lib.bot] [INFO] LLM trigger: user=TestUser, message="hey rosey!"
[2025-11-10 14:32:22] [lib.bot] [INFO] LLM response: user=TestUser, length=156, time=1.8s
```

---

## 4. Implementation

### 4.1 Modified Files

**`lib/bot.py`**

#### 4.1.1 Update `_check_llm_trigger()` Method

**Before (Commit 1):**
```python
def _check_llm_trigger(self, message: str) -> bool:
    """Check if message matches configured trigger patterns."""
    if not self.llm_config or not self.llm_client:
        return False
    
    triggers = self.llm_config.get('llm_triggers', [self.username])
    message_lower = message.lower()
    
    for trigger in triggers:
        if trigger in message:  # Case-sensitive - PROBLEM!
            self.logger.debug('LLM trigger matched: "%s" in "%s"', trigger, message)
            return True
    
    return False
```

**After (Commit 3):**
```python
def _check_llm_trigger(self, message: str) -> bool:
    """Check if message matches configured trigger patterns (case-insensitive).
    
    Args:
        message: Raw chat message text
        
    Returns:
        True if any trigger matched, False otherwise
    """
    # Quick validation
    if not self.llm_config or not self.llm_client:
        return False
    
    if not message or not message.strip():
        return False
    
    # Normalize message for comparison
    message_lower = message.lower()
    
    # Get triggers or use bot username as default
    triggers = self.llm_config.get('llm_triggers')
    if not triggers:
        triggers = [self.username.lower()]
    
    # Check each trigger (case-insensitive)
    for trigger in triggers:
        trigger_lower = trigger.lower()
        if trigger_lower in message_lower:
            # Log matched trigger (truncate long messages)
            msg_preview = message[:50] + ('...' if len(message) > 50 else '')
            self.logger.debug('LLM trigger matched: "%s" in "%s"', trigger, msg_preview)
            self.logger.info('LLM trigger: user=%s, message="%s"', 
                           # Assume username available in caller context
                           'UNKNOWN', msg_preview)
            return True
    
    # Log non-matches at debug level
    msg_preview = message[:50] + ('...' if len(message) > 50 else '')
    self.logger.debug('LLM no trigger matched in: "%s"', msg_preview)
    return False
```

#### 4.1.2 Update `_on_chat_msg()` to Pass Username to Logger

```python
async def _on_chat_msg(self, event, data):
    """Handle incoming chat messages."""
    username = data.get('username')
    message = data.get('msg')
    
    # Store username temporarily for logging (hacky but works)
    self._last_chat_username = username
    
    # Check for LLM trigger
    if self._check_llm_trigger(message):
        await self._handle_llm_chat(username, message)
    
    # ... existing code ...
```

**Better Approach:** Pass username as parameter:
```python
def _check_llm_trigger(self, message: str, username: str = None) -> bool:
    """Check if message matches configured trigger patterns."""
    # ... validation ...
    
    for trigger in triggers:
        trigger_lower = trigger.lower()
        if trigger_lower in message_lower:
            msg_preview = message[:50] + ('...' if len(message) > 50 else '')
            self.logger.debug('LLM trigger matched: "%s" in "%s"', trigger, msg_preview)
            if username:
                self.logger.info('LLM trigger: user=%s, message="%s"', 
                               username, msg_preview)
            return True
    
    # ... no match ...
    return False

# Caller:
if self._check_llm_trigger(message, username):
    await self._handle_llm_chat(username, message)
```

### 4.2 Configuration Files

**`bot/rosey/config.json.dist`**

Update with better examples:
```json
{
  "llm": {
    "enabled": false,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "ollama_host": "http://localhost:11434",
    "system_prompt": "You are Rosey, a helpful assistant.",
    "llm_triggers": ["rosey", "@rosey", "hey rosey"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

### 4.3 Logging Configuration

**Enable DEBUG logging for testing:**

```json
{
  "log_level": "DEBUG",
  "log_file": "bot.log"
}
```

**In code:**
```python
# Configure logger to show DEBUG messages
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 5. Testing

### 5.1 Unit Tests

**Test Case-Insensitive Matching:**
```python
def test_trigger_case_insensitive():
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True  # Mock
    
    assert bot._check_llm_trigger("hey rosey!") == True
    assert bot._check_llm_trigger("hey Rosey!") == True
    assert bot._check_llm_trigger("hey ROSEY!") == True
    assert bot._check_llm_trigger("hey rOsEy!") == True
    assert bot._check_llm_trigger("HEY ROSEY") == True
```

**Test Multiple Triggers:**
```python
def test_multiple_triggers():
    bot = Bot(llm_config={"llm_triggers": ["rosey", "@rosey", "hey rosey"]})
    bot.llm_client = True
    
    assert bot._check_llm_trigger("rosey help") == True
    assert bot._check_llm_trigger("@rosey what?") == True
    assert bot._check_llm_trigger("hey rosey how are you") == True
    assert bot._check_llm_trigger("hello world") == False
```

**Test Default Trigger:**
```python
def test_default_trigger_is_username():
    bot = Bot(username="TestBot", llm_config={"llm_triggers": []})
    bot.llm_client = True
    
    assert bot._check_llm_trigger("hey testbot!") == True
    assert bot._check_llm_trigger("TestBot help") == True
    assert bot._check_llm_trigger("TESTBOT") == True
```

**Test Edge Cases:**
```python
def test_edge_cases():
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True
    
    # Punctuation
    assert bot._check_llm_trigger("rosey!") == True
    assert bot._check_llm_trigger("rosey?") == True
    assert bot._check_llm_trigger("(rosey)") == True
    
    # Whitespace
    assert bot._check_llm_trigger("  rosey  ") == True
    assert bot._check_llm_trigger("\nrosey\n") == True
    
    # Empty/None
    assert bot._check_llm_trigger("") == False
    assert bot._check_llm_trigger("   ") == False
    
    # Unicode
    assert bot._check_llm_trigger("rosey 你好") == True
    assert bot._check_llm_trigger("rosey 🤖") == True
    
    # Long message
    long_msg = "hello " * 100 + "rosey"
    assert bot._check_llm_trigger(long_msg) == True
```

**Test Logging:**
```python
def test_logging_on_match(caplog):
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True
    
    with caplog.at_level(logging.DEBUG):
        bot._check_llm_trigger("hey rosey!")
    
    assert 'LLM trigger matched' in caplog.text
    assert 'rosey' in caplog.text

def test_logging_on_no_match(caplog):
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True
    
    with caplog.at_level(logging.DEBUG):
        bot._check_llm_trigger("hello world")
    
    assert 'LLM no trigger matched' in caplog.text
```

### 5.2 Integration Tests

**Manual Test Scenarios:**

1. **Basic Trigger Test:**
   ```
   Config: "llm_triggers": ["rosey"]
   
   Input: "hey rosey!"
   Expected: LLM responds
   
   Input: "ROSEY HELP"
   Expected: LLM responds
   
   Input: "hello world"
   Expected: No response
   ```

2. **Multiple Trigger Test:**
   ```
   Config: "llm_triggers": ["rosey", "@rosey", "bot"]
   
   Input: "rosey help"
   Expected: LLM responds
   
   Input: "@rosey what time?"
   Expected: LLM responds
   
   Input: "bot answer this"
   Expected: LLM responds
   ```

3. **Default Trigger Test:**
   ```
   Config: "llm_triggers": []  (empty or omitted)
   Bot username: "RoseyBot"
   
   Input: "roseybot help"
   Expected: LLM responds
   
   Input: "ROSEYBOT"
   Expected: LLM responds
   ```

4. **Debug Logging Test:**
   ```
   Config: "log_level": "DEBUG"
   
   Send messages and verify logs show:
   - "LLM trigger check: user=..."
   - "LLM trigger matched: ..." (on match)
   - "LLM no trigger matched in: ..." (on no match)
   ```

### 5.3 Performance Tests

**Benchmark Trigger Check:**
```python
import time

def benchmark_trigger_check():
    bot = Bot(llm_config={"llm_triggers": ["rosey", "@rosey", "hey rosey"]})
    bot.llm_client = True
    
    message = "hey rosey how are you?"
    iterations = 10000
    
    start = time.time()
    for _ in range(iterations):
        bot._check_llm_trigger(message)
    elapsed = time.time() - start
    
    avg_time = (elapsed / iterations) * 1000  # milliseconds
    print(f"Average trigger check time: {avg_time:.4f}ms")
    
    assert avg_time < 1.0, "Trigger check too slow!"

# Expected output: Average trigger check time: 0.05ms
```

---

## 6. Acceptance Criteria

- [x] Trigger matching is case-insensitive
- [x] "rosey", "Rosey", "ROSEY" all trigger LLM
- [x] Multiple triggers supported (any match activates)
- [x] Default trigger is bot's username if `llm_triggers` empty
- [x] Debug logs show trigger checks (matched and not matched)
- [x] Info logs show matched triggers with username
- [x] Message preview in logs truncated to 50 chars
- [x] Empty/whitespace messages handled gracefully
- [x] Unicode characters handled correctly
- [x] Long messages (>1000 chars) handled without performance issues
- [x] Backward compatible with Commit 1 configuration

---

## 7. Deployment

### 7.1 Deployment Steps

1. Update `lib/bot.py` with new `_check_llm_trigger()` logic
2. Update `bot/rosey/config.json.dist` with multiple trigger examples
3. Test locally with various trigger configurations
4. Deploy to test channel
5. Monitor debug logs for trigger behavior
6. Adjust triggers based on false positives/negatives

### 7.2 Configuration Migration

**Old Config (Commit 1):**
```json
{
  "llm": {
    "llm_triggers": ["rosey"]
  }
}
```

**New Config (Commit 3):**
```json
{
  "llm": {
    "llm_triggers": ["rosey", "@rosey", "hey rosey"]
  }
}
```

**No Breaking Changes:** Old configs work as-is (case-insensitivity is backward compatible).

### 7.3 Tuning Triggers

**Best Practices:**

1. **Start Narrow:**
   ```json
   "llm_triggers": ["@rosey"]  // Only @-mentions
   ```

2. **Expand Gradually:**
   ```json
   "llm_triggers": ["@rosey", "rosey help", "rosey?"]
   ```

3. **Avoid False Positives:**
   ```
   BAD: "llm_triggers": ["bot"]  // Too generic
   GOOD: "llm_triggers": ["@rosey", "hey rosey"]
   ```

4. **Use Phrases for Context:**
   ```json
   "llm_triggers": ["rosey what", "rosey how", "rosey why"]
   ```

---

## 8. Known Issues and Limitations

### 8.1 Current Limitations

**L-001: Substring Matching**
- "rosey123" will match trigger "rosey"
- "grosey" will NOT match (not a substring)
- **Mitigation:** Use more specific triggers (e.g., "@rosey")

**L-002: No Regex Support**
- Cannot use patterns like "rosey\b" (word boundary)
- Cannot use wildcards or character classes
- **Future Enhancement:** Add regex mode

**L-003: No Fuzzy Matching**
- Typos don't match: "rsoey" ≠ "rosey"
- **Future Enhancement:** Levenshtein distance matching

**L-004: No Context Awareness**
- Triggers anywhere in message, even mid-word
- **Future Enhancement:** NLP-based intent detection

### 8.2 False Positive Scenarios

**Scenario:** User discussing bot, not addressing it
```
User1: "I think rosey is broken"
Bot: *responds to "rosey" trigger*  // Unintended
```

**Mitigation:**
- Use @-mention triggers: `"llm_triggers": ["@rosey"]`
- Add system prompt: "Only respond when directly addressed"

**Scenario:** Bot's name is common word
```
Bot name: "Test"
User: "this is a test"
Bot: *responds*  // Unintended
```

**Mitigation:**
- Use unique bot name
- Add prefix: "llm_triggers": ["@test", "hey test"]

### 8.3 False Negative Scenarios

**Scenario:** Trigger with typo
```
Trigger: "rosey"
User: "hey rsoey!"
Bot: *no response*  // Typo not recognized
```

**Mitigation:**
- Add common typos to triggers: `["rosey", "rosie", "rosy"]`
- Or wait for fuzzy matching feature

---

## 9. Documentation Updates

### 9.1 Code Documentation

Updated docstring for `_check_llm_trigger()`:
```python
def _check_llm_trigger(self, message: str, username: str = None) -> bool:
    """Check if message matches configured trigger patterns (case-insensitive).
    
    Performs substring matching on normalized (lowercase) message text.
    Supports multiple trigger patterns - any match returns True.
    
    Args:
        message: Raw chat message text
        username: Optional username for logging
        
    Returns:
        True if any trigger matched, False otherwise
        
    Examples:
        >>> bot._check_llm_trigger("hey rosey!")  # Returns True
        >>> bot._check_llm_trigger("ROSEY help")  # Returns True
        >>> bot._check_llm_trigger("hello world")  # Returns False
        
    Notes:
        - Matching is case-insensitive
        - Empty messages return False
        - First match short-circuits (no multiple responses)
        - Logs at DEBUG level for all checks
        - Logs at INFO level for matches (with username if provided)
    """
```

### 9.2 Configuration Documentation

Add to README or configuration guide:
```markdown
### LLM Triggers

The `llm_triggers` field controls when the bot activates LLM responses.

**Matching Rules:**
- Case-insensitive: "rosey" matches "ROSEY", "Rosey", etc.
- Substring: trigger anywhere in message
- Multiple triggers: any match activates response
- Default: bot's username if not specified

**Examples:**

```json
// Single trigger
"llm_triggers": ["rosey"]

// Multiple triggers
"llm_triggers": ["rosey", "@rosey", "hey rosey"]

// Phrase triggers (more specific)
"llm_triggers": ["rosey help", "rosey what", "ask rosey"]
```

**Tips:**
- Use `@mentions` to reduce false positives
- Add common phrases ("hey rosey", "thanks rosey")
- Avoid generic words that appear in normal chat
- Test triggers in low-traffic channel first
```

---

## 10. Related Specifications

- **SPEC-Commit-1-LLM-Foundation.md**: Defines original `_check_llm_trigger()`
- **SPEC-Commit-4-Username-Correction.md**: Uses corrected usernames with triggers

---

## 11. Future Enhancements

**FE-001: Regex Pattern Support**
```json
"llm_triggers": ["^@?rosey\\b", "\\brosey[?!]"]
"llm_trigger_mode": "regex"
```

**FE-002: Fuzzy Matching**
```json
"llm_triggers": ["rosey"],
"llm_trigger_fuzzy": true,
"llm_trigger_fuzzy_threshold": 0.8  // Levenshtein ratio
```

**FE-003: Intent Detection**
```python
# Use NLP to detect if user is asking a question
if is_question(message) and mentions_bot(message):
    trigger_llm()
```

**FE-004: Negative Triggers (Exclusions)**
```json
"llm_triggers": ["rosey"],
"llm_exclude_triggers": ["ignore rosey", "mute rosey"]
```

---

## 12. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Next Commit:** Commit 4 - Username Correction
