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

