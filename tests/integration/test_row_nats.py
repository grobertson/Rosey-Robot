#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for row storage NATS handlers (Sprint 13 Sortie 2).

Tests DatabaseService NATS handlers:
- _handle_schema_register
- _handle_row_insert
- _handle_row_select

These tests verify the complete workflow from NATS request to database operation.

Coverage Target: 90%+
"""
import json
import pytest
from common.database import BotDatabase
from common.database_service import DatabaseService
from common.models import Base

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = None


@pytest.fixture
async def db():
    """Create in-memory database."""
    database = BotDatabase(':memory:')
    
    # Create all tables
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    database._is_connected = True
    await database.schema_registry.load_cache()
    
    yield database
    
    await database.close()


@pytest.fixture
async def nats_client():
    """Create NATS client connected to test server."""
    if NATS is None:
        pytest.skip("NATS not installed")
    
    nats = NATS()
    
    try:
        await nats.connect("nats://localhost:4222")
    except Exception:
        pytest.skip("NATS server not running")
    
    yield nats
    
    await nats.close()


@pytest.fixture
async def db_service(nats_client):
    """Create DatabaseService with NATS and in-memory database."""
    service = DatabaseService(nats_client, ':memory:')
    
    # Initialize database tables BEFORE calling start()
    # start() will call connect() which needs tables to exist
    async with service.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await service.start()
    
    yield service
    
    await service.stop()
    await service.db.close()


# ==================== Schema Registration Tests ====================

class TestSchemaRegisterNATS:
    """Test schema registration via NATS."""
    
    async def test_register_schema_via_nats(self, nats_client, db_service):
        """Test schema registration through NATS."""
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
        assert result['success'] is True
        
        # Verify schema registered
        schema = db_service.db.schema_registry.get_schema("test-plugin", "quotes")
        assert schema is not None
        assert len(schema['fields']) == 1
    
    async def test_register_schema_validates_fields(self, nats_client, db_service):
        """Test that schema validation works through NATS."""
        # Invalid field type
        response = await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "data",
                "schema": {
                    "fields": [
                        {"name": "value", "type": "invalid_type", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
    
    async def test_register_schema_missing_table(self, nats_client, db_service):
        """Test error when table name missing."""
        response = await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "schema": {
                    "fields": [{"name": "value", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "MISSING_FIELD"
        assert "table" in result['error']['message']
    
    async def test_register_schema_invalid_json(self, nats_client, db_service):
        """Test error on invalid JSON."""
        response = await nats_client.request(
            "rosey.db.row.test.schema.register",
            b"not valid json",
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "INVALID_JSON"


# ==================== Insert Tests ====================

class TestRowInsertNATS:
    """Test row insert via NATS."""
    
    async def test_insert_single_row_via_nats(self, nats_client, db_service):
        """Test single row insert through NATS."""
        # Register schema first
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert row
        response = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": {"name": "Test Item"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is True
        assert result['created'] is True
        assert isinstance(result['id'], int)
    
    async def test_insert_bulk_rows_via_nats(self, nats_client, db_service):
        """Test bulk insert through NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "data",
                "schema": {
                    "fields": [{"name": "value", "type": "integer", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Bulk insert
        response = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "data",
                "data": [
                    {"value": 1},
                    {"value": 2},
                    {"value": 3}
                ]
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is True
        assert result['created'] == 3
        assert len(result['ids']) == 3
    
    async def test_insert_validates_data(self, nats_client, db_service):
        """Test that insert validates data through NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "users",
                "schema": {
                    "fields": [
                        {"name": "username", "type": "string", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert missing required field
        response = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "users",
                "data": {"email": "test@example.com"}  # Missing username
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
    
    async def test_insert_unregistered_table(self, nats_client, db_service):
        """Test error when inserting to unregistered table."""
        response = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "nonexistent",
                "data": {"value": "data"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
        assert "not registered" in result['error']['message']


# ==================== Select Tests ====================

class TestRowSelectNATS:
    """Test row select via NATS."""
    
    async def test_select_existing_row_via_nats(self, nats_client, db_service):
        """Test selecting an existing row through NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "posts",
                "schema": {
                    "fields": [
                        {"name": "title", "type": "string", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "posts",
                "data": {"title": "My Post"}
            }).encode(),
            timeout=1.0
        )
        insert_result = json.loads(insert_resp.data.decode())
        row_id = insert_result['id']
        
        # Select
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({
                "table": "posts",
                "id": row_id
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(select_resp.data.decode())
        assert result['success'] is True
        assert result['exists'] is True
        assert result['data']['id'] == row_id
        assert result['data']['title'] == "My Post"
    
    async def test_select_nonexistent_row_via_nats(self, nats_client, db_service):
        """Test selecting a nonexistent row through NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "name", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Select nonexistent row
        response = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({
                "table": "items",
                "id": 99999
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is True
        assert result['exists'] is False
        assert 'data' not in result
    
    async def test_select_missing_id(self, nats_client, db_service):
        """Test error when ID missing."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "name", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        response = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({
                "table": "items"
                # Missing "id"
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "MISSING_FIELD"


# ==================== Complete Workflow Tests ====================

class TestCompleteWorkflow:
    """Test complete end-to-end workflow via NATS."""
    
    async def test_complete_workflow(self, nats_client, db_service):
        """Test register -> insert -> select workflow."""
        # 1. Register schema
        schema_resp = await nats_client.request(
            "rosey.db.row.blog.schema.register",
            json.dumps({
                "table": "articles",
                "schema": {
                    "fields": [
                        {"name": "title", "type": "string", "required": True},
                        {"name": "content", "type": "text", "required": True},
                        {"name": "views", "type": "integer", "required": False}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        schema_result = json.loads(schema_resp.data.decode())
        assert schema_result['success'] is True
        
        # 2. Insert article
        insert_resp = await nats_client.request(
            "rosey.db.row.blog.insert",
            json.dumps({
                "table": "articles",
                "data": {
                    "title": "Getting Started",
                    "content": "This is the content...",
                    "views": 0
                }
            }).encode(),
            timeout=1.0
        )
        insert_result = json.loads(insert_resp.data.decode())
        assert insert_result['success'] is True
        article_id = insert_result['id']
        
        # 3. Select article
        select_resp = await nats_client.request(
            "rosey.db.row.blog.select",
            json.dumps({
                "table": "articles",
                "id": article_id
            }).encode(),
            timeout=1.0
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['success'] is True
        assert select_result['exists'] is True
        assert select_result['data']['title'] == "Getting Started"
        assert select_result['data']['content'] == "This is the content..."
        assert select_result['data']['views'] == 0
    
    async def test_plugin_isolation_via_nats(self, nats_client, db_service):
        """Test that different plugins have isolated data through NATS."""
        schema = {
            "table": "items",
            "schema": {
                "fields": [{"name": "data", "type": "string", "required": True}]
            }
        }
        
        # Register same table for two plugins
        await nats_client.request(
            "rosey.db.row.plugin-a.schema.register",
            json.dumps(schema).encode(),
            timeout=1.0
        )
        await nats_client.request(
            "rosey.db.row.plugin-b.schema.register",
            json.dumps(schema).encode(),
            timeout=1.0
        )
        
        # Insert into plugin-a
        insert_a = await nats_client.request(
            "rosey.db.row.plugin-a.insert",
            json.dumps({"table": "items", "data": {"data": "A data"}}).encode(),
            timeout=1.0
        )
        id_a = json.loads(insert_a.data.decode())['id']
        
        # Insert into plugin-b
        insert_b = await nats_client.request(
            "rosey.db.row.plugin-b.insert",
            json.dumps({"table": "items", "data": {"data": "B data"}}).encode(),
            timeout=1.0
        )
        id_b = json.loads(insert_b.data.decode())['id']
        
        # Select from each plugin
        select_a = await nats_client.request(
            "rosey.db.row.plugin-a.select",
            json.dumps({"table": "items", "id": id_a}).encode(),
            timeout=1.0
        )
        select_b = await nats_client.request(
            "rosey.db.row.plugin-b.select",
            json.dumps({"table": "items", "id": id_b}).encode(),
            timeout=1.0
        )
        
        result_a = json.loads(select_a.data.decode())
        result_b = json.loads(select_b.data.decode())
        
        # Data should be isolated
        assert result_a['data']['data'] == "A data"
        assert result_b['data']['data'] == "B data"


# ==================== Update & Delete Tests ====================

class TestRowUpdateNATS:
    """Test row update operations via NATS."""
    
    async def test_update_via_nats(self, nats_client, db_service):
        """Test updating a row via NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "value", "type": "integer", "required": False}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": {"name": "original", "value": 10}
            }).encode(),
            timeout=1.0
        )
        insert_result = json.loads(insert_resp.data.decode())
        row_id = insert_result['id']
        
        # Update
        update_resp = await nats_client.request(
            "rosey.db.row.test.update",
            json.dumps({
                "table": "items",
                "id": row_id,
                "data": {"value": 20}
            }).encode(),
            timeout=1.0
        )
        
        update_result = json.loads(update_resp.data.decode())
        assert update_result['success'] is True
        assert update_result['updated'] is True
        assert update_result['id'] == row_id
        
        # Verify update
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({"table": "items", "id": row_id}).encode(),
            timeout=1.0
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['data']['name'] == "original"  # Unchanged
        assert select_result['data']['value'] == 20  # Updated
    
    async def test_update_nonexistent_row(self, nats_client, db_service):
        """Test updating non-existent row returns exists=false."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        response = await nats_client.request(
            "rosey.db.row.test.update",
            json.dumps({
                "table": "items",
                "id": 99999,
                "data": {"name": "test"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is True
        assert result['exists'] is False
    
    async def test_update_immutable_field_rejected(self, nats_client, db_service):
        """Test that updating immutable fields is rejected."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({"table": "items", "data": {"name": "Item"}}).encode(),
            timeout=1.0
        )
        row_id = json.loads(insert_resp.data.decode())['id']
        
        # Try to update id
        response = await nats_client.request(
            "rosey.db.row.test.update",
            json.dumps({
                "table": "items",
                "id": row_id,
                "data": {"id": 999}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
        assert "immutable" in result['error']['message'].lower()
    
    async def test_update_missing_fields_rejected(self, nats_client, db_service):
        """Test that update with missing fields is rejected."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Missing 'data' field
        response = await nats_client.request(
            "rosey.db.row.test.update",
            json.dumps({"table": "items", "id": 1}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "MISSING_FIELD"


class TestRowDeleteNATS:
    """Test row delete operations via NATS."""
    
    async def test_delete_via_nats(self, nats_client, db_service):
        """Test deleting a row via NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({"table": "items", "data": {"name": "Item"}}).encode(),
            timeout=1.0
        )
        row_id = json.loads(insert_resp.data.decode())['id']
        
        # Delete
        delete_resp = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "items", "id": row_id}).encode(),
            timeout=1.0
        )
        
        delete_result = json.loads(delete_resp.data.decode())
        assert delete_result['success'] is True
        assert delete_result['deleted'] is True
        
        # Verify deleted
        select_resp = await nats_client.request(
            "rosey.db.row.test.select",
            json.dumps({"table": "items", "id": row_id}).encode(),
            timeout=1.0
        )
        select_result = json.loads(select_resp.data.decode())
        assert select_result['exists'] is False
    
    async def test_delete_nonexistent_row_idempotent(self, nats_client, db_service):
        """Test that deleting non-existent row is idempotent."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Delete non-existent row
        response = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "items", "id": 99999}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is True
        assert result['deleted'] is False  # No error, just returns False
    
    async def test_delete_twice_idempotent(self, nats_client, db_service):
        """Test that deleting same row twice is idempotent."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Insert
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({"table": "items", "data": {"name": "Item"}}).encode(),
            timeout=1.0
        )
        row_id = json.loads(insert_resp.data.decode())['id']
        
        # First delete
        delete1 = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "items", "id": row_id}).encode(),
            timeout=1.0
        )
        result1 = json.loads(delete1.data.decode())
        assert result1['deleted'] is True
        
        # Second delete (idempotent)
        delete2 = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "items", "id": row_id}).encode(),
            timeout=1.0
        )
        result2 = json.loads(delete2.data.decode())
        assert result2['deleted'] is False  # No error
    
    async def test_delete_missing_fields_rejected(self, nats_client, db_service):
        """Test that delete with missing fields is rejected."""
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {"fields": [{"name": "name", "type": "string", "required": True}]}
            }).encode(),
            timeout=1.0
        )
        
        # Missing 'id' field
        response = await nats_client.request(
            "rosey.db.row.test.delete",
            json.dumps({"table": "items"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(response.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "MISSING_FIELD"


# ==================== Search NATS Tests ====================

class TestRowSearchNATS:
    """Integration tests for row search via NATS."""
    
    async def test_search_all_rows_via_nats(self, nats_client, db_service):
        """Test basic search returning all rows via NATS."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "name", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert data
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": [
                    {"name": "Item 1"},
                    {"name": "Item 2"},
                    {"name": "Item 3"}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Search all
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({"table": "items"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is True
        assert result['count'] == 3
        assert result['truncated'] is False
        assert len(result['rows']) == 3
    
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
            }).encode(),
            timeout=1.0
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
            }).encode(),
            timeout=1.0
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
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is True
        assert result['count'] == 1
        assert result['rows'][0]['category'] == "A"
        assert result['rows'][0]['active'] is True
    
    async def test_search_with_sorting_via_nats(self, nats_client, db_service):
        """Test search with sorting via NATS."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "events",
                "schema": {
                    "fields": [{"name": "value", "type": "integer", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "events",
                "data": [
                    {"value": 30},
                    {"value": 10},
                    {"value": 20}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Search sorted descending
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "events",
                "sort": {"field": "value", "order": "desc"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is True
        values = [row['value'] for row in result['rows']]
        assert values == [30, 20, 10]
    
    async def test_search_with_pagination_via_nats(self, nats_client, db_service):
        """Test paginated search via NATS."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "data",
                "schema": {
                    "fields": [{"name": "val", "type": "integer", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "data",
                "data": [{"val": i} for i in range(10)]
            }).encode(),
            timeout=1.0
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
        assert page1['success'] is True
        assert page1['count'] == 3
        assert page1['truncated'] is True
        assert [r['val'] for r in page1['rows']] == [0, 1, 2]
        
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
        assert page2['success'] is True
        assert page2['count'] == 3
        assert page2['truncated'] is True
        assert [r['val'] for r in page2['rows']] == [3, 4, 5]
    
    async def test_search_empty_results_via_nats(self, nats_client, db_service):
        """Test search with no matches via NATS."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "status", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": [{"status": "active"}]
            }).encode(),
            timeout=1.0
        )
        
        # Search for non-existent
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "filters": {"status": "deleted"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is True
        assert result['count'] == 0
        assert result['rows'] == []
        assert result['truncated'] is False
    
    async def test_search_invalid_filter_field_via_nats(self, nats_client, db_service):
        """Test that invalid filter field returns error via NATS."""
        # Register
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "name", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Search with invalid filter
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "filters": {"invalid_field": "value"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
        assert "non-existent field" in result['error']['message']
    
    async def test_search_invalid_sort_field_via_nats(self, nats_client, db_service):
        """Test that invalid sort field returns error via NATS."""
        # Register
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [{"name": "name", "type": "string", "required": True}]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Search with invalid sort
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "sort": {"field": "invalid_field"}
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
        assert "non-existent field" in result['error']['message']
    
    async def test_search_missing_table_via_nats(self, nats_client, db_service):
        """Test that missing table returns error via NATS."""
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({}).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "MISSING_FIELD"
    
    async def test_search_unregistered_table_via_nats(self, nats_client, db_service):
        """Test that searching unregistered table returns error via NATS."""
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({"table": "nonexistent"}).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "VALIDATION_ERROR"
        assert "not registered" in result['error']['message']
    
    async def test_search_invalid_json_via_nats(self, nats_client, db_service):
        """Test that invalid JSON returns error via NATS."""
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            b"not json",
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is False
        assert result['error']['code'] == "INVALID_JSON"
    
    async def test_search_combined_filters_sort_pagination_via_nats(self, nats_client, db_service):
        """Test search with filters, sorting, and pagination combined via NATS."""
        # Register
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "tasks",
                "schema": {
                    "fields": [
                        {"name": "status", "type": "string", "required": True},
                        {"name": "priority", "type": "integer", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Insert mixed data
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "tasks",
                "data": [
                    {"status": "active", "priority": 1},
                    {"status": "active", "priority": 3},
                    {"status": "done", "priority": 2},
                    {"status": "active", "priority": 2},
                    {"status": "active", "priority": 4}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Search active tasks, sorted by priority desc, first page
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "tasks",
                "filters": {"status": "active"},
                "sort": {"field": "priority", "order": "desc"},
                "limit": 2,
                "offset": 0
            }).encode(),
            timeout=1.0
        )
        
        result = json.loads(search_resp.data.decode())
        assert result['success'] is True
        assert result['count'] == 2
        assert result['truncated'] is True
        priorities = [row['priority'] for row in result['rows']]
        assert priorities == [4, 3]


class TestRowSearchWithOperators:
    """Test row search with MongoDB-style operators via NATS (Sprint 14 Sortie 1)."""
    
    async def test_search_with_gte_operator(self, nats_client, db_service):
        """Test search with $gte operator."""
        # Register schema
        register_resp = await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "scores",
                "schema": {
                    "fields": [
                        {"name": "username", "type": "string", "required": True},
                        {"name": "score", "type": "integer", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        assert json.loads(register_resp.data.decode())['success'] is True
        
        # Insert test data
        insert_resp = await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "scores",
                "data": [
                    {"username": "alice", "score": 50},
                    {"username": "bob", "score": 100},
                    {"username": "charlie", "score": 150},
                    {"username": "diana", "score": 200}
                ]
            }).encode(),
            timeout=1.0
        )
        assert json.loads(insert_resp.data.decode())['success'] is True
        
        # Search with $gte operator
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "scores",
                "filters": {"score": {"$gte": 100}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 3
        assert all(row['score'] >= 100 for row in result['rows'])
        usernames = sorted([row['username'] for row in result['rows']])
        assert usernames == ['bob', 'charlie', 'diana']
    
    async def test_search_with_range_query(self, nats_client, db_service):
        """Test range query (score >= 100 AND score <= 150)."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "scores2",
                "schema": {
                    "fields": [
                        {"name": "score", "type": "integer", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "scores2",
                "data": [
                    {"score": 50},
                    {"score": 100},
                    {"score": 150},
                    {"score": 200}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Range query: 100 <= score <= 150
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "scores2",
                "filters": {"score": {"$gte": 100, "$lte": 150}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 2
        scores = sorted([row['score'] for row in result['rows']])
        assert scores == [100, 150]
    
    async def test_search_with_lt_operator(self, nats_client, db_service):
        """Test search with $lt operator."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "ratings",
                "schema": {
                    "fields": [
                        {"name": "rating", "type": "float", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "ratings",
                "data": [
                    {"rating": 1.5},
                    {"rating": 3.0},
                    {"rating": 4.5},
                    {"rating": 5.0}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Search rating < 4.0
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "ratings",
                "filters": {"rating": {"$lt": 4.0}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 2
        assert all(row['rating'] < 4.0 for row in result['rows'])
    
    async def test_search_with_ne_operator(self, nats_client, db_service):
        """Test search with $ne (not equal) operator."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "users",
                "schema": {
                    "fields": [
                        {"name": "username", "type": "string", "required": True},
                        {"name": "status", "type": "string", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "users",
                "data": [
                    {"username": "alice", "status": "active"},
                    {"username": "bob", "status": "banned"},
                    {"username": "charlie", "status": "active"},
                    {"username": "diana", "status": "suspended"}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Search status != 'banned'
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "users",
                "filters": {"status": {"$ne": "banned"}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 3
        assert all(row['status'] != 'banned' for row in result['rows'])
    
    async def test_search_mixed_simple_and_operator(self, nats_client, db_service):
        """Test search with mix of simple equality and operators."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "category", "type": "string", "required": True},
                        {"name": "price", "type": "integer", "required": True},
                        {"name": "available", "type": "boolean", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": [
                    {"category": "electronics", "price": 50, "available": True},
                    {"category": "electronics", "price": 150, "available": True},
                    {"category": "electronics", "price": 200, "available": False},
                    {"category": "books", "price": 120, "available": True}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Mixed: category='electronics' (simple) AND price >= 100 (operator) AND available=True (simple)
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "filters": {
                    "category": "electronics",
                    "price": {"$gte": 100},
                    "available": True
                }
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 1
        assert result['rows'][0]['price'] == 150
    
    async def test_search_range_operator_on_string_fails(self, nats_client, db_service):
        """Test that range operator on string field fails with clear error."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "names",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        # Try to use $gt on string field (should fail)
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "names",
                "filters": {"name": {"$gt": "alice"}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is False
        assert result['error']['code'] == 'VALIDATION_ERROR'
        assert 'numeric or datetime type' in result['error']['message']
    
    async def test_backward_compatibility_simple_filters(self, nats_client, db_service):
        """Test backward compatibility with Sprint 13 simple equality filters."""
        # Register and insert
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "legacy",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "value", "type": "integer", "required": True}
                    ]
                }
            }).encode(),
            timeout=1.0
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "legacy",
                "data": [
                    {"name": "alpha", "value": 1},
                    {"name": "beta", "value": 2},
                    {"name": "alpha", "value": 3}
                ]
            }).encode(),
            timeout=1.0
        )
        
        # Use old-style simple equality filter (no operators)
        search_resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "legacy",
                "filters": {"name": "alpha"}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(search_resp.data.decode())
        
        assert result['success'] is True
        assert result['count'] == 2
        assert all(row['name'] == 'alpha' for row in result['rows'])

