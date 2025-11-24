"""
Database migrations package for plugin schema evolution.

This package provides:
- Migration: Data model for migration files
- AppliedMigration: Data model for applied migrations
- MigrationManager: Discovery, parsing, and tracking of migrations
- MigrationExecutor: Execution of migrations with transaction safety
- MigrationResult: Data model for execution results
- DryRunRollback: Exception for dry-run mode
"""

from .migration import Migration, AppliedMigration
from .migration_manager import MigrationManager
from .migration_executor import (
    DryRunRollback,
    MigrationExecutor,
    MigrationResult,
)

__all__ = [
    'Migration',
    'AppliedMigration',
    'MigrationManager',
    'MigrationExecutor',
    'MigrationResult',
    'DryRunRollback',
]
