# SPEC: Sortie 2 - Magic 8-Ball Plugin

**Sprint:** 18 - Funny Games  
**Sortie:** 2 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 1 day  
**Priority:** HIGH - Simple plugin, showcases personality

---

## 1. Overview

### 1.1 Purpose

The Magic 8-Ball plugin provides fortune-telling entertainment, demonstrating:

- Simple stateless plugin pattern
- Personality injection (Rosey's character)
- Rate limiting to prevent spam
- Event emission for analytics

### 1.2 Scope

**In Scope:**
- `!8ball <question>` command
- Classic 20 8-ball responses
- Rosey personality flavor text
- Configurable cooldown per user
- Event emission

**Out of Scope:**
- Custom response sets
- Question history
- Prediction accuracy tracking (lol)

### 1.3 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Event bus (existing)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/8ball/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── responses.py          # Response definitions with categories
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_responses.py # Unit tests for response logic
    └── test_plugin.py    # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.8ball.ask` | Subscribe | Handle `!8ball` commands |
| `8ball.consulted` | Publish | Event emitted after each consultation |

### 2.3 Message Schemas

#### Ask Request (incoming)
```json
{
  "channel": "string",
  "user": "string",
  "args": "Will I win the lottery?",
  "reply_to": "rosey.reply.abc123"
}
```

#### Ask Response (outgoing)
```json
{
  "success": true,
  "result": {
    "question": "Will I win the lottery?",
    "answer": "Don't count on it",
    "category": "negative",
    "flavor": "Hmm, the spirits are skeptical...",
    "formatted": "🎱 \"Will I win the lottery?\" — Don't count on it. Hmm, the spirits are skeptical..."
  }
}
```

#### Consulted Event (published)
```json
{
  "event": "8ball.consulted",
  "timestamp": "2025-11-24T12:00:00Z",
  "channel": "string",
  "user": "string",
  "category": "negative"
}
```

### 2.4 Response Categories

The classic Magic 8-Ball has 20 responses in 3 categories:

#### Positive (10 responses)
```python
POSITIVE = [
    "It is certain",
    "It is decidedly so",
    "Without a doubt",
    "Yes definitely",
    "You may rely on it",
    "As I see it, yes",
    "Most likely",
    "Outlook good",
    "Yes",
    "Signs point to yes",
]
```

#### Neutral (5 responses)
```python
NEUTRAL = [
    "Reply hazy, try again",
    "Ask again later",
    "Better not tell you now",
    "Cannot predict now",
    "Concentrate and ask again",
]
```

#### Negative (5 responses)
```python
NEGATIVE = [
    "Don't count on it",
    "My reply is no",
    "My sources say no",
    "Outlook not so good",
    "Very doubtful",
]
```

### 2.5 Rosey Personality Flavor

Each category has flavor text that reflects Rosey's personality:

```python
POSITIVE_FLAVORS = [
    "The cosmos smile upon you! ✨",
    "Ooh, looking good!",
    "The vibes are immaculate.",
    "I like where this is going!",
    "The universe has spoken favorably!",
]

NEUTRAL_FLAVORS = [
    "Hmm, the mists are cloudy...",
    "The spirits are being coy today.",
    "Even I can't see through this fog.",
    "The universe is buffering...",
    "*shakes ball dramatically*",
]

NEGATIVE_FLAVORS = [
    "Yikes. Sorry, friend.",
    "The spirits are skeptical...",
    "Oof. Maybe don't bet on that one.",
    "The universe winced a little.",
    "That's a big ol' nope from the cosmos.",
]
```

### 2.6 Class Design

```python
# plugins/8ball/responses.py

import random
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


class Category(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class EightBallResponse:
    """A complete 8-ball response with flavor."""
    answer: str
    category: Category
    flavor: str
    
    def format(self, question: str) -> str:
        """Format for chat display."""
        return f'🎱 "{question}" — {self.answer}. {self.flavor}'


class ResponseSelector:
    """Select 8-ball responses with optional weighting."""
    
    POSITIVE: List[str] = [...]  # 10 responses
    NEUTRAL: List[str] = [...]   # 5 responses
    NEGATIVE: List[str] = [...]  # 5 responses
    
    POSITIVE_FLAVORS: List[str] = [...]
    NEUTRAL_FLAVORS: List[str] = [...]
    NEGATIVE_FLAVORS: List[str] = [...]
    
    def __init__(self, rng: random.Random = None):
        self.rng = rng or random.Random()
    
    def select(self) -> EightBallResponse:
        """
        Select a random response.
        
        Probability distribution matches original 8-ball:
        - Positive: 50% (10/20)
        - Neutral: 25% (5/20)
        - Negative: 25% (5/20)
        """
        ...
    
    def _select_from_category(self, category: Category) -> Tuple[str, str]:
        """Select answer and flavor from a specific category."""
        ...
```

```python
# plugins/8ball/plugin.py

import time
from collections import defaultdict
from lib.plugin.base import PluginBase
from .responses import ResponseSelector, EightBallResponse


class EightBallPlugin(PluginBase):
    """
    Magic 8-Ball fortune-telling plugin.
    
    Commands:
        !8ball <question> - Consult the mystical 8-ball
    """
    
    NAME = "8ball"
    VERSION = "1.0.0"
    DESCRIPTION = "Consult the mystical Magic 8-Ball"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        self.selector = ResponseSelector()
        self.cooldowns: dict[str, float] = defaultdict(float)
        self.cooldown_seconds = self.config.get("cooldown_seconds", 3)
    
    async def setup(self) -> None:
        """Register command handlers."""
        await self.subscribe("rosey.command.8ball.ask", self._handle_ask)
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup on shutdown."""
        self.cooldowns.clear()
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_ask(self, msg) -> None:
        """Handle !8ball command."""
        ...
    
    def _check_cooldown(self, user: str) -> bool:
        """Check if user is on cooldown. Returns True if allowed."""
        ...
    
    def _update_cooldown(self, user: str) -> None:
        """Update user's cooldown timestamp."""
        ...
    
    async def _emit_consulted_event(
        self, channel: str, user: str, category: str
    ) -> None:
        """Emit 8ball.consulted event for analytics."""
        ...
```

### 2.7 Configuration

```json
{
  "cooldown_seconds": 3,
  "emit_events": true,
  "require_question": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cooldown_seconds` | int | 3 | Seconds between uses per user |
| `emit_events` | bool | true | Whether to emit analytics events |
| `require_question` | bool | true | Whether to require a question |

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (20 minutes)

1. Create `plugins/8ball/` directory
2. Create `__init__.py` with exports
3. Create `config.json` with defaults
4. Create empty test files

### Step 2: Implement Response System (1 hour)

1. Define all 20 classic responses
2. Define Rosey flavor text for each category
3. Implement `ResponseSelector` class
4. Implement probability weighting (50/25/25)
5. Write unit tests for response selection

### Step 3: Implement Plugin Class (1.5 hours)

1. Implement `EightBallPlugin.__init__()`
2. Implement `setup()` with NATS subscription
3. Implement `teardown()` for cleanup
4. Implement `_handle_ask()` with question parsing
5. Implement cooldown logic
6. Implement event emission

### Step 4: Testing (45 minutes)

1. Unit tests for response selection distribution
2. Unit tests for cooldown logic
3. Integration tests for command handling
4. Test empty question handling
5. Test cooldown enforcement

### Step 5: Documentation (30 minutes)

1. Write README.md with examples
2. Add docstrings to all methods
3. Document configuration options

---

## 4. Test Cases

### 4.1 Response Selection Tests

| Test | Validation |
|------|------------|
| Distribution over 1000 selections | ~50% positive, ~25% neutral, ~25% negative (±5%) |
| All responses reachable | Each of 20 responses appears in 10000 trials |
| Flavor text matches category | Positive answer gets positive flavor |
| Seeded RNG | Deterministic results for testing |

### 4.2 Cooldown Tests

| Scenario | Expected |
|----------|----------|
| First use | Allowed |
| Immediate second use | Blocked with message |
| Use after cooldown | Allowed |
| Different users | Independent cooldowns |

### 4.3 Command Handling Tests

| Input | Expected |
|-------|----------|
| `!8ball Will I win?` | Random response with question |
| `!8ball` (no question, require=true) | Usage hint |
| `!8ball` (no question, require=false) | Random response |
| Very long question | Truncated in display |

### 4.4 Event Emission Tests

| Scenario | Event Data |
|----------|------------|
| Successful consultation | category, channel, user, timestamp |
| Cooldown blocked | No event emitted |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| No question (if required) | "🎱 The spirits need a question to answer! Usage: !8ball <question>" |
| On cooldown | "🎱 The 8-ball needs a moment to recover... try again in {X} seconds" |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| NATS timeout | Log error, respond with generic message |
| Unexpected exception | Log traceback, respond gracefully |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!8ball <question>` returns one of 20 classic responses
- [ ] Response includes Rosey personality flavor text
- [ ] Response includes 🎱 emoji
- [ ] `!8ball` without question shows usage (if configured)
- [ ] Cooldown prevents spam (configurable)
- [ ] Distribution matches original 8-ball (50/25/25)

### 6.2 Technical

- [ ] Plugin loads without errors
- [ ] Plugin subscribes to correct NATS subject
- [ ] Events emitted on successful consultations
- [ ] Hot reload works
- [ ] Test coverage > 90%

### 6.3 Documentation

- [ ] README.md with usage examples
- [ ] All responses documented
- [ ] Configuration options documented

---

## 7. Sample Interactions

```
User: !8ball Will the movie tonight be good?
Rosey: 🎱 "Will the movie tonight be good?" — Signs point to yes. The vibes are immaculate.

User: !8ball Should I have another slice of pizza?
Rosey: 🎱 "Should I have another slice of pizza?" — It is certain. The cosmos smile upon you! ✨

User: !8ball Will I ever find true love?
Rosey: 🎱 "Will I ever find true love?" — Reply hazy, try again. The spirits are being coy today.

User: !8ball Is this bot sentient?
Rosey: 🎱 "Is this bot sentient?" — Better not tell you now. *shakes ball dramatically*
```

---

## 8. Checklist

### Pre-Implementation
- [ ] Review Sortie 1 (dice-roller) for patterns
- [ ] Finalize Rosey personality flavor text
- [ ] Confirm response list is complete

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement response definitions
- [ ] Implement response selector
- [ ] Implement plugin class
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing in chat
- [ ] Verify personality feels right
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add 8ball plugin

- Implement !8ball command with classic 20 responses
- Add Rosey personality flavor text
- Add configurable cooldown per user
- Emit analytics events

Implements: SPEC-Sortie-2-8Ball.md
Related: PRD-Funny-Games.md
```
