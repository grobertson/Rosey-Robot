#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rosey - A feature-rich CyTube bot with logging, pm control, and database tracking.

Rosey is the main bot application that provides:
- Chat and media logging
- Database tracking of users and statistics
- PM command interface for channel and bot management

"""

import sys
from pathlib import Path
import logging
import asyncio
from functools import partial
from time import localtime, strftime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common import Shell, get_config, configure_logger
from common.database import BotDatabase
from lib.error import CytubeError, SocketIOError
from lib import Bot

# LLM imports (optional)
try:
    from lib.llm import LLMClient
    from lib.llm.triggers import TriggerConfig, TriggerManager
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

def log_chat(logger, event, data):
    """Log a chat message or private message to the chat log

    Args:
        logger: Logger instance to write to
        event: Event name ('message' or 'pm')
        data: Event data dictionary containing time, user, content, etc.
    """
    # Extract timestamp (milliseconds since epoch) and convert to local time
    # For normalized events, get from timestamp field or platform_data
    time_ms = data.get("timestamp", data.get("platform_data", {}).get("time", 0))
    time = strftime("%d/%m/%Y %H:%m:%S", localtime(time_ms // 1000))

    # Extract username and message - normalized events use 'user' and 'content'
    user = data.get("user", data.get("username", "<no username>"))
    msg = data.get("content", data.get("msg", "<no message>"))

    # Format differently for private messages
    if event == "pm":
        to_user = data.get("to", data.get("platform_data", {}).get("to", "<no username>"))
        logger.info(
            "[%s] %s -> %s: %s", time, user, to_user, msg
        )
    else:
        logger.info("[%s] %s: %s", time, user, msg)


def log_media(bot, logger, *_):
    """Log when a new media item starts playing

    Args:
        bot: Bot instance to query for current playlist state
        logger: Logger instance to write to
        *_: Unused event arguments (event name, data)
    """
    current = bot.channel.playlist.current
    if current is not None:
        logger.info(
            '%s: %s "%s"',
            current.username,  # Who queued the item
            current.link.url,  # Media URL
            current.title,  # Media title
        )


class LLMHandlers:
    """Event handlers for LLM integration."""
    
    def __init__(self, bot, llm_client, trigger_manager, logger, config):
        """
        Initialize LLM handlers.
        
        Args:
            bot: Bot instance
            llm_client: LLMClient instance
            trigger_manager: TriggerManager instance
            logger: Logger for LLM events
            config: LLM configuration dict
        """
        self.bot = bot
        self.llm = llm_client
        self.triggers = trigger_manager
        self.logger = logger
        self.log_only = config.get('log_only', False)
    
    async def handle_chat_message(self, event, data):
        """
        Handle chat messages for LLM responses.
        
        Args:
            event: Event name ('chatMsg')
            data: Event data with username, msg, etc.
        """
        username = data.get('username', '')
        message = data.get('msg', '')
        
        # Skip our own messages
        if username.lower() == self.bot.user.name.lower():
            return
        
        # Get user rank for moderation checks
        user = self.bot.channel.get_user(username)
        user_rank = user.rank if user else 0.0
        
        # Check if we should respond
        should_respond, reason = self.triggers.should_respond_to_chat(
            username, message, user_rank
        )
        
        if not should_respond:
            return
        
        self.logger.info("Trigger: %s | User: %s | Message: %s", reason, username, message[:50])
        
        try:
            # Extract prompt (remove commands/mentions)
            prompt = self.triggers.extract_prompt(message)
            if not prompt:
                prompt = "Hello!"
            
            # Generate response
            response = await self.llm.chat(username, prompt)
            
            if self.log_only:
                self.logger.info("[LOG ONLY] Would respond: %s", response)
            else:
                await self.bot.chat(response)
                self.logger.info("Response sent: %s", response[:100])
        
        except Exception as e:
            self.logger.error("LLM error: %s", e, exc_info=True)
    
    async def handle_pm(self, event, data):
        """
        Handle private messages - stub for future implementation.
        
        Could be used for:
        - Private AI conversations
        - Admin commands to control LLM
        - User-specific settings
        """
        # NoOp for now
        pass
    
    async def handle_user_join(self, event, data):
        """
        Handle user join events for greetings.
        
        Args:
            event: Event name ('addUser')
            data: Event data with username, rank, etc.
        """
        username = data.get('name', '')
        rank = data.get('rank', 0.0)
        
        # Check if we should greet
        should_greet, reason = self.triggers.should_greet_user(
            username, rank, is_join=True
        )
        
        if not should_greet:
            return
        
        self.logger.info("Greeting: %s | User: %s (rank: %.1f)", reason, username, rank)
        
        try:
            # Generate personalized greeting
            prompt = f"Greet {username} who just joined the channel. Be brief and friendly."
            response = await self.llm.generate(prompt)
            
            if self.log_only:
                self.logger.info("[LOG ONLY] Would greet: %s", response)
            else:
                await self.bot.chat(response)
                self.logger.info("Greeting sent: %s", response[:100])
        
        except Exception as e:
            self.logger.error("LLM greeting error: %s", e, exc_info=True)


async def run_bot():
    """Run Rosey with proper async handling

    This is the main async function that:
    1. Loads configuration
    2. Sets up loggers for chat and media
    3. Creates and starts the bot and shell
    4. Registers event handlers
    5. Runs the bot until cancelled
    """
    # Load configuration from command line argument
    conf, kwargs = get_config()

    # Create separate loggers for chat messages, media, and LLM
    chat_logger = logging.getLogger("chat")
    media_logger = logging.getLogger("media")
    llm_logger = logging.getLogger("llm")

    # Configure chat logger (separate file or stdout)
    configure_logger(
        chat_logger,
        log_file=conf.get("chat_log_file", None),
        log_format="%(message)s",  # Simple format, just the message
    )

    # Configure media logger (separate file or stdout)
    configure_logger(
        media_logger,
        log_file=conf.get("media_log_file", None),
        log_format="[%(asctime).19s] %(message)s",  # Include timestamp
    )
    
    # Configure LLM logger
    configure_logger(
        llm_logger,
        log_file=conf.get("llm_log_file", None),
        log_format="[%(asctime).19s] [%(levelname)s] %(message)s",
    )

    # Extract CyTube connection parameters from kwargs
    domain = kwargs.pop('domain', None)
    channel = kwargs.pop('channel', None)
    user = kwargs.pop('user', None)
    
    # Handle channel password if it's a tuple
    channel_name = channel[0] if isinstance(channel, (list, tuple)) else channel
    channel_password = channel[1] if isinstance(channel, (list, tuple)) and len(channel) > 1 else None
    
    # Handle user credentials if it's a tuple
    username = user[0] if isinstance(user, (list, tuple)) and user else None
    password = user[1] if isinstance(user, (list, tuple)) and len(user) > 1 else None
    
    # Create Rosey bot instance using from_cytube helper
    bot = Bot.from_cytube(
        domain=domain,
        channel=channel_name,
        channel_password=channel_password,
        user=username,
        password=password,
        **kwargs  # restart_delay, db_path, enable_db
    )

    # Create shell (PM command handler) if configured
    shell = Shell(conf.get("shell", None), bot)
    
    # Initialize LLM if configured
    llm_client = None
    trigger_manager = None
    if HAS_LLM:
        llm_config = conf.get('llm', {})
        if llm_config.get('enabled', False):
            try:
                llm_client = LLMClient(llm_config)
                await llm_client.__aenter__()
                
                trigger_config = TriggerConfig(llm_config.get('triggers', {}))
                bot_username = conf.get('user', ['bot'])[0]
                trigger_manager = TriggerManager(trigger_config, bot_username)
                
                llm_logger.info("LLM integration enabled with %s provider", llm_config.get('provider'))
            except Exception as e:
                llm_logger.error("Failed to initialize LLM: %s", e)
                llm_client = None
                trigger_manager = None

    # Create partial functions with loggers bound
    log = partial(log_chat, chat_logger)
    log_m = partial(log_media, bot, media_logger)

    # Register event handlers (using normalized event names)
    bot.on("message", log)  # Log public chat messages (normalized from chatMsg)
    bot.on("pm", log)  # Log private messages
    bot.on("setCurrent", log_m)  # Log media changes

    # Register PM command handler for moderators (if shell is enabled)
    if shell.bot is not None:
        bot.on("pm", shell.handle_pm_command)  # Handle mod commands via PM
    
    # Register LLM handlers if enabled
    if llm_client and trigger_manager:
        llm_handlers = LLMHandlers(bot, llm_client, trigger_manager, llm_logger, conf.get('llm', {}))
        bot.on("chatMsg", llm_handlers.handle_chat_message)
        bot.on("pm", llm_handlers.handle_pm)
        bot.on("addUser", llm_handlers.handle_user_join)

    try:
        # Run Rosey (blocks until cancelled or error)
        await bot.run()
    finally:
        # Close LLM client if active
        if llm_client:
            await llm_client.__aexit__(None, None, None)


def main():
    """Main entry point for Rosey

    Runs the async bot and handles keyboard interrupt gracefully.

    Returns:
        0 on keyboard interrupt (normal exit)
        1 on error
    """
    try:
        # Run the async bot function
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        # User pressed Ctrl+C, exit cleanly
        return 0

    # If we get here without KeyboardInterrupt, something went wrong
    return 1


if __name__ == "__main__":
    sys.exit(main())
