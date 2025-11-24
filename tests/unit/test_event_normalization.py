"""Unit tests for event normalization layer (Sortie 1).

Tests the 5 critical normalization fixes implemented in Sprint 9:
1. Message event documentation (already correct)
2. User join event with user_data field
3. User leave event with optional user_data
4. User list event with objects (BREAKING CHANGE)
5. PM event with recipient field
"""

from lib.connection.cytube import CyTubeConnection


class TestCyTubeUserNormalization:
    """Test the _normalize_cytube_user helper function."""

    def test_normalize_full_user(self):
        """Test normalization with all fields present."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel"
        )

        raw_user = {
            'name': 'alice',
            'rank': 2,
            'afk': False,
            'meta': {'profile': 'test_profile'}
        }

        normalized = conn._normalize_cytube_user(raw_user)

        assert normalized['username'] == 'alice'
        assert normalized['rank'] == 2
        assert normalized['is_afk'] is False
        assert normalized['is_moderator'] is True  # rank >= 2
        assert normalized['meta'] == {'profile': 'test_profile'}

    def test_normalize_guest_user(self):
        """Test normalization for guest users (rank 0)."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel"
        )

        raw_user = {
            'name': 'guest123',
            'rank': 0,
            'afk': False
        }

        normalized = conn._normalize_cytube_user(raw_user)

        assert normalized['username'] == 'guest123'
        assert normalized['rank'] == 0
        assert normalized['is_moderator'] is False  # rank < 2
        assert normalized['meta'] == {}

    def test_normalize_minimal_user(self):
        """Test normalization with minimal fields (defaults)."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel"
        )

        raw_user = {'name': 'bob'}

        normalized = conn._normalize_cytube_user(raw_user)

        assert normalized['username'] == 'bob'
        assert normalized['rank'] == 0  # default
        assert normalized['is_afk'] is False  # default
        assert normalized['is_moderator'] is False
        assert normalized['meta'] == {}


class TestMessageEventNormalization:
    """Test message (chatMsg) event normalization."""

    def test_message_structure(self):
        """Test message event has correct normalized structure."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = {
            'username': 'alice',
            'msg': 'Hello world',
            'time': 1699564800000,  # milliseconds
            'meta': {},
            'other_field': 'platform_specific'
        }

        event_type, normalized = conn._normalize_event('chatMsg', raw_data)

        assert event_type == 'message'
        assert normalized['user'] == 'alice'
        assert normalized['content'] == 'Hello world'
        assert normalized['timestamp'] == 1699564800  # seconds
        assert 'platform_data' in normalized
        assert normalized['platform_data'] == raw_data


class TestUserJoinNormalization:
    """Test user_join (addUser) event normalization with user_data field."""

    def test_user_join_includes_user_data(self):
        """Test user_join includes full user_data object."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = {
            'name': 'charlie',
            'rank': 3,
            'afk': False,
            'time': 1699564800,
            'meta': {'avatar': 'url'}
        }

        event_type, normalized = conn._normalize_event('addUser', raw_data)

        assert event_type == 'user_join'
        assert normalized['user'] == 'charlie'
        assert 'user_data' in normalized
        assert normalized['user_data']['username'] == 'charlie'
        assert normalized['user_data']['rank'] == 3
        assert normalized['user_data']['is_moderator'] is True
        assert normalized['timestamp'] == 1699564800
        assert 'platform_data' in normalized

    def test_user_join_guest(self):
        """Test user_join for guest user."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = {
            'name': 'guest456',
            'rank': 0,
            'afk': False,
            'time': 1699564800
        }

        event_type, normalized = conn._normalize_event('addUser', raw_data)

        assert normalized['user'] == 'guest456'
        assert normalized['user_data']['is_moderator'] is False


class TestUserLeaveNormalization:
    """Test user_leave (userLeave) event normalization with optional user_data."""

    def test_user_leave_with_full_data(self):
        """Test user_leave includes user_data when fields present."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = {
            'name': 'dave',
            'rank': 2,
            'afk': True,
            'time': 1699564800
        }

        event_type, normalized = conn._normalize_event('userLeave', raw_data)

        assert event_type == 'user_leave'
        assert normalized['user'] == 'dave'
        assert 'user_data' in normalized
        assert normalized['user_data']['username'] == 'dave'
        assert normalized['user_data']['is_afk'] is True
        assert normalized['timestamp'] == 1699564800

    def test_user_leave_minimal(self):
        """Test user_leave without user_data when only name present."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = {
            'name': 'eve',
            'time': 1699564800
        }

        event_type, normalized = conn._normalize_event('userLeave', raw_data)

        assert normalized['user'] == 'eve'
        assert 'user_data' not in normalized  # Optional field absent
        assert normalized['timestamp'] == 1699564800


class TestUserListNormalization:
    """Test user_list (userlist) event normalization - BREAKING CHANGE."""

    def test_user_list_returns_objects_not_strings(self):
        """Test user_list returns array of user objects (not strings)."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = [
            {'name': 'alice', 'rank': 3, 'afk': False},
            {'name': 'bob', 'rank': 0, 'afk': True},
            {'name': 'charlie', 'rank': 2, 'afk': False}
        ]

        event_type, normalized = conn._normalize_event('userlist', raw_data)

        assert event_type == 'user_list'
        assert normalized['count'] == 3
        assert len(normalized['users']) == 3

        # ⚠️ BREAKING CHANGE: users are objects, not strings
        for user in normalized['users']:
            assert isinstance(user, dict)
            assert 'username' in user
            assert 'rank' in user
            assert 'is_moderator' in user

        # Verify specific users
        assert normalized['users'][0]['username'] == 'alice'
        assert normalized['users'][0]['is_moderator'] is True
        assert normalized['users'][1]['username'] == 'bob'
        assert normalized['users'][1]['is_afk'] is True

    def test_user_list_empty(self):
        """Test user_list with empty channel."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        raw_data = []

        event_type, normalized = conn._normalize_event('userlist', raw_data)

        assert normalized['count'] == 0
        assert normalized['users'] == []


class TestPMNormalization:
    """Test PM event normalization with recipient field."""

    def test_pm_includes_recipient(self):
        """Test PM event includes recipient field."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )
        conn.user_name = 'rosey_bot'  # Set bot name

        raw_data = {
            'username': 'frank',
            'msg': 'Hello bot!',
            'time': 1699564800000
        }

        event_type, normalized = conn._normalize_event('pm', raw_data)

        assert event_type == 'pm'
        assert normalized['user'] == 'frank'
        assert normalized['recipient'] == 'rosey_bot'
        assert normalized['content'] == 'Hello bot!'
        assert normalized['timestamp'] == 1699564800
        assert 'platform_data' in normalized

    def test_pm_without_user_name(self):
        """Test PM when bot user_name not set (fallback to 'bot')."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )
        # Don't set user_name (None)

        raw_data = {
            'username': 'grace',
            'msg': 'Test message',
            'time': 1699564800000
        }

        event_type, normalized = conn._normalize_event('pm', raw_data)

        assert normalized['recipient'] == 'bot'  # Fallback value


class TestNormalizationConsistency:
    """Test consistency across all normalized events."""

    def test_all_events_have_platform_data(self):
        """Test all normalized events include platform_data field."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        test_cases = [
            ('chatMsg', {'username': 'test', 'msg': 'hi', 'time': 0}),
            ('addUser', {'name': 'test', 'rank': 0, 'time': 0}),
            ('userLeave', {'name': 'test', 'time': 0}),
            ('userlist', [{'name': 'test', 'rank': 0}]),
            ('pm', {'username': 'test', 'msg': 'hi', 'time': 0})
        ]

        for event, data in test_cases:
            _, normalized = conn._normalize_event(event, data)
            assert 'platform_data' in normalized, f"{event} missing platform_data"

    def test_timestamp_conversion(self):
        """Test timestamp conversion from milliseconds to seconds."""
        conn = CyTubeConnection(
            domain="https://test.server",
            channel="test_channel",

        )

        # CyTube uses milliseconds
        ms_timestamp = 1699564800000
        expected_seconds = 1699564800

        test_cases = [
            ('chatMsg', {'username': 'test', 'msg': 'hi', 'time': ms_timestamp}),
            ('pm', {'username': 'test', 'msg': 'hi', 'time': ms_timestamp})
        ]

        for event, data in test_cases:
            _, normalized = conn._normalize_event(event, data)
            assert normalized['timestamp'] == expected_seconds
