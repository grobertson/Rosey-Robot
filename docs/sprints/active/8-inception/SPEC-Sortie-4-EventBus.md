# Sprint 8, Sortie 4: Event Bus

**Status:** Planning  
**Estimated Effort:** 4 hours  
**Sprint:** Inception (Sprint 8)  
**Phase:** 2 - Plugin Communication  
**Dependencies:** Sortie 1 (Plugin base class), Sortie 2 (PluginManager)

## Objective

Implement event bus for inter-plugin communication. Enable plugins to publish events that other plugins can subscribe to, creating a loosely-coupled plugin ecosystem.

## Background

Plugins need to communicate:
- **Trivia plugin** publishes "trivia_started" event
- **Stats plugin** subscribes, tracks trivia participation
- **Quote plugin** publishes "quote_added" event
- **Search plugin** subscribes, indexes quotes

Event bus provides pub/sub without tight coupling.

## Success Criteria

- ✅ Event bus with publish/subscribe
- ✅ Async event dispatch
- ✅ Event priorities (high, normal, low)
- ✅ Error isolation (one handler fails, others run)
- ✅ Wildcard subscriptions (*, plugin.*)
- ✅ Event history (last N events)
- ✅ Type-safe event data

## Technical Design

### Event Structure

```python
"""
lib/plugin/event.py

Event structure for inter-plugin communication.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from datetime import datetime
from enum import IntEnum


class EventPriority(IntEnum):
    """Event priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class Event:
    """
    Event for inter-plugin communication.
    
    Attributes:
        name: Event name (e.g., 'trivia.started', 'quote.added')
        data: Event data (any JSON-serializable data)
        source: Name of plugin that published event
        priority: Event priority (affects dispatch order)
        timestamp: When event was created
    """
    name: str
    data: Dict[str, Any]
    source: str
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return f"Event({self.name} from {self.source})"
```

### Event Bus Implementation

```python
"""
lib/plugin/event_bus.py

Pub/sub event bus for inter-plugin communication.
"""

import asyncio
import fnmatch
from typing import Dict, List, Callable, Optional, Set
from collections import defaultdict, deque
import logging

from .event import Event, EventPriority


class EventBus:
    """
    Pub/sub event bus for plugins.
    
    Features:
    - Subscribe to events by name or pattern
    - Publish events with priority
    - Async dispatch (non-blocking)
    - Error isolation (one handler fails, others run)
    - Event history (last N events)
    
    Args:
        history_size: Number of events to keep in history (default: 100)
        logger: Optional logger instance
    """
    
    def __init__(self, history_size: int = 100,
                 logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger('plugin.event_bus')
        
        # Subscriptions: event_pattern -> list of (plugin_name, handler)
        self._subscriptions: Dict[str, List[tuple[str, Callable]]] = defaultdict(list)
        
        # Event history
        self._history: deque[Event] = deque(maxlen=history_size)
        
        # Statistics
        self._stats = {
            'events_published': 0,
            'events_dispatched': 0,
            'handler_errors': 0
        }
    
    def subscribe(self, event_pattern: str, handler: Callable,
                 plugin_name: str) -> None:
        """
        Subscribe to events matching pattern.
        
        Args:
            event_pattern: Event name or pattern (supports * wildcard)
            handler: Async function to call on event
            plugin_name: Name of subscribing plugin
        
        Examples:
            bus.subscribe('trivia.started', handler, 'stats')
            bus.subscribe('trivia.*', handler, 'logger')  # All trivia events
            bus.subscribe('*', handler, 'monitor')  # All events
        """
        self._subscriptions[event_pattern].append((plugin_name, handler))
        self.logger.debug(f"{plugin_name} subscribed to {event_pattern}")
    
    def unsubscribe(self, event_pattern: str, plugin_name: str) -> None:
        """
        Unsubscribe plugin from event pattern.
        
        Args:
            event_pattern: Event pattern to unsubscribe from
            plugin_name: Name of plugin
        """
        if event_pattern in self._subscriptions:
            self._subscriptions[event_pattern] = [
                (name, handler) for name, handler in self._subscriptions[event_pattern]
                if name != plugin_name
            ]
    
    def unsubscribe_all(self, plugin_name: str) -> None:
        """
        Unsubscribe plugin from all events.
        
        Args:
            plugin_name: Name of plugin
        """
        for pattern in list(self._subscriptions.keys()):
            self.unsubscribe(pattern, plugin_name)
    
    async def publish(self, event: Event) -> None:
        """
        Publish event to subscribers.
        
        Args:
            event: Event to publish
        """
        self._stats['events_published'] += 1
        
        # Add to history
        self._history.append(event)
        
        # Find matching subscribers
        handlers = self._find_handlers(event.name)
        
        if not handlers:
            self.logger.debug(f"No subscribers for: {event.name}")
            return
        
        # Sort by priority (high -> normal -> low)
        # Within same priority, maintain subscription order
        handlers_by_priority = defaultdict(list)
        for plugin_name, handler in handlers:
            handlers_by_priority[event.priority].append((plugin_name, handler))
        
        # Dispatch in priority order
        for priority in sorted(handlers_by_priority.keys(), reverse=True):
            await self._dispatch_handlers(
                event,
                handlers_by_priority[priority]
            )
    
    def _find_handlers(self, event_name: str) -> List[tuple[str, Callable]]:
        """
        Find all handlers matching event name.
        
        Args:
            event_name: Event name to match
        
        Returns:
            List of (plugin_name, handler) tuples
        """
        handlers = []
        
        for pattern, subscribers in self._subscriptions.items():
            if fnmatch.fnmatch(event_name, pattern):
                handlers.extend(subscribers)
        
        return handlers
    
    async def _dispatch_handlers(self, event: Event,
                                 handlers: List[tuple[str, Callable]]) -> None:
        """
        Dispatch event to handlers.
        
        Args:
            event: Event to dispatch
            handlers: List of (plugin_name, handler) tuples
        """
        for plugin_name, handler in handlers:
            try:
                self._stats['events_dispatched'] += 1
                await handler(event)
            
            except Exception as e:
                self._stats['handler_errors'] += 1
                self.logger.error(
                    f"Error in {plugin_name} handling {event.name}: {e}"
                )
                # Continue with other handlers
    
    def get_history(self, count: Optional[int] = None,
                   event_pattern: Optional[str] = None) -> List[Event]:
        """
        Get event history.
        
        Args:
            count: Number of recent events to return (None = all)
            event_pattern: Filter by event name pattern (None = all)
        
        Returns:
            List of events (most recent first)
        """
        events = list(reversed(self._history))
        
        # Filter by pattern
        if event_pattern:
            events = [e for e in events if fnmatch.fnmatch(e.name, event_pattern)]
        
        # Limit count
        if count:
            events = events[:count]
        
        return events
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get event bus statistics.
        
        Returns:
            Dict with stats (events_published, events_dispatched, handler_errors)
        """
        return self._stats.copy()
    
    def get_subscriptions(self, plugin_name: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get current subscriptions.
        
        Args:
            plugin_name: Filter by plugin name (None = all)
        
        Returns:
            Dict mapping event patterns to plugin names
        """
        result = defaultdict(list)
        
        for pattern, subscribers in self._subscriptions.items():
            for name, _ in subscribers:
                if plugin_name is None or name == plugin_name:
                    result[pattern].append(name)
        
        return dict(result)
```

### Plugin Integration

```python
# lib/plugin/base.py

class Plugin(ABC):
    """Plugin base class with event bus access."""
    
    def __init__(self, bot, config=None):
        # ... existing code ...
        self._event_subscriptions = []  # Track subscriptions for cleanup
    
    @property
    def event_bus(self):
        """Access event bus."""
        return self.bot.plugin_manager.event_bus
    
    def subscribe(self, event_pattern: str, handler: Callable) -> None:
        """
        Subscribe to event pattern.
        
        Args:
            event_pattern: Event name or pattern
            handler: Async function(event) to call
        
        Example:
            self.subscribe('trivia.started', self.on_trivia_start)
        """
        self.event_bus.subscribe(event_pattern, handler, self.metadata.name)
        self._event_subscriptions.append(event_pattern)
    
    async def publish(self, event_name: str, data: Dict[str, Any],
                     priority: EventPriority = EventPriority.NORMAL) -> None:
        """
        Publish event.
        
        Args:
            event_name: Event name (recommend: plugin.action format)
            data: Event data
            priority: Event priority
        
        Example:
            await self.publish('trivia.started', {
                'question': 'What is the answer?',
                'timeout': 30
            })
        """
        event = Event(
            name=event_name,
            data=data,
            source=self.metadata.name,
            priority=priority
        )
        await self.event_bus.publish(event)
    
    async def teardown(self) -> None:
        """Cleanup (unsubscribe from all events)."""
        for pattern in self._event_subscriptions:
            self.event_bus.unsubscribe(pattern, self.metadata.name)
        self._event_subscriptions.clear()
```

### Example: Inter-Plugin Communication

```python
# plugins/trivia_plugin.py

class TriviaPlugin(Plugin):
    """Trivia game plugin that publishes events."""
    
    async def start_trivia(self, question: str):
        """Start trivia question."""
        # Publish event for other plugins
        await self.publish('trivia.started', {
            'question': question,
            'timeout': 30
        })
        
        # ... trivia game logic ...
    
    async def end_trivia(self, winner: str, answer: str):
        """End trivia question."""
        await self.publish('trivia.ended', {
            'winner': winner,
            'answer': answer
        })


# plugins/stats_plugin.py

class StatsPlugin(Plugin):
    """Stats plugin that tracks trivia participation."""
    
    async def setup(self):
        """Subscribe to trivia events."""
        self.subscribe('trivia.*', self.on_trivia_event)
    
    async def on_trivia_event(self, event: Event):
        """Handle trivia events."""
        if event.name == 'trivia.started':
            self.logger.info(f"Trivia started: {event.data['question']}")
        
        elif event.name == 'trivia.ended':
            winner = event.data['winner']
            # Update stats database
            await self.update_trivia_stats(winner)
```

## Implementation Steps

1. **Create event module** (30 min)
   ```bash
   touch lib/plugin/event.py
   touch lib/plugin/event_bus.py
   ```

2. **Implement Event dataclass** (15 min)
   - Define Event structure
   - Add EventPriority enum
   - Add __str__ method

3. **Implement EventBus** (2 hours)
   - Subscribe/unsubscribe methods
   - Pattern matching (fnmatch)
   - Publish with priority sorting
   - Async dispatch
   - Error isolation
   - Event history

4. **Integrate with Plugin base** (45 min)
   - Add event_bus property
   - Add subscribe() helper
   - Add publish() helper
   - Auto-unsubscribe in teardown()

5. **Integrate with PluginManager** (30 min)
   - Create EventBus in __init__
   - Expose to plugins via bot

6. **Write unit tests** (1.5 hours)
   ```python
   # test/test_event_bus.py
   
   import pytest
   from lib.plugin import Event, EventBus, EventPriority
   
   
   @pytest.mark.asyncio
   async def test_subscribe_and_publish():
       """Test basic pub/sub."""
       bus = EventBus()
       
       received = []
       
       async def handler(event):
           received.append(event)
       
       bus.subscribe('test.event', handler, 'test_plugin')
       
       event = Event('test.event', {'key': 'value'}, 'publisher')
       await bus.publish(event)
       
       assert len(received) == 1
       assert received[0].name == 'test.event'
   
   
   @pytest.mark.asyncio
   async def test_wildcard_subscription():
       """Test wildcard patterns."""
       bus = EventBus()
       
       received = []
       
       async def handler(event):
           received.append(event)
       
       bus.subscribe('trivia.*', handler, 'test_plugin')
       
       await bus.publish(Event('trivia.started', {}, 'trivia'))
       await bus.publish(Event('trivia.ended', {}, 'trivia'))
       await bus.publish(Event('quote.added', {}, 'quote'))
       
       assert len(received) == 2  # Only trivia.* events
   
   
   @pytest.mark.asyncio
   async def test_priority_dispatch():
       """Test events dispatched by priority."""
       bus = EventBus()
       
       order = []
       
       async def high_handler(event):
           order.append('high')
       
       async def normal_handler(event):
           order.append('normal')
       
       async def low_handler(event):
           order.append('low')
       
       bus.subscribe('test', high_handler, 'high')
       bus.subscribe('test', normal_handler, 'normal')
       bus.subscribe('test', low_handler, 'low')
       
       # Publish with different priorities
       await bus.publish(Event('test', {}, 'src', priority=EventPriority.HIGH))
       await bus.publish(Event('test', {}, 'src', priority=EventPriority.NORMAL))
       await bus.publish(Event('test', {}, 'src', priority=EventPriority.LOW))
       
       # HIGH priority should dispatch first
       assert order[0] == 'high'
   
   
   @pytest.mark.asyncio
   async def test_error_isolation():
       """Test handler error doesn't affect others."""
       bus = EventBus()
       
       received = []
       
       async def failing_handler(event):
           raise ValueError("Handler failed!")
       
       async def working_handler(event):
           received.append(event)
       
       bus.subscribe('test', failing_handler, 'bad')
       bus.subscribe('test', working_handler, 'good')
       
       await bus.publish(Event('test', {}, 'src'))
       
       # Working handler should still receive event
       assert len(received) == 1
   ```

7. **Example plugins** (30 min)
   - Create example publisher plugin
   - Create example subscriber plugin
   - Demonstrate patterns

8. **Validation** (30 min)
   ```bash
   mypy lib/plugin/event*.py
   pylint lib/plugin/event*.py
   pytest test/test_event_bus.py -v
   ```

## Testing Strategy

### Unit Tests

- ✅ Basic pub/sub
- ✅ Wildcard subscriptions
- ✅ Priority dispatch
- ✅ Error isolation
- ✅ Unsubscribe
- ✅ Event history
- ✅ Statistics

### Integration Tests

- ✅ Multiple plugins communicate
- ✅ Plugin publishes, another subscribes
- ✅ Hot reload preserves subscriptions

## Dependencies

**Python Packages:**
- None (pure Python, fnmatch is stdlib)

**Internal Modules:**
- `lib/plugin/base.py` (Sortie 1)
- `lib/plugin/manager.py` (Sortie 2)

## Validation

Before moving to Sortie 5:

1. ✅ EventBus class complete
2. ✅ Pub/sub works
3. ✅ Wildcards work
4. ✅ Priority dispatch works
5. ✅ Error isolation works
6. ✅ Plugin integration complete
7. ✅ All tests pass

## Risks & Mitigations

**Risk:** Event loops (A publishes, B subscribes and publishes back to A)  
**Mitigation:** Document best practices. Consider max dispatch depth if needed.

**Risk:** Performance with many subscriptions  
**Mitigation:** Pattern matching is fast (fnmatch). Profile if issues arise.

**Risk:** Memory leaks from history  
**Mitigation:** Fixed-size deque (default 100 events)

**Risk:** Plugin unload doesn't unsubscribe  
**Mitigation:** Auto-unsubscribe in Plugin.teardown()

## Design Decisions

### Why Pub/Sub?

Loose coupling. Plugins don't need references to each other.

### Why Wildcards?

Flexible subscriptions. Subscribe to 'trivia.*' instead of each event individually.

### Why Priorities?

Control dispatch order. High-priority handlers (validation) run before low-priority (logging).

### Why Async?

Non-blocking. Publishing event doesn't wait for all handlers.

### Why Event History?

Debugging, monitoring, late subscribers can catch up.

## Next Steps

After completion, proceed to:

- **Sortie 5:** Implement service registry (dependency injection)
- **Sortie 6:** Implement plugin management commands (!plugin list/reload/etc.)

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 8 - Inception
