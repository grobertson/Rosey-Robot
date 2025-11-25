"""Trivia question providers package."""

from .base import QuestionProvider
from .opentdb import OpenTDBProvider

__all__ = ["QuestionProvider", "OpenTDBProvider"]
