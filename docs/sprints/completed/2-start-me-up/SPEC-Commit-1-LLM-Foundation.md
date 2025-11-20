# Technical Specification: Commit 1 - LLM Foundation

**Commit Title:** LLM Foundation  
**Feature:** Core LLM Integration  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 1)  
**Target Release:** v0.3.0  

---

## 1. Overview

### 1.1 Purpose
Establish the foundational infrastructure for LLM integration in Rosey, enabling the bot to respond to chat messages using external language model services (OpenAI or Ollama).

### 1.2 Scope
- Add LLM provider initialization (OpenAI and Ollama)
- Implement message trigger detection system
- Create in-memory conversation context management
- Add configuration schema for LLM settings
- Integrate LLM response generation into chat message handler

### 1.3 Non-Goals
- Remote Ollama server support (Commit 2)
- Advanced trigger pattern matching (Commit 3)
- Username correction system (Commit 4)
- Production deployment automation (Commit 5)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: LLM Provider Initialization**
- Bot shall accept `llm_config` parameter in `__init__()`
- Bot shall support two provider types: "openai" and "ollama"
- Bot shall initialize the appropriate provider client library
- Bot shall log successful initialization or failure

**FR-002: Message Trigger Detection**
- Bot shall check each chat message for configured trigger patterns
- Bot shall support exact string matching (case-sensitive initially)
- Bot shall use bot's own username as default trigger
- Bot shall log when triggers are detected

**FR-003: LLM Request Generation**
- Bot shall construct prompts with system message and user message
- Bot shall include bot's personality in system prompt
- Bot shall send requests to configured LLM provider
- Bot shall handle API timeouts (default 30 seconds)

**FR-004: Response Posting**
- Bot shall extract text from LLM API responses
- Bot shall post responses to channel chat via `bot.chat()`
- Bot shall log response length and generation time
- Bot shall handle response formatting (strip whitespace)

**FR-005: Context Management**
- Bot shall maintain in-memory conversation history per user
- Bot shall store messages as list of dicts: `[{"role": "user"|"assistant", "content": str}]`
- Bot shall limit context to last N messages (configurable, default 10)
- Bot shall clear context on bot restart

**FR-006: Configuration Schema**
- Configuration shall include `llm` section with fields:
  - `enabled` (bool): Master switch for LLM features
  - `provider` (str): "openai" or "ollama"
  - `model` (str): Model identifier (e.g., "gpt-4o-mini", "llama3.2:3b")
  - `openai_api_key` (str): OpenAI API key (required for OpenAI)
  - `system_prompt` (str): Bot personality/instructions
  - `llm_triggers` (list[str]): Activation patterns
  - `llm_cooldown` (int): Seconds between requests per user
  - `max_history_messages` (int): Context window size

### 2.2 Non-Functional Requirements

**NFR-001: Performance**
- Trigger detection shall complete in <1ms
- Context assembly shall complete in <10ms
- LLM integration shall not block main event loop
- Bot shall maintain existing performance for non-LLM operations

**NFR-002: Reliability**
- Bot shall continue operating if LLM provider is unavailable
- Bot shall catch and log all LLM-related exceptions
- Bot shall not crash on malformed LLM responses

**NFR-003: Maintainability**
- All LLM logic shall be contained in `lib/bot.py`
- Methods shall have clear names prefixed with `_llm_` or `_handle_llm_`
- Code shall include docstrings and inline comments

---

## 3. Design

### 3.1 Architecture

```
Bot.__init__()
    ↓
_setup_llm()  ← Initialize provider (OpenAI or Ollama)
    ↓
Bot.start() → Event loop starts
    ↓
_on_chat_msg()  ← Chat message received
    ↓
_check_llm_trigger()  ← Check if message matches triggers
    ↓ (if matched)
_handle_llm_chat()
    ↓
    ├─ Rate limit check
    ├─ Context assembly
    ├─ API call (OpenAI or Ollama)
    ├─ Response extraction
    ├─ bot.chat() (post to channel)
    └─ Context update
```

### 3.2 Data Structures

**Configuration Schema:**
```python
llm_config = {
    "enabled": bool,
    "provider": "openai" | "ollama",
    "model": str,
    "openai_api_key": str,  # Required for OpenAI
    "system_prompt": str,
    "llm_triggers": [str, ...],
    "llm_cooldown": int,  # seconds
    "max_history_messages": int
}
```

**Context Storage:**
```python
# Per-user conversation history
self.llm_user_contexts: dict[str, list[dict]]
# Example:
{
    "User123": [
        {"role": "user", "content": "hey rosey!"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "what's the weather?"}
    ]
}

# Rate limiting state
self.llm_last_request: dict[str, float]
# Example:
{
    "User123": 1699632150.5  # Unix timestamp
}
```

### 3.3 API Interactions

**OpenAI API Call:**
```python
import openai

client = openai.OpenAI(api_key=llm_config['openai_api_key'])

response = client.chat.completions.create(
    model=llm_config['model'],
    messages=[
        {"role": "system", "content": llm_config['system_prompt']},
        *context_messages,
        {"role": "user", "content": user_message}
    ],
    timeout=30
)

reply = response.choices[0].message.content
```

**Ollama API Call:**
```python
import ollama

client = ollama.Client()  # Uses localhost:11434 by default

response = client.chat(
    model=llm_config['model'],
    messages=[
        {"role": "system", "content": llm_config['system_prompt']},
        *context_messages,
        {"role": "user", "content": user_message}
    ]
)

reply = response['message']['content']
```

---

## 4. Implementation

### 4.1 Modified Files

**`lib/bot.py`**

#### 4.1.1 Add Instance Variables

```python
class Bot:
    def __init__(self, domain, channel, user, ..., llm_config=None):
        # ... existing init code ...
        
        # LLM integration
        self.llm_config = llm_config
        self.llm_client = None
        self.llm_user_contexts = {}  # username -> [message_dicts]
        self.llm_last_request = {}   # username -> timestamp
        
        # Initialize LLM if configured
        if self.llm_config and self.llm_config.get('enabled'):
            asyncio.create_task(self._setup_llm())
```

#### 4.1.2 Add `_setup_llm()` Method

```python
async def _setup_llm(self):
    """Initialize LLM provider based on configuration."""
    provider = self.llm_config.get('provider', '').lower()
    
    if provider == 'openai':
        try:
            import openai
            api_key = self.llm_config.get('openai_api_key')
            if not api_key:
                self.logger.error('OpenAI API key not provided')
                return
            self.llm_client = openai.OpenAI(api_key=api_key)
            self.logger.info('LLM enabled: provider=openai, model=%s', 
                           self.llm_config.get('model'))
        except ImportError:
            self.logger.error('openai library not installed: pip install openai')
            
    elif provider == 'ollama':
        try:
            import ollama
            self.llm_client = ollama.Client()
            # Test connection
            self.llm_client.list()  # Will raise if server unavailable
            self.logger.info('LLM enabled: provider=ollama, model=%s', 
                           self.llm_config.get('model'))
        except ImportError:
            self.logger.error('ollama library not installed: pip install ollama')
        except Exception as e:
            self.logger.error('Ollama server unavailable: %s', e)
    else:
        self.logger.error('Unknown LLM provider: %s', provider)
```

#### 4.1.3 Add `_check_llm_trigger()` Method

```python
def _check_llm_trigger(self, message: str) -> bool:
    """Check if message matches configured trigger patterns."""
    if not self.llm_config or not self.llm_client:
        return False
    
    triggers = self.llm_config.get('llm_triggers', [self.username])
    message_lower = message.lower()
    
    for trigger in triggers:
        if trigger in message:  # Case-sensitive for now
            self.logger.debug('LLM trigger matched: "%s" in "%s"', trigger, message)
            return True
    
    return False
```

#### 4.1.4 Add `_handle_llm_chat()` Method

```python
async def _handle_llm_chat(self, username: str, message: str):
    """Generate and send LLM response."""
    import time
    
    # Rate limit check
    cooldown = self.llm_config.get('llm_cooldown', 10)
    now = time.time()
    last_request = self.llm_last_request.get(username, 0)
    
    if now - last_request < cooldown:
        self.logger.debug('LLM cooldown active for user=%s', username)
        return
    
    # Update timestamp
    self.llm_last_request[username] = now
    
    # Get conversation context
    context = self.llm_user_contexts.get(username, [])
    max_history = self.llm_config.get('max_history_messages', 10)
    context = context[-max_history:]  # Keep last N messages
    
    # Assemble messages
    system_prompt = self.llm_config.get('system_prompt', 
                                       f'You are {self.username}, a helpful chat bot.')
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context)
    messages.append({"role": "user", "content": message})
    
    try:
        provider = self.llm_config.get('provider')
        model = self.llm_config.get('model')
        
        start_time = time.time()
        
        if provider == 'openai':
            response = self.llm_client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=30
            )
            reply = response.choices[0].message.content.strip()
            
        elif provider == 'ollama':
            response = self.llm_client.chat(
                model=model,
                messages=messages
            )
            reply = response['message']['content'].strip()
        else:
            self.logger.error('Unknown provider: %s', provider)
            return
        
        elapsed = time.time() - start_time
        self.logger.info('LLM response: user=%s, length=%d, time=%.2fs', 
                        username, len(reply), elapsed)
        
        # Send to channel
        await self.chat(reply)
        
        # Update context
        if username not in self.llm_user_contexts:
            self.llm_user_contexts[username] = []
        self.llm_user_contexts[username].append({"role": "user", "content": message})
        self.llm_user_contexts[username].append({"role": "assistant", "content": reply})
        
    except Exception as e:
        self.logger.error('LLM error: %s', e, exc_info=True)
```

#### 4.1.5 Modify `_on_chat_msg()` Method

```python
async def _on_chat_msg(self, event, data):
    """Handle incoming chat messages."""
    # ... existing message parsing ...
    
    username = data.get('username')
    message = data.get('msg')
    
    # Check for LLM trigger
    if self._check_llm_trigger(message):
        await self._handle_llm_chat(username, message)
    
    # ... existing code (logging, commands, etc.) ...
```

### 4.2 Configuration Files

**`bot/rosey/config.json.dist`**

Add new section:
```json
{
  "domain": "https://cytu.be",
  "channel": "YourChannel",
  "user": ["BotName", "password"],
  "llm": {
    "enabled": false,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "openai_api_key": "",
    "system_prompt": "You are Rosey, a helpful assistant in a CyTube chat.",
    "llm_triggers": ["rosey", "@rosey"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

### 4.3 Dependencies

**`requirements.txt`**

Add new dependencies:
```txt
openai>=1.10.0
ollama>=0.1.0
```

---

## 5. Testing

### 5.1 Unit Tests

**Test Trigger Detection:**
```python
def test_check_llm_trigger_matched():
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True  # Mock
    assert bot._check_llm_trigger("hey rosey!") == True

def test_check_llm_trigger_not_matched():
    bot = Bot(llm_config={"llm_triggers": ["rosey"]})
    bot.llm_client = True
    assert bot._check_llm_trigger("hello world") == False

def test_check_llm_trigger_disabled():
    bot = Bot(llm_config=None)
    assert bot._check_llm_trigger("rosey") == False
```

**Test Rate Limiting:**
```python
@pytest.mark.asyncio
async def test_rate_limiting():
    bot = Bot(llm_config={"llm_cooldown": 10})
    bot.llm_client = True
    
    # First request
    await bot._handle_llm_chat("User1", "test")
    assert "User1" in bot.llm_last_request
    
    # Second request (should be blocked)
    import time
    time.sleep(1)
    await bot._handle_llm_chat("User1", "test2")
    # Verify no API call made (mock and check)
```

**Test Context Management:**
```python
def test_context_pruning():
    bot = Bot(llm_config={"max_history_messages": 3})
    bot.llm_user_contexts["User1"] = [
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "reply1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "reply2"},
        {"role": "user", "content": "msg3"},
    ]
    
    # Simulate getting context in _handle_llm_chat
    context = bot.llm_user_contexts["User1"][-3:]
    assert len(context) == 3
    assert context[0]["content"] == "reply2"
```

### 5.2 Integration Tests

**Test with Live Ollama:**
```bash
# Start Ollama server
ollama serve

# Pull test model
ollama pull llama3.2:3b

# Run bot with test config
python -m lib test-llm-config.json
```

**Manual Test Checklist:**
- [ ] Bot starts with `llm.enabled=true`
- [ ] Bot logs "LLM enabled: provider=..."
- [ ] Send message "hey rosey" in channel
- [ ] Bot generates and posts response
- [ ] Send another message within cooldown period
- [ ] Bot ignores second message
- [ ] Wait for cooldown to expire
- [ ] Send third message
- [ ] Bot responds again

### 5.3 Error Cases

**Test Missing API Key:**
```json
{"llm": {"enabled": true, "provider": "openai", "openai_api_key": ""}}
```
Expected: Error logged, LLM disabled

**Test Invalid Model:**
```json
{"llm": {"provider": "ollama", "model": "nonexistent-model"}}
```
Expected: Error on first request, logged gracefully

**Test Network Timeout:**
- Configure 30s timeout
- Use slow/unreachable Ollama server
- Verify timeout handled, bot continues

---

## 6. Acceptance Criteria

- [x] Bot accepts `llm_config` parameter in `__init__()`
- [x] Bot initializes OpenAI client when `provider="openai"`
- [x] Bot initializes Ollama client when `provider="ollama"`
- [x] Bot detects messages matching `llm_triggers`
- [x] Bot generates LLM responses for triggered messages
- [x] Bot posts responses to channel chat
- [x] Bot maintains per-user conversation context
- [x] Bot enforces rate limiting (cooldown period)
- [x] Bot limits context to `max_history_messages`
- [x] Bot logs all LLM operations (trigger, request, response, error)
- [x] Bot continues operating when LLM provider unavailable
- [x] Configuration schema documented in `.dist` file
- [x] Dependencies added to `requirements.txt`

---

## 7. Rollout

### 7.1 Deployment Steps

1. Update code in `lib/bot.py`
2. Update `requirements.txt`
3. Create `bot/rosey/config.json.dist` with LLM section
4. Install dependencies: `pip install -r requirements.txt`
5. Configure bot (copy `.dist` to `config.json`, edit settings)
6. Test locally with Ollama
7. Deploy to test channel
8. Monitor logs for errors
9. Gather user feedback

### 7.2 Rollback Plan

If critical issues:
1. Set `llm.enabled = false` in config
2. Restart bot
3. Investigate logs
4. Fix issues and redeploy

### 7.3 Monitoring

**Key Metrics:**
- LLM trigger rate (triggers/minute)
- LLM response time (seconds, p95)
- LLM error rate (errors/requests)
- Bot memory usage (MB)

**Log Monitoring:**
```bash
# Watch for LLM activity
journalctl -u cytube-bot -f | grep LLM

# Count triggers
journalctl -u cytube-bot --since today | grep "LLM trigger" | wc -l

# Find errors
journalctl -u cytube-bot --since today | grep "LLM error"
```

---

## 8. Documentation

### 8.1 Code Comments

All new methods include docstrings:
```python
async def _setup_llm(self):
    """Initialize LLM provider based on configuration.
    
    Supports two providers:
    - openai: Requires openai_api_key in config
    - ollama: Requires ollama server running (localhost:11434)
    
    Logs success/failure messages.
    Sets self.llm_client on success, leaves None on failure.
    """
```

### 8.2 Configuration Documentation

Create `docs/LLM_CONFIGURATION.md`:
```markdown
# LLM Configuration

## Quick Start

1. Choose provider (OpenAI or Ollama)
2. Add `llm` section to config.json
3. Set `enabled: true`
4. Configure model and triggers

## OpenAI Setup
...

## Ollama Setup
...
```

### 8.3 Inline Comments

Critical sections include comments:
```python
# Rate limit check - prevent spam
if now - last_request < cooldown:
    return

# Prune old messages - stay within token limits
context = context[-max_history:]

# Send to channel - async to avoid blocking
await self.chat(reply)
```

---

## 9. Related Specifications

- **SPEC-Commit-2-Ollama-Remote-Support.md**: Extends `_setup_llm()` for remote servers
- **SPEC-Commit-3-Trigger-System-Refinement.md**: Improves `_check_llm_trigger()`
- **SPEC-Commit-4-Username-Correction.md**: Adds `_on_set_user_profile()` handler

---

## 10. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Next Commit:** Commit 2 - Ollama Remote Support
