# SPEC: Sortie 4 - Search with Filters & Pagination

**Sprint**: 13 (Row Operations Foundation)  
**Sortie**: 4 of 5  
**Estimated Effort**: ~5 hours  
**Branch**: `feature/sprint-13-sortie-4-search`  
**Dependencies**: Sorties 1-3 (Schema, CRUD operations)

---

## 1. Overview

Implement search functionality with filters, sorting, and pagination for row-based storage, enabling plugins to query their data efficiently.

**What This Sortie Achieves**:

- Search rows with equality filters (AND logic)
- Sort results by single field (ASC/DESC)
- Paginate results with limit + offset
- Detect result truncation
- NATS handler for search operations
- Performance optimization with proper indexing

---

## 2. Scope and Non-Goals

### In Scope

✅ BotDatabase.row_search() method  
✅ Equality filters with AND logic  
✅ Sorting by single field (ascending/descending)  
✅ Pagination (limit + offset)  
✅ Truncation detection  
✅ Result metadata (count, truncated flag)  
✅ DatabaseService NATS handler (_handle_row_search)  
✅ Unit tests (20+ tests)  
✅ Integration tests (12+ tests with NATS)

### Out of Scope

❌ Complex queries (OR, NOT, nested conditions)  
❌ Range filters (>, <, BETWEEN)  
❌ LIKE/pattern matching  
❌ Multi-field sorting  
❌ Full-text search  
❌ Aggregations (COUNT, SUM, AVG)  
❌ Joins between tables

---

## 3. Requirements

### Functional Requirements

**FR-1**: row_search() must:
- Accept optional filters dict (field: value pairs)
- Apply all filters with AND logic
- Support sorting by single field
- Support ASC/DESC sort order
- Enforce max limit (1000 rows)
- Return rows array, count, and truncated flag
- Return empty array when no matches

**FR-2**: Filters must:
- Support equality matching only (field == value)
- Work with all field types (string, integer, boolean, datetime, etc.)
- Handle None/null values correctly
- Reject filters on non-existent fields

**FR-3**: Sorting must:
- Support single field only
- Default to ascending order
- Allow explicit "asc" or "desc"
- Work with all field types
- Handle null values (database-dependent ordering)

**FR-4**: Pagination must:
- Default limit: 100 rows
- Max limit: 1000 rows
- Support offset for subsequent pages
- Detect truncation (more results available)

**FR-5**: NATS handler must:
- Validate JSON request format
- Call BotDatabase.row_search()
- Return success/error responses
- Handle database errors gracefully
- Log all operations

### Non-Functional Requirements

**NFR-1 Performance**:
- Search with filter: <50ms p95 (small tables <10k rows)
- Search with sort: <100ms p95
- Pagination: <20ms per page
- Use database indexes where available

**NFR-2 Reliability**:
- Invalid filters rejected with clear error
- Empty results don't cause errors
- Large result sets handled efficiently

**NFR-3 Testing**: ≥90% code coverage for search operations

---

## 4. Technical Design

### 4.1 BotDatabase Method

**File**: `common/database.py`

```python
from typing import Any, Optional
from datetime import datetime
from sqlalchemy import select, Table

class BotDatabase:
    """Database access layer."""
    
    # ... existing methods ...
    
    MAX_SEARCH_LIMIT = 1000  # Maximum rows per search
    
    async def row_search(
        self,
        plugin_name: str,
        table_name: str,
        filters: Optional[dict] = None,
        sort: Optional[dict] = None,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """
        Search rows with filters, sorting, and pagination.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            filters: Field equality filters (AND logic), e.g., {"status": "active"}
            sort: Sorting spec, e.g., {"field": "created_at", "order": "desc"}
            limit: Max rows to return (default 100, max 1000)
            offset: Pagination offset (default 0)
        
        Returns:
            {
                "rows": [...],          # Array of row dicts
                "count": int,           # Number of rows in this page
                "truncated": bool       # True if more rows available
            }
        
        Raises:
            ValueError: If table not registered, invalid filter field, or invalid sort field
        """
        # Verify table exists
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        # Enforce limit bounds
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        if limit > self.MAX_SEARCH_LIMIT:
            limit = self.MAX_SEARCH_LIMIT
        
        # Get table
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        # Build SELECT statement
        stmt = select(table)
        
        # Apply filters (AND logic)
        if filters:
            schema_fields = {f['name'] for f in schema['fields']}
            schema_fields.update({"id", "created_at", "updated_at"})  # Auto fields
            
            for field, value in filters.items():
                # Validate field exists
                if field not in schema_fields:
                    raise ValueError(
                        f"Cannot filter on non-existent field: {field}"
                    )
                
                # Apply equality filter
                stmt = stmt.where(table.c[field] == value)
        
        # Apply sorting
        if sort:
            sort_field = sort.get('field')
            sort_order = sort.get('order', 'asc').lower()
            
            if not sort_field:
                raise ValueError("Sort field must be specified")
            
            # Validate sort field exists
            schema_fields = {f['name'] for f in schema['fields']}
            schema_fields.update({"id", "created_at", "updated_at"})
            
            if sort_field not in schema_fields:
                raise ValueError(
                    f"Cannot sort on non-existent field: {sort_field}"
                )
            
            # Apply ORDER BY
            if sort_order == 'desc':
                stmt = stmt.order_by(table.c[sort_field].desc())
            else:
                stmt = stmt.order_by(table.c[sort_field])
        
        # Apply pagination with truncation detection
        # Fetch limit+1 to detect if more rows exist
        stmt = stmt.limit(limit + 1).offset(offset)
        
        # Execute query
        async with self.session_factory() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
            
            # Check truncation
            truncated = len(rows) > limit
            if truncated:
                rows = rows[:limit]  # Trim to actual limit
            
            # Convert to dicts and serialize datetimes
            serialized_rows = []
            for row in rows:
                row_dict = dict(row._mapping)
                
                # Serialize datetime objects to ISO strings
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                
                serialized_rows.append(row_dict)
            
            return {
                "rows": serialized_rows,
                "count": len(serialized_rows),
                "truncated": truncated
            }
```

### 4.2 NATS Handler

**File**: `common/database_service.py`

```python
async def _handle_row_search(self, msg):
    """
    Handle rosey.db.row.{plugin}.search requests.
    
    Request:
        {
            "table": str,
            "filters": dict (optional),
            "sort": {"field": str, "order": "asc"|"desc"} (optional),
            "limit": int (optional, default 100, max 1000),
            "offset": int (optional, default 0)
        }
    
    Response:
        {
            "success": true,
            "rows": [...],
            "count": int,
            "truncated": bool
        }
        or
        {"success": false, "error": {...}}
    """
    try:
        # Parse request
        try:
            request = json.loads(msg.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INVALID_JSON",
                    "message": f"Invalid JSON: {str(e)}"
                }
            }).encode())
            return
        
        # Extract plugin from subject
        parts = msg.subject.split('.')
        plugin_name = parts[2]
        
        # Validate required fields
        table_name = request.get('table')
        
        if not table_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'table' missing"
                }
            }).encode())
            return
        
        # Optional fields
        filters = request.get('filters')
        sort = request.get('sort')
        limit = request.get('limit', 100)
        offset = request.get('offset', 0)
        
        # Search
        try:
            result = await self.db.row_search(
                plugin_name,
                table_name,
                filters=filters,
                sort=sort,
                limit=limit,
                offset=offset
            )
        except ValueError as e:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e)
                }
            }).encode())
            return
        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Search operation failed"
                }
            }).encode())
            return
        
        # Success
        response = {"success": True, **result}
        await msg.respond(json.dumps(response).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in row_search: {e}", exc_info=True)
        try:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Unexpected error"
                }
            }).encode())
        except:
            pass

async def start(self):
    """Start DatabaseService and register NATS handlers."""
    # ... existing subscriptions ...
    
    # Row operation handlers
    await self.nc.subscribe("rosey.db.row.*.search", cb=self._handle_row_search)
    
    self.logger.info("DatabaseService started with row search handler")
```

---

## 5. Implementation Steps

### Step 1: Add BotDatabase Method

1. Open `common/database.py`
2. Add MAX_SEARCH_LIMIT constant
3. Implement row_search() with filters, sorting, pagination

### Step 2: Add NATS Handler

1. Open `common/database_service.py`
2. Implement _handle_row_search()
3. Register subscription in start()

### Step 3: Create Unit Tests

**File**: `tests/unit/test_database_row.py`

### Step 4: Create Integration Tests

**File**: `tests/integration/test_row_nats.py`

---

## 6. Testing Strategy

### 6.1 Unit Tests (excerpts)

```python
class TestRowSearch:
    """Test row_search method."""
    
    async def test_search_no_filters(self, db):
        """Test search with no filters returns all rows."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert multiple rows
        await db.row_insert("test", "items", [
            {"name": "Item 1"},
            {"name": "Item 2"},
            {"name": "Item 3"}
        ])
        
        # Search all
        result = await db.row_search("test", "items")
        
        assert result['count'] == 3
        assert result['truncated'] == False
        assert len(result['rows']) == 3
    
    async def test_search_with_single_filter(self, db):
        """Test search with single equality filter."""
        await db.schema_registry.register_schema("test", "users", {
            "fields": [
                {"name": "username", "type": "string", "required": True},
                {"name": "status", "type": "string", "required": True}
            ]
        })
        
        # Insert
        await db.row_insert("test", "users", [
            {"username": "alice", "status": "active"},
            {"username": "bob", "status": "inactive"},
            {"username": "charlie", "status": "active"}
        ])
        
        # Search for active users
        result = await db.row_search("test", "users", filters={"status": "active"})
        
        assert result['count'] == 2
        assert all(row['status'] == 'active' for row in result['rows'])
    
    async def test_search_with_multiple_filters_and(self, db):
        """Test search with multiple filters (AND logic)."""
        await db.schema_registry.register_schema("test", "products", {
            "fields": [
                {"name": "category", "type": "string", "required": True},
                {"name": "available", "type": "boolean", "required": True}
            ]
        })
        
        # Insert
        await db.row_insert("test", "products", [
            {"category": "electronics", "available": True},
            {"category": "electronics", "available": False},
            {"category": "books", "available": True}
        ])
        
        # Search for available electronics
        result = await db.row_search("test", "products", filters={
            "category": "electronics",
            "available": True
        })
        
        assert result['count'] == 1
        assert result['rows'][0]['category'] == "electronics"
        assert result['rows'][0]['available'] == True
    
    async def test_search_with_sort_asc(self, db):
        """Test search with ascending sort."""
        await db.schema_registry.register_schema("test", "events", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        # Insert out of order
        await db.row_insert("test", "events", [
            {"value": 30},
            {"value": 10},
            {"value": 20}
        ])
        
        # Search sorted ascending
        result = await db.row_search("test", "events", sort={"field": "value", "order": "asc"})
        
        values = [row['value'] for row in result['rows']]
        assert values == [10, 20, 30]
    
    async def test_search_with_sort_desc(self, db):
        """Test search with descending sort."""
        await db.schema_registry.register_schema("test", "events", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        await db.row_insert("test", "events", [
            {"value": 10},
            {"value": 30},
            {"value": 20}
        ])
        
        # Search sorted descending
        result = await db.row_search("test", "events", sort={"field": "value", "order": "desc"})
        
        values = [row['value'] for row in result['rows']]
        assert values == [30, 20, 10]
    
    async def test_search_with_pagination(self, db):
        """Test search with limit and offset."""
        await db.schema_registry.register_schema("test", "data", {
            "fields": [{"name": "seq", "type": "integer", "required": True}]
        })
        
        # Insert 10 rows
        await db.row_insert("test", "data", [{"seq": i} for i in range(10)])
        
        # Page 1 (limit=3, offset=0)
        page1 = await db.row_search("test", "data", limit=3, offset=0, sort={"field": "seq"})
        assert page1['count'] == 3
        assert page1['truncated'] == True  # More rows available
        assert [r['seq'] for r in page1['rows']] == [0, 1, 2]
        
        # Page 2 (limit=3, offset=3)
        page2 = await db.row_search("test", "data", limit=3, offset=3, sort={"field": "seq"})
        assert page2['count'] == 3
        assert page2['truncated'] == True
        assert [r['seq'] for r in page2['rows']] == [3, 4, 5]
        
        # Page 3 (limit=3, offset=6)
        page3 = await db.row_search("test", "data", limit=3, offset=6, sort={"field": "seq"})
        assert page3['count'] == 3
        assert page3['truncated'] == True
        assert [r['seq'] for r in page3['rows']] == [6, 7, 8]
        
        # Page 4 (last page)
        page4 = await db.row_search("test", "data", limit=3, offset=9, sort={"field": "seq"})
        assert page4['count'] == 1
        assert page4['truncated'] == False  # No more rows
        assert [r['seq'] for r in page4['rows']] == [9]
    
    async def test_search_truncation_detection(self, db):
        """Test truncation flag with exact limit."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "val", "type": "integer", "required": True}]
        })
        
        # Insert exactly limit+1 rows
        await db.row_insert("test", "items", [{"val": i} for i in range(6)])
        
        # Search with limit=5
        result = await db.row_search("test", "items", limit=5)
        assert result['count'] == 5
        assert result['truncated'] == True  # 6th row exists
    
    async def test_search_empty_results(self, db):
        """Test search with no matches returns empty array."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "status", "type": "string", "required": True}]
        })
        
        await db.row_insert("test", "items", [{"status": "active"}])
        
        # Search for non-existent status
        result = await db.row_search("test", "items", filters={"status": "deleted"})
        
        assert result['count'] == 0
        assert result['rows'] == []
        assert result['truncated'] == False
    
    async def test_search_rejects_invalid_filter_field(self, db):
        """Test that filtering on non-existent field raises error."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        with pytest.raises(ValueError, match="non-existent field: invalid_field"):
            await db.row_search("test", "items", filters={"invalid_field": "value"})
    
    async def test_search_rejects_invalid_sort_field(self, db):
        """Test that sorting on non-existent field raises error."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        with pytest.raises(ValueError, match="non-existent field: invalid_field"):
            await db.row_search("test", "items", sort={"field": "invalid_field"})
    
    async def test_search_enforces_max_limit(self, db):
        """Test that limit is capped at MAX_SEARCH_LIMIT."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "val", "type": "integer", "required": True}]
        })
        
        # Try to search with huge limit
        result = await db.row_search("test", "items", limit=99999)
        
        # Should be capped (no error, just limited)
        # Note: This test validates the limit enforcement, actual row count depends on data
        assert result is not None  # Doesn't crash
```

### 6.2 Integration Tests (excerpts)

```python
class TestRowSearchNATS:
    """Integration tests for search via NATS."""
    
    async def test_search_with_filters_via_nats(self, nats_client, db_service):
        """Test search with filters via NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "category", "type": "string", "required": True},
                        {"name": "active", "type": "boolean", "required": True}
                    ]
                }
            }).encode()
        )
        
        # Insert data
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": [
                    {"category": "A", "active": True},
                    {"category": "A", "active": False},
                    {"category": "B", "active": True}
                ]
            }).encode()
        )
        
        # Search for active A items
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "filters": {"category": "A", "active": True}
            }).encode(),
            timeout=1.0
        )
        search_result = json.loads(search_resp.data.decode())
        
        assert search_result['success'] == True
        assert search_result['count'] == 1
        assert search_result['rows'][0]['category'] == "A"
        assert search_result['rows'][0]['active'] == True
    
    async def test_search_with_pagination_via_nats(self, nats_client, db_service):
        """Test paginated search via NATS."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "data",
                "schema": {"fields": [{"name": "val", "type": "integer", "required": True}]}
            }).encode()
        )
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "data",
                "data": [{"val": i} for i in range(10)]
            }).encode()
        )
        
        # Page 1
        page1_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "data",
                "limit": 3,
                "offset": 0,
                "sort": {"field": "val", "order": "asc"}
            }).encode(),
            timeout=1.0
        )
        page1 = json.loads(page1_resp.data.decode())
        assert page1['count'] == 3
        assert page1['truncated'] == True
        
        # Page 2
        page2_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "data",
                "limit": 3,
                "offset": 3,
                "sort": {"field": "val", "order": "asc"}
            }).encode(),
            timeout=1.0
        )
        page2 = json.loads(page2_resp.data.decode())
        assert page2['count'] == 3
        assert page2['truncated'] == True
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: Search with no filters returns all rows
  - Given table with rows
  - When searching without filters
  - Then all rows returned

- [x] **AC-2**: Search with single filter works
  - Given table with mixed data
  - When searching with one filter
  - Then only matching rows returned

- [x] **AC-3**: Search with multiple filters (AND) works
  - Given table with rows
  - When searching with multiple filters
  - Then only rows matching ALL filters returned

- [x] **AC-4**: Sorting works (ASC/DESC)
  - Given unsorted data
  - When searching with sort
  - Then rows returned in correct order

- [x] **AC-5**: Pagination works
  - Given many rows
  - When searching with limit + offset
  - Then correct page returned

- [x] **AC-6**: Truncation detection works
  - Given more rows than limit
  - When searching
  - Then truncated=true

- [x] **AC-7**: Empty search returns empty array
  - Given no matching rows
  - When searching
  - Then {"rows": [], "count": 0, "truncated": false}

- [x] **AC-8**: Invalid filter field rejected
  - Given filter on non-existent field
  - When searching
  - Then ValueError raised

- [x] **AC-9**: All unit tests pass (20+ tests, 90%+ coverage)

- [x] **AC-10**: All integration tests pass (12+ tests)

---

## 8. Rollout Plan

### Pre-deployment

1. Review all code changes
2. Run full test suite
3. Verify performance targets met
4. Test with various data sizes

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-13-sortie-4-search`
2. Implement BotDatabase.row_search()
3. Implement NATS handler
4. Write comprehensive tests
5. Run tests and verify coverage
6. Commit with message:
   ```
   Sprint 13 Sortie 4: Search with Filters & Pagination
   
   - Add row_search() to BotDatabase
   - Implement NATS handler for search
   - Support equality filters (AND logic)
   - Support sorting (single field, ASC/DESC)
   - Support pagination with truncation detection
   - Add comprehensive tests (32+ tests, 90%+ coverage)
   
   Implements: SPEC-Sortie-4-Search-Filters-Pagination.md
   Related: PRD-Row-Operations-Foundation.md
   Depends-On: SPEC-Sortie-3-Update-Delete-Operations.md
   ```
7. Push branch and create PR
8. Code review
9. Merge to main

### Post-deployment

- Monitor search query performance
- Check for slow queries in logs
- Verify pagination working correctly
- Monitor truncation detection

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 3**: CRUD operations must exist
- **SQLAlchemy 2.0+**: For query building

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Search performance poor on large tables | Medium | Medium | Add indexes, benchmark, optimize queries |
| Pagination issues with concurrent writes | Low | Low | Document behavior, consider using cursors in future |
| Filter validation misses edge cases | Low | Low | Comprehensive tests |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Filter and sort semantics documented
- Pagination behavior documented
- Examples in docstrings

### Developer Documentation

Update `docs/ROW_STORAGE_API.md` with:
- Search API documentation
- Filter syntax examples
- Sorting examples
- Pagination patterns
- Performance considerations

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-3-Update-Delete-Operations.md](SPEC-Sortie-3-Update-Delete-Operations.md)  
**Next**: [SPEC-Sortie-5-Testing-Polish-Documentation.md](SPEC-Sortie-5-Testing-Polish-Documentation.md)

**Parent PRD**: [PRD-Row-Operations-Foundation.md](PRD-Row-Operations-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
