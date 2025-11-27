"""
Tests for trivia game state machine.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock

from trivia.game import (
    GameConfig,
    GameState,
    PlayerScore,
    TriviaGame,
)


class TestGameState:
    """Test GameState enum."""

    def test_values(self):
        """Test enum values."""
        assert GameState.IDLE.value == "idle"
        assert GameState.STARTING.value == "starting"
        assert GameState.QUESTION_ACTIVE.value == "question_active"
        assert GameState.BETWEEN_QUESTIONS.value == "between_questions"
        assert GameState.ENDING.value == "ending"


class TestPlayerScore:
    """Test PlayerScore tracking."""

    def test_initial_values(self):
        """Test initial score values."""
        score = PlayerScore(user="player1")
        assert score.user == "player1"
        assert score.score == 0
        assert score.correct_answers == 0
        assert score.total_answers == 0
        assert score.fastest_time is None

    def test_record_correct_answer(self):
        """Test recording correct answer."""
        score = PlayerScore(user="player1")
        score.record_answer(correct=True, points=10, time_taken=5.0)

        assert score.score == 10
        assert score.correct_answers == 1
        assert score.total_answers == 1
        assert score.fastest_time == 5.0

    def test_record_incorrect_answer(self):
        """Test recording incorrect answer."""
        score = PlayerScore(user="player1")
        score.record_answer(correct=False, points=0, time_taken=8.0)

        assert score.score == 0
        assert score.correct_answers == 0
        assert score.total_answers == 1
        assert score.fastest_time is None  # Only set for correct answers

    def test_fastest_time_tracking(self):
        """Test fastest time is updated correctly."""
        score = PlayerScore(user="player1")

        score.record_answer(correct=True, points=10, time_taken=5.0)
        assert score.fastest_time == 5.0

        score.record_answer(correct=True, points=10, time_taken=3.0)
        assert score.fastest_time == 3.0  # Updated to faster time

        score.record_answer(correct=True, points=10, time_taken=7.0)
        assert score.fastest_time == 3.0  # Not updated (slower)

    def test_multiple_answers(self):
        """Test accumulating multiple answers."""
        score = PlayerScore(user="player1")

        score.record_answer(correct=True, points=10, time_taken=5.0)
        score.record_answer(correct=False, points=0, time_taken=8.0)
        score.record_answer(correct=True, points=15, time_taken=3.0)

        assert score.score == 25
        assert score.correct_answers == 2
        assert score.total_answers == 3
        assert score.fastest_time == 3.0


class TestGameConfig:
    """Test GameConfig defaults and settings."""

    def test_default_values(self):
        """Test default configuration."""
        config = GameConfig()
        assert config.num_questions == 10
        assert config.time_per_question == 30
        assert config.start_delay == 5
        assert config.between_questions == 3
        assert config.points_decay is True
        assert config.min_points_ratio == 0.5

    def test_custom_values(self, game_config):
        """Test custom configuration."""
        assert game_config.num_questions == 3
        assert game_config.time_per_question == 5
        assert game_config.start_delay == 1
        assert game_config.between_questions == 1


class TestTriviaGameInit:
    """Test TriviaGame initialization."""

    def test_initial_state(self, game_config, sample_questions):
        """Test game starts in IDLE state."""
        game = TriviaGame(
            game_id="test-123",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        assert game.game_id == "test-123"
        assert game.channel == "lobby"
        assert game.state == GameState.IDLE
        assert game.current_question_index == -1
        assert game.current_question is None
        assert len(game.scores) == 0
        assert not game.is_active

    def test_is_active_states(self, game_config, sample_questions):
        """Test is_active for different states."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        # Test each state
        game._state = GameState.IDLE
        assert not game.is_active

        game._state = GameState.STARTING
        assert game.is_active

        game._state = GameState.QUESTION_ACTIVE
        assert game.is_active

        game._state = GameState.BETWEEN_QUESTIONS
        assert game.is_active

        game._state = GameState.ENDING
        assert not game.is_active


class TestTriviaGameStart:
    """Test game start functionality."""

    @pytest.mark.asyncio
    async def test_start_transitions_to_starting(self, game_config, sample_questions):
        """Test start() transitions state correctly."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        result = await game.start()
        assert result is True
        assert game.state == GameState.STARTING

        # Clean up
        await game.stop()

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, game_config, sample_questions):
        """Test start() returns False if already running."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        await game.start()
        result = await game.start()  # Try to start again
        assert result is False

        await game.stop()

    @pytest.mark.asyncio
    async def test_start_triggers_question_after_delay(self, game_config, sample_questions):
        """Test that first question is asked after start delay."""
        on_question = AsyncMock()

        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
            on_question=on_question,
        )

        await game.start()

        # Wait for start delay + a bit
        await asyncio.sleep(game_config.start_delay + 0.5)

        assert game.state == GameState.QUESTION_ACTIVE
        assert game.current_question_index == 0
        assert game.current_question is not None
        on_question.assert_called_once()

        await game.stop()


class TestTriviaGameStop:
    """Test game stop functionality."""

    @pytest.mark.asyncio
    async def test_stop_ends_game(self, game_config, sample_questions):
        """Test stop() ends the game."""
        on_end = AsyncMock()

        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
            on_end=on_end,
        )

        await game.start()
        await game.stop()

        assert game.state == GameState.IDLE
        assert not game._running
        on_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, game_config, sample_questions):
        """Test stop() when game not running is safe."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        # Should not raise
        await game.stop()
        assert game.state == GameState.IDLE


class TestTriviaGameAnswers:
    """Test answer submission."""

    @pytest.mark.asyncio
    async def test_submit_correct_answer(self, game_config, sample_questions):
        """Test submitting correct answer."""
        on_answer = AsyncMock()

        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
            on_answer=on_answer,
        )

        await game.start()
        await asyncio.sleep(game_config.start_delay + 0.2)

        # Get correct answer for first question
        correct = sample_questions[0].correct_answer

        result = await game.submit_answer("player1", correct)

        assert result is not None
        assert result.correct is True
        assert result.user == "player1"
        assert result.points_awarded > 0
        on_answer.assert_called_once()

        await game.stop()

    @pytest.mark.asyncio
    async def test_submit_incorrect_answer(self, game_config, sample_questions):
        """Test submitting incorrect answer."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        await game.start()
        await asyncio.sleep(game_config.start_delay + 0.2)

        result = await game.submit_answer("player1", "wrong answer")

        assert result is not None
        assert result.correct is False
        assert result.points_awarded == 0

        await game.stop()

    @pytest.mark.asyncio
    async def test_duplicate_answer_rejected(self, game_config, sample_questions):
        """Test that duplicate answers from same user are rejected."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        await game.start()
        await asyncio.sleep(game_config.start_delay + 0.2)

        # First answer
        result1 = await game.submit_answer("player1", "some answer")
        assert result1 is not None

        # Second answer from same user
        result2 = await game.submit_answer("player1", "another answer")
        assert result2 is None  # Rejected

        await game.stop()

    @pytest.mark.asyncio
    async def test_answer_when_not_active(self, game_config, sample_questions):
        """Test answering when no question active."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        # Not started - should return None
        result = await game.submit_answer("player1", "answer")
        assert result is None


class TestTriviaGameSkip:
    """Test question skipping."""

    @pytest.mark.asyncio
    async def test_skip_moves_to_next(self, game_config, sample_questions):
        """Test skip advances to next question."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        await game.start()
        await asyncio.sleep(game_config.start_delay + 0.2)

        assert game.current_question_index == 0

        result = await game.skip_question()
        assert result is True

        # Wait for next question
        await asyncio.sleep(game_config.between_questions + 0.2)

        assert game.current_question_index == 1

        await game.stop()

    @pytest.mark.asyncio
    async def test_skip_when_not_active(self, game_config, sample_questions):
        """Test skip when no question active."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        result = await game.skip_question()
        assert result is False


class TestTriviaGameTimeout:
    """Test question timeout."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_callback(self, sample_questions):
        """Test timeout triggers on_timeout callback."""
        # Use very short timeout for test
        config = GameConfig(
            num_questions=3,
            time_per_question=1,  # 1 second
            start_delay=0,  # No delay
            between_questions=0,
        )

        on_timeout = AsyncMock()

        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
            on_timeout=on_timeout,
        )

        await game.start()

        # Wait for timeout
        await asyncio.sleep(1.5)

        on_timeout.assert_called()

        await game.stop()


class TestTriviaGameScoring:
    """Test scoring functionality."""

    @pytest.mark.asyncio
    async def test_score_tracking(self, game_config, sample_questions):
        """Test scores are tracked correctly."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        await game.start()
        await asyncio.sleep(game_config.start_delay + 0.2)

        # Submit correct answer
        correct = sample_questions[0].correct_answer
        await game.submit_answer("player1", correct)

        assert "player1" in game.scores
        assert game.scores["player1"].score > 0
        assert game.scores["player1"].correct_answers == 1

        await game.stop()

    def test_points_decay_calculation(self, game_config, sample_questions):
        """Test points decay based on time."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        question = sample_questions[0]  # Easy = 10 base points

        # Fast answer should get more points
        fast_points = game._calculate_points(question, 0.1)

        # Slow answer should get fewer points
        slow_points = game._calculate_points(question, game_config.time_per_question - 0.1)

        assert fast_points > slow_points
        assert fast_points <= int(question.points * 1.5)  # Max 1.5x
        assert slow_points >= int(question.points * game_config.min_points_ratio)

    def test_leaderboard_sorting(self, game_config, sample_questions):
        """Test leaderboard is sorted correctly."""
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        # Add some scores
        game.scores["player1"] = PlayerScore(user="player1", score=50, correct_answers=3)
        game.scores["player2"] = PlayerScore(user="player2", score=80, correct_answers=4)
        game.scores["player3"] = PlayerScore(user="player3", score=50, correct_answers=4)

        leaderboard = game.get_leaderboard()

        # Should be sorted by score (desc), then correct answers (desc)
        assert leaderboard[0].user == "player2"  # Highest score
        assert leaderboard[1].user == "player3"  # Same score, more correct
        assert leaderboard[2].user == "player1"


class TestTriviaGameFullFlow:
    """Test complete game flow."""

    @pytest.mark.asyncio
    async def test_game_ends_after_all_questions(self, sample_questions):
        """Test game ends naturally after all questions answered."""
        config = GameConfig(
            num_questions=2,
            time_per_question=10,
            start_delay=0,
            between_questions=0,
        )

        # Use only 2 questions
        questions = sample_questions[:2]
        on_end = AsyncMock()

        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=questions,
            on_end=on_end,
        )

        await game.start()
        await asyncio.sleep(0.2)

        # Answer first question correctly
        await game.submit_answer("player1", questions[0].correct_answer)
        await asyncio.sleep(0.2)

        # Answer second question correctly
        await game.submit_answer("player1", questions[1].correct_answer)
        await asyncio.sleep(0.5)

        # Game should have ended
        on_end.assert_called_once()
        assert game.state == GameState.IDLE

    @pytest.mark.asyncio
    async def test_get_stats(self, game_config, sample_questions):
        """Test get_stats returns correct info."""
        game = TriviaGame(
            game_id="test-123",
            channel="lobby",
            config=game_config,
            questions=sample_questions,
        )

        stats = game.get_stats()

        assert stats["game_id"] == "test-123"
        assert stats["channel"] == "lobby"
        assert stats["state"] == "idle"
        assert stats["total_questions"] == 3
        assert stats["players"] == 0
