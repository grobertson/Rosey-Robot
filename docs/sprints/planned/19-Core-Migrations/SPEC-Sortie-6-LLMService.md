# SPEC: Sortie 6 - LLM Service & Events

**Sprint:** 19 - Core Migrations  
**Sortie:** 6 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 1.5 days  
**Priority:** HIGH - Enables plugin integration  
**Prerequisites:** Sortie 5 (LLM Memory & Context)

---

## 1. Overview

### 1.1 Purpose

Expose LLM functionality as a service that other plugins can consume:

- NATS-based service interface for LLM capabilities
- Event system for LLM interactions
- Persona management API
- Rate limiting and quotas
- Usage tracking and analytics

### 1.2 Scope

**In Scope:**
- LLMService with public API
- NATS request/response interface
- Event publishing for LLM activity
- Rate limiting per user/channel
- Usage tracking
- Provider health monitoring

**Out of Scope (Sortie 7):**
- MCP tools
- External tool integration

### 1.3 Dependencies

- Sortie 5 (LLM Memory) - MUST be complete
- Event bus (Sprint 6a)

---

## 2. Technical Design

### 2.1 Extended File Structure

```
plugins/llm/
├── ...existing files...
├── service.py            # LLMService - public API
├── rate_limiter.py       # Rate limiting
├── events.py             # Event definitions
└── tests/
    ├── ...existing tests...
    ├── test_service.py      # Service tests
    ├── test_rate_limiter.py # Rate limiter tests
    └── test_events.py       # Event tests
```

### 2.2 NATS Subjects (Service)

```python
# Service request subjects (other plugins call these)
SUBJECTS = {
    # Core LLM operations
    "rosey.llm.chat": "Simple chat message",
    "rosey.llm.complete": "Raw completion request",
    "rosey.llm.summarize": "Summarize text",
    
    # Memory operations
    "rosey.llm.memory.add": "Add memory",
    "rosey.llm.memory.recall": "Recall memories",
    
    # Persona operations
    "rosey.llm.persona.get": "Get current persona",
    "rosey.llm.persona.set": "Set persona for channel",
    "rosey.llm.persona.list": "List available personas",
    
    # Status and health
    "rosey.llm.status": "Get LLM status",
    "rosey.llm.usage": "Get usage statistics",
}
```

### 2.3 Event Subjects

```python
# Events published by LLM plugin (other plugins subscribe)
EVENTS = {
    "rosey.event.llm.response": "LLM generated a response",
    "rosey.event.llm.error": "LLM request failed",
    "rosey.event.llm.memory": "Memory was added/recalled",
    "rosey.event.llm.summarized": "Conversation was summarized",
    "rosey.event.llm.usage.threshold": "Usage threshold reached",
}
```

### 2.4 Message Schemas

```python
# plugins/llm/schemas.py

from dataclasses import dataclass
from typing import Optional, List, Dict, Any


# === Requests ===

@dataclass
class ChatRequest:
    """Request for simple chat."""
    channel: str
    user: str
    message: str
    persona: Optional[str] = None  # Override default


@dataclass
class CompletionRequest:
    """Request for raw completion."""
    messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    provider: Optional[str] = None  # Force specific provider


@dataclass
class SummarizeRequest:
    """Request for text summarization."""
    text: str
    max_length: int = 200
    style: str = "concise"  # concise, detailed, bullets


@dataclass  
class MemoryAddRequest:
    """Request to add memory."""
    channel: str
    content: str
    category: str = "fact"
    user_id: Optional[str] = None
    importance: int = 1


@dataclass
class MemoryRecallRequest:
    """Request to recall memories."""
    channel: str
    query: str
    user_id: Optional[str] = None
    limit: int = 5


# === Responses ===

@dataclass
class ChatResponse:
    """Response from chat."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    provider: Optional[str] = None


@dataclass
class SummaryResponse:
    """Response from summarization."""
    success: bool
    summary: Optional[str] = None
    error: Optional[str] = None


@dataclass
class MemoryResponse:
    """Response from memory operations."""
    success: bool
    memories: List[str] = None
    count: int = 0
    error: Optional[str] = None


@dataclass
class StatusResponse:
    """LLM status response."""
    healthy: bool
    provider: str
    model: str
    requests_today: int
    tokens_today: int
    rate_limited: bool = False


# === Events ===

@dataclass
class LLMResponseEvent:
    """Published when LLM generates response."""
    channel: str
    user: str
    prompt_length: int
    response_length: int
    tokens_used: int
    provider: str
    latency_ms: int


@dataclass
class LLMErrorEvent:
    """Published when LLM request fails."""
    channel: str
    user: str
    error: str
    provider: str


@dataclass
class UsageThresholdEvent:
    """Published when usage threshold reached."""
    user: str
    channel: str
    threshold_type: str  # daily, hourly, tokens
    current: int
    limit: int
```

### 2.5 LLM Service

```python
# plugins/llm/service.py

import time
import json
from typing import Optional, List
from dataclasses import asdict
from .providers.base import Message, ProviderError
from .memory import ConversationMemory
from .rate_limiter import RateLimiter, RateLimitExceeded
from .schemas import *


class LLMService:
    """
    Public LLM service for other plugins.
    
    Provides a clean API for:
    - Chat completions
    - Memory operations
    - Persona management
    - Usage tracking
    """
    
    def __init__(
        self,
        provider,
        memory: ConversationMemory,
        rate_limiter: RateLimiter,
        nats_client,
    ):
        self._provider = provider
        self._memory = memory
        self._rate_limiter = rate_limiter
        self._nc = nats_client
        
        # Usage tracking
        self._requests_today = 0
        self._tokens_today = 0
        self._last_reset = time.time()
    
    async def start(self) -> None:
        """Start service and subscribe to subjects."""
        # Service endpoints
        await self._nc.subscribe("rosey.llm.chat", cb=self._handle_chat)
        await self._nc.subscribe("rosey.llm.complete", cb=self._handle_complete)
        await self._nc.subscribe("rosey.llm.summarize", cb=self._handle_summarize)
        await self._nc.subscribe("rosey.llm.memory.add", cb=self._handle_memory_add)
        await self._nc.subscribe("rosey.llm.memory.recall", cb=self._handle_memory_recall)
        await self._nc.subscribe("rosey.llm.status", cb=self._handle_status)
        await self._nc.subscribe("rosey.llm.usage", cb=self._handle_usage)
    
    # === Public API Methods ===
    
    async def chat(
        self,
        channel: str,
        user: str,
        message: str,
        persona: Optional[str] = None,
    ) -> ChatResponse:
        """
        High-level chat with context and memory.
        
        Used by other plugins for conversational AI.
        """
        start = time.monotonic()
        
        try:
            # Check rate limit
            await self._rate_limiter.check(user, channel)
            
            # Build context
            context = await self._memory.get_context(
                channel=channel,
                system_prompt=self._get_persona_prompt(persona),
                user_id=user,
                query=message,
            )
            
            # Make request
            messages = context.to_messages()
            messages.append(Message(role="user", content=message, name=user))
            
            result = await self._provider.complete(messages)
            
            # Store in memory
            await self._memory.add_message(channel, "user", message, user)
            await self._memory.add_message(channel, "assistant", result.content)
            
            # Track usage
            self._requests_today += 1
            self._tokens_today += result.tokens_used or 0
            
            # Publish event
            latency = int((time.monotonic() - start) * 1000)
            await self._publish_response_event(
                channel, user, len(message), len(result.content),
                result.tokens_used or 0, self._provider.name, latency
            )
            
            return ChatResponse(
                success=True,
                content=result.content,
                tokens_used=result.tokens_used or 0,
                provider=self._provider.name,
            )
            
        except RateLimitExceeded as e:
            await self._publish_error_event(channel, user, str(e))
            return ChatResponse(success=False, error=str(e))
            
        except ProviderError as e:
            await self._publish_error_event(channel, user, str(e))
            return ChatResponse(success=False, error=str(e))
    
    async def complete(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """
        Raw completion without memory/context.
        
        For advanced use cases where caller manages context.
        """
        try:
            message_objs = [
                Message(role=m["role"], content=m["content"])
                for m in messages
            ]
            
            result = await self._provider.complete(
                messages=message_objs,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            self._requests_today += 1
            self._tokens_today += result.tokens_used or 0
            
            return ChatResponse(
                success=True,
                content=result.content,
                tokens_used=result.tokens_used or 0,
                provider=self._provider.name,
            )
            
        except ProviderError as e:
            return ChatResponse(success=False, error=str(e))
    
    async def summarize(
        self,
        text: str,
        max_length: int = 200,
        style: str = "concise",
    ) -> SummaryResponse:
        """
        Summarize text.
        
        Useful for other plugins (trivia explanations, etc).
        """
        prompts = {
            "concise": f"Summarize in {max_length} words or less:\n\n{text}",
            "detailed": f"Provide a detailed summary:\n\n{text}",
            "bullets": f"Summarize as bullet points:\n\n{text}",
        }
        
        prompt = prompts.get(style, prompts["concise"])
        
        try:
            result = await self._provider.complete(
                [Message(role="user", content=prompt)],
                temperature=0.3,
            )
            
            return SummaryResponse(
                success=True,
                summary=result.content,
            )
            
        except ProviderError as e:
            return SummaryResponse(success=False, error=str(e))
    
    async def add_memory(
        self,
        channel: str,
        content: str,
        category: str = "fact",
        user_id: Optional[str] = None,
        importance: int = 1,
    ) -> MemoryResponse:
        """Add a memory."""
        await self._memory.remember(
            channel=channel,
            content=content,
            category=category,
            user_id=user_id,
            importance=importance,
        )
        return MemoryResponse(success=True, count=1)
    
    async def recall_memories(
        self,
        channel: str,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> MemoryResponse:
        """Recall memories."""
        memories = await self._memory.recall(
            channel=channel,
            query=query,
            user_id=user_id,
            limit=limit,
        )
        return MemoryResponse(
            success=True,
            memories=memories,
            count=len(memories),
        )
    
    async def get_status(self) -> StatusResponse:
        """Get service status."""
        return StatusResponse(
            healthy=self._provider.healthy,
            provider=self._provider.name,
            model=self._provider.model,
            requests_today=self._requests_today,
            tokens_today=self._tokens_today,
            rate_limited=False,
        )
    
    # === NATS Handlers ===
    
    async def _handle_chat(self, msg) -> None:
        """Handle chat request from NATS."""
        data = json.loads(msg.data.decode())
        req = ChatRequest(**data)
        
        response = await self.chat(
            channel=req.channel,
            user=req.user,
            message=req.message,
            persona=req.persona,
        )
        
        await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_complete(self, msg) -> None:
        """Handle completion request."""
        data = json.loads(msg.data.decode())
        req = CompletionRequest(**data)
        
        response = await self.complete(
            messages=req.messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        
        await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_summarize(self, msg) -> None:
        """Handle summarization request."""
        data = json.loads(msg.data.decode())
        req = SummarizeRequest(**data)
        
        response = await self.summarize(
            text=req.text,
            max_length=req.max_length,
            style=req.style,
        )
        
        await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_memory_add(self, msg) -> None:
        """Handle memory add request."""
        data = json.loads(msg.data.decode())
        req = MemoryAddRequest(**data)
        
        response = await self.add_memory(
            channel=req.channel,
            content=req.content,
            category=req.category,
            user_id=req.user_id,
            importance=req.importance,
        )
        
        await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_memory_recall(self, msg) -> None:
        """Handle memory recall request."""
        data = json.loads(msg.data.decode())
        req = MemoryRecallRequest(**data)
        
        response = await self.recall_memories(
            channel=req.channel,
            query=req.query,
            user_id=req.user_id,
            limit=req.limit,
        )
        
        await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_status(self, msg) -> None:
        """Handle status request."""
        status = await self.get_status()
        await msg.respond(json.dumps(asdict(status)).encode())
    
    async def _handle_usage(self, msg) -> None:
        """Handle usage request."""
        usage = {
            "requests_today": self._requests_today,
            "tokens_today": self._tokens_today,
            "provider": self._provider.name,
        }
        await msg.respond(json.dumps(usage).encode())
    
    # === Event Publishing ===
    
    async def _publish_response_event(
        self, channel, user, prompt_len, response_len, tokens, provider, latency
    ) -> None:
        """Publish response event."""
        event = LLMResponseEvent(
            channel=channel,
            user=user,
            prompt_length=prompt_len,
            response_length=response_len,
            tokens_used=tokens,
            provider=provider,
            latency_ms=latency,
        )
        await self._nc.publish(
            "rosey.event.llm.response",
            json.dumps(asdict(event)).encode()
        )
    
    async def _publish_error_event(self, channel, user, error) -> None:
        """Publish error event."""
        event = LLMErrorEvent(
            channel=channel,
            user=user,
            error=error,
            provider=self._provider.name,
        )
        await self._nc.publish(
            "rosey.event.llm.error",
            json.dumps(asdict(event)).encode()
        )
    
    def _get_persona_prompt(self, persona: Optional[str]) -> str:
        """Get system prompt for persona."""
        # Persona prompts would be loaded from config
        return "You are Rosey, a friendly and helpful chat assistant."
```

### 2.6 Rate Limiter

```python
# plugins/llm/rate_limiter.py

import time
from dataclasses import dataclass
from typing import Dict, Optional
from collections import defaultdict


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 10
    requests_per_hour: int = 100
    requests_per_day: int = 500
    tokens_per_day: int = 50000
    
    # Cooldown settings
    cooldown_seconds: int = 60


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit_type: str, retry_after: int):
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded ({limit_type}). "
            f"Retry after {retry_after} seconds."
        )


class RateLimiter:
    """
    Rate limiting for LLM requests.
    
    Limits:
    - Per user per minute/hour/day
    - Per channel per hour
    - Global daily token limit
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        
        # Tracking: user -> list of timestamps
        self._user_requests: Dict[str, list] = defaultdict(list)
        
        # Channel tracking
        self._channel_requests: Dict[str, list] = defaultdict(list)
        
        # Token tracking
        self._user_tokens: Dict[str, int] = defaultdict(int)
        self._daily_tokens = 0
        self._last_reset = time.time()
    
    async def check(self, user: str, channel: str) -> None:
        """
        Check if request is allowed.
        
        Raises:
            RateLimitExceeded: If any limit is exceeded
        """
        now = time.time()
        
        # Reset daily counters if needed
        if now - self._last_reset > 86400:
            self._daily_tokens = 0
            self._user_tokens.clear()
            self._last_reset = now
        
        # Clean old timestamps
        self._cleanup_old(user, channel, now)
        
        # Check per-minute limit
        minute_ago = now - 60
        minute_requests = sum(
            1 for t in self._user_requests[user] if t > minute_ago
        )
        if minute_requests >= self.config.requests_per_minute:
            raise RateLimitExceeded("per-minute", 60)
        
        # Check per-hour limit
        hour_ago = now - 3600
        hour_requests = sum(
            1 for t in self._user_requests[user] if t > hour_ago
        )
        if hour_requests >= self.config.requests_per_hour:
            raise RateLimitExceeded("per-hour", 3600 - int(now - self._user_requests[user][0]))
        
        # Check daily limit
        if len(self._user_requests[user]) >= self.config.requests_per_day:
            raise RateLimitExceeded("per-day", 86400)
        
        # Record request
        self._user_requests[user].append(now)
        self._channel_requests[channel].append(now)
    
    async def record_tokens(self, user: str, tokens: int) -> None:
        """Record token usage."""
        self._user_tokens[user] += tokens
        self._daily_tokens += tokens
        
        # Check if threshold reached (for alerts)
        if self._user_tokens[user] >= self.config.tokens_per_day * 0.8:
            # Could publish event here
            pass
    
    def get_remaining(self, user: str) -> dict:
        """Get remaining limits for user."""
        now = time.time()
        
        minute_ago = now - 60
        hour_ago = now - 3600
        
        minute_used = sum(
            1 for t in self._user_requests[user] if t > minute_ago
        )
        hour_used = sum(
            1 for t in self._user_requests[user] if t > hour_ago
        )
        day_used = len(self._user_requests[user])
        
        return {
            "minute": self.config.requests_per_minute - minute_used,
            "hour": self.config.requests_per_hour - hour_used,
            "day": self.config.requests_per_day - day_used,
            "tokens": self.config.tokens_per_day - self._user_tokens[user],
        }
    
    def _cleanup_old(self, user: str, channel: str, now: float) -> None:
        """Remove old timestamps."""
        day_ago = now - 86400
        
        self._user_requests[user] = [
            t for t in self._user_requests[user] if t > day_ago
        ]
        self._channel_requests[channel] = [
            t for t in self._channel_requests[channel] if t > day_ago
        ]
```

---

## 3. Implementation Steps

### Step 1: Create Schemas (30 minutes)

1. Create `plugins/llm/schemas.py`
2. Define all request/response dataclasses
3. Define event dataclasses

### Step 2: Implement Rate Limiter (1 hour)

1. Create `plugins/llm/rate_limiter.py`
2. Implement `RateLimiter` class
3. Write tests for all limit types
4. Test edge cases (reset, cleanup)

### Step 3: Implement LLMService (2 hours)

1. Create `plugins/llm/service.py`
2. Implement public API methods
3. Implement NATS handlers
4. Implement event publishing
5. Write comprehensive tests

### Step 4: Integrate with Plugin (1 hour)

1. Initialize service in plugin setup
2. Wire rate limiter
3. Test full integration

### Step 5: Testing (1 hour)

1. Test service API
2. Test NATS communication
3. Test rate limiting
4. Test events

---

## 4. Test Cases

### 4.1 Service Tests

```python
# tests/test_service.py

import pytest
from plugins.llm.service import LLMService
from plugins.llm.schemas import ChatResponse


@pytest.mark.asyncio
async def test_chat_returns_response(mock_provider, mock_memory, mock_nats):
    """Test basic chat functionality."""
    mock_provider.complete.return_value = MockResult("Hello!", tokens_used=10)
    
    service = LLMService(mock_provider, mock_memory, mock_nats)
    
    response = await service.chat(
        channel="#test",
        user="alice",
        message="Hi there!",
    )
    
    assert response.success is True
    assert response.content == "Hello!"
    assert response.tokens_used == 10


@pytest.mark.asyncio
async def test_rate_limit_enforced(mock_provider, mock_memory, mock_nats):
    """Test rate limiting works."""
    service = LLMService(
        mock_provider, mock_memory, mock_nats,
        rate_limiter=RateLimiter(RateLimitConfig(requests_per_minute=2))
    )
    
    # First two should succeed
    await service.chat("#test", "alice", "Hi 1")
    await service.chat("#test", "alice", "Hi 2")
    
    # Third should fail
    response = await service.chat("#test", "alice", "Hi 3")
    
    assert response.success is False
    assert "rate limit" in response.error.lower()
```

### 4.2 Rate Limiter Tests

```python
@pytest.mark.asyncio
async def test_per_minute_limit():
    """Test per-minute rate limiting."""
    limiter = RateLimiter(RateLimitConfig(requests_per_minute=3))
    
    # First 3 should pass
    for i in range(3):
        await limiter.check("alice", "#test")
    
    # 4th should fail
    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check("alice", "#test")
    
    assert exc.value.limit_type == "per-minute"


@pytest.mark.asyncio  
async def test_different_users_have_separate_limits():
    """Test users don't share limits."""
    limiter = RateLimiter(RateLimitConfig(requests_per_minute=2))
    
    await limiter.check("alice", "#test")
    await limiter.check("alice", "#test")
    
    # Alice is rate limited
    with pytest.raises(RateLimitExceeded):
        await limiter.check("alice", "#test")
    
    # Bob is not
    await limiter.check("bob", "#test")  # Should pass
```

---

## 5. Usage by Other Plugins

### 5.1 From Trivia Plugin

```python
# plugins/trivia/plugin.py

async def _get_hint_from_llm(self, question: str, answer: str) -> str:
    """Get a creative hint from LLM."""
    response = await self._nc.request(
        "rosey.llm.chat",
        json.dumps({
            "channel": self._channel,
            "user": "trivia-bot",
            "message": f"Give a clever hint for this trivia question without giving away the answer.\nQuestion: {question}\nAnswer: {answer}",
        }).encode(),
        timeout=5.0
    )
    
    data = json.loads(response.data.decode())
    if data["success"]:
        return data["content"]
    return "No hint available"
```

### 5.2 From Inspector Plugin

```python
# plugins/inspector/plugin.py

async def _explain_event(self, event_type: str, event_data: dict) -> str:
    """Get LLM explanation of an event."""
    response = await self._nc.request(
        "rosey.llm.summarize",
        json.dumps({
            "text": f"Event: {event_type}\nData: {json.dumps(event_data)}",
            "max_length": 100,
            "style": "concise",
        }).encode(),
        timeout=5.0
    )
    
    data = json.loads(response.data.decode())
    return data.get("summary", "No explanation available")
```

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] LLMService exposes chat/complete/summarize API
- [ ] Other plugins can request LLM via NATS
- [ ] Rate limiting enforced per user
- [ ] Events published for LLM activity
- [ ] Usage tracking works

### 6.2 Technical

- [ ] All NATS handlers work correctly
- [ ] Rate limiter handles edge cases
- [ ] Events conform to schema
- [ ] Test coverage > 85%

---

**Commit Message Template:**
```
feat(plugins): Add LLM service and events

- Add LLMService for inter-plugin communication
- Add NATS request/response interface
- Add rate limiting per user/channel
- Add event publishing for LLM activity
- Add usage tracking

Implements: SPEC-Sortie-6-LLMService.md
Related: PRD-Core-Migrations.md
Part: 3 of 3 (LLM Migration)
```
