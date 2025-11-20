# SPEC-Commit-11: Testing Documentation

## Purpose

Create comprehensive testing documentation to enable developers to understand, run, and extend the test suite. This includes a detailed TESTING.md guide, updates to README.md, and documentation of fixtures and best practices.

## Scope

- **Documentation Files**: TESTING.md (new), README.md (updated)
- **Coverage**: Test running, writing tests, fixtures, troubleshooting
- **Audience**: Developers contributing to the project
- **Dependencies**:
  - All previous SPECs (1-10): Documents the complete test suite

## Documentation Structure

### File 1: TESTING.md (Primary Testing Guide)

Comprehensive guide covering all aspects of testing.

**Table of Contents**:
```markdown
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
```

**Section 1: Overview**
```markdown
## Overview

This project uses pytest for comprehensive test coverage across all components:

- **Testing Framework**: pytest with pytest-asyncio, pytest-cov, pytest-mock
- **Test Count**: 600+ tests across unit and integration suites
- **Coverage Target**: 85% overall (66% minimum floor)
- **Test Organization**: 
  - `tests/unit/` - Unit tests (isolated component testing)
  - `tests/integration/` - Integration tests (multi-component workflows)
  - `tests/fixtures/` - Shared test fixtures and utilities

### Test Coverage by Module

| Module | Tests | Coverage Target |
|--------|-------|----------------|
| lib/user.py | 40+ | 95% |
| lib/util.py | 60+ | 97% |
| lib/media_link.py | 85+ | 97% |
| lib/playlist.py | 65+ | 98% |
| lib/channel.py | 65+ | 98% |
| lib/bot.py | 85+ | 87% |
| common/database.py | 90+ | 90% |
| common/shell.py | 80+ | 85% |
| Integration | 30+ | N/A |
| **Total** | **600+** | **85%** |
```

**Section 2: Quick Start**
```markdown
## Quick Start

### Install Test Dependencies

```bash
# Install all test dependencies
pip install -r requirements.txt

# Or install individually
pip install pytest pytest-asyncio pytest-cov pytest-mock pytest-timeout freezegun
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
```

**Section 3: Test Organization**
```markdown
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
│   ├── test_user.py        # lib/user.py tests
│   ├── test_util.py        # lib/util.py tests
│   ├── test_media_link.py  # lib/media_link.py tests
│   ├── test_playlist.py    # lib/playlist.py tests
│   ├── test_channel.py     # lib/channel.py tests
│   ├── test_bot.py         # lib/bot.py tests
│   ├── test_database.py    # common/database.py tests
│   └── test_shell.py       # common/shell.py tests
├── integration/             # Integration tests (multi-component)
│   ├── __init__.py
│   ├── conftest.py         # Integration test fixtures
│   ├── test_bot_lifecycle.py
│   ├── test_shell_integration.py
│   ├── test_pm_flow.py
│   ├── test_persistence.py
│   ├── test_error_recovery.py
│   └── test_workflows.py
└── fixtures/                # Shared test data and utilities
    ├── __init__.py
    ├── sample_data.py      # Sample test data
    └── mock_helpers.py     # Mock object utilities
```

### Unit Tests vs Integration Tests

**Unit Tests** (`tests/unit/`):
- Test individual components in isolation
- Heavy use of mocking
- Fast execution (<1 second per test)
- Focus on edge cases and error handling
- Run frequently during development

**Integration Tests** (`tests/integration/`):
- Test multiple components together
- Minimal mocking (use real implementations)
- Slower execution (1-5 seconds per test)
- Focus on realistic workflows
- Run before commits and in CI
```

**Section 4: Running Tests**
```markdown
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
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows

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

# Skip slow tests
pytest -m "not slow" -v

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
```

**Section 5: Writing Tests**
```markdown
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
```

**Section 6: Test Fixtures**
```markdown
## Test Fixtures

### Common Fixtures (conftest.py)

#### Event Loop Fixture
```python
@pytest.fixture
def event_loop():
    """Event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

#### Mock Bot Fixture
```python
@pytest.fixture
def mock_bot():
    """Mock bot for testing"""
    bot = MagicMock()
    bot.user.name = "TestBot"
    bot.user.rank = 3.0
    bot.channel.name = "testchannel"
    return bot
```

#### Temporary Database Fixture
```python
@pytest.fixture
def temp_db(tmp_path):
    """Temporary database for testing"""
    db_path = str(tmp_path / "test.db")
    db = BotDatabase(db_path)
    yield db
    db.close()
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
```

**Section 7: Coverage Requirements**
```markdown
## Coverage Requirements

### Overall Targets

| Level | Coverage |
|-------|----------|
| Minimum Floor | 66% |
| Target | 85% |
| Stretch Goal | 90% |

### Per-Module Targets

| Module | Target | Notes |
|--------|--------|-------|
| lib/user.py | 95% | Simple data structures |
| lib/util.py | 97% | Pure functions |
| lib/media_link.py | 97% | URL parsing logic |
| lib/playlist.py | 98% | State management |
| lib/channel.py | 98% | Permission system |
| lib/bot.py | 87% | Complex async, 40+ handlers |
| common/database.py | 90% | CRUD operations |
| common/shell.py | 85% | Command parsing, networking |

### Coverage Configuration

**.coveragerc**:
```ini
[run]
source = lib, common
omit = 
    */tests/*
    */test_*.py
    */__pycache__/*

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
```

**Section 8: Continuous Integration**
```markdown
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
        python-version: [3.9, 3.10, 3.11]
    
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
        entry: pytest
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
```
```

**Section 9: Troubleshooting**
```markdown
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

# Or install project in editable mode
pip install -e .
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
```

#### Fixture Not Found

**Problem**: `fixture 'mock_bot' not found`

**Solution**:
- Check conftest.py exists in test directory
- Verify fixture is defined with @pytest.fixture
- Ensure fixture name matches parameter name

#### Coverage Not Updating

**Problem**: Coverage report shows 0% or old data

**Solution**:
```bash
# Clear coverage cache
rm -rf .coverage htmlcov/

# Re-run with fresh coverage
pytest --cov --cov-report=html
```

### Debug Mode

```bash
# Run single test with full output
pytest tests/unit/test_user.py::TestUserInit::test_init_basic -vv -s

# Drop into debugger on failure
pytest --pdb

# Show 10 slowest tests
pytest --durations=10
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
```
```

**Section 10: Best Practices**
```markdown
## Best Practices

### Test Organization

✅ **DO**:
- Group related tests in classes
- Use descriptive test names
- Test one thing per test
- Use fixtures for common setup
- Test both success and failure cases

❌ **DON'T**:
- Test multiple things in one test
- Use generic names like `test_1`, `test_2`
- Duplicate setup code across tests
- Rely on test execution order
- Leave commented-out code

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
- Verify mock interactions

❌ **DON'T**:
- Mock the code you're testing
- Over-mock (makes tests brittle)
- Use hardcoded mock data
- Forget to assert mock calls

### Async Testing

✅ **DO**:
```python
@pytest.mark.asyncio
async def test_async_method():
    mock = AsyncMock()
    result = await mock.async_method()
    mock.async_method.assert_called_once()
```

❌ **DON'T**:
```python
# Missing asyncio marker
async def test_async_method():  # Will fail!
    result = await async_method()
```

### Test Maintenance

✅ **DO**:
- Update tests when code changes
- Remove obsolete tests
- Keep tests simple and readable
- Document complex test scenarios
- Run full test suite before committing

❌ **DON'T**:
- Skip failing tests
- Comment out broken tests
- Let test code rot
- Commit without running tests
- Push with failing CI
```

### File 2: README.md Updates

Add testing section to existing README.md:

```markdown
## Testing

This project has comprehensive test coverage with 600+ tests across unit and integration suites.

### Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest --cov

# Run unit tests only (faster)
pytest tests/unit/ -v

# Generate coverage report
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Test Organization

- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test multi-component workflows
- **Coverage Target**: 85% overall (66% minimum floor)

### Documentation

See [TESTING.md](TESTING.md) for comprehensive testing guide including:
- Writing new tests
- Test fixtures and utilities
- Debugging test failures
- Best practices

### Running Specific Tests

```bash
# Run specific module tests
pytest tests/unit/test_user.py -v

# Run specific test
pytest tests/unit/test_user.py::TestUserInit::test_init_basic

# Run tests matching pattern
pytest -k "test_database" -v
```

### Coverage Requirements

| Module | Tests | Coverage |
|--------|-------|----------|
| lib/user.py | 40+ | 95% |
| lib/bot.py | 85+ | 87% |
| common/database.py | 90+ | 90% |
| common/shell.py | 80+ | 85% |
| Overall | 600+ | 85% |
```

## Implementation Checklist

### Phase 1: Create TESTING.md
- [ ] Write comprehensive overview section
- [ ] Document quick start commands
- [ ] Describe test organization
- [ ] Provide running tests guide
- [ ] Include writing tests section
- [ ] Document all fixtures
- [ ] Explain coverage requirements
- [ ] Add CI/CD section (planned future work)
- [ ] Create troubleshooting guide
- [ ] Document best practices

### Phase 2: Update README.md
- [ ] Add testing section to table of contents
- [ ] Write testing quick start
- [ ] Link to TESTING.md
- [ ] Add coverage table
- [ ] Document test commands

### Phase 3: Verification
- [ ] Proofread all documentation
- [ ] Verify all code examples are correct
- [ ] Test all command examples
- [ ] Check markdown formatting
- [ ] Ensure links work
- [ ] Validate coverage table matches SPECs

## Success Criteria

- ✅ TESTING.md created with all 10 sections
- ✅ README.md updated with testing section
- ✅ All code examples tested and working
- ✅ Coverage requirements documented
- ✅ Fixtures documented with examples
- ✅ Troubleshooting guide comprehensive
- ✅ Best practices clearly explained
- ✅ CI/CD section prepared (for future)
- ✅ Links and references valid
- ✅ Markdown formatting clean

## Dependencies

- **All SPECs 1-10**: Documents the complete test suite
- **Markdown**: Documentation format

## Implementation Notes

1. **Documentation Style**: Clear, concise, example-driven
2. **Code Examples**: All examples tested and working
3. **Audience**: Developers familiar with Python and pytest
4. **Scope**: Focus on practical guidance, not theory
5. **Maintenance**: Keep synchronized with test implementation
6. **Links**: Use relative links to ensure portability
7. **Coverage Tables**: Match targets from SPECs 1-10
8. **CI/CD**: Document planned future work, not current state
9. **Troubleshooting**: Include real issues encountered during development
10. **Best Practices**: Based on actual codebase patterns

## Notes

- **Purpose**: Enable developers to understand and extend test suite
- **Scope**: Comprehensive testing guide + README updates
- **Key Sections**: Running tests, writing tests, fixtures, troubleshooting
- **Style**: Practical, example-driven, developer-focused
- **Maintenance**: Living document, update as tests evolve
- **Future Work**: CI/CD integration documented but not implemented
- **Testing Strategy**: Document both unit and integration approaches
- **Next Step**: Ready for implementation - final SPEC in series!
