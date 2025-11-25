"""
plugins/8ball/responses.py

Magic 8-Ball response definitions with categories and Rosey personality flavors.

The classic Magic 8-Ball has 20 responses in 3 categories with the following
probability distribution (matching the original toy):
- Positive: 50% (10/20)
- Neutral: 25% (5/20)
- Negative: 25% (5/20)
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional


class Category(Enum):
    """Response categories matching the original Magic 8-Ball."""
    
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


# =============================================================================
# Classic 8-Ball Responses
# =============================================================================

POSITIVE_RESPONSES: List[str] = [
    "It is certain",
    "It is decidedly so",
    "Without a doubt",
    "Yes definitely",
    "You may rely on it",
    "As I see it, yes",
    "Most likely",
    "Outlook good",
    "Yes",
    "Signs point to yes",
]

NEUTRAL_RESPONSES: List[str] = [
    "Reply hazy, try again",
    "Ask again later",
    "Better not tell you now",
    "Cannot predict now",
    "Concentrate and ask again",
]

NEGATIVE_RESPONSES: List[str] = [
    "Don't count on it",
    "My reply is no",
    "My sources say no",
    "Outlook not so good",
    "Very doubtful",
]


# =============================================================================
# Rosey Personality Flavors
# =============================================================================

POSITIVE_FLAVORS: List[str] = [
    "The cosmos smile upon you! ✨",
    "Ooh, looking good!",
    "The vibes are immaculate.",
    "I like where this is going!",
    "The universe has spoken favorably!",
]

NEUTRAL_FLAVORS: List[str] = [
    "Hmm, the mists are cloudy...",
    "The spirits are being coy today.",
    "Even I can't see through this fog.",
    "The universe is buffering...",
    "*shakes ball dramatically*",
]

NEGATIVE_FLAVORS: List[str] = [
    "Yikes. Sorry, friend.",
    "The spirits are skeptical...",
    "Oof. Maybe don't bet on that one.",
    "The universe winced a little.",
    "That's a big ol' nope from the cosmos.",
]


# =============================================================================
# Response Data Classes
# =============================================================================

@dataclass
class EightBallResponse:
    """A complete 8-ball response with flavor text."""
    
    answer: str
    category: Category
    flavor: str
    
    def format(self, question: str) -> str:
        """
        Format the response for chat display.
        
        Args:
            question: The original question asked.
            
        Returns:
            Formatted string ready for chat: 🎱 "question" — answer. flavor
        """
        return f'🎱 "{question}" — {self.answer}. {self.flavor}'
    
    def to_dict(self) -> dict:
        """
        Convert response to dictionary for JSON serialization.
        
        Returns:
            Dictionary with answer, category, and flavor.
        """
        return {
            "answer": self.answer,
            "category": self.category.value,
            "flavor": self.flavor,
        }


# =============================================================================
# Response Selector
# =============================================================================

class ResponseSelector:
    """
    Select 8-ball responses with weighted probability.
    
    The probability distribution matches the original Magic 8-Ball:
    - Positive: 50% (10/20)
    - Neutral: 25% (5/20)
    - Negative: 25% (5/20)
    
    Args:
        rng: Optional random.Random instance for deterministic testing.
    """
    
    # Class-level response lists for easy access in tests
    POSITIVE = POSITIVE_RESPONSES
    NEUTRAL = NEUTRAL_RESPONSES
    NEGATIVE = NEGATIVE_RESPONSES
    
    POSITIVE_FLAVORS = POSITIVE_FLAVORS
    NEUTRAL_FLAVORS = NEUTRAL_FLAVORS
    NEGATIVE_FLAVORS = NEGATIVE_FLAVORS
    
    def __init__(self, rng: Optional[random.Random] = None):
        """
        Initialize the response selector.
        
        Args:
            rng: Optional random.Random instance for deterministic results.
        """
        self.rng = rng if rng is not None else random.Random()
    
    def select(self) -> EightBallResponse:
        """
        Select a random response with weighted probability.
        
        Probability distribution matches original 8-ball:
        - Positive: 50% (10/20)
        - Neutral: 25% (5/20)
        - Negative: 25% (5/20)
        
        Returns:
            EightBallResponse with answer, category, and flavor.
        """
        # Build weighted list: all responses + their categories
        all_responses: List[Tuple[str, Category]] = []
        
        for answer in self.POSITIVE:
            all_responses.append((answer, Category.POSITIVE))
        for answer in self.NEUTRAL:
            all_responses.append((answer, Category.NEUTRAL))
        for answer in self.NEGATIVE:
            all_responses.append((answer, Category.NEGATIVE))
        
        # Random selection from all 20 (natural 50/25/25 distribution)
        answer, category = self.rng.choice(all_responses)
        flavor = self._select_flavor(category)
        
        return EightBallResponse(answer=answer, category=category, flavor=flavor)
    
    def select_from_category(self, category: Category) -> EightBallResponse:
        """
        Select a response from a specific category.
        
        Useful for testing or when you want to control the outcome.
        
        Args:
            category: The Category to select from.
            
        Returns:
            EightBallResponse from the specified category.
        """
        answer = self._select_answer(category)
        flavor = self._select_flavor(category)
        return EightBallResponse(answer=answer, category=category, flavor=flavor)
    
    def _select_answer(self, category: Category) -> str:
        """
        Select a random answer from the specified category.
        
        Args:
            category: The category to select from.
            
        Returns:
            A random answer string.
        """
        if category == Category.POSITIVE:
            return self.rng.choice(self.POSITIVE)
        elif category == Category.NEUTRAL:
            return self.rng.choice(self.NEUTRAL)
        else:
            return self.rng.choice(self.NEGATIVE)
    
    def _select_flavor(self, category: Category) -> str:
        """
        Select a random flavor text for the specified category.
        
        Args:
            category: The category to match flavor with.
            
        Returns:
            A random flavor string matching the category.
        """
        if category == Category.POSITIVE:
            return self.rng.choice(self.POSITIVE_FLAVORS)
        elif category == Category.NEUTRAL:
            return self.rng.choice(self.NEUTRAL_FLAVORS)
        else:
            return self.rng.choice(self.NEGATIVE_FLAVORS)


def get_all_responses() -> List[Tuple[str, Category]]:
    """
    Get all 20 responses with their categories.
    
    Useful for iteration and testing.
    
    Returns:
        List of (answer, category) tuples.
    """
    all_responses: List[Tuple[str, Category]] = []
    
    for answer in POSITIVE_RESPONSES:
        all_responses.append((answer, Category.POSITIVE))
    for answer in NEUTRAL_RESPONSES:
        all_responses.append((answer, Category.NEUTRAL))
    for answer in NEGATIVE_RESPONSES:
        all_responses.append((answer, Category.NEGATIVE))
    
    return all_responses
