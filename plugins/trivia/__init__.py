"""
Trivia Plugin Package

An interactive trivia game plugin using the Open Trivia Database.

Commands:
    !trivia start [N] - Start game with N questions (default 10)
    !trivia stop - End current game
    !trivia answer <answer> / !a <answer> - Submit answer
    !trivia skip - Skip current question
"""

from .question import Answer, Difficulty, Question, QuestionType
from .game import GameConfig, GameState, PlayerScore, TriviaGame
from .providers.base import QuestionProvider
from .providers.opentdb import OpenTDBProvider

__all__ = [
    # Question module
    "Answer",
    "Difficulty",
    "Question",
    "QuestionType",
    # Game module
    "GameConfig",
    "GameState",
    "PlayerScore",
    "TriviaGame",
    # Providers
    "QuestionProvider",
    "OpenTDBProvider",
]
