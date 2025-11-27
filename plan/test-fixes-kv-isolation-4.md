---
goal: Fix KV Service Test Isolation Issues
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Planned'
tags: [testing, kv-service, test-isolation, fixtures, sortie-4]
---

# Implementation Plan: KV Service Test Isolation

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

## Introduction

Fix 2 KV service test failures caused by test data leaking between tests due to shared plugin namespaces. Implement proper test isolation using unique plugin identifiers per test.

**Related**: [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md)

## 1. Requirements & Constraints

### Requirements

- **REQ-038**: Each test MUST use unique plugin identifier
- **REQ-039**: Plugin identifiers MUST be generated dynamically per test
- **REQ-040**: Tests MUST NOT share KV storage between runs
- **REQ-041**: Cleanup fixture MUST remove all test data after each test
- **REQ-042**: Tests MUST verify only their own data, not data from other tests
- **REQ-043**: `test_count_with_prefix` MUST assert count == 3, not 11
- **REQ-044**: `test_list_keys_with_prefix` MUST return only expected keys
- **REQ-045**: Fixtures MUST be reusable across all KV service tests
- **REQ-046**: Cleanup MUST be automatic (autouse fixture)

### Constraints

- **CON-001**: Cannot modify KV service implementation (only test fixtures)
- **CON-002**: Must maintain test intent (verify KV service functionality)
- **CON-003**: Should work with existing KV service API

### Guidelines

- **GUD-001**: Use pytest fixture best practices (scope, autouse, dependency injection)
- **GUD-002**: Generate unique identifiers using test name or UUID
- **GUD-003**: Add clear error messages showing what data was found vs expected

## 2. Implementation Steps

### Phase 1: Analyze Current Test Failures

**GOAL-001**: Understand how test data is leaking between tests

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Read `tests/unit/test_kv_service.py::test_count_with_prefix` | | |
| TASK-002 | Read `tests/unit/test_kv_service.py::test_list_keys_with_prefix` | | |
| TASK-003 | Identify how plugin identifier is set (likely hard-coded 'test') | | |
| TASK-004 | Trace how KV storage is scoped (plugin namespace) | | |
| TASK-005 | Review existing fixtures in test file or conftest.py | | |
| TASK-006 | Document isolation strategy | | |

### Phase 2: Create Isolated Plugin Fixture

**GOAL-002**: Create fixture that provides unique plugin identifier per test

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create `kv_isolated_plugin` fixture in test file or conftest.py | | |
| TASK-008 | Generate unique plugin name using test name + UUID | | |
| TASK-009 | Return plugin identifier for test to use | | |
| TASK-010 | Set fixture scope to 'function' for per-test isolation | | |
| TASK-011 | Test fixture in isolation | | |

**Code Template**:
```python
import uuid
import pytest

@pytest.fixture(scope="function")
def kv_isolated_plugin(request):
    """Provide unique plugin identifier for test isolation."""
    # Generate unique plugin name using test name
    test_name = request.node.name
    unique_id = str(uuid.uuid4())[:8]
    plugin_name = f"test_{test_name}_{unique_id}"
    
    yield plugin_name
    
    # Cleanup is handled by separate autouse fixture
```

### Phase 3: Create Cleanup Fixture

**GOAL-003**: Create autouse fixture to clean up test data after each test

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Create `kv_cleanup` autouse fixture | | |
| TASK-013 | Track plugin identifiers used in test | | |
| TASK-014 | Delete all keys for test plugin after test completes | | |
| TASK-015 | Use KV service API to enumerate and delete keys | | |
| TASK-016 | Verify cleanup doesn't affect other plugins | | |
| TASK-017 | Test cleanup fixture in isolation | | |

**Code Template**:
```python
@pytest.fixture(scope="function", autouse=True)
async def kv_cleanup(kv_service, request):
    """Automatically clean up KV data after each test."""
    yield  # Let test run first
    
    # Get plugin identifier from test (if used)
    if hasattr(request, 'node'):
        # Extract plugin name from test's local variables
        # This assumes test stored it somewhere accessible
        plugin_name = getattr(request.node, '_kv_plugin_name', None)
        
        if plugin_name:
            # Delete all keys for this plugin
            keys = await kv_service.list_keys(plugin_name, prefix="")
            for key in keys:
                await kv_service.delete(plugin_name, key)
```

### Phase 4: Update test_count_with_prefix

**GOAL-004**: Fix test to use isolated plugin and verify correct count

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Add `kv_isolated_plugin` fixture parameter to test | | |
| TASK-019 | Replace hard-coded 'test' plugin with kv_isolated_plugin | | |
| TASK-020 | Store plugin name on request.node for cleanup fixture | | |
| TASK-021 | Verify test creates exactly 3 keys with prefix | | |
| TASK-022 | Assert count == 3 (not allowing 11 or other values) | | |
| TASK-023 | Add error message showing actual keys found | | |
| TASK-024 | Run test and verify it passes | | |

**Code Template**:
```python
async def test_count_with_prefix(kv_service, kv_isolated_plugin, request):
    """Test counting keys with specific prefix."""
    plugin = kv_isolated_plugin
    request.node._kv_plugin_name = plugin  # For cleanup fixture
    
    # Create test data with prefix
    await kv_service.set(plugin, "user:1", "alice")
    await kv_service.set(plugin, "user:2", "bob")
    await kv_service.set(plugin, "user:3", "charlie")
    await kv_service.set(plugin, "config:timeout", "30")  # Different prefix
    
    # Count keys with "user:" prefix
    count = await kv_service.count(plugin, prefix="user:")
    
    # Verify only our 3 keys are counted
    if count != 3:
        # Debug: show what keys exist
        all_keys = await kv_service.list_keys(plugin, prefix="")
        user_keys = [k for k in all_keys if k.startswith("user:")]
        pytest.fail(
            f"Expected 3 keys with prefix 'user:', found {count}.\n"
            f"Keys found: {user_keys}\n"
            f"All keys in plugin: {all_keys}"
        )
    
    assert count == 3, f"Expected 3 keys, found {count}"
```

### Phase 5: Update test_list_keys_with_prefix

**GOAL-005**: Fix test to use isolated plugin and verify correct keys

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | Add `kv_isolated_plugin` fixture parameter to test | | |
| TASK-026 | Replace hard-coded 'test' plugin with kv_isolated_plugin | | |
| TASK-027 | Store plugin name on request.node for cleanup | | |
| TASK-028 | Verify test creates expected keys | | |
| TASK-029 | Assert returned keys match exactly (no extras) | | |
| TASK-030 | Add error message showing unexpected keys | | |
| TASK-031 | Run test and verify it passes | | |

**Code Template**:
```python
async def test_list_keys_with_prefix(kv_service, kv_isolated_plugin, request):
    """Test listing keys with specific prefix."""
    plugin = kv_isolated_plugin
    request.node._kv_plugin_name = plugin  # For cleanup fixture
    
    # Create test data
    await kv_service.set(plugin, "cache:page1", "data1")
    await kv_service.set(plugin, "cache:page2", "data2")
    await kv_service.set(plugin, "cache:page3", "data3")
    await kv_service.set(plugin, "user:admin", "root")  # Different prefix
    
    # List keys with "cache:" prefix
    keys = await kv_service.list_keys(plugin, prefix="cache:")
    
    # Verify only expected keys
    expected_keys = {"cache:page1", "cache:page2", "cache:page3"}
    actual_keys = set(keys)
    
    if actual_keys != expected_keys:
        extra_keys = actual_keys - expected_keys
        missing_keys = expected_keys - actual_keys
        pytest.fail(
            f"Key mismatch for prefix 'cache:':\n"
            f"Expected: {sorted(expected_keys)}\n"
            f"Actual: {sorted(actual_keys)}\n"
            f"Extra keys: {extra_keys or 'none'}\n"
            f"Missing keys: {missing_keys or 'none'}"
        )
    
    assert actual_keys == expected_keys
```

### Phase 6: Review All KV Service Tests

**GOAL-006**: Ensure all KV service tests use isolation pattern

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-032 | List all tests in `test_kv_service.py` | | |
| TASK-033 | Identify tests that use plugin parameter | | |
| TASK-034 | Update any other tests to use kv_isolated_plugin | | |
| TASK-035 | Verify cleanup fixture runs for all tests | | |
| TASK-036 | Run full test file to check for other isolation issues | | |

### Phase 7: Improve KV Service Fixture

**GOAL-007**: Enhance kv_service fixture if needed for better isolation

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-037 | Review kv_service fixture implementation | | |
| TASK-038 | Add method to list all plugins (if doesn't exist) | | |
| TASK-039 | Add method to delete all data for plugin (if doesn't exist) | | |
| TASK-040 | Consider adding isolation mode to KV service for tests | | |
| TASK-041 | Test enhanced fixture | | |

### Phase 8: Validation and Testing

**GOAL-008**: Verify both KV service tests pass consistently

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-042 | Run `pytest tests/unit/test_kv_service.py::test_count_with_prefix -v` | | |
| TASK-043 | Run `pytest tests/unit/test_kv_service.py::test_list_keys_with_prefix -v` | | |
| TASK-044 | Verify both tests pass | | |
| TASK-045 | Run both tests 10 times to verify consistency | | |
| TASK-046 | Run full KV service test suite | | |
| TASK-047 | Verify no test isolation issues remain | | |
| TASK-048 | Document isolation pattern in TESTING.md | | |

## 3. Alternatives

- **ALT-001**: Clear entire KV storage before each test
  - **Rejected**: Too aggressive, may affect concurrent tests
  
- **ALT-002**: Use separate KV service instance per test
  - **Deferred**: More overhead, isolation by plugin is sufficient
  
- **ALT-003**: Mock KV service instead of using real implementation
  - **Rejected**: Reduces test value, we want to test real storage

## 4. Dependencies

- **DEP-001**: KV service must support plugin-scoped storage
- **DEP-002**: KV service API must have list_keys() and delete() methods
- **DEP-003**: pytest with async support (pytest-asyncio)

## 5. Files

- **FILE-001**: `tests/unit/test_kv_service.py` - Update 2 test functions
- **FILE-002**: `tests/unit/conftest.py` or test file - Add isolation fixtures
- **FILE-003**: `docs/TESTING.md` - Document isolation pattern

## 6. Testing

### Unit Tests
- **TEST-001**: Test kv_isolated_plugin fixture generates unique names
- **TEST-002**: Test kv_cleanup fixture deletes only test data
- **TEST-003**: Test multiple tests run in parallel without interference

### Integration Tests
- **TEST-004**: Run test_count_with_prefix individually
- **TEST-005**: Run test_list_keys_with_prefix individually
- **TEST-006**: Run both tests together multiple times

### Validation Tests
- **TEST-007**: Run full KV service test suite
- **TEST-008**: Verify no data leaks between tests
- **TEST-009**: Verify cleanup happens on test failure too

## 7. Risks & Assumptions

### Risks
- **RISK-001**: Cleanup fixture may not work if test crashes hard
  - **Mitigation**: Use pytest's built-in fixture cleanup (yield pattern)
  
- **RISK-002**: Plugin names may collide if UUID generation fails
  - **Mitigation**: Combine test name + UUID + timestamp for uniqueness
  
- **RISK-003**: Other tests may have same isolation issues
  - **Mitigation**: Review all KV service tests proactively

### Assumptions
- **ASSUMPTION-001**: KV service uses plugin parameter for namespace isolation
- **ASSUMPTION-002**: Cleanup fixture runs even if test fails
- **ASSUMPTION-003**: UUID generation provides sufficient uniqueness

## 8. Related Specifications / Further Reading

- [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md) - Overall PRD
- [TESTING.md](../../TESTING.md) - Testing patterns
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) - Fixture documentation

---

**Estimated Time**: 2 hours  
**Priority**: P2 (Medium)  
**Sprint**: 20
