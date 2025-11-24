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
