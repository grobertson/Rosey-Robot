"""
LLM integration for Rosey.

Supports multiple providers:
- OpenAI (GPT-4, GPT-3.5, and OpenAI-compatible APIs)
- Ollama (local inference)
- OpenRouter (remote API with multiple models)
"""

from .client import LLMClient
from .providers import OllamaProvider, OpenAIProvider, OpenRouterProvider

__all__ = ['LLMClient', 'OpenAIProvider', 'OllamaProvider', 'OpenRouterProvider']
