"""
tests/conftest.py

Shared fixtures for countdown plugin tests.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_nats():
    """Create a mock NATS client for testing."""
    nats = AsyncMock()
    nats.publish = AsyncMock()
    
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
    
    # Default request handler (migration check passes)
    async def mock_request(subject, data, timeout=2.0):
        response = MagicMock()
        
        if "migrate" in subject and "status" in subject:
            # Migration status check - return version 2 for advanced features
            response.data = json.dumps({
                "success": True,
                "current_version": 2,
                "pending_count": 0
            }).encode()
        elif "select" in subject:
            # Default empty select result
            response.data = json.dumps({
                "rows": [],
                "count": 0
            }).encode()
        elif "insert" in subject:
            # Return new ID
            response.data = json.dumps({"id": 1}).encode()
        elif "update" in subject:
            response.data = json.dumps({"updated": 1}).encode()
        elif "delete" in subject:
            response.data = json.dumps({"deleted": 1}).encode()
        else:
            response.data = json.dumps({}).encode()
        
        return response
    
    nats.request = mock_request
    
    return nats


@pytest.fixture
def mock_message():
    """Factory for creating mock NATS messages."""
    def _make_message(data: dict, reply_to: str = None):
        msg = MagicMock()
        msg.data = json.dumps(data).encode()
        msg.reply = reply_to
        return msg
    return _make_message


@pytest.fixture
def sample_countdown_data():
    """Sample countdown data for testing."""
    return {
        "id": 1,
        "name": "movie_night",
        "channel": "lobby",
        "target_time": "2025-12-25T20:00:00+00:00",
        "created_by": "testuser",
        "created_at": "2025-11-24T10:00:00+00:00",
        "is_recurring": False,
        "recurrence_rule": None,
        "is_paused": False,
        "alert_minutes": None,
        "last_alert_sent": None,
        "completed": False,
    }
