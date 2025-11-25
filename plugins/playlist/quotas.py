"""
User quota and rate limiting for playlist.

Enforces:
- Maximum items per user
- Maximum total duration per user
- Rate limiting (adds per time window)
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class QuotaConfig:
    """Configuration for user quotas."""
    max_items_per_user: int = 5
    max_duration_per_user: int = 1800  # 30 minutes
    rate_limit_count: int = 3
    rate_limit_window: int = 10  # seconds


@dataclass
class RateLimitTracker:
    """Tracks recent adds for rate limiting."""
    adds: List[datetime] = field(default_factory=list)
    
    def add(self, timestamp: datetime) -> None:
        """Record an add at timestamp."""
        self.adds.append(timestamp)
    
    def count_recent(self, window_seconds: int) -> int:
        """Count adds within window."""
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        self.adds = [ts for ts in self.adds if ts > cutoff]
        return len(self.adds)


class QuotaManager:
    """
    Manages user quotas and rate limiting.
    
    Enforces:
    - Max items per user in queue
    - Max total duration per user
    - Rate limiting (max adds per time window)
    
    Example:
        manager = QuotaManager(config)
        
        # Check before add
        result = manager.check_quota(channel, user, queue_items, item_duration)
        if not result["allowed"]:
            return f"Quota exceeded: {result['reason']}"
        
        # Record successful add
        manager.record_add(channel, user, timestamp)
    """
    
    def __init__(self, config: Optional[QuotaConfig] = None):
        """
        Initialize quota manager.
        
        Args:
            config: QuotaConfig instance or None for defaults
        """
        self.config = config or QuotaConfig()
        # Per-channel rate limit trackers: {channel: {user: RateLimitTracker}}
        self._rate_trackers: Dict[str, Dict[str, RateLimitTracker]] = {}
    
    def check_quota(
        self,
        channel: str,
        user: str,
        queue_items: list,
        item_duration: int = 0
    ) -> Dict[str, any]:
        """
        Check if user can add an item.
        
        Args:
            channel: Channel name
            user: Username
            queue_items: Current queue items (list of PlaylistItem)
            item_duration: Duration of item being added (seconds)
        
        Returns:
            Dict with keys:
            - allowed: bool
            - reason: str (if not allowed)
            - user_items: int (current count)
            - user_duration: int (current total seconds)
            - rate_limit_remaining: int (adds remaining in window)
        """
        # Count user's current items and duration
        user_items = [item for item in queue_items if item.added_by == user]
        user_count = len(user_items)
        user_duration = sum(item.duration for item in user_items)
        
        # Check item count
        if user_count >= self.config.max_items_per_user:
            return {
                "allowed": False,
                "reason": f"You have {user_count} items in queue (max {self.config.max_items_per_user})",
                "user_items": user_count,
                "user_duration": user_duration,
            }
        
        # Check total duration
        new_duration = user_duration + item_duration
        if new_duration > self.config.max_duration_per_user:
            minutes = self.config.max_duration_per_user // 60
            return {
                "allowed": False,
                "reason": f"Adding would exceed {minutes} minute limit ({new_duration}s total)",
                "user_items": user_count,
                "user_duration": user_duration,
            }
        
        # Check rate limit
        rate_check = self._check_rate_limit(channel, user)
        if not rate_check["allowed"]:
            return {
                "allowed": False,
                "reason": rate_check["reason"],
                "user_items": user_count,
                "user_duration": user_duration,
                "rate_limit_remaining": 0,
            }
        
        # All checks passed
        return {
            "allowed": True,
            "user_items": user_count,
            "user_duration": user_duration,
            "rate_limit_remaining": rate_check["remaining"],
        }
    
    def record_add(
        self,
        channel: str,
        user: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record successful add for rate limiting.
        
        Args:
            channel: Channel name
            user: Username
            timestamp: Add time or None for now
        """
        timestamp = timestamp or datetime.utcnow()
        
        if channel not in self._rate_trackers:
            self._rate_trackers[channel] = {}
        
        if user not in self._rate_trackers[channel]:
            self._rate_trackers[channel][user] = RateLimitTracker()
        
        self._rate_trackers[channel][user].add(timestamp)
        logger.debug(f"Recorded add for {user} in {channel}")
    
    def _check_rate_limit(self, channel: str, user: str) -> Dict[str, any]:
        """
        Check rate limit for user.
        
        Args:
            channel: Channel name
            user: Username
        
        Returns:
            Dict with keys: allowed, reason (if not allowed), remaining
        """
        if channel not in self._rate_trackers:
            self._rate_trackers[channel] = {}
        
        if user not in self._rate_trackers[channel]:
            return {
                "allowed": True,
                "remaining": self.config.rate_limit_count,
            }
        
        tracker = self._rate_trackers[channel][user]
        recent_count = tracker.count_recent(self.config.rate_limit_window)
        
        if recent_count >= self.config.rate_limit_count:
            return {
                "allowed": False,
                "reason": f"Rate limit: max {self.config.rate_limit_count} adds per {self.config.rate_limit_window} seconds",
                "remaining": 0,
            }
        
        return {
            "allowed": True,
            "remaining": self.config.rate_limit_count - recent_count,
        }
    
    def get_user_quota_info(
        self,
        channel: str,
        user: str,
        queue_items: list
    ) -> Dict[str, any]:
        """
        Get quota information for user.
        
        Args:
            channel: Channel name
            user: Username
            queue_items: Current queue items
        
        Returns:
            Dict with quota status: items_used, items_max, duration_used,
            duration_max, rate_limit_remaining
        """
        user_items = [item for item in queue_items if item.added_by == user]
        user_count = len(user_items)
        user_duration = sum(item.duration for item in user_items)
        
        rate_check = self._check_rate_limit(channel, user)
        
        return {
            "items_used": user_count,
            "items_max": self.config.max_items_per_user,
            "duration_used": user_duration,
            "duration_max": self.config.max_duration_per_user,
            "rate_limit_remaining": rate_check.get("remaining", 0),
        }
    
    def clear_channel(self, channel: str) -> None:
        """
        Clear rate limit trackers for channel.
        
        Args:
            channel: Channel name
        """
        if channel in self._rate_trackers:
            del self._rate_trackers[channel]
            logger.debug(f"Cleared rate trackers for {channel}")
