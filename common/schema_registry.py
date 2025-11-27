#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema Registry for Plugin Row Storage
=======================================

Manages plugin table schemas with in-memory caching.

Sprint: 13 (Row Operations Foundation)
Sortie: 1 (Schema Registry & Table Creation)

Usage:
    from common.schema_registry import SchemaRegistry
    from common.database import BotDatabase

    db = BotDatabase("sqlite:///bot_data.db")
    registry = SchemaRegistry(db)
    await registry.load_cache()

    # Register schema
    schema = {
        "fields": [
            {"name": "text", "type": "text", "required": True},
            {"name": "author", "type": "string", "required": False}
        ]
    }
    await registry.register_schema("quote-db", "quotes", schema)

    # Get schema
    schema = registry.get_schema("quote-db", "quotes")
"""

import logging
import re
import time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    select,
)

from common.models import PluginTableSchema


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
                return False, f"Field name must be string, got {type(name).__name__}"

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
            True if registered successfully, False if already exists

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
        self.logger.info(f"DEBUG: Storing schema in database: {plugin_name}.{table_name}")
        now = int(time.time())
        async with self.db.session_factory() as session:
            schema_model = PluginTableSchema(
                plugin_name=plugin_name,
                table_name=table_name,
                version=1,
                created_at=now,
                updated_at=now
            )
            schema_model.set_schema(schema)

            session.add(schema_model)
            await session.commit()
            self.logger.info(f"DEBUG: Schema stored in database successfully")

        # Create table
        self.logger.info(f"DEBUG: Creating table: {plugin_name}_{table_name}")
        await self._create_table(plugin_name, table_name, schema)
        self.logger.info(f"DEBUG: Table created successfully")

        # Update cache
        self._cache[key] = schema
        self.logger.info(f"DEBUG: Cache updated, key={key}")

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
                Column(field['name'], col_type, nullable=nullable)  # type: ignore[arg-type]
            )

        # Add timestamps
        columns.append(
            Column('created_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')  # type: ignore[arg-type]
        )
        columns.append(
            Column('updated_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')  # type: ignore[arg-type]
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
            True if deleted, False if not found
        """
        key = (plugin_name, table_name)
        if key not in self._cache:
            return False

        # Drop table
        full_table_name = f"{plugin_name}_{table_name}"
        async with self.db.engine.begin() as conn:
            from sqlalchemy import text
            await conn.execute(text(f"DROP TABLE IF EXISTS {full_table_name}"))

        # Delete from database
        async with self.db.session_factory() as session:
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
