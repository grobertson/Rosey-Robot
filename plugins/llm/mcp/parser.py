"""
MCP Tool Call Parser
====================

Parses tool calls from LLM responses.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .types import ToolCall

logger = logging.getLogger(__name__)


class ToolCallParser:
    """
    Parses tool calls from various LLM response formats.
    
    Supports:
    - OpenAI function calling format
    - Anthropic tool use format
    - Plain text with structured markers
    """
    
    @staticmethod
    def parse_openai_format(response: Dict[str, Any]) -> List[ToolCall]:
        """
        Parse tool calls from OpenAI format.
        
        Args:
            response: OpenAI API response
            
        Returns:
            List of parsed tool calls
        """
        tool_calls = []
        
        # Check for function_call (older format)
        if "function_call" in response:
            fc = response["function_call"]
            try:
                args = json.loads(fc.get("arguments", "{}"))
                tool_calls.append(ToolCall(
                    id="call_0",
                    name=fc["name"],
                    arguments=args,
                ))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function_call arguments: {e}")
        
        # Check for tool_calls (newer format)
        if "tool_calls" in response:
            for idx, tc in enumerate(response["tool_calls"]):
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                    tool_calls.append(ToolCall(
                        id=tc.get("id", f"call_{idx}"),
                        name=tc["function"]["name"],
                        arguments=args,
                    ))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool_call arguments: {e}")
        
        return tool_calls
    
    @staticmethod
    def parse_anthropic_format(response: Dict[str, Any]) -> List[ToolCall]:
        """
        Parse tool calls from Anthropic format.
        
        Args:
            response: Anthropic API response
            
        Returns:
            List of parsed tool calls
        """
        tool_calls = []
        
        # Anthropic uses "content" array with tool_use items
        content = response.get("content", [])
        
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=item.get("id", "call_0"),
                    name=item["name"],
                    arguments=item.get("input", {}),
                ))
        
        return tool_calls
    
    @staticmethod
    def parse(response: Any, format: str = "auto") -> List[ToolCall]:
        """
        Parse tool calls with automatic format detection.
        
        Args:
            response: LLM response (dict or string)
            format: Format hint ("auto", "openai", "anthropic")
            
        Returns:
            List of parsed tool calls
        """
        if not response:
            return []
        
        # If response is a string, no tool calls
        if isinstance(response, str):
            return []
        
        if not isinstance(response, dict):
            logger.warning(f"Unexpected response type: {type(response)}")
            return []
        
        # Try auto-detection if format is "auto"
        if format == "auto":
            # Check for OpenAI markers
            if "function_call" in response or "tool_calls" in response:
                format = "openai"
            # Check for Anthropic markers
            elif "content" in response and isinstance(response["content"], list):
                format = "anthropic"
        
        # Parse based on format
        if format == "openai":
            return ToolCallParser.parse_openai_format(response)
        elif format == "anthropic":
            return ToolCallParser.parse_anthropic_format(response)
        else:
            logger.debug("No tool calls detected in response")
            return []
