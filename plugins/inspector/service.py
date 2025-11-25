from typing import List, Optional, Callable
from .buffer import EventBuffer, CapturedEvent
from .filters import FilterChain


class InspectorService:
    """
    Service exposed to other plugins for inspection.
    
    Example usage from another plugin:
        inspector = await get_service("inspector")
        events = inspector.get_recent_events(pattern="trivia.*")
    """
    
    def __init__(self, buffer: EventBuffer, filter_chain: FilterChain):
        self._buffer = buffer
        self._filter_chain = filter_chain
        self._paused = False
        self._subscribers: List[Callable] = []
    
    @property
    def is_paused(self) -> bool:
        """Check if capturing is paused."""
        return self._paused
    
    def pause(self) -> None:
        """Pause event capturing."""
        self._paused = True
    
    def resume(self) -> None:
        """Resume event capturing."""
        self._paused = False
    
    def get_recent_events(
        self, 
        count: int = 10, 
        pattern: Optional[str] = None
    ) -> List[CapturedEvent]:
        """Get recent events, optionally filtered."""
        return self._buffer.get_recent(count, pattern)
    
    def get_stats(self) -> dict:
        """Get capture statistics."""
        return self._buffer.get_stats()
    
    def subscribe(self, callback: Callable[[CapturedEvent], None]) -> None:
        """Subscribe to captured events (for real-time streaming)."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable) -> None:
        """Unsubscribe from captured events."""
        self._subscribers.remove(callback)
    
    def _notify_subscribers(self, event: CapturedEvent) -> None:
        """Notify all subscribers of a new event."""
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                pass  # Don't let subscriber errors break capture
