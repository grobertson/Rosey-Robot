"""
plugins/countdown/__init__.py

Countdown timer plugin for Rosey.

Provides event countdown functionality with:
- One-time countdowns to specific datetimes
- Automatic T-0 announcements
- Channel-scoped countdown tracking
- Persistent storage via NATS storage API
"""

from .countdown import Countdown, parse_datetime, format_remaining
from .plugin import CountdownPlugin

__all__ = [
    "Countdown",
    "CountdownPlugin",
    "parse_datetime",
    "format_remaining",
]
