"""
Dice parsing and rolling logic.

This module provides:
- DiceParser: Parse and validate dice notation (e.g., "2d6+5")
- DiceRoll: Dataclass representing a roll result
- DiceRoller: Execute dice rolls and coin flips
"""

import re
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DiceRoll:
    """
    Result of a dice roll.

    Attributes:
        notation: Original dice notation string
        count: Number of dice rolled
        sides: Number of sides per die
        modifier: Modifier added to total (can be negative)
        rolls: List of individual die results
        total: Final total (sum of rolls + modifier)
    """

    notation: str
    count: int
    sides: int
    modifier: int
    rolls: List[int]
    total: int

    def format(self) -> str:
        """
        Format roll result for chat display.

        Returns:
            Formatted string with emoji, rolls, modifier, and total.

        Examples:
            "🎲 [4, 3] = 7"
            "🎲 [17] + 5 = 22"
            "🎲 [6, 4, 3, 2] - 2 = 13"
        """
        # Format the rolls
        if len(self.rolls) == 1:
            rolls_str = f"[{self.rolls[0]}]"
        else:
            rolls_str = f"[{', '.join(str(r) for r in self.rolls)}]"

        # Format modifier
        if self.modifier > 0:
            modifier_str = f" + {self.modifier}"
        elif self.modifier < 0:
            modifier_str = f" - {abs(self.modifier)}"
        else:
            modifier_str = ""

        return f"🎲 {rolls_str}{modifier_str} = {self.total}"


class DiceParser:
    """
    Parse and validate dice notation.

    Supports standard notation: [count]d<sides>[+/-modifier]

    Examples:
        - "2d6" -> 2 six-sided dice
        - "d20" -> 1 twenty-sided die (count defaults to 1)
        - "3d8+5" -> 3 eight-sided dice plus 5
        - "4d10-2" -> 4 ten-sided dice minus 2

    Limits (configurable):
        - max_dice: Maximum number of dice (default 20)
        - max_sides: Maximum sides per die (default 1000)
        - max_modifier: Maximum absolute modifier value (default 100)
    """

    # Pattern: [count]d<sides>[+/-modifier]
    # Groups: count (optional), sides (required), modifier (optional)
    PATTERN = re.compile(
        r"^(?P<count>\d+)?d(?P<sides>\d+)(?P<modifier>[+-]\d+)?$", re.IGNORECASE
    )

    # Default limits
    DEFAULT_MAX_DICE = 20
    DEFAULT_MAX_SIDES = 1000
    DEFAULT_MAX_MODIFIER = 100

    def __init__(
        self,
        max_dice: int = DEFAULT_MAX_DICE,
        max_sides: int = DEFAULT_MAX_SIDES,
        max_modifier: int = DEFAULT_MAX_MODIFIER,
    ):
        """
        Initialize parser with limits.

        Args:
            max_dice: Maximum number of dice allowed
            max_sides: Maximum sides per die allowed
            max_modifier: Maximum absolute modifier value allowed
        """
        self.max_dice = max_dice
        self.max_sides = max_sides
        self.max_modifier = max_modifier

    def parse(self, notation: str) -> Tuple[int, int, int]:
        """
        Parse dice notation into (count, sides, modifier).

        Args:
            notation: Dice notation string (e.g., "2d6+5")

        Returns:
            Tuple of (count, sides, modifier)

        Raises:
            ValueError: If notation is invalid or exceeds limits
        """
        if not notation or not notation.strip():
            raise ValueError("Dice notation cannot be empty")

        notation = notation.strip()
        match = self.PATTERN.match(notation)

        if not match:
            raise ValueError(
                f"Invalid dice notation: '{notation}'. "
                "Use format: [count]d<sides>[+/-modifier]. "
                "Examples: 2d6, d20, 3d8+5"
            )

        # Extract groups
        count_str = match.group("count")
        sides_str = match.group("sides")
        modifier_str = match.group("modifier")

        # Parse values
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        modifier = int(modifier_str) if modifier_str else 0

        # Validate
        self._validate_limits(count, sides, modifier)

        return count, sides, modifier

    def _validate_limits(self, count: int, sides: int, modifier: int) -> None:
        """
        Validate roll parameters against limits.

        Args:
            count: Number of dice
            sides: Sides per die
            modifier: Modifier value

        Raises:
            ValueError: If any limit is exceeded
        """
        if count < 1:
            raise ValueError("Must roll at least 1 die")

        if count > self.max_dice:
            raise ValueError(f"Maximum {self.max_dice} dice allowed")

        if sides < 2:
            raise ValueError("Dice must have at least 2 sides")

        if sides > self.max_sides:
            raise ValueError(f"Maximum {self.max_sides} sides allowed")

        if abs(modifier) > self.max_modifier:
            raise ValueError(
                f"Modifier must be between -{self.max_modifier} and +{self.max_modifier}"
            )


class DiceRoller:
    """
    Execute dice rolls and coin flips.

    Uses a configurable random number generator for testability.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        parser: Optional[DiceParser] = None,
    ):
        """
        Initialize roller.

        Args:
            rng: Random number generator (defaults to system RNG)
            parser: Dice parser (defaults to DiceParser with default limits)
        """
        self.rng = rng or random.Random()
        self.parser = parser or DiceParser()

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
        count, sides, modifier = self.parser.parse(notation)

        # Roll the dice
        rolls = [self.rng.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier

        return DiceRoll(
            notation=notation.strip(),
            count=count,
            sides=sides,
            modifier=modifier,
            rolls=rolls,
            total=total,
        )

    def flip(self) -> str:
        """
        Flip a coin.

        Returns:
            "Heads" or "Tails"
        """
        return self.rng.choice(["Heads", "Tails"])

    def format_flip(self, outcome: str) -> str:
        """
        Format flip result for chat display.

        Args:
            outcome: "Heads" or "Tails"

        Returns:
            Formatted string with coin emoji
        """
        return f"🪙 {outcome}!"
