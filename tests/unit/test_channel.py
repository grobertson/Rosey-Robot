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

    def test_rank_precision_constant(self):
        """RANK_PRECISION constant is defined"""
        assert Channel.RANK_PRECISION == 1e-4
        assert Channel.RANK_PRECISION == 0.0001


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
        """UserList can be manipulated"""
        user = User('testuser', rank=1.0)
        channel.userlist.add(user)
        assert len(channel.userlist) == 1
        assert channel.userlist.get('testuser').name == 'testuser'

    def test_playlist_operations(self, channel):
        """Playlist can be manipulated"""
        data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 100}
        }
        channel.playlist.add(None, data)
        assert len(channel.playlist.queue) == 1


class TestChannelCheckPermission:
    """Test Channel.check_permission() method"""

    def test_check_permission_success(self, channel_with_permissions, user_regular):
        """User with sufficient rank passes permission check"""
        result = channel_with_permissions.check_permission('queue', user_regular)
        assert result is True

    def test_check_permission_exact_match(self, channel_with_permissions, user_regular):
        """User with exact rank requirement passes"""
        result = channel_with_permissions.check_permission('queue', user_regular)
        assert result is True

    def test_check_permission_higher_rank(self, channel_with_permissions, user_admin):
        """User with higher rank passes all checks"""
        assert channel_with_permissions.check_permission('chat', user_admin) is True
        assert channel_with_permissions.check_permission('queue', user_admin) is True
        assert channel_with_permissions.check_permission('kick', user_admin) is True
        assert channel_with_permissions.check_permission('ban', user_admin) is True

    def test_check_permission_insufficient_rank_throws(self, channel_with_permissions, user_guest):
        """User with insufficient rank raises ChannelPermissionError"""
        with pytest.raises(ChannelPermissionError) as exc_info:
            channel_with_permissions.check_permission('queue', user_guest)
        error_msg = str(exc_info.value)
        assert 'queue' in error_msg
        assert 'permission denied' in error_msg
        assert 'guest' in error_msg
        assert '0.00' in error_msg  # user rank
        assert '1.00' in error_msg  # required rank

    def test_check_permission_with_throw_false(self, channel_with_permissions, user_guest):
        """With throw=False, returns False instead of raising"""
        result = channel_with_permissions.check_permission('queue', user_guest, throw=False)
        assert result is False

    def test_check_permission_unknown_action_raises_valueerror(self, channel_with_permissions, user_admin):
        """Unknown permission action raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            channel_with_permissions.check_permission('unknown_action', user_admin)
        assert 'unknown action' in str(exc_info.value)
        assert 'unknown_action' in str(exc_info.value)

    def test_check_permission_rank_zero(self, channel_with_permissions, user_guest):
        """Rank 0 (guest) can access rank 0 permissions"""
        result = channel_with_permissions.check_permission('chat', user_guest)
        assert result is True

    def test_check_permission_fractional_rank(self, channel_with_permissions):
        """User with fractional rank just below threshold fails"""
        user = User('nearmod', rank=1.49)
        with pytest.raises(ChannelPermissionError):
            channel_with_permissions.check_permission('playlistadd', user)

    def test_check_permission_fractional_rank_passes(self, channel_with_permissions):
        """User with fractional rank at threshold passes"""
        user = User('nearmod', rank=1.5)
        result = channel_with_permissions.check_permission('playlistadd', user)
        assert result is True


class TestChannelHasPermission:
    """Test Channel.has_permission() method"""

    def test_has_permission_is_wrapper(self, channel_with_permissions, user_regular):
        """has_permission calls check_permission with throw=False"""
        result = channel_with_permissions.has_permission('queue', user_regular)
        assert result is True

    def test_has_permission_returns_false_not_exception(self, channel_with_permissions, user_guest):
        """has_permission returns False for insufficient rank (no exception)"""
        result = channel_with_permissions.has_permission('queue', user_guest)
        assert result is False

    def test_has_permission_returns_true(self, channel_with_permissions, user_moderator):
        """has_permission returns True for sufficient rank"""
        result = channel_with_permissions.has_permission('kick', user_moderator)
        assert result is True

    def test_has_permission_unknown_action_still_raises(self, channel_with_permissions, user_admin):
        """has_permission still raises ValueError for unknown actions"""
        with pytest.raises(ValueError):
            channel_with_permissions.has_permission('unknown_action', user_admin)


class TestChannelPermissionEdgeCases:
    """Test Channel permission edge cases and precision"""

    def test_rank_precision_boundary_below(self, channel_with_permissions):
        """User rank just below threshold (considering precision) fails"""
        # Required rank 1.0, user rank 0.9998
        # 0.9998 + 0.0001 = 0.9999 < 1.0, so should fail
        user = User('almostthere', rank=0.9998)
        with pytest.raises(ChannelPermissionError):
            channel_with_permissions.check_permission('queue', user)

    def test_rank_precision_boundary_at(self, channel_with_permissions):
        """User rank at threshold passes"""
        user = User('exactrank', rank=1.0)
        result = channel_with_permissions.check_permission('queue', user)
        assert result is True

    def test_rank_precision_tiny_difference(self, channel_with_permissions):
        """Rank difference smaller than RANK_PRECISION passes"""
        # Required 1.0, user 1.0 - 0.00001 = 0.99999
        # Difference 0.00001 < RANK_PRECISION (0.0001), so should pass
        user = User('tinydiff', rank=0.99999)
        result = channel_with_permissions.check_permission('queue', user)
        assert result is True

    def test_rank_comparison_uses_precision(self):
        """Verify rank comparison formula: user.rank + RANK_PRECISION < min_rank"""
        channel = Channel('test')
        channel.permissions = {'action': 1.0}

        # user.rank = 0.9999, min_rank = 1.0
        # 0.9999 + 0.0001 = 1.0, NOT < 1.0, so PASSES
        user = User('user', rank=0.9999)
        assert channel.check_permission('action', user) is True

        # user.rank = 0.9998, min_rank = 1.0
        # 0.9998 + 0.0001 = 0.9999, IS < 1.0, so FAILS
        user2 = User('user2', rank=0.9998)
        with pytest.raises(ChannelPermissionError):
            channel.check_permission('action', user2)

    def test_multiple_permissions_different_ranks(self):
        """Channel with multiple permission levels"""
        channel = Channel('test')
        channel.permissions = {
            'level0': 0.0,
            'level1': 1.0,
            'level2': 2.0,
            'level3': 3.0
        }
        user = User('mid', rank=2.0)

        # Should pass level0, level1, level2
        assert channel.has_permission('level0', user) is True
        assert channel.has_permission('level1', user) is True
        assert channel.has_permission('level2', user) is True
        # Should fail level3
        assert channel.has_permission('level3', user) is False

    def test_empty_permissions_dict(self, channel, user_admin):
        """Empty permissions dict raises ValueError for any action"""
        with pytest.raises(ValueError):
            channel.check_permission('anything', user_admin)

    def test_permission_check_error_message_format(self, channel_with_permissions):
        """ChannelPermissionError message contains useful info"""
        user = User('testuser', rank=0.5)
        try:
            channel_with_permissions.check_permission('queue', user)
            assert False, "Should have raised ChannelPermissionError"
        except ChannelPermissionError as e:
            msg = str(e)
            assert 'queue' in msg
            assert 'testuser' in msg
            assert 'permission denied' in msg
            assert '0.50' in msg  # user rank formatted
            assert '1.00' in msg  # required rank formatted


class TestChannelIntegration:
    """Test Channel integration with UserList and Playlist"""

    def test_channel_with_users_and_playlist(self):
        """Channel can manage users and playlist simultaneously"""
        channel = Channel('testchannel')

        # Add users
        user1 = User('user1', rank=1.0)
        user2 = User('user2', rank=2.0)
        channel.userlist.add(user1)
        channel.userlist.add(user2)
        assert len(channel.userlist) == 2

        # Add playlist items
        for i in range(1, 3):
            data = {
                'uid': i,
                'temp': False,
                'queueby': f'user{i}',
                'media': {'type': 'yt', 'id': f'v{i}', 'title': f'Video {i}', 'seconds': 100}
            }
            channel.playlist.add(None, data)
        assert len(channel.playlist.queue) == 2

        # Set permissions
        channel.permissions = {'queue': 1.0}

        # Check permissions
        assert channel.has_permission('queue', user1) is True
        assert channel.has_permission('queue', user2) is True

    def test_channel_state_independence(self):
        """Multiple channels maintain independent state"""
        channel1 = Channel('channel1')
        channel2 = Channel('channel2')

        # Modify channel1
        channel1.drink_count = 10
        channel1.permissions = {'chat': 0.0}
        user1 = User('user1', rank=1.0)
        channel1.userlist.add(user1)

        # channel2 should be unaffected
        assert channel2.drink_count == 0
        assert channel2.permissions == {}
        assert len(channel2.userlist) == 0

    def test_channel_full_state_setup(self):
        """Setup complete channel state"""
        channel = Channel('fullchannel', 'password123')

        # Set all attributes
        channel.drink_count = 5
        channel.voteskip_count = 3
        channel.voteskip_need = 5
        channel.motd = 'Welcome!'
        channel.css = '.chat { color: blue; }'
        channel.js = 'alert("hi");'
        channel.emotes = [{'name': 'test', 'image': 'test.png'}]
        channel.permissions = {'chat': 0.0, 'queue': 1.0}
        channel.options = {'allow_voteskip': True}

        # Add users
        channel.userlist.add(User('user1', rank=1.0))

        # Add playlist
        data = {
            'uid': 1,
            'temp': False,
            'queueby': 'user1',
            'media': {'type': 'yt', 'id': 'test', 'title': 'Test', 'seconds': 100}
        }
        channel.playlist.add(None, data)

        # Verify everything
        assert channel.name == 'fullchannel'
        assert channel.password == 'password123'
        assert channel.drink_count == 5
        assert channel.voteskip_count == 3
        assert len(channel.userlist) == 1
        assert len(channel.playlist.queue) == 1
        assert len(channel.permissions) == 2
        assert len(channel.emotes) == 1
