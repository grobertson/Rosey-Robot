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
