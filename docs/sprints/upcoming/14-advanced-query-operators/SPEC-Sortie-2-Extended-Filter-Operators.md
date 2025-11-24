# SPEC: Sortie 2 - Extended Filter Operators

**Sprint**: 14 (Advanced Query Operators)  
**Sortie**: 2 of 5  
**Estimated Effort**: ~5 hours  
**Branch**: `feature/sprint-14-sortie-2-extended-filters`  
**Dependencies**: Sortie 1 (OperatorParser foundation)

---

## 1. Overview

Extend OperatorParser with set operators ($in, $nin), pattern matching ($like, $ilike), and existence checks ($exists, $null), enabling rich query capabilities for plugins.

**What This Sortie Achieves**:

- Set membership operators ($in, $nin)
- Pattern matching with SQL wildcards ($like, $ilike)
- Existence/null checking ($exists, $null)
- Type validation for new operators
- Comprehensive test coverage

---

## 2. Scope and Non-Goals

### In Scope

✅ Set operators: $in (in list), $nin (not in list)  
✅ Pattern operators: $like (case-sensitive), $ilike (case-insensitive)  
✅ Existence operators: $exists (not null), $null (is null)  
✅ Type validation for pattern operators (string/text only)  
✅ List validation for set operators  
✅ Unit tests (15+ additional tests)  
✅ Integration tests with NATS

### Out of Scope

❌ Compound logic ($and, $or, $not) - Sortie 3  
❌ Update operators - Sortie 3  
❌ Regular expressions - Future enhancement  
❌ Full-text search - V2 feature

---

## 3. Requirements

### Functional Requirements

**FR-1**: Set operators must:
- $in: Match if field value in provided list
- $nin: Match if field value NOT in provided list
- Accept list of 1+ values
- Work with all field types
- Handle empty list edge case

**FR-2**: Pattern operators must:
- $like: Case-sensitive pattern match with SQL wildcards (%, _)
- $ilike: Case-insensitive pattern match
- Only work on string/text fields
- Support % (zero or more chars) and _ (single char) wildcards
- Handle literal % and _ with escaping

**FR-3**: Existence operators must:
- $exists: true = field not null, false = field is null
- $null: true = field is null, false = field not null
- Accept boolean values only
- Work on all field types (including optional fields)

**FR-4**: Error handling must:
- Reject set operators with non-list values
- Reject pattern operators on non-string fields
- Reject existence operators with non-boolean values
- Provide clear error messages

### Non-Functional Requirements

**NFR-1 Performance**: 
- Set operator with 100 values: <10ms overhead
- Pattern matching: Use database indexes where possible

**NFR-2 Compatibility**: Works with Sortie 1 comparison operators

**NFR-3 Testing**: ≥95% code coverage for new operators

---

## 4. Technical Design

### 4.1 OperatorParser Extensions

**File**: `common/database/operator_parser.py` (modifications)

```python
class OperatorParser:
    """Parse MongoDB-style query operators into SQLAlchemy clauses."""
    
    # ... existing COMPARISON_OPS ...
    
    # Set membership operators
    SET_OPS = {
        '$in': lambda col, vals: col.in_(vals),
        '$nin': lambda col, vals: ~col.in_(vals),  # NOT IN
    }
    
    # Pattern matching operators
    PATTERN_OPS = {
        '$like': lambda col, pattern: col.like(pattern),
        '$ilike': lambda col, pattern: col.ilike(pattern),
    }
    
    # Existence/null operators
    EXISTENCE_OPS = {
        '$exists': lambda col, exists: col.isnot(None) if exists else col.is_(None),
        '$null': lambda col, is_null: col.is_(None) if is_null else col.isnot(None),
    }
    
    # Field types compatible with pattern operators
    PATTERN_COMPATIBLE_TYPES = {'string', 'text'}
    
    def __init__(self, schema: Dict[str, Any]):
        """Initialize parser with schema."""
        # ... existing code ...
        
        # Combine all operator sets for validation
        self.all_operators = {
            **self.COMPARISON_OPS,
            **self.SET_OPS,
            **self.PATTERN_OPS,
            **self.EXISTENCE_OPS
        }
    
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
        
        Extended in Sortie 2 with set, pattern, and existence operators.
        """
        # Comparison operators (from Sortie 1)
        if operator in self.COMPARISON_OPS:
            if operator in self.RANGE_OPS:
                if field_type not in self.RANGE_COMPATIBLE_TYPES:
                    raise TypeError(
                        f"Range operator '{operator}' on field '{field_name}' requires "
                        f"numeric or datetime type, got '{field_type}'"
                    )
            op_func = self.COMPARISON_OPS[operator]
            return op_func(column, value)
        
        # Set operators (NEW in Sortie 2)
        if operator in self.SET_OPS:
            # Validate value is a list
            if not isinstance(value, list):
                raise TypeError(
                    f"Set operator '{operator}' on field '{field_name}' requires "
                    f"list value, got {type(value).__name__}"
                )
            
            # Validate non-empty list
            if len(value) == 0:
                raise ValueError(
                    f"Set operator '{operator}' on field '{field_name}' requires "
                    f"non-empty list"
                )
            
            op_func = self.SET_OPS[operator]
            return op_func(column, value)
        
        # Pattern operators (NEW in Sortie 2)
        if operator in self.PATTERN_OPS:
            # Validate field type
            if field_type not in self.PATTERN_COMPATIBLE_TYPES:
                raise TypeError(
                    f"Pattern operator '{operator}' on field '{field_name}' requires "
                    f"string or text type, got '{field_type}'. "
                    f"Pattern operators can only be used with: "
                    f"{', '.join(sorted(self.PATTERN_COMPATIBLE_TYPES))}"
                )
            
            # Validate value is a string
            if not isinstance(value, str):
                raise TypeError(
                    f"Pattern operator '{operator}' on field '{field_name}' requires "
                    f"string value, got {type(value).__name__}"
                )
            
            op_func = self.PATTERN_OPS[operator]
            return op_func(column, value)
        
        # Existence operators (NEW in Sortie 2)
        if operator in self.EXISTENCE_OPS:
            # Validate value is boolean
            if not isinstance(value, bool):
                raise TypeError(
                    f"Existence operator '{operator}' on field '{field_name}' requires "
                    f"boolean value, got {type(value).__name__}"
                )
            
            op_func = self.EXISTENCE_OPS[operator]
            return op_func(column, value)
        
        # Unknown operator
        raise ValueError(
            f"Unknown operator '{operator}' on field '{field_name}'. "
            f"Supported operators: {', '.join(sorted(self.all_operators.keys()))}"
        )
```

---

## 5. Implementation Steps

### Step 1: Extend OperatorParser

1. Add SET_OPS dict
2. Add PATTERN_OPS dict
3. Add EXISTENCE_OPS dict
4. Update `_parse_operator()` with new operator handling
5. Update `all_operators` for error messages

### Step 2: Update Tests

1. Extend `tests/unit/database/test_operator_parser.py`
2. Add set operator tests
3. Add pattern operator tests
4. Add existence operator tests

### Step 3: Integration Tests

Update `tests/integration/test_row_nats.py` with real-world queries

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/unit/database/test_operator_parser.py` (additions)

```python
class TestSetOperators:
    """Test set membership operators."""
    
    def test_in_operator(self, sample_schema, sample_table):
        """Test $in operator."""
        parser = OperatorParser(sample_schema)
        
        filters = {'username': {'$in': ['alice', 'bob', 'charlie']}}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
        # Should compile to: username IN ('alice', 'bob', 'charlie')
    
    def test_nin_operator(self, sample_schema, sample_table):
        """Test $nin operator (not in)."""
        parser = OperatorParser(sample_schema)
        
        filters = {'username': {'$nin': ['banned_user', 'test_user']}}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
        # Should compile to: username NOT IN (...)
    
    def test_in_with_single_value(self, sample_schema, sample_table):
        """Test $in with single-element list."""
        parser = OperatorParser(sample_schema)
        
        filters = {'score': {'$in': [100]}}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
    
    def test_in_with_mixed_types(self, sample_schema, sample_table):
        """Test $in with integers."""
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


class TestPatternOperators:
    """Test pattern matching operators."""
    
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
    
    def test_like_wildcards(self, sample_schema, sample_table):
        """Test SQL wildcard patterns."""
        parser = OperatorParser(sample_schema)
        
        # % = zero or more characters
        filters1 = {'username': {'$like': 'user%'}}
        clauses1 = parser.parse_filters(filters1, sample_table)
        assert len(clauses1) == 1
        
        # _ = exactly one character
        filters2 = {'username': {'$like': 'user_'}}
        clauses2 = parser.parse_filters(filters2, sample_table)
        assert len(clauses2) == 1
        
        # Combined
        filters3 = {'username': {'$like': 'user_%'}}
        clauses3 = parser.parse_filters(filters3, sample_table)
        assert len(clauses3) == 1
    
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
    
    def test_pattern_requires_string_value(self, sample_schema, sample_table):
        """Test pattern operator rejects non-string value."""
        parser = OperatorParser(sample_schema)
        
        filters = {'username': {'$like': 123}}  # Integer, not string
        
        with pytest.raises(TypeError, match="requires string value"):
            parser.parse_filters(filters, sample_table)


class TestExistenceOperators:
    """Test existence/null operators."""
    
    def test_exists_true(self, sample_schema, sample_table):
        """Test $exists: true (field is not null)."""
        parser = OperatorParser(sample_schema)
        
        filters = {'rating': {'$exists': True}}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
        # Should compile to: rating IS NOT NULL
    
    def test_exists_false(self, sample_schema, sample_table):
        """Test $exists: false (field is null)."""
        parser = OperatorParser(sample_schema)
        
        filters = {'rating': {'$exists': False}}
        clauses = parser.parse_filters(filters, sample_table)
        
        assert len(clauses) == 1
        # Should compile to: rating IS NULL
    
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
    
    def test_exists_on_any_field_type(self, sample_schema, sample_table):
        """Test $exists works on all field types."""
        parser = OperatorParser(sample_schema)
        
        # String
        clauses1 = parser.parse_filters({'username': {'$exists': True}}, sample_table)
        assert len(clauses1) == 1
        
        # Integer
        clauses2 = parser.parse_filters({'score': {'$exists': False}}, sample_table)
        assert len(clauses2) == 1
        
        # Boolean
        clauses3 = parser.parse_filters({'active': {'$exists': True}}, sample_table)
        assert len(clauses3) == 1


class TestCombinedOperators:
    """Test combining new operators with existing ones."""
    
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
```

### 6.2 Integration Tests

**File**: `tests/integration/test_row_nats.py` (additions)

```python
class TestExtendedFilterOperators:
    """Test extended operators via NATS."""
    
    async def test_in_operator_via_nats(self, nats_client, db_service):
        """Test $in operator via NATS."""
        # Setup schema and data
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "users",
                "schema": {
                    "fields": [
                        {"name": "username", "type": "string", "required": True},
                        {"name": "status", "type": "string", "required": True}
                    ]
                }
            }).encode()
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "users",
                "data": [
                    {"username": "alice", "status": "active"},
                    {"username": "bob", "status": "banned"},
                    {"username": "charlie", "status": "active"},
                    {"username": "dave", "status": "inactive"}
                ]
            }).encode()
        )
        
        # Search with $in
        resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "users",
                "filters": {"status": {"$in": ["active", "inactive"]}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(resp.data.decode())
        
        assert result['success'] == True
        assert result['count'] == 3
        statuses = {row['status'] for row in result['rows']}
        assert statuses == {'active', 'inactive'}
    
    async def test_like_operator_via_nats(self, nats_client, db_service):
        """Test $like operator via NATS."""
        # Setup
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "users",
                "schema": {
                    "fields": [{"name": "username", "type": "string", "required": True}]
                }
            }).encode()
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "users",
                "data": [
                    {"username": "test_user_1"},
                    {"username": "test_user_2"},
                    {"username": "alice"},
                    {"username": "test_admin"}
                ]
            }).encode()
        )
        
        # Search: usernames starting with "test_user_"
        resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "users",
                "filters": {"username": {"$like": "test_user_%"}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(resp.data.decode())
        
        assert result['count'] == 2
        usernames = {row['username'] for row in result['rows']}
        assert usernames == {'test_user_1', 'test_user_2'}
    
    async def test_exists_operator_via_nats(self, nats_client, db_service):
        """Test $exists operator via NATS."""
        # Setup with optional field
        await nats_client.request(
            "rosey.db.row.test.schema.register",
            json.dumps({
                "table": "items",
                "schema": {
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "description", "type": "text", "required": False}
                    ]
                }
            }).encode()
        )
        
        await nats_client.request(
            "rosey.db.row.test.insert",
            json.dumps({
                "table": "items",
                "data": [
                    {"name": "Item 1", "description": "Has description"},
                    {"name": "Item 2", "description": None},
                    {"name": "Item 3", "description": "Also has one"}
                ]
            }).encode()
        )
        
        # Search: items WITH description
        resp = await nats_client.request(
            "rosey.db.row.test.search",
            json.dumps({
                "table": "items",
                "filters": {"description": {"$exists": True}}
            }).encode(),
            timeout=1.0
        )
        result = json.loads(resp.data.decode())
        
        assert result['count'] == 2
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: $in operator works
  - Given filter with $in and list of values
  - When searching
  - Then returns rows matching any value in list

- [x] **AC-2**: $nin operator works
  - Given filter with $nin
  - When searching
  - Then returns rows NOT matching any value in list

- [x] **AC-3**: $like operator works
  - Given pattern with % and _ wildcards
  - When searching
  - Then returns matching rows (case-sensitive)

- [x] **AC-4**: $ilike operator works
  - Given pattern
  - When searching
  - Then returns matching rows (case-insensitive)

- [x] **AC-5**: $exists operator works
  - Given $exists: true/false
  - When searching
  - Then returns rows with non-null/null values

- [x] **AC-6**: Type validation enforced
  - Given pattern operator on non-string field
  - When parsing
  - Then TypeError raised

- [x] **AC-7**: Set operator validation works
  - Given $in with non-list value
  - When parsing
  - Then TypeError raised with clear message

- [x] **AC-8**: All unit tests pass (15+ new tests, 95%+ coverage)

- [x] **AC-9**: All integration tests pass

- [x] **AC-10**: Backward compatibility maintained
  - Given Sortie 1 comparison operators
  - When using
  - Then still work correctly

---

## 8. Rollout Plan

### Pre-deployment

1. Review code changes
2. Run full test suite
3. Verify backward compatibility

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-14-sortie-2-extended-filters`
2. Extend OperatorParser with new operators
3. Add comprehensive unit tests
4. Add integration tests
5. Run tests and verify coverage
6. Commit with message:
   ```
   Sprint 14 Sortie 2: Extended Filter Operators
   
   - Add set operators ($in, $nin)
   - Add pattern operators ($like, $ilike)
   - Add existence operators ($exists, $null)
   - Type validation for new operators
   - Comprehensive tests (15+ tests, 95%+ coverage)
   
   Implements: SPEC-Sortie-2-Extended-Filter-Operators.md
   Related: PRD-Advanced-Query-Operators.md
   Depends-On: SPEC-Sortie-1-Operator-Parser-Foundation.md
   ```
7. Push branch and create PR
8. Code review
9. Merge to main

### Post-deployment

- Monitor pattern matching performance
- Check for set operator usage patterns
- Verify existence checks working correctly

### Rollback Procedure

```bash
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: OperatorParser class must exist
- **SQLAlchemy**: For .in_(), .like(), .ilike() methods

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Pattern matching slow on large tables | Medium | Medium | Document index recommendations |
| $in with large lists slow | Low | Low | Benchmark and set reasonable limits |
| SQL injection via pattern | Low | High | SQLAlchemy escapes patterns automatically |

---

## 10. Documentation

### Code Documentation

- All new operators documented in docstrings
- Wildcard syntax explained
- Examples provided

### Developer Documentation

Update `docs/guides/PLUGIN_ROW_STORAGE.md` with:
- Set operator examples
- Pattern matching guide with wildcard reference
- Existence check examples

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-1-Operator-Parser-Foundation.md](SPEC-Sortie-1-Operator-Parser-Foundation.md)  
**Next**: [SPEC-Sortie-3-Update-Operators-Compound-Logic.md](SPEC-Sortie-3-Update-Operators-Compound-Logic.md)

**Parent PRD**: [PRD-Advanced-Query-Operators.md](PRD-Advanced-Query-Operators.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
