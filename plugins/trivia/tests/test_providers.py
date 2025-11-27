"""
Tests for trivia question providers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from trivia.question import Difficulty, Question, QuestionType
from trivia.providers.base import QuestionProvider
from trivia.providers.opentdb import (
    OpenTDBProvider,
    OpenTDBError,
    RESPONSE_NO_RESULTS,
)


class TestQuestionProviderBase:
    """Test base provider interface."""

    def test_abstract_methods(self):
        """Test that base class cannot be instantiated."""
        with pytest.raises(TypeError):
            QuestionProvider()

    def test_close_default(self):
        """Test default close is a no-op."""
        # Create a concrete implementation for testing
        class ConcreteProvider(QuestionProvider):
            async def fetch_questions(self, amount, category=None, difficulty=None):
                return []

            async def get_categories(self):
                return []

        # Should not raise
        ConcreteProvider()
        # close() is async, but default implementation does nothing


class TestOpenTDBProvider:
    """Test OpenTDB provider."""

    @pytest.fixture
    def provider(self):
        """Create provider instance."""
        return OpenTDBProvider()

    @pytest.fixture
    def mock_response(self):
        """Sample API response."""
        return {
            "response_code": 0,
            "results": [
                {
                    "category": "General Knowledge",
                    "type": "multiple",
                    "difficulty": "easy",
                    "question": "What is the capital of France?",
                    "correct_answer": "Paris",
                    "incorrect_answers": ["London", "Berlin", "Madrid"],
                },
                {
                    "category": "Science &amp; Nature",
                    "type": "multiple",
                    "difficulty": "medium",
                    "question": "What is H&lt;sub&gt;2&lt;/sub&gt;O?",
                    "correct_answer": "Water",
                    "incorrect_answers": ["Salt", "Sugar", "Air"],
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_fetch_questions_success(self, provider, mock_response):
        """Test successful question fetch."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=mock_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        questions = await provider.fetch_questions(2)

        assert len(questions) == 2
        assert all(isinstance(q, Question) for q in questions)

        # Check first question
        q1 = questions[0]
        assert q1.category == "General Knowledge"
        assert q1.difficulty == Difficulty.EASY
        assert q1.type == QuestionType.MULTIPLE_CHOICE
        assert q1.question == "What is the capital of France?"
        assert q1.correct_answer == "Paris"
        assert len(q1.incorrect_answers) == 3

    @pytest.mark.asyncio
    async def test_html_entity_decoding(self, provider, mock_response):
        """Test HTML entities are decoded."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=mock_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        questions = await provider.fetch_questions(2)

        # Check second question has decoded HTML
        q2 = questions[1]
        assert q2.category == "Science & Nature"  # Decoded from &amp;
        # HTML entities like &lt;sub&gt; get decoded to actual tags
        # This is expected behavior - the raw API data had encoded HTML
        assert "&lt;" not in q2.question  # Should be decoded
        assert "&gt;" not in q2.question

    @pytest.mark.asyncio
    async def test_fetch_with_category(self, provider, mock_response):
        """Test fetching with category filter."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=mock_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        await provider.fetch_questions(5, category=9)

        # Verify category was passed
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["category"] == 9

    @pytest.mark.asyncio
    async def test_fetch_with_difficulty(self, provider, mock_response):
        """Test fetching with difficulty filter."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=mock_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        await provider.fetch_questions(5, difficulty=Difficulty.HARD)

        # Verify difficulty was passed
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["difficulty"] == "hard"

    @pytest.mark.asyncio
    async def test_fetch_clamps_amount(self, provider, mock_response):
        """Test amount is clamped to valid range."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=mock_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        # Request too many
        await provider.fetch_questions(100)
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["amount"] == 50  # Clamped to max

        # Request zero
        await provider.fetch_questions(0)
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["amount"] == 1  # Clamped to min

    @pytest.mark.asyncio
    async def test_api_error_response(self, provider):
        """Test handling API error response."""
        error_response = {"response_code": RESPONSE_NO_RESULTS}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=error_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        with pytest.raises(OpenTDBError) as exc_info:
            await provider.fetch_questions(5)

        assert exc_info.value.code == RESPONSE_NO_RESULTS

    @pytest.mark.asyncio
    async def test_get_categories(self, provider):
        """Test fetching categories."""
        categories_response = {
            "trivia_categories": [
                {"id": 9, "name": "General Knowledge"},
                {"id": 10, "name": "Entertainment: Books"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=MagicMock(return_value=categories_response),
            raise_for_status=MagicMock(),
        ))
        mock_client.is_closed = False

        provider._client = mock_client

        categories = await provider.get_categories()

        assert len(categories) == 2
        assert categories[0]["id"] == 9
        assert categories[0]["name"] == "General Knowledge"

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test close cleans up client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()

        provider._client = mock_client
        provider._session_token = "test-token"

        await provider.close()

        mock_client.aclose.assert_called_once()
        assert provider._client is None
        assert provider._session_token is None


class TestOpenTDBError:
    """Test OpenTDBError exception."""

    def test_error_with_code(self):
        """Test error with response code."""
        error = OpenTDBError(RESPONSE_NO_RESULTS)
        assert error.code == RESPONSE_NO_RESULTS
        assert "No results" in error.message
        assert "1" in str(error)  # Code in string representation

    def test_error_with_custom_message(self):
        """Test error with custom message."""
        error = OpenTDBError(99, "Custom error message")
        assert error.code == 99
        assert error.message == "Custom error message"


class TestParseQuestion:
    """Test question parsing."""

    def test_parse_multiple_choice(self):
        """Test parsing multiple choice question."""
        provider = OpenTDBProvider()

        data = {
            "category": "Science",
            "type": "multiple",
            "difficulty": "medium",
            "question": "Test question?",
            "correct_answer": "Answer A",
            "incorrect_answers": ["Answer B", "Answer C", "Answer D"],
        }

        question = provider._parse_question(data)

        assert question.type == QuestionType.MULTIPLE_CHOICE
        assert question.difficulty == Difficulty.MEDIUM
        assert question.correct_answer == "Answer A"
        assert len(question.incorrect_answers) == 3

    def test_parse_true_false(self):
        """Test parsing true/false question."""
        provider = OpenTDBProvider()

        data = {
            "category": "Science",
            "type": "boolean",
            "difficulty": "easy",
            "question": "Is the sky blue?",
            "correct_answer": "True",
            "incorrect_answers": ["False"],
        }

        question = provider._parse_question(data)

        assert question.type == QuestionType.TRUE_FALSE
        assert question.correct_answer == "True"
        assert question.incorrect_answers == ["False"]

    def test_parse_with_html_entities(self):
        """Test parsing decodes HTML entities."""
        provider = OpenTDBProvider()

        data = {
            "category": "Entertainment: Film &amp; Television",
            "type": "multiple",
            "difficulty": "hard",
            "question": "What year was &quot;Star Wars&quot; released?",
            "correct_answer": "1977",
            "incorrect_answers": ["1975", "1978", "1980"],
        }

        question = provider._parse_question(data)

        assert question.category == "Entertainment: Film & Television"
        assert '"Star Wars"' in question.question

    def test_question_id_generated(self):
        """Test question ID is generated."""
        provider = OpenTDBProvider()

        data = {
            "category": "Test",
            "type": "multiple",
            "difficulty": "easy",
            "question": "Test question?",
            "correct_answer": "A",
            "incorrect_answers": ["B", "C", "D"],
        }

        question = provider._parse_question(data)

        assert question.id is not None
        assert len(question.id) > 0
