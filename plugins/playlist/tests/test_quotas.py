"""
Tests for QuotaManager (user quotas and rate limiting).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from quotas import QuotaManager, QuotaConfig
from models import PlaylistItem, MediaType


@pytest.fixture
def config():
    """Default quota config."""
    return QuotaConfig(
        max_items_per_user=5,
        max_duration_per_user=1800,  # 30 minutes
        rate_limit_count=3,
        rate_limit_window=10  # seconds
    )


@pytest.fixture
def manager(config):
    """Create QuotaManager with config."""
    return QuotaManager(config)


@pytest.fixture
def sample_items():
    """Sample queue items."""
    return [
        PlaylistItem(
            id="1",
            media_type=MediaType.YOUTUBE,
            media_id="abc123",
            title="Video 1",
            duration=300,
            added_by="user1",
            added_at=datetime.utcnow()
        ),
        PlaylistItem(
            id="2",
            media_type=MediaType.YOUTUBE,
            media_id="def456",
            title="Video 2",
            duration=240,
            added_by="user1",
            added_at=datetime.utcnow()
        ),
        PlaylistItem(
            id="3",
            media_type=MediaType.YOUTUBE,
            media_id="ghi789",
            title="Video 3",
            duration=180,
            added_by="user2",
            added_at=datetime.utcnow()
        ),
    ]


class TestQuotaConfig:
    """Test QuotaConfig dataclass."""
    
    def test_defaults(self):
        """Test default configuration."""
        config = QuotaConfig()
        
        assert config.max_items_per_user == 5
        assert config.max_duration_per_user == 1800
        assert config.rate_limit_count == 3
        assert config.rate_limit_window == 10
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = QuotaConfig(
            max_items_per_user=10,
            max_duration_per_user=3600,
            rate_limit_count=5,
            rate_limit_window=60
        )
        
        assert config.max_items_per_user == 10
        assert config.max_duration_per_user == 3600
        assert config.rate_limit_count == 5
        assert config.rate_limit_window == 60


class TestQuotaManager:
    """Test QuotaManager class."""
    
    def test_initialization(self, manager, config):
        """Test manager initialization."""
        assert manager.config == config
        assert manager._rate_trackers == {}
    
    def test_check_quota_empty_queue(self, manager):
        """Test quota check with empty queue."""
        result = manager.check_quota("lobby", "user1", [], item_duration=300)
        
        assert result["allowed"] is True
        assert result["user_items"] == 0
        assert result["user_duration"] == 0
    
    def test_check_quota_within_limits(self, manager, sample_items):
        """Test quota check within all limits."""
        result = manager.check_quota("lobby", "user1", sample_items, item_duration=300)
        
        # user1 has 2 items (540s), adding 300s = 840s total
        assert result["allowed"] is True
        assert result["user_items"] == 2
        assert result["user_duration"] == 540
    
    def test_check_quota_max_items_exceeded(self, manager):
        """Test quota check when max items exceeded."""
        # Create 5 items for user1
        items = [
            PlaylistItem(
                id=str(i),
                media_type=MediaType.YOUTUBE,
                media_id=f"id{i}",
                title=f"Video {i}",
                duration=100,
                added_by="user1",
                added_at=datetime.utcnow()
            )
            for i in range(5)
        ]
        
        result = manager.check_quota("lobby", "user1", items, item_duration=100)
        
        assert result["allowed"] is False
        assert "max 5" in result["reason"]
        assert result["user_items"] == 5
    
    def test_check_quota_max_duration_exceeded(self, manager):
        """Test quota check when max duration exceeded."""
        # Create items totaling 1500s, try to add 400s (exceeds 1800s limit)
        items = [
            PlaylistItem(
                id=str(i),
                media_type=MediaType.YOUTUBE,
                media_id=f"id{i}",
                title=f"Video {i}",
                duration=500,
                added_by="user1",
                added_at=datetime.utcnow()
            )
            for i in range(3)
        ]
        
        result = manager.check_quota("lobby", "user1", items, item_duration=400)
        
        assert result["allowed"] is False
        assert "30 minute limit" in result["reason"]
        assert result["user_duration"] == 1500
    
    def test_check_quota_rate_limit_ok(self, manager):
        """Test quota check with rate limit OK."""
        # Record 2 adds (under limit of 3)
        manager.record_add("lobby", "user1")
        manager.record_add("lobby", "user1")
        
        result = manager.check_quota("lobby", "user1", [], item_duration=100)
        
        assert result["allowed"] is True
        assert result["rate_limit_remaining"] == 1
    
    def test_check_quota_rate_limit_exceeded(self, manager):
        """Test quota check when rate limit exceeded."""
        # Record 3 adds (hits limit)
        manager.record_add("lobby", "user1")
        manager.record_add("lobby", "user1")
        manager.record_add("lobby", "user1")
        
        result = manager.check_quota("lobby", "user1", [], item_duration=100)
        
        assert result["allowed"] is False
        assert "Rate limit" in result["reason"]
        assert result["rate_limit_remaining"] == 0
    
    def test_check_quota_different_users(self, manager, sample_items):
        """Test quota isolation between users."""
        # user1 has 2 items, user2 has 1 item
        result1 = manager.check_quota("lobby", "user1", sample_items, item_duration=100)
        result2 = manager.check_quota("lobby", "user2", sample_items, item_duration=100)
        
        assert result1["user_items"] == 2
        assert result2["user_items"] == 1
    
    def test_check_quota_different_channels(self, manager):
        """Test quota isolation between channels."""
        # Record adds in different channels
        manager.record_add("lobby", "user1")
        manager.record_add("music", "user1")
        
        result_lobby = manager.check_quota("lobby", "user1", [], item_duration=100)
        result_music = manager.check_quota("music", "user1", [], item_duration=100)
        
        # Each channel has its own rate tracking
        assert result_lobby["rate_limit_remaining"] == 2
        assert result_music["rate_limit_remaining"] == 2
    
    def test_record_add(self, manager):
        """Test recording an add."""
        manager.record_add("lobby", "user1")
        
        # Should create tracker
        assert "lobby" in manager._rate_trackers
        assert "user1" in manager._rate_trackers["lobby"]
        assert len(manager._rate_trackers["lobby"]["user1"].adds) == 1
    
    def test_record_add_multiple(self, manager):
        """Test recording multiple adds."""
        manager.record_add("lobby", "user1")
        manager.record_add("lobby", "user1")
        manager.record_add("lobby", "user1")
        
        assert len(manager._rate_trackers["lobby"]["user1"].adds) == 3
    
    def test_rate_limit_expiry(self, manager):
        """Test rate limit window expiry."""
        # Record 3 adds (hits limit)
        old_time = datetime.utcnow() - timedelta(seconds=15)
        manager.record_add("lobby", "user1", timestamp=old_time)
        manager.record_add("lobby", "user1", timestamp=old_time)
        manager.record_add("lobby", "user1", timestamp=old_time)
        
        # Should be allowed since adds expired (>10s ago)
        result = manager.check_quota("lobby", "user1", [], item_duration=100)
        
        assert result["allowed"] is True
    
    def test_get_user_quota_info(self, manager, sample_items):
        """Test getting user quota information."""
        info = manager.get_user_quota_info("lobby", "user1", sample_items)
        
        assert info["items_used"] == 2
        assert info["items_max"] == 5
        assert info["duration_used"] == 540
        assert info["duration_max"] == 1800
        assert info["rate_limit_remaining"] >= 0
    
    def test_get_user_quota_info_empty(self, manager):
        """Test getting quota info for user with no items."""
        info = manager.get_user_quota_info("lobby", "newuser", [])
        
        assert info["items_used"] == 0
        assert info["duration_used"] == 0
        assert info["rate_limit_remaining"] == 3
    
    def test_clear_channel(self, manager):
        """Test clearing channel rate trackers."""
        manager.record_add("lobby", "user1")
        manager.record_add("music", "user2")
        
        manager.clear_channel("lobby")
        
        assert "lobby" not in manager._rate_trackers
        assert "music" in manager._rate_trackers
