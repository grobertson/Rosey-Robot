"""
Tests for MCP Type Definitions
==============================
"""

import pytest
from plugins.llm.mcp.types import (
    ParameterType,
    ToolParameter,
    ToolDefinition,
    ToolCall,
    ToolResult,
)


def test_parameter_type_enum():
    """Test ParameterType enum values."""
    assert ParameterType.STRING.value == "string"
    assert ParameterType.NUMBER.value == "number"
    assert ParameterType.INTEGER.value == "integer"
    assert ParameterType.BOOLEAN.value == "boolean"
    assert ParameterType.ARRAY.value == "array"
    assert ParameterType.OBJECT.value == "object"


def test_tool_parameter_creation():
    """Test creating a tool parameter."""
    param = ToolParameter(
        name="text",
        type=ParameterType.STRING,
        description="Input text",
        required=True,
    )
    
    assert param.name == "text"
    assert param.type == ParameterType.STRING
    assert param.description == "Input text"
    assert param.required is True
    assert param.default is None
    assert param.enum is None


def test_tool_parameter_with_defaults():
    """Test parameter with default value."""
    param = ToolParameter(
        name="count",
        type=ParameterType.INTEGER,
        description="Number of items",
        required=False,
        default=10,
    )
    
    assert param.default == 10
    assert param.required is False


def test_tool_parameter_with_enum():
    """Test parameter with enum values."""
    param = ToolParameter(
        name="color",
        type=ParameterType.STRING,
        description="Color choice",
        enum=["red", "green", "blue"],
    )
    
    assert param.enum == ["red", "green", "blue"]


def test_tool_definition_basic():
    """Test basic tool definition."""
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
    )
    
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.parameters == []
    assert tool.category == "general"
    assert tool.requires_confirmation is False
    assert tool.cooldown_seconds == 0


def test_tool_definition_with_parameters():
    """Test tool definition with parameters."""
    tool = ToolDefinition(
        name="search",
        description="Search for items",
        parameters=[
            ToolParameter("query", ParameterType.STRING, "Search query"),
            ToolParameter("limit", ParameterType.INTEGER, "Max results", required=False, default=10),
        ],
        category="search",
    )
    
    assert len(tool.parameters) == 2
    assert tool.parameters[0].name == "query"
    assert tool.parameters[1].name == "limit"
    assert tool.category == "search"


def test_tool_definition_to_schema():
    """Test converting tool definition to schema."""
    tool = ToolDefinition(
        name="calculate",
        description="Do math",
        parameters=[
            ToolParameter("expression", ParameterType.STRING, "Math expression", required=True),
            ToolParameter("precision", ParameterType.INTEGER, "Decimal places", required=False, default=2),
        ],
    )
    
    schema = tool.to_schema()
    
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calculate"
    assert schema["function"]["description"] == "Do math"
    
    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "expression" in params["properties"]
    assert "precision" in params["properties"]
    assert params["properties"]["expression"]["type"] == "string"
    assert params["properties"]["precision"]["type"] == "integer"
    assert params["properties"]["precision"]["default"] == 2
    assert params["required"] == ["expression"]


def test_tool_definition_to_schema_with_enum():
    """Test schema generation with enum parameter."""
    tool = ToolDefinition(
        name="set_mode",
        description="Set mode",
        parameters=[
            ToolParameter(
                "mode",
                ParameterType.STRING,
                "Mode to set",
                enum=["fast", "slow", "medium"]
            ),
        ],
    )
    
    schema = tool.to_schema()
    mode_prop = schema["function"]["parameters"]["properties"]["mode"]
    
    assert mode_prop["enum"] == ["fast", "slow", "medium"]


def test_tool_call_creation():
    """Test creating a tool call."""
    call = ToolCall(
        id="call_123",
        name="calculate",
        arguments={"expression": "2 + 2"},
    )
    
    assert call.id == "call_123"
    assert call.name == "calculate"
    assert call.arguments == {"expression": "2 + 2"}


def test_tool_result_success():
    """Test successful tool result."""
    result = ToolResult(
        tool_call_id="call_123",
        success=True,
        result="4",
    )
    
    assert result.tool_call_id == "call_123"
    assert result.success is True
    assert result.result == "4"
    assert result.error is None


def test_tool_result_failure():
    """Test failed tool result."""
    result = ToolResult(
        tool_call_id="call_456",
        success=False,
        error="Division by zero",
    )
    
    assert result.tool_call_id == "call_456"
    assert result.success is False
    assert result.result is None
    assert result.error == "Division by zero"


def test_tool_result_to_message_success():
    """Test formatting successful result as message."""
    result = ToolResult(
        tool_call_id="call_1",
        success=True,
        result="The answer is 42",
    )
    
    message = result.to_message()
    assert message == "The answer is 42"


def test_tool_result_to_message_failure():
    """Test formatting failed result as message."""
    result = ToolResult(
        tool_call_id="call_2",
        success=False,
        error="Invalid input",
    )
    
    message = result.to_message()
    assert message == "Error: Invalid input"
