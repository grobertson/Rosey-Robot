"""
Database migrations package for plugin schema evolution.

This package provides:
- Migration: Data model for migration files
- AppliedMigration: Data model for applied migrations
- MigrationManager: Discovery, parsing, and tracking of migrations
"""

from .migration import Migration, AppliedMigration
from .migration_manager import MigrationManager

__all__ = ['Migration', 'AppliedMigration', 'MigrationManager']
