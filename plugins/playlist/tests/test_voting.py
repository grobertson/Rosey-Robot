"""
Tests for skip voting system.
"""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from voting import SkipVoteManager, VoteSession


class TestVoteSession:
    """Tests for VoteSession dataclass."""
    
    def test_vote_session_creation(self):
        """Test creating a vote session."""
        session = VoteSession(channel="lobby", item_id="abc123")
        
        assert session.channel == "lobby"
        assert session.item_id == "abc123"
        assert len(session.voters) == 0
        assert session.threshold == 0.5
        assert isinstance(session.started_at, datetime)


class TestSkipVoteManager:
    """Tests for SkipVoteManager class."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = SkipVoteManager(threshold=0.6, min_votes=3, timeout_minutes=10)
        
        assert manager.threshold == 0.6
        assert manager.min_votes == 3
        assert manager.timeout == timedelta(minutes=10)
    
    def test_vote_success(self):
        """Test casting a vote."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        manager.set_active_users("lobby", {"user1", "user2", "user3"})
        
        result = manager.vote("lobby", "user1")
        
        assert result["success"] is True
        assert result["votes"] == 1
        assert result["needed"] == 2  # max(2, 3 * 0.5) = 2
        assert result["passed"] is False
        assert result["already_voted"] is False
    
    def test_vote_already_voted(self):
        """Test voting twice."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        
        manager.vote("lobby", "user1")
        result = manager.vote("lobby", "user1")
        
        assert result["success"] is False
        assert result["already_voted"] is True
        assert result["votes"] == 1
    
    def test_vote_passed(self):
        """Test vote passing threshold."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        manager.set_active_users("lobby", {"user1", "user2", "user3", "user4"})
        
        result1 = manager.vote("lobby", "user1")
        assert result1["passed"] is False
        
        result2 = manager.vote("lobby", "user2")
        assert result2["passed"] is True
        assert result2["votes"] == 2
        assert result2["needed"] == 2
    
    def test_min_votes_enforced(self):
        """Test minimum votes requirement."""
        manager = SkipVoteManager(threshold=0.5, min_votes=3)
        manager.set_active_users("lobby", {"user1", "user2"})  # Only 2 active users
        
        result = manager.vote("lobby", "user1")
        
        # Should need 3 votes even though only 2 users active
        assert result["needed"] == 3
    
    def test_reset(self):
        """Test resetting votes."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        
        manager.vote("lobby", "user1")
        manager.vote("lobby", "user2")
        
        manager.reset("lobby")
        
        status = manager.get_status("lobby")
        assert status["active"] is False
        assert status["votes"] == 0
    
    def test_get_status_no_session(self):
        """Test get_status when no session."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        
        status = manager.get_status("lobby")
        
        assert status["active"] is False
        assert status["votes"] == 0
        assert status["needed"] == 2
        assert status["voters"] == []
        assert status["item_id"] is None
    
    def test_get_status_active_session(self):
        """Test get_status with active session."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        manager.set_active_users("lobby", {"user1", "user2", "user3"})
        
        manager.vote("lobby", "user1", item_id="abc123")
        
        status = manager.get_status("lobby")
        
        assert status["active"] is True
        assert status["votes"] == 1
        assert status["needed"] == 2
        assert "user1" in status["voters"]
        assert status["item_id"] == "abc123"
    
    def test_has_voted(self):
        """Test has_voted check."""
        manager = SkipVoteManager()
        
        manager.vote("lobby", "user1")
        
        assert manager.has_voted("lobby", "user1") is True
        assert manager.has_voted("lobby", "user2") is False
    
    def test_vote_expiration(self):
        """Test vote session expiration."""
        manager = SkipVoteManager(timeout_minutes=5)
        
        # Create session
        manager.vote("lobby", "user1")
        session = manager._sessions["lobby"]
        
        # Manually expire it
        session.started_at = datetime.utcnow() - timedelta(minutes=6)
        
        # New vote should reset session
        result = manager.vote("lobby", "user2")
        
        # Should be first vote in new session
        assert result["votes"] == 1
    
    def test_threshold_calculation(self):
        """Test threshold calculation with different user counts."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        
        # 2 users: min_votes = 2
        manager.set_active_users("lobby", {"user1", "user2"})
        assert manager._calculate_needed("lobby") == 2
        
        # 4 users: 50% = 2
        manager.set_active_users("lobby", {"user1", "user2", "user3", "user4"})
        assert manager._calculate_needed("lobby") == 2
        
        # 5 users: 50% = 2 (rounds down, but min is 2)
        manager.set_active_users("lobby", {"user1", "user2", "user3", "user4", "user5"})
        assert manager._calculate_needed("lobby") == 2
        
        # 6 users: 50% = 3
        manager.set_active_users("lobby", set(f"user{i}" for i in range(6)))
        assert manager._calculate_needed("lobby") == 3
    
    def test_multiple_channels(self):
        """Test managing votes for multiple channels."""
        manager = SkipVoteManager(threshold=0.5, min_votes=2)
        
        manager.vote("lobby", "user1")
        manager.vote("room2", "user2")
        
        status1 = manager.get_status("lobby")
        status2 = manager.get_status("room2")
        
        assert status1["votes"] == 1
        assert status2["votes"] == 1
        assert "user1" in status1["voters"]
        assert "user2" in status2["voters"]
