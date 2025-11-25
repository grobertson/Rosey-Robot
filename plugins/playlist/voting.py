"""
Skip voting system for playlist.

Allows users to vote to skip the current item with configurable thresholds.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoteSession:
    """
    Active vote session for a channel.
    
    Tracks votes for skipping the current item.
    """
    channel: str
    item_id: str  # Item being voted on
    voters: Set[str] = field(default_factory=set)
    started_at: datetime = field(default_factory=lambda: datetime.utcnow())
    threshold: float = 0.5  # Percentage of active users needed


class SkipVoteManager:
    """
    Manage skip voting for playlist items.
    
    Features:
    - Threshold-based voting (e.g., 50% of active users)
    - Minimum vote requirement
    - Per-channel vote sessions
    - Automatic reset on item change
    - Vote timeout
    
    Example:
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        manager.set_active_users("lobby", {"user1", "user2", "user3"})
        
        result = manager.vote("lobby", "user1")
        # {"success": True, "votes": 1, "needed": 2, "passed": False}
        
        result = manager.vote("lobby", "user2")
        # {"success": True, "votes": 2, "needed": 2, "passed": True}
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        timeout_minutes: int = 5,
        min_votes: int = 2,
    ):
        """
        Initialize skip vote manager.
        
        Args:
            threshold: Percentage of active users needed (0.0-1.0)
            timeout_minutes: Minutes before votes expire
            min_votes: Minimum votes needed regardless of threshold
        """
        self.threshold = max(0.0, min(1.0, threshold))
        self.timeout = timedelta(minutes=timeout_minutes)
        self.min_votes = max(1, min_votes)
        self._sessions: Dict[str, VoteSession] = {}
        
        # Track active users per channel (for threshold calculation)
        self._active_users: Dict[str, Set[str]] = {}
    
    def vote(self, channel: str, user: str, item_id: Optional[str] = None) -> Dict:
        """
        Cast a skip vote.
        
        Args:
            channel: Channel name
            user: Username voting
            item_id: Item ID being voted on (optional, for validation)
        
        Returns:
            Dict with keys:
            - success (bool): Whether vote was cast
            - votes (int): Current vote count
            - needed (int): Votes needed to pass
            - passed (bool): Whether threshold reached
            - already_voted (bool): Whether user already voted
        """
        session = self._get_or_create_session(channel, item_id)
        
        # Check if already voted
        if user in session.voters:
            return {
                "success": False,
                "votes": len(session.voters),
                "needed": self._calculate_needed(channel),
                "passed": False,
                "already_voted": True,
            }
        
        # Check if session expired
        if datetime.utcnow() - session.started_at > self.timeout:
            logger.info(f"Vote session expired for {channel}, resetting")
            self.reset(channel)
            session = self._get_or_create_session(channel, item_id)
        
        # Add vote
        session.voters.add(user)
        
        votes = len(session.voters)
        needed = self._calculate_needed(channel)
        passed = votes >= needed
        
        logger.info(f"Vote cast in {channel} by {user}: {votes}/{needed}")
        
        if passed:
            logger.info(f"Skip vote passed in {channel} with {votes} votes")
            self._clear_session(channel)
        
        return {
            "success": True,
            "votes": votes,
            "needed": needed,
            "passed": passed,
            "already_voted": False,
        }
    
    def reset(self, channel: str) -> None:
        """
        Reset votes for a channel.
        
        Called when:
        - Item changes (new item, no votes needed)
        - Vote passes (automatically cleared)
        - Manual reset requested
        
        Args:
            channel: Channel to reset
        """
        if channel in self._sessions:
            logger.debug(f"Resetting vote session for {channel}")
        self._clear_session(channel)
    
    def set_active_users(self, channel: str, users: Set[str]) -> None:
        """
        Update active user count for threshold calculation.
        
        Should be called periodically to reflect current active users.
        
        Args:
            channel: Channel name
            users: Set of active usernames
        """
        self._active_users[channel] = users
        logger.debug(f"Updated active users for {channel}: {len(users)} users")
    
    def get_status(self, channel: str) -> Dict:
        """
        Get current vote status for a channel.
        
        Args:
            channel: Channel name
        
        Returns:
            Dict with keys:
            - active (bool): Whether there's an active vote session
            - votes (int): Current vote count
            - needed (int): Votes needed to pass
            - voters (List[str]): Users who voted (if active)
            - item_id (str): Item being voted on (if active)
        """
        session = self._sessions.get(channel)
        
        if not session:
            return {
                "active": False,
                "votes": 0,
                "needed": self._calculate_needed(channel),
                "voters": [],
                "item_id": None,
            }
        
        # Check if expired
        if datetime.utcnow() - session.started_at > self.timeout:
            self.reset(channel)
            return {
                "active": False,
                "votes": 0,
                "needed": self._calculate_needed(channel),
                "voters": [],
                "item_id": None,
            }
        
        return {
            "active": True,
            "votes": len(session.voters),
            "needed": self._calculate_needed(channel),
            "voters": list(session.voters),
            "item_id": session.item_id,
        }
    
    def has_voted(self, channel: str, user: str) -> bool:
        """
        Check if a user has already voted in the current session.
        
        Args:
            channel: Channel name
            user: Username
        
        Returns:
            True if user has voted, False otherwise
        """
        session = self._sessions.get(channel)
        return session and user in session.voters
    
    def _get_or_create_session(self, channel: str, item_id: Optional[str] = None) -> VoteSession:
        """
        Get existing session or create new one.
        
        Args:
            channel: Channel name
            item_id: Item ID for validation
        
        Returns:
            Vote session
        """
        if channel not in self._sessions:
            self._sessions[channel] = VoteSession(
                channel=channel,
                item_id=item_id or "",
                threshold=self.threshold,
            )
        return self._sessions[channel]
    
    def _clear_session(self, channel: str) -> None:
        """Clear session for channel."""
        self._sessions.pop(channel, None)
    
    def _calculate_needed(self, channel: str) -> int:
        """
        Calculate votes needed to pass.
        
        Uses max of:
        - Minimum vote requirement
        - Threshold percentage of active users (rounded up)
        
        Args:
            channel: Channel name
        
        Returns:
            Number of votes needed
        """
        active_count = len(self._active_users.get(channel, set()))
        
        if active_count < self.min_votes:
            return self.min_votes
        
        threshold_votes = int(active_count * self.threshold)
        # Ensure at least 1 vote if threshold rounds to 0
        threshold_votes = max(1, threshold_votes)
        
        return max(self.min_votes, threshold_votes)
