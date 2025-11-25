# SPEC: Sortie 7 - MCP Foundation

**Sprint:** 19 - Core Migrations  
**Sortie:** 7 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** HIGH - Future-proofs AI capabilities  
**Prerequisites:** Sortie 6 (LLM Service & Events)

---

## 1. Overview

### 1.1 Purpose

Implement Model Context Protocol (MCP) foundation in the LLM plugin:

- Tool definition framework
- Tool execution pipeline
- Built-in tools (calculator, time, search)
- Plugin-provided tools
- Tool discovery and registration

MCP enables the LLM to call functions/tools, making Rosey more capable.

### 1.2 What is MCP?

Model Context Protocol is a standard for connecting LLMs to external tools and data sources. It allows:

1. **Tool Calling**: LLM requests to execute functions
2. **Context Injection**: Providing LLM with relevant data
3. **Structured Output**: Getting typed responses from LLM

### 1.3 Scope

**In Scope:**
- Tool definition framework
- Tool registration system
- Tool execution pipeline
- Built-in tools (calculator, time, dice)
- Error handling for tool calls
- Tool schema validation

**Out of Scope (Future):**
- External MCP servers (weather API)
- Complex multi-tool chains
- Autonomous agent loops

### 1.4 Dependencies

- Sortie 6 (LLM Service) - MUST be complete
- Provider with tool support (Claude/OpenAI)

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/llm/
├── ...existing files...
├── mcp/
│   ├── __init__.py
│   ├── types.py          # Tool type definitions
│   ├── registry.py       # Tool registration
│   ├── executor.py       # Tool execution
│   ├── parser.py         # Parse tool calls from LLM
│   └── tools/
│       ├── __init__.py
│       ├── calculator.py  # Math operations
│       ├── time.py        # Time/date operations
│       ├── dice.py        # Dice rolling (bridges to dice-roller)
│       └── search.py      # Memory search
└── tests/
    └── mcp/
        ├── test_registry.py
        ├── test_executor.py
        ├── test_parser.py
        └── test_tools.py
```

### 2.2 Tool Definition

```python
# plugins/llm/mcp/types.py

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum


class ParameterType(Enum):
    """Supported parameter types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None  # Allowed values


@dataclass
class ToolDefinition:
    """
    Complete tool definition.
    
    This is what gets sent to the LLM to describe available tools.
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    
    # Metadata
    category: str = "general"
    requires_confirmation: bool = False
    cooldown_seconds: int = 0
    
    def to_schema(self) -> dict:
        """Convert to JSON Schema for LLM."""
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
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_call_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    
    def to_message(self) -> str:
        """Format as message for LLM."""
        if self.success:
            return str(self.result)
        else:
            return f"Error: {self.error}"
```

### 2.3 Tool Registry

```python
# plugins/llm/mcp/registry.py

from typing import Callable, Dict, List, Optional
from .types import ToolDefinition, ToolCall, ToolResult


class Tool:
    """
    Wrapper for a registered tool.
    """
    
    def __init__(
        self,
        definition: ToolDefinition,
        handler: Callable,
    ):
        self.definition = definition
        self.handler = handler
        self._last_used: Dict[str, float] = {}  # user -> timestamp
    
    async def execute(
        self, 
        arguments: Dict, 
        context: dict
    ) -> ToolResult:
        """Execute the tool."""
        try:
            result = await self.handler(arguments, context)
            return ToolResult(
                tool_call_id=context.get("call_id", ""),
                success=True,
                result=result,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=context.get("call_id", ""),
                success=False,
                error=str(e),
            )


class ToolRegistry:
    """
    Registry for all available tools.
    
    Tools can be registered by:
    1. The LLM plugin itself (built-in tools)
    2. Other plugins via NATS (plugin-provided tools)
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
    
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
        """
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        
        tool = Tool(definition, handler)
        self._tools[definition.name] = tool
        
        # Track by category
        if definition.category not in self._categories:
            self._categories[definition.category] = []
        self._categories[definition.category].append(definition.name)
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            tool = self._tools.pop(name)
            category = tool.definition.category
            if category in self._categories:
                self._categories[category].remove(name)
            return True
        return False
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(
        self, 
        category: Optional[str] = None
    ) -> List[ToolDefinition]:
        """List available tools."""
        if category:
            names = self._categories.get(category, [])
            return [self._tools[n].definition for n in names]
        return [t.definition for t in self._tools.values()]
    
    def get_schemas(
        self,
        category: Optional[str] = None,
    ) -> List[dict]:
        """Get tool schemas for LLM."""
        tools = self.list_tools(category)
        return [t.to_schema() for t in tools]
    
    def categories(self) -> List[str]:
        """List tool categories."""
        return list(self._categories.keys())
```

### 2.4 Tool Executor

```python
# plugins/llm/mcp/executor.py

import asyncio
from typing import List, Optional
from .types import ToolCall, ToolResult
from .registry import ToolRegistry


class ToolExecutor:
    """
    Executes tool calls from LLM responses.
    
    Handles:
    - Parameter validation
    - Execution with timeout
    - Error handling
    - Parallel execution (when safe)
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        timeout: float = 30.0,
    ):
        self._registry = registry
        self._timeout = timeout
    
    async def execute(
        self,
        tool_calls: List[ToolCall],
        context: dict,
    ) -> List[ToolResult]:
        """
        Execute a list of tool calls.
        
        Args:
            tool_calls: List of tool calls from LLM
            context: Execution context (channel, user, etc.)
            
        Returns:
            List of tool results
        """
        results = []
        
        for call in tool_calls:
            result = await self._execute_single(call, context)
            results.append(result)
        
        return results
    
    async def execute_parallel(
        self,
        tool_calls: List[ToolCall],
        context: dict,
    ) -> List[ToolResult]:
        """
        Execute tool calls in parallel.
        
        Only use when tools are independent.
        """
        tasks = [
            self._execute_single(call, context)
            for call in tool_calls
        ]
        return await asyncio.gather(*tasks)
    
    async def _execute_single(
        self,
        call: ToolCall,
        context: dict,
    ) -> ToolResult:
        """Execute a single tool call."""
        tool = self._registry.get(call.name)
        
        if not tool:
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=f"Unknown tool: {call.name}",
            )
        
        # Add call ID to context
        exec_context = {**context, "call_id": call.id}
        
        # Validate parameters
        validation_error = self._validate_params(
            call.arguments, 
            tool.definition
        )
        if validation_error:
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=validation_error,
            )
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(call.arguments, exec_context),
                timeout=self._timeout,
            )
            return result
            
        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=f"Tool '{call.name}' timed out after {self._timeout}s",
            )
    
    def _validate_params(
        self,
        arguments: dict,
        definition: ToolDefinition,
    ) -> Optional[str]:
        """Validate parameters against schema."""
        # Check required parameters
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return f"Missing required parameter: {param.name}"
            
            if param.name in arguments:
                value = arguments[param.name]
                
                # Check enum
                if param.enum and value not in param.enum:
                    return f"Invalid value for {param.name}: must be one of {param.enum}"
        
        return None
```

### 2.5 Built-in Tools

```python
# plugins/llm/mcp/tools/calculator.py

import math
import operator
from typing import Dict, Any
from ..types import ToolDefinition, ToolParameter, ParameterType


CALCULATOR_DEFINITION = ToolDefinition(
    name="calculator",
    description="Perform mathematical calculations. Supports basic arithmetic, powers, and common math functions.",
    category="math",
    parameters=[
        ToolParameter(
            name="expression",
            type=ParameterType.STRING,
            description="Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', '2**10')",
        ),
    ],
)


# Safe operations for eval
SAFE_FUNCTIONS = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'sqrt': math.sqrt,
    'pow': pow,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'pi': math.pi,
    'e': math.e,
}


async def calculate(arguments: Dict[str, Any], context: dict) -> str:
    """
    Execute calculator tool.
    
    Uses safe_eval to prevent code injection.
    """
    expression = arguments.get("expression", "")
    
    if not expression:
        raise ValueError("No expression provided")
    
    try:
        # Create safe namespace
        namespace = {"__builtins__": {}, **SAFE_FUNCTIONS}
        
        # Evaluate expression
        result = eval(expression, namespace)
        
        # Format result
        if isinstance(result, float):
            if result == int(result):
                return str(int(result))
            return f"{result:.6g}"
        return str(result)
        
    except SyntaxError:
        raise ValueError(f"Invalid expression: {expression}")
    except NameError as e:
        raise ValueError(f"Unknown function or variable: {e}")
    except Exception as e:
        raise ValueError(f"Calculation error: {e}")


# plugins/llm/mcp/tools/time.py

from datetime import datetime, timezone
from typing import Dict, Any
from zoneinfo import ZoneInfo
from ..types import ToolDefinition, ToolParameter, ParameterType


TIME_DEFINITION = ToolDefinition(
    name="get_time",
    description="Get current date and time, optionally in a specific timezone.",
    category="utility",
    parameters=[
        ToolParameter(
            name="timezone",
            type=ParameterType.STRING,
            description="Timezone name (e.g., 'America/New_York', 'Europe/London', 'UTC')",
            required=False,
            default="UTC",
        ),
        ToolParameter(
            name="format",
            type=ParameterType.STRING,
            description="Output format: 'full', 'date', 'time', 'iso'",
            required=False,
            default="full",
            enum=["full", "date", "time", "iso"],
        ),
    ],
)


async def get_time(arguments: Dict[str, Any], context: dict) -> str:
    """Get current time."""
    tz_name = arguments.get("timezone", "UTC")
    format_type = arguments.get("format", "full")
    
    try:
        tz = ZoneInfo(tz_name)
    except KeyError:
        raise ValueError(f"Unknown timezone: {tz_name}")
    
    now = datetime.now(tz)
    
    formats = {
        "full": now.strftime("%A, %B %d, %Y at %I:%M %p %Z"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S %Z"),
        "iso": now.isoformat(),
    }
    
    return formats.get(format_type, formats["full"])


# plugins/llm/mcp/tools/dice.py

import random
from typing import Dict, Any
from ..types import ToolDefinition, ToolParameter, ParameterType


DICE_DEFINITION = ToolDefinition(
    name="roll_dice",
    description="Roll dice using standard notation (e.g., '2d6', '1d20+5', '4d6kh3').",
    category="fun",
    parameters=[
        ToolParameter(
            name="notation",
            type=ParameterType.STRING,
            description="Dice notation (e.g., '2d6', '1d20+5', '3d6kh2' for keep highest 2)",
        ),
    ],
)


async def roll_dice(arguments: Dict[str, Any], context: dict) -> str:
    """
    Roll dice.
    
    Supports: NdS, NdS+M, NdSkhN, NdSklN
    """
    notation = arguments.get("notation", "").lower().strip()
    
    if not notation:
        raise ValueError("No dice notation provided")
    
    # Parse notation (simplified)
    import re
    
    # Pattern: NdS[kh/kl N][+/-M]
    match = re.match(
        r'^(\d+)d(\d+)(?:(kh|kl)(\d+))?([+-]\d+)?$',
        notation
    )
    
    if not match:
        raise ValueError(f"Invalid dice notation: {notation}")
    
    count = int(match.group(1))
    sides = int(match.group(2))
    keep_type = match.group(3)
    keep_count = int(match.group(4)) if match.group(4) else None
    modifier = int(match.group(5)) if match.group(5) else 0
    
    # Validate
    if count > 100:
        raise ValueError("Too many dice (max 100)")
    if sides > 1000:
        raise ValueError("Too many sides (max 1000)")
    
    # Roll
    rolls = [random.randint(1, sides) for _ in range(count)]
    
    # Keep highest/lowest
    kept = rolls[:]
    if keep_type == "kh" and keep_count:
        kept = sorted(rolls, reverse=True)[:keep_count]
    elif keep_type == "kl" and keep_count:
        kept = sorted(rolls)[:keep_count]
    
    total = sum(kept) + modifier
    
    # Format result
    if len(rolls) == 1:
        result = f"Rolled {notation}: **{total}**"
    else:
        roll_str = ", ".join(str(r) for r in rolls)
        if keep_type:
            kept_str = ", ".join(str(r) for r in kept)
            result = f"Rolled {notation}: [{roll_str}] → kept [{kept_str}]"
        else:
            result = f"Rolled {notation}: [{roll_str}]"
        if modifier:
            result += f" {'+' if modifier > 0 else ''}{modifier}"
        result += f" = **{total}**"
    
    return result
```

### 2.6 Integration with LLM Provider

```python
# plugins/llm/mcp/chat.py

from typing import List, Optional
from ..providers.base import Message
from .types import ToolCall, ToolResult
from .registry import ToolRegistry
from .executor import ToolExecutor


class ToolAwareChat:
    """
    Chat handler that supports tool calling.
    
    Flow:
    1. Send message with tool definitions
    2. If LLM requests tool call, execute it
    3. Send tool results back to LLM
    4. Get final response
    """
    
    def __init__(
        self,
        provider,
        registry: ToolRegistry,
        executor: ToolExecutor,
    ):
        self._provider = provider
        self._registry = registry
        self._executor = executor
    
    async def chat(
        self,
        messages: List[Message],
        context: dict,
        max_tool_calls: int = 5,
    ) -> str:
        """
        Chat with tool support.
        
        Args:
            messages: Conversation messages
            context: Execution context
            max_tool_calls: Maximum tool calls per response
            
        Returns:
            Final response text
        """
        # Get tool schemas
        tools = self._registry.get_schemas()
        
        tool_calls_made = 0
        
        while tool_calls_made < max_tool_calls:
            # Request completion with tools
            response = await self._provider.complete_with_tools(
                messages=messages,
                tools=tools,
            )
            
            # Check if tool calls requested
            if not response.tool_calls:
                return response.content
            
            # Execute tool calls
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in response.tool_calls
            ]
            
            results = await self._executor.execute(tool_calls, context)
            
            # Add assistant message with tool calls
            messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))
            
            # Add tool results
            for result in results:
                messages.append(Message(
                    role="tool",
                    content=result.to_message(),
                    tool_call_id=result.tool_call_id,
                ))
            
            tool_calls_made += len(tool_calls)
        
        # Max tool calls reached, get final response without tools
        response = await self._provider.complete(messages)
        return response.content
```

---

## 3. Implementation Steps

### Step 1: Create Types (30 minutes)

1. Create `plugins/llm/mcp/__init__.py`
2. Create `plugins/llm/mcp/types.py`
3. Define all type classes
4. Write tests for schema generation

### Step 2: Implement Registry (1 hour)

1. Create `plugins/llm/mcp/registry.py`
2. Implement `ToolRegistry` class
3. Write tests

### Step 3: Implement Executor (1.5 hours)

1. Create `plugins/llm/mcp/executor.py`
2. Implement validation
3. Implement execution with timeout
4. Write tests

### Step 4: Implement Built-in Tools (1.5 hours)

1. Create calculator tool
2. Create time tool
3. Create dice tool
4. Write tests for each

### Step 5: Integrate with Chat (2 hours)

1. Create `ToolAwareChat`
2. Update provider to support tool calls
3. Wire up in plugin
4. Test full flow

### Step 6: Testing (1 hour)

1. Test tool registration
2. Test tool execution
3. Test LLM integration
4. Test error cases

---

## 4. Test Cases

### 4.1 Registry Tests

```python
@pytest.mark.asyncio
async def test_register_tool():
    """Test tool registration."""
    registry = ToolRegistry()
    
    async def handler(args, ctx):
        return "result"
    
    registry.register(
        ToolDefinition(name="test", description="Test tool"),
        handler
    )
    
    assert registry.get("test") is not None
    assert len(registry.list_tools()) == 1


@pytest.mark.asyncio
async def test_duplicate_registration_fails():
    """Test duplicate registration is rejected."""
    registry = ToolRegistry()
    
    async def handler(args, ctx):
        return "result"
    
    registry.register(
        ToolDefinition(name="test", description="Test"),
        handler
    )
    
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ToolDefinition(name="test", description="Test 2"),
            handler
        )
```

### 4.2 Executor Tests

```python
@pytest.mark.asyncio
async def test_execute_tool():
    """Test basic tool execution."""
    registry = ToolRegistry()
    
    async def add(args, ctx):
        return args["a"] + args["b"]
    
    registry.register(
        ToolDefinition(
            name="add",
            description="Add numbers",
            parameters=[
                ToolParameter(name="a", type=ParameterType.NUMBER),
                ToolParameter(name="b", type=ParameterType.NUMBER),
            ]
        ),
        add
    )
    
    executor = ToolExecutor(registry)
    
    results = await executor.execute(
        [ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})],
        {}
    )
    
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].result == 5


@pytest.mark.asyncio
async def test_missing_required_param():
    """Test validation catches missing params."""
    registry = ToolRegistry()
    
    async def greet(args, ctx):
        return f"Hello, {args['name']}"
    
    registry.register(
        ToolDefinition(
            name="greet",
            description="Greet someone",
            parameters=[
                ToolParameter(name="name", type=ParameterType.STRING, required=True),
            ]
        ),
        greet
    )
    
    executor = ToolExecutor(registry)
    
    results = await executor.execute(
        [ToolCall(id="1", name="greet", arguments={})],
        {}
    )
    
    assert results[0].success is False
    assert "Missing required" in results[0].error
```

### 4.3 Built-in Tool Tests

```python
@pytest.mark.asyncio
async def test_calculator_basic():
    """Test calculator with basic math."""
    result = await calculate({"expression": "2 + 2"}, {})
    assert result == "4"


@pytest.mark.asyncio
async def test_calculator_functions():
    """Test calculator with math functions."""
    result = await calculate({"expression": "sqrt(16)"}, {})
    assert result == "4"


@pytest.mark.asyncio
async def test_calculator_rejects_unsafe():
    """Test calculator rejects dangerous code."""
    with pytest.raises(ValueError):
        await calculate({"expression": "__import__('os').system('ls')"}, {})


@pytest.mark.asyncio
async def test_dice_basic():
    """Test basic dice roll."""
    result = await roll_dice({"notation": "1d6"}, {})
    assert "Rolled 1d6" in result


@pytest.mark.asyncio
async def test_dice_keep_highest():
    """Test keep highest notation."""
    result = await roll_dice({"notation": "4d6kh3"}, {})
    assert "kept" in result
```

---

## 5. Usage Examples

### 5.1 User Interaction

```
User: !chat What's 15% tip on $47.50?
Rosey: 🤖 Let me calculate that...
       [Uses calculator: 47.50 * 0.15]
       A 15% tip on $47.50 would be $7.13, 
       making the total $54.63.

User: !chat Roll 4d6 and drop the lowest for my D&D character
Rosey: 🤖 Rolling your character stats!
       [Uses roll_dice: 4d6kh3]
       Rolled 4d6kh3: [6, 4, 3, 2] → kept [6, 4, 3] = **13**

User: !chat What time is it in Tokyo right now?
Rosey: 🤖 [Uses get_time: timezone=Asia/Tokyo]
       It's currently Saturday, January 15, 2025 at 11:30 PM JST in Tokyo.
```

### 5.2 Programmatic Usage

```python
# From another plugin

async def use_llm_with_tools(nc, question: str) -> str:
    """Ask LLM with tool support."""
    response = await nc.request(
        "rosey.llm.chat",
        json.dumps({
            "channel": "#test",
            "user": "system",
            "message": question,
            "enable_tools": True,
        }).encode(),
        timeout=30.0
    )
    
    data = json.loads(response.data.decode())
    return data.get("content", "")
```

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] Tool registry allows registration/unregistration
- [ ] Executor validates parameters
- [ ] Executor handles timeouts
- [ ] Calculator tool works with basic math
- [ ] Time tool returns correct timezone
- [ ] Dice tool handles standard notation
- [ ] LLM can request and receive tool results

### 6.2 Technical

- [ ] Tools are isolated (can't access system)
- [ ] Tool errors handled gracefully
- [ ] Test coverage > 85%
- [ ] No security vulnerabilities in calculator

---

## 7. Security Considerations

### 7.1 Calculator Safety

- Use restricted `eval` with safe namespace
- No access to `__builtins__`
- No access to `os`, `sys`, `subprocess`
- Whitelist of allowed functions only

### 7.2 Tool Execution

- Timeout on all tool calls
- Rate limiting on tool usage
- No file system access
- No network access from tools

---

**Commit Message Template:**
```
feat(plugins): Add MCP foundation for tool calling

- Add tool definition framework
- Add tool registry and executor
- Add built-in tools (calculator, time, dice)
- Add tool-aware chat handler
- Add comprehensive security measures

Implements: SPEC-Sortie-7-MCPFoundation.md
Related: PRD-Core-Migrations.md
Part: 1 of 1 (MCP Foundation)
```
