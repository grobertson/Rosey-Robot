# SQL Best Practices

**Writing Secure and Efficient SQL for Rosey Plugins**  
**Version:** 1.0.0  
**Last Updated:** 2025-01-13

---

## Security Best Practices

### 1. Always Use Parameters

**Never** interpolate user data into SQL strings:

```python
# ❌ NEVER DO THIS
query = f"SELECT * FROM my_plugin__users WHERE name = '{user_input}'"

# ✅ ALWAYS DO THIS
results = await client.select(
    "SELECT * FROM my_plugin__users WHERE name = $1",
    [user_input]
)
```

### 2. Validate Input Before Querying

Even with parameterization, validate input:

```python
def get_user(user_id: str) -> dict:
    # Validate user_id is actually an integer
    try:
        validated_id = int(user_id)
    except ValueError:
        raise ValueError("Invalid user ID")
    
    return await client.select(
        "SELECT * FROM my_plugin__users WHERE id = $1",
        [validated_id]
    )
```

### 3. Use Least Privilege

Select only the columns you need:

```python
# ❌ Don't select everything
await client.select("SELECT * FROM my_plugin__users")

# ✅ Select specific columns
await client.select(
    "SELECT id, name, email FROM my_plugin__users"
)
```

### 4. Never Trust Dynamic Table Names

If you must use dynamic table names, validate against allowlist:

```python
ALLOWED_TABLES = frozenset(["users", "events", "settings"])

def get_table_data(table_name: str, plugin: str):
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table: {table_name}")
    
    # Now safe to use (still with namespace)
    full_table = f"{plugin}__{table_name}"
    return await client.select(f"SELECT * FROM {full_table}")
```

### 5. Handle Errors Gracefully

Don't expose error details to users:

```python
try:
    results = await client.select(query, params)
except SQLValidationError as e:
    # Log full error for debugging
    logger.error(f"Query failed: {e}", extra={"query": query})
    # Return generic message to user
    raise UserError("Unable to retrieve data")
```

---

## Performance Best Practices

### 1. Always Use LIMIT

Prevent unbounded result sets:

```python
# ❌ Potentially returns millions of rows
await client.select("SELECT * FROM my_plugin__events")

# ✅ Bounded result set
await client.select(
    "SELECT * FROM my_plugin__events ORDER BY created_at DESC LIMIT $1",
    [100]
)
```

### 2. Index Frequently Queried Columns

Create indexes for WHERE, JOIN, and ORDER BY columns:

```sql
-- Good indexes for common queries
CREATE INDEX idx_my_plugin_events_created_at 
ON my_plugin__events(created_at);

CREATE INDEX idx_my_plugin_events_user_id 
ON my_plugin__events(user_id);

-- Composite index for multi-column queries
CREATE INDEX idx_my_plugin_events_user_date 
ON my_plugin__events(user_id, created_at);
```

### 3. Use Covering Indexes

Include all needed columns in index to avoid table lookup:

```sql
-- Query: SELECT id, name FROM users WHERE email = ?
-- Covering index includes all needed columns
CREATE INDEX idx_my_plugin_users_email_covering 
ON my_plugin__users(email, id, name);
```

### 4. Batch Operations

Use batch inserts for bulk data:

```python
# ❌ Slow: Individual inserts
for item in items:
    await client.insert(
        "INSERT INTO my_plugin__data (value) VALUES ($1)",
        [item]
    )

# ✅ Fast: Batch insert
placeholders = ", ".join(
    f"(${i})" for i in range(1, len(items) + 1)
)
await client.insert(
    f"INSERT INTO my_plugin__data (value) VALUES {placeholders}",
    items
)
```

### 5. Use Appropriate Data Types

Choose efficient types:

```sql
-- ❌ Inefficient
CREATE TABLE my_plugin__flags (
    id INTEGER PRIMARY KEY,
    is_active TEXT,        -- "true"/"false" as text
    created_at TEXT        -- "2025-01-13 10:30:00"
);

-- ✅ Efficient  
CREATE TABLE my_plugin__flags (
    id INTEGER PRIMARY KEY,
    is_active INTEGER,     -- 0 or 1
    created_at TEXT        -- ISO 8601 format
);
```

---

## Query Patterns

### 1. Pagination

```python
async def get_paginated_events(page: int, page_size: int = 20):
    offset = (page - 1) * page_size
    return await client.select(
        """
        SELECT * FROM my_plugin__events 
        ORDER BY created_at DESC 
        LIMIT $1 OFFSET $2
        """,
        [page_size, offset]
    )
```

### 2. Search with LIKE

```python
async def search_users(term: str):
    # Add wildcards to the parameter, not the query
    search_pattern = f"%{term}%"
    return await client.select(
        "SELECT * FROM my_plugin__users WHERE name LIKE $1 LIMIT $2",
        [search_pattern, 100]
    )
```

### 3. Conditional Updates

```python
async def update_if_exists(item_id: int, new_value: str):
    affected = await client.update(
        """
        UPDATE my_plugin__items 
        SET value = $1, updated_at = $2
        WHERE id = $3
        """,
        [new_value, datetime.now().isoformat(), item_id]
    )
    return affected > 0  # True if item existed
```

### 4. Upsert Pattern

```python
async def upsert_setting(key: str, value: str):
    # Try update first
    affected = await client.update(
        "UPDATE my_plugin__settings SET value = $1 WHERE key = $2",
        [value, key]
    )
    
    if affected == 0:
        # Insert if not exists
        await client.insert(
            "INSERT INTO my_plugin__settings (key, value) VALUES ($1, $2)",
            [key, value]
        )
```

### 5. Soft Delete

```python
async def soft_delete_user(user_id: int):
    await client.update(
        """
        UPDATE my_plugin__users 
        SET deleted_at = $1, active = $2 
        WHERE id = $3
        """,
        [datetime.now().isoformat(), False, user_id]
    )

async def get_active_users():
    return await client.select(
        "SELECT * FROM my_plugin__users WHERE deleted_at IS NULL"
    )
```

### 6. Aggregate Queries

```python
async def get_event_stats(user_id: int):
    results = await client.select(
        """
        SELECT 
            event_type,
            COUNT(*) as count,
            MAX(created_at) as last_occurrence
        FROM my_plugin__events 
        WHERE user_id = $1 
        GROUP BY event_type
        """,
        [user_id]
    )
    return results
```

---

## Common Anti-Patterns

### 1. N+1 Queries

```python
# ❌ N+1 problem: 1 query + N queries
users = await client.select("SELECT * FROM my_plugin__users")
for user in users:
    events = await client.select(
        "SELECT * FROM my_plugin__events WHERE user_id = $1",
        [user["id"]]
    )

# ✅ Single query with JOIN
results = await client.select(
    """
    SELECT u.*, e.event_type, e.created_at as event_time
    FROM my_plugin__users u
    LEFT JOIN my_plugin__events e ON u.id = e.user_id
    """
)
```

### 2. SELECT * in Production

```python
# ❌ Fetches all columns including blobs
await client.select("SELECT * FROM my_plugin__files")

# ✅ Fetch only needed columns
await client.select(
    "SELECT id, name, size, created_at FROM my_plugin__files"
)
```

### 3. String Concatenation in WHERE

```python
# ❌ Inefficient: Function on column prevents index use
await client.select(
    "SELECT * FROM my_plugin__users WHERE LOWER(name) = $1",
    [search_term.lower()]
)

# ✅ Use COLLATE NOCASE or store normalized
await client.select(
    "SELECT * FROM my_plugin__users WHERE name = $1 COLLATE NOCASE",
    [search_term]
)
```

### 4. Unbounded IN Clauses

```python
# ❌ IN with 10,000 values
ids = list(range(10000))
placeholders = ",".join(f"${i}" for i in range(1, len(ids) + 1))
await client.select(f"SELECT * FROM my_plugin__data WHERE id IN ({placeholders})", ids)

# ✅ Use temp table or batch queries
for batch in chunks(ids, 100):
    placeholders = ",".join(f"${i}" for i in range(1, len(batch) + 1))
    results = await client.select(
        f"SELECT * FROM my_plugin__data WHERE id IN ({placeholders})",
        batch
    )
```

---

## Transaction Patterns

### 1. All-or-Nothing Operations

```python
async def transfer_points(from_user: int, to_user: int, amount: int):
    async with client.transaction():
        # Deduct from sender
        await client.update(
            "UPDATE my_plugin__users SET points = points - $1 WHERE id = $2",
            [amount, from_user]
        )
        # Add to receiver
        await client.update(
            "UPDATE my_plugin__users SET points = points + $1 WHERE id = $2",
            [amount, to_user]
        )
        # Both succeed or both fail
```

### 2. Check-Then-Act

```python
async def claim_item(user_id: int, item_id: int):
    async with client.transaction():
        # Check availability
        items = await client.select(
            "SELECT * FROM my_plugin__items WHERE id = $1 AND claimed_by IS NULL",
            [item_id]
        )
        
        if not items:
            raise ItemNotAvailable()
        
        # Claim it
        await client.update(
            "UPDATE my_plugin__items SET claimed_by = $1, claimed_at = $2 WHERE id = $3",
            [user_id, datetime.now().isoformat(), item_id]
        )
```

---

## Testing SQL Code

### 1. Use In-Memory Database

```python
@pytest.fixture
async def test_client():
    client = SQLClient(db_path=":memory:", plugin="test")
    await client._execute_raw("""
        CREATE TABLE test__users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    """)
    return client
```

### 2. Test Edge Cases

```python
@pytest.mark.asyncio
async def test_empty_results(test_client):
    """Test handling of no results."""
    results = await test_client.select(
        "SELECT * FROM test__users WHERE id = $1",
        [999999]
    )
    assert results == []

@pytest.mark.asyncio  
async def test_special_characters(test_client):
    """Test handling of special characters in data."""
    await test_client.insert(
        "INSERT INTO test__users (name) VALUES ($1)",
        ["O'Reilly; DROP TABLE users;--"]
    )
    results = await test_client.select(
        "SELECT name FROM test__users WHERE name LIKE $1",
        ["%O'Reilly%"]
    )
    assert len(results) == 1
```

### 3. Test Error Conditions

```python
@pytest.mark.asyncio
async def test_invalid_table_access(test_client):
    """Test namespace enforcement."""
    with pytest.raises(NamespaceViolationError):
        await test_client.select("SELECT * FROM other_plugin__data")
```

---

## Monitoring and Debugging

### 1. Enable Query Logging

```python
import logging
logging.getLogger("lib.storage.sql_audit").setLevel(logging.DEBUG)
```

### 2. Check Query Metrics

```python
metrics = await client.get_query_metrics()
print(f"Total queries: {metrics.total_queries}")
print(f"Avg latency: {metrics.avg_latency_ms:.2f}ms")
print(f"Slowest query: {metrics.slowest_query_ms:.2f}ms")
```

### 3. Explain Query Plans

```python
# For debugging slow queries
plan = await client.select(
    "EXPLAIN QUERY PLAN SELECT * FROM my_plugin__users WHERE name = $1",
    ["test"]
)
print(plan)
```

---

## Summary Checklist

When writing SQL for Rosey plugins:

- [ ] All user data passed as parameters (`$1`, `$2`, etc.)
- [ ] Tables use correct namespace prefix (`plugin__table`)
- [ ] Queries have appropriate LIMIT clauses
- [ ] Frequently queried columns are indexed
- [ ] Only needed columns are selected
- [ ] Errors are handled gracefully
- [ ] Tests cover edge cases and error conditions
- [ ] Complex operations use transactions

---

## See Also

- [Parameterized SQL Guide](PARAMETERIZED_SQL.md) - Full API reference
- [SQL Migration Guide](SQL_MIGRATION_GUIDE.md) - Converting existing code
- [Testing Guide](TESTING.md) - Writing SQL tests
