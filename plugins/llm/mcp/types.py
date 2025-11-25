"""
MCP Type Definitions
====================

Type definitions for Model Context Protocol tools.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ParameterType(Enum):
    """Supported parameter types for tool parameters."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """
    Definition of a tool parameter.
    
    Attributes:
        name: Parameter name
        type: Parameter type
        description: Human-readable description
        required: Whether parameter is required
        default: Default value if not provided
        enum: List of allowed values (optional)
    """
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class ToolDefinition:
    """
    Complete tool definition.
    
    This is what gets sent to the LLM to describe available tools.
    
    Attributes:
        name: Tool name (must be unique)
        description: What the tool does
        parameters: List of tool parameters
        category: Tool category for organization
        requires_confirmation: Whether tool needs user confirmation
        cooldown_seconds: Minimum seconds between calls
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    
    # Metadata
    category: str = "general"
    requires_confirmation: bool = False
    cooldown_seconds: int = 0
    
    def to_schema(self) -> dict:
        """
        Convert to JSON Schema for LLM.
        
        Returns standard tool schema format used by OpenAI/Anthropic.
        
        Returns:
            Dictionary with tool schema
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type.value,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
                
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }


@dataclass
class ToolCall:
    """
    A tool call requested by the LLM.
    
    Attributes:
        id: Unique call ID
        name: Tool name to call
        arguments: Tool arguments as dictionary
    """
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """
    Result of executing a tool.
    
    Attributes:
        tool_call_id: ID of the tool call that produced this result
        success: Whether execution succeeded
        result: Result value (if success=True)
        error: Error message (if success=False)
    """
    tool_call_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    
    def to_message(self) -> str:
        """
        Format as message for LLM.
        
        Returns:
            String representation of result
        """
        if self.success:
            return str(self.result)
        else:
            return f"Error: {self.error}"
