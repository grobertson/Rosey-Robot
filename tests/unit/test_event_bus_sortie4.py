"""
# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
# This test file is DEPRECATED and scheduled for removal.
#
# Reason: The lib/plugin event bus has been superseded by the NATS-based
# event bus architecture. Events are now handled through NATS messaging.
#
# Reference: See bot/rosey/core/event_bus.py for the NATS-based event bus,
# and plugins/quote-db/ or plugins/dice-roller/ for usage patterns.
#
# TODO: Remove this file once all legacy plugin code is deleted.
# ============================================================================

tests/unit/test_event_bus_sortie4.py

Unit tests for event bus system (Sprint 8 Sortie 4).
"""

import pytest
from datetime import datetime

from lib.plugin import (
    Event,
    EventPriority,
    EventBus,
    Plugin,
    PluginMetadata,
    PluginManager,
)


# =================================================================
# Mock Bot
# =================================================================


class MockBot:
    """Mock bot for testing."""

    def __init__(self):
        self.messages = []
        self.plugin_manager = None

    async def send_message(self, message: str):
        self.messages.append(message)


# =================================================================
# Test Plugins
# =================================================================


class PublisherPlugin(Plugin):
    """Plugin that publishes events."""

    @property
    def metadata(self):
        return PluginMetadata(
            name="publisher",
            display_name="Publisher",
            version="1.0.0",
            description="Publishes events",
            author="Test",
        )

    async def publish_test_event(self, data=None):
        """Publish a test event."""
        await self.publish("test.event", data or {"key": "value"})


class SubscriberPlugin(Plugin):
    """Plugin that subscribes to events."""

    def __init__(self, bot, config=None):
        super().__init__(bot, config)
        self.received_events = []

    @property
    def metadata(self):
        return PluginMetadata(
            name="subscriber",
            display_name="Subscriber",
            version="1.0.0",
            description="Subscribes to events",
            author="Test",
        )

    async def setup(self):
        """Subscribe to events."""
        self.subscribe("test.*", self.on_test_event)

    async def on_test_event(self, event):
        """Handle test events."""
        self.received_events.append(event)


# =================================================================
# Fixtures
# =================================================================


@pytest.fixture
def mock_bot():
    """Create mock bot."""
    return MockBot()


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


# =================================================================
# Event Tests
# =================================================================


def test_event_creation():
    """Test Event dataclass creation."""
    event = Event(
        name="test.event",
        data={"key": "value"},
        source="test_plugin",
        priority=EventPriority.HIGH,
    )

    assert event.name == "test.event"
    assert event.data == {"key": "value"}
    assert event.source == "test_plugin"
    assert event.priority == EventPriority.HIGH
    assert isinstance(event.timestamp, datetime)


def test_event_default_priority():
    """Test Event default priority is NORMAL."""
    event = Event(name="test", data={}, source="test")

    assert event.priority == EventPriority.NORMAL


def test_event_str():
    """Test Event string representation."""
    event = Event(name="test.event", data={}, source="test_plugin")

    result = str(event)

    assert "test.event" in result
    assert "test_plugin" in result


def test_event_repr():
    """Test Event developer representation."""
    event = Event(
        name="test.event",
        data={"key1": "value1", "key2": "value2"},
        source="test_plugin",
    )

    result = repr(event)

    assert "test.event" in result
    assert "test_plugin" in result
    assert "NORMAL" in result
    assert "key1" in result or "key2" in result


def test_event_priority_ordering():
    """Test EventPriority ordering (HIGH > NORMAL > LOW)."""
    assert EventPriority.HIGH > EventPriority.NORMAL
    assert EventPriority.NORMAL > EventPriority.LOW
    assert EventPriority.HIGH > EventPriority.LOW


# =================================================================
# EventBus Basic Tests
# =================================================================


def test_event_bus_creation():
    """Test EventBus initialization."""
    bus = EventBus(history_size=50)

    assert bus._history.maxlen == 50
    assert bus._stats["events_published"] == 0
    assert bus._stats["events_dispatched"] == 0
    assert bus._stats["handler_errors"] == 0


@pytest.mark.asyncio
async def test_basic_publish_subscribe(event_bus):
    """Test basic pub/sub."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("test.event", handler, "test_plugin")

    event = Event("test.event", {"key": "value"}, "publisher")
    await event_bus.publish(event)

    assert len(received) == 1
    assert received[0].name == "test.event"
    assert received[0].data == {"key": "value"}


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus):
    """Test multiple subscribers receive same event."""
    received1 = []
    received2 = []

    async def handler1(event):
        received1.append(event)

    async def handler2(event):
        received2.append(event)

    event_bus.subscribe("test.event", handler1, "plugin1")
    event_bus.subscribe("test.event", handler2, "plugin2")

    event = Event("test.event", {}, "publisher")
    await event_bus.publish(event)

    assert len(received1) == 1
    assert len(received2) == 1
    assert received1[0].name == "test.event"
    assert received2[0].name == "test.event"


@pytest.mark.asyncio
async def test_no_subscribers(event_bus):
    """Test publishing with no subscribers (should not fail)."""
    event = Event("test.event", {}, "publisher")
    await event_bus.publish(event)  # Should not raise

    stats = event_bus.get_stats()
    assert stats["events_published"] == 1
    assert stats["events_dispatched"] == 0


# =================================================================
# Wildcard Tests
# =================================================================


@pytest.mark.asyncio
async def test_wildcard_star(event_bus):
    """Test * wildcard matches all events."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("*", handler, "test_plugin")

    await event_bus.publish(Event("test.event", {}, "pub"))
    await event_bus.publish(Event("other.event", {}, "pub"))
    await event_bus.publish(Event("completely.different", {}, "pub"))

    assert len(received) == 3


@pytest.mark.asyncio
async def test_wildcard_pattern(event_bus):
    """Test pattern wildcards (trivia.*)."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("trivia.*", handler, "test_plugin")

    await event_bus.publish(Event("trivia.started", {}, "trivia"))
    await event_bus.publish(Event("trivia.ended", {}, "trivia"))
    await event_bus.publish(Event("quote.added", {}, "quote"))

    assert len(received) == 2  # Only trivia.* events
    assert received[0].name == "trivia.started"
    assert received[1].name == "trivia.ended"


@pytest.mark.asyncio
async def test_multiple_patterns(event_bus):
    """Test subscriber with multiple patterns."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("trivia.*", handler, "test_plugin")
    event_bus.subscribe("quote.*", handler, "test_plugin")

    await event_bus.publish(Event("trivia.started", {}, "trivia"))
    await event_bus.publish(Event("quote.added", {}, "quote"))
    await event_bus.publish(Event("other.event", {}, "other"))

    assert len(received) == 2  # trivia.* and quote.*


# =================================================================
# Priority Tests
# =================================================================


@pytest.mark.asyncio
async def test_priority_dispatch_order(event_bus):
    """Test events dispatched by priority (HIGH -> NORMAL -> LOW)."""
    order = []

    async def high_handler(event):
        order.append("high")

    async def normal_handler(event):
        order.append("normal")

    async def low_handler(event):
        order.append("low")

    event_bus.subscribe("test", high_handler, "high")
    event_bus.subscribe("test", normal_handler, "normal")
    event_bus.subscribe("test", low_handler, "low")

    # Publish HIGH priority event
    await event_bus.publish(
        Event("test", {}, "src", priority=EventPriority.HIGH)
    )

    # All handlers run, but HIGH priority first
    assert order[0] == "high"

    # Clear for next test
    order.clear()

    # Publish LOW priority event
    await event_bus.publish(Event("test", {}, "src", priority=EventPriority.LOW))

    # LOW priority means all handlers run last
    assert order == ["high", "normal", "low"]


# =================================================================
# Error Isolation Tests
# =================================================================


@pytest.mark.asyncio
async def test_handler_error_isolation(event_bus):
    """Test handler error doesn't affect other handlers."""
    received = []

    async def failing_handler(event):
        raise ValueError("Handler failed!")

    async def working_handler(event):
        received.append(event)

    event_bus.subscribe("test", failing_handler, "bad")
    event_bus.subscribe("test", working_handler, "good")

    await event_bus.publish(Event("test", {}, "src"))

    # Working handler should still receive event
    assert len(received) == 1

    # Error should be tracked in stats
    stats = event_bus.get_stats()
    assert stats["handler_errors"] == 1


@pytest.mark.asyncio
async def test_multiple_handler_errors(event_bus):
    """Test multiple handler errors tracked correctly."""
    async def failing_handler1(event):
        raise ValueError("Error 1")

    async def failing_handler2(event):
        raise RuntimeError("Error 2")

    event_bus.subscribe("test", failing_handler1, "bad1")
    event_bus.subscribe("test", failing_handler2, "bad2")

    await event_bus.publish(Event("test", {}, "src"))

    stats = event_bus.get_stats()
    assert stats["handler_errors"] == 2


# =================================================================
# Unsubscribe Tests
# =================================================================


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    """Test unsubscribe removes handler."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("test", handler, "test_plugin")

    # First publish
    await event_bus.publish(Event("test", {}, "src"))
    assert len(received) == 1

    # Unsubscribe
    event_bus.unsubscribe("test", "test_plugin")

    # Second publish (should not receive)
    await event_bus.publish(Event("test", {}, "src"))
    assert len(received) == 1  # Still 1


@pytest.mark.asyncio
async def test_unsubscribe_all(event_bus):
    """Test unsubscribe_all removes all patterns."""
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("test1", handler, "test_plugin")
    event_bus.subscribe("test2", handler, "test_plugin")

    # Unsubscribe all
    event_bus.unsubscribe_all("test_plugin")

    # Publish both events (should not receive)
    await event_bus.publish(Event("test1", {}, "src"))
    await event_bus.publish(Event("test2", {}, "src"))

    assert len(received) == 0


# =================================================================
# History Tests
# =================================================================


@pytest.mark.asyncio
async def test_event_history(event_bus):
    """Test event history tracks published events."""
    await event_bus.publish(Event("test1", {"num": 1}, "src"))
    await event_bus.publish(Event("test2", {"num": 2}, "src"))
    await event_bus.publish(Event("test3", {"num": 3}, "src"))

    history = event_bus.get_history()

    assert len(history) == 3
    assert history[0].name == "test3"  # Most recent first
    assert history[1].name == "test2"
    assert history[2].name == "test1"


@pytest.mark.asyncio
async def test_history_count_limit(event_bus):
    """Test history count parameter."""
    for i in range(5):
        await event_bus.publish(Event(f"test{i}", {}, "src"))

    history = event_bus.get_history(count=2)

    assert len(history) == 2
    assert history[0].name == "test4"  # Most recent
    assert history[1].name == "test3"


@pytest.mark.asyncio
async def test_history_pattern_filter(event_bus):
    """Test history filtering by pattern."""
    await event_bus.publish(Event("trivia.started", {}, "trivia"))
    await event_bus.publish(Event("quote.added", {}, "quote"))
    await event_bus.publish(Event("trivia.ended", {}, "trivia"))

    history = event_bus.get_history(event_pattern="trivia.*")

    assert len(history) == 2
    assert history[0].name == "trivia.ended"
    assert history[1].name == "trivia.started"


@pytest.mark.asyncio
async def test_history_max_size():
    """Test history respects max size."""
    bus = EventBus(history_size=3)

    for i in range(5):
        await bus.publish(Event(f"test{i}", {}, "src"))

    history = bus.get_history()

    # Should only keep last 3
    assert len(history) == 3
    assert history[0].name == "test4"
    assert history[1].name == "test3"
    assert history[2].name == "test2"


# =================================================================
# Statistics Tests
# =================================================================


@pytest.mark.asyncio
async def test_stats_tracking(event_bus):
    """Test statistics are tracked correctly."""
    async def handler(event):
        pass

    event_bus.subscribe("test", handler, "plugin1")
    event_bus.subscribe("test", handler, "plugin2")

    await event_bus.publish(Event("test", {}, "src"))

    stats = event_bus.get_stats()

    assert stats["events_published"] == 1
    assert stats["events_dispatched"] == 2  # 2 handlers
    assert stats["handler_errors"] == 0


@pytest.mark.asyncio
async def test_get_subscriptions(event_bus):
    """Test get_subscriptions returns correct mapping."""
    async def handler(event):
        pass

    event_bus.subscribe("test1", handler, "plugin1")
    event_bus.subscribe("test2", handler, "plugin1")
    event_bus.subscribe("test1", handler, "plugin2")

    subs = event_bus.get_subscriptions()

    assert "plugin1" in subs["test1"]
    assert "plugin1" in subs["test2"]
    assert "plugin2" in subs["test1"]


@pytest.mark.asyncio
async def test_get_subscriptions_filtered(event_bus):
    """Test get_subscriptions with plugin filter."""
    async def handler(event):
        pass

    event_bus.subscribe("test1", handler, "plugin1")
    event_bus.subscribe("test2", handler, "plugin1")
    event_bus.subscribe("test1", handler, "plugin2")

    subs = event_bus.get_subscriptions(plugin_name="plugin1")

    assert "plugin1" in subs["test1"]
    assert "plugin1" in subs["test2"]
    assert "plugin2" not in str(subs)


# =================================================================
# Plugin Integration Tests
# =================================================================


@pytest.mark.asyncio
async def test_plugin_subscribe_helper(mock_bot):
    """Test Plugin.subscribe() helper method."""
    manager = PluginManager(mock_bot)
    mock_bot.plugin_manager = manager

    plugin = SubscriberPlugin(mock_bot)
    await plugin.setup()

    # Publish event
    await manager.event_bus.publish(Event("test.event", {"data": "value"}, "pub"))

    # Should receive event
    assert len(plugin.received_events) == 1
    assert plugin.received_events[0].name == "test.event"


@pytest.mark.asyncio
async def test_plugin_publish_helper(mock_bot):
    """Test Plugin.publish() helper method."""
    manager = PluginManager(mock_bot)
    mock_bot.plugin_manager = manager

    received = []

    async def handler(event):
        received.append(event)

    manager.event_bus.subscribe("test.event", handler, "subscriber")

    # Publish from plugin
    plugin = PublisherPlugin(mock_bot)
    await plugin.publish_test_event({"key": "value"})

    # Should receive event
    assert len(received) == 1
    assert received[0].name == "test.event"
    assert received[0].data == {"key": "value"}
    assert received[0].source == "publisher"


@pytest.mark.asyncio
async def test_plugin_auto_unsubscribe(mock_bot):
    """Test Plugin.teardown() auto-unsubscribes."""
    manager = PluginManager(mock_bot)
    mock_bot.plugin_manager = manager

    plugin = SubscriberPlugin(mock_bot)
    await plugin.setup()

    # Verify subscribed
    subs = manager.event_bus.get_subscriptions("subscriber")
    assert "test.*" in subs

    # Teardown
    await plugin.teardown()

    # Should be unsubscribed
    subs = manager.event_bus.get_subscriptions("subscriber")
    assert len(subs) == 0


# =================================================================
# Utility Tests
# =================================================================


def test_event_bus_repr(event_bus):
    """Test EventBus string representation."""
    async def handler(event):
        pass

    event_bus.subscribe("test", handler, "plugin1")

    result = repr(event_bus)

    assert "EventBus" in result
    assert "1 subscriptions" in result


@pytest.mark.asyncio
async def test_clear_history(event_bus):
    """Test clearing event history."""
    await event_bus.publish(Event("test", {}, "src"))
    await event_bus.publish(Event("test", {}, "src"))

    assert len(event_bus.get_history()) == 2

    event_bus.clear_history()

    assert len(event_bus.get_history()) == 0


@pytest.mark.asyncio
async def test_reset_stats(event_bus):
    """Test resetting statistics."""
    await event_bus.publish(Event("test", {}, "src"))

    stats = event_bus.get_stats()
    assert stats["events_published"] == 1

    event_bus.reset_stats()

    stats = event_bus.get_stats()
    assert stats["events_published"] == 0
