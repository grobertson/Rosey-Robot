"""
Unit tests for PreparedStatementExecutor.

Tests cover:
- Basic SELECT execution
- Write operations (INSERT, UPDATE, DELETE)
- Timeout enforcement
- Row limit enforcement and truncation
- Permission checking for write operations
- Error handling and translation
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.storage.sql_errors import (
    ExecutionError,
    PermissionDeniedError,
    TimeoutError,
)
from lib.storage.sql_executor import PreparedStatementExecutor


class MockRow:
    """Mock SQLAlchemy row object."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._mapping = data

    def _asdict(self) -> dict[str, Any]:
        return dict(self._mapping)


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
        execute_error: Exception | None = None,
    ) -> None:
        self._result = result or MockResult()
        self._execute_error = execute_error
        self._committed = False

    async def execute(
        self,
        query: Any,
        params: dict[int, Any] | None = None,
    ) -> MockResult:
        if self._execute_error:
            raise self._execute_error
        return self._result

    async def commit(self) -> None:
        self._committed = True

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

    def __init__(
        self,
        session: MockSession | None = None,
    ) -> None:
        self._session = session or MockSession()

    def _get_session(self) -> MockSession:
        return self._session


class TestBasicExecution:
    """Test basic query execution."""

    @pytest.fixture
    def mock_db(self) -> MockDatabase:
        """Create mock database."""
        result = MockResult(
            rows=[
                {"id": 1, "username": "alice", "score": 100},
                {"id": 2, "username": "bob", "score": 75},
            ],
            rowcount=2,
        )
        session = MockSession(result=result)
        return MockDatabase(session=session)

    @pytest.fixture
    def executor(self, mock_db: MockDatabase) -> PreparedStatementExecutor:
        """Create executor with mock database."""
        return PreparedStatementExecutor(mock_db)

    async def test_select_simple(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """Basic SELECT returns results."""
        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__users WHERE id = ?",
            params=(1,),
            timeout_ms=1000,
            max_rows=100,
        )

        assert result["row_count"] == 2
        assert len(result["rows"]) == 2
        assert result["rows"][0]["username"] == "alice"
        assert result["truncated"] is False
        assert "execution_time_ms" in result
        assert result["execution_time_ms"] >= 0

    async def test_select_empty(self) -> None:
        """SELECT with no results."""
        result = MockResult(rows=[], rowcount=0)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__users WHERE id = ?",
            params=(999,),
            timeout_ms=1000,
            max_rows=100,
        )

        assert result["row_count"] == 0
        assert result["rows"] == []
        assert result["truncated"] is False

    async def test_select_with_params(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """SELECT with multiple params."""
        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__users WHERE username = ? AND score > ?",
            params=("alice", 50),
            timeout_ms=1000,
            max_rows=100,
        )

        assert result["row_count"] == 2
        assert result["truncated"] is False


class TestWriteOperations:
    """Test INSERT, UPDATE, DELETE operations."""

    @pytest.fixture
    def mock_db_write(self) -> MockDatabase:
        """Create mock database for write ops."""
        result = MockResult(rowcount=1)
        session = MockSession(result=result)
        return MockDatabase(session=session)

    @pytest.fixture
    def executor(self, mock_db_write: MockDatabase) -> PreparedStatementExecutor:
        """Create executor with mock database."""
        return PreparedStatementExecutor(mock_db_write)

    async def test_insert_with_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """INSERT works with allow_write=True."""
        result = await executor.execute(
            plugin="test-plugin",
            query="INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
            params=("charlie", 80),
            timeout_ms=1000,
            max_rows=100,
            allow_write=True,
        )

        assert result["row_count"] == 1
        assert result["rows"] == []
        assert result["truncated"] is False

    async def test_insert_without_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """INSERT without allow_write raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="INSERT INTO test_plugin__users (username) VALUES (?)",
                params=("dave",),
                timeout_ms=1000,
                max_rows=100,
                allow_write=False,
            )

        assert "allow_write" in str(exc_info.value)
        assert exc_info.value.required_permission == "allow_write"

    async def test_update_with_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """UPDATE works with allow_write=True."""
        result = await executor.execute(
            plugin="test-plugin",
            query="UPDATE test_plugin__users SET score = ? WHERE username = ?",
            params=(150, "alice"),
            timeout_ms=1000,
            max_rows=100,
            allow_write=True,
        )

        assert result["row_count"] == 1
        assert result["rows"] == []

    async def test_update_without_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """UPDATE without allow_write raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            await executor.execute(
                plugin="test-plugin",
                query="UPDATE test_plugin__users SET score = ? WHERE id = ?",
                params=(200, 1),
                timeout_ms=1000,
                max_rows=100,
                allow_write=False,
            )

    async def test_delete_with_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """DELETE works with allow_write=True."""
        result = await executor.execute(
            plugin="test-plugin",
            query="DELETE FROM test_plugin__users WHERE username = ?",
            params=("charlie",),
            timeout_ms=1000,
            max_rows=100,
            allow_write=True,
        )

        assert result["row_count"] == 1
        assert result["rows"] == []

    async def test_delete_without_permission(
        self,
        executor: PreparedStatementExecutor,
    ) -> None:
        """DELETE without allow_write raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            await executor.execute(
                plugin="test-plugin",
                query="DELETE FROM test_plugin__users WHERE id = ?",
                params=(1,),
                timeout_ms=1000,
                max_rows=100,
                allow_write=False,
            )


class TestRowLimitEnforcement:
    """Test row limit and truncation."""

    async def test_results_truncated_at_limit(self) -> None:
        """Results truncated when exceeding max_rows."""
        # Create 100 rows
        rows = [{"id": i, "data": f"row_{i}"} for i in range(100)]
        result = MockResult(rows=rows, rowcount=100)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__data",
            params=(),
            timeout_ms=5000,
            max_rows=50,  # Limit to 50
        )

        assert result["row_count"] == 50
        assert len(result["rows"]) == 50
        assert result["truncated"] is True

    async def test_results_not_truncated_under_limit(self) -> None:
        """Results not truncated when under max_rows."""
        rows = [{"id": i} for i in range(30)]
        result = MockResult(rows=rows, rowcount=30)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__data",
            params=(),
            timeout_ms=5000,
            max_rows=100,
        )

        assert result["row_count"] == 30
        assert len(result["rows"]) == 30
        assert result["truncated"] is False

    async def test_results_exact_limit(self) -> None:
        """Results at exactly max_rows are not truncated."""
        rows = [{"id": i} for i in range(50)]
        result = MockResult(rows=rows, rowcount=50)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__data",
            params=(),
            timeout_ms=5000,
            max_rows=50,
        )

        assert result["row_count"] == 50
        assert result["truncated"] is False

    async def test_max_rows_clamped_to_bounds(self) -> None:
        """max_rows is clamped to valid range."""
        rows = [{"id": 1}]
        result = MockResult(rows=rows, rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        # max_rows=-10 should be clamped to MIN_MAX_ROWS (1)
        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM t",
            params=(),
            timeout_ms=1000,
            max_rows=-10,
        )

        assert result is not None  # Should not error


class TestTimeoutEnforcement:
    """Test timeout enforcement."""

    async def test_timeout_raises_error(self) -> None:
        """Query exceeding timeout raises TimeoutError."""

        async def slow_execute(*args: Any, **kwargs: Any) -> MockResult:
            await asyncio.sleep(0.5)  # 500ms delay
            return MockResult(rows=[{"id": 1}])

        session = MockSession()
        session.execute = slow_execute  # type: ignore[method-assign]
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        with pytest.raises(TimeoutError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="SELECT * FROM test_plugin__slow_table",
                params=(),
                timeout_ms=100,  # 100ms timeout (too short)
                max_rows=100,
            )

        assert exc_info.value.timeout_ms == 100

    async def test_completes_within_timeout(self) -> None:
        """Query completing before timeout succeeds."""
        result = MockResult(rows=[{"id": 1}], rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__users",
            params=(),
            timeout_ms=5000,  # 5 second timeout (plenty)
            max_rows=100,
        )

        assert result["row_count"] == 1

    async def test_timeout_clamped_to_bounds(self) -> None:
        """timeout_ms is clamped to valid range."""
        result = MockResult(rows=[{"id": 1}], rowcount=1)
        session = MockSession(result=result)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        # timeout_ms=1 should be clamped to MIN_TIMEOUT_MS (100)
        result = await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM t",
            params=(),
            timeout_ms=1,  # Too low, will be clamped
            max_rows=100,
        )

        assert result is not None  # Should succeed with clamped timeout


class TestErrorHandling:
    """Test error translation and handling."""

    async def test_unique_constraint_error(self) -> None:
        """Unique constraint violation translated correctly."""
        error = Exception("UNIQUE constraint failed: users.username")
        session = MockSession(execute_error=error)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        with pytest.raises(ExecutionError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="INSERT INTO t (username) VALUES (?)",
                params=("alice",),
                allow_write=True,
            )

        assert "unique constraint" in str(exc_info.value).lower()
        assert exc_info.value.details.get("constraint_type") == "unique"

    async def test_foreign_key_error(self) -> None:
        """Foreign key violation translated correctly."""
        error = Exception("FOREIGN KEY constraint failed")
        session = MockSession(execute_error=error)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        with pytest.raises(ExecutionError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="INSERT INTO orders (user_id) VALUES (?)",
                params=(999,),
                allow_write=True,
            )

        assert "foreign key" in str(exc_info.value).lower()

    async def test_database_locked_error(self) -> None:
        """Database locked translated correctly."""
        error = Exception("database is locked")
        session = MockSession(execute_error=error)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        with pytest.raises(ExecutionError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="SELECT * FROM t",
                params=(),
            )

        assert "locked" in str(exc_info.value).lower()
        assert exc_info.value.details.get("transient") is True

    async def test_generic_error(self) -> None:
        """Unknown errors wrapped in ExecutionError."""
        error = Exception("Some unexpected database error")
        session = MockSession(execute_error=error)
        mock_db = MockDatabase(session=session)
        executor = PreparedStatementExecutor(mock_db)

        with pytest.raises(ExecutionError) as exc_info:
            await executor.execute(
                plugin="test-plugin",
                query="SELECT * FROM t",
                params=(),
            )

        assert exc_info.value.original_error is error


class TestStatementTypeDetection:
    """Test statement type detection."""

    @pytest.fixture
    def executor(self) -> PreparedStatementExecutor:
        """Create executor for testing."""
        mock_db = MockDatabase()
        return PreparedStatementExecutor(mock_db)

    def test_detect_select(self, executor: PreparedStatementExecutor) -> None:
        """SELECT detected correctly."""
        assert executor._detect_statement_type("SELECT * FROM t") == "SELECT"
        assert executor._detect_statement_type("  SELECT * FROM t") == "SELECT"
        assert executor._detect_statement_type("select * from t") == "SELECT"

    def test_detect_insert(self, executor: PreparedStatementExecutor) -> None:
        """INSERT detected correctly."""
        assert executor._detect_statement_type("INSERT INTO t VALUES (1)") == "INSERT"

    def test_detect_update(self, executor: PreparedStatementExecutor) -> None:
        """UPDATE detected correctly."""
        assert executor._detect_statement_type("UPDATE t SET x = 1") == "UPDATE"

    def test_detect_delete(self, executor: PreparedStatementExecutor) -> None:
        """DELETE detected correctly."""
        assert executor._detect_statement_type("DELETE FROM t WHERE id = 1") == "DELETE"

    def test_detect_with(self, executor: PreparedStatementExecutor) -> None:
        """WITH (CTE) detected as SELECT-like."""
        assert executor._detect_statement_type("WITH cte AS (SELECT 1) SELECT * FROM cte") == "WITH"

    def test_detect_unknown(self, executor: PreparedStatementExecutor) -> None:
        """Unknown statements return UNKNOWN."""
        assert executor._detect_statement_type("PRAGMA table_info(t)") == "UNKNOWN"
        assert executor._detect_statement_type("CREATE TABLE t (x INT)") == "UNKNOWN"
