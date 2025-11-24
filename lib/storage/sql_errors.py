"""
SQL validation error types and result structures.

This module defines the exception hierarchy and result types for SQL query
validation, providing structured error information for debugging and security.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .errors import StorageError


class StatementType(Enum):
    """SQL statement types for classification."""

    # Allowed DML statements
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

    # Forbidden DDL/admin statements
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    TRUNCATE = "TRUNCATE"
    PRAGMA = "PRAGMA"
    ATTACH = "ATTACH"
    DETACH = "DETACH"

    # Unknown/unparseable
    UNKNOWN = "UNKNOWN"


class SQLValidationError(StorageError):
    """
    Base class for SQL validation errors.

    All SQL validation errors include a code, message, and optional details
    dict for structured error information without leaking schema details.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            code: Error code (e.g., "NAMESPACE_VIOLATION")
            message: Human-readable error message
            details: Optional dict of additional context
        """
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class SQLSyntaxError(SQLValidationError):
    """
    SQL syntax is invalid or unparseable.

    Raised when:
    - Query is empty or whitespace-only
    - sqlparse fails to parse the query
    - Query structure is malformed
    """

    pass


class ForbiddenStatementError(SQLValidationError):
    """
    Statement type not allowed for execution.

    Raised when:
    - DDL statements (CREATE, DROP, ALTER) detected
    - Admin statements (PRAGMA, ATTACH, DETACH) detected
    - TRUNCATE or other destructive operations detected
    """

    pass


class NamespaceViolationError(SQLValidationError):
    """
    Query accesses tables outside allowed namespace.

    Raised when:
    - Table name doesn't match plugin__{table} pattern
    - Query accesses system tables (sqlite_*)
    - Cross-plugin access attempted without permission
    """

    pass


class ParameterError(SQLValidationError):
    """
    Parameter count or format mismatch.

    Raised when:
    - Query uses $N but fewer params provided
    - Invalid placeholder format detected
    - Parameter index out of bounds
    """

    pass


class StackedQueryError(ForbiddenStatementError):
    """
    Multiple SQL statements detected (SQL injection vector).

    Raised when:
    - Semicolon found in query (not at end, not in string)
    - Multiple statements concatenated
    """

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        """Initialize with STACKED_QUERIES code."""
        super().__init__("STACKED_QUERIES", message, details)


@dataclass
class ValidationResult:
    """
    Result of SQL query validation.

    Contains validation outcome, detected statement type, extracted
    table names, placeholder information, and any warnings or errors.
    """

    valid: bool
    """Whether the query passed all validation checks."""

    statement_type: StatementType
    """Detected SQL statement type (SELECT, INSERT, etc.)."""

    tables: set[str] = field(default_factory=set)
    """Set of table names referenced in the query."""

    placeholders: list[int] = field(default_factory=list)
    """List of $N placeholder numbers found (in order of appearance)."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal validation warnings (e.g., inline literals)."""

    error: Optional[SQLValidationError] = None
    """Validation error if valid=False, None otherwise."""

    normalized_query: Optional[str] = None
    """Query with normalized whitespace (for caching/comparison)."""

    def __bool__(self) -> bool:
        """Allow using result in boolean context: if result: ..."""
        return self.valid
