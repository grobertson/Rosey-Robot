# SPEC: Sortie 3 - Update Operators & Compound Logic

**Sprint**: 14 (Advanced Query Operators)  
**Sortie**: 3 of 5  
**Estimated Effort**: ~6 hours  
**Branch**: `feature/sprint-14-sortie-3-update-compound`  
**Dependencies**: Sortie 1 (Operator Parser Foundation), Sortie 2 (Extended Filter Operators)

---

## 1. Overview

Add atomic update operators and compound logical filter operators to the OperatorParser. This sortie enables MongoDB-style update operations (e.g., `$inc`, `$set`, `$max`) that execute atomically at the database level, eliminating race conditions. It also adds compound filter logic (`$and`, `$or`, `$not`) for complex query compositions.

**What This Sortie Achieves**:
- Atomic update operators preventing race conditions
- Compound logical operators for complex filters
- Type-safe update operation validation
- Thread-safe increments/decrements
- Nested logical query support

---

## 2. Scope and Non-Goals

### In Scope
✅ Update operators: `$set`, `$inc`, `$dec`, `$mul`, `$max`, `$min`  
✅ Compound filter operators: `$and`, `$or`, `$not`  
✅ Type validation for update operators  
✅ Atomic execution at database level (SQLAlchemy expressions)  
✅ `parse_update_operations()` method returning SQLAlchemy column expressions  
✅ Extended `parse_filters()` to support compound logic  
✅ 20+ unit tests for update operators  
✅ 10+ unit tests for compound logic  
✅ Integration tests demonstrating atomic behavior

### Out of Scope
❌ Aggregation operators (Sortie 4)  
❌ Multi-field sorting (Sortie 4)  
❌ Performance benchmarks (Sortie 5)  
❌ Array operators (future sprint)  
❌ Transaction management (handled by caller)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Update operators must:
- Execute atomically at database level (no SELECT then UPDATE pattern)
- Support numeric operations: `$set`, `$inc`, `$dec`, `$mul`
- Support conditional operations: `$max`, `$min`
- Validate field types before generating SQL

**FR-2**: Compound logic operators must:
- Support `$and` (all conditions must match)
- Support `$or` (any condition must match)
- Support `$not` (negation of condition)
- Allow nested compound logic (e.g., `$and` containing `$or`)

**FR-3**: Type validation must:
- Reject numeric operators on non-numeric fields
- Reject `$max`/`$min` on incompatible types
- Provide clear error messages with field name and expected type

**FR-4**: `parse_update_operations()` must:
- Accept dict of `{field: {operator: value}}`
- Return dict of `{field: SQLAlchemy_expression}`
- Validate all fields exist in schema
- Support multiple operations in single call

### Non-Functional Requirements

**NFR-1 Atomicity**: Update operations execute as single SQL statement (no race conditions)  
**NFR-2 Performance**: Compound logic generates optimized SQL with proper AND/OR/NOT clauses  
**NFR-3 Type Safety**: Type validation prevents runtime SQL errors  
**NFR-4 Testing**: 85%+ coverage of new code, include concurrency tests

---

## 4. Technical Design

### 4.1 Update Operators

**File**: `common/database/operator_parser.py`

```python
from sqlalchemy import func

class OperatorParser:
    """
    Parse MongoDB-style query and update operators into SQLAlchemy expressions.
    
    Extended in Sortie 3 to support:
    - Atomic update operators ($set, $inc, $dec, $mul, $max, $min)
    - Compound logical operators ($and, $or, $not)
    """
    
    # Update operators (new in Sortie 3)
    UPDATE_OPS = {
        '$set': lambda col, val: val,  # Direct assignment
        '$inc': lambda col, val: col + val,  # Increment
        '$dec': lambda col, val: col - val,  # Decrement
        '$mul': lambda col, val: col * val,  # Multiply
        '$max': lambda col, val: func.greatest(col, val),  # Maximum
        '$min': lambda col, val: func.least(col, val),  # Minimum
    }
    
    # Numeric operators requiring numeric types
    NUMERIC_UPDATE_OPS = {'$inc', '$dec', '$mul'}
    
    # Conditional operators supporting numeric + datetime
    CONDITIONAL_UPDATE_OPS = {'$max', '$min'}
    
    # Numeric-compatible types
    NUMERIC_TYPES = {'INTEGER', 'BIGINT', 'FLOAT', 'REAL', 'NUMERIC', 'DECIMAL'}
    
    # Types supporting max/min operations
    COMPARABLE_TYPES = NUMERIC_TYPES | {'TIMESTAMP', 'DATE', 'DATETIME'}
    
    def parse_update_operations(
        self, 
        operations: Dict[str, Any], 
        table
    ) -> Dict[str, Any]:
        """
        Parse update operations dict into SQLAlchemy column expressions.
        
        Generates atomic update expressions that execute at database level,
        preventing race conditions in concurrent scenarios.
        
        Args:
            operations: Dict of {field: {operator: value}}
                Example: {
                    'score': {'$inc': 10},
                    'high_score': {'$max': 95},
                    'status': {'$set': 'active'}
                }
            table: SQLAlchemy Table object with schema
        
        Returns:
            Dict of {field: SQLAlchemy_expression} for use in update() statement
            Example: {
                'score': Column('score') + 10,
                'high_score': func.greatest(Column('high_score'), 95),
                'status': 'active'
            }
        
        Raises:
            ValueError: If field not in schema or operator unknown
            TypeError: If operator type incompatible with field type
        
        Example:
            >>> parser = OperatorParser(schema)
            >>> ops = {'score': {'$inc': 5}, 'status': {'$set': 'active'}}
            >>> updates = parser.parse_update_operations(ops, users_table)
            >>> stmt = update(users_table).values(**updates).where(...)
        """
        updates = {}
        
        for field_name, op_spec in operations.items():
            # Validate field exists
            if field_name not in self.fields:
                raise ValueError(
                    f"Field '{field_name}' not in schema. "
                    f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                )
            
            field_type = self.fields[field_name]['type']
            column = table.c[field_name]
            
            # Validate operation format
            if not isinstance(op_spec, dict):
                raise TypeError(
                    f"Update operations must be dict {{operator: value}}, "
                    f"got {type(op_spec).__name__} for field '{field_name}'"
                )
            
            if len(op_spec) != 1:
                raise ValueError(
                    f"Each field must have exactly one update operator, "
                    f"got {len(op_spec)} for field '{field_name}'"
                )
            
            operator, value = next(iter(op_spec.items()))
            
            # Validate operator exists
            if operator not in self.UPDATE_OPS:
                raise ValueError(
                    f"Unknown update operator: {operator}. "
                    f"Supported: {', '.join(sorted(self.UPDATE_OPS.keys()))}"
                )
            
            # Type validation
            if operator in self.NUMERIC_UPDATE_OPS:
                if field_type not in self.NUMERIC_TYPES:
                    raise TypeError(
                        f"Operator {operator} requires numeric type, "
                        f"but field '{field_name}' has type {field_type}"
                    )
                
                # Validate value is numeric
                if not isinstance(value, (int, float)):
                    raise TypeError(
                        f"Operator {operator} requires numeric value, "
                        f"got {type(value).__name__}"
                    )
            
            if operator in self.CONDITIONAL_UPDATE_OPS:
                if field_type not in self.COMPARABLE_TYPES:
                    raise TypeError(
                        f"Operator {operator} requires numeric or timestamp type, "
                        f"but field '{field_name}' has type {field_type}"
                    )
            
            # Generate SQLAlchemy expression
            updates[field_name] = self.UPDATE_OPS[operator](column, value)
        
        return updates
```

### 4.2 Compound Logic Operators

**File**: `common/database/operator_parser.py` (extension)

```python
from sqlalchemy import and_, or_, not_

class OperatorParser:
    """Extended with compound logic support."""
    
    # Logical operators (new in Sortie 3)
    LOGICAL_OPS = {'$and', '$or', '$not'}
    
    def parse_filters(
        self, 
        filters: Dict[str, Any], 
        table
    ) -> List:
        """
        Parse filter dict into list of SQLAlchemy clauses.
        
        Extended in Sortie 3 to support compound logical operators:
        - $and: All conditions must match
        - $or: Any condition must match
        - $not: Negation of condition
        
        Args:
            filters: Dict with field filters or logical operators
                Example: {
                    '$and': [
                        {'score': {'$gte': 100}},
                        {'$or': [
                            {'status': {'$eq': 'active'}},
                            {'status': {'$eq': 'pending'}}
                        ]}
                    ]
                }
            table: SQLAlchemy Table object
        
        Returns:
            List of SQLAlchemy clause objects
        
        Raises:
            ValueError: If invalid operator or field
            TypeError: If logical operator value not a list/dict
        
        Example:
            >>> parser = OperatorParser(schema)
            >>> filters = {
            ...     '$and': [
            ...         {'score': {'$gte': 100}},
            ...         {'status': {'$in': ['active', 'pending']}}
            ...     ]
            ... }
            >>> clauses = parser.parse_filters(filters, users_table)
            >>> stmt = select(users_table).where(and_(*clauses))
        """
        # Handle logical operators
        if '$and' in filters:
            conditions = filters['$and']
            if not isinstance(conditions, list):
                raise TypeError("$and operator requires a list of conditions")
            
            if not conditions:
                raise ValueError("$and operator requires at least one condition")
            
            # Recursively parse each condition
            clauses = [self.parse_filters(cond, table) for cond in conditions]
            # Flatten nested lists and combine with AND
            flat_clauses = [c for sublist in clauses for c in sublist]
            return [and_(*flat_clauses)]
        
        if '$or' in filters:
            conditions = filters['$or']
            if not isinstance(conditions, list):
                raise TypeError("$or operator requires a list of conditions")
            
            if not conditions:
                raise ValueError("$or operator requires at least one condition")
            
            # Recursively parse each condition
            clauses = [self.parse_filters(cond, table) for cond in conditions]
            # Flatten nested lists and combine with OR
            flat_clauses = [c for sublist in clauses for c in sublist]
            return [or_(*flat_clauses)]
        
        if '$not' in filters:
            condition = filters['$not']
            if not isinstance(condition, dict):
                raise TypeError("$not operator requires a dict condition")
            
            # Recursively parse the negated condition
            clauses = self.parse_filters(condition, table)
            # Combine clauses with AND then negate
            return [not_(and_(*clauses))]
        
        # Regular field filters (existing code from Sorties 1 & 2)
        clauses = []
        for field_name, filter_value in filters.items():
            if field_name.startswith('$'):
                raise ValueError(
                    f"Unknown logical operator: {field_name}. "
                    f"Supported: $and, $or, $not"
                )
            
            # Parse field operator (existing logic)
            field_clauses = self._parse_field_filter(field_name, filter_value, table)
            clauses.extend(field_clauses)
        
        return clauses
```

### 4.3 Integration with BotDatabase

**File**: `common/database.py` (extension)

```python
class BotDatabase:
    """Extended to support update operations."""
    
    async def row_update(
        self,
        table_name: str,
        filters: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> int:
        """
        Update rows atomically using update operators.
        
        Uses parse_update_operations() to generate atomic SQL expressions,
        preventing race conditions in concurrent scenarios.
        
        Args:
            table_name: Name of the table
            filters: MongoDB-style filter dict (supports compound logic)
            updates: MongoDB-style update operations dict
                Example: {
                    'score': {'$inc': 10},
                    'high_score': {'$max': 95},
                    'updated_at': {'$set': datetime.utcnow()}
                }
        
        Returns:
            Number of rows updated
        
        Raises:
            ValueError: If table/field invalid or operator unknown
            TypeError: If operator type incompatible
        
        Example:
            >>> # Atomic increment (no race condition)
            >>> count = await db.row_update(
            ...     'users',
            ...     {'username': {'$eq': 'alice'}},
            ...     {'score': {'$inc': 5}}
            ... )
        """
        table = self._get_table(table_name)
        parser = OperatorParser(self.row_schemas[table_name])
        
        # Parse filters (may include compound logic)
        where_clauses = parser.parse_filters(filters, table)
        
        # Parse update operations (generates atomic expressions)
        update_values = parser.parse_update_operations(updates, table)
        
        # Execute atomic update
        stmt = update(table).values(**update_values).where(and_(*where_clauses))
        
        async with self.async_session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
```

---

## 5. Implementation Steps

### Step 1: Add Update Operators to OperatorParser
1. Add `UPDATE_OPS` dict with all 6 operators
2. Add `NUMERIC_UPDATE_OPS` set for type checking
3. Add `CONDITIONAL_UPDATE_OPS` set
4. Add `NUMERIC_TYPES` and `COMPARABLE_TYPES` sets
5. Implement `parse_update_operations()` method
6. Add comprehensive type validation
7. Add clear error messages

### Step 2: Add Compound Logic to OperatorParser
1. Add `LOGICAL_OPS` set
2. Extend `parse_filters()` to detect logical operators
3. Implement `$and` handler with recursive parsing
4. Implement `$or` handler with recursive parsing
5. Implement `$not` handler with negation
6. Add validation for logical operator formats
7. Handle nested compound logic

### Step 3: Update BotDatabase
1. Add `row_update()` method (if not already added in Sprint 13)
2. Integrate `parse_update_operations()` call
3. Generate `update()` statement with atomic expressions
4. Add error handling for update operations

### Step 4: Write Unit Tests
**File**: `tests/unit/database/test_operator_parser.py` (extend)

Test categories:
- **Update Operators**: Each operator with valid inputs
- **Type Validation**: Reject invalid type combinations
- **Compound Logic**: AND, OR, NOT with simple filters
- **Nested Logic**: Complex nested combinations
- **Edge Cases**: Empty lists, invalid formats, unknown operators

### Step 5: Write Integration Tests
**File**: `tests/integration/test_atomic_updates.py`

Test categories:
- **Concurrency**: 100 concurrent `$inc` operations
- **Conditional Updates**: `$max` and `$min` behavior
- **Compound Filters**: Updates with complex WHERE clauses

---

## 6. Testing Strategy

### 6.1 Unit Tests - Update Operators

**File**: `tests/unit/database/test_operator_parser.py`

```python
import pytest
from common.database.operator_parser import OperatorParser
from sqlalchemy import Table, Column, Integer, String, MetaData

class TestUpdateOperators:
    """Test update operator parsing."""
    
    @pytest.fixture
    def schema(self):
        return {
            'id': {'type': 'INTEGER', 'nullable': False},
            'score': {'type': 'INTEGER', 'nullable': False},
            'multiplier': {'type': 'FLOAT', 'nullable': False},
            'high_score': {'type': 'INTEGER', 'nullable': True},
            'username': {'type': 'VARCHAR', 'nullable': False},
        }
    
    @pytest.fixture
    def table(self):
        metadata = MetaData()
        return Table(
            'users',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('score', Integer),
            Column('multiplier', Float),
            Column('high_score', Integer),
            Column('username', String),
        )
    
    def test_set_operator(self, schema, table):
        """Test $set operator for direct assignment."""
        parser = OperatorParser(schema)
        ops = {'username': {'$set': 'alice'}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'username' in updates
        assert updates['username'] == 'alice'
    
    def test_inc_operator(self, schema, table):
        """Test $inc operator for incrementing."""
        parser = OperatorParser(schema)
        ops = {'score': {'$inc': 10}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'score' in updates
        # Should be SQLAlchemy expression: Column('score') + 10
        assert str(updates['score']).startswith('users.score')
    
    def test_dec_operator(self, schema, table):
        """Test $dec operator for decrementing."""
        parser = OperatorParser(schema)
        ops = {'score': {'$dec': 5}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'score' in updates
        # Should be SQLAlchemy expression: Column('score') - 5
    
    def test_mul_operator(self, schema, table):
        """Test $mul operator for multiplication."""
        parser = OperatorParser(schema)
        ops = {'multiplier': {'$mul': 2.5}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'multiplier' in updates
    
    def test_max_operator(self, schema, table):
        """Test $max operator for maximum value."""
        parser = OperatorParser(schema)
        ops = {'high_score': {'$max': 100}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'high_score' in updates
        # Should use func.greatest()
    
    def test_min_operator(self, schema, table):
        """Test $min operator for minimum value."""
        parser = OperatorParser(schema)
        ops = {'score': {'$min': 50}}
        
        updates = parser.parse_update_operations(ops, table)
        
        assert 'score' in updates
        # Should use func.least()
    
    def test_multiple_update_operations(self, schema, table):
        """Test multiple update operations in one call."""
        parser = OperatorParser(schema)
        ops = {
            'score': {'$inc': 10},
            'high_score': {'$max': 95},
            'username': {'$set': 'bob'}
        }
        
        updates = parser.parse_update_operations(ops, table)
        
        assert len(updates) == 3
        assert 'score' in updates
        assert 'high_score' in updates
        assert 'username' in updates
    
    def test_invalid_field_name(self, schema, table):
        """Test error on invalid field name."""
        parser = OperatorParser(schema)
        ops = {'nonexistent': {'$inc': 1}}
        
        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_update_operations(ops, table)
    
    def test_unknown_operator(self, schema, table):
        """Test error on unknown update operator."""
        parser = OperatorParser(schema)
        ops = {'score': {'$invalid': 10}}
        
        with pytest.raises(ValueError, match="Unknown update operator"):
            parser.parse_update_operations(ops, table)
    
    def test_numeric_operator_on_string_field(self, schema, table):
        """Test error when using numeric operator on string field."""
        parser = OperatorParser(schema)
        ops = {'username': {'$inc': 1}}
        
        with pytest.raises(TypeError, match="requires numeric type"):
            parser.parse_update_operations(ops, table)
    
    def test_inc_with_non_numeric_value(self, schema, table):
        """Test error when $inc value is not numeric."""
        parser = OperatorParser(schema)
        ops = {'score': {'$inc': 'ten'}}
        
        with pytest.raises(TypeError, match="requires numeric value"):
            parser.parse_update_operations(ops, table)
    
    def test_invalid_operation_format(self, schema, table):
        """Test error when operation is not a dict."""
        parser = OperatorParser(schema)
        ops = {'score': 10}  # Should be {'$set': 10}
        
        with pytest.raises(TypeError, match="must be dict"):
            parser.parse_update_operations(ops, table)
    
    def test_multiple_operators_per_field(self, schema, table):
        """Test error when field has multiple operators."""
        parser = OperatorParser(schema)
        ops = {'score': {'$inc': 5, '$set': 100}}
        
        with pytest.raises(ValueError, match="exactly one update operator"):
            parser.parse_update_operations(ops, table)
```

### 6.2 Unit Tests - Compound Logic

```python
class TestCompoundLogic:
    """Test compound logical operators."""
    
    @pytest.fixture
    def schema(self):
        return {
            'id': {'type': 'INTEGER', 'nullable': False},
            'score': {'type': 'INTEGER', 'nullable': False},
            'status': {'type': 'VARCHAR', 'nullable': False},
            'active': {'type': 'BOOLEAN', 'nullable': False},
        }
    
    @pytest.fixture
    def table(self):
        metadata = MetaData()
        return Table(
            'users',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('score', Integer),
            Column('status', String),
            Column('active', Boolean),
        )
    
    def test_and_operator_simple(self, schema, table):
        """Test $and with simple conditions."""
        parser = OperatorParser(schema)
        filters = {
            '$and': [
                {'score': {'$gte': 100}},
                {'status': {'$eq': 'active'}}
            ]
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
        # Should contain AND clause
    
    def test_or_operator_simple(self, schema, table):
        """Test $or with simple conditions."""
        parser = OperatorParser(schema)
        filters = {
            '$or': [
                {'status': {'$eq': 'active'}},
                {'status': {'$eq': 'pending'}}
            ]
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
        # Should contain OR clause
    
    def test_not_operator_simple(self, schema, table):
        """Test $not with simple condition."""
        parser = OperatorParser(schema)
        filters = {
            '$not': {'score': {'$lt': 50}}
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
        # Should contain NOT clause
    
    def test_nested_and_or(self, schema, table):
        """Test nested $and containing $or."""
        parser = OperatorParser(schema)
        filters = {
            '$and': [
                {'score': {'$gte': 100}},
                {
                    '$or': [
                        {'status': {'$eq': 'active'}},
                        {'status': {'$eq': 'pending'}}
                    ]
                }
            ]
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
        # Should contain nested AND(score>=100, OR(status=active, status=pending))
    
    def test_nested_or_and(self, schema, table):
        """Test nested $or containing $and."""
        parser = OperatorParser(schema)
        filters = {
            '$or': [
                {
                    '$and': [
                        {'score': {'$gte': 100}},
                        {'active': {'$eq': True}}
                    ]
                },
                {'status': {'$eq': 'admin'}}
            ]
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
    
    def test_not_with_compound_condition(self, schema, table):
        """Test $not with compound condition."""
        parser = OperatorParser(schema)
        filters = {
            '$not': {
                '$and': [
                    {'score': {'$lt': 50}},
                    {'active': {'$eq': False}}
                ]
            }
        }
        
        clauses = parser.parse_filters(filters, table)
        
        assert len(clauses) == 1
    
    def test_and_empty_list(self, schema, table):
        """Test error on empty $and list."""
        parser = OperatorParser(schema)
        filters = {'$and': []}
        
        with pytest.raises(ValueError, match="at least one condition"):
            parser.parse_filters(filters, table)
    
    def test_or_not_list(self, schema, table):
        """Test error when $or value is not a list."""
        parser = OperatorParser(schema)
        filters = {'$or': {'score': {'$gte': 100}}}
        
        with pytest.raises(TypeError, match="requires a list"):
            parser.parse_filters(filters, table)
    
    def test_not_not_dict(self, schema, table):
        """Test error when $not value is not a dict."""
        parser = OperatorParser(schema)
        filters = {'$not': ['score', '>', 100]}
        
        with pytest.raises(TypeError, match="requires a dict"):
            parser.parse_filters(filters, table)
    
    def test_unknown_logical_operator(self, schema, table):
        """Test error on unknown logical operator."""
        parser = OperatorParser(schema)
        filters = {'$xor': [{'score': {'$gte': 100}}]}
        
        with pytest.raises(ValueError, match="Unknown logical operator"):
            parser.parse_filters(filters, table)
```

### 6.3 Integration Tests - Atomic Updates

**File**: `tests/integration/test_atomic_updates.py`

```python
import pytest
import asyncio
from common.database import BotDatabase

@pytest.mark.asyncio
class TestAtomicUpdates:
    """Test atomic update behavior preventing race conditions."""
    
    async def test_concurrent_increments(self, db: BotDatabase):
        """Test 100 concurrent $inc operations yield correct total."""
        # Setup: Create user with score=0
        await db.row_create('users', {'username': 'alice', 'score': 0})
        
        # Execute 100 concurrent increments
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
        await db.row_create('users', {'username': 'bob', 'high_score': 50})
        
        # Try to set lower value (should not update)
        count = await db.row_update(
            'users',
            {'username': {'$eq': 'bob'}},
            {'high_score': {'$max': 30}}
        )
        assert count == 1
        
        rows = await db.row_search('users', {'username': {'$eq': 'bob'}})
        assert rows[0]['high_score'] == 50  # Unchanged
        
        # Set higher value (should update)
        await db.row_update(
            'users',
            {'username': {'$eq': 'bob'}},
            {'high_score': {'$max': 75}}
        )
        
        rows = await db.row_search('users', {'username': {'$eq': 'bob'}})
        assert rows[0]['high_score'] == 75  # Updated
    
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
```

**Test Coverage Target**: 85%+ of new code

**Command**:
```bash
pytest tests/unit/database/test_operator_parser.py::TestUpdateOperators -v
pytest tests/unit/database/test_operator_parser.py::TestCompoundLogic -v
pytest tests/integration/test_atomic_updates.py -v --cov=common.database
```

---

## 7. Acceptance Criteria

- [ ] **AC-1**: All 6 update operators implemented
  - Given OperatorParser with schema
  - When calling parse_update_operations() with $set, $inc, $dec, $mul, $max, $min
  - Then correct SQLAlchemy expressions returned

- [ ] **AC-2**: Type validation prevents invalid operations
  - Given numeric operator ($inc, $dec, $mul)
  - When applied to non-numeric field
  - Then TypeError raised with clear message

- [ ] **AC-3**: Atomic updates prevent race conditions
  - Given 100 concurrent $inc operations on same row
  - When all operations complete
  - Then final value equals exactly 100 increments (no lost updates)

- [ ] **AC-4**: $and operator works correctly
  - Given $and with multiple conditions
  - When parsed into SQLAlchemy
  - Then generates proper AND clause combining all conditions

- [ ] **AC-5**: $or operator works correctly
  - Given $or with multiple conditions
  - When parsed into SQLAlchemy
  - Then generates proper OR clause combining all conditions

- [ ] **AC-6**: $not operator works correctly
  - Given $not with condition
  - When parsed into SQLAlchemy
  - Then generates proper NOT clause negating condition

- [ ] **AC-7**: Nested compound logic supported
  - Given $and containing $or containing field filters
  - When parsed
  - Then generates correct nested SQL logic

- [ ] **AC-8**: $max and $min work conditionally
  - Given $max operator with value
  - When current value is higher
  - Then value unchanged (SQL func.greatest() behavior)

- [ ] **AC-9**: Multiple update operations supported
  - Given dict with 3 different fields and operators
  - When parsed
  - Then returns dict with 3 SQLAlchemy expressions

- [ ] **AC-10**: All unit tests pass with 85%+ coverage
  - Given 30+ new unit tests
  - When running pytest
  - Then all tests pass, coverage ≥85%

---

## 8. Rollout Plan

### Pre-deployment
1. Review code changes in OperatorParser
2. Run full test suite including new tests
3. Verify atomic behavior in integration tests
4. Test compound logic with complex nested queries

### Deployment Steps
1. Create feature branch: `git checkout -b feature/sprint-14-sortie-3-update-compound`
2. Implement update operators in `operator_parser.py`
3. Extend `parse_filters()` with compound logic support
4. Update `BotDatabase.row_update()` to use new parser
5. Write comprehensive unit tests (30+ tests)
6. Write integration tests for atomicity
7. Run tests and verify coverage
8. Commit changes with message:
   ```
   Sprint 14 Sortie 3: Update Operators & Compound Logic
   
   - Add atomic update operators ($set, $inc, $dec, $mul, $max, $min)
   - Add compound logical operators ($and, $or, $not)
   - Implement parse_update_operations() method
   - Extend parse_filters() with compound logic support
   - Add comprehensive type validation
   - Add 30+ unit tests and integration tests
   - Verify atomic behavior with concurrency tests
   
   Implements: SPEC-Sortie-3-Update-Operators-Compound-Logic.md
   Related: PRD-Advanced-Query-Operators.md
   ```
9. Push branch and create PR
10. Code review
11. Merge to main

### Post-deployment
- Monitor NATS handler performance with compound queries
- Verify no race conditions in production concurrent updates
- Check query performance with complex nested logic

### Rollback Procedure
If issues arise:
```bash
git revert <commit-hash>
# Update operators are additive, no schema changes
# Safe to rollback without data migration
```

---

## 9. Dependencies & Risks

### Dependencies
- **Sortie 1**: OperatorParser foundation with comparison operators
- **Sortie 2**: Extended filter operators (set, pattern, existence)
- **Sprint 13**: BotDatabase with row_update() method
- **SQLAlchemy 2.0+**: func.greatest(), func.least(), and_(), or_(), not_()

### External Dependencies
None - all functionality within SQLAlchemy

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Race conditions with $inc | Low | High | Use SQLAlchemy column expressions (atomic at DB level) |
| Complex nested logic generates inefficient SQL | Medium | Medium | Test EXPLAIN plans, optimize if needed |
| Type validation too strict | Low | Medium | Allow numeric types on $max/$min with datetime |
| func.greatest/least not supported on SQLite | Low | Medium | Test on both SQLite and PostgreSQL |
| Recursive parsing causes stack overflow | Low | Low | Limit nesting depth if issues arise |

---

## 10. Documentation

### Code Documentation
- Docstrings for `parse_update_operations()` with examples
- Docstrings for extended `parse_filters()` explaining compound logic
- Comments explaining atomic update behavior
- Type hints for all method parameters

### User Documentation
Updates needed in **docs/guides/DATABASE_QUERIES.md**:
- Update operators section with examples
- Compound logic section with nested query examples
- Atomicity guarantees explanation
- Migration guide from SELECT+UPDATE to $inc pattern

### Developer Documentation
Update **docs/DATABASE.md** with:
- Update operator reference table
- Compound logic operator reference
- Atomic operation patterns
- Performance considerations for nested logic

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-Operator-Parser-Foundation.md](SPEC-Sortie-1-Operator-Parser-Foundation.md)
- [SPEC-Sortie-2-Extended-Filter-Operators.md](SPEC-Sortie-2-Extended-Filter-Operators.md)

**Next**: 
- [SPEC-Sortie-4-Aggregations-Multi-Field-Sorting.md](SPEC-Sortie-4-Aggregations-Multi-Field-Sorting.md)
- [SPEC-Sortie-5-Integration-Docs-Performance-Tests.md](SPEC-Sortie-5-Integration-Docs-Performance-Tests.md)

**Parent PRD**: [PRD-Advanced-Query-Operators.md](PRD-Advanced-Query-Operators.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
