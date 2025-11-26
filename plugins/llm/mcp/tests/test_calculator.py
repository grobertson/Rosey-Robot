"""Tests for Calculator MCP tool."""

import pytest
from plugins.llm.mcp.tools.calculator import calculate, CALCULATOR_TOOL


class TestCalculatorTool:
    """Tests for calculator tool."""

    @pytest.mark.asyncio
    async def test_simple_addition(self):
        """Test simple addition."""
        result = await calculate({"expression": "2 + 3"}, {})
        assert "5" in result

    @pytest.mark.asyncio
    async def test_simple_subtraction(self):
        """Test simple subtraction."""
        result = await calculate({"expression": "10 - 3"}, {})
        assert "7" in result

    @pytest.mark.asyncio
    async def test_simple_multiplication(self):
        """Test simple multiplication."""
        result = await calculate({"expression": "4 * 5"}, {})
        assert "20" in result

    @pytest.mark.asyncio
    async def test_simple_division(self):
        """Test simple division."""
        result = await calculate({"expression": "15 / 3"}, {})
        assert "5" in result

    @pytest.mark.asyncio
    async def test_modulo(self):
        """Test modulo operation."""
        result = await calculate({"expression": "10 % 3"}, {})
        assert "1" in result

    @pytest.mark.asyncio
    async def test_power(self):
        """Test power operation."""
        result = await calculate({"expression": "2 ** 3"}, {})
        assert "8" in result

    @pytest.mark.asyncio
    async def test_complex_expression(self):
        """Test complex expression with parentheses."""
        result = await calculate({"expression": "(2 + 3) * 4"}, {})
        assert "20" in result

    @pytest.mark.asyncio
    async def test_nested_parentheses(self):
        """Test nested parentheses."""
        result = await calculate({"expression": "((2 + 3) * 4) / 2"}, {})
        assert "10" in result

    @pytest.mark.asyncio
    async def test_decimal_numbers(self):
        """Test decimal numbers."""
        result = await calculate({"expression": "3.5 * 2"}, {})
        assert "7" in result

    @pytest.mark.asyncio
    async def test_negative_numbers(self):
        """Test negative numbers."""
        result = await calculate({"expression": "-5 + 3"}, {})
        assert "-2" in result

    @pytest.mark.asyncio
    async def test_division_by_zero(self):
        """Test division by zero returns error."""
        result = await calculate({"expression": "10 / 0"}, {})
        assert "Error" in result or "error" in result

    @pytest.mark.asyncio
    async def test_invalid_characters(self):
        """Test invalid characters are rejected."""
        result = await calculate({"expression": "2 + abc"}, {})
        assert "Error" in result or "error" in result

    @pytest.mark.asyncio
    async def test_dangerous_code_rejected(self):
        """Test dangerous code is rejected."""
        result = await calculate({"expression": "import os"}, {})
        assert "Error" in result or "error" in result

    @pytest.mark.asyncio
    async def test_function_calls_rejected(self):
        """Test function calls are rejected."""
        result = await calculate({"expression": "eval('1+1')"}, {})
        assert "Error" in result or "error" in result

    @pytest.mark.asyncio
    async def test_whitespace_handling(self):
        """Test whitespace is handled correctly."""
        result = await calculate({"expression": "  2  +  3  "}, {})
        assert "5" in result

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        """Test empty expression returns error."""
        result = await calculate({"expression": ""}, {})
        assert "Error" in result or "error" in result

    @pytest.mark.asyncio
    async def test_result_includes_expression(self):
        """Test result includes the original expression."""
        result = await calculate({"expression": "2 + 2"}, {})
        # Expression is normalized (whitespace removed)
        assert "2+2" in result
        assert "4" in result


class TestCalculatorDefinition:
    """Tests for calculator tool definition."""

    def test_tool_definition_exists(self):
        """Test tool definition is properly defined."""
        assert CALCULATOR_TOOL is not None
        assert CALCULATOR_TOOL.name == "calculate"
        assert CALCULATOR_TOOL.description
        assert len(CALCULATOR_TOOL.parameters) > 0

    def test_tool_has_expression_parameter(self):
        """Test tool has expression parameter."""
        params = {p.name: p for p in CALCULATOR_TOOL.parameters}
        assert "expression" in params
        assert params["expression"].required

    def test_tool_schema_generation(self):
        """Test tool can generate valid schema."""
        schema = CALCULATOR_TOOL.to_schema()
        assert schema["name"] == "calculate"
        assert "parameters" in schema
