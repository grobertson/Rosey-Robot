"""Tests for Time MCP tool."""

import pytest
from datetime import datetime
from plugins.llm.mcp.tools.time import get_current_time, TIME_TOOL


class TestTimeTool:
    """Tests for time tool."""

    @pytest.mark.asyncio
    async def test_default_format(self):
        """Test time with default format."""
        result = await get_current_time({}, {})
        
        # Should be able to parse the result with default format
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    @pytest.mark.asyncio
    async def test_custom_format_date_only(self):
        """Test time with date-only format."""
        result = await get_current_time({"format": "%Y-%m-%d"}, {})
        
        # Should match YYYY-MM-DD pattern
        datetime.strptime(result, "%Y-%m-%d")

    @pytest.mark.asyncio
    async def test_custom_format_time_only(self):
        """Test time with time-only format."""
        result = await get_current_time({"format": "%H:%M:%S"}, {})
        
        # Should match HH:MM:SS pattern
        datetime.strptime(result, "%H:%M:%S")

    @pytest.mark.asyncio
    async def test_custom_format_12hour(self):
        """Test time with 12-hour format."""
        result = await get_current_time({"format": "%I:%M %p"}, {})
        
        # Should match HH:MM AM/PM pattern
        datetime.strptime(result, "%I:%M %p")

    @pytest.mark.asyncio
    async def test_custom_format_full(self):
        """Test time with full format including weekday."""
        result = await get_current_time({"format": "%A, %B %d, %Y"}, {})
        
        # Should be parseable (though format validation is tricky for full names)
        assert len(result) > 0
        assert "," in result

    @pytest.mark.asyncio
    async def test_iso_format(self):
        """Test time with ISO format."""
        result = await get_current_time({"format": "%Y-%m-%dT%H:%M:%S"}, {})
        
        # Should match ISO 8601 basic format
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%S")

    @pytest.mark.asyncio
    async def test_unix_timestamp_format(self):
        """Test time with unix timestamp format."""
        result = await get_current_time({"format": "%s"}, {})
        
        # Should be a number (unix timestamp)
        # Note: %s may not be supported on all platforms
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_empty_arguments(self):
        """Test time with empty arguments uses default."""
        result = await get_current_time({}, {})
        
        # Should return valid timestamp
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    @pytest.mark.asyncio
    async def test_invalid_format_handled(self):
        """Test invalid format is handled gracefully."""
        # This might raise an exception or return an error string
        # depending on implementation
        try:
            result = await get_current_time({"format": "%Z%Z%Z invalid"}, {})
            # If it doesn't raise, check it returns something
            assert result is not None
        except (ValueError, KeyError):
            # Expected for invalid format
            pass

    @pytest.mark.asyncio
    async def test_returns_string(self):
        """Test tool returns a string."""
        result = await get_current_time({}, {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_current_year(self):
        """Test returned time has current year."""
        result = await get_current_time({"format": "%Y"}, {})
        current_year = datetime.now().year
        assert str(current_year) == result


class TestTimeDefinition:
    """Tests for time tool definition."""

    def test_tool_definition_exists(self):
        """Test tool definition is properly defined."""
        assert TIME_TOOL is not None
        assert TIME_TOOL.name == "get_current_time"
        assert TIME_TOOL.description
        assert len(TIME_TOOL.parameters) > 0

    def test_tool_has_format_parameter(self):
        """Test tool has format parameter."""
        params = {p.name: p for p in TIME_TOOL.parameters}
        assert "format" in params
        assert not params["format"].required  # Format is optional
        assert params["format"].default is not None

    def test_tool_schema_generation(self):
        """Test tool can generate valid schema."""
        schema = TIME_TOOL.to_schema()
        assert schema["name"] == "get_current_time"
        assert "parameters" in schema
