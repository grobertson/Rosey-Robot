#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for BotDatabase row storage operations (Sprint 13 Sortie 2).

Tests:
- get_table() table reflection and caching
- _validate_and_coerce_row() validation and type coercion
- row_insert() single and bulk inserts
- row_select() retrieving rows by ID

Coverage Target: 90%+
"""
import pytest
from datetime import datetime
from common.database import BotDatabase
from common.models import Base


@pytest.fixture
async def db():
    """Create in-memory database for testing."""
    database = BotDatabase(':memory:')
    
    # Create all tables directly (bypass connect() which expects tables from Alembic)
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    database._is_connected = True
    
    # Load schema registry
    await database.schema_registry.load_cache()
    
    yield database
    
    await database.close()


# ==================== get_table() Tests ====================

class TestGetTable:
    """Test get_table method for table reflection and caching."""
    
    async def test_get_table_reflects_table(self, db):
        """Test that get_table reflects table structure."""
        # Register a schema
        await db.schema_registry.register_schema("test", "items", {
            "fields": [
                {"name": "name", "type": "string", "required": True}
            ]
        })
        
        # Get table
        table = await db.get_table("test_items")
        
        # Verify table structure
        assert table.name == "test_items"
        assert 'id' in table.c
        assert 'name' in table.c
        assert 'created_at' in table.c
        assert 'updated_at' in table.c
    
    async def test_get_table_caches_tables(self, db):
        """Test that get_table caches table objects."""
        await db.schema_registry.register_schema("test", "data", {
            "fields": [{"name": "value", "type": "string", "required": True}]
        })
        
        # Get table twice
        table1 = await db.get_table("test_data")
        table2 = await db.get_table("test_data")
        
        # Should be same object (cached)
        assert table1 is table2


# ==================== _validate_and_coerce_row() Tests ====================

class TestValidateAndCoerceRow:
    """Test _validate_and_coerce_row method for validation and type coercion."""
    
    def test_validates_required_fields(self, db):
        """Test that required fields are enforced."""
        schema = {
            "fields": [
                {"name": "username", "type": "string", "required": True},
                {"name": "email", "type": "string", "required": False}
            ]
        }
        
        # Missing required field
        with pytest.raises(ValueError, match="Missing required field: username"):
            db._validate_and_coerce_row({"email": "test@example.com"}, schema)
    
    def test_rejects_unknown_fields(self, db):
        """Test that unknown fields are rejected."""
        schema = {
            "fields": [
                {"name": "name", "type": "string", "required": True}
            ]
        }
        
        with pytest.raises(ValueError, match="Unknown field: age"):
            db._validate_and_coerce_row({"name": "Alice", "age": 30}, schema)
    
    def test_allows_null_for_optional_fields(self, db):
        """Test that optional fields can be null."""
        schema = {
            "fields": [
                {"name": "title", "type": "string", "required": True},
                {"name": "subtitle", "type": "string", "required": False}
            ]
        }
        
        result = db._validate_and_coerce_row({
            "title": "Main",
            "subtitle": None
        }, schema)
        
        assert result['title'] == "Main"
        assert result['subtitle'] is None
    
    def test_rejects_null_for_required_fields(self, db):
        """Test that required fields cannot be null."""
        schema = {
            "fields": [
                {"name": "name", "type": "string", "required": True}
            ]
        }
        
        with pytest.raises(ValueError, match="Field 'name' cannot be null"):
            db._validate_and_coerce_row({"name": None}, schema)
    
    def test_coerces_string_type(self, db):
        """Test string type coercion."""
        schema = {
            "fields": [{"name": "text", "type": "string", "required": True}]
        }
        
        # Number to string
        result = db._validate_and_coerce_row({"text": 42}, schema)
        assert result['text'] == "42"
        assert isinstance(result['text'], str)
    
    def test_coerces_integer_type(self, db):
        """Test integer type coercion."""
        schema = {
            "fields": [{"name": "count", "type": "integer", "required": True}]
        }
        
        # String to integer
        result = db._validate_and_coerce_row({"count": "42"}, schema)
        assert result['count'] == 42
        assert isinstance(result['count'], int)
        
        # Float to integer
        result = db._validate_and_coerce_row({"count": 42.9}, schema)
        assert result['count'] == 42
    
    def test_coerces_float_type(self, db):
        """Test float type coercion."""
        schema = {
            "fields": [{"name": "price", "type": "float", "required": True}]
        }
        
        # String to float
        result = db._validate_and_coerce_row({"price": "19.99"}, schema)
        assert result['price'] == 19.99
        assert isinstance(result['price'], float)
        
        # Integer to float
        result = db._validate_and_coerce_row({"price": 20}, schema)
        assert result['price'] == 20.0
    
    def test_coerces_boolean_type(self, db):
        """Test boolean type coercion."""
        schema = {
            "fields": [{"name": "active", "type": "boolean", "required": True}]
        }
        
        # String to boolean (truthy)
        for value in ['true', 'True', '1', 'yes', 'YES', 'on']:
            result = db._validate_and_coerce_row({"active": value}, schema)
            assert result['active'] is True
        
        # String to boolean (falsy)
        for value in ['false', 'False', '0', 'no', 'off', '']:
            result = db._validate_and_coerce_row({"active": value}, schema)
            assert result['active'] is False
        
        # Number to boolean
        result = db._validate_and_coerce_row({"active": 1}, schema)
        assert result['active'] is True
        
        result = db._validate_and_coerce_row({"active": 0}, schema)
        assert result['active'] is False
    
    def test_coerces_datetime_type(self, db):
        """Test datetime type coercion."""
        schema = {
            "fields": [{"name": "timestamp", "type": "datetime", "required": True}]
        }
        
        # ISO 8601 string to datetime
        result = db._validate_and_coerce_row({
            "timestamp": "2025-11-24T10:30:00"
        }, schema)
        assert isinstance(result['timestamp'], datetime)
        assert result['timestamp'].year == 2025
        assert result['timestamp'].month == 11
        assert result['timestamp'].day == 24
        
        # ISO 8601 with Z suffix
        result = db._validate_and_coerce_row({
            "timestamp": "2025-11-24T10:30:00Z"
        }, schema)
        assert isinstance(result['timestamp'], datetime)
        
        # Already datetime object
        now = datetime.now()
        result = db._validate_and_coerce_row({"timestamp": now}, schema)
        assert result['timestamp'] is now
    
    def test_raises_on_invalid_type_coercion(self, db):
        """Test that invalid type coercion raises ValueError."""
        schema = {
            "fields": [{"name": "count", "type": "integer", "required": True}]
        }
        
        # Invalid string for integer
        with pytest.raises(ValueError, match="Cannot convert value to integer"):
            db._validate_and_coerce_row({"count": "not_a_number"}, schema)


# ==================== row_insert() Tests ====================

class TestRowInsert:
    """Test row_insert method for inserting rows."""
    
    async def test_insert_single_row(self, db):
        """Test inserting a single row."""
        # Register schema
        await db.schema_registry.register_schema("test", "quotes", {
            "fields": [
                {"name": "text", "type": "text", "required": True}
            ]
        })
        
        # Insert
        result = await db.row_insert("test", "quotes", {"text": "Hello world"})
        
        assert result['created'] is True
        assert isinstance(result['id'], int)
        assert result['id'] > 0
    
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
        assert all(isinstance(id, int) for id in result['ids'])
    
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
        """Test type coercion during insert."""
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
        
        assert result['created'] is True
    
    async def test_insert_fails_for_unregistered_table(self, db):
        """Test that insert fails for unregistered table."""
        with pytest.raises(ValueError, match="not registered"):
            await db.row_insert("test", "nonexistent", {"data": "value"})
    
    async def test_insert_empty_list_raises_error(self, db):
        """Test that inserting empty list raises error."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        with pytest.raises(ValueError, match="No data provided"):
            await db.row_insert("test", "items", [])
    
    async def test_insert_validates_all_rows_in_bulk(self, db):
        """Test that all rows are validated in bulk insert."""
        await db.schema_registry.register_schema("test", "data", {
            "fields": [{"name": "value", "type": "integer", "required": True}]
        })
        
        # Second row has invalid data
        with pytest.raises(ValueError, match="Row 1"):
            await db.row_insert("test", "data", [
                {"value": 1},
                {"value": "invalid"}  # Cannot coerce to integer
            ])


# ==================== row_select() Tests ====================

class TestRowSelect:
    """Test row_select method for retrieving rows."""
    
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
        
        assert result['exists'] is True
        assert result['data']['id'] == row_id
        assert result['data']['name'] == "Item 1"
        assert 'created_at' in result['data']
        assert 'updated_at' in result['data']
    
    async def test_select_nonexistent_row(self, db):
        """Test selecting a row that doesn't exist."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        result = await db.row_select("test", "items", 99999)
        assert result['exists'] is False
        assert 'data' not in result
    
    async def test_select_fails_for_unregistered_table(self, db):
        """Test that select fails for unregistered table."""
        with pytest.raises(ValueError, match="not registered"):
            await db.row_select("test", "nonexistent", 1)
    
    async def test_select_serializes_datetime(self, db):
        """Test that datetime fields are serialized to ISO strings."""
        await db.schema_registry.register_schema("test", "events", {
            "fields": [
                {"name": "timestamp", "type": "datetime", "required": True}
            ]
        })
        
        # Insert with datetime
        insert_result = await db.row_insert("test", "events", {
            "timestamp": "2025-11-24T10:30:00Z"
        })
        
        # Select
        result = await db.row_select("test", "events", insert_result['id'])
        
        assert result['exists'] is True
        # timestamp should be ISO string
        assert isinstance(result['data']['timestamp'], str)
        assert 'T' in result['data']['timestamp']  # ISO format has 'T'
        
        # created_at and updated_at also serialized
        assert isinstance(result['data']['created_at'], str)
        assert isinstance(result['data']['updated_at'], str)


# ==================== Integration Tests ====================

class TestRowOperationsIntegration:
    """Integration tests for row operations workflow."""
    
    async def test_complete_workflow(self, db):
        """Test complete insert-select workflow."""
        # Register schema
        await db.schema_registry.register_schema("blog", "posts", {
            "fields": [
                {"name": "title", "type": "string", "required": True},
                {"name": "content", "type": "text", "required": True},
                {"name": "published", "type": "boolean", "required": False},
                {"name": "views", "type": "integer", "required": False}
            ]
        })
        
        # Insert post
        insert_result = await db.row_insert("blog", "posts", {
            "title": "My First Post",
            "content": "This is the content of my first blog post.",
            "published": True,
            "views": 0
        })
        
        assert insert_result['created'] is True
        post_id = insert_result['id']
        
        # Select post
        select_result = await db.row_select("blog", "posts", post_id)
        
        assert select_result['exists'] is True
        post = select_result['data']
        assert post['title'] == "My First Post"
        assert post['content'] == "This is the content of my first blog post."
        assert post['published'] is True
        assert post['views'] == 0
    
    async def test_plugin_isolation(self, db):
        """Test that different plugins have isolated tables."""
        # Register same table name for two plugins
        schema = {
            "fields": [{"name": "data", "type": "string", "required": True}]
        }
        
        await db.schema_registry.register_schema("plugin_a", "items", schema)
        await db.schema_registry.register_schema("plugin_b", "items", schema)
        
        # Insert into plugin_a
        result_a = await db.row_insert("plugin_a", "items", {"data": "A data"})
        
        # Insert into plugin_b
        result_b = await db.row_insert("plugin_b", "items", {"data": "B data"})
        
        # Select from each
        select_a = await db.row_select("plugin_a", "items", result_a['id'])
        select_b = await db.row_select("plugin_b", "items", result_b['id'])
        
        # Should be isolated
        assert select_a['data']['data'] == "A data"
        assert select_b['data']['data'] == "B data"
        
        # Verify tables are different
        assert db.get_table("plugin_a_items") is not db.get_table("plugin_b_items")
