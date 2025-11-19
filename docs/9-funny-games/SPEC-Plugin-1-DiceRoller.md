# Sprint 9 - Plugin 1: Dice Roller

**Complexity:** ⭐☆☆☆☆ (Simple)  
**Effort:** 3 hours  
**Priority:** Foundation  
**Status:** Specification Complete

## Overview

The Dice Roller plugin provides basic dice rolling functionality using standard RPG notation (e.g., `2d6`, `d20`, `3d8+5`). This is the simplest plugin in Sprint 9, designed to validate the basic plugin lifecycle, command registration, and message sending.

### Purpose

- **User Value:** Fun dice rolling for games, decisions, and randomization
- **Architecture Value:** Validates basic plugin functionality with minimal complexity
- **Learning Value:** Simple example for plugin developers to start with

### Features

- Parse dice notation (XdY+/-Z)
- Roll multiple dice
- Support modifiers (addition/subtraction)
- Display results with breakdown
- Standard dice types (d4, d6, d8, d10, d12, d20, d100)

## Commands

### `!roll [notation]`

Roll dice using standard notation.

**Syntax:**
```
!roll [count]d<sides>[+/-modifier]
```

**Examples:**
```
!roll 2d6          # Roll 2 six-sided dice
🎲 [4, 3] = 7

!roll d20          # Roll 1 twenty-sided dice
🎲 [15] = 15

!roll 3d8+5        # Roll 3 eight-sided dice and add 5
🎲 [6, 2, 8] + 5 = 21

!roll 4d10-2       # Roll 4 ten-sided dice and subtract 2
🎲 [7, 3, 9, 1] - 2 = 18

!roll              # Show help
Usage: !roll [count]d<sides>[+/-modifier]
Examples: !roll 2d6, !roll d20, !roll 3d8+5
```

**Validation:**
- Maximum 20 dice per roll
- Maximum 1000 sides per die
- Modifier range: -100 to +100

**Error Handling:**
```
!roll 100d6        # Too many dice
❌ Maximum 20 dice allowed

!roll 2d9999       # Too many sides
❌ Maximum 1000 sides allowed

!roll xyz          # Invalid notation
❌ Invalid dice notation. Use format: [count]d<sides>[+/-modifier]
```

## Configuration

No configuration required - uses only standard library.

## Implementation

### File Structure

```
plugins/dice_roller/
├── __init__.py
└── plugin.py
```

### Code: `plugins/dice_roller/__init__.py`

```python
"""Dice roller plugin for cytube-bot."""

from .plugin import DiceRollerPlugin

__all__ = ['DiceRollerPlugin']
```

### Code: `plugins/dice_roller/plugin.py`

```python
"""
Dice Roller Plugin

A simple plugin that rolls dice using standard RPG notation.
Supports formats like: 2d6, d20, 3d8+5, 4d10-2
"""

import re
import random
from typing import Optional, Tuple, List

from lib.plugin import Plugin
from lib.channel import Channel
from lib.user import User


class DiceRollerPlugin(Plugin):
    """Plugin for rolling dice with standard RPG notation."""
    
    # Regex pattern for dice notation: [count]d<sides>[+/-modifier]
    DICE_PATTERN = re.compile(
        r'^(?P<count>\d+)?d(?P<sides>\d+)(?P<modifier>[+-]\d+)?$',
        re.IGNORECASE
    )
    
    # Limits to prevent abuse
    MAX_DICE = 20
    MAX_SIDES = 1000
    MAX_MODIFIER = 100
    
    def __init__(self, manager):
        """Initialize the dice roller plugin."""
        super().__init__(manager)
        self.name = "dice_roller"
        self.version = "1.0.0"
        self.description = "Roll dice using standard RPG notation"
        self.author = "cytube-bot"
    
    async def setup(self):
        """Set up the plugin (register commands)."""
        await self.register_command('roll', self._handle_roll)
        self.logger.info(f"Dice Roller plugin loaded")
    
    async def teardown(self):
        """Clean up plugin resources."""
        self.logger.info(f"Dice Roller plugin unloaded")
    
    async def _handle_roll(self, channel: Channel, user: User, args: str):
        """
        Handle the !roll command.
        
        Args:
            channel: The channel where the command was issued
            user: The user who issued the command
            args: The dice notation (e.g., "2d6", "d20", "3d8+5")
        """
        # Show help if no args provided
        if not args.strip():
            await channel.send_message(
                "Usage: !roll [count]d<sides>[+/-modifier]"
            )
            await channel.send_message(
                "Examples: !roll 2d6, !roll d20, !roll 3d8+5"
            )
            return
        
        # Parse dice notation
        parsed = self._parse_dice(args.strip())
        if not parsed:
            await channel.send_message(
                "❌ Invalid dice notation. Use format: [count]d<sides>[+/-modifier]"
            )
            return
        
        count, sides, modifier = parsed
        
        # Validate limits
        if count > self.MAX_DICE:
            await channel.send_message(f"❌ Maximum {self.MAX_DICE} dice allowed")
            return
        
        if sides > self.MAX_SIDES:
            await channel.send_message(f"❌ Maximum {self.MAX_SIDES} sides allowed")
            return
        
        if abs(modifier) > self.MAX_MODIFIER:
            await channel.send_message(
                f"❌ Modifier must be between -{self.MAX_MODIFIER} and +{self.MAX_MODIFIER}"
            )
            return
        
        # Roll the dice!
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier
        
        # Format and send result
        result = self._format_result(rolls, modifier, total)
        await channel.send_message(result)
    
    def _parse_dice(self, notation: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse dice notation into components.
        
        Args:
            notation: Dice notation string (e.g., "2d6", "d20", "3d8+5")
        
        Returns:
            Tuple of (count, sides, modifier) or None if invalid
        
        Examples:
            "2d6"    -> (2, 6, 0)
            "d20"    -> (1, 20, 0)
            "3d8+5"  -> (3, 8, 5)
            "4d10-2" -> (4, 10, -2)
        """
        match = self.DICE_PATTERN.match(notation)
        if not match:
            return None
        
        # Extract components
        count_str = match.group('count')
        sides_str = match.group('sides')
        modifier_str = match.group('modifier')
        
        # Convert to integers with defaults
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        modifier = int(modifier_str) if modifier_str else 0
        
        # Basic validation
        if count < 1 or sides < 2:
            return None
        
        return (count, sides, modifier)
    
    def _format_result(self, rolls: List[int], modifier: int, total: int) -> str:
        """
        Format dice roll result for display.
        
        Args:
            rolls: List of individual die rolls
            modifier: The modifier applied
            total: The final total
        
        Returns:
            Formatted result string
        
        Examples:
            [4, 3], 0, 7     -> "🎲 [4, 3] = 7"
            [6, 2, 8], 5, 21 -> "🎲 [6, 2, 8] + 5 = 21"
            [7, 3], -2, 8    -> "🎲 [7, 3] - 2 = 8"
        """
        # Format roll list
        roll_str = ', '.join(str(r) for r in rolls)
        
        # Build result string
        if modifier == 0:
            return f"🎲 [{roll_str}] = {total}"
        elif modifier > 0:
            return f"🎲 [{roll_str}] + {modifier} = {total}"
        else:
            return f"🎲 [{roll_str}] - {abs(modifier)} = {total}"
```

## Testing Strategy

### Unit Tests

```python
"""Tests for dice roller plugin."""

import pytest
from plugins.dice_roller.plugin import DiceRollerPlugin


def test_parse_dice_basic():
    """Test parsing basic dice notation."""
    plugin = DiceRollerPlugin(None)
    
    # Standard notation
    assert plugin._parse_dice("2d6") == (2, 6, 0)
    assert plugin._parse_dice("d20") == (1, 20, 0)
    assert plugin._parse_dice("1d8") == (1, 8, 0)


def test_parse_dice_with_modifier():
    """Test parsing dice notation with modifiers."""
    plugin = DiceRollerPlugin(None)
    
    # With positive modifier
    assert plugin._parse_dice("3d8+5") == (3, 8, 5)
    assert plugin._parse_dice("2d6+10") == (2, 6, 10)
    
    # With negative modifier
    assert plugin._parse_dice("4d10-2") == (4, 10, -2)
    assert plugin._parse_dice("1d20-5") == (1, 20, -5)


def test_parse_dice_invalid():
    """Test parsing invalid dice notation."""
    plugin = DiceRollerPlugin(None)
    
    # Invalid formats
    assert plugin._parse_dice("xyz") is None
    assert plugin._parse_dice("2d") is None
    assert plugin._parse_dice("d") is None
    assert plugin._parse_dice("2x6") is None
    assert plugin._parse_dice("") is None
    
    # Invalid values
    assert plugin._parse_dice("0d6") is None
    assert plugin._parse_dice("2d1") is None
    assert plugin._parse_dice("2d0") is None


def test_format_result_no_modifier():
    """Test formatting results without modifiers."""
    plugin = DiceRollerPlugin(None)
    
    result = plugin._format_result([4, 3], 0, 7)
    assert result == "🎲 [4, 3] = 7"
    
    result = plugin._format_result([15], 0, 15)
    assert result == "🎲 [15] = 15"


def test_format_result_with_modifier():
    """Test formatting results with modifiers."""
    plugin = DiceRollerPlugin(None)
    
    # Positive modifier
    result = plugin._format_result([6, 2, 8], 5, 21)
    assert result == "🎲 [6, 2, 8] + 5 = 21"
    
    # Negative modifier
    result = plugin._format_result([7, 3, 9, 1], -2, 18)
    assert result == "🎲 [7, 3, 9, 1] - 2 = 18"


@pytest.mark.asyncio
async def test_roll_validation_max_dice(mock_channel, mock_user):
    """Test that rolling too many dice is rejected."""
    plugin = DiceRollerPlugin(None)
    await plugin.setup()
    
    # Try to roll 100 dice (exceeds MAX_DICE=20)
    await plugin._handle_roll(mock_channel, mock_user, "100d6")
    
    # Should send error message
    assert mock_channel.last_message.startswith("❌ Maximum")


@pytest.mark.asyncio
async def test_roll_validation_max_sides(mock_channel, mock_user):
    """Test that dice with too many sides are rejected."""
    plugin = DiceRollerPlugin(None)
    await plugin.setup()
    
    # Try to roll d9999 (exceeds MAX_SIDES=1000)
    await plugin._handle_roll(mock_channel, mock_user, "2d9999")
    
    # Should send error message
    assert mock_channel.last_message.startswith("❌ Maximum")


@pytest.mark.asyncio
async def test_roll_basic(mock_channel, mock_user):
    """Test basic dice rolling functionality."""
    plugin = DiceRollerPlugin(None)
    await plugin.setup()
    
    # Roll 2d6
    await plugin._handle_roll(mock_channel, mock_user, "2d6")
    
    # Should send result message
    message = mock_channel.last_message
    assert message.startswith("🎲")
    assert "=" in message
    
    # Result should be between 2 and 12
    total = int(message.split("=")[-1].strip())
    assert 2 <= total <= 12
```

### Integration Tests

```python
"""Integration tests for dice roller plugin."""

import pytest
from plugins.dice_roller.plugin import DiceRollerPlugin


@pytest.mark.asyncio
async def test_plugin_lifecycle(plugin_manager):
    """Test plugin setup and teardown."""
    plugin = DiceRollerPlugin(plugin_manager)
    
    # Setup
    await plugin.setup()
    assert plugin.name == "dice_roller"
    assert plugin.version == "1.0.0"
    
    # Verify command registered
    assert "roll" in plugin_manager.commands
    
    # Teardown
    await plugin.teardown()


@pytest.mark.asyncio
async def test_roll_command_integration(bot, channel):
    """Test roll command through bot."""
    # Send roll command
    await channel.send_chat("!roll 2d6")
    
    # Wait for response
    response = await channel.wait_for_message(timeout=1.0)
    
    # Verify response format
    assert response.startswith("🎲")
    assert "=" in response
```

### Manual Testing

1. **Basic rolls:**
   ```
   !roll 2d6
   !roll d20
   !roll 1d8
   ```

2. **Rolls with modifiers:**
   ```
   !roll 3d8+5
   !roll 4d10-2
   !roll d20+10
   ```

3. **Edge cases:**
   ```
   !roll d4          # Single die
   !roll 20d6        # Maximum dice
   !roll 1d1000      # Maximum sides
   !roll 1d6+100     # Maximum modifier
   ```

4. **Error cases:**
   ```
   !roll 100d6       # Too many dice
   !roll 2d9999      # Too many sides
   !roll xyz         # Invalid notation
   !roll             # No args (help)
   ```

5. **Hot reload test:**
   - Edit plugin.py (change MAX_DICE constant)
   - Save file
   - Verify plugin reloads automatically
   - Test new limit

## Architecture Validation

This plugin validates:

- ✅ **Plugin base class:** Extends `Plugin` correctly
- ✅ **Lifecycle hooks:** Implements `setup()` and `teardown()`
- ✅ **Command registration:** Uses `register_command()`
- ✅ **Message sending:** Uses `channel.send_message()`
- ✅ **Logging:** Uses `self.logger`
- ✅ **Hot reload:** File changes trigger automatic reload
- ✅ **Error handling:** Validates input and handles errors gracefully

## Implementation Steps

### Step 1: Create Plugin Structure (15 minutes)

1. Create directory: `plugins/dice_roller/`
2. Create `__init__.py` (export plugin class)
3. Create `plugin.py` (main plugin code)

### Step 2: Implement Plugin Class (1 hour)

1. Define `DiceRollerPlugin` class
2. Implement `__init__()` (set metadata)
3. Implement `setup()` (register command)
4. Implement `teardown()` (cleanup)

### Step 3: Implement Dice Logic (1 hour)

1. Define regex pattern for dice notation
2. Implement `_parse_dice()` method
3. Implement `_handle_roll()` command handler
4. Implement `_format_result()` method
5. Add validation (max dice, max sides)

### Step 4: Testing (45 minutes)

1. Write unit tests for parsing
2. Write unit tests for formatting
3. Write integration tests
4. Manual testing
5. Hot reload testing

**Total:** ~3 hours

## User Documentation

### Getting Started

The Dice Roller plugin adds dice rolling to your channel using standard RPG notation.

**Basic usage:**
```
!roll 2d6    # Roll two six-sided dice
!roll d20    # Roll one twenty-sided die
!roll 3d8+5  # Roll three eight-sided dice and add 5
```

### Supported Notation

- **Count:** Number of dice to roll (1-20)
- **Sides:** Number of sides per die (2-1000)
- **Modifier:** Value to add or subtract (-100 to +100)

**Format:** `[count]d<sides>[+/-modifier]`

If count is omitted, it defaults to 1 (e.g., `d20` rolls one d20).

### Common Dice Types

- `d4` - Four-sided die
- `d6` - Six-sided die (standard)
- `d8` - Eight-sided die
- `d10` - Ten-sided die
- `d12` - Twelve-sided die
- `d20` - Twenty-sided die (D&D)
- `d100` - Hundred-sided die (percentile)

### Examples

**Basic rolls:**
- `!roll d6` - Roll a single d6
- `!roll 2d6` - Roll 2d6 (like board games)
- `!roll 3d6` - Roll 3d6 (character stats)

**Combat rolls (D&D):**
- `!roll d20+5` - Attack roll with +5 bonus
- `!roll 2d6+3` - Damage roll
- `!roll d20-2` - Attack with -2 penalty

**Ability checks:**
- `!roll d20+7` - Skill check
- `!roll d20+0` - Unmodified roll

## Design Decisions

### Why Regex for Parsing?

- **Simple:** Dice notation is well-defined and simple
- **Efficient:** Single regex match is fast
- **Standard:** Uses standard Python `re` module
- **Readable:** Pattern clearly shows expected format

Alternative (recursive descent parser) would be overkill for this simple grammar.

### Why Random Module?

- **Standard library:** No external dependencies
- **Sufficient:** Quality is good enough for games
- **Fast:** Very low overhead
- **Simple:** `random.randint()` is straightforward

Not using `secrets` module since cryptographic randomness is unnecessary for dice rolls.

### Why Limits?

- **Prevent abuse:** Users can't spam 1000000d1000000
- **Performance:** Keep response times reasonable
- **UX:** Results must fit in chat messages

Limits chosen based on common use cases:
- 20 dice covers most RPG scenarios
- 1000 sides covers specialty dice (d100, d1000)
- ±100 modifier covers typical game bonuses

### Why Emoji?

- **Visual:** 🎲 makes dice rolls stand out in chat
- **Fun:** Adds personality to bot
- **Universal:** Dice emoji is widely supported

## Dependencies

**None!** This plugin uses only Python standard library:
- `re` - Regular expressions
- `random` - Random number generation
- `typing` - Type hints

No external packages required.

## Performance Considerations

- **Fast:** Regex parsing + random generation < 1ms
- **Memory:** Minimal (only stores roll results temporarily)
- **Thread-safe:** Each roll is independent
- **Async:** Command handler is async (non-blocking)

## Security Considerations

- **Input validation:** Regex prevents code injection
- **Resource limits:** Max dice/sides prevents DoS
- **No storage:** No persistent data to secure
- **No network:** No external API calls

## Future Enhancements

Not in scope for Sprint 9, but potential additions:

1. **Advantage/Disadvantage** (D&D 5e):
   ```
   !roll d20 adv    # Roll twice, take higher
   !roll d20 dis    # Roll twice, take lower
   ```

2. **Roll history per user:**
   - Store last N rolls per user
   - Allow re-rolling previous roll

3. **Named rolls:**
   ```
   !roll save d20+5    # Save roll result with label
   !roll recall save   # Show previous "save" roll
   ```

4. **Statistics:**
   - Track total rolls
   - Average results
   - Distribution graphs

5. **Custom dice:**
   - Named dice sets (e.g., "fireball" = "8d6")
   - Per-channel custom dice

## Conclusion

The Dice Roller plugin is a simple, focused plugin that:

- ✅ Provides useful functionality (dice rolling)
- ✅ Validates basic plugin architecture
- ✅ Serves as beginner-friendly example
- ✅ Has zero external dependencies
- ✅ Is fast and secure

Perfect foundation for Sprint 9!

---

**Estimated Implementation:** 3 hours  
**Lines of Code:** ~150  
**External Dependencies:** None  
**Architecture Features Validated:** 6/16
