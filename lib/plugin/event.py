"""
lib/plugin/event.py

Event structure for inter-plugin communication.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict


class EventPriority(IntEnum):
    """Event priority levels for dispatch ordering."""

    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class Event:
    """
    Event for inter-plugin communication.

    Attributes:
        name: Event name (e.g., 'trivia.started', 'quote.added')
        data: Event data (any JSON-serializable data)
        source: Name of plugin that published event
        priority: Event priority (affects dispatch order)
        timestamp: When event was created
    
    Example:
        event = Event(
            name='trivia.started',
            data={'question': 'What is 2+2?', 'timeout': 30},
            source='trivia_plugin',
            priority=EventPriority.HIGH
        )
    """

    name: str
    data: Dict[str, Any]
    source: str
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        """String representation for logging."""
        return f"Event({self.name} from {self.source})"

    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f"Event(name={self.name!r}, source={self.source!r}, "
            f"priority={self.priority.name}, data_keys={list(self.data.keys())})"
        )
