"""
Tests for LLM plugin NATS integration.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.llm.plugin import LLMPlugin
from plugins.llm.providers import ProviderError


class TestLLMPlugin:
    """Tests for LLM plugin."""
    
    @pytest.fixture
    def mock_nats(self):
        """Create mock NATS client."""
        nc = MagicMock()
        nc.subscribe = AsyncMock()
        nc.publish = AsyncMock()
        
        # Mock JetStream KV for memory system
        mock_js = AsyncMock()
        mock_kv = AsyncMock()
        
        # jetstream() is NOT async, just returns the JS context
        nc.jetstream = MagicMock(return_value=mock_js)
        
        # JS methods ARE async
        mock_js.key_value = AsyncMock(return_value=mock_kv)
        mock_js.create_key_value = AsyncMock(return_value=mock_kv)
        
        # KV operations
        mock_kv_entry = MagicMock()
        mock_kv_entry.value = b'[]'
        mock_kv.get = AsyncMock(return_value=mock_kv_entry)
        mock_kv.put = AsyncMock()
        mock_kv.delete = AsyncMock()
        mock_kv.keys = AsyncMock(return_value=[])
        
        return nc
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "default_provider": "ollama",
            "providers": {
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "default_model": "llama3.2"
                }
            },
            "service": {
                "max_context_messages": 10,
                "default_persona": "default"
            }
        }
    
    @pytest.fixture
    def plugin(self, mock_nats, config):
        """Create plugin instance."""
        return LLMPlugin(mock_nats, config)
    
    @pytest.mark.asyncio
    async def test_start(self, plugin, mock_nats):
        """Test plugin startup."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            # Verify service was created
            assert mock_service_class.create_from_config.called
            
            # Verify subscriptions (chat, remember, recall, forget, service request)
            assert mock_nats.subscribe.call_count == 5
            calls = [call.args[0] for call in mock_nats.subscribe.call_args_list]
            assert "rosey.command.chat" in calls
            assert "rosey.command.chat.remember" in calls
            assert "rosey.command.chat.recall" in calls
            assert "rosey.command.chat.forget" in calls
            assert "llm.request" in calls
    
    @pytest.mark.asyncio
    async def test_stop(self, plugin, mock_nats):
        """Test plugin shutdown."""
        # Create mock subscriptions
        sub1 = MagicMock()
        sub1.unsubscribe = AsyncMock()
        sub2 = MagicMock()
        sub2.unsubscribe = AsyncMock()
        
        plugin._subscriptions = [sub1, sub2]
        
        await plugin.stop()
        
        assert sub1.unsubscribe.called
        assert sub2.unsubscribe.called
        assert len(plugin._subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_handle_chat_command(self, plugin, mock_nats):
        """Test handling chat command."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Test response")
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            # Create mock message
            msg_data = {
                "command": "chat",
                "args": ["Hello", "world"],
                "channel_id": "test-channel",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_chat_command(msg)
            
            # Verify service.chat was called
            assert mock_service.chat.called
            call_args = mock_service.chat.call_args
            assert call_args.kwargs["user_message"] == "Hello world"
            assert call_args.kwargs["channel_id"] == "test-channel"
            
            # Verify response was published
            assert mock_nats.publish.called
            pub_args = mock_nats.publish.call_args
            assert pub_args.args[0] == "llm.response"
    
    @pytest.mark.asyncio
    async def test_handle_reset_command(self, plugin, mock_nats):
        """Test handling reset command."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_context_size = MagicMock(return_value=5)
            mock_service.reset_context = MagicMock()
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "command": "chat",
                "args": ["reset"],
                "channel_id": "test-channel",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_chat_command(msg)
            
            # Verify reset was called
            assert mock_service.reset_context.called
            
            # Verify response was published
            assert mock_nats.publish.called
    
    @pytest.mark.asyncio
    async def test_handle_persona_command(self, plugin, mock_nats):
        """Test handling persona command."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.set_persona = MagicMock()
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "command": "chat",
                "args": ["persona", "technical"],
                "channel_id": "test-channel",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_chat_command(msg)
            
            # Verify persona was set
            assert mock_service.set_persona.called
            assert mock_service.set_persona.call_args.args[0] == "technical"
    
    @pytest.mark.asyncio
    async def test_handle_help_command(self, plugin, mock_nats):
        """Test handling help command."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "command": "chat",
                "args": ["help"],
                "channel_id": "test-channel",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_chat_command(msg)
            
            # Verify help was sent
            assert mock_nats.publish.called
            pub_data = json.loads(mock_nats.publish.call_args.args[1].decode())
            assert "Commands" in pub_data["content"]
    
    @pytest.mark.asyncio
    async def test_handle_service_request_chat(self, plugin, mock_nats):
        """Test handling service request for chat."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Service response")
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "action": "chat",
                "channel_id": "test-channel",
                "message": "Test message",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_service_request(msg)
            
            # Verify service.chat was called
            assert mock_service.chat.called
            
            # Verify response was published
            assert mock_nats.publish.called
    
    @pytest.mark.asyncio
    async def test_handle_service_request_complete(self, plugin, mock_nats):
        """Test handling service request for completion."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.complete_raw = AsyncMock(return_value="Completion")
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "action": "complete",
                "channel_id": "test-channel",
                "message": "Test prompt"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_service_request(msg)
            
            # Verify service.complete_raw was called
            assert mock_service.complete_raw.called
    
    @pytest.mark.asyncio
    async def test_handle_service_request_reset(self, plugin, mock_nats):
        """Test handling service request for reset."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.reset_context = MagicMock()
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "action": "reset",
                "channel_id": "test-channel"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_service_request(msg)
            
            # Verify reset was called
            assert mock_service.reset_context.called
    
    @pytest.mark.asyncio
    async def test_error_handling(self, plugin, mock_nats):
        """Test error handling and publishing."""
        with patch("plugins.llm.plugin.LLMService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(side_effect=ProviderError("Test error"))
            mock_service.provider.is_available = AsyncMock(return_value=True)
            mock_service_class.create_from_config.return_value = mock_service
            
            await plugin.start()
            
            msg_data = {
                "command": "chat",
                "args": ["Test"],
                "channel_id": "test-channel",
                "username": "testuser"
            }
            msg = MagicMock()
            msg.data = json.dumps(msg_data).encode()
            
            await plugin._handle_chat_command(msg)
            
            # Verify error was published
            assert mock_nats.publish.called
            pub_args = mock_nats.publish.call_args
            assert pub_args.args[0] == "llm.error"
            
            error_data = json.loads(pub_args.args[1].decode())
            assert "error" in error_data
