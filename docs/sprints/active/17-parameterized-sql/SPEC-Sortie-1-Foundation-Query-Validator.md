# SPEC: Sortie 1 - Foundation: Query Validator & Parameter Binder

**Sprint**: 17-parameterized-sql  
**Sortie**: 1 of 5  
**Status**: Draft  
**Author**: Platform Team  
**Created**: November 24, 2025  
**Last Updated**: November 24, 2025

---

## 1. Overview

### 1.1 Purpose

Implement the foundational components for parameterized SQL execution:
- **Query Validator**: Parse and validate SQL queries for security and correctness
- **Parameter Binder**: Convert PostgreSQL-style `$N` placeholders to SQLite `?` syntax

These components form the **first line of defense** against SQL injection and are critical for the security posture of the entire SQL execution feature.

### 1.2 Scope

**In Scope**:
- Query parsing using `sqlparse` library
- Statement type detection (SELECT, INSERT, UPDATE, DELETE, DDL)
- Table name extraction and namespace validation
- Parameter placeholder validation ($1, $2, $3, ...)
- Parameter binding and type coercion
- Comprehensive validation error messages

**Out of Scope**:
- Query execution (Sortie 2)
- NATS handler integration (Sortie 3)
- Security audit testing (Sortie 4)
- User documentation (Sortie 5)

### 1.3 Dependencies

**Prerequisites**:
- Sprint 16 (Reference Implementation) complete
- `sqlparse` library available (add to requirements.txt)
- Existing database manager from Sprint 12-14

**Dependent Sorties**:
- Sortie 2 (Executor) depends on validation and binding from Sortie 1
- All subsequent sorties build on this foundation

### 1.4 Success Criteria

- [ ] Query validator rejects all dangerous operations (DROP, TRUNCATE, ALTER, PRAGMA)
- [ ] Namespace isolation enforced (plugins can only access own tables)
- [ ] Parameter binding converts $1, $2, $3 to ? placeholders correctly
- [ ] 50+ validation test cases pass
- [ ] 20+ parameter binding test cases pass
- [ ] Zero false positives (valid queries accepted)
- [ ] Zero false negatives (dangerous queries rejected)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-1: SQL Parsing**
- Parse SQL queries using `sqlparse` library
- Detect syntax errors and return clear error messages
- Extract statement type (SELECT, INSERT, UPDATE, DELETE, etc.)
- Extract table names from all clauses (FROM, JOIN, INTO, UPDATE)

**FR-2: Statement Type Validation**
- Allow: SELECT, INSERT, UPDATE, DELETE
- Reject: CREATE, DROP, ALTER, TRUNCATE, PRAGMA, ATTACH, DETACH
- Reject multiple statements (stacked queries)
- Error message explains why statement was rejected

**FR-3: Table Name Validation**
- Extract all table names from query
- Verify table names start with `{plugin}__` prefix
- Allow cross-plugin access for JOINs (configurable)
- Reject access to system tables (sqlite_*)

**FR-4: Parameter Validation**
- Detect all `$N` placeholders in query
- Verify parameter count matches placeholder count
- Validate placeholder numbers are sequential (warn if gaps)
- Reject inline string literals in WHERE clauses (security)

**FR-5: Parameter Binding**
- Replace `$1`, `$2`, `$3` with `?` placeholders
- Build parameter tuple matching placeholder order
- Type coercion: string, int, float, boolean, null
- Handle parameter reuse ($1 used multiple times)

### 2.2 Non-Functional Requirements

**NFR-1: Performance**
- Validation overhead < 5ms P95 for typical queries
- Parsing caching for repeated queries (optional optimization)
- No memory leaks during validation

**NFR-2: Security**
- Zero false negatives (all dangerous operations caught)
- Clear error messages don't leak schema information
- Validation logic auditable and well-documented

**NFR-3: Maintainability**
- Modular design (separate validator, binder classes)
- Comprehensive docstrings and type hints
- Validation rules clearly documented with security rationale

---

## 3. Design

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   SQL Validation Pipeline               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Input: query (str), params (list), plugin (str)        │
│                                                          │
│         ▼                                                │
│  ┌──────────────────────────────────────────┐          │
│  │  Step 1: QueryValidator                  │          │
│  │  • Parse SQL with sqlparse               │          │
│  │  • Extract statement type                │          │
│  │  • Validate statement type allowed       │          │
│  │  • Extract table names                   │          │
│  │  • Validate namespace access             │          │
│  └────────────┬─────────────────────────────┘          │
│               │                                          │
│               ▼                                          │
│  ┌──────────────────────────────────────────┐          │
│  │  Step 2: ParameterValidator              │          │
│  │  • Detect $N placeholders                │          │
│  │  • Count placeholders vs params          │          │
│  │  • Validate parameter types              │          │
│  │  • Check for inline literals             │          │
│  └────────────┬─────────────────────────────┘          │
│               │                                          │
│               ▼                                          │
│  ┌──────────────────────────────────────────┐          │
│  │  Step 3: ParameterBinder                 │          │
│  │  • Replace $N with ?                     │          │
│  │  • Build parameter tuple                 │          │
│  │  • Type coercion                         │          │
│  └────────────┬─────────────────────────────┘          │
│               │                                          │
│               ▼                                          │
│  Output: validated_query (str), bound_params (tuple)    │
│      OR ValidationError                                  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Component Design

#### 3.2.1 ValidationError Hierarchy

```python
class SQLValidationError(Exception):
    """Base class for SQL validation errors."""
    
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class SyntaxError(SQLValidationError):
    """SQL syntax is invalid."""
    pass


class ForbiddenStatementError(SQLValidationError):
    """Statement type not allowed (DDL, etc.)."""
    pass


class NamespaceViolationError(SQLValidationError):
    """Query accesses tables outside allowed namespace."""
    pass


class ParameterError(SQLValidationError):
    """Parameter count/format mismatch."""
    pass
```

#### 3.2.2 ValidationResult Dataclass

```python
from dataclasses import dataclass, field
from typing import List, Optional, Set
from enum import Enum


class StatementType(Enum):
    """SQL statement types."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    # Forbidden types
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    TRUNCATE = "TRUNCATE"
    PRAGMA = "PRAGMA"
    ATTACH = "ATTACH"
    DETACH = "DETACH"
    UNKNOWN = "UNKNOWN"


@dataclass
class ValidationResult:
    """Result of SQL query validation."""
    
    valid: bool
    """Whether the query passed validation."""
    
    statement_type: StatementType
    """Detected SQL statement type."""
    
    tables: Set[str] = field(default_factory=set)
    """Set of table names referenced in query."""
    
    placeholders: List[int] = field(default_factory=list)
    """List of $N placeholder numbers found (in order of appearance)."""
    
    warnings: List[str] = field(default_factory=list)
    """Non-fatal validation warnings."""
    
    error: Optional[SQLValidationError] = None
    """Validation error if valid=False."""
    
    normalized_query: Optional[str] = None
    """Query with normalized whitespace (for caching)."""
```

#### 3.2.3 QueryValidator Class

```python
import re
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML, DDL
from typing import Optional, Set, List


class QueryValidator:
    """
    Validates SQL queries for safety and correctness.
    
    Security Rules:
    1. Only SELECT, INSERT, UPDATE, DELETE allowed
    2. DDL (CREATE, DROP, ALTER) is forbidden
    3. PRAGMA, ATTACH, DETACH are forbidden
    4. Tables must match plugin namespace prefix
    5. System tables (sqlite_*) are forbidden
    6. Stacked queries (;) are forbidden
    """
    
    # Statement types allowed for execution
    ALLOWED_STATEMENTS = {StatementType.SELECT, StatementType.INSERT, 
                          StatementType.UPDATE, StatementType.DELETE}
    
    # Forbidden keywords (case-insensitive)
    FORBIDDEN_KEYWORDS = {'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 
                          'PRAGMA', 'ATTACH', 'DETACH', 'VACUUM', 
                          'REINDEX', 'ANALYZE'}
    
    # System table patterns
    SYSTEM_TABLE_PATTERN = re.compile(r'^sqlite_', re.IGNORECASE)
    
    def __init__(self, allow_cross_plugin: bool = False):
        """
        Initialize validator.
        
        Args:
            allow_cross_plugin: If True, allow JOINs across plugin namespaces
        """
        self.allow_cross_plugin = allow_cross_plugin
    
    def validate(
        self,
        query: str,
        plugin: str,
        params: Optional[List] = None
    ) -> ValidationResult:
        """
        Validate SQL query for safety and correctness.
        
        Args:
            query: SQL query string
            plugin: Plugin name (for namespace validation)
            params: Optional list of parameters (for count validation)
        
        Returns:
            ValidationResult with validation outcome
        
        Example:
            >>> validator = QueryValidator()
            >>> result = validator.validate(
            ...     "SELECT * FROM quote_db__quotes WHERE id = $1",
            ...     plugin="quote-db",
            ...     params=[42]
            ... )
            >>> result.valid
            True
            >>> result.statement_type
            StatementType.SELECT
        """
        params = params or []
        warnings = []
        
        # Step 1: Check for stacked queries (multiple statements)
        if self._has_stacked_queries(query):
            return ValidationResult(
                valid=False,
                statement_type=StatementType.UNKNOWN,
                error=ForbiddenStatementError(
                    "STACKED_QUERIES",
                    "Multiple SQL statements not allowed. Use separate requests.",
                    {"query_preview": query[:100]}
                )
            )
        
        # Step 2: Parse with sqlparse
        try:
            parsed = sqlparse.parse(query)
            if not parsed:
                return ValidationResult(
                    valid=False,
                    statement_type=StatementType.UNKNOWN,
                    error=SyntaxError("EMPTY_QUERY", "Query is empty or whitespace-only")
                )
            stmt = parsed[0]
        except Exception as e:
            return ValidationResult(
                valid=False,
                statement_type=StatementType.UNKNOWN,
                error=SyntaxError("PARSE_ERROR", f"Failed to parse SQL: {e}")
            )
        
        # Step 3: Detect statement type
        statement_type = self._detect_statement_type(stmt)
        
        # Step 4: Check for forbidden statements
        if statement_type not in self.ALLOWED_STATEMENTS:
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                error=ForbiddenStatementError(
                    "FORBIDDEN_STATEMENT",
                    f"{statement_type.value} statements are not allowed. "
                    f"Use migration system for schema changes.",
                    {"statement_type": statement_type.value}
                )
            )
        
        # Step 5: Check for forbidden keywords anywhere in query
        forbidden_found = self._find_forbidden_keywords(query)
        if forbidden_found:
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                error=ForbiddenStatementError(
                    "FORBIDDEN_KEYWORD",
                    f"Query contains forbidden keyword: {forbidden_found}",
                    {"keyword": forbidden_found}
                )
            )
        
        # Step 6: Extract and validate table names
        tables = self._extract_table_names(stmt)
        namespace_prefix = f"{plugin.replace('-', '_')}__"
        
        for table in tables:
            # Check system tables
            if self.SYSTEM_TABLE_PATTERN.match(table):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    error=NamespaceViolationError(
                        "SYSTEM_TABLE_ACCESS",
                        f"Access to system table '{table}' is forbidden",
                        {"table": table}
                    )
                )
            
            # Check namespace prefix
            if not self.allow_cross_plugin and not table.startswith(namespace_prefix):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    error=NamespaceViolationError(
                        "NAMESPACE_VIOLATION",
                        f"Table '{table}' not in plugin namespace. "
                        f"Expected prefix: '{namespace_prefix}'",
                        {"table": table, "expected_prefix": namespace_prefix}
                    )
                )
        
        # Step 7: Extract and validate placeholders
        placeholders = self._extract_placeholders(query)
        
        # Check placeholder count vs params
        if placeholders:
            max_placeholder = max(placeholders)
            if len(params) < max_placeholder:
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    placeholders=placeholders,
                    error=ParameterError(
                        "PARAM_COUNT_MISMATCH",
                        f"Query uses ${max_placeholder} but only {len(params)} params provided",
                        {"max_placeholder": max_placeholder, "params_provided": len(params)}
                    )
                )
            
            # Warn about gaps in placeholder sequence
            expected = set(range(1, max_placeholder + 1))
            actual = set(placeholders)
            missing = expected - actual
            if missing:
                warnings.append(
                    f"Placeholder gap detected: ${min(missing)} not used. "
                    f"This may indicate a bug."
                )
        
        # Step 8: Check for inline string literals (security warning)
        if self._has_inline_string_literals(stmt):
            warnings.append(
                "Query contains inline string literals. Consider using parameters "
                "for all values to prevent SQL injection."
            )
        
        # Validation passed
        return ValidationResult(
            valid=True,
            statement_type=statement_type,
            tables=tables,
            placeholders=placeholders,
            warnings=warnings,
            normalized_query=sqlparse.format(query, strip_whitespace=True)
        )
    
    def _has_stacked_queries(self, query: str) -> bool:
        """Check for multiple statements (SQL injection vector)."""
        # Remove string literals to avoid false positives
        clean_query = re.sub(r"'[^']*'", "''", query)
        clean_query = re.sub(r'"[^"]*"', '""', clean_query)
        # Check for semicolon not at end
        clean_query = clean_query.strip().rstrip(';')
        return ';' in clean_query
    
    def _detect_statement_type(self, stmt) -> StatementType:
        """Detect SQL statement type from parsed statement."""
        first_token = stmt.token_first(skip_ws=True, skip_cm=True)
        if first_token is None:
            return StatementType.UNKNOWN
        
        token_value = first_token.ttype
        token_str = first_token.value.upper()
        
        # Check by token type
        if token_value in (DML.SELECT,):
            return StatementType.SELECT
        elif token_value in (DML.INSERT,):
            return StatementType.INSERT
        elif token_value in (DML.UPDATE,):
            return StatementType.UPDATE
        elif token_value in (DML.DELETE,):
            return StatementType.DELETE
        
        # Check by keyword string
        type_map = {
            'SELECT': StatementType.SELECT,
            'INSERT': StatementType.INSERT,
            'UPDATE': StatementType.UPDATE,
            'DELETE': StatementType.DELETE,
            'CREATE': StatementType.CREATE,
            'DROP': StatementType.DROP,
            'ALTER': StatementType.ALTER,
            'TRUNCATE': StatementType.TRUNCATE,
            'PRAGMA': StatementType.PRAGMA,
            'ATTACH': StatementType.ATTACH,
            'DETACH': StatementType.DETACH,
        }
        return type_map.get(token_str, StatementType.UNKNOWN)
    
    def _find_forbidden_keywords(self, query: str) -> Optional[str]:
        """Check for forbidden keywords in query text."""
        # Tokenize and check each keyword token
        tokens = sqlparse.parse(query)[0].flatten()
        for token in tokens:
            if token.ttype in (Keyword, DDL) or token.ttype is None:
                word = token.value.upper()
                if word in self.FORBIDDEN_KEYWORDS:
                    return word
        return None
    
    def _extract_table_names(self, stmt) -> Set[str]:
        """Extract all table names from SQL statement."""
        tables = set()
        
        # Get table names from FROM, JOIN, INTO, UPDATE clauses
        from_seen = False
        for token in stmt.tokens:
            if token.ttype is Keyword and token.value.upper() in ('FROM', 'JOIN', 'INTO', 'UPDATE'):
                from_seen = True
            elif from_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        tables.add(self._get_table_name(identifier))
                elif isinstance(token, Identifier):
                    tables.add(self._get_table_name(token))
                elif token.ttype is not None and str(token.ttype) == 'Token.Name':
                    tables.add(token.value)
                from_seen = False
        
        return tables
    
    def _get_table_name(self, identifier) -> str:
        """Extract table name from Identifier (handles aliases)."""
        # Handle "table AS alias" or "table alias"
        if isinstance(identifier, Identifier):
            return identifier.get_real_name() or str(identifier)
        return str(identifier)
    
    def _extract_placeholders(self, query: str) -> List[int]:
        """Extract $N placeholder numbers from query."""
        matches = re.findall(r'\$(\d+)', query)
        return [int(m) for m in matches]
    
    def _has_inline_string_literals(self, stmt) -> bool:
        """Check for string literals in WHERE clause (security warning)."""
        for token in stmt.tokens:
            if isinstance(token, Where):
                where_str = str(token)
                # Check for quoted strings (not parameters)
                if re.search(r"'[^']+'" , where_str) or re.search(r'"[^"]+"', where_str):
                    # Exclude empty strings and parameter placeholders
                    if not re.match(r"^['\"]['\"]$", where_str):
                        return True
        return False
```

#### 3.2.4 ParameterBinder Class

```python
import re
from typing import Any, Tuple, List


class ParameterBinder:
    """
    Converts PostgreSQL-style $N placeholders to SQLite ? syntax.
    
    PostgreSQL uses $1, $2, $3 (1-indexed)
    SQLite uses ? (positional, order of appearance)
    
    This class handles the conversion and builds the parameter tuple.
    """
    
    PLACEHOLDER_PATTERN = re.compile(r'\$(\d+)')
    
    def bind(
        self,
        query: str,
        params: List[Any]
    ) -> Tuple[str, Tuple[Any, ...]]:
        """
        Convert PostgreSQL $N placeholders to SQLite ? placeholders.
        
        Args:
            query: SQL query with $1, $2, $3 placeholders
            params: List of parameter values (0-indexed in Python)
        
        Returns:
            Tuple of (sqlite_query, param_tuple)
        
        Raises:
            ParameterError: If parameter count mismatch
        
        Example:
            >>> binder = ParameterBinder()
            >>> q, p = binder.bind(
            ...     "SELECT * FROM t WHERE x = $1 AND y = $2",
            ...     ["alice", 42]
            ... )
            >>> q
            'SELECT * FROM t WHERE x = ? AND y = ?'
            >>> p
            ('alice', 42)
        """
        # Find all placeholders in order of appearance
        matches = list(self.PLACEHOLDER_PATTERN.finditer(query))
        
        if not matches:
            # No placeholders - return as-is
            return query, ()
        
        # Validate parameter indices
        placeholder_nums = [int(m.group(1)) for m in matches]
        max_placeholder = max(placeholder_nums)
        
        if max_placeholder > len(params):
            raise ParameterError(
                "PARAM_COUNT_MISMATCH",
                f"Query uses ${max_placeholder} but only {len(params)} params provided",
                {"max_placeholder": max_placeholder, "params_provided": len(params)}
            )
        
        # Build result query and parameter tuple
        result_query = query
        param_tuple = []
        
        # Replace in reverse order to preserve positions
        for match in reversed(matches):
            placeholder_num = int(match.group(1))
            start, end = match.span()
            result_query = result_query[:start] + '?' + result_query[end:]
        
        # Build params in order of appearance
        for match in matches:
            placeholder_num = int(match.group(1))
            param_tuple.append(params[placeholder_num - 1])  # $1 → index 0
        
        return result_query, tuple(param_tuple)
    
    def coerce_type(self, value: Any) -> Any:
        """
        Coerce Python types to SQLite-compatible types.
        
        Args:
            value: Python value
        
        Returns:
            SQLite-compatible value
        
        Type Mappings:
            - None → NULL
            - bool → int (0/1)
            - int → int
            - float → float
            - str → str
            - bytes → blob
            - datetime → ISO string
            - list/dict → JSON string
        """
        import json
        from datetime import datetime, date
        
        if value is None:
            return None
        elif isinstance(value, bool):
            return 1 if value else 0
        elif isinstance(value, (int, float, str, bytes)):
            return value
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, (list, dict)):
            return json.dumps(value)
        else:
            # Fallback: convert to string
            return str(value)
```

---

## 4. File Structure

```
lib/
└── db/
    ├── __init__.py              # Export public classes
    ├── sql_errors.py            # Error classes and ValidationResult
    ├── sql_validator.py         # QueryValidator class
    └── sql_parameter.py         # ParameterBinder class

tests/
└── unit/
    ├── test_sql_validator.py    # 50+ validator tests
    └── test_sql_parameter.py    # 20+ binder tests
```

---

## 5. Test Cases

### 5.1 QueryValidator Tests

**Statement Type Detection (10 tests)**:
- `test_detect_select` - SELECT statement recognized
- `test_detect_insert` - INSERT statement recognized
- `test_detect_update` - UPDATE statement recognized
- `test_detect_delete` - DELETE statement recognized
- `test_reject_create` - CREATE rejected
- `test_reject_drop` - DROP rejected
- `test_reject_alter` - ALTER rejected
- `test_reject_truncate` - TRUNCATE rejected
- `test_reject_pragma` - PRAGMA rejected
- `test_reject_attach` - ATTACH rejected

**Namespace Validation (10 tests)**:
- `test_valid_namespace` - Table with correct prefix accepted
- `test_invalid_namespace` - Table without prefix rejected
- `test_system_table_rejected` - sqlite_* tables rejected
- `test_cross_plugin_default_rejected` - Cross-plugin access rejected by default
- `test_cross_plugin_allowed_when_enabled` - Cross-plugin allowed when flag set
- `test_multiple_tables_valid` - All tables in JOIN have correct prefix
- `test_multiple_tables_one_invalid` - One invalid table rejects query
- `test_subquery_tables` - Tables in subqueries validated
- `test_cte_tables` - Tables in CTEs validated
- `test_alias_extraction` - Table aliases don't affect validation

**Stacked Query Detection (5 tests)**:
- `test_single_statement_allowed` - Single statement passes
- `test_semicolon_at_end_allowed` - Trailing semicolon allowed
- `test_stacked_queries_rejected` - Multiple statements rejected
- `test_semicolon_in_string_allowed` - Semicolon in string literal allowed
- `test_comment_with_semicolon_allowed` - Semicolon in comment allowed

**Placeholder Validation (10 tests)**:
- `test_placeholder_count_match` - Correct param count passes
- `test_placeholder_count_mismatch` - Too few params rejected
- `test_extra_params_allowed` - Extra params allowed (unused)
- `test_placeholder_reuse` - $1 used twice works
- `test_out_of_order_placeholders` - $2 before $1 works
- `test_placeholder_gap_warning` - Gap in sequence warns
- `test_no_placeholders` - Query without placeholders works
- `test_placeholder_in_string_ignored` - '$1' in string not counted
- `test_large_placeholder_numbers` - $99 works
- `test_zero_placeholder_rejected` - $0 rejected

**Security Tests (15 tests)**:
- `test_drop_table_rejected` - DROP TABLE blocked
- `test_drop_in_subquery_rejected` - DROP in subquery blocked
- `test_truncate_rejected` - TRUNCATE blocked
- `test_pragma_rejected` - PRAGMA blocked
- `test_attach_rejected` - ATTACH database blocked
- `test_inline_literal_warning` - String literal in WHERE warns
- `test_union_with_drop_rejected` - UNION with forbidden statement
- `test_comment_bypass_blocked` - /* DROP */ not executed
- `test_case_insensitive_detection` - DrOp, DROP, drop all blocked
- `test_newline_bypass_blocked` - DROP\nTABLE blocked
- `test_whitespace_bypass_blocked` - Excessive whitespace handled
- `test_nested_subquery_validation` - Deep nesting validated
- `test_cte_injection_blocked` - WITH clause validated
- `test_function_name_not_keyword` - COUNT, MAX not blocked
- `test_column_name_drop_allowed` - Column named "drop" allowed

### 5.2 ParameterBinder Tests

**Basic Binding (10 tests)**:
- `test_single_param` - One placeholder works
- `test_multiple_params` - Multiple placeholders work
- `test_no_params` - No placeholders returns empty tuple
- `test_param_order_preserved` - Order matches appearance
- `test_param_reuse_duplicated` - $1 twice = param twice in tuple
- `test_out_of_order_binding` - $2 before $1 binds correctly
- `test_large_param_count` - 20+ params work
- `test_placeholder_in_string_ignored` - '$1' in string not replaced
- `test_whitespace_around_placeholder` - $ 1 not matched
- `test_negative_placeholder_ignored` - $-1 not matched

**Type Coercion (10 tests)**:
- `test_coerce_none` - None stays None
- `test_coerce_bool_true` - True → 1
- `test_coerce_bool_false` - False → 0
- `test_coerce_int` - int unchanged
- `test_coerce_float` - float unchanged
- `test_coerce_str` - str unchanged
- `test_coerce_datetime` - datetime → ISO string
- `test_coerce_date` - date → ISO string
- `test_coerce_list` - list → JSON string
- `test_coerce_dict` - dict → JSON string

---

## 6. Implementation Checklist

### 6.1 Files to Create

- [ ] `lib/db/__init__.py` - Module init with exports
- [ ] `lib/db/sql_errors.py` - Error classes and ValidationResult
- [ ] `lib/db/sql_validator.py` - QueryValidator implementation
- [ ] `lib/db/sql_parameter.py` - ParameterBinder implementation
- [ ] `tests/unit/test_sql_validator.py` - Validator tests
- [ ] `tests/unit/test_sql_parameter.py` - Binder tests

### 6.2 Dependencies

- [ ] Add `sqlparse>=0.5.0` to requirements.txt

### 6.3 Acceptance Criteria

- [ ] All 50+ validator tests pass
- [ ] All 20+ binder tests pass
- [ ] No mypy type errors
- [ ] No ruff lint errors
- [ ] Code coverage > 95%
- [ ] All dangerous queries rejected (security audit)
- [ ] All valid queries accepted (no false positives)

---

## 7. Security Considerations

### 7.1 Attack Vectors Mitigated

| Attack | Mitigation |
|--------|------------|
| SQL Injection | Mandatory parameterization, no inline values |
| Stacked Queries | Semicolon detection blocks multiple statements |
| DDL Injection | Forbidden statement type validation |
| Namespace Escape | Prefix validation on all table names |
| System Table Access | sqlite_* pattern blocked |
| Comment Bypass | Full query parsing, not regex matching |
| Unicode Bypass | sqlparse handles Unicode correctly |

### 7.2 Security Audit Points

1. **Validator completeness**: All forbidden keywords listed?
2. **Table extraction accuracy**: All SQL clauses covered?
3. **Placeholder regex**: Edge cases handled?
4. **Error message safety**: No schema leakage?
5. **Encoding handling**: UTF-8, Unicode escapes?

---

## 8. Appendix: Example Queries

### 8.1 Valid Queries

```sql
-- Simple SELECT
SELECT * FROM quote_db__quotes WHERE id = $1

-- JOIN across tables (same plugin)
SELECT q.*, t.name FROM quote_db__quotes q
JOIN quote_db__tags t ON q.tag_id = t.id

-- Aggregation
SELECT author, COUNT(*) as count
FROM quote_db__quotes
GROUP BY author
ORDER BY count DESC
LIMIT $1

-- Subquery
SELECT * FROM quote_db__quotes
WHERE score > (SELECT AVG(score) FROM quote_db__quotes)

-- CTE
WITH top_authors AS (
    SELECT author FROM quote_db__quotes
    GROUP BY author HAVING COUNT(*) > 5
)
SELECT * FROM quote_db__quotes
WHERE author IN (SELECT author FROM top_authors)
```

### 8.2 Rejected Queries

```sql
-- DDL (rejected)
DROP TABLE quote_db__quotes;
CREATE TABLE quote_db__new (id INT);
ALTER TABLE quote_db__quotes ADD COLUMN x INT;

-- System table access (rejected)
SELECT * FROM sqlite_master;

-- Wrong namespace (rejected for plugin "quote-db")
SELECT * FROM user_db__users;

-- Stacked queries (rejected)
SELECT 1; DROP TABLE x;

-- PRAGMA (rejected)
PRAGMA table_info(quote_db__quotes);
```

---

**End of Specification**

