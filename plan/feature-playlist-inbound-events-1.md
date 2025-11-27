---
goal: Implement missing inbound DELETE and MOVE_VIDEO event handlers in CytubeConnector
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Completed'
tags: [feature, event-bus, cytube, playlist, inbound]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This sortie implements the missing inbound event handlers for CyTube playlist deletion (`delete`) and video movement (`moveVideo`) events. Currently, these event types are defined in the `CytubeEventType` enum but have no registered handlers, preventing the event bus from propagating these playlist changes to subscribers.

## 1. Requirements & Constraints

### Requirements

- **REQ-001**: Implement `_on_delete()` handler method in CytubeConnector class
- **REQ-002**: Implement `_on_move_video()` handler method in CytubeConnector class
- **REQ-003**: Register both handlers in `_register_cytube_handlers()` method
- **REQ-004**: Add both handlers to `_event_handlers` dict for proper cleanup
- **REQ-005**: DELETE events must publish to `rosey.platform.cytube.delete` NATS subject
- **REQ-006**: MOVE_VIDEO events must publish to `rosey.platform.cytube.moveVideo` NATS subject
- **REQ-007**: Both handlers must follow existing pattern (try/except, increment counters, error logging)
- **REQ-008**: DELETE event data must include `uid` field from CyTube payload
- **REQ-009**: MOVE_VIDEO event data must include `from`, `to`, and `uid` fields from CyTube payload
- **REQ-010**: Both handlers must call `_publish_to_eventbus()` with CytubeEvent wrapper

### Security Requirements

- **SEC-001**: Event data must not be mutated or enhanced (pass-through from CyTube)
- **SEC-002**: No sensitive information should be logged in error messages

### Constraints

- **CON-001**: Must not break existing playlist event handlers (playlist, queue)
- **CON-002**: Must follow async/await patterns consistently
- **CON-003**: Event handlers must not block the event loop
- **CON-004**: Must maintain consistency with existing handler patterns in the codebase

### Guidelines

- **GUD-001**: Follow existing code style in `cytube_connector.py`
- **GUD-002**: Use descriptive error messages that aid debugging
- **GUD-003**: Increment `_events_received` counter on success, `_errors` counter on failure
- **GUD-004**: Log errors with context (event type, error message)

### Patterns

- **PAT-001**: Handler method signature: `async def _on_<event>(self, data: Dict[str, Any]) -> None:`
- **PAT-002**: Create CytubeEvent with appropriate event_type from enum
- **PAT-003**: Wrap handler body in try/except with error logging and counter increment
- **PAT-004**: Call `await self._publish_to_eventbus(event)` to propagate to NATS

## 2. Implementation Steps

### Implementation Phase 1: Add DELETE Handler

- GOAL-001: Implement DELETE event handler following existing patterns

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add `_on_delete()` method after `_on_queue()` (line ~401) in cytube_connector.py | |  |
| TASK-002 | Method accepts `data: Dict[str, Any]` parameter with `uid` field | |  |
| TASK-003 | Create CytubeEvent with DELETE event type and uid in data dict | |  |
| TASK-004 | Call `_publish_to_eventbus()` to publish to NATS | |  |
| TASK-005 | Increment `_events_received` counter on success | |  |
| TASK-006 | Wrap in try/except, log errors, increment `_errors` on failure | |  |

### Implementation Phase 2: Add MOVE_VIDEO Handler

- GOAL-002: Implement MOVE_VIDEO event handler following existing patterns

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add `_on_move_video()` method after `_on_delete()` in cytube_connector.py | |  |
| TASK-008 | Method accepts `data: Dict[str, Any]` with `from`, `to`, optionally `uid` fields | |  |
| TASK-009 | Create CytubeEvent with MOVE_VIDEO type and from/to/uid in data dict | |  |
| TASK-010 | Call `_publish_to_eventbus()` to publish to NATS | |  |
| TASK-011 | Increment `_events_received` counter on success | |  |
| TASK-012 | Wrap in try/except, log errors, increment `_errors` on failure | |  |

### Implementation Phase 3: Register Handlers

- GOAL-003: Register new handlers in connector initialization

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Add `self.channel.on("delete", self._on_delete)` to `_register_cytube_handlers()` (line ~229) | |  |
| TASK-014 | Add `self.channel.on("moveVideo", self._on_move_video)` to `_register_cytube_handlers()` | |  |
| TASK-015 | Add `"delete": self._on_delete` entry to `_event_handlers` dict (line ~243) | |  |
| TASK-016 | Add `"moveVideo": self._on_move_video` entry to `_event_handlers` dict | |  |

### Implementation Phase 4: Unit Tests

- GOAL-004: Add comprehensive unit tests for new handlers

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Add `test_on_delete()` test in test_cytube_connector.py | |  |
| TASK-018 | Test verifies DELETE event published with correct subject and uid | |  |
| TASK-019 | Add `test_on_move_video()` test in test_cytube_connector.py | |  |
| TASK-020 | Test verifies MOVE_VIDEO event published with from/to/uid data | |  |
| TASK-021 | Add error handling tests for both handlers (malformed data) | |  |
| TASK-022 | Verify `_events_received` and `_errors` counters updated correctly | |  |

## 3. Alternatives

- **ALT-001**: Could combine delete and move handlers into single generic playlist change handler
  - Rejected: Individual handlers are more explicit and match existing pattern (playlist, queue are separate)
- **ALT-002**: Could validate uid format before publishing
  - Rejected: CyTube server is source of truth; connector should pass-through data unchanged

## 4. Dependencies

- **DEP-001**: CytubeConnector class in `bot/rosey/core/cytube_connector.py`
- **DEP-002**: CytubeEventType enum must have DELETE and MOVE_VIDEO entries (already exists)
- **DEP-003**: EventBus publish functionality (already exists)
- **DEP-004**: Test fixtures in `tests/unit/test_cytube_connector.py` (mock_event_bus, mock_channel)

## 5. Files

- **FILE-001**: `bot/rosey/core/cytube_connector.py` - Add handler methods and registration
- **FILE-002**: `tests/unit/test_cytube_connector.py` - Add unit tests for new handlers

## 6. Testing

- **TEST-001**: Unit test: DELETE event with valid uid → event published to correct subject
- **TEST-002**: Unit test: DELETE event with missing uid → event published with empty uid
- **TEST-003**: Unit test: MOVE_VIDEO event with from/to/uid → event published with all fields
- **TEST-004**: Unit test: MOVE_VIDEO event with only from/to → event published without uid field
- **TEST-005**: Unit test: Exception during delete handling → error logged, _errors incremented
- **TEST-006**: Unit test: Exception during moveVideo handling → error logged, _errors incremented
- **TEST-007**: Integration test: Handlers registered properly in _event_handlers dict
- **TEST-008**: Integration test: Handlers can be unregistered without error

## 7. Risks & Assumptions

### Risks

- **RISK-001**: CyTube might send delete/moveVideo events with unexpected data structure
  - Mitigation: Use `.get()` with defaults, wrap in try/except, log errors
- **RISK-002**: High-frequency delete/move events could impact performance
  - Mitigation: Handlers are async and non-blocking; NATS handles queueing

### Assumptions

- **ASSUMPTION-001**: CyTube delete event includes `uid` field identifying removed item
- **ASSUMPTION-002**: CyTube moveVideo event includes `from` (old position) and `to` (new position)
- **ASSUMPTION-003**: EventBus publish is async and non-blocking
- **ASSUMPTION-004**: Existing test fixtures (mock_event_bus, mock_channel) support new handlers

## 8. Related Specifications / Further Reading

- [SPEC-Playlist-NATS-Commands.md](../docs/sprints/active/SPEC-Playlist-NATS-Commands.md) - Parent specification
- [cytube_connector.py](../bot/rosey/core/cytube_connector.py) - Implementation file
- [CyTube WebSocket Protocol](https://github.com/calzoneman/sync/blob/3.0/docs/socketconfig.md) - delete/moveVideo event format
