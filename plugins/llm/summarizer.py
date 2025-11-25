"""
LLM Conversation Summarizer
============================

Summarizes conversations using LLM for context management.

Features:
- LLM-based conversation summarization
- Memory extraction from conversations
- Configurable summarization prompts
- JSON-based structured output

Usage:
    summarizer = ConversationSummarizer(llm_service)
    
    # Summarize conversation
    summary = await summarizer.summarize(messages)
    
    # Extract memories
    memories = await summarizer.extract_memories(messages)
"""

import json
from typing import List
from .providers.base import Message


class ConversationSummarizer:
    """
    Summarize conversations for context management.
    
    Uses LLM to create concise summaries and extract memorable facts.
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

    EXTRACT_PROMPT = """Extract important facts from this conversation that should be remembered.
Return as a JSON list of objects with 'category', 'content', and 'importance' (1-5).

Categories:
- 'fact': Factual information
- 'preference': User preferences or likes/dislikes
- 'topic': Topics of interest

Example output:
[
  {{"category": "preference", "content": "User prefers Python over JavaScript", "importance": 3}},
  {{"category": "fact", "content": "User is working on a chatbot project", "importance": 2}},
  {{"category": "topic", "content": "Interested in AI and machine learning", "importance": 4}}
]

Conversation:
{conversation}

Facts (JSON only, no explanation):"""

    def __init__(self, llm_service):
        """
        Initialize summarizer with LLM service.
        
        Args:
            llm_service: LLMService instance for completions
        """
        self._llm = llm_service
    
    async def summarize(self, messages: List[Message]) -> str:
        """
        Summarize a list of messages.
        
        Uses LLM with a special summarization prompt to create a concise
        summary of the conversation.
        
        Args:
            messages: Messages to summarize (chronological order)
            
        Returns:
            Summary text (under 200 words)
        """
        if not messages:
            return "Empty conversation"
        
        # Format conversation for summarization
        conversation = []
        for msg in messages:
            if msg.role == "user":
                name = msg.name or "User"
                conversation.append(f"{name}: {msg.content}")
            elif msg.role == "assistant":
                conversation.append(f"Assistant: {msg.content}")
            # Skip system messages in summary
        
        conversation_text = "\n".join(conversation)
        
        # Request summary from LLM
        prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation_text)
        
        try:
            result = await self._llm.chat(
                message=prompt,
                temperature=0.3,  # More deterministic for summaries
            )
            
            if result.success:
                return result.content.strip()
            else:
                # Fallback: basic stats
                return f"Conversation with {len(messages)} messages"
        except Exception as e:
            return f"Summarization failed: {str(e)}"
    
    async def extract_memories(
        self,
        messages: List[Message],
        user_id: str = None
    ) -> List[dict]:
        """
        Extract memorable facts from messages.
        
        Uses LLM to identify important information that should be remembered
        for future conversations.
        
        Args:
            messages: Messages to analyze
            user_id: Optional user identifier for context
            
        Returns:
            List of memory dicts with 'category', 'content', 'importance'
            Example: [
                {
                    "category": "preference",
                    "content": "User likes Python",
                    "importance": 3
                }
            ]
        """
        if not messages:
            return []
        
        # Format conversation
        conversation = []
        for msg in messages:
            role = msg.role
            name = msg.name or "Unknown"
            conversation.append(f"{role} ({name}): {msg.content}")
        
        conversation_text = "\n".join(conversation)
        
        # Request memory extraction
        prompt = self.EXTRACT_PROMPT.format(conversation=conversation_text)
        
        try:
            result = await self._llm.chat(
                message=prompt,
                temperature=0.2,  # Very deterministic for structured output
            )
            
            if not result.success:
                return []
            
            # Parse JSON response
            content = result.content.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            memories = json.loads(content)
            
            # Validate structure
            valid_memories = []
            for m in memories:
                if isinstance(m, dict) and "category" in m and "content" in m:
                    valid_memories.append({
                        "category": m.get("category", "fact"),
                        "content": m.get("content", ""),
                        "importance": int(m.get("importance", 1)),
                    })
            
            return valid_memories
            
        except json.JSONDecodeError:
            # LLM didn't return valid JSON
            return []
        except Exception:
            # Other errors (network, timeout, etc.)
            return []
