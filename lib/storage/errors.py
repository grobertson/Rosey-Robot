"""
Storage-specific exceptions.

This module defines the exception hierarchy for storage operations,
enabling precise error handling at different layers of the application.
"""


class StorageError(Exception):
    """
    Base exception for storage errors.

    All storage-related exceptions inherit from this base class,
    allowing catch-all error handling when needed.
    """
    pass


class StorageConnectionError(StorageError):
    """
    Storage connection failed.

    Raised when:
    - Unable to establish database connection
    - Connection is lost unexpectedly
    - Authentication fails
    """
    pass


class QueryError(StorageError):
    """
    Query execution failed.

    Raised when:
    - SQL syntax error
    - Query timeout
    - Constraint violation during query
    """
    pass


class MigrationError(StorageError):
    """
    Schema migration failed.

    Raised when:
    - Migration script fails
    - Schema version mismatch
    - Migration rollback fails
    """
    pass


class IntegrityError(StorageError):
    """
    Data integrity violation.

    Raised when:
    - Foreign key constraint violated
    - Unique constraint violated
    - Check constraint violated
    """
    pass
