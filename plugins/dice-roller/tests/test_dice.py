"""
Unit tests for dice parsing and rolling logic.

Tests cover:
- DiceParser: notation parsing and validation
- DiceRoll: result formatting
- DiceRoller: roll execution and coin flips
"""

import random
import pytest
from typing import Tuple

from dice import DiceParser, DiceRoll, DiceRoller


# =============================================================================
# DiceParser Tests
# =============================================================================


class TestDiceParserValidNotation:
    """Tests for valid dice notation parsing."""

    @pytest.fixture
    def parser(self) -> DiceParser:
        """Create a parser with default limits."""
        return DiceParser()

    @pytest.mark.parametrize(
        "notation,expected",
        [
            # Basic notation
            ("2d6", (2, 6, 0)),
            ("d20", (1, 20, 0)),
            ("1d20", (1, 20, 0)),
            ("4d10", (4, 10, 0)),
            ("10d8", (10, 8, 0)),
            # With positive modifier
            ("2d6+5", (2, 6, 5)),
            ("d20+1", (1, 20, 1)),
            ("3d8+10", (3, 8, 10)),
            # With negative modifier
            ("2d6-5", (2, 6, -5)),
            ("d20-1", (1, 20, -1)),
            ("4d10-2", (4, 10, -2)),
            # Edge cases
            ("1d2", (1, 2, 0)),
            ("20d6", (20, 6, 0)),
            ("1d1000", (1, 1000, 0)),
            ("1d6+100", (1, 6, 100)),
            ("1d6-100", (1, 6, -100)),
        ],
    )
    def test_valid_notation(
        self, parser: DiceParser, notation: str, expected: Tuple[int, int, int]
    ) -> None:
        """Test parsing valid dice notation."""
        result = parser.parse(notation)
        assert result == expected

    def test_case_insensitive(self, parser: DiceParser) -> None:
        """Test that notation is case insensitive."""
        assert parser.parse("D6") == (1, 6, 0)
        assert parser.parse("2D20") == (2, 20, 0)
        assert parser.parse("3D8+5") == (3, 8, 5)

    def test_whitespace_stripped(self, parser: DiceParser) -> None:
        """Test that whitespace is stripped."""
        assert parser.parse("  2d6  ") == (2, 6, 0)
        assert parser.parse("\t1d20+5\n") == (1, 20, 5)


class TestDiceParserInvalidNotation:
    """Tests for invalid dice notation."""

    @pytest.fixture
    def parser(self) -> DiceParser:
        """Create a parser with default limits."""
        return DiceParser()

    def test_empty_string(self, parser: DiceParser) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse("")

    def test_whitespace_only(self, parser: DiceParser) -> None:
        """Test that whitespace-only raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse("   ")
        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse("\t\n")

    def test_invalid_format(self, parser: DiceParser) -> None:
        """Test various invalid formats."""
        invalid = ["xyz", "roll", "dice", "2+6", "d", "2d", "dd6", "2dd6"]
        for notation in invalid:
            with pytest.raises(ValueError, match="Invalid dice notation"):
                parser.parse(notation)

    def test_zero_dice(self, parser: DiceParser) -> None:
        """Test that zero dice raises ValueError."""
        with pytest.raises(ValueError, match="at least 1 die"):
            parser.parse("0d6")

    def test_zero_sides(self, parser: DiceParser) -> None:
        """Test that zero sides raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 sides"):
            parser.parse("2d0")

    def test_one_side(self, parser: DiceParser) -> None:
        """Test that one side raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 sides"):
            parser.parse("2d1")


class TestDiceParserLimits:
    """Tests for dice limit validation."""

    def test_exceeds_max_dice(self) -> None:
        """Test that exceeding max dice raises ValueError."""
        parser = DiceParser(max_dice=10)
        with pytest.raises(ValueError, match="Maximum 10 dice"):
            parser.parse("11d6")

    def test_at_max_dice(self) -> None:
        """Test that max dice exactly is allowed."""
        parser = DiceParser(max_dice=10)
        result = parser.parse("10d6")
        assert result == (10, 6, 0)

    def test_exceeds_max_sides(self) -> None:
        """Test that exceeding max sides raises ValueError."""
        parser = DiceParser(max_sides=100)
        with pytest.raises(ValueError, match="Maximum 100 sides"):
            parser.parse("1d101")

    def test_at_max_sides(self) -> None:
        """Test that max sides exactly is allowed."""
        parser = DiceParser(max_sides=100)
        result = parser.parse("1d100")
        assert result == (1, 100, 0)

    def test_exceeds_max_modifier_positive(self) -> None:
        """Test that exceeding max positive modifier raises ValueError."""
        parser = DiceParser(max_modifier=50)
        with pytest.raises(ValueError, match="between -50 and \\+50"):
            parser.parse("1d6+51")

    def test_exceeds_max_modifier_negative(self) -> None:
        """Test that exceeding max negative modifier raises ValueError."""
        parser = DiceParser(max_modifier=50)
        with pytest.raises(ValueError, match="between -50 and \\+50"):
            parser.parse("1d6-51")

    def test_at_max_modifier(self) -> None:
        """Test that max modifier exactly is allowed."""
        parser = DiceParser(max_modifier=50)
        assert parser.parse("1d6+50") == (1, 6, 50)
        assert parser.parse("1d6-50") == (1, 6, -50)

    def test_custom_limits(self) -> None:
        """Test custom limit configuration."""
        parser = DiceParser(max_dice=5, max_sides=20, max_modifier=10)

        # Valid within limits
        assert parser.parse("5d20+10") == (5, 20, 10)

        # Exceeds each limit
        with pytest.raises(ValueError):
            parser.parse("6d6")
        with pytest.raises(ValueError):
            parser.parse("1d21")
        with pytest.raises(ValueError):
            parser.parse("1d6+11")


# =============================================================================
# DiceRoll Tests
# =============================================================================


class TestDiceRollFormat:
    """Tests for DiceRoll formatting."""

    def test_format_single_die(self) -> None:
        """Test formatting a single die roll."""
        roll = DiceRoll(
            notation="d20",
            count=1,
            sides=20,
            modifier=0,
            rolls=[17],
            total=17,
        )
        assert roll.format() == "🎲 [17] = 17"

    def test_format_multiple_dice(self) -> None:
        """Test formatting multiple dice."""
        roll = DiceRoll(
            notation="2d6",
            count=2,
            sides=6,
            modifier=0,
            rolls=[4, 3],
            total=7,
        )
        assert roll.format() == "🎲 [4, 3] = 7"

    def test_format_with_positive_modifier(self) -> None:
        """Test formatting with positive modifier."""
        roll = DiceRoll(
            notation="d20+5",
            count=1,
            sides=20,
            modifier=5,
            rolls=[17],
            total=22,
        )
        assert roll.format() == "🎲 [17] + 5 = 22"

    def test_format_with_negative_modifier(self) -> None:
        """Test formatting with negative modifier."""
        roll = DiceRoll(
            notation="4d6-2",
            count=4,
            sides=6,
            modifier=-2,
            rolls=[6, 4, 3, 2],
            total=13,
        )
        assert roll.format() == "🎲 [6, 4, 3, 2] - 2 = 13"

    def test_format_many_dice(self) -> None:
        """Test formatting many dice."""
        roll = DiceRoll(
            notation="10d6",
            count=10,
            sides=6,
            modifier=0,
            rolls=[1, 2, 3, 4, 5, 6, 1, 2, 3, 4],
            total=31,
        )
        assert roll.format() == "🎲 [1, 2, 3, 4, 5, 6, 1, 2, 3, 4] = 31"


# =============================================================================
# DiceRoller Tests
# =============================================================================


class TestDiceRollerRoll:
    """Tests for DiceRoller.roll()."""

    @pytest.fixture
    def seeded_roller(self) -> DiceRoller:
        """Create a roller with seeded RNG for deterministic tests."""
        rng = random.Random(42)
        return DiceRoller(rng=rng)

    def test_roll_returns_dice_roll(self, seeded_roller: DiceRoller) -> None:
        """Test that roll returns a DiceRoll object."""
        result = seeded_roller.roll("2d6")
        assert isinstance(result, DiceRoll)

    def test_roll_preserves_notation(self, seeded_roller: DiceRoller) -> None:
        """Test that roll preserves original notation."""
        result = seeded_roller.roll("2d6+5")
        assert result.notation == "2d6+5"

    def test_roll_correct_count(self, seeded_roller: DiceRoller) -> None:
        """Test that roll has correct dice count."""
        result = seeded_roller.roll("3d8")
        assert result.count == 3
        assert len(result.rolls) == 3

    def test_roll_values_in_range(self) -> None:
        """Test that roll values are within valid range."""
        roller = DiceRoller()

        # Roll many times to test range
        for _ in range(100):
            result = roller.roll("1d6")
            assert 1 <= result.rolls[0] <= 6
            assert 1 <= result.total <= 6

    def test_roll_total_is_sum_plus_modifier(self, seeded_roller: DiceRoller) -> None:
        """Test that total equals sum of rolls plus modifier."""
        result = seeded_roller.roll("3d6+5")
        assert result.total == sum(result.rolls) + 5

        result = seeded_roller.roll("2d8-3")
        assert result.total == sum(result.rolls) - 3

    def test_roll_deterministic_with_seed(self) -> None:
        """Test that seeded RNG produces consistent results."""
        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        roller1 = DiceRoller(rng=rng1)
        roller2 = DiceRoller(rng=rng2)

        result1 = roller1.roll("4d6")
        result2 = roller2.roll("4d6")

        assert result1.rolls == result2.rolls
        assert result1.total == result2.total

    def test_roll_invalid_notation_raises(self, seeded_roller: DiceRoller) -> None:
        """Test that invalid notation raises ValueError."""
        with pytest.raises(ValueError):
            seeded_roller.roll("invalid")


class TestDiceRollerFlip:
    """Tests for DiceRoller.flip()."""

    def test_flip_returns_heads_or_tails(self) -> None:
        """Test that flip returns either Heads or Tails."""
        roller = DiceRoller()

        # Flip many times
        outcomes = {roller.flip() for _ in range(100)}

        # Should have seen both outcomes
        assert "Heads" in outcomes
        assert "Tails" in outcomes
        # Should not have any other outcomes
        assert outcomes == {"Heads", "Tails"}

    def test_flip_deterministic_with_seed(self) -> None:
        """Test that seeded RNG produces consistent flips."""
        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        roller1 = DiceRoller(rng=rng1)
        roller2 = DiceRoller(rng=rng2)

        results1 = [roller1.flip() for _ in range(10)]
        results2 = [roller2.flip() for _ in range(10)]

        assert results1 == results2


class TestDiceRollerFormatFlip:
    """Tests for DiceRoller.format_flip()."""

    def test_format_flip_heads(self) -> None:
        """Test formatting Heads result."""
        roller = DiceRoller()
        assert roller.format_flip("Heads") == "🪙 Heads!"

    def test_format_flip_tails(self) -> None:
        """Test formatting Tails result."""
        roller = DiceRoller()
        assert roller.format_flip("Tails") == "🪙 Tails!"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    @pytest.fixture
    def roller(self) -> DiceRoller:
        """Create a roller for testing."""
        return DiceRoller()

    def test_very_high_roll(self, roller: DiceRoller) -> None:
        """Test rolling with max values."""
        result = roller.roll("20d1000")
        # Each die can roll 1-1000, so total is 20-20000
        assert 20 <= result.total <= 20000
        assert len(result.rolls) == 20

    def test_minimum_die(self, roller: DiceRoller) -> None:
        """Test rolling a d2 (minimum valid die)."""
        result = roller.roll("1d2")
        assert result.rolls[0] in [1, 2]

    def test_roll_with_zero_modifier(self, roller: DiceRoller) -> None:
        """Test that zero modifier doesn't show in format."""
        result = roller.roll("2d6")
        assert result.modifier == 0
        assert "+" not in result.format()
        assert "-" not in result.format()

    def test_negative_total_possible(self, roller: DiceRoller) -> None:
        """Test that negative totals are possible with modifiers."""
        # Create a roller that will roll 1s
        class FixedRNG:
            def randint(self, a, b):
                return a  # Always return minimum

            def choice(self, seq):
                return seq[0]

        fixed_roller = DiceRoller(rng=FixedRNG())
        result = fixed_roller.roll("1d6-10")

        # Should get 1 - 10 = -9
        assert result.rolls == [1]
        assert result.total == -9
