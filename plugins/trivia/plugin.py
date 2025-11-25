"""
Trivia Plugin

Interactive trivia game plugin using the Open Trivia Database.

Commands:
    !trivia start [N] - Start game with N questions (default 10)
    !trivia stop - End current game
    !trivia answer <answer> / !a <answer> - Submit answer
    !trivia skip - Skip current question

NATS Subjects:
    Subscribe:
        rosey.command.trivia.start - Handle !trivia start
        rosey.command.trivia.stop - Handle !trivia stop
        rosey.command.trivia.answer - Handle !trivia answer / !a
        rosey.command.trivia.skip - Handle !trivia skip
    Publish:
        trivia.game.started - Event when game starts
        trivia.question.asked - Event when question posed
        trivia.answer.correct - Event when correct answer
        trivia.answer.incorrect - Event when wrong answer
        trivia.question.timeout - Event when time expires
        trivia.question.skipped - Event when question skipped
        trivia.game.ended - Event when game ends
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = Any

from .game import GameConfig, GameState, TriviaGame
from .question import Answer, Question
from .providers.opentdb import OpenTDBProvider

logger = logging.getLogger(__name__)


class TriviaPlugin:
    """
    Trivia game plugin.

    Manages trivia games per channel. Each channel can have one
    active game at a time.

    Commands:
        !trivia start [N] - Start game with N questions (default 10)
        !trivia stop - End current game
        !trivia answer <answer> / !a <answer> - Submit answer
        !trivia skip - Skip current question
    """

    # Plugin metadata
    NAMESPACE = "trivia"
    VERSION = "1.0.0"
    DESCRIPTION = "Interactive trivia game"

    # NATS subjects - Commands
    SUBJECT_START = "rosey.command.trivia.start"
    SUBJECT_STOP = "rosey.command.trivia.stop"
    SUBJECT_ANSWER = "rosey.command.trivia.answer"
    SUBJECT_SKIP = "rosey.command.trivia.skip"

    # NATS subjects - Events
    EVENT_GAME_STARTED = "trivia.game.started"
    EVENT_QUESTION_ASKED = "trivia.question.asked"
    EVENT_ANSWER_CORRECT = "trivia.answer.correct"
    EVENT_ANSWER_INCORRECT = "trivia.answer.incorrect"
    EVENT_QUESTION_TIMEOUT = "trivia.question.timeout"
    EVENT_QUESTION_SKIPPED = "trivia.question.skipped"
    EVENT_GAME_ENDED = "trivia.game.ended"

    # Help text
    START_USAGE = "Usage: !trivia start [number_of_questions]"
    ANSWER_USAGE = "Usage: !a <your answer>"

    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        """
        Initialize trivia plugin.

        Args:
            nats_client: Connected NATS client
            config: Plugin configuration dict
        """
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.NAMESPACE}")
        self._initialized = False
        self._subscriptions: List[Any] = []

        # Question provider
        self.provider = OpenTDBProvider()

        # Active games by channel
        self.active_games: Dict[str, TriviaGame] = {}

        # Load configuration with defaults
        self.default_questions = self.config.get("default_questions", 10)
        self.max_questions = self.config.get("max_questions", 50)
        self.time_per_question = self.config.get("time_per_question", 30)
        self.start_delay = self.config.get("start_delay", 5)
        self.between_questions = self.config.get("between_questions", 3)
        self.points_decay = self.config.get("points_decay", True)
        self.emit_events = self.config.get("emit_events", True)

    async def initialize(self) -> None:
        """
        Initialize plugin and subscribe to NATS subjects.
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")

        # Subscribe to commands
        sub_start = await self.nats.subscribe(
            self.SUBJECT_START, cb=self._handle_start
        )
        self._subscriptions.append(sub_start)

        sub_stop = await self.nats.subscribe(
            self.SUBJECT_STOP, cb=self._handle_stop
        )
        self._subscriptions.append(sub_stop)

        sub_answer = await self.nats.subscribe(
            self.SUBJECT_ANSWER, cb=self._handle_answer
        )
        self._subscriptions.append(sub_answer)

        sub_skip = await self.nats.subscribe(
            self.SUBJECT_SKIP, cb=self._handle_skip
        )
        self._subscriptions.append(sub_skip)

        self._initialized = True
        self.logger.info(
            f"Plugin initialized. Subscribed to: "
            f"{self.SUBJECT_START}, {self.SUBJECT_STOP}, "
            f"{self.SUBJECT_ANSWER}, {self.SUBJECT_SKIP}"
        )

    async def shutdown(self) -> None:
        """
        Shutdown plugin and cleanup.
        """
        self.logger.info(f"Shutting down {self.NAMESPACE} plugin")

        # Stop all active games
        for channel, game in list(self.active_games.items()):
            try:
                await game.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping game in {channel}: {e}")
        self.active_games.clear()

        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.warning(f"Error unsubscribing: {e}")
        self._subscriptions.clear()

        # Close provider
        await self.provider.close()

        self._initialized = False
        self.logger.info(f"Plugin shutdown complete")

    # =========================================================================
    # NATS Command Handlers
    # =========================================================================

    async def _handle_start(self, msg) -> None:
        """
        Handle !trivia start [N] command.

        Expected message format:
            {
                "channel": "string",
                "user": "string",
                "args": "10"
            }
        """
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            if msg.reply:
                await self._respond(msg, {"success": False, "error": "Invalid message"})
            return

        channel = data.get("channel", "unknown")
        user = data.get("user", "unknown")
        args = data.get("args", "").strip()

        # Check for existing game
        if channel in self.active_games:
            game = self.active_games[channel]
            if game.is_active:
                if msg.reply:
                    await self._respond(msg, {
                        "success": False,
                        "error": "A game is already in progress! Use !trivia stop to end it.",
                    })
                return

        # Parse number of questions
        num_questions = self.default_questions
        if args:
            try:
                num_questions = int(args)
                num_questions = max(1, min(self.max_questions, num_questions))
            except ValueError:
                pass

        # Fetch questions
        try:
            questions = await self.provider.fetch_questions(num_questions)
        except Exception as e:
            self.logger.error(f"Failed to fetch questions: {e}")
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": "Couldn't fetch trivia questions. Try again later.",
                })
            return

        if not questions:
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": "No questions available. Try again later.",
                })
            return

        # Create game config
        config = GameConfig(
            num_questions=len(questions),
            time_per_question=self.time_per_question,
            start_delay=self.start_delay,
            between_questions=self.between_questions,
            points_decay=self.points_decay,
        )

        # Create game
        game = TriviaGame(
            game_id=str(uuid.uuid4()),
            channel=channel,
            config=config,
            questions=questions,
            on_question=lambda g, q: self._on_question(g, q),
            on_answer=lambda g, a: self._on_answer(g, a),
            on_timeout=lambda g, q: self._on_timeout(g, q),
            on_end=lambda g: self._on_game_end(g),
        )

        self.active_games[channel] = game

        # Start game
        await game.start()

        # Respond
        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {
                    "game_id": game.game_id,
                    "questions": len(questions),
                    "time_per_question": config.time_per_question,
                    "message": (
                        f"🎯 Trivia starting! {len(questions)} questions, "
                        f"{config.time_per_question} seconds each.\n"
                        f"First question in {config.start_delay} seconds..."
                    ),
                },
            })

        # Emit event
        if self.emit_events:
            await self._emit_event(self.EVENT_GAME_STARTED, {
                "channel": channel,
                "game_id": game.game_id,
                "started_by": user,
                "num_questions": len(questions),
            })

    async def _handle_stop(self, msg) -> None:
        """Handle !trivia stop command."""
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            return

        channel = data.get("channel", "unknown")
        user = data.get("user", "unknown")

        game = self.active_games.get(channel)
        if not game or not game.is_active:
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": "No active game to stop.",
                })
            return

        # Stop the game
        await game.stop(ended_by=user)

        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {"message": f"⏹️ Game stopped by {user}."},
            })

    async def _handle_answer(self, msg) -> None:
        """Handle !trivia answer <answer> / !a <answer> command."""
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            return

        channel = data.get("channel", "unknown")
        user = data.get("user", "unknown")
        answer = data.get("args", "").strip()

        if not answer:
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": self.ANSWER_USAGE,
                })
            return

        game = self.active_games.get(channel)
        if not game or game.state != GameState.QUESTION_ACTIVE:
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": "No active question to answer!",
                })
            return

        # Submit answer
        result = await game.submit_answer(user, answer)

        # Response handled by game callback
        if result and msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {
                    "correct": result.correct,
                    "user": result.user,
                    "answer": result.answer,
                    "points": result.points_awarded,
                    "time_taken": result.timestamp,
                },
            })

    async def _handle_skip(self, msg) -> None:
        """Handle !trivia skip command."""
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            return

        channel = data.get("channel", "unknown")

        game = self.active_games.get(channel)
        if not game or game.state != GameState.QUESTION_ACTIVE:
            if msg.reply:
                await self._respond(msg, {
                    "success": False,
                    "error": "No active question to skip!",
                })
            return

        # Reveal answer before skipping
        if game.current_question:
            await self._send_to_channel(
                channel,
                f"⏭️ Skipped! {game.current_question.format_answer_reveal()}",
            )

            # Emit skip event
            if self.emit_events:
                await self._emit_event(self.EVENT_QUESTION_SKIPPED, {
                    "channel": channel,
                    "game_id": game.game_id,
                    "question_number": game.current_question_index + 1,
                })

        await game.skip_question()

        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {"message": "Question skipped."},
            })

    # =========================================================================
    # Game Callbacks
    # =========================================================================

    async def _on_question(self, game: TriviaGame, question: Question) -> None:
        """Called when a new question is asked."""
        formatted = question.format_for_display()
        index = game.current_question_index + 1
        total = len(game.questions)

        message = (
            f"📝 Question {index}/{total} "
            f"({question.difficulty.value.title()} - {question.category}):\n\n"
            f"{formatted}\n\n"
            f"⏱️ {game.config.time_per_question} seconds! Use !a <answer>"
        )

        await self._send_to_channel(game.channel, message)

        if self.emit_events:
            await self._emit_event(self.EVENT_QUESTION_ASKED, {
                "channel": game.channel,
                "game_id": game.game_id,
                "question_number": index,
                "difficulty": question.difficulty.value,
                "category": question.category,
            })

    async def _on_answer(self, game: TriviaGame, answer: Answer) -> None:
        """Called when someone submits an answer."""
        if answer.correct:
            message = (
                f"✅ Correct! {answer.user} got it in "
                f"{answer.timestamp:.1f}s! (+{answer.points_awarded} points)"
            )
            event = self.EVENT_ANSWER_CORRECT
        else:
            message = f"❌ {answer.user} - that's not it!"
            event = self.EVENT_ANSWER_INCORRECT

        await self._send_to_channel(game.channel, message)

        if self.emit_events:
            await self._emit_event(event, {
                "channel": game.channel,
                "game_id": game.game_id,
                "user": answer.user,
                "correct": answer.correct,
                "points": answer.points_awarded,
                "time_taken": answer.timestamp,
            })

    async def _on_timeout(self, game: TriviaGame, question: Question) -> None:
        """Called when question times out."""
        message = f"⏰ Time's up! {question.format_answer_reveal()}"
        await self._send_to_channel(game.channel, message)

        if self.emit_events:
            await self._emit_event(self.EVENT_QUESTION_TIMEOUT, {
                "channel": game.channel,
                "game_id": game.game_id,
                "question_number": game.current_question_index + 1,
                "correct_answer": question.correct_answer,
            })

    async def _on_game_end(self, game: TriviaGame) -> None:
        """Called when game ends."""
        leaderboard = game.get_leaderboard()

        if leaderboard:
            lines = ["🏆 Game Over!\n"]
            medals = ["🥇", "🥈", "🥉"]

            for i, player in enumerate(leaderboard[:10]):
                medal = medals[i] if i < len(medals) else f"{i + 1}."
                lines.append(f"{medal} {player.user} - {player.score} points")

            message = "\n".join(lines)
        else:
            message = "🏆 Game Over! No one scored any points."

        await self._send_to_channel(game.channel, message)

        if self.emit_events:
            await self._emit_event(self.EVENT_GAME_ENDED, {
                "channel": game.channel,
                "game_id": game.game_id,
                "scores": [
                    {"user": p.user, "score": p.score, "correct": p.correct_answers}
                    for p in leaderboard
                ],
                "questions_asked": game.current_question_index + 1,
            })

        # Cleanup
        if game.channel in self.active_games:
            del self.active_games[game.channel]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _respond(self, msg, data: Dict[str, Any]) -> None:
        """Send JSON response to NATS message."""
        try:
            await msg.respond(json.dumps(data).encode())
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

    async def _send_to_channel(self, channel: str, message: str) -> None:
        """
        Send a message to a channel via NATS.

        This publishes to the channel's message subject for the
        router/connector to pick up and send to the actual channel.
        """
        try:
            await self.nats.publish(
                f"rosey.channel.{channel}.message",
                json.dumps({"channel": channel, "message": message}).encode(),
            )
        except Exception as e:
            self.logger.error(f"Error sending to channel {channel}: {e}")

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a NATS event."""
        event_data = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        try:
            await self.nats.publish(event_type, json.dumps(event_data).encode())
        except Exception as e:
            self.logger.debug(f"Could not publish event {event_type}: {e}")
