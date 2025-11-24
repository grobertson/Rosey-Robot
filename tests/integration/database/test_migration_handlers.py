#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for migration NATS handlers.

Tests the complete migration workflow through NATS messages:
apply, rollback, status operations with locking and transactions.

Sprint: 15 - Schema Migrations
Sortie: 2 - NATS Handlers & Execution
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from common.database import BotDatabase
from common.database_service import DatabaseService


# Mock NATS message for testing
class MockMsg:
    """Mock NATS message for testing handlers."""
    def __init__(self, subject: str, data: dict):
        self.subject = subject
        self.data = json.dumps(data).encode()
        self.response = None

    async def respond(self, data: bytes):
        """Store response for assertion."""
        self.response = json.loads(data.decode())


@pytest.fixture
async def test_db():
    """Create test database."""
    db = BotDatabase(':memory:')

    # Skip connect() verification (it queries tables we don't have)
    # Just mark as connected
    db._is_connected = True

    # Create plugin_schema_migrations table manually (Alembic not run in tests)
    async with db._get_session() as session:
        from sqlalchemy import text
        await session.execute(text("""
            CREATE TABLE plugin_schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at DATETIME NOT NULL,
                applied_by TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                execution_time_ms INTEGER NOT NULL,
                UNIQUE(plugin_name, version)
            )
        """))
        await session.commit()

    yield db

    await db.close()


@pytest.fixture
async def test_migrations(tmp_path):
    """Create test migration files."""
    plugin_dir = tmp_path / "test_plugin"
    migrations_dir = plugin_dir / "migrations"
    migrations_dir.mkdir(parents=True)

    # Migration 001 - create table
    (migrations_dir / "001_create_quotes_table.sql").write_text("""
-- UP
CREATE TABLE plugin_test_plugin_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- DOWN
DROP TABLE plugin_test_plugin_quotes;
""")

    # Migration 002 - add column
    (migrations_dir / "002_add_active_column.sql").write_text("""
-- UP
ALTER TABLE plugin_test_plugin_quotes ADD COLUMN active INTEGER DEFAULT 1;

-- DOWN
-- SQLite doesn't support DROP COLUMN easily, so recreate table
CREATE TABLE plugin_test_plugin_quotes_backup AS SELECT id, text, author, created_at FROM plugin_test_plugin_quotes;
DROP TABLE plugin_test_plugin_quotes;
ALTER TABLE plugin_test_plugin_quotes_backup RENAME TO plugin_test_plugin_quotes;
""")

    # Migration 003 - add index
    (migrations_dir / "003_add_author_index.sql").write_text("""
-- UP
CREATE INDEX idx_test_plugin_quotes_author ON plugin_test_plugin_quotes(author);

-- DOWN
DROP INDEX idx_test_plugin_quotes_author;
""")

    return plugin_dir


@pytest.fixture
async def db_service(test_db, test_migrations):
    """Create database service with mock NATS."""
    # Mock NATS client
    nats_mock = MagicMock()
    nats_mock.subscribe = AsyncMock(return_value=MagicMock())

    # Create service
    service = DatabaseService(nats_mock, ':memory:')
    service.db = test_db  # Use test database

    # Override migration_manager to use test migrations
    service.migration_manager.base_path = test_migrations.parent

    yield service


# ==================== Apply Migration Tests ====================

@pytest.mark.asyncio
class TestMigrateApply:
    """Test rosey.db.migrate.{plugin}.apply handler."""

    async def test_apply_single_migration(self, db_service):
        """Apply single migration successfully."""
        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 1, 'applied_by': 'admin'}
        )

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is True
        assert len(msg.response['applied']) == 1
        assert msg.response['applied'][0]['version'] == 1
        assert msg.response['applied'][0]['name'] == 'create_quotes_table'
        assert msg.response['current_version'] == 1
        assert 'execution_time_ms' in msg.response['applied'][0]

    async def test_apply_multiple_migrations(self, db_service):
        """Apply multiple migrations in sequence."""
        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 3, 'applied_by': 'admin'}
        )

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is True
        assert len(msg.response['applied']) == 3
        assert msg.response['current_version'] == 3

        # Verify all migrations applied in order
        versions = [m['version'] for m in msg.response['applied']]
        assert versions == [1, 2, 3]

    async def test_apply_all_pending(self, db_service):
        """Apply all pending migrations when version not specified."""
        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'applied_by': 'system'}
        )

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is True
        assert len(msg.response['applied']) == 3
        assert msg.response['current_version'] == 3

    async def test_apply_no_pending_migrations(self, db_service):
        """Handle case with no pending migrations."""
        # Apply all migrations first
        msg1 = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {}
        )
        await db_service._handle_migrate_apply(msg1)

        # Try to apply again
        msg2 = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {}
        )
        await db_service._handle_migrate_apply(msg2)

        assert msg2.response['success'] is True
        assert len(msg2.response['applied']) == 0
        assert msg2.response['message'] == 'No pending migrations'
        assert msg2.response['current_version'] == 3

    async def test_apply_dry_run(self, db_service):
        """Dry-run mode previews without committing."""
        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 1, 'dry_run': True}
        )

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is True
        assert len(msg.response['applied']) == 1
        assert msg.response['message'] == 'Dry-run: migrations not committed'
        assert msg.response['current_version'] == 0  # Not updated

        # Verify migration not actually applied
        msg2 = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(msg2)
        assert msg2.response['current_version'] == 0

    async def test_apply_invalid_json(self, db_service):
        """Handle invalid JSON in request."""
        msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        msg.data = b'invalid json'

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is False
        assert msg.response['error']['code'] == 'INVALID_JSON'

    async def test_apply_concurrent_lock_timeout(self, db_service):
        """Concurrent migrations blocked by lock."""
        # Acquire lock
        lock = db_service._get_plugin_lock('test_plugin')
        await lock.acquire()

        try:
            # Attempt concurrent migration
            msg = MockMsg(
                'rosey.db.migrate.test_plugin.apply',
                {'version': 1}
            )

            await db_service._handle_migrate_apply(msg)

            assert msg.response['success'] is False
            assert msg.response['error']['code'] == 'LOCK_TIMEOUT'
            assert 'already in progress' in msg.response['error']['message']
        finally:
            lock.release()

    async def test_apply_partial_failure(self, db_service, test_migrations):
        """Handle migration failure mid-sequence."""
        # Create migration with invalid SQL
        migrations_dir = test_migrations / "migrations"
        (migrations_dir / "002_add_active_column.sql").write_text("""
-- UP
INVALID SQL SYNTAX HERE;

-- DOWN
SELECT 1;
""")

        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 3, 'applied_by': 'admin'}
        )

        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is False
        assert msg.response['error']['code'] == 'MIGRATION_FAILED'
        assert len(msg.response['applied']) == 1  # Only first migration succeeded
        assert msg.response['current_version'] == 1


# ==================== Rollback Migration Tests ====================

@pytest.mark.asyncio
class TestMigrateRollback:
    """Test rosey.db.migrate.{plugin}.rollback handler."""

    async def test_rollback_single_migration(self, db_service):
        """Rollback single migration successfully."""
        # Apply migrations first
        apply_msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 3}
        )
        await db_service._handle_migrate_apply(apply_msg)

        # Rollback one migration
        rollback_msg = MockMsg(
            'rosey.db.migrate.test_plugin.rollback',
            {'applied_by': 'admin'}
        )
        await db_service._handle_migrate_rollback(rollback_msg)

        assert rollback_msg.response['success'] is True
        assert len(rollback_msg.response['rolled_back']) == 1
        assert rollback_msg.response['rolled_back'][0]['version'] == 3
        assert rollback_msg.response['current_version'] == 2

    async def test_rollback_to_version(self, db_service):
        """Rollback to specific version."""
        # Apply all migrations
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        # Rollback to version 1
        rollback_msg = MockMsg(
            'rosey.db.migrate.test_plugin.rollback',
            {'version': 1, 'applied_by': 'admin'}
        )
        await db_service._handle_migrate_rollback(rollback_msg)

        assert rollback_msg.response['success'] is True
        assert len(rollback_msg.response['rolled_back']) == 2
        assert rollback_msg.response['current_version'] == 1

        # Verify rollback order (descending)
        versions = [m['version'] for m in rollback_msg.response['rolled_back']]
        assert versions == [3, 2]

    async def test_rollback_to_zero(self, db_service):
        """Rollback all migrations to version 0."""
        # Apply migrations
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        # Rollback all
        rollback_msg = MockMsg(
            'rosey.db.migrate.test_plugin.rollback',
            {'version': 0}
        )
        await db_service._handle_migrate_rollback(rollback_msg)

        assert rollback_msg.response['success'] is True
        assert len(rollback_msg.response['rolled_back']) == 3
        assert rollback_msg.response['current_version'] == 0

    async def test_rollback_no_migrations(self, db_service):
        """Handle rollback with no migrations to rollback."""
        msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {})
        await db_service._handle_migrate_rollback(msg)

        assert msg.response['success'] is True
        assert len(msg.response['rolled_back']) == 0
        assert msg.response['message'] == 'No migrations to rollback'
        assert msg.response['current_version'] == 0

    async def test_rollback_dry_run(self, db_service):
        """Dry-run rollback previews without committing."""
        # Apply migrations
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        # Dry-run rollback
        rollback_msg = MockMsg(
            'rosey.db.migrate.test_plugin.rollback',
            {'version': 1, 'dry_run': True}
        )
        await db_service._handle_migrate_rollback(rollback_msg)

        assert rollback_msg.response['success'] is True
        assert len(rollback_msg.response['rolled_back']) == 2
        assert rollback_msg.response['message'] == 'Dry-run: rollbacks not committed'

        # Verify migrations still applied
        status_msg = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(status_msg)
        assert status_msg.response['current_version'] == 3

    async def test_rollback_invalid_json(self, db_service):
        """Handle invalid JSON in request."""
        msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {})
        msg.data = b'not json'

        await db_service._handle_migrate_rollback(msg)

        assert msg.response['success'] is False
        assert msg.response['error']['code'] == 'INVALID_JSON'

    async def test_rollback_concurrent_lock_timeout(self, db_service):
        """Concurrent rollback blocked by lock."""
        lock = db_service._get_plugin_lock('test_plugin')
        await lock.acquire()

        try:
            msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {})
            await db_service._handle_migrate_rollback(msg)

            assert msg.response['success'] is False
            assert msg.response['error']['code'] == 'LOCK_TIMEOUT'
        finally:
            lock.release()


# ==================== Status Query Tests ====================

@pytest.mark.asyncio
class TestMigrateStatus:
    """Test rosey.db.migrate.{plugin}.status handler."""

    async def test_status_no_migrations(self, db_service):
        """Status with no migrations applied."""
        msg = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(msg)

        assert msg.response['success'] is True
        assert msg.response['current_version'] == 0
        assert len(msg.response['applied_migrations']) == 0
        assert len(msg.response['pending_migrations']) == 3

    async def test_status_with_applied_migrations(self, db_service):
        """Status shows applied and pending migrations."""
        # Apply first two migrations
        apply_msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 2}
        )
        await db_service._handle_migrate_apply(apply_msg)

        # Check status
        status_msg = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(status_msg)

        assert status_msg.response['success'] is True
        assert status_msg.response['current_version'] == 2
        assert len(status_msg.response['applied_migrations']) == 2
        assert len(status_msg.response['pending_migrations']) == 1

        # Verify applied migration details
        applied = status_msg.response['applied_migrations']
        assert applied[0]['version'] == 1
        assert applied[0]['name'] == 'create_quotes_table'
        assert applied[0]['applied_by'] == 'system'
        assert applied[0]['status'] == 'applied'
        assert 'applied_at' in applied[0]
        assert 'checksum' in applied[0]
        assert 'execution_time_ms' in applied[0]

        # Verify pending migration details
        pending = status_msg.response['pending_migrations']
        assert pending[0]['version'] == 3
        assert pending[0]['name'] == 'add_author_index'
        assert pending[0]['filename'] == '003_add_author_index.sql'

    async def test_status_all_applied(self, db_service):
        """Status with all migrations applied."""
        # Apply all migrations
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        # Check status
        status_msg = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(status_msg)

        assert status_msg.response['success'] is True
        assert status_msg.response['current_version'] == 3
        assert len(status_msg.response['applied_migrations']) == 3
        assert len(status_msg.response['pending_migrations']) == 0

    async def test_status_after_rollback(self, db_service):
        """Status reflects rolled back migrations."""
        # Apply and rollback
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        rollback_msg = MockMsg(
            'rosey.db.migrate.test_plugin.rollback',
            {'version': 1}
        )
        await db_service._handle_migrate_rollback(rollback_msg)

        # Check status
        status_msg = MockMsg('rosey.db.migrate.test_plugin.status', {})
        await db_service._handle_migrate_status(status_msg)

        assert status_msg.response['success'] is True
        assert status_msg.response['current_version'] == 1

        # Should show rolled_back status for those migrations
        applied = status_msg.response['applied_migrations']
        rollback_statuses = [m['status'] for m in applied if m['status'] == 'rolled_back']
        assert len(rollback_statuses) == 2


# ==================== Locking Tests ====================

@pytest.mark.asyncio
class TestMigrationLocking:
    """Test per-plugin locking mechanism."""

    async def test_get_plugin_lock_creates_lock(self, db_service):
        """get_plugin_lock creates lock for plugin."""
        lock1 = db_service._get_plugin_lock('plugin1')
        assert isinstance(lock1, type(pytest.importorskip('asyncio').Lock()))

    async def test_get_plugin_lock_returns_same_lock(self, db_service):
        """get_plugin_lock returns same lock for same plugin."""
        lock1 = db_service._get_plugin_lock('plugin1')
        lock2 = db_service._get_plugin_lock('plugin1')
        assert lock1 is lock2

    async def test_get_plugin_lock_different_plugins(self, db_service):
        """Different plugins get different locks."""
        lock1 = db_service._get_plugin_lock('plugin1')
        lock2 = db_service._get_plugin_lock('plugin2')
        assert lock1 is not lock2

    async def test_apply_blocks_rollback(self, db_service):
        """Apply operation blocks concurrent rollback."""
        # Apply migrations first
        apply_msg1 = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg1)

        # Acquire lock
        lock = db_service._get_plugin_lock('test_plugin')
        await lock.acquire()

        try:
            # Attempt rollback while locked
            rollback_msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {})
            await db_service._handle_migrate_rollback(rollback_msg)

            assert rollback_msg.response['success'] is False
            assert rollback_msg.response['error']['code'] == 'LOCK_TIMEOUT'
        finally:
            lock.release()

    async def test_different_plugins_dont_block(self, db_service, test_migrations):
        """Migrations on different plugins don't block each other."""
        # Create second plugin
        plugin2_dir = test_migrations.parent / "plugin2"
        migrations2_dir = plugin2_dir / "migrations"
        migrations2_dir.mkdir(parents=True)
        (migrations2_dir / "001_init.sql").write_text("-- UP\nSELECT 1;\n-- DOWN\nSELECT 1;")

        # Lock plugin1
        lock1 = db_service._get_plugin_lock('test_plugin')
        await lock1.acquire()

        try:
            # plugin2 should work fine
            msg2 = MockMsg('rosey.db.migrate.plugin2.apply', {})
            await db_service._handle_migrate_apply(msg2)

            # Both operations should succeed
            assert msg2.response['success'] is True
        finally:
            lock1.release()


# ==================== Transaction Safety Tests ====================

@pytest.mark.asyncio
class TestTransactionSafety:
    """Test transaction rollback on failures."""

    async def test_apply_failure_rolls_back_transaction(self, db_service, test_migrations):
        """Failed migration doesn't leave partial changes."""
        # Create migration with error mid-execution
        migrations_dir = test_migrations / "migrations"
        (migrations_dir / "001_create_quotes_table.sql").write_text("""
-- UP
CREATE TABLE test_table (id INTEGER);
INVALID SQL HERE;
INSERT INTO test_table VALUES (1);

-- DOWN
DROP TABLE test_table;
""")

        msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is False

        # Verify table wasn't created (transaction rolled back)
        async with db_service.db._get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
            ))
            assert result.scalar() is None

    async def test_rollback_failure_preserves_state(self, db_service, test_migrations):
        """Failed rollback doesn't corrupt database state."""
        # Apply migration
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {'version': 1})
        await db_service._handle_migrate_apply(apply_msg)

        # Create rollback with error
        migrations_dir = test_migrations / "migrations"
        (migrations_dir / "001_create_quotes_table.sql").write_text("""
-- UP
CREATE TABLE plugin_test_plugin_quotes (id INTEGER);

-- DOWN
INVALID SQL HERE;
DROP TABLE plugin_test_plugin_quotes;
""")

        rollback_msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {})
        await db_service._handle_migrate_rollback(rollback_msg)

        assert rollback_msg.response['success'] is False

        # Verify table still exists (rollback transaction failed, but apply preserved)
        async with db_service.db._get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='plugin_test_plugin_quotes'"
            ))
            assert result.scalar() is not None

    async def test_dry_run_always_rolls_back(self, db_service):
        """Dry-run mode always rolls back, even on success."""
        msg = MockMsg(
            'rosey.db.migrate.test_plugin.apply',
            {'version': 1, 'dry_run': True}
        )
        await db_service._handle_migrate_apply(msg)

        assert msg.response['success'] is True

        # Verify table not created
        async with db_service.db._get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='plugin_test_plugin_quotes'"
            ))
            assert result.scalar() is None


# ==================== Helper Methods Tests ====================

@pytest.mark.asyncio
class TestHelperMethods:
    """Test helper methods used by handlers."""

    async def test_get_current_version_no_migrations(self, db_service):
        """get_current_version returns 0 for no migrations."""
        version = await db_service._get_current_version('test_plugin')
        assert version == 0

    async def test_get_current_version_with_migrations(self, db_service):
        """get_current_version returns highest applied version."""
        # Apply migrations
        msg = MockMsg('rosey.db.migrate.test_plugin.apply', {'version': 2})
        await db_service._handle_migrate_apply(msg)

        version = await db_service._get_current_version('test_plugin')
        assert version == 2

    async def test_get_current_version_ignores_failed(self, db_service):
        """get_current_version ignores failed migrations."""
        # Apply migration
        msg = MockMsg('rosey.db.migrate.test_plugin.apply', {'version': 1})
        await db_service._handle_migrate_apply(msg)

        # Manually insert failed migration record
        async with db_service.db._get_session() as session:
            from sqlalchemy import text
            await session.execute(text("""
                INSERT INTO plugin_schema_migrations 
                (plugin_name, version, name, checksum, applied_at, applied_by, status, execution_time_ms)
                VALUES ('test_plugin', 2, 'failed', 'abc', datetime('now'), 'test', 'failed', 100)
            """))
            await session.commit()

        # Should still return 1 (ignores failed)
        version = await db_service._get_current_version('test_plugin')
        assert version == 1

    async def test_get_current_version_ignores_rolled_back(self, db_service):
        """get_current_version ignores rolled back migrations."""
        # Apply and rollback
        apply_msg = MockMsg('rosey.db.migrate.test_plugin.apply', {})
        await db_service._handle_migrate_apply(apply_msg)

        rollback_msg = MockMsg('rosey.db.migrate.test_plugin.rollback', {'version': 1})
        await db_service._handle_migrate_rollback(rollback_msg)

        version = await db_service._get_current_version('test_plugin')
        assert version == 1  # Last successfully applied
