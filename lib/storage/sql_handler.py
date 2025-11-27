"""
NATS SQL Execution Handler for parameterized SQL queries.

This module provides the SQLExecutionHandler class which handles NATS
requests for SQL query execution, integrating the validation, binding,
execution, and formatting pipeline.
"""

import json
import logging
import re
import time
from typing import Any, Optional

from .sql_errors import (
    RequestValidationError,
)
from .sql_executor import PreparedStatementExecutor
from .sql_formatter import ResultFormatter
from .sql_parameter import ParameterBinder
from .sql_validator import QueryValidator


logger = logging.getLogger(__name__)


def extract_plugin_from_subject(subject: str) -> str:
    """
    Extract plugin name from NATS subject.

    Args:
        subject: NATS subject (e.g., "rosey.db.sql.analytics-db.execute")

    Returns:
        Plugin name (e.g., "analytics-db")

    Raises:
        ValueError: If subject format is invalid
    """
    parts = subject.split(".")

    # Expected: rosey.db.sql.<plugin>.execute
    if len(parts) != 5:
        raise ValueError(f"Invalid subject format: {subject}")

    if (
        parts[0] != "rosey"
        or parts[1] != "db"
        or parts[2] != "sql"
        or parts[4] != "execute"
    ):
        raise ValueError(f"Invalid subject format: {subject}")

    plugin = parts[3]

    # Validate plugin name (alphanumeric, hyphens, underscores)
    if not re.match(r"^[a-z0-9_-]+$", plugin, re.IGNORECASE):
        raise ValueError(f"Invalid plugin name: {plugin}")

    return plugin


class SQLExecutionHandler:
    """
    Handle SQL execution requests via NATS messaging.

    This handler subscribes to rosey.db.sql.*.execute subjects and processes
    SQL query requests from plugins. It validates requests, executes queries
    using the SQL execution pipeline, and returns formatted responses.

    Subject Pattern:
        rosey.db.sql.<plugin>.execute

    Request Format:
        {
            "query": "SELECT * FROM plugin__table WHERE id = $1",
            "params": ["value"],
            "allow_write": false,
            "timeout_ms": 10000,
            "max_rows": 10000
        }

    Response Format (Success):
        {
            "rows": [{"id": 1, "name": "value"}],
            "row_count": 1,
            "execution_time_ms": 15.3,
            "truncated": false
        }

    Response Format (Error):
        {
            "error": "VALIDATION_ERROR",
            "message": "CREATE statements are forbidden",
            "details": {...}
        }

    Example:
        >>> handler = SQLExecutionHandler(nats_client, database, config)
        >>> await handler.start()
        >>> # Handler now processes requests
        >>> await handler.stop()

    Thread Safety:
        Handler is async-safe and can process concurrent requests.
    """

    # Default configuration
    DEFAULT_TIMEOUT_MS: int = 10000
    DEFAULT_MAX_ROWS: int = 10000

    # Bounds for configuration
    MIN_TIMEOUT_MS: int = 100
    MAX_TIMEOUT_MS: int = 30000
    MIN_MAX_ROWS: int = 1
    MAX_MAX_ROWS: int = 100000

    def __init__(
        self,
        nats_client: Any,
        database: Any,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize SQL execution handler.

        Args:
            nats_client: NATS client instance (must support subscribe/unsubscribe)
            database: Database instance (passed to executor)
            config: Optional configuration dict with:
                - default_timeout_ms: Default query timeout (default: 10000)
                - default_max_rows: Default row limit (default: 10000)
        """
        self.nats_client = nats_client
        self.database = database
        self.config = config or {}

        # Initialize execution pipeline components
        self.validator = QueryValidator()
        self.binder = ParameterBinder()
        self.executor = PreparedStatementExecutor(database)
        self.formatter = ResultFormatter()

        self.logger = logging.getLogger(__name__)
        self.subscription: Optional[Any] = None

        # Metrics
        self.request_count: int = 0
        self.error_count: int = 0
        self.total_execution_time_ms: float = 0.0

    async def start(self) -> None:
        """
        Start handler by subscribing to NATS subjects.

        Subscribes to: rosey.db.sql.*.execute
        """
        self.logger.info("Starting SQL execution handler")

        # Subscribe to wildcard pattern: rosey.db.sql.*.execute
        self.subscription = await self.nats_client.subscribe(
            "rosey.db.sql.*.execute",
            cb=self.handle_execute,
        )

        self.logger.info(
            "SQL execution handler started, subscribed to rosey.db.sql.*.execute"
        )

    async def stop(self) -> None:
        """Stop handler and clean up resources."""
        if self.subscription:
            await self.subscription.unsubscribe()
            self.subscription = None
            self.logger.info(
                "SQL execution handler stopped "
                f"(requests: {self.request_count}, errors: {self.error_count})"
            )

    async def handle_execute(self, msg: Any) -> None:
        """
        Handle SQL execution request from NATS.

        Message flow:
        1. Parse request JSON
        2. Validate request schema
        3. Extract plugin from subject
        4. Execute query pipeline
        5. Send response

        Args:
            msg: NATS message containing SQL request
        """
        start_time = time.perf_counter()
        self.request_count += 1
        plugin = "unknown"
        request_data: dict[str, Any] = {}

        try:
            # Extract plugin from subject
            try:
                plugin = extract_plugin_from_subject(msg.subject)
            except ValueError as e:
                raise RequestValidationError(
                    str(e),
                    field="subject",
                )

            # Parse request JSON
            try:
                request_data = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise RequestValidationError(
                    f"Invalid JSON: {e}",
                    field="body",
                )

            # Validate request schema
            validated_request = self._validate_request(request_data)

            # Execute query through pipeline
            result = await self._execute_query(plugin, validated_request)

            # Send success response
            response = json.dumps(result).encode()
            await msg.respond(response)

            # Log success
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self.total_execution_time_ms += execution_time_ms
            self.logger.info(
                "SQL query executed successfully",
                extra={
                    "plugin": plugin,
                    "execution_time_ms": round(execution_time_ms, 2),
                    "row_count": result.get("row_count", 0),
                    "truncated": result.get("truncated", False),
                    "query_hash": hash(validated_request["query"]),
                },
            )

        except Exception as e:
            # Handle error
            self.error_count += 1
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Format error response
            error_response = self._format_error(e, request_data, plugin)

            # Send error response
            response = json.dumps(error_response).encode()
            await msg.respond(response)

            # Log error
            self.logger.error(
                "SQL query execution failed: %s",
                str(e),
                extra={
                    "plugin": plugin,
                    "execution_time_ms": round(execution_time_ms, 2),
                    "error_type": type(e).__name__,
                    "error_code": getattr(e, "code", "UNKNOWN_ERROR"),
                },
            )

    def _validate_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate request schema.

        Required fields:
            - query: str (SQL query with $N placeholders)

        Optional fields:
            - params: list (parameter values, default: [])
            - allow_write: bool (default: False)
            - timeout_ms: int (default: 10000, range: 100-30000)
            - max_rows: int (default: 10000, range: 1-100000)

        Args:
            data: Raw request data dict

        Returns:
            Validated request dict with defaults applied

        Raises:
            RequestValidationError: If validation fails
        """
        # Check required field: query
        if "query" not in data:
            raise RequestValidationError(
                "Missing required field: query",
                field="query",
            )

        if not isinstance(data["query"], str):
            raise RequestValidationError(
                "Field 'query' must be a string",
                field="query",
            )

        query = data["query"].strip()
        if not query:
            raise RequestValidationError(
                "Field 'query' cannot be empty",
                field="query",
            )

        # Params is optional, default to empty list
        params = data.get("params", [])
        if not isinstance(params, list):
            raise RequestValidationError(
                "Field 'params' must be a list",
                field="params",
            )

        # Optional: allow_write
        allow_write = data.get("allow_write", False)
        if not isinstance(allow_write, bool):
            raise RequestValidationError(
                "Field 'allow_write' must be a boolean",
                field="allow_write",
            )

        # Optional: timeout_ms
        default_timeout = self.config.get("default_timeout_ms", self.DEFAULT_TIMEOUT_MS)
        timeout_ms = data.get("timeout_ms", default_timeout)
        if not isinstance(timeout_ms, int):
            raise RequestValidationError(
                "Field 'timeout_ms' must be an integer",
                field="timeout_ms",
            )
        if timeout_ms < self.MIN_TIMEOUT_MS or timeout_ms > self.MAX_TIMEOUT_MS:
            raise RequestValidationError(
                f"Field 'timeout_ms' must be between {self.MIN_TIMEOUT_MS} and {self.MAX_TIMEOUT_MS}",
                field="timeout_ms",
            )

        # Optional: max_rows
        default_max_rows = self.config.get("default_max_rows", self.DEFAULT_MAX_ROWS)
        max_rows = data.get("max_rows", default_max_rows)
        if not isinstance(max_rows, int):
            raise RequestValidationError(
                "Field 'max_rows' must be an integer",
                field="max_rows",
            )
        if max_rows < self.MIN_MAX_ROWS or max_rows > self.MAX_MAX_ROWS:
            raise RequestValidationError(
                f"Field 'max_rows' must be between {self.MIN_MAX_ROWS} and {self.MAX_MAX_ROWS}",
                field="max_rows",
            )

        return {
            "query": query,
            "params": params,
            "allow_write": allow_write,
            "timeout_ms": timeout_ms,
            "max_rows": max_rows,
        }

    async def _execute_query(
        self,
        plugin: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute SQL query through validation and execution pipeline.

        Pipeline:
        1. Validate query with QueryValidator
        2. Bind parameters with ParameterBinder
        3. Execute query with PreparedStatementExecutor
        4. Return formatted result

        Args:
            plugin: Plugin name (for namespace validation)
            request: Validated request dict

        Returns:
            Execution result dict

        Raises:
            SQLValidationError: If query validation fails
            ExecutionError: If query execution fails
        """
        query = request["query"]
        params = request["params"]
        allow_write = request["allow_write"]
        timeout_ms = request["timeout_ms"]
        max_rows = request["max_rows"]

        # Step 1: Validate query
        validation_result = self.validator.validate(query, plugin, params)
        if not validation_result.valid:
            raise validation_result.error  # type: ignore[misc]

        # Step 2: Bind parameters ($N → ?)
        sqlite_query, param_tuple = self.binder.bind(query, params)

        # Step 3: Execute query
        result = await self.executor.execute(
            plugin=plugin,
            query=sqlite_query,
            params=param_tuple,
            timeout_ms=timeout_ms,
            max_rows=max_rows,
            allow_write=allow_write,
        )

        # Result already formatted by executor
        return result

    def _format_error(
        self,
        error: Exception,
        request_data: dict[str, Any],
        plugin: str,
    ) -> dict[str, Any]:
        """
        Format error for NATS response.

        Args:
            error: Exception that occurred
            request_data: Original request data (for context)
            plugin: Plugin name

        Returns:
            Formatted error dict
        """
        query = request_data.get("query", "")
        params = request_data.get("params", [])

        return self.formatter.format_error(
            error=error,
            query=query,
            params=params,
            plugin=plugin,
        )

    def get_metrics(self) -> dict[str, Any]:
        """
        Get handler metrics.

        Returns:
            Dict with request_count, error_count, avg_execution_time_ms
        """
        avg_time = (
            self.total_execution_time_ms / self.request_count
            if self.request_count > 0
            else 0.0
        )
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": (
                self.error_count / self.request_count
                if self.request_count > 0
                else 0.0
            ),
            "avg_execution_time_ms": round(avg_time, 2),
        }
