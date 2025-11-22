"""
Storage abstraction layer for bot data persistence.

This module provides an abstract StorageAdapter interface that defines
the contract for all storage implementations (SQLite, PostgreSQL, etc.).
"""

from .adapter import StorageAdapter
from .errors import (
    IntegrityError,
    MigrationError,
    QueryError,
    StorageConnectionError,
    StorageError,
)
from .sqlite import SQLiteStorage

__all__ = [
    'StorageAdapter',
    'SQLiteStorage',
    'StorageError',
    'StorageConnectionError',
    'QueryError',
    'MigrationError',
    'IntegrityError',
]
