# SPEC: Sortie 2 - SQL Executor & Result Formatter

**Sprint**: 17-parameterized-sql  
**Sortie**: 2 of 5  
**Status**: Draft  
**Author**: Platform Team  
**Created**: November 24, 2025  
**Last Updated**: November 24, 2025

---

## 1. Overview

### 1.1 Purpose

Implement the execution layer for parameterized SQL queries:
- **Prepared Statement Executor**: Execute validated queries using SQLite prepared statements
- **Result Formatter**: Convert query results to JSON-serializable format with metadata

This sortie builds on Sortie 1's validation foundation to safely execute queries and return standardized results.

### 1.2 Scope

**In Scope**:
- Prepared statement execution with parameter binding
- Timeout enforcement using asyncio
- Row limit enforcement (default 10,000 rows)
- Result formatting (Row objects → JSON-compatible dicts)
- Execution metadata (row_count, execution_time_ms, truncated flag)
- Error handling and formatting
- SQLite error translation to meaningful error codes

**Out of Scope**:
- Query validation (completed in Sortie 1)
- NATS handler integration (Sortie 3)
- Client wrapper (Sortie 4)
- Security testing (Sortie 5)

### 1.3 Dependencies

**Prerequisites**:
- Sortie 1 (Query Validator & Parameter Binder) complete
- Database manager from Sprint 12-14
- `aiosqlite` library for async SQLite operations

**Dependent Sorties**:
- Sortie 3 (NATS Handler) depends on executor and formatter
- All subsequent sorties build on this execution layer

### 1.4 Success Criteria

- [ ] Prepared statements execute queries safely (no SQL injection possible)
- [ ] Parameter binding converts PostgreSQL $N syntax to SQLite ? syntax
- [ ] Timeout enforcement works (queries abort after configured limit)
- [ ] Row limit enforcement works (results truncated at max_rows)
- [ ] Results are JSON-serializable (no Python objects in output)
- [ ] Execution metadata accurate (row_count, execution_time_ms)
- [ ] 30+ unit tests pass
- [ ] Integration tests with real SQLite database pass

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-1: Prepared Statement Execution**
- Execute queries using SQLite prepared statements (cursor.execute with params)
- Never use string interpolation or concatenation
- Support SELECT, INSERT, UPDATE, DELETE statements
- Commit transactions for write operations
- Rollback on errors

**FR-2: Parameter Binding**
- Convert PostgreSQL-style $1, $2, $3 to SQLite ? placeholders
- Build parameter tuple in correct order
- Handle parameter reuse (e.g., WHERE x = $1 OR y = $1)
- Validate parameter count matches placeholder count
- Type coercion (string, int, float, bool, null)

**FR-3: Timeout Enforcement**
- Support configurable timeout (100ms - 30s)
- Default timeout: 10 seconds
- Use asyncio.timeout for async query execution
- Return TIMEOUT error code if exceeded
- Cancel query execution on timeout

**FR-4: Row Limit Enforcement**
- Support configurable max_rows (1 - 100,000)
- Default max_rows: 10,000
- Truncate results at limit
- Set truncated=true flag if more rows available
- Log warning when results truncated

**FR-5: Result Formatting**
- Convert SQLite Row objects to Python dicts
- Ensure all values are JSON-serializable
- Include column names as dict keys
- Handle NULL values (convert to None/null)
- Handle BLOB values (convert to base64 or error)

**FR-6: Execution Metadata**
- row_count: Number of rows returned (SELECT) or affected (INSERT/UPDATE/DELETE)
- execution_time_ms: Query duration in milliseconds
- truncated: Boolean indicating if results were truncated
- Include metadata in all success responses

**FR-7: Error Handling**
- Catch all SQLite exceptions
- Translate SQLite errors to meaningful error codes
- Include original error message in details
- Return standardized error format
- Preserve error context (query, params)

### 2.2 Non-Functional Requirements

**NFR-1: Performance**
- Execution overhead < 10ms for simple queries
- Parameter binding < 1ms
- Result formatting < 5ms for 1000 rows
- Memory efficient (stream large result sets)

**NFR-2: Security**
- NEVER use string interpolation
- ALWAYS use prepared statements
- Validate timeout and max_rows within bounds
- Log execution errors for monitoring

**NFR-3: Reliability**
- Handle database connection errors gracefully
- Retry transient errors (database locked)
- Clean up resources on timeout
- No database connection leaks

**NFR-4: Observability**
- Log slow queries (> 500ms)
- Log truncated results (warning level)
- Log execution errors (error level)
- Include query hash in logs for correlation

### 2.3 Technical Requirements

**TR-1: Dependencies**
- `aiosqlite` for async SQLite operations
- `asyncio` for timeout enforcement
- Database manager from Sprint 12-14
- Query validator from Sortie 1

**TR-2: Module Structure**
```
lib/db/
├── sql_executor.py       # PreparedStatementExecutor
├── sql_formatter.py      # ResultFormatter
├── sql_parameter.py      # ParameterBinder (from Sortie 1)
└── sql_validator.py      # QueryValidator (from Sortie 1)
```

**TR-3: Type Safety**
- Full type hints for all functions
- TypedDict for result format
- Proper exception types
- Async/await throughout

---

## 3. Design

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SQL Execution Flow                       │
└─────────────────────────────────────────────────────────────┘

1. Input: ValidatedQuery (from Sortie 1)
   ↓
2. ParameterBinder.bind()
   - Convert $1, $2, $3 → ?, ?, ?
   - Build parameter tuple
   ↓
3. PreparedStatementExecutor.execute()
   - Get database connection
   - Prepare statement
   - Execute with timeout
   - Fetch results with row limit
   ↓
4. ResultFormatter.format()
   - Convert Row → dict
   - Add metadata
   - Handle truncation
   ↓
5. Output: ExecutionResult
```

### 3.2 Component Design

#### 3.2.1 ParameterBinder (Enhanced from Sortie 1)

**Purpose**: Convert PostgreSQL-style $N placeholders to SQLite ? syntax

**Class Definition**:
```python
class ParameterBinder:
    """Bind parameters to SQL query placeholders."""
    
    def bind(
        self,
        query: str,
        params: list[Any]
    ) -> tuple[str, tuple[Any, ...]]:
        """
        Convert PostgreSQL $N placeholders to SQLite ? placeholders.
        
        Args:
            query: SQL query with $1, $2, $3 placeholders
            params: List of parameter values (0-indexed in Python, 1-indexed in SQL)
        
        Returns:
            Tuple of (sqlite_query, param_tuple)
        
        Raises:
            ValidationError: If parameter count mismatch
        
        Example:
            >>> binder = ParameterBinder()
            >>> query = "SELECT * FROM users WHERE id = $1 AND status = $2"
            >>> params = ["alice", "active"]
            >>> sqlite_query, param_tuple = binder.bind(query, params)
            >>> print(sqlite_query)
            "SELECT * FROM users WHERE id = ? AND status = ?"
            >>> print(param_tuple)
            ("alice", "active")
        """
```

**Implementation**:
```python
import re
from typing import Any

class ParameterBinder:
    def bind(
        self,
        query: str,
        params: list[Any]
    ) -> tuple[str, tuple[Any, ...]]:
        # Find all $N placeholders
        placeholders = re.findall(r'\$(\d+)', query)
        
        if not placeholders:
            # No parameters
            return query, ()
        
        # Convert to integers
        placeholder_nums = [int(p) for p in placeholders]
        max_param = max(placeholder_nums)
        
        # Validate parameter count
        if max_param > len(params):
            raise ValidationError(
                f"Query uses ${max_param} but only {len(params)} params provided"
            )
        
        # Replace $N with ? in order of appearance
        sqlite_query = query
        param_tuple_builder = []
        
        for placeholder_str in placeholders:
            placeholder_num = int(placeholder_str)
            # Replace first occurrence of $N with ?
            sqlite_query = sqlite_query.replace(
                f"${placeholder_str}",
                "?",
                1  # Only replace first occurrence
            )
            # Add corresponding parameter (1-indexed → 0-indexed)
            param_tuple_builder.append(params[placeholder_num - 1])
        
        return sqlite_query, tuple(param_tuple_builder)
```

**Edge Cases**:
- Empty params list: Return (query, ())
- Parameter reuse: `WHERE x = $1 OR y = $1` → Duplicate param in tuple
- Out-of-order placeholders: `WHERE x = $2 AND y = $1` → Order by appearance
- Missing parameters: Raise ValidationError

#### 3.2.2 PreparedStatementExecutor

**Purpose**: Execute queries safely using SQLite prepared statements

**Class Definition**:
```python
class PreparedStatementExecutor:
    """Execute SQL queries using prepared statements."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize executor.
        
        Args:
            db_manager: Database manager from Sprint 12-14
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    async def execute(
        self,
        plugin: str,
        query: str,
        params: tuple[Any, ...],
        timeout_ms: int = 10000,
        max_rows: int = 10000,
        allow_write: bool = False
    ) -> dict[str, Any]:
        """
        Execute SQL query with prepared statement.
        
        Args:
            plugin: Plugin name (for database connection)
            query: SQL query with ? placeholders (SQLite format)
            params: Parameter tuple matching placeholders
            timeout_ms: Query timeout in milliseconds
            max_rows: Maximum rows to return
            allow_write: Whether write operations are allowed
        
        Returns:
            ExecutionResult dict with rows, metadata
        
        Raises:
            TimeoutError: Query exceeded timeout
            PermissionDeniedError: Write operation without allow_write
            ExecutionError: Database error during execution
        """
```

**Implementation**:
```python
import asyncio
import time
import logging
from typing import Any

class PreparedStatementExecutor:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.slow_query_threshold_ms = 500
    
    async def execute(
        self,
        plugin: str,
        query: str,
        params: tuple[Any, ...],
        timeout_ms: int = 10000,
        max_rows: int = 10000,
        allow_write: bool = False
    ) -> dict[str, Any]:
        """Execute query with prepared statement."""
        
        # Get database connection
        conn = await self.db_manager.get_connection(plugin)
        
        # Start timing
        start_time = time.time()
        
        try:
            # Execute with timeout
            timeout_sec = timeout_ms / 1000.0
            async with asyncio.timeout(timeout_sec):
                # Execute prepared statement (SAFE - no injection)
                cursor = await conn.execute(query, params)
                
                # Determine statement type
                stmt_type = query.strip().upper().split()[0]
                
                if stmt_type == "SELECT" or stmt_type == "WITH":
                    # Fetch results with row limit
                    rows = []
                    count = 0
                    truncated = False
                    
                    async for row in cursor:
                        if count >= max_rows:
                            truncated = True
                            self.logger.warning(
                                f"Query returned more than {max_rows} rows (truncated)",
                                extra={
                                    "plugin": plugin,
                                    "query_hash": hash(query),
                                    "max_rows": max_rows
                                }
                            )
                            break
                        
                        # Convert Row to dict
                        row_dict = dict(row)
                        rows.append(row_dict)
                        count += 1
                    
                    row_count = count
                    result_data = rows
                
                else:  # INSERT, UPDATE, DELETE
                    # Check write permission
                    if not allow_write:
                        raise PermissionDeniedError(
                            f"{stmt_type} operations require allow_write=True"
                        )
                    
                    # Commit write operation
                    await conn.commit()
                    
                    # Get affected rows
                    row_count = cursor.rowcount
                    result_data = []
                    truncated = False
        
        except asyncio.TimeoutError:
            # Query exceeded timeout
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(
                f"Query timeout after {timeout_ms}ms",
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "timeout_ms": timeout_ms,
                    "execution_time_ms": execution_time
                }
            )
            raise TimeoutError(
                f"Query execution exceeded timeout of {timeout_ms}ms"
            )
        
        except Exception as e:
            # Database error
            self.logger.error(
                f"Query execution error: {e}",
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            raise ExecutionError(f"Database error: {e}") from e
        
        finally:
            await cursor.close()
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Log slow queries
        if execution_time_ms > self.slow_query_threshold_ms:
            self.logger.warning(
                f"Slow query detected ({execution_time_ms:.2f}ms)",
                extra={
                    "plugin": plugin,
                    "query_hash": hash(query),
                    "execution_time_ms": execution_time_ms,
                    "threshold_ms": self.slow_query_threshold_ms,
                    "row_count": row_count
                }
            )
        
        # Build result
        return {
            "rows": result_data,
            "row_count": row_count,
            "execution_time_ms": round(execution_time_ms, 2),
            "truncated": truncated
        }
```

**Key Features**:
- Uses `asyncio.timeout` for timeout enforcement
- Iterates cursor with `async for` to handle large result sets
- Converts Row objects to dicts for JSON serialization
- Commits write operations automatically
- Logs slow queries for monitoring
- Handles truncation gracefully

#### 3.2.3 ResultFormatter

**Purpose**: Format execution results into standardized JSON-serializable format

**Class Definition**:
```python
class ResultFormatter:
    """Format SQL execution results."""
    
    def format_success(
        self,
        rows: list[dict[str, Any]],
        row_count: int,
        execution_time_ms: float,
        truncated: bool = False
    ) -> dict[str, Any]:
        """
        Format successful query result.
        
        Args:
            rows: List of row dicts
            row_count: Number of rows
            execution_time_ms: Execution duration
            truncated: Whether results were truncated
        
        Returns:
            Formatted result dict
        """
    
    def format_error(
        self,
        error: Exception,
        query: str,
        params: list[Any],
        plugin: str
    ) -> dict[str, Any]:
        """
        Format query execution error.
        
        Args:
            error: Exception that occurred
            query: SQL query that failed
            params: Query parameters
            plugin: Plugin name
        
        Returns:
            Formatted error dict
        """
```

**Implementation**:
```python
import json
import base64
from typing import Any

class ResultFormatter:
    """Format query results for NATS response."""
    
    def format_success(
        self,
        rows: list[dict[str, Any]],
        row_count: int,
        execution_time_ms: float,
        truncated: bool = False
    ) -> dict[str, Any]:
        """Format successful execution result."""
        
        # Ensure all values are JSON-serializable
        serializable_rows = []
        for row in rows:
            serializable_row = {}
            for key, value in row.items():
                serializable_row[key] = self._make_serializable(value)
            serializable_rows.append(serializable_row)
        
        return {
            "rows": serializable_rows,
            "row_count": row_count,
            "execution_time_ms": execution_time_ms,
            "truncated": truncated
        }
    
    def format_error(
        self,
        error: Exception,
        query: str,
        params: list[Any],
        plugin: str
    ) -> dict[str, Any]:
        """Format execution error."""
        
        # Determine error code
        error_code = self._get_error_code(error)
        
        # Build error response
        error_dict = {
            "error": error_code,
            "message": str(error),
            "details": {
                "plugin": plugin,
                "query_preview": query[:200] + "..." if len(query) > 200 else query,
                "param_count": len(params),
                "error_type": type(error).__name__
            }
        }
        
        # Add specific details based on error type
        if isinstance(error, TimeoutError):
            error_dict["details"]["timeout_ms"] = getattr(error, "timeout_ms", None)
        elif isinstance(error, ValidationError):
            error_dict["details"]["validation_issue"] = getattr(error, "issue", None)
        elif isinstance(error, PermissionDeniedError):
            error_dict["details"]["permission"] = getattr(error, "required_permission", "allow_write")
        
        return error_dict
    
    def _make_serializable(self, value: Any) -> Any:
        """Convert value to JSON-serializable type."""
        
        # Handle None
        if value is None:
            return None
        
        # Handle bytes (BLOB)
        if isinstance(value, bytes):
            return base64.b64encode(value).decode('utf-8')
        
        # Handle boolean (SQLite stores as 0/1)
        if isinstance(value, bool):
            return value
        
        # Handle numeric types
        if isinstance(value, (int, float)):
            return value
        
        # Handle strings
        if isinstance(value, str):
            return value
        
        # Fallback: convert to string
        return str(value)
    
    def _get_error_code(self, error: Exception) -> str:
        """Map exception to error code."""
        
        error_map = {
            ValidationError: "VALIDATION_ERROR",
            PermissionDeniedError: "PERMISSION_DENIED",
            TimeoutError: "TIMEOUT",
            ExecutionError: "EXECUTION_ERROR",
        }
        
        # Check if error class matches
        for error_class, code in error_map.items():
            if isinstance(error, error_class):
                return code
        
        # Default
        return "UNKNOWN_ERROR"
```

### 3.3 Data Structures

#### 3.3.1 ExecutionResult (Success)

```python
from typing import TypedDict

class ExecutionResult(TypedDict):
    """Result of successful query execution."""
    rows: list[dict[str, Any]]        # Query results (SELECT) or empty (INSERT/UPDATE/DELETE)
    row_count: int                     # Rows returned (SELECT) or affected (INSERT/UPDATE/DELETE)
    execution_time_ms: float          # Query duration in milliseconds
    truncated: bool                    # Whether results were truncated at max_rows
```

**Example**:
```python
{
    "rows": [
        {"id": 1, "user_id": "alice", "event_type": "login"},
        {"id": 2, "user_id": "bob", "event_type": "command"}
    ],
    "row_count": 2,
    "execution_time_ms": 15.3,
    "truncated": false
}
```

#### 3.3.2 ExecutionError

```python
class ExecutionError(TypedDict):
    """Result of failed query execution."""
    error: str                         # Error code (VALIDATION_ERROR, TIMEOUT, etc.)
    message: str                       # Human-readable error message
    details: dict[str, Any]           # Additional context (plugin, query, params)
```

**Example**:
```python
{
    "error": "TIMEOUT",
    "message": "Query execution exceeded timeout of 10000ms",
    "details": {
        "plugin": "analytics-db",
        "query_preview": "SELECT * FROM analytics_db__events WHERE...",
        "param_count": 2,
        "error_type": "TimeoutError",
        "timeout_ms": 10000
    }
}
```

### 3.4 Error Handling

#### 3.4.1 Exception Hierarchy

```python
class SQLExecutionError(Exception):
    """Base exception for SQL execution errors."""
    pass

class ValidationError(SQLExecutionError):
    """Query validation failed."""
    pass

class PermissionDeniedError(SQLExecutionError):
    """Insufficient permissions for operation."""
    pass

class TimeoutError(SQLExecutionError):
    """Query execution timeout."""
    def __init__(self, message: str, timeout_ms: int):
        super().__init__(message)
        self.timeout_ms = timeout_ms

class ExecutionError(SQLExecutionError):
    """Database execution error."""
    pass

class TruncationError(SQLExecutionError):
    """Result set truncated (warning, not fatal)."""
    pass
```

#### 3.4.2 SQLite Error Translation

Map SQLite errors to meaningful error codes:

```python
def translate_sqlite_error(error: Exception) -> SQLExecutionError:
    """Translate SQLite exception to custom exception."""
    
    error_msg = str(error).lower()
    
    # Constraint violations
    if "unique constraint" in error_msg:
        return ExecutionError("Unique constraint violation")
    if "foreign key constraint" in error_msg:
        return ExecutionError("Foreign key constraint violation")
    if "not null constraint" in error_msg:
        return ExecutionError("NOT NULL constraint violation")
    
    # Database locked (transient)
    if "database is locked" in error_msg:
        return ExecutionError("Database is locked (retry later)")
    
    # Syntax errors (should not happen after validation)
    if "syntax error" in error_msg:
        return ValidationError(f"SQL syntax error: {error}")
    
    # No such table (should not happen after validation)
    if "no such table" in error_msg:
        return ValidationError(f"Table not found: {error}")
    
    # Generic execution error
    return ExecutionError(f"Database error: {error}")
```

### 3.5 Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Detailed Execution Flow                     │
└─────────────────────────────────────────────────────────────┘

Input: (plugin, validated_query, params, timeout_ms, max_rows, allow_write)

1. ParameterBinder.bind(query, params)
   - Find $1, $2, $3 placeholders
   - Replace with ? in order
   - Build parameter tuple
   → (sqlite_query, param_tuple)

2. PreparedStatementExecutor.execute()
   a. Get database connection (from db_manager)
   b. Start timer
   c. Execute with timeout:
      - async with asyncio.timeout(timeout_sec):
      - cursor = await conn.execute(sqlite_query, param_tuple)
   d. Check statement type:
      - SELECT/WITH: Fetch rows with limit
      - INSERT/UPDATE/DELETE: Check allow_write, commit
   e. Handle results:
      - Convert Row → dict
      - Count rows
      - Check truncation
   f. Calculate execution time
   g. Log if slow query
   → (rows, row_count, execution_time_ms, truncated)

3. ResultFormatter.format_success()
   - Ensure JSON-serializable values
   - Add metadata
   → ExecutionResult

Error Handling:
- TimeoutError → format_error(TimeoutError)
- PermissionDeniedError → format_error(PermissionDeniedError)
- SQLite error → translate → format_error(ExecutionError)
- Any exception → format_error(ExecutionError)
```

---

## 4. Implementation Steps

### 4.1 Phase 1: Parameter Binding (Day 1, Morning)

**Step 1.1**: Create `lib/db/sql_parameter.py`
- Implement `ParameterBinder` class
- Implement `bind()` method with $N → ? conversion
- Handle edge cases (empty params, parameter reuse, out-of-order)

**Step 1.2**: Write unit tests for ParameterBinder
- `test_bind_simple`: Single parameter
- `test_bind_multiple`: Multiple parameters
- `test_bind_reuse`: Parameter reuse (WHERE x = $1 OR y = $1)
- `test_bind_out_of_order`: $2 before $1
- `test_bind_empty`: No parameters
- `test_bind_mismatch`: Parameter count mismatch

**Step 1.3**: Validate tests pass
```bash
pytest tests/lib/db/test_sql_parameter.py -v
```

### 4.2 Phase 2: Executor Core (Day 1, Afternoon)

**Step 2.1**: Create `lib/db/sql_executor.py`
- Implement `PreparedStatementExecutor` class
- Implement `__init__` with db_manager
- Implement basic `execute()` method (SELECT only)

**Step 2.2**: Write unit tests for basic execution
- `test_execute_select_simple`: Basic SELECT query
- `test_execute_select_params`: SELECT with WHERE parameters
- `test_execute_select_empty`: Query returning no rows

**Step 2.3**: Add timeout enforcement
- Implement `asyncio.timeout` wrapper
- Add timeout test cases

**Step 2.4**: Write timeout tests
- `test_execute_timeout`: Query exceeds timeout
- `test_execute_within_timeout`: Query completes before timeout

### 4.3 Phase 3: Row Limit & Truncation (Day 2, Morning)

**Step 3.1**: Implement row limit enforcement
- Add `async for row in cursor` loop
- Implement row counter and truncation logic
- Set `truncated` flag when limit exceeded

**Step 3.2**: Write row limit tests
- `test_execute_row_limit`: Results truncated at max_rows
- `test_execute_under_limit`: Results not truncated
- `test_execute_exact_limit`: Results exactly at limit

**Step 3.3**: Add truncation logging
- Log warning when truncation occurs
- Include query hash and plugin in log

### 4.4 Phase 4: Write Operations (Day 2, Afternoon)

**Step 4.1**: Implement write operation handling
- Detect INSERT/UPDATE/DELETE statements
- Check `allow_write` flag
- Commit transactions
- Return affected row count

**Step 4.2**: Write write operation tests
- `test_execute_insert`: INSERT with allow_write=True
- `test_execute_insert_denied`: INSERT without allow_write (error)
- `test_execute_update`: UPDATE with allow_write=True
- `test_execute_delete`: DELETE with allow_write=True

### 4.5 Phase 5: Result Formatting (Day 3, Morning)

**Step 5.1**: Create `lib/db/sql_formatter.py`
- Implement `ResultFormatter` class
- Implement `format_success()` method
- Implement `format_error()` method

**Step 5.2**: Write formatter tests
- `test_format_success_simple`: Format SELECT results
- `test_format_success_empty`: Format empty result set
- `test_format_success_truncated`: Format truncated results
- `test_format_error_timeout`: Format timeout error
- `test_format_error_permission`: Format permission denied error
- `test_format_error_execution`: Format execution error

**Step 5.3**: Implement JSON serialization
- Handle NULL values (None)
- Handle BLOB values (base64 encode)
- Handle boolean values (0/1 → true/false)
- Test with various data types

### 4.6 Phase 6: Integration & Error Handling (Day 3, Afternoon)

**Step 6.1**: Implement error translation
- Create `translate_sqlite_error()` function
- Map common SQLite errors to custom exceptions

**Step 6.2**: Add comprehensive error handling to executor
- Try/except around execution
- Translate SQLite errors
- Format errors with ResultFormatter

**Step 6.3**: Write integration tests
- `test_integration_select_success`: Full SELECT flow
- `test_integration_insert_success`: Full INSERT flow
- `test_integration_validation_error`: Invalid query rejected
- `test_integration_timeout`: Timeout handled correctly
- `test_integration_permission_denied`: Write without flag rejected

**Step 6.4**: Add observability
- Log slow queries (> 500ms)
- Log errors with context
- Include query hash for correlation

---

## 5. Testing Strategy

### 5.1 Unit Tests (30+ tests)

#### ParameterBinder Tests (8 tests)
```python
# tests/lib/db/test_sql_parameter.py

async def test_bind_simple():
    """Test single parameter binding."""
    binder = ParameterBinder()
    query = "SELECT * FROM users WHERE id = $1"
    params = ["alice"]
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert sqlite_query == "SELECT * FROM users WHERE id = ?"
    assert param_tuple == ("alice",)

async def test_bind_multiple():
    """Test multiple parameter binding."""
    binder = ParameterBinder()
    query = "SELECT * FROM users WHERE id = $1 AND status = $2"
    params = ["alice", "active"]
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert sqlite_query == "SELECT * FROM users WHERE id = ? AND status = ?"
    assert param_tuple == ("alice", "active")

async def test_bind_reuse():
    """Test parameter reuse."""
    binder = ParameterBinder()
    query = "SELECT * FROM users WHERE name = $1 OR email = $1"
    params = ["alice"]
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert sqlite_query == "SELECT * FROM users WHERE name = ? OR email = ?"
    assert param_tuple == ("alice", "alice")  # Duplicated

async def test_bind_out_of_order():
    """Test out-of-order placeholders."""
    binder = ParameterBinder()
    query = "SELECT * FROM users WHERE status = $2 AND id = $1"
    params = ["alice", "active"]
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert sqlite_query == "SELECT * FROM users WHERE status = ? AND id = ?"
    assert param_tuple == ("active", "alice")  # Order by appearance in query

async def test_bind_empty():
    """Test query with no parameters."""
    binder = ParameterBinder()
    query = "SELECT * FROM users LIMIT 10"
    params = []
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert sqlite_query == "SELECT * FROM users LIMIT 10"
    assert param_tuple == ()

async def test_bind_mismatch():
    """Test parameter count mismatch."""
    binder = ParameterBinder()
    query = "SELECT * FROM users WHERE id = $1 AND status = $2"
    params = ["alice"]  # Missing $2
    
    with pytest.raises(ValidationError, match="only 1 params provided"):
        binder.bind(query, params)

async def test_bind_types():
    """Test various parameter types."""
    binder = ParameterBinder()
    query = "INSERT INTO events (user, score, active, data) VALUES ($1, $2, $3, $4)"
    params = ["alice", 42, True, None]
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert param_tuple == ("alice", 42, True, None)

async def test_bind_large_number():
    """Test placeholder with large number."""
    binder = ParameterBinder()
    query = "SELECT $1, $2, $3, $10"
    params = list(range(1, 11))  # 10 params
    
    sqlite_query, param_tuple = binder.bind(query, params)
    
    assert param_tuple == (1, 2, 3, 10)
```

#### PreparedStatementExecutor Tests (15 tests)
```python
# tests/lib/db/test_sql_executor.py

@pytest.fixture
async def executor(db_manager):
    """Create executor fixture."""
    return PreparedStatementExecutor(db_manager)

@pytest.fixture
async def test_db(db_manager):
    """Create test database with sample data."""
    conn = await db_manager.get_connection("test-plugin")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS test_plugin__users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            active BOOLEAN DEFAULT 1
        )
    """)
    await conn.execute("""
        INSERT INTO test_plugin__users (username, score, active)
        VALUES ('alice', 100, 1), ('bob', 75, 1), ('charlie', 50, 0)
    """)
    await conn.commit()
    return conn

async def test_execute_select_simple(executor, test_db):
    """Test basic SELECT query."""
    result = await executor.execute(
        plugin="test-plugin",
        query="SELECT * FROM test_plugin__users WHERE username = ?",
        params=("alice",),
        timeout_ms=1000,
        max_rows=100
    )
    
    assert result["row_count"] == 1
    assert result["rows"][0]["username"] == "alice"
    assert result["rows"][0]["score"] == 100
    assert result["truncated"] is False
    assert result["execution_time_ms"] > 0

async def test_execute_select_multiple(executor, test_db):
    """Test SELECT returning multiple rows."""
    result = await executor.execute(
        plugin="test-plugin",
        query="SELECT * FROM test_plugin__users WHERE active = ?",
        params=(1,),
        timeout_ms=1000,
        max_rows=100
    )
    
    assert result["row_count"] == 2
    assert len(result["rows"]) == 2
    assert result["truncated"] is False

async def test_execute_select_empty(executor, test_db):
    """Test SELECT returning no rows."""
    result = await executor.execute(
        plugin="test-plugin",
        query="SELECT * FROM test_plugin__users WHERE username = ?",
        params=("nonexistent",),
        timeout_ms=1000,
        max_rows=100
    )
    
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["truncated"] is False

async def test_execute_timeout(executor, test_db):
    """Test query timeout."""
    # Insert large dataset
    conn = await executor.db_manager.get_connection("test-plugin")
    for i in range(10000):
        await conn.execute(
            "INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
            (f"user{i}", i)
        )
    await conn.commit()
    
    # Query with very short timeout
    with pytest.raises(TimeoutError, match="exceeded timeout"):
        await executor.execute(
            plugin="test-plugin",
            query="SELECT * FROM test_plugin__users",
            params=(),
            timeout_ms=1,  # 1ms timeout (too short)
            max_rows=100000
        )

async def test_execute_row_limit(executor, test_db):
    """Test row limit enforcement."""
    # Insert many rows
    conn = await executor.db_manager.get_connection("test-plugin")
    for i in range(100):
        await conn.execute(
            "INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
            (f"user{i}", i)
        )
    await conn.commit()
    
    # Query with row limit
    result = await executor.execute(
        plugin="test-plugin",
        query="SELECT * FROM test_plugin__users",
        params=(),
        timeout_ms=5000,
        max_rows=50  # Limit to 50 rows
    )
    
    assert result["row_count"] == 50
    assert len(result["rows"]) == 50
    assert result["truncated"] is True  # More rows available

async def test_execute_insert(executor, test_db):
    """Test INSERT operation."""
    result = await executor.execute(
        plugin="test-plugin",
        query="INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
        params=("dave", 90),
        timeout_ms=1000,
        max_rows=100,
        allow_write=True
    )
    
    assert result["row_count"] == 1  # One row inserted
    assert result["rows"] == []  # No rows returned for INSERT
    assert result["truncated"] is False

async def test_execute_insert_denied(executor, test_db):
    """Test INSERT without write permission."""
    with pytest.raises(PermissionDeniedError, match="require allow_write"):
        await executor.execute(
            plugin="test-plugin",
            query="INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
            params=("dave", 90),
            timeout_ms=1000,
            max_rows=100,
            allow_write=False  # Write not allowed
        )

async def test_execute_update(executor, test_db):
    """Test UPDATE operation."""
    result = await executor.execute(
        plugin="test-plugin",
        query="UPDATE test_plugin__users SET score = ? WHERE username = ?",
        params=(150, "alice"),
        timeout_ms=1000,
        max_rows=100,
        allow_write=True
    )
    
    assert result["row_count"] == 1  # One row updated
    assert result["rows"] == []

async def test_execute_delete(executor, test_db):
    """Test DELETE operation."""
    result = await executor.execute(
        plugin="test-plugin",
        query="DELETE FROM test_plugin__users WHERE username = ?",
        params=("charlie",),
        timeout_ms=1000,
        max_rows=100,
        allow_write=True
    )
    
    assert result["row_count"] == 1  # One row deleted
    assert result["rows"] == []
```

#### ResultFormatter Tests (7 tests)
```python
# tests/lib/db/test_sql_formatter.py

def test_format_success_simple():
    """Test formatting successful SELECT results."""
    formatter = ResultFormatter()
    
    rows = [
        {"id": 1, "username": "alice", "score": 100},
        {"id": 2, "username": "bob", "score": 75}
    ]
    
    result = formatter.format_success(
        rows=rows,
        row_count=2,
        execution_time_ms=15.3,
        truncated=False
    )
    
    assert result["rows"] == rows
    assert result["row_count"] == 2
    assert result["execution_time_ms"] == 15.3
    assert result["truncated"] is False

def test_format_success_empty():
    """Test formatting empty result set."""
    formatter = ResultFormatter()
    
    result = formatter.format_success(
        rows=[],
        row_count=0,
        execution_time_ms=5.1,
        truncated=False
    )
    
    assert result["rows"] == []
    assert result["row_count"] == 0

def test_format_success_truncated():
    """Test formatting truncated results."""
    formatter = ResultFormatter()
    
    result = formatter.format_success(
        rows=[{"id": i} for i in range(100)],
        row_count=100,
        execution_time_ms=250.5,
        truncated=True
    )
    
    assert result["truncated"] is True
    assert result["row_count"] == 100

def test_format_success_serialization():
    """Test JSON serialization of various types."""
    formatter = ResultFormatter()
    
    rows = [
        {
            "string": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "blob": b"binary data"
        }
    ]
    
    result = formatter.format_success(
        rows=rows,
        row_count=1,
        execution_time_ms=10.0,
        truncated=False
    )
    
    # Check BLOB converted to base64
    assert isinstance(result["rows"][0]["blob"], str)
    assert result["rows"][0]["string"] == "hello"
    assert result["rows"][0]["null"] is None

def test_format_error_timeout():
    """Test formatting timeout error."""
    formatter = ResultFormatter()
    
    error = TimeoutError("Query exceeded timeout", 10000)
    
    result = formatter.format_error(
        error=error,
        query="SELECT * FROM large_table",
        params=["param1"],
        plugin="test-plugin"
    )
    
    assert result["error"] == "TIMEOUT"
    assert "timeout" in result["message"].lower()
    assert result["details"]["plugin"] == "test-plugin"
    assert result["details"]["param_count"] == 1

def test_format_error_permission():
    """Test formatting permission denied error."""
    formatter = ResultFormatter()
    
    error = PermissionDeniedError("INSERT requires allow_write=True")
    
    result = formatter.format_error(
        error=error,
        query="INSERT INTO users VALUES (?, ?)",
        params=["alice", 100],
        plugin="test-plugin"
    )
    
    assert result["error"] == "PERMISSION_DENIED"
    assert "allow_write" in result["message"].lower()

def test_format_error_execution():
    """Test formatting execution error."""
    formatter = ResultFormatter()
    
    error = ExecutionError("Unique constraint violation")
    
    result = formatter.format_error(
        error=error,
        query="INSERT INTO users (id, username) VALUES (?, ?)",
        params=[1, "alice"],
        plugin="test-plugin"
    )
    
    assert result["error"] == "EXECUTION_ERROR"
    assert "constraint" in result["message"].lower()
```

### 5.2 Integration Tests (5+ tests)

```python
# tests/lib/db/test_sql_integration.py

@pytest.fixture
async def full_stack(db_manager):
    """Create full SQL execution stack."""
    binder = ParameterBinder()
    executor = PreparedStatementExecutor(db_manager)
    formatter = ResultFormatter()
    
    return {
        "binder": binder,
        "executor": executor,
        "formatter": formatter
    }

async def test_integration_select_success(full_stack, test_db):
    """Test complete SELECT flow."""
    # Input: PostgreSQL-style query
    query_pg = "SELECT * FROM test_plugin__users WHERE username = $1"
    params = ["alice"]
    
    # Step 1: Bind parameters
    query_sqlite, param_tuple = full_stack["binder"].bind(query_pg, params)
    
    # Step 2: Execute
    exec_result = await full_stack["executor"].execute(
        plugin="test-plugin",
        query=query_sqlite,
        params=param_tuple,
        timeout_ms=1000,
        max_rows=100
    )
    
    # Step 3: Format
    formatted = full_stack["formatter"].format_success(**exec_result)
    
    # Verify
    assert formatted["row_count"] == 1
    assert formatted["rows"][0]["username"] == "alice"
    assert "execution_time_ms" in formatted

async def test_integration_insert_success(full_stack, test_db):
    """Test complete INSERT flow."""
    query_pg = "INSERT INTO test_plugin__users (username, score) VALUES ($1, $2)"
    params = ["dave", 90]
    
    query_sqlite, param_tuple = full_stack["binder"].bind(query_pg, params)
    
    exec_result = await full_stack["executor"].execute(
        plugin="test-plugin",
        query=query_sqlite,
        params=param_tuple,
        timeout_ms=1000,
        max_rows=100,
        allow_write=True
    )
    
    formatted = full_stack["formatter"].format_success(**exec_result)
    
    assert formatted["row_count"] == 1
    assert formatted["rows"] == []

async def test_integration_error_handling(full_stack, test_db):
    """Test error handling through full stack."""
    query_pg = "INSERT INTO test_plugin__users (username, score) VALUES ($1, $2)"
    params = ["eve", 80]
    
    query_sqlite, param_tuple = full_stack["binder"].bind(query_pg, params)
    
    # Execute without write permission (should error)
    try:
        await full_stack["executor"].execute(
            plugin="test-plugin",
            query=query_sqlite,
            params=param_tuple,
            timeout_ms=1000,
            max_rows=100,
            allow_write=False  # Error: write not allowed
        )
        assert False, "Should have raised PermissionDeniedError"
    except PermissionDeniedError as e:
        # Format error
        formatted = full_stack["formatter"].format_error(
            error=e,
            query=query_pg,
            params=params,
            plugin="test-plugin"
        )
        
        assert formatted["error"] == "PERMISSION_DENIED"
        assert "allow_write" in formatted["message"].lower()
```

### 5.3 Test Coverage Goals

**Minimum Coverage**: 90% line coverage, 85% branch coverage

**Critical Paths** (100% coverage required):
- Parameter binding ($N → ?)
- Prepared statement execution
- Timeout enforcement
- Row limit enforcement
- Error handling and translation
- Result formatting

**Test Execution**:
```bash
# Run all tests
pytest tests/lib/db/ -v --cov=lib/db --cov-report=html

# Run specific test module
pytest tests/lib/db/test_sql_executor.py -v

# Run with coverage report
pytest tests/lib/db/ --cov=lib/db --cov-report=term-missing
```

---

## 6. Acceptance Criteria

### 6.1 Functional Acceptance

- [ ] **AC-1**: ParameterBinder converts $1, $2, $3 to ? correctly
- [ ] **AC-2**: PreparedStatementExecutor executes SELECT queries
- [ ] **AC-3**: PreparedStatementExecutor executes INSERT/UPDATE/DELETE with allow_write
- [ ] **AC-4**: Timeout enforcement aborts queries exceeding limit
- [ ] **AC-5**: Row limit enforcement truncates results at max_rows
- [ ] **AC-6**: Results are JSON-serializable (all tests pass)
- [ ] **AC-7**: Execution metadata accurate (row_count, execution_time_ms, truncated)
- [ ] **AC-8**: Write operations require allow_write=True
- [ ] **AC-9**: Write operations commit transactions
- [ ] **AC-10**: Errors translated to meaningful error codes

### 6.2 Technical Acceptance

- [ ] **AC-11**: 30+ unit tests pass
- [ ] **AC-12**: 5+ integration tests pass
- [ ] **AC-13**: Test coverage ≥ 90% line, ≥ 85% branch
- [ ] **AC-14**: Type hints complete (no mypy errors)
- [ ] **AC-15**: Docstrings follow Google style
- [ ] **AC-16**: No SQL injection possible (prepared statements only)
- [ ] **AC-17**: Performance acceptable (< 10ms overhead for simple queries)

### 6.3 Quality Acceptance

- [ ] **AC-18**: Code review approved
- [ ] **AC-19**: No linting errors (ruff check)
- [ ] **AC-20**: No security vulnerabilities
- [ ] **AC-21**: Logging implemented (slow queries, errors)
- [ ] **AC-22**: Error messages clear and actionable

---

## 7. Verification & Testing

### 7.1 Manual Testing Checklist

**Test 1: Basic SELECT**
```python
# Execute simple SELECT query
binder = ParameterBinder()
executor = PreparedStatementExecutor(db_manager)

query = "SELECT * FROM test_plugin__users WHERE username = $1"
params = ["alice"]

sqlite_query, param_tuple = binder.bind(query, params)
result = await executor.execute(
    plugin="test-plugin",
    query=sqlite_query,
    params=param_tuple,
    timeout_ms=1000,
    max_rows=100
)

# Verify result structure
assert "rows" in result
assert "row_count" in result
assert "execution_time_ms" in result
assert "truncated" in result
```

**Test 2: Timeout Enforcement**
```python
# Execute query with very short timeout
try:
    result = await executor.execute(
        plugin="test-plugin",
        query="SELECT * FROM large_table",
        params=(),
        timeout_ms=1,  # 1ms - too short
        max_rows=10000
    )
    assert False, "Should have timed out"
except TimeoutError as e:
    print(f"✓ Timeout enforced: {e}")
```

**Test 3: Row Limit Enforcement**
```python
# Execute query returning many rows
result = await executor.execute(
    plugin="test-plugin",
    query="SELECT * FROM test_plugin__users",
    params=(),
    timeout_ms=5000,
    max_rows=50
)

assert result["row_count"] == 50
assert result["truncated"] is True
print("✓ Row limit enforced")
```

**Test 4: Write Permission Check**
```python
# Attempt INSERT without permission
try:
    result = await executor.execute(
        plugin="test-plugin",
        query="INSERT INTO test_plugin__users (username) VALUES (?)",
        params=("frank",),
        timeout_ms=1000,
        max_rows=100,
        allow_write=False
    )
    assert False, "Should have been denied"
except PermissionDeniedError as e:
    print(f"✓ Write permission enforced: {e}")
```

### 7.2 Performance Testing

**Benchmark 1: Parameter Binding**
```python
import time

# Measure parameter binding performance
binder = ParameterBinder()
query = "SELECT * FROM users WHERE id = $1 AND status = $2 AND score > $3"
params = ["alice", "active", 50]

start = time.time()
for _ in range(1000):
    binder.bind(query, params)
elapsed = (time.time() - start) * 1000

print(f"Parameter binding: {elapsed/1000:.3f}ms per call")
assert elapsed / 1000 < 1.0, "Binding should be < 1ms per call"
```

**Benchmark 2: Query Execution**
```python
# Measure simple SELECT performance
executor = PreparedStatementExecutor(db_manager)
query = "SELECT * FROM test_plugin__users WHERE id = ?"
params = (1,)

times = []
for _ in range(100):
    start = time.time()
    result = await executor.execute(
        plugin="test-plugin",
        query=query,
        params=params,
        timeout_ms=1000,
        max_rows=100
    )
    elapsed = (time.time() - start) * 1000
    times.append(elapsed)

avg_time = sum(times) / len(times)
p95_time = sorted(times)[95]

print(f"Average execution time: {avg_time:.2f}ms")
print(f"P95 execution time: {p95_time:.2f}ms")

assert avg_time < 10.0, "Simple query should be < 10ms"
assert p95_time < 20.0, "P95 should be < 20ms"
```

### 7.3 Edge Case Testing

**Edge Case 1: Empty Result Set**
```python
result = await executor.execute(
    plugin="test-plugin",
    query="SELECT * FROM test_plugin__users WHERE username = ?",
    params=("nonexistent",),
    timeout_ms=1000,
    max_rows=100
)

assert result["row_count"] == 0
assert result["rows"] == []
assert result["truncated"] is False
```

**Edge Case 2: NULL Values**
```python
# Insert row with NULL
await executor.execute(
    plugin="test-plugin",
    query="INSERT INTO test_plugin__users (username, score) VALUES (?, ?)",
    params=("george", None),
    timeout_ms=1000,
    max_rows=100,
    allow_write=True
)

# Query NULL value
result = await executor.execute(
    plugin="test-plugin",
    query="SELECT * FROM test_plugin__users WHERE username = ?",
    params=("george",),
    timeout_ms=1000,
    max_rows=100
)

assert result["rows"][0]["score"] is None
```

**Edge Case 3: BLOB Data**
```python
# Insert BLOB
blob_data = b"\x00\x01\x02\x03\xFF"
await executor.execute(
    plugin="test-plugin",
    query="INSERT INTO test_plugin__data (name, content) VALUES (?, ?)",
    params=("file1", blob_data),
    timeout_ms=1000,
    max_rows=100,
    allow_write=True
)

# Query BLOB
result = await executor.execute(
    plugin="test-plugin",
    query="SELECT * FROM test_plugin__data WHERE name = ?",
    params=("file1",),
    timeout_ms=1000,
    max_rows=100
)

# Verify BLOB encoded as base64
import base64
assert isinstance(result["rows"][0]["content"], str)
decoded = base64.b64decode(result["rows"][0]["content"])
assert decoded == blob_data
```

---

## 8. Dependencies & Integration

### 8.1 External Dependencies

**Python Packages** (add to `requirements.txt`):
```
aiosqlite>=0.19.0  # Async SQLite operations
```

**Internal Dependencies**:
- `lib/db/database.py`: DatabaseManager (from Sprint 12-14)
- `lib/db/sql_validator.py`: QueryValidator (from Sortie 1)
- `common/exceptions.py`: Base exception classes

### 8.2 Integration Points

**From Sortie 1**:
- `QueryValidator.validate()` returns `ValidatedQuery`
- Executor receives pre-validated queries

**To Sortie 3**:
- `PreparedStatementExecutor` used by NATS handler
- `ResultFormatter` formats NATS responses

**Database Manager**:
```python
# lib/db/database.py (existing)
class DatabaseManager:
    async def get_connection(self, plugin: str) -> aiosqlite.Connection:
        """Get database connection for plugin."""
        # Returns aiosqlite connection
```

### 8.3 Configuration

**Default Configuration** (`config.json`):
```json
{
    "sql": {
        "default_timeout_ms": 10000,
        "default_max_rows": 10000,
        "slow_query_threshold_ms": 500,
        "max_timeout_ms": 30000,
        "max_max_rows": 100000
    }
}
```

**Configuration Validation**:
- `timeout_ms`: 100 ≤ value ≤ 30000
- `max_rows`: 1 ≤ value ≤ 100000
- `slow_query_threshold_ms`: > 0

---

## 9. Documentation

### 9.1 Code Documentation

**Docstring Example** (Google Style):
```python
async def execute(
    self,
    plugin: str,
    query: str,
    params: tuple[Any, ...],
    timeout_ms: int = 10000,
    max_rows: int = 10000,
    allow_write: bool = False
) -> dict[str, Any]:
    """
    Execute SQL query using prepared statement.
    
    This method executes a validated SQL query using SQLite prepared statements,
    ensuring no SQL injection is possible. Queries are executed with timeout
    and row limit enforcement.
    
    Args:
        plugin: Plugin name (determines database connection)
        query: SQL query with ? placeholders (SQLite format)
        params: Parameter tuple matching placeholders
        timeout_ms: Query timeout in milliseconds (100-30000)
        max_rows: Maximum rows to return (1-100000)
        allow_write: Whether write operations (INSERT/UPDATE/DELETE) are allowed
    
    Returns:
        Execution result dict containing:
            - rows: List of result rows (dicts)
            - row_count: Number of rows returned or affected
            - execution_time_ms: Query duration in milliseconds
            - truncated: Boolean indicating if results were truncated
    
    Raises:
        TimeoutError: Query exceeded timeout limit
        PermissionDeniedError: Write operation without allow_write=True
        ExecutionError: Database error during execution
    
    Example:
        >>> executor = PreparedStatementExecutor(db_manager)
        >>> result = await executor.execute(
        ...     plugin="analytics-db",
        ...     query="SELECT * FROM analytics_db__events WHERE user_id = ?",
        ...     params=("alice",),
        ...     timeout_ms=5000,
        ...     max_rows=1000
        ... )
        >>> print(result["row_count"])
        42
    
    Security:
        - Always uses prepared statements (no string interpolation)
        - Parameters bound securely by SQLite
        - Timeout prevents DoS attacks
        - Row limit prevents memory exhaustion
    
    Performance:
        - Simple queries: < 10ms overhead
        - Complex queries: < 20ms overhead
        - Slow query logging at 500ms threshold
    """
```

### 9.2 Usage Examples

**Example 1: Simple SELECT**
```python
from lib.db.sql_parameter import ParameterBinder
from lib.db.sql_executor import PreparedStatementExecutor
from lib.db.sql_formatter import ResultFormatter

# Initialize components
binder = ParameterBinder()
executor = PreparedStatementExecutor(db_manager)
formatter = ResultFormatter()

# Execute query
query_pg = "SELECT * FROM analytics_db__events WHERE user_id = $1"
params = ["alice"]

query_sqlite, param_tuple = binder.bind(query_pg, params)
result = await executor.execute(
    plugin="analytics-db",
    query=query_sqlite,
    params=param_tuple
)

formatted = formatter.format_success(**result)
print(f"Found {formatted['row_count']} events")
```

**Example 2: INSERT with Write Permission**
```python
# Insert new event
query_pg = "INSERT INTO analytics_db__events (user_id, event_type, timestamp) VALUES ($1, $2, $3)"
params = ["alice", "login", "2025-01-15T10:30:00Z"]

query_sqlite, param_tuple = binder.bind(query_pg, params)
result = await executor.execute(
    plugin="analytics-db",
    query=query_sqlite,
    params=param_tuple,
    allow_write=True  # Required for INSERT
)

print(f"Inserted {result['row_count']} row(s)")
```

**Example 3: Error Handling**
```python
try:
    query_sqlite, param_tuple = binder.bind(query_pg, params)
    result = await executor.execute(
        plugin="analytics-db",
        query=query_sqlite,
        params=param_tuple,
        timeout_ms=5000,
        max_rows=1000
    )
    formatted = formatter.format_success(**result)
except TimeoutError as e:
    formatted = formatter.format_error(e, query_pg, params, "analytics-db")
    print(f"Query timeout: {formatted['message']}")
except PermissionDeniedError as e:
    formatted = formatter.format_error(e, query_pg, params, "analytics-db")
    print(f"Permission denied: {formatted['message']}")
except ExecutionError as e:
    formatted = formatter.format_error(e, query_pg, params, "analytics-db")
    print(f"Execution error: {formatted['message']}")
```

---

## 10. Risks & Mitigations

### 10.1 Technical Risks

**Risk 1: Performance Degradation**
- **Description**: Executor overhead impacts query performance
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**: 
  - Benchmark all code paths
  - Optimize hot paths (parameter binding, result formatting)
  - Cache compiled queries where possible
  - Profile with real workloads

**Risk 2: Memory Exhaustion**
- **Description**: Large result sets consume excessive memory
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Enforce row limits (default 10K)
  - Stream results with `async for`
  - Monitor memory usage in tests
  - Document memory implications

**Risk 3: Timeout Implementation**
- **Description**: `asyncio.timeout` may not work correctly with aiosqlite
- **Likelihood**: Low
- **Impact**: High
- **Mitigation**:
  - Test timeout extensively
  - Verify aiosqlite compatibility
  - Consider alternative timeout mechanisms
  - Add timeout integration tests

### 10.2 Security Risks

**Risk 4: SQL Injection**
- **Description**: Improper parameter binding allows injection
- **Likelihood**: Low (with prepared statements)
- **Impact**: Critical
- **Mitigation**:
  - ALWAYS use prepared statements
  - NEVER use string interpolation
  - Comprehensive injection testing (Sortie 5)
  - Code review focus on security

**Risk 5: Resource Exhaustion**
- **Description**: Malicious queries exhaust system resources
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Enforce timeout limits
  - Enforce row limits
  - Rate limiting (Sortie 4)
  - Monitor query patterns

### 10.3 Operational Risks

**Risk 6: Database Connection Leaks**
- **Description**: Connections not properly closed
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**:
  - Use context managers
  - Explicit cursor.close()
  - Connection pool monitoring
  - Integration tests verify cleanup

---

## 11. Success Metrics

### 11.1 Development Metrics

- **Test Coverage**: ≥ 90% line coverage, ≥ 85% branch coverage
- **Unit Tests**: 30+ tests, all passing
- **Integration Tests**: 5+ tests, all passing
- **Code Review**: Approved with no major issues
- **Documentation**: Complete docstrings, usage examples

### 11.2 Performance Metrics

- **Execution Overhead**: < 10ms for simple queries
- **Parameter Binding**: < 1ms per call
- **Result Formatting**: < 5ms for 1000 rows
- **P95 Latency**: < 50ms for typical queries
- **Throughput**: > 100 queries/second

### 11.3 Quality Metrics

- **Linting**: Zero ruff errors
- **Type Checking**: Zero mypy errors
- **Security**: Zero SQL injection vulnerabilities
- **Reliability**: Zero connection leaks in tests

---

## 12. Completion Checklist

### 12.1 Implementation Checklist

- [ ] `lib/db/sql_parameter.py` created with ParameterBinder
- [ ] `lib/db/sql_executor.py` created with PreparedStatementExecutor
- [ ] `lib/db/sql_formatter.py` created with ResultFormatter
- [ ] Parameter binding implemented and tested
- [ ] Query execution implemented (SELECT)
- [ ] Query execution implemented (INSERT/UPDATE/DELETE)
- [ ] Timeout enforcement implemented
- [ ] Row limit enforcement implemented
- [ ] Result formatting implemented
- [ ] Error handling and translation implemented
- [ ] Logging implemented (slow queries, errors)

### 12.2 Testing Checklist

- [ ] 8+ ParameterBinder unit tests pass
- [ ] 15+ PreparedStatementExecutor unit tests pass
- [ ] 7+ ResultFormatter unit tests pass
- [ ] 5+ integration tests pass
- [ ] Edge case tests pass (NULL, BLOB, empty results)
- [ ] Performance benchmarks meet targets
- [ ] Manual testing checklist complete

### 12.3 Quality Checklist

- [ ] Code review completed and approved
- [ ] Type hints complete (no mypy errors)
- [ ] Docstrings complete (Google style)
- [ ] Linting passes (ruff check)
- [ ] Test coverage ≥ 90%
- [ ] Security review completed
- [ ] Performance benchmarks documented

### 12.4 Documentation Checklist

- [ ] Code documentation complete
- [ ] Usage examples written
- [ ] README updated (if needed)
- [ ] Architecture docs updated (if needed)

---

## 13. Next Steps

After completing Sortie 2:

1. **Sortie 3**: NATS Handler & API Integration
   - Wire executor to NATS messaging
   - Implement request/response schema
   - Add integration tests with NATS

2. **Sortie 4**: Client Wrapper & Audit Logging
   - Create SQLClient convenience wrapper
   - Implement audit logging (100% coverage)
   - Add rate limiting

3. **Sortie 5**: Testing & Documentation
   - SQL injection test suite
   - Performance benchmarks
   - User documentation

---

**Document Version**: 1.0  
**Status**: Ready for Implementation  
**Estimated Duration**: 3 days  
**Dependencies**: Sortie 1 (Query Validator) complete

