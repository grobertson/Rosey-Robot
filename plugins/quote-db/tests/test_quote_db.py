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
