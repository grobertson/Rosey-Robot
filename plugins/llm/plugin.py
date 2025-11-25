"""
LLM Plugin for NATS-based chat integration.

This plugin provides chat functionality through LLM providers, supporting
multiple personas, conversation memory (via NATS KV), and context management.

Features:
    - Multi-provider LLM support (Ollama, OpenAI, OpenRouter)
    - Persistent conversation history (NATS JetStream KV)
    - Automatic summarization
    - Memory recall and storage (NATS-based)
    - Per-channel context isolation
    - Multiple personas

Architecture:
    - NO direct database access
    - ALL persistence via NATS JetStream KeyValue store
    - Plugin-safe distributed storage
"""

import json
import logging
from typing import Any, Optional

from nats.aio.client import Client as NATS

from .service import LLMService
from .service_nats import LLMServiceNATS
from .rate_limiter import RateLimiter, RateLimitConfig
from .prompts import SystemPrompts
from .providers import ProviderError
from .memory import ConversationMemory, MemoryConfig
from .summarizer import ConversationSummarizer

logger = logging.getLogger(__name__)


class LLMPlugin:
    """NATS plugin for LLM chat functionality with persistent memory.
    
    Handles !chat commands and provides LLM services to other plugins
    through NATS messaging. Uses NATS JetStream KV for ALL persistence.
    
    Features:
        - Persistent conversation history (NATS KV)
        - Automatic summarization
        - Memory storage and recall (NATS KV)
        - Context management
        - Plugin-safe architecture (no database access)
    
    Subjects:
        - rosey.command.chat: Chat command handler
        - rosey.command.chat.remember: Remember fact
        - rosey.command.chat.recall: Recall memories
        - rosey.command.chat.forget: Forget memory
        - llm.request: Service request handler
        - llm.response: Response publication
        - llm.error: Error publication
        - rosey.llm.*: NATS service endpoints for inter-plugin communication
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
        self.nats_service: Optional[LLMServiceNATS] = None
        self.memory: Optional[ConversationMemory] = None
        self.summarizer: Optional[ConversationSummarizer] = None
        self.rate_limiter: Optional[RateLimiter] = None
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
            
            # Initialize NATS KV-based memory system
            logger.info("Initializing NATS KV memory system")
            
            memory_config = MemoryConfig(
                max_messages_in_context=self.config.get("max_context", 20)
            )
            self.memory = ConversationMemory(self.nc, memory_config)
            await self.memory.initialize()
            
            self.summarizer = ConversationSummarizer(self.service)
            
            logger.info("NATS KV memory system initialized")
            
            # Initialize rate limiter
            rate_config = self.config.get("rate_limits", {})
            rate_limit_config = RateLimitConfig(
                requests_per_minute=rate_config.get("requests_per_minute", 10),
                requests_per_hour=rate_config.get("requests_per_hour", 100),
                requests_per_day=rate_config.get("requests_per_day", 500),
                tokens_per_day=rate_config.get("tokens_per_day", 50_000),
            )
            self.rate_limiter = RateLimiter(rate_limit_config)
            
            # Initialize NATS service for inter-plugin communication
            self.nats_service = LLMServiceNATS(
                nc=self.nc,
                service=self.service,
                memory=self.memory,
                rate_limiter=self.rate_limiter,
            )
            await self.nats_service.start()
            
            logger.info("NATS LLM service started")
            
            # Subscribe to command subject
            sub = await self.nc.subscribe(
                "rosey.command.chat",
                cb=self._handle_chat_command
            )
            self._subscriptions.append(sub)
            
            # Subscribe to memory command subjects
            sub = await self.nc.subscribe(
                "rosey.command.chat.remember",
                cb=self._handle_remember_command
            )
            self._subscriptions.append(sub)
            
            sub = await self.nc.subscribe(
                "rosey.command.chat.recall",
                cb=self._handle_recall_command
            )
            self._subscriptions.append(sub)
            
            sub = await self.nc.subscribe(
                "rosey.command.chat.forget",
                cb=self._handle_forget_command
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
        # Stop NATS service
        if self.nats_service:
            await self.nats_service.stop()
        
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
            # Add user message to memory
            await self.memory.add_message(
                channel=channel_id,
                role="user",
                content=message,
                user_id=username
            )
            
            # Get response from service
            response = await self.service.chat(
                user_message=message,
                channel_id=channel_id,
                username=username
            )
            
            # Add assistant response to memory
            await self.memory.add_message(
                channel=channel_id,
                role="assistant",
                content=response
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
        # Reset service context
        context_size = self.service.get_context_size(channel_id)
        self.service.reset_context(channel_id)
        
        # Clear NATS KV memory
        cleared = await self.memory.reset_context(channel_id)
        
        await self._send_response(
            channel_id,
            f"Conversation context reset ({context_size} in-memory, {cleared} persisted messages cleared)."
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
!chat remember <fact> - Store a fact in memory
!chat recall <query> - Recall memories by keyword
!chat forget <id> - Forget a specific memory
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
    
    async def _handle_remember_command(self, msg) -> None:
        """Handle !chat remember command.
        
        Args:
            msg: NATS message with command data
        """
        try:
            data = json.loads(msg.data.decode())
            
            args = data.get("args", [])
            channel_id = data.get("channel_id", "")
            username = data.get("username", "User")
            
            if len(args) < 2:
                await self._send_error(
                    channel_id,
                    "Usage: !chat remember <fact>"
                )
                return
            
            # Join all args after "remember"
            fact = " ".join(args[1:])
            
            # Store in memory
            memory_id = await self.memory.remember(
                channel=channel_id,
                content=fact,
                user_id=username
            )
            
            await self._send_response(
                channel_id,
                f"Remembered: {fact} (ID: {memory_id})"
            )
        
        except Exception as e:
            logger.error(f"Error in remember command: {e}")
            await self._send_error(
                data.get("channel_id", ""),
                f"Failed to remember: {e}"
            )
    
    async def _handle_recall_command(self, msg) -> None:
        """Handle !chat recall command.
        
        Args:
            msg: NATS message with command data
        """
        try:
            data = json.loads(msg.data.decode())
            
            args = data.get("args", [])
            channel_id = data.get("channel_id", "")
            
            if len(args) < 2:
                await self._send_error(
                    channel_id,
                    "Usage: !chat recall <query>"
                )
                return
            
            # Join all args after "recall"
            query = " ".join(args[1:])
            
            # Search memories
            memories = await self.memory.recall(
                channel=channel_id,
                query=query,
                limit=5
            )
            
            if not memories:
                await self._send_response(
                    channel_id,
                    f"No memories found for: {query}"
                )
            else:
                response = f"Memories matching '{query}':\n" + "\n".join(
                    f"• {mem}" for mem in memories
                )
                await self._send_response(channel_id, response)
        
        except Exception as e:
            logger.error(f"Error in recall command: {e}")
            await self._send_error(
                data.get("channel_id", ""),
                f"Failed to recall: {e}"
            )
    
    async def _handle_forget_command(self, msg) -> None:
        """Handle !chat forget command.
        
        Args:
            msg: NATS message with command data
        """
        try:
            data = json.loads(msg.data.decode())
            
            args = data.get("args", [])
            channel_id = data.get("channel_id", "")
            
            if len(args) < 2:
                await self._send_error(
                    channel_id,
                    "Usage: !chat forget <memory_id>"
                )
                return
            
            memory_id = args[1]
            
            # Delete memory
            success = await self.memory.forget(
                channel=channel_id,
                memory_id=memory_id
            )
            
            if success:
                await self._send_response(
                    channel_id,
                    f"Forgot memory: {memory_id}"
                )
            else:
                await self._send_error(
                    channel_id,
                    f"Memory not found: {memory_id}"
                )
        
        except Exception as e:
            logger.error(f"Error in forget command: {e}")
            await self._send_error(
                data.get("channel_id", ""),
                f"Failed to forget: {e}"
            )
