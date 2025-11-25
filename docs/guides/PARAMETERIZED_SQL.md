# Parameterized SQL System

**Sprint 17: Parameterized SQL Implementation**  
**Version:** 1.0.0  
**Last Updated:** 2025-01-13

---

## Overview

The Parameterized SQL system provides a secure, high-performance SQL execution pipeline for Rosey plugins. It prevents SQL injection through strict parameterization, enforces namespace isolation, and provides comprehensive audit logging.

### Key Features

- **SQL Injection Prevention**: All user data passed as parameters, never interpolated
- **Namespace Isolation**: Plugins can only access their own tables (`{plugin}__*`)
- **Statement Restrictions**: Only SELECT, INSERT, UPDATE, DELETE allowed
- **Audit Logging**: Every query logged with execution metrics
- **Rate Limiting**: Per-plugin query quotas prevent abuse
- **NATS Integration**: Request/reply pattern for distributed execution

---

## Quick Start

### Basic Query Execution

```python
from lib.storage import SQLClient

# Create client
client = SQLClient(db_path="rosey.db", plugin="my_plugin")

# SELECT with parameters
results = await client.select(
    "SELECT * FROM my_plugin__users WHERE id = $1",
    [user_id]
)

# INSERT with returning
new_id = await client.insert(
    "INSERT INTO my_plugin__events (type, data) VALUES ($1, $2)",
    ["chat", json_data]
)

# UPDATE
affected = await client.update(
    "UPDATE my_plugin__users SET name = $1 WHERE id = $2",
    [new_name, user_id]
)

# DELETE
deleted = await client.delete(
    "DELETE FROM my_plugin__events WHERE created_at < $1",
    [cutoff_date]
)
```

### Via NATS Events

```python
import nats

nc = await nats.connect()

# Execute query via NATS
response = await nc.request(
    "rosey.sql.execute",
    json.dumps({
        "plugin": "my_plugin",
        "query": "SELECT * FROM my_plugin__data WHERE active = $1",
        "params": [True],
        "timeout_ms": 5000
    }).encode(),
    timeout=10.0
)

result = json.loads(response.data)
if result["success"]:
    rows = result["data"]["rows"]
```

---

## Parameter Syntax

### Placeholder Format

Use `$N` syntax for parameters, where N starts at 1:

```sql
-- Single parameter
SELECT * FROM my_plugin__users WHERE id = $1

-- Multiple parameters
SELECT * FROM my_plugin__data 
WHERE created_at > $1 AND status = $2

-- Repeated parameter (use same number)
SELECT * FROM my_plugin__data 
WHERE start_date = $1 OR end_date = $1
```

### Supported Parameter Types

| Python Type | SQLite Type | Example |
|-------------|-------------|---------|
| `int` | INTEGER | `42` |
| `float` | REAL | `3.14` |
| `str` | TEXT | `"hello"` |
| `bool` | INTEGER (0/1) | `True` |
| `None` | NULL | `None` |
| `bytes` | BLOB | `b"\x00\x01"` |
| `datetime` | TEXT (ISO) | `datetime.now()` |

---

## Table Naming Convention

All tables must use the plugin namespace prefix:

```
{plugin_name}__table_name
```

Where:
- Plugin name has hyphens replaced with underscores
- Double underscore `__` separates plugin from table name

### Examples

| Plugin | Table | Full Name |
|--------|-------|-----------|
| `quote-db` | `quotes` | `quote_db__quotes` |
| `markov` | `chains` | `markov__chains` |
| `my_plugin` | `users` | `my_plugin__users` |

### Invalid Tables (Blocked)

```sql
-- Missing namespace prefix
SELECT * FROM users  -- BLOCKED

-- Wrong plugin namespace
SELECT * FROM other_plugin__data  -- BLOCKED

-- System tables
SELECT * FROM sqlite_master  -- BLOCKED
```

---

## Statement Types

### Allowed Statements

| Statement | Description | Requires |
|-----------|-------------|----------|
| SELECT | Read data | - |
| INSERT | Create data | - |
| UPDATE | Modify data | - |
| DELETE | Remove data | - |

### Blocked Statements

| Statement | Reason |
|-----------|--------|
| CREATE | Use migration system |
| DROP | Use migration system |
| ALTER | Use migration system |
| TRUNCATE | Too dangerous |
| PRAGMA | Security risk |
| ATTACH | Security risk |

---

## Error Handling

### Error Types

```python
from lib.storage import (
    SQLValidationError,      # Base class
    SQLSyntaxError,          # Invalid SQL syntax
    ForbiddenStatementError, # DROP, CREATE, etc.
    NamespaceViolationError, # Wrong table prefix
    ParameterError,          # Param count mismatch
    StackedQueryError,       # Multiple statements
    ExecutionError,          # Runtime error
    TimeoutError,            # Query timeout
    RateLimitError,          # Quota exceeded
)
```

### Error Handling Example

```python
from lib.storage import SQLClient, NamespaceViolationError, RateLimitError

client = SQLClient(db_path="rosey.db", plugin="my_plugin")

try:
    results = await client.select(query, params)
except NamespaceViolationError as e:
    logger.warning(f"Plugin tried to access wrong table: {e}")
except RateLimitError as e:
    logger.warning(f"Rate limit exceeded: {e}")
    await asyncio.sleep(1)  # Back off
except SQLValidationError as e:
    logger.error(f"Query validation failed: {e}")
```

---

## Security Features

### SQL Injection Prevention

Parameters are **never** interpolated into SQL. The database driver uses prepared statements:

```python
# SAFE: Parameter passed separately
await client.select(
    "SELECT * FROM my_plugin__users WHERE name = $1",
    [user_input]  # Even "'; DROP TABLE users;--" is safe
)

# DANGEROUS: Never do this!
# query = f"SELECT * FROM users WHERE name = '{user_input}'"
```

### Namespace Isolation

Plugins are sandboxed to their own tables:

```python
# ✅ Valid: Plugin accesses own data
client = SQLClient(plugin="my_plugin")
await client.select("SELECT * FROM my_plugin__data")

# ❌ Blocked: Plugin tries to access other data  
await client.select("SELECT * FROM other_plugin__data")
# Raises NamespaceViolationError
```

### Stacked Query Prevention

Multiple statements are blocked:

```python
# ❌ Blocked
await client.select(
    "SELECT * FROM my_plugin__data; DROP TABLE my_plugin__data"
)
# Raises StackedQueryError
```

---

## Rate Limiting

### Default Limits

| Limit | Value | Window |
|-------|-------|--------|
| Default | 100 queries | 60 seconds |
| High Priority | 500 queries | 60 seconds |
| Background | 20 queries | 60 seconds |

### Handling Rate Limits

```python
from lib.storage import RateLimitError

try:
    await client.select(query, params)
except RateLimitError as e:
    logger.warning(f"Rate limited: {e.remaining} in {e.retry_after}s")
    await asyncio.sleep(e.retry_after)
```

### Check Remaining Quota

```python
status = await client.get_rate_status()
print(f"Remaining: {status.remaining}/{status.limit}")
print(f"Resets in: {status.reset_seconds}s")
```

---

## Audit Logging

Every query is logged with:

- Timestamp
- Plugin name
- Query hash (for grouping)
- Query preview (truncated)
- Parameter count
- Row count
- Execution time
- Success/failure status

### Log Format

```json
{
  "timestamp": "2025-01-13T10:30:00Z",
  "plugin": "my_plugin",
  "query_hash": "a1b2c3d4",
  "query_preview": "SELECT * FROM my_plugin__users WHERE...",
  "param_count": 2,
  "row_count": 10,
  "execution_time_ms": 1.5,
  "status": "success"
}
```

### Query Metrics

```python
# Get query performance metrics
metrics = await client.get_query_metrics()
print(f"Total queries: {metrics.total_queries}")
print(f"Avg latency: {metrics.avg_latency_ms:.2f}ms")
print(f"Cache hit rate: {metrics.cache_hit_rate:.1%}")
```

---

## Performance Tips

### Use Indexes

Create indexes on frequently queried columns:

```sql
-- In migration
CREATE INDEX idx_my_plugin_users_name 
ON my_plugin__users(name);
```

### Limit Results

Always use LIMIT for potentially large result sets:

```python
# Good: Limited results
await client.select(
    "SELECT * FROM my_plugin__events ORDER BY created_at DESC LIMIT $1",
    [100]
)

# Risky: Unbounded results
# await client.select("SELECT * FROM my_plugin__events")
```

### Use Projections

Select only needed columns:

```python
# Good: Specific columns
await client.select(
    "SELECT id, name FROM my_plugin__users WHERE active = $1",
    [True]
)

# Less efficient: All columns
# await client.select("SELECT * FROM my_plugin__users WHERE active = $1", [True])
```

---

## API Reference

### SQLClient

```python
class SQLClient:
    def __init__(
        self,
        db_path: str,
        plugin: str,
        timeout_ms: int = 5000,
    ): ...
    
    async def select(
        self,
        query: str,
        params: list[Any] = None,
    ) -> list[dict]: ...
    
    async def insert(
        self,
        query: str,
        params: list[Any] = None,
    ) -> int: ...  # Returns last_insert_id
    
    async def update(
        self,
        query: str,
        params: list[Any] = None,
    ) -> int: ...  # Returns rows_affected
    
    async def delete(
        self,
        query: str,
        params: list[Any] = None,
    ) -> int: ...  # Returns rows_affected
```

### QueryValidator

```python
class QueryValidator:
    def validate(
        self,
        query: str,
        plugin: str,
        params: list[Any] = None,
    ) -> ValidationResult: ...
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    valid: bool
    statement_type: StatementType
    tables: set[str]
    placeholders: list[int]
    warnings: list[str]
    error: Optional[SQLValidationError]
    normalized_query: Optional[str]
```

---

## See Also

- [SQL Migration Guide](SQL_MIGRATION_GUIDE.md) - Converting existing code
- [SQL Best Practices](SQL_BEST_PRACTICES.md) - Tips and patterns
- [Database Setup](DATABASE_SETUP.md) - Initial configuration
- [Testing Guide](TESTING.md) - Writing SQL tests
