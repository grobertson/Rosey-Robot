"""
Tests for countdown recurrence patterns.
"""

import pytest
from datetime import datetime, time, timezone

from countdown.recurrence import (
    RecurrenceRule, RecurrenceType, DAYS, _ordinal_suffix
)


class TestRecurrenceRuleParse:
    """Tests for RecurrenceRule.parse()."""
    
    def test_parse_daily(self):
        """Parse 'day 09:00' pattern."""
        rule = RecurrenceRule.parse("day 09:00")
        assert rule.type == RecurrenceType.DAILY
        assert rule.time_of_day == time(9, 0)
        assert rule.day_of_week is None
        assert rule.day_of_month is None
    
    def test_parse_daily_alternate(self):
        """Parse 'daily 09:00' pattern."""
        rule = RecurrenceRule.parse("daily 14:30")
        assert rule.type == RecurrenceType.DAILY
        assert rule.time_of_day == time(14, 30)
    
    def test_parse_weekly_full_name(self):
        """Parse 'friday 19:00' pattern."""
        rule = RecurrenceRule.parse("friday 19:00")
        assert rule.type == RecurrenceType.WEEKLY
        assert rule.time_of_day == time(19, 0)
        assert rule.day_of_week == 4  # Friday
    
    def test_parse_weekly_abbreviated(self):
        """Parse 'fri 19:00' pattern."""
        rule = RecurrenceRule.parse("fri 19:00")
        assert rule.type == RecurrenceType.WEEKLY
        assert rule.day_of_week == 4
    
    def test_parse_weekly_monday(self):
        """Parse 'monday 10:00' pattern."""
        rule = RecurrenceRule.parse("monday 10:00")
        assert rule.type == RecurrenceType.WEEKLY
        assert rule.day_of_week == 0
    
    def test_parse_weekly_sunday(self):
        """Parse 'sunday 12:00' pattern."""
        rule = RecurrenceRule.parse("sun 12:00")
        assert rule.type == RecurrenceType.WEEKLY
        assert rule.day_of_week == 6
    
    def test_parse_monthly_1st(self):
        """Parse '1st 12:00' pattern."""
        rule = RecurrenceRule.parse("1st 12:00")
        assert rule.type == RecurrenceType.MONTHLY
        assert rule.time_of_day == time(12, 0)
        assert rule.day_of_month == 1
    
    def test_parse_monthly_15th(self):
        """Parse '15th 14:00' pattern."""
        rule = RecurrenceRule.parse("15th 14:00")
        assert rule.type == RecurrenceType.MONTHLY
        assert rule.day_of_month == 15
    
    def test_parse_monthly_2nd(self):
        """Parse '2nd 09:00' pattern."""
        rule = RecurrenceRule.parse("2nd 09:00")
        assert rule.day_of_month == 2
    
    def test_parse_monthly_3rd(self):
        """Parse '3rd 09:00' pattern."""
        rule = RecurrenceRule.parse("3rd 09:00")
        assert rule.day_of_month == 3
    
    def test_parse_monthly_31st(self):
        """Parse '31st 23:59' pattern."""
        rule = RecurrenceRule.parse("31st 23:59")
        assert rule.day_of_month == 31
    
    def test_parse_case_insensitive(self):
        """Pattern parsing is case insensitive."""
        rule = RecurrenceRule.parse("FRIDAY 19:00")
        assert rule.type == RecurrenceType.WEEKLY
        assert rule.day_of_week == 4
    
    def test_parse_invalid_pattern(self):
        """Invalid pattern raises ValueError."""
        with pytest.raises(ValueError) as exc:
            RecurrenceRule.parse("invalid pattern")
        assert "Couldn't parse" in str(exc.value)
    
    def test_parse_invalid_day(self):
        """Unknown day name raises ValueError."""
        with pytest.raises(ValueError):
            RecurrenceRule.parse("funday 12:00")
    
    def test_parse_invalid_time_hour(self):
        """Invalid hour raises ValueError."""
        with pytest.raises(ValueError) as exc:
            RecurrenceRule.parse("friday 25:00")
        assert "Invalid hour" in str(exc.value)
    
    def test_parse_invalid_time_minute(self):
        """Invalid minute raises ValueError."""
        with pytest.raises(ValueError) as exc:
            RecurrenceRule.parse("friday 12:60")
        assert "Invalid minute" in str(exc.value)
    
    def test_parse_invalid_day_of_month(self):
        """Invalid day of month (32) raises ValueError."""
        with pytest.raises(ValueError):
            RecurrenceRule.parse("32nd 12:00")


class TestRecurrenceRuleNextOccurrence:
    """Tests for RecurrenceRule.next_occurrence()."""
    
    def test_daily_same_day_before(self):
        """Daily at 14:00, current time is 10:00 -> today."""
        rule = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(14, 0)
        )
        after = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.date() == after.date()
        assert result.hour == 14
        assert result.minute == 0
    
    def test_daily_same_day_after(self):
        """Daily at 14:00, current time is 15:00 -> tomorrow."""
        rule = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(14, 0)
        )
        after = datetime(2025, 1, 15, 15, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.date() == datetime(2025, 1, 16).date()
        assert result.hour == 14
    
    def test_weekly_same_week(self):
        """Friday 19:00, current is Wednesday -> this Friday."""
        rule = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4  # Friday
        )
        # Wednesday Jan 15, 2025
        after = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        # Should be Friday Jan 17
        assert result.weekday() == 4
        assert result.day == 17
        assert result.hour == 19
    
    def test_weekly_same_day_before_time(self):
        """Friday 19:00, current is Friday 10:00 -> today."""
        rule = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4
        )
        # Friday Jan 17, 2025 at 10:00
        after = datetime(2025, 1, 17, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.day == 17
        assert result.hour == 19
    
    def test_weekly_same_day_after_time(self):
        """Friday 19:00, current is Friday 20:00 -> next Friday."""
        rule = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4
        )
        # Friday Jan 17, 2025 at 20:00
        after = datetime(2025, 1, 17, 20, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        # Should be Friday Jan 24
        assert result.day == 24
        assert result.hour == 19
    
    def test_weekly_next_week(self):
        """Friday 19:00, current is Saturday -> next Friday."""
        rule = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4
        )
        # Saturday Jan 18, 2025
        after = datetime(2025, 1, 18, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        # Should be Friday Jan 24
        assert result.weekday() == 4
        assert result.day == 24
    
    def test_monthly_same_month(self):
        """1st at 12:00, current is Jan 15 -> Feb 1."""
        rule = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=1
        )
        after = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.month == 2
        assert result.day == 1
        assert result.hour == 12
    
    def test_monthly_before_day(self):
        """15th at 12:00, current is Jan 10 -> Jan 15."""
        rule = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=15
        )
        after = datetime(2025, 1, 10, 10, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.month == 1
        assert result.day == 15
    
    def test_monthly_31st_in_february(self):
        """31st clamped to 28/29 in February."""
        rule = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=31
        )
        # After Jan 31
        after = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        # February 2025 has 28 days
        assert result.month == 2
        assert result.day == 28
    
    def test_monthly_year_rollover(self):
        """December -> January next year."""
        rule = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=15
        )
        after = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
        result = rule.next_occurrence(after)
        
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
    
    def test_next_occurrence_default_now(self):
        """next_occurrence with no argument uses now."""
        rule = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(23, 59)
        )
        result = rule.next_occurrence()
        
        # Should be in the future
        assert result > datetime.now(timezone.utc)
    
    def test_next_occurrence_naive_datetime(self):
        """Naive datetime is treated as UTC."""
        rule = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(14, 0)
        )
        # Naive datetime
        after = datetime(2025, 1, 15, 10, 0)
        result = rule.next_occurrence(after)
        
        assert result.tzinfo == timezone.utc


class TestRecurrenceRuleSerialization:
    """Tests for to_string() and from_string()."""
    
    def test_daily_roundtrip(self):
        """Daily rule serializes and deserializes correctly."""
        original = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(9, 30)
        )
        
        serialized = original.to_string()
        restored = RecurrenceRule.from_string(serialized)
        
        assert restored.type == original.type
        assert restored.time_of_day == original.time_of_day
        assert restored.day_of_week is None
        assert restored.day_of_month is None
    
    def test_weekly_roundtrip(self):
        """Weekly rule serializes and deserializes correctly."""
        original = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4
        )
        
        serialized = original.to_string()
        restored = RecurrenceRule.from_string(serialized)
        
        assert restored.type == original.type
        assert restored.time_of_day == original.time_of_day
        assert restored.day_of_week == 4
    
    def test_monthly_roundtrip(self):
        """Monthly rule serializes and deserializes correctly."""
        original = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=15
        )
        
        serialized = original.to_string()
        restored = RecurrenceRule.from_string(serialized)
        
        assert restored.type == original.type
        assert restored.day_of_month == 15
    
    def test_from_string_invalid_format(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError):
            RecurrenceRule.from_string("invalid")
    
    def test_from_string_invalid_type(self):
        """Unknown type raises ValueError."""
        with pytest.raises(ValueError):
            RecurrenceRule.from_string("hourly|09:00||")
    
    def test_from_string_invalid_time(self):
        """Invalid time format raises ValueError."""
        with pytest.raises(ValueError):
            RecurrenceRule.from_string("daily|9:0||")


class TestRecurrenceRuleDescribe:
    """Tests for describe() method."""
    
    def test_describe_daily(self):
        """Describe daily pattern."""
        rule = RecurrenceRule(
            type=RecurrenceType.DAILY,
            time_of_day=time(9, 0)
        )
        desc = rule.describe()
        assert "Every day" in desc
        assert "09:00" in desc
    
    def test_describe_weekly(self):
        """Describe weekly pattern."""
        rule = RecurrenceRule(
            type=RecurrenceType.WEEKLY,
            time_of_day=time(19, 0),
            day_of_week=4
        )
        desc = rule.describe()
        assert "Friday" in desc
        assert "19:00" in desc
    
    def test_describe_monthly(self):
        """Describe monthly pattern."""
        rule = RecurrenceRule(
            type=RecurrenceType.MONTHLY,
            time_of_day=time(12, 0),
            day_of_month=1
        )
        desc = rule.describe()
        assert "1st" in desc
        assert "12:00" in desc


class TestOrdinalSuffix:
    """Tests for ordinal suffix helper."""
    
    def test_1st(self):
        assert _ordinal_suffix(1) == "st"
    
    def test_2nd(self):
        assert _ordinal_suffix(2) == "nd"
    
    def test_3rd(self):
        assert _ordinal_suffix(3) == "rd"
    
    def test_4th(self):
        assert _ordinal_suffix(4) == "th"
    
    def test_11th(self):
        assert _ordinal_suffix(11) == "th"
    
    def test_12th(self):
        assert _ordinal_suffix(12) == "th"
    
    def test_13th(self):
        assert _ordinal_suffix(13) == "th"
    
    def test_21st(self):
        assert _ordinal_suffix(21) == "st"
    
    def test_22nd(self):
        assert _ordinal_suffix(22) == "nd"
    
    def test_23rd(self):
        assert _ordinal_suffix(23) == "rd"


class TestDayMapping:
    """Tests for DAYS constant."""
    
    def test_all_days_present(self):
        """All day names and abbreviations present."""
        expected = ['monday', 'mon', 'tuesday', 'tue', 'wednesday', 'wed',
                    'thursday', 'thu', 'friday', 'fri', 'saturday', 'sat',
                    'sunday', 'sun']
        for day in expected:
            assert day in DAYS
    
    def test_monday_is_0(self):
        assert DAYS['monday'] == 0
        assert DAYS['mon'] == 0
    
    def test_sunday_is_6(self):
        assert DAYS['sunday'] == 6
        assert DAYS['sun'] == 6
