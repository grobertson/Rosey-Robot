# Plugin Row Storage Guide

**Version**: 1.0  
**Last Updated**: November 24, 2025  
**Sprint**: 13 (Row Operations Foundation)

---

## Overview

The Row Storage System provides structured data persistence for Rosey plugins using a row-based database model. Each plugin gets isolated tables with schema validation, type coercion, and full CRUD + Search operations via NATS.

**Key Features:**
- Dynamic schema registration
- Type-safe operations with automatic coercion
- Plugin isolation (plugins cannot access each other's data)
- Full CRUD + Search operations
- Bulk operations for efficiency
- Pagination for large result sets
- NATS-based API (event bus integration)

---

## Quick Start

### 1. Register a Schema

Before storing data, register your table schema:

```python
import json
import nats

nc = await nats.connect("nats://localhost:4222")

# Register schema
response = await nc.request(
    "rosey.db.row.my-plugin.schema.register",
    json.dumps({
        "table": "quotes",
        "schema": {
            "fields": [
                {"name": "text", "type": "text", "required": True},
                {"name": "author", "type": "string", "required": False},
                {"name": "rating", "type": "integer", "required": False}
            ]
        }
    }).encode()
)

result = json.loads(response.data.decode())
if result['success']:
    print("Schema registered!")
```

### 2. Insert Data

```python
# Single insert
response = await nc.request(
    "rosey.db.row.my-plugin.insert",
    json.dumps({
        "table": "quotes",
        "data": {
            "text": "Hello world!",
            "author": "Alice",
            "rating": 5
        }
    }).encode()
)

result = json.loads(response.data.decode())
quote_id = result['id']  # Auto-generated ID

# Bulk insert
response = await nc.request(
    "rosey.db.row.my-plugin.insert",
    json.dumps({
        "table": "quotes",
        "data": [
            {"text": "Quote 1", "author": "Alice", "rating": 5},
            {"text": "Quote 2", "author": "Bob", "rating": 4},
            {"text": "Quote 3", "author": "Charlie", "rating": 3}
        ]
    }).encode()
)

result = json.loads(response.data.decode())
ids = result['ids']  # List of generated IDs
```

### 3. Retrieve Data

```python
# Select by ID
response = await nc.request(
    "rosey.db.row.my-plugin.select",
    json.dumps({
        "table": "quotes",
        "id": quote_id
    }).encode()
)

result = json.loads(response.data.decode())
if result['exists']:
    quote = result['data']
    print(f"Quote: {quote['text']} by {quote['author']}")
```

### 4. Update Data

```python
# Partial update (only fields you want to change)
response = await nc.request(
    "rosey.db.row.my-plugin.update",
    json.dumps({
        "table": "quotes",
        "id": quote_id,
        "data": {
            "rating": 4  # Only update rating
        }
    }).encode()
)

result = json.loads(response.data.decode())
if result['updated']:
    print("Quote updated!")
```

### 5. Search Data

```python
# Search with filters and sorting
response = await nc.request(
    "rosey.db.row.my-plugin.search",
    json.dumps({
        "table": "quotes",
        "filters": {"author": "Alice"},
        "sort": {"field": "rating", "order": "desc"},
        "limit": 10,
        "offset": 0
    }).encode()
)

result = json.loads(response.data.decode())
print(f"Found {result['count']} quotes")
for quote in result['rows']:
    print(f"  - {quote['text']} (rating: {quote['rating']})")

if result['truncated']:
    print("  More results available...")
```

### 6. Delete Data

```python
# Delete by ID
response = await nc.request(
    "rosey.db.row.my-plugin.delete",
    json.dumps({
        "table": "quotes",
        "id": quote_id
    }).encode()
)

result = json.loads(response.data.decode())
if result['deleted']:
    print("Quote deleted!")
```

---

## Field Types

The system supports the following field types with automatic type coercion:

| Type | SQL Type | Python Type | Examples |
|------|----------|-------------|----------|
| `string` | VARCHAR(255) | str | "Alice", "Hello" |
| `text` | TEXT | str | Long content, articles |
| `integer` | INTEGER | int | 42, -100, 0 |
| `float` | FLOAT | float | 3.14, -0.5, 100.0 |
| `boolean` | BOOLEAN | bool | True, False |
| `datetime` | TIMESTAMP | datetime | "2025-11-24T10:30:00Z" |

### Type Coercion Examples

The system automatically coerces values to match the schema:

```python
# String field
{"name": 123}  # Coerced to "123"

# Integer field
{"age": "42"}  # Coerced to 42
{"count": 3.9}  # Coerced to 3

# Boolean field
{"active": "true"}  # Coerced to True
{"enabled": 1}  # Coerced to True
{"visible": "off"}  # Coerced to False

# Datetime field
{"timestamp": "2025-11-24T10:30:00Z"}  # Parsed to datetime
{"created": "2025-11-24T10:30:00+05:30"}  # Parsed with timezone
```

---

## Auto-Generated Fields

Every table automatically includes these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `created_at` | TIMESTAMP | When row was created (UTC) |
| `updated_at` | TIMESTAMP | When row was last updated (UTC) |

**Note:** These fields are **immutable** - you cannot modify `id` or `created_at`. The `updated_at` field is automatically set on every update.

---

## API Reference

### Schema Registration

**Subject**: `rosey.db.row.{plugin}.schema.register`

**Request**:
```json
{
    "table": "table_name",
    "schema": {
        "fields": [
            {
                "name": "field_name",
                "type": "string|text|integer|float|boolean|datetime",
                "required": true|false
            }
        ]
    }
}
```

**Response (Success)**:
```json
{
    "success": true
}
```

**Response (Error)**:
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Unsupported field type: invalid_type"
    }
}
```

---

### Insert

**Subject**: `rosey.db.row.{plugin}.insert`

**Request (Single)**:
```json
{
    "table": "table_name",
    "data": {
        "field1": "value1",
        "field2": 42
    }
}
```

**Request (Bulk)**:
```json
{
    "table": "table_name",
    "data": [
        {"field1": "value1"},
        {"field1": "value2"},
        {"field1": "value3"}
    ]
}
```

**Response (Single)**:
```json
{
    "success": true,
    "id": 42,
    "created": true
}
```

**Response (Bulk)**:
```json
{
    "success": true,
    "ids": [42, 43, 44],
    "created": 3
}
```

---

### Select

**Subject**: `rosey.db.row.{plugin}.select`

**Request**:
```json
{
    "table": "table_name",
    "id": 42
}
```

**Response (Found)**:
```json
{
    "success": true,
    "exists": true,
    "data": {
        "id": 42,
        "field1": "value1",
        "created_at": "2025-11-24T10:30:00Z",
        "updated_at": "2025-11-24T10:30:00Z"
    }
}
```

**Response (Not Found)**:
```json
{
    "success": true,
    "exists": false
}
```

---

### Update

**Subject**: `rosey.db.row.{plugin}.update`

**Request**:
```json
{
    "table": "table_name",
    "id": 42,
    "data": {
        "field1": "new_value"
    }
}
```

**Response (Updated)**:
```json
{
    "success": true,
    "id": 42,
    "updated": true
}
```

**Response (Not Found)**:
```json
{
    "success": true,
    "exists": false
}
```

---

### Delete

**Subject**: `rosey.db.row.{plugin}.delete`

**Request**:
```json
{
    "table": "table_name",
    "id": 42
}
```

**Response**:
```json
{
    "success": true,
    "deleted": true
}
```

**Note:** Delete is idempotent - deleting a non-existent row returns `{"deleted": false}` without error.

---

### Search

**Subject**: `rosey.db.row.{plugin}.search`

**Request**:
```json
{
    "table": "table_name",
    "filters": {
        "field1": "value1",
        "field2": 42
    },
    "sort": {
        "field": "created_at",
        "order": "desc"
    },
    "limit": 100,
    "offset": 0
}
```

**All parameters are optional**:
- `filters`: Field equality filters (AND logic)
- `sort`: Single-field sorting (asc/desc)
- `limit`: Max rows (default 100, max 1000)
- `offset`: Pagination offset (default 0)

**Response**:
```json
{
    "success": true,
    "rows": [
        {"id": 42, "field1": "value1", ...},
        {"id": 43, "field1": "value2", ...}
    ],
    "count": 2,
    "truncated": false
}
```

**`truncated`**: `true` if more rows exist beyond the limit.

---

## Best Practices

### 1. Schema Design

**Do:**
- Keep schemas simple and focused
- Use appropriate field types
- Mark rarely-used fields as optional (`required: false`)
- Use `text` for long content, `string` for short identifiers

**Don't:**
- Create overly complex schemas
- Use `string` for large content (use `text`)
- Store binary data (not supported)

### 2. Bulk Operations

Always use bulk insert for multiple rows:

```python
# ❌ Don't do this
for item in items:
    await nc.request("rosey.db.row.plugin.insert", ...)

# ✅ Do this
await nc.request("rosey.db.row.plugin.insert", json.dumps({
    "table": "items",
    "data": items
}).encode())
```

### 3. Pagination

Always paginate large result sets:

```python
# ✅ Good
limit = 100
offset = 0
while True:
    result = await search(limit=limit, offset=offset)
    process(result['rows'])
    if not result['truncated']:
        break
    offset += limit
```

### 4. Error Handling

Always check the `success` field:

```python
result = json.loads(response.data.decode())
if not result['success']:
    error = result['error']
    print(f"Error {error['code']}: {error['message']}")
    return

# Process successful result
data = result['data']
```

### 5. Plugin Isolation

**Never** try to access another plugin's tables:

```python
# ❌ This will fail
await nc.request("rosey.db.row.other-plugin.select", ...)

# ✅ Only access your own plugin's tables
await nc.request("rosey.db.row.my-plugin.select", ...)
```

---

## Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `INVALID_JSON` | Malformed JSON request | Fix JSON syntax |
| `MISSING_FIELD` | Required field missing | Add missing field |
| `VALIDATION_ERROR` | Data validation failed | Check schema/data types |
| `DATABASE_ERROR` | Database operation failed | Retry or contact support |
| `INTERNAL_ERROR` | Unexpected server error | Contact support |

---

## Performance Tips

### Insert Performance

- **Single insert**: ~5ms p95
- **Bulk insert (100 rows)**: ~50ms p95
- **Recommendation**: Use bulk insert for 10+ rows

### Search Performance

- **Select by ID**: ~2ms p95
- **Search with filter**: ~20ms p95 (small tables)
- **Search with pagination**: ~25ms p95

**Tips:**
1. Use filters to reduce result set size
2. Always use `limit` for large tables
3. Consider caching frequently-accessed data

---

## Examples

### Example 1: Quote Database

```python
# Register schema
await nc.request(
    "rosey.db.row.quote_db.schema.register",
    json.dumps({
        "table": "quotes",
        "schema": {
            "fields": [
                {"name": "text", "type": "text", "required": True},
                {"name": "author", "type": "string", "required": False},
                {"name": "category", "type": "string", "required": False}
            ]
        }
    }).encode()
)

# Insert quotes
await nc.request(
    "rosey.db.row.quote_db.insert",
    json.dumps({
        "table": "quotes",
        "data": [
            {"text": "Life is beautiful", "author": "Anonymous", "category": "Life"},
            {"text": "Time flies", "author": "Unknown", "category": "Time"}
        ]
    }).encode()
)

# Search by category
response = await nc.request(
    "rosey.db.row.quote_db.search",
    json.dumps({
        "table": "quotes",
        "filters": {"category": "Life"}
    }).encode()
)

quotes = json.loads(response.data.decode())['rows']
```

### Example 2: Task Manager

```python
# Register schema
await nc.request(
    "rosey.db.row.tasks.schema.register",
    json.dumps({
        "table": "tasks",
        "schema": {
            "fields": [
                {"name": "title", "type": "string", "required": True},
                {"name": "description", "type": "text", "required": False},
                {"name": "status", "type": "string", "required": True},
                {"name": "priority", "type": "integer", "required": True}
            ]
        }
    }).encode()
)

# Create task
response = await nc.request(
    "rosey.db.row.tasks.insert",
    json.dumps({
        "table": "tasks",
        "data": {
            "title": "Fix bug",
            "description": "Fix the authentication bug",
            "status": "pending",
            "priority": 1
        }
    }).encode()
)

task_id = json.loads(response.data.decode())['id']

# Update status
await nc.request(
    "rosey.db.row.tasks.update",
    json.dumps({
        "table": "tasks",
        "id": task_id,
        "data": {"status": "completed"}
    }).encode()
)

# Get high priority tasks
response = await nc.request(
    "rosey.db.row.tasks.search",
    json.dumps({
        "table": "tasks",
        "filters": {"status": "pending"},
        "sort": {"field": "priority", "order": "asc"}
    }).encode()
)

tasks = json.loads(response.data.decode())['rows']
```

---

## Troubleshooting

### Schema Not Registered

**Error**: `Table 'quotes' not registered for plugin 'my-plugin'`

**Solution**: Register the schema first using `schema.register` before any operations.

### Type Mismatch

**Error**: `Cannot convert value to integer: 'abc'`

**Solution**: Ensure data types match schema definition. Use automatic type coercion where possible.

### Plugin Isolation Error

**Error**: `Table 'data' not registered for plugin 'plugin-b'`

**Solution**: Each plugin can only access its own tables. Use your plugin name in the NATS subject.

### Missing Required Field

**Error**: `Missing required field: username`

**Solution**: Provide all required fields when inserting data.

### Immutable Field Error

**Error**: `Cannot update immutable field: id`

**Solution**: Do not include `id` or `created_at` in update data. These fields are immutable.

---

## Migration Guide

### From KV Storage

If you're migrating from the KV storage system:

**KV Storage** (key-value pairs):
```python
await nc.request("rosey.db.kv.set", json.dumps({
    "plugin_name": "my-plugin",
    "key": "quote:1",
    "value": {"text": "Hello", "author": "Alice"}
}).encode())
```

**Row Storage** (structured tables):
```python
# Register schema once
await nc.request("rosey.db.row.my-plugin.schema.register", ...)

# Insert structured data
await nc.request("rosey.db.row.my-plugin.insert", json.dumps({
    "table": "quotes",
    "data": {"text": "Hello", "author": "Alice"}
}).encode())
```

**Benefits of Row Storage:**
- Type validation and coercion
- Relational queries (filters, sorting)
- Pagination for large datasets
- Auto-generated IDs and timestamps

---

## Limitations

### Current Limitations

1. **No joins**: Cannot query across multiple tables
2. **Equality filters only**: No range queries (>, <, BETWEEN)
3. **Single-field sorting**: Cannot sort by multiple fields
4. **No full-text search**: Use exact matches only
5. **No transactions**: Operations are atomic but not transactional
6. **No schema migrations**: Changing schemas requires manual migration

### Future Features (Planned)

- Sprint 15: Schema migrations and versioning
- Sprint 16: Indexes and compound keys
- Sprint 17: Range filters and LIKE queries
- Sprint 18: Multi-table joins
- Sprint 19: Full-text search

---

## Additional Resources

- [Architecture Documentation](../ARCHITECTURE.md) - System architecture
- [Testing Guide](../TESTING.md) - How to test with row storage
- [API Source Code](../../common/database.py) - Implementation details
- [Example Plugins](../../examples/) - Complete plugin examples

---

**Need Help?**

- Check the [troubleshooting section](#troubleshooting)
- Review [examples](#examples)
- See [error codes](#error-codes)
- Open an issue on GitHub

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Sprint**: 13 (Row Operations Foundation) ✅ Complete
