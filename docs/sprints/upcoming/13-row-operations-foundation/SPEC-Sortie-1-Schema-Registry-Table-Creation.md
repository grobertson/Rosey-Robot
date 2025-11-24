# SPEC: Sortie 1 - Schema Registry & Table Creation

**Sprint**: 13 (Row Operations Foundation)  
**Sortie**: 1 of 5  
**Estimated Effort**: ~4 hours  
**Branch**: `feature/sprint-13-sortie-1-schema-registry`  
**Dependencies**: Sprint 12 complete (database infrastructure exists)

---

## 1. Overview

Create the schema registry system that enables plugins to register table schemas and have tables created dynamically. This is the foundation for all row-based storage operations.

**What This Sortie Achieves**:

- Schema registry with in-memory cache
- PluginTableSchemas database model
- Schema validation (field types, names, constraints)
- Dynamic table creation from schemas
- SQLite and PostgreSQL compatibility

---

## 2. Scope and Non-Goals

### In Scope

✅ PluginTableSchemas SQLAlchemy model  
✅ SchemaRegistry class with CRUD operations  
✅ Schema validation logic  
✅ Dynamic table creation (SQLAlchemy Core)  
✅ In-memory schema cache  
✅ Alembic migration for schema table  
✅ Unit tests (20+ tests)  
✅ SQLite and PostgreSQL compatibility

### Out of Scope

❌ Row insert/select operations (Sortie 2)  
❌ NATS handlers (Sortie 2)  
❌ Schema migrations (Sprint 15)  
❌ Complex field types (JSON, arrays) - basic types only

---

## 3. Requirements

### Functional Requirements

**FR-1**: PluginTableSchemas model must store:
- plugin_name (string, 100 chars max)
- table_name (string, 100 chars max)
- schema_json (JSON text: field definitions)
- version (integer, default 1)
- created_at, updated_at timestamps
- Composite unique constraint on (plugin_name, table_name)

**FR-2**: SchemaRegistry must provide:
- register_schema(plugin_name, table_name, schema_dict) -> bool
- get_schema(plugin_name, table_name) -> dict | None
- list_schemas(plugin_name) -> list[dict]
- delete_schema(plugin_name, table_name) -> bool
- In-memory cache of all schemas

**FR-3**: Schema validation must check:
- Table name: lowercase, alphanumeric + underscores, 1-100 chars
- Field names: lowercase, alphanumeric + underscores, 1-64 chars
- Field types: string, integer, float, boolean, datetime, text
- Required fields marked correctly
- At least one field defined (excluding auto-generated id)

**FR-4**: Dynamic table creation must:
- Create table with plugin_name prefix (e.g., `quote_db_quotes`)
- Add auto-increment `id` column (primary key)
- Add `created_at` and `updated_at` timestamp columns
- Create columns matching schema field types
- Support NOT NULL constraints for required fields
- Work on both SQLite and PostgreSQL

### Non-Functional Requirements

**NFR-1 Performance**: Schema cache enables <1ms schema lookups  
**NFR-2 Reliability**: Invalid schemas rejected with clear error messages  
**NFR-3 Testing**: 100% coverage of SchemaRegistry class  
**NFR-4 Compatibility**: Tables work identically on SQLite and PostgreSQL

---

## 4. Technical Design

### 4.1 Database Schema

**File**: `common/models.py`

```python
from sqlalchemy import Column, String, Text, Integer, DateTime, UniqueConstraint
from datetime import datetime
import json

class PluginTableSchema(Base):
    """
    Stores table schemas for plugin row-based storage.
    
    Each plugin can register multiple tables. The schema_json field
    defines the columns (name, type, required) for each table.
    """
    
    __tablename__ = 'plugin_table_schemas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_name = Column(String(100), nullable=False, index=True)
    table_name = Column(String(100), nullable=False)
    schema_json = Column(Text, nullable=False)  # JSON: {"fields": [...]}
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('plugin_name', 'table_name', name='uq_plugin_table'),
    )
    
    def __repr__(self):
        return f"<PluginTableSchema(plugin={self.plugin_name}, table={self.table_name}, v{self.version})>"
    
    def get_schema(self) -> dict:
        """Deserialize schema_json."""
        return json.loads(self.schema_json)
    
    def set_schema(self, schema: dict) -> None:
        """Serialize and store schema."""
        self.schema_json = json.dumps(schema)
```

### 4.2 Schema Format

```python
{
    "fields": [
        {
            "name": "text",
            "type": "text",
            "required": True
        },
        {
            "name": "author",
            "type": "string",
            "required": False
        },
        {
            "name": "rating",
            "type": "integer",
            "required": False
        },
        {
            "name": "added_at",
            "type": "datetime",
            "required": False
        }
    ]
}
```

**Supported Types**:
- `string` - VARCHAR(255)
- `text` - TEXT
- `integer` - INTEGER
- `float` - FLOAT
- `boolean` - BOOLEAN
- `datetime` - TIMESTAMP WITH TIME ZONE

### 4.3 SchemaRegistry Class

**File**: `common/schema_registry.py`

```python
import re
from typing import Optional
from sqlalchemy import create_engine, Table, Column, Integer, String, Text, Float, Boolean, DateTime, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from common.models import PluginTableSchema
import json
import logging

class SchemaRegistry:
    """
    Manages plugin table schemas with in-memory caching.
    
    Responsibilities:
    - Validate schema definitions
    - Store schemas in database
    - Create tables dynamically from schemas
    - Cache schemas for fast lookups
    """
    
    def __init__(self, db):
        """
        Initialize schema registry.
        
        Args:
            db: BotDatabase instance
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
        self._cache = {}  # {(plugin_name, table_name): schema_dict}
        
    async def load_cache(self) -> None:
        """Load all schemas from database into memory cache."""
        async with self.db.session_factory() as session:
            from sqlalchemy import select
            stmt = select(PluginTableSchema)
            result = await session.execute(stmt)
            schemas = result.scalars().all()
            
            for schema_model in schemas:
                key = (schema_model.plugin_name, schema_model.table_name)
                self._cache[key] = schema_model.get_schema()
            
            self.logger.info(f"Loaded {len(self._cache)} schemas into cache")
    
    def validate_schema(self, schema: dict) -> tuple[bool, str]:
        """
        Validate schema structure and field definitions.
        
        Args:
            schema: Schema dict with 'fields' key
        
        Returns:
            (is_valid, error_message)
        """
        # Check structure
        if not isinstance(schema, dict):
            return False, "Schema must be a dictionary"
        
        if 'fields' not in schema:
            return False, "Schema must have 'fields' key"
        
        if not isinstance(schema['fields'], list):
            return False, "'fields' must be a list"
        
        if len(schema['fields']) == 0:
            return False, "Schema must have at least one field"
        
        # Validate each field
        field_names = set()
        for i, field in enumerate(schema['fields']):
            if not isinstance(field, dict):
                return False, f"Field {i} must be a dictionary"
            
            # Check required keys
            if 'name' not in field:
                return False, f"Field {i} missing 'name'"
            
            if 'type' not in field:
                return False, f"Field {i} missing 'type'"
            
            # Validate field name
            name = field['name']
            if not isinstance(name, str):
                return False, f"Field name must be string, got {type(name)}"
            
            if not re.match(r'^[a-z][a-z0-9_]{0,63}$', name):
                return False, (
                    f"Field name '{name}' invalid. Must start with lowercase letter, "
                    f"contain only lowercase letters, numbers, underscores, max 64 chars"
                )
            
            # Check for duplicate names
            if name in field_names:
                return False, f"Duplicate field name: {name}"
            field_names.add(name)
            
            # Reserved field names
            if name in ('id', 'created_at', 'updated_at'):
                return False, f"Field name '{name}' is reserved"
            
            # Validate field type
            valid_types = ('string', 'text', 'integer', 'float', 'boolean', 'datetime')
            if field['type'] not in valid_types:
                return False, (
                    f"Field '{name}' has invalid type '{field['type']}'. "
                    f"Valid types: {', '.join(valid_types)}"
                )
            
            # Validate 'required' field
            if 'required' in field and not isinstance(field['required'], bool):
                return False, f"Field '{name}' 'required' must be boolean"
        
        return True, ""
    
    def validate_table_name(self, table_name: str) -> tuple[bool, str]:
        """
        Validate table name format.
        
        Args:
            table_name: Table name to validate
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(table_name, str):
            return False, "Table name must be a string"
        
        if not re.match(r'^[a-z][a-z0-9_]{0,99}$', table_name):
            return False, (
                f"Table name '{table_name}' invalid. Must start with lowercase letter, "
                f"contain only lowercase letters, numbers, underscores, max 100 chars"
            )
        
        return True, ""
    
    async def register_schema(
        self,
        plugin_name: str,
        table_name: str,
        schema: dict
    ) -> bool:
        """
        Register a table schema and create the table.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            schema: Schema definition
        
        Returns:
            True if registered successfully
        
        Raises:
            ValueError: If schema validation fails
        """
        # Validate table name
        valid, error = self.validate_table_name(table_name)
        if not valid:
            raise ValueError(error)
        
        # Validate schema
        valid, error = self.validate_schema(schema)
        if not valid:
            raise ValueError(error)
        
        # Check if already exists
        key = (plugin_name, table_name)
        if key in self._cache:
            self.logger.warning(
                f"Schema for {plugin_name}.{table_name} already exists, skipping"
            )
            return False
        
        # Store in database
        async with self.db.session_factory() as session:
            schema_model = PluginTableSchema(
                plugin_name=plugin_name,
                table_name=table_name,
                version=1
            )
            schema_model.set_schema(schema)
            
            session.add(schema_model)
            await session.commit()
        
        # Create table
        await self._create_table(plugin_name, table_name, schema)
        
        # Update cache
        self._cache[key] = schema
        
        self.logger.info(f"Registered schema: {plugin_name}.{table_name}")
        return True
    
    async def _create_table(
        self,
        plugin_name: str,
        table_name: str,
        schema: dict
    ) -> None:
        """
        Create database table from schema.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name
            schema: Schema definition
        """
        full_table_name = f"{plugin_name}_{table_name}"
        
        # Build column list
        columns = [
            Column('id', Integer, primary_key=True, autoincrement=True),
        ]
        
        # Map schema types to SQLAlchemy types
        type_map = {
            'string': String(255),
            'text': Text,
            'integer': Integer,
            'float': Float,
            'boolean': Boolean,
            'datetime': DateTime(timezone=True),
        }
        
        for field in schema['fields']:
            col_type = type_map[field['type']]
            nullable = not field.get('required', False)
            
            columns.append(
                Column(field['name'], col_type, nullable=nullable)
            )
        
        # Add timestamps
        columns.append(
            Column('created_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
        )
        columns.append(
            Column('updated_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
        )
        
        # Create table
        metadata = MetaData()
        table = Table(full_table_name, metadata, *columns)
        
        async with self.db.engine.begin() as conn:
            await conn.run_sync(metadata.create_all, tables=[table])
        
        self.logger.info(f"Created table: {full_table_name}")
    
    def get_schema(self, plugin_name: str, table_name: str) -> Optional[dict]:
        """
        Get schema from cache.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name
        
        Returns:
            Schema dict or None if not found
        """
        return self._cache.get((plugin_name, table_name))
    
    async def list_schemas(self, plugin_name: str) -> list[dict]:
        """
        List all schemas for a plugin.
        
        Args:
            plugin_name: Plugin identifier
        
        Returns:
            List of schema info dicts
        """
        schemas = []
        for (p_name, t_name), schema in self._cache.items():
            if p_name == plugin_name:
                schemas.append({
                    'table_name': t_name,
                    'fields': schema['fields'],
                    'field_count': len(schema['fields'])
                })
        return schemas
    
    async def delete_schema(
        self,
        plugin_name: str,
        table_name: str
    ) -> bool:
        """
        Delete schema and drop table.
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name
        
        Returns:
            True if deleted
        """
        key = (plugin_name, table_name)
        if key not in self._cache:
            return False
        
        # Drop table
        full_table_name = f"{plugin_name}_{table_name}"
        async with self.db.engine.begin() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {full_table_name}")
        
        # Delete from database
        async with self.db.session_factory() as session:
            from sqlalchemy import delete
            stmt = delete(PluginTableSchema).where(
                PluginTableSchema.plugin_name == plugin_name,
                PluginTableSchema.table_name == table_name
            )
            await session.execute(stmt)
            await session.commit()
        
        # Remove from cache
        del self._cache[key]
        
        self.logger.info(f"Deleted schema and table: {plugin_name}.{table_name}")
        return True
```

---

## 5. Implementation Steps

### Step 1: Create PluginTableSchema Model

1. Open `common/models.py`
2. Add PluginTableSchema class
3. Add all columns with proper types
4. Add unique constraint on (plugin_name, table_name)
5. Implement get_schema() and set_schema() methods

### Step 2: Create Alembic Migration

1. Generate migration: `alembic revision -m "add plugin table schemas"`
2. Edit migration file with table definition
3. Test migration: `alembic upgrade head`
4. Verify table: Check plugin_table_schemas exists
5. Test rollback: `alembic downgrade -1`

### Step 3: Implement SchemaRegistry

1. Create `common/schema_registry.py`
2. Implement SchemaRegistry class
3. Add validation methods
4. Add register_schema() with table creation
5. Add get_schema() using cache
6. Add list_schemas() and delete_schema()

### Step 4: Integrate with BotDatabase

1. Add SchemaRegistry instance to BotDatabase
2. Call load_cache() in BotDatabase initialization
3. Export get_schema() helper method

### Step 5: Create Comprehensive Tests

**File**: `tests/unit/test_schema_registry.py`

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
import pytest
from common.schema_registry import SchemaRegistry
from common.database import BotDatabase

class TestSchemaRegistry:
    """Test SchemaRegistry class."""
    
    @pytest.fixture
    async def registry(self):
        """Create schema registry with test database."""
        db = BotDatabase("sqlite:///:memory:")
        await db.create_tables()
        registry = SchemaRegistry(db)
        await registry.load_cache()
        yield registry
        await db.close()
    
    async def test_validate_schema_valid(self, registry):
        """Test valid schema passes validation."""
        schema = {
            "fields": [
                {"name": "text", "type": "text", "required": True},
                {"name": "author", "type": "string", "required": False}
            ]
        }
        
        valid, error = registry.validate_schema(schema)
        assert valid == True
        assert error == ""
    
    async def test_validate_schema_missing_fields(self, registry):
        """Test schema without 'fields' key."""
        schema = {}
        
        valid, error = registry.validate_schema(schema)
        assert valid == False
        assert "fields" in error
    
    async def test_validate_schema_empty_fields(self, registry):
        """Test schema with empty fields list."""
        schema = {"fields": []}
        
        valid, error = registry.validate_schema(schema)
        assert valid == False
        assert "at least one field" in error
    
    async def test_validate_schema_invalid_field_name(self, registry):
        """Test invalid field names."""
        invalid_names = [
            "UpperCase",  # Must be lowercase
            "123start",   # Must start with letter
            "a" * 65,     # Too long
            "has-dash",   # No dashes allowed
            "id",         # Reserved
            "created_at", # Reserved
        ]
        
        for name in invalid_names:
            schema = {"fields": [{"name": name, "type": "string"}]}
            valid, error = registry.validate_schema(schema)
            assert valid == False
    
    async def test_validate_schema_invalid_type(self, registry):
        """Test invalid field type."""
        schema = {
            "fields": [
                {"name": "field1", "type": "invalid_type"}
            ]
        }
        
        valid, error = registry.validate_schema(schema)
        assert valid == False
        assert "invalid type" in error.lower()
    
    async def test_validate_schema_duplicate_field_names(self, registry):
        """Test duplicate field names."""
        schema = {
            "fields": [
                {"name": "text", "type": "string"},
                {"name": "text", "type": "string"}  # Duplicate
            ]
        }
        
        valid, error = registry.validate_schema(schema)
        assert valid == False
        assert "duplicate" in error.lower()
    
    async def test_validate_table_name_valid(self, registry):
        """Test valid table names."""
        valid_names = ["quotes", "user_data", "trivia_stats", "a", "t123"]
        
        for name in valid_names:
            valid, error = registry.validate_table_name(name)
            assert valid == True, f"'{name}' should be valid"
    
    async def test_validate_table_name_invalid(self, registry):
        """Test invalid table names."""
        invalid_names = [
            "UpperCase",   # Must be lowercase
            "123start",    # Must start with letter
            "has-dash",    # No dashes
            "a" * 101,     # Too long
        ]
        
        for name in invalid_names:
            valid, error = registry.validate_table_name(name)
            assert valid == False, f"'{name}' should be invalid"
    
    async def test_register_schema_success(self, registry):
        """Test successful schema registration."""
        schema = {
            "fields": [
                {"name": "text", "type": "text", "required": True}
            ]
        }
        
        result = await registry.register_schema("test_plugin", "quotes", schema)
        assert result == True
        
        # Verify in cache
        cached = registry.get_schema("test_plugin", "quotes")
        assert cached == schema
    
    async def test_register_schema_creates_table(self, registry):
        """Test that table is created after registration."""
        schema = {
            "fields": [
                {"name": "message", "type": "string", "required": True}
            ]
        }
        
        await registry.register_schema("test", "messages", schema)
        
        # Verify table exists by attempting insert
        from sqlalchemy import text
        async with registry.db.engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO test_messages (message) VALUES ('test')")
            )
    
    async def test_register_schema_duplicate(self, registry):
        """Test registering duplicate schema."""
        schema = {"fields": [{"name": "text", "type": "text"}]}
        
        await registry.register_schema("test", "data", schema)
        result = await registry.register_schema("test", "data", schema)
        
        assert result == False  # Already exists
    
    async def test_get_schema_not_found(self, registry):
        """Test getting non-existent schema."""
        result = registry.get_schema("nonexistent", "table")
        assert result is None
    
    async def test_list_schemas(self, registry):
        """Test listing all schemas for a plugin."""
        await registry.register_schema("plugin1", "table1", {
            "fields": [{"name": "field1", "type": "string"}]
        })
        await registry.register_schema("plugin1", "table2", {
            "fields": [{"name": "field2", "type": "integer"}]
        })
        await registry.register_schema("plugin2", "table1", {
            "fields": [{"name": "field3", "type": "text"}]
        })
        
        schemas = await registry.list_schemas("plugin1")
        assert len(schemas) == 2
        assert any(s['table_name'] == 'table1' for s in schemas)
        assert any(s['table_name'] == 'table2' for s in schemas)
    
    async def test_delete_schema(self, registry):
        """Test deleting schema and table."""
        schema = {"fields": [{"name": "data", "type": "string"}]}
        await registry.register_schema("test", "temp", schema)
        
        # Delete
        result = await registry.delete_schema("test", "temp")
        assert result == True
        
        # Verify removed from cache
        cached = registry.get_schema("test", "temp")
        assert cached is None
    
    async def test_load_cache(self, registry):
        """Test loading schemas from database into cache."""
        # Register some schemas
        await registry.register_schema("plugin1", "table1", {
            "fields": [{"name": "field1", "type": "string"}]
        })
        
        # Create new registry and load cache
        db2 = BotDatabase("sqlite:///:memory:")
        await db2.create_tables()
        registry2 = SchemaRegistry(db2)
        await registry2.load_cache()
        
        # Should have loaded schema
        cached = registry2.get_schema("plugin1", "table1")
        assert cached is not None
```

**Test Coverage Target**: 100% of SchemaRegistry class

---

## 7. Acceptance Criteria

- [x] **AC-1**: PluginTableSchema model created
  - Given the model file
  - When imported
  - Then PluginTableSchema class exists with all columns

- [x] **AC-2**: Alembic migration applies cleanly
  - Given a clean database
  - When running `alembic upgrade head`
  - Then plugin_table_schemas table exists

- [x] **AC-3**: Schema validation rejects invalid schemas
  - Given invalid schema (missing fields, bad types, etc.)
  - When calling validate_schema()
  - Then returns False with error message

- [x] **AC-4**: Table creation works
  - Given valid schema
  - When calling register_schema()
  - Then table created in database

- [x] **AC-5**: Schema cache works
  - Given registered schema
  - When calling get_schema()
  - Then returns schema from cache (<1ms)

- [x] **AC-6**: Plugin isolation enforced
  - Given schemas for plugin-a and plugin-b
  - When listing schemas for plugin-a
  - Then only plugin-a schemas returned

- [x] **AC-7**: All unit tests pass
  - Given test suite
  - When running pytest
  - Then 20+ tests pass with 100% coverage

---

## 8. Rollout Plan

### Pre-deployment

1. Review code changes
2. Run full test suite
3. Verify migration applies and reverses cleanly

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-13-sortie-1-schema-registry`
2. Implement PluginTableSchema model
3. Create Alembic migration
4. Implement SchemaRegistry class
5. Write comprehensive unit tests
6. Run tests and verify coverage
7. Commit changes with message:
   ```
   Sprint 13 Sortie 1: Schema Registry & Table Creation
   
   - Add PluginTableSchema model for storing table schemas
   - Create SchemaRegistry class with validation and caching
   - Implement dynamic table creation from schemas
   - Add comprehensive unit tests (20+ tests, 100% coverage)
   
   Implements: SPEC-Sortie-1-Schema-Registry-Table-Creation.md
   Related: PRD-Row-Operations-Foundation.md
   ```
8. Push branch and create PR
9. Code review
10. Merge to main

### Post-deployment

- Monitor schema registrations
- Verify cache performance
- Check for validation errors in logs

### Rollback Procedure

If issues arise:
```bash
alembic downgrade -1
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sprint 12**: Database infrastructure
- **SQLAlchemy 2.0+**: For dynamic table creation
- **Alembic**: For migrations

### External Dependencies

None

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Dynamic table creation fails | Low | High | Test on both SQLite and PostgreSQL |
| Cache becomes stale | Low | Medium | Load cache on DatabaseService startup |
| Invalid schemas slip through | Low | Medium | Comprehensive validation tests |
| Reserved keywords conflict | Medium | Low | Check against SQLAlchemy reserved words |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Schema format documented with examples
- Validation rules explained

### Developer Documentation

Update `docs/DATABASE.md` with:
- Schema registry usage
- Supported field types
- Table naming conventions

---

## 11. Related Specifications

**Previous**: Sprint 12 Complete  
**Next**: 
- [SPEC-Sortie-2-Insert-Select-Operations.md](SPEC-Sortie-2-Insert-Select-Operations.md)
- [SPEC-Sortie-3-Update-Delete-Operations.md](SPEC-Sortie-3-Update-Delete-Operations.md)
- [SPEC-Sortie-4-Search-Filters-Pagination.md](SPEC-Sortie-4-Search-Filters-Pagination.md)
- [SPEC-Sortie-5-Testing-Polish-Documentation.md](SPEC-Sortie-5-Testing-Polish-Documentation.md)

**Parent PRD**: [PRD-Row-Operations-Foundation.md](PRD-Row-Operations-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
