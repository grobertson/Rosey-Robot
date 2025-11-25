import pytest
from plugins.inspector.filters import EventFilter, FilterChain


class TestEventFilter:
    """Test EventFilter pattern matching."""

    @pytest.mark.parametrize("pattern,subject,expected", [
        ("test.*", "test.foo", True),
        ("test.*", "test.foo.bar", False),
        ("test.>", "test.foo.bar", True),
        ("test.**", "test.foo.bar", True),
        ("*.foo", "test.foo", True),
        ("test.?", "test.a", True),
        ("test.?", "test.ab", False),
    ])
    def test_matches(self, pattern, subject, expected):
        f = EventFilter(pattern)
        assert f.matches(subject) is expected


class TestFilterChain:
    """Test FilterChain logic."""

    def test_include_only(self):
        chain = FilterChain(include=["test.*"])
        assert chain.should_capture("test.foo") is True
        assert chain.should_capture("other.foo") is False

    def test_exclude_only(self):
        chain = FilterChain(exclude=["test.*"])
        assert chain.should_capture("test.foo") is False
        assert chain.should_capture("other.foo") is True

    def test_include_and_exclude(self):
        chain = FilterChain(
            include=["test.*"],
            exclude=["test.bad"]
        )
        assert chain.should_capture("test.good") is True
        assert chain.should_capture("test.bad") is False
        assert chain.should_capture("other.good") is False
