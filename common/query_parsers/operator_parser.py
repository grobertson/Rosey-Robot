"""
MongoDB-style query operator parser for row operations.

Converts filter dictionaries with operators like $gt, $lte into
SQLAlchemy where clauses.

Supports:
- Comparison operators: $eq, $ne, $gt, $gte, $lt, $lte
- Type validation based on table schema
- Clear error messages for invalid operations

Example:
    >>> schema = {
    ...     'fields': [
    ...         {'name': 'score', 'type': 'integer', 'required': True},
    ...         {'name': 'username', 'type': 'string', 'required': True}
    ...     ]
    ... }
    >>> parser = OperatorParser(schema)
    >>> 
    >>> # Simple equality (backward compatible)
    >>> filters = {'username': 'alice'}
    >>> clauses = parser.parse_filters(filters, table)
    >>> 
    >>> # Range query
    >>> filters = {'score': {'$gte': 100, '$lte': 200}}
    >>> clauses = parser.parse_filters(filters, table)
"""

from typing import Any, Dict, List, Callable
from sqlalchemy import Column, and_


class OperatorParser:
    """
    Parse MongoDB-style query operators into SQLAlchemy clauses.
    
    Supports comparison operators ($eq, $ne, $gt, $gte, $lt, $lte)
    with type validation based on table schema.
    
    Attributes:
        COMPARISON_OPS: Dict mapping operator names to SQLAlchemy methods
        RANGE_OPS: Set of operators requiring numeric/datetime types
        RANGE_COMPATIBLE_TYPES: Set of field types compatible with range operators
    """
    
    # Operator name -> SQLAlchemy method (lambda takes column and value)
    COMPARISON_OPS = {
        '$eq': lambda col, val: col == val,
        '$ne': lambda col, val: col != val,
        '$gt': lambda col, val: col > val,
        '$gte': lambda col, val: col >= val,
        '$lt': lambda col, val: col < val,
        '$lte': lambda col, val: col <= val,
    }
    
    # Operators that require numeric or datetime types
    RANGE_OPS = {'$gt', '$gte', '$lt', '$lte'}
    
    # Field types compatible with range operators
    RANGE_COMPATIBLE_TYPES = {'integer', 'float', 'datetime'}
    
    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize parser with table schema.
        
        Args:
            schema: Table schema dict with 'fields' key containing field definitions.
                Each field must have 'name' and 'type' keys.
        
        Example:
            >>> schema = {
            ...     'fields': [
            ...         {'name': 'score', 'type': 'integer', 'required': True},
            ...         {'name': 'username', 'type': 'string', 'required': True}
            ...     ]
            ... }
            >>> parser = OperatorParser(schema)
        
        Note:
            Auto-managed fields (id, created_at, updated_at) are automatically
            added to the field registry.
        """
        self.schema = schema
        self.fields = {f['name']: f for f in schema['fields']}
        
        # Add auto-managed fields (from Sprint 13)
        self.fields['id'] = {'name': 'id', 'type': 'integer'}
        self.fields['created_at'] = {'name': 'created_at', 'type': 'datetime'}
        self.fields['updated_at'] = {'name': 'updated_at', 'type': 'datetime'}
    
    def parse_filters(self, filters: Dict[str, Any], table) -> List:
        """
        Parse filter dict into SQLAlchemy where clauses.
        
        Supports both simple equality filters (backward compatible) and
        operator-based filters.
        
        Args:
            filters: MongoDB-style filter dict. Can use:
                - Simple equality: {'username': 'alice'}
                - Operators: {'score': {'$gte': 100}}
                - Multiple operators: {'score': {'$gte': 100, '$lte': 200}}
            table: SQLAlchemy table object with columns
        
        Returns:
            List of SQLAlchemy where clauses that can be combined with and_()
        
        Raises:
            ValueError: If field name invalid or operator unknown
            TypeError: If operator incompatible with field type
        
        Examples:
            >>> # Simple equality
            >>> filters = {'username': 'alice'}
            >>> clauses = parser.parse_filters(filters, table)
            >>> # Returns: [table.c.username == 'alice']
            
            >>> # Operator-based
            >>> filters = {'score': {'$gte': 100}}
            >>> clauses = parser.parse_filters(filters, table)
            >>> # Returns: [table.c.score >= 100]
            
            >>> # Range query (multiple operators on same field)
            >>> filters = {'score': {'$gte': 100, '$lte': 200}}
            >>> clauses = parser.parse_filters(filters, table)
            >>> # Returns: [table.c.score >= 100, table.c.score <= 200]
            
            >>> # Multiple fields
            >>> filters = {
            ...     'score': {'$gte': 100},
            ...     'username': 'alice',
            ...     'active': True
            ... }
            >>> clauses = parser.parse_filters(filters, table)
            >>> # Returns: [score >= 100, username == 'alice', active == True]
        """
        clauses = []
        
        for field_name, filter_value in filters.items():
            # Validate field exists
            if field_name not in self.fields:
                raise ValueError(
                    f"Field '{field_name}' not found in schema. "
                    f"Available fields: {', '.join(sorted(self.fields.keys()))}"
                )
            
            field_def = self.fields[field_name]
            field_type = field_def['type']
            column = table.c[field_name]
            
            # Simple equality (backward compatible with Sprint 13)
            if not isinstance(filter_value, dict):
                clauses.append(column == filter_value)
                continue
            
            # Operator-based filters
            for operator, value in filter_value.items():
                clause = self._parse_operator(
                    field_name,
                    operator,
                    value,
                    field_type,
                    column
                )
                clauses.append(clause)
        
        return clauses
    
    def _parse_operator(
        self,
        field_name: str,
        operator: str,
        value: Any,
        field_type: str,
        column: Column
    ):
        """
        Parse single operator into SQLAlchemy clause.
        
        Args:
            field_name: Field name (for error messages)
            operator: Operator string (e.g., '$gte', '$eq')
            value: Comparison value
            field_type: Field type from schema (e.g., 'integer', 'string')
            column: SQLAlchemy column object
        
        Returns:
            SQLAlchemy where clause (BinaryExpression)
        
        Raises:
            ValueError: If operator unknown
            TypeError: If operator incompatible with field type
        
        Examples:
            >>> # Valid: range operator on integer
            >>> clause = parser._parse_operator('score', '$gte', 100, 'integer', col)
            >>> 
            >>> # Valid: equality on any type
            >>> clause = parser._parse_operator('name', '$eq', 'alice', 'string', col)
            >>> 
            >>> # Invalid: range operator on string
            >>> parser._parse_operator('name', '$gt', 'alice', 'string', col)
            >>> # Raises: TypeError
        """
        # Check operator exists
        if operator not in self.COMPARISON_OPS:
            raise ValueError(
                f"Unknown operator '{operator}' on field '{field_name}'. "
                f"Supported operators: {', '.join(sorted(self.COMPARISON_OPS.keys()))}"
            )
        
        # Type validation for range operators
        if operator in self.RANGE_OPS:
            if field_type not in self.RANGE_COMPATIBLE_TYPES:
                raise TypeError(
                    f"Range operator '{operator}' on field '{field_name}' requires "
                    f"numeric or datetime type, got '{field_type}'. "
                    f"Range operators can only be used with: "
                    f"{', '.join(sorted(self.RANGE_COMPATIBLE_TYPES))}"
                )
        
        # Generate clause using operator function
        op_func = self.COMPARISON_OPS[operator]
        return op_func(column, value)
    
    def validate_filter_dict(self, filters: Dict[str, Any]) -> None:
        """
        Validate filter dict without generating clauses.
        
        Useful for pre-validation before executing query. Checks:
        - All field names exist in schema
        - All operators are valid
        - All operators are compatible with field types
        
        Args:
            filters: Filter dict to validate
        
        Raises:
            ValueError: If field name or operator invalid
            TypeError: If operator incompatible with field type
        
        Example:
            >>> # Validate before using
            >>> try:
            ...     parser.validate_filter_dict({'score': {'$gte': 100}})
            ...     # Valid - proceed with query
            ... except (ValueError, TypeError) as e:
            ...     # Invalid - handle error
            ...     print(f"Invalid filter: {e}")
        """
        for field_name, filter_value in filters.items():
            # Check field exists
            if field_name not in self.fields:
                raise ValueError(
                    f"Field '{field_name}' not found in schema"
                )
            
            field_type = self.fields[field_name]['type']
            
            # Check operators
            if isinstance(filter_value, dict):
                for operator in filter_value.keys():
                    if operator not in self.COMPARISON_OPS:
                        raise ValueError(
                            f"Unknown operator: {operator}"
                        )
                    
                    if operator in self.RANGE_OPS:
                        if field_type not in self.RANGE_COMPATIBLE_TYPES:
                            raise TypeError(
                                f"Cannot use {operator} on {field_type} field"
                            )
