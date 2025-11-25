"""
Base provider interface for LLM integration.

This module defines the abstract base class and common types for LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional


@dataclass
class Message:
    """A chat message with role and content."""
    
    role: str  # "system", "user", or "assistant"
    content: str
    
    def to_dict(self) -> dict[str, str]:
        """Convert message to dictionary format."""
        return {"role": self.role, "content": self.content}


@dataclass
class CompletionRequest:
    """Request parameters for LLM completion."""
    
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stop: Optional[list[str]] = None
    stream: bool = False
    
    # Provider-specific options
    options: dict[str, Any] | None = None


@dataclass
class CompletionResponse:
    """Response from LLM completion."""
    
    content: str
    model: str
    finish_reason: str  # "stop", "length", "error"
    usage: dict[str, int] | None = None  # {"prompt_tokens": X, "completion_tokens": Y, "total_tokens": Z}


class ProviderError(Exception):
    """Base exception for provider errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        """Initialize provider error.
        
        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.status_code = status_code


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    All provider implementations must inherit from this class and implement
    the abstract methods for completion generation and health checking.
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion for the given request.
        
        Args:
            request: Completion request parameters
            
        Returns:
            CompletionResponse with generated content
            
        Raises:
            ProviderError: If completion fails
        """
        pass
    
    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream completion tokens as they are generated.
        
        Args:
            request: Completion request parameters (with stream=True)
            
        Yields:
            Individual content tokens/chunks
            
        Raises:
            ProviderError: If streaming fails
        """
        pass
    
    @abstractmethod
    async def chat(
        self, 
        messages: list[Message], 
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> CompletionResponse | AsyncIterator[str]:
        """Generate a chat completion with message history.
        
        Args:
            messages: List of chat messages (system, user, assistant)
            model: Model identifier
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            CompletionResponse if stream=False, AsyncIterator[str] if stream=True
            
        Raises:
            ProviderError: If chat completion fails
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and configured correctly.
        
        Returns:
            True if provider can be used, False otherwise
        """
        pass
