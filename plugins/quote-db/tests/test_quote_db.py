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
    async def test_methods_work_after_initialization(self, initialized_plugin, mock_nats):
        """Test methods callable after initialization."""
        # Mock NATS response for add_quote
        mock_response = MagicMock()
        mock_response.data = json.dumps({"id": 1}).encode()
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
        mock_response.data = json.dumps({"id": 42}).encode()
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
        assert "timestamp" in payload["data"]
    
    @pytest.mark.asyncio
    async def test_add_quote_author_defaults_to_unknown(self, initialized_plugin, mock_nats):
        """Test that empty author defaults to 'Unknown'."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"id": 43}).encode()
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
    async def test_get_quote_not_found(self, initialized_plugin, mock_nats):
        """Test getting a non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"rows": []}).encode()
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
    async def test_delete_quote_not_found(self, initialized_plugin, mock_nats):
        """Test deleting a non-existent quote."""
        mock_response = MagicMock()
        mock_response.data = json.dumps({"deleted": 0}).encode()
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
    """Test placeholder methods exist with correct signatures."""
    
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
