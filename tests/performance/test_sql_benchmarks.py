"""
Performance Benchmark Test Suite for Parameterized SQL.

This module provides performance benchmarks to validate that the
parameterized SQL system meets latency and throughput requirements.

Benchmarks include:
- Query validation throughput
- Parameter binding speed
- Full execution pipeline latency
- Concurrent request handling
- Memory efficiency under load
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import pytest

from lib.storage import (
    QueryValidator,
    ParameterBinder,
    PreparedStatementExecutor,
    ResultFormatter,
    SQLClient,
    SQLAuditLogger,
    SQLRateLimiter,
    StatementType,
)


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    ops_per_second: float
    min_time_ms: float
    max_time_ms: float


class TestValidatorPerformance:
    """Benchmark QueryValidator performance."""

    @pytest.fixture
    def validator(self):
        return QueryValidator()

    def benchmark(
        self, name: str, func: callable, iterations: int = 1000
    ) -> BenchmarkResult:
        """Run a benchmark and return results."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    def test_simple_select_validation(self, validator):
        """Benchmark simple SELECT query validation."""

        def run():
            validator.validate(
                "SELECT * FROM test_plugin__data WHERE id = $1",
                "test_plugin",
                params=[1],
            )

        result = self.benchmark("simple_select_validation", run, iterations=1000)

        # Performance assertion: should handle at least 500 ops/sec
        # (sqlparse parsing adds overhead)
        assert result.ops_per_second > 500, (
            f"Simple validation too slow: {result.ops_per_second:.0f} ops/sec"
        )
        # Average latency should be under 5ms
        assert result.avg_time_ms < 5.0, (
            f"Average validation latency too high: {result.avg_time_ms:.3f}ms"
        )

    def test_complex_join_validation(self, validator):
        """Benchmark complex JOIN query validation."""

        def run():
            validator.validate(
                """
                SELECT u.id, u.name, e.event_type, e.timestamp 
                FROM test_plugin__users u
                JOIN test_plugin__events e ON u.id = e.user_id
                WHERE u.active = $1 AND e.timestamp > $2
                ORDER BY e.timestamp DESC
                LIMIT $3
                """,
                "test_plugin",
                params=[True, "2024-01-01", 100],
            )

        result = self.benchmark("complex_join_validation", run, iterations=500)

        # Complex queries should complete (sqlparse is slower for complex queries)
        assert result.ops_per_second > 100, (
            f"Complex validation too slow: {result.ops_per_second:.0f} ops/sec"
        )

    def test_validation_with_many_params(self, validator):
        """Benchmark validation with many parameters."""
        placeholders = ", ".join([f"${i}" for i in range(1, 21)])
        query = f"INSERT INTO test_plugin__data (c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12, c13, c14, c15, c16, c17, c18, c19, c20) VALUES ({placeholders})"
        params = list(range(1, 21))

        def run():
            validator.validate(query, "test_plugin", params=params)

        result = self.benchmark("many_params_validation", run, iterations=500)

        # Many params adds overhead but should still be usable
        assert result.ops_per_second > 100, (
            f"Many-params validation too slow: {result.ops_per_second:.0f} ops/sec"
        )


class TestBinderPerformance:
    """Benchmark ParameterBinder performance."""

    @pytest.fixture
    def binder(self):
        return ParameterBinder()

    def benchmark(
        self, name: str, func: callable, iterations: int = 1000
    ) -> BenchmarkResult:
        """Run a benchmark and return results."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    def test_simple_binding(self, binder):
        """Benchmark simple parameter binding."""

        def run():
            binder.bind("SELECT * FROM test WHERE id = $1", [42])

        result = self.benchmark("simple_binding", run, iterations=5000)

        # Binding should be very fast
        assert result.ops_per_second > 10000, (
            f"Simple binding too slow: {result.ops_per_second:.0f} ops/sec"
        )

    def test_string_escaping(self, binder):
        """Benchmark binding with special characters."""
        payload = "O'Reilly's \"Book\" with \\ backslash"

        def run():
            binder.bind("SELECT * FROM test WHERE name = $1", [payload])

        result = self.benchmark("string_escaping", run, iterations=5000)

        assert result.ops_per_second > 5000, (
            f"String escaping too slow: {result.ops_per_second:.0f} ops/sec"
        )

    def test_large_param_binding(self, binder):
        """Benchmark binding with large string parameter."""
        large_string = "x" * 10000

        def run():
            binder.bind("SELECT * FROM test WHERE data = $1", [large_string])

        result = self.benchmark("large_param_binding", run, iterations=1000)

        assert result.ops_per_second > 1000, (
            f"Large param binding too slow: {result.ops_per_second:.0f} ops/sec"
        )


class TestRateLimiterPerformance:
    """Benchmark SQLRateLimiter performance."""

    @pytest.fixture
    def limiter(self):
        return SQLRateLimiter(default_limit=10000, window_seconds=1)

    def benchmark(
        self, name: str, func: callable, iterations: int = 1000
    ) -> BenchmarkResult:
        """Run a benchmark and return results."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    @pytest.mark.asyncio
    async def test_rate_check_throughput(self, limiter):
        """Benchmark rate limit checking."""

        async def run():
            await limiter.check("test_plugin")

        # Run benchmark
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            await run()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        avg = total / 1000
        ops_per_sec = 1000 / (total / 1000)

        # Rate checking should add minimal overhead
        assert ops_per_sec > 10000, f"Rate checking too slow: {ops_per_sec:.0f} ops/sec"
        # Should be sub-millisecond
        assert avg < 0.5, f"Rate check latency too high: {avg:.4f}ms"


class TestAuditLoggerPerformance:
    """Benchmark SQLAuditLogger performance."""

    @pytest.fixture
    def logger(self):
        return SQLAuditLogger()

    def benchmark(
        self, name: str, func: callable, iterations: int = 1000
    ) -> BenchmarkResult:
        """Run a benchmark and return results."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    def test_log_entry_creation(self, logger):
        """Benchmark audit log entry creation."""

        def run():
            logger.log_query(
                plugin="test",
                query="SELECT * FROM test__data WHERE id = $1",
                params=[1],
                row_count=10,
                execution_time_ms=0.5,
            )

        result = self.benchmark("log_entry", run, iterations=5000)

        # Logging should be reasonably fast
        assert result.ops_per_second > 5000, (
            f"Log entry creation too slow: {result.ops_per_second:.0f} ops/sec"
        )


class TestPipelinePerformance:
    """Benchmark full SQL execution pipeline."""

    @pytest.fixture
    def validator(self):
        return QueryValidator()

    @pytest.fixture
    def binder(self):
        return ParameterBinder()

    def benchmark(
        self, name: str, func: callable, iterations: int = 1000
    ) -> BenchmarkResult:
        """Run a benchmark and return results."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    def test_full_pipeline_no_execution(self, validator, binder):
        """Benchmark full validation + binding pipeline (no DB execution)."""
        query = "SELECT * FROM test_plugin__users WHERE id = $1 AND active = $2"
        params = [42, True]

        def run():
            # Validate
            result = validator.validate(query, "test_plugin", params=params)
            assert result.valid
            # Bind
            bound_query, bound_params = binder.bind(query, params)

        result = self.benchmark("full_pipeline", run, iterations=1000)

        # Full pipeline (minus DB) should be under 2ms average
        assert result.avg_time_ms < 2.0, (
            f"Full pipeline too slow: {result.avg_time_ms:.3f}ms"
        )
        # Should handle at least 500 ops/sec
        assert result.ops_per_second > 500, (
            f"Full pipeline throughput too low: {result.ops_per_second:.0f} ops/sec"
        )


class TestConcurrencyPerformance:
    """Test concurrent request handling performance."""

    @pytest.fixture
    def validator(self):
        return QueryValidator()

    @pytest.fixture
    def binder(self):
        return ParameterBinder()

    @pytest.mark.asyncio
    async def test_concurrent_validations(self, validator, binder):
        """Test concurrent validation requests."""

        async def validate_query(query_id: int):
            query = f"SELECT * FROM test_plugin__data WHERE id = $1"
            result = validator.validate(query, "test_plugin", params=[query_id])
            return result.valid

        # Run 100 concurrent validations
        start = time.perf_counter()
        tasks = [validate_query(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()

        # All should succeed
        assert all(results)

        # Should complete in reasonable time
        elapsed_ms = (end - start) * 1000
        assert elapsed_ms < 500, f"100 concurrent validations took {elapsed_ms:.0f}ms"

    @pytest.mark.asyncio
    async def test_mixed_query_types(self, validator, binder):
        """Test concurrent different query types."""
        queries = [
            ("SELECT * FROM test_plugin__users WHERE id = $1", [1]),
            ("INSERT INTO test_plugin__data (value) VALUES ($1)", ["test"]),
            ("UPDATE test_plugin__data SET value = $1 WHERE id = $2", ["new", 1]),
            ("DELETE FROM test_plugin__data WHERE id = $1", [1]),
        ]

        async def process_query(query: str, params: list):
            result = validator.validate(query, "test_plugin", params=params)
            if result.valid:
                bound_query, bound_params = binder.bind(query, params)
            return result.valid

        # Run mixed queries
        start = time.perf_counter()
        tasks = [
            process_query(q, p) for q, p in queries * 25  # 100 total
        ]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()

        assert all(results)
        elapsed_ms = (end - start) * 1000
        assert elapsed_ms < 500, f"Mixed queries took {elapsed_ms:.0f}ms"


class TestMemoryEfficiency:
    """Test memory efficiency under load."""

    def test_no_memory_leak_in_validator(self):
        """Verify validator doesn't leak memory."""
        import gc

        validator = QueryValidator()
        query = "SELECT * FROM test_plugin__data WHERE id = $1"

        # Warm up
        for _ in range(100):
            validator.validate(query, "test_plugin", params=[1])

        gc.collect()

        # Run many iterations
        for _ in range(10000):
            validator.validate(query, "test_plugin", params=[1])

        gc.collect()

        # If we got here without OOM, test passes
        # More sophisticated memory testing would use tracemalloc

    def test_no_memory_leak_in_binder(self):
        """Verify binder doesn't leak memory."""
        import gc

        binder = ParameterBinder()
        query = "SELECT * FROM test_plugin__data WHERE value = $1"
        large_param = "x" * 1000

        # Warm up
        for _ in range(100):
            binder.bind(query, [large_param])

        gc.collect()

        # Run many iterations with large params
        for _ in range(10000):
            binder.bind(query, [large_param])

        gc.collect()

        # If we got here without OOM, test passes


class TestBenchmarkReporting:
    """Generate performance report."""

    def test_generate_benchmark_summary(self, capsys):
        """Generate a summary of all benchmarks."""
        validator = QueryValidator()
        binder = ParameterBinder()

        results = []

        # Run select benchmarks
        def simple_select():
            validator.validate(
                "SELECT * FROM test_plugin__data WHERE id = $1",
                "test_plugin",
                params=[1],
            )

        result = self._benchmark("Simple SELECT validation", simple_select, 1000)
        results.append(result)

        def simple_bind():
            binder.bind("SELECT * FROM test WHERE id = $1", [42])

        result = self._benchmark("Simple parameter binding", simple_bind, 1000)
        results.append(result)

        # Print summary
        print("\n" + "=" * 60)
        print("PARAMETERIZED SQL PERFORMANCE BENCHMARK REPORT")
        print("=" * 60)
        for r in results:
            print(f"\n{r.name}:")
            print(f"  Iterations: {r.iterations}")
            print(f"  Total time: {r.total_time_ms:.2f}ms")
            print(f"  Avg latency: {r.avg_time_ms:.4f}ms")
            print(f"  Throughput: {r.ops_per_second:.0f} ops/sec")
            print(f"  Min/Max: {r.min_time_ms:.4f}ms / {r.max_time_ms:.4f}ms")
        print("\n" + "=" * 60)

    def _benchmark(
        self, name: str, func: callable, iterations: int
    ) -> BenchmarkResult:
        """Run a benchmark."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        total = sum(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=total / iterations,
            ops_per_second=iterations / (total / 1000),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )
