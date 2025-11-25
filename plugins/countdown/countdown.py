"""
plugins/countdown/countdown.py

Countdown model and datetime parsing utilities.

Provides:
- Countdown dataclass for representing countdown timers
- Datetime parsing for multiple user-friendly formats
- Human-readable time formatting
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# =============================================================================
# Datetime Parsing
# =============================================================================

# Patterns for relative time parsing
RELATIVE_PATTERNS = [
    # "in 2 hours", "in 30 minutes", "in 1 day"
    (r"in\s+(\d+)\s+(second|minute|hour|day|week)s?", "relative"),
    # "2 hours", "30 minutes" (without "in")
    (r"^(\d+)\s+(second|minute|hour|day|week)s?$", "relative_short"),
    # "tomorrow", "tomorrow 14:00"
    (r"tomorrow(?:\s+(\d{1,2}):(\d{2}))?", "tomorrow"),
]

# Patterns for absolute datetime parsing
DATETIME_PATTERNS = [
    # "2025-12-01 20:00" or "2025-12-01 20:00:00"
    (r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", "datetime"),
    # "2025-12-01T20:00:00" (ISO format)
    (r"(\d{4})-(\d{2})-(\d{2})T(\d{1,2}):(\d{2})(?::(\d{2}))?", "datetime_iso"),
    # "12/01/2025 20:00" (US format)
    (r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})", "datetime_us"),
]

# Time unit multipliers (in seconds)
TIME_UNITS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
}


def parse_datetime(time_str: str) -> datetime:
    """
    Parse user input into a datetime object.
    
    Supported formats:
    - "2025-12-01 20:00" or "2025-12-01 20:00:00"
    - "2025-12-01T20:00:00" (ISO format)
    - "12/01/2025 20:00" (US format: MM/DD/YYYY)
    - "tomorrow" or "tomorrow 14:00"
    - "in 2 hours", "in 30 minutes", "in 1 day"
    - "2 hours", "30 minutes" (shorthand)
    
    All times are treated as UTC.
    
    Args:
        time_str: User input string representing a time.
        
    Returns:
        datetime object in UTC.
        
    Raises:
        ValueError: If format not recognized or time is invalid.
    """
    time_str = time_str.strip().lower()
    now = datetime.now(timezone.utc)
    
    # Try relative patterns first
    for pattern, pattern_type in RELATIVE_PATTERNS:
        match = re.match(pattern, time_str, re.IGNORECASE)
        if match:
            if pattern_type in ("relative", "relative_short"):
                amount = int(match.group(1))
                unit = match.group(2).lower()
                seconds = amount * TIME_UNITS[unit]
                return now + timedelta(seconds=seconds)
            
            elif pattern_type == "tomorrow":
                tomorrow = now + timedelta(days=1)
                if match.group(1) and match.group(2):
                    # "tomorrow 14:00"
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    return tomorrow.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                else:
                    # "tomorrow" - same time as now
                    return tomorrow.replace(second=0, microsecond=0)
    
    # Try absolute datetime patterns
    for pattern, pattern_type in DATETIME_PATTERNS:
        match = re.match(pattern, time_str, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if pattern_type in ("datetime", "datetime_iso"):
                year = int(groups[0])
                month = int(groups[1])
                day = int(groups[2])
                hour = int(groups[3])
                minute = int(groups[4])
                second = int(groups[5]) if groups[5] else 0
                
            elif pattern_type == "datetime_us":
                month = int(groups[0])
                day = int(groups[1])
                year = int(groups[2])
                hour = int(groups[3])
                minute = int(groups[4])
                second = 0
            
            try:
                return datetime(
                    year, month, day, hour, minute, second,
                    tzinfo=timezone.utc
                )
            except ValueError as e:
                raise ValueError(f"Invalid date/time values: {e}")
    
    raise ValueError(
        f"Couldn't parse '{time_str}'. "
        "Try: '2025-12-01 20:00', 'tomorrow 19:00', or 'in 2 hours'"
    )


def format_remaining(delta: timedelta, short: bool = False) -> str:
    """
    Format a timedelta as a human-readable string.
    
    Args:
        delta: The time difference to format.
        short: If True, use abbreviated format (e.g., "6d 4h 30m").
        
    Returns:
        Human-readable time string.
    """
    if delta.total_seconds() <= 0:
        return "now" if short else "time's up!"
    
    total_seconds = int(delta.total_seconds())
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if short:
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)
    else:
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if not parts:
            if seconds > 0:
                parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            else:
                parts.append("less than a second")
        return ", ".join(parts)


# =============================================================================
# Countdown Model
# =============================================================================

@dataclass
class Countdown:
    """
    Represents a countdown timer.
    
    Attributes:
        id: Database ID (None if not yet persisted).
        name: User-friendly name for the countdown.
        channel: Channel where the countdown was created.
        target_time: When the countdown ends (UTC).
        created_by: Username who created the countdown.
        created_at: When the countdown was created (UTC).
        is_recurring: Whether this is a recurring countdown (Sortie 4).
        recurrence_rule: Rule for recurring countdowns (Sortie 4).
        completed: Whether the countdown has fired.
    """
    
    name: str
    channel: str
    target_time: datetime
    created_by: str
    id: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    completed: bool = False
    
    @property
    def remaining(self) -> timedelta:
        """
        Time remaining until target.
        
        Returns:
            timedelta, or zero if already expired.
        """
        now = datetime.now(timezone.utc)
        if now >= self.target_time:
            return timedelta(0)
        return self.target_time - now
    
    @property
    def is_expired(self) -> bool:
        """Check if countdown has passed."""
        return datetime.now(timezone.utc) >= self.target_time
    
    def format_remaining(self, short: bool = False) -> str:
        """
        Format remaining time as human-readable string.
        
        Args:
            short: If True, use abbreviated format (e.g., "6d 4h 30m").
            
        Returns:
            Formatted time string.
        """
        return format_remaining(self.remaining, short=short)
    
    def to_dict(self) -> dict:
        """
        Convert countdown to dictionary for JSON serialization.
        
        Returns:
            Dictionary suitable for NATS storage API.
        """
        return {
            "id": self.id,
            "name": self.name,
            "channel": self.channel,
            "target_time": self.target_time.isoformat(),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "is_recurring": self.is_recurring,
            "recurrence_rule": self.recurrence_rule,
            "completed": self.completed,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Countdown":
        """
        Create Countdown from dictionary (e.g., from NATS response).
        
        Args:
            data: Dictionary with countdown fields.
            
        Returns:
            Countdown instance.
        """
        # Parse datetime strings if needed
        target_time = data["target_time"]
        if isinstance(target_time, str):
            target_time = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
        
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif not created_at:
            created_at = datetime.now(timezone.utc)
        
        return cls(
            id=data.get("id"),
            name=data["name"],
            channel=data["channel"],
            target_time=target_time,
            created_by=data["created_by"],
            created_at=created_at,
            is_recurring=data.get("is_recurring", False),
            recurrence_rule=data.get("recurrence_rule"),
            completed=data.get("completed", False),
        )
