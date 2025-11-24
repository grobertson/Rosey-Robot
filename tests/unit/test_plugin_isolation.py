"""
Unit tests for plugin process isolation system.

Tests cover:
- ResourceMonitor: CPU/memory tracking, limit checking, history
- PluginIPC: EventBus wrapper for plugin communication
- PluginProcess: Lifecycle management, crash recovery, restart policies
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
import pytest

from bot.rosey.core.plugin_isolation import (
    RestartPolicy,
    RestartConfig,
    ResourceUsage,
    ResourceLimits,
    ResourceMonitor,
    PluginIPC,
    PluginState,
    PluginProcess
)
from bot.rosey.core.event_bus import EventBus, Priority
from bot.rosey.core.subjects import EventTypes


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing"""
    bus = AsyncMock(spec=EventBus)
    bus.is_connected.return_value = True
    bus.subscribe.return_value = 12345  # Mock subscription ID
    return bus


@pytest.fixture
def mock_psutil_process():
    """Mock psutil.Process for testing"""
    proc = Mock()
    proc.cpu_percent.return_value = 25.5
    proc.memory_info.return_value = Mock(rss=100 * 1024 * 1024)  # 100 MB
    proc.memory_percent.return_value = 5.0
    proc.num_threads.return_value = 4
    proc.num_fds.return_value = 10
    proc.io_counters.return_value = Mock(
        read_bytes=50 * 1024 * 1024,  # 50 MB
        write_bytes=25 * 1024 * 1024  # 25 MB
    )
    return proc


# ============================================================================
# RestartConfig Tests
# ============================================================================

@pytest.mark.asyncio
class TestRestartConfig:
    """Test restart configuration"""

    def test_restart_config_defaults(self):
        """Test default restart configuration"""
        config = RestartConfig()

        assert config.policy == RestartPolicy.ON_FAILURE
        assert config.max_retries == 3
        assert config.backoff_seconds == 1.0
        assert config.backoff_multiplier == 2.0
        assert config.max_backoff_seconds == 60.0
        assert config.reset_after_seconds == 300.0

    def test_restart_config_custom(self):
        """Test custom restart configuration"""
        config = RestartConfig(
            policy=RestartPolicy.ALWAYS,
            max_retries=5,
            backoff_seconds=2.0,
            max_backoff_seconds=120.0
        )

        assert config.policy == RestartPolicy.ALWAYS
        assert config.max_retries == 5
        assert config.backoff_seconds == 2.0
        assert config.max_backoff_seconds == 120.0

    def test_restart_policies(self):
        """Test all restart policy values"""
        assert RestartPolicy.NEVER.value == "never"
        assert RestartPolicy.ON_FAILURE.value == "on-failure"
        assert RestartPolicy.ALWAYS.value == "always"
        assert RestartPolicy.UNLESS_STOPPED.value == "unless-stopped"


# ============================================================================
# ResourceUsage Tests
# ============================================================================

@pytest.mark.asyncio
class TestResourceUsage:
    """Test resource usage tracking"""

    def test_resource_usage_creation(self):
        """Test creating resource usage snapshot"""
        usage = ResourceUsage(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_mb=200.0,
            memory_percent=10.0,
            num_threads=8,
            num_fds=20,
            io_read_mb=100.0,
            io_write_mb=50.0
        )

        assert usage.cpu_percent == 50.0
        assert usage.memory_mb == 200.0
        assert usage.memory_percent == 10.0
        assert usage.num_threads == 8
        assert usage.num_fds == 20
        assert usage.io_read_mb == 100.0
        assert usage.io_write_mb == 50.0


# ============================================================================
# ResourceLimits Tests
# ============================================================================

@pytest.mark.asyncio
class TestResourceLimits:
    """Test resource limits"""

    def test_resource_limits_defaults(self):
        """Test default resource limits (all None)"""
        limits = ResourceLimits()

        assert limits.max_cpu_percent is None
        assert limits.max_memory_mb is None
        assert limits.max_threads is None
        assert limits.max_fds is None

    def test_resource_limits_custom(self):
        """Test custom resource limits"""
        limits = ResourceLimits(
            max_cpu_percent=80.0,
            max_memory_mb=512.0,
            max_threads=16,
            max_fds=100
        )

        assert limits.max_cpu_percent == 80.0
        assert limits.max_memory_mb == 512.0
        assert limits.max_threads == 16
        assert limits.max_fds == 100


# ============================================================================
# ResourceMonitor Tests
# ============================================================================

@pytest.mark.asyncio
class TestResourceMonitor:
    """Test resource monitoring"""

    async def test_monitor_creation_with_psutil(self, mock_psutil_process):
        """Test creating monitor with psutil available"""
        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345)

            assert monitor.pid == 12345
            assert monitor.sample_interval == 1.0
            assert monitor._process is not None
            mock_psutil.Process.assert_called_once_with(12345)

    async def test_monitor_creation_without_psutil(self):
        """Test creating monitor without psutil"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            monitor = ResourceMonitor(pid=12345)

            assert monitor.pid == 12345
            assert monitor._process is None

    async def test_monitor_with_limits(self, mock_psutil_process):
        """Test monitor with resource limits"""
        limits = ResourceLimits(max_cpu_percent=50.0, max_memory_mb=256.0)

        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345, limits=limits)

            assert monitor.limits.max_cpu_percent == 50.0
            assert monitor.limits.max_memory_mb == 256.0

    async def test_get_current_usage(self, mock_psutil_process):
        """Test getting current resource usage"""
        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345)
            usage = await monitor.get_current_usage()

            assert usage is not None
            assert usage.cpu_percent == 25.5
            assert usage.memory_mb == 100.0
            assert usage.memory_percent == 5.0
            assert usage.num_threads == 4

    async def test_get_current_usage_no_psutil(self):
        """Test getting usage without psutil returns None"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            monitor = ResourceMonitor(pid=12345)
            usage = await monitor.get_current_usage()

            assert usage is None

    async def test_check_limits_no_violations(self, mock_psutil_process):
        """Test checking limits with no violations"""
        limits = ResourceLimits(
            max_cpu_percent=100.0,
            max_memory_mb=500.0,
            max_threads=20
        )

        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345, limits=limits)
            usage = await monitor.get_current_usage()
            violations = monitor.check_limits(usage)

            assert len(violations) == 0

    async def test_check_limits_with_violations(self, mock_psutil_process):
        """Test checking limits with violations"""
        limits = ResourceLimits(
            max_cpu_percent=20.0,  # Will exceed
            max_memory_mb=50.0,    # Will exceed
            max_threads=2          # Will exceed
        )

        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345, limits=limits)
            usage = await monitor.get_current_usage()
            violations = monitor.check_limits(usage)

            assert len(violations) == 3
            assert any("CPU" in v for v in violations)
            assert any("Memory" in v for v in violations)
            assert any("Threads" in v for v in violations)

    async def test_add_callback(self, mock_psutil_process):
        """Test adding resource update callback"""
        callback = Mock()

        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345)
            monitor.add_callback(callback)

            assert callback in monitor._callbacks

    async def test_start_stop_monitoring(self, mock_psutil_process):
        """Test starting and stopping monitoring"""
        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345, sample_interval=0.1)

            assert not monitor._monitoring

            await monitor.start_monitoring()
            assert monitor._monitoring
            assert monitor._monitor_task is not None

            # Let it run briefly
            await asyncio.sleep(0.3)

            await monitor.stop_monitoring()
            assert not monitor._monitoring

    async def test_get_history(self, mock_psutil_process):
        """Test getting resource history"""
        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345, sample_interval=0.1)

            # Add some history manually
            for i in range(5):
                usage = await monitor.get_current_usage()
                monitor._history.append(usage)
                await asyncio.sleep(0.05)

            # Get full history
            history = monitor.get_history()
            assert len(history) >= 5

            # Get recent history
            recent = monitor.get_history(duration_seconds=0.2)
            assert len(recent) <= len(history)

    async def test_get_average_usage(self, mock_psutil_process):
        """Test calculating average usage"""
        with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
            mock_psutil.Process.return_value = mock_psutil_process

            monitor = ResourceMonitor(pid=12345)

            # Add some history
            for i in range(3):
                usage = await monitor.get_current_usage()
                monitor._history.append(usage)

            # Get average
            avg = monitor.get_average_usage()

            assert avg is not None
            assert avg.cpu_percent == 25.5  # All samples same
            assert avg.memory_mb == 100.0


# ============================================================================
# PluginIPC Tests
# ============================================================================

@pytest.mark.asyncio
class TestPluginIPC:
    """Test plugin IPC wrapper"""

    async def test_plugin_ipc_creation(self, mock_event_bus):
        """Test creating plugin IPC"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        assert ipc.plugin_name == "test-plugin"
        assert ipc.event_bus is mock_event_bus
        assert len(ipc._command_subscriptions) == 0

    async def test_subscribe_commands(self, mock_event_bus):
        """Test subscribing to plugin commands"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        async def handler(event):
            pass

        await ipc.subscribe_commands(handler)

        mock_event_bus.subscribe.assert_called_once()
        call_args = mock_event_bus.subscribe.call_args
        assert call_args[0][0] == "rosey.commands.test-plugin.>"
        assert len(ipc._command_subscriptions) == 1

    async def test_publish_event(self, mock_event_bus):
        """Test publishing plugin event"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        await ipc.publish_event(
            "test.event",
            {"key": "value"},
            priority=Priority.HIGH
        )

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]

        assert event.subject == "rosey.plugins.test-plugin.test.event"
        assert event.event_type == "test.event"
        assert event.source == "plugin.test-plugin"
        assert event.data == {"key": "value"}
        assert event.priority == Priority.HIGH

    async def test_send_health_ok(self, mock_event_bus):
        """Test sending health check OK"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        await ipc.send_health_ok({"version": "1.0"})

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]

        assert event.event_type == EventTypes.HEALTH_CHECK
        assert event.data["status"] == "ok"
        assert event.data["plugin"] == "test-plugin"
        assert event.data["version"] == "1.0"

    async def test_send_startup(self, mock_event_bus):
        """Test sending startup notification"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        await ipc.send_startup({"version": "1.0"})

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]

        assert event.event_type == EventTypes.PLUGIN_START
        assert event.data["plugin"] == "test-plugin"
        assert event.data["version"] == "1.0"
        assert event.priority == Priority.HIGH

    async def test_send_shutdown(self, mock_event_bus):
        """Test sending shutdown notification"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        await ipc.send_shutdown({"reason": "restart"})

        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args[0][0]

        assert event.event_type == EventTypes.PLUGIN_STOP
        assert event.data["plugin"] == "test-plugin"
        assert event.data["reason"] == "restart"
        assert event.priority == Priority.HIGH

    async def test_cleanup(self, mock_event_bus):
        """Test cleaning up IPC resources"""
        ipc = PluginIPC("test-plugin", mock_event_bus)

        # Subscribe to commands
        async def handler(event):
            pass

        await ipc.subscribe_commands(handler)
        assert len(ipc._command_subscriptions) == 1

        # Cleanup
        await ipc.cleanup()

        mock_event_bus.unsubscribe.assert_called_once()
        assert len(ipc._command_subscriptions) == 0


# ============================================================================
# PluginProcess Tests
# ============================================================================

@pytest.mark.asyncio
class TestPluginProcess:
    """Test plugin process management"""

    @pytest.fixture
    def mock_multiprocessing_process(self):
        """Mock multiprocessing.Process"""
        proc = Mock()
        proc.start = Mock()
        proc.is_alive = Mock(return_value=True)
        proc.terminate = Mock()
        proc.kill = Mock()
        proc.join = Mock()
        proc.pid = 12345
        return proc

    async def test_plugin_process_creation(self, mock_event_bus):
        """Test creating plugin process"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus
        )

        assert plugin.plugin_name == "test-plugin"
        assert plugin.module_path == "test.module"
        assert plugin.event_bus is mock_event_bus
        assert plugin.state == PluginState.STOPPED
        assert plugin.process is None
        assert plugin.pid is None

    async def test_plugin_process_with_config(self, mock_event_bus):
        """Test creating plugin with custom config"""
        restart_config = RestartConfig(policy=RestartPolicy.ALWAYS)
        limits = ResourceLimits(max_cpu_percent=50.0)

        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus,
            restart_config=restart_config,
            resource_limits=limits
        )

        assert plugin.restart_config.policy == RestartPolicy.ALWAYS
        assert plugin.resource_limits.max_cpu_percent == 50.0

    async def test_plugin_states(self):
        """Test plugin state enum values"""
        assert PluginState.STOPPED.value == "stopped"
        assert PluginState.STARTING.value == "starting"
        assert PluginState.RUNNING.value == "running"
        assert PluginState.UNHEALTHY.value == "unhealthy"
        assert PluginState.STOPPING.value == "stopping"
        assert PluginState.CRASHED.value == "crashed"
        assert PluginState.FAILED.value == "failed"

    async def test_start_plugin(self, mock_event_bus, mock_multiprocessing_process):
        """Test starting plugin process"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                # Start plugin
                success = await plugin.start()

                assert success
                assert plugin.state == PluginState.RUNNING
                assert plugin.process is mock_multiprocessing_process
                assert mock_multiprocessing_process.start.called
                assert plugin.pid == 12345

    async def test_start_plugin_already_running(self, mock_event_bus, mock_multiprocessing_process):
        """Test starting plugin that's already running"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                await plugin.start()

                # Try to start again
                success = await plugin.start()

                assert not success
                assert plugin.state == PluginState.RUNNING

    async def test_stop_plugin(self, mock_event_bus, mock_multiprocessing_process):
        """Test stopping plugin process"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                await plugin.start()

                # Stop plugin
                success = await plugin.stop(timeout=0.1)

                assert success
                assert plugin.state == PluginState.STOPPED
                assert mock_multiprocessing_process.terminate.called

    async def test_stop_already_stopped(self, mock_event_bus):
        """Test stopping plugin that's already stopped"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus
        )

        # Already stopped
        success = await plugin.stop()

        assert success
        assert plugin.state == PluginState.STOPPED

    async def test_restart_plugin(self, mock_event_bus, mock_multiprocessing_process):
        """Test restarting plugin process"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            # Create two different mock processes for old and new
            old_proc = Mock()
            old_proc.start = Mock()
            old_proc.is_alive = Mock(return_value=False)  # Terminated
            old_proc.terminate = Mock()
            old_proc.kill = Mock()
            old_proc.join = Mock()
            old_proc.pid = 12345

            new_proc = Mock()
            new_proc.start = Mock()
            new_proc.is_alive = Mock(return_value=True)
            new_proc.terminate = Mock()
            new_proc.kill = Mock()
            new_proc.join = Mock()
            new_proc.pid = 67890

            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', side_effect=[old_proc, new_proc]):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                await plugin.start()
                old_pid = plugin.pid

                # Restart
                success = await plugin.restart()

                assert success
                assert plugin.state == PluginState.RUNNING
                assert plugin.pid == 67890  # New process
                assert plugin.pid != old_pid

    async def test_is_alive(self, mock_event_bus, mock_multiprocessing_process):
        """Test checking if plugin is alive"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                assert not plugin.is_alive()

                await plugin.start()
                assert plugin.is_alive()

                mock_multiprocessing_process.is_alive.return_value = False
                assert not plugin.is_alive()

    async def test_get_uptime(self, mock_event_bus, mock_multiprocessing_process):
        """Test getting plugin uptime"""
        with patch('bot.rosey.core.plugin_isolation.psutil', None):
            with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
                plugin = PluginProcess(
                    plugin_name="test-plugin",
                    module_path="test.module",
                    event_bus=mock_event_bus
                )

                assert plugin.get_uptime() is None

                await plugin.start()
                await asyncio.sleep(0.2)

                uptime = plugin.get_uptime()
                assert uptime is not None
                assert uptime >= 0.2

    async def test_should_restart_never(self, mock_event_bus):
        """Test restart policy NEVER"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus,
            restart_config=RestartConfig(policy=RestartPolicy.NEVER)
        )

        assert not plugin._should_restart()

    async def test_should_restart_always(self, mock_event_bus):
        """Test restart policy ALWAYS"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus,
            restart_config=RestartConfig(policy=RestartPolicy.ALWAYS)
        )

        assert plugin._should_restart()
        plugin._restart_count = 100
        assert plugin._should_restart()  # No limit

    async def test_should_restart_on_failure(self, mock_event_bus):
        """Test restart policy ON_FAILURE with max retries"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus,
            restart_config=RestartConfig(
                policy=RestartPolicy.ON_FAILURE,
                max_retries=3
            )
        )

        assert plugin._should_restart()

        plugin._restart_count = 2
        assert plugin._should_restart()

        plugin._restart_count = 3
        assert not plugin._should_restart()  # Hit limit

    async def test_calculate_backoff(self, mock_event_bus):
        """Test exponential backoff calculation"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus,
            restart_config=RestartConfig(
                backoff_seconds=1.0,
                backoff_multiplier=2.0,
                max_backoff_seconds=10.0
            )
        )

        # First retry: 1.0 * 2^0 = 1.0
        plugin._restart_count = 0
        assert plugin._calculate_backoff() == 1.0

        # Second retry: 1.0 * 2^1 = 2.0
        plugin._restart_count = 1
        assert plugin._calculate_backoff() == 2.0

        # Third retry: 1.0 * 2^2 = 4.0
        plugin._restart_count = 2
        assert plugin._calculate_backoff() == 4.0

        # Very high retry: capped at max
        plugin._restart_count = 10
        assert plugin._calculate_backoff() == 10.0

    async def test_add_callback(self, mock_event_bus):
        """Test adding event callbacks"""
        plugin = PluginProcess(
            plugin_name="test-plugin",
            module_path="test.module",
            event_bus=mock_event_bus
        )

        callback = Mock()
        plugin.add_callback("state_change", callback)

        assert callback in plugin._callbacks["state_change"]


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_plugin_process_with_monitoring(mock_event_bus, mock_psutil_process):
    """Test plugin process with resource monitoring"""
    mock_multiprocessing_process = Mock()
    mock_multiprocessing_process.start = Mock()
    mock_multiprocessing_process.is_alive = Mock(return_value=True)
    mock_multiprocessing_process.terminate = Mock()
    mock_multiprocessing_process.kill = Mock()
    mock_multiprocessing_process.join = Mock()
    mock_multiprocessing_process.pid = 12345

    with patch('bot.rosey.core.plugin_isolation.psutil') as mock_psutil:
        mock_psutil.Process.return_value = mock_psutil_process

        with patch('bot.rosey.core.plugin_isolation.multiprocessing.Process', return_value=mock_multiprocessing_process):
            limits = ResourceLimits(max_cpu_percent=50.0, max_memory_mb=200.0)

            plugin = PluginProcess(
                plugin_name="test-plugin",
                module_path="test.module",
                event_bus=mock_event_bus,
                resource_limits=limits
            )

            await plugin.start()

            # Monitor should be created
            assert plugin.monitor is not None
            assert plugin.monitor.limits.max_cpu_percent == 50.0

            # Cleanup
            mock_multiprocessing_process.is_alive.return_value = False
            await plugin.stop()


@pytest.mark.asyncio
async def test_plugin_ipc_full_flow(mock_event_bus):
    """Test full plugin IPC flow"""
    ipc = PluginIPC("test-plugin", mock_event_bus)

    # Subscribe to commands
    received_events = []

    async def handler(event):
        received_events.append(event)

    await ipc.subscribe_commands(handler)

    # Send various events
    await ipc.send_startup({"version": "1.0"})
    await ipc.send_health_ok({"cpu": 25.5})
    await ipc.publish_event("custom.event", {"data": "test"})
    await ipc.send_shutdown({"reason": "test complete"})

    # Verify all published
    assert mock_event_bus.publish.call_count == 4

    # Cleanup
    await ipc.cleanup()
    mock_event_bus.unsubscribe.assert_called_once()
