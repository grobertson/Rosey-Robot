# SPEC: lib/user.py Tests

**Sprint:** nano-sprint/4-test-assured  
**Commit:** 2 - User Tests  
**Dependencies:** Commit 1 (Infrastructure)  
**Estimated Effort:** Small

---

## Objective

Create comprehensive unit tests for `lib/user.py`, covering the `User` and `UserList` classes. This is the simplest core module and serves as a good starting point for establishing test patterns.

**Target Coverage:** 95% (User is straightforward with minimal edge cases)

---

## Module Analysis

### User Class
- **Purpose:** Represents a CyTube user with rank, profile, and metadata
- **Key Features:**
  - Rank-based permissions (float)
  - Profile (image, text)
  - Meta (afk, muted, smuted, ip, aliases)
  - IP cloaking/uncloaking
  - Equality comparison
- **Complexity:** Low (mostly data container with properties)

### UserList Class
- **Purpose:** Dictionary-based collection of users with leader tracking
- **Key Features:**
  - Add/get users by name
  - Leader management
  - Raises ValueError on duplicates/missing users
- **Complexity:** Low (thin wrapper around dict)

---

## Changes Required

### 1. Create Test File

**File:** `tests/unit/test_user.py` (new)

```python
"""
Unit tests for lib/user.py

Tests the User and UserList classes.
"""
import pytest
from lib.user import User, UserList


class TestUserInit:
    """Test User initialization."""
    
    def test_default_init(self):
        """Test User with default values."""
        user = User()
        assert user.name == ''
        assert user.password is None
        assert user.rank == -1
        assert user.image == ''
        assert user.text == ''
        assert user.afk is False
        assert user.muted is False
        assert user.smuted is False
        assert user.ip is None
        assert user.uncloaked_ip is None
        assert user.aliases == []
    
    def test_init_with_name_and_rank(self):
        """Test User with name and rank."""
        user = User(name='TestUser', rank=2.5)
        assert user.name == 'TestUser'
        assert user.rank == 2.5
    
    def test_init_with_password(self):
        """Test User with password."""
        user = User(name='TestUser', password='secret123')
        assert user.password == 'secret123'
    
    def test_init_with_profile(self):
        """Test User with profile data."""
        profile = {'image': 'avatar.png', 'text': 'Hello!'}
        user = User(profile=profile)
        assert user.image == 'avatar.png'
        assert user.text == 'Hello!'
    
    def test_init_with_meta(self):
        """Test User with metadata."""
        meta = {
            'afk': True,
            'muted': True,
            'smuted': False,
            'ip': '192.168.1.1',
            'aliases': ['Alt1', 'Alt2']
        }
        user = User(meta=meta)
        assert user.afk is True
        assert user.muted is True
        assert user.smuted is False
        assert user.aliases == ['Alt1', 'Alt2']


class TestUserProperties:
    """Test User property getters and setters."""
    
    def test_profile_getter(self):
        """Test profile property returns dict."""
        user = User()
        user.image = 'test.png'
        user.text = 'Test text'
        profile = user.profile
        assert profile == {'image': 'test.png', 'text': 'Test text'}
    
    def test_profile_setter(self):
        """Test profile property setter."""
        user = User()
        user.profile = {'image': 'new.png', 'text': 'New text'}
        assert user.image == 'new.png'
        assert user.text == 'New text'
    
    def test_profile_setter_none(self):
        """Test profile setter with None."""
        user = User()
        user.profile = None
        assert user.image == ''
        assert user.text == ''
    
    def test_profile_setter_partial(self):
        """Test profile setter with partial data."""
        user = User()
        user.profile = {'image': 'only_image.png'}
        assert user.image == 'only_image.png'
        assert user.text == ''
    
    def test_meta_getter(self):
        """Test meta property returns dict."""
        user = User()
        user.afk = True
        user.muted = False
        user.smuted = True
        user.ip = '10.0.0.1'
        user.aliases = ['Alias1']
        meta = user.meta
        assert meta['afk'] is True
        assert meta['muted'] is False
        assert meta['smuted'] is True
        assert meta['ip'] == '10.0.0.1'
        assert meta['aliases'] == ['Alias1']
    
    def test_meta_setter(self):
        """Test meta property setter."""
        user = User()
        meta = {
            'afk': True,
            'muted': True,
            'smuted': False,
            'ip': '172.16.0.1',
            'aliases': ['Test']
        }
        user.meta = meta
        assert user.afk is True
        assert user.muted is True
        assert user.smuted is False
        assert user.ip == '172.16.0.1'
        assert user.aliases == ['Test']
    
    def test_meta_setter_none(self):
        """Test meta setter with None."""
        user = User()
        user.meta = None
        assert user.afk is False
        assert user.muted is False
        assert user.smuted is False
        assert user.ip is None
        assert user.aliases == []
    
    def test_ip_property_sets_uncloaked(self):
        """Test that setting ip also sets uncloaked_ip."""
        user = User()
        user.ip = '192.168.1.1.hidden'
        assert user.ip == '192.168.1.1.hidden'
        # uncloaked_ip is set by uncloak_ip utility
        assert user.uncloaked_ip is not None
    
    def test_ip_property_none_clears_uncloaked(self):
        """Test that setting ip to None clears uncloaked_ip."""
        user = User()
        user.ip = '192.168.1.1'
        assert user.uncloaked_ip is not None
        user.ip = None
        assert user.ip is None
        assert user.uncloaked_ip is None


class TestUserUpdate:
    """Test User update method."""
    
    def test_update_name(self):
        """Test updating name."""
        user = User(name='OldName')
        user.update(name='NewName')
        assert user.name == 'NewName'
    
    def test_update_rank(self):
        """Test updating rank."""
        user = User(rank=1.0)
        user.update(rank=3.0)
        assert user.rank == 3.0
    
    def test_update_profile(self):
        """Test updating profile."""
        user = User()
        user.update(profile={'image': 'updated.png', 'text': 'Updated!'})
        assert user.image == 'updated.png'
        assert user.text == 'Updated!'
    
    def test_update_meta(self):
        """Test updating metadata."""
        user = User()
        user.update(meta={'afk': True, 'muted': True})
        assert user.afk is True
        assert user.muted is True
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        user = User(name='Old', rank=1.0)
        user.update(
            name='New',
            rank=2.5,
            profile={'image': 'new.png'},
            meta={'afk': True}
        )
        assert user.name == 'New'
        assert user.rank == 2.5
        assert user.image == 'new.png'
        assert user.afk is True
    
    def test_update_with_none_values_ignored(self):
        """Test that None values don't update fields."""
        user = User(name='Original', rank=5.0)
        user.update(name=None, rank=None)
        assert user.name == 'Original'
        assert user.rank == 5.0


class TestUserStringRepresentation:
    """Test User __str__ and __repr__."""
    
    def test_str_without_ip(self):
        """Test string representation without IP."""
        user = User(name='TestUser', rank=2.5)
        result = str(user)
        assert 'TestUser' in result
        assert '2.5' in result
        assert result.startswith('<user')
    
    def test_str_with_ip(self):
        """Test string representation with IP."""
        user = User(name='TestUser', rank=2.5)
        user.ip = '192.168.1.1'
        result = str(user)
        assert 'TestUser' in result
        assert '2.5' in result
        assert '192.168.1.1' in result
    
    def test_repr_equals_str(self):
        """Test that __repr__ equals __str__."""
        user = User(name='TestUser', rank=1.0)
        assert repr(user) == str(user)


class TestUserEquality:
    """Test User equality comparisons."""
    
    def test_equal_to_user_with_same_name(self):
        """Test User equals another User with same name."""
        user1 = User(name='TestUser', rank=1.0)
        user2 = User(name='TestUser', rank=2.0)  # Different rank, same name
        assert user1 == user2
    
    def test_not_equal_to_user_with_different_name(self):
        """Test User not equal to User with different name."""
        user1 = User(name='User1')
        user2 = User(name='User2')
        assert user1 != user2
    
    def test_equal_to_string(self):
        """Test User equals string (username)."""
        user = User(name='TestUser')
        assert user == 'TestUser'
    
    def test_not_equal_to_different_string(self):
        """Test User not equal to different string."""
        user = User(name='TestUser')
        assert user != 'OtherUser'
    
    def test_not_equal_to_other_types(self):
        """Test User not equal to non-User, non-string types."""
        user = User(name='TestUser')
        assert user != 123
        assert user != None
        assert user != ['TestUser']
        assert user != {'name': 'TestUser'}


class TestUserList:
    """Test UserList class."""
    
    def test_init(self):
        """Test UserList initialization."""
        userlist = UserList()
        assert userlist.count == 0
        assert userlist.leader is None
        assert len(userlist) == 0
    
    def test_add_user(self):
        """Test adding a user."""
        userlist = UserList()
        user = User(name='TestUser')
        userlist.add(user)
        assert 'TestUser' in userlist
        assert userlist['TestUser'] == user
    
    def test_add_duplicate_raises_error(self):
        """Test adding duplicate user raises ValueError."""
        userlist = UserList()
        user1 = User(name='TestUser')
        user2 = User(name='TestUser')
        userlist.add(user1)
        with pytest.raises(ValueError, match='user exists'):
            userlist.add(user2)
    
    def test_get_existing_user(self):
        """Test getting existing user."""
        userlist = UserList()
        user = User(name='TestUser')
        userlist.add(user)
        retrieved = userlist.get('TestUser')
        assert retrieved == user
    
    def test_get_nonexistent_user_raises_error(self):
        """Test getting nonexistent user raises ValueError."""
        userlist = UserList()
        with pytest.raises(ValueError, match='no user with name'):
            userlist.get('NonExistent')
    
    def test_leader_setter_with_user_object(self):
        """Test setting leader with User object."""
        userlist = UserList()
        user = User(name='Leader')
        userlist.add(user)
        userlist.leader = user
        assert userlist.leader == user
    
    def test_leader_setter_with_username(self):
        """Test setting leader with username string."""
        userlist = UserList()
        user = User(name='Leader')
        userlist.add(user)
        userlist.leader = 'Leader'
        assert userlist.leader == user
    
    def test_leader_setter_none(self):
        """Test setting leader to None."""
        userlist = UserList()
        user = User(name='Leader')
        userlist.add(user)
        userlist.leader = user
        userlist.leader = None
        assert userlist.leader is None
    
    def test_userlist_as_dict(self):
        """Test UserList behaves as dictionary."""
        userlist = UserList()
        user1 = User(name='User1')
        user2 = User(name='User2')
        userlist.add(user1)
        userlist.add(user2)
        
        assert len(userlist) == 2
        assert 'User1' in userlist
        assert 'User2' in userlist
        assert list(userlist.keys()) == ['User1', 'User2']
        assert list(userlist.values()) == [user1, user2]


class TestUserEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_user_with_zero_rank(self):
        """Test user with rank 0.0."""
        user = User(name='Guest', rank=0.0)
        assert user.rank == 0.0
    
    def test_user_with_negative_rank(self):
        """Test user with negative rank."""
        user = User(rank=-1)
        assert user.rank == -1
    
    def test_user_with_high_rank(self):
        """Test user with high rank (admin/owner)."""
        user = User(name='Owner', rank=5.0)
        assert user.rank == 5.0
    
    def test_user_with_fractional_rank(self):
        """Test user with fractional rank."""
        user = User(name='Mod', rank=2.5)
        assert user.rank == 2.5
    
    def test_user_with_empty_profile(self):
        """Test user with empty profile dict."""
        user = User(profile={})
        assert user.image == ''
        assert user.text == ''
    
    def test_user_with_empty_meta(self):
        """Test user with empty meta dict."""
        user = User(meta={})
        assert user.afk is False
        assert user.muted is False
        assert user.smuted is False
        assert user.ip is None
        assert user.aliases == []
    
    def test_user_name_with_special_characters(self):
        """Test user with special characters in name."""
        user = User(name='User[123]')
        assert user.name == 'User[123]'
    
    def test_user_with_very_long_name(self):
        """Test user with very long username."""
        long_name = 'A' * 1000
        user = User(name=long_name)
        assert user.name == long_name
    
    def test_profile_text_multiline(self):
        """Test profile text with multiple lines."""
        user = User()
        user.profile = {'text': 'Line 1\nLine 2\nLine 3'}
        assert user.text == 'Line 1\nLine 2\nLine 3'
    
    def test_aliases_empty_list(self):
        """Test aliases with empty list."""
        user = User(meta={'aliases': []})
        assert user.aliases == []
    
    def test_aliases_multiple_entries(self):
        """Test aliases with multiple entries."""
        aliases = ['Alt1', 'Alt2', 'Alt3', 'Alt4']
        user = User(meta={'aliases': aliases})
        assert user.aliases == aliases
```

---

## Testing Checklist

### Manual Verification

1. **Run tests**
   ```bash
   pytest tests/unit/test_user.py -v
   ```
   Expected: All tests pass

2. **Check coverage**
   ```bash
   pytest tests/unit/test_user.py --cov=lib.user --cov-report=term-missing
   ```
   Expected: >95% coverage

3. **Run with markers**
   ```bash
   pytest tests/unit/test_user.py -m unit
   ```
   Expected: All tests run (all marked as unit)

4. **Run specific test class**
   ```bash
   pytest tests/unit/test_user.py::TestUserInit -v
   ```
   Expected: 5 tests in TestUserInit pass

---

## Success Criteria

- ✅ `tests/unit/test_user.py` created
- ✅ All tests pass (40+ tests)
- ✅ Coverage >95% for lib/user.py
- ✅ Tests cover:
  - User initialization (all parameters)
  - Property getters/setters (profile, meta, ip)
  - Update method (all parameters)
  - String representation
  - Equality comparisons
  - UserList add/get/leader operations
  - Edge cases (special names, empty values, boundaries)
- ✅ No test warnings or errors

---

## Coverage Analysis

**Expected Coverage Breakdown:**

| Component | Lines | Covered | % |
|-----------|-------|---------|---|
| User.__init__ | 15 | 15 | 100% |
| User properties | 30 | 30 | 100% |
| User.update | 10 | 10 | 100% |
| User.__str__ | 5 | 5 | 100% |
| User.__eq__ | 8 | 8 | 100% |
| UserList methods | 20 | 19 | 95% |

**Uncovered Lines (acceptable):**
- Rare error conditions that are hard to trigger
- Defensive code that shouldn't be reached

---

## Notes

- **Test Organization:** Tests grouped by functionality (init, properties, update, etc.)
- **Naming Convention:** Test names describe what they test in plain English
- **Edge Cases:** Special attention to rank values (0, negative, fractional)
- **IP Handling:** Tests verify ip property also sets uncloaked_ip
- **UserList:** Tests verify both User and string inputs for leader

---

## Next Steps

After this commit:
1. Pattern established for unit tests
2. Move to **SPEC-Commit-3: lib/util.py Tests** (MessageParser)
3. Continue with remaining lib/ modules
4. Maintain similar test organization and coverage standards
