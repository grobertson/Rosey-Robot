#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
from lib.playlist import PlaylistItem, Playlist
from lib.media_link import MediaLink


@pytest.fixture
def sample_item_data():
    """Sample playlist item data structure"""
    return {
        'uid': 1,
        'temp': False,
        'queueby': 'testuser',
        'media': {
            'type': 'yt',
            'id': 'dQw4w9WgXcQ',
            'title': 'Test Video',
            'seconds': 180
        }
    }


@pytest.fixture
def sample_item(sample_item_data):
    """Sample PlaylistItem instance"""
    return PlaylistItem(sample_item_data)


@pytest.fixture
def playlist_with_items():
    """Playlist with 3 items"""
    playlist = Playlist()
    for i in range(1, 4):
        data = {
            'uid': i,
            'temp': False,
            'queueby': f'user{i}',
            'media': {
                'type': 'yt',
                'id': f'video{i}',
                'title': f'Video {i}',
                'seconds': 60 * i
            }
        }
        playlist.add(None, data)
    return playlist


class TestPlaylistItemInit:
    """Test PlaylistItem initialization"""

    def test_init_basic(self, sample_item_data):
        """Create PlaylistItem from data dict"""
        item = PlaylistItem(sample_item_data)
        assert item.uid == 1
        assert item.temp is False
        assert item.username == 'testuser'
        assert item.title == 'Test Video'
        assert item.duration == 180

    def test_init_media_link(self, sample_item_data):
        """PlaylistItem creates MediaLink from nested media data"""
        item = PlaylistItem(sample_item_data)
        assert isinstance(item.link, MediaLink)
        assert item.link.type == 'yt'
        assert item.link.id == 'dQw4w9WgXcQ'

    def test_init_temp_true(self, sample_item_data):
        """Create temporary PlaylistItem"""
        sample_item_data['temp'] = True
        item = PlaylistItem(sample_item_data)
        assert item.temp is True

    def test_init_different_media_types(self):
        """Create PlaylistItem with various media types"""
        data = {
            'uid': 2,
            'temp': False,
            'queueby': 'user',
            'media': {
                'type': 'tw',
                'id': 'channelname',
                'title': 'Twitch Stream',
                'seconds': 0
            }
        }
        item = PlaylistItem(data)
        assert item.link.type == 'tw'
        assert item.link.id == 'channelname'
        assert item.duration == 0

    def test_init_zero_duration(self, sample_item_data):
        """Create PlaylistItem with zero duration (livestream)"""
        sample_item_data['media']['seconds'] = 0
        item = PlaylistItem(sample_item_data)
        assert item.duration == 0

    def test_init_long_title(self, sample_item_data):
        """Create PlaylistItem with long title"""
        sample_item_data['media']['title'] = 'A' * 200
        item = PlaylistItem(sample_item_data)
        assert len(item.title) == 200


class TestPlaylistItemStringRepresentation:
    """Test PlaylistItem string representations and equality"""

    def test_str(self, sample_item):
        """Test __str__ format"""
        result = str(sample_item)
        assert '<playlist item #1 "Test Video">' == result

    def test_str_different_uid_title(self):
        """Test __str__ with different uid and title"""
        data = {
            'uid': 42,
            'temp': False,
            'queueby': 'user',
            'media': {
                'type': 'yt',
                'id': 'test',
                'title': 'Amazing Song',
                'seconds': 240
            }
        }
        item = PlaylistItem(data)
        assert str(item) == '<playlist item #42 "Amazing Song">'

    def test_repr_same_as_str(self, sample_item):
        """Test __repr__ returns same as __str__"""
        assert repr(sample_item) == str(sample_item)

    def test_eq_same_uid(self):
        """Two PlaylistItems with same uid are equal"""
        data1 = {
            'uid': 1,
            'temp': False,
            'queueby': 'user1',
            'media': {'type': 'yt', 'id': 'abc', 'title': 'Video 1', 'seconds': 100}
        }
        data2 = {
            'uid': 1,
            'temp': True,
            'queueby': 'user2',
            'media': {'type': 'tw', 'id': 'xyz', 'title': 'Video 2', 'seconds': 200}
        }
        item1 = PlaylistItem(data1)
        item2 = PlaylistItem(data2)
        assert item1 == item2

    def test_eq_different_uid(self):
        """Two PlaylistItems with different uid are not equal"""
        data1 = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'abc', 'title': 'Video', 'seconds': 100}
        }
        data2 = {
            'uid': 2,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'abc', 'title': 'Video', 'seconds': 100}
        }
        item1 = PlaylistItem(data1)
        item2 = PlaylistItem(data2)
        assert item1 != item2

    def test_eq_with_int(self, sample_item):
        """PlaylistItem can compare with int uid"""
        assert sample_item == 1
        assert sample_item != 2

    def test_eq_with_non_item_non_int(self, sample_item):
        """PlaylistItem comparison with non-item non-int types"""
        assert sample_item != "1"
        assert sample_item is not None
        assert sample_item != [1]


class TestPlaylistInit:
    """Test Playlist initialization"""

    def test_init_empty(self):
        """Create empty Playlist"""
        playlist = Playlist()
        assert playlist.time == 0
        assert playlist.locked is False
        assert playlist.paused is True
        assert playlist.current_time == 0
        assert playlist.current is None
        assert playlist.queue == []

    def test_init_independent_instances(self):
        """Multiple Playlist instances are independent"""
        p1 = Playlist()
        p2 = Playlist()
        p1.time = 100
        p1.locked = True
        assert p2.time == 0
        assert p2.locked is False


class TestPlaylistCurrentProperty:
    """Test Playlist current property getter/setter"""

    def test_current_set_to_none(self):
        """Set current to None"""
        playlist = Playlist()
        playlist.current = None
        assert playlist.current is None

    def test_current_set_to_playlist_item(self, sample_item):
        """Set current to PlaylistItem instance"""
        playlist = Playlist()
        playlist.current = sample_item
        assert playlist.current is sample_item
        assert playlist.current.uid == 1

    def test_current_set_to_uid_int(self, playlist_with_items):
        """Set current using uid (int) - converts to PlaylistItem"""
        playlist = playlist_with_items
        playlist.current = 2
        assert isinstance(playlist.current, PlaylistItem)
        assert playlist.current.uid == 2
        assert playlist.current.title == 'Video 2'

    def test_current_set_to_invalid_uid(self, playlist_with_items):
        """Set current to non-existent uid raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.current = 999

    def test_current_get_after_set(self, playlist_with_items):
        """Get current after setting it"""
        playlist = playlist_with_items
        playlist.current = 1
        current = playlist.current
        assert current.uid == 1
        assert current.title == 'Video 1'


class TestPlaylistIndex:
    """Test Playlist.index() method"""

    def test_index_first_item(self, playlist_with_items):
        """Get index of first item"""
        playlist = playlist_with_items
        assert playlist.index(1) == 0

    def test_index_middle_item(self, playlist_with_items):
        """Get index of middle item"""
        playlist = playlist_with_items
        assert playlist.index(2) == 1

    def test_index_last_item(self, playlist_with_items):
        """Get index of last item"""
        playlist = playlist_with_items
        assert playlist.index(3) == 2

    def test_index_not_found(self, playlist_with_items):
        """Get index of non-existent item raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.index(999)

    def test_index_empty_playlist(self):
        """Get index from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.index(1)


class TestPlaylistGet:
    """Test Playlist.get() method"""

    def test_get_existing_item(self, playlist_with_items):
        """Get existing item by uid"""
        playlist = playlist_with_items
        item = playlist.get(2)
        assert isinstance(item, PlaylistItem)
        assert item.uid == 2
        assert item.title == 'Video 2'

    def test_get_first_item(self, playlist_with_items):
        """Get first item"""
        playlist = playlist_with_items
        item = playlist.get(1)
        assert item.uid == 1
        assert item.duration == 60

    def test_get_last_item(self, playlist_with_items):
        """Get last item"""
        playlist = playlist_with_items
        item = playlist.get(3)
        assert item.uid == 3
        assert item.duration == 180

    def test_get_not_found(self, playlist_with_items):
        """Get non-existent item raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.get(999)

    def test_get_empty_playlist(self):
        """Get from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.get(1)


class TestPlaylistAdd:
    """Test Playlist.add() method"""

    def test_add_to_empty_with_none(self, sample_item_data):
        """Add to empty playlist with after=None (append)"""
        playlist = Playlist()
        playlist.add(None, sample_item_data)
        assert len(playlist.queue) == 1
        assert playlist.queue[0].uid == 1

    def test_add_append_multiple(self):
        """Add multiple items with after=None (all append)"""
        playlist = Playlist()
        for i in range(1, 4):
            data = {
                'uid': i,
                'temp': False,
                'queueby': 'user',
                'media': {'type': 'yt', 'id': f'v{i}', 'title': f'Video {i}', 'seconds': 100}
            }
            playlist.add(None, data)
        assert len(playlist.queue) == 3
        assert [item.uid for item in playlist.queue] == [1, 2, 3]

    def test_add_after_first_item(self, playlist_with_items):
        """Add item after first item (insert at index 1)"""
        playlist = playlist_with_items
        new_data = {
            'uid': 10,
            'temp': False,
            'queueby': 'newuser',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New Video', 'seconds': 90}
        }
        playlist.add(1, new_data)
        assert len(playlist.queue) == 4
        assert [item.uid for item in playlist.queue] == [1, 10, 2, 3]

    def test_add_after_last_item(self, playlist_with_items):
        """Add item after last item"""
        playlist = playlist_with_items
        new_data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 90}
        }
        playlist.add(3, new_data)
        assert len(playlist.queue) == 4
        assert [item.uid for item in playlist.queue] == [1, 2, 3, 10]

    def test_add_after_middle_item(self, playlist_with_items):
        """Add item after middle item"""
        playlist = playlist_with_items
        new_data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 90}
        }
        playlist.add(2, new_data)
        assert len(playlist.queue) == 4
        assert [item.uid for item in playlist.queue] == [1, 2, 10, 3]

    def test_add_playlist_item_instance(self, playlist_with_items, sample_item_data):
        """Add pre-created PlaylistItem instance"""
        playlist = playlist_with_items
        sample_item_data['uid'] = 10
        item = PlaylistItem(sample_item_data)
        playlist.add(None, item)
        assert len(playlist.queue) == 4
        assert playlist.queue[3] is item

    def test_add_after_non_existent_raises_error(self, playlist_with_items):
        """Add after non-existent uid raises ValueError"""
        playlist = playlist_with_items
        new_data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 90}
        }
        with pytest.raises(ValueError):
            playlist.add(999, new_data)


class TestPlaylistRemove:
    """Test Playlist.remove() method"""

    def test_remove_by_uid(self, playlist_with_items):
        """Remove item by uid (int)"""
        playlist = playlist_with_items
        playlist.remove(2)
        assert len(playlist.queue) == 2
        assert [item.uid for item in playlist.queue] == [1, 3]

    def test_remove_by_playlist_item(self, playlist_with_items):
        """Remove item by PlaylistItem instance"""
        playlist = playlist_with_items
        item = playlist.get(2)
        playlist.remove(item)
        assert len(playlist.queue) == 2
        assert [item.uid for item in playlist.queue] == [1, 3]

    def test_remove_first_item(self, playlist_with_items):
        """Remove first item"""
        playlist = playlist_with_items
        playlist.remove(1)
        assert len(playlist.queue) == 2
        assert playlist.queue[0].uid == 2

    def test_remove_last_item(self, playlist_with_items):
        """Remove last item"""
        playlist = playlist_with_items
        playlist.remove(3)
        assert len(playlist.queue) == 2
        assert playlist.queue[-1].uid == 2

    def test_remove_current_item_resets_state(self, playlist_with_items):
        """Removing current item resets current, current_time, and pauses"""
        playlist = playlist_with_items
        playlist.current = 2
        playlist.current_time = 45
        playlist.paused = False
        playlist.remove(2)
        assert playlist.current is None
        assert playlist.current_time == 0
        assert playlist.paused is True

    def test_remove_non_current_item_preserves_current(self, playlist_with_items):
        """Removing non-current item preserves current item"""
        playlist = playlist_with_items
        playlist.current = 2
        playlist.current_time = 45
        playlist.paused = False
        playlist.remove(1)
        assert playlist.current.uid == 2
        assert playlist.current_time == 45
        assert playlist.paused is False

    def test_remove_non_existent_raises_error(self, playlist_with_items):
        """Remove non-existent item raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.remove(999)

    def test_remove_from_empty_raises_error(self):
        """Remove from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.remove(1)

    def test_remove_all_items(self, playlist_with_items):
        """Remove all items one by one"""
        playlist = playlist_with_items
        playlist.remove(1)
        playlist.remove(2)
        playlist.remove(3)
        assert len(playlist.queue) == 0


class TestPlaylistMove:
    """Test Playlist.move() method"""

    def test_move_to_end(self, playlist_with_items):
        """Move first item to end"""
        playlist = playlist_with_items
        playlist.move(1, 3)
        assert [item.uid for item in playlist.queue] == [2, 3, 1]

    def test_move_to_beginning(self, playlist_with_items):
        """Move last item to after first (becomes second)"""
        playlist = playlist_with_items
        playlist.move(3, 1)
        assert [item.uid for item in playlist.queue] == [1, 3, 2]

    def test_move_middle_item(self, playlist_with_items):
        """Move middle item forward"""
        playlist = playlist_with_items
        playlist.move(2, 3)
        assert [item.uid for item in playlist.queue] == [1, 3, 2]

    def test_move_to_same_position(self, playlist_with_items):
        """Move item to its current position (after previous item)"""
        playlist = playlist_with_items
        playlist.move(2, 1)
        # Item 2 was after item 1, moving after 1 keeps it in place
        assert [item.uid for item in playlist.queue] == [1, 2, 3]

    def test_move_current_item_resets_to_none(self, playlist_with_items):
        """Moving current item resets current to None (remove behavior)"""
        playlist = playlist_with_items
        playlist.current = 1
        playlist.move(1, 3)
        # Current is reset to None because move() calls remove() which resets it
        assert playlist.current is None

    def test_move_non_existent_raises_error(self, playlist_with_items):
        """Move non-existent item raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.move(999, 1)

    def test_move_after_non_existent_raises_error(self, playlist_with_items):
        """Move after non-existent uid raises ValueError"""
        playlist = playlist_with_items
        with pytest.raises(ValueError):
            playlist.move(1, 999)


class TestPlaylistClear:
    """Test Playlist.clear() method"""

    def test_clear_empty_playlist(self):
        """Clear empty playlist"""
        playlist = Playlist()
        playlist.clear()
        assert len(playlist.queue) == 0
        assert playlist.time == 0
        assert playlist.current is None

    def test_clear_with_items(self, playlist_with_items):
        """Clear playlist with items"""
        playlist = playlist_with_items
        playlist.clear()
        assert len(playlist.queue) == 0

    def test_clear_resets_time(self, playlist_with_items):
        """Clear resets time to 0"""
        playlist = playlist_with_items
        playlist.time = 500
        playlist.clear()
        assert playlist.time == 0

    def test_clear_resets_current(self, playlist_with_items):
        """Clear resets current to None"""
        playlist = playlist_with_items
        playlist.current = 2
        playlist.clear()
        assert playlist.current is None

    def test_clear_resets_current_time(self, playlist_with_items):
        """Clear resets current_time to 0"""
        playlist = playlist_with_items
        playlist.current_time = 45
        playlist.clear()
        assert playlist.current_time == 0

    def test_clear_sets_paused(self, playlist_with_items):
        """Clear sets paused to True"""
        playlist = playlist_with_items
        playlist.paused = False
        playlist.clear()
        assert playlist.paused is True

    def test_clear_preserves_locked(self, playlist_with_items):
        """Clear preserves locked state"""
        playlist = playlist_with_items
        playlist.locked = True
        playlist.clear()
        assert playlist.locked is True


class TestPlaylistEdgeCases:
    """Test Playlist edge cases and error conditions"""

    def test_str_empty_playlist(self):
        """String representation of empty playlist"""
        playlist = Playlist()
        assert str(playlist) == '<playlist []>'

    def test_str_with_items(self, playlist_with_items):
        """String representation with items"""
        playlist = playlist_with_items
        result = str(playlist)
        assert '<playlist [' in result
        assert 'Video 1' in result

    def test_repr_same_as_str(self, playlist_with_items):
        """__repr__ returns same as __str__"""
        playlist = playlist_with_items
        assert repr(playlist) == str(playlist)

    def test_queue_is_mutable_list(self, playlist_with_items):
        """Queue is a mutable list"""
        playlist = playlist_with_items
        assert isinstance(playlist.queue, list)
        len(playlist.queue)
        # Can manipulate directly (though not recommended)
        first = playlist.queue[0]
        assert first.uid == 1

    def test_multiple_operations_sequence(self):
        """Sequence of add, remove, move operations"""
        playlist = Playlist()
        # Add 3 items
        for i in range(1, 4):
            data = {
                'uid': i,
                'temp': False,
                'queueby': 'user',
                'media': {'type': 'yt', 'id': f'v{i}', 'title': f'V{i}', 'seconds': 100}
            }
            playlist.add(None, data)
        # Move item 3 to position 2
        playlist.move(3, 1)
        assert [item.uid for item in playlist.queue] == [1, 3, 2]
        # Remove item 3
        playlist.remove(3)
        assert [item.uid for item in playlist.queue] == [1, 2]
        # Add new item after 1
        new_data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'v10', 'title': 'V10', 'seconds': 100}
        }
        playlist.add(1, new_data)
        assert [item.uid for item in playlist.queue] == [1, 10, 2]

    def test_current_equality_with_int_and_item(self, playlist_with_items):
        """Current item equality works with both int and PlaylistItem"""
        playlist = playlist_with_items
        playlist.current = 2
        # Can compare with int
        assert playlist.current == 2
        # Can compare with PlaylistItem
        item = playlist.get(2)
        assert playlist.current == item
