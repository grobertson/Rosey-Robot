from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Iterator, Dict
from collections import deque
import json
import re


@dataclass
class CapturedEvent:
    """A captured NATS event."""
    timestamp: datetime
    subject: str
    data: bytes
    size_bytes: int
    
    @property
    def data_decoded(self) -> Optional[dict]:
        """Attempt to decode data as JSON."""
        try:
            return json.loads(self.data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    
    @property
    def preview(self) -> str:
        """Get a preview of the data (truncated)."""
        try:
            text = self.data.decode()
            if len(text) > 100:
                return text[:100] + "..."
            return text
        except UnicodeDecodeError:
            return f"<binary {self.size_bytes} bytes>"
    
    def matches_pattern(self, pattern: str) -> bool:
        """Check if subject matches a glob-like pattern."""
        # Simple glob matching
        regex = pattern.replace(".", r"\.")
        regex = regex.replace("**", r".*")
        regex = regex.replace("*", r"[^.]*")
        regex = regex.replace(">", r".*")
        return bool(re.match(f"^{regex}$", self.subject))


class EventBuffer:
    """
    Circular buffer for storing recent events.
    
    Thread-safe for append and iteration.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._buffer: deque[CapturedEvent] = deque(maxlen=max_size)
        self._total_count = 0
        self._subject_counts: Dict[str, int] = {}
    
    def append(self, event: CapturedEvent) -> None:
        """Add an event to the buffer."""
        self._buffer.append(event)
        self._total_count += 1
        
        # Track subject counts
        # Normalize to base subject (remove trailing segments for wildcards)
        base_subject = self._normalize_subject(event.subject)
        self._subject_counts[base_subject] = self._subject_counts.get(base_subject, 0) + 1
    
    def get_recent(
        self, 
        count: int = 10, 
        pattern: Optional[str] = None
    ) -> List[CapturedEvent]:
        """
        Get recent events, optionally filtered by pattern.
        
        Args:
            count: Max number of events to return
            pattern: Glob-like pattern to filter (e.g., "trivia.*")
        
        Returns:
            List of matching events, most recent first
        """
        events = list(self._buffer)
        events.reverse()  # Most recent first
        
        if pattern:
            events = [e for e in events if e.matches_pattern(pattern)]
            
        return events[:count]
    
    def get_stats(self) -> dict:
        """Get buffer statistics."""
        return {
            "total_events": self._total_count,
            "buffer_size": self.max_size,
            "buffer_used": len(self._buffer),
            "top_subjects": self._get_top_subjects(10),
        }
    
    def _get_top_subjects(self, limit: int) -> List[dict]:
        """Get most common subjects."""
        sorted_subjects = sorted(
            self._subject_counts.items(),
            key=lambda x: -x[1]
        )[:limit]
        return [{"subject": s, "count": c} for s, c in sorted_subjects]
    
    def _normalize_subject(self, subject: str) -> str:
        """Normalize subject for counting (collapse numbered segments)."""
        # Collapse segments that look like IDs or numbers
        parts = subject.split(".")
        normalized = []
        for part in parts:
            if part.isdigit() or (len(part) > 20 and "-" in part): # UUID-ish
                normalized.append("*")
            else:
                normalized.append(part)
        return ".".join(normalized)
    
    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        self._subject_counts.clear()
        # Keep total count for lifetime stats
