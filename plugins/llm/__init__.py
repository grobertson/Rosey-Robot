"""
LLM Plugin for Rosey-Robot.

This plugin provides LLM chat functionality with support for multiple providers
(Ollama, OpenAI, OpenRouter) and persona-based system prompts.

Features:
- Multiple LLM providers with automatic fallback
- Conversation context management per channel
- Multiple personas (default, concise, technical, creative)
- NATS-based plugin architecture
- Service interface for other plugins

Usage:
    !chat <message>         - Send a message to the LLM
    !chat reset             - Clear conversation context
    !chat persona <name>    - Change persona
    !chat help              - Show help

Configuration:
    See config.json for provider and service settings.
"""

from .plugin import LLMPlugin
from .service import LLMService
from .providers import (
    LLMProvider,
    Message,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from .prompts import SystemPrompts

__all__ = [
    "LLMPlugin",
    "LLMService",
    "LLMProvider",
    "Message",
    "CompletionRequest",
    "CompletionResponse",
    "ProviderError",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "SystemPrompts",
]

__version__ = "1.0.0"
