"""
Integration tests for atomic updates and compound logic (Sprint 14 Sortie 3).

Tests:
- Atomic update operations ($inc, $max, etc.)
- Concurrency handling (race condition prevention)
- Compound logical filters ($and, $or, $not)
"""

import pytest
import asyncio
import json
from common.database import BotDatabase
from common.models import Base

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = None


@pytest.fixture
async def db():
    """Create in-memory database."""
    database = BotDatabase(':memory:')
    
    # Create all tables
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    database._is_connected = True
    await database.schema_registry.load_cache()
    
    yield database
    
    await database.close()


@pytest.mark.asyncio
class TestAtomicUpdates:
    """Test atomic update behavior preventing race conditions."""
    
    async def test_concurrent_increments(self, db: BotDatabase):
        """Test 100 concurrent $inc operations yield correct total."""
        # Setup: Create user with score=0
        await db.row_create('users', {'username': 'alice', 'score': 0, 'status': 'active'})
        
        # Execute 100 concurrent increments
        # Note: In a real scenario, these would come from different requests
        # We simulate this by creating multiple update tasks
        tasks = [
            db.row_update(
                'users',
                {'username': {'$eq': 'alice'}},
                {'score': {'$inc': 1}}
            )
            for _ in range(100)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify: Each update affected 1 row
        assert all(count == 1 for count in results)
        
        # Verify: Final score is exactly 100 (no race condition)
        rows = await db.row_search('users', {'username': {'$eq': 'alice'}})
        assert len(rows) == 1
        assert rows[0]['score'] == 100
    
    async def test_max_operator_behavior(self, db: BotDatabase):
        """Test $max only updates when new value is greater."""
        # Setup
        await db.row_create('users', {'username': 'bob', 'score': 0, 'status': 'active'})
        # We'll use 'score' as high_score since high_score isn't in the default model yet
        # Or we can register a schema for a custom table if needed.
        # Let's use a custom table to match the SPEC exactly if possible, 
        # but BotDatabase uses models.py. 
        # Let's stick to the 'users' table and 'score' field for simplicity, 
        # or register a dynamic schema if BotDatabase supports it easily without models.
        # BotDatabase relies on SQLAlchemy models. 
        # Let's use 'score' as the field to test $max.
        
        await db.row_update(
            'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$set': 50}}
        )
        
        # Try to set lower value (should not update)
        count = await db.row_update(
            'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$max': 30}}
        )
        assert count == 1 # It "updates" the row, but value remains 50
        
        rows = await db.row_search('users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 50  # Unchanged
        
        # Set higher value (should update)
        await db.row_update(
            'users',
            {'username': {'$eq': 'bob'}},
            {'score': {'$max': 75}}
        )
        
        rows = await db.row_search('users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 75  # Updated
    
    async def test_update_with_compound_filter(self, db: BotDatabase):
        """Test update with compound logical filter."""
        # Setup: Create multiple users
        await db.row_create('users', {'username': 'alice', 'score': 120, 'status': 'active'})
        await db.row_create('users', {'username': 'bob', 'score': 80, 'status': 'active'})
        await db.row_create('users', {'username': 'charlie', 'score': 150, 'status': 'inactive'})
        
        # Update: Increment score for active users with score >= 100
        count = await db.row_update(
            'users',
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
        
        rows = await db.row_search('users', {'username': {'$eq': 'alice'}})
        assert rows[0]['score'] == 130
        
        rows = await db.row_search('users', {'username': {'$eq': 'bob'}})
        assert rows[0]['score'] == 80
        
        rows = await db.row_search('users', {'username': {'$eq': 'charlie'}})
        assert rows[0]['score'] == 150
