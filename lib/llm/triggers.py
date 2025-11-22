"""
Trigger system for determining when the bot should respond with LLM.

Provides flexible, configurable logic for:
- Direct mentions (bot username in message, e.g., "CynthiaRothbot")
- Command triggers (!ai, !ask)
- Keyword/phrase triggers with throttling
- Random ambient chat
- User-specific behaviors
"""

import random
import re
from datetime import datetime
from typing import Any, Dict


class TriggerConfig:
    """Configuration for trigger behavior."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize trigger config.
        
        Config structure:
        {
            'enabled': True/False,
            'direct_mention': True/False,
            'commands': ['!ai', '!ask'],
            'ambient_chat': {
                'enabled': True/False,
                'every_n_messages': 20,
                'randomness': 0.5  # 0.0-1.0, adds variance
            },
            'keywords': [
                {
                    'phrases': ['toddy', 'the toddy'],
                    'probability': 0.1,  # 10% chance
                    'cooldown_seconds': 300
                },
                {
                    'phrases': ['boobs', 'boobies'],
                    'probability': 0.05,
                    'cooldown_seconds': 600
                }
            ],
            'greetings': {
                'enabled': True/False,
                'on_join': {
                    'enabled': True/False,
                    'probability': 0.2,  # 20% of joins
                    'idle_threshold_minutes': 60,
                    'moderators_only': False,
                    'specific_users': {
                        'alice': 1.0,  # Always greet
                        'bob': 0.5     # 50% chance
                    }
                },
                'on_status_change': {
                    'enabled': True/False,
                    'probability': 0.1
                }
            }
        }
        """
        self.enabled = config.get('enabled', False)
        self.direct_mention = config.get('direct_mention', True)
        self.commands = config.get('commands', ['!ai', '!ask'])

        # Ambient chat
        ambient = config.get('ambient_chat', {})
        self.ambient_enabled = ambient.get('enabled', False)
        self.ambient_every_n = ambient.get('every_n_messages', 20)
        self.ambient_randomness = ambient.get('randomness', 0.5)

        # Keywords
        self.keywords = config.get('keywords', [])

        # Greetings
        greetings = config.get('greetings', {})
        self.greetings_enabled = greetings.get('enabled', False)

        join_cfg = greetings.get('on_join', {})
        self.greet_on_join = join_cfg.get('enabled', False)
        self.greet_join_probability = join_cfg.get('probability', 0.2)
        self.greet_idle_threshold = join_cfg.get('idle_threshold_minutes', 60)
        self.greet_mods_only = join_cfg.get('moderators_only', False)
        self.greet_specific_users = join_cfg.get('specific_users', {})

        status_cfg = greetings.get('on_status_change', {})
        self.greet_on_status = status_cfg.get('enabled', False)
        self.greet_status_probability = status_cfg.get('probability', 0.1)


class TriggerManager:
    """Manages triggers and throttling for LLM responses."""

    def __init__(self, config: TriggerConfig, bot_username: str):
        """
        Initialize trigger manager.
        
        Args:
            config: TriggerConfig instance
            bot_username: Bot's CyTube username (e.g., "CynthiaRothbot", "SaveTheRobots")
        """
        self.config = config
        self.bot_username = bot_username.lower()

        # Message counters for ambient chat
        self.message_count = 0
        self.ambient_target = self._calculate_ambient_target()

        # Cooldown tracking per keyword
        self.keyword_cooldowns: Dict[str, datetime] = {}

        # User tracking for greetings
        self.user_last_seen: Dict[str, datetime] = {}

    def _calculate_ambient_target(self) -> int:
        """Calculate next ambient chat trigger with randomness."""
        base = self.config.ambient_every_n
        if self.config.ambient_randomness > 0:
            # Add variance based on randomness setting
            variance = int(base * self.config.ambient_randomness)
            return random.randint(base - variance, base + variance)
        return base

    def should_respond_to_chat(
        self,
        username: str,
        message: str,
        user_rank: float = 0.0
    ) -> tuple[bool, str]:
        """
        Check if bot should respond to a chat message.
        
        Args:
            username: Username who sent message
            message: The message text
            user_rank: User's rank (for moderator checks)
            
        Returns:
            (should_respond, reason) tuple
        """
        if not self.config.enabled:
            return False, "disabled"

        msg_lower = message.lower().strip()

        # Direct mention of bot's username (case-insensitive)
        # Users mention the bot's CyTube name (e.g., "CynthiaRothbot what's playing?")
        if self.config.direct_mention and self.bot_username.lower() in msg_lower:
            return True, "direct_mention"

        # Commands (!ai, !ask)
        for cmd in self.config.commands:
            if msg_lower.startswith(cmd.lower()):
                return True, f"command:{cmd}"

        # Keyword triggers with cooldown
        for kw_config in self.config.keywords:
            phrases = kw_config.get('phrases', [])
            probability = kw_config.get('probability', 0.0)
            cooldown = kw_config.get('cooldown_seconds', 300)

            # Check if any phrase matches
            matched_phrase = None
            for phrase in phrases:
                if phrase.lower() in msg_lower:
                    matched_phrase = phrase
                    break

            if matched_phrase:
                # Check cooldown
                cooldown_key = f"keyword:{matched_phrase}"
                if cooldown_key in self.keyword_cooldowns:
                    elapsed = (datetime.now() - self.keyword_cooldowns[cooldown_key]).total_seconds()
                    if elapsed < cooldown:
                        return False, f"keyword_cooldown:{matched_phrase}"

                # Check probability
                if random.random() < probability:
                    self.keyword_cooldowns[cooldown_key] = datetime.now()
                    return True, f"keyword:{matched_phrase}"
                else:
                    return False, f"keyword_probability_miss:{matched_phrase}"

        # Ambient chat (every N messages with randomness)
        if self.config.ambient_enabled:
            self.message_count += 1
            if self.message_count >= self.ambient_target:
                self.message_count = 0
                self.ambient_target = self._calculate_ambient_target()
                return True, f"ambient:every_{self.config.ambient_every_n}"

        return False, "no_trigger"

    def should_greet_user(
        self,
        username: str,
        user_rank: float = 0.0,
        is_join: bool = True
    ) -> tuple[bool, str]:
        """
        Check if bot should greet a user on join or status change.
        
        Args:
            username: Username
            user_rank: User's rank
            is_join: True for join event, False for status change
            
        Returns:
            (should_greet, reason) tuple
        """
        if not self.config.greetings_enabled:
            return False, "greetings_disabled"

        username_lower = username.lower()

        if is_join:
            if not self.config.greet_on_join:
                return False, "join_greetings_disabled"

            # Check if user has specific probability
            if username_lower in self.config.greet_specific_users:
                prob = self.config.greet_specific_users[username_lower]
                if random.random() < prob:
                    return True, f"specific_user:{username}"
                else:
                    return False, f"specific_user_probability_miss:{username}"

            # Check moderator-only
            if self.config.greet_mods_only and user_rank < 2.0:
                return False, "not_moderator"

            # Check idle threshold
            if username_lower in self.user_last_seen:
                last_seen = self.user_last_seen[username_lower]
                idle_minutes = (datetime.now() - last_seen).total_seconds() / 60
                if idle_minutes < self.config.greet_idle_threshold:
                    return False, f"recently_seen:{idle_minutes:.0f}min"

            # General probability
            if random.random() < self.config.greet_join_probability:
                self.user_last_seen[username_lower] = datetime.now()
                return True, "join_probability"
            else:
                self.user_last_seen[username_lower] = datetime.now()
                return False, "join_probability_miss"

        else:  # Status change
            if not self.config.greet_on_status:
                return False, "status_greetings_disabled"

            if random.random() < self.config.greet_status_probability:
                return True, "status_probability"
            else:
                return False, "status_probability_miss"

    def update_user_seen(self, username: str):
        """Update last seen time for a user."""
        self.user_last_seen[username.lower()] = datetime.now()

    def extract_prompt(self, message: str) -> str:
        """
        Extract the actual prompt from a message, removing commands and bot name.
        
        Examples:
            "!ai tell me a joke" -> "tell me a joke"
            "CynthiaRothbot what's playing?" -> "what's playing?"
            "hey SaveTheRobots explain this" -> "hey explain this"
        
        Args:
            message: Original message
            
        Returns:
            Cleaned prompt text
        """
        msg = message.strip()

        # Remove command prefixes
        for cmd in self.config.commands:
            if msg.lower().startswith(cmd.lower()):
                msg = msg[len(cmd):].strip()
                break

        # Remove bot username mentions (e.g., "CynthiaRothbot" or "SaveTheRobots")
        msg = re.sub(rf'\b{re.escape(self.bot_username)}\b', '', msg, flags=re.IGNORECASE)

        return msg.strip()
