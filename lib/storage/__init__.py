"""
Storage abstraction layer for bot data persistence.

This module provides an abstract StorageAdapter interface that defines
the contract for all storage implementations (SQLite, PostgreSQL, etc.).
"""

from .adapter import StorageAdapter
from .sqlite import SQLiteStorage
from .errors import (
    StorageError,
    StorageConnectionError,
    QueryError,
    MigrationError,
    IntegrityError
)

__all__ = [
    'StorageAdapter',
    'SQLiteStorage',
    'StorageError',
    'StorageConnectionError',
    'QueryError',
    'MigrationError',
    'IntegrityError',
]
