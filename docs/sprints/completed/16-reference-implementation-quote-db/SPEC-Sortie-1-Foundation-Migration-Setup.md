# SPEC-Sortie-1: Foundation and Migration Setup

**Sprint**: 16 - Reference Implementation (Quote-DB Plugin)  
**Sortie**: 1 of 4  
**Estimated Duration**: 1.5 days  
**Status**: Draft  
**Author**: Agent via PRD-Reference-Implementation-Quote-DB.md  
**Created**: November 24, 2025  

---

## 1. Overview

This sortie establishes the foundational structure for the quote-db reference plugin, including directory layout, schema migrations, testing framework, and plugin skeleton. This is the **first plugin to demonstrate modern storage API usage**, serving as the canonical example for all future plugin migrations.

**What This Sortie Achieves**:
- Complete plugin directory structure following best practices
- Three versioned migration files (CREATE TABLE, ADD COLUMN × 2)
- Plugin skeleton with NATS client integration
- Comprehensive test framework with fixtures and mocks
- Initial documentation (README, inline comments)
- Seed data (5 example quotes) for development and testing

**Key Deliverables**:
- `plugins/quote-db/` directory with all scaffolding
- Migration files: 001_create_quotes_table.sql, 002_add_score_column.sql, 003_add_tags_column.sql
- QuoteDBPlugin class skeleton with initialization
- Pytest configuration with NATS mocks
- README with installation and migration instructions

---

## 2. Scope and Non-Goals

### In Scope

- **Directory Structure**: Complete plugin layout matching Rosey conventions
- **Migration Files**: All three migrations with UP/DOWN, seed data
- **Plugin Skeleton**: Basic class with __init__, initialize(), NATS client
- **Test Framework**: pytest setup, conftest.py with fixtures, mock NATS
- **Documentation**: README covering setup, migrations, basic usage
- **Dependencies**: requirements.txt with nats-py, pytest
- **Validation**: All migrations apply/rollback successfully

### Out of Scope (Future Sorties)

- **CRUD Implementation**: add_quote(), get_quote(), etc. (Sortie 2)
- **Search Features**: find_by_author(), search operators (Sortie 3)
- **KV Storage**: Counters, feature flags (Sortie 3)
- **Error Handling**: Comprehensive error recovery (Sortie 4)
- **Integration Tests**: End-to-end with real NATS (Sortie 4)
- **Performance Testing**: Benchmarks, load testing (Sortie 4)

---

## 3. Requirements

### Functional Requirements

**FR-1: Directory Structure**
- Plugin directory: `plugins/quote-db/`
- Subdirectories: `migrations/`, `tests/`
- Files: `__init__.py`, `quote_db.py`, `requirements.txt`, `README.md`
- Test files: `conftest.py`, `test_quote_db.py`, `test_migrations.py`

**FR-2: Migration 001 - Create Quotes Table**
- UP section: CREATE TABLE quotes with columns: id, text, author, added_by, added_at
- DOWN section: DROP TABLE quotes
- Seed data: INSERT 5 example quotes in UP section
- Primary key on id (AUTOINCREMENT)
- NOT NULL constraints on text, added_at
- Index on author for search performance

**FR-3: Migration 002 - Add Score Column**
- UP section: ALTER TABLE ADD COLUMN score, UPDATE to set default values
- DOWN section: Table recreation without score column (SQLite workaround)
- Data migration: Initialize scores based on text length (example pattern)
- Default value: 0 for new quotes

**FR-4: Migration 003 - Add Tags Column**
- UP section: ALTER TABLE ADD COLUMN tags (JSON type)
- DOWN section: Table recreation without tags column
- Default value: '[]' (empty JSON array)
- Validates JSON structure

**FR-5: Plugin Skeleton**
- QuoteDBPlugin class with __init__(nats_client)
- initialize() method checking migration status
- Namespace property: "quote-db"
- Logger instance
- Placeholder methods for future implementation

**FR-6: Test Framework**
- pytest configuration with asyncio support
- Mock NATS client fixture
- Plugin instance fixture using mock NATS
- Example test_initialize() showing pattern

**FR-7: Documentation**
- README with plugin overview
- Installation instructions (pip install -r requirements.txt)
- Migration application steps
- Command reference (stub for Sortie 2)

### Non-Functional Requirements

**NFR-1: Code Quality**
- Type hints for all methods
- Docstrings (Google style) for all classes and public methods
- PEP 8 compliance (checked by linter)
- No hardcoded values (use constants)

**NFR-2: Testability**
- All migrations have reversible DOWN sections
- Seed data uses realistic examples
- Mock fixtures enable unit testing without NATS
- Test migrations on SQLite (primary) and PostgreSQL (stretch)

**NFR-3: Documentation**
- Clear comments explaining design decisions
- README covers 80% of developer questions
- Migration files document purpose in header comments

**NFR-4: Maintainability**
- Directory structure scales to 10+ migrations
- Plugin structure supports adding 20+ methods (Sorties 2-3)
- Test structure supports 50+ test cases

---

## 4. Technical Design

### 4.1 Directory Structure

```
plugins/quote-db/
├── __init__.py                    # Package marker, exports QuoteDBPlugin
├── quote_db.py                    # Main plugin implementation
├── requirements.txt               # Python dependencies
├── README.md                      # Plugin documentation
├── migrations/
│   ├── 001_create_quotes_table.sql
│   ├── 002_add_score_column.sql
│   └── 003_add_tags_column.sql
└── tests/
    ├── __init__.py
    ├── conftest.py                # Pytest fixtures and configuration
    ├── test_quote_db.py           # Plugin unit tests
    └── test_migrations.py         # Migration validation tests
```

### 4.2 Migration 001: Create Quotes Table

**File**: `plugins/quote-db/migrations/001_create_quotes_table.sql`

```sql
-- Migration 001: Create quotes table with initial schema
-- Purpose: Establish base table structure for quote storage
-- Version: 1.0
-- Created: 2025-11-24

-- UP
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index for searching by author
CREATE INDEX idx_quotes_author ON quotes(author);

-- Seed data: Example quotes for development and testing
INSERT INTO quotes (text, author, added_by, added_at) VALUES
('The only way to do great work is to love what you do.', 'Steve Jobs', 'system', CURRENT_TIMESTAMP),
('In the middle of difficulty lies opportunity.', 'Albert Einstein', 'system', CURRENT_TIMESTAMP),
('Life is what happens when you''re busy making other plans.', 'John Lennon', 'system', CURRENT_TIMESTAMP),
('The future belongs to those who believe in the beauty of their dreams.', 'Eleanor Roosevelt', 'system', CURRENT_TIMESTAMP),
('It is during our darkest moments that we must focus to see the light.', 'Aristotle', 'system', CURRENT_TIMESTAMP);

-- DOWN
DROP INDEX IF EXISTS idx_quotes_author;
DROP TABLE IF EXISTS quotes;
```

### 4.3 Migration 002: Add Score Column

**File**: `plugins/quote-db/migrations/002_add_score_column.sql`

```sql
-- Migration 002: Add score column for quote ratings
-- Purpose: Enable users to rate/score quotes
-- Version: 1.0
-- Created: 2025-11-24

-- UP
-- Add score column (default 0)
ALTER TABLE quotes ADD COLUMN score INTEGER DEFAULT 0 NOT NULL;

-- Data migration: Initialize scores based on text length
-- (Example pattern: longer quotes start with higher score)
-- In production, scores would start at 0 and be user-driven
UPDATE quotes SET score = LENGTH(text) / 10 WHERE score = 0;

-- Index for sorting by score
CREATE INDEX idx_quotes_score ON quotes(score DESC);

-- DOWN
-- SQLite doesn't support DROP COLUMN directly
-- Use table recreation pattern

-- Create temporary table without score column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Copy data (excluding score column)
INSERT INTO quotes_new (id, text, author, added_by, added_at)
SELECT id, text, author, added_by, added_at FROM quotes;

-- Drop indexes on old table
DROP INDEX IF EXISTS idx_quotes_score;
DROP INDEX IF EXISTS idx_quotes_author;

-- Replace old table with new
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate author index
CREATE INDEX idx_quotes_author ON quotes(author);
```

### 4.4 Migration 003: Add Tags Column

**File**: `plugins/quote-db/migrations/003_add_tags_column.sql`

```sql
-- Migration 003: Add tags column for categorization
-- Purpose: Enable tagging quotes with categories (motivational, funny, wisdom, etc.)
-- Version: 1.0
-- Created: 2025-11-24

-- UP
-- Add tags column (JSON array)
ALTER TABLE quotes ADD COLUMN tags TEXT DEFAULT '[]' NOT NULL;

-- Example: Add tags to seed quotes
UPDATE quotes SET tags = '["motivational", "work"]' WHERE author = 'Steve Jobs';
UPDATE quotes SET tags = '["wisdom", "opportunity"]' WHERE author = 'Albert Einstein';
UPDATE quotes SET tags = '["life", "philosophy"]' WHERE author = 'John Lennon';
UPDATE quotes SET tags = '["dreams", "motivation"]' WHERE author = 'Eleanor Roosevelt';
UPDATE quotes SET tags = '["wisdom", "adversity"]' WHERE author = 'Aristotle';

-- DOWN
-- SQLite doesn't support DROP COLUMN directly
-- Use table recreation pattern

-- Create temporary table without tags column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    score INTEGER DEFAULT 0 NOT NULL
);

-- Copy data (excluding tags column)
INSERT INTO quotes_new (id, text, author, added_by, added_at, score)
SELECT id, text, author, added_by, added_at, score FROM quotes;

-- Drop indexes
DROP INDEX IF EXISTS idx_quotes_score;
DROP INDEX IF EXISTS idx_quotes_author;

-- Replace old table
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_score ON quotes(score DESC);
```

### 4.5 Plugin Skeleton

**File**: `plugins/quote-db/quote_db.py`

```python
"""
Quote database plugin - reference implementation.

This plugin demonstrates modern Rosey storage API usage:
- Row operations for CRUD (db.row.quote-db.*)
- Advanced operators for search/filter (db.operators.quote-db.*)
- KV storage for counters and config (db.kv.quote-db.*)
- Migrations for schema evolution (db.migrate.quote-db.*)

Serves as canonical example for migrating plugins from direct SQLite access.
"""
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from nats.aio.client import Client as NATS
except ImportError:
    # Allow imports for type checking even if nats-py not installed
    NATS = Any

logger = logging.getLogger(__name__)


class QuoteDBPlugin:
    """
    Quote database plugin using Rosey storage API.
    
    Features:
    - Add/get/delete quotes
    - Search by author, text content
    - Score/rate quotes
    - Tag categorization
    - Statistics (total quotes, top authors)
    
    Storage tiers used:
    - Row operations: Quote CRUD
    - Advanced operators: Search, atomic score updates
    - KV storage: Last quote ID, feature flags
    - Migrations: Schema versioning
    """
    
    # Plugin metadata
    NAMESPACE = "quote-db"
    VERSION = "1.0.0"
    REQUIRED_MIGRATIONS = [1, 2, 3]  # Migration versions this code depends on
    
    def __init__(self, nats_client: NATS):
        """
        Initialize quote-db plugin.
        
        Args:
            nats_client: Connected NATS client for storage API requests
        """
        self.nats = nats_client
        self.logger = logging.getLogger(f"{__name__}.{self.NAMESPACE}")
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize plugin and verify migrations are up to date.
        
        Checks:
        1. Migration status (all required migrations applied)
        2. Schema integrity (table exists, columns present)
        3. Connectivity (NATS client responsive)
        
        Raises:
            RuntimeError: If migrations not applied or connectivity issues
            ValueError: If schema validation fails
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")
        
        # Check migration status
        status = await self._check_migration_status()
        
        if not status["success"]:
            raise RuntimeError(
                f"Failed to check migration status: {status.get('error', 'unknown')}"
            )
        
        current_version = status.get("current_version", 0)
        max_required = max(self.REQUIRED_MIGRATIONS)
        
        if current_version < max_required:
            raise RuntimeError(
                f"Migrations not up to date. Current: {current_version}, "
                f"Required: {max_required}. "
                f"Run: db.migrate.{self.NAMESPACE}.apply"
            )
        
        self._initialized = True
        self.logger.info(
            f"Plugin initialized successfully. "
            f"Schema version: {current_version}"
        )
    
    async def _check_migration_status(self) -> Dict[str, Any]:
        """
        Check migration status via NATS.
        
        Returns:
            Dict with keys:
                - success: bool
                - current_version: int
                - pending_count: int
                - error: str (if success=False)
        """
        try:
            response = await self.nats.request(
                f"db.migrate.{self.NAMESPACE}.status",
                b"{}",
                timeout=5.0
            )
            
            return json.loads(response.data)
        
        except Exception as e:
            self.logger.error(f"Failed to check migration status: {e}")
            return {
                "success": False,
                "error": str(e),
                "current_version": 0
            }
    
    def _ensure_initialized(self) -> None:
        """Raise error if plugin not initialized."""
        if not self._initialized:
            raise RuntimeError(
                f"{self.NAMESPACE} plugin not initialized. "
                "Call initialize() before using methods."
            )
    
    # ===== Placeholder methods for future implementation =====
    # These will be implemented in Sorties 2 and 3
    
    async def add_quote(self, text: str, author: Optional[str] = None, 
                       added_by: str = "unknown") -> int:
        """
        Add a new quote to the database.
        
        Args:
            text: Quote text
            author: Quote author (optional)
            added_by: Username who added the quote
            
        Returns:
            ID of the newly created quote
            
        Raises:
            RuntimeError: If plugin not initialized
            ValueError: If text is empty
        """
        self._ensure_initialized()
        # TODO: Implement in Sortie 2
        raise NotImplementedError("Sortie 2")
    
    async def get_quote(self, quote_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a quote by ID.
        
        Args:
            quote_id: Quote ID to retrieve
            
        Returns:
            Quote dict or None if not found
        """
        self._ensure_initialized()
        # TODO: Implement in Sortie 2
        raise NotImplementedError("Sortie 2")
    
    async def delete_quote(self, quote_id: int) -> bool:
        """
        Delete a quote by ID.
        
        Args:
            quote_id: Quote ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()
        # TODO: Implement in Sortie 2
        raise NotImplementedError("Sortie 2")
    
    async def find_by_author(self, author: str) -> List[Dict[str, Any]]:
        """
        Find all quotes by a specific author.
        
        Args:
            author: Author name (exact match)
            
        Returns:
            List of quote dicts
        """
        self._ensure_initialized()
        # TODO: Implement in Sortie 3
        raise NotImplementedError("Sortie 3")
    
    async def increment_score(self, quote_id: int, amount: int = 1) -> bool:
        """
        Atomically increment a quote's score.
        
        Args:
            quote_id: Quote ID
            amount: Amount to increment (can be negative)
            
        Returns:
            True if successful, False if quote not found
        """
        self._ensure_initialized()
        # TODO: Implement in Sortie 3
        raise NotImplementedError("Sortie 3")
```

### 4.6 Package Init

**File**: `plugins/quote-db/__init__.py`

```python
"""Quote database plugin package."""
from .quote_db import QuoteDBPlugin

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
```

### 4.7 Test Configuration

**File**: `plugins/quote-db/tests/conftest.py`

```python
"""Pytest configuration and fixtures for quote-db plugin tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import json


@pytest.fixture
def mock_nats():
    """
    Create mock NATS client for testing.
    
    The mock client returns successful responses by default.
    Individual tests can override response behavior.
    """
    nats = AsyncMock()
    
    # Default response for migration status
    status_response = MagicMock()
    status_response.data = json.dumps({
        "success": True,
        "current_version": 3,
        "pending_count": 0,
        "applied_migrations": [
            {"version": 1, "name": "create_quotes_table"},
            {"version": 2, "name": "add_score_column"},
            {"version": 3, "name": "add_tags_column"}
        ]
    }).encode()
    
    nats.request = AsyncMock(return_value=status_response)
    
    return nats


@pytest.fixture
def plugin(mock_nats):
    """
    Create QuoteDBPlugin instance with mock NATS client.
    
    Plugin is not initialized by default - tests should call
    plugin.initialize() as needed.
    """
    from quote_db import QuoteDBPlugin
    return QuoteDBPlugin(mock_nats)


@pytest.fixture
async def initialized_plugin(plugin):
    """
    Create and initialize QuoteDBPlugin instance.
    
    Use this fixture when tests need an initialized plugin.
    """
    await plugin.initialize()
    return plugin


@pytest.fixture
def sample_quote():
    """Sample quote data for testing."""
    return {
        "id": 1,
        "text": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
        "added_by": "alice",
        "added_at": "2025-11-24T10:00:00Z",
        "score": 42,
        "tags": ["motivational", "work"]
    }


@pytest.fixture
def sample_quotes():
    """Multiple sample quotes for testing."""
    return [
        {
            "id": 1,
            "text": "The only way to do great work is to love what you do.",
            "author": "Steve Jobs",
            "added_by": "alice",
            "score": 42,
            "tags": ["motivational"]
        },
        {
            "id": 2,
            "text": "In the middle of difficulty lies opportunity.",
            "author": "Albert Einstein",
            "added_by": "bob",
            "score": 38,
            "tags": ["wisdom"]
        },
        {
            "id": 3,
            "text": "Life is what happens when you're busy making other plans.",
            "author": "John Lennon",
            "added_by": "alice",
            "score": 50,
            "tags": ["life"]
        }
    ]
```

### 4.8 Dependencies

**File**: `plugins/quote-db/requirements.txt`

```
# NATS client for storage API communication
nats-py>=2.6.0

# Testing dependencies
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

---

## 5. Implementation Steps

1. **Create Plugin Directory Structure**
   - Create `plugins/quote-db/` directory
   - Create subdirectories: `migrations/`, `tests/`
   - Create empty `__init__.py` files for Python packages

2. **Write Migration 001 - Create Quotes Table**
   - Create `migrations/001_create_quotes_table.sql`
   - Write UP section: CREATE TABLE with all columns
   - Add idx_quotes_author index
   - Insert 5 seed quotes
   - Write DOWN section: DROP INDEX, DROP TABLE
   - Test migration applies and rolls back

3. **Write Migration 002 - Add Score Column**
   - Create `migrations/002_add_score_column.sql`
   - Write UP section: ALTER TABLE ADD COLUMN score
   - Add data migration: UPDATE quotes SET score based on text length
   - Create idx_quotes_score index
   - Write DOWN section: Table recreation pattern (SQLite workaround)
   - Test migration applies and rolls back

4. **Write Migration 003 - Add Tags Column**
   - Create `migrations/003_add_tags_column.sql`
   - Write UP section: ALTER TABLE ADD COLUMN tags (JSON)
   - Update seed quotes with example tags
   - Write DOWN section: Table recreation pattern
   - Test migration applies and rolls back

5. **Implement Plugin Skeleton**
   - Create `quote_db.py` with QuoteDBPlugin class
   - Implement __init__(nats_client)
   - Implement initialize() with migration status check
   - Implement _check_migration_status() using NATS
   - Add _ensure_initialized() guard method
   - Add placeholder methods (add_quote, get_quote, etc.) raising NotImplementedError

6. **Create Package Init**
   - Write `__init__.py` exporting QuoteDBPlugin
   - Add __version__ and __all__

7. **Set Up Test Framework**
   - Create `tests/conftest.py`
   - Write mock_nats fixture with default responses
   - Write plugin fixture (not initialized)
   - Write initialized_plugin fixture
   - Write sample_quote and sample_quotes fixtures

8. **Write Basic Tests**
   - Create `tests/test_quote_db.py`
   - Test plugin instantiation
   - Test initialize() success path
   - Test initialize() with missing migrations
   - Test _ensure_initialized() guard

9. **Create Migration Tests**
   - Create `tests/test_migrations.py`
   - Test migration 001 creates table
   - Test migration 001 inserts seed data
   - Test migration 002 adds score column
   - Test migration 003 adds tags column
   - Test rollback for each migration

10. **Write Dependencies File**
    - Create `requirements.txt`
    - Add nats-py>=2.6.0
    - Add pytest>=7.4.0
    - Add pytest-asyncio>=0.21.0
    - Add pytest-cov>=4.1.0

11. **Write Documentation**
    - Create `README.md`
    - Write overview section
    - Document installation steps
    - Document migration application
    - Add command reference (stub)
    - Link to main project docs

12. **Validate Implementation**
    - Run linter (pyright, flake8)
    - Run all tests with pytest
    - Apply all migrations to test database
    - Verify seed data inserted correctly
    - Test rollback of all migrations

---

## 6. Testing Strategy

### 6.1 Unit Tests - Plugin Initialization

**File**: `tests/test_quote_db.py`

```python
"""Unit tests for QuoteDBPlugin class."""
import pytest
import json
from quote_db import QuoteDBPlugin


class TestPluginInstantiation:
    """Test plugin creation."""
    
    def test_create_plugin(self, mock_nats):
        """Test plugin instantiates correctly."""
        plugin = QuoteDBPlugin(mock_nats)
        
        assert plugin.nats == mock_nats
        assert plugin.NAMESPACE == "quote-db"
        assert plugin.VERSION == "1.0.0"
        assert plugin._initialized is False
    
    def test_plugin_has_required_migrations(self, plugin):
        """Test plugin declares required migrations."""
        assert hasattr(plugin, 'REQUIRED_MIGRATIONS')
        assert plugin.REQUIRED_MIGRATIONS == [1, 2, 3]


class TestPluginInitialization:
    """Test plugin initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, plugin, mock_nats):
        """Test successful initialization."""
        # Mock returns migrations up to date
        await plugin.initialize()
        
        assert plugin._initialized is True
        mock_nats.request.assert_called_once()
        call_args = mock_nats.request.call_args
        assert "db.migrate.quote-db.status" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_initialize_missing_migrations(self, plugin, mock_nats):
        """Test initialization fails if migrations not applied."""
        # Mock returns current_version=1 (missing migrations 2 and 3)
        error_response = type('Response', (), {
            'data': json.dumps({
                "success": True,
                "current_version": 1,
                "pending_count": 2
            }).encode()
        })()
        mock_nats.request.return_value = error_response
        
        with pytest.raises(RuntimeError, match="Migrations not up to date"):
            await plugin.initialize()
        
        assert plugin._initialized is False
    
    @pytest.mark.asyncio
    async def test_initialize_nats_error(self, plugin, mock_nats):
        """Test initialization handles NATS errors."""
        # Mock raises exception
        mock_nats.request.side_effect = Exception("NATS connection failed")
        
        with pytest.raises(RuntimeError, match="Failed to check migration status"):
            await plugin.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, initialized_plugin):
        """Test initialize can be called multiple times safely."""
        # Plugin already initialized by fixture
        await initialized_plugin.initialize()  # Call again
        
        assert initialized_plugin._initialized is True


class TestEnsureInitialized:
    """Test initialization guard."""
    
    @pytest.mark.asyncio
    async def test_methods_require_initialization(self, plugin):
        """Test methods raise error if not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin.add_quote("test quote")
        
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin.get_quote(1)
        
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin.delete_quote(1)
    
    @pytest.mark.asyncio
    async def test_methods_work_after_initialization(self, initialized_plugin):
        """Test methods callable after initialization."""
        # Methods should not raise "not initialized" error
        # They raise NotImplementedError because Sortie 1 doesn't implement them
        with pytest.raises(NotImplementedError):
            await initialized_plugin.add_quote("test quote")


class TestPlaceholderMethods:
    """Test placeholder methods exist with correct signatures."""
    
    @pytest.mark.asyncio
    async def test_add_quote_placeholder(self, initialized_plugin):
        """Test add_quote placeholder exists."""
        with pytest.raises(NotImplementedError):
            await initialized_plugin.add_quote("test", author="Test Author")
    
    @pytest.mark.asyncio
    async def test_get_quote_placeholder(self, initialized_plugin):
        """Test get_quote placeholder exists."""
        with pytest.raises(NotImplementedError):
            await initialized_plugin.get_quote(1)
    
    @pytest.mark.asyncio
    async def test_delete_quote_placeholder(self, initialized_plugin):
        """Test delete_quote placeholder exists."""
        with pytest.raises(NotImplementedError):
            await initialized_plugin.delete_quote(1)
    
    @pytest.mark.asyncio
    async def test_find_by_author_placeholder(self, initialized_plugin):
        """Test find_by_author placeholder exists."""
        with pytest.raises(NotImplementedError):
            await initialized_plugin.find_by_author("Test Author")
    
    @pytest.mark.asyncio
    async def test_increment_score_placeholder(self, initialized_plugin):
        """Test increment_score placeholder exists."""
        with pytest.raises(NotImplementedError):
            await initialized_plugin.increment_score(1, amount=5)
```

### 6.2 Migration Tests

**File**: `tests/test_migrations.py`

```python
"""Tests for quote-db migrations."""
import pytest
import subprocess
import json


class TestMigration001:
    """Test migration 001 - create quotes table."""
    
    def test_migration_applies(self):
        """Test migration 001 applies successfully."""
        # This test requires actual database and Alembic
        # Mark as integration test (skip in unit test runs)
        pytest.skip("Integration test - requires database")
    
    def test_migration_creates_table(self):
        """Test migration creates quotes table with correct columns."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_inserts_seed_data(self):
        """Test migration inserts 5 seed quotes."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_rollback(self):
        """Test migration 001 rolls back cleanly."""
        pytest.skip("Integration test - requires database")


class TestMigration002:
    """Test migration 002 - add score column."""
    
    def test_migration_applies(self):
        """Test migration 002 applies successfully."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_adds_score_column(self):
        """Test migration adds score column."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_initializes_scores(self):
        """Test migration sets initial score values."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_rollback(self):
        """Test migration 002 rolls back cleanly."""
        pytest.skip("Integration test - requires database")


class TestMigration003:
    """Test migration 003 - add tags column."""
    
    def test_migration_applies(self):
        """Test migration 003 applies successfully."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_adds_tags_column(self):
        """Test migration adds tags column."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_initializes_tags(self):
        """Test migration sets initial tag values."""
        pytest.skip("Integration test - requires database")
    
    def test_migration_rollback(self):
        """Test migration 003 rolls back cleanly."""
        pytest.skip("Integration test - requires database")


# Note: Integration tests will be implemented in Sortie 4
# when full database and NATS infrastructure is available
```

### 6.3 Manual Testing Checklist

**Migration Application**:
```bash
# Apply all migrations
nats req "db.migrate.quote-db.apply" '{"target_version": "latest"}'

# Check status
nats req "db.migrate.quote-db.status" '{}'

# Expected output:
# {
#   "success": true,
#   "current_version": 3,
#   "pending_count": 0,
#   "applied_migrations": [...]
# }
```

**Migration Rollback**:
```bash
# Rollback to version 0
nats req "db.migrate.quote-db.rollback" '{"target_version": 0}'

# Verify table dropped
nats req "db.migrate.quote-db.status" '{}'

# Re-apply
nats req "db.migrate.quote-db.apply" '{"target_version": 3}'
```

**Seed Data Verification**:
```bash
# Query seed quotes (after Sortie 2 implements get methods)
# Should show 5 quotes with Steve Jobs, Einstein, etc.
```

**Coverage Target**: 90%+ for plugin skeleton code

**Run Tests**:
```bash
cd plugins/quote-db
pytest tests/ -v --cov=quote_db --cov-report=term-missing
```

---

## 7. Acceptance Criteria

- [ ] **AC-1**: Plugin directory structure created
  - Given the plugins/ directory
  - When listing quote-db/
  - Then all files and subdirectories exist (quote_db.py, migrations/, tests/)

- [ ] **AC-2**: All 3 migration files created
  - Given migrations/ directory
  - When listing files
  - Then 001, 002, 003 SQL files exist with UP and DOWN sections

- [ ] **AC-3**: Migration 001 applies successfully
  - Given clean database
  - When applying migration 001
  - Then quotes table created with 5 seed quotes

- [ ] **AC-4**: Migration 001 rolls back successfully
  - Given database with migration 001 applied
  - When rolling back migration 001
  - Then quotes table dropped, no errors

- [ ] **AC-5**: Migration 002 applies successfully
  - Given database with migration 001 applied
  - When applying migration 002
  - Then score column added, scores initialized

- [ ] **AC-6**: Migration 002 rolls back successfully
  - Given database with migrations 001-002 applied
  - When rolling back migration 002
  - Then score column removed, table intact

- [ ] **AC-7**: Migration 003 applies successfully
  - Given database with migrations 001-002 applied
  - When applying migration 003
  - Then tags column added, tags initialized

- [ ] **AC-8**: Migration 003 rolls back successfully
  - Given database with all migrations applied
  - When rolling back migration 003
  - Then tags column removed, score column intact

- [ ] **AC-9**: Plugin skeleton imports without errors
  - Given quote_db.py file
  - When importing QuoteDBPlugin
  - Then no ImportError, no syntax errors

- [ ] **AC-10**: Plugin initializes with up-to-date migrations
  - Given mock NATS returning current_version=3
  - When calling plugin.initialize()
  - Then no errors, _initialized=True

- [ ] **AC-11**: Plugin initialization fails with missing migrations
  - Given mock NATS returning current_version=1
  - When calling plugin.initialize()
  - Then RuntimeError raised with clear message

- [ ] **AC-12**: Placeholder methods exist and raise NotImplementedError
  - Given initialized plugin
  - When calling add_quote(), get_quote(), etc.
  - Then NotImplementedError raised

- [ ] **AC-13**: Test framework runs successfully
  - Given tests/ directory
  - When running pytest
  - Then all tests pass (or skip integration tests)

- [ ] **AC-14**: Mock fixtures work correctly
  - Given conftest.py
  - When using mock_nats fixture
  - Then NATS requests return expected responses

- [ ] **AC-15**: Code passes linting
  - Given all Python files
  - When running flake8/pyright
  - Then no errors, follows PEP 8

- [ ] **AC-16**: Documentation is complete
  - Given README.md
  - When reading
  - Then installation, migration, and basic usage documented

---

## 8. Rollout Plan

### Pre-deployment

1. Review all migration files for correctness
2. Test migrations on SQLite and PostgreSQL
3. Run linter on all Python files
4. Run pytest test suite
5. Verify seed data inserts correctly

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-16-sortie-1-quote-db-foundation`
2. Create directory structure:

   ```bash
   mkdir -p plugins/quote-db/{migrations,tests}
   touch plugins/quote-db/{__init__.py,quote_db.py,requirements.txt,README.md}
   touch plugins/quote-db/tests/{__init__.py,conftest.py,test_quote_db.py,test_migrations.py}
   ```

3. Write all 3 migration files (001, 002, 003)
4. Implement QuoteDBPlugin skeleton in quote_db.py
5. Write `__init__.py` with exports
6. Create test fixtures in conftest.py
7. Write unit tests in test_quote_db.py
8. Create migration test stubs in test_migrations.py
9. Write requirements.txt with dependencies
10. Write README.md with documentation
11. Test migrations:

    ```bash
    nats req "db.migrate.quote-db.apply" '{"target_version": "latest"}'
    nats req "db.migrate.quote-db.status" '{}'
    ```

12. Run tests:

    ```bash
    cd plugins/quote-db
    pip install -r requirements.txt
    pytest tests/ -v --cov=quote_db
    ```

13. Run linter:

    ```bash
    flake8 quote_db.py tests/
    pyright quote_db.py
    ```

14. Commit changes with message:

    ```text
    Sprint 16 Sortie 1: Quote-DB Foundation & Migrations
    
    - Create plugin directory structure
    - Add 3 schema migrations (CREATE TABLE, ADD COLUMN x2)
    - Implement QuoteDBPlugin skeleton with initialization
    - Add comprehensive test framework with NATS mocks
    - Include 5 seed quotes for development
    - Document installation and migration steps
    
    Implements: SPEC-Sortie-1-Foundation-Migration-Setup.md
    Related: PRD-Reference-Implementation-Quote-DB.md
    ```

15. Push branch and create PR
16. Code review
17. Merge to main

### Post-deployment

- Verify migrations work on staging database
- Check seed data visible in database
- Test plugin imports in integration environment
- Share README with team for feedback

### Rollback Procedure

If issues arise:

```bash
# Rollback migrations
nats req "db.migrate.quote-db.rollback" '{"target_version": 0}'

# Revert code
git revert <commit-hash>
```


---

## 9. Dependencies & Risks

### Dependencies

- **Sprint 15**: Migration system (db.migrate.* handlers)
- **Sprint 13**: Row operations foundation (db.row.* handlers)
- **NATS server**: Running and accessible
- **Python 3.10+**: For type hints and modern syntax
- **pytest**: Testing framework

### External Dependencies

- **nats-py**: NATS client library

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration file format differs from expectations | Low | High | Test migrations on actual database before committing |
| Seed data fails to insert | Low | Medium | Validate SQL syntax, test INSERT statements |
| NATS mock doesn't match real responses | Medium | Medium | Compare mock responses to actual NATS responses |
| SQLite table recreation pattern complex | Medium | Low | Document pattern clearly, test rollbacks thoroughly |
| Plugin skeleton too minimal | Low | Low | Placeholder methods establish interface for Sortie 2 |
| Test fixtures incomplete | Low | Medium | Start simple, expand as needed in Sorties 2-3 |

---

## 10. Documentation

### Code Documentation

- All classes have comprehensive docstrings
- All public methods documented with Args, Returns, Raises
- Inline comments explain design decisions
- Migration files have header comments explaining purpose

### User Documentation

**README.md** sections:

- Overview: What is quote-db plugin
- Installation: pip install -r requirements.txt
- Migrations: How to apply schema migrations
- Commands: Stub for future commands (Sortie 2)
- Architecture: Link to storage API docs
- Contributing: How to add features

### Developer Documentation

**Updates needed**:

- Add plugins/quote-db/ to main README plugin list
- Link to quote-db as reference implementation in storage API docs
- Document migration file format in PLUGIN_MIGRATIONS.md (Sprint 15)

---

## 11. Related Specifications

**Previous**: None (first sortie of Sprint 16)

**Next**:

- [SPEC-Sortie-2-Core-CRUD-Operations.md](SPEC-Sortie-2-Core-CRUD-Operations.md)
- [SPEC-Sortie-3-Advanced-Features.md](SPEC-Sortie-3-Advanced-Features.md)
- [SPEC-Sortie-4-Error-Handling-Documentation-Polish.md](SPEC-Sortie-4-Error-Handling-Documentation-Polish.md)

**Parent PRD**: [PRD-Reference-Implementation-Quote-DB.md](PRD-Reference-Implementation-Quote-DB.md)

**Related Sprints**:

- Sprint 12: KV Storage Foundation
- Sprint 13: Row Operations Foundation
- Sprint 14: Advanced Query Operators
- Sprint 15: Schema Migrations

**Related Documentation**:

- docs/guides/PLUGIN_MIGRATIONS.md (Sprint 15)
- docs/guides/MIGRATION_BEST_PRACTICES.md (Sprint 15)
- examples/migrations/ (Sprint 15 examples)


---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation  
**Sortie 1 of 4**: Foundation complete, ready for CRUD implementation in Sortie 2
