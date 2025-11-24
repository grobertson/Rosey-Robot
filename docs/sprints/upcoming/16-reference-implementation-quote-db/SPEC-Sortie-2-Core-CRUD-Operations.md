---
title: Sprint 16 Sortie 2 - Quote-DB Core CRUD Operations
version: 1.0
date_created: 2025-11-24
last_updated: 2025-11-24
owner: Rosey-Robot Team
tags: [sprint-16, reference-implementation, quote-db, crud, row-operations, testing]
---

# Sprint 16 Sortie 2: Core CRUD Operations

**Sprint**: 16 - Reference Implementation - Quote-DB Plugin  
**Sortie**: 2 of 4  
**Duration**: 1.5 days (6-8 hours)  
**Status**: Ready for Implementation  

---

## 1. Overview

This sortie implements the core Create, Read, and Delete (CRUD) operations for the Quote-DB plugin using the Row Operations API from Sprint 13. Building on the foundation from Sortie 1, we now implement the actual business logic for managing quotes:

- **Add Quote**: Insert new quotes with validation
- **Get Quote**: Retrieve quotes by ID
- **Delete Quote**: Remove quotes by ID
- **Input Validation**: Ensure data integrity (text length, author format)
- **Error Handling**: Handle NATS timeouts, JSON parsing errors, invalid input

This sortie demonstrates proper usage of the Row Operations API:
- `rosey.db.row.{namespace}.insert` for adding quotes
- `rosey.db.row.{namespace}.select` for retrieving quotes
- `rosey.db.row.{namespace}.delete` for removing quotes

All operations are fully tested with comprehensive unit tests using NATS mocks from Sortie 1.

**Key Outcomes**:
- Working CRUD implementation proving Row API integration
- Input validation ensuring data integrity
- Comprehensive unit tests (8+ tests, 80%+ coverage)
- Foundation for advanced features in Sortie 3

---

## 2. Scope and Non-Goals

### In Scope

- **Add Quote Operation**:
  - Accept text, author, added_by parameters
  - Validate text (non-empty, max 1000 chars)
  - Validate author (max 100 chars, default "Unknown")
  - Insert via Row API with timestamp and initial score
  - Return new quote ID

- **Get Quote Operation**:
  - Retrieve single quote by ID
  - Return quote dict or None if not found
  - Use Row API select with $eq filter

- **Delete Quote Operation**:
  - Delete single quote by ID
  - Return True if deleted, False if not found
  - Use Row API delete with $eq filter

- **Input Validation**:
  - Text validation (empty, length, whitespace trimming)
  - Author validation (length, default value, whitespace trimming)
  - Raise ValueError with clear messages

- **Error Handling**:
  - NATS timeout handling (asyncio.TimeoutError)
  - JSON parsing error handling
  - Clear error messages for users

- **Unit Tests**:
  - Test add_quote success case
  - Test get_quote success and not-found cases
  - Test delete_quote success case
  - Test validation failures (empty text, long text, long author)
  - Test NATS timeout scenario
  - Test JSON parsing error
  - 8+ tests, 80%+ coverage

### Out of Scope (Future Sorties)

- **Advanced Search**: find_by_author() with $like operator (Sortie 3)
- **Random Quote**: get_random_quote() (Sortie 3)
- **Voting System**: increment_score() with $inc operator (Sortie 3)
- **KV Counters**: total_quotes, popular_authors KV (Sortie 3)
- **Comprehensive Error Handling**: Plugin-wide error strategy (Sortie 4)
- **Integration Tests**: End-to-end NATS testing (Sortie 4)
- **Performance Optimization**: Batch operations, caching (Future)

---

## 3. Requirements

### Functional Requirements

- **FR-1**: Add Quote Operation
  - Method: `async def add_quote(self, text: str, author: str, added_by: str) -> int`
  - Validate text: non-empty, trimmed, max 1000 chars
  - Validate author: trimmed, max 100 chars, default "Unknown" if empty
  - Insert via `rosey.db.row.quote-db.insert` with:
    - text, author, added_by
    - timestamp: current Unix timestamp
    - score: initial value of 0
  - Return inserted quote ID (int)
  - Raise ValueError for validation failures

- **FR-2**: Get Quote Operation
  - Method: `async def get_quote(self, quote_id: int) -> Optional[Dict]`
  - Retrieve quote by ID via `rosey.db.row.quote-db.select`
  - Use filter: `{"id": {"$eq": quote_id}}` with limit 1
  - Return quote dict if found (id, text, author, added_by, timestamp, score)
  - Return None if not found (empty rows array)

- **FR-3**: Delete Quote Operation
  - Method: `async def delete_quote(self, quote_id: int) -> bool`
  - Delete quote by ID via `rosey.db.row.quote-db.delete`
  - Use filter: `{"id": {"$eq": quote_id}}`
  - Return True if deleted (deleted count > 0)
  - Return False if not found (deleted count == 0)

- **FR-4**: Text Validation
  - Method: `def _validate_text(self, text: str) -> str`
  - Check for empty/whitespace-only text → ValueError("Quote text cannot be empty")
  - Trim leading/trailing whitespace
  - Check length > 1000 chars → ValueError("Quote text too long (max 1000 chars)")
  - Return validated text

- **FR-5**: Author Validation
  - Method: `def _validate_author(self, author: Optional[str]) -> str`
  - If None or empty/whitespace-only → return "Unknown"
  - Trim leading/trailing whitespace
  - Check length > 100 chars → ValueError("Author name too long (max 100 chars)")
  - Return validated author

- **FR-6**: NATS Error Handling
  - Catch asyncio.TimeoutError on NATS requests
  - Re-raise with context: "NATS request timed out: {operation}"
  - Log errors with self.logger

- **FR-7**: JSON Error Handling
  - Catch json.JSONDecodeError on response parsing
  - Re-raise with context: "Invalid JSON response from NATS"

- **FR-8**: Unit Tests
  - Test add_quote: Success case with mocked NATS response
  - Test get_quote: Success case returning quote dict
  - Test get_quote: Not found case returning None
  - Test delete_quote: Success case returning True
  - Test delete_quote: Not found case returning False
  - Test _validate_text: Empty text raises ValueError
  - Test _validate_text: Long text raises ValueError
  - Test _validate_author: Empty author defaults to "Unknown"
  - Test _validate_author: Long author raises ValueError
  - Test NATS timeout: Handled gracefully
  - Minimum 8 tests, target 80%+ coverage

### Non-Functional Requirements

- **NFR-1**: Code Quality
  - All methods have comprehensive docstrings (Args, Returns, Raises)
  - Type hints on all parameters and return values
  - Follow PEP 8 style guidelines
  - Pass flake8 and pyright linting

- **NFR-2**: Testability
  - All CRUD methods are mockable
  - Tests use NATS mock fixtures from Sortie 1
  - Tests verify NATS request payloads
  - Tests cover both success and failure paths

- **NFR-3**: Performance
  - NATS timeout: 2.0 seconds for all operations
  - Validation methods are synchronous (no unnecessary async)
  - Minimal memory allocation

- **NFR-4**: Maintainability
  - Clear separation: CRUD methods, validation helpers, error handling
  - Reusable validation methods for future operations
  - Consistent error message format
  - Logging at INFO (success) and ERROR (failures) levels

---

## 4. Technical Design

### 4.1 CRUD Operations Implementation

**File**: `plugins/quote-db/quote_db.py`

```python
async def add_quote(self, text: str, author: str, added_by: str) -> int:
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
            f"rosey.db.row.{self.namespace}.insert",
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


async def get_quote(self, quote_id: int) -> Optional[Dict]:
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
            f"rosey.db.row.{self.namespace}.select",
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
            f"rosey.db.row.{self.namespace}.delete",
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
```

### 4.2 Validation Helpers

**File**: `plugins/quote-db/quote_db.py` (add to QuoteDBPlugin class)

```python
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
```

### 4.3 Unit Tests

**File**: `plugins/quote-db/tests/test_quote_db.py` (add to existing file)

```python
import pytest
import json
from unittest.mock import MagicMock
import asyncio


# ============================================================================
# Add Quote Tests
# ============================================================================

@pytest.mark.asyncio
async def test_add_quote_success(initialized_plugin, mock_nats):
    """Test adding a quote successfully."""
    # Mock NATS response
    mock_response = MagicMock()
    mock_response.data = json.dumps({"id": 42}).encode()
    mock_nats.request.return_value = mock_response
    
    # Add quote
    quote_id = await initialized_plugin.add_quote("Test quote", "Alice", "bob")
    
    # Verify result
    assert quote_id == 42
    
    # Verify NATS request
    mock_nats.request.assert_called_once()
    call_args = mock_nats.request.call_args
    assert call_args[0][0] == "rosey.db.row.quote-db.insert"
    
    payload = json.loads(call_args[0][1].decode())
    assert payload["table"] == "quotes"
    assert payload["data"]["text"] == "Test quote"
    assert payload["data"]["author"] == "Alice"
    assert payload["data"]["added_by"] == "bob"
    assert payload["data"]["score"] == 0
    assert "timestamp" in payload["data"]


@pytest.mark.asyncio
async def test_add_quote_author_defaults_to_unknown(initialized_plugin, mock_nats):
    """Test that empty author defaults to 'Unknown'."""
    mock_response = MagicMock()
    mock_response.data = json.dumps({"id": 43}).encode()
    mock_nats.request.return_value = mock_response
    
    quote_id = await initialized_plugin.add_quote("Test", "", "bob")
    assert quote_id == 43
    
    payload = json.loads(mock_nats.request.call_args[0][1].decode())
    assert payload["data"]["author"] == "Unknown"


@pytest.mark.asyncio
async def test_add_quote_timeout(initialized_plugin, mock_nats):
    """Test handling of NATS timeout."""
    mock_nats.request.side_effect = asyncio.TimeoutError()
    
    with pytest.raises(asyncio.TimeoutError, match="add_quote"):
        await initialized_plugin.add_quote("Test", "Alice", "bob")


# ============================================================================
# Get Quote Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_quote_success(initialized_plugin, mock_nats):
    """Test getting a quote by ID."""
    mock_response = MagicMock()
    mock_response.data = json.dumps({
        "rows": [{
            "id": 42,
            "text": "Test quote",
            "author": "Alice",
            "added_by": "bob",
            "timestamp": 1234567890,
            "score": 5
        }]
    }).encode()
    mock_nats.request.return_value = mock_response
    
    quote = await initialized_plugin.get_quote(42)
    
    assert quote is not None
    assert quote["id"] == 42
    assert quote["text"] == "Test quote"
    assert quote["author"] == "Alice"
    assert quote["score"] == 5


@pytest.mark.asyncio
async def test_get_quote_not_found(initialized_plugin, mock_nats):
    """Test getting a non-existent quote."""
    mock_response = MagicMock()
    mock_response.data = json.dumps({"rows": []}).encode()
    mock_nats.request.return_value = mock_response
    
    quote = await initialized_plugin.get_quote(999)
    assert quote is None


@pytest.mark.asyncio
async def test_get_quote_timeout(initialized_plugin, mock_nats):
    """Test handling of NATS timeout."""
    mock_nats.request.side_effect = asyncio.TimeoutError()
    
    with pytest.raises(asyncio.TimeoutError, match="get_quote"):
        await initialized_plugin.get_quote(42)


# ============================================================================
# Delete Quote Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delete_quote_success(initialized_plugin, mock_nats):
    """Test deleting a quote."""
    mock_response = MagicMock()
    mock_response.data = json.dumps({"deleted": 1}).encode()
    mock_nats.request.return_value = mock_response
    
    deleted = await initialized_plugin.delete_quote(42)
    assert deleted is True
    
    # Verify NATS request
    call_args = mock_nats.request.call_args
    assert call_args[0][0] == "rosey.db.row.quote-db.delete"
    payload = json.loads(call_args[0][1].decode())
    assert payload["filters"]["id"]["$eq"] == 42


@pytest.mark.asyncio
async def test_delete_quote_not_found(initialized_plugin, mock_nats):
    """Test deleting a non-existent quote."""
    mock_response = MagicMock()
    mock_response.data = json.dumps({"deleted": 0}).encode()
    mock_nats.request.return_value = mock_response
    
    deleted = await initialized_plugin.delete_quote(999)
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_quote_timeout(initialized_plugin, mock_nats):
    """Test handling of NATS timeout."""
    mock_nats.request.side_effect = asyncio.TimeoutError()
    
    with pytest.raises(asyncio.TimeoutError, match="delete_quote"):
        await initialized_plugin.delete_quote(42)


# ============================================================================
# Validation Tests
# ============================================================================

def test_validate_text_empty(plugin):
    """Test validation of empty text."""
    with pytest.raises(ValueError, match="cannot be empty"):
        plugin._validate_text("")


def test_validate_text_whitespace_only(plugin):
    """Test validation of whitespace-only text."""
    with pytest.raises(ValueError, match="cannot be empty"):
        plugin._validate_text("   ")


def test_validate_text_too_long(plugin):
    """Test validation of text exceeding max length."""
    with pytest.raises(ValueError, match="too long"):
        plugin._validate_text("x" * 1001)


def test_validate_text_success(plugin):
    """Test validation of valid text."""
    result = plugin._validate_text("  Valid quote  ")
    assert result == "Valid quote"


def test_validate_author_empty(plugin):
    """Test validation of empty author."""
    result = plugin._validate_author("")
    assert result == "Unknown"


def test_validate_author_none(plugin):
    """Test validation of None author."""
    result = plugin._validate_author(None)
    assert result == "Unknown"


def test_validate_author_too_long(plugin):
    """Test validation of author exceeding max length."""
    with pytest.raises(ValueError, match="too long"):
        plugin._validate_author("x" * 101)


def test_validate_author_success(plugin):
    """Test validation of valid author."""
    result = plugin._validate_author("  Alice  ")
    assert result == "Alice"
```

---

## 5. Implementation Steps

1. **Update QuoteDBPlugin class** (`quote_db.py`)
   - Remove `NotImplementedError` from add_quote(), get_quote(), delete_quote()
   - Add import: `import time` for timestamps

2. **Implement add_quote() method**
   - Add method signature with type hints
   - Add comprehensive docstring
   - Call _ensure_initialized()
   - Validate text and author
   - Build data payload with timestamp and score=0
   - Send NATS request to rosey.db.row.quote-db.insert
   - Parse response JSON, extract ID
   - Add error handling for timeout and JSON parsing
   - Add logging (INFO on success, ERROR on failure)
   - Return quote ID

3. **Implement get_quote() method**
   - Add method signature with type hints
   - Add comprehensive docstring
   - Call _ensure_initialized()
   - Build query payload with $eq filter
   - Send NATS request to rosey.db.row.quote-db.select
   - Parse response JSON, extract rows
   - Return first row if found, None otherwise
   - Add error handling and logging

4. **Implement delete_quote() method**
   - Add method signature with type hints
   - Add comprehensive docstring
   - Call _ensure_initialized()
   - Build query payload with $eq filter
   - Send NATS request to rosey.db.row.quote-db.delete
   - Parse response JSON, check deleted count
   - Return True if deleted > 0, False otherwise
   - Add error handling and logging

5. **Implement _validate_text() helper**
   - Check for empty/whitespace-only text
   - Trim whitespace
   - Check length <= 1000
   - Raise ValueError with clear messages
   - Return validated text

6. **Implement _validate_author() helper**
   - Handle None and empty strings → "Unknown"
   - Trim whitespace
   - Check length <= 100
   - Raise ValueError with clear messages
   - Return validated author

7. **Write unit tests** (`test_quote_db.py`)
   - test_add_quote_success: Mock response, verify ID returned
   - test_add_quote_author_defaults_to_unknown: Test empty author
   - test_add_quote_timeout: Test NATS timeout handling
   - test_get_quote_success: Mock response, verify quote dict
   - test_get_quote_not_found: Mock empty rows
   - test_get_quote_timeout: Test NATS timeout handling
   - test_delete_quote_success: Mock deleted=1
   - test_delete_quote_not_found: Mock deleted=0
   - test_delete_quote_timeout: Test NATS timeout handling
   - test_validate_text_empty: Test empty text raises ValueError
   - test_validate_text_whitespace_only: Test whitespace-only
   - test_validate_text_too_long: Test 1001 char text
   - test_validate_text_success: Test valid text trimmed
   - test_validate_author_empty: Test empty author → "Unknown"
   - test_validate_author_none: Test None author → "Unknown"
   - test_validate_author_too_long: Test 101 char author
   - test_validate_author_success: Test valid author trimmed

8. **Run tests**
   ```bash
   cd plugins/quote-db
   pytest tests/ -v --cov=quote_db --cov-report=term-missing
   ```

9. **Run linter**
   ```bash
   flake8 quote_db.py tests/
   pyright quote_db.py
   ```

10. **Manual testing with NATS**
    - Start NATS server
    - Apply migrations (Sortie 1)
    - Test add_quote in Python REPL
    - Test get_quote retrieval
    - Test delete_quote removal
    - Verify error messages for invalid input

11. **Update README** (`README.md`)
    - Add usage examples for CRUD operations
    - Document error handling behavior
    - Add code examples

12. **Commit changes**
    ```text
    Sprint 16 Sortie 2: Quote-DB CRUD Operations
    
    - Implement add_quote() with validation
    - Implement get_quote() with error handling
    - Implement delete_quote() with status return
    - Add text and author validation helpers
    - Add comprehensive unit tests (17 tests)
    - Handle NATS timeouts and JSON errors
    - Document usage in README
    
    Implements: SPEC-Sortie-2-Core-CRUD-Operations.md
    Related: PRD-Reference-Implementation-Quote-DB.md
    ```

---

## 6. Testing Strategy

### 6.1 Unit Tests Overview

**File**: `plugins/quote-db/tests/test_quote_db.py`

**Coverage Target**: 80%+ overall, 100% for CRUD methods

**Test Organization**:
- Add Quote Tests (3 tests)
- Get Quote Tests (3 tests)
- Delete Quote Tests (3 tests)
- Validation Tests (8 tests)

**Total**: 17 tests

### 6.2 Test Fixtures

Use existing fixtures from Sortie 1:
- `mock_nats`: Mock NATS client
- `plugin`: QuoteDBPlugin instance (not initialized)
- `initialized_plugin`: QuoteDBPlugin instance (initialized)

### 6.3 Add Quote Tests

```python
@pytest.mark.asyncio
async def test_add_quote_success(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS returning ID 42
    When: add_quote("Test", "Alice", "bob") called
    Then: Returns 42, NATS request contains correct payload
    """
    # See section 4.3 for implementation

@pytest.mark.asyncio
async def test_add_quote_author_defaults_to_unknown(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, empty author string
    When: add_quote("Test", "", "bob") called
    Then: Author set to "Unknown" in NATS request
    """

@pytest.mark.asyncio
async def test_add_quote_timeout(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS raises TimeoutError
    When: add_quote() called
    Then: asyncio.TimeoutError raised with "add_quote" message
    """
```

### 6.4 Get Quote Tests

```python
@pytest.mark.asyncio
async def test_get_quote_success(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS returning quote data
    When: get_quote(42) called
    Then: Returns dict with id, text, author, score fields
    """

@pytest.mark.asyncio
async def test_get_quote_not_found(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS returning empty rows
    When: get_quote(999) called
    Then: Returns None
    """

@pytest.mark.asyncio
async def test_get_quote_timeout(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS raises TimeoutError
    When: get_quote() called
    Then: asyncio.TimeoutError raised with "get_quote" message
    """
```

### 6.5 Delete Quote Tests

```python
@pytest.mark.asyncio
async def test_delete_quote_success(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS returning deleted=1
    When: delete_quote(42) called
    Then: Returns True, NATS request contains correct filter
    """

@pytest.mark.asyncio
async def test_delete_quote_not_found(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS returning deleted=0
    When: delete_quote(999) called
    Then: Returns False
    """

@pytest.mark.asyncio
async def test_delete_quote_timeout(initialized_plugin, mock_nats):
    """
    Given: initialized plugin, mock NATS raises TimeoutError
    When: delete_quote() called
    Then: asyncio.TimeoutError raised with "delete_quote" message
    """
```

### 6.6 Validation Tests

```python
def test_validate_text_empty(plugin):
    """
    Given: Empty string
    When: _validate_text("") called
    Then: ValueError raised with "cannot be empty" message
    """

def test_validate_text_whitespace_only(plugin):
    """
    Given: Whitespace-only string
    When: _validate_text("   ") called
    Then: ValueError raised with "cannot be empty" message
    """

def test_validate_text_too_long(plugin):
    """
    Given: 1001 character string
    When: _validate_text() called
    Then: ValueError raised with "too long" message
    """

def test_validate_text_success(plugin):
    """
    Given: Valid text with leading/trailing whitespace
    When: _validate_text("  Test  ") called
    Then: Returns "Test" (trimmed)
    """

def test_validate_author_empty(plugin):
    """
    Given: Empty string
    When: _validate_author("") called
    Then: Returns "Unknown"
    """

def test_validate_author_none(plugin):
    """
    Given: None value
    When: _validate_author(None) called
    Then: Returns "Unknown"
    """

def test_validate_author_too_long(plugin):
    """
    Given: 101 character string
    When: _validate_author() called
    Then: ValueError raised with "too long" message
    """

def test_validate_author_success(plugin):
    """
    Given: Valid author with leading/trailing whitespace
    When: _validate_author("  Alice  ") called
    Then: Returns "Alice" (trimmed)
    """
```

### 6.7 Manual Testing Checklist

- [ ] Start NATS server
- [ ] Apply all migrations from Sortie 1
- [ ] Test add_quote in Python REPL:
  ```python
  from quote_db import QuoteDBPlugin
  import nats
  
  nc = await nats.connect("nats://localhost:4222")
  plugin = QuoteDBPlugin(nc)
  await plugin.initialize()
  
  # Test add
  id1 = await plugin.add_quote("Test quote", "Alice", "bob")
  print(f"Added quote {id1}")
  
  # Test get
  quote = await plugin.get_quote(id1)
  print(quote)
  
  # Test delete
  deleted = await plugin.delete_quote(id1)
  print(f"Deleted: {deleted}")
  ```

- [ ] Test validation errors:
  ```python
  # Empty text
  await plugin.add_quote("", "Alice", "bob")  # Should raise ValueError
  
  # Long text
  await plugin.add_quote("x" * 1001, "Alice", "bob")  # Should raise ValueError
  
  # Long author
  await plugin.add_quote("Test", "x" * 101, "bob")  # Should raise ValueError
  ```

- [ ] Test NATS timeout:
  ```python
  # Stop NATS server
  await plugin.add_quote("Test", "Alice", "bob")  # Should raise TimeoutError
  ```

- [ ] Verify database state:
  ```bash
  nats req "rosey.db.row.quote-db.select" '{"table": "quotes", "filters": {}, "limit": 10}'
  ```

### 6.8 Expected Test Output

```text
==================== test session starts ====================
tests/test_quote_db.py::test_add_quote_success PASSED    [  5%]
tests/test_quote_db.py::test_add_quote_author_defaults_to_unknown PASSED [ 11%]
tests/test_quote_db.py::test_add_quote_timeout PASSED     [ 17%]
tests/test_quote_db.py::test_get_quote_success PASSED     [ 23%]
tests/test_quote_db.py::test_get_quote_not_found PASSED   [ 29%]
tests/test_quote_db.py::test_get_quote_timeout PASSED     [ 35%]
tests/test_quote_db.py::test_delete_quote_success PASSED  [ 41%]
tests/test_quote_db.py::test_delete_quote_not_found PASSED [ 47%]
tests/test_quote_db.py::test_delete_quote_timeout PASSED  [ 52%]
tests/test_quote_db.py::test_validate_text_empty PASSED   [ 58%]
tests/test_quote_db.py::test_validate_text_whitespace_only PASSED [ 64%]
tests/test_quote_db.py::test_validate_text_too_long PASSED [ 70%]
tests/test_quote_db.py::test_validate_text_success PASSED [ 76%]
tests/test_quote_db.py::test_validate_author_empty PASSED [ 82%]
tests/test_quote_db.py::test_validate_author_none PASSED  [ 88%]
tests/test_quote_db.py::test_validate_author_too_long PASSED [ 94%]
tests/test_quote_db.py::test_validate_author_success PASSED [100%]

---------- coverage: platform win32, python 3.10 ----------
Name                Stmts   Miss  Cover   Missing
-------------------------------------------------
quote_db.py            95      8    92%   45-47, 62-64
-------------------------------------------------
TOTAL                  95      8    92%

==================== 17 passed in 0.52s ====================
```

---

## 7. Acceptance Criteria

- [ ] **AC-1**: Add quote operation works
  - Given valid text, author, added_by
  - When add_quote() called
  - Then quote ID returned, quote stored in database

- [ ] **AC-2**: Add quote with empty author defaults to "Unknown"
  - Given empty author string
  - When add_quote() called
  - Then author stored as "Unknown"

- [ ] **AC-3**: Add quote validates text
  - Given empty text or text > 1000 chars
  - When add_quote() called
  - Then ValueError raised with clear message

- [ ] **AC-4**: Get quote retrieves by ID
  - Given existing quote ID
  - When get_quote() called
  - Then quote dict returned with all fields

- [ ] **AC-5**: Get quote returns None for non-existent ID
  - Given non-existent quote ID
  - When get_quote() called
  - Then None returned

- [ ] **AC-6**: Delete quote removes by ID
  - Given existing quote ID
  - When delete_quote() called
  - Then True returned, quote removed from database

- [ ] **AC-7**: Delete quote returns False for non-existent ID
  - Given non-existent quote ID
  - When delete_quote() called
  - Then False returned

- [ ] **AC-8**: NATS timeouts handled gracefully
  - Given NATS server unreachable
  - When CRUD operation called
  - Then asyncio.TimeoutError raised with operation context

- [ ] **AC-9**: All unit tests pass
  - Given test suite
  - When pytest tests/ run
  - Then 17 tests pass, 0 failures

- [ ] **AC-10**: Code coverage meets target
  - Given test suite
  - When coverage measured
  - Then ≥ 80% overall, 90%+ for CRUD methods

- [ ] **AC-11**: Code passes linting
  - Given Python files
  - When flake8 and pyright run
  - Then no errors

- [ ] **AC-12**: Docstrings complete
  - Given all public methods
  - When reviewing code
  - Then all have Args, Returns, Raises sections

---

## 8. Rollout Plan

### Pre-deployment

1. Verify Sortie 1 merged (migrations and skeleton exist)
2. Run all Sortie 1 tests to ensure foundation intact
3. Review CRUD method signatures with team
4. Confirm NATS Row API endpoints operational

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-16-sortie-2-quote-db-crud`
2. Update `quote_db.py`:
   - Remove NotImplementedError from add_quote(), get_quote(), delete_quote()
   - Implement add_quote() with validation and error handling
   - Implement get_quote() with None handling
   - Implement delete_quote() with boolean return
   - Add _validate_text() helper
   - Add _validate_author() helper
   - Add logging statements
3. Update `test_quote_db.py`:
   - Add 17 unit tests covering CRUD and validation
   - Use mock_nats fixture for NATS responses
   - Test success paths and error paths
4. Run tests:

   ```bash
   cd plugins/quote-db
   pytest tests/ -v --cov=quote_db --cov-report=term-missing
   ```

5. Run linter:

   ```bash
   flake8 quote_db.py tests/
   pyright quote_db.py
   ```

6. Manual testing:
   - Start NATS server
   - Apply migrations (if not already applied)
   - Test CRUD operations in Python REPL
   - Verify error messages for invalid input
7. Update README.md:
   - Add "Usage" section with CRUD examples
   - Document error handling behavior
   - Add example code snippets
8. Commit changes:

   ```text
   Sprint 16 Sortie 2: Quote-DB CRUD Operations
   
   - Implement add_quote() with validation
   - Implement get_quote() with error handling
   - Implement delete_quote() with status return
   - Add text and author validation helpers
   - Add comprehensive unit tests (17 tests)
   - Handle NATS timeouts and JSON errors
   - Document usage in README
   
   Implements: SPEC-Sortie-2-Core-CRUD-Operations.md
   Related: PRD-Reference-Implementation-Quote-DB.md
   ```

9. Push branch and create PR
10. Code review
11. Merge to main

### Post-deployment

- Run integration tests on staging
- Verify CRUD operations work with real NATS server
- Check logs for any unexpected errors
- Share README updates with team

### Rollback Procedure

If issues arise:

```bash
# Revert code
git revert <commit-hash>

# Sortie 1 migrations still intact, no database rollback needed
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sortie 1**: Plugin skeleton, migrations, test framework
- **Sprint 13**: Row Operations API (insert, select, delete)
- **NATS server**: Running and accessible at rosey.db.row.quote-db.*
- **Python 3.10+**: For type hints (Optional, Dict)
- **pytest**: Testing framework
- **pytest-asyncio**: For async test support

### External Dependencies

- **nats-py**: NATS client library (already in requirements.txt from Sortie 1)

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Row API response format differs from expected | Low | High | Review Sprint 13 Row API spec, test with real NATS |
| NATS timeout default too short | Low | Medium | Use 2.0s timeout, make configurable in future |
| Validation rules too strict/lenient | Medium | Low | Review with team, adjust limits if needed |
| Test mocks don't match real NATS | Low | Medium | Run manual tests with real NATS server |
| JSON encoding issues with special chars | Low | Medium | Test with quotes containing Unicode, emoji |
| Error messages not user-friendly | Low | Low | Review error messages, add context |

---

## 10. Documentation

### Code Documentation

- All public methods have comprehensive docstrings
- Docstrings include Args, Returns, Raises sections
- Validation helpers documented
- Inline comments explain error handling logic

### User Documentation

**README.md** updates:

**Usage** section:

```markdown
## Usage

### Adding Quotes

from quote_db import QuoteDBPlugin
import nats

# Connect to NATS
nc = await nats.connect("nats://localhost:4222")

# Initialize plugin
plugin = QuoteDBPlugin(nc)
await plugin.initialize()

# Add a quote
quote_id = await plugin.add_quote(
    text="The only way to do great work is to love what you do.",
    author="Steve Jobs",
    added_by="alice"
)
print(f"Added quote {quote_id}")

### Retrieving Quotes

# Get a quote by ID
quote = await plugin.get_quote(quote_id)
if quote:
    print(f"{quote['text']} - {quote['author']}")
else:
    print("Quote not found")

### Deleting Quotes

# Delete a quote
deleted = await plugin.delete_quote(quote_id)
if deleted:
    print("Quote deleted")
else:
    print("Quote not found")

### Error Handling

# Validation errors
try:
    await plugin.add_quote("", "Author", "alice")  # Empty text
except ValueError as e:
    print(f"Validation error: {e}")

# NATS timeout errors
try:
    await plugin.add_quote("Text", "Author", "alice")
except asyncio.TimeoutError as e:
    print(f"NATS timeout: {e}")
```

### Developer Documentation

**Updates needed**:

- Update main README to note CRUD operations implemented
- Add quote-db to list of example plugins
- Link to quote-db as Row API usage example

---

## 11. Related Specifications

**Previous**: [SPEC-Sortie-1-Foundation-Migration-Setup.md](SPEC-Sortie-1-Foundation-Migration-Setup.md)

**Next**:

- [SPEC-Sortie-3-Advanced-Features.md](SPEC-Sortie-3-Advanced-Features.md)
- [SPEC-Sortie-4-Error-Handling-Documentation-Polish.md](SPEC-Sortie-4-Error-Handling-Documentation-Polish.md)

**Parent PRD**: [PRD-Reference-Implementation-Quote-DB.md](PRD-Reference-Implementation-Quote-DB.md)

**Related Sprints**:

- Sprint 12: KV Storage Foundation
- Sprint 13: Row Operations Foundation (used extensively)
- Sprint 14: Advanced Query Operators (used in Sortie 3)
- Sprint 15: Schema Migrations (used in Sortie 1)

**Related Documentation**:

- docs/sprints/completed/13-row-operations/SPEC-Sortie-1-Row-Foundation.md
- docs/sprints/completed/13-row-operations/SPEC-Sortie-2-Insert-Operations.md
- docs/sprints/completed/13-row-operations/SPEC-Sortie-3-Select-Operations.md
- docs/sprints/completed/13-row-operations/SPEC-Sortie-4-Delete-Operations.md

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation  
**Sortie 2 of 4**: CRUD operations complete, ready for advanced features in Sortie 3
