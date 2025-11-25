"""
LLM Service for plugin-to-plugin communication.

This service provides a high-level interface for chat interactions with LLMs,
managing conversation context and provider selection.
"""

import logging
from typing import Any, Optional

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

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM chat functionality.
    
    Manages conversation context per channel and provides a simple interface
    for chat interactions. Other plugins can use this service to add LLM
    capabilities.
    
    Attributes:
        provider: Active LLM provider instance
        contexts: Per-channel conversation contexts
        max_context_messages: Maximum messages to keep in context
        current_persona: Active system prompt persona
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        max_context_messages: int = 10,
        default_persona: str = "default"
    ):
        """Initialize LLM service.
        
        Args:
            provider: LLM provider instance to use
            max_context_messages: Maximum conversation history to maintain
            default_persona: Default system prompt persona
        """
        self.provider = provider
        self.max_context_messages = max_context_messages
        self.current_persona = default_persona
        
        # Per-channel conversation contexts: {channel_id: [Message, ...]}
        self.contexts: dict[str, list[Message]] = {}
        
        logger.info(
            f"LLM service initialized with {provider.__class__.__name__}, "
            f"persona={default_persona}"
        )
    
    async def chat(
        self,
        user_message: str,
        channel_id: str,
        username: str = "User",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Send a chat message and get a response.
        
        This method maintains conversation context per channel, automatically
        managing history and system prompts.
        
        Args:
            user_message: The user's message
            channel_id: Channel identifier for context isolation
            username: Username for context (currently unused, for future features)
            model: Override default model
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            The LLM's response text
            
        Raises:
            ProviderError: If chat completion fails
        """
        # Initialize context for channel if needed
        if channel_id not in self.contexts:
            self.contexts[channel_id] = []
        
        # Add user message to context
        user_msg = Message(role="user", content=user_message)
        self.contexts[channel_id].append(user_msg)
        
        # Build messages list with system prompt
        system_prompt = SystemPrompts.get(self.current_persona)
        messages = [Message(role="system", content=system_prompt)]
        
        # Add context messages (trimmed to max_context_messages)
        context_messages = self.contexts[channel_id][-self.max_context_messages:]
        messages.extend(context_messages)
        
        try:
            # Get response from provider
            response = await self.provider.chat(
                messages=messages,
                model=model or self.provider.config.get("default_model", ""),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            # Type narrowing for mypy
            if not isinstance(response, CompletionResponse):
                raise ProviderError("Expected CompletionResponse, got AsyncIterator")
            
            # Add assistant response to context
            assistant_msg = Message(role="assistant", content=response.content)
            self.contexts[channel_id].append(assistant_msg)
            
            # Trim context if too long (keep up to max_context_messages)
            if len(self.contexts[channel_id]) > self.max_context_messages:
                self.contexts[channel_id] = self.contexts[channel_id][
                    -self.max_context_messages:
                ]
            
            logger.debug(
                f"Chat response for channel {channel_id}: "
                f"{len(response.content)} chars, "
                f"usage={response.usage}"
            )
            
            return response.content
        
        except ProviderError as e:
            logger.error(f"Provider error in chat: {e}")
            # Remove the user message we added since we couldn't respond
            if self.contexts[channel_id] and self.contexts[channel_id][-1] == user_msg:
                self.contexts[channel_id].pop()
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}")
            # Remove the user message we added since we couldn't respond
            if self.contexts[channel_id] and self.contexts[channel_id][-1] == user_msg:
                self.contexts[channel_id].pop()
            raise ProviderError(f"Chat error: {e}")
    
    async def complete_raw(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a completion without conversation context.
        
        Useful for one-off completions or when context management is not needed.
        
        Args:
            prompt: The prompt text
            model: Override default model
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            The LLM's response text
            
        Raises:
            ProviderError: If completion fails
        """
        request = CompletionRequest(
            prompt=prompt,
            model=model or self.provider.config.get("default_model", ""),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        
        try:
            response = await self.provider.complete(request)
            
            logger.debug(
                f"Raw completion: {len(response.content)} chars, "
                f"usage={response.usage}"
            )
            
            return response.content
        
        except ProviderError as e:
            logger.error(f"Provider error in complete_raw: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in complete_raw: {e}")
            raise ProviderError(f"Completion error: {e}")
    
    def reset_context(self, channel_id: str) -> None:
        """Clear conversation context for a channel.
        
        Args:
            channel_id: Channel identifier
        """
        if channel_id in self.contexts:
            message_count = len(self.contexts[channel_id])
            del self.contexts[channel_id]
            logger.info(
                f"Reset context for channel {channel_id} "
                f"({message_count} messages cleared)"
            )
    
    def get_context_size(self, channel_id: str) -> int:
        """Get number of messages in channel context.
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            Number of messages in context (0 if no context)
        """
        return len(self.contexts.get(channel_id, []))
    
    def set_persona(self, persona: str) -> None:
        """Change the system prompt persona.
        
        Args:
            persona: Persona name (default, concise, technical, creative)
            
        Raises:
            ValueError: If persona is not recognized
        """
        # Validate persona
        SystemPrompts.get(persona)
        
        old_persona = self.current_persona
        self.current_persona = persona
        
        logger.info(f"Persona changed: {old_persona} -> {persona}")
    
    def get_persona(self) -> str:
        """Get current persona name.
        
        Returns:
            Current persona name
        """
        return self.current_persona
    
    @classmethod
    def create_from_config(
        cls,
        config: dict[str, Any],
        provider_name: str = "ollama"
    ) -> "LLMService":
        """Create LLM service from configuration dictionary.
        
        Args:
            config: Full plugin configuration
            provider_name: Provider to use (ollama, openai, openrouter)
            
        Returns:
            Initialized LLMService instance
            
        Raises:
            ValueError: If provider is not recognized or not configured
        """
        # Get provider configuration
        providers_config = config.get("providers", {})
        provider_config = providers_config.get(provider_name)
        
        if not provider_config:
            raise ValueError(
                f"Provider '{provider_name}' not found in configuration"
            )
        
        # Create provider instance
        provider_classes = {
            "ollama": OllamaProvider,
            "openai": OpenAIProvider,
            "openrouter": OpenRouterProvider,
        }
        
        provider_class = provider_classes.get(provider_name)
        if not provider_class:
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available: {', '.join(provider_classes.keys())}"
            )
        
        provider = provider_class(provider_config)
        
        # Get service configuration
        service_config = config.get("service", {})
        max_context = service_config.get("max_context_messages", 10)
        default_persona = service_config.get("default_persona", "default")
        
        return cls(
            provider=provider,
            max_context_messages=max_context,
            default_persona=default_persona
        )
