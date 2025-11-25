"""
SQL Executor for parameterized SQL query execution.

This module provides the PreparedStatementExecutor class which executes
validated SQL queries using SQLite prepared statements, ensuring safety
against SQL injection while supporting timeout and row limit enforcement.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from .sql_errors import (
    ExecutionError,
    PermissionDeniedError,
    TimeoutError,
)


logger = logging.getLogger(__name__)


class PreparedStatementExecutor:
    """
    Execute SQL queries using prepared statements.

    This executor safely executes validated SQL queries with parameter binding,
    timeout enforcement, and row limit enforcement. It NEVER uses string
    interpolation - all queries are executed as prepared statements.

    Features:
    - Prepared statement execution (no SQL injection possible)
    - Configurable timeout enforcement via asyncio.timeout
    - Row limit enforcement with truncation detection
    - Write permission control (allow_write flag)
    - Slow query logging
    - Automatic transaction handling for write operations

    Example:
        >>> executor = PreparedStatementExecutor(database)
        >>> result = await executor.execute(
        ...     plugin="quote-db",
        ...     query="SELECT * FROM quote_db__quotes WHERE author = ?",
        ...     params=("Einstein",),
        ...     timeout_ms=5000,
        ...     max_rows=100
        ... )
        >>> print(result["row_count"])
        42
    """

    # Default configuration
    DEFAULT_TIMEOUT_MS: int = 10000  # 10 seconds
    DEFAULT_MAX_ROWS: int = 10000
    SLOW_QUERY_THRESHOLD_MS: int = 500

    # Bounds for configuration
    MIN_TIMEOUT_MS: int = 100
    MAX_TIMEOUT_MS: int = 30000
    MIN_MAX_ROWS: int = 1
    MAX_MAX_ROWS: int = 100000

    def __init__(
        self,
        database: Any,
        slow_query_threshold_ms: int = SLOW_QUERY_THRESHOLD_MS,
    ) -> None:
        """
        Initialize executor.

        Args:
            database: Database instance (must support async context manager
                     and execute() method)
            slow_query_threshold_ms: Queries taking longer than this are logged
                                    as warnings (default 500ms)
        """
        self.database = database
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.logger = logging.getLogger(__name__)

    async def execute(
        self,
        plugin: str,
        query: str,
        params: tuple[Any, ...] = (),
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_rows: int = DEFAULT_MAX_ROWS,
        allow_write: bool = False,
    ) -> dict[str, Any]:
        """
        Execute SQL query using prepared statement.

        This method executes a SQL query with ? placeholders using SQLite's
        prepared statement mechanism. Parameters are bound safely by the
        database driver, preventing SQL injection.

        Args:
            plugin: Plugin name (for logging and potential connection routing)
            query: SQL query with ? placeholders (SQLite format)
            params: Parameter tuple matching ? placeholders in order
            timeout_ms: Query timeout in milliseconds (100-30000, default 10000)
            max_rows: Maximum rows to return for SELECT (1-100000, default 10000)
            allow_write: Whether write operations (INSERT/UPDATE/DELETE) allowed

        Returns:
            Dict containing:
                - rows: List of result dicts (SELECT) or empty list (write ops)
                - row_count: Number of rows returned or affected
                - execution_time_ms: Query duration in milliseconds
                - truncated: Whether results were truncated at max_rows

        Raises:
            TimeoutError: Query exceeded timeout limit
            PermissionDeniedError: Write operation without allow_write=True
            ExecutionError: Database error during execution

        Example:
            >>> result = await executor.execute(
            ...     plugin="analytics-db",
            ...     query="SELECT * FROM analytics_db__events WHERE user_id = ?",
            ...     params=("alice",),
            ...     timeout_ms=5000,
            ...     max_rows=1000
            ... )
            >>> print(f"Found {result['row_count']} events")
        """
        # Validate bounds
        timeout_ms = max(self.MIN_TIMEOUT_MS, min(timeout_ms, self.MAX_TIMEOUT_MS))
        max_rows = max(self.MIN_MAX_ROWS, min(max_rows, self.MAX_MAX_ROWS))

        # Detect statement type
        stmt_type = self._detect_statement_type(query)

        # Check write permission
        if stmt_type in ("INSERT", "UPDATE", "DELETE") and not allow_write:
            raise PermissionDeniedError(
                f"{stmt_type} operations require allow_write=True",
                required_permission="allow_write",
                details={
                    "statement_type": stmt_type,
                    "plugin": plugin,
                },
            )

        # Start timing
        start_time = time.perf_counter()

        try:
            # Execute with timeout
            timeout_sec = timeout_ms / 1000.0

            async with asyncio.timeout(timeout_sec):
                result = await self._execute_query(
                    plugin=plugin,
                    query=query,
                    params=params,
                    stmt_type=stmt_type,
                    max_rows=max_rows,
                )

        except asyncio.TimeoutError:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Query timeout after %.2fms (limit: %dms)",
                execution_time_ms,
                timeout_ms,
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "timeout_ms": timeout_ms,
                    "execution_time_ms": execution_time_ms,
                },
            )
            raise TimeoutError(
                f"Query execution exceeded timeout of {timeout_ms}ms",
                timeout_ms=timeout_ms,
                details={
                    "plugin": plugin,
                    "execution_time_ms": round(execution_time_ms, 2),
                },
            )

        except PermissionDeniedError:
            # Re-raise permission errors as-is
            raise

        except TimeoutError:
            # Re-raise our timeout errors as-is
            raise

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            # Translate to ExecutionError
            translated = self._translate_error(e)
            self.logger.error(
                "Query execution error: %s",
                str(e),
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "execution_time_ms": execution_time_ms,
                },
            )
            raise translated from e

        # Calculate final execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Log slow queries
        if execution_time_ms > self.slow_query_threshold_ms:
            self.logger.warning(
                "Slow query detected: %.2fms (threshold: %dms)",
                execution_time_ms,
                self.slow_query_threshold_ms,
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "execution_time_ms": execution_time_ms,
                    "threshold_ms": self.slow_query_threshold_ms,
                    "row_count": result["row_count"],
                },
            )

        # Add execution time to result
        result["execution_time_ms"] = round(execution_time_ms, 2)

        return result

    async def _execute_query(
        self,
        plugin: str,
        query: str,
        params: tuple[Any, ...],
        stmt_type: str,
        max_rows: int,
    ) -> dict[str, Any]:
        """
        Execute query and fetch results.

        Args:
            plugin: Plugin name
            query: SQL query with ? placeholders
            params: Parameter tuple
            stmt_type: Statement type (SELECT, INSERT, etc.)
            max_rows: Maximum rows to return

        Returns:
            Dict with rows, row_count, truncated (no execution_time_ms yet)
        """
        async with self.database._get_session() as session:
            from sqlalchemy import text

            # Execute prepared statement
            result = await session.execute(text(query), dict(enumerate(params)))

            if stmt_type == "SELECT" or stmt_type == "WITH":
                # Fetch results with row limit
                rows: list[dict[str, Any]] = []
                truncated = False
                count = 0

                # Fetch all rows and convert
                all_rows = result.fetchall()

                for row in all_rows:
                    if count >= max_rows:
                        truncated = True
                        self.logger.warning(
                            "Query results truncated at %d rows",
                            max_rows,
                            extra={
                                "plugin": plugin,
                                "query_hash": hash(query),
                                "max_rows": max_rows,
                                "actual_rows": len(all_rows),
                            },
                        )
                        break

                    # Convert row to dict using column names
                    row_dict = dict(row._mapping)
                    rows.append(row_dict)
                    count += 1

                return {
                    "rows": rows,
                    "row_count": count,
                    "truncated": truncated,
                }

            else:
                # Write operation (INSERT, UPDATE, DELETE)
                await session.commit()

                return {
                    "rows": [],
                    "row_count": result.rowcount,
                    "truncated": False,
                }

    def _detect_statement_type(self, query: str) -> str:
        """
        Detect SQL statement type from query string.

        Args:
            query: SQL query string

        Returns:
            Statement type string (SELECT, INSERT, UPDATE, DELETE, WITH, UNKNOWN)
        """
        # Find first non-whitespace word
        stripped = query.strip().upper()

        for stmt_type in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
            if stripped.startswith(stmt_type):
                return stmt_type

        return "UNKNOWN"

    def _translate_error(self, error: Exception) -> ExecutionError:
        """
        Translate SQLite/SQLAlchemy error to ExecutionError.

        Args:
            error: Original exception

        Returns:
            ExecutionError with meaningful message
        """
        error_msg = str(error).lower()

        # Constraint violations
        if "unique constraint" in error_msg:
            return ExecutionError(
                "Unique constraint violation",
                original_error=error,
                details={"constraint_type": "unique"},
            )
        if "foreign key constraint" in error_msg:
            return ExecutionError(
                "Foreign key constraint violation",
                original_error=error,
                details={"constraint_type": "foreign_key"},
            )
        if "not null constraint" in error_msg:
            return ExecutionError(
                "NOT NULL constraint violation",
                original_error=error,
                details={"constraint_type": "not_null"},
            )

        # Database locked (transient)
        if "database is locked" in error_msg:
            return ExecutionError(
                "Database is locked (retry later)",
                original_error=error,
                details={"transient": True},
            )

        # Syntax errors (shouldn't occur after validation)
        if "syntax error" in error_msg:
            return ExecutionError(
                f"SQL syntax error: {error}",
                original_error=error,
                details={"error_type": "syntax"},
            )

        # No such table (shouldn't occur after validation)
        if "no such table" in error_msg:
            return ExecutionError(
                f"Table not found: {error}",
                original_error=error,
                details={"error_type": "no_table"},
            )

        # Generic execution error
        return ExecutionError(
            f"Database error: {error}",
            original_error=error,
        )
