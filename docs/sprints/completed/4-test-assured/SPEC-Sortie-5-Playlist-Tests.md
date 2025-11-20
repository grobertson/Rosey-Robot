# SPEC-Commit-5: lib/playlist.py Tests

## Objective
Create comprehensive unit tests for `lib/playlist.py`, covering playlist management, item operations (add/remove/move), state tracking (current item, time, paused/locked), and the PlaylistItem class. This module manages the CyTube channel playlist queue.

## Target Coverage
- **Overall**: 95%
- **PlaylistItem**: 100%
- **Playlist**: 95%
- **Playlist operations**: 100%

## Module Analysis

**File**: `lib/playlist.py`

**Key Components**:
1. **PlaylistItem Class**
   - Complexity: Low (data container)
   - Attributes: uid (ID), temp (temporary), username (queueby), link (MediaLink), title, duration
   - Constructor: Takes dict with nested media data
   - String representations: `__str__` (formatted), `__repr__` (same as str)
   - Equality: Compares by uid, supports comparison to int

2. **Playlist Class**
   - Complexity: Medium (queue management with state)
   - Attributes: time (total duration), current (current item), current_time, locked, paused, queue (list of items)
   - Current property: Setter accepts uid (int) or PlaylistItem, getter returns PlaylistItem or None
   - Operations:
     * `index(uid)`: Get index of item by uid (raises ValueError if missing)
     * `get(uid)`: Get PlaylistItem by uid (raises ValueError if missing)
     * `remove(item)`: Remove item, resets current if removing current item
     * `add(after, item)`: Insert item after uid or append if None
     * `move(item, after)`: Reorder item (remove + add)
     * `clear()`: Reset playlist state and empty queue

**Dependencies**:
- `lib.media_link.MediaLink`

**Edge Cases**:
- PlaylistItem: Missing keys in data dict, nested media structure
- Playlist.current setter: int vs PlaylistItem, None, non-existent uid
- Playlist operations: Empty queue, non-existent items, moving to same position
- Playlist.remove: Removing current item (resets state)
- Playlist.add: after=None (append), after=uid (insert)

## Test File Structure

**File**: `tests/unit/test_playlist.py`

**Test Classes**:
1. `TestPlaylistItemInit` - Constructor and attribute extraction
2. `TestPlaylistItemStringRepresentation` - __str__, __repr__, __eq__
3. `TestPlaylistInit` - Playlist initialization
4. `TestPlaylistCurrentProperty` - Current item getter/setter
5. `TestPlaylistIndex` - Finding item index
6. `TestPlaylistGet` - Getting items by uid
7. `TestPlaylistAdd` - Adding items (append and insert)
8. `TestPlaylistRemove` - Removing items
9. `TestPlaylistMove` - Moving/reordering items
10. `TestPlaylistClear` - Clearing playlist
11. `TestPlaylistEdgeCases` - Error handling and boundary conditions

## Implementation

### tests/unit/test_playlist.py

```python
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
        """Test equality for items with same uid"""
        data1 = {
            'uid': 1,
            'temp': False,
            'queueby': 'user1',
            'media': {'type': 'yt', 'id': 'vid1', 'title': 'Video 1', 'seconds': 60}
        }
        data2 = {
            'uid': 1,
            'temp': True,
            'queueby': 'user2',
            'media': {'type': 'yt', 'id': 'vid2', 'title': 'Video 2', 'seconds': 120}
        }
        item1 = PlaylistItem(data1)
        item2 = PlaylistItem(data2)
        assert item1 == item2  # Equal by uid only

    def test_eq_different_uid(self, sample_item):
        """Test inequality for items with different uid"""
        data = {
            'uid': 2,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 60}
        }
        item2 = PlaylistItem(data)
        assert sample_item != item2

    def test_eq_with_int(self, sample_item):
        """Test equality comparison with int (uid)"""
        assert sample_item == 1
        assert sample_item != 2

    def test_eq_with_non_playlistitem(self, sample_item):
        """Test inequality with non-PlaylistItem objects"""
        assert sample_item != "1"
        assert sample_item != {'uid': 1}
        assert sample_item != [1]


class TestPlaylistInit:
    """Test Playlist initialization"""

    def test_init_empty(self):
        """Create empty Playlist with default values"""
        playlist = Playlist()
        assert playlist.time == 0
        assert playlist.locked is False
        assert playlist.paused is True
        assert playlist.current_time == 0
        assert playlist.current is None
        assert playlist.queue == []

    def test_str_empty(self):
        """Test __str__ for empty playlist"""
        playlist = Playlist()
        assert str(playlist) == '<playlist []>'

    def test_repr_same_as_str(self):
        """Test __repr__ returns same as __str__"""
        playlist = Playlist()
        assert repr(playlist) == str(playlist)


class TestPlaylistCurrentProperty:
    """Test Playlist current item property"""

    def test_current_getter_initial(self):
        """Get current item when None"""
        playlist = Playlist()
        assert playlist.current is None

    def test_current_setter_playlistitem(self, playlist_with_items):
        """Set current item using PlaylistItem"""
        item = playlist_with_items.queue[0]
        playlist_with_items.current = item
        assert playlist_with_items.current is item

    def test_current_setter_int(self, playlist_with_items):
        """Set current item using uid (int)"""
        playlist_with_items.current = 2
        assert playlist_with_items.current.uid == 2

    def test_current_setter_none(self, playlist_with_items):
        """Set current item to None"""
        playlist_with_items.current = playlist_with_items.queue[0]
        playlist_with_items.current = None
        assert playlist_with_items.current is None

    def test_current_setter_int_lookup(self, playlist_with_items):
        """Setting current with int calls get() to lookup item"""
        playlist_with_items.current = 1
        assert isinstance(playlist_with_items.current, PlaylistItem)
        assert playlist_with_items.current.uid == 1


class TestPlaylistIndex:
    """Test Playlist.index method"""

    def test_index_first_item(self, playlist_with_items):
        """Get index of first item"""
        assert playlist_with_items.index(1) == 0

    def test_index_middle_item(self, playlist_with_items):
        """Get index of middle item"""
        assert playlist_with_items.index(2) == 1

    def test_index_last_item(self, playlist_with_items):
        """Get index of last item"""
        assert playlist_with_items.index(3) == 2

    def test_index_nonexistent(self, playlist_with_items):
        """Get index of non-existent item raises ValueError"""
        with pytest.raises(ValueError):
            playlist_with_items.index(999)

    def test_index_empty_playlist(self):
        """Get index from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.index(1)


class TestPlaylistGet:
    """Test Playlist.get method"""

    def test_get_first_item(self, playlist_with_items):
        """Get first item by uid"""
        item = playlist_with_items.get(1)
        assert item.uid == 1
        assert item.title == 'Video 1'

    def test_get_middle_item(self, playlist_with_items):
        """Get middle item by uid"""
        item = playlist_with_items.get(2)
        assert item.uid == 2
        assert item.title == 'Video 2'

    def test_get_last_item(self, playlist_with_items):
        """Get last item by uid"""
        item = playlist_with_items.get(3)
        assert item.uid == 3
        assert item.title == 'Video 3'

    def test_get_returns_playlistitem(self, playlist_with_items):
        """Get returns PlaylistItem instance"""
        item = playlist_with_items.get(1)
        assert isinstance(item, PlaylistItem)

    def test_get_nonexistent(self, playlist_with_items):
        """Get non-existent item raises ValueError"""
        with pytest.raises(ValueError):
            playlist_with_items.get(999)

    def test_get_empty_playlist(self):
        """Get from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.get(1)


class TestPlaylistAdd:
    """Test Playlist.add method"""

    def test_add_to_empty_playlist(self, sample_item_data):
        """Add item to empty playlist (after=None)"""
        playlist = Playlist()
        playlist.add(None, sample_item_data)
        assert len(playlist.queue) == 1
        assert playlist.queue[0].uid == 1

    def test_add_appends_when_after_none(self, playlist_with_items):
        """Add with after=None appends to end"""
        data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 100}
        }
        playlist_with_items.add(None, data)
        assert len(playlist_with_items.queue) == 4
        assert playlist_with_items.queue[-1].uid == 10

    def test_add_inserts_after_item(self, playlist_with_items):
        """Add item after specific uid"""
        data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 100}
        }
        playlist_with_items.add(1, data)  # After uid 1 (index 0)
        assert len(playlist_with_items.queue) == 4
        assert playlist_with_items.queue[1].uid == 10  # Inserted at index 1

    def test_add_after_middle_item(self, playlist_with_items):
        """Add item after middle item"""
        data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 100}
        }
        playlist_with_items.add(2, data)  # After uid 2 (index 1)
        assert playlist_with_items.queue[2].uid == 10

    def test_add_after_last_item(self, playlist_with_items):
        """Add item after last item"""
        data = {
            'uid': 10,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'new', 'title': 'New', 'seconds': 100}
        }
        playlist_with_items.add(3, data)  # After uid 3 (index 2)
        assert playlist_with_items.queue[3].uid == 10

    def test_add_playlistitem_instance(self, playlist_with_items, sample_item_data):
        """Add PlaylistItem instance directly"""
        item = PlaylistItem(sample_item_data)
        item.uid = 20
        playlist_with_items.add(None, item)
        assert len(playlist_with_items.queue) == 4
        assert playlist_with_items.queue[-1] is item

    def test_add_converts_dict_to_playlistitem(self, sample_item_data):
        """Add with dict converts to PlaylistItem"""
        playlist = Playlist()
        playlist.add(None, sample_item_data)
        assert isinstance(playlist.queue[0], PlaylistItem)


class TestPlaylistRemove:
    """Test Playlist.remove method"""

    def test_remove_first_item(self, playlist_with_items):
        """Remove first item"""
        playlist_with_items.remove(1)
        assert len(playlist_with_items.queue) == 2
        assert playlist_with_items.queue[0].uid == 2

    def test_remove_middle_item(self, playlist_with_items):
        """Remove middle item"""
        playlist_with_items.remove(2)
        assert len(playlist_with_items.queue) == 2
        assert playlist_with_items.queue[0].uid == 1
        assert playlist_with_items.queue[1].uid == 3

    def test_remove_last_item(self, playlist_with_items):
        """Remove last item"""
        playlist_with_items.remove(3)
        assert len(playlist_with_items.queue) == 2
        assert playlist_with_items.queue[-1].uid == 2

    def test_remove_by_playlistitem(self, playlist_with_items):
        """Remove using PlaylistItem instance"""
        item = playlist_with_items.queue[1]
        playlist_with_items.remove(item)
        assert len(playlist_with_items.queue) == 2

    def test_remove_current_item_resets_state(self, playlist_with_items):
        """Removing current item resets current, current_time, and pauses"""
        playlist_with_items.current = 2
        playlist_with_items.current_time = 30
        playlist_with_items.paused = False
        
        playlist_with_items.remove(2)
        
        assert playlist_with_items.current is None
        assert playlist_with_items.current_time == 0
        assert playlist_with_items.paused is True

    def test_remove_non_current_item_preserves_current(self, playlist_with_items):
        """Removing non-current item preserves current item"""
        playlist_with_items.current = 2
        playlist_with_items.remove(1)
        assert playlist_with_items.current.uid == 2

    def test_remove_nonexistent(self, playlist_with_items):
        """Remove non-existent item raises ValueError"""
        with pytest.raises(ValueError):
            playlist_with_items.remove(999)

    def test_remove_from_empty_playlist(self):
        """Remove from empty playlist raises ValueError"""
        playlist = Playlist()
        with pytest.raises(ValueError):
            playlist.remove(1)


class TestPlaylistMove:
    """Test Playlist.move method"""

    def test_move_item_forward(self, playlist_with_items):
        """Move item forward in queue"""
        playlist_with_items.move(1, 2)  # Move uid 1 after uid 2
        assert playlist_with_items.queue[0].uid == 2
        assert playlist_with_items.queue[1].uid == 1
        assert playlist_with_items.queue[2].uid == 3

    def test_move_item_backward(self, playlist_with_items):
        """Move item backward in queue"""
        playlist_with_items.move(3, 1)  # Move uid 3 after uid 1
        assert playlist_with_items.queue[0].uid == 1
        assert playlist_with_items.queue[1].uid == 3
        assert playlist_with_items.queue[2].uid == 2

    def test_move_to_end(self, playlist_with_items):
        """Move item to end (after last item)"""
        playlist_with_items.move(1, 3)
        assert playlist_with_items.queue[-1].uid == 1

    def test_move_to_beginning(self, playlist_with_items):
        """Move item to beginning (after=None not supported, but we can test after first)"""
        # Move uid 3 to position after uid 1 (effectively moving it up)
        playlist_with_items.move(3, 1)
        assert playlist_with_items.queue[1].uid == 3

    def test_move_preserves_item(self, playlist_with_items):
        """Move preserves item data"""
        original_title = playlist_with_items.get(2).title
        playlist_with_items.move(2, 1)
        moved_item = playlist_with_items.get(2)
        assert moved_item.title == original_title

    def test_move_nonexistent_item(self, playlist_with_items):
        """Move non-existent item raises ValueError"""
        with pytest.raises(ValueError):
            playlist_with_items.move(999, 1)

    def test_move_to_nonexistent_after(self, playlist_with_items):
        """Move to non-existent after position raises ValueError"""
        with pytest.raises(ValueError):
            playlist_with_items.move(1, 999)


class TestPlaylistClear:
    """Test Playlist.clear method"""

    def test_clear_empties_queue(self, playlist_with_items):
        """Clear removes all items from queue"""
        playlist_with_items.clear()
        assert playlist_with_items.queue == []

    def test_clear_resets_time(self, playlist_with_items):
        """Clear resets time to 0"""
        playlist_with_items.time = 500
        playlist_with_items.clear()
        assert playlist_with_items.time == 0

    def test_clear_resets_current(self, playlist_with_items):
        """Clear resets current to None"""
        playlist_with_items.current = 2
        playlist_with_items.clear()
        assert playlist_with_items.current is None

    def test_clear_resets_current_time(self, playlist_with_items):
        """Clear resets current_time to 0"""
        playlist_with_items.current_time = 120
        playlist_with_items.clear()
        assert playlist_with_items.current_time == 0

    def test_clear_sets_paused(self, playlist_with_items):
        """Clear sets paused to True"""
        playlist_with_items.paused = False
        playlist_with_items.clear()
        assert playlist_with_items.paused is True

    def test_clear_empty_playlist(self):
        """Clear empty playlist (no-op)"""
        playlist = Playlist()
        playlist.clear()
        assert playlist.queue == []
        assert playlist.time == 0


class TestPlaylistEdgeCases:
    """Test Playlist edge cases and error scenarios"""

    def test_add_multiple_items_same_uid(self):
        """Add multiple items with same uid (allowed, but unusual)"""
        playlist = Playlist()
        data1 = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'vid1', 'title': 'Video 1', 'seconds': 60}
        }
        data2 = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'vid2', 'title': 'Video 2', 'seconds': 60}
        }
        playlist.add(None, data1)
        playlist.add(None, data2)
        # Both should be added, index() will find first match
        assert len(playlist.queue) == 2

    def test_str_with_items(self, playlist_with_items):
        """Test __str__ contains queue"""
        result = str(playlist_with_items)
        assert '<playlist' in result
        assert '[' in result

    def test_current_setter_looks_up_item(self, playlist_with_items):
        """Setting current with uid looks up item via get()"""
        # This tests the internal get() call in current.setter
        playlist_with_items.current = 2
        assert playlist_with_items.current.title == 'Video 2'

    def test_locked_attribute(self):
        """Test locked attribute can be set"""
        playlist = Playlist()
        assert playlist.locked is False
        playlist.locked = True
        assert playlist.locked is True

    def test_paused_attribute(self):
        """Test paused attribute can be set"""
        playlist = Playlist()
        assert playlist.paused is True
        playlist.paused = False
        assert playlist.paused is False

    def test_time_attribute(self):
        """Test time attribute can be set"""
        playlist = Playlist()
        playlist.time = 600
        assert playlist.time == 600

    def test_current_time_attribute(self):
        """Test current_time attribute can be set"""
        playlist = Playlist()
        playlist.current_time = 45
        assert playlist.current_time == 45
```

## Coverage Analysis

| Component | Expected Coverage | Justification |
|-----------|------------------|---------------|
| PlaylistItem.__init__ | 100% | 6 tests: basic, media link, temp, types, zero duration, long title |
| PlaylistItem.__str__ | 100% | 2 tests: basic format, different values |
| PlaylistItem.__repr__ | 100% | 1 test: same as __str__ |
| PlaylistItem.__eq__ | 100% | 4 tests: same uid, different uid, int comparison, non-PlaylistItem |
| Playlist.__init__ | 100% | 1 test: default values |
| Playlist.__str__ | 100% | 2 tests: empty, with items |
| Playlist.__repr__ | 100% | 1 test: same as __str__ |
| Playlist.current property | 100% | 5 tests: getter, setter (PlaylistItem/int/None), lookup |
| Playlist.index | 100% | 5 tests: first/middle/last, nonexistent, empty |
| Playlist.get | 100% | 6 tests: first/middle/last, returns PlaylistItem, nonexistent, empty |
| Playlist.add | 100% | 7 tests: empty, append (None), insert (after), PlaylistItem/dict |
| Playlist.remove | 100% | 8 tests: first/middle/last, PlaylistItem, current reset, nonexistent |
| Playlist.move | 100% | 7 tests: forward/backward, to end, preserves data, nonexistent |
| Playlist.clear | 100% | 6 tests: queue, time, current, current_time, paused, empty |
| Edge cases | 100% | 6 tests: duplicate uid, locked, paused, time, current_time |

**Overall Expected Coverage**: 98%

## Manual Verification

### Run Tests

```bash
# Run playlist tests only
pytest tests/unit/test_playlist.py -v

# Run with coverage
pytest tests/unit/test_playlist.py --cov=lib.playlist --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_playlist.py::TestPlaylistAdd -v

# Run operation tests
pytest tests/unit/test_playlist.py::TestPlaylistMove tests/unit/test_playlist.py::TestPlaylistRemove -v
```

### Expected Output

```
tests/unit/test_playlist.py::TestPlaylistItemInit::test_init_basic PASSED
tests/unit/test_playlist.py::TestPlaylistAdd::test_add_to_empty_playlist PASSED
tests/unit/test_playlist.py::TestPlaylistMove::test_move_item_forward PASSED
[... 60+ more tests ...]
tests/unit/test_playlist.py::TestPlaylistEdgeCases::test_current_time_attribute PASSED

---------- coverage: platform win32, python 3.x -----------
Name               Stmts   Miss  Cover   Missing
------------------------------------------------
lib/playlist.py       67      1    98%   42
------------------------------------------------
TOTAL                 67      1    98%
```

### Sample Test Execution

```python
# Test PlaylistItem
from lib.playlist import PlaylistItem

data = {
    'uid': 1,
    'temp': False,
    'queueby': 'user',
    'media': {
        'type': 'yt',
        'id': 'dQw4w9WgXcQ',
        'title': 'Test Video',
        'seconds': 180
    }
}
item = PlaylistItem(data)
assert item.uid == 1
assert item.title == 'Test Video'
assert item.link.type == 'yt'
assert str(item) == '<playlist item #1 "Test Video">'

# Test Playlist operations
from lib.playlist import Playlist

playlist = Playlist()
playlist.add(None, data)
assert len(playlist.queue) == 1

playlist.current = 1
assert playlist.current.uid == 1

playlist.remove(1)
assert len(playlist.queue) == 0
assert playlist.current is None
```

## Success Criteria

- [ ] All 65+ tests pass
- [ ] Coverage ≥ 95% for lib/playlist.py
- [ ] PlaylistItem correctly parses nested media data
- [ ] Playlist operations (add/remove/move) work correctly
- [ ] Current item state management works (reset on remove)
- [ ] Edge cases covered: empty playlist, non-existent items, duplicate uids
- [ ] No regression in existing functionality

## Dependencies
- SPEC-Commit-1: Test infrastructure (conftest.py, pytest.ini)
- SPEC-Commit-4: MediaLink tests (dependency)

## Next Steps
After completing playlist tests:
1. Proceed to SPEC-Commit-6: lib/channel.py Tests
2. Verify Playlist is used correctly in channel/bot modules
3. Consider integration tests for playlist state changes
