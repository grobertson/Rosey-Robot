"""
plugins/example_plugin.py

DEPRECATION NOTICE
==================
This example plugin is DEPRECATED and uses an outdated architecture.

Rosey plugins now use a NATS-based architecture where each plugin:
- Runs as a separate process
- Communicates entirely via NATS messaging
- Does NOT inherit from any base class

For new plugin development, see:
- plugins/dice-roller/ - Simple stateless plugin example
- plugins/quote-db/ - Reference implementation with storage
- docs/NATS_MESSAGES.md - NATS message formats
- docs/ARCHITECTURE.md - Plugin architecture overview
==================

Example plugin demonstrating plugin system features.

This plugin shows:
- Lifecycle hooks (setup, teardown, enable, disable)
- Event registration (message, user_join, user_leave)
- Command handling with @on_command decorator
- Configuration access
- Bot interaction (sending messages)
- Logging
"""

import warnings

warnings.warn(
    "example_plugin.py is deprecated. "
    "See plugins/dice-roller/ for the correct NATS-based architecture.",
    DeprecationWarning,
    stacklevel=2,
)

from lib.plugin import Plugin, PluginMetadata


class ExamplePlugin(Plugin):
    """
    Example plugin that responds to commands and events.

    Commands:
        !hello [name] - Say hello
        !goodbye - Say goodbye
        !status - Show plugin status

    Configuration:
        greeting: Custom greeting message (default: "Hello")
        max_greetings: Maximum greetings per minute (default: 10)
    """

    @property
    def metadata(self):
        """Plugin metadata."""
        return PluginMetadata(
            name='example_plugin',
            display_name='Example Plugin',
            version='1.0.0',
            description='Demonstrates plugin features',
            author='Rosey-Robot Team',
            dependencies=[],
            min_bot_version='0.9.0'
        )

    async def setup(self):
        """
        Initialize plugin.

        Register event handlers and validate configuration.
        """
        self.logger.info("Setting up example plugin")

        # Validate configuration (optional)
        # self.validate_config(['required_key'])

        # Load configuration with defaults
        self.greeting = self.get_config('greeting', 'Hello')
        self.max_greetings = self.get_config('max_greetings', 10)
        self.greeting_count = 0

        # Register event handlers
        self.on('message', self.handle_message)
        self.on('user_join', self.handle_user_join)
        self.on('user_leave', self.handle_user_leave)

        # Or use decorators (can't use self.on_command in setup though)
        # Decorators are better used at class level

        self.logger.info(f"Example plugin initialized with greeting: {self.greeting}")

    async def teardown(self):
        """Cleanup plugin."""
        self.logger.info(f"Example plugin shutting down. Sent {self.greeting_count} greetings")

    async def on_enable(self):
        """Called when plugin is enabled."""
        await super().on_enable()
        await self.send_message("🟢 Example plugin is now enabled!")

    async def on_disable(self):
        """Called when plugin is disabled."""
        await super().on_disable()
        await self.send_message("🔴 Example plugin is now disabled")

    # =================================================================
    # Event Handlers
    # =================================================================

    async def handle_message(self, event, data):
        """
        Handle incoming messages.

        Check for commands and respond accordingly.
        """
        if not self.is_enabled:
            return

        message = data.get('content', '')
        username = data.get('user', '')

        # Handle !hello command
        if message.startswith('!hello'):
            await self.handle_hello(username, message)

        # Handle !goodbye command
        elif message.startswith('!goodbye'):
            await self.handle_goodbye(username)

        # Handle !status command
        elif message.startswith('!status'):
            await self.handle_status()

        # Log all messages (example of passive monitoring)
        self.logger.debug(f"Message from {username}: {message[:50]}...")

    async def handle_user_join(self, event, data):
        """Handle user joining channel."""
        if not self.is_enabled:
            return

        username = data.get('user', '')
        self.logger.info(f"User joined: {username}")

        # Optionally greet new users
        # await self.send_message(f"Welcome {username}!")

    async def handle_user_leave(self, event, data):
        """Handle user leaving channel."""
        if not self.is_enabled:
            return

        username = data.get('user', '')
        self.logger.info(f"User left: {username}")

    # =================================================================
    # Command Handlers
    # =================================================================

    async def handle_hello(self, username: str, message: str):
        """
        Handle !hello command.

        Usage: !hello [name]
        """
        # Check rate limit
        if self.greeting_count >= self.max_greetings:
            await self.send_message("⚠️ Too many greetings! Try again later.")
            return

        # Parse optional name argument
        parts = message.split(maxsplit=1)
        target = parts[1] if len(parts) > 1 else username

        # Send greeting
        await self.send_message(f"{self.greeting} {target}!")
        self.greeting_count += 1

        self.logger.info(f"{username} greeted {target} (count: {self.greeting_count})")

    async def handle_goodbye(self, username: str):
        """
        Handle !goodbye command.

        Usage: !goodbye
        """
        await self.send_message(f"Goodbye {username}! 👋")
        self.logger.info(f"{username} said goodbye")

    async def handle_status(self):
        """
        Handle !status command.

        Show plugin status and statistics.
        """
        status = "enabled ✅" if self.is_enabled else "disabled ❌"
        await self.send_message(
            f"📊 {self.metadata.display_name} v{self.metadata.version} - {status}\n"
            f"Greetings sent: {self.greeting_count}/{self.max_greetings}"
        )


# Export plugin class (required)
__plugin__ = ExamplePlugin
