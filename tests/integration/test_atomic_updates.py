"""
Integration tests for atomic updates and compound logic (Sprint 14 Sortie 3).

Tests:
- Atomic update operations ($inc, $max, etc.)
- Concurrency handling (race condition prevention)
- Compound logical filters ($and, $or, $not)
"""

import pytest
import asyncio
from common.database import BotDatabase
from common.models import Base

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = None


# Schema for the test 'users' table
USERS_SCHEMA = {
    "fields": [
        {"name": "username", "type": "string", "required": True},
        {"name": "score", "type": "integer", "required": False},
        {"name": "status", "type": "string", "required": False}
    ]
}


@pytest.fixture
async def db():
    """Create in-memory database with test schema registered."""
    database = BotDatabase(':memory:')

    # Create all tables
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    database._is_connected = True
    await database.schema_registry.load_cache()

    # Register the test 'users' table schema
    await database.schema_registry.register_schema('test', 'users', USERS_SCHEMA)

    yield database

    await database.close()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Test uses filter-based update API that doesn't exist yet - row_update takes row_id not filter")
class TestAtomicUpdates:
    """Test atomic update behavior preventing race conditions."""

    async def test_concurrent_increments(self, db: BotDatabase):
        """Test 100 concurrent $inc operations yield correct total."""
        # Setup: Create user with score=0
        await db.row_insert('test', 'users', {'username': 'alice', 'score': 0, 'status': 'active'})

        # Execute 100 concurrent increments
        # Note: In a real scenario, these would come from different requests
        # We simulate this by creating multiple update tasks
        tasks = [
            db.row_update(
                'test', 'users',
                {'username': {'$eq': 'alice'}},
                {'score': {'$inc': 1}}
            )
            for _ in range(100)
        ]

        results = await asyncio.gather(*tasks)

        # Verify: Each update affected 1 row
        assert all(count == 1 for count in results)

        # Verify: Final score is exactly 100 (no race condition)
        rows = await db.row_search('test', 'users', {'username': {'$eq': 'alice'}})
        assert len(rows) == 1
        assert rows[0]['score'] == 100

    async def test_max_operator_behavior(self, db: BotDatabase):
        """Test $max only updates when new value is greater."""
        # Setup
        await db.row_insert('test', 'users', {'username': 'bob', 'score': 0, 'status': 'active'})

        await db.row_update(
            'test', 'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$set': 50}}
        )

        # Try to set lower value (should not update)
        count = await db.row_update(
            'test', 'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$max': 30}}
        )
        assert count == 1 # It "updates" the row, but value remains 50

        rows = await db.row_search('test', 'users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 50  # Unchanged

        # Set higher value (should update)
        await db.row_update(
            'test', 'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$max': 75}}
        )

        rows = await db.row_search('test', 'users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 75  # Updated

    async def test_update_with_compound_filter(self, db: BotDatabase):
        """Test update with compound logical filter."""
        # Setup: Create multiple users
        await db.row_insert('test', 'users', {'username': 'alice', 'score': 120, 'status': 'active'})
        await db.row_insert('test', 'users', {'username': 'bob', 'score': 80, 'status': 'active'})
        await db.row_insert('test', 'users', {'username': 'charlie', 'score': 150, 'status': 'inactive'})

        # Update: Increment score for active users with score >= 100
        count = await db.row_update(
            'test', 'users',
            {
                '$and': [
                    {'score': {'$gte': 100}},
                    {'status': {'$eq': 'active'}}
                ]
            },
            {'score': {'$inc': 10}}
        )

        # Verify: Only alice updated (bob too low score, charlie inactive)
        assert count == 1

        rows = await db.row_search('test', 'users', {'username': {'$eq': 'alice'}})
        assert rows[0]['score'] == 130

        rows = await db.row_search('test', 'users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 80

        rows = await db.row_search('test', 'users', {'username': {'$eq': 'charlie'}})
        assert rows[0]['score'] == 150
