"""
tests/conftest.py

Shared fixtures for 8ball plugin tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_nats():
    """Create a mock NATS client for testing."""
    nats = AsyncMock()
    nats.publish = AsyncMock()
    nats.subscribe = AsyncMock()
    
    # Track subscriptions
    nats._subscriptions = []
    
    async def mock_subscribe(subject, cb=None):
        sub = MagicMock()
        sub.subject = subject
        sub.callback = cb
        sub.unsubscribe = AsyncMock()
        nats._subscriptions.append(sub)
        return sub
    
    nats.subscribe = mock_subscribe
    
    return nats


@pytest.fixture
def mock_message():
    """Factory for creating mock NATS messages."""
    def _make_message(data: dict, reply_to: str = None):
        import json
        msg = MagicMock()
        msg.data = json.dumps(data).encode()
        msg.reply = reply_to
        return msg
    return _make_message
