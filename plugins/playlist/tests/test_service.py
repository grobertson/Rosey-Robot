"""
Tests for PlaylistService interface.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from service import PlaylistService, AddResult, PlaybackState
from models import PlaylistItem, MediaType
from queue import PlaylistQueue
from metadata import MetadataFetcher
from voting import SkipVoteManager


@pytest.fixture
def mock_metadata_fetcher():
    """Mock metadata fetcher."""
    fetcher = AsyncMock(spec=MetadataFetcher)
    fetcher.fetch.return_value = {
        "title": "Test Video",
        "duration": 180,
        "thumbnail": "https://example.com/thumb.jpg",
        "channel": "Test Channel",
    }
    return fetcher


@pytest.fixture
def mock_vote_manager():
    """Mock vote manager."""
    manager = Mock(spec=SkipVoteManager)
    manager.vote.return_value = {
        "success": True,
        "votes": 1,
        "needed": 2,
        "passed": False,
        "already_voted": False,
    }
    manager.reset = Mock()
    return manager


@pytest.fixture
async def service(mock_metadata_fetcher, mock_vote_manager):
    """Create PlaylistService instance."""
    queues = {}
    event_callback = AsyncMock()
    config = {"max_queue_size": 100, "max_items_per_user": 5}
    
    return PlaylistService(
        queues=queues,
        metadata_fetcher=mock_metadata_fetcher,
        vote_manager=mock_vote_manager,
        event_callback=event_callback,
        config=config,
    )


@pytest.mark.asyncio
class TestPlaylistService:
    """Tests for PlaylistService class."""
    
    async def test_add_item_success(self, service):
        """Test adding item to playlist."""
        result = await service.add_item(
            "lobby",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "user1",
            fetch_metadata=False
        )
        
        assert result.success is True
        assert result.item is not None
        assert result.item.media_type == MediaType.YOUTUBE
        assert result.position == 1
    
    async def test_add_item_invalid_url(self, service):
        """Test adding invalid URL."""
        result = await service.add_item("lobby", "not-a-url", "user1")
        
        assert result.success is False
        assert "invalid" in result.error.lower() or "unrecognized" in result.error.lower()
    
    async def test_add_item_queue_full(self, service):
        """Test adding when queue is full."""
        service._config["max_queue_size"] = 2
        
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user1", False)
        
        result = await service.add_item("lobby", "https://youtube.com/watch?v=3", "user1", False)
        
        assert result.success is False
        assert "full" in result.error.lower()
    
    async def test_add_item_user_limit(self, service):
        """Test per-user item limit."""
        service._config["max_items_per_user"] = 2
        
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user1", False)
        
        result = await service.add_item("lobby", "https://youtube.com/watch?v=3", "user1", False)
        
        assert result.success is False
        assert "already" in result.error.lower() or "items" in result.error.lower()
    
    async def test_remove_item_success(self, service):
        """Test removing an item."""
        result = await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        item_id = result.item.id
        
        removed = await service.remove_item("lobby", item_id, "user1", False)
        
        assert removed is not None
        assert removed.id == item_id
    
    async def test_remove_item_not_found(self, service):
        """Test removing non-existent item."""
        removed = await service.remove_item("lobby", "nonexistent", "user1", False)
        
        assert removed is None
    
    async def test_remove_item_permission_denied(self, service):
        """Test removing someone else's item without admin."""
        result = await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        item_id = result.item.id
        
        removed = await service.remove_item("lobby", item_id, "user2", is_admin=False)
        
        assert removed is None
    
    async def test_remove_item_admin_override(self, service):
        """Test admin can remove anyone's item."""
        result = await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        item_id = result.item.id
        
        removed = await service.remove_item("lobby", item_id, "admin", is_admin=True)
        
        assert removed is not None
        assert removed.id == item_id
    
    async def test_get_queue(self, service):
        """Test getting queue items."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user2", False)
        
        items = service.get_queue("lobby")
        
        assert len(items) == 2
        assert all(isinstance(item, PlaylistItem) for item in items)
    
    async def test_get_current(self, service):
        """Test getting current item."""
        queue = service._get_queue("lobby")
        queue._current = PlaylistItem(
            id="abc123",
            media_type=MediaType.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Test",
            duration=0,
            added_by="user1"
        )
        
        current = service.get_current("lobby")
        
        assert current is not None
        assert current.id == "abc123"
    
    async def test_get_stats(self, service):
        """Test getting queue stats."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user2", False)
        
        stats = service.get_stats("lobby")
        
        assert stats.total_items == 2
        assert stats.unique_users == 2
    
    async def test_get_playback_state(self, service):
        """Test getting playback state."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        
        state = service.get_playback_state("lobby")
        
        assert isinstance(state, PlaybackState)
        assert state.queue_length == 1
    
    async def test_skip(self, service, mock_vote_manager):
        """Test skipping current item."""
        # Add items and set one as current
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user2", False)
        queue = service._get_queue("lobby")
        queue.advance()  # Set first as current
        
        next_item = await service.skip("lobby", "user1")
        
        assert next_item is not None
        mock_vote_manager.reset.assert_called_once_with("lobby")
    
    async def test_skip_empty_queue(self, service):
        """Test skipping when nothing playing."""
        next_item = await service.skip("lobby", "user1")
        
        assert next_item is None
    
    async def test_vote_skip(self, service, mock_vote_manager):
        """Test vote skip."""
        # Add item and set as current
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        queue = service._get_queue("lobby")
        queue.advance()
        
        result = await service.vote_skip("lobby", "user2")
        
        assert result["success"] is True
        mock_vote_manager.vote.assert_called_once()
    
    async def test_vote_skip_no_current(self, service):
        """Test vote skip when nothing playing."""
        result = await service.vote_skip("lobby", "user1")
        
        assert result["success"] is False
        assert "nothing playing" in result["error"].lower()
    
    async def test_shuffle(self, service):
        """Test shuffling queue."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user2", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=3", "user3", False)
        
        count = await service.shuffle("lobby", "user1")
        
        assert count == 3
    
    async def test_clear(self, service, mock_vote_manager):
        """Test clearing queue."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("lobby", "https://youtube.com/watch?v=2", "user2", False)
        
        count = await service.clear("lobby", "admin")
        
        assert count == 2
        mock_vote_manager.reset.assert_called_once_with("lobby")
    
    async def test_subscribe(self, service):
        """Test subscribing to events."""
        callback = Mock()
        
        service.subscribe("lobby", callback)
        
        assert "lobby" in service._subscribers
        assert callback in service._subscribers["lobby"]
    
    async def test_unsubscribe(self, service):
        """Test unsubscribing from events."""
        callback = Mock()
        
        service.subscribe("lobby", callback)
        service.unsubscribe("lobby", callback)
        
        assert callback not in service._subscribers.get("lobby", [])
    
    async def test_notify_subscribers(self, service):
        """Test notifying subscribers."""
        callback = AsyncMock()
        
        service.subscribe("lobby", callback)
        await service.notify_subscribers("lobby", "test.event", {"data": "value"})
        
        callback.assert_called_once_with("test.event", {"data": "value"})
    
    async def test_event_emission(self, service):
        """Test that events are emitted."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        
        # Check event callback was called
        service._emit_event.assert_called()
        call_args = service._emit_event.call_args[0]
        assert call_args[0] == "playlist.item.added"
        assert "item" in call_args[1]
    
    async def test_channel_isolation(self, service):
        """Test that channels are isolated."""
        await service.add_item("lobby", "https://youtube.com/watch?v=1", "user1", False)
        await service.add_item("room2", "https://youtube.com/watch?v=2", "user2", False)
        
        lobby_items = service.get_queue("lobby")
        room2_items = service.get_queue("room2")
        
        assert len(lobby_items) == 1
        assert len(room2_items) == 1
        assert lobby_items[0].id != room2_items[0].id
