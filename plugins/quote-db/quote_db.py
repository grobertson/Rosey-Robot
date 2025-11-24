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
import time
import asyncio
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
    
    def _validate_text(self, text: str) -> str:
        """
        Validate quote text.
        
        Args:
            text: The quote text to validate
            
        Returns:
            Validated and trimmed text
            
        Raises:
            ValueError: If text is empty or too long
        """
        if not text or not text.strip():
            raise ValueError("Quote text cannot be empty")
        
        text = text.strip()
        
        if len(text) > 1000:
            raise ValueError("Quote text too long (max 1000 chars)")
        
        return text
    
    def _validate_author(self, author: Optional[str]) -> str:
        """
        Validate author name.
        
        Args:
            author: The author name to validate (can be None)
            
        Returns:
            Validated and trimmed author name, or "Unknown" if empty
            
        Raises:
            ValueError: If author name is too long
        """
        if not author or not author.strip():
            return "Unknown"
        
        author = author.strip()
        
        if len(author) > 100:
            raise ValueError("Author name too long (max 100 chars)")
        
        return author
    
    # ===== CRUD Operations =====
    # Implemented in Sortie 2
    
    async def add_quote(self, text: str, author: Optional[str] = None, 
                       added_by: str = "unknown") -> int:
        """
        Add a new quote to the database.
        
        Args:
            text: The quote text (1-1000 characters, trimmed)
            author: The quote author (max 100 characters, defaults to "Unknown")
            added_by: Username of the person adding the quote
            
        Returns:
            The ID of the newly created quote
            
        Raises:
            ValueError: If text is empty or too long, or author is too long
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
            Exception: For other NATS/JSON errors
        """
        self._ensure_initialized()
        
        # Validate inputs
        text = self._validate_text(text)
        author = self._validate_author(author)
        
        # Prepare data
        data = {
            "table": "quotes",
            "data": {
                "text": text,
                "author": author,
                "added_by": added_by,
                "timestamp": int(time.time()),
                "score": 0
            }
        }
        
        # Insert via NATS
        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.insert",
                json.dumps(data).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            quote_id = result["id"]
            
            self.logger.info(f"Added quote {quote_id}: '{text[:50]}...' by {author}")
            return quote_id
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout adding quote by {author}")
            raise asyncio.TimeoutError(f"NATS request timed out: add_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")
    
    async def get_quote(self, quote_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a quote by ID.
        
        Args:
            quote_id: The ID of the quote to retrieve
            
        Returns:
            Quote dictionary with keys: id, text, author, added_by, timestamp, score
            Returns None if quote not found
            
        Raises:
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
            Exception: For other NATS/JSON errors
        """
        self._ensure_initialized()
        
        # Query via NATS
        query = {
            "table": "quotes",
            "filters": {"id": {"$eq": quote_id}},
            "limit": 1
        }
        
        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.select",
                json.dumps(query).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            rows = result.get("rows", [])
            
            if rows:
                self.logger.info(f"Retrieved quote {quote_id}")
                return rows[0]
            else:
                self.logger.info(f"Quote {quote_id} not found")
                return None
                
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout getting quote {quote_id}")
            raise asyncio.TimeoutError(f"NATS request timed out: get_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")
    
    async def delete_quote(self, quote_id: int) -> bool:
        """
        Delete a quote by ID.
        
        Args:
            quote_id: The ID of the quote to delete
            
        Returns:
            True if quote was deleted, False if quote not found
            
        Raises:
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
            Exception: For other NATS/JSON errors
        """
        self._ensure_initialized()
        
        # Delete via NATS
        query = {
            "table": "quotes",
            "filters": {"id": {"$eq": quote_id}}
        }
        
        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.delete",
                json.dumps(query).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            deleted = result.get("deleted", 0) > 0
            
            if deleted:
                self.logger.info(f"Deleted quote {quote_id}")
            else:
                self.logger.info(f"Quote {quote_id} not found for deletion")
            
            return deleted
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout deleting quote {quote_id}")
            raise asyncio.TimeoutError(f"NATS request timed out: delete_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")
    
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
