"""
LLM Conversation Memory using NATS JetStream KV
================================================

Lightweight memory management using NATS KeyValue store for persistence.
NO direct database access - all storage via NATS messaging.

Features:
- Store conversation messages in NATS KV
- Store memorable facts in NATS KV
- Per-channel context isolation
- JSON serialization for simple data structures

NATS KV Buckets:
- llm-messages: Recent messages per channel
- llm-memories: Memorable facts per channel
- llm-user-context: User preferences

Key Structure:
- messages:{channel}:recent -> JSON array of last N messages
- memories:{channel}:{id} -> Individual memory JSON
- user:{user_id}:context -> User preferences JSON
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

from .providers.base import Message

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    """Memory configuration."""
    max_messages_in_context: int = 20
    max_memories_per_channel: int = 50


@dataclass
class StoredMessage:
    """Message stored in NATS KV."""
    role: str
    content: str
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    
    def to_message(self) -> Message:
        """Convert to provider Message."""
        return Message(
            role=self.role,
            content=self.content
        )


@dataclass
class StoredMemory:
    """Memory stored in NATS KV."""
    id: str
    content: str
    category: str = "fact"  # fact, preference, topic
    importance: int = 1  # 1-5
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    accessed_at: Optional[str] = None


class ConversationMemory:
    """
    Manages conversation memory using NATS JetStream KV.
    
    All persistence via NATS - no direct database access.
    """
    
    def __init__(self, nats_client, config: Optional[MemoryConfig] = None):
        """
        Initialize memory manager with NATS client.
        
        Args:
            nats_client: NATS client instance (has .jetstream() method)
            config: Memory configuration
        """
        self.nc = nats_client
        self.config = config or MemoryConfig()
        self.js = None  # JetStream context
        self.kv = None  # KeyValue bucket
        
    async def initialize(self) -> None:
        """
        Initialize NATS JetStream KV buckets.
        
        Creates buckets if they don't exist.
        """
        try:
            # Get JetStream context
            self.js = self.nc.jetstream()
            
            # Create or get KV bucket for LLM data
            try:
                self.kv = await self.js.key_value(bucket="llm_data")
            except Exception:  # pylint: disable=broad-except
                # Bucket doesn't exist, create it
                from nats.js.api import KeyValueConfig
                self.kv = await self.js.create_key_value(
                    config=KeyValueConfig(
                        bucket="llm_data",
                        description="LLM conversation memory and context",
                        max_bytes=10 * 1024 * 1024,  # 10MB max
                        history=5,  # Keep last 5 versions,
                    )
                )
            
            logger.info("NATS KV memory system initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize NATS KV: {e}")
            raise
    
    async def add_message(
        self,
        channel: str,
        role: str,
        content: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Add message to conversation history.
        
        Stores in NATS KV with automatic rotation (keeps last N messages).
        
        Args:
            channel: Channel identifier
            role: Message role (user, assistant, system)
            content: Message content
            user_id: User identifier
        """
        if not self.kv:
            logger.warning("Memory not initialized - message not stored")
            return
        
        try:
            # Get existing messages
            messages = await self._get_messages(channel)
            
            # Add new message
            new_message = StoredMessage(
                role=role,
                content=content,
                user_id=user_id,
                timestamp=datetime.utcnow().isoformat()
            )
            messages.append(asdict(new_message))
            
            # Keep only last N messages
            if len(messages) > self.config.max_messages_in_context * 2:
                messages = messages[-self.config.max_messages_in_context * 2:]
            
            # Store back to KV
            key = f"messages:{channel}:recent"
            await self.kv.put(key, json.dumps(messages).encode())
            
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
    
    async def get_recent_messages(
        self,
        channel: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get recent messages for channel.
        
        Args:
            channel: Channel identifier
            limit: Maximum messages (defaults to config)
            
        Returns:
            List of Message objects
        """
        if not self.kv:
            return []
        
        try:
            messages = await self._get_messages(channel)
            
            # Apply limit
            if limit:
                messages = messages[-limit:]
            else:
                messages = messages[-self.config.max_messages_in_context:]
            
            # Convert to Message objects
            return [
                StoredMessage(**msg).to_message()
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    async def reset_context(self, channel: str) -> int:
        """
        Clear conversation history for channel.
        
        Args:
            channel: Channel identifier
            
        Returns:
            Number of messages cleared
        """
        if not self.kv:
            return 0
        
        try:
            messages = await self._get_messages(channel)
            count = len(messages)
            
            # Delete the key
            key = f"messages:{channel}:recent"
            await self.kv.delete(key)
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to reset context: {e}")
            return 0
    
    async def remember(
        self,
        channel: str,
        content: str,
        category: str = "fact",
        user_id: Optional[str] = None,
        importance: int = 1
    ) -> str:
        """
        Store a memory.
        
        Args:
            channel: Channel identifier
            content: Memory content
            category: Memory category
            user_id: User identifier
            importance: Importance (1-5)
            
        Returns:
            Memory ID
        """
        if not self.kv:
            return ""
        
        try:
            # Generate memory ID
            import uuid
            memory_id = str(uuid.uuid4())[:8]
            
            # Create memory
            memory = StoredMemory(
                id=memory_id,
                content=content,
                category=category,
                importance=importance,
                user_id=user_id,
                created_at=datetime.utcnow().isoformat()
            )
            
            # Store in KV
            key = f"memories:{channel}:{memory_id}"
            await self.kv.put(key, json.dumps(asdict(memory)).encode())
            
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return ""
    
    async def recall(
        self,
        channel: str,
        query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Recall memories matching query.
        
        Simple keyword matching.
        
        Args:
            channel: Channel identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            List of memory contents
        """
        if not self.kv:
            return []
        
        try:
            # Get all memories for channel
            memories = await self._get_memories(channel)
            
            # Filter by keyword
            keywords = query.lower().split()
            matches = []
            
            for memory in memories:
                content_lower = memory.content.lower()
                if any(kw in content_lower for kw in keywords):
                    matches.append((memory, memory.importance))
            
            # Sort by importance
            matches.sort(key=lambda x: x[1], reverse=True)
            
            # Return top N
            return [m[0].content for m in matches[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            return []
    
    async def forget(self, channel: str, memory_id: str) -> bool:
        """
        Delete a memory.
        
        Args:
            channel: Channel identifier
            memory_id: Memory ID
            
        Returns:
            True if deleted
        """
        if not self.kv:
            return False
        
        try:
            key = f"memories:{channel}:{memory_id}"
            await self.kv.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Failed to forget memory: {e}")
            return False
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    async def _get_messages(self, channel: str) -> List[Dict[str, Any]]:
        """Get messages from KV."""
        try:
            key = f"messages:{channel}:recent"
            entry = await self.kv.get(key)
            if entry and entry.value:
                return json.loads(entry.value.decode())
            return []
        except Exception:  # pylint: disable=broad-except
            return []
    
    async def _get_memories(self, channel: str) -> List[StoredMemory]:
        """Get all memories for channel from KV."""
        memories = []
        try:
            # Get all keys matching pattern
            keys = await self.kv.keys(f"memories:{channel}:*")
            
            # Fetch each memory
            for key in keys:
                try:
                    entry = await self.kv.get(key)
                    if entry and entry.value:
                        data = json.loads(entry.value.decode())
                        memories.append(StoredMemory(**data))
                except Exception:  # pylint: disable=broad-except
                    continue
            
            return memories
            
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []
