# SPEC: Sortie 1 - Operator Parser Foundation

**Sprint**: 14 (Advanced Query Operators)  
**Sortie**: 1 of 5  
**Estimated Effort**: ~5 hours  
**Branch**: `feature/sprint-14-sortie-1-operator-parser`  
**Dependencies**: Sprint 13 complete (Row Operations Foundation)

---

## 1. Overview

Create the foundational `OperatorParser` class that parses MongoDB-style query operators into SQLAlchemy where clauses, starting with basic comparison operators ($eq, $ne, $gt, $gte, $lt, $lte).

**What This Sortie Achieves**:

- OperatorParser class with schema awareness
- Comparison operator parsing ($eq, $ne, $gt, $gte, $lt, $lte)
- Type validation (numeric/datetime operators on appropriate fields)
- SQLAlchemy clause generation
- Foundation for extended operators in Sortie 2

---

## 2. Scope and Non-Goals

### In Scope

✅ OperatorParser class with schema validation  
✅ Comparison operators: $eq, $ne, $gt, $gte, $lt, $lte  
✅ Type checking for operators (numeric/datetime only for range operators)  
✅ SQLAlchemy where clause generation  
✅ Error handling for invalid fields/operators  
✅ Unit tests (20+ tests)  
✅ Integration with existing row_search()

### Out of Scope

❌ Set operators ($in, $nin) - Sortie 2  
❌ Pattern matching ($like, $ilike) - Sortie 2  
❌ Existence operators ($exists, $null) - Sortie 2  
❌ Compound logic ($and, $or, $not) - Sortie 3  
❌ Update operators - Sortie 3  
❌ Aggregations - Sortie 4

---

## 3. Requirements

### Functional Requirements

**FR-1**: OperatorParser must:
- Accept table schema in constructor
- Parse simple equality filters (backward compatible)
- Parse operator-based filters: `{"score": {"$gte": 100}}`
- Generate valid SQLAlchemy where clauses
- Validate field names against schema
- Validate operator types against field types

**FR-2**: Comparison operators must support:
- $eq (equals): All field types
- $ne (not equals): All field types
- $gt (greater than): integer, float, datetime
- $gte (greater than or equal): integer, float, datetime
- $lt (less than): integer, float, datetime
- $lte (less than or equal): integer, float, datetime

**FR-3**: Type validation must:
- Reject range operators ($gt, $gte, $lt, $lte) on string/text/boolean fields
- Allow $eq/$ne on all field types
- Provide clear error messages

**FR-4**: Error handling must:
- Raise ValueError for unknown fields
- Raise ValueError for unknown operators
- Raise TypeError for type mismatches
- Include field name and operator in error messages

### Non-Functional Requirements

**NFR-1 Performance**: Operator parsing <1ms for typical filters

**NFR-2 Compatibility**: Works with Sprint 13's row_search()

**NFR-3 Testing**: ≥95% code coverage for OperatorParser

---

## 4. Technical Design

### 4.1 OperatorParser Class

**File**: `common/database/operator_parser.py` (new)

```python
"""
MongoDB-style query operator parser for row operations.

Converts filter dictionaries with operators like $gt, $lte into
SQLAlchemy where clauses.
"""

from typing import Any, Dict, List, Callable
from sqlalchemy import Column, and_
from datetime import datetime


class OperatorParser:
    """
    Parse MongoDB-style query operators into SQLAlchemy clauses.
    
    Supports comparison operators ($eq, $ne, $gt, $gte, $lt, $lte)
    with type validation based on table schema.
    """
    
    # Operator name -> SQLAlchemy method
    COMPARISON_OPS = {
        '$eq': lambda col, val: col == val,
        '$ne': lambda col, val: col != val,
        '$gt': lambda col, val: col > val,
        '$gte': lambda col, val: col >= val,
        '$lt': lambda col, val: col < val,
        '$lte': lambda col, val: col <= val,
    }
    
    # Operators that require numeric or datetime types
    RANGE_OPS = {'$gt', '$gte', '$lt', '$lte'}
    
    # Field types compatible with range operators
    RANGE_COMPATIBLE_TYPES = {'integer', 'float', 'datetime'}
    
    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize parser with table schema.
        
        Args:
            schema: Table schema dict with 'fields' key containing field definitions
        
        Example:
            schema = {
                'fields': [
                    {'name': 'score', 'type': 'integer', 'required': True},
                    {'name': 'username', 'type': 'string', 'required': True}
                ]
            }
        """
        self.schema = schema
        self.fields = {f['name']: f for f in schema['fields']}
        
        # Add auto-managed fields (from Sprint 13)
        self.fields['id'] = {'name': 'id', 'type': 'integer'}
        self.fields['created_at'] = {'name': 'created_at', 'type': 'datetime'}
        self.fields['updated_at'] = {'name': 'updated_at', 'type': 'datetime'}
    
    def parse_filters(self, filters: Dict[str, Any], table) -> List:
        """
        Parse filter dict into SQLAlchemy where clauses.
        
        Args:
            filters: MongoDB-style filter dict
            table: SQLAlchemy table object
        
        Returns:
            List of SQLAlchemy where clauses (can be combined with and_())
        
        Raises:
            ValueError: If field name invalid or operator unknown
            TypeError: If operator incompatible with field type
        
        Examples:
            # Simple equality
            filters = {'username': 'alice'}
            clauses = parser.parse_filters(filters, table)
            # Returns: [table.c.username == 'alice']
            
            # Operator-based
            filters = {'score': {'$gte': 100}}
            clauses = parser.parse_filters(filters, table)
            # Returns: [table.c.score >= 100]
            
            # Multiple operators on same field
            filters = {'score': {'$gte': 100, '$lte': 200}}
            clauses = parser.parse_filters(filters, table)
            # Returns: [table.c.score >= 100, table.c.score <= 200]
        """
        clauses = []
        
        for field_name, filter_value in filters.items():
            # Validate field exists
            if field_name not in self.fields:
                raise ValueError(
                    f"Field '{field_name}' not found in schema. "
                    f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                )
            
            field_def = self.fields[field_name]
            field_type = field_def['type']
            column = table.c[field_name]
            
            # Simple equality (backward compatible with Sprint 13)
            if not isinstance(filter_value, dict):
                clauses.append(column == filter_value)
                continue
            
            # Operator-based filters
            for operator, value in filter_value.items():
                clause = self._parse_operator(
                    field_name,
                    operator,
                    value,
                    field_type,
                    column
                )
                clauses.append(clause)
        
        return clauses
    
    def _parse_operator(
        self,
        field_name: str,
        operator: str,
        value: Any,
        field_type: str,
        column: Column
    ):
        """
        Parse single operator into SQLAlchemy clause.
        
        Args:
            field_name: Field name (for error messages)
            operator: Operator string (e.g., '$gte')
            value: Comparison value
            field_type: Field type from schema
            column: SQLAlchemy column object
        
        Returns:
            SQLAlchemy where clause
        
        Raises:
            ValueError: If operator unknown
            TypeError: If operator incompatible with field type
        """
        # Check operator exists
        if operator not in self.COMPARISON_OPS:
            raise ValueError(
                f"Unknown operator '{operator}' on field '{field_name}'. "
                f"Supported operators: {', '.join(sorted(self.COMPARISON_OPS.keys()))}"
            )
        
        # Type validation for range operators
        if operator in self.RANGE_OPS:
            if field_type not in self.RANGE_COMPATIBLE_TYPES:
                raise TypeError(
                    f"Range operator '{operator}' on field '{field_name}' requires "
                    f"numeric or datetime type, got '{field_type}'. "
                    f"Range operators can only be used with: "
                    f"{', '.join(sorted(self.RANGE_COMPATIBLE_TYPES))}"
                )
        
        # Generate clause
        op_func = self.COMPARISON_OPS[operator]
        return op_func(column, value)
    
    def validate_filter_dict(self, filters: Dict[str, Any]) -> None:
        """
        Validate filter dict without generating clauses.
        
        Useful for pre-validation before executing query.
        
        Args:
            filters: Filter dict to validate
        
        Raises:
            ValueError: If validation fails
            TypeError: If type mismatch
        """
        for field_name, filter_value in filters.items():
            # Check field exists
            if field_name not in self.fields:
                raise ValueError(f"Field '{field_name}' not found in schema")
            
            field_type = self.fields[field_name]['type']
            
            # Check operators
            if isinstance(filter_value, dict):
                for operator in filter_value.keys():
                    if operator not in self.COMPARISON_OPS:
                        raise ValueError(f"Unknown operator: {operator}")
                    
                    if operator in self.RANGE_OPS:
                        if field_type not in self.RANGE_COMPATIBLE_TYPES:
                            raise TypeError(
                                f"Cannot use {operator} on {field_type} field"
                            )
```

### 4.2 Integration with BotDatabase

**File**: `common/database.py` (modifications)

```python
from common.database.operator_parser import OperatorParser

class BotDatabase:
    # ... existing code ...
    
    async def row_search(
        self,
        plugin_name: str,
        table_name: str,
        filters: Optional[dict] = None,
        sort: Optional[dict] = None,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """
        Search rows with filters, sorting, and pagination.
        NOW SUPPORTS MONGODB-STYLE OPERATORS (Sprint 14).
        
        Args:
            plugin_name: Plugin identifier
            table_name: Table name (without plugin prefix)
            filters: Field filters - supports:
                - Simple equality: {'username': 'alice'}
                - Operators: {'score': {'$gte': 100, '$lte': 200}}
            sort: Sorting spec
            limit: Max rows to return (default 100, max 1000)
            offset: Pagination offset
        
        Returns:
            {
                "rows": [...],
                "count": int,
                "truncated": bool
            }
        """
        # Get schema and table
        schema = self.schema_registry.get_schema(plugin_name, table_name)
        if not schema:
            raise ValueError(
                f"Table '{table_name}' not registered for plugin '{plugin_name}'"
            )
        
        full_table_name = f"{plugin_name}_{table_name}"
        table = self.get_table(full_table_name)
        
        # Build SELECT statement
        stmt = select(table)
        
        # Apply filters using OperatorParser (NEW in Sprint 14)
        if filters:
            parser = OperatorParser(schema)
            clauses = parser.parse_filters(filters, table)
            
            # Combine all clauses with AND
            if clauses:
                stmt = stmt.where(and_(*clauses))
        
        # ... rest of method unchanged (sorting, pagination) ...
```

---

## 5. Implementation Steps

### Step 1: Create OperatorParser Module

1. Create directory: `common/database/`
2. Create `common/database/__init__.py`
3. Create `common/database/operator_parser.py`
4. Implement OperatorParser class with:
   - COMPARISON_OPS dict
   - RANGE_OPS set
   - RANGE_COMPATIBLE_TYPES set
   - `__init__()` method
   - `parse_filters()` method
   - `_parse_operator()` method
   - `validate_filter_dict()` method

### Step 2: Update BotDatabase

1. Import OperatorParser
2. Modify `row_search()` to use OperatorParser
3. Keep backward compatibility for simple filters

### Step 3: Create Unit Tests

**File**: `tests/unit/database/test_operator_parser.py` (new)

### Step 4: Integration Tests

Update `tests/integration/test_row_nats.py` with operator tests

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/unit/database/test_operator_parser.py`

```python
"""Unit tests for OperatorParser."""

import pytest
from common.database.operator_parser import OperatorParser
from sqlalchemy import Table, Column, Integer, String, DateTime, MetaData


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
    
    def test_simple_equality_filter(self, sample_schema, sample_table):
        """Test simple equality (backward compatible)."""
        parser = OperatorParser(sample_schema)
        
        filters = {'username': 'alice'}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
        # Clause should compile to: username = 'alice'


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
        
        from datetime import datetime
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
```

**Test Coverage Target**: 95%+

**Command**:
```bash
pytest tests/unit/database/test_operator_parser.py -v --cov=common.database.operator_parser --cov-report=term-missing
```

### 6.2 Integration Tests

**File**: `tests/integration/test_row_nats.py` (additions)

```python
class TestRowSearchWithOperators:
    """Test row search with MongoDB-style operators via NATS."""
    
    async def test_search_with_gte_operator(self, nats_client, db_service):
        """Test search with $gte operator."""
        # Register schema
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "scores",
                "schema": {
                    "fields": [{"name": "score", "type": "integer", "required": True}]
                }
            }).encode()
        )
        
        # Insert test data
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "scores",
                "data": [
                    {"score": 50},
                    {"score": 100},
                    {"score": 150},
                    {"score": 200}
                ]
            }).encode()
        )
        
        # Search with $gte
        resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "scores",
                "filters": {"score": {"$gte": 100}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(resp.data.decode())
        
        assert result['success'] == True
        assert result['count'] == 3
        assert all(row['score'] >= 100 for row in result['rows'])
    
    async def test_search_with_range_query(self, nats_client, db_service):
        """Test range query (between two values)."""
        # ... setup ...
        
        # Search: score >= 100 AND score <= 150
        resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "scores",
                "filters": {"score": {"$gte": 100, "$lte": 150}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(resp.data.decode())
        
        assert result['count'] == 2
        scores = [row['score'] for row in result['rows']]
        assert 100 in scores
        assert 150 in scores
        assert 50 not in scores
        assert 200 not in scores
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: OperatorParser class created
  - Given the module
  - When imported
  - Then OperatorParser class available

- [x] **AC-2**: All comparison operators work
  - Given filters with $eq, $ne, $gt, $gte, $lt, $lte
  - When parsing
  - Then correct SQLAlchemy clauses generated

- [x] **AC-3**: Type validation enforced
  - Given range operator on string field
  - When parsing
  - Then TypeError raised with clear message

- [x] **AC-4**: Backward compatibility maintained
  - Given simple equality filter: {'username': 'alice'}
  - When parsing
  - Then works as before

- [x] **AC-5**: Multiple operators on same field
  - Given {'score': {'$gte': 100, '$lte': 200}}
  - When parsing
  - Then generates two clauses

- [x] **AC-6**: Error messages are clear
  - Given unknown field or operator
  - When error raised
  - Then message includes available options

- [x] **AC-7**: Integration with row_search works
  - Given operator-based filters via NATS
  - When searching
  - Then correct results returned

- [x] **AC-8**: All unit tests pass (20+ tests, 95%+ coverage)

- [x] **AC-9**: All integration tests pass

---

## 8. Rollout Plan

### Pre-deployment

1. Review code changes
2. Run full test suite
3. Verify backward compatibility

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-14-sortie-1-operator-parser`
2. Create `common/database/` directory structure
3. Implement OperatorParser class
4. Update BotDatabase.row_search()
5. Write comprehensive unit tests
6. Write integration tests
7. Run tests and verify coverage
8. Commit with message:
   ```
   Sprint 14 Sortie 1: Operator Parser Foundation
   
   - Add OperatorParser class with comparison operators
   - Support $eq, $ne, $gt, $gte, $lt, $lte
   - Type validation for operators
   - Integration with row_search()
   - Comprehensive tests (20+ tests, 95%+ coverage)
   
   Implements: SPEC-Sortie-1-Operator-Parser-Foundation.md
   Related: PRD-Advanced-Query-Operators.md
   Depends-On: Sprint 13 (Row Operations Foundation)
   ```
9. Push branch and create PR
10. Code review
11. Merge to main

### Post-deployment

- Monitor query performance
- Check for type validation errors in logs
- Verify operator usage in plugin queries

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sprint 13**: row_search() must exist
- **SQLAlchemy 2.0+**: For clause generation

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Performance regression | Low | Medium | Benchmark comparison queries |
| Type validation too strict | Medium | Low | Allow explicit overrides if needed |
| Operator precedence issues | Low | Low | Document AND combination behavior |

---

## 10. Documentation

### Code Documentation

- All methods have comprehensive docstrings
- Operator list documented
- Type constraints documented
- Examples in docstrings

### Developer Documentation

Update `docs/guides/PLUGIN_ROW_STORAGE.md` with:
- Operator syntax examples
- Type compatibility table
- Range query examples

---

## 11. Related Specifications

**Previous**: Sprint 13 Complete  
**Next**: [SPEC-Sortie-2-Extended-Filter-Operators.md](SPEC-Sortie-2-Extended-Filter-Operators.md)

**Parent PRD**: [PRD-Advanced-Query-Operators.md](PRD-Advanced-Query-Operators.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
