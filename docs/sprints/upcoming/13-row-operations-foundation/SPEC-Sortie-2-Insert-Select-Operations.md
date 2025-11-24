# SPEC: Sortie 2 - Insert & Select Operations

**Sprint**: 13 (Row Operations Foundation)  
**Sortie**: 2 of 5  
**Estimated Effort**: ~5 hours  
**Branch**: `feature/sprint-13-sortie-2-insert-select`  
**Dependencies**: Sortie 1 (SchemaRegistry must exist)

---

## 1. Overview

Implement insert and select operations for row-based storage, along with NATS handlers to expose these operations to plugins via the event bus.

**What This Sortie Achieves**:

- Insert single or bulk rows with validation
- Select rows by primary key ID
- NATS handlers for insert/select/schema registration
- Type coercion and validation
- Auto-increment ID handling
- Plugin namespace isolation

---

## 2. Scope and Non-Goals

### In Scope

✅ BotDatabase.row_insert() method (single + bulk)  
✅ BotDatabase.row_select() method (by ID)  
✅ DatabaseService NATS handlers (_handle_row_insert, _handle_row_select, _handle_schema_register)  
✅ Type coercion (string -> datetime, int -> float, etc.)  
✅ Data validation against schema  
✅ Plugin isolation enforcement  
✅ Unit tests (20+ tests)  
✅ Integration tests (10+ tests with NATS)

### Out of Scope

❌ Update/delete operations (Sortie 3)  
❌ Search with filters (Sortie 4)  
❌ Complex queries or joins  
❌ Schema migrations (Sprint 15)

---

## 3. Requirements

### Functional Requirements

**FR-1**: row_insert() must:
- Accept single dict or list of dicts
- Validate all fields against schema
- Coerce types where possible (e.g., "2025-11-24" -> datetime)
- Insert into correct table (plugin_name_table_name)
- Return auto-generated ID(s)
- Reject invalid data with clear error

**FR-2**: row_select() must:
- Accept row ID (integer)
- Return row data if exists
- Return {"exists": False} if not found
- Include all fields plus id, created_at, updated_at

**FR-3**: NATS handlers must:
- Validate JSON request format
- Call corresponding BotDatabase methods
- Return success/error responses
- Handle database errors gracefully
- Log all operations

**FR-4**: Type coercion must support:
- String -> datetime (ISO 8601 format)
- String/int -> float
- Any -> boolean (truthy/falsy)
- String -> integer (if valid number)

**FR-5**: Schema registration handler must:
- Accept schema definition via NATS
- Validate and register schema
- Return success/failure

### Non-Functional Requirements

**NFR-1 Performance**:
- Single insert: <10ms p95 latency
- Bulk insert (100 rows): <100ms
- Select by ID: <5ms p95 latency

**NFR-2 Reliability**:
- All operations use transactions
- Invalid data rejected before DB access
- Clear error messages for all failures

**NFR-3 Testing**: ≥90% code coverage for row operations

---

## 4. Technical Design

### 4.1 BotDatabase Methods

**File**: `common/database.py`

```python
from typing import Any
from datetime import datetime
from sqlalchemy import insert, select, Table, MetaData
from sqlalchemy.ext.asyncio import AsyncSession

class BotDatabase:
    """Database access layer."""
    
    def __init__(self, db_url: str):
        # ... existing init ...
        self.schema_registry = SchemaRegistry(self)
        self._table_cache = {}  # Cache reflected tables
    
    async def initialize(self):
        """Initialize database and load schemas."""
        await self.schema_registry.load_cache()
    
    def get_table(self, full_table_name: str) -> Table:
        """
        Get table object (with caching).
        
        Args:
            full_table_name: Full table name (e.g., "quote_db_quotes")
        
        Returns:
            SQLAlchemy Table object
        """
        if full_table_name not in self._table_cache:
            metadata = MetaData()
            table = Table(full_table_name, metadata, autoload_with=self.engine.sync_engine)
            self._table_cache[full_table_name] = table
        
        return self._table_cache[full_table_name]
    
    def _validate_and_coerce_row(self, data: dict, schema: dict) -> dict:
        """
        Validate row data against schema and coerce types.
        
        Args:
            data: Row data to validate
            schema: Schema definition
        
        Returns:
            Validated and coerced data
        
        Raises:
            ValueError: If validation fails
        """
        result = {}
        schema_fields = {f['name']: f for f in schema['fields']}
        
        # Check required fields
        for field in schema['fields']:
            if field.get('required', False) and field['name'] not in data:
                raise ValueError(f"Missing required field: {field['name']}")
        
        # Validate and coerce each field in data
        for key, value in data.items():
            if key not in schema_fields:
                raise ValueError(f"Unknown field: {key}")
            
            field_def = schema_fields[key]
            field_type = field_def['type']
            
            # Handle None values
            if value is None:
                if field_def.get('required', False):
                    raise ValueError(f"Field '{key}' cannot be null")
                result[key] = None
                continue
            
            # Type coercion
            try:
                if field_type == 'string':
                    result[key] = str(value)
                
                elif field_type == 'text':
                    result[key] = str(value)
                
                elif field_type == 'integer':
                    if isinstance(value, str):
                        result[key] = int(value)
                    elif isinstance(value, (int, float)):
                        result[key] = int(value)
                    else:
                        raise ValueError(f"Cannot convert {type(value)} to integer")
                
                elif field_type == 'float':
                    result[key] = float(value)
                
                elif field_type == 'boolean':
                    if isinstance(value, bool):
                        result[key] = value
                    elif isinstance(value, str):
                        result[key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        result[key] = bool(value)
                
                elif field_type == 'datetime':
                    if isinstance(value, datetime):
                        result[key] = value
                    elif isinstance(value, str):
                        # Try ISO 8601 format
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        raise ValueError(f"Cannot convert {type(value)} to datetime")
            
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Field '{key}': Cannot convert value to {field_type}: {e}"
                )
        
        return result
    
    async def row_insert(
        self,
        plugin_name: str,
        table_name: str,
        data: dict | list[dict]
    ) -> dict:
        """
        Insert row(s) into plugin table.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            data: Single dict or list of dicts to insert
        
        Returns:
            Single insert: {"id": 42, "created": True}
            Bulk insert: {"ids": [42, 43, 44], "created": 3}
        
        Raises:
            ValueError: If table not registered or data invalid
        """
        # Get schema
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'. "
                f"Register schema first using schema_register."
            )
        
        # Handle bulk vs single
        is_bulk = isinstance(data, list)
        rows = data if is_bulk else [data]
        
        if len(rows) == 0:
            raise ValueError("No data provided for insert")
        
        # Validate and coerce all rows
        validated_rows = []
        for i, row in enumerate(rows):
            try:
                validated = self._validate_and_coerce_row(row, schema)
                validated_rows.append(validated)
            except ValueError as e:
                raise ValueError(f"Row {i}: {e}")
        
        # Get table
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        # Insert
        async with self.session_factory() as session:
            if is_bulk:
                # Bulk insert with RETURNING
                stmt = insert(table).returning(table.c.id)
                result = await session.execute(stmt, validated_rows)
                ids = [row[0] for row in result.fetchall()]
                await session.commit()
                
                return {
                    "ids": ids,
                    "created": len(ids)
                }
            else:
                # Single insert
                stmt = insert(table).values(**validated_rows[0]).returning(table.c.id)
                result = await session.execute(stmt)
                row_id = result.scalar()
                await session.commit()
                
                return {
                    "id": row_id,
                    "created": True
                }
    
    async def row_select(
        self,
        plugin_name: str,
        table_name: str,
        row_id: int
    ) -> dict:
        """
        Select row by primary key ID.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            row_id: Primary key ID
        
        Returns:
            {"exists": True, "data": {...}} if found
            {"exists": False} if not found
        """
        # Verify table exists
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        # Get table and select
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        async with self.session_factory() as session:
            stmt = select(table).where(table.c.id == row_id)
            result = await session.execute(stmt)
            row = result.fetchone()
            
            if row:
                # Convert to dict and serialize datetimes
                data = dict(row._mapping)
                
                # Convert datetime objects to ISO strings
                for key, value in data.items():
                    if isinstance(value, datetime):
                        data[key] = value.isoformat()
                
                return {
                    "exists": True,
                    "data": data
                }
            else:
                return {
                    "exists": False
                }
```

### 4.2 NATS Handlers

**File**: `common/database_service.py`

```python
async def _handle_schema_register(self, msg):
    """
    Handle rosey.db.row.{plugin}.schema.register requests.
    
    Request:
        {
            "table": str,
            "schema": {
                "fields": [
                    {"name": str, "type": str, "required": bool}
                ]
            }
        }
    
    Response:
        {"success": true} or {"success": false, "error": {...}}
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
        plugin_name = parts[2]  # rosey.db.row.{plugin}.schema.register
        
        # Validate required fields
        table_name = request.get('table')
        schema = request.get('schema')
        
        if not table_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'table' missing"
                }
            }).encode())
            return
        
        if not schema:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'schema' missing"
                }
            }).encode())
            return
        
        # Register schema
        try:
            await self.db.schema_registry.register_schema(
                plugin_name,
                table_name,
                schema
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
            self.logger.error(f"Schema registration failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Schema registration failed"
                }
            }).encode())
            return
        
        # Success
        await msg.respond(json.dumps({
            "success": True
        }).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in schema_register: {e}", exc_info=True)
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

async def _handle_row_insert(self, msg):
    """
    Handle rosey.db.row.{plugin}.insert requests.
    
    Request:
        {
            "table": str,
            "data": dict | list[dict]
        }
    
    Response:
        Single: {"success": true, "id": 42}
        Bulk: {"success": true, "ids": [42, 43], "created": 2}
        Error: {"success": false, "error": {...}}
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
        
        if data is None:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'data' missing"
                }
            }).encode())
            return
        
        # Insert
        try:
            result = await self.db.row_insert(plugin_name, table_name, data)
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
            self.logger.error(f"Insert failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Insert operation failed"
                }
            }).encode())
            return
        
        # Success
        response = {"success": True, **result}
        await msg.respond(json.dumps(response).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in row_insert: {e}", exc_info=True)
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

async def _handle_row_select(self, msg):
    """
    Handle rosey.db.row.{plugin}.select requests.
    
    Request:
        {
            "table": str,
            "id": int
        }
    
    Response:
        {"success": true, "exists": true, "data": {...}}
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
        
        # Select
        try:
            result = await self.db.row_select(plugin_name, table_name, row_id)
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
            self.logger.error(f"Select failed: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Select operation failed"
                }
            }).encode())
            return
        
        # Success
        response = {"success": True, **result}
        await msg.respond(json.dumps(response).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in row_select: {e}", exc_info=True)
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
    # ... existing code ...
    
    # Row operation handlers (wildcard plugin subscription)
    await self.nc.subscribe("rosey.db.row.*.schema.register", cb=self._handle_schema_register)
    await self.nc.subscribe("rosey.db.row.*.insert", cb=self._handle_row_insert)
    await self.nc.subscribe("rosey.db.row.*.select", cb=self._handle_row_select)
    
    self.logger.info("DatabaseService started with row operation handlers")
```

---

## 5. Implementation Steps

### Step 1: Add BotDatabase Methods

1. Open `common/database.py`
2. Add get_table() with caching
3. Add _validate_and_coerce_row() helper
4. Implement row_insert() (single + bulk)
5. Implement row_select()

### Step 2: Add NATS Handlers

1. Open `common/database_service.py`
2. Implement _handle_schema_register()
3. Implement _handle_row_insert()
4. Implement _handle_row_select()
5. Register wildcard subscriptions in start()

### Step 3: Create Unit Tests

**File**: `tests/unit/test_database_row.py`

### Step 4: Create Integration Tests

**File**: `tests/integration/test_row_nats.py`

---

## 6. Testing Strategy

### 6.1 Unit Tests (excerpts)

```python
class TestRowInsert:
    """Test row_insert method."""
    
    async def test_insert_single_row(self, db):
        """Test inserting a single row."""
        # Register schema
        await db.schema_registry.register_schema("test", "quotes", {
            "fields": [
                {"name": "text", "type": "text", "required": True}
            ]
        })
        
        # Insert
        result = await db.row_insert("test", "quotes", {"text": "Hello"})
        
        assert result['created'] == True
        assert isinstance(result['id'], int)
    
    async def test_insert_bulk_rows(self, db):
        """Test bulk insert."""
        await db.schema_registry.register_schema("test", "data", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        result = await db.row_insert("test", "data", [
            {"value": 1},
            {"value": 2},
            {"value": 3}
        ])
        
        assert result['created'] == 3
        assert len(result['ids']) == 3
    
    async def test_insert_validates_required_fields(self, db):
        """Test that required fields are enforced."""
        await db.schema_registry.register_schema("test", "users", {
            "fields": [
                {"name": "username", "type": "string", "required": True},
                {"name": "email", "type": "string", "required": False}
            ]
        })
        
        # Missing required field
        with pytest.raises(ValueError, match="required field: username"):
            await db.row_insert("test", "users", {"email": "test@example.com"})
    
    async def test_insert_coerces_types(self, db):
        """Test type coercion."""
        await db.schema_registry.register_schema("test", "events", {
            "fields": [
                {"name": "timestamp", "type": "datetime", "required": True},
                {"name": "count", "type": "integer", "required": True}
            ]
        })
        
        result = await db.row_insert("test", "events", {
            "timestamp": "2025-11-24T10:30:00Z",  # String -> datetime
            "count": "42"  # String -> integer
        })
        
        assert result['created'] == True

class TestRowSelect:
    """Test row_select method."""
    
    async def test_select_existing_row(self, db):
        """Test selecting an existing row."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {"name": "Item 1"})
        row_id = insert_result['id']
        
        # Select
        result = await db.row_select("test", "items", row_id)
        
        assert result['exists'] == True
        assert result['data']['id'] == row_id
        assert result['data']['name'] == "Item 1"
        assert 'created_at' in result['data']
    
    async def test_select_nonexistent_row(self, db):
        """Test selecting a row that doesn't exist."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        result = await db.row_select("test", "items", 99999)
        assert result['exists'] == False
```

### 6.2 Integration Tests (excerpts)

```python
class TestRowNATS:
    """Integration tests for row operations via NATS."""
    
    async def test_schema_register_via_nats(self, nats_client, db_service):
        """Test schema registration via NATS."""
        response = await nats_client.request(
            "rosey.db.row.test-plugin.schema.register",
            json.dumps({
                "table": "quotes",
                "schema": {
                    "fields": [
                        {"name": "text", "type": "text", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
    
    async def test_insert_and_select_via_nats(self, nats_client, db_service):
        """Test full insert + select workflow."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "data",
                "schema": {
                    "fields": [{"name": "value", "type": "string", "required": True}]
                }
            }).encode()
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "data",
                "data": {"value": "test value"}
            }).encode(),
            timeout=1.0
        )
        insert_result = json.loads(insert_resp.data.decode())
        assert insert_result['success'] == True
        row_id = insert_result['id']
        
        # Select
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({
                "table": "data",
                "id": row_id
            }).encode(),
            timeout=1.0
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['success'] == True
        assert select_result['exists'] == True
        assert select_result['data']['value'] == "test value"
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: Single insert works
  - Given registered schema
  - When inserting single row
  - Then row created and ID returned

- [x] **AC-2**: Bulk insert works
  - Given registered schema
  - When inserting list of rows
  - Then all rows created and IDs returned

- [x] **AC-3**: Select by ID works
  - Given existing row
  - When selecting by ID
  - Then row data returned

- [x] **AC-4**: Type coercion works
  - Given string datetime value
  - When inserting
  - Then converted to datetime object

- [x] **AC-5**: Validation enforced
  - Given invalid data (missing required field)
  - When inserting
  - Then ValueError raised with clear message

- [x] **AC-6**: Plugin isolation enforced
  - Given schemas for plugin-a and plugin-b
  - When plugin-a inserts
  - Then only accessible via plugin-a namespace

- [x] **AC-7**: NATS handlers work
  - Given DatabaseService running
  - When sending NATS request
  - Then response received with correct format

- [x] **AC-8**: All unit tests pass (20+ tests, 90%+ coverage)

- [x] **AC-9**: All integration tests pass (10+ tests)

---

## 8. Rollout Plan

### Pre-deployment

1. Review all code changes
2. Run full test suite
3. Verify performance targets met

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-13-sortie-2-insert-select`
2. Implement BotDatabase methods
3. Implement NATS handlers
4. Write comprehensive tests
5. Run tests and verify coverage
6. Commit with message:
   ```
   Sprint 13 Sortie 2: Insert & Select Operations
   
   - Add row_insert() and row_select() to BotDatabase
   - Implement NATS handlers for insert/select/schema register
   - Add type coercion and validation
   - Add comprehensive tests (30+ tests, 90%+ coverage)
   
   Implements: SPEC-Sortie-2-Insert-Select-Operations.md
   Related: PRD-Row-Operations-Foundation.md
   Depends-On: SPEC-Sortie-1-Schema-Registry-Table-Creation.md
   ```
7. Push branch and create PR
8. Code review
9. Merge to main

### Post-deployment

- Monitor operation latencies
- Check for validation errors in logs
- Verify type coercion working correctly

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: SchemaRegistry must exist
- **SQLAlchemy 2.0+**: For table reflection and inserts
- **NATS**: For handlers

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Type coercion fails for edge cases | Medium | Low | Comprehensive test cases |
| Bulk insert performance poor | Low | Medium | Use SQLAlchemy bulk insert, benchmark |
| Table reflection slow | Low | Low | Cache reflected tables |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Type coercion rules documented
- Examples in docstrings

### Developer Documentation

Update `docs/ROW_STORAGE_API.md` with:
- Insert API documentation
- Select API documentation
- NATS subject patterns
- Type coercion examples

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-1-Schema-Registry-Table-Creation.md](SPEC-Sortie-1-Schema-Registry-Table-Creation.md)  
**Next**: [SPEC-Sortie-3-Update-Delete-Operations.md](SPEC-Sortie-3-Update-Delete-Operations.md)

**Parent PRD**: [PRD-Row-Operations-Foundation.md](PRD-Row-Operations-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
