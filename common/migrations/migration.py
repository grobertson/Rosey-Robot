"""
Database migration data models for plugin schema evolution.

This module defines the core data structures for managing database migrations:
- Migration: Represents a migration file from the filesystem
- AppliedMigration: Represents a migration that has been applied to the database

These models are used by MigrationManager to track schema changes over time.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Migration:
    """
    Represents a single migration file with metadata.

    A migration file contains UP and DOWN SQL sections:
    - UP: SQL statements to apply the migration (forward)
    - DOWN: SQL statements to rollback the migration (backward)

    Attributes:
        version: Migration version number (e.g., 1, 2, 3)
        name: Descriptive name from filename (e.g., 'create_quotes')
        filename: Full filename (e.g., '001_create_quotes.sql')
        file_path: Absolute path to migration file
        up_sql: SQL statements for applying migration
        down_sql: SQL statements for rolling back migration
        checksum: SHA-256 hash of file content

    Example:
        >>> migration = Migration(
        ...     version=1,
        ...     name='create_quotes',
        ...     filename='001_create_quotes.sql',
        ...     file_path='/plugins/quote-db/migrations/001_create_quotes.sql',
        ...     up_sql='CREATE TABLE quotes (id SERIAL PRIMARY KEY);',
        ...     down_sql='DROP TABLE quotes;',
        ...     checksum='a1b2c3d4...'
        ... )
        >>> print(migration)
        <Migration(v1, create_quotes)>
    """

    version: int
    name: str
    filename: str
    file_path: str
    up_sql: str
    down_sql: str
    checksum: str

    def __post_init__(self):
        """Validate migration after initialization."""
        if self.version < 1:
            raise ValueError(
                f"Migration version must be >= 1, got {self.version}"
            )

        if not self.up_sql.strip():
            raise ValueError(
                f"Migration {self.filename} has empty UP section"
            )

        if not self.down_sql.strip():
            raise ValueError(
                f"Migration {self.filename} has empty DOWN section"
            )

    def __lt__(self, other: 'Migration') -> bool:
        """
        Allow sorting migrations by version number.

        Example:
            >>> migrations = [Migration(version=3, ...), Migration(version=1, ...)]
            >>> sorted(migrations)
            [<Migration(v1, ...)>, <Migration(v3, ...)>]
        """
        if not isinstance(other, Migration):
            return NotImplemented
        return self.version < other.version

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Migration(v{self.version}, {self.name})>"


@dataclass
class AppliedMigration:
    """
    Represents a migration that has been applied to the database.

    This corresponds to a row in the plugin_schema_migrations table.
    Used to track which migrations have been executed and when.

    Attributes:
        plugin_name: Name of plugin this migration belongs to
        version: Migration version number
        name: Migration name
        checksum: Checksum at time of application
        applied_at: When migration was applied
        applied_by: User/system that applied it
        status: 'success' or 'failed'
        error_message: Error if migration failed (optional)
        execution_time_ms: Time taken to execute migration (optional)

    Example:
        >>> applied = AppliedMigration(
        ...     plugin_name='quote-db',
        ...     version=1,
        ...     name='create_quotes',
        ...     checksum='a1b2c3d4...',
        ...     applied_at=datetime(2025, 11, 24, 10, 0, 0),
        ...     applied_by='system',
        ...     status='success'
        ... )
        >>> print(applied)
        <AppliedMigration(quote-db v1, success)>
    """

    plugin_name: str
    version: int
    name: str
    checksum: str
    applied_at: datetime
    applied_by: str
    status: str = 'success'
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None

    def __post_init__(self):
        """Validate applied migration after initialization."""
        if self.status not in ('success', 'failed'):
            raise ValueError(
                f"AppliedMigration status must be 'success' or 'failed', "
                f"got '{self.status}'"
            )

        if self.version < 1:
            raise ValueError(
                f"Migration version must be >= 1, got {self.version}"
            )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<AppliedMigration({self.plugin_name} v{self.version}, "
            f"{self.status})>"
        )
