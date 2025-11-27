"""
SQL Client for parameterized SQL queries over NATS.

This module provides a high-level Python client for executing SQL queries
through the NATS SQL API. It wraps the low-level NATS request/response
with convenient methods, error handling, retry logic, and audit logging.

Example:
    >>> from lib.storage import SQLClient
    >>>
    >>> client = SQLClient(nats_client, "my-plugin")
    >>> rows = await client.select(
    ...     "SELECT * FROM my_plugin__events WHERE user_id = $1",
    ...     ["alice"]
    ... )
    >>> for row in rows:
    ...     print(row["event_type"])
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from .sql_audit import SQLAuditLogger
from .sql_errors import (
    ExecutionError,
    ForbiddenStatementError,
    NamespaceViolationError,
    ParameterError,
    PermissionDeniedError,
    SQLSyntaxError,
    SQLValidationError,
    StackedQueryError,
    TimeoutError,
)
from .sql_rate_limit import SQLRateLimiter


# Error code to exception class mapping
_ERROR_MAP: dict[str, type[SQLValidationError]] = {
    "SYNTAX_ERROR": SQLSyntaxError,
    "FORBIDDEN_STATEMENT": ForbiddenStatementError,
    "NAMESPACE_VIOLATION": NamespaceViolationError,
    "PARAMETER_ERROR": ParameterError,
    "PERMISSION_DENIED": PermissionDeniedError,
    "EXECUTION_ERROR": ExecutionError,
    "STACKED_QUERIES": StackedQueryError,
    "TIMEOUT": TimeoutError,
}

# Default NATS subject for SQL queries
DEFAULT_SQL_SUBJECT = "sql.query"


@dataclass
class SQLResult:
    """
    Result of SQL query execution.

    Contains the query results along with metadata about the execution.

    Attributes:
        rows: List of row dictionaries
        row_count: Number of rows returned/affected
        execution_time_ms: Query execution time in milliseconds
        truncated: Whether results were truncated due to max_rows limit

    Example:
        >>> result = await client.execute("SELECT * FROM ...", [])
        >>> for row in result:
        ...     print(row)
        >>> print(f"Found {len(result)} rows in {result.execution_time_ms}ms")
    """

    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool

    def __iter__(self):
        """Allow iteration over rows."""
        return iter(self.rows)

    def __len__(self):
        """Return row count."""
        return self.row_count

    def __bool__(self):
        """Return True if any rows."""
        return self.row_count > 0

    def first(self) -> Optional[dict[str, Any]]:
        """
        Return first row or None.

        Returns:
            First row dict, or None if no rows
        """
        return self.rows[0] if self.rows else None

    def scalar(self, column: Optional[str] = None) -> Any:
        """
        Return single scalar value from first row.

        Args:
            column: Column name, or None for first column

        Returns:
            Value from specified column of first row

        Raises:
            ValueError: If no rows or column not found
        """
        if not self.rows:
            raise ValueError("No rows in result")

        row = self.rows[0]
        if column is None:
            # Get first column value
            return next(iter(row.values()))
        if column not in row:
            raise ValueError(f"Column '{column}' not found in result")
        return row[column]


@dataclass
class SQLClientConfig:
    """
    Configuration for SQLClient.

    Attributes:
        default_timeout_ms: Default query timeout in milliseconds
        max_retries: Maximum retry attempts for transient errors
        retry_delay_ms: Base delay between retries (exponential backoff)
        rate_limit_per_min: Queries per minute (0 to disable)
        slow_query_threshold_ms: Log queries slower than this
        nats_subject: NATS subject for SQL queries
    """

    default_timeout_ms: int = 10000
    max_retries: int = 3
    retry_delay_ms: int = 100
    rate_limit_per_min: int = 100
    slow_query_threshold_ms: float = 500.0
    nats_subject: str = DEFAULT_SQL_SUBJECT


class SQLClient:
    """
    High-level client for parameterized SQL execution over NATS.

    Provides a convenient wrapper around the NATS SQL API with:
    - Convenience methods: select, insert, update, delete
    - Automatic error handling and typed exceptions
    - Retry logic for transient errors
    - Rate limiting (configurable per-plugin quotas)
    - Comprehensive audit logging

    Example:
        >>> from lib.storage import SQLClient
        >>>
        >>> # Create client
        >>> client = SQLClient(nats_client, "my-plugin")
        >>>
        >>> # SELECT queries
        >>> rows = await client.select(
        ...     "SELECT * FROM my_plugin__events WHERE user_id = $1",
        ...     ["alice"]
        ... )
        >>>
        >>> # Single row
        >>> user = await client.select_one(
        ...     "SELECT * FROM my_plugin__users WHERE id = $1",
        ...     [123]
        ... )
        >>>
        >>> # INSERT
        >>> count = await client.insert(
        ...     "INSERT INTO my_plugin__events (user_id, data) VALUES ($1, $2)",
        ...     ["alice", '{"action": "login"}']
        ... )
        >>>
        >>> # UPDATE
        >>> affected = await client.update(
        ...     "UPDATE my_plugin__users SET score = score + $1 WHERE id = $2",
        ...     [10, 123]
        ... )
        >>>
        >>> # DELETE
        >>> deleted = await client.delete(
        ...     "DELETE FROM my_plugin__events WHERE timestamp < $1",
        ...     ["2024-01-01"]
        ... )

    Thread Safety:
        Client is async-safe and can be used concurrently from multiple
        coroutines. Rate limiting and metrics are properly synchronized.
    """

    def __init__(
        self,
        nats_client: Any,
        plugin: str,
        config: Optional[SQLClientConfig] = None,
        rate_limiter: Optional[SQLRateLimiter] = None,
        audit_logger: Optional[SQLAuditLogger] = None,
    ) -> None:
        """
        Initialize SQL client.

        Args:
            nats_client: NATS client instance (must have request() method)
            plugin: Plugin name (determines table namespace)
            config: Client configuration (defaults used if None)
            rate_limiter: Shared rate limiter (created if None)
            audit_logger: Shared audit logger (created if None)
        """
        self._nats = nats_client
        self._plugin = plugin
        self._config = config or SQLClientConfig()

        # Rate limiting
        if rate_limiter is not None:
            self._rate_limiter = rate_limiter
        elif self._config.rate_limit_per_min > 0:
            self._rate_limiter = SQLRateLimiter(
                default_limit=self._config.rate_limit_per_min,
                window_seconds=60,
            )
        else:
            self._rate_limiter = None

        # Audit logging
        self._audit_logger = audit_logger or SQLAuditLogger(
            slow_query_threshold_ms=self._config.slow_query_threshold_ms,
        )

        # Metrics
        self._query_count = 0
        self._error_count = 0
        self._total_time_ms = 0.0

    @property
    def plugin(self) -> str:
        """Get the plugin name."""
        return self._plugin

    async def execute(
        self,
        query: str,
        params: Optional[list[Any]] = None,
        allow_write: bool = False,
        timeout_ms: Optional[int] = None,
        max_rows: Optional[int] = None,
    ) -> SQLResult:
        """
        Execute SQL query and return full result.

        This is the core method that all convenience methods use.
        Use select/insert/update/delete for simpler API.

        Args:
            query: SQL query with $1, $2, $3 placeholders
            params: Parameter values (default: [])
            allow_write: Enable INSERT/UPDATE/DELETE (default: False)
            timeout_ms: Query timeout override (default: from config)
            max_rows: Maximum rows to return (default: no limit)

        Returns:
            SQLResult with rows, row_count, execution_time_ms, truncated

        Raises:
            SQLValidationError: Query failed validation
            SQLSyntaxError: SQL syntax is invalid
            ForbiddenStatementError: Statement type not allowed
            NamespaceViolationError: Table access not allowed
            ParameterError: Parameter count/format mismatch
            PermissionDeniedError: Write without allow_write
            ExecutionError: Database execution error
            TimeoutError: Query exceeded timeout
            RateLimitError: Rate limit exceeded
        """
        params = params or []
        timeout_ms = timeout_ms or self._config.default_timeout_ms

        # Check rate limit
        if self._rate_limiter is not None:
            await self._rate_limiter.check(self._plugin)

        # Build request
        request = {
            "query": query,
            "params": params,
            "allow_write": allow_write,
            "timeout_ms": timeout_ms,
        }
        if max_rows is not None:
            request["max_rows"] = max_rows

        # Execute with retry
        start_time = time.time()
        try:
            result = await self._execute_with_retry(request)
            execution_time_ms = (time.time() - start_time) * 1000

            # Parse response
            sql_result = SQLResult(
                rows=result.get("rows", []),
                row_count=result.get("row_count", len(result.get("rows", []))),
                execution_time_ms=result.get("execution_time_ms", execution_time_ms),
                truncated=result.get("truncated", False),
            )

            # Audit log
            self._audit_logger.log_query(
                plugin=self._plugin,
                query=query,
                params=params,
                row_count=sql_result.row_count,
                execution_time_ms=sql_result.execution_time_ms,
                truncated=sql_result.truncated,
            )

            # Update metrics
            self._query_count += 1
            self._total_time_ms += sql_result.execution_time_ms

            return sql_result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            # Audit log error
            self._audit_logger.log_error(
                plugin=self._plugin,
                query=query,
                params=params,
                error=e,
                execution_time_ms=execution_time_ms,
            )

            # Update metrics
            self._error_count += 1

            raise

    async def _execute_with_retry(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Execute request with retry for transient errors.

        Args:
            request: Request payload

        Returns:
            Response payload

        Raises:
            Various SQLValidationError subclasses on error
        """
        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                return await self._send_request(request)

            except (ConnectionError, asyncio.TimeoutError) as e:
                # Transient error - retry
                last_error = e
                if attempt < self._config.max_retries:
                    delay_ms = self._config.retry_delay_ms * (2**attempt)
                    await asyncio.sleep(delay_ms / 1000)
                continue

            except SQLValidationError:
                # Non-transient error - don't retry
                raise

        # Max retries exceeded
        raise ExecutionError(
            f"Max retries ({self._config.max_retries}) exceeded",
            original_error=last_error,
            details={"last_error": str(last_error)},
        )

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Send request to NATS and parse response.

        Args:
            request: Request payload

        Returns:
            Response payload

        Raises:
            Various exceptions on error
        """
        # Build subject with plugin
        subject = f"{self._config.nats_subject}.{self._plugin}"

        # Serialize request
        payload = json.dumps(request).encode("utf-8")

        # Send request (with timeout)
        timeout_s = request.get("timeout_ms", self._config.default_timeout_ms) / 1000
        try:
            response = await asyncio.wait_for(
                self._nats.request(subject, payload),
                timeout=timeout_s + 1,  # Add buffer for network latency
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                "NATS request timeout",
                timeout_ms=int(timeout_s * 1000),
            )

        # Parse response
        try:
            result = json.loads(response.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ExecutionError(
                f"Invalid response from SQL handler: {e}",
                original_error=e,
            )

        # Check for error response
        if "error" in result:
            self._raise_error(result["error"])

        return result

    def _raise_error(self, error: dict[str, Any]) -> None:
        """
        Convert error response to appropriate exception.

        Args:
            error: Error dict from response

        Raises:
            Appropriate SQLValidationError subclass
        """
        code = error.get("code", "UNKNOWN")
        message = error.get("message", "Unknown error")
        details = error.get("details", {})

        # Special handling for timeout
        if code == "TIMEOUT":
            timeout_ms = details.get("timeout_ms", 0)
            raise TimeoutError(message, timeout_ms=timeout_ms, details=details)

        # Special handling for permission denied
        if code == "PERMISSION_DENIED":
            permission = details.get("required_permission", "allow_write")
            raise PermissionDeniedError(
                message, required_permission=permission, details=details
            )

        # Map other error codes
        error_class = _ERROR_MAP.get(code, SQLValidationError)
        raise error_class(code, message, details)

    async def select(
        self,
        query: str,
        params: Optional[list[Any]] = None,
        timeout_ms: Optional[int] = None,
        max_rows: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute SELECT and return rows.

        Args:
            query: SELECT query with $1, $2, $3 placeholders
            params: Parameter values
            timeout_ms: Query timeout override
            max_rows: Maximum rows to return

        Returns:
            List of row dicts

        Example:
            >>> rows = await client.select(
            ...     "SELECT * FROM my_plugin__events WHERE timestamp > $1",
            ...     ["2025-01-01"]
            ... )
            >>> for row in rows:
            ...     print(row["event_type"])
        """
        result = await self.execute(
            query=query,
            params=params,
            allow_write=False,
            timeout_ms=timeout_ms,
            max_rows=max_rows,
        )
        return result.rows

    async def select_one(
        self,
        query: str,
        params: Optional[list[Any]] = None,
        timeout_ms: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Execute SELECT and return single row or None.

        Args:
            query: SELECT query (should return 0 or 1 row)
            params: Parameter values
            timeout_ms: Query timeout override

        Returns:
            Row dict or None if no results

        Example:
            >>> user = await client.select_one(
            ...     "SELECT * FROM my_plugin__users WHERE id = $1",
            ...     [123]
            ... )
            >>> if user:
            ...     print(f"Found: {user['name']}")
        """
        result = await self.execute(
            query=query,
            params=params,
            allow_write=False,
            timeout_ms=timeout_ms,
            max_rows=1,
        )
        return result.first()

    async def insert(
        self,
        query: str,
        params: list[Any],
        timeout_ms: Optional[int] = None,
    ) -> int:
        """
        Execute INSERT and return row count.

        Args:
            query: INSERT query with $1, $2, $3 placeholders
            params: Values to insert
            timeout_ms: Query timeout override

        Returns:
            Number of rows inserted

        Example:
            >>> count = await client.insert(
            ...     "INSERT INTO my_plugin__events (user_id, data) VALUES ($1, $2)",
            ...     ["alice", '{"action": "login"}']
            ... )
            >>> print(f"Inserted {count} row(s)")
        """
        result = await self.execute(
            query=query,
            params=params,
            allow_write=True,
            timeout_ms=timeout_ms,
        )
        return result.row_count

    async def insert_many(
        self,
        query: str,
        params_list: list[list[Any]],
        timeout_ms: Optional[int] = None,
    ) -> int:
        """
        Execute INSERT for multiple rows.

        Executes the query multiple times with different parameters.
        Returns total rows inserted.

        Args:
            query: INSERT query with placeholders
            params_list: List of parameter lists (one per row)
            timeout_ms: Query timeout override (per query)

        Returns:
            Total rows inserted

        Example:
            >>> count = await client.insert_many(
            ...     "INSERT INTO my_plugin__events (user_id, data) VALUES ($1, $2)",
            ...     [
            ...         ["alice", '{"action": "login"}'],
            ...         ["bob", '{"action": "logout"}'],
            ...     ]
            ... )
            >>> print(f"Inserted {count} row(s)")
        """
        total = 0
        for params in params_list:
            count = await self.insert(query, params, timeout_ms=timeout_ms)
            total += count
        return total

    async def update(
        self,
        query: str,
        params: list[Any],
        timeout_ms: Optional[int] = None,
    ) -> int:
        """
        Execute UPDATE and return affected row count.

        Args:
            query: UPDATE query with $1, $2, $3 placeholders
            params: Parameter values
            timeout_ms: Query timeout override

        Returns:
            Number of rows updated

        Example:
            >>> count = await client.update(
            ...     "UPDATE my_plugin__users SET score = score + $1 WHERE id = $2",
            ...     [10, 123]
            ... )
            >>> print(f"Updated {count} row(s)")
        """
        result = await self.execute(
            query=query,
            params=params,
            allow_write=True,
            timeout_ms=timeout_ms,
        )
        return result.row_count

    async def delete(
        self,
        query: str,
        params: list[Any],
        timeout_ms: Optional[int] = None,
    ) -> int:
        """
        Execute DELETE and return deleted row count.

        Args:
            query: DELETE query with $1, $2, $3 placeholders
            params: Parameter values
            timeout_ms: Query timeout override

        Returns:
            Number of rows deleted

        Example:
            >>> count = await client.delete(
            ...     "DELETE FROM my_plugin__events WHERE timestamp < $1",
            ...     ["2024-01-01"]
            ... )
            >>> print(f"Deleted {count} row(s)")
        """
        result = await self.execute(
            query=query,
            params=params,
            allow_write=True,
            timeout_ms=timeout_ms,
        )
        return result.row_count

    def get_metrics(self) -> dict[str, Any]:
        """
        Get client metrics.

        Returns:
            Dict with query_count, error_count, avg_latency_ms, etc.
        """
        avg_time = self._total_time_ms / self._query_count if self._query_count else 0

        metrics = {
            "plugin": self._plugin,
            "query_count": self._query_count,
            "error_count": self._error_count,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_latency_ms": round(avg_time, 2),
            "error_rate": round(
                self._error_count / self._query_count if self._query_count else 0, 4
            ),
        }

        # Add rate limit status
        if self._rate_limiter is not None:
            status = self._rate_limiter.get_status(self._plugin)
            metrics["rate_limit"] = {
                "limit": status.limit,
                "current": status.current,
                "remaining": status.remaining,
            }

        # Add audit metrics
        audit_metrics = self._audit_logger.get_metrics(self._plugin)
        metrics["slow_queries"] = audit_metrics.total_slow_queries

        return metrics

    def reset_metrics(self) -> None:
        """Reset client metrics."""
        self._query_count = 0
        self._error_count = 0
        self._total_time_ms = 0.0
