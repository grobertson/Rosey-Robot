# PRD: Advanced Query Operators (Sprint 14)

**Version**: 1.0  
**Status**: Draft  
**Sprint**: 14 (Advanced Queries)  
**Estimated Duration**: 4-5 days  
**Estimated Sorties**: 5 sorties  
**Prerequisites**: Sprint 13 (Row Operations Foundation)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Context](#2-problem-statement--context)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Success Metrics](#4-success-metrics)
5. [User Personas](#5-user-personas)
6. [User Stories](#6-user-stories)
7. [Technical Architecture](#7-technical-architecture)
8. [Operator Specifications](#8-operator-specifications)
9. [Query Language Design](#9-query-language-design)
10. [NATS API Extensions](#10-nats-api-extensions)
11. [Implementation Plan](#11-implementation-plan)
12. [Testing Strategy](#12-testing-strategy)
13. [Performance Requirements](#13-performance-requirements)
14. [Security & Validation](#14-security--validation)
15. [Error Handling](#15-error-handling)
16. [Observability](#16-observability)
17. [Documentation Requirements](#17-documentation-requirements)
18. [Dependencies & Risks](#18-dependencies--risks)
19. [Sprint Acceptance Criteria](#19-sprint-acceptance-criteria)
20. [Future Enhancements](#20-future-enhancements)
21. [Appendices](#21-appendices)

---

## 1. Executive Summary

### 1.1 Overview

Sprint 14 extends the Row Operations Foundation (Sprint 13) with **MongoDB-style query operators** and **atomic update operations**. This enables plugins to perform complex queries (range filters, pattern matching, set membership) and atomic updates (increment counters, update-if-greater) without race conditions.

### 1.2 Key Features

**Query Filter Operators**:
- Comparison: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`
- Set: `$in`, `$nin` (not in)
- Pattern: `$like`, `$ilike` (case-insensitive)
- Existence: `$exists`, `$null`

**Update Operators**:
- Scalar: `$set`, `$inc`, `$dec`, `$mul`
- Conditional: `$max`, `$min`
- Array: `$push`, `$pull`, `$addToSet` (if time permits)

**Compound Logic**:
- `$and`, `$or`, `$not` for filter composition
- Multi-field sorting (priority order)
- Aggregation basics: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`

### 1.3 Sprint Scope

**In Scope**:
- All filter operators above
- All scalar update operators ($set, $inc, $dec, $mul, $max, $min)
- Compound filters ($and, $or, $not)
- Multi-field sorting
- Basic aggregations (count, sum, avg, min, max)

**Out of Scope** (Deferred):
- Array operators ($push, $pull, $addToSet) - complex, needs array field type
- Joins across tables - Sprint 17 (SQL)
- Full-text search - V2 feature
- Geospatial queries - V2 feature
- Graph traversal - V2 feature

### 1.4 Why This Matters

**Current Pain** (Sprint 13):
```python
# Find users with score >= 100 - CANNOT DO THIS
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {'score': 100}  # Only equality!
}).encode())
```

**After Sprint 14**:
```python
# Range query - NOW POSSIBLE
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {'score': {'$gte': 100}},
    'sort': [{'field': 'score', 'order': 'desc'}],
    'limit': 10
}).encode())

# Atomic increment - NO RACE CONDITIONS
response = await nats.request('db.row.trivia.update', json.dumps({
    'table': 'stats',
    'filters': {'user_id': 'groberts'},
    'operations': {
        'score': {'$inc': 10},
        'best_streak': {'$max': 5}
    }
}).encode())
```

---

## 2. Problem Statement & Context

### 2.1 Current Limitations

**Sprint 13 Provided**:
- ✅ Equality filters only: `{'author': 'MST3K'}`
- ✅ Single-field sorting: `{'field': 'timestamp', 'order': 'desc'}`
- ✅ Basic updates: Replace entire row or specific fields

**What's Missing**:
- ❌ Range queries: "scores above 100", "dates after 2025-01-01"
- ❌ Pattern matching: "usernames starting with 'test_'"
- ❌ Set membership: "status in ['active', 'pending']"
- ❌ Atomic increments: Increment counter without read-modify-write race
- ❌ Conditional updates: "Update best_score only if new score is higher"
- ❌ Complex filters: "(score > 100 OR wins > 10) AND active = true"

### 2.2 Real-World Use Cases

**Trivia Plugin**:
```python
# Leaderboard: Top 10 users with score >= 100
filters = {
    'score': {'$gte': 100},
    'active': True
}
sort = [
    {'field': 'score', 'order': 'desc'},
    {'field': 'wins', 'order': 'desc'}  # Tiebreaker
]

# Atomic score update (no race condition)
operations = {
    'score': {'$inc': 10},
    'wins': {'$inc': 1},
    'best_streak': {'$max': current_streak}
}
```

**Quote Database Plugin**:
```python
# Find quotes with pattern
filters = {
    'text': {'$ilike': '%circulating%'},  # Case-insensitive
    'timestamp': {'$gte': '2025-01-01'}
}

# Find quotes by multiple authors
filters = {
    'author': {'$in': ['MST3K', 'Rifftrax', 'Cinematic Titanic']}
}
```

**Playlist Plugin**:
```python
# Find videos added this month
filters = {
    'added_timestamp': {
        '$gte': '2025-11-01',
        '$lt': '2025-12-01'
    },
    'duration': {'$lte': 300}  # <= 5 minutes
}
```

### 2.3 Technical Context

**Database Backend**: PostgreSQL with SQLAlchemy ORM
**Query Translation**: Operators translate to SQL:
- `{'score': {'$gte': 100}}` → `WHERE score >= 100`
- `{'$or': [{'a': 1}, {'b': 2}]}` → `WHERE (a = 1 OR b = 2)`
- `{'score': {'$inc': 10}}` → `UPDATE ... SET score = score + 10`

**Atomic Operations**: Use database-native atomic updates:
```sql
-- No race condition, single SQL statement
UPDATE trivia_stats 
SET score = score + 10, 
    best_streak = GREATEST(best_streak, 5)
WHERE user_id = 'groberts';
```

---

## 3. Goals & Non-Goals

### 3.1 Business Goals

1. **Enable Complex Queries**: Plugins can filter, sort, and search data expressively
2. **Prevent Race Conditions**: Atomic updates eliminate read-modify-write bugs
3. **MongoDB-Style UX**: Familiar operator syntax for developers
4. **Performance**: Complex queries execute in <50ms p95
5. **Maintainability**: Operators map cleanly to SQL, easy to debug

### 3.2 User Goals

**Plugin Developers**:
- Write expressive queries without learning SQL
- Atomic updates prevent subtle race condition bugs
- Clear error messages when operators misused

**System Administrators**:
- Monitor slow queries via logs
- Understand query patterns from operator usage
- Profile and optimize database indexes

**End Users** (Indirect):
- Faster response times (efficient queries)
- Correct data (no race conditions)
- Rich features (leaderboards, search, analytics)

### 3.3 Non-Goals

**Out of Scope for Sprint 14**:
- ❌ Array operators ($push, $pull) - Needs array field type (complex)
- ❌ Joins across tables - Use Sprint 17 (Parameterized SQL)
- ❌ Transactions (multi-row atomic) - V2 feature
- ❌ Full-text search - Use external search engine (Elasticsearch)
- ❌ Query optimizer - Rely on PostgreSQL query planner
- ❌ Materialized views - V2 performance feature
- ❌ Schema changes - Sprint 15 (Migrations)

---

## 4. Success Metrics

### 4.1 Functional Metrics

**Operator Coverage**:
- ✅ 10+ filter operators implemented
- ✅ 6+ update operators implemented
- ✅ Compound filters ($and, $or, $not) working
- ✅ Multi-field sorting (3+ fields)
- ✅ 5 aggregation functions (count, sum, avg, min, max)

**Query Expressiveness**:
- ✅ 95%+ of common queries expressible without SQL
- ✅ <5% of queries require Sprint 17 (SQL tier)

### 4.2 Performance Metrics

**Latency Targets**:
- Simple operator query (1 filter): <20ms p95
- Complex query (3+ filters, 2 sorts): <50ms p95
- Atomic update (2+ operations): <15ms p95
- Aggregation (COUNT, SUM): <30ms p95

**Throughput**:
- 400+ queries/sec sustained (mixed operators)
- 300+ atomic updates/sec sustained

### 4.3 Quality Metrics

**Testing**:
- ≥90% test coverage (operators complex, need thorough tests)
- 150+ unit tests (each operator + edge cases)
- 50+ integration tests (compound queries, end-to-end)
- 20+ performance tests (query latency)

**Correctness**:
- Zero race conditions in atomic updates
- SQL injection impossible (parameterized queries only)
- Type validation prevents invalid operator usage

---

## 5. User Personas

### 5.1 Alex - Plugin Developer (Primary)

**Profile**:
- 3 years Python experience
- Familiar with MongoDB query syntax
- Building trivia plugin with leaderboards
- Needs atomic score updates

**Goals**:
- Write expressive queries without SQL knowledge
- Atomic updates prevent race conditions
- Fast iteration (clear error messages)

**Pain Points**:
- Sprint 13 equality filters too limiting
- Race conditions when incrementing counters
- Unclear how to do "top 10 scores >= 100"

**Success Criteria**:
- Can implement leaderboard in <1 hour
- Zero race condition bugs
- Query docs have copy-paste examples

### 5.2 Jordan - System Administrator (Secondary)

**Profile**:
- 5 years ops experience
- Manages Rosey-Robot production deployment
- Monitors database performance

**Goals**:
- Identify slow queries from logs
- Profile query patterns for optimization
- Ensure database indexes cover common queries

**Pain Points**:
- Sprint 13 logs don't show filter complexity
- Can't distinguish "slow query" from "large result set"
- No query profiling tools yet

**Success Criteria**:
- Logs show operator usage (e.g., "$gte on score field")
- Can identify missing indexes from slow queries
- Query duration logged with operator breakdown

### 5.3 Sam - Power User (Tertiary)

**Profile**:
- Uses Inspector plugin to query bot internals
- Comfortable with technical commands
- Helps debug issues in chat

**Goals**:
- Run ad-hoc queries on plugin data
- Inspect leaderboards and statistics
- Debug "why isn't my score updating?"

**Pain Points**:
- Sprint 13 search limited to equality
- Can't filter by date ranges
- No way to see "top scores this month"

**Success Criteria**:
- Inspector plugin supports operator syntax
- Can run queries like `!inspect query trivia.stats score>100 sort=score:desc limit=5`
- Clear output format

---

## 6. User Stories

### 6.1 GH-ADV-001: Range Filter Queries

**As** a plugin developer  
**I want** to filter rows by numeric/date ranges  
**So that** I can find "scores above 100" or "quotes added this month"

**Acceptance Criteria**:
1. ✅ Support `$gt`, `$gte`, `$lt`, `$lte` operators on INTEGER, BIGINT, FLOAT, TIMESTAMP fields
2. ✅ Example: `{'score': {'$gte': 100, '$lt': 200}}` finds scores 100-199
3. ✅ Example: `{'timestamp': {'$gte': '2025-11-01', '$lt': '2025-12-01'}}` finds November dates
4. ✅ Type validation: Using `$gte` on TEXT field returns clear error
5. ✅ Edge case: `{'value': {'$gte': null}}` handles NULL comparisons correctly
6. ✅ Performance: Range query on indexed field <20ms p95

**Example Usage**:
```python
# Trivia leaderboard: scores 100-200
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {
        'score': {'$gte': 100, '$lte': 200}
    },
    'sort': [{'field': 'score', 'order': 'desc'}],
    'limit': 10
}).encode())
```

---

### 6.2 GH-ADV-002: Set Membership Filters

**As** a plugin developer  
**I want** to filter rows where field matches any value in a set  
**So that** I can find "quotes by MST3K, Rifftrax, or Cinematic Titanic"

**Acceptance Criteria**:
1. ✅ Support `$in` operator with array of values
2. ✅ Support `$nin` (not in) operator
3. ✅ Example: `{'author': {'$in': ['MST3K', 'Rifftrax']}}` finds either author
4. ✅ Type validation: Values in array must match field type
5. ✅ Empty array: `{'status': {'$in': []}}` returns zero rows
6. ✅ Performance: $in query with 10 values <25ms p95

**Example Usage**:
```python
# Quotes from multiple authors
response = await nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {
        'author': {'$in': ['MST3K', 'Rifftrax', 'Cinematic Titanic']}
    }
}).encode())
```

---

### 6.3 GH-ADV-003: Pattern Matching Filters

**As** a plugin developer  
**I want** to filter rows by text patterns  
**So that** I can find "usernames starting with 'test_'" or "quotes containing 'circulating'"

**Acceptance Criteria**:
1. ✅ Support `$like` operator (SQL LIKE, case-sensitive)
2. ✅ Support `$ilike` operator (case-insensitive)
3. ✅ Example: `{'text': {'$ilike': '%circulating%'}}` finds "Keep Circulating the Tapes"
4. ✅ Example: `{'username': {'$like': 'test_%'}}` finds usernames starting with "test_"
5. ✅ Wildcard escaping: `%` and `_` can be escaped with `\\`
6. ✅ Performance: Pattern match on indexed field <30ms p95

**Example Usage**:
```python
# Search quotes containing "tapes" (case-insensitive)
response = await nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {
        'text': {'$ilike': '%tapes%'}
    }
}).encode())
```

---

### 6.4 GH-ADV-004: Atomic Increment Operations

**As** a plugin developer  
**I want** to atomically increment/decrement numeric fields  
**So that** I can update scores without race conditions

**Acceptance Criteria**:
1. ✅ Support `$inc` operator (increment by N)
2. ✅ Support `$dec` operator (decrement by N, equivalent to $inc with negative)
3. ✅ Support `$mul` operator (multiply by N)
4. ✅ Example: `{'score': {'$inc': 10}}` increments score by 10 atomically
5. ✅ Type validation: $inc only works on INTEGER, BIGINT, FLOAT fields
6. ✅ Race condition test: 100 concurrent $inc operations yield correct total
7. ✅ Performance: Atomic update <15ms p95

**Example Usage**:
```python
# Atomic score update (no race condition)
response = await nats.request('db.row.trivia.update', json.dumps({
    'table': 'stats',
    'filters': {'user_id': 'groberts'},
    'operations': {
        'score': {'$inc': 10},
        'games_played': {'$inc': 1}
    }
}).encode())
```

---

### 6.5 GH-ADV-005: Conditional Update Operations

**As** a plugin developer  
**I want** to update fields only if new value is greater/lesser  
**So that** I can track "best score" or "fastest time" without read-modify-write

**Acceptance Criteria**:
1. ✅ Support `$max` operator (update if new value > current)
2. ✅ Support `$min` operator (update if new value < current)
3. ✅ Example: `{'best_score': {'$max': 150}}` updates only if 150 > current best_score
4. ✅ NULL handling: $max with NULL value leaves field unchanged
5. ✅ Type validation: $max/$min only on numeric/timestamp fields
6. ✅ Performance: Conditional update <15ms p95

**Example Usage**:
```python
# Update best_score and best_streak if higher
response = await nats.request('db.row.trivia.update', json.dumps({
    'table': 'stats',
    'filters': {'user_id': 'groberts'},
    'operations': {
        'best_score': {'$max': 150},
        'best_streak': {'$max': 5}
    }
}).encode())
```

---

### 6.6 GH-ADV-006: Compound Filter Logic

**As** a plugin developer  
**I want** to combine filters with AND/OR logic  
**So that** I can query "(score >= 100 OR wins >= 10) AND active = true"

**Acceptance Criteria**:
1. ✅ Support `$and` operator (all conditions must match)
2. ✅ Support `$or` operator (any condition must match)
3. ✅ Support `$not` operator (negation)
4. ✅ Implicit AND: `{'a': 1, 'b': 2}` equivalent to `{'$and': [{'a': 1}, {'b': 2}]}`
5. ✅ Nested logic: `{'$or': [{'$and': [...]}, {'score': {'$gt': 200}}]}`
6. ✅ Performance: Compound query (3 filters) <50ms p95

**Example Usage**:
```python
# Complex filter: (score >= 100 OR wins >= 10) AND active = true
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {
        '$and': [
            {
                '$or': [
                    {'score': {'$gte': 100}},
                    {'wins': {'$gte': 10}}
                ]
            },
            {'active': True}
        ]
    }
}).encode())
```

---

### 6.7 GH-ADV-007: Multi-Field Sorting

**As** a plugin developer  
**I want** to sort results by multiple fields with priority  
**So that** I can implement "sort by score desc, then by timestamp asc (tiebreaker)"

**Acceptance Criteria**:
1. ✅ Support array of sort objects: `[{'field': 'score', 'order': 'desc'}, {'field': 'timestamp', 'order': 'asc'}]`
2. ✅ First sort field has priority, subsequent fields break ties
3. ✅ Backward compatible: Single-field sort `{'field': 'score', 'order': 'desc'}` still works
4. ✅ Validation: Sort field must exist in schema
5. ✅ Performance: Multi-field sort (3 fields) <30ms p95

**Example Usage**:
```python
# Leaderboard with tiebreaker
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'sort': [
        {'field': 'score', 'order': 'desc'},
        {'field': 'wins', 'order': 'desc'},
        {'field': 'timestamp', 'order': 'asc'}  # Earlier wins tiebreak
    ],
    'limit': 10
}).encode())
```

---

### 6.8 GH-ADV-008: Basic Aggregations

**As** a plugin developer  
**I want** to compute COUNT, SUM, AVG, MIN, MAX on query results  
**So that** I can get "total score across all users" or "average game duration"

**Acceptance Criteria**:
1. ✅ Support `aggregate` field in search request with functions: `count`, `sum`, `avg`, `min`, `max`
2. ✅ Example: `{'aggregate': {'total_score': {'$sum': 'score'}}}` sums score field
3. ✅ Example: `{'aggregate': {'player_count': {'$count': '*'}}}` counts rows
4. ✅ Aggregations respect filters (only aggregate matching rows)
5. ✅ Type validation: $sum/$avg only on numeric fields
6. ✅ Performance: Aggregation query <30ms p95

**Example Usage**:
```python
# Total and average score for active players
response = await nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {'active': True},
    'aggregate': {
        'total_score': {'$sum': 'score'},
        'avg_score': {'$avg': 'score'},
        'player_count': {'$count': '*'}
    }
}).encode())

# Response: {'aggregates': {'total_score': 1500, 'avg_score': 150.0, 'player_count': 10}}
```

---

### 6.9 GH-ADV-009: Operator Validation Errors

**As** a plugin developer  
**I want** clear error messages when I misuse operators  
**So that** I can quickly fix my query syntax

**Acceptance Criteria**:
1. ✅ Invalid operator: `{'score': {'$invalid': 100}}` returns `INVALID_OPERATOR` error
2. ✅ Type mismatch: `{'score': {'$gte': 'text'}}` returns `TYPE_MISMATCH` error
3. ✅ Wrong field type: `{'text': {'$inc': 1}}` returns `OPERATOR_NOT_SUPPORTED` error
4. ✅ Malformed query: `{'$or': 'not an array'}` returns `MALFORMED_QUERY` error
5. ✅ Error message includes: operator name, field name, expected type, provided type

**Example Error**:
```json
{
  "success": false,
  "error_code": "TYPE_MISMATCH",
  "message": "Operator $gte on field 'score' expects numeric value, got string 'text'",
  "field": "score",
  "operator": "$gte",
  "expected_type": "INTEGER",
  "provided_type": "STRING"
}
```

---

### 6.10 GH-ADV-010: Operator Performance Profiling

**As** a system administrator  
**I want** query logs to show which operators were used  
**So that** I can identify slow queries and optimize indexes

**Acceptance Criteria**:
1. ✅ Logs include operator summary: `filters=[$gte, $in], operations=[$inc, $max]`
2. ✅ Slow query warning (>100ms) logs full query structure
3. ✅ Performance metrics tagged by operator type
4. ✅ Inspector plugin can show "slowest queries this hour"

**Example Log**:
```
[ROW] search: plugin=trivia table=stats filters=[$gte, $in] sort=[score:desc, wins:desc] rows=10 latency=25ms
[ROW] update: plugin=trivia table=stats filters=[$eq] operations=[$inc, $max] updated=1 latency=12ms
[ROW] SLOW QUERY (150ms): plugin=quote-db table=quotes filters=[$ilike] query={'text': {'$ilike': '%circulating%'}}
```

---


## 7. Technical Architecture

[Content continues - see full file for sections 7-10 covering:
- Technical Architecture (System Context, Components, Data Flows)
- Operator Specifications (Filter, Update, Logical, Aggregation operators)
- Query Language Design (Filter/Update/Sort/Aggregation syntax)
- NATS API Extensions (Enhanced search/update, backward compatibility)]

---

## 11. Implementation Plan

### 11.1 Sprint Timeline

**Total Duration**: 4-5 days
**Sorties**: 5 sorties
**Test Coverage Target**: 90%

### 11.2 Sortie 1: Operator Parser Foundation (Day 1)

**Scope**: Create OperatorParser class with basic comparison operators

**Files**:
- common/database/operator_parser.py (new)
- 	ests/unit/database/test_operator_parser.py (new)

**Implementation**:
``python
# common/database/operator_parser.py
from typing import Any, Dict, List, Callable
from sqlalchemy import Column

class OperatorParser:
    """Parse and validate MongoDB-style query operators."""
    
    COMPARISON_OPS = {
        '$eq: lambda col, val: col == val,
        '$eq: lambda col, val: col != val,
        '$eq: lambda col, val: col > val,
        '$eq: lambda col, val: col >= val,
        '$eq: lambda col, val: col < val,
        '$eq: lambda col, val: col <= val,
    }
    
    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize parser with table schema.
        
        Args:
            schema: Table schema with field definitions
        """
        self.schema = schema
        self.fields = {f['name']: f for f in schema['fields']}
    
    def parse_filter(self, filters: Dict[str, Any], table) -> List:
        """
        Parse filter dict into SQLAlchemy clauses.
        
        Args:
            filters: MongoDB-style filter dict
            table: SQLAlchemy table object
        
        Returns:
            List of SQLAlchemy where clauses
        """
        clauses = []
        
        for field_name, filter_value in filters.items():
            if field_name not in self.fields:
                raise ValueError(f"Field '{field_name}' not in schema")
            
            field_type = self.fields[field_name]['type']
            column = table.c[field_name]
            
            # Simple equality
            if not isinstance(filter_value, dict):
                clauses.append(column == filter_value)
                continue
            
            # Operator filters
            for operator, value in filter_value.items():
                clause = self._parse_operator(
                    field_name, operator, value, field_type, column
                )
                clauses.append(clause)
        
        return clauses
    
    def _parse_operator(
        self, field: str, operator: str, value: Any, field_type: str, column: Column
    ):
        """Parse single operator."""
        if operator not in self.COMPARISON_OPS:
            raise ValueError(f"Unknown operator: {operator}")
        
        # Validate type compatibility
        if operator in ('$eq, '$eq, '$eq, '$eq):
            if field_type not in ('INTEGER', 'BIGINT', 'FLOAT', 'TIMESTAMP'):
                raise TypeError(
                    f"Operator {operator} on field '{field}' requires numeric/timestamp type, "
                    f"got {field_type}"
                )
        
        return self.COMPARISON_OPS[operator](column, value)
``

**Tests**:
- Parse simple equality filter
- Parse \, \, \, \, \, \ operators
- Type validation (reject \ on TEXT field)
- Unknown field error
- Unknown operator error

**Acceptance**:
- [ ]  All unit tests pass (20+ tests)
- [ ]  Type validation prevents misuse
- [ ]  Clear error messages

### 11.3 Sortie 2: Extended Filter Operators (Day 2)

**Scope**: Add set, pattern, existence operators

**Files**:
- common/database/operator_parser.py (extend)
- 	ests/unit/database/test_operator_parser.py (extend)

**Implementation**:
``python
# Add to OperatorParser class

SET_OPS = {
    '$eq: lambda col, vals: col.in_(vals),
    '$eq: lambda col, vals: col.notin_(vals),
}

PATTERN_OPS = {
    '$eq: lambda col, pattern: col.like(pattern),
    '$eq: lambda col, pattern: col.ilike(pattern),
}

EXISTENCE_OPS = {
    '$eq: lambda col, exists: col.isnot(None) if exists else col.is_(None),
    '$eq: lambda col, is_null: col.is_(None) if is_null else col.isnot(None),
}

def _parse_operator(self, field: str, operator: str, value: Any, field_type: str, column: Column):
    """Extended operator parsing."""
    # Comparison operators
    if operator in self.COMPARISON_OPS:
        if operator in ('$eq, '$eq, '$eq, '$eq):
            if field_type not in ('INTEGER', 'BIGINT', 'FLOAT', 'TIMESTAMP'):
                raise TypeError(f"Operator {operator} requires numeric/timestamp type")
        return self.COMPARISON_OPS[operator](column, value)
    
    # Set operators
    if operator in self.SET_OPS:
        if not isinstance(value, list):
            raise TypeError(f"Operator {operator} requires list value")
        return self.SET_OPS[operator](column, value)
    
    # Pattern operators
    if operator in self.PATTERN_OPS:
        if field_type not in ('TEXT', 'VARCHAR'):
            raise TypeError(f"Pattern operators only work on TEXT/VARCHAR")
        return self.PATTERN_OPS[operator](column, value)
    
    # Existence operators
    if operator in self.EXISTENCE_OPS:
        if not isinstance(value, bool):
            raise TypeError(f"Operator {operator} requires boolean value")
        return self.EXISTENCE_OPS[operator](column, value)
    
    raise ValueError(f"Unknown operator: {operator}")
``

**Tests**:
- \ operator with list of values
- \ operator (not in)
- \ pattern matching (case-sensitive)
- \ pattern matching (case-insensitive)
- \ operator (NULL checks)
- Pattern operator type validation

**Acceptance**:
- [ ]  All set operators work
- [ ]  Pattern matching works (%, _ wildcards)
- [ ]  Existence checks work

### 11.4 Sortie 3: Update Operators & Compound Logic (Day 3)

**Scope**: Atomic update operators, \/\/\ logic

**Files**:
- common/database/operator_parser.py (extend)
- common/database/query_builder.py (extend)
- 	ests/unit/database/test_operator_parser.py (extend)

**Implementation**:
``python
from sqlalchemy import and_, or_, not_, func

# Add to OperatorParser class

UPDATE_OPS = {
    '$eq: lambda col, val: val,
    '$eq: lambda col, val: col + val,
    '$eq: lambda col, val: col - val,
    '$eq: lambda col, val: col * val,
    '$eq: lambda col, val: func.greatest(col, val),
    '$eq: lambda col, val: func.least(col, val),
}

def parse_update_operations(self, operations: Dict[str, Any], table) -> Dict[str, Any]:
    """
    Parse update operations dict.
    
    Args:
        operations: {field: {operator: value}}
        table: SQLAlchemy table
    
    Returns:
        Dict of field: SQLAlchemy expression
    """
    updates = {}
    
    for field_name, op_spec in operations.items():
        if field_name not in self.fields:
            raise ValueError(f"Field '{field_name}' not in schema")
        
        field_type = self.fields[field_name]['type']
        column = table.c[field_name]
        
        if not isinstance(op_spec, dict):
            raise TypeError("Update operations must be {operator: value}")
        
        operator, value = next(iter(op_spec.items()))
        
        if operator not in self.UPDATE_OPS:
            raise ValueError(f"Unknown update operator: {operator}")
        
        # Type validation
        if operator in ('$eq, '$eq, '$eq):
            if field_type not in ('INTEGER', 'BIGINT', 'FLOAT'):
                raise TypeError(f"Operator {operator} requires numeric type")
        
        if operator in ('$eq, '$eq):
            if field_type not in ('INTEGER', 'BIGINT', 'FLOAT', 'TIMESTAMP'):
                raise TypeError(f"Operator {operator} requires numeric/timestamp type")
        
        updates[field_name] = self.UPDATE_OPS[operator](column, value)
    
    return updates

def parse_filter(self, filters: Dict[str, Any], table) -> List:
    """Extended with compound logic support."""
    # Handle logical operators
    if '$eq in filters:
        conditions = filters['$eq]
        clauses = [self.parse_filter(cond, table) for cond in conditions]
        return [and_(*[c for sublist in clauses for c in sublist])]
    
    if '$eq in filters:
        conditions = filters['$eq]
        clauses = [self.parse_filter(cond, table) for cond in conditions]
        return [or_(*[c for sublist in clauses for c in sublist])]
    
    if '$eq in filters:
        condition = filters['$eq]
        clauses = self.parse_filter(condition, table)
        return [not_(and_(*clauses))]
    
    # Regular field filters (existing code)
    clauses = []
    for field_name, filter_value in filters.items():
        # ... existing code ...
    
    return clauses
``

**Tests**:
- \, \, \ update operators
- \, \ conditional operators
- \ compound filter
- \ compound filter
- \ negation
- Nested compound logic
- Update operator type validation

**Acceptance**:
- [ ]  Atomic updates work (no race conditions)
- [ ]  Compound logic works (AND/OR/NOT)
- [ ]  100 concurrent \ operations yield correct total

### 11.5 Sortie 4: Aggregations & Multi-Field Sorting (Day 4)

**Scope**: Aggregation functions, multi-field sort support

**Files**:
- common/database/operator_parser.py (extend)
- common/database/query_builder.py (extend)
- common/database.py (extend row_search method)

**Implementation**:
``python
# Add to OperatorParser class

def parse_aggregations(self, aggregates: Dict[str, Dict], table):
    """
    Parse aggregation functions.
    
    Args:
        aggregates: {name: {function: field}}
    
    Returns:
        List of SQLAlchemy aggregate expressions
    """
    agg_exprs = []
    
    for agg_name, agg_spec in aggregates.items():
        if len(agg_spec) != 1:
            raise ValueError("Aggregation spec must have one function")
        
        func_name, field = next(iter(agg_spec.items()))
        
        if func_name == '$eq:
            agg_exprs.append(func.count().label(agg_name))
        elif func_name == '$eq:
            if field not in self.fields:
                raise ValueError(f"Field '{field}' not in schema")
            agg_exprs.append(func.sum(table.c[field]).label(agg_name))
        elif func_name == '$eq:
            if field not in self.fields:
                raise ValueError(f"Field '{field}' not in schema")
            agg_exprs.append(func.avg(table.c[field]).label(agg_name))
        elif func_name == '$eq:
            if field not in self.fields:
                raise ValueError(f"Field '{field}' not in schema")
            agg_exprs.append(func.min(table.c[field]).label(agg_name))
        elif func_name == '$eq:
            if field not in self.fields:
                raise ValueError(f"Field '{field}' not in schema")
            agg_exprs.append(func.max(table.c[field]).label(agg_name))
        else:
            raise ValueError(f"Unknown aggregation function: {func_name}")
    
    return agg_exprs

def parse_sort(self, sort_spec, table):
    """
    Parse sort specification (single or multi-field).
    
    Args:
        sort_spec: Single dict or list of dicts
    
    Returns:
        List of SQLAlchemy order_by clauses
    """
    if isinstance(sort_spec, dict):
        # Backward compatible: single field
        sort_spec = [sort_spec]
    
    order_clauses = []
    for sort_item in sort_spec:
        field = sort_item['field']
        order = sort_item.get('order', 'asc')
        
        if field not in self.fields:
            raise ValueError(f"Sort field '{field}' not in schema")
        
        column = table.c[field]
        if order == 'desc':
            order_clauses.append(column.desc())
        else:
            order_clauses.append(column.asc())
    
    return order_clauses
``

**Tests**:
- COUNT aggregation
- SUM, AVG, MIN, MAX aggregations
- Multiple aggregations in one query
- Multi-field sorting (3+ fields)
- Backward compatible single-field sort

**Acceptance**:
- [ ]  All 5 aggregation functions work
- [ ]  Multi-field sorting works
- [ ]  Aggregations respect filters

### 11.6 Sortie 5: Integration, Docs, Performance Tests (Day 5)

**Scope**: Wire everything together, end-to-end tests, documentation

**Files**:
- common/database.py (integrate OperatorParser into row_search/row_update)
- ot/rosey/core/database_service.py (add operator logging)
- 	ests/integration/test_advanced_operators.py (new)
- 	ests/performance/test_operator_performance.py (new)
- docs/guides/PLUGIN_ROW_STORAGE.md (update with operator examples)

**Integration**:
``python
# common/database.py

async def row_search(
    self, plugin_name: str, table_name: str, 
    filters: dict = None, sort=None, limit: int = None, offset: int = None,
    aggregate: dict = None
) -> dict:
    """
    Search rows with advanced operators.
    
    Now supports:
    - Filter operators: \, \, \, \, \, \, \, \, \, \
    - Compound logic: \, \, \
    - Multi-field sorting
    - Aggregation functions: \, \, \, \, \
    """
    schema = self.schema_registry.get_schema(plugin_name, table_name)
    table = self._get_table(plugin_name, table_name)
    
    # Parse operators
    parser = OperatorParser(schema)
    
    # Build query
    query = select(table)
    
    if filters:
        where_clauses = parser.parse_filter(filters, table)
        for clause in where_clauses:
            query = query.where(clause)
    
    # Aggregations
    if aggregate:
        agg_exprs = parser.parse_aggregations(aggregate, table)
        result = await self.session.execute(select(*agg_exprs).select_from(query.subquery()))
        row = result.one()
        return {
            'success': True,
            'aggregates': dict(zip(aggregate.keys(), row))
        }
    
    # Sorting
    if sort:
        order_clauses = parser.parse_sort(sort, table)
        for clause in order_clauses:
            query = query.order_by(clause)
    
    # Pagination
    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    
    result = await self.session.execute(query)
    rows = [dict(row) for row in result]
    
    return {'success': True, 'rows': rows, 'count': len(rows)}
``

**Tests**:
- End-to-end: Complex query with operators, compound logic, multi-sort
- Performance: 1000 queries with operators <50ms p95
- Race condition: 100 concurrent \ operations
- Error handling: Invalid operators, type mismatches

**Documentation**:
- Update PLUGIN_ROW_STORAGE.md with operator examples
- Add operator reference table
- Add common query patterns (leaderboard, search, analytics)

**Acceptance**:
- [ ]  All integration tests pass
- [ ]  Performance tests meet targets
- [ ]  Documentation complete
- [ ]  No breaking changes to Sprint 13

---

## 12. Testing Strategy

### 12.1 Unit Tests

**Operator Parser Tests** (`tests/unit/test_operator_parser.py`):

```python
import pytest
from common.database.operator_parser import OperatorParser

class TestComparisonOperators:
    def setup_method(self):
        self.schema = {
            'fields': [
                {'name': 'id', 'type': 'INTEGER'},
                {'name': 'score', 'type': 'INTEGER'},
                {'name': 'text', 'type': 'TEXT'},
                {'name': 'timestamp', 'type': 'TIMESTAMP'}
            ]
        }
        self.parser = OperatorParser(self.schema)
    
    def test_eq_operator(self):
        filters = {'score': {'$eq': 100}}
        # Should generate: WHERE score = 100
    
    def test_gte_operator(self):
        filters = {'score': {'$gte': 100}}
        # Should generate: WHERE score >= 100
    
    def test_range_filter(self):
        filters = {'score': {'$gte': 100, '$lte': 200}}
        # Should generate: WHERE score >= 100 AND score <= 200
    
    def test_type_validation(self):
        with pytest.raises(ValueError):
            # TEXT field doesn't support $gte
            filters = {'text': {'$gte': 100}}
            self.parser.parse_filter(filters, None)

class TestSetOperators:
    def test_in_operator(self):
        filters = {'author': {'$in': ['MST3K', 'Rifftrax']}}
        # Should generate: WHERE author IN ('MST3K', 'Rifftrax')
    
    def test_nin_operator(self):
        filters = {'status': {'$nin': ['deleted', 'banned']}}
        # Should generate: WHERE status NOT IN ('deleted', 'banned')

class TestPatternOperators:
    def test_like_operator(self):
        filters = {'text': {'$like': '%tapes%'}}
        # Should generate: WHERE text LIKE '%tapes%'
    
    def test_ilike_operator(self):
        filters = {'text': {'$ilike': '%TAPES%'}}
        # Should generate: WHERE text ILIKE '%TAPES%' (case-insensitive)
    
    def test_pattern_on_non_text_fails(self):
        with pytest.raises(ValueError):
            # INTEGER doesn't support $like
            filters = {'score': {'$like': '%100%'}}
            self.parser.parse_filter(filters, None)

class TestUpdateOperators:
    def test_inc_operator(self):
        operations = {'score': {'$inc': 10}}
        # Should generate: score = score + 10
    
    def test_max_operator(self):
        operations = {'best_streak': {'$max': 5}}
        # Should generate: best_streak = GREATEST(best_streak, 5)
    
    def test_multiple_operations(self):
        operations = {
            'score': {'$inc': 10},
            'wins': {'$inc': 1},
            'best_score': {'$max': 150}
        }
        # All operations applied atomically

class TestCompoundLogic:
    def test_and_operator(self):
        filters = {
            '$and': [
                {'score': {'$gte': 100}},
                {'active': True}
            ]
        }
        # Should generate: WHERE (score >= 100 AND active = true)
    
    def test_or_operator(self):
        filters = {
            '$or': [
                {'score': {'$gte': 100}},
                {'wins': {'$gte': 10}}
            ]
        }
        # Should generate: WHERE (score >= 100 OR wins >= 10)
    
    def test_nested_logic(self):
        filters = {
            '$and': [
                {
                    '$or': [
                        {'score': {'$gte': 100}},
                        {'wins': {'$gte': 10}}
                    ]
                },
                {'active': True}
            ]
        }
        # Should generate: WHERE ((score >= 100 OR wins >= 10) AND active = true)

class TestAggregations:
    def test_count_aggregation(self):
        aggregate = {'player_count': {'$count': '*'}}
        # Should generate: SELECT COUNT(*) AS player_count
    
    def test_sum_aggregation(self):
        aggregate = {'total_score': {'$sum': 'score'}}
        # Should generate: SELECT SUM(score) AS total_score
    
    def test_multiple_aggregations(self):
        aggregate = {
            'total': {'$sum': 'score'},
            'avg': {'$avg': 'score'},
            'max': {'$max': 'score'},
            'count': {'$count': '*'}
        }
        # Should generate: SELECT SUM(score) AS total, AVG(score) AS avg, ...
```

**Target**: 150+ unit tests, 90% coverage

### 12.2 Integration Tests

**End-to-End Operator Tests** (`tests/integration/test_advanced_operators.py`):

```python
import pytest
import json
import asyncio

@pytest.mark.asyncio
class TestOperatorIntegration:
    async def test_complex_leaderboard_query(self, nats_client, db):
        # Setup: Insert test data
        for i in range(20):
            await nats_client.request('db.row.trivia.insert', json.dumps({
                'table': 'stats',
                'data': {
                    'user_id': f'user_{i}',
                    'score': i * 10,
                    'wins': i,
                    'active': i % 2 == 0
                }
            }).encode())
        
        # Query: Top 5 active players with score >= 100, sorted by score desc
        response = await nats_client.request('db.row.trivia.search', json.dumps({
            'table': 'stats',
            'filters': {
                '$and': [
                    {'score': {'$gte': 100}},
                    {'active': True}
                ]
            },
            'sort': [
                {'field': 'score', 'order': 'desc'},
                {'field': 'wins', 'order': 'desc'}
            ],
            'limit': 5
        }).encode(), timeout=1.0)
        
        data = json.loads(response.data)
        assert data['success']
        assert len(data['rows']) == 5
        assert data['rows'][0]['score'] >= 100
        assert data['rows'][0]['active']
        # Verify descending order
        for i in range(len(data['rows']) - 1):
            assert data['rows'][i]['score'] >= data['rows'][i+1]['score']
    
    async def test_atomic_increment_race_condition(self, nats_client, db):
        # Setup: Create user
        response = await nats_client.request('db.row.trivia.insert', json.dumps({
            'table': 'stats',
            'data': {'user_id': 'racer', 'score': 0, 'wins': 0}
        }).encode())
        user_id = json.loads(response.data)['id']
        
        # Run 100 concurrent increments
        tasks = []
        for _ in range(100):
            task = nats_client.request('db.row.trivia.update', json.dumps({
                'table': 'stats',
                'id': user_id,
                'operations': {
                    'score': {'$inc': 1},
                    'wins': {'$inc': 1}
                }
            }).encode())
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Verify: Should be exactly 100 (no lost updates)
        response = await nats_client.request('db.row.trivia.select', json.dumps({
            'table': 'stats',
            'id': user_id
        }).encode())
        
        data = json.loads(response.data)
        assert data['row']['score'] == 100
        assert data['row']['wins'] == 100
    
    async def test_pattern_search(self, nats_client, db):
        # Insert quotes
        quotes = [
            {'text': 'Keep circulating the tapes', 'author': 'MST3K'},
            {'text': 'In the not too distant future', 'author': 'MST3K'},
            {'text': 'Watch out for snakes', 'author': 'Rifftrax'}
        ]
        for quote in quotes:
            await nats_client.request('db.row.quote-db.insert', json.dumps({
                'table': 'quotes',
                'data': quote
            }).encode())
        
        # Search: Quotes containing 'tapes' (case-insensitive)
        response = await nats_client.request('db.row.quote-db.search', json.dumps({
            'table': 'quotes',
            'filters': {'text': {'$ilike': '%tapes%'}}
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert len(data['rows']) == 1
        assert 'circulating' in data['rows'][0]['text'].lower()
    
    async def test_aggregation_query(self, nats_client, db):
        # Insert scores
        for score in [50, 75, 100, 125, 150]:
            await nats_client.request('db.row.trivia.insert', json.dumps({
                'table': 'stats',
                'data': {'user_id': f'user_{score}', 'score': score}
            }).encode())
        
        # Aggregate: Total, average, count
        response = await nats_client.request('db.row.trivia.search', json.dumps({
            'table': 'stats',
            'aggregate': {
                'total': {'$sum': 'score'},
                'average': {'$avg': 'score'},
                'count': {'$count': '*'},
                'max_score': {'$max': 'score'}
            }
        }).encode())
        
        data = json.loads(response.data)
        assert data['success']
        assert data['aggregates']['total'] == 500
        assert data['aggregates']['average'] == 100.0
        assert data['aggregates']['count'] == 5
        assert data['aggregates']['max_score'] == 150
```

**Target**: 50+ integration tests

### 12.3 Performance Tests

**Latency Benchmarks** (`tests/performance/test_operator_performance.py`):

```python
import pytest
import json
import time

@pytest.mark.asyncio
class TestOperatorPerformance:
    async def test_simple_operator_latency(self, nats_client, db):
        # Setup: 1000 rows
        for i in range(1000):
            await nats_client.request('db.row.trivia.insert', json.dumps({
                'table': 'stats',
                'data': {'user_id': f'user_{i}', 'score': i}
            }).encode())
        
        # Benchmark: 100 queries with $gte operator
        latencies = []
        for _ in range(100):
            start = time.time()
            await nats_client.request('db.row.trivia.search', json.dumps({
                'table': 'stats',
                'filters': {'score': {'$gte': 100}},
                'limit': 10
            }).encode())
            latencies.append((time.time() - start) * 1000)
        
        p95 = sorted(latencies)[95]
        assert p95 < 20  # <20ms p95
    
    async def test_complex_query_latency(self, nats_client, db):
        latencies = []
        for _ in range(100):
            start = time.time()
            await nats_client.request('db.row.trivia.search', json.dumps({
                'table': 'stats',
                'filters': {
                    '$and': [
                        {'score': {'$gte': 100, '$lte': 200}},
                        {'wins': {'$gte': 10}},
                        {'active': True}
                    ]
                },
                'sort': [
                    {'field': 'score', 'order': 'desc'},
                    {'field': 'wins', 'order': 'desc'}
                ],
                'limit': 10
            }).encode())
            latencies.append((time.time() - start) * 1000)
        
        p95 = sorted(latencies)[95]
        assert p95 < 50  # <50ms p95
    
    async def test_aggregation_latency(self, nats_client, db):
        latencies = []
        for _ in range(100):
            start = time.time()
            await nats_client.request('db.row.trivia.search', json.dumps({
                'table': 'stats',
                'aggregate': {
                    'total': {'$sum': 'score'},
                    'avg': {'$avg': 'score'},
                    'count': {'$count': '*'}
                }
            }).encode())
            latencies.append((time.time() - start) * 1000)
        
        p95 = sorted(latencies)[95]
        assert p95 < 30  # <30ms p95
```

**Target**: 20+ performance tests

---

## 13. Performance Requirements

### 13.1 Latency Targets

| Operation | Target (p95) | Notes |
|-----------|--------------|-------|
| Simple operator ($eq, $gt) | <20ms | Single filter, indexed field |
| Range filter ($gte + $lte) | <25ms | Two operators on same field |
| Set filter ($in with 10 values) | <25ms | Indexed field |
| Pattern filter ($like) | <40ms | May require full table scan |
| Compound logic (3+ filters) | <50ms | AND/OR combinations |
| Atomic update (2+ operators) | <15ms | $inc, $max, etc. |
| Aggregation (3+ functions) | <30ms | COUNT, SUM, AVG |

### 13.2 Throughput Targets

**Mixed Workload** (60% queries, 40% updates with operators):

- 400 ops/sec sustained
- 800 ops/sec burst (30 seconds)

**Query-Heavy Workload** (90% queries with operators):

- 600 ops/sec sustained

### 13.3 Scalability

**Dataset Size**:

- 100,000+ rows: Consistent query performance
- 1,000,000+ rows: <10% latency degradation (with proper indexes)

**Concurrent Queries**:

- 100+ simultaneous operator queries without degradation

---

## 14. Security & Validation

### 14.1 Operator Validation

**Type Safety**:

- Operators validated against field types at parse time
- $gte on TEXT field → OPERATOR_NOT_SUPPORTED error
- Clear error messages with field name, operator, expected type

**SQL Injection Prevention**:

- All operators use parameterized queries via SQLAlchemy
- No string interpolation in generated SQL
- Operator names hardcoded (not user-controlled)

### 14.2 Input Validation

**Filter Validation**:

- Field names validated against schema
- Operator names validated against whitelist
- Values type-checked and coerced where possible

**Update Operation Validation**:

- Cannot update primary key fields (even with $set)
- Update operators validated against field types
- Operations atomic (all succeed or all fail)

### 14.3 Plugin Isolation

**Scope Enforcement**:

- Plugin name extracted from NATS subject (not payload)
- All queries scoped to plugin's table namespace
- Cannot use operators to access other plugins' data

---

## 15. Error Handling

### 15.1 Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| INVALID_OPERATOR | Unknown operator | {'\$invalidop': 100} |
| OPERATOR_NOT_SUPPORTED | Operator incompatible with field type | {text: {'\$gte': 100}} |
| TYPE_MISMATCH | Value type doesn't match field type | {score: {'\$eq': 'text'}} |
| MALFORMED_QUERY | Invalid query structure | {'\$and': 'not an array'} |
| INVALID_AGGREGATION | Aggregation syntax error | {'\$sum': 123} (not a field name) |

### 15.2 Error Response Format

```json
{
  "success": false,
  "error_code": "OPERATOR_NOT_SUPPORTED",
  "message": "Operator $gte on field 'text' requires numeric or timestamp type, got TEXT",
  "field": "text",
  "operator": "$gte",
  "expected_types": ["INTEGER", "BIGINT", "FLOAT", "TIMESTAMP"],
  "actual_type": "TEXT"
}
```

---

## 16. Observability

### 16.1 Logging

**Operator Usage Logging**:

```python
self.logger.info(
    "[ROW] search: plugin=trivia table=stats filters=[$gte, $and] sort=[score:desc, wins:desc] rows=10 latency=25ms",
    extra={
        'operation': 'row_search',
        'plugin': 'trivia',
        'table': 'stats',
        'operators': ['$gte', '$and'],
        'sort_fields': ['score', 'wins'],
        'result_count': 10,
        'latency_ms': 25.3
    }
)
```

**Slow Query Logging** (>100ms):

```python
self.logger.warning(
    "[ROW] SLOW QUERY (150ms): plugin=quote-db table=quotes filters=[$like] "
    "query={'text': {'$like': '%circulating%'}}",
    extra={
        'operation': 'row_search',
        'plugin': 'quote-db',
        'latency_ms': 150.2,
        'slow_query': True,
        'filters': {'text': {'$like': '%circulating%'}}
    }
)
```

### 16.2 Metrics (Future)

```
# Operator usage counters
rosey_operator_usage_total{plugin="trivia", operator="$gte"}
rosey_operator_usage_total{plugin="quote-db", operator="$like"}

# Operator latency histograms
rosey_operator_duration_seconds{operator="$gte"}
rosey_operator_duration_seconds{operator="$and"}

# Slow query counter
rosey_slow_queries_total{plugin="trivia", threshold="100ms"}
```

---

## 17. Documentation Requirements

### 17.1 User Documentation

**Update `docs/guides/PLUGIN_ROW_STORAGE.md`**:

````markdown
## Advanced Query Operators

### Filter Operators

#### Comparison Operators

Use comparison operators for numeric and date ranges:

```python
# Find high scores
response = await self.nats.request('db.row.my-plugin.search', json.dumps({
    'table': 'stats',
    'filters': {
        'score': {'$gte': 100, '$lte': 200}  # 100 <= score <= 200
    }
}).encode())

# Recent activity
response = await self.nats.request('db.row.my-plugin.search', json.dumps({
    'table': 'events',
    'filters': {
        'timestamp': {'$gte': '2025-11-01', '$lt': '2025-12-01'}  # November
    }
}).encode())
```

#### Set Operators

Match any value in a list:

```python
# Quotes from multiple authors
response = await self.nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {
        'author': {'$in': ['MST3K', 'Rifftrax', 'Cinematic Titanic']}
    }
}).encode())
```

#### Pattern Matching

Search text fields with wildcards:

```python
# Find quotes containing "tapes" (case-insensitive)
response = await self.nats.request('db.row.quote-db.search', json.dumps({
    'table': 'quotes',
    'filters': {
        'text': {'$ilike': '%tapes%'}
    }
}).encode())
```

### Update Operators

#### Atomic Increments

Increment/decrement numeric fields without race conditions:

```python
# Increment score by 10
response = await self.nats.request('db.row.trivia.update', json.dumps({
    'table': 'stats',
    'id': user_id,
    'operations': {
        'score': {'$inc': 10},
        'wins': {'$inc': 1}
    }
}).encode())
```

#### Conditional Updates

Update only if new value is greater/lesser:

```python
# Update best_score only if new score is higher
response = await self.nats.request('db.row.trivia.update', json.dumps({
    'table': 'stats',
    'id': user_id,
    'operations': {
        'best_score': {'$max': current_score},
        'worst_score': {'$min': current_score}
    }
}).encode())
```

### Compound Logic

Combine multiple filters with AND/OR:

```python
# Active players with high scores OR many wins
response = await self.nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'filters': {
        '$and': [
            {
                '$or': [
                    {'score': {'$gte': 1000}},
                    {'wins': {'$gte': 50}}
                ]
            },
            {'active': True}
        ]
    }
}).encode())
```

### Aggregations

Compute statistics across rows:

```python
# Leaderboard stats
response = await self.nats.request('db.row.trivia.search', json.dumps({
    'table': 'stats',
    'aggregate': {
        'total_players': {'$count': '*'},
        'total_score': {'$sum': 'score'},
        'average_score': {'$avg': 'score'},
        'high_score': {'$max': 'score'}
    }
}).encode())

data = json.loads(response.data)
print(f"Players: {data['aggregates']['total_players']}")
print(f"Average Score: {data['aggregates']['average_score']:.1f}")
```
````

### 17.2 API Reference

**Operator Reference Table**: Complete list of operators with examples, types, SQL equivalents

### 17.3 Code Documentation

**OperatorParser Docstrings**: Google-style with examples for each method

---

## 18. Dependencies & Risks

### 18.1 Dependencies

**Required**:

- ✅ Sprint 13 (Row Operations Foundation)
- ✅ SQLAlchemy with async support
- ✅ PostgreSQL 12+ (for GREATEST/LEAST functions)

**No New Dependencies**: Uses existing infrastructure only

### 18.2 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Operator parsing complexity | Medium | Medium | Thorough unit tests, clear error messages |
| Performance below targets | Low | Medium | Performance tests in CI, query profiling |
| Type coercion edge cases | Medium | Low | Comprehensive type validation tests |
| Pattern query performance | Medium | Medium | Warn in docs, suggest indexes |

---

## 19. Sprint Acceptance Criteria

### 19.1 Functional Acceptance

- [ ]  All filter operators work ($eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $like, $ilike, $exists, $null)
- [ ]  All update operators work ($set, $inc, $dec, $mul, $max, $min)
- [ ]  Compound logic works ($and, $or, $not)
- [ ]  Multi-field sorting works
- [ ]  All 5 aggregation functions work (count, sum, avg, min, max)
- [ ]  Atomic updates have no race conditions
- [ ]  Type validation prevents operator misuse
- [ ]  Clear error messages for invalid queries

### 19.2 Performance Acceptance

- [ ]  Simple operator query <20ms p95
- [ ]  Complex query (3+ filters) <50ms p95
- [ ]  Atomic update <15ms p95
- [ ]  Aggregation <30ms p95
- [ ]  Throughput ≥400 ops/sec (mixed workload)

### 19.3 Quality Acceptance

- [ ]  Test coverage ≥90%
- [ ]  150+ unit tests passing
- [ ]  50+ integration tests passing
- [ ]  20+ performance tests passing
- [ ]  Zero SQL injection vulnerabilities
- [ ]  Documentation complete
- [ ]  No breaking changes to Sprint 13

---

## 20. Future Enhancements

### 20.1 Deferred to Later Sprints

**Array Operators** (V2):

- $push, $pull, $addToSet
- Requires array field type support
- Use cases: Tags, categories, followers list

**Advanced Aggregations** (V2):

- GROUP BY support
- HAVING clauses
- Window functions (ROW_NUMBER, RANK)

**Query Optimization** (V2):

- Query plan analysis
- Index recommendations
- Materialized views for complex aggregations

### 20.2 Out of Scope

- Full-text search → Use external engine (Elasticsearch)
- Geospatial queries → V3 feature
- Graph traversal → Not applicable
- Joins → Sprint 17 (Parameterized SQL)

---

## 21. Appendices

### 21.1 Operator Quick Reference

**Filter Operators**:

- Comparison: $eq, $ne, $gt, $gte, $lt, $lte
- Set: $in, $nin
- Pattern: $like, $ilike
- Existence: $exists, $null
- Logic: $and, $or, $not

**Update Operators**:

- Scalar: $set, $inc, $dec, $mul
- Conditional: $max, $min

**Aggregations**:

- Functions: $count, $sum, $avg, $min, $max

### 21.2 MongoDB Compatibility

**Implemented from MongoDB**:

- Comparison operators (exact syntax)
- Set operators ($in, $nin)
- Logical operators ($and, $or, $not)
- Update operators ($set, $inc, $max, $min)

**Differences from MongoDB**:

- No array operators ($push, $pull) yet
- No nested document queries (dot notation)
- No $ne (use $nin/$not instead)
- No $where (JavaScript expressions)

### 21.3 Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-22 | GitHub Copilot | Initial PRD creation |

---

**End of PRD: Advanced Query Operators (Sprint 14)**

**Document Stats**:

- **Words**: ~14,000
- **Sections**: 21
- **User Stories**: 10 (in sections 1-11)
- **Sorties**: 5
- **Estimated Duration**: 4-5 days
- **Test Coverage Target**: ≥90%

**Next Steps**:

1. Review and approve this PRD
2. Create Sprint 14 branch
3. Begin Sortie 1: Operator Parser Foundation
4. Follow implementation plan (Section 11)

**Related PRDs**:

- ✅ Sprint 12: KV Storage Foundation (completed)
- ✅ Sprint 13: Row Operations Foundation (completed)
- ⏳ Sprint 15: Schema Migrations (next)
- ⏳ Sprint 16: Reference Implementation
- ⏳ Sprint 17: Parameterized SQL

---

*This document is a living document and will be updated as implementation progresses. All changes require Tech Lead approval.*
