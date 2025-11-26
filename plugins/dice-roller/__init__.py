"""
Dice Roller Plugin

Roll dice and flip coins in chat.

Commands:
    !roll [notation] - Roll dice using standard notation (e.g., 2d6, d20+5)
    !flip - Flip a coin

Example usage:
    !roll 2d6      -> 🎲 [4, 3] = 7
    !roll d20+5    -> 🎲 [17] + 5 = 22
    !roll 4d6-2    -> 🎲 [6, 4, 3, 2] - 2 = 13
    !flip          -> 🪙 Heads!
"""

try:
    # When imported as a package
    from .plugin import DiceRollerPlugin
    from .dice import DiceParser, DiceRoll, DiceRoller
except ImportError:
    # When imported directly (e.g., from tests)
    from plugin import DiceRollerPlugin  # type: ignore[no-redef]
    from dice import DiceParser, DiceRoll, DiceRoller  # type: ignore[no-redef]

__all__ = ["DiceRollerPlugin", "DiceParser", "DiceRoll", "DiceRoller"]
__version__ = "1.0.0"
