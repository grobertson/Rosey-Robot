"""
Test fixtures for trivia plugin tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from trivia.question import Difficulty, Question, QuestionType
from trivia.game import GameConfig


@pytest.fixture
def sample_question():
    """Sample multiple choice question."""
    return Question(
        id="q1",
        category="General Knowledge",
        difficulty=Difficulty.EASY,
        type=QuestionType.MULTIPLE_CHOICE,
        question="What is the capital of France?",
        correct_answer="Paris",
        incorrect_answers=["London", "Berlin", "Madrid"],
    )


@pytest.fixture
def sample_questions():
    """List of sample questions for game tests."""
    return [
        Question(
            id="q1",
            category="General Knowledge",
            difficulty=Difficulty.EASY,
            type=QuestionType.MULTIPLE_CHOICE,
            question="What is the capital of France?",
            correct_answer="Paris",
            incorrect_answers=["London", "Berlin", "Madrid"],
        ),
        Question(
            id="q2",
            category="Science",
            difficulty=Difficulty.MEDIUM,
            type=QuestionType.MULTIPLE_CHOICE,
            question="What planet is known as the Red Planet?",
            correct_answer="Mars",
            incorrect_answers=["Venus", "Jupiter", "Saturn"],
        ),
        Question(
            id="q3",
            category="History",
            difficulty=Difficulty.HARD,
            type=QuestionType.MULTIPLE_CHOICE,
            question="In which year did World War I begin?",
            correct_answer="1914",
            incorrect_answers=["1916", "1912", "1918"],
        ),
    ]


@pytest.fixture
def true_false_question():
    """Sample true/false question."""
    return Question(
        id="tf1",
        category="Science",
        difficulty=Difficulty.EASY,
        type=QuestionType.TRUE_FALSE,
        question="The sun is a star.",
        correct_answer="True",
        incorrect_answers=["False"],
    )


@pytest.fixture
def game_config():
    """Fast game config for testing."""
    return GameConfig(
        num_questions=3,
        time_per_question=5,  # Short for tests
        start_delay=1,
        between_questions=1,
        points_decay=True,
    )


import json

@pytest.fixture
def mock_nats():
    """Mock NATS client."""
    nats = AsyncMock()
    nats.subscribe = AsyncMock(return_value=MagicMock())
    nats.publish = AsyncMock()
    
    # Setup default request response
    mock_response = MagicMock()
    mock_response.data = json.dumps({"success": True}).encode()
    nats.request.return_value = mock_response
    
    return nats


@pytest.fixture
def plugin_config():
    """Plugin configuration for tests."""
    return {
        "time_per_question": 5,
        "start_delay": 1,
        "between_questions": 1,
        "max_questions": 10,
        "default_questions": 3,
        "points_decay": True,
        "emit_events": True,
    }
