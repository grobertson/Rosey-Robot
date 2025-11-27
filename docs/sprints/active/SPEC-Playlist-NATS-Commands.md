---
title: Playlist Command Integration via NATS Event Bus
version: 1.0
date_created: 2025-11-27
owner: Rosey-Robot Team
tags: [architecture, event-bus, cytube, playlist]
---

# Introduction

This specification defines the implementation of outbound playlist manipulation commands through the NATS event bus for the CytubeConnector. Currently, the connector only receives playlist events from CyTube (inbound) and has minimal outbound control (only video skip). This spec adds bidirectional playlist control via standardized NATS command subjects.

## 1. Purpose & Scope

**Purpose:** Enable bot components and plugins to manipulate CyTube playlists through the NATS event bus instead of direct channel API calls, completing the event-driven architecture migration.

**Scope:**
- Add NATS command subjects for playlist operations (add, remove, move, jump)
- Implement command handlers in CytubeConnector to translate NATS commands to CyTube API calls
- Add inbound event handlers for delete and moveVideo events (currently missing)
- Migrate all shell commands to use NATS instead of direct channel API calls
- Update tests to verify command flow

**Out of Scope:**
- UI/frontend changes
- Database persistence of playlist state
- Playlist history/undo functionality
- Advanced playlist features (shuffle, repeat modes)

**Intended Audience:** Developers working on bot core, plugins, and event bus architecture

## 2. Definitions

- **NATS**: Message bus system used for inter-component communication
- **CytubeConnector**: Component that bridges CyTube WebSocket events and NATS event bus
- **Event Bus**: High-level wrapper around NATS (event_bus.py)
- **Subject**: NATS routing key (e.g., `rosey.platform.cytube.send.playlist.add`)
- **Inbound**: Events flowing from CyTube → Connector → NATS → Bot/Plugins
- **Outbound**: Commands flowing from Bot/Plugins → NATS → Connector → CyTube
- **Request/Reply**: NATS pattern where command sender waits for acknowledgment

## 3. Requirements, Constraints & Guidelines

### Requirements

#### Inbound Event Handlers (Currently Missing)

- **REQ-001**: Implement `_on_delete()` handler for CyTube "delete" events
- **REQ-002**: Implement `_on_move_video()` handler for CyTube "moveVideo" events
- **REQ-003**: Register delete and moveVideo handlers in `_register_cytube_handlers()`
- **REQ-004**: Add handlers to `_event_handlers` dict for cleanup
- **REQ-005**: Publish delete events to `rosey.platform.cytube.delete` subject
- **REQ-006**: Publish moveVideo events to `rosey.platform.cytube.moveVideo` subject

#### Outbound Command Subjects

- **REQ-007**: Define command subject hierarchy under `rosey.platform.cytube.send.playlist.*`
- **REQ-008**: Support fire-and-forget commands (publish only, no reply expected)
- **REQ-009**: Support request/reply commands (synchronous confirmation)
- **REQ-010**: All commands must include correlation_id for tracing

#### Command Types

- **REQ-011**: Implement `playlist.add` - Add video to playlist
- **REQ-012**: Implement `playlist.remove` - Remove video from playlist
- **REQ-013**: Implement `playlist.move` - Reorder videos in playlist
- **REQ-014**: Implement `playlist.jump` - Skip to specific video
- **REQ-015**: Implement `playlist.clear` - Remove all videos (moderator only)
- **REQ-016**: Implement `playlist.shuffle` - Randomize playlist order

#### Error Handling

- **REQ-017**: Commands must validate required fields before execution
- **REQ-018**: Failed commands must publish error events to `rosey.platform.cytube.error`
- **REQ-019**: Include original correlation_id in error events
- **REQ-020**: Log all command failures with context

#### Security

- **SEC-001**: Playlist commands must not bypass CyTube's permission system
- **SEC-002**: Connector must rely on CyTube server to enforce permissions
- **SEC-003**: Commands must not expose internal CyTube authentication tokens
- **SEC-004**: Rate limiting handled by CyTube, not connector

### Constraints

- **CON-001**: Cannot break existing inbound playlist event flow
- **CON-002**: CyTube API methods must be called asynchronously (within connector only)
- **CON-003**: Command handlers must not block event loop
- **CON-004**: Must handle CyTube disconnection gracefully (reject commands with error events)
- **CON-005**: Direct channel API calls are anti-pattern outside CytubeConnector core

### Guidelines

- **GUD-001**: Follow existing event bus patterns from PM and chat implementations
- **GUD-002**: Use descriptive error messages for command validation failures
- **GUD-003**: Include video metadata in event payloads where available
- **GUD-004**: Prefer fire-and-forget for UI-triggered actions (faster response)
- **GUD-005**: Use request/reply for plugin automation (verify success)

### Patterns

- **PAT-001**: Command subject pattern: `rosey.platform.cytube.send.playlist.{action}`
- **PAT-002**: Error event pattern: Publish to `rosey.platform.cytube.error` with original subject in metadata
- **PAT-003**: Event data structure: `{"command": "action", "params": {...}, "correlation_id": "uuid"}`
- **PAT-004**: Use CytubeEvent wrapper for all CyTube → NATS events

## 4. Interfaces & Data Contracts

### NATS Subject Hierarchy

```
rosey.platform.cytube.send.playlist.add       # Add video to playlist
rosey.platform.cytube.send.playlist.remove    # Remove video from playlist
rosey.platform.cytube.send.playlist.move      # Reorder video in playlist
rosey.platform.cytube.send.playlist.jump      # Jump to specific video
rosey.platform.cytube.send.playlist.clear     # Clear entire playlist
rosey.platform.cytube.send.playlist.shuffle   # Shuffle playlist order
rosey.platform.cytube.error                   # Command execution errors
```

### Inbound Event Subjects (New)

```
rosey.platform.cytube.delete                  # Video deleted from playlist
rosey.platform.cytube.moveVideo               # Video moved in playlist
```

### Command Data Structures

#### playlist.add
```json
{
  "command": "playlist.add",
  "params": {
    "type": "yt",              // Media type (yt, vm, dm, etc.)
    "id": "dQw4w9WgXcQ",       // Video ID
    "position": "end",         // "end" | "next" | "after:<uid>"
    "temporary": false         // Temporary vs permanent (default: false)
  },
  "correlation_id": "uuid",
  "source": "shell" | "plugin_name"
}
```

#### playlist.remove
```json
{
  "command": "playlist.remove",
  "params": {
    "uid": "abc123"            // Unique playlist item ID
  },
  "correlation_id": "uuid",
  "source": "shell"
}
```

#### playlist.move
```json
{
  "command": "playlist.move",
  "params": {
    "uid": "abc123",           // Item to move
    "after": "xyz789"          // Move after this item (or "prepend")
  },
  "correlation_id": "uuid",
  "source": "shell"
}
```

#### playlist.jump
```json
{
  "command": "playlist.jump",
  "params": {
    "uid": "abc123"            // Item to jump to
  },
  "correlation_id": "uuid",
  "source": "shell"
}
```

#### playlist.clear
```json
{
  "command": "playlist.clear",
  "params": {},
  "correlation_id": "uuid",
  "source": "shell"
}
```

#### playlist.shuffle
```json
{
  "command": "playlist.shuffle",
  "params": {},
  "correlation_id": "uuid",
  "source": "shell"
}
```

### Inbound Event Data (New Handlers)

#### delete event
```json
{
  "event_type": "delete",
  "data": {
    "uid": "abc123"            // UID of deleted item
  },
  "metadata": {
    "cytube_event": "delete",
    "timestamp": 1234567890.123
  }
}
```

#### moveVideo event
```json
{
  "event_type": "moveVideo",
  "data": {
    "from": 3,                 // Original position
    "to": 1,                   // New position
    "uid": "abc123"            // Item UID (if available)
  },
  "metadata": {
    "cytube_event": "moveVideo",
    "timestamp": 1234567890.123
  }
}
```

### Error Response
```json
{
  "event_type": "error",
  "subject": "rosey.platform.cytube.error",
  "data": {
    "command": "playlist.add",
    "error": "Invalid video ID",
    "original_subject": "rosey.platform.cytube.send.playlist.add",
    "correlation_id": "original-uuid"
  },
  "source": "cytube-connector"
}
```

### CyTube Channel API Mapping

| NATS Command | CyTube API Method | Parameters |
|--------------|-------------------|------------|
| playlist.add | `channel.queue(type, id)` | type, id |
| playlist.remove | `channel.delete(uid)` | uid |
| playlist.move | `channel.moveMedia(from, after)` | uid, after |
| playlist.jump | `channel.jumpTo(uid)` | uid |
| playlist.clear | `channel.clearPlaylist()` | (none) |
| playlist.shuffle | `channel.shufflePlaylist()` | (none) |

## 5. Acceptance Criteria

### Inbound Events

- **AC-001**: Given CyTube sends "delete" event, When connector receives it, Then event published to `rosey.platform.cytube.delete`
- **AC-002**: Given CyTube sends "moveVideo" event, When connector receives it, Then event published to `rosey.platform.cytube.moveVideo`
- **AC-003**: Given delete event contains uid, When published, Then uid is in event.data
- **AC-004**: Given moveVideo event contains positions, When published, Then from/to/uid in event.data

### Outbound Commands

- **AC-005**: Given valid playlist.add command, When published to send.playlist.add, Then channel.queue() is called with correct parameters
- **AC-006**: Given valid playlist.remove command, When published to send.playlist.remove, Then channel.delete() is called
- **AC-007**: Given valid playlist.move command, When published to send.playlist.move, Then channel.moveMedia() is called
- **AC-008**: Given valid playlist.jump command, When published to send.playlist.jump, Then channel.jumpTo() is called
- **AC-009**: Given invalid command (missing params), When received, Then error event published with details
- **AC-010**: Given connector not connected, When command received, Then error event published

### Integration

- **AC-011**: Given existing shell commands (add, remove, move, jump), When migrated to use NATS, Then all direct channel API calls removed from shell.py
- **AC-012**: Given plugin publishes playlist.add command, When connector executes it, Then video appears in CyTube playlist
- **AC-013**: Given multiple concurrent commands, When processed, Then all execute in order without blocking

### Error Handling

- **AC-014**: Given CyTube API call fails, When error occurs, Then error event published with stack trace
- **AC-015**: Given malformed command JSON, When received, Then error logged and ignored (no crash)
- **AC-016**: Given command with unknown action, When received, Then error event published

## 6. Test Automation Strategy

### Test Levels

- **Unit Tests**: Test individual command handlers in isolation
- **Integration Tests**: Test full command flow (NATS → Connector → Mock Channel)
- **End-to-End Tests**: Test with real NATS server (not real CyTube)

### Frameworks

- **pytest** with pytest-asyncio for async test support
- **unittest.mock** for mocking CyTube channel API
- **AsyncMock** for async method mocking

### Test Data Management

- Use fixtures for common test data (valid/invalid commands, event payloads)
- Create `MockChannel` helper with all playlist methods
- Create command builder helpers for test readability

### CI/CD Integration

- All tests must pass before merge
- Unit tests run on every commit
- Integration tests run on PR
- Coverage threshold: 85% for new code

### Performance Testing

- Measure command processing latency (target: <5ms per command)
- Test with 100 concurrent commands (ensure no blocking)
- Verify memory usage remains constant under load

## 7. Rationale & Context

### Why NATS Command Pattern?

Currently, playlist manipulation bypasses the event bus architecture:
```python
# Current anti-pattern (direct API calls in shell/plugins)
await bot.channel.queue('yt', 'video_id')
await bot.channel.delete('uid')
```

This creates tight coupling between components and the CyTube channel object, which is an anti-pattern outside the connector core. The NATS pattern provides:

1. **Decoupling**: Shell/plugins communicate via event bus, not direct channel access
2. **Testability**: Commands can be tested without CyTube connection
3. **Observability**: All commands flow through event bus (logging, metrics, tracing)
4. **Consistency**: Matches PM and chat message patterns (already using NATS)
5. **Future-proofing**: Easy to add command queuing, rate limiting, auditing, multi-platform support

### Why Fire-and-Forget vs Request/Reply?

Fire-and-forget (publish only) is preferred for:
- User-triggered commands (fast UI response)
- Commands where confirmation isn't critical
- High-frequency operations

Request/reply is used for:
- Plugin automation requiring confirmation
- Commands that affect other state
- Operations where failure must be handled

Both patterns are supported; caller chooses based on use case.

### Why Separate send.playlist.* Subjects?

Using granular subjects enables:
- Selective subscription (only listen to add events)
- Access control (future: restrict who can clear playlist)
- Metrics per command type
- Easier debugging (filter by command)

Alternative considered: Single `send.command` subject with command in payload. Rejected because:
- Less discoverable
- Can't use NATS wildcards for filtering
- Harder to apply access control

### Why Missing delete/moveVideo Handlers?

Historical oversight. The connector was initially focused on read-only events (chat, media changes). Playlist modification events were not prioritized. Adding them now completes the bidirectional playlist architecture.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: CyTube WebSocket server - Source of inbound events, destination for commands
  - Availability: Required for all playlist operations
  - Failure mode: Commands rejected with "not connected" error
  - Version: Compatible with CyTube 3.x API

### Third-Party Services

- **SVC-001**: NATS server (nats-server) - Message broker
  - Version: 2.9+ required for JetStream support (optional)
  - Port: 4222 (default) or configured port
  - Failure mode: Connector cannot publish/subscribe; direct channel API remains functional

### Infrastructure Dependencies

- **INF-001**: Network connectivity between bot and NATS server
  - Latency requirement: <10ms typical
  - Bandwidth: Minimal (<1KB per command)

- **INF-002**: Async event loop (asyncio)
  - Python 3.11+ required
  - Event loop must not be blocked by command handlers

### Data Dependencies

- **DAT-001**: CyTube channel object with playlist methods
  - Methods required: queue(), delete(), moveMedia(), jumpTo(), clearPlaylist(), shufflePlaylist()
  - Authentication: Handled by existing channel connection

### Technology Platform Dependencies

- **PLT-001**: Python asyncio ecosystem
  - nats-py 2.x for NATS client
  - No synchronous/blocking calls in command handlers

### Compliance Dependencies

- **COM-001**: CyTube terms of service
  - Must not violate rate limits (handled by CyTube server)
  - Must not automate playlist manipulation against server rules

## 9. Examples & Edge Cases

### Example 1: Add Video from Shell Command

```python
# User types: /add https://youtube.com/watch?v=dQw4w9WgXcQ

# Shell parses URL and publishes command
event = Event(
    subject="rosey.platform.cytube.send.playlist.add",
    event_type="command",
    source="shell",
    data={
        "command": "playlist.add",
        "params": {
            "type": "yt",
            "id": "dQw4w9WgXcQ",
            "position": "end",
            "temporary": False
        }
    }
)
await event_bus.publish(event)

# Connector receives, validates, executes
await channel.queue('yt', 'dQw4w9WgXcQ')

# CyTube broadcasts "queue" event to all clients
# Connector publishes to rosey.platform.cytube.queue
# UI updates showing new video
```

### Example 2: Remove Video (Request/Reply)

```python
# Plugin wants to remove video and confirm it worked
response = await event_bus.request(
    subject="rosey.platform.cytube.send.playlist.remove",
    data={
        "command": "playlist.remove",
        "params": {"uid": "abc123"}
    },
    timeout=5.0
)

if response.get("success"):
    logger.info("Video removed successfully")
else:
    logger.error(f"Failed to remove: {response.get('error')}")
```

### Example 3: Error Handling (Invalid Command)

```python
# Missing required parameter
event = Event(
    subject="rosey.platform.cytube.send.playlist.add",
    event_type="command",
    source="buggy_plugin",
    data={
        "command": "playlist.add",
        "params": {
            "type": "yt"
            # Missing "id" parameter
        }
    }
)

# Connector validates and publishes error
error_event = Event(
    subject="rosey.platform.cytube.error",
    event_type="error",
    source="cytube-connector",
    data={
        "command": "playlist.add",
        "error": "Missing required parameter: id",
        "original_subject": "rosey.platform.cytube.send.playlist.add",
        "correlation_id": event.correlation_id
    }
)
```

### Edge Case 1: Disconnect During Command

```python
# Command received while disconnected from CyTube
# Connector must not crash or hang

async def _handle_playlist_command(self, event: Event):
    if not self.channel or not self.channel.is_connected:
        await self._publish_error(
            event,
            "Not connected to CyTube server"
        )
        return
    
    # Process command...
```

### Edge Case 2: Rapid Concurrent Commands

```python
# 100 remove commands published simultaneously
# Must process all without blocking event loop

# Solution: Each command handler is async and doesn't await others
for i in range(100):
    await event_bus.publish(remove_command)

# All commands queue up in NATS
# Connector processes each asynchronously
# CyTube server enforces rate limits naturally
```

### Edge Case 3: Invalid Video ID

```python
# User tries to add video that doesn't exist
# CyTube API will accept command but video won't load

# Command succeeds (CyTube accepts it)
await channel.queue('yt', 'invalid_id_12345')

# CyTube later broadcasts error event
# Connector should not validate video IDs
# (CyTube server is source of truth)
```

### Edge Case 4: Move After Non-Existent Item

```python
# Try to move video after item that was just deleted
{
  "command": "playlist.move",
  "params": {
    "uid": "video1",
    "after": "deleted_video"  # Doesn't exist
  }
}

# CyTube API will reject this
# Connector should catch exception and publish error
try:
    await channel.moveMedia('video1', 'deleted_video')
except Exception as e:
    await self._publish_error(event, str(e))
```

## 10. Validation Criteria

### Code Quality

- **VAL-001**: All async functions use proper async/await syntax
- **VAL-002**: No blocking I/O operations in command handlers
- **VAL-003**: All exceptions are caught and logged
- **VAL-004**: Type hints on all public methods
- **VAL-005**: Docstrings follow Google style guide

### Functional Validation

- **VAL-006**: Unit tests cover all command types (add, remove, move, jump, clear, shuffle)
- **VAL-007**: Integration tests verify NATS → Connector → Channel flow
- **VAL-008**: Error cases have explicit tests (invalid params, disconnected, etc.)
- **VAL-009**: Inbound event handlers (delete, moveVideo) have tests
- **VAL-010**: Manual testing with real CyTube server confirms commands work

### Performance Validation

- **VAL-011**: Command processing latency < 5ms (measured via logging)
- **VAL-012**: 100 concurrent commands complete without errors
- **VAL-013**: Memory usage stable under continuous load (1 hour test)

### Security Validation

- **VAL-014**: Commands cannot bypass CyTube permissions
- **VAL-015**: No credentials or tokens logged in error messages
- **VAL-016**: Malformed commands cannot crash connector

## 11. Related Specifications / Further Reading

### Related Specifications

- [SPEC-Sortie-1-NATS-Event-Bus.md](../completed/6a-quicksilver/SPEC-Sortie-1-NATS-Event-Bus.md) - Original NATS event bus architecture
- [SPEC-PM-NATS-Integration.md](./SPEC-PM-NATS-Integration.md) - PM command integration (similar pattern)
- [docs/ARCHITECTURE.md](../../ARCHITECTURE.md) - Overall bot architecture

### External Documentation

- [NATS Documentation](https://docs.nats.io/) - NATS messaging system
- [nats-py GitHub](https://github.com/nats-io/nats.py) - Python NATS client
- [CyTube API](https://github.com/calzoneman/sync/blob/3.0/docs/socketconfig.md) - CyTube WebSocket protocol

### Code References

- `bot/rosey/core/event_bus.py` - EventBus implementation
- `bot/rosey/core/cytube_connector.py` - CytubeConnector class
- `bot/rosey/core/subjects.py` - NATS subject hierarchy
- `common/shell.py` - Shell command handlers (will be refactored)

### Testing Resources

- `tests/unit/test_cytube_connector.py` - Existing connector tests
- `tests/integration/test_pm_commands.py` - PM integration tests (reference)

---

## Implementation Notes

### Phase 1: Inbound Events (1-2 hours)
1. Add `_on_delete()` handler
2. Add `_on_move_video()` handler
3. Register handlers
4. Write unit tests
5. Verify events publish correctly

### Phase 2: Outbound Commands (3-4 hours)
1. Add command subscription in connector
2. Implement `_handle_playlist_command()` dispatcher
3. Implement individual command handlers (add, remove, move, jump, clear, shuffle)
4. Add error publishing helper
5. Write unit tests for each command

### Phase 3: Migrate Shell Commands (2-3 hours)
1. Remove all direct channel API calls from shell.py playlist commands
2. Replace with NATS event publishing to send.playlist.* subjects
3. Update integration tests to verify NATS flow
4. Remove any remaining channel.queue/delete/moveMedia/jumpTo calls outside connector
5. Manual testing with real CyTube server

### Phase 4: Documentation (1 hour)
1. Update ARCHITECTURE.md
2. Add docstrings
3. Update NATS subject reference docs

**Total Estimated Effort:** 7-10 hours

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CyTube API changes | Low | High | Use existing channel wrapper, add version checks |
| NATS connection failures | Medium | Medium | Clear error events, fail fast with helpful messages |
| Migration introduces bugs | Medium | High | Comprehensive tests, verify all shell commands migrated |
| Performance impact | Low | Low | Async handlers, measure latency |

### Success Metrics

- ✅ All tests pass (100% of new code covered)
- ✅ Command latency < 5ms
- ✅ Zero production errors in first week
- ✅ No direct channel API calls remain in shell.py for playlist operations
- ✅ All playlist functionality works via NATS command pattern
- ✅ grep search confirms no `bot.channel.queue|delete|moveMedia|jumpTo` outside connector
