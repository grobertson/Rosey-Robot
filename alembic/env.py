"""
Alembic Migration Environment for Rosey Bot
============================================

This module configures Alembic to:
1. Load database URL from config.json (not hardcoded)
2. Support async SQLAlchemy operations
3. Import all ORM models for autogeneration
4. Handle both online (async) and offline migrations

Usage:
    alembic revision --autogenerate -m "Description"
    alembic upgrade head
    alembic downgrade -1
"""

import asyncio
import json
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import all models for autogeneration
from common.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogeneration
target_metadata = Base.metadata


# ============================================================================
# Database URL Loading
# ============================================================================

def load_database_url_from_config() -> str:
    """
    Load database URL from config.json.

    Tries (in order):
    1. ROSEY_DATABASE_URL environment variable
    2. config.json (database_url field)
    3. config-test.json (fallback for tests)
    4. Default SQLite (bot_data.db)

    Returns:
        Database URL (e.g., 'sqlite+aiosqlite:///bot_data.db')
    """
    # 1. Check environment variable (highest priority)
    if 'ROSEY_DATABASE_URL' in os.environ:
        return os.environ['ROSEY_DATABASE_URL']

    # 2. Check config.json
    config_paths = [
        Path('config.json'),
        Path('config-test.json'),
        Path('../config.json'),  # For when running from alembic/
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Check for database_url (v0.6.0+)
            if 'database_url' in config_data:
                url = config_data['database_url']
                # Ensure async driver
                if url.startswith('sqlite:///'):
                    url = url.replace('sqlite:///', 'sqlite+aiosqlite:///')
                elif url.startswith('postgresql://'):
                    url = url.replace('postgresql://', 'postgresql+asyncpg://')
                return url

            # Fallback: check for database path (v0.5.0)
            if 'database' in config_data:
                db_path = config_data['database']
                return f'sqlite+aiosqlite:///{db_path}'

    # 3. Default fallback
    return 'sqlite+aiosqlite:///bot_data.db'


# Load database URL
database_url = load_database_url_from_config()
config.set_main_option('sqlalchemy.url', database_url)


# ============================================================================
# Migration Functions
# ============================================================================

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect type changes
        compare_server_default=True,  # Detect default changes
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with an active connection.

    Args:
        connection: Active database connection
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Detect type changes
        compare_server_default=True,  # Detect default changes
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (async).

    Wrapper to run async migrations from sync context.
    """
    asyncio.run(run_async_migrations())


# ============================================================================
# Main Entry Point
# ============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

