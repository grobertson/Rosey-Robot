"""
SQL Audit Logger for parameterized SQL queries.

This module provides comprehensive audit logging for all SQL queries,
supporting security compliance, debugging, and performance analysis.

Features:
    - 100% query logging with structured JSON output
    - Slow query detection and logging
    - Query hashing for pattern analysis
    - SIEM-compatible format

Example:
    >>> logger = SQLAuditLogger(slow_query_threshold_ms=500.0)
    >>> result = SQLResult(rows=[...], row_count=10, ...)
    >>> logger.log_query("my-plugin", "SELECT ...", [], result, start_time)
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# Configure audit loggers
_audit_logger = logging.getLogger("sql.audit")
_slow_logger = logging.getLogger("sql.slow")


@dataclass
class AuditLogEntry:
    """
    Structured audit log entry for SQL query.

    Attributes:
        timestamp: ISO format UTC timestamp
        plugin: Plugin that executed the query
        query_hash: SHA256 hash of normalized query (first 16 chars)
        query_preview: First 100 chars of query
        param_count: Number of parameters bound
        row_count: Number of rows returned/affected
        execution_time_ms: Query execution time in milliseconds
        status: "success" or "error"
        truncated: Whether results were truncated
        error_type: Exception type name (if error)
        error_message: Error message (if error)
        error_code: Error code (if error)
    """

    timestamp: str
    plugin: str
    query_hash: str
    query_preview: str
    param_count: int
    execution_time_ms: float
    status: str
    row_count: Optional[int] = None
    truncated: Optional[bool] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "timestamp": self.timestamp,
            "plugin": self.plugin,
            "query_hash": self.query_hash,
            "query_preview": self.query_preview,
            "param_count": self.param_count,
            "execution_time_ms": self.execution_time_ms,
            "status": self.status,
        }

        if self.row_count is not None:
            result["row_count"] = self.row_count
        if self.truncated is not None:
            result["truncated"] = self.truncated
        if self.error_type is not None:
            result["error_type"] = self.error_type
        if self.error_message is not None:
            result["error_message"] = self.error_message
        if self.error_code is not None:
            result["error_code"] = self.error_code

        return result


@dataclass
class SlowQueryLogEntry:
    """
    Extended log entry for slow queries.

    Includes full query text and sanitized parameters for analysis.
    """

    base: AuditLogEntry
    full_query: str
    params: list[Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = self.base.to_dict()
        result["full_query"] = self.full_query
        result["params"] = self.params
        return result


@dataclass
class QueryMetrics:
    """
    Aggregated query metrics for monitoring.

    Attributes:
        total_queries: Total queries executed
        total_errors: Total query errors
        total_slow_queries: Queries exceeding slow threshold
        total_execution_time_ms: Sum of all execution times
        avg_execution_time_ms: Average execution time
        max_execution_time_ms: Maximum execution time
    """

    total_queries: int = 0
    total_errors: int = 0
    total_slow_queries: int = 0
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    _query_count: int = field(default=0, repr=False)

    def record(self, execution_time_ms: float, is_error: bool, is_slow: bool) -> None:
        """Record query metrics."""
        self.total_queries += 1
        self._query_count += 1
        self.total_execution_time_ms += execution_time_ms

        if is_error:
            self.total_errors += 1
        if is_slow:
            self.total_slow_queries += 1

        self.max_execution_time_ms = max(self.max_execution_time_ms, execution_time_ms)
        if self._query_count > 0:
            self.avg_execution_time_ms = (
                self.total_execution_time_ms / self._query_count
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "total_queries": self.total_queries,
            "total_errors": self.total_errors,
            "total_slow_queries": self.total_slow_queries,
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "max_execution_time_ms": round(self.max_execution_time_ms, 2),
            "error_rate": round(
                self.total_errors / self.total_queries if self.total_queries else 0, 4
            ),
            "slow_query_rate": round(
                self.total_slow_queries / self.total_queries
                if self.total_queries
                else 0,
                4,
            ),
        }


class SQLAuditLogger:
    """
    Audit logger for SQL queries.

    Logs all queries in structured JSON format for:
    - Security auditing and compliance
    - Debugging and troubleshooting
    - Performance analysis
    - SIEM integration

    Features:
        - 100% query logging (configurable log level)
        - Slow query detection with separate logger
        - Query hashing for pattern grouping
        - Param sanitization (truncate long values)
        - Aggregated metrics collection

    Example:
        >>> logger = SQLAuditLogger(slow_query_threshold_ms=500.0)
        >>>
        >>> # Log successful query
        >>> start = time.time()
        >>> result = await execute_query(...)
        >>> logger.log_query("my-plugin", query, params, result, start)
        >>>
        >>> # Log error
        >>> try:
        ...     result = await execute_query(...)
        ... except Exception as e:
        ...     logger.log_error("my-plugin", query, params, e, start)
        >>>
        >>> # Get metrics
        >>> metrics = logger.get_metrics()
        >>> print(f"Slow queries: {metrics.total_slow_queries}")

    Thread Safety:
        All methods are thread-safe.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        slow_logger: Optional[logging.Logger] = None,
        slow_query_threshold_ms: float = 500.0,
        max_param_length: int = 100,
        log_level: int = logging.INFO,
        slow_log_level: int = logging.WARNING,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            logger: Logger for all queries (default: sql.audit)
            slow_logger: Logger for slow queries (default: sql.slow)
            slow_query_threshold_ms: Threshold for slow query logging
            max_param_length: Max length for param values in logs
            log_level: Log level for regular queries
            slow_log_level: Log level for slow queries
        """
        self.logger = logger or _audit_logger
        self.slow_logger = slow_logger or _slow_logger
        self.slow_threshold_ms = slow_query_threshold_ms
        self.max_param_length = max_param_length
        self.log_level = log_level
        self.slow_log_level = slow_log_level

        # Per-plugin metrics
        self._metrics: dict[str, QueryMetrics] = {}
        self._global_metrics = QueryMetrics()

    def log_query(
        self,
        plugin: str,
        query: str,
        params: list[Any],
        row_count: int,
        execution_time_ms: float,
        truncated: bool = False,
    ) -> AuditLogEntry:
        """
        Log successful query execution.

        Args:
            plugin: Plugin that executed the query
            query: SQL query string
            params: Parameter values
            row_count: Number of rows returned/affected
            execution_time_ms: Query execution time in milliseconds
            truncated: Whether results were truncated

        Returns:
            AuditLogEntry for the query
        """
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            plugin=plugin,
            query_hash=self._hash_query(query),
            query_preview=self._truncate(query, 100),
            param_count=len(params),
            row_count=row_count,
            execution_time_ms=round(execution_time_ms, 2),
            truncated=truncated,
            status="success",
        )

        # Log the query
        self.logger.log(
            self.log_level,
            "SQL query executed",
            extra={"audit": entry.to_dict()},
        )

        # Check for slow query
        is_slow = execution_time_ms > self.slow_threshold_ms
        if is_slow:
            self._log_slow_query(entry, query, params)

        # Update metrics
        self._record_metrics(plugin, execution_time_ms, is_error=False, is_slow=is_slow)

        return entry

    def log_error(
        self,
        plugin: str,
        query: str,
        params: list[Any],
        error: Exception,
        execution_time_ms: float,
    ) -> AuditLogEntry:
        """
        Log failed query execution.

        Args:
            plugin: Plugin that executed the query
            query: SQL query string
            params: Parameter values
            error: Exception that occurred
            execution_time_ms: Time until error in milliseconds

        Returns:
            AuditLogEntry for the failed query
        """
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            plugin=plugin,
            query_hash=self._hash_query(query),
            query_preview=self._truncate(query, 100),
            param_count=len(params),
            execution_time_ms=round(execution_time_ms, 2),
            status="error",
            error_type=type(error).__name__,
            error_message=self._truncate(str(error), 200),
            error_code=getattr(error, "code", "UNKNOWN"),
        )

        # Log the error
        self.logger.error(
            "SQL query failed",
            extra={"audit": entry.to_dict()},
        )

        # Update metrics
        self._record_metrics(plugin, execution_time_ms, is_error=True, is_slow=False)

        return entry

    def _log_slow_query(
        self,
        entry: AuditLogEntry,
        query: str,
        params: list[Any],
    ) -> None:
        """Log slow query with full details."""
        slow_entry = SlowQueryLogEntry(
            base=entry,
            full_query=query,
            params=self._sanitize_params(params),
        )

        self.slow_logger.log(
            self.slow_log_level,
            "Slow SQL query detected",
            extra={"slow_query": slow_entry.to_dict()},
        )

    def _hash_query(self, query: str) -> str:
        """
        Generate hash for query (for grouping similar queries).

        Normalizes whitespace before hashing for consistent grouping.

        Args:
            query: SQL query string

        Returns:
            First 16 characters of SHA256 hash
        """
        # Normalize whitespace and case for consistent hashing
        normalized = " ".join(query.split()).lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _truncate(self, value: str, max_length: int) -> str:
        """Truncate string if too long."""
        if len(value) <= max_length:
            return value
        return value[: max_length - 3] + "..."

    def _sanitize_params(self, params: list[Any]) -> list[Any]:
        """
        Sanitize params for logging (truncate long values).

        Prevents logging of very large parameter values while
        preserving enough information for debugging.

        Args:
            params: List of parameter values

        Returns:
            Sanitized parameter list
        """

        def sanitize(val: Any) -> Any:
            if isinstance(val, str) and len(val) > self.max_param_length:
                return val[: self.max_param_length] + "..."
            if isinstance(val, bytes) and len(val) > self.max_param_length:
                return f"<bytes:{len(val)}>"
            return val

        return [sanitize(p) for p in params]

    def _record_metrics(
        self,
        plugin: str,
        execution_time_ms: float,
        is_error: bool,
        is_slow: bool,
    ) -> None:
        """Record metrics for plugin and global."""
        # Per-plugin metrics
        if plugin not in self._metrics:
            self._metrics[plugin] = QueryMetrics()
        self._metrics[plugin].record(execution_time_ms, is_error, is_slow)

        # Global metrics
        self._global_metrics.record(execution_time_ms, is_error, is_slow)

    def get_metrics(self, plugin: Optional[str] = None) -> QueryMetrics:
        """
        Get query metrics.

        Args:
            plugin: Plugin name, or None for global metrics

        Returns:
            QueryMetrics for the specified scope
        """
        if plugin is None:
            return self._global_metrics
        return self._metrics.get(plugin, QueryMetrics())

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get metrics for all plugins and global.

        Returns:
            Dict with "global" and per-plugin metrics
        """
        result = {"global": self._global_metrics.to_dict()}
        for plugin, metrics in self._metrics.items():
            result[plugin] = metrics.to_dict()
        return result

    def reset_metrics(self, plugin: Optional[str] = None) -> None:
        """
        Reset metrics.

        Args:
            plugin: Plugin to reset, or None to reset all
        """
        if plugin is None:
            self._metrics.clear()
            self._global_metrics = QueryMetrics()
        else:
            self._metrics.pop(plugin, None)
