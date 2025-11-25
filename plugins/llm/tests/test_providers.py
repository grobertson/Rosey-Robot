"""
Tests for LLM provider implementations.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from plugins.llm.providers import (
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    Message,
    CompletionRequest,
    ProviderError,
)


class TestOllamaProvider:
    """Tests for Ollama provider."""
    
    @pytest.fixture
    def provider(self):
        """Create Ollama provider instance."""
        config = {
            "base_url": "http://localhost:11434",
            "timeout": 60.0,
            "default_model": "llama3.2"
        }
        return OllamaProvider(config)
    
    @pytest.mark.asyncio
    async def test_complete(self, provider):
        """Test completion generation."""
        request = CompletionRequest(
            prompt="What is Python?",
            model="llama3.2",
            temperature=0.7
        )
        
        mock_response = {
            "model": "llama3.2",
            "response": "Python is a programming language.",
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 20
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.complete(request)
            
            assert response.content == "Python is a programming language."
            assert response.model == "llama3.2"
            assert response.finish_reason == "stop"
            assert response.usage["total_tokens"] == 30
    
    @pytest.mark.asyncio
    async def test_complete_error(self, provider):
        """Test completion error handling."""
        request = CompletionRequest(
            prompt="Test",
            model="llama3.2"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=500,
                text="Internal server error"
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(request)
            
            assert "Ollama API error" in str(exc_info.value)
            assert exc_info.value.status_code == 500
    
    @pytest.mark.asyncio
    async def test_chat(self, provider):
        """Test chat completion."""
        messages = [
            Message(role="user", content="Hello")
        ]
        
        mock_response = {
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "Hi there!"
            },
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 10
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.chat(
                messages=messages,
                model="llama3.2"
            )
            
            assert response.content == "Hi there!"
            assert response.model == "llama3.2"
    
    @pytest.mark.asyncio
    async def test_stream(self, provider):
        """Test streaming completion."""
        request = CompletionRequest(
            prompt="Count to 3",
            model="llama3.2",
            stream=True
        )
        
        mock_lines = [
            '{"response": "1"}',
            '{"response": "2"}',
            '{"response": "3"}'
        ]
        
        async def mock_aiter_lines():
            for line in mock_lines:
                yield line
        
        mock_stream_response = MagicMock(
            status_code=200,
            aiter_lines=mock_aiter_lines
        )
        mock_stream_response.__aenter__ = AsyncMock(return_value=mock_stream_response)
        mock_stream_response.__aexit__ = AsyncMock()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.stream = MagicMock(return_value=mock_stream_response)
            
            chunks = []
            async for chunk in provider.stream(request):
                chunks.append(chunk)
            
            assert chunks == ["1", "2", "3"]
    
    @pytest.mark.asyncio
    async def test_is_available(self, provider):
        """Test availability check."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            available = await provider.is_available()
            assert available is True
    
    @pytest.mark.asyncio
    async def test_is_not_available(self, provider):
        """Test availability check when server is down."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            available = await provider.is_available()
            assert available is False


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4"
        }
        return OpenAIProvider(config)
    
    @pytest.mark.asyncio
    async def test_complete(self, provider):
        """Test completion generation."""
        request = CompletionRequest(
            prompt="What is Python?",
            model="gpt-4"
        )
        
        mock_response = {
            "model": "gpt-4",
            "choices": [{
                "text": "Python is a programming language.",
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.complete(request)
            
            assert response.content == "Python is a programming language."
            assert response.model == "gpt-4"
            assert response.finish_reason == "stop"
            assert response.usage["total_tokens"] == 30
    
    @pytest.mark.asyncio
    async def test_chat(self, provider):
        """Test chat completion."""
        messages = [
            Message(role="user", content="Hello")
        ]
        
        mock_response = {
            "model": "gpt-4",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hi there!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 10,
                "total_tokens": 15
            }
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.chat(
                messages=messages,
                model="gpt-4"
            )
            
            assert response.content == "Hi there!"
            assert response.model == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_is_available_no_key(self):
        """Test availability check without API key."""
        config = {"api_key": "", "base_url": "https://api.openai.com/v1"}
        provider = OpenAIProvider(config)
        
        available = await provider.is_available()
        assert available is False
    
    @pytest.mark.asyncio
    async def test_is_available_with_key(self, provider):
        """Test availability check with API key."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            available = await provider.is_available()
            assert available is True


class TestOpenRouterProvider:
    """Tests for OpenRouter provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenRouter provider instance."""
        config = {
            "api_key": "test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "site_url": "https://example.com",
            "site_name": "Test App",
            "default_model": "anthropic/claude-3-sonnet"
        }
        return OpenRouterProvider(config)
    
    @pytest.mark.asyncio
    async def test_chat(self, provider):
        """Test chat completion."""
        messages = [
            Message(role="user", content="Hello")
        ]
        
        mock_response = {
            "model": "anthropic/claude-3-sonnet",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you?"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 12,
                "total_tokens": 17
            }
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.chat(
                messages=messages,
                model="anthropic/claude-3-sonnet"
            )
            
            assert response.content == "Hello! How can I help you?"
            assert "anthropic" in response.model
    
    @pytest.mark.asyncio
    async def test_complete(self, provider):
        """Test completion (converted to chat format)."""
        request = CompletionRequest(
            prompt="What is AI?",
            model="anthropic/claude-3-sonnet"
        )
        
        mock_response = {
            "model": "anthropic/claude-3-sonnet",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "AI stands for Artificial Intelligence."
                },
                "finish_reason": "stop"
            }]
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            response = await provider.complete(request)
            
            assert "Artificial Intelligence" in response.content
    
    @pytest.mark.asyncio
    async def test_headers_with_site_info(self, provider):
        """Test that site info is included in headers."""
        headers = provider._get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["HTTP-Referer"] == "https://example.com"
        assert headers["X-Title"] == "Test App"


class TestMessage:
    """Tests for Message dataclass."""
    
    def test_to_dict(self):
        """Test message conversion to dictionary."""
        msg = Message(role="user", content="Hello")
        result = msg.to_dict()
        
        assert result == {"role": "user", "content": "Hello"}
    
    def test_message_creation(self):
        """Test message creation."""
        msg = Message(role="assistant", content="Hi there!")
        
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
