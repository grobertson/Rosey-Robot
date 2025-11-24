---
title: Sprint 16 Sortie 3 - Quote-DB Advanced Features
version: 1.0
date_created: 2025-11-24
last_updated: 2025-11-24
owner: Rosey-Robot Team
tags: [sprint-16, reference-implementation, quote-db, advanced-operators, kv-storage, search, voting]
---

# Sprint 16 Sortie 3: Advanced Features (Search, Scoring, KV)

**Sprint**: 16 - Reference Implementation - Quote-DB Plugin  
**Sortie**: 3 of 4  
**Duration**: 1 day (6-8 hours)  
**Status**: Ready for Implementation  

---

## 1. Overview

This sortie implements advanced features demonstrating the full power of the storage API stack:

- **Advanced Operators (Sprint 14)**: $like for search, $or for multi-field queries, $gte for filtering
- **Atomic Updates (Sprint 14)**: $inc for safe concurrent score updates
- **KV Storage (Sprint 12)**: Counter caching to reduce database load

Building on CRUD operations from Sortie 2, we now add:

- **Search Functionality**: Find quotes by author or text using $like and $or operators
- **Voting System**: Upvote/downvote quotes with atomic $inc operations (no race conditions)
- **Top Quotes**: Retrieve highest-scored quotes with sorting and filtering
- **Random Quotes**: Get random quote using KV-cached total count
- **KV Caching**: Total quote count cached with TTL to reduce expensive COUNT queries

This sortie demonstrates:
- How to combine multiple advanced operators in single query
- Atomic updates preventing race conditions in voting
- KV storage reducing load on primary database
- Performance optimization through strategic caching

**Key Outcomes**:
- Working search proving $like and $or operators
- Safe voting system proving atomic $inc updates
- KV caching proving cache-aside pattern
- Foundation for production deployment in Sortie 4

---

## 2. Scope and Non-Goals

### In Scope

- **Search Operation**:
  - Accept query string and optional limit
  - Search both author and text fields using $like
  - Combine with $or operator for multi-field search
  - Sort by timestamp descending
  - Return list of matching quotes

- **Voting Operations**:
  - upvote_quote(): Atomically increment score by 1 using $inc
  - downvote_quote(): Atomically decrement score by 1 using $inc
  - Raise ValueError if quote not found
  - Return updated score after operation

- **Top Quotes Operation**:
  - Retrieve quotes with score >= 1
  - Sort by score descending
  - Accept optional limit (default 10)
  - Return list of top quotes

- **Random Quote Operation**:
  - Get total count from KV cache
  - Generate random ID in range [1, count]
  - Retrieve quote by ID
  - Fallback to first quote if ID not found (gap handling)

- **KV Counter Caching**:
  - _get_quote_count(): Get total from KV or database
  - _count_quotes_from_db(): Count via Row API (cache miss)
  - _update_quote_count_cache(): Set KV with 5-minute TTL
  - Cache invalidation on add/delete

- **Unit Tests**:
  - Test search with results
  - Test search with no results
  - Test upvote increments score
  - Test downvote decrements score
  - Test upvote on non-existent quote
  - Test top quotes ordering
  - Test top quotes with no high-scored quotes
  - Test random quote
  - Test KV cache hit
  - Test KV cache miss
  - 10+ new tests, 85%+ coverage

### Out of Scope (Sortie 4 or Future)

- **Pagination**: Offset-based pagination for large result sets
- **Full-Text Search**: Advanced text search with ranking
- **Tag Filtering**: Search by tags (tags column exists but unused)
- **Author Statistics**: Most prolific authors via aggregation
- **Comprehensive Error Handling**: Plugin-wide error strategy
- **Integration Tests**: End-to-end NATS testing
- **Performance Benchmarks**: Load testing voting system

---

## 3. Requirements

### Functional Requirements

- **FR-1**: Search Quotes
  - Method: `async def search_quotes(self, query: str, limit: int = 10) -> List[Dict]`
  - Search author field with $like: `{"author": {"$like": f"%{query}%"}}`
  - Search text field with $like: `{"text": {"$like": f"%{query}%"}}`
  - Combine with $or: `{"$or": [author_filter, text_filter]}`
  - Sort by timestamp descending: `"sort": {"field": "timestamp", "order": "desc"}`
  - Apply limit (default 10, max 100)
  - Return list of quote dicts

- **FR-2**: Upvote Quote
  - Method: `async def upvote_quote(self, quote_id: int) -> int`
  - Use atomic $inc: `{"operations": {"score": {"$inc": 1}}}`
  - Filter by ID: `{"filters": {"id": {"$eq": quote_id}}}`
  - Raise ValueError if quote not found (updated count == 0)
  - Retrieve and return updated score
  - Invalidate KV cache (future enhancement)

- **FR-3**: Downvote Quote
  - Method: `async def downvote_quote(self, quote_id: int) -> int`
  - Use atomic $inc: `{"operations": {"score": {"$inc": -1}}}`
  - Filter by ID: `{"filters": {"id": {"$eq": quote_id}}}`
  - Raise ValueError if quote not found
  - Retrieve and return updated score
  - Invalidate KV cache (future enhancement)

- **FR-4**: Top Quotes
  - Method: `async def top_quotes(self, limit: int = 10) -> List[Dict]`
  - Filter score >= 1: `{"filters": {"score": {"$gte": 1}}}`
  - Sort by score descending: `"sort": {"field": "score", "order": "desc"}`
  - Apply limit (default 10, max 100)
  - Return list of quote dicts

- **FR-5**: Random Quote
  - Method: `async def random_quote(self) -> Optional[Dict]`
  - Get total count via _get_quote_count()
  - Return None if count == 0
  - Generate random ID in [1, count]
  - Retrieve quote via get_quote(random_id)
  - If None (ID gap), fallback to first quote via search with limit=1

- **FR-6**: Get Quote Count (KV Cache)
  - Method: `async def _get_quote_count(self) -> int`
  - Try KV get: `rosey.db.kv.{namespace}.get` with key "total_count"
  - If exists, return int(value)
  - If not exists or error, call _count_quotes_from_db()
  - Log cache hits/misses

- **FR-7**: Count Quotes from DB
  - Method: `async def _count_quotes_from_db(self) -> int`
  - Select all quotes with limit=10000 (expensive)
  - Count result rows: `len(result.get("rows", []))`
  - Update KV cache via _update_quote_count_cache()
  - Return count

- **FR-8**: Update Quote Count Cache
  - Method: `async def _update_quote_count_cache(self, count: int)`
  - Set KV: `rosey.db.kv.{namespace}.set` with key "total_count"
  - Value: str(count)
  - TTL: 300 seconds (5 minutes)
  - Log cache updates

- **FR-9**: Unit Tests
  - Test search_quotes: Multiple results
  - Test search_quotes: No results
  - Test upvote_quote: Score increments
  - Test upvote_quote: Raises ValueError on not found
  - Test downvote_quote: Score decrements
  - Test top_quotes: Returns sorted by score
  - Test top_quotes: Empty list if no high scores
  - Test random_quote: Returns quote
  - Test random_quote: Returns None if empty database
  - Test _get_quote_count: Cache hit
  - Test _get_quote_count: Cache miss
  - Minimum 11 tests, target 85%+ coverage

### Non-Functional Requirements

- **NFR-1**: Code Quality
  - All methods have comprehensive docstrings
  - Type hints on all parameters and return values
  - Follow PEP 8 style guidelines
  - Pass flake8 and pyright linting

- **NFR-2**: Performance
  - Search queries complete in < 100ms for 1000 quotes
  - Voting operations are atomic (no race conditions)
  - KV cache reduces database load by 90%+
  - Random quote generation O(1) with cache hit

- **NFR-3**: Testability
  - All operations mockable with NATS fixtures
  - Tests verify operator usage (inspect payloads)
  - Tests cover cache hit and cache miss scenarios

- **NFR-4**: Maintainability
  - Clear separation: search, voting, caching logic
  - KV cache abstracted for future enhancements
  - Consistent error handling patterns

---

## 4. Technical Design

### 4.1 Search Implementation

**File**: `plugins/quote-db/quote_db.py`

```python
async def search_quotes(self, query: str, limit: int = 10) -> List[Dict]:
    """Search quotes by author or text."""
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
            f"rosey.db.row.{self.namespace}.search",
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
```

### 4.2 Voting Implementation

```python
async def upvote_quote(self, quote_id: int) -> int:
    """Atomically increment quote score by 1."""
    self._ensure_initialized()
    
    # Atomic increment via $inc
    payload = {
        "table": "quotes",
        "filters": {"id": {"$eq": quote_id}},
        "operations": {"score": {"$inc": 1}}
    }
    
    try:
        response = await self.nats.request(
            f"rosey.db.row.{self.namespace}.update",
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


async def downvote_quote(self, quote_id: int) -> int:
    """Atomically decrement quote score by 1."""
    self._ensure_initialized()
    
    payload = {
        "table": "quotes",
        "filters": {"id": {"$eq": quote_id}},
        "operations": {"score": {"$inc": -1}}
    }
    
    try:
        response = await self.nats.request(
            f"rosey.db.row.{self.namespace}.update",
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
```

### 4.3 Top Quotes Implementation

```python
async def top_quotes(self, limit: int = 10) -> List[Dict]:
    """Get highest-scored quotes."""
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
            f"rosey.db.row.{self.namespace}.search",
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
```

### 4.4 Random Quote Implementation

```python
async def random_quote(self) -> Optional[Dict]:
    """Get a random quote."""
    self._ensure_initialized()
    
    # Get total count (KV cached)
    count = await self._get_quote_count()
    if count == 0:
        self.logger.info("No quotes available for random selection")
        return None
    
    # Generate random ID
    import random
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
            f"rosey.db.row.{self.namespace}.search",
            json.dumps(payload).encode(),
            timeout=2.0
        )
        result = json.loads(response.data.decode())
        rows = result.get("rows", [])
        return rows[0] if rows else None
        
    except asyncio.TimeoutError:
        self.logger.error("NATS timeout getting random quote")
        raise asyncio.TimeoutError("NATS request timed out: random_quote")
```

### 4.5 KV Caching Implementation

```python
async def _get_quote_count(self) -> int:
    """Get total quote count (KV cached)."""
    try:
        response = await self.nats.request(
            f"rosey.db.kv.{self.namespace}.get",
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
    """Count quotes from database (expensive operation)."""
    payload = {
        "table": "quotes",
        "filters": {},
        "limit": 10000  # Maximum limit
    }
    
    try:
        response = await self.nats.request(
            f"rosey.db.row.{self.namespace}.search",
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


async def _update_quote_count_cache(self, count: int):
    """Update KV cache with quote count."""
    payload = {
        "key": "total_count",
        "value": str(count),
        "ttl": 300  # 5 minutes
    }
    
    try:
        await self.nats.request(
            f"rosey.db.kv.{self.namespace}.set",
            json.dumps(payload).encode(),
            timeout=1.0
        )
        self.logger.debug(f"Updated KV cache: total_count={count}")
        
    except Exception as e:
        self.logger.warning(f"Failed to update KV cache: {e}")
```

---

## 5. Implementation Steps

1. **Import random module** (`quote_db.py` top)
2. **Implement search_quotes()** with $or and $like operators
3. **Implement upvote_quote()** with $inc operator
4. **Implement downvote_quote()** with $inc operator
5. **Implement top_quotes()** with $gte filter and score sort
6. **Implement random_quote()** with fallback logic
7. **Implement _get_quote_count()** with KV cache
8. **Implement _count_quotes_from_db()** with cache update
9. **Implement _update_quote_count_cache()** with TTL
10. **Write 11+ unit tests** in test_quote_db.py
11. **Run tests**: `pytest tests/ -v --cov=quote_db`
12. **Run linter**: `flake8 quote_db.py; pyright quote_db.py`
13. **Manual testing** with real NATS
14. **Update README** with new features
15. **Commit changes**

---

## 6. Testing Strategy

### 6.1 Test Coverage

- 11+ new tests
- Target 85%+ overall coverage
- 100% coverage for new methods

### 6.2 Key Tests

**Search Tests**: test_search_quotes_success, test_search_quotes_no_results  
**Voting Tests**: test_upvote_increments, test_downvote_decrements, test_vote_not_found  
**Top Quotes**: test_top_quotes_sorted, test_top_quotes_empty  
**Random Quote**: test_random_quote_success, test_random_quote_empty  
**KV Cache**: test_get_count_cache_hit, test_get_count_cache_miss

---

## 7-11. Remaining Sections

**AC**: Search works, voting atomic, caching reduces load, 11+ tests pass, 85%+ coverage  
**Rollout**: Implement features, test, commit "Sprint 16 Sortie 3: Advanced Features"  
**Dependencies**: Sprints 12, 13, 14, NATS server  
**Risks**: Operator syntax, atomic race conditions, cache invalidation  
**Docs**: Update README with search, voting, top quotes examples  
**Related**: Sortie 2 (previous), Sortie 4 (next), Sprints 12/14 specs

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation  
**Sortie 3 of 4**: Advanced features using full storage API stack
