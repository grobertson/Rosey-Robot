# SPEC: Sortie 1 - Migration Manager Foundation

**Sprint**: 15 (Schema Migrations)  
**Sortie**: 1 of 4  
**Estimated Effort**: ~1.5 days (~12 hours)  
**Branch**: `feature/sprint-15-sortie-1-migration-manager`  
**Dependencies**: Sprint 13 (Row Operations Foundation)

---

## 1. Overview

Create the foundational migration management system including migration file discovery, parsing, checksum computation, and version tracking. This sortie establishes the core infrastructure for database schema evolution without the execution logic.

**What This Sortie Achieves**:
- Migration file discovery and parsing
- UP/DOWN SQL section extraction
- Migration checksum computation and verification
- Version tracking table (`plugin_schema_migrations`)
- Pending and rollback migration calculation
- Migration metadata management

---

## 2. Scope and Non-Goals

### In Scope
✅ `MigrationManager` class for migration file operations  
✅ `Migration` dataclass for migration metadata  
✅ Migration file discovery in plugin directories  
✅ UP/DOWN section parsing from SQL files  
✅ Checksum computation using SHA-256  
✅ `plugin_schema_migrations` table via Alembic  
✅ Pending migrations calculation  
✅ Rollback migrations calculation (reverse order)  
✅ 30+ unit tests covering all parsing scenarios

### Out of Scope
❌ Migration execution logic (Sortie 2)  
❌ NATS handlers (Sortie 2)  
❌ Transaction management (Sortie 2)  
❌ Safety validations (Sortie 3)  
❌ Dry-run mode (Sortie 2)  
❌ Migration locking (Sortie 2)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Migration file discovery must:
- Scan plugin `migrations/` directory
- Find files matching pattern `NNN_description.sql` (e.g., `001_create_table.sql`)
- Sort migrations by version number ascending
- Validate version number uniqueness
- Support gaps in version numbers (001, 003, 005 is valid)

**FR-2**: Migration file parsing must:
- Extract UP section (SQL to apply migration)
- Extract DOWN section (SQL to rollback migration)
- Handle multi-line SQL statements
- Preserve SQL comments
- Detect missing UP or DOWN sections
- Validate section markers (`-- UP`, `-- DOWN`)

**FR-3**: Checksum computation must:
- Use SHA-256 hash algorithm
- Hash the entire file content (including comments)
- Produce consistent checksums across platforms
- Detect file tampering/modification

**FR-4**: Version tracking table must:
- Record each applied migration
- Store plugin name, version, checksum, timestamps
- Support querying current version per plugin
- Track migration success/failure status

**FR-5**: Migration calculation must:
- Calculate pending migrations (not yet applied)
- Calculate rollback migrations (revert to target version)
- Return migrations in correct order (ascending for apply, descending for rollback)
- Handle edge cases (already at target version, no migrations)

### Non-Functional Requirements

**NFR-1 Performance**: Discovery and parsing <100ms for 50 migration files  
**NFR-2 Reliability**: Checksum changes detected 100% of the time  
**NFR-3 Maintainability**: Clear error messages for parsing failures  
**NFR-4 Testing**: 85%+ coverage of MigrationManager code

---

## 4. Technical Design

### 4.1 Migration Data Model

**File**: `common/database/migration.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Migration:
    """
    Represents a single migration file with metadata.
    
    Attributes:
        version: Migration version number (e.g., 1, 2, 3)
        name: Descriptive name from filename (e.g., 'create_quotes')
        filename: Full filename (e.g., '001_create_quotes.sql')
        file_path: Absolute path to migration file
        up_sql: SQL statements for applying migration
        down_sql: SQL statements for rolling back migration
        checksum: SHA-256 hash of file content
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
            raise ValueError(f"Migration version must be >= 1, got {self.version}")
        
        if not self.up_sql.strip():
            raise ValueError(f"Migration {self.filename} has empty UP section")
        
        if not self.down_sql.strip():
            raise ValueError(f"Migration {self.filename} has empty DOWN section")
    
    def __lt__(self, other):
        """Allow sorting migrations by version."""
        return self.version < other.version
    
    def __repr__(self):
        return f"<Migration(v{self.version}, {self.name})>"


@dataclass
class AppliedMigration:
    """
    Represents a migration that has been applied to database.
    
    Attributes:
        plugin_name: Name of plugin this migration belongs to
        version: Migration version number
        name: Migration name
        checksum: Checksum at time of application
        applied_at: When migration was applied
        applied_by: User/system that applied it
        status: 'success' or 'failed'
        error_message: Error if migration failed
    """
    plugin_name: str
    version: int
    name: str
    checksum: str
    applied_at: datetime
    applied_by: str
    status: str = 'success'
    error_message: Optional[str] = None
```

### 4.2 Migration Manager

**File**: `common/database/migration_manager.py`

```python
import hashlib
import re
from pathlib import Path
from typing import List, Optional, Dict
import logging

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
            FileNotFoundError: If plugin directory doesn't exist
            ValueError: If duplicate version numbers found
        
        Example:
            >>> manager = MigrationManager(Path('/opt/rosey/plugins'))
            >>> migrations = manager.discover_migrations('quote-db')
            >>> print(migrations)
            [<Migration(v1, create_quotes)>, <Migration(v2, add_rating)>]
        """
        migrations_dir = self.plugins_base_dir / plugin_name / 'migrations'
        
        if not migrations_dir.exists():
            logger.warning(f"No migrations directory for plugin '{plugin_name}'")
            return []
        
        migrations = []
        versions_seen = set()
        
        for file_path in sorted(migrations_dir.glob('*.sql')):
            match = self.MIGRATION_PATTERN.match(file_path.name)
            if not match:
                logger.warning(f"Skipping invalid migration filename: {file_path.name}")
                continue
            
            version_str, name = match.groups()
            version = int(version_str)
            
            # Check for duplicate versions
            if version in versions_seen:
                raise ValueError(
                    f"Duplicate migration version {version} found in plugin '{plugin_name}'"
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
            >>> migration = manager.parse_migration_file(Path('001_create_table.sql'))
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
    
    def _parse_sections(self, content: str, filename: str) -> tuple[str, str]:
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
        
        # Find section markers
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped == self.UP_MARKER:
                up_start = i + 1
            elif line_stripped == self.DOWN_MARKER:
                down_start = i + 1
        
        # Validate sections found
        if up_start is None:
            raise ValueError(f"Migration {filename} missing '-- UP' marker")
        
        if down_start is None:
            raise ValueError(f"Migration {filename} missing '-- DOWN' marker")
        
        if up_start >= down_start:
            raise ValueError(
                f"Migration {filename} has '-- DOWN' before '-- UP' "
                f"(UP at line {up_start}, DOWN at line {down_start})"
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
            >>> checksum = manager.compute_checksum("-- UP\\nCREATE TABLE...\\n-- DOWN\\nDROP TABLE...\\n")
            >>> print(len(checksum))
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
            applied_migrations: Already applied migrations (for checksum verification)
        
        Returns:
            List of migrations to apply, sorted by version ascending
        
        Raises:
            ValueError: If target_version < current_version (use rollback instead)
        
        Example:
            >>> # Current version: 2, target: 5
            >>> pending = manager.get_pending_migrations('quote-db', 2, 5)
            >>> print([m.version for m in pending])
            [3, 4, 5]
        """
        if target_version < current_version:
            raise ValueError(
                f"Target version {target_version} < current version {current_version}. "
                f"Use get_rollback_migrations() instead."
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
            applied_migrations: Already applied migrations (required for rollback)
        
        Returns:
            List of migrations to rollback, sorted by version DESCENDING
        
        Raises:
            ValueError: If target_version >= current_version (use apply instead)
        
        Example:
            >>> # Current version: 5, target: 2
            >>> rollback = manager.get_rollback_migrations('quote-db', 5, 2, [...])
            >>> print([m.version for m in rollback])
            [5, 4, 3]  # Reverse order!
        """
        if target_version >= current_version:
            raise ValueError(
                f"Target version {target_version} >= current version {current_version}. "
                f"Use get_pending_migrations() instead."
            )
        
        if target_version < 0:
            raise ValueError(f"Target version cannot be negative: {target_version}")
        
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
                    f"Cannot rollback migration {migration.version} - not applied"
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
            ValueError: If checksum mismatch detected
        """
        applied_checksums = {am.version: am.checksum for am in applied_migrations}
        
        for migration in migrations:
            if migration.version in applied_checksums:
                expected = applied_checksums[migration.version]
                if migration.checksum != expected:
                    raise ValueError(
                        f"Checksum mismatch for migration {migration.version}! "
                        f"File has been modified after application. "
                        f"Expected: {expected}, Got: {migration.checksum}"
                    )
```

### 4.3 Database Schema - Tracking Table

**File**: `alembic/versions/XXX_add_plugin_schema_migrations.py`

```python
"""add plugin schema migrations tracking table

Revision ID: XXX_plugin_schema_migrations
Revises: <previous_revision>
Create Date: 2025-11-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'XXX_plugin_schema_migrations'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create plugin_schema_migrations table."""
    op.create_table(
        'plugin_schema_migrations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('plugin_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('applied_by', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
    )
    
    # Unique constraint: one migration per plugin per version
    op.create_index(
        'idx_plugin_schema_migrations_unique',
        'plugin_schema_migrations',
        ['plugin_name', 'version'],
        unique=True
    )
    
    # Index for querying current version
    op.create_index(
        'idx_plugin_schema_migrations_plugin',
        'plugin_schema_migrations',
        ['plugin_name', 'applied_at']
    )


def downgrade() -> None:
    """Drop plugin_schema_migrations table."""
    op.drop_index('idx_plugin_schema_migrations_plugin', table_name='plugin_schema_migrations')
    op.drop_index('idx_plugin_schema_migrations_unique', table_name='plugin_schema_migrations')
    op.drop_table('plugin_schema_migrations')
```

**Table Schema**:
```sql
CREATE TABLE plugin_schema_migrations (
    id SERIAL PRIMARY KEY,
    plugin_name VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    applied_by VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'success' or 'failed'
    error_message TEXT,
    execution_time_ms INTEGER,
    CONSTRAINT unique_plugin_version UNIQUE (plugin_name, version)
);

CREATE INDEX idx_plugin_schema_migrations_plugin ON plugin_schema_migrations(plugin_name, applied_at);
```

---

## 5. Implementation Steps

### Step 1: Create Migration Data Models
1. Create `common/database/migration.py`
2. Define `Migration` dataclass with validation
3. Define `AppliedMigration` dataclass
4. Add `__lt__()` for sorting migrations
5. Add `__repr__()` for debugging

### Step 2: Create MigrationManager Class
1. Create `common/database/migration_manager.py`
2. Implement `__init__()` with plugins directory
3. Define `MIGRATION_PATTERN` regex constant
4. Define `UP_MARKER` and `DOWN_MARKER` constants

### Step 3: Implement Migration Discovery
1. Implement `discover_migrations()` method
2. Scan plugin `migrations/` directory
3. Filter files by regex pattern
4. Detect duplicate version numbers
5. Parse each migration file
6. Return sorted list

### Step 4: Implement Migration Parsing
1. Implement `parse_migration_file()` method
2. Read file content
3. Extract version and name from filename
4. Call `_parse_sections()` to extract UP/DOWN
5. Compute checksum
6. Return Migration object

### Step 5: Implement Section Parsing
1. Implement `_parse_sections()` helper method
2. Find `-- UP` marker line number
3. Find `-- DOWN` marker line number
4. Validate markers exist and order correct
5. Extract SQL between markers
6. Return tuple of (up_sql, down_sql)

### Step 6: Implement Checksum Computation
1. Implement `compute_checksum()` method
2. Use SHA-256 hash algorithm
3. Hash entire file content (UTF-8 encoded)
4. Return hexadecimal digest

### Step 7: Implement Pending Migrations
1. Implement `get_pending_migrations()` method
2. Validate target >= current version
3. Discover all migrations
4. Filter to range (current < version <= target)
5. Sort ascending
6. Optionally verify checksums

### Step 8: Implement Rollback Migrations
1. Implement `get_rollback_migrations()` method
2. Validate target < current version
3. Discover all migrations
4. Filter to range (target < version <= current)
5. Verify migrations were applied
6. Sort DESCENDING (reverse order)

### Step 9: Implement Checksum Verification
1. Implement `_verify_checksums()` helper method
2. Build applied checksums dict
3. Compare migration checksums to applied
4. Raise error on mismatch

### Step 10: Create Alembic Migration
1. Generate migration: `alembic revision -m "add plugin schema migrations"`
2. Define `plugin_schema_migrations` table
3. Add unique constraint on (plugin_name, version)
4. Add indexes for queries
5. Implement downgrade()

### Step 11: Write Comprehensive Unit Tests
**File**: `tests/unit/database/test_migration_manager.py`

Test categories:
- **File Discovery**: Find migrations, skip invalid files, sort correctly
- **File Parsing**: Extract UP/DOWN, handle missing markers, preserve SQL
- **Checksum**: Consistent hashes, detect changes
- **Pending**: Calculate correct range, handle edge cases
- **Rollback**: Reverse order, validate applied
- **Error Handling**: Invalid files, duplicate versions, checksum mismatches

---

## 6. Testing Strategy

### 6.1 Unit Tests - Migration Discovery

**File**: `tests/unit/database/test_migration_manager.py`

```python
import pytest
from pathlib import Path
from common.database.migration_manager import MigrationManager
from common.database.migration import Migration

class TestMigrationDiscovery:
    """Test migration file discovery."""
    
    @pytest.fixture
    def temp_plugins_dir(self, tmp_path):
        """Create temporary plugin directory structure."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        # Create quote-db plugin with migrations
        quote_db = plugins_dir / "quote-db" / "migrations"
        quote_db.mkdir(parents=True)
        
        # Create valid migration files
        (quote_db / "001_create_quotes.sql").write_text(
            "-- UP\nCREATE TABLE quotes (id SERIAL);\n-- DOWN\nDROP TABLE quotes;\n"
        )
        (quote_db / "002_add_rating.sql").write_text(
            "-- UP\nALTER TABLE quotes ADD COLUMN rating INT;\n-- DOWN\nALTER TABLE quotes DROP COLUMN rating;\n"
        )
        (quote_db / "005_add_index.sql").write_text(  # Gap in versions - OK
            "-- UP\nCREATE INDEX idx_rating ON quotes(rating);\n-- DOWN\nDROP INDEX idx_rating;\n"
        )
        
        # Create invalid filename (should be skipped)
        (quote_db / "invalid_name.sql").write_text("-- UP\nSELECT 1;\n-- DOWN\nSELECT 1;\n")
        
        return plugins_dir
    
    def test_discover_migrations_success(self, temp_plugins_dir):
        """Test discovering valid migrations."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        assert len(migrations) == 3
        assert migrations[0].version == 1
        assert migrations[0].name == 'create_quotes'
        assert migrations[1].version == 2
        assert migrations[2].version == 5  # Gap OK
    
    def test_discover_migrations_sorted(self, temp_plugins_dir):
        """Test migrations returned in version order."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        versions = [m.version for m in migrations]
        assert versions == sorted(versions)
    
    def test_discover_migrations_empty_directory(self, tmp_path):
        """Test discovering when no migrations directory exists."""
        manager = MigrationManager(tmp_path)
        migrations = manager.discover_migrations('nonexistent')
        
        assert migrations == []
    
    def test_discover_migrations_skips_invalid_filenames(self, temp_plugins_dir):
        """Test invalid filenames are skipped."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        filenames = [m.filename for m in migrations]
        assert 'invalid_name.sql' not in filenames
    
    def test_discover_migrations_duplicate_version(self, tmp_path):
        """Test error on duplicate version numbers."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test" / "migrations"
        plugin_dir.mkdir(parents=True)
        
        # Create two migrations with same version
        (plugin_dir / "001_first.sql").write_text("-- UP\nSELECT 1;\n-- DOWN\nSELECT 1;\n")
        (plugin_dir / "001_duplicate.sql").write_text("-- UP\nSELECT 2;\n-- DOWN\nSELECT 2;\n")
        
        manager = MigrationManager(plugins_dir)
        
        with pytest.raises(ValueError, match="Duplicate migration version 1"):
            manager.discover_migrations('test')


class TestMigrationParsing:
    """Test migration file parsing."""
    
    def test_parse_migration_file_success(self, tmp_path):
        """Test parsing valid migration file."""
        migration_file = tmp_path / "001_create_table.sql"
        migration_file.write_text("""
-- UP
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL
);
CREATE INDEX idx_users_username ON users(username);

-- DOWN
DROP INDEX idx_users_username;
DROP TABLE users;
""")
        
        manager = MigrationManager(tmp_path.parent)
        migration = manager.parse_migration_file(migration_file)
        
        assert migration.version == 1
        assert migration.name == 'create_table'
        assert 'CREATE TABLE users' in migration.up_sql
        assert 'DROP TABLE users' in migration.down_sql
        assert len(migration.checksum) == 64  # SHA-256 hex digest
    
    def test_parse_migration_missing_up_marker(self, tmp_path):
        """Test error when UP marker missing."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("CREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n")
        
        manager = MigrationManager(tmp_path.parent)
        
        with pytest.raises(ValueError, match="missing '-- UP' marker"):
            manager.parse_migration_file(migration_file)
    
    def test_parse_migration_missing_down_marker(self, tmp_path):
        """Test error when DOWN marker missing."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("-- UP\nCREATE TABLE test;\n")
        
        manager = MigrationManager(tmp_path.parent)
        
        with pytest.raises(ValueError, match="missing '-- DOWN' marker"):
            manager.parse_migration_file(migration_file)
    
    def test_parse_migration_markers_wrong_order(self, tmp_path):
        """Test error when DOWN comes before UP."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("-- DOWN\nDROP TABLE test;\n-- UP\nCREATE TABLE test;\n")
        
        manager = MigrationManager(tmp_path.parent)
        
        with pytest.raises(ValueError, match="has '-- DOWN' before '-- UP'"):
            manager.parse_migration_file(migration_file)
    
    def test_parse_migration_empty_up_section(self, tmp_path):
        """Test error when UP section is empty."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("-- UP\n\n-- DOWN\nDROP TABLE test;\n")
        
        manager = MigrationManager(tmp_path.parent)
        
        with pytest.raises(ValueError, match="has empty UP section"):
            manager.parse_migration_file(migration_file)
    
    def test_parse_migration_preserves_comments(self, tmp_path):
        """Test SQL comments are preserved."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("""
-- UP
-- This creates the users table
CREATE TABLE users (id SERIAL);

-- DOWN
-- This drops the users table
DROP TABLE users;
""")
        
        manager = MigrationManager(tmp_path.parent)
        migration = manager.parse_migration_file(migration_file)
        
        assert '-- This creates the users table' in migration.up_sql
        assert '-- This drops the users table' in migration.down_sql


class TestChecksumComputation:
    """Test checksum computation."""
    
    def test_compute_checksum_consistent(self, tmp_path):
        """Test checksum is consistent for same content."""
        manager = MigrationManager(tmp_path)
        
        content = "-- UP\nCREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        
        checksum1 = manager.compute_checksum(content)
        checksum2 = manager.compute_checksum(content)
        
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA-256 hex = 64 chars
    
    def test_compute_checksum_detects_changes(self, tmp_path):
        """Test checksum changes when content changes."""
        manager = MigrationManager(tmp_path)
        
        content1 = "-- UP\nCREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        content2 = "-- UP\nCREATE TABLE test2;\n-- DOWN\nDROP TABLE test2;\n"
        
        checksum1 = manager.compute_checksum(content1)
        checksum2 = manager.compute_checksum(content2)
        
        assert checksum1 != checksum2
    
    def test_compute_checksum_whitespace_sensitive(self, tmp_path):
        """Test checksum changes with whitespace changes."""
        manager = MigrationManager(tmp_path)
        
        content1 = "-- UP\nCREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        content2 = "-- UP\nCREATE TABLE test;\n\n-- DOWN\nDROP TABLE test;\n"  # Extra newline
        
        checksum1 = manager.compute_checksum(content1)
        checksum2 = manager.compute_checksum(content2)
        
        assert checksum1 != checksum2


class TestPendingMigrations:
    """Test pending migrations calculation."""
    
    @pytest.fixture
    def manager_with_migrations(self, tmp_path):
        """Create manager with test migrations."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test" / "migrations"
        plugin_dir.mkdir(parents=True)
        
        for version in [1, 2, 3, 4, 5]:
            (plugin_dir / f"{version:03d}_migration_{version}.sql").write_text(
                f"-- UP\nCREATE TABLE v{version};\n-- DOWN\nDROP TABLE v{version};\n"
            )
        
        return MigrationManager(plugins_dir)
    
    def test_get_pending_migrations_from_zero(self, manager_with_migrations):
        """Test pending migrations from version 0 (no migrations applied)."""
        pending = manager_with_migrations.get_pending_migrations('test', 0, 3)
        
        assert len(pending) == 3
        assert [m.version for m in pending] == [1, 2, 3]
    
    def test_get_pending_migrations_partial(self, manager_with_migrations):
        """Test pending migrations from partial application."""
        pending = manager_with_migrations.get_pending_migrations('test', 2, 4)
        
        assert len(pending) == 2
        assert [m.version for m in pending] == [3, 4]
    
    def test_get_pending_migrations_already_at_target(self, manager_with_migrations):
        """Test no pending when already at target."""
        pending = manager_with_migrations.get_pending_migrations('test', 3, 3)
        
        assert pending == []
    
    def test_get_pending_migrations_target_less_than_current(self, manager_with_migrations):
        """Test error when target < current (should use rollback)."""
        with pytest.raises(ValueError, match="Use get_rollback_migrations"):
            manager_with_migrations.get_pending_migrations('test', 4, 2)
    
    def test_get_pending_migrations_sorted_ascending(self, manager_with_migrations):
        """Test pending migrations returned in ascending order."""
        pending = manager_with_migrations.get_pending_migrations('test', 0, 5)
        
        versions = [m.version for m in pending]
        assert versions == sorted(versions)


class TestRollbackMigrations:
    """Test rollback migrations calculation."""
    
    @pytest.fixture
    def manager_with_applied(self, tmp_path):
        """Create manager with migrations and mock applied migrations."""
        from common.database.migration import AppliedMigration
        from datetime import datetime
        
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test" / "migrations"
        plugin_dir.mkdir(parents=True)
        
        applied = []
        for version in [1, 2, 3, 4, 5]:
            (plugin_dir / f"{version:03d}_migration_{version}.sql").write_text(
                f"-- UP\nCREATE TABLE v{version};\n-- DOWN\nDROP TABLE v{version};\n"
            )
            applied.append(AppliedMigration(
                plugin_name='test',
                version=version,
                name=f'migration_{version}',
                checksum='abc123',
                applied_at=datetime.utcnow(),
                applied_by='system'
            ))
        
        return MigrationManager(plugins_dir), applied
    
    def test_get_rollback_migrations_to_zero(self, manager_with_applied):
        """Test rollback all migrations."""
        manager, applied = manager_with_applied
        rollback = manager.get_rollback_migrations('test', 5, 0, applied)
        
        assert len(rollback) == 5
        assert [m.version for m in rollback] == [5, 4, 3, 2, 1]  # Descending!
    
    def test_get_rollback_migrations_partial(self, manager_with_applied):
        """Test rollback partial migrations."""
        manager, applied = manager_with_applied
        rollback = manager.get_rollback_migrations('test', 4, 2, applied)
        
        assert len(rollback) == 2
        assert [m.version for m in rollback] == [4, 3]  # Descending!
    
    def test_get_rollback_migrations_target_greater_than_current(self, manager_with_applied):
        """Test error when target >= current (should use apply)."""
        manager, applied = manager_with_applied
        
        with pytest.raises(ValueError, match="Use get_pending_migrations"):
            manager.get_rollback_migrations('test', 2, 4, applied)
    
    def test_get_rollback_migrations_not_applied(self, manager_with_applied):
        """Test error when trying to rollback unapplied migration."""
        from common.database.migration import AppliedMigration
        from datetime import datetime
        
        manager, _ = manager_with_applied
        
        # Only migrations 1-3 applied
        applied_partial = [
            AppliedMigration('test', v, f'migration_{v}', 'abc', datetime.utcnow(), 'system')
            for v in [1, 2, 3]
        ]
        
        # Try to rollback from 5 to 0 (but 4 and 5 not applied!)
        with pytest.raises(ValueError, match="Cannot rollback migration.*not applied"):
            manager.get_rollback_migrations('test', 5, 0, applied_partial)
    
    def test_get_rollback_migrations_sorted_descending(self, manager_with_applied):
        """Test rollback migrations returned in descending order."""
        manager, applied = manager_with_applied
        rollback = manager.get_rollback_migrations('test', 5, 1, applied)
        
        versions = [m.version for m in rollback]
        assert versions == sorted(versions, reverse=True)


class TestChecksumVerification:
    """Test checksum verification."""
    
    def test_verify_checksums_matching(self, tmp_path):
        """Test verification passes when checksums match."""
        from common.database.migration import Migration, AppliedMigration
        from datetime import datetime
        
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        checksum = manager.compute_checksum("test content")
        
        migrations = [Migration(1, 'test', '001_test.sql', '/path', 'UP', 'DOWN', checksum)]
        applied = [AppliedMigration('plugin', 1, 'test', checksum, datetime.utcnow(), 'system')]
        
        # Should not raise
        manager._verify_checksums(migrations, applied)
    
    def test_verify_checksums_mismatch(self, tmp_path):
        """Test verification fails when checksums don't match."""
        from common.database.migration import Migration, AppliedMigration
        from datetime import datetime
        
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        migrations = [Migration(1, 'test', '001_test.sql', '/path', 'UP', 'DOWN', 'checksum_new')]
        applied = [AppliedMigration('plugin', 1, 'test', 'checksum_old', datetime.utcnow(), 'system')]
        
        with pytest.raises(ValueError, match="Checksum mismatch.*File has been modified"):
            manager._verify_checksums(migrations, applied)
```

**Test Coverage Target**: 85%+ of MigrationManager code

**Command**:
```bash
pytest tests/unit/database/test_migration_manager.py -v --cov=common.database.migration_manager --cov-report=term-missing
```

---

## 7. Acceptance Criteria

- [ ] **AC-1**: MigrationManager discovers migration files
  - Given a plugin with migrations/ directory containing 001_create.sql, 002_alter.sql
  - When calling discover_migrations(plugin_name)
  - Then returns list of 2 Migration objects sorted by version

- [ ] **AC-2**: Migration files parsed correctly
  - Given a valid migration file with -- UP and -- DOWN markers
  - When calling parse_migration_file(path)
  - Then up_sql and down_sql extracted correctly

- [ ] **AC-3**: UP/DOWN sections required
  - Given a migration file missing -- UP or -- DOWN marker
  - When calling parse_migration_file(path)
  - Then ValueError raised with clear message

- [ ] **AC-4**: Checksums computed consistently
  - Given same file content
  - When calling compute_checksum() twice
  - Then both checksums are identical (SHA-256 hex, 64 chars)

- [ ] **AC-5**: Checksum detects file changes
  - Given original file with checksum A
  - When file content modified
  - Then new checksum B != A

- [ ] **AC-6**: Pending migrations calculated correctly
  - Given current version 2, target version 5, migrations 1-5 exist
  - When calling get_pending_migrations()
  - Then returns [3, 4, 5] in ascending order

- [ ] **AC-7**: Rollback migrations calculated correctly
  - Given current version 5, target version 2, migrations 1-5 applied
  - When calling get_rollback_migrations()
  - Then returns [5, 4, 3] in descending order

- [ ] **AC-8**: Duplicate versions rejected
  - Given two migration files both named 001_*.sql
  - When calling discover_migrations()
  - Then ValueError raised indicating duplicate version

- [ ] **AC-9**: Invalid filenames skipped
  - Given migration files: 001_valid.sql, invalid_name.sql, 002_valid.sql
  - When calling discover_migrations()
  - Then returns only 001 and 002 (invalid_name.sql skipped)

- [ ] **AC-10**: Checksum verification detects tampering
  - Given applied migration with checksum A
  - When file modified to have checksum B
  - Then _verify_checksums() raises ValueError with "Checksum mismatch"

- [ ] **AC-11**: plugin_schema_migrations table created
  - Given Alembic migration
  - When running alembic upgrade head
  - Then table exists with correct columns and indexes

- [ ] **AC-12**: All unit tests pass
  - Given 30+ unit tests
  - When running pytest
  - Then all tests pass with 85%+ coverage

---

## 8. Rollout Plan

### Pre-deployment

1. Review all code in MigrationManager and Migration classes
2. Run full test suite (30+ unit tests)
3. Verify Alembic migration applies cleanly on SQLite and PostgreSQL
4. Test migration discovery with sample plugin

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-15-sortie-1-migration-manager`
2. Create `common/database/migration.py` with data models
3. Create `common/database/migration_manager.py` with full implementation
4. Create Alembic migration for `plugin_schema_migrations` table
5. Write comprehensive unit tests (30+ tests)
6. Run tests and verify 85%+ coverage
7. Test Alembic migration on staging database
8. Commit changes with message:
   ```
   Sprint 15 Sortie 1: Migration Manager Foundation
   
   - Add Migration and AppliedMigration dataclasses
   - Implement MigrationManager for file discovery and parsing
   - Add UP/DOWN section parsing with validation
   - Implement SHA-256 checksum computation
   - Add pending and rollback migration calculation
   - Create plugin_schema_migrations tracking table
   - Add 30+ unit tests (85%+ coverage)
   
   Implements: SPEC-Sortie-1-Migration-Manager-Foundation.md
   Related: PRD-Schema-Migrations.md
   ```
9. Push branch and create PR
10. Code review
11. Merge to main

### Post-deployment

- Verify `plugin_schema_migrations` table exists in database
- Test discovery on real plugin directories
- Monitor logs for parsing errors

### Rollback Procedure

If issues arise:
```bash
# Rollback Alembic migration
alembic downgrade -1

# Revert code changes
git revert <commit-hash>
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sprint 13**: Row Operations Foundation (database foundation)
- **Alembic**: Database migration tool
- **SQLAlchemy**: ORM framework
- **Python hashlib**: SHA-256 checksum computation

### External Dependencies

None - this is foundational infrastructure

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration file parsing fails on edge cases | Medium | Medium | Comprehensive unit tests covering edge cases |
| Checksum collisions (SHA-256) | Very Low | Low | SHA-256 is cryptographically secure, collisions virtually impossible |
| Plugin directory structure varies | Low | Medium | Document expected structure, validate in discovery |
| Large migrations exceed memory | Low | Medium | Stream file reading if needed (future optimization) |
| Version number gaps cause confusion | Low | Low | Document that gaps are allowed and expected |

---

## 10. Documentation

### Code Documentation

- All classes and methods have comprehensive docstrings
- Docstrings include Args, Returns, Raises sections
- Examples provided in docstrings for key methods
- Type hints for all parameters and return values

### User Documentation

Updates needed in **Sortie 4** when full feature is complete:
- Migration file format guide
- Best practices for writing migrations
- Checksum verification explanation

### Developer Documentation

Update **docs/DATABASE.md** with:
- MigrationManager class overview
- Migration file discovery process
- Checksum computation details
- Version tracking table schema

---

## 11. Related Specifications

**Previous**: None (foundational sortie for Sprint 15)

**Next**: 
- [SPEC-Sortie-2-NATS-Handlers-Execution.md](SPEC-Sortie-2-NATS-Handlers-Execution.md)
- [SPEC-Sortie-3-Safety-Features-Validation.md](SPEC-Sortie-3-Safety-Features-Validation.md)
- [SPEC-Sortie-4-Documentation-Examples.md](SPEC-Sortie-4-Documentation-Examples.md)

**Parent PRD**: [PRD-Schema-Migrations.md](PRD-Schema-Migrations.md)

**Related Sprints**:
- Sprint 13: Row Operations Foundation
- Sprint 16: Data Migrations (builds on Sprint 15)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
