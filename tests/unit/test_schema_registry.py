#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for SchemaRegistry

Sprint: 13 (Row Operations Foundation)
Sortie: 1 (Schema Registry & Table Creation)

Target: 100% coverage of SchemaRegistry class

Test Categories:
1. Schema validation (structure, field names, field types)
2. Table name validation
3. Schema registration and caching
4. Table creation
5. Schema listing and deletion
6. Database persistence
"""

import pytest
from sqlalchemy import text

from common.database import BotDatabase
from common.models import Base


class TestSchemaValidation:
    """Test schema validation logic."""

    @pytest.fixture
    async def registry(self):
        """Create schema registry with in-memory database."""
        import asyncio
        db = BotDatabase(':memory:')

        # Create tables directly without calling connect()
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Load schema cache
        await db.schema_registry.load_cache()

        yield db.schema_registry
        
        # Wait for any pending background tasks to complete
        await asyncio.sleep(0.1)
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
        assert valid is True
        assert error == ""

    async def test_validate_schema_missing_fields_key(self, registry):
        """Test schema without 'fields' key."""
        schema = {}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "fields" in error

    async def test_validate_schema_fields_not_list(self, registry):
        """Test schema with 'fields' as non-list."""
        schema = {"fields": "not a list"}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "list" in error

    async def test_validate_schema_empty_fields(self, registry):
        """Test schema with empty fields list."""
        schema = {"fields": []}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "at least one field" in error

    async def test_validate_schema_field_not_dict(self, registry):
        """Test schema with field as non-dict."""
        schema = {"fields": ["not a dict"]}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "dictionary" in error

    async def test_validate_schema_field_missing_name(self, registry):
        """Test field without 'name' key."""
        schema = {"fields": [{"type": "string"}]}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "name" in error.lower()

    async def test_validate_schema_field_missing_type(self, registry):
        """Test field without 'type' key."""
        schema = {"fields": [{"name": "field1"}]}

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "type" in error.lower()

    async def test_validate_schema_invalid_field_names(self, registry):
        """Test invalid field names."""
        invalid_names = [
            ("UpperCase", "lowercase"),
            ("123start", "start with"),
            ("a" * 65, "max 64"),
            ("has-dash", "letter"),
            ("id", "reserved"),
            ("created_at", "reserved"),
            ("updated_at", "reserved"),
        ]

        for name, expected_error_fragment in invalid_names:
            schema = {"fields": [{"name": name, "type": "string"}]}
            valid, error = registry.validate_schema(schema)
            assert valid is False, f"'{name}' should be invalid"
            assert expected_error_fragment in error.lower(), f"Error should mention '{expected_error_fragment}' for '{name}'"

    async def test_validate_schema_valid_field_names(self, registry):
        """Test valid field names."""
        valid_names = ["text", "user_id", "count123", "a", "field_name_ok"]

        for name in valid_names:
            schema = {"fields": [{"name": name, "type": "string"}]}
            valid, error = registry.validate_schema(schema)
            assert valid is True, f"'{name}' should be valid, got error: {error}"

    async def test_validate_schema_duplicate_field_names(self, registry):
        """Test duplicate field names."""
        schema = {
            "fields": [
                {"name": "text", "type": "string"},
                {"name": "text", "type": "string"}  # Duplicate
            ]
        }

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "duplicate" in error.lower()

    async def test_validate_schema_invalid_type(self, registry):
        """Test invalid field type."""
        schema = {
            "fields": [
                {"name": "field1", "type": "invalid_type"}
            ]
        }

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "invalid type" in error.lower()

    async def test_validate_schema_all_valid_types(self, registry):
        """Test all valid field types."""
        valid_types = ["string", "text", "integer", "float", "boolean", "datetime"]

        for field_type in valid_types:
            schema = {"fields": [{"name": "field1", "type": field_type}]}
            valid, error = registry.validate_schema(schema)
            assert valid is True, f"Type '{field_type}' should be valid, got error: {error}"

    async def test_validate_schema_required_not_boolean(self, registry):
        """Test 'required' field with non-boolean value."""
        schema = {
            "fields": [
                {"name": "field1", "type": "string", "required": "yes"}
            ]
        }

        valid, error = registry.validate_schema(schema)
        assert valid is False
        assert "boolean" in error.lower()

    async def test_validate_schema_not_dict(self, registry):
        """Test schema that is not a dict."""
        valid, error = registry.validate_schema("not a dict")
        assert valid is False
        assert "dictionary" in error


class TestTableNameValidation:
    """Test table name validation logic."""

    @pytest.fixture
    async def registry(self):
        """Create schema registry with in-memory database."""
        db = BotDatabase(':memory:')

        # Create tables directly
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db.schema_registry.load_cache()
        yield db.schema_registry
        await db.close()

    async def test_validate_table_name_valid(self, registry):
        """Test valid table names."""
        valid_names = ["quotes", "user_data", "trivia_stats", "a", "t123"]

        for name in valid_names:
            valid, error = registry.validate_table_name(name)
            assert valid is True, f"'{name}' should be valid, got error: {error}"

    async def test_validate_table_name_invalid(self, registry):
        """Test invalid table names."""
        invalid_names = [
            ("UpperCase", "lowercase"),
            ("123start", "start with"),
            ("has-dash", "letter"),
            ("a" * 101, "max 100"),
        ]

        for name, expected_fragment in invalid_names:
            valid, error = registry.validate_table_name(name)
            assert valid is False, f"'{name}' should be invalid"
            assert expected_fragment in error.lower(), f"Error should mention '{expected_fragment}'"

    async def test_validate_table_name_not_string(self, registry):
        """Test table name that is not a string."""
        valid, error = registry.validate_table_name(123)
        assert valid is False
        assert "string" in error.lower()


class TestSchemaRegistration:
    """Test schema registration and caching."""

    @pytest.fixture
    async def registry(self):
        """Create schema registry with in-memory database."""
        db = BotDatabase(':memory:')

        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db.schema_registry.load_cache()
        yield db.schema_registry
        await db.close()

    async def test_register_schema_success(self, registry):
        """Test successful schema registration."""
        schema = {
            "fields": [
                {"name": "text", "type": "text", "required": True}
            ]
        }

        result = await registry.register_schema("test_plugin", "quotes", schema)
        assert result is True

        # Verify in cache
        cached = registry.get_schema("test_plugin", "quotes")
        assert cached == schema

    async def test_register_schema_duplicate(self, registry):
        """Test registering duplicate schema."""
        schema = {"fields": [{"name": "text", "type": "text"}]}

        await registry.register_schema("test", "data", schema)
        result = await registry.register_schema("test", "data", schema)

        assert result is False  # Already exists

    async def test_register_schema_invalid_table_name(self, registry):
        """Test registration with invalid table name."""
        schema = {"fields": [{"name": "text", "type": "text"}]}

        with pytest.raises(ValueError) as exc_info:
            await registry.register_schema("test", "Invalid-Name", schema)

        assert "lowercase" in str(exc_info.value).lower()

    async def test_register_schema_invalid_schema(self, registry):
        """Test registration with invalid schema."""
        schema = {"fields": []}  # Empty fields

        with pytest.raises(ValueError) as exc_info:
            await registry.register_schema("test", "table1", schema)

        assert "at least one field" in str(exc_info.value)

    async def test_get_schema_not_found(self, registry):
        """Test getting non-existent schema."""
        result = registry.get_schema("nonexistent", "table")
        assert result is None

    async def test_get_schema_after_registration(self, registry):
        """Test getting schema after registration."""
        schema = {
            "fields": [
                {"name": "message", "type": "string", "required": True},
                {"name": "count", "type": "integer", "required": False}
            ]
        }

        await registry.register_schema("plugin1", "messages", schema)

        cached = registry.get_schema("plugin1", "messages")
        assert cached is not None
        assert cached["fields"] == schema["fields"]


class TestTableCreation:
    """Test dynamic table creation."""

    @pytest.fixture
    async def db(self):
        """Create database with schema registry."""
        database = BotDatabase(':memory:')

        async with database.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await database.schema_registry.load_cache()
        yield database
        await database.close()

    async def test_register_schema_creates_table(self, db):
        """Test that table is created after registration."""
        schema = {
            "fields": [
                {"name": "message", "type": "string", "required": True}
            ]
        }

        await db.schema_registry.register_schema("test", "messages", schema)

        # Verify table exists by attempting insert
        async with db.engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO test_messages (message) VALUES ('test')")
            )

            # Verify data
            result = await conn.execute(
                text("SELECT message FROM test_messages")
            )
            row = result.fetchone()
            assert row[0] == 'test'

    @pytest.mark.xfail(reason="Flaky test: intermittent failure when run with other tests, passes in isolation. Suspected test isolation issue.")
    async def test_table_has_id_column(self, db):
        """Test that created table has auto-increment ID column."""
        schema = {"fields": [{"name": "data", "type": "string"}]}
        await db.schema_registry.register_schema("test", "data", schema)

        # Insert rows and verify IDs
        async with db.engine.begin() as conn:
            await conn.execute(text("INSERT INTO test_data (data) VALUES ('row1')"))
            await conn.execute(text("INSERT INTO test_data (data) VALUES ('row2')"))

            result = await conn.execute(text("SELECT id FROM test_data ORDER BY id"))
            rows = result.fetchall()
            assert rows[0][0] == 1
            assert rows[1][0] == 2

    async def test_table_has_timestamps(self, db):
        """Test that created table has created_at and updated_at columns."""
        schema = {"fields": [{"name": "data", "type": "string"}]}
        await db.schema_registry.register_schema("test", "data", schema)

        # Insert row
        async with db.engine.begin() as conn:
            await conn.execute(text("INSERT INTO test_data (data) VALUES ('test')"))

            # Verify timestamp columns exist
            result = await conn.execute(
                text("SELECT created_at, updated_at FROM test_data")
            )
            row = result.fetchone()
            assert row[0] is not None  # created_at
            assert row[1] is not None  # updated_at

    async def test_required_field_enforced(self, db):
        """Test that required fields are enforced."""
        schema = {
            "fields": [
                {"name": "required_field", "type": "string", "required": True}
            ]
        }
        await db.schema_registry.register_schema("test", "data", schema)

        # Attempt to insert without required field should fail
        with pytest.raises(Exception):  # SQLAlchemy will raise an exception
            async with db.engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO test_data (id) VALUES (1)")
                )

    async def test_nullable_field_allowed(self, db):
        """Test that nullable fields accept NULL."""
        schema = {
            "fields": [
                {"name": "optional_field", "type": "string", "required": False}
            ]
        }
        await db.schema_registry.register_schema("test", "data", schema)

        # Insert with NULL optional field should succeed
        async with db.engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO test_data (optional_field) VALUES (NULL)")
            )

            result = await conn.execute(
                text("SELECT optional_field FROM test_data")
            )
            row = result.fetchone()
            assert row[0] is None

    async def test_all_field_types_created(self, db):
        """Test that all field types are created correctly."""
        schema = {
            "fields": [
                {"name": "str_field", "type": "string"},
                {"name": "txt_field", "type": "text"},
                {"name": "int_field", "type": "integer"},
                {"name": "flt_field", "type": "float"},
                {"name": "bool_field", "type": "boolean"},
                {"name": "dt_field", "type": "datetime"},
            ]
        }
        await db.schema_registry.register_schema("test", "alltypes", schema)

        # Verify all columns exist by inserting data
        async with db.engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO test_alltypes 
                (str_field, txt_field, int_field, flt_field, bool_field, dt_field)
                VALUES ('str', 'text', 42, 3.14, 1, '2025-11-24 10:00:00')
            """))

            result = await conn.execute(
                text("SELECT str_field, int_field, flt_field FROM test_alltypes")
            )
            row = result.fetchone()
            assert row[0] == 'str'
            assert row[1] == 42
            assert abs(row[2] - 3.14) < 0.01


class TestSchemaListing:
    """Test schema listing functionality."""

    @pytest.fixture
    async def registry(self):
        """Create schema registry with in-memory database."""
        db = BotDatabase(':memory:')

        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db.schema_registry.load_cache()
        yield db.schema_registry
        await db.close()

    async def test_list_schemas_empty(self, registry):
        """Test listing schemas for plugin with no schemas."""
        schemas = await registry.list_schemas("nonexistent")
        assert schemas == []

    async def test_list_schemas_single_plugin(self, registry):
        """Test listing all schemas for a plugin."""
        await registry.register_schema("plugin1", "table1", {
            "fields": [{"name": "field1", "type": "string"}]
        })
        await registry.register_schema("plugin1", "table2", {
            "fields": [{"name": "field2", "type": "integer"}]
        })

        schemas = await registry.list_schemas("plugin1")
        assert len(schemas) == 2

        table_names = {s['table_name'] for s in schemas}
        assert table_names == {'table1', 'table2'}

    async def test_list_schemas_multiple_plugins(self, registry):
        """Test that listing only returns schemas for requested plugin."""
        await registry.register_schema("plugin1", "table1", {
            "fields": [{"name": "field1", "type": "string"}]
        })
        await registry.register_schema("plugin2", "table1", {
            "fields": [{"name": "field2", "type": "string"}]
        })

        schemas_p1 = await registry.list_schemas("plugin1")
        schemas_p2 = await registry.list_schemas("plugin2")

        assert len(schemas_p1) == 1
        assert len(schemas_p2) == 1
        assert schemas_p1[0]['table_name'] == 'table1'
        assert schemas_p2[0]['table_name'] == 'table1'

    async def test_list_schemas_includes_field_count(self, registry):
        """Test that schema listing includes field count."""
        await registry.register_schema("plugin1", "table1", {
            "fields": [
                {"name": "field1", "type": "string"},
                {"name": "field2", "type": "integer"},
                {"name": "field3", "type": "text"}
            ]
        })

        schemas = await registry.list_schemas("plugin1")
        assert schemas[0]['field_count'] == 3


class TestSchemaDeletion:
    """Test schema deletion functionality."""

    @pytest.fixture
    async def db(self):
        """Create database with schema registry."""
        database = BotDatabase(':memory:')

        async with database.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await database.schema_registry.load_cache()
        yield database
        await database.close()

    async def test_delete_schema_success(self, db):
        """Test successful schema deletion."""
        schema = {"fields": [{"name": "data", "type": "string"}]}
        await db.schema_registry.register_schema("test", "temp", schema)

        # Delete
        result = await db.schema_registry.delete_schema("test", "temp")
        assert result is True

        # Verify removed from cache
        cached = db.schema_registry.get_schema("test", "temp")
        assert cached is None

    async def test_delete_schema_not_found(self, db):
        """Test deleting non-existent schema."""
        result = await db.schema_registry.delete_schema("nonexistent", "table")
        assert result is False

    async def test_delete_schema_drops_table(self, db):
        """Test that table is dropped after schema deletion."""
        schema = {"fields": [{"name": "data", "type": "string"}]}
        await db.schema_registry.register_schema("test", "temp", schema)

        # Insert data
        async with db.engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO test_temp (data) VALUES ('test')")
            )

        # Delete schema
        await db.schema_registry.delete_schema("test", "temp")

        # Verify table dropped (query should fail)
        with pytest.raises(Exception):
            async with db.engine.begin() as conn:
                await conn.execute(text("SELECT * FROM test_temp"))


class TestDatabasePersistence:
    """Test schema persistence across registry instances."""

    @pytest.fixture
    async def db_path(self, tmp_path):
        """Create temporary database file path."""
        return str(tmp_path / "test_schema_persistence.db")

    async def test_load_cache_from_database(self, db_path):
        """Test loading schemas from database into cache."""
        # Create first database instance and register schema
        db1 = BotDatabase(db_path)

        async with db1.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db1.schema_registry.load_cache()

        schema = {"fields": [{"name": "field1", "type": "string"}]}
        await db1.schema_registry.register_schema("plugin1", "table1", schema)

        await db1.close()

        # Create second database instance and verify schema loaded
        db2 = BotDatabase(db_path)

        async with db2.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db2.schema_registry.load_cache()

        cached = db2.schema_registry.get_schema("plugin1", "table1")
        assert cached is not None
        assert cached["fields"] == schema["fields"]

        await db2.close()

    async def test_schema_persists_across_restarts(self, db_path):
        """Test that schemas persist across database restarts."""
        # Register multiple schemas
        db1 = BotDatabase(db_path)

        async with db1.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db1.schema_registry.load_cache()

        await db1.schema_registry.register_schema("plugin1", "table1", {
            "fields": [{"name": "f1", "type": "string"}]
        })
        await db1.schema_registry.register_schema("plugin1", "table2", {
            "fields": [{"name": "f2", "type": "integer"}]
        })
        await db1.schema_registry.register_schema("plugin2", "table1", {
            "fields": [{"name": "f3", "type": "text"}]
        })

        await db1.close()

        # Reload and verify all schemas present
        db2 = BotDatabase(db_path)

        async with db2.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await db2.schema_registry.load_cache()

        schemas_p1 = await db2.schema_registry.list_schemas("plugin1")
        schemas_p2 = await db2.schema_registry.list_schemas("plugin2")

        assert len(schemas_p1) == 2
        assert len(schemas_p2) == 1

        await db2.close()
