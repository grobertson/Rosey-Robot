# Quote-DB Plugin

**Reference implementation demonstrating Rosey storage API usage**

The quote-db plugin is a comprehensive example showing how to build stateful plugins using Rosey's modern storage architecture. It demonstrates:

- **Row Operations** for CRUD (insert, select, update, delete)
- **Advanced Operators** for search and atomic updates ($like, $inc, $max)
- **KV Storage** for counters and feature flags
- **Schema Migrations** for version-controlled database evolution

This plugin serves as the canonical reference for migrating legacy plugins from direct SQLite access to the modern storage API.

## Features

- **Add Quotes**: Store quotes with author, text, timestamps
- **Get Quotes**: Retrieve by ID or search by criteria
- **Score Quotes**: Rate quotes with atomic score updates
- **Tag Quotes**: Categorize with JSON tags
- **Statistics**: Track total quotes, top authors, high scores

## Installation

```bash
cd plugins/quote-db
pip install -r requirements.txt
```

## Schema Migrations

The quote-db plugin uses versioned SQL migrations to manage its database schema. Migrations must be applied before the plugin can be used.

### Applying Migrations

**Via Python**:
```python
import nats
import json

nc = await nats.connect("nats://localhost:4222")

# Check current status
response = await nc.request(
    "rosey.db.migrate.quote-db.status",
    json.dumps({}).encode()
)
print(json.loads(response.data))

# Apply all pending migrations
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({}).encode()
)
print(json.loads(response.data))
```

**Via NATS CLI**:
```bash
# Check migration status
nats req "rosey.db.migrate.quote-db.status" '{}'

# Apply all migrations
nats req "rosey.db.migrate.quote-db.apply" '{}'

# Apply up to specific version
nats req "rosey.db.migrate.quote-db.apply" '{"to_version": 2}'
```

### Migration Files

- **001_create_quotes_table.sql**: Initial schema (id, text, author, added_by, added_at)
- **002_add_score_column.sql**: Add scoring/rating capability
- **003_add_tags_column.sql**: Add JSON tags for categorization

### Rollback

```bash
# Rollback last migration
nats req "rosey.db.migrate.quote-db.rollback" '{"count": 1}'

# Rollback to specific version
nats req "rosey.db.migrate.quote-db.rollback" '{"to_version": 1}'
```

## Usage

### Initialization

```python
from quote_db import QuoteDBPlugin
from nats.aio.client import Client as NATS

# Connect to NATS
nc = await NATS().connect("nats://localhost:4222")

# Create plugin instance
plugin = QuoteDBPlugin(nc)

# Initialize (checks migrations are applied)
await plugin.initialize()
```

### Adding Quotes

```python
# Add a quote
quote_id = await plugin.add_quote(
    text="The only way to do great work is to love what you do.",
    author="Steve Jobs",
    added_by="alice"
)
print(f"Added quote {quote_id}")

# Author defaults to "Unknown" if empty
quote_id = await plugin.add_quote(
    text="Life is what you make it.",
    author="",  # Will be stored as "Unknown"
    added_by="bob"
)
```

### Retrieving Quotes

```python
# Get a quote by ID
quote = await plugin.get_quote(quote_id)
if quote:
    print(f"{quote['text']} - {quote['author']}")
    print(f"Score: {quote['score']}, Added by: {quote['added_by']}")
else:
    print("Quote not found")
```

### Deleting Quotes

```python
# Delete a quote
deleted = await plugin.delete_quote(quote_id)
if deleted:
    print("Quote deleted successfully")
else:
    print("Quote not found")
```

### Error Handling

```python
import asyncio

# Validation errors
try:
    await plugin.add_quote("", "Author", "alice")  # Empty text
except ValueError as e:
    print(f"Validation error: {e}")

try:
    await plugin.add_quote("x" * 1001, "Author", "alice")  # Text too long
except ValueError as e:
    print(f"Validation error: {e}")

try:
    await plugin.add_quote("Text", "x" * 101, "alice")  # Author too long
except ValueError as e:
    print(f"Validation error: {e}")

# NATS timeout errors
try:
    await plugin.add_quote("Text", "Author", "alice")
except asyncio.TimeoutError as e:
    print(f"NATS timeout: {e}")
```

### Commands

**Note**: Advanced operations (search, scoring, tagging) will be implemented in Sprint 16 Sortie 3.

```python
# Find by author
quotes = await plugin.find_by_author("MST3K")

# Increment score (atomic)
success = await plugin.increment_score(quote_id, amount=5)
```

## Development

### Running Tests

```bash
cd plugins/quote-db
pytest tests/ -v --cov=quote_db --cov-report=term-missing
```

### Project Structure

```
plugins/quote-db/
├── __init__.py              # Package exports
├── quote_db.py              # Main plugin implementation
├── requirements.txt         # Dependencies
├── README.md                # This file
├── migrations/              # Schema migrations
│   ├── 001_create_quotes_table.sql
│   ├── 002_add_score_column.sql
│   └── 003_add_tags_column.sql
└── tests/                   # Test suite
    ├── conftest.py          # Pytest fixtures
    ├── test_quote_db.py     # Plugin unit tests
    └── test_migrations.py   # Migration tests
```

## Architecture

### Storage API Usage

The quote-db plugin uses multiple storage tiers:

| Tier | Used For | Example |
|------|----------|---------|
| **Row Operations** | Quote CRUD (insert, select, update, delete) | `db.row.quote-db.insert` |
| **Advanced Operators** | Search (`$like`), atomic updates (`$inc`) | `{"author": {"$like": "%Alice%"}}` |
| **KV Storage** | Quote count cache, feature flags | `db.kv.quote-db.set("count", "42")` |
| **Migrations** | Schema versioning (CREATE TABLE, ADD COLUMN) | `db.migrate.quote-db.apply` |

### Data Flow

```
QuoteDBPlugin
    ↓ (NATS requests)
Database Service (database_service.py)
    ↓ (enforces plugin namespace)
SQLite/PostgreSQL Database
    ↓ (quote_db__quotes table)
Persistent Storage
```

### Plugin Isolation

All database operations are scoped to the `quote-db` namespace:
- Table names: `quote_db__quotes` (plugin prefix added automatically)
- KV keys: `quote-db:key_name` (namespace enforced by database service)
- Migrations: Tracked per-plugin in `_migrations` table

This ensures quote-db cannot access other plugins' data, and vice versa.

## Seed Data

Migration 001 inserts 5 example quotes for development and testing:

1. "The only way to do great work is to love what you do." - Steve Jobs
2. "In the middle of difficulty lies opportunity." - Albert Einstein
3. "Life is what happens when you're busy making other plans." - John Lennon
4. "The future belongs to those who believe in the beauty of their dreams." - Eleanor Roosevelt
5. "It is during our darkest moments that we must focus to see the light." - Aristotle

## Documentation

- **[Plugin Migration Guide](../../docs/guides/PLUGIN_MIGRATIONS.md)** - Sprint 15 migration system docs
- **[Migration Best Practices](../../docs/guides/MIGRATION_BEST_PRACTICES.md)** - Patterns and anti-patterns
- **[NATS Message Reference](../../docs/NATS_MESSAGES.md)** - API schemas and error codes
- **[PRD](../../docs/sprints/active/16-reference-implementation-quote-db/PRD-Reference-Implementation-Quote-DB.md)** - Complete requirements

## Sprint Progress

- ✅ **Sortie 1**: Foundation & Migrations (COMPLETE)
- ✅ **Sortie 2**: Core CRUD Operations (COMPLETE - add, get, delete, validation)
- ⏳ **Sortie 3**: Advanced Features (search, scoring, tags, KV cache)
- ⏳ **Sortie 4**: Error Handling, Documentation, Polish

## Contributing

This plugin serves as the reference implementation for Rosey's storage API. When adding features:

1. Follow existing patterns (NATS requests, error handling)
2. Add comprehensive tests (unit + integration)
3. Update this README with new commands
4. Document any new storage tier usage

## License

Same as main Rosey project - see root LICENSE file.

---

**Version**: 1.0.0  
**Sprint**: 16 - Reference Implementation  
**Status**: Foundation Complete (Sortie 1)  
**Last Updated**: November 24, 2025
