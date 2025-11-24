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
from .sql_errors import (
    ForbiddenStatementError,
    NamespaceViolationError,
    ParameterError,
    SQLSyntaxError,
    SQLValidationError,
    StackedQueryError,
    StatementType,
    ValidationResult,
)
from .sql_parameter import ParameterBinder
from .sql_validator import QueryValidator
from .sqlite import SQLiteStorage

__all__ = [
    # Storage adapters
    "StorageAdapter",
    "SQLiteStorage",
    # Base errors
    "StorageError",
    "StorageConnectionError",
    "QueryError",
    "MigrationError",
    "IntegrityError",
    # SQL validation (Sprint 17)
    "QueryValidator",
    "ParameterBinder",
    "ValidationResult",
    "StatementType",
    "SQLValidationError",
    "SQLSyntaxError",
    "ForbiddenStatementError",
    "NamespaceViolationError",
    "ParameterError",
    "StackedQueryError",
]
