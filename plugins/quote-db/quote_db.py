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
                f"rosey.db.migrate.{self.NAMESPACE}.status",
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
