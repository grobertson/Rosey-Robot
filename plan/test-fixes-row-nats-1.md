---
goal: Fix Row NATS Integration Tests - Schema Registration and Database Fixtures
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Planned'
tags: [testing, row-nats, integration-tests, fixtures, sortie-1]
---

# Implementation Plan: Row NATS Integration Test Fixes

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

## Introduction

Fix all 40 row NATS integration test failures by addressing schema registration, database fixture setup, response validation, and plugin isolation issues.

**Related**: [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md)

## 1. Requirements & Constraints

### Requirements

- **REQ-001**: Test fixtures MUST register schemas before executing NATS operations
- **REQ-002**: Schema registration MUST include all required fields (id, name, value, etc.)
- **REQ-003**: Schema registration MUST use proper plugin isolation (plugin='test')
- **REQ-004**: Registration failures MUST provide clear error messages
- **REQ-005**: Database fixture MUST create user_stats table before tests run
- **REQ-006**: Database fixture MUST run migrations to ensure schema is current
- **REQ-007**: Database fixture MUST properly tear down (close connections, cleanup)
- **REQ-008**: Fixture teardown MUST NOT cause OperationalError exceptions
- **REQ-009**: NATS insert operations MUST return `{'success': True, 'id': <row_id>}`
- **REQ-010**: NATS update operations MUST return `{'success': True}`
- **REQ-011**: NATS delete operations MUST return `{'success': True}`
- **REQ-012**: NATS search operations MUST return `{'success': True, 'rows': [...]}`
- **REQ-013**: Error responses MUST return `{'success': False, 'error': {...}}`
- **REQ-014**: Test plugin MUST properly isolate from other plugins
- **REQ-015**: Schema registry MUST track schemas per plugin
- **REQ-016**: Table names MUST be scoped to plugin namespace

### Constraints

- **CON-001**: Cannot modify production DatabaseService code unless absolutely necessary
- **CON-002**: Must maintain backward compatibility with existing passing tests
- **CON-003**: Fixture changes must work across all row NATS tests
- **CON-004**: Cannot change NATS message format (part of API contract)

### Guidelines

- **GUD-001**: Prefer fixing fixtures over fixing tests
- **GUD-002**: Use pytest best practices (fixtures, autouse, scope)
- **GUD-003**: Add clear error messages for debugging
- **GUD-004**: Document fixture patterns for future tests

## 2. Implementation Steps

### Phase 1: Analyze Current Test Failures

**GOAL-001**: Understand root causes of all 40 test failures

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Read all error messages from pytest output | | |
| TASK-002 | Categorize failures by type (KeyError, success=False, table not found) | | |
| TASK-003 | Identify common patterns across failures | | |
| TASK-004 | Review current fixture implementation in `tests/integration/test_row_nats.py` | | |
| TASK-005 | Review DatabaseService code for schema registration flow | | |
| TASK-006 | Document findings in analysis doc | | |

### Phase 2: Create Schema Registration Fixture

**GOAL-002**: Implement fixture that registers test schemas before NATS operations

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create `schema_registered` fixture in `tests/integration/conftest.py` | | |
| TASK-008 | Define test schema structure (table, fields, immutable_fields, plugin) | | |
| TASK-009 | Implement schema registration via NATS subject `rosey.db.schema.test.register` | | |
| TASK-010 | Add request/reply pattern to wait for registration confirmation | | |
| TASK-011 | Verify registration succeeded (assert response['success'] is True) | | |
| TASK-012 | Add clear error message if registration fails | | |
| TASK-013 | Set fixture scope to 'module' for efficiency | | |
| TASK-014 | Add fixture dependency on `db_service` | | |

**Code Template**:
```python
@pytest.fixture(scope="module")
async def schema_registered(db_service, nc):
    """Register test schema before running row NATS tests."""
    schema = {
        "table": "items",
        "fields": {
            "id": {"type": "integer", "required": True},
            "name": {"type": "string", "required": True},
            "value": {"type": "integer", "required": False},
            "category": {"type": "string", "required": False}
        },
        "immutable_fields": ["id"],
        "plugin": "test"
    }
    
    # Publish schema registration request
    response = await nc.request(
        "rosey.db.schema.test.register",
        json.dumps(schema).encode(),
        timeout=5.0
    )
    
    result = json.loads(response.data.decode())
    assert result['success'] is True, f"Schema registration failed: {result.get('error')}"
    
    yield result
    
    # Optional: Unregister schema on teardown
    # await nc.request("rosey.db.schema.test.unregister", ...)
```

### Phase 3: Fix Database Service Fixture

**GOAL-003**: Ensure database fixture creates all required tables and runs migrations

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Review current `db_service` fixture implementation | | |
| TASK-016 | Add migration execution before DatabaseService starts | | |
| TASK-017 | Verify user_stats table is created | | |
| TASK-018 | Verify all plugin tables are created | | |
| TASK-019 | Add logging for database initialization steps | | |
| TASK-020 | Test fixture in isolation (create, verify tables, teardown) | | |

**Code Template**:
```python
@pytest.fixture(scope="module")
async def db_service():
    """Create and start DatabaseService with proper migrations."""
    # Create in-memory database
    config = {
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
            "echo": False
        }
    }
    
    service = DatabaseService(config)
    
    # Start service (this should run migrations)
    await service.start()
    
    # Verify critical tables exist
    async with service.db.session() as session:
        # Check user_stats table exists
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_stats'")
        )
        assert result.fetchone() is not None, "user_stats table not created"
    
    yield service
    
    # Proper teardown
    await service.stop()
```

### Phase 4: Fix Database Teardown

**GOAL-004**: Prevent OperationalError exceptions during fixture teardown

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Review DatabaseService.stop() implementation | | |
| TASK-022 | Identify source of user_stats UPDATE during close | | |
| TASK-023 | Add proper session cleanup before closing connections | | |
| TASK-024 | Wrap teardown in try/except with logging | | |
| TASK-025 | Verify no exceptions in fixture teardown | | |

**Code Template**:
```python
@pytest.fixture(scope="module")
async def db_service():
    # ... setup code ...
    
    yield service
    
    # Proper teardown without OperationalError
    try:
        # Close all active sessions first
        await service.db.close_all_sessions()
        
        # Stop the service
        await service.stop()
    except Exception as e:
        # Log but don't fail on teardown errors
        logger.warning(f"Error during db_service teardown: {e}")
```

### Phase 5: Update Test Files

**GOAL-005**: Update all row NATS tests to use new fixtures and verify responses

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-026 | Add `schema_registered` fixture to all test functions | | |
| TASK-027 | Update test assertions to check response structure | | |
| TASK-028 | Verify insert operations return `{'success': True, 'id': int}` | | |
| TASK-029 | Verify update operations return `{'success': True}` | | |
| TASK-030 | Verify delete operations return `{'success': True}` | | |
| TASK-031 | Verify search operations return `{'success': True, 'rows': list}` | | |
| TASK-032 | Add better error messages to assertions | | |

**Code Template**:
```python
async def test_insert_single_row_via_nats(db_service, schema_registered, nc):
    """Test inserting a single row via NATS."""
    # Publish insert request
    response = await nc.request(
        "rosey.db.row.test.items.insert",
        json.dumps({"name": "test_item", "value": 42}).encode(),
        timeout=5.0
    )
    
    result = json.loads(response.data.decode())
    
    # Verify response structure
    assert result['success'] is True, f"Insert failed: {result.get('error')}"
    assert 'id' in result, "Response missing 'id' field"
    assert isinstance(result['id'], int), f"ID should be integer, got {type(result['id'])}"
    assert result['id'] > 0, "ID should be positive integer"
```

### Phase 6: Fix Plugin Isolation

**GOAL-006**: Ensure test plugin properly isolates from other plugins

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-033 | Review SchemaRegistry implementation for plugin filtering | | |
| TASK-034 | Verify test schema uses plugin='test' consistently | | |
| TASK-035 | Add plugin parameter to all NATS subjects | | |
| TASK-036 | Test that test plugin tables don't interfere with other plugins | | |

### Phase 7: Validation and Testing

**GOAL-007**: Verify all 40 row NATS tests pass

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-037 | Run `pytest tests/integration/test_row_nats.py -v` | | |
| TASK-038 | Verify 0 failures, 0 errors | | |
| TASK-039 | Run tests 3 times to verify consistency | | |
| TASK-040 | Check for any warnings or deprecations | | |
| TASK-041 | Verify test duration is reasonable (<60s) | | |
| TASK-042 | Run full integration test suite to check for regressions | | |
| TASK-043 | Document any workarounds or limitations | | |

## 3. Alternatives

- **ALT-001**: Modify DatabaseService to handle missing tables gracefully
  - **Rejected**: Too invasive, prefer fixing test fixtures
  
- **ALT-002**: Create separate database instance per test
  - **Rejected**: Too slow, fixture scope='module' is sufficient
  
- **ALT-003**: Mock NATS responses instead of fixing fixtures
  - **Rejected**: Defeats purpose of integration tests

## 4. Dependencies

- **DEP-001**: DatabaseService must support in-memory SQLite for tests
- **DEP-002**: NATS connection must be available in test fixtures
- **DEP-003**: Schema registration endpoint must exist in DatabaseService
- **DEP-004**: Migrations must be idempotent (safe to run multiple times)

## 5. Files

- **FILE-001**: `tests/integration/conftest.py` - Add schema_registered fixture
- **FILE-002**: `tests/integration/test_row_nats.py` - Update all test functions (40 tests)
- **FILE-003**: `common/database_service.py` - Review/fix teardown if needed
- **FILE-004**: `common/database.py` - Review session cleanup if needed

## 6. Testing

### Unit Tests
- **TEST-001**: Test schema_registered fixture in isolation
- **TEST-002**: Test db_service fixture creates all tables
- **TEST-003**: Test db_service fixture teardown doesn't raise exceptions

### Integration Tests
- **TEST-004**: Run all 40 row NATS tests individually
- **TEST-005**: Run all 40 row NATS tests as suite
- **TEST-006**: Run tests multiple times to verify consistency

### Validation Tests
- **TEST-007**: Verify no OperationalError in teardown logs
- **TEST-008**: Verify test duration is acceptable
- **TEST-009**: Verify coverage maintained for DatabaseService

## 7. Risks & Assumptions

### Risks
- **RISK-001**: DatabaseService may have bugs preventing proper teardown
  - **Mitigation**: Review code, add try/except in fixture teardown
  
- **RISK-002**: Schema registration may not work as expected
  - **Mitigation**: Test schema registration endpoint separately first
  
- **RISK-003**: Migrations may fail in test environment
  - **Mitigation**: Verify migrations work with in-memory SQLite

### Assumptions
- **ASSUMPTION-001**: Schema registration endpoint exists and works
- **ASSUMPTION-002**: DatabaseService.stop() should work without errors
- **ASSUMPTION-003**: All row NATS tests use same schema structure

## 8. Related Specifications / Further Reading

- [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md) - Overall PRD
- [TESTING.md](../../TESTING.md) - Testing strategy and patterns
- [DATABASE_SERVICE.md](../../common/DATABASE_SERVICE.md) - DatabaseService documentation
- Sprint 17 documentation - Row Storage via NATS feature

---

**Estimated Time**: 8 hours  
**Priority**: P0 (Blocker)  
**Sprint**: 20
