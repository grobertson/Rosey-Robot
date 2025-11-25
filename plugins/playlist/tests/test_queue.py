"""
Tests for playlist queue operations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from models import MediaType, PlaylistItem
from queue import PlaylistQueue


@pytest.fixture
def sample_item():
    """Create a sample playlist item for testing."""
    return PlaylistItem(
        id="abc123",
        media_type=MediaType.YOUTUBE,
        media_id="test",
        title="Test Video",
        duration=100,
        added_by="user1",
    )


@pytest.fixture
def queue():
    """Create a fresh playlist queue."""
    return PlaylistQueue(max_size=10)


class TestPlaylistQueue:
    """Test PlaylistQueue operations."""
    
    def test_create_queue(self, queue):
        """Test creating an empty queue."""
        assert queue.is_empty
        assert queue.length == 0
        assert queue.current is None
    
    def test_add_item(self, queue, sample_item):
        """Test adding an item to queue."""
        assert queue.add(sample_item)
        assert queue.length == 1
        assert not queue.is_empty
    
    def test_add_item_generates_id(self, queue):
        """Test that add generates ID if not provided."""
        item = PlaylistItem(
            id="",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=0,
            added_by="user",
        )
        queue.add(item)
        assert item.id != ""
        assert len(item.id) == 8
    
    def test_add_to_full_queue(self, queue):
        """Test adding to a full queue returns False."""
        # Fill queue to max
        for i in range(10):
            item = PlaylistItem(
                id=f"item{i}",
                media_type=MediaType.YOUTUBE,
                media_id=f"test{i}",
                title=f"Test {i}",
                duration=0,
                added_by="user",
            )
            queue.add(item)
        
        # Try to add one more
        extra = PlaylistItem(
            id="extra",
            media_type=MediaType.YOUTUBE,
            media_id="extra",
            title="Extra",
            duration=0,
            added_by="user",
        )
        assert not queue.add(extra)
        assert queue.length == 10
    
    def test_remove_by_id(self, queue, sample_item):
        """Test removing item by ID."""
        queue.add(sample_item)
        removed = queue.remove("abc123")
        assert removed is not None
        assert removed.id == "abc123"
        assert queue.is_empty
    
    def test_remove_nonexistent(self, queue):
        """Test removing nonexistent item returns None."""
        result = queue.remove("nope")
        assert result is None
    
    def test_remove_by_user(self, queue):
        """Test removing items by user."""
        # Add items from two users
        for i in range(3):
            queue.add(PlaylistItem(
                id=f"user1_{i}",
                media_type=MediaType.YOUTUBE,
                media_id="test",
                title="Test",
                duration=0,
                added_by="user1",
            ))
        
        for i in range(2):
            queue.add(PlaylistItem(
                id=f"user2_{i}",
                media_type=MediaType.YOUTUBE,
                media_id="test",
                title="Test",
                duration=0,
                added_by="user2",
            ))
        
        # Remove user1's items (limit to 2)
        removed = queue.remove_by_user("user1", count=2)
        assert len(removed) == 2
        assert queue.length == 3  # 1 user1 + 2 user2
    
    def test_advance(self, queue):
        """Test advancing to next item."""
        item1 = PlaylistItem(
            id="item1",
            media_type=MediaType.YOUTUBE,
            media_id="test1",
            title="Test 1",
            duration=0,
            added_by="user",
        )
        item2 = PlaylistItem(
            id="item2",
            media_type=MediaType.YOUTUBE,
            media_id="test2",
            title="Test 2",
            duration=0,
            added_by="user",
        )
        
        queue.add(item1)
        queue.add(item2)
        
        # Advance to first item
        current = queue.advance()
        assert current == item1
        assert queue.current == item1
        assert queue.length == 1
        assert not queue.paused
        
        # Advance to second item
        current = queue.advance()
        assert current == item2
        assert queue.current == item2
        assert queue.length == 0
        
        # Advance on empty queue
        current = queue.advance()
        assert current is None
        assert queue.current is None
        assert queue.paused
    
    def test_shuffle(self, queue):
        """Test shuffling queue."""
        items = []
        for i in range(10):
            item = PlaylistItem(
                id=f"item{i}",
                media_type=MediaType.YOUTUBE,
                media_id=f"test{i}",
                title=f"Test {i}",
                duration=0,
                added_by="user",
            )
            items.append(item)
            queue.add(item)
        
        original_order = [item.id for item in queue.items]
        
        queue.shuffle()
        
        shuffled_order = [item.id for item in queue.items]
        
        # Order should be different (very unlikely to be same after shuffle)
        assert shuffled_order != original_order
        
        # But should have same items
        assert set(shuffled_order) == set(original_order)
        assert queue.length == 10
    
    def test_clear(self, queue):
        """Test clearing queue."""
        for i in range(5):
            queue.add(PlaylistItem(
                id=f"item{i}",
                media_type=MediaType.YOUTUBE,
                media_id="test",
                title="Test",
                duration=0,
                added_by="user",
            ))
        
        count = queue.clear()
        assert count == 5
        assert queue.is_empty
    
    def test_get_stats(self, queue):
        """Test getting queue statistics."""
        queue.add(PlaylistItem(
            id="item1",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=100,
            added_by="user1",
        ))
        queue.add(PlaylistItem(
            id="item2",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=200,
            added_by="user2",
        ))
        queue.add(PlaylistItem(
            id="item3",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=150,
            added_by="user1",
        ))
        
        stats = queue.get_stats()
        assert stats.total_items == 3
        assert stats.total_duration == 450
        assert stats.unique_users == 2
