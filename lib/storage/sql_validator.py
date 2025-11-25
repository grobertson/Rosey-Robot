"""
SQL Query Validator for parameterized SQL execution.

This module provides the QueryValidator class which validates SQL queries
for safety and correctness before execution. It enforces:
- Statement type restrictions (only DML allowed)
- Table namespace isolation (plugin prefix required)
- Stacked query detection (SQL injection prevention)
- Placeholder validation (parameter count matching)
"""

import re
from typing import Any, Optional

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, Where
from sqlparse.tokens import DDL, DML, Keyword, Name

from .sql_errors import (
    ForbiddenStatementError,
    NamespaceViolationError,
    ParameterError,
    SQLSyntaxError,
    StackedQueryError,
    StatementType,
    ValidationResult,
)


class QueryValidator:
    """
    Validates SQL queries for safety and correctness.

    Security Rules:
    1. Only SELECT, INSERT, UPDATE, DELETE allowed
    2. DDL (CREATE, DROP, ALTER) is forbidden
    3. PRAGMA, ATTACH, DETACH are forbidden
    4. Tables must match plugin namespace prefix ({plugin}__)
    5. System tables (sqlite_*) are forbidden
    6. Stacked queries (;) are forbidden

    Example:
        >>> validator = QueryValidator()
        >>> result = validator.validate(
        ...     "SELECT * FROM quote_db__quotes WHERE id = $1",
        ...     plugin="quote-db",
        ...     params=[42]
        ... )
        >>> result.valid
        True
        >>> result.statement_type
        StatementType.SELECT
    """

    # Statement types allowed for execution
    ALLOWED_STATEMENTS: frozenset[StatementType] = frozenset(
        {
            StatementType.SELECT,
            StatementType.INSERT,
            StatementType.UPDATE,
            StatementType.DELETE,
        }
    )

    # Forbidden keywords (case-insensitive) - DDL and admin operations
    FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
        {
            "CREATE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "PRAGMA",
            "ATTACH",
            "DETACH",
            "VACUUM",
            "REINDEX",
            "ANALYZE",
        }
    )

    # System table pattern - blocks access to sqlite internal tables
    SYSTEM_TABLE_PATTERN: re.Pattern[str] = re.compile(r"^sqlite_", re.IGNORECASE)

    # Placeholder pattern for $N syntax
    PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\$(\d+)")

    def __init__(self, allow_cross_plugin: bool = False) -> None:
        """
        Initialize validator.

        Args:
            allow_cross_plugin: If True, allow JOINs across plugin namespaces.
                               Default is False for security.
        """
        self.allow_cross_plugin = allow_cross_plugin

    def validate(
        self,
        query: str,
        plugin: str,
        params: Optional[list[Any]] = None,
    ) -> ValidationResult:
        """
        Validate SQL query for safety and correctness.

        Args:
            query: SQL query string with $N placeholders
            plugin: Plugin name (used to generate namespace prefix)
            params: Optional list of parameters (for count validation)

        Returns:
            ValidationResult with validation outcome, statement type,
            tables, placeholders, warnings, and any error.

        Example:
            >>> validator = QueryValidator()
            >>> result = validator.validate(
            ...     "SELECT * FROM myplugin__data WHERE x = $1",
            ...     plugin="myplugin",
            ...     params=["value"]
            ... )
            >>> result.valid
            True
        """
        params = params or []
        warnings: list[str] = []

        # Step 1: Check for stacked queries (multiple statements)
        if self._has_stacked_queries(query):
            return ValidationResult(
                valid=False,
                statement_type=StatementType.UNKNOWN,
                error=StackedQueryError(
                    "Multiple SQL statements not allowed. Use separate requests.",
                    {"query_preview": query[:100]},
                ),
            )

        # Step 2: Parse with sqlparse
        try:
            parsed = sqlparse.parse(query)
            if not parsed or not str(parsed[0]).strip():
                return ValidationResult(
                    valid=False,
                    statement_type=StatementType.UNKNOWN,
                    error=SQLSyntaxError(
                        "EMPTY_QUERY",
                        "Query is empty or whitespace-only",
                    ),
                )
            stmt = parsed[0]
        except Exception as e:
            return ValidationResult(
                valid=False,
                statement_type=StatementType.UNKNOWN,
                error=SQLSyntaxError(
                    "PARSE_ERROR",
                    f"Failed to parse SQL: {e}",
                ),
            )

        # Step 3: Detect statement type
        statement_type = self._detect_statement_type(stmt)

        # Step 4: Check for forbidden statements
        if statement_type not in self.ALLOWED_STATEMENTS:
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                error=ForbiddenStatementError(
                    "FORBIDDEN_STATEMENT",
                    f"{statement_type.value} statements are not allowed. "
                    f"Use migration system for schema changes.",
                    {"statement_type": statement_type.value},
                ),
            )

        # Step 5: Check for forbidden keywords anywhere in query
        forbidden_found = self._find_forbidden_keywords(stmt)
        if forbidden_found:
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                error=ForbiddenStatementError(
                    "FORBIDDEN_KEYWORD",
                    f"Query contains forbidden keyword: {forbidden_found}",
                    {"keyword": forbidden_found},
                ),
            )

        # Step 6: Extract and validate table names
        tables = self._extract_table_names(stmt)
        namespace_prefix = f"{plugin.replace('-', '_')}__"

        for table in tables:
            # Check system tables
            if self.SYSTEM_TABLE_PATTERN.match(table):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    error=NamespaceViolationError(
                        "SYSTEM_TABLE_ACCESS",
                        f"Access to system table '{table}' is forbidden",
                        {"table": table},
                    ),
                )

            # Check namespace prefix (unless cross-plugin allowed)
            if not self.allow_cross_plugin and not table.startswith(namespace_prefix):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    error=NamespaceViolationError(
                        "NAMESPACE_VIOLATION",
                        f"Table '{table}' not in plugin namespace. "
                        f"Expected prefix: '{namespace_prefix}'",
                        {"table": table, "expected_prefix": namespace_prefix},
                    ),
                )

        # Step 7: Extract and validate placeholders
        placeholders = self._extract_placeholders(query)

        # Check placeholder count vs params
        if placeholders:
            max_placeholder = max(placeholders)
            if len(params) < max_placeholder:
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=tables,
                    placeholders=placeholders,
                    error=ParameterError(
                        "PARAM_COUNT_MISMATCH",
                        f"Query uses ${max_placeholder} but only "
                        f"{len(params)} params provided",
                        {
                            "max_placeholder": max_placeholder,
                            "params_provided": len(params),
                        },
                    ),
                )

            # Warn about gaps in placeholder sequence
            expected = set(range(1, max_placeholder + 1))
            actual = set(placeholders)
            missing = expected - actual
            if missing:
                warnings.append(
                    f"Placeholder gap detected: ${min(missing)} not used. "
                    f"This may indicate a bug."
                )

        # Check for $0 (invalid)
        if 0 in placeholders:
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                tables=tables,
                placeholders=placeholders,
                error=ParameterError(
                    "INVALID_PLACEHOLDER",
                    "Placeholder $0 is invalid. Placeholders start at $1.",
                    {"invalid_placeholder": 0},
                ),
            )

        # Step 8: Check for inline string literals (security warning)
        if self._has_inline_string_literals(stmt):
            warnings.append(
                "Query contains inline string literals. Consider using parameters "
                "for all values to prevent SQL injection."
            )

        # Validation passed
        return ValidationResult(
            valid=True,
            statement_type=statement_type,
            tables=tables,
            placeholders=placeholders,
            warnings=warnings,
            normalized_query=sqlparse.format(
                query,
                strip_whitespace=True,
                keyword_case="upper",
            ),
        )

    def _has_stacked_queries(self, query: str) -> bool:
        """
        Check for multiple statements (SQL injection vector).

        Args:
            query: Raw SQL query string

        Returns:
            True if multiple statements detected
        """
        # Remove string literals to avoid false positives on semicolons in strings
        clean_query = re.sub(r"'[^']*'", "''", query)
        clean_query = re.sub(r'"[^"]*"', '""', clean_query)
        # Remove comments
        clean_query = re.sub(r"--[^\n]*", "", clean_query)
        clean_query = re.sub(r"/\*.*?\*/", "", clean_query, flags=re.DOTALL)
        # Strip trailing semicolon (allowed)
        clean_query = clean_query.strip().rstrip(";")
        # Any remaining semicolon = stacked query
        return ";" in clean_query

    def _detect_statement_type(self, stmt: sqlparse.sql.Statement) -> StatementType:
        """
        Detect SQL statement type from parsed statement.

        Args:
            stmt: Parsed sqlparse Statement object

        Returns:
            StatementType enum value
        """
        first_token = stmt.token_first(skip_ws=True, skip_cm=True)
        if first_token is None:
            return StatementType.UNKNOWN

        token_value = first_token.ttype
        token_str = first_token.value.upper()

        # Check by token type (more reliable)
        if token_value is DML.SELECT:
            return StatementType.SELECT
        elif token_value is DML.INSERT:
            return StatementType.INSERT
        elif token_value is DML.UPDATE:
            return StatementType.UPDATE
        elif token_value is DML.DELETE:
            return StatementType.DELETE
        elif token_value is DDL:
            # Map DDL tokens
            if token_str in ("CREATE", "DROP", "ALTER"):
                return getattr(StatementType, token_str, StatementType.UNKNOWN)

        # Fallback: check by keyword string
        type_map = {
            "SELECT": StatementType.SELECT,
            "INSERT": StatementType.INSERT,
            "UPDATE": StatementType.UPDATE,
            "DELETE": StatementType.DELETE,
            "CREATE": StatementType.CREATE,
            "DROP": StatementType.DROP,
            "ALTER": StatementType.ALTER,
            "TRUNCATE": StatementType.TRUNCATE,
            "PRAGMA": StatementType.PRAGMA,
            "ATTACH": StatementType.ATTACH,
            "DETACH": StatementType.DETACH,
        }
        return type_map.get(token_str, StatementType.UNKNOWN)

    def _find_forbidden_keywords(
        self, stmt: sqlparse.sql.Statement
    ) -> Optional[str]:
        """
        Check for forbidden keywords in query tokens.

        Args:
            stmt: Parsed sqlparse Statement object

        Returns:
            Forbidden keyword found, or None if clean
        """
        for token in stmt.flatten():
            # Check keyword tokens and DDL tokens
            if token.ttype in (Keyword, DDL) or (
                token.ttype is None and token.value.upper() in self.FORBIDDEN_KEYWORDS
            ):
                word = token.value.upper()
                if word in self.FORBIDDEN_KEYWORDS:
                    return word
        return None

    def _extract_table_names(self, stmt: sqlparse.sql.Statement) -> set[str]:
        """
        Extract all table names from SQL statement.

        Handles:
        - FROM clause tables
        - JOIN clause tables
        - INSERT INTO tables
        - UPDATE tables
        - Subqueries (recursive extraction)

        Args:
            stmt: Parsed sqlparse Statement object

        Returns:
            Set of table name strings
        """
        tables: set[str] = set()

        # Track if we've seen a table-introducing keyword
        from_seen = False

        for token in stmt.tokens:
            # Skip whitespace
            if token.is_whitespace:
                continue

            # Check for table-introducing keywords
            if token.ttype is Keyword:
                upper_val = token.value.upper()
                if upper_val in ("FROM", "JOIN", "INTO", "UPDATE"):
                    from_seen = True
                    continue
                elif upper_val in (
                    "WHERE",
                    "SET",
                    "VALUES",
                    "ON",
                    "AND",
                    "OR",
                    "ORDER",
                    "GROUP",
                    "HAVING",
                    "LIMIT",
                ):
                    from_seen = False
                    continue

            # Extract table names after FROM/JOIN/INTO/UPDATE
            if from_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        name = self._get_table_name(identifier)
                        if name:
                            tables.add(name)
                elif isinstance(token, Identifier):
                    name = self._get_table_name(token)
                    if name:
                        tables.add(name)
                elif token.ttype is Name:
                    tables.add(token.value)
                from_seen = False

            # Recurse into parentheses (subqueries)
            if isinstance(token, Parenthesis):
                # Parse content as subquery
                inner = str(token)[1:-1]  # Remove parens
                try:
                    inner_parsed = sqlparse.parse(inner)
                    if inner_parsed:
                        tables.update(self._extract_table_names(inner_parsed[0]))
                except Exception:
                    pass  # Ignore unparseable subqueries

        return tables

    def _get_table_name(self, identifier: Any) -> Optional[str]:
        """
        Extract table name from Identifier (handles aliases).

        Args:
            identifier: sqlparse Identifier or other token

        Returns:
            Table name string, or None if not extractable
        """
        if isinstance(identifier, Identifier):
            # get_real_name() returns the actual table name, not alias
            name = identifier.get_real_name()
            if name:
                return name
            # Fallback to first name token
            for token in identifier.tokens:
                if token.ttype is Name:
                    return token.value
        elif hasattr(identifier, "value"):
            return identifier.value
        return None

    def _extract_placeholders(self, query: str) -> list[int]:
        """
        Extract $N placeholder numbers from query.

        Args:
            query: Raw SQL query string

        Returns:
            List of placeholder numbers in order of appearance
        """
        # First, remove string literals to avoid matching $N in strings
        clean_query = re.sub(r"'[^']*'", "''", query)
        clean_query = re.sub(r'"[^"]*"', '""', clean_query)

        matches = self.PLACEHOLDER_PATTERN.findall(clean_query)
        return [int(m) for m in matches]

    def _has_inline_string_literals(self, stmt: sqlparse.sql.Statement) -> bool:
        """
        Check for string literals in WHERE clause (security warning).

        This is a warning, not an error - inline literals in WHERE clauses
        may indicate SQL injection vulnerabilities.

        Args:
            stmt: Parsed sqlparse Statement object

        Returns:
            True if inline string literals found in WHERE clause
        """
        for token in stmt.tokens:
            if isinstance(token, Where):
                where_str = str(token)
                # Check for non-empty quoted strings
                if re.search(r"'[^']+'" , where_str) or re.search(
                    r'"[^"]+"', where_str
                ):
                    return True
        return False
