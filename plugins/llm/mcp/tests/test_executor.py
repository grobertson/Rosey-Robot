"""Tests for MCP Tool Executor."""

import asyncio
import pytest
from plugins.llm.mcp.executor import ToolExecutor
from plugins.llm.mcp.registry import ToolRegistry
from plugins.llm.mcp.types import ToolDefinition, ToolParameter, ParameterType, ToolCall


@pytest.fixture
def registry():
    """Fresh registry for each test."""
    return ToolRegistry()


@pytest.fixture
def executor(registry):
    """Fresh executor for each test."""
    return ToolExecutor(registry, timeout=5.0)


@pytest.fixture
async def simple_handler():
    """Simple test handler."""
    async def handler(arguments, context):
        return f"Result: {arguments.get('value', 'none')}"
    return handler


@pytest.fixture
async def math_handler():
    """Math test handler."""
    async def handler(arguments, context):
        a = arguments["a"]
        b = arguments["b"]
        return a + b
    return handler


@pytest.fixture
async def slow_handler():
    """Slow handler for timeout tests."""
    async def handler(arguments, context):
        await asyncio.sleep(10)  # Longer than default timeout
        return "done"
    return handler


@pytest.fixture
async def error_handler():
    """Handler that raises an error."""
    async def handler(arguments, context):
        raise ValueError("Test error")
    return handler


class TestParameterValidation:
    """Tests for parameter validation."""

    @pytest.mark.asyncio
    async def test_validate_required_parameter_present(self, executor, registry, simple_handler):
        """Test validation passes with required parameter."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters=[
                ToolParameter(name="value", type=ParameterType.STRING, required=True)
            ],
        )
        registry.register(tool_def, simple_handler)
        
        call = ToolCall(id="1", name="test_tool", arguments={"value": "test"})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert results[0].success
        assert results[0].result == "Result: test"

    @pytest.mark.asyncio
    async def test_validate_required_parameter_missing(self, executor, registry, simple_handler):
        """Test validation fails with missing required parameter."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters=[
                ToolParameter(name="value", type=ParameterType.STRING, required=True)
            ],
        )
        registry.register(tool_def, simple_handler)
        
        call = ToolCall(id="1", name="test_tool", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert not results[0].success
        assert "Missing required parameter" in results[0].error

    @pytest.mark.asyncio
    async def test_validate_optional_parameter_missing(self, executor, registry, simple_handler):
        """Test validation passes with missing optional parameter."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters=[
                ToolParameter(name="value", type=ParameterType.STRING, required=False)
            ],
        )
        registry.register(tool_def, simple_handler)
        
        call = ToolCall(id="1", name="test_tool", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert results[0].success

    @pytest.mark.asyncio
    async def test_validate_type_string(self, executor, registry, simple_handler):
        """Test string type validation."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters=[
                ToolParameter(name="value", type=ParameterType.STRING, required=True)
            ],
        )
        registry.register(tool_def, simple_handler)
        
        # Valid string
        call = ToolCall(id="1", name="test_tool", arguments={"value": "test"})
        results = await executor.execute([call], {})
        assert results[0].success
        
        # Invalid type
        call = ToolCall(id="2", name="test_tool", arguments={"value": 123})
        results = await executor.execute([call], {})
        assert not results[0].success
        assert "Invalid type" in results[0].error

    @pytest.mark.asyncio
    async def test_validate_type_number(self, executor, registry, math_handler):
        """Test number type validation."""
        tool_def = ToolDefinition(
            name="math_tool",
            description="Math",
            parameters=[
                ToolParameter(name="a", type=ParameterType.NUMBER, required=True),
                ToolParameter(name="b", type=ParameterType.NUMBER, required=True),
            ],
        )
        registry.register(tool_def, math_handler)
        
        # Valid numbers
        call = ToolCall(id="1", name="math_tool", arguments={"a": 5.5, "b": 2.3})
        results = await executor.execute([call], {})
        assert results[0].success
        assert results[0].result == 7.8

    @pytest.mark.asyncio
    async def test_validate_type_integer(self, executor, registry, math_handler):
        """Test integer type validation."""
        tool_def = ToolDefinition(
            name="math_tool",
            description="Math",
            parameters=[
                ToolParameter(name="a", type=ParameterType.INTEGER, required=True),
                ToolParameter(name="b", type=ParameterType.INTEGER, required=True),
            ],
        )
        registry.register(tool_def, math_handler)
        
        # Valid integers
        call = ToolCall(id="1", name="math_tool", arguments={"a": 5, "b": 2})
        results = await executor.execute([call], {})
        assert results[0].success
        assert results[0].result == 7
        
        # Float not valid for integer
        call = ToolCall(id="2", name="math_tool", arguments={"a": 5.5, "b": 2})
        results = await executor.execute([call], {})
        assert not results[0].success

    @pytest.mark.asyncio
    async def test_validate_type_boolean(self, executor, registry):
        """Test boolean type validation."""
        async def bool_handler(arguments, context):
            return arguments["flag"]
        
        tool_def = ToolDefinition(
            name="bool_tool",
            description="Boolean",
            parameters=[
                ToolParameter(name="flag", type=ParameterType.BOOLEAN, required=True)
            ],
        )
        registry.register(tool_def, bool_handler)
        
        # Valid boolean
        call = ToolCall(id="1", name="bool_tool", arguments={"flag": True})
        results = await executor.execute([call], {})
        assert results[0].success
        assert results[0].result is True

    @pytest.mark.asyncio
    async def test_validate_type_array(self, executor, registry):
        """Test array type validation."""
        async def array_handler(arguments, context):
            return len(arguments["items"])
        
        tool_def = ToolDefinition(
            name="array_tool",
            description="Array",
            parameters=[
                ToolParameter(name="items", type=ParameterType.ARRAY, required=True)
            ],
        )
        registry.register(tool_def, array_handler)
        
        # Valid array
        call = ToolCall(id="1", name="array_tool", arguments={"items": [1, 2, 3]})
        results = await executor.execute([call], {})
        assert results[0].success
        assert results[0].result == 3

    @pytest.mark.asyncio
    async def test_validate_type_object(self, executor, registry):
        """Test object type validation."""
        async def object_handler(arguments, context):
            return arguments["data"]["key"]
        
        tool_def = ToolDefinition(
            name="object_tool",
            description="Object",
            parameters=[
                ToolParameter(name="data", type=ParameterType.OBJECT, required=True)
            ],
        )
        registry.register(tool_def, object_handler)
        
        # Valid object
        call = ToolCall(id="1", name="object_tool", arguments={"data": {"key": "value"}})
        results = await executor.execute([call], {})
        assert results[0].success
        assert results[0].result == "value"


class TestExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_single_tool(self, executor, registry, simple_handler):
        """Test executing a single tool."""
        tool_def = ToolDefinition(name="test_tool", description="Test")
        registry.register(tool_def, simple_handler)
        
        call = ToolCall(id="1", name="test_tool", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert results[0].tool_call_id == "1"
        assert results[0].success
        assert results[0].result == "Result: none"

    @pytest.mark.asyncio
    async def test_execute_multiple_tools_sequential(self, executor, registry, simple_handler):
        """Test executing multiple tools sequentially."""
        tool_def = ToolDefinition(name="test_tool", description="Test")
        registry.register(tool_def, simple_handler)
        
        calls = [
            ToolCall(id="1", name="test_tool", arguments={"value": "first"}),
            ToolCall(id="2", name="test_tool", arguments={"value": "second"}),
        ]
        results = await executor.execute(calls, {})
        
        assert len(results) == 2
        assert results[0].result == "Result: first"
        assert results[1].result == "Result: second"

    @pytest.mark.asyncio
    async def test_execute_parallel(self, executor, registry, simple_handler):
        """Test executing tools in parallel."""
        tool_def = ToolDefinition(name="test_tool", description="Test")
        registry.register(tool_def, simple_handler)
        
        calls = [
            ToolCall(id="1", name="test_tool", arguments={"value": "first"}),
            ToolCall(id="2", name="test_tool", arguments={"value": "second"}),
        ]
        results = await executor.execute_parallel(calls, {})
        
        assert len(results) == 2
        # Order may vary in parallel execution, so check both are present
        result_values = {r.result for r in results}
        assert "Result: first" in result_values
        assert "Result: second" in result_values

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, executor):
        """Test executing nonexistent tool returns error."""
        call = ToolCall(id="1", name="nonexistent", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert not results[0].success
        assert "not found" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, executor, registry, slow_handler):
        """Test execution timeout."""
        tool_def = ToolDefinition(name="slow_tool", description="Slow")
        registry.register(tool_def, slow_handler)
        
        call = ToolCall(id="1", name="slow_tool", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert not results[0].success
        assert "timed out" in results[0].error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_handler_error(self, executor, registry, error_handler):
        """Test execution with handler that raises error."""
        tool_def = ToolDefinition(name="error_tool", description="Error")
        registry.register(tool_def, error_handler)
        
        call = ToolCall(id="1", name="error_tool", arguments={})
        results = await executor.execute([call], {})
        
        assert len(results) == 1
        assert not results[0].success
        assert "Test error" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_with_context(self, executor, registry):
        """Test execution passes context to handler."""
        async def context_handler(arguments, context):
            return f"User: {context['user']}, Channel: {context['channel']}"
        
        tool_def = ToolDefinition(name="context_tool", description="Context")
        registry.register(tool_def, context_handler)
        
        call = ToolCall(id="1", name="context_tool", arguments={})
        context = {"user": "alice", "channel": "test"}
        results = await executor.execute([call], context)
        
        assert len(results) == 1
        assert results[0].success
        assert results[0].result == "User: alice, Channel: test"

    @pytest.mark.asyncio
    async def test_execute_with_cooldown(self, executor, registry, simple_handler):
        """Test cooldown enforcement."""
        tool_def = ToolDefinition(
            name="cool_tool",
            description="Cooldown",
            cooldown_seconds=1,
        )
        registry.register(tool_def, simple_handler)
        
        call = ToolCall(id="1", name="cool_tool", arguments={})
        
        # First call should succeed
        results = await executor.execute([call], {})
        assert results[0].success
        
        # Immediate second call should fail
        call2 = ToolCall(id="2", name="cool_tool", arguments={})
        results = await executor.execute([call2], {})
        assert not results[0].success
        assert "cooldown" in results[0].error.lower()
        
        # After cooldown, should succeed
        await asyncio.sleep(1.1)
        call3 = ToolCall(id="3", name="cool_tool", arguments={})
        results = await executor.execute([call3], {})
        assert results[0].success
