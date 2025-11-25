"""
OpenAI-compatible provider implementation.

Supports OpenAI API, Azure OpenAI, LocalAI, LM Studio, and other OpenAI-compatible endpoints.
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


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI and OpenAI-compatible APIs.
    
    Configuration:
        api_key: OpenAI API key (required)
        base_url: API base URL (default: "https://api.openai.com/v1")
        organization: OpenAI organization ID (optional)
        timeout: Request timeout in seconds (default: 60.0)
        default_model: Default model name (default: "gpt-4")
        max_retries: Maximum retry attempts (default: 2)
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize OpenAI provider.
        
        Args:
            config: Provider configuration dictionary
        """
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.organization = config.get("organization")
        self.timeout = config.get("timeout", 60.0)
        self.default_model = config.get("default_model", "gpt-4")
        self.max_retries = config.get("max_retries", 2)
    
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
        
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        return headers
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion using OpenAI's completions endpoint.
        
        Args:
            request: Completion request parameters
            
        Returns:
            CompletionResponse with generated content
            
        Raises:
            ProviderError: If completion fails
        """
        url = f"{self.base_url}/completions"
        payload = {
            "model": request.model or self.default_model,
            "prompt": request.prompt,
            "temperature": request.temperature,
            "stream": False,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        
        if request.stop:
            payload["stop"] = request.stop
        
        if request.options:
            payload.update(request.options)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    raise ProviderError(
                        f"OpenAI API error: {response.text}",
                        status_code=response.status_code
                    )
                
                data = response.json()
                choice = data["choices"][0]
                
                return CompletionResponse(
                    content=choice["text"],
                    model=data["model"],
                    finish_reason=choice["finish_reason"],
                    usage=data.get("usage")
                )
        
        except httpx.RequestError as e:
            raise ProviderError(f"OpenAI connection error: {e}")
        except KeyError as e:
            raise ProviderError(f"Unexpected OpenAI response format: missing {e}")
        except Exception as e:
            raise ProviderError(f"OpenAI completion error: {e}")
    
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream completion tokens from OpenAI.
        
        Args:
            request: Completion request parameters
            
        Yields:
            Individual content tokens/chunks
            
        Raises:
            ProviderError: If streaming fails
        """
        url = f"{self.base_url}/completions"
        payload = {
            "model": request.model or self.default_model,
            "prompt": request.prompt,
            "temperature": request.temperature,
            "stream": True,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        
        if request.stop:
            payload["stop"] = request.stop
        
        if request.options:
            payload.update(request.options)
        
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
                            f"OpenAI API error: {text.decode()}",
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
                                if "text" in choice:
                                    yield choice["text"]
                            except json.JSONDecodeError:
                                continue
        
        except httpx.RequestError as e:
            raise ProviderError(f"OpenAI connection error: {e}")
        except Exception as e:
            raise ProviderError(f"OpenAI streaming error: {e}")
    
    async def chat(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> CompletionResponse | AsyncIterator[str]:
        """Generate a chat completion using OpenAI's chat endpoint.
        
        Args:
            messages: List of chat messages
            model: Model identifier
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
                        f"OpenAI API error: {response.text}",
                        status_code=response.status_code
                    )
                
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                return CompletionResponse(
                    content=message["content"],
                    model=data["model"],
                    finish_reason=choice["finish_reason"],
                    usage=data.get("usage")
                )
        
        except httpx.RequestError as e:
            raise ProviderError(f"OpenAI connection error: {e}")
        except KeyError as e:
            raise ProviderError(f"Unexpected OpenAI response format: missing {e}")
        except Exception as e:
            raise ProviderError(f"OpenAI chat error: {e}")
    
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
                            f"OpenAI API error: {text.decode()}",
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
            raise ProviderError(f"OpenAI connection error: {e}")
        except Exception as e:
            raise ProviderError(f"OpenAI chat streaming error: {e}")
    
    async def is_available(self) -> bool:
        """Check if OpenAI API is available and configured.
        
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
