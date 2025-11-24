"""End-to-end integration tests for advanced query operators (Sprint 14).

Tests complex query scenarios combining multiple operator types:
- Compound logic with nested conditions
- Aggregations with filters and sorting
- Atomic updates under concurrency
- Pattern matching and existence operators
- Multi-field sorting with priority order
"""

import pytest
import asyncio
from datetime import datetime, UTC


@pytest.mark.asyncio
class TestAdvancedOperatorsIntegration:
    """End-to-end tests for all advanced operators."""
    
    async def test_complex_query_all_operators(self, db_service):
        """Test complex query combining multiple operator types."""
        # Setup: Create diverse user data
        users = [
            {'username': 'alice', 'score': 120, 'status': 'active', 'email': 'alice@example.com'},
            {'username': 'bob', 'score': 80, 'status': 'inactive', 'email': 'bob@example.com'},
            {'username': 'charlie', 'score': 95, 'status': 'active', 'email': 'charlie@test.com'},
            {'username': 'diana', 'score': 110, 'status': 'pending', 'email': 'diana@example.com'},
            {'username': 'eve', 'score': 150, 'status': 'active', 'email': None},
        ]
        
        for user in users:
            await db_service.handle_row_insert({'table': 'users', 'data': user})
        
        # Query: Active users with score >= 100, email exists, sorted by score DESC
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {
                '$and': [
                    {'status': {'$eq': 'active'}},
                    {'score': {'$gte': 100}},
                    {'email': {'$exists': True}}
                ]
            },
            'sort': [{'field': 'score', 'order': 'desc'}]
        })
        
        # Verify: Only alice (120) matches (charlie is 95, eve has no email)
        assert result['success']
        assert result['count'] == 1
        assert result['rows'][0]['username'] == 'alice'
        assert result['rows'][0]['score'] == 120
    
    async def test_nested_compound_logic(self, db_service):
        """Test deeply nested compound logic."""
        # Setup
        for i in range(10):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {
                    'username': f'user{i}',
                    'score': i * 10,
                    'status': 'active' if i % 2 == 0 else 'inactive',
                    'premium': (i % 3 == 0)
                }
            })
        
        # Query: (active AND score >= 50) OR (inactive AND premium)
        result = await db_service.handle_row_search({
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
            }
        })
        
        # Verify complex logic
        assert result['success']
        assert result['count'] > 0
        
        for row in result['rows']:
            is_match = (
                (row['status'] == 'active' and row['score'] >= 50) or
                (row['status'] == 'inactive' and row['premium'] is True)
            )
            assert is_match, f"Row {row} doesn't match filter logic"
    
    async def test_aggregation_with_filters(self, db_service):
        """Test aggregation combined with filters."""
        # Setup
        for i in range(20):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {
                    'username': f'user{i}',
                    'score': i * 5,
                    'status': 'active' if i % 2 == 0 else 'inactive'
                }
            })
        
        # Query: Aggregation of active users
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'status': {'$eq': 'active'}},
            'aggregates': {
                'total': {'$count': '*'},
                'avg_score': {'$avg': 'score'},
                'max_score': {'$max': 'score'}
            }
        })
        
        assert result['success']
        assert result['total'] == 10  # Half are active
        assert result['avg_score'] > 0
        assert result['max_score'] == 90  # user18: 18 * 5 = 90
    
    async def test_atomic_update_concurrency(self, db_service):
        """Test atomic updates prevent race conditions."""
        # Setup: Create user
        await db_service.handle_row_insert({
            'table': 'users',
            'data': {'username': 'alice', 'score': 0}
        })
        
        # Execute 100 concurrent increments
        tasks = [
            db_service.handle_row_update({
                'table': 'users',
                'filters': {'username': {'$eq': 'alice'}},
                'operations': {'score': {'$inc': 1}}
            })
            for _ in range(100)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify: All updates succeeded
        assert all(r.get('success', False) for r in results)
        
        # Verify: Final score is exactly 100
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert result['rows'][0]['score'] == 100
    
    async def test_update_with_compound_filter(self, db_service):
        """Test update with complex compound filter."""
        # Setup
        for i in range(10):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {
                    'username': f'user{i}',
                    'score': i * 10,
                    'status': 'active' if i >= 5 else 'inactive'
                }
            })
        
        # Update: Increment score for active users with score < 80
        result = await db_service.handle_row_update({
            'table': 'users',
            'filters': {
                '$and': [
                    {'status': {'$eq': 'active'}},
                    {'score': {'$lt': 80}}
                ]
            },
            'operations': {'score': {'$inc': 5}}
        })
        
        # Verify: user5 (50), user6 (60), user7 (70) updated
        assert result['success']
        assert result['updated_count'] == 3
        
        search_result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$in': ['user5', 'user6', 'user7']}},
            'sort': [{'field': 'username', 'order': 'asc'}]
        })
        
        assert search_result['rows'][0]['score'] == 55
        assert search_result['rows'][1]['score'] == 65
        assert search_result['rows'][2]['score'] == 75
    
    async def test_pattern_matching_operators(self, db_service):
        """Test $like and $ilike pattern operators."""
        # Setup
        emails = [
            'alice@example.com',
            'bob@test.com',
            'Charlie@Example.com',  # Note: mixed case
            'diana@example.org'
        ]
        
        for i, email in enumerate(emails):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {'username': f'user{i}', 'email': email, 'score': i}
            })
        
        # Query: Case-insensitive match for @example.com
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'email': {'$ilike': '%@example.com'}}
        })
        
        # Verify: alice and Charlie (case-insensitive)
        assert result['success']
        assert result['count'] == 2
        usernames = {row['username'] for row in result['rows']}
        assert usernames == {'user0', 'user2'}
    
    async def test_set_operators_in_nin(self, db_service):
        """Test $in and $nin set operators."""
        # Setup
        statuses = ['active', 'inactive', 'pending', 'banned', 'trial']
        for i, status in enumerate(statuses):
            await db_service.handle_row_insert({
                'table': 'users',
                'data': {'username': f'user{i}', 'status': status, 'score': i * 10}
            })
        
        # Query: Status in [active, trial]
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'status': {'$in': ['active', 'trial']}}
        })
        
        assert result['success']
        assert result['count'] == 2
        statuses_found = {row['status'] for row in result['rows']}
        assert statuses_found == {'active', 'trial'}
        
        # Query: Status not in [banned, deleted]
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'status': {'$nin': ['banned', 'deleted']}}
        })
        
        assert result['success']
        assert result['count'] == 4  # All except banned
    
    async def test_multi_field_sorting(self, db_service):
        """Test multi-field sorting with priority order."""
        # Setup: Create users with varied status and scores
        users = [
            {'username': 'alice', 'score': 100, 'status': 'active'},
            {'username': 'bob', 'score': 120, 'status': 'active'},
            {'username': 'charlie', 'score': 90, 'status': 'inactive'},
            {'username': 'diana', 'score': 110, 'status': 'inactive'},
        ]
        
        for user in users:
            await db_service.handle_row_insert({'table': 'users', 'data': user})
        
        # Query: Sort by status ASC, then score DESC
        result = await db_service.handle_row_search({
            'table': 'users',
            'sort': [
                {'field': 'status', 'order': 'asc'},
                {'field': 'score', 'order': 'desc'}
            ]
        })
        
        # Expected order:
        # 1. bob (active, 120)
        # 2. alice (active, 100)
        # 3. diana (inactive, 110)
        # 4. charlie (inactive, 90)
        assert result['success']
        assert len(result['rows']) == 4
        assert result['rows'][0]['username'] == 'bob'
        assert result['rows'][1]['username'] == 'alice'
        assert result['rows'][2]['username'] == 'diana'
        assert result['rows'][3]['username'] == 'charlie'
    
    async def test_existence_operators(self, db_service):
        """Test $exists and $null operators."""
        # Setup
        users = [
            {'username': 'alice', 'email': 'alice@example.com', 'score': 100},
            {'username': 'bob', 'email': None, 'score': 80},
            {'username': 'charlie', 'email': 'charlie@test.com', 'score': 90},
        ]
        
        for user in users:
            await db_service.handle_row_insert({'table': 'users', 'data': user})
        
        # Query: Users with email addresses
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'email': {'$exists': True}}
        })
        
        assert result['success']
        assert result['count'] == 2
        usernames = {row['username'] for row in result['rows']}
        assert usernames == {'alice', 'charlie'}
        
        # Query: Users without email addresses
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'email': {'$null': False}}  # email IS NOT NULL
        })
        
        assert result['success']
        assert result['count'] == 2  # Same as $exists: True
    
    async def test_update_operators_all_types(self, db_service):
        """Test all update operators: $set, $inc, $dec, $mul, $max, $min."""
        # Setup
        await db_service.handle_row_insert({
            'table': 'users',
            'data': {'username': 'alice', 'score': 50}
        })
        
        # Test $inc
        result = await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}},
            'operations': {'score': {'$inc': 10}}
        })
        assert result['success']
        
        search = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert search['rows'][0]['score'] == 60
        
        # Test $dec
        await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}},
            'operations': {'score': {'$dec': 5}}
        })
        
        search = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert search['rows'][0]['score'] == 55
        
        # Test $mul
        await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}},
            'operations': {'score': {'$mul': 2}}
        })
        
        search = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert search['rows'][0]['score'] == 110
        
        # Test $max (won't decrease)
        await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}},
            'operations': {'score': {'$max': 100}}
        })
        
        search = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert search['rows'][0]['score'] == 110  # Didn't decrease
        
        # Test $min (won't increase)
        await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}},
            'operations': {'score': {'$min': 90}}
        })
        
        search = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': {'$eq': 'alice'}}
        })
        assert search['rows'][0]['score'] == 90  # Decreased to min
    
    async def test_backward_compatibility_sprint_13(self, db_service):
        """Test backward compatibility with Sprint 13 API."""
        # Setup
        await db_service.handle_row_insert({
            'table': 'users',
            'data': {'username': 'alice', 'score': 100, 'status': 'active'}
        })
        
        # Old Sprint 13 style: Simple equality filter (no operators)
        result = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': 'alice'}  # Not using operators
        })
        
        # Should still work (backward compatible)
        assert result['success']
        assert result['count'] == 1
        assert result['rows'][0]['username'] == 'alice'
        
        # Old Sprint 13 style: Traditional update (no operations)
        update_result = await db_service.handle_row_update({
            'table': 'users',
            'filters': {'username': 'alice'},
            'data': {'status': 'inactive'}  # Using 'data' not 'operations'
        })
        
        assert update_result['success']
        
        verify = await db_service.handle_row_search({
            'table': 'users',
            'filters': {'username': 'alice'}
        })
        assert verify['rows'][0]['status'] == 'inactive'


@pytest.fixture
async def db_service(tmp_path):
    """Create a temporary DatabaseService for integration testing."""
    from common.database import BotDatabase
    from bot.rosey.core.database_service import DatabaseService
    
    # Create temporary database
    db_path = tmp_path / "test_integration.db"
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
