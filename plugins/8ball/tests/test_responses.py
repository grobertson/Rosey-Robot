"""
tests/test_responses.py

Unit tests for 8ball response system.

Tests cover:
- Category enum values
- Response lists completeness
- EightBallResponse formatting
- ResponseSelector probability distribution
- Seeded RNG for deterministic testing
"""

import random
from collections import Counter


import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from responses import (
    Category,
    EightBallResponse,
    ResponseSelector,
    POSITIVE_RESPONSES,
    NEUTRAL_RESPONSES,
    NEGATIVE_RESPONSES,
    POSITIVE_FLAVORS,
    NEUTRAL_FLAVORS,
    NEGATIVE_FLAVORS,
    get_all_responses,
)


# =============================================================================
# Category Enum Tests
# =============================================================================

class TestCategory:
    """Tests for the Category enum."""
    
    def test_category_values(self):
        """All category values should be lowercase strings."""
        assert Category.POSITIVE.value == "positive"
        assert Category.NEUTRAL.value == "neutral"
        assert Category.NEGATIVE.value == "negative"
    
    def test_category_count(self):
        """There should be exactly 3 categories."""
        assert len(Category) == 3


# =============================================================================
# Response List Tests
# =============================================================================

class TestResponseLists:
    """Tests for the response list contents."""
    
    def test_positive_count(self):
        """Positive should have 10 responses (matches original 8-ball)."""
        assert len(POSITIVE_RESPONSES) == 10
    
    def test_neutral_count(self):
        """Neutral should have 5 responses (matches original 8-ball)."""
        assert len(NEUTRAL_RESPONSES) == 5
    
    def test_negative_count(self):
        """Negative should have 5 responses (matches original 8-ball)."""
        assert len(NEGATIVE_RESPONSES) == 5
    
    def test_total_responses(self):
        """Total should be 20 responses (matches original 8-ball)."""
        total = len(POSITIVE_RESPONSES) + len(NEUTRAL_RESPONSES) + len(NEGATIVE_RESPONSES)
        assert total == 20
    
    def test_positive_flavors_count(self):
        """Should have at least 5 positive flavors."""
        assert len(POSITIVE_FLAVORS) >= 5
    
    def test_neutral_flavors_count(self):
        """Should have at least 5 neutral flavors."""
        assert len(NEUTRAL_FLAVORS) >= 5
    
    def test_negative_flavors_count(self):
        """Should have at least 5 negative flavors."""
        assert len(NEGATIVE_FLAVORS) >= 5
    
    def test_no_duplicate_responses(self):
        """All 20 responses should be unique."""
        all_responses = POSITIVE_RESPONSES + NEUTRAL_RESPONSES + NEGATIVE_RESPONSES
        assert len(set(all_responses)) == 20
    
    def test_all_responses_non_empty(self):
        """All responses should be non-empty strings."""
        all_responses = POSITIVE_RESPONSES + NEUTRAL_RESPONSES + NEGATIVE_RESPONSES
        for response in all_responses:
            assert isinstance(response, str)
            assert len(response) > 0
    
    def test_all_flavors_non_empty(self):
        """All flavor texts should be non-empty strings."""
        all_flavors = POSITIVE_FLAVORS + NEUTRAL_FLAVORS + NEGATIVE_FLAVORS
        for flavor in all_flavors:
            assert isinstance(flavor, str)
            assert len(flavor) > 0


# =============================================================================
# EightBallResponse Tests
# =============================================================================

class TestEightBallResponse:
    """Tests for the EightBallResponse dataclass."""
    
    def test_creation(self):
        """Can create a response with all fields."""
        response = EightBallResponse(
            answer="It is certain",
            category=Category.POSITIVE,
            flavor="The cosmos smile upon you! ✨"
        )
        assert response.answer == "It is certain"
        assert response.category == Category.POSITIVE
        assert response.flavor == "The cosmos smile upon you! ✨"
    
    def test_format_basic(self):
        """Format should produce expected output."""
        response = EightBallResponse(
            answer="Yes definitely",
            category=Category.POSITIVE,
            flavor="Looking good!"
        )
        formatted = response.format("Will I win?")
        assert formatted == '🎱 "Will I win?" — Yes definitely. Looking good!'
    
    def test_format_includes_emoji(self):
        """Formatted response should include 8-ball emoji."""
        response = EightBallResponse(
            answer="My reply is no",
            category=Category.NEGATIVE,
            flavor="Yikes."
        )
        formatted = response.format("test")
        assert "🎱" in formatted
    
    def test_format_includes_question(self):
        """Formatted response should include the question."""
        response = EightBallResponse(
            answer="Yes",
            category=Category.POSITIVE,
            flavor="Nice!"
        )
        question = "Will I get pizza?"
        formatted = response.format(question)
        assert question in formatted
    
    def test_format_includes_answer(self):
        """Formatted response should include the answer."""
        response = EightBallResponse(
            answer="Without a doubt",
            category=Category.POSITIVE,
            flavor="Cool!"
        )
        formatted = response.format("test")
        assert "Without a doubt" in formatted
    
    def test_format_includes_flavor(self):
        """Formatted response should include the flavor text."""
        response = EightBallResponse(
            answer="Yes",
            category=Category.POSITIVE,
            flavor="The vibes are immaculate."
        )
        formatted = response.format("test")
        assert "The vibes are immaculate." in formatted
    
    def test_to_dict(self):
        """to_dict should return serializable dictionary."""
        response = EightBallResponse(
            answer="Most likely",
            category=Category.POSITIVE,
            flavor="Nice!"
        )
        d = response.to_dict()
        assert d["answer"] == "Most likely"
        assert d["category"] == "positive"  # String, not enum
        assert d["flavor"] == "Nice!"
    
    def test_to_dict_category_is_string(self):
        """to_dict category should be string value, not enum."""
        response = EightBallResponse(
            answer="No",
            category=Category.NEGATIVE,
            flavor="Sorry!"
        )
        d = response.to_dict()
        assert isinstance(d["category"], str)


# =============================================================================
# ResponseSelector Tests
# =============================================================================

class TestResponseSelector:
    """Tests for the ResponseSelector class."""
    
    def test_select_returns_response(self):
        """select() should return an EightBallResponse."""
        selector = ResponseSelector()
        response = selector.select()
        assert isinstance(response, EightBallResponse)
    
    def test_select_has_valid_category(self):
        """Selected response should have valid category."""
        selector = ResponseSelector()
        response = selector.select()
        assert response.category in Category
    
    def test_select_has_non_empty_answer(self):
        """Selected response should have non-empty answer."""
        selector = ResponseSelector()
        response = selector.select()
        assert len(response.answer) > 0
    
    def test_select_has_non_empty_flavor(self):
        """Selected response should have non-empty flavor."""
        selector = ResponseSelector()
        response = selector.select()
        assert len(response.flavor) > 0
    
    def test_seeded_rng_deterministic(self):
        """Same seed should produce same results."""
        rng1 = random.Random(12345)
        rng2 = random.Random(12345)
        selector1 = ResponseSelector(rng1)
        selector2 = ResponseSelector(rng2)
        
        for _ in range(10):
            r1 = selector1.select()
            r2 = selector2.select()
            assert r1.answer == r2.answer
            assert r1.category == r2.category
    
    def test_distribution_positive_about_50_percent(self):
        """Over many trials, positive should be ~50% (10/20)."""
        rng = random.Random(42)
        selector = ResponseSelector(rng)
        
        counts = Counter()
        trials = 10000
        
        for _ in range(trials):
            response = selector.select()
            counts[response.category] += 1
        
        positive_pct = counts[Category.POSITIVE] / trials
        # Should be ~50% ± 5%
        assert 0.45 <= positive_pct <= 0.55, f"Positive was {positive_pct:.1%}"
    
    def test_distribution_neutral_about_25_percent(self):
        """Over many trials, neutral should be ~25% (5/20)."""
        rng = random.Random(42)
        selector = ResponseSelector(rng)
        
        counts = Counter()
        trials = 10000
        
        for _ in range(trials):
            response = selector.select()
            counts[response.category] += 1
        
        neutral_pct = counts[Category.NEUTRAL] / trials
        # Should be ~25% ± 5%
        assert 0.20 <= neutral_pct <= 0.30, f"Neutral was {neutral_pct:.1%}"
    
    def test_distribution_negative_about_25_percent(self):
        """Over many trials, negative should be ~25% (5/20)."""
        rng = random.Random(42)
        selector = ResponseSelector(rng)
        
        counts = Counter()
        trials = 10000
        
        for _ in range(trials):
            response = selector.select()
            counts[response.category] += 1
        
        negative_pct = counts[Category.NEGATIVE] / trials
        # Should be ~25% ± 5%
        assert 0.20 <= negative_pct <= 0.30, f"Negative was {negative_pct:.1%}"
    
    def test_all_responses_reachable(self):
        """Every response should appear at least once in many trials."""
        rng = random.Random(42)
        selector = ResponseSelector(rng)
        
        seen_answers = set()
        trials = 10000
        
        for _ in range(trials):
            response = selector.select()
            seen_answers.add(response.answer)
        
        all_responses = set(POSITIVE_RESPONSES + NEUTRAL_RESPONSES + NEGATIVE_RESPONSES)
        missing = all_responses - seen_answers
        assert len(missing) == 0, f"Missing responses: {missing}"
    
    def test_flavor_matches_category(self):
        """Flavor text should always match the response category."""
        selector = ResponseSelector()
        
        for _ in range(100):
            response = selector.select()
            
            if response.category == Category.POSITIVE:
                assert response.flavor in POSITIVE_FLAVORS
            elif response.category == Category.NEUTRAL:
                assert response.flavor in NEUTRAL_FLAVORS
            else:
                assert response.flavor in NEGATIVE_FLAVORS
    
    def test_select_from_category_positive(self):
        """select_from_category should return response from specified category."""
        selector = ResponseSelector()
        response = selector.select_from_category(Category.POSITIVE)
        assert response.category == Category.POSITIVE
        assert response.answer in POSITIVE_RESPONSES
        assert response.flavor in POSITIVE_FLAVORS
    
    def test_select_from_category_neutral(self):
        """select_from_category should return response from specified category."""
        selector = ResponseSelector()
        response = selector.select_from_category(Category.NEUTRAL)
        assert response.category == Category.NEUTRAL
        assert response.answer in NEUTRAL_RESPONSES
        assert response.flavor in NEUTRAL_FLAVORS
    
    def test_select_from_category_negative(self):
        """select_from_category should return response from specified category."""
        selector = ResponseSelector()
        response = selector.select_from_category(Category.NEGATIVE)
        assert response.category == Category.NEGATIVE
        assert response.answer in NEGATIVE_RESPONSES
        assert response.flavor in NEGATIVE_FLAVORS


# =============================================================================
# get_all_responses Tests
# =============================================================================

class TestGetAllResponses:
    """Tests for the get_all_responses helper function."""
    
    def test_returns_20_responses(self):
        """Should return exactly 20 response tuples."""
        responses = get_all_responses()
        assert len(responses) == 20
    
    def test_returns_tuples(self):
        """Each item should be (answer, category) tuple."""
        responses = get_all_responses()
        for item in responses:
            assert isinstance(item, tuple)
            assert len(item) == 2
            answer, category = item
            assert isinstance(answer, str)
            assert isinstance(category, Category)
    
    def test_categories_correct(self):
        """Categories should match the response lists."""
        responses = get_all_responses()
        
        for answer, category in responses:
            if category == Category.POSITIVE:
                assert answer in POSITIVE_RESPONSES
            elif category == Category.NEUTRAL:
                assert answer in NEUTRAL_RESPONSES
            else:
                assert answer in NEGATIVE_RESPONSES
