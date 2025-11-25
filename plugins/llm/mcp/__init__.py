"""
Model Context Protocol (MCP) Foundation
========================================

Provides tool calling capabilities for LLMs through the Model Context Protocol.

Key Components:
- types.py: Type definitions for tools, parameters, and results
- registry.py: Tool registration and discovery
- executor.py: Tool execution pipeline
- parser.py: Parse tool calls from LLM responses
- tools/: Built-in tool implementations

Example:
    # Register a tool
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="calculate",
            description="Perform mathematical calculations",
            parameters=[
                ToolParameter("expression", ParameterType.STRING, "Math expression")
            ]
        ),
        handler=calculate_handler
    )
    
    # Execute tool calls
    executor = ToolExecutor(registry)
    results = await executor.execute(tool_calls, context)
"""

from .types import (
    ParameterType,
    ToolParameter,
    ToolDefinition,
    ToolCall,
    ToolResult,
)
from .registry import Tool, ToolRegistry
from .executor import ToolExecutor
from .parser import ToolCallParser

__all__ = [
    "ParameterType",
    "ToolParameter",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "Tool",
    "ToolRegistry",
    "ToolExecutor",
    "ToolCallParser",
]
