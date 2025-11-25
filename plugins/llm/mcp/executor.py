"""
MCP Tool Executor
=================

Executes tool calls from LLM responses with validation and error handling.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

from .types import ToolCall, ToolResult, ToolDefinition, ParameterType
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


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
        """
        Initialize tool executor.
        
        Args:
            registry: Tool registry
            timeout: Maximum execution time per tool (seconds)
        """
        self._registry = registry
        self._timeout = timeout
        logger.info(f"Tool executor initialized (timeout: {timeout}s)")
    
    async def execute(
        self,
        tool_calls: List[ToolCall],
        context: dict,
    ) -> List[ToolResult]:
        """
        Execute a list of tool calls sequentially.
        
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
        
        Only use when tools are independent and don't have side effects
        that depend on each other.
        
        Args:
            tool_calls: List of tool calls from LLM
            context: Execution context
            
        Returns:
            List of tool results
        """
        tasks = [
            self._execute_single(call, context)
            for call in tool_calls
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_single(
        self,
        call: ToolCall,
        context: dict,
    ) -> ToolResult:
        """
        Execute a single tool call with validation and timeout.
        
        Args:
            call: Tool call to execute
            context: Execution context
            
        Returns:
            ToolResult with success/failure
        """
        # Get tool
        tool = self._registry.get(call.name)
        
        if not tool:
            logger.warning(f"Unknown tool requested: {call.name}")
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
            logger.warning(
                f"Tool {call.name} parameter validation failed: {validation_error}"
            )
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=validation_error,
            )
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(call.arguments, exec_context),
                timeout=self._timeout
            )
            
            logger.debug(
                f"Tool {call.name} executed: "
                f"success={result.success}"
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Tool {call.name} timed out after {self._timeout}s")
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=f"Tool execution timed out after {self._timeout}s",
            )
        except Exception as e:
            logger.error(f"Tool {call.name} execution error: {e}", exc_info=True)
            return ToolResult(
                tool_call_id=call.id,
                success=False,
                error=f"Execution error: {str(e)}",
            )
    
    def _validate_params(
        self,
        arguments: Dict[str, Any],
        definition: ToolDefinition,
    ) -> Optional[str]:
        """
        Validate tool parameters.
        
        Args:
            arguments: Provided arguments
            definition: Tool definition with parameter specs
            
        Returns:
            Error message if validation fails, None if valid
        """
        # Check required parameters
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                if param.default is None:
                    return f"Missing required parameter: {param.name}"
                # Use default if available
                arguments[param.name] = param.default
        
        # Check parameter types
        for name, value in arguments.items():
            # Find parameter definition
            param = next(
                (p for p in definition.parameters if p.name == name),
                None
            )
            
            if not param:
                # Unknown parameter - warn but allow
                logger.debug(f"Unknown parameter: {name}")
                continue
            
            # Type check
            if not self._check_type(value, param.type):
                return (
                    f"Invalid type for {name}: "
                    f"expected {param.type.value}, got {type(value).__name__}"
                )
            
            # Enum check
            if param.enum and value not in param.enum:
                return (
                    f"Invalid value for {name}: "
                    f"must be one of {param.enum}"
                )
        
        return None
    
    def _check_type(self, value: Any, expected: ParameterType) -> bool:
        """
        Check if value matches expected type.
        
        Args:
            value: Value to check
            expected: Expected parameter type
            
        Returns:
            True if type matches
        """
        if expected == ParameterType.STRING:
            return isinstance(value, str)
        elif expected == ParameterType.NUMBER:
            return isinstance(value, (int, float))
        elif expected == ParameterType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected == ParameterType.BOOLEAN:
            return isinstance(value, bool)
        elif expected == ParameterType.ARRAY:
            return isinstance(value, list)
        elif expected == ParameterType.OBJECT:
            return isinstance(value, dict)
        
        return False
