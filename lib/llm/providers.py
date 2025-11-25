"""
Base provider interface for LLM backends.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import aiohttp


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration.

        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Chat completion with message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            Generated response
        """
        pass


class OllamaProvider(LLMProvider):
    """Provider for local Ollama inference."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ollama provider.

        Config keys:
            - base_url: Ollama server URL (default: http://localhost:11434)
            - model: Model name (e.g., 'llama3', 'mistral')
        """
        super().__init__(config)
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.model = config.get('model', 'llama3')

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response using Ollama."""
        url = f"{self.base_url}/api/generate"

        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': temperature,
            }
        }

        if system_prompt:
            payload['system'] = system_prompt

        if max_tokens:
            payload['options']['num_predict'] = max_tokens

        # Add any extra options
        payload['options'].update(kwargs)

        assert self.session is not None  # set in __aenter__
        async with self.session.post(url, json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama API error: {resp.status} - {await resp.text()}")

            data = await resp.json()
            return data.get('response', '')

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Chat completion using Ollama."""
        url = f"{self.base_url}/api/chat"

        payload = {
            'model': self.model,
            'messages': messages,
            'stream': False,
            'options': {
                'temperature': temperature,
            }
        }

        if max_tokens:
            payload['options']['num_predict'] = max_tokens

        payload['options'].update(kwargs)

        assert self.session is not None  # set in __aenter__
        async with self.session.post(url, json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama API error: {resp.status} - {await resp.text()}")

            data = await resp.json()
            return data.get('message', {}).get('content', '')


class OpenRouterProvider(LLMProvider):
    """Provider for OpenRouter API."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenRouter provider.

        Config keys:
            - api_key: OpenRouter API key (required)
            - model: Model identifier (e.g., 'anthropic/claude-3-haiku')
            - base_url: API endpoint (default: https://openrouter.ai/api/v1)
            - site_url: Your site URL for OpenRouter rankings (optional)
            - site_name: Your site name for OpenRouter rankings (optional)
        """
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("OpenRouter requires 'api_key' in config")

        self.model = config.get('model', 'anthropic/claude-3-haiku')
        self.base_url = config.get('base_url', 'https://openrouter.ai/api/v1')
        self.site_url = config.get('site_url')
        self.site_name = config.get('site_name', 'Rosey CyTube Bot')

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for OpenRouter requests."""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        if self.site_url:
            headers['HTTP-Referer'] = self.site_url

        if self.site_name:
            headers['X-Title'] = self.site_name

        return headers

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response using OpenRouter."""
        # Convert to chat format
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        return await self.chat(messages, temperature, max_tokens, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Chat completion using OpenRouter."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
        }

        if max_tokens:
            payload['max_tokens'] = max_tokens

        # Add any extra parameters
        payload.update(kwargs)

        assert self.session is not None  # set in __aenter__
        async with self.session.post(url, json=payload, headers=self._get_headers()) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"OpenRouter API error: {resp.status} - {error_text}")

            data = await resp.json()
            return data['choices'][0]['message']['content']


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI API and OpenAI-compatible endpoints."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenAI provider.

        Config keys:
            - api_key: OpenAI API key (required)
            - model: Model identifier (e.g., 'gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo')
            - base_url: API endpoint (default: https://api.openai.com/v1)
                       Can be overridden for Azure OpenAI, LocalAI, LM Studio, etc.
            - organization: OpenAI organization ID (optional)
            - timeout: Request timeout in seconds (default: 30)

        Examples:
            # Standard OpenAI
            {'api_key': 'sk-...', 'model': 'gpt-4o-mini'}

            # Azure OpenAI
            {'api_key': '...', 'model': 'gpt-4',
             'base_url': 'https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT'}

            # LocalAI
            {'api_key': 'not-needed', 'model': 'llama-3',
             'base_url': 'http://localhost:8080/v1'}

            # LM Studio
            {'api_key': 'not-needed', 'model': 'local-model',
             'base_url': 'http://localhost:1234/v1'}
        """
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("OpenAI provider requires 'api_key' in config")

        self.model = config.get('model', 'gpt-4o-mini')
        self.base_url = config.get('base_url', 'https://api.openai.com/v1')
        self.organization = config.get('organization')
        self.timeout = config.get('timeout', 30)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for OpenAI API requests."""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        if self.organization:
            headers['OpenAI-Organization'] = self.organization

        return headers

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response using OpenAI API."""
        # Convert to chat format
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        return await self.chat(messages, temperature, max_tokens, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Chat completion using OpenAI API."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
        }

        if max_tokens:
            payload['max_tokens'] = max_tokens

        # Add any extra parameters (e.g., top_p, frequency_penalty, etc.)
        payload.update(kwargs)

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            assert self.session is not None  # set in __aenter__
            async with self.session.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=timeout
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"OpenAI API error: {resp.status} - {error_text}"
                    )

                data = await resp.json()
                return data['choices'][0]['message']['content']

        except asyncio.TimeoutError:
            raise RuntimeError(
                f"OpenAI API request timed out after {self.timeout}s"
            )
