"""Unit tests for OperatorParser (Sprint 14 Sortie 1)."""

import pytest
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, DateTime, Float, Boolean, MetaData

from common.query_parsers.operator_parser import OperatorParser


@pytest.fixture
def sample_schema():
    """Sample schema for testing."""
    return {
        'fields': [
            {'name': 'username', 'type': 'string', 'required': True},
            {'name': 'score', 'type': 'integer', 'required': True},
            {'name': 'rating', 'type': 'float', 'required': False},
            {'name': 'active', 'type': 'boolean', 'required': True},
            {'name': 'joined_at', 'type': 'datetime', 'required': True}
        ]
    }


@pytest.fixture
def sample_table():
    """Create sample SQLAlchemy table."""
    metadata = MetaData()
    return Table(
        'test_table',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('username', String(100)),
        Column('score', Integer),
        Column('rating', Float),
        Column('active', Boolean),
        Column('joined_at', DateTime),
        Column('created_at', DateTime),
        Column('updated_at', DateTime)
    )


class TestOperatorParserBasics:
    """Test basic functionality."""

    def test_initialization(self, sample_schema):
        """Test parser initialization."""
        parser = OperatorParser(sample_schema)

        assert len(parser.fields) == 8  # 5 schema + 3 auto fields
        assert 'username' in parser.fields
        assert 'id' in parser.fields
        assert 'created_at' in parser.fields
        assert 'updated_at' in parser.fields

    def test_simple_equality_filter(self, sample_schema, sample_table):
        """Test simple equality (backward compatible)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': 'alice'}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1
        # Clause should compile to: username = 'alice'

    def test_empty_filters(self, sample_schema, sample_table):
        """Test empty filter dict."""
        parser = OperatorParser(sample_schema)

        filters = {}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 0


class TestComparisonOperators:
    """Test comparison operators."""

    def test_eq_operator(self, sample_schema, sample_table):
        """Test $eq operator."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$eq': 100}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_ne_operator(self, sample_schema, sample_table):
        """Test $ne operator."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$ne': 'banned_user'}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_gt_operator(self, sample_schema, sample_table):
        """Test $gt operator."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$gt': 100}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_gte_operator(self, sample_schema, sample_table):
        """Test $gte operator."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$gte': 100}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_lt_operator(self, sample_schema, sample_table):
        """Test $lt operator."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$lt': 4.5}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_lte_operator(self, sample_schema, sample_table):
        """Test $lte operator."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$lte': 5.0}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_multiple_operators_same_field(self, sample_schema, sample_table):
        """Test range query with multiple operators."""
        parser = OperatorParser(sample_schema)

        # score >= 100 AND score <= 200
        filters = {'score': {'$gte': 100, '$lte': 200}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2

    def test_multiple_fields(self, sample_schema, sample_table):
        """Test filters on multiple fields."""
        parser = OperatorParser(sample_schema)

        filters = {
            'score': {'$gte': 100},
            'username': 'alice',
            'active': True
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 3

    def test_mixed_simple_and_operator_filters(self, sample_schema, sample_table):
        """Test mix of simple equality and operator filters."""
        parser = OperatorParser(sample_schema)

        filters = {
            'username': 'alice',  # Simple equality
            'score': {'$gte': 100},  # Operator
            'active': True  # Simple equality
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 3


class TestTypeValidation:
    """Test type validation for operators."""

    def test_range_operator_on_integer_ok(self, sample_schema, sample_table):
        """Test range operator on integer field (should work)."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$gte': 100}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_range_operator_on_float_ok(self, sample_schema, sample_table):
        """Test range operator on float field (should work)."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$gte': 4.0}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_range_operator_on_datetime_ok(self, sample_schema, sample_table):
        """Test range operator on datetime field (should work)."""
        parser = OperatorParser(sample_schema)

        filters = {'joined_at': {'$gte': datetime(2025, 1, 1)}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_range_operator_on_string_fails(self, sample_schema, sample_table):
        """Test range operator on string field (should fail)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$gt': 'a'}}

        with pytest.raises(TypeError, match="requires numeric or datetime type"):
            parser.parse_filters(filters, sample_table)

    def test_range_operator_on_boolean_fails(self, sample_schema, sample_table):
        """Test range operator on boolean field (should fail)."""
        parser = OperatorParser(sample_schema)

        filters = {'active': {'$gte': True}}

        with pytest.raises(TypeError, match="requires numeric or datetime type"):
            parser.parse_filters(filters, sample_table)

    def test_eq_ne_on_any_type_ok(self, sample_schema, sample_table):
        """Test $eq and $ne work on any field type."""
        parser = OperatorParser(sample_schema)

        # String
        clauses1 = parser.parse_filters({'username': {'$eq': 'alice'}}, sample_table)
        assert len(clauses1) == 1

        # Boolean
        clauses2 = parser.parse_filters({'active': {'$ne': False}}, sample_table)
        assert len(clauses2) == 1

        # Integer
        clauses3 = parser.parse_filters({'score': {'$eq': 100}}, sample_table)
        assert len(clauses3) == 1

        # Float
        clauses4 = parser.parse_filters({'rating': {'$eq': 4.5}}, sample_table)
        assert len(clauses4) == 1

        # DateTime
        clauses5 = parser.parse_filters(
            {'joined_at': {'$eq': datetime(2025, 1, 1)}},
            sample_table
        )
        assert len(clauses5) == 1


class TestErrorHandling:
    """Test error handling."""

    def test_unknown_field_error(self, sample_schema, sample_table):
        """Test error for unknown field."""
        parser = OperatorParser(sample_schema)

        filters = {'nonexistent_field': {'$eq': 'value'}}

        with pytest.raises(ValueError, match="Field 'nonexistent_field' not found"):
            parser.parse_filters(filters, sample_table)

    def test_unknown_operator_error(self, sample_schema, sample_table):
        """Test error for unknown operator."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$unknown': 100}}

        with pytest.raises(ValueError, match="Unknown operator '\$unknown'"):
            parser.parse_filters(filters, sample_table)

    def test_error_message_includes_available_fields(self, sample_schema, sample_table):
        """Test error message lists available fields."""
        parser = OperatorParser(sample_schema)

        filters = {'bad_field': 'value'}

        with pytest.raises(ValueError) as exc_info:
            parser.parse_filters(filters, sample_table)

        assert 'Available fields:' in str(exc_info.value)
        assert 'username' in str(exc_info.value)

    def test_error_message_includes_supported_operators(self, sample_schema, sample_table):
        """Test error message lists supported operators."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$bad': 100}}

        with pytest.raises(ValueError) as exc_info:
            parser.parse_filters(filters, sample_table)

        assert 'Supported operators:' in str(exc_info.value)
        assert '$gte' in str(exc_info.value)

    def test_type_error_message_clear(self, sample_schema, sample_table):
        """Test type error message is clear."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$gte': 'alice'}}

        with pytest.raises(TypeError) as exc_info:
            parser.parse_filters(filters, sample_table)

        error_msg = str(exc_info.value)
        assert 'username' in error_msg
        assert '$gte' in error_msg
        assert 'string' in error_msg


class TestValidateFilterDict:
    """Test validate_filter_dict() method."""

    def test_valid_filters_pass(self, sample_schema):
        """Test valid filters pass validation."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$gte': 100}}
        parser.validate_filter_dict(filters)  # Should not raise

    def test_invalid_field_fails(self, sample_schema):
        """Test invalid field fails validation."""
        parser = OperatorParser(sample_schema)

        filters = {'bad_field': {'$eq': 'value'}}

        with pytest.raises(ValueError, match="not found in schema"):
            parser.validate_filter_dict(filters)

    def test_invalid_operator_fails(self, sample_schema):
        """Test invalid operator fails validation."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$bad': 100}}

        with pytest.raises(ValueError, match="Unknown operator"):
            parser.validate_filter_dict(filters)

    def test_type_mismatch_fails(self, sample_schema):
        """Test type mismatch fails validation."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$gte': 'alice'}}

        with pytest.raises(TypeError, match="Cannot use"):
            parser.validate_filter_dict(filters)

    def test_validates_simple_equality(self, sample_schema):
        """Test validation works with simple equality."""
        parser = OperatorParser(sample_schema)

        filters = {'username': 'alice'}
        parser.validate_filter_dict(filters)  # Should not raise

    def test_validates_mixed_filters(self, sample_schema):
        """Test validation with mixed filter types."""
        parser = OperatorParser(sample_schema)

        filters = {
            'username': 'alice',
            'score': {'$gte': 100, '$lte': 200},
            'active': True
        }
        parser.validate_filter_dict(filters)  # Should not raise


class TestAutoManagedFields:
    """Test auto-managed fields (id, created_at, updated_at)."""

    def test_can_filter_on_id(self, sample_schema, sample_table):
        """Test filtering on auto-generated id field."""
        parser = OperatorParser(sample_schema)

        filters = {'id': {'$gte': 100}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_can_filter_on_created_at(self, sample_schema, sample_table):
        """Test filtering on auto-generated created_at field."""
        parser = OperatorParser(sample_schema)

        filters = {'created_at': {'$gte': datetime(2025, 1, 1)}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_can_filter_on_updated_at(self, sample_schema, sample_table):
        """Test filtering on auto-generated updated_at field."""
        parser = OperatorParser(sample_schema)

        filters = {'updated_at': {'$lte': datetime(2025, 12, 31)}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_all_operators_on_single_field(self, sample_schema, sample_table):
        """Test using all valid operators on same field."""
        parser = OperatorParser(sample_schema)

        # All comparison operators on integer field
        filters = {
            'score': {
                '$eq': 100,
                '$ne': 50,
                '$gt': 75,
                '$gte': 80,
                '$lt': 150,
                '$lte': 200
            }
        }
        clauses = parser.parse_filters(filters, sample_table)

        # Should generate 6 clauses
        assert len(clauses) == 6

    def test_datetime_range_query(self, sample_schema, sample_table):
        """Test datetime range query."""
        parser = OperatorParser(sample_schema)

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 12, 31)

        filters = {
            'joined_at': {
                '$gte': start_date,
                '$lte': end_date
            }
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2

    def test_negative_numbers(self, sample_schema, sample_table):
        """Test operators with negative numbers."""
        parser = OperatorParser(sample_schema)

        filters = {
            'score': {'$gt': -100},
            'rating': {'$lte': -1.5}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2

    def test_zero_values(self, sample_schema, sample_table):
        """Test operators with zero values."""
        parser = OperatorParser(sample_schema)

        filters = {
            'score': {'$eq': 0},
            'rating': {'$gt': 0.0}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2


class TestSetOperators:
    """Test set membership operators (Sprint 14 Sortie 2)."""

    def test_in_operator(self, sample_schema, sample_table):
        """Test $in operator."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$in': ['alice', 'bob', 'charlie']}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_nin_operator(self, sample_schema, sample_table):
        """Test $nin operator (not in)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$nin': ['banned_user', 'test_user']}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_in_with_single_value(self, sample_schema, sample_table):
        """Test $in with single-element list."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$in': [100]}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_in_with_integers(self, sample_schema, sample_table):
        """Test $in with multiple integers."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$in': [100, 200, 300]}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_in_requires_list(self, sample_schema, sample_table):
        """Test $in rejects non-list value."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$in': 'alice'}}  # String, not list

        with pytest.raises(TypeError, match="requires list value"):
            parser.parse_filters(filters, sample_table)

    def test_in_requires_nonempty_list(self, sample_schema, sample_table):
        """Test $in rejects empty list."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$in': []}}

        with pytest.raises(ValueError, match="non-empty list"):
            parser.parse_filters(filters, sample_table)

    def test_nin_with_multiple_values(self, sample_schema, sample_table):
        """Test $nin with multiple values."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$nin': [50, 75]}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1


class TestPatternOperators:
    """Test pattern matching operators (Sprint 14 Sortie 2)."""

    def test_like_operator(self, sample_schema, sample_table):
        """Test $like operator (case-sensitive)."""
        parser = OperatorParser(sample_schema)

        # Match usernames starting with 'test_'
        filters = {'username': {'$like': 'test_%'}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_ilike_operator(self, sample_schema, sample_table):
        """Test $ilike operator (case-insensitive)."""
        parser = OperatorParser(sample_schema)

        # Match usernames containing 'alice' (any case)
        filters = {'username': {'$ilike': '%alice%'}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_like_wildcards_percent(self, sample_schema, sample_table):
        """Test % wildcard (zero or more characters)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$like': 'user%'}}
        clauses = parser.parse_filters(filters, sample_table)
        assert len(clauses) == 1

    def test_like_wildcards_underscore(self, sample_schema, sample_table):
        """Test _ wildcard (exactly one character)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$like': 'user_'}}
        clauses = parser.parse_filters(filters, sample_table)
        assert len(clauses) == 1

    def test_like_wildcards_combined(self, sample_schema, sample_table):
        """Test combined wildcards."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$like': 'user_%'}}
        clauses = parser.parse_filters(filters, sample_table)
        assert len(clauses) == 1

    def test_pattern_on_string_field_ok(self, sample_schema, sample_table):
        """Test pattern operator on string field (should work)."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$like': '%test%'}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_pattern_on_integer_fails(self, sample_schema, sample_table):
        """Test pattern operator on integer field (should fail)."""
        parser = OperatorParser(sample_schema)

        filters = {'score': {'$like': '10%'}}

        with pytest.raises(TypeError, match="requires string or text type"):
            parser.parse_filters(filters, sample_table)

    def test_pattern_on_boolean_fails(self, sample_schema, sample_table):
        """Test pattern operator on boolean field (should fail)."""
        parser = OperatorParser(sample_schema)

        filters = {'active': {'$like': 'true%'}}

        with pytest.raises(TypeError, match="requires string or text type"):
            parser.parse_filters(filters, sample_table)

    def test_pattern_requires_string_value(self, sample_schema, sample_table):
        """Test pattern operator rejects non-string value."""
        parser = OperatorParser(sample_schema)

        filters = {'username': {'$like': 123}}  # Integer, not string

        with pytest.raises(TypeError, match="requires string value"):
            parser.parse_filters(filters, sample_table)


class TestExistenceOperators:
    """Test existence/null operators (Sprint 14 Sortie 2)."""

    def test_exists_true(self, sample_schema, sample_table):
        """Test $exists: true (field is not null)."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$exists': True}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_exists_false(self, sample_schema, sample_table):
        """Test $exists: false (field is null)."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$exists': False}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_null_true(self, sample_schema, sample_table):
        """Test $null: true (field is null)."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$null': True}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_null_false(self, sample_schema, sample_table):
        """Test $null: false (field is not null)."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$null': False}}
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_exists_requires_boolean(self, sample_schema, sample_table):
        """Test $exists rejects non-boolean value."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$exists': 'true'}}  # String, not bool

        with pytest.raises(TypeError, match="requires boolean value"):
            parser.parse_filters(filters, sample_table)

    def test_null_requires_boolean(self, sample_schema, sample_table):
        """Test $null rejects non-boolean value."""
        parser = OperatorParser(sample_schema)

        filters = {'rating': {'$null': 1}}  # Integer, not bool

        with pytest.raises(TypeError, match="requires boolean value"):
            parser.parse_filters(filters, sample_table)

    def test_exists_on_string_field(self, sample_schema, sample_table):
        """Test $exists works on string fields."""
        parser = OperatorParser(sample_schema)

        clauses = parser.parse_filters({'username': {'$exists': True}}, sample_table)
        assert len(clauses) == 1

    def test_exists_on_integer_field(self, sample_schema, sample_table):
        """Test $exists works on integer fields."""
        parser = OperatorParser(sample_schema)

        clauses = parser.parse_filters({'score': {'$exists': False}}, sample_table)
        assert len(clauses) == 1

    def test_exists_on_boolean_field(self, sample_schema, sample_table):
        """Test $exists works on boolean fields."""
        parser = OperatorParser(sample_schema)

        clauses = parser.parse_filters({'active': {'$exists': True}}, sample_table)
        assert len(clauses) == 1


class TestCombinedOperatorsSortie2:
    """Test combining new operators with existing ones (Sprint 14 Sortie 2)."""

    def test_in_and_comparison(self, sample_schema, sample_table):
        """Test combining $in with comparison operators."""
        parser = OperatorParser(sample_schema)

        filters = {
            'score': {'$gte': 100},
            'username': {'$in': ['alice', 'bob']}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2

    def test_pattern_and_existence(self, sample_schema, sample_table):
        """Test combining pattern and existence operators."""
        parser = OperatorParser(sample_schema)

        filters = {
            'username': {'$like': 'test_%'},
            'rating': {'$exists': True}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2

    def test_all_operator_types_combined(self, sample_schema, sample_table):
        """Test combining operators from Sortie 1 and Sortie 2."""
        parser = OperatorParser(sample_schema)

        filters = {
            'score': {'$gte': 100, '$lte': 200},  # Comparison
            'username': {'$like': '%user%'},      # Pattern
            'rating': {'$exists': True}            # Existence
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 4  # 2 for score range, 1 pattern, 1 existence

    def test_set_and_pattern_and_comparison(self, sample_schema, sample_table):
        """Test set + pattern + comparison operators."""
        parser = OperatorParser(sample_schema)

        filters = {
            'username': {'$like': 'user%'},
            'score': {'$in': [100, 200, 300]},
            'rating': {'$gte': 4.0}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 3

    def test_nin_and_exists(self, sample_schema, sample_table):
        """Test $nin with $exists."""
        parser = OperatorParser(sample_schema)

        filters = {
            'username': {'$nin': ['banned', 'deleted']},
            'rating': {'$exists': True}
        }
        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 2


class TestUpdateOperators:
    """Test update operator parsing (Sprint 14 Sortie 3)."""

    def test_set_operator(self, sample_schema, sample_table):
        """Test $set operator for direct assignment."""
        parser = OperatorParser(sample_schema)
        ops = {'username': {'$set': 'alice'}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'username' in updates
        assert updates['username'] == 'alice'

    def test_inc_operator(self, sample_schema, sample_table):
        """Test $inc operator for incrementing."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$inc': 10}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'score' in updates
        # Should be SQLAlchemy expression
        assert str(updates['score']).find('score') >= 0

    def test_dec_operator(self, sample_schema, sample_table):
        """Test $dec operator for decrementing."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$dec': 5}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'score' in updates

    def test_mul_operator(self, sample_schema, sample_table):
        """Test $mul operator for multiplication."""
        parser = OperatorParser(sample_schema)
        ops = {'rating': {'$mul': 2.5}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'rating' in updates

    def test_max_operator(self, sample_schema, sample_table):
        """Test $max operator for maximum value."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$max': 100}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'score' in updates
        # Should use func.greatest()
        assert 'greatest' in str(updates['score']).lower()

    def test_min_operator(self, sample_schema, sample_table):
        """Test $min operator for minimum value."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$min': 50}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'score' in updates
        # Should use func.least()
        assert 'least' in str(updates['score']).lower()

    def test_multiple_update_operations(self, sample_schema, sample_table):
        """Test multiple update operations in one call."""
        parser = OperatorParser(sample_schema)
        ops = {
            'score': {'$inc': 10},
            'rating': {'$max': 95.0},
            'username': {'$set': 'bob'}
        }

        updates = parser.parse_update_operations(ops, sample_table)

        assert len(updates) == 3
        assert 'score' in updates
        assert 'rating' in updates
        assert 'username' in updates

    def test_inc_on_float_field(self, sample_schema, sample_table):
        """Test $inc works on float fields."""
        parser = OperatorParser(sample_schema)
        ops = {'rating': {'$inc': 0.5}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'rating' in updates

    def test_max_on_datetime_field(self, sample_schema, sample_table):
        """Test $max works on datetime fields."""
        parser = OperatorParser(sample_schema)
        now = datetime(2024, 1, 1, 12, 0, 0)
        ops = {'joined_at': {'$max': now}}

        updates = parser.parse_update_operations(ops, sample_table)

        assert 'joined_at' in updates

    def test_invalid_field_name(self, sample_schema, sample_table):
        """Test error on invalid field name."""
        parser = OperatorParser(sample_schema)
        ops = {'nonexistent': {'$inc': 1}}

        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_update_operations(ops, sample_table)

    def test_unknown_operator(self, sample_schema, sample_table):
        """Test error on unknown update operator."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$invalid': 10}}

        with pytest.raises(ValueError, match="Unknown update operator"):
            parser.parse_update_operations(ops, sample_table)

    def test_numeric_operator_on_string_field(self, sample_schema, sample_table):
        """Test error when using numeric operator on string field."""
        parser = OperatorParser(sample_schema)
        ops = {'username': {'$inc': 1}}

        with pytest.raises(TypeError, match="requires numeric type"):
            parser.parse_update_operations(ops, sample_table)

    def test_numeric_operator_on_boolean_field(self, sample_schema, sample_table):
        """Test error when using numeric operator on boolean field."""
        parser = OperatorParser(sample_schema)
        ops = {'active': {'$mul': 2}}

        with pytest.raises(TypeError, match="requires numeric type"):
            parser.parse_update_operations(ops, sample_table)

    def test_inc_with_non_numeric_value(self, sample_schema, sample_table):
        """Test error when $inc value is not numeric."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$inc': 'ten'}}

        with pytest.raises(TypeError, match="requires numeric value"):
            parser.parse_update_operations(ops, sample_table)

    def test_invalid_operation_format(self, sample_schema, sample_table):
        """Test error when operation is not a dict."""
        parser = OperatorParser(sample_schema)
        ops = {'score': 10}  # Should be {'$set': 10}

        with pytest.raises(TypeError, match="must be dict"):
            parser.parse_update_operations(ops, sample_table)

    def test_multiple_operators_per_field(self, sample_schema, sample_table):
        """Test error when field has multiple operators."""
        parser = OperatorParser(sample_schema)
        ops = {'score': {'$inc': 5, '$set': 100}}

        with pytest.raises(ValueError, match="exactly one update operator"):
            parser.parse_update_operations(ops, sample_table)

    def test_max_on_string_field_fails(self, sample_schema, sample_table):
        """Test error when using $max on string field."""
        parser = OperatorParser(sample_schema)
        ops = {'username': {'$max': 'zzz'}}

        with pytest.raises(TypeError, match="requires numeric or timestamp type"):
            parser.parse_update_operations(ops, sample_table)


class TestCompoundLogic:
    """Test compound logical operators (Sprint 14 Sortie 3)."""

    def test_and_operator_simple(self, sample_schema, sample_table):
        """Test $and with simple conditions."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$and': [
                {'score': {'$gte': 100}},
                {'active': {'$eq': True}}
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1
        # Should contain AND clause

    def test_or_operator_simple(self, sample_schema, sample_table):
        """Test $or with simple conditions."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$or': [
                {'username': {'$eq': 'alice'}},
                {'username': {'$eq': 'bob'}}
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1
        # Should contain OR clause

    def test_not_operator_simple(self, sample_schema, sample_table):
        """Test $not with simple condition."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$not': {'score': {'$lt': 50}}
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1
        # Should contain NOT clause

    def test_nested_and_or(self, sample_schema, sample_table):
        """Test nested $and containing $or."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$and': [
                {'score': {'$gte': 100}},
                {
                    '$or': [
                        {'username': {'$eq': 'alice'}},
                        {'username': {'$eq': 'bob'}}
                    ]
                }
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_nested_or_and(self, sample_schema, sample_table):
        """Test nested $or containing $and."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$or': [
                {
                    '$and': [
                        {'score': {'$gte': 100}},
                        {'active': {'$eq': True}}
                    ]
                },
                {'username': {'$eq': 'admin'}}
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_not_with_compound_condition(self, sample_schema, sample_table):
        """Test $not with compound condition."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$not': {
                '$and': [
                    {'score': {'$lt': 50}},
                    {'active': {'$eq': False}}
                ]
            }
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_and_with_set_operators(self, sample_schema, sample_table):
        """Test $and with set operators."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$and': [
                {'username': {'$in': ['alice', 'bob', 'charlie']}},
                {'score': {'$gte': 100}}
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_or_with_pattern_operators(self, sample_schema, sample_table):
        """Test $or with pattern operators."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$or': [
                {'username': {'$like': 'test_%'}},
                {'username': {'$like': 'admin_%'}}
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1

    def test_and_empty_list(self, sample_schema, sample_table):
        """Test error on empty $and list."""
        parser = OperatorParser(sample_schema)
        filters = {'$and': []}

        with pytest.raises(ValueError, match="at least one condition"):
            parser.parse_filters(filters, sample_table)

    def test_or_not_list(self, sample_schema, sample_table):
        """Test error when $or value is not a list."""
        parser = OperatorParser(sample_schema)
        filters = {'$or': {'score': {'$gte': 100}}}

        with pytest.raises(TypeError, match="requires a list"):
            parser.parse_filters(filters, sample_table)

    def test_not_not_dict(self, sample_schema, sample_table):
        """Test error when $not value is not a dict."""
        parser = OperatorParser(sample_schema)
        filters = {'$not': ['score', '>', 100]}

        with pytest.raises(TypeError, match="requires a dict"):
            parser.parse_filters(filters, sample_table)

    def test_unknown_logical_operator(self, sample_schema, sample_table):
        """Test error on unknown logical operator."""
        parser = OperatorParser(sample_schema)
        filters = {'$xor': [{'score': {'$gte': 100}}]}

        with pytest.raises(ValueError, match="Unknown logical operator"):
            parser.parse_filters(filters, sample_table)

    def test_deeply_nested_logic(self, sample_schema, sample_table):
        """Test deeply nested compound logic."""
        parser = OperatorParser(sample_schema)
        filters = {
            '$and': [
                {
                    '$or': [
                        {'score': {'$gte': 100}},
                        {'rating': {'$gte': 4.5}}
                    ]
                },
                {
                    '$not': {
                        'username': {'$in': ['banned', 'deleted']}
                    }
                }
            ]
        }

        clauses = parser.parse_filters(filters, sample_table)

        assert len(clauses) == 1


class TestAggregations:
    """Test aggregation function parsing (Sortie 4)."""

    def test_count_all(self, sample_schema, sample_table):
        """Test COUNT(*) aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'total': {'$count': '*'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'total'

    def test_count_field(self, sample_schema, sample_table):
        """Test COUNT(field) aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'user_count': {'$count': 'username'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'user_count'

    def test_sum_aggregation(self, sample_schema, sample_table):
        """Test SUM aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'total_score': {'$sum': 'score'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'total_score'

    def test_avg_aggregation(self, sample_schema, sample_table):
        """Test AVG aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'avg_rating': {'$avg': 'rating'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'avg_rating'

    def test_min_aggregation(self, sample_schema, sample_table):
        """Test MIN aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'min_score': {'$min': 'score'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'min_score'

    def test_max_aggregation(self, sample_schema, sample_table):
        """Test MAX aggregation."""
        parser = OperatorParser(sample_schema)
        aggs = {'max_score': {'$max': 'score'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'max_score'

    def test_multiple_aggregations(self, sample_schema, sample_table):
        """Test multiple aggregations in one query."""
        parser = OperatorParser(sample_schema)
        aggs = {
            'total': {'$count': '*'},
            'total_score': {'$sum': 'score'},
            'avg_score': {'$avg': 'score'},
            'min_score': {'$min': 'score'},
            'max_score': {'$max': 'score'},
        }

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 5
        names = [expr.name for expr in exprs]
        assert 'total' in names
        assert 'avg_score' in names

    def test_min_on_datetime_field(self, sample_schema, sample_table):
        """Test MIN on datetime field (valid)."""
        parser = OperatorParser(sample_schema)
        aggs = {'earliest': {'$min': 'joined_at'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'earliest'

    def test_max_on_string_field(self, sample_schema, sample_table):
        """Test MAX on string field (valid - lexicographic comparison)."""
        parser = OperatorParser(sample_schema)
        aggs = {'last_name': {'$max': 'username'}}

        exprs = parser.parse_aggregations(aggs, sample_table)

        assert len(exprs) == 1
        assert exprs[0].name == 'last_name'

    def test_sum_on_non_numeric_field(self, sample_schema, sample_table):
        """Test error when SUM applied to non-numeric field."""
        parser = OperatorParser(sample_schema)
        aggs = {'total': {'$sum': 'username'}}

        with pytest.raises(TypeError, match="requires numeric field"):
            parser.parse_aggregations(aggs, sample_table)

    def test_avg_on_string_field(self, sample_schema, sample_table):
        """Test error when AVG applied to string field."""
        parser = OperatorParser(sample_schema)
        aggs = {'avg_name': {'$avg': 'username'}}

        with pytest.raises(TypeError, match="requires numeric field"):
            parser.parse_aggregations(aggs, sample_table)

    def test_avg_on_boolean_field(self, sample_schema, sample_table):
        """Test error when AVG applied to boolean field."""
        parser = OperatorParser(sample_schema)
        aggs = {'avg_active': {'$avg': 'active'}}

        with pytest.raises(TypeError, match="requires numeric field"):
            parser.parse_aggregations(aggs, sample_table)

    def test_unknown_function(self, sample_schema, sample_table):
        """Test error on unknown aggregation function."""
        parser = OperatorParser(sample_schema)
        aggs = {'result': {'$median': 'score'}}

        with pytest.raises(ValueError, match="Unknown aggregation function"):
            parser.parse_aggregations(aggs, sample_table)

    def test_invalid_field_name(self, sample_schema, sample_table):
        """Test error on invalid field name."""
        parser = OperatorParser(sample_schema)
        aggs = {'total': {'$sum': 'nonexistent'}}

        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_aggregations(aggs, sample_table)

    def test_malformed_spec_not_dict(self, sample_schema, sample_table):
        """Test error when spec is not a dict."""
        parser = OperatorParser(sample_schema)
        aggs = {'total': '$count'}  # Should be {'$count': '*'}

        with pytest.raises(TypeError, match="must be dict"):
            parser.parse_aggregations(aggs, sample_table)

    def test_malformed_spec_multiple_functions(self, sample_schema, sample_table):
        """Test error when spec has multiple functions."""
        parser = OperatorParser(sample_schema)
        aggs = {'result': {'$sum': 'score', '$avg': 'score'}}

        with pytest.raises(ValueError, match="exactly one function"):
            parser.parse_aggregations(aggs, sample_table)

    def test_empty_result_name(self, sample_schema, sample_table):
        """Test error on empty result name."""
        parser = OperatorParser(sample_schema)
        aggs = {'': {'$count': '*'}}

        with pytest.raises(ValueError, match="non-empty string"):
            parser.parse_aggregations(aggs, sample_table)


class TestMultiFieldSorting:
    """Test multi-field sorting (Sortie 4)."""

    def test_single_field_dict(self, sample_schema, sample_table):
        """Test backward compatible single-field sort dict."""
        parser = OperatorParser(sample_schema)
        sort = {'field': 'score', 'order': 'desc'}

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 1

    def test_single_field_list(self, sample_schema, sample_table):
        """Test single-field sort as list."""
        parser = OperatorParser(sample_schema)
        sort = [{'field': 'username', 'order': 'asc'}]

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 1

    def test_multi_field_two_sorts(self, sample_schema, sample_table):
        """Test two-field sort."""
        parser = OperatorParser(sample_schema)
        sort = [
            {'field': 'active', 'order': 'asc'},
            {'field': 'score', 'order': 'desc'}
        ]

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 2

    def test_multi_field_three_sorts(self, sample_schema, sample_table):
        """Test three-field sort with priority order."""
        parser = OperatorParser(sample_schema)
        sort = [
            {'field': 'active', 'order': 'asc'},
            {'field': 'score', 'order': 'desc'},
            {'field': 'username', 'order': 'asc'}
        ]

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 3

    def test_default_order_asc(self, sample_schema, sample_table):
        """Test default order is 'asc' when not specified."""
        parser = OperatorParser(sample_schema)
        sort = [{'field': 'score'}]  # No 'order' key

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 1

    def test_mixed_asc_desc(self, sample_schema, sample_table):
        """Test mixed ascending and descending sorts."""
        parser = OperatorParser(sample_schema)
        sort = [
            {'field': 'score', 'order': 'desc'},
            {'field': 'username', 'order': 'asc'},
            {'field': 'rating', 'order': 'desc'}
        ]

        clauses = parser.parse_sort(sort, sample_table)

        assert len(clauses) == 3

    def test_invalid_field_name(self, sample_schema, sample_table):
        """Test error on invalid field name."""
        parser = OperatorParser(sample_schema)
        sort = [{'field': 'nonexistent', 'order': 'asc'}]

        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_sort(sort, sample_table)

    def test_invalid_order_value(self, sample_schema, sample_table):
        """Test error on invalid order value."""
        parser = OperatorParser(sample_schema)
        sort = [{'field': 'score', 'order': 'ascending'}]

        with pytest.raises(ValueError, match="must be 'asc' or 'desc'"):
            parser.parse_sort(sort, sample_table)

    def test_missing_field_key(self, sample_schema, sample_table):
        """Test error when 'field' key missing."""
        parser = OperatorParser(sample_schema)
        sort = [{'order': 'asc'}]  # No 'field' key

        with pytest.raises(ValueError, match="missing required 'field' key"):
            parser.parse_sort(sort, sample_table)

    def test_empty_sort_list(self, sample_schema, sample_table):
        """Test error on empty sort list."""
        parser = OperatorParser(sample_schema)
        sort = []

        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse_sort(sort, sample_table)

    def test_invalid_sort_type(self, sample_schema, sample_table):
        """Test error when sort is not dict or list."""
        parser = OperatorParser(sample_schema)
        sort = "score"

        with pytest.raises(TypeError, match="must be dict or list"):
            parser.parse_sort(sort, sample_table)

    def test_sort_item_not_dict(self, sample_schema, sample_table):
        """Test error when sort list item is not dict."""
        parser = OperatorParser(sample_schema)
        sort = ['score', 'username']  # Should be list of dicts

        with pytest.raises(TypeError, match="must be dict"):
            parser.parse_sort(sort, sample_table)
