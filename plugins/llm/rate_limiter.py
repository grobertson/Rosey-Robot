"""
LLM Rate Limiter
================

Per-user and per-channel rate limiting for LLM service.
Tracks requests and token usage across multiple time windows.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 10
    requests_per_hour: int = 100
    requests_per_day: int = 500
    tokens_per_day: int = 50_000


@dataclass
class UsageWindow:
    """Track usage within a time window."""
    count: int = 0
    tokens: int = 0
    reset_at: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        """Check if window has expired."""
        return datetime.now() >= self.reset_at
    
    def reset(self, duration: timedelta) -> None:
        """Reset the window."""
        self.count = 0
        self.tokens = 0
        self.reset_at = datetime.now() + duration


@dataclass
class UserUsage:
    """Track usage for a single user."""
    user: str
    minute: UsageWindow = field(default_factory=UsageWindow)
    hour: UsageWindow = field(default_factory=UsageWindow)
    day: UsageWindow = field(default_factory=UsageWindow)
    
    def __post_init__(self):
        """Initialize time windows."""
        self.minute.reset_at = datetime.now() + timedelta(minutes=1)
        self.hour.reset_at = datetime.now() + timedelta(hours=1)
        self.day.reset_at = datetime.now() + timedelta(days=1)


class RateLimiter:
    """
    Rate limiter for LLM service.
    
    Tracks per-user usage across minute, hour, and day windows.
    Automatically resets expired windows.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            config: Rate limit configuration (uses defaults if None)
        """
        self._config = config or RateLimitConfig()
        self._usage: Dict[str, UserUsage] = {}
        self._lock = asyncio.Lock()
        
        logger.info(
            f"RateLimiter initialized: "
            f"{self._config.requests_per_minute}/min, "
            f"{self._config.requests_per_hour}/hr, "
            f"{self._config.requests_per_day}/day, "
            f"{self._config.tokens_per_day} tokens/day"
        )
    
    async def check(self, user: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limits.
        
        Args:
            user: Username to check
            
        Returns:
            Tuple of (allowed, reason). If not allowed, reason explains why.
        """
        async with self._lock:
            usage = self._get_or_create_usage(user)
            self._reset_expired_windows(usage)
            
            # Check minute limit
            if usage.minute.count >= self._config.requests_per_minute:
                seconds_left = (usage.minute.reset_at - datetime.now()).total_seconds()
                return False, f"Rate limit: {self._config.requests_per_minute} requests/minute (resets in {int(seconds_left)}s)"
            
            # Check hour limit
            if usage.hour.count >= self._config.requests_per_hour:
                minutes_left = (usage.hour.reset_at - datetime.now()).total_seconds() / 60
                return False, f"Rate limit: {self._config.requests_per_hour} requests/hour (resets in {int(minutes_left)} minutes)"
            
            # Check day limit (requests)
            if usage.day.count >= self._config.requests_per_day:
                hours_left = (usage.day.reset_at - datetime.now()).total_seconds() / 3600
                return False, f"Rate limit: {self._config.requests_per_day} requests/day (resets in {int(hours_left)} hours)"
            
            # Check day limit (tokens)
            if usage.day.tokens >= self._config.tokens_per_day:
                hours_left = (usage.day.reset_at - datetime.now()).total_seconds() / 3600
                return False, f"Token limit: {self._config.tokens_per_day} tokens/day (resets in {int(hours_left)} hours)"
            
            return True, None
    
    async def record(self, user: str, tokens_used: int = 0) -> None:
        """
        Record a request for a user.
        
        Args:
            user: Username
            tokens_used: Number of tokens used in this request
        """
        async with self._lock:
            usage = self._get_or_create_usage(user)
            self._reset_expired_windows(usage)
            
            # Increment all windows
            usage.minute.count += 1
            usage.hour.count += 1
            usage.day.count += 1
            
            # Track tokens in day window
            usage.day.tokens += tokens_used
            
            logger.debug(
                f"Recorded usage for {user}: "
                f"{usage.minute.count}/{self._config.requests_per_minute} (minute), "
                f"{usage.hour.count}/{self._config.requests_per_hour} (hour), "
                f"{usage.day.count}/{self._config.requests_per_day} (day), "
                f"{usage.day.tokens}/{self._config.tokens_per_day} tokens"
            )
    
    async def get_usage(self, user: str) -> Dict[str, int]:
        """
        Get current usage statistics for a user.
        
        Args:
            user: Username
            
        Returns:
            Dictionary with usage counts and limits
        """
        async with self._lock:
            usage = self._get_or_create_usage(user)
            self._reset_expired_windows(usage)
            
            return {
                "requests_minute": usage.minute.count,
                "requests_hour": usage.hour.count,
                "requests_day": usage.day.count,
                "tokens_day": usage.day.tokens,
                "limit_minute": self._config.requests_per_minute,
                "limit_hour": self._config.requests_per_hour,
                "limit_day": self._config.requests_per_day,
                "limit_tokens_day": self._config.tokens_per_day,
            }
    
    async def get_remaining(self, user: str) -> Dict[str, int]:
        """
        Get remaining capacity for a user.
        
        Args:
            user: Username
            
        Returns:
            Dictionary with remaining requests/tokens
        """
        stats = await self.get_usage(user)
        
        return {
            "requests_minute": stats["limit_minute"] - stats["requests_minute"],
            "requests_hour": stats["limit_hour"] - stats["requests_hour"],
            "requests_day": stats["limit_day"] - stats["requests_day"],
            "tokens_day": stats["limit_tokens_day"] - stats["tokens_day"],
        }
    
    async def reset_user(self, user: str) -> None:
        """
        Reset all usage tracking for a user.
        
        Args:
            user: Username to reset
        """
        async with self._lock:
            if user in self._usage:
                del self._usage[user]
                logger.info(f"Reset rate limits for user: {user}")
    
    async def check_threshold(
        self, 
        user: str,
        threshold_percentage: float = 0.8
    ) -> Optional[Tuple[str, int, int]]:
        """
        Check if user has exceeded usage threshold.
        
        Args:
            user: Username
            threshold_percentage: Percentage threshold (0.0-1.0)
            
        Returns:
            Tuple of (window_type, current, limit) if threshold exceeded, else None
        """
        stats = await self.get_usage(user)
        
        # Check each window
        windows = [
            ("minute", stats["requests_minute"], stats["limit_minute"]),
            ("hour", stats["requests_hour"], stats["limit_hour"]),
            ("day", stats["requests_day"], stats["limit_day"]),
            ("tokens", stats["tokens_day"], stats["limit_tokens_day"]),
        ]
        
        for window_type, current, limit in windows:
            if limit > 0 and (current / limit) >= threshold_percentage:
                return (window_type, current, limit)
        
        return None
    
    def _get_or_create_usage(self, user: str) -> UserUsage:
        """Get or create usage tracking for a user."""
        if user not in self._usage:
            self._usage[user] = UserUsage(user=user)
        return self._usage[user]
    
    def _reset_expired_windows(self, usage: UserUsage) -> None:
        """Reset any expired time windows."""
        if usage.minute.is_expired():
            usage.minute.reset(timedelta(minutes=1))
        
        if usage.hour.is_expired():
            usage.hour.reset(timedelta(hours=1))
        
        if usage.day.is_expired():
            usage.day.reset(timedelta(days=1))
    
    async def get_global_stats(self) -> Dict[str, int]:
        """
        Get global statistics across all users.
        
        Returns:
            Dictionary with aggregate statistics
        """
        async with self._lock:
            total_users = len(self._usage)
            total_requests_day = sum(u.day.count for u in self._usage.values())
            total_tokens_day = sum(u.day.tokens for u in self._usage.values())
            
            return {
                "total_users": total_users,
                "total_requests_day": total_requests_day,
                "total_tokens_day": total_tokens_day,
            }
