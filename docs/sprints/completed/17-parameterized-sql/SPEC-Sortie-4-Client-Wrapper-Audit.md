# SPEC: Sortie 4 - Client Wrapper & Audit Logging

**Sprint**: 17-parameterized-sql  
**Sortie**: 4 of 5  
**Status**: ✅ Complete  
**Author**: Platform Team  
**Created**: November 24, 2025  
**Last Updated**: November 24, 2025

---

## 1. Overview

### 1.1 Purpose

Provide developer-friendly client wrapper and comprehensive audit logging for parameterized SQL:

- **SQLClient**: High-level Python class simplifying NATS SQL interactions
- **Audit Logging**: 100% query logging for security compliance and debugging
- **Rate Limiting**: Per-plugin query quotas to prevent abuse
- **Convenience Methods**: `select()`, `insert()`, `update()`, `delete()` helpers

This sortie improves developer experience and ensures operational visibility.

### 1.2 Scope

**In Scope**:
- SQLClient class with convenience methods
- Automatic retry for transient errors
- Comprehensive audit logging (all queries)
- Rate limiting (configurable per-plugin quotas)
- Slow query logging (threshold-based)
- Query metrics collection

**Out of Scope**:
- SQL injection testing (Sortie 5)
- Performance benchmarking (Sortie 5)
- User documentation/guides (Sortie 5)
- Security audit (Sortie 5)

### 1.3 Dependencies

**Prerequisites**:
- Sortie 1 (Query Validator & Parameter Binder) complete ✅
- Sortie 2 (Executor & Result Formatter) complete ✅
- Sortie 3 (NATS Handler & API) complete ✅

**Dependent Sorties**:
- Sortie 5 uses SQLClient for integration testing

### 1.4 Success Criteria

- [ ] SQLClient class with select/insert/update/delete methods
- [ ] Automatic error handling and retry logic
- [ ] 100% audit logging for all SQL queries
- [ ] Rate limiting with configurable quotas
- [ ] Slow query logging (> 500ms threshold)
- [ ] 30+ unit tests pass
- [ ] Integration tests with SQLExecutionHandler

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-1: SQLClient Class**
- Provide high-level Python interface for SQL execution
- Constructor takes NATS client and plugin name
- Handle JSON serialization/deserialization internally
- Automatic timeout handling

**FR-2: Convenience Methods**
- `select(query, params)` → List of row dicts
- `select_one(query, params)` → Single row dict or None
- `insert(query, params)` → Row count
- `update(query, params)` → Affected row count
- `delete(query, params)` → Deleted row count
- `execute(query, params, allow_write)` → Full result dict

**FR-3: Error Handling**
- Convert NATS errors to typed Python exceptions
- Automatic retry for transient errors (connection issues)
- Clear exception messages with query context
- SQLExecutionError, SQLValidationError, SQLTimeoutError hierarchy

**FR-4: Audit Logging**
- Log every query: timestamp, plugin, query hash, param count
- Log execution time and row count
- Log errors with full context
- Structured JSON format for SIEM integration

**FR-5: Rate Limiting**
- Configurable queries per minute per plugin
- Default: 100 queries/minute
- Reject excess queries with RateLimitError
- Expose rate limit status via metrics

**FR-6: Slow Query Logging**
- Configurable threshold (default: 500ms)
- Log slow queries to separate logger
- Include query, params, execution time
- Aggregate slow query statistics

### 2.2 Non-Functional Requirements

**NFR-1: Usability**
- Client API mirrors SQLAlchemy patterns where appropriate
- Comprehensive docstrings with examples
- Type hints for IDE autocomplete
- Single import for common use cases

**NFR-2: Performance**
- Client overhead < 5ms per query
- Connection reuse (no reconnect per query)
- Async-native implementation

**NFR-3: Observability**
- Prometheus-compatible metrics
- Structured logging (JSON)
- Correlation IDs for request tracing

---

## 3. Design

### 3.1 SQLClient Class

```python
class SQLClient:
    """
    High-level client for parameterized SQL execution.
    
    Provides a convenient wrapper around the NATS SQL API with
    automatic error handling, retry logic, and audit logging.
    
    Example:
        >>> client = SQLClient(nats_connection, "analytics-db")
        >>> rows = await client.select(
        ...     "SELECT * FROM analytics_db__events WHERE user_id = $1",
        ...     ["alice"]
        ... )
        >>> print(f"Found {len(rows)} events")
    
    Thread Safety:
        Client is async-safe and can be used concurrently.
    """
    
    def __init__(
        self,
        nats_client: Any,
        plugin: str,
        config: Optional[dict] = None
    ) -> None:
        """
        Initialize SQL client.
        
        Args:
            nats_client: NATS client instance
            plugin: Plugin name (determines table namespace)
            config: Optional configuration:
                - default_timeout_ms: Query timeout (default: 10000)
                - max_retries: Retry count for transient errors (default: 3)
                - rate_limit_per_min: Queries per minute (default: 100)
                - slow_query_threshold_ms: Slow query logging (default: 500)
        """
    
    async def execute(
        self,
        query: str,
        params: Optional[list] = None,
        allow_write: bool = False,
        timeout_ms: Optional[int] = None,
        max_rows: Optional[int] = None
    ) -> SQLResult:
        """
        Execute SQL query and return full result.
        
        Args:
            query: SQL query with $1, $2, $3 placeholders
            params: Parameter values (default: [])
            allow_write: Enable INSERT/UPDATE/DELETE (default: False)
            timeout_ms: Query timeout override
            max_rows: Row limit override
        
        Returns:
            SQLResult with rows, row_count, execution_time_ms, truncated
        
        Raises:
            SQLValidationError: Query failed validation
            SQLExecutionError: Database error
            SQLTimeoutError: Query exceeded timeout
            RateLimitError: Rate limit exceeded
        """
    
    async def select(
        self,
        query: str,
        params: Optional[list] = None,
        timeout_ms: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Execute SELECT and return rows.
        
        Args:
            query: SELECT query with $1, $2, $3 placeholders
            params: Parameter values
            timeout_ms: Query timeout override
        
        Returns:
            List of row dicts
        
        Example:
            >>> rows = await client.select(
            ...     "SELECT * FROM analytics_db__events WHERE timestamp > $1",
            ...     ["2025-01-01"]
            ... )
        """
    
    async def select_one(
        self,
        query: str,
        params: Optional[list] = None
    ) -> Optional[dict[str, Any]]:
        """
        Execute SELECT and return single row or None.
        
        Args:
            query: SELECT query (should return 0 or 1 row)
            params: Parameter values
        
        Returns:
            Row dict or None if no results
        
        Example:
            >>> user = await client.select_one(
            ...     "SELECT * FROM analytics_db__users WHERE id = $1",
            ...     [123]
            ... )
        """
    
    async def insert(
        self,
        query: str,
        params: list
    ) -> int:
        """
        Execute INSERT and return row count.
        
        Args:
            query: INSERT query with $1, $2, $3 placeholders
            params: Values to insert
        
        Returns:
            Number of rows inserted
        
        Example:
            >>> count = await client.insert(
            ...     "INSERT INTO analytics_db__events (user_id, event) VALUES ($1, $2)",
            ...     ["alice", "login"]
            ... )
        """
    
    async def insert_many(
        self,
        query: str,
        params_list: list[list]
    ) -> int:
        """
        Execute INSERT for multiple rows.
        
        Args:
            query: INSERT query with placeholders
            params_list: List of parameter lists
        
        Returns:
            Total rows inserted
        
        Example:
            >>> count = await client.insert_many(
            ...     "INSERT INTO analytics_db__events (user_id, event) VALUES ($1, $2)",
            ...     [["alice", "login"], ["bob", "logout"]]
            ... )
        """
    
    async def update(
        self,
        query: str,
        params: list
    ) -> int:
        """
        Execute UPDATE and return affected row count.
        
        Args:
            query: UPDATE query with $1, $2, $3 placeholders
            params: Parameter values
        
        Returns:
            Number of rows updated
        
        Example:
            >>> count = await client.update(
            ...     "UPDATE analytics_db__users SET score = score + $1 WHERE id = $2",
            ...     [10, 123]
            ... )
        """
    
    async def delete(
        self,
        query: str,
        params: list
    ) -> int:
        """
        Execute DELETE and return deleted row count.
        
        Args:
            query: DELETE query with $1, $2, $3 placeholders
            params: Parameter values
        
        Returns:
            Number of rows deleted
        
        Example:
            >>> count = await client.delete(
            ...     "DELETE FROM analytics_db__events WHERE timestamp < $1",
            ...     ["2024-01-01"]
            ... )
        """
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get client metrics.
        
        Returns:
            Dict with query_count, error_count, avg_latency_ms, etc.
        """
```

### 3.2 Result Types

```python
@dataclass
class SQLResult:
    """Result of SQL query execution."""
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
    
    def first(self) -> Optional[dict[str, Any]]:
        """Return first row or None."""
        return self.rows[0] if self.rows else None
```

### 3.3 Exception Hierarchy

```python
class SQLError(Exception):
    """Base class for SQL errors."""
    def __init__(self, message: str, code: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class SQLValidationError(SQLError):
    """Query failed validation (syntax, forbidden statement, etc.)."""
    pass


class SQLExecutionError(SQLError):
    """Database execution error (constraint violation, etc.)."""
    pass


class SQLTimeoutError(SQLError):
    """Query exceeded timeout."""
    def __init__(self, message: str, timeout_ms: int, **kwargs):
        super().__init__(message, "TIMEOUT", **kwargs)
        self.timeout_ms = timeout_ms


class SQLPermissionError(SQLError):
    """Permission denied (write without flag, cross-plugin access)."""
    pass


class RateLimitError(SQLError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after_ms: int, **kwargs):
        super().__init__(message, "RATE_LIMIT", **kwargs)
        self.retry_after_ms = retry_after_ms
```

### 3.4 Audit Logger

```python
class SQLAuditLogger:
    """
    Audit logger for SQL queries.
    
    Logs all queries in structured JSON format for:
    - Security auditing
    - Debugging
    - Performance analysis
    - SIEM integration
    """
    
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        slow_query_threshold_ms: float = 500.0
    ):
        self.logger = logger or logging.getLogger("sql.audit")
        self.slow_logger = logging.getLogger("sql.slow")
        self.slow_threshold_ms = slow_query_threshold_ms
    
    def log_query(
        self,
        plugin: str,
        query: str,
        params: list,
        result: SQLResult,
        start_time: float
    ) -> None:
        """Log successful query execution."""
        execution_time_ms = (time.time() - start_time) * 1000
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "plugin": plugin,
            "query_hash": self._hash_query(query),
            "query_preview": query[:100] + "..." if len(query) > 100 else query,
            "param_count": len(params),
            "row_count": result.row_count,
            "execution_time_ms": round(execution_time_ms, 2),
            "truncated": result.truncated,
            "status": "success"
        }
        
        self.logger.info("SQL query executed", extra=log_entry)
        
        # Slow query logging
        if execution_time_ms > self.slow_threshold_ms:
            self._log_slow_query(log_entry, query, params)
    
    def log_error(
        self,
        plugin: str,
        query: str,
        params: list,
        error: Exception,
        start_time: float
    ) -> None:
        """Log failed query execution."""
        execution_time_ms = (time.time() - start_time) * 1000
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "plugin": plugin,
            "query_hash": self._hash_query(query),
            "query_preview": query[:100] + "..." if len(query) > 100 else query,
            "param_count": len(params),
            "execution_time_ms": round(execution_time_ms, 2),
            "status": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_code": getattr(error, "code", "UNKNOWN")
        }
        
        self.logger.error("SQL query failed", extra=log_entry)
    
    def _log_slow_query(
        self,
        log_entry: dict,
        query: str,
        params: list
    ) -> None:
        """Log slow query with full details."""
        slow_entry = {
            **log_entry,
            "full_query": query,
            "params": self._sanitize_params(params)
        }
        self.slow_logger.warning("Slow SQL query", extra=slow_entry)
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query (for grouping similar queries)."""
        import hashlib
        normalized = " ".join(query.split()).lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _sanitize_params(self, params: list) -> list:
        """Sanitize params for logging (truncate long strings)."""
        def sanitize(val):
            if isinstance(val, str) and len(val) > 100:
                return val[:100] + "..."
            return val
        return [sanitize(p) for p in params]
```

### 3.5 Rate Limiter

```python
class SQLRateLimiter:
    """
    Rate limiter for SQL queries.
    
    Uses sliding window algorithm to enforce per-plugin quotas.
    """
    
    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60
    ):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.plugin_limits: dict[str, int] = {}
        self.windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
    
    def set_limit(self, plugin: str, limit: int) -> None:
        """Set custom limit for plugin."""
        self.plugin_limits[plugin] = limit
    
    async def check(self, plugin: str) -> None:
        """
        Check if request is allowed.
        
        Raises:
            RateLimitError: If rate limit exceeded
        """
        async with self._lock:
            now = time.time()
            limit = self.plugin_limits.get(plugin, self.default_limit)
            
            # Get or create window
            if plugin not in self.windows:
                self.windows[plugin] = []
            
            window = self.windows[plugin]
            
            # Remove old entries
            cutoff = now - self.window_seconds
            window[:] = [t for t in window if t > cutoff]
            
            # Check limit
            if len(window) >= limit:
                oldest = min(window)
                retry_after_ms = int((oldest + self.window_seconds - now) * 1000)
                raise RateLimitError(
                    f"Rate limit exceeded for {plugin}: {limit} queries per {self.window_seconds}s",
                    retry_after_ms=retry_after_ms
                )
            
            # Record this request
            window.append(now)
    
    def get_status(self, plugin: str) -> dict[str, Any]:
        """Get rate limit status for plugin."""
        limit = self.plugin_limits.get(plugin, self.default_limit)
        window = self.windows.get(plugin, [])
        now = time.time()
        cutoff = now - self.window_seconds
        current = len([t for t in window if t > cutoff])
        
        return {
            "plugin": plugin,
            "limit": limit,
            "current": current,
            "remaining": max(0, limit - current),
            "window_seconds": self.window_seconds
        }
```

---

## 4. Implementation Steps

### 4.1 Phase 1: SQLClient Core (Day 1, Morning)

**Step 1.1**: Create `lib/storage/sql_client.py`
- Implement `SQLClient` class
- Implement `execute()` method with NATS call
- Add basic error handling

**Step 1.2**: Implement convenience methods
- `select()` - Execute SELECT, return rows
- `select_one()` - Return single row or None
- `insert()` - Execute INSERT with allow_write=True
- `update()` - Execute UPDATE with allow_write=True
- `delete()` - Execute DELETE with allow_write=True

**Step 1.3**: Add SQLResult dataclass
- Implement dataclass with helper methods
- Add `__iter__`, `__len__`, `first()`

### 4.2 Phase 2: Error Handling (Day 1, Afternoon)

**Step 2.1**: Create exception hierarchy
- `SQLError` base class
- `SQLValidationError`, `SQLExecutionError`, `SQLTimeoutError`
- `SQLPermissionError`, `RateLimitError`

**Step 2.2**: Implement error conversion
- Parse error responses from handler
- Map error codes to exception types
- Include query context in exceptions

**Step 2.3**: Add retry logic
- Retry on transient errors (NATS connection issues)
- Configurable retry count and backoff
- Don't retry on validation errors

### 4.3 Phase 3: Audit Logging (Day 2, Morning)

**Step 3.1**: Create `SQLAuditLogger` class
- Log all queries with structured format
- Include timing, row counts, status
- Hash queries for grouping

**Step 3.2**: Add slow query logging
- Separate logger for slow queries
- Configurable threshold
- Include full query and params

**Step 3.3**: Integrate with SQLClient
- Log before/after each query
- Log errors with context

### 4.4 Phase 4: Rate Limiting (Day 2, Afternoon)

**Step 4.1**: Create `SQLRateLimiter` class
- Sliding window algorithm
- Per-plugin quotas
- Thread-safe implementation

**Step 4.2**: Integrate with SQLClient
- Check rate limit before each query
- Return retry-after on limit exceeded
- Expose status via metrics

**Step 4.3**: Add configuration
- Default limits in config
- Per-plugin overrides
- Runtime limit adjustment

### 4.5 Phase 5: Testing (Day 3)

**Step 5.1**: Unit tests for SQLClient
- Test all convenience methods
- Test error handling
- Test retry logic

**Step 5.2**: Unit tests for audit logger
- Test query logging
- Test slow query detection
- Test error logging

**Step 5.3**: Unit tests for rate limiter
- Test limit enforcement
- Test sliding window
- Test per-plugin limits

**Step 5.4**: Integration tests
- Test with SQLExecutionHandler
- Test end-to-end query flow
- Test concurrent clients

---

## 5. Testing Strategy

### 5.1 Unit Tests (30+ tests)

```python
# tests/unit/test_sql_client.py

class TestSQLClient:
    """Unit tests for SQLClient."""
    
    @pytest.fixture
    def mock_nats(self):
        """Create mock NATS client."""
        nats = AsyncMock()
        nats.request = AsyncMock()
        return nats
    
    @pytest.fixture
    def client(self, mock_nats):
        """Create SQLClient with mock NATS."""
        return SQLClient(mock_nats, "test-plugin")
    
    # Initialization tests
    def test_init_default_config(self, mock_nats):
        """Test client initializes with defaults."""
    
    def test_init_custom_config(self, mock_nats):
        """Test client accepts custom config."""
    
    # Execute tests
    async def test_execute_select_success(self, client, mock_nats):
        """Test successful SELECT execution."""
    
    async def test_execute_handles_timeout(self, client, mock_nats):
        """Test timeout error handling."""
    
    async def test_execute_handles_validation_error(self, client, mock_nats):
        """Test validation error handling."""
    
    # Convenience method tests
    async def test_select_returns_rows(self, client, mock_nats):
        """Test select() returns row list."""
    
    async def test_select_one_returns_single(self, client, mock_nats):
        """Test select_one() returns single row."""
    
    async def test_select_one_returns_none(self, client, mock_nats):
        """Test select_one() returns None for no results."""
    
    async def test_insert_sets_allow_write(self, client, mock_nats):
        """Test insert() sets allow_write=True."""
    
    async def test_insert_returns_row_count(self, client, mock_nats):
        """Test insert() returns inserted count."""
    
    async def test_insert_many_multiple_rows(self, client, mock_nats):
        """Test insert_many() handles multiple rows."""
    
    async def test_update_returns_affected_count(self, client, mock_nats):
        """Test update() returns affected count."""
    
    async def test_delete_returns_deleted_count(self, client, mock_nats):
        """Test delete() returns deleted count."""
    
    # Retry tests
    async def test_retry_on_transient_error(self, client, mock_nats):
        """Test automatic retry on transient errors."""
    
    async def test_no_retry_on_validation_error(self, client, mock_nats):
        """Test no retry for validation errors."""
    
    async def test_max_retries_exceeded(self, client, mock_nats):
        """Test error raised after max retries."""


class TestSQLAuditLogger:
    """Unit tests for audit logging."""
    
    def test_log_query_success(self):
        """Test successful query logging."""
    
    def test_log_query_error(self):
        """Test error query logging."""
    
    def test_slow_query_detection(self):
        """Test slow query threshold."""
    
    def test_query_hash_consistency(self):
        """Test query hashing is consistent."""
    
    def test_param_sanitization(self):
        """Test long params are truncated."""


class TestSQLRateLimiter:
    """Unit tests for rate limiting."""
    
    async def test_allow_under_limit(self):
        """Test requests allowed under limit."""
    
    async def test_reject_over_limit(self):
        """Test requests rejected over limit."""
    
    async def test_window_expiry(self):
        """Test old requests expire from window."""
    
    async def test_custom_plugin_limit(self):
        """Test per-plugin limit override."""
    
    async def test_retry_after_calculation(self):
        """Test retry-after header calculation."""
```

### 5.2 Integration Tests (10+ tests)

```python
# tests/integration/test_sql_client_integration.py

class TestSQLClientIntegration:
    """Integration tests with real handler."""
    
    @pytest.fixture
    async def handler(self, nats_client, database):
        """Start SQL handler."""
        handler = SQLExecutionHandler(nats_client, database)
        await handler.start()
        yield handler
        await handler.stop()
    
    @pytest.fixture
    def client(self, nats_client):
        """Create client for test plugin."""
        return SQLClient(nats_client, "test-plugin")
    
    async def test_select_query_end_to_end(self, client, handler):
        """Test full SELECT flow."""
    
    async def test_insert_query_end_to_end(self, client, handler):
        """Test full INSERT flow."""
    
    async def test_concurrent_clients(self, nats_client, handler):
        """Test multiple clients simultaneously."""
    
    async def test_rate_limiting_integration(self, client, handler):
        """Test rate limiting with real queries."""
    
    async def test_audit_logging_integration(self, client, handler, caplog):
        """Test audit logs generated."""
```

---

## 6. Acceptance Criteria

### 6.1 Functional Acceptance

- [ ] **AC-1**: SQLClient.select() returns list of row dicts
- [ ] **AC-2**: SQLClient.select_one() returns single row or None
- [ ] **AC-3**: SQLClient.insert() sets allow_write=True automatically
- [ ] **AC-4**: SQLClient.update() returns affected row count
- [ ] **AC-5**: SQLClient.delete() returns deleted row count
- [ ] **AC-6**: Transient errors are retried automatically
- [ ] **AC-7**: Validation errors raise SQLValidationError
- [ ] **AC-8**: Timeout errors raise SQLTimeoutError
- [ ] **AC-9**: All queries logged to audit logger
- [ ] **AC-10**: Slow queries (>500ms) logged separately

### 6.2 Rate Limiting Acceptance

- [ ] **AC-11**: Rate limiter enforces per-plugin quotas
- [ ] **AC-12**: RateLimitError includes retry-after value
- [ ] **AC-13**: Custom limits can be set per plugin
- [ ] **AC-14**: Rate limit status exposed via metrics

### 6.3 Quality Acceptance

- [ ] **AC-15**: 30+ unit tests pass
- [ ] **AC-16**: 10+ integration tests pass
- [ ] **AC-17**: Type hints complete
- [ ] **AC-18**: Docstrings with examples on all public methods
- [ ] **AC-19**: All 1800+ existing tests still pass

---

## 7. Files to Create/Modify

### 7.1 New Files

| File | Purpose |
|------|---------|
| `lib/storage/sql_client.py` | SQLClient class and helpers |
| `lib/storage/sql_audit.py` | SQLAuditLogger class |
| `lib/storage/sql_rate_limit.py` | SQLRateLimiter class |
| `tests/unit/test_sql_client.py` | Unit tests |
| `tests/unit/test_sql_audit.py` | Audit logger tests |
| `tests/unit/test_sql_rate_limit.py` | Rate limiter tests |
| `tests/integration/test_sql_client_integration.py` | Integration tests |

### 7.2 Modified Files

| File | Changes |
|------|---------|
| `lib/storage/__init__.py` | Export SQLClient, SQLResult, exceptions |
| `lib/storage/sql_errors.py` | Add RateLimitError |

---

## 8. Completion Checklist

### 8.1 Implementation Checklist

- [ ] `lib/storage/sql_client.py` created with SQLClient
- [ ] All convenience methods implemented
- [ ] Error handling and retry logic implemented
- [ ] `lib/storage/sql_audit.py` created with SQLAuditLogger
- [ ] Slow query logging implemented
- [ ] `lib/storage/sql_rate_limit.py` created with SQLRateLimiter
- [ ] Rate limiting integrated with client

### 8.2 Testing Checklist

- [ ] 30+ unit tests pass
- [ ] 10+ integration tests pass
- [ ] All existing tests still pass

### 8.3 Documentation Checklist

- [ ] All public methods have docstrings
- [ ] Type hints complete
- [ ] SPEC file updated with completion status

---

## 9. Next Steps

After completing Sortie 4:

1. **Sortie 5**: Security Testing & Documentation
   - SQL injection test suite (100+ patterns)
   - Performance benchmarking
   - Security audit
   - User documentation and migration guide

---

**Document Version**: 1.0  
**Status**: Ready for Implementation  
**Estimated Duration**: 3 days  
**Dependencies**: Sorties 1-3 complete
