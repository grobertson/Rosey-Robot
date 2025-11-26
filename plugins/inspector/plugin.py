from datetime import datetime
import json
import logging
from .buffer import EventBuffer, CapturedEvent
from .filters import FilterChain
from .service import InspectorService


class InspectorPlugin:
    """
    Plugin inspector for runtime observability.
    
    Commands (admin only):
        !inspect events [pattern] - Show recent events
        !inspect plugins - List loaded plugins
        !inspect plugin <name> - Show plugin details
        !inspect stats - Show event statistics
        !inspect pause - Pause event capturing
        !inspect resume - Resume event capturing
    """
    
    NAMESPACE = "inspector"
    VERSION = "1.0.0"
    DESCRIPTION = "Runtime inspection and debugging"
    
    # NATS subjects - Commands
    SUBJECT_EVENTS = "rosey.command.inspect.events"
    SUBJECT_PLUGINS = "rosey.command.inspect.plugins"
    SUBJECT_PLUGIN = "rosey.command.inspect.plugin"
    SUBJECT_STATS = "rosey.command.inspect.stats"
    SUBJECT_PAUSE = "rosey.command.inspect.pause"
    SUBJECT_RESUME = "rosey.command.inspect.resume"
    
    def __init__(self, nats_client, config: dict = None, plugin_manager=None):
        """
        Initialize inspector plugin.
        
        Args:
            nats_client: NATS client instance
            config: Plugin configuration dict
            plugin_manager: Optional plugin manager for introspection
        """
        self.nc = nats_client
        self.config = config or {}
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger(f"{__name__}.{self.NAMESPACE}")
        
        # Initialize buffer and filter
        buffer_size = self.config.get("buffer_size", 1000)
        self.buffer = EventBuffer(max_size=buffer_size)
        
        self.filter_chain = FilterChain(
            include=self.config.get("include_patterns"),
            exclude=self.config.get("exclude_patterns", [
                "_INBOX.*",  # NATS internal
                "inspector.*",  # Avoid self-reference
            ]),
        )
        
        # Initialize service
        self.service = InspectorService(self.buffer, self.filter_chain)
        
        # Track subscriptions
        self._subscriptions = []
        self._initialized = False
    
    async def initialize(self) -> None:
        """Register handlers and start wildcard subscription."""
        if self._initialized:
            return
        
        # Subscribe to ALL events with wildcard
        sub = await self.nc.subscribe(">", cb=self._capture_event)
        self._subscriptions.append(sub)
        
        # Register command handlers
        sub = await self.nc.subscribe(self.SUBJECT_EVENTS, cb=self._handle_events)
        self._subscriptions.append(sub)
        
        sub = await self.nc.subscribe(self.SUBJECT_PLUGINS, cb=self._handle_plugins)
        self._subscriptions.append(sub)
        
        sub = await self.nc.subscribe(self.SUBJECT_PLUGIN, cb=self._handle_plugin)
        self._subscriptions.append(sub)
        
        sub = await self.nc.subscribe(self.SUBJECT_STATS, cb=self._handle_stats)
        self._subscriptions.append(sub)
        
        sub = await self.nc.subscribe(self.SUBJECT_PAUSE, cb=self._handle_pause)
        self._subscriptions.append(sub)
        
        sub = await self.nc.subscribe(self.SUBJECT_RESUME, cb=self._handle_resume)
        self._subscriptions.append(sub)
        
        self._initialized = True
        self.logger.info(f"{self.NAMESPACE} plugin initialized")
    
    async def shutdown(self) -> None:
        """Cleanup."""
        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.warning(f"Error unsubscribing: {e}")
        
        self._subscriptions.clear()
        self.buffer.clear()
        self._initialized = False
        self.logger.info(f"{self.NAMESPACE} plugin shutdown")
    
    async def _capture_event(self, msg) -> None:
        """Capture incoming event (wildcard handler)."""
        if self.service.is_paused:
            return
        
        if not self.filter_chain.should_capture(msg.subject):
            return
        
        event = CapturedEvent(
            timestamp=datetime.utcnow(),
            subject=msg.subject,
            data=msg.data,
            size_bytes=len(msg.data),
        )
        
        self.buffer.append(event)
        self.service._notify_subscribers(event)
    
    async def _handle_events(self, msg) -> None:
        """Handle !inspect events [pattern]."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        pattern = data.get("args", "").strip() or None
        count = self.config.get("default_event_count", 10)
        
        events = self.buffer.get_recent(count, pattern)
        
        if not events:
            pattern_msg = f" matching '{pattern}'" if pattern else ""
            return await self._reply(msg, {"success": True, "result": {"message": f"📡 No recent events{pattern_msg}"}})
        
        lines = [f"📡 Last {len(events)} events" + (f" matching '{pattern}':" if pattern else ":")]
        
        for event in events:
            time_str = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            lines.append(f"\n[{time_str}] {event.subject} ({event.size_bytes}B)")
            lines.append(f"  {event.preview}")
        
        await self._reply(msg, {"success": True, "result": {"message": "\n".join(lines)}})
    
    async def _handle_plugins(self, msg) -> None:
        """Handle !inspect plugins."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        if not self.plugin_manager:
            return await self._reply_error(msg, "Plugin manager not available")
        
        plugins = self.plugin_manager.get_loaded_plugins()
        
        if not plugins:
            return await self._reply(msg, {"success": True, "result": {"message": "🔌 No plugins loaded"}})
        
        lines = ["🔌 Loaded Plugins:\n"]
        
        for plugin in plugins:
            status = "active" if getattr(plugin, "_initialized", False) else "inactive"
            subs = len(getattr(plugin, "_subscriptions", []))
            lines.append(f"• {plugin.NAMESPACE} v{plugin.VERSION} ({status}) - {subs} subs")
        
        await self._reply(msg, {"success": True, "result": {"message": "\n".join(lines)}})
    
    async def _handle_plugin(self, msg) -> None:
        """Handle !inspect plugin <name>."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        name = data.get("args", "").strip()
        if not name:
            return await self._reply_error(msg, "Usage: !inspect plugin <name>")
        
        if not self.plugin_manager:
            return await self._reply_error(msg, "Plugin manager not available")
        
        plugin = self.plugin_manager.get_plugin(name)
        if not plugin:
            return await self._reply_error(msg, f"Plugin '{name}' not found")
        
        lines = [f"🔌 Plugin: {plugin.NAMESPACE}\n"]
        lines.append(f"• Version: {plugin.VERSION}")
        lines.append(f"• Description: {plugin.DESCRIPTION}")
        status = "active" if getattr(plugin, "_initialized", False) else "inactive"
        lines.append(f"• Status: {status}")
        
        subs = getattr(plugin, "_subscriptions", [])
        if subs:
            lines.append(f"\n📡 Subscriptions ({len(subs)}):")
            for i, sub in enumerate(subs[:10], 1):  # Limit to 10
                subject = getattr(sub, "subject", "unknown")
                lines.append(f"  {i}. {subject}")
            if len(subs) > 10:
                lines.append(f"  ... and {len(subs) - 10} more")
        
        await self._reply(msg, {"success": True, "result": {"message": "\n".join(lines)}})
    
    async def _handle_stats(self, msg) -> None:
        """Handle !inspect stats."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        stats = self.buffer.get_stats()
        
        lines = ["📊 Inspector Stats:\n"]
        lines.append(f"• Total Events: {stats['total_events']:,}")
        lines.append(f"• Buffer: {stats['buffer_used']}/{stats['buffer_size']}")
        lines.append(f"• Status: {'PAUSED' if self.service.is_paused else 'Active'}")
        
        if stats["top_subjects"]:
            lines.append("\n📈 Top Subjects:")
            for item in stats["top_subjects"][:5]:
                lines.append(f"  • {item['subject']}: {item['count']:,}")
        
        await self._reply(msg, {"success": True, "result": {"message": "\n".join(lines)}})
    
    async def _handle_pause(self, msg) -> None:
        """Handle !inspect pause."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        self.service.pause()
        await self._reply(msg, {"success": True, "result": {"message": "📡 Event capturing paused"}})
    
    async def _handle_resume(self, msg) -> None:
        """Handle !inspect resume."""
        data = json.loads(msg.data.decode())
        
        if not await self._check_admin(data["user"]):
            return await self._reply_error(msg, "Admin only command")
        
        self.service.resume()
        await self._reply(msg, {"success": True, "result": {"message": "📡 Event capturing resumed"}})
    
    async def _check_admin(self, user: str) -> bool:
        """Check if user is an admin."""
        admins = self.config.get("admins", [])
        return user in admins or not admins  # If no admins configured, allow all
    
    async def _reply(self, msg, response_dict: dict) -> None:
        """Reply to a NATS message."""
        if msg.reply:
            await self.nc.publish(msg.reply, json.dumps(response_dict).encode())
    
    async def _reply_error(self, msg, error_message: str) -> None:
        """Reply with error."""
        await self._reply(msg, {"success": False, "error": error_message})
