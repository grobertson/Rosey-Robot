"""
Calculator Tool
===============

Mathematical calculation tool for LLM.
"""

import re
import ast
import operator
import logging
from typing import Dict, Any

from ..types import ToolDefinition, ToolParameter, ParameterType

logger = logging.getLogger(__name__)


# Safe operators for eval
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """
    Safely evaluate a mathematical expression AST node.
    
    Only allows basic arithmetic operations, no function calls.
    """
    if isinstance(node, ast.Num):  # <number>
        return node.n
    elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):  # <operator> <operand>
        operand = _safe_eval(node.operand)
        op = SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(operand)
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


async def calculate(arguments: Dict[str, Any], context: dict) -> str:
    """
    Calculate the result of a mathematical expression.
    
    Args:
        arguments: {"expression": "math expression"}
        context: Execution context
        
    Returns:
        Calculation result as string
        
    Raises:
        ValueError: If expression is invalid or unsafe
    """
    expression = arguments.get("expression", "")
    
    if not expression:
        raise ValueError("No expression provided")
    
    # Remove whitespace
    expression = expression.replace(" ", "")
    
    # Validate expression (only digits, operators, parentheses)
    if not re.match(r'^[\d+\-*/().%^]+$', expression):
        raise ValueError("Expression contains invalid characters")
    
    try:
        # Parse expression into AST
        node = ast.parse(expression, mode='eval').body
        
        # Safely evaluate
        result = _safe_eval(node)
        
        logger.info(f"Calculated: {expression} = {result}")
        
        return f"{expression} = {result}"
        
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        raise ValueError(f"Invalid expression: {str(e)}")


# Tool definition
CALCULATOR_TOOL = ToolDefinition(
    name="calculate",
    description="Perform mathematical calculations. Supports +, -, *, /, %, ** (power), and parentheses.",
    parameters=[
        ToolParameter(
            name="expression",
            type=ParameterType.STRING,
            description="Mathematical expression to evaluate (e.g., '2 + 2', '(10 * 5) / 2')",
            required=True,
        )
    ],
    category="utility",
)
