# Model Context Protocol (MCP) Foundation

Model Context Protocol support for the LLM plugin, enabling tool calling capabilities.

## Overview

MCP allows the LLM to call functions/tools to extend its capabilities beyond text generation. Tools can perform calculations, get current time, search data, and more.

## Architecture

```
plugins/llm/mcp/
├── types.py          # Type definitions (ToolDefinition, ToolParameter, ToolCall, ToolResult)
├── registry.py       # Tool registration and discovery
├── executor.py       # Tool execution with validation and error handling
├── parser.py         # Parse tool calls from LLM responses
└── tools/            # Built-in tool implementations
    ├── calculator.py # Mathematical calculations
    └── time.py       # Current time/date
```

## Core Components

### ToolDefinition

Defines a tool's interface:
- Name and description
- Parameters with types and validation
- Metadata (category, cooldown, confirmation)

### ToolRegistry

Manages available tools:
- Register/unregister tools
- List tools by category
- Generate schemas for LLM
- Track usage statistics

### ToolExecutor

Executes tool calls safely:
- Parameter validation
- Timeout handling
- Error handling
- Sequential or parallel execution

### ToolCallParser

Parses tool calls from LLM responses:
- OpenAI format
- Anthropic format
- Auto-detection

## Built-in Tools

### Calculator
Safely evaluates mathematical expressions.
```python
calculate(expression="2 + 2 * 5")  # Returns "2 + 2 * 5 = 12"
```

### Time
Gets current date and time.
```python
get_current_time(format="%Y-%m-%d")  # Returns "2025-11-25"
```

## Usage Example

```python
from plugins.llm.mcp import ToolRegistry, ToolExecutor, ToolDefinition, ToolParameter, ParameterType

# Create registry
registry = ToolRegistry()

# Register built-in tools
from plugins.llm.mcp.tools.calculator import CALCULATOR_TOOL, calculate
registry.register(CALCULATOR_TOOL, calculate)

# Create executor
executor = ToolExecutor(registry, timeout=30.0)

# Execute tool calls from LLM
tool_calls = [
    ToolCall(id="call_1", name="calculate", arguments={"expression": "10 * 5"})
]
context = {"channel": "test", "user": "alice"}
results = await executor.execute(tool_calls, context)

# Check results
for result in results:
    if result.success:
        print(f"Result: {result.result}")
    else:
        print(f"Error: {result.error}")
```

## Creating Custom Tools

```python
from plugins.llm.mcp import ToolDefinition, ToolParameter, ParameterType

# Define tool
MY_TOOL = ToolDefinition(
    name="my_tool",
    description="Does something useful",
    parameters=[
        ToolParameter(
            name="input",
            type=ParameterType.STRING,
            description="Input value",
            required=True
        )
    ],
    category="custom",
    cooldown_seconds=5,  # 5 second cooldown between calls
)

# Implement handler
async def my_tool_handler(arguments, context):
    input_val = arguments["input"]
    # Do something...
    return f"Processed: {input_val}"

# Register
registry.register(MY_TOOL, my_tool_handler)
```

## Parameter Types

- `STRING`: Text values
- `NUMBER`: Floating point numbers
- `INTEGER`: Whole numbers
- `BOOLEAN`: True/False
- `ARRAY`: Lists
- `OBJECT`: Dictionaries

## Tool Categories

- `utility`: General utility tools (calculator, time)
- `search`: Search and retrieval tools
- `data`: Data manipulation tools
- `custom`: User-defined tools

## Safety Features

1. **Parameter Validation**: Type checking and required field validation
2. **Timeout Protection**: Maximum execution time per tool (default: 30s)
3. **Cooldown**: Prevent rapid repeated calls
4. **Safe Execution**: Tools run in isolated async context
5. **Error Handling**: All exceptions caught and reported

## Testing

```bash
# Run MCP tests
python -m pytest plugins/llm/mcp/tests/ -v

# Run with coverage
python -m pytest plugins/llm/mcp/tests/ --cov=plugins/llm/mcp --cov-report=term
```

## Future Enhancements

- Plugin-provided tools via NATS
- Multi-step tool chains
- Tool permissions and access control
- External MCP server integration
- Autonomous agent loops
