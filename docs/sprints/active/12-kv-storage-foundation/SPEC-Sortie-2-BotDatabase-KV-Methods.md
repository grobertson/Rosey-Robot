# SPEC: Sortie 2 - BotDatabase KV Methods

**Sprint**: 12 (KV Storage Foundation)  
**Sortie**: 2 of 4  
**Estimated Effort**: ~6 hours  
**Branch**: `feature/sprint-12-sortie-2-botdatabase-kv`  
**Dependencies**: Sortie 1 (PluginKVStorage model must exist)

---

## 1. Overview

Implement async database methods in `BotDatabase` class for key-value operations. These methods provide the data access layer that DatabaseService will call via NATS handlers.

**What This Sortie Achieves**:

- Five async KV methods in BotDatabase
- JSON serialization/deserialization handling
- TTL expiration enforcement on reads
- Plugin namespace isolation
- Comprehensive unit tests (30+ test cases)

---

## 2. Scope and Non-Goals

### In Scope

✅ `kv_set()` - Upsert with TTL support  
✅ `kv_get()` - Get with expiration checking  
✅ `kv_delete()` - Delete by key  
✅ `kv_list()` - List keys with prefix filter  
✅ `kv_cleanup_expired()` - Bulk expiration cleanup  
✅ Unit tests for all methods (30+ tests)  
✅ Edge case handling (large values, invalid JSON, concurrent access)  
✅ Performance tests (1000-key operations)

### Out of Scope

❌ NATS handlers (Sortie 3)  
❌ Background cleanup task (Sortie 4)  
❌ DatabaseClient wrapper (future enhancement)  
❌ Integration tests with NATS (Sortie 3)

---

## 3. Requirements

### Functional Requirements

**FR-1**: `kv_set()` must:
- Accept plugin_name, key, value, optional ttl_seconds
- Serialize value to JSON
- Calculate expires_at from ttl_seconds
- Upsert (insert or update existing)
- Validate value size ≤64KB

**FR-2**: `kv_get()` must:
- Accept plugin_name, key
- Return {'exists': False} if not found
- Return {'exists': False} if expired
- Return {'exists': True, 'value': deserialized} if valid
- Deserialize JSON value

**FR-3**: `kv_delete()` must:
- Accept plugin_name, key
- Return True if deleted
- Return False if didn't exist

**FR-4**: `kv_list()` must:
- Accept plugin_name, optional prefix, optional limit (default 1000)
- Filter out expired entries
- Support prefix matching
- Return {'keys': [...], 'count': int, 'truncated': bool}
- Sort keys alphabetically

**FR-5**: `kv_cleanup_expired()` must:
- Delete all expired entries across all plugins
- Return count of deleted rows
- Complete in <1 second for 10,000 keys

### Non-Functional Requirements

**NFR-1 Performance**:
- kv_get: <5ms average latency
- kv_set: <10ms average latency
- kv_list: <50ms for 1000 keys
- kv_cleanup_expired: <1s for 10,000 keys

**NFR-2 Reliability**:
- All methods use transactions
- Proper error handling and logging
- Graceful handling of JSON decode errors

**NFR-3 Testing**: ≥90% code coverage for KV methods

---

## 4. Technical Design

### 4.1 Method Signatures

**File**: `common/database.py`

```python
from typing import Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, delete, or_, func
from sqlalchemy.dialects.postgresql import insert
from common.models import PluginKVStorage
import json

class BotDatabase:
    """Database access layer."""
    
    # ... existing methods ...
    
    async def kv_set(
        self,
        plugin_name: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Set a key-value pair for a plugin with optional TTL.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
            value: Any JSON-serializable value
            ttl_seconds: Optional TTL in seconds (None = no expiration)
            
        Raises:
            ValueError: If value exceeds 64KB when serialized
            TypeError: If value is not JSON-serializable
        """
        
    async def kv_get(
        self,
        plugin_name: str,
        key: str
    ) -> dict:
        """
        Get a key-value pair for a plugin.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
        
        Returns:
            {'exists': bool, 'value': Any}
            If key doesn't exist or is expired: {'exists': False}
        """
        
    async def kv_delete(
        self,
        plugin_name: str,
        key: str
    ) -> bool:
        """
        Delete a key-value pair for a plugin.
        
        Args:
            plugin_name: Plugin identifier
            key: Key name
        
        Returns:
            True if key was deleted, False if didn't exist
        """
        
    async def kv_list(
        self,
        plugin_name: str,
        prefix: str = '',
        limit: int = 1000
    ) -> dict:
        """
        List keys for a plugin with optional prefix filter.
        
        Args:
            plugin_name: Plugin identifier
            prefix: Optional key prefix filter
            limit: Maximum keys to return (default 1000)
        
        Returns:
            {
                'keys': [str],
                'count': int,
                'truncated': bool  # True if more results available
            }
        """
        
    async def kv_cleanup_expired(self) -> int:
        """
        Remove all expired keys across all plugins.
        
        Returns:
            Number of keys deleted
        """
```

### 4.2 Implementation Details

#### 4.2.1 kv_set() - Upsert with TTL

```python
async def kv_set(
    self,
    plugin_name: str,
    key: str,
    value: Any,
    ttl_seconds: Optional[int] = None
) -> None:
    """Set a key-value pair for a plugin with optional TTL."""
    # Serialize value to JSON
    try:
        value_json = json.dumps(value)
    except (TypeError, ValueError) as e:
        raise TypeError(f"Value is not JSON-serializable: {e}")
    
    # Check size limit (64KB)
    size_bytes = len(value_json.encode('utf-8'))
    if size_bytes > 65536:
        raise ValueError(
            f"Value size ({size_bytes} bytes) exceeds 64KB limit (65536 bytes)"
        )
    
    # Calculate expiration
    expires_at = None
    if ttl_seconds is not None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    # Upsert using PostgreSQL-style insert...on conflict
    async with self.session_factory() as session:
        stmt = insert(PluginKVStorage).values(
            plugin_name=plugin_name,
            key=key,
            value_json=value_json,
            expires_at=expires_at
        ).on_conflict_do_update(
            index_elements=['plugin_name', 'key'],
            set_={
                'value_json': value_json,
                'expires_at': expires_at,
                'updated_at': func.now()
            }
        )
        await session.execute(stmt)
        await session.commit()
```

#### 4.2.2 kv_get() - Fetch with Expiration Check

```python
async def kv_get(
    self,
    plugin_name: str,
    key: str
) -> dict:
    """Get a key-value pair for a plugin."""
    async with self.session_factory() as session:
        stmt = select(PluginKVStorage).where(
            PluginKVStorage.plugin_name == plugin_name,
            PluginKVStorage.key == key
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        
        if row is None:
            return {'exists': False}
        
        # Check expiration
        if row.is_expired:
            return {'exists': False}
        
        # Deserialize value
        try:
            value = json.loads(row.value_json)
        except json.JSONDecodeError:
            # Log error but don't crash
            # This shouldn't happen if kv_set validation works
            return {'exists': False}
        
        return {
            'exists': True,
            'value': value
        }
```

#### 4.2.3 kv_delete() - Simple Deletion

```python
async def kv_delete(
    self,
    plugin_name: str,
    key: str
) -> bool:
    """Delete a key-value pair for a plugin."""
    async with self.session_factory() as session:
        stmt = delete(PluginKVStorage).where(
            PluginKVStorage.plugin_name == plugin_name,
            PluginKVStorage.key == key
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
```

#### 4.2.4 kv_list() - List with Prefix Filter

```python
async def kv_list(
    self,
    plugin_name: str,
    prefix: str = '',
    limit: int = 1000
) -> dict:
    """List keys for a plugin with optional prefix filter."""
    async with self.session_factory() as session:
        # Build query
        stmt = select(PluginKVStorage.key).where(
            PluginKVStorage.plugin_name == plugin_name,
            # Only non-expired entries
            or_(
                PluginKVStorage.expires_at.is_(None),
                PluginKVStorage.expires_at > func.now()
            )
        )
        
        # Apply prefix filter if provided
        if prefix:
            stmt = stmt.where(PluginKVStorage.key.like(f'{prefix}%'))
        
        # Order by key and fetch limit+1 to detect truncation
        stmt = stmt.order_by(PluginKVStorage.key).limit(limit + 1)
        
        result = await session.execute(stmt)
        keys = [row[0] for row in result.fetchall()]
        
        # Check if results were truncated
        truncated = len(keys) > limit
        if truncated:
            keys = keys[:limit]
        
        return {
            'keys': keys,
            'count': len(keys),
            'truncated': truncated
        }
```

#### 4.2.5 kv_cleanup_expired() - Bulk Deletion

```python
async def kv_cleanup_expired(self) -> int:
    """Remove all expired keys across all plugins."""
    async with self.session_factory() as session:
        stmt = delete(PluginKVStorage).where(
            PluginKVStorage.expires_at.is_not(None),
            PluginKVStorage.expires_at < func.now()
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount
```

---

## 5. Implementation Steps

### Step 1: Add Methods to BotDatabase

1. Open `common/database.py`
2. Add all 5 KV methods to `BotDatabase` class
3. Add necessary imports (json, datetime, timedelta)
4. Add docstrings with Args, Returns, Raises
5. Implement error handling and logging

### Step 2: Handle SQLite Compatibility

For SQLite (which doesn't support PostgreSQL's `INSERT...ON CONFLICT`):

```python
# Use SQLite-compatible upsert
from sqlalchemy.dialects import sqlite

if self.engine.dialect.name == 'sqlite':
    # SQLite: Use INSERT OR REPLACE
    stmt = insert(PluginKVStorage).values(...)
    stmt = stmt.on_conflict_do_update(
        index_elements=['plugin_name', 'key'],
        set_={...}
    )
else:
    # PostgreSQL: Use standard syntax
    stmt = insert(PluginKVStorage).values(...).on_conflict_do_update(...)
```

### Step 3: Create Comprehensive Unit Tests

**File**: `tests/unit/test_database_kv.py`

Test categories:
- **Basic CRUD**: Set, get, delete operations
- **TTL**: Expiration behavior, cleanup
- **Serialization**: All JSON types (dict, list, str, int, bool, None)
- **Edge Cases**: Large values, invalid JSON, concurrent access
- **Prefix Matching**: List with various prefixes
- **Plugin Isolation**: Ensure plugins can't access each other's data
- **Performance**: 1000-key operations

### Step 4: Performance Testing

Create benchmarks for:
- Single key operations (get, set, delete)
- Bulk operations (list 1000 keys)
- Cleanup performance (10,000 expired keys)

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/unit/test_database_kv.py`

```python
import pytest
from datetime import datetime, timedelta
from common.database import BotDatabase
from common.models import PluginKVStorage

class TestBotDatabaseKV:
    """Test BotDatabase KV methods."""
    
    @pytest.fixture
    async def db(self):
        """Create test database instance."""
        # Use in-memory SQLite for tests
        db = BotDatabase("sqlite:///:memory:")
        await db.create_tables()
        yield db
        await db.close()
    
    async def test_kv_set_and_get_basic(self, db):
        """Test basic set and get operations."""
        # Set a value
        await db.kv_set("test-plugin", "config", {"theme": "dark"})
        
        # Get it back
        result = await db.kv_get("test-plugin", "config")
        assert result['exists'] == True
        assert result['value'] == {"theme": "dark"}
    
    async def test_kv_set_all_json_types(self, db):
        """Test serialization of all JSON types."""
        test_cases = [
            ("dict", {"key": "value"}),
            ("list", [1, 2, 3]),
            ("string", "hello world"),
            ("int", 42),
            ("float", 3.14),
            ("bool_true", True),
            ("bool_false", False),
            ("null", None),
            ("nested", {"users": [{"name": "Alice", "score": 95}]}),
        ]
        
        for key, value in test_cases:
            await db.kv_set("test", key, value)
            result = await db.kv_get("test", key)
            assert result['exists'] == True
            assert result['value'] == value
    
    async def test_kv_get_nonexistent_key(self, db):
        """Test getting a key that doesn't exist."""
        result = await db.kv_get("test", "nonexistent")
        assert result['exists'] == False
    
    async def test_kv_set_with_ttl(self, db):
        """Test TTL expiration."""
        # Set with 1 second TTL
        await db.kv_set("test", "expires", "data", ttl_seconds=1)
        
        # Should exist immediately
        result = await db.kv_get("test", "expires")
        assert result['exists'] == True
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Should not exist after TTL
        result = await db.kv_get("test", "expires")
        assert result['exists'] == False
    
    async def test_kv_set_upsert(self, db):
        """Test that set updates existing keys."""
        # Initial set
        await db.kv_set("test", "counter", 1)
        result = await db.kv_get("test", "counter")
        assert result['value'] == 1
        
        # Update
        await db.kv_set("test", "counter", 2)
        result = await db.kv_get("test", "counter")
        assert result['value'] == 2
    
    async def test_kv_set_value_size_limit(self, db):
        """Test value size limit enforcement."""
        # Just under limit - should work
        small_value = "x" * 65000
        await db.kv_set("test", "small", small_value)  # Should succeed
        
        # Over limit - should fail
        large_value = "x" * 70000
        with pytest.raises(ValueError, match="exceeds 64KB limit"):
            await db.kv_set("test", "large", large_value)
    
    async def test_kv_set_non_serializable(self, db):
        """Test handling of non-JSON-serializable values."""
        class NotSerializable:
            pass
        
        with pytest.raises(TypeError, match="not JSON-serializable"):
            await db.kv_set("test", "bad", NotSerializable())
    
    async def test_kv_delete(self, db):
        """Test delete operation."""
        # Set a key
        await db.kv_set("test", "temp", "data")
        
        # Delete it
        deleted = await db.kv_delete("test", "temp")
        assert deleted == True
        
        # Verify it's gone
        result = await db.kv_get("test", "temp")
        assert result['exists'] == False
        
        # Delete again - should return False
        deleted = await db.kv_delete("test", "temp")
        assert deleted == False
    
    async def test_kv_list_basic(self, db):
        """Test listing keys."""
        # Set multiple keys
        await db.kv_set("test", "key1", 1)
        await db.kv_set("test", "key2", 2)
        await db.kv_set("test", "key3", 3)
        
        # List all
        result = await db.kv_list("test")
        assert result['count'] == 3
        assert result['keys'] == ["key1", "key2", "key3"]
        assert result['truncated'] == False
    
    async def test_kv_list_with_prefix(self, db):
        """Test prefix filtering."""
        # Set keys with various prefixes
        await db.kv_set("test", "user:alice", {"name": "Alice"})
        await db.kv_set("test", "user:bob", {"name": "Bob"})
        await db.kv_set("test", "config:theme", "dark")
        
        # List with "user:" prefix
        result = await db.kv_list("test", prefix="user:")
        assert result['count'] == 2
        assert "user:alice" in result['keys']
        assert "user:bob" in result['keys']
        assert "config:theme" not in result['keys']
    
    async def test_kv_list_excludes_expired(self, db):
        """Test that list excludes expired keys."""
        # Set some keys with short TTL
        await db.kv_set("test", "expires1", 1, ttl_seconds=1)
        await db.kv_set("test", "expires2", 2, ttl_seconds=1)
        await db.kv_set("test", "permanent", 3)
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # List should only show permanent key
        result = await db.kv_list("test")
        assert result['count'] == 1
        assert result['keys'] == ["permanent"]
    
    async def test_kv_list_truncation(self, db):
        """Test limit and truncation detection."""
        # Set 15 keys
        for i in range(15):
            await db.kv_set("test", f"key{i:02d}", i)
        
        # List with limit=10
        result = await db.kv_list("test", limit=10)
        assert result['count'] == 10
        assert result['truncated'] == True
        
        # List with limit=20
        result = await db.kv_list("test", limit=20)
        assert result['count'] == 15
        assert result['truncated'] == False
    
    async def test_kv_list_sorted(self, db):
        """Test that keys are sorted alphabetically."""
        # Set keys in random order
        keys = ["zebra", "apple", "mango", "banana"]
        for key in keys:
            await db.kv_set("test", key, 1)
        
        # List should be sorted
        result = await db.kv_list("test")
        assert result['keys'] == ["apple", "banana", "mango", "zebra"]
    
    async def test_kv_cleanup_expired(self, db):
        """Test bulk cleanup of expired keys."""
        # Set multiple keys with short TTL
        for i in range(5):
            await db.kv_set("test", f"expires{i}", i, ttl_seconds=1)
        
        # Set some permanent keys
        for i in range(3):
            await db.kv_set("test", f"keep{i}", i)
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Cleanup
        deleted = await db.kv_cleanup_expired()
        assert deleted == 5
        
        # Verify only permanent keys remain
        result = await db.kv_list("test")
        assert result['count'] == 3
        assert all("keep" in key for key in result['keys'])
    
    async def test_plugin_isolation(self, db):
        """Test that plugins can't access each other's data."""
        # Set data for two plugins
        await db.kv_set("plugin-a", "secret", "data-a")
        await db.kv_set("plugin-b", "secret", "data-b")
        
        # Each plugin should only see their own data
        result_a = await db.kv_get("plugin-a", "secret")
        assert result_a['value'] == "data-a"
        
        result_b = await db.kv_get("plugin-b", "secret")
        assert result_b['value'] == "data-b"
        
        # List should be isolated
        await db.kv_set("plugin-a", "key1", 1)
        await db.kv_set("plugin-b", "key2", 2)
        
        list_a = await db.kv_list("plugin-a")
        assert "key1" in list_a['keys']
        assert "key2" not in list_a['keys']
    
    async def test_kv_performance_bulk_set(self, db):
        """Test performance of bulk set operations."""
        import time
        
        start = time.time()
        for i in range(100):
            await db.kv_set("test", f"key{i}", {"index": i})
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<1s for 100 keys)
        assert elapsed < 1.0
    
    async def test_kv_performance_bulk_get(self, db):
        """Test performance of bulk get operations."""
        import time
        
        # Set up data
        for i in range(100):
            await db.kv_set("test", f"key{i}", {"index": i})
        
        # Measure get performance
        start = time.time()
        for i in range(100):
            await db.kv_get("test", f"key{i}")
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<1s for 100 keys)
        assert elapsed < 1.0
    
    async def test_kv_performance_list_1000(self, db):
        """Test performance of listing 1000 keys."""
        import time
        
        # Set up 1000 keys
        for i in range(1000):
            await db.kv_set("test", f"key{i:04d}", i)
        
        # Measure list performance
        start = time.time()
        result = await db.kv_list("test", limit=1000)
        elapsed = time.time() - start
        
        assert result['count'] == 1000
        assert elapsed < 0.05  # <50ms
    
    async def test_kv_performance_cleanup_10k(self, db):
        """Test cleanup performance with 10k expired keys."""
        import time
        
        # Set up 10k expired keys
        past = datetime.utcnow() - timedelta(hours=1)
        async with db.session_factory() as session:
            for i in range(10000):
                entry = PluginKVStorage(
                    plugin_name="test",
                    key=f"key{i}",
                    value_json='"data"',
                    expires_at=past
                )
                session.add(entry)
            await session.commit()
        
        # Measure cleanup performance
        start = time.time()
        deleted = await db.kv_cleanup_expired()
        elapsed = time.time() - start
        
        assert deleted == 10000
        assert elapsed < 1.0  # <1 second
```

**Test Coverage Target**: ≥90% of KV methods

**Command**:
```bash
pytest tests/unit/test_database_kv.py -v --cov=common.database --cov-report=term-missing
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: All 5 KV methods implemented in `common/database.py`
  - Given the BotDatabase class
  - When inspecting methods
  - Then kv_set, kv_get, kv_delete, kv_list, kv_cleanup_expired exist

- [x] **AC-2**: JSON serialization works for all types
  - Given various Python types (dict, list, str, int, bool, None)
  - When calling kv_set then kv_get
  - Then values round-trip correctly

- [x] **AC-3**: TTL expiration enforced on reads
  - Given a key with TTL=1 second
  - When reading after 2 seconds
  - Then kv_get returns {'exists': False}

- [x] **AC-4**: Upsert behavior works correctly
  - Given an existing key
  - When calling kv_set with new value
  - Then value is updated, not duplicated

- [x] **AC-5**: Value size limit enforced
  - Given a value >64KB
  - When calling kv_set
  - Then ValueError is raised

- [x] **AC-6**: Plugin isolation enforced
  - Given keys for plugin-a and plugin-b
  - When plugin-a lists keys
  - Then only plugin-a keys are returned

- [x] **AC-7**: Prefix filtering works
  - Given keys "user:alice", "user:bob", "config:theme"
  - When calling kv_list with prefix="user:"
  - Then only user:* keys returned

- [x] **AC-8**: List truncation detected
  - Given 15 keys and limit=10
  - When calling kv_list
  - Then truncated=True and count=10

- [x] **AC-9**: Cleanup removes expired keys
  - Given 5 expired and 3 permanent keys
  - When calling kv_cleanup_expired
  - Then 5 deleted, 3 remain

- [x] **AC-10**: Unit tests pass with ≥90% coverage
  - Given the test suite
  - When running pytest with coverage
  - Then all 30+ tests pass and coverage ≥90%

- [x] **AC-11**: Performance targets met
  - Given performance tests
  - When measuring latencies
  - Then kv_get <5ms, kv_set <10ms, kv_list <50ms, cleanup <1s

---

## 8. Rollout Plan

### Pre-deployment

1. Review all method implementations
2. Run full test suite
3. Verify performance benchmarks
4. Test on both SQLite and PostgreSQL

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-12-sortie-2-botdatabase-kv`
2. Implement 5 KV methods in `common/database.py`
3. Add error handling and logging
4. Write comprehensive unit tests
5. Run tests and verify coverage ≥90%
6. Run performance benchmarks
7. Commit changes with message:
   ```
   Sprint 12 Sortie 2: BotDatabase KV Methods
   
   - Add kv_set, kv_get, kv_delete, kv_list, kv_cleanup_expired
   - Implement JSON serialization and TTL handling
   - Add plugin namespace isolation
   - Add comprehensive unit tests (30+ tests, 90%+ coverage)
   - Add performance benchmarks
   
   Implements: SPEC-Sortie-2-BotDatabase-KV-Methods.md
   Related: PRD-KV-Storage-Foundation.md
   Depends-On: SPEC-Sortie-1-KV-Schema-Model.md
   ```
8. Push branch and create PR
9. Code review
10. Merge to main

### Post-deployment

- Monitor test coverage metrics
- Verify performance in staging environment
- Check logs for any serialization errors

### Rollback Procedure

If issues arise:
```bash
git revert <commit-hash>
# Database schema remains (no migration changes)
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: PluginKVStorage model must exist
- **SQLAlchemy 2.0+**: For async database operations
- **PostgreSQL** or **SQLite**: Database backend

### External Dependencies

None

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Performance degrades with 10k+ keys | Low | Medium | Index on expires_at ensures fast cleanup |
| SQLite upsert syntax differs | Medium | Low | Test on both databases, use dialect detection |
| JSON serialization edge cases | Low | Medium | Comprehensive tests for all JSON types |
| Concurrent access issues | Low | Low | SQLAlchemy transactions handle concurrency |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Args, Returns, Raises documented
- Example usage in docstrings

### Developer Documentation

Update `docs/DATABASE.md` with:
- KV method usage examples
- Performance characteristics
- Plugin isolation guarantees

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-1-KV-Schema-Model.md](SPEC-Sortie-1-KV-Schema-Model.md)  
**Next**: 
- [SPEC-Sortie-3-DatabaseService-NATS-Handlers.md](SPEC-Sortie-3-DatabaseService-NATS-Handlers.md)
- [SPEC-Sortie-4-TTL-Cleanup-Polish.md](SPEC-Sortie-4-TTL-Cleanup-Polish.md)

**Parent PRD**: [PRD-KV-Storage-Foundation.md](PRD-KV-Storage-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
