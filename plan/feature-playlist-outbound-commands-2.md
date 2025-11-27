---
goal: Implement outbound playlist command handlers in CytubeConnector with NATS subscription
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Completed'
tags: [feature, event-bus, cytube, playlist, outbound, commands]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This sortie implements the complete outbound playlist command infrastructure in CytubeConnector. This includes subscribing to NATS command subjects (`rosey.platform.cytube.send.playlist.*`), implementing a command dispatcher, creating 6 individual command handlers (add, remove, move, jump, clear, shuffle), and adding error event publishing for failed commands.

## 1. Requirements & Constraints

### Requirements

- **REQ-001**: Subscribe to `rosey.platform.cytube.send.playlist.*` wildcard subject in connector `start()` method
- **REQ-002**: Implement `_handle_playlist_command()` dispatcher method to route commands
- **REQ-003**: Implement `_playlist_add()` handler - calls `channel.queue(type, id)`
- **REQ-004**: Implement `_playlist_remove()` handler - calls `channel.delete(uid)`
- **REQ-005**: Implement `_playlist_move()` handler - calls `channel.moveMedia(uid, after)`
- **REQ-006**: Implement `_playlist_jump()` handler - calls `channel.jumpTo(uid)`
- **REQ-007**: Implement `_playlist_clear()` handler - calls `channel.clearPlaylist()`
- **REQ-008**: Implement `_playlist_shuffle()` handler - calls `channel.shufflePlaylist()`
- **REQ-009**: All handlers must validate required parameters before execution
- **REQ-010**: Implement `_publish_playlist_error()` helper for error event publishing
- **REQ-011**: Failed commands must publish error events to `rosey.platform.cytube.error` subject
- **REQ-012**: Error events must include original correlation_id, command name, and error message
- **REQ-013**: Commands received when not connected must reject with "Not connected" error
- **REQ-014**: All command handlers must be async and non-blocking
- **REQ-015**: Command validation must check for required fields (type/id for add, uid for remove/move/jump)

### Security Requirements

- **SEC-001**: Command handlers must not bypass CyTube permission system (rely on server enforcement)
- **SEC-002**: Error messages must not expose internal implementation details or credentials
- **SEC-003**: Command data must be validated but not sanitized (CyTube server validates)

### Constraints

- **CON-001**: Commands execute through existing channel API methods only (no direct protocol access)
- **CON-002**: Must handle disconnection gracefully without crashing
- **CON-003**: Dispatcher must not block on individual command execution
- **CON-004**: Cannot break existing `_handle_eventbus_command()` for chat/skip commands

### Guidelines

- **GUD-001**: Follow existing command handler pattern from PM implementation
- **GUD-002**: Use descriptive error messages that help users debug issues
- **GUD-003**: Log all command executions at debug level for troubleshooting
- **GUD-004**: Use correlation_id from incoming event for tracing

### Patterns

- **PAT-001**: Command handler signature: `async def _playlist_<action>(self, event: Event) -> None:`
- **PAT-002**: Extract params from `event.data["params"]` dict
- **PAT-003**: Validate required params, call `_publish_playlist_error()` if missing
- **PAT-004**: Call corresponding channel API method
- **PAT-005**: Catch exceptions and publish error events with full context

## 2. Implementation Steps

### Implementation Phase 1: Subscription and Dispatcher

- GOAL-001: Set up NATS subscription and command routing infrastructure

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add playlist command subscription in `start()` method after PM subscription | |  |
| TASK-002 | Subscribe to `rosey.platform.cytube.send.playlist.*` with callback `_handle_playlist_command` | |  |
| TASK-003 | Store subscription ID for cleanup in `stop()` method | |  |
| TASK-004 | Implement `_handle_playlist_command()` dispatcher method | |  |
| TASK-005 | Extract command action from `event.data["command"]` (e.g., "playlist.add") | |  |
| TASK-006 | Route to appropriate handler based on action: add/remove/move/jump/clear/shuffle | |  |
| TASK-007 | Log unknown commands and publish error event | |  |
| TASK-008 | Wrap dispatcher in try/except to catch routing errors | |  |

### Implementation Phase 2: Connection Check and Error Helper

- GOAL-002: Implement connection validation and error publishing infrastructure

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Implement `_publish_playlist_error()` helper method | |  |
| TASK-010 | Method accepts event, error message, and optional exception | |  |
| TASK-011 | Create error Event with subject `rosey.platform.cytube.error` | |  |
| TASK-012 | Include original command, correlation_id, error message in data | |  |
| TASK-013 | Publish error event to EventBus | |  |
| TASK-014 | Log error at ERROR level with full context | |  |
| TASK-015 | Add connection check at start of `_handle_playlist_command()` | |  |
| TASK-016 | Reject command with "Not connected to CyTube server" if channel is None | |  |

### Implementation Phase 3: Add/Remove/Jump Handlers

- GOAL-003: Implement core playlist manipulation handlers

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Implement `_playlist_add()` method | |  |
| TASK-018 | Extract and validate `type`, `id` from event.data["params"] | |  |
| TASK-019 | Call `await self.channel.queue(type, id)` | |  |
| TASK-020 | Catch exceptions and call `_publish_playlist_error()` | |  |
| TASK-021 | Log successful add at debug level | |  |
| TASK-022 | Implement `_playlist_remove()` method | |  |
| TASK-023 | Extract and validate `uid` from params | |  |
| TASK-024 | Call `await self.channel.delete(uid)` | |  |
| TASK-025 | Handle errors and log success | |  |
| TASK-026 | Implement `_playlist_jump()` method | |  |
| TASK-027 | Extract and validate `uid` from params | |  |
| TASK-028 | Call `await self.channel.jumpTo(uid)` | |  |
| TASK-029 | Handle errors and log success | |  |

### Implementation Phase 4: Move/Clear/Shuffle Handlers

- GOAL-004: Implement remaining playlist manipulation handlers

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-030 | Implement `_playlist_move()` method | |  |
| TASK-031 | Extract and validate `uid`, `after` from params | |  |
| TASK-032 | Call `await self.channel.moveMedia(uid, after)` | |  |
| TASK-033 | Handle errors and log success | |  |
| TASK-034 | Implement `_playlist_clear()` method | |  |
| TASK-035 | No params required, call `await self.channel.clearPlaylist()` | |  |
| TASK-036 | Handle errors and log success | |  |
| TASK-037 | Implement `_playlist_shuffle()` method | |  |
| TASK-038 | No params required, call `await self.channel.shufflePlaylist()` | |  |
| TASK-039 | Handle errors and log success | |  |

### Implementation Phase 5: Unit Tests

- GOAL-005: Comprehensive unit tests for all command handlers

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-040 | Add test fixtures: mock channel with playlist methods (queue, delete, etc.) | |  |
| TASK-041 | Test `_playlist_add()` with valid params → channel.queue called | |  |
| TASK-042 | Test `_playlist_add()` with missing type → error event published | |  |
| TASK-043 | Test `_playlist_add()` with missing id → error event published | |  |
| TASK-044 | Test `_playlist_remove()` with valid uid → channel.delete called | |  |
| TASK-045 | Test `_playlist_remove()` with missing uid → error event published | |  |
| TASK-046 | Test `_playlist_move()` with valid uid/after → channel.moveMedia called | |  |
| TASK-047 | Test `_playlist_move()` with missing params → error event published | |  |
| TASK-048 | Test `_playlist_jump()` with valid uid → channel.jumpTo called | |  |
| TASK-049 | Test `_playlist_clear()` → channel.clearPlaylist called | |  |
| TASK-050 | Test `_playlist_shuffle()` → channel.shufflePlaylist called | |  |
| TASK-051 | Test command when not connected → "Not connected" error published | |  |
| TASK-052 | Test dispatcher routes commands to correct handlers | |  |
| TASK-053 | Test dispatcher handles unknown command → error published | |  |
| TASK-054 | Test channel API exception → error event published with exception message | |  |

## 3. Alternatives

- **ALT-001**: Could use single handler with switch statement instead of individual methods
  - Rejected: Separate methods are more testable and follow existing patterns
- **ALT-002**: Could implement request/reply pattern for confirmation
  - Deferred: Fire-and-forget simpler for initial implementation; can add reply later
- **ALT-003**: Could validate video IDs before calling CyTube API
  - Rejected: CyTube server is source of truth; connector should not duplicate validation

## 4. Dependencies

- **DEP-001**: EventBus subscription infrastructure (already exists)
- **DEP-002**: CyTube channel object with playlist methods: queue, delete, moveMedia, jumpTo, clearPlaylist, shufflePlaylist
- **DEP-003**: Subjects.py must define or support wildcard subject pattern
- **DEP-004**: Test mock channel must implement all 6 playlist methods

## 5. Files

- **FILE-001**: `bot/rosey/core/cytube_connector.py` - Add command subscription, dispatcher, 6 handlers, error helper
- **FILE-002**: `tests/unit/test_cytube_connector.py` - Add unit tests for all command handlers

## 6. Testing

### Unit Tests

- **TEST-001**: Each command handler called with valid params → correct channel method invoked
- **TEST-002**: Each command handler called with missing params → error event published
- **TEST-003**: Command handler when channel is None → "Not connected" error
- **TEST-004**: Channel method raises exception → error event published with exception message
- **TEST-005**: Dispatcher routes "playlist.add" → _playlist_add called
- **TEST-006**: Dispatcher routes "playlist.remove" → _playlist_remove called
- **TEST-007**: Dispatcher with unknown action → error event published
- **TEST-008**: Error helper publishes to correct subject with correlation_id preserved

### Integration Tests (Manual)

- **TEST-009**: Publish add command → video appears in CyTube playlist
- **TEST-010**: Publish remove command → video removed from CyTube playlist
- **TEST-011**: Publish move command → video position changes in CyTube
- **TEST-012**: Publish jump command → CyTube jumps to specified video
- **TEST-013**: Publish clear command → CyTube playlist empties
- **TEST-014**: Publish shuffle command → CyTube playlist order randomizes

## 7. Risks & Assumptions

### Risks

- **RISK-001**: CyTube API methods might have different signatures than expected
  - Mitigation: Review existing bot.channel implementation before coding
- **RISK-002**: High command volume could overwhelm CyTube server
  - Mitigation: CyTube enforces rate limits; connector passes through errors
- **RISK-003**: Command failures might not provide useful error messages
  - Mitigation: Catch and wrap exceptions with context before publishing

### Assumptions

- **ASSUMPTION-001**: Channel object has async methods: queue, delete, moveMedia, jumpTo, clearPlaylist, shufflePlaylist
- **ASSUMPTION-002**: Channel methods raise exceptions on failure (not silent failures)
- **ASSUMPTION-003**: EventBus.subscribe accepts wildcard subjects with `*`
- **ASSUMPTION-004**: Commands arrive as Event objects with data["command"] and data["params"]

## 8. Related Specifications / Further Reading

- [SPEC-Playlist-NATS-Commands.md](../docs/sprints/active/SPEC-Playlist-NATS-Commands.md) - Parent specification
- [SPEC-PM-NATS-Integration.md](../docs/sprints/active/SPEC-PM-NATS-Integration.md) - Similar command pattern reference
- [cytube_connector.py](../bot/rosey/core/cytube_connector.py) - Implementation file
- [CyTube Channel API](https://github.com/calzoneman/sync) - Channel method documentation
