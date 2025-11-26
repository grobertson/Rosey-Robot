"""
Time Tool
=========

Current time and date information tool for LLM.
"""

from datetime import datetime
from typing import Dict, Any
import logging

from ..types import ToolDefinition, ToolParameter, ParameterType

logger = logging.getLogger(__name__)


async def get_current_time(arguments: Dict[str, Any], context: dict) -> str:
    """
    Get current date and time.
    
    Args:
        arguments: {"format": "format string" (optional)}
        context: Execution context
        
    Returns:
        Current time as formatted string
    """
    format_str = arguments.get("format", "%Y-%m-%d %H:%M:%S")
    
    try:
        now = datetime.now()
        formatted = now.strftime(format_str)
        
        logger.info(f"Get time: {formatted}")
        
        return formatted
        
    except Exception as e:
        logger.error(f"Time formatting error: {e}")
        # Return current time with default format on error
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Tool definition
TIME_TOOL = ToolDefinition(
    name="get_current_time",
    description="Get the current date and time. Useful for time-sensitive queries or scheduling.",
    parameters=[
        ToolParameter(
            name="format",
            type=ParameterType.STRING,
            description="strftime format string (default: '%Y-%m-%d %H:%M:%S')",
            required=False,
            default="%Y-%m-%d %H:%M:%S",
        )
    ],
    category="utility",
)
