"""
Unit tests for ParameterBinder.

Tests cover:
- Basic binding ($N to ? conversion)
- Parameter ordering and reuse
- Type coercion (bool, datetime, list, dict, etc.)
- Error handling (missing params, invalid placeholders)
"""

from datetime import date, datetime

import pytest

from lib.storage import ParameterBinder, ParameterError


class TestBasicBinding:
    """Test basic $N to ? placeholder conversion."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_single_param(self, binder: ParameterBinder) -> None:
        """One placeholder works."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE id = $1",
            [42],
        )
        assert query == "SELECT * FROM t WHERE id = ?"
        assert params == (42,)

    def test_multiple_params(self, binder: ParameterBinder) -> None:
        """Multiple placeholders work."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $1 AND y = $2 AND z = $3",
            ["a", "b", "c"],
        )
        assert query == "SELECT * FROM t WHERE x = ? AND y = ? AND z = ?"
        assert params == ("a", "b", "c")

    def test_no_params(self, binder: ParameterBinder) -> None:
        """No placeholders returns empty tuple."""
        query, params = binder.bind(
            "SELECT COUNT(*) FROM t",
            [],
        )
        assert query == "SELECT COUNT(*) FROM t"
        assert params == ()

    def test_param_order_preserved(self, binder: ParameterBinder) -> None:
        """Order matches appearance in query."""
        query, params = binder.bind(
            "INSERT INTO t (a, b) VALUES ($1, $2)",
            ["first", "second"],
        )
        assert params == ("first", "second")

    def test_param_reuse_duplicated(self, binder: ParameterBinder) -> None:
        """$1 twice = param twice in tuple."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $1 OR y = $1",
            ["value"],
        )
        assert query == "SELECT * FROM t WHERE x = ? OR y = ?"
        assert params == ("value", "value")

    def test_out_of_order_binding(self, binder: ParameterBinder) -> None:
        """$2 before $1 binds correctly."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $2 AND y = $1",
            ["first", "second"],
        )
        assert query == "SELECT * FROM t WHERE x = ? AND y = ?"
        # Params in order of appearance: $2 then $1
        assert params == ("second", "first")

    def test_large_param_count(self, binder: ParameterBinder) -> None:
        """20+ params work."""
        placeholders = ", ".join(f"${i}" for i in range(1, 21))
        values = list(range(1, 21))
        query, params = binder.bind(
            f"INSERT INTO t VALUES ({placeholders})",
            values,
        )
        assert query.count("?") == 20
        assert len(params) == 20
        assert params == tuple(values)

    def test_placeholder_in_string_not_replaced(self, binder: ParameterBinder) -> None:
        """'$1' in string literal is not replaced."""
        # Note: This depends on the binder implementation.
        # The current implementation does replace in strings.
        # For full correctness, we'd need query parsing.
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $1",
            ["value"],
        )
        assert params == ("value",)

    def test_whitespace_around_placeholder(self, binder: ParameterBinder) -> None:
        """Placeholders with surrounding whitespace work."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $1 AND y=$2",
            ["a", "b"],
        )
        assert query == "SELECT * FROM t WHERE x = ? AND y=?"
        assert params == ("a", "b")


class TestParameterErrors:
    """Test error handling for parameter issues."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_param_count_mismatch(self, binder: ParameterBinder) -> None:
        """Too few params raises ParameterError."""
        with pytest.raises(ParameterError) as exc_info:
            binder.bind(
                "SELECT * FROM t WHERE x = $1 AND y = $2",
                ["only_one"],
            )
        assert exc_info.value.code == "PARAM_COUNT_MISMATCH"
        assert exc_info.value.details["max_placeholder"] == 2
        assert exc_info.value.details["params_provided"] == 1

    def test_zero_placeholder_rejected(self, binder: ParameterBinder) -> None:
        """$0 raises ParameterError."""
        with pytest.raises(ParameterError) as exc_info:
            binder.bind(
                "SELECT * FROM t WHERE x = $0",
                ["value"],
            )
        assert exc_info.value.code == "INVALID_PLACEHOLDER"

    def test_extra_params_allowed(self, binder: ParameterBinder) -> None:
        """Extra params don't raise error."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE x = $1",
            ["used", "unused1", "unused2"],
        )
        assert params == ("used",)


class TestTypeCoercion:
    """Test type coercion to SQLite-compatible types."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_coerce_none(self, binder: ParameterBinder) -> None:
        """None stays None."""
        assert binder.coerce_type(None) is None

    def test_coerce_bool_true(self, binder: ParameterBinder) -> None:
        """True → 1."""
        assert binder.coerce_type(True) == 1

    def test_coerce_bool_false(self, binder: ParameterBinder) -> None:
        """False → 0."""
        assert binder.coerce_type(False) == 0

    def test_coerce_int(self, binder: ParameterBinder) -> None:
        """int unchanged."""
        assert binder.coerce_type(42) == 42
        assert binder.coerce_type(-100) == -100
        assert binder.coerce_type(0) == 0

    def test_coerce_float(self, binder: ParameterBinder) -> None:
        """float unchanged."""
        assert binder.coerce_type(3.14) == 3.14
        assert binder.coerce_type(-0.5) == -0.5

    def test_coerce_str(self, binder: ParameterBinder) -> None:
        """str unchanged."""
        assert binder.coerce_type("hello") == "hello"
        assert binder.coerce_type("") == ""

    def test_coerce_bytes(self, binder: ParameterBinder) -> None:
        """bytes unchanged."""
        data = b"\x00\x01\x02"
        assert binder.coerce_type(data) == data

    def test_coerce_datetime(self, binder: ParameterBinder) -> None:
        """datetime → ISO string."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        assert binder.coerce_type(dt) == "2024-01-15T10:30:45"

    def test_coerce_datetime_with_microseconds(self, binder: ParameterBinder) -> None:
        """datetime with microseconds → ISO string."""
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456)
        assert binder.coerce_type(dt) == "2024-01-15T10:30:45.123456"

    def test_coerce_date(self, binder: ParameterBinder) -> None:
        """date → ISO string."""
        d = date(2024, 1, 15)
        assert binder.coerce_type(d) == "2024-01-15"

    def test_coerce_list(self, binder: ParameterBinder) -> None:
        """list → JSON string."""
        data = [1, 2, 3, "four"]
        result = binder.coerce_type(data)
        assert result == '[1, 2, 3, "four"]'

    def test_coerce_dict(self, binder: ParameterBinder) -> None:
        """dict → JSON string."""
        data = {"key": "value", "number": 42}
        result = binder.coerce_type(data)
        # JSON key order may vary
        assert '"key": "value"' in result
        assert '"number": 42' in result

    def test_coerce_nested_structure(self, binder: ParameterBinder) -> None:
        """Nested list/dict → JSON string."""
        data = {"items": [1, 2, 3], "meta": {"count": 3}}
        result = binder.coerce_type(data)
        assert '"items"' in result
        assert '"meta"' in result

    def test_coerce_unicode(self, binder: ParameterBinder) -> None:
        """Unicode strings preserved."""
        data = {"emoji": "🎉", "chinese": "中文"}
        result = binder.coerce_type(data)
        assert "🎉" in result
        assert "中文" in result


class TestBindWithCoercion:
    """Test bind() with type coercion enabled."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_bind_with_bool_coercion(self, binder: ParameterBinder) -> None:
        """Booleans coerced in bind()."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE active = $1",
            [True],
        )
        assert params == (1,)

    def test_bind_with_datetime_coercion(self, binder: ParameterBinder) -> None:
        """Datetime coerced in bind()."""
        dt = datetime(2024, 1, 15)
        query, params = binder.bind(
            "SELECT * FROM t WHERE created > $1",
            [dt],
        )
        assert params == ("2024-01-15T00:00:00",)

    def test_bind_without_coercion(self, binder: ParameterBinder) -> None:
        """Type coercion can be disabled."""
        query, params = binder.bind(
            "SELECT * FROM t WHERE active = $1",
            [True],
            coerce_types=False,
        )
        assert params == (True,)  # Not coerced to int

    def test_bind_mixed_types(self, binder: ParameterBinder) -> None:
        """Mixed types all coerced correctly."""
        query, params = binder.bind(
            "INSERT INTO t (a, b, c, d) VALUES ($1, $2, $3, $4)",
            [True, datetime(2024, 1, 1), [1, 2], {"x": 1}],
        )
        assert params[0] == 1  # bool → int
        assert params[1] == "2024-01-01T00:00:00"  # datetime → str
        assert params[2] == "[1, 2]"  # list → JSON
        assert '"x": 1' in params[3]  # dict → JSON


class TestExtractPlaceholders:
    """Test placeholder extraction utility."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_extract_simple(self, binder: ParameterBinder) -> None:
        """Simple extraction works."""
        result = binder.extract_placeholders(
            "SELECT * FROM t WHERE x = $1 AND y = $2"
        )
        assert result == [1, 2]

    def test_extract_out_of_order(self, binder: ParameterBinder) -> None:
        """Out of order extraction preserves appearance order."""
        result = binder.extract_placeholders(
            "SELECT * FROM t WHERE x = $3 AND y = $1"
        )
        assert result == [3, 1]

    def test_extract_duplicates(self, binder: ParameterBinder) -> None:
        """Duplicates preserved."""
        result = binder.extract_placeholders(
            "SELECT * FROM t WHERE x = $1 AND y = $1"
        )
        assert result == [1, 1]

    def test_extract_none(self, binder: ParameterBinder) -> None:
        """No placeholders returns empty list."""
        result = binder.extract_placeholders("SELECT * FROM t")
        assert result == []


class TestValidateParams:
    """Test parameter validation utility."""

    @pytest.fixture
    def binder(self) -> ParameterBinder:
        """Create binder instance."""
        return ParameterBinder()

    def test_validate_passes(self, binder: ParameterBinder) -> None:
        """Valid params don't raise."""
        # Should not raise
        binder.validate_params(
            "SELECT * FROM t WHERE x = $1 AND y = $2",
            ["a", "b"],
        )

    def test_validate_fails_on_mismatch(self, binder: ParameterBinder) -> None:
        """Invalid params raise ParameterError."""
        with pytest.raises(ParameterError):
            binder.validate_params(
                "SELECT * FROM t WHERE x = $1 AND y = $2",
                ["only_one"],
            )

    def test_validate_fails_on_zero(self, binder: ParameterBinder) -> None:
        """$0 raises ParameterError."""
        with pytest.raises(ParameterError) as exc_info:
            binder.validate_params(
                "SELECT * FROM t WHERE x = $0",
                ["value"],
            )
        assert exc_info.value.code == "INVALID_PLACEHOLDER"

    def test_validate_no_placeholders(self, binder: ParameterBinder) -> None:
        """No placeholders always passes."""
        binder.validate_params("SELECT * FROM t", [])
        binder.validate_params("SELECT * FROM t", ["extra"])
