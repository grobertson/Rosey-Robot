# SQL Migration Guide

**Migrating to Parameterized SQL in Rosey**  
**Version:** 1.0.0  
**Last Updated:** 2025-01-13

---

## Overview

This guide helps you migrate existing Rosey plugins from raw SQL string formatting to the secure parameterized SQL system.

---

## Why Migrate?

### Security Issues with Raw SQL

```python
# ⚠️ VULNERABLE TO SQL INJECTION
query = f"SELECT * FROM users WHERE name = '{user_input}'"
cursor.execute(query)

# If user_input = "'; DROP TABLE users;--"
# The query becomes:
# SELECT * FROM users WHERE name = ''; DROP TABLE users;--'
```

### Benefits of Parameterized SQL

- **SQL Injection Prevention**: Parameters never interpolated
- **Namespace Enforcement**: Automatic table access control
- **Audit Trail**: All queries logged automatically
- **Rate Limiting**: Built-in abuse prevention
- **Type Safety**: Proper parameter type handling
- **NATS Integration**: Distributed query execution

---

## Migration Steps

### Step 1: Identify Raw SQL

Search for SQL vulnerability patterns:

```python
# Common patterns to find:
f"SELECT * FROM {table} WHERE {column} = '{value}'"
"SELECT * FROM users WHERE id = " + str(user_id)
query.format(name=user_input)
f"INSERT INTO data VALUES ('{data}')"
```

### Step 2: Add Namespace Prefix

Update table names to use plugin prefix:

```python
# Before
"SELECT * FROM users WHERE id = ?"

# After (for plugin "my_plugin")
"SELECT * FROM my_plugin__users WHERE id = $1"
```

### Step 3: Convert to $N Parameters

Replace `?` placeholders with numbered `$N`:

```python
# Before (positional ?)
cursor.execute(
    "SELECT * FROM users WHERE name = ? AND active = ?",
    (name, True)
)

# After (numbered $N)
await client.select(
    "SELECT * FROM my_plugin__users WHERE name = $1 AND active = $2",
    [name, True]
)
```

### Step 4: Use SQLClient

Replace direct cursor operations:

```python
# Before
import sqlite3
conn = sqlite3.connect("rosey.db")
cursor = conn.cursor()
cursor.execute(query, params)
results = cursor.fetchall()

# After
from lib.storage import SQLClient
client = SQLClient(db_path="rosey.db", plugin="my_plugin")
results = await client.select(query, params)
```

---

## Common Migration Patterns

### SELECT Queries

```python
# Before
cursor.execute(f"SELECT * FROM quotes WHERE author = '{author}'")
rows = cursor.fetchall()

# After
results = await client.select(
    "SELECT * FROM quote_db__quotes WHERE author = $1",
    [author]
)
```

### INSERT Queries

```python
# Before
cursor.execute(
    f"INSERT INTO quotes (text, author) VALUES ('{text}', '{author}')"
)
conn.commit()
new_id = cursor.lastrowid

# After
new_id = await client.insert(
    "INSERT INTO quote_db__quotes (text, author) VALUES ($1, $2)",
    [text, author]
)
```

### UPDATE Queries

```python
# Before
cursor.execute(
    f"UPDATE quotes SET text = '{new_text}' WHERE id = {quote_id}"
)
conn.commit()

# After
affected = await client.update(
    "UPDATE quote_db__quotes SET text = $1 WHERE id = $2",
    [new_text, quote_id]
)
```

### DELETE Queries

```python
# Before
cursor.execute(f"DELETE FROM quotes WHERE id = {quote_id}")
conn.commit()

# After
deleted = await client.delete(
    "DELETE FROM quote_db__quotes WHERE id = $1",
    [quote_id]
)
```

### Dynamic WHERE Clauses

```python
# Before - Building query string
conditions = []
params = []
if name:
    conditions.append(f"name = '{name}'")
if status:
    conditions.append(f"status = '{status}'")
query = f"SELECT * FROM users WHERE {' AND '.join(conditions)}"

# After - Use numbered parameters
conditions = []
params = []
param_num = 1
if name:
    conditions.append(f"name = ${param_num}")
    params.append(name)
    param_num += 1
if status:
    conditions.append(f"status = ${param_num}")
    params.append(status)
    param_num += 1

query = f"SELECT * FROM my_plugin__users WHERE {' AND '.join(conditions)}"
results = await client.select(query, params)
```

### IN Clauses

```python
# Before - String formatting list
ids_str = ','.join(str(id) for id in ids)
cursor.execute(f"SELECT * FROM users WHERE id IN ({ids_str})")

# After - Generate placeholders
placeholders = ','.join(f'${i}' for i in range(1, len(ids) + 1))
query = f"SELECT * FROM my_plugin__users WHERE id IN ({placeholders})"
results = await client.select(query, ids)
```

### LIKE Patterns

```python
# Before - Vulnerable to injection
cursor.execute(f"SELECT * FROM users WHERE name LIKE '%{search}%'")

# After - Parameter with wildcards
search_pattern = f"%{search}%"
results = await client.select(
    "SELECT * FROM my_plugin__users WHERE name LIKE $1",
    [search_pattern]
)
```

---

## Table Migration

### Create Migration for Namespace

```python
# alembic/versions/xxx_add_namespace_prefix.py

def upgrade():
    # Rename tables to add namespace prefix
    op.rename_table('quotes', 'quote_db__quotes')
    op.rename_table('users', 'quote_db__users')
    
    # Update foreign key references if needed
    # ...

def downgrade():
    op.rename_table('quote_db__quotes', 'quotes')
    op.rename_table('quote_db__users', 'users')
```

### Update Indexes

```python
# Indexes also need namespace prefix
def upgrade():
    op.drop_index('idx_quotes_author')
    op.create_index(
        'idx_quote_db_quotes_author',
        'quote_db__quotes',
        ['author']
    )
```

---

## Async Migration

### Converting Sync to Async

```python
# Before - Synchronous
def get_quote(quote_id: int) -> dict:
    conn = sqlite3.connect("rosey.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# After - Asynchronous
async def get_quote(quote_id: int) -> dict | None:
    client = SQLClient(db_path="rosey.db", plugin="quote_db")
    results = await client.select(
        "SELECT * FROM quote_db__quotes WHERE id = $1",
        [quote_id]
    )
    return results[0] if results else None
```

### Handling Connection Management

```python
# Before - Manual connection management
class QuoteService:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
    
    def close(self):
        self.conn.close()

# After - Async context manager
class QuoteService:
    def __init__(self, db_path: str, plugin: str):
        self.client = SQLClient(db_path=db_path, plugin=plugin)
    
    async def get_quotes(self) -> list[dict]:
        return await self.client.select(
            "SELECT * FROM quote_db__quotes"
        )
```

---

## Error Handling Migration

### Update Exception Handling

```python
# Before
try:
    cursor.execute(query)
except sqlite3.Error as e:
    logger.error(f"Database error: {e}")

# After
from lib.storage import (
    SQLValidationError,
    NamespaceViolationError,
    RateLimitError,
    ExecutionError,
)

try:
    await client.select(query, params)
except NamespaceViolationError:
    logger.warning("Table access denied")
except RateLimitError as e:
    logger.warning(f"Rate limited, retry in {e.retry_after}s")
except SQLValidationError as e:
    logger.error(f"Invalid query: {e}")
except ExecutionError as e:
    logger.error(f"Execution failed: {e}")
```

---

## Testing Updates

### Update Test Fixtures

```python
# Before
@pytest.fixture
def db_connection():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE quotes (id INTEGER, text TEXT)")
    yield conn
    conn.close()

# After
@pytest.fixture
async def sql_client():
    client = SQLClient(db_path=":memory:", plugin="test")
    # Create table with namespace prefix
    await client._execute_raw(
        "CREATE TABLE test__quotes (id INTEGER, text TEXT)"
    )
    yield client
```

### Update Test Assertions

```python
# Before
def test_get_quote(db_connection):
    cursor = db_connection.cursor()
    cursor.execute("INSERT INTO quotes (text) VALUES ('test')")
    cursor.execute("SELECT * FROM quotes WHERE text = 'test'")
    assert cursor.fetchone() is not None

# After
@pytest.mark.asyncio
async def test_get_quote(sql_client):
    await sql_client.insert(
        "INSERT INTO test__quotes (text) VALUES ($1)",
        ["test"]
    )
    results = await sql_client.select(
        "SELECT * FROM test__quotes WHERE text = $1",
        ["test"]
    )
    assert len(results) == 1
```

---

## Checklist

Use this checklist when migrating a plugin:

- [ ] Identify all SQL queries in plugin code
- [ ] Add namespace prefix to all table names
- [ ] Convert `?` placeholders to `$N` format
- [ ] Replace raw cursor with SQLClient
- [ ] Convert sync functions to async
- [ ] Update error handling
- [ ] Create table migration for namespace
- [ ] Update indexes with namespace prefix
- [ ] Update test fixtures and assertions
- [ ] Run security tests against plugin
- [ ] Update plugin documentation

---

## Getting Help

If you encounter issues during migration:

1. Check the [Parameterized SQL Guide](PARAMETERIZED_SQL.md)
2. Review [SQL Best Practices](SQL_BEST_PRACTICES.md)
3. Run security tests: `pytest tests/security/ -v`
4. Check audit logs for query issues

---

## See Also

- [Parameterized SQL Guide](PARAMETERIZED_SQL.md) - Full API reference
- [SQL Best Practices](SQL_BEST_PRACTICES.md) - Tips and patterns
- [Testing Guide](TESTING.md) - Writing SQL tests
