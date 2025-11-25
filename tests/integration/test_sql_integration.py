"""
Integration tests for parameterized SQL execution stack.

Tests the complete flow from PostgreSQL-style queries through
parameter binding, execution, and result formatting.
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from lib.storage import (
    ExecutionError,
    ParameterBinder,
    PermissionDeniedError,
    PreparedStatementExecutor,
    ResultFormatter,
    TimeoutError,
)


class MockRow:
    """Mock SQLAlchemy row object."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._mapping = data


class MockResult:
    """Mock SQLAlchemy result object."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        rowcount: int = 0,
    ) -> None:
        self._rows = [MockRow(r) for r in (rows or [])]
        self.rowcount = rowcount

    def fetchall(self) -> list[MockRow]:
        return self._rows


class MockSession:
    """Mock async database session."""

    def __init__(
        self,
        result: MockResult | None = None,
    ) -> None:
        self._result = result or MockResult()
        self._executed_queries: list[tuple[str, dict[int, Any]]] = []

    async def execute(
        self,
        query: Any,
        params: dict[int, Any] | None = None,
    ) -> MockResult:
        # Store the query and params for verification
        self._executed_queries.append((str(query), params or {}))
        return self._result

    async def commit(self) -> None:
        pass

    async def __aenter__(self) -> "MockSession":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        pass


class MockDatabase:
    """Mock database for testing."""

    def __init__(self, session: MockSession | None = None) -> None:
        self._session = session or MockSession()

    def _get_session(self) -> MockSession:
        return self._session


class TestFullStackSelect:
    """Test complete SELECT flow through all components."""

    @pytest.fixture
    def stack(self) -> dict[str, Any]:
        """Create full execution stack with mock database."""
        result = MockResult(
            rows=[
                {"id": 1, "username": "alice", "score": 100, "active": True},
                {"id": 2, "username": "bob", "score": 75, "active": False},
            ],
            rowcount=2,
        )
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)

        return {
            "binder": ParameterBinder(),
            "executor": PreparedStatementExecutor(mock_db),
            "formatter": ResultFormatter(),
            "session": session,
        }

    async def test_complete_select_flow(self, stack: dict[str, Any]) -> None:
        """Full SELECT flow from PostgreSQL-style query to formatted result."""
        # Step 1: PostgreSQL-style query
        query_pg = "SELECT * FROM test_plugin__users WHERE username = $1"
        params = ["alice"]

        # Step 2: Bind parameters
        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert query_sqlite == "SELECT * FROM test_plugin__users WHERE username = ?"
        assert param_tuple == ("alice",)

        # Step 3: Execute
        exec_result = await stack["executor"].execute(
            plugin="test-plugin",
            query=query_sqlite,
            params=param_tuple,
            timeout_ms=5000,
            max_rows=100,
        )

        assert exec_result["row_count"] == 2
        assert len(exec_result["rows"]) == 2
        assert exec_result["truncated"] is False

        # Step 4: Format
        formatted = stack["formatter"].format_success(
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
            execution_time_ms=exec_result["execution_time_ms"],
            truncated=exec_result["truncated"],
        )

        assert formatted["rows"][0]["username"] == "alice"
        assert formatted["rows"][0]["active"] is True  # Boolean preserved
        assert "execution_time_ms" in formatted

    async def test_select_with_multiple_params(self, stack: dict[str, Any]) -> None:
        """SELECT with multiple parameters bound correctly."""
        query_pg = "SELECT * FROM t WHERE x = $1 AND y = $2 AND z = $3"
        params = ["a", 42, True]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert query_sqlite == "SELECT * FROM t WHERE x = ? AND y = ? AND z = ?"
        assert param_tuple == ("a", 42, 1)  # True coerced to 1

        result = await stack["executor"].execute(
            plugin="test",
            query=query_sqlite,
            params=param_tuple,
        )

        assert result is not None

    async def test_select_with_reused_params(self, stack: dict[str, Any]) -> None:
        """Parameter reuse handled correctly."""
        query_pg = "SELECT * FROM t WHERE name = $1 OR alias = $1"
        params = ["alice"]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert query_sqlite == "SELECT * FROM t WHERE name = ? OR alias = ?"
        assert param_tuple == ("alice", "alice")  # Duplicated


class TestFullStackInsert:
    """Test complete INSERT flow through all components."""

    @pytest.fixture
    def stack(self) -> dict[str, Any]:
        """Create full execution stack for write operations."""
        result = MockResult(rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)

        return {
            "binder": ParameterBinder(),
            "executor": PreparedStatementExecutor(mock_db),
            "formatter": ResultFormatter(),
            "session": session,
        }

    async def test_complete_insert_flow(self, stack: dict[str, Any]) -> None:
        """Full INSERT flow from PostgreSQL-style query to formatted result."""
        query_pg = "INSERT INTO test_plugin__events (user_id, type, data) VALUES ($1, $2, $3)"
        params = ["alice", "login", {"ip": "127.0.0.1"}]

        # Bind
        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert "?" in query_sqlite
        # Dict should be JSON serialized
        assert param_tuple[2] == '{"ip": "127.0.0.1"}'

        # Execute with write permission
        exec_result = await stack["executor"].execute(
            plugin="test-plugin",
            query=query_sqlite,
            params=param_tuple,
            timeout_ms=5000,
            max_rows=100,
            allow_write=True,
        )

        assert exec_result["row_count"] == 1
        assert exec_result["rows"] == []

        # Format
        formatted = stack["formatter"].format_success(
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
            execution_time_ms=exec_result["execution_time_ms"],
            truncated=exec_result["truncated"],
        )

        assert formatted["row_count"] == 1


class TestErrorHandlingFlow:
    """Test error handling through full stack."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create parameter binder."""
        return ParameterBinder()

    @pytest.fixture
    def formatter(self) -> ResultFormatter:
        """Create result formatter."""
        return ResultFormatter()

    async def test_permission_denied_flow(
        self,
        binder: ParameterBinder,
        formatter: ResultFormatter,
    ) -> None:
        """Permission denied error flows through correctly."""
        result = MockResult(rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        query_pg = "INSERT INTO test_plugin__users (name) VALUES ($1)"
        params = ["alice"]

        query_sqlite, param_tuple = binder.bind(query_pg, params)

        try:
            await executor.execute(
                plugin="test-plugin",
                query=query_sqlite,
                params=param_tuple,
                allow_write=False,  # Permission denied
            )
            pytest.fail("Should have raised PermissionDeniedError")
        except PermissionDeniedError as e:
            # Format the error
            formatted = formatter.format_error(
                error=e,
                query=query_pg,
                params=params,
                plugin="test-plugin",
            )

            assert formatted["error"] == "PERMISSION_DENIED"
            assert formatted["details"]["permission"] == "allow_write"

    async def test_execution_error_flow(
        self,
        binder: ParameterBinder,
        formatter: ResultFormatter,
    ) -> None:
        """Execution error flows through correctly."""
        session = MockSession()
        session.execute = AsyncMock(
            side_effect=Exception("UNIQUE constraint failed")
        )
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        query_pg = "INSERT INTO test_plugin__users (id, name) VALUES ($1, $2)"
        params = [1, "alice"]

        query_sqlite, param_tuple = binder.bind(query_pg, params)

        try:
            await executor.execute(
                plugin="test-plugin",
                query=query_sqlite,
                params=param_tuple,
                allow_write=True,
            )
            pytest.fail("Should have raised ExecutionError")
        except ExecutionError as e:
            formatted = formatter.format_error(
                error=e,
                query=query_pg,
                params=params,
                plugin="test-plugin",
            )

            assert formatted["error"] == "EXECUTION_ERROR"
            assert "unique constraint" in formatted["message"].lower()


class TestTypeCoercionFlow:
    """Test type coercion through full stack."""

    @pytest.fixture
    def stack(self) -> dict[str, Any]:
        """Create full execution stack."""
        result = MockResult(rows=[{"result": "ok"}], rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)

        return {
            "binder": ParameterBinder(),
            "executor": PreparedStatementExecutor(mock_db),
            "formatter": ResultFormatter(),
        }

    async def test_datetime_coercion(self, stack: dict[str, Any]) -> None:
        """Datetime coerced to ISO string."""
        from datetime import datetime

        query_pg = "INSERT INTO t (created_at) VALUES ($1)"
        dt = datetime(2025, 1, 15, 10, 30, 0)
        params = [dt]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert param_tuple[0] == "2025-01-15T10:30:00"

    async def test_list_coercion(self, stack: dict[str, Any]) -> None:
        """List coerced to JSON string."""
        query_pg = "INSERT INTO t (tags) VALUES ($1)"
        params = [["python", "sql", "testing"]]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert param_tuple[0] == '["python", "sql", "testing"]'

    async def test_dict_coercion(self, stack: dict[str, Any]) -> None:
        """Dict coerced to JSON string."""
        query_pg = "INSERT INTO t (metadata) VALUES ($1)"
        params = [{"key": "value", "count": 42}]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        # JSON preserves key order in Python 3.7+
        assert '"key": "value"' in param_tuple[0]
        assert '"count": 42' in param_tuple[0]

    async def test_boolean_coercion(self, stack: dict[str, Any]) -> None:
        """Boolean coerced to 0/1."""
        query_pg = "INSERT INTO t (active, deleted) VALUES ($1, $2)"
        params = [True, False]

        query_sqlite, param_tuple = stack["binder"].bind(query_pg, params)

        assert param_tuple[0] == 1
        assert param_tuple[1] == 0


class TestResultWithBinaryData:
    """Test handling of binary data through full stack."""

    async def test_blob_in_results(self) -> None:
        """Binary data in results converted to base64."""
        result = MockResult(
            rows=[
                {"id": 1, "name": "file.bin", "data": b"\x00\x01\x02\xff"},
            ],
            rowcount=1,
        )
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)

        binder = ParameterBinder()
        executor = PreparedStatementExecutor(mock_db)
        formatter = ResultFormatter()

        query_pg = "SELECT * FROM test_plugin__files WHERE id = $1"
        params = [1]

        query_sqlite, param_tuple = binder.bind(query_pg, params)

        exec_result = await executor.execute(
            plugin="test-plugin",
            query=query_sqlite,
            params=param_tuple,
        )

        formatted = formatter.format_success(
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
            execution_time_ms=exec_result["execution_time_ms"],
            truncated=exec_result["truncated"],
        )

        # Binary data should be base64 encoded
        import base64

        decoded = base64.b64decode(formatted["rows"][0]["data"])
        assert decoded == b"\x00\x01\x02\xff"
