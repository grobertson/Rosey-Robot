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
    ExecutionError,
    ForbiddenStatementError,
    NamespaceViolationError,
    ParameterError,
    PermissionDeniedError,
    RequestValidationError,
    SQLSyntaxError,
    SQLValidationError,
    StackedQueryError,
    StatementType,
    TimeoutError,
    ValidationResult,
)
from .sql_executor import PreparedStatementExecutor
from .sql_formatter import ResultFormatter
from .sql_handler import SQLExecutionHandler, extract_plugin_from_subject
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
    # SQL execution (Sprint 17, Sortie 2)
    "PreparedStatementExecutor",
    "ResultFormatter",
    "TimeoutError",
    "PermissionDeniedError",
    "ExecutionError",
    # NATS handler (Sprint 17, Sortie 3)
    "SQLExecutionHandler",
    "extract_plugin_from_subject",
    "RequestValidationError",
]
