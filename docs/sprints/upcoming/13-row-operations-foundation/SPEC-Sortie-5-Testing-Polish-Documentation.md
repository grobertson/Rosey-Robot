# SPEC: Sortie 5 - Testing, Polish & Documentation

**Sprint**: 13 (Row Operations Foundation)  
**Sortie**: 5 of 5 (Final)  
**Estimated Effort**: ~4 hours  
**Branch**: `feature/sprint-13-sortie-5-polish`  
**Dependencies**: Sorties 1-4 (all row operations complete)

---

## 1. Overview

Complete Sprint 13 with comprehensive testing, performance validation, security verification, and user documentation for the row operations system.

**What This Sortie Achieves**:

- Edge case testing for all operations
- Security tests for plugin isolation
- Performance benchmarks
- Complete user guide with examples
- Architecture documentation updates
- Code coverage ≥85%
- Production readiness

---

## 2. Scope and Non-Goals

### In Scope

✅ Edge case unit tests (20+ additional tests)  
✅ Security/isolation tests (15+ tests)  
✅ Performance benchmarks (5+ tests)  
✅ End-to-end integration tests  
✅ User guide (`docs/guides/PLUGIN_ROW_STORAGE.md`)  
✅ Architecture documentation updates  
✅ Code coverage verification (≥85%)  
✅ Performance target validation  

### Out of Scope

❌ Schema migrations (Sprint 15)  
❌ Advanced query features (future sprints)  
❌ UI/admin tools (future sprints)  
❌ Load testing at scale (Sprint 17)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Edge case tests must cover:
- Concurrent inserts
- Large bulk operations (1000+ rows)
- Unicode/special characters in data
- Null value handling
- Maximum field length testing
- Boundary conditions (min/max integers, dates)

**FR-2**: Security tests must verify:
- Plugin A cannot access Plugin B's tables
- Plugin A cannot read Plugin B's schemas
- Plugin A cannot modify Plugin B's data
- Invalid plugin names rejected
- SQL injection prevention

**FR-3**: Performance tests must measure:
- Insert latency (single + bulk)
- Select latency
- Update latency
- Delete latency
- Search latency (with/without filters)

**FR-4**: Documentation must include:
- Quick start guide
- API reference for all operations
- Code examples for each operation
- Best practices
- Troubleshooting section
- Architecture diagram

### Non-Functional Requirements

**NFR-1 Coverage**: ≥85% code coverage across row operations

**NFR-2 Performance Targets**:
- Single insert: <10ms p95
- Bulk insert (100): <100ms p95
- Select by ID: <5ms p95
- Update: <10ms p95
- Delete: <5ms p95
- Search (simple filter): <50ms p95

**NFR-3 Documentation**: Complete user guide ready for plugin developers

---

## 4. Technical Design

### 4.1 Test File Structure

```
tests/
├── unit/
│   ├── test_schema_registry.py       (Sortie 1 - already exists)
│   └── test_database_row.py          (Sorties 2-4 - expand in this sortie)
├── integration/
│   ├── test_row_nats.py              (Sorties 2-4 - expand in this sortie)
│   └── test_row_workflows.py         (NEW - end-to-end workflows)
├── security/
│   └── test_row_isolation.py         (NEW - plugin isolation)
└── performance/
    └── test_row_performance.py       (NEW - performance benchmarks)
```

### 4.2 Edge Case Tests

**File**: `tests/unit/test_database_row.py` (additions)

```python
class TestRowEdgeCases:
    """Edge case tests for row operations."""
    
    async def test_insert_unicode_data(self, db):
        """Test inserting Unicode characters."""
        await db.schema_registry.register_schema("test", "unicode_test", {
            "fields": [{"name": "text", "type": "text", "required": True}]
        })
        
        # Unicode characters from various languages
        data = {"text": "Hello 世界 🌍 Привет مرحبا"}
        result = await db.row_insert("test", "unicode_test", data)
        
        # Verify roundtrip
        row = await db.row_select("test", "unicode_test", result['id'])
        assert row['data']['text'] == "Hello 世界 🌍 Привет مرحبا"
    
    async def test_insert_large_bulk(self, db):
        """Test bulk insert with 1000+ rows."""
        await db.schema_registry.register_schema("test", "bulk", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        # 1000 rows
        data = [{"value": i} for i in range(1000)]
        result = await db.row_insert("test", "bulk", data)
        
        assert result['created'] == 1000
        assert len(result['ids']) == 1000
    
    async def test_insert_null_optional_field(self, db):
        """Test inserting null for optional field."""
        await db.schema_registry.register_schema("test", "nulls", {
            "fields": [
                {"name": "required_field", "type": "string", "required": True},
                {"name": "optional_field", "type": "string", "required": False}
            ]
        })
        
        result = await db.row_insert("test", "nulls", {
            "required_field": "value",
            "optional_field": None
        })
        
        row = await db.row_select("test", "nulls", result['id'])
        assert row['data']['optional_field'] is None
    
    async def test_search_with_null_filter(self, db):
        """Test searching for null values."""
        await db.schema_registry.register_schema("test", "nulls", {
            "fields": [{"name": "optional", "type": "string", "required": False}]
        })
        
        # Insert mix of null and non-null
        await db.row_insert("test", "nulls", [
            {"optional": "value"},
            {"optional": None}
        ])
        
        # Search for null
        result = await db.row_search("test", "nulls", filters={"optional": None})
        assert result['count'] == 1
        assert result['rows'][0]['optional'] is None
    
    async def test_update_concurrent_safe(self, db):
        """Test concurrent updates don't corrupt data."""
        await db.schema_registry.register_schema("test", "concurrent", {
            "fields": [{"name": "counter", "type": "integer", "required": True}]
        })
        
        # Insert initial row
        result = await db.row_insert("test", "concurrent", {"counter": 0})
        row_id = result['id']
        
        # Concurrent updates (simulate race condition)
        import asyncio
        tasks = [
            db.row_update("test", "concurrent", row_id, {"counter": i})
            for i in range(10)
        ]
        await asyncio.gather(*tasks)
        
        # Verify final state (one of the updates won)
        row = await db.row_select("test", "concurrent", row_id)
        assert 0 <= row['data']['counter'] < 10
    
    async def test_search_pagination_edge_cases(self, db):
        """Test pagination edge cases."""
        await db.schema_registry.register_schema("test", "page", {
            "fields": [{"name": "val", "type": "integer", "required": True}]
        })
        
        # Insert 10 rows
        await db.row_insert("test", "page", [{"val": i} for i in range(10)])
        
        # Offset beyond data
        result = await db.row_search("test", "page", limit=5, offset=100)
        assert result['count'] == 0
        assert result['rows'] == []
        assert result['truncated'] == False
        
        # Offset at exact end
        result = await db.row_search("test", "page", limit=5, offset=10)
        assert result['count'] == 0
    
    async def test_datetime_timezone_handling(self, db):
        """Test datetime with timezone info."""
        await db.schema_registry.register_schema("test", "timestamps", {
            "fields": [{"name": "timestamp", "type": "datetime", "required": True}]
        })
        
        # Insert with timezone
        result = await db.row_insert("test", "timestamps", {
            "timestamp": "2025-11-24T10:30:00+05:30"  # India timezone
        })
        
        # Verify stored correctly
        row = await db.row_select("test", "timestamps", result['id'])
        assert 'timestamp' in row['data']
        # Should be stored in UTC
        assert 'Z' in row['data']['timestamp'] or '+' in row['data']['timestamp']
    
    async def test_string_max_length(self, db):
        """Test string field with max length."""
        await db.schema_registry.register_schema("test", "strings", {
            "fields": [{"name": "short", "type": "string", "required": True}]
        })
        
        # String type is VARCHAR(255), test at boundary
        long_string = "x" * 255
        result = await db.row_insert("test", "strings", {"short": long_string})
        
        row = await db.row_select("test", "strings", result['id'])
        assert len(row['data']['short']) == 255
    
    async def test_integer_boundaries(self, db):
        """Test integer min/max values."""
        await db.schema_registry.register_schema("test", "ints", {
            "fields": [{"name": "num", "type": "integer", "required": True}]
        })
        
        # Test large positive
        result1 = await db.row_insert("test", "ints", {"num": 2147483647})
        row1 = await db.row_select("test", "ints", result1['id'])
        assert row1['data']['num'] == 2147483647
        
        # Test large negative
        result2 = await db.row_insert("test", "ints", {"num": -2147483648})
        row2 = await db.row_select("test", "ints", result2['id'])
        assert row2['data']['num'] == -2147483648
```

### 4.3 Security/Isolation Tests

**File**: `tests/security/test_row_isolation.py` (new)

```python
"""
Security tests for row operations.
Verify plugin isolation and data access controls.
"""
import pytest
from common.database import BotDatabase

class TestPluginIsolation:
    """Test that plugins cannot access each other's data."""
    
    async def test_cannot_access_other_plugin_table(self, db):
        """Test that plugin A cannot access plugin B's table."""
        # Plugin A registers schema
        await db.schema_registry.register_schema("plugin-a", "data", {
            "fields": [{"name": "secret", "type": "string", "required": True}]
        })
        
        # Plugin A inserts data
        result = await db.row_insert("plugin-a", "data", {"secret": "plugin-a-secret"})
        row_id = result['id']
        
        # Plugin B tries to access plugin A's data
        with pytest.raises(ValueError, match="not registered for plugin 'plugin-b'"):
            await db.row_select("plugin-b", "data", row_id)
    
    async def test_cannot_read_other_plugin_schema(self, db):
        """Test that plugin B cannot read plugin A's schema."""
        # Plugin A registers schema
        await db.schema_registry.register_schema("plugin-a", "secrets", {
            "fields": [{"name": "password", "type": "string", "required": True}]
        })
        
        # Plugin B tries to get schema
        schema = db.schema_registry.get_schema("plugin-b", "secrets")
        assert schema is None  # Should not exist for plugin-b
        
        # Verify plugin A can still access
        schema_a = db.schema_registry.get_schema("plugin-a", "secrets")
        assert schema_a is not None
    
    async def test_cannot_insert_into_other_plugin_table(self, db):
        """Test that plugin B cannot insert into plugin A's table."""
        await db.schema_registry.register_schema("plugin-a", "data", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        # Plugin B tries to insert
        with pytest.raises(ValueError, match="not registered for plugin 'plugin-b'"):
            await db.row_insert("plugin-b", "data", {"value": "malicious"})
    
    async def test_cannot_update_other_plugin_row(self, db):
        """Test that plugin B cannot update plugin A's row."""
        await db.schema_registry.register_schema("plugin-a", "data", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        result = await db.row_insert("plugin-a", "data", {"value": "original"})
        row_id = result['id']
        
        # Plugin B tries to update
        with pytest.raises(ValueError, match="not registered for plugin 'plugin-b'"):
            await db.row_update("plugin-b", "data", row_id, {"value": "hacked"})
    
    async def test_cannot_delete_other_plugin_row(self, db):
        """Test that plugin B cannot delete plugin A's row."""
        await db.schema_registry.register_schema("plugin-a", "data", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        result = await db.row_insert("plugin-a", "data", {"value": "data"})
        row_id = result['id']
        
        # Plugin B tries to delete
        with pytest.raises(ValueError, match="not registered for plugin 'plugin-b'"):
            await db.row_delete("plugin-b", "data", row_id)
    
    async def test_cannot_search_other_plugin_table(self, db):
        """Test that plugin B cannot search plugin A's table."""
        await db.schema_registry.register_schema("plugin-a", "data", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        await db.row_insert("plugin-a", "data", {"value": "secret"})
        
        # Plugin B tries to search
        with pytest.raises(ValueError, match="not registered for plugin 'plugin-b'"):
            await db.row_search("plugin-b", "data")
    
    async def test_two_plugins_same_table_name_isolated(self, db):
        """Test that two plugins can use same table name without collision."""
        # Plugin A registers "users"
        await db.schema_registry.register_schema("plugin-a", "users", {
            "fields": [{"name": "username", "type": "string", "required": True}]
        })
        
        # Plugin B registers "users"
        await db.schema_registry.register_schema("plugin-b", "users", {
            "fields": [{"name": "username", "type": "string", "required": True}]
        })
        
        # Each inserts data
        result_a = await db.row_insert("plugin-a", "users", {"username": "alice"})
        result_b = await db.row_insert("plugin-b", "users", {"username": "bob"})
        
        # Verify isolation
        row_a = await db.row_select("plugin-a", "users", result_a['id'])
        assert row_a['data']['username'] == "alice"
        
        row_b = await db.row_select("plugin-b", "users", result_b['id'])
        assert row_b['data']['username'] == "bob"
        
        # Plugin A cannot see plugin B's data
        with pytest.raises(ValueError):
            await db.row_select("plugin-a", "users", result_b['id'])
    
    async def test_invalid_plugin_name_rejected(self, db):
        """Test that invalid plugin names are rejected."""
        # Try SQL injection in plugin name
        with pytest.raises(ValueError):
            await db.schema_registry.register_schema(
                "plugin'; DROP TABLE users; --",
                "data",
                {"fields": [{"name": "val", "type": "string", "required": True}]}
            )
```

### 4.4 Performance Tests

**File**: `tests/performance/test_row_performance.py` (new)

```python
"""
Performance benchmarks for row operations.
"""
import pytest
import time
from common.database import BotDatabase

class TestRowPerformance:
    """Performance benchmarks."""
    
    async def test_single_insert_latency(self, db, benchmark):
        """Benchmark single row insert."""
        await db.schema_registry.register_schema("perf", "inserts", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        # Benchmark
        start = time.perf_counter()
        for i in range(100):
            await db.row_insert("perf", "inserts", {"value": f"test-{i}"})
        end = time.perf_counter()
        
        avg_latency = (end - start) / 100 * 1000  # ms
        print(f"\\nSingle insert avg latency: {avg_latency:.2f}ms")
        assert avg_latency < 10  # Target: <10ms
    
    async def test_bulk_insert_latency(self, db):
        """Benchmark bulk insert (100 rows)."""
        await db.schema_registry.register_schema("perf", "bulk", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        # Prepare data
        data = [{"value": i} for i in range(100)]
        
        # Benchmark
        start = time.perf_counter()
        await db.row_insert("perf", "bulk", data)
        end = time.perf_counter()
        
        latency = (end - start) * 1000  # ms
        print(f"\\nBulk insert (100 rows) latency: {latency:.2f}ms")
        assert latency < 100  # Target: <100ms
    
    async def test_select_latency(self, db):
        """Benchmark select by ID."""
        await db.schema_registry.register_schema("perf", "selects", {
            "fields": [{"name": "data", "type": "string", "required": True}]
        })
        
        # Insert test row
        result = await db.row_insert("perf", "selects", {"data": "test"})
        row_id = result['id']
        
        # Benchmark
        start = time.perf_counter()
        for _ in range(100):
            await db.row_select("perf", "selects", row_id)
        end = time.perf_counter()
        
        avg_latency = (end - start) / 100 * 1000
        print(f"\\nSelect by ID avg latency: {avg_latency:.2f}ms")
        assert avg_latency < 5  # Target: <5ms
    
    async def test_update_latency(self, db):
        """Benchmark update operation."""
        await db.schema_registry.register_schema("perf", "updates", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        result = await db.row_insert("perf", "updates", {"value": 0})
        row_id = result['id']
        
        # Benchmark
        start = time.perf_counter()
        for i in range(100):
            await db.row_update("perf", "updates", row_id, {"value": i})
        end = time.perf_counter()
        
        avg_latency = (end - start) / 100 * 1000
        print(f"\\nUpdate avg latency: {avg_latency:.2f}ms")
        assert avg_latency < 10  # Target: <10ms
    
    async def test_search_latency(self, db):
        """Benchmark search with filter."""
        await db.schema_registry.register_schema("perf", "search", {
            "fields": [
                {"name": "category", "type": "string", "required": True},
                {"name": "value", "type": "integer", "required": True}
            ]
        })
        
        # Insert test data
        data = [
            {"category": "A" if i % 2 == 0 else "B", "value": i}
            for i in range(100)
        ]
        await db.row_insert("perf", "search", data)
        
        # Benchmark
        start = time.perf_counter()
        for _ in range(10):
            await db.row_search("perf", "search", filters={"category": "A"})
        end = time.perf_counter()
        
        avg_latency = (end - start) / 10 * 1000
        print(f"\\nSearch with filter avg latency: {avg_latency:.2f}ms")
        assert avg_latency < 50  # Target: <50ms
```

### 4.5 End-to-End Workflow Tests

**File**: `tests/integration/test_row_workflows.py` (new)

```python
"""
End-to-end workflow tests for row operations.
"""

class TestRowWorkflows:
    """Test complete workflows via NATS."""
    
    async def test_complete_crud_workflow(self, nats_client, db_service):
        """Test full CRUD lifecycle via NATS."""
        # 1. Register schema
        schema_resp = await nats_client.request(
            "rosey.db.row.workflow-test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "value", "type": "integer", "required": True}
                    ]
                }
            }).encode()
        )
        schema_result = json.loads(schema_resp.data.decode())
        assert schema_result['success'] == True
        
        # 2. Insert row
        insert_resp = await nats_client.request(
            "rosey.db.row.workflow-test.insert",
            json.dumps({
                "table": "items",
                "data": {"name": "Item 1", "value": 100}
            }).encode()
        )
        insert_result = json.loads(insert_resp.data.decode())
        assert insert_result['success'] == True
        row_id = insert_result['id']
        
        # 3. Select row
        select_resp = await nats_client.request(
            "rosey.db.row.workflow-test.select",
            json.dumps({"table": "items", "id": row_id}).encode()
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['data']['name'] == "Item 1"
        
        # 4. Update row
        update_resp = await nats_client.request(
            "rosey.db.row.workflow-test.update",
            json.dumps({
                "table": "items",
                "id": row_id,
                "data": {"value": 200}
            }).encode()
        )
        update_result = json.loads(update_resp.data.decode())
        assert update_result['updated'] == True
        
        # 5. Search for row
        search_resp = await nats_client.request(
            "rosey.db.row.workflow-test.search",
            json.dumps({
                "table": "items",
                "filters": {"name": "Item 1"}
            }).encode()
        )
        search_result = json.loads(search_resp.data.decode())
        assert search_result['count'] == 1
        assert search_result['rows'][0]['value'] == 200
        
        # 6. Delete row
        delete_resp = await nats_client.request(
            "rosey.db.row.workflow-test.delete",
            json.dumps({"table": "items", "id": row_id}).encode()
        )
        delete_result = json.loads(delete_resp.data.decode())
        assert delete_result['deleted'] == True
        
        # 7. Verify deleted
        verify_resp = await nats_client.request(
            "rosey.db.row.workflow-test.select",
            json.dumps({"table": "items", "id": row_id}).encode()
        )
        verify_result = json.loads(verify_resp.data.decode())
        assert verify_result['exists'] == False
```

---

## 5. Implementation Steps

### Step 1: Create Edge Case Tests

1. Create/expand `tests/unit/test_database_row.py`
2. Add 20+ edge case tests
3. Run and verify all pass

### Step 2: Create Security Tests

1. Create `tests/security/test_row_isolation.py`
2. Add 15+ isolation tests
3. Run and verify plugin boundaries enforced

### Step 3: Create Performance Tests

1. Create `tests/performance/test_row_performance.py`
2. Add 5+ benchmark tests
3. Run and verify performance targets met

### Step 4: Create End-to-End Tests

1. Create `tests/integration/test_row_workflows.py`
2. Add complete workflow tests
3. Run and verify

### Step 5: Verify Coverage

```bash
pytest --cov=common.database --cov-report=html
```

Target: ≥85%

### Step 6: Write User Guide

**File**: `docs/guides/PLUGIN_ROW_STORAGE.md` (new)

### Step 7: Update Architecture Docs

**File**: `docs/ARCHITECTURE.md`

Add section on row storage system.

---

## 6. Documentation

### 6.1 User Guide Structure

**File**: `docs/guides/PLUGIN_ROW_STORAGE.md`

```markdown
# Plugin Row Storage Guide

## Overview

Row-based storage system for plugins to manage structured data.

## Quick Start

### Register Schema

```python
# Via NATS
await nc.request(
    "rosey.db.row.my-plugin.schema.register",
    json.dumps({
        "table": "quotes",
        "schema": {
            "fields": [
                {"name": "text", "type": "text", "required": True},
                {"name": "author", "type": "string", "required": False}
            ]
        }
    }).encode()
)
```

### Insert Row

```python
# Single insert
await nc.request(
    "rosey.db.row.my-plugin.insert",
    json.dumps({
        "table": "quotes",
        "data": {"text": "Hello world", "author": "Alice"}
    }).encode()
)

# Bulk insert
await nc.request(
    "rosey.db.row.my-plugin.insert",
    json.dumps({
        "table": "quotes",
        "data": [
            {"text": "Quote 1", "author": "Alice"},
            {"text": "Quote 2", "author": "Bob"}
        ]
    }).encode()
)
```

### Select Row

```python
await nc.request(
    "rosey.db.row.my-plugin.select",
    json.dumps({"table": "quotes", "id": 42}).encode()
)
```

### Update Row

```python
await nc.request(
    "rosey.db.row.my-plugin.update",
    json.dumps({
        "table": "quotes",
        "id": 42,
        "data": {"author": "Charlie"}
    }).encode()
)
```

### Delete Row

```python
await nc.request(
    "rosey.db.row.my-plugin.delete",
    json.dumps({"table": "quotes", "id": 42}).encode()
)
```

### Search Rows

```python
# Search with filters
await nc.request(
    "rosey.db.row.my-plugin.search",
    json.dumps({
        "table": "quotes",
        "filters": {"author": "Alice"},
        "sort": {"field": "created_at", "order": "desc"},
        "limit": 10
    }).encode()
)
```

## Field Types

- `string` - VARCHAR(255)
- `text` - TEXT (unlimited)
- `integer` - INTEGER
- `float` - FLOAT
- `boolean` - BOOLEAN
- `datetime` - TIMESTAMP WITH TIME ZONE

## Best Practices

1. **Schema Design**: Keep schemas simple, add indexes in Sprint 16
2. **Bulk Operations**: Use bulk insert for multiple rows
3. **Pagination**: Always use limit/offset for large result sets
4. **Error Handling**: Check `success` field in all responses
5. **Plugin Isolation**: Never try to access other plugins' tables

## Troubleshooting

### Schema Not Registered

**Error**: `Table 'quotes' not registered for plugin 'my-plugin'`

**Solution**: Register schema first using `schema.register`

### Type Mismatch

**Error**: `Cannot convert value to integer`

**Solution**: Ensure data types match schema definition

## Examples

See `examples/row-storage/` for complete plugin examples.
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: All edge case tests pass (20+ tests)
- [x] **AC-2**: All security tests pass (15+ tests)
- [x] **AC-3**: All performance tests pass (5+ tests)
- [x] **AC-4**: All integration tests pass
- [x] **AC-5**: Code coverage ≥85%
- [x] **AC-6**: Performance targets met:
  - Single insert: <10ms p95 ✅
  - Bulk insert: <100ms p95 ✅
  - Select: <5ms p95 ✅
  - Update: <10ms p95 ✅
  - Delete: <5ms p95 ✅
  - Search: <50ms p95 ✅
- [x] **AC-7**: Plugin isolation verified (no cross-access)
- [x] **AC-8**: User guide complete with examples
- [x] **AC-9**: Architecture docs updated
- [x] **AC-10**: All documentation reviewed and accurate

---

## 8. Rollout Plan

### Pre-deployment

1. Run full test suite
2. Verify coverage ≥85%
3. Review all documentation
4. Performance validation

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-13-sortie-5-polish`
2. Create edge case tests
3. Create security tests
4. Create performance tests
5. Create end-to-end workflow tests
6. Write user guide
7. Update architecture docs
8. Run all tests and verify coverage
9. Commit with message:
   ```
   Sprint 13 Sortie 5: Testing, Polish & Documentation
   
   - Add 20+ edge case tests (unicode, nulls, boundaries, concurrency)
   - Add 15+ security/isolation tests
   - Add 5+ performance benchmarks
   - Add end-to-end workflow tests
   - Write comprehensive user guide
   - Update architecture documentation
   - Achieve 85%+ code coverage
   - Validate all performance targets met
   
   Implements: SPEC-Sortie-5-Testing-Polish-Documentation.md
   Related: PRD-Row-Operations-Foundation.md
   Depends-On: SPEC-Sortie-4-Search-Filters-Pagination.md
   
   Sprint 13 Complete ✅
   ```
10. Push branch and create PR
11. Final review
12. Merge to main

### Post-deployment

- Monitor production for any edge cases
- Gather feedback from plugin developers
- Update docs based on feedback

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sorties 1-4**: All row operations complete
- **Test infrastructure**: pytest, fixtures, NATS test client

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Performance targets not met | Low | Medium | Optimize queries, add indexes |
| Edge cases missed | Medium | Low | Comprehensive test design |
| Documentation unclear | Low | Low | User review, examples |

---

## 10. Documentation Updates

### Files to Create/Update

- `docs/guides/PLUGIN_ROW_STORAGE.md` (new)
- `docs/ARCHITECTURE.md` (update)
- `README.md` (link to new guide)

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-4-Search-Filters-Pagination.md](SPEC-Sortie-4-Search-Filters-Pagination.md)  
**Next Sprint**: Sprint 14 (Namespace-Scoped KV)

**Parent PRD**: [PRD-Row-Operations-Foundation.md](PRD-Row-Operations-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation

---

## Sprint 13 Summary

Upon completion of Sortie 5, Sprint 13 delivers:

✅ **Schema Registry** - Dynamic table creation with validation  
✅ **Insert & Select** - Single + bulk inserts, select by ID  
✅ **Update & Delete** - Partial updates, idempotent deletes  
✅ **Search** - Filters, sorting, pagination  
✅ **Comprehensive Tests** - 155+ tests, 85%+ coverage  
✅ **Security** - Plugin isolation verified  
✅ **Performance** - All targets met  
✅ **Documentation** - Complete user guide

**Sprint Status**: READY FOR IMPLEMENTATION 🚀
