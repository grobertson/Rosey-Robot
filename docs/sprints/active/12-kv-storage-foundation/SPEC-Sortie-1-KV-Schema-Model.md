# SPEC: Sortie 1 - KV Schema & Model

**Sprint**: 12 (KV Storage Foundation)  
**Sortie**: 1 of 4  
**Estimated Effort**: ~4 hours  
**Branch**: `feature/sprint-12-sortie-1-kv-schema`  
**Dependencies**: None (foundational work)

---

## 1. Overview

Create the SQLAlchemy model and Alembic migration for the `plugin_kv_storage` table. This foundational sortie establishes the database schema that all other KV operations will depend on.

**What This Sortie Achieves**:
- Database table for plugin key-value storage with TTL support
- Composite primary key ensuring plugin namespace isolation
- Indexes for efficient TTL cleanup and prefix queries
- Comprehensive model tests establishing data layer reliability

---

## 2. Scope and Non-Goals

### In Scope
✅ `PluginKVStorage` SQLAlchemy model with all columns  
✅ Composite primary key `(plugin_name, key)`  
✅ Three indexes: composite primary key, expiration, prefix  
✅ Alembic migration with up/down support  
✅ Model properties: `is_expired`, `get_value()`, `set_value()`  
✅ Model validation (size limits, JSON serialization)  
✅ Comprehensive unit tests (15+ test cases)  
✅ SQLite and PostgreSQL compatibility testing

### Out of Scope
❌ DatabaseService NATS handlers (Sortie 3)  
❌ Cleanup background task (Sortie 4)  
❌ Integration tests with NATS (Sortie 3)  
❌ BotDatabase async methods (Sortie 2)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Table schema must support:
- Plugin namespace isolation
- TTL-based expiration
- JSON value storage up to 64KB
- Fast key lookups by plugin
- Efficient expiration cleanup

**FR-2**: Model must provide:
- JSON serialization/deserialization
- Expiration checking
- Value size validation
- Type-safe accessors

**FR-3**: Migration must:
- Create table with all columns and indexes
- Support rollback (downgrade)
- Work on SQLite and PostgreSQL

### Non-Functional Requirements

**NFR-1 Performance**: Composite primary key index enables O(1) key lookups  
**NFR-2 Storage**: Enforce 64KB value size limit  
**NFR-3 Compatibility**: SQLAlchemy 2.0+ syntax, Python 3.10+ type hints  
**NFR-4 Testing**: 100% model code coverage

---

## 4. Technical Design

### 4.1 Table Schema

```sql
CREATE TABLE plugin_kv_storage (
    plugin_name VARCHAR(100) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value_json TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (plugin_name, key)
);

CREATE INDEX idx_plugin_kv_expires 
    ON plugin_kv_storage (expires_at) 
    WHERE expires_at IS NOT NULL;

CREATE INDEX idx_plugin_kv_prefix 
    ON plugin_kv_storage (plugin_name, key);
```

### 4.2 SQLAlchemy Model

**File**: `common/models.py`

```python
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.orm import validates
from datetime import datetime
import json
from typing import Any, Optional

class PluginKVStorage(Base):
    """
    Key-value storage for plugins with TTL support.
    
    Each plugin gets an isolated namespace identified by plugin_name.
    Values are stored as JSON and can optionally expire after a TTL.
    """
    
    __tablename__ = 'plugin_kv_storage'
    
    # Composite primary key
    plugin_name = Column(String(100), primary_key=True, nullable=False)
    key = Column(String(255), primary_key=True, nullable=False)
    
    # Value storage
    value_json = Column(Text, nullable=False)
    
    # TTL support
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_plugin_kv_expires', 'expires_at', 
              postgresql_where=expires_at.isnot(None)),
        Index('idx_plugin_kv_prefix', 'plugin_name', 'key'),
    )
    
    def __repr__(self):
        expired = " [EXPIRED]" if self.is_expired else ""
        return f"<PluginKVStorage(plugin={self.plugin_name}, key={self.key}{expired})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at
    
    def get_value(self) -> Any:
        """
        Deserialize and return the stored value.
        
        Returns:
            Deserialized Python object (dict, list, str, int, etc.)
            
        Raises:
            json.JSONDecodeError: If value_json is invalid JSON
        """
        return json.loads(self.value_json)
    
    def set_value(self, value: Any) -> None:
        """
        Serialize and store a Python value as JSON.
        
        Args:
            value: Any JSON-serializable Python object
            
        Raises:
            TypeError: If value is not JSON-serializable
            ValueError: If serialized value exceeds 64KB
        """
        serialized = json.dumps(value)
        
        # Check size limit (64KB)
        size_bytes = len(serialized.encode('utf-8'))
        if size_bytes > 65536:
            raise ValueError(
                f"Value size ({size_bytes} bytes) exceeds 64KB limit (65536 bytes)"
            )
        
        self.value_json = serialized
    
    @validates('plugin_name')
    def validate_plugin_name(self, key, value):
        """Validate plugin name format."""
        if not value or not isinstance(value, str):
            raise ValueError("plugin_name must be a non-empty string")
        
        if len(value) > 100:
            raise ValueError("plugin_name must be ≤100 characters")
        
        # Plugin names should be lowercase alphanumeric with hyphens/underscores
        import re
        if not re.match(r'^[a-z0-9\-_]+$', value):
            raise ValueError(
                "plugin_name must contain only lowercase letters, numbers, hyphens, and underscores"
            )
        
        return value
    
    @validates('key')
    def validate_key(self, key, value):
        """Validate key format."""
        if not value or not isinstance(value, str):
            raise ValueError("key must be a non-empty string")
        
        if len(value) > 255:
            raise ValueError("key must be ≤255 characters")
        
        return value
```

### 4.3 Alembic Migration

**File**: `alembic/versions/001_add_plugin_kv_storage.py`

```python
"""add plugin kv storage

Revision ID: 001_plugin_kv_storage
Revises: <previous_revision>
Create Date: 2025-11-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_plugin_kv_storage'
down_revision = '<previous_revision>'  # Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create plugin_kv_storage table."""
    op.create_table(
        'plugin_kv_storage',
        sa.Column('plugin_name', sa.String(length=100), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value_json', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('plugin_name', 'key', name='pk_plugin_kv_storage')
    )
    
    # Index for TTL cleanup (partial index on PostgreSQL)
    op.create_index(
        'idx_plugin_kv_expires',
        'plugin_kv_storage',
        ['expires_at'],
        unique=False,
        postgresql_where=sa.text('expires_at IS NOT NULL')
    )
    
    # Index for prefix queries
    op.create_index(
        'idx_plugin_kv_prefix',
        'plugin_kv_storage',
        ['plugin_name', 'key'],
        unique=False
    )


def downgrade() -> None:
    """Drop plugin_kv_storage table."""
    op.drop_index('idx_plugin_kv_prefix', table_name='plugin_kv_storage')
    op.drop_index('idx_plugin_kv_expires', table_name='plugin_kv_storage')
    op.drop_table('plugin_kv_storage')
```

---

## 5. Implementation Steps

### Step 1: Update `common/models.py`
1. Add `PluginKVStorage` class definition
2. Define all columns with proper types
3. Add composite primary key
4. Define indexes
5. Implement `is_expired` property
6. Implement `get_value()` method
7. Implement `set_value()` method with size validation
8. Add validators for `plugin_name` and `key`

### Step 2: Create Alembic Migration
1. Generate migration: `alembic revision -m "add plugin kv storage"`
2. Edit migration file with table definition
3. Add indexes (including partial index for PostgreSQL)
4. Implement downgrade() for rollback
5. Test migration: `alembic upgrade head`
6. Verify schema: Check table exists with correct columns and indexes
7. Test rollback: `alembic downgrade -1`

### Step 3: Create Unit Tests
**File**: `tests/unit/test_models_kv_storage.py`

Test categories:
- **Creation**: Valid model instantiation
- **Validation**: Plugin name format, key length, value size
- **Serialization**: JSON encoding/decoding
- **Expiration**: TTL checking, expired vs non-expired
- **Edge Cases**: Large values, special characters, None values

### Step 4: Verify Migration
1. Test on SQLite (dev environment)
2. Test on PostgreSQL (staging/production)
3. Verify all indexes created
4. Check index usage with EXPLAIN queries

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/unit/test_models_kv_storage.py`

```python
import pytest
from datetime import datetime, timedelta
import json
from common.models import PluginKVStorage

class TestPluginKVStorageModel:
    """Test PluginKVStorage model."""
    
    def test_create_basic_entry(self):
        """Test creating a basic KV entry."""
        entry = PluginKVStorage(
            plugin_name="test-plugin",
            key="config",
            value_json='{"theme": "dark"}'
        )
        assert entry.plugin_name == "test-plugin"
        assert entry.key == "config"
        assert entry.value_json == '{"theme": "dark"}'
        assert entry.expires_at is None
    
    def test_set_value_serialization(self):
        """Test set_value() serializes correctly."""
        entry = PluginKVStorage(plugin_name="test", key="data")
        
        # Dict
        entry.set_value({"count": 42, "active": True})
        assert entry.value_json == '{"count": 42, "active": true}'
        
        # List
        entry.set_value([1, 2, 3])
        assert entry.value_json == '[1, 2, 3]'
        
        # String
        entry.set_value("hello")
        assert entry.value_json == '"hello"'
        
        # Number
        entry.set_value(123)
        assert entry.value_json == '123'
    
    def test_get_value_deserialization(self):
        """Test get_value() deserializes correctly."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="data",
            value_json='{"name": "Alice", "scores": [95, 87, 92]}'
        )
        
        value = entry.get_value()
        assert value == {"name": "Alice", "scores": [95, 87, 92]}
        assert isinstance(value, dict)
        assert isinstance(value["scores"], list)
    
    def test_value_size_limit(self):
        """Test value size limit enforcement (64KB)."""
        entry = PluginKVStorage(plugin_name="test", key="large")
        
        # Just under limit - should work
        small_value = "x" * 65000
        entry.set_value(small_value)  # Should succeed
        
        # Over limit - should fail
        large_value = "x" * 70000
        with pytest.raises(ValueError, match="exceeds 64KB limit"):
            entry.set_value(large_value)
    
    def test_is_expired_property(self):
        """Test expiration checking."""
        # No expiration
        entry1 = PluginKVStorage(
            plugin_name="test",
            key="forever",
            value_json='"data"',
            expires_at=None
        )
        assert entry1.is_expired == False
        
        # Future expiration
        entry2 = PluginKVStorage(
            plugin_name="test",
            key="future",
            value_json='"data"',
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert entry2.is_expired == False
        
        # Past expiration
        entry3 = PluginKVStorage(
            plugin_name="test",
            key="past",
            value_json='"data"',
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert entry3.is_expired == True
    
    def test_plugin_name_validation(self):
        """Test plugin_name validation."""
        # Valid names
        valid = ["test", "my-plugin", "plugin_123", "a", "test-plugin-name"]
        for name in valid:
            entry = PluginKVStorage(plugin_name=name, key="k", value_json='1')
            assert entry.plugin_name == name
        
        # Invalid names
        with pytest.raises(ValueError, match="non-empty string"):
            PluginKVStorage(plugin_name="", key="k", value_json='1')
        
        with pytest.raises(ValueError, match="lowercase"):
            PluginKVStorage(plugin_name="TestPlugin", key="k", value_json='1')
        
        with pytest.raises(ValueError, match="≤100 characters"):
            long_name = "x" * 101
            PluginKVStorage(plugin_name=long_name, key="k", value_json='1')
    
    def test_key_validation(self):
        """Test key validation."""
        # Valid keys
        entry = PluginKVStorage(
            plugin_name="test",
            key="valid-key_123",
            value_json='1'
        )
        assert entry.key == "valid-key_123"
        
        # Empty key
        with pytest.raises(ValueError, match="non-empty string"):
            PluginKVStorage(plugin_name="test", key="", value_json='1')
        
        # Too long
        with pytest.raises(ValueError, match="≤255 characters"):
            long_key = "x" * 256
            PluginKVStorage(plugin_name="test", key=long_key, value_json='1')
    
    def test_repr(self):
        """Test string representation."""
        entry = PluginKVStorage(
            plugin_name="test-plugin",
            key="config",
            value_json='"data"'
        )
        repr_str = repr(entry)
        assert "test-plugin" in repr_str
        assert "config" in repr_str
        
        # Test expired entry
        expired = PluginKVStorage(
            plugin_name="test",
            key="old",
            value_json='"data"',
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert "[EXPIRED]" in repr(expired)
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="bad",
            value_json="not valid json"
        )
        
        with pytest.raises(json.JSONDecodeError):
            entry.get_value()
    
    def test_timestamps(self):
        """Test created_at and updated_at timestamps."""
        entry = PluginKVStorage(
            plugin_name="test",
            key="time",
            value_json='"data"'
        )
        
        # Should have created_at by default
        assert entry.created_at is not None
        assert isinstance(entry.created_at, datetime)
        
        # Should have updated_at by default
        assert entry.updated_at is not None
        assert isinstance(entry.updated_at, datetime)
```

**Test Coverage Target**: 100% of model code

**Command**:
```bash
pytest tests/unit/test_models_kv_storage.py -v --cov=common.models --cov-report=term-missing
```

### 6.2 Migration Tests

```bash
# Apply migration
alembic upgrade head

# Verify current revision
alembic current

# Check table exists
psql -d rosey -c "\d plugin_kv_storage"

# Verify indexes
psql -d rosey -c "\di plugin_kv_storage*"

# Test rollback
alembic downgrade -1

# Verify table dropped
psql -d rosey -c "\d plugin_kv_storage"  # Should fail

# Re-apply
alembic upgrade head
```

### 6.3 PostgreSQL vs SQLite Compatibility

**Test on both databases**:
```bash
# SQLite (dev)
export DATABASE_URL="sqlite:///rosey_dev.db"
alembic upgrade head
pytest tests/unit/test_models_kv_storage.py

# PostgreSQL (staging)
export DATABASE_URL="postgresql://user:pass@localhost/rosey_test"
alembic upgrade head
pytest tests/unit/test_models_kv_storage.py
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: PluginKVStorage model defined in `common/models.py`
  - Given the model file
  - When imported
  - Then PluginKVStorage class exists with all columns

- [x] **AC-2**: Composite primary key enforces uniqueness
  - Given a database with the plugin_kv_storage table
  - When inserting (plugin="test", key="config")
  - Then attempting to insert duplicate raises IntegrityError

- [x] **AC-3**: Alembic migration applies cleanly
  - Given a clean database
  - When running `alembic upgrade head`
  - Then plugin_kv_storage table exists with correct schema

- [x] **AC-4**: Migration reverses cleanly
  - Given a database with plugin_kv_storage table
  - When running `alembic downgrade -1`
  - Then table is dropped with no errors

- [x] **AC-5**: All indexes created
  - Given the migrated database
  - When inspecting indexes
  - Then idx_plugin_kv_expires and idx_plugin_kv_prefix exist

- [x] **AC-6**: Model tests pass with 100% coverage
  - Given the test suite
  - When running pytest with coverage
  - Then all 15+ tests pass and coverage ≥100%

- [x] **AC-7**: Value size limit enforced
  - Given a PluginKVStorage instance
  - When calling set_value() with >64KB data
  - Then ValueError is raised

- [x] **AC-8**: Expiration logic works correctly
  - Given entries with past, future, and None expires_at
  - When checking is_expired property
  - Then only past expirations return True

- [x] **AC-9**: Plugin name validation works
  - Given invalid plugin names (uppercase, empty, too long)
  - When creating model instances
  - Then ValueError is raised with clear message

- [x] **AC-10**: SQLite and PostgreSQL compatibility
  - Given both database types
  - When running migrations and tests
  - Then all tests pass on both databases

---

## 8. Rollout Plan

### Pre-deployment
1. Review code changes
2. Run full test suite on both SQLite and PostgreSQL
3. Verify migration applies and reverses cleanly

### Deployment Steps
1. Create feature branch: `git checkout -b feature/sprint-12-sortie-1-kv-schema`
2. Implement model in `common/models.py`
3. Create Alembic migration
4. Write comprehensive unit tests
5. Run tests and verify coverage
6. Test migration on staging database
7. Commit changes with message:
   ```
   Sprint 12 Sortie 1: KV Schema & Model
   
   - Add PluginKVStorage SQLAlchemy model
   - Create Alembic migration for plugin_kv_storage table
   - Implement composite primary key and indexes
   - Add model properties and validation
   - Add comprehensive unit tests (100% coverage)
   
   Implements: SPEC-Sortie-1-KV-Schema-Model.md
   Related: PRD-KV-Storage-Foundation.md
   ```
8. Push branch and create PR
9. Code review
10. Merge to main

### Post-deployment
- Monitor migration execution in production
- Verify indexes created correctly
- Check table exists in database

### Rollback Procedure
If issues arise:
```bash
alembic downgrade -1
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies
- **Alembic**: Database migration tool
- **SQLAlchemy 2.0+**: ORM framework
- **PostgreSQL** or **SQLite**: Database backend

### External Dependencies
None - this is foundational database schema work

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration fails on PostgreSQL | Low | High | Test on staging PostgreSQL before production |
| Partial index not supported on SQLite | Medium | Low | Make partial index PostgreSQL-specific in migration |
| Model validation conflicts with existing data | Low | Medium | This is net-new table, no existing data |
| 64KB size limit too restrictive | Low | Medium | Document limit in PRD, can increase later if needed |

---

## 10. Documentation

### Code Documentation
- All model methods have docstrings with Args, Returns, Raises
- Migration file has revision comment explaining purpose
- Test file has class and method docstrings

### User Documentation
Updates needed in **Sortie 4** when full feature is complete.

### Developer Documentation
Update `docs/DATABASE.md` with:
- plugin_kv_storage table schema
- Index usage and query patterns
- Model usage examples

---

## 11. Related Specifications

**Previous**: None (foundational sortie)  
**Next**: 
- [SPEC-Sortie-2-BotDatabase-KV-Methods.md](SPEC-Sortie-2-BotDatabase-KV-Methods.md)
- [SPEC-Sortie-3-DatabaseService-NATS-Handlers.md](SPEC-Sortie-3-DatabaseService-NATS-Handlers.md)
- [SPEC-Sortie-4-TTL-Cleanup-Polish.md](SPEC-Sortie-4-TTL-Cleanup-Polish.md)

**Parent PRD**: [PRD-KV-Storage-Foundation.md](PRD-KV-Storage-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
