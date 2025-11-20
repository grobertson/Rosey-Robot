# SPEC: Test Infrastructure Setup

**Sprint:** nano-sprint/4-test-assured  
**Commit:** 1 - Infrastructure Setup  
**Dependencies:** None  
**Estimated Effort:** Medium

---

## Objective

Establish the pytest testing infrastructure with proper configuration, directory structure, and base fixtures. This creates the foundation for all subsequent test development.

---

## Changes Required

### 1. Create Test Directory Structure

**New Directory:** `tests/` at project root

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── unit/                 # Unit tests
│   └── __init__.py
├── integration/          # Integration tests
│   └── __init__.py
└── fixtures/             # Test data files
    ├── sample_config.json
    └── test_playlist.txt
```

### 2. Configure pytest

**File:** `pytest.ini` (new, project root)

```ini
[pytest]
# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test paths
testpaths = tests

# Output options
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings

# Markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, multiple components)
    asyncio: Async tests requiring event loop
    slow: Tests that take >1 second

# Asyncio configuration
asyncio_mode = auto
```

### 3. Configure Coverage

**File:** `.coveragerc` (new, project root)

```ini
[run]
source = lib, common, bot, web
omit =
    */tests/*
    */__pycache__/*
    */.venv/*
    */venv/*
    */examples/*
    */_old/*
    */test_*.py
    setup.py

[report]
precision = 2
show_missing = True
skip_covered = False

# Coverage thresholds
fail_under = 66.0

[html]
directory = htmlcov
```

### 4. Base Fixtures in conftest.py

**File:** `tests/conftest.py` (new)

```python
"""
Shared pytest fixtures for Rosey test suite.

This file contains fixtures that are available to all test files.
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock


@pytest.fixture
def event_loop():
    """
    Create event loop for async tests.
    
    This fixture ensures each test gets a fresh event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_config():
    """
    Sample bot configuration for testing.
    
    Returns:
        dict: Basic bot configuration with required fields
    """
    return {
        'channel': 'test_channel',
        'username': 'TestBot',
        'password': 'test_password',
        'server': 'wss://cytu.be:9443/socket.io/',
        'database': {
            'enabled': False  # Default to disabled for unit tests
        },
        'logging': {
            'level': 'WARNING'  # Reduce noise in tests
        }
    }


@pytest.fixture
def mock_websocket():
    """
    Mock websocket connection.
    
    Returns:
        AsyncMock: Mocked websocket with common methods
    """
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws


@pytest.fixture
def mock_channel():
    """
    Mock Channel instance.
    
    Returns:
        Mock: Channel with common attributes and methods
    """
    channel = Mock()
    channel.name = 'test_channel'
    channel.users = []
    channel.playlist = []
    channel.connected = True
    channel.send_chat = AsyncMock()
    channel.send_pm = AsyncMock()
    return channel


@pytest.fixture
def mock_user():
    """
    Mock User instance.
    
    Args:
        Can be parametrized with rank, username, etc.
    
    Returns:
        Mock: User with basic attributes
    """
    user = Mock()
    user.name = 'TestUser'
    user.rank = 1.0
    user.afk = False
    user.profile = {}
    return user


@pytest.fixture
def mock_database():
    """
    Mock Database instance.
    
    Returns:
        Mock: Database with common methods mocked
    """
    db = Mock()
    db.log_user_action = AsyncMock()
    db.log_media = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value={'id': 1, 'username': 'TestUser'})
    db.update_user_rank = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def sample_chat_event():
    """
    Sample chat event data.
    
    Returns:
        dict: Chat event in CyTube format
    """
    return {
        'username': 'TestUser',
        'msg': 'Hello, world!',
        'time': 1699747200000,  # Nov 11, 2024 (fixed timestamp for consistency)
        'meta': {}
    }


@pytest.fixture
def sample_pm_event():
    """
    Sample PM event data.
    
    Returns:
        dict: PM event in CyTube format
    """
    return {
        'username': 'ModUser',
        'to': 'TestBot',
        'msg': 'help',
        'time': 1699747200000
    }


@pytest.fixture
def sample_media():
    """
    Sample media item.
    
    Returns:
        dict: Media item in CyTube format
    """
    return {
        'id': 'yt_dQw4w9WgXcQ',
        'title': 'Test Video',
        'duration': 212,
        'type': 'yt',
        'uid': 'test_uid_123'
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """
    Create temporary config file for testing.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        sample_config: Sample configuration fixture
    
    Returns:
        Path: Path to temporary config.json file
    """
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(sample_config, indent=2))
    return config_file


@pytest.fixture
def mock_bot():
    """
    Mock Bot instance with common attributes.
    
    Returns:
        Mock: Bot with mocked channel, database, and methods
    """
    bot = Mock()
    bot.connected = True
    bot.channel = mock_channel()
    bot.db = None  # Tests can set this if needed
    bot.send_chat_message = AsyncMock()
    bot.pm = AsyncMock()
    return bot


# Test data files


@pytest.fixture
def sample_playlist_file(tmp_path):
    """
    Create sample playlist text file.
    
    Args:
        tmp_path: pytest's temporary directory fixture
    
    Returns:
        Path: Path to temporary playlist file
    """
    playlist_file = tmp_path / "test_playlist.txt"
    playlist_file.write_text(
        "https://youtube.com/watch?v=dQw4w9WgXcQ\n"
        "https://youtube.com/watch?v=9bZkp7q19f0\n"
        "# Comment line\n"
        "https://vimeo.com/123456789\n"
    )
    return playlist_file


# Pytest configuration helpers


def pytest_configure(config):
    """
    Pytest configuration hook.
    
    Registers custom markers.
    """
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "asyncio: Async tests")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")
```

### 5. Update requirements.txt

**File:** `requirements.txt` (update)

Add testing dependencies:

```pip-requirements
# Testing dependencies
pytest>=8.2.2
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
pytest-mock>=3.14.0
pytest-timeout>=2.3.0
freezegun>=1.5.0  # For mocking time
```

### 6. Create Sample Test Data Files

**File:** `tests/fixtures/sample_config.json` (new)

```json
{
  "channel": "test_channel",
  "username": "TestBot",
  "password": "test_password",
  "server": "wss://cytu.be:9443/socket.io/",
  "database": {
    "enabled": false
  }
}
```

**File:** `tests/fixtures/test_playlist.txt` (new)

```
https://youtube.com/watch?v=dQw4w9WgXcQ
https://youtube.com/watch?v=9bZkp7q19f0
# This is a comment
https://vimeo.com/123456789
https://dailymotion.com/video/x8abcde
```

### 7. Create Basic Smoke Test

**File:** `tests/test_infrastructure.py` (new)

```python
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
```

---

## Testing Checklist

### Manual Verification

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run pytest**
   ```bash
   pytest
   ```
   Expected: 6 tests pass

3. **Run with coverage**
   ```bash
   pytest --cov
   ```
   Expected: Coverage report generated (will be low initially)

4. **Run specific markers**
   ```bash
   pytest -m unit
   pytest -m integration
   ```
   Expected: Filtered tests run

5. **Run with verbose output**
   ```bash
   pytest -v
   ```
   Expected: Detailed test output

6. **Generate HTML coverage report**
   ```bash
   pytest --cov --cov-report=html
   ```
   Expected: `htmlcov/` directory created

7. **Verify fixtures**
   ```bash
   pytest --fixtures
   ```
   Expected: All custom fixtures listed

### Verification Commands

```bash
# Check pytest is installed
pytest --version

# List all fixtures
pytest --fixtures

# Run with maximum verbosity
pytest -vv

# Show coverage by file
pytest --cov --cov-report=term-missing

# Check configuration
pytest --co  # Collection only, no execution
```

---

## Success Criteria

- ✅ `tests/` directory structure created
- ✅ `pytest.ini` configured
- ✅ `.coveragerc` configured
- ✅ `conftest.py` with base fixtures
- ✅ Testing dependencies installed
- ✅ Sample test data files created
- ✅ Infrastructure smoke tests pass
- ✅ `pytest` command works without errors
- ✅ `pytest --cov` generates coverage report
- ✅ Custom markers work (unit, integration, asyncio)
- ✅ Fixtures are available to all tests

---

## Usage Examples

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run unit tests only
pytest -m unit

# Run specific test file
pytest tests/test_infrastructure.py

# Run specific test
pytest tests/test_infrastructure.py::test_pytest_working

# Run with verbose output
pytest -v

# Run and stop at first failure
pytest -x

# Run and show local variables on failure
pytest -l
```

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov --cov-report=term-missing

# HTML report
pytest --cov --cov-report=html
# Then open htmlcov/index.html

# Generate both
pytest --cov --cov-report=term-missing --cov-report=html
```

---

## Notes

- **Fixtures:** All fixtures in `conftest.py` are available to tests without import
- **Markers:** Use `@pytest.mark.unit` and `@pytest.mark.integration` to categorize tests
- **Async:** Use `@pytest.mark.asyncio` for async tests (auto-enabled in pytest.ini)
- **Coverage:** Initial coverage will be 0% - this is expected
- **Mock Strategy:** Fixtures provide mocked components; tests can customize as needed

---

## Troubleshooting

### Issue: pytest not found
**Solution:** Run `pip install -r requirements.txt`

### Issue: Import errors in tests
**Solution:** Ensure project root is in PYTHONPATH or run pytest from project root

### Issue: Async tests fail
**Solution:** Verify pytest-asyncio is installed and `asyncio_mode = auto` in pytest.ini

### Issue: Coverage report empty
**Solution:** This is expected initially; coverage will increase as tests are added

### Issue: Fixtures not found
**Solution:** Ensure `conftest.py` is in `tests/` directory with proper syntax

---

## Next Steps

After this commit:
1. Infrastructure is ready for test development
2. Begin with **SPEC-Commit-2: lib/user.py Tests** (simplest module)
3. Use fixtures from conftest.py
4. Follow unit test patterns established here

---

## Rollback Plan

If issues arise:
1. Remove `tests/` directory
2. Remove `pytest.ini` and `.coveragerc`
3. Revert requirements.txt changes
4. No code changes needed (infrastructure only)
