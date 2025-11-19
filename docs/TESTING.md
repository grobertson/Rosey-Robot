# Testing Guide

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Test Organization](#test-organization)
4. [Running Tests](#running-tests)
5. [Writing Tests](#writing-tests)
6. [Test Fixtures](#test-fixtures)
7. [Coverage Requirements](#coverage-requirements)
8. [Continuous Integration](#continuous-integration)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Overview

This project uses pytest for comprehensive test coverage across all components:

- **Testing Framework**: pytest with pytest-asyncio, pytest-cov, pytest-mock
- **Test Count**: 600+ tests across unit and integration suites
- **Coverage Target**: 85% overall (66% minimum floor)
- **Test Organization**: 
  - `tests/unit/` - Unit tests (isolated component testing)
  - `tests/integration/` - Integration tests (multi-component workflows)

### Test Coverage by Module

| Module | Tests | Coverage Target |
|--------|-------|----------------|
| lib/user.py | 48 | 100% |
| lib/util.py | 58 | 93% |
| lib/media_link.py | 75 | 100% |
| lib/playlist.py | 66 | 100% |
| lib/channel.py | 44 | 100% |
| lib/bot.py | 73 | 44% |
| common/database.py | 102 | 96% |
| common/shell.py | 65 | 86% |
| Integration | 30 | N/A |
| **Total** | **567** | **~92%** |

## Quick Start

### Install Test Dependencies

```bash
# Install all test dependencies
pip install -r requirements.txt

# Dependencies include:
# - pytest: Testing framework
# - pytest-asyncio: Async test support
# - pytest-cov: Coverage reporting
# - pytest-mock: Enhanced mocking
# - freezegun: Time mocking
```

### Run All Tests

```bash
# Run complete test suite with coverage
pytest --cov --cov-report=term-missing

# Run only unit tests (faster)
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v
```

### Check Coverage

```bash
# Generate detailed coverage report
pytest --cov --cov-report=html
# Opens htmlcov/index.html in browser

# Check if coverage meets minimum threshold (66%)
pytest --cov --cov-fail-under=66
```

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures for all tests
├── pytest.ini               # Pytest configuration
├── unit/                    # Unit tests (isolated components)
│   ├── __init__.py
│   ├── conftest.py         # Unit test fixtures
│   ├── test_user.py        # lib/user.py tests (48 tests)
│   ├── test_util.py        # lib/util.py tests (58 tests)
│   ├── test_media_link.py  # lib/media_link.py tests (75 tests)
│   ├── test_playlist.py    # lib/playlist.py tests (66 tests)
│   ├── test_channel.py     # lib/channel.py tests (44 tests)
│   ├── test_bot.py         # lib/bot.py tests (73 tests)
│   ├── test_database.py    # common/database.py tests (102 tests)
│   └── test_shell.py       # common/shell.py tests (65 tests)
└── integration/             # Integration tests (multi-component)
    ├── __init__.py
    ├── conftest.py         # Integration test fixtures
    ├── test_bot_lifecycle.py        # Bot lifecycle (6 tests)
    ├── test_shell_integration.py    # Shell commands (7 tests)
    ├── test_pm_commands.py          # PM flow (5 tests)
    ├── test_database_persistence.py # Persistence (5 tests)
    ├── test_error_recovery.py       # Error handling (4 tests)
    └── test_workflows.py            # End-to-end (3 tests)
```

### Unit Tests vs Integration Tests

**Unit Tests** (`tests/unit/`):
- Test individual components in isolation
- Heavy use of mocking
- Fast execution (<1 second per test)
- Focus on edge cases and error handling
- Run frequently during development
- 537 tests covering 8 modules

**Integration Tests** (`tests/integration/`):
- Test multiple components together
- Minimal mocking (use real implementations)
- Slower execution (1-5 seconds per test)
- Focus on realistic workflows
- Run before commits and in CI
- 30 tests covering 6 scenarios

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_user.py

# Run specific test class
pytest tests/unit/test_user.py::TestUserInit

# Run specific test
pytest tests/unit/test_user.py::TestUserInit::test_init_basic

# Run tests matching pattern
pytest -k "test_user" -v
```

### Coverage Commands

```bash
# Run with coverage
pytest --cov

# Coverage for specific module
pytest tests/unit/test_user.py --cov=lib.user

# Generate HTML coverage report
pytest --cov --cov-report=html
start htmlcov/index.html  # Windows
open htmlcov/index.html  # macOS

# Show missing lines
pytest --cov --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov --cov-fail-under=85
```

### Filtering and Selection

```bash
# Run only fast tests (unit tests)
pytest tests/unit/ -v

# Run only slow tests (integration)
pytest tests/integration/ -v

# Run tests marked with specific marker
pytest -m "asyncio" -v

# Stop on first failure
pytest -x

# Run last failed tests only
pytest --lf

# Run failed tests first, then rest
pytest --ff
```

### Debugging

```bash
# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Drop into debugger on failure
pytest --pdb

# Full traceback
pytest --tb=long

# Short traceback
pytest --tb=short

# Enable debug logging
pytest --log-cli-level=DEBUG
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4

# Auto-detect CPU count
pytest -n auto
```

## Writing Tests

### Test File Structure

```python
"""Tests for lib/example.py"""
import pytest
from lib import Example


class TestExampleInit:
    """Tests for Example initialization"""
    
    def test_init_basic(self):
        """Basic initialization works"""
        obj = Example("test")
        assert obj.name == "test"
    
    def test_init_with_options(self):
        """Initialization with options"""
        obj = Example("test", option=True)
        assert obj.option is True


class TestExampleMethods:
    """Tests for Example methods"""
    
    @pytest.mark.asyncio
    async def test_async_method(self):
        """Async methods work correctly"""
        obj = Example("test")
        result = await obj.async_method()
        assert result is not None
```

### Test Naming Conventions

**Test Files**: `test_<module>.py`
- `test_user.py` for `lib/user.py`
- `test_database.py` for `common/database.py`

**Test Classes**: `Test<ClassName><Aspect>`
- `TestUserInit` - Initialization tests
- `TestUserProperties` - Property tests
- `TestUserMethods` - Method tests

**Test Methods**: `test_<what>_<condition>`
- `test_init_basic` - Basic initialization
- `test_init_with_password` - Init with password
- `test_get_user_not_found` - Get user when not found

### Assertion Patterns

```python
# Basic assertions
assert value == expected
assert value is True
assert value in collection
assert isinstance(obj, MyClass)

# String assertions
assert "substring" in string
assert string.startswith("prefix")
assert string.endswith("suffix")

# Numeric assertions
assert value > 0
assert 0 <= value <= 100
assert abs(value - expected) < 0.001  # Floating point

# Collection assertions
assert len(collection) == 3
assert all(x > 0 for x in values)
assert any(x > 10 for x in values)

# Exception assertions
with pytest.raises(ValueError):
    function_that_raises()

with pytest.raises(ValueError, match="error message"):
    function_that_raises()
```

### Async Test Patterns

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await async_function()
    assert result is not None

@pytest.mark.asyncio
async def test_async_with_mock():
    """Test with async mock"""
    from unittest.mock import AsyncMock
    
    mock_obj = AsyncMock()
    mock_obj.method.return_value = "result"
    
    result = await mock_obj.method()
    assert result == "result"
    mock_obj.method.assert_called_once()
```

### Mocking Patterns

```python
from unittest.mock import Mock, MagicMock, AsyncMock, patch

# Basic mock
mock_obj = Mock()
mock_obj.method.return_value = "result"

# Mock with side effects
mock_obj.method.side_effect = [1, 2, 3]  # Different value each call
mock_obj.method.side_effect = Exception("Error")  # Raise exception

# Async mock
async_mock = AsyncMock()
async_mock.method.return_value = "async result"

# Patch module function
with patch('module.function') as mock_func:
    mock_func.return_value = "mocked"
    result = module.function()

# Patch object method
with patch.object(obj, 'method') as mock_method:
    mock_method.return_value = "mocked"
    result = obj.method()
```

## Test Fixtures

### Common Fixtures (conftest.py)

#### Mock Bot Fixture
```python
@pytest.fixture
def mock_bot():
    """Mock bot for testing"""
    bot = MagicMock()
    bot.user.name = "TestBot"
    bot.user.rank = 3.0
    bot.channel.name = "testchannel"
    bot.channel.userlist = MagicMock()
    bot.channel.playlist = MagicMock()
    bot.db = None
    bot.socket = MagicMock()
    bot.socket.connected = True
    return bot
```

#### Temporary Database Fixture
```python
@pytest.fixture
def temp_db(tmp_path):
    """Temporary database for testing"""
    from common.database import BotDatabase
    db_path = str(tmp_path / "test.db")
    db = BotDatabase(db_path)
    yield db
    db.close()
```

#### Integration Fixtures
```python
@pytest.fixture
def integration_bot(integration_db):
    """Bot instance with real database but mocked socket"""
    from lib.bot import Bot
    bot = Bot(
        domain="cytu.be",
        channel="test_integration",
        user="IntegrationTestBot"
    )
    bot.db = integration_db
    bot.socket = MagicMock()
    bot.socket.connected = True
    yield bot
```

### Using Fixtures

```python
def test_with_fixture(mock_bot):
    """Test uses mock_bot fixture"""
    assert mock_bot.user.name == "TestBot"

def test_with_multiple_fixtures(mock_bot, temp_db):
    """Test uses multiple fixtures"""
    temp_db.user_joined(mock_bot.user.name)
    stats = temp_db.get_user_stats(mock_bot.user.name)
    assert stats is not None
```

### Fixture Scopes

```python
@pytest.fixture(scope="function")  # Default: new instance per test
def per_test():
    return setup()

@pytest.fixture(scope="class")  # Shared within test class
def per_class():
    return setup()

@pytest.fixture(scope="module")  # Shared within module
def per_module():
    return setup()

@pytest.fixture(scope="session")  # Shared across all tests
def per_session():
    return setup()
```

### Fixture Cleanup

```python
@pytest.fixture
def resource():
    """Fixture with cleanup"""
    res = acquire_resource()
    yield res
    res.cleanup()  # Cleanup after test
```

## Coverage Requirements

### Overall Targets

| Level | Coverage |
|-------|----------|
| Minimum Floor | 66% |
| Target | 85% |
| Current Average | ~92% |

### Per-Module Targets

| Module | Tests | Coverage | Target |
|--------|-------|----------|--------|
| lib/user.py | 48 | 100% | 95% |
| lib/util.py | 58 | 93% | 93% |
| lib/media_link.py | 75 | 100% | 97% |
| lib/playlist.py | 66 | 100% | 98% |
| lib/channel.py | 44 | 100% | 98% |
| lib/bot.py | 73 | 44% | 85% |
| common/database.py | 102 | 96% | 90% |
| common/shell.py | 65 | 86% | 85% |

### Coverage Configuration

**pytest.ini**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -ra
    --strict-markers
    --cov-report=term-missing:skip-covered
    --cov-config=.coveragerc

markers =
    asyncio: marks tests as async (deselect with '-m "not asyncio"')
    slow: marks tests as slow (deselect with '-m "not slow"')
```

**.coveragerc**:
```ini
[run]
source = lib, common
omit = 
    */tests/*
    */test_*.py
    */__pycache__/*
    */_old/*

[report]
precision = 2
show_missing = True
skip_covered = False
fail_under = 66

[html]
directory = htmlcov
```

### Checking Coverage

```bash
# Overall coverage
pytest --cov

# Per-module coverage
pytest tests/unit/test_user.py --cov=lib.user --cov-report=term-missing

# Fail if below threshold
pytest --cov --cov-fail-under=85

# Generate HTML report
pytest --cov --cov-report=html
```

## Continuous Integration

### CI Workflow (Future)

This section documents the planned CI/CD setup for future implementation:

#### GitHub Actions (Planned)

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov --cov-report=xml --cov-fail-under=66
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

#### Pre-commit Hooks (Planned)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/ -x
        language: system
        pass_filenames: false
        always_run: true
```

### Local Pre-commit Testing

```bash
# Run tests before committing
pytest tests/unit/ -x  # Stop on first failure

# Quick smoke test
pytest tests/unit/test_user.py tests/unit/test_util.py -v

# Full test suite
pytest --cov --cov-fail-under=85
```

## Troubleshooting

### Common Issues

#### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'lib'`

**Solution**:
```bash
# Ensure you're in the project root
cd /path/to/Rosey-Robot

# Run tests with python -m pytest
python -m pytest

# Or ensure paths are correct
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### Async Test Failures

**Problem**: `RuntimeError: Event loop is closed`

**Solution**:
```python
# Use pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async():
    result = await async_function()
    assert result is not None

# Or add to module top:
pytestmark = pytest.mark.asyncio
```

#### Database Lock Errors

**Problem**: `sqlite3.OperationalError: database is locked`

**Solution**:
```python
# Ensure database cleanup in fixtures
@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = BotDatabase(db_path)
    yield db
    db.close()  # Always close!

# Or handle in test teardown
try:
    if db.conn:
        db.close()
except:
    pass
```

#### Fixture Not Found

**Problem**: `fixture 'mock_bot' not found`

**Solution**:
- Check conftest.py exists in test directory
- Verify fixture is defined with @pytest.fixture
- Ensure fixture name matches parameter name
- Check fixture scope allows access

#### Coverage Not Updating

**Problem**: Coverage report shows 0% or old data

**Solution**:
```bash
# Clear coverage cache
rm -rf .coverage htmlcov/ .pytest_cache/

# Re-run with fresh coverage
pytest --cov --cov-report=html
```

#### Windows Path Issues

**Problem**: Tests fail on Windows with path separators

**Solution**:
```python
# Use pathlib for cross-platform paths
from pathlib import Path
db_path = Path(tmp_path) / "test.db"

# Or use os.path
import os
db_path = os.path.join(tmp_path, "test.db")
```

### Debug Mode

```bash
# Run single test with full output
pytest tests/unit/test_user.py::TestUserInit::test_init_basic -vv -s

# Drop into debugger on failure
pytest --pdb

# Show 10 slowest tests
pytest --durations=10

# Show all durations
pytest --durations=0
```

### Performance Issues

```bash
# Profile test execution time
pytest --durations=0  # Show all durations

# Run tests in parallel
pip install pytest-xdist
pytest -n auto

# Skip slow integration tests
pytest tests/unit/ -v

# Run only fast tests
pytest -m "not slow" -v
```

## Best Practices

### Test Organization

✅ **DO**:
- Group related tests in classes
- Use descriptive test names that explain what's being tested
- Test one specific behavior per test
- Use fixtures for common setup
- Test both success and failure cases
- Keep tests independent and isolated

❌ **DON'T**:
- Test multiple unrelated things in one test
- Use generic names like `test_1`, `test_2`
- Duplicate setup code across tests
- Rely on test execution order
- Leave commented-out code
- Skip tests without good reason

### Assertion Style

✅ **DO**:
```python
# Specific assertions
assert user.name == "alice"
assert len(userlist) == 3
assert "error" in result.lower()

# Multiple assertions for related checks
def test_user_init():
    user = User("alice", rank=2.0)
    assert user.name == "alice"
    assert user.rank == 2.0
    assert user.afk is False
```

❌ **DON'T**:
```python
# Vague assertions
assert user  # What are we checking?
assert result  # Too generic

# Unrelated assertions in same test
def test_everything():
    assert user.name == "alice"
    assert database.get_stats()  # Unrelated
    assert shell.parse("cmd")  # Unrelated
```

### Mocking Strategy

✅ **DO**:
- Mock external dependencies (network, filesystem)
- Mock components you're not testing
- Use realistic mock data
- Verify mock interactions with assertions
- Use AsyncMock for async methods

❌ **DON'T**:
- Mock the code you're testing
- Over-mock (makes tests brittle)
- Use hardcoded mock data that doesn't match reality
- Forget to assert mock calls
- Mock when you could use a real object

### Async Testing

✅ **DO**:
```python
@pytest.mark.asyncio
async def test_async_method():
    mock = AsyncMock()
    mock.method.return_value = "result"
    result = await mock.method()
    assert result == "result"
    mock.method.assert_called_once()
```

❌ **DON'T**:
```python
# Missing asyncio marker
async def test_async_method():  # Will fail!
    result = await async_method()

# Using Mock instead of AsyncMock
mock = Mock()  # Wrong! Use AsyncMock for async
result = await mock.async_method()
```

### Test Maintenance

✅ **DO**:
- Update tests when code changes
- Remove obsolete tests promptly
- Keep tests simple and readable
- Document complex test scenarios
- Run full test suite before committing
- Review test failures carefully

❌ **DON'T**:
- Skip failing tests without fixing them
- Comment out broken tests
- Let test code become outdated
- Commit without running tests
- Ignore coverage drops
- Push with failing CI

### Integration Test Guidelines

✅ **DO**:
- Use real components (Database, Shell, Bot logic)
- Mock only external I/O (socket connections)
- Test realistic workflows
- Ensure proper cleanup (close databases, cancel tasks)
- Use isolated test databases (tmp_path)

❌ **DON'T**:
- Mock everything (defeats integration testing purpose)
- Share state between tests
- Rely on external services
- Skip cleanup (causes resource leaks)
- Test trivial integrations (use unit tests)

### Coverage Best Practices

✅ **DO**:
- Aim for 85%+ coverage
- Focus on testing behavior, not just coverage percentage
- Document why certain code isn't covered
- Test error paths and edge cases
- Use coverage to find untested code

❌ **DON'T**:
- Write tests just to increase coverage percentage
- Ignore uncovered critical paths
- Test implementation details instead of behavior
- Skip error handling tests
- Assume 100% coverage means bug-free code
