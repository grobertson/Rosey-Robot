# Event Normalization Specification

**Version**: 1.0  
**Status**: Draft  
**Created**: January 2025  
**Last Updated**: January 2025

## Overview

This document defines the event normalization layer for Rosey-Robot. The normalization layer provides a platform-agnostic event structure that allows components to work with any chat platform (CyTube, Discord, Twitch, etc.) without modification.

### Philosophy

- **NATS Event Bus First**: All inter-layer communication flows through NATS pub/sub - no direct method calls between layers
- **Normalization Always Wins**: Components should use normalized fields whenever possible
- **Platform Agnostic Core**: Bot logic should work with any platform
- **Bi-Directional NATS**: All interactions use NATS channels bi-directionally (request/reply pattern for synchronous operations)
- **Plugin Isolation**: Plugins communicate ONLY via NATS - no direct access to bot internals, database, or other plugins
- **Consistency**: All events follow the same structural pattern
- **Future Proof**: Adding new platforms requires only connection adapter changes

---

## Event Structure Pattern

All normalized events follow this structure:

```python
{
    # Standard normalized fields (PLATFORM AGNOSTIC)
    "user": str,           # Username (always present for user-related events)
    "content": str,        # Message content (for message events)
    "timestamp": int,      # Unix timestamp in seconds
    
    # Event-specific normalized fields
    # ... additional normalized fields ...
    
    # Platform-specific data (OPTIONAL - for plugins)
    "platform_data": {
        # Original platform event data
        # Structure varies by platform
    }
}
```

### Design Principles

1. **NATS-First Communication**: All layers communicate via NATS subjects - bot layer publishes to NATS, database layer subscribes to NATS, plugins only touch NATS
2. **Bi-Directional NATS**: Use request/reply pattern for synchronous operations (e.g., database queries), pub/sub for async events
3. **Layer Isolation**: Bot layer NEVER directly calls database methods - always via NATS. Database layer NEVER directly calls bot methods - always via NATS.
4. **Top-level normalized fields** are consistent across all platforms
5. **Platform-specific data** is wrapped in `platform_data` object
6. **Handlers should prefer** normalized fields over `platform_data`
7. **Plugins may access** `platform_data` for platform-specific features (via NATS events)
8. **Documentation** clearly indicates which fields are normalized vs platform-specific

---

## Normalized Event Types

### 1. Message Event

**Event Name**: `message`

**Normalized Structure**:

```python
{
    "user": "username",           # Sender's username
    "content": "message text",    # Message content
    "timestamp": 1234567890,      # Unix timestamp
    "platform_data": {
        # CyTube example:
        "username": "username",
        "msg": "message text",
        "meta": {...},
        "time": 1234567890000
    }
}
```

**Normalized Fields**:
- `user` (str): Username of message sender
- `content` (str): Message text content
- `timestamp` (int): Unix timestamp in seconds

**Platform-Specific** (in `platform_data`):
- CyTube: `username`, `msg`, `meta`, `time`
- Discord: `author`, `content`, `embeds`, etc.
- Twitch: `display-name`, `message`, `badges`, etc.

**Status**: ✅ Implemented in `lib/connection/cytube.py` line 479  
**TODO**: Complete documentation, add examples for other platforms

---

### 2. User Join Event

**Event Name**: `user_join`

**Current Structure** (INCOMPLETE):

```python
{
    "user": "username",           # Username only
    "timestamp": 1234567890,
    "platform_data": {
        # CyTube user object
        "name": "username",
        "rank": 1,
        "afk": false,
        ...
    }
}
```

**Target Structure** (COMPLETE):

```python
{
    "user": "username",           # Username
    "user_data": {                # Full user object (normalized)
        "username": "username",
        "rank": 1,
        "is_afk": false,
        "is_moderator": false,
        # ... other normalized user fields
    },
    "timestamp": 1234567890,
    "platform_data": {
        # Original platform user object
        "name": "username",
        "rank": 1,
        "afk": false,
        # ... platform-specific fields
    }
}
```

**Normalized Fields** (Target):
- `user` (str): Username
- `user_data` (dict): Full user object with normalized fields
  - `username` (str): Username
  - `rank` (int): User rank/permission level
  - `is_afk` (bool): AFK status
  - `is_moderator` (bool): Moderator status
  - Additional fields as needed

**Status**: ⚠️ INCOMPLETE  
**TODO Marker**: `lib/connection/cytube.py` line 493  
**Required Changes**:
1. Add full `user_data` dict at top level
2. Normalize user object fields (rank, afk, etc.)
3. Update `lib/bot.py` `_on_user_join` to use `user_data` field
4. Update documentation

---

### 3. User Leave Event

**Event Name**: `user_leave`

**Current Structure** (INCOMPLETE):

```python
{
    "user": "username",           # Username (from 'name' field)
    "timestamp": 1234567890,
    "platform_data": {
        "name": "username"
    }
}
```

**Target Structure** (CONSISTENT WITH user_join):

```python
{
    "user": "username",           # Username
    "user_data": {                # Full user object (if available)
        "username": "username",
        # ... normalized fields from userlist
    },
    "timestamp": 1234567890,
    "platform_data": {
        "name": "username"
    }
}
```

**Normalized Fields** (Target):
- `user` (str): Username
- `user_data` (dict, optional): Full user object if available from userlist

**Status**: ⚠️ INCOMPLETE  
**TODO Marker**: `lib/connection/cytube.py` line 505  
**Required Changes**:
1. Add symmetry with `user_join` event
2. Include `user_data` if user is in userlist
3. Update `lib/bot.py` `_on_user_leave` to use normalized structure
4. Remove fallback to `name` field

---

### 4. User List Event

**Event Name**: `user_list`

**Current Structure** (INCORRECT):

```python
{
    "users": ["user1", "user2", "user3"],  # Just usernames (WRONG)
    "timestamp": 1234567890,
    "platform_data": [                      # Full user objects (should be top level)
        {"name": "user1", "rank": 1, ...},
        {"name": "user2", "rank": 0, ...},
        {"name": "user3", "rank": 2, ...}
    ]
}
```

**Target Structure** (CORRECT):

```python
{
    "users": [                              # Full user objects (normalized)
        {
            "username": "user1",
            "rank": 1,
            "is_afk": false,
            "is_moderator": false,
            ...
        },
        {
            "username": "user2",
            "rank": 0,
            "is_afk": false,
            "is_moderator": false,
            ...
        }
    ],
    "timestamp": 1234567890,
    "platform_data": [                      # Original platform user objects
        {"name": "user1", "rank": 1, "afk": false, ...},
        {"name": "user2", "rank": 0, "afk": false, ...}
    ]
}
```

**Normalized Fields** (Target):
- `users` (list[dict]): Array of full user objects with normalized fields
  - Each user object has same structure as `user_data` in user_join

**Status**: ❌ INCORRECT STRUCTURE  
**TODO Marker**: `lib/connection/cytube.py` line 517  
**Required Changes**:
1. **CRITICAL**: Reverse the structure - `users` should have full objects, not strings
2. Normalize user object fields consistently with `user_join`
3. Update `lib/bot.py` `_on_user_list` to use `users` array
4. Update all user iteration logic

---

### 5. PM (Private Message) Event

**Event Name**: `pm`

**Current Structure** (INCOMPLETE):

```python
{
    "user": "sender",             # Sender username
    "content": "message text",    # Message content
    "timestamp": 1234567890,
    "platform_data": {
        "username": "sender",
        "msg": "message text",
        "to": "recipient",
        "meta": {...}
    }
}
```

**Target Structure** (COMPLETE):

```python
{
    "user": "sender",             # Sender username
    "recipient": "recipient",     # Recipient username (NEW)
    "content": "message text",    # Message content
    "timestamp": 1234567890,
    "is_read": false,            # Read status (NEW, optional)
    "platform_data": {
        "username": "sender",
        "msg": "message text",
        "to": "recipient",
        "meta": {...}
    }
}
```

**Normalized Fields** (Target):
- `user` (str): Sender username
- `recipient` (str): Recipient username
- `content` (str): Message text
- `timestamp` (int): Unix timestamp
- `is_read` (bool, optional): Read status for bi-directional PM support

**Status**: ⚠️ INCOMPLETE  
**TODO Marker**: `lib/connection/cytube.py` line 528  
**Required Changes**:
1. Add `recipient` field at top level
2. Consider adding `is_read` for PM management
3. Update PM handlers to use normalized fields
4. Update `common/shell.py` to remove `platform_data` fallback

---

## Migration Guide

### For Component Developers

**DO:**
- ✅ Use normalized fields (`user`, `content`, `timestamp`)
- ✅ Document which normalized fields your component uses
- ✅ Handle missing optional fields gracefully
- ✅ Write platform-agnostic code

**DON'T:**
- ❌ Access `platform_data` in core components
- ❌ Assume platform-specific field names
- ❌ Hard-code CyTube-specific logic
- ❌ Create dependencies on platform structure

### For Plugin Developers

**You MAY:**
- ✅ Access `platform_data` for platform-specific features
- ✅ Check for platform type before using platform-specific data
- ✅ Provide fallbacks if platform-specific data unavailable

**Example Plugin Pattern**:

```python
async def handle_message(self, event, data):
    # Prefer normalized fields
    username = data.get('user', '')
    message = data.get('content', '')
    
    # Access platform_data only if needed
    platform_data = data.get('platform_data', {})
    if 'meta' in platform_data:
        # CyTube-specific: Check for shadow mute
        if platform_data['meta'].get('shadow'):
            return  # Ignore shadow-muted users
    
    # Process message (platform-agnostic)
    if message.startswith('!hello'):
        await self.send_message(f'Hello {username}!')
```

### Migration Steps

1. **Update Connection Adapters**
   - Fix event normalization in `lib/connection/cytube.py`
   - Add normalized fields to all events
   - Ensure consistent structure

2. **Update Bot Event Handlers**
   - Remove `platform_data` access from `lib/bot.py`
   - Use only normalized fields
   - Update handler signatures if needed

3. **Update Components**
   - Remove `platform_data` fallbacks from `common/shell.py`
   - Verify all components use normalized fields
   - Update tests to match new structure

4. **Update Documentation**
   - Update plugin documentation with examples
   - Document all normalized event structures
   - Provide migration examples

5. **Test Thoroughly**
   - Unit tests for normalization layer
   - Integration tests for event handlers
   - Verify backward compatibility

---

## Implementation Checklist

### Phase 1: Connection Layer (CRITICAL)

- [ ] **user_list normalization** (`cytube.py` line 517)
  - [ ] Reverse structure: `users` array gets full objects
  - [ ] Normalize user object fields
  - [ ] Keep `platform_data` with original structure
  - [ ] Update tests

- [ ] **user_join normalization** (`cytube.py` line 493)
  - [ ] Add `user_data` dict at top level
  - [ ] Normalize user fields (rank, afk, etc.)
  - [ ] Update tests

- [ ] **user_leave normalization** (`cytube.py` line 505)
  - [ ] Match structure with `user_join`
  - [ ] Add `user_data` if available from userlist
  - [ ] Update tests

- [ ] **pm normalization** (`cytube.py` line 528)
  - [ ] Add `recipient` field
  - [ ] Consider `is_read` field
  - [ ] Update tests

- [ ] **message normalization** (`cytube.py` line 479)
  - [ ] Verify all fields present
  - [ ] Document structure
  - [ ] Update tests

### Phase 2: Bot Handlers

- [ ] **_on_user_list** (`bot.py` line 267)
  - [ ] Use `data.get('users', [])` instead of `platform_data`
  - [ ] Remove TODO marker after connection layer fixed
  - [ ] Update tests

- [ ] **_on_user_join** (`bot.py` line 285)
  - [ ] Use `data.get('user_data', {})` instead of `platform_data`
  - [ ] Remove fallback to `name` field
  - [ ] Update tests

- [ ] **_on_user_leave** (`bot.py` line 299)
  - [ ] Use only `data.get('user')` field
  - [ ] Remove fallback to `name` field
  - [ ] Update tests

- [ ] **_on_message** (`bot.py` line 309)
  - [ ] Already correct - verify no changes needed
  - [ ] Update documentation
  - [ ] Add as example in this spec

### Phase 3: Components

- [ ] **Shell PM Handler** (`common/shell.py` line 100)
  - [ ] Remove `platform_data` fallback
  - [ ] Use only `user` and `content` fields
  - [ ] Update tests

- [ ] **Other Components**
  - [ ] Audit all event handlers
  - [ ] Remove `platform_data` access
  - [ ] Update documentation

### Phase 4: Documentation

- [ ] **Plugin Documentation** (`lib/plugin/base.py`)
  - [ ] Update event structure examples
  - [ ] Add migration guide
  - [ ] Clarify when to use `platform_data`

- [ ] **Architecture Documentation** (`docs/ARCHITECTURE.md`)
  - [ ] Add normalization layer section
  - [ ] Update event flow diagrams
  - [ ] Document platform adapter responsibilities

- [ ] **This Specification**
  - [ ] Complete all event type examples
  - [ ] Add platform comparison tables
  - [ ] Include real-world examples

### Phase 5: Testing

- [ ] **Unit Tests**
  - [ ] Test each normalized event type
  - [ ] Test missing field handling
  - [ ] Test platform_data presence/absence

- [ ] **Integration Tests**
  - [ ] Test event handlers with normalized events
  - [ ] Test plugin access to platform_data
  - [ ] Test multiple platforms (if available)

- [ ] **Live Testing**
  - [ ] Connect to real CyTube channel
  - [ ] Verify all event handlers work
  - [ ] Test PM commands
  - [ ] Test user list updates

---

## Platform Adapter Requirements

When implementing a new platform adapter, you MUST:

1. **Normalize All Events**
   - Transform platform events to normalized structure
   - Include all required normalized fields
   - Wrap original data in `platform_data`

2. **Follow Event Type Specs**
   - Use exact field names from this specification
   - Include all required fields for each event type
   - Use consistent data types

3. **Document Platform Specifics**
   - Document what's in `platform_data`
   - List any platform-specific limitations
   - Provide example events

4. **Test Thoroughly**
   - Unit test event normalization
   - Integration test with bot handlers
   - Verify field types and presence

### Example Platform Adapter Pattern

```python
class MyPlatformConnection(ConnectionAdapter):
    async def _emit_normalized_event(self, event: str, data: Dict) -> None:
        """Emit event with normalized structure."""
        if event == 'platform_message':
            # Normalize message event
            normalized = {
                'user': data['sender_name'],
                'content': data['text'],
                'timestamp': int(data['created_at'].timestamp()),
                'platform_data': data  # Original platform data
            }
            await self._trigger_callbacks('message', normalized)
        
        elif event == 'platform_user_join':
            # Normalize user join event
            normalized = {
                'user': data['username'],
                'user_data': {
                    'username': data['username'],
                    'rank': data['role_level'],
                    'is_afk': data.get('away', False),
                    'is_moderator': data['role_level'] >= 2
                },
                'timestamp': int(time.time()),
                'platform_data': data
            }
            await self._trigger_callbacks('user_join', normalized)
```

---

## Future Enhancements

### Planned Improvements

1. **Event Versioning**
   - Add `schema_version` field to events
   - Support backward compatibility
   - Allow gradual migration

2. **Richer User Data**
   - Add avatar URL to `user_data`
   - Add user ID (platform-agnostic)
   - Add account creation date

3. **Message Metadata**
   - Add reply-to information
   - Add thread/context information
   - Add reaction support

4. **Platform Detection**
   - Add `platform` field to all events
   - Allow plugins to detect platform type
   - Enable platform-specific behavior

### Long-Term Vision

- **Multi-Platform Support**: Single bot instance connected to multiple platforms
- **Platform Bridge**: Forward events between platforms
- **Unified User Identity**: Track users across platforms
- **Platform-Specific Plugins**: Enable/disable based on platform capabilities

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [lib/plugin/base.py](../lib/plugin/base.py) - Plugin development guide
- [lib/connection/adapter.py](../lib/connection/adapter.py) - Connection adapter interface
- [tests/unit/test_connection_adapter.py](../tests/unit/test_connection_adapter.py) - Adapter tests

---

## Changelog

### Version 1.0 (January 2025) - Draft

- Initial specification
- Documented current state and target state
- Created implementation checklist
- Added migration guide for developers

---

## Appendix: Event Quick Reference

| Event Type | Required Fields | Optional Fields | Status |
|------------|----------------|-----------------|--------|
| `message` | user, content, timestamp | platform_data | ✅ Complete |
| `user_join` | user, user_data, timestamp | platform_data | ⚠️ Incomplete |
| `user_leave` | user, timestamp | user_data, platform_data | ⚠️ Incomplete |
| `user_list` | users, timestamp | platform_data | ❌ Incorrect |
| `pm` | user, recipient, content, timestamp | is_read, platform_data | ⚠️ Incomplete |

**Legend**:
- ✅ Complete: Fully implemented and documented
- ⚠️ Incomplete: Partially implemented, needs work
- ❌ Incorrect: Current structure is wrong, needs fixing

---

**Document Status**: Draft  
**Next Review**: After Phase 1 implementation  
**Maintainer**: Rosey-Robot Team
