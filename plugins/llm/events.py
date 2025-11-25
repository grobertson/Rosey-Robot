"""
LLM Events
==========

Event publishing utilities for LLM service observability.
"""

import json
import logging
from dataclasses import asdict
from typing import Optional

from nats.aio.client import Client as NATSClient

from .schemas import (
    LLMResponseEvent,
    LLMErrorEvent,
    LLMMemoryEvent,
    LLMSummarizedEvent,
    UsageThresholdEvent,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publish LLM events to NATS.
    
    All events are published to rosey.event.llm.* subjects for observability.
    Other plugins can subscribe to these events for monitoring, analytics, etc.
    """
    
    def __init__(self, nc: NATSClient):
        """
        Initialize event publisher.
        
        Args:
            nc: NATS client instance
        """
        self._nc = nc
    
    async def publish_response(
        self,
        channel: str,
        user: str,
        prompt_length: int,
        response_length: int,
        tokens_used: int,
        provider: str,
        latency_ms: int,
        persona: Optional[str] = None,
    ) -> None:
        """
        Publish LLM response event.
        
        Args:
            channel: Channel ID
            user: Username
            prompt_length: Length of prompt in characters
            response_length: Length of response in characters
            tokens_used: Tokens consumed
            provider: Provider name
            latency_ms: Response latency in milliseconds
            persona: Persona used (if any)
        """
        event = LLMResponseEvent(
            channel=channel,
            user=user,
            prompt_length=prompt_length,
            response_length=response_length,
            tokens_used=tokens_used,
            provider=provider,
            latency_ms=latency_ms,
            persona=persona,
        )
        
        try:
            await self._nc.publish(
                "rosey.event.llm.response",
                json.dumps(asdict(event)).encode(),
            )
            logger.debug(f"Published response event: {channel}/{user}")
        except Exception as e:
            logger.error(f"Failed to publish response event: {e}")
    
    async def publish_error(
        self,
        channel: str,
        user: str,
        error: str,
        provider: str,
        error_type: str = "provider_error",
    ) -> None:
        """
        Publish LLM error event.
        
        Args:
            channel: Channel ID
            user: Username
            error: Error message
            provider: Provider name
            error_type: Type of error (provider_error, rate_limit, validation)
        """
        event = LLMErrorEvent(
            channel=channel,
            user=user,
            error=error,
            provider=provider,
            error_type=error_type,
        )
        
        try:
            await self._nc.publish(
                "rosey.event.llm.error",
                json.dumps(asdict(event)).encode(),
            )
            logger.debug(f"Published error event: {channel}/{user}")
        except Exception as e:
            logger.error(f"Failed to publish error event: {e}")
    
    async def publish_memory(
        self,
        channel: str,
        action: str,
        user_id: Optional[str],
        memory_count: int,
    ) -> None:
        """
        Publish memory event.
        
        Args:
            channel: Channel ID
            action: Action performed (add, recall)
            user_id: User ID (if any)
            memory_count: Number of memories affected
        """
        event = LLMMemoryEvent(
            channel=channel,
            action=action,
            user_id=user_id,
            memory_count=memory_count,
        )
        
        try:
            await self._nc.publish(
                "rosey.event.llm.memory",
                json.dumps(asdict(event)).encode(),
            )
            logger.debug(f"Published memory event: {channel}/{action}")
        except Exception as e:
            logger.error(f"Failed to publish memory event: {e}")
    
    async def publish_summarized(
        self,
        channel: str,
        message_count: int,
        summary_length: int,
    ) -> None:
        """
        Publish summarization event.
        
        Args:
            channel: Channel ID
            message_count: Number of messages summarized
            summary_length: Length of summary in characters
        """
        event = LLMSummarizedEvent(
            channel=channel,
            message_count=message_count,
            summary_length=summary_length,
        )
        
        try:
            await self._nc.publish(
                "rosey.event.llm.summarized",
                json.dumps(asdict(event)).encode(),
            )
            logger.debug(f"Published summarized event: {channel}")
        except Exception as e:
            logger.error(f"Failed to publish summarized event: {e}")
    
    async def publish_usage_threshold(
        self,
        user: str,
        channel: str,
        threshold_type: str,
        current: int,
        limit: int,
        percentage: float,
    ) -> None:
        """
        Publish usage threshold event.
        
        Args:
            user: Username
            channel: Channel ID
            threshold_type: Type of threshold (minute, hour, day, tokens)
            current: Current usage
            limit: Usage limit
            percentage: Percentage of limit used
        """
        event = UsageThresholdEvent(
            user=user,
            channel=channel,
            threshold_type=threshold_type,
            current=current,
            limit=limit,
            percentage=percentage,
        )
        
        try:
            await self._nc.publish(
                "rosey.event.llm.usage_threshold",
                json.dumps(asdict(event)).encode(),
            )
            logger.info(
                f"Published usage threshold event: {user} - "
                f"{threshold_type} at {percentage:.0%}"
            )
        except Exception as e:
            logger.error(f"Failed to publish usage threshold event: {e}")
