"""
Trivia Game State Machine

Manages trivia game sessions with state transitions,
timing, and score tracking.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

from .question import Answer, Question


class GameState(Enum):
    """Game state enumeration."""

    IDLE = "idle"
    STARTING = "starting"
    QUESTION_ACTIVE = "question_active"
    BETWEEN_QUESTIONS = "between_questions"
    ENDING = "ending"


@dataclass
class PlayerScore:
    """
    Track a player's score in the current game.

    Attributes:
        user: Player username
        score: Total points accumulated
        correct_answers: Number of correct answers
        total_answers: Number of answers submitted
        fastest_time: Fastest correct answer time
    """

    user: str
    score: int = 0
    correct_answers: int = 0
    total_answers: int = 0
    fastest_time: Optional[float] = None

    def record_answer(self, correct: bool, points: int, time_taken: float) -> None:
        """
        Record an answer submission.

        Args:
            correct: Whether answer was correct
            points: Points to award
            time_taken: Time taken to answer
        """
        self.total_answers += 1

        if correct:
            self.score += points
            self.correct_answers += 1

            if self.fastest_time is None or time_taken < self.fastest_time:
                self.fastest_time = time_taken


@dataclass
class GameConfig:
    """
    Configuration for a trivia game.

    Attributes:
        num_questions: Total questions in the game
        time_per_question: Seconds to answer each question
        start_delay: Seconds before first question
        between_questions: Seconds between questions
        points_decay: Whether to award more points for faster answers
        min_points_ratio: Minimum points ratio when using decay (0-1)
    """

    num_questions: int = 10
    time_per_question: int = 30
    start_delay: int = 5
    between_questions: int = 3
    points_decay: bool = True
    min_points_ratio: float = 0.5


# Type alias for callbacks
GameCallback = Optional[Callable[["TriviaGame"], None]]
QuestionCallback = Optional[Callable[["TriviaGame", Question], None]]
AnswerCallback = Optional[Callable[["TriviaGame", Answer], None]]


class TriviaGame:
    """
    Manages a single trivia game session.

    Responsible for:
    - Game state transitions
    - Question progression
    - Score tracking
    - Timer management

    The game emits events via callbacks for the plugin to handle
    (sending messages to chat, emitting NATS events, etc.)
    """

    def __init__(
        self,
        game_id: str,
        channel: str,
        config: GameConfig,
        questions: List[Question],
        on_state_change: GameCallback = None,
        on_question: QuestionCallback = None,
        on_answer: AnswerCallback = None,
        on_timeout: QuestionCallback = None,
        on_end: GameCallback = None,
    ):
        """
        Initialize a trivia game.

        Args:
            game_id: Unique identifier for this game
            channel: Channel where game is being played
            config: Game configuration
            questions: List of questions for the game
            on_state_change: Called when game state changes
            on_question: Called when a new question is asked
            on_answer: Called when someone answers
            on_timeout: Called when question times out
            on_end: Called when game ends
        """
        self.game_id = game_id
        self.channel = channel
        self.config = config
        self.questions = questions

        # Callbacks
        self.on_state_change = on_state_change
        self.on_question = on_question
        self.on_answer = on_answer
        self.on_timeout = on_timeout
        self.on_end = on_end

        # State
        self._state = GameState.IDLE
        self.current_question_index = -1
        self.current_question: Optional[Question] = None
        self.question_start_time: Optional[float] = None
        self.scores: Dict[str, PlayerScore] = {}
        self.answered_this_question: Set[str] = set()

        # Timer task
        self._timer_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def state(self) -> GameState:
        """Current game state."""
        return self._state

    @state.setter
    def state(self, new_state: GameState) -> None:
        """Set state and trigger callback."""
        old_state = self._state
        self._state = new_state

        if old_state != new_state and self.on_state_change:
            try:
                result = self.on_state_change(self)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                pass

    @property
    def is_active(self) -> bool:
        """Whether the game is currently active."""
        return self._state in (
            GameState.STARTING,
            GameState.QUESTION_ACTIVE,
            GameState.BETWEEN_QUESTIONS,
        )

    async def start(self) -> bool:
        """
        Start the game with countdown.

        Returns:
            True if game started, False if already running
        """
        if self._state != GameState.IDLE:
            return False

        self._running = True
        self.state = GameState.STARTING

        # Wait for start delay then ask first question
        self._timer_task = asyncio.create_task(self._start_countdown())
        return True

    async def _start_countdown(self) -> None:
        """Wait for start delay then begin game."""
        await asyncio.sleep(self.config.start_delay)

        if self._running:
            await self._next_question()

    async def stop(self, ended_by: Optional[str] = None) -> None:
        """
        Stop the game early.

        Args:
            ended_by: Username of who stopped the game
        """
        if not self._running:
            return

        self._running = False

        # Cancel any pending timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass

        self.state = GameState.ENDING
        await self._end_game()

    async def submit_answer(self, user: str, answer: str) -> Optional[Answer]:
        """
        Process an answer submission.

        Args:
            user: Username of who answered
            answer: The submitted answer

        Returns:
            Answer object if processed, None if invalid/duplicate
        """
        # Only accept answers during active question
        if self._state != GameState.QUESTION_ACTIVE:
            return None

        # Don't allow duplicate answers from same user
        if user in self.answered_this_question:
            return None

        if not self.current_question or not self.question_start_time:
            return None

        # Mark user as having answered
        self.answered_this_question.add(user)

        # Calculate time taken
        time_taken = time.time() - self.question_start_time

        # Check if correct
        correct = self.current_question.check_answer(answer)

        # Calculate points
        points = 0
        if correct:
            points = self._calculate_points(self.current_question, time_taken)

        # Create answer record
        answer_record = Answer(
            user=user,
            answer=answer,
            timestamp=time_taken,
            correct=correct,
            points_awarded=points,
        )

        # Update player score
        if user not in self.scores:
            self.scores[user] = PlayerScore(user=user)
        self.scores[user].record_answer(correct, points, time_taken)

        # Trigger callback
        if self.on_answer:
            try:
                result = self.on_answer(self, answer_record)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # If correct, cancel timer and move to next question
        if correct:
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                try:
                    await self._timer_task
                except asyncio.CancelledError:
                    pass

            # Schedule next question
            if self._running:
                self._timer_task = asyncio.create_task(self._between_questions())

        return answer_record

    async def skip_question(self) -> bool:
        """
        Skip to next question.

        Returns:
            True if skipped, False if no active question
        """
        if self._state != GameState.QUESTION_ACTIVE:
            return False

        # Cancel timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass

        # Move to next
        if self._running:
            await self._next_question()

        return True

    async def _next_question(self) -> None:
        """Advance to next question or end game."""
        self.current_question_index += 1
        self.answered_this_question.clear()

        # Check if game is over
        if self.current_question_index >= len(self.questions):
            self.state = GameState.ENDING
            await self._end_game()
            return

        # Get next question
        self.current_question = self.questions[self.current_question_index]
        self.question_start_time = time.time()
        self.state = GameState.QUESTION_ACTIVE

        # Trigger question callback
        if self.on_question:
            try:
                result = self.on_question(self, self.current_question)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # Start question timer
        self._timer_task = asyncio.create_task(self._question_timer())

    async def _question_timer(self) -> None:
        """Timer for current question."""
        await asyncio.sleep(self.config.time_per_question)

        if self._running and self._state == GameState.QUESTION_ACTIVE:
            await self._on_question_timeout()

    async def _on_question_timeout(self) -> None:
        """Called when time runs out on a question."""
        if not self.current_question:
            return

        # Trigger timeout callback
        if self.on_timeout:
            try:
                result = self.on_timeout(self, self.current_question)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # Move to next question
        if self._running:
            self._timer_task = asyncio.create_task(self._between_questions())

    async def _between_questions(self) -> None:
        """Wait between questions."""
        self.state = GameState.BETWEEN_QUESTIONS
        await asyncio.sleep(self.config.between_questions)

        if self._running:
            await self._next_question()

    async def _end_game(self) -> None:
        """End the game and trigger callback."""
        self._running = False
        self.state = GameState.ENDING

        if self.on_end:
            try:
                result = self.on_end(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # Reset to idle
        self.state = GameState.IDLE

    def _calculate_points(self, question: Question, time_taken: float) -> int:
        """
        Calculate points with optional time decay.

        Faster answers earn more points (up to 1.5x base points).
        Slow answers earn minimum points (min_points_ratio of base).

        Args:
            question: The question being answered
            time_taken: Seconds taken to answer

        Returns:
            Points to award
        """
        base_points = question.points

        if not self.config.points_decay:
            return base_points

        # Calculate decay
        max_time = self.config.time_per_question
        min_ratio = self.config.min_points_ratio
        max_ratio = 1.5  # Bonus for very fast answers

        # Linear interpolation from max_ratio (instant) to min_ratio (timeout)
        ratio = max_ratio - (max_ratio - min_ratio) * (time_taken / max_time)
        ratio = max(min_ratio, min(max_ratio, ratio))

        return int(base_points * ratio)

    def get_leaderboard(self) -> List[PlayerScore]:
        """
        Get sorted leaderboard.

        Returns:
            List of PlayerScore objects sorted by score (desc), then correct answers (desc)
        """
        return sorted(
            self.scores.values(),
            key=lambda p: (-p.score, -p.correct_answers),
        )

    def get_stats(self) -> Dict:
        """
        Get current game statistics.

        Returns:
            Dict with game stats
        """
        return {
            "game_id": self.game_id,
            "channel": self.channel,
            "state": self._state.value,
            "current_question": self.current_question_index + 1,
            "total_questions": len(self.questions),
            "players": len(self.scores),
            "total_answers": sum(p.total_answers for p in self.scores.values()),
            "total_correct": sum(p.correct_answers for p in self.scores.values()),
        }
