"""
High-level LLM client for Rosey.

Manages provider selection, context, and conversation state.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from .providers import OpenAIProvider, OllamaProvider, OpenRouterProvider


class LLMClient:
    """
    Main LLM client for Rosey.
    
    Handles:
    - Provider abstraction
    - Conversation context
    - Prompt management
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM client.
        
        Config structure:
        {
            'provider': 'openai' | 'ollama' | 'openrouter',
            'openai': {...},
            'ollama': {...},
            'openrouter': {...},
            'system_prompt_file': 'path/to/prompt.md',
            'max_context_messages': 10,
            'temperature': 0.7,
            'max_tokens': 500
        }
        """
        self.config = config
        self.provider_name = config.get('provider', 'ollama')
        
        # Initialize provider
        if self.provider_name == 'openai':
            provider_config = config.get('openai', {})
            self.provider = OpenAIProvider(provider_config)
        elif self.provider_name == 'ollama':
            provider_config = config.get('ollama', {})
            self.provider = OllamaProvider(provider_config)
        elif self.provider_name == 'openrouter':
            provider_config = config.get('openrouter', {})
            self.provider = OpenRouterProvider(provider_config)
        else:
            raise ValueError(f"Unknown provider: {self.provider_name}")
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        # Conversation settings
        self.max_context_messages = config.get('max_context_messages', 10)
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 500)
        
        # Conversation history per user
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
    
    def _load_system_prompt(self) -> Optional[str]:
        """Load system prompt from file."""
        prompt_file = self.config.get('system_prompt_file')
        if not prompt_file:
            return None
        
        prompt_path = Path(prompt_file)
        if not prompt_path.is_absolute():
            # Relative to bot/rosey directory
            base_dir = Path(__file__).parent.parent
            prompt_path = base_dir / prompt_file
        
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
        
        return None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.provider.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.provider.__aexit__(exc_type, exc_val, exc_tb)
    
    def _get_conversation(self, user: str) -> List[Dict[str, str]]:
        """Get conversation history for a user."""
        if user not in self.conversations:
            self.conversations[user] = []
        return self.conversations[user]
    
    def _add_message(self, user: str, role: str, content: str):
        """Add a message to conversation history."""
        conversation = self._get_conversation(user)
        conversation.append({'role': role, 'content': content})
        
        # Trim to max context
        if len(conversation) > self.max_context_messages * 2:  # *2 for user+assistant pairs
            # Keep system message if it exists, trim oldest exchanges
            self.conversations[user] = conversation[-(self.max_context_messages * 2):]
    
    def clear_conversation(self, user: str):
        """Clear conversation history for a user."""
        if user in self.conversations:
            del self.conversations[user]
    
    async def chat(
        self,
        user: str,
        message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Chat with the LLM maintaining conversation context.
        
        Args:
            user: Username for conversation tracking
            message: User's message
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            
        Returns:
            LLM response
        """
        # Add user message to history
        self._add_message(user, 'user', message)
        
        # Build messages array
        messages = []
        if self.system_prompt:
            messages.append({'role': 'system', 'content': self.system_prompt})
        
        messages.extend(self._get_conversation(user))
        
        # Generate response
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        response = await self.provider.chat(
            messages=messages,
            temperature=temp,
            max_tokens=max_tok
        )
        
        # Add assistant response to history
        self._add_message(user, 'assistant', response)
        
        return response
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a one-off response without conversation context.
        
        Args:
            prompt: The prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            
        Returns:
            LLM response
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        return await self.provider.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=temp,
            max_tokens=max_tok
        )
