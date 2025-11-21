"""
lib/plugin/base.py

Abstract plugin base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
import logging
from .metadata import PluginMetadata
from .errors import PluginError
from .event import Event, EventPriority


class Plugin(ABC):
    """
    Abstract base class for bot plugins.
    
    Plugins extend bot functionality with modular, reloadable code.
    All plugins must inherit from this class and implement required methods.
    
    Lifecycle:
        1. __init__() - Construct plugin (fast, no I/O)
        2. setup() - Initialize plugin (async, can do I/O)
        3. on_enable() - Called when plugin enabled
        4. [plugin runs, handles events]
        5. on_disable() - Called when plugin disabled
        6. teardown() - Cleanup plugin (async)
    
    Attributes:
        bot: Bot instance (access to send_message, channel, etc.)
        config: Plugin configuration dict
        logger: Logger instance for this plugin
        is_enabled: Whether plugin is currently enabled
        
    Example:
        class MyPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name='my_plugin',
                    display_name='My Plugin',
                    version='1.0.0',
                    description='Does something cool',
                    author='Me'
                )
            
            async def setup(self):
                self.on('message', self.handle_message)
            
            async def handle_message(self, event, data):
                if not self.is_enabled:
                    return
                message = data.get('content', '')
                if message.startswith('!hello'):
                    await self.send_message('Hello!')
    """
    
    def __init__(self, bot, config: Optional[Dict[str, Any]] = None):
        """
        Initialize plugin.
        
        IMPORTANT: This should be fast (no I/O, no blocking operations).
        Do heavy initialization in setup().
        
        Args:
            bot: Bot instance providing services and API
            config: Plugin configuration dict (from config file)
        """
        self.bot = bot
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.metadata.name}")
        self._is_enabled = False
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._event_subscriptions: List[str] = []  # Track subscriptions for cleanup
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """
        Plugin metadata (name, version, description, etc.).
        
        This should return a constant PluginMetadata instance.
        Do not compute this dynamically.
        
        Returns:
            PluginMetadata instance with plugin information
        
        Example:
            @property
            def metadata(self):
                return PluginMetadata(
                    name='dice_roller',
                    display_name='Dice Roller',
                    version='1.0.0',
                    description='Roll dice with !roll command',
                    author='YourName'
                )
        """
    
    @property
    def is_enabled(self) -> bool:
        """Check if plugin is currently enabled."""
        return self._is_enabled
    
    @property
    def storage(self):
        """
        Access bot's storage adapter (may be None).
        
        Returns:
            StorageAdapter instance or None if database disabled
        """
        return getattr(self.bot, 'storage', None)
    
    @property
    def event_bus(self):
        """
        Access event bus for inter-plugin communication.
        
        Returns:
            EventBus instance from plugin manager
        
        Example:
            # Subscribe to events
            self.subscribe('trivia.started', self.on_trivia)
            
            # Publish events
            await self.publish('quote.added', {'quote': 'Hello!', 'author': 'Alice'})
        """
        if hasattr(self.bot, 'plugin_manager'):
            return self.bot.plugin_manager.event_bus
        return None
    
    # =================================================================
    # Lifecycle Hooks
    # =================================================================
    
    async def setup(self) -> None:
        """
        Initialize plugin (called once on load).
        
        Use this for:
        - Validating configuration
        - Creating database tables
        - Loading persistent state
        - Registering event handlers
        - Starting background tasks
        
        This is called once when plugin is first loaded.
        If this raises an exception, the plugin will not be loaded.
        
        Raises:
            PluginError: If setup fails (plugin will not load)
        """
    
    async def teardown(self) -> None:
        """
        Cleanup plugin (called once on unload).
        
        Use this for:
        - Saving persistent state
        - Closing connections
        - Canceling background tasks
        - Releasing resources
        
        This is called once when plugin is unloaded.
        Should not raise exceptions (best effort cleanup).
        Always runs even if plugin crashes.
        """
        # Auto-unsubscribe from all event bus subscriptions
        if self.event_bus:
            for pattern in self._event_subscriptions:
                self.event_bus.unsubscribe(pattern, self.metadata.name)
            self._event_subscriptions.clear()
    
    async def on_enable(self) -> None:
        """
        Called when plugin is enabled.
        
        Use this for:
        - Re-registering event handlers (if needed)
        - Resuming background tasks
        - Logging enable event
        
        Called after setup() on initial load.
        Also called when user manually enables a disabled plugin.
        """
        self._is_enabled = True
        self.logger.info(f"{self.metadata.display_name} enabled")
    
    async def on_disable(self) -> None:
        """
        Called when plugin is disabled.
        
        Use this for:
        - Unregistering event handlers (optional)
        - Pausing background tasks
        - Logging disable event
        
        Called when user manually disables the plugin.
        Plugin remains loaded but inactive (is_enabled = False).
        Event handlers should check is_enabled before processing.
        """
        self._is_enabled = False
        self.logger.info(f"{self.metadata.display_name} disabled")
    
    # =================================================================
    # Event Registration
    # =================================================================
    
    def on(self, event_name: str, handler: Callable) -> None:
        """
        Register event handler.
        
        Handlers are called when the bot triggers the event.
        Multiple handlers can be registered for the same event.
        
        Args:
            event_name: Event name ('message', 'user_join', 'user_leave', etc.)
            handler: Async function to call: async def handler(event, data)
        
        Example:
            self.on('message', self.handle_message)
            self.on('user_join', self.handle_user_join)
        """
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
        self.logger.debug(f"Registered handler for '{event_name}'")
    
    def on_message(self, handler: Callable) -> Callable:
        """
        Decorator to register message handler.
        
        Handler signature: async def handler(event, data)
        
        Data contains:
            - user: Username
            - content: Message text
            - timestamp: Message time
            - platform_data: Platform-specific fields
        
        Example:
            @plugin.on_message
            async def handle_message(self, event, data):
                username = data.get('user', '')
                message = data.get('content', '')
                if message.startswith('!hello'):
                    await self.send_message(f'Hello {username}!')
        
        Returns:
            The handler (for chaining)
        """
        self.on('message', handler)
        return handler
    
    def on_user_join(self, handler: Callable) -> Callable:
        """
        Decorator to register user join handler.
        
        Handler signature: async def handler(event, data)
        
        Data contains:
            - user: Username
            - platform_data: Platform-specific user info
        """
        self.on('user_join', handler)
        return handler
    
    def on_user_leave(self, handler: Callable) -> Callable:
        """
        Decorator to register user leave handler.
        
        Handler signature: async def handler(event, data)
        
        Data contains:
            - user: Username
        """
        self.on('user_leave', handler)
        return handler
    
    def on_command(self, command: str, handler: Callable) -> Callable:
        """
        Decorator to register command handler.
        
        Automatically parses commands starting with ! prefix.
        
        Args:
            command: Command name (without ! prefix)
            handler: Async function(username, args) to call
        
        Handler signature: async def handler(username: str, args: List[str])
        
        Example:
            @plugin.on_command('roll')
            async def handle_roll(self, username, args):
                # Handle !roll 2d6 command
                dice = args[0] if args else '1d6'
                result = roll_dice(dice)
                await self.send_message(f'{username} rolled {result}')
        
        Returns:
            The handler (for chaining)
        """
        async def wrapper(event, data):
            if not self.is_enabled:
                return
            
            message = data.get('content', '')
            if message.startswith(f'!{command}'):
                username = data.get('user', '')
                # Parse arguments (everything after command)
                parts = message.split(maxsplit=1)
                args = parts[1].split() if len(parts) > 1 else []
                await handler(username, args)
        
        self.on('message', wrapper)
        return handler
    
    # =================================================================
    # Inter-Plugin Communication (Event Bus)
    # =================================================================
    
    def subscribe(self, event_pattern: str, handler: Callable) -> None:
        """
        Subscribe to event bus events matching pattern.
        
        Enables inter-plugin communication via pub/sub.
        Automatically unsubscribed when plugin is torn down.
        
        Args:
            event_pattern: Event name or pattern (supports * wildcard)
            handler: Async function(event) to call
        
        Examples:
            # Subscribe to specific event
            self.subscribe('trivia.started', self.on_trivia_start)
            
            # Subscribe to all trivia events
            self.subscribe('trivia.*', self.on_trivia_event)
            
            # Subscribe to all events
            self.subscribe('*', self.on_any_event)
        """
        if not self.event_bus:
            self.logger.warning("Event bus not available")
            return
        
        self.event_bus.subscribe(event_pattern, handler, self.metadata.name)
        self._event_subscriptions.append(event_pattern)
    
    async def publish(
        self,
        event_name: str,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """
        Publish event to event bus.
        
        Other plugins can subscribe to these events for inter-plugin communication.
        
        Args:
            event_name: Event name (recommend: plugin.action format)
            data: Event data (any JSON-serializable dict)
            priority: Event priority (HIGH, NORMAL, or LOW)
        
        Examples:
            # Publish trivia started event
            await self.publish('trivia.started', {
                'question': 'What is 2+2?',
                'timeout': 30
            })
            
            # Publish high-priority event
            await self.publish('alert.critical', {
                'message': 'System overload!'
            }, priority=EventPriority.HIGH)
        """
        if not self.event_bus:
            self.logger.warning("Event bus not available")
            return
        
        event = Event(
            name=event_name,
            data=data,
            source=self.metadata.name,
            priority=priority,
        )
        await self.event_bus.publish(event)
    
    # =================================================================
    # Bot Interaction
    # =================================================================
    
    async def send_message(self, message: str) -> None:
        """
        Send message to channel.
        
        Convenience wrapper around bot.send_message().
        
        Args:
            message: Message text to send
        
        Example:
            await self.send_message('Hello from plugin!')
        """
        if hasattr(self.bot, 'send_message'):
            await self.bot.send_message(message)
        else:
            self.logger.warning("Bot does not support send_message()")
    
    # =================================================================
    # Configuration
    # =================================================================
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Supports dot notation for nested configuration.
        
        Args:
            key: Configuration key (supports 'nested.key' format)
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        
        Example:
            # Config: {'max_dice': 10, 'api': {'key': 'secret'}}
            max_dice = self.get_config('max_dice', 6)  # Returns 10
            api_key = self.get_config('api.key')  # Returns 'secret'
            timeout = self.get_config('timeout', 30)  # Returns 30 (default)
        """
        # Support dot notation for nested config
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def validate_config(self, required_keys: List[str]) -> None:
        """
        Validate that required configuration keys exist.
        
        Args:
            required_keys: List of required config keys (supports dot notation)
        
        Raises:
            PluginError: If any required key is missing
        
        Example:
            def setup(self):
                self.validate_config(['api_key', 'server.host'])
        """
        missing = []
        for key in required_keys:
            if self.get_config(key) is None:
                missing.append(key)
        
        if missing:
            raise PluginError(
                f"{self.metadata.display_name}: Missing required config keys: "
                f"{', '.join(missing)}"
            )
    
    # =================================================================
    # Service Registry
    # =================================================================
    
    @property
    def services(self):
        """
        Access service registry for dependency injection.
        
        Returns:
            ServiceRegistry instance from plugin manager or None
        
        Example:
            # Check if service available
            if self.services.has('weather'):
                weather = self.services.get('weather')
        """
        if hasattr(self.bot, 'plugin_manager'):
            return self.bot.plugin_manager.service_registry
        return None
    
    def provide_service(self, service, dependencies: Optional[Dict[str, str]] = None) -> None:
        """
        Register a service with the service registry.
        
        Args:
            service: Service instance to provide (must inherit from Service ABC)
            dependencies: Optional mapping of required service names to minimum versions
        
        Raises:
            PluginError: If service registry not available
            PluginError: If service name already registered
        
        Example:
            class WeatherService(Service):
                @property
                def service_name(self) -> str:
                    return "weather"
                
                @property
                def service_version(self) -> str:
                    return "1.0.0"
                
                def get_weather(self, location: str) -> dict:
                    return {"temp": 72, "condition": "sunny"}
            
            # In plugin setup()
            weather = WeatherService()
            self.provide_service(weather)
        """
        if not self.services:
            raise PluginError(
                f"{self.metadata.display_name}: Service registry not available"
            )
        
        self.services.register(
            service,
            provider=self.metadata.name,
            dependencies=dependencies
        )
        self.logger.info(
            f"Provided service '{service.service_name}' v{service.service_version}"
        )
    
    def get_service(self, service_name: str, min_version: Optional[str] = None):
        """
        Get a service from the service registry.
        
        Args:
            service_name: Name of the service to retrieve
            min_version: Optional minimum version requirement
        
        Returns:
            Service instance if found and version compatible, None otherwise
        
        Example:
            # Get service if available
            weather = self.get_service('weather', min_version='1.0.0')
            if weather:
                data = weather.get_weather('Seattle')
        """
        if not self.services:
            self.logger.warning("Service registry not available")
            return None
        
        return self.services.get(service_name, min_version)
    
    def require_service(self, service_name: str, min_version: Optional[str] = None):
        """
        Get a service from the registry, raising error if not available.
        
        Args:
            service_name: Name of the service to retrieve
            min_version: Optional minimum version requirement
        
        Returns:
            Service instance
        
        Raises:
            PluginError: If service registry not available
            PluginError: If service not registered or version incompatible
        
        Example:
            # Require service (raises error if unavailable)
            weather = self.require_service('weather', min_version='1.0.0')
            data = weather.get_weather('Seattle')
        """
        if not self.services:
            raise PluginError(
                f"{self.metadata.display_name}: Service registry not available"
            )
        
        return self.services.require(service_name, min_version)
    
    # =================================================================
    # Utility
    # =================================================================
    
    def __str__(self) -> str:
        """String representation for logs."""
        return str(self.metadata)
    
    def __repr__(self) -> str:
        """Developer representation."""
        status = "enabled" if self.is_enabled else "disabled"
        return f"<{self.metadata.name} v{self.metadata.version} ({status})>"
