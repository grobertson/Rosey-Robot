"""
Infrastructure smoke tests.

Verifies that the test infrastructure is set up correctly.
"""
import pytest


def test_pytest_working():
    """Verify pytest is working."""
    assert True


def test_fixtures_available(sample_config, mock_channel, mock_user):
    """Verify fixtures are available."""
    assert sample_config is not None
    assert mock_channel is not None
    assert mock_user is not None


@pytest.mark.asyncio
async def test_async_working():
    """Verify async tests work."""
    async def async_func():
        return 42

    result = await async_func()
    assert result == 42


@pytest.mark.unit
def test_unit_marker():
    """Verify unit marker works."""
    assert True


@pytest.mark.integration
def test_integration_marker():
    """Verify integration marker works."""
    assert True


def test_mock_available(mock_bot, mock_database):
    """Verify mock fixtures work."""
    assert mock_bot.connected is True
    assert mock_database is not None
