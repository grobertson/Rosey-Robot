"""
Migration manager for plugin database schema evolution.

This module provides the MigrationManager class which handles:
- Discovery of migration files in plugin directories
- Parsing of migration files (extracting UP/DOWN SQL sections)
- Checksum computation for tamper detection
- Calculation of pending and rollback migrations

Migration files follow the naming convention: NNN_description.sql
Example: 001_create_quotes.sql, 002_add_rating.sql

File format:
    -- UP
    CREATE TABLE my_table (id SERIAL PRIMARY KEY);

    -- DOWN
    DROP TABLE my_table;
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional

from .migration import Migration, AppliedMigration

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Manages migration file discovery, parsing, and metadata.

    Responsibilities:
    - Discover migration files in plugin directories
    - Parse migration files (extract UP/DOWN sections)
    - Compute checksums for tamper detection
    - Calculate pending and rollback migrations

    Does NOT execute migrations (see MigrationExecutor in Sortie 2).

    Example:
        >>> manager = MigrationManager(Path('/opt/rosey/plugins'))
        >>> migrations = manager.discover_migrations('quote-db')
        >>> print(migrations)
        [<Migration(v1, create_quotes)>, <Migration(v2, add_rating)>]
    """

    # Migration filename pattern: NNN_description.sql
    # Examples: 001_create_table.sql, 042_add_index.sql
    MIGRATION_PATTERN = re.compile(r'^(\d{3})_([a-z0-9_]+)\.sql$')

    # Section markers in migration files
    UP_MARKER = '-- UP'
    DOWN_MARKER = '-- DOWN'

    def __init__(self, plugins_base_dir: Path):
        """
        Initialize migration manager.

        Args:
            plugins_base_dir: Base directory containing plugin folders
                Example: /opt/rosey/plugins/
                Expected structure:
                    plugins/
                        quote-db/
                            migrations/
                                001_create_quotes.sql
                                002_add_rating.sql
                        trivia/
                            migrations/
                                001_create_questions.sql
        """
        self.plugins_base_dir = Path(plugins_base_dir)

    def discover_migrations(self, plugin_name: str) -> List[Migration]:
        """
        Discover all migration files for a plugin.

        Scans the plugin's migrations/ directory for files matching
        the pattern NNN_description.sql, parses them, and returns
        a sorted list by version number.

        Args:
            plugin_name: Name of the plugin (e.g., 'quote-db')

        Returns:
            List of Migration objects sorted by version ascending

        Raises:
            ValueError: If duplicate version numbers found

        Example:
            >>> manager = MigrationManager(Path('/opt/rosey/plugins'))
            >>> migrations = manager.discover_migrations('quote-db')
            >>> print(migrations)
            [<Migration(v1, create_quotes)>, <Migration(v2, add_rating)>]
        """
        migrations_dir = self.plugins_base_dir / plugin_name / 'migrations'

        if not migrations_dir.exists():
            logger.warning(
                f"No migrations directory for plugin '{plugin_name}'"
            )
            return []

        migrations = []
        versions_seen = set()

        for file_path in sorted(migrations_dir.glob('*.sql')):
            match = self.MIGRATION_PATTERN.match(file_path.name)
            if not match:
                logger.warning(
                    f"Skipping invalid migration filename: {file_path.name}"
                )
                continue

            version_str, name = match.groups()
            version = int(version_str)

            # Check for duplicate versions
            if version in versions_seen:
                raise ValueError(
                    f"Duplicate migration version {version} found in "
                    f"plugin '{plugin_name}'"
                )
            versions_seen.add(version)

            # Parse migration file
            try:
                migration = self.parse_migration_file(file_path)
                migrations.append(migration)
                logger.debug(f"Discovered migration: {migration}")
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                raise

        return sorted(migrations)

    def parse_migration_file(self, file_path: Path) -> Migration:
        """
        Parse a migration file and extract UP/DOWN sections.

        Migration file format:
        ```sql
        -- UP
        CREATE TABLE my_table (id SERIAL PRIMARY KEY);
        CREATE INDEX idx_my_table_id ON my_table(id);

        -- DOWN
        DROP INDEX idx_my_table_id;
        DROP TABLE my_table;
        ```

        Args:
            file_path: Path to migration file

        Returns:
            Migration object with UP/DOWN SQL extracted

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If UP or DOWN section missing

        Example:
            >>> manager = MigrationManager(Path('/opt/rosey/plugins'))
            >>> migration = manager.parse_migration_file(
            ...     Path('001_create_table.sql')
            ... )
            >>> print(migration.up_sql)
            'CREATE TABLE my_table (id SERIAL PRIMARY KEY);'
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Migration file not found: {file_path}")

        # Read file content
        content = file_path.read_text(encoding='utf-8')

        # Extract version and name from filename
        match = self.MIGRATION_PATTERN.match(file_path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {file_path.name}")

        version_str, name = match.groups()
        version = int(version_str)

        # Parse UP and DOWN sections
        up_sql, down_sql = self._parse_sections(content, file_path.name)

        # Compute checksum
        checksum = self.compute_checksum(content)

        return Migration(
            version=version,
            name=name,
            filename=file_path.name,
            file_path=str(file_path.absolute()),
            up_sql=up_sql,
            down_sql=down_sql,
            checksum=checksum
        )

    def _parse_sections(
        self,
        content: str,
        filename: str
    ) -> tuple[str, str]:
        """
        Parse UP and DOWN sections from migration file content.

        Args:
            content: Full file content
            filename: Filename for error messages

        Returns:
            Tuple of (up_sql, down_sql)

        Raises:
            ValueError: If UP or DOWN marker missing
        """
        lines = content.split('\n')

        up_start = None
        down_start = None

        # Find section markers (case-insensitive)
        for i, line in enumerate(lines):
            line_stripped = line.strip().upper()
            if line_stripped == self.UP_MARKER:
                up_start = i + 1
            elif line_stripped == self.DOWN_MARKER:
                down_start = i + 1

        # Validate sections found
        if up_start is None:
            raise ValueError(
                f"Migration {filename} missing '{self.UP_MARKER}' marker"
            )

        if down_start is None:
            raise ValueError(
                f"Migration {filename} missing '{self.DOWN_MARKER}' marker"
            )

        if up_start >= down_start:
            raise ValueError(
                f"Migration {filename} has '{self.DOWN_MARKER}' before "
                f"'{self.UP_MARKER}' (UP at line {up_start}, "
                f"DOWN at line {down_start})"
            )

        # Extract SQL sections
        up_sql = '\n'.join(lines[up_start:down_start-1]).strip()
        down_sql = '\n'.join(lines[down_start:]).strip()

        return up_sql, down_sql

    def compute_checksum(self, content: str) -> str:
        """
        Compute SHA-256 checksum of migration file content.

        Used to detect file tampering after migrations are applied.
        If checksum changes, migration has been modified and should
        not be trusted.

        Args:
            content: Full file content including comments

        Returns:
            Hexadecimal SHA-256 hash (64 characters)

        Example:
            >>> manager = MigrationManager(Path('/opt/rosey/plugins'))
            >>> checksum = manager.compute_checksum(
            ...     "-- UP\\nCREATE TABLE...\\n-- DOWN\\nDROP TABLE...\\n"
            ... )
            >>> len(checksum)
            64
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_pending_migrations(
        self,
        plugin_name: str,
        current_version: int,
        target_version: int,
        applied_migrations: Optional[List[AppliedMigration]] = None
    ) -> List[Migration]:
        """
        Calculate migrations to apply to reach target version.

        Args:
            plugin_name: Name of plugin
            current_version: Current schema version (0 if never migrated)
            target_version: Desired schema version
            applied_migrations: Already applied migrations (for checksum
                verification, optional)

        Returns:
            List of migrations to apply, sorted by version ascending

        Raises:
            ValueError: If target_version < current_version
                (use get_rollback_migrations instead)

        Example:
            >>> # Current version: 2, target: 5
            >>> pending = manager.get_pending_migrations('quote-db', 2, 5)
            >>> print([m.version for m in pending])
            [3, 4, 5]
        """
        if target_version < current_version:
            raise ValueError(
                f"Target version {target_version} < current version "
                f"{current_version}. Use get_rollback_migrations() instead."
            )

        if target_version == current_version:
            logger.info(f"Already at target version {target_version}")
            return []

        # Discover all migrations
        all_migrations = self.discover_migrations(plugin_name)

        if not all_migrations:
            logger.warning(f"No migrations found for plugin '{plugin_name}'")
            return []

        # Filter to pending range
        pending = [
            m for m in all_migrations
            if current_version < m.version <= target_version
        ]

        # Verify checksums if applied migrations provided
        if applied_migrations:
            self._verify_checksums(pending, applied_migrations)

        return sorted(pending)

    def get_rollback_migrations(
        self,
        plugin_name: str,
        current_version: int,
        target_version: int,
        applied_migrations: List[AppliedMigration]
    ) -> List[Migration]:
        """
        Calculate migrations to rollback to reach target version.

        Returns migrations in REVERSE order (descending version)
        since rollbacks apply from newest to oldest.

        Args:
            plugin_name: Name of plugin
            current_version: Current schema version
            target_version: Desired schema version (older than current)
            applied_migrations: Already applied migrations (required)

        Returns:
            List of migrations to rollback, sorted by version DESCENDING

        Raises:
            ValueError: If target_version >= current_version
                (use get_pending_migrations instead)

        Example:
            >>> # Current version: 5, target: 2
            >>> rollback = manager.get_rollback_migrations(
            ...     'quote-db', 5, 2, [...]
            ... )
            >>> print([m.version for m in rollback])
            [5, 4, 3]  # Reverse order!
        """
        if target_version >= current_version:
            raise ValueError(
                f"Target version {target_version} >= current version "
                f"{current_version}. Use get_pending_migrations() instead."
            )

        if target_version < 0:
            raise ValueError(
                f"Target version cannot be negative: {target_version}"
            )

        # Discover all migrations
        all_migrations = self.discover_migrations(plugin_name)

        # Filter to rollback range
        to_rollback = [
            m for m in all_migrations
            if target_version < m.version <= current_version
        ]

        # Verify these migrations were actually applied
        applied_versions = {am.version for am in applied_migrations}
        for migration in to_rollback:
            if migration.version not in applied_versions:
                raise ValueError(
                    f"Cannot rollback migration {migration.version} - "
                    f"not applied"
                )

        # Return in REVERSE order (newest first)
        return sorted(to_rollback, reverse=True)

    def _verify_checksums(
        self,
        migrations: List[Migration],
        applied_migrations: List[AppliedMigration]
    ):
        """
        Verify migration checksums match applied versions.

        Args:
            migrations: Migrations from filesystem
            applied_migrations: Migrations from database

        Raises:
            ValueError: If checksum mismatch detected (file was modified
                after being applied)
        """
        applied_checksums = {
            am.version: am.checksum for am in applied_migrations
        }

        for migration in migrations:
            if migration.version in applied_checksums:
                expected = applied_checksums[migration.version]
                if migration.checksum != expected:
                    raise ValueError(
                        f"Checksum mismatch for migration {migration.version}! "
                        f"File has been modified after application. "
                        f"Expected: {expected}, Got: {migration.checksum}"
                    )

    def find_migration(self, plugin_name: str, version: int) -> Migration:
        """
        Find a specific migration by plugin name and version.

        Used for checksum verification when comparing file vs database.

        Args:
            plugin_name: Name of plugin
            version: Migration version number

        Returns:
            Migration object

        Raises:
            FileNotFoundError: If migration file not found

        Example:
            >>> manager = MigrationManager('/path/to/plugins')
            >>> migration = manager.find_migration('quotes', 3)
            >>> print(migration.checksum)
        """
        all_migrations = self.discover_migrations(plugin_name)

        for migration in all_migrations:
            if migration.version == version:
                return migration

        raise FileNotFoundError(
            f"Migration not found: {plugin_name} version {version}"
        )
