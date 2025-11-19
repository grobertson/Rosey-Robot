# SPEC-Commit-6: lib/channel.py Tests

## Objective
Create comprehensive unit tests for `lib/channel.py`, covering channel initialization, state management, user lists, playlists, and permission checking system. The Channel class is the core container for all CyTube channel state.

## Target Coverage
- **Overall**: 95%
- **Channel.__init__**: 100%
- **Channel.check_permission**: 100%
- **Channel.has_permission**: 100%

## Module Analysis

**File**: `lib/channel.py`

**Key Components**:
1. **Channel Class**
   - Complexity: Medium (permission system + state management)
   - Attributes:
     * Identification: name, password
     * Counters: drink_count, voteskip_count, voteskip_need
     * Content: motd (message of day), css, js, emotes
     * Configuration: permissions (dict), options (dict)
     * Collections: userlist (UserList), playlist (Playlist)
   - Methods:
     * `check_permission(action, user, throw=True)`: Verify user rank ≥ required rank
     * `has_permission(action, user)`: Wrapper calling check_permission with throw=False
   - Constants: RANK_PRECISION = 1e-4 (for floating point comparison)

2. **Permission System**
   - Permissions dict maps action names to minimum rank (float)
   - Rank comparison uses RANK_PRECISION to handle floating point imprecision
   - Throws ChannelPermissionError if permission denied (throw=True)
   - Returns bool if throw=False
   - Raises ValueError for unknown actions

**Dependencies**:
- `lib.playlist.Playlist`
- `lib.user.UserList`, `lib.user.User`
- `lib.error.ChannelPermissionError`

**Edge Cases**:
- Permission checking: Exact rank match (with RANK_PRECISION), rank just below/above threshold
- Unknown permissions (ValueError)
- Empty permissions dict
- User rank 0.0 (guest)
- Floating point precision (user.rank = 2.9999999)

## Test File Structure

**File**: `tests/unit/test_channel.py`

**Test Classes**:
1. `TestChannelInit` - Initialization with defaults and custom values
2. `TestChannelStringRepresentation` - __str__, __repr__
3. `TestChannelAttributes` - Setting/getting channel state
4. `TestChannelCheckPermission` - Permission checking with throw=True
5. `TestChannelHasPermission` - Permission checking with throw=False
6. `TestChannelPermissionEdgeCases` - Rank precision, boundary conditions
7. `TestChannelIntegration` - UserList and Playlist integration

## Implementation

### tests/unit/test_channel.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
from lib.channel import Channel
from lib.user import User, UserList
from lib.playlist import Playlist
from lib.error import ChannelPermissionError


@pytest.fixture
def channel():
    """Basic channel instance"""
    return Channel('testchannel')


@pytest.fixture
def channel_with_password():
    """Channel with password"""
    return Channel('privatechannel', 'secret123')


@pytest.fixture
def channel_with_permissions():
    """Channel with configured permissions"""
    channel = Channel('testchannel')
    channel.permissions = {
        'chat': 0.0,
        'queue': 1.0,
        'playlistdelete': 2.0,
        'playlistadd': 1.5,
        'kick': 3.0,
        'ban': 4.0
    }
    return channel


@pytest.fixture
def user_guest():
    """Guest user (rank 0)"""
    return User('guest', rank=0.0)


@pytest.fixture
def user_regular():
    """Regular user (rank 1)"""
    return User('regular', rank=1.0)


@pytest.fixture
def user_moderator():
    """Moderator user (rank 3)"""
    return User('moderator', rank=3.0)


@pytest.fixture
def user_admin():
    """Admin user (rank 5)"""
    return User('admin', rank=5.0)


class TestChannelInit:
    """Test Channel initialization"""

    def test_init_default(self):
        """Create channel with default values"""
        channel = Channel()
        assert channel.name == ''
        assert channel.password is None
        assert channel.drink_count == 0
        assert channel.voteskip_count == 0
        assert channel.voteskip_need == 0
        assert channel.motd == ''
        assert channel.css == ''
        assert channel.js == ''
        assert channel.emotes == []
        assert channel.permissions == {}
        assert channel.options == {}
        assert isinstance(channel.userlist, UserList)
        assert isinstance(channel.playlist, Playlist)

    def test_init_with_name(self):
        """Create channel with name"""
        channel = Channel('testchannel')
        assert channel.name == 'testchannel'
        assert channel.password is None

    def test_init_with_name_and_password(self):
        """Create channel with name and password"""
        channel = Channel('privatechannel', 'secret123')
        assert channel.name == 'privatechannel'
        assert channel.password == 'secret123'

    def test_init_empty_name(self):
        """Create channel with empty name"""
        channel = Channel('')
        assert channel.name == ''

    def test_init_userlist_is_new_instance(self):
        """Each channel gets its own UserList instance"""
        channel1 = Channel('channel1')
        channel2 = Channel('channel2')
        assert channel1.userlist is not channel2.userlist

    def test_init_playlist_is_new_instance(self):
        """Each channel gets its own Playlist instance"""
        channel1 = Channel('channel1')
        channel2 = Channel('channel2')
        assert channel1.playlist is not channel2.playlist


class TestChannelStringRepresentation:
    """Test Channel string representations"""

    def test_str(self, channel):
        """Test __str__ format"""
        assert str(channel) == '<channel "testchannel">'

    def test_str_empty_name(self):
        """Test __str__ with empty name"""
        channel = Channel('')
        assert str(channel) == '<channel "">'

    def test_str_special_characters(self):
        """Test __str__ with special characters in name"""
        channel = Channel('test-channel_123')
        assert str(channel) == '<channel "test-channel_123">'

    def test_repr_same_as_str(self, channel):
        """Test __repr__ returns same as __str__"""
        assert repr(channel) == str(channel)


class TestChannelAttributes:
    """Test Channel attribute management"""

    def test_set_drink_count(self, channel):
        """Set drink counter"""
        channel.drink_count = 42
        assert channel.drink_count == 42

    def test_set_voteskip_counts(self, channel):
        """Set voteskip counters"""
        channel.voteskip_count = 5
        channel.voteskip_need = 10
        assert channel.voteskip_count == 5
        assert channel.voteskip_need == 10

    def test_set_motd(self, channel):
        """Set message of the day"""
        channel.motd = 'Welcome to the channel!'
        assert channel.motd == 'Welcome to the channel!'

    def test_set_css(self, channel):
        """Set channel CSS"""
        channel.css = 'body { background: black; }'
        assert channel.css == 'body { background: black; }'

    def test_set_js(self, channel):
        """Set channel JavaScript"""
        channel.js = 'console.log("Hello");'
        assert channel.js == 'console.log("Hello");'

    def test_set_emotes(self, channel):
        """Set channel emotes list"""
        emotes = [
            {'name': 'Kappa', 'image': 'kappa.png'},
            {'name': 'PogChamp', 'image': 'pogchamp.png'}
        ]
        channel.emotes = emotes
        assert len(channel.emotes) == 2
        assert channel.emotes[0]['name'] == 'Kappa'

    def test_set_permissions(self, channel):
        """Set permissions dict"""
        permissions = {'chat': 0.0, 'queue': 1.0}
        channel.permissions = permissions
        assert channel.permissions['chat'] == 0.0
        assert channel.permissions['queue'] == 1.0

    def test_set_options(self, channel):
        """Set options dict"""
        options = {'allow_voteskip': True, 'max_queue': 50}
        channel.options = options
        assert channel.options['allow_voteskip'] is True
        assert channel.options['max_queue'] == 50

    def test_userlist_operations(self, channel):
        """Add users to channel userlist"""
        user = User('testuser', rank=1.0)
        channel.userlist.add(user)
        assert 'testuser' in channel.userlist
        assert channel.userlist['testuser'].rank == 1.0

    def test_playlist_operations(self, channel):
        """Add items to channel playlist"""
        item_data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {
                'type': 'yt',
                'id': 'test123',
                'title': 'Test Video',
                'seconds': 180
            }
        }
        channel.playlist.add(None, item_data)
        assert len(channel.playlist.queue) == 1


class TestChannelCheckPermission:
    """Test Channel.check_permission method with throw=True (default)"""

    def test_check_permission_sufficient_rank(self, channel_with_permissions, user_regular):
        """User with sufficient rank passes permission check"""
        result = channel_with_permissions.check_permission('queue', user_regular)
        assert result is True

    def test_check_permission_exact_rank(self, channel_with_permissions, user_regular):
        """User with exact minimum rank passes permission check"""
        # user_regular has rank 1.0, 'queue' requires 1.0
        result = channel_with_permissions.check_permission('queue', user_regular)
        assert result is True

    def test_check_permission_higher_rank(self, channel_with_permissions, user_admin):
        """User with rank higher than required passes permission check"""
        # admin (rank 5) should pass all permission checks
        assert channel_with_permissions.check_permission('chat', user_admin) is True
        assert channel_with_permissions.check_permission('queue', user_admin) is True
        assert channel_with_permissions.check_permission('ban', user_admin) is True

    def test_check_permission_insufficient_rank_throws(self, channel_with_permissions, user_guest):
        """User with insufficient rank raises ChannelPermissionError"""
        with pytest.raises(ChannelPermissionError) as exc_info:
            channel_with_permissions.check_permission('queue', user_guest)
        error_msg = str(exc_info.value)
        assert 'queue' in error_msg
        assert 'guest' in error_msg
        assert 'permission denied' in error_msg

    def test_check_permission_unknown_action_throws(self, channel_with_permissions, user_regular):
        """Unknown permission action raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            channel_with_permissions.check_permission('unknown_action', user_regular)
        assert 'unknown action' in str(exc_info.value)
        assert 'unknown_action' in str(exc_info.value)

    def test_check_permission_empty_permissions_dict(self, channel, user_regular):
        """Empty permissions dict raises ValueError for any action"""
        with pytest.raises(ValueError):
            channel.check_permission('chat', user_regular)

    def test_check_permission_guest_can_chat(self, channel_with_permissions, user_guest):
        """Guest (rank 0) can use actions with rank 0 requirement"""
        # 'chat' requires rank 0.0
        result = channel_with_permissions.check_permission('chat', user_guest)
        assert result is True

    def test_check_permission_moderator_can_kick(self, channel_with_permissions, user_moderator):
        """Moderator (rank 3) can kick (requires rank 3)"""
        result = channel_with_permissions.check_permission('kick', user_moderator)
        assert result is True

    def test_check_permission_moderator_cannot_ban(self, channel_with_permissions, user_moderator):
        """Moderator (rank 3) cannot ban (requires rank 4)"""
        with pytest.raises(ChannelPermissionError):
            channel_with_permissions.check_permission('ban', user_moderator)


class TestChannelHasPermission:
    """Test Channel.has_permission method (throw=False wrapper)"""

    def test_has_permission_sufficient_rank_returns_true(self, channel_with_permissions, user_regular):
        """User with sufficient rank returns True"""
        result = channel_with_permissions.has_permission('queue', user_regular)
        assert result is True

    def test_has_permission_insufficient_rank_returns_false(self, channel_with_permissions, user_guest):
        """User with insufficient rank returns False (no exception)"""
        result = channel_with_permissions.has_permission('queue', user_guest)
        assert result is False

    def test_has_permission_unknown_action_still_throws(self, channel_with_permissions, user_regular):
        """Unknown action still raises ValueError even with has_permission"""
        with pytest.raises(ValueError):
            channel_with_permissions.has_permission('unknown_action', user_regular)

    def test_has_permission_guest(self, channel_with_permissions, user_guest):
        """Guest can chat but cannot queue"""
        assert channel_with_permissions.has_permission('chat', user_guest) is True
        assert channel_with_permissions.has_permission('queue', user_guest) is False

    def test_has_permission_moderator(self, channel_with_permissions, user_moderator):
        """Moderator permission check results"""
        assert channel_with_permissions.has_permission('chat', user_moderator) is True
        assert channel_with_permissions.has_permission('queue', user_moderator) is True
        assert channel_with_permissions.has_permission('kick', user_moderator) is True
        assert channel_with_permissions.has_permission('ban', user_moderator) is False

    def test_has_permission_admin(self, channel_with_permissions, user_admin):
        """Admin has all permissions"""
        assert channel_with_permissions.has_permission('chat', user_admin) is True
        assert channel_with_permissions.has_permission('queue', user_admin) is True
        assert channel_with_permissions.has_permission('kick', user_admin) is True
        assert channel_with_permissions.has_permission('ban', user_admin) is True


class TestChannelPermissionEdgeCases:
    """Test Channel permission edge cases and rank precision"""

    def test_rank_precision_constant(self):
        """Verify RANK_PRECISION constant value"""
        assert Channel.RANK_PRECISION == 1e-4
        assert Channel.RANK_PRECISION == 0.0001

    def test_permission_rank_just_below_threshold(self, channel_with_permissions):
        """User with rank just below threshold fails (within RANK_PRECISION)"""
        # 'queue' requires 1.0, user has 0.99999 (below threshold)
        user = User('almostthere', rank=0.99999)
        with pytest.raises(ChannelPermissionError):
            channel_with_permissions.check_permission('queue', user)

    def test_permission_rank_just_above_threshold(self, channel_with_permissions):
        """User with rank just above threshold passes"""
        # 'queue' requires 1.0, user has 1.00001 (above threshold)
        user = User('justmadeit', rank=1.00001)
        result = channel_with_permissions.check_permission('queue', user)
        assert result is True

    def test_permission_rank_within_precision(self, channel_with_permissions):
        """User with rank within RANK_PRECISION of threshold"""
        # 'queue' requires 1.0, user has 0.99995 (within precision)
        user = User('almostthere', rank=0.99995)
        with pytest.raises(ChannelPermissionError):
            channel_with_permissions.check_permission('queue', user)

    def test_permission_fractional_ranks(self, channel_with_permissions):
        """Test with fractional rank requirements"""
        # 'playlistadd' requires 1.5
        user_15 = User('user15', rank=1.5)
        user_14 = User('user14', rank=1.4)
        user_16 = User('user16', rank=1.6)
        
        assert channel_with_permissions.has_permission('playlistadd', user_15) is True
        assert channel_with_permissions.has_permission('playlistadd', user_14) is False
        assert channel_with_permissions.has_permission('playlistadd', user_16) is True

    def test_permission_zero_rank_requirement(self, channel_with_permissions):
        """Test actions with 0.0 rank requirement (open to all)"""
        user_zero = User('guest', rank=0.0)
        user_negative = User('negative', rank=-1.0)
        
        # 'chat' requires 0.0
        assert channel_with_permissions.has_permission('chat', user_zero) is True
        # Negative rank should fail (0.0 + RANK_PRECISION > -1.0)
        assert channel_with_permissions.has_permission('chat', user_negative) is False

    def test_permission_high_rank_requirement(self, channel_with_permissions):
        """Test actions with high rank requirements"""
        user_39 = User('almostban', rank=3.9)
        user_40 = User('canban', rank=4.0)
        
        # 'ban' requires 4.0
        assert channel_with_permissions.has_permission('ban', user_39) is False
        assert channel_with_permissions.has_permission('ban', user_40) is True

    def test_permission_error_message_format(self, channel_with_permissions, user_guest):
        """Verify ChannelPermissionError message format"""
        with pytest.raises(ChannelPermissionError) as exc_info:
            channel_with_permissions.check_permission('kick', user_guest)
        
        error_msg = str(exc_info.value)
        assert 'kick' in error_msg  # Action name
        assert 'guest' in error_msg  # User name
        assert 'permission denied' in error_msg
        assert '0.00' in error_msg  # User rank (formatted)
        assert '3.00' in error_msg  # Required rank (formatted)


class TestChannelIntegration:
    """Integration tests for Channel with UserList and Playlist"""

    def test_channel_userlist_integration(self, channel):
        """Channel userlist works with multiple users"""
        user1 = User('user1', rank=1.0)
        user2 = User('user2', rank=2.0)
        user3 = User('user3', rank=3.0)
        
        channel.userlist.add(user1)
        channel.userlist.add(user2)
        channel.userlist.add(user3)
        
        assert len(channel.userlist) == 3
        assert 'user1' in channel.userlist
        assert channel.userlist['user2'].rank == 2.0

    def test_channel_playlist_integration(self, channel):
        """Channel playlist works with multiple items"""
        for i in range(1, 4):
            item_data = {
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
            channel.playlist.add(None, item_data)
        
        assert len(channel.playlist.queue) == 3
        assert channel.playlist.queue[0].title == 'Video 1'

    def test_channel_permission_with_userlist_user(self, channel_with_permissions):
        """Check permissions for user in channel userlist"""
        user = User('channeluser', rank=2.0)
        channel_with_permissions.userlist.add(user)
        
        # Get user from userlist and check permission
        userlist_user = channel_with_permissions.userlist['channeluser']
        result = channel_with_permissions.check_permission('playlistdelete', userlist_user)
        assert result is True

    def test_channel_full_state(self, channel):
        """Channel maintains full state correctly"""
        channel.name = 'mychannel'
        channel.password = 'secret'
        channel.drink_count = 10
        channel.voteskip_count = 3
        channel.voteskip_need = 5
        channel.motd = 'Welcome!'
        channel.css = 'body { color: red; }'
        channel.js = 'alert("hi");'
        channel.emotes = [{'name': 'Kappa', 'image': 'kappa.png'}]
        channel.permissions = {'chat': 0.0}
        channel.options = {'allow_voteskip': True}
        
        user = User('testuser', rank=1.0)
        channel.userlist.add(user)
        
        # Verify all state preserved
        assert channel.name == 'mychannel'
        assert channel.password == 'secret'
        assert channel.drink_count == 10
        assert len(channel.emotes) == 1
        assert 'testuser' in channel.userlist
```

## Coverage Analysis

| Component | Expected Coverage | Justification |
|-----------|------------------|---------------|
| Channel.__init__ | 100% | 6 tests: default, name, name+password, empty name, separate instances |
| Channel.__str__ | 100% | 3 tests: basic, empty name, special chars |
| Channel.__repr__ | 100% | 1 test: same as __str__ |
| Channel.check_permission | 100% | 9 tests: sufficient rank, exact rank, higher rank, insufficient (throws), unknown action, empty dict, various rank levels |
| Channel.has_permission | 100% | 6 tests: sufficient (True), insufficient (False), unknown action, guest/mod/admin permission sets |
| Attribute management | 100% | 10 tests: drink_count, voteskip, motd, css, js, emotes, permissions, options, userlist, playlist |
| Permission edge cases | 100% | 7 tests: RANK_PRECISION, just below/above threshold, fractional ranks, zero/high requirements, error format |
| Integration | 100% | 4 tests: userlist operations, playlist operations, permission with userlist user, full state |

**Overall Expected Coverage**: 98%

## Manual Verification

### Run Tests

```bash
# Run channel tests only
pytest tests/unit/test_channel.py -v

# Run with coverage
pytest tests/unit/test_channel.py --cov=lib.channel --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_channel.py::TestChannelCheckPermission -v

# Run permission edge case tests
pytest tests/unit/test_channel.py::TestChannelPermissionEdgeCases -v
```

### Expected Output

```
tests/unit/test_channel.py::TestChannelInit::test_init_default PASSED
tests/unit/test_channel.py::TestChannelCheckPermission::test_check_permission_sufficient_rank PASSED
tests/unit/test_channel.py::TestChannelPermissionEdgeCases::test_rank_precision_constant PASSED
[... 60+ more tests ...]
tests/unit/test_channel.py::TestChannelIntegration::test_channel_full_state PASSED

---------- coverage: platform win32, python 3.x -----------
Name              Stmts   Miss  Cover   Missing
-----------------------------------------------
lib/channel.py       39      1    97%   78
-----------------------------------------------
TOTAL                39      1    97%
```

### Sample Test Execution

```python
# Test Channel initialization
from lib.channel import Channel

channel = Channel('testchannel', 'password')
assert channel.name == 'testchannel'
assert channel.password == 'password'
assert len(channel.userlist) == 0
assert len(channel.playlist.queue) == 0

# Test permissions
from lib.user import User
from lib.error import ChannelPermissionError

channel.permissions = {'queue': 1.0, 'kick': 3.0}

guest = User('guest', rank=0.0)
regular = User('regular', rank=1.0)
mod = User('mod', rank=3.0)

# has_permission (returns bool)
assert channel.has_permission('queue', regular) is True
assert channel.has_permission('queue', guest) is False

# check_permission (throws exception)
assert channel.check_permission('kick', mod) is True
try:
    channel.check_permission('kick', regular)
    assert False, "Should have raised ChannelPermissionError"
except ChannelPermissionError as e:
    assert 'permission denied' in str(e)
```

## Success Criteria

- [ ] All 65+ tests pass
- [ ] Coverage ≥ 95% for lib/channel.py
- [ ] Permission system works correctly with RANK_PRECISION
- [ ] check_permission and has_permission behave correctly (throw vs return)
- [ ] UserList and Playlist integration works
- [ ] Edge cases covered: floating point precision, boundary ranks, unknown actions
- [ ] No regression in existing functionality

## Dependencies
- SPEC-Commit-1: Test infrastructure (conftest.py, pytest.ini)
- SPEC-Commit-2: User tests (dependency)
- SPEC-Commit-5: Playlist tests (dependency)

## Next Steps
After completing channel tests:
1. Proceed to SPEC-Commit-7: lib/bot.py Tests (MOST COMPLEX)
2. Verify Channel is used correctly in bot module
3. Consider integration tests for channel state updates from socket events
