# NATS Message Format Reference

**Purpose**: Complete reference for NATS message formats used by Rosey  
**Version**: 1.0  
**Last Updated**: November 24, 2025

---

## Overview

Rosey uses NATS as the central event bus for all inter-component communication. This document defines the message formats, request/response schemas, error codes, and examples for all NATS subjects.

### Subject Hierarchy

NATS subjects follow a hierarchical structure:

```text
rosey.{category}.{specifics}...

Examples:
- rosey.platform.cytube.message       # CyTube chat message
- rosey.events.message                # Normalized message (any platform)
- rosey.commands.trivia.execute       # Execute trivia command
- rosey.db.migrate.quote-db.apply     # Apply migrations for quote-db plugin
```

### Message Patterns

1. **Pub/Sub (Fire-and-Forget)**: Publisher sends message, subscribers receive it asynchronously
2. **Request/Reply**: Sender awaits response, synchronous operation with timeout

---

## Database Migration Messages

**Added**: Sprint 15 - Schema Migrations

Database migration handlers provide NATS-based migration management for plugins.

### Subject Format

```text
rosey.db.migrate.<plugin-name>.<operation>

Operations:
- apply      # Apply pending migrations
- rollback   # Rollback applied migrations
- status     # Get migration status
```

---

## db.migrate.<plugin>.apply

**Subject**: `rosey.db.migrate.<plugin-name>.apply`  
**Pattern**: Request/Reply  
**Purpose**: Apply pending migrations for a plugin

### Request Schema

```json
{
  "to_version": 5,      // Optional: Apply up to this version (omit to apply all)
  "dry_run": false      // Optional: Validate only, don't execute (default: false)
}
```

**Request Fields**:
- `to_version` (integer, optional): Maximum version to apply. Omit to apply all pending migrations.
- `dry_run` (boolean, optional): If `true`, validates SQL without executing. Default: `false`.

**Empty Request**: `{}` - Applies all pending migrations

### Success Response

```json
{
  "success": true,
  "migrations_applied": 3,
  "final_version": 5,
  "warnings": [
    "Migration 002 drops column 'deprecated_col' (data loss)",
    "Migration 004 deletes data from 'old_table'"
  ]
}
```

**Success Response Fields**:
- `success` (boolean): Always `true` for successful operations
- `migrations_applied` (integer): Number of migrations applied (0 if all up-to-date)
- `final_version` (integer): Current schema version after applying migrations
- `warnings` (array of strings): Validation warnings for destructive operations

### Error Response

```json
{
  "success": false,
  "error": "VALIDATION_FAILED",
  "message": "Migration 003 validation failed: SQLite does not support DROP COLUMN",
  "details": {
    "migration_version": 3,
    "migration_description": "drop_old_column",
    "validation_errors": [
      {
        "level": "ERROR",
        "message": "SQLite does not support DROP COLUMN directly",
        "line": 5,
        "suggestion": "Use table recreation pattern (see docs)"
      }
    ]
  }
}
```

**Error Response Fields**:
- `success` (boolean): Always `false` for errors
- `error` (string): Error code (see [Error Codes](#error-codes))
- `message` (string): Human-readable error message
- `details` (object, optional): Additional error context
  - `migration_version` (integer): Version number that failed
  - `migration_description` (string): Description of failed migration
  - `validation_errors` (array): Validation issues (ERROR level blocks execution)

### Example Usage

```python
import nats
import json

nc = await nats.connect("nats://localhost:4222")

# Apply all pending migrations
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({}).encode(),
    timeout=30.0  # 30 second timeout for long migrations
)

result = json.loads(response.data)

if result['success']:
    print(f"Applied {result['migrations_applied']} migrations")
    print(f"Schema version: {result['final_version']}")
    
    if result['warnings']:
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
else:
    print(f"Migration failed: {result['error']}")
    print(f"Message: {result['message']}")
    
    if 'validation_errors' in result.get('details', {}):
        for error in result['details']['validation_errors']:
            print(f"  [{error['level']}] {error['message']}")
```

### Dry-Run Mode

Validate migrations without executing:

```python
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({"dry_run": True}).encode(),
    timeout=10.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Would apply {result['migrations_applied']} migrations")
    if result['warnings']:
        print("Warnings that would occur:")
        for warning in result['warnings']:
            print(f"  - {warning}")
else:
    print(f"Validation failed: {result['message']}")
```

### Apply to Specific Version

```python
response = await nc.request(
    "rosey.db.migrate.quote-db.apply",
    json.dumps({"to_version": 3}).encode(),
    timeout=30.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Applied up to version {result['final_version']}")
```

---

## db.migrate.<plugin>.rollback

**Subject**: `rosey.db.migrate.<plugin-name>.rollback`  
**Pattern**: Request/Reply  
**Purpose**: Rollback applied migrations for a plugin

### Request Schema

```json
{
  "count": 1,           // Optional: Number of migrations to rollback (from newest)
  "to_version": 2,      // Optional: Rollback to this version (alternative to count)
  "dry_run": false      // Optional: Validate only, don't execute (default: false)
}
```

**Request Fields**:
- `count` (integer, optional): Number of migrations to roll back from the newest. Default: 1.
- `to_version` (integer, optional): Roll back to this version (alternative to `count`). Exclusive with `count`.
- `dry_run` (boolean, optional): If `true`, validates SQL without executing. Default: `false`.

**Mutual Exclusion**: Specify `count` OR `to_version`, not both.

### Success Response

```json
{
  "success": true,
  "migrations_rolled_back": 2,
  "final_version": 3,
  "warnings": [
    "Migration 005 rollback drops table 'new_feature' (data loss)",
    "Migration 004 rollback cannot fully restore original data"
  ]
}
```

**Success Response Fields**:
- `success` (boolean): Always `true` for successful operations
- `migrations_rolled_back` (integer): Number of migrations rolled back
- `final_version` (integer): Current schema version after rollback
- `warnings` (array of strings): Validation warnings for destructive rollbacks

### Error Response

```json
{
  "success": false,
  "error": "ROLLBACK_FAILED",
  "message": "Migration 004 rollback failed: no such table: old_table",
  "details": {
    "migration_version": 4,
    "migration_description": "rename_table",
    "sql_error": "no such table: old_table"
  }
}
```

**Error Response Fields**:
- `success` (boolean): Always `false` for errors
- `error` (string): Error code (see [Error Codes](#error-codes))
- `message` (string): Human-readable error message
- `details` (object, optional): Additional error context
  - `migration_version` (integer): Version that failed to roll back
  - `migration_description` (string): Description of failed migration
  - `sql_error` (string): Database error message

### Example Usage

```python
# Rollback single migration (most recent)
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"count": 1}).encode(),
    timeout=30.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Rolled back {result['migrations_rolled_back']} migrations")
    print(f"Schema version: {result['final_version']}")
    
    if result['warnings']:
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
else:
    print(f"Rollback failed: {result['message']}")
```

### Rollback to Version

```python
# Rollback to version 2 (rolls back 3, 4, 5 if currently at 5)
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"to_version": 2}).encode(),
    timeout=30.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Rolled back to version {result['final_version']}")
```

### Dry-Run Rollback

```python
response = await nc.request(
    "rosey.db.migrate.quote-db.rollback",
    json.dumps({"count": 1, "dry_run": True}).encode(),
    timeout=10.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Would rollback {result['migrations_rolled_back']} migrations")
    if result['warnings']:
        print("Warnings that would occur:")
        for warning in result['warnings']:
            print(f"  - {warning}")
```

---

## db.migrate.<plugin>.status

**Subject**: `rosey.db.migrate.<plugin-name>.status`  
**Pattern**: Request/Reply  
**Purpose**: Get current migration status for a plugin

### Request Schema

```json
{}
```

**Empty Request**: No parameters required

### Success Response

```json
{
  "success": true,
  "plugin_name": "quote-db",
  "current_version": 3,
  "available_version": 5,
  "pending_migrations": [
    {
      "version": 4,
      "description": "add_indexes",
      "checksum": "a3f8e9d...",
      "warnings": ["Creates 3 indexes (may take time on large tables)"]
    },
    {
      "version": 5,
      "description": "add_foreign_keys",
      "checksum": "b7c2a1f...",
      "warnings": ["Requires table recreation (SQLite limitation)"]
    }
  ],
  "applied_migrations": [
    {
      "version": 1,
      "description": "create_quotes_table",
      "checksum": "e4d5c6b...",
      "applied_at": "2025-11-24T10:00:00Z",
      "applied_by": "admin"
    },
    {
      "version": 2,
      "description": "add_category_column",
      "checksum": "f1a2b3c...",
      "applied_at": "2025-11-24T10:01:30Z",
      "applied_by": "admin"
    },
    {
      "version": 3,
      "description": "add_author_index",
      "checksum": "d9e8f7a...",
      "applied_at": "2025-11-24T10:02:15Z",
      "applied_by": "admin"
    }
  ]
}
```

**Success Response Fields**:
- `success` (boolean): Always `true` for successful operations
- `plugin_name` (string): Name of the plugin
- `current_version` (integer): Currently applied schema version (0 if no migrations applied)
- `available_version` (integer): Highest version available in migration files
- `pending_migrations` (array): Migrations not yet applied
  - `version` (integer): Migration version number
  - `description` (string): Migration description from filename
  - `checksum` (string): SHA-256 checksum (first 8 chars shown)
  - `warnings` (array of strings): Validation warnings for this migration
- `applied_migrations` (array): Migrations already applied
  - `version` (integer): Migration version number
  - `description` (string): Migration description
  - `checksum` (string): SHA-256 checksum
  - `applied_at` (string): ISO 8601 timestamp
  - `applied_by` (string): User who applied the migration

### Error Response

```json
{
  "success": false,
  "error": "CHECKSUM_MISMATCH",
  "message": "Migration 002 file has been modified (checksum mismatch)",
  "details": {
    "migration_version": 2,
    "migration_description": "add_category_column",
    "expected_checksum": "f1a2b3c4d5e6f7a8",
    "actual_checksum": "a8f7e6d5c4b3a2f1"
  }
}
```

**Error Response Fields**:
- `success` (boolean): Always `false` for errors
- `error` (string): Error code (see [Error Codes](#error-codes))
- `message` (string): Human-readable error message
- `details` (object, optional): Additional error context

### Example Usage

```python
response = await nc.request(
    "rosey.db.migrate.quote-db.status",
    json.dumps({}).encode(),
    timeout=5.0
)

result = json.loads(response.data)

if result['success']:
    print(f"Plugin: {result['plugin_name']}")
    print(f"Current version: {result['current_version']}")
    print(f"Available version: {result['available_version']}")
    
    if result['pending_migrations']:
        print(f"\nPending migrations ({len(result['pending_migrations'])}):")
        for migration in result['pending_migrations']:
            print(f"  {migration['version']:03d}_{migration['description']}")
            if migration['warnings']:
                for warning in migration['warnings']:
                    print(f"      ⚠️  {warning}")
    
    print(f"\nApplied migrations ({len(result['applied_migrations'])}):")
    for migration in result['applied_migrations']:
        print(f"  {migration['version']:03d}_{migration['description']}")
        print(f"      Applied: {migration['applied_at']} by {migration['applied_by']}")
else:
    print(f"Status check failed: {result['error']}")
    print(f"Message: {result['message']}")
```

---

## Error Codes

### LOCK_TIMEOUT

**Description**: Migration lock acquisition timeout (another migration in progress)

**Cause**: Another client is currently applying or rolling back migrations for this plugin

**Recovery**:
1. Wait for other migration to complete (check status)
2. Retry operation
3. If lock persists, check for hung processes

**Example**:
```json
{
  "success": false,
  "error": "LOCK_TIMEOUT",
  "message": "Could not acquire migration lock after 30 seconds",
  "details": {
    "timeout_seconds": 30,
    "locked_by": "admin",
    "locked_at": "2025-11-24T10:05:00Z"
  }
}
```

### VALIDATION_FAILED

**Description**: Migration validation found ERROR-level issues

**Cause**: SQL contains operations not supported by SQLite or syntax errors

**Recovery**:
1. Review validation errors in `details.validation_errors`
2. Fix SQL using suggested workarounds
3. For SQLite limitations, use table recreation pattern (see [Migration Best Practices](guides/MIGRATION_BEST_PRACTICES.md))
4. Re-apply migration

**Example**:
```json
{
  "success": false,
  "error": "VALIDATION_FAILED",
  "message": "Migration 003 validation failed: SQLite does not support DROP COLUMN",
  "details": {
    "migration_version": 3,
    "migration_description": "drop_old_column",
    "validation_errors": [
      {
        "level": "ERROR",
        "message": "SQLite does not support DROP COLUMN directly",
        "line": 5,
        "suggestion": "Use table recreation pattern (see docs/guides/MIGRATION_BEST_PRACTICES.md)"
      }
    ]
  }
}
```

### MIGRATION_FAILED

**Description**: Migration execution failed (SQL error)

**Cause**: SQL statement failed during execution (table doesn't exist, constraint violation, etc.)

**Recovery**:
1. Review `details.sql_error` for database error
2. Fix SQL in migration file
3. Transaction automatically rolled back - database consistent
4. Re-apply migration

**Example**:
```json
{
  "success": false,
  "error": "MIGRATION_FAILED",
  "message": "Migration 004 failed: no such table: old_table",
  "details": {
    "migration_version": 4,
    "migration_description": "rename_table",
    "sql_error": "no such table: old_table",
    "statement": "ALTER TABLE old_table RENAME TO new_table;"
  }
}
```

### ROLLBACK_FAILED

**Description**: Migration rollback failed (SQL error in DOWN section)

**Cause**: DOWN SQL statement failed during rollback execution

**Recovery**:
1. Review `details.sql_error` for database error
2. Fix DOWN SQL in migration file
3. Transaction automatically rolled back - database consistent
4. May need manual intervention or database restore if data corrupted

**Example**:
```json
{
  "success": false,
  "error": "ROLLBACK_FAILED",
  "message": "Migration 005 rollback failed: FOREIGN KEY constraint failed",
  "details": {
    "migration_version": 5,
    "migration_description": "add_foreign_keys",
    "sql_error": "FOREIGN KEY constraint failed",
    "statement": "DROP TABLE child_table;"
  }
}
```

### CHECKSUM_MISMATCH

**Description**: Migration file has been modified after being applied

**Cause**: File contents changed after migration was applied (detected via SHA-256 checksum)

**Recovery**:
1. **NEVER modify applied migrations** - this is a serious error
2. Check git history to see what changed
3. Revert file to original contents
4. Create NEW migration for additional changes

**Example**:
```json
{
  "success": false,
  "error": "CHECKSUM_MISMATCH",
  "message": "Migration 002 file has been modified (checksum mismatch)",
  "details": {
    "migration_version": 2,
    "migration_description": "add_category_column",
    "expected_checksum": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "actual_checksum": "a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3",
    "applied_at": "2025-11-24T10:01:30Z"
  }
}
```

### INVALID_REQUEST

**Description**: Request message is malformed or contains invalid parameters

**Cause**: JSON parsing error, invalid field types, or conflicting parameters

**Recovery**:
1. Check request JSON syntax
2. Verify field types (integer vs string)
3. Don't specify both `count` and `to_version` in rollback
4. Use valid version numbers (>= 1)

**Example**:
```json
{
  "success": false,
  "error": "INVALID_REQUEST",
  "message": "Cannot specify both 'count' and 'to_version' in rollback request",
  "details": {
    "request_data": {"count": 2, "to_version": 3}
  }
}
```

### NO_MIGRATIONS_FOUND

**Description**: No migration files found for plugin

**Cause**: Plugin has no `migrations/` directory or directory is empty

**Recovery**:
1. Create `plugins/<plugin-name>/migrations/` directory
2. Add migration files following naming convention
3. Or accept that plugin has no migrations (not an error if intentional)

**Example**:
```json
{
  "success": false,
  "error": "NO_MIGRATIONS_FOUND",
  "message": "No migration files found for plugin 'quote-db'",
  "details": {
    "plugin_name": "quote-db",
    "expected_path": "plugins/quote-db/migrations/"
  }
}
```

---

## Common Patterns

### Apply Migrations on Plugin Startup

```python
async def initialize_plugin():
    """Apply any pending migrations before plugin starts."""
    nc = await nats.connect("nats://localhost:4222")
    
    # Check status
    response = await nc.request(
        "rosey.db.migrate.my-plugin.status",
        json.dumps({}).encode(),
        timeout=5.0
    )
    status = json.loads(response.data)
    
    if not status['success']:
        raise RuntimeError(f"Status check failed: {status['message']}")
    
    # Apply if pending
    if status['pending_migrations']:
        print(f"Applying {len(status['pending_migrations'])} pending migrations...")
        response = await nc.request(
            "rosey.db.migrate.my-plugin.apply",
            json.dumps({}).encode(),
            timeout=30.0
        )
        result = json.loads(response.data)
        
        if not result['success']:
            raise RuntimeError(f"Migration failed: {result['message']}")
        
        print(f"Applied {result['migrations_applied']} migrations")
        
        if result['warnings']:
            for warning in result['warnings']:
                print(f"⚠️  {warning}")
```

### Safe Production Deployment

```python
async def deploy_migrations():
    """Safely deploy migrations to production."""
    nc = await nats.connect("nats://localhost:4222")
    
    # 1. Dry-run to validate
    print("Validating migrations...")
    response = await nc.request(
        "rosey.db.migrate.my-plugin.apply",
        json.dumps({"dry_run": True}).encode(),
        timeout=10.0
    )
    result = json.loads(response.data)
    
    if not result['success']:
        print(f"Validation failed: {result['message']}")
        return False
    
    if result['warnings']:
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  ⚠️  {warning}")
        
        # Require confirmation for destructive operations
        confirm = input("Continue with these warnings? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted")
            return False
    
    # 2. Backup database
    print("Backing up database...")
    # ... backup logic ...
    
    # 3. Apply migrations
    print("Applying migrations...")
    response = await nc.request(
        "rosey.db.migrate.my-plugin.apply",
        json.dumps({}).encode(),
        timeout=60.0  # Longer timeout for production
    )
    result = json.loads(response.data)
    
    if result['success']:
        print(f"✅ Applied {result['migrations_applied']} migrations")
        print(f"Schema version: {result['final_version']}")
        return True
    else:
        print(f"❌ Migration failed: {result['message']}")
        # Database automatically rolled back
        return False
```

### Emergency Rollback

```python
async def emergency_rollback(plugin_name: str, to_version: int):
    """Emergency rollback to specific version."""
    nc = await nats.connect("nats://localhost:4222")
    
    # Check current status
    response = await nc.request(
        f"rosey.db.migrate.{plugin_name}.status",
        json.dumps({}).encode(),
        timeout=5.0
    )
    status = json.loads(response.data)
    
    if not status['success']:
        print(f"Status check failed: {status['message']}")
        return False
    
    current = status['current_version']
    print(f"Current version: {current}")
    print(f"Rolling back to version: {to_version}")
    
    # Dry-run rollback
    print("Validating rollback...")
    response = await nc.request(
        f"rosey.db.migrate.{plugin_name}.rollback",
        json.dumps({"to_version": to_version, "dry_run": True}).encode(),
        timeout=10.0
    )
    result = json.loads(response.data)
    
    if not result['success']:
        print(f"Rollback validation failed: {result['message']}")
        return False
    
    if result['warnings']:
        print("Warnings:")
        for warning in result['warnings']:
            print(f"  ⚠️  {warning}")
    
    # Execute rollback
    print("Executing rollback...")
    response = await nc.request(
        f"rosey.db.migrate.{plugin_name}.rollback",
        json.dumps({"to_version": to_version}).encode(),
        timeout=60.0
    )
    result = json.loads(response.data)
    
    if result['success']:
        print(f"✅ Rolled back {result['migrations_rolled_back']} migrations")
        print(f"Schema version: {result['final_version']}")
        return True
    else:
        print(f"❌ Rollback failed: {result['message']}")
        return False
```

---

## Related Documentation

- **[Plugin Migration Guide](guides/PLUGIN_MIGRATIONS.md)** - Complete guide for plugin developers
- **[Migration Best Practices](guides/MIGRATION_BEST_PRACTICES.md)** - Detailed best practices and patterns
- **[Migration Examples](../examples/migrations/)** - 10 example migration files
- **[Architecture](ARCHITECTURE.md)** - System architecture with Schema Migrations section

---

**Version**: 1.0  
**Sprint**: 15 - Schema Migrations  
**Last Updated**: November 24, 2025
