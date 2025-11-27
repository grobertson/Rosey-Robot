---
goal: Migrate shell playlist commands from direct channel API calls to NATS event publishing
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Completed'
tags: [refactor, event-bus, shell, playlist, migration]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This sortie migrates all shell playlist commands (`add`, `remove`, `move`, `jump`) from direct channel API calls to NATS event publishing. This completes the architectural migration where shell commands communicate with CytubeConnector via the event bus rather than directly accessing the channel object, eliminating the anti-pattern of direct API calls outside the connector core.

## 1. Requirements & Constraints

### Requirements

- **REQ-001**: Replace `bot.add_media()` in `cmd_add()` with NATS publish to `send.playlist.add`
- **REQ-002**: Replace `bot.remove_media()` in `cmd_remove()` with NATS publish to `send.playlist.remove`
- **REQ-003**: Replace `bot.move_media()` in `cmd_move()` with NATS publish to `send.playlist.move`
- **REQ-004**: Replace `bot.set_current_media()` in `cmd_jump()` with NATS publish to `send.playlist.jump`
- **REQ-005**: All commands must publish Events with proper correlation_id for tracing
- **REQ-006**: Commands must include source="shell" in event metadata
- **REQ-007**: Remove any remaining direct channel API calls for playlist operations from shell.py
- **REQ-008**: Maintain existing command functionality and user-facing behavior
- **REQ-009**: Update command return messages to reflect async nature (optional)
- **REQ-010**: All NATS publishes must be fire-and-forget (no blocking on reply)

### Security Requirements

- **SEC-001**: Command data must not include sensitive information
- **SEC-002**: User-provided URLs must not be modified before publishing (pass-through)

### Constraints

- **CON-001**: Cannot change shell command syntax or user interface
- **CON-002**: Commands must remain fast and responsive (fire-and-forget pattern)
- **CON-003**: Must handle EventBus unavailable gracefully (fall back to error message)
- **CON-004**: Cannot break non-playlist commands during refactor

### Guidelines

- **GUD-001**: Follow NATS event structure from spec (command, params, correlation_id, source)
- **GUD-002**: Generate unique correlation_id per command for tracing
- **GUD-003**: Log command publications at debug level
- **GUD-004**: Keep error messages user-friendly

### Patterns

- **PAT-001**: Create Event with subject `rosey.platform.cytube.send.playlist.<action>`
- **PAT-002**: Event data structure: `{"command": "playlist.action", "params": {...}, "source": "shell"}`
- **PAT-003**: Use `await bot.event_bus.publish(event)` for fire-and-forget
- **PAT-004**: Handle EventBus publish errors gracefully

## 2. Implementation Steps

### Implementation Phase 1: Refactor cmd_add

- GOAL-001: Migrate add command from direct API to NATS

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Locate `cmd_add()` method in shell.py (line ~624) | |  |
| TASK-002 | Remove `await bot.add_media(link, append=True, temp=temp)` call | |  |
| TASK-003 | Parse MediaLink to extract type and id | |  |
| TASK-004 | Create Event with subject `rosey.platform.cytube.send.playlist.add` | |  |
| TASK-005 | Event data: `{"command": "playlist.add", "params": {"type": type, "id": id, "position": "end", "temporary": temp}}` | |  |
| TASK-006 | Generate correlation_id using uuid4 | |  |
| TASK-007 | Set event source to "shell" | |  |
| TASK-008 | Publish event: `await bot.event_bus.publish(event)` | |  |
| TASK-009 | Update return message if needed (optional) | |  |
| TASK-010 | Wrap in try/except to handle publish errors | |  |

### Implementation Phase 2: Refactor cmd_remove

- GOAL-002: Migrate remove command from direct API to NATS

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Locate `cmd_remove()` method in shell.py (line ~646) | |  |
| TASK-012 | Get playlist item and extract uid | |  |
| TASK-013 | Remove `await bot.remove_media(item)` call | |  |
| TASK-014 | Create Event with subject `rosey.platform.cytube.send.playlist.remove` | |  |
| TASK-015 | Event data: `{"command": "playlist.remove", "params": {"uid": item.uid}}` | |  |
| TASK-016 | Generate correlation_id and set source to "shell" | |  |
| TASK-017 | Publish event to EventBus | |  |
| TASK-018 | Update return message if needed | |  |
| TASK-019 | Handle publish errors gracefully | |  |

### Implementation Phase 3: Refactor cmd_move

- GOAL-003: Migrate move command from direct API to NATS

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-020 | Locate `cmd_move()` method in shell.py (line ~672) | |  |
| TASK-021 | Extract from_item uid and after_item uid (if exists) | |  |
| TASK-022 | Remove `await bot.move_media(from_item, after_item)` call | |  |
| TASK-023 | Create Event with subject `rosey.platform.cytube.send.playlist.move` | |  |
| TASK-024 | Event data: `{"command": "playlist.move", "params": {"uid": from_uid, "after": after_uid}}` | |  |
| TASK-025 | Handle "move to beginning" case (after_uid = "prepend" or None) | |  |
| TASK-026 | Generate correlation_id and set source to "shell" | |  |
| TASK-027 | Publish event to EventBus | |  |
| TASK-028 | Update return message (remove "not yet supported" for beginning) | |  |
| TASK-029 | Handle publish errors gracefully | |  |

### Implementation Phase 4: Refactor cmd_jump

- GOAL-004: Migrate jump command from direct API to NATS

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-030 | Locate `cmd_jump()` method in shell.py (line ~700) | |  |
| TASK-031 | Get playlist item and extract uid | |  |
| TASK-032 | Remove `await bot.set_current_media(item)` call | |  |
| TASK-033 | Create Event with subject `rosey.platform.cytube.send.playlist.jump` | |  |
| TASK-034 | Event data: `{"command": "playlist.jump", "params": {"uid": item.uid}}` | |  |
| TASK-035 | Generate correlation_id and set source to "shell" | |  |
| TASK-036 | Publish event to EventBus | |  |
| TASK-037 | Update return message if needed | |  |
| TASK-038 | Handle publish errors gracefully | |  |

### Implementation Phase 5: Verification and Testing

- GOAL-005: Verify migration complete and all tests pass

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | Search shell.py for any remaining `bot.add_media|remove_media|move_media|set_current_media` calls | |  |
| TASK-040 | Search shell.py for any remaining `bot.channel.queue|delete|moveMedia|jumpTo` calls | |  |
| TASK-041 | Verify EventBus is available in bot instance | |  |
| TASK-042 | Update or add integration tests for shell commands | |  |
| TASK-043 | Test add command with real NATS → verify video added | |  |
| TASK-044 | Test remove command → verify video removed | |  |
| TASK-045 | Test move command → verify video moved | |  |
| TASK-046 | Test jump command → verify playback jumps | |  |
| TASK-047 | Test error handling when EventBus unavailable | |  |
| TASK-048 | Run full test suite to ensure no regressions | |  |

## 3. Alternatives

- **ALT-001**: Could use request/reply pattern to wait for confirmation
  - Rejected: Adds latency, users expect instant feedback; fire-and-forget matches UI expectations
- **ALT-002**: Could create shell-specific event subjects
  - Rejected: Shell should use same subjects as plugins for consistency
- **ALT-003**: Could keep direct API as fallback when EventBus unavailable
  - Rejected: Would maintain anti-pattern; better to fail fast and report error

## 4. Dependencies

- **DEP-001**: EventBus must be initialized and available in bot instance
- **DEP-002**: CytubeConnector must be subscribed to playlist command subjects (Sortie 2)
- **DEP-003**: Playlist item objects must have `uid` attribute
- **DEP-004**: MediaLink parsing must extract type and id correctly

## 5. Files

- **FILE-001**: `common/shell.py` - Refactor cmd_add, cmd_remove, cmd_move, cmd_jump methods
- **FILE-002**: `tests/integration/test_shell_playlist.py` - Add/update integration tests (may need to create)
- **FILE-003**: `tests/unit/test_shell.py` - Update unit tests if they exist

## 6. Testing

### Unit Tests

- **TEST-001**: cmd_add with valid URL → publishes Event with correct subject and data
- **TEST-002**: cmd_add extracts type/id from MediaLink correctly
- **TEST-003**: cmd_remove with valid position → publishes Event with correct uid
- **TEST-004**: cmd_move with valid positions → publishes Event with from/after uids
- **TEST-005**: cmd_jump with valid position → publishes Event with correct uid
- **TEST-006**: All commands generate unique correlation_id
- **TEST-007**: All commands set source="shell" in event

### Integration Tests

- **TEST-008**: Shell add command → CytubeConnector receives event → video added to CyTube
- **TEST-009**: Shell remove command → video removed from CyTube
- **TEST-010**: Shell move command → video position changes in CyTube
- **TEST-011**: Shell jump command → playback jumps in CyTube
- **TEST-012**: EventBus unavailable → commands return error message without crashing

### Regression Tests

- **TEST-013**: Non-playlist commands still work (say, pm, clear, status, etc.)
- **TEST-014**: All existing shell tests pass
- **TEST-015**: Full bot integration test passes

## 7. Risks & Assumptions

### Risks

- **RISK-001**: MediaLink parsing might fail for some URL formats
  - Mitigation: Keep existing try/except error handling
- **RISK-002**: Missing uid attribute on playlist items
  - Mitigation: Verify playlist item structure before refactor
- **RISK-003**: EventBus not initialized at shell command time
  - Mitigation: Check bot.event_bus existence, return clear error
- **RISK-004**: Fire-and-forget means no confirmation to user
  - Mitigation: Return success message immediately; user sees result in UI

### Assumptions

- **ASSUMPTION-001**: bot.event_bus is initialized before shell commands execute
- **ASSUMPTION-002**: Playlist items have uid attribute (UID from CyTube)
- **ASSUMPTION-003**: MediaLink.from_url() extracts type and id correctly
- **ASSUMPTION-004**: CytubeConnector is running and subscribed to command subjects
- **ASSUMPTION-005**: Fire-and-forget is acceptable (no wait for command completion)

## 8. Related Specifications / Further Reading

- [SPEC-Playlist-NATS-Commands.md](../docs/sprints/active/SPEC-Playlist-NATS-Commands.md) - Parent specification
- [shell.py](../common/shell.py) - Implementation file
- [EventBus API](../bot/rosey/core/event_bus.py) - Event publishing interface
- [NATS Subjects](../bot/rosey/core/subjects.py) - Subject hierarchy
