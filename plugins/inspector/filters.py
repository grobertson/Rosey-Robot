import re
from typing import List, Optional


class EventFilter:
    """
    Filter events by subject pattern.
    
    Supports glob-like patterns:
    - * matches single segment (e.g., trivia.* matches trivia.start)
    - ** matches multiple segments (e.g., trivia.** matches trivia.game.started)
    - ? matches single character
    """
    
    def __init__(self, pattern: str):
        self.pattern = pattern
        self._regex = self._compile_pattern(pattern)
    
    def matches(self, subject: str) -> bool:
        """Check if subject matches the pattern."""
        return bool(self._regex.match(subject))
    
    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Convert glob pattern to regex."""
        # Handle NATS-style wildcards
        # * = single token
        # > = all remaining tokens
        # ** = multiple tokens
        # ? = single character
        regex = pattern
        regex = regex.replace(".", r"\.")
        regex = regex.replace("?", r".")  # Single character (before **)
        regex = regex.replace("**", r"[^.]+(?:\.[^.]+)*")  # Multiple segments
        regex = regex.replace("*", r"[^.]*")  # Single segment
        regex = regex.replace(">", r".*")  # All remaining
        return re.compile(f"^{regex}$")


class FilterChain:
    """Chain of filters (include/exclude)."""
    
    def __init__(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        self.include_filters = [EventFilter(p) for p in (include or [])]
        self.exclude_filters = [EventFilter(p) for p in (exclude or [])]
    
    def should_capture(self, subject: str) -> bool:
        """Determine if an event should be captured."""
        # If exclude matches, reject
        for f in self.exclude_filters:
            if f.matches(subject):
                return False
        
        # If no include filters, accept all
        if not self.include_filters:
            return True
        
        # If include filters exist, must match one
        for f in self.include_filters:
            if f.matches(subject):
                return True
        
        return False
