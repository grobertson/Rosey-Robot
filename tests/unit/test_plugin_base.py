"""
# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
# This test file is DEPRECATED and scheduled for removal.
#
# Reason: The lib/plugin/ module and Plugin base class have been superseded
# by the NATS-based plugin architecture. All plugins now:
# - Run as separate processes
# - Communicate via NATS messaging
# - Do not inherit from a base class
#
# Reference: See plugins/quote-db/ and plugins/dice-roller/ for the
# correct plugin pattern.
#
# TODO: Remove this file once all legacy plugin code is deleted.
# ============================================================================

tests/unit/test_plugin_base.py

Unit tests for plugin base class.
"""

import pytest
from lib.plugin import Plugin, PluginMetadata, PluginError


# =================================================================
# Test Plugin Implementation
# =================================================================

class TestPlugin(Plugin):
    """Simple test plugin."""

    @property
    def metadata(self):
        return PluginMetadata(
            name='test_plugin',
            display_name='Test Plugin',
            version='1.0.0',
            description='Test plugin',
            author='Test'
        )


class MinimalPlugin(Plugin):
    """Minimal plugin with no custom implementation."""

    @property
    def metadata(self):
        return PluginMetadata(
            name='minimal',
            display_name='Minimal',
            version='0.1.0',
            description='Minimal test plugin',
            author='Test'
        )


# =================================================================
# Mock Bot
# =================================================================

class MockBot:
    """Mock bot for testing."""

    def __init__(self):
        self.messages = []
        self.storage = None

    async def send_message(self, message: str):
        """Record sent messages."""
        self.messages.append(message)


# =================================================================
# Initialization Tests
# =================================================================

def test_plugin_init():
    """Test plugin initialization."""
    bot = MockBot()
    config = {'key': 'value'}

    plugin = TestPlugin(bot, config)

    assert plugin.bot is bot
    assert plugin.config == config
    assert plugin.is_enabled is False
    assert plugin.logger is not None
    assert plugin._event_handlers == {}


def test_plugin_init_no_config():
    """Test plugin initialization without config."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    assert plugin.config == {}


def test_plugin_metadata():
    """Test plugin metadata property."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    meta = plugin.metadata
    assert meta.name == 'test_plugin'
    assert meta.display_name == 'Test Plugin'
    assert meta.version == '1.0.0'
    assert meta.description == 'Test plugin'
    assert meta.author == 'Test'


# =================================================================
# Lifecycle Tests
# =================================================================

@pytest.mark.asyncio
async def test_setup_default():
    """Test default setup() does nothing."""
    bot = MockBot()
    plugin = MinimalPlugin(bot)

    # Should not raise
    await plugin.setup()


@pytest.mark.asyncio
async def test_teardown_default():
    """Test default teardown() does nothing."""
    bot = MockBot()
    plugin = MinimalPlugin(bot)

    # Should not raise
    await plugin.teardown()


@pytest.mark.asyncio
async def test_on_enable():
    """Test on_enable sets enabled flag."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    assert plugin.is_enabled is False

    await plugin.on_enable()

    assert plugin.is_enabled is True


@pytest.mark.asyncio
async def test_on_disable():
    """Test on_disable clears enabled flag."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    await plugin.on_enable()
    assert plugin.is_enabled is True

    await plugin.on_disable()
    assert plugin.is_enabled is False


@pytest.mark.asyncio
async def test_lifecycle_flow():
    """Test full lifecycle flow."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    # Initial state
    assert plugin.is_enabled is False

    # Setup
    await plugin.setup()
    assert plugin.is_enabled is False  # Not enabled yet

    # Enable
    await plugin.on_enable()
    assert plugin.is_enabled is True

    # Disable
    await plugin.on_disable()
    assert plugin.is_enabled is False

    # Teardown
    await plugin.teardown()


# =================================================================
# Event Registration Tests
# =================================================================

def test_event_registration():
    """Test registering event handlers."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    async def handler(event, data):
        pass

    plugin.on('message', handler)

    assert 'message' in plugin._event_handlers
    assert handler in plugin._event_handlers['message']


def test_multiple_handlers_same_event():
    """Test multiple handlers for same event."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    async def handler1(event, data):
        pass

    async def handler2(event, data):
        pass

    plugin.on('message', handler1)
    plugin.on('message', handler2)

    handlers = plugin._event_handlers['message']
    assert len(handlers) == 2
    assert handler1 in handlers
    assert handler2 in handlers


def test_on_message_decorator():
    """Test on_message decorator registers handler."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    @plugin.on_message
    async def handler(event, data):
        pass

    assert 'message' in plugin._event_handlers
    assert handler in plugin._event_handlers['message']


def test_on_user_join_decorator():
    """Test on_user_join decorator."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    @plugin.on_user_join
    async def handler(event, data):
        pass

    assert 'user_join' in plugin._event_handlers
    assert handler in plugin._event_handlers['user_join']


def test_on_user_leave_decorator():
    """Test on_user_leave decorator."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    @plugin.on_user_leave
    async def handler(event, data):
        pass

    assert 'user_leave' in plugin._event_handlers
    assert handler in plugin._event_handlers['user_leave']


@pytest.mark.asyncio
async def test_on_command_decorator():
    """Test on_command decorator parses commands."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    called = []

    async def handler(username, args):
        called.append((username, args))

    plugin.on_command('test', handler)

    # Trigger the command
    message_handlers = plugin._event_handlers['message']
    assert len(message_handlers) == 1

    # Simulate !test command
    await plugin.on_enable()
    await message_handlers[0]('message', {
        'user': 'testuser',
        'content': '!test arg1 arg2'
    })

    assert len(called) == 1
    assert called[0] == ('testuser', ['arg1', 'arg2'])


@pytest.mark.asyncio
async def test_on_command_no_args():
    """Test command with no arguments."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    called = []

    async def handler(username, args):
        called.append((username, args))

    plugin.on_command('simple', handler)

    await plugin.on_enable()
    message_handlers = plugin._event_handlers['message']

    # Simulate !simple (no args)
    await message_handlers[0]('message', {
        'user': 'testuser',
        'content': '!simple'
    })

    assert called == [('testuser', [])]


@pytest.mark.asyncio
async def test_on_command_disabled():
    """Test command doesn't fire when disabled."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    called = []

    async def handler(username, args):
        called.append((username, args))

    plugin.on_command('test', handler)

    # Plugin is disabled
    assert plugin.is_enabled is False

    message_handlers = plugin._event_handlers['message']
    await message_handlers[0]('message', {
        'user': 'testuser',
        'content': '!test'
    })

    # Should not call handler
    assert called == []


# =================================================================
# Bot Interaction Tests
# =================================================================

@pytest.mark.asyncio
async def test_send_message():
    """Test sending messages to bot."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    await plugin.send_message("Hello")

    assert bot.messages == ["Hello"]


@pytest.mark.asyncio
async def test_send_message_no_support():
    """Test send_message when bot doesn't support it."""
    class BotNoSend:
        pass

    bot = BotNoSend()
    plugin = TestPlugin(bot)

    # Should not raise, just log warning
    await plugin.send_message("Hello")


# =================================================================
# Configuration Tests
# =================================================================

def test_get_config_simple():
    """Test getting simple config values."""
    bot = MockBot()
    config = {
        'key1': 'value1',
        'key2': 42
    }
    plugin = TestPlugin(bot, config)

    assert plugin.get_config('key1') == 'value1'
    assert plugin.get_config('key2') == 42


def test_get_config_default():
    """Test get_config with default value."""
    bot = MockBot()
    plugin = TestPlugin(bot, {})

    assert plugin.get_config('missing', 'default') == 'default'


def test_get_config_nested():
    """Test getting nested config with dot notation."""
    bot = MockBot()
    config = {
        'database': {
            'host': 'localhost',
            'port': 5432,
            'credentials': {
                'user': 'admin'
            }
        }
    }
    plugin = TestPlugin(bot, config)

    assert plugin.get_config('database.host') == 'localhost'
    assert plugin.get_config('database.port') == 5432
    assert plugin.get_config('database.credentials.user') == 'admin'


def test_get_config_nested_missing():
    """Test nested config with missing keys."""
    bot = MockBot()
    config = {'database': {'host': 'localhost'}}
    plugin = TestPlugin(bot, config)

    assert plugin.get_config('database.missing', 'default') == 'default'
    assert plugin.get_config('missing.nested', 'default') == 'default'


def test_validate_config_success():
    """Test validate_config with all required keys."""
    bot = MockBot()
    config = {
        'api_key': 'secret',
        'server': {
            'host': 'localhost'
        }
    }
    plugin = TestPlugin(bot, config)

    # Should not raise
    plugin.validate_config(['api_key', 'server.host'])


def test_validate_config_missing():
    """Test validate_config with missing keys."""
    bot = MockBot()
    config = {'api_key': 'secret'}
    plugin = TestPlugin(bot, config)

    with pytest.raises(PluginError) as exc_info:
        plugin.validate_config(['api_key', 'server.host'])

    assert 'server.host' in str(exc_info.value)


# =================================================================
# Storage Access Tests
# =================================================================

def test_storage_property():
    """Test storage property returns bot storage."""
    class BotWithStorage:
        def __init__(self):
            self.storage = "mock_storage"

    bot = BotWithStorage()
    plugin = TestPlugin(bot)

    assert plugin.storage == "mock_storage"


def test_storage_property_none():
    """Test storage property when bot has no storage."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    assert plugin.storage is None


# =================================================================
# String Representation Tests
# =================================================================

def test_str():
    """Test __str__ returns metadata string."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    result = str(plugin)
    # PluginMetadata.__str__ returns "Test Plugin v1.0.0"
    assert 'Test Plugin' in result or 'test_plugin' in result


def test_repr():
    """Test __repr__ includes name, version, and status."""
    bot = MockBot()
    plugin = TestPlugin(bot)

    result = repr(plugin)
    assert 'test_plugin' in result
    assert '1.0.0' in result
    assert 'disabled' in result

    # Enable and check again
    plugin._is_enabled = True
    result = repr(plugin)
    assert 'enabled' in result


# =================================================================
# Integration Tests
# =================================================================

@pytest.mark.asyncio
async def test_full_plugin_workflow():
    """Test complete plugin workflow."""
    bot = MockBot()
    config = {
        'greeting': 'Hello',
        'max_count': 5
    }

    plugin = TestPlugin(bot, config)

    # Setup
    await plugin.setup()

    # Enable
    await plugin.on_enable()
    assert plugin.is_enabled is True

    # Register handlers
    messages_received = []

    @plugin.on_message
    async def handler(event, data):
        messages_received.append(data)

    # Simulate event
    handlers = plugin._event_handlers['message']
    await handlers[0]('message', {'user': 'test', 'content': 'hello'})

    assert len(messages_received) == 1
    assert messages_received[0]['content'] == 'hello'

    # Send message
    await plugin.send_message("Response")
    assert bot.messages == ["Response"]

    # Disable
    await plugin.on_disable()
    assert plugin.is_enabled is False

    # Teardown
    await plugin.teardown()
