"""
Open Trivia Database Provider

Fetches trivia questions from the Open Trivia Database API.
https://opentdb.com/
"""

import html
import logging
from typing import List, Optional

try:
    import httpx
except ImportError:
    httpx = None

from .base import QuestionProvider
from ..question import Difficulty, Question, QuestionType

logger = logging.getLogger(__name__)


# OpenTDB response codes
RESPONSE_SUCCESS = 0
RESPONSE_NO_RESULTS = 1
RESPONSE_INVALID_PARAMETER = 2
RESPONSE_TOKEN_NOT_FOUND = 3
RESPONSE_TOKEN_EMPTY = 4

RESPONSE_MESSAGES = {
    RESPONSE_SUCCESS: "Success",
    RESPONSE_NO_RESULTS: "No results available for query",
    RESPONSE_INVALID_PARAMETER: "Invalid parameter",
    RESPONSE_TOKEN_NOT_FOUND: "Session token not found",
    RESPONSE_TOKEN_EMPTY: "Token has exhausted all questions",
}


class OpenTDBError(Exception):
    """Error from Open Trivia Database API."""

    def __init__(self, code: int, message: str = None):
        self.code = code
        self.message = message or RESPONSE_MESSAGES.get(code, "Unknown error")
        super().__init__(f"OpenTDB error {code}: {self.message}")


class OpenTDBProvider(QuestionProvider):
    """
    Open Trivia Database provider.

    API Documentation: https://opentdb.com/api_config.php

    Features:
    - Fetches random trivia questions
    - Supports category and difficulty filtering
    - Handles HTML entity decoding
    - Optional session tokens (prevents duplicate questions)
    """

    BASE_URL = "https://opentdb.com/api.php"
    CATEGORY_URL = "https://opentdb.com/api_category.php"
    TOKEN_URL = "https://opentdb.com/api_token.php"

    DEFAULT_TIMEOUT = 10.0

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize OpenTDB provider.

        Args:
            timeout: HTTP request timeout in seconds
        """
        if httpx is None:
            raise ImportError(
                "httpx is required for OpenTDBProvider. "
                "Install it with: pip install httpx"
            )

        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._session_token: Optional[str] = None
        self.logger = logging.getLogger(f"{__name__}.OpenTDBProvider")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def fetch_questions(
        self,
        amount: int,
        category: Optional[int] = None,
        difficulty: Optional[Difficulty] = None,
    ) -> List[Question]:
        """
        Fetch questions from OpenTDB.

        Args:
            amount: Number of questions (1-50)
            category: Optional category ID
            difficulty: Optional difficulty level

        Returns:
            List of Question objects

        Raises:
            OpenTDBError: If API returns error
            httpx.HTTPError: If network error occurs
        """
        client = await self._get_client()

        # Build query parameters
        params = {
            "amount": min(50, max(1, amount)),
            "type": "multiple",  # Multiple choice only for now
        }

        if category is not None:
            params["category"] = category

        if difficulty is not None:
            params["difficulty"] = difficulty.value

        if self._session_token:
            params["token"] = self._session_token

        self.logger.debug(f"Fetching {amount} questions with params: {params}")

        # Make request
        response = await client.get(self.BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()

        # Check response code
        response_code = data.get("response_code", 0)
        if response_code != RESPONSE_SUCCESS:
            raise OpenTDBError(response_code)

        # Parse questions
        questions = [self._parse_question(q) for q in data.get("results", [])]

        self.logger.debug(f"Fetched {len(questions)} questions")
        return questions

    def _parse_question(self, data: dict) -> Question:
        """
        Parse OpenTDB response into Question object.

        Args:
            data: Raw question data from API

        Returns:
            Question object
        """
        # Decode HTML entities
        question_text = html.unescape(data["question"])
        correct_answer = html.unescape(data["correct_answer"])
        incorrect_answers = [html.unescape(a) for a in data["incorrect_answers"]]
        category = html.unescape(data["category"])

        # Parse enums
        difficulty = Difficulty(data["difficulty"])
        question_type = QuestionType(data["type"])

        # Generate ID from question hash
        question_id = str(hash(question_text) & 0xFFFFFFFF)

        return Question(
            id=question_id,
            category=category,
            difficulty=difficulty,
            type=question_type,
            question=question_text,
            correct_answer=correct_answer,
            incorrect_answers=incorrect_answers,
        )

    async def get_categories(self) -> List[dict]:
        """
        Get available categories from OpenTDB.

        Returns:
            List of category dicts: [{"id": 9, "name": "General Knowledge"}, ...]
        """
        client = await self._get_client()

        response = await client.get(self.CATEGORY_URL)
        response.raise_for_status()

        data = response.json()
        return data.get("trivia_categories", [])

    async def get_session_token(self) -> str:
        """
        Get a session token to prevent duplicate questions.

        Returns:
            Session token string
        """
        client = await self._get_client()

        response = await client.get(
            self.TOKEN_URL,
            params={"command": "request"},
        )
        response.raise_for_status()

        data = response.json()
        if data.get("response_code") != 0:
            raise OpenTDBError(
                data.get("response_code", -1),
                "Failed to get session token",
            )

        self._session_token = data.get("token")
        self.logger.debug(f"Got session token: {self._session_token[:8]}...")
        return self._session_token

    async def reset_session_token(self) -> None:
        """Reset session token to re-enable all questions."""
        if not self._session_token:
            return

        client = await self._get_client()

        response = await client.get(
            self.TOKEN_URL,
            params={"command": "reset", "token": self._session_token},
        )
        response.raise_for_status()

        self.logger.debug("Session token reset")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._session_token = None
