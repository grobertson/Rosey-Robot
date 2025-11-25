# SPEC: Sortie 4 - LLM Plugin Foundation

**Sprint:** 19 - Core Migrations  
**Sortie:** 4 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2-3 days  
**Priority:** HIGH - Core feature migration

---

## 1. Overview

### 1.1 Purpose

Migrate the existing `lib/llm_client.py` functionality into a proper NATS-based plugin:

- Clean plugin structure for LLM interactions
- LLMService interface for other plugins
- Event-driven LLM requests
- Model abstraction (Ollama, OpenAI, etc.)

### 1.2 Current State Analysis

The existing `lib/llm_client.py` contains:
- Ollama client configuration
- Chat completion requests
- System prompt management
- Streaming support

This needs to be:
1. Wrapped in a plugin structure
2. Exposed as a service (LLMService)
3. Provider-agnostic interface
4. Event-driven via NATS

### 1.3 Scope

**In Scope (Sortie 4):**
- Plugin structure and configuration
- Migrate LLM client code
- Provider abstraction layer
- Basic LLMService interface
- Chat command (`!chat <message>`)
- Unit tests

**Out of Scope (Sortie 5):**
- Advanced providers (OpenAI, Anthropic)
- Conversation memory/context
- Streaming responses

### 1.4 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Ollama server (external)
- httpx for API requests

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/llm/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── service.py            # LLMService interface
├── providers/
│   ├── __init__.py
│   ├── base.py           # Provider interface
│   └── ollama.py         # Ollama provider
├── prompts.py            # System prompts
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_providers.py    # Provider tests
    ├── test_service.py      # Service tests
    └── test_plugin.py       # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.chat` | Subscribe | Handle `!chat` command |
| `rosey.command.llm.reset` | Subscribe | Reset conversation |
| `llm.request` | Subscribe | Internal LLM request |
| `llm.response` | Publish | LLM response event |
| `llm.error` | Publish | LLM error event |

### 2.3 Provider Abstraction

```python
# plugins/llm/providers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, AsyncIterator


@dataclass
class Message:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None  # For user identification


@dataclass
class CompletionRequest:
    """Request for chat completion."""
    messages: List[Message]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


@dataclass
class CompletionResponse:
    """Response from chat completion."""
    content: str
    model: str
    finish_reason: str
    usage: Optional[dict] = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Implementations:
    - OllamaProvider: Local Ollama server
    - OpenAIProvider: OpenAI API (future)
    - AnthropicProvider: Anthropic API (future)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...
    
    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """List of available models."""
        ...
    
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Generate a chat completion.
        
        Args:
            request: Completion request
            
        Returns:
            Completion response
            
        Raises:
            ProviderError: If completion fails
        """
        ...
    
    @abstractmethod
    async def stream(
        self, 
        request: CompletionRequest
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion.
        
        Args:
            request: Completion request (stream=True will be set)
            
        Yields:
            Chunks of response text
        """
        ...
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        ...
    
    async def close(self) -> None:
        """Cleanup resources."""
        pass


class ProviderError(Exception):
    """Error from LLM provider."""
    
    def __init__(self, message: str, provider: str, recoverable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable
```

### 2.4 Ollama Provider

```python
# plugins/llm/providers/ollama.py

import httpx
from typing import List, Optional, AsyncIterator
from .base import LLMProvider, CompletionRequest, CompletionResponse, Message, ProviderError


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider.
    
    Connects to local or remote Ollama server.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._default_model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available_models: List[str] = []
    
    @property
    def name(self) -> str:
        return "ollama"
    
    @property
    def available_models(self) -> List[str]:
        return self._available_models
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate chat completion."""
        client = await self._get_client()
        
        model = request.model or self._default_model
        
        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
            },
        }
        
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens
        
        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return CompletionResponse(
                content=data["message"]["content"],
                model=data.get("model", model),
                finish_reason=data.get("done_reason", "stop"),
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                },
            )
            
        except httpx.ConnectError:
            raise ProviderError(
                "Cannot connect to Ollama server",
                self.name,
                recoverable=True,
            )
        except httpx.TimeoutException:
            raise ProviderError(
                "Request timed out",
                self.name,
                recoverable=True,
            )
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"HTTP error: {e.response.status_code}",
                self.name,
                recoverable=e.response.status_code >= 500,
            )
    
    async def stream(
        self, 
        request: CompletionRequest
    ) -> AsyncIterator[str]:
        """Stream chat completion."""
        client = await self._get_client()
        
        model = request.model or self._default_model
        
        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "stream": True,
            "options": {
                "temperature": request.temperature,
            },
        }
        
        async with client.stream("POST", "/api/chat", json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
    
    async def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            
            if response.status_code == 200:
                data = response.json()
                self._available_models = [
                    m["name"] for m in data.get("models", [])
                ]
                return True
            return False
            
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

### 2.5 System Prompts

```python
# plugins/llm/prompts.py

from typing import Optional


class SystemPrompts:
    """
    System prompts for different personas.
    """
    
    DEFAULT = """You are Rosey, a helpful and friendly chat bot. 
You assist users in a chat room with various tasks and conversation.
Keep responses concise and appropriate for a chat environment.
Be helpful, witty, and engaging."""

    CONCISE = """You are Rosey, a chat bot assistant.
Give brief, helpful responses. Maximum 2-3 sentences unless more detail is requested.
Be friendly but efficient."""

    TECHNICAL = """You are Rosey, a technically-minded chat bot assistant.
Help with programming, technical questions, and debugging.
Use code blocks for code. Be precise and accurate."""

    CREATIVE = """You are Rosey, a creative and playful chat bot.
Be imaginative, tell stories, make jokes, and engage in creative writing.
Have fun with responses while being helpful."""

    @classmethod
    def get(cls, name: str = "default") -> str:
        """Get system prompt by name."""
        prompts = {
            "default": cls.DEFAULT,
            "concise": cls.CONCISE,
            "technical": cls.TECHNICAL,
            "creative": cls.CREATIVE,
        }
        return prompts.get(name.lower(), cls.DEFAULT)
    
    @classmethod
    def available(cls) -> list[str]:
        """Get available prompt names."""
        return ["default", "concise", "technical", "creative"]
```

### 2.6 LLM Service

```python
# plugins/llm/service.py

from typing import Optional, List
from dataclasses import dataclass
from .providers.base import (
    LLMProvider, 
    CompletionRequest, 
    CompletionResponse,
    Message,
    ProviderError,
)
from .prompts import SystemPrompts


@dataclass
class ChatResult:
    """Result of a chat request."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None


class LLMService:
    """
    Service interface for LLM interactions.
    
    Exposed to other plugins for programmatic access.
    
    Example usage:
        llm = await get_service("llm")
        result = await llm.chat("Hello!", user="player1")
        if result.success:
            print(result.content)
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        default_prompt: str = "default",
        max_context_messages: int = 10,
    ):
        self._provider = provider
        self._default_prompt = default_prompt
        self._max_context = max_context_messages
        
        # Simple conversation context (per channel)
        # More advanced memory in Sortie 5
        self._contexts: dict[str, List[Message]] = {}
    
    @property
    def provider_name(self) -> str:
        """Get current provider name."""
        return self._provider.name
    
    @property
    def available_models(self) -> List[str]:
        """Get available models."""
        return self._provider.available_models
    
    async def is_available(self) -> bool:
        """Check if LLM service is available."""
        return await self._provider.is_available()
    
    async def chat(
        self,
        message: str,
        user: Optional[str] = None,
        channel: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> ChatResult:
        """
        Send a chat message and get a response.
        
        Args:
            message: User's message
            user: Username (for context)
            channel: Channel (for context isolation)
            system_prompt: Override system prompt
            model: Override model
            temperature: Response temperature
            
        Returns:
            ChatResult with response or error
        """
        # Build messages
        messages = []
        
        # System prompt
        prompt = system_prompt or SystemPrompts.get(self._default_prompt)
        messages.append(Message(role="system", content=prompt))
        
        # Context (if channel provided)
        if channel:
            context = self._get_context(channel)
            messages.extend(context)
        
        # User message
        user_msg = Message(role="user", content=message, name=user)
        messages.append(user_msg)
        
        # Request completion
        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
        )
        
        try:
            response = await self._provider.complete(request)
            
            # Update context
            if channel:
                self._add_to_context(channel, user_msg)
                self._add_to_context(
                    channel, 
                    Message(role="assistant", content=response.content)
                )
            
            return ChatResult(
                success=True,
                content=response.content,
                model=response.model,
            )
            
        except ProviderError as e:
            return ChatResult(
                success=False,
                error=str(e),
            )
    
    async def complete_raw(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> CompletionResponse:
        """
        Raw completion request (for advanced use).
        
        Use this for custom message flows.
        """
        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return await self._provider.complete(request)
    
    def reset_context(self, channel: str) -> None:
        """Reset conversation context for a channel."""
        self._contexts.pop(channel, None)
    
    def _get_context(self, channel: str) -> List[Message]:
        """Get context for a channel."""
        return self._contexts.get(channel, [])
    
    def _add_to_context(self, channel: str, message: Message) -> None:
        """Add message to context."""
        if channel not in self._contexts:
            self._contexts[channel] = []
        
        self._contexts[channel].append(message)
        
        # Trim to max context
        if len(self._contexts[channel]) > self._max_context:
            self._contexts[channel] = self._contexts[channel][-self._max_context:]
```

### 2.7 Plugin Implementation

```python
# plugins/llm/plugin.py

import json
from typing import Optional
from lib.plugin.base import PluginBase
from .service import LLMService
from .providers.ollama import OllamaProvider
from .prompts import SystemPrompts


class LLMPlugin(PluginBase):
    """
    LLM (Large Language Model) plugin.
    
    Commands:
        !chat <message> - Chat with the AI
        !chat reset - Reset conversation
        !chat persona <name> - Change AI persona
    """
    
    NAME = "llm"
    VERSION = "1.0.0"
    DESCRIPTION = "AI-powered chat"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        
        # Will be initialized in setup
        self.provider: Optional[OllamaProvider] = None
        self.service: Optional[LLMService] = None
        
        # Per-channel personas
        self._personas: dict[str, str] = {}
    
    async def setup(self) -> None:
        """Initialize LLM provider and service."""
        # Initialize provider
        self.provider = OllamaProvider(
            base_url=self.config.get("ollama_url", "http://localhost:11434"),
            model=self.config.get("model", "llama3.2:3b"),
            timeout=self.config.get("timeout", 60.0),
        )
        
        # Check availability
        if not await self.provider.is_available():
            self.logger.warning("LLM provider not available")
        else:
            self.logger.info(f"LLM provider ready: {self.provider.available_models}")
        
        # Initialize service
        self.service = LLMService(
            provider=self.provider,
            default_prompt=self.config.get("default_persona", "default"),
            max_context_messages=self.config.get("max_context", 10),
        )
        
        # Register service
        await self.register_service("llm", self.service)
        
        # Subscribe to commands
        await self.subscribe("rosey.command.chat", self._handle_chat)
        await self.subscribe("llm.request", self._handle_internal_request)
        
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup."""
        if self.provider:
            await self.provider.close()
        await self.unregister_service("llm")
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_chat(self, msg) -> None:
        """Handle !chat command."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        message = data.get("args", "").strip()
        
        if not message:
            return await self._reply_usage(msg, "chat <message>")
        
        # Handle subcommands
        if message.lower() == "reset":
            self.service.reset_context(channel)
            return await self._reply(msg, "🔄 Conversation reset!")
        
        if message.lower().startswith("persona "):
            persona = message[8:].strip().lower()
            if persona in SystemPrompts.available():
                self._personas[channel] = persona
                return await self._reply(msg, f"🎭 Persona set to: {persona}")
            else:
                available = ", ".join(SystemPrompts.available())
                return await self._reply_error(msg, f"Unknown persona. Available: {available}")
        
        # Check availability
        if not await self.service.is_available():
            return await self._reply_error(msg, "AI is currently unavailable")
        
        # Get persona for channel
        persona = self._personas.get(channel, "default")
        system_prompt = SystemPrompts.get(persona)
        
        # Send typing indicator (optional, via CyTube)
        # await self._send_typing(channel)
        
        # Get response
        result = await self.service.chat(
            message=message,
            user=user,
            channel=channel,
            system_prompt=system_prompt,
        )
        
        if result.success:
            await self._reply(msg, f"🤖 {result.content}")
            
            # Emit event
            await self.publish("llm.response", {
                "event": "llm.response",
                "channel": channel,
                "user": user,
                "prompt": message,
                "response": result.content,
                "model": result.model,
            })
        else:
            await self._reply_error(msg, f"AI error: {result.error}")
            
            await self.publish("llm.error", {
                "event": "llm.error",
                "channel": channel,
                "error": result.error,
            })
    
    async def _handle_internal_request(self, msg) -> None:
        """Handle internal LLM request from other plugins."""
        data = json.loads(msg.data.decode())
        
        prompt = data.get("prompt")
        system = data.get("system_prompt")
        model = data.get("model")
        
        if not prompt:
            return
        
        result = await self.service.chat(
            message=prompt,
            system_prompt=system,
            model=model,
        )
        
        if data.get("reply_to"):
            await self.nats_client.publish(
                data["reply_to"],
                json.dumps({
                    "success": result.success,
                    "content": result.content,
                    "error": result.error,
                }).encode()
            )
```

### 2.8 Configuration

```json
{
  "ollama_url": "http://localhost:11434",
  "model": "llama3.2:3b",
  "timeout": 60.0,
  "default_persona": "default",
  "max_context": 10,
  "temperature": 0.7,
  "max_response_length": 500
}
```

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/llm/` directory
2. Create all files with docstrings
3. Create `config.json` with defaults

### Step 2: Implement Provider Abstraction (1 hour)

1. Implement base provider interface
2. Define Message and request/response types
3. Define ProviderError

### Step 3: Implement Ollama Provider (1.5 hours)

1. Migrate from existing lib/llm_client.py
2. Implement complete() method
3. Implement stream() method (basic)
4. Implement is_available() check
5. Write tests with mocked HTTP

### Step 4: Implement System Prompts (30 minutes)

1. Define default prompts
2. Add persona variations
3. Test prompt selection

### Step 5: Implement LLM Service (1.5 hours)

1. Implement service interface
2. Implement chat() method
3. Implement context management
4. Wire up provider
5. Write tests

### Step 6: Implement Plugin (1.5 hours)

1. Initialize provider and service
2. Implement chat command handler
3. Implement persona switching
4. Implement context reset
5. Register service

### Step 7: Testing (1 hour)

1. Unit tests for provider
2. Unit tests for service
3. Integration tests for plugin
4. Test with real Ollama (optional)

---

## 4. Test Cases

### 4.1 Provider Tests

| Test | Validation |
|------|------------|
| Complete request | Returns response |
| Connection error | Raises ProviderError |
| Timeout | Raises ProviderError |
| is_available() | Returns True/False |

### 4.2 Service Tests

| Test | Validation |
|------|------------|
| chat() | Returns ChatResult |
| Context added | Messages in context |
| Context trimmed | Max messages respected |
| reset_context() | Context cleared |

### 4.3 Plugin Tests

| Command | Expected |
|---------|----------|
| `!chat Hello` | AI response |
| `!chat reset` | Context reset message |
| `!chat persona concise` | Persona changed |
| `!chat` (empty) | Usage message |
| Provider unavailable | Error message |

---

## 5. Acceptance Criteria

### 5.1 Functional

- [ ] `!chat <message>` gets AI response
- [ ] `!chat reset` clears conversation
- [ ] `!chat persona <name>` changes persona
- [ ] Context maintained per channel
- [ ] Graceful handling of unavailable LLM

### 5.2 Technical

- [ ] Provider abstraction allows future providers
- [ ] Service exposed to other plugins
- [ ] Events emitted for responses/errors
- [ ] Test coverage > 85%

### 5.3 Migration

- [ ] Existing lib/llm_client.py functionality preserved
- [ ] Configuration migrated
- [ ] No breaking changes

---

## 6. Sample Interactions

```
User: !chat Hello, who are you?
Rosey: 🤖 Hello! I'm Rosey, your friendly chat bot assistant. 
       I'm here to help with questions, have conversations, 
       and make your chat experience more fun!

User: !chat What's the weather like?
Rosey: 🤖 I don't have access to real-time weather data, but I'd 
       suggest checking a weather app or website for your location!

User: !chat persona technical
Rosey: 🎭 Persona set to: technical

User: !chat How do I reverse a string in Python?
Rosey: 🤖 Use slicing with `[::-1]`:
       ```python
       s = "hello"
       reversed_s = s[::-1]  # "olleh"
       ```

User: !chat reset
Rosey: 🔄 Conversation reset!
```

---

## 7. Checklist

### Pre-Implementation
- [ ] Review existing lib/llm_client.py
- [ ] Test Ollama server connection
- [ ] Design provider interface

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement provider abstraction
- [ ] Implement Ollama provider
- [ ] Implement system prompts
- [ ] Implement LLM service
- [ ] Implement plugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real Ollama
- [ ] Test persona switching
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add LLM plugin foundation

- Implement provider abstraction layer
- Migrate Ollama client from lib/llm_client.py
- Add LLMService for other plugins
- Add !chat command with personas
- Add conversation context per channel

Implements: SPEC-Sortie-4-LLMFoundation.md
Related: PRD-Core-Migrations.md
Part: 1 of 3 (LLM Migration)
```
