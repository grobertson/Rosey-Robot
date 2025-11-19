# Sortie 8: Testing & Validation

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐⭐⭐ (Comprehensive Coverage)  
**Estimated Time:** 4-6 hours  
**Priority:** CRITICAL  
**Dependencies:** All previous sorties (1-7)

---

## Objective

Implement comprehensive test suite to validate the entire Quicksilver architecture works correctly. This includes unit tests (individual components), integration tests (components working together), performance tests (latency/throughput), and end-to-end tests (full user workflows).

---

## Testing Strategy

### Test Pyramid

```
           ┌──────────────┐
           │     E2E      │  5% - Full workflows (slow, expensive)
           │   (5 tests)  │
           └──────────────┘
         ┌────────────────────┐
         │   Integration      │  20% - Component interaction
         │    (30 tests)      │
         └────────────────────┘
     ┌──────────────────────────┐
     │      Unit Tests          │  75% - Individual functions
     │      (120+ tests)        │
     └──────────────────────────┘
```

### Coverage Goals

- **Unit Tests**: 80%+ coverage of individual modules
- **Integration Tests**: All component boundaries tested
- **Performance Tests**: p99 latency < 10ms, throughput > 1000 msg/sec
- **E2E Tests**: Critical user paths validated

### Test Environments

1. **Unit**: Mock dependencies, isolated testing
2. **Integration**: Real NATS server (in-memory or Docker)
3. **Performance**: Dedicated NATS server, production-like config
4. **E2E**: Full stack with real plugins

---

## Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_event_bus.py
│   ├── test_subjects.py
│   ├── test_router.py
│   ├── test_plugin_interface.py
│   ├── test_plugin_process.py
│   ├── test_plugin_manager.py
│   └── test_permissions.py
│
├── integration/             # Integration tests
│   ├── test_nats_integration.py
│   ├── test_connector_integration.py
│   ├── test_plugin_communication.py
│   ├── test_command_flow.py
│   └── test_multi_plugin.py
│
├── performance/             # Performance tests
│   ├── test_latency.py
│   ├── test_throughput.py
│   ├── test_concurrency.py
│   └── test_resource_usage.py
│
├── e2e/                     # End-to-end tests
│   ├── test_user_command.py
│   ├── test_plugin_lifecycle.py
│   ├── test_crash_recovery.py
│   └── test_multi_platform.py
│
└── fixtures/                # Test fixtures
    ├── conftest.py
    ├── mock_nats.py
    ├── mock_plugins.py
    └── test_data.py
```

---

## Implementation

### Task 8.1: Unit Tests - EventBus

**File:** `tests/unit/test_event_bus.py`

```python
"""
Unit tests for EventBus
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from bot.rosey.core.event_bus import EventBus, Event


@pytest.mark.asyncio
class TestEvent:
    """Test Event dataclass"""
    
    def test_event_creation(self):
        """Test creating event"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"}
        )
        
        assert event.subject == "rosey.test"
        assert event.event_type == "test.event"
        assert event.source == "test"
        assert event.data["key"] == "value"
        assert event.correlation_id is not None
        assert event.timestamp is not None
    
    def test_event_to_dict(self):
        """Test event serialization"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"key": "value"}
        )
        
        data = event.to_dict()
        
        assert data["subject"] == "rosey.test"
        assert data["event_type"] == "test.event"
        assert data["data"]["key"] == "value"
        assert "correlation_id" in data
        assert "timestamp" in data
    
    def test_event_from_dict(self):
        """Test event deserialization"""
        data = {
            "subject": "rosey.test",
            "event_type": "test.event",
            "source": "test",
            "data": {"key": "value"},
            "correlation_id": "test-123",
            "timestamp": 1234567890.0
        }
        
        event = Event.from_dict(data)
        
        assert event.subject == "rosey.test"
        assert event.event_type == "test.event"
        assert event.correlation_id == "test-123"


@pytest.mark.asyncio
class TestEventBus:
    """Test EventBus class"""
    
    @pytest.fixture
    async def mock_nats(self):
        """Mock NATS client"""
        nc = AsyncMock()
        nc.is_connected = True
        nc.jetstream = Mock(return_value=AsyncMock())
        return nc
    
    @pytest.fixture
    async def event_bus(self, mock_nats):
        """Create EventBus with mocked NATS"""
        with patch('nats.connect', return_value=mock_nats):
            bus = EventBus(servers=["nats://localhost:4222"])
            await bus.connect()
            return bus
    
    async def test_connect(self, mock_nats):
        """Test connecting to NATS"""
        with patch('nats.connect', return_value=mock_nats) as mock_connect:
            bus = EventBus(servers=["nats://localhost:4222"])
            await bus.connect()
            
            assert bus.is_connected()
            mock_connect.assert_called_once()
    
    async def test_disconnect(self, event_bus):
        """Test disconnecting from NATS"""
        await event_bus.disconnect()
        
        assert not event_bus.is_connected()
    
    async def test_publish(self, event_bus, mock_nats):
        """Test publishing event"""
        event = Event(
            subject="rosey.test",
            event_type="test.event",
            source="test",
            data={"message": "hello"}
        )
        
        await event_bus.publish(event)
        
        # Verify NATS publish was called
        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        assert call_args[0][0] == "rosey.test"  # subject
    
    async def test_subscribe(self, event_bus, mock_nats):
        """Test subscribing to subject"""
        callback = AsyncMock()
        
        await event_bus.subscribe("rosey.test.>", callback)
        
        # Verify NATS subscribe was called
        mock_nats.subscribe.assert_called_once()
    
    async def test_request_reply(self, event_bus, mock_nats):
        """Test request/reply pattern"""
        # Mock NATS request
        mock_response = Mock()
        mock_response.data = b'{"result": "success"}'
        mock_nats.request = AsyncMock(return_value=mock_response)
        
        response = await event_bus.request(
            "rosey.test.request",
            {"action": "test"}
        )
        
        assert response["result"] == "success"
        mock_nats.request.assert_called_once()


@pytest.mark.asyncio
async def test_global_event_bus():
    """Test global event bus singleton"""
    from bot.rosey.core.event_bus import (
        initialize_event_bus,
        get_event_bus,
        shutdown_event_bus
    )
    
    with patch('nats.connect', return_value=AsyncMock()):
        # Initialize
        bus1 = await initialize_event_bus()
        
        # Get same instance
        bus2 = await get_event_bus()
        
        assert bus1 is bus2
        
        # Cleanup
        await shutdown_event_bus()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

### Task 8.2: Unit Tests - Subjects

**File:** `tests/unit/test_subjects.py`

```python
"""
Unit tests for subject hierarchy
"""
import pytest

from bot.rosey.core.subjects import (
    Subjects,
    SubjectBuilder,
    validate,
    parse,
    build_platform_subject,
    build_command_subject,
    build_plugin_subject
)


class TestSubjects:
    """Test Subjects constants"""
    
    def test_base_subject(self):
        """Test base subject constant"""
        assert Subjects.BASE == "rosey"
    
    def test_platform_subject(self):
        """Test platform subject pattern"""
        assert Subjects.PLATFORM == "rosey.platform"
    
    def test_events_subject(self):
        """Test events subject pattern"""
        assert Subjects.EVENTS == "rosey.events"
    
    def test_commands_subject(self):
        """Test commands subject pattern"""
        assert Subjects.COMMANDS == "rosey.commands"
    
    def test_plugins_subject(self):
        """Test plugins subject pattern"""
        assert Subjects.PLUGINS == "rosey.plugins"


class TestSubjectBuilder:
    """Test SubjectBuilder class"""
    
    def test_build_platform_subject(self):
        """Test building platform subject"""
        subject = (SubjectBuilder()
                   .platform("cytube")
                   .event("message")
                   .build())
        
        assert subject == "rosey.platform.cytube.message"
    
    def test_build_command_subject(self):
        """Test building command subject"""
        subject = (SubjectBuilder()
                   .command("trivia", "answer")
                   .build())
        
        assert subject == "rosey.commands.trivia.answer"
    
    def test_build_plugin_subject(self):
        """Test building plugin subject"""
        subject = (SubjectBuilder()
                   .plugin("markov")
                   .event("ready")
                   .build())
        
        assert subject == "rosey.plugins.markov.ready"
    
    def test_builder_chaining(self):
        """Test method chaining"""
        builder = SubjectBuilder()
        result = builder.platform("discord").event("user.join")
        
        assert result is builder  # Should return self
        assert builder.build() == "rosey.platform.discord.user.join"


class TestSubjectHelpers:
    """Test helper functions"""
    
    def test_build_platform_subject_helper(self):
        """Test build_platform_subject helper"""
        subject = build_platform_subject("slack", "message")
        assert subject == "rosey.platform.slack.message"
    
    def test_build_command_subject_helper(self):
        """Test build_command_subject helper"""
        subject = build_command_subject("calendar", "create")
        assert subject == "rosey.commands.calendar.create"
    
    def test_build_plugin_subject_helper(self):
        """Test build_plugin_subject helper"""
        subject = build_plugin_subject("echo", "error")
        assert subject == "rosey.plugins.echo.error"


class TestSubjectValidation:
    """Test subject validation"""
    
    def test_validate_valid_subject(self):
        """Test validating valid subject"""
        assert validate("rosey.platform.cytube.message")
        assert validate("rosey.events.message")
        assert validate("rosey.commands.trivia.answer")
    
    def test_validate_wildcard_subject(self):
        """Test validating wildcard subject"""
        assert validate("rosey.platform.*")
        assert validate("rosey.events.>")
        assert validate("rosey.commands.*.execute")
    
    def test_validate_invalid_subject(self):
        """Test validating invalid subject"""
        assert not validate("invalid")
        assert not validate("rosey")
        assert not validate("rosey..invalid")
        assert not validate(".rosey.platform")


class TestSubjectParsing:
    """Test subject parsing"""
    
    def test_parse_platform_subject(self):
        """Test parsing platform subject"""
        parts = parse("rosey.platform.cytube.message")
        
        assert parts["category"] == "platform"
        assert parts["platform"] == "cytube"
        assert parts["event"] == "message"
    
    def test_parse_command_subject(self):
        """Test parsing command subject"""
        parts = parse("rosey.commands.trivia.answer")
        
        assert parts["category"] == "commands"
        assert parts["plugin"] == "trivia"
        assert parts["action"] == "answer"
    
    def test_parse_plugin_subject(self):
        """Test parsing plugin subject"""
        parts = parse("rosey.plugins.markov.ready")
        
        assert parts["category"] == "plugins"
        assert parts["plugin"] == "markov"
        assert parts["event"] == "ready"
    
    def test_parse_invalid_subject(self):
        """Test parsing invalid subject"""
        parts = parse("invalid.subject")
        
        assert parts == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

### Task 8.3: Unit Tests - Plugin Manager

**File:** `tests/unit/test_plugin_manager.py`

```python
"""
Unit tests for Plugin Manager
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from bot.rosey.plugins.plugin_manager import (
    PluginManager,
    PluginInfo,
    PluginState,
    RestartPolicy
)
from bot.rosey.plugins.plugin_manifest import PluginManifest


@pytest.fixture
def mock_event_bus():
    """Mock event bus"""
    bus = Mock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    bus.servers = ["nats://localhost:4222"]
    return bus


@pytest.fixture
def sample_manifest():
    """Sample plugin manifest"""
    return PluginManifest(
        name="test_plugin",
        version="1.0.0",
        description="Test plugin"
    )


@pytest.fixture
def plugin_info(sample_manifest):
    """Sample plugin info"""
    return PluginInfo(
        name="test_plugin",
        manifest=sample_manifest,
        plugin_path="/path/to/plugin.py"
    )


class TestPluginInfo:
    """Test PluginInfo dataclass"""
    
    def test_plugin_info_creation(self, plugin_info):
        """Test creating plugin info"""
        assert plugin_info.name == "test_plugin"
        assert plugin_info.state == PluginState.STOPPED
        assert plugin_info.crash_count == 0
        assert plugin_info.enabled is True
    
    def test_is_running(self, plugin_info):
        """Test is_running method"""
        assert not plugin_info.is_running()
        
        plugin_info.state = PluginState.RUNNING
        assert plugin_info.is_running()
        
        plugin_info.state = PluginState.UNHEALTHY
        assert plugin_info.is_running()
        
        plugin_info.state = PluginState.CRASHED
        assert not plugin_info.is_running()
    
    def test_uptime_seconds(self, plugin_info):
        """Test uptime calculation"""
        assert plugin_info.uptime_seconds() == 0.0
        
        plugin_info.start_time = datetime.now()
        uptime = plugin_info.uptime_seconds()
        assert uptime >= 0.0
        assert uptime < 1.0  # Should be very small
    
    def test_error_rate(self, plugin_info):
        """Test error rate calculation"""
        assert plugin_info.error_rate() == 0.0
        
        plugin_info.command_success_count = 7
        plugin_info.command_error_count = 3
        
        assert plugin_info.error_rate() == 0.3  # 30% errors


class TestPluginManager:
    """Test PluginManager class"""
    
    @pytest.fixture
    async def plugin_manager(self, mock_event_bus):
        """Create plugin manager for testing"""
        manager = PluginManager(
            plugins_dir="tests/fixtures/plugins",
            event_bus=mock_event_bus
        )
        
        # Add test plugins manually
        manager.plugins["plugin_a"] = PluginInfo(
            name="plugin_a",
            manifest=PluginManifest(
                name="plugin_a",
                version="1.0.0",
                description="Test A"
            ),
            plugin_path="plugin_a.py"
        )
        
        manager.plugins["plugin_b"] = PluginInfo(
            name="plugin_b",
            manifest=PluginManifest(
                name="plugin_b",
                version="1.0.0",
                description="Test B"
            ),
            plugin_path="plugin_b.py",
            dependencies=["plugin_a"]
        )
        
        return manager
    
    def test_dependency_validation(self, plugin_manager):
        """Test dependency graph building"""
        plugin_manager._validate_dependencies()
        
        # plugin_b depends on plugin_a
        assert "plugin_a" in plugin_manager.plugins["plugin_b"].dependencies
        
        # plugin_a should have plugin_b as dependent
        assert "plugin_b" in plugin_manager.plugins["plugin_a"].dependents
    
    def test_startup_order(self, plugin_manager):
        """Test startup order calculation"""
        plugin_manager._validate_dependencies()
        order = plugin_manager._get_startup_order()
        
        # plugin_a should start before plugin_b
        idx_a = order.index("plugin_a")
        idx_b = order.index("plugin_b")
        
        assert idx_a < idx_b
    
    def test_circular_dependency_detection(self, plugin_manager):
        """Test circular dependency detection"""
        # Create circular dependency
        plugin_manager.plugins["plugin_a"].dependencies = ["plugin_b"]
        plugin_manager.plugins["plugin_b"].dependencies = ["plugin_a"]
        
        # Should detect circle
        has_circle = plugin_manager._has_circular_dependency("plugin_a", set())
        assert has_circle
    
    @pytest.mark.asyncio
    async def test_enable_disable_plugin(self, plugin_manager):
        """Test enabling/disabling plugins"""
        plugin_manager.disable_plugin("plugin_a")
        assert not plugin_manager.plugins["plugin_a"].enabled
        
        plugin_manager.enable_plugin("plugin_a")
        assert plugin_manager.plugins["plugin_a"].enabled
        assert plugin_manager.plugins["plugin_a"].crash_count == 0
    
    @pytest.mark.asyncio
    async def test_get_plugin_status(self, plugin_manager):
        """Test getting plugin status"""
        status = plugin_manager.get_plugin_status("plugin_a")
        
        assert status is not None
        assert status["name"] == "plugin_a"
        assert status["state"] == "stopped"
        assert status["enabled"] is True
        assert "uptime_seconds" in status
        assert "crash_count" in status
    
    @pytest.mark.asyncio
    async def test_get_all_status(self, plugin_manager):
        """Test getting all plugin statuses"""
        all_status = plugin_manager.get_all_status()
        
        assert len(all_status) == 2
        assert "plugin_a" in all_status
        assert "plugin_b" in all_status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

### Task 8.4: Integration Tests - Command Flow

**File:** `tests/integration/test_command_flow.py`

```python
"""
Integration tests for command flow
Tests: User Command → Router → Plugin → Response
"""
import pytest
import asyncio
from pathlib import Path

from bot.rosey.core.event_bus import EventBus, Event
from bot.rosey.core.router import CoreRouter, CommandParser
from bot.rosey.core.subjects import build_command_subject
from bot.rosey.plugins.plugin_manager import PluginManager


@pytest.fixture
async def nats_server():
    """
    Start NATS server for integration testing
    
    Requires: NATS server installed
    """
    import subprocess
    
    # Start NATS server
    process = subprocess.Popen(
        ["nats-server", "-p", "14222"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    await asyncio.sleep(1)  # Wait for startup
    
    yield "nats://localhost:14222"
    
    # Cleanup
    process.terminate()
    process.wait()


@pytest.fixture
async def event_bus(nats_server):
    """Create real EventBus"""
    bus = EventBus(servers=[nats_server])
    await bus.connect()
    
    yield bus
    
    await bus.disconnect()


@pytest.fixture
async def router(event_bus):
    """Create CoreRouter"""
    router = CoreRouter(event_bus=event_bus)
    await router.initialize()
    
    yield router
    
    await router.shutdown()


@pytest.mark.asyncio
@pytest.mark.integration
class TestCommandFlow:
    """Integration tests for command flow"""
    
    async def test_command_parsing(self, router):
        """Test command parsing"""
        parser = CommandParser()
        
        # Simple command
        cmd = parser.parse("!ping", "user", "channel", "cytube")
        assert cmd.name == "ping"
        assert cmd.action is None
        
        # Command with action
        cmd = parser.parse("!trivia answer 42", "user", "channel", "cytube")
        assert cmd.name == "trivia"
        assert cmd.action == "answer"
        assert cmd.args == ["42"]
        
        # Command with flags
        cmd = parser.parse("!trivia start --rounds=5", "user", "channel", "cytube")
        assert cmd.name == "trivia"
        assert cmd.action == "start"
        assert cmd.kwargs["rounds"] == "5"
    
    async def test_event_to_command_flow(self, router, event_bus):
        """Test full event → command flow"""
        # Create message event
        event = Event(
            subject="rosey.events.message",
            event_type="message",
            source="cytube",
            data={
                "user": "test_user",
                "channel": "test_channel",
                "message": "!echo test message",
                "platform": "cytube"
            }
        )
        
        # Publish event
        await event_bus.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Command should be routed to echo plugin
        # (In full test, would verify command was published to rosey.commands.echo.execute)
    
    async def test_plugin_response_routing(self, router, event_bus):
        """Test plugin response routing back to platform"""
        # Mock plugin result
        correlation_id = "test-123"
        
        result_event = Event(
            subject="rosey.commands.echo.result",
            event_type="command.result",
            source="echo",
            data={
                "message": "Echo: test message",
                "success": True
            },
            correlation_id=correlation_id
        )
        
        # Track responses
        responses = []
        
        async def capture_response(event):
            responses.append(event)
        
        # Subscribe to platform responses
        await event_bus.subscribe("rosey.platform.cytube.send", capture_response)
        
        # Publish result
        await event_bus.publish(result_event)
        
        # Wait for routing
        await asyncio.sleep(0.5)
        
        # Should route to platform
        # (Full test would verify response sent to cytube connector)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multi_plugin_interaction(nats_server):
    """
    Test multiple plugins interacting
    Plugin A → Plugin B → Response
    """
    # Setup
    event_bus = EventBus(servers=[nats_server])
    await event_bus.connect()
    
    plugin_manager = PluginManager(
        plugins_dir="tests/fixtures/plugins",
        event_bus=event_bus
    )
    await plugin_manager.initialize()
    
    # Start plugins
    await plugin_manager.start_all()
    
    # Send command to plugin A
    event = Event(
        subject="rosey.commands.plugin_a.test",
        event_type="command",
        source="test",
        data={"action": "test"}
    )
    
    await event_bus.publish(event)
    
    # Wait for processing
    await asyncio.sleep(1.0)
    
    # Verify plugin B received event from plugin A
    # (Would need to check plugin B state or responses)
    
    # Cleanup
    await plugin_manager.stop_all()
    await event_bus.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
```

---

### Task 8.5: Performance Tests

**File:** `tests/performance/test_latency.py`

```python
"""
Performance tests for message latency
"""
import pytest
import asyncio
import time
import statistics
from typing import List

from bot.rosey.core.event_bus import EventBus, Event


@pytest.fixture
async def event_bus():
    """Create EventBus for performance testing"""
    bus = EventBus(servers=["nats://localhost:4222"])
    await bus.connect()
    
    yield bus
    
    await bus.disconnect()


@pytest.mark.asyncio
@pytest.mark.performance
class TestLatency:
    """Test message latency"""
    
    async def test_publish_latency(self, event_bus):
        """Test publish latency (one-way)"""
        latencies: List[float] = []
        
        for i in range(1000):
            event = Event(
                subject="rosey.test.latency",
                event_type="test",
                source="test",
                data={"index": i}
            )
            
            start = time.perf_counter()
            await event_bus.publish(event)
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)  # Convert to ms
        
        # Calculate statistics
        avg = statistics.mean(latencies)
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        print(f"\n=== Publish Latency ===")
        print(f"Average: {avg:.2f}ms")
        print(f"p50: {p50:.2f}ms")
        print(f"p95: {p95:.2f}ms")
        print(f"p99: {p99:.2f}ms")
        
        # Assert p99 < 10ms (goal from PRD)
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms target"
    
    async def test_request_reply_latency(self, event_bus):
        """Test request/reply latency (round-trip)"""
        # Setup responder
        async def responder(msg):
            # Echo response
            await event_bus.reply(msg, {"status": "ok"})
        
        await event_bus.subscribe("rosey.test.request", responder)
        
        # Give responder time to subscribe
        await asyncio.sleep(0.1)
        
        latencies: List[float] = []
        
        for i in range(100):
            start = time.perf_counter()
            
            response = await event_bus.request(
                "rosey.test.request",
                {"index": i},
                timeout=1.0
            )
            
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)
        
        # Calculate statistics
        avg = statistics.mean(latencies)
        p99 = statistics.quantiles(latencies, n=100)[98]
        
        print(f"\n=== Request/Reply Latency ===")
        print(f"Average: {avg:.2f}ms")
        print(f"p99: {p99:.2f}ms")
        
        # Request/reply is round-trip, so allow 2x publish latency
        assert p99 < 20.0, f"p99 latency {p99:.2f}ms exceeds 20ms target"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_throughput(event_bus):
    """Test message throughput"""
    message_count = 10000
    
    # Counter
    received = {"count": 0}
    
    async def counter(event):
        received["count"] += 1
    
    await event_bus.subscribe("rosey.test.throughput", counter)
    
    # Send messages
    start = time.perf_counter()
    
    for i in range(message_count):
        event = Event(
            subject="rosey.test.throughput",
            event_type="test",
            source="test",
            data={"index": i}
        )
        await event_bus.publish(event)
    
    # Wait for all messages to be received
    timeout = 10.0
    elapsed = 0.0
    while received["count"] < message_count and elapsed < timeout:
        await asyncio.sleep(0.1)
        elapsed += 0.1
    
    end = time.perf_counter()
    
    duration = end - start
    throughput = message_count / duration
    
    print(f"\n=== Throughput ===")
    print(f"Messages: {message_count}")
    print(f"Duration: {duration:.2f}s")
    print(f"Throughput: {throughput:.0f} msg/sec")
    print(f"Received: {received['count']}/{message_count}")
    
    # Assert throughput > 1000 msg/sec (goal from PRD)
    assert throughput > 1000, f"Throughput {throughput:.0f} msg/sec below 1000 target"
    assert received["count"] == message_count, "Not all messages received"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance", "-s"])
```

---

### Task 8.6: End-to-End Tests

**File:** `tests/e2e/test_user_command.py`

```python
"""
End-to-end tests for complete user workflows
"""
import pytest
import asyncio

from bot.rosey.core.event_bus import EventBus, Event, initialize_event_bus
from bot.rosey.core.router import CoreRouter
from bot.rosey.plugins.plugin_manager import PluginManager, initialize_plugin_manager


@pytest.fixture
async def full_stack():
    """
    Setup complete Rosey stack for E2E testing
    """
    # Initialize EventBus
    event_bus = await initialize_event_bus(servers=["nats://localhost:4222"])
    
    # Initialize Router
    router = CoreRouter(event_bus=event_bus)
    await router.initialize()
    
    # Initialize PluginManager
    plugin_manager = await initialize_plugin_manager(
        plugins_dir="tests/fixtures/plugins",
        event_bus=event_bus
    )
    
    # Start all plugins
    await plugin_manager.start_all()
    
    yield {
        "event_bus": event_bus,
        "router": router,
        "plugin_manager": plugin_manager
    }
    
    # Cleanup
    await plugin_manager.stop_all()
    await router.shutdown()
    await event_bus.disconnect()


@pytest.mark.asyncio
@pytest.mark.e2e
class TestUserCommands:
    """End-to-end tests for user commands"""
    
    async def test_echo_command(self, full_stack):
        """
        Test: User sends !echo message
        Flow: Message → Router → Echo Plugin → Response
        """
        event_bus = full_stack["event_bus"]
        
        # Track responses
        responses = []
        
        async def capture_response(event):
            responses.append(event.data)
        
        # Subscribe to platform responses
        await event_bus.subscribe("rosey.platform.cytube.send", capture_response)
        
        # Simulate user message
        user_message = Event(
            subject="rosey.events.message",
            event_type="message",
            source="cytube",
            data={
                "user": "test_user",
                "channel": "test_channel",
                "message": "!echo Hello, World!",
                "platform": "cytube"
            }
        )
        
        await event_bus.publish(user_message)
        
        # Wait for response
        await asyncio.sleep(1.0)
        
        # Verify response
        assert len(responses) > 0
        response = responses[0]
        assert "Hello, World!" in response["message"]
    
    async def test_plugin_not_found(self, full_stack):
        """
        Test: User sends command to non-existent plugin
        """
        event_bus = full_stack["event_bus"]
        
        responses = []
        
        async def capture_response(event):
            responses.append(event.data)
        
        await event_bus.subscribe("rosey.platform.cytube.send", capture_response)
        
        # Command to non-existent plugin
        user_message = Event(
            subject="rosey.events.message",
            event_type="message",
            source="cytube",
            data={
                "user": "test_user",
                "channel": "test_channel",
                "message": "!nonexistent test",
                "platform": "cytube"
            }
        )
        
        await event_bus.publish(user_message)
        
        await asyncio.sleep(1.0)
        
        # Should get error response
        assert len(responses) > 0
        response = responses[0]
        assert "not found" in response["message"].lower() or "unknown" in response["message"].lower()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_plugin_crash_recovery(full_stack):
    """
    Test: Plugin crashes, manager restarts it
    """
    plugin_manager = full_stack["plugin_manager"]
    event_bus = full_stack["event_bus"]
    
    # Get initial status
    status_before = plugin_manager.get_plugin_status("echo")
    assert status_before["state"] == "running"
    
    # Simulate crash (send crash command to plugin)
    crash_event = Event(
        subject="rosey.commands.echo.crash",
        event_type="command",
        source="test",
        data={"action": "crash"}
    )
    
    await event_bus.publish(crash_event)
    
    # Wait for crash detection and recovery
    await asyncio.sleep(5.0)
    
    # Check if plugin was restarted
    status_after = plugin_manager.get_plugin_status("echo")
    
    # Should be running again (or starting)
    assert status_after["state"] in ["running", "starting"]
    assert status_after["crash_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_multi_platform_command(full_stack):
    """
    Test: Same command works from different platforms
    """
    event_bus = full_stack["event_bus"]
    
    platforms = ["cytube", "discord", "slack"]
    
    for platform in platforms:
        responses = []
        
        async def capture_response(event):
            responses.append(event.data)
        
        # Subscribe to platform-specific responses
        await event_bus.subscribe(
            f"rosey.platform.{platform}.send",
            capture_response
        )
        
        # Send command from this platform
        user_message = Event(
            subject=f"rosey.platform.{platform}.message",
            event_type="message",
            source=platform,
            data={
                "user": "test_user",
                "channel": "test_channel",
                "message": "!echo test",
                "platform": platform
            }
        )
        
        await event_bus.publish(user_message)
        
        await asyncio.sleep(1.0)
        
        # Verify response to correct platform
        assert len(responses) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])
```

---

### Task 8.7: Test Fixtures & Configuration

**File:** `tests/fixtures/conftest.py`

```python
"""
Pytest configuration and shared fixtures
"""
import pytest
import asyncio
import os
from pathlib import Path


def pytest_configure(config):
    """Configure pytest"""
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (require NATS)"
    )
    config.addinivalue_line(
        "markers", "performance: Performance tests (slow)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (full stack)"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_data_dir():
    """Test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture
def mock_config():
    """Mock configuration"""
    return {
        "nats_url": "nats://localhost:4222",
        "plugins_dir": "tests/fixtures/plugins",
        "command_prefix": "!",
        "health_check_interval": 30,
        "max_crash_count": 3
    }
```

**File:** `tests/fixtures/mock_plugins.py`

```python
"""
Mock plugins for testing
"""
import asyncio
from bot.rosey.plugins.plugin_interface import PluginInterface
from bot.rosey.plugins.plugin_manifest import PluginManifest, SubjectPermission


class MockEchoPlugin(PluginInterface):
    """Mock echo plugin for testing"""
    
    @property
    def plugin_name(self) -> str:
        return "echo"
    
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="echo",
            version="1.0.0",
            description="Test echo plugin",
            subject_permissions=[
                SubjectPermission("rosey.commands.echo.>", allow_subscribe=True),
                SubjectPermission("rosey.commands.echo.>", allow_publish=True),
            ]
        )
    
    async def on_start(self):
        """Subscribe to commands"""
        await self.subscribe_to_events(['command'])
    
    async def handle_command(self, event):
        """Echo back message"""
        message = event.data.get('message', '')
        
        await self.publish_result({
            "message": f"Echo: {message}"
        }, event.correlation_id)


class MockCrashPlugin(PluginInterface):
    """Mock plugin that can crash on command"""
    
    @property
    def plugin_name(self) -> str:
        return "crash"
    
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="crash",
            version="1.0.0",
            description="Test crash plugin"
        )
    
    async def handle_command(self, event):
        """Crash if commanded"""
        if event.data.get('action') == 'crash':
            raise RuntimeError("Intentional crash for testing")
        
        await self.publish_result({"status": "ok"}, event.correlation_id)
```

---

### Task 8.8: Test Runner Scripts

**File:** `scripts/run_tests.sh`

```bash
#!/bin/bash
# Run test suite

set -e

echo "=== Running Quicksilver Test Suite ==="

# Unit tests (fast, no dependencies)
echo -e "\n[1/4] Unit Tests..."
pytest tests/unit -v -m unit --cov=bot/rosey --cov-report=term-missing

# Integration tests (require NATS)
echo -e "\n[2/4] Integration Tests..."
pytest tests/integration -v -m integration

# Performance tests (slow)
echo -e "\n[3/4] Performance Tests..."
pytest tests/performance -v -m performance -s

# E2E tests (full stack)
echo -e "\n[4/4] End-to-End Tests..."
pytest tests/e2e -v -m e2e -s

echo -e "\n=== All Tests Passed! ==="
```

**File:** `scripts/run_tests.bat`

```batch
@echo off
REM Run test suite (Windows)

echo === Running Quicksilver Test Suite ===

REM Unit tests
echo.
echo [1/4] Unit Tests...
pytest tests\unit -v -m unit --cov=bot\rosey --cov-report=term-missing
if errorlevel 1 exit /b 1

REM Integration tests
echo.
echo [2/4] Integration Tests...
pytest tests\integration -v -m integration
if errorlevel 1 exit /b 1

REM Performance tests
echo.
echo [3/4] Performance Tests...
pytest tests\performance -v -m performance -s
if errorlevel 1 exit /b 1

REM E2E tests
echo.
echo [4/4] End-to-End Tests...
pytest tests\e2e -v -m e2e -s
if errorlevel 1 exit /b 1

echo.
echo === All Tests Passed! ===
```

---

### Task 8.9: CI/CD Integration

**File:** `.github/workflows/quicksilver-tests.yml`

```yaml
name: Quicksilver Tests

on:
  push:
    branches: [ main, develop, sprint/* ]
  pull_request:
    branches: [ main, develop ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run unit tests
      run: |
        pytest tests/unit -v -m unit --cov=bot/rosey --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
          - 8222:8222
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Wait for NATS
      run: |
        sleep 2
        curl -f http://localhost:8222/varz || exit 1
    
    - name: Run integration tests
      run: |
        pytest tests/integration -v -m integration

  performance-tests:
    runs-on: ubuntu-latest
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run performance tests
      run: |
        pytest tests/performance -v -m performance -s
      
    - name: Comment PR with results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          // Post performance results to PR
          // (Would parse pytest output and format nicely)
```

---

## Test Coverage Report

**Expected Coverage:**

```
Component                    Coverage
─────────────────────────────────────
event_bus.py                 85%
subjects.py                  92%
router.py                    80%
plugin_interface.py          78%
plugin_runner.py             75%
plugin_manager.py            82%
plugin_manifest.py           90%
permissions.py               88%
─────────────────────────────────────
Overall                      82%
```

---

## Running Tests

### All Tests

```bash
# Linux/Mac
./scripts/run_tests.sh

# Windows
scripts\run_tests.bat
```

### By Category

```bash
# Unit tests only (fast)
pytest tests/unit -v -m unit

# Integration tests (require NATS)
pytest tests/integration -v -m integration

# Performance tests
pytest tests/performance -v -m performance -s

# E2E tests
pytest tests/e2e -v -m e2e -s
```

### Specific Test

```bash
pytest tests/unit/test_event_bus.py::TestEventBus::test_publish -v
```

### With Coverage

```bash
pytest tests/unit -v --cov=bot/rosey --cov-report=html
# Open htmlcov/index.html
```

---

## Documentation

**File:** `docs/testing/TESTING-GUIDE.md`

```markdown
# Testing Guide

## Overview

Quicksilver has comprehensive test coverage:
- **Unit Tests**: Individual component testing (fast, isolated)
- **Integration Tests**: Component interaction testing (require NATS)
- **Performance Tests**: Latency and throughput validation
- **E2E Tests**: Complete workflow validation

## Running Tests

### Quick Start

```bash
# All tests
./scripts/run_tests.sh

# Fast unit tests only
pytest tests/unit -v -m unit
```

### Prerequisites

**For Integration/E2E Tests:**
- NATS server running on localhost:4222
- Or Docker: `docker run -p 4222:4222 -p 8222:8222 nats:2.10-alpine`

**For Performance Tests:**
- Dedicated NATS server (not shared with other processes)
- Stable network connection

## Test Organization

```
tests/
├── unit/           # Fast, isolated, no dependencies
├── integration/    # Component interaction, requires NATS
├── performance/    # Latency/throughput benchmarks
└── e2e/            # Full stack workflows
```

## Writing Tests

### Unit Test Template

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_my_feature():
    """Test description"""
    # Arrange
    mock_dependency = AsyncMock()
    
    # Act
    result = await my_function(mock_dependency)
    
    # Assert
    assert result == expected_value
```

### Integration Test Template

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_component_interaction():
    """Test description"""
    # Setup real NATS connection
    event_bus = EventBus(servers=["nats://localhost:4222"])
    await event_bus.connect()
    
    try:
        # Test interaction
        pass
    finally:
        await event_bus.disconnect()
```

## Coverage Goals

- Unit tests: 80%+ coverage
- Integration tests: All boundaries tested
- Performance tests: Meet PRD goals (p99 < 10ms, > 1000 msg/sec)
- E2E tests: All critical user paths

## CI/CD

Tests run automatically on:
- Push to main/develop
- Pull requests
- Sprint branches

GitHub Actions workflow: `.github/workflows/quicksilver-tests.yml`

## Troubleshooting

**Tests hang:**
- Check NATS server is running
- Check no other process using port 4222
- Increase timeouts in conftest.py

**Performance tests fail:**
- Close other applications
- Check system resources
- Run on dedicated machine/VM
- Verify NATS server performance mode

**Import errors:**
- Run from project root
- Check PYTHONPATH includes project root
- Activate virtual environment
```

---

## Success Criteria

✅ Unit tests covering all components (80%+ coverage)  
✅ Integration tests for component boundaries  
✅ Performance tests validating PRD goals  
✅ E2E tests for critical workflows  
✅ Test fixtures and mocks  
✅ CI/CD integration (GitHub Actions)  
✅ Test runner scripts (Linux/Windows)  
✅ Comprehensive testing documentation  

---

## Time Breakdown

- Unit tests (EventBus, Subjects, Manager): 2 hours
- Integration tests (Command flow, Multi-plugin): 1.5 hours
- Performance tests (Latency, Throughput): 1 hour
- E2E tests (User commands, Recovery): 1.5 hours
- Test fixtures and configuration: 45 minutes
- CI/CD integration: 45 minutes
- Documentation: 30 minutes

**Total: 8 hours**

---

## Validation Results (Expected)

Once tests are implemented and run:

```
=== Test Results ===

Unit Tests:        120/120 passed (100%)
Integration Tests:  30/30 passed (100%)
Performance Tests:   5/5 passed (100%)
E2E Tests:           5/5 passed (100%)

Coverage:          82%

Performance:
  Publish p99:     7.3ms  ✓ (< 10ms)
  Request p99:    14.8ms  ✓ (< 20ms)
  Throughput:    2847/s   ✓ (> 1000/s)

=== All Tests Passed ===
```

---

## Next Steps After Testing

With comprehensive testing in place:

1. **Sortie 1-8 Implementation**: Start implementing the architecture
2. **Continuous Testing**: Run tests after each sortie
3. **Regression Prevention**: Tests prevent breaking changes
4. **Performance Monitoring**: Track performance over time
5. **Coverage Improvement**: Fill gaps as discovered

---

## Production Considerations

**Current Test Suite: Development-Ready**
- ✅ Comprehensive unit coverage
- ✅ Integration tests for boundaries
- ✅ Performance validation
- ✅ E2E workflow testing
- ✅ CI/CD automation

**Future Enhancements:**
- Load testing (100+ concurrent users)
- Stress testing (resource exhaustion)
- Chaos engineering (random failures)
- Security testing (penetration, fuzzing)
- Mutation testing (test quality validation)
- Property-based testing (Hypothesis)
- Visual regression testing (UI/dashboard)
- Production monitoring integration
