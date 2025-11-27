"""Pytest configuration and fixtures for quote-db plugin tests."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import json


@pytest.fixture
def mock_nats():
    """
    Create mock NATS client for testing.

    Returns AsyncMock with no default configuration.
    Tests should set return_value or side_effect as needed.
    """
    nats = AsyncMock()
    nats.request = AsyncMock()
    return nats


@pytest.fixture
def plugin(mock_nats):
    """
    Create QuoteDBPlugin instance with mock NATS client.

    Plugin is not initialized by default - tests that need initialization
    should set up mock responses and call plugin.initialize().
    Or use initialized_plugin fixture instead.
    """
    from quote_db import QuoteDBPlugin
    return QuoteDBPlugin(mock_nats)


@pytest_asyncio.fixture(scope="function")
async def initialized_plugin(mock_nats):
    """
    Create and initialize QuoteDBPlugin instance.

    Use this fixture when tests need an initialized plugin.
    Creates plugin with the mock_nats fixture and initializes it.
    Tests can then override mock_nats.request.return_value for their needs.
    """
    from quote_db import QuoteDBPlugin
    plugin = QuoteDBPlugin(mock_nats)
    
    # Temporarily configure mock for initialization (2 calls)
    status_response = MagicMock()
    status_response.data = json.dumps({
        "success": True,
        "current_version": 3,
        "pending_count": 0,
        "applied_migrations": [
            {"version": 1, "name": "create_quotes_table"},
            {"version": 2, "name": "add_score_column"},
            {"version": 3, "name": "add_tags_column"}
        ]
    }).encode()
    
    schema_response = MagicMock()
    schema_response.data = json.dumps({"success": True}).encode()
    
    # Save any existing side_effect the test may have set
    original_side_effect = mock_nats.request.side_effect
    original_return_value = mock_nats.request.return_value
    
    # Set up for initialization
    mock_nats.request.side_effect = [status_response, schema_response]
    mock_nats.request.return_value = None
    
    # Initialize
    await plugin.initialize()
    
    # Restore original mock configuration
    mock_nats.request.side_effect = original_side_effect
    mock_nats.request.return_value = original_return_value
    
    return plugin


@pytest.fixture
def sample_quote():
    """Sample quote data for testing."""
    return {
        "id": 1,
        "text": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
        "added_by": "alice",
        "added_at": "2025-11-24T10:00:00Z",
        "score": 42,
        "tags": ["motivational", "work"]
    }


@pytest.fixture
def sample_quotes():
    """Multiple sample quotes for testing."""
    return [
        {
            "id": 1,
            "text": "The only way to do great work is to love what you do.",
            "author": "Steve Jobs",
            "added_by": "alice",
            "score": 42,
            "tags": ["motivational"]
        },
        {
            "id": 2,
            "text": "In the middle of difficulty lies opportunity.",
            "author": "Albert Einstein",
            "added_by": "bob",
            "score": 38,
            "tags": ["wisdom"]
        },
        {
            "id": 3,
            "text": "Life is what happens when you're busy making other plans.",
            "author": "John Lennon",
            "added_by": "alice",
            "score": 50,
            "tags": ["life"]
        }
    ]
