# Sprint 9 - Plugin 5: Plugin Inspector

**Complexity:** ⭐⭐⭐⭐⭐ (Advanced)  
**Effort:** 4 hours  
**Priority:** Operational Excellence  
**Status:** Specification Complete

## Overview

The Plugin Inspector provides runtime introspection and monitoring of the entire plugin system. This advanced plugin validates service provider patterns, system introspection, event monitoring, and provides critical operational visibility.

### Purpose

- **User Value:** Runtime debugging and system health monitoring
- **Architecture Value:** Validates introspection, service provider, event subscriptions
- **Learning Value:** Advanced plugin demonstrating system-level APIs

### Features

- List all plugins with metrics
- Detailed plugin inspection
- Event bus monitoring
- Service registry inspection
- System health checks
- Real-time statistics
- Event subscription (wildcard)

## Commands

### `!inspect plugins`

List all loaded plugins with basic metrics.

**Example:**

```bash
!inspect plugins
📦 Loaded Plugins (5):

  ✅ dice_roller v1.0.0 (enabled)
     Commands: 1 | Uptime: 2h 15m
  
  ✅ quote_db v1.0.0 (enabled)
     Commands: 1 | Storage: Yes | Uptime: 2h 15m
  
  ✅ weather v1.0.0 (enabled)
     Commands: 2 | Services: 1 | Uptime: 2h 15m
  
  ✅ trivia v1.0.0 (enabled)
     Commands: 1 | Storage: Yes | Uptime: 2h 15m
  
  ✅ inspector v1.0.0 (enabled)
     Commands: 1 | Services: 1 | Uptime: 2h 15m
```

### `!inspect plugin <name>`

Show detailed information about a specific plugin.

**Example:**

```bash
!inspect plugin trivia
🔍 Plugin: trivia v1.0.0

Status: ✅ Enabled
Uptime: 2h 15m
Author: cytube-bot
Description: Interactive trivia game with scoring

Commands:
  !trivia (registered)

Storage:
  ✅ Using storage adapter
  Database: /data/trivia/trivia.db

Events Published:
  - trivia.game_started
  - trivia.question_asked
  - trivia.answer_submitted
  - trivia.game_finished

Events Subscribed:
  (none)

Services Provided:
  (none)

Services Consumed:
  (none)

Configuration:
  question_timeout: 30
  questions_per_game: 10
  fast_answer_bonus: 2

Health: ✅ Healthy
```

### `!inspect events`

Show event bus statistics and recent activity.

**Example:**

```bash
!inspect events
📡 Event Bus Statistics:

Total Events Published: 1,247
Total Events Dispatched: 3,741
Event Handlers: 15
Errors: 0

Recent Events (last 10):
  1. trivia.answer_submitted (5s ago)
     Handlers: 1 | Duration: 2ms
  
  2. trivia.question_asked (35s ago)
     Handlers: 1 | Duration: 1ms
  
  3. plugin.reloaded (2m ago)
     Handlers: 3 | Duration: 15ms

Event Patterns:
  trivia.* - 847 events (68%)
  plugin.* - 245 events (20%)
  channel.* - 155 events (12%)
```

### `!inspect services`

Show registered services in the service registry.

**Example:**

```bash
!inspect services
🔧 Registered Services (2):

  weather (WeatherService)
    Status: ✅ Started
    Provided by: weather v1.0.0
    Consumers: 0 plugins
    
  inspector (InspectorService)
    Status: ✅ Started
    Provided by: inspector v1.0.0
    Consumers: 0 plugins
```

### `!inspect health`

Perform system-wide health check.

**Example:**

```bash
!inspect health
🔍 System Health Check:

Overall Status: ✅ Healthy

Plugin System: ✅ Good
  - 5 plugins enabled
  - 0 plugins failed
  - 0 plugins disabled

Event Bus: ✅ Good
  - 1,247 events published
  - 0.0% error rate
  - Average handler time: 3ms

Service Registry: ✅ Good
  - 2 services started
  - 0 services stopped

System Uptime: 2h 15m
Memory Usage: 145 MB
```

## Service Provider

The InspectorService can be used by other plugins:

```python
# In another plugin
inspector = self.get_service('inspector')
if inspector:
    metrics = inspector.get_plugin_metrics('trivia')
    health = inspector.check_plugin_health('trivia')
```

**Service API:**

- `get_plugin_metrics(plugin_name: str) -> Dict[str, Any]`
- `get_event_bus_stats() -> Dict[str, Any]`
- `get_service_registry_info() -> Dict[str, Any]`
- `check_plugin_health(plugin_name: str) -> Dict[str, Any]`
- `get_system_health() -> Dict[str, Any]`

## Implementation

### File Structure

```
plugins/inspector/
├── __init__.py
├── plugin.py
└── service.py
```

### Code: `plugins/inspector/__init__.py`

```python
"""Plugin inspector for cytube-bot."""

from .plugin import InspectorPlugin
from .service import InspectorService

__all__ = ['InspectorPlugin', 'InspectorService']
```

### Code: `plugins/inspector/service.py`

```python
"""
Inspector Service

Provides programmatic access to system introspection data.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


class InspectorService:
    """Service for system introspection."""
    
    def __init__(self, plugin_manager):
        """Initialize inspector service."""
        self.plugin_manager = plugin_manager
        self.start_time = datetime.now()
    
    def get_plugin_metrics(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
        
        Returns:
            Metrics dict or None if plugin not found
        """
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return None
        
        # Get plugin info
        uptime = self._get_uptime(plugin)
        command_count = len(plugin.commands) if hasattr(plugin, 'commands') else 0
        
        return {
            'name': plugin.name,
            'version': plugin.version,
            'state': plugin.state,
            'uptime': uptime,
            'command_count': command_count,
            'has_storage': hasattr(plugin, 'db') and plugin.db is not None,
            'provides_services': len(plugin.provided_services) if hasattr(plugin, 'provided_services') else 0,
            'event_subscriptions': self._count_event_subscriptions(plugin),
            'event_publications': self._count_event_publications(plugin)
        }
    
    def get_event_bus_stats(self) -> Dict[str, Any]:
        """
        Get event bus statistics.
        
        Returns:
            Event bus stats dict
        """
        event_bus = self.plugin_manager.event_bus
        
        return {
            'total_published': event_bus.total_published,
            'total_dispatched': event_bus.total_dispatched,
            'total_errors': event_bus.total_errors,
            'handler_count': len(event_bus.handlers),
            'recent_events': self._get_recent_events(event_bus, limit=10),
            'event_patterns': self._get_event_patterns(event_bus)
        }
    
    def get_service_registry_info(self) -> Dict[str, Any]:
        """
        Get service registry information.
        
        Returns:
            Service registry info dict
        """
        service_registry = self.plugin_manager.service_registry
        
        services = []
        for name, service_info in service_registry.services.items():
            services.append({
                'name': name,
                'type': type(service_info['instance']).__name__,
                'status': service_info['status'],
                'provider': service_info['provider'].name,
                'version': service_info['version']
            })
        
        return {
            'service_count': len(services),
            'services': services
        }
    
    def check_plugin_health(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Check health of a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
        
        Returns:
            Health check result or None if plugin not found
        """
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return None
        
        issues = []
        
        # Check if plugin is enabled
        if plugin.state != 'enabled':
            issues.append(f"Plugin is {plugin.state}")
        
        # Check if commands are registered
        if hasattr(plugin, 'commands') and not plugin.commands:
            issues.append("No commands registered")
        
        # Check if storage is accessible
        if hasattr(plugin, 'db') and plugin.db is None:
            issues.append("Storage not initialized")
        
        # Check if services are running
        if hasattr(plugin, 'provided_services'):
            for service_name, service in plugin.provided_services.items():
                if not service.is_running():
                    issues.append(f"Service '{service_name}' not running")
        
        return {
            'plugin': plugin_name,
            'healthy': len(issues) == 0,
            'status': 'healthy' if len(issues) == 0 else 'unhealthy',
            'issues': issues
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health.
        
        Returns:
            System health summary
        """
        # Plugin health
        all_plugins = self.plugin_manager.get_all_plugins()
        enabled_count = sum(1 for p in all_plugins if p.state == 'enabled')
        failed_count = sum(1 for p in all_plugins if p.state == 'failed')
        
        # Event bus health
        event_bus = self.plugin_manager.event_bus
        error_rate = (event_bus.total_errors / event_bus.total_published * 100) if event_bus.total_published > 0 else 0
        
        # Service registry health
        service_registry = self.plugin_manager.service_registry
        started_services = sum(1 for s in service_registry.services.values() if s['status'] == 'started')
        stopped_services = sum(1 for s in service_registry.services.values() if s['status'] == 'stopped')
        
        # Overall status
        status = 'healthy'
        if failed_count > 0 or error_rate > 5.0 or stopped_services > 0:
            status = 'degraded'
        if failed_count > len(all_plugins) / 2:
            status = 'unhealthy'
        
        return {
            'status': status,
            'plugin_system': {
                'status': 'good' if failed_count == 0 else 'degraded',
                'enabled': enabled_count,
                'failed': failed_count,
                'total': len(all_plugins)
            },
            'event_bus': {
                'status': 'good' if error_rate < 1.0 else 'degraded',
                'total_events': event_bus.total_published,
                'error_rate': error_rate
            },
            'service_registry': {
                'status': 'good' if stopped_services == 0 else 'degraded',
                'started': started_services,
                'stopped': stopped_services
            },
            'uptime': (datetime.now() - self.start_time).total_seconds()
        }
    
    def _get_uptime(self, plugin) -> int:
        """Get plugin uptime in seconds."""
        if hasattr(plugin, 'start_time'):
            return (datetime.now() - plugin.start_time).total_seconds()
        return 0
    
    def _count_event_subscriptions(self, plugin) -> int:
        """Count event subscriptions for a plugin."""
        count = 0
        event_bus = self.plugin_manager.event_bus
        for handlers in event_bus.handlers.values():
            for handler in handlers:
                if handler['plugin'] == plugin:
                    count += 1
        return count
    
    def _count_event_publications(self, plugin) -> int:
        """Count event publications by a plugin."""
        # This would require tracking in event bus
        return 0
    
    def _get_recent_events(self, event_bus, limit: int) -> List[Dict[str, Any]]:
        """Get recent events from event bus."""
        if not hasattr(event_bus, 'recent_events'):
            return []
        
        return event_bus.recent_events[-limit:]
    
    def _get_event_patterns(self, event_bus) -> Dict[str, int]:
        """Get event patterns (grouped by prefix)."""
        if not hasattr(event_bus, 'event_counts'):
            return {}
        
        patterns = {}
        for event_name, count in event_bus.event_counts.items():
            prefix = event_name.split('.')[0] + '.*'
            patterns[prefix] = patterns.get(prefix, 0) + count
        
        return patterns
```

### Code: `plugins/inspector/plugin.py`

```python
"""
Inspector Plugin

Provides commands for system introspection and monitoring.
"""

from typing import Optional
from datetime import timedelta

from lib.plugin import Plugin
from lib.channel import Channel
from lib.user import User
from .service import InspectorService


class InspectorPlugin(Plugin):
    """Plugin for system introspection."""
    
    def __init__(self, manager):
        """Initialize the inspector plugin."""
        super().__init__(manager)
        self.name = "inspector"
        self.version = "1.0.0"
        self.description = "System introspection and monitoring"
        self.author = "cytube-bot"
        
        self.service: Optional[InspectorService] = None
    
    async def setup(self):
        """Set up the plugin."""
        # Create and provide service
        self.service = InspectorService(self.manager)
        await self.provide_service('inspector', self.service)
        
        # Register command
        await self.register_command('inspect', self._handle_inspect)
        
        # Subscribe to all events for monitoring
        await self.subscribe('*', self._on_any_event)
        
        self.logger.info(f"Inspector plugin loaded")
    
    async def teardown(self):
        """Clean up plugin resources."""
        self.service = None
        self.logger.info(f"Inspector plugin unloaded")
    
    async def _on_any_event(self, event_name: str, data: dict):
        """Handle all events (for monitoring)."""
        # Could log or collect metrics here
        pass
    
    async def _handle_inspect(self, channel: Channel, user: User, args: str):
        """Handle inspect commands."""
        if not args.strip():
            await self._show_help(channel)
            return
        
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""
        
        if subcommand == "plugins":
            await self._handle_plugins(channel)
        elif subcommand == "plugin":
            await self._handle_plugin(channel, subargs)
        elif subcommand == "events":
            await self._handle_events(channel)
        elif subcommand == "services":
            await self._handle_services(channel)
        elif subcommand == "health":
            await self._handle_health(channel)
        else:
            await channel.send_message(f"❌ Unknown subcommand: {subcommand}")
            await self._show_help(channel)
    
    async def _handle_plugins(self, channel: Channel):
        """List all plugins."""
        plugins = self.manager.get_all_plugins()
        
        await channel.send_message(f"📦 Loaded Plugins ({len(plugins)}):")
        await channel.send_message("")
        
        for plugin in plugins:
            metrics = self.service.get_plugin_metrics(plugin.name)
            if not metrics:
                continue
            
            status_icon = "✅" if plugin.state == "enabled" else "❌"
            
            info_parts = []
            if metrics['command_count'] > 0:
                info_parts.append(f"Commands: {metrics['command_count']}")
            if metrics['has_storage']:
                info_parts.append("Storage: Yes")
            if metrics['provides_services'] > 0:
                info_parts.append(f"Services: {metrics['provides_services']}")
            
            uptime_str = self._format_uptime(metrics['uptime'])
            info_parts.append(f"Uptime: {uptime_str}")
            
            info = " | ".join(info_parts)
            
            await channel.send_message(f"  {status_icon} {plugin.name} v{plugin.version} ({plugin.state})")
            await channel.send_message(f"     {info}")
            await channel.send_message("")
    
    async def _handle_plugin(self, channel: Channel, name: str):
        """Show detailed plugin info."""
        if not name.strip():
            await channel.send_message("❌ Please provide a plugin name")
            return
        
        plugin = self.manager.get_plugin(name.strip())
        if not plugin:
            await channel.send_message(f"❌ Plugin not found: {name}")
            return
        
        metrics = self.service.get_plugin_metrics(plugin.name)
        health = self.service.check_plugin_health(plugin.name)
        
        # Header
        await channel.send_message(f"🔍 Plugin: {plugin.name} v{plugin.version}")
        await channel.send_message("")
        
        # Status
        status_icon = "✅" if plugin.state == "enabled" else "❌"
        uptime_str = self._format_uptime(metrics['uptime'])
        await channel.send_message(f"Status: {status_icon} {plugin.state.title()}")
        await channel.send_message(f"Uptime: {uptime_str}")
        await channel.send_message(f"Author: {plugin.author}")
        await channel.send_message(f"Description: {plugin.description}")
        await channel.send_message("")
        
        # Commands
        if metrics['command_count'] > 0:
            await channel.send_message("Commands:")
            if hasattr(plugin, 'commands'):
                for cmd in plugin.commands:
                    await channel.send_message(f"  !{cmd} (registered)")
            await channel.send_message("")
        
        # Storage
        if metrics['has_storage']:
            await channel.send_message("Storage:")
            await channel.send_message("  ✅ Using storage adapter")
            await channel.send_message("")
        
        # Events
        if metrics['event_subscriptions'] > 0:
            await channel.send_message(f"Event Subscriptions: {metrics['event_subscriptions']}")
            await channel.send_message("")
        
        # Services
        if metrics['provides_services'] > 0:
            await channel.send_message(f"Services Provided: {metrics['provides_services']}")
            await channel.send_message("")
        
        # Health
        health_icon = "✅" if health['healthy'] else "⚠️"
        await channel.send_message(f"Health: {health_icon} {health['status'].title()}")
        if health['issues']:
            for issue in health['issues']:
                await channel.send_message(f"  - {issue}")
    
    async def _handle_events(self, channel: Channel):
        """Show event bus statistics."""
        stats = self.service.get_event_bus_stats()
        
        await channel.send_message("📡 Event Bus Statistics:")
        await channel.send_message("")
        await channel.send_message(f"Total Events Published: {stats['total_published']:,}")
        await channel.send_message(f"Total Events Dispatched: {stats['total_dispatched']:,}")
        await channel.send_message(f"Event Handlers: {stats['handler_count']}")
        await channel.send_message(f"Errors: {stats['total_errors']}")
        await channel.send_message("")
        
        # Recent events
        if stats['recent_events']:
            await channel.send_message(f"Recent Events (last {len(stats['recent_events'])}):")
            for i, event in enumerate(stats['recent_events'], 1):
                await channel.send_message(f"  {i}. {event['name']} ({event['age']})")
            await channel.send_message("")
        
        # Event patterns
        if stats['event_patterns']:
            await channel.send_message("Event Patterns:")
            for pattern, count in sorted(stats['event_patterns'].items(), key=lambda x: x[1], reverse=True):
                percentage = count / stats['total_published'] * 100 if stats['total_published'] > 0 else 0
                await channel.send_message(f"  {pattern} - {count:,} events ({percentage:.0f}%)")
    
    async def _handle_services(self, channel: Channel):
        """Show registered services."""
        info = self.service.get_service_registry_info()
        
        await channel.send_message(f"🔧 Registered Services ({info['service_count']}):")
        await channel.send_message("")
        
        for service in info['services']:
            status_icon = "✅" if service['status'] == "started" else "⏸️"
            
            await channel.send_message(f"  {service['name']} ({service['type']})")
            await channel.send_message(f"    Status: {status_icon} {service['status'].title()}")
            await channel.send_message(f"    Provided by: {service['provider']} v{service['version']}")
            await channel.send_message("")
    
    async def _handle_health(self, channel: Channel):
        """Perform system health check."""
        health = self.service.get_system_health()
        
        # Overall status
        status_icon = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}[health['status']]
        await channel.send_message("🔍 System Health Check:")
        await channel.send_message("")
        await channel.send_message(f"Overall Status: {status_icon} {health['status'].title()}")
        await channel.send_message("")
        
        # Plugin system
        ps = health['plugin_system']
        ps_icon = "✅" if ps['status'] == "good" else "⚠️"
        await channel.send_message(f"Plugin System: {ps_icon} {ps['status'].title()}")
        await channel.send_message(f"  - {ps['enabled']} plugins enabled")
        await channel.send_message(f"  - {ps['failed']} plugins failed")
        await channel.send_message("")
        
        # Event bus
        eb = health['event_bus']
        eb_icon = "✅" if eb['status'] == "good" else "⚠️"
        await channel.send_message(f"Event Bus: {eb_icon} {eb['status'].title()}")
        await channel.send_message(f"  - {eb['total_events']:,} events published")
        await channel.send_message(f"  - {eb['error_rate']:.1f}% error rate")
        await channel.send_message("")
        
        # Service registry
        sr = health['service_registry']
        sr_icon = "✅" if sr['status'] == "good" else "⚠️"
        await channel.send_message(f"Service Registry: {sr_icon} {sr['status'].title()}")
        await channel.send_message(f"  - {sr['started']} services started")
        await channel.send_message("")
        
        # System uptime
        uptime_str = self._format_uptime(health['uptime'])
        await channel.send_message(f"System Uptime: {uptime_str}")
    
    async def _show_help(self, channel: Channel):
        """Show command help."""
        await channel.send_message("Inspector Commands:")
        await channel.send_message("  !inspect plugins - List all plugins")
        await channel.send_message("  !inspect plugin <name> - Show plugin details")
        await channel.send_message("  !inspect events - Show event bus stats")
        await channel.send_message("  !inspect services - Show registered services")
        await channel.send_message("  !inspect health - System health check")
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        delta = timedelta(seconds=int(seconds))
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)
```

## Testing Strategy

### Unit Tests

```python
"""Tests for inspector plugin."""

import pytest
from plugins.inspector.service import InspectorService


def test_get_plugin_metrics(plugin_manager):
    """Test getting plugin metrics."""
    service = InspectorService(plugin_manager)
    
    # Add mock plugin
    mock_plugin = create_mock_plugin('test_plugin')
    plugin_manager.add_plugin(mock_plugin)
    
    metrics = service.get_plugin_metrics('test_plugin')
    
    assert metrics is not None
    assert metrics['name'] == 'test_plugin'
    assert 'uptime' in metrics


def test_system_health(plugin_manager):
    """Test system health check."""
    service = InspectorService(plugin_manager)
    
    health = service.get_system_health()
    
    assert health['status'] in ['healthy', 'degraded', 'unhealthy']
    assert 'plugin_system' in health
    assert 'event_bus' in health
```

### Integration Tests

```python
"""Integration tests for inspector plugin."""

import pytest


@pytest.mark.asyncio
async def test_inspect_plugins(bot, channel):
    """Test listing plugins."""
    await channel.send_chat("!inspect plugins")
    
    response = await channel.wait_for_message(timeout=2.0)
    assert "Loaded Plugins" in response
```

## Architecture Validation

This plugin validates:

- ✅ **Service provider:** Provides InspectorService
- ✅ **System introspection:** Access to plugin manager internals
- ✅ **Event monitoring:** Wildcard event subscription
- ✅ **Health checks:** Plugin and system health validation
- ✅ **Metrics collection:** Real-time statistics

---

**Estimated Implementation:** 4 hours  
**Lines of Code:** ~600 (300 service + 300 plugin)  
**External Dependencies:** None  
**Architecture Features Validated:** 5/16

🔍 **Operational Excellence - Essential for production monitoring!**
