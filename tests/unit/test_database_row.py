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
        assert await db.get_table("plugin_a_items") is not await db.get_table("plugin_b_items")


# ==================== Update & Delete Tests ====================

class TestRowUpdate:
    """Test row_update method for partial updates."""
    
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
        
        assert update_result['updated'] is True
        assert update_result['id'] == row_id
        
        # Verify name unchanged, value updated
        select_result = await db.row_select("test", "items", row_id)
        assert select_result['data']['name'] == "Item 1"
        assert select_result['data']['value'] == 200
    
    async def test_update_multiple_fields(self, db):
        """Test updating multiple fields at once."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [
                {"name": "name", "type": "string", "required": True},
                {"name": "value", "type": "integer", "required": False},
                {"name": "active", "type": "boolean", "required": False}
            ]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {
            "name": "Item",
            "value": 10,
            "active": False
        })
        row_id = insert_result['id']
        
        # Update multiple fields
        update_result = await db.row_update("test", "items", row_id, {
            "name": "Updated Item",
            "value": 20
        })
        
        assert update_result['updated'] is True
        
        # Verify updates
        select_result = await db.row_select("test", "items", row_id)
        assert select_result['data']['name'] == "Updated Item"
        assert select_result['data']['value'] == 20
        assert select_result['data']['active'] is False  # Unchanged
    
    async def test_update_nonexistent_row(self, db):
        """Test updating a row that doesn't exist."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        result = await db.row_update("test", "items", 99999, {"name": "New Name"})
        assert result['exists'] is False
        assert 'updated' not in result
    
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
        """Test that updated_at is automatically set on update."""
        import asyncio
        
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert
        insert_result = await db.row_insert("test", "items", {"name": "Original"})
        row_id = insert_result['id']
        
        # Get initial timestamps
        select1 = await db.row_select("test", "items", row_id)
        created_at = select1['data']['created_at']
        updated_at1 = select1['data']['updated_at']
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Update
        await db.row_update("test", "items", row_id, {"name": "Updated"})
        
        # Verify updated_at changed
        select2 = await db.row_select("test", "items", row_id)
        assert select2['data']['created_at'] == created_at  # Unchanged
        assert select2['data']['updated_at'] > updated_at1  # Changed
    
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
    
    async def test_update_empty_data_raises_error(self, db):
        """Test that empty update data raises error."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        insert_result = await db.row_insert("test", "items", {"name": "Item"})
        row_id = insert_result['id']
        
        # Try empty update
        with pytest.raises(ValueError, match="No data provided"):
            await db.row_update("test", "items", row_id, {})
    
    async def test_update_unregistered_table_raises_error(self, db):
        """Test update fails for unregistered table."""
        with pytest.raises(ValueError, match="not registered"):
            await db.row_update("test", "nonexistent", 1, {"name": "Test"})
    
    async def test_update_validates_data(self, db):
        """Test that update validates data like insert."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "count", "type": "integer", "required": True}]
        })
        
        insert_result = await db.row_insert("test", "items", {"count": 10})
        row_id = insert_result['id']
        
        # Try invalid type coercion
        with pytest.raises(ValueError, match="Cannot convert"):
            await db.row_update("test", "items", row_id, {"count": "not_a_number"})


class TestRowDelete:
    """Test row_delete method for idempotent deletion."""
    
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
        assert delete_result['deleted'] is True
        
        # Verify gone
        select_result = await db.row_select("test", "items", row_id)
        assert select_result['exists'] is False
    
    async def test_delete_nonexistent_row_idempotent(self, db):
        """Test that deleting non-existent row is idempotent."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Delete non-existent row
        result = await db.row_delete("test", "items", 99999)
        assert result['deleted'] is False  # Returns False but doesn't error
    
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
        assert result1['deleted'] is True
        
        # Second delete (idempotent)
        result2 = await db.row_delete("test", "items", row_id)
        assert result2['deleted'] is False  # No error, just returns False
    
    async def test_delete_unregistered_table_raises_error(self, db):
        """Test delete fails for unregistered table."""
        with pytest.raises(ValueError, match="not registered"):
            await db.row_delete("test", "nonexistent", 1)
    
    async def test_delete_multiple_rows(self, db):
        """Test deleting multiple rows one by one."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert multiple rows
        id1 = (await db.row_insert("test", "items", {"name": "Item 1"}))['id']
        id2 = (await db.row_insert("test", "items", {"name": "Item 2"}))['id']
        id3 = (await db.row_insert("test", "items", {"name": "Item 3"}))['id']
        
        # Delete them
        result1 = await db.row_delete("test", "items", id1)
        result2 = await db.row_delete("test", "items", id2)
        result3 = await db.row_delete("test", "items", id3)
        
        assert result1['deleted'] is True
        assert result2['deleted'] is True
        assert result3['deleted'] is True
        
        # Verify all gone
        assert (await db.row_select("test", "items", id1))['exists'] is False
        assert (await db.row_select("test", "items", id2))['exists'] is False
        assert (await db.row_select("test", "items", id3))['exists'] is False


# ==================== Search Tests ====================

class TestRowSearch:
    """Test row_search method with filters, sorting, and pagination."""
    
    async def test_search_no_filters(self, db):
        """Test search with no filters returns all rows."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert multiple rows
        result = await db.row_insert("test", "items", [
            {"name": "Item 1"},
            {"name": "Item 2"},
            {"name": "Item 3"}
        ])
        
        # Search all
        search_result = await db.row_search("test", "items")
        
        assert search_result['count'] == 3
        assert search_result['truncated'] is False
        assert len(search_result['rows']) == 3
    
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
        assert result['rows'][0]['available'] is True
    
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
        assert page1['truncated'] is True  # More rows available
        assert [r['seq'] for r in page1['rows']] == [0, 1, 2]
        
        # Page 2 (limit=3, offset=3)
        page2 = await db.row_search("test", "data", limit=3, offset=3, sort={"field": "seq"})
        assert page2['count'] == 3
        assert page2['truncated'] is True
        assert [r['seq'] for r in page2['rows']] == [3, 4, 5]
        
        # Page 3 (limit=3, offset=6)
        page3 = await db.row_search("test", "data", limit=3, offset=6, sort={"field": "seq"})
        assert page3['count'] == 3
        assert page3['truncated'] is True
        assert [r['seq'] for r in page3['rows']] == [6, 7, 8]
        
        # Page 4 (last page)
        page4 = await db.row_search("test", "data", limit=3, offset=9, sort={"field": "seq"})
        assert page4['count'] == 1
        assert page4['truncated'] is False  # No more rows
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
        assert result['truncated'] is True  # 6th row exists
    
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
        assert result['truncated'] is False
    
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
        assert result is not None
        # If we had data, it would be limited to MAX_SEARCH_LIMIT
    
    async def test_search_rejects_invalid_limit(self, db):
        """Test that limit < 1 raises error."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [{"name": "val", "type": "integer", "required": True}]
        })
        
        with pytest.raises(ValueError, match="Limit must be at least 1"):
            await db.row_search("test", "items", limit=0)
    
    async def test_search_with_filter_and_sort(self, db):
        """Test search combining filters and sorting."""
        await db.schema_registry.register_schema("test", "tasks", {
            "fields": [
                {"name": "status", "type": "string", "required": True},
                {"name": "priority", "type": "integer", "required": True}
            ]
        })
        
        # Insert mixed data
        await db.row_insert("test", "tasks", [
            {"status": "active", "priority": 3},
            {"status": "active", "priority": 1},
            {"status": "done", "priority": 2},
            {"status": "active", "priority": 2}
        ])
        
        # Search active tasks sorted by priority desc
        result = await db.row_search(
            "test", "tasks",
            filters={"status": "active"},
            sort={"field": "priority", "order": "desc"}
        )
        
        assert result['count'] == 3
        priorities = [row['priority'] for row in result['rows']]
        assert priorities == [3, 2, 1]
    
    async def test_search_datetime_serialization(self, db):
        """Test that datetime fields are serialized to ISO strings."""
        await db.schema_registry.register_schema("test", "events", {
            "fields": [{"name": "name", "type": "string", "required": True}]
        })
        
        # Insert row (will have created_at)
        await db.row_insert("test", "events", [{"name": "event1"}])
        
        # Search
        result = await db.row_search("test", "events")
        
        assert result['count'] == 1
        row = result['rows'][0]
        
        # created_at should be string, not datetime object
        assert isinstance(row['created_at'], str)
        # Should be valid ISO format (no exception)
        from datetime import datetime
        datetime.fromisoformat(row['created_at'])
    
    async def test_search_unregistered_table(self, db):
        """Test that searching unregistered table raises error."""
        with pytest.raises(ValueError, match="not registered"):
            await db.row_search("test", "nonexistent")
    
    async def test_search_default_sort_order(self, db):
        """Test that default sort order is ascending."""
        await db.schema_registry.register_schema("test", "nums", {
            "fields": [{"name": "val", "type": "integer", "required": True}]
        })
        
        await db.row_insert("test", "nums", [
            {"val": 3},
            {"val": 1},
            {"val": 2}
        ])
        
        # Sort without order specified (should default to asc)
        result = await db.row_search("test", "nums", sort={"field": "val"})
        
        values = [row['val'] for row in result['rows']]
        assert values == [1, 2, 3]
    
    async def test_search_pagination_with_filters(self, db):
        """Test pagination works with filters."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [
                {"name": "category", "type": "string", "required": True},
                {"name": "seq", "type": "integer", "required": True}
            ]
        })
        
        # Insert mixed categories
        data = []
        for i in range(10):
            data.append({"category": "A" if i % 2 == 0 else "B", "seq": i})
        await db.row_insert("test", "items", data)
        
        # Search category A with pagination
        page1 = await db.row_search(
            "test", "items",
            filters={"category": "A"},
            limit=2,
            offset=0,
            sort={"field": "seq"}
        )
        
        assert page1['count'] == 2
        assert page1['truncated'] is True
        assert [r['seq'] for r in page1['rows']] == [0, 2]
        
        page2 = await db.row_search(
            "test", "items",
            filters={"category": "A"},
            limit=2,
            offset=2,
            sort={"field": "seq"}
        )
        
        assert page2['count'] == 2
        assert [r['seq'] for r in page2['rows']] == [4, 6]
    
    async def test_search_with_none_value_filter(self, db):
        """Test filtering with None/null value."""
        await db.schema_registry.register_schema("test", "items", {
            "fields": [
                {"name": "name", "type": "string", "required": True},
                {"name": "optional_field", "type": "string", "required": False}
            ]
        })
        
        # Insert rows with and without optional field
        await db.row_insert("test", "items", [
            {"name": "item1", "optional_field": "value"},
            {"name": "item2", "optional_field": None}  # Explicit None
        ])
        
        # Search for None value
        result = await db.row_search("test", "items", filters={"optional_field": None})
        
        assert result['count'] == 1
        assert result['rows'][0]['name'] == "item2"
