"""
Unit tests for MigrationManager class.

Tests cover:
- Migration file discovery and sorting
- Migration file parsing (UP/DOWN extraction)
- Checksum computation and verification
- Pending migrations calculation
- Rollback migrations calculation
- Error handling and validation
"""

import pytest
from datetime import datetime
from pathlib import Path

from common.migrations.migration import Migration, AppliedMigration
from common.migrations.migration_manager import MigrationManager


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
        (quote_db / "invalid_name.sql").write_text(
            "-- UP\nSELECT 1;\n-- DOWN\nSELECT 1;\n"
        )
        
        # Create non-SQL file (should be skipped)
        (quote_db / "README.md").write_text("# Migrations")
        
        return plugins_dir
    
    def test_discover_migrations_success(self, temp_plugins_dir):
        """Test discovering valid migrations."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        assert len(migrations) == 3
        assert migrations[0].version == 1
        assert migrations[0].name == 'create_quotes'
        assert migrations[1].version == 2
        assert migrations[1].name == 'add_rating'
        assert migrations[2].version == 5  # Gap OK
        assert migrations[2].name == 'add_index'
    
    def test_discover_migrations_sorted(self, temp_plugins_dir):
        """Test migrations returned in version order."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        versions = [m.version for m in migrations]
        assert versions == sorted(versions)
        assert versions == [1, 2, 5]
    
    def test_discover_migrations_empty_directory(self, tmp_path):
        """Test discovering when no migrations directory exists."""
        manager = MigrationManager(tmp_path)
        migrations = manager.discover_migrations('nonexistent')
        
        assert migrations == []
    
    def test_discover_migrations_no_sql_files(self, tmp_path):
        """Test discovering when migrations directory has no .sql files."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test" / "migrations"
        plugin_dir.mkdir(parents=True)
        
        # Create only non-SQL files
        (plugin_dir / "README.md").write_text("# Migrations")
        (plugin_dir / "notes.txt").write_text("Notes")
        
        manager = MigrationManager(plugins_dir)
        migrations = manager.discover_migrations('test')
        
        assert migrations == []
    
    def test_discover_migrations_skips_invalid_filenames(self, temp_plugins_dir):
        """Test invalid filenames are skipped."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        filenames = [m.filename for m in migrations]
        assert 'invalid_name.sql' not in filenames
        assert 'README.md' not in filenames
    
    def test_discover_migrations_duplicate_version(self, tmp_path):
        """Test error on duplicate version numbers."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test" / "migrations"
        plugin_dir.mkdir(parents=True)
        
        # Create two migrations with same version
        (plugin_dir / "001_first.sql").write_text(
            "-- UP\nSELECT 1;\n-- DOWN\nSELECT 1;\n"
        )
        (plugin_dir / "001_duplicate.sql").write_text(
            "-- UP\nSELECT 2;\n-- DOWN\nSELECT 2;\n"
        )
        
        manager = MigrationManager(plugins_dir)
        
        with pytest.raises(ValueError, match="Duplicate migration version 1"):
            manager.discover_migrations('test')
    
    def test_discover_migrations_file_path_absolute(self, temp_plugins_dir):
        """Test migration file_path is absolute."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        for migration in migrations:
            assert Path(migration.file_path).is_absolute()
    
    def test_discover_migrations_preserves_metadata(self, temp_plugins_dir):
        """Test migration metadata is preserved."""
        manager = MigrationManager(temp_plugins_dir)
        migrations = manager.discover_migrations('quote-db')
        
        migration = migrations[0]
        assert migration.version == 1
        assert migration.name == 'create_quotes'
        assert migration.filename == '001_create_quotes.sql'
        assert len(migration.checksum) == 64  # SHA-256


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
        assert 'CREATE INDEX idx_users_username' in migration.up_sql
        assert 'DROP INDEX idx_users_username' in migration.down_sql
        assert 'DROP TABLE users' in migration.down_sql
        assert len(migration.checksum) == 64  # SHA-256 hex digest
    
    def test_parse_migration_missing_up_marker(self, tmp_path):
        """Test error when UP marker missing."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text(
            "CREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        )
        
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
        migration_file.write_text(
            "-- DOWN\nDROP TABLE test;\n-- UP\nCREATE TABLE test;\n"
        )
        
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
    
    def test_parse_migration_empty_down_section(self, tmp_path):
        """Test error when DOWN section is empty."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("-- UP\nCREATE TABLE test;\n-- DOWN\n\n")
        
        manager = MigrationManager(tmp_path.parent)
        
        with pytest.raises(ValueError, match="has empty DOWN section"):
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
    
    def test_parse_migration_preserves_whitespace(self, tmp_path):
        """Test whitespace is preserved in SQL."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("""
-- UP
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL
);

-- DOWN
DROP TABLE users;
""")
        
        manager = MigrationManager(tmp_path.parent)
        migration = manager.parse_migration_file(migration_file)
        
        # Multiline SQL preserved
        assert 'id SERIAL PRIMARY KEY' in migration.up_sql
        assert 'username VARCHAR(255)' in migration.up_sql
    
    def test_parse_migration_case_insensitive_markers(self, tmp_path):
        """Test markers are case-insensitive."""
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text(
            "-- up\nCREATE TABLE test;\n-- down\nDROP TABLE test;\n"
        )
        
        manager = MigrationManager(tmp_path.parent)
        migration = manager.parse_migration_file(migration_file)
        
        assert 'CREATE TABLE test' in migration.up_sql
        assert 'DROP TABLE test' in migration.down_sql
    
    def test_parse_migration_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        manager = MigrationManager(tmp_path)
        
        with pytest.raises(FileNotFoundError, match="Migration file not found"):
            manager.parse_migration_file(tmp_path / "nonexistent.sql")


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
    
    def test_compute_checksum_comment_sensitive(self, tmp_path):
        """Test checksum changes when comments change."""
        manager = MigrationManager(tmp_path)
        
        content1 = "-- UP\n-- Comment\nCREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        content2 = "-- UP\nCREATE TABLE test;\n-- DOWN\nDROP TABLE test;\n"
        
        checksum1 = manager.compute_checksum(content1)
        checksum2 = manager.compute_checksum(content2)
        
        assert checksum1 != checksum2
    
    def test_compute_checksum_empty_content(self, tmp_path):
        """Test checksum of empty content."""
        manager = MigrationManager(tmp_path)
        
        checksum = manager.compute_checksum("")
        
        assert len(checksum) == 64
        # SHA-256 of empty string
        assert checksum == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'


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
    
    def test_get_pending_migrations_single(self, manager_with_migrations):
        """Test pending single migration."""
        pending = manager_with_migrations.get_pending_migrations('test', 2, 3)
        
        assert len(pending) == 1
        assert pending[0].version == 3
    
    def test_get_pending_migrations_all(self, manager_with_migrations):
        """Test pending all migrations."""
        pending = manager_with_migrations.get_pending_migrations('test', 0, 5)
        
        assert len(pending) == 5
        assert [m.version for m in pending] == [1, 2, 3, 4, 5]
    
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
    
    def test_get_pending_migrations_no_plugin_migrations(self, tmp_path):
        """Test pending when plugin has no migrations."""
        manager = MigrationManager(tmp_path)
        pending = manager.get_pending_migrations('nonexistent', 0, 5)
        
        assert pending == []


class TestRollbackMigrations:
    """Test rollback migrations calculation."""
    
    @pytest.fixture
    def manager_with_applied(self, tmp_path):
        """Create manager with migrations and mock applied migrations."""
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
    
    def test_get_rollback_migrations_single(self, manager_with_applied):
        """Test rollback single migration."""
        manager, applied = manager_with_applied
        rollback = manager.get_rollback_migrations('test', 3, 2, applied)
        
        assert len(rollback) == 1
        assert rollback[0].version == 3
    
    def test_get_rollback_migrations_target_greater_than_current(self, manager_with_applied):
        """Test error when target >= current (should use apply)."""
        manager, applied = manager_with_applied
        
        with pytest.raises(ValueError, match="Use get_pending_migrations"):
            manager.get_rollback_migrations('test', 2, 4, applied)
    
    def test_get_rollback_migrations_target_equal_current(self, manager_with_applied):
        """Test error when target == current (no rollback needed)."""
        manager, applied = manager_with_applied
        
        with pytest.raises(ValueError, match="Use get_pending_migrations"):
            manager.get_rollback_migrations('test', 3, 3, applied)
    
    def test_get_rollback_migrations_target_negative(self, manager_with_applied):
        """Test error when target version is negative."""
        manager, applied = manager_with_applied
        
        with pytest.raises(ValueError, match="Target version cannot be negative"):
            manager.get_rollback_migrations('test', 3, -1, applied)
    
    def test_get_rollback_migrations_not_applied(self, manager_with_applied):
        """Test error when trying to rollback unapplied migration."""
        manager, _ = manager_with_applied
        
        # Only migrations 1-3 applied
        applied_partial = [
            AppliedMigration(
                'test', v, f'migration_{v}', 'abc', datetime.utcnow(), 'system'
            )
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
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        checksum = manager.compute_checksum("test content")
        
        migrations = [
            Migration(1, 'test', '001_test.sql', '/path', 'UP', 'DOWN', checksum)
        ]
        applied = [
            AppliedMigration(
                'plugin', 1, 'test', checksum, datetime.utcnow(), 'system'
            )
        ]
        
        # Should not raise
        manager._verify_checksums(migrations, applied)
    
    def test_verify_checksums_mismatch(self, tmp_path):
        """Test verification fails when checksums don't match."""
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        migrations = [
            Migration(1, 'test', '001_test.sql', '/path', 'UP', 'DOWN', 'checksum_new')
        ]
        applied = [
            AppliedMigration(
                'plugin', 1, 'test', 'checksum_old', datetime.utcnow(), 'system'
            )
        ]
        
        with pytest.raises(ValueError, match="Checksum mismatch.*File has been modified"):
            manager._verify_checksums(migrations, applied)
    
    def test_verify_checksums_no_applied(self, tmp_path):
        """Test verification passes when no applied migrations."""
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        migrations = [
            Migration(1, 'test', '001_test.sql', '/path', 'UP', 'DOWN', 'checksum')
        ]
        applied = []  # No applied migrations
        
        # Should not raise (nothing to verify)
        manager._verify_checksums(migrations, applied)
    
    def test_verify_checksums_partial_overlap(self, tmp_path):
        """Test verification with partial overlap."""
        plugins_dir = tmp_path / "plugins"
        manager = MigrationManager(plugins_dir)
        
        checksum1 = manager.compute_checksum("content1")
        checksum2 = manager.compute_checksum("content2")
        
        migrations = [
            Migration(1, 'test1', '001_test1.sql', '/path1', 'UP', 'DOWN', checksum1),
            Migration(2, 'test2', '002_test2.sql', '/path2', 'UP', 'DOWN', checksum2),
            Migration(3, 'test3', '003_test3.sql', '/path3', 'UP', 'DOWN', 'new')
        ]
        applied = [
            AppliedMigration('plugin', 1, 'test1', checksum1, datetime.utcnow(), 'system'),
            AppliedMigration('plugin', 2, 'test2', checksum2, datetime.utcnow(), 'system')
        ]
        
        # Should not raise (migration 3 is new, not applied yet)
        manager._verify_checksums(migrations, applied)
