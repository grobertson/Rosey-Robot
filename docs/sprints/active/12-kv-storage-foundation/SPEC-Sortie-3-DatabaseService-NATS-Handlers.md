# SPEC: Sortie 3 - DatabaseService NATS Handlers

**Sprint**: 12 (KV Storage Foundation)  
**Sortie**: 3 of 4  
**Estimated Effort**: ~6 hours  
**Branch**: `feature/sprint-12-sortie-3-nats-handlers`  
**Dependencies**: Sortie 1 (model), Sortie 2 (BotDatabase methods)

---

## 1. Overview

Implement NATS request handlers in `DatabaseService` for key-value operations. These handlers expose the BotDatabase KV methods via the event bus, enabling plugins to perform KV operations through message passing.

**What This Sortie Achieves**:

- Four NATS request handlers for KV operations
- Subject pattern: `rosey.db.kv.{operation}`
- JSON request/response validation
- Comprehensive error handling
- Integration tests with NATS

---

## 2. Scope and Non-Goals

### In Scope

✅ `_handle_kv_set` - Set/upsert handler  
✅ `_handle_kv_get` - Get handler  
✅ `_handle_kv_delete` - Delete handler  
✅ `_handle_kv_list` - List handler  
✅ Request validation (JSON schema)  
✅ Error response formatting  
✅ Integration tests with NATS (20+ tests)  
✅ Subject registration in `start()`

### Out of Scope

❌ Background cleanup task (Sortie 4)  
❌ DatabaseClient wrapper (future)  
❌ Monitoring/metrics (future enhancement)  
❌ Request rate limiting (future)

---

## 3. Requirements

### Functional Requirements

**FR-1**: NATS subject pattern must be:
- `rosey.db.kv.set` - Set/upsert
- `rosey.db.kv.get` - Get
- `rosey.db.kv.delete` - Delete
- `rosey.db.kv.list` - List keys

**FR-2**: Request format must include:
- `plugin_name` (required for all operations)
- Operation-specific fields (key, value, ttl_seconds, prefix, limit)

**FR-3**: Response format must include:
- `success` (bool)
- `data` (operation result) on success
- `error` (dict with code and message) on failure

**FR-4**: Error codes must cover:
- `INVALID_JSON` - Malformed request
- `MISSING_FIELD` - Required field missing
- `VALUE_TOO_LARGE` - Value exceeds 64KB
- `INTERNAL_ERROR` - Database error

**FR-5**: All handlers must:
- Validate request format
- Call corresponding BotDatabase method
- Format response consistently
- Log errors appropriately

### Non-Functional Requirements

**NFR-1 Performance**: 
- Handler latency <5ms (excluding DB time)
- End-to-end <15ms for simple operations

**NFR-2 Reliability**:
- All errors caught and returned as error responses
- No uncaught exceptions crash DatabaseService

**NFR-3 Testing**: Integration tests with real NATS connection

---

## 4. Technical Design

### 4.1 NATS Subject Pattern

```
rosey.db.kv.set      # Set/upsert key-value
rosey.db.kv.get      # Get key-value
rosey.db.kv.delete   # Delete key-value
rosey.db.kv.list     # List keys with prefix
```

### 4.2 Request/Response Schemas

#### kv.set Request
```json
{
  "plugin_name": "my-plugin",
  "key": "config",
  "value": {"theme": "dark"},
  "ttl_seconds": 3600  // Optional
}
```

#### kv.set Response (Success)
```json
{
  "success": true,
  "data": {}
}
```

#### kv.get Request
```json
{
  "plugin_name": "my-plugin",
  "key": "config"
}
```

#### kv.get Response (Success)
```json
{
  "success": true,
  "data": {
    "exists": true,
    "value": {"theme": "dark"}
  }
}
```

#### kv.delete Request
```json
{
  "plugin_name": "my-plugin",
  "key": "config"
}
```

#### kv.delete Response (Success)
```json
{
  "success": true,
  "data": {
    "deleted": true
  }
}
```

#### kv.list Request
```json
{
  "plugin_name": "my-plugin",
  "prefix": "user:",     // Optional
  "limit": 100           // Optional, default 1000
}
```

#### kv.list Response (Success)
```json
{
  "success": true,
  "data": {
    "keys": ["user:alice", "user:bob"],
    "count": 2,
    "truncated": false
  }
}
```

#### Error Response (All Operations)
```json
{
  "success": false,
  "error": {
    "code": "MISSING_FIELD",
    "message": "Required field 'key' is missing"
  }
}
```

### 4.3 Handler Implementations

**File**: `common/database_service.py`

#### 4.3.1 _handle_kv_set

```python
async def _handle_kv_set(self, msg):
    """
    Handle rosey.db.kv.set requests.
    
    Request:
        {
            "plugin_name": str,
            "key": str,
            "value": Any,
            "ttl_seconds": Optional[int]
        }
    
    Response:
        {"success": true, "data": {}}
        or
        {"success": false, "error": {"code": str, "message": str}}
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
        
        # Validate required fields
        plugin_name = request.get("plugin_name")
        key = request.get("key")
        value = request.get("value")
        
        if not plugin_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'plugin_name' is missing"
                }
            }).encode())
            return
        
        if not key:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'key' is missing"
                }
            }).encode())
            return
        
        if "value" not in request:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'value' is missing"
                }
            }).encode())
            return
        
        ttl_seconds = request.get("ttl_seconds")
        
        # Call database method
        try:
            await self.db.kv_set(plugin_name, key, value, ttl_seconds)
        except ValueError as e:
            # Value too large or other validation error
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "VALUE_TOO_LARGE" if "64KB" in str(e) else "VALIDATION_ERROR",
                    "message": str(e)
                }
            }).encode())
            return
        except Exception as e:
            self.logger.error(f"Error in kv_set: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Database operation failed"
                }
            }).encode())
            return
        
        # Success response
        await msg.respond(json.dumps({
            "success": True,
            "data": {}
        }).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in _handle_kv_set: {e}", exc_info=True)
        try:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Unexpected error occurred"
                }
            }).encode())
        except:
            pass  # Can't respond, connection may be dead
```

#### 4.3.2 _handle_kv_get

```python
async def _handle_kv_get(self, msg):
    """
    Handle rosey.db.kv.get requests.
    
    Request:
        {"plugin_name": str, "key": str}
    
    Response:
        {"success": true, "data": {"exists": bool, "value": Any}}
        or
        {"success": false, "error": {"code": str, "message": str}}
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
        
        # Validate required fields
        plugin_name = request.get("plugin_name")
        key = request.get("key")
        
        if not plugin_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'plugin_name' is missing"
                }
            }).encode())
            return
        
        if not key:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'key' is missing"
                }
            }).encode())
            return
        
        # Call database method
        try:
            result = await self.db.kv_get(plugin_name, key)
        except Exception as e:
            self.logger.error(f"Error in kv_get: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Database operation failed"
                }
            }).encode())
            return
        
        # Success response
        await msg.respond(json.dumps({
            "success": True,
            "data": result
        }).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in _handle_kv_get: {e}", exc_info=True)
        try:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Unexpected error occurred"
                }
            }).encode())
        except:
            pass
```

#### 4.3.3 _handle_kv_delete

```python
async def _handle_kv_delete(self, msg):
    """
    Handle rosey.db.kv.delete requests.
    
    Request:
        {"plugin_name": str, "key": str}
    
    Response:
        {"success": true, "data": {"deleted": bool}}
        or
        {"success": false, "error": {"code": str, "message": str}}
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
        
        # Validate required fields
        plugin_name = request.get("plugin_name")
        key = request.get("key")
        
        if not plugin_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'plugin_name' is missing"
                }
            }).encode())
            return
        
        if not key:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'key' is missing"
                }
            }).encode())
            return
        
        # Call database method
        try:
            deleted = await self.db.kv_delete(plugin_name, key)
        except Exception as e:
            self.logger.error(f"Error in kv_delete: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Database operation failed"
                }
            }).encode())
            return
        
        # Success response
        await msg.respond(json.dumps({
            "success": True,
            "data": {"deleted": deleted}
        }).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in _handle_kv_delete: {e}", exc_info=True)
        try:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Unexpected error occurred"
                }
            }).encode())
        except:
            pass
```

#### 4.3.4 _handle_kv_list

```python
async def _handle_kv_list(self, msg):
    """
    Handle rosey.db.kv.list requests.
    
    Request:
        {
            "plugin_name": str,
            "prefix": Optional[str],
            "limit": Optional[int]
        }
    
    Response:
        {"success": true, "data": {"keys": [str], "count": int, "truncated": bool}}
        or
        {"success": false, "error": {"code": str, "message": str}}
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
        
        # Validate required fields
        plugin_name = request.get("plugin_name")
        
        if not plugin_name:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "MISSING_FIELD",
                    "message": "Required field 'plugin_name' is missing"
                }
            }).encode())
            return
        
        prefix = request.get("prefix", "")
        limit = request.get("limit", 1000)
        
        # Call database method
        try:
            result = await self.db.kv_list(plugin_name, prefix, limit)
        except Exception as e:
            self.logger.error(f"Error in kv_list: {e}", exc_info=True)
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Database operation failed"
                }
            }).encode())
            return
        
        # Success response
        await msg.respond(json.dumps({
            "success": True,
            "data": result
        }).encode())
        
    except Exception as e:
        self.logger.error(f"Unexpected error in _handle_kv_list: {e}", exc_info=True)
        try:
            await msg.respond(json.dumps({
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Unexpected error occurred"
                }
            }).encode())
        except:
            pass
```

### 4.4 Subject Registration

Update `start()` method:

```python
async def start(self):
    """Start DatabaseService and register NATS handlers."""
    self.logger.info("Starting DatabaseService...")
    
    # ... existing row operation subscriptions ...
    
    # KV storage handlers
    await self.nc.subscribe("rosey.db.kv.set", cb=self._handle_kv_set)
    await self.nc.subscribe("rosey.db.kv.get", cb=self._handle_kv_get)
    await self.nc.subscribe("rosey.db.kv.delete", cb=self._handle_kv_delete)
    await self.nc.subscribe("rosey.db.kv.list", cb=self._handle_kv_list)
    
    self.logger.info("DatabaseService started and subscribed to KV subjects")
```

---

## 5. Implementation Steps

### Step 1: Add Handler Methods

1. Open `common/database_service.py`
2. Add four handler methods: `_handle_kv_set`, `_handle_kv_get`, `_handle_kv_delete`, `_handle_kv_list`
3. Implement JSON parsing and validation
4. Add error handling with proper error codes
5. Call corresponding BotDatabase methods

### Step 2: Register Subjects

1. Update `start()` method
2. Add four `subscribe()` calls for KV subjects
3. Verify no subject name conflicts

### Step 3: Create Integration Tests

**File**: `tests/integration/test_database_service_kv.py`

Test categories:
- **Happy Path**: Successful operations
- **Validation**: Missing fields, invalid JSON
- **Error Handling**: Database errors, size limits
- **End-to-End**: Full request/response cycle

### Step 4: Manual Testing

Test with `nats` CLI:
```bash
# Set
nats req rosey.db.kv.set '{"plugin_name":"test","key":"config","value":{"theme":"dark"}}'

# Get
nats req rosey.db.kv.get '{"plugin_name":"test","key":"config"}'

# List
nats req rosey.db.kv.list '{"plugin_name":"test"}'

# Delete
nats req rosey.db.kv.delete '{"plugin_name":"test","key":"config"}'
```

---

## 6. Testing Strategy

### 6.1 Integration Tests

**File**: `tests/integration/test_database_service_kv.py`

```python
import pytest
import json
from nats.aio.client import Client as NATS
from common.database_service import DatabaseService
from common.database import BotDatabase

class TestDatabaseServiceKV:
    """Integration tests for DatabaseService KV handlers."""
    
    @pytest.fixture
    async def nats_client(self):
        """Create NATS client for tests."""
        nc = NATS()
        await nc.connect("nats://localhost:4222")
        yield nc
        await nc.close()
    
    @pytest.fixture
    async def db_service(self):
        """Create DatabaseService instance."""
        db = BotDatabase("sqlite:///:memory:")
        await db.create_tables()
        
        service = DatabaseService(db, "nats://localhost:4222")
        await service.start()
        
        yield service
        
        await service.stop()
        await db.close()
    
    async def test_kv_set_and_get(self, nats_client, db_service):
        """Test set and get operations via NATS."""
        # Set a value
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "config",
                "value": {"theme": "dark"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        
        # Get it back
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({
                "plugin_name": "test",
                "key": "config"
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        assert result['data']['exists'] == True
        assert result['data']['value'] == {"theme": "dark"}
    
    async def test_kv_set_with_ttl(self, nats_client, db_service):
        """Test TTL support."""
        # Set with 2 second TTL
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "temp",
                "value": "data",
                "ttl_seconds": 2
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        
        # Should exist immediately
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result['data']['exists'] == True
        
        # Wait for expiration
        await asyncio.sleep(3)
        
        # Should not exist after TTL
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        result = json.loads(response.data.decode())
        assert result['data']['exists'] == False
    
    async def test_kv_delete(self, nats_client, db_service):
        """Test delete operation."""
        # Set a value
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "temp",
                "value": "data"
            }).encode()
        )
        
        # Delete it
        response = await nats_client.request(
            "rosey.db.kv.delete",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        assert result['data']['deleted'] == True
        
        # Verify it's gone
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test", "key": "temp"}).encode()
        )
        result = json.loads(response.data.decode())
        assert result['data']['exists'] == False
    
    async def test_kv_list(self, nats_client, db_service):
        """Test list operation."""
        # Set multiple keys
        for i in range(3):
            await nats_client.request(
                "rosey.db.kv.set",
                json.dumps({
                    "plugin_name": "test",
                    "key": f"key{i}",
                    "value": i
                }).encode()
            )
        
        # List all
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "test"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        assert result['data']['count'] == 3
        assert "key0" in result['data']['keys']
        assert "key1" in result['data']['keys']
        assert "key2" in result['data']['keys']
    
    async def test_kv_list_with_prefix(self, nats_client, db_service):
        """Test prefix filtering."""
        # Set keys with different prefixes
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "user:alice", "value": 1}).encode()
        )
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "user:bob", "value": 2}).encode()
        )
        await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({"plugin_name": "test", "key": "config:theme", "value": 3}).encode()
        )
        
        # List with prefix
        response = await nats_client.request(
            "rosey.db.kv.list",
            json.dumps({"plugin_name": "test", "prefix": "user:"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == True
        assert result['data']['count'] == 2
        assert "user:alice" in result['data']['keys']
        assert "user:bob" in result['data']['keys']
        assert "config:theme" not in result['data']['keys']
    
    async def test_invalid_json(self, nats_client, db_service):
        """Test handling of invalid JSON."""
        response = await nats_client.request(
            "rosey.db.kv.set",
            b"not valid json",
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == False
        assert result['error']['code'] == "INVALID_JSON"
    
    async def test_missing_plugin_name(self, nats_client, db_service):
        """Test missing plugin_name field."""
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"key": "config"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == False
        assert result['error']['code'] == "MISSING_FIELD"
        assert "plugin_name" in result['error']['message']
    
    async def test_missing_key(self, nats_client, db_service):
        """Test missing key field."""
        response = await nats_client.request(
            "rosey.db.kv.get",
            json.dumps({"plugin_name": "test"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == False
        assert result['error']['code'] == "MISSING_FIELD"
        assert "key" in result['error']['message']
    
    async def test_value_too_large(self, nats_client, db_service):
        """Test value size limit."""
        large_value = "x" * 70000
        
        response = await nats_client.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "large",
                "value": large_value
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] == False
        assert result['error']['code'] == "VALUE_TOO_LARGE"
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: Four NATS handlers implemented
  - Given DatabaseService
  - When checking handler methods
  - Then _handle_kv_set, _handle_kv_get, _handle_kv_delete, _handle_kv_list exist

- [x] **AC-2**: Subjects registered in start()
  - Given DatabaseService started
  - When publishing to rosey.db.kv.* subjects
  - Then handlers receive messages

- [x] **AC-3**: Request validation works
  - Given missing required field
  - When sending request
  - Then error response with MISSING_FIELD code

- [x] **AC-4**: JSON parsing errors handled
  - Given invalid JSON request
  - When sending to handler
  - Then error response with INVALID_JSON code

- [x] **AC-5**: Value size limit enforced
  - Given value >64KB
  - When sending kv.set request
  - Then error response with VALUE_TOO_LARGE code

- [x] **AC-6**: Database errors handled gracefully
  - Given database connection error
  - When handler calls DB method
  - Then error response with INTERNAL_ERROR code

- [x] **AC-7**: Success responses formatted correctly
  - Given successful operation
  - When receiving response
  - Then success=true and data field present

- [x] **AC-8**: Integration tests pass (20+ tests)
  - Given test suite
  - When running integration tests
  - Then all tests pass

- [x] **AC-9**: End-to-end latency <15ms
  - Given performance test
  - When measuring request/response time
  - Then p95 latency <15ms

---

## 8. Rollout Plan

### Pre-deployment

1. Verify all handler implementations
2. Run integration tests with real NATS
3. Test with `nats` CLI manually
4. Verify no subject conflicts

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-12-sortie-3-nats-handlers`
2. Implement four handler methods
3. Update `start()` method with subscriptions
4. Write integration tests
5. Run tests and verify all pass
6. Manual testing with `nats` CLI
7. Commit changes with message:
   ```
   Sprint 12 Sortie 3: DatabaseService NATS Handlers
   
   - Add _handle_kv_set, _handle_kv_get, _handle_kv_delete, _handle_kv_list
   - Register rosey.db.kv.* subjects in start()
   - Implement request validation and error handling
   - Add integration tests (20+ tests)
   
   Implements: SPEC-Sortie-3-DatabaseService-NATS-Handlers.md
   Related: PRD-KV-Storage-Foundation.md
   Depends-On: SPEC-Sortie-2-BotDatabase-KV-Methods.md
   ```
8. Push branch and create PR
9. Code review
10. Merge to main

### Post-deployment

- Monitor NATS subject subscriptions
- Check logs for handler errors
- Verify integration tests pass in CI/CD

### Rollback Procedure

If issues arise:
```bash
git revert <commit-hash>
# Database and model layers remain functional
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: PluginKVStorage model
- **Sortie 2**: BotDatabase KV methods
- **NATS server**: Running and accessible
- **nats.py**: Python NATS client library

### External Dependencies

- NATS server (must be running for integration tests)

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| NATS connection failures | Low | High | Connection retry logic, health checks |
| Message parsing overhead | Low | Low | JSON parsing is fast (<1ms) |
| Handler crashes affect all plugins | Medium | Medium | Comprehensive error handling, no uncaught exceptions |
| Subject name conflicts | Low | Low | Follow rosey.db.kv.* naming convention |

---

## 10. Documentation

### Code Documentation

- All handlers have comprehensive docstrings
- Request/response schemas documented
- Error codes documented

### Developer Documentation

Update `docs/NATS_SUBJECTS.md` with:
- KV subject patterns
- Request/response examples
- Error codes reference

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-KV-Schema-Model.md](SPEC-Sortie-1-KV-Schema-Model.md)
- [SPEC-Sortie-2-BotDatabase-KV-Methods.md](SPEC-Sortie-2-BotDatabase-KV-Methods.md)

**Next**: [SPEC-Sortie-4-TTL-Cleanup-Polish.md](SPEC-Sortie-4-TTL-Cleanup-Polish.md)

**Parent PRD**: [PRD-KV-Storage-Foundation.md](PRD-KV-Storage-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
