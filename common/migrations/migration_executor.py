#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration executor with transaction management and tracking.

Executes plugin schema migrations safely within database transactions,
tracking results in plugin_schema_migrations table. Supports dry-run
mode for previewing changes without committing.

Sprint: 15 - Schema Migrations
Sortie: 2 - NATS Handlers & Execution
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.migrations.migration import Migration


class DryRunRollbackError(Exception):
    """Exception raised to trigger rollback during dry-run mode."""
    pass


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL string into individual statements.

    Handles semicolon-separated statements while preserving
    string literals and comments. Required for SQLite which
    can only execute one statement at a time.

    Args:
        sql: SQL string with one or more statements

    Returns:
        List of individual SQL statements (without trailing semicolons)
    """
    statements = []
    current = []
    in_string = False
    string_char = None

    lines = sql.split('\n')
    for line in lines:
        # Skip SQL comments
        stripped = line.strip()
        if stripped.startswith('--'):
            continue

        # Track string literals to avoid splitting on semicolons inside strings
        for i, char in enumerate(line):
            if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            if char == ';' and not in_string:
                # End of statement
                current.append(line[:i])
                stmt = '\n'.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                # Keep remainder of line for next statement
                if i + 1 < len(line):
                    remainder = line[i+1:].strip()
                    if remainder and not remainder.startswith('--'):
                        current.append(remainder)
                break
        else:
            # No semicolon found, add whole line
            current.append(line)

    # Add final statement if any
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements


@dataclass
class MigrationResult:
    """
    Result of migration execution.

    Attributes:
        success: Whether migration completed successfully
        version: Migration version that was executed
        execution_time_ms: Execution time in milliseconds
        error_message: Error message if failed (None if success)
    """
    success: bool
    version: int
    execution_time_ms: int
    error_message: Optional[str] = None


class MigrationExecutor:
    """
    Executes plugin schema migrations with transaction safety.

    Wraps SQL execution in transactions, tracks results in
    plugin_schema_migrations table, supports dry-run previews.

    All operations are atomic: either fully applied or fully rolled back.

    Attributes:
        database: BotDatabase instance for connection management
        logger: Logger for execution tracking

    Example:
        executor = MigrationExecutor(database)

        # Apply migration
        result = await executor.apply_migration(
            session=session,
            plugin_name='quotes',
            migration=migration,
            applied_by='admin',
            dry_run=False
        )

        # Rollback migration
        result = await executor.rollback_migration(
            session=session,
            plugin_name='quotes',
            migration=migration,
            applied_by='admin'
        )
    """

    def __init__(self, database):
        """
        Initialize migration executor.

        Args:
            database: BotDatabase instance
        """
        self.database = database
        self.logger = logging.getLogger(__name__)

    async def apply_migration(
        self,
        session: AsyncSession,
        plugin_name: str,
        migration: Migration,
        applied_by: str = 'system',
        dry_run: bool = False
    ) -> MigrationResult:
        """
        Apply migration UP section to database.

        Executes migration SQL within session transaction. If dry_run=True,
        raises DryRunRollbackError after execution to trigger automatic rollback.

        Records result in plugin_schema_migrations table (except for dry-run).

        Args:
            session: Active database session (managed by caller)
            plugin_name: Plugin identifier
            migration: Migration to apply
            applied_by: User/system applying migration
            dry_run: If True, execute but don't commit (preview mode)

        Returns:
            MigrationResult with success status and execution time

        Raises:
            DryRunRollbackError: If dry_run=True (triggers transaction rollback)
            Exception: On SQL execution failure

        Example:
            async with database._get_session() as session:
                result = await executor.apply_migration(
                    session=session,
                    plugin_name='quotes',
                    migration=migration,
                    applied_by='admin',
                    dry_run=False
                )
        """
        start_time = time.time()
        error_message = None

        try:
            self.logger.info(
                'Applying migration %s v%03d for plugin %s%s',
                migration.name,
                migration.version,
                plugin_name,
                ' (DRY RUN)' if dry_run else ''
            )

            # Execute UP section (split into individual statements for SQLite)
            statements = _split_sql_statements(migration.up_sql)
            for stmt in statements:
                if stmt.strip():  # Skip empty statements
                    await session.execute(text(stmt))

            execution_time_ms = int((time.time() - start_time) * 1000)

            if dry_run:
                self.logger.info(
                    'Dry-run complete for %s v%03d (%dms) - rolling back',
                    migration.name,
                    migration.version,
                    execution_time_ms
                )
                # Raise exception to trigger rollback
                raise DryRunRollbackError('Dry-run mode: rolling back transaction')

            # Record successful migration
            await self._record_migration(
                session=session,
                plugin_name=plugin_name,
                migration=migration,
                applied_by=applied_by,
                status='applied',
                error_message=None,
                execution_time_ms=execution_time_ms
            )

            self.logger.info(
                'Applied migration %s v%03d for plugin %s (%dms)',
                migration.name,
                migration.version,
                plugin_name,
                execution_time_ms
            )

            return MigrationResult(
                success=True,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message=None
            )

        except DryRunRollbackError:
            # Expected in dry-run mode
            execution_time_ms = int((time.time() - start_time) * 1000)
            return MigrationResult(
                success=True,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message='Dry-run: transaction rolled back'
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)

            self.logger.error(
                'Failed to apply migration %s v%03d for plugin %s: %s',
                migration.name,
                migration.version,
                plugin_name,
                error_message
            )

            # Record failed migration (if not dry-run)
            if not dry_run:
                try:
                    await self._record_migration(
                        session=session,
                        plugin_name=plugin_name,
                        migration=migration,
                        applied_by=applied_by,
                        status='failed',
                        error_message=error_message,
                        execution_time_ms=execution_time_ms
                    )
                except Exception as record_error:
                    self.logger.error(
                        'Failed to record migration failure: %s',
                        record_error
                    )

            return MigrationResult(
                success=False,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message=error_message
            )

    async def rollback_migration(
        self,
        session: AsyncSession,
        plugin_name: str,
        migration: Migration,
        applied_by: str = 'system',
        dry_run: bool = False
    ) -> MigrationResult:
        """
        Rollback migration DOWN section from database.

        Executes migration DOWN SQL within session transaction. If dry_run=True,
        raises DryRunRollbackError after execution to trigger automatic rollback.

        Records result in plugin_schema_migrations table (except for dry-run).

        Args:
            session: Active database session (managed by caller)
            plugin_name: Plugin identifier
            migration: Migration to rollback
            applied_by: User/system rolling back migration
            dry_run: If True, execute but don't commit (preview mode)

        Returns:
            MigrationResult with success status and execution time

        Raises:
            DryRunRollbackError: If dry_run=True (triggers transaction rollback)
            Exception: On SQL execution failure

        Example:
            async with database._get_session() as session:
                result = await executor.rollback_migration(
                    session=session,
                    plugin_name='quotes',
                    migration=migration,
                    applied_by='admin',
                    dry_run=False
                )
        """
        start_time = time.time()
        error_message = None

        try:
            self.logger.info(
                'Rolling back migration %s v%03d for plugin %s%s',
                migration.name,
                migration.version,
                plugin_name,
                ' (DRY RUN)' if dry_run else ''
            )

            # Execute DOWN section (split into individual statements for SQLite)
            statements = _split_sql_statements(migration.down_sql)
            for stmt in statements:
                if stmt.strip():  # Skip empty statements
                    await session.execute(text(stmt))

            execution_time_ms = int((time.time() - start_time) * 1000)

            if dry_run:
                self.logger.info(
                    'Dry-run rollback complete for %s v%03d (%dms) - rolling back',
                    migration.name,
                    migration.version,
                    execution_time_ms
                )
                # Raise exception to trigger rollback
                raise DryRunRollbackError('Dry-run mode: rolling back transaction')

            # Record rollback
            await self._record_migration(
                session=session,
                plugin_name=plugin_name,
                migration=migration,
                applied_by=applied_by,
                status='rolled_back',
                error_message=None,
                execution_time_ms=execution_time_ms
            )

            self.logger.info(
                'Rolled back migration %s v%03d for plugin %s (%dms)',
                migration.name,
                migration.version,
                plugin_name,
                execution_time_ms
            )

            return MigrationResult(
                success=True,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message=None
            )

        except DryRunRollbackError:
            # Expected in dry-run mode
            execution_time_ms = int((time.time() - start_time) * 1000)
            return MigrationResult(
                success=True,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message='Dry-run: transaction rolled back'
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)

            self.logger.error(
                'Failed to rollback migration %s v%03d for plugin %s: %s',
                migration.name,
                migration.version,
                plugin_name,
                error_message
            )

            # Record failed rollback (if not dry-run)
            if not dry_run:
                try:
                    await self._record_migration(
                        session=session,
                        plugin_name=plugin_name,
                        migration=migration,
                        applied_by=applied_by,
                        status='rollback_failed',
                        error_message=error_message,
                        execution_time_ms=execution_time_ms
                    )
                except Exception as record_error:
                    self.logger.error(
                        'Failed to record rollback failure: %s',
                        record_error
                    )

            return MigrationResult(
                success=False,
                version=migration.version,
                execution_time_ms=execution_time_ms,
                error_message=error_message
            )

    async def _record_migration(
        self,
        session: AsyncSession,
        plugin_name: str,
        migration: Migration,
        applied_by: str,
        status: str,
        error_message: Optional[str],
        execution_time_ms: int
    ) -> None:
        """
        Record migration execution in plugin_schema_migrations table.

        Creates new row with execution details. Does not commit session
        (caller manages transaction).

        Args:
            session: Active database session
            plugin_name: Plugin identifier
            migration: Migration that was executed
            applied_by: User/system that executed migration
            status: Execution status (applied, rolled_back, failed, rollback_failed)
            error_message: Error message if failed (None if success)
            execution_time_ms: Execution time in milliseconds

        Raises:
            Exception: On database insert failure
        """
        query = text("""
            INSERT INTO plugin_schema_migrations (
                plugin_name, version, name, checksum,
                applied_at, applied_by, status,
                error_message, execution_time_ms
            ) VALUES (
                :plugin_name, :version, :name, :checksum,
                :applied_at, :applied_by, :status,
                :error_message, :execution_time_ms
            )
        """)

        await session.execute(
            query,
            {
                'plugin_name': plugin_name,
                'version': migration.version,
                'name': migration.name,
                'checksum': migration.checksum,
                'applied_at': datetime.utcnow(),
                'applied_by': applied_by,
                'status': status,
                'error_message': error_message,
                'execution_time_ms': execution_time_ms
            }
        )

    async def ensure_migrations_table(self, session: AsyncSession) -> None:
        """Ensure plugin_schema_migrations table exists.

        Creates the migrations tracking table if it doesn't exist.
        Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).

        Args:
            session: Active database session

        Raises:
            Exception: On table creation failure
        """
        create_table_sql = text("""
            CREATE TABLE IF NOT EXISTS plugin_schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMP NOT NULL,
                applied_by TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                execution_time_ms INTEGER,
                UNIQUE(plugin_name, version)
            )
        """)

        await session.execute(create_table_sql)

        # Create index for faster queries
        create_index_sql = text("""
            CREATE INDEX IF NOT EXISTS idx_plugin_migrations_status
            ON plugin_schema_migrations(plugin_name, status)
        """)

        await session.execute(create_index_sql)
        await session.commit()

        self.logger.debug("Ensured plugin_schema_migrations table exists")
