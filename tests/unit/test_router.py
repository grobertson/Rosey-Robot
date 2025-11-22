"""
Unit tests for command router system.

Tests cover:
- RoutePattern: Pattern matching with different match types
- RouteRule: Complete routing rules with metadata
- CommandRouter: Message routing between platform and plugins
"""

import pytest
from unittest.mock import AsyncMock, Mock

from bot.rosey.core.router import (
    RouteType,
    MatchType,
    RoutePattern,
    RouteRule,
    CommandRouter
)
from bot.rosey.core.event_bus import Event, EventBus
from bot.rosey.core.subjects import Subjects, EventTypes
from bot.rosey.core.plugin_manager import (
    PluginManager,
    PluginEntry
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = AsyncMock(spec=EventBus)
    bus.subscribe = AsyncMock(return_value=1)
    bus.unsubscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_plugin_manager():
    """Mock PluginManager with some plugins"""
    manager = Mock(spec=PluginManager)
    
    # Mock registry
    manager.registry = Mock()
    manager.registry.has = Mock(return_value=True)
    manager.registry.list_running = Mock(return_value=["plugin1", "plugin2"])
    
    # Mock plugin entry
    mock_entry = Mock(spec=PluginEntry)
    mock_entry.is_running = Mock(return_value=True)
    manager.registry.get = Mock(return_value=mock_entry)
    
    return manager


# ============================================================================
# RoutePattern Tests
# ============================================================================

class TestRoutePattern:
    """Test route pattern matching"""
    
    def test_exact_match(self):
        """Test exact string matching"""
        pattern = RoutePattern("hello", MatchType.EXACT)
        
        assert pattern.matches("hello") is True
        assert pattern.matches("HELLO") is True
        assert pattern.matches("hello world") is False
    
    def test_prefix_match(self):
        """Test prefix matching"""
        pattern = RoutePattern("!", MatchType.PREFIX)
        
        assert pattern.matches("!help") is True
        assert pattern.matches("!command") is True
        assert pattern.matches("help!") is False
        assert pattern.matches("no prefix") is False
    
    def test_suffix_match(self):
        """Test suffix matching"""
        pattern = RoutePattern("?", MatchType.SUFFIX)
        
        assert pattern.matches("what is this?") is True
        assert pattern.matches("question?") is True
        assert pattern.matches("?question") is False
    
    def test_contains_match(self):
        """Test contains matching"""
        pattern = RoutePattern("bot", MatchType.CONTAINS)
        
        assert pattern.matches("hey bot") is True
        assert pattern.matches("robot") is True
        assert pattern.matches("bot help") is True
        assert pattern.matches("hello") is False
    
    def test_regex_match(self):
        """Test regex matching"""
        pattern = RoutePattern(r"\d+", MatchType.REGEX)
        
        assert pattern.matches("123") is True
        assert pattern.matches("test 456 test") is True
        assert pattern.matches("no numbers") is False
    
    def test_regex_complex(self):
        """Test complex regex pattern"""
        pattern = RoutePattern(r"^(hello|hi|hey)\s+bot", MatchType.REGEX)
        
        assert pattern.matches("hello bot") is True
        assert pattern.matches("hi bot") is True
        assert pattern.matches("hey bot!") is True
        assert pattern.matches("greetings bot") is False
    
    def test_case_insensitive(self):
        """Test that matching is case-insensitive"""
        pattern = RoutePattern("TEST", MatchType.EXACT)
        
        assert pattern.matches("test") is True
        assert pattern.matches("Test") is True
        assert pattern.matches("TEST") is True
    
    def test_disabled_pattern(self):
        """Test that disabled patterns don't match"""
        pattern = RoutePattern("test", MatchType.EXACT, enabled=False)
        
        assert pattern.matches("test") is False
    
    def test_invalid_regex(self):
        """Test handling of invalid regex"""
        pattern = RoutePattern("[invalid(", MatchType.REGEX)
        
        # Should be disabled due to invalid regex
        assert pattern.enabled is False
        assert pattern.matches("anything") is False
    
    def test_pattern_with_target(self):
        """Test pattern with specific target plugin"""
        pattern = RoutePattern(
            "help",
            MatchType.PREFIX,
            target_plugin="help-plugin"
        )
        
        assert pattern.target_plugin == "help-plugin"
        assert pattern.matches("help me") is True
    
    def test_pattern_priority(self):
        """Test pattern with priority"""
        pattern = RoutePattern("test", MatchType.EXACT, priority=10)
        
        assert pattern.priority == 10


# ============================================================================
# RouteRule Tests
# ============================================================================

class TestRouteRule:
    """Test routing rules"""
    
    def test_rule_creation(self):
        """Test creating a routing rule"""
        pattern = RoutePattern("help", MatchType.PREFIX)
        rule = RouteRule(
            name="help-rule",
            pattern=pattern,
            route_type=RouteType.DIRECT,
            description="Route help commands"
        )
        
        assert rule.name == "help-rule"
        assert rule.route_type == RouteType.DIRECT
        assert rule.description == "Route help commands"
    
    def test_rule_matches(self):
        """Test rule matching delegates to pattern"""
        pattern = RoutePattern("test", MatchType.EXACT)
        rule = RouteRule("test-rule", pattern, RouteType.DIRECT)
        
        assert rule.matches("test") is True
        assert rule.matches("other") is False
    
    def test_rule_with_metadata(self):
        """Test rule with custom metadata"""
        pattern = RoutePattern("cmd", MatchType.PREFIX)
        rule = RouteRule(
            "cmd-rule",
            pattern,
            RouteType.PATTERN,
            metadata={"category": "commands", "version": "1.0"}
        )
        
        assert rule.metadata["category"] == "commands"
        assert rule.metadata["version"] == "1.0"


# ============================================================================
# CommandRouter Tests
# ============================================================================

@pytest.mark.asyncio
class TestCommandRouter:
    """Test command router"""
    
    async def test_router_creation(self, mock_event_bus, mock_plugin_manager):
        """Test creating router"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        assert router.event_bus is mock_event_bus
        assert router.plugin_manager is mock_plugin_manager
        assert router.command_prefix == "!"
    
    async def test_custom_prefix(self, mock_event_bus, mock_plugin_manager):
        """Test router with custom command prefix"""
        router = CommandRouter(
            mock_event_bus,
            mock_plugin_manager,
            command_prefix="/"
        )
        
        assert router.command_prefix == "/"
    
    async def test_start_router(self, mock_event_bus, mock_plugin_manager):
        """Test starting router"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        success = await router.start()
        
        assert success is True
        assert mock_event_bus.subscribe.call_count == 3
    
    async def test_start_already_running(self, mock_event_bus, mock_plugin_manager):
        """Test starting already running router"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        await router.start()
        success = await router.start()
        
        assert success is False
    
    async def test_stop_router(self, mock_event_bus, mock_plugin_manager):
        """Test stopping router"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        await router.start()
        success = await router.stop()
        
        assert success is True
        assert mock_event_bus.unsubscribe.call_count == 3
    
    async def test_add_rule(self, mock_event_bus, mock_plugin_manager):
        """Test adding routing rule"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        pattern = RoutePattern("help", MatchType.PREFIX, priority=5)
        rule = RouteRule("help-rule", pattern, RouteType.DIRECT)
        
        router.add_rule(rule)
        
        rules = router.get_rules()
        assert len(rules) == 1
        assert rules[0].name == "help-rule"
    
    async def test_rules_sorted_by_priority(self, mock_event_bus, mock_plugin_manager):
        """Test that rules are sorted by priority"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        rule1 = RouteRule("low", RoutePattern("a", MatchType.EXACT, priority=1), RouteType.DIRECT)
        rule2 = RouteRule("high", RoutePattern("b", MatchType.EXACT, priority=10), RouteType.DIRECT)
        rule3 = RouteRule("med", RoutePattern("c", MatchType.EXACT, priority=5), RouteType.DIRECT)
        
        router.add_rule(rule1)
        router.add_rule(rule2)
        router.add_rule(rule3)
        
        rules = router.get_rules()
        assert rules[0].name == "high"  # priority 10
        assert rules[1].name == "med"   # priority 5
        assert rules[2].name == "low"   # priority 1
    
    async def test_remove_rule(self, mock_event_bus, mock_plugin_manager):
        """Test removing routing rule"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        rule = RouteRule("test", RoutePattern("x", MatchType.EXACT), RouteType.DIRECT)
        router.add_rule(rule)
        
        success = router.remove_rule("test")
        
        assert success is True
        assert len(router.get_rules()) == 0
    
    async def test_add_command_handler(self, mock_event_bus, mock_plugin_manager):
        """Test registering command handler"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        router.add_command_handler("help", "help-plugin")
        
        handlers = router.get_command_handlers()
        assert handlers["help"] == "help-plugin"
    
    async def test_remove_command_handler(self, mock_event_bus, mock_plugin_manager):
        """Test removing command handler"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        router.add_command_handler("test", "test-plugin")
        success = router.remove_command_handler("test")
        
        assert success is True
        assert len(router.get_command_handlers()) == 0
    
    async def test_add_fallback_plugin(self, mock_event_bus, mock_plugin_manager):
        """Test adding fallback plugin"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        router.add_fallback_plugin("fallback-plugin")
        
        fallbacks = router.get_fallback_plugins()
        assert "fallback-plugin" in fallbacks
    
    async def test_remove_fallback_plugin(self, mock_event_bus, mock_plugin_manager):
        """Test removing fallback plugin"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        router.add_fallback_plugin("test-plugin")
        success = router.remove_fallback_plugin("test-plugin")
        
        assert success is True
        assert len(router.get_fallback_plugins()) == 0
    
    async def test_route_to_plugin_direct(self, mock_event_bus, mock_plugin_manager):
        """Test routing message to specific plugin"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "test message"}
        )
        
        # Route directly
        await router._route_to_plugin(event, "plugin1")
        
        # Verify publish was called
        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args[0][0]
        assert "plugin1" in call_args.subject
    
    async def test_route_command_with_handler(self, mock_event_bus, mock_plugin_manager):
        """Test routing command to registered handler"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        router.add_command_handler("help", "help-plugin")
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.COMMAND}",
            event_type=EventTypes.COMMAND,
            source="platform",
            data={"command": "!help"}
        )
        
        await router._handle_platform_command(event)
        
        # Verify routed to help-plugin
        mock_event_bus.publish.assert_called()
    
    async def test_route_message_by_pattern(self, mock_event_bus, mock_plugin_manager):
        """Test routing message by pattern match"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        # Add rule
        pattern = RoutePattern("hello", MatchType.PREFIX, target_plugin="greeter-plugin")
        rule = RouteRule("greet", pattern, RouteType.DIRECT)
        router.add_rule(rule)
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "hello world"}
        )
        
        await router._handle_platform_message(event)
        
        # Verify routed
        mock_event_bus.publish.assert_called()
    
    async def test_route_to_fallback(self, mock_event_bus, mock_plugin_manager):
        """Test routing unmatched message to fallback"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        router.add_fallback_plugin("fallback-plugin")
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "unmatched message"}
        )
        
        await router._handle_platform_message(event)
        
        # Verify routed to fallback
        mock_event_bus.publish.assert_called()
    
    async def test_route_plugin_response(self, mock_event_bus, mock_plugin_manager):
        """Test routing plugin response to platform"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        event = Event(
            subject=f"{Subjects.PLUGINS}.test-plugin.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="test-plugin",
            data={"response": "Test response"}
        )
        
        await router._handle_plugin_response(event)
        
        # Verify published to platform
        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args[0][0]
        assert Subjects.PLATFORM in call_args.subject
    
    async def test_broadcast_route(self, mock_event_bus, mock_plugin_manager):
        """Test broadcast routing to all plugins"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        # Add broadcast rule
        pattern = RoutePattern("announce", MatchType.PREFIX)
        rule = RouteRule("broadcast", pattern, RouteType.BROADCAST)
        router.add_rule(rule)
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "announce something"}
        )
        
        await router._handle_platform_message(event)
        
        # Verify routed to multiple plugins
        assert mock_event_bus.publish.call_count >= 2  # plugin1 and plugin2
    
    async def test_get_statistics(self, mock_event_bus, mock_plugin_manager):
        """Test getting router statistics"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        
        router.add_rule(RouteRule("r1", RoutePattern("a", MatchType.EXACT), RouteType.DIRECT))
        router.add_command_handler("cmd", "plugin")
        router.add_fallback_plugin("fallback")
        
        stats = router.get_statistics()
        
        assert stats["rules"] == 1
        assert stats["command_handlers"] == 1
        assert stats["fallback_plugins"] == 1
        assert stats["running"] is False
    
    async def test_dont_route_to_stopped_plugin(self, mock_event_bus, mock_plugin_manager):
        """Test that stopped plugins are not routed to"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        # Make plugin appear stopped
        mock_entry = Mock()
        mock_entry.is_running = Mock(return_value=False)
        mock_plugin_manager.registry.get = Mock(return_value=mock_entry)
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "test"}
        )
        
        # Try to route
        await router._route_to_plugin(event, "stopped-plugin")
        
        # Should not publish
        mock_event_bus.publish.assert_not_called()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestCommandRouterIntegration:
    """Test router integration scenarios"""
    
    async def test_complete_routing_flow(self, mock_event_bus, mock_plugin_manager):
        """Test complete message routing flow"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        # Add various routing mechanisms
        router.add_command_handler("help", "help-plugin")
        
        pattern = RoutePattern("hello", MatchType.PREFIX, target_plugin="greeter")
        router.add_rule(RouteRule("greet", pattern, RouteType.DIRECT))
        
        router.add_fallback_plugin("logger")
        
        # Test command routing
        cmd_event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.COMMAND}",
            event_type=EventTypes.COMMAND,
            source="platform",
            data={"command": "!help"}
        )
        await router._handle_platform_command(cmd_event)
        
        # Test pattern routing
        msg_event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "hello there"}
        )
        await router._handle_platform_message(msg_event)
        
        # Verify routing occurred
        assert mock_event_bus.publish.call_count >= 2
    
    async def test_priority_routing(self, mock_event_bus, mock_plugin_manager):
        """Test that higher priority rules are checked first"""
        router = CommandRouter(mock_event_bus, mock_plugin_manager)
        await router.start()
        
        # Add rules with different priorities (both match same text)
        high = RouteRule(
            "high",
            RoutePattern("test", MatchType.CONTAINS, target_plugin="high-plugin", priority=10),
            RouteType.DIRECT
        )
        low = RouteRule(
            "low",
            RoutePattern("test", MatchType.CONTAINS, target_plugin="low-plugin", priority=1),
            RouteType.DIRECT
        )
        
        router.add_rule(low)
        router.add_rule(high)
        
        event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="platform",
            data={"message": "test message"}
        )
        
        await router._handle_platform_message(event)
        
        # Should route to high priority plugin only (DIRECT breaks)
        call_args = mock_event_bus.publish.call_args[0][0]
        assert "high-plugin" in call_args.subject
