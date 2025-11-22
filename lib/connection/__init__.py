"""
Connection adapters for chat platforms.

This module provides abstract interfaces and concrete implementations
for connecting to various chat platforms (CyTube, Discord, Twitch, etc.).
"""

from .adapter import ConnectionAdapter
from .cytube import CyTubeConnection
from .errors import (
    AuthenticationError,
    ConnectionError,
    NotConnectedError,
    ProtocolError,
    SendError,
    UserNotFoundError,
)

__all__ = [
    'ConnectionAdapter',
    'CyTubeConnection',
    'ConnectionError',
    'AuthenticationError',
    'NotConnectedError',
    'SendError',
    'UserNotFoundError',
    'ProtocolError',
]
