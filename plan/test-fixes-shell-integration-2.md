---
goal: Update Shell Integration Tests for Event-Driven Architecture
version: 1.0
date_created: 2025-11-27
last_updated: 2025-11-27
owner: Rosey-Robot Team
status: 'Planned'
tags: [testing, shell, integration-tests, event-driven, nats, sortie-2]
---

# Implementation Plan: Shell Integration Test Updates

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

## Introduction

Update 2 shell integration tests to work with the new event-driven architecture introduced in Sprint 19 (Playlist NATS Commands). Tests currently expect direct API calls but should verify NATS event publishing instead.

**Related**: [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md)

## 1. Requirements & Constraints

### Requirements

- **REQ-017**: Shell integration tests MUST assert on NATS event publishing, not direct API calls
- **REQ-018**: Tests MUST verify event subject matches expected pattern
- **REQ-019**: Tests MUST verify event data contains correct parameters
- **REQ-020**: Tests MUST use mock EventBus for verification
- **REQ-021**: `test_shell_add_command_updates_playlist` MUST verify `rosey.platform.cytube.send.playlist.add` event
- **REQ-022**: `test_playlist_manipulation_workflow` MUST verify sequence of playlist events
- **REQ-023**: Tests MUST NOT mock channel API methods (add_media, delete, etc.)
- **REQ-024**: Tests MUST verify correlation IDs are present in events

### Constraints

- **CON-001**: Cannot change shell command behavior (already implemented in Sprint 19)
- **CON-002**: Must maintain test intent (verifying playlist manipulation works)
- **CON-003**: Should follow patterns from existing unit tests in `test_shell.py`

### Guidelines

- **GUD-001**: Use existing mock_bot fixture patterns from unit tests
- **GUD-002**: Keep test names and docstrings unchanged
- **GUD-003**: Add clear assertions with descriptive error messages

## 2. Implementation Steps

### Phase 1: Analyze Current Test Failures

**GOAL-001**: Understand what tests expect vs what actually happens

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Read `tests/integration/test_shell_integration.py::test_shell_add_command_updates_playlist` | | |
| TASK-002 | Read `tests/integration/test_workflows.py::test_playlist_manipulation_workflow` | | |
| TASK-003 | Identify assertions that fail (add_media.assert_called_once) | | |
| TASK-004 | Review successful unit tests in `tests/unit/test_shell.py` for patterns | | |
| TASK-005 | Document fixture changes needed | | |

### Phase 2: Update Integration Bot Fixture

**GOAL-002**: Add mock EventBus to integration_bot fixture

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Locate `integration_bot` fixture (likely in conftest.py or test file) | | |
| TASK-007 | Add `event_bus` attribute as Mock object | | |
| TASK-008 | Configure event_bus.publish as AsyncMock | | |
| TASK-009 | Ensure event_bus is available before shell commands execute | | |
| TASK-010 | Test fixture in isolation | | |

**Code Template**:
```python
@pytest.fixture
async def integration_bot(mock_channel):
    """Create integration test bot with mock EventBus."""
    from unittest.mock import Mock, AsyncMock
    
    bot = Mock()
    bot.channel = mock_channel
    bot.config = {"shell": {"enabled": True, "prefix": "!"}}
    bot.username = "TestBot"
    
    # Add mock EventBus
    bot.event_bus = Mock()
    bot.event_bus.publish = AsyncMock()
    
    # Shell needs bot reference
    shell = Shell(bot)
    bot.shell = shell
    
    yield bot
```

### Phase 3: Update test_shell_add_command_updates_playlist

**GOAL-003**: Fix test to verify NATS event publishing instead of direct API call

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Remove assertion: `integration_bot.add_media.assert_called_once()` | | |
| TASK-012 | Add assertion: `integration_bot.event_bus.publish.assert_called_once()` | | |
| TASK-013 | Verify published event subject is `rosey.platform.cytube.send.playlist.add` | | |
| TASK-014 | Verify event data contains correct video type and id | | |
| TASK-015 | Verify event data contains correlation_id | | |
| TASK-016 | Run test in isolation and verify it passes | | |

**Code Template**:
```python
async def test_shell_add_command_updates_playlist(integration_bot):
    """Test that !add command publishes playlist.add event."""
    # Simulate user command
    await integration_bot.shell.handle_command(
        "!add https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        username="testuser",
        is_moderator=True
    )
    
    # Verify event was published
    integration_bot.event_bus.publish.assert_called_once()
    
    # Get the published event
    call_args = integration_bot.event_bus.publish.call_args
    event = call_args[0][0]  # First positional argument
    
    # Verify event structure
    assert event.subject == "rosey.platform.cytube.send.playlist.add"
    assert event.event_type == "command"
    assert event.data["command"] == "playlist.add"
    assert event.data["params"]["type"] == "yt"
    assert event.data["params"]["id"] == "dQw4w9WgXcQ"
    assert "correlation_id" in event.data
```

### Phase 4: Update test_playlist_manipulation_workflow

**GOAL-004**: Fix workflow test to verify sequence of NATS events

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Remove all direct API assertions (add_media, delete, etc.) | | |
| TASK-018 | Track all event_bus.publish calls | | |
| TASK-019 | Verify sequence of events (add → move → jump → remove) | | |
| TASK-020 | Verify each event has correct subject and data | | |
| TASK-021 | Verify all events have correlation_ids | | |
| TASK-022 | Run test in isolation and verify it passes | | |

**Code Template**:
```python
async def test_playlist_manipulation_workflow(integration_bot):
    """Test complete playlist manipulation workflow via NATS events."""
    # Reset mock to track all calls
    integration_bot.event_bus.publish.reset_mock()
    
    # 1. Add video
    await integration_bot.shell.handle_command(
        "!add https://youtube.com/watch?v=test123",
        username="testuser",
        is_moderator=True
    )
    
    # 2. Move video
    await integration_bot.shell.handle_command(
        "!move 12345 1",
        username="testuser",
        is_moderator=True
    )
    
    # 3. Jump to video
    await integration_bot.shell.handle_command(
        "!jump 12345",
        username="testuser",
        is_moderator=True
    )
    
    # 4. Remove video
    await integration_bot.shell.handle_command(
        "!remove 12345",
        username="testuser",
        is_moderator=True
    )
    
    # Verify all events were published
    assert integration_bot.event_bus.publish.call_count == 4
    
    # Verify event sequence
    calls = integration_bot.event_bus.publish.call_args_list
    
    # Event 1: playlist.add
    event1 = calls[0][0][0]
    assert event1.subject == "rosey.platform.cytube.send.playlist.add"
    assert event1.data["command"] == "playlist.add"
    
    # Event 2: playlist.move
    event2 = calls[1][0][0]
    assert event2.subject == "rosey.platform.cytube.send.playlist.move"
    assert event2.data["command"] == "playlist.move"
    
    # Event 3: playlist.jump
    event3 = calls[2][0][0]
    assert event3.subject == "rosey.platform.cytube.send.playlist.jump"
    assert event3.data["command"] == "playlist.jump"
    
    # Event 4: playlist.remove
    event4 = calls[3][0][0]
    assert event4.subject == "rosey.platform.cytube.send.playlist.remove"
    assert event4.data["command"] == "playlist.remove"
```

### Phase 5: Validation and Testing

**GOAL-005**: Verify both shell integration tests pass

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Run `pytest tests/integration/test_shell_integration.py::test_shell_add_command_updates_playlist -v` | | |
| TASK-024 | Run `pytest tests/integration/test_workflows.py::test_playlist_manipulation_workflow -v` | | |
| TASK-025 | Verify both tests pass | | |
| TASK-026 | Run both tests 3 times to verify consistency | | |
| TASK-027 | Run full integration test suite to check for regressions | | |
| TASK-028 | Update test documentation with new patterns | | |

## 3. Alternatives

- **ALT-001**: Keep old tests and add new event-driven tests
  - **Rejected**: Duplicates test coverage, old tests don't match current architecture
  
- **ALT-002**: Mock both API calls and event publishing
  - **Rejected**: Over-mocking reduces test value
  
- **ALT-003**: Create end-to-end tests with real EventBus
  - **Deferred**: Good idea but out of scope for this fix

## 4. Dependencies

- **DEP-001**: Sprint 19 Playlist NATS Commands implementation (completed)
- **DEP-002**: Shell commands use EventBus (implemented in Sprint 19)
- **DEP-003**: Event class with subject, event_type, data attributes

## 5. Files

- **FILE-001**: `tests/integration/test_shell_integration.py` - Update 1 test
- **FILE-002**: `tests/integration/test_workflows.py` - Update 1 test
- **FILE-003**: `tests/integration/conftest.py` - Update integration_bot fixture (if exists)
- **FILE-004**: Test file itself if fixture is inline

## 6. Testing

### Unit Tests
- **TEST-001**: Test integration_bot fixture has event_bus mock
- **TEST-002**: Test event_bus.publish is called for each command

### Integration Tests
- **TEST-003**: Run test_shell_add_command_updates_playlist individually
- **TEST-004**: Run test_playlist_manipulation_workflow individually
- **TEST-005**: Run both tests together

### Validation Tests
- **TEST-006**: Verify test output is clear and descriptive
- **TEST-007**: Verify tests run in <5 seconds
- **TEST-008**: Verify no warnings or deprecations

## 7. Risks & Assumptions

### Risks
- **RISK-001**: Event structure may differ from expectations
  - **Mitigation**: Review Sprint 19 implementation for exact event format
  
- **RISK-002**: Fixture changes may affect other integration tests
  - **Mitigation**: Run full integration suite after changes

### Assumptions
- **ASSUMPTION-001**: Shell commands use bot.event_bus.publish() (verified in Sprint 19)
- **ASSUMPTION-002**: Event class has subject, event_type, and data attributes
- **ASSUMPTION-003**: Integration tests should verify event publishing, not end-to-end behavior

## 8. Related Specifications / Further Reading

- [PRD-Test-Infrastructure-Fixes.md](../docs/sprints/active/PRD-Test-Infrastructure-Fixes.md) - Overall PRD
- [SPEC-Playlist-NATS-Commands.md](../docs/sprints/active/SPEC-Playlist-NATS-Commands.md) - Sprint 19 implementation
- [test_shell.py](../../tests/unit/test_shell.py) - Unit test patterns to follow

---

**Estimated Time**: 2 hours  
**Priority**: P1 (High)  
**Sprint**: 20
