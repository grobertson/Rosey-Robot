"""
OpenRouter provider implementation for multi-model LLM access.

OpenRouter provides unified access to multiple LLM providers through a single API.
"""

import httpx
from typing import Any, AsyncIterator, Optional

from .base import (
    LLMProvider,
    Message,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
)


class OpenRouterProvider(LLMProvider):
    """Provider for OpenRouter multi-model API.
    
    OpenRouter supports models from OpenAI, Anthropic, Google, Meta, and more
    through a unified OpenAI-compatible interface.
    
    Configuration:
        api_key: OpenRouter API key (required)
        base_url: API base URL (default: "https://openrouter.ai/api/v1")
        site_url: Your site URL for rankings (optional but recommended)
        site_name: Your site name for rankings (optional but recommended)
        timeout: Request timeout in seconds (default: 60.0)
        default_model: Default model name (default: "anthropic/claude-3-sonnet")
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize OpenRouter provider.
        
        Args:
            config: Provider configuration dictionary
        """
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")
        self.site_url = config.get("site_url", "")
        self.site_name = config.get("site_name", "Rosey-Robot")
        self.timeout = config.get("timeout", 60.0)
        self.default_model = config.get("default_model", "anthropic/claude-3-sonnet")
    
    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Optional headers for rankings and attribution
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        
        if self.site_name:
            headers["X-Title"] = self.site_name
        
        return headers
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion using OpenRouter's completions endpoint.
        
        Args:
            request: Completion request parameters
            
        Returns:
            CompletionResponse with generated content
            
        Raises:
            ProviderError: If completion fails
        """
        # OpenRouter uses chat completions endpoint for all models
        # Convert single prompt to chat format
        messages = [Message(role="user", content=request.prompt)]
        return await self.chat(
            messages=messages,
            model=request.model or self.default_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
        )
    
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream completion tokens from OpenRouter.
        
        Args:
            request: Completion request parameters
            
        Yields:
            Individual content tokens/chunks
            
        Raises:
            ProviderError: If streaming fails
        """
        # Convert to chat format
        messages = [Message(role="user", content=request.prompt)]
        result = await self.chat(
            messages=messages,
            model=request.model or self.default_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True
        )
        
        # Type narrowing for mypy
        if isinstance(result, CompletionResponse):
            yield result.content
        else:
            async for chunk in result:
                yield chunk
    
    async def chat(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> CompletionResponse | AsyncIterator[str]:
        """Generate a chat completion using OpenRouter's chat endpoint.
        
        Args:
            messages: List of chat messages
            model: Model identifier (e.g., "anthropic/claude-3-sonnet")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            CompletionResponse if stream=False, AsyncIterator[str] if stream=True
            
        Raises:
            ProviderError: If chat completion fails
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model or self.default_model,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": temperature,
            "stream": stream,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if stream:
            return self._stream_chat(url, payload)
        else:
            return await self._complete_chat(url, payload, model)
    
    async def _complete_chat(
        self,
        url: str,
        payload: dict[str, Any],
        model: str
    ) -> CompletionResponse:
        """Non-streaming chat completion helper.
        
        Args:
            url: API endpoint URL
            payload: Request payload
            model: Model identifier
            
        Returns:
            CompletionResponse with generated content
            
        Raises:
            ProviderError: If completion fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    raise ProviderError(
                        f"OpenRouter API error: {response.text}",
                        status_code=response.status_code
                    )
                
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                return CompletionResponse(
                    content=message["content"],
                    model=data.get("model", model),
                    finish_reason=choice.get("finish_reason", "stop"),
                    usage=data.get("usage")
                )
        
        except httpx.RequestError as e:
            raise ProviderError(f"OpenRouter connection error: {e}")
        except KeyError as e:
            raise ProviderError(f"Unexpected OpenRouter response format: missing {e}")
        except Exception as e:
            raise ProviderError(f"OpenRouter chat error: {e}")
    
    async def _stream_chat(
        self,
        url: str,
        payload: dict[str, Any]
    ) -> AsyncIterator[str]:
        """Streaming chat completion helper.
        
        Args:
            url: API endpoint URL
            payload: Request payload
            
        Yields:
            Individual content tokens/chunks
            
        Raises:
            ProviderError: If streaming fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=self._get_headers()
                ) as response:
                    if response.status_code != 200:
                        text = await response.aread()
                        raise ProviderError(
                            f"OpenRouter API error: {text.decode()}",
                            status_code=response.status_code
                        )
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]  # Remove "data: " prefix
                            
                            if line.strip() == "[DONE]":
                                break
                            
                            try:
                                import json
                                data = json.loads(line)
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                continue
        
        except httpx.RequestError as e:
            raise ProviderError(f"OpenRouter connection error: {e}")
        except Exception as e:
            raise ProviderError(f"OpenRouter chat streaming error: {e}")
    
    async def is_available(self) -> bool:
        """Check if OpenRouter API is available and configured.
        
        Returns:
            True if API key is set and endpoint responds, False otherwise
        """
        if not self.api_key:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers()
                )
                return response.status_code == 200
        except Exception:
            return False
