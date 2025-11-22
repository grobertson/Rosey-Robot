# Technical Specification: Remove Stats Query xfail

**Sprint**: Sprint 10.5 "The French Connection II"  
**Sortie**: 2 of 4  
**Estimated Effort**: 15 minutes  
**Dependencies**: Sprint 10 Sortie 2 (stats handlers implemented)  

---

## Overview

Remove xfail marker from `test_query_user_stats_via_nats` to validate that stats query request/reply handlers (implemented in Sprint 10 Sortie 2) work correctly.

---

## Implementation

### Remove xfail Marker

**File**: `tests/integration/test_sprint9_integration.py`  
**Line**: ~319  

**Current Code**:
```python
@pytest.mark.xfail(reason="DatabaseService request/reply handlers not implemented yet")
@pytest.mark.asyncio
async def test_query_user_stats_via_nats(self, nats_client, database_service):
    """Test querying user stats via NATS request/reply."""
    # Test implementation...
```

**New Code**:
```python
@pytest.mark.asyncio
async def test_query_user_stats_via_nats(self, nats_client, database_service):
    """Test querying user stats via NATS request/reply.
    
    Validates Sprint 10 Sortie 2 stats query handlers implementation.
    """
    # Test implementation...
```

**Change**: Remove `@pytest.mark.xfail(...)` line

---

## Validation

### 1. Run Test Locally

```bash
pytest tests/integration/test_sprint9_integration.py::TestDatabaseService::test_query_user_stats_via_nats -v
```

**Expected Result**: Test PASSES (stats handlers implemented in Sortie 2)

**If Test Fails**:
1. Check NATS connection in test
2. Verify DatabaseService._handle_stats_query() exists
3. Check subject subscription: `rosey.db.query.user_stats`
4. Document failure and restore xfail with updated reason

---

### 2. Run All Sprint 9 Tests

```bash
pytest tests/integration/test_sprint9_integration.py -v
```

**Expected**: 13/13 passing (was 12/13 with 1 xfail)

---

## Acceptance Criteria

- [ ] xfail marker removed from line 319
- [ ] Test passes locally (validates Sortie 2 implementation)
- [ ] All Sprint 9 integration tests still pass
- [ ] No new xfail markers added
- [ ] xfail count: 0 (down from 1)

---

## Rollback Plan

If test fails after xfail removal:

1. **Restore xfail marker** with updated reason:
   ```python
   @pytest.mark.xfail(reason="Stats query test fails: [specific error]. Fix in Sprint 11.")
   ```

2. **Document failure** in issue:
   - Error message
   - Expected behavior vs actual
   - Root cause hypothesis

3. **Create Sprint 11 task** to fix properly

---

**Estimated Time**: 15 minutes  
**Files Changed**: 1 (test_sprint9_integration.py)  
**Lines Changed**: -1 (remove decorator)
