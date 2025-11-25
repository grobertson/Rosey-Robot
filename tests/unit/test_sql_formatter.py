"""
Unit tests for ResultFormatter.

Tests cover:
- Success result formatting
- Error result formatting
- JSON serialization of various types
- BLOB to base64 conversion
- Error code mapping
"""

import pytest

from lib.storage.sql_errors import (
    ExecutionError,
    ParameterError,
    PermissionDeniedError,
    TimeoutError,
)
from lib.storage.sql_formatter import ResultFormatter


class TestFormatSuccess:
    """Test successful result formatting."""

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create formatter instance."""
        return ResultFormatter()

    def test_format_simple_rows(self, formatter: ResultFormatter) -> None:
        """Basic rows formatted correctly."""
        rows = [
            {"id": 1, "username": "alice", "score": 100},
            {"id": 2, "username": "bob", "score": 75},
        ]

        result = formatter.format_success(
            rows=rows,
            row_count=2,
            execution_time_ms=15.3,
            truncated=False,
        )

        assert result["rows"] == rows
        assert result["row_count"] == 2
        assert result["execution_time_ms"] == 15.3
        assert result["truncated"] is False

    def test_format_empty_result(self, formatter: ResultFormatter) -> None:
        """Empty result set formatted correctly."""
        result = formatter.format_success(
            rows=[],
            row_count=0,
            execution_time_ms=5.1,
            truncated=False,
        )

        assert result["rows"] == []
        assert result["row_count"] == 0
        assert result["truncated"] is False

    def test_format_truncated_result(self, formatter: ResultFormatter) -> None:
        """Truncated results include flag."""
        rows = [{"id": i} for i in range(100)]

        result = formatter.format_success(
            rows=rows,
            row_count=100,
            execution_time_ms=250.5,
            truncated=True,
        )

        assert result["truncated"] is True
        assert result["row_count"] == 100

    def test_format_null_values(self, formatter: ResultFormatter) -> None:
        """NULL values preserved as None."""
        rows = [{"id": 1, "optional_field": None}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result["rows"][0]["optional_field"] is None

    def test_format_boolean_values(self, formatter: ResultFormatter) -> None:
        """Boolean values preserved."""
        rows = [{"id": 1, "active": True, "deleted": False}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result["rows"][0]["active"] is True
        assert result["rows"][0]["deleted"] is False

    def test_format_numeric_values(self, formatter: ResultFormatter) -> None:
        """Numeric values preserved."""
        rows = [{"int_val": 42, "float_val": 3.14159}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result["rows"][0]["int_val"] == 42
        assert result["rows"][0]["float_val"] == 3.14159


class TestBlobSerialization:
    """Test BLOB (bytes) to base64 conversion."""

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create formatter instance."""
        return ResultFormatter()

    def test_blob_converted_to_base64(self, formatter: ResultFormatter) -> None:
        """Bytes converted to base64 string."""
        rows = [{"id": 1, "data": b"binary data"}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        # "binary data" in base64
        assert result["rows"][0]["data"] == "YmluYXJ5IGRhdGE="
        assert isinstance(result["rows"][0]["data"], str)

    def test_empty_blob(self, formatter: ResultFormatter) -> None:
        """Empty bytes converted to empty base64."""
        rows = [{"id": 1, "data": b""}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        assert result["rows"][0]["data"] == ""

    def test_binary_blob(self, formatter: ResultFormatter) -> None:
        """Binary data with non-printable chars converted."""
        rows = [{"id": 1, "data": b"\x00\x01\x02\xff"}]

        result = formatter.format_success(
            rows=rows,
            row_count=1,
            execution_time_ms=10.0,
            truncated=False,
        )

        # Verify it's base64 decodable
        import base64
        decoded = base64.b64decode(result["rows"][0]["data"])
        assert decoded == b"\x00\x01\x02\xff"


class TestFormatError:
    """Test error result formatting."""

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create formatter instance."""
        return ResultFormatter()

    def test_format_timeout_error(self, formatter: ResultFormatter) -> None:
        """Timeout error formatted with code and details."""
        error = TimeoutError(
            "Query exceeded timeout",
            timeout_ms=10000,
        )

        result = formatter.format_error(
            error=error,
            query="SELECT * FROM large_table",
            params=["param1"],
            plugin="test-plugin",
        )

        assert result["error"] == "TIMEOUT"
        assert "timeout" in result["message"].lower()
        assert result["details"]["plugin"] == "test-plugin"
        assert result["details"]["param_count"] == 1
        assert result["details"]["timeout_ms"] == 10000

    def test_format_permission_error(self, formatter: ResultFormatter) -> None:
        """Permission denied error formatted correctly."""
        error = PermissionDeniedError(
            "INSERT requires allow_write=True",
            required_permission="allow_write",
        )

        result = formatter.format_error(
            error=error,
            query="INSERT INTO t VALUES (?)",
            params=["alice"],
            plugin="test-plugin",
        )

        assert result["error"] == "PERMISSION_DENIED"
        assert "allow_write" in result["message"].lower()
        assert result["details"]["permission"] == "allow_write"

    def test_format_execution_error(self, formatter: ResultFormatter) -> None:
        """Execution error formatted correctly."""
        error = ExecutionError(
            "Unique constraint violation",
            original_error=Exception("original"),
            details={"constraint_type": "unique"},
        )

        result = formatter.format_error(
            error=error,
            query="INSERT INTO users (username) VALUES (?)",
            params=["alice"],
            plugin="test-plugin",
        )

        assert result["error"] == "EXECUTION_ERROR"
        assert "constraint" in result["message"].lower()
        assert result["details"]["error_type"] == "ExecutionError"

    def test_format_parameter_error(self, formatter: ResultFormatter) -> None:
        """Parameter error formatted correctly."""
        error = ParameterError(
            "PARAM_COUNT_MISMATCH",
            "Query uses $3 but only 2 params provided",
        )

        result = formatter.format_error(
            error=error,
            query="SELECT * FROM t WHERE x = $1 AND y = $2 AND z = $3",
            params=["a", "b"],
            plugin="test-plugin",
        )

        assert result["error"] == "PARAM_ERROR"  # Maps to PARAM_ERROR in formatter
        assert result["details"]["param_count"] == 2

    def test_format_unknown_error(self, formatter: ResultFormatter) -> None:
        """Unknown errors get UNKNOWN_ERROR code."""
        error = ValueError("Something unexpected")

        result = formatter.format_error(
            error=error,
            query="SELECT 1",
            params=[],
            plugin="test-plugin",
        )

        assert result["error"] == "UNKNOWN_ERROR"


class TestQueryTruncation:
    """Test query truncation in error responses."""

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create formatter instance."""
        return ResultFormatter()

    def test_short_query_not_truncated(self, formatter: ResultFormatter) -> None:
        """Short queries not truncated."""
        short_query = "SELECT * FROM users"
        error = ExecutionError("Error")

        result = formatter.format_error(
            error=error,
            query=short_query,
            params=[],
            plugin="test",
        )

        assert result["details"]["query_preview"] == short_query

    def test_long_query_truncated(self, formatter: ResultFormatter) -> None:
        """Long queries truncated with ellipsis."""
        long_query = "SELECT " + "x, " * 200 + "y FROM table_name"
        error = ExecutionError("Error")

        result = formatter.format_error(
            error=error,
            query=long_query,
            params=[],
            plugin="test",
        )

        assert len(result["details"]["query_preview"]) <= 203  # 200 + "..."
        assert result["details"]["query_preview"].endswith("...")


class TestMakeSerializable:
    """Test internal serialization method."""

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create formatter instance."""
        return ResultFormatter()

    def test_none_unchanged(self, formatter: ResultFormatter) -> None:
        """None passes through unchanged."""
        assert formatter._make_serializable(None) is None

    def test_string_unchanged(self, formatter: ResultFormatter) -> None:
        """Strings pass through unchanged."""
        assert formatter._make_serializable("hello") == "hello"

    def test_int_unchanged(self, formatter: ResultFormatter) -> None:
        """Integers pass through unchanged."""
        assert formatter._make_serializable(42) == 42

    def test_float_unchanged(self, formatter: ResultFormatter) -> None:
        """Floats pass through unchanged."""
        assert formatter._make_serializable(3.14) == 3.14

    def test_bool_unchanged(self, formatter: ResultFormatter) -> None:
        """Booleans pass through unchanged."""
        assert formatter._make_serializable(True) is True
        assert formatter._make_serializable(False) is False

    def test_bytes_to_base64(self, formatter: ResultFormatter) -> None:
        """Bytes converted to base64."""
        result = formatter._make_serializable(b"test")
        assert result == "dGVzdA=="

    def test_unknown_type_to_string(self, formatter: ResultFormatter) -> None:
        """Unknown types converted to string."""

        class CustomType:
            def __str__(self) -> str:
                return "custom_value"

        result = formatter._make_serializable(CustomType())
        assert result == "custom_value"
