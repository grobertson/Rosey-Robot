"""
plugins/countdown/__init__.py

Countdown timer plugin for Rosey.

Provides event countdown functionality with:
- One-time countdowns to specific datetimes
- Recurring countdowns (daily, weekly, monthly)
- T-minus alerts (configurable warning intervals)
- Automatic T-0 announcements
- Channel-scoped countdown tracking
- Persistent storage via NATS storage API
"""

from .countdown import Countdown, parse_datetime, format_remaining
from .plugin import CountdownPlugin
from .recurrence import RecurrenceRule, RecurrenceType
from .alerts import AlertConfig, AlertManager

__all__ = [
    "Countdown",
    "CountdownPlugin",
    "parse_datetime",
    "format_remaining",
    "RecurrenceRule",
    "RecurrenceType",
    "AlertConfig",
    "AlertManager",
]
