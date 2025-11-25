"""
Trivia Question Models

Data models for trivia questions and answers.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Dict, List
import html
import random


class Difficulty(Enum):
    """Question difficulty level."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(Enum):
    """Question format type."""

    MULTIPLE_CHOICE = "multiple"
    TRUE_FALSE = "boolean"
    FREE_RESPONSE = "free"


# Points awarded per difficulty
DIFFICULTY_POINTS = {
    Difficulty.EASY: 10,
    Difficulty.MEDIUM: 20,
    Difficulty.HARD: 30,
}


@dataclass
class Question:
    """
    Represents a trivia question.

    Attributes:
        id: Unique identifier for the question
        category: Category/topic of the question
        difficulty: Difficulty level (easy/medium/hard)
        type: Question format (multiple choice, true/false, free response)
        question: The question text
        correct_answer: The correct answer
        incorrect_answers: List of incorrect answers
    """

    id: str
    category: str
    difficulty: Difficulty
    type: QuestionType
    question: str
    correct_answer: str
    incorrect_answers: List[str]
    _shuffled_answers: List[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Initialize shuffled answers after creation."""
        # Create shuffled answer list on first access
        self._shuffled_answers = []

    @property
    def all_answers(self) -> List[str]:
        """
        All answers shuffled (for multiple choice display).

        The shuffled order is cached so it remains consistent.
        """
        if not self._shuffled_answers:
            answers = [self.correct_answer] + list(self.incorrect_answers)
            random.shuffle(answers)
            self._shuffled_answers = answers
        return self._shuffled_answers

    @property
    def answer_map(self) -> Dict[str, str]:
        """
        Map of letter -> answer for multiple choice.

        Returns:
            Dict like {"A": "Paris", "B": "London", ...}
        """
        letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
        return {
            letters[i]: answer
            for i, answer in enumerate(self.all_answers)
            if i < len(letters)
        }

    @property
    def points(self) -> int:
        """Base points for this question based on difficulty."""
        return DIFFICULTY_POINTS.get(self.difficulty, 10)

    def check_answer(self, answer: str, fuzzy_threshold: float = 0.85) -> bool:
        """
        Check if answer is correct.

        Handles:
        - Case insensitivity
        - Letter answers (A, B, C, D) for multiple choice
        - Full text answers
        - Fuzzy matching for free response

        Args:
            answer: The submitted answer
            fuzzy_threshold: Minimum similarity ratio for fuzzy match (0-1)

        Returns:
            True if answer is correct
        """
        answer = answer.strip()
        if not answer:
            return False

        normalized_answer = answer.lower()
        normalized_correct = self.correct_answer.lower()

        # 1. Exact match (case insensitive)
        if normalized_answer == normalized_correct:
            return True

        # 2. Letter answer (A, B, C, D) for multiple choice
        if (
            self.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE)
            and len(answer) == 1
            and answer.upper() in self.answer_map
        ):
            letter_answer = self.answer_map[answer.upper()]
            return letter_answer.lower() == normalized_correct

        # 3. For true/false, accept various forms
        if self.type == QuestionType.TRUE_FALSE:
            true_forms = {"t", "true", "yes", "y", "1"}
            false_forms = {"f", "false", "no", "n", "0"}

            if normalized_correct in ["true", "yes"]:
                return normalized_answer in true_forms
            elif normalized_correct in ["false", "no"]:
                return normalized_answer in false_forms

        # 4. Full text match against any answer choice
        if self.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
            for choice in self.all_answers:
                if normalized_answer == choice.lower():
                    return choice.lower() == normalized_correct

        # 5. Fuzzy matching for free response
        ratio = SequenceMatcher(None, normalized_answer, normalized_correct).ratio()
        if ratio >= fuzzy_threshold:
            return True

        return False

    def format_for_display(self) -> str:
        """
        Format question for chat display.

        Returns:
            Formatted string with question and answer options
        """
        lines = [html.unescape(self.question), ""]

        if self.type == QuestionType.TRUE_FALSE:
            lines.append("A) True  B) False")
        elif self.type == QuestionType.MULTIPLE_CHOICE:
            # Format as two columns for 4 answers
            answers = self.all_answers
            if len(answers) == 4:
                lines.append(f"A) {answers[0]}  B) {answers[1]}")
                lines.append(f"C) {answers[2]}  D) {answers[3]}")
            else:
                # Single column for other counts
                for i, ans in enumerate(answers):
                    letter = chr(ord("A") + i)
                    lines.append(f"{letter}) {ans}")
        # Free response shows no options

        return "\n".join(lines)

    def format_answer_reveal(self) -> str:
        """Format the correct answer reveal."""
        return f"The answer was: **{self.correct_answer}**"


@dataclass
class Answer:
    """
    Represents a submitted answer.

    Attributes:
        user: Username of who answered
        answer: The submitted answer text
        timestamp: Time taken to answer (seconds since question asked)
        correct: Whether the answer was correct
        points_awarded: Points awarded for this answer
    """

    user: str
    answer: str
    timestamp: float
    correct: bool
    points_awarded: int
