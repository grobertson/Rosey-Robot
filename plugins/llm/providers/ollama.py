"""
Ollama provider implementation for local LLM inference.

Supports local Ollama server at configurable endpoint (default localhost:11434).
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


class OllamaProvider(LLMProvider):
    """Provider for local Ollama LLM server.
    
    Configuration:
        base_url: Ollama server URL (default: "http://localhost:11434")
        timeout: Request timeout in seconds (default: 60.0)
        default_model: Default model name (default: "llama3.2")
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize Ollama provider.
        
        Args:
            config: Provider configuration dictionary
        """
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.timeout = config.get("timeout", 60.0)
        self.default_model = config.get("default_model", "llama3.2")
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion using Ollama's generate endpoint.
        
        Args:
            request: Completion request parameters
            
        Returns:
            CompletionResponse with generated content
            
        Raises:
            ProviderError: If completion fails
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": request.model or self.default_model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
            }
        }
        
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens
        
        if request.stop:
            payload["options"]["stop"] = request.stop
        
        if request.options:
            payload["options"].update(request.options)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code != 200:
                    raise ProviderError(
                        f"Ollama API error: {response.text}",
                        status_code=response.status_code
                    )
                
                data = response.json()
                
                return CompletionResponse(
                    content=data.get("response", ""),
                    model=data.get("model", request.model),
                    finish_reason="stop" if data.get("done") else "length",
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                    }
                )
        
        except httpx.RequestError as e:
            raise ProviderError(f"Ollama connection error: {e}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"Ollama completion error: {e}")
    
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream completion tokens from Ollama.
        
        Args:
            request: Completion request parameters
            
        Yields:
            Individual content tokens/chunks
            
        Raises:
            ProviderError: If streaming fails
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": request.model or self.default_model,
            "prompt": request.prompt,
            "stream": True,
            "options": {
                "temperature": request.temperature,
            }
        }
        
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens
        
        if request.stop:
            payload["options"]["stop"] = request.stop
        
        if request.options:
            payload["options"].update(request.options)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        text = await response.aread()
                        raise ProviderError(
                            f"Ollama API error: {text.decode()}",
                            status_code=response.status_code
                        )
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                import json
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                            except json.JSONDecodeError:
                                continue
        
        except httpx.RequestError as e:
            raise ProviderError(f"Ollama connection error: {e}")
        except Exception as e:
            raise ProviderError(f"Ollama streaming error: {e}")
    
    async def chat(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> CompletionResponse | AsyncIterator[str]:
        """Generate a chat completion using Ollama's chat endpoint.
        
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
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model or self.default_model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
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
                response = await client.post(url, json=payload)
                
                if response.status_code != 200:
                    raise ProviderError(
                        f"Ollama API error: {response.text}",
                        status_code=response.status_code
                    )
                
                data = response.json()
                message = data.get("message", {})
                
                return CompletionResponse(
                    content=message.get("content", ""),
                    model=data.get("model", model),
                    finish_reason="stop" if data.get("done") else "length",
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                    }
                )
        
        except httpx.RequestError as e:
            raise ProviderError(f"Ollama connection error: {e}")
        except Exception as e:
            raise ProviderError(f"Ollama chat error: {e}")
    
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
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        text = await response.aread()
                        raise ProviderError(
                            f"Ollama API error: {text.decode()}",
                            status_code=response.status_code
                        )
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                import json
                                data = json.loads(line)
                                message = data.get("message", {})
                                if "content" in message:
                                    yield message["content"]
                            except json.JSONDecodeError:
                                continue
        
        except httpx.RequestError as e:
            raise ProviderError(f"Ollama connection error: {e}")
        except Exception as e:
            raise ProviderError(f"Ollama chat streaming error: {e}")
    
    async def is_available(self) -> bool:
        """Check if Ollama server is available.
        
        Returns:
            True if server responds to health check, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
