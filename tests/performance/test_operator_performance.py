"""Performance tests for advanced query operators (Sprint 14).

These tests validate that advanced operators meet performance targets:
- Query latency: p95 <50ms
- Concurrent update throughput: >100 ops/sec
- Aggregation queries: reasonable performance on larger datasets

Run with: pytest tests/performance/test_operator_performance.py -v -m performance
"""

import pytest
import time
import asyncio
import statistics
from typing import List

# Mark all tests in this module as performance tests
pytestmark = pytest.mark.performance


@pytest.mark.asyncio
class TestOperatorPerformance:
    """Performance benchmarks for advanced operators."""

    async def test_query_latency_small_dataset(self, db_service):
        """Benchmark query latency with operators (100 queries, 1000 rows)."""
        # Setup: Create 1000 rows
        rows = [
            {
                'username': f'user{i}',
                'score': i % 200,
                'status': 'active' if i % 3 == 0 else 'inactive'
            }
            for i in range(1000)
        ]

        # Bulk insert for efficiency
        for i in range(0, len(rows), 100):
            batch = rows[i:i+100]
            await db_service.handle_row_insert({
                'table': 'users',
                'data': batch
            })

        # Benchmark: 100 queries with operators
        latencies: List[float] = []

        for _ in range(100):
            start = time.perf_counter()

            await db_service.handle_row_search({
                'table': 'users',
                'filters': {
                    '$and': [
                        {'score': {'$gte': 50}},
                        {'status': {'$eq': 'active'}}
                    ]
                },
                'sort': [{'field': 'score', 'order': 'desc'}],
                'limit': 10
            })

            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        print("\n\nQuery Latency Performance (1000 rows, 100 queries):")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        # Assert: p95 < 50ms (target)
        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"

    async def test_concurrent_update_throughput(self, db_service):
        """Test throughput of concurrent atomic updates (100 concurrent ops)."""
        # Setup: Create 10 users
        for i in range(10):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {'username': f'user{i}', 'score': 0}
            })

        # Benchmark: 100 concurrent increments
        start = time.perf_counter()

        tasks = []
        for i in range(100):
            user_id = i % 10  # Distribute across 10 users
            task = db_service.handle_row_update({
                'table': 'users',
                'filters': {'username': {'$eq': f'user{user_id}'}},
                'operations': {'score': {'$inc': 1}}
            })
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - start
        throughput = 100 / elapsed

        print("\n\nConcurrent Update Throughput:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.0f} ops/sec")

        # Verify all updates succeeded
        success_count = sum(1 for r in results if r.get('success', False))
        assert success_count == 100, f"Only {success_count}/100 updates succeeded"

        # Assert: Throughput > 100 ops/sec
        assert throughput > 100, f"Throughput {throughput:.0f} ops/sec below 100 target"

        # Verify final counts are correct (each user should have score == 10)
        for i in range(10):
            result = await db_service.handle_row_search({
                'table': 'users',
                'filters': {'username': {'$eq': f'user{i}'}}
            })
            user = result['rows'][0]
            assert user['score'] == 10, f"user{i} has score {user['score']}, expected 10"

    async def test_aggregation_performance(self, db_service):
        """Benchmark aggregation query performance (1000 rows)."""
        # Setup: 1000 rows
        rows = [
            {
                'username': f'user{i}',
                'score': i % 500,
                'status': 'active' if i % 2 == 0 else 'inactive'
            }
            for i in range(1000)
        ]

        for i in range(0, len(rows), 100):
            batch = rows[i:i+100]
            await db_service.handle_row_insert({
                'table': 'users',
                'data': batch
            })

        # Benchmark: 50 aggregation queries
        latencies: List[float] = []

        for _ in range(50):
            start = time.perf_counter()

            await db_service.handle_row_search({
                'table': 'users',
                'filters': {'status': {'$eq': 'active'}},
                'aggregates': {
                    'total': {'$count': '*'},
                    'avg_score': {'$avg': 'score'},
                    'max_score': {'$max': 'score'}
                }
            })

            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        p95 = statistics.quantiles(latencies, n=20)[18]

        print("\n\nAggregation Query Latency (1000 rows, 50 queries):")
        print(f"  p95: {p95:.2f}ms")

        # Assert: Reasonable performance for aggregations
        assert p95 < 100, f"Aggregation p95 {p95:.2f}ms exceeds 100ms"

    async def test_compound_logic_performance(self, db_service):
        """Test performance of nested compound logic queries."""
        # Setup: 1000 rows
        rows = [
            {
                'username': f'user{i}',
                'score': i % 200,
                'status': 'active' if i % 3 == 0 else 'inactive',
                'premium': (i % 5 == 0)
            }
            for i in range(1000)
        ]

        for i in range(0, len(rows), 100):
            batch = rows[i:i+100]
            await db_service.handle_row_insert({
                'table': 'users',
                'data': batch
            })

        # Benchmark: 100 complex compound queries
        latencies: List[float] = []

        for _ in range(100):
            start = time.perf_counter()

            await db_service.handle_row_search({
                'table': 'users',
                'filters': {
                    '$or': [
                        {
                            '$and': [
                                {'status': {'$eq': 'active'}},
                                {'score': {'$gte': 50}}
                            ]
                        },
                        {
                            '$and': [
                                {'status': {'$eq': 'inactive'}},
                                {'premium': {'$eq': True}}
                            ]
                        }
                    ]
                },
                'sort': [{'field': 'score', 'order': 'desc'}],
                'limit': 20
            })

            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        p95 = statistics.quantiles(latencies, n=20)[18]

        print("\n\nCompound Logic Query Latency (1000 rows, 100 queries):")
        print(f"  p95: {p95:.2f}ms")

        # Assert: Complex queries still performant
        assert p95 < 75, f"Compound logic p95 {p95:.2f}ms exceeds 75ms"

    async def test_pattern_matching_performance(self, db_service):
        """Test performance of pattern matching operators."""
        # Setup: 1000 rows with email addresses
        rows = [
            {
                'username': f'user{i}',
                'email': f'user{i}@{"example" if i % 2 == 0 else "test"}.com',
                'score': i
            }
            for i in range(1000)
        ]

        for i in range(0, len(rows), 100):
            batch = rows[i:i+100]
            await db_service.handle_row_insert({
                'table': 'users',
                'data': batch
            })

        # Benchmark: 100 pattern matching queries
        latencies: List[float] = []

        for _ in range(100):
            start = time.perf_counter()

            await db_service.handle_row_search({
                'table': 'users',
                'filters': {'email': {'$ilike': '%@example.com'}},
                'sort': [{'field': 'score', 'order': 'desc'}],
                'limit': 10
            })

            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        p95 = statistics.quantiles(latencies, n=20)[18]

        print("\n\nPattern Matching Query Latency (1000 rows, 100 queries):")
        print(f"  p95: {p95:.2f}ms")

        # Pattern matching is typically slower, so higher threshold
        assert p95 < 100, f"Pattern matching p95 {p95:.2f}ms exceeds 100ms"


@pytest.fixture
async def db_service(tmp_path):
    """Create a temporary DatabaseService for performance testing."""
    from common.database import BotDatabase
    from bot.rosey.core.database_service import DatabaseService

    # Create temporary database
    db_path = tmp_path / "test_performance.db"
    db = BotDatabase(str(db_path))
    await db.initialize()

    # Create service
    service = DatabaseService(db, plugin_name="test-plugin")

    # Register test schema
    await service.handle_schema_register({
        'table': 'users',
        'schema': {
            'fields': [
                {'name': 'username', 'type': 'string', 'required': True},
                {'name': 'email', 'type': 'string', 'required': False},
                {'name': 'score', 'type': 'integer', 'required': False},
                {'name': 'status', 'type': 'string', 'required': False},
                {'name': 'premium', 'type': 'boolean', 'required': False}
            ]
        }
    })

    yield service

    # Cleanup
    await db.close()
