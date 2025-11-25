"""
SQL Parameter Binder for parameterized SQL execution.

This module provides the ParameterBinder class which converts
PostgreSQL-style $N placeholders to SQLite ? syntax and builds
the parameter tuple for safe query execution.
"""

import json
import re
from datetime import date, datetime
from typing import Any

from .sql_errors import ParameterError


class ParameterBinder:
    """
    Converts PostgreSQL-style $N placeholders to SQLite ? syntax.

    PostgreSQL uses $1, $2, $3 (1-indexed, can be reused)
    SQLite uses ? (positional, order of appearance)

    This class handles the conversion and builds the parameter tuple
    in the correct order for execution.

    Example:
        >>> binder = ParameterBinder()
        >>> query, params = binder.bind(
        ...     "SELECT * FROM t WHERE x = $1 AND y = $2",
        ...     ["alice", 42]
        ... )
        >>> query
        'SELECT * FROM t WHERE x = ? AND y = ?'
        >>> params
        ('alice', 42)
    """

    # Pattern for $N placeholders (positive integers only)
    PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\$(\d+)")

    def bind(
        self,
        query: str,
        params: list[Any],
        coerce_types: bool = True,
    ) -> tuple[str, tuple[Any, ...]]:
        """
        Convert PostgreSQL $N placeholders to SQLite ? placeholders.

        Args:
            query: SQL query with $1, $2, $3 placeholders
            params: List of parameter values (0-indexed in Python, but
                   $1 refers to params[0], $2 to params[1], etc.)
            coerce_types: If True, apply type coercion to params

        Returns:
            Tuple of (sqlite_query, param_tuple) where sqlite_query has
            ? placeholders and param_tuple contains values in order of
            placeholder appearance.

        Raises:
            ParameterError: If placeholder references non-existent param

        Example:
            >>> binder = ParameterBinder()
            >>> q, p = binder.bind("SELECT * FROM t WHERE id = $1", [42])
            >>> q
            'SELECT * FROM t WHERE id = ?'
            >>> p
            (42,)

            # Reused placeholders
            >>> q, p = binder.bind(
            ...     "SELECT * FROM t WHERE x = $1 OR y = $1",
            ...     ["value"]
            ... )
            >>> q
            'SELECT * FROM t WHERE x = ? OR y = ?'
            >>> p
            ('value', 'value')
        """
        # Find all placeholders in order of appearance
        matches = list(self.PLACEHOLDER_PATTERN.finditer(query))

        if not matches:
            # No placeholders - return query as-is with empty params
            return query, ()

        # Validate all placeholder indices
        placeholder_nums = [int(m.group(1)) for m in matches]

        # Check for $0 (invalid)
        if 0 in placeholder_nums:
            raise ParameterError(
                "INVALID_PLACEHOLDER",
                "Placeholder $0 is invalid. Placeholders start at $1.",
                {"invalid_placeholder": 0},
            )

        max_placeholder = max(placeholder_nums)

        if max_placeholder > len(params):
            raise ParameterError(
                "PARAM_COUNT_MISMATCH",
                f"Query uses ${max_placeholder} but only "
                f"{len(params)} params provided",
                {
                    "max_placeholder": max_placeholder,
                    "params_provided": len(params),
                },
            )

        # Build result query by replacing placeholders in reverse order
        # (reverse order preserves string positions during replacement)
        result_query = query
        for match in reversed(matches):
            start, end = match.span()
            result_query = result_query[:start] + "?" + result_query[end:]

        # Build params tuple in order of placeholder appearance
        param_list: list[Any] = []
        for match in matches:
            placeholder_num = int(match.group(1))
            value = params[placeholder_num - 1]  # $1 → params[0]
            if coerce_types:
                value = self.coerce_type(value)
            param_list.append(value)

        return result_query, tuple(param_list)

    def coerce_type(self, value: Any) -> Any:
        """
        Coerce Python types to SQLite-compatible types.

        Args:
            value: Python value of any type

        Returns:
            SQLite-compatible value

        Type Mappings:
            - None → NULL (no change)
            - bool → int (0/1)
            - int → int (no change)
            - float → float (no change)
            - str → str (no change)
            - bytes → blob (no change)
            - datetime → ISO 8601 string
            - date → ISO 8601 string
            - list → JSON string
            - dict → JSON string
            - other → str(value)

        Example:
            >>> binder = ParameterBinder()
            >>> binder.coerce_type(True)
            1
            >>> binder.coerce_type(False)
            0
            >>> binder.coerce_type(datetime(2024, 1, 15, 10, 30))
            '2024-01-15T10:30:00'
            >>> binder.coerce_type({"key": "value"})
            '{"key": "value"}'
        """
        if value is None:
            return None
        elif isinstance(value, bool):
            # Must check bool before int (bool is subclass of int)
            return 1 if value else 0
        elif isinstance(value, (int, float, str, bytes)):
            return value
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        else:
            # Fallback: convert to string representation
            return str(value)

    def extract_placeholders(self, query: str) -> list[int]:
        """
        Extract all $N placeholder numbers from query.

        Args:
            query: SQL query string

        Returns:
            List of placeholder numbers in order of appearance

        Example:
            >>> binder = ParameterBinder()
            >>> binder.extract_placeholders("SELECT * FROM t WHERE x = $1 AND y = $2")
            [1, 2]
            >>> binder.extract_placeholders("SELECT * FROM t WHERE x = $2 AND y = $1")
            [2, 1]
        """
        matches = self.PLACEHOLDER_PATTERN.findall(query)
        return [int(m) for m in matches]

    def validate_params(self, query: str, params: list[Any]) -> None:
        """
        Validate that params list has enough values for query placeholders.

        Args:
            query: SQL query with $N placeholders
            params: List of parameter values

        Raises:
            ParameterError: If placeholder references non-existent param
        """
        placeholders = self.extract_placeholders(query)
        if not placeholders:
            return

        # Check for $0
        if 0 in placeholders:
            raise ParameterError(
                "INVALID_PLACEHOLDER",
                "Placeholder $0 is invalid. Placeholders start at $1.",
                {"invalid_placeholder": 0},
            )

        max_placeholder = max(placeholders)
        if max_placeholder > len(params):
            raise ParameterError(
                "PARAM_COUNT_MISMATCH",
                f"Query uses ${max_placeholder} but only "
                f"{len(params)} params provided",
                {
                    "max_placeholder": max_placeholder,
                    "params_provided": len(params),
                },
            )
