"""
LLM Plugin for NATS-based chat integration.

This plugin provides chat functionality through LLM providers, supporting
multiple personas and conversation context management.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from nats.aio.client import Client as NATS

from .service import LLMService
from .prompts import SystemPrompts
from .providers import ProviderError

logger = logging.getLogger(__name__)


class LLMPlugin:
    """NATS plugin for LLM chat functionality.
    
    Handles !chat commands and provides LLM services to other plugins
    through NATS messaging.
    
    Subjects:
        - rosey.command.chat: Chat command handler
        - llm.request: Service request handler
        - llm.response: Response publication
        - llm.error: Error publication
    """
    
    def __init__(self, nc: NATS, config: dict[str, Any]):
        """Initialize LLM plugin.
        
        Args:
            nc: NATS client instance
            config: Plugin configuration dictionary
        """
        self.nc = nc
        self.config = config
        self.service: Optional[LLMService] = None
        self._subscriptions = []
        
        logger.info("LLM plugin initialized")
    
    async def start(self) -> None:
        """Start the plugin and subscribe to NATS subjects."""
        # Get provider from config
        provider_name = self.config.get("default_provider", "ollama")
        
        try:
            # Create service
            self.service = LLMService.create_from_config(
                self.config,
                provider_name=provider_name
            )
            
            # Check if provider is available
            is_available = await self.service.provider.is_available()
            if not is_available:
                logger.warning(
                    f"Provider {provider_name} is not available. "
                    f"Plugin will be limited."
                )
            else:
                logger.info(f"Provider {provider_name} is available")
            
            # Subscribe to command subject
            sub = await self.nc.subscribe(
                "rosey.command.chat",
                cb=self._handle_chat_command
            )
            self._subscriptions.append(sub)
            
            # Subscribe to service request subject
            sub = await self.nc.subscribe(
                "llm.request",
                cb=self._handle_service_request
            )
            self._subscriptions.append(sub)
            
            logger.info("LLM plugin started and subscribed to NATS subjects")
        
        except Exception as e:
            logger.error(f"Failed to start LLM plugin: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the plugin and unsubscribe from NATS subjects."""
        for sub in self._subscriptions:
            await sub.unsubscribe()
        
        self._subscriptions.clear()
        logger.info("LLM plugin stopped")
    
    async def _handle_chat_command(self, msg) -> None:
        """Handle !chat command from users.
        
        Command formats:
            !chat <message>         - Send chat message
            !chat reset             - Reset conversation context
            !chat persona <name>    - Change persona
            !chat help              - Show help message
        
        Args:
            msg: NATS message with command data
        """
        try:
            data = json.loads(msg.data.decode())
            
            command = data.get("command", "")
            args = data.get("args", [])
            channel_id = data.get("channel_id", "")
            username = data.get("username", "User")
            
            if not self.service:
                await self._send_error(
                    channel_id,
                    "LLM service is not initialized"
                )
                return
            
            # Handle subcommands
            if not args:
                await self._send_help(channel_id)
                return
            
            subcommand = args[0].lower()
            
            if subcommand == "reset":
                await self._handle_reset(channel_id)
            elif subcommand == "persona":
                await self._handle_persona(channel_id, args[1:])
            elif subcommand == "help":
                await self._send_help(channel_id)
            else:
                # Treat entire args as message
                message = " ".join(args)
                await self._handle_chat(channel_id, username, message)
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in chat command: {e}")
        except Exception as e:
            logger.error(f"Error handling chat command: {e}")
            if "channel_id" in data:
                await self._send_error(data["channel_id"], str(e))
    
    async def _handle_chat(
        self,
        channel_id: str,
        username: str,
        message: str
    ) -> None:
        """Handle chat message from user.
        
        Args:
            channel_id: Channel identifier
            username: Username
            message: User's message
        """
        try:
            # Get response from service
            response = await self.service.chat(
                user_message=message,
                channel_id=channel_id,
                username=username
            )
            
            # Publish response
            await self._send_response(channel_id, response)
        
        except ProviderError as e:
            logger.error(f"Provider error in chat: {e}")
            await self._send_error(
                channel_id,
                f"Sorry, I encountered an error: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}")
            await self._send_error(
                channel_id,
                "Sorry, something went wrong while processing your message."
            )
    
    async def _handle_reset(self, channel_id: str) -> None:
        """Handle context reset command.
        
        Args:
            channel_id: Channel identifier
        """
        context_size = self.service.get_context_size(channel_id)
        self.service.reset_context(channel_id)
        
        await self._send_response(
            channel_id,
            f"Conversation context reset ({context_size} messages cleared)."
        )
    
    async def _handle_persona(
        self,
        channel_id: str,
        args: list[str]
    ) -> None:
        """Handle persona change command.
        
        Args:
            channel_id: Channel identifier
            args: Command arguments (persona name or empty for list)
        """
        if not args:
            # List available personas
            personas = SystemPrompts.available()
            current = self.service.get_persona()
            persona_list = ", ".join(personas)
            
            await self._send_response(
                channel_id,
                f"Available personas: {persona_list}. "
                f"Current: {current}. "
                f"Use: !chat persona <name>"
            )
            return
        
        persona_name = args[0].lower()
        
        try:
            self.service.set_persona(persona_name)
            await self._send_response(
                channel_id,
                f"Persona changed to: {persona_name}"
            )
        except ValueError as e:
            await self._send_error(channel_id, str(e))
    
    async def _send_help(self, channel_id: str) -> None:
        """Send help message to channel.
        
        Args:
            channel_id: Channel identifier
        """
        help_text = """LLM Chat Commands:
!chat <message> - Send a message to the LLM
!chat reset - Clear conversation context
!chat persona [name] - Change or list personas (default, concise, technical, creative)
!chat help - Show this help message"""
        
        await self._send_response(channel_id, help_text)
    
    async def _handle_service_request(self, msg) -> None:
        """Handle LLM service request from other plugins.
        
        Request format:
            {
                "action": "chat" | "complete" | "reset",
                "channel_id": str,
                "message": str (for chat/complete),
                "username": str (optional, for chat),
                "model": str (optional),
                "temperature": float (optional),
                "max_tokens": int (optional)
            }
        
        Args:
            msg: NATS message with request data
        """
        try:
            data = json.loads(msg.data.decode())
            
            if not self.service:
                await self._send_error(
                    data.get("channel_id", ""),
                    "LLM service is not initialized"
                )
                return
            
            action = data.get("action", "")
            channel_id = data.get("channel_id", "")
            
            if action == "chat":
                response = await self.service.chat(
                    user_message=data["message"],
                    channel_id=channel_id,
                    username=data.get("username", "User"),
                    model=data.get("model"),
                    temperature=data.get("temperature", 0.7),
                    max_tokens=data.get("max_tokens")
                )
                await self._send_response(channel_id, response)
            
            elif action == "complete":
                response = await self.service.complete_raw(
                    prompt=data["message"],
                    model=data.get("model"),
                    temperature=data.get("temperature", 0.7),
                    max_tokens=data.get("max_tokens")
                )
                await self._send_response(channel_id, response)
            
            elif action == "reset":
                self.service.reset_context(channel_id)
                await self._send_response(
                    channel_id,
                    "Context reset"
                )
            
            else:
                await self._send_error(
                    channel_id,
                    f"Unknown action: {action}"
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in service request: {e}")
        except KeyError as e:
            logger.error(f"Missing required field in service request: {e}")
        except ProviderError as e:
            logger.error(f"Provider error in service request: {e}")
            await self._send_error(
                data.get("channel_id", ""),
                f"Provider error: {e}"
            )
        except Exception as e:
            logger.error(f"Error handling service request: {e}")
            await self._send_error(
                data.get("channel_id", ""),
                f"Service error: {e}"
            )
    
    async def _send_response(
        self,
        channel_id: str,
        content: str
    ) -> None:
        """Publish response event.
        
        Args:
            channel_id: Channel identifier
            content: Response content
        """
        event = {
            "channel_id": channel_id,
            "content": content,
            "type": "llm_response"
        }
        
        await self.nc.publish(
            "llm.response",
            json.dumps(event).encode()
        )
    
    async def _send_error(
        self,
        channel_id: str,
        error: str
    ) -> None:
        """Publish error event.
        
        Args:
            channel_id: Channel identifier
            error: Error message
        """
        event = {
            "channel_id": channel_id,
            "error": error,
            "type": "llm_error"
        }
        
        await self.nc.publish(
            "llm.error",
            json.dumps(event).encode()
        )
