"""
Tests for trivia question models.
"""

import pytest

from trivia.question import (
    Answer,
    Difficulty,
    DIFFICULTY_POINTS,
    Question,
    QuestionType,
)


class TestDifficulty:
    """Test Difficulty enum."""

    def test_values(self):
        """Test enum values."""
        assert Difficulty.EASY.value == "easy"
        assert Difficulty.MEDIUM.value == "medium"
        assert Difficulty.HARD.value == "hard"

    def test_from_string(self):
        """Test creating from string."""
        assert Difficulty("easy") == Difficulty.EASY
        assert Difficulty("medium") == Difficulty.MEDIUM
        assert Difficulty("hard") == Difficulty.HARD


class TestQuestionType:
    """Test QuestionType enum."""

    def test_values(self):
        """Test enum values."""
        assert QuestionType.MULTIPLE_CHOICE.value == "multiple"
        assert QuestionType.TRUE_FALSE.value == "boolean"
        assert QuestionType.FREE_RESPONSE.value == "free"


class TestQuestion:
    """Test Question dataclass."""

    def test_creation(self, sample_question):
        """Test basic question creation."""
        assert sample_question.id == "q1"
        assert sample_question.category == "General Knowledge"
        assert sample_question.difficulty == Difficulty.EASY
        assert sample_question.type == QuestionType.MULTIPLE_CHOICE
        assert sample_question.question == "What is the capital of France?"
        assert sample_question.correct_answer == "Paris"
        assert len(sample_question.incorrect_answers) == 3

    def test_points_by_difficulty(self, sample_question):
        """Test points calculation by difficulty."""
        assert sample_question.points == 10  # EASY

        medium_q = Question(
            id="m1",
            category="Test",
            difficulty=Difficulty.MEDIUM,
            type=QuestionType.MULTIPLE_CHOICE,
            question="Test?",
            correct_answer="A",
            incorrect_answers=["B", "C", "D"],
        )
        assert medium_q.points == 20

        hard_q = Question(
            id="h1",
            category="Test",
            difficulty=Difficulty.HARD,
            type=QuestionType.MULTIPLE_CHOICE,
            question="Test?",
            correct_answer="A",
            incorrect_answers=["B", "C", "D"],
        )
        assert hard_q.points == 30

    def test_all_answers_shuffled(self, sample_question):
        """Test that all_answers includes all options."""
        answers = sample_question.all_answers
        assert len(answers) == 4
        assert "Paris" in answers
        assert "London" in answers
        assert "Berlin" in answers
        assert "Madrid" in answers

    def test_all_answers_cached(self, sample_question):
        """Test that shuffled order is cached."""
        first = sample_question.all_answers
        second = sample_question.all_answers
        assert first == second  # Same order

    def test_answer_map(self, sample_question):
        """Test letter-to-answer mapping."""
        answer_map = sample_question.answer_map
        assert len(answer_map) == 4
        assert "A" in answer_map
        assert "B" in answer_map
        assert "C" in answer_map
        assert "D" in answer_map
        # All answers should be present
        assert set(answer_map.values()) == {"Paris", "London", "Berlin", "Madrid"}


class TestCheckAnswer:
    """Test answer checking logic."""

    def test_exact_match(self, sample_question):
        """Test exact case-insensitive match."""
        assert sample_question.check_answer("Paris") is True
        assert sample_question.check_answer("paris") is True
        assert sample_question.check_answer("PARIS") is True
        assert sample_question.check_answer("PaRiS") is True

    def test_letter_answer(self, sample_question):
        """Test answering by letter."""
        # Find which letter corresponds to Paris
        for letter, answer in sample_question.answer_map.items():
            if answer == "Paris":
                assert sample_question.check_answer(letter) is True
                assert sample_question.check_answer(letter.lower()) is True
            else:
                assert sample_question.check_answer(letter) is False

    def test_wrong_answer(self, sample_question):
        """Test incorrect answers."""
        assert sample_question.check_answer("London") is False
        assert sample_question.check_answer("Berlin") is False
        assert sample_question.check_answer("Madrid") is False
        assert sample_question.check_answer("Tokyo") is False

    def test_empty_answer(self, sample_question):
        """Test empty/whitespace answers."""
        assert sample_question.check_answer("") is False
        assert sample_question.check_answer("   ") is False

    def test_fuzzy_match(self, sample_question):
        """Test fuzzy matching for close answers."""
        # Close misspelling should match
        assert sample_question.check_answer("Parris") is True  # One extra r
        assert sample_question.check_answer("Pais") is True  # Missing r

    def test_fuzzy_threshold(self, sample_question):
        """Test fuzzy matching threshold."""
        # Very wrong should not match
        assert sample_question.check_answer("xyz") is False
        assert sample_question.check_answer("Londoon") is False

    def test_true_false_variants(self, true_false_question):
        """Test true/false answer variants."""
        # True variants
        assert true_false_question.check_answer("True") is True
        assert true_false_question.check_answer("true") is True
        assert true_false_question.check_answer("t") is True
        assert true_false_question.check_answer("T") is True
        assert true_false_question.check_answer("yes") is True
        assert true_false_question.check_answer("y") is True
        assert true_false_question.check_answer("1") is True

        # False variants (should be wrong)
        assert true_false_question.check_answer("False") is False
        assert true_false_question.check_answer("false") is False
        assert true_false_question.check_answer("f") is False
        assert true_false_question.check_answer("no") is False
        assert true_false_question.check_answer("n") is False
        assert true_false_question.check_answer("0") is False

    def test_true_false_letter_a_b(self, true_false_question):
        """Test A/B for true/false."""
        # Find which letter maps to correct answer
        answer_map = true_false_question.answer_map
        correct_letter = None
        wrong_letter = None
        
        for letter, answer in answer_map.items():
            if answer == true_false_question.correct_answer:
                correct_letter = letter
            else:
                wrong_letter = letter
        
        assert correct_letter is not None
        assert wrong_letter is not None
        assert true_false_question.check_answer(correct_letter) is True
        assert true_false_question.check_answer(wrong_letter) is False


class TestFormatForDisplay:
    """Test question display formatting."""

    def test_multiple_choice_format(self, sample_question):
        """Test multiple choice formatting."""
        display = sample_question.format_for_display()
        assert "What is the capital of France?" in display
        assert "A)" in display
        assert "B)" in display
        assert "C)" in display
        assert "D)" in display

    def test_true_false_format(self, true_false_question):
        """Test true/false formatting."""
        display = true_false_question.format_for_display()
        assert "The sun is a star." in display
        assert "A) True" in display
        assert "B) False" in display

    def test_answer_reveal(self, sample_question):
        """Test answer reveal formatting."""
        reveal = sample_question.format_answer_reveal()
        assert "Paris" in reveal
        assert "The answer was:" in reveal


class TestAnswer:
    """Test Answer dataclass."""

    def test_creation(self):
        """Test Answer creation."""
        answer = Answer(
            user="player1",
            answer="Paris",
            timestamp=5.2,
            correct=True,
            points_awarded=12,
        )
        assert answer.user == "player1"
        assert answer.answer == "Paris"
        assert answer.timestamp == 5.2
        assert answer.correct is True
        assert answer.points_awarded == 12

    def test_incorrect_answer(self):
        """Test incorrect answer."""
        answer = Answer(
            user="player2",
            answer="London",
            timestamp=8.5,
            correct=False,
            points_awarded=0,
        )
        assert answer.correct is False
        assert answer.points_awarded == 0


class TestDifficultyPoints:
    """Test difficulty points mapping."""

    def test_all_difficulties_have_points(self):
        """Test all difficulties have point values."""
        for difficulty in Difficulty:
            assert difficulty in DIFFICULTY_POINTS
            assert DIFFICULTY_POINTS[difficulty] > 0

    def test_hard_worth_more(self):
        """Test harder questions worth more points."""
        assert DIFFICULTY_POINTS[Difficulty.HARD] > DIFFICULTY_POINTS[Difficulty.MEDIUM]
        assert DIFFICULTY_POINTS[Difficulty.MEDIUM] > DIFFICULTY_POINTS[Difficulty.EASY]
