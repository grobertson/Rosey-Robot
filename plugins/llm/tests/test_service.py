"""
Tests for LLM service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from plugins.llm.service import LLMService
from plugins.llm.providers import (
    Message,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
)
from plugins.llm.prompts import SystemPrompts


class TestLLMService:
    """Tests for LLM service."""
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = MagicMock()
        provider.config = {"default_model": "test-model"}
        provider.chat = AsyncMock()
        provider.complete = AsyncMock()
        provider.is_available = AsyncMock(return_value=True)
        return provider
    
    @pytest.fixture
    def service(self, mock_provider):
        """Create LLM service instance."""
        return LLMService(
            provider=mock_provider,
            max_context_messages=10,
            default_persona="default"
        )
    
    @pytest.mark.asyncio
    async def test_chat(self, service, mock_provider):
        """Test chat with context management."""
        # Mock provider response
        mock_provider.chat.return_value = CompletionResponse(
            content="Hello! How can I help?",
            model="test-model",
            finish_reason="stop"
        )
        
        response = await service.chat(
            user_message="Hi",
            channel_id="test-channel",
            username="testuser"
        )
        
        assert response == "Hello! How can I help?"
        
        # Verify context was created
        assert "test-channel" in service.contexts
        assert len(service.contexts["test-channel"]) == 2  # user + assistant
        
        # Verify provider was called with correct messages
        call_args = mock_provider.chat.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0].role == "system"  # System prompt
        assert messages[1].role == "user"
        assert messages[1].content == "Hi"
    
    @pytest.mark.asyncio
    async def test_chat_maintains_context(self, service, mock_provider):
        """Test that context is maintained across messages."""
        mock_provider.chat.return_value = CompletionResponse(
            content="Response",
            model="test-model",
            finish_reason="stop"
        )
        
        # First message
        await service.chat("Message 1", "channel-1")
        
        # Second message
        await service.chat("Message 2", "channel-1")
        
        # Verify context has both messages
        assert len(service.contexts["channel-1"]) == 4  # 2 user + 2 assistant
        
        # Verify second call included first message in context
        call_args = mock_provider.chat.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 3  # system + previous user/assistant + new user
    
    @pytest.mark.asyncio
    async def test_chat_isolates_channels(self, service, mock_provider):
        """Test that different channels have isolated contexts."""
        mock_provider.chat.return_value = CompletionResponse(
            content="Response",
            model="test-model",
            finish_reason="stop"
        )
        
        await service.chat("Message 1", "channel-1")
        await service.chat("Message 2", "channel-2")
        
        assert "channel-1" in service.contexts
        assert "channel-2" in service.contexts
        assert len(service.contexts["channel-1"]) == 2
        assert len(service.contexts["channel-2"]) == 2
    
    @pytest.mark.asyncio
    async def test_chat_context_trimming(self, service, mock_provider):
        """Test that context is trimmed when too long."""
        mock_provider.chat.return_value = CompletionResponse(
            content="Response",
            model="test-model",
            finish_reason="stop"
        )
        
        # Send many messages to exceed max_context_messages * 2
        for i in range(15):
            await service.chat(f"Message {i}", "channel-1")
        
        # Context should be trimmed
        context_size = len(service.contexts["channel-1"])
        assert context_size <= service.max_context_messages
    
    @pytest.mark.asyncio
    async def test_chat_error_handling(self, service, mock_provider):
        """Test that errors don't corrupt context."""
        mock_provider.chat.side_effect = ProviderError("Test error")
        
        with pytest.raises(ProviderError):
            await service.chat("Message", "channel-1")
        
        # Context should be empty (message was removed on error)
        assert len(service.contexts.get("channel-1", [])) == 0
    
    @pytest.mark.asyncio
    async def test_complete_raw(self, service, mock_provider):
        """Test raw completion without context."""
        mock_provider.complete.return_value = CompletionResponse(
            content="Completion result",
            model="test-model",
            finish_reason="stop"
        )
        
        response = await service.complete_raw(
            prompt="Test prompt",
            temperature=0.5
        )
        
        assert response == "Completion result"
        
        # Verify provider was called
        call_args = mock_provider.complete.call_args
        request = call_args[0][0]
        assert isinstance(request, CompletionRequest)
        assert request.prompt == "Test prompt"
        assert request.temperature == 0.5
    
    def test_reset_context(self, service):
        """Test context reset."""
        # Create some context
        service.contexts["channel-1"] = [
            Message(role="user", content="Message 1"),
            Message(role="assistant", content="Response 1"),
        ]
        
        service.reset_context("channel-1")
        
        assert "channel-1" not in service.contexts
    
    def test_get_context_size(self, service):
        """Test getting context size."""
        service.contexts["channel-1"] = [
            Message(role="user", content="Message 1"),
            Message(role="assistant", content="Response 1"),
        ]
        
        assert service.get_context_size("channel-1") == 2
        assert service.get_context_size("nonexistent") == 0
    
    def test_set_persona(self, service):
        """Test changing persona."""
        service.set_persona("concise")
        assert service.current_persona == "concise"
        
        service.set_persona("technical")
        assert service.current_persona == "technical"
    
    def test_set_invalid_persona(self, service):
        """Test setting invalid persona."""
        with pytest.raises(ValueError) as exc_info:
            service.set_persona("nonexistent")
        
        assert "Unknown persona" in str(exc_info.value)
    
    def test_get_persona(self, service):
        """Test getting current persona."""
        assert service.get_persona() == "default"
        
        service.set_persona("creative")
        assert service.get_persona() == "creative"
    
    def test_create_from_config(self, mock_provider):
        """Test creating service from configuration."""
        config = {
            "default_provider": "ollama",
            "providers": {
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "default_model": "llama3.2"
                }
            },
            "service": {
                "max_context_messages": 20,
                "default_persona": "technical"
            }
        }
        
        service = LLMService.create_from_config(config, provider_name="ollama")
        
        assert service.max_context_messages == 20
        assert service.current_persona == "technical"
    
    def test_create_from_config_missing_provider(self):
        """Test creating service with missing provider."""
        config = {
            "providers": {}
        }
        
        with pytest.raises(ValueError) as exc_info:
            LLMService.create_from_config(config, provider_name="nonexistent")
        
        assert "not found in configuration" in str(exc_info.value)
    
    def test_create_from_config_invalid_provider(self):
        """Test creating service with invalid provider name."""
        config = {
            "providers": {
                "valid": {}
            }
        }
        
        # Try with nonexistent provider
        with pytest.raises(ValueError) as exc_info:
            LLMService.create_from_config(config, provider_name="invalid")
        
        assert "not found in configuration" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_chat_with_persona(self, service, mock_provider):
        """Test that persona affects system prompt."""
        mock_provider.chat.return_value = CompletionResponse(
            content="Response",
            model="test-model",
            finish_reason="stop"
        )
        
        # Change persona
        service.set_persona("technical")
        
        await service.chat("Test message", "channel-1")
        
        # Verify system prompt contains technical persona
        call_args = mock_provider.chat.call_args
        messages = call_args.kwargs["messages"]
        system_prompt = messages[0].content
        
        assert "technical" in system_prompt.lower()
