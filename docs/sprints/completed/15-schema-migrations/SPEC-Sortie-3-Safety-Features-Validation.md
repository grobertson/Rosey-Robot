# SPEC-Sortie-3: Safety Features & Validation

**Sprint**: 15 - Schema Migrations  
**Sortie**: 3 of 4  
**Estimated Duration**: 1 day  
**Status**: Draft  
**Author**: Agent via PRD-Schema-Migrations.md  
**Created**: November 24, 2025  

---

## 1. Overview

This sortie implements safety features and validation for database migrations to prevent data loss and detect issues before execution. Building on Sortie 2's execution infrastructure, we add checksum verification to detect file tampering, validation for destructive operations (DROP COLUMN, DROP TABLE), SQLite limitation detection, and basic SQL syntax checking. These features provide guardrails for safe schema evolution.

**What This Sortie Achieves**:
- MigrationValidator class for analyzing migration SQL
- Checksum verification on status checks (detect file tampering)
- Destructive operation warnings (DROP COLUMN, DROP TABLE, TRUNCATE)
- SQLite limitation detection (unsupported ALTER operations)
- Basic SQL syntax validation
- Warning system with severity levels (INFO, WARNING, ERROR)

**Key Safety Checks**:
- File checksum vs database checksum comparison
- DROP COLUMN → data loss warning (ERROR on SQLite)
- DROP TABLE → data loss warning
- TRUNCATE TABLE → data loss warning
- SQLite unsupported operations → ERROR
- Invalid SQL syntax → ERROR

---

## 2. Scope and Non-Goals

### In Scope

- **MigrationValidator Class**: Analyzes migration SQL for safety issues
- **Checksum Verification**: Compare file checksums to database on status check
- **Destructive Operation Detection**: Regex patterns for DROP, TRUNCATE operations
- **SQLite Limitation Detection**: Unsupported ALTER TABLE operations
- **Warning System**: Structured warnings with level, message, migration context
- **Handler Integration**: Add validation to apply/rollback handlers
- **Validation Results**: Return warnings in status response

### Out of Scope (Future Work)

- **Advanced SQL Parsing**: Full AST analysis of SQL (use regex patterns)
- **Data Loss Estimation**: Calculate rows affected (requires query execution)
- **Automatic Fixes**: Suggest workarounds for SQLite limitations
- **Schema Diff**: Compare expected vs actual schema after migration
- **Performance Analysis**: Estimate migration execution time
- **Documentation**: User guides and examples (Sortie 4)

---

## 3. Requirements

### Functional Requirements

**FR-1: Checksum Verification**
- On status check, compare file checksums to database checksums
- For each applied migration, read file and compute current checksum
- If current checksum != stored checksum, add ERROR warning
- Warning message: "Migration {version} file has been modified (checksum mismatch)"

**FR-2: Destructive Operation Detection**
- Scan UP SQL for destructive keywords: DROP COLUMN, DROP TABLE, TRUNCATE
- For DROP COLUMN: Add WARNING with "potential data loss"
- For DROP TABLE: Add WARNING with "table will be deleted"
- For TRUNCATE TABLE: Add WARNING with "all rows will be deleted"
- Use case-insensitive regex matching

**FR-3: SQLite Limitation Detection**
- If database type is SQLite AND migration contains:
  - DROP COLUMN → ERROR: "SQLite does not support DROP COLUMN directly"
  - ALTER COLUMN → ERROR: "SQLite does not support ALTER COLUMN directly"
  - ADD CONSTRAINT → ERROR: "SQLite does not support ADD CONSTRAINT directly"
- Suggest workaround: "Use table recreation pattern (CREATE temp, INSERT, DROP old, RENAME temp)"

**FR-4: Basic SQL Syntax Validation**
- Check for common syntax errors:
  - Unmatched parentheses: count '(' vs ')'
  - Unterminated strings: odd number of single quotes (not in comments)
  - Missing semicolons: if multiple statements expected
- Return ERROR warnings for syntax issues

**FR-5: Warning System**
- Define Warning dataclass with level, message, migration_version, migration_name
- Levels: INFO, WARNING, ERROR
- ERROR warnings should prevent migration from executing
- WARNING warnings should be shown but allow execution
- INFO warnings for informational messages

**FR-6: Handler Integration**
- Before applying migration, call validator.validate_migration()
- If any ERROR warnings, reject with error_code='VALIDATION_FAILED'
- If WARNING warnings, include in response with warnings field
- On status check, include validation warnings for pending migrations

### Non-Functional Requirements

**NFR-1: Performance**
- Validation should complete < 50ms per migration
- Regex patterns compiled once and reused

**NFR-2: Reliability**
- False positives acceptable for safety (warn even if not destructive)
- False negatives not acceptable (must catch all dangerous operations)

**NFR-3: Testability**
- 20+ unit tests covering all validation rules
- Test fixtures with sample dangerous SQL

**NFR-4: Code Coverage**
- Target: 85%+ for MigrationValidator
- Minimum: 66% per project standards

---

## 4. Technical Design

### 4.1 Warning Data Model

```python
"""
common/database/migration_validator.py
"""
from dataclasses import dataclass
from enum import Enum
from typing import List
import re


class WarningLevel(Enum):
    """Severity levels for validation warnings."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationWarning:
    """Warning from migration validation."""
    
    level: WarningLevel
    message: str
    migration_version: int
    migration_name: str
    category: str  # 'checksum', 'destructive', 'sqlite', 'syntax'
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'level': self.level.value,
            'message': self.message,
            'migration_version': self.migration_version,
            'migration_name': self.migration_name,
            'category': self.category
        }
    
    def __repr__(self) -> str:
        return f"[{self.level.value}] Migration {self.migration_version}_{self.migration_name}: {self.message}"
```

### 4.2 MigrationValidator Class

```python
class MigrationValidator:
    """Validates migrations for safety and compatibility issues."""
    
    # Compiled regex patterns for performance
    DROP_COLUMN_PATTERN = re.compile(r'\bDROP\s+COLUMN\b', re.IGNORECASE)
    DROP_TABLE_PATTERN = re.compile(r'\bDROP\s+TABLE\b', re.IGNORECASE)
    TRUNCATE_PATTERN = re.compile(r'\bTRUNCATE\s+TABLE\b', re.IGNORECASE)
    ALTER_COLUMN_PATTERN = re.compile(r'\bALTER\s+COLUMN\b', re.IGNORECASE)
    ADD_CONSTRAINT_PATTERN = re.compile(r'\bADD\s+CONSTRAINT\b', re.IGNORECASE)
    
    def __init__(self, db_type: str = 'sqlite'):
        """
        Initialize validator.
        
        Args:
            db_type: Database type ('sqlite', 'postgresql', etc.)
        """
        self.db_type = db_type.lower()
    
    def validate_migration(self, migration: 'Migration') -> List[ValidationWarning]:
        """
        Validate a migration for safety and compatibility issues.
        
        Args:
            migration: Migration object to validate
            
        Returns:
            List of ValidationWarning objects (empty if no issues)
            
        Example:
            >>> validator = MigrationValidator(db_type='sqlite')
            >>> warnings = validator.validate_migration(migration)
            >>> for w in warnings:
            ...     print(f"{w.level.value}: {w.message}")
        """
        warnings = []
        
        # Check for destructive operations
        warnings.extend(self._check_destructive_operations(migration))
        
        # Check SQLite limitations
        if self.db_type == 'sqlite':
            warnings.extend(self._check_sqlite_limitations(migration))
        
        # Check basic syntax
        warnings.extend(self._check_syntax(migration))
        
        return warnings
    
    def verify_checksums(
        self, 
        migration: 'Migration', 
        stored_checksum: str
    ) -> List[ValidationWarning]:
        """
        Verify migration file checksum matches stored checksum.
        
        Args:
            migration: Migration object with current checksum
            stored_checksum: Checksum from database
            
        Returns:
            List with ERROR warning if mismatch, empty if match
        """
        warnings = []
        
        if migration.checksum != stored_checksum:
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message=f"Migration file has been modified (checksum mismatch). "
                        f"Expected: {stored_checksum[:8]}..., Got: {migration.checksum[:8]}...",
                migration_version=migration.version,
                migration_name=migration.name,
                category='checksum'
            ))
        
        return warnings
    
    def _check_destructive_operations(self, migration: 'Migration') -> List[ValidationWarning]:
        """Check for destructive SQL operations."""
        warnings = []
        sql = migration.up_sql
        
        # DROP COLUMN
        if self.DROP_COLUMN_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.WARNING,
                message="Migration drops column (potential data loss). "
                        "Ensure column data is no longer needed or backed up.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='destructive'
            ))
        
        # DROP TABLE
        if self.DROP_TABLE_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.WARNING,
                message="Migration drops table (all table data will be deleted). "
                        "Ensure data is backed up or no longer needed.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='destructive'
            ))
        
        # TRUNCATE TABLE
        if self.TRUNCATE_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.WARNING,
                message="Migration truncates table (all rows will be deleted). "
                        "Ensure data is backed up or no longer needed.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='destructive'
            ))
        
        return warnings
    
    def _check_sqlite_limitations(self, migration: 'Migration') -> List[ValidationWarning]:
        """Check for SQLite unsupported operations."""
        warnings = []
        sql = migration.up_sql
        
        # DROP COLUMN not supported
        if self.DROP_COLUMN_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message="SQLite does not support DROP COLUMN directly. "
                        "Use table recreation pattern: CREATE temp table, "
                        "INSERT data (excluding column), DROP old table, RENAME temp table.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='sqlite'
            ))
        
        # ALTER COLUMN not supported
        if self.ALTER_COLUMN_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message="SQLite does not support ALTER COLUMN directly. "
                        "Use table recreation pattern with modified schema.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='sqlite'
            ))
        
        # ADD CONSTRAINT not supported
        if self.ADD_CONSTRAINT_PATTERN.search(sql):
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message="SQLite does not support ADD CONSTRAINT directly. "
                        "Define constraints in initial CREATE TABLE or use table recreation.",
                migration_version=migration.version,
                migration_name=migration.name,
                category='sqlite'
            ))
        
        return warnings
    
    def _check_syntax(self, migration: 'Migration') -> List[ValidationWarning]:
        """Check for basic SQL syntax errors."""
        warnings = []
        sql = migration.up_sql
        
        # Remove SQL comments before checking
        sql_no_comments = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_comments, flags=re.DOTALL)
        
        # Check parentheses balance
        open_parens = sql_no_comments.count('(')
        close_parens = sql_no_comments.count(')')
        if open_parens != close_parens:
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message=f"Unmatched parentheses: {open_parens} open, {close_parens} close",
                migration_version=migration.version,
                migration_name=migration.name,
                category='syntax'
            ))
        
        # Check string quotes balance (simplified - doesn't handle escapes)
        single_quotes = sql_no_comments.count("'")
        if single_quotes % 2 != 0:
            warnings.append(ValidationWarning(
                level=WarningLevel.ERROR,
                message=f"Unterminated string (odd number of single quotes: {single_quotes})",
                migration_version=migration.version,
                migration_name=migration.name,
                category='syntax'
            ))
        
        return warnings
```

### 4.3 Handler Integration

Update handlers to use validator:

```python
"""
common/database/database_service.py (additions)
"""
from .migration_validator import MigrationValidator, ValidationWarning, WarningLevel


class DatabaseService:
    def __init__(self, nats_client, db, plugins_dir):
        # ... existing init
        self.validator = MigrationValidator(db_type='sqlite')  # or from config
    
    async def handle_migrate_apply(self, msg):
        """Apply handler with validation."""
        # ... existing code ...
        
        pending = manager.get_pending_migrations(plugin_name, current_version, target_version)
        
        # Validate all pending migrations
        all_warnings = []
        for migration in pending:
            warnings = self.validator.validate_migration(migration)
            all_warnings.extend(warnings)
            
            # Check for ERROR warnings
            errors = [w for w in warnings if w.level == WarningLevel.ERROR]
            if errors:
                await msg.respond(json.dumps({
                    'success': False,
                    'error_code': 'VALIDATION_FAILED',
                    'message': 'Migration validation failed',
                    'errors': [e.to_dict() for e in errors],
                    'warnings': [w.to_dict() for w in warnings if w.level == WarningLevel.WARNING]
                }).encode())
                return
        
        # Continue with migration application...
        results = []
        for migration in pending:
            result = await executor.apply_migration(...)
            results.append(result)
        
        # Include warnings in response
        await msg.respond(json.dumps({
            'success': True,
            'applied_migrations': [r.to_dict() for r in results],
            'warnings': [w.to_dict() for w in all_warnings if w.level == WarningLevel.WARNING]
        }).encode())
    
    async def handle_migrate_status(self, msg):
        """Status handler with checksum verification."""
        # ... existing code ...
        
        # Get applied migrations with checksums
        applied_rows = await self.db.fetch_all(
            """
            SELECT version, name, checksum, applied_at, applied_by, status
            FROM plugin_schema_migrations
            WHERE plugin_name = ? AND status = 'applied'
            """,
            (plugin_name,)
        )
        
        # Verify checksums
        checksum_warnings = []
        for row in applied_rows:
            # Find migration file
            try:
                migration = manager.find_migration(plugin_name, row['version'])
                warnings = self.validator.verify_checksums(migration, row['checksum'])
                checksum_warnings.extend(warnings)
            except FileNotFoundError:
                checksum_warnings.append(ValidationWarning(
                    level=WarningLevel.ERROR,
                    message=f"Migration file {row['version']}_{row['name']}.sql not found",
                    migration_version=row['version'],
                    migration_name=row['name'],
                    category='checksum'
                ))
        
        # Validate pending migrations
        pending_migrations = [m for m in all_migrations if m.version > current_version]
        pending_warnings = []
        for migration in pending_migrations:
            warnings = self.validator.validate_migration(migration)
            pending_warnings.extend(warnings)
        
        await msg.respond(json.dumps({
            'success': True,
            'plugin_name': plugin_name,
            'current_version': current_version,
            'checksum_warnings': [w.to_dict() for w in checksum_warnings],
            'pending_warnings': [w.to_dict() for w in pending_warnings],
            # ... rest of status response
        }).encode())
```

---

## 5. Implementation Steps

1. **Create Validation Data Models** (`common/database/migration_validator.py`)
   - Define WarningLevel enum (INFO, WARNING, ERROR)
   - Define ValidationWarning dataclass
   - Add to_dict() method for JSON serialization

2. **Create MigrationValidator Class**
   - Define compiled regex patterns (DROP_COLUMN, DROP_TABLE, etc.)
   - Implement __init__(db_type)
   - Implement validate_migration() - main entry point

3. **Implement Destructive Operation Checks**
   - Implement _check_destructive_operations()
   - Check for DROP COLUMN pattern → WARNING
   - Check for DROP TABLE pattern → WARNING
   - Check for TRUNCATE TABLE pattern → WARNING

4. **Implement SQLite Limitation Checks**
   - Implement _check_sqlite_limitations()
   - Check for DROP COLUMN → ERROR (if db_type='sqlite')
   - Check for ALTER COLUMN → ERROR
   - Check for ADD CONSTRAINT → ERROR
   - Include workaround suggestions in messages

5. **Implement Syntax Checks**
   - Implement _check_syntax()
   - Remove comments from SQL before checking
   - Check parentheses balance
   - Check string quote balance

6. **Implement Checksum Verification**
   - Implement verify_checksums(migration, stored_checksum)
   - Compare checksums
   - Return ERROR warning if mismatch

7. **Add find_migration() Helper to MigrationManager**
   - Implement find_migration(plugin_name, version) in MigrationManager
   - Discover migrations, find by version
   - Return Migration object or raise FileNotFoundError

8. **Integrate Validator into Apply Handler**
   - Initialize validator in DatabaseService.__init__
   - Call validator.validate_migration() for each pending migration
   - Check for ERROR warnings, reject if found
   - Include WARNING warnings in response

9. **Integrate Validator into Status Handler**
   - Call validator.verify_checksums() for applied migrations
   - Call validator.validate_migration() for pending migrations
   - Include checksum_warnings and pending_warnings in response

10. **Unit Tests**
    - Write tests for each validation rule
    - Test checksum verification
    - Test destructive operation detection
    - Test SQLite limitation detection
    - Test syntax checking

11. **Documentation**
    - Add docstrings to all methods
    - Document warning categories and levels
    - Document validation rules

---

## 6. Testing Strategy

### 6.1 Unit Tests - MigrationValidator

**tests/unit/database/test_migration_validator.py**

```python
import pytest
from common.database.migration_validator import (
    MigrationValidator, ValidationWarning, WarningLevel
)
from common.database.migration import Migration


class TestDestructiveOperations:
    def test_drop_column_warning(self):
        """Test DROP COLUMN generates WARNING."""
        migration = Migration(
            version=1,
            name="drop_col",
            up_sql="ALTER TABLE quotes DROP COLUMN author;",
            down_sql="-- cannot undo",
            checksum="abc123"
        )
        
        validator = MigrationValidator(db_type='postgresql')
        warnings = validator.validate_migration(migration)
        
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.WARNING
        assert 'potential data loss' in warnings[0].message.lower()
        assert warnings[0].category == 'destructive'
    
    def test_drop_table_warning(self):
        """Test DROP TABLE generates WARNING."""
        migration = Migration(
            version=1,
            name="drop_table",
            up_sql="DROP TABLE old_quotes;",
            down_sql="CREATE TABLE old_quotes (id INTEGER);",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        assert len(warnings) >= 1
        drop_warnings = [w for w in warnings if 'drop table' in w.message.lower()]
        assert len(drop_warnings) == 1
        assert drop_warnings[0].level == WarningLevel.WARNING
    
    def test_truncate_warning(self):
        """Test TRUNCATE TABLE generates WARNING."""
        migration = Migration(
            version=1,
            name="truncate",
            up_sql="TRUNCATE TABLE quotes;",
            down_sql="-- cannot undo",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        assert len(warnings) >= 1
        truncate_warnings = [w for w in warnings if 'truncate' in w.message.lower()]
        assert len(truncate_warnings) == 1
    
    def test_case_insensitive_matching(self):
        """Test patterns match case-insensitively."""
        migration = Migration(
            version=1,
            name="drop_mixed_case",
            up_sql="drop table Quotes;",  # lowercase 'drop'
            down_sql="",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        assert len(warnings) >= 1


class TestSQLiteLimitations:
    def test_drop_column_error_sqlite(self):
        """Test DROP COLUMN generates ERROR on SQLite."""
        migration = Migration(
            version=1,
            name="drop_col",
            up_sql="ALTER TABLE quotes DROP COLUMN author;",
            down_sql="",
            checksum="abc123"
        )
        
        validator = MigrationValidator(db_type='sqlite')
        warnings = validator.validate_migration(migration)
        
        # Should have both destructive WARNING and SQLite ERROR
        errors = [w for w in warnings if w.level == WarningLevel.ERROR]
        assert len(errors) == 1
        assert 'sqlite does not support' in errors[0].message.lower()
        assert 'recreation' in errors[0].message.lower()
    
    def test_alter_column_error_sqlite(self):
        """Test ALTER COLUMN generates ERROR on SQLite."""
        migration = Migration(
            version=1,
            name="alter_col",
            up_sql="ALTER TABLE quotes ALTER COLUMN text TYPE TEXT;",
            down_sql="",
            checksum="abc123"
        )
        
        validator = MigrationValidator(db_type='sqlite')
        warnings = validator.validate_migration(migration)
        
        errors = [w for w in warnings if w.level == WarningLevel.ERROR]
        assert len(errors) == 1
        assert 'sqlite' in errors[0].message.lower()
    
    def test_add_constraint_error_sqlite(self):
        """Test ADD CONSTRAINT generates ERROR on SQLite."""
        migration = Migration(
            version=1,
            name="add_fk",
            up_sql="ALTER TABLE quotes ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);",
            down_sql="",
            checksum="abc123"
        )
        
        validator = MigrationValidator(db_type='sqlite')
        warnings = validator.validate_migration(migration)
        
        errors = [w for w in warnings if w.level == WarningLevel.ERROR]
        assert len(errors) == 1
    
    def test_postgresql_allows_operations(self):
        """Test PostgreSQL does not generate SQLite errors."""
        migration = Migration(
            version=1,
            name="drop_col",
            up_sql="ALTER TABLE quotes DROP COLUMN author;",
            down_sql="",
            checksum="abc123"
        )
        
        validator = MigrationValidator(db_type='postgresql')
        warnings = validator.validate_migration(migration)
        
        # Should only have destructive WARNING, not SQLite ERROR
        errors = [w for w in warnings if w.level == WarningLevel.ERROR]
        assert len(errors) == 0


class TestSyntaxValidation:
    def test_unmatched_parentheses(self):
        """Test unmatched parentheses generates ERROR."""
        migration = Migration(
            version=1,
            name="bad_parens",
            up_sql="CREATE TABLE test (id INTEGER, name TEXT;",  # missing )
            down_sql="DROP TABLE test;",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        errors = [w for w in warnings if w.category == 'syntax']
        assert len(errors) >= 1
        assert 'parentheses' in errors[0].message.lower()
    
    def test_unterminated_string(self):
        """Test unterminated string generates ERROR."""
        migration = Migration(
            version=1,
            name="bad_string",
            up_sql="INSERT INTO test VALUES (1, 'unterminated);",  # missing '
            down_sql="DELETE FROM test;",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        errors = [w for w in warnings if w.category == 'syntax']
        assert len(errors) >= 1
        assert 'string' in errors[0].message.lower() or 'quote' in errors[0].message.lower()
    
    def test_valid_sql_no_syntax_errors(self):
        """Test valid SQL generates no syntax errors."""
        migration = Migration(
            version=1,
            name="valid",
            up_sql="CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT);",
            down_sql="DROP TABLE test;",
            checksum="abc123"
        )
        
        validator = MigrationValidator()
        warnings = validator.validate_migration(migration)
        
        syntax_errors = [w for w in warnings if w.category == 'syntax']
        assert len(syntax_errors) == 0


class TestChecksumVerification:
    def test_matching_checksum_no_warning(self):
        """Test matching checksums generate no warning."""
        migration = Migration(
            version=1,
            name="test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
            checksum="abc123def456"
        )
        
        validator = MigrationValidator()
        warnings = validator.verify_checksums(migration, stored_checksum="abc123def456")
        
        assert len(warnings) == 0
    
    def test_checksum_mismatch_error(self):
        """Test checksum mismatch generates ERROR."""
        migration = Migration(
            version=1,
            name="test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
            checksum="abc123def456"
        )
        
        validator = MigrationValidator()
        warnings = validator.verify_checksums(migration, stored_checksum="different123")
        
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.ERROR
        assert 'checksum mismatch' in warnings[0].message.lower()
        assert warnings[0].category == 'checksum'


class TestWarningDataModel:
    def test_warning_to_dict(self):
        """Test ValidationWarning serializes to dict."""
        warning = ValidationWarning(
            level=WarningLevel.WARNING,
            message="Test warning",
            migration_version=1,
            migration_name="test",
            category="test"
        )
        
        d = warning.to_dict()
        assert d['level'] == 'WARNING'
        assert d['message'] == 'Test warning'
        assert d['migration_version'] == 1
        assert d['category'] == 'test'
    
    def test_warning_repr(self):
        """Test ValidationWarning string representation."""
        warning = ValidationWarning(
            level=WarningLevel.ERROR,
            message="Syntax error",
            migration_version=2,
            migration_name="bad_sql",
            category="syntax"
        )
        
        repr_str = repr(warning)
        assert '[ERROR]' in repr_str
        assert 'Migration 2_bad_sql' in repr_str
        assert 'Syntax error' in repr_str


### 6.2 Integration Tests - Handler Validation

**tests/integration/database/test_migration_validation_handlers.py**

```python
import pytest
import json


class TestApplyHandlerValidation:
    async def test_apply_rejected_on_error_warnings(self, database_service, nats_msg):
        """Test apply handler rejects migrations with ERROR warnings."""
        # Migration with SQLite DROP COLUMN (ERROR)
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 2}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is False
        assert response['error_code'] == 'VALIDATION_FAILED'
        assert len(response['errors']) > 0
        assert any('sqlite' in e['message'].lower() for e in response['errors'])
    
    async def test_apply_succeeds_with_warnings(self, database_service, nats_msg):
        """Test apply handler succeeds with WARNING level warnings."""
        # Migration with DROP TABLE (WARNING, not ERROR)
        nats_msg.subject = "db.migrate.quotes.apply"
        nats_msg.data = json.dumps({"target_version": 1}).encode()
        
        await database_service.handle_migrate_apply(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert response['success'] is True
        assert 'warnings' in response
        assert len(response['warnings']) > 0


class TestStatusHandlerValidation:
    async def test_status_includes_checksum_warnings(self, database_service, nats_msg):
        """Test status includes checksum verification warnings."""
        # Apply migration, then modify file
        nats_msg.subject = "db.migrate.quotes.status"
        nats_msg.data = json.dumps({}).encode()
        
        await database_service.handle_migrate_status(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert 'checksum_warnings' in response
    
    async def test_status_includes_pending_warnings(self, database_service, nats_msg):
        """Test status includes validation warnings for pending migrations."""
        nats_msg.subject = "db.migrate.quotes.status"
        nats_msg.data = json.dumps({}).encode()
        
        await database_service.handle_migrate_status(nats_msg)
        
        response = json.loads(nats_msg.respond.call_args[0][0])
        assert 'pending_warnings' in response
```

**Coverage Target**: 85%+ for MigrationValidator

---

## 7. Acceptance Criteria

- [ ] **AC-1**: Checksum verification detects file tampering
  - Given applied migration with checksum A
  - When file modified to have checksum B
  - Then status handler returns ERROR warning with "checksum mismatch"

- [ ] **AC-2**: DROP COLUMN generates WARNING
  - Given migration with "ALTER TABLE ... DROP COLUMN"
  - When validating migration
  - Then WARNING returned with "potential data loss"

- [ ] **AC-3**: DROP TABLE generates WARNING
  - Given migration with "DROP TABLE"
  - When validating migration
  - Then WARNING returned with "table will be deleted"

- [ ] **AC-4**: TRUNCATE TABLE generates WARNING
  - Given migration with "TRUNCATE TABLE"
  - When validating migration
  - Then WARNING returned with "all rows will be deleted"

- [ ] **AC-5**: SQLite DROP COLUMN generates ERROR
  - Given SQLite database and migration with DROP COLUMN
  - When validating migration
  - Then ERROR returned with "SQLite does not support" and workaround

- [ ] **AC-6**: SQLite ALTER COLUMN generates ERROR
  - Given SQLite database and migration with ALTER COLUMN
  - When validating migration
  - Then ERROR returned with SQLite limitation message

- [ ] **AC-7**: Unmatched parentheses generates ERROR
  - Given migration with 3 '(' and 2 ')'
  - When validating migration
  - Then syntax ERROR returned

- [ ] **AC-8**: Unterminated string generates ERROR
  - Given migration with odd number of single quotes
  - When validating migration
  - Then syntax ERROR returned

- [ ] **AC-9**: Apply handler rejects ERROR warnings
  - Given migration with ERROR warning
  - When applying migration
  - Then request rejected with VALIDATION_FAILED error

- [ ] **AC-10**: Apply handler includes WARNING warnings in response
  - Given migration with WARNING level warning
  - When applying migration successfully
  - Then response includes warnings array

- [ ] **AC-11**: Status handler includes checksum warnings
  - Given status request
  - When checksum mismatches exist
  - Then response includes checksum_warnings array

- [ ] **AC-12**: All unit tests pass
  - Given 20+ validation tests
  - When running pytest
  - Then all tests pass with 85%+ coverage

---

## 8. Rollout Plan

### Pre-deployment

1. Ensure Sorties 1 and 2 complete and tested
2. Review all validation logic
3. Run full test suite (20+ unit tests)
4. Test with various dangerous SQL patterns

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-15-sortie-3-validation`
2. Create `common/database/migration_validator.py`
   - WarningLevel enum
   - ValidationWarning dataclass
   - MigrationValidator class with all checks
3. Add find_migration() helper to MigrationManager
4. Update DatabaseService handlers:
   - Integrate validator in apply handler
   - Integrate validator in status handler
5. Write comprehensive unit tests
6. Write integration tests for handlers
7. Run tests and verify 85%+ coverage
8. Commit changes with message:
   ```
   Sprint 15 Sortie 3: Safety Features & Validation
   
   - Add MigrationValidator with destructive operation detection
   - Implement checksum verification on status checks
   - Add SQLite limitation detection with workarounds
   - Add basic SQL syntax validation
   - Integrate validation into apply and status handlers
   - Reject migrations with ERROR warnings
   - Add 20+ validation tests (85%+ coverage)
   
   Implements: SPEC-Sortie-3-Safety-Features-Validation.md
   Related: PRD-Schema-Migrations.md
   ```
9. Push branch and create PR
10. Code review
11. Merge to main

### Post-deployment

- Test validation with sample dangerous migrations
- Verify SQLite limitations caught
- Verify checksum verification works
- Monitor warnings in status responses

### Rollback Procedure

If issues arise:
```bash
# Revert code changes
git revert <commit-hash>

# Restart services
systemctl restart cytube-bot
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sorties 1-2**: MigrationManager and execution infrastructure
- **Python re module**: For regex pattern matching
- **Sprint 13**: Database foundation

### External Dependencies

None

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| False positives block safe migrations | Medium | Medium | Document override mechanism, make warnings clear |
| Regex patterns miss edge cases | Medium | Low | Comprehensive test suite, err on side of caution |
| Performance impact of validation | Low | Low | Compile regex patterns once, minimal overhead |
| Users ignore warnings | Medium | High | Make warnings prominent, require acknowledgment for destructive operations |
| Checksum verification blocks legitimate changes | Low | Medium | Document process for updating migrations (don't modify applied migrations) |

---

## 10. Documentation

### Code Documentation

- All classes and methods have comprehensive docstrings
- Docstrings include Args, Returns, Examples sections
- Type hints for all parameters and return values
- Warning messages include actionable guidance

### User Documentation

Updates needed in **Sortie 4**:
- Validation warning reference
- How to resolve SQLite limitations
- Best practices for safe migrations
- When to modify applied migrations (never!)

### Developer Documentation

Update **docs/DATABASE.md** with:
- MigrationValidator class overview
- Validation categories and rules
- Warning levels and meanings
- Checksum verification process

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-Migration-Manager-Foundation.md](SPEC-Sortie-1-Migration-Manager-Foundation.md)
- [SPEC-Sortie-2-NATS-Handlers-Execution.md](SPEC-Sortie-2-NATS-Handlers-Execution.md)

**Next**: 
- [SPEC-Sortie-4-Documentation-Examples.md](SPEC-Sortie-4-Documentation-Examples.md)

**Parent PRD**: [PRD-Schema-Migrations.md](PRD-Schema-Migrations.md)

**Related Sprints**:
- Sprint 13: Row Operations Foundation
- Sprint 16: Data Migrations

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation
