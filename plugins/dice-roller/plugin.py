"""
Dice Roller Plugin

A simple stateless plugin for rolling dice and flipping coins in chat.
Serves as a canonical template for future plugin development.

This plugin runs as a separate process and communicates entirely via NATS.

Commands:
    !roll [notation] - Roll dice using standard notation
    !flip - Flip a coin

NATS Subjects:
    Subscribe:
        rosey.command.dice.roll - Handle !roll commands
        rosey.command.dice.flip - Handle !flip commands
    Publish:
        rosey.event.dice.rolled - Event emitted after each roll
        rosey.event.dice.flipped - Event emitted after each flip
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from nats.aio.client import Client as NATS
except ImportError:
    # Allow imports for type checking even if nats-py not installed
    NATS = Any

try:
    from .dice import DiceParser, DiceRoll, DiceRoller
except ImportError:
    from dice import DiceParser, DiceRoll, DiceRoller

logger = logging.getLogger(__name__)


class DiceRollerPlugin:
    """
    Dice rolling plugin for chat games and decisions.

    This plugin communicates entirely via NATS messaging:
    - Subscribes to command subjects for !roll and !flip
    - Publishes events for analytics
    - Uses request/reply pattern for command responses

    Commands:
        !roll [notation] - Roll dice using standard notation
        !flip - Flip a coin

    Examples:
        !roll 2d6      -> 🎲 [4, 3] = 7
        !roll d20+5    -> 🎲 [17] + 5 = 22
        !roll 4d6-2    -> 🎲 [6, 4, 3, 2] - 2 = 13
        !flip          -> 🪙 Heads!
    """

    # Plugin metadata
    NAMESPACE = "dice-roller"
    VERSION = "1.0.0"
    DESCRIPTION = "Roll dice and flip coins"

    # NATS subjects
    SUBJECT_ROLL = "rosey.command.dice.roll"
    SUBJECT_FLIP = "rosey.command.dice.flip"
    EVENT_ROLLED = "rosey.event.dice.rolled"
    EVENT_FLIPPED = "rosey.event.dice.flipped"

    # Help text
    ROLL_USAGE = (
        "Usage: !roll [count]d<sides>[+/-modifier]\n"
        "Examples: !roll 2d6, !roll d20, !roll 3d8+5, !roll 4d10-2"
    )

    # Defaults
    DEFAULT_NATS_TIMEOUT = 2.0  # seconds

    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        """
        Initialize dice roller plugin.

        Args:
            nats_client: Connected NATS client for messaging
            config: Plugin configuration dict
        """
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.NAMESPACE}")
        self._initialized = False
        self._subscriptions: List[Any] = []

        # Load configuration with defaults
        max_dice = self.config.get("max_dice", DiceParser.DEFAULT_MAX_DICE)
        max_sides = self.config.get("max_sides", DiceParser.DEFAULT_MAX_SIDES)
        max_modifier = self.config.get("max_modifier", DiceParser.DEFAULT_MAX_MODIFIER)
        self.emit_events = self.config.get("emit_events", True)

        # Create parser with configured limits
        parser = DiceParser(
            max_dice=max_dice,
            max_sides=max_sides,
            max_modifier=max_modifier,
        )

        # Create roller with parser
        self.roller = DiceRoller(parser=parser)

    async def initialize(self) -> None:
        """
        Initialize plugin and subscribe to NATS subjects.

        This sets up the command handlers for !roll and !flip.
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")

        # Subscribe to roll commands
        sub_roll = await self.nats.subscribe(
            self.SUBJECT_ROLL, cb=self._handle_roll
        )
        self._subscriptions.append(sub_roll)

        # Subscribe to flip commands
        sub_flip = await self.nats.subscribe(
            self.SUBJECT_FLIP, cb=self._handle_flip
        )
        self._subscriptions.append(sub_flip)

        self._initialized = True
        self.logger.info(
            f"Plugin initialized. Subscribed to: "
            f"{self.SUBJECT_ROLL}, {self.SUBJECT_FLIP}"
        )

    async def shutdown(self) -> None:
        """
        Shutdown plugin and cleanup subscriptions.
        """
        self.logger.info(f"Shutting down {self.NAMESPACE} plugin")

        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.warning(f"Error unsubscribing: {e}")

        self._subscriptions.clear()
        self._initialized = False
        self.logger.info("Plugin shutdown complete")

    def _ensure_initialized(self) -> None:
        """Raise error if plugin not initialized."""
        if not self._initialized:
            raise RuntimeError(
                f"{self.NAMESPACE} plugin not initialized. "
                "Call initialize() before using methods."
            )

    # =========================================================================
    # NATS Command Handlers
    # =========================================================================

    async def _handle_roll(self, msg) -> None:
        """
        Handle !roll command from NATS.

        Expected message format:
            {
                "channel": "string",
                "user": "string",
                "args": "2d6+5"
            }

        Response format:
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
        """
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            if msg.reply:
                await self._respond(msg, {"success": False, "error": "Invalid message format"})
            return

        channel = data.get("channel", "unknown")
        user = data.get("user", "unknown")
        args = data.get("args", "").strip()

        # Process the roll
        response = await self._process_roll(channel, user, args)

        # Respond if reply subject provided
        if msg.reply:
            await self._respond(msg, response)

    async def _handle_flip(self, msg) -> None:
        """
        Handle !flip command from NATS.

        Expected message format:
            {
                "channel": "string",
                "user": "string"
            }

        Response format:
            {
                "success": true,
                "result": {
                    "outcome": "Heads",
                    "formatted": "🪙 Heads!"
                }
            }
        """
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            if msg.reply:
                await self._respond(msg, {"success": False, "error": "Invalid message format"})
            return

        channel = data.get("channel", "unknown")
        user = data.get("user", "unknown")

        # Process the flip
        response = await self._process_flip(channel, user)

        # Respond if reply subject provided
        if msg.reply:
            await self._respond(msg, response)

    async def _respond(self, msg, data: Dict[str, Any]) -> None:
        """Send JSON response to NATS message."""
        try:
            await msg.respond(json.dumps(data).encode())
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

    # =========================================================================
    # Core Logic
    # =========================================================================

    async def _process_roll(
        self, channel: str, user: str, notation: str
    ) -> Dict[str, Any]:
        """
        Process a dice roll request.

        Args:
            channel: Channel where command was issued
            user: User who issued command
            notation: Dice notation string

        Returns:
            Response dict with success status and result or error
        """
        # No notation provided - show usage
        if not notation:
            return {
                "success": False,
                "error": self.ROLL_USAGE,
            }

        try:
            # Execute the roll
            roll = self.roller.roll(notation)

            # Emit event
            if self.emit_events:
                await self._emit_roll_event(channel, user, roll)

            # Return success response
            return {
                "success": True,
                "result": {
                    "notation": roll.notation,
                    "rolls": roll.rolls,
                    "modifier": roll.modifier,
                    "total": roll.total,
                    "formatted": roll.format(),
                },
            }

        except ValueError as e:
            self.logger.debug(f"Roll error for '{notation}': {e}")
            return {
                "success": False,
                "error": f"❌ {str(e)}",
            }

    async def _process_flip(self, channel: str, user: str) -> Dict[str, Any]:
        """
        Process a coin flip request.

        Args:
            channel: Channel where command was issued
            user: User who issued command

        Returns:
            Response dict with success status and result
        """
        # Execute the flip
        outcome = self.roller.flip()
        formatted = self.roller.format_flip(outcome)

        # Emit event
        if self.emit_events:
            await self._emit_flip_event(channel, user, outcome)

        return {
            "success": True,
            "result": {
                "outcome": outcome,
                "formatted": formatted,
            },
        }

    # =========================================================================
    # Event Emission
    # =========================================================================

    async def _emit_roll_event(self, channel: str, user: str, roll: DiceRoll) -> None:
        """
        Emit dice.rolled event for analytics.

        Args:
            channel: Channel where roll occurred
            user: User who rolled
            roll: DiceRoll result
        """
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "user": user,
            "dice_count": roll.count,
            "dice_sides": roll.sides,
            "modifier": roll.modifier,
            "rolls": roll.rolls,
            "total": roll.total,
        }

        try:
            await self.nats.publish(
                self.EVENT_ROLLED, json.dumps(event_data).encode()
            )
        except Exception as e:
            self.logger.debug(f"Could not publish roll event: {e}")

    async def _emit_flip_event(self, channel: str, user: str, outcome: str) -> None:
        """
        Emit dice.flipped event for analytics.

        Args:
            channel: Channel where flip occurred
            user: User who flipped
            outcome: "Heads" or "Tails"
        """
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "user": user,
            "outcome": outcome,
        }

        try:
            await self.nats.publish(
                self.EVENT_FLIPPED, json.dumps(event_data).encode()
            )
        except Exception as e:
            self.logger.debug(f"Could not publish flip event: {e}")

    # =========================================================================
    # Direct API (for testing or direct usage)
    # =========================================================================

    def roll(self, notation: str) -> DiceRoll:
        """
        Roll dice directly (synchronous).

        Args:
            notation: Dice notation string (e.g., "2d6+5")

        Returns:
            DiceRoll result

        Raises:
            ValueError: If notation is invalid
        """
        return self.roller.roll(notation)

    def flip(self) -> str:
        """
        Flip a coin directly (synchronous).

        Returns:
            "Heads" or "Tails"
        """
        return self.roller.flip()
