import pytest
from datetime import datetime
from plugins.inspector.buffer import EventBuffer, CapturedEvent


class TestEventBuffer:
    """Test EventBuffer functionality."""

    @pytest.fixture
    def buffer(self):
        return EventBuffer(max_size=5)

    def test_append_and_get(self, buffer):
        """Test appending and retrieving events."""
        event = CapturedEvent(
            timestamp=datetime.now(),
            subject="test.event",
            data=b"{}",
            size_bytes=2
        )
        buffer.append(event)
        
        recent = buffer.get_recent()
        assert len(recent) == 1
        assert recent[0] == event

    def test_buffer_overflow(self, buffer):
        """Test buffer respects max size."""
        for i in range(10):
            event = CapturedEvent(
                timestamp=datetime.now(),
                subject=f"test.event.{i}",
                data=b"{}",
                size_bytes=2
            )
            buffer.append(event)
        
        recent = buffer.get_recent(count=10)
        assert len(recent) == 5
        assert recent[0].subject == "test.event.9"  # Most recent first
        assert recent[-1].subject == "test.event.5"

    def test_pattern_filtering(self, buffer):
        """Test filtering by pattern."""
        e1 = CapturedEvent(datetime.now(), "test.foo", b"{}", 2)
        e2 = CapturedEvent(datetime.now(), "test.bar", b"{}", 2)
        e3 = CapturedEvent(datetime.now(), "other.foo", b"{}", 2)
        
        buffer.append(e1)
        buffer.append(e2)
        buffer.append(e3)
        
        # Filter test.*
        recent = buffer.get_recent(pattern="test.*")
        assert len(recent) == 2
        assert recent[0].subject == "test.bar"
        assert recent[1].subject == "test.foo"

    def test_stats(self, buffer):
        """Test statistics tracking."""
        buffer.append(CapturedEvent(datetime.now(), "test.a", b"{}", 2))
        buffer.append(CapturedEvent(datetime.now(), "test.a", b"{}", 2))
        buffer.append(CapturedEvent(datetime.now(), "test.b", b"{}", 2))
        
        stats = buffer.get_stats()
        assert stats["total_events"] == 3
        assert stats["buffer_used"] == 3
        assert stats["buffer_size"] == 5
        
        top = stats["top_subjects"]
        assert len(top) == 2
        assert top[0]["subject"] == "test.a"
        assert top[0]["count"] == 2
