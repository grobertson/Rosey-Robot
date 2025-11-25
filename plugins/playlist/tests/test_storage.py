"""
Tests for PlaylistStorage (database persistence).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import PlaylistStorage
from models import PlaylistItem, MediaType


@pytest.fixture
def mock_db():
    """Mock DatabaseService."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    db.fetch_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def storage(mock_db):
    """Create PlaylistStorage with mock database."""
    return PlaylistStorage(mock_db)


@pytest.fixture
def sample_item():
    """Sample playlist item."""
    return PlaylistItem(
        id="test_123",
        media_type=MediaType.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Test Video",
        duration=180,
        added_by="testuser",
        added_at=datetime(2025, 11, 24, 10, 0, 0)
    )


@pytest.mark.asyncio
class TestPlaylistStorage:
    """Test PlaylistStorage class."""
    
    async def test_create_tables(self, storage, mock_db):
        """Test table creation."""
        await storage.create_tables()
        
        # Should execute CREATE TABLE for all 3 tables
        assert mock_db.execute.call_count >= 6  # 3 tables + 3 indices
        
        # Check for table creation queries
        calls = mock_db.execute.call_args_list
        create_calls = [str(call) for call in calls if "CREATE TABLE" in str(call)]
        
        assert any("playlist_queue" in str(call) for call in create_calls)
        assert any("playlist_history" in str(call) for call in create_calls)
        assert any("playlist_user_stats" in str(call) for call in create_calls)
    
    async def test_save_queue_empty(self, storage, mock_db):
        """Test saving empty queue."""
        await storage.save_queue("lobby", [])
        
        # Should delete existing queue
        assert mock_db.execute.called
        delete_call = mock_db.execute.call_args_list[0]
        assert "DELETE FROM playlist_queue" in str(delete_call)
    
    async def test_save_queue_with_items(self, storage, mock_db, sample_item):
        """Test saving queue with items."""
        item2 = PlaylistItem(
            id="test_456",
            media_type=MediaType.VIMEO,
            media_id="123456",
            title="Another Video",
            duration=240,
            added_by="user2",
            added_at=datetime(2025, 11, 24, 10, 5, 0)
        )
        
        await storage.save_queue("lobby", [sample_item, item2])
        
        # Should delete + insert for each item
        assert mock_db.execute.call_count >= 3  # DELETE + 2 INSERTs
        
        # Check insert calls
        insert_calls = [c for c in mock_db.execute.call_args_list 
                       if "INSERT INTO playlist_queue" in str(c)]
        assert len(insert_calls) == 2
    
    async def test_load_queue_empty(self, storage, mock_db):
        """Test loading empty queue."""
        mock_db.fetch_all.return_value = []
        
        items = await storage.load_queue("lobby")
        
        assert items == []
        assert mock_db.fetch_all.called
    
    async def test_load_queue_with_items(self, storage, mock_db):
        """Test loading queue with items."""
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "channel": "lobby",
                "position": 0,
                "media_type": "yt",  # MediaType.YOUTUBE.value
                "media_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "duration": 180,
                "added_by": "testuser",
                "added_at": datetime(2025, 11, 24, 10, 0, 0)
            },
            {
                "id": 2,
                "channel": "lobby",
                "position": 1,
                "media_type": "vi",  # MediaType.VIMEO.value
                "media_id": "123456",
                "title": "Another Video",
                "duration": 240,
                "added_by": "user2",
                "added_at": datetime(2025, 11, 24, 10, 5, 0)
            }
        ]
        
        items = await storage.load_queue("lobby")
        
        assert len(items) == 2
        assert items[0].title == "Test Video"
        assert items[1].title == "Another Video"
        assert items[0].media_type == MediaType.YOUTUBE
    
    async def test_clear_queue(self, storage, mock_db):
        """Test clearing persisted queue."""
        await storage.clear_queue("lobby")
        
        assert mock_db.execute.called
        call_str = str(mock_db.execute.call_args_list[0])
        assert "DELETE FROM playlist_queue" in call_str
        assert "lobby" in call_str
    
    async def test_get_persisted_channels(self, storage, mock_db):
        """Test getting channels with persisted queues."""
        mock_db.fetch_all.return_value = [
            {"channel": "lobby"},
            {"channel": "music"}
        ]
        
        channels = await storage.get_persisted_channels()
        
        assert channels == ["lobby", "music"]
    
    async def test_record_play(self, storage, mock_db, sample_item):
        """Test recording play in history."""
        await storage.record_play("lobby", sample_item, play_duration=150, skipped=False)
        
        # Should insert into history AND update user stats
        assert mock_db.execute.call_count >= 2
        
        # Check history insert
        history_call = mock_db.execute.call_args_list[0]
        assert "INSERT INTO playlist_history" in str(history_call)
    
    async def test_record_play_skipped(self, storage, mock_db, sample_item):
        """Test recording skipped play."""
        await storage.record_play("lobby", sample_item, play_duration=0, skipped=True)
        
        # Should mark as skipped in history
        history_call = mock_db.execute.call_args_list[0]
        assert "skipped" in str(history_call).lower()
    
    async def test_get_history_empty(self, storage, mock_db):
        """Test getting empty history."""
        mock_db.fetch_all.return_value = []
        
        history = await storage.get_history("lobby", limit=10)
        
        assert history == []
    
    async def test_get_history_with_entries(self, storage, mock_db):
        """Test getting play history."""
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "channel": "lobby",
                "media_type": "youtube",
                "media_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "duration": 180,
                "added_by": "testuser",
                "played_at": datetime(2025, 11, 24, 10, 0, 0),
                "play_duration": 180,
                "skipped": False
            }
        ]
        
        history = await storage.get_history("lobby", limit=10)
        
        assert len(history) == 1
        assert history[0]["title"] == "Test Video"
        assert history[0]["skipped"] is False
    
    async def test_get_user_history(self, storage, mock_db):
        """Test getting user's play history."""
        mock_db.fetch_all.return_value = [
            {
                "id": 1,
                "channel": "lobby",
                "media_type": "youtube",
                "media_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "duration": 180,
                "added_by": "testuser",
                "played_at": datetime(2025, 11, 24, 10, 0, 0),
                "play_duration": 180,
                "skipped": False
            }
        ]
        
        history = await storage.get_user_history("testuser", limit=10)
        
        assert len(history) == 1
        assert history[0]["added_by"] == "testuser"
    
    async def test_get_user_stats_none(self, storage, mock_db):
        """Test getting stats for user with none."""
        mock_db.fetch_one.return_value = None
        
        stats = await storage.get_user_stats("newuser")
        
        assert stats is None
    
    async def test_get_user_stats(self, storage, mock_db):
        """Test getting user stats."""
        mock_db.fetch_one.return_value = {
            "user_id": "testuser",
            "items_added": 10,
            "items_played": 8,
            "items_skipped": 2,
            "total_duration_added": 1800,
            "total_duration_played": 1440,
            "last_add": datetime(2025, 11, 24, 10, 0, 0)
        }
        
        stats = await storage.get_user_stats("testuser")
        
        assert stats is not None
        assert stats["items_added"] == 10
        assert stats["items_played"] == 8
        assert stats["items_skipped"] == 2
    
    async def test_record_add(self, storage, mock_db):
        """Test recording item addition."""
        await storage.record_add("testuser", duration=180)
        
        # Should insert or update user stats
        assert mock_db.execute.called
        call_str = str(mock_db.execute.call_args_list[0])
        assert "playlist_user_stats" in call_str
        assert "items_added" in call_str
