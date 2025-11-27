"""Unit tests for QuoteDBPlugin class."""
import pytest
import json
import asyncio
from unittest.mock import MagicMock
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
        # Mock returns for: 1) migration status, 2) schema registration
        status_response = MagicMock()
        status_response.data = json.dumps({
            "success": True,
            "current_version": 3,
            "pending_count": 0
        }).encode()
        
        schema_response = MagicMock()
        schema_response.data = json.dumps({"success": True}).encode()
        
        mock_nats.request.side_effect = [status_response, schema_response]
        
        await plugin.initialize()

        assert plugin._initialized is True
        # Should make 2 calls: migration status + schema registration
        assert mock_nats.request.call_count == 2
        first_call = mock_nats.request.call_args_list[0]
        assert "db.migrate.quote-db.status" in first_call[0][0]
        second_call = mock_nats.request.call_args_list[1]
        assert "db.row.quote-db.schema.register" in second_call[0][0]

    @pytest.mark.asyncio
    async def test_initialize_missing_migrations(self, plugin, mock_nats):
        """Test initialization fails if migrations not applied."""
        # Mock returns current_version=1 (missing migrations 2 and 3)
        error_response = MagicMock()
        error_response.data = json.dumps({
            "success": True,
            "current_version": 1,
            "pending_count": 2
        }).encode()
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
    async def test_methods_work_after_initialization(self, initialized_plugin, mock_nats):
        """Test methods callable after initialization."""
        # Mock NATS response for add_quote
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "id": 1}).encode()
        mock_nats.request.return_value = mock_response

        # Methods should not raise "not initialized" error
        quote_id = await initialized_plugin.add_quote("test quote", "Author", "user")
        assert quote_id == 1


class TestAddQuote:
    """Test add_quote operation."""

    @pytest.mark.asyncio
    async def test_add_quote_success(self, initialized_plugin, mock_nats):
        """Test adding a quote successfully."""
        # Mock NATS response
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "id": 42}).encode()
        mock_nats.request.return_value = mock_response

        # Add quote
        quote_id = await initialized_plugin.add_quote("Test quote", "Alice", "bob")

        # Verify result
        assert quote_id == 42

        # Verify NATS request
        mock_nats.request.assert_called()
        call_args = mock_nats.request.call_args
        assert call_args[0][0] == "rosey.db.row.quote-db.insert"

        payload = json.loads(call_args[0][1].decode())
        assert payload["table"] == "quotes"
        assert payload["data"]["text"] == "Test quote"
        assert payload["data"]["author"] == "Alice"
        assert payload["data"]["added_by"] == "bob"
        assert payload["data"]["score"] == 0
        assert "added_at" in payload["data"]
        assert "tags" in payload["data"]

    @pytest.mark.asyncio
    async def test_add_quote_author_defaults_to_unknown(self, initialized_plugin, mock_nats):
        """Test that empty author defaults to 'Unknown'."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "id": 43}).encode()
        mock_nats.request.return_value = mock_response

        quote_id = await initialized_plugin.add_quote("Test", "", "bob")
        assert quote_id == 43

        payload = json.loads(mock_nats.request.call_args[0][1].decode())
        assert payload["data"]["author"] == "Unknown"

    @pytest.mark.asyncio
    async def test_add_quote_timeout(self, initialized_plugin, mock_nats):
        """Test handling of NATS timeout."""
        mock_nats.request.side_effect = asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError, match="add_quote"):
            await initialized_plugin.add_quote("Test", "Alice", "bob")


class TestGetQuote:
    """Test get_quote operation."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, initialized_plugin, mock_nats):
        """Test getting a quote by ID."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "success": True,
            "exists": True,
            "data": {
                "id": 42,
                "text": "Test quote",
                "author": "Alice",
                "added_by": "bob",
                "timestamp": 1234567890,
                "score": 5
            }
        }).encode()
        mock_nats.request.return_value = mock_response

        quote = await initialized_plugin.get_quote(42)

        assert quote is not None
        assert quote["id"] == 42
        assert quote["text"] == "Test quote"
        assert quote["author"] == "Alice"
        assert quote["score"] == 5

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, initialized_plugin, mock_nats):
        """Test getting a non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "exists": False}).encode()
        mock_nats.request.return_value = mock_response

        quote = await initialized_plugin.get_quote(999)
        assert quote is None

    @pytest.mark.asyncio
    async def test_get_quote_timeout(self, initialized_plugin, mock_nats):
        """Test handling of NATS timeout."""
        mock_nats.request.side_effect = asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError, match="get_quote"):
            await initialized_plugin.get_quote(42)


class TestDeleteQuote:
    """Test delete_quote operation."""

    @pytest.mark.asyncio
    async def test_delete_quote_success(self, initialized_plugin, mock_nats):
        """Test deleting a quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "deleted": True}).encode()
        mock_nats.request.return_value = mock_response

        deleted = await initialized_plugin.delete_quote(42)
        assert deleted is True

        # Verify NATS request
        call_args = mock_nats.request.call_args
        assert call_args[0][0] == "rosey.db.row.quote-db.delete"
        payload = json.loads(call_args[0][1].decode())
        assert payload["id"] == 42  # Direct ID, not filters

    @pytest.mark.asyncio
    async def test_delete_quote_not_found(self, initialized_plugin, mock_nats):
        """Test deleting a non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "deleted": False}).encode()
        mock_nats.request.return_value = mock_response

        deleted = await initialized_plugin.delete_quote(999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_quote_timeout(self, initialized_plugin, mock_nats):
        """Test handling of NATS timeout."""
        mock_nats.request.side_effect = asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError, match="delete_quote"):
            await initialized_plugin.delete_quote(42)


class TestValidation:
    """Test input validation."""

    def test_validate_text_empty(self, plugin):
        """Test validation of empty text."""
        with pytest.raises(ValueError, match="cannot be empty"):
            plugin._validate_text("")

    def test_validate_text_whitespace_only(self, plugin):
        """Test validation of whitespace-only text."""
        with pytest.raises(ValueError, match="cannot be empty"):
            plugin._validate_text("   ")

    def test_validate_text_too_long(self, plugin):
        """Test validation of text exceeding max length."""
        with pytest.raises(ValueError, match="too long"):
            plugin._validate_text("x" * 1001)

    def test_validate_text_success(self, plugin):
        """Test validation of valid text."""
        result = plugin._validate_text("  Valid quote  ")
        assert result == "Valid quote"

    def test_validate_author_empty(self, plugin):
        """Test validation of empty author."""
        result = plugin._validate_author("")
        assert result == "Unknown"

    def test_validate_author_none(self, plugin):
        """Test validation of None author."""
        result = plugin._validate_author(None)
        assert result == "Unknown"

    def test_validate_author_too_long(self, plugin):
        """Test validation of author exceeding max length."""
        with pytest.raises(ValueError, match="too long"):
            plugin._validate_author("x" * 101)

    def test_validate_author_success(self, plugin):
        """Test validation of valid author."""
        result = plugin._validate_author("  Alice  ")
        assert result == "Alice"


class TestPlaceholderMethods:
    """Test convenience wrapper methods."""

    @pytest.mark.asyncio
    async def test_find_by_author_success(self, initialized_plugin, mock_nats):
        """Test find_by_author calls search_quotes."""
        mock_nats.reset_mock()

        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "success": True,
            "rows": [
                {"id": 1, "text": "Test quote", "author": "Einstein", "score": 5}
            ]
        }).encode()
        mock_nats.request.return_value = mock_response

        quotes = await initialized_plugin.find_by_author("Einstein")

        assert len(quotes) == 1
        assert quotes[0]["author"] == "Einstein"
        mock_nats.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_score_success(self, initialized_plugin, mock_nats):
        """Test increment_score increases score by custom amount."""
        mock_nats.reset_mock()

        # Mock update response (atomic $inc)
        update_response = MagicMock()
        update_response.data = json.dumps({"success": True, "updated": True}).encode()

        # Mock get_quote response (retrieve updated score)
        get_response = MagicMock()
        get_response.data = json.dumps({
            "success": True,
            "exists": True,
            "data": {"id": 1, "text": "Test", "author": "Author", "score": 15}
        }).encode()

        mock_nats.request.side_effect = [update_response, get_response]

        score = await initialized_plugin.increment_score(1, amount=10)

        assert score == 15
        assert mock_nats.request.call_count == 2

    @pytest.mark.asyncio
    async def test_increment_score_not_found(self, initialized_plugin, mock_nats):
        """Test increment_score raises ValueError when quote not found."""
        mock_nats.reset_mock()

        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "updated": False}).encode()
        mock_nats.request.return_value = mock_response

        with pytest.raises(ValueError, match="Quote 999 not found"):
            await initialized_plugin.increment_score(999, amount=5)


class TestSearchQuotes:
    """Test search_quotes operation."""

    @pytest.mark.asyncio
    async def test_search_quotes_success(self, initialized_plugin, mock_nats):
        """Test searching quotes with results."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "success": True,
            "rows": [
                {"id": 1, "text": "Test quote", "author": "Alice", "score": 5},
                {"id": 2, "text": "Another quote", "author": "Bob", "score": 3}
            ]
        }).encode()
        mock_nats.request.return_value = mock_response

        results = await initialized_plugin.search_quotes("test", limit=10)

        assert len(results) == 2
        assert results[0]["author"] == "Alice"

        # Verify NATS payload
        call_args = mock_nats.request.call_args
        assert "search" in call_args[0][0]
        payload = json.loads(call_args[0][1].decode())
        assert "$or" in payload["filters"]
        assert payload["filters"]["$or"][0]["author"]["$like"] == "%test%"
        assert payload["filters"]["$or"][1]["text"]["$like"] == "%test%"

    @pytest.mark.asyncio
    async def test_search_quotes_no_results(self, initialized_plugin, mock_nats):
        """Test searching with no results."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "rows": []}).encode()
        mock_nats.request.return_value = mock_response

        results = await initialized_plugin.search_quotes("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_quotes_invalid_limit(self, initialized_plugin):
        """Test search with invalid limit."""
        with pytest.raises(ValueError, match="between 1 and 100"):
            await initialized_plugin.search_quotes("test", limit=0)

        with pytest.raises(ValueError, match="between 1 and 100"):
            await initialized_plugin.search_quotes("test", limit=101)


class TestVoting:
    """Test upvote/downvote operations."""

    @pytest.mark.asyncio
    async def test_upvote_quote_success(self, initialized_plugin, mock_nats):
        """Test upvoting a quote."""
        # Reset mock to clear initialization calls
        mock_nats.request.reset_mock()

        # Mock update response (atomic $inc)
        update_response = MagicMock()
        update_response.data = json.dumps({"success": True, "updated": True}).encode()

        # Mock get_quote response (retrieve updated score)
        get_response = MagicMock()
        get_response.data = json.dumps({
            "success": True,
            "exists": True,
            "data": {"id": 42, "text": "Test", "author": "Alice", "score": 6}
        }).encode()

        mock_nats.request.side_effect = [update_response, get_response]

        score = await initialized_plugin.upvote_quote(42)
        assert score == 6

        # Verify update payload uses atomic $inc
        call_args = mock_nats.request.call_args_list[0]
        assert "update" in call_args[0][0]
        payload = json.loads(call_args[0][1].decode())
        assert payload["operations"]["score"]["$inc"] == 1

    @pytest.mark.asyncio
    async def test_downvote_quote_success(self, initialized_plugin, mock_nats):
        """Test downvoting a quote."""
        # Reset mock to clear initialization calls
        mock_nats.request.reset_mock()

        # Mock update response (atomic $inc with -1)
        update_response = MagicMock()
        update_response.data = json.dumps({"success": True, "updated": True}).encode()

        # Mock get_quote response (retrieve updated score)
        get_response = MagicMock()
        get_response.data = json.dumps({
            "success": True,
            "exists": True,
            "data": {"id": 42, "text": "Test", "author": "Alice", "score": 4}
        }).encode()

        mock_nats.request.side_effect = [update_response, get_response]

        score = await initialized_plugin.downvote_quote(42)
        assert score == 4

        # Verify $inc with negative value
        call_args = mock_nats.request.call_args_list[0]
        payload = json.loads(call_args[0][1].decode())
        assert payload["operations"]["score"]["$inc"] == -1

    @pytest.mark.asyncio
    async def test_upvote_quote_not_found(self, initialized_plugin, mock_nats):
        """Test upvoting non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "updated": False}).encode()
        mock_nats.request.return_value = mock_response

        with pytest.raises(ValueError, match="not found"):
            await initialized_plugin.upvote_quote(999)

    @pytest.mark.asyncio
    async def test_downvote_quote_not_found(self, initialized_plugin, mock_nats):
        """Test downvoting non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True, "updated": False}).encode()
        mock_nats.request.return_value = mock_response

        with pytest.raises(ValueError, match="not found"):
            await initialized_plugin.downvote_quote(999)


class TestTopQuotes:
    """Test top_quotes operation."""

    @pytest.mark.asyncio
    async def test_top_quotes_success(self, initialized_plugin, mock_nats):
        """Test getting top quotes."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({
            "rows": [
                {"id": 1, "text": "Best quote", "author": "Alice", "score": 10},
                {"id": 2, "text": "Good quote", "author": "Bob", "score": 5}
            ]
        }).encode()
        mock_nats.request.return_value = mock_response

        results = await initialized_plugin.top_quotes(limit=10)

        assert len(results) == 2
        assert results[0]["score"] == 10

        # Verify payload with $gte filter
        call_args = mock_nats.request.call_args
        payload = json.loads(call_args[0][1].decode())
        assert payload["filters"]["score"]["$gte"] == 1
        assert payload["sort"]["field"] == "score"
        assert payload["sort"]["order"] == "desc"

    @pytest.mark.asyncio
    async def test_top_quotes_empty(self, initialized_plugin, mock_nats):
        """Test top quotes with no high-scored quotes."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"rows": []}).encode()
        mock_nats.request.return_value = mock_response

        results = await initialized_plugin.top_quotes()
        assert results == []

    @pytest.mark.asyncio
    async def test_top_quotes_invalid_limit(self, initialized_plugin):
        """Test top quotes with invalid limit."""
        with pytest.raises(ValueError, match="between 1 and 100"):
            await initialized_plugin.top_quotes(limit=0)


class TestRandomQuote:
    """Test random_quote operation."""

    @pytest.mark.asyncio
    async def test_random_quote_success(self, initialized_plugin, mock_nats):
        """Test getting a random quote."""
        # Mock KV cache hit
        kv_response = MagicMock()
        kv_response.data = json.dumps({"exists": True, "value": "5"}).encode()

        # Mock get_quote response
        get_response = MagicMock()
        get_response.data = json.dumps({
            "success": True,
            "exists": True,
            "data": {"id": 3, "text": "Random quote", "author": "Alice", "score": 2}
        }).encode()

        mock_nats.request.side_effect = [kv_response, get_response]

        quote = await initialized_plugin.random_quote()

        assert quote is not None
        assert quote["text"] == "Random quote"

    @pytest.mark.asyncio
    async def test_random_quote_empty_database(self, initialized_plugin, mock_nats):
        """Test random quote with empty database."""
        # Mock KV cache returning 0 count
        kv_response = MagicMock()
        kv_response.data = json.dumps({"exists": True, "value": "0"}).encode()
        mock_nats.request.return_value = kv_response

        quote = await initialized_plugin.random_quote()
        assert quote is None

    @pytest.mark.asyncio
    async def test_random_quote_fallback(self, initialized_plugin, mock_nats):
        """Test random quote with ID gap fallback."""
        # Mock KV cache
        kv_response = MagicMock()
        kv_response.data = json.dumps({"exists": True, "value": "10"}).encode()

        # Mock get_quote returning None (ID gap)
        get_none = MagicMock()
        get_none.data = json.dumps({"success": True, "exists": False}).encode()

        # Mock fallback search
        fallback_response = MagicMock()
        fallback_response.data = json.dumps({
            "success": True,
            "rows": [{"id": 1, "text": "First quote", "author": "Alice", "score": 0}]
        }).encode()

        mock_nats.request.side_effect = [kv_response, get_none, fallback_response]

        quote = await initialized_plugin.random_quote()

        assert quote is not None
        assert quote["text"] == "First quote"


class TestKVCaching:
    """Test KV caching operations."""

    @pytest.mark.asyncio
    async def test_get_quote_count_cache_hit(self, initialized_plugin, mock_nats):
        """Test getting count from KV cache."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"exists": True, "value": "42"}).encode()
        mock_nats.request.return_value = mock_response

        count = await initialized_plugin._get_quote_count()

        assert count == 42
        call_args = mock_nats.request.call_args
        assert "kv.quote-db.get" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_quote_count_cache_miss(self, initialized_plugin, mock_nats):
        """Test counting from database on cache miss."""
        # Mock KV miss
        kv_response = MagicMock()
        kv_response.data = json.dumps({"exists": False}).encode()

        # Mock database count
        db_response = MagicMock()
        db_response.data = json.dumps({
            "rows": [{"id": 1}, {"id": 2}, {"id": 3}]
        }).encode()

        # Mock KV set (cache update)
        set_response = MagicMock()
        set_response.data = json.dumps({"success": True}).encode()

        mock_nats.request.side_effect = [kv_response, db_response, set_response]

        count = await initialized_plugin._get_quote_count()

        assert count == 3

        # Verify cache update was called (check for kv.set in call history)
        set_calls = [c for c in mock_nats.request.call_args_list if "kv.quote-db.set" in str(c[0][0])]
        assert len(set_calls) >= 1
        payload = json.loads(set_calls[0][0][1].decode())
        assert payload["key"] == "total_count"
        assert payload["value"] == "3"
        assert payload["ttl"] == 300
