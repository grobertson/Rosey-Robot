"""
MongoDB-style query operator parser for row operations.

Converts filter dictionaries with operators like $gt, $lte into
SQLAlchemy where clauses.

Supports:
- Comparison operators: $eq, $ne, $gt, $gte, $lt, $lte
- Set operators: $in, $nin (Sprint 14 Sortie 2)
- Pattern operators: $like, $ilike (Sprint 14 Sortie 2)
- Existence operators: $exists, $null (Sprint 14 Sortie 2)
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
    >>> 
    >>> # Set membership
    >>> filters = {'username': {'$in': ['alice', 'bob']}}
    >>> clauses = parser.parse_filters(filters, table)
    >>> 
    >>> # Pattern matching
    >>> filters = {'username': {'$like': 'test_%'}}
    >>> clauses = parser.parse_filters(filters, table)
"""

from typing import Any, Dict, List, Callable
from sqlalchemy import Column, and_


class OperatorParser:
    """
    Parse MongoDB-style query operators into SQLAlchemy clauses.
    
    Supports:
    - Comparison operators: $eq, $ne, $gt, $gte, $lt, $lte (Sortie 1)
    - Set operators: $in, $nin (Sortie 2)
    - Pattern operators: $like, $ilike (Sortie 2)
    - Existence operators: $exists, $null (Sortie 2)
    
    All operators include type validation based on table schema.
    
    Attributes:
        COMPARISON_OPS: Dict mapping comparison operators to SQLAlchemy methods
        SET_OPS: Dict mapping set operators to SQLAlchemy methods
        PATTERN_OPS: Dict mapping pattern operators to SQLAlchemy methods
        EXISTENCE_OPS: Dict mapping existence operators to SQLAlchemy methods
        RANGE_OPS: Set of operators requiring numeric/datetime types
        RANGE_COMPATIBLE_TYPES: Set of field types compatible with range operators
        PATTERN_COMPATIBLE_TYPES: Set of field types compatible with pattern operators
    """
    
    # Comparison operators (Sortie 1)
    # Operator name -> SQLAlchemy method (lambda takes column and value)
    COMPARISON_OPS = {
        '$eq': lambda col, val: col == val,
        '$ne': lambda col, val: col != val,
        '$gt': lambda col, val: col > val,
        '$gte': lambda col, val: col >= val,
        '$lt': lambda col, val: col < val,
        '$lte': lambda col, val: col <= val,
    }
    
    # Set membership operators (Sortie 2)
    SET_OPS = {
        '$in': lambda col, vals: col.in_(vals),
        '$nin': lambda col, vals: ~col.in_(vals),  # NOT IN
    }
    
    # Pattern matching operators (Sortie 2)
    PATTERN_OPS = {
        '$like': lambda col, pattern: col.like(pattern),
        '$ilike': lambda col, pattern: col.ilike(pattern),  # Case-insensitive
    }
    
    # Existence/null checking operators (Sortie 2)
    EXISTENCE_OPS = {
        '$exists': lambda col, exists: col.isnot(None) if exists else col.is_(None),
        '$null': lambda col, is_null: col.is_(None) if is_null else col.isnot(None),
    }
    
    # Operators that require numeric or datetime types
    RANGE_OPS = {'$gt', '$gte', '$lt', '$lte'}
    
    # Field types compatible with range operators
    RANGE_COMPATIBLE_TYPES = {'integer', 'float', 'datetime'}
    
    # Field types compatible with pattern operators
    PATTERN_COMPATIBLE_TYPES = {'string', 'text'}
    
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
        
        # Combined operator registry for validation and error messages
        self.all_operators = {
            **self.COMPARISON_OPS,
            **self.SET_OPS,
            **self.PATTERN_OPS,
            **self.EXISTENCE_OPS
        }
    
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
        
        Extended in Sortie 2 with set, pattern, and existence operators.
        
        Args:
            field_name: Field name (for error messages)
            operator: Operator string (e.g., '$gte', '$eq', '$in', '$like')
            value: Operator value (type depends on operator)
            field_type: Field type from schema (e.g., 'integer', 'string')
            column: SQLAlchemy column object
        
        Returns:
            SQLAlchemy where clause (BinaryExpression)
        
        Raises:
            ValueError: If operator unknown or value invalid
            TypeError: If operator incompatible with field type
        
        Examples:
            >>> # Comparison: range operator on integer
            >>> clause = parser._parse_operator('score', '$gte', 100, 'integer', col)
            >>> 
            >>> # Set: membership check
            >>> clause = parser._parse_operator('status', '$in', ['active', 'pending'], 'string', col)
            >>> 
            >>> # Pattern: SQL wildcard match
            >>> clause = parser._parse_operator('name', '$like', 'test_%', 'string', col)
            >>> 
            >>> # Existence: null check
            >>> clause = parser._parse_operator('rating', '$exists', True, 'float', col)
        """
        # Comparison operators (Sortie 1)
        if operator in self.COMPARISON_OPS:
            # Type validation for range operators
            if operator in self.RANGE_OPS:
                if field_type not in self.RANGE_COMPATIBLE_TYPES:
                    raise TypeError(
                        f"Range operator '{operator}' on field '{field_name}' requires "
                        f"numeric or datetime type, got '{field_type}'. "
                        f"Range operators can only be used with: "
                        f"{', '.join(sorted(self.RANGE_COMPATIBLE_TYPES))}"
                    )
            
            op_func = self.COMPARISON_OPS[operator]
            return op_func(column, value)
        
        # Set operators (Sortie 2)
        if operator in self.SET_OPS:
            # Validate value is a list
            if not isinstance(value, list):
                raise TypeError(
                    f"Set operator '{operator}' on field '{field_name}' requires "
                    f"list value, got {type(value).__name__}"
                )
            
            # Validate non-empty list
            if len(value) == 0:
                raise ValueError(
                    f"Set operator '{operator}' on field '{field_name}' requires "
                    f"non-empty list"
                )
            
            op_func = self.SET_OPS[operator]
            return op_func(column, value)
        
        # Pattern operators (Sortie 2)
        if operator in self.PATTERN_OPS:
            # Validate field type
            if field_type not in self.PATTERN_COMPATIBLE_TYPES:
                raise TypeError(
                    f"Pattern operator '{operator}' on field '{field_name}' requires "
                    f"string or text type, got '{field_type}'. "
                    f"Pattern operators can only be used with: "
                    f"{', '.join(sorted(self.PATTERN_COMPATIBLE_TYPES))}"
                )
            
            # Validate value is a string
            if not isinstance(value, str):
                raise TypeError(
                    f"Pattern operator '{operator}' on field '{field_name}' requires "
                    f"string value, got {type(value).__name__}"
                )
            
            op_func = self.PATTERN_OPS[operator]
            return op_func(column, value)
        
        # Existence operators (Sortie 2)
        if operator in self.EXISTENCE_OPS:
            # Validate value is boolean
            if not isinstance(value, bool):
                raise TypeError(
                    f"Existence operator '{operator}' on field '{field_name}' requires "
                    f"boolean value, got {type(value).__name__}"
                )
            
            op_func = self.EXISTENCE_OPS[operator]
            return op_func(column, value)
        
        # Unknown operator
        raise ValueError(
            f"Unknown operator '{operator}' on field '{field_name}'. "
            f"Supported operators: {', '.join(sorted(self.all_operators.keys()))}"
        )
    
    def validate_filter_dict(self, filters: Dict[str, Any]) -> None:
        """
        Validate filter dict without generating clauses.
        
        Useful for pre-validation before executing query. Checks:
        - All field names exist in schema
        - All operators are valid
        - All operators are compatible with field types
        - All operator values have correct types
        
        Args:
            filters: Filter dict to validate
        
        Raises:
            ValueError: If field name, operator, or value invalid
            TypeError: If operator incompatible with field type or value type wrong
        
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
                for operator, value in filter_value.items():
                    # Check operator exists
                    if operator not in self.all_operators:
                        raise ValueError(
                            f"Unknown operator: {operator}"
                        )
                    
                    # Validate comparison operators
                    if operator in self.RANGE_OPS:
                        if field_type not in self.RANGE_COMPATIBLE_TYPES:
                            raise TypeError(
                                f"Cannot use {operator} on {field_type} field"
                            )
                    
                    # Validate set operators
                    if operator in self.SET_OPS:
                        if not isinstance(value, list):
                            raise TypeError(
                                f"Set operator {operator} requires list value"
                            )
                        if len(value) == 0:
                            raise ValueError(
                                f"Set operator {operator} requires non-empty list"
                            )
                    
                    # Validate pattern operators
                    if operator in self.PATTERN_OPS:
                        if field_type not in self.PATTERN_COMPATIBLE_TYPES:
                            raise TypeError(
                                f"Cannot use {operator} on {field_type} field"
                            )
                        if not isinstance(value, str):
                            raise TypeError(
                                f"Pattern operator {operator} requires string value"
                            )
                    
                    # Validate existence operators
                    if operator in self.EXISTENCE_OPS:
                        if not isinstance(value, bool):
                            raise TypeError(
                                f"Existence operator {operator} requires boolean value"
                            )
