# SPEC: Sortie 4 - Aggregations & Multi-Field Sorting

**Sprint**: 14 (Advanced Query Operators)  
**Sortie**: 4 of 5  
**Estimated Effort**: ~5 hours  
**Branch**: `feature/sprint-14-sortie-4-aggregations-sorting`  
**Dependencies**: Sortie 1 (Operator Parser), Sortie 2 (Extended Filters), Sortie 3 (Update Ops)

---

## 1. Overview

Add aggregation functions and multi-field sorting support to the query system. This sortie enables SQL aggregate operations (COUNT, SUM, AVG, MIN, MAX) and priority-based multi-field sorting, completing the advanced query operator feature set.

**What This Sortie Achieves**:
- Five aggregation functions: COUNT, SUM, AVG, MIN, MAX
- Multi-field sorting with priority order
- Aggregations with filter constraints
- Backward compatibility with single-field sort
- Type validation for aggregate operations

---

## 2. Scope and Non-Goals

### In Scope
✅ Aggregation functions: COUNT, SUM, AVG, MIN, MAX  
✅ `parse_aggregations()` method in OperatorParser  
✅ Multi-field sorting with priority order  
✅ `parse_sort()` method supporting list of sort specs  
✅ Backward compatibility with single-field sort dict  
✅ Aggregations with WHERE clause filters  
✅ Type validation for aggregate fields  
✅ 15+ unit tests for aggregations  
✅ 10+ unit tests for multi-field sorting  
✅ Integration tests combining filters, aggregations, sorting

### Out of Scope
❌ GROUP BY operations (future sprint)  
❌ HAVING clause (future sprint)  
❌ Window functions (future sprint)  
❌ DISTINCT aggregations (future sprint)  
❌ Performance benchmarks (Sortie 5)  
❌ User documentation (Sortie 5)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Aggregation functions must:
- Support COUNT (total rows matching filter)
- Support SUM, AVG, MIN, MAX on numeric fields
- Allow custom result names (aliases)
- Respect WHERE clause filters
- Validate field types (numeric for SUM/AVG)

**FR-2**: Multi-field sorting must:
- Accept list of sort specifications
- Apply sorts in priority order (first sort = primary, etc.)
- Support ascending and descending order per field
- Maintain backward compatibility with single-field dict
- Validate all sort fields exist in schema

**FR-3**: Integration with BotDatabase must:
- Extend `row_search()` to accept `aggregates` parameter
- Extend `row_search()` to accept multi-field `sort` parameter
- Return aggregation results as dict with custom names
- Work seamlessly with existing filters and operators

**FR-4**: Type validation must:
- Reject SUM/AVG on non-numeric fields
- Allow MIN/MAX on numeric, datetime, and text fields
- Allow COUNT on any field or without field (COUNT(*))
- Provide clear error messages

### Non-Functional Requirements

**NFR-1 Performance**: Aggregations execute as single SQL query (no post-processing)  
**NFR-2 Compatibility**: Works on SQLite and PostgreSQL  
**NFR-3 Type Safety**: Type hints for all methods  
**NFR-4 Testing**: 85%+ coverage of new code

---

## 4. Technical Design

### 4.1 Aggregation Functions

**File**: `common/database/operator_parser.py`

```python
from sqlalchemy import func

class OperatorParser:
    """Extended with aggregation support in Sortie 4."""
    
    # Aggregation functions
    AGGREGATION_FUNCS = {
        '$count': func.count,
        '$sum': func.sum,
        '$avg': func.avg,
        '$min': func.min,
        '$max': func.max,
    }
    
    # Functions requiring numeric types
    NUMERIC_AGGREGATIONS = {'$sum', '$avg'}
    
    # Functions supporting various types
    COMPARABLE_AGGREGATIONS = {'$min', '$max'}  # Numeric, datetime, text
    
    def parse_aggregations(
        self, 
        aggregates: Dict[str, Dict[str, str]], 
        table
    ) -> List:
        """
        Parse aggregation specifications into SQLAlchemy aggregate expressions.
        
        Args:
            aggregates: Dict of {result_name: {function: field}}
                Example: {
                    'total_count': {'$count': '*'},
                    'total_score': {'$sum': 'score'},
                    'avg_score': {'$avg': 'score'},
                    'max_score': {'$max': 'score'}
                }
            table: SQLAlchemy Table object
        
        Returns:
            List of SQLAlchemy aggregate expressions with labels
            Example: [
                func.count().label('total_count'),
                func.sum(Column('score')).label('total_score'),
                func.avg(Column('score')).label('avg_score'),
                func.max(Column('score')).label('max_score')
            ]
        
        Raises:
            ValueError: If function unknown, field invalid, or spec malformed
            TypeError: If function incompatible with field type
        
        Example:
            >>> parser = OperatorParser(schema)
            >>> aggs = {
            ...     'total': {'$count': '*'},
            ...     'avg_score': {'$avg': 'score'}
            ... }
            >>> agg_exprs = parser.parse_aggregations(aggs, users_table)
            >>> stmt = select(*agg_exprs).where(...)
        """
        agg_exprs = []
        
        for result_name, agg_spec in aggregates.items():
            # Validate result name
            if not result_name or not isinstance(result_name, str):
                raise ValueError("Aggregation result name must be a non-empty string")
            
            # Validate spec format
            if not isinstance(agg_spec, dict):
                raise TypeError(
                    f"Aggregation spec must be dict {{function: field}}, "
                    f"got {type(agg_spec).__name__} for '{result_name}'"
                )
            
            if len(agg_spec) != 1:
                raise ValueError(
                    f"Aggregation spec must have exactly one function, "
                    f"got {len(agg_spec)} for '{result_name}'"
                )
            
            func_name, field = next(iter(agg_spec.items()))
            
            # Validate function exists
            if func_name not in self.AGGREGATION_FUNCS:
                raise ValueError(
                    f"Unknown aggregation function: {func_name}. "
                    f"Supported: {', '.join(sorted(self.AGGREGATION_FUNCS.keys()))}"
                )
            
            # Handle COUNT special case (can be COUNT(*) or COUNT(field))
            if func_name == '$count':
                if field == '*':
                    agg_exprs.append(func.count().label(result_name))
                else:
                    if field not in self.fields:
                        raise ValueError(
                            f"Field '{field}' not in schema. "
                            f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                        )
                    agg_exprs.append(func.count(table.c[field]).label(result_name))
                continue
            
            # Other aggregations require valid field
            if field not in self.fields:
                raise ValueError(
                    f"Field '{field}' not in schema. "
                    f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                )
            
            field_type = self.fields[field]['type']
            column = table.c[field]
            
            # Type validation for numeric aggregations
            if func_name in self.NUMERIC_AGGREGATIONS:
                if field_type not in self.NUMERIC_TYPES:
                    raise TypeError(
                        f"Aggregation {func_name} requires numeric field, "
                        f"but field '{field}' has type {field_type}"
                    )
            
            # MIN/MAX support numeric, datetime, text
            if func_name in self.COMPARABLE_AGGREGATIONS:
                comparable_types = self.NUMERIC_TYPES | {'TIMESTAMP', 'DATE', 'DATETIME', 'VARCHAR', 'TEXT'}
                if field_type not in comparable_types:
                    raise TypeError(
                        f"Aggregation {func_name} requires numeric, datetime, or text field, "
                        f"but field '{field}' has type {field_type}"
                    )
            
            # Generate aggregate expression
            agg_func = self.AGGREGATION_FUNCS[func_name]
            agg_exprs.append(agg_func(column).label(result_name))
        
        return agg_exprs
```

### 4.2 Multi-Field Sorting

**File**: `common/database/operator_parser.py` (extension)

```python
class OperatorParser:
    """Extended with multi-field sorting support."""
    
    def parse_sort(
        self, 
        sort_spec: Union[Dict[str, str], List[Dict[str, str]]], 
        table
    ) -> List:
        """
        Parse sort specification into SQLAlchemy order_by clauses.
        
        Supports both single-field (dict) and multi-field (list) sorting.
        Multi-field sorts are applied in priority order (first = primary sort).
        
        Args:
            sort_spec: Single dict or list of dicts with format:
                {'field': 'field_name', 'order': 'asc'|'desc'}
                
                Single-field example:
                {'field': 'score', 'order': 'desc'}
                
                Multi-field example:
                [
                    {'field': 'status', 'order': 'asc'},
                    {'field': 'score', 'order': 'desc'},
                    {'field': 'username', 'order': 'asc'}
                ]
            
            table: SQLAlchemy Table object
        
        Returns:
            List of SQLAlchemy order_by clauses in priority order
        
        Raises:
            ValueError: If field not in schema or order invalid
            TypeError: If sort_spec format invalid
        
        Example:
            >>> parser = OperatorParser(schema)
            >>> # Multi-field sort: status ASC, then score DESC
            >>> sort = [
            ...     {'field': 'status', 'order': 'asc'},
            ...     {'field': 'score', 'order': 'desc'}
            ... ]
            >>> order_clauses = parser.parse_sort(sort, users_table)
            >>> stmt = select(users_table).order_by(*order_clauses)
        """
        # Backward compatibility: convert single dict to list
        if isinstance(sort_spec, dict):
            sort_spec = [sort_spec]
        
        if not isinstance(sort_spec, list):
            raise TypeError(
                f"Sort spec must be dict or list of dicts, "
                f"got {type(sort_spec).__name__}"
            )
        
        if not sort_spec:
            raise ValueError("Sort spec list cannot be empty")
        
        order_clauses = []
        
        for i, sort_item in enumerate(sort_spec):
            if not isinstance(sort_item, dict):
                raise TypeError(
                    f"Sort item {i} must be dict, got {type(sort_item).__name__}"
                )
            
            # Validate required 'field' key
            if 'field' not in sort_item:
                raise ValueError(f"Sort item {i} missing required 'field' key")
            
            field = sort_item['field']
            order = sort_item.get('order', 'asc').lower()
            
            # Validate field exists
            if field not in self.fields:
                raise ValueError(
                    f"Sort field '{field}' not in schema. "
                    f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                )
            
            # Validate order
            if order not in ('asc', 'desc'):
                raise ValueError(
                    f"Sort order must be 'asc' or 'desc', got '{order}' "
                    f"for field '{field}'"
                )
            
            # Generate order clause
            column = table.c[field]
            if order == 'desc':
                order_clauses.append(column.desc())
            else:
                order_clauses.append(column.asc())
        
        return order_clauses
```

### 4.3 Integration with BotDatabase

**File**: `common/database.py` (extension)

```python
class BotDatabase:
    """Extended to support aggregations and multi-field sorting."""
    
    async def row_search(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[Union[Dict[str, str], List[Dict[str, str]]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        aggregates: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search rows with optional filtering, sorting, and aggregation.
        
        Extended in Sortie 4 to support:
        - Aggregation functions (COUNT, SUM, AVG, MIN, MAX)
        - Multi-field sorting with priority order
        
        Args:
            table_name: Name of the table
            filters: MongoDB-style filter dict (supports all operators from Sorties 1-3)
            sort: Sort specification (single dict or list for multi-field)
            limit: Maximum number of rows to return
            offset: Number of rows to skip
            aggregates: Aggregation specifications
                Example: {
                    'total': {'$count': '*'},
                    'avg_score': {'$avg': 'score'}
                }
        
        Returns:
            If aggregates provided: Dict with aggregation results
            Otherwise: List of row dicts
        
        Example:
            >>> # Regular search with multi-field sort
            >>> rows = await db.row_search(
            ...     'users',
            ...     filters={'status': {'$eq': 'active'}},
            ...     sort=[
            ...         {'field': 'score', 'order': 'desc'},
            ...         {'field': 'username', 'order': 'asc'}
            ...     ],
            ...     limit=10
            ... )
            
            >>> # Aggregation query
            >>> result = await db.row_search(
            ...     'users',
            ...     filters={'status': {'$eq': 'active'}},
            ...     aggregates={
            ...         'total': {'$count': '*'},
            ...         'avg_score': {'$avg': 'score'},
            ...         'max_score': {'$max': 'score'}
            ...     }
            ... )
            >>> # Returns: {'total': 150, 'avg_score': 87.5, 'max_score': 100}
        """
        table = self._get_table(table_name)
        parser = OperatorParser(self.row_schemas[table_name])
        
        # Aggregation query
        if aggregates:
            agg_exprs = parser.parse_aggregations(aggregates, table)
            stmt = select(*agg_exprs)
            
            # Apply filters if provided
            if filters:
                where_clauses = parser.parse_filters(filters, table)
                stmt = stmt.where(and_(*where_clauses))
            
            async with self.async_session() as session:
                result = await session.execute(stmt)
                row = result.fetchone()
                
                # Convert to dict with custom names
                return dict(zip([agg.name for agg in agg_exprs], row))
        
        # Regular query (existing code with sort extension)
        stmt = select(table)
        
        # Apply filters
        if filters:
            where_clauses = parser.parse_filters(filters, table)
            stmt = stmt.where(and_(*where_clauses))
        
        # Apply sorting (now supports multi-field)
        if sort:
            order_clauses = parser.parse_sort(sort, table)
            stmt = stmt.order_by(*order_clauses)
        
        # Apply pagination
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        
        async with self.async_session() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
            
            return [dict(row._mapping) for row in rows]
```

---

## 5. Implementation Steps

### Step 1: Add Aggregation Support to OperatorParser
1. Add `AGGREGATION_FUNCS` dict mapping function names to SQLAlchemy funcs
2. Add `NUMERIC_AGGREGATIONS` and `COMPARABLE_AGGREGATIONS` sets
3. Implement `parse_aggregations()` method
4. Add type validation for each function
5. Handle COUNT(*) special case
6. Add comprehensive error messages

### Step 2: Add Multi-Field Sorting to OperatorParser
1. Implement `parse_sort()` method
2. Support both dict (single-field) and list (multi-field) input
3. Validate field existence and order values
4. Generate SQLAlchemy order_by clauses in priority order
5. Maintain backward compatibility with existing single-field sort

### Step 3: Extend BotDatabase.row_search()
1. Add `aggregates` parameter to method signature
2. Branch logic: aggregations vs regular query
3. For aggregations:
   - Call `parse_aggregations()`
   - Build SELECT with aggregate expressions
   - Apply filters if provided
   - Return dict with custom result names
4. For regular queries:
   - Update sort handling to use `parse_sort()`
   - Support multi-field sort lists

### Step 4: Write Unit Tests
**File**: `tests/unit/database/test_operator_parser.py` (extend)

Test categories:
- **Aggregations**: Each function (COUNT, SUM, AVG, MIN, MAX)
- **Type Validation**: Reject invalid type combinations
- **Multi-Field Sort**: Priority order, mixed asc/desc
- **Backward Compatibility**: Single-field sort dict still works
- **Edge Cases**: Empty specs, invalid fields, malformed input

### Step 5: Write Integration Tests
**File**: `tests/integration/test_aggregations_sorting.py`

Test categories:
- **Aggregations with Filters**: COUNT, SUM, AVG respecting WHERE clause
- **Multi-Field Sort**: 3-field sort with real data
- **Combined Query**: Filters + sorts together

---

## 6. Testing Strategy

### 6.1 Unit Tests - Aggregations

**File**: `tests/unit/database/test_operator_parser.py`

```python
import pytest
from common.database.operator_parser import OperatorParser
from sqlalchemy import Table, Column, Integer, String, Float, MetaData

class TestAggregations:
    """Test aggregation function parsing."""
    
    @pytest.fixture
    def schema(self):
        return {
            'id': {'type': 'INTEGER', 'nullable': False},
            'username': {'type': 'VARCHAR', 'nullable': False},
            'score': {'type': 'INTEGER', 'nullable': False},
            'rating': {'type': 'FLOAT', 'nullable': False},
            'status': {'type': 'VARCHAR', 'nullable': False},
        }
    
    @pytest.fixture
    def table(self):
        metadata = MetaData()
        return Table(
            'users',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('username', String),
            Column('score', Integer),
            Column('rating', Float),
            Column('status', String),
        )
    
    def test_count_all(self, schema, table):
        """Test COUNT(*) aggregation."""
        parser = OperatorParser(schema)
        aggs = {'total': {'$count': '*'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'total'
        # Should use func.count()
    
    def test_count_field(self, schema, table):
        """Test COUNT(field) aggregation."""
        parser = OperatorParser(schema)
        aggs = {'user_count': {'$count': 'username'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'user_count'
    
    def test_sum_aggregation(self, schema, table):
        """Test SUM aggregation."""
        parser = OperatorParser(schema)
        aggs = {'total_score': {'$sum': 'score'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'total_score'
        # Should use func.sum()
    
    def test_avg_aggregation(self, schema, table):
        """Test AVG aggregation."""
        parser = OperatorParser(schema)
        aggs = {'avg_rating': {'$avg': 'rating'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'avg_rating'
    
    def test_min_aggregation(self, schema, table):
        """Test MIN aggregation."""
        parser = OperatorParser(schema)
        aggs = {'min_score': {'$min': 'score'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'min_score'
    
    def test_max_aggregation(self, schema, table):
        """Test MAX aggregation."""
        parser = OperatorParser(schema)
        aggs = {'max_score': {'$max': 'score'}}
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 1
        assert exprs[0].name == 'max_score'
    
    def test_multiple_aggregations(self, schema, table):
        """Test multiple aggregations in one query."""
        parser = OperatorParser(schema)
        aggs = {
            'total': {'$count': '*'},
            'total_score': {'$sum': 'score'},
            'avg_score': {'$avg': 'score'},
            'min_score': {'$min': 'score'},
            'max_score': {'$max': 'score'},
        }
        
        exprs = parser.parse_aggregations(aggs, table)
        
        assert len(exprs) == 5
        names = [expr.name for expr in exprs]
        assert 'total' in names
        assert 'avg_score' in names
    
    def test_sum_on_non_numeric_field(self, schema, table):
        """Test error when SUM applied to non-numeric field."""
        parser = OperatorParser(schema)
        aggs = {'total': {'$sum': 'username'}}
        
        with pytest.raises(TypeError, match="requires numeric field"):
            parser.parse_aggregations(aggs, table)
    
    def test_avg_on_string_field(self, schema, table):
        """Test error when AVG applied to string field."""
        parser = OperatorParser(schema)
        aggs = {'avg_status': {'$avg': 'status'}}
        
        with pytest.raises(TypeError, match="requires numeric field"):
            parser.parse_aggregations(aggs, table)
    
    def test_unknown_function(self, schema, table):
        """Test error on unknown aggregation function."""
        parser = OperatorParser(schema)
        aggs = {'result': {'$median': 'score'}}
        
        with pytest.raises(ValueError, match="Unknown aggregation function"):
            parser.parse_aggregations(aggs, table)
    
    def test_invalid_field_name(self, schema, table):
        """Test error on invalid field name."""
        parser = OperatorParser(schema)
        aggs = {'total': {'$sum': 'nonexistent'}}
        
        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_aggregations(aggs, table)
    
    def test_malformed_spec_not_dict(self, schema, table):
        """Test error when spec is not a dict."""
        parser = OperatorParser(schema)
        aggs = {'total': '$count'}  # Should be {'$count': '*'}
        
        with pytest.raises(TypeError, match="must be dict"):
            parser.parse_aggregations(aggs, table)
    
    def test_malformed_spec_multiple_functions(self, schema, table):
        """Test error when spec has multiple functions."""
        parser = OperatorParser(schema)
        aggs = {'result': {'$sum': 'score', '$avg': 'score'}}
        
        with pytest.raises(ValueError, match="exactly one function"):
            parser.parse_aggregations(aggs, table)
    
    def test_empty_result_name(self, schema, table):
        """Test error on empty result name."""
        parser = OperatorParser(schema)
        aggs = {'': {'$count': '*'}}
        
        with pytest.raises(ValueError, match="non-empty string"):
            parser.parse_aggregations(aggs, table)
```

### 6.2 Unit Tests - Multi-Field Sorting

```python
class TestMultiFieldSorting:
    """Test multi-field sorting."""
    
    @pytest.fixture
    def schema(self):
        return {
            'id': {'type': 'INTEGER', 'nullable': False},
            'username': {'type': 'VARCHAR', 'nullable': False},
            'score': {'type': 'INTEGER', 'nullable': False},
            'status': {'type': 'VARCHAR', 'nullable': False},
        }
    
    @pytest.fixture
    def table(self):
        metadata = MetaData()
        return Table(
            'users',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('username', String),
            Column('score', Integer),
            Column('status', String),
        )
    
    def test_single_field_dict(self, schema, table):
        """Test backward compatible single-field sort dict."""
        parser = OperatorParser(schema)
        sort = {'field': 'score', 'order': 'desc'}
        
        clauses = parser.parse_sort(sort, table)
        
        assert len(clauses) == 1
        # Should be score DESC
    
    def test_single_field_list(self, schema, table):
        """Test single-field sort as list."""
        parser = OperatorParser(schema)
        sort = [{'field': 'username', 'order': 'asc'}]
        
        clauses = parser.parse_sort(sort, table)
        
        assert len(clauses) == 1
    
    def test_multi_field_two_sorts(self, schema, table):
        """Test two-field sort."""
        parser = OperatorParser(schema)
        sort = [
            {'field': 'status', 'order': 'asc'},
            {'field': 'score', 'order': 'desc'}
        ]
        
        clauses = parser.parse_sort(sort, table)
        
        assert len(clauses) == 2
        # First clause should be status ASC
        # Second clause should be score DESC
    
    def test_multi_field_three_sorts(self, schema, table):
        """Test three-field sort with priority order."""
        parser = OperatorParser(schema)
        sort = [
            {'field': 'status', 'order': 'asc'},
            {'field': 'score', 'order': 'desc'},
            {'field': 'username', 'order': 'asc'}
        ]
        
        clauses = parser.parse_sort(sort, table)
        
        assert len(clauses) == 3
    
    def test_default_order_asc(self, schema, table):
        """Test default order is 'asc' when not specified."""
        parser = OperatorParser(schema)
        sort = [{'field': 'score'}]  # No 'order' key
        
        clauses = parser.parse_sort(sort, table)
        
        assert len(clauses) == 1
        # Should default to ASC
    
    def test_invalid_field_name(self, schema, table):
        """Test error on invalid field name."""
        parser = OperatorParser(schema)
        sort = [{'field': 'nonexistent', 'order': 'asc'}]
        
        with pytest.raises(ValueError, match="not in schema"):
            parser.parse_sort(sort, table)
    
    def test_invalid_order_value(self, schema, table):
        """Test error on invalid order value."""
        parser = OperatorParser(schema)
        sort = [{'field': 'score', 'order': 'ascending'}]
        
        with pytest.raises(ValueError, match="must be 'asc' or 'desc'"):
            parser.parse_sort(sort, table)
    
    def test_missing_field_key(self, schema, table):
        """Test error when 'field' key missing."""
        parser = OperatorParser(schema)
        sort = [{'order': 'asc'}]  # No 'field' key
        
        with pytest.raises(ValueError, match="missing required 'field' key"):
            parser.parse_sort(sort, table)
    
    def test_empty_sort_list(self, schema, table):
        """Test error on empty sort list."""
        parser = OperatorParser(schema)
        sort = []
        
        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse_sort(sort, table)
    
    def test_invalid_sort_type(self, schema, table):
        """Test error when sort is not dict or list."""
        parser = OperatorParser(schema)
        sort = "score"
        
        with pytest.raises(TypeError, match="must be dict or list"):
            parser.parse_sort(sort, table)
```

### 6.3 Integration Tests

**File**: `tests/integration/test_aggregations_sorting.py`

```python
import pytest
from common.database import BotDatabase

@pytest.mark.asyncio
class TestAggregationsIntegration:
    """Test aggregations with real database."""
    
    async def test_count_with_filter(self, db: BotDatabase):
        """Test COUNT aggregation respecting filter."""
        # Setup: Create users
        await db.row_create('users', {'username': 'alice', 'score': 100, 'status': 'active'})
        await db.row_create('users', {'username': 'bob', 'score': 80, 'status': 'active'})
        await db.row_create('users', {'username': 'charlie', 'score': 60, 'status': 'inactive'})
        
        # Query: Count active users
        result = await db.row_search(
            'users',
            filters={'status': {'$eq': 'active'}},
            aggregates={'total': {'$count': '*'}}
        )
        
        assert result == {'total': 2}
    
    async def test_sum_avg_min_max(self, db: BotDatabase):
        """Test multiple aggregations in one query."""
        # Setup
        await db.row_create('users', {'username': 'alice', 'score': 100})
        await db.row_create('users', {'username': 'bob', 'score': 80})
        await db.row_create('users', {'username': 'charlie', 'score': 90})
        
        # Query: Multiple aggregations
        result = await db.row_search(
            'users',
            aggregates={
                'total': {'$count': '*'},
                'total_score': {'$sum': 'score'},
                'avg_score': {'$avg': 'score'},
                'min_score': {'$min': 'score'},
                'max_score': {'$max': 'score'},
            }
        )
        
        assert result['total'] == 3
        assert result['total_score'] == 270
        assert result['avg_score'] == 90.0
        assert result['min_score'] == 80
        assert result['max_score'] == 100
    
    async def test_multi_field_sort(self, db: BotDatabase):
        """Test multi-field sorting with real data."""
        # Setup: Create users with varied status and scores
        await db.row_create('users', {'username': 'alice', 'score': 100, 'status': 'active'})
        await db.row_create('users', {'username': 'bob', 'score': 120, 'status': 'active'})
        await db.row_create('users', {'username': 'charlie', 'score': 90, 'status': 'inactive'})
        await db.row_create('users', {'username': 'diana', 'score': 110, 'status': 'inactive'})
        
        # Query: Sort by status ASC, then score DESC
        rows = await db.row_search(
            'users',
            sort=[
                {'field': 'status', 'order': 'asc'},
                {'field': 'score', 'order': 'desc'}
            ]
        )
        
        # Expected order:
        # 1. bob (active, 120)
        # 2. alice (active, 100)
        # 3. diana (inactive, 110)
        # 4. charlie (inactive, 90)
        assert len(rows) == 4
        assert rows[0]['username'] == 'bob'
        assert rows[1]['username'] == 'alice'
        assert rows[2]['username'] == 'diana'
        assert rows[3]['username'] == 'charlie'
    
    async def test_filter_sort_limit_combined(self, db: BotDatabase):
        """Test complex query combining filters, sorting, and limit."""
        # Setup
        for i in range(10):
            await db.row_create('users', {
                'username': f'user{i}',
                'score': i * 10,
                'status': 'active' if i % 2 == 0 else 'inactive'
            })
        
        # Query: Active users, sorted by score DESC, top 3
        rows = await db.row_search(
            'users',
            filters={'status': {'$eq': 'active'}},
            sort=[{'field': 'score', 'order': 'desc'}],
            limit=3
        )
        
        assert len(rows) == 3
        assert rows[0]['score'] == 80  # user8
        assert rows[1]['score'] == 60  # user6
        assert rows[2]['score'] == 40  # user4
```

**Test Coverage Target**: 85%+ of new code

**Command**:
```bash
pytest tests/unit/database/test_operator_parser.py::TestAggregations -v
pytest tests/unit/database/test_operator_parser.py::TestMultiFieldSorting -v
pytest tests/integration/test_aggregations_sorting.py -v --cov=common.database
```

---

## 7. Acceptance Criteria

- [ ] **AC-1**: All 5 aggregation functions implemented
  - Given OperatorParser with schema
  - When calling parse_aggregations() with COUNT, SUM, AVG, MIN, MAX
  - Then correct SQLAlchemy aggregate expressions returned

- [ ] **AC-2**: COUNT(*) and COUNT(field) both work
  - Given aggregation specs for both COUNT types
  - When parsed
  - Then COUNT(*) uses func.count(), COUNT(field) uses func.count(column)

- [ ] **AC-3**: Type validation prevents invalid aggregations
  - Given SUM or AVG on non-numeric field
  - When calling parse_aggregations()
  - Then TypeError raised with clear message

- [ ] **AC-4**: Multiple aggregations in single query
  - Given 5 different aggregations in one spec
  - When executed via row_search()
  - Then dict returned with all 5 results

- [ ] **AC-5**: Aggregations respect filters
  - Given aggregation with WHERE clause filter
  - When COUNT executed
  - Then only matching rows counted

- [ ] **AC-6**: Multi-field sorting works
  - Given list with 3 sort specifications
  - When parsed
  - Then 3 order_by clauses in priority order

- [ ] **AC-7**: Backward compatible single-field sort
  - Given single dict sort spec (existing format)
  - When parsed
  - Then works exactly as before (no breaking change)

- [ ] **AC-8**: Sort order validation
  - Given invalid order value (not 'asc' or 'desc')
  - When calling parse_sort()
  - Then ValueError raised

- [ ] **AC-9**: Integration test passes
  - Given complex query with filters, multi-field sort, limit
  - When executed
  - Then results sorted correctly by priority order

- [ ] **AC-10**: All unit tests pass with 85%+ coverage
  - Given 25+ new unit tests
  - When running pytest
  - Then all tests pass, coverage ≥85%

---

## 8. Rollout Plan

### Pre-deployment
1. Review code changes in OperatorParser and BotDatabase
2. Run full test suite including new tests
3. Verify aggregations return correct results
4. Test multi-field sort priority order

### Deployment Steps
1. Create feature branch: `git checkout -b feature/sprint-14-sortie-4-aggregations-sorting`
2. Implement `parse_aggregations()` in `operator_parser.py`
3. Implement `parse_sort()` with multi-field support
4. Extend `BotDatabase.row_search()` with aggregates parameter
5. Update sort handling to use new parser method
6. Write comprehensive unit tests (25+ tests)
7. Write integration tests
8. Run tests and verify coverage
9. Commit changes with message:
   ```
   Sprint 14 Sortie 4: Aggregations & Multi-Field Sorting
   
   - Add aggregation functions (COUNT, SUM, AVG, MIN, MAX)
   - Add multi-field sorting with priority order
   - Implement parse_aggregations() method
   - Extend parse_sort() for multi-field support
   - Extend BotDatabase.row_search() with aggregates parameter
   - Add comprehensive type validation
   - Add 25+ unit tests and integration tests
   - Maintain backward compatibility for single-field sort
   
   Implements: SPEC-Sortie-4-Aggregations-Multi-Field-Sorting.md
   Related: PRD-Advanced-Query-Operators.md
   ```
10. Push branch and create PR
11. Code review
12. Merge to main

### Post-deployment
- Monitor NATS handler performance with aggregation queries
- Verify multi-field sorts produce expected results
- Check query performance with complex aggregations

### Rollback Procedure
If issues arise:
```bash
git revert <commit-hash>
# Aggregations are additive, no schema changes
# Safe to rollback without data migration
```

---

## 9. Dependencies & Risks

### Dependencies
- **Sortie 1**: OperatorParser foundation
- **Sortie 2**: Extended filter operators
- **Sortie 3**: Update operators and compound logic
- **Sprint 13**: BotDatabase with row_search() method
- **SQLAlchemy 2.0+**: func.count(), func.sum(), func.avg(), func.min(), func.max()

### External Dependencies
None - all functionality within SQLAlchemy

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Aggregations generate inefficient SQL | Low | Medium | Test EXPLAIN plans, verify indexes used |
| Multi-field sort with many fields slow | Low | Medium | Recommend limit on sort fields in docs |
| Breaking change to sort parameter | Low | High | Maintain backward compatibility with dict input |
| MIN/MAX on text fields produce unexpected results | Medium | Low | Document string comparison semantics |
| COUNT(*) vs COUNT(field) confusion | Medium | Low | Clear documentation with examples |

---

## 10. Documentation

### Code Documentation
- Docstrings for `parse_aggregations()` with examples
- Docstrings for extended `parse_sort()` explaining priority order
- Comments explaining aggregation type validation
- Type hints for all method parameters

### User Documentation
Updates needed in **docs/guides/DATABASE_QUERIES.md**:
- Aggregation functions section with examples
- Multi-field sorting section with priority explanation
- Combining filters, aggregations, and sorting
- Performance considerations

### Developer Documentation
Update **docs/DATABASE.md** with:
- Aggregation function reference table
- Multi-field sort examples
- Type compatibility matrix for aggregations
- Query optimization tips

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-Operator-Parser-Foundation.md](SPEC-Sortie-1-Operator-Parser-Foundation.md)
- [SPEC-Sortie-2-Extended-Filter-Operators.md](SPEC-Sortie-2-Extended-Filter-Operators.md)
- [SPEC-Sortie-3-Update-Operators-Compound-Logic.md](SPEC-Sortie-3-Update-Operators-Compound-Logic.md)

**Next**: 
- [SPEC-Sortie-5-Integration-Docs-Performance-Tests.md](SPEC-Sortie-5-Integration-Docs-Performance-Tests.md)

**Parent PRD**: [PRD-Advanced-Query-Operators.md](PRD-Advanced-Query-Operators.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
