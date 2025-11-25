"""
MCP Tool Registry
=================

Registry for managing available MCP tools.
"""

import time
import logging
from typing import Callable, Dict, List, Optional

from .types import ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class Tool:
    """
    Wrapper for a registered tool.
    
    Tracks tool metadata, usage statistics, and cooldowns.
    """
    
    def __init__(
        self,
        definition: ToolDefinition,
        handler: Callable,
    ):
        """
        Initialize tool wrapper.
        
        Args:
            definition: Tool definition with schema
            handler: Async function to execute tool
        """
        self.definition = definition
        self.handler = handler
        self._last_used: Dict[str, float] = {}  # user -> timestamp
        self._call_count = 0
    
    async def execute(
        self, 
        arguments: Dict, 
        context: dict
    ) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            arguments: Tool arguments
            context: Execution context (channel, user, call_id)
            
        Returns:
            ToolResult with success/failure and result/error
        """
        try:
            # Check cooldown
            user = context.get("user", "")
            if self.definition.cooldown_seconds > 0 and user:
                last_used = self._last_used.get(user, 0)
                elapsed = time.time() - last_used
                if elapsed < self.definition.cooldown_seconds:
                    remaining = self.definition.cooldown_seconds - elapsed
                    return ToolResult(
                        tool_call_id=context.get("call_id", ""),
                        success=False,
                        error=f"Tool on cooldown. Wait {remaining:.1f}s",
                    )
            
            # Execute handler
            result = await self.handler(arguments, context)
            
            # Update stats
            if user:
                self._last_used[user] = time.time()
            self._call_count += 1
            
            return ToolResult(
                tool_call_id=context.get("call_id", ""),
                success=True,
                result=result,
            )
            
        except Exception as e:
            logger.error(f"Tool {self.definition.name} failed: {e}", exc_info=True)
            return ToolResult(
                tool_call_id=context.get("call_id", ""),
                success=False,
                error=str(e),
            )
    
    @property
    def call_count(self) -> int:
        """Get total number of calls to this tool."""
        return self._call_count


class ToolRegistry:
    """
    Registry for all available MCP tools.
    
    Tools can be registered by:
    1. The LLM plugin itself (built-in tools)
    2. Other plugins via NATS (plugin-provided tools)
    
    Provides tool discovery, validation, and schema generation.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
        logger.info("Tool registry initialized")
    
    def register(
        self,
        definition: ToolDefinition,
        handler: Callable,
    ) -> None:
        """
        Register a tool.
        
        Args:
            definition: Tool definition with schema
            handler: Async function to execute tool
            
        Raises:
            ValueError: If tool name already registered
        """
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        
        tool = Tool(definition, handler)
        self._tools[definition.name] = tool
        
        # Track by category
        if definition.category not in self._categories:
            self._categories[definition.category] = []
        self._categories[definition.category].append(definition.name)
        
        logger.info(
            f"Registered tool: {definition.name} "
            f"(category: {definition.category})"
        )
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            tool = self._tools.pop(name)
            category = tool.definition.category
            if category in self._categories:
                self._categories[category].remove(name)
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool wrapper or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(
        self, 
        category: Optional[str] = None
    ) -> List[ToolDefinition]:
        """
        List available tools.
        
        Args:
            category: Filter by category (optional)
            
        Returns:
            List of tool definitions
        """
        if category:
            names = self._categories.get(category, [])
            return [self._tools[n].definition for n in names]
        return [t.definition for t in self._tools.values()]
    
    def get_schemas(
        self,
        category: Optional[str] = None,
    ) -> List[dict]:
        """
        Get tool schemas for LLM.
        
        Args:
            category: Filter by category (optional)
            
        Returns:
            List of tool schemas in standard format
        """
        tools = self.list_tools(category)
        return [t.to_schema() for t in tools]
    
    def categories(self) -> List[str]:
        """
        List tool categories.
        
        Returns:
            List of category names
        """
        return list(self._categories.keys())
    
    def count(self) -> int:
        """
        Get total number of registered tools.
        
        Returns:
            Tool count
        """
        return len(self._tools)
    
    def stats(self) -> Dict[str, int]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with tool call counts
        """
        return {
            name: tool.call_count
            for name, tool in self._tools.items()
        }
