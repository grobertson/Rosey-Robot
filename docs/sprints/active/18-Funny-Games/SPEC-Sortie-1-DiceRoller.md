# SPEC: Sortie 1 - Dice Roller Plugin

**Sprint:** 18 - Funny Games  
**Sortie:** 1 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 1-2 days  
**Priority:** HIGH - Foundation plugin, template for others

---

## 1. Overview

### 1.1 Purpose

The Dice Roller plugin is the simplest plugin in Sprint 18, serving as both a useful feature and a **canonical template** for future plugin development. It demonstrates:

- Basic plugin structure and lifecycle
- Command registration via NATS
- Stateless request handling
- Event emission for analytics
- Proper error handling and user feedback

### 1.2 Scope

**In Scope:**
- `!roll` command with dice notation parsing (XdY, XdY+Z, XdY-Z)
- `!flip` command for coin flips
- Event emission for analytics
- Comprehensive test coverage
- Plugin documentation

**Out of Scope:**
- Persistence (stateless plugin)
- Roll history
- Advantage/disadvantage mechanics (future enhancement)
- Custom dice definitions

### 1.3 Dependencies

- NATS client (existing)
- Plugin base class (existing in `lib/plugin/`)
- Event bus (existing)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/dice-roller/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── dice.py               # Dice parsing and rolling logic
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_dice.py      # Unit tests for dice logic
    └── test_plugin.py    # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.dice.roll` | Subscribe | Handle `!roll` commands |
| `rosey.command.dice.flip` | Subscribe | Handle `!flip` commands |
| `dice.rolled` | Publish | Event emitted after each roll |
| `dice.flipped` | Publish | Event emitted after each flip |

### 2.3 Message Schemas

#### Roll Request (incoming)
```json
{
  "channel": "string",
  "user": "string",
  "args": "2d6+5",
  "reply_to": "rosey.reply.abc123"
}
```

#### Roll Response (outgoing)
```json
{
  "success": true,
  "result": {
    "notation": "2d6+5",
    "rolls": [4, 3],
    "modifier": 5,
    "total": 12,
    "formatted": "🎲 [4, 3] + 5 = 12"
  }
}
```

#### Roll Event (published)
```json
{
  "event": "dice.rolled",
  "timestamp": "2025-11-24T12:00:00Z",
  "channel": "string",
  "user": "string",
  "dice_count": 2,
  "dice_sides": 6,
  "modifier": 5,
  "total": 12
}
```

#### Flip Response (outgoing)
```json
{
  "success": true,
  "result": {
    "outcome": "Heads",
    "formatted": "🪙 Heads!"
  }
}
```

### 2.4 Class Design

```python
# plugins/dice-roller/dice.py

import re
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DiceRoll:
    """Result of a dice roll."""
    notation: str
    count: int
    sides: int
    modifier: int
    rolls: List[int]
    total: int

    def format(self) -> str:
        """Format roll result for chat display."""
        ...


class DiceParser:
    """Parse and validate dice notation."""
    
    # Pattern: [count]d<sides>[+/-modifier]
    PATTERN = re.compile(
        r'^(?P<count>\d+)?d(?P<sides>\d+)(?P<modifier>[+-]\d+)?$',
        re.IGNORECASE
    )
    
    # Limits
    MAX_DICE = 20
    MAX_SIDES = 1000
    MAX_MODIFIER = 100
    
    @classmethod
    def parse(cls, notation: str) -> Tuple[int, int, int]:
        """
        Parse dice notation into (count, sides, modifier).
        
        Raises:
            ValueError: If notation is invalid or exceeds limits
        """
        ...
    
    @classmethod
    def validate_limits(cls, count: int, sides: int, modifier: int) -> None:
        """
        Validate roll parameters against limits.
        
        Raises:
            ValueError: If any limit is exceeded
        """
        ...


class DiceRoller:
    """Execute dice rolls."""
    
    def __init__(self, rng: Optional[random.Random] = None):
        """Initialize with optional RNG for testing."""
        self.rng = rng or random.Random()
    
    def roll(self, notation: str) -> DiceRoll:
        """
        Parse notation and execute roll.
        
        Args:
            notation: Dice notation string (e.g., "2d6+5")
            
        Returns:
            DiceRoll with results
            
        Raises:
            ValueError: If notation is invalid
        """
        ...
    
    def flip(self) -> str:
        """
        Flip a coin.
        
        Returns:
            "Heads" or "Tails"
        """
        return self.rng.choice(["Heads", "Tails"])
```

```python
# plugins/dice-roller/plugin.py

from lib.plugin.base import PluginBase
from .dice import DiceRoller, DiceRoll


class DiceRollerPlugin(PluginBase):
    """
    Dice rolling plugin for chat games and decisions.
    
    Commands:
        !roll [notation] - Roll dice using standard notation
        !flip - Flip a coin
    """
    
    NAME = "dice-roller"
    VERSION = "1.0.0"
    DESCRIPTION = "Roll dice and flip coins"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        self.roller = DiceRoller()
    
    async def setup(self) -> None:
        """Register command handlers."""
        await self.subscribe("rosey.command.dice.roll", self._handle_roll)
        await self.subscribe("rosey.command.dice.flip", self._handle_flip)
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup on shutdown."""
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_roll(self, msg) -> None:
        """Handle !roll command."""
        ...
    
    async def _handle_flip(self, msg) -> None:
        """Handle !flip command."""
        ...
    
    async def _emit_roll_event(self, channel: str, user: str, roll: DiceRoll) -> None:
        """Emit dice.rolled event for analytics."""
        ...
    
    async def _emit_flip_event(self, channel: str, user: str, outcome: str) -> None:
        """Emit dice.flipped event for analytics."""
        ...
```

### 2.5 Configuration

```json
{
  "max_dice": 20,
  "max_sides": 1000,
  "max_modifier": 100,
  "cooldown_seconds": 0,
  "emit_events": true
}
```

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/dice-roller/` directory
2. Create `__init__.py` with exports
3. Create `config.json` with defaults
4. Create empty test files

### Step 2: Implement Dice Logic (1.5 hours)

1. Implement `DiceParser.parse()` with regex
2. Implement `DiceParser.validate_limits()`
3. Implement `DiceRoll` dataclass with `format()`
4. Implement `DiceRoller.roll()` and `flip()`
5. Write unit tests for all parsing edge cases

### Step 3: Implement Plugin Class (1.5 hours)

1. Implement `DiceRollerPlugin.__init__()`
2. Implement `setup()` with NATS subscriptions
3. Implement `teardown()` for cleanup
4. Implement `_handle_roll()` with error handling
5. Implement `_handle_flip()`
6. Implement event emission methods

### Step 4: Testing (1 hour)

1. Unit tests for dice parsing (valid/invalid notation)
2. Unit tests for limit validation
3. Integration tests for command handling
4. Test error responses
5. Test event emission

### Step 5: Documentation (30 minutes)

1. Write README.md with usage examples
2. Add docstrings to all public methods
3. Document configuration options

---

## 4. Test Cases

### 4.1 Dice Parsing Tests

| Input | Expected Output | Test Type |
|-------|-----------------|-----------|
| `"2d6"` | (2, 6, 0) | Valid |
| `"d20"` | (1, 20, 0) | Valid (count defaults to 1) |
| `"3d8+5"` | (3, 8, 5) | Valid with positive modifier |
| `"4d10-2"` | (4, 10, -2) | Valid with negative modifier |
| `"D6"` | (1, 6, 0) | Valid (case insensitive) |
| `"100d6"` | ValueError | Exceeds max dice |
| `"2d9999"` | ValueError | Exceeds max sides |
| `"2d6+999"` | ValueError | Exceeds max modifier |
| `"xyz"` | ValueError | Invalid format |
| `""` | ValueError | Empty string |
| `"0d6"` | ValueError | Zero dice |
| `"2d0"` | ValueError | Zero sides |
| `"2d1"` | ValueError | One side (not a die) |

### 4.2 Roll Execution Tests

| Scenario | Validation |
|----------|------------|
| Roll 2d6 | Returns 2 values, each 1-6, sum correct |
| Roll with modifier | Modifier added to sum |
| Roll d20 | Single value 1-20 |
| Deterministic test | Seeded RNG produces expected results |

### 4.3 Command Handling Tests

| Input | Expected Response |
|-------|-------------------|
| `!roll 2d6` | Success with formatted result |
| `!roll` (no args) | Help message |
| `!roll invalid` | Error message with hint |
| `!roll 100d100` | Error: exceeds limits |
| `!flip` | "Heads" or "Tails" |

### 4.4 Event Emission Tests

| Scenario | Event |
|----------|-------|
| Successful roll | `dice.rolled` with correct data |
| Successful flip | `dice.flipped` with outcome |
| Failed roll | No event emitted |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Invalid notation | "❌ Invalid dice notation. Use format: [count]d<sides>[+/-modifier]. Examples: 2d6, d20, 3d8+5" |
| Too many dice | "❌ Maximum 20 dice allowed" |
| Too many sides | "❌ Maximum 1000 sides allowed" |
| Modifier too large | "❌ Modifier must be between -100 and +100" |
| No arguments | "Usage: !roll [count]d<sides>[+/-modifier]. Examples: !roll 2d6, !roll d20+5" |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| NATS timeout | Log error, respond with generic message |
| JSON parse error | Log error, respond with generic message |
| Unexpected exception | Log full traceback, respond gracefully |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!roll 2d6` returns two d6 results and their sum
- [ ] `!roll d20+5` returns d20 result plus 5
- [ ] `!roll` without arguments shows usage help
- [ ] Invalid notation returns helpful error message
- [ ] Limits are enforced (20 dice, 1000 sides, ±100 modifier)
- [ ] `!flip` returns "Heads" or "Tails" with emoji

### 6.2 Technical

- [ ] Plugin loads without errors
- [ ] Plugin subscribes to correct NATS subjects
- [ ] Events emitted on successful rolls/flips
- [ ] Hot reload works (plugin can be reloaded)
- [ ] Test coverage > 90%

### 6.3 Documentation

- [ ] README.md with usage examples
- [ ] All public methods have docstrings
- [ ] Configuration options documented

---

## 7. Future Enhancements (Out of Scope)

These are documented for future sprints:

1. **Advantage/Disadvantage**: Roll twice, take higher/lower
2. **Roll History**: Store last N rolls per user
3. **Named Rolls**: Save roll configurations (`!roll save attack d20+5`)
4. **Statistics**: Track roll distributions per user
5. **Exploding Dice**: Re-roll and add on max value

---

## 8. Checklist

### Pre-Implementation
- [ ] Review existing plugin structure in `lib/plugin/`
- [ ] Confirm NATS message format with existing plugins
- [ ] Set up development environment

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement dice parsing logic
- [ ] Implement dice rolling logic
- [ ] Implement plugin class
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing in chat
- [ ] Code review
- [ ] Documentation complete
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add dice-roller plugin

- Implement !roll command with dice notation parsing
- Implement !flip command for coin flips
- Add event emission for analytics
- Include comprehensive test coverage

Implements: SPEC-Sortie-1-DiceRoller.md
Related: PRD-Funny-Games.md
```
