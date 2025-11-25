"""
Unit tests for the SQL Execution Handler (NATS integration).

Tests the SQLExecutionHandler class that exposes SQL execution via NATS messaging.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from lib.storage.sql_handler import (
    SQLExecutionHandler,
    extract_plugin_from_subject,
)
from lib.storage.sql_errors import (
    RequestValidationError,
    SQLValidationError,
    ForbiddenStatementError,
    ParameterError,
    ExecutionError,
    TimeoutError as SQLTimeoutError,
    PermissionDeniedError,
)


# =============================================================================
# Test extract_plugin_from_subject
# =============================================================================


class TestExtractPluginFromSubject:
    """Tests for the extract_plugin_from_subject helper function."""

    def test_valid_subject_extracts_plugin(self) -> None:
        """Test extracting plugin name from valid subject."""
        assert extract_plugin_from_subject("rosey.db.sql.quotes.execute") == "quotes"
        assert extract_plugin_from_subject("rosey.db.sql.polls.execute") == "polls"
        assert extract_plugin_from_subject("rosey.db.sql.chat_logs.execute") == "chat_logs"

    def test_hyphenated_plugin_name(self) -> None:
        """Test extracting hyphenated plugin names."""
        assert extract_plugin_from_subject("rosey.db.sql.my-plugin.execute") == "my-plugin"

    def test_underscored_plugin_name(self) -> None:
        """Test extracting underscored plugin names."""
        assert extract_plugin_from_subject("rosey.db.sql.my_plugin.execute") == "my_plugin"

    def test_numeric_plugin_name(self) -> None:
        """Test extracting plugin names with numbers."""
        assert extract_plugin_from_subject("rosey.db.sql.plugin123.execute") == "plugin123"

    def test_short_subject_raises_error(self) -> None:
        """Test that short subjects raise ValueError."""
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("rosey.db.sql")
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("rosey.db")
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("")

    def test_wrong_prefix_raises_error(self) -> None:
        """Test that wrong prefix raises ValueError."""
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("other.db.sql.plugin.execute")
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("rosey.other.sql.plugin.execute")

    def test_wrong_suffix_raises_error(self) -> None:
        """Test that wrong suffix raises ValueError."""
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("rosey.db.sql.plugin.query")
        with pytest.raises(ValueError, match="Invalid subject format"):
            extract_plugin_from_subject("rosey.db.sql.plugin.run")


# =============================================================================
# Test Handler Initialization
# =============================================================================


class TestSQLExecutionHandlerInit:
    """Tests for SQLExecutionHandler initialization."""

    def test_init_with_defaults(self) -> None:
        """Test handler initialization with default config."""
        nats_client = MagicMock()
        database = MagicMock()

        handler = SQLExecutionHandler(
            nats_client=nats_client,
            database=database,
        )

        assert handler.nats_client is nats_client
        assert handler.database is database
        assert handler.config == {}
        assert handler.request_count == 0
        assert handler.error_count == 0

    def test_init_with_custom_config(self) -> None:
        """Test handler initialization with custom config."""
        nats_client = MagicMock()
        database = MagicMock()
        config = {
            "default_timeout_ms": 5000,
            "default_max_rows": 500,
        }

        handler = SQLExecutionHandler(
            nats_client=nats_client,
            database=database,
            config=config,
        )

        assert handler.config == config
        assert handler.config["default_timeout_ms"] == 5000
        assert handler.config["default_max_rows"] == 500

    def test_init_creates_pipeline_components(self) -> None:
        """Test handler creates all pipeline components."""
        handler = SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )

        assert handler.validator is not None
        assert handler.binder is not None
        assert handler.executor is not None
        assert handler.formatter is not None


# =============================================================================
# Test Request Validation
# =============================================================================


class TestRequestValidation:
    """Tests for _validate_request method."""

    @pytest.fixture
    def handler(self) -> SQLExecutionHandler:
        """Create a handler for testing."""
        return SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )

    def test_valid_minimal_request(self, handler: SQLExecutionHandler) -> None:
        """Test validating a minimal valid request."""
        data = {"query": "SELECT * FROM users"}
        result = handler._validate_request(data)

        assert result["query"] == "SELECT * FROM users"
        assert result["params"] == []
        assert result["allow_write"] is False
        assert result["timeout_ms"] == SQLExecutionHandler.DEFAULT_TIMEOUT_MS
        assert result["max_rows"] == SQLExecutionHandler.DEFAULT_MAX_ROWS

    def test_valid_full_request(self, handler: SQLExecutionHandler) -> None:
        """Test validating a request with all options."""
        data = {
            "query": "SELECT * FROM users WHERE id = $1",
            "params": [42],
            "allow_write": True,
            "timeout_ms": 5000,
            "max_rows": 100,
        }
        result = handler._validate_request(data)

        assert result["query"] == "SELECT * FROM users WHERE id = $1"
        assert result["params"] == [42]
        assert result["allow_write"] is True
        assert result["timeout_ms"] == 5000
        assert result["max_rows"] == 100

    def test_missing_query_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that missing query raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({})
        assert "query" in str(exc_info.value).lower()

    def test_empty_query_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that empty query raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": ""})
        assert "query" in str(exc_info.value).lower()

    def test_whitespace_query_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that whitespace-only query raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "   "})
        assert "query" in str(exc_info.value).lower()

    def test_non_string_query_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that non-string query raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": 123})
        assert "string" in str(exc_info.value).lower()

    def test_non_list_params_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that non-list params raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "params": "not a list"})
        assert "list" in str(exc_info.value).lower()

    def test_non_bool_allow_write_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that non-boolean allow_write raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "allow_write": "yes"})
        assert "boolean" in str(exc_info.value).lower()

    def test_non_int_timeout_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that non-integer timeout_ms raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "timeout_ms": "fast"})
        assert "integer" in str(exc_info.value).lower()

    def test_timeout_below_min_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that timeout_ms below minimum raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "timeout_ms": 50})
        assert "100" in str(exc_info.value)  # Minimum is 100

    def test_timeout_above_max_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that timeout_ms above maximum raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "timeout_ms": 60000})
        assert "30000" in str(exc_info.value)  # Maximum is 30000

    def test_non_int_max_rows_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that non-integer max_rows raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "max_rows": "all"})
        assert "integer" in str(exc_info.value).lower()

    def test_max_rows_below_min_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that max_rows below minimum raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "max_rows": 0})
        assert "1" in str(exc_info.value)  # Minimum is 1

    def test_max_rows_above_max_raises_error(self, handler: SQLExecutionHandler) -> None:
        """Test that max_rows above maximum raises RequestValidationError."""
        with pytest.raises(RequestValidationError) as exc_info:
            handler._validate_request({"query": "SELECT 1", "max_rows": 200000})
        assert "100000" in str(exc_info.value)  # Maximum is 100000

    def test_request_with_various_param_types(self, handler: SQLExecutionHandler) -> None:
        """Test request validation with various parameter types."""
        data = {
            "query": "INSERT INTO test VALUES ($1, $2, $3, $4)",
            "params": [42, "text", 3.14, None],
            "allow_write": True,
        }
        result = handler._validate_request(data)
        assert result["params"] == [42, "text", 3.14, None]

    def test_custom_config_affects_defaults(self) -> None:
        """Test that custom config affects default values."""
        handler = SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
            config={"default_timeout_ms": 3000, "default_max_rows": 500},
        )

        result = handler._validate_request({"query": "SELECT 1"})
        assert result["timeout_ms"] == 3000
        assert result["max_rows"] == 500


# =============================================================================
# Test Error Formatting
# =============================================================================


class TestErrorFormatting:
    """Tests for _format_error method."""

    @pytest.fixture
    def handler(self) -> SQLExecutionHandler:
        """Create a handler for testing."""
        return SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )

    def test_format_validation_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting RequestValidationError."""
        error = RequestValidationError("Invalid query format")
        request = {"query": "bad query"}
        
        result = handler._format_error(error, request, "test_plugin")
        
        # Result should contain error info
        assert "error" in result or "message" in result

    def test_format_sql_validation_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting SQL validation errors."""
        error = SQLValidationError("SYNTAX_ERROR", "Invalid SQL syntax")
        request = {"query": "SELEKT * FROM users"}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_forbidden_statement_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting ForbiddenStatementError."""
        error = ForbiddenStatementError("FORBIDDEN_STATEMENT", "DROP TABLE not allowed")
        request = {"query": "DROP TABLE users"}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_parameter_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting ParameterError."""
        error = ParameterError("PARAMETER_ERROR", "Parameter count mismatch")
        request = {"query": "SELECT $1, $2", "params": [1]}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_timeout_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting timeout errors."""
        error = SQLTimeoutError("Query exceeded timeout", timeout_ms=1000)
        request = {"query": "SELECT * FROM large_table", "timeout_ms": 1000}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_permission_denied_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting PermissionDeniedError."""
        error = PermissionDeniedError("Write not allowed")
        request = {"query": "DELETE FROM users", "allow_write": False}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_execution_error(self, handler: SQLExecutionHandler) -> None:
        """Test formatting ExecutionError."""
        error = ExecutionError("Database error")
        request = {"query": "SELECT * FROM missing_table"}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result

    def test_format_generic_exception(self, handler: SQLExecutionHandler) -> None:
        """Test formatting generic exceptions."""
        error = RuntimeError("Something unexpected")
        request = {"query": "SELECT 1"}
        
        result = handler._format_error(error, request, "test_plugin")
        
        assert "error" in result or "message" in result


# =============================================================================
# Test Handler Start/Stop
# =============================================================================


class TestHandlerLifecycle:
    """Tests for handler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_nats(self) -> None:
        """Test that start() subscribes to NATS subject."""
        nats_client = AsyncMock()
        mock_subscription = MagicMock()
        nats_client.subscribe.return_value = mock_subscription
        
        handler = SQLExecutionHandler(
            nats_client=nats_client,
            database=MagicMock(),
        )
        
        await handler.start()
        
        nats_client.subscribe.assert_called_once()
        call_args = nats_client.subscribe.call_args
        assert call_args[0][0] == "rosey.db.sql.*.execute"
        assert handler.subscription is mock_subscription

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_from_nats(self) -> None:
        """Test that stop() unsubscribes from NATS."""
        nats_client = AsyncMock()
        mock_subscription = AsyncMock()
        nats_client.subscribe.return_value = mock_subscription
        
        handler = SQLExecutionHandler(
            nats_client=nats_client,
            database=MagicMock(),
        )
        
        await handler.start()
        await handler.stop()
        
        mock_subscription.unsubscribe.assert_called_once()
        assert handler.subscription is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        """Test that stop() without start() is safe."""
        handler = SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )
        
        # Should not raise
        await handler.stop()


# =============================================================================
# Test Message Handling
# =============================================================================


class TestHandleExecute:
    """Tests for handle_execute method."""

    @pytest.fixture
    def handler(self) -> SQLExecutionHandler:
        """Create a handler for testing with mocked dependencies."""
        handler = SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )
        return handler

    def _make_msg(self, subject: str, data: dict) -> MagicMock:
        """Create a mock NATS message."""
        msg = MagicMock()
        msg.subject = subject
        msg.data = json.dumps(data).encode("utf-8")
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_handle_invalid_json_responds_error(self, handler: SQLExecutionHandler) -> None:
        """Test handling of invalid JSON in request."""
        msg = MagicMock()
        msg.subject = "rosey.db.sql.test.execute"
        msg.data = b"not valid json"
        msg.respond = AsyncMock()
        
        await handler.handle_execute(msg)
        
        msg.respond.assert_called_once()
        response = json.loads(msg.respond.call_args[0][0])
        # Should contain error information
        assert "error" in response or "message" in response

    @pytest.mark.asyncio
    async def test_handle_invalid_subject_responds_error(self, handler: SQLExecutionHandler) -> None:
        """Test handling of invalid subject format."""
        msg = self._make_msg("bad.subject", {"query": "SELECT 1"})
        
        await handler.handle_execute(msg)
        
        msg.respond.assert_called_once()
        response = json.loads(msg.respond.call_args[0][0])
        assert "error" in response or "message" in response

    @pytest.mark.asyncio
    async def test_handle_missing_query_responds_error(self, handler: SQLExecutionHandler) -> None:
        """Test handling of missing query in request."""
        msg = self._make_msg("rosey.db.sql.test.execute", {})
        
        await handler.handle_execute(msg)
        
        msg.respond.assert_called_once()
        response = json.loads(msg.respond.call_args[0][0])
        assert "error" in response or "message" in response

    @pytest.mark.asyncio
    async def test_handle_execute_success(self, handler: SQLExecutionHandler) -> None:
        """Test successful query execution."""
        msg = self._make_msg(
            "rosey.db.sql.quotes.execute",
            {"query": "SELECT id, text FROM quotes WHERE id = $1", "params": [1]},
        )
        
        # Mock the internal execution pipeline
        with patch.object(handler, "_execute_query", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "rows": [{"id": 1, "text": "Test quote"}],
                "row_count": 1,
                "execution_time_ms": 5.2,
                "truncated": False,
            }
            
            await handler.handle_execute(msg)
        
        msg.respond.assert_called_once()
        response = json.loads(msg.respond.call_args[0][0])
        assert response["rows"] == [{"id": 1, "text": "Test quote"}]
        assert response["row_count"] == 1

    @pytest.mark.asyncio
    async def test_handle_execute_tracks_plugin(self, handler: SQLExecutionHandler) -> None:
        """Test that plugin is extracted from subject correctly."""
        msg = self._make_msg(
            "rosey.db.sql.my_custom_plugin.execute",
            {"query": "SELECT 1"},
        )
        
        with patch.object(handler, "_execute_query", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"rows": [], "row_count": 0}
            
            await handler.handle_execute(msg)
            
            # Check the plugin was passed correctly
            mock_exec.assert_called_once()
            assert mock_exec.call_args[0][0] == "my_custom_plugin"

    @pytest.mark.asyncio
    async def test_handle_execute_increments_request_count(self, handler: SQLExecutionHandler) -> None:
        """Test that request count is incremented."""
        msg = self._make_msg(
            "rosey.db.sql.test.execute",
            {"query": "SELECT 1"},
        )
        
        initial_count = handler.request_count
        
        with patch.object(handler, "_execute_query", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"rows": [], "row_count": 0}
            await handler.handle_execute(msg)
        
        assert handler.request_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_handle_execute_increments_error_count_on_failure(self, handler: SQLExecutionHandler) -> None:
        """Test that error count is incremented on failure."""
        msg = MagicMock()
        msg.subject = "rosey.db.sql.test.execute"
        msg.data = b"invalid json"
        msg.respond = AsyncMock()
        
        initial_error_count = handler.error_count
        
        await handler.handle_execute(msg)
        
        assert handler.error_count == initial_error_count + 1


# =============================================================================
# Test Metrics
# =============================================================================


class TestMetrics:
    """Tests for metrics tracking in handler."""

    @pytest.fixture
    def handler(self) -> SQLExecutionHandler:
        """Create a handler for testing."""
        return SQLExecutionHandler(
            nats_client=MagicMock(),
            database=MagicMock(),
        )

    def test_initial_metrics_are_zero(self, handler: SQLExecutionHandler) -> None:
        """Test that initial metrics are all zero."""
        metrics = handler.get_metrics()
        
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["error_rate"] == 0.0
        assert metrics["avg_execution_time_ms"] == 0.0

    def test_metrics_error_rate_calculation(self, handler: SQLExecutionHandler) -> None:
        """Test error rate calculation."""
        handler.request_count = 10
        handler.error_count = 2
        
        metrics = handler.get_metrics()
        
        assert metrics["error_rate"] == 0.2

    def test_metrics_avg_execution_time(self, handler: SQLExecutionHandler) -> None:
        """Test average execution time calculation."""
        handler.request_count = 4
        handler.total_execution_time_ms = 100.0
        
        metrics = handler.get_metrics()
        
        assert metrics["avg_execution_time_ms"] == 25.0
