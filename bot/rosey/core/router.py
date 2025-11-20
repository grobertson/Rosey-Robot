"""
Core message router for Rosey Bot.

The router sits between the platform (Cytube) and plugins, intelligently
routing messages, commands, and events between them based on patterns,
priorities, and plugin capabilities.

Key responsibilities:
- Route platform messages to appropriate plugins
- Route plugin responses back to platform
- Handle command dispatch with pattern matching
- Manage routing rules and priorities
- Support broadcast and targeted routing
"""

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Callable, Optional, Any, Pattern
import logging

from .event_bus import EventBus, Event, Priority
from .subjects import Subjects, SubjectBuilder, EventTypes
from .plugin_manager import PluginManager


logger = logging.getLogger(__name__)


# ============================================================================
# Route Types and Patterns
# ============================================================================

class RouteType(Enum):
    """Type of routing to perform"""
    DIRECT = auto()      # Route to specific plugin
    PATTERN = auto()     # Route based on pattern match
    BROADCAST = auto()   # Route to all matching plugins
    FALLBACK = auto()    # Route to fallback handler


class MatchType(Enum):
    """How to match messages to routes"""
    EXACT = auto()       # Exact string match
    PREFIX = auto()      # Message starts with pattern
    SUFFIX = auto()      # Message ends with pattern
    CONTAINS = auto()    # Message contains pattern
    REGEX = auto()       # Regular expression match


@dataclass
class RoutePattern:
    """Pattern for matching and routing messages"""
    pattern: str
    match_type: MatchType
    target_plugin: Optional[str] = None  # None = broadcast
    priority: int = 0  # Higher priority routes checked first
    enabled: bool = True
    
    # Compiled regex if match_type is REGEX
    _regex: Optional[Pattern] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Compile regex pattern if needed"""
        if self.match_type == MatchType.REGEX:
            try:
                self._regex = re.compile(self.pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{self.pattern}': {e}")
                self.enabled = False
    
    def matches(self, text: str) -> bool:
        """Check if text matches this pattern"""
        if not self.enabled:
            return False
        
        text_lower = text.lower()
        pattern_lower = self.pattern.lower()
        
        if self.match_type == MatchType.EXACT:
            return text_lower == pattern_lower
        elif self.match_type == MatchType.PREFIX:
            return text_lower.startswith(pattern_lower)
        elif self.match_type == MatchType.SUFFIX:
            return text_lower.endswith(pattern_lower)
        elif self.match_type == MatchType.CONTAINS:
            return pattern_lower in text_lower
        elif self.match_type == MatchType.REGEX:
            return self._regex is not None and self._regex.search(text) is not None
        
        return False


@dataclass
class RouteRule:
    """Complete routing rule with pattern and metadata"""
    name: str
    pattern: RoutePattern
    route_type: RouteType
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, text: str) -> bool:
        """Check if text matches this rule's pattern"""
        return self.pattern.matches(text)


# ============================================================================
# Command Router
# ============================================================================

class CommandRouter:
    """
    Routes commands and messages between platform and plugins.
    
    The router maintains routing rules, subscribes to platform events,
    matches incoming messages against patterns, and dispatches to
    appropriate plugins via the EventBus.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        plugin_manager: PluginManager,
        command_prefix: str = "!"
    ):
        """
        Initialize command router.
        
        Args:
            event_bus: EventBus for communication
            plugin_manager: Plugin manager for plugin info
            command_prefix: Prefix for explicit commands (default: !)
        """
        self.event_bus = event_bus
        self.plugin_manager = plugin_manager
        self.command_prefix = command_prefix
        
        # Routing tables
        self._rules: List[RouteRule] = []
        self._command_handlers: Dict[str, str] = {}  # command -> plugin
        self._fallback_plugins: List[str] = []
        
        # Subscription tracking
        self._subscriptions: List[int] = []
        self._running = False
    
    # ========================================================================
    # Lifecycle
    # ========================================================================
    
    async def start(self) -> bool:
        """
        Start the router and subscribe to events.
        
        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Router already running")
            return False
        
        try:
            # Subscribe to platform messages (cytube.message, etc.)
            sub_id = await self.event_bus.subscribe(
                f"{Subjects.PLATFORM}.*.{EventTypes.MESSAGE}",
                self._handle_platform_message
            )
            self._subscriptions.append(sub_id)
            
            # Subscribe to platform commands
            sub_id = await self.event_bus.subscribe(
                f"{Subjects.PLATFORM}.*.{EventTypes.COMMAND}",
                self._handle_platform_command
            )
            self._subscriptions.append(sub_id)
            
            # Subscribe to plugin responses
            sub_id = await self.event_bus.subscribe(
                f"{Subjects.PLUGINS}.*.{EventTypes.MESSAGE}",
                self._handle_plugin_response
            )
            self._subscriptions.append(sub_id)
            
            self._running = True
            logger.info("Command router started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start router: {e}")
            return False
    
    async def stop(self) -> bool:
        """
        Stop the router and unsubscribe from events.
        
        Returns:
            True if stopped successfully
        """
        if not self._running:
            return True
        
        try:
            # Unsubscribe from all events
            for sub_id in self._subscriptions:
                await self.event_bus.unsubscribe(sub_id)
            
            self._subscriptions.clear()
            self._running = False
            logger.info("Command router stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop router: {e}")
            return False
    
    # ========================================================================
    # Route Management
    # ========================================================================
    
    def add_rule(self, rule: RouteRule) -> None:
        """Add a routing rule"""
        self._rules.append(rule)
        # Sort by priority (highest first)
        self._rules.sort(key=lambda r: r.pattern.priority, reverse=True)
        logger.debug(f"Added routing rule: {rule.name}")
    
    def remove_rule(self, name: str) -> bool:
        """Remove a routing rule by name"""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                logger.debug(f"Removed routing rule: {name}")
                return True
        return False
    
    def add_command_handler(self, command: str, plugin_name: str) -> None:
        """Register a plugin as handler for a specific command"""
        self._command_handlers[command.lower()] = plugin_name
        logger.debug(f"Registered command handler: {command} -> {plugin_name}")
    
    def remove_command_handler(self, command: str) -> bool:
        """Unregister a command handler"""
        command_lower = command.lower()
        if command_lower in self._command_handlers:
            del self._command_handlers[command_lower]
            logger.debug(f"Unregistered command handler: {command}")
            return True
        return False
    
    def add_fallback_plugin(self, plugin_name: str) -> None:
        """Add a plugin to handle unmatched messages"""
        if plugin_name not in self._fallback_plugins:
            self._fallback_plugins.append(plugin_name)
            logger.debug(f"Added fallback plugin: {plugin_name}")
    
    def remove_fallback_plugin(self, plugin_name: str) -> bool:
        """Remove a fallback plugin"""
        if plugin_name in self._fallback_plugins:
            self._fallback_plugins.remove(plugin_name)
            logger.debug(f"Removed fallback plugin: {plugin_name}")
            return True
        return False
    
    # ========================================================================
    # Message Routing
    # ========================================================================
    
    async def _handle_platform_message(self, event: Event) -> None:
        """
        Handle incoming platform message.
        
        Routes the message to appropriate plugins based on:
        1. Routing rules (patterns)
        2. Fallback plugins
        """
        message = event.data.get("message", "")
        if not message:
            return
        
        logger.debug(f"Routing platform message: {message[:50]}...")
        
        # Find matching rules
        matched_rules = [rule for rule in self._rules if rule.matches(message)]
        
        if matched_rules:
            await self._route_by_rules(event, matched_rules)
        else:
            await self._route_to_fallbacks(event)
    
    async def _handle_platform_command(self, event: Event) -> None:
        """
        Handle incoming platform command.
        
        Commands have explicit format: !command args
        Routes directly to registered command handler.
        """
        command = event.data.get("command", "")
        if not command:
            return
        
        logger.debug(f"Routing platform command: {command}")
        
        # Extract command name
        parts = command.split(maxsplit=1)
        command_name = parts[0].lower()
        
        # Remove prefix if present
        if command_name.startswith(self.command_prefix):
            command_name = command_name[len(self.command_prefix):]
        
        # Find handler
        plugin_name = self._command_handlers.get(command_name)
        
        if plugin_name:
            await self._route_to_plugin(event, plugin_name)
        else:
            logger.debug(f"No handler for command: {command_name}")
    
    async def _handle_plugin_response(self, event: Event) -> None:
        """
        Handle plugin response and route to platform.
        
        Takes plugin output and formats it for platform delivery.
        """
        response = event.data.get("response", "")
        if not response:
            return
        
        logger.debug(f"Routing plugin response to platform: {response[:50]}...")
        
        # Create platform send event
        platform_event = Event(
            subject=f"{Subjects.PLATFORM}.cytube.{EventTypes.MESSAGE}",
            event_type=EventTypes.MESSAGE,
            source="router",
            data={
                "message": response,
                "plugin": event.source,
                "correlation_id": event.correlation_id
            },
            correlation_id=event.correlation_id
        )
        
        await self.event_bus.publish(platform_event)
    
    async def _route_by_rules(
        self,
        event: Event,
        matched_rules: List[RouteRule]
    ) -> None:
        """Route message according to matched rules"""
        for rule in matched_rules:
            if rule.route_type == RouteType.DIRECT:
                if rule.pattern.target_plugin:
                    await self._route_to_plugin(event, rule.pattern.target_plugin)
                    break  # Only route to first matching direct rule
                    
            elif rule.route_type == RouteType.BROADCAST:
                # Get all running plugins
                running = self.plugin_manager.registry.list_running()
                for plugin_name in running:
                    await self._route_to_plugin(event, plugin_name)
                break
                
            elif rule.route_type == RouteType.PATTERN:
                if rule.pattern.target_plugin:
                    await self._route_to_plugin(event, rule.pattern.target_plugin)
                    # Continue to next rule (pattern routes don't break)
    
    async def _route_to_fallbacks(self, event: Event) -> None:
        """Route message to fallback plugins"""
        if not self._fallback_plugins:
            logger.debug("No fallback plugins configured")
            return
        
        for plugin_name in self._fallback_plugins:
            await self._route_to_plugin(event, plugin_name)
    
    async def _route_to_plugin(self, event: Event, plugin_name: str) -> None:
        """Route event to specific plugin"""
        # Check plugin is running
        if not self.plugin_manager.registry.has(plugin_name):
            logger.warning(f"Cannot route to unknown plugin: {plugin_name}")
            return
        
        entry = self.plugin_manager.registry.get(plugin_name)
        if not entry or not entry.is_running():
            logger.warning(f"Cannot route to stopped plugin: {plugin_name}")
            return
        
        # Create plugin-specific event
        plugin_subject = f"{Subjects.PLUGINS}.{plugin_name}.{EventTypes.MESSAGE}"
        
        plugin_event = Event(
            subject=plugin_subject,
            event_type=EventTypes.MESSAGE,
            source="router",
            data=event.data,
            correlation_id=event.correlation_id,
            priority=event.priority
        )
        
        await self.event_bus.publish(plugin_event)
        logger.debug(f"Routed message to plugin: {plugin_name}")
    
    # ========================================================================
    # Queries
    # ========================================================================
    
    def get_rules(self) -> List[RouteRule]:
        """Get all routing rules"""
        return self._rules.copy()
    
    def get_command_handlers(self) -> Dict[str, str]:
        """Get all command handlers"""
        return self._command_handlers.copy()
    
    def get_fallback_plugins(self) -> List[str]:
        """Get all fallback plugins"""
        return self._fallback_plugins.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics"""
        return {
            "running": self._running,
            "rules": len(self._rules),
            "command_handlers": len(self._command_handlers),
            "fallback_plugins": len(self._fallback_plugins),
            "subscriptions": len(self._subscriptions)
        }
