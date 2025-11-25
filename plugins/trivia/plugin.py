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
from .storage import TriviaStorage, GameRecord
from .achievements import AchievementChecker, Achievement, GameResult

logger = logging.getLogger(__name__)


class TriviaPlugin:
    """
    Trivia game plugin.

    Manages trivia games per channel. Each channel can have one
    active game at a time.

    Commands:
        !trivia start [N] [category] - Start game with N questions (default 10)
        !trivia stop - End current game
        !trivia answer <answer> / !a <answer> - Submit answer
        !trivia skip - Skip current question
        !trivia stats [user] - Show user statistics
        !trivia leaderboard / !trivia lb - Show channel leaderboard
        !trivia global - Show global leaderboard
    """

    # Plugin metadata
    NAMESPACE = "trivia"
    VERSION = "1.1.0"
    DESCRIPTION = "Interactive trivia game with persistence"

    # NATS subjects - Commands
    SUBJECT_START = "rosey.command.trivia.start"
    SUBJECT_STOP = "rosey.command.trivia.stop"
    SUBJECT_ANSWER = "rosey.command.trivia.answer"
    SUBJECT_SKIP = "rosey.command.trivia.skip"
    SUBJECT_STATS = "rosey.command.trivia.stats"
    SUBJECT_LEADERBOARD = "rosey.command.trivia.leaderboard"
    SUBJECT_GLOBAL = "rosey.command.trivia.global"

    # NATS subjects - Events
    EVENT_GAME_STARTED = "trivia.game.started"
    EVENT_QUESTION_ASKED = "trivia.question.asked"
    EVENT_ANSWER_CORRECT = "trivia.answer.correct"
    EVENT_ANSWER_INCORRECT = "trivia.answer.incorrect"
    EVENT_QUESTION_TIMEOUT = "trivia.question.timeout"
    EVENT_QUESTION_SKIPPED = "trivia.question.skipped"
    EVENT_GAME_ENDED = "trivia.game.ended"
    EVENT_ACHIEVEMENT_EARNED = "trivia.achievement.earned"

    # Help text
    START_USAGE = "Usage: !trivia start [number_of_questions] [category]"
    ANSWER_USAGE = "Usage: !a <your answer>"

    # Category mapping
    CATEGORY_MAP = {
        "general": 9,
        "science": 17,
        "computers": 18,
        "math": 19,
        "geography": 22,
        "history": 23,
        "sports": 21,
        "animals": 27,
        "vehicles": 28,
    }

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

        # Storage and Achievements (initialized in setup)
        self.storage: Optional[TriviaStorage] = None
        self.achievement_checker: Optional[AchievementChecker] = None

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
        self.enable_achievements = self.config.get("enable_achievements", True)

    async def initialize(self) -> None:
        """
        Initialize plugin and subscribe to NATS subjects.
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")

        # Initialize storage
        try:
            self.storage = TriviaStorage(self.nats)
            await self.storage.register_schemas()
            self.achievement_checker = AchievementChecker(self.storage)
            self.logger.info("Trivia storage initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize storage: {e}")
            # We can continue without storage, but features will be limited
            # Or we could raise. For now, let's log and continue, checking self.storage later.

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

        sub_stats = await self.nats.subscribe(
            self.SUBJECT_STATS, cb=self._handle_stats
        )
        self._subscriptions.append(sub_stats)

        sub_lb = await self.nats.subscribe(
            self.SUBJECT_LEADERBOARD, cb=self._handle_leaderboard
        )
        self._subscriptions.append(sub_lb)

        sub_global = await self.nats.subscribe(
            self.SUBJECT_GLOBAL, cb=self._handle_global
        )
        self._subscriptions.append(sub_global)

        self._initialized = True
        self.logger.info(
            f"Plugin initialized. Subscribed to: "
            f"{self.SUBJECT_START}, {self.SUBJECT_STOP}, "
            f"{self.SUBJECT_ANSWER}, {self.SUBJECT_SKIP}, "
            f"{self.SUBJECT_STATS}, {self.SUBJECT_LEADERBOARD}, {self.SUBJECT_GLOBAL}"
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
        Handle !trivia start [N] [category] command.

        Expected message format:
            {
                "channel": "string",
                "user": "string",
                "args": "10 science"
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
        args_str = data.get("args", "").strip()

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

        # Parse args
        num_questions = self.default_questions
        category = None
        
        if args_str:
            parts = args_str.split()
            for part in parts:
                if part.isdigit():
                    num_questions = int(part)
                    num_questions = max(1, min(self.max_questions, num_questions))
                elif part.lower() in self.CATEGORY_MAP:
                    category = self.CATEGORY_MAP[part.lower()]

        # Fetch questions
        try:
            questions = await self.provider.fetch_questions(num_questions, category=category)
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
        
        # Record game start
        if self.storage:
            try:
                await self.storage.record_game_start(
                    game.game_id,
                    channel,
                    user,
                    len(questions),
                )
            except Exception as e:
                self.logger.error(f"Failed to record game start: {e}")

        # Respond
        cat_name = next((k for k, v in self.CATEGORY_MAP.items() if v == category), "General") if category else "General"
        
        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {
                    "game_id": game.game_id,
                    "questions": len(questions),
                    "category": cat_name,
                    "time_per_question": config.time_per_question,
                    "message": (
                        f"🎯 Trivia starting! {len(questions)} questions ({cat_name.title()}), "
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
                "category": cat_name,
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
            
        # Update stats and check achievements
        if self.storage and self.achievement_checker:
            try:
                # Update streak
                await self.storage.update_streak(answer.user, answer.correct)
                
                # Update category stats
                if game.current_question:
                    await self.storage.update_category_stats(
                        answer.user,
                        game.current_question.category,
                        answer.correct,
                    )
                
                # Check achievements
                if self.enable_achievements:
                    stats = await self.storage.get_user_stats(answer.user)
                    if stats:
                        new_achievements = await self.achievement_checker.check_and_award(
                            answer.user, stats
                        )
                        for achievement in new_achievements:
                            await self._announce_achievement(game.channel, answer.user, achievement)
            except Exception as e:
                self.logger.error(f"Error updating stats/achievements: {e}")

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
        winner = leaderboard[0] if leaderboard else None

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
            
        # Persist scores and check achievements
        if self.storage and leaderboard:
            try:
                # Record game end
                await self.storage.record_game_end(
                    game.game_id,
                    num_players=len(leaderboard),
                    winner_id=winner.user if winner else None,
                )
                
                # Update stats for each player
                for player in leaderboard:
                    is_winner = (player.user == winner.user) if winner else False
                    
                    # Update user stats
                    await self.storage.update_user_stats(
                        user_id=player.user,
                        questions_answered=player.total_answers,
                        correct_answers=player.correct_answers,
                        points_earned=player.score,
                        won_game=is_winner,
                        fastest_ms=int(player.fastest_time * 1000) if player.fastest_time else None,
                    )
                    
                    # Update channel stats
                    await self.storage.update_channel_stats(
                        user_id=player.user,
                        channel=game.channel,
                        points=player.score,
                        correct=player.correct_answers,
                        won=is_winner,
                    )
                    
                    # Check achievements
                    if self.enable_achievements and self.achievement_checker:
                        stats = await self.storage.get_user_stats(player.user)
                        if stats:
                            game_result = GameResult(
                                won=is_winner,
                                perfect=(player.correct_answers == player.total_answers and player.total_answers > 0),
                                score=player.score,
                            )
                            new_achievements = await self.achievement_checker.check_and_award(
                                player.user, stats, game_result
                            )
                            for achievement in new_achievements:
                                await self._announce_achievement(game.channel, player.user, achievement)
                                
            except Exception as e:
                self.logger.error(f"Error persisting game stats: {e}")

        # Cleanup
        if game.channel in self.active_games:
            del self.active_games[game.channel]

    async def _handle_stats(self, msg) -> None:
        """Handle !trivia stats [user]."""
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            return

        args = data.get("args", "").strip()
        target_user = args if args else data.get("user", "unknown")
        
        if not self.storage:
            if msg.reply:
                await self._respond(msg, {"success": False, "error": "Stats storage not available."})
            return
            
        stats = await self.storage.get_user_stats(target_user)
        
        if not stats:
            if msg.reply:
                await self._respond(msg, {
                    "success": True, 
                    "result": {"message": f"📊 No stats found for {target_user}"}
                })
            return
        
        achievements = await self.storage.get_user_achievements(target_user)
        
        message = (
            f"📊 Stats for {target_user}:\n"
            f"• Games: {stats.total_games} | Won: {stats.games_won}\n"
            f"• Questions: {stats.correct_answers}/{stats.total_questions} "
            f"({stats.accuracy:.1f}%)\n"
            f"• Total Points: {stats.total_points:,}\n"
            f"• Streak: 🔥{stats.current_answer_streak} | Best: {stats.best_answer_streak}\n"
            f"• 🏆 {len(achievements)} achievements earned"
        )
        
        if stats.favorite_category:
            message += f"\n• Favorite: {stats.favorite_category.title()}"
        
        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {
                    "user": target_user,
                    "stats": {
                        "games": stats.total_games,
                        "won": stats.games_won,
                        "points": stats.total_points,
                        "accuracy": stats.accuracy
                    },
                    "message": message
                }
            })

    async def _handle_leaderboard(self, msg) -> None:
        """Handle !trivia leaderboard / !trivia lb."""
        try:
            data = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.logger.error(f"Invalid message format: {e}")
            return

        channel = data.get("channel", "unknown")
        
        if not self.storage:
            return
            
        leaderboard = await self.storage.get_channel_leaderboard(channel)
        
        if not leaderboard:
            if msg.reply:
                await self._respond(msg, {
                    "success": True,
                    "result": {"message": "📊 No trivia has been played in this channel yet!"}
                })
            return
        
        lines = [f"🏆 Trivia Leaderboard ({channel}):\n"]
        medals = ["🥇", "🥈", "🥉"]
        
        for entry in leaderboard[:10]:
            medal = medals[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
            lines.append(
                f"{medal} {entry.user_id} - {entry.total_points:,} pts "
                f"({entry.games_played} games)"
            )
        
        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {"message": "\n".join(lines)}
            })

    async def _handle_global(self, msg) -> None:
        """Handle !trivia global."""
        if not self.storage:
            return
            
        leaderboard = await self.storage.get_global_leaderboard()
        
        if not leaderboard:
            if msg.reply:
                await self._respond(msg, {
                    "success": True,
                    "result": {"message": "📊 No trivia has been played yet!"}
                })
            return
        
        lines = ["🌍 Global Trivia Leaderboard:\n"]
        medals = ["🥇", "🥈", "🥉"]
        
        for entry in leaderboard[:10]:
            medal = medals[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
            lines.append(
                f"{medal} {entry.user_id} - {entry.total_points:,} pts"
            )
        
        if msg.reply:
            await self._respond(msg, {
                "success": True,
                "result": {"message": "\n".join(lines)}
            })

    async def _announce_achievement(
        self, 
        channel: str, 
        user: str, 
        achievement: Achievement
    ) -> None:
        """Announce newly earned achievement."""
        message = (
            f"🎉 {user} earned an achievement!\n"
            f"{achievement.icon} **{achievement.name}**\n"
            f"_{achievement.description}_"
        )
        
        await self._send_to_channel(channel, message)
        
        if self.emit_events:
            await self._emit_event(self.EVENT_ACHIEVEMENT_EARNED, {
                "channel": channel,
                "user": user,
                "achievement": {
                    "id": achievement.id,
                    "name": achievement.name,
                    "icon": achievement.icon,
                },
            })

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
