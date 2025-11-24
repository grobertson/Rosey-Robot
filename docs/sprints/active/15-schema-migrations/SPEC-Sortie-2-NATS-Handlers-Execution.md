# SPEC-Sortie-2: NATS Handlers & Execution

**Sprint**: 15 - Schema Migrations  
**Sortie**: 2 of 4  
**Estimated Duration**: 1.5 days  
**Status**: Draft  
**Author**: Agent via PRD-Schema-Migrations.md  
**Created**: November 24, 2025  

---

## 1. Overview

This sortie implements NATS message handlers and execution infrastructure for database schema migrations. Building on Sortie 1's MigrationManager foundation, we add request/response handlers for applying, rolling back, and checking migration status via the event bus. This sortie introduces MigrationExecutor for database transaction management, locking for concurrent safety, and result tracking for observability.

**What This Sortie Achieves**:
- NATS handlers: `db.migrate.<plugin>.apply`, `.rollback`, `.status`
- MigrationExecutor class for transaction-wrapped SQL execution
- Migration locking with asyncio.Lock to prevent concurrent runs
- Applied migration tracking in plugin_schema_migrations table
- Dry-run mode for safe preview
- Comprehensive error handling and rollback

**Key Integration Points**:
- DatabaseService registers handlers in NATS client
- MigrationManager discovers/parses migrations (Sortie 1)
- MigrationExecutor applies UP/DOWN SQL with transaction safety
- plugin_schema_migrations table tracks applied migrations

---

## 2. Scope and Non-Goals

### In Scope

- **NATS Handler Registration**: Add migration-specific NATS subscriptions in DatabaseService
- **Apply Handler**: `db.migrate.<plugin>.apply` - Applies pending migrations
- **Rollback Handler**: `db.migrate.<plugin>.rollback` - Reverts applied migrations
- **Status Handler**: `db.migrate.<plugin>.status` - Returns migration state
- **MigrationExecutor**: Class for executing migrations with transaction management
- **Locking**: asyncio.Lock per plugin to prevent concurrent migrations
- **Transaction Management**: BEGIN/COMMIT/ROLLBACK for atomic migrations
- **Dry-Run Mode**: Preview migrations without committing changes
- **Error Recovery**: Automatic rollback on failure
- **Result Tracking**: Store execution time, status, error messages

### Out of Scope (Future Sorties)

- **Safety Features**: Destructive operation warnings (Sortie 3)
- **Validation**: SQL syntax checking, column existence (Sortie 3)
- **SQLite Limitations**: Detection and warnings (Sortie 3)
- **Checksum Verification**: On status checks (Sortie 3)
- **Documentation**: User guides and examples (Sortie 4)
- **Auto-migration**: Automatic schema updates on plugin load (future)

---

## 3. Requirements

### Functional Requirements

**FR-1: NATS Handler Registration**
- DatabaseService registers three handlers during initialization:
  - `db.migrate.{plugin}.apply`
  - `db.migrate.{plugin}.rollback`
  - `db.migrate.{plugin}.status`
- Handlers use wildcard: `db.migrate.*.*`
- Plugin name extracted from subject (e.g., `db.migrate.quotes.apply` → plugin="quotes")

**FR-2: Apply Migration Handler**
- Receives: `{"target_version": 3, "dry_run": false}` or `{"target_version": "latest"}`
- Discovers all migrations for plugin
- Calculates pending migrations (current → target)
- Executes each pending migration in order
- Commits transaction on success
- Rolls back transaction on failure
- Returns: `{"success": true, "applied_migrations": [...]}`

**FR-3: Rollback Migration Handler**
- Receives: `{"target_version": 0}` (rollback to version)
- Calculates rollback migrations (current → target)
- Executes DOWN SQL for each migration in descending order
- Commits transaction on success
- Rolls back transaction on failure
- Returns: `{"success": true, "rolled_back_migrations": [...]}`

**FR-4: Status Migration Handler**
- Receives: `{}` (no parameters)
- Queries plugin_schema_migrations table
- Discovers all available migrations
- Calculates current version, pending count, applied list
- Returns: `{"current_version": 3, "pending_count": 2, "applied_migrations": [...]}`

**FR-5: Migration Locking**
- One migration per plugin at a time
- Use asyncio.Lock per plugin (dict: plugin_name → Lock)
- Acquire lock before starting migration
- Release lock after completion or error
- Return error if lock already held: `{"error": "MIGRATION_IN_PROGRESS"}`

**FR-6: Transaction Management**
- Each migration wrapped in database transaction
- BEGIN before executing SQL
- COMMIT on success
- ROLLBACK on exception
- Preserve isolation between migrations

**FR-7: Dry-Run Mode**
- When `dry_run=True`, execute migration but rollback transaction
- Return same result format with `dry_run: true` flag
- Useful for previewing changes
- No changes committed to database

**FR-8: Result Tracking**
- Insert record into plugin_schema_migrations after applying migration
- Fields: plugin_name, version, name, checksum, applied_at, applied_by, status, error_message, execution_time_ms
- Status: "applied", "rolled_back", "failed"
- Measure execution time in milliseconds

### Non-Functional Requirements

**NFR-1: Performance**
- Migration execution time depends on SQL complexity
- Lock acquisition < 1ms
- Handler response time < 100ms overhead (excluding SQL execution)

**NFR-2: Reliability**
- Transaction rollback on any error prevents partial migrations
- Lock prevents race conditions
- Comprehensive error messages for troubleshooting

**NFR-3: Testability**
- 40+ integration tests covering all handlers
- Test fixtures with sample migrations
- Mock NATS messages for handler testing

**NFR-4: Code Coverage**
- Target: 85%+ for MigrationExecutor and handlers
- Minimum: 66% per project standards

---

## 4. Technical Design

### 4.1 MigrationExecutor Class

Handles execution of individual migrations with transaction safety.

```python
"""
common/database/migration_executor.py
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import time

from .migration import Migration
from .database import Database


@dataclass
class MigrationResult:
    """Result of executing a migration."""
    
    success: bool
    migration: Migration
    execution_time_ms: int
    applied_at: datetime
    applied_by: str
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'version': self.migration.version,
            'name': self.migration.name,
            'execution_time_ms': self.execution_time_ms,
            'applied_at': self.applied_at.isoformat(),
            'applied_by': self.applied_by,
            'error': self.error
        }


class MigrationExecutor:
    """Executes database migrations with transaction safety."""
    
    def __init__(self, database: Database):
        """
        Initialize migration executor.
        
        Args:
            database: Database instance for executing SQL
        """
        self.db = database
    
    async def apply_migration(
        self, 
        plugin_name: str, 
        migration: Migration, 
        dry_run: bool = False,
        applied_by: str = "system"
    ) -> MigrationResult:
        """
        Apply a migration by executing its UP SQL.
        
        Args:
            plugin_name: Name of the plugin
            migration: Migration object with UP SQL
            dry_run: If True, execute but rollback transaction
            applied_by: User/system applying the migration
            
        Returns:
            MigrationResult with success status and timing
            
        Raises:
            Exception: If migration execution fails (transaction rolled back)
        """
        start_time = time.time()
        applied_at = datetime.utcnow()
        
        try:
            # Begin transaction
            async with self.db.transaction():
                # Execute UP SQL
                await self.db.execute(migration.up_sql)
                
                if not dry_run:
                    # Record applied migration
                    await self._record_migration(
                        plugin_name=plugin_name,
                        migration=migration,
                        status="applied",
                        applied_at=applied_at,
                        applied_by=applied_by,
                        execution_time_ms=int((time.time() - start_time) * 1000)
                    )
                else:
                    # Dry-run: intentionally rollback
                    raise DryRunRollback()
            
            execution_time = int((time.time() - start_time) * 1000)
            return MigrationResult(
                success=True,
                migration=migration,
                execution_time_ms=execution_time,
                applied_at=applied_at,
                applied_by=applied_by
            )
            
        except DryRunRollback:
            # Dry-run completed successfully
            execution_time = int((time.time() - start_time) * 1000)
            return MigrationResult(
                success=True,
                migration=migration,
                execution_time_ms=execution_time,
                applied_at=applied_at,
                applied_by=applied_by
            )
            
        except Exception as e:
            # Migration failed, transaction automatically rolled back
            execution_time = int((time.time() - start_time) * 1000)
            error_message = f"Migration {migration.version}_{migration.name} failed: {str(e)}"
            
            # Record failure
            await self._record_migration(
                plugin_name=plugin_name,
                migration=migration,
                status="failed",
                applied_at=applied_at,
                applied_by=applied_by,
                execution_time_ms=execution_time,
                error_message=error_message
            )
            
            return MigrationResult(
                success=False,
                migration=migration,
                execution_time_ms=execution_time,
                applied_at=applied_at,
                applied_by=applied_by,
                error=error_message
            )
    
    async def rollback_migration(
        self, 
        plugin_name: str, 
        migration: Migration,
        applied_by: str = "system"
    ) -> MigrationResult:
        """
        Rollback a migration by executing its DOWN SQL.
        
        Args:
            plugin_name: Name of the plugin
            migration: Migration object with DOWN SQL
            applied_by: User/system rolling back
            
        Returns:
            MigrationResult with success status and timing
        """
        start_time = time.time()
        applied_at = datetime.utcnow()
        
        try:
            async with self.db.transaction():
                # Execute DOWN SQL
                await self.db.execute(migration.down_sql)
                
                # Update migration record to rolled_back
                await self.db.execute(
                    """
                    UPDATE plugin_schema_migrations
                    SET status = 'rolled_back'
                    WHERE plugin_name = ? AND version = ?
                    """,
                    (plugin_name, migration.version)
                )
            
            execution_time = int((time.time() - start_time) * 1000)
            return MigrationResult(
                success=True,
                migration=migration,
                execution_time_ms=execution_time,
                applied_at=applied_at,
                applied_by=applied_by
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_message = f"Rollback {migration.version}_{migration.name} failed: {str(e)}"
            
            return MigrationResult(
                success=False,
                migration=migration,
                execution_time_ms=execution_time,
                applied_at=applied_at,
                applied_by=applied_by,
                error=error_message
            )
    
    async def _record_migration(
        self,
        plugin_name: str,
        migration: Migration,
        status: str,
        applied_at: datetime,
        applied_by: str,
        execution_time_ms: int,
        error_message: Optional[str] = None
    ):
        """Record migration application in tracking table."""
        await self.db.execute(
            """
            INSERT INTO plugin_schema_migrations 
            (plugin_name, version, name, checksum, applied_at, applied_by, 
             status, error_message, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plugin_name,
                migration.version,
                migration.name,
                migration.checksum,
                applied_at.isoformat(),
                applied_by,
                status,
                error_message,
                execution_time_ms
            )
        )


class DryRunRollback(Exception):
    """Exception raised to rollback dry-run transactions."""
    pass
```

### 4.2 DatabaseService NATS Handlers

Add migration handlers to DatabaseService class.

```python
"""
common/database/database_service.py (additions)
"""
import asyncio
from typing import Dict
from .migration_manager import MigrationManager
from .migration_executor import MigrationExecutor


class DatabaseService:
    def __init__(self, nats_client, db, plugins_dir):
        self.nc = nats_client
        self.db = db
        self.plugins_dir = plugins_dir
        self.migration_locks: Dict[str, asyncio.Lock] = {}
    
    async def start(self):
        """Register all NATS handlers."""
        # Existing handlers...
        
        # Migration handlers
        await self.nc.subscribe("db.migrate.*.apply", cb=self.handle_migrate_apply)
        await self.nc.subscribe("db.migrate.*.rollback", cb=self.handle_migrate_rollback)
        await self.nc.subscribe("db.migrate.*.status", cb=self.handle_migrate_status)
    
    def _get_plugin_lock(self, plugin_name: str) -> asyncio.Lock:
        """Get or create lock for plugin migrations."""
        if plugin_name not in self.migration_locks:
            self.migration_locks[plugin_name] = asyncio.Lock()
        return self.migration_locks[plugin_name]
    
    async def _get_current_version(self, plugin_name: str) -> int:
        """Get current migration version for plugin."""
        result = await self.db.fetch_one(
            """
            SELECT MAX(version) as version
            FROM plugin_schema_migrations
            WHERE plugin_name = ? AND status = 'applied'
            """,
            (plugin_name,)
        )
        return result['version'] if result and result['version'] else 0
    
    async def handle_migrate_apply(self, msg):
        """
        Handle db.migrate.<plugin>.apply requests.
        
        Request: {"target_version": 3, "dry_run": false}
        Response: {"success": true, "applied_migrations": [...]}
        """
        # Extract plugin name from subject: db.migrate.quotes.apply -> quotes
        parts = msg.subject.split('.')
        plugin_name = parts[2]
        
        # Parse request
        data = json.loads(msg.data)
        target_version = data.get('target_version', 'latest')
        dry_run = data.get('dry_run', False)
        
        # Acquire lock
        lock = self._get_plugin_lock(plugin_name)
        if lock.locked():
            await msg.respond(json.dumps({
                'success': False,
                'error_code': 'MIGRATION_IN_PROGRESS',
                'message': f'Migration already in progress for {plugin_name}'
            }).encode())
            return
        
        async with lock:
            try:
                # Initialize manager and executor
                manager = MigrationManager(self.plugins_dir)
                executor = MigrationExecutor(self.db)
                
                # Get current version
                current_version = await self._get_current_version(plugin_name)
                
                # Resolve 'latest' to actual version
                if target_version == 'latest':
                    all_migrations = manager.discover_migrations(plugin_name)
                    if not all_migrations:
                        await msg.respond(json.dumps({
                            'success': True,
                            'message': 'No migrations found',
                            'applied_migrations': []
                        }).encode())
                        return
                    target_version = max(m.version for m in all_migrations)
                
                # Calculate pending migrations
                pending = manager.get_pending_migrations(plugin_name, current_version, target_version)
                
                if not pending:
                    await msg.respond(json.dumps({
                        'success': True,
                        'message': 'No pending migrations',
                        'current_version': current_version,
                        'applied_migrations': []
                    }).encode())
                    return
                
                # Apply each migration
                results = []
                for migration in pending:
                    result = await executor.apply_migration(
                        plugin_name, 
                        migration, 
                        dry_run=dry_run
                    )
                    
                    if not result.success:
                        # Migration failed, stop and report
                        await msg.respond(json.dumps({
                            'success': False,
                            'error_code': 'MIGRATION_FAILED',
                            'message': result.error,
                            'failed_version': migration.version,
                            'applied_migrations': [r.to_dict() for r in results]
                        }).encode())
                        return
                    
                    results.append(result)
                
                # All migrations applied successfully
                await msg.respond(json.dumps({
                    'success': True,
                    'dry_run': dry_run,
                    'applied_migrations': [r.to_dict() for r in results]
                }).encode())
                
            except Exception as e:
                await msg.respond(json.dumps({
                    'success': False,
                    'error_code': 'INTERNAL_ERROR',
                    'message': str(e)
                }).encode())
    
    async def handle_migrate_rollback(self, msg):
        """
        Handle db.migrate.<plugin>.rollback requests.
        
        Request: {"target_version": 0}
        Response: {"success": true, "rolled_back_migrations": [...]}
        """
        parts = msg.subject.split('.')
        plugin_name = parts[2]
        
        data = json.loads(msg.data)
        target_version = data.get('target_version', 0)
        
        lock = self._get_plugin_lock(plugin_name)
        if lock.locked():
            await msg.respond(json.dumps({
                'success': False,
                'error_code': 'MIGRATION_IN_PROGRESS',
                'message': f'Migration already in progress for {plugin_name}'
            }).encode())
            return
        
        async with lock:
            try:
                manager = MigrationManager(self.plugins_dir)
                executor = MigrationExecutor(self.db)
                
                current_version = await self._get_current_version(plugin_name)
                
                # Calculate rollback migrations (descending order)
                rollback_migrations = manager.get_rollback_migrations(
                    plugin_name, 
                    current_version, 
                    target_version
                )
                
                if not rollback_migrations:
                    await msg.respond(json.dumps({
                        'success': True,
                        'message': 'No migrations to rollback',
                        'current_version': current_version,
                        'rolled_back_migrations': []
                    }).encode())
                    return
                
                results = []
                for migration in rollback_migrations:
                    result = await executor.rollback_migration(plugin_name, migration)
                    
                    if not result.success:
                        await msg.respond(json.dumps({
                            'success': False,
                            'error_code': 'ROLLBACK_FAILED',
                            'message': result.error,
                            'failed_version': migration.version,
                            'rolled_back_migrations': [r.to_dict() for r in results]
                        }).encode())
                        return
                    
                    results.append(result)
                
                await msg.respond(json.dumps({
                    'success': True,
                    'rolled_back_migrations': [r.to_dict() for r in results]
                }).encode())
                
            except Exception as e:
                await msg.respond(json.dumps({
                    'success': False,
                    'error_code': 'INTERNAL_ERROR',
                    'message': str(e)
                }).encode())
    
    async def handle_migrate_status(self, msg):
        """
        Handle db.migrate.<plugin>.status requests.
        
        Request: {}
        Response: {
            "current_version": 3,
            "pending_count": 2,
            "applied_migrations": [...],
            "available_migrations": [...]
        }
        """
        parts = msg.subject.split('.')
        plugin_name = parts[2]
        
        try:
            manager = MigrationManager(self.plugins_dir)
            
            # Get current version
            current_version = await self._get_current_version(plugin_name)
            
            # Get all available migrations
            all_migrations = manager.discover_migrations(plugin_name)
            
            # Get applied migrations from database
            applied_rows = await self.db.fetch_all(
                """
                SELECT version, name, checksum, applied_at, applied_by, 
                       status, execution_time_ms
                FROM plugin_schema_migrations
                WHERE plugin_name = ? AND status = 'applied'
                ORDER BY version ASC
                """,
                (plugin_name,)
            )
            
            applied_migrations = [
                {
                    'version': row['version'],
                    'name': row['name'],
                    'checksum': row['checksum'],
                    'applied_at': row['applied_at'],
                    'applied_by': row['applied_by'],
                    'execution_time_ms': row['execution_time_ms']
                }
                for row in applied_rows
            ]
            
            # Calculate pending
            pending_migrations = [
                {'version': m.version, 'name': m.name}
                for m in all_migrations
                if m.version > current_version
            ]
            
            await msg.respond(json.dumps({
                'success': True,
                'plugin_name': plugin_name,
                'current_version': current_version,
                'pending_count': len(pending_migrations),
                'applied_migrations': applied_migrations,
                'pending_migrations': pending_migrations,
                'available_migrations': [
                    {'version': m.version, 'name': m.name} 
                    for m in all_migrations
                ]
            }).encode())
            
        except Exception as e:
            await msg.respond(json.dumps({
                'success': False,
                'error_code': 'INTERNAL_ERROR',
                'message': str(e)
            }).encode())
```

---

## 5. Implementation Steps

1. **Create MigrationExecutor Class** (`common/database/migration_executor.py`)
   - Define MigrationResult dataclass with success, timing, error fields
   - Implement MigrationExecutor.__init__(database)
   - Implement apply_migration() with transaction wrapper
   - Implement rollback_migration() with DOWN SQL execution
   - Implement _record_migration() helper for tracking
   - Add DryRunRollback exception class

2. **Add Migration Locking** (`common/database/database_service.py`)
   - Add self.migration_locks: Dict[str, asyncio.Lock] to __init__
   - Implement _get_plugin_lock(plugin_name) helper
   - Return existing lock or create new one per plugin

3. **Add Current Version Helper**
   - Implement _get_current_version(plugin_name) in DatabaseService
   - Query MAX(version) from plugin_schema_migrations
   - Return 0 if no migrations applied

4. **Implement Apply Handler**
   - Add handle_migrate_apply() method in DatabaseService
   - Extract plugin_name from subject (split by '.')
   - Parse JSON request: target_version, dry_run
   - Acquire plugin lock, return error if locked
   - Initialize MigrationManager and MigrationExecutor
   - Resolve 'latest' to actual max version
   - Get pending migrations (current → target)
   - Loop through pending, call executor.apply_migration()
   - Stop and report on first failure
   - Return success with applied_migrations list

5. **Implement Rollback Handler**
   - Add handle_migrate_rollback() method
   - Extract plugin_name from subject
   - Parse JSON request: target_version
   - Acquire plugin lock
   - Get rollback migrations (current → target, descending)
   - Loop through rollback list, call executor.rollback_migration()
   - Stop and report on first failure
   - Return success with rolled_back_migrations list

6. **Implement Status Handler**
   - Add handle_migrate_status() method
   - Extract plugin_name from subject
   - Get current_version from database
   - Discover all_migrations from filesystem
   - Query applied_migrations from database
   - Calculate pending_migrations (version > current)
   - Return comprehensive status object

7. **Register NATS Handlers**
   - Update DatabaseService.start() method
   - Subscribe to "db.migrate.*.apply" → handle_migrate_apply
   - Subscribe to "db.migrate.*.rollback" → handle_migrate_rollback
   - Subscribe to "db.migrate.*.status" → handle_migrate_status
   - Wildcard subscriptions enable any plugin

8. **Add Error Response Helper** (optional)
   - Create _error_response(error_code, message) helper
   - Standardize error response format
   - Use in all handlers for consistency

9. **Update Database Class** (if needed)
   - Ensure Database.transaction() context manager exists
   - Ensure Database.execute() supports multi-statement SQL
   - Ensure Database.fetch_one() and fetch_all() available

10. **Integration Testing**
    - Write integration tests using test fixtures
    - Test apply, rollback, status handlers end-to-end
    - Test locking with concurrent requests
    - Test dry-run mode

11. **Documentation**
    - Add docstrings to all methods
    - Document NATS message formats
    - Document error codes

---

## 6. Testing Strategy

### 6.1 Unit Tests - MigrationExecutor

**tests/unit/database/test_migration_executor.py**

```python
import pytest
from common.database.migration_executor import MigrationExecutor, MigrationResult
from common.database.migration import Migration


class TestApplyMigration:
    async def test_apply_migration_success(self, db, sample_migration):
        """Test applying migration executes UP SQL and records result."""
        executor = MigrationExecutor(db)
        result = await executor.apply_migration("quotes", sample_migration)
        
        assert result.success is True
        assert result.migration == sample_migration
        assert result.execution_time_ms > 0
        assert result.error is None
        
        # Verify migration recorded
        row = await db.fetch_one(
            "SELECT * FROM plugin_schema_migrations WHERE plugin_name='quotes' AND version=1"
        )
        assert row['status'] == 'applied'
    
    async def test_apply_migration_dry_run(self, db, sample_migration):
        """Test dry-run mode rolls back transaction."""
        executor = MigrationExecutor(db)
        result = await executor.apply_migration("quotes", sample_migration, dry_run=True)
        
        assert result.success is True
        
        # Verify no record in database (rolled back)
        row = await db.fetch_one(
            "SELECT * FROM plugin_schema_migrations WHERE plugin_name='quotes' AND version=1"
        )
        assert row is None
    
    async def test_apply_migration_failure(self, db):
        """Test failed migration rolls back and records error."""
        bad_migration = Migration(
            version=1,
            name="bad_sql",
            up_sql="INVALID SQL SYNTAX",
            down_sql="DROP TABLE test;",
            checksum="abc123"
        )
        
        executor = MigrationExecutor(db)
        result = await executor.apply_migration("quotes", bad_migration)
        
        assert result.success is False
        assert "failed" in result.error.lower()
        
        # Verify failure recorded
        row = await db.fetch_one(
            "SELECT * FROM plugin_schema_migrations WHERE plugin_name='quotes' AND version=1"
        )
        assert row['status'] == 'failed'
        assert row['error_message'] is not None


class TestRollbackMigration:
    async def test_rollback_migration_success(self, db, applied_migration):
        """Test rollback executes DOWN SQL."""
        executor = MigrationExecutor(db)
        result = await executor.rollback_migration("quotes", applied_migration)
        
        assert result.success is True
        assert result.migration == applied_migration
        
        # Verify status updated
        row = await db.fetch_one(
            "SELECT * FROM plugin_schema_migrations WHERE plugin_name='quotes' AND version=1"
        )
        assert row['status'] == 'rolled_back'
    
    async def test_rollback_migration_failure(self, db, applied_migration):
        """Test rollback failure is recorded."""
        bad_migration = Migration(
            version=1,
            name="bad_rollback",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="INVALID SQL",
            checksum="abc123"
        )
        
        executor = MigrationExecutor(db)
        result = await executor.rollback_migration("quotes", bad_migration)
        
        assert result.success is False
        assert "failed" in result.error.lower()


class TestTransactionManagement:
    async def test_transaction_rollback_on_error(self, db):
        """Test transaction rolls back on error, leaving no partial changes."""
        migration = Migration(
            version=1,
            name="multi_statement",
            up_sql="CREATE TABLE test1 (id INTEGER); INVALID SQL; CREATE TABLE test2 (id INTEGER);",
            down_sql="DROP TABLE test1; DROP TABLE test2;",
            checksum="abc123"
        )
        
        executor = MigrationExecutor(db)
        result = await executor.apply_migration("quotes", migration)
        
        assert result.success is False
        
        # Verify test1 and test2 tables do NOT exist (transaction rolled back)
        tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [t['name'] for t in tables]
        assert 'test1' not in table_names
        assert 'test2' not in table_names


### 6.2 Integration Tests - NATS Handlers

**tests/integration/database/test_migration_handlers.py**

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


class TestApplyHandler:
    async def test_apply_single_migration(self, database_service, nats_msg):
        """Test applying single migration via NATS."""
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 1}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['applied_migrations']) == 1
        assert response['applied_migrations'][0]['version'] == 1
    
    async def test_apply_multiple_migrations(self, database_service, nats_msg):
        """Test applying multiple migrations in order."""
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 3}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['applied_migrations']) == 3
        assert response['applied_migrations'][0]['version'] == 1
        assert response['applied_migrations'][2]['version'] == 3
    
    async def test_apply_to_latest(self, database_service, nats_msg):
        """Test applying migrations to latest version."""
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": "latest"}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
    
    async def test_apply_dry_run(self, database_service, nats_msg, db):
        """Test dry-run mode does not commit changes."""
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 1, "dry_run": True}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert response['dry_run'] is True
        
        # Verify no migrations recorded
        row = await db.fetch_one(
            "SELECT * FROM plugin_schema_migrations WHERE plugin_name='quotes'"
        )
        assert row is None
    
    async def test_apply_no_pending(self, database_service, nats_msg):
        """Test apply when already at target version."""
        # Apply migrations first
        nats_msg.data = json.dumps({"target_version": 2}).encode()
        await database_service.handle_migrate_apply(nats_msg)
        
        # Try to apply again
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['applied_migrations']) == 0
        assert 'No pending migrations' in response['message']
    
    async def test_apply_migration_failure(self, database_service, nats_msg):
        """Test apply stops on first failure."""
        # Setup: Migration 2 has invalid SQL
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 3}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is False
        assert response['error_code'] == 'MIGRATION_FAILED'
        assert response['failed_version'] == 2
        assert len(response['applied_migrations']) == 1  # Only migration 1 succeeded


class TestRollbackHandler:
    async def test_rollback_single_migration(self, database_service, nats_msg):
        """Test rolling back single migration."""
        # Apply migrations first
        nats_msg.subject = "db.migrate.quotes.rollback"
        nats_msg.data = json.dumps({"target_version": 2}).encode()
        await database_service.handle_migrate_apply(nats_msg)
        
        # Rollback to version 1
        nats_msg.data = json.dumps({"target_version": 1}).encode()
        await database_service.handle_migrate_rollback(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['rolled_back_migrations']) == 1
        assert response['rolled_back_migrations'][0]['version'] == 2
    
    async def test_rollback_to_zero(self, database_service, nats_msg):
        """Test rolling back all migrations."""
        # Apply 3 migrations
        nats_msg.data = json.dumps({"target_version": 3}).encode()
        await database_service.handle_migrate_apply(nats_msg)
        
        # Rollback to zero
        nats_msg.subject = "db.migrate.quotes.rollback"
        nats_msg.data = json.dumps({"target_version": 0}).encode()
        await database_service.handle_migrate_rollback(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['rolled_back_migrations']) == 3
        assert response['rolled_back_migrations'][0]['version'] == 3  # Descending order
        assert response['rolled_back_migrations'][2]['version'] == 1
    
    async def test_rollback_no_migrations(self, database_service, nats_msg):
        """Test rollback when already at target version."""
        nats_msg.subject = "db.migrate.quotes.rollback"
        nats_msg.data = json.dumps({"target_version": 0}).encode()
        
        await database_service.handle_migrate_rollback(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert len(response['rolled_back_migrations']) == 0
        assert 'No migrations to rollback' in response['message']
    
    async def test_rollback_failure(self, database_service, nats_msg):
        """Test rollback stops on first failure."""
        # Setup: Migration 2 has invalid DOWN SQL
        nats_msg.subject = "db.migrate.quotes.rollback"
        nats_msg.data = json.dumps({"target_version": 0}).encode()
        
        await database_service.handle_migrate_rollback(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is False
        assert response['error_code'] == 'ROLLBACK_FAILED'


class TestStatusHandler:
    async def test_status_no_migrations(self, database_service, nats_msg):
        """Test status with no applied migrations."""
        nats_msg.subject = "db.migrate.quotes.status"
        nats_msg.data = json.dumps({}).encode()
        
        await database_service.handle_migrate_status(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert response['current_version'] == 0
        assert response['pending_count'] == 3  # Assuming 3 migrations available
        assert len(response['applied_migrations']) == 0
        assert len(response['available_migrations']) == 3
    
    async def test_status_with_applied_migrations(self, database_service, nats_msg):
        """Test status shows applied and pending."""
        # Apply 2 migrations
        await database_service.handle_migrate_apply(nats_msg)
        
        # Get status
        nats_msg.subject = "db.migrate.quotes.status"
        nats_msg.data = json.dumps({}).encode()
        await database_service.handle_migrate_status(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['current_version'] == 2
        assert len(response['applied_migrations']) == 2
        assert response['pending_count'] == 1  # 1 migration remaining


class TestMigrationLocking:
    async def test_concurrent_apply_rejected(self, database_service, nats_msg):
        """Test concurrent migration attempts are rejected."""
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 3}).encode()
        
        # Start first migration (doesn't complete)
        task1 = asyncio.create_task(database_service.handle_migrate_apply(nats_msg))
        await asyncio.sleep(0.1)  # Let first task acquire lock
        
        # Try second migration
        msg2 = MagicMock()
        msg2.subject = "db.migrate.quotes.apply"
        msg2.data = nats_msg.data
        msg2.respond = AsyncMock()
        
        await database_service.handle_migrate_apply(msg2)
        
        response = json.loads(msg2.respond.call_args[0][0])
        assert response['success'] is False
        assert response['error_code'] == 'MIGRATION_IN_PROGRESS'
        
        await task1
    
    async def test_different_plugins_concurrent(self, database_service):
        """Test migrations for different plugins can run concurrently."""
        msg1 = MagicMock()
        msg1.subject = "db.migrate.quotes.apply"
        msg1.data = json.dumps({"target_version": 1}).encode()
        msg1.respond = AsyncMock()
        
        msg2 = MagicMock()
        msg2.subject = "db.migrate.polls.apply"
        msg2.data = json.dumps({"target_version": 1}).encode()
        msg2.respond = AsyncMock()
        
        # Both should succeed
        await asyncio.gather(
            database_service.handle_migrate_apply(msg1),
            database_service.handle_migrate_apply(msg2)
        )
        
        response1 = json.loads(msg1.respond.call_args[0][0])
        response2 = json.loads(msg2.respond.call_args[0][0])
        
        assert response1['success'] is True
        assert response2['success'] is True


### 6.3 Test Fixtures

```python
@pytest.fixture
async def sample_migration():
    """Sample migration for testing."""
    return Migration(
        version=1,
        name="create_table",
        up_sql="CREATE TABLE test (id INTEGER PRIMARY KEY);",
        down_sql="DROP TABLE test;",
        checksum="abc123def456"
    )

@pytest.fixture
async def applied_migration(db, sample_migration):
    """Migration that has been applied."""
    executor = MigrationExecutor(db)
    await executor.apply_migration("quotes", sample_migration)
    return sample_migration

@pytest.fixture
def nats_msg():
    """Mock NATS message."""
    msg = MagicMock()
    msg.subject = "db.migrate.quotes.apply"
    msg.data = json.dumps({"target_version": 1}).encode()
    msg.respond = AsyncMock()
    return msg
```

**Coverage Target**: 85%+ across MigrationExecutor and handlers

---

## 7. Acceptance Criteria

- [ ] **AC-1**: MigrationExecutor applies migrations successfully
  - Given a Migration with valid UP SQL
  - When calling apply_migration()
  - Then SQL executes and migration recorded in tracking table

- [ ] **AC-2**: MigrationExecutor rolls back migrations successfully
  - Given an applied Migration with valid DOWN SQL
  - When calling rollback_migration()
  - Then DOWN SQL executes and status updated to 'rolled_back'

- [ ] **AC-3**: Transactions rollback on failure
  - Given migration with invalid SQL
  - When applying migration
  - Then transaction rolls back, no partial changes committed

- [ ] **AC-4**: Dry-run mode works correctly
  - Given dry_run=True
  - When applying migration
  - Then SQL executes but transaction rolls back, no tracking record

- [ ] **AC-5**: Apply handler registers and responds
  - Given NATS message to db.migrate.quotes.apply
  - When handler processes request
  - Then pending migrations applied, response includes applied_migrations list

- [ ] **AC-6**: Rollback handler registers and responds
  - Given NATS message to db.migrate.quotes.rollback
  - When handler processes request
  - Then migrations rolled back in descending order, response includes rolled_back_migrations

- [ ] **AC-7**: Status handler returns accurate information
  - Given plugin with 2 applied and 1 pending migration
  - When requesting status
  - Then response shows current_version=2, pending_count=1

- [ ] **AC-8**: Migration locking prevents concurrent runs
  - Given migration in progress for plugin "quotes"
  - When second migration request arrives for "quotes"
  - Then second request rejected with MIGRATION_IN_PROGRESS error

- [ ] **AC-9**: Different plugins can migrate concurrently
  - Given migration for "quotes" in progress
  - When migration request arrives for "polls"
  - Then both migrations succeed without blocking each other

- [ ] **AC-10**: Failed migration stops execution
  - Given migrations [1, 2, 3] where migration 2 has invalid SQL
  - When applying to version 3
  - Then migration 1 succeeds, migration 2 fails, migration 3 never attempted

- [ ] **AC-11**: 'latest' target version resolves correctly
  - Given migrations 001, 002, 003 available
  - When applying with target_version='latest'
  - Then all three migrations applied to reach version 3

- [ ] **AC-12**: All integration tests pass
  - Given 40+ integration tests
  - When running pytest
  - Then all tests pass with 85%+ coverage

---

## 8. Rollout Plan

### Pre-deployment

1. Ensure Sortie 1 (MigrationManager) is merged and tested
2. Review all MigrationExecutor and handler code
3. Run full test suite (40+ integration tests)
4. Test with sample plugin migrations on staging database
5. Verify locking works with concurrent requests

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-15-sortie-2-nats-handlers`
2. Create `common/database/migration_executor.py`
   - MigrationResult dataclass
   - MigrationExecutor class
   - DryRunRollback exception
3. Update `common/database/database_service.py`
   - Add migration_locks dictionary
   - Add _get_plugin_lock() helper
   - Add _get_current_version() helper
   - Add handle_migrate_apply()
   - Add handle_migrate_rollback()
   - Add handle_migrate_status()
   - Register handlers in start()
4. Write integration tests
   - test_migration_executor.py (unit tests)
   - test_migration_handlers.py (integration tests)
5. Run tests and verify 85%+ coverage
6. Test on staging with real plugins
7. Commit changes with message:
   ```
   Sprint 15 Sortie 2: NATS Handlers & Execution
   
   - Add MigrationExecutor with transaction management
   - Implement db.migrate.<plugin>.apply handler
   - Implement db.migrate.<plugin>.rollback handler
   - Implement db.migrate.<plugin>.status handler
   - Add migration locking per plugin
   - Support dry-run mode for safe preview
   - Add 40+ integration tests (85%+ coverage)
   
   Implements: SPEC-Sortie-2-NATS-Handlers-Execution.md
   Related: PRD-Schema-Migrations.md
   ```
8. Push branch and create PR
9. Code review
10. Merge to main

### Post-deployment

- Test apply/rollback/status via NATS CLI or Postman
- Monitor logs for handler errors
- Verify locking prevents concurrent migrations
- Test dry-run mode on production-like data

### Rollback Procedure

If issues arise:
```bash
# Revert code changes
git revert <commit-hash>

# Restart services to unregister handlers
systemctl restart cytube-bot
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: MigrationManager must be complete and tested
- **Sprint 13**: Database foundation with transaction support
- **Sprint 6a**: NATS event bus for handler registration
- **asyncio**: For locking and async handlers
- **Python 3.11+**: For async/await syntax

### External Dependencies

- NATS server running and accessible

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Transaction not rolled back on error | Low | High | Comprehensive unit tests for error cases |
| Lock not released on exception | Low | High | Use async context manager for lock acquisition |
| Concurrent migrations corrupt database | Low | Critical | Lock per plugin, thorough concurrency tests |
| Long-running migration blocks other requests | Medium | Medium | Document best practices for migration size, consider timeout |
| Dry-run shows false success | Low | Medium | Test dry-run thoroughly, ensure transaction rollback |
| Handler registration fails silently | Low | Medium | Add logging for successful registration |

---

## 10. Documentation

### Code Documentation

- All classes and methods have comprehensive docstrings
- Docstrings include Args, Returns, Raises sections
- Examples provided for key methods
- Type hints for all parameters and return values

### User Documentation

Updates needed in **Sortie 4**:
- How to trigger migrations via NATS
- NATS message format examples
- Error code reference
- Dry-run usage guide

### Developer Documentation

Update **docs/DATABASE.md** with:
- MigrationExecutor class overview
- NATS handler architecture
- Locking mechanism explanation
- Transaction management details
- Error handling patterns

Update **docs/NATS_MESSAGES.md** with:
- db.migrate.<plugin>.apply message format
- db.migrate.<plugin>.rollback message format
- db.migrate.<plugin>.status message format
- Response schemas
- Error codes

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-Migration-Manager-Foundation.md](SPEC-Sortie-1-Migration-Manager-Foundation.md)

**Next**: 
- [SPEC-Sortie-3-Safety-Features-Validation.md](SPEC-Sortie-3-Safety-Features-Validation.md)
- [SPEC-Sortie-4-Documentation-Examples.md](SPEC-Sortie-4-Documentation-Examples.md)

**Parent PRD**: [PRD-Schema-Migrations.md](PRD-Schema-Migrations.md)

**Related Sprints**:
- Sprint 6a: NATS Event Bus (Quicksilver)
- Sprint 13: Row Operations Foundation
- Sprint 16: Data Migrations

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
