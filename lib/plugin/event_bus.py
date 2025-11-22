"""
lib/plugin/event_bus.py

Pub/sub event bus for inter-plugin communication.
"""

import fnmatch
from typing import Dict, List, Callable, Optional, Tuple
from collections import defaultdict, deque
import logging

from .event import Event


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

    Example:
        bus = EventBus()
        
        # Subscribe to specific event
        async def on_trivia(event):
            print(f"Trivia: {event.data['question']}")
        
        bus.subscribe('trivia.started', on_trivia, 'stats_plugin')
        
        # Publish event
        event = Event('trivia.started', {'question': 'What is 2+2?'}, 'trivia_plugin')
        await bus.publish(event)
    """

    def __init__(
        self, history_size: int = 100, logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger("plugin.event_bus")

        # Subscriptions: event_pattern -> list of (plugin_name, handler)
        self._subscriptions: Dict[str, List[Tuple[str, Callable]]] = defaultdict(list)

        # Event history
        self._history: deque = deque(maxlen=history_size)

        # Statistics
        self._stats = {
            "events_published": 0,
            "events_dispatched": 0,
            "handler_errors": 0,
        }

    def subscribe(self, event_pattern: str, handler: Callable, plugin_name: str) -> None:
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
        self.logger.debug(f"📡 {plugin_name} subscribed to {event_pattern}")

    def unsubscribe(self, event_pattern: str, plugin_name: str) -> None:
        """
        Unsubscribe plugin from event pattern.

        Args:
            event_pattern: Event pattern to unsubscribe from
            plugin_name: Name of plugin
        """
        if event_pattern in self._subscriptions:
            original_count = len(self._subscriptions[event_pattern])
            self._subscriptions[event_pattern] = [
                (name, handler)
                for name, handler in self._subscriptions[event_pattern]
                if name != plugin_name
            ]
            removed = original_count - len(self._subscriptions[event_pattern])
            if removed > 0:
                self.logger.debug(
                    f"📡 {plugin_name} unsubscribed from {event_pattern}"
                )

    def unsubscribe_all(self, plugin_name: str) -> None:
        """
        Unsubscribe plugin from all events.

        Args:
            plugin_name: Name of plugin
        """
        patterns_unsubscribed = 0
        for pattern in list(self._subscriptions.keys()):
            original_count = len(self._subscriptions[pattern])
            self.unsubscribe(pattern, plugin_name)
            if len(self._subscriptions[pattern]) < original_count:
                patterns_unsubscribed += 1

        if patterns_unsubscribed > 0:
            self.logger.debug(
                f"📡 {plugin_name} unsubscribed from {patterns_unsubscribed} patterns"
            )

    async def publish(self, event: Event) -> None:
        """
        Publish event to subscribers.

        Args:
            event: Event to publish
        """
        self._stats["events_published"] += 1

        # Add to history
        self._history.append(event)

        # Find matching subscribers
        handlers = self._find_handlers(event.name)

        if not handlers:
            self.logger.debug(f"📡 No subscribers for: {event.name}")
            return

        self.logger.debug(
            f"📡 Publishing {event.name} from {event.source} "
            f"to {len(handlers)} handler(s)"
        )

        # Sort handlers by event priority
        # Within same priority, maintain subscription order
        handlers_by_priority = defaultdict(list)
        for plugin_name, handler in handlers:
            handlers_by_priority[event.priority].append((plugin_name, handler))

        # Dispatch in priority order (high -> normal -> low)
        for priority in sorted(handlers_by_priority.keys(), reverse=True):
            await self._dispatch_handlers(event, handlers_by_priority[priority])

    def _find_handlers(self, event_name: str) -> List[Tuple[str, Callable]]:
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

    async def _dispatch_handlers(
        self, event: Event, handlers: List[Tuple[str, Callable]]
    ) -> None:
        """
        Dispatch event to handlers.

        Args:
            event: Event to dispatch
            handlers: List of (plugin_name, handler) tuples
        """
        for plugin_name, handler in handlers:
            try:
                self._stats["events_dispatched"] += 1
                await handler(event)

            except Exception as e:
                self._stats["handler_errors"] += 1
                self.logger.error(
                    f"❌ Error in {plugin_name} handling {event.name}: {e}",
                    exc_info=True,
                )
                # Continue with other handlers (error isolation)

    def get_history(
        self, count: Optional[int] = None, event_pattern: Optional[str] = None
    ) -> List[Event]:
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

    def get_subscriptions(
        self, plugin_name: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get current subscriptions.

        Args:
            plugin_name: Filter by plugin name (None = all)

        Returns:
            Dict mapping event patterns to list of plugin names
        """
        result = defaultdict(list)

        for pattern, subscribers in self._subscriptions.items():
            for name, _ in subscribers:
                if plugin_name is None or name == plugin_name:
                    if name not in result[pattern]:  # Avoid duplicates
                        result[pattern].append(name)

        return dict(result)

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
        self.logger.debug("📡 Event history cleared")

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "events_published": 0,
            "events_dispatched": 0,
            "handler_errors": 0,
        }
        self.logger.debug("📡 Statistics reset")

    def __repr__(self) -> str:
        """Developer representation."""
        sub_count = sum(len(subs) for subs in self._subscriptions.values())
        return (
            f"<EventBus: {sub_count} subscriptions, "
            f"{len(self._history)} events in history>"
        )
