"""Tests for MCP Tool Registry."""

import pytest
from plugins.llm.mcp.registry import Tool, ToolRegistry
from plugins.llm.mcp.types import ToolDefinition, ToolParameter, ParameterType


@pytest.fixture
def sample_tool_def():
    """Sample tool definition."""
    return ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters=[
            ToolParameter(
                name="input",
                type=ParameterType.STRING,
                description="Input value",
                required=True,
            )
        ],
        category="test",
    )


@pytest.fixture
async def sample_handler():
    """Sample tool handler."""
    async def handler(arguments, context):
        return f"Processed: {arguments['input']}"
    return handler


@pytest.fixture
def registry():
    """Fresh registry for each test."""
    return ToolRegistry()


class TestTool:
    """Tests for Tool wrapper."""

    @pytest.mark.asyncio
    async def test_tool_creation(self, sample_tool_def, sample_handler):
        """Test tool wrapper creation."""
        tool = Tool(sample_tool_def, sample_handler)
        assert tool.definition == sample_tool_def
        assert tool.handler == sample_handler
        assert tool.call_count == 0
        assert tool.last_called is None

    @pytest.mark.asyncio
    async def test_tool_execute(self, sample_tool_def, sample_handler):
        """Test tool execution."""
        tool = Tool(sample_tool_def, sample_handler)
        result = await tool.execute({"input": "test"}, {})
        assert result == "Processed: test"
        assert tool.call_count == 1
        assert tool.last_called is not None

    @pytest.mark.asyncio
    async def test_tool_execute_multiple_calls(self, sample_tool_def, sample_handler):
        """Test tool execution tracks call count."""
        tool = Tool(sample_tool_def, sample_handler)
        await tool.execute({"input": "test1"}, {})
        await tool.execute({"input": "test2"}, {})
        await tool.execute({"input": "test3"}, {})
        assert tool.call_count == 3

    @pytest.mark.asyncio
    async def test_tool_last_called_updates(self, sample_tool_def, sample_handler):
        """Test last_called timestamp updates."""
        tool = Tool(sample_tool_def, sample_handler)
        await tool.execute({"input": "test1"}, {})
        first_call = tool.last_called
        
        await tool.execute({"input": "test2"}, {})
        second_call = tool.last_called
        
        assert second_call > first_call


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_registry_creation(self, registry):
        """Test registry creation."""
        assert registry.count() == 0
        assert registry.categories() == []

    def test_register_tool(self, registry, sample_tool_def, sample_handler):
        """Test registering a tool."""
        registry.register(sample_tool_def, sample_handler)
        assert registry.count() == 1
        assert "test_tool" in registry.list_tools()

    def test_register_duplicate_tool_raises(self, registry, sample_tool_def, sample_handler):
        """Test registering duplicate tool raises error."""
        registry.register(sample_tool_def, sample_handler)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(sample_tool_def, sample_handler)

    def test_unregister_tool(self, registry, sample_tool_def, sample_handler):
        """Test unregistering a tool."""
        registry.register(sample_tool_def, sample_handler)
        registry.unregister("test_tool")
        assert registry.count() == 0

    def test_unregister_nonexistent_tool(self, registry):
        """Test unregistering nonexistent tool does nothing."""
        registry.unregister("nonexistent")  # Should not raise

    def test_get_tool(self, registry, sample_tool_def, sample_handler):
        """Test getting a tool."""
        registry.register(sample_tool_def, sample_handler)
        tool = registry.get("test_tool")
        assert tool is not None
        assert tool.definition == sample_tool_def

    def test_get_nonexistent_tool(self, registry):
        """Test getting nonexistent tool returns None."""
        tool = registry.get("nonexistent")
        assert tool is None

    def test_list_tools(self, registry, sample_handler):
        """Test listing all tools."""
        tool1 = ToolDefinition(name="tool1", description="Tool 1", category="cat1")
        tool2 = ToolDefinition(name="tool2", description="Tool 2", category="cat2")
        
        registry.register(tool1, sample_handler)
        registry.register(tool2, sample_handler)
        
        tools = registry.list_tools()
        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_list_tools_by_category(self, registry, sample_handler):
        """Test listing tools by category."""
        tool1 = ToolDefinition(name="tool1", description="Tool 1", category="cat1")
        tool2 = ToolDefinition(name="tool2", description="Tool 2", category="cat1")
        tool3 = ToolDefinition(name="tool3", description="Tool 3", category="cat2")
        
        registry.register(tool1, sample_handler)
        registry.register(tool2, sample_handler)
        registry.register(tool3, sample_handler)
        
        cat1_tools = registry.list_tools(category="cat1")
        assert len(cat1_tools) == 2
        assert "tool1" in cat1_tools
        assert "tool2" in cat1_tools

    def test_categories(self, registry, sample_handler):
        """Test getting all categories."""
        tool1 = ToolDefinition(name="tool1", description="Tool 1", category="cat1")
        tool2 = ToolDefinition(name="tool2", description="Tool 2", category="cat2")
        tool3 = ToolDefinition(name="tool3", description="Tool 3", category="cat2")
        
        registry.register(tool1, sample_handler)
        registry.register(tool2, sample_handler)
        registry.register(tool3, sample_handler)
        
        categories = registry.categories()
        assert len(categories) == 2
        assert "cat1" in categories
        assert "cat2" in categories

    def test_get_schemas(self, registry, sample_tool_def, sample_handler):
        """Test getting tool schemas."""
        registry.register(sample_tool_def, sample_handler)
        schemas = registry.get_schemas()
        
        assert len(schemas) == 1
        assert schemas[0]["name"] == "test_tool"
        assert schemas[0]["description"] == "A test tool"
        assert "parameters" in schemas[0]

    def test_get_schemas_by_category(self, registry, sample_handler):
        """Test getting schemas by category."""
        tool1 = ToolDefinition(name="tool1", description="Tool 1", category="cat1")
        tool2 = ToolDefinition(name="tool2", description="Tool 2", category="cat2")
        
        registry.register(tool1, sample_handler)
        registry.register(tool2, sample_handler)
        
        schemas = registry.get_schemas(category="cat1")
        assert len(schemas) == 1
        assert schemas[0]["name"] == "tool1"

    def test_stats(self, registry, sample_tool_def, sample_handler):
        """Test getting usage statistics."""
        registry.register(sample_tool_def, sample_handler)
        stats = registry.stats()
        
        assert "test_tool" in stats
        assert stats["test_tool"] == 0  # No calls yet

    @pytest.mark.asyncio
    async def test_stats_after_execution(self, registry, sample_tool_def, sample_handler):
        """Test stats update after tool execution."""
        registry.register(sample_tool_def, sample_handler)
        tool = registry.get("test_tool")
        
        await tool.execute({"input": "test"}, {})
        await tool.execute({"input": "test"}, {})
        
        stats = registry.stats()
        assert stats["test_tool"] == 2
