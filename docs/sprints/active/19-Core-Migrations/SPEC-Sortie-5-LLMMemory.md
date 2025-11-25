# SPEC: Sortie 5 - LLM Memory & Context

**Sprint:** 19 - Core Migrations  
**Sortie:** 5 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** HIGH - Key UX enhancement  
**Prerequisites:** Sortie 4 (LLM Foundation)

---

## 1. Overview

### 1.1 Purpose

Enhance the LLM plugin with sophisticated context management:

- Persistent conversation memory
- Per-user context isolation
- Summarization for long conversations
- Context window management
- Memory search and recall

### 1.2 Scope

**In Scope:**
- Conversation memory database
- Per-channel and per-user context
- Smart context window management
- Conversation summarization
- Memory recall (`!chat recall <topic>`)
- Context persistence across restarts

**Out of Scope (Sortie 6):**
- Additional providers
- Streaming responses
- Advanced tools

### 1.3 Dependencies

- Sortie 4 (LLM Foundation) - MUST be complete
- Database service (Sprint 17)

---

## 2. Technical Design

### 2.1 Extended File Structure

```
plugins/llm/
├── ...existing files...
├── memory.py             # Memory management
├── storage.py            # Database operations
├── summarizer.py         # Conversation summarization
└── tests/
    ├── ...existing tests...
    ├── test_memory.py       # Memory tests
    ├── test_storage.py      # Storage tests
    └── test_summarizer.py   # Summarizer tests
```

### 2.2 Database Schema

```sql
-- Conversation messages
CREATE TABLE llm_messages (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    user_id TEXT NULL,  -- NULL for assistant messages
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- For context management
    token_count INTEGER DEFAULT 0,
    summarized BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_llm_messages_channel ON llm_messages(channel);
CREATE INDEX idx_llm_messages_user ON llm_messages(user_id);
CREATE INDEX idx_llm_messages_time ON llm_messages(channel, created_at DESC);

-- Conversation summaries
CREATE TABLE llm_summaries (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    summary TEXT NOT NULL,
    messages_from INTEGER NOT NULL,  -- First message ID
    messages_to INTEGER NOT NULL,    -- Last message ID
    message_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_summaries_channel ON llm_summaries(channel);

-- User preferences and context
CREATE TABLE llm_user_context (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    preferred_persona TEXT DEFAULT 'default',
    custom_context TEXT NULL,  -- User-provided context
    interaction_count INTEGER DEFAULT 0,
    last_interaction TIMESTAMP NULL
);

CREATE INDEX idx_llm_user_context_user ON llm_user_context(user_id);

-- Memory entries (facts to remember)
CREATE TABLE llm_memories (
    id INTEGER PRIMARY KEY,
    channel TEXT NOT NULL,
    user_id TEXT NULL,
    category TEXT NOT NULL,  -- 'fact', 'preference', 'topic'
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 1,  -- 1-5
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP NULL
);

CREATE INDEX idx_llm_memories_channel ON llm_memories(channel);
CREATE INDEX idx_llm_memories_user ON llm_memories(user_id);
```

### 2.3 Memory Management

```python
# plugins/llm/memory.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from .storage import LLMStorage
from .providers.base import Message


@dataclass
class MemoryConfig:
    """Memory management configuration."""
    max_messages_in_context: int = 20
    max_tokens_in_context: int = 4000
    summarize_after_messages: int = 50
    memory_decay_days: int = 30
    max_memories_per_channel: int = 100


@dataclass
class ConversationContext:
    """Context for a conversation."""
    system_prompt: str
    summaries: List[str]
    recent_messages: List[Message]
    relevant_memories: List[str]
    
    def to_messages(self) -> List[Message]:
        """Convert context to message list for LLM."""
        messages = []
        
        # System prompt with context
        system_content = self.system_prompt
        
        if self.summaries:
            system_content += "\n\n## Previous conversation summary:\n"
            system_content += "\n".join(self.summaries)
        
        if self.relevant_memories:
            system_content += "\n\n## Remembered facts:\n"
            system_content += "\n".join(f"- {m}" for m in self.relevant_memories)
        
        messages.append(Message(role="system", content=system_content))
        messages.extend(self.recent_messages)
        
        return messages


class ConversationMemory:
    """
    Manages conversation memory and context.
    
    Handles:
    - Message history
    - Context window management
    - Conversation summarization
    - Memory persistence
    """
    
    def __init__(
        self,
        storage: LLMStorage,
        config: MemoryConfig = None,
    ):
        self._storage = storage
        self._config = config or MemoryConfig()
        
        # In-memory cache for active conversations
        self._active: dict[str, List[Message]] = {}
    
    async def add_message(
        self,
        channel: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Add a message to conversation history.
        
        Handles automatic summarization if needed.
        """
        # Add to database
        await self._storage.save_message(channel, user_id, role, content)
        
        # Add to active cache
        if channel not in self._active:
            self._active[channel] = []
        
        self._active[channel].append(Message(
            role=role,
            content=content,
            name=user_id,
        ))
        
        # Check if summarization needed
        message_count = await self._storage.get_message_count(channel)
        unsummarized = await self._storage.get_unsummarized_count(channel)
        
        if unsummarized >= self._config.summarize_after_messages:
            await self._trigger_summarization(channel)
    
    async def get_context(
        self,
        channel: str,
        system_prompt: str,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> ConversationContext:
        """
        Build conversation context for LLM request.
        
        Args:
            channel: Channel identifier
            system_prompt: Base system prompt
            user_id: User making request (for personalization)
            query: Current query (for memory recall)
            
        Returns:
            ConversationContext ready for LLM
        """
        # Get recent messages from cache or DB
        recent = await self._get_recent_messages(
            channel, 
            self._config.max_messages_in_context
        )
        
        # Get summaries
        summaries = await self._storage.get_summaries(channel, limit=3)
        summary_texts = [s["summary"] for s in summaries]
        
        # Get relevant memories
        memories = []
        if query:
            memories = await self._recall_memories(channel, query, user_id)
        
        return ConversationContext(
            system_prompt=system_prompt,
            summaries=summary_texts,
            recent_messages=recent,
            relevant_memories=memories,
        )
    
    async def reset_context(self, channel: str) -> int:
        """
        Reset conversation context for a channel.
        
        Returns:
            Number of messages cleared
        """
        count = await self._storage.clear_messages(channel)
        self._active.pop(channel, None)
        return count
    
    async def remember(
        self,
        channel: str,
        content: str,
        category: str = "fact",
        user_id: Optional[str] = None,
        importance: int = 1,
    ) -> None:
        """
        Store a memory for future recall.
        """
        await self._storage.save_memory(
            channel=channel,
            user_id=user_id,
            category=category,
            content=content,
            importance=importance,
        )
    
    async def recall(
        self,
        channel: str,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[str]:
        """
        Recall relevant memories.
        
        Returns:
            List of memory contents
        """
        return await self._recall_memories(channel, query, user_id, limit)
    
    async def forget(self, channel: str, memory_id: int) -> bool:
        """Delete a specific memory."""
        return await self._storage.delete_memory(memory_id)
    
    async def _get_recent_messages(
        self, 
        channel: str, 
        limit: int
    ) -> List[Message]:
        """Get recent messages, preferring cache."""
        if channel in self._active:
            return self._active[channel][-limit:]
        
        # Load from database
        rows = await self._storage.get_recent_messages(channel, limit)
        messages = [
            Message(role=row["role"], content=row["content"], name=row["user_id"])
            for row in rows
        ]
        
        # Update cache
        self._active[channel] = messages
        
        return messages
    
    async def _recall_memories(
        self,
        channel: str,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[str]:
        """
        Recall memories relevant to query.
        
        Uses simple keyword matching. Could be enhanced with embeddings.
        """
        memories = await self._storage.search_memories(
            channel=channel,
            query=query,
            user_id=user_id,
            limit=limit,
        )
        
        # Update last_accessed
        for m in memories:
            await self._storage.touch_memory(m["id"])
        
        return [m["content"] for m in memories]
    
    async def _trigger_summarization(self, channel: str) -> None:
        """Trigger summarization of old messages."""
        # Get unsummarized messages
        messages = await self._storage.get_unsummarized_messages(channel)
        
        if len(messages) < 10:
            return
        
        # Request summarization (uses LLM)
        # This will be called by the plugin
        pass
```

### 2.4 Summarization

```python
# plugins/llm/summarizer.py

from typing import List
from .providers.base import Message, CompletionRequest


class ConversationSummarizer:
    """
    Summarize conversations for context management.
    """
    
    SUMMARIZE_PROMPT = """Summarize the following conversation concisely.
Focus on:
- Main topics discussed
- Important facts or information shared
- User preferences or requests
- Any decisions or conclusions

Keep the summary under 200 words.

Conversation:
{conversation}

Summary:"""

    def __init__(self, llm_service):
        self._llm = llm_service
    
    async def summarize(self, messages: List[Message]) -> str:
        """
        Summarize a list of messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary text
        """
        # Format conversation
        conversation = []
        for msg in messages:
            if msg.role == "user":
                name = msg.name or "User"
                conversation.append(f"{name}: {msg.content}")
            elif msg.role == "assistant":
                conversation.append(f"Assistant: {msg.content}")
        
        conversation_text = "\n".join(conversation)
        
        # Request summary
        prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation_text)
        
        result = await self._llm.chat(
            message=prompt,
            temperature=0.3,  # More deterministic for summaries
        )
        
        if result.success:
            return result.content
        else:
            # Fallback: just list topics
            return f"Conversation with {len(messages)} messages"
    
    async def extract_memories(self, messages: List[Message]) -> List[dict]:
        """
        Extract memorable facts from messages.
        
        Returns:
            List of memory dicts with category, content, importance
        """
        EXTRACT_PROMPT = """Extract important facts from this conversation that should be remembered.
Return as a JSON list of objects with 'category', 'content', and 'importance' (1-5).

Categories: 'fact', 'preference', 'topic'

Example:
[
  {"category": "preference", "content": "User prefers Python over JavaScript", "importance": 3},
  {"category": "fact", "content": "User is working on a chatbot project", "importance": 2}
]

Conversation:
{conversation}

Facts (JSON):"""

        conversation_text = "\n".join(
            f"{msg.role}: {msg.content}" for msg in messages
        )
        
        result = await self._llm.chat(
            message=EXTRACT_PROMPT.format(conversation=conversation_text),
            temperature=0.2,
        )
        
        if result.success:
            try:
                import json
                return json.loads(result.content)
            except:
                return []
        
        return []
```

### 2.5 Storage Class

```python
# plugins/llm/storage.py

from typing import List, Optional
from datetime import datetime
from common.database_service import DatabaseService


class LLMStorage:
    """Database operations for LLM memory."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def create_tables(self) -> None:
        """Create LLM tables if not exists."""
        ...
    
    # === Messages ===
    
    async def save_message(
        self,
        channel: str,
        user_id: Optional[str],
        role: str,
        content: str,
    ) -> int:
        """Save a message and return its ID."""
        result = await self.db.execute(
            """
            INSERT INTO llm_messages (channel, user_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (channel, user_id, role, content)
        )
        return result.lastrowid
    
    async def get_recent_messages(
        self, 
        channel: str, 
        limit: int
    ) -> List[dict]:
        """Get recent messages for a channel."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM llm_messages
            WHERE channel = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (channel, limit)
        )
        # Reverse to get chronological order
        return list(reversed([dict(r) for r in rows]))
    
    async def get_message_count(self, channel: str) -> int:
        """Get total message count for channel."""
        row = await self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM llm_messages WHERE channel = ?",
            (channel,)
        )
        return row["cnt"]
    
    async def get_unsummarized_count(self, channel: str) -> int:
        """Get count of unsummarized messages."""
        row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as cnt FROM llm_messages 
            WHERE channel = ? AND summarized = FALSE
            """,
            (channel,)
        )
        return row["cnt"]
    
    async def get_unsummarized_messages(self, channel: str) -> List[dict]:
        """Get all unsummarized messages."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM llm_messages
            WHERE channel = ? AND summarized = FALSE
            ORDER BY created_at
            """,
            (channel,)
        )
        return [dict(r) for r in rows]
    
    async def mark_summarized(self, message_ids: List[int]) -> None:
        """Mark messages as summarized."""
        placeholders = ",".join("?" * len(message_ids))
        await self.db.execute(
            f"UPDATE llm_messages SET summarized = TRUE WHERE id IN ({placeholders})",
            message_ids
        )
    
    async def clear_messages(self, channel: str) -> int:
        """Clear all messages for a channel."""
        result = await self.db.execute(
            "DELETE FROM llm_messages WHERE channel = ?",
            (channel,)
        )
        return result.rowcount
    
    # === Summaries ===
    
    async def save_summary(
        self,
        channel: str,
        summary: str,
        messages_from: int,
        messages_to: int,
        message_count: int,
    ) -> None:
        """Save a conversation summary."""
        await self.db.execute(
            """
            INSERT INTO llm_summaries 
            (channel, summary, messages_from, messages_to, message_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (channel, summary, messages_from, messages_to, message_count)
        )
    
    async def get_summaries(
        self, 
        channel: str, 
        limit: int = 3
    ) -> List[dict]:
        """Get recent summaries for a channel."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM llm_summaries
            WHERE channel = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (channel, limit)
        )
        return [dict(r) for r in rows]
    
    # === Memories ===
    
    async def save_memory(
        self,
        channel: str,
        user_id: Optional[str],
        category: str,
        content: str,
        importance: int,
    ) -> int:
        """Save a memory."""
        result = await self.db.execute(
            """
            INSERT INTO llm_memories (channel, user_id, category, content, importance)
            VALUES (?, ?, ?, ?, ?)
            """,
            (channel, user_id, category, content, importance)
        )
        return result.lastrowid
    
    async def search_memories(
        self,
        channel: str,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[dict]:
        """
        Search memories by keyword.
        
        Simple LIKE matching. Could be enhanced with FTS or embeddings.
        """
        # Split query into keywords
        keywords = query.lower().split()
        
        if not keywords:
            return []
        
        # Build LIKE conditions
        conditions = ["channel = ?"]
        params = [channel]
        
        for keyword in keywords[:5]:  # Limit keywords
            conditions.append("LOWER(content) LIKE ?")
            params.append(f"%{keyword}%")
        
        if user_id:
            conditions.append("(user_id IS NULL OR user_id = ?)")
            params.append(user_id)
        
        params.append(limit)
        
        query_sql = f"""
            SELECT * FROM llm_memories
            WHERE {" AND ".join(conditions)}
            ORDER BY importance DESC, last_accessed DESC NULLS LAST
            LIMIT ?
        """
        
        rows = await self.db.fetch_all(query_sql, params)
        return [dict(r) for r in rows]
    
    async def touch_memory(self, memory_id: int) -> None:
        """Update last_accessed for a memory."""
        await self.db.execute(
            "UPDATE llm_memories SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
            (memory_id,)
        )
    
    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory."""
        result = await self.db.execute(
            "DELETE FROM llm_memories WHERE id = ?",
            (memory_id,)
        )
        return result.rowcount > 0
    
    async def get_user_memories(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[dict]:
        """Get memories associated with a user."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM llm_memories
            WHERE user_id = ?
            ORDER BY importance DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        return [dict(r) for r in rows]
```

### 2.6 Extended Plugin

```python
# plugins/llm/plugin.py (extensions for memory)

class LLMPlugin(PluginBase):
    """Extended with memory management."""
    
    async def setup(self) -> None:
        """Setup with memory."""
        # ... existing setup ...
        
        # Initialize storage
        db_service = await get_database_service()
        self.storage = LLMStorage(db_service)
        await self.storage.create_tables()
        
        # Initialize memory
        self.memory = ConversationMemory(
            storage=self.storage,
            config=MemoryConfig(
                max_messages_in_context=self.config.get("max_context", 20),
                summarize_after_messages=self.config.get("summarize_after", 50),
            ),
        )
        
        # Initialize summarizer
        self.summarizer = ConversationSummarizer(self.service)
        
        # Add memory commands
        await self.subscribe("rosey.command.chat.remember", self._handle_remember)
        await self.subscribe("rosey.command.chat.recall", self._handle_recall)
        await self.subscribe("rosey.command.chat.forget", self._handle_forget)
    
    async def _handle_chat(self, msg) -> None:
        """Extended chat handler with memory."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        message = data.get("args", "").strip()
        
        if not message:
            return await self._reply_usage(msg, "chat <message>")
        
        # Handle subcommands
        if message.lower() == "reset":
            count = await self.memory.reset_context(channel)
            return await self._reply(msg, f"🔄 Conversation reset! ({count} messages cleared)")
        
        # ... other subcommands ...
        
        # Build context with memory
        persona = self._personas.get(channel, "default")
        system_prompt = SystemPrompts.get(persona)
        
        context = await self.memory.get_context(
            channel=channel,
            system_prompt=system_prompt,
            user_id=user,
            query=message,  # For memory recall
        )
        
        # Get response using context
        messages = context.to_messages()
        messages.append(Message(role="user", content=message, name=user))
        
        try:
            response = await self.service.complete_raw(
                messages=messages,
                temperature=self.config.get("temperature", 0.7),
            )
            
            # Store messages in memory
            await self.memory.add_message(channel, "user", message, user)
            await self.memory.add_message(channel, "assistant", response.content)
            
            await self._reply(msg, f"🤖 {response.content}")
            
        except ProviderError as e:
            await self._reply_error(msg, f"AI error: {e}")
    
    async def _handle_remember(self, msg) -> None:
        """Handle !chat remember <fact>."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        fact = data.get("args", "").strip()
        
        if not fact:
            return await self._reply_usage(msg, "remember <fact>")
        
        await self.memory.remember(
            channel=channel,
            content=fact,
            category="fact",
            user_id=user,
            importance=3,
        )
        
        await self._reply(msg, f"💾 I'll remember that!")
    
    async def _handle_recall(self, msg) -> None:
        """Handle !chat recall <topic>."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        topic = data.get("args", "").strip()
        
        if not topic:
            return await self._reply_usage(msg, "recall <topic>")
        
        memories = await self.memory.recall(
            channel=channel,
            query=topic,
            user_id=user,
            limit=5,
        )
        
        if not memories:
            return await self._reply(msg, f"🤔 I don't recall anything about '{topic}'")
        
        lines = ["💭 Here's what I remember:\n"]
        for m in memories:
            lines.append(f"• {m}")
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_forget(self, msg) -> None:
        """Handle !chat forget (clears memories for channel)."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        
        # Clear all memories for channel
        await self.storage.db.execute(
            "DELETE FROM llm_memories WHERE channel = ?",
            (channel,)
        )
        
        await self._reply(msg, "🗑️ Memories cleared!")
```

---

## 3. Implementation Steps

### Step 1: Database Schema (30 minutes)

1. Create Alembic migration
2. Run migration
3. Verify tables

### Step 2: Implement Storage (1.5 hours)

1. Implement LLMStorage class
2. Implement message operations
3. Implement summary operations
4. Implement memory operations
5. Write tests

### Step 3: Implement Memory Manager (2 hours)

1. Implement ConversationMemory
2. Implement context building
3. Implement memory recall
4. Implement cache management
5. Write tests

### Step 4: Implement Summarizer (1 hour)

1. Implement ConversationSummarizer
2. Implement memory extraction
3. Write tests

### Step 5: Extend Plugin (1.5 hours)

1. Wire up memory to chat handler
2. Add memory commands
3. Integrate summarization
4. Test full flow

### Step 6: Testing (1 hour)

1. Test context building
2. Test memory recall
3. Test summarization
4. Test persistence

---

## 4. Acceptance Criteria

### 4.1 Functional

- [ ] Conversation context maintained across messages
- [ ] `!chat remember <fact>` stores memories
- [ ] `!chat recall <topic>` retrieves relevant memories
- [ ] `!chat forget` clears memories
- [ ] Conversations persist across restarts
- [ ] Long conversations auto-summarize

### 4.2 Technical

- [ ] Memory persisted to database
- [ ] Context window managed properly
- [ ] Summarization works
- [ ] Test coverage > 85%

---

## 5. Sample Interactions

```
User: !chat My name is Alice and I love programming
Rosey: 🤖 Nice to meet you, Alice! What kind of programming 
       do you enjoy?

User: !chat remember Alice prefers Python and works on AI projects
Rosey: 💾 I'll remember that!

[Later]

User: !chat recall Alice
Rosey: 💭 Here's what I remember:
       • Alice prefers Python and works on AI projects

User: !chat What was my name again?
Rosey: 🤖 Your name is Alice! You mentioned you love 
       programming, particularly Python and AI projects.

User: !chat reset
Rosey: 🔄 Conversation reset! (15 messages cleared)
       Note: Memories are still available.

User: !chat forget
Rosey: 🗑️ Memories cleared!
```

---

**Commit Message Template:**
```
feat(plugins): Add LLM memory and context

- Add conversation memory persistence
- Add per-channel context management
- Add conversation summarization
- Add memory recall (!chat recall)
- Add fact storage (!chat remember)

Implements: SPEC-Sortie-5-LLMMemory.md
Related: PRD-Core-Migrations.md
Part: 2 of 3 (LLM Migration)
```
