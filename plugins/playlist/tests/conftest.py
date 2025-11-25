"""
pytest configuration for playlist plugin tests.
"""

import sys
from pathlib import Path

# Add plugin directory to path for imports
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_nats():
    """Mock NATS client for testing."""
    mock = MagicMock()
    mock.subscribe = AsyncMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def playlist_config():
    """Default playlist configuration."""
    return {
        "max_queue_size": 100,
        "max_items_per_user": 5,
        "allowed_media_types": [],
        "emit_events": True,
        "admins": ["admin1"],
    }
