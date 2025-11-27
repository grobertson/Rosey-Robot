"""
SQL Result Formatter for standardized query result formatting.

This module provides the ResultFormatter class which converts SQL execution
results into JSON-serializable format with proper metadata and error handling.
"""

import base64
import logging
from typing import Any

from .sql_errors import (
    ExecutionError,
    ParameterError,
    PermissionDeniedError,
    SQLValidationError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


class ResultFormatter:
    """
    Format SQL execution results for NATS response.

    Converts raw query results into standardized JSON-serializable format
    with proper metadata. Also handles error formatting for consistent
    error responses across all SQL operations.

    Features:
    - JSON serialization of all result types
    - BLOB to base64 conversion
    - NULL value handling
    - Boolean normalization
    - Error code mapping
    - Execution metadata inclusion

    Example:
        >>> formatter = ResultFormatter()
        >>> result = formatter.format_success(
        ...     rows=[{"id": 1, "name": "Alice"}],
        ...     row_count=1,
        ...     execution_time_ms=15.3,
        ...     truncated=False
        ... )
        >>> print(result)
        {'rows': [{'id': 1, 'name': 'Alice'}], 'row_count': 1, ...}
    """

    # Error code mapping for known exception types
    ERROR_CODE_MAP: dict[type, str] = {
        TimeoutError: "TIMEOUT",
        PermissionDeniedError: "PERMISSION_DENIED",
        ExecutionError: "EXECUTION_ERROR",
        ParameterError: "PARAM_ERROR",
    }

    def format_success(
        self,
        rows: list[dict[str, Any]],
        row_count: int,
        execution_time_ms: float,
        truncated: bool = False,
    ) -> dict[str, Any]:
        """
        Format successful query result.

        Converts all values in rows to JSON-serializable types:
        - bytes → base64-encoded string
        - None → null (no change needed)
        - bool → true/false (no change needed)
        - int/float/str → as-is

        Args:
            rows: List of result row dicts
            row_count: Number of rows returned or affected
            execution_time_ms: Query execution duration in milliseconds
            truncated: Whether results were truncated at max_rows

        Returns:
            Formatted result dict ready for JSON serialization

        Example:
            >>> formatter = ResultFormatter()
            >>> result = formatter.format_success(
            ...     rows=[{"id": 1, "data": b"binary"}],
            ...     row_count=1,
            ...     execution_time_ms=10.5,
            ...     truncated=False
            ... )
            >>> result["rows"][0]["data"]  # base64 encoded
            'YmluYXJ5'
        """
        # Ensure all values are JSON-serializable
        serializable_rows = []
        for row in rows:
            serializable_row = {}
            for key, value in row.items():
                serializable_row[key] = self._make_serializable(value)
            serializable_rows.append(serializable_row)

        return {
            "rows": serializable_rows,
            "row_count": row_count,
            "execution_time_ms": execution_time_ms,
            "truncated": truncated,
        }

    def format_error(
        self,
        error: Exception,
        query: str,
        params: list[Any],
        plugin: str,
    ) -> dict[str, Any]:
        """
        Format query execution error.

        Maps exceptions to standard error codes and formats a consistent
        error response with context for debugging.

        Args:
            error: Exception that occurred
            query: SQL query that failed (will be truncated in response)
            params: Query parameters (count included, not values)
            plugin: Plugin name

        Returns:
            Formatted error dict with code, message, and details

        Example:
            >>> formatter = ResultFormatter()
            >>> error = TimeoutError("Query exceeded timeout", timeout_ms=10000)
            >>> result = formatter.format_error(
            ...     error=error,
            ...     query="SELECT * FROM large_table",
            ...     params=["param1"],
            ...     plugin="test-plugin"
            ... )
            >>> result["error"]
            'TIMEOUT'
        """
        # Determine error code
        error_code = self._get_error_code(error)

        # Build error details
        details: dict[str, Any] = {
            "plugin": plugin,
            "query_preview": self._truncate_query(query),
            "param_count": len(params),
            "error_type": type(error).__name__,
        }

        # Add specific details based on error type
        if isinstance(error, TimeoutError):
            details["timeout_ms"] = error.timeout_ms
        elif isinstance(error, PermissionDeniedError):
            details["permission"] = error.required_permission
        elif isinstance(error, SQLValidationError):
            if error.details:
                details["validation_details"] = error.details

        return {
            "error": error_code,
            "message": str(error),
            "details": details,
        }

    def _make_serializable(self, value: Any) -> Any:
        """
        Convert value to JSON-serializable type.

        Args:
            value: Any Python value

        Returns:
            JSON-serializable value

        Type conversions:
            - None → None (null in JSON)
            - bytes → base64 string
            - bool → bool (true/false in JSON)
            - int/float → number
            - str → string
            - other → str(value)
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            return base64.b64encode(value).decode("utf-8")

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):
            return value

        # Fallback: convert to string representation
        logger.debug(
            "Converting non-standard type to string: %s",
            type(value).__name__,
        )
        return str(value)

    def _get_error_code(self, error: Exception) -> str:
        """
        Map exception to error code string.

        Args:
            error: Exception instance

        Returns:
            Error code string (e.g., "TIMEOUT", "PERMISSION_DENIED")
        """
        # Check known error types
        for error_class, code in self.ERROR_CODE_MAP.items():
            if isinstance(error, error_class):
                return code

        # Check if it's any SQLValidationError subclass
        if isinstance(error, SQLValidationError):
            return error.code

        # Default for unknown errors
        return "UNKNOWN_ERROR"

    def _truncate_query(self, query: str, max_length: int = 200) -> str:
        """
        Truncate query string for error reporting.

        Args:
            query: SQL query string
            max_length: Maximum length before truncation

        Returns:
            Query string, truncated with "..." if too long
        """
        if len(query) <= max_length:
            return query
        return query[:max_length] + "..."
