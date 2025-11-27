"""
tests/test_countdown.py

Unit tests for the Countdown model and datetime parsing.

Tests cover:
- Datetime parsing for multiple formats
- Time remaining calculations
- Human-readable formatting
- Countdown dataclass operations
"""

import pytest
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from countdown import (
    Countdown,
    parse_datetime,
    format_remaining,
)


# =============================================================================
# Datetime Parsing Tests
# =============================================================================

class TestParseDatetime:
    """Tests for datetime parsing function."""
    
    def test_parse_iso_format(self):
        """Parse '2025-12-01 20:00' format."""
        result = parse_datetime("2025-12-01 20:00")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 1
        assert result.hour == 20
        assert result.minute == 0
    
    def test_parse_iso_with_seconds(self):
        """Parse '2025-12-01 20:00:30' format."""
        result = parse_datetime("2025-12-01 20:00:30")
        assert result.second == 30
    
    def test_parse_iso_t_format(self):
        """Parse '2025-12-01T20:00:00' ISO format."""
        result = parse_datetime("2025-12-01T20:00:00")
        assert result.year == 2025
        assert result.hour == 20
    
    def test_parse_us_format(self):
        """Parse '12/01/2025 20:00' US format."""
        result = parse_datetime("12/01/2025 20:00")
        assert result.month == 12
        assert result.day == 1
        assert result.year == 2025
    
    def test_parse_in_hours(self):
        """Parse 'in 2 hours' relative format."""
        now = datetime.now(timezone.utc)
        result = parse_datetime("in 2 hours")
        
        # Should be approximately 2 hours from now
        diff = result - now
        assert 7100 < diff.total_seconds() < 7300  # ~2 hours
    
    def test_parse_in_minutes(self):
        """Parse 'in 30 minutes' relative format."""
        now = datetime.now(timezone.utc)
        result = parse_datetime("in 30 minutes")
        
        diff = result - now
        assert 1700 < diff.total_seconds() < 1900  # ~30 minutes
    
    def test_parse_in_days(self):
        """Parse 'in 3 days' relative format."""
        now = datetime.now(timezone.utc)
        result = parse_datetime("in 3 days")
        
        diff = result - now
        assert 2.9 < diff.total_seconds() / 86400 < 3.1  # ~3 days
    
    def test_parse_tomorrow(self):
        """Parse 'tomorrow' keyword."""
        now = datetime.now(timezone.utc)
        result = parse_datetime("tomorrow")
        
        diff = result - now
        assert 0.9 < diff.total_seconds() / 86400 < 1.1  # ~1 day
    
    def test_parse_tomorrow_with_time(self):
        """Parse 'tomorrow 14:00' format."""
        result = parse_datetime("tomorrow 14:00")
        assert result.hour == 14
        assert result.minute == 0
    
    def test_parse_shorthand_hours(self):
        """Parse '2 hours' shorthand (without 'in')."""
        now = datetime.now(timezone.utc)
        result = parse_datetime("2 hours")
        
        diff = result - now
        assert 7100 < diff.total_seconds() < 7300
    
    def test_parse_case_insensitive(self):
        """Parsing should be case-insensitive."""
        result1 = parse_datetime("In 2 Hours")
        result2 = parse_datetime("IN 2 HOURS")
        
        # Results should be very close (within a second)
        diff = abs((result1 - result2).total_seconds())
        assert diff < 2
    
    def test_parse_invalid_format(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_datetime("not a valid time")
    
    def test_parse_invalid_date_values(self):
        """Invalid date values raise ValueError."""
        with pytest.raises(ValueError):
            parse_datetime("2025-13-45 99:99")  # Invalid month/day/time
    
    def test_result_is_utc(self):
        """Parsed datetime should be UTC."""
        result = parse_datetime("2025-12-01 20:00")
        assert result.tzinfo == timezone.utc


# =============================================================================
# Format Remaining Tests
# =============================================================================

class TestFormatRemaining:
    """Tests for time remaining formatting."""
    
    def test_format_days_hours_minutes(self):
        """Format days, hours, and minutes."""
        delta = timedelta(days=6, hours=4, minutes=30)
        result = format_remaining(delta)
        assert "6 days" in result
        assert "4 hours" in result
        assert "30 minutes" in result
    
    def test_format_hours_minutes(self):
        """Format hours and minutes only."""
        delta = timedelta(hours=2, minutes=15)
        result = format_remaining(delta)
        assert "2 hours" in result
        assert "15 minutes" in result
        assert "days" not in result
    
    def test_format_minutes_only(self):
        """Format minutes only."""
        delta = timedelta(minutes=45)
        result = format_remaining(delta)
        assert "45 minutes" in result
    
    def test_format_seconds_only(self):
        """Format seconds when less than a minute."""
        delta = timedelta(seconds=30)
        result = format_remaining(delta)
        assert "30 seconds" in result
    
    def test_format_short_mode(self):
        """Short format uses abbreviations."""
        delta = timedelta(days=6, hours=4, minutes=30)
        result = format_remaining(delta, short=True)
        assert "6d" in result
        assert "4h" in result
        assert "30m" in result
    
    def test_format_short_seconds(self):
        """Short format for seconds."""
        delta = timedelta(seconds=45)
        result = format_remaining(delta, short=True)
        assert "45s" in result
    
    def test_format_zero_duration(self):
        """Format zero duration."""
        delta = timedelta(0)
        result = format_remaining(delta)
        assert "time's up" in result.lower()
    
    def test_format_negative_duration(self):
        """Negative duration treated as zero."""
        delta = timedelta(days=-1)
        result = format_remaining(delta)
        assert "time's up" in result.lower()
    
    def test_format_singular_units(self):
        """Singular units (1 day, 1 hour, etc.)."""
        delta = timedelta(days=1, hours=1, minutes=1)
        result = format_remaining(delta)
        assert "1 day" in result
        assert "1 hour" in result
        assert "1 minute" in result


# =============================================================================
# Countdown Model Tests
# =============================================================================

class TestCountdown:
    """Tests for Countdown dataclass."""
    
    def test_create_countdown(self):
        """Can create a countdown with required fields."""
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        assert countdown.name == "test"
        assert countdown.channel == "lobby"
        assert countdown.created_by == "testuser"
        assert countdown.id is None
        assert countdown.completed is False
    
    def test_remaining_property(self):
        """remaining property returns correct timedelta."""
        target = datetime.now(timezone.utc) + timedelta(hours=2)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        remaining = countdown.remaining
        assert 7000 < remaining.total_seconds() < 7300
    
    def test_remaining_expired(self):
        """remaining returns zero for expired countdown."""
        target = datetime.now(timezone.utc) - timedelta(hours=1)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        assert countdown.remaining.total_seconds() == 0
    
    def test_is_expired_true(self):
        """is_expired returns True for past time."""
        target = datetime.now(timezone.utc) - timedelta(hours=1)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        assert countdown.is_expired is True
    
    def test_is_expired_false(self):
        """is_expired returns False for future time."""
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        assert countdown.is_expired is False
    
    def test_format_remaining_method(self):
        """format_remaining method works."""
        target = datetime.now(timezone.utc) + timedelta(hours=2, minutes=30)
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        result = countdown.format_remaining()
        assert "2 hours" in result
        assert "30 minutes" in result or "29 minutes" in result
    
    def test_to_dict(self):
        """to_dict returns serializable dictionary."""
        target = datetime(2025, 12, 25, 20, 0, 0, tzinfo=timezone.utc)
        countdown = Countdown(
            id=1,
            name="test",
            channel="lobby",
            target_time=target,
            created_by="testuser"
        )
        
        d = countdown.to_dict()
        
        assert d["id"] == 1
        assert d["name"] == "test"
        assert d["channel"] == "lobby"
        assert "2025-12-25" in d["target_time"]
        assert d["created_by"] == "testuser"
        assert d["completed"] is False
    
    def test_from_dict(self, sample_countdown_data):
        """from_dict creates Countdown from dictionary."""
        countdown = Countdown.from_dict(sample_countdown_data)
        
        assert countdown.id == 1
        assert countdown.name == "movie_night"
        assert countdown.channel == "lobby"
        assert countdown.created_by == "testuser"
        assert countdown.completed is False
    
    def test_from_dict_parses_datetime_strings(self, sample_countdown_data):
        """from_dict parses ISO datetime strings."""
        countdown = Countdown.from_dict(sample_countdown_data)
        
        assert isinstance(countdown.target_time, datetime)
        assert countdown.target_time.year == 2025
        assert countdown.target_time.month == 12
    
    def test_default_created_at(self):
        """created_at defaults to now."""
        before = datetime.now(timezone.utc)
        
        countdown = Countdown(
            name="test",
            channel="lobby",
            target_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by="testuser"
        )
        
        after = datetime.now(timezone.utc)
        
        assert before <= countdown.created_at <= after
