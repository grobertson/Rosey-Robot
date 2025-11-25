"""
plugins/8ball/plugin.py

Magic 8-Ball fortune-telling plugin for Rosey.

NATS-based plugin that handles:
- rosey.command.8ball.ask - Main command handler
- 8ball.consulted - Event emission for analytics

This plugin demonstrates:
- Simple stateless plugin pattern
- Personality injection (Rosey's character)
- Rate limiting to prevent spam
- Event emission for analytics
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from nats.aio.client import Client as NATS

try:
    from .responses import ResponseSelector, EightBallResponse
except ImportError:
    from responses import ResponseSelector, EightBallResponse


class EightBallPlugin:
    """
    Magic 8-Ball fortune-telling plugin.
    
    Consult the mystical 8-Ball with `!8ball <question>` and receive
    one of 20 classic responses with Rosey's personality flair.
    
    Commands:
        !8ball <question> - Consult the mystical 8-ball
        
    Configuration:
        cooldown_seconds: Seconds between uses per user (default: 3)
        emit_events: Whether to emit analytics events (default: true)
        require_question: Whether to require a question (default: true)
        max_question_length: Max displayed question length (default: 100)
        
    NATS Subjects:
        Subscribe: rosey.command.8ball.ask
        Publish: rosey.event.8ball.consulted
    """
    
    # Plugin metadata
    NAMESPACE = "8ball"
    VERSION = "1.0.0"
    DESCRIPTION = "Consult the mystical Magic 8-Ball"
    
    # NATS subjects
    SUBJECT_ASK = "rosey.command.8ball.ask"
    EVENT_CONSULTED = "rosey.event.8ball.consulted"
    
    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the 8-Ball plugin.
        
        Args:
            nats_client: Connected NATS client for messaging.
            config: Optional configuration dictionary.
        """
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.NAMESPACE}")
        
        # Response selection
        self.selector = ResponseSelector()
        
        # Cooldown tracking: user -> last_use_timestamp
        self.cooldowns: Dict[str, float] = defaultdict(float)
        
        # Configuration with defaults
        self.cooldown_seconds = self.config.get("cooldown_seconds", 3)
        self.emit_events = self.config.get("emit_events", True)
        self.require_question = self.config.get("require_question", True)
        self.max_question_length = self.config.get("max_question_length", 100)
        
        # Subscription tracking
        self._subscriptions = []
    
    async def initialize(self) -> None:
        """
        Initialize the plugin and subscribe to NATS subjects.
        
        Should be called after construction to set up message handlers.
        """
        sub = await self.nats.subscribe(self.SUBJECT_ASK, cb=self._handle_ask)
        self._subscriptions.append(sub)
        self.logger.info(f"8ball plugin v{self.VERSION} loaded")
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin and cleanup resources.
        
        Unsubscribes from all NATS subjects and clears cooldowns.
        """
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        self.cooldowns.clear()
        self.logger.info("8ball plugin unloaded")
    
    async def _handle_ask(self, msg) -> None:
        """
        Handle incoming !8ball ask requests.
        
        Message format (incoming):
        {
            "channel": "string",
            "user": "string", 
            "args": "question string",
            "reply_to": "rosey.reply.xyz"
        }
        
        Response format (outgoing):
        {
            "success": true/false,
            "result": {...} or "error": "..."
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            user = data.get("user", "anonymous")
            question = data.get("args", "").strip()
            reply_to = data.get("reply_to")
            
            # Check cooldown
            if not self._check_cooldown(user):
                remaining = self._get_cooldown_remaining(user)
                response = {
                    "success": False,
                    "error": f"🎱 The 8-ball needs a moment to recover... try again in {remaining:.0f} seconds"
                }
                if reply_to:
                    await self.nats.publish(reply_to, json.dumps(response).encode())
                return
            
            # Check if question is required
            if self.require_question and not question:
                response = {
                    "success": False,
                    "error": "🎱 The spirits need a question to answer! Usage: !8ball <question>"
                }
                if reply_to:
                    await self.nats.publish(reply_to, json.dumps(response).encode())
                return
            
            # Truncate very long questions for display
            display_question = question[:self.max_question_length]
            if len(question) > self.max_question_length:
                display_question = display_question.rstrip() + "..."
            
            # If no question provided (and not required), use a default
            if not question:
                display_question = "what does fate hold?"
            
            # Get response
            ball_response = self.selector.select()
            formatted = ball_response.format(display_question)
            
            # Update cooldown
            self._update_cooldown(user)
            
            # Build response
            response = {
                "success": True,
                "result": {
                    "question": display_question,
                    "answer": ball_response.answer,
                    "category": ball_response.category.value,
                    "flavor": ball_response.flavor,
                    "formatted": formatted,
                }
            }
            
            # Send reply
            if reply_to:
                await self.nats.publish(reply_to, json.dumps(response).encode())
            
            # Emit analytics event
            if self.emit_events:
                await self._emit_consulted_event(
                    channel=channel,
                    user=user,
                    category=ball_response.category.value
                )
            
            self.logger.debug(f"8ball consulted by {user}: {ball_response.category.value}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in 8ball request: {e}")
            if msg.reply:
                error_response = {"success": False, "error": "Invalid request format"}
                await self.nats.publish(msg.reply, json.dumps(error_response).encode())
        except Exception as e:
            self.logger.exception(f"Error handling 8ball request: {e}")
            if msg.reply:
                error_response = {"success": False, "error": "An error occurred consulting the 8-ball"}
                await self.nats.publish(msg.reply, json.dumps(error_response).encode())
    
    def _check_cooldown(self, user: str) -> bool:
        """
        Check if a user is allowed to use the 8-ball (not on cooldown).
        
        Args:
            user: Username to check.
            
        Returns:
            True if the user can use the 8-ball, False if on cooldown.
        """
        if self.cooldown_seconds <= 0:
            return True
        
        last_use = self.cooldowns.get(user, 0)
        return time.time() - last_use >= self.cooldown_seconds
    
    def _get_cooldown_remaining(self, user: str) -> float:
        """
        Get remaining cooldown time for a user.
        
        Args:
            user: Username to check.
            
        Returns:
            Remaining seconds, or 0 if not on cooldown.
        """
        last_use = self.cooldowns.get(user, 0)
        elapsed = time.time() - last_use
        remaining = self.cooldown_seconds - elapsed
        return max(0, remaining)
    
    def _update_cooldown(self, user: str) -> None:
        """
        Update a user's cooldown timestamp to now.
        
        Args:
            user: Username to update.
        """
        self.cooldowns[user] = time.time()
    
    async def _emit_consulted_event(
        self,
        channel: str,
        user: str,
        category: str
    ) -> None:
        """
        Emit an 8ball.consulted event for analytics.
        
        Args:
            channel: Channel where the command was used.
            user: User who consulted the 8-ball.
            category: Response category (positive/neutral/negative).
        """
        event = {
            "event": "8ball.consulted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "user": user,
            "category": category,
        }
        await self.nats.publish(self.EVENT_CONSULTED, json.dumps(event).encode())
    
    # =========================================================================
    # Direct API (for programmatic access)
    # =========================================================================
    
    def ask(self, question: Optional[str] = None) -> EightBallResponse:
        """
        Consult the 8-ball directly (synchronous API).
        
        This method bypasses NATS and cooldowns for direct integration.
        
        Args:
            question: Optional question (not used in response selection).
            
        Returns:
            EightBallResponse with answer, category, and flavor.
        """
        return self.selector.select()
    
    def ask_formatted(self, question: str) -> str:
        """
        Consult the 8-ball and get a formatted response string.
        
        Args:
            question: The question to ask.
            
        Returns:
            Formatted response string ready for display.
        """
        response = self.selector.select()
        return response.format(question)
