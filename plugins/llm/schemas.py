"""
LLM Service Schemas
===================

Request, response, and event schemas for the LLM service.
Used for NATS communication between plugins.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# ============================================================================
# Service Requests
# ============================================================================


@dataclass
class ChatRequest:
    """Request for simple chat with context and memory."""
    channel: str
    user: str
    message: str
    persona: Optional[str] = None  # Override default persona


@dataclass
class CompletionRequest:
    """Request for raw completion without memory/context."""
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
    category: str = "fact"  # fact, preference, topic
    user_id: Optional[str] = None
    importance: int = 1  # 1-5


@dataclass
class MemoryRecallRequest:
    """Request to recall memories."""
    channel: str
    query: str
    user_id: Optional[str] = None
    limit: int = 5


@dataclass
class PersonaGetRequest:
    """Request to get current persona for channel."""
    channel: str


@dataclass
class PersonaSetRequest:
    """Request to set persona for channel."""
    channel: str
    persona: str


@dataclass
class StatusRequest:
    """Request for LLM service status."""
    pass


@dataclass
class UsageRequest:
    """Request for usage statistics."""
    user: Optional[str] = None  # Specific user or global


# ============================================================================
# Service Responses
# ============================================================================


@dataclass
class ChatResponse:
    """Response from chat."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    provider: Optional[str] = None


@dataclass
class CompletionResponse:
    """Response from raw completion."""
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
    memories: Optional[List[str]] = None
    count: int = 0
    memory_id: Optional[str] = None  # For add operations
    error: Optional[str] = None


@dataclass
class PersonaResponse:
    """Response from persona operations."""
    success: bool
    persona: Optional[str] = None
    available: Optional[List[str]] = None
    error: Optional[str] = None


@dataclass
class StatusResponse:
    """LLM service status response."""
    healthy: bool
    provider: str
    model: str
    requests_today: int
    tokens_today: int
    rate_limited: bool = False
    uptime_seconds: int = 0


@dataclass
class UsageResponse:
    """Usage statistics response."""
    user: Optional[str]
    requests_today: int
    tokens_today: int
    rate_limits_remaining: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# Events
# ============================================================================


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
    persona: Optional[str] = None


@dataclass
class LLMErrorEvent:
    """Published when LLM request fails."""
    channel: str
    user: str
    error: str
    provider: str
    error_type: str = "provider_error"  # provider_error, rate_limit, validation


@dataclass
class LLMMemoryEvent:
    """Published when memory is added/recalled."""
    channel: str
    action: str  # add, recall
    user_id: Optional[str]
    memory_count: int


@dataclass
class LLMSummarizedEvent:
    """Published when conversation is summarized."""
    channel: str
    message_count: int
    summary_length: int


@dataclass
class UsageThresholdEvent:
    """Published when usage threshold reached."""
    user: str
    channel: str
    threshold_type: str  # minute, hour, day, tokens
    current: int
    limit: int
    percentage: float  # Percentage of limit used


# ============================================================================
# Helper Functions
# ============================================================================


def chat_request_from_dict(data: Dict[str, Any]) -> ChatRequest:
    """Create ChatRequest from dictionary."""
    return ChatRequest(**data)


def completion_request_from_dict(data: Dict[str, Any]) -> CompletionRequest:
    """Create CompletionRequest from dictionary."""
    return CompletionRequest(**data)


def summarize_request_from_dict(data: Dict[str, Any]) -> SummarizeRequest:
    """Create SummarizeRequest from dictionary."""
    return SummarizeRequest(**data)


def memory_add_request_from_dict(data: Dict[str, Any]) -> MemoryAddRequest:
    """Create MemoryAddRequest from dictionary."""
    return MemoryAddRequest(**data)


def memory_recall_request_from_dict(data: Dict[str, Any]) -> MemoryRecallRequest:
    """Create MemoryRecallRequest from dictionary."""
    return MemoryRecallRequest(**data)
