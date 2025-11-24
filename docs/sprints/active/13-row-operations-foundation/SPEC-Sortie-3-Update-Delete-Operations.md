# SPEC: Sortie 3 - Update & Delete Operations

**Sprint**: 13 (Row Operations Foundation)  
**Sortie**: 3 of 5  
**Estimated Effort**: ~4 hours  
**Branch**: `feature/sprint-13-sortie-3-update-delete`  
**Dependencies**: Sorties 1-2 (SchemaRegistry, Insert & Select)

---

## 1. Overview

Implement update and delete operations for row-based storage, completing the CRUD operations for plugin tables.

**What This Sortie Achieves**:

- Update existing rows with partial or full updates
- Delete rows by ID (idempotent)
- Enforce primary key immutability
- NATS handlers for update/delete
- Validation and type coercion for updates
- Safe deletion with existence checks

---

## 2. Scope and Non-Goals

### In Scope

✅ BotDatabase.row_update() method (partial updates)  
✅ BotDatabase.row_delete() method (idempotent deletion)  
✅ DatabaseService NATS handlers (_handle_row_update, _handle_row_delete)  
✅ Primary key (id) immutability enforcement  
✅ Type coercion and validation for updates  
✅ Unit tests (15+ tests)  
✅ Integration tests (8+ tests with NATS)

### Out of Scope

❌ Bulk updates/deletes (future enhancement)  
❌ Search and filter operations (Sortie 4)  
❌ Soft deletes (future enhancement)  
❌ Cascade deletes  
❌ Update history/auditing

---

## 3. Requirements

### Functional Requirements

**FR-1**: row_update() must:
- Accept row ID and partial update data (dict)
- Only update specified fields (preserve unspecified)
- Validate and coerce types like insert
- Return updated row ID and modified flag
- Reject updates to primary key (id)
- Reject updates to auto-managed fields (created_at)
- Return {"exists": False} if row not found

**FR-2**: row_delete() must:
- Accept row ID
- Delete row if exists
- Return success even if row doesn't exist (idempotent)
- Return {"deleted": True/False} indicating if row was actually deleted

**FR-3**: NATS handlers must:
- Validate JSON request format
- Call corresponding BotDatabase methods
- Return success/error responses
- Handle database errors gracefully
- Log all operations

**FR-4**: Immutability enforcement:
- Attempting to update "id" raises ValueError
- Attempting to update "created_at" raises ValueError
- "updated_at" is auto-managed (set to current timestamp)

### Non-Functional Requirements

**NFR-1 Performance**:
- Update operation: <10ms p95 latency
- Delete operation: <5ms p95 latency

**NFR-2 Reliability**:
- All operations use transactions
- Invalid updates rejected before DB access
- Clear error messages for all failures

**NFR-3 Testing**: ≥90% code coverage for update/delete operations

---

## 4. Technical Design

### 4.1 BotDatabase Methods

**File**: `common/database.py`

```python
from typing import Any
from datetime import datetime, timezone
from sqlalchemy import update, delete, select, Table

class BotDatabase:
    """Database access layer."""
    
    # ... existing methods ...
    
    IMMUTABLE_FIELDS = {"id", "created_at"}  # Fields that cannot be updated
    
    async def row_update(
        self,
        plugin_name: str,
        table_name: str,
        row_id: int,
        data: dict
    ) -> dict:
        """
        Update row by primary key ID (partial update).
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            row_id: Primary key ID
            data: Fields to update (partial dict)
        
        Returns:
            {"id": 42, "updated": True} if row existed and was updated
            {"exists": False} if row not found
        
        Raises:
            ValueError: If table not registered, data invalid, or immutable field update attempted
        """
        # Verify table exists
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        # Check for empty update
        if not data:
            raise ValueError("No data provided for update")
        
        # Check for immutable field updates
        immutable_attempted = self.IMMUTABLE_FIELDS.intersection(data.keys())
        if immutable_attempted:
            raise ValueError(
                f"Cannot update immutable fields: {', '.join(immutable_attempted)}"
            )
        
        # Validate and coerce update data
        validated_data = self._validate_and_coerce_row(data, schema)
        
        # Add updated_at timestamp
        validated_data['updated_at'] = datetime.now(timezone.utc)
        
        # Get table
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        # Check if row exists first
        async with self.session_factory() as session:
            # Check existence
            check_stmt = select(table.c.id).where(table.c.id == row_id)
            result = await session.execute(check_stmt)
            exists = result.scalar() is not None
            
            if not exists:
                return {"exists": False}
            
            # Perform update
            stmt = (
                update(table)
                .where(table.c.id == row_id)
                .values(**validated_data)
            )
            await session.execute(stmt)
            await session.commit()
            
            return {
                "id": row_id,
                "updated": True
            }
    
    async def row_delete(
        self,
        plugin_name: str,
        table_name: str,
        row_id: int
    ) -> dict:
        """
        Delete row by primary key ID (idempotent).
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            row_id: Primary key ID
        
        Returns:
            {"deleted": True} if row existed and was deleted
            {"deleted": False} if row did not exist
        
        Raises:
            ValueError: If table not registered
        """
        # Verify table exists
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        # Get table
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        # Delete
        async with self.session_factory() as session:
            stmt = delete(table).where(table.c.id == row_id)
            result = await session.execute(stmt)
            await session.commit()
            
            # Check if any rows were deleted
            deleted = result.rowcount > 0
            
            return {
                "deleted": deleted
            }
```

### 4.2 NATS Handlers

**File**: `common/database_service.py`

```python
async def _handle_row_update(self, msg):
    """
    Handle rosey.db.row.{plugin}.update requests.
    
    Request:
        {
            "table": str,
            "id": int,
            "data": dict
        }
    
    Response:
        {"success": true, "id": 42, "updated": true}
        or
        {"success": true, "exists": false}
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
        row_id = request.get('id')
        data = request.get('data')
        
        if not table_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'table' missing"
                }
            }).encode())
            return
        
        if row_id is None:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'id' missing"
                }
            }).encode())
            return
        
        if data is None:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'data' missing"
                }
            }).encode())
            return
        
        # Update
        try:
            result = await self.db.row_update(plugin_name, table_name, row_id, data)
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
            self.logger.error(f"Update failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Update operation failed"
                }
            }).encode())
            return
        
        # Success
        response = {"success": True, **result}
        await msg.respond(json.dumps(response).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in row_update: {e}", exc_info=True)
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

async def _handle_row_delete(self, msg):
    """
    Handle rosey.db.row.{plugin}.delete requests.
    
    Request:
        {
            "table": str,
            "id": int
        }
    
    Response:
        {"success": true, "deleted": true/false}
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
        row_id = request.get('id')
        
        if not table_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'table' missing"
                }
            }).encode())
            return
        
        if row_id is None:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'id' missing"
                }
            }).encode())
            return
        
        # Delete
        try:
            result = await self.db.row_delete(plugin_name, table_name, row_id)
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
            self.logger.error(f"Delete failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Delete operation failed"
                }
            }).encode())
            return
        
        # Success
        response = {"success": True, **result}
        await msg.respond(json.dumps(response).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in row_delete: {e}", exc_info=True)
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
    await self.nc.subscribe("rosey.db.row.*.update", cb=self._handle_row_update)
    await self.nc.subscribe("rosey.db.row.*.delete", cb=self._handle_row_delete)
    
    self.logger.info("DatabaseService started with row update/delete handlers")
```

---

## 5. Implementation Steps

### Step 1: Add BotDatabase Methods

1. Open `common/database.py`
2. Add IMMUTABLE_FIELDS constant
3. Implement row_update() with immutability checks
4. Implement row_delete() (idempotent)

### Step 2: Add NATS Handlers

1. Open `common/database_service.py`
2. Implement _handle_row_update()
3. Implement _handle_row_delete()
4. Register subscriptions in start()

### Step 3: Create Unit Tests

**File**: `tests/unit/test_database_row.py`

### Step 4: Create Integration Tests

**File**: `tests/integration/test_row_nats.py`

---

## 6. Testing Strategy

### 6.1 Unit Tests (excerpts)

```python
class TestRowUpdate:
    """Test row_update method."""
    
    async def test_update_single_field(self, db):
        """Test updating a single field (partial update)."""
        # Register schema
        await db.schema_registry.register_schema("test", "items", {
            "fields": [
                {"name": "name", "type": "string", "required": True},
                {"name": "value", "type": "integer", "required": False}
            ]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {
            "name": "Item 1",
            "value": 100
        })
        row_id = insert_result['id']
        
        # Update only value
        update_result = await db.row_update("test", "items", row_id, {"value": 200})
        
        assert update_result['updated'] == True
        assert update_result['id'] == row_id
        
        # Verify name unchanged
        select_result = await db.row_select("test", "items", row_id)
        assert select_result['data']['name'] == "Item 1"
        assert select_result['data']['value'] == 200
    
    async def test_update_nonexistent_row(self, db):
        """Test updating a row that doesn't exist."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        result = await db.row_update("test", "items", 99999, {"name": "New Name"})
        assert result['exists'] == False
    
    async def test_update_rejects_id_change(self, db):
        """Test that updating primary key is rejected."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        insert_result = await db.row_insert("test", "items", {"name": "Item"})
        row_id = insert_result['id']
        
        # Try to update id
        with pytest.raises(ValueError, match="immutable fields"):
            await db.row_update("test", "items", row_id, {"id": 999})
    
    async def test_update_rejects_created_at_change(self, db):
        """Test that updating created_at is rejected."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        insert_result = await db.row_insert("test", "items", {"name": "Item"})
        row_id = insert_result['id']
        
        # Try to update created_at
        with pytest.raises(ValueError, match="immutable fields"):
            await db.row_update("test", "items", row_id, {
                "created_at": "2025-01-01T00:00:00Z"
            })
    
    async def test_update_sets_updated_at(self, db):
        """Test that updated_at is automatically set."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {"name": "Original"})
        row_id = insert_result['id']
        
        # Get initial timestamps
        select1 = await db.row_select("test", "items", row_id)
        created_at = select1['data']['created_at']
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Update
        await db.row_update("test", "items", row_id, {"name": "Updated"})
        
        # Verify updated_at changed
        select2 = await db.row_select("test", "items", row_id)
        assert select2['data']['created_at'] == created_at  # Unchanged
        assert select2['data']['updated_at'] > created_at   # Changed
    
    async def test_update_coerces_types(self, db):
        """Test type coercion in updates."""
        await db.schema_registry.register_schema("test", "data", {
            "fields": [
                {"name": "count", "type": "integer", "required": True},
                {"name": "timestamp", "type": "datetime", "required": False}
            ]
        })
        
        insert_result = await db.row_insert("test", "data", {"count": 10})
        row_id = insert_result['id']
        
        # Update with string types
        await db.row_update("test", "data", row_id, {
            "count": "42",  # String -> integer
            "timestamp": "2025-11-24T10:00:00Z"  # String -> datetime
        })
        
        # Verify coercion worked
        select_result = await db.row_select("test", "data", row_id)
        assert select_result['data']['count'] == 42
        assert 'timestamp' in select_result['data']

class TestRowDelete:
    """Test row_delete method."""
    
    async def test_delete_existing_row(self, db):
        """Test deleting an existing row."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {"name": "Item"})
        row_id = insert_result['id']
        
        # Delete
        delete_result = await db.row_delete("test", "items", row_id)
        assert delete_result['deleted'] == True
        
        # Verify gone
        select_result = await db.row_select("test", "items", row_id)
        assert select_result['exists'] == False
    
    async def test_delete_nonexistent_row_idempotent(self, db):
        """Test that deleting non-existent row is idempotent."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Delete non-existent row
        result = await db.row_delete("test", "items", 99999)
        assert result['deleted'] == False  # Returns False but doesn't error
    
    async def test_delete_twice_idempotent(self, db):
        """Test that deleting same row twice is idempotent."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {"name": "Item"})
        row_id = insert_result['id']
        
        # First delete
        result1 = await db.row_delete("test", "items", row_id)
        assert result1['deleted'] == True
        
        # Second delete
        result2 = await db.row_delete("test", "items", row_id)
        assert result2['deleted'] == False  # No error, just returns False
```

### 6.2 Integration Tests (excerpts)

```python
class TestRowUpdateDeleteNATS:
    """Integration tests for update/delete via NATS."""
    
    async def test_update_via_nats(self, nats_client, db_service):
        """Test update via NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "value", "type": "string", "required": True}]
                }
            }).encode()
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({"table": "items", "data": {"value": "original"}}).encode()
        )
        insert_result = json.loads(insert_resp.data.decode())
        row_id = insert_result['id']
        
        # Update
        update_resp = await nats_client.request(
            "rosey.db.row.test.update",
            json.dumps({
                "table": "items",
                "id": row_id,
                "data": {"value": "updated"}
            }).encode(),
            timeout=1.0
        )
        update_result = json.loads(update_resp.data.decode())
        assert update_result['success'] == True
        assert update_result['updated'] == True
        
        # Verify
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({"table": "items", "id": row_id}).encode()
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['data']['value'] == "updated"
    
    async def test_delete_via_nats(self, nats_client, db_service):
        """Test delete via NATS."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "temp",
                "schema": {"fields": [{"name": "val", "type": "string", "required": True}]}
            }).encode()
        )
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({"table": "temp", "data": {"val": "test"}}).encode()
        )
        row_id = json.loads(insert_resp.data.decode())['id']
        
        # Delete
        delete_resp = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "temp", "id": row_id}).encode(),
            timeout=1.0
        )
        delete_result = json.loads(delete_resp.data.decode())
        assert delete_result['success'] == True
        assert delete_result['deleted'] == True
        
        # Verify gone
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({"table": "temp", "id": row_id}).encode()
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['exists'] == False
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: Partial update works
  - Given existing row
  - When updating single field
  - Then only that field changes

- [x] **AC-2**: Update returns exists=false for missing row
  - Given non-existent row ID
  - When updating
  - Then {"exists": False} returned

- [x] **AC-3**: Primary key immutable
  - Given attempt to update "id"
  - When updating
  - Then ValueError raised

- [x] **AC-4**: created_at immutable
  - Given attempt to update "created_at"
  - When updating
  - Then ValueError raised

- [x] **AC-5**: updated_at auto-managed
  - Given any update
  - When update succeeds
  - Then updated_at set to current timestamp

- [x] **AC-6**: Delete works
  - Given existing row
  - When deleting
  - Then row removed and {"deleted": True}

- [x] **AC-7**: Delete is idempotent
  - Given non-existent row
  - When deleting
  - Then {"deleted": False} (no error)

- [x] **AC-8**: All unit tests pass (15+ tests, 90%+ coverage)

- [x] **AC-9**: All integration tests pass (8+ tests)

---

## 8. Rollout Plan

### Pre-deployment

1. Review all code changes
2. Run full test suite
3. Verify performance targets met

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-13-sortie-3-update-delete`
2. Implement BotDatabase methods (row_update, row_delete)
3. Implement NATS handlers
4. Write comprehensive tests
5. Run tests and verify coverage
6. Commit with message:
   ```
   Sprint 13 Sortie 3: Update & Delete Operations
   
   - Add row_update() and row_delete() to BotDatabase
   - Implement NATS handlers for update/delete
   - Enforce primary key immutability
   - Add comprehensive tests (23+ tests, 90%+ coverage)
   
   Implements: SPEC-Sortie-3-Update-Delete-Operations.md
   Related: PRD-Row-Operations-Foundation.md
   Depends-On: SPEC-Sortie-2-Insert-Select-Operations.md
   ```
7. Push branch and create PR
8. Code review
9. Merge to main

### Post-deployment

- Monitor operation latencies
- Check for validation errors in logs
- Verify immutability enforcement working

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 2**: Insert & Select operations must exist
- **SQLAlchemy 2.0+**: For update/delete statements

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Race conditions on updates | Low | Medium | Use transactions, test concurrency |
| Accidental bulk deletes | Low | High | Single-ID only in this sortie |
| Performance with large updates | Low | Low | Benchmark, optimize if needed |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Immutability rules documented
- Examples in docstrings

### Developer Documentation

Update `docs/ROW_STORAGE_API.md` with:
- Update API documentation
- Delete API documentation
- Immutability rules
- Examples

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-2-Insert-Select-Operations.md](SPEC-Sortie-2-Insert-Select-Operations.md)  
**Next**: [SPEC-Sortie-4-Search-Filters-Pagination.md](SPEC-Sortie-4-Search-Filters-Pagination.md)

**Parent PRD**: [PRD-Row-Operations-Foundation.md](PRD-Row-Operations-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
