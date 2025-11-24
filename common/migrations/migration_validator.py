#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration validation for safety and compatibility checks.

Validates migrations for destructive operations, SQLite limitations,
syntax errors, and checksum integrity. Provides warnings at different
severity levels (INFO, WARNING, ERROR).

Sprint: 15 - Schema Migrations
Sortie: 3 - Safety Features & Validation
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import List

from common.migrations.migration import Migration


class WarningLevel(Enum):
    """Severity levels for validation warnings."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationWarning:
    """
    Warning from migration validation.
    
    Attributes:
        level: Severity level (INFO, WARNING, ERROR)
        message: Human-readable warning message
        migration_version: Migration version that triggered warning
        migration_name: Migration name that triggered warning
        category: Warning category ('checksum', 'destructive', 'sqlite', 'syntax')
    
    Example:
        >>> warning = ValidationWarning(
        ...     level=WarningLevel.ERROR,
        ...     message="SQLite does not support DROP COLUMN",
        ...     migration_version=3,
        ...     migration_name="remove_author",
        ...     category="sqlite"
        ... )
        >>> print(warning)
        [ERROR] Migration 3_remove_author: SQLite does not support DROP COLUMN
    """
    level: WarningLevel
    message: str
    migration_version: int
    migration_name: str
    category: str  # 'checksum', 'destructive', 'sqlite', 'syntax'
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary with all fields, level as string value
        
        Example:
            >>> warning.to_dict()
            {
                'level': 'ERROR',
                'message': 'SQLite does not support DROP COLUMN',
                'migration_version': 3,
                'migration_name': 'remove_author',
                'category': 'sqlite'
            }
        """
        return {
            'level': self.level.value,
            'message': self.message,
            'migration_version': self.migration_version,
            'migration_name': self.migration_name,
            'category': self.category
        }
    
    def __repr__(self) -> str:
        """String representation for logging."""
        return f"[{self.level.value}] Migration {self.migration_version}_{self.migration_name}: {self.message}"


class MigrationValidator:
    """
    Validates migrations for safety and compatibility issues.
    
    Performs multiple validation checks:
    - Destructive operations (DROP COLUMN, DROP TABLE, TRUNCATE)
    - SQLite limitations (unsupported ALTER operations)
    - Basic SQL syntax (parentheses, string quotes)
    - Checksum verification (file tampering detection)
    
    Attributes:
        db_type: Database type ('sqlite', 'postgresql', etc.)
        
    Example:
        >>> validator = MigrationValidator(db_type='sqlite')
        >>> warnings = validator.validate_migration(migration)
        >>> for w in warnings:
        ...     if w.level == WarningLevel.ERROR:
        ...         print(f"ERROR: {w.message}")
    """
    
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
    
    def validate_migration(self, migration: Migration) -> List[ValidationWarning]:
        """
        Validate a migration for safety and compatibility issues.
        
        Performs all validation checks and returns list of warnings.
        Checks performed:
        - Destructive operations (DROP, TRUNCATE)
        - SQLite limitations (if db_type='sqlite')
        - Basic SQL syntax (parentheses, quotes)
        
        Args:
            migration: Migration object to validate
            
        Returns:
            List of ValidationWarning objects (empty if no issues)
            
        Example:
            >>> validator = MigrationValidator(db_type='sqlite')
            >>> migration = Migration(...)
            >>> warnings = validator.validate_migration(migration)
            >>> errors = [w for w in warnings if w.level == WarningLevel.ERROR]
            >>> if errors:
            ...     print(f"Cannot proceed: {len(errors)} errors found")
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
        migration: Migration, 
        stored_checksum: str
    ) -> List[ValidationWarning]:
        """
        Verify migration file checksum matches stored checksum.
        
        Detects if migration file has been modified after being applied.
        This is a critical safety check to prevent inconsistencies.
        
        Args:
            migration: Migration object with current checksum
            stored_checksum: Checksum from database (when migration was applied)
            
        Returns:
            List with ERROR warning if mismatch, empty list if match
            
        Example:
            >>> validator = MigrationValidator()
            >>> warnings = validator.verify_checksums(migration, "abc123...")
            >>> if warnings:
            ...     print("WARNING: Migration file has been modified!")
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
    
    def _check_destructive_operations(self, migration: Migration) -> List[ValidationWarning]:
        """
        Check for destructive SQL operations.
        
        Scans UP SQL for operations that destroy data:
        - DROP COLUMN: Potential data loss
        - DROP TABLE: All table data will be deleted
        - TRUNCATE TABLE: All rows will be deleted
        
        All generate WARNING level (not ERROR) to allow execution with acknowledgment.
        
        Args:
            migration: Migration to check
            
        Returns:
            List of WARNING level ValidationWarning objects
        """
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
    
    def _check_sqlite_limitations(self, migration: Migration) -> List[ValidationWarning]:
        """
        Check for SQLite unsupported operations.
        
        SQLite has limited ALTER TABLE support. These operations generate ERROR
        warnings that prevent migration execution:
        - DROP COLUMN: Not supported directly
        - ALTER COLUMN: Not supported directly
        - ADD CONSTRAINT: Not supported directly
        
        All include workaround suggestions (table recreation pattern).
        
        Args:
            migration: Migration to check
            
        Returns:
            List of ERROR level ValidationWarning objects
        """
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
    
    def _check_syntax(self, migration: Migration) -> List[ValidationWarning]:
        """
        Check for basic SQL syntax errors.
        
        Performs simple checks that catch common errors:
        - Unmatched parentheses
        - Unterminated strings (odd number of quotes)
        
        These are basic heuristics and may have false positives/negatives,
        but catch most common syntax errors before execution.
        
        Args:
            migration: Migration to check
            
        Returns:
            List of ERROR level ValidationWarning objects for syntax issues
        """
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
