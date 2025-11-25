"""
LLM Service NATS Interface
===========================

NATS request/response handlers for inter-plugin LLM communication.
Wraps the core LLMService with rate limiting and event publishing.
"""

import json
import logging
import time
from dataclasses import asdict
from typing import Optional, List, Dict, Any

from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from .service import LLMService
from .rate_limiter import RateLimiter
from .events import EventPublisher
from .memory import ConversationMemory
from .schemas import (
    ChatRequest,
    ChatResponse,
    CompletionRequest,
    CompletionResponse,
    SummarizeRequest,
    SummaryResponse,
    MemoryAddRequest,
    MemoryRecallRequest,
    MemoryResponse,
    StatusRequest,
    StatusResponse,
    UsageRequest,
    UsageResponse,
)
from .providers import Message, ProviderError

logger = logging.getLogger(__name__)


class LLMServiceNATS:
    """
    NATS-enabled LLM service for inter-plugin communication.
    
    Provides request/response endpoints on NATS subjects:
    - rosey.llm.chat - Chat with context and memory
    - rosey.llm.complete - Raw completion without memory
    - rosey.llm.summarize - Text summarization
    - rosey.llm.memory.add - Add memory
    - rosey.llm.memory.recall - Recall memories
    - rosey.llm.status - Service status
    - rosey.llm.usage - Usage statistics
    
    Publishes events to rosey.event.llm.* subjects for observability.
    """
    
    def __init__(
        self,
        nc: NATSClient,
        service: LLMService,
        memory: ConversationMemory,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize NATS service interface.
        
        Args:
            nc: NATS client
            service: Core LLM service
            memory: Conversation memory
            rate_limiter: Rate limiter (creates default if None)
        """
        self._nc = nc
        self._service = service
        self._memory = memory
        self._rate_limiter = rate_limiter or RateLimiter()
        self._events = EventPublisher(nc)
        
        # Usage tracking
        self._requests_today = 0
        self._tokens_today = 0
        self._start_time = time.time()
        
        logger.info("LLM NATS service initialized")
    
    async def start(self) -> None:
        """Subscribe to all NATS subjects."""
        await self._nc.subscribe("rosey.llm.chat", cb=self._handle_chat)
        await self._nc.subscribe("rosey.llm.complete", cb=self._handle_complete)
        await self._nc.subscribe("rosey.llm.summarize", cb=self._handle_summarize)
        await self._nc.subscribe("rosey.llm.memory.add", cb=self._handle_memory_add)
        await self._nc.subscribe("rosey.llm.memory.recall", cb=self._handle_memory_recall)
        await self._nc.subscribe("rosey.llm.status", cb=self._handle_status)
        await self._nc.subscribe("rosey.llm.usage", cb=self._handle_usage)
        
        logger.info("LLM NATS service started, subscribed to 7 subjects")
    
    async def stop(self) -> None:
        """Cleanup (placeholder for future needs)."""
        logger.info("LLM NATS service stopped")
    
    # ========================================================================
    # NATS Request Handlers
    # ========================================================================
    
    async def _handle_chat(self, msg: Msg) -> None:
        """Handle chat request."""
        start_time = time.monotonic()
        
        try:
            # Parse request
            data = json.loads(msg.data.decode())
            req = ChatRequest(**data)
            
            # Check rate limit
            allowed, reason = await self._rate_limiter.check(req.user)
            if not allowed:
                response = ChatResponse(
                    success=False,
                    error=reason,
                )
                await msg.respond(json.dumps(asdict(response)).encode())
                await self._events.publish_error(
                    channel=req.channel,
                    user=req.user,
                    error=reason or "Rate limit exceeded",
                    provider=self._service.provider.__class__.__name__,
                    error_type="rate_limit",
                )
                return
            
            # Get chat response
            response_text = await self._service.chat(
                user_message=req.message,
                channel_id=req.channel,
                username=req.user,
            )
            
            # Track usage
            tokens_used = 0  # TODO: Get from provider response
            await self._rate_limiter.record(req.user, tokens_used)
            self._requests_today += 1
            self._tokens_today += tokens_used
            
            # Build response
            response = ChatResponse(
                success=True,
                content=response_text,
                tokens_used=tokens_used,
                provider=self._service.provider.__class__.__name__,
            )
            
            # Publish event
            latency_ms = int((time.monotonic() - start_time) * 1000)
            await self._events.publish_response(
                channel=req.channel,
                user=req.user,
                prompt_length=len(req.message),
                response_length=len(response_text),
                tokens_used=tokens_used,
                provider=self._service.provider.__class__.__name__,
                latency_ms=latency_ms,
                persona=req.persona,
            )
            
            # Check thresholds
            await self._check_usage_thresholds(req.user, req.channel)
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling chat request: {e}", exc_info=True)
            response = ChatResponse(success=False, error=str(e))
            await msg.respond(json.dumps(asdict(response)).encode())
            
            # Try to publish error event
            try:
                data = json.loads(msg.data.decode())
                await self._events.publish_error(
                    channel=data.get("channel", "unknown"),
                    user=data.get("user", "unknown"),
                    error=str(e),
                    provider=self._service.provider.__class__.__name__,
                    error_type="provider_error",
                )
            except:
                pass
    
    async def _handle_complete(self, msg: Msg) -> None:
        """Handle raw completion request."""
        try:
            data = json.loads(msg.data.decode())
            req = CompletionRequest(**data)
            
            # Build messages for provider
            prompt_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in req.messages
            )
            
            # Get completion
            response_text = await self._service.complete_raw(
                prompt=prompt_text,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            
            response = CompletionResponse(
                success=True,
                content=response_text,
                tokens_used=0,  # TODO: Track tokens
                provider=self._service.provider.__class__.__name__,
            )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling completion request: {e}", exc_info=True)
            response = CompletionResponse(success=False, error=str(e))
            await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_summarize(self, msg: Msg) -> None:
        """Handle summarization request."""
        try:
            data = json.loads(msg.data.decode())
            req = SummarizeRequest(**data)
            
            # Build summarization prompt
            prompts = {
                "concise": f"Summarize in {req.max_length} words or less:\n\n{req.text}",
                "detailed": f"Provide a detailed summary:\n\n{req.text}",
                "bullets": f"Summarize as bullet points:\n\n{req.text}",
            }
            
            prompt = prompts.get(req.style, prompts["concise"])
            
            # Get summary
            summary = await self._service.complete_raw(
                prompt=prompt,
                temperature=0.3,
            )
            
            response = SummaryResponse(
                success=True,
                summary=summary,
            )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling summarize request: {e}", exc_info=True)
            response = SummaryResponse(success=False, error=str(e))
            await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_memory_add(self, msg: Msg) -> None:
        """Handle memory add request."""
        try:
            data = json.loads(msg.data.decode())
            req = MemoryAddRequest(**data)
            
            # Add memory
            memory_id = await self._memory.remember(
                channel=req.channel,
                content=req.content,
                category=req.category,
                user_id=req.user_id,
                importance=req.importance,
            )
            
            response = MemoryResponse(
                success=True,
                count=1,
                memory_id=memory_id,
            )
            
            # Publish event
            await self._events.publish_memory(
                channel=req.channel,
                action="add",
                user_id=req.user_id,
                memory_count=1,
            )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling memory add: {e}", exc_info=True)
            response = MemoryResponse(success=False, error=str(e))
            await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_memory_recall(self, msg: Msg) -> None:
        """Handle memory recall request."""
        try:
            data = json.loads(msg.data.decode())
            req = MemoryRecallRequest(**data)
            
            # Recall memories
            memories = await self._memory.recall(
                channel=req.channel,
                query=req.query,
                user_id=req.user_id,
                limit=req.limit,
            )
            
            response = MemoryResponse(
                success=True,
                memories=memories,
                count=len(memories),
            )
            
            # Publish event
            await self._events.publish_memory(
                channel=req.channel,
                action="recall",
                user_id=req.user_id,
                memory_count=len(memories),
            )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling memory recall: {e}", exc_info=True)
            response = MemoryResponse(success=False, error=str(e))
            await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_status(self, msg: Msg) -> None:
        """Handle status request."""
        try:
            uptime = int(time.time() - self._start_time)
            
            response = StatusResponse(
                healthy=True,
                provider=self._service.provider.__class__.__name__,
                model=self._service.provider.config.get("default_model", "unknown"),
                requests_today=self._requests_today,
                tokens_today=self._tokens_today,
                rate_limited=False,
                uptime_seconds=uptime,
            )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling status request: {e}", exc_info=True)
            response = StatusResponse(
                healthy=False,
                provider="unknown",
                model="unknown",
                requests_today=0,
                tokens_today=0,
            )
            await msg.respond(json.dumps(asdict(response)).encode())
    
    async def _handle_usage(self, msg: Msg) -> None:
        """Handle usage request."""
        try:
            data = json.loads(msg.data.decode())
            req = UsageRequest(**data)
            
            if req.user:
                # Get user-specific usage
                remaining = await self._rate_limiter.get_remaining(req.user)
                usage = await self._rate_limiter.get_usage(req.user)
                
                response = UsageResponse(
                    user=req.user,
                    requests_today=usage["requests_day"],
                    tokens_today=usage["tokens_day"],
                    rate_limits_remaining=remaining,
                )
            else:
                # Get global usage
                stats = await self._rate_limiter.get_global_stats()
                
                response = UsageResponse(
                    user=None,
                    requests_today=stats["total_requests_day"],
                    tokens_today=stats["total_tokens_day"],
                )
            
            await msg.respond(json.dumps(asdict(response)).encode())
            
        except Exception as e:
            logger.error(f"Error handling usage request: {e}", exc_info=True)
            response = UsageResponse(
                user=None,
                requests_today=0,
                tokens_today=0,
            )
            await msg.respond(json.dumps(asdict(response)).encode())
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _check_usage_thresholds(self, user: str, channel: str) -> None:
        """Check if user has exceeded usage thresholds and publish events."""
        threshold = await self._rate_limiter.check_threshold(user, 0.8)
        
        if threshold:
            window_type, current, limit = threshold
            percentage = (current / limit) if limit > 0 else 0.0
            
            await self._events.publish_usage_threshold(
                user=user,
                channel=channel,
                threshold_type=window_type,
                current=current,
                limit=limit,
                percentage=percentage,
            )
