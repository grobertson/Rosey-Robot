"""
Recurrence pattern parsing and calculation for countdown plugin.

This module provides support for recurring countdowns like:
- "every day 09:00" - Daily at 09:00 UTC
- "every friday 19:00" - Weekly on Friday at 19:00 UTC
- "every 1st 12:00" - Monthly on the 1st at 12:00 UTC

All times are UTC. Pattern parsing is case-insensitive.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from datetime import timezone
from enum import Enum
from typing import Optional
import re
import calendar


class RecurrenceType(Enum):
    """Types of recurrence patterns."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Day name mapping (lowercase)
DAYS = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6,
}

# Day names for display
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


@dataclass
class RecurrenceRule:
    """
    Represents a recurrence pattern.
    
    Examples:
        "every day 09:00" -> RecurrenceRule(DAILY, time=09:00)
        "every friday 19:00" -> RecurrenceRule(WEEKLY, day_of_week=4, time=19:00)
        "every 1st 12:00" -> RecurrenceRule(MONTHLY, day_of_month=1, time=12:00)
    
    Attributes:
        type: The recurrence type (daily, weekly, monthly).
        time_of_day: The time (hour, minute) for the recurrence.
        day_of_week: For weekly, the day (0=Monday, 6=Sunday).
        day_of_month: For monthly, the day of month (1-31).
    """
    type: RecurrenceType
    time_of_day: time
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    day_of_month: Optional[int] = None  # 1-31
    
    def next_occurrence(self, after: Optional[datetime] = None) -> datetime:
        """
        Calculate the next occurrence after a given time.
        
        Args:
            after: Reference time (default: now UTC). If naive, assumed UTC.
            
        Returns:
            Next datetime when this recurrence occurs (UTC).
        """
        if after is None:
            after = datetime.now(timezone.utc)
        elif after.tzinfo is None:
            # Assume naive datetime is UTC
            after = after.replace(tzinfo=timezone.utc)
        
        if self.type == RecurrenceType.DAILY:
            return self._next_daily(after)
        elif self.type == RecurrenceType.WEEKLY:
            return self._next_weekly(after)
        elif self.type == RecurrenceType.MONTHLY:
            return self._next_monthly(after)
        else:
            raise ValueError(f"Unknown recurrence type: {self.type}")
    
    def _next_daily(self, after: datetime) -> datetime:
        """Calculate next daily occurrence."""
        # Try today at the target time
        candidate = after.replace(
            hour=self.time_of_day.hour,
            minute=self.time_of_day.minute,
            second=0,
            microsecond=0
        )
        
        if candidate <= after:
            # Already passed today, use tomorrow
            candidate += timedelta(days=1)
        
        return candidate
    
    def _next_weekly(self, after: datetime) -> datetime:
        """Calculate next weekly occurrence."""
        if self.day_of_week is None:
            raise ValueError("Weekly recurrence requires day_of_week")
        
        # Find next occurrence of the target day
        current_day = after.weekday()
        target_day = self.day_of_week
        
        # Calculate days until target day
        days_ahead = target_day - current_day
        if days_ahead < 0:
            days_ahead += 7
        
        candidate = after.replace(
            hour=self.time_of_day.hour,
            minute=self.time_of_day.minute,
            second=0,
            microsecond=0
        ) + timedelta(days=days_ahead)
        
        # If it's the same day but already passed, go to next week
        if days_ahead == 0 and candidate <= after:
            candidate += timedelta(days=7)
        
        return candidate
    
    def _next_monthly(self, after: datetime) -> datetime:
        """Calculate next monthly occurrence."""
        if self.day_of_month is None:
            raise ValueError("Monthly recurrence requires day_of_month")
        
        year = after.year
        month = after.month
        target_day = self.day_of_month
        
        # Clamp to valid day for this month
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(target_day, max_day)
        
        # Try this month
        candidate = datetime(
            year=year,
            month=month,
            day=actual_day,
            hour=self.time_of_day.hour,
            minute=self.time_of_day.minute,
            second=0,
            microsecond=0,
            tzinfo=timezone.utc
        )
        
        if candidate <= after:
            # Already passed this month, go to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            
            max_day = calendar.monthrange(year, month)[1]
            actual_day = min(target_day, max_day)
            
            candidate = datetime(
                year=year,
                month=month,
                day=actual_day,
                hour=self.time_of_day.hour,
                minute=self.time_of_day.minute,
                second=0,
                microsecond=0,
                tzinfo=timezone.utc
            )
        
        return candidate
    
    def to_string(self) -> str:
        """
        Serialize to string for storage.
        
        Format: "type|HH:MM|day_of_week|day_of_month"
        
        Returns:
            Serialized string.
        """
        time_str = f"{self.time_of_day.hour:02d}:{self.time_of_day.minute:02d}"
        dow = str(self.day_of_week) if self.day_of_week is not None else ""
        dom = str(self.day_of_month) if self.day_of_month is not None else ""
        return f"{self.type.value}|{time_str}|{dow}|{dom}"
    
    @classmethod
    def from_string(cls, rule_str: str) -> 'RecurrenceRule':
        """
        Parse from storage string.
        
        Args:
            rule_str: Serialized rule string.
            
        Returns:
            Parsed RecurrenceRule.
            
        Raises:
            ValueError: If format is invalid.
        """
        parts = rule_str.split("|")
        if len(parts) != 4:
            raise ValueError(f"Invalid rule format: {rule_str}")
        
        type_str, time_str, dow_str, dom_str = parts
        
        # Parse type
        try:
            rec_type = RecurrenceType(type_str)
        except ValueError:
            raise ValueError(f"Unknown recurrence type: {type_str}")
        
        # Parse time
        time_match = re.match(r'^(\d{2}):(\d{2})$', time_str)
        if not time_match:
            raise ValueError(f"Invalid time format: {time_str}")
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        time_of_day = time(hour=hour, minute=minute)
        
        # Parse day_of_week
        day_of_week = int(dow_str) if dow_str else None
        
        # Parse day_of_month
        day_of_month = int(dom_str) if dom_str else None
        
        return cls(
            type=rec_type,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            day_of_month=day_of_month
        )
    
    @classmethod
    def parse(cls, pattern: str) -> 'RecurrenceRule':
        """
        Parse user input into RecurrenceRule.
        
        Supported patterns:
            "day 09:00" or "daily 09:00" - Every day at 09:00
            "monday 10:00" or "mon 10:00" - Every Monday at 10:00
            "friday 19:00" or "fri 19:00" - Every Friday at 19:00
            "1st 12:00" - Every 1st of the month at 12:00
            "15th 14:00" - Every 15th of the month at 14:00
        
        Note: The "every" prefix should already be removed.
        
        Args:
            pattern: User-provided pattern string (without "every").
            
        Returns:
            Parsed RecurrenceRule.
            
        Raises:
            ValueError: If pattern not recognized.
        """
        pattern = pattern.strip().lower()
        
        # Try to match daily pattern: "day HH:MM" or "daily HH:MM"
        daily_match = re.match(r'^(?:day|daily)\s+(\d{1,2}):(\d{2})$', pattern)
        if daily_match:
            hour = int(daily_match.group(1))
            minute = int(daily_match.group(2))
            _validate_time(hour, minute)
            return cls(
                type=RecurrenceType.DAILY,
                time_of_day=time(hour=hour, minute=minute)
            )
        
        # Try to match weekly pattern: "<day_name> HH:MM"
        weekly_match = re.match(r'^(\w+)\s+(\d{1,2}):(\d{2})$', pattern)
        if weekly_match:
            day_name = weekly_match.group(1)
            hour = int(weekly_match.group(2))
            minute = int(weekly_match.group(3))
            
            if day_name in DAYS:
                _validate_time(hour, minute)
                return cls(
                    type=RecurrenceType.WEEKLY,
                    time_of_day=time(hour=hour, minute=minute),
                    day_of_week=DAYS[day_name]
                )
        
        # Try to match monthly pattern: "<N>st/nd/rd/th HH:MM"
        monthly_match = re.match(
            r'^(\d{1,2})(?:st|nd|rd|th)\s+(\d{1,2}):(\d{2})$', 
            pattern
        )
        if monthly_match:
            day_of_month = int(monthly_match.group(1))
            hour = int(monthly_match.group(2))
            minute = int(monthly_match.group(3))
            
            if 1 <= day_of_month <= 31:
                _validate_time(hour, minute)
                return cls(
                    type=RecurrenceType.MONTHLY,
                    time_of_day=time(hour=hour, minute=minute),
                    day_of_month=day_of_month
                )
            else:
                raise ValueError(f"Invalid day of month: {day_of_month}")
        
        raise ValueError(
            f"Couldn't parse pattern '{pattern}'. "
            "Try: 'friday 19:00', 'day 09:00', or '1st 12:00'"
        )
    
    def describe(self) -> str:
        """
        Human-readable description of the recurrence.
        
        Returns:
            Description like "Every Friday at 7:00 PM"
        """
        time_str = self.time_of_day.strftime("%H:%M")
        
        if self.type == RecurrenceType.DAILY:
            return f"Every day at {time_str}"
        elif self.type == RecurrenceType.WEEKLY:
            day_name = DAY_NAMES[self.day_of_week] if self.day_of_week is not None else "?"
            return f"Every {day_name} at {time_str}"
        elif self.type == RecurrenceType.MONTHLY:
            day = self.day_of_month or 0
            suffix = _ordinal_suffix(day)
            return f"Every {day}{suffix} at {time_str}"
        else:
            return f"Unknown pattern at {time_str}"


def _validate_time(hour: int, minute: int) -> None:
    """Validate hour and minute values."""
    if not (0 <= hour <= 23):
        raise ValueError(f"Invalid hour: {hour}. Must be 0-23.")
    if not (0 <= minute <= 59):
        raise ValueError(f"Invalid minute: {minute}. Must be 0-59.")


def _ordinal_suffix(n: int) -> str:
    """Get ordinal suffix for a number (st, nd, rd, th)."""
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
