"""
Unit tests for SQL Client.

Tests the SQLClient class including NATS communication, error handling,
retry logic, and convenience methods.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.storage.sql_client import SQLClient, SQLClientConfig, SQLResult
from lib.storage.sql_errors import (
    ExecutionError,
    ForbiddenStatementError,
    NamespaceViolationError,
    ParameterError,
    PermissionDeniedError,
    SQLSyntaxError,
    TimeoutError,
)
from lib.storage.sql_rate_limit import RateLimitError


class TestSQLResult:
    """Tests for SQLResult dataclass."""

    def test_iteration(self):
        """Test iterating over result rows."""
        result = SQLResult(
            rows=[{"id": 1}, {"id": 2}, {"id": 3}],
            row_count=3,
            execution_time_ms=10.0,
            truncated=False,
        )

        ids = [row["id"] for row in result]
        assert ids == [1, 2, 3]

    def test_len(self):
        """Test len() returns row count."""
        result = SQLResult(
            rows=[{"id": 1}, {"id": 2}],
            row_count=2,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert len(result) == 2

    def test_bool_true(self):
        """Test bool() returns True when rows exist."""
        result = SQLResult(
            rows=[{"id": 1}], row_count=1, execution_time_ms=10.0, truncated=False
        )

        assert bool(result) is True

    def test_bool_false(self):
        """Test bool() returns False when no rows."""
        result = SQLResult(
            rows=[], row_count=0, execution_time_ms=10.0, truncated=False
        )

        assert bool(result) is False

    def test_first_with_rows(self):
        """Test first() returns first row."""
        result = SQLResult(
            rows=[{"id": 1, "name": "first"}, {"id": 2, "name": "second"}],
            row_count=2,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result.first() == {"id": 1, "name": "first"}

    def test_first_empty(self):
        """Test first() returns None when empty."""
        result = SQLResult(
            rows=[], row_count=0, execution_time_ms=10.0, truncated=False
        )

        assert result.first() is None

    def test_scalar_first_column(self):
        """Test scalar() returns first column value."""
        result = SQLResult(
            rows=[{"count": 42, "other": "ignored"}],
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result.scalar() == 42

    def test_scalar_named_column(self):
        """Test scalar() with column name."""
        result = SQLResult(
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result.scalar("name") == "test"

    def test_scalar_no_rows_raises(self):
        """Test scalar() raises on empty result."""
        result = SQLResult(
            rows=[], row_count=0, execution_time_ms=10.0, truncated=False
        )

        with pytest.raises(ValueError, match="No rows"):
            result.scalar()

    def test_scalar_invalid_column_raises(self):
        """Test scalar() raises on invalid column."""
        result = SQLResult(
            rows=[{"id": 1}], row_count=1, execution_time_ms=10.0, truncated=False
        )

        with pytest.raises(ValueError, match="Column 'invalid' not found"):
            result.scalar("invalid")


class TestSQLClientConfig:
    """Tests for SQLClientConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = SQLClientConfig()

        assert config.default_timeout_ms == 10000
        assert config.max_retries == 3
        assert config.retry_delay_ms == 100
        assert config.rate_limit_per_min == 100
        assert config.slow_query_threshold_ms == 500.0


class TestSQLClient:
    """Tests for SQLClient class."""

    @pytest.fixture
    def mock_nats(self):
        """Create mock NATS client."""
        nats = MagicMock()
        nats.request = AsyncMock()
        return nats

    @pytest.fixture
    def client(self, mock_nats):
        """Create SQLClient with mock NATS."""
        # Disable rate limiting for most tests
        config = SQLClientConfig(rate_limit_per_min=0)
        return SQLClient(mock_nats, "test-plugin", config=config)

    def _make_response(self, data: dict) -> MagicMock:
        """Create mock NATS response."""
        response = MagicMock()
        response.data = json.dumps(data).encode("utf-8")
        return response

    # Initialization tests

    def test_init_default_config(self, mock_nats):
        """Test client initializes with defaults."""
        client = SQLClient(mock_nats, "my-plugin")

        assert client.plugin == "my-plugin"

    def test_init_custom_config(self, mock_nats):
        """Test client accepts custom config."""
        config = SQLClientConfig(default_timeout_ms=5000, max_retries=5)
        client = SQLClient(mock_nats, "my-plugin", config=config)

        assert client._config.default_timeout_ms == 5000
        assert client._config.max_retries == 5

    def test_init_with_rate_limiter(self, mock_nats):
        """Test client uses provided rate limiter."""
        from lib.storage.sql_rate_limit import SQLRateLimiter

        limiter = SQLRateLimiter(default_limit=50)
        client = SQLClient(mock_nats, "my-plugin", rate_limiter=limiter)

        assert client._rate_limiter is limiter

    # Execute tests

    @pytest.mark.asyncio
    async def test_execute_select_success(self, client, mock_nats):
        """Test successful SELECT execution."""
        mock_nats.request.return_value = self._make_response(
            {
                "rows": [{"id": 1, "name": "test"}],
                "row_count": 1,
                "execution_time_ms": 5.0,
                "truncated": False,
            }
        )

        result = await client.execute(
            "SELECT * FROM test_plugin__events WHERE id = $1", [1]
        )

        assert result.row_count == 1
        assert result.rows[0]["name"] == "test"
        assert result.execution_time_ms == 5.0

    @pytest.mark.asyncio
    async def test_execute_sends_correct_request(self, client, mock_nats):
        """Test execute sends correct NATS request."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [], "row_count": 0}
        )

        await client.execute(
            "SELECT * FROM test_plugin__events WHERE id = $1",
            [123],
            allow_write=False,
            timeout_ms=5000,
        )

        # Check request was sent to correct subject
        call_args = mock_nats.request.call_args
        subject = call_args[0][0]
        payload = json.loads(call_args[0][1].decode("utf-8"))

        assert subject == "sql.query.test-plugin"
        assert payload["query"] == "SELECT * FROM test_plugin__events WHERE id = $1"
        assert payload["params"] == [123]
        assert payload["allow_write"] is False
        assert payload["timeout_ms"] == 5000

    @pytest.mark.asyncio
    async def test_execute_with_max_rows(self, client, mock_nats):
        """Test execute includes max_rows in request."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [], "row_count": 0}
        )

        await client.execute(
            "SELECT * FROM test_plugin__events", max_rows=100
        )

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["max_rows"] == 100

    # Error handling tests

    @pytest.mark.asyncio
    async def test_execute_handles_validation_error(self, client, mock_nats):
        """Test validation error is converted to exception."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "SYNTAX_ERROR",
                    "message": "Invalid SQL syntax",
                    "details": {},
                }
            }
        )

        with pytest.raises(SQLSyntaxError) as exc_info:
            await client.execute("INVALID SQL")

        assert "Invalid SQL syntax" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_handles_forbidden_statement(self, client, mock_nats):
        """Test forbidden statement error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "FORBIDDEN_STATEMENT",
                    "message": "DROP not allowed",
                    "details": {},
                }
            }
        )

        with pytest.raises(ForbiddenStatementError):
            await client.execute("DROP TABLE users")

    @pytest.mark.asyncio
    async def test_execute_handles_namespace_violation(self, client, mock_nats):
        """Test namespace violation error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "NAMESPACE_VIOLATION",
                    "message": "Cannot access other plugin tables",
                    "details": {},
                }
            }
        )

        with pytest.raises(NamespaceViolationError):
            await client.execute("SELECT * FROM other_plugin__data")

    @pytest.mark.asyncio
    async def test_execute_handles_parameter_error(self, client, mock_nats):
        """Test parameter error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "PARAMETER_ERROR",
                    "message": "Missing parameter $2",
                    "details": {},
                }
            }
        )

        with pytest.raises(ParameterError):
            await client.execute("SELECT * FROM test WHERE a = $1 AND b = $2", [1])

    @pytest.mark.asyncio
    async def test_execute_handles_permission_denied(self, client, mock_nats):
        """Test permission denied error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Write not allowed",
                    "details": {"required_permission": "allow_write"},
                }
            }
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            await client.execute("INSERT INTO test VALUES ($1)", [1])

        assert exc_info.value.required_permission == "allow_write"

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self, client, mock_nats):
        """Test timeout error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "TIMEOUT",
                    "message": "Query timed out",
                    "details": {"timeout_ms": 10000},
                }
            }
        )

        with pytest.raises(TimeoutError) as exc_info:
            await client.execute("SELECT * FROM large_table")

        assert exc_info.value.timeout_ms == 10000

    @pytest.mark.asyncio
    async def test_execute_handles_execution_error(self, client, mock_nats):
        """Test execution error."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": "Database error",
                    "details": {},
                }
            }
        )

        with pytest.raises(ExecutionError):
            await client.execute("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_execute_handles_nats_timeout(self, client, mock_nats):
        """Test NATS request timeout."""
        mock_nats.request.side_effect = asyncio.TimeoutError()

        # After max retries, should raise ExecutionError
        with pytest.raises((TimeoutError, ExecutionError)):
            await client.execute("SELECT * FROM test")

    # Retry tests

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, mock_nats):
        """Test automatic retry on connection error."""
        config = SQLClientConfig(max_retries=2, retry_delay_ms=10, rate_limit_per_min=0)
        client = SQLClient(mock_nats, "test-plugin", config=config)

        # First two calls fail, third succeeds
        mock_nats.request.side_effect = [
            ConnectionError("Failed"),
            ConnectionError("Failed"),
            self._make_response({"rows": [], "row_count": 0}),
        ]

        result = await client.execute("SELECT * FROM test")

        assert result.row_count == 0
        assert mock_nats.request.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_validation_error(self, client, mock_nats):
        """Test no retry for validation errors."""
        mock_nats.request.return_value = self._make_response(
            {
                "error": {
                    "code": "SYNTAX_ERROR",
                    "message": "Invalid SQL",
                    "details": {},
                }
            }
        )

        with pytest.raises(SQLSyntaxError):
            await client.execute("INVALID SQL")

        # Should only be called once (no retry)
        assert mock_nats.request.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_nats):
        """Test error raised after max retries."""
        config = SQLClientConfig(max_retries=2, retry_delay_ms=10, rate_limit_per_min=0)
        client = SQLClient(mock_nats, "test-plugin", config=config)

        mock_nats.request.side_effect = ConnectionError("Always fails")

        with pytest.raises(ExecutionError) as exc_info:
            await client.execute("SELECT * FROM test")

        assert "Max retries" in str(exc_info.value)
        # 1 initial + 2 retries = 3 calls
        assert mock_nats.request.call_count == 3

    # Select tests

    @pytest.mark.asyncio
    async def test_select_returns_rows(self, client, mock_nats):
        """Test select() returns row list."""
        mock_nats.request.return_value = self._make_response(
            {
                "rows": [{"id": 1}, {"id": 2}],
                "row_count": 2,
            }
        )

        rows = await client.select("SELECT * FROM test_plugin__events")

        assert rows == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_select_with_params(self, client, mock_nats):
        """Test select() with parameters."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [{"id": 1}], "row_count": 1}
        )

        rows = await client.select(
            "SELECT * FROM test_plugin__events WHERE user_id = $1", ["alice"]
        )

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["params"] == ["alice"]
        assert payload["allow_write"] is False

    # Select one tests

    @pytest.mark.asyncio
    async def test_select_one_returns_single(self, client, mock_nats):
        """Test select_one() returns single row."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [{"id": 1, "name": "test"}], "row_count": 1}
        )

        row = await client.select_one(
            "SELECT * FROM test_plugin__users WHERE id = $1", [1]
        )

        assert row == {"id": 1, "name": "test"}

    @pytest.mark.asyncio
    async def test_select_one_returns_none(self, client, mock_nats):
        """Test select_one() returns None for no results."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [], "row_count": 0}
        )

        row = await client.select_one(
            "SELECT * FROM test_plugin__users WHERE id = $1", [999]
        )

        assert row is None

    @pytest.mark.asyncio
    async def test_select_one_sets_max_rows(self, client, mock_nats):
        """Test select_one() sets max_rows=1."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [], "row_count": 0}
        )

        await client.select_one("SELECT * FROM test")

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["max_rows"] == 1

    # Insert tests

    @pytest.mark.asyncio
    async def test_insert_sets_allow_write(self, client, mock_nats):
        """Test insert() sets allow_write=True."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 1})

        await client.insert(
            "INSERT INTO test_plugin__events (data) VALUES ($1)", ["test"]
        )

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["allow_write"] is True

    @pytest.mark.asyncio
    async def test_insert_returns_row_count(self, client, mock_nats):
        """Test insert() returns inserted count."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 1})

        count = await client.insert(
            "INSERT INTO test_plugin__events (data) VALUES ($1)", ["test"]
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_insert_many_multiple_rows(self, client, mock_nats):
        """Test insert_many() handles multiple rows."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 1})

        count = await client.insert_many(
            "INSERT INTO test_plugin__events (data) VALUES ($1)",
            [["row1"], ["row2"], ["row3"]],
        )

        assert count == 3
        assert mock_nats.request.call_count == 3

    # Update tests

    @pytest.mark.asyncio
    async def test_update_returns_affected_count(self, client, mock_nats):
        """Test update() returns affected count."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 5})

        count = await client.update(
            "UPDATE test_plugin__users SET score = $1 WHERE active = $2", [100, True]
        )

        assert count == 5

    @pytest.mark.asyncio
    async def test_update_sets_allow_write(self, client, mock_nats):
        """Test update() sets allow_write=True."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 0})

        await client.update("UPDATE test_plugin__users SET score = $1", [100])

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["allow_write"] is True

    # Delete tests

    @pytest.mark.asyncio
    async def test_delete_returns_deleted_count(self, client, mock_nats):
        """Test delete() returns deleted count."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 3})

        count = await client.delete(
            "DELETE FROM test_plugin__events WHERE timestamp < $1", ["2024-01-01"]
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_delete_sets_allow_write(self, client, mock_nats):
        """Test delete() sets allow_write=True."""
        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 0})

        await client.delete("DELETE FROM test_plugin__events WHERE id = $1", [1])

        payload = json.loads(mock_nats.request.call_args[0][1].decode("utf-8"))
        assert payload["allow_write"] is True

    # Rate limiting tests

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, mock_nats):
        """Test rate limit is checked before query."""
        from lib.storage.sql_rate_limit import SQLRateLimiter

        limiter = SQLRateLimiter(default_limit=1, window_seconds=60)
        client = SQLClient(mock_nats, "test-plugin", rate_limiter=limiter)

        mock_nats.request.return_value = self._make_response({"rows": [], "row_count": 0})

        # First request should succeed
        await client.execute("SELECT 1")

        # Second request should fail due to rate limit
        with pytest.raises(RateLimitError):
            await client.execute("SELECT 2")

    # Metrics tests

    @pytest.mark.asyncio
    async def test_get_metrics(self, client, mock_nats):
        """Test metrics collection."""
        mock_nats.request.return_value = self._make_response(
            {"rows": [], "row_count": 0, "execution_time_ms": 10.0}
        )

        await client.execute("SELECT 1")
        await client.execute("SELECT 2")

        metrics = client.get_metrics()

        assert metrics["plugin"] == "test-plugin"
        assert metrics["query_count"] == 2
        assert metrics["error_count"] == 0

    @pytest.mark.asyncio
    async def test_metrics_track_errors(self, client, mock_nats):
        """Test error metrics are tracked."""
        mock_nats.request.return_value = self._make_response(
            {"error": {"code": "SYNTAX_ERROR", "message": "Invalid", "details": {}}}
        )

        try:
            await client.execute("INVALID SQL")
        except SQLSyntaxError:
            pass

        metrics = client.get_metrics()

        assert metrics["error_count"] == 1

    def test_reset_metrics(self, client, mock_nats):
        """Test resetting metrics."""
        client._query_count = 10
        client._error_count = 2
        client._total_time_ms = 100.0

        client.reset_metrics()

        metrics = client.get_metrics()
        assert metrics["query_count"] == 0
        assert metrics["error_count"] == 0
