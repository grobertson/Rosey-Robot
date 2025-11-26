"""Tests for MCP Tool Call Parser."""

import pytest
from plugins.llm.mcp.parser import ToolCallParser


class TestOpenAIFormat:
    """Tests for OpenAI format parsing."""

    def test_parse_openai_old_format(self):
        """Test parsing old OpenAI function_call format."""
        response = {
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "calculate",
                        "arguments": '{"expression": "2 + 2"}'
                    }
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 1
        assert calls[0].name == "calculate"
        assert calls[0].arguments == {"expression": "2 + 2"}
        assert calls[0].id is not None

    def test_parse_openai_new_format(self):
        """Test parsing new OpenAI tool_calls format."""
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "calculate",
                                "arguments": '{"expression": "2 + 2"}'
                            }
                        }
                    ]
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 1
        assert calls[0].id == "call_123"
        assert calls[0].name == "calculate"
        assert calls[0].arguments == {"expression": "2 + 2"}

    def test_parse_openai_multiple_tools(self):
        """Test parsing multiple tool calls."""
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "calculate",
                                "arguments": '{"expression": "2 + 2"}'
                            }
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "get_current_time",
                                "arguments": '{}'
                            }
                        }
                    ]
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 2
        assert calls[0].name == "calculate"
        assert calls[1].name == "get_current_time"

    def test_parse_openai_no_tools(self):
        """Test parsing response with no tool calls."""
        response = {
            "choices": [{
                "message": {
                    "content": "Just a regular response"
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 0

    def test_parse_openai_invalid_json_arguments(self):
        """Test parsing with invalid JSON arguments."""
        response = {
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "calculate",
                        "arguments": "not valid json"
                    }
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 1
        # Parser should handle invalid JSON gracefully
        assert calls[0].name == "calculate"


class TestAnthropicFormat:
    """Tests for Anthropic format parsing."""

    def test_parse_anthropic_single_tool(self):
        """Test parsing Anthropic tool_use format."""
        response = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "calculate",
                    "input": {"expression": "2 + 2"}
                }
            ]
        }
        
        calls = ToolCallParser.parse_anthropic_format(response)
        assert len(calls) == 1
        assert calls[0].id == "toolu_123"
        assert calls[0].name == "calculate"
        assert calls[0].arguments == {"expression": "2 + 2"}

    def test_parse_anthropic_multiple_tools(self):
        """Test parsing multiple Anthropic tool calls."""
        response = {
            "content": [
                {
                    "type": "text",
                    "text": "Let me help you with that."
                },
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "calculate",
                    "input": {"expression": "10 * 5"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "get_current_time",
                    "input": {}
                }
            ]
        }
        
        calls = ToolCallParser.parse_anthropic_format(response)
        assert len(calls) == 2
        assert calls[0].name == "calculate"
        assert calls[1].name == "get_current_time"

    def test_parse_anthropic_no_tools(self):
        """Test parsing Anthropic response with no tools."""
        response = {
            "content": [
                {
                    "type": "text",
                    "text": "Just a regular response"
                }
            ]
        }
        
        calls = ToolCallParser.parse_anthropic_format(response)
        assert len(calls) == 0

    def test_parse_anthropic_mixed_content(self):
        """Test parsing response with mixed content types."""
        response = {
            "content": [
                {"type": "text", "text": "First I'll calculate."},
                {"type": "tool_use", "id": "t1", "name": "calc", "input": {"x": 5}},
                {"type": "text", "text": "Then check time."},
                {"type": "tool_use", "id": "t2", "name": "time", "input": {}},
            ]
        }
        
        calls = ToolCallParser.parse_anthropic_format(response)
        assert len(calls) == 2


class TestAutoDetection:
    """Tests for automatic format detection."""

    def test_parse_auto_openai(self):
        """Test auto-detection of OpenAI format."""
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "calculate",
                            "arguments": '{"expression": "2 + 2"}'
                        }
                    }]
                }
            }]
        }
        
        calls = ToolCallParser.parse(response, format="auto")
        assert len(calls) == 1
        assert calls[0].name == "calculate"

    def test_parse_auto_anthropic(self):
        """Test auto-detection of Anthropic format."""
        response = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "calculate",
                    "input": {"expression": "2 + 2"}
                }
            ]
        }
        
        calls = ToolCallParser.parse(response, format="auto")
        assert len(calls) == 1
        assert calls[0].name == "calculate"

    def test_parse_explicit_openai(self):
        """Test explicit OpenAI format selection."""
        response = {
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "test",
                        "arguments": '{}'
                    }
                }
            }]
        }
        
        calls = ToolCallParser.parse(response, format="openai")
        assert len(calls) == 1

    def test_parse_explicit_anthropic(self):
        """Test explicit Anthropic format selection."""
        response = {
            "content": [
                {"type": "tool_use", "id": "t1", "name": "test", "input": {}}
            ]
        }
        
        calls = ToolCallParser.parse(response, format="anthropic")
        assert len(calls) == 1

    def test_parse_invalid_format(self):
        """Test parsing with invalid format raises error."""
        response = {}
        with pytest.raises(ValueError, match="Unsupported format"):
            ToolCallParser.parse(response, format="unsupported")

    def test_parse_ambiguous_format(self):
        """Test parsing ambiguous format returns empty list."""
        response = {"unknown": "structure"}
        calls = ToolCallParser.parse(response, format="auto")
        assert len(calls) == 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        calls = ToolCallParser.parse({}, format="auto")
        assert len(calls) == 0

    def test_parse_null_response(self):
        """Test parsing None response."""
        calls = ToolCallParser.parse(None, format="auto")
        assert len(calls) == 0

    def test_parse_openai_empty_choices(self):
        """Test parsing OpenAI response with empty choices."""
        response = {"choices": []}
        calls = ToolCallParser.parse_openai_format(response)
        assert len(calls) == 0

    def test_parse_anthropic_empty_content(self):
        """Test parsing Anthropic response with empty content."""
        response = {"content": []}
        calls = ToolCallParser.parse_anthropic_format(response)
        assert len(calls) == 0

    def test_parse_openai_missing_arguments(self):
        """Test parsing tool call without arguments."""
        response = {
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "test"
                        # Missing arguments field
                    }
                }
            }]
        }
        
        calls = ToolCallParser.parse_openai_format(response)
        # Should handle gracefully
        assert len(calls) <= 1

    def test_parse_anthropic_missing_input(self):
        """Test parsing Anthropic tool without input."""
        response = {
            "content": [{
                "type": "tool_use",
                "id": "t1",
                "name": "test"
                # Missing input field
            }]
        }
        
        calls = ToolCallParser.parse_anthropic_format(response)
        # Should handle gracefully
        assert len(calls) <= 1
