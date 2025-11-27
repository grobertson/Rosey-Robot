"""
Unit tests for SQL Audit Logger.

Tests the SQLAuditLogger class including query logging, slow query
detection, and metrics collection.
"""

import logging
from unittest.mock import MagicMock

import pytest

from lib.storage.sql_audit import (
    AuditLogEntry,
    QueryMetrics,
    SQLAuditLogger,
)


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_to_dict_success(self):
        """Test to_dict for successful query."""
        entry = AuditLogEntry(
            timestamp="2025-01-01T00:00:00Z",
            plugin="test-plugin",
            query_hash="abc123",
            query_preview="SELECT * FROM...",
            param_count=2,
            execution_time_ms=15.5,
            status="success",
            row_count=10,
            truncated=False,
        )

        d = entry.to_dict()

        assert d["timestamp"] == "2025-01-01T00:00:00Z"
        assert d["plugin"] == "test-plugin"
        assert d["query_hash"] == "abc123"
        assert d["row_count"] == 10
        assert d["status"] == "success"
        assert "error_type" not in d  # None values excluded

    def test_to_dict_error(self):
        """Test to_dict for failed query."""
        entry = AuditLogEntry(
            timestamp="2025-01-01T00:00:00Z",
            plugin="test-plugin",
            query_hash="abc123",
            query_preview="SELECT * FROM...",
            param_count=2,
            execution_time_ms=5.0,
            status="error",
            error_type="SQLValidationError",
            error_message="Invalid syntax",
            error_code="SYNTAX_ERROR",
        )

        d = entry.to_dict()

        assert d["status"] == "error"
        assert d["error_type"] == "SQLValidationError"
        assert d["error_code"] == "SYNTAX_ERROR"


class TestQueryMetrics:
    """Tests for QueryMetrics dataclass."""

    def test_initial_values(self):
        """Test initial metric values."""
        metrics = QueryMetrics()

        assert metrics.total_queries == 0
        assert metrics.total_errors == 0
        assert metrics.total_slow_queries == 0
        assert metrics.avg_execution_time_ms == 0.0

    def test_record_success(self):
        """Test recording successful query."""
        metrics = QueryMetrics()

        metrics.record(10.0, is_error=False, is_slow=False)

        assert metrics.total_queries == 1
        assert metrics.total_errors == 0
        assert metrics.avg_execution_time_ms == 10.0

    def test_record_error(self):
        """Test recording failed query."""
        metrics = QueryMetrics()

        metrics.record(5.0, is_error=True, is_slow=False)

        assert metrics.total_queries == 1
        assert metrics.total_errors == 1

    def test_record_slow(self):
        """Test recording slow query."""
        metrics = QueryMetrics()

        metrics.record(1000.0, is_error=False, is_slow=True)

        assert metrics.total_slow_queries == 1

    def test_record_multiple(self):
        """Test recording multiple queries."""
        metrics = QueryMetrics()

        metrics.record(10.0, is_error=False, is_slow=False)
        metrics.record(20.0, is_error=False, is_slow=False)
        metrics.record(30.0, is_error=False, is_slow=False)

        assert metrics.total_queries == 3
        assert metrics.avg_execution_time_ms == 20.0
        assert metrics.max_execution_time_ms == 30.0
        assert metrics.total_execution_time_ms == 60.0

    def test_to_dict(self):
        """Test metrics to_dict includes all fields."""
        metrics = QueryMetrics()
        metrics.record(10.0, is_error=False, is_slow=False)
        metrics.record(5.0, is_error=True, is_slow=False)

        d = metrics.to_dict()

        assert d["total_queries"] == 2
        assert d["total_errors"] == 1
        assert d["error_rate"] == 0.5


class TestSQLAuditLogger:
    """Tests for SQLAuditLogger class."""

    @pytest.fixture
    def logger(self):
        """Create logger with mock loggers."""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_slow_logger = MagicMock(spec=logging.Logger)
        return SQLAuditLogger(
            logger=mock_logger,
            slow_logger=mock_slow_logger,
            slow_query_threshold_ms=500.0,
        )

    # Initialization tests

    def test_init_defaults(self):
        """Test default initialization."""
        logger = SQLAuditLogger()

        assert logger.slow_threshold_ms == 500.0
        assert logger.max_param_length == 100

    def test_init_custom_threshold(self):
        """Test custom slow query threshold."""
        logger = SQLAuditLogger(slow_query_threshold_ms=100.0)

        assert logger.slow_threshold_ms == 100.0

    # Log query tests

    def test_log_query_success(self, logger):
        """Test logging successful query."""
        entry = logger.log_query(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__events WHERE id = $1",
            params=[123],
            row_count=10,
            execution_time_ms=15.0,
            truncated=False,
        )

        assert entry.plugin == "test-plugin"
        assert entry.status == "success"
        assert entry.row_count == 10
        assert entry.execution_time_ms == 15.0

        # Verify logger was called
        logger.logger.log.assert_called_once()

    def test_log_query_with_truncation(self, logger):
        """Test logging query with truncated results."""
        entry = logger.log_query(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__events",
            params=[],
            row_count=1000,
            execution_time_ms=50.0,
            truncated=True,
        )

        assert entry.truncated is True

    def test_log_query_slow(self, logger):
        """Test slow query is logged separately."""
        logger.log_query(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__events",
            params=[],
            row_count=100,
            execution_time_ms=600.0,  # Over 500ms threshold
            truncated=False,
        )

        # Should log to both regular and slow logger
        logger.logger.log.assert_called_once()
        logger.slow_logger.log.assert_called_once()

    def test_log_query_not_slow(self, logger):
        """Test fast query not logged as slow."""
        logger.log_query(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__events",
            params=[],
            row_count=10,
            execution_time_ms=100.0,  # Under threshold
            truncated=False,
        )

        # Should only log to regular logger
        logger.logger.log.assert_called_once()
        logger.slow_logger.log.assert_not_called()

    # Log error tests

    def test_log_error(self, logger):
        """Test logging query error."""
        error = ValueError("Test error")

        entry = logger.log_error(
            plugin="test-plugin",
            query="SELECT * FROM invalid",
            params=[],
            error=error,
            execution_time_ms=5.0,
        )

        assert entry.status == "error"
        assert entry.error_type == "ValueError"
        assert "Test error" in entry.error_message

        # Verify error logger was called
        logger.logger.error.assert_called_once()

    def test_log_error_with_code(self, logger):
        """Test logging error with code attribute."""

        class CodedError(Exception):
            code = "CUSTOM_ERROR"

        error = CodedError("Custom error")

        entry = logger.log_error(
            plugin="test-plugin",
            query="SELECT * FROM test",
            params=[],
            error=error,
            execution_time_ms=1.0,
        )

        assert entry.error_code == "CUSTOM_ERROR"

    # Query hash tests

    def test_query_hash_consistent(self, logger):
        """Test query hashing is consistent."""
        query = "SELECT * FROM test_plugin__events WHERE id = $1"

        entry1 = logger.log_query("p1", query, [], 0, 1.0)
        entry2 = logger.log_query("p2", query, [], 0, 1.0)

        assert entry1.query_hash == entry2.query_hash

    def test_query_hash_normalizes_whitespace(self, logger):
        """Test query hash normalizes whitespace."""
        query1 = "SELECT * FROM test"
        query2 = "SELECT  *  FROM   test"
        query3 = "select * from test"

        entry1 = logger.log_query("p", query1, [], 0, 1.0)
        entry2 = logger.log_query("p", query2, [], 0, 1.0)
        entry3 = logger.log_query("p", query3, [], 0, 1.0)

        # All should have same hash after normalization
        assert entry1.query_hash == entry2.query_hash
        assert entry2.query_hash == entry3.query_hash

    def test_query_hash_different_queries(self, logger):
        """Test different queries have different hashes."""
        entry1 = logger.log_query("p", "SELECT * FROM a", [], 0, 1.0)
        entry2 = logger.log_query("p", "SELECT * FROM b", [], 0, 1.0)

        assert entry1.query_hash != entry2.query_hash

    # Query preview tests

    def test_query_preview_truncation(self, logger):
        """Test long queries are truncated in preview."""
        long_query = "SELECT " + "a, " * 100 + "z FROM test"

        entry = logger.log_query("p", long_query, [], 0, 1.0)

        assert len(entry.query_preview) <= 103  # 100 + "..."
        assert entry.query_preview.endswith("...")

    def test_query_preview_short_query(self, logger):
        """Test short queries are not truncated."""
        short_query = "SELECT * FROM test"

        entry = logger.log_query("p", short_query, [], 0, 1.0)

        assert entry.query_preview == short_query

    # Parameter sanitization tests

    def test_param_sanitization_long_string(self, logger):
        """Test long string parameters are truncated."""
        long_param = "x" * 200

        # Trigger slow query to get sanitized params
        logger.log_query(
            plugin="test",
            query="SELECT * FROM test WHERE data = $1",
            params=[long_param],
            row_count=0,
            execution_time_ms=600.0,  # Trigger slow query
        )

        # Check the slow logger call
        call_args = logger.slow_logger.log.call_args
        slow_entry = call_args[1]["extra"]["slow_query"]

        # Params should be sanitized
        assert len(slow_entry["params"][0]) <= 103

    def test_param_sanitization_bytes(self, logger):
        """Test bytes parameters are represented safely."""
        bytes_param = b"x" * 200

        logger.log_query(
            plugin="test",
            query="SELECT * FROM test WHERE data = $1",
            params=[bytes_param],
            row_count=0,
            execution_time_ms=600.0,
        )

        call_args = logger.slow_logger.log.call_args
        slow_entry = call_args[1]["extra"]["slow_query"]

        # Bytes should be represented as <bytes:N>
        assert "<bytes:200>" in str(slow_entry["params"])

    # Metrics tests

    def test_get_metrics_global(self, logger):
        """Test global metrics collection."""
        logger.log_query("p1", "SELECT 1", [], 1, 10.0)
        logger.log_query("p2", "SELECT 2", [], 1, 20.0)

        metrics = logger.get_metrics()

        assert metrics.total_queries == 2
        assert metrics.avg_execution_time_ms == 15.0

    def test_get_metrics_per_plugin(self, logger):
        """Test per-plugin metrics."""
        logger.log_query("plugin-a", "SELECT 1", [], 1, 10.0)
        logger.log_query("plugin-a", "SELECT 2", [], 1, 20.0)
        logger.log_query("plugin-b", "SELECT 3", [], 1, 5.0)

        metrics_a = logger.get_metrics("plugin-a")
        metrics_b = logger.get_metrics("plugin-b")

        assert metrics_a.total_queries == 2
        assert metrics_b.total_queries == 1

    def test_get_metrics_unknown_plugin(self, logger):
        """Test metrics for unknown plugin returns empty."""
        metrics = logger.get_metrics("unknown")

        assert metrics.total_queries == 0

    def test_get_all_metrics(self, logger):
        """Test get_all_metrics returns all plugins."""
        logger.log_query("p1", "SELECT 1", [], 1, 10.0)
        logger.log_query("p2", "SELECT 2", [], 1, 20.0)

        all_metrics = logger.get_all_metrics()

        assert "global" in all_metrics
        assert "p1" in all_metrics
        assert "p2" in all_metrics

    def test_reset_metrics_all(self, logger):
        """Test resetting all metrics."""
        logger.log_query("p1", "SELECT 1", [], 1, 10.0)
        logger.log_query("p2", "SELECT 2", [], 1, 20.0)

        logger.reset_metrics()

        assert logger.get_metrics().total_queries == 0
        assert logger.get_metrics("p1").total_queries == 0

    def test_reset_metrics_single_plugin(self, logger):
        """Test resetting single plugin metrics."""
        logger.log_query("p1", "SELECT 1", [], 1, 10.0)
        logger.log_query("p2", "SELECT 2", [], 1, 20.0)

        logger.reset_metrics("p1")

        # p1 should be reset, p2 should remain
        assert logger.get_metrics("p1").total_queries == 0
        assert logger.get_metrics("p2").total_queries == 1

    # Error metrics tests

    def test_error_metrics(self, logger):
        """Test error metrics are tracked."""
        logger.log_query("p", "SELECT 1", [], 1, 10.0)
        logger.log_error("p", "SELECT invalid", [], ValueError("Error"), 5.0)

        metrics = logger.get_metrics("p")

        assert metrics.total_queries == 2
        assert metrics.total_errors == 1

    # Slow query metrics tests

    def test_slow_query_metrics(self, logger):
        """Test slow query metrics are tracked."""
        logger.log_query("p", "SELECT 1", [], 1, 100.0)  # Fast
        logger.log_query("p", "SELECT 2", [], 1, 600.0)  # Slow

        metrics = logger.get_metrics("p")

        assert metrics.total_queries == 2
        assert metrics.total_slow_queries == 1
