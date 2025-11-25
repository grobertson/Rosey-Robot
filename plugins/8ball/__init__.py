"""
plugins/8ball/__init__.py

Magic 8-Ball fortune-telling plugin for Rosey.

Provides fortune-telling entertainment with:
- Classic 20 8-ball responses
- Rosey personality flavor text
- Configurable cooldown per user
- Event emission for analytics
"""

from .responses import (
    Category,
    EightBallResponse,
    ResponseSelector,
    POSITIVE_RESPONSES,
    NEUTRAL_RESPONSES,
    NEGATIVE_RESPONSES,
)
from .plugin import EightBallPlugin

__all__ = [
    "Category",
    "EightBallResponse",
    "ResponseSelector",
    "EightBallPlugin",
    "POSITIVE_RESPONSES",
    "NEUTRAL_RESPONSES",
    "NEGATIVE_RESPONSES",
]
