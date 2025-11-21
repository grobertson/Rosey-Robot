# Sprint 8 Sortie 4 Summary: Event Bus

**Sprint**: 8-inception (Plugin System)  
**Sortie**: 4 - Event Bus  
**Status**: ✅ Complete  
**Date**: November 21, 2025  

---

## Overview

Implemented pub/sub event bus for inter-plugin communication. Plugins can now publish events that other plugins subscribe to, enabling loosely-coupled plugin ecosystems without direct dependencies.

---

## Implementation Summary

### Files Created

1. **lib/plugin/event.py** (61 lines)
   - `Event` dataclass: name, data, source, priority, timestamp
   - `EventPriority` enum: LOW (0), NORMAL (1), HIGH (2)
   - String representations for logging

2. **lib/plugin/event_bus.py** (318 lines)
   - `EventBus` class: Pub/sub system
   - Subscribe/unsubscribe with wildcard patterns (`*`, `plugin.*`)
   - Priority-based dispatch (HIGH → NORMAL → LOW)
   - Error isolation (handler failures don't affect others)
   - Event history (last N events, default 100)
   - Statistics tracking

3. **tests/unit/test_event_bus_sortie4.py** (718 lines, 30 tests)
   - Event creation and properties
   - Basic pub/sub
   - Wildcard subscriptions
   - Priority dispatch
   - Error isolation
   - Unsubscribe
   - History and filtering
   - Statistics
   - Plugin integration

### Files Modified

4. **lib/plugin/manager.py**
   - Added EventBus instantiation in `__init__`
   - Exposed `event_bus` property to plugins

5. **lib/plugin/base.py**
   - Added `event_bus` property
   - Added `subscribe(pattern, handler)` helper
   - Added `publish(name, data, priority)` helper
   - Auto-unsubscribe in `teardown()`

6. **lib/plugin/__init__.py**
   - Exported `Event`, `EventPriority`, `EventBus`

---

## Architecture

```
┌────────────────────────────────────────┐
│         PluginManager                  │
│    ┌────────────────────┐              │
│    │    EventBus        │              │
│    │  - subscribe()     │              │
│    │  - publish()       │              │
│    │  - history         │              │
│    └────────────────────┘              │
└────────────────────────────────────────┘
         ▲                    ▲
         │                    │
    ┌────┴────┐          ┌────┴────┐
    │ Plugin A │          │ Plugin B │
    │          │          │          │
    │ publish()│          │subscribe()│
    │          │          │          │
    └──────────┘          └──────────┘
```

**Flow**:
1. Plugin B subscribes: `self.subscribe('trivia.*', handler)`
2. Plugin A publishes: `await self.publish('trivia.started', {...})`
3. EventBus matches pattern, dispatches by priority
4. Plugin B's handler receives event

---

## Features

### Wildcard Subscriptions

```python
# Specific event
self.subscribe('trivia.started', self.on_trivia_start)

# All trivia events
self.subscribe('trivia.*', self.on_any_trivia)

# All events
self.subscribe('*', self.on_any_event)
```

### Priority Dispatch

```python
# High priority (validation, anti-spam)
await self.publish('message.received', data, priority=EventPriority.HIGH)

# Normal priority (default)
await self.publish('trivia.started', data)

# Low priority (logging, analytics)
await self.publish('stats.collected', data, priority=EventPriority.LOW)
```

**Dispatch Order**: HIGH → NORMAL → LOW within each event

### Error Isolation

```python
# If handler1 crashes, handler2 still runs
bus.subscribe('test', failing_handler, 'plugin1')
bus.subscribe('test', working_handler, 'plugin2')

await bus.publish(Event('test', {}, 'src'))
# Both handlers called, error logged but not propagated
```

### Event History

```python
# Get last 10 events
recent = bus.get_history(count=10)

# Get all trivia events
trivia_events = bus.get_history(event_pattern='trivia.*')

# Most recent first
for event in recent:
    print(f"{event.name} from {event.source} at {event.timestamp}")
```

---

## Usage Examples

### Example: Trivia Plugin (Publisher)

```python
class TriviaPlugin(Plugin):
    async def start_question(self, question: str):
        """Start trivia, notify other plugins."""
        await self.publish('trivia.started', {
            'question': question,
            'timeout': 30,
            'difficulty': 'medium'
        })
        # ... game logic ...
    
    async def end_question(self, winner: str):
        """End trivia, publish results."""
        await self.publish('trivia.ended', {
            'winner': winner,
            'correct_answer': self.answer,
            'time_elapsed': self.elapsed
        })
```

### Example: Stats Plugin (Subscriber)

```python
class StatsPlugin(Plugin):
    async def setup(self):
        """Subscribe to trivia events."""
        self.subscribe('trivia.*', self.on_trivia_event)
    
    async def on_trivia_event(self, event: Event):
        """Track trivia participation."""
        if event.name == 'trivia.started':
            await self.increment_stat('trivia_questions_asked')
        
        elif event.name == 'trivia.ended':
            winner = event.data['winner']
            await self.increment_stat(f'trivia_wins_{winner}')
            
        self.logger.info(f"Trivia event: {event.name}")
```

### Example: Logger Plugin (Monitor)

```python
class LoggerPlugin(Plugin):
    async def setup(self):
        """Subscribe to ALL events."""
        self.subscribe('*', self.log_event)
    
    async def log_event(self, event: Event):
        """Log all plugin communication."""
        self.logger.info(
            f"Event: {event.name} from {event.source}, "
            f"data keys: {list(event.data.keys())}"
        )
```

---

## Test Coverage

### Test Summary

- **Total Tests**: 30
- **Status**: ✅ All Passing
- **Time**: 0.46s

### Test Categories

1. **Event Tests** (5 tests)
   - Creation, default priority
   - String representations
   - Priority ordering

2. **Basic Pub/Sub** (4 tests)
   - Basic publish/subscribe
   - Multiple subscribers
   - No subscribers

3. **Wildcards** (3 tests)
   - `*` wildcard (all events)
   - Pattern wildcards (`trivia.*`)
   - Multiple patterns

4. **Priority** (1 test)
   - Priority dispatch ordering

5. **Error Handling** (2 tests)
   - Single handler error
   - Multiple handler errors

6. **Unsubscribe** (2 tests)
   - Unsubscribe single pattern
   - Unsubscribe all patterns

7. **History** (4 tests)
   - Event history tracking
   - Count limiting
   - Pattern filtering
   - Max size enforcement

8. **Statistics** (3 tests)
   - Stats tracking
   - Get subscriptions (all)
   - Get subscriptions (filtered)

9. **Plugin Integration** (3 tests)
   - Plugin.subscribe() helper
   - Plugin.publish() helper
   - Auto-unsubscribe on teardown

10. **Utility** (3 tests)
    - String representation
    - Clear history
    - Reset stats

---

## Performance

### Resource Usage

- **Memory**: ~5-10 KB per 100 events in history
- **CPU**: Minimal (pattern matching with fnmatch)
- **Dispatch**: Async, non-blocking

### Scalability

- **Subscribers**: O(N) for N subscribers per pattern
- **Pattern Matching**: O(P) for P patterns
- **History**: O(1) append (fixed-size deque)

---

## Metrics

### Code Stats

- **Implementation**: 379 lines (event.py + event_bus.py)
- **Tests**: 718 lines (30 tests)
- **Modified**: 3 files (manager.py, base.py, __init__.py)
- **Total**: ~1100 lines

### Test Results

```
Platform: Windows (Python 3.12.10)
Sortie 4 Tests: 30 passed (0.46s)
Full Suite: 1099 passed (up from 1069)
Added: 30 tests
Status: All green ✅
```

---

## Design Decisions

### Why Pub/Sub?

**Loose Coupling**: Plugins don't need references to each other. Trivia plugin doesn't know about Stats plugin.

### Why Wildcards?

**Flexibility**: Subscribe to `trivia.*` instead of each event individually. Easy to monitor all events from a plugin.

### Why Priorities?

**Control**: High-priority handlers (anti-spam, validation) run before low-priority (logging, analytics).

### Why Async?

**Non-Blocking**: Publishing event doesn't block. Handlers run concurrently.

### Why Event History?

**Debugging**: See recent events for troubleshooting.  
**Monitoring**: Track event flow through system.  
**Late Subscribers**: New plugins can catch up on missed events.

---

## Acceptance Criteria

### From SPEC-Sortie-4-EventBus.md

- ✅ Event bus with publish/subscribe
- ✅ Async event dispatch
- ✅ Event priorities (HIGH, NORMAL, LOW)
- ✅ Error isolation (one handler fails, others run)
- ✅ Wildcard subscriptions (`*`, `plugin.*`)
- ✅ Event history (last N events)
- ✅ Type-safe event data (Event dataclass)
- ✅ Plugin integration (subscribe/publish helpers)
- ✅ Auto-unsubscribe on teardown
- ✅ Comprehensive tests (30 tests, all passing)

---

## Known Limitations

1. **Event Loops**: No protection against A→B→A event loops (document best practices)
2. **Order Guarantees**: Within same priority, subscription order maintained but not guaranteed across reloads
3. **Memory**: History bounded but no automatic cleanup of old subscriptions
4. **Synchronous**: Handlers run sequentially (async but not parallel)

---

## Future Enhancements

1. **Event Filtering**: Subscribe with filters (`trivia.started` + `difficulty=hard`)
2. **Event Queue**: Buffer events, batch dispatch
3. **Priority Inheritance**: Handlers can adjust priority dynamically
4. **Event Replay**: Replay history for debugging
5. **Metrics Dashboard**: Visualize event flow in web UI
6. **Cross-Bot Events**: Publish events across multiple bot instances via NATS

---

## Related Documents

- [SPEC-Sortie-4-EventBus.md](SPEC-Sortie-4-EventBus.md) - Technical specification
- [PRD-Inception.md](PRD-Inception.md) - Product requirements
- [AGENTS.md](../../../AGENTS.md) - Development workflow

---

## Commit Message

```
Sprint 8 Sortie 4: Event Bus

Implement pub/sub event bus for inter-plugin communication.

Features:
- Event dataclass (name, data, source, priority, timestamp)
- EventPriority enum (LOW, NORMAL, HIGH)
- EventBus with subscribe/unsubscribe
- Wildcard pattern matching (*, plugin.*)
- Priority-based dispatch (HIGH → NORMAL → LOW)
- Error isolation (handler failures don't affect others)
- Event history (last N events, default 100)
- Statistics tracking
- Plugin helpers (subscribe, publish, auto-unsubscribe)

Files Created:
- lib/plugin/event.py (61 lines)
- lib/plugin/event_bus.py (318 lines)
- tests/unit/test_event_bus_sortie4.py (718 lines, 30 tests)

Files Modified:
- lib/plugin/manager.py (EventBus instantiation)
- lib/plugin/base.py (subscribe/publish helpers)
- lib/plugin/__init__.py (exports)

Testing:
- 30 new tests (all passing)
- Full suite: 1099 tests passing (up from 1069)
- Event creation and properties
- Basic pub/sub, wildcards, priorities
- Error isolation, unsubscribe
- History, statistics, plugin integration

Use Cases:
- Trivia plugin publishes trivia.started → Stats plugin tracks
- Quote plugin publishes quote.added → Search plugin indexes
- Any plugin publishes * → Logger plugin monitors all events

Implements: SPEC-Sortie-4-EventBus.md
Related: PRD-Inception.md
```

---

**Sortie Complete**: ✅  
**Next Sortie**: 5 - Service Registry (dependency injection)  
**Sprint Progress**: 4/5 sorties complete
