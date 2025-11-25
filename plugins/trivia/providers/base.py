"""
Base Question Provider Interface

Abstract base class for trivia question providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..question import Difficulty, Question


class QuestionProvider(ABC):
    """
    Base class for question providers.

    Providers fetch trivia questions from various sources
    (APIs, local files, databases, etc.)
    """

    @abstractmethod
    async def fetch_questions(
        self,
        amount: int,
        category: Optional[int] = None,
        difficulty: Optional[Difficulty] = None,
    ) -> List[Question]:
        """
        Fetch questions from the provider.

        Args:
            amount: Number of questions to fetch
            category: Optional category ID to filter by
            difficulty: Optional difficulty level to filter by

        Returns:
            List of Question objects

        Raises:
            ValueError: If provider cannot fulfill the request
            ConnectionError: If network error occurs
        """
        ...

    @abstractmethod
    async def get_categories(self) -> List[dict]:
        """
        Get available categories.

        Returns:
            List of dicts with category info:
            [{"id": 9, "name": "General Knowledge"}, ...]
        """
        ...

    async def close(self) -> None:
        """
        Close any resources used by the provider.

        Override this in subclasses that need cleanup.
        """
        pass
