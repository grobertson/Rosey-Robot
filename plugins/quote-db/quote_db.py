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
import random
from typing import Optional, List, Dict, Any

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

    # Constants
    DEFAULT_NATS_TIMEOUT = 2.0  # seconds
    DEFAULT_KV_TIMEOUT = 1.0  # seconds
    DEFAULT_MAX_RETRIES = 3
    KV_CACHE_TTL = 300  # 5 minutes
    MAX_SEARCH_LIMIT = 100
    MIN_SEARCH_LIMIT = 1

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

        # Skip if already initialized (idempotent)
        if self._initialized:
            self.logger.debug("Plugin already initialized, skipping")
            return

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

        # Register table schema (required for row operations)
        await self._register_schema()

        self._initialized = True
        self.logger.info(
            f"Plugin initialized successfully. "
            f"Schema version: {current_version}"
        )

    async def _register_schema(self) -> None:
        """
        Register quotes table schema with database service.
        
        This is required before any row operations can be performed.
        Defines the table structure after all migrations are applied.
        
        Raises:
            RuntimeError: If schema registration fails
        """
        schema = {
            "table": "quotes",
            "schema": {
                "fields": [
                    {"name": "text", "type": "string", "required": True, "max_length": 1000},
                    {"name": "author", "type": "string", "max_length": 100},
                    {"name": "added_by", "type": "string", "max_length": 50},
                    {"name": "added_at", "type": "datetime", "required": True},
                    {"name": "score", "type": "integer", "required": True, "default": 0},
                    {"name": "tags", "type": "string", "required": True, "default": "[]"}
                ]
            }
        }
        
        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.schema.register",
                json.dumps(schema).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            
            if not result.get("success"):
                raise RuntimeError(f"Schema registration failed: {result.get('error')}")
                
            self.logger.info("Schema registered successfully")
            
        except asyncio.TimeoutError:
            raise RuntimeError("Schema registration timeout - database service not responding")
        except Exception as e:
            raise RuntimeError(f"Schema registration failed: {e}")

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
                "added_at": int(time.time()),
                "score": 0,
                "tags": "[]"
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
            raise asyncio.TimeoutError("NATS request timed out: add_quote")
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
            raise asyncio.TimeoutError("NATS request timed out: get_quote")
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
            raise asyncio.TimeoutError("NATS request timed out: delete_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def add_quote_safe(
        self,
        text: str,
        author: str,
        added_by: str,
        max_retries: int = None
    ) -> Optional[int]:
        """
        Add quote with retry logic for transient failures.

        This method wraps add_quote() with exponential backoff retry logic
        for handling transient NATS timeouts. Validation errors are not retried.

        Args:
            text: Quote text (1-1000 characters)
            author: Quote author (max 100 characters)
            added_by: Username adding the quote
            max_retries: Maximum retry attempts (default: DEFAULT_MAX_RETRIES)

        Returns:
            Quote ID if successful, None if max retries exceeded

        Raises:
            ValueError: If validation fails (no retry)
            Exception: For unexpected errors (no retry)

        Example:
            >>> quote_id = await plugin.add_quote_safe(
            ...     "Test quote", "Author", "user", max_retries=3
            ... )
            >>> if quote_id:
            ...     print(f"Added quote {quote_id}")
            ... else:
            ...     print("Max retries exceeded")
        """
        if max_retries is None:
            max_retries = self.DEFAULT_MAX_RETRIES

        for attempt in range(max_retries):
            try:
                quote_id = await self.add_quote(text, author, added_by)
                if attempt > 0:
                    self.logger.info(f"Retry succeeded on attempt {attempt + 1}")
                return quote_id

            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    self.logger.warning(
                        f"NATS timeout, retry {attempt + 1}/{max_retries} "
                        f"in {wait_time}s: '{text[:50]}...'"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        f"Max retries ({max_retries}) exceeded for add_quote: "
                        f"'{text[:50]}...'"
                    )
                    return None

            except ValueError:
                # Don't retry validation errors
                self.logger.error(f"Validation error (no retry): {text[:50]}")
                raise

            except Exception as e:
                # Unexpected error, don't retry
                self.logger.exception(f"Unexpected error adding quote: {e}")
                raise

        return None

    async def search_quotes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search quotes by author or text.

        Args:
            query: Search query string
            limit: Maximum results to return (1-100, default 10)

        Returns:
            List of matching quote dicts, sorted by timestamp descending

        Raises:
            ValueError: If limit out of range
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
        """
        self._ensure_initialized()

        # Validate limit
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        # Build search payload with $or and $like
        payload = {
            "table": "quotes",
            "filters": {
                "$or": [
                    {"author": {"$like": f"%{query}%"}},
                    {"text": {"$like": f"%{query}%"}}
                ]
            },
            "sort": {"field": "timestamp", "order": "desc"},
            "limit": limit
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.search",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            quotes = result.get("rows", [])

            self.logger.info(f"Search '{query}' returned {len(quotes)} results")
            return quotes

        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout searching for '{query}'")
            raise asyncio.TimeoutError("NATS request timed out: search_quotes")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def upvote_quote(self, quote_id: int) -> int:
        """
        Atomically increment quote score by 1.

        Args:
            quote_id: The ID of the quote to upvote

        Returns:
            The updated score after upvoting

        Raises:
            ValueError: If quote not found
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
        """
        self._ensure_initialized()

        # Atomic increment via $inc
        payload = {
            "table": "quotes",
            "filters": {"id": {"$eq": quote_id}},
            "operations": {"score": {"$inc": 1}}
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.update",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())

            if result.get("updated", 0) == 0:
                raise ValueError(f"Quote {quote_id} not found")

            # Retrieve updated score
            quote = await self.get_quote(quote_id)
            score = quote["score"]

            self.logger.info(f"Upvoted quote {quote_id}, new score: {score}")
            return score

        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout upvoting quote {quote_id}")
            raise asyncio.TimeoutError("NATS request timed out: upvote_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def downvote_quote(self, quote_id: int) -> int:
        """
        Atomically decrement quote score by 1.

        Args:
            quote_id: The ID of the quote to downvote

        Returns:
            The updated score after downvoting

        Raises:
            ValueError: If quote not found
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
        """
        self._ensure_initialized()

        payload = {
            "table": "quotes",
            "filters": {"id": {"$eq": quote_id}},
            "operations": {"score": {"$inc": -1}}
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.update",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())

            if result.get("updated", 0) == 0:
                raise ValueError(f"Quote {quote_id} not found")

            quote = await self.get_quote(quote_id)
            score = quote["score"]

            self.logger.info(f"Downvoted quote {quote_id}, new score: {score}")
            return score

        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout downvoting quote {quote_id}")
            raise asyncio.TimeoutError("NATS request timed out: downvote_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def top_quotes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get highest-scored quotes.

        Args:
            limit: Maximum results to return (1-100, default 10)

        Returns:
            List of top-scored quotes (score >= 1), sorted by score descending

        Raises:
            ValueError: If limit out of range
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
        """
        self._ensure_initialized()

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        payload = {
            "table": "quotes",
            "filters": {"score": {"$gte": 1}},
            "sort": {"field": "score", "order": "desc"},
            "limit": limit
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.search",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            quotes = result.get("rows", [])

            self.logger.info(f"Retrieved {len(quotes)} top quotes")
            return quotes

        except asyncio.TimeoutError:
            self.logger.error("NATS timeout getting top quotes")
            raise asyncio.TimeoutError("NATS request timed out: top_quotes")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def random_quote(self) -> Optional[Dict[str, Any]]:
        """
        Get a random quote.

        Uses KV-cached total count for efficient random selection.
        Falls back to first quote if random ID has gap.

        Returns:
            Random quote dict, or None if database empty

        Raises:
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out
        """
        self._ensure_initialized()

        # Get total count (KV cached)
        count = await self._get_quote_count()
        if count == 0:
            self.logger.info("No quotes available for random selection")
            return None

        # Generate random ID
        random_id = random.randint(1, count)

        # Try to get quote
        quote = await self.get_quote(random_id)
        if quote:
            return quote

        # Fallback: get first quote (handles ID gaps)
        self.logger.warning(f"Quote {random_id} not found, using fallback")
        payload = {
            "table": "quotes",
            "filters": {},
            "limit": 1
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.search",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            rows = result.get("rows", [])
            return rows[0] if rows else None

        except asyncio.TimeoutError:
            self.logger.error("NATS timeout getting random quote fallback")
            raise asyncio.TimeoutError("NATS request timed out: random_quote")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    # ===== Placeholder Methods =====

    async def find_by_author(self, author: str) -> List[Dict[str, Any]]:
        """
        Find all quotes by a specific author.

        This is a convenience wrapper around search_quotes() that performs
        an author name search.

        Args:
            author: Author name to search for

        Returns:
            List of quote dicts matching the author

        Raises:
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out

        Example:
            >>> quotes = await plugin.find_by_author("Einstein")
            >>> print(f"Found {len(quotes)} quotes by Einstein")
        """
        self._ensure_initialized()

        # Use search_quotes() which handles author searches
        return await self.search_quotes(author, limit=100)

    async def increment_score(self, quote_id: int, amount: int = 1) -> int:
        """
        Atomically increment a quote's score by any amount.

        This is a general-purpose score manipulation method. For simple
        upvote/downvote operations, consider using upvote_quote() or 
        downvote_quote() instead.

        Args:
            quote_id: Quote ID to modify
            amount: Amount to increment (can be negative for decrement)

        Returns:
            The updated score after increment

        Raises:
            ValueError: If quote not found
            RuntimeError: If plugin not initialized
            asyncio.TimeoutError: If NATS request times out

        Example:
            >>> new_score = await plugin.increment_score(42, 5)
            >>> print(f"Score increased by 5, now: {new_score}")
        """
        self._ensure_initialized()

        # Atomic increment via $inc
        payload = {
            "table": "quotes",
            "filters": {"id": {"$eq": quote_id}},
            "operations": {"score": {"$inc": amount}}
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.update",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())

            if result.get("updated", 0) == 0:
                raise ValueError(f"Quote {quote_id} not found")

            # Retrieve updated score
            quote = await self.get_quote(quote_id)
            score = quote["score"]

            self.logger.info(
                f"Incremented quote {quote_id} by {amount}, new score: {score}"
            )
            return score

        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout incrementing score for quote {quote_id}")
            raise asyncio.TimeoutError("NATS request timed out: increment_score")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    # ===== KV Caching Methods =====
    # Implemented in Sortie 3

    async def _get_quote_count(self) -> int:
        """
        Get total quote count (KV cached).

        Returns:
            Total number of quotes

        Raises:
            asyncio.TimeoutError: If database query times out
        """
        try:
            response = await self.nats.request(
                f"rosey.db.kv.{self.NAMESPACE}.get",
                json.dumps({"key": "total_count"}).encode(),
                timeout=1.0
            )
            result = json.loads(response.data.decode())

            if result.get("exists", False):
                count = int(result["value"])
                self.logger.debug(f"KV cache hit: total_count={count}")
                return count

        except Exception as e:
            self.logger.warning(f"KV cache miss: {e}")

        # Cache miss: count from database
        self.logger.debug("Counting quotes from database")
        return await self._count_quotes_from_db()

    async def _count_quotes_from_db(self) -> int:
        """
        Count quotes from database (expensive operation).

        Returns:
            Total number of quotes

        Raises:
            asyncio.TimeoutError: If database query times out
        """
        payload = {
            "table": "quotes",
            "filters": {},
            "limit": 10000  # Maximum limit
        }

        try:
            response = await self.nats.request(
                f"rosey.db.row.{self.NAMESPACE}.search",
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            count = len(result.get("rows", []))

            # Update cache
            await self._update_quote_count_cache(count)

            self.logger.info(f"Counted {count} quotes from database")
            return count

        except asyncio.TimeoutError:
            self.logger.error("NATS timeout counting quotes")
            raise asyncio.TimeoutError("NATS request timed out: _count_quotes_from_db")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise Exception("Invalid JSON response from NATS")

    async def _update_quote_count_cache(self, count: int):
        """
        Update KV cache with quote count.

        Args:
            count: Total quote count to cache
        """
        payload = {
            "key": "total_count",
            "value": str(count),
            "ttl": 300  # 5 minutes
        }

        try:
            await self.nats.request(
                f"rosey.db.kv.{self.NAMESPACE}.set",
                json.dumps(payload).encode(),
                timeout=1.0
            )
            self.logger.debug(f"Updated KV cache: total_count={count}")
        except Exception as e:
            self.logger.warning(f"Failed to update KV cache: {e}")
