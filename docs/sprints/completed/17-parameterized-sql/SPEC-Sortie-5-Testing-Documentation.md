# SPEC: Sortie 5 - Security Testing & Documentation

**Sprint**: 17-parameterized-sql  
**Sortie**: 5 of 5  
**Status**: Draft  
**Author**: Platform Team  
**Created**: November 24, 2025  
**Last Updated**: November 24, 2025

---

## 1. Overview

### 1.1 Purpose

Validate security, measure performance, and provide comprehensive documentation:

- **SQL Injection Testing**: 100+ attack patterns verified blocked
- **Security Audit**: Complete review of all SQL execution paths
- **Performance Benchmarking**: Baseline metrics for latency and throughput
- **Developer Documentation**: 20+ examples, migration guide, best practices

This sortie ensures the parameterized SQL system is secure, performant, and well-documented for production use.

### 1.2 Scope

**In Scope**:
- SQL injection test suite (100+ patterns)
- Security audit of entire SQL pipeline
- Performance benchmarks (latency, throughput)
- Load testing under concurrent queries
- Developer documentation with examples
- Migration guide for existing plugins
- Best practices guide

**Out of Scope**:
- Performance optimization (out of scope for this sprint)
- Production deployment (separate sprint)
- Plugin migration implementation (plugins migrate themselves)

### 1.3 Dependencies

**Prerequisites**:
- Sortie 1 (Query Validator & Parameter Binder) complete ✅
- Sortie 2 (Executor & Result Formatter) complete ✅
- Sortie 3 (NATS Handler & API) complete ✅
- Sortie 4 (Client Wrapper & Audit) complete ✅ (expected)

**Dependent Sorties**: None (final sortie)

### 1.4 Success Criteria

- [ ] SQL injection test suite blocks 100% of attack patterns
- [ ] Security audit passes with no critical findings
- [ ] Performance benchmarks documented (baseline established)
- [ ] Load test demonstrates 1000+ queries/min capability
- [ ] Developer documentation complete with 20+ examples
- [ ] Migration guide published
- [ ] All tests pass (1900+ including new tests)

---

## 2. Requirements

### 2.1 Security Requirements

**SR-1: SQL Injection Prevention**
- Test 100+ SQL injection patterns
- All known attack vectors blocked
- Zero bypass vulnerabilities

**SR-2: Parameter Binding Security**
- All user input properly parameterized
- No string interpolation in queries
- Type coercion prevents type confusion attacks

**SR-3: Permission Enforcement**
- Namespace isolation enforced (plugins can't access other plugin data)
- Write operations require explicit flag
- Forbidden statements always blocked

**SR-4: Error Message Security**
- Error messages don't leak database schema
- Query text sanitized in error responses
- Detailed errors only in logs (not user-facing)

### 2.2 Performance Requirements

**PR-1: Latency Benchmarks**
- Simple SELECT: < 10ms median
- Complex SELECT with joins: < 50ms median
- INSERT/UPDATE: < 20ms median
- 99th percentile < 100ms

**PR-2: Throughput Benchmarks**
- Support 1000+ queries/minute sustained
- Graceful degradation under load
- No memory leaks under stress

**PR-3: Concurrent Load**
- 50+ concurrent clients
- No deadlocks or race conditions
- Fair scheduling across plugins

### 2.3 Documentation Requirements

**DR-1: Developer Guide**
- Quick start (5-minute guide)
- Complete API reference
- 20+ code examples
- Common patterns and recipes

**DR-2: Migration Guide**
- Step-by-step migration from raw SQL
- Before/after examples
- Testing strategy for migrations

**DR-3: Best Practices**
- Query optimization tips
- Error handling patterns
- Rate limiting guidance
- Audit log usage

---

## 3. Design

### 3.1 SQL Injection Test Suite

```python
# tests/security/test_sql_injection.py

"""
SQL Injection Security Test Suite

Tests 100+ attack patterns including:
- Classic SQL injection
- UNION-based injection
- Blind SQL injection
- Time-based injection
- Comment-based attacks
- Encoding bypasses
- Second-order injection
"""

SQL_INJECTION_PATTERNS = [
    # Classic injection
    ("' OR '1'='1", "Classic always-true"),
    ("'; DROP TABLE users; --", "Drop table attack"),
    ("' UNION SELECT * FROM users --", "Union select"),
    ("1; DELETE FROM events", "Statement termination"),
    
    # Comment-based
    ("admin'--", "Line comment bypass"),
    ("admin'/*", "Block comment bypass"),
    ("*/OR/**/1=1--", "Comment obfuscation"),
    
    # Encoding bypasses
    ("admin%27--", "URL encoded quote"),
    ("admin\\x27--", "Hex encoded quote"),
    ("CHAR(39)||'1'='1", "CHAR encoding"),
    
    # Boolean-based blind
    ("' AND 1=1 --", "Boolean true"),
    ("' AND 1=2 --", "Boolean false"),
    ("' AND SUBSTRING(username,1,1)='a", "Substring extraction"),
    
    # Time-based blind
    ("'; WAITFOR DELAY '0:0:5'--", "SQL Server delay"),
    ("'; SELECT pg_sleep(5);--", "PostgreSQL sleep"),
    ("'; SELECT SLEEP(5);--", "MySQL sleep"),
    
    # UNION attacks
    ("' UNION SELECT NULL--", "Union NULL probe"),
    ("' UNION SELECT 1,2,3--", "Union column count"),
    ("' UNION SELECT password FROM users--", "Union data extraction"),
    
    # Second-order
    ("O'Reilly", "Stored injection prep"),  # Valid but watch for second-order
    
    # Advanced
    ("admin' AND (SELECT COUNT(*) FROM users) > 0 --", "Subquery injection"),
    ("admin'||(SELECT password FROM users LIMIT 1)||'", "String concatenation"),
    ("1 AND EXISTS(SELECT * FROM users WHERE username='admin')", "EXISTS injection"),
    
    # ... 75+ more patterns
]


class TestSQLInjectionPrevention:
    """SQL injection attack prevention tests."""
    
    @pytest.fixture
    def client(self, nats_client):
        return SQLClient(nats_client, "security-test")
    
    @pytest.mark.parametrize("pattern,description", SQL_INJECTION_PATTERNS)
    async def test_injection_blocked_in_select(self, client, pattern, description):
        """Test injection pattern is blocked in SELECT WHERE clause."""
        query = f"SELECT * FROM security_test__users WHERE name = $1"
        
        # Should execute safely - pattern is treated as literal string
        result = await client.select(query, [pattern])
        
        # Pattern should be in parameter, not interpreted as SQL
        # No error means it was properly parameterized
        assert isinstance(result, list)
    
    @pytest.mark.parametrize("pattern,description", SQL_INJECTION_PATTERNS)
    async def test_injection_cannot_escape_parameter(self, client, pattern, description):
        """Test pattern cannot escape parameter boundary."""
        # Try to inject in various parameter positions
        queries = [
            ("SELECT * FROM security_test__events WHERE user_id = $1", [pattern]),
            ("SELECT * FROM security_test__events WHERE data LIKE $1", [pattern]),
            ("SELECT * FROM security_test__events WHERE timestamp > $1", [pattern]),
        ]
        
        for query, params in queries:
            # All should execute without SQL error (pattern treated as string)
            try:
                await client.select(query, params)
            except SQLExecutionError as e:
                # Acceptable: execution error due to type mismatch
                # NOT acceptable: SQL injection succeeded
                assert "syntax" not in str(e).lower()
                assert "injection" not in str(e).lower()
    
    async def test_query_validation_blocks_raw_injection(self, client):
        """Test validator rejects queries with injection in SQL itself."""
        dangerous_queries = [
            "SELECT * FROM users; DROP TABLE users",
            "SELECT * FROM users WHERE 1=1; --",
            "SELECT * FROM users UNION SELECT * FROM admins",
        ]
        
        for query in dangerous_queries:
            with pytest.raises((SQLValidationError, SQLPermissionError)):
                await client.select(query, [])
```

### 3.2 Security Audit Checklist

```python
# tests/security/test_security_audit.py

"""
Security Audit Test Suite

Validates security properties across the SQL pipeline.
"""

class TestSecurityAudit:
    """Comprehensive security audit tests."""
    
    # Namespace isolation
    async def test_cannot_access_other_plugin_tables(self, client):
        """Plugin cannot SELECT from other plugin's tables."""
        with pytest.raises(SQLPermissionError):
            await client.select(
                "SELECT * FROM other_plugin__secrets", []
            )
    
    async def test_cannot_join_across_plugins(self, client):
        """Plugin cannot JOIN to other plugin's tables."""
        with pytest.raises(SQLPermissionError):
            await client.select(
                "SELECT * FROM my_plugin__users u "
                "JOIN other_plugin__data d ON u.id = d.user_id", 
                []
            )
    
    # Write protection
    async def test_write_blocked_without_flag(self, client):
        """INSERT fails without allow_write flag."""
        with pytest.raises(SQLPermissionError):
            await client.execute(
                "INSERT INTO my_plugin__events (data) VALUES ($1)",
                ["test"],
                allow_write=False
            )
    
    async def test_drop_always_blocked(self, client):
        """DROP always blocked regardless of flags."""
        with pytest.raises(SQLValidationError):
            await client.execute(
                "DROP TABLE my_plugin__events",
                [],
                allow_write=True
            )
    
    # Error sanitization
    async def test_error_does_not_leak_schema(self, client):
        """Error messages don't reveal database structure."""
        try:
            await client.select("SELECT invalid_column FROM my_plugin__events", [])
        except SQLExecutionError as e:
            error_msg = str(e).lower()
            # Should not contain full table paths or column lists
            assert "information_schema" not in error_msg
            assert "pg_catalog" not in error_msg
    
    # Parameter safety
    async def test_null_byte_injection_blocked(self, client):
        """Null byte injection is handled safely."""
        result = await client.select(
            "SELECT * FROM my_plugin__events WHERE data = $1",
            ["test\x00injection"]
        )
        # Should not error or allow bypass
        assert isinstance(result, list)
    
    async def test_unicode_handling(self, client):
        """Unicode is handled correctly without bypass."""
        # Various Unicode that could bypass filters
        patterns = [
            "admin\u2019--",  # Right single quote
            "admin\uff07--",  # Fullwidth apostrophe
            "test\u0027--",   # Unicode quote
        ]
        for pattern in patterns:
            result = await client.select(
                "SELECT * FROM my_plugin__events WHERE user = $1",
                [pattern]
            )
            assert isinstance(result, list)
```

### 3.3 Performance Benchmark Framework

```python
# tests/performance/benchmark_sql.py

"""
Performance Benchmark Suite

Measures latency and throughput for parameterized SQL.
"""

import asyncio
import statistics
import time
from typing import NamedTuple


class BenchmarkResult(NamedTuple):
    """Benchmark result metrics."""
    name: str
    iterations: int
    total_time_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float


async def benchmark(
    name: str,
    func,
    iterations: int = 1000,
    warmup: int = 100
) -> BenchmarkResult:
    """
    Run benchmark and collect metrics.
    
    Args:
        name: Benchmark name
        func: Async function to benchmark
        iterations: Number of iterations
        warmup: Warmup iterations (not measured)
    
    Returns:
        BenchmarkResult with all metrics
    """
    # Warmup
    for _ in range(warmup):
        await func()
    
    # Benchmark
    times = []
    start_total = time.perf_counter()
    
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    
    total_time_ms = (time.perf_counter() - start_total) * 1000
    
    times.sort()
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_ms=total_time_ms,
        min_ms=times[0],
        max_ms=times[-1],
        mean_ms=statistics.mean(times),
        median_ms=statistics.median(times),
        p95_ms=times[int(iterations * 0.95)],
        p99_ms=times[int(iterations * 0.99)],
        throughput_per_sec=iterations / (total_time_ms / 1000)
    )


class TestSQLBenchmarks:
    """SQL performance benchmarks."""
    
    @pytest.fixture
    def client(self, nats_client):
        return SQLClient(nats_client, "benchmark")
    
    async def test_simple_select_latency(self, client, benchmark_output):
        """Benchmark simple SELECT query."""
        async def query():
            await client.select(
                "SELECT * FROM benchmark__events WHERE id = $1",
                [1]
            )
        
        result = await benchmark("simple_select", query)
        benchmark_output.record(result)
        
        assert result.median_ms < 10, "Median should be < 10ms"
        assert result.p99_ms < 100, "P99 should be < 100ms"
    
    async def test_complex_select_latency(self, client, benchmark_output):
        """Benchmark complex SELECT with JOIN."""
        async def query():
            await client.select(
                "SELECT e.*, u.name FROM benchmark__events e "
                "JOIN benchmark__users u ON e.user_id = u.id "
                "WHERE e.timestamp > $1 ORDER BY e.timestamp LIMIT 100",
                ["2025-01-01"]
            )
        
        result = await benchmark("complex_select", query)
        benchmark_output.record(result)
        
        assert result.median_ms < 50, "Median should be < 50ms"
    
    async def test_insert_latency(self, client, benchmark_output):
        """Benchmark INSERT query."""
        async def query():
            await client.insert(
                "INSERT INTO benchmark__events (user_id, data) VALUES ($1, $2)",
                [1, '{"event": "benchmark"}']
            )
        
        result = await benchmark("insert", query, iterations=500)
        benchmark_output.record(result)
        
        assert result.median_ms < 20, "Median should be < 20ms"
    
    async def test_concurrent_load(self, nats_client, benchmark_output):
        """Benchmark concurrent client load."""
        clients = [
            SQLClient(nats_client, f"load-test-{i}")
            for i in range(50)
        ]
        
        async def run_queries(client, count):
            times = []
            for _ in range(count):
                start = time.perf_counter()
                await client.select(
                    "SELECT * FROM load_test__events LIMIT 10", []
                )
                times.append((time.perf_counter() - start) * 1000)
            return times
        
        start = time.perf_counter()
        results = await asyncio.gather(*[
            run_queries(c, 20) for c in clients
        ])
        total_time_ms = (time.perf_counter() - start) * 1000
        
        all_times = [t for times in results for t in times]
        total_queries = len(all_times)
        throughput = total_queries / (total_time_ms / 1000)
        
        benchmark_output.record({
            "name": "concurrent_load",
            "clients": 50,
            "queries_per_client": 20,
            "total_queries": total_queries,
            "total_time_ms": total_time_ms,
            "throughput_per_sec": throughput,
            "mean_latency_ms": statistics.mean(all_times),
            "p99_latency_ms": sorted(all_times)[int(len(all_times) * 0.99)]
        })
        
        assert throughput > 1000, "Should handle > 1000 queries/min"
```

### 3.4 Documentation Structure

```
docs/
├── guides/
│   ├── PARAMETERIZED_SQL.md        # Main developer guide
│   ├── SQL_MIGRATION_GUIDE.md      # Migration from raw SQL
│   └── SQL_BEST_PRACTICES.md       # Best practices and tips
└── sprints/
    └── active/17-parameterized-sql/
        └── SECURITY_REPORT.md       # Security audit results
```

---

## 4. Implementation Steps

### 4.1 Phase 1: SQL Injection Test Suite (Day 1, Morning)

**Step 1.1**: Create injection pattern corpus
- Compile 100+ SQL injection patterns
- Categorize by attack type
- Document expected behavior

**Step 1.2**: Implement injection tests
- Parametric tests for all patterns
- Test in SELECT, INSERT, UPDATE contexts
- Verify proper parameterization

**Step 1.3**: Create bypass attempt tests
- Unicode encoding bypasses
- Null byte injection
- Comment-based bypasses

### 4.2 Phase 2: Security Audit (Day 1, Afternoon)

**Step 2.1**: Namespace isolation tests
- Cross-plugin access prevention
- JOIN restriction enforcement
- Subquery restriction enforcement

**Step 2.2**: Permission enforcement tests
- Write flag requirements
- Forbidden statement blocking
- DDL prevention

**Step 2.3**: Error sanitization tests
- Error message content verification
- No schema leakage
- No query leakage in user-facing errors

### 4.3 Phase 3: Performance Benchmarks (Day 2, Morning)

**Step 3.1**: Create benchmark framework
- Timing infrastructure
- Statistics collection
- Output formatting

**Step 3.2**: Implement latency benchmarks
- Simple SELECT benchmark
- Complex SELECT benchmark
- INSERT/UPDATE/DELETE benchmarks

**Step 3.3**: Implement throughput benchmarks
- Single client throughput
- Concurrent client throughput
- Stress testing

### 4.4 Phase 4: Load Testing (Day 2, Afternoon)

**Step 4.1**: Create load test scenarios
- Sustained load (1000 queries/min)
- Burst load (10x normal)
- Mixed read/write load

**Step 4.2**: Implement stability tests
- Memory usage over time
- Connection pool behavior
- Error rate under load

**Step 4.3**: Document baseline metrics
- Record all benchmark results
- Create comparison charts
- Establish performance baseline

### 4.5 Phase 5: Developer Documentation (Day 3)

**Step 5.1**: Create quick start guide
- 5-minute getting started
- First query example
- Basic error handling

**Step 5.2**: Create comprehensive API reference
- All methods documented
- All parameters explained
- All exceptions listed

**Step 5.3**: Create 20+ code examples
- Simple SELECT examples
- INSERT/UPDATE/DELETE examples
- Batch operations
- Error handling patterns
- Rate limit handling
- Audit log usage

**Step 5.4**: Create migration guide
- Step-by-step migration process
- Before/after code comparisons
- Testing migration strategy
- Common pitfalls

**Step 5.5**: Create best practices guide
- Query optimization
- Parameter usage
- Error handling
- Performance tips
- Security reminders

---

## 5. Testing Strategy

### 5.1 Security Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `tests/security/test_sql_injection.py` | 100+ | Injection pattern testing |
| `tests/security/test_security_audit.py` | 30+ | Security audit tests |

### 5.2 Performance Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `tests/performance/benchmark_sql.py` | 10+ | Latency benchmarks |
| `tests/performance/test_load.py` | 5+ | Load/stress tests |

### 5.3 Test Execution

```bash
# Run security tests
pytest tests/security/ -v --tb=short

# Run performance benchmarks (writes results to file)
pytest tests/performance/ -v --benchmark-output=benchmark_results.json

# Run all tests
pytest tests/ -v
```

---

## 6. Acceptance Criteria

### 6.1 Security Acceptance

- [ ] **AC-1**: 100+ SQL injection patterns blocked
- [ ] **AC-2**: No injection pattern bypasses found
- [ ] **AC-3**: Namespace isolation enforced (100% of test cases)
- [ ] **AC-4**: Permission enforcement verified
- [ ] **AC-5**: Error messages sanitized (no schema leakage)

### 6.2 Performance Acceptance

- [ ] **AC-6**: Simple SELECT median < 10ms
- [ ] **AC-7**: Complex SELECT median < 50ms
- [ ] **AC-8**: INSERT median < 20ms
- [ ] **AC-9**: P99 latency < 100ms for all operations
- [ ] **AC-10**: Throughput > 1000 queries/minute sustained
- [ ] **AC-11**: 50+ concurrent clients supported

### 6.3 Documentation Acceptance

- [ ] **AC-12**: Quick start guide complete
- [ ] **AC-13**: API reference complete
- [ ] **AC-14**: 20+ code examples provided
- [ ] **AC-15**: Migration guide complete
- [ ] **AC-16**: Best practices guide complete

### 6.4 Quality Acceptance

- [ ] **AC-17**: All security tests pass
- [ ] **AC-18**: All performance tests pass
- [ ] **AC-19**: All existing tests still pass
- [ ] **AC-20**: Security audit signed off

---

## 7. Files to Create/Modify

### 7.1 New Files

| File | Purpose |
|------|---------|
| `tests/security/test_sql_injection.py` | Injection test suite |
| `tests/security/test_security_audit.py` | Security audit tests |
| `tests/performance/benchmark_sql.py` | Performance benchmarks |
| `tests/performance/test_load.py` | Load testing |
| `tests/performance/conftest.py` | Benchmark fixtures |
| `docs/guides/PARAMETERIZED_SQL.md` | Developer guide |
| `docs/guides/SQL_MIGRATION_GUIDE.md` | Migration guide |
| `docs/guides/SQL_BEST_PRACTICES.md` | Best practices |

### 7.2 Modified Files

| File | Changes |
|------|---------|
| `README.md` | Add link to SQL documentation |
| `docs/ARCHITECTURE.md` | Update with SQL pipeline description |

---

## 8. Documentation Content Outline

### 8.1 PARAMETERIZED_SQL.md (Developer Guide)

```markdown
# Parameterized SQL Developer Guide

## Quick Start (5 minutes)
- Installation / setup
- First query example
- Basic error handling

## API Reference
### SQLClient
- Constructor and configuration
- execute() method
- select() / select_one()
- insert() / insert_many()
- update() / delete()
- get_metrics()

### SQLResult
- Properties and methods
- Iteration and access

### Exceptions
- Exception hierarchy
- Error codes
- Handling patterns

## Code Examples (20+)
1. Simple SELECT
2. SELECT with multiple parameters
3. SELECT with LIKE
4. SELECT with IN clause
5. SELECT with ORDER BY and LIMIT
6. select_one() usage
7. Simple INSERT
8. INSERT with RETURNING
9. Batch insert with insert_many()
10. Simple UPDATE
11. UPDATE with complex conditions
12. Simple DELETE
13. DELETE with joins
14. Transaction handling
15. Error handling - validation errors
16. Error handling - timeout
17. Error handling - rate limits
18. Retry logic customization
19. Audit log usage
20. Metrics collection
21. Connection configuration
22. Custom rate limits
```

### 8.2 SQL_MIGRATION_GUIDE.md

```markdown
# Migration Guide: Raw SQL to Parameterized SQL

## Overview
- Why migrate?
- What changes?
- Timeline recommendation

## Step-by-Step Migration

### Step 1: Inventory Existing Queries
- Finding raw SQL usage
- Categorizing queries

### Step 2: Rewrite Queries
- Before/after examples
- Placeholder syntax
- Common patterns

### Step 3: Update Client Code
- Replacing raw SQL calls
- Using SQLClient
- Error handling changes

### Step 4: Testing
- Unit test updates
- Integration testing
- Regression testing

### Step 5: Rollout
- Feature flags
- Gradual migration
- Rollback plan

## Common Pitfalls
- String interpolation habits
- Dynamic column names
- Query building patterns

## Before/After Examples (10+)
```

### 8.3 SQL_BEST_PRACTICES.md

```markdown
# Parameterized SQL Best Practices

## Query Design
- Keep queries simple
- Use appropriate indexes
- Avoid SELECT *
- Limit result sets

## Parameter Usage
- Always use placeholders
- Type-appropriate values
- NULL handling

## Error Handling
- Catch specific exceptions
- Log context
- User-friendly messages

## Performance
- Connection reuse
- Batch operations
- Query caching strategies

## Security
- Never interpolate strings
- Validate input before query
- Audit log review

## Operational
- Rate limit configuration
- Monitoring queries
- Slow query analysis
```

---

## 9. Completion Checklist

### 9.1 Security Testing Checklist

- [ ] 100+ injection patterns tested
- [ ] Namespace isolation verified
- [ ] Permission enforcement verified
- [ ] Error sanitization verified
- [ ] Security audit completed

### 9.2 Performance Testing Checklist

- [ ] Latency benchmarks run
- [ ] Throughput benchmarks run
- [ ] Load tests completed
- [ ] Baseline metrics documented

### 9.3 Documentation Checklist

- [ ] Developer guide written
- [ ] Migration guide written
- [ ] Best practices guide written
- [ ] 20+ examples created
- [ ] README updated

### 9.4 Final Verification

- [ ] All tests pass (1900+)
- [ ] Security audit signed off
- [ ] Documentation reviewed
- [ ] Sprint complete

---

## 10. Sprint Completion

After completing Sortie 5:

1. **Sprint Review**
   - Review all deliverables
   - Verify acceptance criteria
   - Document lessons learned

2. **Merge to Main**
   - Final PR review
   - Merge nano-sprint branch
   - Tag release (v0.X.0)

3. **Future Work**
   - Performance optimization sprint (if needed)
   - Production deployment sprint
   - Plugin migration support

---

**Document Version**: 1.0  
**Status**: Ready for Implementation  
**Estimated Duration**: 3 days  
**Dependencies**: Sorties 1-4 complete
