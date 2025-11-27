# Testing Guide

**Last Updated**: November 27, 2025  
**Sprint**: 20 - Test Infrastructure Fixes

---

## Overview

This document describes testing patterns, best practices, and infrastructure for the Rosey-Robot project. Our test suite includes unit tests, integration tests, and performance tests, with a focus on reliability, maintainability, and developer productivity.

### Test Suite Metrics

- **Total Tests**: 2,340+ tests
- **Pass Rate**: 99.8%+ (2,213+ passing)
- **Coverage Target**: 85% (minimum 66%)
- **Test Categories**: Unit (2,100+), Integration (180+), Performance (5)

---

## Table of Contents

1. [Running Tests](#running-tests)
2. [Test Organization](#test-organization)
3. [Testing Patterns](#testing-patterns)
4. [Common Issues & Solutions](#common-issues--solutions)
5. [Performance Testing](#performance-testing)
6. [Integration Testing](#integration-testing)
7. [Contributing Guidelines](#contributing-guidelines)

---

## Running Tests

### Quick Start

```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Run single test
pytest tests/unit/test_database_row.py::TestRowInsert::test_insert_single_row -xvs
```

### Test Categories

| Category | Path | Count | Purpose |
|----------|------|-------|---------|
| Unit Tests | `tests/unit/` | 2,100+ | Test individual components in isolation |
| Integration Tests | `tests/integration/` | 180+ | Test component interactions (NATS, database, shell) |
| Performance Tests | `tests/performance/` | 5 | Validate query performance and benchmarks |

### Common Test Flags

```powershell
-v              # Verbose output
-x              # Stop on first failure
-s              # Show print statements
--tb=short      # Short traceback format
--lf            # Run last failed tests
--co            # Collect only (show tests without running)
-k "pattern"    # Run tests matching pattern
--maxfail=3     # Stop after N failures
```

---

## Test Organization

### Directory Structure

```
tests/
├── unit/                      # Unit tests (fast, isolated)
│   ├── test_database_row.py          # Row API tests (60 tests)
│   ├── test_schema_registry.py       # Schema registration (36 tests)
│   ├── test_shell.py                 # Shell command tests (40 tests)
│   └── database/                     # Database subsystem tests
├── integration/               # Integration tests (slower, multi-component)
│   ├── test_row_nats.py             # Row NATS handlers (51 tests)
│   ├── test_shell_integration.py    # Shell integration (7 tests)
│   └── test_workflows.py            # End-to-end workflows
├── performance/               # Performance benchmarks
│   ├── test_sql_benchmarks.py       # SQL performance (5 tests)
│   ├── baseline.json                # Performance baselines
│   └── baseline_loader.py           # Baseline utilities
└── conftest.py                # Shared fixtures
```

### Test Naming Conventions

- **Test Files**: `test_<module>.py` (e.g., `test_database_row.py`)
- **Test Classes**: `Test<Feature>` (e.g., `TestRowInsert`)
- **Test Functions**: `test_<behavior>` (e.g., `test_insert_single_row`)

**Examples**:
```python
# Good test names (describe behavior)
def test_insert_validates_required_fields()
def test_register_schema_creates_table()
def test_search_with_filters_via_nats()

# Avoid (too generic or unclear)
def test_insert()  # What aspect of insert?
def test_case1()   # What does case1 test?
```

---

## Testing Patterns

### 1. Schema Registration Pattern

**Problem**: Tests need database tables for row operations  
**Solution**: Use `schema_registry` fixture and register schemas before operations

```python
@pytest.fixture
async def db():
    """Create test database with in-memory storage."""
    database = BotDatabase(':memory:')
    # Tables created via schema registration
    await database.connect()
    yield database
    await database.close()

async def test_row_operations(db):
    """Test row insert after schema registration."""
    # Register schema first
    schema = {
        "fields": [
            {"name": "text", "type": "string", "required": True},
            {"name": "author", "type": "string"}
        ]
    }
    await db.schema_registry.register_schema("test", "quotes", schema)
    
    # Now row operations work
    result = await db.row_insert("test", "quotes", {"text": "Hello"})
    assert result["created"] is True
```

**Key Points**:
- Always register schemas before row operations
- Use descriptive plugin and table names (`"test"`, `"quotes"`)
- Schema includes `fields` with `name`, `type`, and optional `required`
- Auto-managed fields: `id`, `created_at`, `updated_at` (added automatically)

### 2. Event-Driven Testing Pattern

**Problem**: Shell commands now publish NATS events instead of calling APIs directly  
**Solution**: Mock `event_bus` and assert on published events

```python
async def test_shell_add_command_publishes_event(mock_bot):
    """Test !add command publishes playlist.add event."""
    # Mock event bus
    mock_bot.event_bus = Mock()
    mock_bot.event_bus.publish = AsyncMock()
    
    # Execute command
    await mock_bot.shell.handle_command(
        "!add https://youtube.com/watch?v=abc123",
        username="testuser",
        is_moderator=True
    )
    
    # Verify event published
    mock_bot.event_bus.publish.assert_called_once()
    
    # Verify event structure
    call_args = mock_bot.event_bus.publish.call_args
    event = call_args[0][0]
    
    assert event.subject == "rosey.platform.cytube.send.playlist.add"
    assert event.data["command"] == "playlist.add"
    assert event.data["params"]["type"] == "yt"
    assert event.data["params"]["id"] == "abc123"
    assert "correlation_id" in event.data
```

**Key Points**:
- Mock `event_bus.publish` as `AsyncMock`
- Verify event `subject` matches expected NATS subject pattern
- Verify event `data` contains correct command and params
- Always check for `correlation_id` in event data

### 3. In-Memory Database Testing Pattern

**Problem**: SQLite `:memory:` databases are per-connection  
**Solution**: Use `run_sync()` pattern to ensure same database connection

```python
# ❌ WRONG: Creates separate sync engine (isolated database)
def _create_table_sync(self):
    sync_engine = create_engine('sqlite://')  # Separate database!
    metadata.create_all(sync_engine)

# ✅ CORRECT: Uses async engine's connection
async def _create_table(self):
    async with self.engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: metadata.create_all(sync_conn))
```

**Key Points**:
- Always use `engine.begin()` context for transactions
- Use `run_sync()` to execute sync SQLAlchemy code on async connection
- Never create separate sync engines for in-memory databases
- Let `begin()` context manage commits (no manual `commit()` calls)

### 4. Performance Baseline Pattern

**Problem**: Hardcoded performance expectations fail with system variation  
**Solution**: Use calibrated baselines with tolerance

```python
# tests/performance/baseline.json
{
    "simple_select_validation": {
        "baseline": 300,
        "min_acceptable": 240,
        "metric": "ops_per_sec"
    }
}

# Test using baseline
async def test_simple_select_validation():
    # Run benchmark
    ops_per_sec = await run_benchmark()
    
    # Load baseline
    min_acceptable = get_min_acceptable("simple_select_validation", "ops_per_sec")
    
    # Assert with tolerance
    assert ops_per_sec >= min_acceptable, \
        f"Performance degraded: {ops_per_sec} ops/sec (min: {min_acceptable})"
    
    # Log performance
    log_performance("simple_select_validation", ops_per_sec, 300, "ops_per_sec")
```

**Key Points**:
- Use `baseline.json` for target values and tolerances (typically 20%)
- Assert on `min_acceptable`, not hardcoded values
- Log actual vs baseline for CI metrics
- Calibrate baselines on representative hardware

### 5. Async Fixture Pattern

**Problem**: Fixtures need async setup/teardown  
**Solution**: Use `async def` fixtures with proper cleanup

```python
@pytest.fixture
async def db():
    """Database fixture with proper async lifecycle."""
    database = BotDatabase(':memory:')
    await database.connect()
    
    yield database
    
    # Wait for pending tasks before cleanup
    await asyncio.sleep(0.1)
    await database.close()
```

**Key Points**:
- Use `async def` for fixtures requiring async operations
- Always await `connect()` before yield
- Add small delay before cleanup to let background tasks finish
- Always await `close()` in cleanup

---

## Common Issues & Solutions

### Issue 1: "no such table" Errors in Unit Tests

**Symptom**: Tests fail with `OperationalError: no such table: test_quotes`

**Root Cause**: Synchronous engine creation creates isolated in-memory database

**Solution**: Use `run_sync()` pattern on async engine's connection

```python
# Fix in common/schema_registry.py and common/database.py
async def _create_table(self):
    async with self.db.engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: metadata.create_all(sync_conn))
```

**See**: Sprint 20 Unit Test Fixes (commit cd50bca)

### Issue 2: Flaky Performance Tests

**Symptom**: Tests pass/fail intermittently based on system load

**Root Cause**: Hardcoded performance expectations don't account for variation

**Solution**: Implement baseline system with tolerance

```python
# Use baseline.json with 20% tolerance
min_acceptable = get_min_acceptable("test_name", "ops_per_sec")
assert actual >= min_acceptable
```

**See**: Sprint 20 Performance Baseline System (commit 04f5569)

### Issue 3: Shell Integration Tests Failing After Sprint 19

**Symptom**: `add_media.assert_called_once()` fails

**Root Cause**: Shell commands now publish NATS events instead of calling APIs

**Solution**: Mock `event_bus` and assert on published events

```python
# Update test to verify event publishing
mock_bot.event_bus.publish.assert_called_once()
event = mock_bot.event_bus.publish.call_args[0][0]
assert event.subject == "rosey.platform.cytube.send.playlist.add"
```

**See**: Sprint 20 Shell Integration Fixes (commit 893ba6a)

### Issue 4: Row NATS Tests Failing with Task Cancellation

**Symptom**: Tests fail with `asyncio.CancelledError` in NATS handlers

**Root Cause**: NATS handlers run in background tasks that get cancelled during test cleanup

**Solution**: Track handler tasks and cancel gracefully in fixtures

```python
@pytest.fixture
async def nats_with_bot(nats_server, integration_bot):
    handler_task = asyncio.create_task(listen_for_events())
    yield
    # Cancel handler task before cleanup
    handler_task.cancel()
    try:
        await handler_task
    except asyncio.CancelledError:
        pass
```

**See**: Sprint 20 Row NATS Fixes (commit 3c75619)

---

## Performance Testing

### Baseline System

Performance tests use a calibrated baseline system to handle system variation:

1. **Baseline File** (`tests/performance/baseline.json`):
   ```json
   {
       "test_name": {
           "baseline": 300,
           "min_acceptable": 240,
           "metric": "ops_per_sec"
       }
   }
   ```

2. **Baseline Loader** (`tests/performance/baseline_loader.py`):
   - `load_baseline()` - Load baseline configuration
   - `get_min_acceptable()` - Get minimum acceptable value
   - `log_performance()` - Log actual vs baseline

3. **Test Pattern**:
   ```python
   async def test_benchmark():
       actual = await run_benchmark()
       expected = get_baseline_value("test_name", "ops_per_sec")
       min_acceptable = get_min_acceptable("test_name", "ops_per_sec")
       
       assert actual >= min_acceptable
       log_performance("test_name", actual, expected, "ops_per_sec")
   ```

### Current Benchmarks

| Test | Baseline | Min Acceptable | Metric |
|------|----------|----------------|--------|
| simple_select_validation | 300 | 240 | ops/sec |
| complex_join_validation | 40 | 32 | ops/sec |
| many_params_validation | 35 | 28 | ops/sec |
| rate_check_throughput | 5000 | 4000 | ops/sec |
| full_pipeline | 5.0 | 6.0 | ms |

**Calibration**: Baselines calibrated on Windows 11, Python 3.12, SQLite in-memory

---

## Integration Testing

### Row NATS Integration Tests

Tests for database operations via NATS events (51 tests total):

**Categories**:
- Schema registration via NATS (4 tests)
- Row insert via NATS (4 tests)
- Row select via NATS (3 tests)
- Row update via NATS (4 tests)
- Row delete via NATS (4 tests)
- Row search via NATS (12 tests)
- Search with operators (7 tests)
- Extended operators (8 tests)
- Compound logic (4 tests)

**Pattern**:
```python
async def test_insert_via_nats(nats_with_bot, nats_client):
    # Publish NATS request
    response = await nats_client.request(
        "rosey.plugin.database.row.insert",
        json.dumps({
            "plugin_name": "test",
            "table_name": "quotes",
            "data": {"text": "Hello world"}
        }).encode(),
        timeout=2.0
    )
    
    # Verify response
    result = json.loads(response.data.decode())
    assert result["success"] is True
    assert result["data"]["created"] is True
```

### Shell Integration Tests

Tests for shell commands with event-driven architecture (7 tests):

**Pattern**:
```python
async def test_shell_command(integration_bot):
    # Mock event bus
    integration_bot.event_bus.publish = AsyncMock()
    
    # Execute command
    await integration_bot.shell.handle_command("!add url", ...)
    
    # Verify event published
    event = integration_bot.event_bus.publish.call_args[0][0]
    assert event.subject == "rosey.platform.cytube.send.playlist.add"
```

---

## Contributing Guidelines

### Adding New Tests

1. **Choose Test Category**:
   - Unit test: Fast, isolated, no external dependencies
   - Integration test: Multi-component, NATS/database interactions
   - Performance test: Benchmarks with calibrated baselines

2. **Follow Naming Conventions**:
   - File: `test_<module>.py`
   - Class: `Test<Feature>`
   - Function: `test_<behavior>`

3. **Write Clear Assertions**:
   ```python
   # ✅ Good: Clear failure message
   assert result["created"] is True, f"Insert failed: {result}"
   
   # ❌ Bad: Generic assertion
   assert result
   ```

4. **Use Appropriate Fixtures**:
   - `db` - In-memory database (unit tests)
   - `nats_with_bot` - NATS + bot integration
   - `integration_bot` - Bot with mock event bus

5. **Add Documentation**:
   - Docstring explaining what behavior is tested
   - Comments for non-obvious setup or assertions

### Test Quality Standards

- **Coverage**: Aim for 85%+ (minimum 66%)
- **Speed**: Unit tests <100ms, integration tests <2s
- **Reliability**: Tests pass consistently (no flakiness)
- **Independence**: Tests don't depend on execution order
- **Clarity**: Test intent clear from name and assertions

---

## Reference

### Key Files

- `pytest.ini` - Pytest configuration
- `tests/conftest.py` - Shared fixtures
- `tests/performance/baseline.json` - Performance baselines
- `.coverage` - Coverage data (generated)
- `htmlcov/` - HTML coverage report (generated)

### Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [SETUP.md](SETUP.md) - Development environment setup
- [AGENTS.md](../AGENTS.md) - Agent workflow for development

### Sprint 20 Changes

- **Unit Test Fixes**: Fixed 41 of 42 unit test failures (in-memory database isolation)
- **Performance Baseline System**: Calibrated baselines with 20% tolerance
- **Shell Integration Updates**: Updated for event-driven architecture (Sprint 19)
- **Row NATS Fixes**: Fixed task cancellation issues in NATS handlers

See commits: cd50bca, 04f5569, 893ba6a, 3c75619

---

**Document Version**: 1.0  
**Last Updated**: November 27, 2025  
**Maintained By**: Rosey-Robot Team
