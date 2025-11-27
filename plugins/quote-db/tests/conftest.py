"""Pytest configuration and fixtures for quote-db plugin tests."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import json


@pytest.fixture
def mock_nats():
    """
    Create mock NATS client for testing.

    The mock client returns successful responses by default.
    Individual tests can override response behavior.
    """
    nats = AsyncMock()

    # Default response for migration status
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

    nats.request = AsyncMock(return_value=status_response)

    return nats


@pytest.fixture
def plugin(mock_nats):
    """
    Create QuoteDBPlugin instance with mock NATS client.

    Plugin is not initialized by default - tests should call
    plugin.initialize() as needed.
    """
    from quote_db import QuoteDBPlugin
    return QuoteDBPlugin(mock_nats)


@pytest_asyncio.fixture(scope="function")
async def initialized_plugin(plugin):
    """
    Create and initialize QuoteDBPlugin instance.

    Use this fixture when tests need an initialized plugin.
    """
    await plugin.initialize()
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
